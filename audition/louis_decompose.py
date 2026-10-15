"""Decompose all louis sets: per-beat technique labels + set arcs -> theory.

Jev typed choice per beat (technique vocab from casey riff_analysis +
our set): self_deprecation, literalize, callback, escalation,
deadpan_drop, sincere_claim, absurd_confession, audience_address.
Plus existing theory tags. Synthesis: what is Louis actually doing.
Usage: python3 louis_decompose.py
"""
from __future__ import annotations
import json, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_or import decide
from jev_deliver import fixed_beats

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"

TECHNIQUES = {
    "self_deprecation": "damages his own status/ego",
    "literalize": "takes a figure of speech as literal fact",
    "callback": "references an earlier bit/line from this set",
    "escalation": "raises stakes or extremity from the previous beat",
    "deadpan_drop": "delivers absurdity completely flat",
    "sincere_claim": "states something with full earnest sincerity",
    "absurd_confession": "confesses something bizarre as if normal",
    "audience_address": "speaks directly to the crowd/room",
}

def decompose(setname: str) -> dict:
    words = json.loads((REPO / f"theory/scribe/{setname}.json").read_text())["words"]
    beats = fixed_beats(words)
    gp = REPO / f"theory/killtony-minutes/{setname}_gemini.gemini.json"
    segs = json.loads(gp.read_text())["segments"] if gp.exists() else []
    state = {"performer": "louis_ck",
             "persona": "self-deprecating sincere storyteller; takes audience to weird dark places; "
                        "pauses are intimacy; escalations self-damage; callbacks behind silence",
             "segments": [{"id": f"s{b['i']}", "text": b["text"]} for b in beats]}
    qs = {}
    for b in beats:
        sid = f"s{b['i']}"
        qs[f"{sid}_tech"] = {"type": "choice",
            "instructions": f"For segment {sid}, which primary technique is this comedian using?",
            "criteria": TECHNIQUES}
    res = decide(state, qs)
    ans = res.get("answers", {})
    cost = res.get("usage", {}).get("cost", 0)
    rows = []
    for b in beats:
        sid = f"s{b['i']}"
        tech = (ans.get(f"{sid}_tech") or {}).get("choice", "sincere_claim")
        in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]
                  and not w["text"].strip().startswith("[")]
        dur = (in_win[-1]["end"] - in_win[0]["start"]) if len(in_win) >= 2 else 1
        wps = len(in_win)/dur if dur > 0 else 0
        laugh = any("laugh_near=True" in (s.get("comedy") or {}).get("note","")
                    for s in segs
                    if max(0, min(b["t1"], s["t1"])-max(b["t0"], s["t0"])) > 0)
        rows.append({"seg": sid, "text": b["text"][:90], "technique": tech,
                     "wpm": round(wps*60, 1), "laugh": laugh})
        print(f"  {sid} {tech:19} wpm={wps*60:.0f} {'LAUGH' if laugh else ''} {b['text'][:44]}")
    from collections import Counter
    tech_counts = Counter(r["technique"] for r in rows)
    laugh_tech = Counter(r["technique"] for r in rows if r["laugh"])
    doc = {"set": setname, "cost_usd": cost, "rows": rows,
           "technique_freq": dict(tech_counts.most_common()),
           "laugh_by_technique": dict(laugh_tech.most_common()),
           "n": len(rows), "laugh_rate": round(sum(r['laugh'] for r in rows)/max(len(rows),1), 2)}
    (LAB / f"louis_decomp_{setname}.json").write_text(json.dumps(doc, indent=2))
    print(f"{setname}: {len(rows)} beats ${cost:.5f} | top tech: {tech_counts.most_common(3)}")
    return doc

if __name__ == "__main__":
    sets = sorted(p.stem for p in (REPO / "theory/scribe").glob("louis_c*.json"))
    all_docs = [decompose(s) for s in sets]
    # aggregate theory
    from collections import Counter
    tech_all, laugh_all = Counter(), Counter()
    for d in all_docs:
        tech_all.update(d["technique_freq"])
        laugh_all.update(d["laugh_by_technique"])
    total = sum(tech_all.values())
    print("\n=== LOUIS UNIFIED (all clips) ===")
    for t, n in tech_all.most_common():
        lr = laugh_all.get(t, 0) / max(n, 1)
        print(f"  {t:19} freq={n/total:.2f} laugh_rate={lr:.2f}")
    (LAB / "louis_unified_decomp.json").write_text(json.dumps(
        {"clips": [d["set"] for d in all_docs],
         "technique_freq": dict(tech_all.most_common()),
         "laugh_by_technique": dict(laugh_all.most_common()),
         "total_beats": total}, indent=2))
