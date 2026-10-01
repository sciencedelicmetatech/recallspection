# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 18.0.x  | ✅ Active |
| < 18.0  | ❌ Unsupported |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately to: **eliamraell@yandex.com**

Include:

- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Any proof-of-concept code
- Your assessment of impact

**Response timeline:**

| Stage | Target |
|---|---|
| Acknowledgement | 72 hours |
| Initial assessment | 7 days |
| Fix or mitigation | 30 days |
| Public disclosure | Coordinated with reporter |

We credit reporters in release notes unless anonymity is requested.

---

## Threat Model

Recallspection protects against an **unauthenticated adversary** who can:

- Read any wire bytes
- Write well-formed bytes at any key
- Delete wire bytes
- Replay previously observed wire bytes

The adversary does **not** hold secret key material. If `RECALLSPECTION_EXACT_SECRET` is compromised, HMACs can be forged — that is the threat model boundary.

**Out of scope:**

- Authenticated adversaries holding the master key
- Timing side channels
- Byzantine coordinators
- Physical access to the host machine

---

## What Is Detected

| Attack Class | Detection Mechanism |
|---|---|
| Payload tampering | Per-record HMAC-SHA256 tag |
| Metadata modification | Tag binds all fields jointly |
| Record substitution | Key bound into tag |
| Replay of old versions | Monotonic version counter + per-key high-water mark |
| Deletion attack | Tombstone + container MAC |
| Whole-container rollback | Transparency log + S3 Object Lock anchor |
| Wrong-agent-key access | Key identifier bound into tag |

**Detection rate:** 100 % across 85 attacks in the integrity attack suite.  
**Silent failure rate:** 0 %.

---

## Cryptographic Primitives

| Primitive | Algorithm | Purpose |
|---|---|---|
| Per-record MAC | HMAC-SHA256 | Binds every record field into a 32-byte tag |
| Container MAC | HMAC-SHA256 | Binds full container state into one tag |
| Hash chain | SHA3-256 | Transparency log (`prev_hash` linkage) |
| Merkle root | SHA3-256 | Anchor commitment over log |
| Constant-time compare | `hmac.compare_digest` | Prevents timing leaks on secret comparison |

All primitives are available in the Python standard library. No third-party crypto dependencies.

---

## Rollback Protection

The transparency log proves records have not been modified. It does **not** prove that a whole authentic container has not been replaced with an earlier authentic one. That requires an external witness.

**Local rollback** (within a session) is caught by the `prev_hash` chain and `max_version` check.

**Cross-session rollback** is caught by the S3 Object Lock anchor:

- On every `POST /anchor`, the Merkle root of `transparency.log` is written to S3 with **COMPLIANCE** mode.
- Even the bucket owner cannot delete or modify the anchor before the retain-until date.
- The client retains the last observed log head `ρ` and verifies both local consistency and anchor consistency on read.

Without an anchor, cross-session rollback is **undetectable**. This is a proven limitation, not a bug.

---

## Known Gaps

| Gap | Boundary | Mitigation |
|---|---|---|
| Master secret compromise | HMACs forgeable | External KMS + S3 anchor closes the loop |
| Authenticated adversary | Checkpoint-level attribution only | Ed25519 checkpoint signing (roadmap) |
| Timing side channels | Constant-time assumed, not measured | Future work |
| Retention expiry | Object Lock retention is a deployment parameter | Re-anchor before expiry |
| Bootstrapping | First read in a fresh deployment cannot distinguish current from prior | Pre-populate the anchor |
| Trusted clock | Rollback detection assumes a trusted clock or authenticated anchor oracle | Deploy with trusted NTP or signed anchor responses |

---
Disclosure Policy
 
We follow coordinated disclosure:
1. Reporter submits privately.
2. We acknowledge within 72 hours.
3. We confirm and assess within 7 days.
4. We develop and test a fix.
5. We coordinate a disclosure date with the reporter.
6. We publish a security advisory and credit the reporter. 
We will not pursue legal action against researchers acting in good faith.

---

## Security-Relevant Configuration

**Required in production:**

```bash
RECALLSPECTION_EXACT_SECRET="<32-byte secret>"
RECALLSPECTION_ADMIN_KEY="<random key>"
RECALLSPECTION_SIGNUP_SECRET="<random secret>"