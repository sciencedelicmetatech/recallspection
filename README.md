<div align="center">

<img src="banner.svg" alt="Recallspection Banner" width="800">

# Recallspection

**Tamper-evident exact memory for autonomous AI agents.**

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

> This contract is the subject of [Paper 1](https://doi.org/10.5281/zenodo.23078584). Rollback is covered by [Paper 2](https://doi.org/10.5281/zenodo.23188770). Revocation is covered by [Paper 3](https://doi.org/10.5281/zenodo.23199032). Read-path integrity is Paper 4 (in press). The unified framework is Paper 5 (in press).

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.2-8A2BE2)](https://github.com/sciencedelicmetatech/recallspection)
[![Anchor](https://img.shields.io/badge/Anchor-S3%20Object%20Lock%20(COMPLIANCE)-00FF88?logo=amazons3&logoColor=white)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
[![IETF](https://img.shields.io/badge/IETF%20Agent%20Record-inspired-6f42c1)](https://datatracker.ietf.org/)
[![Lean 4](https://img.shields.io/badge/Lean-4.11.0-6b4e9e?logo=lean&logoColor=white)](https://leanprover.github.io/)
[![Z3](https://img.shields.io/badge/Z3-SMT-8A2BE2)](https://github.com/Z3Prover/z3)
[![License](https://img.shields.io/badge/License-see%20LICENSE-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-anchor--ready-success)]()
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23078584-blue?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.23078584)

</div>

---

## The Problem

Single-slot memory (Mem0/Zep style) under 5× overload:

| Store | Recall | Silent wrong | Notes |
|---|---:|---:|---|
| Naive single-slot (our baseline) | 19.84 % | 80.16 % | No key routing; vector index only. |
| SWSTM Bucket-8 | 97.45 % | 0 % | Bucketed routing, no exact-first short-circuit. |
| **Recallspection (exact-first hybrid)** | **100 %** | **0 %** | Exact key hit bypasses the vector index entirely. |

Under load, naive stores return another key's fact 80 % of the time, the exact failure mode HaluMem (Jan 2026) documents. Recallspection never silently swaps facts.

---
# Verification artifacts

Machine-checked companions to the five papers in this repository. Every artifact runs in under a minute and does not depend on the product code.

## Tiers

Each theorem ships with artifacts at up to three tiers. The tiers are cumulative: an artifact at a higher tier proves more, but does not replace the lower-tier check, because the lower-tier check confirms that the higher-tier claim is about the right thing.

| Tier | Tool | What it establishes |
|---|---|---|
| Existence | Python | A concrete collapse on a bounded model. Does not prove the theorem. |
| Structural | Z3 (SMT) | The attack encoding is consistent. In-scope: UNSAT. Out-of-scope: SAT. Does not prove the theorem. |
| Proof | Lean 4 | The deterministic core of the theorem. No `sorry`. |

No Python or Z3 artifact proves the full probabilistic or computational claim. Each paper's verification-tiers section states this explicitly. The Lean artifact proves the deterministic core.

---

## Python + Z3 artifacts

One file runs all four checks. Zero external dependencies for the bounded checks. Z3 required for the SMT conformance tests.

---

```bash
python verification/necessity.py

## Install

Core (zero external deps beyond Python 3.10+):

```bash
pip install git+https://github.com/sciencedelicmetatech/recallspection.git