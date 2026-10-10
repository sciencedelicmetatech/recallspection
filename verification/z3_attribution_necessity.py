#!/usr/bin/env python3
"""
SMT conformance test for Raell's Attribution Indistinguishability
Theorem (Paper 6).

In-scope: store-internal attributor, identical (S_state, r), differing
causal chains -> UNSAT.

Out-of-scope negative control: attributor enriched with a causal anchor
bit -> SAT.
"""
from z3 import *


def test_attribution_smt():
    print("Testing Attribution Indistinguishability (Z3 SMT)")
    print("=" * 64)

    StoreState = DeclareSort("At_StoreState")
    Record = DeclareSort("At_Record")

    C1 = Bool("at_C1")
    C2 = Bool("at_C2")

    S1 = Const("at_S1", StoreState)
    S2 = Const("at_S2", StoreState)
    R1 = Const("at_R1", Record)
    R2 = Const("at_R2", Record)

    is_agnostic = Function("at_is_agnostic", StoreState, Record, BoolSort())
    M_store = Function("at_M_store", StoreState, Record, BoolSort())

    # In-scope: attributor reads (S_state, r) only.
    s1 = Solver()
    s1.add(S1 == S2)
    s1.add(R1 == R2)
    s1.add(is_agnostic(S1, R1))
    s1.add(is_agnostic(S2, R2))
    s1.add(C1 != C2)
    s1.add(M_store(S1, R1) == C1)
    s1.add(M_store(S2, R2) == C2)
    assert s1.check() == unsat, "expected UNSAT in-scope (attribution)"

    # Negative control: attributor enriched with an anchor bit.
    M_full = Function("at_M_full", StoreState, Record, BoolSort(), BoolSort())
    a1 = Bool("at_anchor1")
    a2 = Bool("at_anchor2")
    s2 = Solver()
    s2.add(S1 == S2)
    s2.add(R1 == R2)
    s2.add(a1 != a2)
    s2.add(C1 != C2)
    s2.add(M_full(S1, R1, a1) == C1)
    s2.add(M_full(S2, R2, a2) == C2)
    assert s2.check() == sat, "expected SAT out-of-scope (attribution)"

    print("PASS: in-scope UNSAT, out-of-scope SAT (causal anchor bit)")


if __name__ == "__main__":
    test_attribution_smt()