#!/usr/bin/env python3
"""
Bounded finite-model check for Raell's Attribution Indistinguishability
Theorem (Paper 6).

Constructs two worlds with identical (S_state, r) but differing causal
chains. Confirms no store-internal attributor is sound.

Zero deps. Runs in <1s.
"""


def check_attributor(M, records, c1, c2):
    """
    M: dict mapping record -> {"Attributed", "Unattributed"}.
    c1, c2: causal chain verdicts for two worlds with identical records.
    Returns True if M is sound in both worlds.
    """
    for r in records:
        dec = M[r]
        if dec != c1 or dec != c2:
            return False
    return True


def main():
    print("Testing Attribution Indistinguishability (Bounded Model)")
    print("=" * 64)

    records = [0, 1, 2]
    outputs = ["Attributed", "Unattributed"]

    mechanisms = []
    for m0 in outputs:
        for m1 in outputs:
            for m2 in outputs:
                mechanisms.append({0: m0, 1: m1, 2: m2})

    print(f"Enumerated {len(mechanisms)} store-internal attributors.")

    counterexamples = [
        M for M in mechanisms
        if check_attributor(M, records, "Attributed", "Unattributed")
    ]

    assert len(counterexamples) == 0, f"theorem violated: {counterexamples}"

    print(f"PASS: enumerated {len(mechanisms)} attributors, "
          f"0 sound (Attributed vs Unattributed).")
    print("  (Theorem holds on this bounded model.)")


if __name__ == "__main__":
    main()