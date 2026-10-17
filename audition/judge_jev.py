"""JEV as a candidate laughter judge — NOT the final authority.

Per user spec (2026-10-17):
  JEV produces a reaction distribution. A separate calibrator learns
  the mapping from JEV confidence to actual human laugh rates.

  "If Jev says strong_laugh with 0.9 confidence, that does NOT mean
   90% of humans will laugh hard. You need observed reactions to
   establish that mapping."

Usage:
  from judge_jev import judge_event, judge_batch
  prediction = judge_event(event)  # JEV's opinion
  calibrated = calibrator.calibrate(prediction, audience_profile)  # learned mapping
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

# JEV reaction categories
REACTIONS = ["silence", "chuckle", "laugh", "big_laugh", "roar"]
REACTION_ORDER = {r: i for i, r in enumerate(REACTIONS)}

# JEV questions (from spec)
JEV_QUESTIONS = [
    "audible_laughter_likely",
    "reaction_strength",
    "reaction_type",
    "reveal_understood",
    "needs_human_review",
]


def _get_key(name: str) -> str | None:
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(name)


def judge_event(event: dict) -> dict:
    """Ask JEV to judge a comedy event.

    Returns JEV's raw opinion — NOT calibrated to human laugh rates.
    The calibrator (calibrate_laughter.py) learns the mapping.
    """
    key = _get_key("OPENROUTER_API_KEY")
    if not key:
        # Fallback: rule-based judge (no API needed)
        return _rule_based_judge(event)

    prompt = f"""You are JEV, a comedy audience simulator. Judge this comedy event.

Event:
- Setup: {event.get('setup', 'N/A')}
- Expected: {event.get('expected', 'N/A')}
- Reveal: {event.get('reveal', 'N/A')}
- Primary mechanism: {event.get('primary_mechanism', 'incongruity')}
- Delivery style: {event.get('delivery', {}).get('style', 'moderate')}
- Pace: {event.get('delivery', {}).get('pace_wpm', 0)} wpm
- Pause before reveal: {event.get('delivery', {}).get('pause_before_reveal_ms', 0)} ms
- Vocal energy: {event.get('delivery', {}).get('vocal_energy', 'moderate')}
- Punchline understood: {event.get('interpretation', {}).get('punchline_understood', True)}
- Weakness: {event.get('interpretation', {}).get('possible_weakness', 'none')}

Answer these questions with calibrated probabilities (0.0-1.0):

1. audible_laughter_likely: Probability this produces audible laughter in a typical comedy club audience.
2. reaction_strength: Expected strength on scale 0-4 (0=silence, 1=chuckle, 2=laugh, 3=big_laugh, 4=roar).
3. reaction_type: Most likely reaction category (silence/chuckle/laugh/big_laugh/roar).
4. reveal_understood: Probability the audience understands the reveal.
5. needs_human_review: Probability this joke should be flagged for human review.

Output JSON: {{"audible_laughter_likely": 0.0, "reaction_strength": 0, "reaction_type": "silence", "reveal_understood": 0.0, "needs_human_review": 0.0}}"""

    import urllib.request

    body = json.dumps({
        "model": "anthropic/claude-haiku-4.5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        content = resp["choices"][0]["message"]["content"]
        judge = json.loads(content)
        judge["source"] = "jev_api"
        return judge
    except Exception:
        return _rule_based_judge(event)


def _rule_based_judge(event: dict) -> dict:
    """Fallback rule-based judge when API is unavailable.

    Uses comedy theory: certain mechanisms + delivery patterns predict laughter.
    This is NOT learned — it's a starting point the calibrator improves on.
    """
    mech = event.get("primary_mechanism", "incongruity")
    style = event.get("delivery", {}).get("style", "moderate")
    energy = event.get("delivery", {}).get("vocal_energy", "moderate")
    understood = event.get("interpretation", {}).get("punchline_understood", True)
    weakness = event.get("interpretation", {}).get("possible_weakness", "")

    # Base probability by mechanism (theory-driven priors)
    mech_prob = {
        "status_reversal": 0.75, "identity_contradiction": 0.70,
        "misdirection": 0.72, "setup_punchline": 0.65,
        "escalation": 0.68, "callback": 0.70,
        "self_deprecation": 0.60, "deadpan": 0.55,
        "anti_humor": 0.45, "sarcasm": 0.58,
        "absurdism": 0.50, "blue_humor": 0.70,
        "incongruity": 0.60, "benign_violation": 0.65,
        "garden_path": 0.62, "double_interpret": 0.60,
        "split_knowledge": 0.65, "expose_self_blindness": 0.55,
        "displacement": 0.50,
    }
    prob = mech_prob.get(mech, 0.55)

    # Delivery modifiers
    if energy == "explosive":
        prob += 0.10
    elif energy == "restrained":
        prob -= 0.05
    if style == "deadpan":
        prob -= 0.05  # harder to land
    if not understood:
        prob -= 0.20
    if weakness:
        prob -= 0.05

    prob = max(0.0, min(1.0, prob))

    # Map probability to reaction strength
    if prob < 0.3:
        strength, rtype = 0, "silence"
    elif prob < 0.5:
        strength, rtype = 1, "chuckle"
    elif prob < 0.7:
        strength, rtype = 2, "laugh"
    elif prob < 0.85:
        strength, rtype = 3, "big_laugh"
    else:
        strength, rtype = 4, "roar"

    return {
        "audible_laughter_likely": round(prob, 3),
        "reaction_strength": strength,
        "reaction_type": rtype,
        "reveal_understood": 0.85 if understood else 0.40,
        "needs_human_review": 0.3 if weakness else 0.1,
        "source": "rule_based",
    }


def judge_batch(events: list[dict]) -> list[dict]:
    """Judge a batch of events."""
    return [judge_event(e) for e in events]


if __name__ == "__main__":
    # Demo
    event = {
        "setup": "Ralph claims overwhelming power",
        "expected": "Nobody can question his authority",
        "reveal": "HR evaluates his conduct",
        "primary_mechanism": "status_reversal",
        "delivery": {"style": "dry", "vocal_energy": "restrained", "pace_wpm": 165},
        "interpretation": {"punchline_understood": True, "possible_weakness": ""},
    }
    result = judge_event(event)
    print(json.dumps(result, indent=2))
