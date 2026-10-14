"""Jev->Fish bridge + per-comedian calibration loop (SPEC-JEV-DELIVERY).

Loop per set: decode (Jev: transcript -> emotion+pace per beat) -> render
(fish free tier, clone voice) -> compare (rendered vs actual slice, per-metric)
-> calibrate (errors into state) -> repeat until bounds:
  emotion acc > 0.60 | wpm MAE < 20 | pitch-var MAE < 1.5 st
Held-out test after convergence: decode unseen set with converged state.

Usage:
  python3 jev_loop.py run --set kt704_passport --rounds 3
  python3 jev_loop.py heldout --calibrated kt704_passport --set kt715_ep715
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jev_or import decide
from jev_deliver import (EMOTIONS, EMO_RECIPE, load_set, fixed_beats,
                         gemini_label, build_state, questions_for, ARI_PROFILE)
import fish_tts, voice_judge

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
CLONE = "dbeb1d68566245e2b857617b830e8031"  # ari clone
CLIPS = {
    "kt704_passport": "/home/box/ari_matti_sets/shorts/kt704_passport_short.mp4",
    "kt715_ep715": "/home/box/ari_matti_sets/shorts/kt715_ep715_clip.mp4",
    "kt715_walking": "/home/box/ari_matti_sets/shorts/kt715_walking_short.mp4",
    "kt728_diversifying": "/home/box/ari_matti_sets/shorts/kt728_diversifying_short.mp4",
    "kt728_jamesbond": "/home/box/ari_matti_sets/shorts/kt728_jamesbond_short.mp4",
}
BASE_WPM = 154.3  # ari-clone base probe, speed 1.0

# pace score (0-3 ordered scale) -> fish speed multiplier
PACE_SPEED = {0: 0.70, 1: 0.95, 2: 1.20, 3: 1.45}


def slice_actual(setname: str, t0: float, t1: float) -> Path:
    out = Path(f"/tmp/opencode/_act_{setname}_{t0:.0f}.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", CLIPS[setname],
                    "-ss", str(t0), "-t", str(t1 - t0),
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out)],
                   check=True, capture_output=True, timeout=60)
    return out


def render_pred(setname: str, round_i: int, beat: dict, emo: str,
                pace_score: float, speed_scale: float = 1.0) -> Path:
    """Jev prediction -> fish render (clone voice)."""
    cue, temp = EMO_RECIPE.get(emo, ("[neutral]", 0.6))
    bucket = int(round(max(0, min(3, pace_score))))
    speed = max(0.5, min(2.0, PACE_SPEED[bucket] * speed_scale))
    text = f"{cue} {beat['text']}".strip() if cue else beat["text"]
    r = fish_tts.synthesize_fish(
        f"jl-{setname}-r{round_i}-{beat['i']}", text, voice=CLONE,
        direction=False, temperature=temp,
        prosody={"speed": speed, "volume": 0.0})
    return Path(r["path"])


def measure_wpm_var(path: Path, n_words: int) -> dict:
    m = voice_judge.measure(path)
    dur = m["duration_ms"] / 1000
    return {"wpm": round(n_words / dur * 60, 1) if dur else 0,
            "var_st": round(m["pitch"].get("std_semitones") or 0, 2)}


def run_round(setname: str, round_i: int, errors: list, profile: dict,
               speed_scale: float = 1.0) -> dict:
    import re
    words_all, gem = load_set(setname)
    words = [w for w in words_all if not w["text"].strip().startswith("[")]
    beats = fixed_beats(words_all)
    state = build_state(profile, beats, errors)
    qs = questions_for(beats)
    res = decide(state, qs)
    answers = res.get("answers", {})
    cost = res.get("usage", {}).get("cost", 0)

    rows, new_errors = [], []
    for b in beats:
        sid = f"s{b['i']}"
        pred_emo = (answers.get(f"{sid}_emo") or {}).get("choice", "neutral")
        pace = (answers.get(f"{sid}_pace") or {}).get("score", 1.5)
        true_emo = gemini_label(gem, b["t0"], b["t1"])
        wav = render_pred(setname, round_i, b, pred_emo, pace, speed_scale)
        gen = measure_wpm_var(wav, b["n_words"])
        # actual: speech-span wpm from word timings (crowd time excluded)
        in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]]
        act_wpm = 0.0
        if len(in_win) >= 2:
            span = in_win[-1]["end"] - in_win[0]["start"]
            act_wpm = round(len(in_win) / span * 60, 1) if span > 1 else 0.0
        act_wav = slice_actual(setname, b["t0"], b["t1"])
        act_var = measure_wpm_var(act_wav, max(b["n_words"], 1))["var_st"]
        wpm_err = round(gen["wpm"] - act_wpm, 1)
        var_err = round(gen["var_st"] - act_var, 2)
        row = {"seg": sid, "pred_emo": pred_emo, "true_emo": true_emo,
               "match": pred_emo == true_emo, "pace": round(pace, 2),
               "gen_wpm": gen["wpm"], "act_wpm": act_wpm, "wpm_err": wpm_err,
               "gen_var": gen["var_st"], "act_var": act_var, "var_err": var_err,
               "wav": str(wav)}
        rows.append(row)
        new_errors.append({"seg": sid, "pred_emo": pred_emo, "true_emo": true_emo,
                           "pace": round(pace, 2), "wpm_err": wpm_err,
                           "var_err": var_err,
                           "note": f"pred {pred_emo}/pace{pace:.1f}; actual {true_emo} "
                                   f"wpm {act_wpm} var {act_var}; gen was {gen['wpm']}/{gen['var_st']}"})

    n = max(len(rows), 1)
    acc = sum(r["match"] for r in rows) / n
    wpm_mae = sum(abs(r["wpm_err"]) for r in rows) / n
    var_mae = sum(abs(r["var_err"]) for r in rows) / n
    summary = {"round": round_i, "emotion_acc": round(acc, 3),
               "wpm_mae": round(wpm_mae, 1), "var_mae": round(var_mae, 2),
               "cost_usd": cost, "rows": rows}
    print(f"  R{round_i}: acc={acc:.2f} wpm_mae={wpm_mae:.1f} var_mae={var_mae:.2f} "
          f"cost=${cost:.6f}")
    for r in rows:
        flag = "OK " if r["match"] else "MISS"
        print(f"    {r['seg']} {flag} {r['pred_emo']:14}/{r['true_emo']:14} "
              f"wpm {r['gen_wpm']:.0f}/{r['act_wpm']:.0f} ({r['wpm_err']:+.0f}) "
              f"var {r['gen_var']:.1f}/{r['act_var']:.1f}")
    return summary, new_errors


BOUNDS = {"emotion_acc": 0.60, "wpm_mae": 20.0, "var_mae": 1.5}


def converged(s: dict) -> bool:
    return (s["emotion_acc"] >= BOUNDS["emotion_acc"]
            and s["wpm_mae"] <= BOUNDS["wpm_mae"]
            and s["var_mae"] <= BOUNDS["var_mae"])


def run(setname: str, rounds: int = 3, profile: dict | None = None) -> dict:
    profile = profile or ARI_PROFILE
    errors: list = []
    history = []
    speed_scale = 1.0
    for r in range(1, rounds + 1):
        summary, new_errors = run_round(setname, r, errors, profile, speed_scale)
        # empirical tempo calibration: geometric mean of act/gen wpm ratio
        ratios = [r_["act_wpm"] / max(r_["gen_wpm"], 1) for r_ in summary["rows"]
                   if r_["gen_wpm"] > 50 and r_["act_wpm"] > 50]
        if ratios:
            import math
            g = math.exp(sum(math.log(x) for x in ratios) / len(ratios))
            speed_scale = round(max(0.4, min(2.5, speed_scale * g)), 3)
            summary["speed_scale"] = speed_scale
            print(f"    -> speed_scale now {speed_scale} (from ratios "
                  f"{[round(x,2) for x in ratios]})")
        history.append(summary)
        errors.extend(new_errors)
        if converged(summary):
            print(f"  CONVERGED at round {r}")
            break
    doc = {"set": setname, "clone": CLONE, "bounds": BOUNDS,
           "history": history, "errors": errors,
           "converged": converged(history[-1]) if history else False,
           "note": "Jev transcript->delivery->fish->vs actual; same clone voice",
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"jev_loop_{setname}.json").write_text(json.dumps(doc, indent=2))
    print(f"-> voicelab/jev_loop_{setname}.json "
          f"({'CONVERGED' if doc['converged'] else 'not converged'})")
    return doc


def heldout(calibrated_set: str, test_set: str) -> dict:
    """Feed converged error history into decode of an UNSEEN set."""
    doc = json.loads((LAB / f"jev_loop_{calibrated_set}.json").read_text())
    errors = doc["errors"]
    words, gem = load_set(test_set)
    beats = fixed_beats(words)
    state = build_state(ARI_PROFILE, beats, errors[-20:])
    res = decide(state, questions_for(beats))
    answers = res.get("answers", {})
    rows = []
    for b in beats:
        sid = f"s{b['i']}"
        pred = (answers.get(f"{sid}_emo") or {}).get("choice", "neutral")
        true = gemini_label(gem, b["t0"], b["t1"])
        rows.append({"seg": sid, "pred": pred, "true": true, "match": pred == true})
    acc = sum(r["match"] for r in rows) / max(len(rows), 1)
    print(f"HELD-OUT {test_set} (state from {calibrated_set}): "
          f"acc={acc:.2f} over {len(rows)} beats")
    for r in rows:
        print(f"  {r['seg']} {'OK ' if r['match'] else 'MISS'} {r['pred']:14}/{r['true']}")
    out = {"calibrated_on": calibrated_set, "tested": test_set,
           "accuracy": round(acc, 3), "rows": rows,
           "errors_used": len(errors),
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"jev_heldout_{test_set}.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--set", default="kt704_passport")
    r.add_argument("--rounds", type=int, default=3)
    h = sub.add_parser("heldout")
    h.add_argument("--calibrated", default="kt704_passport")
    h.add_argument("--set", required=True)
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.set, args.rounds)
    elif args.cmd == "heldout":
        heldout(args.calibrated, args.set)
