"""Cast delivery engines: KT performers (2+ sets) -> character archetypes.

Scans killtony-personas for performers with >=2 sets (evidence floor),
extracts each one's delivery signature (archetype, traits, operator lean,
crowd prior), scores them against the delivery archetypes our canon/worlds
need, and writes voicelab/casting.json.

Delivery archetypes use the measured grammar (voices.json/domains.json):
variance/energy/pace requirements + operator vocabulary. Owner mappings
honored (pickles->villain, ari->mock_indignant engine).

Usage: python3 cast_table.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
OUT = HERE / "voicelab" / "casting.json"

# Owner-proven anchors (evidence beats scoring).
ANCHORS = {
    "sir_winston_pickles": "villain_dracula",   # "mr pickle = dracula" (owner)
    "ari_matti": "mock_indignant_engine",      # exact-word calibrated
    "casey_rocket": "chaos_gremlin",           # manic/deadpan swing engine
}

# trait tokens that ACTUALLY exist in killtony-personas (plays_X)
TRAIT_MAP = {
    "villain_dracula": {"shock_humor", "crime", "religion", "absurdist"},
    "chaos_gremlin": {"absurdist", "physical", "shock_humor", "drugs"},
    "mock_indignant_engine": {"politics", "race", "shock_humor", "meta"},
    "deadpan_cryptkeeper": {"observational", "storytelling", "self_deprecation"},
    "ice_sovereign": {"observational", "meta", "self_deprecation"},
    "warm_mother": {"relationships", "family", "sex", "dating"},
    "whimsical_fae": {"absurdist", "musical", "storytelling", "other"},
    "hype_host": {"shock_humor", "race", "politics", "disability"},
    "sage_narrator": {"storytelling", "observational", "family", "religion"},
    "trickster": {"meta", "self_deprecation", "observational", "absurdist"},
}
TARGETS = {
    "villain_dracula": {
        "need": "evil aristocrat: controlled menace, dark charisma",
        "ops": ["status_invert", "rigidify"], "traits_wanted": ["dark", "absurdist", "deadpan", "formal"],
        "energy": "mid", "vibe_match": ["seductive", "comedy"],
        "pace_wpm": 160, "punch_words": "clipped", "owner_note": "mr pickle archetype (sir_winston_pickles proved)"},
    "chaos_gremlin": {
        "need": "unhinged id: manic spikes, physical chaos",
        "ops": ["double_interpret", "absurdity", "exaggeration"], "traits_wanted": ["chaotic", "fast", "surreal", "erratic"],
        "energy": "high", "vibe_match": ["comedy"],
        "pace_wpm": 200, "punch_words": "rambling", "owner_note": "casey engine (manic/deadpan swing)"},
    "mock_indignant_engine": {
        "need": "spiky offense comedian: grievance velocity",
        "ops": ["status_invert", "literalize"], "traits_wanted": ["angry", "confident", "absurd"],
        "energy": "high", "vibe_match": ["comedy"],
        "pace_wpm": 220, "punch_words": "mid", "owner_note": "ari engine (exact-word calibrated)"},
    "deadpan_cryptkeeper": {
        "need": "flat eerie narrator: stillness as threat",
        "ops": ["rigidify", "literalize"], "traits_wanted": ["deadpan", "dry", "dark"],
        "energy": "low", "vibe_match": ["sleep", "comedy"],
        "pace_wpm": 150, "punch_words": "clipped"},
    "ice_sovereign": {
        "need": "cold authority: level highness, zero warmth",
        "ops": ["status_invert"], "traits_wanted": ["cold", "formal", "superior"],
        "energy": "low", "vibe_match": ["seductive"],
        "pace_wpm": 155, "punch_words": "clipped"},
    "warm_mother": {
        "need": "safety with command: still pitch, breathing volume",
        "ops": ["rigidify"], "traits_wanted": ["warm", "dominant", "caring"],
        "energy": "low", "vibe_match": ["seductive", "sleep"],
        "pace_wpm": 155, "punch_words": "mid"},
    "whimsical_fae": {
        "need": "level float: high, even, airy",
        "ops": ["double_interpret"], "traits_wanted": ["weird", "literal", "gleeful"],
        "energy": "mid", "vibe_match": ["whimsical"],
        "pace_wpm": 180, "punch_words": "mid"},
    "hype_host": {
        "need": "crowd engine: fast, wide, loud, inclusive",
        "ops": ["exaggeration", "parody"], "traits_wanted": ["energetic", "confident", "loud"],
        "energy": "high", "vibe_match": ["comedy"],
        "pace_wpm": 200, "punch_words": "rambling"},
    "sage_narrator": {
        "need": "trusted thread-holder: mid, even, present",
        "ops": ["split_knowledge"], "traits_wanted": ["wise", "measured", "storyteller"],
        "energy": "mid", "vibe_match": ["narration"],
        "pace_wpm": 165, "punch_words": "mid"},
    "trickster": {
        "need": "wordplay gremlin-light: reversal hunger",
        "ops": ["double_interpret", "split_knowledge"], "traits_wanted": ["clever", "smug", "meta"],
        "energy": "mid", "vibe_match": ["comedy", "whimsical"],
        "pace_wpm": 185, "punch_words": "clipped"},
}


def set_counts() -> Counter:
    c = Counter()
    for p in (REPO / "theory/killtony-minutes").glob("*.json"):
        m = re.match(r"(.+)-(\d+)\.json$", p.name)
        if m:
            c[m.group(1)] += 1
    return c


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def load_features() -> dict:
    """Aggregate per-comedian set structure from killtony-features.jsonl."""
    agg: dict = {}
    p = REPO / "theory/killtony-features.jsonl"
    if not p.exists():
        return agg
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        name = norm_name((r.get("set_pointer") or {}).get("comedian") or "")
        if not name:
            continue
        beats = r.get("beats") or []
        n = len(beats) or 1
        punches = [b for b in beats if b.get("type") == "punchline"]
        timing = r.get("timing_s") or {}
        dur = (timing.get("end") or 0) - (timing.get("start") or 0)
        wpm = (r.get("word_count") or 0) / dur * 60 if dur > 5 else None
        punch_words = (sum(b.get("words", 0) for b in punches) / len(punches)) if punches else 0
        d = agg.setdefault(name, {"wpm": [], "punch_density": [], "punch_words": [],
                                  "reframes": [], "crowd_ord": [], "n": 0})
        if wpm:
            d["wpm"].append(wpm)
        d["punch_density"].append(len(punches) / n)
        d["punch_words"].append(punch_words)
        d["reframes"].append(sum(1 for b in beats if b.get("reframe")))
        d["crowd_ord"].append(r.get("crowd_ord") or 5)
        d["n"] += 1
    out = {}
    for k, d in agg.items():
        mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
        out[k] = {"sets": d["n"], "wpm": mean(d["wpm"]),
                  "punch_density": mean(d["punch_density"]),
                  "punch_words": mean(d["punch_words"]),
                  "reframes": mean(d["reframes"]),
                  "crowd_ord": mean(d["crowd_ord"])}
    return out


def load_persona(name: str) -> dict | None:
    p = REPO / "theory/killtony-personas" / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def deep_level(name: str) -> int:
    d = REPO / "theory/killtony-minutes"
    n = 0
    if list(d.glob(f"kt*{name.split('_')[0]}*acoustic.json")) or list(d.glob(f"{name}*acoustic.json")):
        n += 2
    if list(d.glob(f"kt*{name.split('_')[0]}*gemini.json")) or list(d.glob(f"{name}*gemini.json")):
        n += 2
    if list(d.glob(f"{name}*.performance.v1.json")) or list(d.glob(f"kt*{name}*performance.v1.json")):
        n += 1
    return n


def score(persona: dict, target: dict, tname: str, feat: dict | None = None) -> dict:
    ops = ((persona.get("comedy") or {}).get("operator_priors")) or {}
    num = {k: v for k, v in ops.items() if isinstance(v, (int, float))}
    total = sum(num.values()) or 1.0
    top = sorted(num, key=lambda k: -num[k])
    top_share = (num[top[0]] / total) if top else 0.0
    op_hit = 1 if top and top[0] in target["ops"] else 0
    traits = [t.replace("plays_", "") for t in (persona.get("traits") or [])]
    wanted = TRAIT_MAP.get(tname, set())
    trait_hits = [t for t in traits if t in wanted]
    trait_ratio = len(trait_hits) / max(len(wanted), 1)
    crowd = persona.get("provenance", {}).get("mean_crowd_ord") or 5.0
    # delivery-structure match from features.jsonl aggregates
    delivery = {}
    d_score = 0.0
    if feat and feat.get("wpm"):
        tgt_wpm = target.get("pace_wpm", 180)
        d_score += 2.5 * max(0.0, 1.0 - abs(feat["wpm"] - tgt_wpm) / 120.0)
        pw = feat.get("punch_words") or 0
        pref = target.get("punch_words", "mid")
        band = {"clipped": (0, 7), "mid": (6, 12), "rambling": (10, 40)}[pref]
        d_score += 1.5 * (1.0 if band[0] <= pw <= band[1] else 0.2)
        delivery = {"wpm": feat["wpm"], "punch_words": pw,
                    "punch_density": feat.get("punch_density"),
                    "crowd_ord": feat.get("crowd_ord")}
    raw = 3.0 * trait_ratio + 2.5 * op_hit * top_share + d_score
    return {"score": round(raw, 2), "op_hit": op_hit, "top_op": top[0] if top else None,
            "top_share": round(top_share, 2), "trait_hits": trait_hits,
            "delivery": delivery, "crowd_ord_prior": crowd}


def main():
    counts = set_counts()
    roster = {n: c for n, c in counts.items() if c >= 2}
    feats = load_features()
    casting: dict = {"rule": "n>=2 sets; anchors; trait+op+delivery(wpm/punch) score; crowd_ord prior only",
                     "anchors": ANCHORS, "targets": {}, "unassigned": []}
    # anchors claim first
    assigned = {n: t for n, t in ANCHORS.items() if n in roster or n == "casey_rocket"}
    for tname, t in TARGETS.items():
        rows = []
        for name, nsets in roster.items():
            per = load_persona(name)
            if not per:
                continue
            s = score(per, t, tname, feats.get(name))
            anchor_for = assigned.get(name)
            rows.append({"performer": name, "sets": nsets,
                         "deep": deep_level(name), "persona_traits": per.get("traits"),
                         "persona_archetype": per.get("archetype"),
                         "anchored_to": anchor_for if anchor_for == tname else None, **s})
        # greedy: drop performers already anchored/claimed elsewhere
        rows.sort(key=lambda r: (-(3.0 if r.get("anchored_to") else 0.0) - r["score"],
                                 -r["deep"], -r["sets"]))
        kept, used = [], set()
        for r in rows:
            owner = assigned.get(r["performer"])
            if owner and owner != tname:
                continue
            if r["performer"] in used:
                continue
            kept.append(r)
            used.add(r["performer"])
        casting["targets"][tname] = {"need": t["need"], "owner_note": t.get("owner_note", ""),
                                     "top_matches": kept[:5]}
    assigned_roster = set(assigned)
    for block in casting["targets"].values():
        for r in block["top_matches"][:3]:
            assigned_roster.add(r["performer"])
    casting["unassigned"] = [n for n in roster if n not in assigned_roster]
    OUT.write_text(json.dumps(casting, indent=2))
    print(f"wrote {OUT}\n")
    for tname, block in casting["targets"].items():
        m = block["top_matches"][0]
        tag = "ANCHOR" if m.get("anchored_to") else f"sc={m['score']:.1f}"
        print(f"{tname:26} <- {m['performer']:24} {tag:8} sets={m['sets']} deep={m['deep']}")


if __name__ == "__main__":
    main()
