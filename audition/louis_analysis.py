"""Full analysis on louis series: dpv stats + delivery signature + theory tags.

Per clip: word-timing pause structure (dpv), voice_judge acoustics,
theory_tagger beat tags + laugh correlation. Aggregate into LOUIS-FORMULA.
Usage: python3 louis_analysis.py [--all]
"""
from __future__ import annotations
import argparse, json, statistics as st, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from theory_tagger import tag_set
from jev_deliver import fixed_beats
import voice_judge

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"

def clip_stats(setname: str) -> dict:
    scribe = json.loads((REPO / f"theory/scribe/{setname}.json").read_text())
    words = scribe["words"]
    src = scribe.get("source", "")
    # dpv temporal features from word timings
    pauses = [round(words[i+1]["start"] - words[i]["end"], 3)
              for i in range(len(words)-1)
              if words[i+1]["start"] - words[i]["end"] > 0.15]
    span = words[-1]["end"] - words[0]["start"]
    n_syll_est = len(words) * 1.4  # rough eng syllables/word
    speech_time = span - sum(pauses)
    rate = n_syll_est / speech_time if speech_time > 1 else 0
    wpm = len(words) / span * 60 if span else 0
    m = voice_judge.measure(Path(src)) if src and Path(src).exists() else {}
    return {"set": setname, "n_words": len(words), "span_s": round(span, 1),
            "wpm": round(wpm, 1), "syll_per_s": round(rate, 2),
            "avg_pause": round(st.mean(pauses), 2) if pauses else 0,
            "pause_var": round(st.stdev(pauses), 2) if len(pauses) > 2 else 0,
            "n_pauses": len(pauses),
            "pitch_std": (m.get("pitch") or {}).get("std_semitones"),
            "median_hz": (m.get("pitch") or {}).get("median_hz"),
            "dyn_db": (m.get("intensity") or {}).get("p90_p10_db"),
            "centroid": (m.get("brightness") or {}).get("spectral_centroid_hz")}

def main():
    sets = sorted(p.stem for p in (REPO / "theory/scribe").glob("louis_c*.json"))
    print(f"louis clips: {sets}")
    rows, tags_all = [], []
    for s in sets:
        r = clip_stats(s)
        try:
            t = tag_set(s)
            r["theory_corr"] = t.get("laugh_correlations", {})
            r["n_laugh_beats"] = sum(1 for row in t["rows"] if row["laugh_near"])
            r["n_beats"] = len(t["rows"])
        except Exception as e:
            print(f"  {s}: tagger fail {str(e)[:80]}")
        rows.append(r)
        print(f"  {s}: wpm={r['wpm']} pause={r['avg_pause']}s±{r['pause_var']} "
              f"rate={r['syll_per_s']} pitch={r['pitch_std']} laughs={r.get('n_laugh_beats')}/{r.get('n_beats')}")
    doc = {"performer": "louis_ck", "clips": rows,
           "dpv_benchmark": {"pro_pause": 1.39, "amateur_pause": 0.96,
                             "pro_rate_syll": 4.20, "amateur_rate": 4.47,
                             "source": "Timing-is-Everything 828 sets"},
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (LAB / "louis_series_analysis.json").write_text(json.dumps(doc, indent=2))
    # aggregate formula
    if rows:
        agg = {k: round(st.mean([r[k] for r in rows if r.get(k) is not None]), 2)
               for k in ("wpm", "avg_pause", "pause_var", "syll_per_s", "pitch_std", "dyn_db", "centroid") if any(r.get(k) is not None for r in rows)}
        print(f"\nLOUIS AGGREGATE ({len(rows)} clips): {agg}")
        # dpv verdict
        verdict = ("PRO-LEVEL pauses" if agg["avg_pause"] >= 1.2 else
                   "mid" if agg["avg_pause"] >= 0.9 else "tight/amateur pauses")
        print(f"dpv verdict: avg_pause {agg['avg_pause']}s -> {verdict} (pros: 1.39s)")

if __name__ == "__main__":
    main()
