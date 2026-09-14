import torch
import torch.nn as nn
from typing import List, Dict, Tuple, Optional, Any, Union
from collections import defaultdict
import hashlib

# --- ExactMemory Wrapper for CI compatibility ---
class ExactMemory:
    def __init__(self, secret: str = "default_secret"):
        self._storage = {}
        self._secret = secret
        self._fact_count = 0

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(f"{self._secret}:{key}".encode()).hexdigest()

    def _pack(self, value: Any) -> str:
        return str(value)

    def add(self, key: str, value: Any) -> None:
        key_str = str(key)
        existed = key_str in self
        self._storage[self._hash_key(key_str)] = self._pack(value)
        if not existed:
            self._fact_count += 1

    def get(self, key: str) -> Optional[str]:
        return self._storage.get(self._hash_key(str(key)))

    def __contains__(self, key: str) -> bool:
        return self._hash_key(str(key)) in self._storage

    def __len__(self) -> int:
        return self._fact_count

    @property
    def fact_count(self) -> int:
        return self._fact_count


# --- SWSTM Neural Model ---
class SWSTMModel(nn.Module):
    def __init__(self, num_slots: int, key_dim: int, slot_dim: int, temperature: float):
        super().__init__()
        self.num_slots = num_slots
        self.key_dim = key_dim
        self.slot_dim = slot_dim
        self.temperature = temperature
        
        self.prototypes = nn.Parameter(torch.randn(num_slots, slot_dim))
        self.self_token = nn.Parameter(torch.zeros(num_slots))
        
        self.key_proj = nn.Linear(key_dim, slot_dim)
        self.val_proj = nn.Linear(key_dim, slot_dim)

    def forward(self, key_vec: torch.Tensor, val_vec: Optional[torch.Tensor] = None, op: str = "read"):
        if key_vec.dim() == 1:
            key_vec = key_vec.unsqueeze(0)
            
        key_proj = self.key_proj(key_vec)
        sim = torch.matmul(key_proj, self.prototypes.T) / self.temperature
        sim = sim + self.self_token.unsqueeze(0)
        
        return sim


