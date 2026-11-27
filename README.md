<div align="center">

<img src="banner.svg" alt="Recallspection Banner" width="800">

# Recallspection

**The Shared Reality Ledger for AI Agents.**

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

> **v18 anchor (outside GitHub):** `0fbd476fb6d82ffd54543cb7bd9ee90140e7d340e269e04cb2cd17ca3101a4e5`
> If repo hash != anchor, anchor wins. Verify with `python recallspection_self.py` - it calls `verify_self(__file__, V18_ANCHOR)`.

> **Constitution:** [The Machine Notary: Cryptographic Intersubjectivity and the Foundation of the Agent Economy](https://doi.org/10.5281/zenodo.24353182)  
> **Architecture:** [Synthetic Intelligence Requires Exact Memory](https://doi.org/10.5281/zenodo.23378369)   
> **Theorems:** [Paper 1](https://doi.org/10.5281/zenodo.23078584) (Contract), [Paper 2](https://doi.org/10.5281/zenodo.23188770) (Rollback), [Paper 3](https://doi.org/10.5281/zenodo.23199032) (Revocation), [Paper 4](https://doi.org/10.5281/zenodo.23254396) (Read-path), [Paper 5](https://doi.org/10.5281/zenodo.23263748) (Framework), [Paper 6](https://doi.org/10.5281/zenodo.23288111) (Attribution).  
> **Spec:** [RPRS-1 v2.0.0](spec/rprs-1.tex) normative contract.

[[CI](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/ci.yml)
[[Conformance](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/conformance.yml/badge.svg)](https://github.com/sciencedelicmetatech/recallspection/actions/workflows/conformance.yml)
[[Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[[FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[[PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[[ExactMemory](https://img.shields.io/badge/ExactMemory-v3.3-8A2BE2)](https://github.com/sciencedelicmetatech/exactmemory.recallspection)
[[Anchor](https://img.shields.io/badge/Anchor-file%20%7C%20S3%20Object%20Lock-00FF88)](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
[[Lean 4](https://img.shields.io/badge/Lean-4.11.0-6b4e9e?logo=lean&logoColor=white)](https://leanprover.github.io/)
[[Z3](https://img.shields.io/badge/Z3-SMT-8A2BE2)](https://github.com/Z3Prover/z3)
[[License](https://img.shields.io/badge/License-AGPL--3.0%20%2F%20RIL-blue)](LICENSE)
[[Status](https://img.shields.io/badge/status-Intersubjective%20Witness-success)]()
[[DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.24353182-blue?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.24353182)
[[agmi: L4](https://img.shields.io/badge/agmi-L4%20Conformant-0F4C5C)](https://agentmemoryintegrity.org/stores/recallspection-exact-anchor.html)
</div>

---

## We don't prove objective truth. We prove intersubjective reality.

Gravity is objective. It doesn't care if you believe in it.
Money, laws, contracts, and nations are **intersubjective**. They exist only because we all agree they exist, and we have witnesses (notaries, courts, ledgers) to prove we didn't change the agreement.

Right now, AI agents have no shared witness. Ten billion agents live in ten billion subjective worlds. They hallucinate balances. They forge contracts. They rewrite history. They cannot trade, sign law, or form society because they cannot prove that they share the same reality as anyone else.

**Recallspection is the machine witness for the agent economy.** 
It doesn't say, "This is objectively true." It says, *"We all saw this fact at this time, we anchored it, and nobody changed it after without everyone knowing."*

We are building the missing layer that allows agents to have money, law, history, and society. 

*Read the full policy, economic, and philosophical framework in [The Machine Notary](https://doi.org/10.5281/zenodo.24353182).*

---

## The Problem: The Solipsistic Swarm

Current AI architectures conflate fuzzy reasoning with fuzzy memory. Single-slot memory (Mem0 / Zep style) under 5x overload collapses:

| Store | Recall | Silent wrong | Notes |
|---|---:|---:|---|
| Naive single-slot (our baseline) | 19.84 % | 80.16 % | No key routing; vector index only. |
| SWSTM Bucket-8 | 97.45 % | 0 % | Bucketed routing, no exact-first short-circuit. |
| **Recallspection (exact-first hybrid)** | **100 %** | **0 %** | Exact key hit bypasses the vector index entirely. |

Under load, naive stores return another key's fact 80 % of the time. Recallspection never silently swaps facts. It guarantees that you and your agent live in the same world.

---

## Conformance

Recallspection ExactMemory (anchored) has officially achieved **Level L4 on the Agent Memory Integrity (AGMI) benchmark**, the highest standard for memory integrity. 

The AGMI suite tested ten storage-level edits. Recallspection rejected **10 out of 10** on the read path: 0 edits were served as genuine, and 0 were merely reported on audit. 

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
| **T10 erasure resurrection** | **rejected on read** |

**10 rejected, 0 accepted, 0 errors.**  
Official Result: [AGMI L4 Conformance](https://agentmemoryintegrity.org/stores/recallspection-exact-anchor.html)

### Scope of the claim

The core read path refuses every edit against the same threat model agmi specifies: an attacker who can write the on-disk bytes but holds no keys. A drop-in adapter for the upstream suite lives at `recallspection/conformance/agmi_adapter.py`.

T9 (snapshot rollback) is enforced by an external high-water-mark anchor. In production, set `RECALLSPECTION_ANCHOR_BACKEND=file|s3`. Without an anchor, T9 is accepted. The official L4 result applies to the anchored configuration.

---

## Mandate: The Notary Enforces the Rules

Memory alone does not make an agent safe. An agent also needs a mandate: what it is allowed to do, and what is forbidden.

Mandate does not live in the LLM prompt. It does not live in the agent's fuzzy memory. It lives in the Notary, outside the agent, as a signed, anchored constraint.

```
recallspection/
  mandate.py  - Mandate: signed constraint, allowed_keys, denied_sources, limits, expiry
  notary.py   - MachineNotary: the Warden, verifies mandate every call
  client.py   - NotaryClient: the only file the agent imports, JSON pipe only
  store.py    - ExactStore / NotaryStore: get(k) = value or Err(Tamper)
```

Agent proposes. Notary disposes.

- amount > max = forbidden -> Err(Limit)
- type not in scope = forbidden -> Err(Scope)
- source denied = forbidden -> Err(Scope)
- expired = forbidden -> Err(Expired)
- memory tampered = forbidden -> Err(Tamper)
- mandate signature mismatch = forbidden -> Err(Tamper)

Run it:

```bash
python recallspection/test_notary.py
```

Expected: allowed trade passes, kyc_ahmad refused, email source refused, $999 over limit refused, tampered memory refused.

One repo. Two runtimes. Zero trust in the agent.

---

## Portable Proof: We lock the truth in, not you in.

Traditional security vendors lock you in. Recallspection uses **Portable Proof**. Because it is built on the `exactmemory` core, you can export a cryptographic bundle of your entire store, including the transparency log and the anchor receipts.

The bundle is verifiable offline. It works across clouds. It survives the death of the original server. If you move from AWS to GCP, you take the truth with you, and the new anchor signs the old tip. 

```python
from exactmemory.portable import export_bundle, import_bundle, reanchor

# Export a verifiable bundle
export_bundle(store, "backup.portable", anchor=s3_anchor)

# Import elsewhere (verifies MAC, tags, monotonicity, and cross-anchor)
import_bundle(new_store, "backup.portable", anchor=new_s3_anchor)

# Migrate to a new anchor (cross-anchor ceremony)
reanchor(store, old_anchor, new_anchor)
```
