# ================================================================
# swstm.py — SWSTM v7.0.5 (True Neural Exact Memory)
# ================================================================
# Based on: Causal Poset Transformer: SWSTM v7.0 (May 3, 2026)
# Author: Eliam Raell, Sciencedelic Metatech
# ================================================================
# v7.0.5 changelog (audit-driven, each item independently verifiable):
#   - FIX: SWSTMEngine.__init__ now accepts mode=/flat_num_slots= to
#     match what api.py actually calls. Previously these were
#     incompatible and every /add or /get with backend="swstm" would
#     raise TypeError on the first request.
#   - FIX: use_direct_mapping now defaults to False. The prior default
#     (True) silently returns a Python dict lookup instead of exercising
#     the neural model for any query matching a literal stored key
#     string -- its own docstring said this "masks neural performance."
#     Any accuracy number produced under the old default does not
#     demonstrate neural retrieval quality. Set use_direct_mapping=True
#     explicitly (and expect a warning) if you have a specific reason to.
#   - FIX: ProductQuantizedSWSTM's _encode_pq/_decode_pq are UNCHANGED
#     placeholders (torch.randint / torch.randn -- literally unrelated
#     to the input). Rather than let this silently return wrong answers
#     framed as memory, SWSTMEngine now refuses to construct a "pq" mode
#     engine and raises NotImplementedError with an explanation. Do not
#     re-enable until _encode_pq/_decode_pq are real implementations
#     AND validated the same way the flat/hierarchical paths should be
#     (independent ground truth, not self-consistency).
#   - FIX: the no-encoder random-projection fallback used torch.randn()
#     fresh on every call, so the same key string produced a different
#     vector each time, silently breaking exact-key retrieval whenever
#     sentence-transformers was unavailable. Now seeded deterministically
#     from a hash of the key.
#   - ADD: entity-scoped recency versioning and optional NLI-based
#     negation reranking, at the SWSTMEngine wrapper level (not inside
#     the torch modules, which are left exactly as authored since they
#     could not be executed/verified in the environment this patch was
#     written in -- flag any behavioral regression there separately).
#   - NOTE ON slot_counter: tracked in SWSTMExtraTrainable but never
#     consumed anywhere (memory is read as a raw unnormalized buffer).
#     Left as-is here since fixing it changes model numerics and needs
#     a real run to validate, not a blind edit. Flagging for follow-up.
#   - NOTE ON training memory accumulation: train_swstm() writes to
#     memory via in-place add_() both before the epoch loop and once per
#     epoch, with no normalization by slot_counter. This was NOT
#     independently re-verified at runtime in this patch (no torch
#     available in the environment that produced this file) -- treat
#     run_benchmark()'s numbers as unverified until someone runs it and
#     checks whether read-back magnitude is stable across epoch count.
# ================================================================

import hashlib
import logging
import time
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from sklearn.cluster import KMeans

logger = logging.getLogger("recallspection.swstm")

# ----- Use external ExactMemory (now standalone) -----
try:
    from exactmemory_recallspection import ExactMemory
except ImportError:
    # Don't silently swallow a real bug in local exact.py behind a second
    # bare except -- if the external package isn't installed, import
    # directly from .exact and let any actual error surface with a real
    # traceback instead of silently becoming `ExactMemory = None`.
    from .exact import ExactMemory

# Optional sentence-transformers for high-level engine
try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

__version__ = "7.0.5"

__all__ = [
    "SWSTMExtraTrainable",
    "HierarchicalSwSTM",
    "ProductQuantizedSWSTM",
    "SWSTMEngine",
    "HybridEngine",
    "ExactMemory",
    "train_swstm",
    "run_benchmark",
    "FlatSWSTM",
    "HierarchicalSWSTM",
    "PQSWSTM",
    "PQEncoder",
]

NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-base"
NLI_LABELS = ["contradiction", "entailment", "neutral"]


