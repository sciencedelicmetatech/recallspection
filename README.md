
<div align="center">

<img src="banner.svg" alt="Recallspection Banner" width="800">

# Recallspection

**Tamper-evident exact memory for autonomous AI agents.**

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C)](https://pytorch.org/)
[![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.1-8A2BE2)](https://pypi.org/project/recallspection/)
[![Anchor](https://img.shields.io/badge/Anchor-S3%20Object%20Lock%20COMPLIANCE-00FF88)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
[![IETF](https://img.shields.io/badge/IETF%20Agent%20Record-inspired-6f42c1)](https://datatracker.ietf.org/)
[![License](https://img.shields.io/badge/License-AGPL--3.0%20%7C%20Commercial-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-anchor--ready-success)]()
[![PyPI](https://img.shields.io/badge/pypi-recallspection-orange)](https://pypi.org/project/recallspection/)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23078584-blue)](https://doi.org/10.5281/zenodo.23078584)

</div>

---

## The Problem

Single-slot memory (Mem0/Zep style) under 5× overload:

| Store | Recall | Silent wrong |
|---|---:|---:|
| Naive single-slot | 19.84 % | **80.16 %** |
| SWSTM Bucket-8 | 97.45 % | 0 % |
| **Recallspection (hybrid exact-first)** | **100 %** | **0 %** |

Under load, naive stores return **another key's fact 80 % of the time** — the exact failure mode HaluMem (Jan 2026) documents. Recallspection never silently swaps facts.

---

## Install

```bash
pip install recallspection
pip install boto3   # for the S3 anchor path
```

---

Quick Start

```python
from recallspection.swstm import HybridEngine

hybrid = HybridEngine(num_slots=2000, mode="flat", device="cpu")
hybrid.add("agent:mission", "Secure memory for AI agents")
print(hybrid.get("agent:mission", top_k=1))
# → ExactMemory hit first, SWSTM fuzzy fallback if not found
```

---

Architecture

```
                    ┌──────────────────────────────┐
                    │        Recallspection        │
                    │      Evidence Custodian      │
                    └──────────────┬───────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
┌───────▼────────────┐   ┌─────────▼───────────┐   ┌──────────▼──────────┐
│    ExactMemory     │   │   SWSTM Slot Index  │   │  S3 Object Lock     │
├────────────────────┤   ├─────────────────────┤   │  Anchor             │
│ Exact key recall   │   │ Fuzzy candidate     │   ├─────────────────────┤
│ HMAC-SHA256        │   │   routing           │   │ COMPLIANCE WORM     │
│ Replay resistance  │   │ Slot buckets        │   │ 30-day immutability │
│ Rollback resistance│   │ Exact key resolution│   │ Third-party verify  │
│ Transparency log   │   │ Sticky self-token   │   │ Merkle root anchor  │
│ Container MAC      │   │ No last-writer-wins │   │ Anti-rollback proof │
│ per_key_max check  │   │ Exact-first hybrid  │   │ EU AI Act Art. 12   │
└────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

ExactMemory is the ledger. SWSTM routes fuzzy candidates only. S3 anchor proves the ledger wasn't rolled back.

---

Guarantees

Detects (100 % detection, 0 % silent failure across 85 attacks):

· Payload tampering, metadata modification, record substitution
· Replay of old versions, deletion attacks, wrong-key substitution
· Whole-container rollback (with S3 anchor)

Does not claim:

· Solving general LLM hallucination
· Beating Mem0 / LoCoMo / LongMemEval on QA benchmarks
· IETF Agent Record compliance (records are Agent Record-inspired)

```bash
python tests/test_integrity_attack_suite.py
```

---

S3 Object Lock Anchor

The transparency log proves records weren't modified. It does not prove a whole authentic file wasn't replaced with an earlier authentic file. That requires an external witness.

```bash
# Bucket MUST be created with Object Lock enabled — cannot be added later.
aws s3api create-bucket \
  --bucket recallspection-anchor-prod-1a2b3c \
  --region us-east-1 \
  --object-lock-enabled-for-bucket

aws s3api put-object-lock-configuration \
  --bucket recallspection-anchor-prod-1a2b3c \
  --object-lock-configuration \
  '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"COMPLIANCE","Days":30}}}'
```

```python
from recallspection.anchor import anchor_root

root = anchor_root("/data/transparency.log")
print(f"Anchored {root} to S3")
# curl https://api.recallspection.com/verify?root=0x4a2f...1291
# → {"local_valid": true, "s3_locked": true, "retain_until": "2027-01-28"}
```

---

API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
# Swagger UI → http://localhost:8000/docs
```

Public: GET /health · POST /signup · GET /verify
Auth: POST /add · GET /get · POST /exact/add · GET /exact/get · GET /usage · POST /anchor · GET /audit/export
Admin: GET /admin/keys · POST /admin/revoke/{id} · POST /admin/save · POST /admin/consolidate

---

Environment

```bash
# Required in production
RECALLSPECTION_EXACT_SECRET="your-master-exact-secret"
RECALLSPECTION_ADMIN_KEY="your-admin-key"
RECALLSPECTION_SIGNUP_SECRET="your-signup-secret"

# Storage (mount persistent disk)
RECALLSPECTION_MEMORY_FILE="/data/memory.db"
RECALLSPECTION_SWSTM_FILE="/data/swstm.pt"
RECALLSPECTION_DB_FILE="/data/keys.db"
RECALLSPECTION_EXACT_LOG="/data/transparency.log"

# S3 anchor
RECALLSPECTION_S3_BUCKET="recallspection-anchor-prod-1a2b3c"
RECALLSPECTION_S3_REGION="us-east-1"
RECALLSPECTION_S3_RETENTION_DAYS="30"
AWS_ACCESS_KEY_ID="..."
AWS_SECRET_ACCESS_KEY="..."
```

---

Security Model

· ExactMemory. HMAC-SHA256 + SHA3-256 hash chain. Detects tampering, substitution, replay, deletion, rollback.
· Rollback. Transparency log + optional S3 Object Lock anchor closes the container-plus-log rollback gap.
· API. Key auth, quotas, fail-closed admin, constant-time comparison, payload limits.
· Fuzzy path. Fail-open as candidate list. Fail-closed as answer. Only ExactMemory returns values.

Known gap: if RECALLSPECTION_EXACT_SECRET leaks, HMACs can be forged. That is the threat model boundary. External KMS + S3 anchor closes the loop.

---

Testing

```bash
pytest tests/ -v --cov=recallspection
python tests/test_integrity_attack_suite.py   # self-contained, no deps
python tests/test_swstm_collision.py
```

---

Docs

· Security Model
· API Reference
· Evaluation
· IETF Agent Record Status
· Paper: ExactMemory–Recallspection Integrity Theorem

---

Research

Part of the Sciencedelic Metatech ecosystem.

Companion paper: The ExactMemory-Recallspection Integrity Theorem — write-time commitment is necessary for tamper-evident agent memory.

---

License

Dual-licensed:

· Open source: AGPL-3.0
· Commercial: Recallspection Integrity License (RIL) v1.0

---

<div align="center">The flight recorder, not the cache.

Memory stops being a cache and becomes a ledger. The store cannot quietly return a different fact. The log cannot be quietly rolled back.

</div>
```---

