"""Merge R2 UK clips into funnygraph (prx0r/funnygraph), prep a contribution branch.

For every comedian with a comedian-graph.json in the funnygraph clone:
  - enrich clip rows via yt-dlp --dump-json (channelId, subs, publishedAt, likes ...)
  - merge into data/youtube/{slug}.json (dedupe by videoId, recompute aggregates)

Comedians without a graph go to uk_clips_proposed/{slug}.json (same row format)
so the graph can be created first.

Usage:
  python3 funnygraph_sync.py                 # write into clone (no git actions)
  python3 funnygraph_sync.py --push          # commit + push branch uk-clips-<date>
  python3 funnygraph_sync.py --no-enrich     # skip yt-dlp metadata (uses cache only)
"""
from __future__ import annotations
import argparse, json, os, shlex, subprocess, time
from pathlib import Path

HERE = Path(__file__).parent
INDEX = HERE / "index" / "uk_comedy_index.jsonl"
CACHE = HERE / "index" / "yt_meta_cache.json"
FG = Path(os.environ.get("FUNNYGRAPH_DIR", "/tmp/funnygraph"))
YT = FG / "data" / "youtube"
PROPOSED = FG / "uk_clips_proposed"
COOKIES = str(HERE / ".env.cookies") if (HERE / ".env.cookies").exists() else \
    "/home/box/Downloads/cookies.txt"

SLUG_FIXES = {
    "marcus-brigstock": "marcus-brigstocke",
    "jason-byrne": "jason-byrne",
}


def _gh_token() -> str | None:
    tok = os.environ.get("GH_PUSH_TOKEN")
    if tok:
        return tok
    envf = HERE / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line.startswith("GH_PUSH_TOKEN="):
                return line.split("=", 1)[1].strip()
    return None


def bracket(subs: int | None) -> str | None:
    if subs is None:
        return None
    if subs < 10_000:
        return "micro (<10k)"
    if subs < 100_000:
        return "small (<100k)"
    if subs < 1_000_000:
        return "medium (<1M)"
    return "large (>=1M)"


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def enrich(vid: str, cache: dict) -> dict | None:
    if vid in cache:
        return cache[vid]
    cmd = ["yt-dlp", "--dump-json", "--no-download", "--no-playlist",
           f"https://youtube.com/watch?v={vid}"]
    if Path(COOKIES).exists():
        cmd += ["--cookies", COOKIES]
    cmd += shlex.split(os.environ.get("YTDLP_EXTRA", ""))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            cache[vid] = None
            return None
        d = json.loads(r.stdout.splitlines()[0])
        meta = {
            "channel": d.get("channel"),
            "channelId": d.get("channel_id"),
            "channel_subs": d.get("channel_follower_count"),
            "publishedAt": (d.get("upload_date") or "")[:4] + "-" +
                           (d.get("upload_date") or "")[4:6] + "-" +
                           (d.get("upload_date") or "")[6:8] if d.get("upload_date") else None,
            "views": d.get("view_count"),
            "likes": d.get("like_count"),
            "comments": d.get("comment_count"),
            "duration_s": d.get("duration"),
        }
        cache[vid] = meta
        return meta
    except Exception:
        cache[vid] = None
        return None


def row_for(clip: dict, meta: dict | None) -> dict:
    meta = meta or {}
    views = meta.get("views") if meta.get("views") is not None else (clip.get("views") or 0)
    subs = meta.get("channel_subs")
    return {
        "videoId": clip["clip_id"],
        "title": clip["title"],
        "channel": meta.get("channel") or clip.get("channel") or "",
        "channelId": meta.get("channelId"),
        "channel_subs": subs,
        "bracket": bracket(subs),
        "publishedAt": meta.get("publishedAt"),
        "views": views,
        "likes": meta.get("likes") or 0,
        "comments": meta.get("comments") or 0,
        "duration_s": meta.get("duration_s") or clip.get("duration_s"),
        "r2_clip": clip["r2_clip_key"],
        "transcript": True,
        "source_group": clip["source_group"],
    }


