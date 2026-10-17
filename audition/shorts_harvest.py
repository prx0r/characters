"""Harvest a YouTube channel's shorts tab: captions-first -> R2 (transcripts only).

Attribution parsed from titles like "Name @ Club | ..." / "Name | ...".
No audio upload (keeps R2 + VPS disk light); transcripts + words only.

Usage:
  python3 shorts_harvest.py --channel @angelcomedyclub --source-group angel-shorts --max 250
"""
from __future__ import annotations
import argparse, json, os, re, shlex, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boto3
import yt_captions

HERE = Path(__file__).parent
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


def _ok_name(s: str) -> str | None:
    s = (s or "").strip().strip("|").strip()
    if not (2 <= len(s.split()) <= 4) or len(s) > 42 or re.search(r"\d", s):
        return None
    if s.lower().startswith(("how ", "why ", "what ", "when ", "the ")):
        return None
    return s


_LIVE_AT_RE = re.compile(r"\s+\b(?:LIVE|Live|live)\b\s+(?:at|from)\b.*$")
_CLUB_NAME_RE = re.compile(r"\b(club|stand|live|tv|channel|presents|shows?|official|"
                           r"music|podcast)\b", re.I)
_CLUB_HANDLE_RE = re.compile(r"club|standup|live|presents", re.I)


def _channel_fallback(ch: str, handle: str = "") -> str | None:
    """Channel display name as comedian; rejects clubs/venues.

    Solo channels often end in 'Comedy' (e.g. 'Jake Lambert Comedy') so only
    club/venue hints disqualify; the handle is a second signal.
    """
    c = (ch or "").strip()
    if not c or c.startswith("@"):
        return None
    if _CLUB_NAME_RE.search(c) or _CLUB_HANDLE_RE.search(handle or ""):
        return None
    c = re.sub(r"\s+comedy$", "", c, flags=re.I).strip()
    return _ok_name(c)


def parse_name(title: str) -> str | None:
    t = re.sub(r"#\S+", "", title).strip()
    if " @ " in t:
        left = t.split(" @ ")[0]
        return _ok_name(left.split("|")[-1])
    segs = [s.strip() for s in t.split("|")]
    if len(segs) >= 2:
        for cand in (segs[1], segs[0]):
            cand = _LIVE_AT_RE.sub("", cand).strip()
            if _CLUB_NAME_RE.search(cand):
                continue
            c = _ok_name(cand)
            if c:
                return c
        return None
    for sep in (" – ", " - "):
        if sep in t:
            cand = t.split(sep)[0]
            if not _CLUB_NAME_RE.search(cand):
                c = _ok_name(cand)
                if c:
                    return c
    return None


_display_cache: dict[str, str | None] = {}


def resolve_channel_display(vid: str) -> str | None:
    """Video id -> channel display name (cached per video)."""
    if vid in _display_cache:
        return _display_cache[vid]
    name = None
    cmd = ["yt-dlp", "--skip-download", "--print", "%(channel)s", "--no-warnings",
           f"https://www.youtube.com/watch?v={vid}"]
    if Path(COOKIES).exists():
        cmd += ["--cookies", COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = (r.stdout or "").strip().splitlines()
        if r.returncode == 0 and out and out[0]:
            name = out[0]
    except Exception:
        pass
    _display_cache[vid] = name
    return name


def list_shorts(channel: str, cap: int) -> list[dict]:
    url = f"https://www.youtube.com/{channel}/shorts"
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--playlist-end", str(cap), url]
    if Path(COOKIES).exists():
        cmd += ["--cookies", COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    out = []
    for line in r.stdout.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        out.append({"id": d.get("id"), "title": d.get("title") or "",
                    "duration": d.get("duration"), "views": d.get("view_count") or 0,
                    "channel": d.get("channel") or d.get("uploader") or channel})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--channel", required=True)
    p.add_argument("--source-group", required=True)
    p.add_argument("--max", type=int, default=150)
    p.add_argument("--fallback-name", default=None)
    args = p.parse_args()

    shorts = list_shorts(args.channel, args.max)
    print(f"{args.channel}: {len(shorts)} entries", flush=True)

    chan_fallback = args.fallback_name
    if not chan_fallback and shorts and (shorts[0].get("channel") or "").startswith("@"):
        disp = resolve_channel_display(shorts[0]["id"])
        chan_fallback = _channel_fallback(disp or "", handle=args.channel)
    if chan_fallback:
        print(f"  solo-channel fallback name: {chan_fallback}", flush=True)

    stats = {"done": 0, "exists": 0, "nocap": 0, "noname": 0, "small": 0}
    for i, s in enumerate(shorts):
        vid = s["id"]
        dur = s.get("duration")
        if dur and dur > 185:
            stats["small"] += 1
            continue
        name = parse_name(s["title"]) or chan_fallback or \
            _channel_fallback(s.get("channel") or "", handle=args.channel)
        if not name:
            stats["noname"] += 1
            continue
        slug = slugify(f"{name}-{vid}")
        cslug = slugify(name)
        key = f"comedians/{cslug}/clips/{slug}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            stats["exists"] += 1
            continue
        except Exception:
            pass

        with tempfile.TemporaryDirectory() as td:
            try:
                cap = yt_captions.fetch_captions(vid, td)
            except Exception:
                cap = None
        if not cap:
            stats["nocap"] += 1
            continue

        data = {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                "title": s["title"], "comedian": name,
                "channel": s["channel"], "views": s["views"],
                "duration_s": dur, "source_group": args.source_group,
                "transcript": cap["transcript"], "words": cap["words"],
                "transcript_method": cap["method"]}
        s3.put_object(Bucket=R2_BUCKET, Key=key,
                      Body=json.dumps(data).encode(), ContentType="application/json")
        stats["done"] += 1
        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(shorts)}] {json.dumps(stats)}", flush=True)
        time.sleep(0.8)

    print(f"harvest done: {json.dumps(stats)}", flush=True)


if __name__ == "__main__":
    main()
