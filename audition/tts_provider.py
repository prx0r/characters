"""TTS: edge-tts first, piper-local fallback, espeak last resort. Real audio only."""
from __future__ import annotations

import asyncio
import hashlib
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
AUDIO_DIR = HERE / "audio"
AUDIO_DIR.mkdir(exist_ok=True)
VOICE_MODEL = HERE / "voices" / "en_US-lessac-medium.onnx"

VOICES = {"no_nose_nolan": "en-US-GuyNeural",
          "reptilian_ralph_middle_management": "en-US-ChristopherNeural",
          "rudy_dulce_hvac": "en-US-GuyNeural"}


def _ffprobe_ms(path: Path) -> int | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                            str(path)], capture_output=True, text=True, timeout=15)
        return int(float(r.stdout.strip()) * 1000)
    except Exception:
        return None


def estimate_ms(text: str, pauses_ms: int) -> int:
    return int(len(text.split()) / 2.6 * 1000) + pauses_ms


async def _edge_save(text: str, voice: str, out: Path, rate: str = "+0%",
                     pitch: str = "+0Hz") -> None:
    import edge_tts
    last: Exception | None = None
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))
            return
        except Exception as e:  # retry (transient net)
            last = e
            await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"edge-tts failed: {last}")


def _piper_save(text: str, out_wav: Path) -> None:
    if not VOICE_MODEL.exists():
        raise RuntimeError("piper voice model missing")
    r = subprocess.run(["piper", "--model", str(VOICE_MODEL),
                        "--output_file", str(out_wav)],
                       input=text.encode(), capture_output=True, timeout=120)
    if r.returncode != 0 or not out_wav.exists() or out_wav.stat().st_size < 2000:
        raise RuntimeError(f"piper failed: {r.stderr.decode()[:200]}")


def _espeak_save(text: str, out_wav: Path) -> None:
    r = subprocess.run(["espeak", "-v", "en", "-s", "150", "-w", str(out_wav), text],
                       capture_output=True, timeout=120)
    if r.returncode != 0 or not out_wav.exists() or out_wav.stat().st_size < 2000:
        raise RuntimeError("espeak failed")


def synthesize_qwen(audition_id: str, text: str, voice: str,
                    model: str = "qwen-audio-3.0-tts-flash") -> dict:
    """Opt-in Qwen TTS via `bl speech synthesize`. Only when AUDITION_TTS=qwen.

    Voice IDs are model-specific (use `bl speech synthesize --list-voices --model X`).
    qwen-voice-design IDs do NOT work on audio-3.0-tts-plus — separate providers.
    """
    import os as _os
    import alibaba as _ali
    if not _ali.get_key():
        raise RuntimeError("DASHSCOPE_API_KEY missing (audition/.env)")
    out = AUDIO_DIR / f"{audition_id}-qwen.mp3"
    if out.exists():
        out.unlink()
    r = _ali._run_bl(_ali.tts_argv(model, text[:5000], voice, str(out)), timeout=120)
    if not r["ok"] or not out.exists() or out.stat().st_size < 2000:
        raise RuntimeError(f"qwen tts failed: {(r['err'] or r['out'])[:200]}")
    dur = _ffprobe_ms(out) or estimate_ms(text, 0)
    return {"path": str(out), "duration_ms": dur,
            "provenance": f"qwen-tts:{model}+ffprobe",
            "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}


def synthesize(audition_id: str, text: str, voice: str, rate: str = "+0%",
               pitch: str = "+0Hz") -> dict:
    """Tries edge-tts, then piper-local, then espeak. Raises if all fail (no fake audio)."""
    import os as _os
    if _os.getenv("AUDITION_TTS", "") == "qwen":
        qmodel = _os.getenv("AUDITION_TTS_MODEL", "qwen-audio-3.0-tts-flash")
        qvoice = _os.getenv("AUDITION_TTS_VOICE", voice)
        try:
            return synthesize_qwen(audition_id, text, qvoice, qmodel)
        except Exception as e:
            # fall through to edge-tts chain; record error below
            _qerr = str(e)[:200]
        else:
            _qerr = ""
    else:
        _qerr = ""
    errors = []
    if _qerr:
        errors.append(f"qwen: {_qerr}")
    # 1. edge-tts (best voices, needs Bing network)
    try:
        out = AUDIO_DIR / f"{audition_id}.mp3"
        if out.exists():
            out.unlink()
        asyncio.run(_edge_save(text, voice, out, rate=rate, pitch=pitch))
        if out.exists() and out.stat().st_size >= 2000:
            dur = _ffprobe_ms(out) or estimate_ms(text, 0)
            return {"path": str(out), "duration_ms": dur,
                    "provenance": ("edge-tts" + ("+ffprobe" if _ffprobe_ms(out) else "+estimated")
                                   + f"|rate={rate}|pitch={pitch}"),
                    "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    except Exception as e:
        errors.append(f"edge: {e}")
        if out.exists() and out.stat().st_size >= 2000:
            dur = _ffprobe_ms(out) or estimate_ms(text, 0)
            return {"path": str(out), "duration_ms": dur,
                    "provenance": "edge-tts" + ("+ffprobe" if _ffprobe_ms(out) else "+estimated"),
                    "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
        # 2. piper local neural voice (dedupe note: single edge handler above)
    try:
        out = AUDIO_DIR / f"{audition_id}.wav"
        if out.exists():
            out.unlink()
        _piper_save(text, out)
        dur = _ffprobe_ms(out) or estimate_ms(text, 0)
        return {"path": str(out), "duration_ms": dur, "provenance": "piper-local",
                "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    except Exception as e:
        errors.append(f"piper: {e}")
    # 3. espeak robotic fallback (still real speech)
    try:
        out = AUDIO_DIR / f"{audition_id}.wav"
        if out.exists():
            out.unlink()
        _espeak_save(text, out)
        dur = _ffprobe_ms(out) or estimate_ms(text, 0)
        return {"path": str(out), "duration_ms": dur, "provenance": "espeak-fallback",
                "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    except Exception as e:
        errors.append(f"espeak: {e}")
    raise RuntimeError("all TTS providers failed: " + " | ".join(errors)[:400])
