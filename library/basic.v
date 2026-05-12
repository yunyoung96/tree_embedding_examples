Theorem same: 0 = 0.
Proof.
reflexivity.
Qed.

Require Import Nat.

Lemma addn0 n : n + 0 = n.
Proof.
induction n.
reflexivity.
simpl. rewrite IHn. reflexivity. Qed.

(* Dual KerPair: module alias causes user name != canonical name *)
Module OriginalMod.
  Inductive Color := Red | Green | Blue.
End OriginalMod.

Module AliasedMod := OriginalMod.

(* AliasedMod.Color -> Dual KerPair:
   user KerName:      <path>.AliasedMod.Color
   canonical KerName: <path>.OriginalMod.Color *)
Lemma dual_example (c : AliasedMod.Color) : True.
Proof.
  exact I.
Qed.
