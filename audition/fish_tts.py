"""Fish Audio TTS: s2.1-pro-free default, drama-3 behind FISH_PAID=1.

Env: FISH_API_KEY in audition/.env. AUDITION_TTS=fish to opt in.
Directions ride inside the text (Drama 3 / s2 bracket syntax) — no schema change.

Per-beat path (compose_set.py): each delivery.json beat renders separately
with its own [emotion] cue + [emphasis] on the punch word, then stitches with
exact pause_after_ms silence — the timing contract becomes real audio.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
AUDIO_DIR = HERE / "audio"
AUDIO_DIR.mkdir(exist_ok=True)
API = "https://api.fish.audio/v1/tts"

SIGNATURE_DIRECTIONS = {
    "angry": "angry, sharp, blaming named individuals",
    "condescending": "condescending, slow and patient, explaining as if to children",
    "drunk_on_power": "expansive, drunk on power, saying the quiet part proudly",
    "exhausted": "exhausted, barely finding the energy to finish",
    "paranoid": "paranoid, speaking too fast, glancing at the doors",
    "sad": "sad, deflated, voice trailing off",
    "manic": "manic, fast, eyes wide, unstoppable momentum",
    "subservient": "subservient, eager to please, voice slightly too high",
    "smug": "smug, savoring every word, faint smirk in the voice",
    "panicked": "panicked, words tumbling out, tripping over consonants",
}

PAIRED_TAGS = ("<whisper>", "<emphasis>", "<soft>", "<fast>", "<slow>",
               "<stress>", "<forceful>")

# delivery.json beat.performance.expression -> S2 bracket cue (docs: 64 emotions).
# empty string = no cue (neutral beats stay clean).
EXPRESSION_TAGS = {
    "deadpan": "[indifferent]",
    "neutral": "",
    "annoyed": "[frustrated]",
    "confused": "[confused]",
    "grin": "[delighted]",
    "surprised": "[surprised]",
    "smug": "[proud]",
    "paranoid": "[anxious]",
    "angry": "[angry]",
    "sad": "[sad]",
    "manic": "[excited]",
    "panicked": "[nervous]",
    "subservient": "[embarrassed]",
    "exhausted": "[tired]",
    "whisper": "[whispering]",
}

_TAG_RE = re.compile(
    r"\[(?:happy|sad|angry|excited|calm|nervous|confident|surprised|satisfied|"
    r"delighted|scared|worried|upset|frustrated|depressed|empathetic|embarrassed|"
    r"disgusted|moved|proud|relaxed|grateful|curious|sarcastic|disdainful|unhappy|"
    r"anxious|hysterical|indifferent|uncertain|doubtful|confused|disappointed|regretful|"
    r"guilty|ashamed|jealous|envious|hopeful|optimistic|pessimistic|nostalgic|lonely|"
    r"bored|contemptuous|sympathetic|compassionate|determined|resigned|whispering|soft tone|"
    r"in a hurry tone|shouting|screaming|emphasis|sigh|laugh|chuckle|groan|"
    r"[^\[\]]{0,80})\]|</?(?:whisper|emphasis|soft|fast|slow|stress|forceful)>",
    re.IGNORECASE)


def _load_env() -> None:
    envf = HERE / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def strip_directions(text: str) -> str:
    """Remove bracket cues and word tags — for edge-tts/piper fallback paths."""
    return _TAG_RE.sub("", text).strip()


def expression_cue(expression: str, modulator: str = "") -> str:
    """Beat expression -> bracket cue; falls back to modulator signature bracket."""
    cue = EXPRESSION_TAGS.get((expression or "").lower(), "")
    if cue:
        return cue
    if modulator and modulator in SIGNATURE_DIRECTIONS:
        return f"[{SIGNATURE_DIRECTIONS[modulator]}]"
    return ""


def emphasize_last(text: str) -> str:
    """Wrap the final word in [emphasis] — punch/closer hold."""
    w = text.rstrip().split()
    if len(w) < 2:
        return text
    tail = w[-1].rstrip(".,!?;:")
    punct = w[-1][len(tail):]
    w[-1] = f"[emphasis]{tail}{punct}"
    return " ".join(w)


def render_beat(audition_id: str, beat: dict, voice: str | None = None,
                modulator: str = "", mod: dict | None = None, paid: bool = False,
                emphasis: bool = True, references: list[dict] | None = None,
                vibe: str = "", pronunciation: list[dict] | None = None) -> dict:
    """One beat -> one fish call with its own cue + punch emphasis + prosody.

    beat: delivery.json beat dict (text, performance.expression, type,
    speech.emphasis/pace). emphasis applied on punchline/tag/closer when
    speech.emphasis >= 0.8 or type is a punch family. prosody.speed from
    beat pace; volume nudge by beat type; temperature from character vibe.
    """
    _load_env()
    text = (beat.get("text") or "").strip()
    if not text:
        raise RuntimeError("empty beat text")
    expr = ((beat.get("performance") or {}).get("expression") or "").strip()
    cue = expression_cue(expr, modulator or "")
    emph = float(((beat.get("speech") or {}).get("emphasis")) or 0.0)
    btype = (beat.get("type") or "")
    if emphasis and (emph >= 0.8 or btype in ("punchline", "closer", "tag")):
        text = emphasize_last(text)
    directed = f"{cue} {text}".strip() if cue else text
    bid = beat.get("id") or "b0"
    return synthesize_fish(f"{audition_id}-{bid}", directed, voice=voice,
                           modulator=modulator or "neutral", mod=mod, paid=paid,
                           direction=False, references=references,
                           temperature=temperature_for(vibe),
                           prosody=prosody_for_beat(beat),
                           pronunciation=pronunciation)  # cue per beat


def silence_wav(ms: int, out: Path | None = None) -> Path:
    """Exact silence via ffmpeg anullsrc (24k mono to match edge/fish mp3 decode)."""
    ms = max(0, int(ms))
    out = out or (AUDIO_DIR / f"silence-{ms}.wav")
    if out.exists() and out.stat().st_size > 100:
        return out
    dur = f"{ms / 1000.0:.3f}"
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", dur, "-c:a", "pcm_s16le", str(out)],
        capture_output=True, timeout=30)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"silence gen failed: {r.stderr.decode()[:200]}")
    return out


def stitch_wav(parts: list[Path], out: Path) -> Path:
    """Concat wav/mp3 parts into one wav via ffmpeg concat demuxer."""
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:a", "pcm_s16le", str(out)],
        capture_output=True, timeout=120)
    lst.unlink(missing_ok=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"stitch failed: {r.stderr.decode()[:200]}")
    return out


def zero_shot_refs(wav_paths: list[Path], texts: list[str] | None = None) -> list[dict]:
    """Candidate wavs -> TTSRequest.references payload (zero-shot cloning)."""
    refs = []
    for i, p in enumerate(wav_paths):
        refs.append({
            "audio": base64.b64encode(p.read_bytes()).decode(),
            "format": "wav",
            "text": (texts[i] if texts and i < len(texts) else None),
        })
    return refs


def _ffprobe_ms(path: Path) -> int | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", str(path)],
                           capture_output=True, text=True, timeout=15)
        return int(float(r.stdout.strip()) * 1000)
    except Exception:
        return None


def estimate_ms(text: str, pauses_ms: int = 0) -> int:
    return int(len(text.split()) / 2.6 * 1000) + pauses_ms


def get_key() -> str | None:
    _load_env()
    return os.getenv("FISH_API_KEY") or None


def model_for(paid: bool = False) -> str:
    """ALWAYS s2.1-pro-free ($0). Paid models (drama-3) are hard-removed until
    the owner explicitly re-enables them — do not add paid paths here."""
    return "s2.1-pro-free"


def directions_for_modulator(modulator: str, mod: dict | None = None) -> str:
    """Modulator JSON -> Drama 3 plain-language direction string."""
    if mod is None:
        try:
            mod = json.loads((HERE / "modulators.json").read_text()).get(modulator) or {}
        except Exception:
            mod = {}
    if modulator in SIGNATURE_DIRECTIONS:
        base = SIGNATURE_DIRECTIONS[modulator]
    else:
        mod = mod or {}
        perf = (mod.get("performative") or {})
        emo = (mod.get("emotional") or {})
        pace = perf.get("pace_delta", 0)
        arousal = emo.get("arousal", 0.5)
        parts = []
        if pace >= 0.1 or arousal >= 0.75:
            parts.append("fast, high energy")
        elif pace <= -0.1 or arousal <= 0.3:
            parts.append("slow, low energy")
        else:
            parts.append("measured")
        gestures = perf.get("gestures", "")
        if gestures and gestures not in ("minimal", ""):
            parts.append(f"{gestures} physically")
        if emo.get("defensiveness", 0) >= 0.7:
            parts.append("defensive edge")
        base = ", ".join(parts)
    return f"[{base}]"


def wrap_text(text: str, modulator: str, mod: dict | None = None,
              direction: bool = True) -> str:
    if not direction:
        return text
    return directions_for_modulator(modulator, mod) + " " + text


def _request(text: str, reference_id: str | None, model: str,
             fmt: str = "mp3", timeout: int = 120,
             references: list[dict] | None = None,
             temperature: float | None = None,
             prosody: dict | None = None,
             top_p: float | None = None,
             pronunciation: list[dict] | None = None) -> bytes:
    key = get_key()
    if not key:
        raise RuntimeError("FISH_API_KEY missing (audition/.env)")
    body: dict = {"text": text, "format": fmt}
    if reference_id:
        body["reference_id"] = reference_id
    if references:
        body["references"] = references
    if temperature is not None:
        body["temperature"] = max(0.0, min(1.0, float(temperature)))
    if top_p is not None:
        body["top_p"] = max(0.0, min(1.0, float(top_p)))
    if prosody:
        body["prosody"] = prosody
    if pronunciation:
        body["pronunciation_dictionary"] = pronunciation
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "model": model})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# beat pace token -> prosody.speed multiplier (API range 0.5-2.0)
PACE_SPEED = {"slow": 0.8, "normal": 1.0, "fast": 1.2, "rapid_fire": 1.45,
              "dragging": 0.65}
# beat type -> volume nudge in dB (punches up, setups level)
TYPE_VOLUME_DB = {"punchline": 1.5, "closer": 2.0, "tag": 1.0,
                  "setup": 0.0, "premise": 0.0, "escalation": 1.0}


def prosody_for_beat(beat: dict) -> dict:
    """Beat delivery params -> API prosody block (speed + volume)."""
    pace = ((beat.get("speech") or {}).get("pace") or "normal").lower()
    btype = (beat.get("type") or "setup").lower()
    p = {"speed": PACE_SPEED.get(pace, 1.0),
         "volume": TYPE_VOLUME_DB.get(btype, 0.0)}
    return p


def pron_dict(entries: dict[str, str]) -> list[dict]:
    """{word: replacement} -> inline pronunciation dictionary payload."""
    items = [{"key": k, "value": v, "case_sensitive": False}
             for k, v in list(entries.items())[:5000]]
    return [{"items": items}] if items else []


# vibe -> TTS expressiveness. Deadpan = low temp (consistent, flat);
# manic = high temp (varied). Judge loop calibrated these bands.
VIBE_TEMPERATURE = {
    "deadpan": 0.35, "sad": 0.4, "exhausted": 0.4, "relaxed": 0.5,
    "smug": 0.55, "paranoid": 0.6, "neutral": 0.6,
    "sarcastic": 0.65, "angry": 0.7,
    "manic": 0.9, "gleeful": 0.85, "panicked": 0.8,
}


def temperature_for(vibe: str) -> float | None:
    return VIBE_TEMPERATURE.get((vibe or "").lower())


def mary_prosody(modulator: str) -> dict | None:
    """MARY emotion-module predictions for a modulator (human-speech prior).
    precedence: measured cue_tempo > MARY > defaults. MARY supplies
    pitch_direction (valence) which we cannot measure on TTS."""
    try:
        m = json.loads((HERE / "voicelab" / "mary_model.json").read_text())
        return m["modulators"].get(modulator)
    except Exception:
        return None


def valence_direction(modulator: str) -> str:
    """Pitch-direction hint from valence (MARY accent-shape rule):
    valence<0 falling, >0 rising. Maps to fish pitch_shift language."""
    mp = mary_prosody(modulator)
    return (mp or {}).get("pitch_direction", "flat")


def voice_for_pack(slug: str) -> tuple[str | None, list[dict] | None]:
    """Pack slug -> (reference_id, zero-shot references) from voice.fish pick."""
    try:
        c = json.loads((HERE.parent / "freaks" / slug / "character.json").read_text())
    except Exception:
        return None, None
    fish = ((c.get("voice") or {}).get("fish")) or {}
    if fish.get("reference_id"):
        return fish["reference_id"], None
    wav_rel = fish.get("wav")
    if wav_rel:
        wav = HERE.parent / wav_rel
        if wav.exists():
            return None, zero_shot_refs([wav], [fish.get("reference_text") or None])
    return None, None


def synthesize_fish(audition_id: str, text: str, voice: str | None = None,
                    modulator: str = "", mod: dict | None = None,
                    paid: bool = False, direction: bool = True,
                    references: list[dict] | None = None,
                    temperature: float | None = None,
                    prosody: dict | None = None,
                    pronunciation: list[dict] | None = None) -> dict:
    model = model_for(paid=paid)
    directed = wrap_text(text, modulator or "neutral", mod, direction=direction)
    ref = voice or os.getenv("FISH_VOICE_ID") or None
    out = AUDIO_DIR / f"{audition_id}-fish.mp3"
    if out.exists():
        out.unlink()
    try:
        data = _request(directed, ref, model, references=references,
                        temperature=temperature, prosody=prosody,
                        pronunciation=pronunciation)
    except Exception as e:
        raise RuntimeError(f"fish tts ({model}) failed: {str(e)[:200]}")
    if len(data) < 2000:
        raise RuntimeError(f"fish tts returned too little audio ({len(data)}B)")
    out.write_bytes(data)
    dur = _ffprobe_ms(out) or estimate_ms(directed)
    return {"path": str(out), "duration_ms": dur,
            "provenance": f"fish-tts:{model}" + ("+direction" if direction else "")
                          + ("+ffprobe" if _ffprobe_ms(out) else "+estimated"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "model": model, "directed": direction}


def list_public_voices_sample() -> list[dict]:
    """Drama 3 cast from docs — safe defaults, no key needed to remember."""
    return [
        {"name": "Adrian", "language": "EN-US", "id": "bf322df2096a46f18c579d0baa36f41d"},
        {"name": "Delia", "language": "EN-US", "id": "c70cfb98867a4bfb9ae20d2401257b92"},
        {"name": "Sheila", "language": "EN-US", "id": "f3a2b90078d54a65af4b95f63bc7798e"},
    ]
