"""Delivery Engine: set text → directed Fish TTS audio with timings.

Takes a comedian's minute and renders it using:
  1. Character profile (voice_engine.json) — who they are, how they deliver
  2. Comedy theory (pause ladder, coupling, mechanisms) — when to pause
  3. Laugh prediction — where laughs are expected
  4. Fish TTS s2.1-pro-free — the actual audio generation

Pipeline:
  text → beat segmentation → mechanism tagging → timing assignment →
  direction string generation → Fish TTS render → audio assembly →
  timeline + stats output

Usage:
  from delivery_engine import DeliveryEngine
  engine = DeliveryEngine(comedian="louis")
  result = engine.render_minute(text)
  result.audio_path  # the rendered WAV
  result.timeline    # per-beat timings + directions
  result.stats       # what worked, what didn't
"""
from __future__ import annotations
import json, re, time, subprocess, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
AUDIO_DIR = HERE / "audio"
AUDIO_DIR.mkdir(exist_ok=True)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Beat:
    """One beat of the set."""
    index: int
    text: str
    beat_type: str  # opener, setup, punchline, tag, closer
    mechanism: str
    # Timing (seconds)
    pause_before: float
    target_wps: float
    target_duration: float
    # Direction
    emotion_cue: str
    tone_marker: str
    speed: float
    temperature: float
    # Laugh prediction
    p_laugh: float
    laugh_type: str


@dataclass
class RenderResult:
    """Full render output."""
    audio_path: str
    duration_ms: int
    beats: list
    timeline: list
    stats: dict
    provenance: str


# ============================================================
# CHARACTER PROFILES
# ============================================================

# Fallback profiles (used when voice_engine.json doesn't have the performer)
PROFILES = {
    "louis": {
        "wpm": 163, "pause_ladder": [0.6, 1.5, 1.0], "pause_jitter": 0.25,
        "coupling_ratio": 1.41, "temperature": 0.55, "speed_scale": 0.85,
        "emotion_cues": ["[calm]", "[sarcastic]", "[indifferent]"],
        "dynamics_db": 19.6, "pitch_std_st": 6.83,
        "techniques": {"literalize": 0.24, "escalation": 0.19, "self_deprecation": 0.16},
    },
    "kam": {
        "wpm": 210, "pause_ladder": [0.4, 1.2, 0.8], "pause_jitter": 0.30,
        "coupling_ratio": 1.35, "temperature": 0.70, "speed_scale": 1.0,
        "emotion_cues": ["[energetic]", "[confident]", "[playful]"],
        "dynamics_db": 28.0, "pitch_std_st": 5.5,
        "techniques": {"self_deprecation": 0.30, "escalation": 0.25, "audience_address": 0.20},
    },
    "default": {
        "wpm": 180, "pause_ladder": [0.5, 1.3, 0.9], "pause_jitter": 0.25,
        "coupling_ratio": 1.35, "temperature": 0.60, "speed_scale": 1.0,
        "emotion_cues": ["[neutral]", "[amused]", "[confident]"],
        "dynamics_db": 25.0, "pitch_std_st": 5.0,
        "techniques": {"setup_punchline": 0.40, "self_deprecation": 0.20, "escalation": 0.15},
    },
}


def load_profile(comedian: str) -> dict:
    """Load character profile from voice_engine.json or fallback."""
    ve_path = LAB / "voice_engine.json"
    if ve_path.exists():
        engine = json.loads(ve_path.read_text())
        perf = engine.get("performers", {}).get(comedian)
        if perf and "delivery_state" in perf:
            state = perf["delivery_state"]
            # Merge with fallback for missing fields
            base = PROFILES.get(comedian, PROFILES["default"]).copy()
            for k, v in state.items():
                if k in ("wpm_target",):
                    base["wpm"] = v
                elif k == "speed_scale":
                    base["speed_scale"] = v
                elif k == "temperature":
                    base["temperature"] = v
                elif k == "pause_ladder" and isinstance(v, dict):
                    base["pause_ladder"] = [v.get("setup", 0.5), v.get("pre_punch", 1.3), v.get("tag", 0.9)]
                elif k == "emotion_cues":
                    base["emotion_cues"] = v
            return base
    return PROFILES.get(comedian, PROFILES["default"])


