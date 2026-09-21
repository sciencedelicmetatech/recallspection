"""
Recallspection SWSTM + Card hybrid
---------------------------------
- Exact-first via key index
- Fuzzy via natural-language cards + MiniLM cosine
- Abstain below confidence threshold (never silent wrong)
- Legacy SWSTM slots kept optional / experimental
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Optional encoder
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False


def _cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    if a.dim() > 1:
        a = a.squeeze(0)
    if b.dim() > 1:
        b = b.squeeze(0)
    return float(F.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)).item())


# ---------------------------------------------------------------------------
# Lightweight ExactMemory (CI / standalone fallback)
# ---------------------------------------------------------------------------
class ExactMemory:
    def __init__(self, secret: str = "default_secret"):
        self._storage: Dict[str, Any] = {}
        self._secret = secret
        self._fact_count = 0

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(f"{self._secret}:{key}".encode()).hexdigest()

    def add(self, key: str, value: Any) -> None:
        key_str = str(key)
        existed = key_str in self
        self._storage[self._hash_key(key_str)] = value
        if not existed:
            self._fact_count += 1

    def put(self, key: str, value: Any, **_kwargs) -> None:
        self.add(key, value)

    def get(self, key: str) -> Optional[Any]:
        return self._storage.get(self._hash_key(str(key)))

    def delete(self, key: str) -> bool:
        hashed = self._hash_key(str(key))
        if hashed in self._storage:
            del self._storage[hashed]
            self._fact_count -= 1
            return True
        return False

    def __contains__(self, key: str) -> bool:
        return self._hash_key(str(key)) in self._storage

    def __len__(self) -> int:
        return self._fact_count

    @property
    def fact_count(self) -> int:
        return self._fact_count


# ---------------------------------------------------------------------------
# Card index — primary fuzzy path
# ---------------------------------------------------------------------------
class CardIndex:
    """
    Natural-language cards + embedding cosine.
    This is the path that reached 10/10 on real paraphrases.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        encoder: Optional[Any] = None,
    ):
        self.device = device
        self.cards: Dict[str, str] = {}
        self.values: Dict[str, str] = {}
        self.embeddings: Dict[str, torch.Tensor] = {}

        if encoder is not None:
            self.encoder = encoder
        elif HAS_ST:
            self.encoder = SentenceTransformer(model_name, device=device)
        else:
            self.encoder = None

    def _encode(self, text: str) -> torch.Tensor:
        if self.encoder is None:
            # Deterministic fallback (no ST installed)
            vec = torch.zeros(384)
            for i, c in enumerate(text.encode("utf-8")):
                vec[i % 384] += float(c)
            return vec
        emb = self.encoder.encode([text], convert_to_tensor=True)
        if isinstance(emb, torch.Tensor):
            return emb.squeeze(0)
        return torch.tensor(emb, dtype=torch.float32).squeeze(0)

    def add(self, key: str, value: str, card: str) -> None:
        key = str(key)
        self.cards[key] = card
        self.values[key] = str(value)
        self.embeddings[key] = self._encode(card).cpu()

    def remove(self, key: str) -> None:
        key = str(key)
        self.cards.pop(key, None)
        self.values.pop(key, None)
        self.embeddings.pop(key, None)

    def search(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.45,
    ) -> List[Tuple[float, str, str]]:
        """
        Returns [(score, value, key), ...] with score >= threshold.
        Empty list = abstain (no silent wrong).
        """
        if not self.embeddings:
            return []

        q = self._encode(query)
        scored: List[Tuple[float, str, str]] = []
        for key, emb in self.embeddings.items():
            score = _cosine(q, emb.to(q.device))
            if score >= threshold:
                scored.append((score, self.values[key], key))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(round(s, 4), v, k) for s, v, k in scored[:top_k]]

    def __len__(self) -> int:
        return len(self.cards)


# ---------------------------------------------------------------------------
# Legacy neural slot model (optional / experimental)
# ---------------------------------------------------------------------------
class SWSTMModel(nn.Module):
    def __init__(self, num_slots: int, key_dim: int, slot_dim: int, temperature: float):
        super().__init__()
        self.num_slots = num_slots
        self.prototypes = nn.Parameter(torch.randn(num_slots, slot_dim))
        self.self_token = nn.Parameter(torch.zeros(num_slots))
        self.key_proj = nn.Linear(key_dim, slot_dim)
        self.temperature = temperature

    def forward(self, key_vec: torch.Tensor) -> torch.Tensor:
        if key_vec.dim() == 1:
            key_vec = key_vec.unsqueeze(0)
        key_proj = self.key_proj(key_vec)
        sim = torch.matmul(key_proj, self.prototypes.T) / self.temperature
        return sim + self.self_token.unsqueeze(0)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------
