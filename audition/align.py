"""Word/phoneme alignment — offline, free, no keys (Vosk).

Replaces proportional beat-scaling as the timing source for mouth cues.
Produces visemes.json: [{t, shape, word}] with shapes from the rig's
mouth_shapes. Falls back gracefully (missing model/audio -> None).
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

VOWEL_SHAPE = {"a": "AI", "e": "E", "i": "AI", "o": "O", "u": "U", "y": "E"}


def _vowel_shape(word: str) -> str:
    w = word.lower()
    if w.startswith(("f", "v")):
        return "FV"
    if w.startswith(("m", "b", "p")):
        return "MBP"
    if w.startswith("l"):
        return "L"
    for ch in w:
        if ch in VOWEL_SHAPE:
            return VOWEL_SHAPE[ch]
    return "rest"


def _to_wav16k(src: Path, dst: Path) -> None:
    r = subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
                        "-f", "wav", str(dst)], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg convert failed")


def align_words(audio: Path, workdir: Path | None = None) -> list[dict] | None:
    """Vosk word timestamps. Returns [{word,start_ms,end_ms}] or None."""
    try:
        from vosk import KaldiRecognizer, Model
    except Exception:
        return None
    try:
        import tempfile
        work = Path(workdir or tempfile.mkdtemp(prefix="align_"))
        work.mkdir(parents=True, exist_ok=True)
        wav = work / "a.wav"
        _to_wav16k(audio, wav)
        model = Model(lang="en-us")
        rec = KaldiRecognizer(model, 16000)
        rec.SetWords(True)
        words: list[dict] = []
        with wave.open(str(wav), "rb") as wf:
            while True:
                data = wf.readframes(8000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    words += json.loads(rec.Result()).get("result", [])
        words += json.loads(rec.FinalResult()).get("result", [])
        return [{"word": w["word"], "start_ms": int(w["start"] * 1000),
                 "end_ms": int(w["end"] * 1000)} for w in words]
    except Exception:
        return None


def visemes(words: list[dict]) -> list[dict]:
    out = []
    for w in words:
        out.append({"t": w["start_ms"], "shape": _vowel_shape(w["word"]), "word": w["word"]})
        out.append({"t": w["end_ms"], "shape": "rest", "word": ""})
    return out
