"""Character foundry: concept -> funny PERSONA -> dpv-timed sets.

THE PERSONA-FIRST LAW (owner 2026-10-15):
Comedy is not forced. A funny PERSONA is a sincere identity with two
conflicting axes: who they are (baseline, believed fully) x what leaks
(the gap). Material is just that person being themselves in MUNDANE
situations — the situation does the comedy, the persona does the
sincerity. Techniques (dpv timing, garden_path, escalation) are
AMPLIFIERS on an existing tension, never the source. Test: is the
character funny BEFORE it says anything? If yes, the persona works.
Rating loop: owner listens, rates which identity-gap configuration
lands; ratings calibrate future persona derivations (mini-LoRe).

Repeatable pipeline (owner idea -> rating loop):
1. concept -> character graph (identity baseline + violation engine)
   The FUNNY = double violation: violates AUDIENCE expectation of the
   archetype AND his own established identity (dpv: surprise is
   relative to the frame; identity IS the frame).
2. emerge -> affect/delivery texture from the graph
3. material = collision moments aimed at the identity gap
4. dpv scaffold per set: establish baseline (0.6s rhythm) -> ONE
   scheduled surprise late (1.5s coupling pause) -> escalation callback
5. render (voice card) -> verify -> archive with rating slots

Usage: python3 character_foundry.py --kgraph sweetheart_dracula [--variants 3]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from emerge import affect_from_graph, signature_emotion, modulator_cycle
import fish_tts, voice_judge, cf_asr

HERE = Path(__file__).parent
LAB = HERE / "voicelab"

# dpv set scaffold: (beat_type, pause_after_ms) — the Timing-is-Everything template
# dpv: pause AFTER beat N = the pause BEFORE beat N+1. Strategic coupling
# puts the 1.5s extension BEFORE the surprise (pros +41% before surprise).
DPV_SCAFFOLD = [
    ("identity_1", 600),   # establish baseline
    ("identity_2", 600),   # deepen expectation
    ("rhythm", 1500),      # long pause BEFORE the surprise (coupling!)
    ("surprise", 1000),    # let the violation resolve
    ("callback", 800),     # escalation callback
    ("tag", 600),          # button
]


def render_set(foundry_id: str, variant: str, beats: list, voice: str) -> dict:
    """beats: [(type, text)] — dpv pauses from scaffold by position."""
    parts, log = [], []
    for i, (btype, text) in enumerate(beats):
        pause_after = DPV_SCAFFOLD[min(i, len(DPV_SCAFFOLD)-1)][1]
        # surprise beat gets extra pre-weight: slightly lower temp before it
        # is handled by material quality; here render text as-is
        out = fish_tts.synthesize_fish(f"fd-{foundry_id}-{variant}-{i}", text,
                                       voice=voice, direction=False,
                                       temperature=0.45 if i < 3 else (0.7 if i == 3 else 0.55),
                                       prosody={"speed": 1.0, "volume": 0.0})
        parts.append(Path(out["path"]))
        log.append({"beat": i, "type": btype, "text": text,
                    "pause_after_ms": pause_after})
        if i < len(beats) - 1:
            parts.append(fish_tts.silence_wav(pause_after))
        print(f"    [{btype:9}] pause={pause_after}ms  {text[:60]}...")
    wav = LAB / "foundry" / f"{foundry_id}__{variant}.wav"
    wav.parent.mkdir(exist_ok=True)
    fish_tts.stitch_wav(parts, wav)
    return {"wav": str(wav), "beats": log}


def foundry(kgraph_name: str, voice: str, variants: dict) -> list:
    graph = json.loads((HERE / "kgraphs" / f"{kgraph_name}.json").read_text())
    affect = affect_from_graph(graph)
    sig_emo, sig_cue = signature_emotion(graph)
    cycle = modulator_cycle(graph, affect)
    a11 = affect["arousal"] * 2 - 1
    mary_rate = 0.5 * a11 + 0.2 * affect["valence"]
    spec = {"affect_derived": affect,
            "signature": {"emotion": sig_emo, "cue": sig_cue},
            "modulator_cycle": cycle,
            "delivery_spec": {"baseline_tempo": "fast" if mary_rate > 0.15 else (
                "slow" if mary_rate < -0.15 else "conversational"),
                "pitch_band": "wide" if affect["arousal"] > 0.7 else (
                    "narrow" if affect["arousal"] < 0.4 else "mid")}}
    (LAB / "emerged" / f"{kgraph_name}.json").parent.mkdir(parents=True, exist_ok=True)
    (LAB / "emerged" / f"{kgraph_name}.json").write_text(json.dumps(spec, indent=2))
    print(f"FOUNDRY {graph['name']}: A={spec['affect_derived']['arousal']} "
          f"V={spec['affect_derived']['valence']} P={spec['affect_derived']['power']} "
          f"sig={spec['signature']['emotion']}")
    print(f"  identity baseline: {spec['delivery_spec']['baseline_tempo']} / "
          f"{spec['delivery_spec']['pitch_band']} | cycle={spec['modulator_cycle']}")
    results = []
    for variant, beats in variants.items():
        print(f"  variant {variant}:")
        r = render_set(kgraph_name, variant, beats, voice)
        heard = cf_asr.transcribe(Path(r["wav"]))
        hw = {w["text"].lower().strip(".,!?;:'\"") for w in heard.get("words", [])}
        intended = " ".join(b[1] for b in beats)
        iw = [w.lower().strip(".,!?;:'\"") for w in intended.split()]
        unsaid = [w for w in iw if w not in hw]
        match = round(1 - len(unsaid)/max(len(iw),1), 3)
        m = voice_judge.measure(Path(r["wav"]))
        rec = {"foundry": kgraph_name, "variant": variant, "voice": voice,
               "affect": spec["affect_derived"], "verify_match": match,
               "unsaid": unsaid[:6], "duration_ms": m["duration_ms"],
               "beats": r["beats"], "rating": None, "rating_note": "owner listens here",
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        outp = LAB / "foundry" / f"{kgraph_name}__{variant}.json"
        outp.write_text(json.dumps(rec, indent=2))
        import shutil
        shutil.copy(r["wav"], f"/home/box/{kgraph_name}__{variant}.wav")
        print(f"    verify={match} dur={rec['duration_ms']}ms -> /home/box/{kgraph_name}__{variant}.wav")
        results.append(rec)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kgraph", required=True)
    ap.add_argument("--voice", default="04e9ab898fb44ccd9b7ac2357439d6ec")
    ap.add_argument("--variants-file", required=True)
    args = ap.parse_args()
    variants = json.loads(Path(args.variants_file).read_text())
    foundry(args.kgraph, args.voice, variants)
