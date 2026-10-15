# AGENTS.md — operating manual for prx0r/characters

Read this first. THE VISION: `docs/THE-VISION.md` (owner, verbatim).
Deep map: `docs/ENGINE-MAP.md`. Universe flywheel: `docs/UNIVERSE.md`.

## What this repo is

The comedy universe: a **database of comedians** → **decomposition**
(why sets are funny, theory-tagged) → **generation** (AI comedians
performing in proven delivery) → **ranking** (audiences + judges).
Expanding what comedy means to AI.

## Hard rules (violations happened; absolute)

- **Money:** synthesis = `s2.1-pro-free` ONLY ($0), ALWAYS. MCP TTS is
  FORBIDDEN for renders (the one 970-credit louis-voice render was the
  exception that proved the rule — do not repeat). MCP free uses only:
  clone creation, voice search, get_credit_balance. ANY spend = ASK with
  exact numbers first.
- **Pitch-slide era is OVER.** Fish speed-knob shifts pitch on large
  factors — never use it outside the clean zone (0.92-1.08). Tempo via
  direction language (cues + tone markers). No post-stretch code exists
  anymore; don't reintroduce it.
- **Keys:** only in `.env` (chmod 600, gitignored). Never print/commit.
- **Material:** no verbatim copyrighted acts in packs/channel content;
  theory analysis of transcripts is fine, generation uses original or
  world-mapped material. `[censored]` tokens stripped from all renders.
- **Never invent funny minutes from scratch** (deleted foundry/riffchain
  workflows). SETS LEAD: actual set text → substitutions/stencil mapping
  only. Owner rejected generated-from-air material every time.
- **Judge humility:** real pro sets must outscore generated sets
  (calibration ladder: garbage < generated < pro). If a model change
  breaks that order, reject the change.
- Merge: commit, fetch, no rebase/force on master. Tests: `python3 -m
  pytest audition/test_audition.py -q` (slow box). Kill by PID.

## The pipelines (how each works RIGHT NOW)

### 1. Delivery engine (transcript → predicted performance)
`cf_asr.py` (Cloudflare whisper → words+timings, "ha ha" laugh
extraction) → ground truth via gemini segments or AM-laugh detector →
`jev_or.py` (typesafe/jev-1.13 via OpenRouter, ~$0.0001/set; typed
emotion-choice + pace-score per beat; multimodal via
`TypeSafe-Danger-Zone-Images` header) → `fish_tts.py` renders per beat
(prompted tempo: emotion cue × tone marker × clean-zone speed — never
post-stretch) → `jev_loop.py` compares vs actual audio, per-beat damped
speed calibration, bounds acc≥0.6/wpm≤20/var≤1.5. Converged states:
ari, casey, pickles, kam; louis formula in `theory/LOUIS-FORMULA.md`.
Emergence: character graph (`kgraphs/`) → `emerge.py` → affect (A,V,P)
→ MARY tempo, signature emotion from misinterpretation rule.

### 2. Funniness judge + laugh simulator
`laugh_predictor.py` (v3: sklearn on casey-riff events + AM-labeled
beats, LOO AUROC .664, history-dominant) → `laugh_sim.py`: listen to
ANY audio → 6s windows → P(laugh) → MIX crowd/chuckle clips at predicted
moments (`/home/box/sim_*.wav`). Validate vs cached AM events (precision
~60-78% where GT reliable). `show_runner.py`: episodes — acts perform
with adaptive dpv pauses, simulated crowd, judge scores (real sets =
measured laugh density; generated = predicted P). Ledger:
`voicelab/shows/*.json`.

### 3. Theory corpus
`theory/`: LAUGH-PHYSICS (3-scale), DVP-FINDINGS (pause ladder 0.6/1.5/1.0
+ jitter; coupling = expertise metric), LOUIS-FORMULA + LOUIS-JOKE-
ANATOMY, PHYSICALITY-AXIS (voice-first vs physical → casting rule),
ENGINE-ARCHETYPE-MAP (delivery-identity shape: pickles=Dracula),
RESEARCH-REVIEW (5-tier arxiv synthesis). Data: `theory/scribe/`
(word timings), `killtony-minutes/*_gemini` (GT), `casey_rocket_riff_db`
(666 labeled riffs), `killtony-features.jsonl` (276 sets),
`kt_archive_graph.json` (569 sets/408 comedians from killtonyarchive).

### 4. Characters (the product)
Voice cards (`voicelab/voices.json`, probe+measure) + clones (free MCP,
`mcp_fish.py`, `clone_ids.json` — 7 performers). Stencils = delivery
templates per set (`voicelab/stencils/`). Mapping: stencil × character
material × voice (`swap_material.py` / inline; set text + substitutions
ONLY). Material rule: mundane context × identity gap. Breakdowns:
`breakdown.py` (set → narration-ready "why funny" markdown — the
YouTube channel engine).

### 5. Ranking (`minute_battle.py`)
Shortform minutes (45-100s), blind A/B vote (YouTube embeds or local
wavs), Elo + Wilson bounds, leaderboard. Goal: the funniest minute in
existence. Ratings slots in every swap/show JSON feed back into
voice_battle taste weights.

### 6. Live lane (queued)
SNL-VISION.md: mood function (Jev per-turn modulator), multimodal Jev
frame judging, handwired browser engine, video reaction shows. Fish
Plus plan (250k credits) = video fuel. Ask before spend.

## Tools quickref
- `python3 audition/compose_set.py <pack> --dry-run` — pack → beats
- `python3 audition/laugh_sim.py <audio>` — laugh track over anything
- `python3 audition/breakdown.py --set X --performer Y` — channel script
- `python3 audition/show_runner.py --name ep --acts-file Y` — episode
- `python3 audition/voicecast.py design <slug>` — voice-design (ASK: $)
- `python3 audition/ledger.py` — rebuild experiment registry
- Jev/OpenRouter + Fish keys + CF token: `.env` only

## Priority lane (owner 2026-10-15): STAND-STILL COMICS

The GOATs whose oomph is vocals + joke structure + theory + storytelling
timing, minimal visuals: **norm macdonald, jerry seinfeld, louis ck**
(and kin: wright, hedberg, gaffigan, tig). The voice-first tier
(`theory/PHYSICALITY-AXIS.md`) — our engine lands these audio-only.
Pipeline order: more sets for these first (download → scribe → GT →
state → decomposition), before any physical-comic work.

## Open threads
Roster pack (ear-approved sets), Standupedia scraper, name-noise cleanup
on kt_archive_graph, laugh-sim threshold tuning, per-performer judge
offsets, word-level laugh labels (StandUp4AI method), Rive rig, channel
batch-breakdowns over 569 archived sets.
