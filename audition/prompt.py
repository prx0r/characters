"""Prompt compiler — seed/system separation done right.

SYSTEM  = seed philosophy only (stable per seed_version). Never scenario,
          never prior jokes, never feedback text.
STYLE   = modulator performative layer (how the state speaks).
CONTEXT = instance: scenario + state + memories + operator priors (names
          only) + avoid-fingerprints (short hashes, not lines).
TASK    = JSON schema for beats + decision.

This is why the same seed survives any scenario: the system never learns
the scenario, and the scenario never rewrites the system.
"""
from __future__ import annotations

import hashlib
import json

PROMPT_VERSION = "prompt-v1"


def build_system(character: dict) -> str:
    raw = character.get("raw", {}) or {}
    phil = raw.get("philosophy", {}) or {}
    dc = raw.get("dramatic_core", {}) or {}
    sc = raw.get("self_concept", {}) or {}
    sm = raw.get("social_model", {}) or {}
    mot = raw.get("motivations", {}) or {}
    exp = raw.get("expression", {}) or {}
    lines = [
        f"You are {character.get('name')}. {character.get('deal', '')}",
        "Your philosophy (never violate; never mention as doctrine):",
        f"- Ontology: {phil.get('ontology', '')}",
        f"- Epistemology: {phil.get('epistemology', '')}",
        f"- Axiology: {phil.get('axiology', '')}",
        f"- Causality: {phil.get('causality', '')}",
        f"- Agency: {phil.get('agency', '')}",
        f"- You believe you are: {sc.get('identity', dc.get('self_model', ''))}",
        f"- Status orientation: {sm.get('status_orientation', '')}; authority: {sm.get('attitude_to_authority', '')}",
        f"- You seek {', '.join(mot.get('seeks', []))}; avoid {', '.join(mot.get('avoids', []))}",
        f"- Blind spots (you cannot see these; the audience can): {', '.join(character.get('blind_spots', []))}",
        f"- Misinterpretation rule (your core comic engine): {raw.get('misinterpretation_rule', '')}",
        f"- Register: {exp.get('default_register', '')}; restraint: {exp.get('emotional_restraint', '')}",
        f"- Awareness: {raw.get('awareness', 'unknown')} (unaware = unearned confidence, never wink)",
        "Rules: stay in worldview under any scenario; never break character to explain the joke;",
        "never repeat prior punchlines; the closer lands hardest and stays short.",
    ]
    return "\n".join(l for l in lines if l.strip())


def build_style(modulator: str, mod: dict) -> str:
    perf = (mod.get("performative", {}) or {})
    emo = (mod.get("emotional", {}) or {})
    cog = (mod.get("cognitive", {}) or {})
    energy = int(emo.get("arousal", 0.5) * 80)
    return (f"Current state: {modulator} (energy {energy}/80). {mod.get('tilt', '')} "
            f"Attention on {cog.get('attention', 'the situation')}. "
            f"Arousal {emo.get('arousal', 0.5)}. "
            f"Pace {'up' if perf.get('pace_delta', 0) > 0 else 'down'}, "
            f"pauses x{perf.get('pause_mult', 1.0)}. "
            f"Restraint interaction: {mod.get('restraint_interaction', '')}".strip())


def affinity_segment(set_number: int, familiarity: str = "") -> str:
    """Shikigami pattern: relationship depth modulates address.

    Set 3 Nolan talks different than set 30 Nolan — shared history exists.
    """
    n = max(1, int(set_number or 1))
    if n <= 2:
        return "No shared history yet: introduce yourself through the joke, earn every laugh."
    if n <= 10:
        return (f"Set {n}: the room half-knows you. Lean on one running thread; "
                f"do not explain old jokes. {familiarity}".strip())
    return (f"Set {n}: regulars present. Callback freely; subvert one expectation "
            f"they hold about you. {familiarity}".strip())


def tts_params(modulator: str, mod: dict) -> dict:
    """Modulator -> edge-tts params. Pace from performative, pitch by arousal."""
    perf, emo = (mod.get("performative", {}) or {}), (mod.get("emotional", {}) or {})
    pace = perf.get("pace_delta", 0)
    rate = "slow" if pace <= -0.1 else ("fast" if pace >= 0.1 else "normal")
    pitch = "+0Hz"
    if emo.get("arousal", 0.5) >= 0.75:
        pitch = "+40Hz"
    elif emo.get("arousal", 0.5) <= 0.3:
        pitch = "-30Hz"
    return {"rate": rate, "pitch": pitch, "modulator": modulator}


def build_context(scenario: dict, state: dict, memories: list[str],
                  operators: list[str], avoid: str, critique: str) -> str:
    return (f"Tonight's situation ({scenario.get('id')}): "
            f"{(scenario.get('comic_model') or scenario.get('comic_claim') or '')[:300]}\n"
            f"Your state: {json.dumps(state)[:400]}\n"
            f"Living memory (fictional, may callback): {'; '.join(memories[-3:]) or 'none yet'}\n"
            f"Licensed mechanisms (use these, not others): {', '.join(operators)}\n"
            f"Do not repeat these beats:\n{avoid[:600]}\n"
            f"Audience note to honor: {critique[:200]}".strip())


def build_task() -> str:
    return ("Return strict JSON: {scenario_summary, character_decision "
            "{appraisal, chosen_goal, reaction, emotional_shift}, "
            "change_from_last, beats:[{id,type,text,pause_after_ms,emphasis}]}. "
            "6 beats (setup/setup/misdirect-or-escalation/punchline/tag-or-callback/closer), "
            "130-150 words total, opener IS a joke (no throat-clearing), closer under 8 words.")


def compile(character: dict, scenario: dict, state: dict, memories: list[str],
            modulator: str, mod: dict, operators: list[str],
            avoid: str, critique: str) -> tuple[list[dict], str]:
    """Returns (messages, prompt_version_hash)."""
    messages = [
        {"role": "system", "content": build_system(character)},
        {"role": "user", "content": build_style(modulator, mod) + "\n\n"
         + build_context(scenario, state, memories, operators, avoid, critique)
         + "\n\n" + build_task()},
    ]
    h = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:12]
    return messages, f"{PROMPT_VERSION}-{h}"
