#!/usr/bin/env python3
"""Archive local comedy media to R2 under _archive/media/ with a sha256 manifest.

Uploads every file under the given roots, preserving relative paths, then writes
_archive/media/manifest-<date>.json. Does NOT delete anything.

Usage: python3 archive_media.py /home/box/comedy-audio /home/box/comedy_sets /tmp/tmporhl11k3.wav
"""
from __future__ import annotations
import hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shorts_harvest import s3, R2_BUCKET  # noqa: E402

PREFIX = "_archive/media"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    roots = [Path(p) for p in sys.argv[1:]]
    files = []
    for root in roots:
        if root.is_file():
            files.append((root, root.name))
        elif root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    files.append((p, str(p.relative_to(root.parent))))
    print(f"{len(files)} files to archive", flush=True)
    manifest = []
    for i, (path, rel) in enumerate(files, 1):
        key = f"{PREFIX}/{rel}"
        size = path.stat().st_size
        try:
            head = s3.head_object(Bucket=R2_BUCKET, Key=key)
            if head["ContentLength"] == size:
                manifest.append({"path": str(path), "key": key, "size": size,
                                 "sha256": head.get("Metadata", {}).get("sha256", "")})
                print(f"  [{i}/{len(files)}] exists {key}", flush=True)
                continue
        except Exception:
            pass
        digest = sha256(path)
        for attempt in range(3):
            try:
                s3.upload_file(str(path), R2_BUCKET, key,
                               ExtraArgs={"Metadata": {"sha256": digest,
                                                       "origin_path": str(path)}})
                break
            except Exception as e:
                print(f"  retry {attempt+1} {path}: {str(e)[:80]}", flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            print(f"  FAILED {path}", flush=True)
            continue
        manifest.append({"path": str(path), "key": key, "size": size, "sha256": digest})
        print(f"  [{i}/{len(files)}] {size/1048576:.1f} MB -> {key}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%F")
    mkey = f"{PREFIX}/manifest-{stamp}.json"
    s3.put_object(Bucket=R2_BUCKET, Key=mkey,
                  Body=json.dumps({"created": stamp, "entries": manifest}, indent=1).encode(),
                  ContentType="application/json")
    total = sum(e["size"] for e in manifest)
    print(f"done: {len(manifest)} files, {total/1048576:.0f} MB, manifest -> {mkey}", flush=True)


if __name__ == "__main__":
    main()
