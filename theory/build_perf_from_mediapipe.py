"""Build performance.v1 timelines from MediaPipe windows alone (no Omni).

Heuristics (tunable):
- mouth_wide / brow spikes → expression + speak markers
- lean_x_range spikes → lean_in gesture
- arm_open rise → small_gesture
- hand_face drop → mic-hand face touch
- energy proxy = z(mouth_wide) + z(brow_range) + z(lean_x_range)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "killtony-minutes"


def z(vals: np.ndarray) -> np.ndarray:
    if len(vals) < 2:
        return np.zeros_like(vals, dtype=float)
    s = vals.std()
    return (vals - vals.mean()) / (s if s > 1e-6 else 1.0)


def build(granular: dict) -> dict:
    ws = granular.get("numeric_windows") or []
    if not ws:
        return {"version": "performance.v1", "events": [], "n_events": 0}

    def col(k):
        return np.array([w.get(k) if w.get(k) is not None else 0.0 for w in ws], dtype=float)

    mouth = col("mouth_wide_max")
    brow = col("brow_range")
    lean = col("lean_x_range")
    arm = col("arm_open_mean")
    hand = col("hand_face_right_min")
    energy = z(mouth) + z(brow) + z(lean)

    events = []
    for i, w in enumerate(ws):
        t0 = w["t0"]
        # expression from brow + mouth
        if brow[i] > 0.8 and mouth[i] > 0.4:
            expr = "surprised"
        elif brow[i] < 0.15 and mouth[i] < 0.25:
            expr = "deadpan"
        elif mouth[i] > 0.45 and brow[i] < 0.4:
            expr = "smirk"
        elif brow[i] > 0.5 and mouth[i] < 0.3:
            expr = "annoyed"
        else:
            expr = "neutral"
        events.append({"t": t0, "kind": "expression", "value": expr,
                       "energy": round(float(energy[i]), 3)})

        # gesture
        if lean[i] > 0.18:
            events.append({"t": t0, "kind": "gesture", "value": "lean in"})
        elif arm[i] > 0.65 and i > 0 and arm[i] - arm[i - 1] > 0.05:
            events.append({"t": t0, "kind": "gesture", "value": "small gesture"})
        elif hand[i] < 0.35:
            events.append({"t": t0, "kind": "gesture", "value": "hand to face"})

        # speak proxy when mouth active
        if mouth[i] > 0.3:
            events.append({"t": t0, "kind": "speak_start",
                           "value": {"energy": round(float(energy[i]), 3)}})

        # hold still on sudden energy drop after spike (punchline stillness)
        if i > 1 and energy[i - 1] > 1.2 and energy[i] < 0.3:
            events.append({"t": t0, "kind": "hold", "ms": 1200})

    events.sort(key=lambda e: (e["t"], e.get("kind") or ""))
    return {
        "version": "performance.v1",
        "source": granular.get("id"),
        "duration_s": granular.get("mediapipe", {}).get("duration_s"),
        "method": "mediapipe_heuristic_v1",
        "events": events,
        "n_events": len(events),
    }


def main():
    for gpath in sorted(OUT.glob("*.granular.json")):
        g = json.loads(gpath.read_text())
        perf = build(g)
        out = gpath.with_name(gpath.name.replace(".granular.json", ".performance.v1.json"))
        out.write_text(json.dumps(perf, indent=2))
        print(f"{out.name}: {perf['n_events']} events")


if __name__ == "__main__":
    main()
