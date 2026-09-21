"""
Recallspection Test Suite
=========================
Three tests in one file:
  1. PARITY      — verify crypto correctness against NIST vectors
  2. PERSISTENCE — save a fact, then reload it after app restart
  3. TAMPER      — prove tampering is detected

Usage:
  python recallspection_test_suite.py parity
  python recallspection_test_suite.py save
  python recallspection_test_suite.py load
  python recallspection_test_suite.py tamper

Or run with no argument to run parity + tamper (safe, in-memory).
"""

import hashlib
import hmac
import zlib
import json
import platform
import sys
import os


# ===========================================================================
# Storage path (iOS-safe: ~/Documents is writable, script dir is not)
# ===========================================================================
DB_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "recallspection_test.json"
)

KEYS = {
    "agent_key": b"bench-agent-key-32-bytes-long!!!",
    "container": b"bench-container-key-32-bytes!!!!",
}
assert len(KEYS["agent_key"]) == 32
assert len(KEYS["container"]) == 32


# ===========================================================================
# TEST 1: PARITY — cryptographic correctness against NIST vectors
# ===========================================================================
def test_parity():
    print("=" * 60)
    print("TEST 1: CROSS-PLATFORM PARITY")
    print("=" * 60)
    print()

    print("ENVIRONMENT")
    print("-" * 60)
    print("platform:        " + platform.platform())
    print("machine:         " + platform.machine())
    print("python_version:  " + sys.version.split()[0])
    print("implementation:  " + platform.python_implementation())
    print()

    # --- SHA3-256 NIST test vectors ---
    print("SHA3-256 NIST TEST VECTORS")
    print("-" * 60)

    vectors = [
        b"",
        b"abc",
        b"Recallspection",
        b"Clause 4.2: The Contractor shall deliver the final report within 30 days.",
        b'{"confidence":0.99,"object":"Paris","predicate":"located_in","subject":"Eiffel Tower"}',
    ]

    # Published NIST reference values for the first two inputs
    NIST_EMPTY = "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
    NIST_ABC   = "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532"

    hashes = []
    for i, v in enumerate(vectors):
        h = hashlib.sha3_256(v).hexdigest()
        hashes.append(h)
        label = v[:40].decode("utf-8", errors="replace")
        print("  [" + str(i) + "] input:  " + repr(label))
        print("      hash:   " + h)

    print()
    print("VERIFICATION AGAINST NIST")
    print("-" * 60)

    ok = True

    if hashes[0] == NIST_EMPTY:
        print("  [0] empty string  MATCHES NIST  PASS")
    else:
        print("  [0] empty string  MISMATCH      FAIL")
        print("      expected: " + NIST_EMPTY)
        print("      got:      " + hashes[0])
        ok = False

    if hashes[1] == NIST_ABC:
        print("  [1] 'abc'         MATCHES NIST  PASS")
    else:
        print("  [1] 'abc'         MISMATCH      FAIL")
        print("      expected: " + NIST_ABC)
        print("      got:      " + hashes[1])
        ok = False

    print()

    # --- HMAC-SHA256 ---
    print("HMAC-SHA256 TEST")
    print("-" * 60)
    key = b"bench-agent-key-32-bytes-long!!!"
    message = b"test message for hmac"
    tag = hmac.new(key, message, hashlib.sha256).digest()
    print("  tag hex: " + tag.hex())
    print()

    # --- zlib round-trip ---
    print("ZLIB ROUND-TRIP TEST")
    print("-" * 60)
    sample = b"Clause 4.2: The Contractor shall deliver the final report within 30 days."
    compressed = zlib.compress(sample, 6)
    decompressed = zlib.decompress(compressed)
    rt_ok = (decompressed == sample)
    print("  original length:   " + str(len(sample)))
    print("  compressed length: " + str(len(compressed)))
    print("  round-trip ok:     " + str(rt_ok))
    if not rt_ok:
        ok = False
    print()

    # --- Fingerprint ---
    fingerprint_input = "|".join(hashes)
    fingerprint = hashlib.sha3_256(fingerprint_input.encode()).hexdigest()

    print("=" * 60)
    print("PARITY FINGERPRINT")
    print("=" * 60)
    print("  " + fingerprint)
    print()
    print("  Run this on another device. If the fingerprint matches,")
    print("  cross-platform parity is proven.")
    print()

    if ok:
        print("RESULT: PARITY PASS")
    else:
        print("RESULT: PARITY FAIL")
    print()
    return ok


# ===========================================================================
# TEST 2: PERSISTENCE — save, then reload after app restart
# ===========================================================================
def _make_tag(key, value):
    msg = key.encode() + b"|" + value.encode()
    return hmac.new(KEYS["agent_key"], msg, hashlib.sha256).hexdigest()


def _read_db():
    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_db(data):
    d = os.path.dirname(DB_PATH)
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)


