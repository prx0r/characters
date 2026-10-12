"""Stage contracts — renderer-agnostic Character Pack / World Seed / Performance Spec.

Rive, Wan, HappyOyster are all just performers of the same timeline.
The timeline is the asset; the renderer is interchangeable.

Contracts (all JSON-serializable, versioned):
- Rig: persistent puppet — expressions, gestures, mouth shapes, movement rules,
  plus a `rive` block mapping each control to a future .riv state/input.
  SVG fallback params ride along so Stage Lab performs TODAY.
- Stage: reusable venue — positions, lights, camera presets.
- Timeline (performance.v1): ordered timestamped events validated against
  final audio duration. Never overwrites delivery.json.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
RIGS = HERE / "rigs"
STAGES = HERE / "stages"
TIMELINE_SCHEMA = "performance.v1"

VALID_EVENT_KINDS = {
    "lights", "enter", "exit", "speak_start", "expression", "gesture",
    "look", "camera", "hold", "mouth", "sfx",
}


def load_rig(rig_id: str) -> dict | None:
    try:
        return json.loads((RIGS / f"{rig_id}.json").read_text())
    except Exception:
        return None


def load_stage(stage_id: str) -> dict | None:
    try:
        return json.loads((STAGES / f"{stage_id}.json").read_text())
    except Exception:
        return None


def list_rigs() -> list[dict]:
    out = []
    for p in sorted(RIGS.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            out.append({"rig_id": p.stem, "character_id": d.get("character_id"),
                        "name": d.get("name"), "gestures": list((d.get("gestures") or {})),
                        "expressions": list((d.get("expressions") or {}))})
        except Exception:
            pass
    return out


def list_stages() -> list[dict]:
    out = []
    for p in sorted(STAGES.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            out.append({"stage_id": p.stem, "name": d.get("name"),
                        "cameras": list((d.get("cameras") or {}))})
        except Exception:
            pass
    return out


def direct(audition: dict, rig: dict, stage: dict) -> dict:
    """Stage Director: approved beats + psychology + rig -> proposed events.

    Rules (from master brief, condensed):
    - motivation determines reactions; movement emphasizes, never distracts
    - punchlines earn stillness (hold), never a new gesture on top
    - character is unaware of the joke; director knows it
    - sparse gestures: max ~1 per 2 beats; Ralph moves less (profile.movement)
    - eye_glitch after punchline, suit_adjust on groan/tag, warm_rock_lean before closer
    - camera: wide -> medium, close-up only on glitch/reveal, push-in on closer
    """
    beats = audition.get("beats") or []
    dur = audition.get("audio_duration_ms") or 60000
    profile = (rig.get("profile") or {})
    move_cap = float(profile.get("movement", 0.5))
    gest_budget = max(2, int(len(beats) * (0.5 if move_cap < 0.4 else 0.75)))
    actions = rig.get("gestures") or {}

    events: list[dict] = [
        {"t": 0, "kind": "lights", "id": "house_up"},
        {"t": 400, "kind": "enter", "from": "stage_left"},
        {"t": 1300, "kind": "gesture", "id": "suit_adjust", "intensity": 0.4},
        {"t": 2000, "kind": "camera", "id": "medium"},
        {"t": 2000, "kind": "speak_start"},
    ]
    used = 1
    for b in beats:
        t0, t1 = int(b.get("start_ms", 0)), int(b.get("end_ms", 0))
        btype = b.get("type", "setup")
        if btype == "punchline":
            events.append({"t": t1, "kind": "hold", "ms": int(rig.get("punchline_hold_ms", 1200)),
                           "note": "stillness lets the laugh land"})
            if "eye_glitch" in actions and used < gest_budget + 2:
                events.append({"t": t1 + 400, "kind": "gesture", "id": "eye_glitch",
                               "intensity": 1.0, "beat": b.get("id")})
                used += 1
            events.append({"t": t1 + 900, "kind": "camera", "id": "closeup"})
            events.append({"t": t1 + 2200, "kind": "camera", "id": "medium"})
        elif btype in ("tag", "misdirect") and used < gest_budget:
            if "suit_adjust" in actions:
                events.append({"t": t0 + 300, "kind": "gesture", "id": "suit_adjust",
                               "intensity": 0.6, "beat": b.get("id")})
                used += 1
            events.append({"t": t0, "kind": "expression", "id": "annoyed", "beat": b.get("id")})
        elif btype == "closer":
            if "warm_rock_lean" in actions:
                events.append({"t": max(0, t0 - 800), "kind": "gesture", "id": "warm_rock_lean",
                               "intensity": 0.8, "beat": b.get("id")})
            events.append({"t": t0, "kind": "camera", "id": "pushin"})
            events.append({"t": t0, "kind": "expression", "id": "self_satisfied"})
        elif btype == "setup" and used < gest_budget:
            # sparse life: head_tilt OR look_audience, never both.
            # Stable content hash — Python hash() randomizes per process.
            import hashlib as _hl
            pick = "head_tilt" if int(_hl.md5(b.get("id", "").encode()).hexdigest(), 16) % 2 else "look_audience"
            if pick in actions or pick.startswith("look"):
                events.append({"t": t0 + 200, "kind": "gesture" if pick in actions else "look",
                               "id": pick, "intensity": 0.3, "beat": b.get("id")})
                used += 1
    events.append({"t": dur - 500, "kind": "camera", "id": "wide"})
    events.append({"t": dur, "kind": "exit", "to": "stage_left"})
    events.sort(key=lambda e: e["t"])
    mouth = _load_visemes(audition.get("id", ""))
    return {"schema": TIMELINE_SCHEMA, "audition_id": audition.get("id"),
            "character_id": audition.get("character_id"),
            "rig_id": rig.get("rig_id"), "rig_version": rig.get("version"),
            "stage_id": stage.get("stage_id"),
            "audio_duration_ms": dur,
            "delivery_hash": _hash_beats(beats),
            "mouth": mouth or {"source": "sine-fallback", "events": []},
            "events": [e for e in events if 0 <= e["t"] <= dur + 1000]}


def _load_visemes(aud_id: str) -> dict | None:
    """Vosk word->viseme track precomputed beside the audio (gitignored).
    Absent -> caller falls back. Never blocks directing."""
    try:
        p = HERE / "audio" / f"{aud_id}.visemes.json"
        if p.exists() and p.stat().st_size > 100:
            return {"source": "vosk", "events": json.loads(p.read_text())}
    except Exception:
        pass
    return None


def validate_timeline(tl: dict) -> list[str]:
    errs = []
    if tl.get("schema") != TIMELINE_SCHEMA:
        errs.append(f"schema must be {TIMELINE_SCHEMA}")
    dur = tl.get("audio_duration_ms") or 0
    if dur <= 0:
        errs.append("audio_duration_ms missing")
    for e in tl.get("events") or []:
        if e.get("kind") not in VALID_EVENT_KINDS:
            errs.append(f"bad event kind {e.get('kind')}")
        if not isinstance(e.get("t"), int) or e["t"] < 0 or e["t"] > dur + 1000:
            errs.append(f"event outside audio: {e}")
    return errs


def _hash_beats(beats: list) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(
        [{"id": b.get("id"), "type": b.get("type"), "text": b.get("text")} for b in beats]
    ).encode()).hexdigest()[:16]