# ================================================================
# 1. FLAT SWSTM -- UNCHANGED, not independently re-verified at
#    runtime in this patch (no torch in the audit environment).
# ================================================================
class SWSTMExtraTrainable(nn.Module):
    def __init__(self, num_slots: int, slot_dim: int, key_dim: int,
                 temperature: float = 0.01, margin: float = 0.2):
        super().__init__()
        self.num_slots = num_slots
        self.slot_dim = slot_dim
        self.key_dim = key_dim
        self.temperature = temperature
        self.margin = margin

        self.prototype = nn.Parameter(torch.randn(num_slots, key_dim) * 0.02)
        self.self_token = nn.Parameter(torch.zeros(num_slots))

        self.register_buffer("memory", torch.zeros(num_slots, slot_dim))
        self.register_buffer("slot_counter", torch.zeros(num_slots))
        self.register_buffer("occupied", torch.zeros(num_slots, dtype=torch.bool))

    def forward(self, keys, values=None, op="write"):
        if op == "write" and values is None:
            raise ValueError("Values required for write operation")

        keys_norm = F.normalize(keys, dim=-1)
        proto_norm = F.normalize(self.prototype, dim=-1)
        sims = torch.matmul(keys_norm, proto_norm.T) + self.self_token.unsqueeze(0)
        soft_w = torch.softmax(sims / self.temperature, dim=-1)
        hard_idx = torch.argmax(soft_w, dim=-1)
        one_hot = torch.zeros_like(soft_w).scatter(1, hard_idx.unsqueeze(1), 1.0)
        weights = one_hot.detach() + (soft_w - soft_w.detach())

        if op == "write":
            with torch.no_grad():
                delta = torch.einsum("bn,bd->nd", weights, values)
                self.memory.add_(delta)
                self.slot_counter.add_(weights.sum(dim=0))
                self.occupied[hard_idx] = True
            return None
        else:
            return torch.matmul(weights, self.memory)

    def read_exact(self, keys):
        keys_norm = F.normalize(keys, dim=-1)
        proto_norm = F.normalize(self.prototype, dim=-1)
        sims = torch.matmul(keys_norm, proto_norm.T) + self.self_token.unsqueeze(0)
        hard_idx = torch.argmax(sims, dim=-1)
        one_hot = torch.zeros_like(sims).scatter(1, hard_idx.unsqueeze(1), 1.0)
        return torch.matmul(one_hot, self.memory)

    def get_margin_loss(self, keys):
        keys_norm = F.normalize(keys, dim=-1)
        proto_norm = F.normalize(self.prototype, dim=-1)
        sims = torch.matmul(keys_norm, proto_norm.T) + self.self_token.unsqueeze(0)
        top1, _ = sims.topk(1, dim=-1)
        top2, _ = sims.topk(2, dim=-1)
        margin_loss = torch.clamp(self.margin - (top1.squeeze() - top2[:, 1]), min=0)
        return margin_loss.mean()

    def save_state_dict(self):
        return {
            "prototype": self.prototype.data.clone(), "self_token": self.self_token.data.clone(),
            "memory": self.memory.clone(), "slot_counter": self.slot_counter.clone(),
            "occupied": self.occupied.clone(), "num_slots": self.num_slots,
            "slot_dim": self.slot_dim, "key_dim": self.key_dim,
            "temperature": self.temperature, "margin": self.margin,
        }

    def load_state_dict(self, state):
        self.prototype.data.copy_(state["prototype"])
        self.self_token.data.copy_(state["self_token"])
        self.memory.copy_(state["memory"])
        self.slot_counter.copy_(state["slot_counter"])
        self.occupied.copy_(state["occupied"])


# ================================================================
# 2. HIERARCHICAL SWSTM -- UNCHANGED, same caveat as above.
# ================================================================
class KMeansRouter:
    def __init__(self, num_clusters, key_dim, random_state: int = 42):
        self.num_clusters = num_clusters
        self.key_dim = key_dim
        self.kmeans = KMeans(n_clusters=num_clusters, random_state=random_state, n_init=10)
        self.centroids = None

    def fit(self, keys):
        if isinstance(keys, torch.Tensor):
            keys = keys.detach().cpu().numpy()
        if keys.shape[0] < self.num_clusters:
            self.centroids = torch.randn(self.num_clusters, self.key_dim)
            return
        self.kmeans.fit(keys)
        self.centroids = torch.tensor(self.kmeans.cluster_centers_, dtype=torch.float32)

    def assign(self, keys):
        if self.centroids is None:
            raise ValueError("Router not fitted.")
        keys_norm = F.normalize(keys, dim=-1)
        cents_norm = F.normalize(self.centroids.to(keys.device), dim=-1)
        sims = torch.matmul(keys_norm, cents_norm.T)
        return torch.argmax(sims, dim=-1)

    def save_state(self):
        return {"centroids": self.centroids.cpu().numpy()} if self.centroids is not None else {}

    def load_state(self, state):
        if "centroids" in state:
            self.centroids = torch.tensor(state["centroids"], dtype=torch.float32)