def aggregates(rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda r: -(r.get("views") or 0))
    total_views = sum(r.get("views") or 0 for r in rows)
    total_likes = sum(r.get("likes") or 0 for r in rows)
    return {
        "clips": len(rows),
        "total_views": total_views,
        "total_likes": total_likes,
        "avg_views": round(total_views / len(rows)) if rows else 0,
        "like_rate": round(total_likes / total_views, 5) if total_views else 0.0,
        "top_clip": rows[0] if rows else None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--push", action="store_true")
    p.add_argument("--no-enrich", action="store_true")
    args = p.parse_args()

    clips = [json.loads(l) for l in INDEX.read_text().splitlines() if l.strip()]
    yt_clips = [c for c in clips if c["clip_id"] and c["source_group"] != "bbc-radio"]
    print(f"{len(clips)} clips, {len(yt_clips)} YouTube clips")

    cache = load_cache()
    if not args.no_enrich:
        for i, c in enumerate(yt_clips):
            if c["clip_id"] not in cache:
                enrich(c["clip_id"], cache)
                if (i + 1) % 10 == 0:
                    print(f"  enriched {i+1}/{len(yt_clips)}")
                    CACHE.write_text(json.dumps(cache, indent=0))
        CACHE.write_text(json.dumps(cache, indent=0))

    by_comedian: dict[str, list[dict]] = {}
    for c in yt_clips:
        fg_slug = SLUG_FIXES.get(c["comedian_slug"], c["comedian_slug"])
        by_comedian.setdefault(fg_slug, []).append(c)

    written, proposed = [], []
    for slug, cro in sorted(by_comedian.items()):
        rows = [row_for(c, cache.get(c["clip_id"])) for c in cro]
        graph = FG / "comedians" / slug / "comedian-graph.json"
        is_known = graph.exists()

        if is_known:
            path = YT / f"{slug}.json"
            if path.exists():
                old = json.loads(path.read_text())
                old_rows = {r["videoId"]: r for r in old.get("rows", [])}
                for r in rows:
                    old_rows[r["videoId"]] = r  # fresh metadata wins
                rows = list(old_rows.values())
                channels = old.get("channels", {})
            else:
                channels = {}
            method = "uk-clips-harvest (transcript-first)"
            out = {"comedian_id": slug,
                   "name": cro[0]["comedian"],
                   "channels": channels, **aggregates(rows), "rows": rows,
                   "method": method}
            YT.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
            written.append(slug)
        else:
            PROPOSED.mkdir(parents=True, exist_ok=True)
            out = {"comedian_id": slug, "name": cro[0]["comedian"],
                   **aggregates(rows), "rows": rows, "method": "uk-clips-harvest (graph pending)"}
            (PROPOSED / f"{slug}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
            proposed.append(slug)

    print(f"wrote {len(written)} data/youtube files: {written}")
    print(f"proposed (no graph yet) {len(proposed)}: {proposed}")

    if args.push:
        date = time.strftime("%Y-%m-%d")
        branch = f"uk-clips-{date}"
        subprocess.run(["git", "checkout", "-B", branch], cwd=FG, check=True)
        subprocess.run(["git", "add", "data/youtube", "uk_clips_proposed"], cwd=FG, check=True)
        msg = (f"UK clips batch {date}: transcripts + YouTube rows from R2 index\n\n"
               f"- {len(yt_clips)} YouTube clips across {len(by_comedian)} comedians\n"
               f"- data/youtube: {', '.join(written) or '-'}\n"
               f"- uk_clips_proposed (graph pending): {', '.join(proposed) or '-'}\n"
               f"- transcripts + word timings in R2: comedy-specials/comedians/*/clips/")
        subprocess.run(["git", "commit", "-m", msg], cwd=FG, check=True)
        tok = _gh_token()
        remote = "origin"
        if tok:
            remote = f"https://{tok}@github.com/prx0r/funnygraph.git"
        subprocess.run(["git", "push", remote, f"{branch}:{branch}"], cwd=FG, check=True)
        print(f"pushed branch {branch}")


if __name__ == "__main__":
    main()
