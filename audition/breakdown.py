"""Breakdown generator: set -> "why this is funny" decomposition.

The YouTube-channel engine: ingest a set -> theory tags + dpv stats +
laugh timeline + anatomy template -> markdown breakdown (narration-ready).
Usage: python3 breakdown.py --set kt704_performer --performer ari_matti
"""
from __future__ import annotations
import argparse, json, statistics as st
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_deliver import fixed_beats

HERE = Path(__file__).parent
REPO = HERE.parent
OUT = HERE / "voicelab" / "breakdowns"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--performer", default="unknown")
    args = ap.parse_args()
    s = args.set
    words = json.loads((REPO / f"theory/scribe/{s}.json").read_text())["words"]
    beats = fixed_beats(words)
    tags = {}
    tp = HERE / f"voicelab/theory_tags_{s}.json"
    if tp.exists():
        tags = {r["seg"]: r for r in json.loads(tp.read_text())["rows"]}
    # dpv stats
    pauses = [round(words[i+1]["start"] - words[i]["end"], 2)
              for i in range(len(words)-1)
              if 0.15 < words[i+1]["start"] - words[i]["end"] < 15]
    span = words[-1]["end"] - words[0]["start"]
    wpm = len(words) / span * 60 if span else 0
    avg_pause = st.mean(pauses) if pauses else 0
    # GT laughs
    gp = REPO / f"theory/killtony-minutes/{s}_gemini.gemini.json"
    segs = json.loads(gp.read_text())["segments"] if gp.exists() else []
    laugh_moments = [round(sg["t0"], 1) for sg in segs
                     if "laugh_near=True" in (sg.get("comedy") or {}).get("note", "")]
    # AM events if cached
    am = HERE / f"voicelab/am_events/{s}.json"
    am_events = json.loads(am.read_text()) if am.exists() else []

    md = [f"# BREAKDOWN: {s} ({args.performer})", "",
          "## The numbers (dpv)",
          f"- length: {span:.0f}s, {len(words)} words, **{wpm:.0f} wpm**",
          f"- avg pause: **{avg_pause:.2f}s** (pros 1.39s / amateurs 0.96s)",
          f"- pause variability: {st.pstdev(pauses):.2f}s" if len(pauses) > 2 else "",
          f"- laugh moments: {len(laugh_moments)} GT / {len(am_events)} acoustic",
          "",
          "## Beat-by-beat theory", ""]
    for b in beats:
        sid = f"s{b['i']}"
        t = tags.get(sid, {})
        md.append(f"**{sid}** [{b['t0']:.0f}-{b['t1']:.0f}s] — "
                  f"gp={t.get('garden_path','?')} ic={t.get('identity_contradiction','?')} "
                  f"surp={t.get('surprise','?')} esc={t.get('escalation','?')} "
                  f"{'🎬 LAUGH' if t.get('laugh_near') else ''}")
        md.append(f"> {b['text'][:120]}...")
        md.append("")
    # unified verdict via tags
    if tags:
        gp_m = st.mean([t.get("garden_path", 0) for t in tags.values()])
        ic_m = st.mean([t.get("identity_contradiction", 0) for t in tags.values()])
        esc_m = st.mean([t.get("escalation", 0) for t in tags.values()])
        surp_m = st.mean([t.get("surprise", 1) for t in tags.values()])
        md += ["## Why it works (theory)",
               f"- garden_path density: {gp_m:.2f} (expectation-setting present)",
               f"- identity_contradiction: {ic_m:.2f} (character collision)",
               f"- escalation: {esc_m:.2f} (stakes rising)",
               f"- peak surprise: {surp_m:.1f}/3 (dpv: peaks matter, not averages)",
               f"- coupling check: pauses {avg_pause:.2f}s vs pros 1.39s — "
               f"{'pro-tier holds' if avg_pause >= 1.2 else 'below pro (room to grow)'}",
               "",
               "## Anatomy (LOUIS-JOKE-ANATOMY template)",
               "premise clarity -> micro-surprises w/ pauses -> counterpoint ->",
               "dramatization -> anticipatory laughs -> punchline -> tags. "
               "Stay in the bit during laughs; augment, never pivot."]
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{s}.md"
    p.write_text("\n".join(x for x in md if x != ""))
    print(f"breakdown -> {p}")
    print("\n".join(md[:18]))

if __name__ == "__main__":
    main()
