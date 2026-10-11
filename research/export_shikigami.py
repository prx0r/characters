#!/usr/bin/env python3
"""Seed -> Shikigami profile exporter (one-way, our words).

AGPL boundary: reads OUR graphs, writes THEIR JSON shape. No Shikigami
code imported, nothing copied. Our seed stays canonical; the export is
a runtime costume for their engine.

Covers: base_prompt (3 layers from philosophy), style_constraint (from
expression), emotion_config (modulators -> energy/emotion prompts),
memory_config (facts cap, extraction cadence). Comedy-only fields
(misinterpretation_rule, operator priors, KT evidence) ride in
_comedy_sidecar, ignored by their engine, preserved for ours.

Run: python3 /root/characters/research/export_shikigami.py <character_id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_seed(character_id: str) -> dict:
    if character_id in ("reptilian_ralph_middle_management", "ralph"):
        return json.load(open("/root/characters/freaks/reptilian-ralph-middle-management/character.json"))
    if character_id in ("no_nose_nolan", "nolan"):
        d = json.load(open("/root/pogpet/templates/characters/no_nose_nolan.json"))
        d["name"] = d.get("name", "No-Nose Nolan")
        return d
    p = Path(f"/root/characters/theory/killtony-personas/{character_id}.json")
    if p.exists():
        return json.loads(p.read_text())
    raise SystemExit(f"unknown character {character_id}")


def convert(s: dict) -> dict:
    phil = s.get("philosophy", {}) or {}
    dc = s.get("dramatic_core", {}) or {}
    exp = s.get("expression", {}) or {}
    mods = {}
    try:
        mods = json.load(open("/root/characters/audition/modulators.json"))
    except Exception:
        pass
    emotion_prompts = {}
    for m, spec in mods.items():
        emo = (spec.get("emotional", {}) or {})
        emotion_prompts[m] = (f"{spec.get('tilt', '')} "
                              f"Arousal {emo.get('arousal', 0.5)}. "
                              f"{spec.get('restraint_interaction', '')}".strip())
    return {
        "profile_id": s.get("id", "unknown"),
        "display_name": s.get("name", "Unknown"),
        "base_prompt": {
            "surface": f"You are {s.get('name')}. {(s.get('persona') or {}).get('deal', s.get('humour', ''))}",
            "underneath": " ".join(f"{k}: {v}" for k, v in phil.items())[:800],
            "deepest": (f"Wants {dc.get('want', '')}; fears {dc.get('fear', '')}. "
                        f"Blind to {dc.get('blind_spots', '')}. Doctrine stays offstage."),
        },
        "style_constraint": {
            "register": exp.get("default_register", ""),
            "restraint": exp.get("emotional_restraint", ""),
            "rules": ["stay in worldview under any scenario",
                      "never break character to explain the joke"],
        },
        "emotion_config": {
            "default_state": "relaxed",
            "energy_prompts": {"0": "Spent. Minimal output; listen.",
                               "40": "Steady. Normal warmth and restraint.",
                               "80": "Lit. Expansive, indiscreet, leaks the quiet part."},
            "emotion_prompts": emotion_prompts,
        },
        "memory_config": {"enabled": True, "extraction_frequency": 5,
                          "max_facts_in_prompt": 8,
                          "note": "facts are fictional-world events; audience metrics never enter memory"},
        "_comedy_sidecar": {
            "misinterpretation_rule": s.get("misinterpretation_rule", ""),
            "operator_priors": ((s.get("comedy") or {}).get("operator_priors", {})),
            "preferred_theories": s.get("preferred_theories", []),
            "provenance": "prx0r/characters seed; Shikigami engine ignores this block",
        },
        "_license_note": "export shape only; no AGPL code embedded or imported",
    }


def main():
    cid = sys.argv[1] if len(sys.argv) > 1 else "reptilian_ralph_middle_management"
    out = Path(f"/root/characters/theory/shikigami-exports/{cid}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(convert(load_seed(cid)), indent=1, ensure_ascii=False))
    print(f"exported {out}")


if __name__ == "__main__":
    main()
