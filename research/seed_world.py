"""Seed a world from DeityDB entities (standardized WHO mine).

Reads /root/deitydb sqlite (entities + attribute claims; relationship tables
are empty in this copy, so edges are curated per world in CURATED_EDGES).
Writes:
  canon/<slug>/canon.json   — paraphrased reference block (never verbatim)
  world rows                — worlds + residents via store.py
Body = DiceBear seed (deterministic, free). Funny = edge+mechanism generator
+ arena duels. Standardized testing = fixed scenario battery (SEED_BATTERY).

Usage:
  PYTHONPATH=audition python3 research/seed_world.py --world greek --tradition Greek --limit 12
  PYTHONPATH=audition python3 research/seed_world.py --world greek --entities ENT_ZEUS,ENT_HERA
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "audition"))
DEITYDB = Path("/root/deitydb/backups/deitydb_pre_v2_1_62.sqlite")

# FIXED scenario battery: same seeds -> same scenarios (controlled comparison:
# same scenario, different graphs). Resolved once, pinned here.
SEED_BATTERY = [7, 11, 22, 33, 42]

# Curated classical edges (paraphrased common knowledge; provenance marked).
# Small-N, high-quality — the DeityDB copy has no populated edge table.
CURATED_EDGES = {
    "greek": [
        ("zeus", "hera", "spouse", "sovereign vs wronged spouse: thunder vs ledger"),
        ("zeus", "poseidon", "sibling", "sky vs sea: jurisdiction war over everything wet"),
        ("zeus", "hades", "sibling", "sky vs underworld: the brother who never visits"),
        ("zeus", "athena", "parent", "father vs favorite: born from his skull, outshines him"),
        ("apollo", "artemis", "sibling", "sun vs moon: twins competing over the same sky"),
        ("aphrodite", "ares", "consort", "beauty vs war: the alliance nobody admits"),
        ("hera", "athena", "rival", "wife vs favorite-child: proxy war by etiquette"),
    ],
}

WORLD_BIBLES = {
    "greek": ("Olympus runs on protocol older than the sky and pettier than a group chat. "
              "Every god has a domain (their excuse), a spouse or sibling (their problem), "
              "and a mortal habit they deny. Home crowd knows the myths; break canon and they boo."),
}


def slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-").replace("--", "-")


def fetch_entities(tradition: str, ids: list[str], limit: int) -> list[dict]:
    con = sqlite3.connect(f"file:{DEITYDB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    if ids:
        q = f"SELECT * FROM entities WHERE entity_id IN ({','.join('?' * len(ids))})"
        rows = con.execute(q, ids).fetchall()
    else:
        rows = con.execute("SELECT * FROM entities WHERE tradition=? LIMIT ?", (tradition, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        claims = [dict(x) for x in con.execute(
            "SELECT claim_type,claim_value,confidence FROM claims WHERE entity_id=?", (d["entity_id"],)).fetchall()]
        d["claims"] = claims
        out.append(d)
    con.close()
    return out


def canon_block(ent: dict, world_id: str) -> dict:
    """Paraphrase entity row into OUR canon schema. No verbatim source text."""
    domains = [c["claim_value"] for c in ent["claims"] if c["claim_type"] == "domain"]
    tags = [c["claim_value"] for c in ent["claims"] if c["claim_type"] == "tag"]
    name = ent["canonical_name"]
    return {
        "slug": slugify(name), "name": name, "world": world_id,
        "classification": f"{ent.get('tradition')} {ent.get('entity_type') or ''} (public-domain myth; paraphrased, no verbatim)",
        "core_lore_paraphrased": [
            f"Domains: {'; '.join(domains) or ent.get('primary_domains') or 'unspecified'}.",
            f"Standing: {ent.get('category') or ent.get('entity_type') or 'figure'}; tags: {', '.join(tags[:6]) or 'none'}.",
        ],
        "behavior_social": [],
        "comedy_engine": {"angles": [], "seeds": []},
        "provenance": {"deitydb_id": ent["entity_id"], "confidence": ent.get("evidence_confidence"),
                       "rule": "paraphrase only; blind_spots unknown until evidenced (import rule §3)"},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--tradition", default="")
    ap.add_argument("--entities", default="")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    import store
    ids = [x for x in args.entities.split(",") if x]
    ents = fetch_entities(args.tradition, ids, args.limit)
    print(f"entities: {len(ents)}")
    conn = store.connect()
    try:
        conn.execute("INSERT OR IGNORE INTO worlds (world_id,name,lore,shared_worldview,created_at)"
                     " VALUES (?,?,?,?,?)",
                     (args.world, args.world.title(), WORLD_BIBLES.get(args.world, ""), "", time.time()))
        for ent in ents:
            slug = slugify(ent["canonical_name"])
            cdir = ROOT / "canon" / slug
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "canon.json").write_text(json.dumps(canon_block(ent, args.world), indent=1))
            try:
                conn.execute("INSERT OR IGNORE INTO world_residents (world_id,canon_id) VALUES (?,?)",
                             (args.world, slug))
            except Exception as e:
                print("resident err", slug, e)
        for a, b, rel, charge in CURATED_EDGES.get(args.world, []):
            conn.execute("INSERT OR IGNORE INTO world_relationships (id,world_id,a,b,charge,created_at)"
                         " VALUES (?,?,?,?,?,?)",
                         (store.new_id("rel"), args.world, a, b, f"{rel}: {charge}", time.time()))
        conn.commit()
    finally:
        conn.close()
    print("canon blocks + world rows written; edges:", len(CURATED_EDGES.get(args.world, [])))
    print("SEED_BATTERY (fixed scenarios):", SEED_BATTERY)


if __name__ == "__main__":
    main()
