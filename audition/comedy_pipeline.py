"""Comedy Special Pipeline: yt-dlp → transcript → R2 → delete local.

Downloads comedy specials, extracts transcripts, stores in R2.
Never fills local disk.

Usage:
  python3 comedy_pipeline.py --search "Ali Wong Baby Cobra"
  python3 comedy_pipeline.py --url "https://youtube.com/watch?v=..."
  python3 comedy_pipeline.py --bulk funnygraph/transcripts/
"""
from __future__ import annotations
import boto3, json, subprocess, sys, tempfile, os, re
from pathlib import Path

# R2 config
R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"
COOKIES = "/home/box/Downloads/cookies.txt"

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET, region_name="auto")


def search_youtube(query: str, max_results: int = 5) -> list[dict]:
    """Search YouTube for comedy specials."""
    cmd = [
        "yt-dlp", "--flat-playlist", "--print-json",
        f"ytsearch{max_results}:{query}",
        "--no-download",
    ]
    if Path(COOKIES).exists():
        cmd += ["--cookies", COOKIES]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    videos = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                d = json.loads(line)
                videos.append({
                    "id": d.get("id"),
                    "title": d.get("title", ""),
                    "duration": d.get("duration"),
                    "url": f"https://youtube.com/watch?v={d.get('id')}",
                })
            except json.JSONDecodeError:
                continue
    return videos


def download_and_transcribe(url: str, comedian: str = "") -> dict:
    """Download audio, transcribe via CF ASR, upload to R2, delete local."""
    sys.path.insert(0, "/home/box/repos/characters/audition")
    import cf_asr

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.m4a")

        # Download audio only (smaller than video)
        cmd = ["yt-dlp", "-x", "--audio-format", "m4a",
               "-o", audio_path, url, "--no-playlist"]
        if Path(COOKIES).exists():
            cmd += ["--cookies", COOKIES]

        print(f"Downloading audio...")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return {"error": f"download failed: {r.stderr[:200]}"}

        # Find the actual file
        files = list(Path(tmpdir).glob("*.m4a"))
        if not files:
            return {"error": "no audio file produced"}
        audio_path = str(files[0])

        # Get video info
        info_cmd = ["yt-dlp", "--dump-json", "--no-download", url]
        if Path(COOKIES).exists():
            info_cmd += ["--cookies", COOKIES]
        info_r = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(info_r.stdout) if info_r.stdout else {}
        title = info.get("title", "unknown")
        duration = info.get("duration", 0)

        # Transcribe via CF ASR
        print(f"Transcribing ({duration}s)...")
        asr = cf_asr.transcribe(audio_path)
        transcript = " ".join(w["text"] for w in asr["words"])

        # Build R2 key
        slug = re.sub(r'[^a-z0-9]+', '-', f"{comedian}-{title}".lower()).strip('-')[:80]
        r2_key = f"specials/{slug}.json"

        # Upload transcript + metadata to R2
        data = {
            "url": url,
            "title": title,
            "comedian": comedian,
            "duration_s": duration,
            "n_words": len(asr["words"]),
            "transcript": transcript,
            "words": asr["words"],  # word-level timestamps
        }

        s3.put_object(Bucket=R2_BUCKET, Key=r2_key,
                      Body=json.dumps(data).encode(),
                      ContentType="application/json")

        # Also upload raw audio to R2 (compressed)
        audio_key = f"audio/{slug}.m4a"
        print(f"Uploading audio to R2...")
        s3.upload_file(audio_path, R2_BUCKET, audio_key)

        print(f"Done: {r2_key}")
        return {
            "r2_key": r2_key,
            "audio_key": audio_key,
            "title": title,
            "duration": duration,
            "n_words": len(asr["words"]),
        }


def list_specials() -> list[dict]:
    """List all specials in R2."""
    resp = s3.list_objects_v2(Bucket=R2_BUCKET, Prefix="specials/")
    items = []
    for obj in resp.get("Contents", []):
        items.append({"key": obj["Key"], "size": obj["Size"]})
    return items


def get_transcript(slug: str) -> dict:
    """Retrieve transcript from R2."""
    r = s3.get_object(Bucket=R2_BUCKET, Key=f"specials/{slug}.json")
    return json.loads(r["Body"].read())


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Comedy Special Pipeline")
    p.add_argument("--search", help="Search YouTube")
    p.add_argument("--url", help="Direct YouTube URL")
    p.add_argument("--comedian", default="", help="Comedian name")
    p.add_argument("--list", action="store_true", help="List stored specials")
    p.add_argument("--get", help="Get transcript by slug")
    args = p.parse_args()

    if args.list:
        items = list_specials()
        print(f"{len(items)} specials in R2:")
        for i in items:
            print(f"  {i['key']} ({i['size']} bytes)")

    elif args.get:
        data = get_transcript(args.get)
        print(f"Title: {data['title']}")
        print(f"Duration: {data['duration_s']}s")
        print(f"Transcript: {data['transcript'][:200]}...")

    elif args.url:
        result = download_and_transcribe(args.url, args.comedian)
        print(json.dumps(result, indent=2))

    elif args.search:
        videos = search_youtube(args.search)
        print(f"Found {len(videos)} videos:")
        for v in videos:
            dur = f"{v['duration']//60}m" if v['duration'] else "?"
            print(f"  [{dur}] {v['title'][:60]}")
            print(f"       {v['url']}")

    else:
        p.print_help()
