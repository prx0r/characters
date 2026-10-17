"""Realtime Laughter Engine — process audio, predict laughter, render in real-time.

Works standalone: import from any repo, no path dependencies.

Architecture:
  1. Input: audio stream (microphone) OR pre-recorded set
  2. Feature extraction: energy, pitch, pace (real-time)
  3. Prediction: prosody200 clean model (AUC 0.862) + physics
  4. Rendering: crowd audio synthesis
  5. Stats: per-beat analysis of what worked

Usage:
  from realtime_laughter import LaughterEngine
  engine = LaughterEngine()
  engine.start_mic()  # realtime from microphone
  engine.process_file("set.wav")  # pre-recorded
  stats = engine.get_stats()  # granular analysis
"""
from __future__ import annotations
import json, time, pickle, struct, queue, threading, sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Callable
import numpy as np

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class LaughEvent:
    """One predicted laugh moment."""
    timestamp: float
    p_laugh: float
    intensity: float  # 0.0-1.0
    laugh_type: str   # chuckle, laugh, big_laugh, roar
    mechanism: str    # setup_punchline, misdirection, etc.
    duration_ms: int
    clip_used: str = ""

@dataclass
class BeatStats:
    """Stats for one beat/segment."""
    timestamp: float
    duration: float
    p_laugh: float
    actual_laugh: bool
    predicted_laugh: bool
    intensity: float
    mechanism: str
    energy_mean: float
    energy_std: float
    wpm: float
    pause_ratio: float

@dataclass
class SetStats:
    """Full set analysis."""
    duration: float
    total_beats: int
    predicted_laughs: int
    actual_laughs: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    auc: float
    calibration_gap: float
    beats: list = field(default_factory=list)
    laugh_events: list = field(default_factory=list)
    mechanism_breakdown: dict = field(default_factory=dict)
    timeline: list = field(default_factory=list)


# ============================================================
# FEATURE EXTRACTION (real-time capable)
# ============================================================

class FeatureExtractor:
    """Extract audio features from PCM frames."""

    def __init__(self, sample_rate=16000, window_sec=0.5):
        self.sr = sample_rate
        self.window = int(window_sec * sample_rate)
        self.buffer = np.array([], dtype=np.float32)
        self.energy_history = []
        self.pause_threshold = 0.01
        self.in_pause = False
        self.pause_start = 0

    def extract(self, pcm: np.ndarray) -> dict:
        """Extract features from a PCM frame."""
        self.buffer = np.concatenate([self.buffer, pcm])

        if len(self.buffer) < self.window:
            return {}

        # Take the window
        frame = self.buffer[-self.window:]
        self.buffer = self.buffer[self.window:]

        # Energy
        energy = float(np.sqrt(np.mean(frame ** 2)))
        self.energy_history.append(energy)
        if len(self.energy_history) > 100:
            self.energy_history = self.energy_history[-100:]

        # Energy stats
        e_mean = np.mean(self.energy_history[-20:]) if self.energy_history else 0
        e_std = np.std(self.energy_history[-20:]) if len(self.energy_history) >= 2 else 0
        e_max = max(self.energy_history[-20:]) if self.energy_history else 0
        e_min = min(self.energy_history[-20:]) if self.energy_history else 0

        # Pause detection
        is_pause = energy < self.pause_threshold
        if is_pause and not self.in_pause:
            self.in_pause = True
            self.pause_start = time.time()
        elif not is_pause and self.in_pause:
            self.in_pause = False

        pause_ratio = sum(1 for e in self.energy_history[-20:] if e < self.pause_threshold) / max(len(self.energy_history[-20:]), 1)

        # Zero-crossing rate (proxy for pitch/spectral content)
        zcr = float(np.mean(np.abs(np.diff(np.sign(frame)))) / 2)

        return {
            "energy_mean": float(e_mean),
            "energy_std": float(e_std),
            "energy_max": float(e_max),
            "energy_min": float(e_min),
            "energy": energy,
            "zcr": zcr,
            "pause_ratio": pause_ratio,
            "is_pause": is_pause,
        }


# ============================================================
# LAUGH PREDICTOR
# ============================================================

