"""Qwen3.8 Omni observer: audio + transcript + character context → structured comedy observation.

Architecture (per user spec 2026-10-17):
  Layer 1: Qwen Omni — the observer
    What was said? How was it delivered? What was the intended joke?

  Layer 2: semantic_events.py — expectation → reveal → surprise → contradiction

  Layer 3: judge_jev.py + calibrate_laughter.py — the judges

  Layer 4: audience renderer (future)

Key principle: Don't make Qwen guess facts software can measure.
ASR gives word timestamps. librosa gives energy. Qwen interprets MEANING.

Usage:
  from observer_qwen import observe_minute
  obs = observe_minute(audio_path, transcript, character_context)
  # returns dict matching comedy.observation.v1 schema
"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
from typing import Any

# OpenRouter config
OPENROUTER_MODEL = "qwen/qwen3.8-omni-flash"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Alibaba realtime (for live mode later)
ALIBABA_REALTIME_MODEL = "qwen3.8-omni-flash-realtime"


def _get_key(name: str) -> str | None:
    """Read key from .env without printing it."""
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(name)


OBSERVATION_SCHEMA = {
    "schema": "comedy.observation.v1",
    "required": ["joke_id", "evidence", "semantics", "delivery", "interpretation"],
    "properties": {
        "joke_id": {"type": "string"},
        "evidence": {
            "type": "object",
            "properties": {
                "transcript": {"type": "string"},
                "start_ms": {"type": "integer"},
                "end_ms": {"type": "integer"},
                "audio_source": {"type": "string"},
            },
        },
        "semantics": {
            "type": "object",
            "properties": {
                "setup": {"type": "string"},
                "expected": {"type": "string"},
                "reveal": {"type": "string"},
                "mechanisms": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "setup_punchline", "misdirection", "escalation",
                            "callback", "self_deprecation", "deadpan",
                            "anti_humor", "sarcasm", "absurdism", "blue_humor",
                            "status_reversal", "identity_contradiction",
                            "incongruity", "benign_violation",
                            "garden_path", "double_interpret",
                            "split_knowledge", "expose_self_blindness",
                            "displacement",
                        ],
                    },
                },
                "character_reference": {"type": "string"},
                "requires_prior_context": {"type": "boolean"},
            },
        },
        "delivery": {
            "type": "object",
            "properties": {
                "style": {"type": "string"},
                "pause_before_reveal_ms": {"type": "integer"},
                "emphasis": {"type": "array", "items": {"type": "string"}},
                "vocal_energy": {"type": "string"},
            },
        },
        "interpretation": {
            "type": "object",
            "properties": {
                "punchline_understood": {"type": "boolean"},
                "possible_weakness": {"type": "string"},
            },
        },
    },
}

# Qwen prompt: focused on meaning, not measurement
SYSTEM_PROMPT = """You are a comedy analyst. You receive a transcript segment, \
measured audio features (from software, not you), and character context.

Your job: identify the JOKE STRUCTURE — what's the setup, what did the audience \
expect, what's the reveal, and which comedic mechanisms are at work.

You do NOT measure anything. Audio features (WPM, pauses, pitch, energy) are \
provided by the audio pipeline. You interpret what they MEAN in performance.

Output a JSON object matching this schema:
{
  "joke_id": "string",
  "evidence": {"transcript": "...", "start_ms": 0, "end_ms": 0, "audio_source": "..."},
  "semantics": {
    "setup": "what the comedian establishes",
    "expected": "what the audience expects to happen",
    "reveal": "what actually happens",
    "mechanisms": ["setup_punchline", "misdirection", ...],
    "character_reference": "which character trait is referenced",
    "requires_prior_context": true/false
  },
  "delivery": {
    "style": "dry|animated|deadpan|confessional|escalating",
    "pause_before_reveal_ms": 0,
    "emphasis": ["words that carry the joke"],
    "vocal_energy": "restrained|moderate|high|explosive"
  },
  "interpretation": {
    "punchline_understood": true/false,
    "possible_weakness": "why this might not land"
  }
}

Be precise. If the segment isn't a joke, say so in interpretation.possible_weakness."""


def observe_minute(
    audio_path: str | Path,
    transcript: str,
    character_context: str = "",
    measured_features: dict | None = None,
) -> dict:
    """Analyze one minute of comedy via Qwen3.8 Omni.

    Args:
        audio_path: path to audio file (for ASR + features, not sent to Qwen)
        transcript: ASR transcript (from cf_asr.py)
        character_context: who is speaking, their traits, callbacks
        measured_features: dict from audio pipeline (wpm, pauses, energy, etc.)

    Returns:
        dict matching comedy.observation.v1 schema
    """
    key = _get_key("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not found in .env or environment")

    # Build the user message with measured features merged in
    features = measured_features or {}
    user_msg = f"""Transcript:
{transcript}

Character context:
{character_context or "(none provided)"}

Measured audio features (from software pipeline, NOT your estimation):
{json.dumps(features, indent=2)}

Analyze the joke structure in this segment. Output JSON."""

    import urllib.request

    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/prx0r/characters",
            "X-Title": "Characters Comedy Observer",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())

    content = resp["choices"][0]["message"]["content"]
    obs = json.loads(content)

    # Merge measured features into delivery (don't let Qwen fabricate them)
    if "delivery" not in obs:
        obs["delivery"] = {}
    if "wpm" in features:
        obs["delivery"]["pace_wpm"] = features["wpm"]
    if "pause_before_punchline_ms" in features:
        obs["delivery"]["pause_before_reveal_ms"] = features["pause_before_punchline_ms"]

    obs.setdefault("schema", "comedy.observation.v1")
    return obs


def observe_from_audio(
    audio_path: str | Path,
    character_context: str = "",
) -> dict:
    """Full pipeline: ASR + audio features → Qwen observation.

    This is the P0 precomputed mode: analyze before playback.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    import cf_asr

    # Step 1: ASR
    asr = cf_asr.transcribe(audio_path)
    transcript = " ".join(w["text"] for w in asr["words"])

    # Step 2: Measured features from word timestamps
    words = asr["words"]
    if len(words) >= 2:
        total_dur = words[-1]["end"] - words[0]["start"]
        wpm = len(words) / max(total_dur / 60, 0.01)
        gaps = [words[i+1]["start"] - words[i]["end"] for i in range(len(words)-1)]
        pause_mean = sum(gaps) / max(len(gaps), 1)
        pause_max = max(gaps) if gaps else 0
    else:
        wpm = 0
        pause_mean = 0
        pause_max = 0

    measured = {
        "wpm": round(wpm, 1),
        "pause_mean_ms": round(pause_mean * 1000),
        "pause_max_ms": round(pause_max * 1000),
        "n_words": len(words),
        "duration_s": round(total_dur, 1) if len(words) >= 2 else 0,
    }

    # Step 3: Qwen observation
    return observe_minute(audio_path, transcript, character_context, measured)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Qwen comedy observer")
    p.add_argument("audio", help="Audio file path")
    p.add_argument("--context", default="", help="Character context")
    p.add_argument("--out", help="Output JSON path")
    args = p.parse_args()

    obs = observe_from_audio(args.audio, args.context)
    out = json.dumps(obs, indent=2)
    if args.out:
        Path(args.out).write_text(out)
        print(f"Saved to {args.out}")
    else:
        print(out)
