"""Index easy/folk-and-fable collections into folk world_lore.

Reference, don't copy: scripts stay in place; we store title, size,
source URLs (Gutenberg, public domain) and an opening-line fingerprint.
Usage: PYTHONPATH=audition python3 research/seed_folk_lore.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
FABLE = Path("/root/easy/folk-and-fable")
sys.path.insert(0, str(ROOT / "audition"))


def main() -> None:
    import store
    conn = store.connect()
    n = 0
    try:
        for d in sorted(FABLE.iterdir()):
            meta, script = d / "meta.json", d / "script.txt"
            if not (d.is_dir() and meta.exists()):
                continue
            try:
                m = json.loads(meta.read_text())
            except Exception:
                continue
            words = len(script.read_text().split()) if script.exists() else 0
            srcs = "; ".join(s.get("url", "") for s in m.get("sources", [])[:3])
            fp = ""
            if script.exists():
                fp = " ".join(script.read_text().split()[:14])
            claim = (f"FABLE {d.name}: {m.get('title', '')} "
                     f"({words} words spoken). {fp}...")
            if conn.execute("SELECT 1 FROM world_lore WHERE claim=?", (claim,)).fetchone():
                continue
            conn.execute("INSERT INTO world_lore (id,world_id,claim,source,created_at)"
                         " VALUES (?,?,?,?,?)",
                         (store.new_id("lore"), "folk", claim, srcs, time.time()))
            n += 1
        conn.commit()
    finally:
        conn.close()
    print(f"indexed {n} new folk lore rows")


if __name__ == "__main__":
    main()
