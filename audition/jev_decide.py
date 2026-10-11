"""Jev instance chooser — calibrated modulator/operator picks via TypeSafe.

Uses pogpet/backend/jev.py (pinned typesafe/jev-1.13, OpenRouter decisions).
No key -> returns None and the caller keeps the contextual-bandit logic.
Jev never writes jokes; it only picks from options we define, with confidence.
Needs OPENROUTER_API_KEY server-side (ask-first spend like every other call).
"""
from __future__ import annotations

import sys

for _p in ("/root/pogpet/backend", "/root/pogpet"):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def pick_modulator(state_text: str, options: list[str]) -> dict | None:
    """Choice over modulators. Returns {modulator, confidence, probabilities} or None."""
    try:
        import jev as _jev
    except Exception:
        return None
    try:
        answers = _jev.ask(
            {"scenario_and_history": state_text},
            {"modulator": {"type": "choice",
                           "instructions": "Which performance mood best serves this character in this scenario given the feedback history?",
                           "criteria": {o: o for o in options}}},
        )
    except Exception:
        return None
    try:
        m = answers["modulator"]
        choice = m.get("choice") if isinstance(m, dict) else m
        if choice not in options:
            return None
        probs = (m.get("probabilities") or {}) if isinstance(m, dict) else {}
        conf = (m.get("confidence") or 0) if isinstance(m, dict) else 0
        return {"modulator": choice, "confidence": round(float(conf), 3),
                "probabilities": probs, "chooser": "jev-1.13"}
    except Exception:
        return None


def theory_present(text: str, theory_id: str, hint: str) -> dict | None:
    """Noul: does this mechanism appear in the minute? For annotation passes."""
    try:
        import jev as _jev
    except Exception:
        return None
    try:
        answers = _jev.ask(
            {"minute": text[:3000]},
            {theory_id: {"type": "noul",
                         "instructions": f"Does the mechanism '{theory_id}' appear in this comedy minute? {hint}"}},
        )
        a = answers[theory_id]
        p = a.get("noul", 0.5) if isinstance(a, dict) else 0.5
        return {"theory": theory_id, "p": round(float(p), 3)}
    except Exception:
        return None


def decide_instance(state: dict, mod_options: list[str], mod_tilts: dict,
                    op_options: list[str], op_hyps: dict) -> dict | None:
    """One parallel Jev call for the whole instance lock.

    Returns {modulator, modulator_conf, operator, operator_conf,
             appraisal{}, vetoes{}, chooser} or None (no key/failure).
    Thresholds: choice needs conf>=0.6 else falls back per-field.
    """
    try:
        import jev_questions as _q
        import jev as _jev
    except Exception:
        return None
    questions = {}
    questions.update(_q.q_modulator(mod_options, mod_tilts))
    questions.update(_q.q_operator(op_options, op_hyps))
    questions.update(_q.q_appraisal())
    questions.update(_q.q_vetoes())
    try:
        answers = _jev.ask(state, questions)
    except Exception:
        return None
    out = {"chooser": "jev-1.13", "appraisal": {}, "vetoes": {}}
    try:
        m = answers.get("modulator", {})
        out["modulator"] = m.get("choice") if isinstance(m, dict) else None
        out["modulator_conf"] = round(float(m.get("confidence", 0)), 3) if isinstance(m, dict) else 0
        o = answers.get("operator", {})
        out["operator"] = o.get("choice") if isinstance(o, dict) else None
        out["operator_conf"] = round(float(o.get("confidence", 0)), 3) if isinstance(o, dict) else 0
        for k in ("status_threatened", "blind_spot_armed", "play_frame", "benign_ready"):
            a = answers.get(k, {})
            out["appraisal"][k] = round(float(a.get("noul", 0.5)), 3) if isinstance(a, dict) else 0.5
        for k in ("character_swappable", "generic_ai_humor", "reframe_present"):
            a = answers.get(k, {})
            out["vetoes"][k] = round(float(a.get("noul", 0.5)), 3) if isinstance(a, dict) else 0.5
        if out["modulator"] not in mod_options:
            out["modulator"] = None
        if out["operator"] not in op_options:
            out["operator"] = None
        return out
    except Exception:
        return None
