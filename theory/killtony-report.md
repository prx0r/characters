# Kill Tony decode — rule-v0 report

Sets: 276 (207 train / 69 heldout comedians). Base crowd mean: 2.41 (0=silence..4=roaring).

Operator lifts vs base (train) + heldout check:

- unmask: lift +0.194 (train_mean 2.6, heldout None, n=5)
- rigidify: lift +0.073 (train_mean 2.479, heldout 3.2, n=48)
- identity_contradict: lift +0.065 (train_mean 2.471, heldout 3.143, n=34)
- expose_self_blindness: lift +0.065 (train_mean 2.471, heldout 3.143, n=34)
- double_interpret: lift +0.045 (train_mean 2.451, heldout 2.837, n=406)
- repeat_variation: lift +0.038 (train_mean 2.444, heldout 2.821, n=189)
- literalize: lift +0.007 (train_mean 2.413, heldout 2.8, n=230)
- status_invert: lift -0.031 (train_mean 2.375, heldout None, n=8)

Use: positive-lift operators seed generator exploration; POG remains ground truth.
Do not: imitate lines, train on verbatim, treat LLM scores as laughter.

## 2026-10-11 registry expansion (37 theories, 15 operators)
Added from literature sweep: simultaneity, benign_appraisal, play_state,
diminishment (Apter), false_alarm, anxiety_reduction, false_analogy,
juxtaposition, role_reversal, perspective_shift, cratylism (Attardo LM
catalogue), jab_line (long-text structure). New ops: false_analogy,
juxtapose, role_reverse (all pure, tested).
External validation: Warren/Barsky/McGraw 2021 finds surprise and
superiority do NOT discriminate humorous from non-humorous; simultaneity,
violation, benign appraisal do. Our Jev lifts agree (status_invert -0.03).
New entries ship at support 0.5, untested.

## 2026-10-11 arXiv sweep (40 theories)
Papers that change the design, not just the bibliography:
- 2602.12763 Not Human Funnier: machine identity as comedy resource (N=32,
  p=.03). Identity-first openers + stereotype breaking. This is our seed
  philosophy argument with human evidence behind it. -> machine_identity.
- 2604.09629 HumorGen: 6 theory-personas as MoT experts; SFT beats DPO;
  reasoning traces HURT funniness (explainer trap — we already store
  decisions, never CoT). Neurotic 63.4% / Absurdist 55.8% / Wordsmith 34.9%.
  -> persona_routing.
- 2606.00022 lmfaoooo (MWAHAHA rank 1): generate-many -> select-best with
  interpretable 17-feature basis + BT/Elo. Selection is the bottleneck, not
  generation. Our app generates ONE minute; candidate ranking is the next
  build. -> selection_bottleneck.
- ACL 2026 Comedy Club: discussion-as-social-memory wins 75.6%; rubric diffs
  agree (ICC 0.71) while binary preference doesn't (k=0.237). Validates our
  multi-signal feedback (rating + POGs + critique, never one score).
