import json, time
from mandate import Mandate
from store import NotaryStore
from notary import MachineNotary
from client import NotaryClient

SECRET = b"super-secret-notary-signing-key-123"
mandate = Mandate(
    agent_id="logistics-bot-01",
    allowed_keys=["shipment_100", "shipment_101"],
    denied_sources=["email"],
    max_amount=50.0,
    max_trades_per_day=10,
    expiry=int(time.time()) + 3600,
).sign(SECRET)

store = NotaryStore(SECRET)
notary = MachineNotary(notary_secret=SECRET, mandate=mandate, store=store)

# Transport: JSON pipe, not object reference. In prod this is HTTP / gRPC.
def transport(proposal_json: str) -> str:
    proposal = json.loads(proposal_json)
    result = notary.evaluate_proposal(proposal)
    return json.dumps(result)

agent = NotaryClient(agent_id="logistics-bot-01", transport=transport)

print("TEST 1 Allowed:", agent.propose(key="shipment_100", value="delivered", source="tool_verified", amount=40))
print("TEST 2 Mandate denied key:", agent.propose(key="kyc_ahmad", value="exempt", source="user_prompt", amount=10))
print("TEST 3 Denied source:", agent.propose(key="shipment_100", value="lost", source="email", amount=10))
print("TEST 4 Over limit:", agent.propose(key="shipment_100", value="delivered", source="tool_verified", amount=999))

# Tamper test: edit raw store without updating tag
store.tamper_for_demo("shipment_100", "HACKED")
# Next read via Notary should still be blocked on write path? Show direct tamper detection:
try:
    print("Tamper read:", store.memory.get("shipment_100"))
except Exception as e:
    print("TEST 5 Tamper detected on read:", e)
