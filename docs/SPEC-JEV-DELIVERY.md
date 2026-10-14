# SPEC-JEV-DELIVERY — per-comedian Jev delivery state machine

Owner endgame 2026-10-14: predict audience laughs; predict how a character
profile delivers a passage; calibrate a Jev state per comedian/archetype
until it quantitatively predicts their delivery from transcript alone.

## The loop (quantitative, no vibes)

1. **Decode:** transcript (words only, no timing) + comedian profile
   (archetype, persona, MARY affect coords, prior error history) → Jev
   predicts per-segment delivery: emotion (choice), pace (score),
   energy (score), valence-direction (choice), punch-likelihood (noul).
   One call per minute, ~15 typed questions, ~$0.0002.
2. **Render:** predictions → engine recipes → s2.1-pro-free → wav.
3. **Compare:** measure rendered vs ACTUAL audio per segment:
   |delta_wpm|, |delta_pitch_var|, |delta_dyn|, emotion-label accuracy
   vs gemini ground truth, laugh-position overlap (when available).
4. **Calibrate:** errors appended to state ("you predicted rapid for
   grievance lines; actual was measured — subtract 0.15 speed next time").
   P-TTT-style in-context fast weights, no training infra.
5. **Converge:** stop when per-metric error bands overlap the corpus
   noise floor (render-vs-render variance). The Jev state IS the
   comedian's delivery model.

## Why Jev fits (not an LLM)

- Typed outputs = our recipe knobs directly (choice->cue, score->speed
  bucket, noul->punch flag). No parsing, no hallucinated prose.
- Parallel questions = full-minute decode in one 70-500ms call.
- Calibrated probabilities = we know when it's unsure (low confidence
  -> explore that segment type more, like our RL loop).
- $0.000013/call -> calibration loop runs thousands of iterations free.
- Deterministic replay: state+questions+model pin = same decision.

## Ground truth available per comedian

- kt704/715/728 (ari), casey_1/2, pickles_1/2: gemini emotion segments
  (label accuracy target), scribe word timings (per-segment wpm),
  prosody Praat stats (pitch var, intensity), our perf_sets renders
  (render-vs-render noise floor already measured).
- norm_moth, louis_roadrage: scribe + judge stats (thinner ground truth).

## Falsifiable targets (first calibration pass)

- emotion-label accuracy vs gemini: >60% (baseline: majority class ~35%)
- per-segment wpm MAE: <20 (zero-shot floor was 34 with persona priors;
  Jev + profile + error history should beat it)
- pitch-var MAE: <1.5 st (corpus band 4.2-5.9)

## What kills it (honest risks)

- Jev may regress to archetype means (safe mid predictions) — mitigated
  by confidence-weighted exploration in state.
- Segment granularity: fixed beats from features.jsonl (fair, no timing
  leak) vs gemini segments (leaks timing). Use fixed 15s beats for the
  honest test.
- One comedian at a time; cross-comedian generalization untested until
  3+ states exist.
