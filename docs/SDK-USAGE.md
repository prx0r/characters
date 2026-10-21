# Delivery SDK — how to use it, how to extend it

The comedy delivery SDK lives here. One sentence: **a character profile
wears a harvested real-comic's delivery, and the engine renders it on Fish
(free tier) with Attardo-grounded timing.** Theory contract:
`theory/attardo-timing-map.md`. Field contract: `docs/SPEC-FREAK-SDK.md`.
Freaktown handoff: `docs/DELIVERY-SDK-INTEGRATION.md` (their repo).

All commands from `audition/`. All Fish usage is `s2.1-pro-free` ($0).
Ask before ANY spend (AGENTS.md).

## Use

### 1. Render a character's minute (audio + timings + sealed set)

```bash
python3 delivery_engine.py minute.txt \
  --comedian buddha-ultimate-deadpan \   # = freak slug (reads character.json)
  --out my_render \                      # -> audition/audio/my_render.wav
  --seal /tmp/sealed_my_render           # -> sealed-set.v1 bundle for freaktown
# plan only, no TTS:
python3 delivery_engine.py minute.txt --comedian buddha-ultimate-deadpan --dry-run
```

What happens: character profile → `delivery.style` → style JSON → per-beat
pauses (pre-punch hold floor, resolution window scaled by predicted laugh),
Norrick speed contrast (prompt-decomposed, clean-zone rule kept), cues from
the style vocabulary (forbidden cues fall back), Fish render with style
volume/temperature + cast voice → assemble with exact gaps.

Sealed bundle (4 files): `set.wav`, `timeline.json` (exact ms),
`mouth_cues.json` (energy envelope), `set_plan.json` (profile + per-beat
performance; character actions win — `koan_hold` → deadpan + hold).

### 2. Verify (basics only — the judge never judges taste)

```bash
VERIFY_ASR=bark python3 verify_set.py --profile <p> --voice <v>   # word fidelity (local Bark 3.0)
python3 voice_judge.py audio/my_render.wav --vibe deadpan          # wpm/pitch/dyn vs bands
```
Bundled facts live in `stats.sealed` + timeline (hold ms present? window
present?). Funnier/arena/humans decide funny. Model scores propose.

### 3. Watch (optional, paid-bytes)

Feed the wav + frames + spec to `qwen3.8-omni-flash` (input_audio +
image data URLs; script pattern: box `/tmp/opencode/qwen/review_sealed.py`).
It reports mechanics only: deadpan read, hold detected, pace, punch land.

### 4. Play on stage (freaktown)

Push bundle to their sets host, `loadSealedSet(url)` → PerformancePlan.
Their `stage-runtime/tests/sealedSdkExport.test.ts` is the contract test
(fixture regenerated from `--seal` output).

## Extend

### New style from a comic (the core loop)

1. Get word-timing scribes into `theory/scribe/<name>.json`
   (`{words:[{text,start,end}]}`, optional `<name>_laughs.json` with
   `{laughs:[{t}]}`; acoustics block matched from
   `voicelab/dataset/real_*.json` `delivery` when available).
2. Harvest:
   ```bash
   python3 style_harvest.py <name> --archetype <deadpan|sincere_storyteller|...> [--check]
   ```
   → `voicelab/styles/<name>.json`. Self-test pattern: compare against a
   hand-measured formula (`louis --check` is the reference; keep it PASS).
3. Wire a character to it: `"delivery": {"style": "<name>", "overrides": {...}}`.

Rules: scribes stay local (analysis only); styles are numbers, never lines.
Archetype cue vocab lives in `style_harvest.ARCHETYPE_CUES` — add an
archetype there first (allowed/forbidden emotion cues).

### New character

Add `freaks/<slug>/character.json` fields:
```json
"voice": {"tags": {"tone":[], "register", "texture", "casting_query",
                   "f0_target_hz", "reference_text"}},
"delivery": {"style": "<harvested>", "archetype": "...",
             "overrides": {"punchline_hold_ms": 1500,
                           "post_punch_ms": 1000, "temperature": 0.5}}
```
Then cast: `casting_query` → Fish library search → A/B two candidates
(`fish_tts.synthesize_fish` sample line, $0) → measure with `voice_judge`
(pitch_std/f0 vs style targets) → write `voice.fish.reference_id` +
measurement note. Existing example: buddha pack.

### New timing rule

1. Claim → knob row in `theory/attardo-timing-map.md` (T-number, source page).
2. Implement in `delivery_engine.py` (assign_timings / scale_resolution_
   windows / generate_direction / render_beat — whichever owns the knob).
3. Prove it in audio (silence scan / voice_judge) and note it in HANDOVER.

Current T-map: hold floor (T1), resolution window (T2), Norrick contrast
(T3), laugh-scaled re-entry (T4), frame/emphasis protection (T5/T6),
flat-style no-stress rule (T6), audience loop (T7/T11).

### New mesh / avatar

`freaks/mesh-map.json`: slug → their cast GLB (`status: confident|
plausible|todo`; todo = stage appearance fallback). When freaktown adds
families (human/deity), fill entries — stage picks it up via
`set_plan.mesh`.

## Limits (honest)

- Free tier only; drama-3 hard-removed; voice-design paywalled (skip).
- Tag-emotion TTS (`qwen-audio-3.0-tts`) unavailable on our key — Fish is
  the expressive engine.
- Conformance ≠ funny: the SDK makes renders mechanically faithful to
  measured humans; humans dispose (Wilson/arena/Funnier).
- Box: no GPU, no torch; Bark 3.0 ASR is sherpa-onnx (~685MB at
  ~/models/bark3-onnx).
