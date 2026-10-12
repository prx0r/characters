# Ari Engine — How a Performance Becomes a Reusable Character Animation

**Date:** 2026-10-12  
**Status:** Working end-to-end on 5 Ari Matti sets  
**Repo:** `prx0r/characters` master

---

## What this document is

The complete pipeline from raw stand-up video to a character (Ralph) performing
the same physical/vocal delivery. Every data layer, every schema, every mapping.
This is the spec for reproducing any comedian's performance on any character.

---

## The pipeline (one diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│  SOURCE: 60–120s stand-up clip (mp4, any comedian)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  MEDIAPIPE  │  │   GEMINI    │  │  ALIBABA    │
   │  (local)    │  │  3.8-flash  │  │  ASR (free) │
   │             │  │  (cloud)    │  │  (cloud)    │
   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
          │                │                │
          ▼                ▼                ▼
   numeric dials     semantic tags    word timings
   @15Hz             per-segment      @ms precision
          │                │                │
          └────────────────┼────────────────┘
                           ▼
              ┌────────────────────────┐
              │  PERFORMANCE.V1        │
              │  unified timeline      │
              │  (Stage Lab schema)    │
              └───────────┬────────────┘
                          │
              ┌───────────┴────────────┐
              ▼                        ▼
     ┌────────────────┐      ┌────────────────┐
     │ Ralph SVG      │      │ Rive puppet    │
     │ player (HTML)  │      │ (future)       │
     │ WORKING ✅     │      │ scaffolded     │
     └────────────────┘      └────────────────┘
