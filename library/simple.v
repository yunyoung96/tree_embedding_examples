Lemma f0 : forall b : bool, b = b.
Proof.
    intros.
    destruct b.
    - reflexivity.
    - reflexivity.
Qed.

Lemma f00 : forall b1 : bool, b1 = b1.
Proof.
    intros.
    destruct b1.
    - reflexivity.
    - reflexivity.
Qed.


Lemma f1: 0 + 4 = 4.
    simpl.
    reflexivity.
Qed.

Lemma f2: 0 + 3 = 3.
    simpl.
    reflexivity.
Qed.

Lemma f3 : forall n : nat, 0 + n = n.
Proof.
    intros n.
    simpl.
    reflexivity.
Qed.

Lemma f4_multi_goal_hyp : forall (n m : nat), n = m -> m = n -> n = n /\ m = m.
Proof.
    intros n m Hnm Hmn.
    split.
    - reflexivity.
    - reflexivity.
Qed.

Lemma f5_induction : forall n : nat, n + 0 = n.
Proof.
    intros n.
    induction n as [| n IHn].
    - reflexivity.
    - simpl.
      rewrite IHn.
      reflexivity.
Qed.
