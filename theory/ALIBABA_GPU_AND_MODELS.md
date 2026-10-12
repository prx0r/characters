# Alibaba stack — models, GPU, billing (prx0r/characters)

Updated Oct 2026. Key lives in `audition/.env` (`DASHSCOPE_API_KEY`), never committed.

## API endpoints

| Use | Base URL |
|-----|----------|
| OpenAI-compatible (intl) | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| Native DashScope | `https://dashscope-intl.aliyuncs.com/api/v1` |
| Console (Singapore) | https://modelstudio.console.alibabacloud.com/ap-southeast-1 |

International keys do **not** work on `dashscope.aliyuncs.com` (Beijing).

## What this key can call today (verified)

| Model | Status | Use |
|-------|--------|-----|
| `qwen-flash-character` | OK free 1M | Theory tags, bulk persona |
| `qwen-plus-character` | OK free 1M | Quality theory tags |
| `qwen-audio-3.1-asr-flash` | OK free 1M | Word-timestamped ASR (via public URL) |
| `qwen-audio-3.0-asr-flash` | OK free 36K | ASR |
| `qwen-audio-3.0-tts-flash` / `plus` | OK free 10K | TTS |
| `qwen3.7-text-embedding` | OK free 1M | Embeddings |
| `qwen-mt-image-2.0` | OK free 100 | Image translation only |
| `qwen3.8-omni-flash` | **403 Unpurchased** | Joint AV analysis — needs real-name + Free Quota Only off |
| `qwen3.8-flash` / VL models | **403 Unpurchased** | Same |

403 cause: unverified account has Free Quota Only force-enabled → models without free quota hard-block.
Fix: Account Center → identity verification → disable Free Quota Only for target models (or PAYG after verify).

## Free-quota prices (when PAYG unlocks)

| Model | In / 1M | Out / 1M |
|-------|---------|----------|
| `qwen3.8-omni-flash` | $0.15 | $0.47 |
| `qwen3.8-flash` | $0.15 | $0.47 |
| `qwen3.5-omni-flash` | $0.40 (+$3 audio) | $2.20 |
| Wan 2.2 animate-move | $0.12/s std · $0.18/s pro | 50s free advertised |
| HappyOyster acting | $0.0308/s 480p | invite only |

Omni analysis of one 60s short ≈ **$0.01–0.03**.

## Extraction pipeline (free tier, working)

```bash
cd /home/box/repos/characters

# 1. MediaPipe body/face dials → granular + performance.v1
.venv/bin/python theory/extract_performance.py <video.mp4> --id <stem> --skip-omni

# 2. Upload audio → litterbox → word ASR → align body×speech → anger report
.venv/bin/python theory/align_speech_body.py <video.mp4> <stem>

# 3. Theory tags from archive transcript (character models)
.venv/bin/python theory/tag_comedy_theory.py

# 4. Rebuild performance.v1 from existing granular windows
.venv/bin/python theory/build_perf_from_mediapipe.py
```

ASR path: mp3 32kbps → litterbox.catbox.moe 24h URL → `qwen-audio-3.1-asr-flash` multimodal generation API with `input_audio.data = URL`.
Base64 body too large (Aliyun fetches URL, not inline).

Outputs land in `theory/killtony-minutes/`:
- `*.granular.json` — 15Hz face blendshapes + body dials
- `*.performance.v1.json` — Stage Lab timeline events
- `*.theory.json` — GTVH ops, emotion, anger hypotheses
- `*.anger_speech_report.md` — speech×body anger windows + word timings
- `ari_ANGER_body_voice_model.md` — rigging cross-ref to Ralph + modulators.json

## GPU (cheapest for batch work)

Do **not** rent 24/7 ECS. Use serverless / spot for LivePortrait batches:

| Option | GPU | $/hr | Notes |
|--------|-----|------|-------|
| ACS best-effort (intl) | T4 | **0.18** | Scale to zero |
| ACS best-effort (intl) | A10 | **0.57** | LivePortrait-class |
| ECS spot AP-Southeast | A10G | **0.26** | Interruptible |
| PAI EAS spot | L20 | ~0.40 | 20% of list |
| Function Compute GPU | T4-class | ~0.26 for 1h use | True per-second |

30s LivePortrait on T4 spot ≈ **$0.01–0.05**.

Console: https://ecs.console.aliyun.com/ · PAI: https://pai.console.aliyun.com/

## Billing status (this account)

- PAYG billing account exists (Google Pay bound, settlement threshold $100)
- Real-name verification **not complete** → omni/VL still 403
- No subscription purchased (correct for current usage)
- Identity verify: https://account.alibabacloud.com/realname/identity_verification.htm
- Top-up: https://usercenter2-intl.aliyun.com/finance/online-recharge

## Rig mapping (anger → Ralph)

| Dial / theory | Ralph expression | modulators.json |
|---------------|------------------|-----------------|
| brow furrow + mouth open | `annoyed` | angry.emphasis_delta |
| lean spike + sharp arm | `lean_forward` / small_shrug | angry.gestures: sharp |
| hold after punch | Stage Lab hold 1200ms | angry.pause_mult |
| mock indignation | `annoyed` + `suit_adjust` | anger_flavor: mock |

See `theory/killtony-minutes/ari_ANGER_body_voice_model.md`.


## Gemini (working multimodal alternative)

Key in `audition/.env` `GEMINI_API_KEY`. Model: `gemini-3.8-flash`.
Video + audio + frames. ~$0.10/M tokens (input), ~$0.40/M output. Free tier generous for experiments.

```bash
.venv/bin/python theory/gemini_performance.py <video.mp4> <stem>
```

Outputs: `*.gemini.json` (full granular analysis) + `*.performance.v1.json`.
~75s for a 60s clip, ~8.5k tokens (5.5k video + 0.6k text + 0.4k thinking).
Inline base64 under ~15MB (compress_clip handles this).

Schema: segments with body/face/vocal/comedy_theory + gesture_library + anger_analysis.
Replaces blocked qwen3.8-omni-flash for AV performance analysis.
