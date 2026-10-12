"""Mine books for worlds — semantic search over the lore corpus.

No torch, no server, no new deps: chunks in SQLite, embeddings via
DashScope (qwen3.7-text-embedding, free 1M), brute-force cosine (corpus is
small). GraphRAG-style entity extraction is the later upgrade (needs LLM
budget); this is the retrieval half, and it runs today.

  PYTHONPATH=audition python3 research/mine.py index   # chunk+embed corpus
  PYTHONPATH=audition python3 research/mine.py search "mantis beings" --top 5
  PYTHONPATH=audition python3 research/mine.py feed --world galactic --query "reptilian hierarchy" --top 8
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "audition"))
DB = ROOT / "theory" / "mine.db"
SOURCES = [
    (ROOT / "theory", "*.md"),
    (ROOT / "canon", "*/canon.json"),
    (ROOT / "freaks", "*/character.json"),
]
SKIP_DIRS = {"killtony-minutes", "killtony-personas", "character-formulas",
             "market", "prosody", "scribe", "shikigami-exports",
             "almanac-species", "personas-outsiders"}


def _key() -> str:
    for line in (ROOT / "audition" / ".env").read_text().splitlines():
        if line.startswith("DASHSCOPE_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("no key")


def embed(texts: list[str], model: str = "qwen3.7-text-embedding") -> list[list[float]]:
    """DashScope embeddings, OpenAI-compatible endpoint."""
    key = _key()
    out: list[list[float]] = []
    for i in range(0, len(texts), 10):
        batch = [t[:2048] for t in texts[i:i + 10]]
        req = urllib.request.Request(
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/embeddings",
            data=json.dumps({"model": model, "input": batch}).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode())
            out += [e["embedding"] for e in sorted(d["data"], key=lambda e: e["index"])]
        except Exception as e:
            raise SystemExit(f"embed failed: {e}")
        time.sleep(0.3)
    return out


def chunk_text(text: str, path: str, size: int = 400, ov: int = 60) -> list[tuple[str, str]]:
    words = text.split()
    out = []
    i = 0
    while i < len(words):
        out.append((path, " ".join(words[i:i + size])))
        i += size - ov
    return out


def build_index() -> int:
    chunks: list[tuple[str, str]] = []
    for base, pat in SOURCES:
        for f in sorted(base.glob(pat)):
            if any(s in str(f) for s in SKIP_DIRS):
                continue
            if f.suffix == ".json":
                try:
                    d = json.loads(f.read_text())
                    txt = json.dumps(d)[:6000]
                except Exception:
                    continue
            else:
                txt = f.read_text()[:20000]
            chunks += chunk_text(txt, str(f.relative_to(ROOT)))
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, path TEXT, text TEXT, vec TEXT)")
    have = {r[0] for r in con.execute("SELECT path FROM chunks")}
    new = [c for c in chunks if c[0] not in {h.split("#")[0] for h in have}]
    # re-embed fully if corpus changed shape (cheap at this scale)
    if new:
        ids = [f"{p}#{i}" for i, (p, _) in enumerate(new)]
        vecs = embed([t for _, t in new])
        for (p, t), v, i in zip(new, vecs, ids):
            _ = i
            con.execute("INSERT INTO chunks (path, text, vec) VALUES (?,?,?)",
                        (p, t, json.dumps(v)))
        con.commit()
    n = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    con.close()
    print(f"indexed {n} chunks ({len(new)} new)")
    return n


def _cos(a: list[float], b: list[float]) -> float:
    n = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return n / (da * db) if da and db else 0.0


def search(query: str, top: int = 5) -> list[dict]:
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT path, text, vec FROM chunks").fetchall()
    con.close()
    qv = embed([query])[0]
    scored = []
    for path, text, vec in rows:
        scored.append((_cos(qv, json.loads(vec)), path, text))
    scored.sort(reverse=True)
    return [{"score": round(s, 3), "path": p, "text": t[:400]} for s, p, t in scored[:top]]


def feed(world_id: str, query: str, top: int = 8, dry: bool = True) -> list[dict]:
    import store
    hits = search(query, top)
    if dry:
        return hits
    conn = store.connect()
    n = 0
    try:
        for h in hits:
            claim = f"MINED [{h['path']}@{h['score']}]: {h['text'][:280]}"
            if conn.execute("SELECT 1 FROM world_lore WHERE claim=?", (claim,)).fetchone():
                continue
            conn.execute("INSERT INTO world_lore (id,world_id,claim,source,created_at)"
                         " VALUES (?,?,?,?,?)",
                         (store.new_id("lore"), world_id, claim,
                          f"semantic mine: {query}", time.time()))
            n += 1
        conn.commit()
    finally:
        conn.close()
    print(f"fed {n} rows to {world_id}")
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "search", "feed"])
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--world", default="galactic")
    ap.add_argument("--go", action="store_true", help="actually write lore rows")
    args = ap.parse_args()
    if args.cmd == "index":
        build_index()
    elif args.cmd == "search":
        for h in search(args.query, args.top):
            print(h["score"], h["path"], "\n  ", h["text"][:160].replace("\n", " "), "\n")
    elif args.cmd == "feed":
        feed(args.world, args.query, args.top, dry=not args.go)


if __name__ == "__main__":
    main()
