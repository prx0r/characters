"""Backfill url (and missing comedian tag) into existing R2 clip JSONs.

--dry-run to just report. Idempotent.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shorts_harvest import s3, R2_BUCKET  # noqa: E402

dry = "--dry-run" in sys.argv
token = None
fixed = checked = 0
while True:
    kw = dict(Bucket=R2_BUCKET, Prefix="comedians/")
    if token:
        kw["ContinuationToken"] = token
    r = s3.list_objects_v2(**kw)
    for o in r.get("Contents", []):
        key = o["Key"]
        if not key.endswith(".json"):
            continue
        checked += 1
        d = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read())
        changed = False
        vid = d.get("id")
        if vid and not d.get("url"):
            d["url"] = f"https://www.youtube.com/watch?v={vid}"
            changed = True
        if changed and not dry:
            s3.put_object(Bucket=R2_BUCKET, Key=key,
                          Body=json.dumps(d).encode(),
                          ContentType="application/json")
        if changed:
            fixed += 1
            print(("DRY " if dry else "FIX ") + key)
    token = r.get("NextContinuationToken")
    if not token:
        break
print(f"checked {checked}, fixed {fixed}")
