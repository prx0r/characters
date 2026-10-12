"""Gemini video performance analysis — cheap multimodal replacement for blocked omni.

gemini-3.8-flash: video + audio + frames, ~$0.10/M tokens, free tier generous.
Inline base64 under ~20MB; longer clips use Files API (not implemented here).

Output matches the Omni-style granular schema used by extract_performance.py.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AUDITION = Path(__file__).parent.parent / "audition"
OUT = Path(__file__).parent / "killtony-minutes"
TMP = Path("/tmp/opencode/gemini_perf")

PROMPT = """You are a comedy performance analyst. This is a stand-up clip.
Return STRICT JSON only. Timestamps relative to video start (seconds).

{
  "speaker_guess": str,
  "overall": {
    "energy_arc": str,
    "dominant_emotion": str,
    "dominant_emotion_intensity": number,
    "stage_presence": str
  },
  "segments": [
    {
      "t0": number, "t1": number,
      "emotion": "neutral|angry|defiant|gleeful|manic|deadpan|embarrassed|mock_indignant|sarcastic",
      "emotion_intensity": number,
      "body": {
        "lean": "back|neutral|forward",
        "lean_amount": number,
        "head": "neutral|tilt_left|tilt_right|nod|shake|jut",
        "arms": "sides|open|crossed|mic_point|hand_to_face|gesture_out",
        "face": "neutral|annoyed|surprised|deadpan|smirk|grimace|wide_eyes|sneer|mock_horror",
        "brow": "neutral|raised|furrowed|one_raised|flat_angry",
        "micro_gesture": str
      },
      "comedy": {
        "beat_type": "setup|premise|escalation|punchline|tag|callback|closer|button",
        "gtvh_operators": [str],
        "status_move": "down|up|flat|reversal",
        "note": str
      },
      "vocal": {
        "energy": number,
        "pitch_shift": "flat|rise|fall|spike|drop",
        "pace": "slow|normal|fast|rapid_fire",
        "emphasis_words": [str],
        "note": str
      }
    }
  ],
  "gesture_library": [
    {"name": str, "t_guess": number, "duration_est_s": number,
     "body_params": {"lean": number, "head_deg": number, "arm_open": number, "brow": number},
     "emotion_tag": str}
  ],
  "anger_analysis": {
    "present": bool,
    "type": "hot_yelling|cold_flat|mock_indignant|controlled_seethe|fake_rage_for_joke|none",
    "body_signature": [str],
    "face_signature": [str],
    "vocal_signature": [str],
    "target": str,
    "release_or_withhold": str,
    "contrast_before_after": str
  }
}"""


def _key() -> str:
    for line in (AUDITION / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("no GEMINI_API_KEY in audition/.env")


def compress_clip(src: Path, max_mb: float = 15, seconds: int | None = None) -> Path:
    """H.264 480p under size cap for inline base64."""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"{src.stem}_gem.mp4"
    dur_args = ["-t", str(seconds)] if seconds else []
    cmd = ["ffmpeg", "-y", "-i", str(src), *dur_args,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
           "-vf", "scale=480:-2", "-c:a", "aac", "-b:a", "48k", str(out)]
    subprocess.run(cmd, capture_output=True, timeout=120)
    # shrink further if needed
    while out.exists() and out.stat().st_size > max_mb * 1024 * 1024:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(out), "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "32", "-vf", "scale=360:-2", "-c:a", "aac", "-b:a", "32k",
             str(out.with_suffix(".tmp.mp4"))],
            capture_output=True, timeout=120)
        out.with_suffix(".tmp.mp4").replace(out)
    return out


def analyze_video(video: Path, prompt: str = PROMPT, model: str = "gemini-3.8-flash") -> dict:
    key = _key()
    clip = compress_clip(video)
    print(f"  clip {clip.name} {clip.stat().st_size//1024}KB", flush=True)
    b64 = base64.b64encode(clip.read_bytes()).decode()
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "video/mp4", "data": b64}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.3,
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    text = d["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    parsed["_meta"] = {
        "model": model,
        "elapsed_s": round(time.time() - t0, 1),
        "clip_mb": round(clip.stat().st_size / 1024 / 1024, 2),
        "usage": d.get("usageMetadata", {}),
    }
    return parsed


def to_performance_v1(gem: dict, source_id: str) -> dict:
    events = []
    for seg in gem.get("segments") or []:
        t0 = float(seg.get("t0") or 0)
        body = seg.get("body") or {}
        comedy = seg.get("comedy") or {}
        vocal = seg.get("vocal") or {}
        events.append({"t": round(t0, 2), "kind": "expression",
                       "value": body.get("face", "neutral"),
                       "intensity": seg.get("emotion_intensity")})
        lean = body.get("lean") or "neutral"
        arm = body.get("arms") or "sides"
        gesture = "hold still"
        if lean == "forward":
            gesture = "lean in"
        elif arm in ("open", "gesture_out"):
            gesture = "small gesture"
        elif arm == "crossed":
            gesture = "hold still"
        events.append({"t": round(t0, 2), "kind": "gesture", "value": gesture})
        events.append({"t": round(t0, 2), "kind": "look", "value": "audience"})
        events.append({"t": round(t0, 2), "kind": "speak_start",
                       "value": {"emotion": seg.get("emotion"),
                                "energy": vocal.get("energy"),
                                "pitch_shift": vocal.get("pitch_shift"),
                                "pace": vocal.get("pace"),
                                "beat_type": comedy.get("beat_type")}})
        if comedy.get("beat_type") == "punchline":
            events.append({"t": round(t0, 2) + 0.05, "kind": "hold", "ms": 1200})
    events.sort(key=lambda e: (e["t"], e.get("kind") or ""))
    return {
        "version": "performance.v1",
        "source": source_id,
        "method": "gemini-3.8-flash_video",
        "events": events,
        "n_events": len(events),
        "meta": gem.get("_meta"),
    }


def main():
    video = Path(sys.argv[1])
    stem = sys.argv[2] if len(sys.argv) > 2 else video.stem
    OUT.mkdir(exist_ok=True)
    print(f"Gemini analyze {video.name} ...", flush=True)
    gem = analyze_video(video)
    print(f"  done in {gem['_meta']['elapsed_s']}s, "
          f"{len(gem.get('segments') or [])} segments")
    gp = OUT / f"{stem}.gemini.json"
    gp.write_text(json.dumps(gem, indent=2))
    print(f"wrote {gp.name}")
    perf = to_performance_v1(gem, stem)
    pp = OUT / f"{stem}.performance.v1.json"
    pp.write_text(json.dumps(perf, indent=2))
    print(f"wrote {pp.name} ({perf['n_events']} events)")
    ang = gem.get("anger_analysis") or {}
    if ang.get("present"):
        print(f"  anger: {ang.get('type')} — {ang.get('body_signature')}")


if __name__ == "__main__":
    main()
