"""Extract per-beat audio features from KT sets (T2 fix).

librosa_features.json has per-STEM features (constant across beats).
We need per-BEAT features: f0_std, energy_std, centroid within each beat window.

Output: kt_beats_enhanced.jsonl — beats with per-beat audio features.
"""
from __future__ import annotations
import json, subprocess, tempfile, os, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

BEATS_PATH = Path("/home/box/comedy-audio/laugh_training_beats.jsonl")
KT_DIR = Path("/home/box/comedy-audio/kt-sets")
OUT = Path(__file__).parent / "voicelab" / "kt_beats_enhanced.jsonl"


def extract_beat_features(audio_path: str, beat_start: float, beat_end: float, sr: int = 16000) -> dict:
    """Extract audio features within a beat window."""
    import librosa

    # Load only the beat window
    y, sr = librosa.load(audio_path, sr=sr, offset=max(0, beat_start), duration=beat_end - beat_start)

    if len(y) < sr * 0.1:
        return {}

    # F0 (pitch)
    f0 = librosa.yin(y, fmin=60, fmax=400, sr=sr)
    f0_valid = f0[f0 > 0]
    f0_std = float(np.std(f0_valid)) if len(f0_valid) > 1 else 0

    # Energy
    rms = librosa.feature.rms(y=y)[0]
    rms_std = float(np.std(rms))
    rms_mean = float(np.mean(rms))

    # Spectral centroid
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    cent_mean = float(np.mean(cent))

    # ZCR
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    zcr_mean = float(np.mean(zcr))

    # MFCCs
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc1 = float(np.mean(mfccs[0]))
    mfcc2 = float(np.mean(mfccs[1]))

    # Onset rate
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_rate = len(onsets) / max(len(y) / sr, 0.1)

    return {
        "f0_std": round(f0_std, 2),
        "rms_std": round(rms_std, 5),
        "rms_mean": round(rms_mean, 5),
        "cent_mean": round(cent_mean, 1),
        "zcr_mean": round(zcr_mean, 4),
        "mfcc1": round(mfcc1, 2),
        "mfcc2": round(mfcc2, 2),
        "onset_rate": round(onset_rate, 2),
    }


def main():
    import librosa  # check available

    beats = [json.loads(l) for l in open(BEATS_PATH)]
    print(f"Loading {len(beats)} beats")

    # Group by stem
    stems = {}
    for b in beats:
        stems.setdefault(b["stem"], []).append(b)

    enhanced = []
    for stem, stem_beats in stems.items():
        # Find audio file
        audio_path = None
        for ext in [".m4a", ".mp3", ".webm"]:
            p = KT_DIR / f"{stem}{ext}"
            if p.exists():
                audio_path = str(p)
                break

        if not audio_path:
            print(f"  SKIP {stem}: no audio")
            continue

        # Get total duration
        duration = max(b["pos"] + b["dur"] for b in stem_beats) + 10

        print(f"  Processing {stem}: {len(stem_beats)} beats")

        for b in stem_beats:
            beat_start = b["pos"] * duration
            beat_end = beat_start + b["dur"]

            audio_feats = extract_beat_features(audio_path, beat_start, beat_end)

            enhanced_beat = {**b, **audio_feats}
            enhanced.append(enhanced_beat)

    # Save
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for b in enhanced:
            f.write(json.dumps(b) + "\n")

    print(f"\nSaved {len(enhanced)} enhanced beats to {OUT}")

    # Quick stats
    if enhanced:
        f0_stds = [b.get("f0_std", 0) for b in enhanced if "f0_std" in b]
        print(f"f0_std: mean={np.mean(f0_stds):.1f}, std={np.std(f0_stds):.1f}")


if __name__ == "__main__":
    main()
