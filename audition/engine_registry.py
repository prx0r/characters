"""Voice engine registry: collect converged per-performer states.

Reads every voicelab/jev_loop_<set>.json, extracts each performer's
delivery state (speed_scale, beat_scales, emotion biases, bounds status),
writes voicelab/voice_engine.json — the reusable "deliver like X" machine.

Usage: python3 engine_registry.py          # rebuild
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
OUT = LAB / "voice_engine.json"

SET_PERFORMER = {
    "kt704_passport": "ari", "kt715_ep715": "ari", "kt715_walking": "ari",
    "kt715_nashville": "ari", "kt728_diversifying": "ari", "kt728_jamesbond": "ari",
    "casey_rocket_1": "casey", "casey_rocket_2": "casey",
    "louis_roadrage": "louis", "norm_moth": "norm",
    "will_montgomery_1": "will", "kam_patterson_1": "kam", "kam_patterson_2": "kam",
    "sir_winston_pickles_1": "pickles", "sir_winston_pickles_2": "pickles",
}
BOUNDS = {"emotion_acc": 0.60, "wpm_mae": 20.0, "var_mae": 1.5}


def build() -> dict:
    engines = {}
    for bp in sorted(LAB.glob("jev_loop_*.json")):
        setname = bp.stem.replace("jev_loop_", "")
        perf = SET_PERFORMER.get(setname)
        if not perf:
            continue
        d = json.loads(bp.read_text())
        hist = d.get("history") or []
        if not hist:
            continue
        best = min(hist, key=lambda h: (h["wpm_mae"] - 100 * h["emotion_acc"]))
        # emotion confusion from all rounds' rows
        conf = Counter()
        for h in hist:
            for r in h.get("rows", []):
                if not r["match"]:
                    conf[(r["pred_emo"], r["true_emo"])] += 1
        eng = engines.setdefault(perf, {"sets": [], "converged_sets": [],
                                        "confusions": Counter()})
        eng["sets"].append(setname)
        if (best["emotion_acc"] >= BOUNDS["emotion_acc"]
                and best["wpm_mae"] <= BOUNDS["wpm_mae"]
                and best["var_mae"] <= BOUNDS["var_mae"]):
            eng["converged_sets"].append(setname)
        eng["speed_scale"] = best.get("speed_scale", 1.0)
        eng["beat_scales"] = best.get("beat_scales", {})
        eng["best_round"] = {"set": setname, "round": best.get("round"),
                             "acc": best["emotion_acc"],
                             "wpm_mae": best["wpm_mae"],
                             "var_mae": best["var_mae"]}
        eng["confusions"].update(conf)
        if "profile" not in eng:
            try:
                eng["profile"] = json.loads(
                    (HERE / "jev_loop.py").read_text().split("PROFILES = {")[1]
                    .split(f'"{perf}": {{')[1].split("\n    },")[0].join(["{", "}"]))
            except Exception:
                eng["profile"] = {}

    out = {}
    for perf, eng in engines.items():
        total_rounds = sum(1 for _ in eng["sets"])
        out[perf] = {
            "sets_trained": eng["sets"],
            "converged_sets": eng["converged_sets"],
            "status": "converged" if eng["converged_sets"] else (
                "partial" if any(True for _ in eng["sets"]) else "none"),
            "delivery_state": {
                "speed_scale": eng.get("speed_scale"),
                "beat_scales": eng.get("beat_scales"),
                "emotion_confusions": {f"{a}->{b}": n for (a, b), n in
                                       eng["confusions"].most_common(8)},
            },
            "best_round": eng.get("best_round"),
            "bounds": BOUNDS,
        }
    doc = {"rule": "state = speed_scale + beat_scales + confusions; "
                   "converged = acc>=0.6 & wpm_mae<=20 & var_mae<=1.5",
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "performers": out}
    OUT.write_text(json.dumps(doc, indent=2))
    print(f"voice_engine.json: {len(out)} performers")
    for perf, e in out.items():
        print(f"  {perf:12} status={e['status']:10} "
              f"sets={len(e['sets_trained'])} converged={e['converged_sets'] or '-'} "
              f"scale={e['delivery_state']['speed_scale']}")
    return doc


if __name__ == "__main__":
    build()