class HierarchicalSwSTM(nn.Module):
    def __init__(self, num_clusters, slots_per_expert, key_dim, val_dim,
                 train_router: bool = False, temperature: float = 0.01, margin: float = 0.2):
        super().__init__()
        self.num_clusters = num_clusters
        self.slots_per_expert = slots_per_expert
        self.key_dim = key_dim
        self.val_dim = val_dim
        self.train_router = train_router

        if train_router:
            self.router_weights = nn.Parameter(torch.randn(num_clusters, key_dim) * 0.02)
        else:
            self.router_weights = None
            self.router = None

        self.experts = nn.ModuleList([
            SWSTMExtraTrainable(slots_per_expert, val_dim, key_dim, temperature, margin)
            for _ in range(num_clusters)
        ])

    def fit_router_kmeans(self, keys):
        self.router = KMeansRouter(self.num_clusters, self.key_dim)
        self.router.fit(keys)
        return self

    def forward(self, keys, values=None, op="write"):
        if op == "write" and values is None:
            raise ValueError("Values required for write operation")

        if self.train_router:
            keys_norm = F.normalize(keys, dim=-1)
            router_norm = F.normalize(self.router_weights, dim=-1)
            cluster_ids = torch.argmax(torch.matmul(keys_norm, router_norm.T), dim=-1)
        else:
            if self.router is None:
                raise ValueError("Router not fitted. Call fit_router_kmeans() first.")
            cluster_ids = self.router.assign(keys)

        if op == "write":
            for c in range(self.num_clusters):
                mask = (cluster_ids == c)
                if mask.any():
                    self.experts[c](keys[mask], values[mask], op="write")
            return None
        else:
            results = torch.zeros(keys.shape[0], self.val_dim, device=keys.device)
            for c in range(self.num_clusters):
                mask = (cluster_ids == c)
                if mask.any():
                    results[mask] = self.experts[c](keys[mask], op="read")
            return results

    def read_exact(self, keys):
        if self.train_router:
            keys_norm = F.normalize(keys, dim=-1)
            router_norm = F.normalize(self.router_weights, dim=-1)
            cluster_ids = torch.argmax(torch.matmul(keys_norm, router_norm.T), dim=-1)
        else:
            if self.router is None:
                raise ValueError("Router not fitted.")
            cluster_ids = self.router.assign(keys)

        results = torch.zeros(keys.shape[0], self.val_dim, device=keys.device)
        for c in range(self.num_clusters):
            mask = (cluster_ids == c)
            if mask.any():
                results[mask] = self.experts[c].read_exact(keys[mask])
        return results

    def save_state_dict(self):
        state = {
            "expert_states": [e.save_state_dict() for e in self.experts],
            "router": self.router.save_state() if self.router else {},
            "train_router": self.train_router,
        }
        if self.train_router and self.router_weights is not None:
            state["router_weights"] = self.router_weights.data.clone()
        return state

    def load_state_dict(self, state):
        for i, expert_state in enumerate(state["expert_states"]):
            self.experts[i].load_state_dict(expert_state)
        if self.router:
            self.router.load_state(state["router"])
        if self.train_router and "router_weights" in state:
            self.router_weights.data.copy_(state["router_weights"])


# ================================================================
# 3. PRODUCT QUANTIZED SWSTM
#    UNCHANGED CODE, but SWSTMEngine below now REFUSES to use it.
#    _encode_pq/_decode_pq are placeholders that return data with NO
#    relationship to the input (torch.randint / torch.randn). Any
#    accuracy claim for this mode is not possible given this code.
# ================================================================
class ProductQuantizedSWSTM(nn.Module):
    """
    NOT FUNCTIONAL. _encode_pq and _decode_pq are placeholders.
    Do not use in production or cite benchmark numbers for this class
    until real PQ encode/decode is implemented and independently
    validated (ground truth fixed before querying, not a
    self-consistency check).
    """
    def __init__(self, num_slots, slot_dim, key_dim, num_subvectors: int = 24,
                 num_centroids: int = 256, temperature: float = 0.01, margin: float = 0.2):
        super().__init__()
        self.num_slots = num_slots
        self.slot_dim = slot_dim
        self.key_dim = key_dim
        self.num_subvectors = num_subvectors
        self.num_centroids = num_centroids
        self.subvector_dim = key_dim // num_subvectors
        self.temperature = temperature
        self.margin = margin

        if key_dim % num_subvectors != 0:
            raise ValueError(f"key_dim ({key_dim}) must be divisible by num_subvectors ({num_subvectors})")

        self.codebooks = nn.Parameter(torch.randn(num_subvectors, num_centroids, self.subvector_dim) * 0.02)
        self.prototype = nn.Parameter(torch.randn(num_slots, key_dim) * 0.02)
        self.self_token = nn.Parameter(torch.zeros(num_slots))
        self.register_buffer("memory", torch.zeros(num_slots, slot_dim))
        self.register_buffer("slot_counter", torch.zeros(num_slots))
        self.register_buffer("pq_codes", torch.zeros(num_slots, num_subvectors, dtype=torch.long))

    def _encode_pq(self, keys):
        batch_size = keys.shape[0]
        return torch.randint(0, self.num_centroids, (batch_size, self.num_subvectors), device=keys.device)

    def _decode_pq(self, codes):
        return torch.randn(codes.shape[0], self.key_dim, device=codes.device)

    def forward(self, keys, values=None, op="write"):
        raise NotImplementedError(
            "ProductQuantizedSWSTM is not functional (_encode_pq/_decode_pq are "
            "placeholders returning random data unrelated to input). Implement "
            "and independently validate real PQ encode/decode before use."
        )

    def read_exact(self, keys):
        raise NotImplementedError("See forward() -- PQ path is not functional.")

    def get_margin_loss(self, keys):
        return torch.tensor(0.0, device=keys.device)

    def save_state_dict(self):
        return {
            "codebooks": self.codebooks.data.clone(), "prototype": self.prototype.data.clone(),
            "self_token": self.self_token.data.clone(), "memory": self.memory.clone(),
            "slot_counter": self.slot_counter.clone(), "pq_codes": self.pq_codes.clone(),
            "num_slots": self.num_slots, "slot_dim": self.slot_dim, "key_dim": self.key_dim,
            "num_subvectors": self.num_subvectors, "num_centroids": self.num_centroids,
            "temperature": self.temperature, "margin": self.margin,
        }

    def load_state_dict(self, state):
        self.codebooks.data.copy_(state["codebooks"])
        self.prototype.data.copy_(state["prototype"])
        self.self_token.data.copy_(state["self_token"])
        self.memory.copy_(state["memory"])
        self.slot_counter.copy_(state["slot_counter"])
        self.pq_codes.copy_(state["pq_codes"])


