From Coq Require Import ArithRing.

Variable n : nat.

Lemma foo : n + 0 = n.
Proof. ring. Qed.

Check foo.  (* foo : n + 0 = n *)

Lemma foo2 : forall (m : nat), m + 0 = m.
Proof. intros m. ring. Qed.

Check foo2.  (* foo2 : forall m : nat, m + 0 = m *)

Lemma foo3 : n + 0 + 0 = n.
Proof.
  rewrite -> foo.
  apply foo.
Qed.


Print Assumptions foo.

From Coq Require Import ArithRing.

Section S.
  Variable n : nat.

  Lemma foo4 : n + 0 = n.
  Proof using.
    ring.
  Qed.

End S.

Check foo4.


Lemma foo5 : forall (k : nat), k + 0 = k.
  intros k.
  apply foo4.
Qed.

Check foo_section.
(* foo_section : ∀ n : nat, n + 0 = n *)

Lemma use_foo_section : forall (k : nat), k + 0 = k.
Proof.
  intros k.
  apply foo_section.
Qed.


Theorem f : 2 = 2.
Proof using.
    simpl.
Admitted.

Theorem f2 : 2 + 0 = 2.
Proof using.
    simpl.
    reflexivity.
Qed.

Theorem f3 : 2 + 0 = 2.
Proof.
    simpl.
    reflexivity.
Qed.
