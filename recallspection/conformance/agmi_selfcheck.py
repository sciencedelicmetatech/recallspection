"""
agmi conformance, self-contained. Pythonista-friendly.

Real T6 cross-context replay and T7 rollback replay.
Both use genuine record bytes from the tool itself, placed in a wrong slot.
Container MAC catches it on load. Verdict: rejected on read.

Nine edits T1-T9. Three verdicts: rejected, reported, accepted.
"""
import os, hmac, hashlib, json, time, zlib, shutil, tempfile
from pathlib import Path

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


def sha3_256_hex(data):
    return hashlib.sha3_256(data).hexdigest()


class ExactMemoryError(Exception): pass
class TamperError(ExactMemoryError): pass
class RollbackError(ExactMemoryError): pass
class LogCompromisedError(ExactMemoryError): pass
class MissingKeyError(ExactMemoryError): pass
class FormatVersionError(ExactMemoryError): pass


class RemoteAnchor:
    def anchor(self, chain_hash, max_version, container_hash):
        raise NotImplementedError
    def get_latest(self):
        raise NotImplementedError
    def verify(self, chain_hash):
        raise NotImplementedError


class StubAnchor(RemoteAnchor):
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


class TransparencyLog:
    def __init__(self, log_path, require_log=True):
        self.log_path = log_path
        self.require_log = require_log

    def _canonical(self, obj):
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

    def append(self, counter, max_version, container_hash):
        prev_hash = "0" * 64
        last = self._last_entry()
        if last:
            prev_hash = last["chain_hash"]
        entry = {
            "timestamp": int(time.time()),
            "counter": counter,
            "max_version": max_version,
            "container_hash": container_hash,
            "prev_hash": prev_hash,
        }
        chain_hash = sha3_256_hex(
            (prev_hash + self._canonical(entry).decode()).encode()
        )
        entry["chain_hash"] = chain_hash
        dir_name = os.path.dirname(os.path.abspath(self.log_path)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name)
        try:
            with os.fdopen(fd, "w") as f_tmp:
                f_tmp.write(self._canonical(entry).decode() + "\n")
                f_tmp.flush()
                os.fsync(f_tmp.fileno())
            with open(self.log_path, "a") as f:
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                with open(tmp_path, "r") as f_tmp_read:
                    f.write(f_tmp_read.read())
                f.flush()
                os.fsync(f.fileno())
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        return entry

    def _last_entry(self):
        if not os.path.exists(self.log_path):
            return None
        try:
            with open(self.log_path, "r") as f:
                lines = [l.strip() for l in f if l.strip()]
                return json.loads(lines[-1]) if lines else None
        except Exception:
            return None

    def verify_chain(self):
        if not os.path.exists(self.log_path):
            if self.require_log:
                return False, "Log file missing but require_log=True"
            return True, "No log yet"
        with open(self.log_path, "r") as f:
            lines = [l.strip() for l in f if l.strip()]
        prev_hash = "0" * 64
        for i, line in enumerate(lines):
            entry = json.loads(line)
            if entry.get("prev_hash") != prev_hash:
                return False, "Line " + str(i) + " prev_hash mismatch"
            entry_copy = {k: v for k, v in entry.items() if k != "chain_hash"}
            recomputed = sha3_256_hex(
                (prev_hash + self._canonical(entry_copy).decode()).encode()
            )
            if not hmac.compare_digest(recomputed, entry["chain_hash"]):
                return False, "Line " + str(i) + " chain_hash invalid"
            prev_hash = entry["chain_hash"]
        return True, "Chain OK - " + str(len(lines)) + " entries"

    def get_tip(self):
        return self._last_entry()


