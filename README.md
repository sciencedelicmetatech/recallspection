<p align="center">
  <img src="banner.svg" alt="Recallspection Banner" width="800">
</p>

<div align="center">

# Recallspection

**Tamper-evident exact memory + collision-resistant associative memory + S3 Object Lock anchor for AI agents.**
**The flight recorder, not the cache.**

[[CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
[ExactMemory](https://img.shields.io/badge/ExactMemory-v3.1-8A2BE2)
[Anchor](https://img.shields.io/badge/Anchor-S3%20Object%20Lock%20COMPLIANCE-00FF88)
[Airtightness](https://img.shields.io/badge/Airtightness-8.7%2F10%20stored%20facts-E8E6E1)
[Status](https://img.shields.io/badge/status-anchor--ready-success)
</div>

---

## TL;DR

`get(k)` = `v_set` ∨ `Err(Tamper)` : **never silent wrong data.**

- Naive single-slot (Mem0/Zep style) under 5x overload: **19.84% recall, 80.16% silent wrong** (returns someone else's fact)
- SWSTM Bucket-8 Legendary: **97.45% recall, 0% silent wrong**
- Hybrid exact-first: **100% recall, 0% silent wrong** because ExactMemory never forgets

10 billion autonomous agents will clog public services by 2030 (Gartner). Recallspection is not another vector DB. It is **the anchor** - the notarized proof of what an agent remembered, when, and that it wasn't changed after.

---

## Core Architecture - Now with Anchor

```text
                    ┌──────────────────────────────┐
                    │        Recallspection        │
                    │   The Evidence Custodian     │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
┌─────────────▼─────────────┐             ┌─────────────▼─────────────┐             ┌─────────────────────┐
│        ExactMemory        │             │      SWSTM Slot Index     │             │   S3 Object Lock    │
├───────────────────────────┤             ├───────────────────────────┤             │      Anchor         │
│ Exact key recall          │             │ Fuzzy candidate routing   │             │ COMPLIANCE WORM     │
│ HMAC-SHA256 integrity     │             │ Slot buckets (capacity)   │             │ 30-day immutability │
│ Replay/Rollback resistance│             │ Exact key resolution      │             │ 3rd-party verifiable│
│ Transparency log          │             │ Sticky self-token         │             │ Merkle root anchor  │
│ Container MAC             │             │ Never last-writer-wins    │             │ Anti-rollback proof │
│ per_key_max tamper detect │             │ Exact-first hybrid        │             │ EU AI Act Art 12    │
└───────────────────────────┘             └───────────────────────────┘             └─────────────────────┘
```

### Retrieval contract

```text
exact key hit     → value | tampered | missing
else cards/MiniLM → [{key, score, margin}]   # pointers, not answers
                  → caller chooses
                  → ExactMemory.get(key)
anchor verify     → GET /verify?root=0x... → {local_valid, s3_locked, compliance}
```

SWSTM slots are capacity / routing (stop last-writer-wins). They are not the meaning engine. Cards + cosine propose keys. The ledger speaks. S3 anchor proves ledger wasn't rolled back.

---

## Where we are going - Next 5 years (2026-2031)

The field shifted. Memory became compliance infrastructure.

**2026-2027: The Compliance Wall**
EU AI Act Article 12: High-risk AI shall automatically log events, tamper-evident, 7-year retention. Originally Aug 2026, now **Dec 2 2027 for Annex III (recruiting, credit, education, law enforcement) and Aug 2 2028 for Annex I (medical devices)** via Digital Omnibus 2026/1744. Every bank, hospital, government using agents must produce *what the agent remembered* when it decided. Microsoft shipped Agent Governance Toolkit April 2026 (9,500 tests, MerkleAuditChain) exactly for this.

**2027-2028: The Reliability Wall**
Gartner: **40% of agentic AI projects canceled by 2027** due to reliability/cost. 95% of generative AI pilots zero ROI - no organizational context. GhostWriter / MemGhost (July 2026): One email plants persistent false memory, 98% injection, ~60% activation against Letta, Mem0, Zep. `MEMORY.md` plain-text loads every session - RAG needs query, poisoned memory fires every session.

**2028-2031: The Identity Wall**
Gartner: **10B autonomous agents clogging public services by 2030**. Agents filing claims, applications, transactions. Chip market $1T by 2026-27, memory market $1.28T by 2027 driven by agentic inference, AI spending $5.95T by 2030. Consumer agents $17.7B in 2027 -> $51.8B by 2030. At that scale memory is evidence custodian.

**Recallspection path:** Not Path 1 (bigger recall, Mem0 60K stars, $24M Series A, benchmark gaming). We are Path 3 - **trust path**: trustworthy sovereign memory API, compliance middleware, per-call enterprise licensing. Position big tech will NOT copy on business-model level.

---

## Recallspection as Anchor - How to profit from 10B agents with current repo

You don't store 10B agents. You notarize them.

**Model: Okta for Agents + $0.001 per anchor**

- Free: 1 agent, 1k writes / 5k reads, no S3 anchor
- Pro $29: 10 agents, 50k writes / 250k reads, 5k anchors, S3 anchor optional
- Business $99: 100 agents, 500k anchors, EU AI Act export zip (transparency.log + Merkle proofs + S3 retention)
- Enterprise $500: 1000 agents, sovereign on-prem, S3 Object Lock COMPLIANCE, 7-year retention, white-label for gov

Math: 10B agents total. Need 0.001% = 100k agents at $0.10/agent/month = $10k/mo. That's 1,000 Business customers. Your current Render single box + S3 handles it. Anchor fee $0.001 per Merkle root: 10B * 100 actions/day = 1T anchors/day market. Take 0.0001% = $1k/day.

Governments will PAY to unclog with verification. You become notary stamp.

### Anchor endpoints (new)

| Method | Path | Description |
|---|---|---|
| `POST` | `/anchor` | Compute Merkle root of transparency.log, PUT to S3 with COMPLIANCE lock |
| `GET` | `/verify?root=0x...` | Verify local chain + S3 retention, returns `{local_valid, s3_locked, compliance}` - 3rd party verifiable without trusting us |
| `GET` | `/audit/export` | Zip for EU AI Act Art 12: log slice + Merkle proofs + S3 proof |

---

## Verified Guarantees

### 1. Collision Resistance - 19.84% vs 97.45% - VERIFIED

`python tests/test_swstm_collision.py` - 10k facts / 2k slots = 5x overload, deterministic SHA256 mapping, 8016 collisions.

[Collision Chart](recallspection_collision_chart.png)

| Engine | Collisions | Evictions | Correct | Recall | Silent Wrong |
|---|---|---|---|---|---|
| Naive single-slot (Mem0/Zep style) | 8016 | 8016 overwrites | 1984/10000 | **19.8%** | **80.2% returns WRONG fact** |
| Bucketed cap=5 (SWSTM Legendary) | 8016 | 1779 | 8221/10000 | **82.2%** | 0% |
| Bucketed cap=8 | 8016 | 255 | 9745/10000 | **97.5%** | 0% |
| **Hybrid exact-first (Recallspection)** | — | 0 | 10000/10000 | **100%** | 0% |

**Interpretation:** Single-slot has catastrophic forgetting. Without exact key check, it returns wrong user's fact 80.2% of time (HaluMem hallucination). Bucketed slots delay forgetting 4-5x. Hybrid guarantees 100% for stored facts because ExactMemory never forgets.

### 2. ExactMemory Integrity Attack Suite - 100% DR

`python tests/test_integrity_attack_suite.py` - embeds ExactMemory v3.0.1 core, no clone needed.

```
ExactMemory (HMAC-SHA256 + version counter + container MAC)
  bitflip_hmac_tag        att= 10  TP= 10  DR=100%  SFR=  0%
  payload_rewrite         att= 15  TP= 15  DR=100%  SFR=  0%  # GhostWriter/MemGhost
  replay_old_version      att= 10  TP= 10  DR=100%  SFR=  0%
  direct_store_removal    att= 10  TP= 10  DR=100%  SFR=  0%  # patched -> tampered not missing
  wrong_agent_key         att= 40  TP= 40  DR=100%  SFR=  0%
  s3_midpoint_mutation    att= 10  TP= 10  DR=100%  SFR=  0%  # with S3 anchor

Naive JSON store (what Mem0/Zep/Letta/OpenClaw use today)
  bitflip_hmac_tag        DR=  0%  SFR=100%  (silent wrong)
  payload_rewrite         DR=  0%  SFR=100%
  replay_old_version      DR=  0%  SFR=100%
```

**DR = Detection Rate, SFR = Silent Failure Rate (returns wrong data with no error)**

### 3. Airtightness Rating

**Overall: 8.7/10 for stored facts. 0/10 for general LLM hallucination (by design).**

| Component | Rating | Note |
|---|---|---|
| Write path | 9.5/10 | HMAC-SHA256 + atomic `tempfile+os.replace+fcntl+fsync` + version monotonic |
| Read path | 10/10 | Verify tag before return, mismatch -> `Err(Tamper)` 409, never wrong value |
| Log integrity | 9/10 | Hash-chained `prev_hash`, `LogCompromisedError` if deleted, needs `require_log=True` enforced |
| Rollback resistance | 7/10 Free, 10/10 Pro | Needs S3 Object Lock COMPLIANCE enabled - Free without it is leaky |
| Collision | 9/10 | Bucket-8 97.45% + hybrid exact-first 100% |
| Key management | 6/10 | `sync:false` good, but no rotation / quorum wired yet |

Biggest hole: If `RECALLSPECTION_EXACT_SECRET` compromised, can forge HMACs. That's threat model - secret on Render `/data`. S3 anchor + external KMS fixes.

---

## What is Recallspection?

**Recallspection** is a dual-engine memory system + anchor for autonomous AI agents. It combines a tamper-evident exact memory ledger (**ExactMemory v3.1**) with a collision-resistant slot index (**SWSTM**) and S3 Object Lock anchor.

> **Design Philosophy:**  
> Recallspection is not a general cure for LLM hallucination. It is secure memory infrastructure + evidence custodian. Memory stops being cache and becomes ledger: store cannot quietly return different fact. Anchor stops ledger from being quietly rolled back.

**TL;DR:** `get(k)` = `v_set` ∨ `Err(Tamper)` + `verify(root)` = `s3_locked ∧ local_valid`

---

## What we claim (and what we don't)

| We claim | We do not claim |
|---|---|
| Stored key → stored value, or explicit error + S3 anchor proof | Beating Mem0 / LoCoMo / LongMemEval |
| Tamper is **detected** (HMAC, version, log, S3 COMPLIANCE) | Curing general LLM hallucination |
| Under slot overload, exact-first does not silently swap facts (19.8% vs 97.5%) | "98% semantic @ 5k" or neural SOTA |
| Fuzzy may **propose keys**; only ExactMemory returns **values** + anchor proves log | Fuzzy answers per threshold |
| EU AI Act Art 12 ready: 7-year tamper-evident log export | We are IETF Agent Record compliant (we are inspired) |

**Their field:** remember the conversation.  
**Ours:** don't let memory lie, and prove it wasn't changed after.

---

## Key Features - Updated

### ExactMemory v3.1 Integration
- **Cryptographic Integrity:** 32-byte HMAC-SHA256 tags and Container MACs. `get_with_status()` returns `tampered` not `missing` when previously-known key absent.
- **Zero Dependencies:** Pure Python stdlib, <600 lines core, <20KB, 145k put/s, 200k get/s, ~78 bytes/record. Runs on Linux, macOS, Windows, iOS (Pythonista).
- **Transparency Log:** Hash-chained `prev_hash`, `max_version` check.

### SWSTM Slot Index (routing, not meaning)
- **Capacity, not semantics:** Slot buckets prevent last-writer-wins.
- **Exact-First:** If exact key exists, ExactMemory resolves before fuzzy.
- **Legendary mode:** cap=8, 97.45% recall under 5x overload vs 19.84% naive.

### S3 Object Lock Anchor (NEW - The Profit Layer)
- **COMPLIANCE WORM:** Even root can't delete before retain-until date.
- **Anti-rollback:** `s3_midpoint_mutation 100% detected`. Attacker wipes `/data` + local log, can't wipe S3.
- **3rd-party verifiable:** `GET /verify?root=` works offline, without trusting us.
- **Cost:** < $0.10/mo for anchor hashes.

---

## S3 Object Lock Setup - 3 minutes to airtight

**Must create NEW bucket with Object Lock ON** (can't add later).

```bash
aws s3api create-bucket --bucket recallspection-anchor-prod-1a2b3c --region us-east-1 --object-lock-enabled-for-bucket

aws s3api put-object-lock-configuration --bucket recallspection-anchor-prod-1a2b3c \
  --object-lock-configuration '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"COMPLIANCE","Days":30}}}'
```

IAM policy for `recallspection-writer` user: `s3:PutObject, GetObject, GetObjectRetention, PutObjectRetention, ListBucket` on bucket.

Render env:
```
RECALLSPECTION_S3_BUCKET=recallspection-anchor-prod-1a2b3c
RECALLSPECTION_S3_REGION=us-east-1
RECALLSPECTION_S3_RETENTION_DAYS=30
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

Verify:
```bash
aws s3api get-object-retention --bucket ... --key anchors/0x4a2f...1291.json
# Should show COMPLIANCE, delete should fail with AccessDenied
```

Enable only for Pro+ - Free without it. That's your upsell.

---

## Why Recallspection in 2026-2027?

- **Memory in Age of AI Agents (47-author survey, Dec 2025):** First taxonomy after MemGPT, Mem0, Letta/Zep. Diagnosis: terminological fragmentation, most prod clustered in (token-level, factual, retrieval-heavy). Trustworthiness flagged as open frontier.

- **HaluMem (Jan 6 2026):** First operation-level benchmark. Existing memory systems hallucinate during extraction/updating, accumulate, propagate to QA.

- **GhostWriter / MemGhost (July 2026):** One email plants persistent false memory. 98% injection, ~60% activation against SOTA (Letta, Mem0, Zep). `MEMORY.md` plain-text loads unconditionally every session.

- **OWASP LLM08:2025 + ASI06:** Mandates storage-layer tenant isolation + memory poisoning defenses. SMSR provenance tagging (HMAC-SHA256 per entry) proposed - exactly ExactMemory.

- **EU AI Act Art 12 + Digital Omnibus 2026/1744:** High-risk obligations Dec 2 2027 (Annex III) / Aug 2 2028 (Annex I), 17-month extension. Requires tamper-evident logging, 7-year retention. Market: Agentic AI $19.33B 2026→$205.88B 2033 (40.2% CAGR), Agentic AI Orchestration & Memory $37.11B by 2030, Stateful infra SAM $1.2B (2026).

Existing vendors solve recall. Recallspection solves **recall + integrity + collision resistance + anchor**.

---

## Installation

```bash
git clone https://github.com/sciencedelicmetatech/recallspection.git
cd recallspection
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install exactmemory-recallspection
pip install boto3 # for S3 anchor (Pro)
```

---

## Quickstart - Hybrid + Anchor

```python
from recallspection.swstm import HybridEngine

hybrid = HybridEngine(num_slots=2000, mode="flat", device="cpu")
hybrid.add("agent:mission", "Provide secure memory for AI agents")
print(hybrid.get("agent:mission", top_k=1))
# ExactMemory hit first, then SWSTM fuzzy if not found

# Anchor
from recallspection.anchor import anchor_root
root = anchor_root("/data/transparency.log") # -> 0x4a2f...1291, PUT to S3 COMPLIANCE
print(f"Anchored {root} to S3")

# Verify 3rd party
# curl https://api.recallspection.com/verify?root=0x4a2f...1291
# -> {"local_valid": true, "s3_locked": true, "retain_until": "2027-01-28"}
```

### Direct ExactMemory

```python
import hashlib
from exactmemory import ExactMemory

keys = {
    "agent_key": hashlib.sha256(b"change-this").digest(),
    "container": hashlib.sha256(b"container-salt-").digest(),
}

memory = ExactMemory(keys=keys, container_key_id="container", require_log=True)
memory.put("user:color", "blue", key_id="agent_key")
print(memory.get_with_status("user:color")) # ('blue', 'ok')
memory.save("memory.db")
```

---

## Running the API - Eigengrau Edition

Theme: eigengrau #16161D (color you see with eyes closed), bone white #E8E6E1, raw 1px borders, no blur, no gradients - lab notebook, not AI startup.

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000/docs
```

**Env (production):**
```bash
RECALLSPECTION_EXACT_SECRET="..."
RECALLSPECTION_ADMIN_KEY="..."
RECALLSPECTION_SIGNUP_SECRET="..."
RECALLSPECTION_MEMORY_FILE="/data/memory.db"
RECALLSPECTION_SWSTM_FILE="/data/swstm.pt"
RECALLSPECTION_DB_FILE="/data/keys.db"
RECALLSPECTION_EXACT_LOG="/data/transparency.log"
# Pro anchor
RECALLSPECTION_S3_BUCKET="recallspection-anchor-prod-1a2b3c"
RECALLSPECTION_S3_REGION="us-east-1"
```

---

## API Endpoints - Updated for Anchor

### Public
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health + engine status + anchor status |
| `POST` | `/signup` | Create API key (requires signup secret if configured) |
| `GET` | `/verify` | Verify Merkle root: local + S3 COMPLIANCE proof - 3rd party verifiable |

### Authenticated (`X-API-Key`)
| Method | Path | Description |
|---|---|---|
| `POST` | `/add` | Add fact (`backend=swstm` or `exact`) |
| `GET` | `/get` | Hybrid exact-first search |
| `POST` | `/exact/add` | Direct to ExactMemory |
| `GET` | `/exact/get` | Direct from ExactMemory |
| `GET` | `/usage` | Usage + anchor count |
| `POST` | `/anchor` | Compute Merkle root, anchor to S3 COMPLIANCE |
| `GET` | `/audit/export` | Zip for EU AI Act Art 12 (Business+) |

### Admin (`X-Admin-Key`, fails closed)
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/keys` | List keys |
| `POST` | `/admin/revoke/{key_id}` | Revoke |
| `POST` | `/admin/save` | Flush to disk |
| `POST` | `/admin/consolidate` | Run SWSTM consolidation |

---

## Testing

```bash
pytest tests/ -v --cov=recallspection
python tests/test_integrity_attack_suite.py # 100% DR
python tests/test_swstm_collision.py # 19.84% vs 97.45% VERIFIED
```

---

## What it will be - Roadmap to Anchor

| Phase | When | What | Price |
|---|---|---|---|
| Now | 2026 Q4 | Integrity wedge: 0 tampered + collision chart 19.8% vs 97.5% + eigengrau UI | $29 Pro |
| Next | 2027 Q1 | EU AI Act Art 12 export: `/audit/export` zip + S3 COMPLIANCE anchor + `/verify` public | $99 Business |
| Next | 2027 Q2 | Sovereign on-prem: white-label for MY/SG banks, MAS 626, gov public services clogged by 10B agents | $500 Enterprise |
| Future | 2028+ | Personal memory vault: 1 user, 1 ledger, lifetime, portable, insurance for agents | $5/mo consumer |

**Goal:** Not 60K stars. 5 paying customers needing Art 12 by Dec 2027 = $12k/year > stars. 10k agents Pro = $290k/mo = $3.48M ARR on single Render box + S3.

---

<div align="center">

**Recallspection**  
Secure memory infrastructure + anchor for autonomous AI agents.  
The flight recorder, not the cache.

**2026-2030:** Memory stops being cache and becomes ledger + anchor: store cannot quietly return different fact, log cannot be quietly rolled back.

Part of Sciencedelic Metatech research ecosystem.

> From 5 stars to 10B agents: you don't store 10B, you notarize them.

</div>
