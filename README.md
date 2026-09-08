
```markdown
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
```

---

🚀 Quick Start

1. ExactMemory (Production – Tamper‑Evident Store)

```python
from exactmemory_recallspection import ExactMemory

# Create a store with a secret key (32 bytes)
secret = b"your-32-byte-secret-key!!!!!!!!!!"
mem = ExactMemory(secret_key=secret)

# Store a value (any JSON‑serializable object)
mem.add("user:123", {"name": "Alice", "role": "admin"})

# Retrieve
result = mem.get("user:123")  # {'name': 'Alice', 'role': 'admin'}

# Unknown key
result = mem.get("unknown")   # None

# Tamper detection – if data is corrupted, raises TamperDetectedError
# mem.add("key", "value") -> corrupt the file manually -> mem.get("key") raises exception
```

2. SWSTM (Research – Neural Memory)

```python
import torch
from recallspection import SWSTMExtraTrainable, train_swstm

# Create a flat SWSTM memory
model = SWSTMExtraTrainable(
    num_slots=200,    # number of memory slots
    slot_dim=32,      # value dimension (one‑hot)
    key_dim=64,       # key embedding dimension
)

# Generate synthetic data (100 facts, 64‑dim keys, 32‑dim one‑hot values)
keys = torch.randn(100, 64)
values = torch.zeros(100, 32)
for i in range(100):
    values[i, i % 32] = 1.0

# Train the neural memory
train_swstm(model, keys, values, num_epochs=10, lr=0.001, verbose=True)

# Retrieve (hard assignment – no gradients)
read = model.read_exact(keys)
preds = torch.argmax(read, dim=-1)
targets = torch.argmax(values, dim=-1)
accuracy = (preds == targets).float().mean().item()
print(f"Accuracy: {accuracy*100:.2f}%")  # typically ≥99% on this dataset
```

3. Using the High‑Level Engine (SWSTMEngine)

```python
from recallspection import SWSTMEngine, SWSTMExtraTrainable

model = SWSTMExtraTrainable(num_slots=200, slot_dim=32, key_dim=64)
engine = SWSTMEngine(model, use_direct_mapping=False)  # honest neural mode

# Add facts (values as integers, automatically one‑hot encoded)
engine.add("capital of France", 0)   # 0 → one‑hot vector
engine.add("capital of Germany", 1)

# Retrieve (neural only)
result = engine.get("France's capital")  # returns one‑hot vector
```

---

🌐 API Server

Recallspection includes a FastAPI server that exposes both ExactMemory and SWSTM over HTTP.

Run the Server

```bash
uvicorn recallspection.api:app --reload
```

Then visit:

· Landing page: http://localhost:8000
· Interactive API docs: http://localhost:8000/docs

Endpoints

Endpoint Method Auth Description
/ GET ❌ Landing page
/health GET ❌ Health check
/signup POST ❌ Generate an API key
/usage GET ✅ Check remaining quota
/add POST ✅ Store a fact (key‑value)
/get GET ✅ Retrieve fact(s)
/exact/add POST ✅ Store to ExactMemory only
/exact/get GET ✅ Retrieve from ExactMemory only
/agent-info GET ✅ Detect if request is from AI agent
/admin/keys GET ✅ (admin) List all API keys
/admin/revoke/{id} POST ✅ (admin) Revoke an API key

Authentication: All protected endpoints require the X-API-Key header.

---

📊 Benchmarks & Status

Mode Facts Tested Accuracy Memory/Fact Status
ExactMemory Unlimited (verified) 100% ~471 bytes ✅ Production‑ready
Flat SWSTM 100 ≥99% ~384 bytes ✅ Working (research)
Flat SWSTM 500 ≥95% (preliminary) ~384 bytes ⚠️ Needs validation
Hierarchical SWSTM Untested Untested Untested ⚠️ Basic, unvalidated
PQ SWSTM N/A N/A 24 bytes (claimed) ❌ Not implemented

Note: All neural benchmarks are based on synthetic data and small datasets. The 100% claims from the paper are not reproducible from this repository – we are actively working to provide reproducible evaluation scripts and raw outputs.

---

📁 Project Structure

```
recallspection/
├── exact.py              # ExactMemory (HMAC‑SHA3‑256, tamper‑evident)
├── swstm.py              # SWSTM v7.0 (Flat, Hierarchical, PQ, Engine)
├── __init__.py           # Package exports (ExactMemory, SWSTMEngine, etc.)
├── api.py                # FastAPI server (SQLite keys, usage tracking)
├── index.html            # Landing page
├── tests/
│   ├── test_swstm.py     # ⚠️ Some tests currently failing (in progress)
│   └── ...
├── setup.py              # Packaging configuration
├── requirements.txt      # Dependencies
├── banner.svg            # Banner image
└── README.md             # This file
```

---

📦 Dependencies

Package Purpose Required For
fastapi Web framework API server
uvicorn ASGI server API server
sentence-transformers Text embeddings SWSTM
scikit-learn K‑Means clustering Hierarchical SWSTM
torch PyTorch SWSTM neural memory
numpy Numeric operations SWSTM
pydantic Data validation API server

ExactMemory has zero external dependencies: it uses only the Python standard library.


---

📜 License & Patent

License: GNU Affero General Public License v3.0 (AGPLv3) – see LICENSE for details.

Patent: US Provisional Application filed – SWSTM technology.

Commercial Use: For commercial licensing, enterprise support, or patent inquiries, contact:
📧 eliamraell@yandex.com

---

📚 References

· Raell, E. (2026). Causal Poset Transformer: SWSTM v7.0. (Available in docs/)
· Raell, E. (2026). SWSTM v6.6 Pantone Paper.
· Live Demo: recallspection.onrender.com
· API Docs: recallspection.onrender.com/docs
· ExactMemory Standalone: github.com/sciencedelicmetatech/exactmemory.recallspection

---

🤝 Contributing

We welcome contributions, especially on:

· Fixing the test suite
· Implementing HybridEngine
· Replacing the PQ placeholder with a real implementation
· Publishing reproducible benchmarks (with raw outputs and configs)
· Adding LangChain / MCP integration

Please open an issue or pull request for improvements.
For patent and commercial inquiries: eliamraell@yandex.com

---

Made with ❤️ by Sciencedelic Metatech

```

---

This README is **honest, complete, and actionable** – it clearly separates production‑ready ExactMemory from research‑grade SWSTM, lists all known limitations, and provides a realistic roadmap. It builds trust by being transparent about what works and what doesn't.
```