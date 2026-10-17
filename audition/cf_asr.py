"""Cloudflare Workers AI whisper — default ASR for the voice engine.

Binary upload to @cf/openai/whisper (cheap tier). Chunks >90s files.
Returns scribe-format words [{text,start,end}]. Falls back to local
faster-whisper tiny on CF failure. Token: CLOUDFLARE_API_TOKEN in .env.

Usage: python3 cf_asr.py <audio> [--out scribe.json]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent


def _creds():
    tok = acc = None
    envf = HERE / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                tok = line.split("=", 1)[1]
            elif line.startswith("CF_AI_ACCOUNT_ID="):
                acc = line.split("=", 1)[1]
    return tok, acc


def _parse_vtt(vtt: str, offset: float = 0.0) -> list[dict]:
    """WEBVTT -> [{start,end,text}] phrases (tolerates short timestamps)."""
    import re

    def t2f(t: str) -> float:
        t = t.strip()
        if not t:
            return 0.0
        if ":" in t:
            parts = t.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(t)

    out = []
    blocks = re.split(r"\n\n+", vtt)
    for b in blocks:
        lines = b.strip().splitlines()
        if not lines or "-->" not in lines[0]:
            continue
        try:
            a, e = lines[0].split("-->")
            s, ee = t2f(a) + offset, t2f(e) + offset
        except Exception:
            continue
        text = " ".join(l.strip() for l in lines[1:] if l.strip() and not l.startswith("WEBVTT"))
        if text:
            out.append({"start": round(s, 2), "end": round(ee, 2), "text": text})
    return out


_LAUGH_RE = None


def is_laugh_phrase(text: str) -> bool:
    """CF whisper writes audience laughter as 'ha ha ha...' / 'ah ha' runs."""
    global _LAUGH_RE
    if _LAUGH_RE is None:
        import re
        _LAUGH_RE = re.compile(r"^(?:ha|ah|ha ha|lmao|haha|heh)+[.!]?$", re.I)
    toks = [t for t in text.replace(",", " ").split() if t.strip(".!?")]
    return bool(toks) and all(_LAUGH_RE.match(t) or _LAUGH_RE.match(t.lower())
                              for t in toks) and len(toks) >= 2


def phrases_to_words(phrases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split speech phrases to word spans; extract laugh events + punch candi-
    dates (last speech word before a laugh run) — audio-first beat labels."""
    import re
    words, laughs, punches = [], [], []
    prev_word = None
    for p in phrases:
        if is_laugh_phrase(p["text"]):
            laughs.append({"start": p["start"], "end": p["end"],
                           "intensity": min(1.0, len(p["text"].split()) / 8),
                           "source": "cf-whisper-transcript"})
            if prev_word:
                punches.append({"word": prev_word["text"], "at": prev_word["end"],
                                "laugh_start": p["start"],
                                "gap_to_laugh": round(p["start"] - prev_word["end"], 2)})
            continue
        toks = p["text"].split()
        if not toks:
            continue
        step = (p["end"] - p["start"]) / len(toks)
        for i, t in enumerate(toks):
            w = {"text": t.strip(".,!?;:"), "start": round(p["start"] + i * step, 2),
                 "end": round(p["start"] + (i + 1) * step, 2), "type": "word",
                 "speaker_id": "speaker_0"}
            words.append(w)
            prev_word = w
    return words, laughs, punches


def _run_whisper(audio_bytes: bytes, ext: str = "wav") -> dict:
    tok, acc = _creds()
    if not tok or not acc:
        raise RuntimeError("CLOUDFLARE_API_TOKEN / CF_AI_ACCOUNT_ID missing")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/openai/whisper",
        data=audio_bytes,
        headers={"Authorization": f"Bearer {tok}", "Content-Type": f"audio/{ext}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.load(r)
    result = res.get("result") or res
    if not isinstance(result, dict) or "text" not in result:
        raise RuntimeError(f"cf whisper bad response: {str(res)[:200]}")
    return result


def _chunk_pcm(path: Path, chunk_s: int = 90):
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True,
        timeout=30).stdout.strip() or 0)
    n = max(1, int(dur / chunk_s) + (1 if dur % chunk_s else 0))
    out = []
    for i in range(n):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            t = Path(tmp.name)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path),
             "-ss", str(i * chunk_s), "-t", str(chunk_s),
             "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(t)],
            check=True, capture_output=True, timeout=120)
        out.append((i * chunk_s, t))
    return dur, out


