"""Laugh simulator: listens to any audio set, laughs where it predicts.

Input: any set audio. Transcribe (word timings) -> window ~6s -> laugh
model v3 (wps, pause, position, history) -> P per window -> MIX a crowd
laugh track over the original at predicted moments. Also emits the
timeline. Compare its laughs to actual (AM events) = built-in validation.

Usage: python3 laugh_sim.py <audio> [--out mixed.wav] [--threshold 0.5]
"""
from __future__ import annotations
import argparse, json, pickle, subprocess, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import fish_tts

HERE = Path(__file__).parent
LAB = HERE / "voicelab"


def features_and_predict(words, win_s=6.0):
    """Window the word stream -> features -> P per window."""
    m = pickle.loads((LAB / "laugh_model_v3.pkl").read_bytes())
    if not words:
        return [], []
    t0, t1 = words[0]["start"], words[-1]["end"]
    preds, hist, wins = [], 0.0, []
    t = t0
    while t < t1:
        ws = [w for w in words if t <= w["start"] < t + win_s]
        if len(ws) >= 3:
            dur = ws[-1]["end"] - ws[0]["start"]
            wps = len(ws) / dur if dur > 0 else 0
            prev_end = max((w["end"] for w in words if w["end"] <= t), default=t)
            pause = min(t - prev_end, 15) if prev_end < t else 0
            x = np.array([[wps, pause, win_s, (t - t0) / max(t1 - t0, 1), hist]])
            p = float(m["model"].predict_proba(x)[0, 1])
            wins.append({"t_start": round(t, 2), "t_end": round(min(t + win_s, t1), 2),
                         "wps": round(wps, 2), "p_laugh": round(p, 3),
                         "moment": round(min(t + win_s, t1), 2)})
            preds.append(p)
            hist = min(10, hist + p) * 0.85
        t += win_s
    return wins, preds


def crowd_clip(kind: str) -> Path:
    """Pre-render crowd sounds once."""
    out = HERE / "audio" / f"crowd_{kind}.wav"
    if not out.exists():
        cue = "[crowd laughing]" if kind == "crowd" else "[chuckling]"
        r = fish_tts.synthesize_fish(f"crowd-{kind}", cue, direction=False, temperature=0.8)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", r["path"],
                        str(out)], check=True)
    return out


def mix_laughter(audio: Path, wins: list, threshold: float, out: Path) -> list:
    """Overlay crowd clips at predicted moments (amix with adelay)."""
    crowd = crowd_clip("crowd")
    chuck = crowd_clip("chuck")
    fired = []
    inputs = ["-i", str(audio)]
    filters, idx = [], 1
    for w in wins:
        if w["p_laugh"] >= threshold:
            clip, ms = crowd, int(w["moment"] * 1000)
            kind = "crowd"
        elif w["p_laugh"] >= max(0.3, threshold - 0.18):
            clip, ms = chuck, int(w["moment"] * 1000)
            kind = "chuckle"
        else:
            continue
        inputs += ["-i", str(clip)]
        filters.append(f"[{idx}]adelay={ms}|{ms}[a{idx}]")
        fired.append({**w, "kind": kind, "ms": ms})
        idx += 1
    if not fired:
        # still write original through
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio), str(out)], check=True)
        return []
    mix_labels = "[0:a]" + "".join(f"[a{i}]" for i in range(1, idx))
    filters.append(f"{mix_labels}amix=inputs={idx}:duration=first:dropout_transition=0[out]")
    cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + [
        "-filter_complex", ";".join(filters), "-map", "[out]", str(out)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return fired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--out", default=None)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--win", type=float, default=6.0)
    args = ap.parse_args()
    audio = Path(args.audio)
    out = Path(args.out) if args.out else audio.with_name(audio.stem + "__with_crowd.wav")

    import cf_asr
    print(f"listening: {audio.name} ...")
    d = cf_asr.transcribe(audio)
    wins, preds = features_and_predict(d["words"], args.win)
    n_high = sum(1 for p in preds if p >= args.threshold)
    print(f"{len(wins)} windows, {n_high} predicted-laugh (P>={args.threshold})")

    fired = mix_laughter(audio, wins, args.threshold, out)
    print(f"laughed at {len(fired)} moments:")
    for f in fired:
        print(f"  {f['moment']:6.1f}s  P={f['p_laugh']}  [{f['kind']}]")

    # validation hook: if AM events cached for a matching set, compare
    timeline = {"audio": str(audio), "windows": wins, "fired": fired,
                "threshold": args.threshold,
                "out": str(out)}
    Path(str(out).replace(".wav", "_timeline.json")).write_text(json.dumps(timeline, indent=2))
    print(f"\nmixed: {out}")


if __name__ == "__main__":
    main()