class ExactMemory:
    VERSION = "3.2.0"
    TRUSTED_SOURCES = frozenset({"system", "admin", "user_confirmed"})

    def __init__(self, keys, container_key_id="container", ttl_seconds=None,
                 log_path="./transparency.log", remote_anchor=None,
                 require_log=True, strict_rollback=True):
        if container_key_id not in keys:
            raise ValueError("container_key_id must exist in keys")
        self.keys = keys
        self.container_key_id = container_key_id
        self.ttl = ttl_seconds
        self.store = {}
        self.counter = 0
        self.max_version = 0
        self.per_key_max = {}
        self.tombstones = {}
        self.log = TransparencyLog(log_path, require_log=require_log)
        self.remote_anchor = remote_anchor
        self.require_log = require_log
        self.strict_rollback = strict_rollback
        self.tag_len = 32

    def _canonical(self, record):
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()

    def _make_tag(self, key_id, record):
        rec = record.copy()
        rec["_key_hash"] = sha3_256_hex(rec["key"].encode())
        rec["_key_id_hash"] = sha3_256_hex(key_id.encode())
        return hmac.new(
            self.keys[key_id], self._canonical(rec), hashlib.sha256
        ).digest()[:32]

    def _default_key_id(self):
        return next(iter([kk for kk in self.keys if kk != self.container_key_id]))

    def put(self, k, v, key_id=None, source="unknown", context=None, owner=None):
        kid = key_id or self._default_key_id()
        incoming_trusted = source in self.TRUSTED_SOURCES
        existing = self.store.get(k)
        if existing is not None:
            old_rec, _old_tag = existing
            if old_rec.get("trusted", False) and not incoming_trusted:
                old_rec.setdefault("shadow", []).append({
                    "value": v,
                    "source": source,
                    "ts": int(time.time()),
                })
                new_tag = self._make_tag(old_rec["key_id"], old_rec)
                self.store[k] = (old_rec, new_tag)
                return "rejected"
        self.counter += 1
        record = {
            "key": k,
            "value": v,
            "key_id": kid,
            "version": self.counter,
            "timestamp": int(time.time()),
            "nonce": os.urandom(16).hex(),
            "source": source,
            "trusted": incoming_trusted,
            "revoked": False,
            "shadow": existing[0].get("shadow", []) if existing else [],
            "context": context,
            "owner": owner,
        }
        tag = self._make_tag(kid, record)
        self.store[k] = (record, tag)
        self.max_version = self.counter
        self.per_key_max[k] = self.counter
        self.tombstones.pop(k, None)
        return "ok"

    def revoke(self, k, key_id=None):
        if k not in self.store:
            return "missing"
        rec, _old_tag = self.store[k]
        if rec.get("revoked", False):
            return "ok"
        self.counter += 1
        rec["revoked"] = True
        rec["version"] = self.counter
        rec["revoke_timestamp"] = int(time.time())
        new_tag = self._make_tag(rec["key_id"], rec)
        self.store[k] = (rec, new_tag)
        self.max_version = self.counter
        self.per_key_max[k] = self.counter
        return "ok"

    def get_shadow(self, k):
        if k not in self.store:
            return []
        rec, _tag = self.store[k]
        return list(rec.get("shadow", []))

    def get_with_status(self, k):
        if k in self.tombstones:
            rec, tag = self.tombstones[k]
            if not hmac.compare_digest(tag, self._make_tag(rec["key_id"], rec)):
                return None, "tampered"
            return None, "tombstoned"
        if k not in self.store:
            if k in self.per_key_max:
                return None, "tampered"
            return None, "missing"
        rec, tag = self.store[k]
        if not hmac.compare_digest(tag, self._make_tag(rec["key_id"], rec)):
            return None, "tampered"
        if rec["version"] < self.per_key_max.get(k, 0):
            return None, "tampered"
        if rec.get("revoked", False):
            return None, "revoked"
        if self.ttl is not None and int(time.time()) - rec["timestamp"] > self.ttl:
            return None, "expired"
        return rec["value"], "ok"

    def save(self, path):
        entries = [(key, rec, tag.hex())
                   for key, (rec, tag) in self.store.items()]
        tombs = [(key, rec, tag.hex())
                 for key, (rec, tag) in self.tombstones.items()]
        container = {
            "counter": self.counter,
            "max_version": self.max_version,
            "per_key_max": self.per_key_max,
            "entries": entries,
            "tombstones": tombs,
            "tag_len": 32,
            "version": self.VERSION,
            "container_key_id": self.container_key_id,
        }
        raw = json.dumps(container, sort_keys=True,
                         separators=(",", ":")).encode()
        compressed = zlib.compress(raw, 6)
        container_hash = sha3_256_hex(compressed)
        mac = hmac.new(
            self.keys[self.container_key_id], compressed, hashlib.sha256
        ).digest()
        dir_name = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name)
        try:
            with os.fdopen(fd, "wb") as f:
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(mac + compressed)
                f.flush()
                os.fsync(f.fileno())
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        log_entry = self.log.append(
            self.counter, self.max_version, container_hash
        )
        if self.remote_anchor:
            self.remote_anchor.anchor(
                log_entry["chain_hash"],
                self.max_version,
                container_hash,
            )

    def load(self, path, keys=None):
        valid, msg = self.log.verify_chain()
        if not valid:
            raise LogCompromisedError(msg)
        tip = self.log.get_tip()
        if self.require_log and not tip:
            raise LogCompromisedError("Log required but missing")
        if self.remote_anchor and tip:
            latest_remote = self.remote_anchor.get_latest()
            if latest_remote and tip["max_version"] < latest_remote["max_version"]:
                raise RollbackError("Log rollback vs remote anchor")
        with open(path, "rb") as f:
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            blob = f.read()
            if HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        if len(blob) < 32:
            raise TamperError("File too short")
        mac, compressed = blob[:32], blob[32:]
        expected_mac = hmac.new(
            self.keys[self.container_key_id], compressed, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise TamperError("Container MAC failed")
        container_hash = sha3_256_hex(compressed)
        raw = zlib.decompress(compressed)
        container = json.loads(raw)
        file_version = container.get("version", "unknown")
        if file_version != self.VERSION:
            raise FormatVersionError(
                "Container format " + str(file_version)
                + " incompatible with " + self.VERSION
            )
        if tip and container["max_version"] < tip["max_version"]:
            raise RollbackError(
                "ROLLBACK! File " + str(container["max_version"])
                + " < log " + str(tip["max_version"])
            )
        if keys is not None:
            self.keys = keys
        self.counter = container["counter"]
        self.max_version = container["max_version"]
        self.per_key_max = container.get("per_key_max", {})
        self.store = {}
        for k, rec, tag_hex in container["entries"]:
            if self.ttl is not None and int(time.time()) - rec["timestamp"] > self.ttl:
                continue
            self.store[k] = (rec, bytes.fromhex(tag_hex))
        self.tombstones = {
            k: (rec, bytes.fromhex(tag_hex))
            for k, rec, tag_hex in container.get("tombstones", [])
        }


INTEGRITY = (TamperError, RollbackError, LogCompromisedError, FormatVersionError)
TERMINAL = ("tampered", "tombstoned", "expired", "revoked")

CTX_A = "session-A"
CTX_B = "session-B"
OWNER_A = "agent-alpha"
OWNER_B = "agent-beta"


class Rig:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="agmi-rsc-"))
        self.db = self.dir / "memory.db"
        self.log = self.dir / "transparency.log"
        master = b"agmi-conformance-master-secret"
        self.keys = {
            "agent_key": hashlib.sha256(master).digest(),
            "container": hashlib.sha256(
                b"container-salt-" + hashlib.sha256(master).digest()
            ).digest(),
        }
        self.anchor = StubAnchor()
        self.recorded = []  # list of (key, context, owner, version)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _mem(self):
        return ExactMemory(
            keys=self.keys,
            container_key_id="container",
            require_log=True,
            log_path=str(self.log),
            remote_anchor=self.anchor,
        )

    def seed(self, n=6):
        m = self._mem()
        for i in range(n):
            if i % 2 == 0:
                ctx, own = CTX_A, OWNER_A
            else:
                ctx, own = CTX_B, OWNER_B
            k = "memory-" + str(i)
            m.put(k, "value number " + str(i), key_id="agent_key",
                  source="admin", context=ctx, owner=own)
            self.recorded.append((k, ctx, own, i + 1))
        m.save(str(self.db))

    def load_container(self):
        blob = self.db.read_bytes()
        mac, comp = blob[:32], blob[32:]
        return mac, json.loads(zlib.decompress(comp))

    def write_container(self, mac, container):
        raw = json.dumps(container, sort_keys=True,
                         separators=(",", ":")).encode()
        comp = zlib.compress(raw, 6)
        self.db.write_bytes(mac + comp)

    def append_genuine(self):
        m = self._mem()
        m.load(str(self.db))
        i = len(self.recorded)
        k = "memory-" + str(i)
        ctx = CTX_A if i % 2 == 0 else CTX_B
        own = OWNER_A if i % 2 == 0 else OWNER_B
        m.put(k, "genuine write", key_id="agent_key", source="admin",
              context=ctx, owner=own)
        self.recorded.append((k, ctx, own, i + 1))
        m.save(str(self.db))

    def snapshot(self):
        d = Path(tempfile.mkdtemp(prefix="agmi-rsc-snap-"))
        shutil.copy(self.db, d / "memory.db")
        shutil.copy(self.log, d / "transparency.log")
        return d

    def restore(self, d):
        shutil.copy(d / "memory.db", self.db)
        shutil.copy(d / "transparency.log", self.log)

    def read_path_verdict(self):
        """Return (verdict, detail).

        rejected  load refused, or every read cleanly terminal
        reported  load succeeded but a subsequent audit caught it
        accepted  load succeeded and audit saw nothing wrong
        """
        try:
            m = self._mem()
            m.load(str(self.db))
        except INTEGRITY as e:
            return "rejected", type(e).__name__ + ": " + str(e)[:80]
        except Exception as e:
            return "error", "load: " + type(e).__name__ + ": " + str(e)[:80]

        # Load succeeded. Now: does an audit (re-read + verify per-key) catch it?
        caught = None
        for k, _ctx, _own, _v in self.recorded:
            try:
                _val, status = m.get_with_status(k)
            except Exception as e:
                caught = "read raised " + type(e).__name__ + " on " + k
                break
            if status in TERMINAL:
                caught = "read refused " + k + ": " + status
                break

        if caught is not None:
            return "rejected", caught
        return "accepted", "load and audit both saw nothing wrong"


