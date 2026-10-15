# ENGINE-MAP — the canonical map of this repo (2026-10-16)

Three pipelines share one loop: **understand delivery → judge funniness →
extract theory → generate characters → hear rating → update**. This doc
maps every moving part. Old specs (SPEC-character-graph, VISION, MAP.md)
still hold for character-graph schema and world vision; this is the
engine layer on top.

## Pipeline 1 — Delivery engine (transcript → predicted performance)

Question it answers: *how does this comedian deliver these words?*

| step | script | notes |
|---|---|---|
| ASR + timings | `cf_asr.py` | Cloudflare whisper (binary upload, VTT parse, "ha ha" laugh extraction). Local faster-whisper fallback |
| ground truth | AM-laugh GT builder (inline; see louis_ingest) | 4-12Hz detector splits sets into emotion segments when no gemini |
| profile | `kgraphs/<name>.json` | rich text-only character graph (persona, dramatic_core, delivery_texture) |
| affect | `emerge.py` | graph lexicons → (arousal,valence,power) → MARY → tempo band, signature emotion |
| predict | `jev_or.py` + `jev_deliver.py` | Jev typed decisions (typesafe/jev-1.13 via OpenRouter, ~$0.0001/set): per-beat emotion choice + pace score |
| render | `fish_tts.py` | s2.1-pro-free ($0). Prompted tempo: emotion cue × tone marker × clean-zone speed (NO post-stretch). Pron dictionaries. Multi-speaker ready |
| compare+calibrate | `jev_loop.py` | render → measure vs actual → error history → re-predict. Per-beat damped speed scales. Bounds: acc≥0.6, wpm_mae≤20, var_mae≤1.5 |
| zero-shot test | `predict_zero_shot.py`, `zero_cal_test.py` | persona-prior floor; text-only kgraph test (honest negatives recorded) |
| de-cheat | (inline; voicelab/decheat_*.json) | clone vs neutral voice: clone carried +25wpm tempo, zero decisions |

**Converged delivery states:** ari (kt704), casey (set 2), pickles (sets 1+2), kam (set 1). Louis = formula-level (`theory/LOUIS-FORMULA.md`: pauses 1.67s above pros, syll 3.94, dyn 19.6dB).

## Pipeline 2 — Funniness judge (does it land?)

| component | script | metric |
|---|---|---|
| laugh predictor | `laugh_predictor.py` | P(laugh in 2s)+loudness bucket; CV AUROC 0.777; live RL loop (prediction error = reward) |
| dpv timing judge | `compose_set.py` pause ladder + `louis_analysis.py` | pause-before-surprise extension (pros +41% vs amateurs 27% — THE expertise metric) |
| delivery rubric | `dataset.py` | pace/laugh-density/verify composite, same rubric for real+generated |
| word verify | `verify_set.py` / compose auto-verify | CF whisper word-match vs intended (catches mumbles) |
| theory tags | `theory_tagger.py` | per-beat garden_path/identity_contradiction/surprise/escalation → laugh correlation |
| experiment log | `ledger.py` → `voicelab/ledger.json` + EXPERIMENTS.md | every run registered, verdict slots (owner ear disposes) |
| taste/A-B | `voice_battle.py` | Elo+Wilson pairs, verdict shape unified with influence repo |

## Pipeline 3 — Theory corpus (why it works)

| artifact | content |
|---|---|
| `theory/LAUGH-PHYSICS.md` | 3-scale answer: atomic units win (quick_riff .44 vs bit .31), slow-cold/fast-hot tempo, 78% of laughs start before punchline ends, identity_contradiction overrepresented in roaring sets (n=276), golden signature = escalation+garden_path |
| `theory/DVP-FINDINGS.md` | Timing-is-Everything (828 sets): pause r=.36 strongest predictor; our old 500ms = amateur; new ladder 0.6/1.5/1.0s + jitter |
| `theory/LOUIS-FORMULA.md` | measured sincerity engine |
| `theory/PHYSICALITY-AXIS.md` | voice-first vs physical comedians — casting rule |
| `theory/ENGINE-ARCHETYPE-MAP.md` | delivery-identity shape: pickles=Dracula (formal-container), casey=Joker (swing) |
| `theory/THEORY-REVIEW-kgraph.md` | persona-text≠delivery; graph iteration loop |
| `theory/FRONTIER-NOTES.md`, `PROCESS-REVIEW.md` | literature mapping, segmentation modes |
| `theory/vibe-bands.json` | performer emotion bands (distilled) |
| KT corpus | `theory/scribe/*` (word timings), `killtony-minutes/*_gemini` (GT), `casey_rocket_riff_db` (663 labeled riffs), `killtony-features.jsonl` (276 sets) |

## Pipeline 4 — Characters (the product)

| step | script |
|---|---|
| voice cards | probe+measure → `voicelab/voices.json` (9+ cards; fish library + clones) |
| clones | `mcp_fish.py` create_voice_clone (free) — 7 performers cloned; `clone_ids.json` |
| delivery templates | stencils per set (`voicelab/stencils/`) + `delivery_index.json` |
| mapping | `swap_material.py` / inline: stencil × character content × voice (world-mapping; ENGINE-ARCHETYPE-MAP shapes) |
| set-led variants | substitution tables on actual set text (ari×galactic/medieval/corporate, casey×naturedoc/corporate) |
| emerged characters | kgraphs (sweetheart_dracula) + `emerge.py` |
| material rule | mundane contexts × identity gap; NEVER invented percentage scaffolds (foundry deleted) |

**Held audio bank:** `/home/box/` — mapped sets, variants, kam×spongebob/patrick, louis series (13 clips, ingest c09+ running).

## Current state (honest)

- 4 converged delivery states; louis formula measured; 7 clones; 9 voice cards
- laugh predictor AUROC .777 with live RL loop; dpv judge wired
- zero-shot from text: NOT cracked (0.28-0.36; GT-quality + delivery_texture gaps)
- physical comedians: voice-only = half act (video lane pending: render.py puppet or Fish Plus lip-sync)
- money: everything $0 (s2.1-pro-free + free MCP clone + $0.0001 Jev); voice-design blocked on API credit; Plus plan 250k credits unused (video lane fuel)

## What next (priority order)

1. **Close the judge loop with owner ratings** (~20 picks): fit battle weights so the judge predicts *your* taste (voice_battle/LoRe mini). Ratings slots exist in every swap/foundry json.
2. **Finish louis ingest** (c09-c13) → refit delivery state; then a full multi-clip converged "deliver like louis" engine.
3. **Video lane pilot**: one physical-comedian set (casey or kam) through render.py puppet or Plus lip-sync — does embodiment close the gap you heard?
4. **Laugh predictor v2**: word-level labels via StandUp4AI method (kill GT-leakage); wire live mic → AM-detect → prediction-error RL for real shows.
5. **Roster pack**: 3-5 ear-approved character sets (from winning engine×container pairs) ready for Freaktown pipeline.
6. Research bonus: write up the round-trip delivery-calibration method (demo paper).

## Money rules (unchanged, absolute)

Free API always; MCP TTS = identity checks only (print credits_charged);
clone creation free; voice-design/video spend = ASK with exact numbers.
