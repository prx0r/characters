"""World operations — ONE of three distinct operations.

A World wraps residents, relationships, lore, news and leagues. It knows
WHERE and WHO-WITH-WHOM. It never generates lines (graphs do that) or
stages shows (formats do that) — it supplies cast, context and standings.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class World:
    """Residents + relationships + lore + news + league for one world_id."""

    def __init__(self, world_id: str):
        self.id = world_id
        import store as _store
        conn = _store.connect()
        try:
            r = conn.execute("SELECT * FROM worlds WHERE world_id=?", (world_id,)).fetchone()
            self.meta = dict(r) if r else {"world_id": world_id, "name": world_id.title()}
        finally:
            conn.close()

    def _conn(self):
        import store as _store
        return _store.connect()

    def residents(self, role: str = "") -> list[dict]:
        conn = self._conn()
        try:
            q = "SELECT * FROM world_residents WHERE world_id=?"
            args: list = [self.id]
            if role:
                q += " AND role=?"
                args.append(role)
            return [dict(r) for r in conn.execute(q, args).fetchall()]
        finally:
            conn.close()

    def cast(self, character_ids: list[str]) -> list:
        """CharacterGraphs for explicit ids (validates they exist)."""
        from graph_ops import CharacterGraph
        return [CharacterGraph(cid) for cid in character_ids]

    def storytellers(self) -> list:
        """Resident storytellers as graphs (Stage 1: repertoire holders)."""
        from graph_ops import CharacterGraph
        out = []
        for r in self.residents(role="storyteller"):
            if r.get("character_id"):
                try:
                    out.append(CharacterGraph(r["character_id"]))
                except Exception:
                    pass
        return out

    def relationships(self) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM world_relationships WHERE world_id=?", (self.id,)).fetchall()]
        finally:
            conn.close()

    def lore(self, limit: int = 10) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT claim, source FROM world_lore WHERE world_id=? ORDER BY created_at DESC LIMIT ?",
                (self.id, limit)).fetchall()]
        finally:
            conn.close()

    def news(self, limit: int = 5) -> list[dict]:
        """Fresh Earth-feed items for inspiration (claims starting EARTH FEED)."""
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT claim, source FROM world_lore WHERE world_id=? AND claim LIKE 'EARTH FEED%'"
                " ORDER BY created_at DESC LIMIT ?", (self.id, limit)).fetchall()]
        finally:
            conn.close()

    def repertoire(self, resident: str) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM repertoire WHERE world_id=? AND resident=?", (self.id, resident)).fetchall()]
        finally:
            conn.close()

    def league(self) -> list[dict]:
        """Arena standings scoped to this world's performers.

        Joins audition contenders via their character's resident row, so only
        world members table. Theory tags ride along for mechanism boards.
        """
        import json as _j
        conn = self._conn()
        try:
            res = {r["character_id"] for r in conn.execute(
                "SELECT character_id FROM world_residents WHERE world_id=? AND character_id<>''",
                (self.id,)).fetchall()}
            rows = []
            for a in conn.execute("SELECT * FROM auditions WHERE status='ready'").fetchall():
                a = dict(a)
                if a["character_id"] not in res:
                    continue
                ops = _j.loads(a["operator_ids"])
                wins = conn.execute("SELECT COUNT(*) FROM arena_votes v JOIN arena_contenders c"
                                    " ON c.id=v.winner_id WHERE c.kind='audition' AND c.ref=?",
                                    (a["id"],)).fetchone()[0]
                bouts = conn.execute("SELECT COUNT(*) FROM arena_votes v JOIN arena_contenders c"
                                     " ON (c.id=v.a_id OR c.id=v.b_id) WHERE c.kind='audition' AND c.ref=?",
                                     (a["id"],)).fetchone()[0]
                rows.append({"audition_id": a["id"], "character_id": a["character_id"],
                             "scenario": a["scenario_id"], "operators": ops,
                             "wins": wins, "bouts": bouts})
            return sorted(rows, key=lambda r: (-r["wins"], r["bouts"]))
        finally:
            conn.close()


def list_worlds() -> list[dict]:
    import store as _store
    conn = _store.connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM worlds").fetchall()]
    finally:
        conn.close()


def premise(world_id: str, character_id: str, mechanism: str,
            seed: int | None = None) -> dict:
    """World-grounded scenario: relationship edge x mechanism x worldview.

    Returns a scenario dict compatible with generate_minute. No generic AI
    topics: every premise grows out of a charged edge in the world graph
    (or world lore/news when edges run dry). One situation that can evolve
    across a whole minute — never a grab-bag of claims.
    """
    import random as _r
    rng = _r.Random(seed)
    w = World(world_id)
    rels = w.relationships()
    rel = rng.choice(rels) if rels else {}
    charge = rel.get("charge", "") if rel else ""
    lore = w.lore(3)
    news = w.news(1)
    lore_bit = (lore[0]["claim"][:140] if lore else "")
    news_bit = (news[0]["claim"][:140] if news else "")
    mech_fuel = {
        "status_invert": "the low outrank the high, on paper, tonight",
        "identity_contradict": "the mask and the face swap jobs mid-scene",
        "rigidify": "procedure worshipped until it backfires",
        "double_interpret": "one order, two readings, both obeyed",
        "literalize": "a figure of speech comes true on stage",
        "repeat_variation": "the same demand returns bigger each time",
        "unmask": "a disguise fails at the worst line",
        "expose_self_blindness": "self-incrimination filed as testimony",
        "false_analogy": "a metaphor with teeth bites back",
    }.get(mechanism, mechanism.replace("_", " "))
    comic_model = (f"{charge}. Tonight, {mech_fuel}. "
                   f"{character_id.replace('_', ' ')} must act, in one continuous scene.").strip()
    return {"id": f"{world_id}_{mechanism}_{rng.randint(100, 999)}",
            "comic_claim": comic_model,
            "comic_model": comic_model,
            "reality_model": lore_bit or w.meta.get("shared_worldview", ""),
            "central_question": f"what breaks first: the rule or the ruler?",
            "tensions": [charge] if charge else [],
            "derivations": [{"premise": news_bit or lore_bit or comic_model}],
            "theories": [mechanism],
            "world_id": world_id, "edge": {k: rel.get(k, "") for k in ("a", "b", "charge")}}
