import Std

/-!
# Meta-Framework for Mechanism-External Predicates

This file formalizes the abstract framework that underlies the
necessity theorems of the Recallspection program (Papers 1 through 6).

The formal content of the framework is a functional tautology: a
mechanism whose input is determined by its input alone cannot decide a
predicate that depends on external state. The contribution of the
framework is the characterization (a deciding mechanism must factor
through the externality profile) and the taxonomy (content predicates
have unbounded profiles; metadata predicates are bounded).

This artifact does not re-prove the full cryptographic reductions of
the four storage papers. It establishes the *structural* claim: the
predicates share a common framework, and their externality profiles
fall into the two classes of the taxonomy.

No `sorry`. Pinned to leanprover/lean4:v4.11.0.
-/

namespace Recallspection.Meta

/-! ## Abstract framework -/

/-- A predicate ranges over a mechanism input and external state. -/
abbrev Predicate (I E : Type) := I → E → Bool

/-- A mechanism-internal decision reads only the input. -/
abbrev MechanismInternal (I : Type) := I → Bool

/-- A mechanism decides a predicate when it agrees with it on all worlds. -/
def Decides {I E : Type} (M : MechanismInternal I) (P : Predicate I E) : Prop :=
  ∀ i e, M i = P i e

/-- A predicate is mechanism-external when it distinguishes two external
    states for the same input. -/
def MechanismExternal {I E : Type} (P : Predicate I E) : Prop :=
  ∃ i e e', P i e ≠ P i e'

/-- The trivial core: no mechanism-internal decision decides a
    mechanism-external predicate. -/
theorem impossibility {I E : Type} (P : Predicate I E)
    (h : MechanismExternal P) :
    ¬ ∃ M : MechanismInternal I, Decides M P := by
  rintro ⟨M, hM⟩
  obtain ⟨i, e, e', hdiff⟩ := h
  have h1 : M i = P i e := hM i e
  have h2 : M i = P i e' := hM i e'
  rw [h1] at h2
  exact hdiff h2

/-! ## Externality profiles and the taxonomy -/

/-- P-equivalence on external state. -/
def PEquiv {I E : Type} (P : Predicate I E) (e₁ e₂ : E) : Prop :=
  ∀ i : I, P i e₁ = P i e₂

/-- Bounded profile: at most two P-classes over the external state. -/
def BoundedProfile {I E : Type} (P : Predicate I E) : Prop :=
  ∀ e₁ e₂ e₃ : E,
    PEquiv P e₁ e₂ ∨ PEquiv P e₁ e₃ ∨ PEquiv P e₂ e₃

/-- Unbounded profile: at least three distinct P-classes. -/
def UnboundedProfile {I E : Type} (P : Predicate I E) : Prop :=
  ∃ e₁ e₂ e₃ : E,
    ¬ PEquiv P e₁ e₂ ∧ ¬ PEquiv P e₁ e₃ ∧ ¬ PEquiv P e₂ e₃

/-! ## The instance predicates -/

/-- Paper 2 (rollback): input is store state, external state is the
    temporal anchor's verdict. -/
def P_rollback (_ : Bool) (t : Bool) : Bool := t

/-- Paper 3 (revocation): input is store state, external state is the
    authority's decision. -/
def P_revocation (_ : Bool) (a : Bool) : Bool := a

/-- Paper 1 (modification): input is stored bytes, external state is the
    original bytes. -/
def P_content (stored : Nat) (original : Nat) : Bool := stored == original

/-- Paper 4 (read path): input is stored bytes, external state is the
    delivered payload. -/
def P_readpath (stored : Nat) (delivered : Nat) : Bool := stored == delivered

/-! ### Each instance is mechanism-external -/

theorem rollback_external : MechanismExternal P_rollback :=
  ⟨false, false, true, by decide⟩

theorem revocation_external : MechanismExternal P_revocation :=
  ⟨false, false, true, by decide⟩

theorem content_external : MechanismExternal P_content :=
  ⟨0, 0, 1, by decide⟩

theorem readpath_external : MechanismExternal P_readpath :=
  ⟨0, 0, 1, by decide⟩

/-! ### Taxonomy: bounded and unbounded profiles -/

theorem rollback_bounded : BoundedProfile P_rollback := by
  intro e₁ e₂ e₃
  cases e₁ <;> cases e₂ <;> cases e₃
  · exact Or.inl (fun _ => rfl)
  · exact Or.inl (fun _ => rfl)
  · exact Or.inr (Or.inl (fun _ => rfl))
  · exact Or.inr (Or.inr (fun _ => rfl))
  · exact Or.inr (Or.inr (fun _ => rfl))
  · exact Or.inr (Or.inl (fun _ => rfl))
  · exact Or.inl (fun _ => rfl)
  · exact Or.inl (fun _ => rfl)

theorem revocation_bounded : BoundedProfile P_revocation := by
  intro e₁ e₂ e₃
  cases e₁ <;> cases e₂ <;> cases e₃
  · exact Or.inl (fun _ => rfl)
  · exact Or.inl (fun _ => rfl)
  · exact Or.inr (Or.inl (fun _ => rfl))
  · exact Or.inr (Or.inr (fun _ => rfl))
  · exact Or.inr (Or.inr (fun _ => rfl))
  · exact Or.inr (Or.inl (fun _ => rfl))
  · exact Or.inl (fun _ => rfl)
  · exact Or.inl (fun _ => rfl)

theorem content_unbounded : UnboundedProfile P_content := by
  refine ⟨0, 1, 2, ?_, ?_, ?_⟩
  · intro h; exact absurd (h 0) (by decide)
  · intro h; exact absurd (h 0) (by decide)
  · intro h; exact absurd (h 1) (by decide)

theorem readpath_unbounded : UnboundedProfile P_readpath := by
  refine ⟨0, 1, 2, ?_, ?_, ?_⟩
  · intro h; exact absurd (h 0) (by decide)
  · intro h; exact absurd (h 0) (by decide)
  · intro h; exact absurd (h 1) (by decide)

end Recallspection.Meta