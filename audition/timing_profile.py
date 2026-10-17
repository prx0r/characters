"""Comedian Timing Profile: text rhythm → delivery → laugh placement.

Based on:
- Louis formula: 1.67s pauses, 3.94 syll/s, 19.6dB dynamics
- dpv findings: pause ladder 0.6/1.5/1.0, coupling ratio 1.41
- KT timing profiles: per-comedian fingerprints
- Rhythm findings (characters2): sentence structure = delivery proxy

The insight: text rhythm IS delivery timing. "A bit that can't breathe
on the page can't breathe on stage." We can predict delivery from text
structure alone, then audio features increase confidence.

Usage:
  from timing_profile import ComedianProfile, extract_rhythm, match_profile
  profile = extract_rhythm(text)  # what rhythm is this text?
  comedian = match_profile(profile)  # who does it sound like?
  delivery = profile_to_delivery(profile)  # what timing to use?
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np


# ── Comedian timing fingerprints (measured) ────────────────

COMEDIAN_PROFILES = {
    "louis": {
        "wpm": 163, "syll_per_sec": 3.94,
        "pause_mean": 1.67, "pause_variance": 1.13,
        "dynamics_db": 19.6, "pitch_std_st": 6.83,
        "centroid_hz": 1535,
        "pause_ladder": {"setup": 0.7, "pre_punch": 1.7, "tag": 1.0},
        "emotion_cues": ["[calm]", "[sarcastic]", "[indifferent]"],
        "text_rhythm": {"mean_sent_len": 12.5, "sent_len_std": 6.2, "fragment_ratio": 0.15},
    },
    "kam": {
        "wpm": 210, "syll_per_sec": 4.5,
        "pause_mean": 0.8, "pause_variance": 0.9,
        "dynamics_db": 28, "pitch_std_st": 5.5,
        "centroid_hz": 2200,
        "pause_ladder": {"setup": 0.4, "pre_punch": 1.2, "tag": 0.8},
        "emotion_cues": ["[energetic]", "[confident]", "[playful]"],
        "text_rhythm": {"mean_sent_len": 8.5, "sent_len_std": 4.0, "fragment_ratio": 0.25},
    },
    "chris_rock": {
        "wpm": 220, "syll_per_sec": 4.8,
        "pause_mean": 0.6, "pause_variance": 0.8,
        "dynamics_db": 35, "pitch_std_st": 7.2,
        "centroid_hz": 2500,
        "pause_ladder": {"setup": 0.3, "pre_punch": 1.0, "tag": 0.6},
        "emotion_cues": ["[energetic]", "[intense]", "[rhythmic]"],
        "text_rhythm": {"mean_sent_len": 7.5, "sent_len_std": 5.5, "fragment_ratio": 0.30},
        "notes": "Rhythmic. Short punchy sentences with escalation.",
    },
    "default": {
        "wpm": 180, "syll_per_sec": 4.2,
        "pause_mean": 1.0, "pause_variance": 1.0,
        "dynamics_db": 25, "pitch_std_st": 5.0,
        "centroid_hz": 2000,
        "pause_ladder": {"setup": 0.5, "pre_punch": 1.3, "tag": 0.9},
        "emotion_cues": ["[neutral]", "[amused]", "[confident]"],
        "text_rhythm": {"mean_sent_len": 10.0, "sent_len_std": 5.0, "fragment_ratio": 0.20},
    },
}


# ── Text rhythm extraction ─────────────────────────────────

@dataclass
class TextRhythm:
    """Rhythm features from text structure."""
    mean_sent_len: float
    sent_len_std: float
    fragment_ratio: float  # sentences < 6 words
    staccato_run: int  # consecutive short sentences
    long_sentence_ratio: float  # sentences >= 15 words
    n_sentences: int
    has_punchline_pattern: bool  # long setup → short punch


def extract_rhythm(text: str) -> TextRhythm:
    """Extract rhythm features from text.

    From characters2 RHYTHM-FINDINGS.md:
    - Humans: mean 11.75 words/sent, sd=5.8, fragment_ratio=0.20
    - AI: mean 5.4 words/sent, sd=3.0, fragment_ratio=0.62
    """
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(s.strip()) > 3]
    if not sentences:
        return TextRhythm(10, 5, 0.2, 0, 0.33, 0, False)

    lens = [len(s.split()) for s in sentences]
    mean_len = np.mean(lens)
    std_len = np.std(lens)
    fragment_ratio = sum(1 for l in lens if l < 6) / len(lens)
    long_ratio = sum(1 for l in lens if l >= 15) / len(lens)

    # Staccato run: consecutive sentences <= 8 words
    staccato_run = 0
    max_staccato = 0
    for l in lens:
        if l <= 8:
            staccato_run += 1
            max_staccato = max(max_staccato, staccato_run)
        else:
            staccato_run = 0

    # Punchline pattern: long sentence followed by short
    has_punchline = False
    for i in range(1, len(lens)):
        if lens[i-1] > 10 and lens[i] < 8:
            has_punchline = True
            break

    return TextRhythm(
        mean_sent_len=round(float(mean_len), 1),
        sent_len_std=round(float(std_len), 1),
        fragment_ratio=round(float(fragment_ratio), 3),
        staccato_run=max_staccato,
        long_sentence_ratio=round(float(long_ratio), 3),
        n_sentences=len(sentences),
        has_punchline_pattern=has_punchline,
    )


# ── Profile matching ───────────────────────────────────────

def match_profile(rhythm: TextRhythm) -> tuple[str, float]:
    """Match text rhythm to closest comedian profile.

    Returns (comedian_name, similarity_score).
    """
    best_match = "default"
    best_score = float("inf")

    for name, profile in COMEDIAN_PROFILES.items():
        if name == "default":
            continue

        target = profile["text_rhythm"]
        # Euclidean distance on rhythm features
        dist = np.sqrt(
            (rhythm.mean_sent_len - target["mean_sent_len"]) ** 2 +
            (rhythm.sent_len_std - target["sent_len_std"]) ** 2 +
            (rhythm.fragment_ratio - target["fragment_ratio"]) ** 2 * 10
        )

        if dist < best_score:
            best_score = dist
            best_match = name

    # Convert distance to similarity (0-1)
    similarity = max(0.0, 1.0 - best_score / 20.0)
    return best_match, round(similarity, 3)


# ── Rhythm → delivery mapping ──────────────────────────────

def rhythm_to_delivery(rhythm: TextRhythm, comedian: str = "default") -> dict:
    """Map text rhythm to delivery parameters.

    "A bit that can't breathe on the page can't breathe on stage."
    Staccato text → fast delivery. Long sentences → room for pauses.
    """
    profile = COMEDIAN_PROFILES.get(comedian, COMEDIAN_PROFILES["default"])
    ladder = profile["pause_ladder"]

    # Adjust based on rhythm
    if rhythm.mean_sent_len < 7:
        # Staccato: faster delivery, shorter pauses
        speed = 1.1
        pause_scale = 0.7
    elif rhythm.mean_sent_len > 14:
        # Long sentences: slower, more room for pauses
        speed = 0.85
        pause_scale = 1.3
    else:
        speed = 1.0
        pause_scale = 1.0

    # Fragment ratio affects pause placement
    if rhythm.fragment_ratio > 0.4:
        # Many fragments: quick-fire delivery
        pause_scale *= 0.8
    elif rhythm.fragment_ratio < 0.1:
        # Few fragments: measured delivery
        pause_scale *= 1.2

    return {
        "comedian": comedian,
        "speed": round(speed, 2),
        "pause_setup": round(ladder["setup"] * pause_scale, 2),
        "pause_pre_punch": round(ladder["pre_punch"] * pause_scale, 2),
        "pause_tag": round(ladder["tag"] * pause_scale, 2),
        "wpm": round(profile["wpm"] * speed),
        "emotion_cues": profile["emotion_cues"],
        "dynamics_db": profile["dynamics_db"],
        "notes": profile.get("notes", ""),
    }


# ── Laugh placement from rhythm ────────────────────────────

def rhythm_based_laughs(text: str, rhythm: TextRhythm, delivery: dict) -> list[dict]:
    """Place laughs based on text rhythm + delivery timing.

    Rules:
    - Punchline pattern (long→short) gets a laugh
    - Staccato bursts get chuckles
    - Closer gets bigger laugh
    - Delivery timing determines WHEN (not just IF)
    """
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(s.strip()) > 3]

    laughs = []
    t = 0.5  # opening pause

    for i, sent in enumerate(sentences):
        words = sent.split()
        n = len(words)

        # Speech duration from delivery speed
        speech_dur = n / (delivery["wpm"] / 60.0)

        # Pause before this beat
        if i == 0:
            pause = 0.2
        elif i == len(sentences) - 1:
            pause = delivery["pause_pre_punch"] * 1.2
        else:
            # Check if this is a punchline (previous long, this short)
            if i > 0 and len(sentences[i-1].split()) > 10 and n < 8:
                pause = delivery["pause_pre_punch"]
            else:
                pause = delivery["pause_setup"]

        t += pause + speech_dur

        # Laugh decision
        will_laugh = False
        laugh_type = "chuckle"
        intensity = 0.3

        # Punchline pattern
        if i > 0 and len(sentences[i-1].split()) > 10 and n < 8:
            will_laugh = True
            laugh_type = "laugh"
            intensity = 0.5

        # Staccato burst
        if rhythm.staccato_run >= 3 and i >= 2:
            will_laugh = True
            laugh_type = "chuckle"
            intensity = 0.25

        # Closer
        if i == len(sentences) - 1:
            will_laugh = True
            laugh_type = "big_laugh"
            intensity = 0.7

        if will_laugh:
            laughs.append({
                "timestamp_s": round(t, 1),
                "laugh_type": laugh_type,
                "intensity": intensity,
                "sentence_index": i,
                "text": sent[:40],
            })

    return laughs


if __name__ == "__main__":
    # Demo: analyze rhythm and match comedian
    text = (
        "You know what I love about Monopoly? "
        "The little houses. They are so tiny. "
        "Like, why are they so small? "
        "You are supposed to be building an empire, "
        "and they give you these little green houses "
        "that look like they belong in a dollhouse. "
        "I played Monopoly with my kids the other day. "
        "My daughter, she is nine, she beat me. "
        "And I am not even mad. "
        "I am impressed."
    )

    rhythm = extract_rhythm(text)
    comedian, similarity = match_profile(rhythm)
    delivery = rhythm_to_delivery(rhythm, comedian)
    laughs = rhythm_based_laughs(text, rhythm, delivery)

    print("Text Rhythm Analysis")
    print("=" * 60)
    print(f"Mean sentence length: {rhythm.mean_sent_len} words")
    print(f"Sentence length std:  {rhythm.sent_len_std}")
    print(f"Fragment ratio:       {rhythm.fragment_ratio:.1%}")
    print(f"Staccato run:         {rhythm.staccato_run}")
    print(f"Long sentence ratio:  {rhythm.long_sentence_ratio:.1%}")
    print(f"Punchline pattern:    {rhythm.has_punchline_pattern}")

    print(f"\nMatched comedian:     {comedian} (similarity {similarity:.1%})")

    print(f"\nDelivery parameters:")
    print(f"  Speed:              {delivery['speed']}x")
    print(f"  WPM:                {delivery['wpm']}")
    print(f"  Pause setup:        {delivery['pause_setup']}s")
    print(f"  Pause pre-punch:    {delivery['pause_pre_punch']}s")
    print(f"  Emotion cues:       {delivery['emotion_cues']}")

    print(f"\nLaugh placement ({len(laughs)} moments):")
    for l in laughs:
        bar = "█" * int(l["intensity"] * 15)
        print(f"  {l['timestamp_s']:>6.1f}s {l['laugh_type']:12s} {bar:15s} | {l['text']}")
