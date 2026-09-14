# --- ExactMemory (re-exported for test imports) ---
import hashlib
import json
import zlib
from typing import Any, Dict, List, Optional, Tuple, Union

class ExactMemory:
    def __init__(self):
        self._storage: Dict[bytes, bytes] = {}
        self._fact_count = 0

    def _hash_key(self, key: Union[str, bytes]) -> bytes:
        if isinstance(key, str): key = key.encode("utf-8")
        return hashlib.sha3_256(key).digest()

    def _pack(self, value: Any) -> bytes:
        json_str = json.dumps(value, sort_keys=True)
        compressed = zlib.compress(json_str.encode("utf-8"), level=6)
        checksum = hashlib.sha256(compressed).digest()
        return checksum + compressed

    def _unpack(self, packed: bytes) -> Optional[Any]:
        if len(packed) < 32: return None
        checksum, compressed = packed[:32], packed[32:]
        if hashlib.sha256(compressed).digest() != checksum: return None
        try: return json.loads(zlib.decompress(compressed).decode("utf-8"))
        except Exception: return None

    def add(self, key: Union[str, bytes], value: Any) -> None:
        self._storage[self._hash_key(key)] = self._pack(value)
        self._fact_count += 1

    def get(self, key: Union[str, bytes]) -> Optional[Any]:
        packed = self._storage.get(self._hash_key(key))
        return self._unpack(packed) if packed else None

    def delete(self, key: Union[str, bytes]) -> bool:
        key_digest = self._hash_key(key)
        if key_digest in self._storage:
            del self._storage[key_digest]
            self._fact_count -= 1
            return True
        return False

    def __len__(self) -> int: return self._fact_count
    def __contains__(self, key: Union[str, bytes]) -> bool: return self._hash_key(key) in self._storage


# --- SWSTM Core (Legendary Version) ---
import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import defaultdict

class SWSTMCore(nn.Module):
    def __init__(self, num_slots: int, slot_dim: int, key_dim: int, temperature: float = 0.01):
        super().__init__()
        self.num_slots = num_slots
        self.slot_dim = slot_dim
        self.key_dim = key_dim
        self.temperature = temperature
        self.prototype = nn.Parameter(torch.randn(num_slots, key_dim) * 0.02)
        
        # [LEGENDARY FEATURE 1] Sticky Tokens: Tracks usage/frequency
        self.self_token = nn.Parameter(torch.zeros(num_slots))
        
        self.register_buffer("memory", torch.zeros(num_slots, slot_dim))
        self.register_buffer("slot_occupied", torch.zeros(num_slots, dtype=torch.bool))
        self.register_buffer("write_count", torch.zeros(num_slots, dtype=torch.long))

    def forward(self, keys: torch.Tensor, values: Optional[torch.Tensor] = None, op: str = "read"):
        keys_norm = F.normalize(keys, dim=-1)
        proto_norm = F.normalize(self.prototype, dim=-1)
        
        sims = torch.matmul(keys_norm, proto_norm.T) + self.self_token.unsqueeze(0)
        soft_w = F.softmax(sims / self.temperature, dim=-1)
        hard_idx = torch.argmax(soft_w, dim=-1)
        one_hot = F.one_hot(hard_idx, num_classes=self.num_slots).float()
        weights = one_hot.detach() + (soft_w - soft_w.detach())
        
        if op == "write":
            if values is None: raise ValueError("values required for write")
            delta = torch.einsum("bn,bd->nd", weights, values)
            self.memory.add_(delta)
            self.slot_occupied[hard_idx] = True
            self.write_count[hard_idx] += 1
            return hard_idx
            
        return torch.matmul(weights, self.memory)

    def read_exact(self, keys: torch.Tensor) -> torch.Tensor:
        keys_norm = F.normalize(keys, dim=-1)
        proto_norm = F.normalize(self.prototype, dim=-1)
        sims = torch.matmul(keys_norm, proto_norm.T) + self.self_token.unsqueeze(0)
        hard_idx = torch.argmax(sims, dim=-1)
        one_hot = F.one_hot(hard_idx, num_classes=self.num_slots).float()
        return torch.matmul(one_hot, self.memory)

    def margin_loss(self, keys: torch.Tensor, margin: float = 0.2) -> torch.Tensor:
        keys_norm = F.normalize(keys, dim=-1)
        proto_norm = F.normalize(self.prototype, dim=-1)
        sims = torch.matmul(keys_norm, proto_norm.T) + self.self_token.unsqueeze(0)
        top2, _ = sims.topk(2, dim=-1)
        return torch.mean(F.relu(margin - (top2[:, 0] - top2[:, 1])))

    def init_prototypes_from_keys(self, keys: torch.Tensor):
        from sklearn.cluster import KMeans
        keys_np = keys.detach().cpu().numpy()
        n_clusters = min(self.num_slots, keys_np.shape[0])
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        kmeans.fit(keys_np)
        centroids = torch.tensor(kmeans.cluster_centers_, dtype=keys.dtype, device=keys.device)
        self.prototype.data[:n_clusters] = centroids[:n_clusters]

    def get_state(self) -> Dict[str, Any]:
        return {
            "prototype": self.prototype.cpu(),
            "self_token": self.self_token.cpu(),
            "memory": self.memory.cpu(),
            "slot_occupied": self.slot_occupied.cpu(),
            "write_count": self.write_count.cpu(),
            "num_slots": self.num_slots,
            "slot_dim": self.slot_dim,
            "key_dim": self.key_dim,
            "temperature": self.temperature,
        }

    def set_state(self, state: Dict[str, Any]):
        self.prototype.data.copy_(state["prototype"].to(self.prototype.device))
        self.self_token.data.copy_(state["self_token"].to(self.self_token.device))
        self.memory.copy_(state["memory"].to(self.memory.device))
        self.slot_occupied.copy_(state["slot_occupied"].to(self.slot_occupied.device))
        self.write_count.copy_(state["write_count"].to(self.write_count.device))

