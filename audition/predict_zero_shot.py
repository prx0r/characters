"""Zero-shot unseen-minute test: predict delivery from PERSON priors only.

No RL, no hearing the target clip first. Predictions come from:
  persona features.jsonl aggregates + EMO priors v2 + base-voice math.
Render -> measure vs the REAL clip's stats -> error. Then 1 adaptation
round (miss-driven) -> error after. Frontier-informed metric: wpm + var
(our F0-proxy) both compared against the actual audio itself.

Usage: python3 predict_zero_shot.py --scribe ... --audio ... --comedian kam_patterson
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def persona_wpm(comedian: str) -> float | None:
    ws = []
    for line in (REPO / "theory/killtony-features.jsonl").read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if norm((r.get("set_pointer") or {}).get("comedian") or "") != norm(comedian):
            continue
        t = r.get("timing_s") or {}
        dur = (t.get("end") or 0) - (t.get("start") or 0)
        if dur > 20:  # filter junk timing rows
            wpm = r["word_count"] / dur * 60
            if 80 <= wpm <= 320:  # sane standup range
                ws.append(wpm)
    if not ws:
        return None
    ws.sort()
    return round(ws[len(ws) // 2], 1)  # median, robust to outliers


def segments(words, gap=0.8, min_n=5):
    """Laugh-gap segmentation (StandUp4AI insight): gaps >0.8s in continuous
    speech are usually audience-laughter holes, not dead air — split there
    and mark the pre-gap word as a punch candidate (audio-first beat label)."""
    segs, cur = [], [words[0]]
    for w in words[1:]:
        if w["start"] - cur[-1]["end"] > gap and len(cur) >= min_n:
            segs.append(cur); cur = [w]
        else:
            cur.append(w)
    if len(cur) >= min_n:
        segs.append(cur)
    # punch candidates: last word before a >0.8s gap
    punches = set()
    for a, b in zip(words, words[1:]):
        if b["start"] - a["end"] > gap:
            punches.add(a["start"])
    return segs, punches


def emo_of(ws):
    dur = ws[-1]["end"] - ws[0]["start"]
    wpm = len(ws) / dur * 60 if dur else 180
    if wpm >= 200: return "manic", "[excited]", 0.85
    if wpm >= 170: return "gleeful", "[delighted]", 0.80
    if wpm >= 140: return "neutral", "[neutral]", 0.60
    return "deadpan", "", 0.45


def render_seg(name, text, temp, speed, cue):
    import fish_tts
    t = f"{cue} {text}".strip() if cue else text
    r = fish_tts.synthesize_fish(f"zs-{name}", t, direction=False, temperature=temp,
                                 prosody={"speed": round(speed, 2), "volume": 0.0})
    return Path(r["path"])


def measure(path, n_words):
    import voice_judge
    m = voice_judge.measure(path)
    dur = m["duration_ms"] / 1000
    return {"wpm": round(n_words / dur * 60, 1) if dur else 0,
            "var_st": m["pitch"].get("std_semitones") or 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scribe", required=True)
    ap.add_argument("--audio", required=True, help="source clip = ground truth")
    ap.add_argument("--comedian", required=True)
    ap.add_argument("--adapt", action="store_true", help="run 1 miss-driven round")
    args = ap.parse_args()

    import fish_tts, voice_judge
    words = json.loads(Path(args.scribe).read_text())["words"]
    segs, punch_times = segments(words)
    print(f"laugh-gap segments: {len(segs)} (was 1 with old 1.1s gap) | "
          f"punch candidates: {len(punch_times)}")

    # ground truth = the actual clip
    gt = measure(Path(args.audio), len(words))
    pw = persona_wpm(args.comedian)
    print(f"ACTUAL clip: wpm={gt['wpm']} var={gt['var_st']}")
    print(f"persona prior (past sets): wpm={pw}")

    base = render_seg("base", "The quick brown fox jumps over the lazy dog.", 0.6, 1.0, "")
    bm = measure(base, 9)
    print(f"base voice: wpm={bm['wpm']}")

    rows = []
    for i, ws in enumerate(segs):
        emo, cue, temp = emo_of(ws)
        text = re.sub(r"\[laughs?\]", "", " ".join(w["text"] for w in ws), flags=re.I)
        text = re.sub(r"\[censored\]", "crap", text, flags=re.I)
        text = " ".join(text.split())
        n = len(text.split())
        # PREDICTION: persona wpm (not this clip's timing!) adjusted by emotion
        pred_wpm = (pw or gt["wpm"]) * {"manic": 1.15, "gleeful": 1.05,
                                        "neutral": 0.95, "deadpan": 0.85}.get(emo, 1.0)
        try:
            ct = json.loads((HERE / "voicelab/cue_tempo.json").read_text())["factors"]
        except Exception:
            ct = {}
        cfactor = ct.get(cue, 1.0) if cue else 1.0
        speed = max(0.5, min(2.0, pred_wpm / max(bm["wpm"] * cfactor, 1)))
        p = render_seg(f"{args.comedian}-{i}", text, temp, speed, cue)
        m = measure(p, n)
        # real per-segment stats
        seg_dur = ws[-1]["end"] - ws[0]["start"]
        real_wpm = n / seg_dur * 60
        err = round(m["wpm"] - real_wpm, 1)
        rows.append({"seg": i, "emotion": emo, "pred_wpm": round(pred_wpm),
                     "real_wpm": round(real_wpm, 1), "gen_wpm": m["wpm"],
                     "err": err, "gen_var": m["var_st"], "file": str(p),
                     "speed": round(speed, 2), "cue": cue, "temp": temp})
        print(f"  seg{i} {emo:8} pred={pred_wpm:.0f} real={real_wpm:.0f} gen={m['wpm']:.0f} err={err:+.1f}")

    mae0 = sum(abs(r["err"]) for r in rows) / len(rows)
    print(f"\nZERO-SHOT wpm MAE: {mae0:.1f}")
    if args.adapt:
        # one miss-driven round: rescale speed by real/pred per segment
        rows2 = []
        for r, ws in zip(rows, segs):
            text = re.sub(r"\[laughs?\]", "", " ".join(w["text"] for w in ws), flags=re.I)
            text = " ".join(re.sub(r"\[censored\]", "crap", text, flags=re.I).split())
            speed2 = max(0.5, min(2.0, r["speed"] * (r["real_wpm"] / max(r["gen_wpm"], 1))))
            p = render_seg(f"{args.comedian}-a{r['seg']}", text, r["temp"], speed2, r["cue"])
            m = measure(p, len(text.split()))
            seg_dur = ws[-1]["end"] - ws[0]["start"]
            real_wpm = len(text.split()) / seg_dur * 60
            rows2.append({**r, "err2": round(m["wpm"] - real_wpm, 1), "gen2_wpm": m["wpm"],
                          "speed2": round(speed2, 2)})
            print(f"  adapt seg{r['seg']}: gen={m['wpm']:.0f} err={rows2[-1]['err2']:+.1f} (speed {r['speed']}->{speed2:.2f})")
        mae1 = sum(abs(r["err2"]) for r in rows2) / len(rows2)
        print(f"AFTER 1 ADAPT ROUND wpm MAE: {mae1:.1f} (was {mae0:.1f})")
        rows = rows2

    out = {"comedian": args.comedian, "zero_shot_mae": round(mae0, 2),
           "after_adapt_mae": round(mae1, 2) if args.adapt else None,
           "actual": gt, "persona_prior_wpm": pw, "segments": rows,
           "note": "delivery predicted from person priors only; tested vs real clip"}
    p = HERE / "voicelab" / f"zeroshot_{args.comedian}.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"-> {p}")


if __name__ == "__main__":
    main()
