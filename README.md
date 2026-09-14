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
![Status](https://img.shields.io/badge/status-production--hardening-orange)

</div>

---

## What is Recallspection?

**Recallspection** is a dual-engine memory system for autonomous AI agents.

It combines:

1. **ExactMemory v3** — a tamper-evident, replay-resistant, rollback-resistant exact memory ledger.
2. **SWSTM Legendary** — a collision-resistant neural associative memory engine for fuzzy retrieval and agent-scale semantic memory.

Together, they form a secure memory layer for agents that need to remember facts reliably, retrieve associated information flexibly, and detect tampering or rollback attempts.

> **Important positioning:**  
> Recallspection is not a general cure for LLM hallucination.  
> It is a memory infrastructure layer that provides deterministic recall for stored facts, tamper evidence for persisted records, and reduced overwrite-based forgetting in neural slot memory.

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
│ Replay resistance         │             │ Exact key resolution      │
│ Rollback resistance       │             │ Sticky self-token         │
│ Transparency log          │             │ Consolidation / sleep     │
│ Container MAC             │             │ Encoder injection         │
│ Tombstones                │             │ Save/load roundtrip       │
│ Remote anchor support     │             │ Hybrid exact-first search │
└───────────────────────────┘             └───────────────────────────┘
pip install exactmemory-recallspection

Below is the **full README for the main repo**: `sciencedelicmetatech/recallspection`.

Important banner rule:

> Keep the main repo banner unique. Do **not** reuse the ExactMemory repo banner.  
> The README below assumes your main repo banner file is `banner.svg`.  
> If your main banner has a different filename, only change this line:
>
> ```md
> ![Recallspection Banner](banner.svg)
> ```

---

## Recommended `README.md` for Main Repo

```md
![Recallspection Banner](banner.svg)

<div align="center">

# Recallspection

**Tamper-evident exact memory + collision-resistant neural associative memory for AI agents.**

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C)
![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.0%2B-8A2BE2)
![Status](https://img.shields.io/badge/status-production--hardening-orange)

</div>

---

## What is Recallspection?

**Recallspection** is a dual-engine memory system for autonomous AI agents.

It combines:

1. **ExactMemory v3** — a tamper-evident, replay-resistant, rollback-resistant exact memory ledger.
2. **SWSTM Legendary** — a collision-resistant neural associative memory engine for fuzzy retrieval and agent-scale semantic memory.

Together, they form a secure memory layer for agents that need to remember facts reliably, retrieve associated information flexibly, and detect tampering or rollback attempts.

> **Important positioning:**  
> Recallspection is not a general cure for LLM hallucination.  
> It is a memory infrastructure layer that provides deterministic recall for stored facts, tamper evidence for persisted records, and reduced overwrite-based forgetting in neural slot memory.

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
│ Replay resistance         │             │ Exact key resolution      │
│ Rollback resistance       │             │ Sticky self-token         │
│ Transparency log          │             │ Consolidation / sleep     │
│ Container MAC             │             │ Encoder injection         │
│ Tombstones                │             │ Save/load roundtrip       │
│ Remote anchor support     │             │ Hybrid exact-first search │
└───────────────────────────┘             └───────────────────────────┘
```

---

## Why Recallspection?

Most AI memory systems fail in one of three ways:

1. **They forget silently.**  
   A vector store overwrites or loses memories under collision pressure.

2. **They retrieve approximately when exactness is required.**  
   Some agent tasks need deterministic recall, not nearest-neighbor guessing.

3. **They cannot prove whether a memory was modified.**  
   A database may return data, but not prove that the data is still authentic.

Recallspection addresses these issues by separating memory responsibilities:

- **ExactMemory** handles authoritative, auditable, tamper-evident facts.
- **SWSTM Legendary** handles associative, fuzzy, neural-style retrieval.
- **Hybrid retrieval** prefers exact memory first, then falls back to neural memory.

---

## Features

### ExactMemory Integration

The production ExactMemory engine is maintained in the companion repository:

**[exactmemory.recallspection](https://github.com/sciencedelicmetatech/exactmemory.recallspection)**

It provides:

- **HMAC-SHA256 integrity** with 32-byte authentication tags
- **Metadata binding** across key, version, timestamp, and nonce
- **Replay resistance** using monotonic version counters
- **Rollback resistance** using a hash-chained transparency log
- **Container MAC** for authenticating the full persisted database file
- **Tombstones** for signed deletion
- **Missing vs tampered vs expired vs tombstoned** status reporting
- **Remote anchor interface** for S3 Object Lock-style external anchoring
- **Zero external dependencies** — pure Python standard library

### SWSTM Legendary

The upgraded SWSTM engine includes:

- **Slot buckets** instead of single-slot overwrite storage
- **Exact key resolution inside buckets**
- **Sticky self-token** for rewarding frequently used slots
- **Neural consolidation / sleep** for prototype refinement
- **CI-safe encoder injection**
- **Legacy API compatibility**
- **Save/load roundtrip safety**
- **Delete support**
- **Public `fact_count` interface**
- **Hybrid exact-first retrieval**

---

## What Recallspection Solves

Recallspection is designed to provide:

- Deterministic retrieval for stored facts
- Tamper evidence for persisted agent memory
- Replay and rollback detection
- Reduced catastrophic forgetting from slot overwrite collisions
- Hybrid exact + fuzzy retrieval
- Production-safe API access with usage limits and admin controls

---

## What Recallspection Does Not Claim

Recallspection does **not** claim to:

- Eliminate all LLM hallucination
- Replace model alignment or reasoning safety
- Guarantee semantic correctness of facts written by an agent
- Prevent malicious writes if the attacker has valid API credentials and secrets

It is a secure memory layer, not a general truth engine.

---

## Installation

### Main Repository

```bash
git clone https://github.com/sciencedelicmetatech/recallspection.git
cd recallspection
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ExactMemory Dependency

Install the standalone ExactMemory package:

```bash
pip install exactmemory-recallspection
```

Or install directly from GitHub:

```bash
pip install git+https://github.com/sciencedelicmetatech/exactmemory.recallspection.git
```

---

## Quickstart: Library Usage

### SWSTM Legendary

```python
from recallspection.swstm import SWSTMEngine

engine = SWSTMEngine(
    num_slots=2000,
    mode="flat",
    device="cpu",
)

engine.add("agent:name", "Recallspection")
engine.add("agent:purpose", "Secure memory for AI agents")

print(engine.get("agent:name", top_k=1))
print(engine.fact_count)
```

### ExactMemory v3

```python
import hashlib
from exactmemory import ExactMemory

master_secret = b"change-this-in-production"

keys = {
    "agent_key": hashlib.sha256(master_secret).digest(),
    "container": hashlib.sha256(b"container-salt-" + hashlib.sha256(master_secret).digest()).digest(),
}

memory = ExactMemory(
    keys=keys,
    container_key_id="container",
    require_log=True,
    log_path="transparency.log",
)

memory.put("user:favorite_color", "blue", key_id="agent_key")
memory.save("memory.db")

print(memory.get("user:favorite_color", raise_on_tampered=True))
```

### Hybrid Engine

```python
from recallspection.swstm import HybridEngine

hybrid = HybridEngine(
    num_slots=2000,
    mode="flat",
    device="cpu",
)

hybrid.add("project", "Recallspection")
print(hybrid.get("project", top_k=1))
```

---

## Running the API

If your API module is `recallspection/api.py`, run:

```bash
uvicorn recallspection.api:app --host 0.0.0.0 --port 8000
```

If you have a top-level `api.py`, run:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000/docs
```

---

## Environment Variables

### Required for Production

```bash
RECALLSPECTION_EXACT_SECRET="your-master-exact-secret"
RECALLSPECTION_ADMIN_KEY="your-admin-key"
RECALLSPECTION_SIGNUP_SECRET="your-signup-secret"
```

### Storage Paths

For local development:

```bash
RECALLSPECTION_MEMORY_FILE="memory.db"
RECALLSPECTION_SWSTM_FILE="swstm.pt"
RECALLSPECTION_DB_FILE="keys.db"
RECALLSPECTION_EXACT_LOG="transparency.log"
```

For Render or container deployments with persistent disk:

```bash
RECALLSPECTION_MEMORY_FILE="/data/memory.db"
RECALLSPECTION_SWSTM_FILE="/data/swstm.pt"
RECALLSPECTION_DB_FILE="/data/keys.db"
RECALLSPECTION_EXACT_LOG="/data/transparency.log"
```

### Optional Settings

```bash
SWSTM_MODE="flat"
AUTO_SAVE_INTERVAL="100"
PORT="8000"
```

---

## API Endpoints

### Public

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Landing page or API status |
| `GET` | `/health` | Health check |
| `POST` | `/signup` | Create API key, protected by signup secret if configured |

### Authenticated

All authenticated endpoints require:

```http
X-API-Key: your_api_key
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/add` | Add fact to SWSTM or ExactMemory |
| `GET` | `/get` | Retrieve fact from SWSTM or ExactMemory |
| `POST` | `/exact/add` | Add fact to ExactMemory |
| `GET` | `/exact/get` | Retrieve fact from ExactMemory |
| `GET` | `/usage` | Show API key usage and remaining quota |
| `GET` | `/agent-info` | Detect agent-style client and show plan advice |

### Admin

Admin endpoints require:

```http
X-Admin-Key: your_admin_key
```

If no admin key is configured, admin endpoints fail closed.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/keys` | List API keys |
| `POST` | `/admin/revoke/{key_id}` | Revoke an API key |
| `POST` | `/admin/save` | Force memory save |
| `POST` | `/admin/consolidate` | Run SWSTM consolidation and save |

---

## Example API Usage

### Signup

```bash
curl -X POST "http://localhost:8000/signup?owner=demo&plan=free" \
  -H "X-Signup-Secret: your-signup-secret"
```

### Add to ExactMemory

```bash
curl -X POST "http://localhost:8000/add?backend=exact" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "agent:name",
    "value": "Recallspection"
  }'
```

### Get from ExactMemory

```bash
curl "http://localhost:8000/get?key=agent:name&backend=exact" \
  -H "X-API-Key: your_api_key"
```

### Add to SWSTM

```bash
curl -X POST "http://localhost:8000/add?backend=swstm" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "agent:mission",
    "value": "Provide secure memory for autonomous agents"
  }'
