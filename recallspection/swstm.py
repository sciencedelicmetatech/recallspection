"""
SWSTM - Semantic memory core.

Two documented, measured weaknesses of plain embedding-similarity search
are addressed here as FIRST-CLASS features, not bolted on:

  1. Recency/contradiction: cosine similarity has no concept of time.
     Facts sharing an `entity_id` are versioned; retrieval returns the
     most recent version by default. Verified: old-vs-new address test.

  2. Negation blindness: a sentence-transformer embedding assigns high
     similarity (measured: 0.93-0.97) to a statement and its negation.
     A two-stage retrieve-then-rerank pipeline is used: embeddings do
     fast coarse retrieval, then an NLI cross-encoder resolves
     entailment/contradiction on the shortlist only (NLI does not scale
     to full-corpus search, hence two stages, not one).

Honesty note: neither fix is claimed as a novel algorithm. Recency
versioning is basic bitemporal data modeling; retrieve-then-rerank with
NLI is standard IR practice. What's new here, if anything, is that they
are applied to two specific, measured failures of THIS system's prior
behavior, with reproducible numbers -- not a general "beats mainstream"
claim.

Modes (kept for interface compatibility with api.py):
  "flat"         -- brute-force cosine search, fine up to a few thousand facts.
  "hierarchical" -- k-means-clustered search for larger fact counts.
  "auto"         -- picks flat below a threshold, hierarchical above.
PQ (product-quantized) mode is NOT implemented in this file. The
original README claimed "100%" at PQ scale with no published
prediction log; do not re-add that claim until it is backed by a
reproducible artifact (see test_swstm.py; run the SAME harness this
docstring's fixes were validated against, not a self-consistency check).
"""

import time
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, CrossEncoder

logger = logging.getLogger("recallspection.swstm")

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-base"
NLI_LABELS = ["contradiction", "entailment", "neutral"]

# Calibrate this per deployment/embedding model -- do NOT copy a threshold
# from a different embedding space (this was a real mistake caught during
# development; see project history). A quick calibration recipe is in
# tests/test_swstm.py::test_calibrate_abstain_threshold.
DEFAULT_ABSTAIN_THRESHOLD = 0.30


class _EmbeddingIndex:
    """Shared embedding logic for flat and hierarchical modes."""

    def __init__(self, n_clusters: Optional[int] = None):
        self.model = SentenceTransformer(EMBED_MODEL_NAME)
        self.value_map: Dict[str, dict] = {}   # key -> {text, value, entity_id, ts}
        self._matrix: Optional[np.ndarray] = None
        self._keys_order: List[str] = []
        self._dirty = True
        self.n_clusters = n_clusters
        self._kmeans: Optional[KMeans] = None

    def add(self, key: str, text: str, value: Any, entity_id: Optional[str], ts: Optional[float]):
        self.value_map[key] = {
            "text": text,
            "value": value,
            "entity_id": entity_id or key,
            "ts": ts if ts is not None else time.time(),
        }
        self._dirty = True

    def _current_view(self) -> Dict[str, dict]:
        """Entity-scoped recency filter: only the newest fact per
        entity_id is 'current'. Fixes the address_old/address_new class
        of bug -- structural, not similarity-dependent."""
        latest: Dict[str, Tuple[str, float]] = {}
        for k, f in self.value_map.items():
            eid = f["entity_id"]
            if eid not in latest or f["ts"] > latest[eid][1]:
                latest[eid] = (k, f["ts"])
        keep = {k for k, _ in latest.values()}
        return {k: v for k, v in self.value_map.items() if k in keep}

    def _rebuild(self, current_only: bool):
        facts = self._current_view() if current_only else self.value_map
        self._keys_order = list(facts.keys())
        if not self._keys_order:
            self._matrix = None
            self._dirty = False
            return
        texts = [facts[k]["text"] for k in self._keys_order]
        self._matrix = self.model.encode(texts, normalize_embeddings=True)
        if self.n_clusters and len(self._keys_order) >= self.n_clusters:
            self._kmeans = KMeans(n_clusters=self.n_clusters, n_init=10, random_state=42).fit(self._matrix)
        self._dirty = False

    def search(self, query: str, top_k: int, current_only: bool, n_probe: int = 3
               ) -> List[Tuple[str, float]]:
        if self._dirty:
            self._rebuild(current_only)
        if self._matrix is None or not self._keys_order:
            return []
        qvec = self.model.encode([query], normalize_embeddings=True)

        if self._kmeans is not None:
            centroid_sims = cosine_similarity(qvec, self._kmeans.cluster_centers_)[0]
            probe = np.argsort(-centroid_sims)[:n_probe]
            candidate_idx = [i for i, lbl in enumerate(self._kmeans.labels_) if lbl in probe]
        else:
            candidate_idx = list(range(len(self._keys_order)))

        sub_matrix = self._matrix[candidate_idx]
        sims = cosine_similarity(qvec, sub_matrix)[0]
        ranked = np.argsort(-sims)[:top_k]
        return [(self._keys_order[candidate_idx[i]], float(sims[i])) for i in ranked]


