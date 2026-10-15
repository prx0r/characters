"""Voice Design lab — crack Fish voice-design-1 prompts per character.

One brief per character built from character.json (persona + profile + vibe).
Iterations live in audition/voicelab/<slug>/iter-<n>/ (brief.json + cand-*.wav
+ feedback.md). Owner listens, writes feedback, we refine the instruction.

Cost: $0.01 per design request (n candidates, one request). Guarded by
FISH_SPEND_OK=1 in audition/.env — owner authorises spend by setting it.
s2.1-pro-free TTS to AUDITION the candidates is $0.

Pick: writes voice.fish block into character.json; fish_tts uses the chosen
candidate wav as a zero-shot `references` sample (no paid voice model needed).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"
API = "https://api.fish.audio/v1/voice-design"
MODEL = "voice-design-1"
COST_PER_REQ = 0.01

# Character persona → voice-design instruction ingredients.
# Never include real-person biography; stats and archetype only.
VIBE_DELIVERY = {
    "deadpan": "flat deadpan delivery, minimal pitch movement, dry",
    "manic": "fast kinetic delivery, wide pitch swings, barely contained energy",
    "paranoid": "tight wary delivery, glancing delivery, rushed confessions",
    "smug": "slow savoring delivery, pleased with every word",
    "sad": "deflated delivery, voice trailing off at phrase ends",
    "exhausted": "low-energy delivery, barely finding the energy to finish",
    "angry": "sharp frustrated delivery, blaming tone",
    "relaxed": "easy unhurried delivery, casual warmth",
}


def _load_env() -> None:
    envf = HERE / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def get_key() -> str | None:
    _load_env()
    return os.getenv("FISH_API_KEY") or None


def spend_ok() -> bool:
    _load_env()
    return os.getenv("FISH_SPEND_OK", "") == "1"


def load_pack(slug: str) -> dict:
    p = REPO / "freaks" / slug / "character.json"
    if not p.exists():
        raise RuntimeError(f"no pack: {p}")
    return json.loads(p.read_text())


def build_brief(slug: str, extra: str = "", data: dict | None = None) -> str:
    """Voice-design instruction (≤2000 chars) from the pack itself."""
    c = data or load_pack(slug)
    persona = c.get("persona", {}) or {}
    profile = c.get("profile", {}) or {}
    vibe = (c.get("vibe") or "relaxed").lower()
    deal = persona.get("deal", "")
    style = persona.get("interview_style", "")
    pace = float(profile.get("pace", 0.6))
    energy = float(profile.get("energy", 0.6))
    delivery = VIBE_DELIVERY.get(vibe, VIBE_DELIVERY["relaxed"])
    pace_w = "fast urgent pacing" if pace >= 0.85 else (
        "measured pacing" if pace >= 0.55 else "slow deliberate pacing")
    energy_w = "high-energy" if energy >= 0.75 else (
        "mid-energy" if energy >= 0.45 else "low-energy")
    parts = [
        f"Character voice for a comedy stage persona: {deal}",
        f"Speaks {style}." if style else "",
        f"Voice: {energy_w}, {pace_w}. {delivery}.",
        "Distinctive, castable, not a generic narrator. Natural spoken English.",
        extra.strip(),
    ]
    brief = " ".join(p for p in parts if p)
    return brief[:2000]


def reference_line(slug: str, data: dict | None = None) -> str:
    """Short line the candidate voices speak (≤150 chars) — a pack persona fact."""
    c = data or load_pack(slug)
    facts = (c.get("persona", {}) or {}).get("facts", []) or []
    if facts:
        line = facts[0].rstrip(".") + "."
    else:
        line = (c.get("premise") or c.get("name") or slug).rstrip(".") + "."
    return line[:150]


def design(slug: str, extra: str = "", n: int = 2, seed: int | None = None,
           speed: float = 1.0, note: str = "") -> dict:
    """One design request → iteration folder with n candidate wavs.

    Returns iteration dict. Refuses without FISH_SPEND_OK=1 (owner rule:
    ask before any spend; they set the flag to authorise a batch).
    """
    key = get_key()
    if not key:
        raise RuntimeError("FISH_API_KEY missing (audition/.env)")
    if not spend_ok():
        raise RuntimeError("FISH_SPEND_OK=1 required in audition/.env (ask-before-spend rule)")
    data = load_pack(slug)
    instruction = build_brief(slug, extra=extra, data=data)
    ref_text = reference_line(slug, data=data)
    body = {"instruction": instruction, "reference_text": ref_text,
            "language": "en", "n": max(1, min(4, int(n))), "speed": float(speed)}
    if seed is not None:
        body["seed"] = int(seed)
    t0 = time.time()
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "model": MODEL})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        hint = ""
        if e.code == 402:
            hint = (" (402: voice-design needs the API pay-as-you-go pool funded — "
                    "top up at fish.audio/app, not the web-app plan credits)")
        raise RuntimeError(f"voice-design HTTP {e.code}{hint}: {detail}")
    cands = resp.get("candidates") or []
    if not cands:
        raise RuntimeError(f"voice-design returned no candidates: {str(resp)[:200]}")

    iters = sorted(LAB.glob(f"{slug}/iter-*")) if LAB.exists() else []
    nxt = (int(iters[-1].name.split("-")[-1]) + 1) if iters else 1
    outdir = LAB / slug / f"iter-{nxt:03d}"
    outdir.mkdir(parents=True, exist_ok=True)
    files = []
    for i, cand in enumerate(cands):
        wav = outdir / f"cand-{i}.wav"
        wav.write_bytes(base64.b64decode(cand.get("audio_base64") or ""))
        files.append({"file": wav.name, "sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
                      "sample_rate": cand.get("sample_rate"),
                      "duration_ms": cand.get("duration_ms")})
    manifest = {
        "slug": slug, "iter": nxt, "model": MODEL, "instruction": instruction,
        "extra": extra, "reference_text": ref_text, "seed": seed, "speed": speed,
        "n": len(cands), "candidates": files, "note": note,
        "cost_usd": round(COST_PER_REQ, 2), "elapsed_s": round(time.time() - t0, 1),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "feedback": None,
    }
    (outdir / "brief.json").write_text(json.dumps(manifest, indent=2))
    if not (outdir / "feedback.md").exists():
        (outdir / "feedback.md").write_text(
            f"# Feedback iter-{nxt:03d} ({slug})\n\n"
            f"Instruction: {instruction}\n\n"
            f"Listen to cand-*.wav. For each candidate write: keep / kill / tweak\n"
            f"(what to change in the instruction).\n")
    return manifest


def iterations(slug: str) -> list[Path]:
    base = LAB / slug
    if not base.exists():
        return []
    return sorted(base.glob("iter-*"))


def save_feedback(slug: str, it: int, text: str) -> Path:
    d = LAB / slug / f"iter-{it:03d}"
    if not d.exists():
        raise RuntimeError(f"no iteration {it} for {slug}")
    p = d / "feedback.md"
    p.write_text(text if text.endswith("\n") else text + "\n")
    fb = json.loads((d / "brief.json").read_text())
    fb["feedback"] = {"saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "summary": text.strip().splitlines()[0][:120] if text.strip() else ""}
    (d / "brief.json").write_text(json.dumps(fb, indent=2))
    return p


def pick(slug: str, it: int, cand: int) -> dict:
    """Lock a candidate: writes voice.fish into the pack character.json."""
    d = LAB / slug / f"iter-{it:03d}"
    manifest = json.loads((d / "brief.json").read_text())
    wav = d / f"cand-{cand}.wav"
    if not wav.exists():
        raise RuntimeError(f"missing {wav}")
    cpath = REPO / "freaks" / slug / "character.json"
    c = json.loads(cpath.read_text())
    voice = c.get("voice", {}) or {}
    voice.update({
        "provider": "fish",
        "fish": {
            "method": "voice-design-1",
            "instruction": manifest["instruction"],
            "reference_text": manifest["reference_text"],
            "iteration": it, "candidate": cand,
            "wav": str(wav.relative_to(REPO)),
            "sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
            "picked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    })
    c["voice"] = voice
    cpath.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
    return voice["fish"]


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="voicecast",
                                 description="Fish voice-design lab (crack prompts per character)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief", help="print the auto-built instruction (no cost)")
    b.add_argument("slug")
    b.add_argument("--extra", default="")
    d = sub.add_parser("design", help=f"generate candidates (${COST_PER_REQ}/req)")
    d.add_argument("slug")
    d.add_argument("--extra", default="")
    d.add_argument("--n", type=int, default=2)
    d.add_argument("--seed", type=int, default=None)
    d.add_argument("--speed", type=float, default=1.0)
    d.add_argument("--note", default="")
    sub.add_parser("list", help="list iterations for a slug")
    ls = sub.add_parser("ls", help="list slugs with lab folders")
    f = sub.add_parser("feedback", help="save owner feedback on an iteration")
    f.add_argument("slug")
    f.add_argument("iter", type=int)
    f.add_argument("text", help="feedback text (keep/kill/tweak per candidate)")
    p = sub.add_parser("pick", help="lock candidate into character.json")
    p.add_argument("slug")
    p.add_argument("iter", type=int)
    p.add_argument("cand", type=int)
    args = ap.parse_args()

    if args.cmd == "brief":
        print(build_brief(args.slug, extra=args.extra))
    elif args.cmd == "design":
        m = design(args.slug, extra=args.extra, n=args.n, seed=args.seed,
                   speed=args.speed, note=args.note)
        itdir = LAB / args.slug / ("iter-%03d" % m["iter"])
        print("iter-%03d -> %s" % (m["iter"], itdir))
        print(f"cost: ${m['cost_usd']}  candidates: {m['n']}")
        for c in m["candidates"]:
            print(f"  {c['file']}  {c['duration_ms']}ms  {c['sample_rate']}Hz")
        print("owner: listen, then `feedback <slug> <iter> \"...\"`")
    elif args.cmd == "ls":
        if LAB.exists():
            for p in sorted(LAB.iterdir()):
                if p.is_dir():
                    print(p.name, len(list(p.glob("iter-*"))))
    elif args.cmd == "list":
        for p in iterations(args.slug):
            m = json.loads((p / "brief.json").read_text())
            print(f"{p.name}  n={m['n']}  extra={m.get('extra','')!r}  "
                  f"feedback={'yes' if m.get('feedback') else 'no'}")
    elif args.cmd == "feedback":
        p = save_feedback(args.slug, args.iter, args.text)
        print(f"saved {p}")
    elif args.cmd == "pick":
        v = pick(args.slug, args.iter, args.cand)
        print(f"picked iter-{v['iteration']} cand-{v['candidate']} -> "
              f"freaks/{args.slug}/character.json voice.fish")


if __name__ == "__main__":
    _main()
