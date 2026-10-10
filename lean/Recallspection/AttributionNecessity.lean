import Std

/-!
# Attribution Indistinguishability - Deterministic Core

This file formalizes the deterministic core of Raell's Attribution
Indistinguishability Theorem (Paper 6). It proves that a store-internal
attributor cannot be sound with respect to an external causal chain that
can take different values for the same local record.

**Scope**: Deterministic core only. The full information-theoretic claim
of Paper 6 is stated in the paper, not here.

No `sorry`. Pinned to leanprover/lean4:v4.11.0.
-/

namespace Recallspection.Attribution

/-- The causal chain verdict for a record: whether it was genuinely
    caused by the agent's internal state. -/
inductive CausalVerdict
| attributed
| unattributed

/--
A mechanism is *store-internal* if its output is determined by the store
state and the record alone, with no access to the external causal chain.
-/
structure StoreInternal (StoreState Record : Type) where
  decide : StoreState → Record → CausalVerdict

/-- A world consists of a store state, a record, and the external
    causal chain's verdict. -/
structure World (StoreState Record : Type) where
  S : StoreState
  r : Record
  C : CausalVerdict

/-- Two worlds share a store state and record. -/
def same_record {StoreState Record : Type}
    (W1 W2 : World StoreState Record) : Prop :=
  W1.S = W2.S ∧ W1.r = W2.r

/--
Theorem (Attribution Indistinguishability - Deterministic Core):
A store-internal attributor cannot be sound in two worlds that share a
store state and record but disagree on the causal chain.
-/
theorem soundness_impossible
  {StoreState Record : Type}
  (M : StoreInternal StoreState Record)
  (W1 W2 : World StoreState Record)
  (h_same : same_record W1 W2)
  (h_diff : W1.C ≠ W2.C)
  (h_sound_1 : M.decide W1.S W1.r = W1.C)
  (h_sound_2 : M.decide W2.S W2.r = W2.C) :
  False := by
  obtain ⟨hS, hr⟩ := h_same
  rw [hS, hr] at h_sound_1
  exact h_diff (h_sound_1.symm.trans h_sound_2)

end Recallspection.Attribution