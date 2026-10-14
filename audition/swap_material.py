"""Material swap: proven delivery stencil x original world material x any voice.

The full engine in one call:
  stencil (KT performer's recipes+arc)  x  material (freaks pack persona text)
  x  voice slot (card or clone)  ->  rendered set  ->  CF whisper verify.

Usage: python3 swap_material.py --stencil kt704_standup --pack kappa-kyle-cucumber-debt --voice kid_darwin
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"

VOICES = {
    "kid_darwin": "3a561684e5fa46eb9528e8e6ff9000c9",
    "spongebob": "0051da373e0a4ac282399909d1d31b69",
    "roast": "4805c450f3e84faaa16f2cf9690fbd90",
    "narrator": "8d21b053e2804e2a890e1cf62f267b6f",
    "luna": "fe2619861dfc4bcab9da073029ca80a4",
    "mommy": "60bd8f0f5bbc462a8fa1686dd81af336",
    "ari_clone": "dbeb1d68566245e2b857617b830e8031",
    "casey_clone": "9c36c951cee84457a5cc9f94387e9a42",
    "pickles_clone": "100e10e7c5464a10b5120a01ade115a2",
    "louis_clone": "fb015415ebf141999fc882baa0e0834c",
}

# arc-shaped material slots: (beat_label, prompt to fill from pack persona)
# Labels follow the kt704 emotional arc; material = pack content.
SLOT_PROMPTS = {
    "manic": "opener: state who you are and the absurd premise, fast and excited",
    "sarcastic": "dry escalation of the premise — one concrete absurd detail",
    "mock_indignant": "the grievance peak: the thing that's unfair in your world",
    "gleeful": "closer: tag line that calls back to the premise, delighted",
    "neutral": "bridge: one observational beat",
}


def load_pack_material(slug: str) -> dict:
    c = json.loads((REPO / "freaks" / slug / "character.json").read_text())
    persona = c.get("persona", {}) or {}
    dc = c.get("dramatic_core", {}) or {}
    return {
        "name": c.get("name", slug),
        "deal": persona.get("deal", ""),
        "facts": persona.get("facts", []) or [],
        "want": dc.get("want", ""), "fear": dc.get("fear", ""),
        "blind": (dc.get("blind_spots") or [""])[0],
        "vibe": c.get("vibe", "neutral"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stencil", default="ari_matti_kt704_passport")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--voice", default="kid_darwin")
    ap.add_argument("--extra-material", default="",
                    help="freeform world material to weave in")
    args = ap.parse_args()

    import fish_tts, voice_judge, cf_asr

    sten = json.loads((LAB / "stencils" / f"{args.stencil}.json").read_text())
    mat = load_pack_material(args.pack)
    voice = VOICES.get(args.voice, args.voice)

    # build material lines mapped to the arc (original words, pack-sourced)
    facts = mat["facts"]
    lines = {
        "manic": f"I'm {mat['name']}! {mat['deal'].split('.')[0]}!",
        "sarcastic": (facts[0].rstrip(".") + "." if facts else mat["deal"]),
        "mock_indignant": (f"They say {mat['blind'].rstrip('.')} — "
                           f"and I still can't get my {mat['want'].rstrip('.')}!"),
        "gleeful": (facts[1].rstrip(".") + "." if len(facts) > 1 else
                    f"Bow back. I dare you."),
        "neutral": (facts[2].rstrip(".") + "." if len(facts) > 2 else
                    "The ledger never lies."),
    }
    if args.extra_material:
        lines["sarcastic"] = args.extra_material

    parts, beats_log, t0 = [], [], time.time()
    for s in sten["segments"]:
        r = s["recipe"]
        label = s["material_slot"]["beat_label"]
        text = lines.get(label, mat["deal"])
        cue = r["cue"]
        t = f"{cue} {text}".strip() if cue else text
        out = fish_tts.synthesize_fish(
            f"swap-{args.pack}-{args.stencil}-{s['seg']}", t, voice=voice,
            direction=False, temperature=r["temp"],
            prosody={"speed": r["speed"], "volume": r["vol"]})
        p = Path(out["path"])
        parts.append(p)
        beats_log.append({"seg": s["seg"], "label": label, "text": text,
                          "recipe": r, "file": str(p)})
        print(f"  seg{s['seg']} [{label}] {text[:60]}...")
        parts.append(fish_tts.silence_wav(350))

    outdir = LAB / "swaps"
    outdir.mkdir(exist_ok=True)
    wav = outdir / f"{args.pack}__{args.stencil}__{args.voice}.wav"
    fish_tts.stitch_wav(parts[:-1], wav)

    # verify
    intended = " ".join(b["text"] for b in beats_log)
    heard = cf_asr.transcribe(wav)
    hw = {w["text"].lower().strip(".,!?;:'\"") for w in heard.get("words", [])}
    intended_words = [w.lower().strip(".,!?;:'\"") for w in intended.split()]
    unsaid = [w for w in intended_words if w not in hw]
    match = round(1 - len(unsaid) / max(len(intended_words), 1), 3)
    m = voice_judge.measure(wav)

    rec = {"pack": args.pack, "stencil": args.stencil, "voice": args.voice,
           "voice_id": voice, "beats": beats_log, "out": str(wav),
           "verify_match": match, "unsaid": unsaid[:10],
           "laugh_events": len(heard.get("laugh_events") or []),
           "duration_ms": m["duration_ms"],
           "pitch_std": m["pitch"].get("std_semitones"),
           "elapsed_s": round(time.time() - t0, 1),
           "note": "delivery=KT stencil, material=pack persona, voice=card",
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    rp = outdir / f"{args.pack}__{args.stencil}__{args.voice}.json"
    rp.write_text(json.dumps(rec, indent=2))
    print(f"\nSWAP: {wav}")
    print(f"verify match={match} unsaid={unsaid[:5] or 'none'} "
          f"laughters={rec['laugh_events']} dur={rec['duration_ms']}ms")


if __name__ == "__main__":
    main()
