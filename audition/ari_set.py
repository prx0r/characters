"""Ari full-set RL loop — exact words, per-segment recipes, evolve to target.

kt704 set (0-59s): words from scribe, emotion arcs from gemini, targets from
calibration winners. Per segment: render -> score (wpm_err + var_err) ->
mutate (speed/temp/cue) -> keep-if-better, N rounds. Stitch full set.
Recipe ledger content-addressed (cg-spirit: recipe sha = receipt).

Free tier only. Usage: python3 ari_set.py [--rounds 2]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab" / "ari_set"

# gemini segments (kt704): (t0, t1, emotion, base_temp, base_speed, cue)
SEGMENTS = [
    (12.5, 25.5, "manic",         0.85, 1.30, "[excited]"),
    (25.5, 40.5, "sarcastic",     0.65, 1.10, "[sarcastic]"),
    (40.5, 54.0, "mock_indignant", 0.85, 1.56, "[frustrated]"),
    (54.0, 59.5, "gleeful",       0.80, 1.30, "[delighted]"),
]
VAR_TARGET = {"manic": 6.2, "sarcastic": 4.6, "mock_indignant": 6.0, "gleeful": 5.4}
CUE_ALTS = {"manic": ["[excited]", "[delighted]", ""],
            "sarcastic": ["[sarcastic]", "[indifferent]", "[confused]"],
            "mock_indignant": ["[frustrated]", "[angry]", "[excited]"],
            "gleeful": ["[delighted]", "[chuckling]", "[excited]"]}


def load_words():
    d = json.loads((REPO / "theory/scribe/kt704_passport.json").read_text())
    return d["words"]


def segment_text(words, t0, t1):
    ws = [w for w in words if t0 <= w["start"] < t1]
    if not ws:
        return "", 0, 0.0
    text = " ".join(w["text"] for w in ws
                    if not w["text"].startswith("[laugh"))
    text = text.replace("[laughs]", "").replace("[laughing]", "")
    dur = ws[-1]["end"] - ws[0]["start"]
    return " ".join(text.split()), len(text.split()), dur


def render(name, text, temp, speed, vol, cue):
    import fish_tts
    t = f"{cue} {text}".strip() if cue else text
    r = fish_tts.synthesize_fish(f"ariset-{name}", t, direction=False,
                                 temperature=temp,
                                 prosody={"speed": round(speed, 2), "volume": vol})
    return Path(r["path"])


def measure(path, words_n):
    import voice_judge
    m = voice_judge.measure(path)
    dur = m["duration_ms"] / 1000
    return {"wpm": round(words_n / dur * 60, 1) if dur else 0,
            "var_st": m["pitch"].get("std_semitones") or 0,
            "duration_ms": m["duration_ms"]}


def score(m, target_wpm, target_var):
    return round(abs(m["wpm"] - target_wpm) / target_wpm * 100
                 + 1.2 * abs(m["var_st"] - target_var), 2)


def recipe_id(seg_i, temp, speed, cue, vol=0.0):
    blob = f"kt704seg{seg_i}|t{temp}|s{speed}|c{cue}|v{vol}".encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def evolve_segment(seg_i, words, rounds):
    t0, t1, emo, temp, speed0, cue = SEGMENTS[seg_i]
    text, n_words, real_dur = segment_text(words, t0, t1)
    target_wpm = n_words / real_dur * 60 if real_dur else 220
    target_var = VAR_TARGET[emo]
    # measure base voice wpm on THIS text, then speed = target/base
    base_p = render(f"base-s{seg_i}", text, temp, 1.0, 0.0, "")
    base_m = measure(base_p, n_words)
    speed = max(0.5, min(2.0, target_wpm / max(base_m["wpm"], 1)))
    print(f"  base wpm={base_m['wpm']} -> init speed={speed:.2f} (tgt {target_wpm:.0f})", flush=True)
    best = {"score": 1e9}
    ledger = []

    candidates = [{"temp": temp, "speed": round(speed, 2), "cue": cue, "vol": 0.0}]
    for r in range(rounds + 1):
        next_cands = []
        for c in candidates:
            rid = recipe_id(seg_i, c["temp"], c["speed"], c["cue"], c["vol"])
            try:
                p = render(f"s{seg_i}_{rid}", text, c["temp"], c["speed"], c["vol"], c["cue"])
                m = measure(p, n_words)
                sc = score(m, target_wpm, target_var)
                row = {"recipe_id": rid, "round": r, **c, **m, "score": sc,
                       "target_wpm": round(target_wpm, 1)}
                ledger.append(row)
                print(f"  seg{seg_i} r{r} {rid} sc={sc:6.2f} wpm={m['wpm']:6.1f}"
                      f"(tgt {target_wpm:.0f}) var={m['var_st']:.2f}"
                      f"(tgt {target_var}) {c['cue'] or 'no-cue'}", flush=True)
                if sc < best["score"]:
                    best = row
                # mutate around candidates
                if r < rounds:
                    for dt in (-0.12, 0.12):
                        next_cands.append({**c, "temp": round(max(0.3, min(0.95, c["temp"] + dt)), 2)})
                    for ds in (-0.25, 0.25):
                        next_cands.append({**c, "speed": round(max(0.5, min(2.0, c["speed"] + ds)), 2)})
                    for alt in CUE_ALTS[emo]:
                        if alt != c["cue"]:
                            next_cands.append({**c, "cue": alt})
                            break
                    next_cands.append({**c, "vol": max(-4.0, min(3.0, c["vol"] + (1.0 if m["wpm"] < target_wpm else -1.0)))})
            except Exception as e:
                print(f"  seg{seg_i} r{r} {rid} FAIL {str(e)[:80]}", flush=True)
        candidates = next_cands[:6]  # keep search cheap
    return text, best, ledger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    LAB.mkdir(parents=True, exist_ok=True)
    words = load_words()
    full_ledger = []
    winners = []
    for seg_i in range(len(SEGMENTS)):
        print(f"== segment {seg_i} {SEGMENTS[seg_i][2]} ==", flush=True)
        text, best, ledger = evolve_segment(seg_i, words, args.rounds)
        full_ledger.extend(ledger)
        winners.append({"seg": seg_i, "text": text, **best})
        print(f"  BEST seg{seg_i}: sc={best['score']} {best.get('recipe_id')}", flush=True)

    # stitch full set with short breaths between segments
    import fish_tts
    parts = []
    for w in winners:
        t0, t1, emo, *_ = SEGMENTS[w["seg"]]
        cue = w["cue"]
        p = render(f"final-{w['seg']}", w["text"], w["temp"], w["speed"], w["vol"], cue)
        parts.append(p)
        parts.append(fish_tts.silence_wav(350))
    out = LAB / "ari_kt704_full.wav"
    fish_tts.stitch_wav(parts[:-1], out)

    doc = {"set": "kt704", "segments": winners, "ledger": full_ledger,
           "out": str(out), "total_ms": fish_tts._ffprobe_ms(out),
           "note": "exact words, per-segment RL on fish knobs; $0 free tier",
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / "ari_set.json").write_text(json.dumps(doc, indent=2))
    print(f"\nFULL SET: {out} ({doc['total_ms']}ms)", flush=True)
    print(json.dumps([{k: w[k] for k in ("seg", "score", "wpm", "var_st", "cue", "temp", "speed")} for w in winners], indent=1))


if __name__ == "__main__":
    main()
