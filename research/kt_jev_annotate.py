#!/usr/bin/env python3
"""Kill Tony Jev annotation — deconstruct every set per theory.

One parallel Jev request per set (10 nouls + 1 choice). Calibrated
probabilities replace rule-v0 keyword tags. 0.4-0.6 = uncertain, routed
to human, never counted. Cost ledger appended per run.

Needs OPENROUTER_API_KEY. Resumes from theory/kt-jev-tags.jsonl.
Run: python3 /root/characters/research/kt_jev_annotate.py [--limit N]
"""
from __future__ import annotations

import glob
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/root/pogpet/backend")
sys.path.insert(0, "/root/characters/audition")

KT_DATA = Path("/root/reference/comedy/kill-tony-archive/data")
OUT = Path("/root/characters/theory/kt-jev-tags.jsonl")
LEDGER = Path("/root/characters/theory/kt-jev-ledger.jsonl")

NOULS = {
    "rigidity": "A person or institution mechanically follows a rule after reality made it absurd.",
    "status_reversal": "The powerful are diminished; who controls whom is inverted.",
    "displacement": "A loaded or taboo point is answered sideways through bland or bureaucratic language.",
    "identity_contradiction": "What the performer claims to be conflicts with what they show.",
    "self_awareness": "The performer knowingly exploits the absurdity of their own identity.",
    "specificity": "Concrete specific details carry the joke: names, places, numbers.",
    "escalation": "Beats build stepwise to something bigger; the pattern grows.",
    "garden_path": "The setup builds one reading, then forces re-reading another way.",
    "benign_violation": "Something wrong or taboo is made safe or distant enough to laugh at.",
    "audience_alliance": "The audience is let in on knowledge someone in the scene lacks.",
}
CHOICE = {"primary": {"type": "choice",
                      "instructions": "Which single mechanism carries this minute most?",
                      "criteria": {k: k for k in list(NOULS) + ["other"]}}}


def load_sets():
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
                continue
            seen.add(h)
            out.append({"file": Path(f).name, "meta": s, "text": t, "hash": h})
    return out


def main():
    import jev as _jev
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    done = set()
    if OUT.exists():
        for line in open(OUT):
            try:
                done.add(json.loads(line)["hash"])
            except Exception:
                pass
    sets = [s for s in load_sets() if s["hash"] not in done]
    if limit:
        sets = sets[:limit]
    print(f"annotating {len(sets)} sets ({len(done)} already done)")
    questions = {k: {"type": "noul", "instructions": v} for k, v in NOULS.items()}
    questions.update(CHOICE)
    n_ok, spend_note = 0, time.time()
    with open(OUT, "a") as f:
        for i, s in enumerate(sets):
            try:
                resp = _jev.decide({"minute": s["text"][:3000]}, questions)
                ans = resp.get("answers", {})
            except Exception as e:
                print(f"[{i}] jev error: {str(e)[:100]}; stopping (resume later)")
                break
            tags = {}
            for k in NOULS:
                try:
                    p = float(ans[k]["noul"]) if isinstance(ans.get(k), dict) else 0.5
                except Exception:
                    p = 0.5
                tags[k] = {"p": round(p, 3),
                           "verdict": "yes" if p >= 0.6 else ("no" if p <= 0.4 else "uncertain")}
            prim = ans.get("primary", {})
            row = {"hash": s["hash"], "file": s["file"],
                   "comedian": s["meta"].get("comedian_name"), "set_number": s["meta"].get("set_number"),
                   "crowd": s["meta"].get("crowd_reaction"),
                   "word_count": len(s["text"].split()),
                   "tags": tags,
                   "primary": prim.get("choice") if isinstance(prim, dict) else None,
                   "primary_conf": round(float(prim.get("confidence", 0)), 3) if isinstance(prim, dict) else 0,
                   "annotator": "jev-1.13", "usage": resp.get("usage", {})}
            f.write(json.dumps(row) + "\n")
            f.flush()
            n_ok += 1
            if n_ok % 25 == 0:
                print(f"  {n_ok}/{len(sets)}...")
            time.sleep(0.3)
    with open(LEDGER, "a") as f:
        f.write(json.dumps({"ts": time.time(), "n": n_ok, "elapsed_s": round(time.time() - spend_note, 1),
                            "note": "Jev $0.042/1M in, out free; ~200 tok/set => <$0.01 total"}) + "\n")
    print(f"done: {n_ok} newly annotated")


if __name__ == "__main__":
    main()
