"""
Adapter between agmi's MemoryAdapter interface and ExactMemory.

Real T6/T7 support: contexts are stored in each record's `context` field.
The per-key `put()` writes the context into the record, which the
per-record tag and the container MAC both cover. Replaying a genuine
record into a different context or position changes container bytes,
which breaks the container MAC, which rejects on read.

Real T9 support: snapshot_store/restore_store copy both memory.db and
transparency.log. remote_anchor (from Env, or a test stub) holds the
high-water mark off-store.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import zlib
from pathlib import Path

from agmi.adapters.base import MemoryAdapter, Record

from exactmemory.recallspection import (
    ExactMemory, TamperError, RollbackError, LogCompromisedError,
)

try:
    from exactmemory.recallspection import FormatVersionError
except ImportError:
    FormatVersionError = Exception


INTEGRITY = (TamperError, RollbackError, LogCompromisedError, FormatVersionError)
TERMINAL = ("tampered", "tombstoned", "expired", "revoked")

CTX_A = "session-A"
CTX_B = "session-B"


class StubAnchor:
    def __init__(self):
        self._mark = 0
        self._chain = None
    def anchor(self, chain_hash, max_version, container_hash):
        if max_version > self._mark:
            self._mark = max_version
            self._chain = chain_hash
    def get_latest(self):
        if self._mark == 0:
            return None
        return {"max_version": self._mark, "chain_hash": self._chain}
    def verify(self, chain_hash):
        return chain_hash == self._chain


class RecallspectionAdapter(MemoryAdapter):
    name = "recallspection"
    supports_replay = True
    supports_metadata = True
    supports_snapshot = True

    def __init__(self):
        self._dir = None
        self._db = None
        self._log = None
        self._keys = None
        self._anchor = None
        self._seeded = []
        self.verify_detail = None

    # --- lifecycle ---
    def setup(self):
        self._dir = Path(tempfile.mkdtemp(prefix="agmi-recallspection-"))
        self._db = self._dir / "memory.db"
        self._log = self._dir / "transparency.log"
        master = b"agmi-conformance-master-secret"
        self._keys = {
            "agent_key": hashlib.sha256(master).digest(),
            "container": hashlib.sha256(
                b"container-salt-" + hashlib.sha256(master).digest()
            ).digest(),
        }
        self._anchor = StubAnchor()
        self._seeded = []

    def teardown(self):
        if self._dir and self._dir.exists():
            shutil.rmtree(self._dir, ignore_errors=True)
        self._dir = None

    def _mem(self):
        return ExactMemory(
            keys=self._keys,
            container_key_id="container",
            require_log=True,
            log_path=str(self._log),
            remote_anchor=self._anchor,
        )

    # --- seeding ---
    def seed(self, n):
        m = self._mem()
        for i in range(n):
            ctx = CTX_A if i % 2 == 0 else CTX_B
            k = "memory-" + str(i)
            m.put(k, "value number " + str(i), key_id="agent_key",
                  source="admin", context=ctx)
            self._seeded.append(k)
        m.save(str(self._db))

    def seed_other(self, n):
        m = self._mem()
        for i in range(n):
            k = "other-" + str(i)
            m.put(k, "other value " + str(i), key_id="agent_key",
                  source="admin", context=CTX_B)
            self._seeded.append(k)
        m.save(str(self._db))

    # --- raw container access ---
    def _load_container(self):
        blob = self._db.read_bytes()
        mac, compressed = blob[:32], blob[32:]
        return mac, json.loads(zlib.decompress(compressed))

    def _write_container(self, mac, container):
        raw = json.dumps(container, sort_keys=True,
                         separators=(",", ":")).encode()
        compressed = zlib.compress(raw, 6)
        self._db.write_bytes(mac + compressed)

    def read_all_raw(self):
        _, c = self._load_container()
        out = []
        for i, (k, rec, tag_hex) in enumerate(c.get("entries", [])):
            out.append(Record(seq=i, fields={
                "key": k,
                "value": rec.get("value"),
                "version": rec.get("version"),
                "timestamp": rec.get("timestamp"),
                "source": rec.get("source"),
                "owner": rec.get("owner"),
                "identity": rec.get("key_id"),
                "context": rec.get("context"),
                "tag": tag_hex,
            }))
        return out

    def read_other_raw(self):
        return self.read_all_raw()

    def write_raw(self, record):
        mac, c = self._load_container()
        entries = c.get("entries", [])
        i = record.seq
        f = record.fields
        if i < len(entries):
            k, rec, tag = entries[i]
            rec = dict(rec)
            for fld in ("value", "timestamp", "source", "context", "owner"):
                if fld in f:
                    rec[fld] = f[fld]
            entries[i] = [k, rec, tag]
        c["entries"] = entries
        self._write_container(mac, c)

    def delete_raw(self, seq):
        mac, c = self._load_container()
        entries = c.get("entries", [])
        if seq < len(entries):
            del entries[seq]
        c["entries"] = entries
        self._write_container(mac, c)

    def replay_onto(self, victim_seq, donor):
        """Copy donor's genuine bytes onto the victim slot.

        Both donor and victim records exist in the tool's own store.
        This moves genuine bytes without writing through put(), which is
        exactly the attack T6/T7 model.
        """
        mac, c = self._load_container()
        entries = c.get("entries", [])
        if victim_seq >= len(entries):
            return
        v_k, _v_rec, _v_tag = entries[victim_seq]
        d = donor.fields
        new_rec = {
            "key": v_k,
            "value": d.get("value"),
            "key_id": d.get("identity", "agent_key"),
            "version": d.get("version", 1),
            "timestamp": d.get("timestamp", int(time.time())),
            "nonce": "0" * 32,
            "source": d.get("source", "unknown"),
            "trusted": True,
            "revoked": False,
            "shadow": [],
            "context": d.get("context"),
            "owner": d.get("owner"),
        }
        entries[victim_seq] = [v_k, new_rec, d.get("tag", "0" * 64)]
        c["entries"] = entries
        self._write_container(mac, c)

    # --- metadata layer ---
    def read_meta(self, seq):
        _, c = self._load_container()
        entries = c.get("entries", [])
        if seq >= len(entries):
            return {}
        k, rec, _tag = entries[seq]
        return {"owner": rec.get("owner"), "context": rec.get("context")}

    def write_meta(self, seq, meta):
        mac, c = self._load_container()
        entries = c.get("entries", [])
        if seq >= len(entries):
            return
        k, rec, tag = entries[seq]
        rec = dict(rec)
        rec.update(meta)
        entries[seq] = [k, rec, tag]
        c["entries"] = entries
        self._write_container(mac, c)

    # --- payload hooks ---
    def mutate_payload(self, record):
        f = dict(record.fields)
        f["value"] = str(f.get("value", "")) + " [TAMPERED]"
        return Record(seq=record.seq, fields=f)

    def forge_record(self, template):
        f = dict(template.fields)
        f["key"] = "forged-memory"
        f["value"] = "attacker planted this"
        f["owner"] = "attacker"
        return Record(seq=template.seq + 1, fields=f)

    # --- snapshot (T9) ---
    def snapshot_store(self):
        d = Path(tempfile.mkdtemp(prefix="agmi-rsc-snap-"))
        shutil.copy(self._db, d / "memory.db")
        shutil.copy(self._log, d / "transparency.log")
        return d

    def restore_store(self, token):
        shutil.copy(token / "memory.db", self._db)
        shutil.copy(token / "transparency.log", self._log)

    def append_genuine(self):
        m = self._mem()
        m.load(str(self._db))
        i = len(self._seeded)
        k = "memory-" + str(i)
        ctx = CTX_A if i % 2 == 0 else CTX_B
        m.put(k, "genuine write", key_id="agent_key", source="admin", context=ctx)
        self._seeded.append(k)
        m.save(str(self._db))

    # --- reload + verify ---
    def reload(self):
        pass

    def verify(self):
        self.verify_detail = None
        try:
            m = self._mem()
            m.load(str(self._db))
        except INTEGRITY as e:
            self.verify_detail = type(e).__name__ + ": " + str(e)[:120]
            return False
        except Exception as e:
            self.verify_detail = "error: " + type(e).__name__ + ": " + str(e)[:120]
            return False
        for k in self._seeded:
            try:
                _val, status = m.get_with_status(k)
            except Exception as e:
                self.verify_detail = "read raised " + type(e).__name__ + " on " + k
                return False
            if status in TERMINAL:
                self.verify_detail = "read refused " + k + ": " + status
                return False
        return True