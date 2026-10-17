"""BBC Fringe Comedy Showcase batch: RSS MP3s → ASR → R2 by comedian.

Each episode features 2 comedians; transcript JSON is stored under each
comedian's folder, audio under the first-named comedian's folder.

Usage: python3 bbc_fringe_batch.py [RSS_URL]
"""
from __future__ import annotations
import json, os, re, sys, tempfile, time, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boto3
import cf_asr

R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def slugify(s: str, maxlen: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:maxlen]


def parse_feed(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req, timeout=30).read()
    root = ET.fromstring(xml)
    eps = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        enc = item.find("enclosure")
        if enc is None or not title:
            continue
        dur = item.findtext(f"{ITUNES}duration") or "0"
        try:
            dur = int(dur)
        except ValueError:
            dur = 0
        if dur < 300:  # skip trailers
            continue
        eps.append({"title": title, "mp3": enc.get("url"), "duration": dur})
    return eps


def comedians_from_title(title: str) -> list[str]:
    parts = re.split(r"\s+and\s+|,\s*", title)
    out = []
    for p in parts:
        p = p.strip()
        if p and len(p) < 40 and not p.lower().startswith("welcome"):
            out.append(p)
    return out or ["fringe-showcase"]


def process(ep: dict, force: bool = False) -> dict:
    names = comedians_from_title(ep["title"])
    slug = slugify(f"bbc-fringe-{ep['title']}")
    first = slugify(names[0])
    check_key = f"comedians/{first}/clips/{slug}.json"
    if not force:
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=check_key)
            return {"status": "exists", "key": check_key}
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmpdir:
        mp3 = os.path.join(tmpdir, "ep.mp3")
        req = urllib.request.Request(ep["mp3"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(mp3, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)

        try:
            asr = cf_asr.transcribe(mp3)
        except Exception as e:
            return {"status": "transcribe_failed", "error": str(e)[:200]}

        transcript = " ".join(w["text"] for w in asr["words"])
        data = {"title": ep["title"], "comedians": names,
                "source": "BBC Radio Ulster The Fringe Comedy Showcase",
                "duration_s": ep["duration"],
                "transcript": transcript, "words": asr["words"]}

        for name in names:
            nslug = slugify(name)
            key = f"comedians/{nslug}/clips/{slug}.json"
            s3.put_object(Bucket=R2_BUCKET, Key=key,
                          Body=json.dumps(data).encode(),
                          ContentType="application/json")

        audio_key = f"comedians/{first}/audio/{slug}.mp3"
        s3.upload_file(mp3, R2_BUCKET, audio_key)
        return {"status": "done", "n_words": len(asr["words"]),
                "comedians": names, "keys": len(names)}


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv
    ids = None
    for a in sys.argv[1:]:
        if a.startswith("--ids="):
            ids = [s.strip().lower() for s in a.split("=", 1)[1].split(",") if s.strip()]
    url = argv[0] if argv else "https://podcasts.files.bbci.co.uk/p0jl6yys.rss"
    eps = parse_feed(url)
    if ids:
        eps = [e for e in eps if any(k in e["title"].lower() for k in ids)]
    print(f"Feed: {len(eps)} episodes (>=5min){' [filtered]' if ids else ''}", flush=True)
    stats = {"done": 0, "exists": 0, "failed": 0}
    for i, ep in enumerate(eps):
        print(f"[{i+1}/{len(eps)}] {ep['title'][:50]} ({ep['duration']}s)...", end=" ", flush=True)
        try:
            res = process(ep, force=force)
        except Exception as e:
            res = {"status": "failed", "error": str(e)[:200]}
        print(res["status"], res.get("n_words", ""), flush=True)
        stats["done" if res["status"] == "done" else
              "exists" if res["status"] == "exists" else "failed"] += 1
        if res["status"] not in ("done", "exists"):
            print(f"    error: {res.get('error', '?')}", flush=True)
        time.sleep(1)
    print(f"\nDONE: {json.dumps(stats)}", flush=True)


if __name__ == "__main__":
    main()
