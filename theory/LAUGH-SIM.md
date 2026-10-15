# Canonical Laugh Simulator — spec v0

*The missing piece: an automated audience that scores every generated set
before it reaches humans. Fills the dry score-back loop.*

## Endgame: the crowd simulator (owner vision, 2026-10-16)

**Submit a minute of audio. Hear the laughs in response.**

Not a binary laugh/no-laugh detector. A **super-granular laugh engine** that
models the *texture* of audience response:

```
INPUT:  60s audio clip (generated or real)
        + crowd_state (hot/cold/drunk/nervous/TV/taping/club/theater)
        + set_context (what came before, character, mechanism)

OUTPUT: audio track of laughter — right laughs, right texture, right timing
        layered under/over the performance audio
```

### Jev's role: laugh texture, not laugh presence

Jev picks the *character* of each laugh from the mechanism + context:

| Mechanism (Jev noul) | Typical laugh texture |
|---|---|
| rigidity | building chuckle → groan-laugh |
| status_reversal | sharp "oooh" → roar |
| displacement | confused laugh → nervous titter |
| garden_path | silence → explosive release |
| benign_violation | shocked gasp → wheezing |
| audience_allusion | knowing chuckle → warm roar |
| specificity | quick staccato bursts |
| escalation | rising waves, each bigger |

One Jev call per beat: `{type, intensity 1-10, duration_s, delay_ms, reason}`
→ Fish Drama-3 renders: `[shocked laugh]` `[wheezing laugh]` `[dying laughter]`
→ composited under the performance. Total latency ~3-5s (inside a natural
punchline pause).

### Crowd state: the audience is a stateful entity

```python
crowd_state = {
  "heat": 0-10,          # primed? laughing already? TIC-TALK contagion
  "type": "club|theater|tv_taping|drunk_friday|corporate|balcony",
  "memory": [...],       # callbacks land harder; dark jokes shift energy
  "trajectory": [...],   # energy over time — rises, sags, recovers
  "sensitivity": {...},  # what this crowd laughs at (from calibration)
}
```

Heat feeds the contagion term (TIC-TALK: AUROC 0.643 alone). A hot crowd
laugh-storms; a dead room needs bigger mechanisms to break even. The same
joke renders differently in a club vs a corporate room — that's the
granularity.

### RL environment (once calibrated)

```
STATE:      character + scenario + crowd_state + joke_text + set_history
ACTION:     delivery choice (modulator, timing, mechanism emphasis)
POLICY:     Jev now; fine-tuned model later (trained on this env)
REWARD:     simulated laugh score (calibrated on real crowd responses)
ENVIRONMENT: the laugh simulator itself
```

Train on **real comic sets, not AI ones**. The datasets have quality spread:
- **GOATS first**: Ali Wong special, TIC-TALK's 90 Netflix specials (all
  booked professionals), comedians-transcript's 20 named comics
- **Mixed**: KT archive (open micers + Ari/Casey-level pros) — filter by
  crowd_ord=roaring/big_laughs + golden_ticket flag
- **Skip**: standup4ai raw (Comedy Central clips, variable quality) until
  we have a quality filter

The RL loop: AI does a set → simulated crowd responds → score flows back →
policy improves → next set is funnier. No live audience needed. Human votes
become calibration checks, not the training signal.

### Why this works

- Laugh data is abundant (62K prosody segments + 130K StandUp4AI labels +
  887 SMILE reasons + 276 KT sets + Ali Wong scores + TIC-TALK 90 specials)
- Jev already classifies mechanisms on text (276 sets done)
- Fish already renders directed audio (smoke-tested)
- The composition layer is just audio mixing (ffmpeg)
- The calibration loop: render → score vs real crowd data → adjust → repeat

### What "calibrated" means

The simulator's laugh output, given a real comic's audio as input, should
match the actual crowd response recorded in that same audio. Measured by:
- laugh timing correlation (predictor events vs actual events)
- intensity correlation (predicted magnitude vs crowd_ord / laugh score)
- texture match (does the Jev-predicted laugh type match what happened?)

Once these correlations are high on real sets, the simulator is trustworthy
for scoring AI sets. Then the RL loop runs.

## Literature validation