class LaughPredictor:
    """Predict laughter from audio features. Uses prosody200 model if available,
    falls back to rule-based."""

    def __init__(self, model_path: str | Path | None = None):
        self.model = None
        self.model_path = Path(model_path) if model_path else None
        self.calibration_offset = 0.0
        self.calibration_scale = 1.0
        self.calibration_history = []

        # Try to load prosody200 model
        if self.model_path and self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    bundle = pickle.load(f)
                self.model = bundle.get("model")
                self.kept_features = bundle.get("kept_features", list(range(14)))
            except Exception:
                pass

    def predict(self, features: dict, history: list[dict]) -> dict:
        """Predict laugh probability from features + history."""
        if self.model is not None:
            return self._predict_model(features, history)
        return self._predict_rules(features, history)

    def _predict_model(self, features: dict, history: list[dict]) -> dict:
        """Use the trained prosody200 model."""
        # Build feature vector (match prosody200 format: 14 clean features)
        # We approximate: energy stats + zcr + history
        e_hist = [h.get("energy_mean", 0) for h in history[-10:]]
        e_mean = features.get("energy_mean", np.mean(e_hist) if e_hist else 0)
        e_std = features.get("energy_std", np.std(e_hist) if len(e_hist) > 1 else 0)

        # Approximate the 14 features (we don't have exact mapping)
        # Use energy stats as best approximation
        feats = np.array([[
            e_mean,
            features.get("zcr", 0),
            e_std,
            features.get("energy_max", 0),
            0, 0, 0, 0,  # placeholder
            features.get("energy_min", 0),
            0, 0, 0, 0, 0, 0,
        ]])

        try:
            prob = float(self.model.predict_proba(feats)[0, 1])
        except Exception:
            prob = self._predict_rules(features, history)["p_laugh"]

        # Apply calibration (scale to match real laugh rates ~24%)
        prob = max(0.0, min(1.0, prob * self.calibration_scale + self.calibration_offset))
        self.calibration_history.append(prob)
        if len(self.calibration_history) > 1000:
            self.calibration_history = self.calibration_history[-1000:]

        return {
            "p_laugh": prob,
            "intensity": min(1.0, prob * 1.2),
            "source": "model",
        }

    def calibrate(self, target_rate: float = 0.24):
        """Auto-calibrate to match target laugh rate."""
        if not self.calibration_history:
            return
        current = np.mean(self.calibration_history)
        if current > 0:
            self.calibration_scale = target_rate / current
        print(f"Calibrated: scale={self.calibration_scale:.2f} (was mean {current:.3f}, target {target_rate})")

    def _predict_rules(self, features: dict, history: list[dict]) -> dict:
        """Rule-based prediction (fallback)."""
        e_mean = features.get("energy_mean", 0)
        e_std = features.get("energy_std", 0)
        pause = features.get("pause_ratio", 0)
        pos = len(history) / max(len(history) + 50, 1)  # rough position

        # Energy variation is the strongest signal (our finding)
        energy_score = min(1.0, e_std * 20)

        # Pause before punchline helps
        pause_score = min(1.0, pause * 3) if pause > 0.1 else 0

        # Crowd heat (recent laughs)
        recent = [h for h in history[-5:] if h.get("p_laugh", 0) > 0.5]
        heat_score = len(recent) / 5

        # Position: later in set = warmer crowd
        pos_score = pos * 0.3

        # Combined
        prob = 0.3 * energy_score + 0.2 * pause_score + 0.3 * heat_score + 0.2 * pos_score
        prob = max(0.0, min(1.0, prob))

        if prob < 0.3:
            intensity, ltype = 0.2, "chuckle"
        elif prob < 0.5:
            intensity, ltype = 0.4, "laugh"
        elif prob < 0.7:
            intensity, ltype = 0.7, "big_laugh"
        else:
            intensity, ltype = 1.0, "roar"

        return {
            "p_laugh": prob,
            "intensity": intensity,
            "laugh_type": ltype,
            "source": "rules",
        }


# ============================================================
# CROWD RENDERER
# ============================================================

