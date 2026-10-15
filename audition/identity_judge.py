"""Identity judge: is this minute actually a [comedian] set?

Jev discriminator per comedian: real-set style card (few-shot excerpts +
delivery stats) vs candidate minute -> noul "is this them?", choice
"whose style is this most like", score "style match", choice "what
breaks the illusion". The adversarial loop for generated minutes.

Usage: python3 identity_judge.py --comedian casey_rocket \
       --wav-file <rec.json with beats> [--compare-with ...]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_or import decide

HERE = Path(__file__).parent
REPO = HERE.parent

STYLE_CARDS = {
    "casey_rocket": {
        "sample_lines": ["God, senior year is gonna be nuts.",
                         "Marble. Marble. Hair. The ritual's almost complete, Tony.",
                         "Alexander wept, for there were no more rifts left to conquer."],
        "stats": "delivery: manic-deadpan swings, 135-360wpm within one set, "
                 "rapid-fire surreal bursts then flat drops, self-aware absurdism",
        "fingerprint": "absurd image-dense surrealism + deadpan drops + kinetic tempo"},
    "louis_ck": {
        "sample_lines": ["I was going to tell you about the thing. Anyway that's the thing.",
                         "My girls are six and nine now.",
                         "I can smell their blood through three walls, Karen."],
        "stats": "delivery: 1.67s avg pauses (above pros), 3.94 syll/s slow, "
                 "19.6dB dynamics (close-mic), forward-spiral escalation, self-pay",
        "fingerprint": "sincere confession-booth: literalize metaphor, escalate forward, self-damage"},
    "norm_macdonald": {
        "sample_lines": ["A moth goes into a podiatrist's office.",
                         "The cold took her down, as it did many of us.",
                         "Cause the light was on."],
        "stats": "delivery: suspension deadpan, 192wpm, pitch_std 10 (widest), "
                 "dyn 13 (flat volume), long tangent then snap return",
        "fingerprint": "deadpan authority over absurd premises; believes his own bit"},
}


def judge(comedian: str, minutes: list[dict]) -> list[dict]:
    """minutes: [{name, text_excerpt, delivery_summary}]"""
    card = STYLE_CARDS[comedian]
    others = {k: v["fingerprint"] for k, v in STYLE_CARDS.items() if k != comedian}
    results = []
    for m in minutes:
        state = {
            "target_comedian": comedian,
            "style_card": {"sample_lines": card["sample_lines"],
                           "delivery": card["stats"],
                           "fingerprint": card["fingerprint"]},
            "candidate": {"name": m["name"], "text_excerpt": m["text_excerpt"][:600],
                          "delivery_summary": m["delivery_summary"]},
            "other_comedians_fingerprint": others,
        }
        qs = {
            "is_them": {"type": "noul",
                "instructions": f"Could this candidate plausibly BE a set by {comedian}, "
                                "considering both material and delivery?",
                "criteria": {"true": "matches fingerprint in material AND delivery",
                             "false": "breaks character in material or delivery"}},
            "closest": {"type": "choice",
                "instructions": "Whose style is this candidate most like?",
                "criteria": {**{k: v["fingerprint"] for k, v in STYLE_CARDS.items()},
                             "none": "matches none of them"}},
            "match": {"type": "score",
                "instructions": "How close is the style match (5=indistinguishable from real)?",
                "criteria": ["wrong comedian", "vaguely adjacent", "plausible",
                             "convincing", "near-perfect"]},
            "breaks": {"type": "choice",
                "instructions": "What most breaks the illusion, if anything?",
                "criteria": {"nothing": "fully plausible",
                             "material": "content/topics wrong for them",
                             "delivery": "timing/energy wrong for them",
                             "structure": "set shape wrong for them"}},
        }
        res = decide(state, qs)
        a = res.get("answers", {})
        out = {"minute": m["name"], "comedian": comedian,
               "is_them": (a.get("is_them") or {}).get("noul"),
               "closest": (a.get("closest") or {}).get("choice"),
               "match": (a.get("match") or {}).get("score"),
               "breaks": (a.get("breaks") or {}).get("choice"),
               "cost": res.get("usage", {}).get("cost")}
        results.append(out)
        print(f"  {m['name'][:38]:38} is_them={out['is_them']:.2f} "
              f"match={out['match']:.1f}/5 closest={out['closest']:14} breaks={out['breaks']}")
    return results


def minute_from_perf(setname: str) -> dict:
    d = json.loads((HERE / f"voicelab/jev_loop_{setname}.json").read_text())
    best = min(d["history"], key=lambda h: h["wpm_mae"])
    rows = best["rows"]
    text = " ".join(r.get("text", "") for r in rows)[:600]
    if not text:
        from jev_deliver import load_set, fixed_beats
        words, _ = load_set(setname)
        text = " ".join(b["text"] for b in fixed_beats(words))[:600]
    wpm = sum(r["gen_wpm"] for r in rows) / max(len(rows), 1)
    return {"name": f"GEN:{setname}", "text_excerpt": text,
            "delivery_summary": f"rendered: avg {wpm:.0f}wpm, "
                                f"emotions={[r['pred_emo'] for r in rows]}"}


def minute_from_swap(path: str) -> dict:
    d = json.loads(Path(path).read_text())
    text = " ".join(b["text"] for b in d.get("beats", []))[:600]
    return {"name": Path(path).stem, "text_excerpt": text,
            "delivery_summary": d.get("mapping", d.get("note", "mapped set"))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--comedian", required=True, choices=sorted(STYLE_CARDS))
    ap.add_argument("--minutes", nargs="+", required=True,
                    help="paths to swap/rec jsons or set:<name>")
    args = ap.parse_args()
    minutes = []
    for m in args.minutes:
        if m.startswith("set:"):
            minutes.append(minute_from_perf(m[4:]))
        else:
            minutes.append(minute_from_swap(m))
    judge(args.comedian, minutes)
