"""A/B voice lab — crack Fish prompt language for performer delivery profiles.

Two halves:
  ladders  — DELIVERY prompts (cues + temperature + speed) rendered on
             s2.1-pro-free ($0). Available now. Same probe line, different
             cue recipes per performer profile. Listen, rank, keep winners.
  prompts  — TIMBRE prompts (voice-design-1 instruction variants) written
             as ready-to-fire request bodies. No API call — voice-design
             needs API credit ($0.01/req, currently 402). When credit lands:
             python3 voicecast.py design <slug> --ab-body voicelab/ab-prompts/...

Stats source: theory/vibe-bands.json performers block (delivery models only).
Never names the real person in a prompt — delivery descriptors only.

Usage:
  python3 ab_voice.py ladders ari_matti
  python3 ab_voice.py ladders casey_rocket
  python3 ab_voice.py prompts            # write all timbre bodies (no API)
  python3 ab_voice.py rank ari_matti 2 4 1 3   # save your ranking (best→worst)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab" / "ab"
BANDS = REPO / "theory" / "vibe-bands.json"

# Fixed probe: original stage patter, two setups -> absurd turn -> deadpan
# closer. Exercises the arcs without echoing anyone's material.
PROBE = ("Audiences always ask me about the schedule. I tell them the schedule "
         "is a suggestion. Last week the schedule showed up at my door and I "
         "offered it a seat. It declined. Now we meet Thursdays, formally, "
         "and nobody moves first.")

# Delivery ladders: (variant, [(section_text_prefix, cue, speed, volume_db)],
# temperature). Section = split of PROBE by sentence.
LADDERS = {
    "ari_matti": {
        "note": "DNA: sarcastic measured setups -> mock-indignant/manic spikes, "
                "pitch spikes, temp mid. Bands: pitch_var 4.2-5.5st, med ~187Hz.",
        "variants": [
            ("v1_spike_arc", 0.65, [
                ("Audiences", "[neutral]", 1.0, 0.0),
                ("I tell them", "[sarcastic]", 1.0, 0.0),
                ("Last week", "[sarcastic]", 1.15, 0.5),
                ("It declined", "[frustrated]", 1.2, 1.5),
                ("Now we meet", "[indifferent]", 0.9, 0.0),
            ]),
            ("v2_dry_hot", 0.6, [
                ("Audiences", "[calm]", 0.9, 0.0),
                ("I tell them", "[indifferent]", 0.95, 0.0),
                ("Last week", "[sarcastic]", 1.1, 0.5),
                ("It declined", "[shouting]", 1.25, 2.0),
                ("Now we meet", "[sarcastic]", 0.85, 0.0),
            ]),
            ("v3_explode", 0.75, [
                ("Audiences", "[sarcastic]", 1.0, 0.0),
                ("I tell them", "[sarcastic]", 1.05, 0.0),
                ("Last week", "[excited]", 1.3, 1.0),
                ("It declined", "[angry]", 1.35, 2.0),
                ("Now we meet", "[calm]", 0.8, 0.0),
            ]),
            ("v4_control", 0.7, [
                ("Audiences", "", 1.0, 0.0),
                ("is a suggestion", "", 1.0, 0.0),
                ("showed up", "", 1.0, 0.0),
                ("It declined", "", 1.0, 0.0),
                ("nobody moves", "", 1.0, 0.0),
            ]),
        ],
    },
    "casey_rocket": {
        "note": "DNA: manic/gleeful energy, rapid_fire, pitch spikes, "
                "deadpan drops. Bands: energy .55-.85, pace up to .8+.",
        "variants": [
            ("v1_manic_swing", 0.85, [
                ("Audiences", "[excited]", 1.15, 0.5),
                ("I tell them", "[delighted]", 1.1, 0.5),
                ("Last week", "[excited]", 1.3, 1.0),
                ("It declined", "[indifferent]", 0.8, 0.0),
                ("Now we meet", "[delighted]", 1.2, 0.5),
            ]),
            ("v2_rapid_gleeful", 0.9, [
                ("Audiences", "[delighted]", 1.45, 0.5),
                ("I tell them", "[delighted]", 1.45, 0.5),
                ("Last week", "[hysterical]", 1.45, 1.0),
                ("It declined", "[chuckling]", 1.2, 0.5),
                ("Now we meet", "[excited]", 1.45, 1.0),
            ]),
            ("v3_drop_out", 0.8, [
                ("Audiences", "[excited]", 1.3, 1.0),
                ("I tell them", "[excited]", 1.25, 0.5),
                ("Last week", "[confused]", 1.35, 1.0),
                ("It declined", "[whispering]", 0.7, -3.0),
                ("Now we meet", "[embarrassed]", 0.85, -1.0),
            ]),
            ("v4_control", 0.7, [
                ("Audiences", "", 1.0, 0.0),
                ("is a suggestion", "", 1.0, 0.0),
                ("showed up", "", 1.0, 0.0),
                ("It declined", "", 1.0, 0.0),
                ("nobody moves", "", 1.0, 0.0),
            ]),
        ],
    },
}

# Timbre prompt variants — voice-design bodies (NOT sent; need API credit).
TIMBRE = {
    "ari_matti": [
        "Comedy stage voice, adult male, mid-range pitch around 185Hz with "
        "sudden wide pitch swings, crisp consonants, light Nordic-European "
        "accent in English, dry measured setups that snap into sharp "
        "high-energy spikes, expressive not flat.",
        "Adult male comedian voice, mid pitch, high pitch variability, "
        "sarcastic unhurried cadence that explodes into fast mock-indignant "
        "bursts, slight rasp at volume, sharp intake of energy on punchlines.",
        None,  # filled from bands voice_design_extra
    ],
    "casey_rocket": [
        "Comedy stage voice, adult male, kinetic rapid-fire delivery, wide "
        "pitch swings with sudden spikes, slightly raspy warm stoner-cadence, "
        "gleeful manic energy that can collapse into flat deadpan instantly.",
        "Adult male, fast erratic pacing, pitch spikes then abrupt drops, "
        "playful surreal warmth, high energy with sudden deadpan, mid pitch.",
        None,
    ],
}


def _load_fish():
    import fish_tts
    return fish_tts


def render_ladder(performer: str, variant: str, temp: float,
                  sections: list[tuple[str, str, float, float]]) -> dict:
    fish = _load_fish()
    sentences = [s.strip() for s in PROBE.split(".") if s.strip()]
    parts = []
    for sent, (prefix, cue, speed, vol) in zip(sentences, sections):
        if prefix.lower() not in sent.lower():
            raise RuntimeError(f"section mismatch: {sent[:30]!r} vs {prefix!r}")
        text = f"{cue} {sent}.".strip() if cue else f"{sent}."
        out_dir = LAB / performer
        out_dir.mkdir(parents=True, exist_ok=True)
        tag = f"{variant}-{prefix[:8].strip().lower().replace(' ', '')}"
        r = fish.synthesize_fish(f"ab-{performer}-{tag}", text,
                                 modulator="neutral", direction=False,
                                 temperature=temp,
                                 prosody={"speed": speed, "volume": vol})
        parts.append(r)
        time.sleep(0.3)
    total = sum(p["duration_ms"] for p in parts)
    return {"variant": variant, "temperature": temp, "beats": parts,
            "total_ms": total}


def cmd_ladders(performer: str) -> None:
    spec = LADDERS[performer]
    outdir = LAB / performer
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"# {performer} delivery ladders — s2.1-pro-free, $0")
    print(f"# {spec['note']}")
    manifest = {"performer": performer, "probe": PROBE,
                "note": spec["note"], "rendered_at":
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "variants": []}
    for variant, temp, sections in spec["variants"]:
        m = render_ladder(performer, variant, temp, sections)
        # stitch variant to one file for easy listening
        parts = [Path(b["path"]) for b in m["beats"]]
        out = outdir / f"{variant}.wav"
        fish = _load_fish()
        fish.stitch_wav(parts, out)
        m["file"] = str(out)
        manifest["variants"].append(m)
        print(f"  {variant:16} temp={temp}  {m['total_ms']}ms  -> {out}")
    (outdir / "ladders.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"listen, then: python3 ab_voice.py rank {performer} <best> <2nd> <3rd> <worst>")


def cmd_prompts() -> None:
    bands = json.loads(BANDS.read_text()) if BANDS.exists() else {}
    out = REPO / "audition" / "voicelab" / "ab-prompts"
    out.mkdir(parents=True, exist_ok=True)
    for performer, variants in TIMBRE.items():
        extra = ((bands.get("performers") or {}).get(performer)
                 or {}).get("voice_design_extra") or ""
        bodies = []
        for i, v in enumerate(variants):
            instr = v or extra
            if not instr:
                continue
            bodies.append({
                "variant": f"t{i+1}",
                "request": {"instruction": instr[:2000],
                            "reference_text": PROBE.split(".")[0] + ".",
                            "language": "en", "n": 1, "seed": 42},
                "sent": False,
                "cost_if_fired_usd": 0.01,
            })
        p = out / f"{performer}.json"
        p.write_text(json.dumps({"performer": performer, "bodies": bodies,
                                 "blocked_on": "API credit (voice-design 402)"}, indent=2))
        print(f"{p}  ({len(bodies)} bodies ready, $0.01 each when credit lands)")


def cmd_rank(performer: str, order: list[int]) -> None:
    p = LAB / performer / "ladders.json"
    if not p.exists():
        raise RuntimeError(f"render ladders first: {p} missing")
    m = json.loads(p.read_text())
    names = [v["variant"] for v in m["variants"]]
    if sorted(order) != [1, 2, 3, 4]:
        raise RuntimeError("rank needs a permutation of 1 2 3 4 (best→worst)")
    m["ranking_best_to_worst"] = [names[i - 1] for i in order]
    m["winner"] = names[order[0] - 1]
    p.write_text(json.dumps(m, indent=2))
    print(f"winner: {m['winner']}  (full ranking saved to {p})")


def _main() -> None:
    ap = argparse.ArgumentParser(description="A/B voice prompt lab (free tier)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("ladders", help="render delivery ladders ($0 fish free)")
    l.add_argument("performer", choices=sorted(LADDERS))
    sub.add_parser("prompts", help="write timbre voice-design bodies (no API)")
    r = sub.add_parser("rank", help="save owner ranking best->worst")
    r.add_argument("performer", choices=sorted(LADDERS))
    r.add_argument("order", nargs=4, type=int)
    args = ap.parse_args()
    if args.cmd == "ladders":
        cmd_ladders(args.performer)
    elif args.cmd == "prompts":
        cmd_prompts()
    elif args.cmd == "rank":
        cmd_rank(args.performer, args.order)


if __name__ == "__main__":
    _main()
