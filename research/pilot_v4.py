"""v4-turbo pilots: tale excerpt -> tagged segments -> Eleven v4 -> MP3.

Maximizes v4 per docs/refs/eleven-v4: audio tags (never SSML), ellipses for
pauses, explicit dialogue tags, per-role stability/speed, previous/next_text
continuity, narrator bedtime baseline. Reuses easy/audio/eleven.py (their
lane) — this script only directs.
Usage: ELEVENLABS_API_KEY=... python3 research/pilot_v4.py (runs 3 pilots)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
EASY = Path("/root/easy/audio")
sys.path.insert(0, str(EASY))
sys.path.insert(0, str(ROOT / "audition"))
OUT = Path("/tmp/opencode/pilots")
OUT.mkdir(parents=True, exist_ok=True)

NARRATOR = {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "stability": 0.65,
            "similarity": 0.8, "speed": 0.85}  # George, warm storyteller
PILOTS = [
    {"resident": "anansi-spider", "collection": "jamaica-anansi",
     "voice_id": "N2lVS1w4EtoT3dr4eOWO", "stability": 0.45, "speed": 1.0,
     "chars": 1300},   # Callum trickster, quicker
    {"resident": "gnorma-the-hoa-gnome", "collection": "household-spirits",
     "voice_id": "XrExE9yKIg1WjnnlVkGX", "stability": 0.6, "speed": 0.9,
     "chars": 1300},   # Matilda stern
    {"resident": "yuki-snow-narrator", "collection": "kwaidan-part-2",
     "voice_id": "pFZP5JQG7iQjIQuC4Bku", "stability": 0.7, "speed": 0.8,
     "chars": 1300},   # Lily velvet, slow frost
]


def clean_excerpt(collection: str, chars: int) -> str:
    txt = Path(f"/root/easy/folk-and-fable/{collection}/script.txt").read_text()
    up = txt.upper()
    s = up.find("*** START OF")
    if s >= 0:
        nl = txt.find("\n", s)
        txt = txt[nl + 1:]
    e = up.find("*** END OF")
    if e >= 0:
        txt = txt[:e]
    lines = txt.splitlines()
    # drop Gutenberg metadata header (Title/Author/Release/Language/Credits/Produced-by/Updated)
    meta = re.compile(r"^(title|author|contributor|release date|language|original publication|other information|credits|produced by|updated|transcriber|illustrator|editor)\s*:", re.I)
    while lines and (not lines[0].strip() or meta.match(lines[0].strip()) or
                     lines[0].strip().lower().startswith("the project gutenberg") or
                     "gutenberg" in lines[0].lower() and len(lines[0]) < 120):
        lines.pop(0)
    # front matter (title pages, TOCs, prefaces, license leftovers) is short
    # lines; narrative prose runs long. Scan wide for the first long,
    # non-metadata line, keeping one heading line above it.
    skip_pat = re.compile(r"^(title|author|contributor|release date|language|original publication|other information|credits|produced by|updated|transcriber|illustrator|editor)\s*:", re.I)
    start = 0
    for i, ln in enumerate(lines[:400]):
        s = ln.strip()
        if len(s) > 140 and not skip_pat.match(s) and "gutenberg" not in s.lower():
            start = i
            break
    if start:
        head = start - 1 if start >= 1 and lines[start - 1].strip() else start
        lines = lines[head:]
    txt = "\n".join(lines)
    txt = re.sub(r"\[\d+\]", "", txt)  # footnote markers v4 would read aloud
    txt = re.sub(r"[ \t]+", " ", txt)
    return txt.strip()[:chars]


def segment(text: str) -> list[tuple[str, str]]:
    """Split into (role, line): quoted speech -> character, else narrator."""
    import eleven_tags as _tags
    parts = re.split(r'(".*?")', text, flags=re.S)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 2 and p.startswith('"'):
            line, _ = _tags.prepare(p.strip('"').strip(), "character speaks")
            out.append(("character", line))
        else:
            for sent in re.split(r"(?<=[.!?])\s+", p):
                if sent.strip():
                    out.append(("narrator", sent.strip()))
    return [(r, l) for r, l in out if l]


def synth(text: str, voice_id: str, stability: float, speed: float,
          prev: str, nxt: str, out: Path) -> int:
    import eleven as _el
    os.environ.setdefault("ELEVENLABS_API_KEY", "")
    cfg = {"voice_id": voice_id, "model": "eleven_v4",
           "stability": stability, "similarity": 0.8, "speed": speed}
    payload = {"text": text, "model_id": cfg["model"],
               "voice_settings": {"stability": stability, "similarity_bias": 0.8, "speed": speed},
               "previous_text": prev[-500:], "next_text": nxt[:500]}
    data = _el.post(voice_id, payload)
    out.write_bytes(data)
    return len(text)


def run_pilot(spec: dict) -> dict:
    import eleven as _el
    _ = _el.MODEL
    text = clean_excerpt(spec["collection"], spec["chars"])
    segs = segment(text)[:14]
    paths, billed, prev = [], 0, ""
    full = " ".join(l for _, l in segs)
    for i, (role, line) in enumerate(segs):
        nxt = " ".join(l for _, l in segs[i + 1:i + 3])
        if role == "character":
            v, st, sp = spec["voice_id"], spec["stability"], spec["speed"]
        else:
            v, st, sp = NARRATOR["voice_id"], NARRATOR["stability"], NARRATOR["speed"]
        p = OUT / f"{spec['resident']}_{i:02d}.mp3"
        billed += synth(line, v, st, sp, prev, nxt, p)
        paths.append(str(p))
        prev = line
        time.sleep(0.5)
    lst = OUT / f"{spec['resident']}_list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in paths))
    out = OUT / f"{spec['resident']}_pilot.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out)], capture_output=True, timeout=120)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
                       capture_output=True, text=True, timeout=30)
    return {"resident": spec["resident"], "segments": len(segs),
            "chars_billed": billed, "audio": str(out),
            "duration_s": round(float(d.stdout.strip()), 1)}


def main() -> None:
    rep = []
    for spec in PILOTS:
        try:
            r = run_pilot(spec)
            print(r["resident"], r["segments"], "segs,", r["duration_s"], "s,", r["chars_billed"], "chars")
        except SystemExit as e:
            print(spec["resident"], "STOP:", e)
            break
        except Exception as e:
            print(spec["resident"], "FAIL:", str(e)[:150])
            break
        rep.append(r)
    Path("/tmp/opencode/pilot_report.json").write_text(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