```

---

## Layer 1 — MediaPipe (local, free, numeric)

**Script:** `theory/extract_performance.py`  
**Model:** Face Landmarker + Pose Landmarker (Tasks API, CPU)  
**Rate:** 15 Hz (every 2nd frame of 30fps)  
**Output:** `*.granular.json`

### Face dials (per frame)

| Dial | What it measures | Range | Used for |
|------|-----------------|-------|----------|
| `brow_left` / `brow_right` | Brow height relative to eye line | ~0–0.5 | Anger (furrow = low), surprise (raised) |
| `brow_asym` | One-raised skepticism | ~0–0.1 | Suspicion, deadpan |
| `eye_open_left/right` | Eye aperture | ~0–0.15 | Blink, wide_eyes, squint |
| `mouth_open` | Jaw drop | ~0–0.5 | Speaking, surprise, shout |
| `mouth_wide` | Lip corner stretch | ~0–0.6 | Smile, sneer, tension |
| `head_yaw_proxy` | Head turn | ~0–1 | Look away, address |
| `head_pitch_proxy` | Chin up/down | ~0–1 | Nod, challenge, submission |

### ARKit blendshapes (52 dims, when available)

`bs_browInnerUp`, `bs_browDownLeft/Right`, `bs_jawOpen`,  
`bs_mouthSmileLeft/Right`, `bs_mouthFrownLeft/Right`,  
`bs_eyeBlinkLeft/Right`, `bs_eyeSquintLeft/Right`,  
`bs_mouthPressLeft/Right`, `bs_cheekPuff`, `bs_noseSneerLeft/Right`

These are the same 52 blendshapes Rive/Live2D can map to.

### Body dials (per frame)

| Dial | What | Range | Used for |
|------|------|-------|----------|
| `lean_x` | Torso lean forward/back | ±0.5 | Lean forward on emphasis |
| `lean_y` | Torso vertical shift | ±0.5 | Crouch, rise |
| `shoulder_tilt` | Shoulder asymmetry | ±0.3 | Shrug, tilt |
| `arm_open` | Arm extension from body | 0–1 | Open arms, gesture |
| `hand_face_left/right` | Hand-to-face distance | 0–1 | Mic hold, face touch |

### Derived features

Per-window (1s) aggregates: `brow_mean`, `brow_range`, `mouth_open_max`,  
`mouth_wide_max`, `lean_x_range`, `arm_open_mean`, `shoulder_tilt_abs`,  
`hand_face_right_min`. Plus velocity derivatives (`d_brow_left`, etc.).

**What this gives us:** Exact numeric body state at 15Hz. No interpretation —  
just geometry. This is the ground truth that Gemini's semantic tags can be  
validated against.

---

## Layer 2 — Gemini 3.8-flash (cloud, ~$0.01/set, semantic)

**Script:** `theory/gemini_performance.py`  
**Model:** `gemini-3.8-flash`  
**Input:** 480p compressed clip (~3MB), inline base64  
**Output:** `*.gemini.json`

### Segment schema (per 5–15s window)

```json
{
  "t0": 0.0, "t1": 12.5,
  "emotion": "gleeful",
  "emotion_intensity": 0.65,
  "body": {
    "lean": "neutral|forward|back",
    "lean_amount": 0.1,
    "head": "nod|jut|tilt_left|tilt_right|shake",
    "arms": "sides|open|crossed|mic_point|hand_to_face|gesture_out",
    "face": "neutral|annoyed|surprised|deadpan|smirk|grimace|wide_eyes|sneer|mock_horror",
    "brow": "neutral|raised|furrowed|one_raised|flat_angry",
    "micro_gesture": "text description"
  },
  "comedy": {
    "beat_type": "setup|premise|escalation|punchline|tag|callback|closer|button",
    "gtvh_operators": ["literalise", "double_meaning", "..."],
    "status_move": "down|up|flat|reversal",
    "note": "why this beat works"
  },
  "vocal": {
    "energy": 0.6,
    "pitch_shift": "flat|rise|fall|spike|drop",
    "pace": "slow|normal|fast|rapid_fire",
    "emphasis_words": ["Texas", "proud"],
    "note": "accent, tone, delivery style"
  }
}
```

### Gesture library (named reusable clips)

```json
{
  "name": "righteous_indignation_point",
  "t_guess": 51.0,
  "duration_est_s": 2.5,
  "body_params": {"lean": 0.4, "head_deg": 0.0, "arm_open": 0.8, "brow": -0.8},
  "emotion_tag": "mock_indignant"
}
```

These `body_params` are the bridge to Rive numeric inputs.

### Anger analysis (the key deliverable)

```json
{
  "present": true,
  "type": "fake_rage_for_joke",
  "body_signature": ["forward lean", "tense shoulders", "pointed finger"],
  "face_signature": ["tightened sneer", "narrowed eyes", "furrowed brow", "wide jaw"],
  "vocal_signature": ["volume spike", "vocal fry", "hard plosives"],
  "target": "ungrateful Americans",
  "release_or_withhold": "full explosive release",
  "contrast_before_after": "deadpan mock before → beaming smile after"
}
```

This is what "expressing anger" looks like as a data structure: body, face,  
vocal, target, release pattern, and the contrast that makes it funny.

**What this gives us:** Semantic interpretation of the performance — which  
emotion, which comedy mechanism, which physical signals carry it.

---

## Layer 3 — Alibaba ASR (free tier, word timestamps)

**Script:** `theory/align_speech_body.py`  
**Model:** `qwen-audio-3.1-asr-flash`  
**Input:** 32kbps mp3 via public URL (litterbox)  
**Output:** word-level timings in `*.granular.json`

```json
{"text": "passport", "t0": 58.2, "t1": 58.5}
```

~320 words for a 60s set. Aligns speech to MediaPipe windows →  
`speech_aligned_windows` with `anger_proxy` flags.

**What this gives us:** Exact word timings for lip-sync and beat alignment.

---

## Layer 4 — Performance.v1 (unified timeline)

**Script:** `theory/gemini_to_stage.py`  
**Schema:** Stage Lab `performance.v1`  
**Output:** `*.stage_timeline.json`

### Event types

| Kind | Fields | When |
|------|--------|------|
| `expression` | `id` (Ralph name), `source_emotion`, `intensity` | Segment start |
| `gesture` | `id` (Ralph gesture), `intensity` | Body triggers |
| `camera` | `id` (wide/medium/closeup/pushin) | Punchlines, closers |
| `hold` | `ms` (1200 default) | Punchlines |
| `speak_start` | — | Segment start |
| `lights` / `enter` / `exit` | — | Show bookends |

### Emotion → Ralph expression mapping

| Gemini emotion | Ralph expression | Visual effect |
|---------------|-----------------|---------------|
| neutral, deadpan | `deadpan` | Half-lidded, flat mouth |
| angry, mock_indignant, annoyed | `annoyed` | Furrowed brows, thin mouth |
| sarcastic, suspicious | `suspicious` | Narrowed eyes, low brow |
| defiant, confident | `confident` | High brow, smirk |
| gleeful | `self_satisfied` | High brow, smirk |
| manic, surprised | `surprised` | Wide eyes, open mouth |
| embarrassed | `embarrassed` | Raised brow, darting eyes |

### Body → Ralph gesture mapping

| Gemini body | Ralph gesture | SVG effect |
|------------|---------------|------------|
| `lean=forward` | `lean_forward` | Head group translates down 14px |
| `arms=open/gesture_out` | `small_shrug` | Body group translates up 8px |
| `head=jut/tilt` | `head_tilt` | Head rotates 8° |
| `beat_type=punchline` | `hold` + `eye_glitch` | 1200ms stillness + red slit pupils |
| `beat_type=closer` | `warm_rock_lean` | Head translates down 20px |
| `beat_type=tag` | `suit_adjust` | Body tugs left-right |

### Camera mapping

| Trigger | Camera |
|---------|--------|
| Default | `medium` (waist-up) |
| Punchline | `closeup` (1.35× zoom) |
| Closer | `pushin` (1.2× slow push) |
| End | `wide` (0.85× full stage) |

---

## Layer 5 — Ralph puppet (SVG player, working)

**File:** `theory/killtony-minutes/*_player.html`  
**Also served at:** `/stage/gemini/<stem>/player`

Standalone HTML, no server needed. Ralph is drawn as SVG:
- Green reptilian head (`#6b8f5e`) with slit-pupil eyes
- Navy suit with white shirt and red tie
- Microphone on stand
- Spotlight + red curtains + floor shadow

**What animates:**
- Brows rotate for `annoyed` (furrowed)
- Mouth ry/cy changes for `surprised` (open) vs `deadpan` (flat)
- Head group translates/rotates for lean, tilt, warm_rock
- Body group translates for shrug, suit_adjust
- Eyes go red slit for `eye_glitch`
- Camera label + zoom scale for wide/medium/closeup/pushin
- Emotion + beat_type HUD updates per segment

---

## Layer 6 — API endpoints (Flask, working)

| Route | What |
|-------|------|
| `GET /api/stage/gemini` | List all 5 sets with metadata |
| `GET /api/stage/gemini/<stem>/timeline` | Stage Lab timeline JSON |
| `GET /api/stage/gemini/<stem>/raw` | Full Gemini analysis JSON |
| `GET /stage/gemini/<stem>/player` | Standalone player HTML |
| `GET /stage/gemini` | Gallery page |

---

## What we have vs what's missing

### Working ✅

- [x] Numeric body dials (MediaPipe, 15Hz, free)
- [x] Semantic body/emotion/theory tags (Gemini, ~$0.01/set)
- [x] Word-level speech timestamps (Alibaba ASR, free)
- [x] Anger decomposition (body + face + vocal + target + release)
- [x] Named gesture library with numeric params
- [x] Performance.v1 timeline generation
- [x] Emotion → Ralph expression mapping (7 emotions)
- [x] Body → Ralph gesture mapping (6 gestures)
- [x] SVG puppet player with scrub + play/pause
- [x] Flask API + gallery page
- [x] 5 sets fully processed

### Not yet wired 🔧

- [ ] **Facial blendshapes → Rive numeric inputs**  
  MediaPipe gives 52 blendshapes. Rive state machine expects named inputs.  
  The mapping table exists in `modulators.json` but isn't called yet.

- [ ] **Audio → lip-sync (visemes)**  
  ASR gives word timings. Vosk viseme track is scaffolded in `stage.py`  
  (`_load_visemes`) but no audio is generated for Ari sets yet.  
  Need: TTS render of the set → Vosk → viseme events → mouth params.

- [ ] **Vocal delivery → animation intensity**  
  Gemini gives `vocal.energy` (0–1) and `pitch_shift`. These could scale  
  gesture amplitude and camera zoom. Currently only used for camera triggers.

- [ ] **Gesture library → reusable motion clips**  
  Gemini names gestures with numeric params. These could be stored as  
  reusable clips that any character can play, not just one-off events.

- [ ] **Cross-set anger comparison**  
  5 sets all have anger analysis. Comparing their `body_signature` arrays  
  would give a composite "how Ari does angry" model.

- [ ] **Rive state machine**  
  `ralph.json` has a `rive` block with state machine name and targets.  
  No `.riv` file exists yet. SVG player is the fallback.

---

## File inventory

```
theory/
  extract_performance.py      MediaPipe → granular.json
  align_speech_body.py        ASR + body alignment → anger report
  gemini_performance.py       Gemini → gemini.json
  gemini_to_stage.py          Gemini → stage_timeline.json + player.html
  tag_comedy_theory.py        Character models → theory.json
  build_perf_from_mediapipe.py  MediaPipe → performance.v1
  asr_timestamps.py           ASR helper
  ALIBABA_GPU_AND_MODELS.md   Stack reference

  killtony-minutes/
    kt704_ari_passport.granular.json           MediaPipe + ASR
    kt704_ari_passport_gemini.gemini.json      Gemini analysis
    kt704_ari_passport_gemini.stage_timeline.json  Stage Lab events
    kt704_ari_passport_gemini_player.html      Standalone player
    kt704_ari_set1.theory.json                 Comedy theory tags
    kt704_ari_passport.anger_speech_report.md  Anger × speech
    ... (same × 5 sets)

audition/
  app.py                    Flask API (gemini endpoints at line ~933)
  static/gemini_stage.html  Gallery page
  rigs/ralph.json           Ralph rig (expressions, gestures, Rive targets)
  stages/comedy_club.json   Stage venue
  modulators.json           Emotion → performative scaling
```

---

## How to run the full pipeline on a new set

```bash
cd /home/box/repos/characters

# 1. Compress source to 640p h264
ffmpeg -i input.mp4 -c:v libx264 -preset fast -crf 23 \
  -vf "scale=640:-2" -an proc.mp4

# 2. MediaPipe dials (local, free)
.venv/bin/python theory/extract_performance.py proc.mp4 --id my_set --skip-omni

# 3. Gemini semantic analysis (~$0.01, 30–90s)
.venv/bin/python theory/gemini_performance.py input.mp4 my_set_gemini

# 4. Stage Lab bridge → timeline + player
.venv/bin/python theory/gemini_to_stage.py \
  theory/killtony-minutes/my_set_gemini.gemini.json

# 5. Open player
# file://.../theory/killtony-minutes/my_set_gemini_player.html
```

---

## The anger model (what we've learned from 5 sets)

All 5 Ari sets have anger analysis. Composite findings:

| Dimension | Ari's signature |
|-----------|----------------|
| **Type** | `fake_rage_for_joke` or `mock_indignant` — never genuine hot anger |
| **Body** | Forward lean + pointed finger + tense shoulders |
| **Face** | Sneer + narrowed eyes + furrowed brow + wide jaw |
| **Vocal** | Sudden volume spike + vocal fry + hard plosives |
| **Target** | Always an idea/group, never a person in the room |
| **Release** | Full explosive release, then immediate smile/laugh |
| **Contrast** | Deadpan or whiny voice BEFORE → rage spike → gleeful AFTER |

The contrast is the comedy. The rage is a performance choice, not an  
emotion. This maps to `modulators.json` `angry.performative`:

```json
{
  "emphasis_delta": 0.15,
  "gestures": "sharp",
  "pace_delta": 0.1,
  "pause_mult": 0.7,
  "restraint_interaction": "low restraint into shouting"
}
```

To make Ralph "do angry like Ari":  
`emphasis_delta=0.15` + `gestures=sharp` + `lean_forward` gesture +  
`annoyed` expression + `eye_glitch` after punchline + hold 1200ms +  
immediate `self_satisfied` after.
