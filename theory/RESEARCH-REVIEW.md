# RESEARCH-REVIEW — the full arxiv corpus, what it gave us (2026-10-16)

Every paper we pulled this session, what we adopted, what it confirms or
contradicts, what's still unexploited.

## Tier 1 — the load-bearing papers

**Timing-is-Everything / dpv (2605.00143, 828 Chinese pro sets)**
- temporal beats semantic: pause r=0.36 (strongest single predictor),
  pause-variability 0.35, speech-rate −0.10. Peak surprise > average.
- strategic coupling: pauses +35.6% before high-surprise; pros +41.2%
  vs amateurs 27.4% — the expertise metric.
- ADOPTED: pause ladder (0.6/1.5/1.0s + jitter), coupling ratio as the
  comedy-judge expertise signal, adaptive coupling wired to laugh model.
  Our old 500ms pauses were literally amateur-tier. The paper fixed the
  engine's biggest measurable mistake.

**TIC-TALK (2603.21803, 90 Netflix specials, multimodal)**
- kinetic energy r=−0.75 with laughter (body stills before punchlines);
  personal/bodily content > geopolitical; laughter history dominates
  onset prediction (AUROC .643).
- ADOPTED: physicality axis (voice-first vs physical comedians — owner's
  listen-pass confirmed independently); laugh-history feature in v3
  (.650 — replicates their .643 on our corpus); stillness rule.

**StandUp4AI (2505.18903, 330h, 7 languages)**
- word-level laughter SEQUENCE labeling; ASR-timestamp-discrepancy
  trick finds ~3 missed outbursts/video; fixed windows mislabel.
- ADOPTED: "ha ha" transcript laughter (cf_asr), AM-acoustic labels;
  their finding validates our zero-cal caveat (fixed beats = label
  noise). NOT yet adopted: word-level labels (laugh v2 upgrade queue).

**Punchlines-to-Predictions (2504.09049)**
- humans 41%, LLMs 51% identifying punchlines from TEXT. Audio ground
  truth via forced alignment is the only fair method.
- USE: explains zero-cal ceilings (0.28-0.36) and the GT-leakage trap;
  justifies audio-first religion.

## Tier 2 — the calibration science (we rediscovered these from TTS measurements BEFORE reading them)

**MARY / Going Retro (2307.02132)** — linear rules rate=0.5·arousal+0.2·valence,
volume∝arousal, pitch-direction by valence. WIRED as mary_model.json.
CONTRADICTION found: our measured cue-tempo factors disagree with MARY on
[sarcastic]/[frustrated] direction — TTS renders emotion differently than
human actors. Our measurements > MARY for this engine; MARY fills gaps +
supplies valence direction.

**Scherer CPM / Banse & Scherer (1996) / Larrouy-Maestri 2025 review**
— 3D affect (arousal/valence/power) → 7 acoustic factors (~57% variance).
Our five-dial grammar is a subset. van Rijn 2023: pleasure=slow/low-pitch,
joy=fast/high — matches our sultry/mommy vs luna registry EXACTLY.

**Fujisaki harmony paradox** — high-arousal emotions are acoustically
adjacent (anger/joy/fear share pitch/rate); valence contour separates
them. Explains our sarcastic↔mock_indignant confusion (the systematic
miss in every calibration) and motivates the pitch_direction channel.

**Frijda action readiness** — emotions are readiness states; tempo is
their motor residue. The theory behind cue-tempo coupling: [excited] is
an approach-vector, [frustrated] is blocked-approach drag.

## Tier 3 — the cloning/transfer literature

- **Exact Prosody Cloning (2206.12229)** / Lux: phone-level F0/duration/
  energy overwrite — model-level, Fish API can't. Our parametric
  approximation is the black-box workaround; this paper defines the
  ideal we approximate.
- **ReStyle-TTS (2604)**: zero-shot clones inherit STYLE not just timbre
  — our de-cheat QUANTIFIED this on our pipeline (+25wpm tempo carry,
  zero decision carry).
- **FC-TTS (2605)**: disentangled timbre/style references — validates
  our voice-card × delivery-stencil separation as the right architecture.
- **ComedicSpeech (2305.12200)**: standup TTS by training personal
  prosody — the TRAINING paradigm vs our PARAMETER paradigm. Confirms
  the problem is recognized; our approach works on frozen APIs.
- **Qwen3-TTS (2601.15621)**: SOTA description-based voice control —
  the "prompt a voice" endpoint Fish lacks; the voice-design lane when
  credit exists.

## Tier 4 — decision models (the live lane)

- **TypeSafe Jev + multimodal release (blog 2026-10-14)**: images via
  danger-zone header — VERIFIED LIVE (shot-type choice @0.91). box type
  (1.14) = bounding box → performer tracking. Benchmark (2609.37647):
  Jev strongest on gist-of-short-text — exactly our beat-tagging use.
- **Visual Jev / PixelJev (2609)**: research precedents for image→typed
  decisions; official multimodal Jev now supersedes for our purposes.

## Tier 5 — queued, not yet consumed

- Open Mic dataset (Mittal: funniness-scored segments)
- CocoNut-Humoresque (voice-fit, 1800 segments + acoustics)
- UR-FUNNY (16.5k punchline segments, COVAREP)
- Silvia self-vs-judge (r=.13 — the confidence calibration)
- Owner's taste stack: speed-dating stated-vs-revealed, LoRe/P-TTT/PEBS/
  ARF-RLHF (mapped in SNL-VISION §3; battle loop is the consumer)
- Dark & Stormy / surprisal (late-sentence high-surprisal = dpv peak,
  convergent evidence)

## The meta-lesson

We measured our way to Scherer, MARY, Frijda and Fujisaki BEFORE reading
them — from black-box TTS cue factors. That independence is the strongest
validation the measurement stack has: when your engine's numbers
rediscover30 years of affect science, the numbers mean something. The two
places we DISAGREE with the literature (TTS emotion rendering vs human
actors; clone style-inheritance magnitude) are the two places we
contributed something back.
