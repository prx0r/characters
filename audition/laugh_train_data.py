"""Laugh training data builder: ASR words + AM events → Jev decision rows.

Pipeline:
  1. Load ASR word timestamps for a special
  2. Load AM-detected laugh events for the same special
  3. Segment into beats (fixed ~6s windows or sentence boundaries)
  4. Label each beat: laugh=1 if AM event in [beat_end-0.5s, beat_end+2.0s]
  5. Extract features: text context + timing + mechanism
  6. Output: Jev decision format (state/questions/gold)

Usage:
  python3 laugh_train_data.py build    # build rows from all ASR+AM pairs
  python3 laugh_train_data.py jev      # format as Jev decision training data
"""
from __future__ import annotations
import json, re
from pathlib import Path

AUDIO = Path("/home/box/comedy-audio")
ASR_DIR = AUDIO / "asr"
AM_DIR = AUDIO / "am_events"
OUT_DIR = Path(__file__).parent / "voicelab" / "laugh_training"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_special(stem: str) -> dict | None:
    """Load ASR words + AM events for one special."""
    asr_p = ASR_DIR / f"{stem}.json"
    am_p = AM_DIR / f"{stem}.json"
    if not asr_p.exists() or not am_p.exists():
        return None
    words = json.loads(asr_p.read_text())["words"]
    events = json.loads(am_p.read_text())
    return {"stem": stem, "words": words, "events": events}


def make_beats(words: list, win_s: float = 6.0) -> list:
    """Fixed-window beats over the word stream."""
    if not words:
        return []
    t0, t1 = words[0]["start"], words[-1]["end"]
    beats = []
    t = t0
    i = 0
    while t < t1:
        ws = [w for w in words if t <= w["start"] < t + win_s
              and not w["text"].startswith("[")]
        if len(ws) >= 3:
            dur = ws[-1]["end"] - ws[0]["start"]
            # timing features
            prev_end = max((w["end"] for w in words if w["end"] <= t), default=t)
            pause = min(t - prev_end, 15) if prev_end < t else 0
            beats.append({
                "i": i, "t0": round(t,2), "t1": round(min(t+win_s, t1),2),
                "wps": round(len(ws)/dur, 2) if dur > 0 else 0,
                "pause_before": round(pause, 2),
                "dur": round(dur, 2),
                "pos": round((t-t0)/max(t1-t0, 1), 3),
                "text": " ".join(w["text"] for w in ws),
                "n_words": len(ws),
            })
            i += 1
        t += win_s
    return beats


def label_beats(beats: list, events: list) -> list:
    """Label each beat: laugh=1 if AM event near beat end."""
    hist = 0.0
    for b in beats:
        # AM onset in [beat_end - 0.5s, beat_end + 2.0s]
        b["laugh"] = 1 if any(b["t1"] - 0.5 <= s <= b["t1"] + 2.0
                               for s, _, _ in events) else 0
        # laugh intensity: max modulation strength in window
        strengths = [m for s, _, m in events
                     if b["t1"] - 0.5 <= s <= b["t1"] + 2.0]
        b["laugh_strength"] = round(max(strengths), 2) if strengths else 0.0
        # contagion history (decaying)
        b["hist"] = round(hist, 2)
        hist = min(10, hist + b["laugh"]) * 0.88
    return beats


def extract_text_context(words: list, beat: dict, before: int = 5, after: int = 3) -> dict:
    """Get text context around a beat for mechanism analysis."""
    # words in this beat
    beat_words = [w for w in words if beat["t0"] <= w["start"] < beat["t1"]
                  and not w["text"].startswith("[")]
    # words before (context)
    before_words = [w for w in words if w["end"] <= beat["t0"]
                    and not w["text"].startswith("[")][-before:]
    # words after (the reaction)
    after_words = [w for w in words if w["start"] >= beat["t1"]
                   and not w["text"].startswith("[")][:after]

    return {
        "setup": " ".join(w["text"] for w in before_words),
        "punchline": " ".join(w["text"] for w in beat_words),
        "reaction": " ".join(w["text"] for w in after_words),
    }


def build_all() -> list:
    """Build training rows from all ASR+AM pairs."""
    rows = []
    stems = sorted(set(
        p.stem for p in ASR_DIR.glob("*.json")
        if (AM_DIR / f"{p.stem}.json").exists()
    ))
    print(f"building from {len(stems)} specials")
    for stem in stems:
        data = load_special(stem)
        if not data:
            continue
        beats = make_beats(data["words"])
        beats = label_beats(beats, data["events"])
        n_pos = sum(b["laugh"] for b in beats)
        print(f"  {stem}: {len(beats)} beats, {n_pos} positive ({n_pos/max(len(beats),1):.1%})")
        for b in beats:
            ctx = extract_text_context(data["words"], b)
            rows.append({
                "stem": stem, "beat_i": b["i"],
                "t0": b["t0"], "t1": b["t1"],
                "wps": b["wps"], "pause_before": b["pause_before"],
                "dur": b["dur"], "pos": b["pos"], "hist": b["hist"],
                "text": b["text"],
                "setup": ctx["setup"], "punchline": ctx["punchline"],
                "reaction": ctx["reaction"],
                "laugh": b["laugh"], "laugh_strength": b["laugh_strength"],
            })
    return rows


def format_jev(rows: list) -> list:
    """Format rows as Jev decision training data."""
    questions = {
        "will_laugh": {
            "type": "noul",
            "instructions": "Will the audience laugh after this segment of a stand-up comedy set?"
        },
        "laugh_size": {
            "type": "score",
            "instructions": "How big will the laugh be?",
            "criteria": ["none", "light", "medium", "big", "roaring"]
        }
    }
    jev_rows = []
    for r in rows:
        # Map laugh_strength to size scale
        strength = r["laugh_strength"]
        if strength == 0: size = 0
        elif strength < 0.6: size = 1
        elif strength < 0.7: size = 2
        elif strength < 0.8: size = 3
        else: size = 4

        state = (
            f"SETUP: {r['setup']}\n"
            f"SEGMENT: {r['punchline']}\n"
            f"CONTEXT: speaking at {r['wps']:.1f} words/sec, "
            f"after {r['pause_before']:.1f}s pause, "
            f"{r['pos']:.0%} through the set, "
            f"recent laughs: {r['hist']:.0f}"
        )
        jev_rows.append({
            "state": state,
            "questions": questions,
            "gold": {"will_laugh": r["laugh"] == 1, "laugh_size": size},
            "_meta": {"stem": r["stem"], "t0": r["t0"], "laugh_strength": r["laugh_strength"]}
        })
    return jev_rows


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"

    rows = build_all()
    print(f"\ntotal rows: {len(rows)}, positive: {sum(r['laugh'] for r in rows)}")

    # Save raw rows
    (OUT_DIR / "beats.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows))
    print(f"saved {OUT_DIR}/beats.jsonl")

    if cmd == "jev":
        jev_rows = format_jev(rows)
        (OUT_DIR / "jev_training.jsonl").write_text(
            "\n".join(json.dumps(r) for r in jev_rows))
        print(f"saved {OUT_DIR}/jev_training.jsonl ({len(jev_rows)} rows)")
