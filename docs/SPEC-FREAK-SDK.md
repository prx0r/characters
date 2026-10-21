# SPEC-FREAK-SDK v0.1 — voice.tags + delivery.style

**Status:** pilot (Buddha). One method: measure a real comic, wear their
delivery. AI won't invent good delivery; it can copy delivery we've measured.

**Theory contract:** `theory/attardo-timing-map.md` — every timing rule maps
from Attardo ch10/GTVH (KR-NS = the NS knowledge resource = delivery).
Knobs T1–T12: pre-punch hold floor, resolution window, Norrick contrast,
laugh-scaled re-entry, flat-frame protection.

## The contract (new fields in `freaks/<slug>/character.json`)

```json
"voice": {
  "provider": "edge-tts",          // fallback chain unchanged
  "voice_id": "en-US-GuyNeural",
  "tags": {                        // NEW — Fish casting brief
    "tone": ["detached", "unhurried"],
    "register": "mid-low male",
    "texture": "slightly dark storyteller",
    "casting_query": "calm dry male narrator deadpan low warm",
    "f0_target_hz": 127,
    "reference_text": "one sentence in the character's mouth"
  }
},
"delivery": {                      // NEW — how they perform
  "style": "norm_macdonald",       // key into voicelab/styles/<slug>.json
  "archetype": "suspension_deadpan",
  "overrides": {                   // character beats on top of the style
    "punchline_hold_ms": 1500
  }
}
```

## Style profiles (`audition/voicelab/styles/<slug>.json`)

delivery_style.v1, produced by `style_harvest.py` from word-timing scribes
(theory/scribe/) + delivery acoustics (voicelab/dataset/real_*.json when the
clip was measured). Fields that matter:

- `engine_recipe` — Fish knobs the engine obeys: wpm, speed_scale,
  pause_ladder [setup, pre_punch, tag], coupling_ratio, volume_db,
  dynamics_db, pitch_std_st, emotion_cues, emotion_forbidden
- `measured` — medians + IQR per clip (evidence)
- `technique_mix` — mechanism tag frequencies

Self-test: `python3 audition/style_harvest.py louis --check` — harvested
numbers must land near theory/LOUIS-FORMULA.md (PASS as of 2026-10-21:
wpm 170/163, speed 0.84/0.85, ladder within 0.45s).

## Pipeline

1. **Cast** — `voice.tags.casting_query` → Fish library search → A/B samples
   on s2.1-pro-free → write `voice.fish.reference_id` (voicecast.py slot).
2. **Render** — delivery_engine reads `delivery.style` → loads style JSON →
   per-beat pauses/cues/speed from recipe + character overrides → Fish.
3. **Verify** — voice_judge (wpm/pitch-var/dynamics vs style targets) +
   word-diff (VERIFY_ASR=bark or CF whisper). Knobs tuned keep-if-better.

## Archetype → style mapping

`audition/voicelab/archetypes.json` still owns comedian↔archetype. A style
profile is a *measured instance* of an archetype. Characters reference the
measured style, not the raw archetype. Pooling multiple comedians of one
archetype (`--archetype deadpan --members norm,...`) gives an archetype
profile; per-comedian deltas are the "how related" vector.

## Rules

- Clips/scribes stay local, analysis only; styles are numbers, never lines
  (copyright rule). No verbatim material in profiles.
- Free tier only (search, clones, s2.1-pro-free). Ask before ANY spend.
- Scores propose, humans dispose — conformance ≠ funny; it means the render
  matches mechanics humans laughed at.
