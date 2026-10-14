"""Voice battle: blind A/B pairs -> Elo + Wilson -> fitted casting weights.

The port (owner proposal): influence's arena loop (blind A/B + Elo/Wilson)
onto voice casting. Pairs of candidates (voice cards, stencils, or recipes)
render the SAME material; human picks blind; Elo converges; ~20 picks
fits weights (mini-LoRe, no training infra). Replaces hand-set scores.

Unified verdict shape (shared with influence fuse()):
  {state: hot|growing|steady|cooling|cold,
   action: double_down|experiment|pivot,
   n: int, confidence: float, source: "battle"|"crowd"|"model"}

Usage:
  python3 voice_battle.py start                 # new session (random pair)
  python3 voice_battle.py show                  # current pair + paths to wavs
  python3 voice_battle.py pick a|b              # record blind pick, next pair
  python3 voice_battle.py board                 # Elo table + verdicts + wilson
"""
from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
BATTLE = LAB / "battle"
STATE = BATTLE / "state.json"

K = 32
INIT = 1500.0


def wilson(wins: int, n: int, z: float = 1.96) -> float:
    """Wilson lower bound — our Wilson-before-crowns rule."""
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    rad = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return round((centre - rad) / denom, 3)


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"ratings": {}, "history": [], "current": None,
            "material": "I run river protection. Payment is cucumbers. "
                        "Strictly cucumbers. Dave owes me nine.",
            "candidates": {}, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def save(s: dict) -> None:
    BATTLE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def rating(s: dict, cid: str) -> float:
    return s["ratings"].get(cid, INIT)


def verdict_for(cid: str, s: dict) -> dict:
    """Unified verdict shape from battle record."""
    h = [x for x in s["history"] if cid in (x.get("a"), x.get("b"))]
    wins = sum(1 for x in h if x.get("winner") == cid)
    n = len(h)
    w = wilson(wins, n)
    r = rating(s, cid)
    if n < 3:
        state, action = "steady", "experiment"
    elif r >= 1550 and w > 0.5:
        state, action = "hot", "double_down"
    elif r >= 1500:
        state, action = "growing", "experiment"
    elif r >= 1450:
        state, action = "cooling", "experiment"
    else:
        state, action = "cold", "pivot"
    return {"state": state, "action": action, "n": n, "wins": wins,
            "elo": round(r, 1), "wilson_lb": w, "source": "battle"}


def next_pair(s: dict, exclude: tuple | None = None) -> dict:
    cids = list(s["candidates"])
    if len(cids) < 2:
        raise RuntimeError("need >=2 candidates (add via --add)")
    pairs = [(a, b) for i, a in enumerate(cids) for b in cids[i + 1:]]
    seen = {(x["a"], x["b"]) for x in s["history"]}
    fresh = [p for p in pairs if p not in seen and p[::-1] not in seen]
    pool = fresh or pairs
    a, b = random.choice(pool)
    return {"a": a, "b": b}


def add_candidate(s: dict, cid: str, meta: dict | None = None) -> None:
    s["candidates"][cid] = meta or {}
    s["ratings"].setdefault(cid, INIT)


def pick(s: dict, winner: str) -> None:
    cur = s["current"]
    loser = cur["b"] if winner == cur["a"] else cur["a"]
    ra, rb = rating(s, cur["a"]), rating(s, cur["b"])
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    eb = 1 - ea
    sa = 1.0 if winner == cur["a"] else 0.0
    s["ratings"][cur["a"]] = ra + K * (sa - ea)
    s["ratings"][cur["b"]] = rb + K * ((1 - sa) - eb)
    s["history"].append({"a": cur["a"], "b": cur["b"], "winner": winner,
                         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    s["current"] = next_pair(s)
    save(s)
    print(f"recorded: {winner} beats {loser} | next pair: {s['current']['a']} vs {s['current']['b']}")


def board(s: dict) -> None:
    print(f"{'candidate':28} {'elo':>7} {'W-L':>6} {'wilson':>7} {'verdict':>22}")
    rows = sorted(s["ratings"].items(), key=lambda kv: -kv[1])
    for cid, r in rows:
        v = verdict_for(cid, s)
        print(f"{cid:28} {r:>7.1f} {v['wins']}-{v['n']-v['wins']:>3} "
              f"{v['wilson_lb']:>7.3f} {v['state']+'/'+v['action']:>22}")
    # save verdicts for casting.json consumption
    out = {cid: verdict_for(cid, s) for cid in s["ratings"]}
    (BATTLE / "verdicts.json").write_text(json.dumps(
        {"rule": "calibrate at ~20 picks; wilson LB gates 'hot'",
         "verdicts": out, "picks": len(s["history"]),
         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2))


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start")
    sub.add_parser("show")
    pk = sub.add_parser("pick")
    pk.add_argument("winner", choices=["a", "b"])
    ad = sub.add_parser("add")
    ad.add_argument("cid")
    ad.add_argument("--meta", default="{}")
    sub.add_parser("board")
    ap.add_argument("--material", default=None)
    args = ap.parse_args()
    s = load()
    if args.material:
        s["material"] = args.material
    if args.cmd == "start":
        if not s["candidates"]:
            for c in ("kid_darwin", "spongebob", "roast", "narrator", "luna"):
                add_candidate(s, c, {"type": "voice_card"})
        s["current"] = next_pair(s)
        save(s)
        print(f"pair: {s['current']['a']} vs {s['current']['b']}")
        print(f"material: {s['material'][:70]}...")
    elif args.cmd == "show":
        cur = s.get("current") or next_pair(s)
        s["current"] = cur
        save(s)
        print(f"A: {cur['a']}  B: {cur['b']}")
        print(f"render both with: python3 voice_battle.py material "
              f"(then listen blind — filenames stripped)")
    elif args.cmd == "pick":
        pick(s, args.winner)
    elif args.cmd == "add":
        add_candidate(s, args.cid, json.loads(args.meta))
        save(s)
        print(f"added {args.cid}")
    elif args.cmd == "board":
        board(s)


if __name__ == "__main__":
    _main()
