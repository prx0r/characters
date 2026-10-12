"""Tavern interop — our characters as V2 PNG cards, community cards as contenders.

Spec: chara_card_v2 (chara chunk) + ccv3 dual-write for V3 readers.
Portrait: DiceBear PNG per character seed. Lore: canon -> character_book.
No new services; tavern_card lib + Pillow already on the box.
"""
from __future__ import annotations

import base64
import io
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent


def _pack(character_id: str) -> dict | None:
    import generate as _gen
    try:
        chars = {c["id"]: c for c in _gen.list_characters()}
    except Exception:
        return None
    for c in chars.values():
        if c["id"] == character_id:
            return c
    # direct freak-pack load for ids outside the picker roster
    import generate as _g2
    slug = character_id.replace("_", "-")
    return _g2.load_freak_character(slug)


def _ascii(s: str, n: int) -> str:
    return "".join(c for c in (s or "") if ord(c) < 128)[:n]


def export_card(character_id: str) -> tuple[bytes, str]:
    """(png_bytes, filename) Tavern V2 card for one of ours."""
    from tavern_card import write_png_card
    import generate as _gen
    ch = _pack(character_id)
    if not ch:
        raise ValueError(f"unknown character {character_id}")
    raw = ch.get("raw") or {}
    persona = raw.get("persona") or {}
    dc = raw.get("dramatic_core") or ch
    facts = persona.get("facts") or ch.get("traits") or []
    blinds = (dc.get("blind_spots") if isinstance(dc, dict) else None) or ch.get("blind_spots") or []
    book_entries = []
    for key in (ch.get("threads") or [])[:4]:
        book_entries.append({"keys": key.split()[:3], "content": _ascii(f"Lore thread: {key}.", 200),
                             "enabled": True, "insertion_order": 100,
                             "position": "before_char"})
    card = {"spec": "chara_card_v2", "spec_version": "2.0", "data": {
        "name": _ascii(ch.get("name", character_id), 120),
        "description": _ascii(persona.get("deal") or ch.get("deal", ""), 1200),
        "personality": _ascii(("Facts: " + "; ".join(facts[:6]) +
                               ". Blind spots: " + ", ".join(blinds[:3]) +
                               ". Rule: " + (raw.get("misinterpretation_rule", "") or "")), 1800),
        "scenario": "Pogtown Comedy Club audition. Perform a 60-second stand-up set.",
        "first_mes": _ascii(f"Yes. I am {ch.get('name', character_id)}. {persona.get('deal', '') or ch.get('deal', '')}", 500),
        "mes_example": _ascii("{{user}}: Warm up the crowd. {{char}}: " + (persona.get("interview_style", "") or "deadpan"), 300),
        "creator": "pogtown", "character_version": str(raw.get("seed_version", "1")),
        "tags": ["comedy", "pogtown"],
        "character_book": {"name": _ascii(f"{character_id} canon", 80), "entries": book_entries}}}
    style = {"no_nose_nolan": "personas",
             "reptilian_ralph_middle_management": "adventurer",
             "rudy_dulce_hvac": "bottts"}.get(character_id, "adventurer")
    try:
        with urllib.request.urlopen(
                f"https://api.dicebear.com/10.x/{style}/png?seed={character_id}&size=512",
                timeout=30) as r:
            face = r.read()
    except Exception:
        face = b""
    png = write_png_card(card, template_png=face if face[:8].startswith(b"\x89PNG") else None)
    return png, f"{character_id}-card.png"


def _read_png_card(raw: bytes) -> dict:
    """Minimal V2/V3 tEXt reader (ccv3 first, then chara; zTXt supported).
    Avoids third-party quirks; spec: base64(utf-8(json))."""
    import struct
    import zlib
    import base64 as _b64
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return json.loads(raw.decode("utf-8"))
    chunks = {}
    pos = 8
    while pos + 8 <= len(raw):
        ln = struct.unpack(">I", raw[pos:pos + 4])[0]
        typ = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + ln]
        if typ == b"tEXt":
            kw, _, txt = data.partition(b"\x00")
            try:
                chunks[kw.decode("latin1")] = txt.decode("latin1")
            except Exception:
                pass
        elif typ == b"zTXt":
            kw, _, rest = data.partition(b"\x00")
            try:
                chunks[kw.decode("latin1")] = zlib.decompress(rest[1:]).decode("utf-8")
            except Exception:
                pass
        pos += 12 + ln
    for key in ("ccv3", "chara"):
        if key in chunks:
            txt = "".join(chunks[key].split())
            return json.loads(_b64.b64decode(txt).decode("utf-8"))
    raise ValueError("no chara/ccv3 chunk found")


def import_card(raw: bytes, source_url: str = "") -> dict:
    """Parse community PNG/JSON. Returns normalized card + portrait bytes."""
    try:
        data = _read_png_card(raw)
    except Exception:
        from tavern_card import parse_card
        data = parse_card(raw)
    d = data.get("data", data)
    portrait = b""
    if raw[:8] == b"\x89PNG":
        portrait = raw
    book = d.get("character_book") or {}
    entries = book.get("entries", []) if isinstance(book, dict) else []
    return {"spec": data.get("spec", "?"), "name": d.get("name", "unknown"),
            "description": (d.get("description", "") or "")[:800],
            "personality": (d.get("personality", "") or "")[:800],
            "scenario": (d.get("scenario", "") or "")[:400],
            "first_mes": (d.get("first_mes", "") or "")[:400],
            "tags": (d.get("tags", "") or [])[:12] if isinstance(d.get("tags", ""), list) else [],
            "book_entries": len(entries), "source_url": source_url,
            "portrait": base64.b64encode(portrait).decode() if portrait else ""}
