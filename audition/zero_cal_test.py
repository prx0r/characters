"""Zero-calibration test: predict delivery from transcript + TEXT profile ONLY.

The true test the owner asked for: can we predict a comedian we've NEVER
heard? Predictor gets: transcript (text), kt-personas.json profile (text),
archetype mapping, MARY affect, POPULATION priors (speed_scale from OTHER
comedians). Never: their audio, error history, per-comedian scale.
Scorer (after prediction) uses their audio for GT + comparison only.

Usage: python3 zero_cal_test.py --set uncle_lazer_kt --comedian uncle_laser
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
import fish_tts, voice_judge

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"

# population priors (learned from OTHER comedians — general, not target's)
POP_SPEED_SCALE = 0.70  # mean of converged performers' scales
POP_CLONE = None        # None = default fish voice (delivery test, not timbre)


def load_personas(comedian: str) -> dict:
    for name in (comedian, comedian.replace("_", "-"),
                 comedian.replace("_", " "), comedian + "s"):
        p = REPO / "theory/killtony-personas" / f"{name}.json"
        if p.exists():
            return json.loads(p.read_text())
    return {}


def text_profile(comedian: str) -> dict:
    """TEXT-ONLY profile: personas json + archetype + MARY. No audio ever."""
    per = load_personas(comedian)
    traits = per.get("traits") or []
    humour = per.get("humour") or ""
    arch = per.get("archetype") or "unknown"
    ops = list(((per.get("comedy") or {}).get("operator_priors") or {}).keys())[:4]
    # archetype -> affect guess (from archetypes.json mapping, text knowledge)
    ARCH_AFFECT = {
        "bisociation": {"arousal": 0.65, "valence": 0.1, "power": 0.6},
        "literalise": {"arousal": 0.55, "valence": 0.0, "power": 0.5},
        "literalize": {"arousal": 0.55, "valence": 0.0, "power": 0.5},
    }
    affect = ARCH_AFFECT.get(arch, {"arousal": 0.6, "valence": 0.0, "power": 0.5})
    return {
        "name": comedian,
        "persona_note": f"stage persona hypothesis from text only: {', '.join(traits)}. "
                        f"Comedy lean: {humour}. Top mechanisms: {', '.join(ops)}.",
        "delivery_note": (f"Archetype prior: {arch}. No delivery audio has been heard "
                          f"for this comedian; use population norms with this persona."),
        "affect": affect,
        "archetype": arch,
    }


def predict_beats(beats: list, profile: dict) -> dict:
    """Jev prediction with TEXT-ONLY state (no errors, no target audio)."""
    state = {
        "comedian": profile["name"],
        "persona": profile["persona_note"],
        "delivery_history_note": profile["delivery_note"],
        "affect": profile["affect"],
        "segments": [{"id": f"s{b['i']}", "text": b["text"]} for b in beats],
        "note": "You have NOT heard this comedian. Predict from text + persona only.",
    }
    qs = {}
    for b in beats:
        sid = f"s{b['i']}"
        qs[f"{sid}_emo"] = {"type": "choice",
            "instructions": f"For segment {sid}, which delivery emotion fits the text?",
            "criteria": EMOTIONS}
        qs[f"{sid}_pace"] = {"type": "score",
            "instructions": f"For segment {sid}, how fast should it be delivered?",
            "criteria": ["slow measured", "conversational", "fast energetic", "rapid-fire"]}
    res = decide(state, qs)
    return res.get("answers", {})


def render_beat(i: int, text: str, emo: str, pace: float, speed_scale: float) -> Path:
    cue, temp, emo_speed = EMO_RECIPE.get(emo, ("[neutral]", 0.6, 1.0))
    bucket = int(round(max(0, min(3, pace))))
    target = {0: 0.70, 1: 0.95, 2: 1.20, 3: 1.45}[bucket] * speed_scale * emo_speed
    t = f"{cue} {text}".strip() if cue else text
    r = fish_tts.synthesize_fish(f"zc-{i}", t, voice=POP_CLONE, direction=False,
                                 temperature=temp,
                                 prosody={"speed": round(target, 2)})
    return Path(r["path"])


def run(setname: str, comedian: str, clip: str) -> dict:
    words = json.loads((REPO / "theory/scribe" / f"{setname}.json").read_text())["words"]
    gt = json.loads((REPO / "theory/killtony-minutes" / f"{setname}_gemini.gemini.json").read_text())
    beats = fixed_beats(words)
    profile = text_profile(comedian)
    print(f"{setname} ({comedian}): {len(beats)} beats | profile: "
          f"{profile['archetype']} | affect={profile['affect']}")
    print(f"  persona(text-only): {profile['persona_note'][:80]}...")

    t0 = time.time()
    answers = predict_beats(beats, profile)
    print(f"  jev predicted: {time.time()-t0:.1f}s")

    parts, rows = [], []
    for b in beats:
        sid = f"s{b['i']}"
        pred_emo = (answers.get(f"{sid}_emo") or {}).get("choice", "neutral")
        pace = (answers.get(f"{sid}_pace") or {}).get("score", 1.5)
        true_emo = gemini_label(gt["segments"], b["t0"], b["t1"])
        true_all = gemini_labels(gt["segments"], b["t0"], b["t1"])
        wav = render_beat(b["i"], b["text"], pred_emo, pace, POP_SPEED_SCALE)
        gen = voice_judge.measure(wav)
        gen_wpm = b["n_words"] / (gen["duration_ms"] / 1000) * 60
        # actual speech-span wpm
        in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]
                  and not w["text"].strip().startswith("[")]
        act_wpm = 0.0
        if len(in_win) >= 2:
            span = in_win[-1]["end"] - in_win[0]["start"]
            act_wpm = len(in_win) / span * 60 if span > 1 else 0
        match = 1.0 if pred_emo == true_emo else (0.5 if pred_emo in true_all[1:3] else 0.0)
        parts.append(wav)
        rows.append({"seg": sid, "pred_emo": pred_emo, "true_emo": true_emo,
                     "match_score": match, "gen_wpm": round(gen_wpm, 1),
                     "act_wpm": round(act_wpm, 1),
                     "wpm_err": round(gen_wpm - act_wpm, 1)})
        print(f"    {sid} {'OK ' if match >= 1 else ('~' if match else 'MISS')} "
              f"{pred_emo:14}/{true_emo:14} wpm {gen_wpm:.0f}/{act_wpm:.0f}")

    acc = sum(r["match_score"] for r in rows) / max(len(rows), 1)
    wpm_mae = sum(abs(r["wpm_err"]) for r in rows) / max(len(rows), 1)
    import fish_tts as F
    out_wav = Path(f"/home/box/zerocal_{comedian}_{setname}.wav")
    F.stitch_wav(parts, out_wav)
    doc = {"set": setname, "comedian": comedian, "condition": "zero-calibration "
           "(text profile + population priors only; never heard their audio)",
           "profile_archetype": profile["archetype"],
           "emotion_acc": round(acc, 3), "wpm_mae": round(wpm_mae, 1),
           "n_beats": len(rows), "rows": rows, "wav": str(out_wav),
           "cost_note": "jev ~$0.0001 + fish free",
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"zerocal_{comedian}_{setname}.json").write_text(json.dumps(doc, indent=2))
    print(f"\nZERO-CAL {comedian}: acc={acc:.2f} wpm_mae={wpm_mae:.1f} -> {out_wav}")
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--comedian", required=True)
    ap.add_argument("--clip", default="")
    args = ap.parse_args()
    run(args.set, args.comedian, args.clip)