| Paper | Finding | Our mapping |
|---|---|---|
| **dpv framework** (2026, 828 Chinese stand-up sets) | Temporal features OUTWEIGHT semantic features. Pauses lengthen before high-surprise punchlines (0.6s→1.5s). Escalation (rising unpredictability) predicts appreciation (r=0.09, p<0.01) | Stage 1 pause features + distance_shift |
| **Uncertainty & Surprisal** (ACL 2021) | Setup creates semantic uncertainty; punchline creates surprisal. Two features distinguish jokes from non-jokes | Stage 1 LM-based surprisal/uncertainty |
| **TIC-TALK** (CHum 2026, 90 Netflix specials) | Kinetic energy r=-0.75 vs laughter (stillness-before-punchline). Laugh autocorrelation AUROC=0.643 (contagion dominates). Personal/bodily content > geopolitical | Stage 1 kinetic_energy + laugh_history |
| **StandUp4AI** (EMNLP 2025) | Word-level sequence labeling: predict laugh AFTER each word, not binary classification. 130K labels, 7 languages | Stage 2 training data |
| **"So You Think You're Funny"** (EMNLP 2021) | Humour quotient = laugh_duration / clip_duration, validated κ=0.6 | Magnitude calibration formula |
| **SMILE** (NAACL 2024) | 887 laugh reasons: multi-factorial (content + facial expression + context). Audience laughter clearer signal than individual laughter | Stage 3 mechanism→texture mapping |
| **Deep Learning Humor Prediction** (LREC 2016) | Setup→punchline RNN with canned laughter labels. Setup context essential for punchline effectiveness | Confirms setup/punchline segmentation |
| **Provine 1992** | Laughter contagion: 0.2s reaction lag, social facilitation | Stage 1 delay_ms in laugh rendering |

### Key insight from the literature

The reasoning for WHY people laugh is **empirical and structural**, not
extractable from text analysis alone. The dpv framework shows:
- A joke works by **coordinated violations of temporal AND semantic predictions**
- The setup establishes BOTH a rhythm (regular pauses) and semantic expectations
- The punchline violates BOTH simultaneously (extended pause + distant content)
- This coupling creates conditions for "efficient prediction error resolution" → pleasure

So the laugh prediction model should LEARN these patterns from data:
"long setup + sudden pause + high surprisal → explosive release laugh"
"escalating semantic distance + rising pauses → building roar"

Jev's role is not to predict the laugh but to SELECT the texture given the
predicted profile and mechanism. That's a smaller, more tractable reasoning task.

### What the literature says about clean data

The cleanest data for training Stage 2:
1. **TIC-TALK** (90 Netflix specials, aligned text/audio/laughter) — but derived annotations only, no audio distributed
2. **Ali Wong** (925 timed captions, laugh scores 0-10) — we have this, cleanest continuous intensity labels
3. **StandUp4AI** (130K word-level labels, 7 languages) — we have this, largest volume
4. **dpv's Chinese corpus** (828 sets, 107 hours) — not public, but their feature extraction methodology is reproducible
5. **Open Mic dataset** (Mittal et al. 2021) — stand-up performances with human-annotated funniness scores

The dpv paper's methodology is directly applicable: extract pause features +
semantic distance from our existing sets (KT, Ali Wong, StandUp4AI), train
the empirical predictor on the laugh labels we already have.

The RL loop (RL-LOOP.md) is wired but dry — no live POGs flow because battles
haven't run with audiences. Calibration (performance_dna.py) ran once (n=2
Dracula) with no laugh signal. The laugh predictor closes both gaps: every
Fish render gets a predicted laugh curve automatically, compared to anchor
laugh curves, iterated without human wait.

## Laugh audio sources (the actual sounds)

Three tiers: individual laugh samples, crowd-level laughs, synthesis.

### Tier 1: Individual laugh samples (texture library)

| Source | What | License | Size |
|---|---|---|---|
| **VocalSound** (MIT) | 21,024 recordings — laughter, sighs, coughs, throat clearing from 3,365 subjects. Age/gender metadata. THE laugh primitive library. | CC BY-SA 4.0 | free, ~1G |
| **Laughterscape** | 11,413 laughter sounds, 584 Japanese speakers, from YouTube | research only | free |
| **Happy/Evil Laughter** (Zenodo) | 90 clips labeled happy vs mocking (taunting = higher F0) | open | small |
| **AudioSet** (Google) | 2M clips, laughter class — extract via YouTube IDs | CC BY-SA 4.0 | huge, partial |

