"""Laugh Track Renderer — mixes real laugh clips into audio at predicted moments.

Uses the 6 CC0 laugh clips with their ADSR envelopes.
No noise synthesis. Real crowd audio only.

Usage:
  from laugh_track_renderer import LaughTrackRenderer
  r = LaughTrackRenderer()
  r.load_voice_audio("set.wav")
  r.add_laugh(timestamp_s=12.5, laugh_type="big_laugh", intensity=0.8)
  r.add_laugh(timestamp_s=18.0, laugh_type="laugh", intensity=0.6)
  r.render("output.wav")  # voice + laughs mixed
"""
from __future__ import annotations
import json, subprocess, struct
from pathlib import Path
import numpy as np

CLIPS_DIR = Path("/home/box/comedy-ai/laugh-library")
ADSR_PATH = CLIPS_DIR / "laugh_adsr.json"
LIBRARY_PATH = CLIPS_DIR / "laugh_library.json"


class LaughTrackRenderer:
    """Mix real laugh clips into voice audio at timestamps."""

    def __init__(self, sample_rate=44100):
        self.sr = sample_rate
        self.voice = np.array([], dtype=np.float32)
        self.clips = {}  # name -> (audio, adsr, library_info)
        self.laughs = []  # (timestamp_s, laugh_type, intensity)
        self._load_clips()

    def _load_clips(self):
        """Load all laugh clips with ADSR envelopes."""
        if not CLIPS_DIR.exists():
            return

        adsr = {}
        if ADSR_PATH.exists():
            adsr = json.loads(ADSR_PATH.read_text())

        library = {}
        if LIBRARY_PATH.exists():
            library = json.loads(LIBRARY_PATH.read_text())

        for clip_path in CLIPS_DIR.glob("*.mp3"):
            name = clip_path.stem
            try:
                result = subprocess.run(
                    ["ffmpeg", "-i", str(clip_path), "-f", "s16le", "-ac", "1",
                     "-ar", str(self.sr), "-"],
                    capture_output=True, timeout=15
                )
                audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                self.clips[name] = {
                    "audio": audio,
                    "adsr": adsr.get(name, {}),
                    "info": library.get(name, {}),
                }
            except Exception:
                continue

    def load_voice_audio(self, path: str | Path):
        """Load the voice/comedy audio to mix laughs into."""
        result = subprocess.run(
            ["ffmpeg", "-i", str(path), "-f", "s16le", "-ac", "1",
             "-ar", str(self.sr), "-"],
            capture_output=True, timeout=60
        )
        self.voice = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0

    def add_laugh(self, timestamp_s: float, laugh_type: str = "laugh", intensity: float = 0.6):
        """Queue a laugh at a timestamp."""
        self.laughs.append((timestamp_s, laugh_type, intensity))

    def _select_clip(self, laugh_type: str, intensity: float) -> dict | None:
        """Select the best clip for a laugh type + intensity.

        Reject clips longer than 10s — those are applause tracks, not laughs.
        """
        if not self.clips:
            return None

        scored = []
        for name, clip in self.clips.items():
            clip_intensity = clip["info"].get("intensity", 0.5)
            clip_dur = clip["info"].get("duration_s", 999)

            # Skip clips that are too long (applause tracks)
            if clip_dur > 10.0:
                continue

            # Type matching
            type_match = 0
            if laugh_type == "roar" and clip_intensity > 0.7:
                type_match = 1
            elif laugh_type == "big_laugh" and 0.5 < clip_intensity <= 0.9:
                type_match = 1
            elif laugh_type == "laugh" and 0.3 < clip_intensity <= 0.7:
                type_match = 1
            elif laugh_type == "chuckle" and clip_intensity <= 0.4:
                type_match = 1

            dist = abs(clip_intensity - intensity)
            # Prefer shorter clips (real laughs, not sustained applause)
            dur_penalty = clip_dur / 20.0

            scored.append((-(type_match - dist - dur_penalty), name, clip))

        scored.sort(key=lambda x: x[0])
        return scored[0][2] if scored else None

    def _apply_adsr(self, audio: np.ndarray, adsr: dict, intensity: float, max_dur_s: float = 2.5) -> np.ndarray:
        """Apply ADSR envelope to a laugh clip.

        Truncates to max_dur_s. High intensity = longer laugh.
        """
        # Duration scales with intensity: chuckle ~1s, roar ~3s
        max_dur = max_dur_s * (0.4 + intensity * 0.6)
        max_n = int(max_dur * self.sr)
        if len(audio) > max_n:
            audio = audio[:max_n]

        n = len(audio)
        if n == 0 or not adsr:
            return audio * intensity

        attack_s = min(adsr.get("attack_s", 0.1), max_dur_s * 0.3)
        decay_s = adsr.get("decay_s", 0.1)
        sustain_level = adsr.get("sustain_level", 0.5)
        release_s = min(adsr.get("release_s", 0.5), max_dur_s * 0.4)

        attack_n = int(attack_s * self.sr)
        decay_n = int(decay_s * self.sr)
        release_n = int(release_s * self.sr)
        sustain_n = max(0, n - attack_n - decay_n - release_n)

        envelope = np.concatenate([
            np.linspace(0, 1, attack_n, endpoint=False),
            np.linspace(1, sustain_level, decay_n, endpoint=False),
            np.full(sustain_n, sustain_level),
            np.linspace(sustain_level, 0, release_n),
        ])

        # Pad or trim envelope to match audio length
        if len(envelope) < n:
            envelope = np.pad(envelope, (0, n - len(envelope)))
        else:
            envelope = envelope[:n]

        return audio * envelope * intensity

    def _place_laugh(self, output: np.ndarray, clip_audio: np.ndarray, timestamp_s: float, intensity: float):
        """Place a laugh clip at a timestamp with fade-in."""
        onset = int(timestamp_s * self.sr)
        if onset >= len(output):
            return

        end = min(onset + len(clip_audio), len(output))
        segment = clip_audio[:end - onset]

        # Fade-in 50ms to avoid clicks
        fade_n = int(0.05 * self.sr)
        if fade_n < len(segment):
            segment = segment.copy()
            segment[:fade_n] *= np.linspace(0, 1, fade_n)

        output[onset:end] += segment

    def render(self, output_path: str | Path, room_tone_db: float = -40.0) -> dict:
        """Render voice + laugh track to file.

        Args:
            output_path: output WAV file
            room_tone_db: background noise floor (dB)

        Returns:
            dict with stats about the render
        """
        if len(self.voice) == 0:
            raise RuntimeError("No voice audio loaded. Call load_voice_audio() first.")

        output = self.voice.copy()

        # Mix laugh clips at timestamps
        clips_used = []
        for timestamp_s, laugh_type, intensity in self.laughs:
            clip = self._select_clip(laugh_type, intensity)
            if clip is None:
                continue

            adsr = clip["adsr"]
            shaped = self._apply_adsr(clip["audio"], adsr, intensity)
            self._place_laugh(output, shaped, timestamp_s, intensity)
            clips_used.append({
                "timestamp": timestamp_s,
                "type": laugh_type,
                "intensity": intensity,
                "clip_duration_s": round(len(shaped) / self.sr, 2),
            })

        # Add room tone (not digital silence)
        noise = np.random.randn(len(output)).astype(np.float32)
        noise = noise * (10 ** (room_tone_db / 20))
        output += noise

        # Normalize to prevent clipping
        peak = np.max(np.abs(output))
        if peak > 0.95:
            output = output / peak * 0.95

        # Write WAV
        pcm = (output * 32767).astype(np.int16).tobytes()
        with open(output_path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + len(pcm)))
            f.write(b"WAVEfmt ")
            f.write(struct.pack("<IHHIIHH", 16, 1, 1, self.sr, self.sr * 2, 2, 16))
            f.write(b"data")
            f.write(struct.pack("<I", len(pcm)))
            f.write(pcm)

        duration_s = len(output) / self.sr
        laugh_dur = sum(c["clip_duration_s"] for c in clips_used)

        return {
            "output": str(output_path),
            "duration_s": round(duration_s, 1),
            "n_laughs": len(clips_used),
            "laugh_seconds": round(laugh_dur, 1),
            "laugh_density": round(laugh_dur / max(duration_s, 1), 3),
            "clips_used": clips_used,
            "peak_db": round(20 * np.log10(peak + 1e-10), 1),
        }


if __name__ == "__main__":
    r = LaughTrackRenderer()
    print(f"Loaded {len(r.clips)} clips: {list(r.clips.keys())}")
    for name, clip in r.clips.items():
        intensity = clip["info"].get("intensity", "?")
        dur = clip["info"].get("duration_s", "?")
        attack = clip["adsr"].get("attack_s", "?")
        print(f"  {name}: intensity={intensity} dur={dur}s attack={attack}s")
