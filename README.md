<p align="center">
  <img src="banner.svg" alt="Recallspection Banner" width="800">
</p>

# 🧠 RECALLSPECTION v18.0.0 – Dual‑Engine Memory Research Prototype

> *Production‑ready cryptographic exact store + research‑grade neural associative memory.*

[![GitHub](https://img.shields.io/badge/GitHub-sciencedelicmetatech%2Frecallspection-blue)](https://github.com/sciencedelicmetatech/recallspection)
[![License](https://img.shields.io/badge/license-AGPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v18.0.0-blue)](https://github.com/sciencedelicmetatech/recallspection)
[![Render](https://img.shields.io/website?url=https%3A%2F%2Frecallspection.onrender.com)](https://recallspection.onrender.com)
[![Live Demo](https://img.shields.io/badge/demo-recallspection.onrender.com-brightgreen)](https://recallspection.onrender.com)
[![API Docs](https://img.shields.io/badge/docs-API-blueviolet)](https://recallspection.onrender.com/docs)
[![ExactMemory](https://img.shields.io/badge/ExactMemory-standalone%20package-blue)](https://github.com/sciencedelicmetatech/exactmemory.recallspection)
[![Patent](https://img.shields.io/badge/Patent-Pending-orange)]()

---

## 📑 Table of Contents

- [What is Recallspection?](#-what-is-recallspection)
- [Quick Comparison](#-quick-comparison)
- [Architecture Overview](#-architecture-overview)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [API Server](#-api-server)
- [Benchmarks & Status](#-benchmarks--status)
- [Project Structure](#-project-structure)
- [Dependencies](#-dependencies)
- [Known Limitations](#-known-limitations)
- [Roadmap](#-roadmap)
- [License & Patent](#-license--patent)
- [References](#-references)
- [Contributing](#-contributing)

---

## 📌 What is Recallspection?

**Recallspection** is a research repository that explores a **dual‑engine memory architecture** for AI agents:

1. **ExactMemory** – a production‑ready, tamper‑evident cryptographic key‑value store.
2. **SWSTM** – a research‑grade neural associative memory that learns to store and retrieve facts with competitive slot addressing and differentiable training.

The core idea: AI agents need **both** a deterministic, auditable memory for facts and a fuzzy, semantic memory for natural language. Recallspection provides a unified API for both – but only ExactMemory is currently production‑ready.

> **⚠️ Important:** The neural components (SWSTM) are **experimental and under active development**. They are not yet production‑ready. For a production‑ready tamper‑proof store, use the separate package [`exactmemory-recallspection`](https://github.com/sciencedelicmetatech/exactmemory.recallspection).

---

## ⚡ Quick Comparison

| Feature | ExactMemory | SWSTM (Neural) |
|---------|-------------|----------------|
| **Purpose** | Cryptographic audit trail | Semantic / fuzzy retrieval |
| **Exact Match Ratio** | 1.0000 (verified) | ≥0.99 on 100 facts (flat mode) |
| **Paraphrase / Fuzzy** | ❌ | ✅ (preliminary, small datasets) |
| **Read Latency** | ~8 µs | ~1 ms (estimate) |
| **Memory per Fact** | ~471 bytes | ~384 bytes (flat) |
| **Tamper‑Evidence** | ✅ HMAC‑SHA3‑256 (16‑byte MAC) | ❌ (neural only) |
| **Dependencies** | None (Python stdlib) | torch, transformers, sklearn |
| **Production Ready** | ✅ Yes (standalone package) | 🧪 Research prototype |
| **Platform** | iOS, Linux, macOS, Windows | Linux, macOS (GPU/CPU) |

---

## 🏗️ Architecture Overview

### ExactMemory (Cryptographic Core) – ✅ Production

- **HMAC‑SHA3‑256** integrity protection (16‑byte MAC) – protects against both accidental corruption **and** malicious tampering (secret key required).
- **zlib compression** (level 6) for space efficiency.
- **TamperDetectedError** exception – distinct from "key not found".
- **Zero external dependencies** – pure Python standard library.
- **Standalone package** available as `exactmemory-recallspection`.
- **Persistence** via `export_state()` / `load_state()` (JSON).

### SWSTM (Neural Core) – 🧪 Research Prototype

| Mode | Status | Capacity (tested) | Accuracy (tested) |
|------|--------|-------------------|-------------------|
| **Flat** | ✅ Working | 100–500 facts | ≥99% (100 facts) |
| **Hierarchical** | ✅ Basic (K‑Means) | Untested | Untested |
| **PQ** | ❌ Placeholder | N/A | N/A |

**Key properties:**
- **Differentiable** – trains with STE (Straight‑Through Estimator) + margin loss.
- **Self‑token** – per‑slot temporal bias to resolve collisions.
- **No dict fallback** – `use_direct_mapping=False` by default (honest neural mode).
- **Persistence** – full state save/load via `save_state()` / `load_state()`.
- **Cosine similarity** – consistent across flat and hierarchical modes.
- **K‑Means routing** – for hierarchical mode (requires manual `fit_router()` call).

---

## 🛠️ Installation

```bash
# Full research package (includes both ExactMemory and SWSTM)
pip install git+https://github.com/sciencedelicmetatech/recallspection.git

# For production use, install ExactMemory only:
pip install exactmemory-recallspection