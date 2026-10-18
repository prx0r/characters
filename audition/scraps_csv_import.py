#!/usr/bin/env python3
"""Import the HuggingFace Scraps-From-The-Loft CSV scrape (419 specials) -> R2.

Usage: python3 scraps_csv_import.py /path/to/comedy-transcripts.csv
"""
from __future__ import annotations
import csv, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shorts_harvest import s3, slugify, R2_BUCKET  # noqa: E402


def parse_title(t: str) -> tuple[str, str]:
    t = re.sub(r"\s*[–—-]\s*(Full\s+)?Transcript.*$", "", t, flags=re.I)
    t = re.sub(r"\s*\|\s*(Full\s+)?Transcript.*$", "", t, flags=re.I).strip()
    m = re.match(r"^([^:]{2,40}):\s*(.+)$", t)
    if m:
        comedian, special = m.group(1).strip(), m.group(2).strip()
    else:
        comedian, special = t, t
    if comedian.isupper():
        comedian = comedian.title()
    return comedian, special


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^(Full\s+)?Transcript of .*?\n+", "", text, flags=re.I)
    for stop in ("Share this article", "Leave a Comment", "More stand-up comedy",
                 "Related Posts"):
        if stop in text:
            text = text.split(stop)[0]
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    path = sys.argv[1]
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    stats = {"stored": 0, "exists": 0, "small": 0}
    for r in rows:
        title = (r.get("transcript-link") or "").strip()
        url = (r.get("transcript-link-href") or "").strip()
        text = clean_text(r.get("transcript") or "")
        if len(text) < 2000:
            stats["small"] += 1
            continue
        comedian, special = parse_title(title)
        cslug, sslug = slugify(comedian), slugify(special)
        key = f"comedians/{cslug}/specials/{sslug}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            stats["exists"] += 1
            continue
        except Exception:
            pass
        words = [{"text": w, "type": "word"}
                 for w in re.findall(r"[A-Za-z0-9']+", text)]
        data = {"id": f"scraps:{cslug}:{sslug}", "url": url, "comedian": comedian,
                "title": title, "special": special, "source": "scrapsfromtheloft-csv",
                "n_words": len(words),
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "words": words, "transcript": text,
                "transcript_method": "published-transcript"}
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=json.dumps(data).encode(),
                      ContentType="application/json")
        stats["stored"] += 1
        if stats["stored"] % 50 == 0:
            print(f"  stored {stats['stored']}...", flush=True)
    print(f"scraps_csv_import: {json.dumps(stats)}", flush=True)


if __name__ == "__main__":
    main()
