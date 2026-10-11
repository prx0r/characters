#!/usr/bin/env python3
"""Character Comedy Audition App — P0. Flask + SQLite + edge-tts.

Run:  python3 /root/characters/audition/app.py
Open: http://127.0.0.1:8801/
"""
from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

import store
import generate
import tts_provider

HERE = Path(__file__).parent
app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")

RATINGS = {"not_funny": 0, "amusing": 1, "funny": 2, "excellent": 3}
JOBS: dict[str, dict] = {}


def _conn():
    return store.connect()


@app.get("/")
def index():
    return send_file(HERE / "static" / "index.html")


@app.get("/api/auditions/characters")
def characters():
    return jsonify({"characters": generate.list_characters(),
                    "llm": "openai:" + (__import__("os").getenv("AUDITION_LLM_MODEL", "gpt-4o-mini")
                                        if __import__("os").getenv("OPENAI_API_KEY") else "offline-template-v0"),
                    "tts": "edge-tts"})


def _run_generation(job_id: str, character_id: str):
    conn = _conn()
    try:
        JOBS[job_id]["status"] = "generating"
        recent = store.recent_feedback(conn, character_id, 5)
        # used scenario ids (avoid repeats)
        used_rows = conn.execute("SELECT scenario_id FROM auditions WHERE character_id=? ORDER BY created_at DESC LIMIT 12",
                                 (character_id,)).fetchall()
        used = [r[0] for r in used_rows]
        recent_full = [{"scenario_id": u, "full_text": "", "comment": "", "operator_ids": "[]",
                        "rating": 0, "pog_count": 0} for u in []]  # placeholder merged below
        # merge feedback text for avoid-list
        fb = store.recent_feedback(conn, character_id, 5)
        for f in fb:
            f["pog_count"] = conn.execute("SELECT COUNT(*) FROM pogs WHERE audition_id=?",
                                          (f["id"],)).fetchone()[0]
        strat = store.get_strategy(conn, character_id)
        seed = random.randint(1, 10**9)
        gen = generate.generate_minute(character_id, fb, strat, seed)
        # noslop filter: veto AI-slop minutes, one regeneration with a new seed
        slop = generate.slop_check(gen["full_text"])
        if slop.get("is_ai"):
            gen = generate.generate_minute(character_id, fb, strat, seed + 1)
            slop = {**generate.slop_check(gen["full_text"]), "vetoed_first": True}
        gen["decision"]["slop"] = slop
        # next-minute must be fresh: if scenario repeats and alternatives exist, repick once
        if gen["scenario"]["id"] in used:
            alt = generate.pick_scenario(used, random.Random(seed + 1))
            if alt["id"] not in used:
                gen["scenario"] = alt
        JOBS[job_id].update({"status": "synthesising", "scenario_id": gen["scenario"]["id"]})
        voice = tts_provider.VOICES.get(character_id, gen["character"].get("voice_id", "en-US-GuyNeural"))
        audio = tts_provider.synthesize(job_id, gen["full_text"], voice)
        pauses = sum(b.get("pause_after_ms", 0) for b in gen["beats"])
        est_total = sum(b["end_ms"] - b["start_ms"] for b in gen["beats"])
        # scale beat timings to real audio duration
        scale = (audio["duration_ms"] / est_total) if est_total else 1.0
        t = 0
        for b in gen["beats"]:
            dur = int((b["end_ms"] - b["start_ms"]) * scale)
            b["start_ms"], b["end_ms"] = t, t + dur
            t += dur
        row = {"id": job_id, "character_id": character_id,
               "character_version": generate.CHARACTER_VERSION,
               "scenario_id": gen["scenario"]["id"],
               "source_block_ids": [gen["scenario"]["id"]],
               "theory_ids": gen["theory_ids"], "operator_ids": gen["operator_ids"],
               "decision": gen["decision"], "strategy_version": strat["version"],
               "exploration": gen["exploration"], "model_id": gen["model_id"],
               "generation_seed": gen["seed"], "beats": gen["beats"],
               "full_text": gen["full_text"], "audio_path": audio["path"],
               "audio_duration_ms": audio["duration_ms"],
               "timing_provenance": ("beats-scaled-to-" + audio["provenance"]),
               "audio_hash": audio["sha256"], "status": "ready", "error": "",
               "change_note": gen["decision"].get("change_from_last", "")}
        store.insert_audition(conn, row)
        JOBS[job_id].update({"status": "ready"})
    except Exception as e:  # surfaced, retryable
        JOBS[job_id].update({"status": "failed", "error": str(e)[:500]})
    finally:
        conn.close()