### Tier 2: Crowd-level laughs (the audience bed)

| Source | What | License |
|---|---|---|
| **Mixkit** (free) | "crowd laugh" 4s, "big crowd laughing" 7s, "small crowd laugh+applause" 5s, "light applause with laughter" 10s — 52 laugh SFX total | Mixkit (free commercial) |
| **BlankSound** | crowd laughing clips (2-5s), crowd "wow", disappointed crowd, ovation | free |
| **Freesound** | CC0 crowd/laugh/applause samples | CC0 |
| **KT/StandUp4AI/our wavs** | real crowd laughter extracted from comedy sets — the authentic texture | research |

### Tier 3: Synthesis (generate new laughs)

| Method | Latency | Texture |
|---|---|---|
| **Fish Drama-3** `[laughs]` `[shocked laugh]` `[wheezing]` | ~2-4s | directed, controllable |
| **Sample library** (VocalSound + Mixkit layered) | instant | authentic, pre-rendered |
| **Hybrid** (Jev picks sample type → Fish fills gaps) | ~1-3s | best of both |

### Compositor architecture

```
punchline_timestamp
  → Jev: {laugh_type, intensity, duration, delay_ms, reason}
  → pick from library OR Fish render:
      shocked laugh  → VocalSound "surprise" subset OR [shocked laugh] tag
      wheezing       → VocalSound high-arousal OR [wheezing laugh]
      crowd bed      → Mixkit "big crowd laughing" looped/scaled
      groan-laugh    → VocalSound + Fish [groans] blend
  → layer: crowd_bed (low) + individualLaughs (mid) + reactions (high)
  → composite under performance audio at punchline + delay_ms
  → intensity scales: sample gain, crowd_bed density, reverb send
```

The crowd_state modulates which library tier dominates:
- hot club: dense individual laughs, fast onset, overlapping
- dead room: sparse, delayed, low intensity, maybe just 2 people
- TV taping: clean crowd bed + occasional standout laughs
- drunk friday: loud, sloppy, overlapping, some heckle-adjacent

| Source | What it gives | Size | Where |
|---|---|---|---|
| **prosody200** (Kaggle) | 62K segments × 15-dim prosody, 16.8% laugh labels | 6.7M | `theory/datasets/prosody200/` |
| **ali-wong** (Kaggle) | 925 timed captions, 352 laugh-scored 0–10, 120 topic groups | 96K | `theory/datasets/ali-wong/` |
| **StandUp4AI** (debz) | 3,617 videos, 130K+ laughter labels, word-level seq labeling, 7 languages | 2.2M | debz `/root/reference/comedy/standup4ai-dataset/` |
| **SMILE** (Google Drive) | 887 clips, laugh REASON annotations (why people laugh) — sitcom + TED | ~1G | need download |
| **"So You Think You're Funny"** (EMNLP 2021) | Humour quotient formula: laugh_duration / clip_duration → 0–4 scale, validated κ=0.6 | paper | formula only |
| **TIC-TALK** (CHum 2026) | 90 Netflix specials, 5400 topic segments; laughter autocorrelation AUROC=0.643 (crowd contagion); kinetic energy r=−0.75 vs laughter (stillness-before-punchline) | paper | findings only |
| **KT archive** (debz) | 276 Jev-tagged sets + crowd_ord labels + 423 Casey laugh timestamps | 332M | debz |
| **Our audio** | 10 wavs (Casey/Ari/Pickles/Louis) + scribe word timestamps | local | `~/voice_engine/sets/` |

## Architecture: empirical prediction + Jev texture

Literature validation (see below) shows the laugh prediction should be
**empirical** (trained on structure→laugh mappings from real data), not
Jev reasoning from text alone. Jev's role is texture selection and
mechanism labeling — not laugh prediction.

### The three-stage pipeline

