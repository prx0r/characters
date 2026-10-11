#!/usr/bin/env python3
"""Kill Tony emotion pass — Shikigami-style state per set.

One parallel Jev call per set: dominant emotion (choice), energy 1-5,
valence/arousal/defensiveness (scores), self-directed (noul).
Merges into theory/killtony-minutes/*.json as state{}.
Resumes; cheap (~200 tok/set).

Run: python3 /root/characters/research/kt_emotion.py [--limit N]
Needs OPENROUTER_API_KEY.
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/pogpet/backend")

KT_DATA = Path("/root/reference/comedy/kill-tony-archive/data")
OUT = Path("/root/characters/theory/kt-emotion.jsonl")
MINUTES = Path("/root/characters/theory/killtony-minutes")

EMOTIONS = ["confident", "anxious", "angry", "gleeful", "deadpan",
            "embarrassed", "defiant", "wistful", "manic", "weary"]


def load_sets():
    out, seen = [], set()
    for f in sorted(glob.glob(str(KT_DATA / "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        items = d if isinstance(d, list) else d.get("sets", [])
        for s in items:
            if not isinstance(s, dict):
                continue
            t = (s.get("set_transcript") or "").strip()
            if not t:
                continue
            h = hashlib.sha256(t.encode()).hexdigest()[:16]
            if h in seen:
                continue
            seen.add(h)
            out.append({"meta": s, "text": t, "hash": h})
    return out


def main():
    import jev as _jev
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    done = set()
    if OUT.exists():
        for line in open(OUT):
            try:
                done.add(json.loads(line)["hash"])
            except Exception:
                pass
    sets = [s for s in load_sets() if s["hash"] not in done]
    if limit:
        sets = sets[:limit]
    print(f"emotion pass: {len(sets)} sets ({len(done)} done)")
    q = {
        "emotion": {"type": "choice", "instructions": "Dominant performed emotion of this minute?",
                    "criteria": {e: e for e in EMOTIONS}},
        "energy": {"type": "score", "instructions": "Performed energy level?",
                   "criteria": ["flat", "low", "medium", "high", "frantic"]},
        "valence": {"type": "score", "instructions": "Emotional valence: hostile to warm?",
                    "criteria": ["hostile", "sharp", "neutral", "warm", "loving"]},
        "arousal": {"type": "score", "instructions": "Arousal level?",
                    "criteria": ["lethargic", "calm", "engaged", "intense", "manic"]},
        "self_directed": {"type": "noul", "instructions": "Is the comic target the performer themselves?"},
    }
    n = 0
    with open(OUT, "a") as f:
        for i, s in enumerate(sets):
            try:
                import jev as _j2
                resp = _j2.decide({"minute": s["text"][:3000]}, q)
                ans = resp.get("answers", {})
            except Exception as e:
                print(f"[{i}] jev error {str(e)[:80]}; stopping")
                break
            g = lambda k, dflt=0.5: float((ans.get(k, {}) or {}).get("noul", dflt))
            pick = lambda k: ((ans.get(k, {}) or {}).get("choice"),
                              round(float((ans.get(k, {}) or {}).get("confidence", 0)), 3))
            em, emc = pick("emotion")
            en = ans.get("energy", {})
            va = ans.get("valence", {})
            ar = ans.get("arousal", {})
            row = {"hash": s["hash"], "comedian": s["meta"].get("comedian_name"),
                   "set_number": s["meta"].get("set_number"), "crowd": s["meta"].get("crowd_reaction"),
                   "state": {"emotion": em, "emotion_conf": emc,
                             "energy": en.get("score") if isinstance(en, dict) else None,
                             "valence": va.get("score") if isinstance(va, dict) else None,
                             "arousal": ar.get("score") if isinstance(ar, dict) else None,
                             "self_directed": round(g("self_directed"), 3)},
                   "annotator": "jev-1.13"}
            f.write(json.dumps(row) + "\n")
            f.flush()
            n += 1
            if n % 25 == 0:
                print(f"  {n}/{len(sets)}...")
            time.sleep(0.3)
    # merge into minute files
    by_hash = {}
    for line in open(OUT):
        try:
            r = json.loads(line)
            by_hash[r["hash"]] = r
        except Exception:
            pass
    feats = {}
    for line in open("/root/characters/theory/killtony-features.jsonl"):
        try:
            r = json.loads(line)
            feats[(r["set_pointer"]["comedian"], r["set_pointer"]["set_number"])] = r.get("set_id", "")
        except Exception:
            pass
    merged = 0
    for jf in MINUTES.glob("*.json"):
        try:
            m = json.load(open(jf))
        except Exception:
            continue
        sid = m.get("set_id", "")
        h = sid.split("-")[-1] if "-" in sid else ""
        e = by_hash.get(h)
        if e and "state" not in m:
            m["state"] = e["state"]
            json.dump(m, open(jf, "w"), indent=1)
            merged += 1
    print(f"done: {n} new, {merged} minute files carry state")


if __name__ == "__main__":
    main()
