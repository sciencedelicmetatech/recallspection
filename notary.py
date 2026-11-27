import hmac, hashlib, json, time
from mandate import Mandate
from store import NotaryStore, TamperError

class MachineNotary:
    def __init__(self, notary_secret: bytes, mandate: Mandate, store: NotaryStore):
        self.notary_secret = notary_secret
        # Verify mandate signature on load. Pasted version trusted mandate object.
        ok, why = mandate.verify(notary_secret)
        if not ok:
            raise Exception(f"Mandate refused on load: {why}")
        self.mandate = mandate
        self.store = store
        self.trade_counts = {}

    def evaluate_proposal(self, proposal: dict) -> dict:
        agent_id = proposal.get("agent_id")
        key = proposal.get("key")
        value = proposal.get("value")
        source = proposal.get("source")
        amount = proposal.get("amount", 0)

        # 1. Identity: in prod this must be mTLS / signed proposal, not just a field.
        # Field alone is forgeable. Here we keep check + note the gap.
        if agent_id != self.mandate.agent_id:
            return self._error("Identity Mismatch")

        # 2. Mandate: signature + expiry re-checked every call
        ok, why = self.mandate.verify(self.notary_secret)
        if not ok:
            return self._error(why)

        # 3. Allowed keys + denied sources
        allowed, reason = self.mandate.is_allowed(key, source)
        if not allowed:
            return self._error(f"Mandate Refused: {reason}")

        # 4. Limit + rate: pasted version had no limits, so $1M trade would pass
        if amount and amount > self.mandate.max_amount:
            return self._error(f"Err(Limit): {amount} > max {self.mandate.max_amount}")
        day = int(time.time() // 86400)
        ckey = (self.mandate.agent_id, day)
        if self.trade_counts.get(ckey, 0) >= self.mandate.max_trades_per_day:
            return self._error("Err(Rate): max trades per day reached")

        # 5. Write to vault
        try:
            proof_tag = self.store.commit_fact(key, value, writer_id=agent_id, source=source)
        except Exception as e:
            return self._error(str(e))

        self.trade_counts[ckey] = self.trade_counts.get(ckey, 0) + 1
        receipt = {
            "status": "Allow",
            "key": key,
            "agent_id": agent_id,
            "proof_tag": proof_tag,
            "anchor": self.store.memory.anchor(),
            "timestamp": int(time.time())
        }
        receipt["notary_signature"] = self._sign(receipt)
        return receipt

    def _sign(self, payload: dict) -> str:
        data = json.dumps(payload, sort_keys=True).encode()
        return hmac.new(self.notary_secret, data, hashlib.sha256).hexdigest()

    def _error(self, message: str) -> dict:
        return {"status": "Err", "message": message}