```
STAGE 1: STRUCTURAL FEATURE EXTRACTION (from audio + transcript)
  Pause features (dpv framework):
    - setup_rhythm: mean pause duration in setup (baseline ~0.6s)
    - pause_escalation: do pauses lengthen toward punchline?
    - pre_punchline_pause: pause duration in [punchline-2s, punchline)
    - pause_variability: std of pause durations (deviation from rhythm)
  Semantic features (uncertainty & surprisal):
    - setup_uncertainty: LM entropy while generating setup (multiple readings?)
    - punchline_surprisal: -log P(punchline | setup) from LM
    - semantic_distance: 1 - cosine(setup_embed, punchline_embed)
    - distance_shift: slope of semantic distance over time (escalation)
  Performance features:
    - speech_rate: syllables/sec (slower = more prediction window)
    - kinetic_energy: from MediaPipe (TIC-TALK: stillness before punchline)
    - mechanism_tags: Jev nouls on the text (rigidity, garden_path, etc.)
    - laugh_history: recent laugh events (TIC-TALK: autocorrelation AUROC 0.643)

STAGE 2: EMPIRICAL LAUGH PREDICTION (trained on real data)
  Input: Stage 1 features
  Output: laugh_profile (continuous 0-1 per trait)
  Training data:
    - ali-wong: 925 captions with laugh scores 0-10 → magnitude, timing
    - prosody200: 62K segments with audio features + laugh labels
    - StandUp4AI: 130K word-level laugh labels
    - KT archive: 276 sets with crowd_ord + mechanism tags
    - TIC-TALK: 90 specials with aligned text/audio/laughter
  Model: gradient boosting or small neural net (CPU-trainable)
  This model LEARNS what structural patterns earn which laugh profiles

STAGE 3: JEV TEXTURE SELECTION (reasoning layer)
  Input: predicted laugh_profile + mechanism_tags + crowd_state
  Output: laugh_type + rendering parameters
  Jev picks the right laugh CHARACTER from the mechanism:
    - garden_path → explosive release (long buildup, sudden payoff)
    - benign_violation → shocked wheeze (wrong + safe)
    - status_reversal → sharp "oooh" → roar
    - escalation → rising waves
  This is where Jev's reasoning adds value — mapping mechanism to texture
```

### Why this architecture (literature-validated)

1. **Timing dominates content** (dpv 2026): pause patterns predict
   appreciation better than semantic features. Stage 1 extracts these.
2. **Incongruity is computable** (ACL 2021): surprisal and uncertainty
   from any LM distinguish jokes from non-jokes. We measure these.
3. **Contagion is the strongest single signal** (TIC-TALK): laugh history
   alone gets AUROC 0.643. Stage 1 includes laugh_history.
4. **Escalation predicts success** (dpv): distance_shift (rising
   unpredictability) correlates with appreciation. Stage 1 extracts this.
5. **Jev's value is texture, not prediction**: given "this is a garden_path
   with high magnitude," Jev picks the right laugh type. That's reasoning
   over mechanism, not over raw text.

```
LAYER 1: DETECT — is there laughter in this audio window?
  model: prosody200 logistic (feat8-dropped, AUC 0.58)
  backup: StandUp4AI Whisper-AT ensemble
  input: 15-dim prosody features (F0, energy, MFCC, spectral)
  output: p(laugh) per 32ms frame

LAYER 2: MAGNITUDE — how big is the laugh?
  formula: laugh_duration / window_duration (from EMNLP 2021, κ=0.6)
  continuous 0–10 scale (ali-wong calibration set)
  maps to our POG strength (0–4 crowd_ord)

LAYER 3: TIMING — where does the laugh fall relative to the punchline?
  metrics (from TIC-TALK + louistheory1.md):
    - anticipatory_laugh_ratio: laughs in [punchline−3s, punchline) / total
    - post_punchline_peak: time from punchline to max laugh intensity
    - mid_sentence_pct: laugh starts inside a sentence (Casey: 16.6%)
    - laugh_curve_slope: linear fit of laugh magnitude [punchline−5s, punchline+5s]
    - stillness_before: mean kinetic energy [punchline−2s, punchline) vs baseline
      (TIC-TALK: r=−0.75, validates Louis CK "stillness before punchline")

LAYER 4: REASON — WHY did the audience laugh?
  maps to Jev mechanism nouls (kt_jev_annotate.py):
    rigidity, status_reversal, displacement, identity_contradiction,
    self_awareness, specificity, escalation, garden_path,
    benign_violation, audience_alliance
  SMILE reasoning annotations as training signal (when downloaded)
  Jev noul probabilities already on 276 KT sets

LAYER 5: CONTAGION — crowd momentum (TIC-TALK: AUROC 0.643 alone)
  autoregressive: p(laugh_t) = f(features_t, laugh_history[−5s,0])
  captures Provine 1992 crowd-contagion effect
  strongest single predictor — must be in ensemble
```