def transcribe(path: str | Path) -> dict:
    """CF whisper -> scribe-format dict. Auto-chunks. Fallback: local tiny."""
    path = Path(path)
    try:
        dur, chunks = _chunk_pcm(path)
        words, texts = [], []
        all_laughs, all_punches = [], []
        for offset, tmp in chunks:
            res = _run_whisper(tmp.read_bytes())
            texts.append(res.get("text") or "")
            vtt = res.get("vtt") or ""
            phrases = _parse_vtt(vtt, offset)
            if phrases:
                ws, laughs, punches = phrases_to_words(phrases)
                words.extend(ws)
                all_laughs.extend(laughs)
                all_punches.extend(punches)
            else:
                for w in res.get("words") or []:
                    if isinstance(w, dict):
                        t = (w.get("word") or w.get("text") or "").strip()
                        s = float(w.get("start") or 0) + offset
                        e = float(w.get("end") or 0) + offset
                    elif isinstance(w, (list, tuple)) and len(w) >= 3:
                        s, e, t = float(w[0]) + offset, float(w[1]) + offset, str(w[2]).strip()
                    else:
                        continue
                    if t:
                        words.append({"text": t, "start": round(s, 2),
                                      "end": round(e, 2), "type": "word",
                                      "speaker_id": "speaker_0"})
            tmp.unlink(missing_ok=True)
        speech_text = " ".join(w["text"] for w in words)
        return {"language_code": "eng", "text": speech_text, "words": words,
                "laugh_events": all_laughs, "punch_candidates": all_punches,
                "audio_duration_secs": dur,
                "asr": "cloudflare-whisper",
                "note": "laughter extracted from transcript 'ha ha' runs (StandUp4AI-style)"};
    except Exception as e:
        if os.environ.get("CF_ASR_NO_FALLBACK"):
            print(f"cf whisper failed ({str(e)[:120]}); no fallback (CF_ASR_NO_FALLBACK)",
                  flush=True)
            raise
        print(f"cf whisper failed ({str(e)[:120]}); local tiny fallback", flush=True)
        import array
        import numpy as np
        from faster_whisper import WhisperModel
        with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
                            "-ac", "1", "-ar", "16000", "-f", "s16le", tmp.name],
                           check=True, capture_output=True, timeout=180)
            raw = Path(tmp.name).read_bytes()
        a = array.array("h")
        a.frombytes(raw)
        audio = np.asarray(a, dtype="float32") / 32768.0
        m = WhisperModel("tiny", device="cpu", compute_type="int8")
        segs, info = m.transcribe(audio, language="en", beam_size=1,
                                  word_timestamps=True, vad_filter=False)
        words = []
        texts = []
        for s in segs:
            texts.append(s.text.strip())
            for w in (s.words or []):
                words.append({"text": w.word.strip(), "start": round(w.start, 2),
                              "end": round(w.end, 2), "type": "word",
                              "speaker_id": "speaker_0"})
        return {"language_code": "eng", "text": " ".join(texts), "words": words,
                "audio_duration_secs": info.duration, "asr": "local-faster-whisper-tiny"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--out")
    args = ap.parse_args()
    t0 = time.time()
    d = transcribe(args.audio)
    print(f"{d['asr']}: {len(d['words'])} words, {d['audio_duration_secs']:.1f}s, "
          f"{time.time()-t0:.1f}s")
    if args.out:
        Path(args.out).write_text(json.dumps(d, indent=1))
        print("->", args.out)
