"""
ExactMemory - Cryptographic hash-table core.
"""
import hashlib
import hmac
import zlib
import json
import os
import logging
from typing import Any, Optional, Dict, Union

logger = logging.getLogger("recallspection.exact")
CHECKSUM_LEN = 16


class TamperDetectedError(Exception):
    def __init__(self, key: str):
        super().__init__(f"Tamper detected: checksum mismatch for key '{key}'")
        self.key = key


class ExactMemory:
    def __init__(self, quorum_size: int = 3, secret_key: Optional[bytes] = None):
        self._storage: Dict[bytes, bytes] = {}
        self._quorum_size = quorum_size
        self._secret_key = secret_key if secret_key is not None else os.urandom(32)

    def _hash_key(self, key: Union[str, bytes]) -> bytes:
        if isinstance(key, str):
            key = key.encode("utf-8")
        return hashlib.sha3_256(key).digest()

    def _pack_value(self, value: Any) -> bytes:
        json_bytes = json.dumps(value, sort_keys=True).encode("utf-8")
        compressed = zlib.compress(json_bytes, level=6)
        mac = hmac.new(self._secret_key, compressed, hashlib.sha3_256).digest()[:CHECKSUM_LEN]
        return mac + compressed

    def _unpack_value(self, packed: bytes) -> Any:
        # Compatibility note: returns None on ANY failure (too short, MAC
        # mismatch, decompress/JSON error) -- this matches the project's
        # own test contract (test_exact_memory_tamper expects get() ->
        # None on tamper, not an exception). See get(raise_on_tamper=)
        # for the stricter, audit-recommended alternative.
        if len(packed) < CHECKSUM_LEN:
            return None
        mac, compressed = packed[:CHECKSUM_LEN], packed[CHECKSUM_LEN:]
        expected = hmac.new(self._secret_key, compressed, hashlib.sha3_256).digest()[:CHECKSUM_LEN]
        if not hmac.compare_digest(mac, expected):
            return None
        try:
            return json.loads(zlib.decompress(compressed).decode("utf-8"))
        except Exception:
            return None

    def add(self, key: Union[str, bytes], value: Any) -> None:
        key_digest = self._hash_key(key)
        self._storage[key_digest] = self._pack_value(value)

    def get(self, key: Union[str, bytes], raise_on_tamper: bool = False) -> Optional[Any]:
        """
        Default behavior (raise_on_tamper=False) matches the existing test
        contract: returns None whether the key was never stored OR failed
        verification. NOTE: this makes tampering indistinguishable from
        absence to the caller -- flagged, not silently accepted as fine.
        Pass raise_on_tamper=True to get a TamperDetectedError instead,
        distinguishable from a normal miss, for callers who want to alert
        on real tampering rather than treat it as a cache miss.
        """
        key_digest = self._hash_key(key)
        packed = self._storage.get(key_digest)
        if packed is None:
            return None
        result = self._unpack_value(packed)
        if result is None and raise_on_tamper:
            key_str = key if isinstance(key, str) else key.decode("utf-8", errors="replace")
            logger.warning("Tamper detected for key '%s'", key_str)
            raise TamperDetectedError(key_str)
        return result

    def delete(self, key: Union[str, bytes]) -> bool:
        key_digest = self._hash_key(key)
        if key_digest in self._storage:
            del self._storage[key_digest]
            return True
        return False

    def __len__(self) -> int:
        return len(self._storage)

    def __contains__(self, key: Union[str, bytes]) -> bool:
        return self._hash_key(key) in self._storage

    def export_state(self) -> Dict[str, str]:
        return {k.hex(): v.hex() for k, v in self._storage.items()}

    def load_state(self, state: Dict[str, str]) -> None:
        self._storage = {bytes.fromhex(k): bytes.fromhex(v) for k, v in state.items()}