## The killer feature: Jev multi-dimensional laugh scorer

Not laugh/no-laugh. A **continuous 0-1 vector** across theory-driven traits,
each with reasoning. Jev's noul system applied to laugh evaluation:

```json
{
  "laugh_profile": {
    "magnitude":     0.72,   // how big was the laugh overall
    "anticipation":  0.85,   // pre-punchline lean-in (TIC-TALK stillness)
    "release":       0.91,   // explosive vs mild after punchline
    "contagion":     0.78,   // did it spread through the room
    "warmth":        0.63,   // laughing WITH vs AT (SMILE valence)
    "specificity":   0.88,   // unique to THIS joke vs generic
    "mechanism_fit": 0.82,   // laugh matched intended mechanism
    "timing":        0.95    // right delay, right duration
  },
  "reasoning": {
    "magnitude": "3.2s roar on the Monopoly punchline, peak at 2.1s",
    "anticipation": "chuckling 2s before punchline during Candyland setup",
    "warmth": "audience laughing with the daughter, not at her",
    "timing": "0.4s reaction lag — natural Provine window"
  },
  "mechanism": {
    "benign_violation": 0.91,
    "garden_path": 0.74,
    "status_reversal": 0.67,
    "specificity": 0.88
  },
  "laugh_type": {
    "roar": 0.6, "wheezing": 0.1, "chuckle": 0.2, "groan": 0.1
  },
  "crowd_state": {"heat": 7, "type": "club", "trajectory": "rising"},
  "verdict": "STRONG — garden_path earned explosive release, high specificity, warm contagion"
}
```

This is one Jev call per minute (~400 tokens). The nouls are calibrated
(0.4-0.6 uncertain band). Reasoning makes it debuggable — not a black box.

### Why this is the RL reward signal

- Continuous (not binary) → dense reward, faster learning
- Multi-dimensional → can optimize for specific traits (warmth vs shock)
- Theory-grounded → interpretable, can diagnose WHY a minute failed
- Reasoning attached → human can audit, Jev can self-critique
- Calibrated → 0.4-0.6 band flags uncertain cases for human review

### Kill Tony as the RL environment format