@app.post("/api/auditions")
def create_audition():
    data = request.get_json(force=True) or {}
    character_id = data.get("character_id", "no_nose_nolan")
    # validate character
    ids = {c["id"] for c in generate.list_characters()}
    if character_id not in ids:
        return jsonify({"error": f"unknown character_id {character_id}"}), 400
    job_id = store.new_id("aud")
    JOBS[job_id] = {"status": "queued", "character_id": character_id, "created_at": time.time()}
    threading.Thread(target=_run_generation, args=(job_id, character_id), daemon=True).start()
    return jsonify({"audition_id": job_id, "status": "queued"})


@app.get("/api/auditions/<aud_id>")
def get_audition(aud_id: str):
    if aud_id in JOBS and JOBS[aud_id].get("status") in ("queued", "generating", "synthesising"):
        return jsonify({"id": aud_id, "status": JOBS[aud_id]["status"],
                        "scenario_id": JOBS[aud_id].get("scenario_id", "")})
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
    finally:
        conn.close()
    if not row:
        st = JOBS.get(aud_id, {})
        if st.get("status") == "failed":
            return jsonify({"id": aud_id, "status": "failed", "error": st.get("error", "")}), 200
        return jsonify({"error": "unknown audition id"}), 404
    row["audio_url"] = f"/audio/{aud_id}"
    # KT-shaped mirror: our auditions read like Kill Tony records
    pogs = []
    conn2 = _conn()
    try:
        pogs = [dict(p) for p in conn2.execute(
            "SELECT * FROM pogs WHERE audition_id=? ORDER BY playback_ms", (aud_id,)).fetchall()]
        fb = conn2.execute("SELECT * FROM feedbacks WHERE audition_id=?", (aud_id,)).fetchone()
    finally:
        conn2.close()
    row["pogs"] = pogs
    row["retention"] = None
    conn3 = _conn()
    try:
        rr = conn3.execute(
            """SELECT COUNT(*) n, AVG(CAST(watch_ms AS FLOAT)/MAX(duration_ms,1)) avgr,
                      AVG(CASE WHEN decision='skip' THEN 1.0 ELSE 0.0 END) skipr,
                      SUM(CASE WHEN decision='like' THEN 1 ELSE 0 END) likes
               FROM short_views WHERE audition_id=?""", (aud_id,)).fetchone()
        if rr and rr["n"]:
            row["retention"] = {"views": rr["n"], "avg_watch": round(rr["avgr"] or 0, 3),
                                "skip_rate": round(rr["skipr"] or 0, 3), "likes": rr["likes"] or 0}
    except Exception:
        pass
    finally:
        conn3.close()
    row["kt_record"] = {
        "comedian_name": row["character_id"], "set_number": None,
        "topic_tags": row["source_block_ids"],
        "crowd_reaction": (dict(fb)["room_reaction"] if fb else "") or None,
        "tony_praise_level": (dict(fb)["rating"] if fb else None),
        "beats": [{"type": b["type"], "words": len(b["text"].split())} for b in row["beats"]],
        "pog_times_ms": [p["playback_ms"] for p in pogs],
        "note": "POG timestamps are the audience trace; crowd_reaction is the reviewer's room read",
    }
    return jsonify(row)


@app.get("/audio/<aud_id>")
def audio(aud_id: str):
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "unknown audition id"}), 404
    p = Path(row["audio_path"])
    if not p.exists():
        return jsonify({"error": "audio file missing"}), 410
    mime = "audio/mpeg" if p.suffix == ".mp3" else "audio/wav"
    return send_file(p, mimetype=mime)


