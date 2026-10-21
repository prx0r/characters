"""Bark 3.0 local ASR via sherpa-onnx (0.6B int8, CC-BY-4.0).

OPT-IN alternative to cf_asr for the verify loop: `VERIFY_ASR=bark`.
Weights: hf://velddev/Underdog-Bark-3.0-sherpa-onnx (int8, ~685MB unpacked).
Model dir: $BARK_MODEL_DIR (default ~/models/bark3-onnx), threads: $BARK_THREADS.
Prepends 0.25s of silence, as the model card's evaluation did.

Usage: python3 bark_asr.py <audio>
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path

def _model_dir() -> Path:
    cands = [os.getenv("BARK_MODEL_DIR", ""), str(Path.home() / "models" / "bark3-onnx"),
             "/home/box/models/bark3-onnx"]
    for c in cands:
        if c and (Path(c) / "encoder.int8.onnx").exists():
            return Path(c)
    return Path(cands[0] or cands[1])


MODEL_DIR = _model_dir()

_rec = None


def _recognizer():
    global _rec
    if _rec is None:
        import sherpa_onnx
        d = MODEL_DIR
        _rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.int8.onnx"),
            joiner=str(d / "joiner.int8.onnx"),
            tokens=str(d / "tokens.txt"),
            model_type="nemo_transducer",
            num_threads=int(os.getenv("BARK_THREADS", "1")),
        )
    return _rec


def transcribe(path: str | Path) -> dict:
    """16k mono PCM -> text. No word timings; Bark emits segment text only."""
    import numpy as np
    path = Path(path)
    t0 = time.time()
    with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                        "-ac", "1", "-ar", "16000", "-f", "s16le", tmp.name],
                       capture_output=True, timeout=180, check=True)
        raw = Path(tmp.name).read_bytes()
    audio = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    audio = np.concatenate([np.zeros(4000, dtype="float32"), audio])
    rec = _recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(16000, audio)
    rec.decode_stream(stream)
    text = stream.result.text.replace("<unk>", "").strip()
    return {"language_code": "eng", "text": text, "words": [],
            "audio_duration_secs": round(len(audio) / 16000, 2),
            "asr": "bark-3.0-onnx-int8",
            "elapsed_secs": round(time.time() - t0, 2)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    args = ap.parse_args()
    d = transcribe(args.audio)
    print(f"{d['asr']}: {d['audio_duration_secs']:.1f}s audio, "
          f"{d['elapsed_secs']:.1f}s wall\n{d['text']}")
