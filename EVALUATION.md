# Evaluation

All numbers below are reproducible with the commands shown. No external model downloads required.

Run everything:

    pytest tests/ -v --cov=recallspection
    python tests/test_integrity_attack_suite.py
    python tests/test_swstm_collision.py

---

## 1. Integrity Attack Suite

Self-contained. Embeds the patched ExactMemory v3.0.1 core directly.

Command:

    python tests/test_integrity_attack_suite.py

### ExactMemory (HMAC-SHA256 + version counter + container MAC)

| Attack | Attempts | Detected | DR | SFR |
|---|---:|---:|---:|---:|
| bitflip_hmac_tag | 10 | 10 | 100% | 0% |
| payload_rewrite | 15 | 15 | 100% | 0% |
| replay_old_version | 10 | 10 | 100% | 0% |
| direct_store_removal | 10 | 10 | 100% | 0% |
| wrong_agent_key | 40 | 40 | 100% | 0% |
| s3_midpoint_mutation | 10 | 10 | 100% | 0% |

### Naive JSON store (what Mem0 / Zep / Letta / OpenClaw use today)

| Attack | DR | SFR |
|---|---:|---:|
| bitflip_hmac_tag | 0% | 100% (silent wrong) |
| payload_rewrite | 0% | 100% (silent wrong) |
| replay_old_version | 0% | 100% (silent wrong) |
| direct_store_removal | 0% | 100% (silent wrong) |

### Attack meanings

| Attack | Simulates | Naive JSON | ExactMemory |
|---|---|---|---|
| bitflip_hmac_tag | Disk corruption / file edit | 100% silent wrong | 100% detected |
| payload_rewrite | GhostWriter / MemGhost email injection | 100% silent wrong | 100% detected |
| replay_old_version | Restore old backup / eTAMP | 100% silent wrong | 100% detected |
| direct_store_removal | Deletion attack | 100% silent missing | 100% tampered |
| wrong_agent_key | Key compromise / tenant isolation failure | 0% | 100% detected |
| s3_midpoint_mutation | Wipe /data and local log | 0% | 100% detected (with anchor) |

DR = detection rate (higher is better).  
SFR = silent failure rate (returns wrong data with no error).

The naive store is literally `store[k] = v`. That is what MEMORY.md does today.

---

## 2. SWSTM Collision Resistance Stress Test

Config: 2,000 slots, 10,000 facts, average load 5.0, maximum load 14 per slot, deterministic SHA-256 slot mapping.

Command:

    python tests/test_swstm_collision.py

| Engine | Collisions | Evictions | Correct Recall | Silent wrong |
|---|---:|---:|---:|---:|
| Naive single-slot (Mem0/Zep style) | 8,016 | 8,016 overwrites | 1,984 / 10,000 (19.8%) | 80.2% returns WRONG fact |
| Bucketed cap=5 (SWSTM) | 8,016 | 1,779 | 8,221 / 10,000 (82.2%) | 0% |
| Bucketed cap=8 | 8,016 | 255 | 9,745 / 10,000 (97.5%) | 0% |
| Hybrid exact-first (Recallspection) | — | 0 | 10,000 / 10,000 (100%) | 0% |

### Load curve (recall vs facts inserted)

| Facts | Naive recall | Bucket cap=5 |
|---:|---:|---:|
| 2,000 | 62.8% | 100% |
| 4,000 | 43.0% | 99.1% |
| 6,000 | 31.6% | 95.4% |
| 8,000 | 24.5% | 89.6% |
| 10,000 | 19.8% | 82.2% |

### Interpretation

Single-slot memory has catastrophic forgetting; the last writer wins per slot. Without an exact-key check, it returns another key's fact 80.2% of the time — the failure mode HaluMem describes. Bucketed slots delay forgetting by 4–5×. The hybrid guarantees 100% for stored facts because ExactMemory never forgets; SWSTM is only for the fuzzy / semantic fallback path.

---

## 3. Optional Card Search (in-house, not LoCoMo)

MiniLM over one-fact cards, new-domain paraphrases, n = 242.

| Metric | Value |
|---|---|
| Key@1 | 86% (95% CI ≈ 81–90%) |
| Key@3 | 95% (95% CI ≈ 91–97%) |
| Value leak | 0 |

Fuzzy payload contains keys only. This measures retrieval of keys, not end-to-end chat QA. Do not compare it to vendor LoCoMo headlines.

---

## 4. Performance

Environment: Python 3.11, single process, single thread, commodity laptop CPU, no network.

Latencies in microseconds, p50 / p99 over the full population at each scale. save/load are wall-clock milliseconds per call.

| Scale | add p50 | add p99 | get p50 | get p99 | save (ms) | load (ms) | bytes/record |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 11.71 | 18.42 | 9.17 | 16.62 | 2.37 | 2.44 | 84.7 |
| 1,000 | 11.54 | 32.33 | 9.33 | 23.04 | 9.34 | 3.13 | 83.0 |
| 10,000 | 11.37 | 26.38 | 9.25 | 12.25 | 78.50 | 69.81 | 82.8 |

**Hot path is flat in scale.** add p50 moves 11.71 → 11.37 µs across a 100× increase in record count; get p50 moves 9.17 → 9.25 µs. This is the empirical content of the O(1) claim.

**Cold path is linear.** save at 10,000 is 78.50 ms vs 9.34 ms at 1,000; load at 10,000 is 69.81 ms. Neither is on the hot path, and neither affects the O(1) claim.

**Storage.** bytes/record is stable at ~83 across all scales. The wire-format overhead amortizes to a fixed cost per record.

---

## 5. Rollback Detection

| Scenario | Adversary capability | Detection source | Result |
|---|---|---|---|
| E3a | Container rolled back; log retained | log tip vs max_version | RollbackError |
| E3b | Container and log rolled back; anchor retained | anchor max_version vs log tip | RollbackError |

E3a is detected without an anchor because the log is a separate file. E3b requires the anchor: an adversary rolling back both produces an internally consistent history, and only state outside the client's control distinguishes it from the honest prior state.

This is the empirical confirmation of the rollback necessity theorem.

---

## 6. Threats to Validity

- Single environment. Absolute constants are not claimed to generalize.
- Experiment 4 is single-run.
- Embedded core rather than installed distribution.
- Synthetic workload with small records.
- No adversarial timing; constant-time behavior of hmac.compare_digest is assumed, not measured.

---

## 7. Reproducing

    git clone https://github.com/sciencedelicmetatech/recallspection.git
    cd recallspection
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    pytest tests/ -v --cov=recallspection
    python tests/test_integrity_attack_suite.py
    python tests/test_swstm_collision.py

Companion paper: The ExactMemory-Recallspection Integrity Theorem — https://doi.org/10.5281/zenodo.23078584