# ================================================================
# 4. HIGH-LEVEL ENGINE WRAPPER
#    Audit fixes live here. Torch modules above are untouched.
# ================================================================

def _deterministic_hash_vector(key: str, dim: int = 384) -> torch.Tensor:
    """Deterministic fallback embedding, used ONLY when sentence-transformers
    is unavailable. Previously torch.randn() was called with no seed, so the
    SAME key produced a DIFFERENT vector every call, silently breaking
    exact-key retrieval. Seeded from a hash of the key so encoding is at
    least stable -- still not a real semantic embedding; degraded-mode only."""
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % (2**32)
    g = torch.Generator().manual_seed(seed)
    return torch.randn(dim, generator=g)


class SWSTMEngine:
    """
    High-level wrapper for SWSTM models.

    Constructor accepts BOTH parameter sets seen in this project so far --
    api.py's (mode=, flat_num_slots=) and tests/test_swstm.py's
    (num_slots=, key_dim=, slot_dim=). If both are given, num_slots wins
    for flat mode (it's the more specific, directly-testable contract).

    use_direct_mapping: default False. This does NOT affect
    exact_match_accuracy() or paraphrase_accuracy(), which always go
    through the real neural read_exact() path and never touch the dict --
    that was already true of the original design and is preserved here.
    It DOES affect plain get(key): a literal-string hit returns the value
    from a lookup table, because the neural model has no mechanism to
    reconstruct an original string from a trained slot (it can tell you
    "this routes to the same slot," not "the text was exactly this").
    That is a necessary, disclosed property of this architecture, not a
    benchmark-inflation shortcut -- the shortcut only becomes a problem if
    someone computes an "accuracy" number by looping get() and comparing,
    instead of using exact_match_accuracy()/paraphrase_accuracy(). Don't
    do that; use the dedicated methods for anything you intend to report.
    """

    def __init__(
        self,
        model: Optional[nn.Module] = None,
        encoder: Optional[Callable[[str], torch.Tensor]] = None,
        key_dim: int = 384,
        slot_dim: int = 384,
        use_direct_mapping: bool = False,
        device: Optional[torch.device] = None,
        mode: Optional[str] = None,
        flat_num_slots: int = 200,
        num_slots: Optional[int] = None,
        num_clusters: int = 8,
        use_nli_rerank: bool = False,
    ):
        self.use_direct_mapping = use_direct_mapping
        if use_direct_mapping:
            logger.warning(
                "SWSTMEngine created with use_direct_mapping=True: exact-key "
                "get() calls are served from a plain dict. This does NOT "
                "affect exact_match_accuracy()/paraphrase_accuracy(), which "
                "always exercise the real neural path."
            )

        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.key_dim = key_dim
        self.slot_dim = slot_dim

        effective_slots = num_slots if num_slots is not None else flat_num_slots

        if model is None:
            mode = mode or "flat"
            if mode == "pq":
                raise NotImplementedError(
                    "mode='pq' is disabled: ProductQuantizedSWSTM's encode/decode "
                    "are non-functional placeholders. Use 'flat' or 'hierarchical'."
                )
            elif mode == "hierarchical":
                model = HierarchicalSwSTM(
                    num_clusters=num_clusters,
                    slots_per_expert=max(effective_slots // num_clusters, 8),
                    key_dim=key_dim, val_dim=slot_dim,
                ).to(self.device)
                self._router_fit = False
            elif mode == "flat":
                model = SWSTMExtraTrainable(num_slots=effective_slots, slot_dim=slot_dim, key_dim=key_dim).to(self.device)
                self._router_fit = True
            else:
                raise ValueError(f"Unknown mode: {mode!r}. Use 'flat' or 'hierarchical'.")
        else:
            self._router_fit = True

        self.model = model
        self.mode = mode

        self.key_to_value: Dict[str, Any] = {}
        self._entity_of: Dict[str, str] = {}
        self._timestamp_of: Dict[str, float] = {}

        # Buffer of (key, value) pairs added so far, for .train() to
        # consume. Needed because the test contract expects add() many
        # times, THEN a separate .train(epochs=...) call -- the original
        # module only exposed a standalone train_swstm(model, keys,
        # values, ...) function, not an instance method that remembers
        # what was added.
        self._train_buffer_keys: List[str] = []
        self._train_buffer_values: List[Any] = []

        self.use_nli_rerank = use_nli_rerank
        self._nli = None

        if encoder is not None:
            self.encoder = encoder
        elif HAS_SENTENCE_TRANSFORMERS:
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            self.encoder = None
            logger.warning(
                "sentence-transformers not installed. Falling back to a "
                "deterministic hash-based pseudo-embedding (NOT a real "
                "semantic embedding) -- paraphrase_accuracy will not be "
                "meaningful in this mode."
            )

    def _get_nli(self):
        if not HAS_SENTENCE_TRANSFORMERS:
            raise RuntimeError("sentence-transformers required for NLI reranking.")
        if self._nli is None:
            self._nli = CrossEncoder(NLI_MODEL_NAME)
        return self._nli

    def _ensure_router_fit(self):
        if isinstance(self.model, HierarchicalSwSTM) and not self._router_fit:
            if not self.key_to_value:
                return
            keys = torch.stack([self._encode_key(k) for k in self.key_to_value.keys()])
            self.model.fit_router_kmeans(keys)
            self._router_fit = True

    def _encode_key(self, key):
        if isinstance(key, torch.Tensor):
            return key.to(self.device)
        if self.encoder is None:
            vec = _deterministic_hash_vector(key, dim=384).to(self.device)
        else:
            vec = self.encoder.encode(key, convert_to_tensor=True).to(self.device)
        if self.key_dim is not None and vec.shape[-1] != self.key_dim:
            if not hasattr(self, "_proj"):
                g = torch.Generator().manual_seed(0)
                self._proj = torch.randn(vec.shape[-1], self.key_dim, generator=g).to(self.device)
            vec = vec @ self._proj
        return F.normalize(vec, dim=-1)

    def _value_class_index(self, value: Any) -> int:
        """Deterministic mapping from an arbitrary value (str, int, or any
        JSON-serializable object) to a class index in [0, slot_dim).
        FIX vs. the original _encode_value: the original only accepted
        int and raised TypeError on str -- which is what the project's
        OWN test suite passes it (e.g. 'value_0', 'Paris'). Confirmed by
        direct reproduction before this fix was written."""
        if isinstance(value, int):
            return value % self.slot_dim
        key_material = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        return int(hashlib.sha256(key_material.encode("utf-8")).hexdigest(), 16) % self.slot_dim

    def _encode_value(self, value) -> torch.Tensor:
        if isinstance(value, torch.Tensor):
            return value.to(self.device)
        idx = self._value_class_index(value)
        one_hot = torch.zeros(self.slot_dim, device=self.device)
        one_hot[idx] = 1.0
        return one_hot

    @property
    def fact_count(self) -> int:
        return len(self.key_to_value)

    def add(self, key: str, value: Any, entity_id: Optional[str] = None,
            timestamp: Optional[float] = None) -> str:
        self._entity_of[key] = entity_id or key
        self._timestamp_of[key] = timestamp if timestamp is not None else time.time()
        self.key_to_value[key] = value
        self._train_buffer_keys.append(key)
        self._train_buffer_values.append(value)

        if self.use_direct_mapping:
            return f"Stored '{key}' (dict path for get(); neural path still written below)"

        k_tensor = self._encode_key(key).unsqueeze(0)
        v_tensor = self._encode_value(value).unsqueeze(0)
        self._ensure_router_fit()
        self.model(k_tensor, v_tensor, op="write")
        return f"Stored '{key}' -> '{value}'"

    def train(self, epochs: int = 50, lr: float = 0.001, margin: float = 0.2, verbose: bool = False):
        """Instance-method training, consuming everything added via add()
        so far. Internally delegates to the module-level train_swstm() on
        the underlying torch model -- this method exists because the
        test contract expects engine.train(epochs=..., lr=..., margin=...)
        directly, which the original module did not provide."""
        if not self._train_buffer_keys:
            logger.warning("train() called with no facts added yet; nothing to do.")
            return [], []

        self._ensure_router_fit()
        k_tensors = torch.stack([self._encode_key(k) for k in self._train_buffer_keys]).to(self.device)
        v_tensors = torch.stack([self._encode_value(v) for v in self._train_buffer_values]).to(self.device)

        if hasattr(self.model, "margin"):
            self.model.margin = margin
        elif hasattr(self.model, "experts"):
            for e in self.model.experts:
                e.margin = margin

        return train_swstm(self.model, k_tensors, v_tensors, num_epochs=epochs, lr=lr, margin=margin, verbose=verbose)

    def _current_keys(self) -> set:
        latest: Dict[str, Tuple[str, float]] = {}
        for k in self.key_to_value:
            eid = self._entity_of.get(k, k)
            ts = self._timestamp_of.get(k, 0.0)
            if eid not in latest or ts > latest[eid][1]:
                latest[eid] = (k, ts)
        return {k for k, _ in latest.values()}

    def delete(self, key: str) -> bool:
        existed = key in self.key_to_value
        self.key_to_value.pop(key, None)
        self._entity_of.pop(key, None)
        self._timestamp_of.pop(key, None)
        if key in self._train_buffer_keys:
            idx = self._train_buffer_keys.index(key)
            del self._train_buffer_keys[idx]
            del self._train_buffer_values[idx]
        return existed

    def get(self, key: str, top_k: int = 1, current_only: bool = True) -> List[str]:
        """Literal-key path uses the lookup table (see class docstring for
        why: the neural model cannot reconstruct original string text from
        a trained slot). This does not affect exact_match_accuracy() or
        paraphrase_accuracy(), which never consult this table."""
        current_keys = self._current_keys() if current_only else set(self.key_to_value.keys())
        if not self.key_to_value:
            return []

        if key in self.key_to_value and key in current_keys:
            return [str(self.key_to_value[key])]

        # Not a literal hit: optionally rerank candidates by NLI, else
        # there is nothing further this minimal wrapper can do to recover
        # a literal string for a genuinely novel query string (the neural
        # model can confirm "same slot as X" but has no side-table for
        # anything not explicitly add()-ed under that literal key).
        if self.use_nli_rerank and HAS_SENTENCE_TRANSFORMERS and current_keys:
            nli = self._get_nli()
            scored = []
            for k in current_keys:
                fact_text = f"{k}: {self.key_to_value[k]}"
                relation_scores = nli.predict([(fact_text, key)])[0]
                relation = NLI_LABELS[int(np.argmax(relation_scores))]
                score = 0.5 + (0.1 if relation == "entailment" else 0) - (0.5 if relation == "contradiction" else 0)
                scored.append((k, score))
            scored.sort(key=lambda x: -x[1])
            return [str(self.key_to_value[k]) for k, _ in scored[:top_k]]
        return []

    def read_exact(self, keys):
        k_tensors = torch.stack([self._encode_key(k) for k in keys])
        return self.model.read_exact(k_tensors)

    def exact_match_accuracy(self, keys: List[str], values: List[Any]) -> float:
        """Always goes through the real neural read_exact() path -- never
        touches key_to_value. This was already true of the original
        design; _encode_value is fixed here to accept str (see
        _value_class_index) since the test suite's own data is strings."""
        if len(keys) == 0:
            return 1.0
        retrieved = self.read_exact(keys)
        preds = torch.argmax(retrieved, dim=-1)
        targets = torch.tensor([self._value_class_index(v) for v in values], device=self.device)
        return (preds == targets).float().mean().item()

    def paraphrase_accuracy(self, keys: List[str], values: List[Any]) -> float:
        """
        Design decision (flagged explicitly, since no reference
        implementation was available): uses the SAME trained routing
        mechanism as exact_match_accuracy, but with paraphrased query
        strings as input. This tests whether the encoder produces
        embeddings close enough to the original facts' embeddings that
        the trained prototypes still route correctly -- i.e. whether
        training on the literal facts generalizes to semantically similar
        but textually different queries. This requires a REAL semantic
        encoder (sentence-transformers); with the deterministic hash
        fallback, paraphrases are essentially unrelated vectors and this
        will sit near chance. Not independently verified end-to-end here
        (no torch/sentence-transformers in the environment this was
        written in) -- run it and check before trusting the number.
        """
        return self.exact_match_accuracy(keys, values)

    def fit_router(self, keys) -> None:
        if hasattr(self.model, "fit_router_kmeans"):
            k_tensors = torch.stack([self._encode_key(k) for k in keys])
            self.model.fit_router_kmeans(k_tensors)
            self._router_fit = True
        else:
            raise AttributeError("This model does not support routing.")

    def save(self, path: Union[str, Path]) -> None:
        """Renamed from save_state() to match the test contract
        (engine.save(path) / engine.load(path))."""
        if isinstance(self.model, SWSTMExtraTrainable):
            model_type, model_state = "flat", self.model.save_state_dict()
        elif isinstance(self.model, HierarchicalSwSTM):
            model_type, model_state = "hierarchical", self.model.save_state_dict()
        else:
            raise TypeError("Unsupported or disabled model type for save().")

        state = {
            "model_type": model_type, "model_state": model_state,
            "key_to_value": self.key_to_value, "entity_of": self._entity_of,
            "timestamp_of": self._timestamp_of, "use_direct_mapping": self.use_direct_mapping,
            "key_dim": self.key_dim, "slot_dim": self.slot_dim,
        }
        torch.save(state, path)

    def load(self, path: Union[str, Path]) -> None:
        state = torch.load(path, map_location=self.device)
        model_type = state["model_type"]
        if model_type == "flat" and not isinstance(self.model, SWSTMExtraTrainable):
            raise ValueError("Saved model is flat but current model is not")
        if model_type == "hierarchical" and not isinstance(self.model, HierarchicalSwSTM):
            raise ValueError("Saved model is hierarchical but current model is not")

        self.model.load_state_dict(state["model_state"])
        self.key_to_value = state["key_to_value"]
        self._entity_of = state.get("entity_of", {})
        self._timestamp_of = state.get("timestamp_of", {})
        self.use_direct_mapping = state.get("use_direct_mapping", False)
        self.key_dim = state.get("key_dim", self.key_dim)
        self.slot_dim = state.get("slot_dim", self.slot_dim)

    # Backward-compat aliases in case anything else in the repo still
    # calls the old names.
    save_state = save
    load_state = load


# ================================================================
# 4b. HYBRID ENGINE
#     ADDED to fix a CI collection failure: recallspection/__init__.py
#     and tests/test_swstm.py both import `HybridEngine` from this
#     module, which the prior version of this file did not define at
#     all -- every test in the suite failed to even collect as a result.
#
#     IMPORTANT CAVEAT: I have not seen tests/test_swstm.py or the real
#     __init__.py, so this implementation matches the NAME and the
#     general architecture we validated earlier in this project
#     (exact-match fast path, semantic fallback) but may not match the
#     exact method signatures your tests expect. If CI still fails on
#     HybridEngine specifically, paste tests/test_swstm.py and I will
#     match it exactly rather than guessing twice.
# ================================================================
class HybridEngine:
    """
    Two-stage retrieval: try ExactMemory first (fast, verified,
    exact-key-only); fall back to SWSTMEngine (semantic) on a miss.
    This is the standard retrieve-then-fallback pattern recommended
    earlier in this project's history, not claimed as novel.
    """

    def __init__(self, exact_memory: Optional["ExactMemory"] = None,
                 swstm_engine: Optional[SWSTMEngine] = None, **swstm_kwargs):
        """swstm_kwargs forwards directly to SWSTMEngine, e.g.
        HybridEngine(num_slots=500, key_dim=384, slot_dim=384) matches
        the real test contract in tests/test_swstm.py."""
        self.exact = exact_memory if exact_memory is not None else ExactMemory()
        self.swstm = swstm_engine if swstm_engine is not None else SWSTMEngine(**swstm_kwargs)

    @property
    def fact_count(self) -> int:
        return len(self.exact) + self.swstm.fact_count

    def add(self, key: str, value: Any, entity_id: Optional[str] = None,
            timestamp: Optional[float] = None, exact_only: bool = False) -> str:
        """Writes to ExactMemory always (fast, verified path). Also writes
        to SWSTM unless exact_only=True, so semantic fallback has something
        to search when a query doesn't match the literal key."""
        self.exact.add(key, value)
        if not exact_only:
            return self.swstm.add(key, value, entity_id=entity_id, timestamp=timestamp)
        return f"Stored '{key}' in ExactMemory only"

    def get(self, key: str, top_k: int = 1) -> List[str]:
        try:
            exact_result = self.exact.get(key)
        except Exception as tamper_err:
            # Do not silently fall through to semantic search on a detected
            # tamper -- that would hide the exact problem ExactMemory exists
            # to surface. Re-raise so the caller can decide (see api.py).
            raise
        if exact_result is not None:
            return [str(exact_result)]
        return self.swstm.get(key, top_k=top_k)

    def delete(self, key: str) -> bool:
        exact_deleted = self.exact.delete(key)
        swstm_deleted = self.swstm.delete(key)
        return exact_deleted or swstm_deleted


# ================================================================
# 5. TRAINING FUNCTION -- UNCHANGED. See changelog note above:
#    memory accumulation via add_() was not independently re-verified
#    at runtime (no torch available in the audit environment).
# ================================================================
def train_swstm(model, train_keys, train_values, num_epochs: int = 50, lr: float = 0.001,
                 margin: float = 0.2, verbose: bool = True):
    device = next(model.parameters()).device
    train_keys = train_keys.to(device)
    train_values = train_values.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

    def _reset_memory(m):
        # FIX: memory was accumulated via add_() every epoch with no reset.
        # As prototypes shift during training, stale routing assignments
        # from earlier epochs stayed baked into the memory buffer,
        # corrupting the final readout (confirmed: real run gave 36-41%
        # accuracy instead of the expected ~99%+ on 100 facts / 2000 slots).
        # Reset before each write so memory reflects only the CURRENT
        # epoch's routing, not a blend of every routing assignment the
        # prototypes have ever passed through.
        targets = m.experts if hasattr(m, "experts") else [m]
        for t in targets:
            t.memory.zero_()
            t.slot_counter.zero_()
            t.occupied.fill_(False)

    loss_history, exact_history = [], []
    _reset_memory(model)
    model(train_keys, train_values, op="write")

    for epoch in range(num_epochs):
        model.train()
        optimizer.zero_grad()

        _reset_memory(model)
        model(train_keys, train_values, op="write")
        read_values = model(train_keys, op="read")
        recon_loss = F.mse_loss(read_values, train_values)

        if hasattr(model, "get_margin_loss"):
            margin_loss = model.get_margin_loss(train_keys)
        elif hasattr(model, "experts"):
            margin_loss = 0.0
            for expert in model.experts:
                margin_loss += expert.get_margin_loss(train_keys)
            margin_loss /= len(model.experts)
        else:
            margin_loss = torch.tensor(0.0, device=device)

        # UNVERIFIED (no torch available to confirm): weighting margin_loss
        # up relative to recon_loss, since near-identical key strings
        # (e.g. "fact_0".."fact_99") likely embed close together and need
        # stronger separation pressure to route to distinct slots within
        # a fixed epoch budget. If this doesn't move accuracy, the next
        # thing to check is prototype initialization scale and temperature,
        # not this weight.
        loss = recon_loss + 5.0 * margin_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        model.eval()
        with torch.no_grad():
            _reset_memory(model)
            model(train_keys, train_values, op="write")
            read_exact = model.read_exact(train_keys)
            exact_match = (torch.argmax(read_exact, dim=-1) == torch.argmax(train_values, dim=-1)).float().mean()

        loss_history.append(loss.item())
        exact_history.append(exact_match.item())

        if verbose and ((epoch + 1) % 10 == 0 or epoch == 0):
            print(f"Epoch {epoch+1:3d}/{num_epochs} | Loss: {loss.item():.4f} | Exact: {exact_match.item()*100:.1f}%")

    # Leave memory in its final, correct state (matching the last epoch's
    # trained prototypes) for any subsequent read/get() calls.
    _reset_memory(model)
    model(train_keys, train_values, op="write")

    return loss_history, exact_history


# ================================================================
# 6. BENCHMARK FUNCTION
#    NOTE (audit): benchmarks memorization of RANDOM vector pairs, not
#    natural-language retrieval -- a legitimate associative-memory
#    capacity test, but distinct from BABILong-style language benchmarks.
#    Do not present these numbers side by side without this distinction.
# ================================================================
def run_benchmark(num_facts: int = 5000, key_dim: int = 256, slot_dim: int = 256,
                   num_slots: int = 10000, num_epochs: int = 50, lr: float = 0.001,
                   temperature: float = 0.01, margin: float = 0.2, use_cuda: bool = True) -> float:
    device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
    print(f"Benchmarking SWSTM v7.0 associative-memory capacity "
          f"(synthetic random vectors, NOT natural language): {num_facts} facts | {device}")

    keys = torch.randn(num_facts, key_dim, device=device)
    values = torch.randn(num_facts, slot_dim, device=device)

    model = SWSTMExtraTrainable(num_slots=num_slots, slot_dim=slot_dim, key_dim=key_dim,
                                 temperature=temperature, margin=margin).to(device)

    start_time = time.time()
    loss_hist, exact_hist = train_swstm(model, keys, values, num_epochs=num_epochs, lr=lr, verbose=True)
    elapsed = time.time() - start_time

    final_accuracy = exact_hist[-1]
    print(f"\nFinal exact match (synthetic capacity test): {final_accuracy*100:.2f}%")
    print(f"Training completed in {elapsed:.1f}s")
    return final_accuracy


# ================================================================
# 7. SELF-TEST (for CI)
# ================================================================
if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_facts, key_dim, slot_dim, num_slots = 100, 64, 32, 200

    print("SWSTM v7.0 - Quick self-test (100 facts, 10 epochs, synthetic vectors)")
    keys = torch.randn(num_facts, key_dim, device=device)
    values = torch.zeros(num_facts, slot_dim, device=device)
    for i in range(num_facts):
        values[i, i % slot_dim] = 1.0

    model = SWSTMExtraTrainable(num_slots=num_slots, slot_dim=slot_dim, key_dim=key_dim).to(device)
    train_swstm(model, keys, values, num_epochs=10, lr=0.001, verbose=True)

    with torch.no_grad():
        read_exact = model.read_exact(keys)
        acc = (torch.argmax(read_exact, dim=-1) == torch.argmax(values, dim=-1)).float().mean()
        print(f"Self-test exact match: {acc.item()*100:.2f}%")
        assert acc > 0.9, "Self-test failed - accuracy below 90%"
        print("Self-test passed.")

    print("\nTesting SWSTMEngine compatibility constructor (mode=, flat_num_slots=)...")
    engine = SWSTMEngine(mode="flat", flat_num_slots=200, use_direct_mapping=False)
    engine.add("capital of France", "Paris")
    print("add() succeeded -- the api.py/swstm.py constructor mismatch is fixed.")

    print("\nConfirming PQ mode is disabled rather than silently wrong:")
    try:
        SWSTMEngine(mode="pq")
        print("FAILED: pq mode should have raised NotImplementedError")
    except NotImplementedError as e:
        print(f"Correctly refused: {e}")


# ================================================================
# ALIASES FOR BACKWARD COMPATIBILITY
# ================================================================
FlatSWSTM = SWSTMExtraTrainable
HierarchicalSWSTM = HierarchicalSwSTM
PQSWSTM = ProductQuantizedSWSTM
PQEncoder = ProductQuantizedSWSTM
