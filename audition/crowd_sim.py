"""Crowd simulator: render a set with model-predicted crowd response.

Per beat: laugh model P -> insert [crowd laughing] (P>=.55), [chuckling]
(.35-.55), or silence (low). The set + its predicted audience, audible.

Usage: python3 crowd_sim.py --set-json voicelab/swaps/dracula__pickles_set_mapping.json \
       --out /home/box/dracula_with_crowd.wav [--voice <id>]
"""
from __future__ import annotations
import argparse, json, pickle
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import fish_tts, voice_judge

HERE = Path(__file__).parent
LAB = HERE / "voicelab"

def laugh_p(wpm, pos, hist):
    m = pickle.loads((LAB / "laugh_model_v3.pkl").read_bytes())
    x = np.array([[wpm/60, 1.0, 15.0, pos, hist]])
    return float(m["model"].predict_proba(x)[0, 1])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default=None, help="override voice id")
    ap.add_argument("--crowd-cue", default="[crowd laughing]")
    args = ap.parse_args()
    rec = json.loads(Path(args.set_json).read_text())
    beats = rec["beats"]
    voice = args.voice or (rec.get("voice") if isinstance(rec.get("voice"), str) else None)
    # resolve voice: mapping jsons store voice as name or id; try clone_ids/names
    VOICE_IDS = {"roast": "4805c450f3e84faaa16f2cf9690fbd90",
                 "dracula_a": "04e9ab898fb44ccd9b7ac2357439d6ec",
                 "narrator": "8d21b053e2804e2a890e1cf62f267b6f",
                 "spongebob": "0051da373e0a4ac282399909d1d31b69"}
    if voice in VOICE_IDS: voice = VOICE_IDS[voice]
    parts, log = [], []
    hist = 0.0
    for i, b in enumerate(beats):
        text = b["text"]
        r = b.get("recipe") or {"temp": 0.6, "speed": 1.0, "cue": "", "vol": 0}
        cue = r.get("cue") or ""
        t = f"{cue} {text}".strip() if cue else text
        # estimate wpm from text length (short-beat proxy) + position
        est_wpm = len(text.split()) / max(b.get("pause_after_ms", 800)/1000 + len(text.split())/2.6, 1) * 60
        p = laugh_p(est_wpm, (i+1)/len(beats), hist)
        out = fish_tts.synthesize_fish(f"cs-{i}", t, voice=voice, direction=False,
                                       temperature=r.get("temp", 0.6),
                                       prosody={"speed": r.get("speed", 1.0),
                                                "volume": r.get("vol", 0)})
        parts.append(Path(out["path"]))
        # predicted crowd response AFTER this beat
        if p >= 0.55:
            _lr = fish_tts.synthesize_fish(f"cs-laugh-{i}", args.crowd_cue,
                                           direction=False, temperature=0.8)
            parts.append(Path(_lr["path"]))
            verdict = "CROWD"
        elif p >= 0.35:
            _cr = fish_tts.synthesize_fish(f"cs-chk-{i}", "[chuckling]",
                                           direction=False, temperature=0.8)
            parts.append(Path(_cr["path"]))
            verdict = "chuckle"
        else:
            parts.append(fish_tts.silence_wav(600))
            verdict = "silence"
        log.append({"beat": i, "p_laugh": round(p, 2), "crowd": verdict})
        hist = min(10, hist + (1 if p >= 0.55 else 0)) * 0.88
        print(f"  beat{i}: P={p:.2f} -> {verdict}  {text[:50]}...")
    wav = Path(args.out)
    fish_tts.stitch_wav(parts, wav)
    m = voice_judge.measure(wav)
    rec_out = {"source_set": args.set_json, "beats": log,
               "duration_ms": m["duration_ms"], "crowd_events": sum(1 for l in log if l["crowd"]=="CROWD"),
               "note": "crowd response = laugh model v3 predictions, rendered via fish sound cues"}
    Path(str(wav).replace(".wav", "_sim.json")).write_text(json.dumps(rec_out, indent=2))
    print(f"\n{wav}: {rec_out['crowd_events']} crowd laughs, {m['duration_ms']}ms")

if __name__ == "__main__":
    main()
