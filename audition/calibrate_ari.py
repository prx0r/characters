"""Calibrate to ari's exact segment: same words, match his real wpm + emotion.

Target from scribe+gemini: kt704 40.5-54.0s, mock_indignant, rapid_fire,
energy .95, 289.6 wpm over 13.9s. Variables = only what fish accepts:
[emotion] cues, temperature, prosody.speed, volume. Free tier, $0.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

HERE = Path(__file__).parent
LAB = HERE / "voicelab" / "calibrate"
TARGET_WPM = 289.6
TEXT = ("Who gives a crap? You're here on the winning side. [chuckling] If "
        "you don't like America, go check out Ukraine. Try to get an oatmeal "
        "latte in downtown Kiev, you ungrateful crap.")


def measure(path):
    import voice_judge
    import fish_tts
    m = voice_judge.measure(path)
    words = len(TEXT.split())
    dur_s = m["duration_ms"] / 1000
    wpm = words / dur_s * 60 if dur_s else 0
    return {"wpm": round(wpm, 1), "duration_ms": m["duration_ms"],
            "p90_p10_db": m["intensity"].get("p90_p10_db"),
            "std_semitones": m["pitch"].get("std_semitones"),
            "median_hz": m["pitch"].get("median_hz")}


def render(name, text, temp, speed, volume=1.0):
    import fish_tts
    r = fish_tts.synthesize_fish(f"cal-{name}", text, direction=False,
                                 temperature=temp,
                                 prosody={"speed": speed, "volume": volume})
    return Path(r["path"])


def main():
    LAB.mkdir(parents=True, exist_ok=True)
    import fish_tts

    # base wpm of the free voice on this text
    base = render("base", TEXT, 0.7, 1.0)
    bm = measure(base)
    speed = max(0.5, min(2.0, TARGET_WPM / max(bm["wpm"], 1)))
    print(f"base wpm={bm['wpm']} -> speed={speed:.2f} to hit {TARGET_WPM}", flush=True)

    variants = [
        ("paced_plain", TEXT, 0.7, speed, 0.0),
        ("cues_mid", f"[frustrated] Who gives a crap? You're here on the "
                     f"winning side. [chuckling] If you don't like America, "
                     f"go check out Ukraine. Try to get an oatmeal latte in "
                     f"downtown Kiev, you ungrateful crap.", 0.75, speed, 0.5),
        ("cues_hot", f"[frustrated] Who gives a crap? You're here on the "
                     f"winning side. [chuckling] If you don't like America, "
                     f"go check out Ukraine. [emphasis]Try to get an oatmeal "
                     f"latte in downtown Kiev, [angry] you ungrateful crap.", 0.85, speed, 1.5),
        ("cues_max", f"[excited] Who gives a crap? You're here on the "
                     f"winning side. [chuckling] If you don't like America, "
                     f"go check out Ukraine. [shouting]Try to get an oatmeal "
                     f"latte in downtown Kiev, you ungrateful crap.", 0.95, speed, 2.0),
        ("cues_sarcastic", f"[sarcastic] Who gives a crap? You're here on "
                           f"the winning side. If you don't like America, go "
                           f"check out Ukraine. Try to get an oatmeal latte "
                           f"in downtown Kiev, you ungrateful crap.", 0.75, speed, 1.0),
        ("temp_ladder", f"[frustrated] Who gives a crap? You're here on the "
                        f"winning side. [chuckling] If you don't like America, "
                        f"go check out Ukraine. Try to get an oatmeal latte "
                        f"in downtown Kiev, you ungrateful crap.", 0.9, speed * 1.05, 1.0),
    ]
    board = [{"name": "base_no_cues", **bm, "temp": 0.7, "speed": 1.0}]
    for name, text, temp, speed_m, vol in variants:
        try:
            p = render(name, text, temp, speed_m, vol)
            m = measure(p)
            m.update({"name": name, "temp": temp, "speed": speed_m,
                      "wpm_err": round(abs(m["wpm"] - TARGET_WPM), 1)})
            board.append(m)
            print(f"  {name:16} wpm={m['wpm']:6.1f} err={m['wpm_err']:5.1f} "
                  f"dyn={m['p90_p10_db']} st={m['std_semitones']} "
                  f"->{p.name}", flush=True)
            time.sleep(0.3)
        except Exception as e:
            print(f"  {name:16} FAIL {str(e)[:100]}", flush=True)

    scored = [b for b in board if "wpm_err" in b]
    scored.sort(key=lambda b: (b["wpm_err"], -(b["p90_p10_db"] or 0)))
    doc = {"target_wpm": TARGET_WPM, "text": TEXT,
           "best": scored[0] if scored else None, "board": board,
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / "ari_calibrate.json").write_text(json.dumps(doc, indent=2))
    if scored:
        b = scored[0]
        print(f"\nBEST: {b['name']} wpm={b['wpm']} (target {TARGET_WPM}) "
              f"temp={b['temp']} speed={b['speed']}", flush=True)


if __name__ == "__main__":
    main()
