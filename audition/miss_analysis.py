"""What-did-we-miss: predicted delivery vs actual audio -> error ledger -> priors.

The closed loop (owner design):
  profile (from KT data) -> export minute (perf_set RL) -> test vs actual ->
  attribute misses to knobs -> update emotion-prior proposals -> theory notes
  (what the voice was DOING around laughs = why the minute works).

Inputs per set: voicelab/perf_sets/<set>.json (renders) + theory prosody/
acoustic/gemini/riff_db ground truth. Output: voicelab/perf_sets/miss_<set>.json
+ aggregate voicelab/emo_priors_v2.json (proposal; human approves merge).

Usage: python3 miss_analysis.py --set kt704_passport [--all-done]
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab" / "perf_sets"

# knob physics (established in calibration loops)
KNOB_FIX = [
    # (condition, knob, delta, why)
    ("wpm_low", "speed", +0.15, "renders slow vs his real pace"),
    ("wpm_high", "speed", -0.15, "renders fast vs his real pace"),
    ("var_low", "temp", +0.10, "too flat vs his pitch movement"),
    ("var_high", "temp", -0.10, "too wild vs his level delivery"),
]


def load_set(setname: str) -> dict | None:
    p = LAB / f"{setname}.json"
    return json.loads(p.read_text()) if p.exists() else None


def actual_prosody(setname: str) -> dict | None:
    clip = setname.replace("_passport", "").replace("louis_", "louis_")
    for cand in (setname, clip, setname.replace("kt704", "kt704"),
                 "kt704" if setname.startswith("kt704") else None,
                 "casey_rocket_1" if "casey_rocket_1" in setname else None,
                 "casey_rocket_2" if "casey_rocket_2" in setname else None,
                 "sir_winston_pickles_1" if "sir_winston_pickles_1" in setname else None,
                 "sir_winston_pickles_2" if "sir_winston_pickles_2" in setname else None,
                 "kt715_ep715" if "kt715_ep715" in setname else None,
                 "kt715_walking" if "kt715_walking" in setname else None,
                 "kt728_diversifying" if "kt728_diversifying" in setname else None,
                 "kt728_jamesbond" if "kt728_jamesbond" in setname else None):
        if not cand:
            continue
        p = REPO / "theory/prosody" / cand / "prosody.json"
        if p.exists():
            return json.loads(p.read_text())
    return None


def analyze(setname: str) -> dict:
    runs = load_set(setname)
    if not runs:
        return {"set": setname, "error": "no render board"}
    pros = actual_prosody(setname)
    m = ((pros or {}).get("metrics") or {})
    real_var = m.get("pitch_variability_semitones")
    thirds = ((pros or {}).get("progression") or {}).get("segments") or []

    misses, proposals = [], defaultdict(lambda: {"wpm_d": [], "var_d": [], "n": 0})
    for seg in runs["segments"]:
        err = {"seg": seg["seg"], "emotion": seg["emotion"],
               "wpm_err": round(seg["wpm"] - seg.get("target_wpm", seg["wpm"]), 1),
               "var_st": seg["var_st"]}
        # vs whole-clip var as coarse ground truth
        if real_var:
            err["var_err_vs_real"] = round(seg["var_st"] - real_var, 2)
        fixes = []
        if err["wpm_err"] < -8:
            fixes.append({"knob": "speed", "delta": +0.15, "why": "too slow vs his timing"})
        elif err["wpm_err"] > 8:
            fixes.append({"knob": "speed", "delta": -0.15, "why": "too fast vs his timing"})
        if real_var and seg["var_st"] < real_var - 1.0:
            fixes.append({"knob": "temp", "delta": +0.10, "why": "flatter than his real voice"})
        elif real_var and seg["var_st"] > real_var + 1.0:
            fixes.append({"knob": "temp", "delta": -0.10, "why": "wilder than his real voice"})
        err["proposed_fixes"] = fixes
        if abs(err["wpm_err"]) > 8 or (real_var and abs(err.get("var_err_vs_real", 0)) > 1):
            misses.append(err)
        p = proposals[seg["emotion"]]
        p["wpm_d"].append(err["wpm_err"])
        p["var_d"].append(err.get("var_err_vs_real") or 0)
        p["n"] += 1

    # aggregate emotion-prior adjustments
    prior_updates = {}
    for emo, p in proposals.items():
        n = max(p["n"], 1)
        dw = sum(p["wpm_d"]) / n
        dv = sum(p["var_d"]) / n
        prior_updates[emo] = {"n": p["n"], "mean_wpm_err": round(dw, 1),
                              "mean_var_err": round(dv, 2),
                              "suggest_speed_delta": round(max(-0.2, min(0.2, -dw / 150)), 2),
                              "suggest_temp_delta": round(max(-0.15, min(0.15, dv / 20)), 2)}

    # theory layer: what was the voice doing around the REAL laughs (casey riff_db)
    theory = []
    rdb = REPO / "theory/killtony-minutes/casey_rocket_riff_db.json"
    if "casey" in setname and rdb.exists():
        db = json.loads(rdb.read_text())
        laughs = (db.get("laugh_times") or [])[:50]
        theory.append({"note": "casey laugh corpus loaded", "n_laughs": len(laughs),
                       "delivery_stats": db.get("delivery_stats")})

    doc = {"set": setname, "misses": misses, "miss_count": len(misses),
           "segment_count": len(runs["segments"]),
           "prior_updates": prior_updates, "theory_notes": theory,
           "real_prosody": {"pitch_var": real_var,
                            "thirds_var": [t.get("pitch_variability_semitones") for t in thirds]},
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"miss_{setname}.json").write_text(json.dumps(doc, indent=2))
    return doc


def aggregate() -> dict:
    all_updates = defaultdict(lambda: {"wpm": [], "var": [], "n": 0})
    for p in sorted(LAB.glob("miss_*.json")):
        d = json.loads(p.read_text())
        for emo, u in (d.get("prior_updates") or {}).items():
            a = all_updates[emo]
            a["wpm"].append(u["mean_wpm_err"]); a["var"].append(u["mean_var_err"])
            a["n"] += u["n"]
    out = {}
    for emo, a in all_updates.items():
        n = max(a["n"], 1)
        mw = sum(a["wpm"]) / len(a["wpm"]) if a["wpm"] else 0
        mv = sum(a["var"]) / len(a["var"]) if a["var"] else 0
        out[emo] = {"n_segments": a["n"],
                    "mean_wpm_err": round(mw, 1), "mean_var_err": round(mv, 2),
                    "emo_temp_delta": round(max(-0.15, min(0.15, mv / 20)), 2),
                    "cue_speed_note": "bump speed" if mw < -5 else ("trim speed" if mw > 5 else "pace ok")}
    doc = {"rule": "PROPOSAL only — human approves before EMO map merge",
           "aggregated_from": len(list(LAB.glob('miss_*.json'))),
           "updates": out, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (HERE / "voicelab" / "emo_priors_v2.json").write_text(json.dumps(doc, indent=2))
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set")
    ap.add_argument("--all-done", action="store_true")
    args = ap.parse_args()
    if args.all_done:
        names = [p.stem for p in LAB.glob("*.json") if not p.name.startswith(("miss_",))]
        for n in names:
            d = analyze(n)
            print(f"{n}: {d.get('miss_count')}/{d.get('segment_count')} misses")
    elif args.set:
        d = analyze(args.set)
        print(json.dumps({k: d[k] for k in ("set", "miss_count", "segment_count", "prior_updates")}, indent=1))
    agg = aggregate()
    print("priors v2:", json.dumps(agg["updates"], indent=1)[:600])


if __name__ == "__main__":
    main()
