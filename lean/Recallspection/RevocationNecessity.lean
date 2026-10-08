import Std

/-!
# Revocation Indistinguishability - Deterministic Core

Namespace: Recallspection.Revocation
-/

namespace Recallspection.Revocation

inductive AuthStatus
| valid
| revoked

structure StoreInternal (StoreState Record : Type) where
  decide : StoreState → Record → AuthStatus

structure World (StoreState Record : Type) where
  S : StoreState
  r : Record
  O : AuthStatus

def same_store {StoreState Record : Type}
    (W1 W2 : World StoreState Record) : Prop :=
  W1.S = W2.S ∧ W1.r = W2.r

theorem soundness_impossible
  {StoreState Record : Type}
  (M : StoreInternal StoreState Record)
  (W1 W2 : World StoreState Record)
  (h_same : same_store W1 W2)
  (h_diff : W1.O ≠ W2.O)
  (h_sound_1 : M.decide W1.S W1.r = W1.O)
  (h_sound_2 : M.decide W2.S W2.r = W2.O) :
  False := by
  obtain ⟨hS, hr⟩ := h_same
  rw [hS, hr] at h_sound_1
  exact h_diff (h_sound_1.trans h_sound_2.symm)

end Recallspection.Revocation