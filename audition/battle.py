"""Candidate battle — generate many, classify, ship the winner.

lmfaoooo lesson: selection is the bottleneck. Per turn we generate N
instance-variants (different modulators/operators), score each with the
full classifier stack (slop fused + Jev vetoes/appraisal + novelty), and
persist the winner as the audition. Losers are logged with reasons, never
shown. Scores accumulate -> quantitative progress per character.
"""
from __future__ import annotations

import random


def score_candidate(full_text: str, beats: list[dict], decision: dict,
                    prior_texts: list[str]) -> dict:
    """Higher is better. Components recorded for audit."""
    parts: dict = {}
    # 1. slop fused (clean wins)
    try:
        import slop_jev
        sj = slop_jev.jev_slop(full_text)
        parts["slop"] = round(1.0 - sj.get("fused", 0.5), 3)
        parts["slop_verdict"] = sj.get("verdict", "?")
    except Exception:
        parts["slop"] = 0.5
        parts["slop_verdict"] = "unknown"
    # 2. jev vetoes/appraisal on the finished text
    try:
        import jev_decide
        import jev_questions as _qq
        st = {"minute": full_text[:3000]}
        q = {}
        q.update(_qq.q_vetoes())
        q.update({k: v for k, v in _qq.q_appraisal().items() if k in ("play_frame", "benign_ready")})
        import jev as _jev
        ans = _jev.ask(st, q)
        g = lambda k: float((ans.get(k, {}) or {}).get("noul", 0.5))
        parts["not_swappable"] = round(1 - g("character_swappable"), 3)
        parts["not_generic"] = round(1 - g("generic_ai_humor"), 3)
        parts["reframe"] = round(g("reframe_present"), 3)
        parts["play_ready"] = round((g("play_frame") + g("benign_ready")) / 2, 3)
    except Exception:
        parts.update({"not_swappable": 0.5, "not_generic": 0.5, "reframe": 0.5, "play_ready": 0.5})
    # 3. novelty vs prior minutes (word overlap penalty)
    words = set(full_text.lower().split())
    nov = 1.0
    for p in prior_texts[-5:]:
        pw = set(p.lower().split())
        ov = len(words & pw) / max(1, len(words | pw))
        nov = min(nov, 1 - ov)
    parts["novelty"] = round(nov, 3)
    # 4. shape bonus: opener short + closer shortest
    try:
        ws = [len(b["text"].split()) for b in beats]
        parts["shape"] = 1.0 if ws and ws[-1] <= min(ws[:-1] or [ws[-1]]) and ws[0] <= 22 else 0.4
    except Exception:
        parts["shape"] = 0.5
    # 5. gates: hard veto tanks the candidate; flags cost a little
    try:
        import gates
        g = gates.check(beats)
        parts["gates"] = 1.0 if g["passed"] else 0.0
        parts["gate_flags"] = len(g["flags"])
    except Exception:
        parts["gates"] = 0.5
        parts["gate_flags"] = 0
    total = round(0.2 * parts["slop"] + 0.2 * parts["not_swappable"] + 0.1 * parts["not_generic"]
                  + 0.15 * parts["reframe"] + 0.1 * parts["play_ready"]
                  + 0.1 * parts["novelty"] + 0.05 * parts["shape"] + 0.1 * parts["gates"], 3)
    if parts.get("gates") == 0.0:
        total = min(total, 0.3)
    return {"parts": parts, "total": total}


def battle(character_id: str, recent: list[dict], strategy: dict, n: int = 3,
           seed: int | None = None) -> dict:
    """Generate n variants, return winner + ranked table. Deterministic seeds."""
    import generate as _gen
    rng = random.Random(seed if seed is not None else random.randint(1, 10**9))
    priors = [r.get("full_text", "") for r in (recent or [])]
    cands = []
    running = list(recent or [])
    for i in range(n):
        g = _gen.generate_minute(character_id, running, strategy, seed=rng.randint(1, 10**9))
        sc = score_candidate(g["full_text"], g["beats"], g["decision"], priors)
        priors = priors + [g["full_text"]]
        running = running + [{"scenario_id": g["scenario"]["id"], "full_text": g["full_text"],
                              "comment": "", "operator_ids": "[]", "rating": 0, "pog_count": 0}]
        cands.append({"gen": g, "score": sc})
    cands.sort(key=lambda c: -c["score"]["total"])
    table = [{"modulator": c["gen"]["decision"]["instance"]["modulator"],
              "operator": c["gen"]["decision"]["instance"]["operator"],
              "scenario": c["gen"]["scenario"]["id"],
              "text": c["gen"]["full_text"],
              "total": c["score"]["total"], "parts": c["score"]["parts"]} for c in cands]
    return {"winner": cands[0]["gen"], "winner_score": cands[0]["score"], "table": table}