# --- Legendary SWSTM Engine ---
class SWSTMEngine:
    def __init__(
        self,
        num_slots: int = 2000,
        key_dim: int = 384,
        slot_dim: int = 384,
        temperature: float = 0.01,
        encoder_model: str = "all-MiniLM-L6-v2",
        device: Optional[Union[str, torch.device]] = None,
        encoder: Optional[Any] = None,
        mode: Optional[str] = None,
        flat_num_slots: Optional[int] = None,
        hierarchical_num_slots: Optional[int] = None,
        **legacy_kwargs: Any,
    ):
        if flat_num_slots is not None:
            num_slots = flat_num_slots
        elif hierarchical_num_slots is not None:
            num_slots = hierarchical_num_slots
            
        self.num_slots = num_slots
        self.key_dim = key_dim
        self.slot_dim = slot_dim
        self.temperature = temperature
        self.encoder_model = encoder_model
        self.device = torch.device(device) if device else torch.device("cpu")
        self.mode = mode or "flat"
        
        self.slot_to_values: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        self.value_to_slot: Dict[str, int] = {}
        self._train_buffer: List[Tuple[torch.Tensor, torch.Tensor, str, str]] = []
        
        if encoder is not None:
            self.encoder = encoder
        else:
            try:
                from sentence_transformers import SentenceTransformer
                self.encoder = SentenceTransformer(encoder_model)
            except ImportError:
                self.encoder = None
                
        self.model = SWSTMModel(num_slots, key_dim, slot_dim, temperature).to(self.device)

    @property
    def fact_count(self) -> int:
        return sum(len(bucket) for bucket in self.slot_to_values.values())

    def __len__(self) -> int:
        return self.fact_count

    def _encode(self, text: str) -> torch.Tensor:
        if self.encoder is None:
            vec = torch.zeros(self.key_dim)
            for i, c in enumerate(text.encode('utf-8')):
                vec[i % self.key_dim] += c
            return vec.to(self.device)
        
        try:
            vec = self.encoder.encode([text], convert_to_tensor=True)
        except TypeError:
            vec = self.encoder.encode([text])
            
        if isinstance(vec, torch.Tensor):
            return vec.squeeze(0).to(self.device)
        else:
            return torch.tensor(vec, dtype=torch.float32).squeeze(0).to(self.device)

    def add(self, key: str, value: str) -> int:
        key_str = str(key)
        value_str = str(value)

        # remove old key from buffer
        self._train_buffer = [
            (kv, vv, k, v)
            for kv, vv, k, v in self._train_buffer
            if k != key_str
        ]

        # remove old key from buckets
        for slot_idx in list(self.slot_to_values.keys()):
            self.slot_to_values[slot_idx] = [
                (k, v)
                for k, v in self.slot_to_values[slot_idx]
                if k != key_str
            ]
            if not self.slot_to_values[slot_idx]:
                del self.slot_to_values[slot_idx]

        key_vec = self._encode(key_str)
        val_vec = self._encode(value_str)

        with torch.no_grad():
            sim = self.model.forward(key_vec, val_vec, op="write")
            slot_idx = int(torch.argmax(sim, dim=-1).item())

        self.slot_to_values[slot_idx].append((key_str, value_str))
        self.value_to_slot[value_str] = slot_idx

        self._train_buffer.append(
            (
                key_vec.squeeze(0).cpu(),
                val_vec.squeeze(0).cpu(),
                key_str,
                value_str,
            )
        )

        with torch.no_grad():
            self.model.self_token.data[slot_idx] += 0.01

        return slot_idx

    def get(self, key: str, top_k: int = 1) -> List[str]:
        key_str = str(key)
        
        # 1. EXACT MATCH FIRST (Legendary Upgrade)
        for slot_idx, bucket in self.slot_to_values.items():
            for k, v in bucket:
                if k == key_str:
                    return [v]

        # 2. NEURAL ROUTING (Fuzzy fallback for unseen keys)
        key_vec = self._encode(key_str)
        
        with torch.no_grad():
            sim = self.model.forward(key_vec, op="read")
            
            # Mask unoccupied slots
            mask = torch.full_like(sim, float('-inf'))
            for slot_idx in self.slot_to_values.keys():
                if slot_idx < self.num_slots:
                    mask[slot_idx] = 0.0
            
            sim = sim + mask
            
            # Select top slots
            k_select = min(top_k, len(self.slot_to_values))
            if k_select == 0:
                return []
                
            top_sim, top_slots = torch.topk(sim, k_select, dim=-1)
            
            results = []
            for slot_idx in top_slots[0].tolist():
                bucket = self.slot_to_values.get(slot_idx, [])
                if not bucket:
                    continue
                
                # Exact key match inside selected bucket
                exact_match = None
                for k, v in bucket:
                    if k == key_str:
                        exact_match = v
                        break
                        
                if exact_match is not None:
                    results.append(exact_match)
                else:
                    # Fallback to latest bucket value
                    results.append(bucket[-1][1])
                    
            # Deduplicate while preserving order
            seen = set()
            deduped = []
            for r in results:
                if r not in seen:
                    seen.add(r)
                    deduped.append(r)
                    
            return deduped[:top_k]

    def delete(self, key: str) -> bool:
        key_str = str(key)
        found = False
        
        orig_len = len(self._train_buffer)
        self._train_buffer = [
            (kv, vv, k, v)
            for kv, vv, k, v in self._train_buffer
            if k != key_str
        ]
        if len(self._train_buffer) < orig_len:
            found = True
            
        for slot_idx in list(self.slot_to_values.keys()):
            orig_bucket_len = len(self.slot_to_values[slot_idx])
            self.slot_to_values[slot_idx] = [
                (k, v)
                for k, v in self.slot_to_values[slot_idx]
                if k != key_str
            ]
            if len(self.slot_to_values[slot_idx]) < orig_bucket_len:
                found = True
            if not self.slot_to_values[slot_idx]:
                del self.slot_to_values[slot_idx]
                
        return found

    def train(self, epochs: int = 50, lr: float = 0.01, margin: float = 0.2) -> None:
        if not self._train_buffer:
            return
            
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        
        for epoch in range(epochs):
            for kv, vv, k, v in self._train_buffer:
                kv = kv.to(self.device)
                vv = vv.to(self.device)
                
                optimizer.zero_grad()
                sim = self.model.forward(kv, vv, op="write")
                
                target_slot = None
                for s_idx, bucket in self.slot_to_values.items():
                    for bk, bv in bucket:
                        if bk == k:
                            target_slot = s_idx
                            break
                    if target_slot is not None:
                        break
                        
                if target_slot is None:
                    continue
                    
                target_sim = sim[0, target_slot]
                loss = torch.tensor(0.0, device=self.device)
                for s_idx in range(self.num_slots):
                    if s_idx != target_slot:
                        loss = loss + torch.clamp(margin - target_sim + sim[0, s_idx], min=0.0)
                        
                if loss.item() > 0:
                    loss.backward()
                    optimizer.step()

    def consolidate(self) -> None:
        if not self._train_buffer:
            return
            
        with torch.no_grad():
            for s_idx in range(self.num_slots):
                bucket = self.slot_to_values.get(s_idx, [])
                if not bucket:
                    continue
                    
                key_vecs = []
                for kv, vv, k, v in self._train_buffer:
                    for bk, bv in bucket:
                        if bk == k:
                            key_vecs.append(kv)
                            break
                if key_vecs:
                    avg_vec = torch.stack(key_vecs).mean(dim=0).to(self.device)
                    proj = self.model.key_proj(avg_vec.unsqueeze(0)).squeeze(0)
                    self.model.prototypes.data[s_idx] = 0.9 * self.model.prototypes.data[s_idx] + 0.1 * proj

    def save(self, path: str) -> None:
        state = {
            "slot_to_values": dict(self.slot_to_values),
            "value_to_slot": self.value_to_slot,
            "train_buffer": [
                (kv.cpu(), vv.cpu(), k, v) for kv, vv, k, v in self._train_buffer
            ],
            "model_state": self.model.state_dict(),
            "fact_count": self.fact_count,
        }
        torch.save(state, path)

    def load(self, path: str) -> None:
        state = torch.load(path, map_location=self.device)
        self.slot_to_values = defaultdict(list)
        self.slot_to_values.update(state.get("slot_to_values", {}))
        self.value_to_slot = state.get("value_to_slot", {})
        self._train_buffer = state.get("train_buffer", [])
        if "model_state" in state:
            self.model.load_state_dict(state["model_state"])


# --- Hybrid Engine ---
class HybridEngine:
    def __init__(self, exact_secret: str = "default_secret", **swstm_kwargs):
        self.exact = ExactMemory(secret=exact_secret)
        self.swstm = SWSTMEngine(**swstm_kwargs)

    def add(self, key: str, value: str) -> None:
        self.exact.add(key, value)
        self.swstm.add(key, value)

    def get(self, key: str, top_k: int = 1) -> List[str]:
        exact_val = self.exact.get(key)
        if exact_val is not None:
            return [exact_val]
        return self.swstm.get(key, top_k=top_k)

    def delete(self, key: str) -> bool:
        return self.swstm.delete(key)

    @property
    def fact_count(self) -> int:
        return len(self.exact) + self.swstm.fact_count

    def __len__(self) -> int:
        return self.fact_count
        
    def train(self, *args, **kwargs):
        self.swstm.train(*args, **kwargs)
        
    def consolidate(self):
        self.swstm.consolidate()
        
    def save(self, path: str):
        self.swstm.save(path)
        
    def load(self, path: str):
        self.swstm.load(path)
