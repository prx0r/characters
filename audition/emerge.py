"""Character → delivery emergence: the inner life IS the delivery spec.

Owner principle: for a NEW character, delivery emerges from the character
graph — dramatic_core, philosophy, blind_spots, misinterpretation_rule —
not from a comedian lookup. The MARY affect layer closes the chain:
inner life -> (arousal, valence, power) -> (rate, volume, range, direction).

Rules (grounded in our measured science):
- fear lexicon -> arousal↑ valence↓ (threat-preparation = Frijda readiness)
- want/ontology keywords -> power (hierarchy/court/debt = high control)
- blind_spots -> modulator cycling set (the states contradictions push them into)
- misinterpretation_rule -> signature emotion (what criticism BECOMES)
- persona.interview_style -> micro-tempo texture
- vibe field -> baseline EMO recipe

Usage: python3 emerge.py kappa-kyle-cucumber-debt
       python3 emerge.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent

# lexicons -> affect deltas (arousal, valence, power)
FEAR_WORDS = {"dry", "exposed", "failure", "fail", "shame", "caught", "dead",
              "die", "threat", "watched", "humiliate", "collapse", "dishonor"}
POWER_WORDS = {"hierarchy", "court", "ledger", "debt", "tribute", "manager",
               "boss", "king", "queen", "law", "bylaws", "sumo", "bloodline",
               "fleet", "supreme", "control", "rule", "judge", "weigh"}
WARMTH_WORDS = {"friend", "kind", "help", "care", "love", "home", "safe",
                "bow", "polite", "please", "thank"}
SPIKE_WORDS = {"flustered", "snap", "explode", "suddenly", "furious",
               "manic", "panic", "instantly", "spike"}

# misinterpretation -> signature emotion/cue (what criticism becomes)
MISINTERP_SIG = {
    "transaction": ("mock_indignant", "[frustrated]"),     # everything is a debt
    "conspiracy": ("sarcastic", "[sarcastic]"),            # everything is a plot
    "bureaucracy": ("deadpan", ""),                        # everything is procedure
    "politeness": ("deadpan", ""),                         # manners as armor
    "status": ("mock_indignant", "[frustrated]"),          # slights are structural
    "literal": ("manic", "[excited]"),                     # takes it literally, fast
    "nurtur": ("gleeful", "[delighted]"),
    "none": ("neutral", "[neutral]"),
}


def affect_from_graph(c: dict) -> dict:
    """Derive (arousal, valence, power) from the character graph text."""
    blob_parts = [
        c.get("misinterpretation_rule") or "",
        json.dumps(c.get("dramatic_core") or {}),
        json.dumps(c.get("philosophy") or {}),
        json.dumps(c.get("persona") or {}),
        c.get("vibe") or "",
    ]
    blob = " ".join(blob_parts).lower()
    words = set(re.findall(r"[a-z]+", blob))

    fear_hits = words & FEAR_WORDS
    power_hits = words & POWER_WORDS
    warm_hits = words & WARMTH_WORDS
    spike_hits = words & SPIKE_WORDS

    arousal = 0.5 + 0.06 * len(spike_hits) + 0.03 * len(fear_hits)
    valence = 0.1 + 0.08 * len(warm_hits) - 0.07 * len(fear_hits)
    power = 0.4 + 0.07 * len(power_hits)

    # vibe field as direct prior override (owner-authored shortcut)
    vibe = (c.get("vibe") or "").lower()
    VIBE_AFFECT = {"deadpan": (0.35, 0.0, 0.55), "manic": (0.9, 0.3, 0.8),
                   "gleeful": (0.7, 0.6, 0.5), "sad": (0.25, -0.6, 0.2),
                   "paranoid": (0.75, -0.6, 0.3), "smug": (0.5, 0.3, 0.8)}
    if vibe in VIBE_AFFECT:
        a, v, p = VIBE_AFFECT[vibe]
        arousal = (arousal + a) / 2
        valence = (valence + v) / 2
        power = (power + p) / 2

    return {"arousal": round(max(0.05, min(0.95, arousal)), 2),
            "valence": round(max(-0.9, min(0.9, valence)), 2),
            "power": round(max(0.05, min(0.95, power)), 2),
            "evidence": {"fear": sorted(fear_hits), "power": sorted(power_hits),
                         "warmth": sorted(warm_hits), "spike": sorted(spike_hits)}}


def signature_emotion(c: dict) -> tuple[str, str]:
    rule = (c.get("misinterpretation_rule") or "").lower()
    for key, sig in MISINTERP_SIG.items():
        if key in rule:
            return sig
    return ("neutral", "[neutral]")


def modulator_cycle(c: dict, affect: dict) -> list[str]:
    """The states contradictions push this character into (blind-spot engine)."""
    blind = " ".join((c.get("dramatic_core") or {}).get("blind_spots") or []).lower()
    cycle = []
    if affect["power"] > 0.65:
        cycle += ["smug", "drunk_on_power"]
    if affect["arousal"] > 0.7:
        cycle += ["manic"]
    if affect["valence"] < -0.2:
        cycle += ["paranoid", "angry"]
    if affect["power"] < 0.4:
        cycle += ["subservient", "exhausted"]
    if "dry" in blind or "deadpan" in blind:
        cycle.insert(0, "deadpan" if "deadpan" not in cycle else cycle[0])
    if not cycle:
        cycle = ["relaxed", "smug"]
    return list(dict.fromkeys(cycle))[:4]


def emerge(slug: str) -> dict:
    c = json.loads((REPO / "freaks" / slug / "character.json").read_text())
    affect = affect_from_graph(c)
    sig_emo, sig_cue = signature_emotion(c)
    cycle = modulator_cycle(c, affect)

    # MARY predictions (from the affect we derived)
    a11 = affect["arousal"] * 2 - 1
    v = affect["valence"]
    mary_rate = 0.5 * a11 + 0.2 * v
    mary_vol = round(3.3 * a11, 1)
    mary_dir = "falling" if v < -0.1 else ("rising" if v > 0.1 else "flat")

    # interview_style micro-texture
    style = ((c.get("persona") or {}).get("interview_style") or "").lower()
    pace_note = ("measured with micro-spikes" if "fluster" in style
                 else "rapid" if ("fast" in style or "rapid" in style)
                 else "measured")

    spec = {
        "slug": slug,
        "name": c.get("name"),
        "affect_derived": affect,
        "mary": {"pred_rate_delta": round(mary_rate, 2),
                 "pred_volume_db": mary_vol, "pitch_direction": mary_dir},
        "signature": {"emotion": sig_emo, "cue": sig_cue,
                      "from_misinterpretation": c.get("misinterpretation_rule")},
        "modulator_cycle": cycle,
        "delivery_spec": {
            "baseline_tempo": "fast" if mary_rate > 0.15 else (
                "slow" if mary_rate < -0.15 else "conversational"),
            "pace_texture": pace_note,
            "pitch_band": "wide" if affect["arousal"] > 0.7 else (
                "narrow" if affect["arousal"] < 0.4 else "mid"),
            "signature_recipe": None,  # filled from EMO_RECIPE by caller
            "starting_modulator": cycle[0],
        },
        "why": (f"fear={affect['evidence']['fear'] or '-'} power="
                f"{affect['evidence']['power'] or '-'} warmth="
                f"{affect['evidence']['warmth'] or '-'} spikes="
                f"{affect['evidence']['spike'] or '-'}"),
        "note": "delivery EMERGES from the character graph; comedians were "
                "only calibration for the mapping rules (MARY + archetypes)",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    outdir = HERE / "voicelab" / "emerged"
    outdir.mkdir(exist_ok=True)
    (outdir / f"{slug}.json").write_text(json.dumps(spec, indent=2))
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all:
        for d in sorted((REPO / "freaks").iterdir()):
            if (d / "character.json").exists():
                s = emerge(d.name)
                print(f"{s['name'][:36]:36} A={s['affect_derived']['arousal']} "
                      f"V={s['affect_derived']['valence']} P={s['affect_derived']['power']} "
                      f"sig={s['signature']['emotion']:14} tempo={s['delivery_spec']['baseline_tempo']}")
    elif args.slug:
        s = emerge(args.slug)
        print(json.dumps(s, indent=1))
    else:
        ap.error("give slug or --all")


if __name__ == "__main__":
    main()
