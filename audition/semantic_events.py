"""Semantic event model: Qwen observation → structured comedy event.

This is NOT a neural network. It's a well-designed JSON schema that Qwen
fills and this code validates + enriches with measured features.

Event flow: expectation → reveal → surprise → character contradiction

Usage:
  from semantic_events import build_event, validate_event
  event = build_event(observation, measured_features)
  assert validate_event(event)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

# Valid comedy mechanisms (superset of Qwen's enum)
MECHANISMS = {
    "setup_punchline", "misdirection", "escalation", "callback",
    "self_deprecation", "deadpan", "anti_humor", "sarcasm", "absurdism",
    "blue_humor", "status_reversal", "identity_contradiction",
    "incongruity", "benign_violation", "garden_path", "double_interpret",
    "split_knowledge", "expose_self_blindness", "displacement",
}

# Mapping mechanism → theory (from LAUGHTER-THEORIES.md)
MECHANISM_THEORY = {
    "setup_punchline": "incongruity",
    "misdirection": "incongruity",
    "escalation": "incongruity",
    "callback": "incongruity",
    "self_deprecation": "superiority",
    "deadpan": "incongruity",
    "anti_humor": "incongruity",
    "sarcasm": "superiority",
    "absurdism": "incongruity",
    "blue_humor": "benign_violation",
    "status_reversal": "superiority",
    "identity_contradiction": "incongruity",
    "incongruity": "incongruity",
    "benign_violation": "benign_violation",
    "garden_path": "incongruity",
    "double_interpret": "incongruity",
    "split_knowledge": "incongruity",
    "expose_self_blindness": "superiority",
    "displacement": "relief",
}

# Mechanism → expected laugh characteristics (from laugh_types.json)
MECHANISM_LAUGH_TYPE = {
    "setup_punchline": "burst",
    "misdirection": "cackle",
    "escalation": "roar",
    "callback": "chuckle_wave",
    "self_deprecation": "warm_chuckle",
    "deadpan": "snort",
    "anti_humor": "confused_chuckle",
    "sarcasm": "chuckle_wave",
    "absurdism": "giggle_fit",
    "blue_humor": "roar",
    "status_reversal": "roar",
    "identity_contradiction": "cackle",
    "incongruity": "burst",
    "benign_violation": "roar",
    "garden_path": "burst",
    "double_interpret": "cackle",
    "split_knowledge": "chuckle_wave",
    "expose_self_blindness": "warm_chuckle",
    "displacement": "chuckle_wave",
}


def build_event(
    observation: dict,
    measured_features: dict | None = None,
) -> dict:
    """Convert a Qwen observation into a validated comedy event.

    The event is the handoff between Layer 1 (observer) and Layer 3 (judges).
    """
    obs = observation
    sem = obs.get("semantics", {})
    deliv = obs.get("delivery", {})
    interp = obs.get("interpretation", {})
    evidence = obs.get("evidence", {})
    measured = measured_features or {}

    # Validate mechanisms
    mechanisms = [m for m in sem.get("mechanisms", []) if m in MECHANISMS]
    if not mechanisms:
        mechanisms = ["incongruity"]  # default

    # Theory mapping
    primary_mech = mechanisms[0]
    theory = MECHANISM_THEORY.get(primary_mech, "incongruity")
    expected_laugh = MECHANISM_LAUGH_TYPE.get(primary_mech, "burst")

    # Merge measured delivery features (don't let Qwen fabricate)
    pace = measured.get("wpm") or deliv.get("pace_wpm", 0)
    pause_ms = measured.get("pause_before_punchline_ms") or deliv.get("pause_before_reveal_ms", 0)

    event = {
        "schema": "comedy.event.v1",
        "joke_id": obs.get("joke_id", "unknown"),
        "timestamp": {
            "start_ms": evidence.get("start_ms", 0),
            "end_ms": evidence.get("end_ms", 0),
        },
        "transcript": evidence.get("transcript", ""),
        "mechanisms": mechanisms,
        "primary_mechanism": primary_mech,
        "theory": theory,
        "expected_laugh_type": expected_laugh,
        "setup": sem.get("setup", ""),
        "expected": sem.get("expected", ""),
        "reveal": sem.get("reveal", ""),
        "requires_prior_context": sem.get("requires_prior_context", False),
        "character_reference": sem.get("character_reference", ""),
        "delivery": {
            "style": deliv.get("style", "moderate"),
            "vocal_energy": deliv.get("vocal_energy", "moderate"),
            "pace_wpm": pace,
            "pause_before_reveal_ms": pause_ms,
            "emphasis": deliv.get("emphasis", []),
        },
        "measured": measured,
        "interpretation": {
            "punchline_understood": interp.get("punchline_understood", True),
            "possible_weakness": interp.get("possible_weakness", ""),
        },
    }
    return event


def validate_event(event: dict) -> bool:
    """Validate a comedy event has all required fields and valid values."""
    required = ["schema", "joke_id", "mechanisms", "primary_mechanism",
                "theory", "delivery", "measured"]
    for field in required:
        if field not in event:
            return False
    if event["primary_mechanism"] not in MECHANISMS:
        return False
    if not event["mechanisms"]:
        return False
    return True


def enrich_with_am_event(event: dict, am_events: list) -> dict:
    """Attach ground-truth laughter if AM event exists near this joke.

    am_events: list of [start_s, end_s, strength] from AM detector.
    """
    start_s = event["timestamp"]["start_ms"] / 1000
    end_s = event["timestamp"]["end_ms"] / 1000

    # Look for laugh in [end_s - 0.5, end_s + 2.0]
    best = None
    for a_start, a_end, a_strength in am_events:
        if a_start >= end_s - 0.5 and a_start <= end_s + 2.0:
            if best is None or a_strength > best[2]:
                best = (a_start, a_end, a_strength)

    if best:
        event["ground_truth"] = {
            "laugh_detected": True,
            "laugh_start_s": best[0],
            "laugh_end_s": best[1],
            "laugh_strength": best[2],
            "delay_ms": int((best[0] - end_s) * 1000),
        }
    else:
        event["ground_truth"] = {"laugh_detected": False}

    return event


def batch_build(observations: list[dict], features_list: list[dict]) -> list[dict]:
    """Build events from a batch of observations."""
    events = []
    for i, obs in enumerate(observations):
        feats = features_list[i] if i < len(features_list) else {}
        event = build_event(obs, feats)
        if validate_event(event):
            events.append(event)
    return events


if __name__ == "__main__":
    # Demo: build an event from a sample observation
    sample_obs = {
        "joke_id": "demo-001",
        "evidence": {
            "transcript": "HR told me I need to work on my people skills.",
            "start_ms": 12200, "end_ms": 16600,
        },
        "semantics": {
            "setup": "Ralph claims overwhelming power",
            "expected": "Nobody can question his authority",
            "reveal": "Human Resources evaluates his conduct",
            "mechanisms": ["status_reversal", "identity_contradiction"],
            "character_reference": "ralph.status_model",
            "requires_prior_context": True,
        },
        "delivery": {"style": "dry", "vocal_energy": "restrained"},
        "interpretation": {"punchline_understood": True, "possible_weakness": ""},
    }
    event = build_event(sample_obs, {"wpm": 165, "pause_before_punchline_ms": 360})
    print(json.dumps(event, indent=2))
    print(f"\nValid: {validate_event(event)}")