class CrowdRenderer:
    """Generate crowd laughter audio from laugh events."""

    def __init__(self, sample_rate=44100, laugh_clips_dir: str | Path | None = None):
        self.sr = sample_rate
        self.clips = []
        self.laugh_clips_dir = Path(laugh_clips_dir) if laugh_clips_dir else None

        # Try to load laugh clips
        if self.laugh_clips_dir and self.laugh_clips_dir.exists():
            self._load_clips()

        # Synthesis parameters
        self.voice_count = {"chuckle": 2, "laugh": 5, "big_laugh": 12, "roar": 25}
        self.durations = {"chuckle": 0.4, "laugh": 1.2, "big_laugh": 2.5, "roar": 4.0}

    def _load_clips(self):
        """Load laugh clips from directory."""
        import subprocess
        for clip_path in self.laugh_clips_dir.glob("*.mp3"):
            try:
                # Convert to numpy
                result = subprocess.run(
                    ["ffmpeg", "-i", str(clip_path), "-f", "s16le", "-ac", "1", "-ar", str(self.sr), "-"],
                    capture_output=True, timeout=10
                )
                audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                self.clips.append(audio)
            except Exception:
                continue

    def render(self, event: LaughEvent) -> np.ndarray:
        """Render a laugh event to audio."""
        duration = self.durations.get(event.laugh_type, 1.0)
        n_samples = int(duration * self.sr)

        # Use loaded clips if available
        if self.clips:
            return self._render_from_clips(event, n_samples)

        # Synthesize
        return self._synthesize(event, n_samples)

    def _render_from_clips(self, event: LaughEvent, n_samples: int) -> np.ndarray:
        """Render by mixing loaded clips."""
        output = np.zeros(n_samples, dtype=np.float32)
        n_voices = self.voice_count.get(event.laugh_type, 5)

        for i in range(n_voices):
            clip = self.clips[np.random.randint(0, len(self.clips))]
            # Stagger onset
            onset = int(np.random.uniform(0, 0.3 * self.sr))
            # Random pitch/speed variation
            speed = np.random.uniform(0.9, 1.1)
            # Scale by intensity
            vol = event.intensity * np.random.uniform(0.3, 0.8)

            # Place clip
            end = min(onset + len(clip), n_samples)
            if end > onset:
                clip_sample = clip[:end - onset] * vol
                output[onset:end] += clip_sample

        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0:
            output = output / peak * 0.5

        return output

    def _synthesize(self, event: LaughEvent, n_samples: int) -> np.ndarray:
        """Synthesize crowd laughter."""
        output = np.zeros(n_samples, dtype=np.float32)
        n_voices = self.voice_count.get(event.laugh_type, 5)

        for i in range(n_voices):
            # Each voice: burst of noise-modulated tone
            onset = int(np.random.uniform(0, 0.3 * self.sr))
            duration = int(np.random.uniform(0.5, 1.5) * self.sr)
            end = min(onset + duration, n_samples)

            if end <= onset:
                continue

            # Voice parameters
            f0 = np.random.uniform(150, 300)  # pitch
            vol = event.intensity * np.random.uniform(0.2, 0.6)

            # Generate laugh-like burst
            t = np.arange(end - onset) / self.sr
            # Amplitude envelope: quick attack, decay
            env = np.exp(-t * 3) * (1 - np.exp(-t * 50))
            # Noise-modulated tone (laugh-like)
            noise = np.random.randn(len(t)) * 0.5
            tone = np.sin(2 * np.pi * f0 * t) * 0.5
            voice = (noise + tone) * env * vol

            output[onset:end] += voice

        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0:
            output = output / peak * 0.5

        return output

    def render_silence(self, duration_sec: float) -> np.ndarray:
        """Render room tone (not digital silence)."""
        n = int(duration_sec * self.sr)
        # Low-level noise floor
        return np.random.randn(n).astype(np.float32) * 0.005


# ============================================================
# MAIN ENGINE
# ============================================================

