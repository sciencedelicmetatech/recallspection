<div align="center">

<img src="banner.svg" alt="Recallspection Banner" width="800">

# Recallspection

**Tamper-evident exact memory for autonomous AI agents.**

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.2-8A2BE2)](https://github.com/sciencedelicmetatech/recallspection)
[![Anchor](https://img.shields.io/badge/Anchor-S3%20Object%20Lock%20COMPLIANCE-00FF88?logo=amazons3&logoColor=white)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
[![IETF](https://img.shields.io/badge/IETF%20Agent%20Record-inspired-6f42c1)](https://datatracker.ietf.org/)
[![License](https://img.shields.io/badge/License-AGPL--3.0%20%7C%20Commercial-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-anchor--ready-success)]()
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23078584-blue?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.23078584)

</div>

---

## The Problem

Single-slot memory (Mem0/Zep style) under 5× overload:

| Store | Recall | Silent wrong |
|---|---:|---:|
| Naive single-slot | 19.84 % | **80.16 %** |
| SWSTM Bucket-8 | 97.45 % | 0 % |
| **Recallspection (hybrid exact-first)** | **100 %** | **0 %** |

Under load, naive stores return **another key's fact 80 % of the time** the exact failure mode HaluMem (Jan 2026) documents. Recallspection never silently swaps facts.

---

## Install

```bash
pip install git+https://github.com/sciencedelicmetatech/recallspection.git
# For the S3 anchor path:
pip install "recallspection[anchor] @ git+https://github.com/sciencedelicmetatech/recallspection.git"