# LAUGH-PHYSICS — why people laugh right there (our corpus + theory)

Owner question 2026-10-15. Evidence: casey riff_db (663 clean riffs, 423
laugh timestamps), killtony-features (276 sets, 57 roaring/10 golden),
AM-laugh GT sets (will/kam/lazer), plus TIC-TALK/StandUp4AI papers.

## The answer has three scales

### 1. Set scale — the arc is why they keep laughing
- **Golden-ticket signature (10/10 sampled): escalation + garden_path.**
  Every GT set leads the audience down a path (garden_path) and escalates
  into the twist. Not one golden set lacks both.
- **Roaring sets (crowd>=4) overrepresent identity_contradiction (+0.08)
  and rigidity (+0.08)** — the character-collision theories. The crowd
  laughs hardest when WHO the person is contradicts what they say/do.
  This is our engine's blind-spot thesis, confirmed at corpus scale.
- Roaring sets also carry more reframes (0.67 vs 0.48) and punches
  (4.0 vs 3.6). More turns per minute.

### 2. Riff scale — atomicity beats length
Casey trigger rates by unit type:
| unit | n | trigger rate |
|---|---|---|
| quick_riff | 181 | **0.44** |
| micro_tag | 116 | **0.43** |
| full_riff | 213 | 0.38 |
| bit | 153 | 0.31 |

Small units land more often than long bits. And by tempo:
| wps band | n | trigger rate |
|---|---|---|
| slow (<2.5) | 198 | **0.51** |
| moderate | 109 | 0.50 |
| fast | 119 | 0.37 |
| rapid (3.8+) | 236 | 0.25 |

Casey's rapid-riff FLOOD mostly dies (0.25); his slow-moderate riffs
succeed most per attempt. The earlier "laughed riffs are faster" finding
reconciles: given a laugh, the riff was moderately fast vs quiet riffs —
and once the room is hot he accelerates (history-dominance, TIC-TALK
AUROC 0.643). Slow wins cold; acceleration wins hot.

### 3. Moment scale — laughter starts BEFORE the punchline ends
- **laugh_delay median −0.36s; 78% OVERLAP.** The audience starts
  laughing before the riff finishes. Patterns: mid-sentence 117,
  overlap 92, clean "after" only 59. Half of all laughs are not
  post-button — they fire during the final approach.
- Pre-laugh pauses are SHORTER before laughs (3.4s vs 5.2s quiet —
  third performer confirmation: lazer, casey, and the corpus).
- Body stills before punchlines (TIC-TALK r=−0.75); voice holds or
  accelerates. The dissociation is the delivery physics of the moment.

## The unified why

People laugh when a **character-collision** (identity contradiction,
garden-path twist) arrives in an **atomic unit** (quick riff, not a bit),
delivered at **slow-moderate cold tempo** that **accelerates hot**, with
the **body still and the voice moving**, and the laugh **fires mid-approach**
— 78% start before the sentence ends. Content that is personal/bodily
out-laughs geopolitical (TIC-TALK). Golden tickets are just the sets that
stack escalation + garden_path on top of all of this.

## Engine implications (already wired or queued)
- atomic units: our 11-beat minute structure ≈ quick_riff grain — right call
- slow-cold/fast-hot: MARY arousal tempo + hot-room prior (cue_tempo)
- laugh mid-approach: pause_bump BEFORE punchline (stillness) + no long
  hold after (overlap style) — our compose_set pre-punch rule + casey's
  negative-delay profile
- identity_contradiction: blind-spot material targeting (emerge.py
  misinterpretation cycling) — the material-swap engine already aims here
- garden_path/escalation: collision-shape library (WORLD-MAPPING) —
  wrong_expert and status_reversal are garden-path generators
