"""Harvest shorts for every UK roster comedian (longform presence irrelevant).

For each roster name: yt-dlp search (normal + Shorts filter); results <=185s
with captions get harvested to R2 under the comedian's own slug.
Resumable state: audition/index/shorts_discovery_state.json

Usage:
  python3 uk_shorts_discovery.py --max-names 1200
"""
from __future__ import annotations
import argparse, json, os, re, shlex, subprocess, sys, tempfile, time
import urllib.parse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boto3
import yt_captions

HERE = Path(__file__).parent
ROSTER = HERE / "index" / "uk_roster.json"
PRIORITY = HERE / "index" / "priority_names.json"
STATE = HERE / "index" / "shorts_discovery_state.json"
INDEX = HERE / "index" / "uk_comedy_index.jsonl"
COOKIES = str(HERE / ".env.cookies") if (HERE / ".env.cookies").exists() else \
    "/home/box/Downloads/cookies.txt"

R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")


def slugify(s: str, maxlen: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:maxlen]


def yt_search(query: str, n: int) -> list[dict]:
    cmd = ["yt-dlp", f"ytsearch{n}:{query}", "--flat-playlist", "--dump-json"]
    if Path(COOKIES).exists():
        cmd += ["--cookies", COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return []
    out = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        out.append({"id": d.get("id"), "title": d.get("title") or "",
                    "duration": d.get("duration"), "views": d.get("view_count") or 0,
                    "channel": d.get("channel") or d.get("uploader") or ""})
    return out


def yt_search_shorts(query: str, n: int) -> list[dict]:
    """YouTube search restricted to Shorts (sp=EgIYAQ). Durations may be None."""
    url = ("https://www.youtube.com/results?search_query="
           + urllib.parse.quote_plus(query) + "&sp=EgIYAQ%253D%253D")
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--playlist-end", str(n), url]
    if Path(COOKIES).exists():
        cmd += ["--cookies", COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return []
    out = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        out.append({"id": d.get("id"), "title": d.get("title") or "",
                    "duration": d.get("duration"), "views": d.get("view_count") or 0,
                    "channel": d.get("channel") or d.get("uploader") or ""})
    return out


def harvest(name: str, shorts: list[dict], state: dict) -> int:
    cslug = slugify(name)
    n = 0
    for s in shorts:
        if not s["id"] or (s.get("duration") or 0) > 185:
            continue
        key = f"comedians/{cslug}/clips/{cslug}-{s['id'].lower()}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            n += 1
            continue
        except Exception:
            pass
        with tempfile.TemporaryDirectory() as td:
            try:
                cap = yt_captions.fetch_captions(s["id"], td)
            except Exception:
                cap = None
        if not cap:
            continue
        data = {"id": s["id"], "url": f"https://www.youtube.com/watch?v={s['id']}",
                "title": s["title"], "comedian": name,
                "channel": s["channel"], "views": s["views"],
                "duration_s": s.get("duration"),
                "source_group": "shorts-discovery",
                "transcript": cap["transcript"], "words": cap["words"],
                "transcript_method": cap["method"]}
        s3.put_object(Bucket=R2_BUCKET, Key=key,
                      Body=json.dumps(data).encode(), ContentType="application/json")
        n += 1
        time.sleep(0.8)
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-names", type=int, default=1200)
    args = p.parse_args()

    roster = json.loads(ROSTER.read_text())
    priority = json.loads(PRIORITY.read_text()) if PRIORITY.exists() else []
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    have = set()
    if INDEX.exists():
        for line in INDEX.read_text().splitlines():
            if line.strip():
                have.add(json.loads(line)["comedian"].lower())

    by_low = {e["name"].lower(): e for e in roster}
    entries, seen_names = [], set()
    for n in priority:
        low = n.lower()
        if low in seen_names:
            continue
        seen_names.add(low)
        entries.append(by_low.get(low, {"name": n, "sources": ["priority-2026"]}))
    for e in roster:
        low = e["name"].lower()
        if low in seen_names:
            continue
        seen_names.add(low)
        entries.append(e)

    done = 0
    for entry in entries:
        if done >= args.max_names:
            break
        name = entry["name"]
        if name.lower() in state or name.lower() in have:
            continue

        shorts, seen = [], set()
        for r in yt_search(f"{name} stand up", 10):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            d = r.get("duration")
            if 0 < (d or 0) <= 185 and "apollo" not in (r["title"] or "").lower():
                shorts.append(r)
        for r in yt_search_shorts(f"{name} stand up", 15):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            d = r.get("duration")
            t = (r["title"] or "").lower()
            if (d is None or 0 < d <= 185) and "apollo" not in t and "24/7" not in t:
                shorts.append(r)
        n = harvest(name, shorts[:12], state) if shorts else 0
        state[name] = {"status": "harvested" if n else "no-material-found",
                       "checked": time.strftime("%F"), "harvested": n}
        done += 1
        if done % 5 == 0:
            STATE.write_text(json.dumps(state, indent=0, ensure_ascii=False))
            print(f"  [{done}/{args.max_names}] last: {name} -> {state[name]['status']}",
                  flush=True)
        time.sleep(1.2)

    STATE.write_text(json.dumps(state, indent=0, ensure_ascii=False))
    by = {}
    for v in state.values():
        by[v["status"]] = by.get(v["status"], 0) + 1
    print(f"discovery done: {json.dumps(by)}", flush=True)
    (HERE / "index" / ".shorts_done").touch()


if __name__ == "__main__":
    main()
