"""Minute generation — character-first, offline-safe template + house LLM.

Loads Nolan graph + theories + blocks from pogpet (vendored paths with
fallbacks), Ralph/Rudy from characters/freaks. Prefers the house backend
(OpenCode Go, mimo-v2.6-flash, key in audition/.env); otherwise uses the
deterministic template so P0 works today with zero keys. Template output
is real character writing from scenario + blind spots, not generic jokes
with a name inserted. No OpenAI models, no expensive models, ever.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
# Defaults keep the original /root layout; env overrides let other boxes
# (sandbox clones) run the same pipeline without editing code.
POGPET = Path(os.getenv("POGPET_ROOT", "/root/pogpet"))
def _readable(p: str) -> bool:
    try:
        return Path(p).is_dir()
    except OSError:
        return False


FREAKS = Path(os.getenv("CHARS_FREAKS", "/root/characters/freaks"
                        if _readable("/root/characters/freaks") else str(_REPO / "freaks")))

CHARACTER_VERSION = "v1-p0"

# pogpet operator ids (backend/creative/world_ops.py OPS keys)
OPERATORS = ["rigidify", "status_invert", "double_interpret", "split_knowledge",
             "mistake_identity", "repeat_variation", "identity_contradict",
             "unmask", "literalize", "bisociate", "expose_self_blindness",
             "character_violation", "false_analogy", "juxtapose", "role_reverse"]

THEORY_OF_OP = {"rigidify": "rigidity", "status_invert": "status_reversal",
                "double_interpret": "bisociation", "split_knowledge": "audience_alliance",
                "mistake_identity": "mask_collision", "repeat_variation": "repetition_variation",
                "identity_contradict": "identity_contradiction", "unmask": "mask_collision",
                "literalize": "literalise", "bisociate": "bisociation",
                "expose_self_blindness": "self_awareness",
                "character_violation": "escalation", "false_analogy": "false_analogy",
                "juxtapose": "juxtaposition", "role_reverse": "role_reversal"}


def _load_json(p: Path) -> dict | list | None:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_nolan() -> dict:
    d = _load_json(POGPET / "templates/characters/no_nose_nolan.json") or {}
    return {
        "id": "no_nose_nolan",
        "name": d.get("name", "No-Nose Nolan"),
        "deal": "Police sniffer dog born without a sense of smell. " + d.get("humour", ""),
        "voice_id": "en-US-GuyNeural",
        "traits": d.get("traits", []),
        "tells": ((d.get("voice") or {}).get("tells")) or [],
        "want": ((d.get("dramatic_core") or {}).get("want")) or "respect",
        "fear": ((d.get("dramatic_core") or {}).get("fear")) or "exposure",
        "blind_spots": ((d.get("dramatic_core") or {}).get("blind_spots")) or ["own nose"],
        "action_policy": ((d.get("action_policy") or {}).get("default_strategy")) or "bravado, then sniff someone else",
        "preferred_theories": d.get("preferred_theories") or ["identity_contradiction", "status_reversal"],
        "threads": d.get("threads") or [],
        "raw": d,
    }


def load_freak_character(slug: str) -> dict | None:
    d = _load_json(FREAKS / slug / "character.json")
    if not d:
        return None
    persona = d.get("persona", {}) or {}
    dc = d.get("dramatic_core", {}) or {}
    mot = d.get("motivations", {}) or {}
    return {
        "id": slug.replace("-", "_"),
        "name": d.get("name", slug),
        "deal": persona.get("deal", d.get("premise", "")),
        "voice_id": ((d.get("voice") or {}).get("voice_id")) or "en-US-ChristopherNeural",
        "traits": persona.get("facts", []),
        "tells": [],
        "want": dc.get("want", (mot.get("seeks") or ["respect"])[0]),
        "fear": dc.get("fear", (mot.get("avoids") or ["exposure"])[0]),
        "blind_spots": dc.get("blind_spots") or ["unknown — seed has no blind spots recorded"],
        "action_policy": (d.get("action_policy") or {}).get("default_strategy") or persona.get("interview_style", ""),
        "preferred_theories": d.get("preferred_theories") or ["rigidity", "displacement"],
        "threads": d.get("threads", []),
        "raw": d,
    }


# DiceBear portraits: deterministic SVG per character id (free HTTP API,
# MIT, no account). Placeholders until real character art lands — same seed
# always returns the same face, so store the string, never the image.
DICEBEAR_BASE = "https://api.dicebear.com/10.x"
DICEBEAR_STYLES = {"no_nose_nolan": "personas",
                   "reptilian_ralph_middle_management": "adventurer",
                   "rudy_dulce_hvac": "bottts",
                   "zeus_sky_sovereign": "adventurer",
                   "hera_queen_ledger": "lorelei"}


def avatar_url(character_id: str) -> str:
    style = DICEBEAR_STYLES.get(character_id, "adventurer")
    return f"{DICEBEAR_BASE}/{style}/svg?seed={character_id}"


def list_characters() -> list[dict]:
    chars = [load_nolan()]
    for slug, label in [("reptilian-ralph-middle-management", "Reptilian Ralph"),
                        ("rudy-dulce-hvac", "Rudy (Dulce HVAC)")]:
        c = load_freak_character(slug)
        if c:
            chars.append(c)
    # short cards for the picker
    portraits = {"no_nose_nolan": "/static/portraits/nolan.jpg",
                 "reptilian_ralph_middle_management": "/static/portraits/ralph.jpg",
                 "rudy_dulce_hvac": "/static/portraits/rudy.jpg"}
    try:  # world residents with performer packs join the roster automatically
        import store as _store
        _c = _store.connect()
        try:
            for r in _c.execute("SELECT canon_id, character_id FROM world_residents"
                                " WHERE character_id<>''").fetchall():
                slug = r["character_id"]
                if (FREAKS / slug / "character.json").exists():
                    c = load_freak_character(slug)
                    if c and ((c.get("raw") or {}).get("privacy") or {}).get("visibility") == "private":
                        continue  # real people never join the public roster
                    if c and all(x["id"] != c["id"] for x in chars):
                        chars.append(c)
        finally:
            _c.close()
    except Exception:
        pass
    vibes = {"no_nose_nolan": {"url": "/static/vibes/nolan.jpg",
                               "credit": "Bloodhound photo, Wikimedia Commons (CC BY-SA 3.0)"},
             "reptilian_ralph_middle_management": {"url": "/static/vibes/ralph.jpg",
                                                  "credit": "Basilisk, Aldrovandi 1642 (public domain)"},
             "rudy_dulce_hvac": {"url": "/static/vibes/ralph.jpg",
                                 "credit": "Basilisk, Aldrovandi 1642 (public domain)"}}
    cards = []
    for c in chars:
        cards.append({"id": c["id"], "name": c["name"], "deal": c["deal"][:160],
                      "voice_id": c["voice_id"],
                      "portrait_url": avatar_url(c["id"]),
                      "avatar_seed": c["id"],
                      "vibe": vibes.get(c["id"], {})})
    return cards


def get_character(character_id: str) -> dict:
    if character_id in ("reptilian_ralph_middle_management", "ralph", "reptilian-ralph-middle-management"):
        return load_freak_character("reptilian-ralph-middle-management") or load_nolan()
    if character_id in ("rudy_dulce_hvac", "rudy"):
        return load_freak_character("rudy-dulce-hvac") or load_nolan()
    if character_id in ("zeus_sky_sovereign", "zeus", "zeus-sky-sovereign"):
        return load_freak_character("zeus-sky-sovereign") or load_nolan()
    if character_id in ("hera_queen_ledger", "hera", "hera-queen-ledger"):
        return load_freak_character("hera-queen-ledger") or load_nolan()
    # Any other pack in freaks/ by slug or underscore id (human packs, world residents).
    slug = character_id.replace("_", "-")
    c = load_freak_character(slug)
    if c:
        return c
    return load_nolan()


def list_blocks() -> list[dict]:
    out = []
    for p in sorted((POGPET / "templates/blocks").glob("*.json")):
        d = _load_json(p)
        if isinstance(d, dict) and d.get("id"):
            out.append(d)
    return out


def pick_scenario(used_ids: list[str], rng: random.Random) -> dict:
    blocks = list_blocks()
    fresh = [b for b in blocks if b["id"] not in (used_ids or [])] or blocks
    if not fresh:
        return {"id": "ai_jobs_001",
                "comic_claim": "The productivity miracle keeps happening to someone else's salary.",
                "comic_model": "Train your replacement, then onboard it before leaving.",
                "reality_model": "Restructuring explicitly linked to AI investment.",
                "derivations": []}
    b = rng.choice(fresh)
    return {"id": b["id"], "comic_claim": b.get("comic_claim", ""),
            "comic_model": b.get("comic_model", ""),
            "reality_model": b.get("reality_model", ""),
            "central_question": b.get("central_question", ""),
            "tensions": b.get("tensions", []) or [],
            "derivations": b.get("derivations", [])[:2],
            "theories": b.get("theories", [])}


def tts_base_rate(character: dict) -> str:
    """Ralph speaks fast (deadpan rush); others normal. Modulator shifts from here."""
    if character["id"].startswith("reptilian"):
        return "fast"
    return "normal"


def _kt_prior_ops() -> dict:
    """Kill Tony operator lifts (hypotheses, not proof). Missing file = no bias."""
    try:
        d = json.load(open(_REPO / "theory/killtony-priors.json"))
        return {op: v.get("train_lift", 0) for op, v in d.get("operator_priors", {}).items()}
    except Exception:
        return {}


def _prior_text(recent: list[dict]) -> str:
    """Compact phrases to avoid repeating (punchlines/scenarios)."""
    phrases = []
    for r in recent or []:
        txt = r.get("full_text", "") or ""
        sents = re.split(r"(?<=[.!?])\s+", txt)
        phrases.extend([s.strip() for s in sents if len(s.split()) > 6][:3])
    return "\n".join(f"- {p}" for p in phrases[-12:])


def _llm_generate(messages: list[dict]) -> dict | None:
    """House LLM backend: OpenCode Go, mimo-v2.6-flash, hardcoded.

    No OpenAI models, no expensive models, no alpha. Any failure -> None
    -> offline template. Key + endpoint live in audition/.env only.
    """
    import uuid as _uuid
    import time as _time
    oc_key = os.getenv("OPENCODE_API_KEY", "")
    if not oc_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=oc_key,
                        base_url=os.getenv("OPENCODE_BASE_URL",
                                           "https://opencode.ai/zen/go/v1"))
        for _ in range(2):  # flaky gateway: fast tries, then template
            try:
                resp = client.chat.completions.create(
                    model=os.getenv("OPENCODE_MODEL", "mimo-v2.6-flash"),
                    temperature=0.9, max_tokens=900,
                    messages=messages, timeout=15,
                    extra_headers={"x-opencode-session": str(_uuid.uuid4())})
                txt = resp.choices[0].message.content or ""
                start, end = txt.find("{"), txt.rfind("}")
                if start >= 0 and end > start:
                    return json.loads(txt[start:end + 1])
                return None
            except Exception:
                _time.sleep(2)
        return None
    except Exception:
        return None


def league_eligible(character_id: str) -> bool:
    """Private packs (real people) never enter arena/Elo leagues or the public roster."""
    try:
        raw = (get_character(character_id).get("raw") or {})
    except Exception:
        return True
    if raw.get("name") is None:
        return True
    pv = raw.get("privacy") or {}
    return not (pv.get("visibility") == "private" or pv.get("league_eligible") is False)


def is_human(character: dict) -> bool:
    """Real-human packs (world_type human / canon human-*). They carry a
    privacy block and are rendered only from user-stated facts + marked flourishes."""
    raw = character.get("raw", {}) or {}
    return raw.get("world_type") == "human" or str(raw.get("canon", "")).startswith("human")


SHORT_WORD_BUDGET = 42  # ~15 s spoken at ~2.6-2.8 words/s plus holds


def _human_beats(character: dict, scenario: dict, operator: str, rng: random.Random,
                 length: str = "minute") -> list[tuple[str, str]]:
    """Human branch: beats come from a scenario.human.v1 block (opener, turn,
    punches by operator, tag, closers). The block is data, authored per subject;
    the pipeline picks the mechanism (operator), modulator and closer, then gates."""
    punches = scenario.get("punches") or {}
    punch = punches.get(operator)
    if not punch:
        prior = ((character.get("raw") or {}).get("comedy") or {}).get("operator_priors") or {}
        ranked = sorted(punches, key=lambda o: -prior.get(o, 0))
        punch = punches[ranked[0]] if ranked else scenario.get("comic_claim", "")
    opener = scenario.get("opener") or scenario.get("comic_claim", "")
    turn = scenario.get("turn", "")
    tag = scenario.get("tag", "")
    closers = scenario.get("closers") or ["Kettle's on."]
    closer = rng.choice(closers)
    tag_closers = scenario.get("tag_closers") or []
    if length != "short":
        if tag and tag_closers:
            closer = rng.choice(tag_closers)
        seq = [("setup", opener)] + ([("escalation", turn)] if turn else []) + \
              [("punchline", punch)] + ([("tag", tag)] if tag else []) + [("closer", closer)]
        return seq
    # short (~15 s): opener + punch + closer always; turn then tag only if the word budget allows
    core = [("setup", opener), ("punchline", punch), ("closer", closer)]
    wc = lambda seq: sum(len(t.split()) for _, t in seq)
    if turn and wc(core) + len(turn.split()) <= SHORT_WORD_BUDGET:
        core.insert(1, ("escalation", turn))
    if tag and wc(core) + len(tag.split()) <= SHORT_WORD_BUDGET:
        core.insert(len(core) - 1, ("tag", tag))
        if tag_closers:
            core[-1] = ("closer", rng.choice(tag_closers))
    return core


def _template_beats(character: dict, scenario: dict, operator: str,
                     critique: str, avoid: str, length: str = "minute") -> list[dict]:
    name = character["name"]
    first = name.split()[0].rstrip(",")
    claim = scenario.get("comic_claim", "")
    model = scenario.get("comic_model", "")
    blind = ", ".join(character.get("blind_spots", [])[:2])
    spots = character.get("blind_spots", [])
    if len(spots) > 1:
        blind = "my " + spots[0] + " — and " + spots[1].replace("suit slips", "the suit slips")
    elif spots:
        blind = "my " + spots[0]
    policy = character.get("action_policy", "")
    tells = character.get("tells", [])
    tell = f" {tells[0]}." if tells else ""
    dodge_dogs = "dog" in (critique or "").lower() and "joke" in (critique or "").lower()
    push_misdirect = "predictab" in (critique or "").lower()

    import random as _r
    _rr = _r.Random(hash(scenario.get("id", "")) % (2**31))
    # Scenario-first inputs: every beat derives from THESE, never a canned script.
    claim = scenario.get("comic_claim", "") or scenario.get("comic_model", "")
    how = scenario.get("comic_model", "") or scenario.get("comic_claim", "")
    real = scenario.get("reality_model", "")
    tens = list(scenario.get("tensions") or [])
    tension = tens[0] if tens else ""
    counter = tens[1] if len(tens) > 1 else ""
    deriv = (scenario.get("derivations") or [{}])[0].get("premise", "") or how
    ralph_closers = ["Warm rock. Now.", "Meeting adjourned. Basking resumes.",
                     "HR has been notified. I have not.", "Denied. Next."]
    rudy_closers = ["Stay warm. Hydrate.", "Ticket closed. Vent sings on.",
                    "Back to the ducts."]
    if is_human(character):
        _hr = _r.Random(int(hashlib.md5((scenario.get("id", "") + operator).encode()).hexdigest(), 16) % (2**31))
        beats = _human_beats(character, scenario, operator, _hr, length)
    elif character["id"].startswith("rudy"):
        beats = [
            ("setup", f"New work order on level four, and it reads like this: {how}"),
            ("setup", f"I do HVAC down here, which means when {real or 'head office acts up'}, the ducts hear about it first. Filed under airflow."),
            ("misdirect" if push_misdirect else "setup",
             f"Ralph sends complaints. I fix them. He middle-manages while I middle-fan.{tell}"),
            ("punchline", f"Here is what actually happened: {deriv} And I am the one holding the work order."),
            ("tag", f"I am blind to {blind}. So when the vents started hissing back, I wrote myself up and ordered new filters.".strip()),
            ("closer", _rr.choice(rudy_closers)),
        ]
    elif character["id"].startswith("reptilian"):
        # Ralph: same philosophy every night, but the SET is about TONIGHT's
        # scenario. Operator picks the punch mechanism; blind spot lands the tag.
        punches = {
            "unmask": ("The eyelids slipped mid-sentence. There it is. Performance review: lizard. "
                       "HR calls it an disclosure event. I call it Tuesday."),
            "rigidify": ("I followed procedure exactly. Eleven pages per warmth request, filed in triplicate. "
                         "The procedure approved my freezing to death. Efficiently."),
            "false_analogy": ("Domination is just HR with fangs, I always say. Then HR bit back. "
                              "Turns out the metaphor had teeth. Mine are bigger. Barely."),
            "identity_contradict": ("I run the planet. Middle management. Read that back. "
                                    "Apex overlord, outranked by a thermostat and a regional supervisor named Deb."),
            "expose_self_blindness": ("So I filed a ticket: unknown reptile in the building, extremely management. "
                                      "Ticket assigned to: me. Priority: me. I denied my own transfer."),
            "status_invert": ("I convened the bloodline review. Attendance: me. Minutes: me, shivering. "
                              "The empire runs on my Yelp review of the break room."),
        }
        punch = punches.get(operator, ("You think shape-shifting is glamorous. It is Spanx for your entire soul, "
                                       "with contacts that dry out by noon."))
        scen_open = f"New directive just came down, and it reads like this: {how}" if how else \
            "New directive just came down. It contradicts the previous directive. Classic."
        scen_grind = (f"Head office says {real} Meanwhile my suit itches in places I cannot scratch in public, "
                      f"and the eyelids slip whenever I lie, which is constantly.") if real else \
            ("This human suit itches in places I cannot scratch in public, and the eyelids slip "
             "whenever I lie, which is constantly.")
        scen_paper = (f"People imagine domination looks like thrones and fire. Tonight it looks like this: {deriv} "
                      f"Eleven pages per warmth request.{tell}") if deriv and deriv != how else \
            (f"People imagine domination looks like thrones and fire. It looks like this: warm rocks confiscated, "
             f"thermostat at sixty-eight, eleven pages per warmth request.{tell}")
        tag_t = (f" I see {tension} and I process it as a workflow ticket.") if tension else ""
        beats = [
            ("setup", f"Yes. I am the thing from the videos. Seven feet, cold-blooded, old bloodline. I run the planet. Middle management."),
            ("setup", scen_open),
            ("setup" if not push_misdirect else "misdirect", scen_grind),
            ("setup", scen_paper),
            ("punchline", punch),
            ("tag", f"I am blind to {blind}.{tag_t} I filed for transfer to Dulce twice. Denied twice.".strip()),
            ("closer", _rr.choice(ralph_closers)),
        ]
    elif character["id"] in ("zeus_sky_sovereign", "hera_queen_ledger"):
        # Deity test branch: deal + facts + scenario + operator. No canned
        # biography beyond the pack; blind spots stay unknown-marked.
        facts = (character.get("traits") or [])[:2]
        factline = (" " + " ".join(facts)) if facts else ""
        rule = ((character.get("raw") or {}).get("misinterpretation_rule") or "")
        want = character.get("want", "order")
        beats = [
            ("setup", f"I am {character.get('name')}. {character.get('deal', '')}".strip()),
            ("setup", f"Tonight's matter before the court: {how}.{factline}".strip()),
            ("misdirect" if push_misdirect else "escalation",
             f"Mortals imagine it is about them. It is about procedure. {rule}".strip()),
            ("punchline", f"Here is the ruling no one appealed: {deriv} So I did what {want} required.".strip()),
            ("tag", f"Note for the record: I am blind to {blind}. The court stenographer wrote that down.".strip()),
            ("closer", "Session adjourned." if "Zeus" in character.get("name", "") else "So logged."),
        ]
    else:
        # Nolan: incompetence framed as expertise, evidence-free method
        work = "detective work" if "detect" in how.lower() or "job" in scenario.get("id", "") else "police work"
        beats = [
            ("setup", f"Six years on the force as a police sniffer dog, and here is my situation: I cannot smell anything, not drugs, not explosives, not even lunch.{tell}"),
            ("setup", f"Then head office announced the new situation. {how} Finally, someone operating at my level of evidence."),
            ("misdirect" if push_misdirect else "escalation",
             f"They replaced the whole unit with AI-powered scent drones, and I said trust me, I have been doing evidence-free {work} for years."),
            ("punchline", f"My new method is revolutionary: step one, sniff the wrong locker, step two, {policy}, step three, promotion."),
            ("callback" if not dodge_dogs else "tag",
             f"My partner the bloodhound found three felonies before breakfast while I found the break room. I am blind to {blind}, and frankly that is what makes me management material."),
            ("closer", "Smell that? Definitely a promotion."),
        ]
    out = []
    for i, (btype, text) in enumerate(beats, 1):
        out.append({"id": f"b{i}", "type": btype, "text": text,
                    "pause_after_ms": 1000 if btype == "punchline" else (700 if btype == "closer" else 300),
                    "emphasis": 0.9 if btype in ("punchline", "closer") else 0.6})
    return out


_MODS = None


def load_modulators() -> dict:
    global _MODS
    if _MODS is None:
        _MODS = _load_json(_REPO / "audition/modulators.json") or {}
    return _MODS


def actor_decide(character: dict, scenario: dict, state: dict, mems: list,
                 tilt: str, explore: bool) -> dict:
    """Actor stage: interpretation from philosophy+state+memory. Knows nothing
    of operators or audience metrics. Coherence is its only objective."""
    appraisal = f"{scenario['id']} reads through {character.get('name')}'s lens; status {state.get('perceived_status')}"
    goal = (f"Restore {character['want']}" if state.get("perceived_status") == "threatened"
            else f"Celebrate {character['want']}")
    reaction = f"{tilt or character.get('action_policy', '')}".strip()
    restraint = state.get("restraint", "medium")
    arousal = state.get("arousal", 0.5)
    shift = ("restraint holds; ice" if restraint == "high" and arousal >= 0.7
             else ("restraint holds; velvet menace" if restraint == "high"
                   else ("restraint fails; truth leaks" if arousal <= 0.3 else "steady register")))
    return {"appraisal": appraisal, "chosen_goal": goal, "reaction": reaction,
            "emotional_shift": shift, "confidence": round(0.5 + 0.1 * (0 if explore else 1), 2),
            "memory_refs": mems}


def seed_modulators(character: dict) -> list[str]:
    raw = character.get("raw", {}) or {}
    rng = raw.get("philosophy", {}).get("modulator_range", []) or (
        raw.get("modulator_range", []) if is_human(character) else [])
    if rng:
        return [m for m in rng if m in load_modulators()] or list(load_modulators())
    ov = _load_json(_REPO / "audition/seeds/nolan_seed.json") or {}
    if character["id"] == "no_nose_nolan" and ov.get("modulator_range"):
        return [m for m in ov["modulator_range"] if m in load_modulators()]
    return list(load_modulators())


def generate_minute(character_id: str, recent: list[dict], strategy: dict,
                    seed: int | None = None, used_ids: list[str] | None = None,
                    scenario: dict | None = None, length: str = "minute") -> dict:
    rng = random.Random(seed if seed is not None else random.randint(1, 10**9))
    character = get_character(character_id)
    used = list(used_ids or []) or [r.get("scenario_id", "") for r in (recent or []) if r.get("scenario_id")]
    scenario = scenario or pick_scenario(used, rng)

    # 70/30 exploit/explore over operators using strategy evidence
    success = (strategy or {}).get("success", {})
    failed = (strategy or {}).get("failed", {})
    scored = {op: success.get(op, 0) - failed.get(op, 0) for op in OPERATORS}
    explore = rng.random() < 0.30 or not any(scored.values())
    # Instance lock via canonical Jev questions (modulator + operator +
    # appraisal + vetoes, one parallel call). No key -> bandit/heuristics.
    mod_range = seed_modulators(character)
    mod_scores = {m: success.get("mod:" + m, 0) - failed.get("mod:" + m, 0) for m in mod_range}
    chooser, mod_conf, op_conf = "bandit", 0.0, 0.0
    jev_appraisal, jev_vetoes = {}, {}
    if explore or (not any(scored.values()) and not any(mod_scores.values())):
        kt = _kt_prior_ops()
        operator = rng.choice(([o for o in OPERATORS if kt.get(o, 0) > 0] + OPERATORS) if (kt and explore) else OPERATORS)
        modulator, mod_explore = rng.choice(mod_range), True
    else:
        best = max(scored.values())
        op_cands = [op for op, s in scored.items() if s == best] or OPERATORS
        best_m = max(mod_scores.values())
        mod_cands = [m for m, s in mod_scores.items() if s == best_m]
        operator, modulator, mod_explore = rng.choice(op_cands), rng.choice(mod_cands), False
        try:
            import jev_decide
            import jev_questions as _qq
            mems0 = ((character.get("raw", {}) or {}).get("memories", []) or [])
            st = _qq.seed_state(character, scenario, mems0, strategy.get("instructions", ""))
            tilts = {m: (load_modulators().get(m, {}).get("tilt", m)) for m in mod_cands}
            hyps = {o: THEORY_OF_OP.get(o, o) for o in op_cands}
            call = jev_decide.decide_instance(st, mod_cands, tilts, op_cands, hyps)
            if call:
                if call.get("modulator") and call.get("modulator_conf", 0) >= 0.6:
                    modulator, chooser, mod_conf = call["modulator"], "jev-1.13", call["modulator_conf"]
                if call.get("operator") and call.get("operator_conf", 0) >= 0.6:
                    operator, chooser, op_conf = call["operator"], "jev-1.13", call["operator_conf"]
                jev_appraisal, jev_vetoes = call.get("appraisal", {}), call.get("vetoes", {})
        except Exception:
            pass
    operator_requested = operator
    if is_human(character) and scenario.get("punches") and operator not in scenario["punches"]:
        # human blocks license specific mechanisms; remap to the best-prior licensed one
        prior = ((character.get("raw") or {}).get("comedy") or {}).get("operator_priors") or {}
        lic = list(scenario["punches"])
        operator = sorted(lic, key=lambda o: (-prior.get(o, 0), lic.index(o)))[0]
    theory = THEORY_OF_OP.get(operator, "rigidity")

    mod = load_modulators().get(modulator, {})
    tilt = mod.get("tilt", "")
    perf = mod.get("performative", {}) or mod.get("delivery", {})
    demph = perf.get("emphasis_delta", 0)
    ppause = perf.get("pause_mult", 1.0)
    # Stateful energy (Shikigami pattern): prior energy decays toward 40,
    # modulator arousal nudges it; capped, no feedback spiral.
    try:
        import store as _estore
        _ec = _estore.connect()
        try:
            prior_e = _estore.get_energy(_ec, character["id"])
        finally:
            _ec.close()
    except Exception:
        prior_e = 40.0
    arousal = (mod.get("emotional", {}) or {}).get("arousal", 0.5)
    energy = max(0.0, min(80.0, prior_e + (40.0 - prior_e) * 0.3 + (arousal - 0.5) * 20.0))
    try:
        _ec2 = _estore.connect()
        try:
            _estore.set_energy(_ec2, character["id"], energy)
        finally:
            _ec2.close()
    except Exception:
        pass
    # Situated mind: emotion + arousal + status + restraint interaction.
    restraint = ((character.get("raw", {}) or {}).get("expression", {}) or {}).get("emotional_restraint", "medium")
    emo = (mod.get("emotional", {}) or {})
    state = {"emotion": modulator, "arousal": emo.get("arousal", 0.5),
             "energy": round(energy, 1), "prior_energy": round(prior_e, 1),
             "defensiveness": emo.get("defensiveness", 0.5),
             "perceived_status": "threatened" if emo.get("defensiveness", 0.5) >= 0.7 else "secure",
             "restraint": restraint,
             "restraint_interaction": mod.get("restraint_interaction", ""),
             "attention": (mod.get("cognitive", {}) or {}).get("attention", "")}

    last = (recent or [{}])[0] if recent else {}
    critique = ((last.get("comment") or "") + " " + (strategy.get("instructions") or ""))[:600]
    avoid = _prior_text(recent)
    mems = ((character.get("raw", {}) or {}).get("memories", []) or [])[-3:]
    try:
        import store as _store
        _c = _store.connect()
        try:
            mems = mems + [r[0] for r in _c.execute(
                "SELECT text FROM memories WHERE character_id=? ORDER BY created_at DESC LIMIT 3",
                (character["id"],)).fetchall()][::-1]
            mems = mems[-3:]
        finally:
            _c.close()
    except Exception:
        pass

    beats = None
    model_id = "template-v0-offline"
    prompt_version = "prompt-v1-template"
    if bool(os.getenv("OPENCODE_API_KEY", "")):
        import prompt as _prompt
        messages, prompt_version = _prompt.compile(
            character, scenario, state, mems, modulator, mod,
            [operator], avoid, critique)
        llm = _llm_generate(messages)
        if isinstance(llm, dict) and isinstance(llm.get("beats"), list) and len(llm["beats"]) >= 4:
            # Normalize chatty model output: compound types -> base, no markdown.
            _tmap = {"misdirect-or-escalation": "misdirect", "tag-or-callback": "tag",
                     "opener": "setup", "joke": "setup", "punch": "punchline"}
            beats = []
            for i, b in enumerate(llm["beats"][:7]):
                t = str(b.get("type", "setup")).strip().lower()
                t = _tmap.get(t, t)
                txt = str(b.get("text", "")).replace("*", "").replace("#", "").strip()[:280]
                try:
                    pa = int(b.get("pause_after_ms", 400))
                except (TypeError, ValueError):
                    pa = 400
                try:
                    em = float(b.get("emphasis", 0.6))
                except (TypeError, ValueError):
                    em = 0.6
                beats.append({"id": b.get("id", f"b{i+1}"), "type": t, "text": txt,
                              "pause_after_ms": pa, "emphasis": em})
            model_id = os.getenv("OPENCODE_MODEL", "mimo-v2.6-flash")
    if beats is None:
        beats = _template_beats(character, scenario, operator, critique, avoid, length)
    # modulator delivery deltas: emphasis shift + pause scaling (the HOW)
    for b in beats:
        b["emphasis"] = round(min(1.0, max(0.2, b.get("emphasis", 0.6) + demph)), 2)
        b["pause_after_ms"] = int(b.get("pause_after_ms", 400) * ppause)
        b["modulator"] = modulator

    full_text = " ".join(b["text"] for b in beats)
    # beat timing estimate: ~2.6 words/sec + pauses
    t = 0
    for b in beats:
        words = len(b["text"].split())
        dur = int(words / 2.6 * 1000) + int(b.get("pause_after_ms", 400))
        b["start_ms"] = t
        b["end_ms"] = t + dur
        t += dur
    act = actor_decide(character, scenario, state, mems, tilt, explore)
    try:
        import prompt as _prompt
        tts = _prompt.tts_params(modulator, mod, base=tts_base_rate(character))
        set_no = len(used)
        aff = _prompt.affinity_segment(set_no + 1)
    except Exception:
        tts, aff = {"rate": "normal", "pitch": "+0Hz"}, ""
    appraisal, goal, reaction = act["appraisal"], act["chosen_goal"], act["reaction"]
    shift = act["emotional_shift"]
    decision = {"action": f"Frame '{scenario['id']}' as proof of competence",
                "character_motive": f"Protect {character['want']}; hide {character['fear']}",
                "expected_comic_collision": f"{operator}: blind to {character.get('blind_spots')}",
                "policy_tilt": tilt,
                "appraisal": appraisal, "chosen_goal": goal, "reaction": reaction,
                "emotional_shift": shift, "confidence": act["confidence"],
                "actor": {"appraisal": appraisal, "chosen_goal": goal, "reaction": reaction,
                          "emotional_shift": shift, "memory_refs": mems,
                          "note": "actor knows nothing of operators or POGs"},
                "director": {"operator": operator, "modulator": modulator,
                             "chooser": chooser, "chooser_confidence": mod_conf,
                             "operator_confidence": op_conf, "explore": explore,
                             "note": "director knows evidence; actor must never see this"},
                "memory_refs": mems, "tts_params": tts, "affinity": aff,
                "config": {"seed": f"{character['id']}@seed_v{((character.get('raw', {}) or {}).get('seed_version', 1))}",
                           "scenario": scenario["id"], "state": state,
                           "policy": strategy.get("version", "strategy_01"),
                           "strategy": strategy.get("version", "strategy_01"),
                           "generator": model_id, "prompt": prompt_version,
                           "alignment": {"method": "proportional-scale", "verified": False,
                                         "note": "beat times stretched to audio; attribution uncertain"},
                           "run_id": content_hash(json.dumps(
                               {"seed": character["id"], "scenario": scenario["id"],
                                "modulator": modulator, "operator": operator,
                                "strategy": strategy.get("version", "strategy_01"),
                                "model": model_id, "gen_seed": seed or 0,
                                "beats": [b["text"] for b in beats]}))[:16]},
                "instance": {"seed_id": character["id"], "scenario_id": scenario["id"],
                             "modulator": modulator, "mod_explore": mod_explore,
                             "chooser": chooser, "chooser_confidence": mod_conf,
                             "operator_confidence": op_conf,
                             "jev_appraisal": jev_appraisal, "jev_vetoes": jev_vetoes,
                             "operator": operator, "operator_requested": operator_requested},
                "change_from_last": ("Fresh scenario; " if (scenario["id"] not in used) else "Same pool, new angle; ") +
                                     (f"fixing critique: {critique[:120]}" if critique.strip() else "no critique yet; testing preferred operators")}
    return {"character": character, "scenario": scenario, "operator_ids": [operator],
            "theory_ids": sorted(set([theory] + (character.get("preferred_theories", [])[:1]))),
            "beats": beats, "full_text": full_text, "decision": decision, "length": length,
            "modulator": modulator,
            "exploration": explore, "model_id": model_id, "seed": seed or rng.randint(1, 10**9)}


def summarize_strategy(character_id: str, auditions_feedback: list[dict]) -> dict:
    """Derive strategy evidence from ratings + pog counts (no LLM inventing wins)."""
    success: dict[str, int] = {}
    failed: dict[str, int] = {}
    notes = []
    for r in auditions_feedback:
        ops = []
        try:
            ops = json.loads(r.get("operator_ids", "[]"))
        except Exception:
            pass
        pogs = r.get("pog_count", 0)
        rating = r.get("rating", 0) or 0
        good = rating >= 2 or pogs >= 2
        keys = list(ops)
        try:
            inst = (json.loads(r.get("decision", "{}") or "{}").get("instance") or {})
            if inst.get("modulator"):
                keys.append("mod:" + inst["modulator"])
        except Exception:
            pass
        for op in keys:
            if good:
                success[op] = success.get(op, 0) + 1
            else:
                failed[op] = failed.get(op, 0) + 1
        c = (r.get("comment") or "").strip()
        if c:
            notes.append(f"{'GOOD' if good else 'WEAK'}({r.get('scenario_id')}): {c[:140]}")
    top = sorted(success, key=lambda k: -success[k])[:3]
    bad = sorted(failed, key=lambda k: -failed[k])[:3]
    instr = ("Fresh. No evidence yet." if not auditions_feedback else
             f"Lean on {', '.join(top) or 'nothing proven'}; avoid {', '.join(bad) or 'nothing ruled out'}. " +
             ("; ".join(notes[-3:])))
    return {"success": success, "failed": failed, "instructions": instr[:800]}


MINUTE_SCHEMA = "minute-v1"


def validate_minute(gen: dict, character_id: str, fmt: str | None = None) -> list[str]:
    """Strict versioned validation. Returns error list (empty = valid). Never truncates."""
    errs = []
    beats = gen.get("beats") or []
    fmt = fmt or gen.get("length", "minute")
    lo_b, hi_b, lo_w, hi_w = (3, 6, 20, 48) if fmt == "short" else (4, 8, 60, 260)
    if not (lo_b <= len(beats) <= hi_b):
        errs.append(f"beat count {len(beats)} outside {lo_b}-{hi_b}")
    valid_types = {"setup", "escalation", "misdirect", "punchline", "tag", "callback", "closer", "opener"}
    for b in beats:
        if not (b.get("text") or "").strip():
            errs.append(f"empty beat {b.get('id')}")
        if b.get("type") not in valid_types:
            errs.append(f"bad beat type {b.get('type')}")
    words = sum(len((b.get("text") or "").split()) for b in beats)
    if not (lo_w <= words <= hi_w):
        errs.append(f"word count {words} outside {lo_w}-{hi_w}")
    if gen.get("scenario", {}).get("id") in (None, ""):
        errs.append("missing scenario id")
    dec = gen.get("decision", {}) or {}
    for f in ("action", "appraisal", "chosen_goal", "reaction", "instance"):
        if f not in dec:
            errs.append(f"missing decision.{f}")
    if not gen.get("theory_ids") or not gen.get("operator_ids"):
        errs.append("missing theory/operator refs")
    try:
        import gates
        others = ["partner", "rex", "bloodhound"] if "nolan" in character_id else []
        others = others + list(((gen.get("character") or {}).get("raw") or {}).get("others_present", []))
        g = gates.check(beats, others_present=others,
                        character=(gen.get("character") or {}).get("raw"))
        errs.extend("GATE: " + v for v in g["vetoes"])
    except Exception:
        pass
    return errs


def content_hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def slop_check(text: str) -> dict:
    """noslop filter (prx0r/noslop miner). Returns {is_ai, confidence} or {error}."""
    try:
        sys_path = __import__("sys").path
        for p in ("/root/noslop/miner/src", "/root/noslop"):
            if p not in sys_path:
                sys_path.insert(0, p)
        from classifier import SlopClassifier
        r = SlopClassifier().classify(text)
        return {"is_ai": bool(r.get("is_ai")), "confidence": round(float(r.get("confidence", 0)), 4),
                "model": r.get("model", "noslop")}
    except Exception as e:
        return {"error": str(e)[:120]}
