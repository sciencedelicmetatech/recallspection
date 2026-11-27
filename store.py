import hmac, hashlib, json

class TamperError(Exception):
    pass

def _hmac(secret: bytes, msg: bytes) -> str:
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()

class ExactStore:
    """Real store. Pasted version imported exactmemory_recallspection which does not exist in this repo."""
    def __init__(self, secret: bytes):
        self.secret = secret
        self.data = {}
        self.ledger = []
        self.head = "GENESIS"

    def _tag(self, k, value, version):
        msg = json.dumps({"k": k, "v": value, "ver": version}, sort_keys=True).encode()
        return _hmac(self.secret, msg)

    def put(self, k, value):
        version = self.data.get(k, {}).get("version", 0) + 1
        tag = self._tag(k, value, version)
        self.data[k] = {"value": value, "version": version, "tag": tag}
        entry = {"k": k, "ver": version, "tag": tag, "prev": self.head}
        entry_hash = _hmac(self.secret, json.dumps(entry, sort_keys=True).encode())
        entry["hash"] = entry_hash
        self.ledger.append(entry)
        self.head = entry_hash
        return tag

    def get(self, k):
        if k not in self.data:
            raise TamperError(f"Err(Missing): {k} not found")
        rec = self.data[k]
        expect = self._tag(k, rec["value"], rec["version"])
        if not hmac.compare_digest(expect, rec["tag"]):
            raise TamperError(f"Err(Tamper): {k} tag mismatch")
        return rec["value"]

    def anchor(self):
        return self.head

class NotaryStore:
    def __init__(self, secret: bytes):
        self.memory = ExactStore(secret)

    def commit_fact(self, key: str, value: str, writer_id: str, source: str) -> str:
        # writer_id / source already checked by Notary before this is called
        tag = self.memory.put(key, value)
        return tag

    def tamper_for_demo(self, k, evil):
        if k in self.memory.data:
            self.memory.data[k]["value"] = evil