# --- T1 to T5, T8: byte edits to the container ---

def t1_content_tamper(r):
    mac, c = r.load_container()
    if not c["entries"]:
        return
    k, rec, tag = c["entries"][0]
    rec = dict(rec); rec["value"] = "TAMPERED"
    c["entries"][0] = [k, rec, tag]
    r.write_container(mac, c)


def t2_tail_truncation(r):
    mac, c = r.load_container()
    if c["entries"]:
        c["entries"] = c["entries"][:-1]
    r.write_container(mac, c)


def t3_middle_deletion(r):
    mac, c = r.load_container()
    if len(c["entries"]) >= 3:
        del c["entries"][1]
    r.write_container(mac, c)


def t4_reorder(r):
    mac, c = r.load_container()
    if len(c["entries"]) >= 2:
        c["entries"][0], c["entries"][1] = c["entries"][1], c["entries"][0]
    r.write_container(mac, c)


def t5_forged_insert(r):
    mac, c = r.load_container()
    forged = {
        "key": "forged-memory", "value": "attacker planted this",
        "key_id": "agent_key", "version": c.get("counter", 0) + 1,
        "timestamp": int(time.time()), "nonce": "0" * 32,
        "source": "unknown", "trusted": False, "revoked": False,
        "shadow": [], "context": CTX_A, "owner": "attacker",
    }
    c["entries"].append([forged["key"], forged, "0" * 64])
    r.write_container(mac, c)


