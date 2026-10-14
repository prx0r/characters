"""Fish Audio TTS: s2.1-pro-free default, drama-3 behind FISH_PAID=1.

Env: FISH_API_KEY in audition/.env. AUDITION_TTS=fish to opt in.
Directions ride inside the text (Drama 3 / s2 bracket syntax) — no schema change.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
AUDIO_DIR = HERE / "audio"
API = "https://api.fish.audio/v1/tts"

SIGNATURE_DIRECTIONS = {
    "angry": "angry, sharp, blaming named individuals",
    "condescending": "condescending, slow and patient, explaining as if to children",
    "drunk_on_power": "expansive, drunk on power, saying the quiet part proudly",
    "exhausted": "exhausted, barely finding the energy to finish",
    "paranoid": "paranoid, speaking too fast, glancing at the doors",
    "sad": "sad, deflated, voice trailing off",
    "manic": "manic, fast, eyes wide, unstoppable momentum",
    "subservient": "subservient, eager to please, voice slightly too high",
    "smug": "smug, savoring every word, faint smirk in the voice",
    "panicked": "panicked, words tumbling out, tripping over consonants",
}

PAIRED_TAGS = ("<whisper>", "<emphasis>", "<soft>", "<fast>", "<slow>",
               "<stress>", "<forceful>")


def _ffprobe_ms(path: Path) -> int | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", str(path)],
                           capture_output=True, text=True, timeout=15)
        return int(float(r.stdout.strip()) * 1000)
    except Exception:
        return None


def estimate_ms(text: str, pauses_ms: int = 0) -> int:
    return int(len(text.split()) / 2.6 * 1000) + pauses_ms


def get_key() -> str | None:
    return os.getenv("FISH_API_KEY") or None


def model_for(paid: bool = False) -> str:
    if paid and os.getenv("FISH_PAID", "") == "1":
        return "drama-3"
    return "s2.1-pro-free"


def directions_for_modulator(modulator: str, mod: dict | None = None) -> str:
    """Modulator JSON -> Drama 3 plain-language direction string."""
    if mod is None:
        try:
            mod = json.loads((HERE / "modulators.json").read_text()).get(modulator) or {}
        except Exception:
            mod = {}
    if modulator in SIGNATURE_DIRECTIONS:
        base = SIGNATURE_DIRECTIONS[modulator]
    else:
        mod = mod or {}
        perf = (mod.get("performative") or {})
        emo = (mod.get("emotional") or {})
        pace = perf.get("pace_delta", 0)
        arousal = emo.get("arousal", 0.5)
        parts = []
        if pace >= 0.1 or arousal >= 0.75:
            parts.append("fast, high energy")
        elif pace <= -0.1 or arousal <= 0.3:
            parts.append("slow, low energy")
        else:
            parts.append("measured")
        gestures = perf.get("gestures", "")
        if gestures and gestures not in ("minimal", ""):
            parts.append(f"{gestures} physically")
        if emo.get("defensiveness", 0) >= 0.7:
            parts.append("defensive edge")
        base = ", ".join(parts)
    return f"[{base}]"


def wrap_text(text: str, modulator: str, mod: dict | None = None,
              direction: bool = True) -> str:
    if not direction:
        return text
    return directions_for_modulator(modulator, mod) + " " + text


def _request(text: str, reference_id: str | None, model: str,
             fmt: str = "mp3", timeout: int = 120) -> bytes:
    key = get_key()
    if not key:
        raise RuntimeError("FISH_API_KEY missing (audition/.env)")
    body: dict = {"text": text, "format": fmt}
    if reference_id:
        body["reference_id"] = reference_id
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "model": model})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def synthesize_fish(audition_id: str, text: str, voice: str | None = None,
                    modulator: str = "", mod: dict | None = None,
                    paid: bool = False, direction: bool = True) -> dict:
    model = model_for(paid=paid)
    directed = wrap_text(text, modulator or "neutral", mod, direction=direction)
    ref = voice or os.getenv("FISH_VOICE_ID") or None
    out = AUDIO_DIR / f"{audition_id}-fish.mp3"
    if out.exists():
        out.unlink()
    try:
        data = _request(directed, ref, model)
    except Exception as e:
        raise RuntimeError(f"fish tts ({model}) failed: {str(e)[:200]}")
    if len(data) < 2000:
        raise RuntimeError(f"fish tts returned too little audio ({len(data)}B)")
    out.write_bytes(data)
    dur = _ffprobe_ms(out) or estimate_ms(directed)
    return {"path": str(out), "duration_ms": dur,
            "provenance": f"fish-tts:{model}" + ("+direction" if direction else "")
                          + ("+ffprobe" if _ffprobe_ms(out) else "+estimated"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "model": model, "directed": direction}


def list_public_voices_sample() -> list[dict]:
    """Drama 3 cast from docs — safe defaults, no key needed to remember."""
    return [
        {"name": "Adrian", "language": "EN-US", "id": "bf322df2096a46f18c579d0baa36f41d"},
        {"name": "Delia", "language": "EN-US", "id": "c70cfb98867a4bfb9ae20d2401257b92"},
        {"name": "Sheila", "language": "EN-US", "id": "f3a2b90078d54a65af4b95f63bc7798e"},
    ]
