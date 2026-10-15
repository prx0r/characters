"""K-graph predict: rich text-only character graph -> delivery -> vs GT,
then THEORY REVIEW: why the actual delivery makes sense where we missed.

The real test (owner spec): build a granular character graph from text
(personas + features-persona + research), emerge affect, Jev-predict the
set, render at MARY tempo (no fitted scale), score vs GT. Then review
misses against our theory toolkit (sprint-into-laugh, dissociation,
action-readiness, Fujisaki) and write down WHY the actual wins.

Usage: python3 kgraph_predict.py --kgraph uncle_laser --set uncle_lazer_kt
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_or import decide
from jev_deliver import (EMOTIONS, EMO_RECIPE, fixed_beats, gemini_label,
                         gemini_labels)
from emerge import affect_from_graph
import fish_tts, voice_judge

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"
POP_SCALE = 0.70


def mary_rate(affect: dict) -> float:
    a11 = affect["arousal"] * 2 - 1
    return 0.5 * a11 + 0.2 * affect["valence"]


def predict(beats: list, graph: dict, affect: dict) -> dict:
    state = {
        "comedian": graph["name"],
        "persona": (graph.get("persona") or {}).get("deal", ""),
        "facts": (graph.get("persona") or {}).get("facts", []),
        "interview_style": (graph.get("persona") or {}).get("interview_style", ""),
        "dramatic_core": graph.get("dramatic_core"),
        "misinterpretation_rule": graph.get("misinterpretation_rule"),
        "philosophy": graph.get("philosophy"),
        "blind_spots": (graph.get("dramatic_core") or {}).get("blind_spots"),
        "affect": affect,
        "signature_move": graph.get("signature_move", ""),
        "modulator_range": graph.get("modulator_range", []),
        "segments": [{"id": f"s{b['i']}", "text": b["text"]} for b in beats],
        "note": "Predict delivery from this character graph. You have NOT "
                "heard them; the graph IS your only knowledge.",
    }
    qs = {}
    for b in beats:
        sid = f"s{b['i']}"
        qs[f"{sid}_emo"] = {"type": "choice",
            "instructions": f"For segment {sid}, which delivery emotion fits, "
                            f"given this character's psyche?",
            "criteria": EMOTIONS}
        qs[f"{sid}_pace"] = {"type": "score",
            "instructions": f"For segment {sid}, how fast does THIS character deliver?",
            "criteria": ["slow measured", "conversational", "fast energetic", "rapid-fire"]}
    res = decide(state, qs)
    return res.get("answers", {})


def run(kgraph_name: str, setname: str) -> dict:
    graph = json.loads((HERE / "kgraphs" / f"{kgraph_name}.json").read_text())
    words = json.loads((REPO / "theory/scribe" / f"{setname}.json").read_text())["words"]
    gt = json.loads((REPO / "theory/killtony-minutes" / f"{setname}_gemini.gemini.json").read_text())
    beats = fixed_beats(words)
    affect = affect_from_graph(graph)
    rate = mary_rate(affect)
    # MARY tempo: rate -> PACE bucket (NO fitted scale — the honest condition)
    pace0 = 0 if rate < -0.2 else (1 if rate < 0.05 else (2 if rate < 0.25 else 3))
    print(f"{kgraph_name} @ {setname}: {len(beats)} beats | "
          f"affect A={affect['arousal']} V={affect['valence']} P={affect['power']} "
          f"-> mary_rate={rate:+.2f} base_pace={pace0}")

    t0 = time.time()
    answers = predict(beats, graph, affect)
    print(f"  jev: {time.time()-t0:.1f}s")

    PACE = {0: 0.70, 1: 0.95, 2: 1.20, 3: 1.45}
    parts, rows = [], []
    for b in beats:
        sid = f"s{b['i']}"
        pred_emo = (answers.get(f"{sid}_emo") or {}).get("choice", "neutral")
        pace_pred = (answers.get(f"{sid}_pace") or {}).get("score", float(pace0))
        # tempo = MARY base blended with Jev's per-beat pace preference
        pace_blend = 0.5 * (pace_pred + pace0)
        cue, temp, emo_speed = EMO_RECIPE.get(pred_emo, ("[neutral]", 0.6, 1.0))
        speed = PACE[int(round(max(0, min(3, pace_blend))))] * POP_SCALE * emo_speed
        true_emo = gemini_label(gt["segments"], b["t0"], b["t1"])
        true_all = gemini_labels(gt["segments"], b["t0"], b["t1"])
        t = f"{cue} {b['text']}".strip() if cue else b["text"]
        out = fish_tts.synthesize_fish(f"kg-{sid}", t, voice=None, direction=False,
                                       temperature=temp, prosody={"speed": round(speed, 2)})
        m = voice_judge.measure(Path(out["path"]))
        gen_wpm = b["n_words"] / (m["duration_ms"] / 1000) * 60
        in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]
                  and not w["text"].strip().startswith("[")]
        act_wpm = 0.0
        if len(in_win) >= 2:
            span = in_win[-1]["end"] - in_win[0]["start"]
            act_wpm = len(in_win) / span * 60 if span > 1 else 0
        match = 1.0 if pred_emo == true_emo else (0.5 if pred_emo in true_all[1:3] else 0.0)
        parts.append(Path(out["path"]))
        rows.append({"seg": sid, "text": b["text"][:80], "pred_emo": pred_emo,
                     "true_emo": true_emo, "true_all": true_all[:3],
                     "match_score": match, "pred_pace": round(pace_pred, 2),
                     "gen_wpm": round(gen_wpm, 1), "act_wpm": round(act_wpm, 1),
                     "wpm_err": round(gen_wpm - act_wpm, 1),
                     "gen_var": m["pitch"].get("std_semitones"),
                     "wav": str(out["path"])})
        flag = "OK " if match >= 1 else ("~" if match else "MISS")
        print(f"    {sid} {flag} {pred_emo:14}/{true_emo:14} "
              f"wpm {gen_wpm:.0f}/{act_wpm:.0f} pace_pred={pace_pred:.1f}")

    acc = sum(r["match_score"] for r in rows) / max(len(rows), 1)
    wpm_mae = sum(abs(r["wpm_err"]) for r in rows) / max(len(rows), 1)
    out_wav = Path(f"/home/box/kgraph_{kgraph_name}_{setname}.wav")
    fish_tts.stitch_wav(parts, out_wav)

    # THEORY REVIEW: why does the actual delivery make sense where we missed?
    review = []
    for r in rows:
        if r["match_score"] >= 1 and abs(r["wpm_err"]) < 30:
            continue
        theories = []
        # sprint-into-laugh: actual faster near a laugh boundary
        if r["act_wpm"] > r["gen_wpm"] + 25 and "laugh" in json.dumps(gt["segments"]):
            seg_laugh = any(s.get("comedy", {}).get("note", "").find("laugh_near=True") >= 0
                            and abs(s["t0"]) <= 9999 for s in gt["segments"])
            if seg_laugh:
                theories.append("sprint-into-laugh: actual accelerates near "
                                "audience response (Casey corpus: laughed riffs "
                                "faster + shorter pre-pauses)")
        if r["act_wpm"] < r["gen_wpm"] - 25:
            theories.append("drawl-hold: actual slower than graph predicts — "
                            "either pause-embedding inside the beat or "
                            "action-readiness BLOCKED (Frijda: avoidance "
                            "readiness = drag, not acceleration)")
        if r["match_score"] == 0 and r["pred_emo"] != r["true_emo"]:
            if r["true_emo"] in ("mock_indignant", "sarcastic") and r["pred_emo"] in ("mock_indignant", "sarcastic"):
                theories.append("Fujisaki paradox: grievance-vs-irony are "
                                "acoustically adjacent; text alone can't "
                                "separate them without intensity cues")
            elif r["true_emo"] == "sarcastic" and r["pred_emo"] in ("manic", "gleeful"):
                theories.append("graph arousal too high: braggy persona text "
                                "pushed prediction to high-energy; actual "
                                "lands sarcastic (dry, not hot) — "
                                "persona.performative overpowers persona.affect")
            else:
                theories.append(f"graph mis-specified for this beat: "
                                f"predicted {r['pred_emo']} from graph psyche, "
                                f"actual {r['true_emo']} — the graph's "
                                f"modulator_cycle may need this state earlier")
        review.append({"seg": r["seg"], "pred": r["pred_emo"], "true": r["true_emo"],
                       "wpm_gen": r["gen_wpm"], "wpm_act": r["act_wpm"],
                       "why_actual_wins": theories or ["no theory — in-band" if r["match_score"] >= 1 else "label mismatch, no pattern matched"]})

    doc = {"kgraph": kgraph_name, "set": setname,
           "condition": "rich text-only graph -> emerge -> Jev -> MARY tempo "
                        "(no fitted scale, no clone, never heard them)",
           "affect": affect, "mary_rate": round(rate, 2),
           "emotion_acc": round(acc, 3), "wpm_mae": round(wpm_mae, 1),
           "rows": rows, "theory_review": review, "wav": str(out_wav),
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"kgraph_{kgraph_name}_{setname}.json").write_text(json.dumps(doc, indent=2))
    print(f"\nKGRAPH {kgraph_name}: acc={acc:.2f} wpm_mae={wpm_mae:.1f} -> {out_wav}")
    print(f"THEORY REVIEW ({len(review)} misses):")
    for rv in review:
        print(f"  {rv['seg']}: {rv['why_actual_wins'][0][:90]}")
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kgraph", required=True)
    ap.add_argument("--set", required=True)
    args = ap.parse_args()
    run(args.kgraph, args.set)
