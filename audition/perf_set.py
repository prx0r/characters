"""Multi-performer full-set RL: exact words x emotion arcs x per-set recipes.

Registry-driven: each performer has scribe+gemini sets and a clone voice.
Per segment: base-speed init, mutate (temp/speed/cue), keep best, stitch set.
Free API only ($0). Owners: ari/casey/pickles clones created via MCP (free).

Usage: python3 perf_set.py --performer casey_rocket [--rounds 1]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab" / "perf_sets"

CLONES = json.loads((Path(__file__).parent / "voicelab" / "clone_ids.json").read_text()) \
    if (Path(__file__).parent / "voicelab" / "clone_ids.json").exists() else {}

PERFORMERS = {
    "ari_matti": {
        "voice": CLONES.get("ari", ""),
        "sets": ["kt704_passport", "kt715_ep715", "kt715_walking",
                 "kt728_diversifying", "kt728_jamesbond"],
    },
    "casey_rocket": {
        "voice": CLONES.get("casey", ""),
        "sets": ["casey_rocket_1", "casey_rocket_2"],
    },
    "sir_winston_pickles": {
        "voice": CLONES.get("pickles", ""),
        "sets": ["sir_winston_pickles_1", "sir_winston_pickles_2"],
    },
    "louis_ck": {
        "voice": CLONES.get("louis", ""),
        "sets": ["louis_roadrage"],
    },
}

EMO = {
    "manic":         ("[excited]", 0.85, 6.4),
    "gleeful":       ("[delighted]", 0.80, 5.4),
    "deadpan":       ("", 0.45, 4.2),
    "sarcastic":     ("[sarcastic]", 0.65, 4.6),
    "mock_indignant": ("[frustrated]", 0.85, 6.0),
    "neutral":       ("[neutral]", 0.60, 5.0),
    "defiant":       ("[frustrated]", 0.80, 5.5),
    "embarrassed":   ("[embarrassed]", 0.70, 5.0),
}
CUE_ALTS = ["[excited]", "[delighted]", "[sarcastic]", "[frustrated]", "[neutral]", ""]


def gemini_path(setname: str) -> Path | None:
    d = REPO / "theory/killtony-minutes"
    cands = [d / f"{setname}_gemini.gemini.json"]
    if setname.startswith("kt704"):
        cands.append(d / "kt704_ari_passport_gemini.gemini.json")
    for c in cands:
        if c.exists():
            return c
    return None


def load_words(setname: str) -> list:
    p = REPO / "theory/scribe" / f"{setname}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("words") or []


def seg_text(words, t0, t1):
    import re
    ws = [w for w in words if t0 <= w["start"] < t1]
    if len(ws) < 6:
        return "", 0, 0.0
    text = " ".join(w["text"] for w in ws)
    text = re.sub(r"\[laughs?\]|\[laughing\]", "", text, flags=re.I)
    text = re.sub(r"\[censored\]", "crap", text, flags=re.I)
    text = " ".join(text.split())
    dur = ws[-1]["end"] - ws[0]["start"]
    return text, len(text.split()), dur


def render(name, text, temp, speed, vol, cue, voice):
    import fish_tts
    t = f"{cue} {text}".strip() if cue else text
    r = fish_tts.synthesize_fish(f"ps-{name}", t, voice=voice or None,
                                 direction=False, temperature=temp,
                                 prosody={"speed": round(speed, 2), "volume": vol})
    return Path(r["path"])


def measure(path, n_words):
    import voice_judge
    m = voice_judge.measure(path)
    dur = m["duration_ms"] / 1000
    return {"wpm": round(n_words / dur * 60, 1) if dur else 0,
            "var_st": m["pitch"].get("std_semitones") or 0,
            "duration_ms": m["duration_ms"]}


def run_set(perf: str, setname: str, voice: str, rounds: int) -> dict:
    words = load_words(setname)
    gpath = gemini_path(setname)
    if not words or not gpath:
        return {"set": setname, "error": "missing scribe or gemini"}
    segs = json.loads(gpath.read_text()).get("segments") or []
    LAB.mkdir(parents=True, exist_ok=True)
    parts, results = [], []
    for si, seg in enumerate(segs):
        emo = (seg.get("emotion") or "neutral").lower()
        cue0, temp0, var_tgt = EMO.get(emo, EMO["neutral"])
        text, n_words, real_dur = seg_text(words, seg["t0"], seg["t1"])
        if n_words < 6:
            continue
        target_wpm = n_words / real_dur * 60
        base = render(f"{setname}-b{si}", text, temp0, 1.0, 0.0, "", voice)
        bm = measure(base, n_words)
        speed0 = max(0.5, min(2.0, target_wpm / max(bm["wpm"], 1)))
        best = None
        cands = [{"temp": temp0, "speed": round(speed0, 2), "cue": cue0, "vol": 0.0}]
        for r in range(rounds + 1):
            nxt = []
            for c in cands:
                rid = hashlib.sha256(
                    f"{setname}{si}{c['temp']}{c['speed']}{c['cue']}".encode()).hexdigest()[:10]
                try:
                    p = render(f"{setname}-{si}-{rid}", text, c["temp"], c["speed"], c["vol"], c["cue"], voice)
                    m = measure(p, n_words)
                    sc = round(abs(m["wpm"] - target_wpm) / target_wpm * 100
                               + 1.2 * abs(m["var_st"] - var_tgt), 2)
                    row = {"seg": si, "emotion": emo, "rid": rid, **c, **m,
                           "score": sc, "target_wpm": round(target_wpm, 1),
                           "file": str(p)}
                    print(f"  {setname} s{si} r{r} {emo:13} sc={sc:6.2f} "
                          f"wpm={m['wpm']:6.1f}/{target_wpm:.0f}", flush=True)
                    if best is None or sc < best["score"]:
                        best = row
                    if r < rounds:
                        nxt.append({**c, "temp": round(max(0.3, min(0.95, c["temp"] + 0.12)), 2)})
                        nxt.append({**c, "speed": round(max(0.5, min(2.0, c["speed"] + 0.2)), 2)})
                        nxt.append({**c, "speed": round(max(0.5, min(2.0, c["speed"] - 0.2)), 2)})
                        alts = [a for a in CUE_ALTS if a != c["cue"]]
                        nxt.append({**c, "cue": alts[0]})
                except Exception as e:
                    print(f"  {setname} s{si} FAIL {str(e)[:70]}", flush=True)
            cands = nxt[:5]
        if best:
            results.append(best)
            p = render(f"final-{setname}-{si}", text, best["temp"], best["speed"],
                       best["vol"], best["cue"], voice)
            parts.append(p)
            import fish_tts
            parts.append(fish_tts.silence_wav(350))
    out = LAB / f"{setname}.wav"
    import fish_tts
    if parts:
        fish_tts.stitch_wav(parts[:-1], out)
    doc = {"performer": perf, "set": setname, "voice": voice, "segments": results,
           "out": str(out), "total_ms": fish_tts._ffprobe_ms(out) if out.exists() else 0,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / f"{setname}.json").write_text(json.dumps(doc, indent=2))
    avg = sum(r["score"] for r in results) / max(len(results), 1)
    print(f"DONE {setname}: {len(results)} segs avg_score={avg:.2f} -> {out}", flush=True)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--performer", choices=sorted(PERFORMERS), required=True)
    ap.add_argument("--rounds", type=int, default=1)
    args = ap.parse_args()
    p = PERFORMERS[args.performer]
    for setname in p["sets"]:
        run_set(args.performer, setname, p["voice"], args.rounds)


if __name__ == "__main__":
    main()
