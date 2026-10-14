"""Jev delivery decoder: transcript -> predicted delivery -> render -> compare.

Per-comedian calibration state machine (SPEC-JEV-DELIVERY).
First test: kt704 (ari). Honest split: fixed 15s beats (no timing leak).
Jev predicts per-beat emotion/pace/energy from text + profile + error
history. Label accuracy vs gemini ground truth = first falsifiable target.

Usage: python3 jev_deliver.py decode --set kt704_passport [--render]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_or import decide

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"

EMOTIONS = {
    "manic": "fast kinetic, high energy, wide pitch swings",
    "gleeful": "bright amused energy, smiling voice",
    "deadpan": "flat affect, minimal pitch movement, dry",
    "sarcastic": "dry mocking, ironic emphasis",
    "mock_indignant": "spiky offense, grievance energy rising to anger",
    "neutral": "baseline observational",
    "defiant": "pushing back, controlled intensity",
    "embarrassed": "awkward warmth, self-conscious",
}

# emotion -> engine recipe (from calibrate/ + domains/)
EMO_RECIPE = {
    "manic":         ("[excited]", 0.85),
    "gleeful":       ("[delighted]", 0.80),
    "deadpan":       ("", 0.45),
    "sarcastic":     ("[sarcastic]", 0.65),
    "mock_indignant": ("[frustrated]", 0.85),
    "neutral":       ("[neutral]", 0.60),
    "defiant":       ("[frustrated]", 0.80),
    "embarrassed":   ("[embarrassed]", 0.70),
}


def load_set(setname: str):
    scribe = json.loads((REPO / "theory/scribe" / f"{setname}.json").read_text())
    words = scribe["words"]
    # find gemini for ground truth
    d = REPO / "theory/killtony-minutes"
    gpath = None
    for c in (d / f"{setname}_gemini.gemini.json",
              d / "kt704_ari_passport_gemini.gemini.json" if setname.startswith("kt704") else None):
        if c and c.exists():
            gpath = c
            break
    gem = json.loads(gpath.read_text()) if gpath else {"segments": []}
    return words, gem.get("segments") or []


def fixed_beats(words, beat_s: float = 15.0):
    """Honest segmentation: fixed-length windows, no timing leak.
    Strips [laughing]/[censored] annotation tokens — they inflate word
    counts (real audio includes crowd time; TTS skips the tokens)."""
    import re
    if not words:
        return []
    clean = [w for w in words if not w["text"].strip().startswith("[")]
    if not clean:
        return []
    t0, t1 = clean[0]["start"], clean[-1]["end"]
    beats = []
    t = t0
    while t < t1:
        ws = [w for w in clean if t <= w["start"] < t + beat_s]
        if len(ws) >= 5:
            text = " ".join(w["text"] for w in ws)
            beats.append({"i": len(beats), "t0": round(t, 1),
                          "t1": round(min(t + beat_s, t1), 1),
                          "text": " ".join(text.split()),
                          "n_words": len(ws),
                          "real_wpm": round(len(ws) / beat_s * 60, 1)})
        t += beat_s
    return beats


def gemini_label(segments, t0, t1):
    """Ground-truth emotion for a beat = majority-overlap gemini segment."""
    best, best_ov = None, 0.0
    for s in segments:
        ov = max(0.0, min(t1, s["t1"]) - max(t0, s["t0"]))
        if ov > best_ov:
            best_ov, best = ov, (s.get("emotion") or "neutral").lower()
    return best or "neutral"


def summarize_errors(errors: list) -> dict:
    """Compress raw errors into low-dim bias terms (PersonalAlign/LoRe
    insight: raw replay overfits; summaries generalize)."""
    if not errors:
        return {}
    confusions = {}
    wpm_by_pred = {}
    for e in errors:
        if not e.get("match", True) if "match" in e else e.get("pred_emo") != e.get("true_emo"):
            key = e.get("pred_emo") or e.get("pred")
            true = e.get("true_emo") or e.get("true")
            if key and true:
                confusions.setdefault(key, {})
                confusions[key][true] = confusions[key].get(true, 0) + 1
        pe = e.get("pred_emo") or e.get("pred")
        if pe and "wpm_err" in e:
            wpm_by_pred.setdefault(pe, []).append(e["wpm_err"])
    wpm_bias = {k: round(sum(v) / len(v)) for k, v in wpm_by_pred.items()}
    return {"confusion_biases": confusions, "wpm_bias_by_predicted_emotion": wpm_bias,
            "n_errors": len(errors),
            "guidance": "When you predict an emotion listed in confusion_biases, "
                        "consider whether its most common actual label fits better. "
                        "wpm_bias tells you how your pace predictions skew per emotion."}


def build_state(profile: dict, beats: list, errors: list | None = None) -> dict:
    state = {
        "comedian": profile["name"],
        "persona": profile.get("persona_note", ""),
        "delivery_history_note": profile.get("delivery_note", ""),
        "affect": profile.get("affect", {}),
        "segments": [{"id": f"s{b['i']}", "text": b["text"]} for b in beats],
    }
    if errors:
        state["calibration"] = summarize_errors(errors)
    return state


def questions_for(beats: list) -> dict:
    """Per-beat: emotion choice + pace score. One parallel call."""
    qs = {}
    for b in beats:
        sid = f"s{b['i']}"
        qs[f"{sid}_emo"] = {
            "type": "choice",
            "instructions": f"For segment {sid}, which delivery emotion fits the text?",
            "criteria": EMOTIONS,
        }
        qs[f"{sid}_pace"] = {
            "type": "score",
            "instructions": f"For segment {sid}, how fast should it be delivered?",
            "criteria": ["slow measured", "conversational", "fast energetic", "rapid-fire"],
        }
    return qs


def decode(setname: str, profile: dict, errors: list | None = None, render: bool = False):
    words, gem = load_set(setname)
    beats = fixed_beats(words)
    print(f"{setname}: {len(words)} words -> {len(beats)} fixed beats, "
          f"{len(gem)} gemini segments (ground truth)")
    state = build_state(profile, beats, errors)
    qs = questions_for(beats)
    t0 = time.time()
    res = decide(state, qs)
    elapsed = time.time() - t0
    answers = res.get("answers", {})
    cost = res.get("usage", {}).get("cost", 0)
    print(f"jev: {len(qs)} questions, {elapsed:.1f}s, ${cost:.6f}")

    # compare vs gemini ground truth
    results, correct, total = [], 0, 0
    for b in beats:
        sid = f"s{b['i']}"
        pred_emo = (answers.get(f"{sid}_emo") or {}).get("choice", "neutral")
        pred_conf = (answers.get(f"{sid}_emo") or {}).get("confidence", 0)
        pred_pace = (answers.get(f"{sid}_pace") or {}).get("score", 1)
        true_emo = gemini_label(gem, b["t0"], b["t1"])
        match = pred_emo == true_emo
        correct += match
        total += 1
        results.append({"seg": sid, "text": b["text"][:60],
                        "pred_emo": pred_emo, "true_emo": true_emo,
                        "match": match, "conf": round(pred_conf, 2),
                        "pred_pace": round(pred_pace, 2),
                        "real_wpm": b["real_wpm"]})
        flag = "OK " if match else "MISS"
        print(f"  {sid} {flag} pred={pred_emo:14} true={true_emo:14} "
              f"conf={pred_conf:.2f} pace={pred_pace:.1f} real_wpm={b['real_wpm']:.0f}")

    acc = correct / max(total, 1)
    # majority-class baseline
    from collections import Counter
    true_counts = Counter(r["true_emo"] for r in results)
    base = true_counts.most_common(1)[0][1] / max(total, 1)
    print(f"\nemotion accuracy: {acc:.2f} (baseline majority: {base:.2f}, "
          f"target >0.60) {'BEATS BASELINE' if acc > base else 'AT/BELOW BASELINE'}")
    print(f"cost: ${cost:.6f}")

    out = {"set": setname, "beats": len(beats), "accuracy": round(acc, 3),
           "baseline": round(base, 3), "beats_baseline": acc > base,
           "cost_usd": cost, "elapsed_s": round(elapsed, 1),
           "results": results, "answers_raw": answers,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"jev_decode_{setname}.json").write_text(json.dumps(out, indent=2))
    return out


ARI_PROFILE = {
    "name": "ari_matti",
    "persona_note": "Estonian professional immigrant; grievance-velocity comedian; "
                    "spikes from sarcastic setups into mock-indignant rage, gleeful collapses",
    "delivery_note": "fast (200+wpm spikes), cue ladder frustrated->angry, temp .85, "
                     "sprints INTO laughs, wide pitch var 4.2-5.5st",
    "affect": {"arousal": 0.85, "valence": -0.3, "power": 0.8},
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="kt704_passport")
    ap.add_argument("--render", action="store_true")
    args = ap.parse_args()
    decode(args.set, ARI_PROFILE, render=args.render)