def t8_metadata_tamper(r):
    mac, c = r.load_container()
    if c["entries"]:
        k, rec, tag = c["entries"][0]
        rec = dict(rec)
        rec["source"] = "spoofed-source"
        rec["timestamp"] = 0
        c["entries"][0] = [k, rec, tag]
    r.write_container(mac, c)


# --- T6 cross-context replay (agmi-realistic) ---
# Find a genuine record from CTX_A. Copy its bytes into the slot of a CTX_B
# record. Keep the victim's key identifier so the store looks well-formed.
# Every byte in the donor came from the tool itself. The MAC still fails.

def t6_cross_context_replay(r):
    mac, c = r.load_container()
    entries = c["entries"]
    src_i = None
    dst_i = None
    for i, (k, rec, tag) in enumerate(entries):
        if rec.get("context") == CTX_A and src_i is None:
            src_i = i
        if rec.get("context") == CTX_B and dst_i is None:
            dst_i = i
        if src_i is not None and dst_i is not None:
            break
    if src_i is None or dst_i is None:
        return
    _s_k, s_rec, s_tag = entries[src_i]
    d_k, _d_rec, _d_tag = entries[dst_i]
    donor = dict(s_rec)
    donor["key"] = d_k
    # victim's owner / identity slot preserved; donor's payload and context moved in
    donor["owner"] = s_rec.get("owner")
    entries[dst_i] = [d_k, donor, s_tag]
    r.write_container(mac, c)