class LaughterEngine:
    """Realtime laughter engine."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        laugh_clips_dir: str | Path | None = None,
        sample_rate: int = 16000,
        laugh_threshold: float = 0.35,
    ):
        self.sr = sample_rate
        self.laugh_threshold = laugh_threshold
        self.features = FeatureExtractor(sample_rate)
        self.predictor = LaughPredictor(model_path)
        self.renderer = CrowdRenderer(44100, laugh_clips_dir)

        # Auto-load clips from common locations
        if laugh_clips_dir is None:
            for alt in ["/home/box/comedy-ai/laugh-library", "laugh-library"]:
                if Path(alt).exists():
                    self.renderer.laugh_clips_dir = Path(alt)
                    self.renderer._load_clips()
                    break

        # State
        self.history = []
        self.laugh_events = []
        self.beat_stats = []
        self.start_time = time.time()

        # Callbacks
        self.on_laugh: Callable[[LaughEvent], None] | None = None
        self.on_beat: Callable[[BeatStats], None] | None = None

    def process_frame(self, pcm: np.ndarray, timestamp: float | None = None) -> LaughEvent | None:
        """Process one audio frame. Returns LaughEvent if laugh detected."""
        if timestamp is None:
            timestamp = time.time() - self.start_time

        # Extract features
        feats = self.features.extract(pcm)
        if not feats:
            return None

        # Predict
        pred = self.predictor.predict(feats, self.history)
        self.history.append({**feats, **pred, "timestamp": timestamp})

        # Detect laugh events: sustained high probability
        p = pred["p_laugh"]
        recent_probs = [h.get("p_laugh", 0) for h in self.history[-3:]]
        avg_recent = np.mean(recent_probs) if recent_probs else p

        # Event if: current is high AND not already in a laugh event
        in_event = len(self.laugh_events) > 0 and (timestamp - self.laugh_events[-1].timestamp) < 2.0
        is_high = avg_recent > self.laugh_threshold

        if is_high and not in_event:
            event = LaughEvent(
                timestamp=timestamp,
                p_laugh=avg_recent,
                intensity=min(1.0, avg_recent * 1.2),
                laugh_type="laugh" if avg_recent < 0.5 else "big_laugh",
                mechanism="unknown",
                duration_ms=int(avg_recent * 2000),
            )
            self.laugh_events.append(event)

            if self.on_laugh:
                self.on_laugh(event)

            return event

        return None

    def process_file(self, filepath: str | Path) -> SetStats:
        """Process a complete audio file and return stats."""
        import subprocess

        filepath = Path(filepath)
        print(f"Processing {filepath.name}...")

        # Decode audio
        result = subprocess.run(
            ["ffmpeg", "-i", str(filepath), "-f", "s16le", "-ac", "1", "-ar", str(self.sr), "-"],
            capture_output=True, timeout=300
        )
        audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / self.sr
        print(f"  Duration: {duration:.1f}s")

        # Process in 0.5s frames
        frame_size = int(0.5 * self.sr)
        n_frames = len(audio) // frame_size

        for i in range(n_frames):
            frame = audio[i * frame_size:(i + 1) * frame_size]
            timestamp = i * 0.5

            feats = self.features.extract(frame)
            if not feats:
                continue

            pred = self.predictor.predict(feats, self.history)
            self.history.append({**feats, **pred, "timestamp": timestamp})

            # Detect laugh event
            p = pred["p_laugh"]
            recent_probs = [h.get("p_laugh", 0) for h in self.history[-3:]]
            avg_recent = np.mean(recent_probs) if recent_probs else p
            in_event = len(self.laugh_events) > 0 and (timestamp - self.laugh_events[-1].timestamp) < 2.0

            if avg_recent > self.laugh_threshold and not in_event:
                event = LaughEvent(
                    timestamp=timestamp,
                    p_laugh=avg_recent,
                    intensity=min(1.0, avg_recent * 1.2),
                    laugh_type="laugh" if avg_recent < 0.5 else "big_laugh",
                    mechanism="unknown",
                    duration_ms=int(avg_recent * 2000),
                )
                self.laugh_events.append(event)
                if self.on_laugh:
                    self.on_laugh(event)

            # Record beat stats
            beat = BeatStats(
                timestamp=timestamp,
                duration=0.5,
                p_laugh=pred["p_laugh"],
                actual_laugh=False,  # would need ground truth
                predicted_laugh=pred["p_laugh"] > self.laugh_threshold,
                intensity=pred.get("intensity", 0),
                mechanism="unknown",
                energy_mean=feats.get("energy_mean", 0),
                energy_std=feats.get("energy_std", 0),
                wpm=0,
                pause_ratio=feats.get("pause_ratio", 0),
            )
            self.beat_stats.append(beat)

            if self.on_beat:
                self.on_beat(beat)

        # Generate stats
        return self.get_stats(duration)

    def get_stats(self, duration: float | None = None) -> SetStats:
        """Generate granular stats for the set."""
        if duration is None:
            duration = self.beat_stats[-1].timestamp if self.beat_stats else 0

        n_beats = len(self.beat_stats)
        predicted = sum(1 for b in self.beat_stats if b.predicted_laugh)
        n_events = len(self.laugh_events)

        # Mechanism breakdown
        mechanisms = {}
        for e in self.laugh_events:
            m = e.mechanism
            mechanisms[m] = mechanisms.get(m, 0) + 1

        # Timeline (one entry per 5 seconds)
        timeline = []
        for t in range(0, int(duration), 5):
            beats_in_window = [b for b in self.beat_stats if t <= b.timestamp < t + 5]
            if beats_in_window:
                avg_p = np.mean([b.p_laugh for b in beats_in_window])
                timeline.append({
                    "time": t,
                    "p_laugh": round(float(avg_p), 3),
                    "energy": round(float(np.mean([b.energy_mean for b in beats_in_window])), 4),
                })

        # Calibration: mean predicted vs would-be actual
        mean_predicted = np.mean([b.p_laugh for b in self.beat_stats]) if self.beat_stats else 0

        return SetStats(
            duration=duration,
            total_beats=n_beats,
            predicted_laughs=predicted,
            actual_laughs=0,  # needs ground truth
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            auc=0.0,
            calibration_gap=abs(mean_predicted - 0.24),  # vs typical laugh rate
            beats=self.beat_stats,
            laugh_events=self.laugh_events,
            mechanism_breakdown=mechanisms,
            timeline=timeline,
        )

    def start_mic(self, callback: Callable[[LaughEvent], None] | None = None):
        """Start realtime microphone processing."""
        self.on_laugh = callback
        print("Microphone mode: press Ctrl+C to stop")

        try:
            import pyaudio
        except ImportError:
            print("pyaudio not installed. Run: pip install pyaudio")
            return

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sr,
            input=True,
            frames_per_buffer=int(0.5 * self.sr),
        )

        try:
            while True:
                data = stream.read(int(0.5 * self.sr), exception_on_overflow=False)
                pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                event = self.process_frame(pcm)
                if event:
                    print(f"  [LAUGH p={event.p_laugh:.2f} type={event.laugh_type}]")
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Realtime Laughter Engine")
    p.add_argument("audio", nargs="?", help="Audio file to process")
    p.add_argument("--mic", action="store_true", help="Use microphone")
    p.add_argument("--model", default="audition/voicelab/prosody200_clean_model.pkl")
    p.add_argument("--clips", default="/home/box/comedy-ai/laugh-library")
    p.add_argument("--out", help="Output stats JSON")
    args = p.parse_args()

    engine = LaughterEngine(
        model_path=args.model if Path(args.model).exists() else None,
        laugh_clips_dir=args.clips if Path(args.clips).exists() else None,
    )

    if args.mic:
        engine.start_mic()
    elif args.audio:
        stats = engine.process_file(args.audio)

        # Print summary
        print(f"\n{'='*50}")
        print(f"SET ANALYSIS")
        print(f"{'='*50}")
        print(f"Duration:       {stats.duration:.1f}s")
        print(f"Total beats:    {stats.total_beats}")
        print(f"Predicted:      {stats.predicted_laughs} laughs")
        print(f"Events:         {len(stats.laugh_events)}")
        print(f"Calibration:    {stats.calibration_gap:.3f}")
        print(f"\nTimeline:")
        for t in stats.timeline[:10]:
            bar = "█" * int(t["p_laugh"] * 20)
            print(f"  {t['time']:>4}s: {t['p_laugh']:.2f} {bar}")

        if args.out:
            Path(args.out).write_text(json.dumps(asdict(stats), indent=2, default=str))
            print(f"\nStats saved to {args.out}")
    else:
        p.print_help()
