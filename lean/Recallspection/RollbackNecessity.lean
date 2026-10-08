import Std

/-!
# Rollback Indistinguishability - Deterministic Core

Namespace: Recallspection.Rollback
-/

namespace Recallspection.Rollback

inductive TemporalStatus
| current
| stale

structure StoreInternal (StoreState Record : Type) where
  decide : StoreState → Record → TemporalStatus

structure World (StoreState Record : Type) where
  S : StoreState
  r : Record
  T : TemporalStatus

def same_store {StoreState Record : Type}
    (W1 W2 : World StoreState Record) : Prop :=
  W1.S = W2.S ∧ W1.r = W2.r

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

end Recallspection.Rollback