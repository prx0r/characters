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
                         gemini_label, gemini_labels, build_state,
                         questions_for, ARI_PROFILE)
import fish_tts, voice_judge

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
CLONE = "dbeb1d68566245e2b857617b830e8031"  # ari clone
CLIPS = {
    "kt704_passport": "/home/box/ari_matti_sets/shorts/kt704_passport_short.mp4",
    "kt715_ep715": "/home/box/ari_matti_sets/shorts/kt715_ep715_clip.mp4",
    "kt715_walking": "/home/box/ari_matti_sets/shorts/kt715_walking_short.mp4",
    "kt715_nashville": "/home/box/ari_matti_sets/shorts/kt715_nashville_short.mp4",
    "kt728_diversifying": "/home/box/ari_matti_sets/shorts/kt728_diversifying_short.mp4",
    "kt728_jamesbond": "/home/box/ari_matti_sets/shorts/kt728_jamesbond_short.mp4",
    "casey_rocket_1": "/home/box/comedy_sets/shorts/casey_rocket_1.mp4",
    "casey_rocket_2": "/home/box/comedy_sets/shorts/casey_rocket_2.mp4",
    "louis_roadrage": "/home/box/louis_sets/louis_roadrage.m4a",
    "norm_moth": "/home/box/norm_sets/norm_joke_trim.wav",
    "will_montgomery_1": "/home/box/comedy_sets/shorts/will_montgomery_1.mp4",
    "kam_patterson_1": "/home/box/comedy_sets/shorts/kam_patterson_1.mp4",
    "kam_patterson_2": "/home/box/comedy_sets/shorts/kam_patterson_2.mp4",
    "sir_winston_pickles_1": "/home/box/comedy_sets/shorts/sir_winston_pickles_1.mp4",
    "sir_winston_pickles_2": "/home/box/comedy_sets/shorts/sir_winston_pickles_2.mp4",
}
_extra = HERE / "voicelab" / "extra_clips.json"
if _extra.exists():
    CLIPS.update(json.loads(_extra.read_text()))
CLONES = {"ari": "dbeb1d68566245e2b857617b830e8031",
          "casey": "9c36c951cee84457a5cc9f94387e9a42",
          "pickles": "100e10e7c5464a10b5120a01ade115a2",
          "louis": "fb015415ebf141999fc882baa0e0834c",
          "norm": "085d639799cc449c8a5350fe8543c14b",
          "will": "9c1e219466b84e448976d5f163d3d9fc",
          "kam": "6ab05a976a684ea49798183783cbd3f9",
          "seinfeld": "f73820b82341447daa943f59ae414415"}
SET_PERFORMER = {"kt704_passport": "ari", "kt715_ep715": "ari", "kt715_walking": "ari",
                 "kt715_nashville": "ari", "kt728_diversifying": "ari", "kt728_jamesbond": "ari",
                 "casey_rocket_1": "casey", "casey_rocket_2": "casey",
                 "louis_roadrage": "louis", "norm_moth": "norm",
                 "will_montgomery_1": "will", "kam_patterson_1": "kam",
                 "kam_patterson_2": "kam",
                 "sir_winston_pickles_1": "pickles", "sir_winston_pickles_2": "pickles",
                 "seinfeld_c01": "seinfeld", "seinfeld_c02": "seinfeld", "seinfeld_c03": "seinfeld", "seinfeld_c04": "seinfeld", "seinfeld_c05": "seinfeld"}
BASE_WPM = 154.3  # per-performer probe override in run()
CLONE = CLONES["ari"]

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
    cue, temp, emo_speed = EMO_RECIPE.get(emo, ("[neutral]", 0.6, 1.0))
    bucket = int(round(max(0, min(3, pace_score))))
    speed = max(0.5, min(2.0, PACE_SPEED[bucket] * speed_scale * emo_speed))
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
               speed_scale: float = 1.0, beat_scales: dict | None = None) -> dict:
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
        true_all = gemini_labels(gem, b["t0"], b["t1"])
        match = 1.0 if pred_emo == true_emo else (
            0.5 if pred_emo in true_all[1:3] else 0.0)
        bscale = (beat_scales or {}).get(sid, 1.0)
        wav = render_pred(setname, round_i, b, pred_emo, pace,
                          speed_scale * bscale)
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
               "match": pred_emo == true_emo, "match_score": match,
               "true_all": true_all[:3], "pace": round(pace, 2),
               "gen_wpm": gen["wpm"], "act_wpm": act_wpm, "wpm_err": wpm_err,
               "gen_var": gen["var_st"], "act_var": act_var, "var_err": var_err,
               "wav": str(wav)}
        rows.append(row)
        if beat_scales is not None and gen["wpm"] > 40 and act_wpm > 40:
            import math
            ratio = act_wpm / gen["wpm"]
            ratio = max(0.5, min(2.0, ratio))
            old = beat_scales.get(sid, 1.0)
            beat_scales[sid] = round(old * (ratio ** 0.7), 3)  # damped
        new_errors.append({"seg": sid, "pred_emo": pred_emo, "true_emo": true_emo,
                           "pace": round(pace, 2), "wpm_err": wpm_err,
                           "var_err": var_err,
                           "note": f"pred {pred_emo}/pace{pace:.1f}; actual {true_emo} "
                                   f"wpm {act_wpm} var {act_var}; gen was {gen['wpm']}/{gen['var_st']}"})

    n = max(len(rows), 1)
    acc = sum(r.get("match_score", 1.0 if r["match"] else 0.0) for r in rows) / n
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