def _attribute_beat(beats: list[dict], t_ms: int) -> tuple[str | None, bool]:
    cands = [b for b in beats if b["start_ms"] <= t_ms <= b["end_ms"] + 2000]
    if not cands:
        prev = [b for b in beats if b["start_ms"] <= t_ms]
        if not prev:
            return None, True
        b = max(prev, key=lambda b: b["start_ms"])
        return b["id"], (t_ms - b["start_ms"] > 2000)
    # closest preceding start wins; uncertain if several overlap
    b = max(cands, key=lambda b: b["start_ms"])
    return b["id"], len(cands) > 1


@app.post("/api/auditions/<aud_id>/pogs")
def record_pog(aud_id: str):
    data = request.get_json(force=True) or {}
    event_id = data.get("event_id") or store.new_id("pog")
    try:
        playback_ms = int(data.get("playback_ms", -1))
    except Exception:
        return jsonify({"error": "playback_ms must be an integer"}), 400
    iteration = int(data.get("iteration", 1))
    conn = _conn()
    try:
        if store.pog_exists(conn, event_id):
            r = conn.execute("SELECT * FROM pogs WHERE event_id=?", (event_id,)).fetchone()
            return jsonify(dict(r))
        row = store.get_audition(conn, aud_id)
        if not row:
            return jsonify({"error": "unknown audition id"}), 404
        if playback_ms < 0 or playback_ms > row["audio_duration_ms"]:
            return jsonify({"error": "playback_ms outside audio duration"}), 400
        beat_id, uncertain = _attribute_beat(row["beats"], playback_ms)
        return jsonify(store.insert_pog(conn, event_id, aud_id, playback_ms, iteration, beat_id, int(uncertain)))
    finally:
        conn.close()


@app.post("/api/auditions/<aud_id>/play_event")
def play_event(aud_id: str):
    data = request.get_json(force=True) or {}
    kind = str(data.get("kind", ""))[:20]
    pos = int(data.get("position_ms", 0))
    if kind not in ("play", "pause", "seek", "ended"):
        return jsonify({"error": "bad kind"}), 400
    conn = _conn()
    try:
        eid = store.new_id("pev")
        conn.execute("INSERT INTO play_events (id, audition_id, kind, position_ms, created_at) VALUES (?,?,?,?,?)",
                     (eid, aud_id, kind, pos, time.time()))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.post("/api/auditions/<aud_id>/feedback")
def feedback(aud_id: str):
    data = request.get_json(force=True) or {}
    rating = data.get("rating", None)
    if isinstance(rating, str):
        rating = RATINGS.get(rating, None)
    if rating not in (0, 1, 2, 3):
        return jsonify({"error": "rating must be 0-3 or not_funny/amusing/funny/excellent"}), 400
    conn = _conn()
    try:
        if not store.get_audition(conn, aud_id):
            return jsonify({"error": "unknown audition id"}), 404
        try:
            fb = store.insert_feedback(conn, aud_id, rating, data.get("comment", ""),
                                       data.get("room_reaction", ""))
        except ValueError as e:
            code = 400 if "room_reaction" in str(e) else 409
            return jsonify({"error": str(e)}), code
        # update strategy from all feedback for this character
        aud = store.get_audition(conn, aud_id)
        rows = conn.execute(
            """SELECT a.scenario_id, a.operator_ids, a.decision, a.id, f.rating, f.comment,
                      (SELECT COUNT(*) FROM pogs p WHERE p.audition_id=a.id) AS pog_count
               FROM auditions a JOIN feedbacks f ON f.audition_id=a.id
               WHERE a.character_id=?""", (aud["character_id"],)).fetchall()
        summ = generate.summarize_strategy(aud["character_id"], [dict(r) for r in rows])
        old = store.get_strategy(conn, aud["character_id"])
        ver = f"strategy_{int(old['version'].split('_')[-1]) + 1:02d}" if old["version"].startswith("strategy_") else "strategy_02"
        store.save_strategy(conn, aud["character_id"], ver, summ["success"], summ["failed"], summ["instructions"])
        return jsonify({**fb, "strategy": summ["instructions"]})
    finally:
        conn.close()


@app.post("/api/auditions/<aud_id>/next")
def next_audition(aud_id: str):
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "unknown audition id"}), 404
    return create_audition.__wrapped__() if hasattr(create_audition, "__wrapped__") else _next(row)


