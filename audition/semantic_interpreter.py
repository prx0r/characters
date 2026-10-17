"""Semantic interpreter: LLM-based joke understanding.

Replaces JEV-first evaluation. Per peer review:
  "JEV is a structured decision model, not a general-purpose
   language-understanding or reasoning model."

  "Transcript → Semantic interpreter → Structured joke representation
   → Predictor / JEV"

Uses Qwen3.8 Omni via OpenRouter for semantic understanding.
JEV is kept as an optional downstream decision component only.

Usage:
  from semantic_interpreter import interpret_joke
  event = interpret_joke(transcript, character_graph, prior_context)
  # returns dict matching schemas/joke_event.json

Required semantic tests (from peer review):
  - Ordinary factual sentence → does not invent a joke mechanism
  - Clear setup+punchline → identifies expectation and reveal
  - Same punchline, different setup → recognizes meaning changes
  - Callback to previous beat → finds earlier reference
  - Sarcastic delivery → distinguishes literal from intended
  - Ralph contradicts identity → grounds in character.json
  - Ambiguous line → reports uncertainty, doesn't fabricate
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

OPENROUTER_MODEL = "qwen/qwen3.8-omni-flash"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Valid mechanisms (must match schemas/joke_event.json)
MECHANISMS = {
    "setup_punchline", "misdirection", "escalation", "callback",
    "self_deprecation", "deadpan", "anti_humor", "sarcasm",
    "absurdism", "blue_humor", "status_reversal",
    "identity_contradiction", "incongruity", "benign_violation",
    "garden_path", "double_interpret", "split_knowledge",
    "expose_self_blindness", "displacement", "not_a_joke",
}


def _get_key(name: str) -> str | None:
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(name)


SYSTEM_PROMPT = """You are a comedy semantic interpreter. Your ONLY job is to \
understand what a joke MEANS — not to predict whether anyone laughs.

You receive:
1. The transcript of what was said
2. Character graph context (who is speaking, their identity, contradictions)
3. Prior context (earlier setup, callbacks)

You output a JSON object describing the joke's structure:
- mechanism: which comedic mechanisms are at work
- setup: what the comedian establishes
- expected: what the audience expects
- reveal: what actually happens
- character_conflict: how this conflicts with character identity
- irony_detected: is there irony?
- literal_meaning vs intended_meaning: for sarcastic/ironic jokes
- confidence_in_interpretation: how sure are you (0.0-1.0)

CRITICAL RULES:
1. If the segment is NOT a joke (ordinary statement, question, etc.), \
set mechanism to ["not_a_joke"] and confidence to 0.9+.
2. If you are UNSURE about the interpretation, set confidence < 0.7 \
and explain in uncertainty_reason. DO NOT fabricate an explanation.
3. Ground character contradictions in the provided character graph. \
Do not invent character traits.
4. Distinguish literal from intended meaning for sarcasm/irony.
5. For callbacks, identify WHAT is being called back to.

Valid mechanisms: setup_punchline, misdirection, escalation, callback, \
self_deprecation, deadpan, anti_humor, sarcasm, absurdism, blue_humor, \
status_reversal, identity_contradiction, incongruity, benign_violation, \
garden_path, double_interpret, split_knowledge, expose_self_blindness, \
displacement, not_a_joke."""


def interpret_joke(
    transcript: str,
    character_graph: dict | str | None = None,
    prior_context: str = "",
    beat_id: str = "",
) -> dict:
    """Interpret a joke using an LLM (Qwen via OpenRouter).

    Args:
        transcript: what was said
        character_graph: who is speaking (dict or JSON string from character.json)
        prior_context: earlier setup, callbacks, previous beats
        beat_id: beat identifier from delivery.json

    Returns:
        dict matching schemas/joke_event.json
    """
    key = _get_key("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not found")

    # Format character context
    if isinstance(character_graph, dict):
        char_ctx = json.dumps(character_graph, indent=2)
    elif isinstance(character_graph, str):
        char_ctx = character_graph
    else:
        char_ctx = "(no character context provided)"

    user_msg = f"""Transcript:
{transcript}

Character context:
{char_ctx}

Prior context (earlier beats, callbacks):
{prior_context or "(none)"}

Interpret this joke. Output JSON matching the schema."""

    import urllib.request

    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/prx0r/characters",
            "X-Title": "Characters Semantic Interpreter",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())

    content = resp["choices"][0]["message"]["content"]
    event = json.loads(content)

    # Validate and normalize
    event.setdefault("joke_id", beat_id or "unknown")
    event.setdefault("beat_id", beat_id)
    event.setdefault("transcript", transcript)

    # Filter mechanisms to valid set
    mechs = event.get("mechanism", [])
    if isinstance(mechs, str):
        mechs = [mechs]
    event["mechanism"] = [m for m in mechs if m in MECHANISMS]
    if not event["mechanism"]:
        event["mechanism"] = ["not_a_joke"]

    # Ensure confidence exists
    event.setdefault("confidence_in_interpretation", 0.5)
    event.setdefault("uncertainty_reason", "")

    return event


def interpret_set(
    beats: list[dict],
    character_graph: dict | None = None,
) -> list[dict]:
    """Interpret a full set of beats sequentially.

    Args:
        beats: list of dicts with 'text' and optionally 'beat_id'
        character_graph: character.json contents

    Returns:
        list of joke events, with prior context accumulated
    """
    events = []
    prior_lines = []

    for beat in beats:
        text = beat.get("text", "")
        beat_id = beat.get("beat_id", "")
        prior = "\n".join(prior_lines[-5:])  # last 5 beats as context

        event = interpret_joke(text, character_graph, prior, beat_id)
        events.append(event)

        # Add to prior context
        summary = f"[{beat_id}] {event.get('setup', '')} → {event.get('reveal', '')}"
        prior_lines.append(summary)

    return events


if __name__ == "__main__":
    # Semantic tests from peer review
    tests = [
        {
            "name": "Ordinary factual sentence",
            "transcript": "The weather is nice today.",
            "expect": "not_a_joke",
        },
        {
            "name": "Clear setup and punchline",
            "transcript": "I told my therapist I was afraid of commitment. She said we should schedule weekly sessions. I said, 'Don't rush me.'",
            "expect": "misdirection or setup_punchline",
        },
        {
            "name": "Ralph contradicts identity",
            "transcript": "I'm an apex predator. I control thirteen bloodlines. Yesterday HR told me I need to work on my people skills.",
            "expect": "status_reversal or identity_contradiction",
        },
        {
            "name": "Ambiguous line",
            "transcript": "That's what she said.",
            "expect": "uncertainty or not_a_joke (context-dependent)",
        },
    ]

    print("Semantic interpreter tests (requires OPENROUTER_API_KEY):")
    print("=" * 60)
    for t in tests:
        print(f"\n{t['name']}:")
        print(f"  Input: {t['transcript'][:80]}...")
        print(f"  Expected: {t['expect']}")
        try:
            event = interpret_joke(t["transcript"])
            print(f"  Got: {event['mechanism']}")
            print(f"  Confidence: {event['confidence_in_interpretation']}")
            print(f"  Setup: {event.get('setup', 'N/A')[:60]}")
            print(f"  Reveal: {event.get('reveal', 'N/A')[:60]}")
        except Exception as e:
            print(f"  Error: {e}")
