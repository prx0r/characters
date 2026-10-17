"""Standup Simulator: perform a set, get simulated laughter.

One script. Text in → audio with laughs out.

Usage:
  python3 standup_sim.py "your set text here"
  python3 standup_sim.py --file set.txt
  python3 standup_sim.py --live  # microphone mode
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from laugh_track_renderer import LaughTrackRenderer
from crowd_state import CrowdStateMachine

# ── Beat segmentation ──────────────────────────────────────

def segment_beats(text: str) -> list[dict]:
    """Split text into beats. Short sentences near question/exclamation = punchlines."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(s.strip()) > 3]
    beats = []
    for i, sent in enumerate(sentences):
        words = sent.split()
        n = len(words)

        # Punchline detection: short + has punctuation + follows longer sentence
        is_punchline = False
        if i > 0:
            prev_len = len(sentences[i-1].split())
            if n < 10 and prev_len > 8:
                is_punchline = True
        if n < 6 and ("!" in sent or "?" in sent):
            is_punchline = True
        if re.search(r"\b(not|no|never|don't|but actually|except)\b", sent, re.I) and n < 12:
            is_punchline = True

        beats.append({
            "index": i,
            "text": sent,
            "n_words": n,
            "is_punchline": is_punchline,
            "is_last": i == len(sentences) - 1,
        })
    return beats


# ── Laugh placement (theory, not ML) ───────────────────────

def place_laughs(beats: list[dict]) -> list[dict]:
    """Place laughs using comedy theory, not ML prediction.

    Rules (from dpv + Louis formula):
    - Punchline → laugh
    - Every 3rd beat → small chuckle
    - Closer → bigger laugh
    - Crowd state modulates intensity
    """
    crowd = CrowdStateMachine()
    laughs = []

    # Estimate timing: ~2.5 words/sec speech + 1.2s avg pause
    t = 0.5  # small opening pause

    for i, b in enumerate(beats):
        speech_dur = b["n_words"] / 2.5
        pause = 1.2  # average pause between beats

        # Longer pause before punchlines (dpv: 1.5s pre-punch)
        if b["is_punchline"]:
            pause = 2.0

        t += speech_dur

        # Predict laugh
        will_laugh = False
        laugh_type = "chuckle"
        intensity = 0.3

        if b["is_punchline"]:
            will_laugh = True
            laugh_type = "laugh"
            intensity = 0.5
        elif i % 3 == 2 and i > 0:
            will_laugh = True
            laugh_type = "chuckle"
            intensity = 0.25
        if b["is_last"]:
            will_laugh = True
            laugh_type = "big_laugh"
            intensity = 0.7

        if will_laugh:
            # Crowd state modulates intensity
            state = crowd.beat(laughed=True, intensity=intensity, laugh_type=laugh_type)
            intensity = min(1.0, intensity * (1 + state.heat * 0.3))
            laughs.append({
                "timestamp_s": round(t, 1),
                "laugh_type": laugh_type,
                "intensity": round(intensity, 2),
                "beat_index": i,
                "text": b["text"][:40],
            })
        else:
            crowd.beat(laughed=False)

        t += pause

    return laughs


# ── Audio generation ───────────────────────────────────────

def render_set(text: str, output_path: str = "standup_output.wav") -> dict:
    """Full pipeline: text → voice + laugh track → WAV."""
    from fish_tts import synthesize_fish

    print(f"Segmenting {len(text)} chars...")
    beats = segment_beats(text)
    print(f"  {len(beats)} beats, {sum(b['is_punchline'] for b in beats)} punchlines")

    print("Placing laughs...")
    laughs = place_laughs(beats)
    print(f"  {len(laughs)} laugh moments")

    # Render voice
    print("Rendering voice (Fish TTS, free)...")
    voice_segments = []
    for i, b in enumerate(beats):
        result = synthesize_fish(
            f"sim-{i:03d}",
            b["text"],
            modulator="neutral",
        )
        voice_segments.append(result["path"])
        print(f"  Beat {i}: {result['duration_ms']/1000:.1f}s {'[LAUGH]' if any(l['beat_index']==i for l in laughs) else ''}")

    # Concatenate voice segments with pauses
    print("Assembling audio...")
    import subprocess
    all_voice = []
    for i, (seg_path, b) in enumerate(zip(voice_segments, beats)):
        # Load segment
        r = subprocess.run(
            ["ffmpeg", "-i", seg_path, "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
            capture_output=True, timeout=30
        )
        audio = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        all_voice.append(audio)

        # Add pause after beat
        pause_dur = 2.0 if b["is_punchline"] else 1.2
        pause = np.zeros(int(pause_dur * 44100), dtype=np.float32)
        all_voice.append(pause)

    voice = np.concatenate(all_voice)

    # Mix laugh track
    print("Mixing laugh track...")
    renderer = LaughTrackRenderer()
    renderer.voice = voice

    for laugh in laughs:
        renderer.add_laugh(
            timestamp_s=laugh["timestamp_s"],
            laugh_type=laugh["laugh_type"],
            intensity=laugh["intensity"],
        )

    stats = renderer.render(output_path)

    return {
        "output": output_path,
        "duration_s": stats["duration_s"],
        "n_beats": len(beats),
        "n_punchlines": sum(b["is_punchline"] for b in beats),
        "n_laughs": stats["n_laughs"],
        "laugh_density": stats["laugh_density"],
        "laughs": laughs,
    }


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Standup Simulator")
    p.add_argument("text", nargs="?", help="Set text")
    p.add_argument("--file", help="Read set from file")
    p.add_argument("--out", default="standup_output.wav", help="Output WAV")
    args = p.parse_args()

    if args.file:
        text = Path(args.file).read_text()
    elif args.text:
        text = args.text
    else:
        # Demo set
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
            "I am impressed. "
            "She has no idea what she did. "
            "She just knows she won. "
            "And that is the purest form of victory."
        )

    print("=" * 50)
    print("STANDUP SIMULATOR")
    print("=" * 50)

    result = render_set(text, args.out)

    print(f"\n{'='*50}")
    print(f"RESULT")
    print(f"{'='*50}")
    print(f"Output:     {result['output']}")
    print(f"Duration:   {result['duration_s']:.1f}s")
    print(f"Beats:      {result['n_beats']} ({result['n_punchlines']} punchlines)")
    print(f"Laughs:     {result['n_laughs']}")
    print(f"Density:    {result['laugh_density']:.0%}")
    print(f"\nLaugh timeline:")
    for l in result["laughs"]:
        bar = "█" * int(l["intensity"] * 15)
        print(f"  {l['timestamp_s']:>6.1f}s {l['laugh_type']:12s} {bar:15s} | {l['text']}")
