# VOICE-ENGINE — character × domain architecture

Status: core loop LIVE (free tier only). Plan approved by owner 2026-10-14.

## The equation

```
final voice = character timbre (voice card)
            × domain recipe (general preset, fish knobs)
            × within-domain fine-tune (character/performer offsets)
```

Example: reptilian-comedy =
`reptilian voice card × comedy domain recipe × (ari/Casey-style micro-offsets
tuned for that character's persona)`.

Sleep-reptilian = same card × sleep recipe (no comedy offsets). One timbre,
many domain states. That's the matrix.

## Layers (what feeds what)

| Layer | Source of truth | Lives in | Controls (fish knobs ONLY) |
|---|---|---|---|
| Timbre | reference voice probe (owner-sent ids) or voice-design prompt | `audition/voicelab/voices.json` | choice of `reference_id` / voice-design instruction |
| Domain recipe | exemplar text read by 2+ domain reference voices → measured signature → transfer-tested on a neutral voice | `audition/voicelab/domains.json` | `[emotion]` cue, temperature, prosody.speed, volume, text phrasing (…, trailing) |
| Fine-tune | performer calibration loops (exact-words wpm matching, ari/casey) | `voicelab/calibrate/*.json` | per-segment cue ladders, speed deltas, temp per beat |

NOT controls (do not waste time): Hz targets, formants as input. Those are
MEASUREMENTS for judging only. Fish only accepts: cue, temperature, top_p,
speed (0.5–2.0), volume (dB), pronunciation, voice choice.

## The judging stack (A/B vs live set)

- delivery: wpm (word timestamps), pitch-var, dynamics, level — `voice_judge.py`
- timbre (stats-level vs `theory/killtony-minutes/*.acoustic.json`):
  centroid, MFCC-13, proxy jitter/shimmer — `voice_judge.timbre_profile()`
- corpus bands: `theory/vibe-bands.json` (distilled from KT analysis,
  performer blocks: ari_matti, casey_rocket)
- human ears dispose; scores propose (same rule as POG)

## Domain presets (distilled so far)

- **sleep** — recipe `[relaxed] temp.35 speed.72 vol-1.5`, signature slow +
  dark voice + drowsy glides (NOT flat). Transfer-proven on narrator voice.
- **comedy/standup** — composite arc (sub-states, from exact-word calibrations):
  manic `[excited] .85/1.30` · deadpan `no-cue .45/1.69` · gleeful
  `[delighted] .90/1.54` · mock-indignant `[frustrated→angry] .85/1.56`.
  Ari vs Casey = fine-tune differences WITHIN the domain (cue vocabulary,
  which sub-states, ordering).
- **seductive** — glides `[calm] temp~.5 speed~.75 vol-2`; warm vs ice split =
  variance/level fine-tune (see voices.json sultry pair).
- **whimsical** — level-float: temp~.4 speed~1.15, no punch cues; voice does
  the highness (luna card).
- **narration** — neutral knobs, voice-selected (narrator card: mid+even).

## Roadmap (autonomous lane)

1. Owner sends more reference voices → carded (probe text fixed for comparability)
2. Each new domain: exemplar text + 2 reference voices + transfer test
3. Fine-tune pass per character pack: delivery.json beats get domain +
   per-beat offsets; compose_set uses them
4. When API credit lands: voice-design prompts from cards (timbre without
   reference) — `voicelab/ab-prompts/*.json` ready to fire
5. MCP (connected): library voice search to AUTO-FILL domain reference slots

## Money

Everything above: `s2.1-pro-free`, $0. voice-design blocked on 402 (needs
API credit top-up) — owner said no spend until then.
**Credit policy (owner rule):** default synthesis = free API forever; MCP TTS
only for one-shot identity checks (~100 credits, always print
`credits_charged`); clone creation is free; ask with exact numbers before
ANY new charge.

## The KT → character pipeline (the actual product loop)

1. **Mine a KT set** → `theory/scribe/*.json` (word timestamps) +
   `*.gemini.json` (emotion arcs) + `*.acoustic.json` (timbre stats).
2. **Freeze a standup profile** (`voicelab/profiles/<set>.json`): exact
   words per segment + per-segment recipes (temp/speed/cue/vol). Voice is a
   SLOT, not part of the profile. See `kt704_standup.json`.
3. **Map profile → character archetype.** The delivery IS the casting:
   wild-deep roast energy (var 6+, dyn 51dB) → dracula/villain types;
   flat-narrow deadpan (var <2) → cryptkeeper/creepy-narrator; manic-spike
   → chaotic gremlins. Owner mapping: "mr pickle delivery = dracula".
4. **Drop a voice into the slot**: library card from `voices.json`, a
   private clone (`mcp_fish.py` + `create_voice_clone`, creation $0), or
   default. Render: same profile text+recipes, new voice_id.
5. **Verify loop** (`verify_set.py`): faster-whisper transcribes the
   render, word-diff vs intended text, auto-fix (slow down, re-cue) until
   match is clean. Catches muffled/unsaid words.
6. Fine-tune with the ari/casey RL machinery (`ari_set.py`) when a
   character needs its own arc inside a domain.

Stencil demo (2026-10-14): `kt704_standup` performed by ari clone,
spongebob, kid, roast — same words+recipes, four identities.

## Portable setup (another box)

```bash
# 1. deps (no torch; CPU only)
python3 -m pip install faster-whisper          # verify-loop ASR
# ffmpeg required

# 2. free-tier key
echo 'FISH_API_KEY=...' > audition/.env        # chmod 600; gitignored

# 3. Fish MCP (identity search/clone; plan credits)
opencode mcp add fish-audio --url https://api.fish.audio/mcp
opencode mcp auth fish-audio                   # browser OAuth; token in
                                               # ~/.local/share/opencode/mcp-auth.json
                                               # (auto-refresh handled by mcp_fish.py)

# 4. smoke
python3 audition/compose_set.py kappa-kyle-cucumber-debt --dry-run
python3 audition/mcp_fish.py call get_credit_balance '{}'
ARI_VOICE_ID=<clone> python3 audition/ari_set.py --rounds 1
python3 audition/verify_set.py --voice spongebob
```

Layout contract: engine = `audition/{fish_tts,voice_judge,mcp_fish,
compose_set,calibrate_*,ari_set,verify_set,ab_voice,voicecast}.py`;
registries = `audition/voicelab/{voices,domains}.json` +
`voicelab/profiles/*.json`; corpus bands = `theory/vibe-bands.json`.
Everything serializes to JSON; renders stay untracked (wav/mp3 gitignored).