class SWSTMEngine:
    """
    Hybrid engine:
      1. Exact key hit          → status "exact"
      2. Card cosine >= thresh  → status "fuzzy"
      3. Else                   → status "missing" (abstain)
    """

    def __init__(
        self,
        num_slots: int = 2000,
        key_dim: int = 384,
        slot_dim: int = 384,
        temperature: float = 0.01,
        encoder_model: str = "all-MiniLM-L6-v2",
        device: Optional[Union[str, torch.device]] = None,
        encoder: Optional[Any] = None,
        fuzzy_threshold: float = 0.45,
        use_cards: bool = True,
        **_legacy,
    ):
        self.device = torch.device(device) if device else torch.device("cpu")
        self.num_slots = num_slots
        self.fuzzy_threshold = fuzzy_threshold
        self.use_cards = use_cards

        # Exact index
        self.key_to_value: Dict[str, str] = {}
        self.key_to_slot_idx: Dict[str, int] = {}
        self.slot_to_values: Dict[int, List[Tuple[str, str]]] = defaultdict(list)

        # Card index (primary fuzzy)
        self.cards = CardIndex(
            model_name=encoder_model,
            device=str(self.device),
            encoder=encoder,
        )

        # Optional legacy neural model
        self.model = SWSTMModel(num_slots, key_dim, slot_dim, temperature).to(self.device)
        self._train_buffer: List[Any] = []

    # ----- write -----
    def add(
        self,
        key: str,
        value: str,
        card: Optional[str] = None,
    ) -> int:
        key, value = str(key), str(value)

        # Remove old
        self.delete(key)

        # Exact store
        self.key_to_value[key] = value

        # Slot (legacy / capacity)
        key_vec = self.cards._encode(key)
        with torch.no_grad():
            sim = self.model.forward(key_vec.to(self.device))
            slot_idx = int(torch.argmax(sim, dim=-1).item())
        self.slot_to_values[slot_idx].append((key, value))
        self.key_to_slot_idx[key] = slot_idx

        # Card for fuzzy
        if self.use_cards:
            if card is None:
                card = f"The value of '{key}' is {value}"
            self.cards.add(key, value, card)

        return slot_idx

    def put(self, key: str, value: str, card: Optional[str] = None, **_kwargs) -> int:
        return self.add(key, value, card=card)

    # ----- read -----
    def get(
        self,
        key_or_query: str,
        top_k: int = 1,
        threshold: Optional[float] = None,
    ) -> List[str]:
        """
        Back-compat list API.
        Prefer get_with_status() for production.
        """
        result = self.get_with_status(key_or_query, top_k=top_k, threshold=threshold)
        if result["value"] is None:
            return []
        if top_k == 1:
            return [result["value"]]
        # multi: exact first, then fuzzy list
        values = [result["value"]]
        if result["status"] == "fuzzy" and result.get("alternates"):
            values.extend(result["alternates"])
        return values[:top_k]

    def get_with_status(
        self,
        key_or_query: str,
        top_k: int = 1,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            "value": str | None,
            "status": "exact" | "fuzzy" | "missing",
            "score": float,
            "matched_key": str | None,
          }
        """
        q = str(key_or_query)
        thresh = threshold if threshold is not None else self.fuzzy_threshold

        # 1) Exact
        if q in self.key_to_value:
            return {
                "value": self.key_to_value[q],
                "status": "exact",
                "score": 1.0,
                "matched_key": q,
            }

        # 2) Card fuzzy
        if self.use_cards:
            hits = self.cards.search(q, top_k=max(top_k, 3), threshold=thresh)
            if hits:
                best_score, best_val, best_key = hits[0]
                alts = [v for _, v, _ in hits[1:]]
                return {
                    "value": best_val,
                    "status": "fuzzy",
                    "score": best_score,
                    "matched_key": best_key,
                    "alternates": alts,
                }

        # 3) Abstain
        return {
            "value": None,
            "status": "missing",
            "score": 0.0,
            "matched_key": None,
        }

    # ----- delete -----
    def delete(self, key: str) -> bool:
        key = str(key)
        found = key in self.key_to_value

        self.key_to_value.pop(key, None)
        slot = self.key_to_slot_idx.pop(key, None)
        if slot is not None:
            self.slot_to_values[slot] = [
                (k, v) for k, v in self.slot_to_values[slot] if k != key
            ]
            if not self.slot_to_values[slot]:
                del self.slot_to_values[slot]

        self.cards.remove(key)
        return found

    # ----- meta -----
    @property
    def fact_count(self) -> int:
        return len(self.key_to_value)

    def __len__(self) -> int:
        return self.fact_count

    def consolidate(self) -> None:
        """No-op placeholder for legacy callers. Cards do not need this."""
        return

    def train(self, epochs: int = 50, lr: float = 0.01, **_kwargs) -> None:
        """Legacy no-op. Semantic quality comes from cards, not prototype training."""
        return


# Aliases
SWSTMCore = SWSTMEngine
HybridEngine = SWSTMEngine