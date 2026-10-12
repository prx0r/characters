"""Show builders — react, podcast, shanty, surrounded.

All template-written from persona packs (deterministic, offline, free).
Mimo may draft where the gateway allows; template is the floor that always
works. Every show keeps a transcript record beside its audio.
"""
from __future__ import annotations

import time
from pathlib import Path

import formats as F


def _char(cid: str) -> dict:
    import generate as _gen
    return _gen.get_character(cid)


def _first(cid: str, char: dict) -> str:
    return (char.get("name") or cid).split()[0].rstrip(",")


def react(target_audition: dict, reactor_ids: list[str]) -> dict:
    """Agents watch a set, react per beat. Graphs react, format stages."""
    from graph_ops import CharacterGraph
    beats = target_audition.get("beats") or []
    order, transcript, parts = [], [], []
    tag = f"react_{int(time.time())}"
    for rid in reactor_ids:
        g = CharacterGraph(rid)
        order.append({"reactor": rid, "lines": []})
        for b in beats:
            t = b.get("type", "setup")
            short = " ".join(b.get("text", "").split()[:7])
            if t == "punchline":
                line = f"{g.first} here. HA! {short} — writing that one down."
            elif t == "closer":
                line = f"{g.first} verdict: {short}. mine was better."
            elif t == "tag":
                line = f"{g.first} again? {short}. noted."
            else:
                line = f"{g.first} watching. {short}. go on."
            a = g.say(line, f"{tag}_{rid}_{b.get('id')}")
            parts.append(a["path"])
            order[-1]["lines"].append({"at_ms": b.get("start_ms", 0), "text": line,
                                       "audio": a["path"], "dur": a["duration_ms"]})
            transcript.append({"at_ms": b.get("start_ms", 0), "reactor": rid, "text": line})
    out = F.AUDIO / f"{tag}.mp3"
    m = F.concat_mp3(parts, out)
    rec = {"format": "react", "target": target_audition.get("id"),
           "reactors": reactor_ids, "audio": m, "order": order, "transcript": transcript}
    F.save_record("react", rec)
    return rec


def podcast(topic: str, cast_ids: list[str], rounds: int = 2,
            world_id: str = "") -> dict:
    """Clique roundtable: any graphs, optional world fuel.

    Distinct operations: graphs speak (graph_ops), world supplies news/lore
    context (world_ops), this function only stages the format (formats).
    """
    from graph_ops import CharacterGraph
    cast = [CharacterGraph(cid) for cid in cast_ids]
    fuel = ""
    if world_id:
        from world_ops import World
        w = World(world_id)
        news = w.news(2)
        if news:
            fuel = " Fresh in: " + "; ".join(n["claim"][:100] for n in news)
    tag = f"pod_{int(time.time())}"
    host = cast[0]
    guests = cast[1:] or cast[:1]
    script = [(host, f"Welcome back. Tonight: {topic}.{fuel} {host.first} presiding.")]
    for r in range(rounds):
        for g in guests:
            script.append((g, f"{g.first} responding. {g.deal[:120]} Frankly I am blind to "
                              f"{', '.join(g.blind_spots[:1])}, but on {topic}: absolutely."))
    script.append((host, f"{host.first} closing. We solved nothing. Same time next week."))
    parts, transcript = [], []
    for i, (g, line) in enumerate(script):
        a = g.say(line, f"{tag}_{i}")
        parts.append(a["path"])
        transcript.append({"speaker": g.id, "text": line, "audio": a["path"]})
    out = F.AUDIO / f"{tag}.mp3"
    m = F.concat_mp3(parts, out)
    rec = {"format": "podcast", "topic": topic, "cast": cast_ids,
           "world": world_id, "audio": m, "transcript": transcript}
    F.save_record("podcast", rec)
    return rec


def shanty(world_id: str, lines_per_verse: int = 4) -> dict:
    """World anthem in verse, chanted over a synthesized click-track bed."""
    import store as _store
    conn = _store.connect()
    try:
        w = conn.execute("SELECT * FROM worlds WHERE world_id=?", (world_id,)).fetchone()
        res = [dict(r) for r in conn.execute(
            "SELECT * FROM world_residents WHERE world_id=?", (world_id,)).fetchall()]
        rels = [dict(r) for r in conn.execute(
            "SELECT * FROM world_relationships WHERE world_id=?", (world_id,)).fetchall()]
    finally:
        conn.close()
    if not w:
        raise ValueError(f"unknown world {world_id}")
    w = dict(w)
    lore_bits = (w.get("lore") or "").split(". ")[:2]
    calls = [f"Way-hey, {r['canon_id'].replace('-', ' ')}!" for r in res[:3]]
    resps = ([r["charge"] for r in rels[:3]] or ["heave away, heave away"])
    verses = []
    for i in range(lines_per_verse):
        verses.append(("call", calls[i % len(calls)]))
        verses.append(("resp", resps[i % len(resps)] + ", heave away!"))
    verses.append(("call", f"So raise a cup to {w['name']}, lads!"))
    verses.append(("resp", "heave away home!"))
    tag = f"shanty_{world_id}_{int(time.time())}"
    parts, transcript = [], []
    for i, (kind, line) in enumerate(verses):
        a = F.speak_line("rudy_dulce_hvac", line, f"{tag}_{i}")
        parts.append(a["path"])
        transcript.append({"kind": kind, "text": line})
    voice = F.AUDIO / f"{tag}_voice.mp3"
    F.concat_mp3(parts, voice)
    bed = F.click_bed(F.AUDIO / f"{tag}_bed.mp3",
                      sum(1 for _ in parts) * 2200, bpm=100)
    out = F.AUDIO / f"{tag}.mp3"
    F.mix_voice_bed(voice, bed, out)
    import hashlib
    rec = {"format": "shanty", "world": world_id, "audio": {"path": str(out)},
           "lore_used": lore_bits, "transcript": transcript}
    F.save_record("shanty", rec)
    return rec


def surrounded(human_prompt: str, mob_ids: list[str]) -> dict:
    """Text-first Surrounded: mob graphs answer the human. Scored by got_me."""
    from graph_ops import CharacterGraph
    tag = f"sur_{int(time.time())}"
    rounds = []
    for mid in mob_ids:
        g = CharacterGraph(mid)
        rounds.append({"mob": mid,
                       "text": f"{g.first} stepping up. You said: {human_prompt[:140]}. "
                               f"{g.misrule or 'I hear you'}. All I want is {g.want or 'victory'} — and your laugh.",
                       "got_me": 0})
    rec = {"format": "surrounded", "prompt": human_prompt, "mob": mob_ids, "rounds": rounds}
    p = F.save_record("surrounded", rec)
    rec["record_path"] = str(p)
    return rec
