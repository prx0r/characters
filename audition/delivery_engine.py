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
import json, os, re, time, subprocess, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

HERE = Path(__file__).parent
LAB = HERE / "voicelab"
STYLES = LAB / "styles"
FREAKS = HERE.parent / "freaks"
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


def load_style_profile(character_slug: str) -> dict | None:
    """freaks/<slug>/character.json delivery.style → engine profile (SPEC-FREAK-SDK)."""
    cpath = FREAKS / character_slug / "character.json"
    if not cpath.exists():
        return None
    char = json.loads(cpath.read_text())
    delivery = char.get("delivery") or {}
    style_key = delivery.get("style")
    if not style_key:
        return None
    spath = STYLES / f"{style_key}.json"
    if not spath.exists():
        return None
    style = json.loads(spath.read_text())
    recipe = style.get("engine_recipe", {})
    overrides = delivery.get("overrides") or {}
    ladder = list(recipe.get("pause_ladder", [0.5, 1.3, 0.9]))
    hold_ms = overrides.get("punchline_hold_ms")
    if hold_ms:
        ladder[1] = max(ladder[1], hold_ms / 1000.0)
    # resolution window: harvested laugh latency or ladder[2]; override floor
    post = recipe.get("post_punch_s") or ladder[2]
    post_ms = overrides.get("post_punch_ms")
    if post_ms:
        post = max(post, post_ms / 1000.0)
    return {
        "wpm": recipe.get("wpm", 180),
        "pause_ladder": ladder,
        "pause_jitter": recipe.get("pause_jitter", 0.25),
        "coupling_ratio": recipe.get("coupling_ratio", 1.35),
        "post_punch_s": round(post, 2),
        "punch_hold_floor_s": (hold_ms / 1000.0) if hold_ms else 0.6,
        "temperature": overrides.get("temperature", recipe.get("temperature", 0.6)),
        "speed_scale": recipe.get("speed_scale", 1.0),
        "emotion_cues": recipe.get("emotion_cues", ["[neutral]"]),
        "emotion_forbidden": recipe.get("emotion_forbidden", []),
        "dynamics_db": recipe.get("dynamics_db"),
        "pitch_std_st": recipe.get("pitch_std_st"),
        "volume_db": recipe.get("volume_db", 0.0),
        "techniques": style.get("technique_mix", {}),
        "style_slug": style_key,
        "source": f"voicelab/styles/{style_key}.json",
        "voice_fish_id": (char.get("voice") or {}).get("fish", {}).get("reference_id"),
    }


def load_profile(comedian: str) -> dict:
    """Character slug (delivery.style) → voice_engine.json → fallback."""
    styled = load_style_profile(comedian)
    if styled:
        return styled
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

# beat type -> speed factor (Norrick contrast: punch snaps faster than setup;
# escalation/list mechanisms run hot into the verdict, then stop dead)
BEAT_SPEED = {"opener": 1.0, "setup": 1.0, "punchline": 1.08, "tag": 1.05,
              "closer": 0.95}
MECH_SPEED = {"escalation": 1.15, "callback": 1.05}


