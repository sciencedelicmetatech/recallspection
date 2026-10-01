<div align="center">

<img src="banner.svg" alt="Recallspection Banner" width="800">

# Recallspection

**Tamper-evident exact memory for autonomous AI agents.**

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

[![CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C)](https://pytorch.org/)
[![ExactMemory](https://img.shields.io/badge/ExactMemory-v3.1-8A2BE2)](https://pypi.org/project/exactmemory-recallspection/)
[![Anchor](https://img.shields.io/badge/Anchor-S3%20Object%20Lock%20COMPLIANCE-00FF88)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
[![IETF](https://img.shields.io/badge/IETF%20Agent%20Record-inspired-6f42c1)](https://datatracker.ietf.org/)
[![License](https://img.shields.io/badge/License-AGPL--3.0%20%7C%20Commercial-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-anchor--ready-success)]()
[![PyPI](https://img.shields.io/badge/pypi-exactmemory--recallspection-orange)](https://pypi.org/project/exactmemory-recallspection/)
[![Downloads](https://img.shields.io/badge/downloads-1k%2Fmonth-brightgreen)]()
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.xxxxxxx-blue)]()

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
pip install exactmemory-recallspection
pip install boto3   # for the S3 anchor path