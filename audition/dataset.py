"""KT minute-dataset builder: process any clip -> full labeled entry.

One entry = audio + profile + delivery labels + laughs + rubric scores.
This IS the dataset the comedy judge trains on. Scoring our generated
minutes uses the same rubric -> direct comparison to real minutes.

Entry schema (voicelab/dataset/<id>.json):
  id, source (clip path or set name), duration_ms
  words[], laugh_events[], punch_candidates[]     (cf_asr)
  delivery: wpm, pitch_std, dyn_db, centroid       (voice_judge)
  profile: performer, persona (from kt-personas if known), voice_id
  stencil: arc emotions, recipes used (if processed via perf_set)
  crowd_ord / golden (from killtony-features if matched)
  rubric: {verify_match, laugh_rate, pace_score, arc_score, composite}
  verdict: null | good | bad  (+ note)

Usage:
  python3 dataset.py ingest /path/to/clip.mp4 --performer ari_matti
  python3 dataset.py score <entry_id>            # rubric on existing entry
  python3 dataset.py rubric <wav> --compare-to ari_matti_kt704_passport
  python3 dataset.py list
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
DS = HERE / "voicelab" / "dataset"


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def crowd_for(performer: str, set_no: int | None = None):
    """Look up crowd_ord/golden from killtony-features for a performer."""
    out = []
    for line in (REPO / "theory/killtony-features.jsonl").read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if norm((r.get("set_pointer") or {}).get("comedian") or "") == norm(performer):
            out.append({"crowd_ord": r.get("crowd_ord"), "golden": r.get("golden_ticket"),
                        "praise": r.get("tony_praise"), "n_beats": r.get("n_beats"),
                        "words": r.get("word_count")})
    return out


def rubric(entry: dict) -> dict:
    """The scoring rubric — same for real and generated minutes."""
    d = entry.get("delivery") or {}
    laughs = entry.get("laugh_events") or []
    dur_s = (entry.get("duration_ms") or 60000) / 1000
    wpm = d.get("wpm") or 0
    laugh_rate = len(laughs) / max(dur_s / 10, 0.1)  # laughs per 10s
    # pace: standup sweet spot ~140-220 wpm (KT corpus), penalize extremes
    pace = max(0.0, 1.0 - abs(wpm - 180) / 140.0)
    # laugh density: ~1.2/10s = corpus mean -> 1.0 score
    laugh_s = min(1.0, laugh_rate / 1.2)
    # verify: word-match if present (generated only)
    verify = entry.get("rubric", {}).get("verify_match")
    # crowd prior if performer known
    cf = crowd_for(entry.get("profile", {}).get("performer", ""))
    crowd = (sum(c["crowd_ord"] for c in cf) / len(cf) / 5.0) if cf else None
    parts = {"pace": round(pace, 3), "laugh_density": round(laugh_s, 3)}
    if verify is not None:
        parts["verify"] = round(verify, 3)
    if crowd is not None:
        parts["crowd_prior"] = round(crowd, 3)
    composite = round(sum(parts.values()) / len(parts), 3)
    return {"parts": parts, "composite": composite,
            "laugh_rate_per_10s": round(laugh_rate, 2),
            "note": "same rubric for real + generated; verify only on generated"}


def ingest(clip: str, performer: str = "", setname: str = "", skip_asr: bool = False):
    import cf_asr, voice_judge
    clip_p = Path(clip)
    entry_id = setname or f"{norm(performer or 'unknown')}_{clip_p.stem}"[:60]
    # decode to wav for judge
    tmp_wav = Path(f"/tmp/opencode/_ds_{entry_id}.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clip_p),
                    "-ac", "1", "-ar", "16000", str(tmp_wav)], check=True,
                   capture_output=True, timeout=120)
    m = voice_judge.measure(tmp_wav)
    words, laughs, punches = [], [], []
    if not skip_asr:
        d = cf_asr.transcribe(tmp_wav)
        words = d.get("words") or []
        laughs = d.get("laugh_events") or []
        punches = d.get("punch_candidates") or []
    dur = m["duration_ms"]
    wpm = len(words) / (dur / 1000) * 60 if words and dur else None
    crowd = crowd_for(performer) if performer else []
    entry = {
        "id": entry_id, "source": str(clip_p), "duration_ms": dur,
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "words": words, "laugh_events": laughs, "punch_candidates": punches,
        "delivery": {"wpm": round(wpm, 1) if wpm else None,
                     "pitch_std": m["pitch"].get("std_semitones"),
                     "median_hz": m["pitch"].get("median_hz"),
                     "dyn_db": m["intensity"].get("p90_p10_db"),
                     "centroid": (m.get("brightness") or {}).get("spectral_centroid_hz")},
        "profile": {"performer": performer, "crowd_history": crowd[:5]},
        "audio_copy": None,
        "verdict": None, "verdict_note": "",
    }
    entry["rubric"] = rubric(entry)
    DS.mkdir(parents=True, exist_ok=True)
    # archive audio
    dest = DS / f"{entry_id}.wav"
    subprocess.run(["cp", str(tmp_wav), str(dest)], check=True)
    entry["audio_copy"] = str(dest)
    (DS / f"{entry_id}.json").write_text(json.dumps(entry, indent=2))
    tmp_wav.unlink(missing_ok=True)
    r = entry["rubric"]
    print(f"INGEST {entry_id}: {len(words)} words, {len(laughs)} laughs, "
          f"wpm={entry['delivery']['wpm']}, composite={r['composite']}")
    return entry


def rescore(entry_id: str):
    p = DS / f"{entry_id}.json"
    e = json.loads(p.read_text())
    e["rubric"] = rubric(e)
    p.write_text(json.dumps(e, indent=2))
    print(f"{entry_id}: composite={e['rubric']['composite']} parts={e['rubric']['parts']}")


def compare(gen_entry: str, real_entry: str):
    g = json.loads((DS / f"{gen_entry}.json").read_text())
    r = json.loads((DS / f"{real_entry}.json").read_text())
    print(f"{'':22} {'GENERATED':>12} {'REAL':>12}")
    for k in ("wpm", "pitch_std", "dyn_db", "centroid"):
        gv = (g.get("delivery") or {}).get(k)
        rv = (r.get("delivery") or {}).get(k)
        print(f"{k:22} {str(gv):>12} {str(rv):>12}")
    print(f"{'laugh_rate/10s':22} {g['rubric']['laugh_rate_per_10s']:>12} {r['rubric']['laugh_rate_per_10s']:>12}")
    print(f"{'composite':22} {g['rubric']['composite']:>12} {r['rubric']['composite']:>12}")


def listing():
    for p in sorted(DS.glob("*.json")):
        e = json.loads(p.read_text())
        print(f"{e['id']:40} wpm={str((e.get('delivery') or {}).get('wpm')):6} "
              f"laughs={len(e.get('laugh_events') or []):3} "
              f"composite={e['rubric']['composite']} verdict={e.get('verdict') or 'pending'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest")
    ing.add_argument("clip")
    ing.add_argument("--performer", default="")
    ing.add_argument("--setname", default="")
    ing.add_argument("--skip-asr", action="store_true")
    sc = sub.add_parser("score")
    sc.add_argument("entry_id")
    cp = sub.add_parser("compare")
    cp.add_argument("generated")
    cp.add_argument("real")
    sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "ingest":
        ingest(args.clip, args.performer, args.setname, args.skip_asr)
    elif args.cmd == "score":
        rescore(args.entry_id)
    elif args.cmd == "compare":
        compare(args.generated, args.real)
    elif args.cmd == "list":
        listing()
