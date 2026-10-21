"""Sealed-set exporter: delivery_engine render -> freaktown sealed-set.v1.

Contract: freaktown packages/stage-runtime/src/plan/setAdapter.ts
  set.wav          timing authority = this render (FT-03 analogue)
  timeline.json    [{beat_id,type,start_ms,dur_ms,end_ms,pause_*_ms,text,performance}]
  mouth_cues.json  [{start_ms,end_ms,shape:"open"}] — energy envelope of set.wav
                   (honest label: derived, not forced-aligned)
  set_plan.json    {character_id, mesh, premise, delivery:{profile,beats}}

Timing rule mirrors assemble_audio: gap = max(pause_before, prev pause_after);
speech = per-beat rendered duration (ffprobe). Trailing = last pause_after.

Mesh lookup: freaks/mesh-map.json (mesh null -> "" -> stage appearance
fallback). Performance per beat: mechanism -> expression, character actions
(after_punchline/on_laugh/after_setup) -> gesture/look.

Usage: driven by delivery_engine --seal DIR (needs post-render beats).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
FREAKS = HERE.parent / "freaks"
MESH_MAP = FREAKS / "mesh-map.json"

# mechanism -> stage face intent (setAdapter EXPRESSION_ACTION vocabulary)
MECH_EXPR = {
    "deadpan": "deadpan", "misdirection": "smug", "escalation": "annoyed",
    "callback": "smile", "self_deprecation": "frown",
    "status_reversal": "annoyed", "displacement": "frown",
}
# character action face -> stage expression (stage vocab: deadpan/smug/smile/
# annoyed/surprised/frown/disgusted); character face beats mechanism default
FACE_EXPR = {"neutral": "deadpan", "deadpan": "deadpan", "grin": "smile",
             "smile": "smile", "frown": "frown", "annoyed": "annoyed",
             "smug": "smug", "surprised": "surprised", "disgusted": "disgusted"}
# character action body -> stage gesture (gesture "hold" -> locomotion.freeze)
BODY_GESTURE = {"hold still": "hold", "shrug": "shrug", "point": "point",
                "wave": "wave", "open": "open"}
TYPE_MAP = {"opener": "setup", "setup": "setup", "punchline": "punchline",
            "closer": "closer", "tag": "tag"}


def mesh_for(slug: str) -> str:
    if not MESH_MAP.exists():
        return ""
    try:
        entry = json.loads(MESH_MAP.read_text()).get("map", {}).get(slug) or {}
        return entry.get("mesh") or ""
    except Exception:
        return ""


def _mouth_spans(wav: Path) -> list[dict]:
    """Energy envelope of set.wav -> voiced spans (10ms frames, >=80ms runs)."""
    import numpy as np
    with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav),
                        "-ac", "1", "-ar", "16000", "-f", "s16le", tmp.name],
                       capture_output=True, timeout=180, check=True)
        raw = Path(tmp.name).read_bytes()
    a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    win = 160  # 10ms
    if len(a) < win * 4:
        return []
    n = len(a) // win
    rms = np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(axis=1))
    thr = max(0.01, float(rms.max()) * 0.12)
    spans: list[dict] = []
    start = None
    for i, v in enumerate(rms > thr):
        if v and start is None:
            start = i
        elif not v and start is not None:
            s, e = start * 10, i * 10
            if e - s >= 80:
                spans.append({"start_ms": s, "end_ms": e, "shape": "open"})
            start = None
    if start is not None:
        s, e = start * 10, len(rms) * 10
        if e - s >= 80:
            spans.append({"start_ms": s, "end_ms": e, "shape": "open"})
    return spans


def _performance(beat: dict, actions: dict, flat: bool) -> dict:
    mech = beat.get("mechanism", "")
    bt = beat["beat_type"]
    expr = MECH_EXPR.get(mech)
    if expr is None:
        expr = ("deadpan" if flat
                else ("smile" if bt in ("setup", "opener", "closer") else "smug"))
    gesture = look = None
    face = None
    for act in (actions or {}).values():
        trig = (act.get("trigger") or "").lower()
        body = (act.get("body") or "").lower()
        g = BODY_GESTURE.get(body)
        if trig == "after_punchline" and bt in ("punchline", "closer", "tag"):
            gesture = gesture or g
            face = face or FACE_EXPR.get((act.get("face") or "").lower())
        elif trig == "on_laugh" and beat.get("p_laugh", 0) > 0.5:
            gesture = gesture or g
        elif trig == "after_setup" and bt in ("setup", "opener"):
            if body.startswith("look"):
                look = look or body.split()[-1]
            else:
                gesture = gesture or g
    perf = {"expression": face or expr}
    if gesture:
        perf["gesture"] = gesture
    if look:
        perf["look"] = look
    return perf


def seal(beats: list[dict], profile: dict, character: dict | None,
         slug: str, audio_path: Path, outdir: Path) -> dict:
    """Write the sealed set bundle. beats: post-render (have _rendered)."""
    import hashlib
    character = character or {}
    actions = character.get("actions") or {}
    flat = (profile.get("volume_db") or 0) <= -2
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    shutil.copy(audio_path, outdir / "set.wav")

    timeline: list[dict] = []
    plan_beats: list[dict] = []
    cursor = 0  # ms
    prev_after = 0.0  # s
    n = 0
    for b in beats:
        r = b.get("_rendered")
        if not r:
            continue
        gap_s = max(b.get("pause_before", 0.5), prev_after)
        start = cursor + int(round(gap_s * 1000))
        dur = int(r["duration_ms"])
        end = start + dur
        n += 1
        bid = f"b{n}"
        perf = _performance(b, actions, flat)
        timeline.append({
            "beat_id": bid,
            "type": TYPE_MAP.get(b["beat_type"], b["beat_type"]),
            "start_ms": start, "dur_ms": dur, "end_ms": end,
            "pause_before_ms": int(round(b.get("pause_before", 0) * 1000)),
            "pause_after_ms": int(round(b.get("pause_after", 0) * 1000)),
            "text": b["text"],
            "performance": perf,
        })
        plan_beats.append({"id": bid, "performance": perf})
        cursor = end
        prev_after = b.get("pause_after", 0.0)

    duration_ms = cursor + int(round(prev_after * 1000))
    prof = character.get("profile") or {}
    set_plan = {
        "character_id": slug,
        "mesh": mesh_for(slug),
        "premise": character.get("premise", ""),
        "delivery": {
            "profile": {"energy": prof.get("energy", 0.6),
                        "pace": prof.get("pace", 1.0),
                        "style": (character.get("delivery") or {}).get("style", "")},
            "beats": plan_beats,
        },
        "built_from": {"delivery_engine": Path(audio_path).name,
                       "seal": hashlib.sha256(Path(audio_path).read_bytes()).hexdigest()[:16]},
    }

    (outdir / "timeline.json").write_text(json.dumps(timeline, indent=1))
    (outdir / "mouth_cues.json").write_text(json.dumps(_mouth_spans(Path(outdir / "set.wav")), indent=1))
    (outdir / "set_plan.json").write_text(json.dumps(set_plan, indent=1))
    return {"outdir": str(outdir), "beats": n, "duration_ms": duration_ms,
            "mesh": set_plan["mesh"]}
