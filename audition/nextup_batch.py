"""UK indie batch: NextUp Comedy shorts + manual queue → R2 organized by comedian.

R2 layout:
  comedians/{comedian-slug}/clips/{comedian-slug}-{video_id}.json   (transcript + words)
  comedians/{comedian-slug}/audio/{comedian-slug}-{video_id}.m4a

Usage:
  python3 nextup_batch.py                     # process all >10K-view shorts
  python3 nextup_batch.py --min-views 5000    # lower threshold
  python3 nextup_batch.py --shorts-json PATH  # different list file
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boto3
import cf_asr
import yt_captions

R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"
COOKIES = "/home/box/Downloads/cookies.txt"

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")

MANUAL_QUEUE = [
    {"id": "NivJKUfa7Sw", "comedian": "Bill Hicks", "title": "Weirdest Question"},
    {"id": "v0pVK0bIJrQ", "comedian": "Alasdair Beckett-King", "title": "Sea"},
    {"id": "qhJF-c04jnc", "comedian": "Miles Jupp", "title": "Chap"},
    {"id": "eV2TlSfWxWE", "comedian": "Miles Jupp", "title": "Dishwasher Fascist"},
    {"id": "r8ky4Zz_Zls", "comedian": "Ali Woods", "title": "Craziest Party Story"},
    {"id": "_QzEmV10xY8", "comedian": "Ali Woods", "title": "At The Moment FULL SPECIAL"},
    {"id": "sgwWxdRhjls", "comedian": "Alexandra Haddow", "title": "Not My Finest Hour FULL SPECIAL"},
]


def slugify(s: str, maxlen: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:maxlen]


def build_roster(rows: list[dict]) -> list[str]:
    names = {r["comedian"] for r in rows if "comedian" in r and len(r["comedian"]) < 40}
    extra = [
        "Josh Jones", "Geoff Norcott", "Rosco McClelland", "Susie McCabe",
        "Alasdair Beckett-King", "Clinton Baptiste", "Tom Ward", "Jen Brister",
        "Jason Byrne", "Zoe Lyons", "Emmanuel Sonubi", "Rachel Parris",
        "Ted Hill", "Lou Taylor", "Miles Jupp", "Hal Cruttenden",
        "Marcus Brigstocke", "Tommy Tiernan", "Bill Hicks", "Dominic Holland",
        "Stuart Laws", "Lara Ricote", "Markus Birdman", "President Obonjo",
        "Alison Spittle", "Alistair Barrie", "Paul Sinha", "Isabelle Farah",
        "Paddy Young", "Ricky Balshaw", "Russell Hicks", "Josh Glanc",
        "Andy Parsons", "Kiri Pritchard-McLean", "Ian Smith", "Sukh Kaur Ojla",
        "Angela Barnes", "Lucy Porter", "Milton Jones", "Felicity Ward",
        "Chris Forbes", "Sarah Roberts", "Andrew White", "Hal Cruttenden",
        "Ayoade Bamgboye", "Dave Landau", "Loni Love",
    ]
    return sorted(names | set(extra), key=len, reverse=True)


def resolve_comedian(row: dict, roster: list[str]) -> str:
    if "comedian" in row:
        name = row["comedian"]
        name = re.split(r"[.,]", name)[0].strip()
        if len(name) < 40:
            return name
    for name in roster:
        if name.lower() in row.get("raw_title", "").lower():
            return name
    return "nextup-comedy"


def process(vid: str, comedian: str, title: str, views: int = 0,
            channel: str = "NextUp Comedy", force: bool = False) -> dict:
    cslug = slugify(comedian)
    slug = slugify(f"{comedian}-{vid}")
    r2_key = f"comedians/{cslug}/clips/{slug}.json"
    audio_key = f"comedians/{cslug}/audio/{slug}.m4a"

    if not force:
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=r2_key)
            return {"status": "exists", "key": r2_key}
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. transcript: YouTube captions first (free, word-level, no limits)
        try:
            cap = yt_captions.fetch_captions(vid, tmpdir)
        except Exception:
            cap = None

        # 2. audio for storage (and ASR fallback)
        audio = os.path.join(tmpdir, "audio.m4a")
        cmd = ["yt-dlp", "-x", "--audio-format", "m4a", "-o", audio,
               f"https://youtube.com/watch?v={vid}", "--no-playlist",
               "--max-filesize", "300M"]
        if Path(COOKIES).exists():
            cmd += ["--cookies", COOKIES]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        files = list(Path(tmpdir).glob("*.m4a"))

        if cap:
            words, transcript, method = cap["words"], cap["transcript"], cap["method"]
        else:
            if r.returncode != 0 or not files:
                return {"status": "download_failed", "error": r.stderr[-200:]}
            try:
                asr = cf_asr.transcribe(str(files[0]))
            except Exception as e:
                return {"status": "transcribe_failed", "error": str(e)[:200]}
            words, transcript, method = asr["words"], \
                " ".join(w["text"] for w in asr["words"]), "cf-whisper"

        data = {"id": vid, "title": title, "comedian": comedian, "channel": channel,
                "views": views, "transcript": transcript, "words": words,
                "transcript_method": method}
        s3.put_object(Bucket=R2_BUCKET, Key=r2_key,
                      Body=json.dumps(data).encode(), ContentType="application/json")
        if files:
            s3.upload_file(str(files[0]), R2_BUCKET, audio_key)
        return {"status": "done", "key": r2_key, "n_words": len(words),
                "method": method}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shorts-json", default="/tmp/opencode/nextup_shorts.json")
    p.add_argument("--min-views", type=int, default=10000)
    p.add_argument("--delay", type=float, default=1.5)
    p.add_argument("--no-manual", action="store_true")
    p.add_argument("--force", action="store_true", help="Overwrite existing R2 clips")
    p.add_argument("--ids", help="Comma-separated video ids (subset of the queue)")
    args = p.parse_args()

    rows = json.loads(Path(args.shorts_json).read_text())
    roster = build_roster(rows)

    queue = []
    for r in rows:
        if r["views"] >= args.min_views:
            queue.append({"id": r["id"], "comedian": resolve_comedian(r, roster),
                          "title": r["title"], "views": r["views"],
                          "raw_title": r.get("raw_title", r["title"])})
    if not args.no_manual:
        for m in MANUAL_QUEUE:
            queue.append({**m, "views": 0, "raw_title": m["title"]})

    seen = set()
    deduped = []
    for q in queue:
        if q["id"] not in seen:
            seen.add(q["id"])
            deduped.append(q)
    queue = deduped
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
        queue = [q for q in queue if q["id"] in wanted]

    print(f"Queue: {len(queue)} videos", flush=True)
    stats = {"done": 0, "exists": 0, "failed": 0}
    for i, q in enumerate(queue):
        print(f"[{i+1}/{len(queue)}] {q['comedian']}: {q['title'][:45]}...", end=" ", flush=True)
        try:
            res = process(q["id"], q["comedian"], q["title"], q["views"], force=args.force)
        except Exception as e:
            res = {"status": "failed", "error": str(e)[:200]}
        print(res["status"], res.get("method", ""), flush=True)
        stats["done" if res["status"] == "done" else
              "exists" if res["status"] == "exists" else "failed"] += 1
        if res["status"] not in ("done", "exists"):
            print(f"    error: {res.get('error', '?')}", flush=True)
        time.sleep(args.delay)
    print(f"\nDONE: {json.dumps(stats)}", flush=True)


if __name__ == "__main__":
    main()