```

### Get from SWSTM

```bash
curl "http://localhost:8000/get?key=agent:mission&backend=swstm" \
  -H "X-API-Key: your_api_key"
```

---

## Testing

Run the test suite:

```bash
pytest tests/ -v --cov=recallspection
```

The test suite is CI-safe:

- No SentenceTransformer model downloads are required.
- Tests use a `DummyEncoder`.
- SWSTM accepts injected encoders.
- ExactMemory wrapper tests validate upsert, deletion, and roundtrip behavior.

---

## Security Model

### ExactMemory Guarantees

ExactMemory v3 is designed to detect:

- Payload tampering
- Metadata tampering
- Record substitution
- Replay of old records
- File rollback
- Log deletion
- Container-level modification
- Tombstone tampering

It does this through:

- HMAC-SHA256 record tags
- SHA3-256 hash chains
- Monotonic version counters
- Container MAC
- Transparency log verification
- Optional remote anchoring

### API Security

The Recallspection API includes:

- API key authentication
- Usage quotas
- Signup secret protection
- Admin fail-closed behavior
- Constant-time secret comparison with `hmac.compare_digest`
- Payload size limits
- Internal error masking
- Auto-save interval
- Atomic persistence for SWSTM and ExactMemory

---

## Persistence

Recallspection uses multiple persisted artifacts:

| File | Purpose |
|---|---|
| `memory.db` or configured memory file | ExactMemory container |
| `transparency.log` | ExactMemory hash-chained transparency log |
| `swstm.pt` | SWSTM model and memory state |
| `keys.db` | API keys and usage tracking |

For production deployments, these files should be stored on persistent storage.

If you deploy on Render, use a persistent disk and point environment variables to that mount path.

---

## Deployment Notes

### Render

Recommended start command:

```bash
uvicorn recallspection.api:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```bash
RECALLSPECTION_EXACT_SECRET=...
RECALLSPECTION_ADMIN_KEY=...
RECALLSPECTION_SIGNUP_SECRET=...
RECALLSPECTION_MEMORY_FILE=/data/memory.db
RECALLSPECTION_SWSTM_FILE=/data/swstm.pt
RECALLSPECTION_DB_FILE=/data/keys.db
RECALLSPECTION_EXACT_LOG=/data/transparency.log
```