def assign_timings(beats: list[dict], profile: dict) -> list[dict]:
    """Assign pause durations and speeds based on theory + profile.

    Attardo ch10 (theory/attardo-timing-map.md):
      T1 pre-punch hold: ladder[1] x coupling, 0.6s floor
      T2 resolution window: pause_after on punch/closer (post_punch_s)
      T3 Norrick contrast: BEAT_SPEED x MECH_SPEED factors (outside the
        0.92-1.08 clean zone fish_tts decomposes via tempo_via_prompt)
    """
    ladder = profile.get("pause_ladder", [0.5, 1.3, 0.9])
    jitter = profile.get("pause_jitter", 0.25)
    coupling = profile.get("coupling_ratio", 1.35)
    base_wps = profile.get("wpm", 180) / 60.0  # words per second
    post_punch = profile.get("post_punch_s") or ladder[2]
    hold_floor = profile.get("punch_hold_floor_s") or 0.6  # T1 Attardo floor

    import random
    random.seed(42)  # reproducible

    for b in beats:
        bt = b["beat_type"]

        # Pause before this beat (dpv ladder)
        if bt == "opener":
            pause = 0.2
        elif bt == "punchline":
            # T1: dpv coupling: extend pause before surprise; hard floor
            # (Attardo 0.6s, or character override e.g. Buddha 1.5s)
            pause = max(hold_floor, ladder[1] * coupling * (1 + random.uniform(-jitter, jitter)))
        elif bt == "tag":
            pause = ladder[2] * (1 + random.uniform(-jitter, jitter))
        elif bt == "closer":
            pause = ladder[0] * 1.5
        else:  # setup
            pause = ladder[0] * (1 + random.uniform(-jitter, jitter))

        # T2: resolution window AFTER punch/closer (merged with next beat's
        # pre-pause at assemble time via max — one silence between beats)
        pause_after = post_punch if bt in ("punchline", "closer") else 0.0

        # T3: Norrick contrast — factor multiplies profile speed in directions
        speed = BEAT_SPEED.get(bt, 1.0) * MECH_SPEED.get(b["mechanism"], 1.0)

        target_wps = base_wps * min(speed, 1.2)
        target_duration = b["n_words"] / max(target_wps, 0.1)

        b.update({
            "pause_before": round(pause, 2),
            "pause_after": round(pause_after, 2),
            "speed": round(speed, 3),
            "target_wps": round(target_wps, 2),
            "target_duration": round(target_duration, 2),
        })

    return beats


def scale_resolution_windows(beats: list[dict]) -> list[dict]:
    """T4 audience loop: predicted laugh stretches the resolution window
    (don't step on the laugh); cold beats re-enter sooner."""
    for b in beats:
        base = b.get("pause_after", 0.0)
        if base > 0:
            scale = 0.6 + 0.8 * min(max(b.get("p_laugh", 0.5), 0.0), 1.0)
            b["pause_after"] = round(base * scale, 2)
    return beats


# ============================================================
# LAUGH PREDICTION
# ============================================================

