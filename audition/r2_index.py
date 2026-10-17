"""Build the UK comedy metadata index from R2 `comedians/` for funnygraph merges.

Outputs (local, committed):
  audition/index/uk_comedy_index.jsonl      one row per clip
  audition/index/uk_comedy_summary.json     per-comedian aggregates
  audition/index/funnygraph_additions.json  funnygraph-ready rows per comedian

Uploads index + summary to R2 `index/` for durability.

Usage: python3 r2_index.py
"""
from __future__ import annotations
import json, os, re, time
from collections import defaultdict

import boto3

R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index")

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")


def list_keys(prefix: str) -> list[dict]:
    keys, token = [], None
    while True:
        kw = {"Bucket": R2_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        keys.extend(resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def display_name(slug: str, data: dict) -> str:
    c = data.get("comedian") or ""
    if c and c != slug and len(c) < 40 and " " in c:
        return c
    return " ".join(w.capitalize() for w in slug.split("-"))


def source_group(data: dict, channel: str) -> str:
    blob = (str(data.get("source", "")) + " " + channel).lower()
    if "nextup" in blob:
        return "nextup"
    if "fringe" in blob or "bbc" in blob or "ulster" in blob:
        return "bbc-radio"
    if channel:
        return "youtube"
    return "unknown"


def main():
    os.makedirs(OUT, exist_ok=True)
    clips = [o for o in list_keys("comedians/")
             if re.match(r"comedians/[^/]+/clips/.+\.json$", o["Key"])]
    audio_by_stem = {}
    for o in list_keys("comedians/"):
        m = re.match(r"comedians/[^/]+/audio/(.+)\.[a-z0-9]+$", o["Key"])
        if m:
            audio_by_stem[m.group(1)] = o["Key"]

    rows = []
    for o in clips:
        key = o["Key"]
        cslug = key.split("/")[1]
        data = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read())
        words = data.get("words") or []
        dur = words[-1].get("end") if words else data.get("duration_s") or 0
        channel = data.get("channel", "")
        stem = key.split("/")[-1][:-5]
        audio_key = audio_by_stem.get(stem)
        rows.append({
            "comedian": display_name(cslug, data),
            "comedian_slug": cslug,
            "clip_id": data.get("id") or data.get("video_id") or "",
            "title": data.get("title", ""),
            "channel": channel,
            "source_group": source_group(data, channel),
            "url": data.get("url", f"https://youtube.com/watch?v={data.get('id', '')}"),
            "views": data.get("views", 0),
            "likes": data.get("likes", 0),
            "duration_s": round(dur, 1) if dur else None,
            "n_words": len(words),
            "transcript_chars": len(data.get("transcript", "")),
            "r2_clip_key": key,
            "r2_audio_key": audio_key,
        })

    rows.sort(key=lambda r: (r["comedian_slug"], r["title"]))

    with open(os.path.join(OUT, "uk_comedy_index.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by = defaultdict(list)
    for r in rows:
        by[r["comedian_slug"]].append(r)
    summary = {
        "generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source": "r2:comedy-specials/comedians",
        "comedians": len(by),
        "clips": len(rows),
        "total_words": sum(r["n_words"] for r in rows),
        "per_comedian": {},
    }
    for cslug, cro in sorted(by.items()):
        summary["per_comedian"][cslug] = {
            "name": cro[0]["comedian"],
            "clips": len(cro),
            "words": sum(r["n_words"] for r in cro),
            "views": sum(r["views"] or 0 for r in cro),
            "sources": sorted({r["source_group"] for r in cro}),
            "has_audio": sum(1 for r in cro if r["r2_audio_key"]),
        }

    with open(os.path.join(OUT, "uk_comedy_summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    fg = {"generated": summary["generated"], "source": summary["source"], "comedians": []}
    for cslug, cro in sorted(by.items()):
        fg["comedians"].append({
            "comedian_id": cslug,
            "name": cro[0]["comedian"],
            "clips": len(cro),
            "total_views": sum(r["views"] or 0 for r in cro),
            "sources": sorted({r["source_group"] for r in cro}),
            "rows": [{
                "videoId": r["clip_id"],
                "title": r["title"],
                "channel": r["channel"],
                "views": r["views"],
                "duration_s": r["duration_s"],
                "r2_clip": r["r2_clip_key"],
                "source_group": r["source_group"],
            } for r in cro],
        })
    with open(os.path.join(OUT, "funnygraph_additions.json"), "w") as f:
        json.dump(fg, f, ensure_ascii=False, indent=1)

    for name in ("uk_comedy_index.jsonl", "uk_comedy_summary.json"):
        s3.upload_file(os.path.join(OUT, name), R2_BUCKET, f"index/{name}")

    print(f"{len(rows)} clips, {len(by)} comedians, "
          f"{summary['total_words']} words → {OUT}/")
    for cslug, s in summary["per_comedian"].items():
        print(f"  {s['name']:<24} clips={s['clips']:<2} words={s['words']:<6} "
              f"audio={s['has_audio']} {','.join(s['sources'])}")


if __name__ == "__main__":
    main()
