"""Funnier pre-filter — Jev scores premise BEFORE expensive generation.

A full generate_minute costs an LLM call + TTS + battle scoring.
The pre-filter costs one cheap Jev judgment on (scenario + modulator +
operator + character voice) and kills obvious duds before spending.

Rules:
  - EXPLOIT path: prefilter applies (we think we know what works — verify cheap).
  - EXPLORE path: bypasses prefilter (the point is trying unproven combos).
  - No key / Jev failure: pass-through (never block on infra failure).
  - Threshold 0.4: below = skip candidate, battle tries next combo.

Expected savings: ~80% of exploit-path duds killed at ~1% of generation cost.
"""
from __future__ import annotations


def prefilter_questions() -> dict:
    """Jev question set for premise viability."""
    return {
        "has_comic_potential": {
            "type": "noul",
            "instructions": "Does this scenario + character + approach combination have genuine comic potential? A clear collision between the character's worldview and the situation, with room for escalation? Answer no for generic setups with no tension.",
        },
        "voice_fit": {
            "type": "noul",
            "instructions": "Does this modulator fit this character's established voice? Would fans recognize this as authentic to the character, not generic comedy wearing their name?",
        },
    }


def prefilter_state(character: dict, scenario: dict) -> dict:
    """Minimal state for the pre-filter judgment (small = cheap)."""
    phil = ((character.get("raw", {}) or {}).get("philosophy", {}) or {})
    return {
        "character": character.get("name", ""),
        "voice": str(phil.get("register", "") or phil.get("ontology", ""))[:200],
        "scenario": scenario.get("id", ""),
        "premise": (scenario.get("comic_model")
                    or scenario.get("comic_claim", ""))[:300],
    }


def judge_premise(character: dict, scenario: dict) -> dict:
    """Run pre-filter judgment. Returns {pass, score, reason}.

    Fail-open: any error → pass=True (never block generation on infra).
    """
    try:
        import jev as _jev
    except ImportError:
        return {"pass": True, "score": 0.5, "reason": "no jev — pass-through"}
    try:
        state = prefilter_state(character, scenario)
        answers = _jev.ask(state, prefilter_questions())
        if not isinstance(answers, dict):
            return {"pass": True, "score": 0.5, "reason": "bad response, pass-through"}
        pot = answers.get("has_comic_potential", {})
        fit = answers.get("voice_fit", {})
        p_score = float(pot.get("noul", 0.5)) if isinstance(pot, dict) else 0.5
        f_score = float(fit.get("noul", 0.5)) if isinstance(fit, dict) else 0.5
        score = round(p_score * 0.6 + f_score * 0.4, 2)
        passed = score >= 0.4
        return {"pass": passed, "score": score,
                "reason": f"potential={p_score} fit={f_score}"}
    except Exception as e:
        return {"pass": True, "score": 0.5,
                "reason": f"jev error, pass-through: {e}"[:150]}
