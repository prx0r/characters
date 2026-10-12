"""Full granular pipeline for free-quota stack:
  MediaPipe body/face dials + word-timed ASR + character-model theory
  → performance.v1 with speech-aligned beats + anger correlation.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
AUDITION = HERE.parent / "audition"
OUT = HERE / "killtony-minutes"


def _key() -> str:
    for line in (AUDITION / ".env").read_text().splitlines():
        if line.startswith("DASHSCOPE_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("no key")


def upload_temp(src: Path) -> str:
    """litterbox 24h public URL (Aliyun can resolve)."""
    import subprocess as sp
    r = sp.run(
        ["curl", "-s", "-F", "reqtype=fileupload", "-F", "time=24h",
         "-F", f"fileToUpload=@{str(src)}", "https://litterbox.catbox.moe/resources/internals/api.php"],
        capture_output=True, text=True, timeout=120)
    url = (r.stdout or "").strip()
    if not url.startswith("http"):
        raise RuntimeError(f"upload failed out={r.stdout[:300]!r} err={r.stderr[:300]!r}")
    return url


def asr_words(url: str, model: str = "qwen-audio-3.1-asr-flash") -> dict:
    body = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [
            {"type": "input_audio", "input_audio": {"data": url}}]}]},
        "parameters": {"format": "mp3", "sample_rate": "16000",
                       "language_hints": ["en"]},
    }
    req = urllib.request.Request(
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {_key()}",
                 "Content-Type": "application/json",
                 "X-DashScope-SSE": "disable"},
        method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def extract_words(resp: dict) -> list[dict]:
    words = []
    # shape: output.output.sentence.words (seen in live response)
    def find_words(o):
        if isinstance(o, dict):
            if "words" in o and isinstance(o["words"], list):
                for w in o["words"]:
                    if not isinstance(w, dict):
                        continue
                    t = (w.get("text") or "").strip()
                    if not t:
                        continue
                    words.append({
                        "text": t,
                        "t0": (w.get("begin_time") or 0) / 1000.0,
                        "t1": (w.get("end_time") or 0) / 1000.0,
                    })
            for v in o.values():
                find_words(v)
        elif isinstance(o, list):
            for v in o:
                find_words(v)
        elif isinstance(o, str) and o.lstrip().startswith("{"):
            try:
                find_words(json.loads(o))
            except Exception:
                pass
    find_words(resp)
    # dedupe consecutive identical
    out = []
    for w in words:
        if out and out[-1]["text"] == w["text"] and abs(out[-1]["t0"] - w["t0"]) < 0.01:
            continue
        out.append(w)
    return out


def punchline_times(words: list[dict], energy_peaks: list[float]) -> list[float]:
    """Heuristic: long pause after dense speech → likely punchline hold zone."""
    if not words:
        return []
    hits = []
    for i in range(1, len(words)):
        gap = words[i]["t0"] - words[i - 1]["t1"]
        if gap > 0.6:
            hits.append(round(words[i - 1]["t1"], 2))
    return hits


def attach_speech_to_granular(granular: dict, words: list[dict]) -> dict:
    """Correlate each numeric window with concurrent words + mouth activity."""
    ws = granular.get("numeric_windows") or []
    aligned = []
    for w in ws:
        t0, t1 = w["t0"], w["t1"]
        concurrent = [x for x in words if x["t0"] < t1 and x["t1"] > t0]
        text = " ".join(x["text"] for x in concurrent)[:80]
        aligned.append({
            **w,
            "speech_text": text,
            "n_words": len(concurrent),
            "speaking": bool(concurrent),
            "mouth_vs_speech": round((w.get("mouth_open_max") or 0), 3),
        })
    # anger windows = high mouth_wide + speaking + high brow_range OR high lean
    for a in aligned:
        energy = (a.get("mouth_wide_max") or 0) + (a.get("brow_range") or 0) + (a.get("lean_x_range") or 0)
        a["energy"] = round(energy, 3)
        a["anger_proxy"] = bool(
            a["speaking"] and energy > 0.85 and
            ((a.get("mouth_wide_max") or 0) > 0.28 or (a.get("lean_x_range") or 0) > 0.12)
        )
    granular["speech_aligned_windows"] = aligned
    granular["asr_words"] = words
    granular["asr_word_count"] = len(words)
    granular["punchline_gaps_s"] = punchline_times(words, [])
    return granular


def performance_v1_from_aligned(granular: dict) -> dict:
    events = []
    for w in granular.get("speech_aligned_windows") or []:
        t = w["t0"]
        if w.get("speaking"):
            events.append({"t": t, "kind": "speak_start",
                           "value": {"text": w.get("speech_text", "")[:60],
                                     "energy": w.get("energy"),
                                     "anger_proxy": w.get("anger_proxy")}})
        # expression
        brow, mouth = w.get("brow_mean") or 0, w.get("mouth_wide_max") or 0
        if brow > 0.45 and mouth > 0.4:
            expr = "surprised"
        elif w.get("anger_proxy"):
            expr = "annoyed"
        elif mouth < 0.2 and brow < 0.25:
            expr = "deadpan"
        else:
            expr = "neutral"
        events.append({"t": t, "kind": "expression", "value": expr,
                       "energy": w.get("energy")})
        if (w.get("lean_x_range") or 0) > 0.16:
            events.append({"t": t, "kind": "gesture", "value": "lean in"})
        elif (w.get("arm_open_mean") or 0) > 0.62:
            events.append({"t": t, "kind": "gesture", "value": "small gesture"})
    # punchline holds
    for pt in granular.get("punchline_gaps_s") or []:
        events.append({"t": pt, "kind": "hold", "ms": 1200})
    events.sort(key=lambda e: (e["t"], e.get("kind") or ""))
    return {
        "version": "performance.v1",
        "source": granular.get("id"),
        "duration_s": granular.get("mediapipe", {}).get("duration_s"),
        "method": "mediapipe+asr_aligned_v1",
        "n_asr_words": granular.get("asr_word_count"),
        "events": events,
        "n_events": len(events),
    }


def main():
    video = Path(sys.argv[1])
    stem = sys.argv[2] if len(sys.argv) > 2 else video.stem
    gran_path = OUT / f"{stem}.granular.json"
    if not gran_path.exists():
        print("run extract_performance.py first for", stem)
        sys.exit(1)
    granular = json.loads(gran_path.read_text())

    # make small mp3 for upload
    mp3 = Path("/tmp/opencode") / f"{stem}_asr.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "libmp3lame", "-b:a", "32k", str(mp3)],
        capture_output=True, timeout=90, check=True)
    print(f"upload {mp3.name} ({mp3.stat().st_size//1024}KB) ...", flush=True)
    url = upload_temp(mp3)
    print(" url", url)
    print("ASR ...", flush=True)
    t0 = time.time()
    resp = asr_words(url)
    print(f" {time.time()-t0:.1f}s")
    words = extract_words(resp)
    print(f" words: {len(words)}")
    for w in words[:8]:
        print(f"  {w['t0']:5.2f} {w['text']}")

    granular = attach_speech_to_granular(granular, words)
    gran_path.write_text(json.dumps(granular, indent=2))

    perf = performance_v1_from_aligned(granular)
    perf_path = OUT / f"{stem}.performance.v1.json"
    perf_path.write_text(json.dumps(perf, indent=2))
    print(f"wrote {perf_path.name}: {perf['n_events']} events")

    # anger report with speech context
    ang = [w for w in granular["speech_aligned_windows"] if w.get("anger_proxy")]
    report = OUT / f"{stem}.anger_speech_report.md"
    lines = [
        f"# Anger×speech report — {stem}",
        f"- ASR words: {len(words)}",
        f"- anger_proxy windows: {len(ang)} / {len(granular['speech_aligned_windows'])}",
        "",
        "## Anger-proxy windows (speech + high body energy)",
        "",
    ]
    for w in ang:
        lines.append(
            f"- t={w['t0']}s energy={w.get('energy')} "
            f"mouthW={w.get('mouth_wide_max')} leanR={w.get('lean_x_range')} "
            f"brow={w.get('brow_mean')}  «{w.get('speech_text','')[:70]}»")
    lines += ["", "## Full transcript (word timings)", ""]
    for w in words:
        lines.append(f"  {w['t0']:6.2f}-{w['t1']:6.2f}  {w['text']}")
    report.write_text("\n".join(lines))
    print(f"wrote {report.name}")


if __name__ == "__main__":
    main()
