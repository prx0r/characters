"""Performance DNA: embed real performances, define target profiles, calibrate.

Anchors (Ari, Casey) = embedded real clips → vectors in multimodal space.
Targets (Dracula, Mickey, …) = text briefs + acoustic/movement deltas.
Loop: generate Fish audio → embed → measure distance to target vs anchors.

Uses gemini-embedding-2 (multimodal: text+audio+video one space).
Key: audition/.env GEMINI_API_KEY only.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "killtony-minutes"
DNA_DIR = HERE / "performance-dna"
DNA_DIR.mkdir(exist_ok=True)

API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent"
DIM = 768  # MRL-truncated: cheap storage, little quality loss


def _key() -> str:
    k = os.getenv("GEMINI_API_KEY")
    if not k:
        raise RuntimeError("GEMINI_API_KEY missing")
    return k


def _post(body: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        API + f"?key={_key()}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def embed_text(text: str, task: str = "semantic similarity") -> list[float]:
    body = {
        "model": "models/gemini-embedding-2",
        "content": {"parts": [{"text": f"task: {task} | {text}"}]},
        "embedContentConfig": {"outputDimensionality": DIM}
    }
    r = _post(body)
    return r["embedding"]["values"]


def embed_audio_file(path: Path, prompt: str = "comedy performance delivery",
                     max_seconds: int = 170) -> list[float]:
    """Embed audio via inline base64. Trims to max_seconds with ffmpeg first."""
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "clip.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-t", str(max_seconds),
             "-ac", "1", "-ar", "16000", "-b:a", "48k", str(clip)],
            capture_output=True, timeout=120, check=True)
        data = base64.b64encode(clip.read_bytes()).decode()
    body = {
        "model": "models/gemini-embedding-2",
        "content": {"parts": [
            {"text": f"task: performance similarity | {prompt}"},
            {"inlineData": {"mimeType": "audio/mpeg", "data": data}}
        ]},
        "embedContentConfig": {"outputDimensionality": DIM}
    }
    r = _post(body, timeout=300)
    return r["embedding"]["values"]


def embed_video_file(path: Path, prompt: str = "comedy performance body language",
                     max_seconds: int = 110) -> list[float]:
    """Embed video (visual only — audio track ignored by API)."""
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-t", str(max_seconds),
             "-vf", "fps=1,scale=480:-2", "-c:v", "libx264",
             "-preset", "veryfast", "-an", str(clip)],
            capture_output=True, timeout=180, check=True)
        data = base64.b64encode(clip.read_bytes()).decode()
    body = {
        "model": "models/gemini-embedding-2",
        "content": {"parts": [
            {"text": f"task: performance similarity | {prompt}"},
            {"inlineData": {"mimeType": "video/mp4", "data": data}}
        ]},
        "embedContentConfig": {"outputDimensionality": DIM}
    }
    r = _post(body, timeout=300)
    return r["embedding"]["values"]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na * nb else 0.0


def extract_numeric_dna(stem: str) -> dict:
    """Pull acoustic + movement + timing features for a stem into one dict."""
    ac_p = OUT / f"{stem}.acoustic.json"
    gr_p = OUT / f"{stem}.granular.json"
    dna: dict = {"stem": stem}
    if ac_p.exists():
        ac = json.loads(ac_p.read_text())
        f0 = ac.get("f0", {})
        vo = ac.get("voice_quality", {})
        sp = ac.get("speech", {})
        dna["acoustic"] = {
            "f0_median": f0.get("median"),
            "f0_range": f0.get("range"),
            "jitter": vo.get("jitter"),
            "shimmer": vo.get("shimmer"),
            "speech_rate": sp.get("syllables_per_sec"),
            "pause_ratio": sp.get("pause_ratio"),
        }
    if gr_p.exists():
        gr = json.loads(gr_p.read_text())
        ws = gr.get("numeric_windows") or []
        if ws:
            import statistics as st
            def col(k):
                vals = [w.get(k) or 0.0 for w in ws]
                return {"mean": st.mean(vals), "p90": sorted(vals)[int(len(vals)*0.9)]}
            dna["movement"] = {
                "lean": col("lean_x_range"),
                "arm": col("arm_open_mean"),
                "mouth": col("mouth_wide_max"),
                "brow": col("brow_range"),
                "n_windows": len(ws),
            }
    # riff timing if present
    riff_p = OUT / f"{stem.replace('casey_rocket','casey_rocket')}_riff_db.json"
    if "casey" in stem:
        rdb_p = OUT / "casey_rocket_riff_db.json"
        if rdb_p.exists():
            rdb = json.loads(rdb_p.read_text())
            ds = rdb.get("delivery_stats", {})
            dna["timing"] = {
                "mean_pause": ds.get("mean_pause"),
                "laugh_mid_sentence_pct": ds.get("laugh_mid_sentence_pct"),
                "riff_type_counts": ds.get("riff_type_counts"),
            }
    return dna


def make_anchor(stem: str, media: Path | None = None, label: str = "") -> dict:
    """Build a full anchor profile: numeric DNA + embeddings of real media."""
    anchor = {"kind": "anchor", "stem": stem, "label": label or stem,
              "numeric": extract_numeric_dna(stem), "embeddings": {}}
    if media and media.exists():
        try:
            anchor["embeddings"]["audio"] = embed_audio_file(media, f"{label or stem} standup comedy delivery")
            print(f"  audio embedded ({len(anchor['embeddings']['audio'])}d)")
        except Exception as e:
            print(f"  audio embed failed: {e}")
        try:
            anchor["embeddings"]["video"] = embed_video_file(media, f"{label or stem} stage movement")
            print(f"  video embedded ({len(anchor['embeddings']['video'])}d)")
        except Exception as e:
            print(f"  video embed failed: {e}")
    # text identity from existing analysis if available
    fa_p = OUT / "casey_rocket_FULL_analysis.json"
    if "casey" in stem and fa_p.exists():
        fa = json.loads(fa_p.read_text())
        cf = fa.get("character_formulation", {})
        desc = f"{cf.get('vocal_signature','')}. {cf.get('physical_signature','')}. {cf.get('comedy_worldview','')}"
        try:
            anchor["embeddings"]["text"] = embed_text(desc, "comedy character description")
            print(f"  text embedded ({len(anchor['embeddings']['text'])}d)")
        except Exception as e:
            print(f"  text embed failed: {e}")
    out_p = DNA_DIR / f"anchor_{stem}.json"
    out_p.write_text(json.dumps(anchor, indent=1))
    print(f"anchor saved: {out_p}")
    return anchor


def make_target(name: str, vocal: str, physical: str, worldview: str,
                acoustic_deltas: dict | None = None,
                movement_deltas: dict | None = None,
                direction_seed: str = "") -> dict:
    """Define a target character profile in the same space as anchors."""
    desc = f"{vocal}. {physical}. {worldview}"
    target = {
        "kind": "target", "name": name,
        "description": desc,
        "vocal_signature": vocal,
        "physical_signature": physical,
        "worldview": worldview,
        "acoustic_deltas": acoustic_deltas or {},
        "movement_deltas": movement_deltas or {},
        "direction_seed": direction_seed,
        "embeddings": {}
    }
    try:
        target["embeddings"]["text"] = embed_text(desc, "comedy character description")
        print(f"  target text embedded ({len(target['embeddings']['text'])}d)")
    except Exception as e:
        print(f"  text embed failed: {e}")
    out_p = DNA_DIR / f"target_{name.lower().replace(' ','_')}.json"
    out_p.write_text(json.dumps(target, indent=1))
    print(f"target saved: {out_p}")
    return target


def calibrate(target_name: str, generated_audio: Path, prompt: str = "") -> dict:
    """Embed generated Fish audio, measure distance to target + all anchors."""
    tp = DNA_DIR / f"target_{target_name.lower().replace(' ','_')}.json"
    if not tp.exists():
        raise RuntimeError(f"no target profile: {tp}")
    target = json.loads(tp.read_text())
    gen_emb = embed_audio_file(generated_audio, prompt or f"{target_name} comedy delivery")
    result = {
        "target": target_name,
        "generated_audio": str(generated_audio),
        "distances": {}
    }
    t_emb = target.get("embeddings", {}).get("text")
    if t_emb:
        result["distances"]["to_target_text"] = round(cosine(gen_emb, t_emb), 4)
    for ap in sorted(DNA_DIR.glob("anchor_*.json")):
        a = json.loads(ap.read_text())
        for modality, emb in a.get("embeddings", {}).items():
            key = f"to_{a['stem']}_{modality}"
            result["distances"][key] = round(cosine(gen_emb, emb), 4)
    result["embedding"] = gen_emb
    out_p = DNA_DIR / f"calibration_{target_name.lower().replace(' ','_')}_{generated_audio.stem}.json"
    out_p.write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result.items() if k != "embedding"}, indent=1))
    return result


def main():
    ap = argparse.ArgumentParser(description="Performance DNA framework")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("anchor", help="build anchor from real media")
    a.add_argument("stem")
    a.add_argument("--media", type=Path, default=None)
    a.add_argument("--label", default="")

    t = sub.add_parser("target", help="define target character profile")
    t.add_argument("name")
    t.add_argument("--vocal", required=True)
    t.add_argument("--physical", required=True)
    t.add_argument("--worldview", required=True)
    t.add_argument("--direction-seed", default="")

    c = sub.add_parser("calibrate", help="measure generated audio vs target+anchors")
    c.add_argument("target_name")
    c.add_argument("generated_audio", type=Path)

    e = sub.add_parser("embed", help="quick embed text/audio/video")
    e.add_argument("kind", choices=["text", "audio", "video"])
    e.add_argument("path_or_text")

    args = ap.parse_args()
    if args.cmd == "anchor":
        make_anchor(args.stem, args.media, args.label)
    elif args.cmd == "target":
        make_target(args.name, args.vocal, args.physical, args.worldview,
                    direction_seed=args.direction_seed)
    elif args.cmd == "calibrate":
        calibrate(args.target_name, args.generated_audio)
    elif args.cmd == "embed":
        if args.kind == "text":
            v = embed_text(args.path_or_text)
        elif args.kind == "audio":
            v = embed_audio_file(Path(args.path_or_text))
        else:
            v = embed_video_file(Path(args.path_or_text))
        print(f"{len(v)}d, first5: {[round(x,4) for x in v[:5]]}")


if __name__ == "__main__":
    main()
