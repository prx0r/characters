"""Distill performance corpus (gemini segments + Praat prosody) into vibe bands.

Input:  theory/killtony-minutes/*.gemini.json  (emotion arcs, vocal params)
        theory/prosody/*/prosody.json          (pitch Hz, variability st, intensity)
Output: theory/vibe-bands.json — per-emotion target stats + per-performer
        calibration blocks for the judge loop. Stats only. Never emits
        transcript text or joke content — delivery model, not material.

Usage: python3 theory/distill_dna.py
"""
from __future__ import annotations

import json
import statistics as stats
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "vibe-bands.json"

# Performer calibration sets (prosody clip prefix -> performer tag).
# Delivery stats only; stage-persona hypothesis, never the real person.
PERFORMERS = {
    "ari_matti": {"prosody_prefixes": ("kt704", "kt715", "kt728"),
                  "gemini_globs": ("kt7*_gemini.gemini.json",)},
    "casey_rocket": {"prosody_prefixes": ("casey_rocket",),
                     "gemini_globs": ("casey_rocket*_gemini.gemini.json",)},
}

# gemini pace token -> numeric-ish bucket for aggregation
PACE_MAP = {"rapid_fire": 1.0, "fast": 0.8, "normal": 0.5, "slow": 0.25, "dragging": 0.1}
PITCH_SHIFT = {"rise": 1, "drop": -1, "flat": 0, "spike": 1, "fall": -1}


def _gemini_samples(globs: tuple[str, ...] = ("*.gemini.json",)) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    seen: set[Path] = set()
    for g in globs:
        for p in sorted((HERE / "killtony-minutes").glob(g)):
            if p in seen:
                continue
            seen.add(p)
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            for seg in d.get("segments") or []:
                emo = (seg.get("emotion") or "").lower()
                voc = seg.get("vocal") or {}
                if not emo:
                    continue
                out.setdefault(emo, []).append({
                    "energy": float(voc.get("energy") or 0.5),
                    "pace": PACE_MAP.get(str(voc.get("pace") or "normal"), 0.5),
                    "pitch_shift": PITCH_SHIFT.get(str(voc.get("pitch_shift") or "flat"), 0),
                    "intensity": float(seg.get("emotion_intensity") or 0.5),
                    "source": p.stem,
                })
    return out


def _prosody_stats(prefixes: tuple[str, ...] | None = None) -> list[dict]:
    rows = []
    for p in sorted((HERE / "prosody").glob("*/prosody.json")):
        if prefixes and not p.parent.name.startswith(prefixes):
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        m = d.get("metrics") or {}
        pitch = m.get("pitch_hz") or {}
        rows.append({
            "clip": p.parent.name,
            "pitch_var_st": (m.get("pitch_variability_semitones")
                             or (d.get("trend_metrics") or {}).get("pitch_variability_semitones")),
            "pitch_median_hz": pitch.get("median"),
            "intensity_std_db": m.get("intensity_db", {}).get("std"),
            "intensity_range_db": (d.get("trend_metrics") or {}).get("intensity_range_db"),
        })
    return [r for r in rows if r.get("pitch_var_st") is not None]


def _performer_block(name: str, spec: dict) -> dict:
    """Delivery-model block for one performer (stats only, never material)."""
    gem = _gemini_samples(spec["gemini_globs"])
    mix = {emo: len(rows) for emo, rows in sorted(gem.items())}
    total = sum(mix.values()) or 1
    energies = [r["energy"] for rows in gem.values() for r in rows]
    paces = [r["pace"] for rows in gem.values() for r in rows]
    pros = _prosody_stats(spec["prosody_prefixes"])
    top = sorted(mix.items(), key=lambda kv: -kv[1])[:3]
    brief = (f"Comedy delivery model (stage persona hypothesis, not the real person): "
             f"{' then '.join(e for e, _ in top)} arc. "
             f"Pitch variability target {_band([r['pitch_var_st'] for r in pros]).get('mid')} semitones; "
             f"median pitch around {_band([r['pitch_median_hz'] for r in pros if r.get('pitch_median_hz')]).get('mid')} Hz. "
             f"Delivery swings between measured setups and sharp high-energy spikes.")
    return {
        "emotion_mix": mix, "emotion_mix_pct": {k: round(100 * v / total) for k, v in mix.items()},
        "energy": _band(energies), "pace": _band(paces),
        "prosody": {
            "pitch_var_st": _band([r["pitch_var_st"] for r in pros]),
            "pitch_median_hz": _band([r["pitch_median_hz"] for r in pros if r.get("pitch_median_hz")]),
            "intensity_std_db": _band([r["intensity_std_db"] for r in pros if r.get("intensity_std_db") is not None]),
            "clips": pros,
        },
        "voice_design_extra": brief[:600],
        "note": "Delivery stats only. No transcript, no joke content, not the real person.",
    }


def _band(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    vals = sorted(vals)
    lo = vals[max(0, int(len(vals) * 0.15))]
    hi = vals[min(len(vals) - 1, int(len(vals) * 0.85))]
    return {"n": len(vals), "lo": round(lo, 2), "mid": round(stats.median(vals), 2),
            "hi": round(hi, 2)}


def distill() -> dict:
    gem = _gemini_samples()
    vibes = {}
    for emo, rows in sorted(gem.items()):
        vibes[emo] = {
            "energy": _band([r["energy"] for r in rows]),
            "pace": _band([r["pace"] for r in rows]),
            "pitch_shift_mean": round(sum(r["pitch_shift"] for r in rows) / len(rows), 2),
            "intensity": _band([r["intensity"] for r in rows]),
            "n_segments": len(rows),
            "sources": sorted({r["source"] for r in rows}),
        }
    pros = _prosody_stats()
    corpus = {
        "pitch_var_st": _band([r["pitch_var_st"] for r in pros if r["pitch_var_st"] is not None]),
        "pitch_median_hz": _band([r["pitch_median_hz"] for r in pros if r.get("pitch_median_hz")]),
        "intensity_std_db": _band([r["intensity_std_db"] for r in pros if r.get("intensity_std_db")]),
        "clips": pros,
    }
    performers = {name: _performer_block(name, spec) for name, spec in PERFORMERS.items()}
    doc = {
        "version": "vibe-bands.v1",
        "method": "distill_dna.py — gemini segment emotions + praat prosody stats",
        "note": "Delivery target bands only. No transcript content. "
                "Use: voice_judge compares rendered audio stats against these.",
        "vibes": vibes,
        "corpus_prosody": corpus,
        "performers": performers,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


if __name__ == "__main__":
    d = distill()
    print(f"wrote {OUT}")
    print(f"vibes: {', '.join(sorted(d['vibes']))}  "
          f"prosody clips: {len(d['corpus_prosody']['clips'])}")
