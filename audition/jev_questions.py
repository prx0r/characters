"""Canonical Jev questions — every decision point in the engine, typed.

Each builder returns (state, questions) ready for jev.ask/decide.
No key -> callers fall back to bandit/heuristics; questions stay identical
so behavior is comparable across choosers. All confidences recorded.
"""
from __future__ import annotations


def seed_state(character: dict, scenario: dict, memories: list[str],
               strategy_note: str = "", performance_brief: str = "") -> dict:
    """Compile seed + scenario + memory + performance into Jev-readable state.

    performance_brief: from store.format_performance_brief() — past battle
    scores + POGs by modulator. Jev uses this to tilt toward proven
    modulators. Empty = all unproven (explore freely).
    """
    raw = character.get("raw", {}) or {}
    phil = raw.get("philosophy", {}) or {}
    return {
        "character": character.get("name"),
        "ontology": phil.get("ontology", ""),
        "epistemology": phil.get("epistemology", ""),
        "axiology": phil.get("axiology", ""),
        "causality": phil.get("causality", ""),
        "agency": phil.get("agency", ""),
        "self_model": ((character.get("raw", {}) or {}).get("dramatic_core", {}) or {}).get("self_model", ""),
        "blind_spots": character.get("blind_spots", []),
        "misinterpretation_rule": raw.get("misinterpretation_rule", ""),
        "awareness": raw.get("awareness", "unknown"),
        "restraint": ((raw.get("expression", {}) or {}).get("emotional_restraint", "medium")),
        "scenario": scenario.get("id"),
        "situation": (scenario.get("comic_model") or scenario.get("comic_claim") or "")[:300],
        "memories": memories[-3:],
        "evidence": (strategy_note or "")[:300],
        "performance": (performance_brief or "")[:800],
    }


def q_modulator(options: list[str], tilts: dict) -> dict:
    return {"modulator": {"type": "choice",
                          "instructions": "Which performance mood best serves this character's philosophy in this scenario given the evidence AND past performance? Prefer modulators with high battle scores in the performance history, unless the scenario clearly demands a different energy. Unscored modulators are fair game for exploration.",
                          "criteria": {o: tilts.get(o, o)[:120] for o in options}}}


def q_operator(options: list[str], hyps: dict) -> dict:
    return {"operator": {"type": "choice",
                         "instructions": "Which comic operation best reveals the absurdity of what this mind is doing?",
                         "criteria": {o: hyps.get(o, o)[:120] for o in options}}}


def q_appraisal() -> dict:
    return {
        "status_threatened": {"type": "noul",
                              "instructions": "Does the scenario threaten the character's status or self-model?"},
        "blind_spot_armed": {"type": "noul",
                             "instructions": "Is the character's blind spot directly engaged by this scenario?"},
        "play_frame": {"type": "noul",
                       "instructions": "Is there a play frame (deadpan ritual, venue, formality) making violation safe?"},
        "benign_ready": {"type": "noul",
                         "instructions": "Is the violation distance, weak commitment, or alternative norm present?"},
    }


def q_vetoes() -> dict:
    return {
        "character_swappable": {"type": "noul",
                                "instructions": "Could a different character deliver this minute unchanged?"},
        "generic_ai_humor": {"type": "noul",
                             "instructions": "Is this generic AI humor with a name inserted?"},
        "reframe_present": {"type": "noul",
                            "instructions": "Does a perspective shift actually occur (not just a topic)?"},
    }