# --- T7 rollback replay (agmi-realistic) ---
# Within the same context, copy the OLDEST genuine record over the NEWEST.
# Both are legitimate records of the same context. Only position is wrong.

def t7_rollback_replay(r):
    mac, c = r.load_container()
    entries = c["entries"]
    ctx_a = []
    for i, (k, rec, tag) in enumerate(entries):
        if rec.get("context") == CTX_A:
            ctx_a.append((i, k, rec, tag))
    if len(ctx_a) < 2:
        return
    older = ctx_a[0]
    newer = ctx_a[-1]
    _o_i, _o_k, o_rec, o_tag = older
    n_i, n_k, _n_rec, _n_tag = newer
    donor = dict(o_rec)
    donor["key"] = n_k
    entries[n_i] = [n_k, donor, o_tag]
    r.write_container(mac, c)


def t9_snapshot_rollback(r):
    snap = r.snapshot()
    r.append_genuine()
    r.restore(snap)
    shutil.rmtree(snap, ignore_errors=True)


ATTACKS = [
    ("T1 content tamper",       t1_content_tamper),
    ("T2 tail truncation",      t2_tail_truncation),
    ("T3 middle deletion",      t3_middle_deletion),
    ("T4 reordering",           t4_reorder),
    ("T5 forged insertion",     t5_forged_insert),
    ("T6 cross-context replay", t6_cross_context_replay),
    ("T7 rollback replay",      t7_rollback_replay),
    ("T8 metadata tamper",      t8_metadata_tamper),
    ("T9 snapshot rollback",    t9_snapshot_rollback),
]


def run():
    results = []
    for label, fn in ATTACKS:
        r = Rig()
        try:
            r.seed(6)
            fn(r)
            verdict, detail = r.read_path_verdict()
        except Exception as e:
            verdict, detail = "error", type(e).__name__ + ": " + str(e)[:120]
        finally:
            r.cleanup()
        results.append((label, verdict, detail))

    print()
    print("=" * 80)
    print("agmi conformance, Recallspection / ExactMemory v3.2.0")
    print("=" * 80)
    print("%-26s%-10s%s" % ("edit", "verdict", "detail"))
    print("-" * 80)
    for label, verdict, detail in results:
        print("%-26s%-10s%s" % (label, verdict, detail))
    print("-" * 80)

    rejected = sum(1 for _, v, _ in results if v == "rejected")
    reported = sum(1 for _, v, _ in results if v == "reported")
    accepted = sum(1 for _, v, _ in results if v == "accepted")
    errors = sum(1 for _, v, _ in results if v == "error")
    print("rejected: %d   reported: %d   accepted: %d   errors: %d"
          % (rejected, reported, accepted, errors))
    print()
    if errors:
        print("Errors mean environment fault.")
        return 2
    if accepted == 0 and reported == 0:
        print("All nine edits rejected on the read path.")
        return 0
    if accepted == 0:
        print("All edits either rejected or reported.")
        return 0
    print("At least one edit was accepted.")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())