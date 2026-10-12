"""Phoneme-level lip-sync via OpenFaceFX → Ralph mouth shapes.

OpenFaceFX (pip install openfacefx, numpy-only) does:
  text + WAV → phoneme timestamps → Oculus 15 visemes → coarticulated curves

We map Oculus visemes → Ralph's 10 mouth shapes:
  closed, rest, AI, E, O, U, FV, L, MBP, open

Output format matches stage.py `_load_visemes`:
  audio/{aud_id}.visemes.json = [{"t": ms, "shape": str, "word": str}, ...]

Usage:
  python theory/lipsync.py <audio.mp3|wav> <transcript.txt> --aud-id <id>
  python theory/lipsync.py --from-asr <asr_words.json> --audio <wav> --aud-id <id>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
AUDITION = HERE.parent / "audition"
VIS_DIR = AUDITION / "audio"

# Oculus/MPEG-4 15 visemes → Ralph mouth shapes (rigs/ralph.json)
VISEME_TO_RALPH = {
    "sil": "closed",
    "PP": "MBP",      # P, B, M — lips pressed
    "FF": "FV",       # F, V — lower lip to teeth
    "TH": "E",        # TH — tongue between teeth (approximate)
    "DD": "E",        # D, T, N, L — tongue to palate
    "kk": "O",        # K, G — back of tongue (approximate)
    "CH": "O",        # CH, SH, J — pursed lips
    "SS": "E",        # S, Z — teeth close
    "nn": "E",        # N, NG — slightly open
    "RR": "U",        # R — slightly rounded
    "aa": "AI",       # AA, AH — wide open
    "E": "E",         # EH, AE — open slight smile
    "I": "AI",        # IH, IY — small opening (AI covers I)
    "O": "O",         # OH, AO — rounded medium
    "U": "U",         # UW, OW — small rounded
}


def _to_wav16k(src: Path) -> Path:
    wav = Path(tempfile.mkdtemp(prefix="lipsync_")) / "a.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(wav)],
        capture_output=True, timeout=120, check=True)
    return wav


def _wav_duration_s(wav: Path) -> float:
    import wave
    with wave.open(str(wav), "rb") as w:
        return w.getnframes() / w.getframerate()


def naive_track(text: str, wav: Path) -> dict:
    """OpenFaceFX naive: text + WAV → FaceTrack with phoneme-level viseme curves."""
    from openfacefx import generate_naive
    import wave as _wave
    with _wave.open(str(wav), "rb") as w:
        dur = w.getnframes() / w.getframerate()
    track = generate_naive(text, duration=dur, wav=str(wav))
    # convert FaceTrack to plain dict
    channels = []
    for ch in track.channels:
        keys = [[kf.time, kf.value] for kf in ch.keys]
        channels.append({"name": ch.name, "keys": keys})
    return {"channels": channels, "duration": track.duration, "fps": track.fps}


def track_to_ralph(track: dict, words: list[dict] | None = None) -> list[dict]:
    """Convert OpenFaceFX track → stage.py visemes format [{t, shape, word}].

    OpenFaceFX track: {channels: [{name, keys: [[time_s, weight], ...]}], ...}
    We pick the dominant viseme per keyframe and map to Ralph shapes.
    If words (ASR timestamps) provided, attach the nearest word.
    """
    channels = track.get("channels") or []
    if not channels:
        return []

    # Build time→viseme list by sampling all channel keys
    # For each timestamp that appears, find the channel with max weight
    events: list[tuple[float, str, float]] = []  # (t_s, viseme, weight)
    for ch in channels:
        name = ch.get("name", "sil")
        for key in ch.get("keys") or []:
            t, w = key[0], key[1]
            if w > 0.05:  # ignore near-zero
                events.append((float(t), name, float(w)))

    events.sort(key=lambda x: x[0])

    # Deduplicate: for each ~30ms bin, take the highest-weight viseme
    out: list[dict] = []
    bin_s = 0.03
    last_bin = -1
    last_shape = None
    for t, vis, w in events:
        b = int(t / bin_s)
        if b == last_bin:
            continue
        last_bin = b
        shape = VISEME_TO_RALPH.get(vis, "rest")
        if shape == last_shape:
            continue  # skip redundant
        last_shape = shape
        # find nearest word
        word = ""
        if words:
            t_ms = t * 1000
            for wd in words:
                if wd.get("start_ms", 0) <= t_ms <= wd.get("end_ms", 0):
                    word = wd.get("word", "")
                    break
        out.append({"t": int(t * 1000), "shape": shape, "word": word})

    return out


def load_asr_words(path: Path) -> list[dict]:
    """Load ASR word timestamps from align_speech_body / granular.json format."""
    data = json.loads(path.read_text())
    raw = data if isinstance(data, list) else data.get("asr_words", data.get("words", []))
    words = []
    for w in raw:
        words.append({
            "word": w.get("text", w.get("word", "")),
            "start_ms": int(float(w.get("t0", w.get("start_ms", 0))) * 1000),
            "end_ms": int(float(w.get("t1", w.get("end_ms", 0))) * 1000),
        })
    return words


def generate(audio: Path, transcript: str, aud_id: str,
             words: list[dict] | None = None) -> list[dict]:
    """Full pipeline: audio + transcript → Ralph visemes JSON."""
    wav = _to_wav16k(audio)
    print(f"  wav {wav.name} {_wav_duration_s(wav):.1f}s", flush=True)
    print(f"  transcript {len(transcript)} chars", flush=True)
    track = naive_track(transcript, wav)
    n_keys = sum(len(ch.get("keys") or []) for ch in track.get("channels") or [])
    print(f"  openfacefx track: {len(track.get('channels') or [])} channels, {n_keys} keys", flush=True)
    visemes = track_to_ralph(track, words)
    print(f"  ralph visemes: {len(visemes)} events", flush=True)
    # save where stage.py looks
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    out = VIS_DIR / f"{aud_id}.visemes.json"
    out.write_text(json.dumps(visemes, indent=2))
    print(f"  wrote {out}", flush=True)
    return visemes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path, help="audio file (mp3/wav)")
    ap.add_argument("--transcript", type=str, help="plain text transcript")
    ap.add_argument("--transcript-file", type=Path, help="file containing transcript")
    ap.add_argument("--asr-words", type=Path, help="ASR words JSON from align_speech_body")
    ap.add_argument("--aud-id", required=True, help="audition id for visemes.json")
    args = ap.parse_args()

    transcript = args.transcript or ""
    if args.transcript_file:
        transcript = args.transcript_file.read_text().strip()
    if not transcript:
        print("need --transcript or --transcript-file")
        sys.exit(1)

    words = load_asr_words(args.asr_words) if args.asr_words else None
    if words:
        print(f"  {len(words)} ASR words loaded", flush=True)

    visemes = generate(args.audio, transcript, args.aud_id, words)
    # summary
    shapes: dict[str, int] = {}
    for v in visemes:
        shapes[v["shape"]] = shapes.get(v["shape"], 0) + 1
    print(f"  shape distribution: {shapes}")


if __name__ == "__main__":
    main()
