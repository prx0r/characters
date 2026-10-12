"""Market research via AvatarChannels free MCP (no key, no install).

Queries: avatar comedy formats, product-selling personas, persistent
characters. Output: theory/market/<slug>.json with rows + hypotheses.
Hypotheses feed arena experiments; never auto-copy channels.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "theory" / "market"
URL = "https://avatarchannels.com/mcp"
HDRS = {"Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"}


def _rpc(method: str, params: dict | None = None, rid: int = 1) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": rid,
                       "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(URL, data=body, headers=HDRS)
    raw = urllib.request.urlopen(req, timeout=40).read().decode()
    for line in raw.splitlines():
        if line.startswith("data:"):
            msg = json.loads(line[5:])
            if "result" in msg:
                return msg["result"]
            raise RuntimeError(str(msg.get("error"))[:300])
    raise RuntimeError("no result frame")


def search(query: str, extra: dict | None = None) -> list[dict]:
    args = {"query": query}
    if extra:
        args.update(extra)
    r = _rpc("tools/call", {"name": "search_channels", "arguments": args}, 3)
    txt = r["content"][0]["text"]
    head, _, js = txt.partition("{")
    try:
        return json.loads("{" + js).get("channels", [])
    except Exception:
        return [{"_raw": txt[:500]}]


def hypothesize(rows: list[dict]) -> list[str]:
    hyps = []
    sellers = [c for c in rows if c.get("sells") and c["sells"] != "none found"]
    if sellers:
        hyps.append(f"{len(sellers)}/{len(rows)} sell products: characters can pitch without breaking show — test Oddy-style gift plugs.")
    freq = sorted([c.get("uploads_wk", 0) or 0 for c in rows])
    if freq:
        hyps.append(f"upload cadence median {freq[len(freq)//2]}/wk: match-or-exceed for absurd-comedy lane.")
    niches = {}
    for c in rows:
        niches[c.get("niche", "?")] = niches.get(c.get("niche", "?"), 0) + 1
    top = sorted(niches.items(), key=lambda kv: -kv[1])[:3]
    hyps.append("crowded niches: " + "; ".join(f"{k} x{v}" for k, v in top))
    return hyps


QUERIES = {
    "avatar-comedy": "comedy funny",
    "persistent-characters": "animated couple recurring",
    "product-sellers": "shop store",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, q in QUERIES.items():
        try:
            rows = search(q)
        except Exception as e:
            print(slug, "FAILED", str(e)[:120])
            continue
        doc = {"query": q, "at": time.time(), "n": len(rows),
               "channels": rows, "hypotheses": hypothesize(rows)}
        (OUT / f"{slug}.json").write_text(json.dumps(doc, indent=1))
        print(slug, len(rows), "channels,", len(doc["hypotheses"]), "hypotheses")
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
