# Fish Audio — compatibility map (imported 2026-10-14)

Docs: `docs/fish/` (llms.txt index, OpenAPI spec, key pages).
Live API enum confirms `drama-3` on `/v1/tts` and both timestamp-streaming endpoints.
Drama 3 shipped **2026-10-13** — one day old.

## What they have that we want

| Fish feature | Model / endpoint | Our equivalent today | Upgrade path |
|---|---|---|---|
| **Drama 3 directed TTS** — `[plain-language direction]` inline, `<whisper>/<emphasis>` word tags, sounds `[sigh]`, pauses, language switch | `drama-3` on `POST /v1/tts` | Modulator → edge-tts rate/pitch (fast/slow, ±40Hz) | `fish_tts.directions_for_modulator()` sends our modulators verbatim as Drama 3 directions |
| **Multi-speaker dialogue** — `<|speaker:N|>` + `reference_id: [id0, id1]` in ONE render | `drama-3` / s2-family | Duel = two separate synthesize() calls | One request renders a whole duel/podcast scene; speaker tags keep voices locked |
| **Timestamp streaming** — SSE audio chunks + cumulative word alignment per chunk | `/v1/tts/stream/with-timestamp` | Separate OpenFaceFX/viseme pass (lipsync.py) | Word timings arrive with the audio — avatar lip-sync without a second pipeline |
| **Free dev TTS** — same quality as s2.1-pro, $0 | `s2.1-pro-free` | edge-tts (free, flaky, rate-limited voices) | Drop-in free upgrade; bracket `[emotion]` tags work on it too |
| **Voice Design** — original voice from text description | `POST /v1/voice-design` ($0.01/req) | Fixed edge-tts voice map (3 characters) | Each character pack's `vocal_signature` field IS a voice-design instruction |
| **ASR with speakers + emotion cues + word timestamps** | `transcribe-1-pro` ($0.36/hr) | Scribe/DashScope; KT decoder | Replaces paid DashScope ASR; speaker_turns map to our riff_db schema |
| **MCP server** | `https://api.fish.audio/mcp` (OAuth) | none | Add to Hermes: voice casting, batch TTS, transcription by chat |

## The big one: modulators → Drama 3

Our `modulators.json` already encodes per-modulator cognitive/emotional/performative
fields. Drama 3 accepts exactly that kind of direction as plain text. The mapping
(`audition/fish_tts.py`):

```
paranoid       → [paranoid, speaking too fast, glancing at the doors]
condescending  → [condescending, slow and patient, explaining as if to children]
exhausted      → [exhausted, barely finding the energy to finish]
drunk_on_power → [expansive, drunk on adoration, saying the quiet part proudly]
```

Derived from `arousal` (pace), `defensiveness` (edge), `gestures` (physicality)
plus a signature-phrase lookup. The direction rides INSIDE the text — no schema
change, no new params. Our existing `tts_params()` (rate/pitch) stays as the
edge-tts fallback path.

**Sincerity doctrine check:** Drama 3 directions describe *how* to say something,
never *that it's comedy*. `[paranoid, speaking too fast]` does not break character.
The wink-veto list in gates.py still applies to SCRIPT text; directions are
delivery instructions to the voice engine, not lines the character says. Compliant.

## Formats unlocked

| Format | How Drama 3 does it |
|---|---|
| **Duel / Battle** | One request: `<|speaker:0|>[icy and precise] Your premise is a parking ticket.<|speaker:1|>[offended, escalating] It's a MANIFESTO` with two voice IDs |
| **Podcast / Shanty** | Multi-speaker scene render; completion metric on the single file |
| **Standup (avatar)** | Timestamp stream → word timings → drive casey_player-style SVG/Rive with lip-sync for free |
| **Surrounded** | N speaker IDs in reference_id array; crowd scene in one call |

## Money (rules apply)

- **`s2.1-pro-free`: $0** — safe. Key in `audition/.env`, smoke-tested 2026-10-14.
- **`drama-3`: NOT in the published API price table** (table lists s1/s2-pro/s2.1-pro only). Same family as s2.1-pro, likely $15/M — **ASK BEFORE ENABLING**, gate stays `FISH_PAID=1`.
- **Voice Design: $0.01/request** — ask before batch-generating 25 character voices.
- **ASR: $0.36/audio-hour** — ask before bulk-transcribing Kill Tony episodes.
- **Two separate billing pools** (do not mix them up):
  1. **API pay-as-you-go** (`FISH_API_KEY`, what our provider uses) — charges per usage, no plan needed.
  2. **Web-app package credits** (Plus/Pro/Max subscription) — MCP and the browser app draw from this. Avatar video/lip-sync ONLY works here, not via REST API.

## Full cost table (budget reference, updated 2026-10-14)

### API (pay-as-you-go, our key)