def _next(row: dict):
    job_id = store.new_id("aud")
    JOBS[job_id] = {"status": "queued", "character_id": row["character_id"], "created_at": time.time()}
    threading.Thread(target=_run_generation, args=(job_id, row["character_id"]), daemon=True).start()
    return jsonify({"audition_id": job_id, "status": "queued"})


@app.get("/api/auditions")
def history():
    character_id = request.args.get("character_id", "no_nose_nolan")
    conn = _conn()
    try:
        return jsonify({"auditions": store.list_auditions(conn, character_id)})
    finally:
        conn.close()


@app.post("/api/auditions/<aud_id>/memory")
def add_memory(aud_id: str):
    """Character learning: record a fictional event. Explicit, versioned, never auto."""
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if not text or len(text) > 300:
        return jsonify({"error": "memory text required, max 300 chars"}), 400
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
        if not row:
            return jsonify({"error": "unknown audition id"}), 404
        mid = store.new_id("mem")
        conn.execute("INSERT INTO memories (id, character_id, text, source_audition, created_at)"
                     " VALUES (?,?,?,?,?)",
                     (mid, row["character_id"], text, aud_id, __import__("time").time()))
        conn.commit()
        return jsonify({"memory_id": mid, "character_id": row["character_id"], "text": text})
    finally:
        conn.close()


@app.get("/shorts")
def shorts_page():
    return send_file(HERE / "static" / "shorts.html")


@app.get("/api/shorts/feed")
def shorts_feed():
    """Unseen-first audition cards: id, character, portrait, audio, beats, duration."""
    character_id = request.args.get("character_id", "")
    conn = _conn()
    try:
        q = ("SELECT a.id, a.character_id, a.scenario_id, a.full_text, a.beats,"
             " a.audio_duration_ms FROM auditions a WHERE a.status='ready'")
        args: list = []
        if character_id:
            q += " AND a.character_id=?"
            args.append(character_id)
        q += " ORDER BY (SELECT COUNT(*) FROM short_views v WHERE v.audition_id=a.id), a.created_at DESC LIMIT 30"
        rows = [dict(r) for r in conn.execute(q, args).fetchall()]
    finally:
        conn.close()
    portraits = {"no_nose_nolan": "/static/portraits/nolan.jpg",
                 "reptilian_ralph_middle_management": "/static/portraits/ralph.jpg",
                 "rudy_dulce_hvac": "/static/portraits/rudy.jpg"}
    cards = []
    for r in rows:
        beats = json.loads(r["beats"])
        cards.append({"audition_id": r["id"], "character_id": r["character_id"],
                      "scenario_id": r["scenario_id"],
                      "portrait_url": portraits.get(r["character_id"], ""),
                      "audio_url": f"/audio/{r['id']}",
                      "duration_ms": r["audio_duration_ms"],
                      "beats": [{"id": b["id"], "type": b["type"], "text": b["text"],
                                 "start_ms": b["start_ms"], "end_ms": b["end_ms"]} for b in beats]})
    return jsonify({"cards": cards})


@app.post("/api/shorts/event")
def shorts_event():
    """decision in skip|like|complete|replay|comment. watch_ms = retention proxy."""
    data = request.get_json(force=True) or {}
    aud_id = data.get("audition_id", "")
    try:
        watch_ms = max(0, int(data.get("watch_ms", 0)))
    except Exception:
        return jsonify({"error": "watch_ms must be integer"}), 400
    decision = data.get("decision", "")
    if decision not in ("skip", "like", "complete", "replay", "comment"):
        return jsonify({"error": "bad decision"}), 400
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
        if not row:
            return jsonify({"error": "unknown audition id"}), 404
        if watch_ms > row["audio_duration_ms"] + 5000:
            return jsonify({"error": "watch_ms beyond media length"}), 400
        vid = store.new_id("view")
        conn.execute("INSERT INTO short_views (view_id, audition_id, watch_ms, duration_ms,"
                     " decision, comment, created_at) VALUES (?,?,?,?,?,?,?)",
                     (vid, aud_id, watch_ms, row["audio_duration_ms"], decision,
                      (data.get("comment") or "")[:500], time.time()))
        conn.commit()
        return jsonify({"view_id": vid, "retention": round(watch_ms / max(1, row["audio_duration_ms"]), 3)})
    finally:
        conn.close()


