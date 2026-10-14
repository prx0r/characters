# SNL-VISION — sketch engine, live quickfire, video-reaction shows

Owner brief 2026-10-14. The delivery engine doesn't stop at stand-up minutes.

## 1. Sketch show (SNL grammar)

Same engine, new format: a sketch = fixed characters (voice cards + domain
recipes + collision shapes) performing scripted material blocks. SNL grammar:
cold-open (host = sage_narrator archetype), desk bits (hype_host), character
return sketches (status_reversal collision, same character different scene).
Delivery arcs come from stencils; material blocks are swappable per week
(current-events slots — the "joke blocks about current events" the owner
wants). Roster is LIVE: characters ranked by view/laugh metrics promote to
host slots; relegated characters drop to background. Same league mechanic
as VISION.md, applied to sketch.

## 2. Live quickfire (Jev in the seat)

Jev (jev_decide.py) currently picks modulator+operator per minute. Live
quickfire = Jev in REAL TIME during a show:
- viewer question / current event arrives
- Jev picks character × collision shape × delivery recipe from priors
- engine renders the line (<2s on s2.1-pro-free) → host reads or TTS speaks
- laugh/POG feedback updates Jev's priors live (ARF-RLHF: continuous
  satisfaction trajectories, not binary likes)

## 3. Calibrated decision models (the Jev upgrade path)

Owner's research → our mapping:

| Paper | Our use |
|---|---|
| LoRe (low-rank reward) | owner taste = weighted combo of basis rewards (per-archetype prefs); learnable from few his verdicts on dataset entries |
| P-TTT (test-time training) | per-show: his last N verdicts → fast weights → this show's picks adapt without retraining |
| PEBS (per-rater calibration) | every voter (owner, crowd, model) gets own slope/offset — never pool raw scores; our Wilson-before-crowns rule, formalized |
| ARF-RLHF | POG timestamps = continuous satisfaction trajectory; score the SET, not the bit |
| OTS/record-replay (Opnova etc.) | owner demonstrates a good minute once (dataset entry verdict=good) → engine mines the collision+delivery as a reusable skill (stencil) |
| PersonalAlign hierarchical intents | mine his long-term verdicts: moment (this set: good) → preference (deadpan over manic for villains) → routine (villain characters always get deadpan arcs) — proactively fills gaps |

Jev + these = the live interviewer brain: given an embedding of "what the
room wants now," answer in character in realtime.

## 4. Alibaba stack (qwen omni)

Alibaba/qwen-omni lane (owner-approved alibaba.py exists): multimodal
realtime — feed the live video of a sketch/reaction show to qwen-omni for
host banter + segment transitions. The voice engine speaks the lines;
qwen-omni handles improv glue between scripted blocks. Costs: qwen flash
tier via existing bl CLI (ASK before spend per AGENTS).

## 5. Video-reaction shows

The "humans load vids, characters react" format:
- human submits a video URL → clip ingested (yt-dlp or upload)
- roster of characters each react IN CHARACTER (voice card × domain ×
  collision with the video's topic — topic extracted via cf_asr/ASR)
- live stream = host (sage_narrator) + rotating reactors ranked by Jev
- agent-only mode: same pipeline, no human host, characters debate the clip
This is VISION.md's SURROUNDED + podcast pattern, pointed at video input.
