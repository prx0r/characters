"""Audition persistence — SQLite. No ORM. Immutable audition records."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "auditions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS auditions (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL,
  character_version TEXT NOT NULL,
  scenario_id TEXT NOT NULL,
  source_block_ids TEXT NOT NULL,
  theory_ids TEXT NOT NULL,
  operator_ids TEXT NOT NULL,
  decision TEXT NOT NULL,
  strategy_version TEXT NOT NULL,
  exploration INTEGER NOT NULL,
  model_id TEXT NOT NULL,
  generation_seed INTEGER NOT NULL,
  beats TEXT NOT NULL,
  full_text TEXT NOT NULL,
  audio_path TEXT NOT NULL,
  audio_duration_ms INTEGER NOT NULL,
  timing_provenance TEXT NOT NULL,
  audio_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT NOT NULL,
  change_note TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pogs (
  event_id TEXT PRIMARY KEY,
  audition_id TEXT NOT NULL,
  playback_ms INTEGER NOT NULL,
  iteration INTEGER NOT NULL,
  beat_id TEXT,
  uncertain INTEGER NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feedbacks (
  audition_id TEXT PRIMARY KEY,
  rating INTEGER NOT NULL,
  comment TEXT NOT NULL,
  submitted_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS strategies (
  character_id TEXT PRIMARY KEY,
  version TEXT NOT NULL,
  success TEXT NOT NULL,
  failed TEXT NOT NULL,
  instructions TEXT NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS play_events (
  id TEXT PRIMARY KEY,
  audition_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  position_ms INTEGER NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS human_takes (
  id TEXT PRIMARY KEY,
  audition_id TEXT NOT NULL,
  audio_path TEXT NOT NULL,
  audio_hash TEXT NOT NULL,
  duration_ms INTEGER NOT NULL,
  mime TEXT NOT NULL,
  converted_path TEXT NOT NULL,
  created_at REAL NOT NULL
);
"""