# ============================================================
# BEAT SEGMENTATION + MECHANISM TAGGING
# ============================================================

def segment_beats(text: str) -> list[dict]:
    """Segment text into beats (sentences with type detection)."""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]

    beats = []
    for i, sent in enumerate(sentences):
        words = sent.split()
        n_words = len(words)

        # Classify beat type
        if i == 0:
            beat_type = "opener"
        elif i == len(sentences) - 1:
            beat_type = "closer"
        elif n_words < 8 and ("!" in sent or "?" in sent or "not" in sent.lower() or "don't" in sent.lower()):
            beat_type = "punchline"
        elif n_words < 6:
            beat_type = "tag"
        else:
            beat_type = "setup"

        # Tag mechanism
        mechanism = tag_mechanism(sent, beat_type, sentences[:i])

        beats.append({
            "index": i,
            "text": sent,
            "beat_type": beat_type,
            "mechanism": mechanism,
            "n_words": n_words,
        })

    return beats


def tag_mechanism(text: str, beat_type: str, prior_beats: list[str]) -> str:
    """Tag the comedic mechanism of a beat."""
    t = text.lower()

    # Callback: references something from earlier
    prior_words = set()
    for pb in prior_beats:
        prior_words.update(w.lower() for w in pb.split() if len(w) > 3)
    current_words = set(w.lower() for w in t.split() if len(w) > 3)
    if prior_words and len(prior_words & current_words) >= 2:
        return "callback"

    # Self-deprecation
    if re.search(r"\b(i'm|i am|my|me|myself)\b.*\b(stupid|dumb|ugly|fat|broke|failed|loser|idiot)\b", t):
        return "self_deprecation"

    # Escalation markers
    if re.search(r"\b(and then|and then|even worse|but wait|the best part)\b", t):
        return "escalation"

    # Misdirection / setup-punchline
    if beat_type == "punchline":
        if re.search(r"\b(not|no|never|don't|won't|can't|but actually)\b", t):
            return "misdirection"
        return "setup_punchline"

    # Deadpan (short, flat statements)
    if beat_type == "tag" and len(text.split()) < 5:
        return "deadpan"

    # Status reversal
    if re.search(r"\b(but|except|however|although|yet)\b", t):
        return "status_reversal"

    return "setup_punchline"


# ============================================================
# TIMING ASSIGNMENT
# ============================================================

def assign_timings(beats: list[dict], profile: dict) -> list[dict]:
    """Assign pause durations and speeds based on theory + profile."""
    ladder = profile.get("pause_ladder", [0.5, 1.3, 0.9])
    jitter = profile.get("pause_jitter", 0.25)
    coupling = profile.get("coupling_ratio", 1.35)
    base_wps = profile.get("wpm", 180) / 60.0  # words per second

    import random
    random.seed(42)  # reproducible

    for b in beats:
        bt = b["beat_type"]

        # Pause before this beat (dpv ladder)
        if bt == "opener":
            pause = 0.2
        elif bt == "punchline":
            # dpv coupling: extend pause before surprise
            pause = ladder[1] * coupling * (1 + random.uniform(-jitter, jitter))
        elif bt == "tag":
            pause = ladder[2] * (1 + random.uniform(-jitter, jitter))
        elif bt == "closer":
            pause = ladder[0] * 1.5
        else:  # setup
            pause = ladder[0] * (1 + random.uniform(-jitter, jitter))

        # Speed: slower for setup, normal for punchline
        if bt == "setup":
            speed = 0.9
        elif bt == "punchline":
            speed = 1.0
        elif bt == "tag":
            speed = 1.05
        else:
            speed = 1.0

        # Target duration based on wps
        target_wps = base_wps * speed
        target_duration = b["n_words"] / max(target_wps, 0.1)

        b.update({
            "pause_before": round(pause, 2),
            "target_wps": round(target_wps, 2),
            "target_duration": round(target_duration, 2),
        })

    return beats