def predict_laughs(beats: list[dict], profile: dict) -> list[dict]:
    """Predict laugh probability per beat using delivery-aware model + crowd state.

    Crowd state (heat/momentum) modulates predictions:
    - Hot crowd (killed) = easier laughs
    - Cold crowd = harder laughs
    - Momentum builds during streaks
    """
    import sys
    sys.path.insert(0, str(HERE))
    from delivery_laugh import predict_with_delivery
    from crowd_state import CrowdStateMachine

    crowd = CrowdStateMachine()

    for i, b in enumerate(beats):
        # Predict with delivery features
        pred = predict_with_delivery(
            text=b["text"],
            mechanism=b["mechanism"],
            beat_type=b["beat_type"],
            pause_s=b.get("pause_before", 1.0),
            wps=b.get("target_wps", 2.7),
            pos=i / max(len(beats), 1),
        )

        # Crowd state modulates the prediction
        p_modulated = crowd.predict_next(pred["p_laugh"])
        b["p_laugh"] = round(p_modulated, 3)
        b["p_base"] = pred["p_laugh"]
        b["crowd_heat"] = round(crowd.state.heat, 3)
        b["crowd_momentum"] = crowd.state.momentum

        # Update crowd state based on prediction
        # (in production, this would be actual laughs; here it's predicted)
        will_laugh = p_modulated > 0.45  # lower threshold to match base rates
        laugh_type = "big_laugh" if p_modulated > 0.65 else "laugh"
        crowd.beat(laughed=will_laugh, intensity=p_modulated, laugh_type=laugh_type)

        b["laugh_type"] = crowd.get_laugh_type() if will_laugh else "chuckle"

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
    """Generate Fish TTS direction for a beat (style-aware)."""
    mech = beat["mechanism"]
    bt = beat["beat_type"]

    # Emotion cue
    cue, temp = EMOTION_CUES.get(mech, ("[neutral]", 0.60))

    # Override for beat type
    if bt == "opener":
        cue = "[confident]"
    elif bt == "closer":
        cue = "[warm]"

    # Style vocabulary: forbidden cues fall back to the style's first allowed
    forbidden = set(profile.get("emotion_forbidden") or [])
    allowed = profile.get("emotion_cues") or []
    if cue in forbidden:
        cue = allowed[0] if allowed else "[neutral]"
    if profile.get("temperature") is not None:
        temp = profile["temperature"]

    # T3: desired speed = profile x beat factor. NOT clamped to the clean
    # zone here — fish_tts.tempo_via_prompt decomposes out-of-zone targets
    # into direction language; the API knob never leaves 0.92-1.08.
    desired = profile.get("speed_scale", 1.0) * beat.get("speed", 1.0)
    speed = round(max(0.6, min(1.4, desired)), 3)

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
    """Render one beat with Fish TTS (style volume/temperature/emphasis).

    T5: [emphasis] wraps punch/closer last word — but FLAT styles
    (volume_db <= -2, deadpan) keep important words unstressed: the
    violation lives in the voice, not in stress (manner-max flout).
    T6: fish prosody.volume = style volume floor + beat-type nudge
    (nudges halved on flat styles so the envelope stays flat).
    """
    import sys
    sys.path.insert(0, str(HERE))
    from fish_tts import synthesize_fish, emphasize_last, TYPE_VOLUME_DB

    direction = beat.get("_direction", {})
    text = beat["text"]
    cue = direction.get("emotion_cue", "")
    speed = direction.get("speed", 1.0)
    temp = direction.get("temperature", 0.60)
    bt = beat["beat_type"]

    flat = (profile.get("volume_db") or 0) <= -2
    if not flat and bt in ("punchline", "closer"):
        text = emphasize_last(text)

    nudge = TYPE_VOLUME_DB.get(bt, 0.0) * (0.5 if flat else 1.0)
    volume = round((profile.get("volume_db") or 0.0) + nudge, 1)

    # Render
    audition_id = f"delivery-{hashlib.md5(text.encode()).hexdigest()[:8]}"

    result = synthesize_fish(
        audition_id,
        text,
        modulator="neutral" if not cue else cue.strip("[]"),
        temperature=temp,
        prosody={"speed": speed, "volume": volume},
        voice=clone_id or profile.get("voice_fish_id"),
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
    seal_dir: str | Path | None = None,
) -> RenderResult:
    """Full pipeline: text → directed audio with timings.

    Args:
        text: the comedian's minute
        comedian: profile name (louis, kam, default, etc.) or freak slug
        clone_id: Fish voice clone ID (None = default voice)
        output_name: output file name (auto-generated if None)
        seal_dir: also write freaktown sealed-set.v1 bundle (seal_set.py)

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

    # 4b. T4: audience loop — predicted laughs stretch resolution windows
    beats = scale_resolution_windows(beats)

    # 5. Generate directions
    for b in beats:
        b["_direction"] = generate_direction(b, profile)

    # 6. Render each beat — concurrent (network-bound Fish calls; order of
    # beats is preserved regardless of completion order). DELIVERY_THREADS=0
    # forces sequential (debugging).
    from concurrent.futures import ThreadPoolExecutor
    workers = int(os.environ.get("DELIVERY_THREADS", "3"))

    def _one(b):
        try:
            return b, render_beat(b, profile, clone_id), None
        except Exception as e:
            return b, None, e

    jobs = []
    if workers > 1 and len(beats) > 2:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = list(pool.map(_one, beats))
    else:
        jobs = [_one(b) for b in beats]

    rendered = []
    for b, r, err in jobs:
        if err is not None:
            print(f"  Beat {b['index']} render failed: {err}")
            b["_rendered"] = None
        else:
            b["_rendered"] = r
            rendered.append(r)

    # 7. Assemble audio
    if output_name is None:
        output_name = f"delivery-{comedian}-{int(time.time())}"

    audio_path = AUDIO_DIR / f"{output_name}.wav"
    assembled = assemble_audio(beats, audio_path)

    # 8. Build timeline
    timeline = build_timeline(beats)

    # 9. Stats
    stats = compute_stats(beats, profile, comedian)

    # 10. Optional sealed-set export (needs post-render beats for durations)
    if seal_dir:
        import seal_set
        char_path = FREAKS / comedian / "character.json"
        character = json.loads(char_path.read_text()) if char_path.exists() else {}
        sealed = seal_set.seal(beats, profile, character, comedian,
                               audio_path, Path(seal_dir))
        stats["sealed"] = sealed

    return RenderResult(
        audio_path=str(audio_path),
        duration_ms=assembled.get("duration_ms", 0),
        beats=[{k: v for k, v in b.items() if not k.startswith("_")} for b in beats],
        timeline=timeline,
        stats=stats,
        provenance=f"fish-tts:s2.1-pro-free+delivery-engine+{comedian}",
    )


def assemble_audio(beats: list[dict], output_path: Path) -> dict:
    """Assemble rendered beats: [gap][audio][gap][audio]...[trailing].

    Gap between beats = max(this beat's pause_before, previous beat's
    pause_after) — the pre-punch hold (T1) and the resolution window (T2)
    are the SAME silence when they stack; nothing doubles up.
    Trailing silence = last beat's pause_after (laugh-out window).
    """
    import numpy as np

    rendered_beats = [b for b in beats if b.get("_rendered")]
    if not rendered_beats:
        return {"duration_ms": 0}

    # Decode each beat
    segments = []
    prev_after = 0.0
    for b in rendered_beats:
        gap_s = max(b.get("pause_before", 0.5), prev_after)
        if gap_s > 0.01:
            segments.append(np.zeros(int(gap_s * 44100), dtype=np.float32))
        path = b["_rendered"]["path"]
        result = subprocess.run(
            ["ffmpeg", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
            capture_output=True, timeout=30
        )
        audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        segments.append(audio)
        prev_after = b.get("pause_after", 0.0)

    if prev_after > 0.01:
        segments.append(np.zeros(int(prev_after * 44100), dtype=np.float32))

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
    """Build a timeline of beats with timings and predictions (matches audio)."""
    timeline = []
    t = 0.0
    prev_after = 0.0
    for b in beats:
        gap = max(b.get("pause_before", 0.5), prev_after)
        dur = b.get("target_duration", 2.0)
        t += gap

        timeline.append({
            "time_s": round(t, 2),
            "beat_index": b["index"],
            "beat_type": b["beat_type"],
            "mechanism": b["mechanism"],
            "p_laugh": b.get("p_laugh", 0),
            "laugh_type": b.get("laugh_type", ""),
            "gap_before": round(gap, 2),
            "pause_after": b.get("pause_after", 0),
            "target_duration": dur,
            "text_preview": b["text"][:60],
        })

        t += dur
        prev_after = b.get("pause_after", 0.0)

    return timeline


def compute_stats(beats: list[dict], profile: dict, comedian: str = "default") -> dict:
    """Compute delivery stats."""
    n = len(beats)
    laugh_beats = [b for b in beats if b.get("p_laugh", 0) > 0.65]  # higher threshold
    total_pause = sum(b.get("pause_before", 0) + b.get("pause_after", 0)
                      for b in beats)
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
    p.add_argument("--seal", help="Also write sealed-set.v1 bundle to DIR (freaktown)")
    p.add_argument("--dry-run", action="store_true", help="Show plan without rendering")
    args = p.parse_args()

    text = Path(args.text_file).read_text()

    if args.dry_run:
        profile = load_profile(args.comedian)
        beats = segment_beats(text)
        beats = assign_timings(beats, profile)
        beats = predict_laughs(beats, profile)
        beats = scale_resolution_windows(beats)
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
        result = render_minute(text, args.comedian, args.clone, args.out,
                               seal_dir=args.seal)
        print(f"\nRendered: {result.audio_path}")
        print(f"Duration: {result.duration_ms/1000:.1f}s")
        print(f"Beats: {result.stats['n_beats']}")
        print(f"Predicted laughs: {result.stats['predicted_laughs']}")
        print(f"Laughter rate: {result.stats['laugh_rate']:.1%}")
        print(f"\nTimeline:")
        for t in result.timeline:
            bar = "█" * int(t["p_laugh"] * 10)
            print(f"  {t['time_s']:>6.1f}s [{t['beat_type']:10s}] {t['p_laugh']:.2f} {bar} | {t['text_preview'][:30]}")
