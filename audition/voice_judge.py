"""Judge rendered set audio against vibe target bands (the feedback loop).

Measures duration, median pitch, pitch variability (semitones), intensity
spread from a wav/mp3. Praat/parselmouth if installed; numpy autocorrelation
fallback otherwise (rough but enough to catch deadpan-vs-manic mistakes).

Compare target = vibe band of the character (character.json.vibe) or the
corpus-wide prosody band. Exit code 0 always — verdict is data, not gate
(POG/human still disposes).

Usage:
  python3 voice_judge.py ../freaks/kappa-kyle-cucumber-debt/set.wav --vibe deadpan
  python3 voice_judge.py --pack kappa-kyle-cucumber-debt
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
BANDS = REPO / "theory" / "vibe-bands.json"


def _decode_mono(path: Path, sr: int = 16000) -> tuple[list[float], int]:
    """Any audio -> mono float samples via ffmpeg s16le."""
    with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ac", "1",
             "-ar", str(sr), "-f", "s16le", tmp.name],
            capture_output=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"decode failed: {r.stderr.decode()[:200]}")
        raw = Path(tmp.name).read_bytes()
    import array
    a = array.array("h")
    a.frombytes(raw)
    return [x / 32768.0 for x in a], sr


def _pitch_track(samples: list[float], sr: int) -> list[float]:
    try:
        import numpy as np
    except ImportError:
        return _pitch_track_pure(samples, sr)
    import numpy as np
    x = np.asarray(samples, dtype="float64")
    frame, hop = int(0.04 * sr), int(0.01 * sr)
    if len(x) < frame:
        return []
    n_frames = 1 + (len(x) - frame) // hop
    win = np.hanning(frame)
    track = []
    fmin, fmax = 75.0, 400.0
    lag_min, lag_max = int(sr / fmax), int(sr / fmin)
    for i in range(n_frames):
        seg = x[i * hop:i * hop + frame] * win
        if np.sqrt(np.mean(seg ** 2)) < 0.01:
            continue
        ac = np.correlate(seg, seg, mode="full")[frame - 1:]
        ac[:lag_min] = 0
        if lag_max >= len(ac):
            continue
        lag = lag_min + int(np.argmax(ac[lag_min:lag_max]))
        if ac[lag] <= 0:
            continue
        track.append(sr / lag)
    return track


def _pitch_track_pure(samples: list[float], sr: int) -> list[float]:
    frame, hop = int(0.04 * sr), int(0.02 * sr)
    lag_min, lag_max = int(sr / 400), int(sr / 75)
    track = []
    for i in range(0, max(0, len(samples) - frame), hop):
        seg = samples[i:i + frame]
        rms = math.sqrt(sum(s * s for s in seg) / len(seg))
        if rms < 0.01:
            continue
        best_lag, best_e = 0, 0.0
        for lag in range(lag_min, min(lag_max, len(seg) - 1)):
            e = sum(seg[j] * seg[j + lag] for j in range(0, len(seg) - lag, 2))
            if e > best_e:
                best_e, best_lag = e, lag
        if best_lag:
            track.append(sr / best_lag)
    return track


def measure(path: Path) -> dict:
    samples, sr = _decode_mono(path)
    dur_ms = int(len(samples) / sr * 1000)
    track = _pitch_track(samples, sr)
    pitch = {"n_frames": len(track)}
    if track:
        mid = sorted(track)[len(track) // 2]
        mean = sum(track) / len(track)
        var_st = 12.0 * math.log2(max(track) / max(1e-6, min(track))) if max(track) > 0 else 0
        # population std in semitones around median
        stdev_st = (sum((12.0 * math.log2(max(1e-6, f) / max(1e-6, mid))) ** 2
                        for f in track) / len(track)) ** 0.5
        pitch.update({"median_hz": round(mid, 1), "mean_hz": round(mean, 1),
                      "range_semitones": round(var_st, 2),
                      "std_semitones": round(stdev_st, 2)})
    # intensity: frame RMS dB
    frame = int(0.02 * sr)
    rms_db = []
    for i in range(0, len(samples) - frame, frame):
        seg = samples[i:i + frame]
        rms = math.sqrt(sum(s * s for s in seg) / len(seg))
        if rms > 1e-5:
            rms_db.append(20 * math.log10(rms))
    intensity = {}
    if rms_db:
        rms_db.sort()
        intensity = {
            "median_db": round(rms_db[len(rms_db) // 2], 1),
            "std_db": round((sum((x - sum(rms_db) / len(rms_db)) ** 2
                                 for x in rms_db) / len(rms_db)) ** 0.5, 1),
            "p90_p10_db": round(rms_db[int(len(rms_db) * 0.9)] - rms_db[int(len(rms_db) * 0.1)], 1),
        }
    return {"duration_ms": dur_ms, "pitch": pitch, "intensity": intensity,
            "method": "parselmouth-missing;numpy-or-pure-autocorrelation"}


def judge(path: Path, vibe: str = "", claimed_ms: int = 0,
          performer: str = "") -> dict:
    m = measure(path)
    bands = {}
    if BANDS.exists():
        bands = json.loads(BANDS.read_text())
    target = (bands.get("vibes") or {}).get(vibe) if vibe else None
    perf = (bands.get("performers") or {}).get(performer) if performer else None
    corpus = (bands.get("corpus_prosody") or {})
    verdict = {"file": str(path), "vibe": vibe or "(none)",
               "performer": performer or "(none)",
               "measured": m, "target": target, "performer_target": perf,
               "corpus_pitch_var_st": corpus.get("pitch_var_st"),
               "checks": []}
    pv = m["pitch"].get("std_semitones")
    if claimed_ms and m["duration_ms"]:
        drift = m["duration_ms"] - claimed_ms
        verdict["checks"].append({
            "check": "duration", "drift_ms": drift,
            "ok": abs(drift) <= max(1500, claimed_ms * 0.15)})
    band_src = None
    if perf and perf.get("prosody", {}).get("pitch_var_st", {}).get("n"):
        band_src = ("performer", perf["prosody"]["pitch_var_st"])
    elif target and target.get("pitch_var_st", {}).get("n"):
        band_src = ("vibe", target["pitch_var_st"])
    elif corpus.get("pitch_var_st", {}).get("n"):
        band_src = ("corpus", corpus["pitch_var_st"])
    if pv is not None and band_src:
        kind, b = band_src
        lo = b["lo"]
        hi = max(b["hi"], lo + 0.5)
        verdict["checks"].append({
            "check": f"pitch_var_in_{kind}_band", "value": pv, "band": [lo, hi],
            "ok": lo <= pv <= hi})
    verdict["ok"] = all(c.get("ok") for c in verdict["checks"]) if verdict["checks"] else None
    return verdict


def _main() -> None:
    ap = argparse.ArgumentParser(description="judge rendered audio vs vibe bands")
    ap.add_argument("wav", nargs="?", default=None)
    ap.add_argument("--pack", default=None, help="slug: judges freaks/<slug>/set.wav "
                    "using pack vibe + claimed duration")
    ap.add_argument("--vibe", default=None, help="override vibe key (deadpan, manic, ...)")
    ap.add_argument("--performer", default=None,
                    help="calibration performer block (e.g. ari_matti)")
    args = ap.parse_args()
    vibe, claimed = args.vibe or "", 0
    if args.pack:
        pack = REPO / "freaks" / args.pack
        wav = pack / "set.wav"
        ch = json.loads((pack / "character.json").read_text())
        vibe = vibe or (ch.get("vibe") or "")
        dl = pack / "delivery.json"
        if dl.exists():
            claimed = int((json.loads(dl.read_text()).get("metadata") or {})
                          .get("total_duration_ms") or 0)
    elif args.wav:
        wav = Path(args.wav)
    else:
        ap.error("give a wav path or --pack slug")
    v = judge(wav, vibe=vibe, claimed_ms=claimed, performer=args.performer or "")
    print(json.dumps(v, indent=2))


if __name__ == "__main__":
    _main()
