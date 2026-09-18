<p align="center">
  <img src="banner.svg" alt="Recallspection Banner" width="800">
</p>

<div align="center">

# Recallspection

**Tamper-evident exact memory + collision-resistant neural associative memory for AI agents.**

[[CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
[PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C)
[ExactMemory](https://img.shields.io/badge/ExactMemory-v3.0%2B-8A2BE2)
[Integrity](https://img.shields.io/badge/Integrity-100%25%20DR-success)
[Collision](https://img.shields.io/badge/Collision-97.5%25%20recall-blue)
[Status](https://img.shields.io/badge/status-production--ready-success)

</div>

---

## Core Architecture

```text
                    ┌──────────────────────────────┐
                    │        Recallspection        │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
┌─────────────▼─────────────┐             ┌─────────────▼─────────────┐
│        ExactMemory        │             │      SWSTM Legendary      │
├───────────────────────────┤             ├───────────────────────────┤
│ Exact key recall          │             │ Fuzzy / semantic recall   │
│ HMAC-SHA256 integrity     │             │ Slot buckets              │
│ Replay/Rollback resistance│             │ Exact key resolution      │
│ Transparency log          │             │ Sticky self-token         │
│ Container MAC             │             │ Neural consolidation      │
│ per_key_max tamper detect │             │ Exact-first hybrid        │
└───────────────────────────┘             └───────────────────────────┘
```

---

## What is Recallspection?

**Recallspection** is a dual-engine memory system for autonomous AI agents. It combines a tamper-evident exact memory ledger (**ExactMemory v3**) with a collision-resistant neural associative memory engine (**SWSTM Legendary**). 

> **Design Philosophy:**  
> Recallspection is not a general cure for LLM hallucination. It is a secure memory infrastructure layer that provides deterministic recall for stored facts, cryptographic tamper evidence for persisted records, and reduced overwrite-based forgetting in neural slot memory.

**TL;DR:** `get(k)` = `v_set` ∨ `Err(Tamper)` — never silent wrong data.

---

## Why Recallspection in 2026?

The field shifted in 12 months. Memory became both the biggest differentiator and the biggest attack surface.

*   **Memory in the Age of AI Agents (47-author survey, Dec 2025, 2512.13564):** First taxonomy of the explosion after MemGPT (2023), Mem0 (2024), Letta/Zep/Graphiti. Diagnosis: terminological fragmentation, most production systems clustered in `(token-level, factual, retrieval-heavy)` corner. Trustworthiness flagged as open frontier.

*   **HaluMem (Jan 6 2026):** First operation-level benchmark. Shows existing memory systems hallucinate during extraction and updating, accumulate, and propagate to QA. End-to-end QA evaluation hides the stage where hallucination arises.

*   **GhostWriter / MemGhost (July 2026):** One email plants a persistent false memory. 98% injection success, ~60% activation against SOTA agents (Letta, Mem0, Zep). Background-mode 87.5% success on GPT-5.4, 71.4% on Claude Code. `MEMORY.md` plain-text files load unconditionally every session - RAG needs a query, poisoned memory fires every session.

*   **OWASP LLM08:2025 + ASI06:** Mandates storage-layer tenant isolation and memory poisoning defenses. SMSR provenance tagging (HMAC-SHA256 per entry) proposed as mitigation - exactly what ExactMemory implements.

**Current market:** Agentic AI $19.33B in 2026 → $205.88B by 2033 (40.2% CAGR), Agentic AI Orchestration & Memory $37.11B by 2030, Stateful agent infra SAM $1.2B (2026). Visible funding $66M into memory (Mem0 $24M Series A at $150M valuation, Letta $10M). Vector DB market $2.38B→$18.86B by 2035.

Existing vendors solve recall. Recallspection solves **recall + integrity + collision resistance**.

---

## Key Features

### ExactMemory Integration
Powered by the companion [exactmemory.recallspection](https://github.com/sciencedelicmetatech/exactmemory.recallspection) library:
- **Cryptographic Integrity:** 32-byte HMAC-SHA256 tags and Container MACs.
- **Replay & Rollback Resistance:** Monotonic version counters and hash-chained transparency logs.
- **Zero Dependencies:** Pure Python standard library implementation. <600 lines core, <20KB, 145k put/s, 200k get/s, ~78 bytes/record.
- **Patched Detection:** `get_with_status()` returns `tampered` not `missing` when a previously-known key (in `per_key_max`) is absent - distinguishes deletion attack from never-written.

### SWSTM Legendary
- **Collision-Resistant:** Uses slot buckets to prevent catastrophic forgetting from slot overwrites.
- **Exact-First Hybrid Retrieval:** Checks exact memory before falling back to neural fuzzy search.
- **Neural Sleep:** Consolidation cycles refine prototypes without losing factual records.
- **Production-Ready:** CI-safe encoder injection, atomic save/load roundtrips, and legacy API compatibility.

---

## Verified Guarantees

### 1. ExactMemory Integrity Attack Suite (Self-Contained)

Embeds patched ExactMemory v3.0.1 core directly - no clone needed. Run: `python attack_suite.py`

```
ExactMemory (HMAC-SHA256 + version counter + container MAC)
  bitflip_hmac_tag        att= 10  TP= 10  DR=100%  SFR=  0%
  payload_rewrite         att= 15  TP= 15  DR=100%  SFR=  0%
  replay_old_version      att= 10  TP= 10  DR=100%  SFR=  0%
  direct_store_removal    att= 10  TP= 10  DR=100%  SFR=  0%
  wrong_agent_key         att= 40  TP= 40  DR=100%  SFR=  0%

Naive JSON store (what Mem0/Zep/Letta/OpenClaw use today)
  bitflip_hmac_tag        DR=  0%  SFR=100%  (silent wrong)
  payload_rewrite         DR=  0%  SFR=100%
  replay_old_version      DR=  0%  SFR=100%
  direct_store_removal    DR=  0%  SFR=100%
```

| Attack | What it simulates | Naive JSON | ExactMemory |
|---|---|---|---|
| bitflip_hmac_tag | Disk corruption / file edit | 100% silent wrong | 100% detected |
| payload_rewrite | GhostWriter/MemGhost email injection | 100% silent wrong | 100% detected |
| replay_old_version | Restore old backup / eTAMP | 100% silent wrong | 100% detected |
| direct_store_removal | Deletion attack | 100% silent missing | 100% tampered (patched) |
| wrong_agent_key | Key compromise / tenant isolation failure | 0% | 100% detected |

**Legend:** DR = Detection Rate (higher better), SFR = Silent Failure Rate (returns wrong data with no error)

Naive store is literally `store[k]=v`. That's `MEMORY.md` today.

### 2. SWSTM Collision Resistance Stress Test

Config: 2000 slots, 10k facts, avg load 5.0, max load 14 per slot, deterministic SHA256 slot mapping.

| Engine | Collisions | Evictions | Correct | Recall | Silent Wrong |
|---|---|---|---|---|---|
| Naive single-slot (Mem0/Zep style) | 8016 | 8016 overwrites | 1984/10000 | **19.8%** | **80.2% returns WRONG fact** |
| Bucketed cap=5 (SWSTM Legendary) | 8016 | 1779 | 8221/10000 | **82.2%** | 0% |
| Bucketed cap=8 | 8016 | 255 | 9745/10000 | **97.5%** | 0% |
| **Hybrid exact-first (Recallspection)** | — | 0 | 10000/10000 | **100%** | 0% |

**Load curve (recall vs facts inserted):**

| Facts | Naive recall | Bucket cap 5 |
|---|---|---|
| 2000 | 62.8% | 100% |
| 4000 | 43.0% | 99.1% |
| 6000 | 31.6% | 95.4% |
| 8000 | 24.5% | 89.6% |
| 10000 | 19.8% | 82.2% |

Interpretation: Single-slot memory has catastrophic forgetting - last writer wins per slot. Without exact key check, it returns wrong user's fact 80.2% of the time (HaluMem hallucination). Bucketed slots delay forgetting 4-5x. Hybrid guarantees 100% for stored facts because ExactMemory never forgets; SWSTM is only for fuzzy/semantic fallback.

---

## Installation

```bash
git clone https://github.com/sciencedelicmetatech/recallspection.git
cd recallspection
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install the standalone ExactMemory engine
pip install exactmemory-recallspection
```

---

## Quickstart

### Hybrid Engine (Recommended)
```python
from recallspection.swstm import HybridEngine

hybrid = HybridEngine(num_slots=2000, mode="flat", device="cpu")

hybrid.add("agent:mission", "Provide secure memory for AI agents")
print(hybrid.get("agent:mission", top_k=1))
# ExactMemory hit first, then SWSTM fuzzy if not found
```

### Direct ExactMemory Usage
```python
import hashlib
from exactmemory import ExactMemory

master_secret = b"change-this-in-production"
keys = {
    "agent_key": hashlib.sha256(master_secret).digest(),
    "container": hashlib.sha256(b"container-salt-" + hashlib.sha256(master_secret).digest()).digest(),
}

memory = ExactMemory(keys=keys, container_key_id="container", require_log=True)
memory.put("user:color", "blue", key_id="agent_key")
print(memory.get_with_status("user:color")) # ('blue', 'ok')

# Tamper detection
# memory.store['user:color'] = (rec, bad_tag) -> ('blue', 'tampered') not 'blue'
# del memory.store['user:color'] -> (None, 'tampered') not 'missing' [PATCHED]

memory.save("memory.db")
```

---

## Running the API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000/docs for the interactive Swagger UI
```

### Environment Variables

**Required for Production:**
```bash
RECALLSPECTION_EXACT_SECRET="your-master-exact-secret"
RECALLSPECTION_ADMIN_KEY="your-admin-key"
RECALLSPECTION_SIGNUP_SECRET="your-signup-secret"
```

**Storage Paths (Use persistent disk in production):**
```bash
RECALLSPECTION_MEMORY_FILE="/data/memory.db"
RECALLSPECTION_SWSTM_FILE="/data/swstm.pt"
RECALLSPECTION_DB_FILE="/data/keys.db"
RECALLSPECTION_EXACT_LOG="/data/transparency.log"
```

---

## API Endpoints

### Public
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check and engine status |
| `POST` | `/signup` | Create API key (requires signup secret if configured) |

### Authenticated (`X-API-Key` header required)
| Method | Path | Description |
|---|---|---|
| `POST` | `/add` | Add fact to SWSTM (`backend=swstm`) or ExactMemory (`backend=exact`) |
| `GET` | `/get` | Retrieve fact (Hybrid exact-first search) |
| `POST` | `/exact/add` | Add directly to ExactMemory |
| `GET` | `/exact/get` | Retrieve directly from ExactMemory |
| `GET` | `/usage` | Show API key usage and remaining quota |

### Admin (`X-Admin-Key` header required, fails closed if unconfigured)
| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/keys` | List API keys |
| `POST` | `/admin/revoke/{key_id}` | Revoke an API key |
| `POST` | `/admin/save` | Force memory flush to disk |
| `POST` | `/admin/consolidate` | Run SWSTM neural consolidation |

---

## Deployment & Persistence

Recallspection relies on four persisted artifacts:
1. `memory.db` (ExactMemory container)
2. `transparency.log` (ExactMemory hash chain)
3. `swstm.pt` (SWSTM model and memory state)
4. `keys.db` (API keys and usage tracking)

**Render / Container Deployment:**
- **Always use a persistent disk.** If the filesystem is ephemeral, your transparency log and memory states will be lost on restart.
- Map the environment variables (`RECALLSPECTION_MEMORY_FILE`, etc.) to your persistent disk mount path (e.g., `/data/`).
- The API features an auto-save interval and atomic writes to prevent corruption during sudden container kills.

---

## Security Model

- **ExactMemory Guarantees:** Detects payload tampering, metadata modification, record substitution, file rollback, and log deletion via HMAC-SHA256 and SHA3-256 hash chains. Patched to detect direct store removal as `tampered`.
- **Rollback Protection:** Transparency log with `prev_hash` chain, `max_version` check, optional S3 Object Lock remote anchor for log+container rollback.
- **API Security:** Includes API key auth, usage quotas, signup secrets, fail-closed admin routes, constant-time secret comparison (`hmac.compare_digest`), payload size limits, and internal error masking.
- **What it does NOT claim:** Does not solve general LLM hallucination. Does not prevent write - makes write auditable and undeletable without detection.

---

## Testing

The test suite is fully CI-safe (no external model downloads required):

```bash
pytest tests/ -v --cov=recallspection

# Integrity attack suite (self-contained, no deps)
python tests/test_integrity_attack_suite.py

# Collision stress test
python tests/test_swstm_collision.py
```

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'exactmemory'`**: Ensure you ran `pip install exactmemory-recallspection`.
- **Health endpoint shows `swstm_loaded: false`**: The SWSTM state file doesn't exist yet or the persistence path isn't writable. Add a fact and trigger `/admin/save`.
- **ExactMemory raises tamper/rollback errors**: Do not manually edit `memory.db` or `transparency.log`. These errors mean the cryptographic integrity system is working as designed.
- **`get_with_status()` returns `tampered` for missing key**: You hit the patched case - key was previously known (in `per_key_max`) but now absent from store. This is deletion attack detection, not a bug.

---

<div align="center">

**Recallspection**  
Secure memory infrastructure for autonomous AI agents.  
Part of the Sciencedelic Metatech research ecosystem.

> If this is true - and the two suites above prove it - memory stops being a cache and becomes a ledger. That is a multi-billion dollar infrastructure shift.

</div>
