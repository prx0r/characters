"""GTVH comedic classifier — every minute as a 6-tuple.

Attardo & Raskin: Joke = {SO, LM, SI, TA, NS, LA}, hierarchically ordered.
SO (script opposition) determines most; LA (wording) least. Similarity
between minutes = shared low KRs. This beats flat theory tags: it says
WHICH opposition, resolved HOW, about WHAT situation, aimed at WHOM,
told HOW, worded HOW.

Jev answers SO/LM/TA/NS (judgment); code fills SI/LA (extraction).
No key -> code-only fallback with explicit provenance.
"""
from __future__ import annotations

import re
import sys

for _p in ("/root/pogpet/backend",):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SO_OPTIONS = ["real/unreal", "possible/impossible", "high/low status",
              "competent/incompetent", "caring/cruel", "smart/dumb",
              "sacred/profane", "normal/absurd", "other"]
LM_OPTIONS = ["garden_path", "false_analogy", "juxtaposition", "role_reversal",
              "perspective_shift", "figure_ground", "exaggeration", "cratylism",
              "rigidify", "displacement", "literalize", "other"]
NS_OPTIONS = ["narrative", "qa", "monologue-list", "anecdote", "one-liner-chain", "other"]


def _code_si_la(text: str) -> dict:
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]
    mids = []
    for s in sents:
        words = s.split()
        mids.extend(words[1:])
    midset = {w.strip(",.?!;:") for w in mids}
    proper = [p for p in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text)
              if " " in p or p in midset][:12]
    nums = re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", text)
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()]
    return {"situation": f"{len(proper)} named entities, {len(nums)} figures; {len(sents)} sentences",
            "entities": proper[:8], "figures": nums[:8],
            "language": f"{len(text.split())} words; opener {len(sents[0].split()) if sents else 0}w; "
                        f"closer {len(sents[-1].split()) if sents else 0}w"}


def classify(text: str) -> dict:
    base = _code_si_la(text)
    out = {"SO": None, "LM": None, "SI": base["situation"], "TA": None,
           "NS": None, "LA": base["language"], "entities": base["entities"],
           "provenance": "code-only"}
    try:
        import jev as _jev
        answers = _jev.ask(
            {"minute": text[:3000]},
            {"SO": {"type": "choice", "instructions": "Which script opposition carries this minute?",
                    "criteria": {o: o for o in SO_OPTIONS}},
             "LM": {"type": "choice", "instructions": "Which logical mechanism joins the two scripts?",
                    "criteria": {o: o for o in LM_OPTIONS}},
             "TA": {"type": "choice", "instructions": "Who is the butt of the joke, if anyone?",
                    "criteria": {"self": "the performer themselves", "powerful": "bosses/institutions",
                                 "peers": "equals/ Everyman", "none": "no target, pure absurdity"}},
             "NS": {"type": "choice", "instructions": "How is the minute organized as narrative?",
                    "criteria": {o: o for o in NS_OPTIONS}}})
    except Exception:
        return out
    try:
        for k in ("SO", "LM", "TA", "NS"):
            a = answers.get(k, {})
            if isinstance(a, dict) and a.get("choice"):
                out[k] = {"value": a["choice"], "conf": round(float(a.get("confidence", 0)), 3)}
        out["provenance"] = "jev-1.13+code"
    except Exception:
        pass
    return out


def similarity(a: dict, b: dict) -> dict:
    """GTVH joke similarity: shared low KRs count most (LA > NS > TA > SI > LM > SO)."""
    weights = {"LA": 1, "NS": 2, "TA": 3, "SI": 4, "LM": 5, "SO": 6}
    score, detail = 0, {}
    for k, w in weights.items():
        va = (a.get(k) or {}).get("value") if isinstance(a.get(k), dict) else a.get(k)
        vb = (b.get(k) or {}).get("value") if isinstance(b.get(k), dict) else b.get(k)
        same = bool(va and vb and (va == vb or (k == "SI" and va[:20] == vb[:20])))
        detail[k] = same
        if same:
            score += w
    return {"similarity": score, "max": sum(weights.values()), "shared": detail}
