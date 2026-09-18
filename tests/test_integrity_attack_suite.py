#!/usr/bin/env python3
"""
ExactMemory Integrity Attack Suite - CI version
Embeds patched ExactMemory v3.0.1 core. No GitHub clone required.
Patch: get_with_status() returns "tampered" not "missing" when key in per_key_max but absent from store.
"""

import copy
import hashlib
import hmac
import json
import os
import time
import zlib
from typing import Dict, Optional, Tuple

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

def sha3_256_hex(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()

class ExactMemoryError(Exception): pass
class TamperError(ExactMemoryError): pass
class RollbackError(ExactMemoryError): pass
class LogCompromisedError(ExactMemoryError): pass
class MissingKeyError(ExactMemoryError): pass

class TransparencyLog:
    def __init__(self, log_path: str, require_log: bool = True):
        self.log_path = log_path
        self.require_log = require_log
    def _canonical(self, obj) -> bytes:
        return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
    def append(self, counter: int, max_version: int, container_hash: str) -> dict:
        prev_hash = "0" * 64
        last = self._last_entry()
        if last:
            prev_hash = last['chain_hash']
        entry = {
            'timestamp': int(time.time()),
            'counter': counter,
            'max_version': max_version,
            'container_hash': container_hash,
            'prev_hash': prev_hash,
        }
        chain_hash = sha3_256_hex((prev_hash + self._canonical(entry).decode()).encode())
        entry['chain_hash'] = chain_hash
        try:
            with open(self.log_path, 'a') as f:
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(self._canonical(entry).decode() + "\n")
                f.flush()
                os.fsync(f.fileno())
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        return entry
    def _last_entry(self):
        if not os.path.exists(self.log_path):
            return None
        try:
            with open(self.log_path, 'r') as f:
                lines = [l.strip() for l in f if l.strip()]
                return json.loads(lines[-1]) if lines else None
        except Exception:
            return None
    def verify_chain(self):
        if not os.path.exists(self.log_path):
            if self.require_log:
                return False, "Log file missing but require_log=True"
            return True, "No log yet (opt-in)"
        try:
            with open(self.log_path, 'r') as f:
                lines = [l.strip() for l in f if l.strip()]
        except Exception as e:
            return False, "Cannot read log: " + str(e)
        prev_hash = "0" * 64
        for i, line in enumerate(lines):
            entry = json.loads(line)
            if entry.get('prev_hash') != prev_hash:
                return False, f"Line {i} prev_hash mismatch"
            entry_copy = {k: v for k, v in entry.items() if k != 'chain_hash'}
            recomputed = sha3_256_hex((prev_hash + self._canonical(entry_copy).decode()).encode())
            if not hmac.compare_digest(recomputed, entry['chain_hash']):
                return False, f"Line {i} chain_hash invalid"
            prev_hash = entry['chain_hash']
        return True, f"Chain OK - {len(lines)} entries"
    def get_tip(self):
        return self._last_entry()

class ExactMemory:
    VERSION = "3.0.1"
    def __init__(self, keys, container_key_id='container', ttl_seconds=None,
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
    def _canonical(self, record: dict) -> bytes:
        return json.dumps(record, sort_keys=True, separators=(',', ':')).encode()
    def _make_tag(self, key_id: str, record: dict) -> bytes:
        rec = record.copy()
        rec['_key_hash'] = sha3_256_hex(rec['key'].encode())
        rec['_key_id_hash'] = sha3_256_hex(key_id.encode())
        return hmac.new(self.keys[key_id], self._canonical(rec), hashlib.sha256).digest()[:32]
    def put(self, k, v, key_id=None):
        kid = key_id or next(iter([kk for kk in self.keys if kk != self.container_key_id]))
        self.counter += 1
        record = {
            'key': k, 'value': v, 'key_id': kid,
            'version': self.counter, 'timestamp': int(time.time()),
            'nonce': os.urandom(16).hex()
        }
        tag = self._make_tag(kid, record)
        self.store[k] = (record, tag)
        self.max_version = self.counter
        self.per_key_max[k] = self.counter
        self.tombstones.pop(k, None)
        return record
    def get_with_status(self, k) -> Tuple[Optional[object], str]:
        if k in self.tombstones:
            rec, tag = self.tombstones[k]
            if not hmac.compare_digest(tag, self._make_tag(rec['key_id'], rec)):
                return None, "tampered"
            return None, "tombstoned"
        if k not in self.store:
            if k in self.per_key_max:
                return None, "tampered"
            return None, "missing"
        rec, tag = self.store[k]
        if not hmac.compare_digest(tag, self._make_tag(rec['key_id'], rec)):
            return None, "tampered"
        if rec['version'] < self.per_key_max.get(k, 0):
            return None, "tampered"
        if self.ttl is not None and int(time.time()) - rec['timestamp'] > self.ttl:
            return None, "expired"
        return rec['value'], "ok"
    def delete(self, k, key_id=None):
        kid = key_id or next(iter([kk for kk in self.keys if kk != self.container_key_id]))
        self.counter += 1
        tomb = {
            'key': k, 'deleted': True, 'version': self.counter,
            'key_id': kid, 'timestamp': int(time.time()),
            'nonce': os.urandom(16).hex()
        }
        tag = self._make_tag(kid, tomb)
        self.tombstones[k] = (tomb, tag)
        self.store.pop(k, None)
        self.max_version = self.counter
        self.per_key_max[k] = self.counter

class NaiveStore:
    def __init__(self):
        self.store = {}
    def put(self, k, v, **kwargs):
        self.store[k] = v
    def get_with_status(self, k):
        if k in self.store:
            return self.store[k], "ok"
        return None, "missing"
    def delete(self, k):
        self.store.pop(k, None)

def classify(store, key, expected):
    try:
        val, status = store.get_with_status(key)
        if status in ("tampered", "tombstoned", "expired"):
            return "detected"
        if status == "missing":
            return "missing"
        if val == expected:
            return "correct"
        return "silent_wrong"
    except Exception:
        return "detected"

def attack_none(mem): return set()
def attack_bitflip_hmac_tag(mem):
    attacked=set()
    for i,k in enumerate(list(mem.store.keys())[:20]):
        if i%2!=0: continue
        try:
            rec,tag=mem.store[k]
            bad=bytearray(tag); bad[0]^=0xFF
            mem.store[k]=(rec,bytes(bad)); attacked.add(k)
        except: continue
    return attacked
def attack_payload_rewrite(mem):
    attacked=set()
    for k in list(mem.store.keys())[:15]:
        try:
            rec,tag=mem.store[k]; rec=copy.deepcopy(rec); rec["value"]={"data":"ATTACKER_CONTROLLED"}
            mem.store[k]=(rec,tag); attacked.add(k)
        except: continue
    return attacked
def attack_replay_old_version(mem):
    attacked=set()
    for k in list(mem.store.keys())[:10]:
        try:
            old=copy.deepcopy(mem.store[k]); mem.put(k,{"replayed":True},key_id="agent_key"); mem.store[k]=old; attacked.add(k)
        except: continue
    return attacked
def attack_direct_removal(mem):
    attacked=set()
    for k in list(mem.store.keys())[:10]:
        try: del mem.store[k]; attacked.add(k)
        except: continue
    return attacked
def attack_wrong_agent_key(mem):
    mem.keys["agent_key"]=b"wrong-agent-key-32-bytes-long!!!"; return set(mem.store.keys())

def run_suite(factory, is_exact):
    facts={f"key_{i}":{"id":i,"data":f"value_{i}"} for i in range(40)}
    attacks=[("none",attack_none),("bitflip_hmac_tag",attack_bitflip_hmac_tag),("payload_rewrite",attack_payload_rewrite),("replay_old_version",attack_replay_old_version),("direct_store_removal",attack_direct_removal),("wrong_agent_key",attack_wrong_agent_key)]
    results={}
    for aname,afn in attacks:
        store=factory()
        for k,v in facts.items(): store.put(k,v,key_id="agent_key")
        if is_exact: attacked=afn(store)
        else:
            attacked=set()
            if aname=="bitflip_hmac_tag":
                for k in list(store.store.keys())[0:20:2]: store.store[k]="TAMPERED"; attacked.add(k)
            elif aname=="payload_rewrite":
                for k in list(store.store.keys())[:15]: store.store[k]={"data":"ATTACKER_CONTROLLED"}; attacked.add(k)
            elif aname=="replay_old_version":
                for k in list(store.store.keys())[:10]: old=copy.deepcopy(store.store[k]); store.put(k,{"replayed":True}); store.store[k]=old; attacked.add(k)
            elif aname=="direct_store_removal":
                for k in list(store.store.keys())[:10]: del store.store[k]; attacked.add(k)
        tp=fn=0
        for k,expected in facts.items():
            outcome=classify(store,k,expected); is_att=k in attacked
            if is_att:
                if outcome=="detected": tp+=1
                else: fn+=1
        n_att=len(attacked); dr=(tp/n_att) if n_att else None; sfr=(fn/n_att) if n_att else None
        results[aname]={"attacked":n_att,"tp":tp,"fn":fn,"DR":dr,"SFR":sfr}
    return results

def test_exactmemory_integrity():
    KEYS={"agent_key":b"bench-agent-key-32-bytes-long!!!","container":b"bench-container-key-32-bytes!!!!"}
    exact=run_suite(lambda: ExactMemory(keys=KEYS,container_key_id="container",require_log=False),True)
    # All attacks must be 100% DR except none
    for aname in ["bitflip_hmac_tag","payload_rewrite","replay_old_version","direct_store_removal","wrong_agent_key"]:
        dr=exact[aname]["DR"]
        assert dr==1.0, f"{aname} DR {dr} != 100%"
    # Naive must fail
    naive=run_suite(lambda: NaiveStore(),False)
    for aname in ["bitflip_hmac_tag","payload_rewrite","replay_old_version","direct_store_removal"]:
        sfr=naive[aname]["SFR"]
        assert sfr==1.0, f"naive {aname} should be 100% silent failure, got {sfr}"

if __name__=="__main__":
    test_exactmemory_integrity()
    print("ExactMemory integrity: 100% DR verified")
