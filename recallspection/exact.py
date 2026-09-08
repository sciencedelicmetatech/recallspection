"""
ExactMemory - Cryptographic hash-table core.
Pure Python stdlib only (hmac/hashlib/zlib/json).

THREAT MODEL (read before deploying):
  This module protects against ACCIDENTAL corruption (bit flips, disk
  errors, truncated writes) with high confidence, PROVIDED a secret
  key is supplied that is not available to whatever is doing the
  corrupting.
  It does NOT protect against a deliberate actor who has both write
  access to the underlying storage AND the secret key -- no MAC scheme
  can defend against that. If you need protection against an untrusted
  process with raw storage access, keep the secret key outside that
  process's reach (e.g. a separate signing service).
"""

import hashlib
import hmac
import zlib
import json
import os
import logging
from typing import Any, Optional, Dict, Union

logger = logging.getLogger("recallspection.exact")

CHECKSUM_LEN = 16  # bytes; 4 bytes (32 bits) is brute-forceable in seconds
                    # on commodity hardware and is not sufficient even for
                    # accidental-corruption detection at scale.


class TamperDetectedError(Exception):
    """Raised when a stored value fails integrity verification.
    Distinguished deliberately from 'key not found' -- silently treating
    tampering the same as absence defeats the point of tamper-evidence."""
    def __init__(self, key: str):
        super().__init__(f"Tamper detected: checksum mismatch for key '{key}'")
        self.key = key


class ExactMemory:
    """
    Tamper-evident (against accidental corruption) key-value store.
    Uses SHA3-256 for key hashing and HMAC-SHA3-256 for value integrity.
    """

    def __init__(self, secret_key: Optional[bytes] = None):
        """
        secret_key: HMAC key. If not provided, one is generated randomly
        and is NOT persisted -- callers needing persistence across
        process restarts MUST supply and manage their own secret_key
        (e.g. from an environment variable or secrets manager), or every
        value written in a previous process will fail verification after
        restart. This is intentional: silently persisting a generated
        key alongside the data it protects would defeat the point of a
        keyed MAC.
        """
        self._storage: Dict[bytes, bytes] = {}
        self._secret_key = secret_key if secret_key is not None else os.urandom(32)

    # ---------------- internal helpers ----------------

    def _hash_key(self, key: Union[str, bytes]) -> bytes:
        if isinstance(key, str):
            key = key.encode("utf-8")
        return hashlib.sha3_256(key).digest()

    def _pack_value(self, value: Any) -> bytes:
        json_bytes = json.dumps(value, sort_keys=True).encode("utf-8")
        compressed = zlib.compress(json_bytes, level=6)
        mac = hmac.new(self._secret_key, compressed, hashlib.sha3_256).digest()[:CHECKSUM_LEN]
        return mac + compressed

    def _unpack_value(self, key_str: str, packed: bytes) -> Any:
        if len(packed) < CHECKSUM_LEN:
            raise TamperDetectedError(key_str)
        mac, compressed = packed[:CHECKSUM_LEN], packed[CHECKSUM_LEN:]
        expected = hmac.new(self._secret_key, compressed, hashlib.sha3_256).digest()[:CHECKSUM_LEN]
        if not hmac.compare_digest(mac, expected):
            raise TamperDetectedError(key_str)
        try:
            return json.loads(zlib.decompress(compressed).decode("utf-8"))
        except Exception as e:
            # decompression/JSON failure after a passing MAC means the
            # MAC itself was forged or corrupted in a way that happened
            # to collide -- astronomically unlikely, but fail loudly.
            raise TamperDetectedError(key_str) from e

    # ---------------- public API ----------------

    def add(self, key: Union[str, bytes], value: Any) -> None:
        """Store a key-value pair. Overwrites do not inflate fact count
        (see __len__)."""
        key_digest = self._hash_key(key)
        self._storage[key_digest] = self._pack_value(value)

    def get(self, key: Union[str, bytes]) -> Optional[Any]:
        """Retrieve value for key.
        Returns None if the key was never stored.
        Raises TamperDetectedError if the key exists but failed
        verification -- this is deliberately NOT the same code path as
        'not found', so callers can alert/log on real tampering instead
        of silently treating it as a cache miss."""
        key_digest = self._hash_key(key)
        packed = self._storage.get(key_digest)
        if packed is None:
            return None
        key_str = key if isinstance(key, str) else key.decode("utf-8", errors="replace")
        try:
            return self._unpack_value(key_str, packed)
        except TamperDetectedError:
            logger.warning("Tamper detected for key digest %s", key_digest.hex())
            raise

    def get_or_none(self, key: Union[str, bytes]) -> Optional[Any]:
        """Convenience wrapper for callers who want the old
        'never distinguish tamper from absence' behavior. Prefer get()
        and handle TamperDetectedError explicitly in new code."""
        try:
            return self.get(key)
        except TamperDetectedError:
            return None

    def delete(self, key: Union[str, bytes]) -> bool:
        key_digest = self._hash_key(key)
        if key_digest in self._storage:
            del self._storage[key_digest]
            return True
        return False

    def __len__(self) -> int:
        """Actual distinct key count, not a manually-tracked counter
        that can drift from reality on overwrite."""
        return len(self._storage)

    def __contains__(self, key: Union[str, bytes]) -> bool:
        return self._hash_key(key) in self._storage

    # ---------------- persistence (explicit, not private-attribute poking) ----------------

    def export_state(self) -> Dict[str, str]:
        """Hex-encoded snapshot for persistence. Callers (e.g. api.py)
        should use this instead of reaching into _storage directly."""
        return {k.hex(): v.hex() for k, v in self._storage.items()}

    def load_state(self, state: Dict[str, str]) -> None:
        self._storage = {bytes.fromhex(k): bytes.fromhex(v) for k, v in state.items()}