| Function | Model | Unit price | Our-job estimate |
|---|---|---|---|
| TTS standard | `s2.1-pro` | $15 / M UTF-8 bytes (~180k words ≈ 12h audio) | 60s audition ≈ 1.5-2KB text ≈ **$0.03**; 10min podcast ≈ **$0.30** |
| TTS dev/free | `s2.1-pro-free` | **$0** | anything during dev/testing |
| TTS Drama 3 | `drama-3` | unlisted, assume ~$15/M until confirmed | same as s2.1-pro ballpark |
| ASR | `transcribe-1-pro` | $0.36 / audio-hour | KT episode 1h = **$0.36**; Casey/Theo 1.5h ≈ **$0.54** |
| Voice Design | `voice-design-1` | $0.01 / request (not per candidate) | cast one character = 1 req = **$0.01**; 25 packs = **$0.25** |
| Voice clone (create model) | `POST /model` | included in platform terms; verify in dashboard | per-voice, check before batch |

### Web-app plans (credits pool — needed for avatar video)

| Plan | Price | Credits/mo | ≈ audio minutes | Avatar video? | Notes |
|---|---|---|---|---|---|
| Free | $0 | 8,000 | ~7 min | **No** (personal use only, no lip-sync) | daily image gens only |
| **Plus** | **$11/mo annual ($15 monthly)** | 250,000 | ~200 min | **Yes** | min tier for lip-sync; 10 private voices; 1 pro voice slot |
| Pro | $75/mo annual ($100 monthly) | 2,000,000 | ~1,620 min | Yes | 5 pro voice slots; 3 team seats |
| Max | $749/mo annual | 25,000,000 | ~6,250 min | Yes | 10 team seats |

Credits burn ≈ **600-625 per audio-minute**. Video generation is credit-metered
**per job at generation time** — MCP asks you to confirm the quoted price before
each render (no fixed public per-second price; varies by lip-sync model: HeyGen
Avatar 4, Creatify Aurora, Infinitalk, Veed Fabric, PixVerse, SyncLipSync v2/v3).

### Avatar / lip-sync specifics

- **Not in the REST API.** Web app (`fish.audio/app/image-video`) or MCP only.
- **Reusable avatar = free to create.** Upload/save a character portrait once
  (photo, DiceBear render, or image-model generation). It sits in your library;
  every subsequent lip-sync video pays only the per-generation credit cost.
  No separate "avatar slot" fee on paid plans (10 private voice slots on Plus;
  avatars themselves are just saved images).
- **Lip-sync video requires Plus minimum** ($11-15/mo). Free plan cannot do it.
- **Professional Voice Clone** (studio-quality, verified speaker, release
  capability) requires Pro plan. Instant Voice Clone (10s audio) is lower tier.
- Practical budget for us: **Plus plan ($11/mo) + API pay-as-you-go** gets us
  Drama 3 audio + avatar video for a handful of showcase Shorts. At ~200 audio-min
  credits/mo on Plus, that's plenty for character showcase clips (each Short
  ≈ 30-60s audio); video credit cost per job is quoted live and confirmed before
  spending.

## Key status

`FISH_API_KEY` in `audition/.env` (gitignored, 600). Smoke-tested: `s2.1-pro-free`
+ direction, 4s MP3 generated OK. Wallet balance not queryable with this key
(`/wallet/{user_id}/...` needs user-id path) — check usage in the web dashboard.

## Wire-in points (files)

- `audition/fish_tts.py` — NEW: provider + modulator→direction compiler
- `audition/tts_provider.py` — `AUDITION_TTS=fish` opt-in path (mirrors qwen path)
- `audition/prompt.py:tts_params` — direction dict added alongside rate/pitch
- character packs — `fish_voice_id` field per pack (after voice casting)
- theory/scribe — optional `transcribe-1-pro` backend for new podcast analysis

## Avatar product angle

Fish runs a full **Image & Video studio** (`fish.audio/app/image-video`): 8
lip-sync models (HeyGen Avatar 4, Creatify Aurora, Infinitalk, Veed Fabric,
PixVerse, SyncLipSync v2/v3), anime/3D/mascot/photoreal faces, script-to-video
with our Drama 3 voices baked in. This is what HeyGen/Viggle/Pictoria build on.
Also: full AI image gen (GPT Image, Nano Banana, Seedream) and video gen
(Seedance, Kling, Veo, WAN) via same studio/MCP — could generate character
portraits then make them talk in one flow.

**Do we still need our 2D stack (SVG players, Rive, MediaPipe rigs)?**
For *production avatar video* — no, Fish's lip-sync models are strictly better
(HeyGen-grade faces vs our hand-coded SVG). Keep the 2D stack as:
1. **Fallback** when no Plus plan / no credits — edge-tts + SVG still works offline.
2. **Live/realtime** surface — the audition engine's instant preview doesn't
   wait for video-gen queue; SVG reacts in-browser while Fish renders async.
3. **Theory-lab visualization** — casey_player.py + blendshapes are analysis
   tools, not production assets; Fish can't replay our extracted MediaPipe data.
Recommendation: Fish becomes the **showcase/production path** (`/mp4`, `/watch`,
Shorts); 2D stack stays for **dev-loop + analysis**. Don't delete it.
