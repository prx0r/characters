"""Casey riff-chain engine: the five-stage cognitive sequence as generator.

From casey_rocket_FULL_analysis.riff_architecture:
  acoustic intake -> instant uncritical agreement -> structural
  misinterpretation -> scientific/corporate semantic grafting -> visceral
  somatic consequence.
Techniques: literalize / non_sequitur / absurdist_expansion / callback.
Grains: quick_riff (trigger .44), micro_tag (.43), full_riff (.38).
Chain = seed premise -> riffs through the sequence -> micro_tag callback.

This is RIFFING, not beat-writing: short associative units in the
comedian's linkage logic. Character lore supplies the domains to graft.

Usage: python3 riff_chain.py --world joker --seed "the guard asked about my treatment plan" --n 6
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
import fish_tts, voice_judge, cf_asr

HERE = Path(__file__).parent
LAB = HERE / "voicelab"

# the five stages (FULL_analysis cognitive_sequence) x techniques
STAGES = ["intake_agree", "misinterpret", "graft", "visceral", "callback_tag"]
TECHS = {"literalize": "take the figurative thing as literal physics",
         "non_sequitur": "respond to the wrong semantic slot entirely",
         "absurdist_expansion": "escalate the premise into unverifiable territory"}

# grain recipes (casey calibrated): quick/micro short+fast, full slower
GRAINS = {"quick_riff": {"temp": 0.85, "speed": 1.35, "cue": "[excited]", "max_words": 22},
          "micro_tag": {"temp": 0.45, "speed": 0.85, "cue": "", "max_words": 12},
          "full_riff": {"temp": 0.80, "speed": 1.10, "cue": "[delighted]", "max_words": 35}}


def chain_for(world: dict, seed: str, n: int = 6, seed_rng: int = 7) -> list:
    """Generate an n-riff chain: stage cycle + grain schedule + world grafts.
    Deterministic (seeded) for replay."""
    rng = random.Random(seed_rng)
    grafts = world.get("graft_domains", ["corporate jargon", "science-y terms"])
    specifics = world.get("specifics", ["the situation"])
    chain = []
    grain_seq = (["quick_riff"] * max(0, n - 2)) + ["micro_tag", "micro_tag"]
    for i in range(n):
        stage = STAGES[i % 4] if i < n - 2 else ("callback_tag" if i == n - 1 else "micro_callback")
        grain = grain_seq[i]
        # riffs are PRE-GENERATED world text here (the generator instantiates
        # the sequence structure; world material authored per world tokens)
        chain.append({"i": i, "stage": stage, "grain": grain})
    return chain


def render_chain(foundry_id: str, riffs: list, voice: str, world_name: str) -> dict:
    """riffs: [(grain, text)] — render with grain recipe + casey tempo."""
    parts, log = [], []
    for i, (grain, text) in enumerate(riffs):
        g = GRAINS[grain]
        out = fish_tts.synthesize_fish(f"rc-{foundry_id}-{i}", text, voice=voice,
                                       direction=False, temperature=g["temp"],
                                       prosody={"speed": g["speed"], "volume": 0.0})
        parts.append(Path(out["path"]))
        # micro_tags get the short laugh-scale gap; quick_riffs get Casey's
        # short pre-pause (laughed riffs: shorter pauses)
        gap = 350 if grain == "quick_riff" else (600 if grain == "full_riff" else 500)
        log.append({"i": i, "grain": grain, "text": text, "gap_ms": gap})
        if i < len(riffs) - 1:
            parts.append(fish_tts.silence_wav(gap))
        print(f"  [{grain:9}] {text[:62]}...")
    wav = LAB / "riffchains" / f"{foundry_id}__{world_name}.wav"
    wav.parent.mkdir(exist_ok=True)
    fish_tts.stitch_wav(parts, wav)
    return {"wav": str(wav), "riffs": log}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundry-id", required=True)
    ap.add_argument("--world", required=True, help="json: {graft_domains, specifics}")
    ap.add_argument("--riffs-file", required=True, help="json: [[grain, text], ...]")
    ap.add_argument("--voice", required=True)
    args = ap.parse_args()
    world = json.loads(Path(args.world).read_text())
    riffs = json.loads(Path(args.riffs_file).read_text())
    r = render_chain(args.foundry_id, riffs, args.voice, world.get("name", "world"))
    heard = cf_asr.transcribe(Path(r["wav"]))
    hw = {w["text"].lower().strip(".,!?;:'\"") for w in heard.get("words", [])}
    iw = [w.lower().strip(".,!?;:'\"") for w in " ".join(t for _, t in riffs).split()]
    unsaid = [w for w in iw if w not in hw]
    match = round(1 - len(unsaid)/max(len(iw),1), 3)
    m = voice_judge.measure(Path(r["wav"]))
    import shutil
    shutil.copy(r["wav"], f"/home/box/{args.foundry_id}.wav")
    out = {**r, "world": world.get("name"), "verify_match": match,
           "unsaid": unsaid[:6], "duration_ms": m["duration_ms"],
           "note": "casey five-stage riff chain; grain recipes from trigger-rate data",
           "rating": None}
    Path(str(r["wav"]).replace(".wav", ".json")).write_text(json.dumps(out, indent=2))
    print(f"\nverify={match} dur={m['duration_ms']}ms -> /home/box/{args.foundry_id}.wav")