# ============================================================
# LAUGH PREDICTION
# ============================================================

def predict_laughs(beats: list[dict], profile: dict) -> list[dict]:
    """Predict laugh probability per beat based on mechanism + position."""
    techniques = profile.get("techniques", {})
    n = len(beats)

    for i, b in enumerate(beats):
        mech = b["mechanism"]
        bt = b["beat_type"]

        # Base probability by mechanism
        mech_prob = {
            "status_reversal": 0.65, "misdirection": 0.62,
            "setup_punchline": 0.55, "escalation": 0.58,
            "callback": 0.60, "self_deprecation": 0.50,
            "deadpan": 0.45, "displacement": 0.40,
        }
        p = mech_prob.get(mech, 0.50)

        # Beat type modifier
        if bt == "punchline":
            p += 0.15
        elif bt == "tag":
            p += 0.05
        elif bt == "opener":
            p -= 0.10  # cold crowd
        elif bt == "closer":
            p += 0.10  # warm crowd

        # Position modifier (crowd warms up)
        pos = i / max(n, 1)
        p += pos * 0.15

        # Technique familiarity
        if mech in techniques:
            p += techniques[mech] * 0.1

        p = max(0.0, min(1.0, p))

        # Laugh type by probability
        if p < 0.35:
            ltype = "chuckle"
        elif p < 0.55:
            ltype = "laugh"
        elif p < 0.75:
            ltype = "big_laugh"
        else:
            ltype = "roar"

        b.update({"p_laugh": round(p, 3), "laugh_type": ltype})

    return beats


# ============================================================
# DIRECTION STRING GENERATION
# ============================================================

# Emotion → Fish cue mapping
EMOTION_CUES = {
    "setup_punchline": ("[neutral]", 0.60),
    "misdirection": ("[sarcastic]", 0.55),
    "escalation": ("[excited]", 0.70),
    "callback": ("[amused]", 0.60),
    "self_deprecation": ("[confessional]", 0.50),
    "deadpan": ("", 0.45),
    "status_reversal": ("[indignant]", 0.65),
    "displacement": ("[calm]", 0.55),
}

# Speed → Fish speed (clean zone 0.92-1.08)
def speed_to_fish(base_speed: float, beat_speed: float) -> float:
    """Combine profile speed with beat speed, clamp to clean zone."""
    s = base_speed * beat_speed
    return max(0.92, min(1.08, s))


def generate_direction(beat: dict, profile: dict) -> dict:
    """Generate Fish TTS direction for a beat."""
    mech = beat["mechanism"]
    bt = beat["beat_type"]

    # Emotion cue
    cue, temp = EMOTION_CUES.get(mech, ("[neutral]", 0.60))

    # Override for beat type
    if bt == "opener":
        cue = "[confident]"
    elif bt == "closer":
        cue = "[warm]"

    # Tone marker (never outside clean zone)
    speed = speed_to_fish(profile.get("speed_scale", 1.0), beat.get("speed", 1.0))

    # Build direction string
    parts = []
    if cue:
        parts.append(cue)
    parts.append(beat["text"])
    direction = " ".join(parts)

    return {
        "direction": direction,
        "emotion_cue": cue,
        "temperature": temp,
        "speed": speed,
    }


# ============================================================
# FISH TTS RENDERING
# ============================================================

