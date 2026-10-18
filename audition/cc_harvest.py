#!/usr/bin/env python3
"""Harvest Comedy Central UK (StandUp4AI video list) transcripts via yt-dlp.

Reads the StandUp4AI CSV, keeps English/UK rows, fetches captions and stores
to R2 under channels/comedycentraluk/sets/<vid>.json.

Usage: python3 cc_harvest.py /tmp/opencode/standup4ai.csv [--region en_uk] [--limit N]
"""
from __future__ import annotations
import argparse, csv, json, os, sys, tempfile, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shorts_harvest import s3, R2_BUCKET  # noqa: E402
import yt_captions  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--region", default="en_uk")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [r for r in csv.DictReader(open(args.csv_path, encoding="utf-8"))
            if r.get("region") == args.region]
    if args.limit:
        rows = rows[: args.limit]
    print(f"region {args.region}: {len(rows)} videos", flush=True)

    stats = {"done": 0, "exists": 0, "nocap": 0, "fail": 0}
    for r in rows:
        vid = r["url"].split("v=")[-1].split("&")[0]
        key = f"channels/comedycentraluk/sets/{vid}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            stats["exists"] += 1
            continue
        except Exception:
            pass
        with tempfile.TemporaryDirectory() as td:
            try:
                cap = yt_captions.fetch_captions(vid, td)
            except Exception as e:
                cap = None
                print(f"  error {vid}: {e}", flush=True)
        if not cap:
            stats["nocap"] += 1
            print(f"no captions: {vid} | {r['title'][:60]}", flush=True)
            continue
        data = {"id": vid, "url": r["url"], "title": r["title"],
                "description": (r.get("description") or "")[:500],
                "channel": r.get("channel") or "Comedy Central UK",
                "duration_s": int(float(r["duration"])) if r.get("duration") else None,
                "views": int(float(r["view_count"])) if r.get("view_count") else 0,
                "source": "standup4ai/cc-uk", "region": args.region,
                "n_words": len(cap["words"]), "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "words": cap["words"], "transcript": cap["transcript"],
                "transcript_method": cap["method"]}
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=json.dumps(data).encode(),
                      ContentType="application/json")
        stats["done"] += 1
        if stats["done"] % 20 == 0:
            print(f"  [{stats['done']}/{len(rows)}] {json.dumps(stats)}", flush=True)
        time.sleep(1.0)
    print(f"cc_harvest: {json.dumps(stats)}", flush=True)


if __name__ == "__main__":
    main()
