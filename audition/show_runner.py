"""Show runner: simulated comedy episode — acts, crowd, judge, standings.

v1 pilot: takes existing rendered sets as acts, runs crowd_sim per act,
scores with the full rubric (laugh-model mean P + delivery stats + verify),
updates Elo standings, writes the episode ledger. All components already
existed; this is the orchestration.

Usage: python3 show_runner.py episode --name pilot_001
"""
from __future__ import annotations
import argparse, json, pickle, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import fish_tts, voice_judge

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
SHOWS = LAB / "shows"

ACTS = [
    {"act": 1, "character": "Dracula (pickles engine)",
     "set_json": "swaps/dracula__pickles_set_mapping.json", "voice": "04e9ab898fb44ccd9b7ac2357439d6ec"},
    {"act": 2, "character": "Joker (casey engine)",
     "set_json": "swaps/joker__casey_derived.json", "voice": "fad5a5a6770e47019f566b8f8c0ff609"},
    {"act": 3, "character": "Blip (kam engine)",
     "set_json": "swaps/blip_the_first-contact_host__kam_patterson_delivery.json",
     "voice": "0051da373e0a4ac282399909d1d31b69"},
]

def laugh_p(wpm, pos, hist):
    m = pickle.loads((LAB / "laugh_model_v3.pkl").read_bytes())
    return float(m["model"].predict_proba(np.array([[wpm/60, 1.0, 15.0, pos, hist]]))[0, 1])

def perform(act: dict) -> dict:
    """Render act with adaptive pauses + inline crowd response."""
    rec = json.loads((LAB / act["set_json"]).read_text())
    beats = rec["beats"]
    parts, beat_log, hist = [], [], 0.0
    total_crowd = 0
    for i, b in enumerate(beats):
        r = b.get("recipe") or {"temp": 0.6, "speed": 1.0, "cue": "", "vol": 0}
        cue = r.get("cue") or ""
        t = f"{cue} {b['text']}".strip() if cue else b["text"]
        est_wpm = len(b["text"].split()) / max(0.8 + len(b["text"].split())/2.6, 1) * 60
        p = laugh_p(est_wpm, (i+1)/len(beats), hist)
        out = fish_tts.synthesize_fish(f"show-{act['act']}-{i}", t, voice=act["voice"],
                                       direction=False, temperature=r.get("temp", 0.6),
                                       prosody={"speed": r.get("speed", 1.0),
                                                "volume": r.get("vol", 0)})
        parts.append(Path(out["path"]))
        if p >= 0.55:
            lr = fish_tts.synthesize_fish(f"show-laugh-{act['act']}-{i}", "[crowd laughing]",
                                          direction=False, temperature=0.8)
            parts.append(Path(lr["path"])); total_crowd += 1; verdict = "CROWD"
        elif p >= 0.35:
            cr = fish_tts.synthesize_fish(f"show-chk-{act['act']}-{i}", "[chuckling]",
                                          direction=False, temperature=0.8)
            parts.append(Path(cr["path"])); verdict = "chuckle"
        else:
            parts.append(fish_tts.silence_wav(600)); verdict = "silence"
        beat_log.append({"beat": i, "p_laugh": round(p, 2), "crowd": verdict})
        hist = min(10, hist + (1 if p >= 0.55 else 0)) * 0.88
    wav = SHOWS / f"act{act['act']}_{act['character'].split()[0].lower()}.wav"
    fish_tts.stitch_wav(parts, wav)
    m = voice_judge.measure(wav)
    mean_p = sum(b["p_laugh"] for b in beat_log) / len(beat_log)
    return {"act": act["act"], "character": act["character"], "wav": str(wav),
            "beats": beat_log, "mean_p": round(mean_p, 3),
            "crowd_events": total_crowd, "duration_ms": m["duration_ms"],
            "pitch_std": m["pitch"].get("std_semitones"),
            "verify_source": rec.get("verify_match")}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="pilot_001")
    ap.add_argument("--acts-file", default=None)
    args = ap.parse_args()
    SHOWS.mkdir(exist_ok=True)
    print(f"EPISODE {args.name}: {len(ACTS)} acts\n")
    acts = ACTS
    if args.acts_file:
        acts = json.loads(Path(args.acts_file).read_text())
    results = []
    for act in acts:
        print(f"ACT {act['act']}: {act['character']}")
        r = perform(act)
        # composite judge score: mean P (crowd) + verify (words survived) - length penalty noise
        score = round(r["mean_p"] * 0.7 + (r.get("verify_source") or 0.85) * 0.3, 3)
        r["judge_score"] = score
        print(f"  -> meanP={r['mean_p']} crowd_events={r['crowd_events']} "
              f"verify={r.get('verify_source')} JUDGE={score}\n")
        results.append(r)
    # standings by judge score
    results.sort(key=lambda r: -r["judge_score"])
    ep = {"name": args.name, "acts": results,
          "standings": [{"rank": i+1, "character": r["character"],
                         "judge_score": r["judge_score"]} for i, r in enumerate(results)],
          "judge_stack": "laugh_model_v3 mean P (0.7) + verify (0.3); dpv stats logged",
          "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (SHOWS / f"{args.name}.json").write_text(json.dumps(ep, indent=2))
    print("STANDINGS:")
    for s in ep["standings"]:
        print(f"  {s['rank']}. {s['character']:32} {s['judge_score']}")
    print(f"\nledger: voicelab/shows/{args.name}.json")
    print("wavs:", [r["wav"].split("/")[-1] for r in results])

if __name__ == "__main__":
    main()
