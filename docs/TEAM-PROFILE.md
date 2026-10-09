# Tamper-Evident Agent Memory Profile (TEAM)

**Version:** 0.1
**Date:** 8 October 2026
**Status:** Profile specification (self-published)
**Author:** Eliam Raell, Sciencedelic Metatech

---

## Abstract

This document defines a minimal profile for agent memory stores. A
conforming store MUST return the exact value previously stored under a
key, or an explicit integrity failure. Silent substitution, corruption,
or rollback of stored facts is non-conformant.

The profile is the operational form of the necessity theorems in the
Recallspection research program. The contract in Section 3 is what any
store must implement if it is to satisfy the storage-layer guarantees
that Papers 1 through 4 prove are necessary.

---

## 1. Introduction

Autonomous agents increasingly act on stored facts. Existing memory
layers optimize for retrieval relevance. They do not, by default,
guarantee that a returned fact is still the fact that was written.

The four necessity theorems in the Recallspection program establish
that no store-internal mechanism can decide integrity predicates that
depend on external facts:

- **Paper 1** [1]: write-time modification and deletion require a
  write-time key.
- **Paper 2** [2]: rollback requires a temporal anchor.
- **Paper 3** [3]: revocation requires an external authority oracle.
- **Paper 4** [4]: read-path projection integrity requires a
  read-side witness.

This profile specifies the minimum integrity contract for agent memory
used in consequential systems, and the external anchors that make the
contract satisfiable.

---

## 2. Conventions and Definitions

The key words "MUST", "MUST NOT", "SHOULD", and "MAY" in this document
are to be interpreted as described in RFC 2119.

**Exact hit.** A read for a key that was previously written and has not
been deleted. The distinction between a write and a subsequent read is
determined by the store's own write history.

**Non-hit statuses.** A read may also return a status indicating the key
was never written (missing), that the record has expired (expired), or
that the record is administratively invalidated (revoked, tombstoned).
Section 3 does not constrain these statuses; they are governed by the
store's own semantics.

**Integrity failure.** An explicit error indicating the stored record
cannot be authenticated or has been rolled back. A conforming store
MUST signal integrity failure as a distinct outcome from any non-hit
status.

**Silent substitution.** Returning a value different from the last
successfully written value for that key, without signalling an error.

**External anchor.** State outside the store's own state that the store
reads to decide an integrity predicate. Examples: a cryptographic key,
a monotonic counter, an authority signature, a read-side witness.

---

## 3. Core Contract

On an exact hit a conforming store MUST either:

(a) return the exact value last written under that key, or
(b) return an integrity failure.

A conforming store MUST NOT perform silent substitution.

For non-hit statuses (missing, expired, revoked, tombstoned), this
profile does not constrain the return value. A store MAY return any
value or signal, provided it is distinguishable from an exact hit and
from an integrity failure.

---

## 4. Required Protections

A conforming store MUST detect and fail closed on:

- modification of payload or integrity-relevant metadata
- replay of an older valid record under the same key
- deletion of integrity metadata, signalled as an integrity failure
  rather than silent absence

A conforming store MUST detect and fail closed on whole-store rollback
**when an external anchor is configured**. Without an external anchor,
whole-store rollback is undetectable (Paper 2 [2]); the store SHOULD
document this limitation and MUST NOT claim conformance to cross-session
rollback in that configuration.

A conforming store that must detect revocation by an external authority
MUST consult the authority at read time or verify a fresh signature
against state outside the store (Paper 3 [3]).

A conforming store that must detect read-path projection substitution
MUST receive a read-side witness signed by the delivery channel or an
independent monitor, and verify it against the bytes actually received
(Paper 4 [4]). This requirement is provisional pending publication of
Paper 4.

---

## 5. Threat Model (In Scope)

An unauthenticated adversary who can read, write, delete, or replay
stored bytes, but who does not possess the store's secret key material.

Out of scope: compromise of the secret key, physical host control, and
timing side channels.

---

## 6. Conformance

A store claims conformance to this profile only if it passes a
published black-box test suite that attempts modification, replay, and
rollback and verifies that silent substitution never occurs.

A published suite for this purpose means a suite whose source is
publicly available, whose test vectors are reproducible, and whose pass
criteria are documented. The `agmi` conformance suite [5] is one such
suite. Equivalent suites that exercise the same three attack classes
are acceptable, provided they are published under the same conditions.

A store claiming conformance MUST publish the specific suite version it
was tested against and the results of that run.

---

## 7. Security Considerations

Integrity depends on confidentiality of key material. Operators MUST
protect secrets with appropriate key management.

Without an external anchor, cross-session rollback may be undetectable.
This is a known limitation and is stated in Section 4, not a violation
of the core contract in Section 3. The core contract is satisfiable
without an external anchor; the rollback extension is not.

External anchors carry their own trust assumptions. A write-time key
trusts the key holder. A temporal anchor trusts the anchor's clock or
gossip protocol. An authority oracle trusts the authority's signature.
A read-side witness trusts the adapter or monitor that signs it. Each
profile must state its anchor and the trust assumption that anchor
implies.

---

## 8. IANA Considerations

This section is included to preserve the standard document layout. This
document is not an IETF submission and has no IANA actions. Parties
wishing to register a conformance marker for this profile should
propose it through an appropriate venue.

---

## References

[1] Sciencedelic Metatech. *The ExactMemory-Recallspection Integrity
Theorem: Write-Time Commitment for Tamper-Evident Agent Memory.*
Zenodo, version 1.0.0, Oct 2026.
DOI: 10.5281/zenodo.23078584.

[2] Sciencedelic Metatech. *The Rollback Indistinguishability Theorem:
A Machine-Checked Necessity Result for Agent Memory Integrity.*
Zenodo, version 2.0.0, Oct 2026.
DOI: 10.5281/zenodo.23188770.

[3] Sciencedelic Metatech. *The Revocation Indistinguishability
Theorem: External Eligibility Is Necessary for Record Invalidation.*
Zenodo, version 1.0.0, Oct 2026.
DOI: 10.5281/zenodo.23199032.

[4] Sciencedelic Metatech. *The Read-Path Indistinguishability
Theorem: Projection Integrity Requires Read-Side Witnesses.*
Zenodo, forthcoming, Oct 2026.

[5] Tech4biz Solutions. *agmi: Agent Memory Integrity: A Conformance
Test Suite for Tamper Evidence in AI Agent Memory and Checkpoint
Stores.* Zenodo, version 0.6.0, Sept 2026.
DOI: 10.5281/zenodo.22765627.

---

## Author's Address

Eliam Raell,
Sciencedelic Metatech,
Email: eliamraell@yandex.com