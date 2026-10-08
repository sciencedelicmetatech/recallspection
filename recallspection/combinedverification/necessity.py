#!/usr/bin/env python3
"""
Combined necessity verification for the Recallspection program.

Runs the four machine-checked artifacts cited in Paper 2 §10 and
Paper 3 §10:

  [1] Rollback bounded finite-model check    (Paper 2, Existence tier)
  [2] Rollback SMT conformance test          (Paper 2, Structural tier)
  [3] Revocation bounded finite-model check  (Paper 3, Existence tier)
  [4] Revocation SMT conformance test        (Paper 3, Structural tier)

Usage:
    python verification/necessity.py

Exit code 0 on success, 1 on any failure or missing dependency.
"""

import sys


# ============================================================
# [1] Rollback bounded finite-model check  (Paper 2, Existence)
# ============================================================

def rollback_bounded() -> str:
    """
    Enumerate small store-internal mechanisms and confirm that none is
    sound against a rollback predicate whose external anchor (the
    temporal state) is not in the mechanism's input.

    Theorem 3.1 (Paper 2): any mechanism whose input is entirely
    determined by store state cannot decide a predicate that depends on
    the store's position in time.
    """
    states = [0, 1, 2]                 # three representative store states
    outputs = ["Current", "Stale"]     # mechanism's decision alphabet

    mechanisms = []
    for m0 in outputs:
        for m1 in outputs:
            for m2 in outputs:
                mechanisms.append({0: m0, 1: m1, 2: m2})

    def is_sound(M, o1, o2):
        # For each state s, the same store state must yield a decision
        # that matches the external predicate in BOTH worlds. Since the
        # worlds differ (o1 != o2), no single decision can match both.
        for s in states:
            dec = M[s]
            if dec != o1 or dec != o2:
                return False
        return True

    counterexamples = [M for M in mechanisms if is_sound(M, "Current", "Stale")]
    assert not counterexamples, f"theorem violated: {counterexamples}"
    return f"enumerated {len(mechanisms)} mechanisms, 0 sound (Current vs Stale)"


# ============================================================
# [2] Rollback SMT conformance test  (Paper 2, Structural)
# ============================================================

def rollback_smt() -> str:
    """
    Z3 encoding of the rollback impossibility.

    In-scope:  store-internal mechanism, identical store state,
               differing external predicate -> UNSAT.
    Negative:  mechanism enriched with an external anchor bit
               -> SAT.
    """
    from z3 import (
        Bool, BoolSort, Const, DeclareSort, Function, Solver, sat, unsat,
    )

    StoreState = DeclareSort("Rb_StoreState")
    O1 = Bool("rb_O1")
    O2 = Bool("rb_O2")
    S1 = Const("rb_S1", StoreState)
    S2 = Const("rb_S2", StoreState)
    is_agnostic = Function("rb_is_agnostic", StoreState, BoolSort())
    M_store = Function("rb_M_store", StoreState, BoolSort())

    # In-scope: mechanism reads store state only.
    s1 = Solver()
    s1.add(S1 == S2)
    s1.add(is_agnostic(S1))
    s1.add(is_agnostic(S2))
    s1.add(O1 != O2)
    s1.add(M_store(S1) == O1)
    s1.add(M_store(S2) == O2)
    assert s1.check() == unsat, "expected UNSAT in-scope (rollback)"

    # Negative control: mechanism enriched with an external anchor bit.
    M_full = Function("rb_M_full", StoreState, BoolSort(), BoolSort())
    a1 = Bool("rb_anchor1")
    a2 = Bool("rb_anchor2")
    s2 = Solver()
    s2.add(S1 == S2)
    s2.add(a1 != a2)
    s2.add(O1 != O2)
    s2.add(M_full(S1, a1) == O1)
    s2.add(M_full(S2, a2) == O2)
    assert s2.check() == sat, "expected SAT out-of-scope (rollback)"

    return "in-scope UNSAT, out-of-scope SAT (external anchor bit)"


