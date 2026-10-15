"""Theory tagger: granular per-beat theory labels + laugh correlation.

Tags each beat via Jev (typed, ~$0.0001/set): garden_path_step,
identity_contradiction (noul), semantic_surprise (score 0-3), escalation.
Computed (no Jev): pause_before (temporal violation), wpm_deviation from
set baseline. Then correlates tags with GT laugh proximity — the
"what makes a set funny" first pass, beat-granular.

Usage: python3 theory_tagger.py --set kt704_passport
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_or import decide
from jev_deliver import fixed_beats, gemini_labels

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"


def tag_set(setname: str) -> dict:
    words = json.loads((REPO / "theory/scribe" / f"{setname}.json").read_text())["words"]
    gt_p = REPO / "theory/killtony-minutes" / f"{setname}_gemini.gemini.json"
    gt = json.loads(gt_p.read_text()) if gt_p.exists() else {"segments": []}
    beats = fixed_beats(words)
    # computed temporal features
    clean = [w for w in words if not w["text"].strip().startswith("[")]
    for i, b in enumerate(beats):
        in_win = [w for w in clean if b["t0"] <= w["start"] < b["t1"]]
        b["wpm"] = (len(in_win) / (in_win[-1]["start"] - in_win[0]["end"] + (in_win[-1]["end"] - in_win[0]["start"])) * 60
                    if len(in_win) >= 2 and in_win[-1]["end"] > in_win[0]["start"] else 0)
        # pause before this beat (gap from previous beat's last word)
        if i > 0:
            prev_win = [w for w in clean if beats[i-1]["t0"] <= w["start"] < beats[i-1]["t1"]]
            b["pause_before"] = round(in_win[0]["start"] - prev_win[-1]["end"], 2) if in_win and prev_win else 0
        else:
            b["pause_before"] = 0
        b["laugh_near"] = any("laugh_near=True" in (s.get("comedy") or {}).get("note", "")
                              or s.get("comedy", {}).get("beat_type") in ("punchline", "closer")
                              for s in gt["segments"]
                              if max(0, min(b["t1"], s["t1"]) - max(b["t0"], s["t0"])) > 0)
    baseline_wpm = sum(b["wpm"] for b in beats) / max(len(beats), 1)
    for b in beats:
        b["wpm_dev"] = round(b["wpm"] - baseline_wpm, 1)

    state = {"segments": [{"id": f"s{b['i']}", "text": b["text"],
                           "note": f"pause_before={b['pause_before']}s wpm_dev={b['wpm_dev']}"} for b in beats],
             "task": "tag each beat with comedy-theory labels"}
    qs = {}
    for b in beats:
        sid = f"s{b['i']}"
        qs[f"{sid}_gp"] = {"type": "noul",
            "instructions": f"Is {sid} a garden-path step (leading the audience toward an expected conclusion that will be subverted)?",
            "criteria": {"true": "sets up an expectation deliberately", "false": "states or resolves without setting a trap"}}
        qs[f"{sid}_ic"] = {"type": "noul",
            "instructions": f"Does {sid} contain identity contradiction (the speaker's behavior contradicts who they claim to be)?",
            "criteria": {"true": "self-undercutting, hypocrisy, character collision", "false": "consistent with stated persona"}}
        qs[f"{sid}_surp"] = {"type": "score",
            "instructions": f"How semantically surprising is {sid} given the previous segments?",
            "criteria": ["expected continuation", "mild deviation", "notable twist", "sharp violation"]}
        qs[f"{sid}_esc"] = {"type": "noul",
            "instructions": f"Does {sid} escalate (raise stakes/intensity) from what came before?",
            "criteria": {"true": "bigger, worse, or more extreme", "false": "flat or resolving"}}
    t0 = time.time()
    res = decide(state, qs)
    answers = res.get("answers", {})
    cost = res.get("usage", {}).get("cost", 0)
    print(f"{setname}: {len(beats)} beats, {len(qs)} tags, ${cost:.6f}")

    rows = []
    for b in beats:
        sid = f"s{b['i']}"
        row = {"seg": sid, "text": b["text"][:70],
               "garden_path": (answers.get(f"{sid}_gp") or {}).get("noul", 0),
               "identity_contradiction": (answers.get(f"{sid}_ic") or {}).get("noul", 0),
               "surprise": (answers.get(f"{sid}_surp") or {}).get("score", 1),
               "escalation": (answers.get(f"{sid}_esc") or {}).get("noul", 0),
               "pause_before": b["pause_before"], "wpm_dev": b["wpm_dev"],
               "laugh_near": b["laugh_near"]}
        rows.append(row)
        print(f"  {sid} gp={row['garden_path']:.2f} ic={row['identity_contradiction']:.2f} "
              f"surp={row['surprise']:.1f} esc={row['escalation']:.2f} "
              f"pause={row['pause_before']}s dev={row['wpm_dev']:+.0f} "
              f"{'LAUGH' if row['laugh_near'] else ''}")

    # correlate tags with laugh proximity
    import statistics as st
    corr = {}
    laugh_rows = [r for r in rows if r["laugh_near"]]
    quiet_rows = [r for r in rows if not r["laugh_near"]]
    for key in ("garden_path", "identity_contradiction", "surprise", "escalation", "pause_before", "wpm_dev"):
        lv = [r[key] for r in laugh_rows]
        qv = [r[key] for r in quiet_rows]
        if lv and qv:
            corr[key] = {"laugh_mean": round(st.mean(lv), 2), "quiet_mean": round(st.mean(qv), 2),
                         "lift": round(st.mean(lv) - st.mean(qv), 2)}
    print(f"\nlaugh vs quiet (n={len(laugh_rows)}/{len(quiet_rows)}):")
    for k, v in corr.items():
        print(f"  {k:22} laugh={v['laugh_mean']} quiet={v['quiet_mean']} lift={v['lift']:+}")
    doc = {"set": setname, "cost_usd": cost, "rows": rows, "laugh_correlations": corr,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"theory_tags_{setname}.json").write_text(json.dumps(doc, indent=2))
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    args = ap.parse_args()
    tag_set(args.set)
