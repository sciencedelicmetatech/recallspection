<div align="center">

<img src="banner.svg" alt="Recallspection Banner" width="800">

# Recallspection

**Tamper-evident exact memory for autonomous AI agents.**

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

> The contract is [Paper 1](https://doi.org/10.5281/zenodo.23078584). Rollback is [Paper 2](https://doi.org/10.5281/zenodo.23188770). Revocation is [Paper 3](https://doi.org/10.5281/zenodo.23199032). Read-path integrity is [Paper 4](https://doi.org/10.5281/zenodo.23254396). The framework is [Paper 5](https://doi.org/10.5281/zenodo.23263748). Attribution is [Paper 6](https://doi.org/10.5281/zenodo.23288111).

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[![Conformance](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/conformance.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/conformance.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.2-8A2BE2)](https://github.com/sciencedelicmetatech/exactmemory.recallspection)
[![Anchor](https://img.shields.io/badge/Anchor-file%20%7C%20S3%20Object%20Lock-00FF88)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
[![Lean 4](https://img.shields.io/badge/Lean-4.11.0-6b4e9e?logo=lean&logoColor=white)](https://leanprover.github.io/)
[![Z3](https://img.shields.io/badge/Z3-SMT-8A2BE2)](https://github.com/Z3Prover/z3)
[![License](https://img.shields.io/badge/License-see%20LICENSE-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-anchor--ready-success)]()
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23078584-blue?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.23078584)

</div>

---

## The problem

Single-slot memory (Mem0 / Zep style) under 5x overload:

| Store | Recall | Silent wrong | Notes |
|---|---:|---:|---|
| Naive single-slot (our baseline) | 19.84 % | 80.16 % | No key routing; vector index only. |
| SWSTM Bucket-8 | 97.45 % | 0 % | Bucketed routing, no exact-first short-circuit. |
| **Recallspection (exact-first hybrid)** | **100 %** | **0 %** | Exact key hit bypasses the vector index entirely. |

Under load, naive stores return another key's fact 80 % of the time, the exact failure mode HaluMem (Jan 2026) documents. Recallspection never silently swaps facts.

---

## Conformance

Storage-edit conformance against a local reproduction of the agmi suite's nine storage-level attacks (T1-T9). Verdicts use agmi's vocabulary:

- `rejected`: the read path refused the edit before serving
- `reported`: a separate audit named the problem afterwards, the read path had already served the value
- `accepted`: the tool loaded the altered store and served the edit as genuine

| Edit | Verdict |
|---|---|
| T1 content tamper | rejected on read |
| T2 tail truncation | rejected on read |
| T3 middle deletion | rejected on read |
| T4 reordering | rejected on read |
| T5 forged insertion | rejected on read |
| T6 cross-context replay | rejected on read |
| T7 rollback replay | rejected on read |
| T8 metadata tamper | rejected on read |
| T9 snapshot rollback | rejected on read |

**9 rejected, 0 accepted, 0 errors.**

Run: `python recallspection/conformance/agmi_selfcheck.py`

For comparison, in the published agmi table, only one of twenty stores rejects all of T1-T8 on the read path, and no store in the table rejects T9. Recallspection rejects all nine.

### Honest scope of the claim

The runner is a local reproduction of the nine attacks, not a run of the upstream `agmi-check` binary. The core read path refuses every edit against the same threat model agmi specifies: an attacker who can write the on-disk bytes but holds no keys. A drop-in adapter for the upstream suite lives at `recallspection/conformance/agmi_adapter.py`; running it requires `agent-memory-integrity` installed and, when it runs, is what earns the `agmi-check` name.

T9 (snapshot rollback) is enforced by an external high-water-mark anchor. In production, set `RECALLSPECTION_ANCHOR_BACKEND=file|s3`. Without an anchor, T9 is accepted. The self-check uses an in-process stub to demonstrate the read-path mechanism.

---

## Papers and DOIs

| # | Title | DOI |
|---|---|---|
| 1 | ExactMemory-Recallspection Integrity Theorem | [10.5281/zenodo.23078584](https://doi.org/10.5281/zenodo.23078584) |
| 2 | Rollback Indistinguishability Theorem | [10.5281/zenodo.23188770](https://doi.org/10.5281/zenodo.23188770) |
| 3 | Revocation Indistinguishability Theorem | [10.5281/zenodo.23199032](https://doi.org/10.5281/zenodo.23199032) |
| 4 | Read-Path Indistinguishability Theorem | [10.5281/zenodo.23254396](https://doi.org/10.5281/zenodo.23254396) |
| 5 | Raell's Externality Theorem (framework) | [10.5281/zenodo.23263748](https://doi.org/10.5281/zenodo.23263748) |
| 6 | Attribution Indistinguishability Theorem | [10.5281/zenodo.23288111](https://doi.org/10.5281/zenodo.23288111) |

Papers 7 to 9 (contextual integrity, composition stack, factuality) are in draft.

The unifying frame across all six papers: a mechanism reading only its own input cannot decide a predicate that depends on facts outside that input. This is the scoping condition; the individual theorems are instances of it.

---

## Verification artifacts

Machine-checked companions to the six papers. Every artifact runs in under a minute and does not depend on the product code.

### Tiers

Each theorem ships with artifacts at up to three tiers. The tiers are cumulative: an artifact at a higher tier proves more, but does not replace the lower-tier check, because the lower-tier check confirms that the higher-tier claim is about the right thing.

| Tier | Tool | What it establishes |
|---|---|---|
| Existence | Python | A concrete collapse on a bounded model. Does not prove the theorem. |
| Structural | Z3 (SMT) | The attack encoding is consistent. In-scope: UNSAT. Out-of-scope: SAT. Does not prove the theorem. |
| Proof | Lean 4 | The deterministic core of the theorem. No `sorry`. |

No Python or Z3 artifact proves the full probabilistic or computational claim. Each paper's verification-tiers section states this explicitly. The Lean artifact proves the deterministic core.

### Run all checks

```bash
python verification/necessity.py
python verification/attribution_necessity.py
python verification/z3_attribution_necessity.py