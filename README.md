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
│        ExactMemory        │             │      SWSTM + Cards        │
├───────────────────────────┤             ├───────────────────────────┤
│ Exact key recall          │             │ Fuzzy via cards + cosine  │
│ HMAC-SHA256 integrity     │             │ Slot buckets (capacity)   │
│ Replay/Rollback resistance│             │ Exact key resolution      │
│ Transparency log          │             │ Sticky self-token         │
│ Container MAC             │             │ Exact-first hybrid        │
│ per_key_max tamper detect │             │ Abstain below threshold   │
└───────────────────────────┘             └───────────────────────────┘
```

---

## What is Recallspection?

Recallspection is a dual-engine memory system for autonomous AI agents. It combines a tamper-evident exact memory ledger (ExactMemory v3) with a collision-resistant associative memory engine (SWSTM) and card-based fuzzy retrieval.

The design goal is simple: memory should be deterministic, auditable, and safe under attack. When an exact key is known, Recallspection returns the exact value. When a fact is uncertain, it abstains instead of silently returning the wrong result.

**Design philosophy:** Recallspection is not a general cure for LLM hallucination. It is a secure memory infrastructure layer for storing facts with integrity, provenance, and safe retrieval semantics.

**TL;DR:** get(k) = v_set OR Err(Tamper) never silent wrong data.

---

## Why Recallspection in 2026?

The field shifted in 12 months. Memory became both the biggest differentiator and the biggest attack surface.

- Memory in the Age of AI Agents (47-author survey, Dec 2025): classification of memory systems and failure modes after MemGPT, Mem0, Letta, Zep, and Graphiti.
- HaluMem (Jan 2026): benchmark showing memory systems hallucinate during extraction and updating, then propagate those errors into QA.
- GhostWriter / MemGhost: persistent false memories can be injected via background poisoning attacks with high activation against common agent stacks.
- OWASP LLM08:2025 + ASI06: mandates storage-layer isolation and memory poisoning defenses. Provenance tagging and tamper detection are foundational mitigations.

Current market momentum is massive, but most systems still solve recall without integrity. Recallspection solves recall + integrity + collision resistance.

---

## Key Features

### ExactMemory Integration

Powered by the companion `exactmemory.recallspection` library:

- Cryptographic integrity with 32-byte HMAC-SHA256 tags and container MACs
- Replay and rollback resistance via monotonic version counters and hash-chained transparency logs
- No external dependency burden: pure Python standard library, compact core, high throughput
- Patched detection semantics: `get_with_status()` distinguishes missing from tampered

### SWSTM + Cards

- Collision-resistant slot buckets prevent catastrophic overwrites
- Exact-first hybrid retrieval checks exact memory before fuzzy fallback
- Card-based fuzzy retrieval for natural-language paraphrase lookup
- Abstains when confidence is below threshold instead of returning wrong data
- Production-safe encoder injection and atomic persistence lifecycle

---

## Verified Guarantees

### 1. ExactMemory Integrity Attack Suite

Self-contained attack suite embedded in the project. Run:

```bash
python attack_suite.py
```

```text
ExactMemory (HMAC-SHA256 + version counter + container MAC)
  bitflip_hmac_tag        att= 10  TP= 10  DR=100%  SFR=  0%
  payload_rewrite         att= 15  TP= 15  DR=100%  SFR=  0%
  replay_old_version      att= 10  TP= 10  DR=100%  SFR=  0%
  direct_store_removal    att= 10  TP= 10  DR=100%  SFR=  0%
  wrong_agent_key         att= 40  TP= 40  DR=100%  SFR=  0%

Naive JSON store
  bitflip_hmac_tag        DR=  0%  SFR=100%  (silent wrong)
  payload_rewrite         DR=  0%  SFR=100%
  replay_old_version      DR=  0%  SFR=100%
  direct_store_removal    DR=  0%  SFR=100%
