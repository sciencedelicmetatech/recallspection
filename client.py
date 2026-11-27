import json

class NotaryClient:
    def __init__(self, agent_id: str, transport):
        """
        transport is a function that takes JSON string and returns JSON string.
        Agent never gets Notary object. Pasted version passed Notary object directly,
        which means agent could do notary.notary_secret in Python. That breaks the boundary.
        Here agent only gets a pipe.
        """
        self.agent_id = agent_id
        self._transport = transport

    def propose(self, key: str, value: str, source: str, amount: float = 0) -> dict:
        proposal = {
            "agent_id": self.agent_id,
            "key": key,
            "value": value,
            "source": source,
            "amount": amount
        }
        # Serialize: boundary is JSON, not object reference
        resp_json = self._transport(json.dumps(proposal))
        return json.loads(resp_json)
