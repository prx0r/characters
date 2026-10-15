"""Master experiment ledger — every A/B run auto-registers here.

Scans voicelab/ artifacts (perf_sets boards, miss ledgers, stencils,
zeroshot, verify, calibrate, domains) + audio archive -> ledger.json +
EXPERIMENTS.md. Human verdicts live in ledger.json under "verdict"
(pending until filled). The comedy-judge future reads this.

Usage: python3 ledger.py            # rebuild
       python3 ledger.py --verdict <set_id> good|bad "note"
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"
ARCHIVE = Path("/home/box/voice_engine/sets")


def build() -> dict:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    entries = {}

    for bp in sorted(LAB.glob("perf_sets/*.json")):
        if bp.name.startswith("miss_"):
            continue
        d = json.loads(bp.read_text())
        sid = f"{d['performer']}_{d['set']}"
        miss_p = LAB / "perf_sets" / f"miss_{d['set']}.json"
        miss = json.loads(miss_p.read_text()) if miss_p.exists() else {}
        segs = d.get("segments") or []
        # archive audio
        wav = Path(d.get("out") or "")
        arch = None
        if wav.exists():
            arch = ARCHIVE / f"{sid}.wav"
            if not arch.exists() or arch.stat().st_size != wav.stat().st_size:
                shutil.copy(wav, arch)
        learned = {}
        for e in miss.get("prior_updates") or {}:
            u = miss["prior_updates"][e]
            learned[e] = {"mean_wpm_err": u.get("mean_wpm_err"),
                          "suggested_speed_delta": u.get("suggest_speed_delta")}
        entries[sid] = {
            "performer": d["performer"], "set": d["set"],
            "voice": d.get("voice"), "n_segments": len(segs),
            "avg_score": round(sum(s["score"] for s in segs) / max(len(segs), 1), 2) if segs else None,
            "miss_count": miss.get("miss_count"),
            "learned_per_emotion": learned,
            "audio": str(arch) if arch else str(wav),
            "board": str(bp), "miss_ledger": str(miss_p) if miss_p.exists() else None,
            "stencil": str(LAB / "stencils" / f"{sid}.json") if (LAB / "stencils" / f"{sid}.json").exists() else None,
            "verdict": None, "verdict_note": "",
        }

    for zp in sorted(LAB.glob("zeroshot_*.json")):
        d = json.loads(zp.read_text())
        sid = f"zeroshot_{d.get('comedian')}"
        entries.setdefault(sid, {"performer": d.get("comedian"), "set": "(unseen)",
                                 "n_segments": len(d.get("segments") or [])})
        entries[sid].update({
            "zero_shot_mae": d.get("zero_shot_mae"),
            "after_adapt_mae": d.get("after_adapt_mae"),
            "board": str(zp), "verdict": None, "verdict_note": "",
        })

    for vp in sorted(LAB.glob("calibrate/*_calibrate.json")):
        d = json.loads(vp.read_text())
        sid = vp.stem
        entries.setdefault(sid, {"performer": sid.replace("_calibrate", ""), "set": "(calibration)"})
        winners = d.get("winners") or {}
        entries[sid].update({
            "calibrate_winners": {k: {"wpm": v.get("wpm"), "score": v.get("score"),
                                      "cue": v.get("cue"), "temp": v.get("temp")}
                                  for k, v in winners.items()} if isinstance(winners, dict) else None,
            "board": str(vp), "verdict": None, "verdict_note": "",
        })

    priors = LAB / "emo_priors_v2.json"
    doc = {
        "rule": "every A/B run registers; verdict pending until human fills",
        "comedy_judge_note": ("this ledger + stencils + priors = timing/delivery "
                              "ground truth for the future judge engine"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "priors_file": str(priors) if priors.exists() else None,
        "archive_dir": str(ARCHIVE),
        "entries": entries,
    }
    (LAB / "ledger.json").write_text(json.dumps(doc, indent=2))

    lines = ["# EXPERIMENTS — A/B ledger (auto-generated; verdicts pending)",
             "",
             f"Updated: {doc['updated_at']}  |  audio archive: `{ARCHIVE}`",
             "",
             "| set | performer | segs | avg_score | misses | zero-shot MAE | verdict |",
             "|---|---|---|---|---|---|---|"]
    for sid, e in sorted(entries.items()):
        lines.append(f"| {sid} | {e.get('performer','')} | {e.get('n_segments','')} | "
                     f"{e.get('avg_score','')} | {e.get('miss_count','')} | "
                     f"{e.get('zero_shot_mae') or e.get('after_adapt_mae') or ''} | "
                     f"{e.get('verdict') or 'pending'} |")
    (LAB / "EXPERIMENTS.md").write_text("\n".join(lines) + "\n")
    print(f"ledger: {len(entries)} entries -> voicelab/ledger.json + EXPERIMENTS.md")
    print(f"archive: {ARCHIVE} ({len(list(ARCHIVE.glob('*.wav')))} wavs)")
    return doc


def verdict(set_id: str, v: str, note: str = "") -> None:
    p = LAB / "ledger.json"
    d = json.loads(p.read_text())
    if set_id not in d["entries"]:
        raise RuntimeError(f"unknown set_id {set_id}")
    d["entries"][set_id]["verdict"] = v
    d["entries"][set_id]["verdict_note"] = note
    p.write_text(json.dumps(d, indent=2))
    print(f"verdict {set_id}: {v}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict", nargs=3, metavar=("SET", "GOOD_BAD", "NOTE"))
    args = ap.parse_args()
    if args.verdict:
        verdict(*args.verdict)
    else:
        build()
