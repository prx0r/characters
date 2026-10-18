#!/usr/bin/env python3
"""Harvest full-special transcripts from YouTube (captions) -> R2.

Stores comedians/<slug>/specials/<special>.json with timestamped words,
mirroring the clip schema.

Usage: python3 specials_harvest.py [--only comedian-substr]
"""
from __future__ import annotations
import argparse, json, os, shlex, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shorts_harvest import s3, slugify, R2_BUCKET  # noqa: E402
import yt_captions  # noqa: E402

SPECIALS = [
    ("Stewart Lee", "stand-up-comedian-2005-live", "VxN8PhKzZgY"),
    ("Stewart Lee", "90s-comedian-2006-live", "PClKMRcugVA"),
    ("Stewart Lee", "carpet-remnant-world-2012-live", "7oyfkqD4UP8"),
    ("Stewart Lee", "live-at-the-lowry", "eYct1AAsr7Y"),
    ("Stewart Lee", "basic-lee-2024", "CYNvljiaeuA"),
    ("Stewart Lee", "comedy-vehicle-s1e2-television", "iUX03wbrpjE"),
    ("Stewart Lee", "comedy-vehicle-s1e4-financial-crisis", "zpbAnk8ka5g"),
    ("Stewart Lee", "comedy-vehicle-s1e5-comedy", "h-Ewpg90D0g"),
    ("Stewart Lee", "comedy-vehicle-s1e6-religion", "-SQIfEwAkcw"),
    ("Stewart Lee", "comedy-vehicle-dead-mouse", "QXiiq1EUr7Q"),
    ("Stewart Lee", "comedy-vehicle-jeremy-corbyn", "2b9eRI-WRgU"),
    ("Simon Amstell", "do-nothing-live", "K4mH6E0hMbI"),
    ("Daniel Sloss", "socio-2021", "4ppYdCzLEJQ"),
]


def meta(vid: str) -> dict:
    cmd = ["yt-dlp", "--skip-download", "--no-warnings",
           "--print", "%(title)s|||%(duration)s|||%(view_count)s|||%(channel)s",
           f"https://www.youtube.com/watch?v={vid}"]
    if Path(yt_captions.COOKIES).exists():
        cmd += ["--cookies", yt_captions.COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        parts = (r.stdout or "").strip().splitlines()[0].split("|||")
        return {"title": parts[0], "duration_s": int(float(parts[1])) if parts[1] not in ("NA", "None", "") else None,
                "views": int(parts[2]) if parts[2] not in ("NA", "None", "") else 0,
                "channel": parts[3] if len(parts) > 3 else ""}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    for comedian, special, vid in SPECIALS:
        if args.only and args.only.lower() not in comedian.lower():
            continue
        cslug, sslug = slugify(comedian), slugify(special)
        key = f"comedians/{cslug}/specials/{sslug}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            print(f"exists: {key}", flush=True)
            continue
        except Exception:
            pass
        with tempfile.TemporaryDirectory() as td:
            try:
                cap = yt_captions.fetch_captions(vid, td)
            except Exception as e:
                cap = None
                print(f"  captions error {vid}: {e}", flush=True)
        if not cap:
            print(f"NO CAPTIONS: {vid} ({special})", flush=True)
            continue
        m = meta(vid)
        data = {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                "comedian": comedian, "special": special,
                "title": m.get("title") or special, "channel": m.get("channel") or "",
                "views": m.get("views") or 0, "duration_s": m.get("duration_s"),
                "source": "youtube-full", "n_words": len(cap["words"]),
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "words": cap["words"], "transcript": cap["transcript"],
                "transcript_method": cap["method"]}
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=json.dumps(data).encode(),
                      ContentType="application/json")
        print(f"stored: {key} ({len(cap['words'])} words, {cap['method']})", flush=True)


if __name__ == "__main__":
    main()
