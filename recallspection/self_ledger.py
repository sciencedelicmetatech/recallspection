import os
import sys
import hashlib
import hmac
import json
import time
from pathlib import Path

# The secret used to sign the ledger entries. 
# In production, this should be injected at runtime, but for self-checks, 
# a hardcoded salt prevents casual tampering.
LEDGER_HMAC_KEY = b"recallspection_v18_self_integrity_key"

def get_ledger_path() -> Path:
    """Returns the local append-only ledger path."""
    home = Path.home()
    ledger_dir = home / ".recallspection"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    return ledger_dir / "self.jsonl"

def sha256_file(filepath: str) -> str:
    """Computes the SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def make_tag(key: str, value: str, version: str) -> str:
    """Creates an HMAC tag for a ledger entry."""
    payload = f"{key}|{value}|{version}".encode()
    return hmac.new(LEDGER_HMAC_KEY, payload, hashlib.sha256).hexdigest()

def append_to_ledger(filepath: str, version: str):
    """Appends a new file hash to the local ledger."""
    file_hash = sha256_file(filepath)
    key = f"file:{os.path.basename(filepath)}:ver={version}"
    tag = make_tag(key, file_hash, version)
    
    entry = {
        "timestamp": int(time.time()),
        "key": key,
        "value": file_hash,
        "version": version,
        "tag": tag
    }
    
    ledger_path = get_ledger_path()
    with open(ledger_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[Recallspection] Ledger updated: {key} -> {file_hash[:8]}...")

def verify_self(filepath: str, expected_public_anchor: str):
    """
    Verifies the current file against the local ledger and the public anchor.
    Exits the process if tampering is detected.
    """
    if not os.path.exists(filepath):
        sys.exit(f"[Recallspection FATAL] File not found: {filepath}")
        
    actual_hash = sha256_file(filepath)
    ledger_path = get_ledger_path()
    
    if not ledger_path.exists():
        sys.exit("[Recallspection FATAL] Local ledger missing. Refusing to run unverified code.")
        
    last_entry = None
    with open(ledger_path, "r") as f:
        for line in f:
            if line.strip():
                last_entry = json.loads(line)
                
    if not last_entry:
        sys.exit("[Recallspection FATAL] Ledger is empty.")
        
    # 1. Verify the HMAC tag of the latest ledger entry
    expected_tag = make_tag(last_entry["key"], last_entry["value"], last_entry["version"])
    if not hmac.compare_digest(expected_tag, last_entry["tag"]):
        sys.exit("[Recallspection FATAL] Ledger HMAC tag invalid. The ledger has been tampered with.")
        
    # 2. Verify the current file matches the ledger
    if not hmac.compare_digest(actual_hash, last_entry["value"]):
        sys.exit(
            f"[Recallspection FATAL] CODE TAMPER DETECTED!\n"
            f"Expected: {last_entry['value']}\n"
            f"Actual:   {actual_hash}\n"
            f"Git may have been force-pushed. Refusing to execute."
        )
        
    # 3. Verify the public anchor (prevents the attacker from just updating the local ledger)
    # The public anchor is a hash you post in your README, tweet, or paper.
    if expected_public_anchor and not hmac.compare_digest(last_entry["value"], expected_public_anchor):
        sys.exit(
            f"[Recallspection FATAL] PUBLIC ANCHOR MISMATCH!\n"
            f"Ledger tip: {last_entry['value']}\n"
            f"Expected anchor: {expected_public_anchor}\n"
            f"The local ledger has been rolled forward by an attacker."
        )
        
    print(f"[Recallspection] ✅ Self-integrity verified: {last_entry['key']}")