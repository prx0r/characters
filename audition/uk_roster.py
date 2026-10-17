"""Build the UK comedian roster from Wikipedia categories + local sources.

Output: audition/index/uk_roster.json  [{name, sources: [...]}]

Usage: python3 uk_roster.py
"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "index" / "uk_roster.json"

CATEGORIES = [
    "British stand-up comedians",
    "English stand-up comedians",
    "Scottish stand-up comedians",
    "Welsh stand-up comedians",
    "Northern Irish stand-up comedians",
    "British women comedians",
]
API = "https://en.wikipedia.org/w/api.php"


def api(params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}?{q}",
                                 headers={"User-Agent": "patala-research/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def category_members(cat: str) -> list[str]:
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{cat}",
             "cmlimit": "500", "cmtype": "page", "format": "json"}
        if cont:
            p["cmcontinue"] = cont
        d = api(p)
        out += [m["title"] for m in d["query"]["categorymembers"]]
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont or len(out) >= 1500:
            break
        time.sleep(0.3)
    return out


def clean(name: str) -> str:
    for suffix in (" (comedian)", " (stand-up comedian)", " (comic)", " (humourist)"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def main():
    roster: dict[str, set] = {}
    for cat in CATEGORIES:
        names = category_members(cat)
        print(f"{cat}: {len(names)}")
        for n in names:
            roster.setdefault(clean(n), set()).add(f"wikipedia:{cat}")

    for p, tag in [(HERE / "index" / "uk_comedy_index.jsonl", "r2-index")]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip():
                    d = json.loads(line)
                    roster.setdefault(d["comedian"], set()).add(tag)

    out = [{"name": n, "sources": sorted(s)} for n, s in sorted(roster.items())]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"roster: {len(out)} names -> {OUT}")


if __name__ == "__main__":
    main()