def test_save():
    print("=" * 60)
    print("TEST 2: PERSISTENCE — SAVE")
    print("=" * 60)
    print()
    print("  DB path: " + DB_PATH)
    print()

    data = _read_db()
    key = "test_key"
    value = "persistence works"

    data[key] = {
        "value": value,
        "tag": _make_tag(key, value),
        "hash": hashlib.sha3_256(value.encode()).hexdigest(),
    }
    _write_db(data)

    print("  SAVED: " + key + " = " + value)
    print()
    print("  Now fully quit this app (kill the process), reopen it,")
    print("  and run:")
    print("    python recallspection_test_suite.py load")
    print()


def test_load():
    print("=" * 60)
    print("TEST 2: PERSISTENCE — LOAD")
    print("=" * 60)
    print()
    print("  DB path: " + DB_PATH)
    print()

    if not os.path.exists(DB_PATH):
        print("  RESULT: FAIL — NO DB FOUND")
        print("  The file does not exist. The save did not persist.")
        print()
        return False

    data = _read_db()

    if "test_key" not in data:
        print("  RESULT: FAIL — MISSING KEY")
        print("  The file exists but the fact is gone.")
        print()
        return False

    entry = data["test_key"]
    stored_value = entry.get("value", "")
    stored_tag = entry.get("tag", "")
    stored_hash = entry.get("hash", "")

    expected_tag = _make_tag("test_key", stored_value)
    expected_hash = hashlib.sha3_256(stored_value.encode()).hexdigest()

    if not hmac.compare_digest(stored_tag, expected_tag):
        print("  RESULT: TAMPERED")
        print("  The stored HMAC does not match. The file was altered.")
        print()
        return False

    if not hmac.compare_digest(stored_hash, expected_hash):
        print("  RESULT: TAMPERED")
        print("  The stored hash does not match. The value was altered.")
        print()
        return False

    print("  VERIFIED: test_key = " + stored_value)
    print()
    print("  RESULT: PERSISTENCE PASS")
    print("  The fact survived app shutdown and reload.")
    print()
    return True


# ===========================================================================
# TEST 3: TAMPER — prove tampering is detected
# ===========================================================================
def test_tamper():
    print("=" * 60)
    print("TEST 3: TAMPER DETECTION")
    print("=" * 60)
    print()

    # In-memory store, using the same HMAC scheme
    store = {}

    def put(k, v):
        store[k] = {
            "value": v,
            "tag": _make_tag(k, v),
            "hash": hashlib.sha3_256(v.encode()).hexdigest(),
        }

    def get_with_status(k):
        if k not in store:
            return None, "missing"
        entry = store[k]
        expected_tag = _make_tag(k, entry["value"])
        if not hmac.compare_digest(entry["tag"], expected_tag):
            return None, "tampered"
        expected_hash = hashlib.sha3_256(entry["value"].encode()).hexdigest()
        if not hmac.compare_digest(entry["hash"], expected_hash):
            return None, "tampered"
        return entry["value"], "ok"

    # --- Store a fact ---
    put("clause_42", "The Contractor shall deliver within 30 days.")
    val, status = get_with_status("clause_42")
    print("  [1] Store + retrieve")
    print("      status: " + status)
    print("      value:  " + str(val))
    assert status == "ok", "expected ok"
    print("      PASS")
    print()

    # --- Missing key ---
    val, status = get_with_status("never_written")
    print("  [2] Never-written key")
    print("      status: " + status)
    assert status == "missing", "expected missing"
    print("      PASS")
    print()

    # --- Tamper with the value ---
    store["clause_42"]["value"] = "The Contractor shall deliver within 90 days."
    val, status = get_with_status("clause_42")
    print("  [3] Tampered value")
    print("      status: " + status)
    print("      value:  " + str(val))
    assert status == "tampered", "expected tampered"
    assert val is None, "value must be withheld"
    print("      PASS — tampering detected, value withheld")
    print()

    # --- Restore and tamper with the tag ---
    put("clause_42", "The Contractor shall deliver within 30 days.")
    store["clause_42"]["tag"] = "0" * 64
    val, status = get_with_status("clause_42")
    print("  [4] Tampered HMAC tag")
    print("      status: " + status)
    assert status == "tampered", "expected tampered"
    print("      PASS — tag mismatch detected")
    print()

    print("=" * 60)
    print("  RESULT: TAMPER PASS")
    print("  All three statuses (ok / tampered / missing) work correctly.")
    print("=" * 60)
    print()
    return True


# ===========================================================================
# DISPATCHER
# ===========================================================================
def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    cmd = args[0].lower() if args else "all"

    if cmd == "parity":
        test_parity()
    elif cmd == "save":
        test_save()
    elif cmd == "load":
        test_load()
    elif cmd == "tamper":
        test_tamper()
    elif cmd == "all":
        test_parity()
        test_tamper()
        print("Run 'python recallspection_test_suite.py save' next.")
        print()
    else:
        print("Unknown command: " + cmd)
        print("Use: parity | save | load | tamper | all")
        print()


if __name__ == "__main__":
    main()