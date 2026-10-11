#!/usr/bin/env python3
"""Kill Tony theory decoder — offline research pipeline.

Reads local kill-tony-archive transcripts, emits FEATURES ONLY
(no verbatim beyond <=7-word fingerprints) tagged with pogpet
theory IDs + world operators, then measures which mechanisms
associate with crowd response on held-out comedians.

Output:
  theory/killtony-features.jsonl  — one row per set (features + pointers)
  theory/killtony-priors.json     — operator priors for the generator
  theory/killtony-report.md       — what transferred, with uncertainty

Run: python3 /root/characters/research/kt_decode.py
"""
from __future__ import annotations

import glob
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

KT_DATA = Path("/root/reference/comedy/kill-tony-archive/data")
THEORIES = json.load(open("/root/pogpet/templates/theories.json"))["theories"]
THEORY_IDS = {t["id"] for t in THEORIES}
OUT_DIR = Path("/root/characters/theory")
ANNOTATOR = "rule-v0"
ANNOTATOR_VERSION = "kt_decode.py rule-v0 (deterministic heuristics, no LLM)"

CROWD_ORD = {"silence": 0, "light": 1, "moderate": 2, "big_laughs": 3, "roaring": 4}

CONTRAST = re.compile(r"\b(but|instead|actually|turns out|suddenly|realiz\w+|who'?s \w+ who)\b", re.I)
REFRAME = re.compile(r"\b(because|so that'?s why|that'?s why|which means|the key is)\b", re.I)
RULE_WORDS = re.compile(r"\b(always|never|policy|procedure|every single|literally required)\b", re.I)
STATUS_WORDS = re.compile(r"\b(boss|manager|promotion|fired|landlord|officer|doctor|expert|professional)\b", re.I)
TABOO = re.compile(r"\b(fuck\w*|shit|dick|pussy|pregnan\w*|deport\w*|illegal|abortion)\b", re.I)
BUREAU = re.compile(r"\b(visa|passport|paperwork|meeting|HR|desk|form|status|available)\b", re.I)


def sents(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def proper_nouns(text: str) -> list[str]:
    return re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text)


def segment(text: str) -> list[dict]:
    """Heuristic beat segmentation. Types only + word counts + positions."""
    ss = sents(text)
    n = len(ss)
    beats = []
    for i, s in enumerate(ss):
        w = len(s.split())
        if i == 0:
            btype = "opener"
        elif i == n - 1:
            btype = "closer"
        elif CONTRAST.search(s) or REFRAME.search(s) or s.rstrip().endswith(("?", "!")):
            btype = "punchline"
        else:
            btype = "setup"
        beats.append({"i": i, "type": btype, "words": w,
                      "contrast": bool(CONTRAST.search(s)), "reframe": bool(REFRAME.search(s))})
    # callbacks: distinctive proper nouns recurring across beats
    nouns = Counter(proper_nouns(text))
    repeats = sorted([x for x, c in nouns.items() if c >= 2 and len(x) > 3])
    return beats, repeats


def tag_theories(text: str, beats: list[dict]) -> list[dict]:
    tags = []

    def add(tid: str, conf: float, rule: str):
        if tid in THEORY_IDS:
            tags.append({"theory": tid, "confidence": conf, "rule": rule,
                         "uncertain": conf < 0.6})

    pns = proper_nouns(text)
    if len(pns) >= 2:
        add("specificity", min(0.9, 0.4 + 0.1 * len(pns)), f"{len(pns)} proper nouns")
    punches = [b for b in beats if b["type"] == "punchline"]
    if punches:
        add("garden_path", 0.55, f"{len(punches)} contrast/reframe turns")
        add("resolution", 0.5, "turn forces re-read")
    if RULE_WORDS.search(text):
        add("rigidity", 0.6, "rule/policy language present")
    if STATUS_WORDS.search(text):
        add("status_reversal", 0.5 if TABOO.search(text) else 0.45, "status words in minute")
    if TABOO.search(text) and STATUS_WORDS.search(text):
        add("degrading_analogy", 0.45, "low-concrete yoked to status frame")
    if TABOO.search(text) and BUREAU.search(text):
        add("displacement", 0.6, "loaded point answered via paperwork frame")
    if re.search(r"\b(not .{3,30} but .{3,30})\b", text, re.I):
        add("figure_ground", 0.5, "not-X-but-Y flip")
    if re.search(r"\b(19|20)\d\d\b|\d+\s*(pounds|times|blocks|minutes)", text):
        add("exaggeration", 0.45, "countable scale present")
        add("specificity", 0.5, "numbers ground the bit")
    if len(beats) >= 5 and any(b["type"] == "punchline" for b in beats[2:]):
        add("escalation", 0.5, "late punch after buildup")
    if re.search(r"\b(I'?m (like|a professional|the)|trust me|you know what I'?m saying|here'?s an idea|maybe it'?s just me)\b", text, re.I):
        add("identity_contradiction", 0.5, "self-label vs displayed behavior")
        add("self_awareness", 0.45, "performs awareness of own identity")
    if not tags:
        add("incongruity", 0.35, "default: model violated, mechanism unclear")
    # world-op mapping for generator priors
    op_map = {"rigidity": "rigidify", "status_reversal": "status_invert",
              "displacement": "double_interpret", "garden_path": "double_interpret",
              "specificity": "literalize", "escalation": "repeat_variation",
              "identity_contradiction": "identity_contradict",
              "self_awareness": "expose_self_blindness",
              "degrading_analogy": "unmask", "figure_ground": "double_interpret",
              "resolution": "double_interpret", "exaggeration": "literalize",
              "incongruity": "bisociate"}
    for t in tags:
        t["operator"] = op_map.get(t["theory"], "bisociate")
    return tags


