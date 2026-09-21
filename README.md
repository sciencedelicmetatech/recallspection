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