"""Generate stand-up sets for a real-human pack through the audition pipeline.

  PYTHONPATH=audition python3 research/human_sets.py --slug chris-prior-golf-dad [--n 6] [--length short]

For each scenario.human.v1 block in freaks/<slug>/scenarios.json:
battle.battle(fixed scenario, n candidates) -> winner -> validate_minute (short
format) + gates (incl. privacy hard gates) -> freaks/<slug>/sets/<scenario>.json.
Generator is the house LLM when OPENCODE_API_KEY is set, else template-v0-offline
(the scenario block's authored material). Every file records which.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "audition"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--length", default="short")
    ap.add_argument("--seed", type=int, default=57)
    a = ap.parse_args()
    import battle, gates, generate
    pack = ROOT / "freaks" / a.slug
    scen = json.loads((pack / "scenarios.json").read_text())
    cid = a.slug.replace("-", "_")
    out_dir = pack / "sets"; out_dir.mkdir(exist_ok=True)
    strat = {"success": {}, "failed": {}, "instructions": "", "version": "strategy_01"}
    summary = []
    recent: list[dict] = []
    for i, s in enumerate(scen["scenarios"]):
        r = battle.battle(cid, recent, strat, n=a.n, seed=a.seed + i, scenario=s, length=a.length)
        w = r["winner"]
        errs = generate.validate_minute(w, cid, fmt=a.length)
        g = gates.check(w["beats"], others_present=w["character"]["raw"].get("others_present", []),
                        character=w["character"]["raw"])
        words = sum(len(b["text"].split()) for b in w["beats"])
        rec = {"schema": "human-set.v1", "slug": a.slug, "scenario_id": s["id"], "premise": s.get("premise"),
               "length": a.length, "generator": w["model_id"],
               "authorship": scen.get("authorship", "") if w["model_id"].startswith("template") else "house LLM",
               "house_llm": bool(os.getenv("OPENCODE_API_KEY")),
               "operator": w["decision"]["instance"]["operator"], "modulator": w["modulator"],
               "run_id": w["decision"]["config"]["run_id"], "beats": w["beats"], "full_text": w["full_text"],
               "word_count": words, "est_spoken_s": round(words / 2.6, 1),
               "score": r["winner_score"], "candidates": [{k: c[k] for k in ("operator", "modulator", "total", "text")} for c in r["table"]],
               "validate_minute": errs or "PASS", "gates": g, "created_at": time.time()}
        (out_dir / f"{s['id']}.json").write_text(json.dumps(rec, indent=1))
        recent = [{"scenario_id": s["id"], "full_text": w["full_text"], "comment": "", "operator_ids": "[]",
                   "rating": 0, "pog_count": 0}] + recent
        summary.append({"scenario": s["id"], "operator": rec["operator"], "modulator": rec["modulator"],
                        "words": words, "score": r["winner_score"]["total"], "validate": rec["validate_minute"],
                        "gates_passed": g["passed"], "flags": g["flags"], "text": w["full_text"]})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
