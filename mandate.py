import hmac, hashlib, json, time
from dataclasses import dataclass, asdict, field

def _hmac(secret: bytes, msg: bytes) -> str:
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()

@dataclass
class Mandate:
    # Pasted version was right: allowed_keys + denied_sources
    # Missing: signature, expiry, limits. Without those, mandate itself can be edited.
    agent_id: str
    allowed_keys: list
    denied_sources: list = field(default_factory=list)
    max_amount: float = 50.0
    max_trades_per_day: int = 3
    expiry: int = 0
    version: int = 1
    signature: str = ""

    def canonical(self):
        d = asdict(self)
        d.pop("signature", None)
        return json.dumps(d, sort_keys=True).encode()

    def sign(self, secret: bytes):
        self.signature = _hmac(secret, self.canonical())
        return self

    def verify(self, secret: bytes):
        expect = _hmac(secret, self.canonical())
        if not hmac.compare_digest(expect, self.signature):
            return False, "Err(Tamper): mandate signature mismatch"
        if self.expiry and time.time() > self.expiry:
            return False, "Err(Expired): mandate expired"
        return True, "ok"

    def is_allowed(self, action_key: str, source: str):
        if source in self.denied_sources:
            return False, f"Source '{source}' is globally denied"
        if self.allowed_keys != ["*"] and action_key not in self.allowed_keys:
            return False, f"Key '{action_key}' not in mandate allowed list"
        return True, "Allowed"
