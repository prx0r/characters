"""Vertical MP4 renderer — real Shorts files from audition data.

PIL compositor (aoc caption pattern: Montserrat ExtraBold, auto-shrink,
wrapped, stroked text) + ffmpeg assembly (powvid pipeline pattern:
integer-ms chunk durations, yuv420p, faststart). One PNG per caption chunk,
concat demuxer, mux the audition's real audio. No GPU, no downloads beyond
one DiceBear portrait (cached in /tmp, never in git).

Shorts grammar: portrait dominates upper frame, ONE flashing caption chunk
lower-third, name plate top, progress bar. Same layout as /watch.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
FONT = Path("/root/powvid/assets/Montserrat-ExtraBold.ttf")
W, H = 1080, 1920


def chunks(text: str, n: int = 6) -> list[str]:
    w = text.split()
    if len(w) <= n:
        return [text]
    return [" ".join(w[i:i + n]) for i in range(0, len(w), n)]


def portrait_png(character_id: str, style: str, cache: Path) -> Path | None:
    out = cache / f"{character_id}.png"
    if out.exists() and out.stat().st_size > 2000:
        return out
    try:
        url = f"https://api.dicebear.com/10.x/{style}/png?seed={character_id}&size=512"
        urllib.request.urlretrieve(url, out)
        return out if out.stat().st_size > 2000 else None
    except Exception:
        return None


def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(FONT), size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)


MOUTH_RY = {"AI": 34, "E": 22, "O": 30, "U": 18, "FV": 12, "L": 18,
            "MBP": 8, "rest": 8, "open": 38, "closed": 4}


def draw_puppet(d, svg: dict, mouth: str, cx: int = W // 2, top: int = 400, s: float = 4.0) -> None:
    """Rig puppet in PIL — same character the site performs (colors/accessory
    from rigs/*.json svg block; mouth from the viseme at frame time)."""
    skin, suit = svg.get("skin", "#6b8f5e"), svg.get("suit", "#2b3440")
    trim = svg.get("trim", "#e8e4d8")
    acc = svg.get("accessory", "none")
    u = lambda v: int(cx + v * s)
    v = lambda v: int(top + v * s)
    # torso
    d.rounded_rectangle([u(-52), v(70), u(52), v(150)], radius=14, fill=suit)
    d.rectangle([u(-10), v(70), u(10), v(150)], fill=trim)
    d.polygon([(u(0), v(82),), (u(8), v(102)), (u(0), v(128)), (u(-8), v(102))], fill="#7c1f1f")
    # head
    d.ellipse([u(-52), v(-58), u(52), v(58)], fill=skin, outline="#2c3a26", width=3)
    # brows + eyes
    d.rectangle([u(-40), v(-38), u(-10), v(-31)], fill="#2c3a26")
    d.rectangle([u(10), v(-38), u(40), v(-31)], fill="#2c3a26")
    for ex in (-25, 25):
        d.ellipse([u(ex - 14), v(-8), u(ex + 14), v(24)], fill="#f4f1e4")
        d.ellipse([u(ex - 5), v(-7), u(ex + 5), v(23)], fill="#111111")
    # mouth by viseme
    d.ellipse([u(-16), v(38 - MOUTH_RY.get(mouth, 8) // 2),
               u(16), v(38 + MOUTH_RY.get(mouth, 8) // 2)], fill="#1a0f0f")
    # accessories
    if acc == "cap":
        d.rounded_rectangle([u(-48), v(-54), u(48), v(-34)], radius=10, fill=suit)
        d.rounded_rectangle([u(30), v(-48), u(60), v(-38)], radius=5, fill=suit)
    elif acc == "crown":
        d.polygon([(u(-40), v(-48)), (u(-28), v(-76)), (u(-14), v(-52)), (u(0), v(-80)),
                   (u(14), v(-52)), (u(28), v(-76)), (u(40), v(-48))], fill=trim)
    elif acc == "bolt":
        d.polygon([(u(18), v(-90)), (u(2), v(-62)), (u(12), v(-62)), (u(0), v(-34)),
                   (u(24), v(-64)), (u(14), v(-64))], fill=trim)
    # mic stand in front
    d.rectangle([u(-3), v(100), u(3), v(190)], fill="#0c0c0c")
    d.ellipse([u(-13), v(82), u(13), v(108)], fill="#1f2937", outline="#4b5563", width=2)


def frame_png(bg, portrait, name: str, chunk: str, frac: float, path: Path,
              svg: dict | None = None, mouth: str = "rest") -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    img = Image.new("RGB", (W, H), (8, 8, 12))
    d = ImageDraw.Draw(img)
    for y in range(H):  # warm club gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(30 + 20 * t), int(18 + 12 * t), int(10 + 8 * t)))
    # curtains + spotlight cone (comedy club, same as /watch)
    for x0 in (0, W - 130):
        d.rectangle([x0, 0, x0 + 130, H], fill="#5b1414")
    d.polygon([(350, 0), (730, 0), (950, H), (130, H)], fill=(80, 62, 30))
    d.ellipse([350, 990, 730, 1050], fill=(0, 0, 0))  # floor shadow at puppet base
    draw_puppet(d, svg or {}, mouth)
    if portrait and portrait.exists() and not (svg or {}).get("skin"):
        try:
            p = Image.open(portrait).convert("RGB")
            face = p.resize((620, 620), Image.LANCZOS)
            mask = Image.new("L", (620, 620), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 620, 620], fill=255)
            img.paste(face, (230, 330), mask)
        except Exception:
            pass
    ns = 56
    nf = _font(ns)
    while d.textlength(name, font=nf) > W - 120 and ns > 28:
        ns -= 4
        nf = _font(ns)
    d.text(((W - d.textlength(name, font=nf)) // 2, 120), name, font=nf, fill=(250, 204, 21))
    size = 84
    font = _font(size)
    wrapped = _wrap(d, chunk, font, W - 160)
    while d.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)[3] > 560 and size > 40:
        size -= 6
        font = _font(size)
        wrapped = _wrap(d, chunk, font, W - 160)
    bbox = d.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)
    cx, cy = (W - bbox[2]) // 2, 1230
    d.multiline_text((cx, cy), wrapped, font=font, fill="white",
                     stroke_width=4, stroke_fill="black", spacing=10, align="center")
    d.rectangle([60, H - 60, 60 + int((W - 120) * frac), H - 44], fill=(250, 204, 21))
    img.save(path)


def render_mp4(audition: dict, out_path: Path, style: str = "adventurer",
               workdir: Path | None = None) -> dict:
    """Render audition -> 1080x1920 MP4. Returns manifest (path/sha/dur/chunks)."""
    from PIL import Image
    work = Path(workdir or tempfile.mkdtemp(prefix="render_"))
    work.mkdir(parents=True, exist_ok=True)
    beats = audition.get("beats") or []
    total_ms = audition.get("audio_duration_ms") or 60000
    name = (audition.get("character_id") or "unknown").replace("_", " ")
    face = portrait_png(audition.get("character_id", "x"), style, work)
    try:  # rig puppet colors/accessories — same character the site performs
        import stage as _stage
        rigs = {r["character_id"]: r["rig_id"] for r in _stage.list_rigs()}
        _rig = _stage.load_rig(rigs.get(audition.get("character_id", ""), "ralph")) or {}
        svg = _rig.get("svg") or {}
    except Exception:
        svg = {}
    # caption timeline: Vosk word windows (~1.6s of real speech each) so cuts
    # follow phrasing, not word counts; beat-fraction fallback without a track.
    words = _load_words(audition.get("id", ""))
    tl: list = []
    if words:
        words = sorted(words, key=lambda w: w["start_ms"])
        cur, start = [], words[0]["start_ms"]
        for w in words:
            cur.append(w["word"])
            if w["end_ms"] - start >= 1600:
                tl.append((start, " ".join(cur), _shape_at(w["start_ms"], words)))
                cur, start = [], w["end_ms"]
        if cur:
            tl.append((start, " ".join(cur), _shape_at(start, words)))
        # merge micro-fragments (<3 words) forward so no flash reads "mine i"
        merged: list = []
        for t, ch, mo in tl:
            if merged and len(merged[-1][1].split()) < 3:
                pt, pch, pmo = merged.pop()
                merged.append((pt, pch + " " + ch, pmo))
            else:
                merged.append((t, ch, mo))
        tl = merged
    else:
        for b in beats:
            dur = max(400, int(b.get("end_ms", 0)) - int(b.get("start_ms", 0)))
            chs = chunks(b.get("text", ""), 6)
            per = dur / max(1, len(chs))
            t = int(b.get("start_ms", 0))
            for ch in chs:
                tl.append((t, ch, "rest"))
                t += per
    if not tl:
        tl = [(0, name, "rest")]
    # clamp exactly to the real audio length (no dead tail)
    audio_ms = _probe_ms(Path(audition["audio_path"])) or total_ms
    tl = [(t, ch, mo) for (t, ch, mo) in tl if t < audio_ms]
    # frames
    lst = work / "list.txt"
    with open(lst, "w") as f:
        for i, (t, ch, mo) in enumerate(tl):
            nxt = tl[i + 1][0] if i + 1 < len(tl) else audio_ms
            dur_s = max(0.2, (nxt - t) / 1000)
            p = work / f"f{i:03d}.png"
            frame_png(None, face, name, ch, min(1.0, nxt / audio_ms), p, svg=svg, mouth=mo)
            f.write(f"file '{p}'\nduration {dur_s:.3f}\n")
        f.write(f"file '{work}/f{len(tl)-1:03d}.png'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-i", audition["audio_path"],
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
           "-c:a", "aac", "-t", f"{audio_ms / 1000:.3f}",
           "-movflags", "+faststart", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not out_path.exists():
        raise RuntimeError("ffmpeg failed: " + r.stderr[-600:])
    dur = _probe_ms(out_path)
    return {"path": str(out_path), "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
            "duration_ms": dur, "chunks": len(tl), "frames_dir": str(work)}


def _load_words(aud_id: str) -> list[dict] | None:
    """Vosk word track precomputed beside the audio (align.py)."""
    try:
        from align import align_words  # noqa (documents the producer)
        p = HERE / "audio" / f"{aud_id}.words.json"
        if p.exists():
            return json.loads(p.read_text())
        v = HERE / "audio" / f"{aud_id}.visemes.json"
        if v.exists():
            return [{"word": e.get("word", ""), "start_ms": e["t"], "end_ms": e["t"] + 300}
                    for e in json.loads(v.read_text()) if e.get("word")]
    except Exception:
        pass
    return None


def _shape_at(t_ms: int, words: list[dict]) -> str:
    from align import _vowel_shape
    best, bt = "rest", -1
    for w in words:
        if w["start_ms"] <= t_ms and w["start_ms"] >= bt:
            bt, best = w["start_ms"], _vowel_shape(w.get("word", ""))
    return best


def _probe_ms(p: Path) -> int:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                           capture_output=True, text=True, timeout=30)
        return int(float(r.stdout.strip()) * 1000)
    except Exception:
        return 0


def contact_sheet(mp4: Path, out: Path, n: int = 8) -> Path:
    """Tile n evenly-spaced frames — the agent's way to WATCH the set back."""
    dur = _probe_ms(mp4) / 1000
    thumbs = []
    work = mp4.parent
    for i in range(n):
        t = dur * (i + 0.5) / n
        th = work / f"th{i:02d}.png"
        subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.1f}", "-i", str(mp4),
                        "-frames:v", "1", "-vf", "scale=270:480", str(th)],
                       capture_output=True, timeout=60)
        thumbs.append(th)
    from PIL import Image
    cols, rows = 4, (n + 3) // 4
    sheet = Image.new("RGB", (270 * cols, 480 * rows), (0, 0, 0))
    for i, th in enumerate(thumbs):
        try:
            sheet.paste(Image.open(th), ((i % cols) * 270, (i // cols) * 480))
        except Exception:
            pass
    sheet.save(out)
    return out


def audio_report(audio: Path) -> dict:
    """Silences (= candidate comic pauses) + loudness. Numbers for what I can't hear."""
    rep: dict = {}
    try:
        r = subprocess.run(["ffmpeg", "-i", str(audio), "-af",
                            "silencedetect=noise=-30dB:d=0.4", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
        import re
        starts = re.findall(r"silence_start: ([\d.]+)", r.stderr)
        ends = re.findall(r"silence_end: ([\d.]+)", r.stderr)
        gaps = [(float(s), float(e)) for s, e in zip(starts, ends)]
        rep["pauses"] = [{"start": round(s, 2), "dur": round(e - s, 2)} for s, e in gaps]
        rep["n_pauses"] = len(gaps)
    except Exception as e:
        rep["pauses_error"] = str(e)[:100]
    try:
        r = subprocess.run(["ffmpeg", "-i", str(audio), "-af", "ebur128=peak=true",
                            "-f", "null", "-"], capture_output=True, text=True, timeout=120)
        import re
        m = re.findall(r"I:\s+([-\d.]+) LUFS", r.stderr)
        rep["loudness_lufs"] = float(m[-1]) if m else None
    except Exception:
        pass
    return rep