def render_beat(beat: dict, profile: dict, clone_id: str | None = None) -> dict:
    """Render one beat with Fish TTS."""
    import sys
    sys.path.insert(0, str(HERE))
    from fish_tts import synthesize_fish

    direction = beat.get("_direction", {})
    text = beat["text"]
    cue = direction.get("emotion_cue", "")
    speed = direction.get("speed", 1.0)
    temp = direction.get("temperature", 0.60)

    # Build directed text
    directed = f"{cue} {text}".strip() if cue else text

    # Render
    audition_id = f"delivery-{hashlib.md5(text.encode()).hexdigest()[:8]}"

    result = synthesize_fish(
        audition_id,
        text,
        modulator="neutral" if not cue else cue.strip("[]"),
        prosody={"speed": speed, "temperature": temp},
        voice=clone_id,
    )

    return {
        "path": result["path"],
        "duration_ms": result["duration_ms"],
        "model": result["model"],
    }


def render_minute(
    text: str,
    comedian: str = "default",
    clone_id: str | None = None,
    output_name: str | None = None,
) -> RenderResult:
    """Full pipeline: text → directed audio with timings.

    Args:
        text: the comedian's minute
        comedian: profile name (louis, kam, default, etc.)
        clone_id: Fish voice clone ID (None = default voice)
        output_name: output file name (auto-generated if None)

    Returns:
        RenderResult with audio path, timeline, and stats
    """
    t0 = time.time()

    # 1. Load profile
    profile = load_profile(comedian)

    # 2. Segment into beats
    beats = segment_beats(text)

    # 3. Assign timings (theory-driven)
    beats = assign_timings(beats, profile)

    # 4. Predict laughs
    beats = predict_laughs(beats, profile)

    # 5. Generate directions
    for b in beats:
        b["_direction"] = generate_direction(b, profile)

    # 6. Render each beat
    rendered = []
    for b in beats:
        try:
            r = render_beat(b, profile, clone_id)
            b["_rendered"] = r
            rendered.append(r)
        except Exception as e:
            print(f"  Beat {b['index']} render failed: {e}")
            b["_rendered"] = None

    # 7. Assemble audio
    if output_name is None:
        output_name = f"delivery-{comedian}-{int(time.time())}"

    audio_path = AUDIO_DIR / f"{output_name}.wav"
    assembled = assemble_audio(beats, audio_path)

    # 8. Build timeline
    timeline = build_timeline(beats)

    # 9. Stats
    stats = compute_stats(beats, profile, comedian)

    return RenderResult(
        audio_path=str(audio_path),
        duration_ms=assembled.get("duration_ms", 0),
        beats=[{k: v for k, v in b.items() if not k.startswith("_")} for b in beats],
        timeline=timeline,
        stats=stats,
        provenance=f"fish-tts:s2.1-pro-free+delivery-engine+{comedian}",
    )


