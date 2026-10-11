#!/usr/bin/env python3
"""Kill Tony persona graphs — every decoded comedian as a Nolan-shaped
stage-persona graph. HYPOTHESES from observed sets, not biographical facts.

Reads theory/killtony-features.jsonl + raw archive metadata.
Writes theory/killtony-personas/<slug>.json (pogpet character schema).

Run: python3 /root/characters/research/kt_personas.py
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter
from pathlib import Path

KT_DATA = Path("/root/reference/comedy/kill-tony-archive/data")
OUT = Path("/root/characters/theory/killtony-personas")

OP_TO_THEORY = {"rigidify": "rigidity", "status_invert": "status_reversal",
                "double_interpret": "bisociation", "split_knowledge": "audience_alliance",
                "mistake_identity": "mask_collision", "repeat_variation": "repetition_variation",
                "identity_contradict": "identity_contradiction", "unmask": "mask_collision",
                "literalize": "literalise", "bisociate": "bisociation",
                "expose_self_blindness": "self_awareness",
                "character_violation": "escalation"}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_") or "unknown"


def main():
    feats = [json.loads(l) for l in open("/root/characters/theory/killtony-features.jsonl")]
    # raw metadata per comedian for disclosed facts (not psychology)
    raw: dict[str, dict] = {}
    for f in sorted(glob.glob(str(KT_DATA / "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        items = d if isinstance(d, list) else d.get("sets", [])
        for s in items:
            if not isinstance(s, dict):
                continue
            c = s.get("comedian_name") or "Unknown"
            r = raw.setdefault(c, {"n": 0, "disclosed": {}, "fun": [], "interview": []})
            r["n"] += 1
            for k in ("disclosed_age", "disclosed_location", "disclosed_occupation",
                      "disclosed_relationship_status", "disclosed_years_doing_comedy"):
                v = s.get(k)
                if v and str(v) != "None":
                    r["disclosed"].setdefault(k, set()).add(str(v))
            r["fun"].extend(s.get("fun_facts") or [])
            if s.get("interview_summary"):
                r["interview"].append(str(s["interview_summary"])[:200])
    by_comic: dict[str, list] = {}
    for row in feats:
        by_comic.setdefault(row["set_pointer"]["comedian"], []).append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for comic, rows in sorted(by_comic.items()):
        opfreq = Counter(t["operator"] for r in rows for t in r["theories"] if t["confidence"] >= 0.45)
        topics = Counter(t for r in rows for t in (r["topics"] or []))
        crowds = [r["crowd_ord"] for r in rows if r["crowd_ord"] >= 0]
        ops = opfreq.most_common(3)
        theories = [OP_TO_THEORY.get(o, o) for o, _ in ops]
        r = raw.get(comic, {})
        graph = {
            "id": f"kt_{slug(comic)}", "name": comic,
            "version": "kt.persona-hypothesis.v1",
            "hypothesis_note": "STAGE PERSONA inferred from observed Kill Tony sets only. Not a claim about the real person.",
            "provenance": {"sets": len(rows), "files": sorted({x['set_pointer']['file'] for x in rows}),
                           "annotator": "rule-v0", "mean_crowd_ord": round(sum(crowds) / len(crowds), 2) if crowds else None},
            "archetype": "identity_contradiction" if "identity_contradict" in dict(ops) else (theories[0] if theories else "incongruity"),
            "traits": [f"plays {t}" for t, _ in topics.most_common(3)],
            "humour": f"observed lean: {', '.join(o for o, _ in ops) or 'unclassified'}",
            "dramatic_core": {"want": "the minute to land",
                              "fear": "silence",
                              "need": "one reliable closer",
                              "self_model": (r.get("fun") or ["unestablished"])[0][:80],
                              "blind_spots": ["unknown — single-minute evidence only"]},
            "status_model": {"desired_status": "regular",
                             "felt_status": "bucket pull"},
            "knowledge": {"native_period": "now",
                          "knows": [t for t, _ in topics.most_common(3)],
                          "does_not_know": []},
            "perception": {"notices_first": [t for t, _ in topics.most_common(2)],
                           "ignores": [], "watched": [t for t, _ in topics.most_common(6)]},
            "action_policy": {"default_strategy": f"opens, escalates via {ops[0][0] if ops else 'unknown'}"},
            "comedy": {"operator_priors": {o: round(c / max(1, len(rows)), 2) for o, c in ops}},
            "preferred_theories": theories,
            "voice": {"cadence": "unknown from text alone", "tells": []},
            "threads": [t for t, _ in topics.most_common(5)],
            "memories": [],
            "relationships": [],
            "callbacks": [],
            "disclosed": {k: sorted(v) for k, v in r.get("disclosed", {}).items()},
            "masks": "unassigned — needs human review",
        }
        (OUT / f"{slug(comic)}.json").write_text(json.dumps(graph, indent=1))
        n += 1
    print(f"personas: {n} -> {OUT}")


if __name__ == "__main__":
    main()
