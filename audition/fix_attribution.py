#!/usr/bin/env python3
"""Repair comedian attribution on existing R2 clips.

Recomputes comedian = parse_name(title) or channel-owner display name and
moves the object to the correct comedian folder when it changed.

Usage: python3 fix_attribution.py [--limit N]
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shorts_harvest import (parse_name, _channel_fallback, resolve_channel_display,  # noqa: E402
                            s3, slugify, R2_BUCKET)

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    pag = s3.get_paginator("list_objects_v2")
    keys = []
    for page in pag.paginate(Bucket=R2_BUCKET, Prefix="comedians/"):
        for o in page.get("Contents", []):
            if "/clips/" in o["Key"] and o["Size"] > 50:
                keys.append(o["Key"])
    if args.limit:
        keys = keys[: args.limit]

    stats = {"checked": 0, "fixed": 0, "left": 0, "deleted": 0}
    for k in keys:
        try:
            d = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=k)["Body"].read())
        except Exception:
            continue
        stats["checked"] += 1
        ch = d.get("channel") or ""
        new = parse_name(d.get("title") or "")
        if not new and ch.startswith("@"):
            disp = resolve_channel_display(d.get("id") or "")
            new = _channel_fallback(disp or "", handle=ch)
        if not new and not ch.startswith("@"):
            new = _channel_fallback(ch, handle=ch)
        old = d.get("comedian") or ""
        if not new or slugify(new) == slugify(old):
            stats["left"] += 1
            continue
        d["comedian"] = new
        vid = (d.get("id") or "").lower()
        new_key = f"comedians/{slugify(new)}/clips/{slugify(new)}-{vid}.json"
        s3.put_object(Bucket=R2_BUCKET, Key=new_key,
                      Body=json.dumps(d).encode(),
                      ContentType="application/json")
        s3.delete_object(Bucket=R2_BUCKET, Key=k)
        stats["fixed"] += 1
        stats["deleted"] += 1
        if stats["fixed"] % 25 == 0:
            print(f"  fixed {stats['fixed']}...", flush=True)
    print(f"fix_attribution: {json.dumps(stats)}", flush=True)


if __name__ == "__main__":
    main()
