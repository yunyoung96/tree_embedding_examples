From Coq Require Import Nat.
From Coq Require Import Numbers.Cyclic.Int63.Uint63.
From Coq Require Import Floats.PrimFloat.
From Coq Require Import Array.PArray.

Local Parameter vnat : nat.

Section VarSample.
  Variable visible_var : nat.

  Lemma var_sample : visible_var = visible_var.
  Proof.
    reflexivity.
  Qed.
End VarSample.

Inductive visible_small : Type :=
| vca
| vcb.

Inductive visible_Meta_keyword : Type :=
| Meta.

Local Parameter QSort : nat.
Local Parameter Unif : nat.
Local Parameter RelevanceVar : nat.
Local Parameter Same : nat.
Local Parameter Dual : nat.
Local Parameter RawLevel : nat.
Local Parameter UGlobal : nat.
Local Parameter library : nat.
Local Parameter process : nat.
Local Parameter uid : nat.

Set Primitive Projections.

Record visible_box : Type := {
  vfld : nat
}.

CoInductive visible_stream : Type :=
| vcon : nat -> visible_stream -> visible_stream.

Lemma rel_var_const_sample :
  forall reln : nat, Nat.add reln vnat = Nat.add reln vnat.
Proof.
  easy.
Qed.

Lemma ind_construct_sample : vca = vca.
Proof.
  reflexivity.
Qed.

Lemma sort_prod_lambda_letin_cast_app_sample :
  (forall ptyp : Type, ptyp -> ptyp) ->
  (fun lamx : nat => lamx) 0%nat =
  (let letx := (0%nat : nat) in letx).
Proof.
  intro pid.
  reflexivity.
Qed.

Lemma case_fix_sample :
  forall cass : visible_small,
    (match cass with
     | vca => 0%nat
     | vcb => 1%nat
     end) =
    (fix fixf (fixn : nat) : nat :=
       match fixn with
       | O => O
       | S fixk => S (fixf fixk)
       end) (match cass with
             | vca => 0%nat
             | vcb => 1%nat
             end).
Proof.
  intros [|]; reflexivity.
Qed.

Lemma proj_sample : forall boxx : visible_box, vfld boxx = vfld boxx.
Proof.
  easy.
Qed.

Lemma cofix_sample :
  (cofix cofx : visible_stream := vcon 0%nat cofx) =
  (cofix cofx : visible_stream := vcon 0%nat cofx).
Proof.
  reflexivity.
Qed.

Lemma int_sample : 1%uint63 = 1%uint63.
Proof.
  reflexivity.
Qed.

Lemma float_sample : 1%float = 1%float.
Proof.
  reflexivity.
Qed.

Lemma array_sample :
  [| 1%nat; 2%nat | 0%nat : nat |] =
  [| 1%nat; 2%nat | 0%nat : nat |].
Proof.
  reflexivity.
Qed.

Lemma evar_meta_marker_sample : exists evrn : nat, evrn = evrn.
Proof.
  eexists.
  instantiate (1 := 0%nat).
  reflexivity.
Qed.

Lemma meta_keyword_marker_sample : Meta = Meta.
Proof.
  reflexivity.
Qed.

Lemma sort_set_irrel_sample :
  forall sp : SProp, sp -> Set.
Proof.
  intros sp hp.
  exact nat.
Qed.

Module Type MSIG.
  Parameter typ : Type.
  Parameter val : typ.
End MSIG.

Module DotM.
  Definition dotv : nat := 0%nat.
End DotM.

Module Fmod (Bnd : MSIG).
  Lemma modpath_sample :
    Bnd.val = Bnd.val /\ DotM.dotv = DotM.dotv.
  Proof.
    split; reflexivity.
  Qed.
End Fmod.

Module Orig.
  Definition oval : nat := 0%nat.
End Orig.

Module Alia := Orig.

Lemma dual_path_sample : Alia.oval = Orig.oval.
Proof.
  reflexivity.
Qed.

Lemma qsort_marker_sample : QSort = QSort.
Proof. reflexivity. Qed.

Lemma unif_marker_sample : Unif = Unif.
Proof. reflexivity. Qed.

Lemma relevance_var_marker_sample : RelevanceVar = RelevanceVar.
Proof. reflexivity. Qed.

Lemma same_marker_sample : Same = Same.
Proof. reflexivity. Qed.

Lemma dual_marker_sample2 : Dual = Dual.
Proof. reflexivity. Qed.

Lemma rawlevel_marker_sample : RawLevel = RawLevel.
Proof. reflexivity. Qed.

Lemma uglobal_marker_sample : UGlobal = UGlobal.
Proof. reflexivity. Qed.

Lemma library_marker_sample : library = library.
Proof. reflexivity. Qed.

Lemma process_marker_sample : process = process.
Proof. reflexivity. Qed.

Lemma uid_marker_sample : uid = uid.
Proof. reflexivity. Qed.

Inductive visible_even_tree : Type :=
| ve_leaf : visible_even_tree
| ve_node : visible_odd_tree -> visible_even_tree
with visible_odd_tree : Type :=
| vo_node : visible_even_tree -> visible_odd_tree.

Lemma mutual_inductive_sample :
  forall tree : visible_even_tree, tree = tree.
Proof.
  easy.
Qed.
