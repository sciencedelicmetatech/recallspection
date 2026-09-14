
```markdown
<p align="center">
  <img src="banner.svg" alt="Recallspection Banner" width="800">
</p>

<div align="center">

# Recallspection

**Tamper-evident exact memory + collision-resistant neural associative memory for AI agents.**

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C)
![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.0%2B-8A2BE2)
![Status](https://img.shields.io/badge/status-production--ready-success)

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
└───────────────────────────┘             └───────────────────────────┘
```

---

## What is Recallspection?

**Recallspection** is a dual-engine memory system for autonomous AI agents. It combines a tamper-evident exact memory ledger (**ExactMemory v3**) with a collision-resistant neural associative memory engine (**SWSTM Legendary**). 

> **Design Philosophy:**  
> Recallspection is not a general cure for LLM hallucination. It is a secure memory infrastructure layer that provides deterministic recall for stored facts, cryptographic tamper evidence for persisted records, and reduced overwrite-based forgetting in neural slot memory.

---

## Key Features

### ExactMemory Integration
Powered by the companion [exactmemory.recallspection](https://github.com/sciencedelicmetatech/exactmemory.recallspection) library:
- **Cryptographic Integrity:** 32-byte HMAC-SHA256 tags and Container MACs.
- **Replay & Rollback Resistance:** Monotonic version counters and hash-chained transparency logs.
- **Zero Dependencies:** Pure Python standard library implementation.

### SWSTM Legendary
- **Collision-Resistant:** Uses slot buckets to prevent catastrophic forgetting from slot overwrites.
- **Exact-First Hybrid Retrieval:** Checks exact memory before falling back to neural fuzzy search.
- **Neural Sleep:** Consolidation cycles refine prototypes without losing factual records.
- **Production-Ready:** CI-safe encoder injection, atomic save/load roundtrips, and legacy API compatibility.

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

- **ExactMemory Guarantees:** Detects payload tampering, metadata modification, record substitution, file rollback, and log deletion via HMAC-SHA256 and SHA3-256 hash chains.
- **API Security:** Includes API key auth, usage quotas, signup secrets, fail-closed admin routes, constant-time secret comparison (`hmac.compare_digest`), payload size limits, and internal error masking.

---

## Testing

The test suite is fully CI-safe (no external model downloads required):

```bash
pytest tests/ -v --cov=recallspection
```

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'exactmemory'`**: Ensure you ran `pip install exactmemory-recallspection`.
- **Health endpoint shows `swstm_loaded: false`**: The SWSTM state file doesn't exist yet or the persistence path isn't writable. Add a fact and trigger `/admin/save`.
- **ExactMemory raises tamper/rollback errors**: Do not manually edit `memory.db` or `transparency.log`. These errors mean the cryptographic integrity system is working as designed.

---

<div align="center">

**Recallspection**  
Secure memory infrastructure for autonomous AI agents.  
Part of the Sciencedelic Metatech research ecosystem.

</div>
```

