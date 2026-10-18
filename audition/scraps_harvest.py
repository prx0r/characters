#!/usr/bin/env python3
"""Fetch full stand-up special transcripts from Scraps From The Loft -> R2.

Stores comedians/<slug>/specials/<special>.json with full text + word list
(no timestamps; laugh markers kept in the text).

Usage: python3 scraps_harvest.py [--only comedian-substr]
"""
from __future__ import annotations
import argparse, html, json, os, re, sys, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shorts_harvest import s3, slugify, R2_BUCKET  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

SPECIALS = [
    ("Stewart Lee", "stand-up-comedian-2005",
     "https://scrapsfromtheloft.com/comedy/stewart-lee-standup-comedian-full-transcript"),
    ("Stewart Lee", "90s-comedian-2006",
     "https://scrapsfromtheloft.com/comedy/stewart-lee-90s-comedian-2006-full-transcript"),
    ("Stewart Lee", "carpet-remnant-world-2012",
     "https://scrapsfromtheloft.com/comedy/stewart-lee-carpet-remnant-world-transcript"),
    ("Stewart Lee", "content-provider-2018",
     "https://scrapsfromtheloft.com/comedy/stewart-lee-content-provider-transcript"),
    ("Daniel Sloss", "jigsaw-2018",
     "https://scrapsfromtheloft.com/comedy/daniel-sloss-jigsaw-transcript"),
    ("Daniel Sloss", "dark-2018",
     "https://scrapsfromtheloft.com/comedy/daniel-sloss-dark-transcript"),
    ("Daniel Sloss", "x-2019",
     "https://scrapsfromtheloft.com/comedy/daniel-sloss-x-transcript"),
]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def extract_entry(page: str) -> str | None:
    m = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>', page)
    if not m:
        return None
    i = m.end()
    depth = 1
    for tag in re.finditer(r"<div\b|</div>", page[i:]):
        if tag.group(0) == "</div>":
            depth -= 1
            if depth == 0:
                return page[i:i + tag.start()]
        else:
            depth += 1
    return page[i:]


def extract_main(page: str) -> str | None:
    frag = extract_entry(page)
    if frag and len(frag) > 3000:
        return frag
    m = re.search(r'<article\b[^>]*class="[^"]*single-article[^"]*"[^>]*>', page)
    if m:
        end = page.find("</article>", m.end())
        if end > 0:
            frag = page[m.end():end]
    return frag


def clean(frag: str) -> str:
    frag = re.sub(r"<(script|style|figure|figcaption|nav|aside)\b.*?</\1>", " ",
                  frag, flags=re.S | re.I)
    frag = re.sub(r"<br\s*/?>", "\n", frag, flags=re.I)
    frag = re.sub(r"</p>", "\n\n", frag, flags=re.I)
    frag = re.sub(r"<[^>]+>", "", frag)
    frag = html.unescape(frag)
    for stop in ("Share this article", "Leave a Comment", "More stand-up comedy",
                 "Related Posts", "© 2026 Scraps"):
        if stop in frag:
            frag = frag.split(stop)[0]
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in frag.splitlines()]
    out, blank = [], 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    return "\n".join(out).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--index", default=None,
                    help="index/scraps_index.json from scraps_index.py (bulk mode)")
    args = ap.parse_args()

    items = SPECIALS
    if args.index:
        with open(args.index) as f:
            items = [(i["comedian"], i["special"], i["url"]) for i in json.load(f)["items"]]

    for comedian, special, url in items:
        if args.only and args.only.lower() not in comedian.lower():
            continue
        cslug, sslug = slugify(comedian), slugify(special)
        key = f"comedians/{cslug}/specials/{sslug}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            print(f"exists: {key}", flush=True)
            continue
        except Exception:
            pass
        try:
            page = fetch(url)
        except Exception as e:
            print(f"FETCH FAIL {url}: {e}", flush=True)
            continue
        frag = extract_main(page)
        text = clean(frag) if frag else ""
        if len(text.split()) < 500:
            print(f"TOO SHORT ({len(text.split())} words): {url}", flush=True)
            continue
        words = [{"text": w, "type": "word"}
                 for w in re.findall(r"[A-Za-z0-9']+", text)]
        data = {"id": f"scraps:{cslug}:{sslug}", "url": url, "comedian": comedian,
                "title": f"{comedian}: {special}", "special": special,
                "source": "scrapsfromtheloft", "n_words": len(words),
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "words": words, "transcript": text,
                "transcript_method": "published-transcript"}
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=json.dumps(data).encode(),
                      ContentType="application/json")
        print(f"stored: {key} ({len(words)} words)", flush=True)
        time.sleep(1.0)


if __name__ == "__main__":
    main()
