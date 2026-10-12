"""Acoustic vocal analysis — Ari's actual voice fingerprint.

librosa (local, free, CPU) extracts:
  - F0 pitch track (median, range, contour)
  - RMS energy envelope
  - Spectral centroid (brightness)
  - MFCCs (vocal tract shape)
  - Speech rate (syllable nuclei / sec)
  - Pause pattern (silence detection)
  - Jitter/shimmer (voice quality — roughness)
  - Formant estimates (F1-F3 via MFCC proxy)

Pairs with MediaPipe body dials and Gemini semantic tags to give a
complete numeric picture of the performance.

Usage:
  python theory/acoustic.py <audio.wav> --id <stem>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "killtony-minutes"


def _to_wav16k(src: Path) -> Path:
    import tempfile
    wav = Path(tempfile.mkdtemp(prefix="acoustic_")) / "a.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, timeout=120, check=True)
    return wav


def analyze(wav_path: Path) -> dict:
    """Full acoustic analysis of a speech recording."""
    import librosa

    y, sr = librosa.load(str(wav_path), sr=16000, mono=True)
    duration = len(y) / sr

    # ── F0 (pitch) ──
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=60, fmax=400, sr=sr, frame_length=1024, hop_length=160)
    f0_clean = f0[~np.isnan(f0)]
    f0_track = [{"t": round(i * 160 / sr, 3), "hz": round(float(v), 1)}
                for i, v in enumerate(f0) if not np.isnan(v)]

    # ── RMS energy ──
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=160)[0]
    rms_track = [{"t": round(i * 160 / sr, 3), "db": round(float(librosa.amplitude_to_db(r)), 1)}
                 for i, r in enumerate(rms)]

    # ── Spectral centroid (brightness) ──
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=160)[0]
    centroid_track = [{"t": round(i * 160 / sr, 3), "hz": round(float(c), 1)}
                      for i, c in enumerate(centroid)]

    # ── MFCCs (vocal tract shape — 13 coefficients) ──
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=160)
    mfcc_mean = [round(float(m), 2) for m in mfccs.mean(axis=1)]
    mfcc_std = [round(float(m), 2) for m in mfccs.std(axis=1)]

    # ── Speech rate via syllable nuclei (energy peaks) ──
    # approximate: count energy peaks above threshold
    rms_db = librosa.amplitude_to_db(rms)
    threshold = np.percentile(rms_db[rms_db > -60], 70) if np.any(rms_db > -60) else -30
    peaks = librosa.util.peak_pick(
        rms_db, pre_max=5, post_max=5, pre_avg=5, post_avg=5,
        delta=3, wait=int(0.15 * sr / 160))
    n_syllables = len(peaks)
    speech_rate = n_syllables / duration if duration > 0 else 0

    # ── Pause / silence detection ──
    # top_db=30 relative to max → silence below that
    intervals = librosa.effects.split(y, top_db=30)
    pauses = []
    prev_end = 0
    for start, end in intervals:
        if start / sr - prev_end > 0.15:  # >150ms silence = pause
            pauses.append({
                "t0": round(prev_end, 2),
                "t1": round(start / sr, 2),
                "dur_ms": round((start / sr - prev_end) * 1000),
            })
        prev_end = end / sr
    speech_ratio = sum(e - s for s, e in intervals) / (duration * sr) if duration > 0 else 0

    # ── Jitter / shimmer (voice quality — needs voiced segments) ──
    jitter = shimmer = None
    if len(f0_clean) > 10:
        # local jitter: mean |F0[i+1]-F0[i]| / F0[i]
        f0_diffs = np.abs(np.diff(f0_clean))
        jitter = round(float(np.mean(f0_diffs / f0_clean[:-1]) * 100), 3)  # %
        # shimmer: needs amplitude per period — approximate from RMS on voiced
        voiced_rms = rms[voiced_flag[:len(rms)]] if len(voiced_flag) >= len(rms) else np.array([])
        if len(voiced_rms) > 10:
            shimmer = round(float(np.mean(np.abs(np.diff(voiced_rms)) / voiced_rms[:-1]) * 100), 3)

    # ── Formant proxy via LPC ──
    formants = []
    try:
        from scipy.signal import lfilter
        # LPC order ~2 + sr/1000 for 16kHz
        order = 2 + 16000 // 1000
        # analyze a voiced mid-clip frame
        mid = len(y) // 2
        frame = y[mid:mid + 1024]
        if len(frame) == 1024:
            frame = frame * np.hamming(1024)
            # autocorrelation method
            corr = np.correlate(frame, frame, mode="full")
            corr = corr[len(corr) // 2:]
            # Durbin's method for LPC
            a = np.zeros(order + 1)
            a[0] = 1.0
            e = corr[0]
            for i in range(1, order + 1):
                lam = sum(a[j] * corr[i - j] for j in range(i))
                k = -lam / e if e > 0 else 0
                a_new = a.copy()
                for j in range(1, i):
                    a_new[j] = a[j] + k * a[i - j]
                a_new[i] = k
                a = a_new
                e *= (1 - k * k)
                if e <= 0:
                    break
            # roots of LPC polynomial → formant frequencies
            roots = np.roots(a)
            roots = roots[np.imag(roots) > 0]
            angles = np.arctan2(np.imag(roots), np.real(roots))
            freqs = sorted(angles * (sr / (2 * np.pi)))
            formants = [round(float(f), 0) for f in freqs[:3] if 200 < f < 4000]
    except Exception:
        pass

    # ── Summary stats ──
    f0_stats = {}
    if len(f0_clean) > 0:
        f0_stats = {
            "median_hz": round(float(np.median(f0_clean)), 1),
            "mean_hz": round(float(np.mean(f0_clean)), 1),
            "min_hz": round(float(np.min(f0_clean)), 1),
            "max_hz": round(float(np.max(f0_clean)), 1),
            "range_ratio": round(float(np.max(f0_clean) / max(np.min(f0_clean), 1)), 2),
            "std_hz": round(float(np.std(f0_clean)), 1),
            "voiced_fraction": round(float(np.mean(voiced_flag)), 3),
        }

    rms_stats = {
        "mean_db": round(float(np.mean(librosa.amplitude_to_db(rms[rms > 1e-6]))), 1) if np.any(rms > 1e-6) else None,
        "max_db": round(float(np.max(librosa.amplitude_to_db(rms))), 1),
        "min_db": round(float(np.min(librosa.amplitude_to_db(rms[rms > 1e-6]))), 1) if np.any(rms > 1e-6) else None,
        "dynamic_range_db": round(float(np.ptp(librosa.amplitude_to_db(rms))), 1),
    }

    return {
        "duration_s": round(duration, 2),
        "sample_rate": sr,
        "f0": f0_stats,
        "energy": rms_stats,
        "spectral": {
            "centroid_mean_hz": round(float(np.mean(centroid)), 1),
            "centroid_std_hz": round(float(np.std(centroid)), 1),
        },
        "speech": {
            "syllable_nuclei": n_syllables,
            "rate_per_sec": round(speech_ratio and speech_rate, 2),
            "speech_ratio": round(float(speech_ratio), 3),
            "n_pauses": len(pauses),
            "pauses": pauses[:20],  # first 20
            "avg_pause_ms": round(float(np.mean([p["dur_ms"] for p in pauses])), 0) if pauses else 0,
        },
        "voice_quality": {
            "jitter_pct": jitter,
            "shimmer_pct": shimmer,
        },
        "formants_hz": formants,
        "mfcc_mean": mfcc_mean,
        "mfcc_std": mfcc_std,
        # downsampled tracks (every 5th point to keep file small)
        "tracks": {
            "f0": f0_track[::5],
            "rms": rms_track[::5],
            "centroid": centroid_track[::5],
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--id", required=True)
    args = ap.parse_args()

    wav = _to_wav16k(args.audio)
    print(f"analyzing {wav.name} ...", flush=True)
    result = analyze(wav)
    print(f"  duration: {result['duration_s']}s")
    print(f"  F0 median: {result['f0'].get('median_hz')}Hz "
          f"(range {result['f0'].get('min_hz')}-{result['f0'].get('max_hz')})")
    print(f"  energy: {result['energy'].get('mean_db')}dB mean, "
          f"{result['energy'].get('dynamic_range_db')}dB dynamic range")
    print(f"  speech rate: {result['speech'].get('rate_per_sec')}/s, "
          f"{result['speech'].get('n_pauses')} pauses")
    print(f"  jitter: {result['voice_quality'].get('jitter_pct')}%")
    print(f"  formants: {result['formants_hz']}")

    OUT.mkdir(exist_ok=True)
    out = OUT / f"{args.id}.acoustic.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
