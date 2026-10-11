"""Performance gates — what gets spoken must be speakable.

Hard vetoes fail validation. Soft flags route to human. The TTS reads
beats verbatim, so anything unspeakable in text is unspeakable on stage.
"""
from __future__ import annotations

import re

LABELS = re.compile(r"(?i)^(blind spot|setup|punchline|closer|tag|callback|misdirect|escalation|opener|beat|pause|emphasis)\s*:")
JARGON = ["reframe cruelty", "operator", "modulator", "rigidify", "displacement",
          "misinterpretation", "double_interpret", "status_invert", "identity_contradict"]
SELF_THIRD = re.compile(r"\b[Hh]e\b|\b[Hh]im\b|\b[Hh]is\b")


def check(beats: list[dict], others_present: list[str] | None = None) -> dict:
    """Returns {vetoes: [...], flags: [...], passed: bool}."""
    others = [o.lower() for o in (others_present or [])]
    vetoes, flags = [], []
    full = " ".join(b.get("text", "") for b in beats)
    for b in beats:
        t = b.get("text", "")
        if LABELS.search(t.strip()):
            vetoes.append(f"{b['id']}: stage-direction label spoken aloud")
        for j in JARGON:
            if j.lower() in t.lower():
                vetoes.append(f"{b['id']}: internal jargon on stage ({j})")
    # third-person self-reference: he/him/his with no other male entity around
    if SELF_THIRD.search(full):
        if not any(o in full.lower() for o in others):
            flags.append("third-person pronoun without a clear other; likely self-reference bug")
    # shape
    if beats:
        if len(beats[0].get("text", "").split()) < 6:
            flags.append("b1 too short to be a cold-open joke")
        if len(beats[-1].get("text", "").split()) > 12:
            vetoes.append("closer over 12 words")
    return {"vetoes": vetoes, "flags": flags, "passed": not vetoes}
