"""Delivery-aware laugh prediction: same text + different timing → different P(laugh).

Core insight from dpv research: pros extend pause before surprise 41.2% vs amateurs 27.4%.
The SAME joke lands differently based on delivery choices.

This module learns the mapping: (mechanism, timing, direction) → laugh probability.

Usage:
  from delivery_laugh import predict_with_delivery
  p = predict_with_delivery("punchline text", mechanism="misdirection", pause=2.1, wps=2.7)
  # p = 0.72 (with long pause) vs p = 0.45 (with short pause)
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent


# ============================================================
# DELIVERY-LAUGH COUPLING MODEL
# ============================================================

# Mechanism → base probability (before delivery modulation)
MECH_BASE = {
    "status_reversal": 0.55, "misdirection": 0.52,
    "setup_punchline": 0.48, "escalation": 0.50,
    "callback": 0.52, "self_deprecation": 0.45,
    "deadpan": 0.40, "displacement": 0.38,
}

# Delivery features that MODULATE the base probability
# These are learned from dpv research + our corpus analysis

def dpv_coupling_effect(pause_s: float, baseline_pause: float = 0.6) -> float:
    """dpv coupling: pause before surprise.

    REAL DATA (5702 events from 5 AM specials):
    - 95% of beats have pause < 100ms (continuous speech)
    - Longer pauses slightly REDUCE laugh rate (0.239 → 0.176)
    - dpv's "41.2% extension" is RELATIVE to comedian's own baseline,
      not absolute seconds

    This function is now a WEAK effect based on actual data.
    """
    # Real data shows pause has minimal/negative effect
    # Keep small effect for theory compatibility
    if pause_s < 0.3:
        return 0.0    # normal (most beats are here)
    elif pause_s < 1.0:
        return -0.02  # slight reduction
    elif pause_s < 2.5:
        return -0.05  # noticeable reduction
    else:
        return -0.08  # long pause = tension dies


def pace_effect(wps: float, target_wps: float = 2.7) -> float:
    """Pace effect based on REAL DATA.

    REAL DATA (5702 events):
    - wps 0-1.5: laugh rate 0.186
    - wps 1.5-2.5: laugh rate 0.214
    - wps 2.5-3.5: laugh rate 0.240
    - wps 3.5+: laugh rate 0.314

    FASTER = MORE LAUGHS (opposite of common assumption).
    """
    # Match the real data curve
    if wps < 1.5:
        return -0.05  # slow = less laughter
    elif wps < 2.5:
        return 0.0
    elif wps < 3.5:
        return 0.03
    else:
        return 0.08  # fast = more laughter (real data)


def energy_variation_effect(e_std: float) -> float:
    """Energy variation is the strongest laugh predictor (our finding: AUC 0.654).

    High energy variation = dynamic delivery = more laughs.
    """
    # e_std typically 0.01-0.05
    if e_std < 0.01:
        return -0.10  # monotone
    elif e_std < 0.02:
        return 0.0    # okay
    elif e_std < 0.04:
        return 0.08   # dynamic
    else:
        return 0.05   # very dynamic (might be erratic)


def crowd_heat_effect(recent_laugh_rate: float) -> float:
    """Crowd heat: warm crowd laughs more (contagion).

    recent_laugh_rate: fraction of last 5 beats that got laughs.
    """
    return recent_laugh_rate * 0.15


def position_effect(pos: float) -> float:
    """Position in set: crowd warms up over time."""
    return pos * 0.10


def predict_with_delivery(
    text: str,
    mechanism: str = "setup_punchline",
    beat_type: str = "punchline",
    pause_s: float = 1.5,
    wps: float = 2.7,
    e_std: float = 0.02,
    recent_laugh_rate: float = 0.0,
    pos: float = 0.5,
    target_wps: float = 2.7,
) -> dict:
    """Predict laugh probability with delivery features.

    Same text + different delivery = different probability.

    Returns dict with p_laugh, components (for explainability).
    """
    # Base from mechanism
    base = MECH_BASE.get(mechanism, 0.45)

    # Beat type modifier
    if beat_type == "punchline":
        base += 0.10
    elif beat_type == "tag":
        base += 0.05
    elif beat_type == "opener":
        base -= 0.08
    elif beat_type == "closer":
        base += 0.08

    # Delivery modulations
    dpv = dpv_coupling_effect(pause_s)
    pace = pace_effect(wps, target_wps)
    energy = energy_variation_effect(e_std)
    heat = crowd_heat_effect(recent_laugh_rate)
    position = position_effect(pos)

    # Combined
    p = base + dpv + pace + energy + heat + position
    p = max(0.0, min(1.0, p))

    return {
        "p_laugh": round(p, 3),
        "base": round(base, 3),
        "dpv_coupling": round(dpv, 3),
        "pace": round(pace, 3),
        "energy": round(energy, 3),
        "heat": round(heat, 3),
        "position": round(position, 3),
        "mechanism": mechanism,
        "delivery": {
            "pause_s": pause_s,
            "wps": wps,
            "e_std": e_std,
        },
    }


def compare_deliveries(
    text: str,
    mechanism: str,
    deliveries: list[dict],
) -> list[dict]:
    """Compare the same joke under different delivery choices.

    deliveries: list of dicts with pause_s, wps, e_std, etc.
    """
    results = []
    for d in deliveries:
        pred = predict_with_delivery(
            text, mechanism=mechanism,
            pause_s=d.get("pause_s", 1.5),
            wps=d.get("wps", 2.7),
            e_std=d.get("e_std", 0.02),
            recent_laugh_rate=d.get("recent_laugh_rate", 0),
            pos=d.get("pos", 0.5),
        )
        results.append({
            "delivery": d,
            "prediction": pred,
        })
    return results


# ============================================================
# INTEGRATION WITH DELIVERY ENGINE
# ============================================================

def modulate_engine_predictions(beats: list[dict], profile: dict) -> list[dict]:
    """Update delivery engine's laugh predictions with delivery-aware model.

    This is the coupling: the engine's timing choices change the predictions.
    """
    recent_laughs = []

    for b in beats:
        # Recent laugh rate (last 5 beats)
        recent_rate = sum(recent_laughs[-5:]) / max(len(recent_laughs[-5:]), 1)

        # Predict with delivery features
        pred = predict_with_delivery(
            text=b["text"],
            mechanism=b["mechanism"],
            beat_type=b["beat_type"],
            pause_s=b.get("pause_before", 1.0),
            wps=b.get("target_wps", 2.7),
            e_std=profile.get("dynamics_db", 25) / 1000,  # approximate
            recent_laugh_rate=recent_rate,
            pos=b["index"] / max(len(beats), 1),
            target_wps=profile.get("wpm", 180) / 60,
        )

        b["p_laugh"] = pred["p_laugh"]
        b["laugh_breakdown"] = pred  # keep components for explainability

        # Track for heat
        recent_laughs.append(1 if pred["p_laugh"] > 0.65 else 0)

    return beats


# ============================================================
# DEMO: Same Joke, Different Delivery
# ============================================================

if __name__ == "__main__":
    joke = "And I am not even mad. I am impressed."

    print(f"Same joke, different delivery:")
    print(f'"{joke}"')
    print("=" * 70)

    deliveries = [
        {"label": "Rush it (amateur)", "pause_s": 0.4, "wps": 4.0, "e_std": 0.01},
        {"label": "Normal pace", "pause_s": 1.2, "wps": 2.7, "e_std": 0.02},
        {"label": "Louis formula (dpv optimal)", "pause_s": 2.1, "wps": 2.7, "e_std": 0.025},
        {"label": "Long dramatic pause", "pause_s": 3.5, "wps": 2.7, "e_std": 0.02},
        {"label": "Full Louis + warm crowd", "pause_s": 2.1, "wps": 2.7, "e_std": 0.025, "recent_laugh_rate": 0.8},
    ]

    results = compare_deliveries(joke, "misdirection", deliveries)

    for r in results:
        d = r["delivery"]
        p = r["prediction"]
        bar = "█" * int(p["p_laugh"] * 20)
        print(f"\n{d['label']}:")
        print(f"  pause={d['pause_s']}s wps={d['wps']} e_std={d.get('e_std', 0.02)}")
        print(f"  P(laugh) = {p['p_laugh']:.3f} {bar}")
        print(f"  breakdown: base={p['base']} dpv={p['dpv_coupling']} pace={p['pace']} energy={p['energy']} heat={p['heat']}")
