"""Verify loop: transcribe renders, diff against intended words, auto-fix.

ASR: faster-whisper tiny/cpu ($0 local; CF Workers AI needs an API token,
R2 keys can't infer). Per segment: transcribe -> normalize -> word diff ->
if misses, try fixes (slower speed, emphasis on missed words) -> keep better.
Updates profile with winning per-segment adjustments.

Usage: python3 verify_set.py --profile profiles/kt704_standup.json --voice spongebob
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

HERE = Path(__file__).parent
LAB = HERE / "voicelab" / "ari_set"
PROF = HERE / "voicelab" / "profiles"

_model = None


def asr(audio_path: Path) -> str:
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("tiny", device="cpu", compute_type="int8")
    # decode ourselves — system pyav is incompatible with fw's decode_audio
    import array
    import subprocess
    import tempfile
    import numpy as np
    with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(audio_path),
                        "-ac", "1", "-ar", "16000", "-f", "s16le", tmp.name],
                       capture_output=True, timeout=120, check=True)
        raw = Path(tmp.name).read_bytes()
    a = array.array("h")
    a.frombytes(raw)
    audio = np.asarray(a, dtype="float32") / 32768.0
    segs, _ = _model.transcribe(audio, language="en", beam_size=1, vad_filter=False)
    return " ".join(s.text.strip() for s in segs)


def norm(s: str) -> list[str]:
    s = s.lower()
    s = re.sub(r"[^\w\s']|[\[\]]", " ", s)
    s = re.sub(r"\b(um|uh|ah|mm)\b", " ", s)
    return [w for w in s.split() if w and not w.startswith("http")]


def diff(intended: str, heard: str) -> dict:
    a, b = norm(intended), norm(heard)
    ai = set(a)
    missing = [w for w in b if w not in ai and w not in ("",)]
    # rough alignment: words in intended not present in heard
    bi = set(b)
    unsaid = [w for w in a if w not in bi]
    match = 1.0 - (len(unsaid) + len(missing)) / max(len(a) + len(b), 1)
    return {"match": round(max(0.0, match), 3), "unsaid": unsaid,
            "hallucinated": missing, "heard": heard[:200]}


def render_seg(name, text, temp, speed, vol, cue, voice):
    import fish_tts
    t = f"{cue} {text}".strip() if cue else text
    r = fish_tts.synthesize_fish(f"vf-{name}", t, voice=voice, direction=False,
                                 temperature=temp,
                                 prosody={"speed": round(speed, 2), "volume": vol})
    return Path(r["path"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="kt704_standup.json")
    ap.add_argument("--voice", default="spongebob")
    ap.add_argument("--fix-rounds", type=int, default=1)
    args = ap.parse_args()

    VOICES = {
        "spongebob": "0051da373e0a4ac282399909d1d31b69",
        "kid_darwin": "3a561684e5fa46eb9528e8e6ff9000c9",
        "roast": "4805c450f3e84faaa16f2cf9690fbd90",
        "ari_clone": "dbeb1d68566245e2b857617b830e8031",
    }
    voice = VOICES[args.voice]
    prof = json.loads((PROF / args.profile).read_text())
    report = {"voice": args.voice, "segments": []}

    for s in prof["segments"]:
        seg_i, text = s["seg"], s["text"]
        r = s["recipe"]
        best = None
        cand = dict(r)
        for fix in range(args.fix_rounds + 1):
            wav = render_seg(f"{args.voice}-{seg_i}-{fix}", text,
                             cand["temp"], cand["speed"], cand["vol"],
                             cand["cue"], voice)
            heard = asr(wav)
            d = diff(text, heard)
            row = {"seg": seg_i, "fix": fix, "recipe": dict(cand), **d,
                   "file": str(wav)}
            print(f"  {args.voice} seg{seg_i} fix{fix} match={d['match']:.2f} "
                  f"unsaid={d['unsaid'][:6]}", flush=True)
            if best is None or d["match"] > best["match"]:
                best = row
            # fix strategy: slow down + emphasize first unsaid word region
            if d["unsaid"] and fix < args.fix_rounds:
                cand = {**cand, "speed": round(max(0.5, cand["speed"] - 0.15), 2),
                        "temp": round(max(0.3, cand["temp"] - 0.05), 2)}
        report["segments"].append(best)

    avg = sum(s["match"] for s in report["segments"]) / len(report["segments"])
    report["avg_match"] = round(avg, 3)
    out = LAB / f"verify_{args.voice}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\n{args.voice}: avg_match={avg:.3f} -> {out}", flush=True)

    # adopt fixes into a voice-specific profile overlay
    overlay = {"profile": args.profile, "voice": args.voice,
               "segments": [{"seg": s["seg"], "recipe": s["recipe"],
                             "match": s["match"]} for s in report["segments"]]}
    ov = HERE / "voicelab" / "profiles" / f"kt704_standup_{args.voice}.json"
    ov.write_text(json.dumps(overlay, indent=2))
    print(f"overlay: {ov}", flush=True)


if __name__ == "__main__":
    main()
