# Research: Audio → Meaning → Body → Comedy Theory

Papers and repos that map directly onto our Ari Engine pipeline.
Date: 2026-10-12

---

## The key papers

### 1. TIC-TALK (arXiv:2603.21803) — THE paper for this exact problem
**"Timing In stand-up Comedy: Text, Audio, Laughter, Kinesics"**

90 Netflix specials, 5400+ temporally aligned segments. Pipeline:
- BERTopic 60s thematic segmentation
- Whisper-AT 0.8s laughter detection
- YOLOv8-pose → 17-joint skeletal coordinates @ 1fps
- Continuous kinematic signals: arm spread, kinetic energy, trunk lean

**Critical finding for us:** Kinetic energy **negatively** predicts laughter rate
(r = −0.75). Stillness-before-punchline is real. Comedians freeze their body
to concentrate audience attention on the verbal punch.

Also: personal/bodily content elicits more laughter than geopolitical.
Close-up proportion correlates with laughter (r = +0.28) — reactive montage.

**Maps to:** Our MediaPipe body dials + Gemini beat types. We can compute the
same kinetic energy signal and correlate with our acoustic peaks.

### 2. Decoding Humor (ICMI 2026) — the multimodal fusion architecture
Word-level sequence labeling for humor using:
- Text: LLaMA-2-1B embeddings (causal)
- Audio: BYOL-A self-supervised features
- Visual: MMPose skeleton
- Fusion: Multimodal Transformer (MulT)

**Finding:** Trimodal (T+S+A) beats unimodal. Cross-lingual training
regularizes better than monolingual.

**Maps to:** Our three-layer extraction (Gemini text + librosa audio +
MediaPipe body) is structurally identical. We're missing the fusion step —
a model that jointly reasons over all three.

### 3. Gesture-Speech Alignment (Kucherenko 2021)
**Key finding:** Gesture **semantics** predict from **text alone**.
Gesture **phase** (timing) predicts from **audio** alone.
Audio alone cannot predict gesture meaning.

**Maps to:** Why our pipeline works — Gemini reads the text for meaning
(which gesture), prosody-lens reads the audio for timing (when gesture).
We don't need to fuse them into one model; they're complementary.

### 4. JEGAL (Oxford, arXiv:2503.22668)
Tri-modal embedding space for gestures + speech + text.
Weakly supervised from in-the-wild video.
Gesture-word coupling loss learns which words get gestured.

**Maps to:** Could rank which of Ari's words carry the most gestural weight.
Our emphasis_words from Gemini are a cheap version of this.

### 5. GTVH Analyzer (GitHub: iamahmadyasin/gtvh-analyzer)
LLM pipeline for GTVH annotation:
1. Segment → narrative units
2. Detect humorous lines (discrete / register_clash / irony)
3. Annotate Knowledge Resources (Script Opposition, Situation, Target,
   Narrative Strategy, Language)

**Maps to:** Our Gemini GTVH tags are a single-pass version. This staged
approach would be more accurate — segment first, then annotate each line.

### 6. MWAHAHA (GitHub: J10Official, SemEval 2026)
GTVH-guided joke **generation** pipeline with DSPy:
- ContextEnricher → HumorArchitect → DeliveryStrategist → ContentWriter → HumorJudge
- 4 candidates, single-elimination tournament

**Maps to:** Generation side — once we understand Ari's formula, generate
new jokes in his style using GTVH modules.

### 7. MTLLFM (arXiv:2605.25409)
Temporal laughter localization. Outperforms Gemini 3 Flash and Qwen on
precise laughter onset/offset. Weakly supervised from clip-level labels.

**Maps to:** If we add audience laughter detection to Kill Tony footage,
this gives us the timing signal that validates our punchline detection.

---

## The Ari Engine + research stack

```
Ari video
  │
  ├─ MediaPipe ──────── body dials @15Hz (kinematic signals, TIC-TALK)
  ├─ Gemini ─────────── semantic tags, GTVH ops, emotion, gestures
  ├─ Qwen ASR ───────── word timings (ms precision)
  ├─ librosa ────────── F0, formants, jitter, shimmer, MFCC
  ├─ prosody-lens ───── pause map, pitch contours, acoustic peaks
  ├─ OpenFaceFX ─────── phoneme → viseme curves
  │
  └─ FUSION (what we're building)
       │
       ├─ Per-word alignment: word × body_state × acoustic × viseme
       ├─ GTVH annotation: script_opposition × logical_mechanism × target
       ├─ Gesture semantics: which words carry gestural weight (Kucherenko)
       ├─ Stillness-before-punchline: kinetic energy drop before peaks (TIC-TALK)
       └─ Laughter validation: audience response as ground truth (MTLLFM)
```

---

## What we're missing vs the research

| Gap | Research solution | Effort |
|-----|-------------------|--------|
| Laughter detection | MTLLFM / Omine model | Medium — need audience audio |
| Joint multimodal fusion | MulT architecture | High — need training data |
| Per-word gesture ranking | JEGAL coupling loss | Medium — can approximate with emphasis_words |
| Staged GTVH annotation | GTVH-analyzer prompts | Low — just restructure our Gemini prompt |
| Kinetic energy computation | TIC-TALK formula | Low — we have the keypoints |

---

## Immediate actions (low effort, high value)

1. **Compute kinetic energy** from MediaPipe body dials per TIC-TALK formula
   → correlate with our acoustic peaks. Validate stillness-before-punchline
   on Ari's sets.

2. **Staged GTVH annotation** — restructure Gemini prompt into 3 stages
   (segment → detect → annotate) following gtvh-analyzer.

3. **Per-word body state table** — join ASR words × MediaPipe windows ×
   Gemini segments × acoustic peaks into one CSV per set. This is the
   "why everything is done the way it is" table.

4. **Laughter detection** on Kill Tony footage — audience mics exist in
   the full episodes. Energy-based peak detection (librosa) as first pass.

---

## Ari validation (computed 2026-10-12)

Kinetic energy proxy from MediaPipe lean/arm/brow deltas, correlated with
prosody-lens acoustic peaks:

| Set | Peak | KE before → after | Pattern |
|-----|------|-------------------|---------|
| passport | 45.9s (rage) | 0.040 → 0.021 | **STILLNESS −48%** |
| passport | 56.2s (closer) | — | freeze after punchline |
| walking | 31.0s | 0.096 → 0.075 | **STILLNESS −22%** |
| ep715 | 96.7s (closer) | 0.060 → 0.016 | **STILLNESS −73%** |
| jamesbond | 22.2s | 0.054 → 0.036 | **STILLNESS −33%** |
| jamesbond | 12.4s | 0.032 → 0.065 | SPIKE +102% |
| diversifying | 66.6s | 0.016 → 0.065 | SPIKE +306% |
| diversifying | 45.6s | 0.051 → 0.063 | SPIKE +24% |

**Finding:** Ari has TWO punchline modes:
1. **Stillness** (4/7 peaks) — freeze body after verbal punch, let joke land
2. **Spike** (3/7 peaks) — explosive physical act-out AFTER the punch

This matches TIC-TALK's r=−0.75 finding but adds nuance: stillness is the
default, but Ari sometimes releases energy physically after the peak.
The spike peaks correspond to act-out moments (pointing, lungging).

Stillness windows cluster in setup phases (t=2-25s) — Ari is calm during
setup, moves during escalation, freezes on punchlines.