Important:

- Do not store secrets in the repository.
- Use a persistent disk.
- If using SentenceTransformer encoders, pre-cache models or allow sufficient startup time.
- The health endpoint should return `healthy` after startup.

---

## SWSTM Legendary Design Details

### Slot Buckets

Original SWSTM used:

```python
slot_to_value[slot_idx] = value
```

This caused overwrite-based forgetting when multiple keys routed to the same slot.

Legendary SWSTM uses:

```python
slot_to_values[slot_idx].append((key, value))
```

This prevents one key from silently destroying another key in the same slot.

### Exact Key Resolution

Before fuzzy fallback, SWSTM attempts exact key resolution.

This means stored keys can be retrieved exactly even under slot collision pressure.

### Sticky Self-Token

The `self_token` rewards frequently used slots, making useful slots more salient over time.

### Consolidation

`consolidate()` performs a lightweight neural sleep cycle:

- Reviews stored training buffer
- Refines prototypes
- Preserves factual records
- Prepares memory topology for future writes

### Encoder Injection

Tests and lightweight deployments can inject a custom encoder:

```python
engine = SWSTMEngine(
    num_slots=4,
    key_dim=8,
    slot_dim=8,
    encoder=my_encoder,
    device="cpu",
)
```

This prevents CI from downloading large sentence transformer models.

