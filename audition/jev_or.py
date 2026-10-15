"""Jev via OpenRouter — typed decisions for the voice engine.

Model: typesafe/jev-1.13 on POST /api/alpha/decisions.
$0.042/M input tokens, output free. State + typed questions ->
choice/score/noul with calibrated probabilities. Key: OPENROUTER_API_KEY.

Uses:
- casting: which archetype fits a performer? (choice over archetypes)
- mood function: which modulator given conversation state? (choice)
- rubric judge: is this minute good? (score on our rubric) — model
  proposes, human disposes (AGENTS rule)
- material slot filler priority (score per collision shape)

Usage: python3 jev_or.py decide --state '{"..." }' --question "..."
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"
ENV = Path(__file__).parent / ".env"


def _key() -> str:
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.getenv("OPENROUTER_API_KEY") or ""


def decide(state: dict | str, questions: dict, model: str = MODEL) -> dict:
    """questions: {qid: {type: noul|choice|score, instructions, criteria}}.
    criteria: {key: desc} for noul/choice; ordered list for score."""
    key = _key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY missing")
    body = {"model": model,
            "state": state if isinstance(state, dict) else {"input": str(state)},
            "questions": questions}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"jev decisions HTTP {e.code}: {e.read().decode()[:300]}")


def cast_archetype(performer_summary: str, archetypes: dict[str, str]) -> dict:
    """Which delivery archetype fits this performer? (choice)"""
    q = {"archetype": {"type": "choice",
                       "instructions": "Which delivery archetype best fits this performer's stage persona?",
                       "criteria": archetypes}}
    return decide({"performer": performer_summary}, q)


def pick_modulator(context: str, modulators: dict[str, str]) -> dict:
    """Mood function: which modulator given conversation state? (choice)"""
    q = {"mood": {"type": "choice",
                  "instructions": "Which emotional modulator fits this conversation moment for the character?",
                  "criteria": modulators}}
    return decide({"context": context}, q)


def judge_minute(minute_summary: dict) -> dict:
    """Score a minute on delivery quality (model proposes; human disposes)."""
    q = {"quality": {"type": "score",
                     "instructions": "How strong is this comedy minute overall (delivery + timing + character)?",
                     "criteria": ["weak delivery, misses timing", "competent, some moments",
                                  "strong delivery, timing lands"]},
         "landed": {"type": "noul",
                    "instructions": "Would this minute get strong audience laughter?",
                    "criteria": {"true": "delivery + material clearly land",
                                 "false": "flat or mistimed"}}}
    return decide(minute_summary, q)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide")
    d.add_argument("--state", required=True)
    d.add_argument("--questions", required=True, help="JSON record")
    d.add_argument("--model", default=MODEL)
    t = sub.add_parser("test", help="smoke test the connection")
    args = ap.parse_args()
    if args.cmd == "test":
        out = decide({"ticket": "checkout broken"},
                     {"is_bug": {"type": "noul",
                                 "instructions": "Is this a software defect?",
                                 "criteria": {"true": "broken behavior",
                                              "false": "question or request"}}})
        print(json.dumps(out.get("answers", out), indent=1)[:400])
        print("cost:", out.get("usage", {}).get("cost"))
    elif args.cmd == "decide":
        out = decide(args.state if args.state.startswith("{") else {"input": args.state},
                     json.loads(args.questions), args.model)
        print(json.dumps(out, indent=1)[:2000])