def assemble_audio(beats: list[dict], output_path: Path) -> dict:
    """Assemble rendered beats into one audio file with pauses."""
    import numpy as np

    rendered_beats = [b for b in beats if b.get("_rendered")]
    if not rendered_beats:
        return {"duration_ms": 0}

    # Decode each beat
    segments = []
    for b in rendered_beats:
        path = b["_rendered"]["path"]
        # Decode to numpy
        result = subprocess.run(
            ["ffmpeg", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
            capture_output=True, timeout=30
        )
        audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        segments.append(audio)

        # Add pause after beat
        pause_s = b.get("pause_before", 0.5)
        pause = np.zeros(int(pause_s * 44100), dtype=np.float32)
        segments.append(pause)

    # Concatenate
    full_audio = np.concatenate(segments) if segments else np.array([], dtype=np.float32)

    # Normalize
    peak = np.max(np.abs(full_audio))
    if peak > 0:
        full_audio = full_audio / peak * 0.85

    # Write WAV
    import struct
    pcm = (full_audio * 32767).astype(np.int16).tobytes()
    with open(output_path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + len(pcm)))
        f.write(b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, 44100, 44100 * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", len(pcm)))
        f.write(pcm)

    return {"duration_ms": int(len(full_audio) / 44100 * 1000)}


def build_timeline(beats: list[dict]) -> list[dict]:
    """Build a timeline of beats with timings and predictions."""
    timeline = []
    t = 0.0
    for b in beats:
        pause = b.get("pause_before", 0.5)
        dur = b.get("target_duration", 2.0)
        t += pause

        timeline.append({
            "time_s": round(t, 2),
            "beat_index": b["index"],
            "beat_type": b["beat_type"],
            "mechanism": b["mechanism"],
            "p_laugh": b.get("p_laugh", 0),
            "laugh_type": b.get("laugh_type", ""),
            "pause_before": pause,
            "target_duration": dur,
            "text_preview": b["text"][:60],
        })

        t += dur

    return timeline


def compute_stats(beats: list[dict], profile: dict, comedian: str = "default") -> dict:
    """Compute delivery stats."""
    n = len(beats)
    laugh_beats = [b for b in beats if b.get("p_laugh", 0) > 0.65]  # higher threshold
    total_pause = sum(b.get("pause_before", 0) for b in beats)
    total_duration = sum(b.get("target_duration", 0) for b in beats)
    avg_wps = sum(b.get("target_wps", 0) for b in beats) / max(n, 1)

    # Mechanism breakdown
    mechanisms = {}
    for b in beats:
        m = b["mechanism"]
        mechanisms[m] = mechanisms.get(m, 0) + 1

    # Beat type breakdown
    types = {}
    for b in beats:
        t = b["beat_type"]
        types[t] = types.get(t, 0) + 1

    return {
        "n_beats": n,
        "predicted_laughs": len(laugh_beats),
        "laugh_rate": round(len(laugh_beats) / max(n, 1), 3),
        "total_pause_s": round(total_pause, 1),
        "total_speech_s": round(total_duration, 1),
        "avg_wps": round(avg_wps, 1),
        "target_wpm": profile.get("wpm", 180),
        "mechanisms": mechanisms,
        "beat_types": types,
        "profile": comedian,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Delivery Engine")
    p.add_argument("text_file", help="Text file with the comedian's minute")
    p.add_argument("--comedian", default="default", help="Comedian profile")
    p.add_argument("--clone", help="Fish voice clone ID")
    p.add_argument("--out", help="Output name")
    p.add_argument("--dry-run", action="store_true", help="Show plan without rendering")
    args = p.parse_args()

    text = Path(args.text_file).read_text()

    if args.dry_run:
        profile = load_profile(args.comedian)
        beats = segment_beats(text)
        beats = assign_timings(beats, profile)
        beats = predict_laughs(beats, profile)
        for b in beats:
            b["_direction"] = generate_direction(b, profile)

        print(f"Profile: {args.comedian}")
        print(f"WPM target: {profile['wpm']}")
        print(f"Pause ladder: {profile['pause_ladder']}")
        print(f"\nBeats ({len(beats)}):")
        for b in beats:
            d = b["_direction"]
            print(f"  [{b['beat_type']:10s}] {b['mechanism']:20s} p={b['p_laugh']:.2f} "
                  f"pause={b['pause_before']:.2f}s speed={d['speed']:.2f} "
                  f"cue={d['emotion_cue']:15s} | {b['text'][:40]}...")
    else:
        result = render_minute(text, args.comedian, args.clone, args.out)
        print(f"\nRendered: {result.audio_path}")
        print(f"Duration: {result.duration_ms/1000:.1f}s")
        print(f"Beats: {result.stats['n_beats']}")
        print(f"Predicted laughs: {result.stats['predicted_laughs']}")
        print(f"Laughter rate: {result.stats['laugh_rate']:.1%}")
        print(f"\nTimeline:")
        for t in result.timeline:
            bar = "█" * int(t["p_laugh"] * 10)
            print(f"  {t['time_s']:>6.1f}s [{t['beat_type']:10s}] {t['p_laugh']:.2f} {bar} | {t['text_preview'][:30]}")