# ============================================================
# [3] Revocation bounded finite-model check  (Paper 3, Existence)
# ============================================================

def revocation_bounded() -> str:
    """
    Same structure as the rollback bounded check, with the external
    predicate being the authority's revocation state rather than the
    temporal anchor.

    Theorem 3.1 (Paper 3): any mechanism whose input is entirely
    determined by store state cannot decide revocation authority.
    """
    states = [0, 1, 2]
    outputs = ["Valid", "Revoked"]

    mechanisms = []
    for m0 in outputs:
        for m1 in outputs:
            for m2 in outputs:
                mechanisms.append({0: m0, 1: m1, 2: m2})

    def is_sound(M, o1, o2):
        for s in states:
            dec = M[s]
            if dec != o1 or dec != o2:
                return False
        return True

    counterexamples = [M for M in mechanisms if is_sound(M, "Valid", "Revoked")]
    assert not counterexamples, f"theorem violated: {counterexamples}"
    return f"enumerated {len(mechanisms)} mechanisms, 0 sound (Valid vs Revoked)"


# ============================================================
# [4] Revocation SMT conformance test  (Paper 3, Structural)
# ============================================================

def revocation_smt() -> str:
    """
    Z3 encoding of the revocation impossibility.

    In-scope:  store-internal mechanism, O-agnostic state, differing
               authority decisions -> UNSAT.
    Negative:  mechanism enriched with an authority signature bit
               -> SAT.
    """
    from z3 import (
        Bool, BoolSort, Const, DeclareSort, Function, Solver, sat, unsat,
    )

    StoreState = DeclareSort("Rv_StoreState")
    O1 = Bool("rv_O1")
    O2 = Bool("rv_O2")
    S1 = Const("rv_S1", StoreState)
    S2 = Const("rv_S2", StoreState)
    is_agnostic = Function("rv_is_agnostic", StoreState, BoolSort())
    M_store = Function("rv_M_store", StoreState, BoolSort())

    # In-scope: mechanism reads store state only.
    s1 = Solver()
    s1.add(S1 == S2)
    s1.add(is_agnostic(S1))
    s1.add(is_agnostic(S2))
    s1.add(O1 != O2)
    s1.add(M_store(S1) == O1)
    s1.add(M_store(S2) == O2)
    assert s1.check() == unsat, "expected UNSAT in-scope (revocation)"

    # Negative control: mechanism enriched with an authority signature bit.
    M_full = Function("rv_M_full", StoreState, BoolSort(), BoolSort())
    sig1 = Bool("rv_sig1")
    sig2 = Bool("rv_sig2")
    s2 = Solver()
    s2.add(S1 == S2)
    s2.add(sig1 != sig2)
    s2.add(O1 != O2)
    s2.add(M_full(S1, sig1) == O1)
    s2.add(M_full(S2, sig2) == O2)
    assert s2.check() == sat, "expected SAT out-of-scope (revocation)"

    return "in-scope UNSAT, out-of-scope SAT (authority signature bit)"


# ============================================================
# Driver
# ============================================================

def main() -> int:
    checks = [
        ("[1] Rollback bounded check     (Paper 2, Existence)",  rollback_bounded),
        ("[2] Rollback SMT conformance   (Paper 2, Structural)", rollback_smt),
        ("[3] Revocation bounded check   (Paper 3, Existence)",  revocation_bounded),
        ("[4] Revocation SMT conformance (Paper 3, Structural)", revocation_smt),
    ]

    print("=" * 68)
    print("Recallspection -- combined necessity verification")
    print("=" * 68)

    failures = 0
    for label, fn in checks:
        print(f"\n{label}")
        try:
            msg = fn()
            print(f"  PASS: {msg}")
        except ImportError:
            print(f"  SKIP: z3-solver not installed (pip install z3-solver)")
            failures += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failures += 1

    print("\n" + "=" * 68)
    if failures:
        print(f"RESULT: {failures} check(s) failed or skipped")
        return 1
    print("RESULT: all 4 checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())