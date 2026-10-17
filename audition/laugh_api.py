"""Laugh Engine API — standalone, works from any repo.

No path dependencies. Self-contained.

Usage:
  # From any Python project:
  import sys
  sys.path.insert(0, "/path/to/characters/audition")
  from laugh_api import LaughEngine

  engine = LaughEngine()
  events = engine.predict_from_file("comedy_set.wav")
  stats = engine.get_stats()

  # Or generate a laugh track for a transcript:
  track = engine.predict_from_text(["setup...", "punchline!"])
"""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import asdict

# Import the engine
try:
    from realtime_laughter import LaughterEngine, LaughEvent, SetStats
except ImportError:
    # Allow running as standalone module
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from realtime_laughter import LaughterEngine, LaughEvent, SetStats

import numpy as np


class LaughEngine:
    """Simple API for laugh prediction and rendering."""

    def __init__(self, model_path: str | None = None, threshold: float = 0.25):
        """Initialize. Auto-discovers models and clips."""
        # Find model
        if model_path is None:
            for alt in [
                Path(__file__).parent / "voicelab" / "prosody200_clean_model.pkl",
                Path(__file__).parent / "voicelab" / "unified_laugh_model.pkl",
            ]:
                if alt.exists():
                    model_path = str(alt)
                    break

        # Find clips
        clips_dir = None
        for alt in ["/home/box/comedy-ai/laugh-library", "laugh-library"]:
            if Path(alt).exists():
                clips_dir = alt
                break

        self.engine = LaughterEngine(
            model_path=model_path,
            laugh_clips_dir=clips_dir,
            laugh_threshold=threshold,
        )

    def predict_from_file(self, audio_path: str) -> list[dict]:
        """Predict laughs from audio file. Returns list of laugh events."""
        stats = self.engine.process_file(audio_path)
        return [asdict(e) for e in stats.laugh_events]

    def predict_from_text(self, sentences: list[str]) -> list[dict]:
        """Predict laughs from text sentences (no audio needed).

        Uses text features to estimate laugh probability per sentence.
        """
        import re
        import numpy as np

        events = []
        for i, text in enumerate(sentences):
            # Simple text features
            words = text.split()
            has_question = "?" in text
            has_exclamation = "!" in text
            has_negation = bool(re.search(r"\b(not|no|never|don't|won't)\b", text, re.I))
            has_taboo = bool(re.search(r"\b(fuck|shit|damn|hell|bitch)\b", text, re.I))
            is_short = len(words) < 8
            is_punchline = is_short and (has_exclamation or has_negation)

            # Score
            score = 0.2
            if is_punchline:
                score += 0.4
            if has_exclamation:
                score += 0.15
            if has_taboo:
                score += 0.15
            if has_question:
                score -= 0.05
            if len(words) > 20:
                score -= 0.05  # long setup
            if is_short and has_negation:
                score += 0.2  # classic joke structure

            score = max(0.0, min(1.0, score))

            if score > 0.3:
                events.append({
                    "sentence_index": i,
                    "text": text[:80],
                    "p_laugh": round(score, 3),
                    "laugh_type": "laugh" if score < 0.6 else "big_laugh",
                    "intensity": round(min(1.0, score * 1.2), 3),
                })

        return events

    def render_laugh(self, event: dict, output_path: str | None = None) -> bytes:
        """Render a laugh event to WAV audio bytes."""
        import struct

        laugh_event = LaughEvent(
            timestamp=event.get("timestamp", 0),
            p_laugh=event.get("p_laugh", 0.5),
            intensity=event.get("intensity", 0.5),
            laugh_type=event.get("laugh_type", "laugh"),
            mechanism=event.get("mechanism", "unknown"),
            duration_ms=event.get("duration_ms", 1000),
        )

        audio = self.engine.renderer.render(laugh_event)

        # Convert to WAV
        pcm = (audio * 32767).astype(np.int16).tobytes()
        wav = b"RIFF"
        wav += struct.pack("<I", 36 + len(pcm))
        wav += b"WAVEfmt "
        wav += struct.pack("<IHHIIHH", 16, 1, 1, 44100, 44100 * 2, 2, 16)
        wav += b"data"
        wav += struct.pack("<I", len(pcm))
        wav += pcm

        if output_path:
            Path(output_path).write_bytes(wav)

        return wav

    def get_stats(self) -> dict:
        """Get stats from last prediction."""
        stats = self.engine.get_stats()
        return asdict(stats)

    def get_timeline(self) -> list[dict]:
        """Get prediction timeline."""
        stats = self.engine.get_stats()
        return stats.timeline


# Convenience function
def quick_laugh(audio_path: str, threshold: float = 0.25) -> list[dict]:
    """One-liner: predict laughs from audio file."""
    engine = LaughEngine(threshold=threshold)
    return engine.predict_from_file(audio_path)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Laugh Engine API")
    p.add_argument("input", help="Audio file or text file")
    p.add_argument("--text", action="store_true", help="Treat input as text file")
    p.add_argument("--threshold", type=float, default=0.25)
    p.add_argument("--render", help="Render laughs to this output WAV")
    args = p.parse_args()

    engine = LaughEngine(threshold=args.threshold)

    if args.text:
        sentences = Path(args.input).read_text().strip().split("\n")
        events = engine.predict_from_text(sentences)
    else:
        events = engine.predict_from_file(args.input)

    print(json.dumps(events, indent=2))

    if args.render and events:
        engine.render_laugh(events[0], args.render)
        print(f"\nRendered to {args.render}")
