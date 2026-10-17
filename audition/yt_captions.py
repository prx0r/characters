"""YouTube captions via yt-dlp — first choice for YouTube sources.

Word-level timing from json3 (no ASR cost, no rate limits). Falls back to
None so the caller can use cf_asr (for non-YouTube audio like BBC MP3s).

Usage:
  python3 yt_captions.py --test VIDEO_ID     # print first words + method
"""
from __future__ import annotations
import glob, json, os, shlex, subprocess, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
COOKIES = (os.path.join(_HERE, ".env.cookies")
           if os.path.exists(os.path.join(_HERE, ".env.cookies"))
           else "/home/box/Downloads/cookies.txt")


def _run(cmd: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ytdlp_subs(video_id: str, tmpdir: str, manual: bool) -> list[str]:
    flag = "--write-subs" if manual else "--write-auto-subs"
    cmd = ["yt-dlp", "--skip-download", flag, "--sub-langs", "en.*",
           "--sub-format", "json3", "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
           f"https://youtube.com/watch?v={video_id}", "--no-playlist"]
    if os.path.exists(COOKIES):
        cmd += ["--cookies", COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    _run(cmd)
    return sorted(glob.glob(os.path.join(tmpdir, f"{video_id}*.json3")))


def _pick(files: list[str], video_id: str) -> str | None:
    if not files:
        return None
    for suffix in (f"{video_id}.en.json3", f"{video_id}.en-orig.json3"):
        for f in files:
            if f.endswith(suffix):
                return f
    return files[0]


def parse_json3(path: str) -> dict:
    d = json.load(open(path, encoding="utf-8"))
    words = []
    for e in d.get("events", []):
        base = e.get("tStartMs", 0)
        dur = e.get("dDurationMs", 0)
        seglist = []
        for s in e.get("segs") or []:
            txt = (s.get("utf8") or "").strip()
            if txt:
                seglist.append((txt, base + s.get("tOffsetMs", 0)))
        for i, (txt, start_ms) in enumerate(seglist):
            end_ms = seglist[i + 1][1] if i + 1 < len(seglist) else base + dur
            if words and words[-1]["text"] == txt and start_ms / 1000 < words[-1]["end"]:
                continue  # rolling-window duplicate
            words.append({"text": txt, "start": round(start_ms / 1000, 2),
                          "end": round(end_ms / 1000, 2), "type": "word"})
    transcript = " ".join(w["text"] for w in words)
    return {"words": words, "transcript": transcript}


def fetch_captions(video_id: str, tmpdir: str) -> dict | None:
    """Return {'words', 'transcript', 'method'} or None if no captions exist."""
    manual_files = _ytdlp_subs(video_id, tmpdir, manual=True)
    f = _pick(manual_files, video_id)
    method = "youtube-manual-captions"
    if not f:
        auto_files = _ytdlp_subs(video_id, tmpdir, manual=False)
        f = _pick(auto_files, video_id)
        method = "youtube-auto-captions"
    if not f:
        return None
    out = parse_json3(f)
    if not out["words"]:
        return None
    out["method"] = method
    return out


if __name__ == "__main__":
    if "--test" in sys.argv:
        vid = sys.argv[sys.argv.index("--test") + 1]
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cap = fetch_captions(vid, td)
        if not cap:
            print("no captions")
        else:
            print(f"method: {cap['method']}")
            print(f"words: {len(cap['words'])}")
            print(f"first 12: {[w['text'] for w in cap['words'][:12]]}")
    else:
        print(__doc__)
