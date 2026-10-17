#!/usr/bin/env python3
"""Merge the shared R2 club queue into the local sources_queue.json."""
import sys
from pathlib import Path

import boto3

HERE = Path(__file__).parent
LOCAL = HERE / "sources_queue.json"

s3 = boto3.client("s3",
    endpoint_url="https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com",
    aws_access_key_id="36c9d71d3defa6b43f53536bdc6f65f3",
    aws_secret_access_key="c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691",
    region_name="auto")

try:
    data = s3.get_object(Bucket="comedy-specials",
                         Key="_coord/sources_queue.json")["Body"].read()
except Exception as e:
    print(f"no remote queue: {str(e)[:80]}", file=sys.stderr)
    sys.exit(0)

remote = [ln for ln in data.decode(errors="ignore").splitlines() if ln.strip()]
have = set(LOCAL.read_text().splitlines()) if LOCAL.exists() else set()
new = [ln for ln in remote if ln not in have]
if new:
    with LOCAL.open("a") as f:
        f.write("\n".join(new) + "\n")
print(f"queue sync: +{len(new)} new (total {len(have) + len(new)})")
