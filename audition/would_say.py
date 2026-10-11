"""Would-X-say-this — attribution classifier in persona space.

Noul per candidate persona ("would Ari say this?") + choice over the
roster. Evidence-backed: each verdict cites persona traits. Used for
analysis and audition gating, never for impersonation output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _p in ("/root/pogpet/backend",):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PERSONAS = Path("/root/characters/theory/killtony-personas")


def load_persona(pid: str) -> dict | None:
    for f in list(PERSONAS.glob("*.json")) + list(Path("/root/characters/theory/personas-outsiders").glob("*.json")):
        try:
            d = json.loads(open(f).read())
        except Exception:
            continue
        if d.get("id") == pid or f.stem == pid:
            return d
    if pid in ("no_nose_nolan", "nolan"):
        try:
            d = json.load(open("/root/pogpet/templates/characters/no_nose_nolan.json"))
            d["name"] = d.get("name", "No-Nose Nolan")
            return d
        except Exception:
            return None
    if pid in ("reptilian_ralph_middle_management", "ralph"):
        try:
            d = json.load(open("/root/characters/freaks/reptilian-ralph-middle-management/character.json"))
            d["name"] = d.get("name", "Ralph")
            d["humour"] = (d.get("persona") or {}).get("deal", "")
            return d
        except Exception:
            return None
    return None


def persona_brief(p: dict) -> str:
    dc = p.get("dramatic_core", {}) or {}
    return (f"{p.get('name')}: {p.get('humour', '')}. Wants {dc.get('want', '')}; "
            f"fears {dc.get('fear', '')}. Blind to {dc.get('blind_spots', '')}. "
            f"Leans {p.get('comedy', {}).get('operator_priors', '')}. "
            f"Threads: {p.get('threads', '')}"[:600])


def would_say(text: str, persona_ids: list[str]) -> dict | None:
    """Choice: whose mouth does this belong in + per-persona nouls."""
    profiles, briefs = {}, {}
    for pid in persona_ids:
        p = load_persona(pid)
        if not p:
            continue
        profiles[pid] = p
        briefs[pid] = persona_brief(p)
    if not profiles:
        return None
    q = {f"would_{pid}": {"type": "noul", "instructions":
                          f"Would this persona say this minute? {b}"}
         for pid, b in briefs.items()}
    q["best_fit"] = {"type": "choice", "instructions": "Whose mouth does this minute belong in?",
                     "criteria": {pid: briefs[pid][:150] for pid in briefs}}
    try:
        import jev as _j2
        ans = _j2.decide({"minute": text[:3000]}, q).get("answers", {})
    except Exception:
        return None
    out = {"fits": {}, "best": None, "chooser": "jev-1.13"}
    try:
        for pid in briefs:
            a = ans.get(f"would_{pid}", {})
            out["fits"][pid] = round(float(a.get("noul", 0.5)), 3) if isinstance(a, dict) else 0.5
        b = ans.get("best_fit", {})
        if isinstance(b, dict) and b.get("choice") in briefs:
            out["best"] = {"persona": b["choice"], "conf": round(float(b.get("confidence", 0)), 3)}
        return out
    except Exception:
        return None
