# AGENTS.md — operating manual for prx0r/characters

Read this first. Vision: `docs/THE-VISION.md`. Deep map: `docs/ENGINE-MAP.md`.
**Metrics truth: `docs/MODEL-CARDS.md` (if any doc disagrees, MODEL-CARDS wins).**

## What this repo is

Comedy universe: **database of comedians** → **decomposition** (why sets
are funny, theory-tagged) → **generation** (AI comedians in proven delivery)
→ **ranking** (audiences + judges). Expanding what comedy means to AI.

## Hard rules (violations happened; absolute)

- **Money:** synthesis = `s2.1-pro-free` ONLY ($0), ALWAYS. MCP TTS is
  FORBIDDEN for renders. MCP free uses only: clone creation, voice search,
  get_credit_balance. ANY spend = ASK with exact numbers first.
- **Pitch-slide era is OVER.** Fish speed-knob shifts pitch — never use
  outside clean zone (0.92–1.08). Tempo via direction language only.
- **Keys:** only in `.env` (chmod 600, gitignored). Never print/commit.
- **Material:** no verbatim copyrighted acts. `[censored]` stripped from renders.
- **Never invent funny minutes from scratch.** SETS LEAD: actual set text
  → substitutions/stencil mapping only.
- **Judge humility:** real pro sets must outscore generated sets
  (garbage < generated < pro). If a model change breaks that, reject it.
- **Metrics honesty:** if a number was measured with label leakage, mark
  it as leaked. Never present leaked metrics as working. See MODEL-CARDS.md.
- Merge: commit, fetch, no rebase/force on master. Tests: `python3 -m
  pytest audition/test_audition.py -q` (slow box, 10/12 pass). Kill by PID.

## The pipelines (verified working 2026-10-17)

### 1. Delivery engine (transcript → predicted performance)
`cf_asr.py` (Cloudflare whisper → words+timings) → ground truth via gemini
or AM-laugh detector → `jev_or.py` (typesafe/jev-1.13 via OpenRouter) →
`fish_tts.py` renders per beat → `jev_loop.py` compares vs actual audio.
Converged: ari, casey, pickles, kam; louis formula-level. Calibration
loops NOT run for: seinfeld (5 clips ingested), norm (audio on box).

### 2. Laugh engine (text/audio → predicted laughter)
**Two approaches, both working:**

**A. Text path** (SMILE distribution):
- `unified_laugh_model.pkl` — AUC 0.979 on SMILE test split
- `laugh_track.py` — text → calibrated laugh track per comedian
- `laugh_timeline.py` — text → timeline with crowd modulation

**B. Delivery path** (audio energy, generalizes better):
- `delivery_aware_model.pkl` — AUC 0.654 leave-one-comedian-out (KT)
- `am_delivery_model.pkl` — AUC 0.564 cross-comedian (AM specials)
- Features: energy_mean/std/max/min, position, duration

**Key finding:** audio energy beats text (0.654 vs 0.548). The engine
needs energy, not just words.

**Crowd physics:** `learned_physics.json` — heat=0.487 dominates.
⚠️ Old "99.7% loss reduction" was LABEL LEAKAGE — fixed 2026-10-17.

### 3. Theory corpus
`theory/`: LAUGH-PHYSICS (3-scale corpus findings), DVP-FINDINGS (pause
ladder 0.6/1.5/1.0 + jitter), LOUIS-FORMULA (measured: 1.67s pauses,
3.94 syll/s, 19.6 dB dynamics), PHYSICALITY-AXIS (voice-first casting
rule), ENGINE-ARCHETYPE-MAP. Data: `scribe/` (word timings),
`killtony-minutes/` (GT), `casey_rocket_riff_db.json` (663 labeled riffs),
`kt_archive_graph.json` (569 sets/408 comedians).

### 4. Characters (the product)
Voice cards (`voicelab/voices.json`) + clones (free MCP, `clone_ids.json`
— 8 performers including ari). Stencils in `voicelab/stencils/`. Mapping:
stencil × character material × voice. Breakdowns: `breakdown.py`.

### 5. Ranking (`minute_battle.py`)
Shortform minutes, blind A/B vote, Elo + Wilson bounds. Needs server
restart (`auditions.db` not in checkout).

### 6. Live lane (queued)
SNL-VISION.md: mood function, multimodal Jev, handwired browser engine.
Not implemented.

## Laugh engine data (verified on disk)

| What | Where | Size |
|------|-------|------|
| 5 AM specials + events | `/home/box/comedy-audio/` | ~680 MB |
| ASR transcripts | `/home/box/comedy-audio/asr/` | 5 JSONs |
| KT sets (12 stems) | `/home/box/comedy-audio/kt-sets/` | 12 m4a |
| Training beats | `audition/voicelab/laugh_training/beats.jsonl` | 2998 rows |
| Laugh clips (6 CC0) | `/home/box/comedy-ai/laugh-library/` | mp3s |
| Laugh types | `/home/box/comedy-ai/laugh-corpus/laugh_types.json` | 8 types |
| Comedy principles | `/home/box/comedy-ai/theory-videos/comedy_principles.json` | 10 → Jev |
| Theory videos | `/home/box/comedy-ai/theory-videos/` | 6 m4a |

## Tools quickref

```bash
# Laugh track from text
python3 audition/laugh_track.py --demo

# Transcribe audio
python3 -c "import sys; sys.path.insert(0,'audition'); import cf_asr; print(cf_asr.transcribe('audio.mp3'))"

# Fish TTS
python3 -c "import sys; sys.path.insert(0,'audition'); import fish_tts; fish_tts.synthesize_fish('id', 'text', modulator='confessional')"

# Crowd physics (Bun)
cd /home/box/handwired && ~/.bun/bin/bun run lab/crowd-physics/finetune-circuit.ts

# Retrain delivery model
python3 audition/train_delivery_model.py

# Tests
python3 -m pytest audition/test_audition.py -q  # 10/12 pass
```

## Priority lane: STAND-STILL COMICS

GOATs whose oomph is vocals + joke structure: **norm macdonald, jerry
seinfeld, louis ck** (and kin: wright, hedberg, gaffigan, tig). Voice-first
tier — engine lands these audio-only. Pipeline: more sets → scribe → GT
→ state → decomposition.

## Open threads (verified actionable)

| Thread | Effort | Impact |
|--------|--------|--------|
| Combine text + delivery + narrative features | 2-3hr | High |
| Jev mechanism classifier (coherent vs stitched) | 2hr | High |
| Seinfeld calibration (5 clips ingested) | 1hr | Medium |
| Norm calibration (audio on box) | 1hr | Medium |
| Find VocalSound alternative (zip was corrupt) | 30min | High |
| Complete theory video transcripts (4/6 done) | 15min | Medium |
| Kaggle Unsloth retry (pinned versions plan exists) | 1hr | High |
