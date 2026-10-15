"""Autonomous sonic optimizer — close the gap to ari_matti delivery stats.

Loop: render probe variants (base voice x ladder x temperature) on
s2.1-pro-free ONLY ($0) -> measure with voice_judge -> score distance to
ari bands (pitch median + pitch variability) -> mutate around the best
-> repeat. Leaderboard + winning recipe saved to voicelab/ab/ari_matti/.

Caveat: pitch tracker is a consistent relative proxy (not Praat) — good for
ranking variants, not absolute Hz truth. Bands came from real Praat stats.

Usage: python3 optimize_ari.py [--rounds 2]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
LAB = HERE / "voicelab" / "ab" / "ari_matti"
BANDS = HERE.parent / "theory" / "vibe-bands.json"

# Public library voices (docs-safe defaults) as base-voice levers.
# None = fish default voice. Errors on a voice are skipped, not fatal.
BASE_VOICES = [
    (None, "default"),
    ("bf322df2096a46f18c579d0baa36f41d", "adrian"),
    ("c70cfb98867a4bfb9ae20d2401257b92", "delia"),
]

# Ladder styles: (name, temp, sections[(prefix,cue,speed,vol)])
LADDERS = {
    "spike_arc": [
        ("Audiences", "[neutral]", 1.0, 0.0),
        ("I tell them", "[sarcastic]", 1.0, 0.0),
        ("Last week", "[sarcastic]", 1.15, 0.5),
        ("It declined", "[frustrated]", 1.2, 1.5),
        ("Now we meet", "[indifferent]", 0.9, 0.0),
    ],
    "dry_hot": [
        ("Audiences", "[calm]", 0.9, 0.0),
        ("I tell them", "[indifferent]", 0.95, 0.0),
        ("Last week", "[sarcastic]", 1.1, 0.5),
        ("It declined", "[shouting]", 1.25, 2.0),
        ("Now we meet", "[sarcastic]", 0.85, 0.0),
    ],
    "explode": [
        ("Audiences", "[sarcastic]", 1.0, 0.0),
        ("I tell them", "[sarcastic]", 1.05, 0.0),
        ("Last week", "[excited]", 1.3, 1.0),
        ("It declined", "[angry]", 1.35, 2.0),
        ("Now we meet", "[calm]", 0.8, 0.0),
    ],
    "swing_wide": [
        ("Audiences", "[sarcastic]", 0.95, 0.0),
        ("I tell them", "[confused]", 1.05, 0.0),
        ("Last week", "[excited]", 1.25, 1.0),
        ("It declined", "[indifferent]", 0.85, -1.0),
        ("Now we meet", "[sarcastic]", 1.1, 0.5),
    ],
}

PROBE = ("Audiences always ask me about the schedule. I tell them the schedule "
         "is a suggestion. Last week the schedule showed up at my door and I "
         "offered it a seat. It declined. Now we meet Thursdays, formally, "
         "and nobody moves first.")


def targets() -> dict:
    d = json.loads(BANDS.read_text())
    ari = d["performers"]["ari_matti"]["prosody"]
    return {"median_hz": ari["pitch_median_hz"]["mid"],
            "median_band": [ari["pitch_median_hz"]["lo"], ari["pitch_median_hz"]["hi"]],
            "std_st": ari["pitch_var_st"]["mid"],
            "std_band": [ari["pitch_var_st"]["lo"], ari["pitch_var_st"]["hi"]]}


def render_variant(name: str, voice_ref: str | None, ladder: str,
                   temp: float, speed_scale: float = 1.0) -> Path:
    import fish_tts
    sentences = [s.strip() for s in PROBE.split(".") if s.strip()]
    parts = []
    for sent, (prefix, cue, speed, vol) in zip(sentences, LADDERS[ladder]):
        text = f"{cue} {sent}.".strip() if cue else f"{sent}."
        r = fish_tts.synthesize_fish(f"opt-{name}", text, voice=voice_ref,
                                     modulator="neutral", direction=False,
                                     temperature=temp,
                                     prosody={"speed": round(min(2.0, max(0.5, speed * speed_scale)), 2),
                                              "volume": vol})
        parts.append(Path(r["path"]))
        time.sleep(0.35)
    out = LAB / f"{name}.wav"
    fish_tts.stitch_wav(parts, out)
    return out


def measure_variant(wav: Path, tg: dict) -> dict:
    import voice_judge
    m = voice_judge.measure(wav)
    med = m["pitch"].get("median_hz") or 0.0
    std = m["pitch"].get("std_semitones") or 0.0
    d_med = abs(med - tg["median_hz"]) / max(tg["median_hz"], 1)
    d_std = abs(std - tg["std_st"]) / max(tg["std_st"], 0.5)
    in_med = tg["median_band"][0] <= med <= tg["median_band"][1]
    in_std = tg["std_band"][0] <= std <= tg["std_band"][1]
    return {"median_hz": med, "std_semitones": std,
            "d_median": round(d_med, 4), "d_std": round(d_std, 4),
            "distance": round(0.5 * d_med + 0.5 * d_std, 4),
            "in_median_band": in_med, "in_std_band": in_std,
            "duration_ms": m["duration_ms"]}


def run_round(round_id: int, recipes: list[dict], tg: dict,
              board: list[dict]) -> list[dict]:
    results = []
    for rec in recipes:
        name = rec["name"]
        try:
            wav = render_variant(name, rec.get("voice_ref"), rec["ladder"],
                                 rec["temp"], rec.get("speed_scale", 1.0))
            m = measure_variant(wav, tg)
            m.update(rec)
            m["round"] = round_id
            board.append(m)
            results.append(m)
            print(f"  R{round_id} {name:28} dist={m['distance']:.3f} "
                  f"med={m['median_hz']:.0f} std={m['std_semitones']:.2f} "
                  f"bands={'YY' if (m['in_median_band'] and m['in_std_band']) else 'n '}",
                  flush=True)
        except Exception as e:
            print(f"  R{round_id} {name:28} FAIL {str(e)[:120]}", flush=True)
    return results


def mutate(best: list[dict]) -> list[dict]:
    """Round-2 recipes: perturb the best round-1 variants."""
    out = []
    for b in best[:2]:
        base = b["name"].rsplit("_r1", 1)[0]
        for i, (dt, ds) in enumerate([(-0.1, 1.1), (0.1, 0.9), (0.0, 1.2)]):
            out.append({"name": f"{base}_mut{i}_r2", "voice_ref": b.get("voice_ref"),
                        "voice": b.get("voice"), "ladder": b["ladder"],
                        "temp": round(max(0.3, min(0.95, b["temp"] + dt)), 2),
                        "speed_scale": ds})
        # ladder swap on same voice
        for lad in LADDERS:
            if lad != b["ladder"]:
                out.append({"name": f"{base}_{lad}_r2", "voice_ref": b.get("voice_ref"),
                            "voice": b.get("voice"), "ladder": lad,
                            "temp": b["temp"], "speed_scale": 1.0})
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args()
    LAB.mkdir(parents=True, exist_ok=True)
    tg = targets()
    print(f"target: median {tg['median_hz']}Hz band {tg['median_band']} | "
          f"std {tg['std_st']}st band {tg['std_band']}", flush=True)
    board: list[dict] = []

    r1 = []
    for vref, vname in BASE_VOICES:
        for ladder in ("spike_arc", "dry_hot"):
            for temp in (0.6, 0.8):
                r1.append({"name": f"{vname}_{ladder}_t{temp}_r1".replace(".", ""),
                           "voice_ref": vref, "voice": vname, "ladder": ladder,
                           "temp": temp})
    print(f"round 1: {len(r1)} variants", flush=True)
    res1 = run_round(1, r1, tg, board)
    res1.sort(key=lambda r: r["distance"])
    best = res1[:2]
    print(f"round 1 best: {best[0]['name']} dist={best[0]['distance']}", flush=True)

    if args.rounds >= 2 and best:
        r2 = mutate(best)
        print(f"round 2: {len(r2)} mutants of {', '.join(b['name'] for b in best)}", flush=True)
        run_round(2, r2, tg, board)

    board.sort(key=lambda r: r["distance"])
    winner = board[0]
    doc = {"performer": "ari_matti", "target": tg,
           "note": "relative pitch proxy; free tier only; $0 total",
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "winner": winner, "board": board}
    (LAB / "optimize.json").write_text(json.dumps(doc, indent=2))
    print(f"\nWINNER: {winner['name']}  dist={winner['distance']}  "
          f"med={winner['median_hz']} std={winner['std_semitones']}  "
          f"recipe: voice={winner.get('voice')} ladder={winner['ladder']} "
          f"temp={winner['temp']} speed_scale={winner.get('speed_scale', 1)}",
          flush=True)
    print(f"saved {LAB / 'optimize.json'}  ({len(board)} variants tested)", flush=True)


if __name__ == "__main__":
    main()
