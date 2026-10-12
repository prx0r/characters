"""Extract sourced lore claims from theory literature into world_lore.

Reads clark-*.md Verbatim (short, attributed) + Paraphrased-points bullets.
NO invention: every row carries source + status (verbatim-attributed |
paraphrase). Dedupe by claim text. Mapping file->world below.
Usage: PYTHONPATH=audition python3 research/extract_lore.py
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "audition"))

FILE_WORLD = {
    "clark-reptoids": "galactic", "clark-nordics": "galactic",
    "clark-mib": "galactic", "clark-shaver": "galactic",
    "clark-ultraterrestrials": "galactic",
    "clark-fairies": "folk", "clark-kappa": "folk", "clark-old-hag": "folk",
}


def parse_clark(path: Path) -> tuple[list[str], list[str], str]:
    txt = path.read_text()
    src = ""
    m = re.search(r"Source:\s*(.+)", txt)
    if m:
        src = m.group(1).strip()[:200]
    verbatim, paraphrase, mode = [], [], None
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("## Verbatim"):
            mode = "v"
            continue
        if s.startswith("## Paraphrased") or s.startswith("## Paraphrase"):
            mode = "p"
            continue
        if s.startswith("##"):
            mode = None
            continue
        if mode and s.startswith("- "):
            (verbatim if mode == "v" else paraphrase).append(s[2:].strip()[:500])
    return verbatim, paraphrase, src


def main() -> None:
    import store
    conn = store.connect()
    n = 0
    try:
        for stem, wid in FILE_WORLD.items():
            p = ROOT / "theory" / f"{stem}.md"
            if not p.exists():
                continue
            verb, para, src = parse_clark(p)
            for v in verb:
                claim = f"SOURCED: {v}"
                if conn.execute("SELECT 1 FROM world_lore WHERE claim=?", (claim,)).fetchone():
                    continue
                conn.execute("INSERT INTO world_lore (id,world_id,claim,source,created_at)"
                             " VALUES (?,?,?,?,?)",
                             (store.new_id("lore"), wid, claim,
                              f"{src} [verbatim-attributed]", time.time()))
                n += 1
            for v in para:
                claim = f"SOURCED: {v}"
                if conn.execute("SELECT 1 FROM world_lore WHERE claim=?", (claim,)).fetchone():
                    continue
                conn.execute("INSERT INTO world_lore (id,world_id,claim,source,created_at)"
                             " VALUES (?,?,?,?,?)",
                             (store.new_id("lore"), wid, claim,
                              f"{src} [paraphrase]", time.time()))
                n += 1
        conn.commit()
    finally:
        conn.close()
    print(f"extracted {n} sourced lore rows")


if __name__ == "__main__":
    main()
