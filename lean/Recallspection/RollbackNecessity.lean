import Std

/-!
# Rollback Indistinguishability - Deterministic Core

This file formalizes the deterministic core of Raell's Rollback
Indistinguishability Theorem (Paper 2). It proves that a store-internal
mechanism cannot be sound with respect to an external authority whose
temporal state can take different values for the same store state.

**Scope**: Deterministic core only. The full probabilistic and
computational claim is stated in Paper 2, not here.

No `sorry`. Pinned to leanprover/lean4:v4.11.0.
-/

namespace Recallspection

/-- The store's position in time, as decided by an external anchor. -/
inductive TemporalStatus
| current
| stale

/--
A mechanism is *store-internal* if its output is determined by the
store state and the record alone, with no access to a temporal anchor.
-/
structure StoreInternal (StoreState Record : Type) where
  decide : StoreState → Record → TemporalStatus

/-- A world consists of a store state, a record, and the external
    temporal anchor's verdict. -/
structure World (StoreState Record : Type) where
  S : StoreState
  r : Record
  T : TemporalStatus

/-- Two worlds share a store state and record. -/
def same_store {StoreState Record : Type}
    (W1 W2 : World StoreState Record) : Prop :=
  W1.S = W2.S ∧ W1.r = W2.r

/--
Theorem (Rollback Indistinguishability - Deterministic Core):
A store-internal mechanism cannot be sound in two worlds that share a
store state but disagree on the temporal anchor.
-/
theorem soundness_impossible
  {StoreState Record : Type}
  (M : StoreInternal StoreState Record)
  (W1 W2 : World StoreState Record)
  (h_same : same_store W1 W2)
  (h_diff : W1.T ≠ W2.T)
  (h_sound_1 : M.decide W1.S W1.r = W1.T)
  (h_sound_2 : M.decide W2.S W2.r = W2.T) :
  False := by
  obtain ⟨hS, hr⟩ := h_same
  rw [hS, hr] at h_sound_1
  exact h_diff (h_sound_1.trans h_sound_2.symm)

end Recallspection