@app.get("/api/shorts/retention")
def shorts_retention():
    """Per-audition retention aggregates: views, avg watch ratio, skip rate, likes."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT audition_id, COUNT(*) n,
                      AVG(CAST(watch_ms AS FLOAT)/MAX(duration_ms,1)) avgr,
                      AVG(CASE WHEN decision='skip' THEN 1.0 ELSE 0.0 END) skipr,
                      SUM(CASE WHEN decision='like' THEN 1 ELSE 0 END) likes,
                      SUM(CASE WHEN decision='replay' THEN 1 ELSE 0 END) replays
               FROM short_views GROUP BY audition_id""").fetchall()
        return jsonify({"retention": [dict(r) for r in rows]})
    finally:
        conn.close()


TAKE_EXTS = {".wav": "audio/wav", ".webm": "audio/webm", ".mp3": "audio/mpeg",
              ".ogg": "audio/ogg", ".m4a": "audio/mp4"}


@app.post("/api/auditions/<aud_id>/human_take")
def upload_take(aud_id: str):
    """P1: upload your own delivery of the approved script. Original preserved."""
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "unknown audition id"}), 404
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "missing audio file field"}), 400
    ext = Path(f.filename or "").suffix.lower()
    if ext not in TAKE_EXTS:
        return jsonify({"error": f"unsupported extension {ext or '?'}; use wav/webm/mp3/ogg/m4a"}), 400
    raw = f.read()
    if len(raw) < 2000:
        return jsonify({"error": "audio too short/empty"}), 400
    if len(raw) > 15 * 1024 * 1024:
        return jsonify({"error": "audio over 15MB cap"}), 400
    take_id = store.new_id("take")
    out = HERE / "audio" / f"{take_id}{ext}"
    out.write_bytes(raw)
    import hashlib
    import subprocess
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
                           capture_output=True, text=True, timeout=20)
        dur = int(float(r.stdout.strip()) * 1000)
    except Exception:
        return jsonify({"error": "could not read audio duration; file may be corrupt"}), 400
    conn = _conn()
    try:
        take = store.insert_take(conn, take_id, aud_id, str(out),
                                 hashlib.sha256(raw).hexdigest(), dur, TAKE_EXTS[ext])
        return jsonify({**take, "elevenlabs_status": "not_configured",
                        "note": "Original preserved. Voice conversion needs ELEVENLABS_API_KEY."})
    finally:
        conn.close()


@app.get("/api/auditions/<aud_id>/takes")
def take_list(aud_id: str):
    conn = _conn()
    try:
        if not store.get_audition(conn, aud_id):
            return jsonify({"error": "unknown audition id"}), 404
        takes = store.list_takes(conn, aud_id)
    finally:
        conn.close()
    for t in takes:
        t["audio_url"] = f"/takes/{t['id']}"
    return jsonify({"takes": takes})


@app.get("/takes/<take_id>")
def take_audio(take_id: str):
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM human_takes WHERE id=?", (take_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        return jsonify({"error": "unknown take id"}), 404
    p = Path(r["audio_path"])
    if not p.exists():
        return jsonify({"error": "take file missing"}), 410
    return send_file(p, mimetype=r["mime"])


@app.post("/api/auditions/<aud_id>/source")
def set_source(aud_id: str):
    data = request.get_json(force=True) or {}
    source = data.get("source", "ai_tts")
    take_id = data.get("take_id", "")
    if source not in ("ai_tts", "human_voice_performance"):
        return jsonify({"error": "source must be ai_tts or human_voice_performance"}), 400
    conn = _conn()
    try:
        if not store.get_audition(conn, aud_id):
            return jsonify({"error": "unknown audition id"}), 404
        try:
            store.set_active_take(conn, aud_id, take_id, source)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"audition_id": aud_id, "performance_source": source, "active_take_id": take_id})
    finally:
        conn.close()


if __name__ == "__main__":
    print("Audition app on http://127.0.0.1:8807/")
    app.run(host="127.0.0.1", port=8807, threaded=True)
