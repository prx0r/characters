#!/usr/bin/env python3
"""Curation report: best clips + comedians from the discovery club channels.

Scans all R2 clip JSONs, keeps those from web-discovered club channels
(@handles, watcher/angel harvests), ranks clips by views and comedians by
total views, writes index/DISCOVERY_TOP.md + index/discovery_top.json and
uploads both to R2 under _reports/.

Usage: python3 discovery_top.py
"""
from __future__ import annotations
import collections, json
from datetime import datetime, timezone
from pathlib import Path

import boto3

HERE = Path(__file__).parent
R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"
DISCOVERY_GROUPS = {"web-discovered", "angel-shorts"}

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")


def is_discovery(d: dict) -> bool:
    ch = d.get("channel") or ""
    return ch.startswith("@") or d.get("source_group") in DISCOVERY_GROUPS


def main():
    pag = s3.get_paginator("list_objects_v2")
    keys = []
    for page in pag.paginate(Bucket=R2_BUCKET, Prefix="comedians/"):
        for o in page.get("Contents", []):
            if "/clips/" in o["Key"] and o["Size"] > 50:
                keys.append(o["Key"])

    clips = []
    for k in keys:
        try:
            d = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=k)["Body"].read())
        except Exception:
            continue
        if not is_discovery(d):
            continue
        clips.append({"comedian": d.get("comedian") or "?",
                      "channel": d.get("channel") or "?",
                      "title": (d.get("title") or "")[:90],
                      "views": int(d.get("views") or 0),
                      "url": d.get("url") or "",
                      "group": d.get("source_group") or "",
                      "words": len(d.get("words") or [])})

    by_clip = sorted(clips, key=lambda c: -c["views"])
    comics = collections.defaultdict(
        lambda: {"clips": 0, "views": 0, "channels": set(), "best": None})
    for c in clips:
        e = comics[c["comedian"]]
        e["clips"] += 1
        e["views"] += c["views"]
        e["channels"].add(c["channel"])
        if e["best"] is None or c["views"] > e["best"]["views"]:
            e["best"] = c
    top_comics = sorted(comics.items(), key=lambda kv: -kv[1]["views"])
    chans = collections.defaultdict(lambda: {"clips": 0, "views": 0, "comics": set()})
    for c in clips:
        e = chans[c["channel"]]
        e["clips"] += 1
        e["views"] += c["views"]
        e["comics"].add(c["comedian"])
    top_chans = sorted(chans.items(), key=lambda kv: -kv[1]["views"])

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = [f"# Discovery channels — best clips & comedians ({ts})",
          f"\nTotal discovery clips: {len(clips)} across {len(chans)} channels, "
          f"{len(comics)} comedians.\n",
          "## Top clips (views)"]
    for c in by_clip[:25]:
        md.append(f"- **{c['views']:,}** — {c['comedian']} ({c['channel']}) — "
                  f"{c['title']} {c['url']}")
    md.append("\n## Top comedians (total views)")
    for name, e in top_comics[:25]:
        b = e["best"]
        md.append(f"- **{e['views']:,}** views / {e['clips']} clips — {name} "
                  f"(channels: {', '.join(sorted(e['channels']))}) best: {b['url']}")
    md.append("\n## Top channels (total views)")
    for ch, e in top_chans[:15]:
        md.append(f"- **{e['views']:,}** views / {e['clips']} clips — {ch} "
                  f"({len(e['comics'])} comedians)")
    report = "\n".join(md)

    out_json = {"generated": ts, "clips": len(clips),
                "top_clips": by_clip[:100],
                "top_comedians": [{"name": n, "clips": e["clips"],
                                   "views": e["views"],
                                   "channels": sorted(e["channels"]),
                                   "best_url": e["best"]["url"]}
                                  for n, e in top_comics[:100]],
                "channels": [{"channel": c, "clips": e["clips"], "views": e["views"],
                              "comedians": len(e["comics"])} for c, e in top_chans]}

    (HERE / "index" / "DISCOVERY_TOP.md").write_text(report)
    (HERE / "index" / "discovery_top.json").write_text(json.dumps(out_json, indent=1))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    for key in (f"_reports/discovery_top_{stamp}.md", "_reports/discovery_top.md"):
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=report.encode(),
                      ContentType="text/markdown")
    for key in (f"_reports/discovery_top_{stamp}.json", "_reports/discovery_top.json"):
        s3.put_object(Bucket=R2_BUCKET, Key=key,
                      Body=json.dumps(out_json, indent=1).encode(),
                      ContentType="application/json")
    print(f"discovery report: {len(clips)} clips, {len(comics)} comedians, "
          f"{len(chans)} channels -> index/DISCOVERY_TOP.md + R2 _reports/")


if __name__ == "__main__":
    main()
