#!/usr/bin/env python3
"""Kill Tony minutes in our theory language.

Per set -> theory/killtony-minutes/<set_id>.json:
  who (persona graph ref + hypothesis), trajectory (beat arc in our beat
  types + operators), appraisal/goal/reaction (inferred, flagged),
  mechanisms (Jev probs where done, rule-v0 otherwise), outcome (crowd).

Run: python3 /root/characters/research/kt_translate.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

T = Path("/root/characters/theory")
OUT = T / "killtony-minutes"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_") or "unknown"


def main():
    feats = {}
    for line in open(T / "killtony-features.jsonl"):
        r = json.loads(line)
        feats[(r["set_pointer"]["comedian"], r["set_pointer"]["set_number"])] = r
    jev = {}
    fp = T / "kt-jev-tags.jsonl"
    if fp.exists():
        for line in open(fp):
            try:
                r = json.loads(line)
                jev[(r["comedian"], r.get("set_number"))] = r
            except Exception:
                pass
    OUT.mkdir(exist_ok=True)
    n = 0
    for (comic, num), f in sorted(feats.items()):
        j = jev.get((comic, num))
        mechs = []
        if j:
            for k, v in j["tags"].items():
                mechs.append({"theory": k, "p": v["p"], "verdict": v["verdict"],
                              "source": "jev-1.13"})
            primary = {"operator": None, "theory": j.get("primary"),
                       "confidence": j.get("primary_conf"), "source": "jev-1.13"}
        else:
            for t in f["theories"]:
                mechs.append({"theory": t["theory"], "p": t["confidence"],
                              "verdict": "yes" if t["confidence"] >= 0.6 else "uncertain",
                              "source": "rule-v0"})
            primary = {"operator": None, "theory": None, "confidence": 0,
                       "source": "rule-v0-pending-jev"}
        # trajectory: beat arc in our types + persona-operators at turns
        traj = [{"beat": b["i"], "type": b["type"], "words": b["words"],
                 "turn": bool(b["contrast"] or b["reframe"])} for b in f["beats"]]
        topics = f.get("topics") or []
        minute = {
            "set_id": f.get("set_id") or f"{comic}-{num}",
            "who": {"persona_ref": f"killtony-personas/{slug(comic)}.json",
                    "comedian": comic,
                    "persona_note": "stage persona hypothesis; not the real person"},
            "trajectory": {"beats": traj, "callbacks": f.get("callbacks", []),
                           "arc": f"{traj[0]['type']}->{traj[-1]['type']} over {len(traj)} beats"},
            "appraisal": {"scenario_families": f.get("scenario_families", []),
                          "topics": topics,
                          "inferred": "performer treats this topic as winnable room material",
                          "inferred_flag": True},
            "mechanisms": mechs, "primary": primary,
            "outcome": {"crowd": f.get("crowd"), "crowd_ord": f.get("crowd_ord"),
                        "tony_praise": f.get("tony_praise")},
            "provenance": {"file": f["set_pointer"]["file"],
                           "annotator": "jev-1.13" if j else "rule-v0",
                           "license": "features only; transcript (c) its performers"},
        }
        (OUT / f"{slug(comic)}-{num}.json").write_text(json.dumps(minute, indent=1))
        n += 1
    print(f"minutes in our language: {n} (jev-backed: {len(jev)})")


if __name__ == "__main__":
    main()