def persona(text: str, meta: dict) -> dict:
    first = " ".join(sents(text)[:2])
    ilines = len(re.findall(r"\bI('m| am| was| have| got)\b", text))
    return {"self_labels": (meta.get("fun_facts") or [])[:3],
            "i_statements": ilines,
            "opener_fingerprint": " ".join(first.split()[:7]),
            "contradiction_hypothesis":
                f"presents as {((meta.get('fun_facts') or ['unknown'])[0])[:60]}; "
                f"behavior in minute may undercut it ({ilines} self-framing lines)",
            "note": "hypothesis only, not a psychological fact"}


def load_sets() -> list[dict]:
    import hashlib
    out, seen = [], set()
    for f in sorted(glob.glob(str(KT_DATA / "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        items = d if isinstance(d, list) else d.get("sets", [])
        for s in items:
            if not isinstance(s, dict):
                continue
            t = (s.get("set_transcript") or "").strip()
            if not t:
                continue
            h = hashlib.sha256(t.encode()).hexdigest()[:16]
            if h in seen:
                continue  # duplicate set committed in two files; keep first
            seen.add(h)
            s = dict(s)
            s["_text_hash"] = h
            out.append({"file": Path(f).name, "meta": s, "text": t})
    return out


SCENARIO_FAMILIES = {
    "employment_and_ai": r"\b(ai|artificial intelligence|robot|chatgpt|automation|laid off|replace(d)?|job|work|boss|employee)\b",
    "family_and_relationships": r"\b(family|mother|father|dad|mom|wife|husband|marriage|dating|girlfriend|boyfriend)\b",
    "institutions": r"\b(police|government|school|teacher|law|court|hospital|hr|human resources)\b",
    "money_and_class": r"\b(money|rent|rich|poor|salary|pay|bank|broke|debt)\b",
    "technology": r"\b(computer|phone|internet|app|ai|robot|online|website)\b",
}


def scenario_families(text: str) -> list[str]:
    return [k for k, p in SCENARIO_FAMILIES.items() if re.search(p, text, re.I)]


def main():
    random.seed(7)
    sets = load_sets()
    print(f"loaded {sets} sets")
    rows = []
    for s in sets:
        m, t = s["meta"], s["text"]
        beats, callbacks = segment(t)
        m_clean = {k: v for k, v in m.items() if k != "set_transcript"}
        rows.append({
            "set_id": f"{m.get('comedian_name', '?')}-{m.get('set_number', '?')}-{m.get('_text_hash', '')}",
            "set_pointer": {"file": s["file"], "comedian": m.get("comedian_name"),
                            "set_number": m.get("set_number")},
            "scenario_families": scenario_families(t),
            "license_note": "transcript (c) its performers; repo code MIT; features-only row, no verbatim",
            "annotator": ANNOTATOR, "annotator_note": ANNOTATOR_VERSION,
            "word_count": len(t.split()), "n_beats": len(beats),
            "beats": beats, "callbacks": callbacks[:5],
            "theories": tag_theories(t, beats),
            "persona": persona(t, m_clean),
            "topics": m.get("topic_tags"),
            "crowd": m.get("crowd_reaction"), "crowd_ord": CROWD_ORD.get(m.get("crowd_reaction"), -1),
            "tony_praise": m.get("tony_praise_level"), "golden_ticket": m.get("golden_ticket"),
            "timing_s": {"start": m.get("set_start_seconds"), "end": m.get("set_end_seconds")},
            "timing_note": "repo warns timestamps can drift 1-2 min; do not use for beat alignment",
        })
    # held-out by comedian: 20% comedians held out
    names = sorted({r["set_pointer"]["comedian"] for r in rows})
    held = set(random.sample(names, max(1, len(names) // 5)))
    for r in rows:
        r["split"] = "heldout" if r["set_pointer"]["comedian"] in held else "train"
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "killtony-features.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # associations on train, verified on heldout: mean crowd by operator presence
    def means(rs):
        acc = defaultdict(list)
        for r in rs:
            if r["crowd_ord"] < 0:
                continue
            for t in r["theories"]:
                if t["confidence"] >= 0.45:  # rule-v0 is noisy; threshold documents, not certifies
                    acc[t["operator"]].append(r["crowd_ord"])
        return {k: round(sum(v) / len(v), 3) for k, v in acc.items() if len(v) >= 5}
    tr = [r for r in rows if r["split"] == "train"]
    ho = [r for r in rows if r["split"] == "heldout"]
    m_tr, m_ho = means(tr), means(ho)
    base_tr = sum(r["crowd_ord"] for r in tr if r["crowd_ord"] >= 0) / max(1, sum(1 for r in tr if r["crowd_ord"] >= 0))
    priors = {}
    for op in set(m_tr) | set(m_ho):
        priors[op] = {"train_lift": round((m_tr.get(op, base_tr) - base_tr), 3),
                      "heldout_mean": m_ho.get(op), "train_mean": m_tr.get(op),
                      "n_train": sum(1 for r in tr for t in r["theories"]
                                     if t["operator"] == op and t["confidence"] >= 0.45)}
    json.dump({"base_crowd_mean": round(base_tr, 3), "annotator": ANNOTATOR,
               "n_train": len(tr), "n_heldout": len(ho),
               "warning": "rule-v0 tags are noisy; lifts are hypotheses, not proof",
               "operator_priors": priors},
              open(OUT_DIR / "killtony-priors.json", "w"), indent=1)
    rep = ["# Kill Tony decode — rule-v0 report", "",
           f"Sets: {len(rows)} ({len(tr)} train / {len(ho)} heldout comedians). Base crowd mean: {base_tr:.2f} (0=silence..4=roaring).", "",
           "Operator lifts vs base (train) + heldout check:", ""]
    for op, p in sorted(priors.items(), key=lambda x: -x[1]["train_lift"]):
        rep.append(f"- {op}: lift {p['train_lift']:+} (train_mean {p['train_mean']}, heldout {p['heldout_mean']}, n={p['n_train']})")
    rep += ["", "Use: positive-lift operators seed generator exploration; POG remains ground truth.",
            "Do not: imitate lines, train on verbatim, treat LLM scores as laughter."]
    (OUT_DIR / "killtony-report.md").write_text("\n".join(rep) + "\n")
    # comedian profiles: longitudinal stats + theory frequencies + persona hypothesis
    profs = {}
    for r in rows:
        c = r["set_pointer"]["comedian"]
        p = profs.setdefault(c, {"comedian": c, "sets": [], "crowds": [], "theories": Counter(),
                                 "topics": Counter(), "files": set()})
        p["sets"].append({"file": r["set_pointer"]["file"], "n": r["set_pointer"]["set_number"],
                          "crowd": r["crowd"], "words": r["word_count"]})
        if r["crowd_ord"] >= 0:
            p["crowds"].append(r["crowd_ord"])
        for t in r["theories"]:
            if t["confidence"] >= 0.45:
                p["theories"][t["operator"]] += 1
        for t in (r["topics"] or []):
            p["topics"][t] += 1
        p["files"].add(r["set_pointer"]["file"])
    profiles = []
    for c, p in sorted(profs.items()):
        n = len(p["sets"])
        profiles.append({
            "comedian": c, "n_sets": n,
            "mean_crowd": round(sum(p["crowds"]) / len(p["crowds"]), 2) if p["crowds"] else None,
            "theory_freq": dict(p["theories"].most_common(5)),
            "top_topics": [t for t, _ in p["topics"].most_common(5)],
            "persona_hypothesis": ("recurring: " + ", ".join(list(p["theories"])[:3])) if p["theories"] else "single set, no pattern yet",
            "persona_note": "stage-persona hypothesis from observed sets only, not a psychological fact",
            "files": sorted(p["files"]),
        })
    json.dump(profiles, open(OUT_DIR / "killtony-comedian-profiles.json", "w"), indent=1)
    # scenario index: same-topic sets across comedians for cross-comedian comparison
    scen = defaultdict(list)
    for r in rows:
        for t in (r["topics"] or []):
            scen[t].append({"comedian": r["set_pointer"]["comedian"], "file": r["set_pointer"]["file"],
                            "crowd": r["crowd"], "words": r["word_count"],
                            "operators": sorted({x["operator"] for x in r["theories"] if x["confidence"] >= 0.45})})
    scen_out = {k: {"n_sets": len(v), "n_comedians": len({x["comedian"] for x in v}), "sets": v}
                for k, v in sorted(scen.items(), key=lambda x: -len(x[1]))}
    json.dump(scen_out, open(OUT_DIR / "killtony-scenario-index.json", "w"), indent=1)
    print(f"profiles: {len(profiles)} comedians | scenarios: {len(scen_out)} topics")
    print("\n".join(rep))
    print(f"\nwrote {OUT_DIR/'killtony-features.jsonl'}")


if __name__ == "__main__":
    main()
