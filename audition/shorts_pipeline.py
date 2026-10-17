"""Shorts Pipeline: download high-view shorts → transcript → R2 → delete local.

From funnygraph YouTube data: 187 shorts with >100K views.
Each short: comedian, title, views, duration, videoId.
After pipeline: word-level timestamps + audio in R2.

Usage:
  python3 shorts_pipeline.py --top 50          # download top 50 by views
  python3 shorts_pipeline.py --comedian "Ali Wong"  # specific comedian
  python3 shorts_pipeline.py --video hlXlMQc_22o    # single video
"""
from __future__ import annotations
import boto3, json, subprocess, sys, tempfile, os, re, time
from pathlib import Path

R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"
COOKIES = "/home/box/Downloads/cookies.txt"
FUNNYGRAPH = Path("/tmp/funnygraph")

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET, region_name="auto")


def load_shorts(min_views: int = 100000, max_duration: int = 60) -> list[dict]:
    """Load high-view shorts from funnygraph YouTube data."""
    yt_dir = FUNNYGRAPH / "data" / "youtube"
    shorts = []

    for f in sorted(yt_dir.glob("*.json")):
        d = json.loads(f.read_text())
        comedian = d.get("name", "?")
        for r in d.get("rows", []):
            dur = r.get("duration_s", 0)
            views = r.get("views", 0)
            if dur and dur < max_duration and views >= min_views:
                shorts.append({
                    "video_id": r["videoId"],
                    "title": r.get("title", ""),
                    "comedian": comedian,
                    "views": views,
                    "likes": r.get("likes", 0),
                    "duration_s": dur,
                    "channel": r.get("channel", ""),
                    "url": f"https://youtube.com/watch?v={r['videoId']}",
                })

    shorts.sort(key=lambda x: -x["views"])
    return shorts


def process_short(short: dict) -> dict:
    """Download one short → transcribe → upload to R2 → delete local."""
    sys.path.insert(0, "/home/box/repos/characters/audition")
    import cf_asr

    vid = short["video_id"]
    slug = re.sub(r'[^a-z0-9]+', '-',
                  f"{short['comedian']}-{vid}".lower()).strip('-')[:60]

    # Check if already in R2
    r2_key = f"shorts/{slug}.json"
    try:
        s3.head_object(Bucket=R2_BUCKET, Key=r2_key)
        return {"status": "exists", "r2_key": r2_key}
    except Exception:
        pass

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.m4a")

        # Download audio
        cmd = ["yt-dlp", "-x", "--audio-format", "m4a",
               "-o", audio_path, short["url"], "--no-playlist",
               "--max-filesize", "50M"]
        if Path(COOKIES).exists():
            cmd += ["--cookies", COOKIES]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return {"status": "download_failed", "error": r.stderr[:200]}

        files = list(Path(tmpdir).glob("*.m4a"))
        if not files:
            return {"status": "no_audio"}

        # Transcribe
        try:
            asr = cf_asr.transcribe(str(files[0]))
        except Exception as e:
            return {"status": "transcribe_failed", "error": str(e)[:200]}

        transcript = " ".join(w["text"] for w in asr["words"])

        # Upload transcript to R2
        data = {**short, "transcript": transcript, "words": asr["words"]}
        s3.put_object(Bucket=R2_BUCKET, Key=r2_key,
                      Body=json.dumps(data).encode(),
                      ContentType="application/json")

        # Upload audio to R2
        audio_key = f"shorts-audio/{slug}.m4a"
        s3.upload_file(str(files[0]), R2_BUCKET, audio_key)

        return {
            "status": "done",
            "r2_key": r2_key,
            "audio_key": audio_key,
            "n_words": len(asr["words"]),
        }


def batch_process(shorts: list[dict], delay: float = 2.0):
    """Process a batch of shorts with rate limiting."""
    results = {"done": 0, "exists": 0, "failed": 0, "errors": []}

    for i, short in enumerate(shorts):
        print(f"[{i+1}/{len(shorts)}] {short['comedian']}: {short['title'][:40]}...", end=" ")
        result = process_short(short)
        print(f"{result['status']}")

        if result["status"] == "done":
            results["done"] += 1
        elif result["status"] == "exists":
            results["exists"] += 1
        else:
            results["failed"] += 1
            results["errors"].append({"video": short["video_id"], **result})

        time.sleep(delay)  # rate limit

    return results


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Shorts Pipeline")
    p.add_argument("--top", type=int, help="Download top N by views")
    p.add_argument("--min-views", type=int, default=100000)
    p.add_argument("--comedian", help="Filter by comedian")
    p.add_argument("--video", help="Process single video ID")
    p.add_argument("--list", action="store_true", help="List available shorts")
    p.add_argument("--delay", type=float, default=2.0, help="Delay between downloads")
    args = p.parse_args()

    if args.list:
        shorts = load_shorts(min_views=args.min_views)
        print(f"{len(shorts)} shorts with >{args.min_views} views:")
        for s in shorts[:20]:
            print(f"  {s['comedian']:20s} {s['views']:>12,} views  {s['duration_s']:>3}s  {s['title'][:40]}")

    elif args.video:
        shorts = load_shorts(min_views=0)
        match = [s for s in shorts if s["video_id"] == args.video]
        if match:
            result = process_short(match[0])
            print(json.dumps(result, indent=2))
        else:
            print(f"Video {args.video} not found in funnygraph data")

    elif args.comedian:
        shorts = load_shorts(min_views=args.min_views)
        shorts = [s for s in shorts if args.comedian.lower() in s["comedian"].lower()]
        print(f"{len(shorts)} shorts for {args.comedian}")
        if args.top:
            shorts = shorts[:args.top]
        results = batch_process(shorts, delay=args.delay)
        print(f"\nResults: {json.dumps(results, indent=2)}")

    elif args.top:
        shorts = load_shorts(min_views=args.min_views)
        shorts = shorts[:args.top]
        print(f"Processing top {len(shorts)} shorts...")
        results = batch_process(shorts, delay=args.delay)
        print(f"\nResults: {json.dumps(results, indent=2)}")

    else:
        p.print_help()
