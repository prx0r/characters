"""Slop as Jev classifier — code counts, Jev judges.

Deterministic 41-signal stats ride along as JSON state (free, exact);
five semantic nouls do what regex can't (generic? hedged? committed?).
Fused with the logistic score; veto only when both agree, route the
middle to human. No key -> logistic alone, as today.
"""
from __future__ import annotations

import sys

for _p in ("/root/noslop/miner/src", "/root/pogpet/backend"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLOP_QUESTIONS = {
    "scaffolding": {"type": "noul",
                    "instructions": "Does this read like essay scaffolding (thesis statements, 'in conclusion' energy, listicle structure)?"},
    "metronomic": {"type": "noul",
                   "instructions": "Is the rhythm metronomic: uniform medium sentences with no fragments, bursts, or staccato?"},
    "hedged": {"type": "noul",
               "instructions": "Is it hedged and non-committal (almost, arguably, parenthetical qualifiers, vague attribution)?"},
    "generic": {"type": "noul",
                "instructions": "Is this generic content any speaker could deliver unchanged?"},
    "uncommitted": {"type": "noul",
                    "instructions": "Does the voice refuse to assert anything concrete (abstractions, no names/numbers/places)?"},
}


def signals_state(text: str) -> dict:
    try:
        from classifier import SlopClassifier
        r = SlopClassifier().classify(text)
        sig = r.get("signals", {})
        return {"logistic_prob": round(float(r.get("confidence", 0)), 3),
                "pattern_counts": {k: sig.get(k) for k in
                                   ("narr", "neg", "three_list", "cliche", "staccato", "hedges")},
                "rhythm": {k: round(float(sig.get(k, 0)), 3) for k in
                           ("avg_sent_len", "frag_ratio", "vocab_div", "fw_ratio")}}
    except Exception as e:
        return {"error": str(e)[:100]}


def jev_slop(text: str) -> dict:
    """Returns {logistic, jev_mean, fused, verdict}. Verdict in clean|suspect|slop."""
    st = signals_state(text)
    base = st.get("logistic_prob", 0.5)
    try:
        import jev as _jev
        answers = _jev.ask({"minute": text[:3000], "computed_signals": st}, SLOP_QUESTIONS)
        ps = []
        for k in SLOP_QUESTIONS:
            a = answers.get(k, {})
            ps.append(float(a.get("noul", 0.5)) if isinstance(a, dict) else 0.5)
        jm = sum(ps) / len(ps)
    except Exception:
        return {"logistic": base, "jev_mean": None, "fused": base,
                "verdict": "slop" if base >= 0.7 else "clean", "chooser": "logistic-only"}
    fused = round(0.5 * base + 0.5 * jm, 3)
    if fused >= 0.7 and base >= 0.5:
        verdict = "slop"
    elif fused <= 0.35:
        verdict = "clean"
    else:
        verdict = "suspect"
    return {"logistic": base, "jev_mean": round(jm, 3), "fused": fused,
            "verdict": verdict, "chooser": "jev-fused",
            "questions": {k: round(float((answers.get(k, {}) or {}).get("noul", 0.5)), 3)
                          for k in SLOP_QUESTIONS}}


if __name__ == "__main__":
    import json
    demo = ("In conclusion, it is important to note that humor is a multifaceted phenomenon. "
            "Firstly, there is incongruity. Secondly, there is relief. Thirdly, there is superiority. "
            "One might argue that, arguably, experts say comedy is subjective (though not always).")
    print(json.dumps(jev_slop(demo), indent=1))
