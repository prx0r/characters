#!/usr/bin/env python3
"""Hypothesis engine — reverse-engineer WHY a character works.

For each character (ours from auditions DB, KT comedians from features):
  1. Contrastive mining: pairs of instances differing in ONE factor
     (modulator, operator, scenario) with different outcomes.
  2. Each contrast proposes a falsifiable hypothesis:
     {claim, theory, operator, scope, predicts, evidence, status}.
  3. Formula card: ranked hypotheses + signature combo + open falsifiers.

Statuses: proposed -> testing -> supported | refuted | stale.
Jev slot: jev_decide.theory_present() upgrades tag confidence when keyed.

Run: python3 /root/characters/research/hypothesis.py
Out: theory/character-formulas/<id>.json
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

AUD_DB = Path("/root/characters/audition/auditions.db")
KT_FEATS = Path("/root/characters/theory/killtony-features.jsonl")
OUT = Path("/root/characters/theory/character-formulas")

CROWD = {"silence": 0, "light": 1, "moderate": 2, "big_laughs": 3, "roaring": 4}


def our_instances() -> dict[str, list[dict]]:
    if not AUD_DB.exists():
        return {}
    c = sqlite3.connect(str(AUD_DB))
    c.row_factory = sqlite3.Row
    out = defaultdict(list)
    for r in c.execute("SELECT * FROM auditions"):
        d = dict(r)
        try:
            dec = json.loads(d.get("decision") or "{}")
            ops = json.loads(d.get("operator_ids") or "[]")
        except Exception:
            dec, ops = {}, []
        inst = dec.get("instance", {}) or {}
        fb = c.execute("SELECT * FROM feedbacks WHERE audition_id=?", (d["id"],)).fetchone()
        pogs = c.execute("SELECT COUNT(*) FROM pogs WHERE audition_id=?", (d["id"],)).fetchone()[0]
        rating = dict(fb)["rating"] if fb else None
        room = (dict(fb).get("room_reaction") or "") if fb else ""
        score = None
        if rating is not None:
            score = rating + min(1.0, pogs / 3.0) + (CROWD.get(room, 0) / 8.0 if room else 0)
        out[d["character_id"]].append({
            "id": d["id"], "scenario": d.get("scenario_id"), "operator": (ops or [None])[0],
            "modulator": inst.get("modulator"), "state": (dec.get("config") or {}).get("state", {}),
            "score": score, "rating": rating, "pogs": pogs, "room": room,
            "theories": json.loads(d.get("theory_ids") or "[]"),
        })
    c.close()
    return out


def kt_instances() -> dict[str, list[dict]]:
    if not KT_FEATS.exists():
        return {}
    out = defaultdict(list)
    for line in open(KT_FEATS):
        r = json.loads(line)
        if r.get("crowd_ord", -1) < 0:
            continue
        out["kt_" + r["set_pointer"]["comedian"].lower().replace(" ", "_").replace("-", "_")].append({
            "id": r.get("set_id"), "scenario": (r.get("scenario_families") or ["?"])[0],
            "operator": next((t["operator"] for t in r["theories"] if t["confidence"] >= 0.45), None),
            "modulator": None, "state": {},
            "score": float(r["crowd_ord"]), "rating": None, "pogs": 0, "room": r.get("crowd"),
            "theories": [t["theory"] for t in r["theories"] if t["confidence"] >= 0.45],
        })
    return out


def mine(instances: list[dict]) -> list[dict]:
    """Single-factor contrasts -> hypotheses. Needs >=2 scored instances."""
    scored = [x for x in instances if x["score"] is not None]
    hyps = []
    if len(scored) < 2:
        return [{"claim": "insufficient evidence: need >=2 rated instances",
                 "status": "proposed", "evidence": [x["id"] for x in instances]}]
    for factor in ("modulator", "operator", "scenario"):
        groups = defaultdict(list)
        for x in scored:
            groups[x[factor]].append(x)
        if len(groups) < 2:
            continue
        ranked = sorted(groups.items(), key=lambda kv: -(sum(v["score"] for v in kv[1]) / len(kv[1])))
        (best_k, best_v), (worst_k, worst_v) = ranked[0], ranked[-1]
        best_m = sum(v["score"] for v in best_v) / len(best_v)
        worst_m = sum(v["score"] for v in worst_v) / len(worst_v)
        gap = round(best_m - worst_m, 2)
        if gap <= 0:
            continue
        hyps.append({
            "claim": f"{factor} '{best_k}' outperforms '{worst_k}' (gap {gap:+})",
            "factor": factor, "winner": best_k, "loser": worst_k, "gap": gap,
            "predicts": f"next {factor}-'{best_k}' instance scores above {worst_m:.1f}",
            "evidence_for": [v["id"] for v in best_v],
            "evidence_against": [v["id"] for v in worst_v],
            "status": "testing" if len(scored) >= 6 else "proposed",
            "n": len(scored),
        })
    if not hyps:
        hyps.append({"claim": "no single-factor gap found; outcomes consistent across factors",
                     "status": "proposed",
                     "evidence": [x["id"] for x in scored]})
    return hyps


def card(cid: str, instances: list[dict]) -> dict:
    hyps = mine(instances)
    scored = [x for x in instances if x["score"] is not None]
    sig = {}
    if scored:
        combos = defaultdict(list)
        for x in scored:
            combos[(x["modulator"], x["operator"])].append(x["score"])
        if combos:
            (m, o), vs = max(combos.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
            sig = {"modulator": m, "operator": o,
                   "mean": round(sum(vs) / len(vs), 2), "n": len(vs)}
    return {"character_id": cid, "n_instances": len(instances), "n_scored": len(scored),
            "signature": sig, "hypotheses": hyps,
            "falsifiers": ["a losing instance with the signature combo",
                           "a winning instance contradicting the top hypothesis"],
            "note": "Formula = ranked falsifiable claims, not a fixed joke template."}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = our_instances()
    for k, v in kt_instances().items():
        data.setdefault(k, v)
    # focus cards: ours + KT comedians with >=3 sets
    keep = [k for k, v in data.items() if not k.startswith("kt_") or len(v) >= 3]
    for cid in sorted(keep):
        (OUT / f"{cid}.json").write_text(json.dumps(card(cid, data[cid]), indent=1))
    print(f"formula cards: {len(keep)} "
          f"(ours: {sum(1 for k in keep if not k.startswith('kt_'))}, "
          f"kt>=3sets: {sum(1 for k in keep if k.startswith('kt_'))})")


if __name__ == "__main__":
    main()
