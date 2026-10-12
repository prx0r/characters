"""Sketch from a world edge (format factory).

  PYTHONPATH=audition python3 research/world_sketch.py --world prior-family --kit worlds/prior-family/kits/evening-audit.json

Reads the edge (kit.edge a,b) from world_relationships (seed it first with
seed_world.py), runs formats.sketch_from_edge, writes
worlds/<world>/sketches/<kit id>.json and a char-lab duet script beside it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "audition"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--db", default="")
    a = ap.parse_args()
    import formats, store
    kit = json.loads((ROOT / a.kit).read_text())
    ea, eb = kit["edge"]
    conn = store.connect(a.db) if a.db else store.connect()
    try:
        row = conn.execute("SELECT * FROM world_relationships WHERE world_id=? AND ((a=? AND b=?) OR (a=? AND b=?))",
                           (a.world, ea, eb, eb, ea)).fetchone()
        res = {r["canon_id"]: dict(r) for r in conn.execute("SELECT * FROM world_residents WHERE world_id=?", (a.world,))}
        world = conn.execute("SELECT * FROM worlds WHERE world_id=?", (a.world,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise SystemExit(f"no edge {ea}-{eb} in world {a.world}; run seed_world.py --world {a.world}")
    slug = lambda node: (res.get(node) or {}).get("character_id") or node
    sk = formats.sketch_from_edge(a.world, slug(ea), slug(eb), row["charge"], kit)
    sk["edge_id"] = row["id"]
    sk["world_visibility"] = world["visibility"] if world and "visibility" in world.keys() else "public"
    if any((res.get(n) or {}).get("visibility") == "private" for n in (ea, eb)):
        sk["visibility"] = "private"
    out = ROOT / "worlds" / a.world / "sketches"; out.mkdir(parents=True, exist_ok=True)
    (out / f"{kit['id']}.json").write_text(json.dumps(sk, indent=1))
    duet = {"name": sk["name"], "cast": sk["cast"], "lines": sk["lines"],
            "source": f"chars/worlds/{a.world}/sketches/{kit['id']}.json", "visibility": sk["visibility"]}
    (out / f"{kit['id']}.duet.json").write_text(json.dumps(duet, indent=1))
    print(json.dumps({k: sk[k] for k in ("name", "premise", "operator", "operator_ranking", "word_count",
                                         "est_spoken_s", "passed", "visibility")}, indent=1))
    for g, v in sk["gates"].items():
        print(" gates", g, "passed" if v["passed"] else "FAILED", v["vetoes"], v["flags"])
    for l in sk["lines"]:
        print(f"  {sk['cast'][l['who']]}: {l['text']}")


if __name__ == "__main__":
    main()
