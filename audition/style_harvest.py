"""Style harvester: scribe clips → delivery_style.v1 profile.

One method per comedian/archetype:
  scribe (word timings [+ laughs] [+ delivery acoustics]) →
  per-clip metrics → aggregated style JSON → engine recipe (Fish knobs).

Inputs:
  - theory/scribe/<clip>.json  — {words:[{text,start,end}], text?}
  - theory/scribe/<clip>_laughs.json — {laughs:[{t}]} (optional anchors)
  - voicelab/dataset/real_*.json — may carry delivery {wpm,pitch_std,
    median_hz,dyn_db,centroid} measured by theory/acoustic.py

Output: voicelab/styles/<slug>.json (delivery_style.v1)

Self-test: python3 style_harvest.py louis --check
  (harvested louis vs theory/LOUIS-FORMULA.md targets)

Usage:
  python3 style_harvest.py <slug> --scribes theory/scribe/<glob>
  python3 style_harvest.py --archetype deadpan --members norm,casey
  python3 style_harvest.py <slug> --check
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import re
import statistics
import time
from pathlib import Path

HERE = Path(__file__).parent
SCRIBE = HERE.parent / "theory" / "scribe"
DATASET = HERE / "voicelab" / "dataset"
STYLES = HERE / "voicelab" / "styles"
STYLES.mkdir(exist_ok=True)

VOWEL = re.compile(r"[aeiouy]+", re.I)

# LOUIS-FORMULA.md (13 clips, hand-measured) — harvester self-test targets.
# pause ladder slack is wide: scribe hold-excess vs Praat energy-regions are
# related but not identical estimators. dynamics/pitch need real audio.
CHECKS = {
    "louis": {"wpm": 163, "syll_per_s": 3.94, "speed_scale": 0.85,
              "ladder": [0.6, 1.5, 1.0], "ladder_slack": 0.45,
              "wpm_slack": 20, "syll_slack": 0.4, "speed_slack": 0.08},
}

# archetype → default cue vocabulary (deadpan priors: Niebuhr/Logi + repo work)
ARCHETYPE_CUES = {
    "deadpan": {"allowed": ["[indifferent]", "[calm]", "[serious]"],
                "forbidden": ["[excited]", "[happy]", "[manic]", "[energetic]"]},
    "sincere_storyteller": {"allowed": ["[calm]", "[confessional]", "[warm]"],
                            "forbidden": ["[manic]", "[aggressive]"]},
    "mock_indignant": {"allowed": ["[frustrated]", "[indignant]", "[excited]"],
                       "forbidden": ["[calm]", "[whispering]"]},
    "manic_swing": {"allowed": ["[excited]", "[manic]", "[indifferent]"],
                    "forbidden": []},
    "roast_bravado": {"allowed": ["[confident]", "[aggressive]", "[amused]"],
                      "forbidden": ["[whispering]", "[sad]"]},
    "whimsical_float": {"allowed": ["[dreamy]", "[playful]", "[confident]"],
                        "forbidden": ["[angry]", "[aggressive]"]},
}


def load_scribe(path: Path) -> dict:
    return json.loads(path.read_text())


def find_dataset_delivery(words: list[dict]) -> dict | None:
    """Match a scribe against voicelab/dataset real_* by word overlap; return
    its measured delivery block if close enough."""
    if not words:
        return None
    head = " ".join(w["text"].lower() for w in words[:12])
    for f in DATASET.glob("real_*.json"):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        dw = d.get("words") or []
        dhead = " ".join(w["text"].lower() for w in dw[:12])
        if head and dhead and head[:60] == dhead[:60]:
            return d.get("delivery")
    return None


def syllables(text: str) -> int:
    return max(1, len(VOWEL.findall(text)))


def clip_metrics(scribe: dict, laughs: list[float] | None = None) -> dict:
    words = [w for w in scribe.get("words", []) if w.get("end", 0) > w.get("start", 0)]
    if len(words) < 8:
        raise ValueError(f"too few words ({len(words)})")

    # CF-whisper scribes quantize word spans inside phrases; real pauses hide
    # inside duration outliers. holds = words > max(0.9s, 3x median duration);
    # their excess over median is the pause time they carry.
    durs = [w["end"] - w["start"] for w in words]
    med_dur = statistics.median(durs)
    hold_thresh = max(0.9, 3 * med_dur)
    holds = [(w, d) for w, d in zip(words, durs) if d > hold_thresh]
    excess_total = sum(d - med_dur for _, d in holds)

    total_s = words[-1]["end"] - words[0]["start"]
    speech_s = max(total_s - excess_total, 1.0)
    n_syll = sum(syllables(w["text"]) for w in words)

    # pause ladder from hold excesses (the hidden pauses)
    excesses = sorted(d - med_dur for _, d in holds)
    pct = lambda q: excesses[min(len(excesses) - 1, max(0, int(q * len(excesses))))] if excesses else 0.0

    # also visible gaps (quantized scribes: rare, but keep)
    gaps = [b["start"] - a["end"] for a, b in zip(words, words[1:])
            if b["start"] - a["end"] > 0.15]

    hold = None
    if laughs:
        latencies = []
        for t in laughs:
            prev = [w for w in words if w["end"] <= t]
            if prev:
                latencies.append(round(t - prev[-1]["end"], 2))
        if latencies:
            hold = {"react_median_s": round(statistics.median(latencies), 2),
                    "n_anchors": len(latencies)}

    acoustics = find_dataset_delivery(words)

    return {
        "n_words": len(words),
        "duration_s": round(total_s, 2),
        "wpm": round(len(words) / total_s * 60, 1),
        "speech_wpm": round(len(words) / speech_s * 60, 1),
        "syll_per_s": round(n_syll / speech_s, 2),
        "pause_s": {
            "p25": round(pct(0.25), 2),
            "median": round(pct(0.50), 2),
            "p75": round(pct(0.75), 2),
            "p90": round(pct(0.90), 2),
            "mean": round(statistics.mean(excesses), 2) if excesses else 0.0,
            "n_holds": len(holds),
            "n_gaps": len(gaps),
            "total_s": round(excess_total, 1),
        },
        "hold": hold,
        "acoustics": acoustics,
    }


def engine_recipe(agg: dict, archetype: str | None) -> dict:
    p = agg["pause_s"]
    setup, pre_punch, tag = p["p25"], p["p75"], p["median"]
    if pre_punch <= 0 or setup <= 0:
        coupling = 1.35
    else:
        coupling = round(min(2.0, pre_punch / max(setup, 0.1)), 2)

    # fish natural ≈ 4.63 syll/s at speed 1.0 (louis: 3.94 → 0.85)
    syll = agg["syll_per_s"]["median"] if isinstance(agg["syll_per_s"], dict) else agg["syll_per_s"]
    speed = round(max(0.4, min(1.4, syll / 4.63)), 2)

    ac = agg.get("acoustics") or {}
    dyn = ac.get("dyn_db")
    volume = round((dyn - 25.0) * 0.28, 1) if dyn else 0.0

    cues = ARCHETYPE_CUES.get(archetype or "", {"allowed": ["[neutral]", "[calm]"],
                                                "forbidden": []})
    return {
        "wpm": round(agg["wpm"]["median"] if isinstance(agg["wpm"], dict) else agg["wpm"]),
        "syll_per_s": syll,
        "speed_scale": speed,
        "temperature": 0.55,
        "pause_ladder": [setup, pre_punch, tag],
        "pause_jitter": 0.25,
        "coupling_ratio": coupling,
        "volume_db": volume,
        "dynamics_db": dyn,
        "pitch_std_st": ac.get("pitch_std"),
        "f0_median_hz": ac.get("median_hz"),
        "centroid_hz": ac.get("centroid"),
        "emotion_cues": cues["allowed"],
        "emotion_forbidden": cues["forbidden"],
    }


def harvest(slug: str, scribe_paths: list[Path], archetype: str | None = None) -> dict:
    clips = []
    for sp in sorted(scribe_paths):
        s = load_scribe(sp)
        lf = sp.with_name(sp.stem + "_laughs.json")
        laughs = None
        if lf.exists():
            laughs = [x["t"] for x in json.loads(lf.read_text()).get("laughs", [])]
        m = clip_metrics(s, laughs)
        m["clip"] = sp.stem
        clips.append(m)

    wpms = [c["speech_wpm"] for c in clips]
    sylls = [c["syll_per_s"] for c in clips]
    paus = [c["pause_s"]["mean"] for c in clips]
    agg = {
        "n_clips": len(clips),
        "wpm": {"median": round(statistics.median(wpms), 1),
                "iqr": [round(min(wpms), 1), round(max(wpms), 1)]},
        "syll_per_s": {"median": round(statistics.median(sylls), 2),
                       "iqr": [round(min(sylls), 2), round(max(sylls), 2)]},
        "pause_s": {
            "p25": round(statistics.median(c["pause_s"]["p25"] for c in clips), 2),
            "median": round(statistics.median(c["pause_s"]["median"] for c in clips), 2),
            "p75": round(statistics.median(c["pause_s"]["p75"] for c in clips), 2),
            "p90": round(statistics.median(c["pause_s"]["p90"] for c in clips), 2),
            "mean": round(statistics.median(paus), 2),
        },
        "hold": next((c["hold"] for c in clips if c.get("hold")), None),
        "acoustics": next((c["acoustics"] for c in clips if c.get("acoustics")), None),
    }

    # median clip → recipe (uses aggregate pause stats + its acoustics)
    recipe = engine_recipe(agg, archetype)

    # technique mix from scribe texts via delivery_engine tagger
    import sys
    sys.path.insert(0, str(HERE))
    from delivery_engine import segment_beats, tag_mechanism
    mech: dict[str, int] = {}
    total = 0
    for sp in scribe_paths:
        text = " ".join(w["text"] for w in load_scribe(sp).get("words", []))
        for b in segment_beats(text):
            mech[b["mechanism"]] = mech.get(b["mechanism"], 0) + 1
            total += 1
    technique_mix = {k: round(v / max(total, 1), 3) for k, v in
                     sorted(mech.items(), key=lambda x: -x[1])}

    return {
        "schema": "delivery_style.v1",
        "slug": slug,
        "archetype": archetype,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "measured": agg,
        "engine_recipe": recipe,
        "technique_mix": technique_mix,
        "clips": [c["clip"] for c in clips],
        "method": "style_harvest.py (word-timing scribes; acoustics from dataset delivery blocks when present)",
        "per_clip": clips,
    }


def check_louis(style: dict) -> None:
    t = CHECKS["louis"]
    r = style["engine_recipe"]
    ok = True

    def row(name, got, want, slack):
        nonlocal ok
        if got is None:
            print(f"  {name:16s} SKIP (needs audio)")
            return
        if want is None:
            print(f"  {name:16s} got={got} (no scribe acoustics; from audio when present)")
            return
        diff = abs(got - want)
        mark = "ok" if diff <= slack else "OFF"
        if diff > slack:
            ok = False
        print(f"  {name:16s} {mark} got={got} want={want} slack={slack}")

    row("wpm", r["wpm"], t["wpm"], t["wpm_slack"])
    row("syll_per_s", r["syll_per_s"], t["syll_per_s"], t["syll_slack"])
    row("speed_scale", r["speed_scale"], t["speed_scale"], t["speed_slack"])
    for i, name in enumerate(["setup", "pre_punch", "tag"]):
        row(f"ladder_{name}", r["pause_ladder"][i], t["ladder"][i], t["ladder_slack"])
    row("dynamics_db", r.get("dynamics_db"), None, 0)
    row("pitch_std_st", r.get("pitch_std_st"), None, 0)
    print("self-test:", "PASS" if ok else "NEEDS-EARS")


def main():
    ap = argparse.ArgumentParser(description="Style harvester")
    ap.add_argument("slug", nargs="?", help="style slug (e.g. louis, norm_macdonald)")
    ap.add_argument("--scribes", help="glob of scribe files (default: theory/scribe/<slug>*)")
    ap.add_argument("--archetype", help="archetype tag (deadpan, sincere_storyteller, ...)")
    ap.add_argument("--check", action="store_true", help="self-test against known formula")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.slug:
        ap.error("slug required")

    pattern = args.scribes or str(SCRIBE / f"{args.slug}*")
    paths = [Path(p) for p in globmod.glob(pattern) if "_laughs" not in p]
    if not paths:
        raise SystemExit(f"no scribes match {pattern}")

    style = harvest(args.slug, paths, args.archetype)
    print(f"{args.slug}: {style['measured']['n_clips']} clips | "
          f"wpm {style['engine_recipe']['wpm']} | "
          f"ladder {style['engine_recipe']['pause_ladder']} | "
          f"speed {style['engine_recipe']['speed_scale']}")

    if args.check and args.slug in CHECKS:
        check_louis(style)

    if args.dry_run:
        print(json.dumps({k: v for k, v in style.items() if k != "per_clip"}, indent=1))
        return

    out = STYLES / f"{args.slug}.json"
    out.write_text(json.dumps(style, indent=1))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
