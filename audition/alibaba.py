"""Alibaba Model Studio providers for characters audition engine.

All IDs verified against public catalog via `bl model search` (Oct 2026).
Free quotas below are ADVERTISED Singapore new-account quotas from docs,
not confirmed on this account (needs console login: `bl auth login --console`).

Rules:
- Key comes ONLY from audition/.env DASHSCOPE_API_KEY (never hardcoded, never logged).
- Text/omni/TTS/image default to cheapest free-tier picks.
- Video/animate/HappyOyster NEVER auto-run: they bill per second and can
  draw balance once free quota is gone. Require ALLOW_BILLABLE=1 + explicit call.
- Enable Free Quota Only in console first (off by default).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).parent

# role -> ordered picks (cheapest first). model: (bl_command, notes)
MODELS: dict[str, list[dict]] = {
    "roleplay": [
        {"model": "qwen-flash-character", "via": "bl text chat",
         "cost": "~0.25/1.5 per 1M in/out", "free": "1M advertised",
         "use": "bulk character improv, 8k ctx, cheapest persistent persona"},
        {"model": "qwen-plus-character", "via": "bl text chat",
         "cost": "~0.8/2 per 1M in/out", "free": "1M advertised",
         "use": "quality roleplay, 32k ctx, second pick / A/B vs flash"},
    ],
    "text": [
        {"model": "qwen3.8-flash", "via": "bl text chat",
         "cost": "flash tier", "free": "1M advertised",
         "use": "cheap gesture tagging, scene analysis, bulk"},
        {"model": "qwen3.8-max", "via": "bl text chat",
         "cost": "max tier", "free": "check console",
         "use": "quality writing fallback (default bl model)"},
    ],
    "omni": [
        {"model": "qwen3.8-omni-flash", "via": "bl omni",
         "cost": "omni tokens (audio+vision priced higher)", "free": "1M advertised",
         "use": "JOINT audiovisual performance analysis (video+audio together). "
                "Ordinary VL ignores audio — use this for acting critique."},
        {"model": "qwen3-omni-flash", "via": "bl omni",
         "cost": "1.8 text-in / 15.8 audio-in / 3.3 vision-in per 1M", "free": "check console",
         "use": "fallback omni, 64k ctx"},
        {"model": "qwen3.8-omni-flash-realtime", "via": "bl omni (realtime)",
         "cost": "realtime rates", "free": "1M advertised",
         "use": "live AV conversation with animated character (Interactive Lab)"},
    ],
    "tts": [
        {"model": "qwen-audio-3.0-tts-flash", "via": "bl speech synthesize",
         "cost": "~0.15/10k chars", "free": "check console",
         "use": "cheapest TTS for bulk minutes"},
        {"model": "qwen-audio-3.0-tts-plus", "via": "bl speech synthesize",
         "cost": "~0.20/10k chars", "free": "10k chars advertised",
         "use": "quality TTS for winners (P0 voice comparison)"},
        {"model": "cosyvoice-v3-flash", "via": "bl speech synthesize",
         "cost": "flash tier", "free": "check console",
         "use": "clone/design voice IDs (v3.5-flash needs voice ID)"},
    ],
    "voice_design": [
        {"model": "qwen-voice-enrollment", "via": "console/API (voice IDs for cosyvoice-v3.5-flash)",
         "cost": "~0.20/new voice", "free": "10 designs advertised",
         "use": "create persistent fictional voices from descriptions. "
                "NOT interchangeable with audio-3.0-tts-plus voices — separate providers."},
    ],
    "image": [
        {"model": "qwen-image-2.0", "via": "bl image generate",
         "cost": "~0.035/image", "free": "100 advertised",
         "use": "consistent designs, feature edits (default image workhorse)"},
        {"model": "qwen-image-3.0", "via": "bl image generate",
         "cost": "higher", "free": "10 advertised",
         "use": "concept art, expression sheets (default bl image model)"},
        {"model": "wan2.7-image", "via": "API (groups/storyboards)",
         "cost": "check console", "free": "50 advertised",
         "use": "coherent character/storyboard groups"},
    ],
    "video": [
        {"model": "wan3.0-video", "via": "bl video generate",
         "cost": "per-sec OUT; ref mode bills IN+OUT", "free": "30s advertised (in+out combined)",
         "use": "hero sketches only. BILLABLE — see below.", "billable": True},
        {"model": "wan2.7-t2v", "via": "bl video generate",
         "cost": "per-sec", "free": "check console",
         "use": "text-to-video fallback", "billable": True},
        {"model": "wan2.7-r2v", "via": "bl video ref",
         "cost": "per-sec", "free": "check console",
         "use": "multi-subject reference video", "billable": True},
    ],
    "animate": [
        {"model": "wan2.2-animate-move", "via": "API (move transfer)",
         "cost": "$0.12/s std, $0.18/s pro", "free": "50s advertised",
         "use": "reference acting video -> character image, <=30s. "
                "P1 Capture Lab comparison vs MediaPipe->Rive.", "billable": True},
        {"model": "wan2.2-animate-mix", "via": "API (mix/swap)",
         "cost": "$0.18/s std equiv", "free": "50s advertised",
         "use": "put original character into acted video", "billable": True},
    ],
    "embed": [
        {"model": "tongyi-embedding-vision-flash", "via": "API embeddings",
         "cost": "cheap", "free": "1M advertised",
         "use": "searchable acting vocabulary (skeptical glance, restrained frustration...)"},
    ],
    "asr": [
        {"model": "qwen-asr-flash (via bl speech recognize)", "via": "bl speech recognize",
         "cost": "cheap", "free": "check console",
         "use": "timed transcripts, word-level timing for puppet beats"},
    ],
    "happyoyster": [
        {"model": "happyoyster-1.0-adventure", "via": "API (in catalog)",
         "cost": "per-sec", "free": "none advertised",
         "use": "interactive world baseline", "billable": True},
        {"model": "happyoyster-1.0-acting", "via": "console/API (NOT in public catalog; invite preview)",
         "cost": "$0.0308/s 480p", "free": "none",
         "use": "live character speak/react, 3min identity hold. Benchmark vs Rive; do not assume script fidelity.",
         "billable": True},
        {"model": "happyoyster-1.0-directing", "via": "console/API (NOT in public catalog)",
         "cost": "$0.0539/s 480p", "free": "none",
         "use": "direct scene/camera mid-stream. Most expensive; defer.", "billable": True},
    ],
}

# cheapest default per role (free-tier first)
DEFAULTS = {
    "roleplay": "qwen-flash-character",
    "text": "qwen3.8-flash",
    "omni": "qwen3.8-omni-flash",
    "tts": "qwen-audio-3.0-tts-flash",
    "image": "qwen-image-2.0",
    "embed": "tongyi-embedding-vision-flash",
    "asr": "qwen-asr-flash",
}


def get_key() -> str:
    """DASHSCOPE_API_KEY from env or audition/.env. Empty = not configured."""
    k = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if k:
        return k
    try:
        for line in (HERE / ".env").read_text().splitlines():
            if line.startswith("DASHSCOPE_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except Exception:
        pass
    return ""


def billable_allowed() -> bool:
    return os.getenv("ALLOW_BILLABLE", "") == "1"


def _run_bl(argv: list[str], timeout: int = 120, dry: bool = False) -> dict:
    """Run a bl command. dry=True appends --dry-run (no spend, validates flags)."""
    cmd = ["bl", *argv]
    if dry and "--dry-run" not in argv:
        cmd.append("--dry-run")
    env = dict(os.environ, NO_COLOR="1")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(HERE))
        return {"ok": r.returncode == 0, "code": r.returncode,
                "out": (r.stdout or "")[:4000], "err": (r.stderr or "")[:1000]}
    except Exception as e:
        return {"ok": False, "code": -1, "out": "", "err": str(e)[:200]}


def chat_argv(model: str, message: str, system: str = "") -> list[str]:
    a = ["text", "chat", "--model", model, "--message", message]
    if system:
        a += ["--system", system]
    return a


def omni_argv(model: str, message: str, video: str = "", audio: str = "",
              image: str = "", text_only: bool = True) -> list[str]:
    a = ["omni", "--model", model, "--message", message]
    if video:
        a += ["--video", video]
    if audio:
        a += ["--audio", audio]
    if image:
        a += ["--image", image]
    if text_only:
        a += ["--text-only"]
    return a


def tts_argv(model: str, text: str, voice: str, out: str) -> list[str]:
    return ["speech", "synthesize", "--model", model, "--text", text,
            "--voice", voice, "--out", out]


def image_argv(model: str, prompt: str, out_dir: str, n: int = 1,
               size: str = "1:1") -> list[str]:
    return ["image", "generate", "--model", model, "--prompt", prompt,
            "--n", str(n), "--size", size, "--out-dir", out_dir]


def video_argv(model: str, prompt: str, out: str, duration: int = 5,
               image: str = "") -> list[str]:
    a = ["video", "generate", "--model", model, "--prompt", prompt,
         "--duration", str(duration), "--download", out]
    if image:
        a += ["--image", image]
    return a


def guard_billable(kind: str) -> dict | None:
    """Returns error dict if a billable op is attempted without ALLOW_BILLABLE=1."""
    if billable_allowed():
        return None
    return {"ok": False, "code": 7, "out": "",
            "err": f"refused {kind}: set ALLOW_BILLABLE=1 after enabling Free Quota Only. "
                   f"Video/animate/HappyOyster bill per second once free quota is gone."}
