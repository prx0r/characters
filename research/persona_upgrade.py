#!/usr/bin/env python3
"""Ari-grade rendition upgrade — emotional range + signature devices per persona.

Reads kt-emotion.jsonl + killtony-minutes + kt-jev-tags; writes
emotional_range{}, signature_devices[], would_say_notes into
theory/killtony-personas/<slug>.json. Rerunnable; improves as passes complete.

Run: python3 /root/characters/research/persona_upgrade.py [--comedian NAME]
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

T = Path("/root/characters/theory")


def main():
    only = sys.argv[sys.argv.index("--comedian") + 1].lower() if "--comedian" in sys.argv else None
    emos = [json.loads(l) for l in open(T / "kt-emotion.jsonl")] if (T / "kt-emotion.jsonl").exists() else []
    tags = {}
    if (T / "kt-jev-tags.jsonl").exists():
        for line in open(T / "kt-jev-tags.jsonl"):
            try:
                r = json.loads(line)
                tags[(r["comedian"], r.get("set_number"))] = r
            except Exception:
                pass
    by_comic = collections.defaultdict(list)
    for e in emos:
        by_comic[e["comedian"]].append(e)
    n = 0
    for f in sorted((T / "killtony-personas").glob("*.json")):
        d = json.load(open(f))
        name = d.get("name", "")
        if only and only not in name.lower():
            continue
        rows = by_comic.get(name, [])
        if not rows:
            continue
        st = [r["state"] for r in rows]
        emo_counts = collections.Counter(s.get("emotion") for s in st if s.get("emotion"))
        energies = [s["energy"] for s in st if s.get("energy") is not None]
        mechs = collections.Counter()
        for r in rows:
            t = tags.get((name, r.get("set_number")), {}).get("tags", {})
            for k, v in t.items():
                if isinstance(v, dict) and v.get("verdict") == "yes":
                    mechs[k] += 1
        d["emotional_range"] = {
            "emotions_observed": dict(emo_counts),
            "energy_band": [min(energies), max(energies)] if energies else None,
            "self_directed_rate": round(sum(1 for s in st if (s.get("self_directed") or 0) >= 0.6) / max(1, len(st)), 2),
            "n_states": len(st),
        }
        d["signature_devices"] = [{"mechanism": k, "sets": c} for k, c in mechs.most_common(5)]
        tops = emo_counts.most_common(2)
        d["would_say_notes"] = (
            f"Say YES when: {tops[0][0] if tops else '?'} energy with "
            f"{', '.join(k for k, _ in mechs.most_common(3)) or 'unclassified mechanisms'}. "
            f"Say NO when: flat apology, earnest explainer, off-turf topics outside ({', '.join(d.get('threads', [])[:3])} are home turf).")
        json.dump(d, open(f, "w"), indent=1)
        n += 1
    print(f"renditions upgraded: {n}")


if __name__ == "__main__":
    main()
