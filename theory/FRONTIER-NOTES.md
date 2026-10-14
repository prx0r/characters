# FRONTIER-NOTES — what the papers say vs our approach (2026-10-14)

Sources: TIC-TALK (2603.21803), StandUp4AI (2505.18903), Punchlines-to-
Predictions (2504.09049), Open Mic (Mittal 2021), survey 2509.21175.

## Verified against our approach

| Finding | Source | Our status | Action |
|---|---|---|---|
| Stillness before punchline (kinetic E vs laughter r=-0.75) | TIC-TALK | pauses exist; no explicit pre-punch hold | compose_set: pause>=500ms before punchline beats; stencil rig note |
| Personal/bodily material laughs > geopolitical | TIC-TALK | material_swap has no content prior | rank swap slots: bodily/personal > abstract |
| Laughter HISTORY dominates onset (AUROC .643 vs text .554) — hot room stays hot | TIC-TALK | not modeled | in multi-beat renders: early-beat quality weighted higher in scoring |
| Punchline-from-text is hard (humans 41%, LLM 51%) | Punchlines | we label via rules | keep AUDIO-first (laugh timestamps); never trust text labels alone |
| Laughter = word-level sequence labeling, many laughs per sentence | StandUp4AI | binary-ish segment labels | laugh-gap labeling (below) |
| Whisper/WhisperX timestamp discrepancies reveal missed laughs (~3/video) | StandUp4AI | unexploited | **cheap version: big inter-word gaps in "continuous" speech = hidden laughter** |
| Laugh acoustics: 4-12Hz modulation energy is a key feature | StandUp4AI App B | not used | future numpy laugh detector |
| Zero-shot SOTA = phone-level F0/duration cloning | FC-TTS etc | API-limited | parametric + adapt loop stays correct |

## Tiny patches adopted (this pass)

1. **Laugh-gap segmentation** (`seg_text`/`segments`): split words on gaps
   >0.8s (laugh-scale, not silence-scale 1.1s+); the word before a gap =
   punch-candidate label. Fixes pause-less minute collapse (Kam flaw) AND
   gives audio-first beat labels without any detector model.
2. **Pre-punch pause rule** (compose_set): ensure >=500ms silence before
   punchline/closer beats (stillness = attention focus, TIC-TALK).
3. Open Mic dataset (funniness-scored segments) = next data pull for
   unseen-performer priors. Not yet downloaded.