# --- SWSTM Engine (Legendary Version) ---
from sentence_transformers import SentenceTransformer
from pathlib import Path

class SWSTMEngine:
    def __init__(
        self,
        num_slots: int = 2000,
        key_dim: int = 384,
        slot_dim: int = 384,
        temperature: float = 0.01,
        encoder_model: str = "all-MiniLM-L6-v2",
        device: Optional[torch.device] = None,
    ):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.key_dim = key_dim
        self.slot_dim = slot_dim
        self.encoder = SentenceTransformer(encoder_model)
        self.model = SWSTMCore(
            num_slots=num_slots,
            slot_dim=slot_dim,
            key_dim=key_dim,
            temperature=temperature,
        ).to(self.device)
        
        # [LEGENDARY FEATURE 2] Slot Buckets instead of Dict Overwrites!
        self.slot_to_values: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
        
        self.value_to_slot: Dict[str, int] = {}
        # Buffer stores: (key_vec, val_vec, key_str, value_str)
        self._train_buffer: List[tuple] = [] 
        self._prototypes_initialized = False

    def _encode(self, text: str) -> torch.Tensor:
        vec = self.encoder.encode(text, convert_to_tensor=True)
        if vec.dim() == 1: vec = vec.unsqueeze(0)
        return F.normalize(vec.to(self.device), dim=-1)

    def add(self, key: str, value: str) -> int:
        key_vec = self._encode(key)
        val_vec = self._encode(value)
        with torch.no_grad():
            slot_idx = self.model.forward(key_vec, val_vec, op="write").item()
            
        # [LEGENDARY FIX] Append to bucket instead of overwriting!
        self.slot_to_values[slot_idx].append((key, value))
        self.value_to_slot[value] = slot_idx
        
        # Buffer stores both vector and string for consolidation
        self._train_buffer.append((key_vec.squeeze(0), val_vec.squeeze(0), key, value))
        
        # [LEGENDARY FEATURE 3] Sticky Token Reward
        with torch.no_grad():
            self.model.self_token[slot_idx] += 0.01
            
        return slot_idx

    def get(self, key: str, top_k: int = 1) -> List[str]:
        key_vec = self._encode(key)
        with torch.no_grad():
            keys_norm = F.normalize(key_vec, dim=-1)
            proto_norm = F.normalize(self.model.prototype, dim=-1)
            sims = torch.matmul(keys_norm, proto_norm.T) + self.model.self_token.unsqueeze(0)
            occupied_mask = self.model.slot_occupied.unsqueeze(0)
            sims = sims.masked_fill(~occupied_mask, float("-inf"))
            k = min(top_k, int(occupied_mask.sum().item()))
            if k == 0: return []
            _, top_indices = torch.topk(sims, k, dim=-1)
            
        results = []
        for idx in top_indices.squeeze(0).tolist():
            bucket = self.slot_to_values.get(idx, [])
            
            # Exact match resolution inside the bucket
            exact_match = None
            for k_val, v_val in bucket:
                if k_val == key:
                    exact_match = v_val
                    break
                    
            if exact_match is not None:
                results.append(exact_match)
            elif bucket:
                # Fuzzy fallback: return the most recently added value in this conceptual cluster
                results.append(bucket[-1][1])
                
        return results

    # [LEGENDARY FEATURE 4] Neural Sleep (Consolidation)
    def consolidate(self, epochs: int = 10, lr: float = 0.01, margin: float = 0.2):
        """
        Re-organizes memory topology to reduce collisions. 
        Like biological sleep, it re-clusters memories and defragments slots.
        """
        if len(self._train_buffer) < 2:
            print("[SWSTM] Not enough data to consolidate.")
            return
            
        keys = torch.stack([k for k, _, _, _ in self._train_buffer])
        print(f"[SWSTM] Entering Consolidation Phase (Neural Sleep) on {len(keys)} memories...")
        
        # 1. Re-train prototypes to find better conceptual clusters
        self.model.init_prototypes_from_keys(keys)
        
        # 2. Reset the neural memory buffer and buckets
        self.model.memory.zero_()
        self.model.slot_occupied.zero_()
        self.model.write_count.zero_()
        self.slot_to_values.clear()
        
        # 3. Re-route all memories into the newly optimized slots
        for key_vec, val_vec, key_str, value_str in self._train_buffer:
            with torch.no_grad():
                self.model.self_token.zero_() # Clean slate for routing
                slot_idx = self.model.forward(key_vec.unsqueeze(0), val_vec.unsqueeze(0), op="write").item()
            
            self.slot_to_values[slot_idx].append((key_str, value_str))
            self.value_to_slot[value_str] = slot_idx
            
        print("[SWSTM] Consolidation complete. Memory defragmented.")

    def train(self, epochs: int = 50, lr: float = 0.01, margin: float = 0.2):
        if len(self._train_buffer) < 2:
            print("[SWSTM] Not enough data to train.")
            return
        keys = torch.stack([k for k, _, _, _ in self._train_buffer])
        if not self._prototypes_initialized:
            print(f"[SWSTM] Initializing {self.model.num_slots} prototypes from {len(keys)} keys...")
            self.model.init_prototypes_from_keys(keys)
            self._prototypes_initialized = True
            
            # Reset and repopulate buffers cleanly
            self.model.memory.zero_()
            self.model.slot_occupied.zero_()
            self.model.write_count.zero_()
            self.slot_to_values.clear()
            self.value_to_slot.clear()
            
            for key_vec, val_vec, key_str, value_str in self._train_buffer:
                slot_idx = self.model.forward(key_vec.unsqueeze(0), val_vec.unsqueeze(0), op="write").item()
                self.slot_to_values[slot_idx].append((key_str, value_str))
                self.value_to_slot[value_str] = slot_idx
                
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        print(f"[SWSTM] Training on {len(keys)} keys for {epochs} epochs...")
        for epoch in range(epochs):
            optimizer.zero_grad()
            loss = self.model.margin_loss(keys, margin=margin)
            loss.backward()
            optimizer.step()
            if (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{epochs}, margin_loss={loss.item():.4f}")
        print("[SWSTM] Training complete.")

    def exact_match_accuracy(self, test_keys: List[str], test_values: List[str]) -> float:
        if not test_keys: return 0.0
        correct = 0
        for k, v in zip(test_keys, test_values):
            retrieved = self.get(k, top_k=1)
            if retrieved and retrieved[0] == v:
                correct += 1
        return correct / len(test_keys)

    def paraphrase_accuracy(self, paraphrase_keys: List[str], expected_values: List[str]) -> float:
        if not paraphrase_keys: return 0.0
        correct = 0
        for k, v in zip(paraphrase_keys, expected_values):
            retrieved = self.get(k, top_k=1)
            if retrieved and retrieved[0] == v:
                correct += 1
        return correct / len(paraphrase_keys)

    def save(self, path: Union[str, Path]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "model": self.model.get_state(),
            "slot_to_values": dict(self.slot_to_values), # Convert defaultdict to dict for JSON/Pickle
            "value_to_slot": self.value_to_slot,
            "key_dim": self.key_dim,
            "slot_dim": self.slot_dim,
        }
        torch.save(state, path)
        print(f"[SWSTM] Saved to {path}")

    def load(self, path: Union[str, Path]):
        state = torch.load(path, map_location=self.device, weights_only=False)
        self.model.set_state(state["model"])
        self.slot_to_values = defaultdict(list, state["slot_to_values"])
        self.value_to_slot = state["value_to_slot"]
        self.key_dim = state["key_dim"]
        self.slot_dim = state["slot_dim"]
        print(f"[SWSTM] Loaded from {path}")

# --- Hybrid Engine ---
class HybridEngine:
    def __init__(self, **swstm_kwargs):
        self.exact = ExactMemory()
        self.swstm = SWSTMEngine(**swstm_kwargs)

    def add(self, key: str, value: str):
        self.exact.add(key, value)
        self.swstm.add(key, value)

    def get(self, key: str, top_k: int = 1) -> List[str]:
        result = self.exact.get(key)
        if result is not None:
            return [result]
        return self.swstm.get(key, top_k=top_k)

    def train(self, epochs: int = 50, lr: float = 0.01):
        self.swstm.train(epochs=epochs, lr=lr)

    def consolidate(self):
        self.swstm.consolidate()

    def save(self, path: Union[str, Path]):
        self.swstm.save(path)

    def load(self, path: Union[str, Path]):
        self.swstm.load(path)
