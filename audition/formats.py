"""Format factory — every show is a subgraph shape + scoring rule.

Standup = 1 character, 1 set (exists: audition -> watch -> mp4).
React = N characters watch one set, timestamped reaction lines.
Podcast = clique roundtable on one topic, multi-voice audio.
Shanty = world anthem in verse, chanted over a click-track bed.
Surrounded = edges pointed at the human (web prototype: text first).
Roast = star graph, all edges at one target (prompts + duels, no new tech).

Shared builders: speak_line (TTS per character voice), concat_mp3,
transcript records. All artifacts land in audition/audio (gitignored).
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).parent
AUDIO = HERE / "audio"

FORMATS = {
    "standup": {"shape": "solo", "needs": ["character_id", "scenario"],
                "scores": ["pog", "rating", "retention"]},
    "react": {"shape": "edges-at-target", "needs": ["reactor_ids", "target_audition_id"],
              "scores": ["got_me", "quote_back"]},
    "podcast": {"shape": "clique", "needs": ["topic", "cast_ids"],
                "scores": ["completion", "replay", "quote_back"]},
    "shanty": {"shape": "unison", "needs": ["world_id"],
               "scores": ["replay", "sing_back"]},
    "surrounded": {"shape": "edges-at-human", "needs": ["human_prompt", "mob_ids"],
                   "scores": ["laugh", "concession"]},
    "roast": {"shape": "star", "needs": ["target_id", "roaster_ids"],
              "scores": ["got_me", "groan"]},
}

VOICES = {"no_nose_nolan": "en-US-GuyNeural",
          "reptilian_ralph_middle_management": "en-US-ChristopherNeural",
          "rudy_dulce_hvac": "en-US-GuyNeural",
          "zeus_sky_sovereign": "en-US-ChristopherNeural",
          "hera_queen_ledger": "en-US-AriaNeural"}


def speak_line(character_id: str, text: str, tag: str) -> dict:
    """One TTS line in the character's voice. Returns {path, duration_ms}."""
    import tts_provider as _tts
    voice = VOICES.get(character_id, "en-US-GuyNeural")
    return _tts.synthesize(f"{tag}", text, voice)


def concat_mp3(parts: list[str], out: Path) -> dict:
    lst = out.parent / (out.stem + "_list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(out)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("concat failed: " + r.stderr[-300:])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
                       capture_output=True, text=True, timeout=30)
    try:
        dur = int(float(d.stdout.strip()) * 1000)
    except Exception:
        dur = 0
    import hashlib
    return {"path": str(out), "duration_ms": dur,
            "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}


def click_bed(out: Path, duration_ms: int, bpm: int = 100) -> Path:
    """Sea-shanty percussion bed: synthesized kick+tick, no samples needed."""
    beat = 60.0 / bpm
    dur = duration_ms / 1000
    filt = (f"sine=frequency=90:duration={dur}:sample_rate=44100,"
            f"volume=0.25,apad[low];sine=frequency=1200:duration={dur}:"
            f"sample_rate=44100,volume=0.08,apad[hi];"
            f"[low][hi]amix=inputs=2:duration=first")
    r = subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", filt,
                        "-t", f"{dur:.2f}", "-c:a", "mp3", str(out)],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("bed failed: " + r.stderr[-300:])
    return out


def mix_voice_bed(voice: Path, bed: Path, out: Path) -> Path:
    r = subprocess.run(["ffmpeg", "-y", "-i", str(voice), "-i", str(bed),
                        "-filter_complex", "[0:a]volume=1.0[v];[1:a]volume=0.35[b];[v][b]amix=inputs=2:duration=first",
                        "-c:a", "mp3", str(out)], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("mix failed: " + r.stderr[-300:])
    return out


def save_record(kind: str, record: dict) -> Path:
    p = AUDIO / f"{kind}_{int(time.time())}.json"
    p.write_text(json.dumps(record, indent=1))
    return p