PROFILES = {
    "ari": ARI_PROFILE,
    "casey": {
        "name": "casey_rocket",
        "persona_note": "Kinetic manic-deadpan swinger; rapid-fire surreal bursts "
                        "then flat drops; physical chaos as punctuation; self-aware absurdism",
        "delivery_note": "manic [excited]; deadpan no-cue low temp; huge tempo deltas "
                         "(deadpan ~135wpm vs manic ~360wpm); laughed riffs FASTER",
        "affect": {"arousal": 0.8, "valence": 0.3, "power": 0.6},
    },
    "louis": {
        "name": "louis_ck",
        "persona_note": "Self-deprecating sincere storyteller; raw physical specificity; "
                        "builds to weird dark places; sincerity is the engine; laughs as byproduct",
        "delivery_note": "mid pitch, wide dynamics, build-then-collapse, comfort with silence; "
                         "road-rage window measured ~210wpm fast passages",
        "affect": {"arousal": 0.6, "valence": -0.4, "power": 0.5},
    },
    "norm": {
        "name": "norm_macdonald",
        "persona_note": "Suspension-of-reality deadpan; enters his own world and believes it; "
                        "slow burn, long tangent then snap return; wide pitch swings, flat volume",
        "delivery_note": "moth joke measured 192wpm, pitch_std 10.1 (widest), dyn 13.3 (flat); "
                         "tells it like he's figuring it out live",
        "affect": {"arousal": 0.4, "valence": 0.1, "power": 0.6},
    },
    "will": {
        "name": "william_montgomery",
        "persona_note": "Unhinged scream-comedy chaos agent; violent tonal swings; "
                        "shouts punchlines then collapses into muttering; unhinged intensity",
        "delivery_note": "extreme dynamics; sudden shouts; AM-GT shows mock_indignant/"
                         "gleeful mix; wide variance",
        "affect": {"arousal": 0.9, "valence": -0.2, "power": 0.9},
    },
    "kam": {
        "name": "kam_patterson",
        "persona_note": "Machine-gun crowd-work energy; barrel-through-laughter delivery; "
                        "storyteller who sprints; gleeful agreement with his own premises",
        "delivery_note": "fast (210+ wpm measured), gleeful-dominant AM-GT, "
                         "laughs overlap speech (barrel-through style)",
        "affect": {"arousal": 0.85, "valence": 0.4, "power": 0.7},
    },
    "pickles": {
        "name": "sir_winston_pickles",
        "persona_note": "Absurdist prop-comic gentleman; formal delivery of insanity; "
                        "sponsors a little person; deadpan aristocrat of chaos",
        "delivery_note": "gemini GT available; pickles_1 183wpm measured, "
                         "deadpan-formal register",
        "affect": {"arousal": 0.5, "valence": 0.2, "power": 0.7},
    },
    "seinfeld": {
        "name": "jerry_seinfeld",
        "persona_note": "observational stand-still comic; incredulous everyman; "
                        "tiny-life absurdity with surgical precision; voice-first GOAT",
        "delivery_note": "mid-fast, precise articulation, controlled swings, "
                         "setup-punch-tag discipline; minimal body, maximal phrasing",
        "affect": {"arousal": 0.55, "valence": 0.3, "power": 0.55},
    },
}
BOUNDS = {"emotion_acc": 0.60, "wpm_mae": 20.0, "var_mae": 1.5}


def converged(s: dict) -> bool:
    return (s["emotion_acc"] >= BOUNDS["emotion_acc"]
            and s["wpm_mae"] <= BOUNDS["wpm_mae"]
            and s["var_mae"] <= BOUNDS["var_mae"])


def probe_base(clone: str) -> float:
    r = fish_tts.synthesize_fish("jl-base-probe",
                                 "The quick brown fox jumps over the lazy dog.",
                                 voice=clone, direction=False, temperature=0.6)
    m = voice_judge.measure(Path(r["path"]))
    return round(9 / (m["duration_ms"] / 1000) * 60, 1)


def run(setname: str, rounds: int = 3, profile: dict | None = None) -> dict:
    global CLONE, BASE_WPM
    perf = SET_PERFORMER.get(setname, "ari")
    CLONE = CLONES[perf]
    BASE_WPM = probe_base(CLONE)
    print(f"performer={perf} clone={CLONE[:8]}.. base_wpm={BASE_WPM}")
    profile = profile or PROFILES.get(perf, ARI_PROFILE)
    errors: list = []
    history = []
    speed_scale = 1.0
    beat_scales: dict = {}
    for r in range(1, rounds + 1):
        summary, new_errors = run_round(setname, r, errors, profile, speed_scale,
                                        beat_scales)
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
