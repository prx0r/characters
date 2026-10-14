"""Compose a freaks pack's delivery.json into real per-beat audio.

fish (free tier): one call per beat with its [emotion] cue + punch emphasis,
then exact pause_after_ms silence between beats, stitched to one wav.
edge: same beat structure, tags stripped (edge has no cue support).

Usage:
  python3 compose_set.py kappa-kyle-cucumber-debt            # fish if key, else edge
  python3 compose_set.py kappa-kyle-cucumber-debt --tts edge # force edge
  python3 compose_set.py --all --dry-run                     # plan only, $0
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
FREAKS = REPO / "freaks"
sys.path.insert(0, str(HERE))

import fish_tts  # noqa: E402


def _load_env() -> None:
    fish_tts._load_env()


def pick_tts(want: str) -> str:
    _load_env()
    if want in ("fish", "edge"):
        return want
    return "fish" if fish_tts.get_key() else "edge"


def render_edge(beat: dict, audition_id: str, voice_id: str) -> dict:
    import tts_provider
    text = fish_tts.strip_directions((beat.get("text") or "").strip())
    expr = ((beat.get("performance") or {}).get("expression") or "")
    # map expression to edge rate/pitch roughly (no cues on edge)
    pace = ((beat.get("speech") or {}).get("pace") or "normal")
    rate = "+15%" if pace in ("fast", "rapid_fire") else (
        "-10%" if pace in ("slow",) else "+0%")
    bid = beat.get("id") or "b0"
    out = HERE / "audio" / f"{audition_id}-{bid}.mp3"
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        out.unlink()
    asyncio.run(tts_provider._edge_save(text, voice_id, out, rate=rate))
    dur = tts_provider._ffprobe_ms(out) or tts_provider.estimate_ms(text, 0)
    return {"path": str(out), "duration_ms": dur,
            "provenance": f"edge-tts|rate={rate}|cue-stripped", "sha256": None}


def compose(slug: str, tts: str = "auto", modulator: str | None = None,
            out_name: str | None = None, dry_run: bool = False) -> dict:
    pack = FREAKS / slug
    delivery = json.loads((pack / "delivery.json").read_text())
    character = json.loads((pack / "character.json").read_text())
    beats = delivery.get("beats") or []
    if not beats:
        raise RuntimeError(f"{slug}: no beats in delivery.json")
    tts = pick_tts(tts)
    mod = modulator or (character.get("modulator_range") or [""])[0]
    voice_id = ((character.get("voice") or {}).get("voice_id")
                or ((delivery.get("voice") or {}).get("voice_id"))
                or "en-US-GuyNeural")
    ref_id, refs = (fish_tts.voice_for_pack(slug) if tts == "fish"
                    else (None, None))
    vibe = (character.get("vibe") or "").strip()
    pron_entries = ((character.get("voice") or {}).get("pron")) or {}
    pron = fish_tts.pron_dict(pron_entries) if pron_entries else None

    plan = []
    for b in beats:
        expr = ((b.get("performance") or {}).get("expression") or "")
        cue = fish_tts.expression_cue(expr, mod) if tts == "fish" else ""
        pp = fish_tts.prosody_for_beat(b) if tts == "fish" else {}
        plan.append({"id": b.get("id"), "type": b.get("type"),
                     "pause_after_ms": b.get("pause_after_ms", 300),
                     "cue": cue or "-", "speed": pp.get("speed"),
                     "volume_db": pp.get("volume"), "chars": len(b.get("text") or "")})
    if dry_run:
        return {"slug": slug, "tts": tts, "voice": voice_id, "vibe": vibe,
                "pron_words": len(pron_entries), "zero_shot": bool(refs or ref_id),
                "beats": plan,
                "total_pause_ms": sum(p["pause_after_ms"] for p in plan[:-1])}

    t0 = time.time()
    parts, provenance = [], []
    for b in beats:
        bid = b.get("id") or "b0"
        if tts == "fish":
            r = fish_tts.render_beat(slug, b, voice=ref_id, modulator=mod,
                                     references=refs, vibe=vibe,
                                     pronunciation=pron)
        else:
            r = render_edge(b, f"{slug}", voice_id)
        parts.append(Path(r["path"]))
        provenance.append({"beat": bid, "path": r["path"],
                           "duration_ms": r["duration_ms"],
                           "provenance": r["provenance"]})
        import random
        pause = int(b.get("pause_after_ms", 600) or 600)
        nxt = beats[beats.index(b) + 1] if b is not beats[-1] else {}
        ntype = (nxt.get("type") or "")
        # dpv (Timing-is-Everything, 828 sets): setups establish ~0.6s;
        # STRATEGIC COUPLING: pause ~1.5s before punch/closer (pros extend
        # 41% before high-surprise; amateur 27%; our old 500ms = amateur)
        if ntype in ("punchline", "closer"):
            pause = max(pause, 1500)
        elif ntype == "tag":
            pause = max(pause, 1000)
        # pause variability (r=0.35 with votes): jitter gaps +-25% deterministically
        pause = int(pause * (0.85 + 0.3 * ((hash(str(b.get("id"))) % 100) / 100)))
        if pause > 0 and b is not beats[-1]:
            parts.append(fish_tts.silence_wav(pause))

    out = pack / (out_name or "set.wav")
    fish_tts.stitch_wav(parts, out)
    actual = fish_tts._ffprobe_ms(out)
    claimed = int((delivery.get("metadata") or {}).get("total_duration_ms") or 0)

    # auto-verify: CF whisper on the stitched render, word-match vs intended
    verify = None
    try:
        import cf_asr
        intended = " ".join((b.get("text") or "") for b in beats)
        heard = cf_asr.transcribe(out)
        heard_words = {w["text"].lower().strip(".,!?;:'\"") for w in heard.get("words", [])}
        intended_words = [w.lower().strip(".,!?;:'\"") for w in intended.split()
                          if w.lower().strip(".,!?;:'\"") not in ("", "crap")]
        unsaid = [w for w in intended_words if w not in heard_words]
        match = 1.0 - len(unsaid) / max(len(intended_words), 1)
        verify = {"asr": heard.get("asr"), "match": round(match, 3),
                  "unsaid": unsaid[:10],
                  "laugh_events": len(heard.get("laugh_events") or [])}
        print(f"  verify: match={verify['match']} unsaid={unsaid[:5] or 'none'}")
    except Exception as e:
        verify = {"error": str(e)[:120]}

    rec = {
        "slug": slug, "tts": tts, "modulator": mod, "voice": voice_id,
        "zero_shot": bool(refs or ref_id), "beats": provenance,
        "out": str(out), "actual_ms": actual, "claimed_ms": claimed,
        "drift_ms": (actual - claimed) if (actual and claimed) else None,
        "verify": verify,
        "elapsed_s": round(time.time() - t0, 1),
        "composed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (pack / "compose.json").write_text(json.dumps(rec, indent=2) + "\n")
    return rec


def _main() -> None:
    ap = argparse.ArgumentParser(description="compose pack delivery.json to audio")
    ap.add_argument("slug", nargs="?", default=None)
    ap.add_argument("--all", action="store_true", help="compose every complete pack")
    ap.add_argument("--tts", default="auto", choices=["auto", "fish", "edge"])
    ap.add_argument("--modulator", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slugs = ([p.parent.name for p in sorted(FREAKS.glob("*/delivery.json"))]
             if args.all else [args.slug])
    if not slugs or slugs == [None]:
        ap.error("give a slug or --all")
    for slug in slugs:
        try:
            r = compose(slug, tts=args.tts, modulator=args.modulator,
                        dry_run=args.dry_run)
            if args.dry_run:
                print(f"{slug}: dry-run tts={r['tts']} beats={len(r['beats'])} "
                      f"pauses={r['total_pause_ms']}ms vibe={r.get('vibe') or '-'} "
                      f"pron={r.get('pron_words', 0)} zero_shot={r['zero_shot']}")
                for p in r["beats"]:
                    print(f"  {p['id']} {p['type']:9} cue={p['cue']:14} "
                          f"speed={p.get('speed')} vol={p.get('volume_db')}dB "
                          f"pause={p['pause_after_ms']}ms")
            else:
                print(f"{slug}: {r['out']}  {r['actual_ms']}ms "
                      f"(claimed {r['claimed_ms']}, drift {r['drift_ms']}) "
                      f"tts={r['tts']} {r['elapsed_s']}s")
        except Exception as e:
            print(f"{slug}: FAIL {e}")


if __name__ == "__main__":
    _main()
