"""Vibe matcher — mechanism-profile similarity, never lines or biography.

Compares any persona (KT-derived or ours) against the roster + all KT
personas by comedy mechanism overlap. Use: find the closest resident for a
target vibe, or find a comedian's kindred spirits for transplant specs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent


def mechanisms_of_persona(p: dict) -> set[str]:
    ops = set()
    h = p.get("humour", "") or ""
    for tok in h.replace(",", " ").split():
        t = tok.strip().lower()
        if t and t not in {"observed", "lean:", "leans", "plays", "and", "or"}:
            ops.add(t)
    com = p.get("comedy") or {}
    ops.update((com.get("operator_priors") or {}).keys())
    ops.update(p.get("preferred_theories") or [])
    if p.get("archetype"):
        ops.add(str(p["archetype"]).lower())
    dc = p.get("dramatic_core") or {}
    for b in dc.get("blind_spots", []) or []:
        ops.add("blind:" + str(b).lower()[:40])
    for t in p.get("traits", []) or []:
        ops.add("trait:" + str(t).lower()[:40])
    return {o for o in ops if len(o) > 2}


def weighted_jaccard(a: set[str], b: set[str], df: dict[str, int], n: int) -> float:
    import math
    def w(t: str) -> float:
        return math.log((1 + n) / (1 + df.get(t, 0))) + 1.0
    inter = a & b
    if not inter:
        return 0.0
    num = sum(w(t) for t in inter)
    den = sum(w(t) for t in (a | b))
    return round(num / den, 3) if den else 0.0


def load_kt_personas() -> dict[str, dict]:
    out = {}
    for f in sorted((ROOT / "theory" / "killtony-personas").glob("*.json")):
        try:
            d = json.loads(f.read_text())
            out[f.stem] = d
        except Exception:
            pass
    return out


def load_roster() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT / "audition"))
    import generate as _gen
    out = {}
    ids = [c["id"] for c in _gen.list_characters()]
    for cid in ids:
        try:
            full = _gen.get_character(cid)
            raw = full.get("raw") or {}
            out[cid] = {"name": full.get("name"), "humour": "",
                        "traits": [f"plays {t}" for t in (full.get("traits") or [])[:4]],
                        "dramatic_core": {"blind_spots": full.get("blind_spots") or []},
                        "comedy": raw.get("comedy", {}),
                        "preferred_theories": list(raw.get("preferred_theories", [])) +
                        list(full.get("preferred_theories", []) or []),
                        "archetype": raw.get("archetype", "")}
        except Exception:
            pass
    return out


def rank(target_mechs: set[str], candidates: dict[str, set[str]],
         df: dict[str, int] | None = None, n: int = 1) -> list[tuple]:
    rows = []
    for cid, mechs in candidates.items():
        if df is None:
            inter, union = target_mechs & mechs, target_mechs | mechs
            j = round(len(inter) / max(1, len(union)), 3)
        else:
            j = weighted_jaccard(target_mechs, mechs, df, n)
        rows.append((j, cid, sorted((target_mechs & mechs))[:6]))
    return sorted(rows, reverse=True)


def load_comedian_vectors() -> dict[str, dict[str, float]]:
    """Observed mechanism rates per comedian from minute files (not boilerplate tags)."""
    import glob as _glob
    import math as _m
    agg: dict[str, dict[str, list]] = {}
    for f in _glob.glob(str(ROOT / "theory" / "killtony-minutes" / "*.json")):
        stem = Path(f).stem
        com = stem.rsplit("-", 1)[0] if "-" in stem else stem
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        for m in d.get("mechanisms", []) or []:
            t = str(m.get("theory", "")).lower()
            v = m.get("verdict", "")
            if t:
                agg.setdefault(com, {}).setdefault(t, []).append(1.0 if v == "yes" else 0.0)
    return {c: {t: sum(v) / len(v) for t, v in ts.items()} for c, ts in agg.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    num = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    da = sum(v * v for v in a.values()) ** 0.5
    db = sum(v * v for v in b.values()) ** 0.5
    return round(num / (da * db), 3) if da and db else 0.0


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", default="ari_matti", help="KT persona stem")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()
    vecs = load_comedian_vectors()
    target = vecs.get(args.persona)
    if not target:
        print("no observed sets for", args.persona)
        return
    print(f"target {args.persona}: sets observed, top mechanisms:",
          sorted(target.items(), key=lambda kv: -kv[1])[:5])
    print("\n-- KT kindred (observed mechanism rates, cosine) --")
    rows = [(cosine(target, v), c) for c, v in vecs.items() if c != args.persona]
    for score, cid in sorted(rows, reverse=True)[: args.top]:
        print(f"{score:.3f} {cid}")
    kt = load_kt_personas()
    target_p = kt.get(args.persona, {})
    tm = mechanisms_of_persona(target_p)
    all_mechs = [mechanisms_of_persona(v) for v in list(kt.values())]
    df: dict[str, int] = {}
    for ms in all_mechs:
        for t in ms:
            df[t] = df.get(t, 0) + 1
    ros = load_roster()
    print("\n-- roster (tag overlap, weighted) --")
    for score, cid, inter in rank(tm, {k: mechanisms_of_persona(v) for k, v in ros.items()},
                                  df, len(all_mechs))[:6]:
        print(f"{score:.3f} {cid} shared={inter}")


if __name__ == "__main__":
    main()
