# IETF Agent Record Status

## Summary

In August 2026 the IETF published an Informational draft, `draft-maintainer-1f916-agent-record-00`, describing a signed append-only record format for AI agents: key-binding events, Merkle checkpoints over an RFC 6962 log, countersigned witnesses, memory seals, attestations, and offline-verifiable dossiers.

It is **not an RFC**. It carries no formal standards-process standing. It is one registry's deployed wire format, published to invite independent implementation.

Recallspection emits records in the same **shape** — signed envelope, hash chain, checkpoint, dossier export — and **not in the same signature algorithm**.

---

## Signature Algorithm: HMAC-SHA256 Now, Ed25519 Opt-In

The draft requires Ed25519. Python's standard library does not provide it, and Recallspection's core constraint is **zero dependencies** — the engine runs on iOS (Pythonista / Pyto) where `pip install` is not available.

| | HMAC-SHA256 (shipped) | Pure-Python Ed25519 (draft requirement) |
|---|---|---|
| Per-operation cost | ~5–20 µs | ~2.8 ms sign / ~10.8 ms verify (desktop, pure-Python reference) |
| Dependencies | standard library only | vendored implementation required |
| Mobile CPU class | unchanged | estimated 2–4 orders of magnitude slower per operation |

Paying that on every `put()` would break the property that makes ExactMemory useful on edge devices. So:

- **Today:** records are signed with HMAC-SHA256, in the Agent Record wire shape.
- **On request:** an Ed25519 signing mode is added for **checkpoints only** (once per session), which is where the interoperability value actually sits — not per-write.
- **Always declared:** every exported dossier states its own algorithm and its own compliance status. Nothing is presented as verified when it is not.

```json
{
  "record": "1f916.record.v1:<sha256_hex>",
  "sig_algo": "hmac-sha256",
  "compliance": "agent-record-inspired, not agent-record-compliant"
}