```

### 2. SWSTM Collision Resistance Stress Test

Configuration: 2000 slots, 10k facts, average load 5.0, deterministic SHA256 slot mapping.

| Engine | Collisions | Correct Recall | Silent Wrong |
| --- | ---: | ---: | ---: |
| Naive single-slot | 8016 | 1984/10000 (19.8%) | 80.2% |
| Bucketed cap=5 | 1779 | 8221/10000 (82.2%) | 0% |
| Bucketed cap=8 | 255 | 9745/10000 (97.5%) | 0% |
| Hybrid exact-first | 0 | 10000/10000 (100%) | 0% |

Interpretation: single-slot memory has catastrophic forgetting. Recallspection avoids silent wrong answers by preferring exact matches and abstaining when needed.

### 3. Card-based Paraphrase Path

On a 10-query benchmark, the exact key path and card-based path both reached 100% accuracy on the tested set. Legacy prototype routing was unstable and inconsistent.

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

# Optional: richer card for better paraphrase recall
hybrid.add(
    "user:favorite_color",
    "blue",
    card="The user's favorite color is blue",
)
print(hybrid.get_with_status("what color does the user like?"))
# -> status "fuzzy", value "blue" (if score >= threshold)
print(hybrid.get_with_status("what is the meaning of life?"))
# -> status "missing" (abstain — never silent wrong)
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
print(memory.get_with_status("user:color"))  # ('blue', 'ok')

# Tamper detection
# memory.store['user:color'] = (rec, bad_tag) -> ('blue', 'tampered') not 'blue'
# del memory.store['user:color'] -> (None, 'tampered') not 'missing'

memory.save("memory.db")
```

---

## Running the API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000/docs for the interactive Swagger UI
```

---

## Environment Variables

### Required for Production

```text
RECALLSPECTION_EXACT_SECRET="your-master-exact-secret"
RECALLSPECTION_ADMIN_KEY="your-admin-key"
RECALLSPECTION_SIGNUP_SECRET="your-signup-secret"
```

### Storage Paths

```text
RECALLSPECTION_MEMORY_FILE="/data/memory.db"
RECALLSPECTION_SWSTM_FILE="/data/swstm.pt"
RECALLSPECTION_DB_FILE="/data/keys.db"
RECALLSPECTION_EXACT_LOG="/data/transparency.log"
```

---

## API Endpoints

### Public

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check and engine status |
| POST | `/signup` | Create API key (requires signup secret if configured) |

### Authenticated

| Method | Path | Description |
| --- | --- | --- |
| POST | `/add` | Add a fact to SWSTM or ExactMemory |
| GET | `/get` | Retrieve a fact using hybrid exact-first search |
| POST | `/exact/add` | Add directly to ExactMemory |
| GET | `/exact/get` | Retrieve directly from ExactMemory |
| GET | `/usage` | Show API key usage and remaining quota |

### Admin

| Method | Path | Description |
| --- | --- | --- |
| GET | `/admin/keys` | List API keys |
| POST | `/admin/revoke/{key_id}` | Revoke an API key |
| POST | `/admin/save` | Force memory flush to disk |
| POST | `/admin/consolidate` | Run SWSTM neural consolidation |

---

## Deployment & Persistence

Recallspection depends on four persisted artifacts:

1. `memory.db` — ExactMemory container
2. `transparency.log` — ExactMemory hash chain
3. `swstm.pt` — SWSTM model and memory state
4. `keys.db` — API keys and usage tracking

For Render or container deployment:

- Use a persistent disk
- Map all persistence paths under `/data/`
- Keep the API auto-save interval enabled for crash safety

---

## Security Model

- ExactMemory detects payload tampering, metadata tampering, record substitution, file rollback, and log deletion using HMAC-SHA256 and hash chaining
- Rollback protection is enforced via transparency logs and version checks
- API access controls include API key auth, usage quotas, fail-closed admin routes, and constant-time secret comparisons
- Fuzzy retrieval abstains below threshold instead of silently returning wrong data

---

## Testing

```bash
pytest tests/ -v --cov=recallspection

# Integrity attack suite
python tests/test_integrity_attack_suite.py

# Collision stress test
python tests/test_swstm_collision.py
```

---

## Troubleshooting

| Error | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'exactmemory'` | Run `pip install exactmemory-recallspection` |
| Health endpoint shows `swstm_loaded: false` | Ensure the state file path is writable and add a fact before saving |
| ExactMemory raises tamper or rollback errors | Do not edit `memory.db` or `transparency.log` manually; the system is working as designed |
| `get_with_status()` returns `tampered` for a missing key | This is a deletion-attack detection case |
| Fuzzy queries return `missing` | Add a richer `card=` on write or lower the fuzzy threshold |

---

<p align="center">
  <strong>Recallspection</strong> — Secure memory infrastructure for autonomous AI agents.<br>
  Part of the Sciencedelic Metatech research ecosystem.
</p>
