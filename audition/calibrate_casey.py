"""Casey calibration — exact words per emotion segment, rapid auto-iterate.

Segments from casey_rocket_1 (scribe words + gemini emotions):
  manic    17-25s  221 wpm  [excited] energy
  deadpan  25-37s  235 wpm  flat ritual delivery
  gleeful  57-72s  315 wpm  fast confessional laugh-cadence
Score = wpm match + pitch-var near segment target. Free tier, $0.
Outputs: audition/audio/casey-<seg>-<variant>-fish.mp3 + arc demo stitch.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

HERE = Path(__file__).parent
LAB = HERE / "voicelab" / "calibrate"

SEGMENTS = {
    "manic": {
        "text": "God, senior year is gonna be nuts. [chuckling] We're gonna "
                "run this school, man.",
        "target_wpm": 221.2, "target_std": 6.4, "temp": 0.85,
        "ladders": [
            ("excited_fast", "[excited] God, senior year is gonna be nuts. "
                             "[chuckling] We're gonna run this school, man."),
            ("delighted", "[delighted] God, senior year is gonna be nuts. "
                          "[chuckling] We're gonna run this school, man."),
            ("plain_fast", "God, senior year is gonna be nuts. We're gonna "
                           "run this school, man."),
        ],
    },
    "deadpan": {
        "text": "Marble. Marble. Hair. The ritual's almost complete, Tony. "
                "But one of us has to die for the other to truly be free.",
        "target_wpm": 234.5, "target_std": 4.2, "temp": 0.35,
        "ladders": [
            ("indifferent", "[indifferent] Marble. Marble. Hair. The "
                            "ritual's almost complete, Tony. But one of us "
                            "has to die for the other to truly be free."),
            ("whisper", "[whispering] Marble. Marble. Hair. The ritual's "
                        "almost complete, Tony. But one of us has to die "
                        "for the other to truly be free."),
            ("plain", "Marble. Marble. Hair. The ritual's almost complete, "
                      "Tony. But one of us has to die for the other to "
                      "truly be free."),
        ],
    },
    "gleeful": {
        "text": "She pulled me aside and she said, Titty Boy LaCroix, and- "
                "[chuckling] I said, Speaking? And- she said, What do you "
                "wanna be when you grow up? And I told her the truth, Austin.",
        "target_wpm": 315.4, "target_std": 5.3, "temp": 0.8,
        "ladders": [
            ("delighted_wide", "[delighted] She pulled me aside and she "
                               "said, Titty Boy LaCroix, and- [chuckling] I "
                               "said, Speaking? And- she said, What do you "
                               "wanna be when you grow up? And I told her "
                               "the truth, Austin."),
            ("chuckling_run", "[chuckling] She pulled me aside and she "
                              "said, Titty Boy LaCroix, and- I said, "
                              "Speaking? And- she said, What do you wanna "
                              "be when you grow up? And I told her the "
                              "truth, Austin."),
            ("plain_fast", "She pulled me aside and she said, Titty Boy "
                           "LaCroix, and- I said, Speaking? And- she said, "
                           "What do you wanna be when you grow up? And I "
                           "told her the truth, Austin."),
        ],
    },
}


def measure(path, words):
    import voice_judge
    m = voice_judge.measure(path)
    dur = m["duration_ms"] / 1000
    return {"wpm": round(words / dur * 60, 1) if dur else 0,
            "duration_ms": m["duration_ms"],
            "std_st": m["pitch"].get("std_semitones"),
            "median_hz": m["pitch"].get("median_hz"),
            "dyn_db": m["intensity"].get("p90_p10_db")}


def score(m, seg):
    wpm_err = abs(m["wpm"] - seg["target_wpm"])
    std_err = abs((m["std_st"] or 0) - seg["target_std"])
    return round(wpm_err / seg["target_wpm"] * 100 + 0.8 * std_err, 2)


def render(name, text, temp, speed, vol=0.0):
    import fish_tts
    r = fish_tts.synthesize_fish(f"casey-{name}", text, direction=False,
                                 temperature=temp,
                                 prosody={"speed": round(speed, 2), "volume": vol})
    return Path(r["path"])


def main():
    LAB.mkdir(parents=True, exist_ok=True)
    winners = {}
    all_results = []
    for seg_name, seg in SEGMENTS.items():
        print(f"\n== {seg_name} (target {seg['target_wpm']} wpm, std {seg['target_std']}st, temp {seg['temp']}) ==")
        words = len(seg["text"].split())
        base = render(f"{seg_name}-base", seg["text"], seg["temp"], 1.0)
        bm = measure(base, words)
        speed = max(0.5, min(2.0, seg["target_wpm"] / max(bm["wpm"], 1)))
        print(f"  base wpm={bm['wpm']} -> speed={speed:.2f}")
        results = []
        for lad_name, text in seg["ladders"]:
            for d_speed, d_temp, tag in [(0.0, 0.0, ""), (-0.1, 0.0, "_slower"), (0.05, 0.1, "_hot")]:
                s = max(0.5, min(2.0, speed + d_speed))
                t = max(0.25, min(0.95, seg["temp"] + d_temp))
                name = f"{seg_name}_{lad_name}{tag}"
                try:
                    p = render(name, text, t, s)
                    m = measure(p, words)
                    sc = score(m, seg)
                    m.update({"name": name, "ladder": lad_name, "temp": t,
                              "speed": s, "score": sc, "segment": seg_name})
                    results.append(m)
                    all_results.append(m)
                    print(f"  {name:34} wpm={m['wpm']:6.1f} std={m['std_st'] or 0:5.2f} "
                          f"score={sc:6.2f} -> {p.name}")
                    time.sleep(0.25)
                except Exception as e:
                    print(f"  {name:34} FAIL {str(e)[:80]}")
        results.sort(key=lambda r: r["score"])
        winners[seg_name] = results[0]

    # stitch arc demo: best per emotion, his original gap feel (~0.8s)
    import fish_tts
    parts = []
    for seg_name in ("manic", "deadpan", "gleegal" if False else "gleeful"):
        w = winners[seg_name]
        # re-render winner clean for the demo file
        text = next(t for ln, t in SEGMENTS[seg_name]["ladders"] if ln == w["ladder"])
        p = render(f"arc-{seg_name}", text, w["temp"], w["speed"])
        parts.append(p)
        parts.append(fish_tts.silence_wav(800))
    demo = LAB / "casey_arc_demo.wav"
    fish_tts.stitch_wav(parts[:-1], demo)

    doc = {"winners": winners, "results": all_results,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "exact words, wpm-matched to his real segment timing; $0"}
    (LAB / "casey_calibrate.json").write_text(json.dumps(doc, indent=2))
    print("\n== WINNERS ==")
    for k, w in winners.items():
        print(f"  {k:8} {w['name']:34} score={w['score']} wpm={w['wpm']} "
              f"temp={w['temp']} speed={w['speed']}")
    print(f"arc demo: {demo}")


if __name__ == "__main__":
    main()
