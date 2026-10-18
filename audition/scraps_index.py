#!/usr/bin/env python3
"""Crawl the Scraps From The Loft stand-up index (A-Z) -> index/scraps_index.json.

Output: list of {"comedian", "special", "url"} for live pages (deduped by key
against what is already in R2 during harvest, not here).

Usage: python3 scraps_index.py
"""
from __future__ import annotations
import html, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
BASE = "https://scrapsfromtheloft.com/stand-up-comedy-scripts"
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]

sys.path.insert(0, HERE)
from scraps_csv_import import parse_title  # noqa: E402


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def main():
    seen: dict[str, dict] = {}
    for letter in LETTERS:
        url = f"{BASE}?su_letter={letter}"
        try:
            page = fetch(url)
        except Exception as e:
            print(f"FAIL {letter}: {e}", flush=True)
            continue
        n = 0
        for m in re.finditer(
                r'<a[^>]+href="(https://scrapsfromtheloft\.com/comedy/[^"]+)"[^>]*>(.*?)</a>',
                page, re.S):
            href, label = m.group(1), html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
            label = re.sub(r"\s+", " ", label).strip()
            if not label or len(label) < 6 or "/comedy/" not in href:
                continue
            if href in seen:
                continue
            comedian, special = parse_title(label)
            seen[href] = {"comedian": comedian, "special": special, "url": href}
            n += 1
        print(f"{letter}: +{n} links", flush=True)
        time.sleep(1.0)
    out = list(seen.values())
    with open(os.path.join(HERE, "index", "scraps_index.json"), "w") as f:
        json.dump({"crawled": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "count": len(out), "items": out}, f, indent=1)
    print(f"scraps_index: {len(out)} live transcript links -> index/scraps_index.json")


if __name__ == "__main__":
    main()