---

## Hybrid Retrieval Behavior

Hybrid retrieval follows an exact-first policy:

1. Check ExactMemory for the requested key.
2. If an exact valid record exists, return it.
3. If not, query SWSTM.
4. Return fuzzy or associative results.

This gives agents deterministic behavior for high-value facts while preserving flexible semantic retrieval.

---

## Development Status

Current milestone:

```text
Recallspection v18.1.0-legendary
```

Status:

- CI-safe SWSTM Legendary engine: complete
- ExactMemory wrapper compatibility: complete
- API production hardening: complete
- ExactMemory v3 integration: complete
- README and documentation upgrade: in progress
- Render production deployment: next

---

## Related Repository

For the standalone tamper-evident memory engine, see:

**[sciencedelicmetatech/exactmemory.recallspection](https://github.com/sciencedelicmetatech/exactmemory.recallspection)**

The main Recallspection repository uses ExactMemory as the authoritative exact memory layer.

---

## Repository Structure

```text
recallspection/
├── recallspection/
│   ├── __init__.py
│   ├── swstm.py
│   ├── exact.py
│   └── api.py
├── tests/
│   └── test_swstm.py
├── requirements.txt
├── README.md
├── SECURITY.md
└── ROADMAP.md
```

---

## Troubleshooting

### `ImportError: cannot import name 'SWSTMCore'`

Add the compatibility alias to `recallspection/swstm.py`:

```python
SWSTMCore = SWSTMEngine
```

### `ModuleNotFoundError: No module named 'exactmemory'`

Install the ExactMemory package:

```bash
pip install exactmemory-recallspection
```

or:

```bash
pip install git+https://github.com/sciencedelicmetatech/exactmemory.recallspection.git
```

### Health endpoint shows `swstm_loaded: false`

This may mean:

- No SWSTM state file exists yet
- The persistence path is not writable
- The server has not saved memory yet
- The deployment filesystem is ephemeral

Use persistent storage and trigger `/admin/save` after adding facts.

### ExactMemory raises tamper or rollback errors

Do not manually edit:

- `memory.db`
- `transparency.log`
- ExactMemory container files

These errors mean the integrity system is working as designed.

---

## License

MIT License. See `LICENSE` for details.

---

<div align="center">

**Recallspection**  
Secure memory infrastructure for autonomous AI agents.

Part of the Sciencedelic Metatech research ecosystem.

</div>
```

---