KT already solved the format problem:
- **1 minute** (hard time limit — forces economy)
- **Live crowd response** (ground truth laughter, not judges' opinions)
- **Kill or not** (binary outcome + crowd intensity)
- **Bench warmers** (competition — better acts stay)

Our extension: same format, AI comedians, simulated crowd.

```
AI KILL TONY EPISODE:
  1. AI comedian (character pack) gets 60s
  2. Generates minute (Jev picks modulator/mechanism)
  3. Fish renders delivery
  4. Laugh sim renders crowd response
  5. Jev scores laugh_profile (the 0-1 vector above)
  6. Score = weighted combination of laugh_profile traits
  7. Next comedian up
  8. Over episodes: policy improves, characters evolve
```

Training data: real KT sets (276 tagged + crowd_ord labels) calibrate the
simulator. Once simulator matches real crowd responses on held-out comics,
it's trustworthy for scoring AI sets. Then the RL loop runs without humans.

### The endgame (owner, verbatim)

> "one brand new AI minute with simulated crowd but it's actually funny.
> once we have that it's game over literally."

What "actually funny" means, operationally:
- laugh_profile.magnitude ≥ 0.7 (big laugh)
- laugh_profile.warmth ≥ 0.5 (laughing with, not at)
- laugh_profile.specificity ≥ 0.7 (earned by THIS joke, not generic)
- laugh_profile.mechanism_fit ≥ 0.6 (the laugh matches the intent)
- Jev verdict contains "STRONG" or "SOLID"

That's the pass threshold for an AI minute. Calibrate against real KT sets:
what laugh_profile do actual roaring/big_laughs sets score? That's the bar.

```python
laugh_sim(audio_path, punchline_times) -> {
  "laugh_curve": [...],          # p(laugh) per frame
  "total_laugh_seconds": float,
  "humour_quotient": float,       # L2 formula, 0–1
  "anticipatory_ratio": float,    # L3: pre-punchline / total
  "stillness_score": float,       # L3: kinetic energy dip before punchline
  "contagion_auc": float,         # L5: autoregressive lift over base rate
  "mechanism_laugh_map": {...},   # L4: which mechanisms earn which laugh shapes
  "vs_anchor": {...},             # cosine distance to Casey/Ari/Pickles curves
  "verdict": "pass" | "iterate" | "fail"  # threshold: humour_quotient >= 0.3
}
```

## Integration points

| Component | Integration |
|---|---|
| `performance_dna.py` | add laugh_curve to numeric DNA; calibrate compares laugh curves not just embeddings |
| `audition/battle.py` | battle score = 0.5×Jev + 0.5×laugh_sim (when no live audience) |
| `audition/prefilter.py` | laugh_sim on TTS preview before full battle |
| `theory/extract_performance.py` | run laugh_sim after scribe; attach to killtony-minutes/*.json |
| `freaks/*/delivery.json` | store predicted laugh curve per beat as acceptance metric |
| Arena / POG | when live votes arrive, compare laugh_sim prediction to actual POGs → recalibrate |

## Training plan (tiny-box friendly)

1. **Structural feature extraction** (next): extract dpv-style pause features
   + semantic surprisal from KT/Ali Wong sets. Pure code, no training. This
   is the foundation everything else trains on.
2. **Empirical laugh predictor**: train gradient boosting on structural
   features → laugh labels (ali-wong scores, KT crowd_ord, StandUp4AI
   word-level). CPU-trainable, ~10 min. Measure AUC/correlation on held-out.
3. **Jev texture validation**: given predicted laugh_profile + mechanism,
   does Jev pick the right laugh_type? Test on 276 KT sets (compare Jev
   texture choice to actual crowd response). One Jev call per set.
4. **SMILE calibration**: do Jev's mechanism nouls match SMILE's 887 free-text
   reasons? Extends our KT tags with sitcom+TED laughter patterns.
5. **Contagion term**: fit autoregressive laugh_history model on KT timestamps
   (423 events). TIC-TALK shows this alone gets AUROC 0.643.
6. **Laugh library**: download VocalSound (21K individual laughs) + Mixkit
   (crowd beds). Compositor picks/renders from these based on Jev texture.
7. **First AI Kill Tony episode**: 3 AI comedians, 1 minute each, empirical
   predictor scores the laugh_profile, Jev picks textures, Fish renders.
   The endgame demo.

## What this unlocks

- **Calibration loop closed:** Fish render → laugh_sim → compare to anchor →
  adjust direction → re-render. No human wait. Dracula iterates tonight.
- **Jev validation:** do mechanism tags predict laugh magnitude/timing?
  Cross-check 276 tagged sets against their crowd_ord labels.
- **Live show prep:** laugh_sim becomes the automated booker — kills sets
  that won't land before they reach a stage.
- **The alien act:** once laugh_sim understands what earns laughter on
  human material, applying a new perspective (LGBT, alien, etc.) over the
  same mechanisms is a prompt change, not a retrain.

## Status

- [x] prosody200 downloaded + trained (AUC 0.58 honest)
- [x] 10 local wavs scored (theory/laugh-model/predictions/)
- [x] ali-wong downloaded (validation set ready)
- [x] StandUp4AI cloned (130K labels, 2.2M, on disk)
- [x] **SMILE downloaded + extracted** (887 laugh reasons in `theory/datasets/smile/annotations/`)
- [x] Jev laugh scorer spec written (this file)
- [ ] ali-wong laugh-curve validation run
- [ ] Jev laugh scorer prototype (one call, test on Casey audio)
- [ ] L3 timing metrics implemented + validated on Casey (423 laugh timestamps)
- [ ] L5 contagion term fitted
- [ ] laugh_sim wired into performance_dna.py calibration
- [ ] laugh_sim wired into battle.py as POG proxy
- [ ] VocalSound + Mixkit laugh library downloaded
- [ ] First AI Kill Tony episode (simulated crowd, 1 minute)