class SWSTMEngine:
    def __init__(self, mode: str = "flat", flat_num_slots: int = 200,
                 abstain_threshold: float = DEFAULT_ABSTAIN_THRESHOLD,
                 use_nli_rerank: bool = True):
        self.mode = mode
        self.flat_num_slots = flat_num_slots
        self.abstain_threshold = abstain_threshold
        self.use_nli_rerank = use_nli_rerank

        n_clusters = None if mode == "flat" else max(4, flat_num_slots // 50)
        self.memory = _EmbeddingIndex(n_clusters=n_clusters)
        self._nli: Optional[CrossEncoder] = None  # lazy-loaded, it's a 738MB model

    @property
    def fact_count(self) -> int:
        return len(self.memory.value_map)

    def _get_nli(self) -> CrossEncoder:
        if self._nli is None:
            self._nli = CrossEncoder(NLI_MODEL_NAME)
        return self._nli

    def add(self, key: str, value: str, entity_id: Optional[str] = None,
            timestamp: Optional[float] = None) -> str:
        self.memory.add(key, text=f"{key}: {value}" if key not in value else value,
                         value=value, entity_id=entity_id, ts=timestamp)
        return f"Stored '{key}' -> '{value}'"

    def get(self, query: str, top_k: int = 1, current_only: bool = True,
            rerank_candidates: int = 8) -> List[str]:
        """
        Retrieval pipeline:
          1. Coarse retrieval via embeddings (fast, scales).
          2. If use_nli_rerank: rerank the shortlist by contradiction/
             entailment relative to the query, penalizing contradictions.
             This is the fix for the measured negation-blindness failure.
          3. Abstain (return []) if the best remaining score is below
             threshold, rather than confidently returning a wrong match.
        """
        candidates = self.memory.search(query, top_k=max(rerank_candidates, top_k),
                                         current_only=current_only)
        if not candidates:
            return []

        if self.use_nli_rerank:
            nli = self._get_nli()
            facts = self.memory._current_view() if current_only else self.memory.value_map
            reranked = []
            for key, sim in candidates:
                fact_text = facts[key]["text"]
                relation_scores = nli.predict([(fact_text, query)])[0]
                relation = NLI_LABELS[int(np.argmax(relation_scores))]
                score = sim
                if relation == "contradiction":
                    score -= 0.5   # strong penalty: this is the OPPOSITE of the query's claim
                elif relation == "entailment":
                    score += 0.1   # small boost: confirmed consistent
                reranked.append((key, score))
            reranked.sort(key=lambda x: -x[1])
            candidates = reranked

        if not candidates or candidates[0][1] < self.abstain_threshold:
            return []

        facts = self.memory._current_view() if current_only else self.memory.value_map
        return [str(facts[k]["value"]) for k, _ in candidates[:top_k]]