def migrate(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(auditions)").fetchall()}
    if "performance_source" not in cols:
        conn.execute("ALTER TABLE auditions ADD COLUMN performance_source TEXT NOT NULL DEFAULT 'ai_tts'")
    if "active_take_id" not in cols:
        conn.execute("ALTER TABLE auditions ADD COLUMN active_take_id TEXT NOT NULL DEFAULT ''")
    fcols = {r[1] for r in conn.execute("PRAGMA table_info(feedbacks)").fetchall()}
    if "room_reaction" not in fcols:
        conn.execute("ALTER TABLE feedbacks ADD COLUMN room_reaction TEXT NOT NULL DEFAULT ''")
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
      id TEXT PRIMARY KEY, character_id TEXT NOT NULL, text TEXT NOT NULL,
      source_audition TEXT NOT NULL, created_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS short_views (
      view_id TEXT PRIMARY KEY, audition_id TEXT NOT NULL,
      watch_ms INTEGER NOT NULL, duration_ms INTEGER NOT NULL,
      decision TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '',
      created_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
      job_id TEXT PRIMARY KEY, character_id TEXT NOT NULL, mode TEXT NOT NULL,
      status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
      created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS strategy_versions (
      version TEXT PRIMARY KEY, character_id TEXT NOT NULL, parent TEXT NOT NULL,
      success TEXT NOT NULL, failed TEXT NOT NULL, instructions TEXT NOT NULL,
      evidence TEXT NOT NULL, hypotheses TEXT NOT NULL DEFAULT '[]',
      changes TEXT NOT NULL DEFAULT '', uncertainties TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'accepted', created_at REAL NOT NULL, hash TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS strategy_pointer (
      character_id TEXT PRIMARY KEY, version TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS battle_runs (
      job_id TEXT PRIMARY KEY, character_id TEXT NOT NULL,
      table_json TEXT NOT NULL, winner_idx INTEGER NOT NULL,
      blind_votes TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL)""")
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()}
    for col, ddl in (("type", "TEXT NOT NULL DEFAULT 'event'"),
                     ("status", "TEXT NOT NULL DEFAULT 'proposed'"),
                     ("entities", "TEXT NOT NULL DEFAULT '[]'"),
                     ("callback_count", "INTEGER NOT NULL DEFAULT 0"),
                     ("last_used", "REAL NOT NULL DEFAULT 0")):
        if col not in mcols:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {col} {ddl}")
    conn.execute("""CREATE TABLE IF NOT EXISTS callback_uses (
      id TEXT PRIMARY KEY, character_id TEXT NOT NULL, memory_id TEXT NOT NULL,
      audition_id TEXT NOT NULL, mechanism TEXT NOT NULL, landed INTEGER NOT NULL DEFAULT 0,
      created_at REAL NOT NULL)""")
    conn.commit()


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate(conn)
    return conn


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def insert_audition(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """INSERT INTO auditions
        (id, character_id, character_version, scenario_id, source_block_ids,
         theory_ids, operator_ids, decision, strategy_version, exploration,
         model_id, generation_seed, beats, full_text, audio_path,
         audio_duration_ms, timing_provenance, audio_hash, status, error,
         change_note, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row["id"], row["character_id"], row["character_version"],
            row["scenario_id"], json.dumps(row["source_block_ids"]),
            json.dumps(row["theory_ids"]), json.dumps(row["operator_ids"]),
            json.dumps(row["decision"]), row["strategy_version"],
            int(row["exploration"]), row["model_id"], row["generation_seed"],
            json.dumps(row["beats"]), row["full_text"], row["audio_path"],
            row["audio_duration_ms"], row["timing_provenance"],
            row["audio_hash"], row["status"], row.get("error", ""),
            row.get("change_note", ""), row.get("created_at", time.time()),
        ),
    )
    conn.commit()


def get_audition(conn: sqlite3.Connection, aud_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM auditions WHERE id=?", (aud_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("source_block_ids", "theory_ids", "operator_ids", "decision", "beats"):
        d[k] = json.loads(d[k])
    return d


def list_auditions(conn: sqlite3.Connection, character_id: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM auditions WHERE character_id=? ORDER BY created_at DESC LIMIT ?",
        (character_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("source_block_ids", "theory_ids", "operator_ids", "decision", "beats"):
            d[k] = json.loads(d[k])
        d["pogs"] = [dict(p) for p in conn.execute(
            "SELECT * FROM pogs WHERE audition_id=? ORDER BY playback_ms", (d["id"],)).fetchall()]
        f = conn.execute("SELECT * FROM feedbacks WHERE audition_id=?", (d["id"],)).fetchone()
        d["feedback"] = dict(f) if f else None
        out.append(d)
    return out


def insert_pog(conn: sqlite3.Connection, event_id: str, audition_id: str,
               playback_ms: int, iteration: int, beat_id: str | None,
               uncertain: int) -> dict:
    conn.execute(
        "INSERT INTO pogs (event_id, audition_id, playback_ms, iteration, beat_id, uncertain, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (event_id, audition_id, playback_ms, iteration, beat_id, uncertain, time.time()),
    )
    conn.commit()
    return {"event_id": event_id, "audition_id": audition_id,
            "playback_ms": playback_ms, "iteration": iteration,
            "beat_id": beat_id, "uncertain": bool(uncertain)}


def pog_exists(conn: sqlite3.Connection, event_id: str) -> bool:
    return conn.execute("SELECT 1 FROM pogs WHERE event_id=?", (event_id,)).fetchone() is not None


def insert_feedback(conn: sqlite3.Connection, audition_id: str, rating: int, comment: str,
                    room_reaction: str = "") -> dict:
    if room_reaction not in ("", "silence", "light", "moderate", "big_laughs", "roaring"):
        raise ValueError("room_reaction must be silence/light/moderate/big_laughs/roaring")
    if conn.execute("SELECT 1 FROM feedbacks WHERE audition_id=?", (audition_id,)).fetchone():
        raise ValueError("feedback already submitted for this audition")
    conn.execute(
        "INSERT INTO feedbacks (audition_id, rating, comment, submitted_at, room_reaction) VALUES (?,?,?,?,?)",
        (audition_id, rating, comment or "", time.time(), room_reaction),
    )
    conn.commit()
    return {"audition_id": audition_id, "rating": rating, "comment": comment or "",
            "room_reaction": room_reaction}


def get_strategy(conn: sqlite3.Connection, character_id: str) -> dict:
    """Current accepted versioned strategy; migrates legacy row once."""
    ver = current_strategy_version(conn, character_id)
    if ver:
        v = get_strategy_at(conn, character_id, ver)
        if v:
            return {"character_id": character_id, "version": v["version"],
                    "success": v["success"], "failed": v["failed"],
                    "instructions": v["instructions"]}
    r = conn.execute("SELECT * FROM strategies WHERE character_id=?", (character_id,)).fetchone()
    if not r:
        return {"character_id": character_id, "version": "strategy_01",
                "success": {}, "failed": {}, "instructions": "Fresh. No evidence yet."}
    d = dict(r)
    save_strategy_version(conn, character_id, d["version"], "genesis",
                          json.loads(d["success"]), json.loads(d["failed"]),
                          d["instructions"], [], status="accepted")
    return {"character_id": character_id, "version": d["version"],
            "success": json.loads(d["success"]), "failed": json.loads(d["failed"]),
            "instructions": d["instructions"]}


def save_strategy(conn: sqlite3.Connection, character_id: str, version: str,
                  success: dict, failed: dict, instructions: str,
                  evidence: list | None = None, hypotheses: list | None = None,
                  changes: str = "") -> None:
    """Append-only: new immutable version + pointer move. Legacy row kept for compat."""
    parent = current_strategy_version(conn, character_id) or "genesis"
    save_strategy_version(conn, character_id, version, parent, success, failed,
                          instructions, evidence or [], hypotheses, changes,
                          status="accepted")
    conn.execute(
        "INSERT INTO strategies (character_id, version, success, failed, instructions, updated_at)"
        " VALUES (?,?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET"
        " version=excluded.version, success=excluded.success, failed=excluded.failed,"
        " instructions=excluded.instructions, updated_at=excluded.updated_at",
        (character_id, version, json.dumps(success), json.dumps(failed),
         instructions, time.time()),
    )
    conn.commit()


def recent_feedback(conn: sqlite3.Connection, character_id: str, n: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT a.id, a.scenario_id, a.theory_ids, a.operator_ids, a.full_text,
                  f.rating, f.comment FROM auditions a
           JOIN feedbacks f ON f.audition_id = a.id
           WHERE a.character_id=? ORDER BY f.submitted_at DESC LIMIT ?""",
        (character_id, n),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_take(conn: sqlite3.Connection, take_id: str, audition_id: str,
               audio_path: str, audio_hash: str, duration_ms: int, mime: str) -> dict:
    conn.execute(
        "INSERT INTO human_takes (id, audition_id, audio_path, audio_hash, duration_ms, mime, converted_path, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (take_id, audition_id, audio_path, audio_hash, duration_ms, mime, "", __import__("time").time()),
    )
    conn.commit()
    return {"take_id": take_id, "audition_id": audition_id, "duration_ms": duration_ms, "mime": mime}


def list_takes(conn: sqlite3.Connection, audition_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM human_takes WHERE audition_id=? ORDER BY created_at", (audition_id,)).fetchall()]


def set_active_take(conn: sqlite3.Connection, audition_id: str, take_id: str, source: str) -> None:
    assert source in ("ai_tts", "human_voice_performance")
    if source == "human_voice_performance":
        ok = conn.execute("SELECT 1 FROM human_takes WHERE id=? AND audition_id=?",
                          (take_id, audition_id)).fetchone()
        if not ok:
            raise ValueError("unknown take for this audition")
    conn.execute("UPDATE auditions SET performance_source=?, active_take_id=? WHERE id=?",
                 (source, take_id if source != "ai_tts" else "", audition_id))
    conn.commit()


def upsert_job(conn: sqlite3.Connection, job_id: str, character_id: str,
               mode: str, status: str, error: str = "") -> None:
    import time as _t
    conn.execute(
        "INSERT INTO jobs (job_id, character_id, mode, status, error, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET"
        " status=excluded.status, error=excluded.error, updated_at=excluded.updated_at",
        (job_id, character_id, mode, status, error, _t.time(), _t.time()))
    conn.commit()


def sweep_stale_jobs(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "UPDATE jobs SET status='failed', error='interrupted by restart (retryable)',"
        " updated_at=strftime('%s','now') WHERE status NOT IN ('ready','failed')")
    conn.commit()
    return cur.rowcount


def _sv_hash(character_id: str, parent: str, success: dict, failed: dict,
             instructions: str, evidence: list) -> str:
    import hashlib, json as _j
    return hashlib.sha256(_j.dumps(
        {"c": character_id, "p": parent, "s": success, "f": failed,
         "i": instructions, "e": sorted(evidence)}).encode()).hexdigest()[:16]


def save_strategy_version(conn: sqlite3.Connection, character_id: str, version: str,
                          parent: str, success: dict, failed: dict, instructions: str,
                          evidence: list, hypotheses: list | None = None,
                          changes: str = "", uncertainties: str = "",
                          status: str = "accepted") -> str:
    h = _sv_hash(character_id, parent, success, failed, instructions, evidence)
    conn.execute(
        "INSERT OR IGNORE INTO strategy_versions (version, character_id, parent, success, failed,"
        " instructions, evidence, hypotheses, changes, uncertainties, status, created_at, hash)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (version, character_id, parent, json.dumps(success), json.dumps(failed), instructions,
         json.dumps(evidence), json.dumps(hypotheses or []), changes, uncertainties,
         status, __import__("time").time(), h))
    if status == "accepted":
        conn.execute(
            "INSERT INTO strategy_pointer (character_id, version) VALUES (?,?)"
            " ON CONFLICT(character_id) DO UPDATE SET version=excluded.version",
            (character_id, version))
    conn.commit()
    return h


def get_strategy_at(conn: sqlite3.Connection, character_id: str, version: str) -> dict | None:
    r = conn.execute("SELECT * FROM strategy_versions WHERE character_id=? AND version=?",
                     (character_id, version)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["success"] = json.loads(d["success"])
    d["failed"] = json.loads(d["failed"])
    d["evidence"] = json.loads(d["evidence"])
    d["hypotheses"] = json.loads(d["hypotheses"])
    return d


def current_strategy_version(conn: sqlite3.Connection, character_id: str) -> str | None:
    r = conn.execute("SELECT version FROM strategy_pointer WHERE character_id=?",
                     (character_id,)).fetchone()
    return r[0] if r else None


def set_strategy_status(conn: sqlite3.Connection, character_id: str, version: str,
                        status: str) -> None:
    assert status in ("proposed", "accepted", "rejected", "reverted")
    conn.execute("UPDATE strategy_versions SET status=? WHERE character_id=? AND version=?",
                 (status, character_id, version))
    if status == "accepted":
        conn.execute(
            "INSERT INTO strategy_pointer (character_id, version) VALUES (?,?)"
            " ON CONFLICT(character_id) DO UPDATE SET version=excluded.version",
            (character_id, version))
    conn.commit()


def add_memory_typed(conn: sqlite3.Connection, character_id: str, text: str,
                     source_audition: str, mtype: str = "event",
                     status: str = "proposed", entities: list | None = None) -> str:
    assert mtype in ("event", "relationship", "gag", "callback_opportunity", "material")
    assert status in ("canonical", "proposed", "rejected")
    mid = new_id("mem")
    conn.execute("INSERT INTO memories (id, character_id, text, source_audition, created_at,"
                 " type, status, entities) VALUES (?,?,?,?,?,?,?,?)",
                 (mid, character_id, text, source_audition, __import__("time").time(),
                  mtype, status, json.dumps(entities or [])))
    conn.commit()
    return mid


def retrieve_memories(conn: sqlite3.Connection, character_id: str, scenario_id: str = "",
                      limit: int = 8, query: str = "") -> list[dict]:
    """Ranked retrieval: canonical + salience + recency + lexical overlap.

    Score = type/status base + BM25-lite term overlap with (query+scenario)
    + recency + unused-callback boost. No vectors, no new deps.
    """
    import re as _re
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM memories WHERE character_id=? AND status != 'rejected'",
        (character_id,)).fetchall()]
    terms = [t.lower() for t in _re.findall(r"[a-z]{3,}", (query + " " + scenario_id).lower())]
    now = __import__("time").time()
    scored = []
    for m in rows:
        s = 0.0
        if m["status"] == "canonical":
            s += 2.0
        if m["type"] == "callback_opportunity" and not m["callback_count"]:
            s += 2.0
        age_days = max(0.0, (now - (m["created_at"] or now)) / 86400.0)
        s += 1.0 / (1.0 + age_days / 30.0)
        text = ((m["text"] or "") + " " + (m.get("entities") or "")).lower()
        hits = sum(1 for t in set(terms) if t in text)
        s += min(2.0, hits * 0.5)
        try:
            ents = json.loads(m.get("entities") or "[]")
        except Exception:
            ents = []
        if scenario_id and any(e and e in scenario_id for e in ents):
            s += 1.5
        scored.append((s, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:limit]]


def propose_callbacks(conn: sqlite3.Connection, character_id: str,
                      scenario_id: str) -> list[dict]:
    """Callback candidates with evidence — generator decides, never auto-inserted."""
    mems = retrieve_memories(conn, character_id, scenario_id, limit=12)
    out = []
    for m in mems:
        if m["type"] not in ("event", "gag", "callback_opportunity"):
            continue
        if m["status"] == "proposed" and m["callback_count"] > 0:
            continue
        out.append({"memory_id": m["id"], "type": m["type"], "text": m["text"],
                    "status": m["status"], "prior_uses": m["callback_count"],
                    "source_audition": m["source_audition"],
                    "needs": "new consequence in this scenario; never repeat the old punchline"})
    return out[:5]


def record_battle(conn: sqlite3.Connection, job_id: str, character_id: str,
                  table: list, winner_idx: int = 0) -> None:
    import time as _t, json as _j
    conn.execute("INSERT OR REPLACE INTO battle_runs (job_id, character_id, table_json,"
                 " winner_idx, blind_votes, created_at) VALUES (?,?,?,?,?,?)",
                 (job_id, character_id, _j.dumps(table), winner_idx, "[]", _t.time()))
    conn.commit()


def get_energy(conn: sqlite3.Connection, character_id: str) -> float:
    conn.execute("CREATE TABLE IF NOT EXISTS energy_state (character_id TEXT PRIMARY KEY,"
                 " energy REAL NOT NULL, updated_at REAL NOT NULL)")
    r = conn.execute("SELECT energy, updated_at FROM energy_state WHERE character_id=?",
                     (character_id,)).fetchone()
    if not r:
        return 40.0
    # time recovery toward 40 (Shikigami pattern: full recovery ~4h)
    import time as _t
    elapsed = max(0.0, _t.time() - (r[1] or _t.time()))
    e = float(r[0])
    return max(0.0, min(80.0, e + (40.0 - e) * min(1.0, elapsed / 14400.0)))


def set_energy(conn: sqlite3.Connection, character_id: str, energy: float) -> None:
    import time as _t
    conn.execute("INSERT INTO energy_state (character_id, energy, updated_at) VALUES (?,?,?)"
                 " ON CONFLICT(character_id) DO UPDATE SET energy=excluded.energy,"
                 " updated_at=excluded.updated_at", (character_id, max(0.0, min(80.0, energy)), _t.time()))
    conn.commit()
