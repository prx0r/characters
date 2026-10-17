"""Build comedy events with ground truth from ASR + AM events.

Loads the 5 AM specials, builds events per beat, attaches ground truth.
Output: events JSONL ready for ab_predictor_experiment.py.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ASR_DIR = Path("/home/box/comedy-audio/asr")
AM_DIR = Path("/home/box/comedy-audio/am_events")
OUT = Path(__file__).parent / "voicelab" / "comedy_events.jsonl"


def build_events_for_special(stem: str) -> list[dict]:
    """Build comedy events from ASR words + AM laugh events."""
    asr_p = ASR_DIR / f"{stem}.json"
    am_p = AM_DIR / f"{stem}.json"

    if not asr_p.exists() or not am_p.exists():
        return []

    words = json.loads(asr_p.read_text())["words"]
    am_events = json.loads(am_p.read_text())

    if len(words) < 10:
        return []

    # Segment into ~6s beats
    WINDOW = 6.0
    STEP = 3.0
    total_dur = words[-1]["end"] - words[0]["start"]

    events = []
    for w_start in range(0, int(total_dur), int(STEP)):
        w_end = w_start + WINDOW

        # Find words in this window
        beat_words = [w for w in words if w["start"] >= w_start and w["start"] < w_end]
        if len(beat_words) < 3:
            continue

        transcript = " ".join(w["text"] for w in beat_words)
        if len(transcript) < 20:
            continue

        # Measured features
        gaps = [beat_words[i+1]["start"] - beat_words[i]["end"] for i in range(len(beat_words)-1)]
        wps = len(beat_words) / max(WINDOW, 0.1)
        pause_mean = sum(gaps) / max(len(gaps), 1) if gaps else 0

        # Ground truth: laugh in [w_end - 0.5, w_end + 2.0]
        laugh_detected = False
        laugh_strength = 0.0
        for a_start, a_end, a_strength in am_events:
            if a_start >= w_end - 0.5 and a_start <= w_end + 2.0:
                laugh_detected = True
                laugh_strength = max(laugh_strength, a_strength)

        # Position in set
        pos = w_start / max(total_dur, 1)

        # Hist: laughs so far
        hist = sum(1 for a_start, _, _ in am_events if a_start < w_start)
        hist_rate = hist / max(w_start / 10, 1)

        event = {
            "schema": "comedy.event.v1",
            "joke_id": f"{stem}-{w_start}",
            "special": stem,
            "timestamp": {"start_ms": w_start * 1000, "end_ms": w_end * 1000},
            "transcript": transcript,
            "measured": {
                "wps": round(wps, 2),
                "pause_mean_ms": round(pause_mean * 1000),
                "pos": round(pos, 3),
                "hist_rate": round(hist_rate, 3),
                "n_words": len(beat_words),
            },
            "ground_truth": {
                "laugh_detected": laugh_detected,
                "laugh_strength": laugh_strength,
            },
        }
        events.append(event)

    return events


def main():
    all_events = []
    for am_file in sorted(AM_DIR.glob("*.json")):
        stem = am_file.stem
        events = build_events_for_special(stem)
        n_laugh = sum(1 for e in events if e["ground_truth"]["laugh_detected"])
        print(f"{stem}: {len(events)} events, {n_laugh} laughs ({n_laugh/max(len(events),1)*100:.0f}%)")
        all_events.extend(events)

    # Save
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\n")

    n_laugh = sum(1 for e in all_events if e["ground_truth"]["laugh_detected"])
    print(f"\nTotal: {len(all_events)} events, {n_laugh} laughs ({n_laugh/max(len(all_events),1)*100:.0f}%)")
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
