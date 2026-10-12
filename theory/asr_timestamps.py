"""Word-timestamped ASR via free-quota qwen-audio models (sync multimodal API)."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AUDITION = Path(__file__).parent.parent / "audition"


def _key() -> str:
    for line in (AUDITION / ".env").read_text().splitlines():
        if line.startswith("DASHSCOPE_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("no key")


def to_wav16k(src: Path) -> Path:
    wav = Path("/tmp/opencode") / f"{src.stem}_16k.wav"
    if not wav.exists() or wav.stat().st_size < 1000:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(wav)],
            capture_output=True, timeout=60, check=True)
    return wav


def asr_sync(wav: Path, model: str = "qwen-audio-3.1-asr-flash") -> dict:
    key = _key()
    b64 = base64.b64encode(wav.read_bytes()).decode()
    body = {
        "model": model,
        "input": {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "input_audio",
                     "input_audio": {"data": b64, "format": "wav"}},
                ],
            }]
        },
        "parameters": {
            "format": "wav",
            "sample_rate": "16000",
            "language_hints": ["en"],
            "enable_timestamp": True,
        },
    }
    req = urllib.request.Request(
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "disable",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except Exception as e:
        raw = b""
        if hasattr(e, "read"):
            try:
                raw = e.read()
            except Exception:
                pass
        return {"error": str(e), "body": raw.decode(errors="replace")[:800]}


def flatten_words(resp: dict) -> list[dict]:
    """Best-effort extract of word timestamps from various response shapes."""
    words = []
    # try nested output.choices[0].message.content structures
    def walk(o):
        if isinstance(o, dict):
            if "words" in o and isinstance(o["words"], list):
                for w in o["words"]:
                    if isinstance(w, dict) and "text" in w:
                        words.append({
                            "text": w.get("text", "").strip(),
                            "t0": (w.get("begin_time") or w.get("start_time") or 0) / 1000.0,
                            "t1": (w.get("end_time") or w.get("stop_time") or 0) / 1000.0,
                        })
            if "sentences" in o and isinstance(o["sentences"], list):
                for s in o["sentences"]:
                    walk(s)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and o.startswith("{"):
            try:
                walk(json.loads(o))
            except Exception:
                pass
    walk(resp)
    # dedupe
    seen = set()
    out = []
    for w in words:
        k = (w["text"], w["t0"])
        if k in seen:
            continue
        seen.add(k)
        out.append(w)
    return out


def main():
    src = Path(sys.argv[1])
    model = sys.argv[2] if len(sys.argv) > 2 else "qwen-audio-3.1-asr-flash"
    wav = to_wav16k(src)
    print(f"ASR {wav.name} ({wav.stat().st_size//1024}KB) via {model} ...", flush=True)
    t0 = time.time()
    resp = asr_sync(wav, model)
    print(f"  {time.time()-t0:.1f}s")
    outp = Path("/tmp/opencode") / f"{src.stem}.asr.json"
    outp.write_text(json.dumps(resp, indent=2, ensure_ascii=False))
    if "error" in resp:
        print("ERROR", resp["error"])
        print(resp.get("body", "")[:400])
        return
    words = flatten_words(resp)
    print(f"  words: {len(words)}")
    for w in words[:15]:
        print(f"  {w['t0']:6.2f}-{w['t1']:6.2f}  {w['text']}")
    # save clean words
    wp = Path("/tmp/opencode") / f"{src.stem}.words.json"
    wp.write_text(json.dumps(words, indent=2))
    print("->", outp, wp)


if __name__ == "__main__":
    main()
