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


def _job(job_id: str, character_id: str, mode: str, status: str, error: str = "") -> None:
    """Write-through: memory cache + durable jobs table."""
    JOBS[job_id] = {"status": status, "character_id": character_id,
                    "created_at": JOBS.get(job_id, {}).get("created_at", time.time())}
    try:
        conn = _conn()
        try:
            store.upsert_job(conn, job_id, character_id, mode, status, error)
        finally:
            conn.close()
    except Exception:
        pass


def _startup_sweep() -> None:
    try:
        conn = _conn()
        try:
            n = store.sweep_stale_jobs(conn)
            if n:
                print(f"jobs: {n} stale marked failed-retryable")
        finally:
            conn.close()
    except Exception as e:
        print(f"jobs sweep skipped: {e}")


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
        _job(job_id, character_id, "single", "generating")
        recent = store.recent_feedback(conn, character_id, 5)
        # used scenario ids (avoid repeats)
        used_rows = conn.execute("SELECT scenario_id FROM auditions WHERE character_id=? ORDER BY created_at DESC LIMIT 12",
                                 (character_id,)).fetchall()
        used = [r[0] for r in used_rows]
        recent_full = [{"scenario_id": u, "full_text": "", "comment": "", "operator_ids": "[]",
                        "rating": 0, "pog_count": 0} for u in []]  # placeholder merged below
        # merge feedback text for avoid-list; include UNRATED minutes too
        # (repetition happened because only rated rows fed _prior_text)
        fb = store.recent_feedback(conn, character_id, 5)
        for f in fb:
            f["pog_count"] = conn.execute("SELECT COUNT(*) FROM pogs WHERE audition_id=?",
                                          (f["id"],)).fetchone()[0]
        seen_ids = {f["id"] for f in fb}
        for r in conn.execute("SELECT id, scenario_id, full_text, operator_ids FROM auditions"
                              " WHERE character_id=? ORDER BY created_at DESC LIMIT 8",
                              (character_id,)).fetchall():
            if r["id"] not in seen_ids:
                fb.append({"id": r["id"], "scenario_id": r["scenario_id"],
                           "full_text": r["full_text"], "comment": "",
                           "operator_ids": r["operator_ids"], "rating": 0, "pog_count": 0})
        strat = store.get_strategy(conn, character_id)
        seed = random.randint(1, 10**9)
        gen = generate.generate_minute(character_id, fb, strat, seed, used_ids=used)
        # noslop filter: veto AI-slop minutes, one regeneration with a new seed
        slop = generate.slop_check(gen["full_text"])
        if slop.get("is_ai"):
            gen = generate.generate_minute(character_id, fb, strat, seed + 1, used_ids=used)
            slop = {**generate.slop_check(gen["full_text"]), "vetoed_first": True}
        try:
            import slop_jev
            fused = slop_jev.jev_slop(gen["full_text"])
            slop["jev"] = {k: fused[k] for k in ("jev_mean", "fused", "verdict", "chooser") if k in fused}
            if fused.get("verdict") == "slop" and not slop.get("is_ai"):
                gen = generate.generate_minute(character_id, fb, strat, seed + 2, used_ids=used)
                slop = {**generate.slop_check(gen["full_text"]), "vetoed_first": True,
                        "vetoed_by": "jev-fused"}
        except Exception:
            pass
        gen["decision"]["slop"] = slop
        problems = generate.validate_minute(gen, character_id)
        if problems:
            raise RuntimeError("invalid minute (" + "; ".join(problems[:4]) + ")")
        _persist_ready(job_id, character_id, conn, gen, strat, seed)
        JOBS[job_id].update({"status": "ready"}); _job(job_id, JOBS[job_id].get("character_id", ""), JOBS[job_id].get("mode", "single"), "ready")
    except Exception as e:  # surfaced, retryable
        JOBS[job_id].update({"status": "failed", "error": str(e)[:500]}); _job(job_id, JOBS[job_id].get("character_id", ""), JOBS[job_id].get("mode", "single"), "failed", str(e)[:500])
    finally:
        conn.close()


def _persist_ready(job_id: str, character_id: str, conn, gen: dict, strat: dict, seed: int) -> None:
    JOBS[job_id].update({"status": "synthesising", "scenario_id": gen["scenario"]["id"]})
    voice = tts_provider.VOICES.get(character_id, gen["character"].get("voice_id", "en-US-GuyNeural"))
    tp = (gen.get("decision") or {}).get("tts_params") or {}
    # edge-tts wants +NN% rate; map our named rates
    rate = {"slow": "-15%", "normal": "+0%", "fast": "+12%"}.get(tp.get("rate", "normal"), "+0%")
    audio = tts_provider.synthesize(job_id, gen["full_text"], voice,
                                    rate=rate, pitch=tp.get("pitch", "+0Hz"))
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
    _record_graph_instance(job_id, character_id, gen, strat)


def _record_graph_instance(job_id: str, character_id: str,
                           gen: dict, strat: dict) -> None:
    """Bridge: audition persist → character graph instance.

    Writes to bgraph2 via SDK record_instance. Fail-open (logs, never
    crashes the audition). This closes the performer→manager loop:
    battle winners land in the graph, seed_state picks them up next round,
    influence2 direction reads them via fuse_character.
    """
    try:
        import sys as _sys
        import os as _os
        _sdk_dir = "/root/characters/sdk"
        if _sdk_dir not in _sys.path:
            _sys.path.insert(0, _sdk_dir)
        import character_sdk as _sdk
        decision = gen.get("decision") or {}
        inst = decision.get("instance") or {}
        instance = {
            "instance_id": job_id,
            "seed_id": gen.get("character", {}).get(
                "seed_version", "seed-overlay-v1"),
            "scenario_id": gen.get("scenario", {}).get("id", "unknown"),
            "modulator": inst.get("modulator") or decision.get("modulator"),
            "operator": inst.get("operator") or decision.get("operator"),
            "chooser": inst.get("chooser") or decision.get("chooser"),
            "battle_score": (decision.get("battle_score") or {}).get("total")
            if isinstance(decision.get("battle_score"), dict)
            else decision.get("battle_score"),
        }
        # drop Nones — SDK requires instance_id/seed_id/scenario_id only
        instance = {k: v for k, v in instance.items() if v is not None}
        _sdk.record_instance(character_id, instance)
    except Exception as e:
        # fail-open: graph write never blocks audition persistence
        print(f"[bridge] record_instance failed for {job_id}: {e}"[:200])


def _run_battle(job_id: str, character_id: str, matched: bool = False):
    conn = _conn()
    try:
        _job(job_id, character_id, "battle", "battling")
        import battle as _battle
        fb = store.recent_feedback(conn, character_id, 5)
        for f in fb:
            f["pog_count"] = conn.execute("SELECT COUNT(*) FROM pogs WHERE audition_id=?",
                                          (f["id"],)).fetchone()[0]
        _seen = {f["id"] for f in fb}
        for r in conn.execute("SELECT id, scenario_id, full_text, operator_ids FROM auditions"
                              " WHERE character_id=? ORDER BY created_at DESC LIMIT 8",
                              (character_id,)).fetchall():
            if r["id"] not in _seen:
                fb.append({"id": r["id"], "scenario_id": r["scenario_id"],
                           "full_text": r["full_text"], "comment": "",
                           "operator_ids": r["operator_ids"], "rating": 0, "pog_count": 0})
        strat = store.get_strategy(conn, character_id)
        seed = random.randint(1, 10**9)
        res = _battle.battle(character_id, fb, strat, n=3, seed=seed, matched=matched)
        gen = res["winner"]
        gen["decision"]["slop"] = {"battle": True, "mode": res.get("mode", "open")}
        gen["decision"]["battle_score"] = res["winner_score"]
        gen["decision"]["battle_table"] = [{k: v for k, v in c.items() if k != "text"}
                                           for c in res["table"]]
        store.record_battle(conn, job_id, character_id, res["table"], winner_idx=0)
        _persist_ready(job_id, character_id, conn, gen, strat, seed)
        JOBS[job_id].update({"status": "ready"}); _job(job_id, JOBS[job_id].get("character_id", ""), JOBS[job_id].get("mode", "single"), "ready")
    except Exception as e:
        JOBS[job_id].update({"status": "failed", "error": str(e)[:500]}); _job(job_id, JOBS[job_id].get("character_id", ""), JOBS[job_id].get("mode", "single"), "failed", str(e)[:500])
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
    JOBS[job_id] = {"status": "queued", "mode": "single", "character_id": character_id, "created_at": time.time()}
    _job(job_id, character_id, "single", "queued")
    threading.Thread(target=_run_generation, args=(job_id, character_id), daemon=True).start()
    return jsonify({"audition_id": job_id, "status": "queued"})


@app.post("/api/auditions/battle")
def create_battle():
    """Generate 3, classify, ship the winner. mode=matched holds one scenario
    across candidates so wins teach approach, not premise."""
    data = request.get_json(force=True) or {}
    character_id = data.get("character_id", "no_nose_nolan")
    matched = data.get("mode", "open") == "matched"
    ids = {c["id"] for c in generate.list_characters()}
    if character_id not in ids:
        return jsonify({"error": f"unknown character_id {character_id}"}), 400
    job_id = store.new_id("aud")
    JOBS[job_id] = {"status": "queued", "mode": "battle", "character_id": character_id, "created_at": time.time()}
    _job(job_id, character_id, "battle", "queued")
    threading.Thread(target=_run_battle, args=(job_id, character_id, matched), daemon=True).start()
    return jsonify({"audition_id": job_id, "status": "queued",
                    "mode": "battle-matched" if matched else "battle"})


@app.get("/api/characters/<character_id>/progress")
def progress(character_id: str):
    """Quantitative track: battle scores, ratings, POGs, room, retention over time."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT a.id, a.created_at, a.scenario_id, a.operator_ids, a.decision,
                      f.rating, f.comment, f.room_reaction,
                      (SELECT COUNT(*) FROM pogs p WHERE p.audition_id=a.id) AS pogs,
                      (SELECT AVG(CAST(watch_ms AS FLOAT)/MAX(duration_ms,1)) FROM short_views v
                        WHERE v.audition_id=a.id) AS retention
               FROM auditions a LEFT JOIN feedbacks f ON f.audition_id=a.id
               WHERE a.character_id=? ORDER BY a.created_at""", (character_id,)).fetchall()
        pts = []
        for r in rows:
            d = dict(r)
            try:
                dec = json.loads(d.get("decision") or "{}")
            except Exception:
                dec = {}
            inst = dec.get("instance", {}) or {}
            pts.append({"id": d["id"], "at": d["created_at"], "scenario": d["scenario_id"],
                        "operator": (json.loads(d.get("operator_ids") or "[]") or [None])[0],
                        "modulator": inst.get("modulator"), "chooser": inst.get("chooser"),
                        "battle": (dec.get("battle_score") or {}).get("total"),
                        "rating": d["rating"], "pogs": d["pogs"], "room": d["room_reaction"],
                        "retention": round(d["retention"], 3) if d["retention"] is not None else None})
        return jsonify({"character_id": character_id, "points": pts})
    finally:
        conn.close()


@app.get("/api/auditions/<aud_id>")
def get_audition(aud_id: str):
    if aud_id in JOBS and JOBS[aud_id].get("status") in ("queued", "generating", "synthesising", "battling"):
        return jsonify({"id": aud_id, "status": JOBS[aud_id]["status"],
                        "scenario_id": JOBS[aud_id].get("scenario_id", "")})
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
        job = None if row else conn.execute("SELECT * FROM jobs WHERE job_id=?", (aud_id,)).fetchone()
    finally:
        conn.close()
    if not row and job:
        return jsonify({"id": aud_id, "status": dict(job)["status"],
                        "error": dict(job)["error"] or None}), 200
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
        ev_ids = [r["id"] for r in rows]
        store.save_strategy(conn, aud["character_id"], ver, summ["success"], summ["failed"],
                            summ["instructions"], evidence=ev_ids,
                            changes=f"after {aud_id}: rating {rating}")
        return jsonify({**fb, "strategy": summ["instructions"], "strategy_version": ver})
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
    JOBS[job_id] = {"status": "queued", "mode": "single", "character_id": row["character_id"], "created_at": time.time()}
    _job(job_id, row["character_id"], "single", "queued")
    threading.Thread(target=_run_generation, args=(job_id, row["character_id"]), daemon=True).start()
    return jsonify({"audition_id": job_id, "status": "queued"})


@app.get("/api/auditions/<aud_id>/observations")
def observations(aud_id: str):
    """S8: evidence-linked observations. Set-level, beat-level, delivery, engagement kept separate."""
    conn = _conn()
    try:
        row = store.get_audition(conn, aud_id)
        if not row:
            return jsonify({"error": "unknown audition id"}), 404
        pogs = [dict(p) for p in conn.execute(
            "SELECT * FROM pogs WHERE audition_id=? ORDER BY playback_ms", (aud_id,)).fetchall()]
        fb = conn.execute("SELECT * FROM feedbacks WHERE audition_id=?", (aud_id,)).fetchone()
        ops = row["operator_ids"]
        beats = []
        for b in row["beats"]:
            bp = [p for p in pogs if p.get("beat_id") == b["id"]]
            beats.append({"beat_id": b["id"], "type": b["type"], "words": len(b["text"].split()),
                          "operator": (ops or [None])[0],
                          "operator_note": "minute-level operator; beat shares it (credit uncertainty)",
                          "pogs": [{"playback_ms": p["playback_ms"], "uncertain": bool(p["uncertain"])}
                                   for p in bp]})
        return jsonify({"audition_id": aud_id, "operator_ids": ops,
                        "set": {"rating": dict(fb)["rating"] if fb else None,
                                "room": (dict(fb).get("room_reaction") or None) if fb else None,
                                "comment": (dict(fb)["comment"] if fb else "") or None},
                        "beats": beats,
                        "engagement": {"pog_count": len(pogs),
                                       "sessions": len({p["iteration"] for p in pogs})},
                        "causal_note": "POG near a beat is correlation; mechanism claims stay hypotheses"})
    finally:
        conn.close()


@app.get("/api/characters/<character_id>/callbacks")
def callbacks(character_id: str):
    scenario_id = request.args.get("scenario_id", "")
    conn = _conn()
    try:
        return jsonify({"callbacks": store.propose_callbacks(conn, character_id, scenario_id)})
    finally:
        conn.close()


@app.post("/api/characters/<character_id>/reflect")
def reflect(character_id: str):
    """S9: evidence-linked strategy proposal. Proposes; never auto-accepts."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT a.id, a.scenario_id, a.operator_ids, a.decision, f.rating, f.comment,
                      (SELECT COUNT(*) FROM pogs p WHERE p.audition_id=a.id) AS pog_count
               FROM auditions a JOIN feedbacks f ON f.audition_id=a.id
               WHERE a.character_id=? ORDER BY f.submitted_at DESC LIMIT 10""",
            (character_id,)).fetchall()
        obs = [dict(r) for r in rows]
        if not obs:
            return jsonify({"error": "no rated auditions to reflect on"}), 400
        good = [o for o in obs if (o["rating"] or 0) >= 2 or (o.get("pog_count") or 0) >= 2]
        weak = [o for o in obs if o not in good]
        proposal = {
            "holds": sorted({(o.get("scenario_id"), (o.get("operator_ids") or "[]")) for o in good})[:5],
            "retire": sorted({(o.get("scenario_id"), (o.get("operator_ids") or "[]")) for o in weak})[:5],
            "experiment": "next minute: best held operator on a fresh scenario; predict rating>=2",
            "uncertainty": f"n={len(obs)} rated; correlation only",
        }
        return jsonify({"character_id": character_id, "proposal": proposal, "status": "proposed"})
    finally:
        conn.close()


@app.get("/api/characters/<character_id>/strategies")
def strategy_history(character_id: str):
    conn = _conn()
    try:
        rows = conn.execute("SELECT version, parent, instructions, evidence, hypotheses, changes,"
                            " uncertainties, status, created_at, hash FROM strategy_versions"
                            " WHERE character_id=? ORDER BY created_at", (character_id,)).fetchall()
        cur = store.current_strategy_version(conn, character_id)
        return jsonify({"current": cur, "versions": [dict(r) for r in rows]})
    finally:
        conn.close()


@app.post("/api/characters/<character_id>/strategies/<version>/status")
def strategy_status(character_id: str, version: str):
    data = request.get_json(force=True) or {}
    status = data.get("status", "")
    if status not in ("accepted", "rejected", "reverted"):
        return jsonify({"error": "status must be accepted/rejected/reverted"}), 400
    conn = _conn()
    try:
        if not store.get_strategy_at(conn, character_id, version):
            return jsonify({"error": "unknown strategy version"}), 404
        store.set_strategy_status(conn, character_id, version, status)
        return jsonify({"character_id": character_id, "version": version, "status": status})
    finally:
        conn.close()


@app.get("/api/battles/<job_id>/blind")
def battle_blind(job_id: str):
    """S10: blind A/B of winner vs best loser. Texts only; winner hidden until vote."""
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM battle_runs WHERE job_id=?", (job_id,)).fetchone()
        if not r:
            return jsonify({"error": "unknown battle"}), 404
        import json as _j
        table = _j.loads(r["table_json"])
        if len(table) < 2:
            return jsonify({"error": "battle had fewer than 2 candidates"}), 400
        pair = [{"label": "A", "idx": 0, "text": table[0]["text"]},
                {"label": "B", "idx": 1, "text": table[1]["text"]}]
        import random as _r
        _r.shuffle(pair)
        conn.execute("UPDATE battle_runs SET blind_map=? WHERE job_id=?",
                     (_j.dumps({p["label"]: p["idx"] for p in pair}), job_id))
        conn.commit()
        return jsonify({"job_id": job_id, "options": pair,
                        "note": "winner hidden; vote, then reveal"})
    finally:
        conn.close()


@app.post("/api/battles/<job_id>/blind_vote")
def battle_blind_vote(job_id: str):
    data = request.get_json(force=True) or {}
    pick = data.get("pick", "")
    if pick not in ("A", "B"):
        return jsonify({"error": "pick A or B"}), 400
    voter = str(data.get("voter_id", "anon"))[:64]
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM battle_runs WHERE job_id=?", (job_id,)).fetchone()
        if not r:
            return jsonify({"error": "unknown battle"}), 404
        import json as _j, time as _t
        try:
            mapping = _j.loads(r["blind_map"] or "{}")
        except Exception:
            mapping = {}
        if pick not in mapping:
            return jsonify({"error": "stale matchup — reload the blind pair and vote again"}), 409
        picked_idx = mapping[pick]
        votes = _j.loads(r["blind_votes"] or "[]")
        if any(v.get("voter_id") == voter for v in votes):
            return jsonify({"error": "already voted on this battle"}), 409
        votes.append({"pick": pick, "picked_idx": picked_idx,
                      "model_winner_idx": r["winner_idx"],
                      "agrees_with_model": picked_idx == r["winner_idx"],
                      "voter_id": voter, "at": _t.time()})
        conn.execute("UPDATE battle_runs SET blind_votes=? WHERE job_id=?",
                     (_j.dumps(votes), job_id))
        conn.commit()
        return jsonify({"job_id": job_id, "model_winner_idx": r["winner_idx"],
                        "you_picked_idx": picked_idx,
                        "agree": picked_idx == r["winner_idx"],
                        "votes": len(votes),
                        "note": "human pick resolved against stored shuffle map"})
    finally:
        conn.close()


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


@app.get("/watch")
def watch_page():
    return send_file(HERE / "static" / "watch.html")


@app.post("/api/gtvh/classify")
def gtvh_classify():
    """Comedic classifier: GTVH 6-tuple for any minute. Analysis, not a gate."""
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if len(text.split()) < 10:
        return jsonify({"error": "need at least 10 words"}), 400
    import gtvh
    return jsonify(gtvh.classify(text))


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


@app.get("/api/stage/rigs")
def stage_rigs():
    import stage as _st
    return jsonify({"rigs": _st.list_rigs()})


@app.get("/api/stage/stages")
def stage_stages():
    import stage as _st
    return jsonify({"stages": _st.list_stages()})


@app.get("/api/stage/character/<character_id>")
def stage_character(character_id: str):
    """Character Pack for the stage: psychology, emotions, gestures, voice.

    Powers the Stage Lab puppet + Rive mapping. Read-only; never mutates canon.
    """
    char = generate.get_character(character_id)
    rig = None
    import stage as _st
    for r in _st.list_rigs():
        if r.get("character_id") == character_id:
            rig = _st.load_rig(r["rig_id"])
    raw = (char.get("raw") or {}) if isinstance(char, dict) else {}
    return jsonify({
        "character_id": character_id, "name": char.get("name"),
        "deal": char.get("deal"), "want": char.get("want"), "fear": char.get("fear"),
        "blind_spots": char.get("blind_spots"), "action_policy": char.get("action_policy"),
        "philosophy": raw.get("philosophy", {}), "expression": raw.get("expression", {}),
        "modulator_range": raw.get("modulator_range") or raw.get("philosophy", {}).get("modulator_range", []),
        "misinterpretation_rule": raw.get("misinterpretation_rule", ""),
        "awareness": raw.get("awareness", "unknown"),
        "emotions": {m: (generate.load_modulators().get(m, {}) or {}).get("tilt", m)
                     for m in (generate.seed_modulators(char) if hasattr(generate, "seed_modulators") else [])},
        "rig": ({"rig_id": rig.get("rig_id"), "version": rig.get("version"),
                 "gestures": rig.get("gestures"), "expressions": rig.get("expressions"),
                 "mouth_shapes": rig.get("mouth_shapes"),
                 "movement_rules": rig.get("movement_rules"), "svg": rig.get("svg"),
                 "rive": rig.get("rive")} if rig else None),
    })


@app.post("/api/stage/direct/<aud_id>")
def stage_direct(aud_id: str):
    """Stage Director: beats + psychology -> proposed performance.v1 timeline."""
    import stage as _st
    data = request.get_json(force=True) or {}
    rig_id = data.get("rig_id", "ralph")
    stage_id = data.get("stage_id", "comedy_club")
    conn = _conn()
    try:
        aud = store.get_audition(conn, aud_id)
    finally:
        conn.close()
    if not aud:
        return jsonify({"error": "unknown audition id"}), 404
    rig = _st.load_rig(rig_id)
    stg = _st.load_stage(stage_id)
    if not rig:
        return jsonify({"error": f"unknown rig {rig_id}"}), 400
    if not stg:
        return jsonify({"error": f"unknown stage {stage_id}"}), 400
    tl = _st.direct(aud, rig, stg)
    errs = _st.validate_timeline(tl)
    if errs:
        return jsonify({"error": "; ".join(errs[:4])}), 400
    tid = store.new_id("tl")
    conn = _conn()
    try:
        conn.execute("INSERT INTO stage_timelines (id, audition_id, character_id, rig_id,"
                     " rig_version, stage_id, timeline, created_at) VALUES (?,?,?,?,?,?,?,?)",
                     (tid, aud_id, aud["character_id"], rig_id, rig.get("version", ""),
                      stage_id, json.dumps(tl), time.time()))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"timeline_id": tid, **tl})


@app.get("/api/stage/timeline/<tid>")
def stage_timeline(tid: str):
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM stage_timelines WHERE id=?", (tid,)).fetchone()
    finally:
        conn.close()
    if not r:
        return jsonify({"error": "unknown timeline"}), 404
    d = dict(r)
    d["timeline"] = json.loads(d["timeline"])
    return jsonify(d)


# ── Gemini performance sets (Ari engine) ──────────────────────────────
GEMINI_DIR = Path(__file__).parent.parent / "theory" / "killtony-minutes"


@app.get("/api/stage/gemini")
def stage_gemini_list():
    """List all Gemini-analyzed performance sets."""
    sets = []
    for p in sorted(GEMINI_DIR.glob("*_gemini.gemini.json")):
        stem = p.name.replace(".gemini.json", "")
        tl_path = GEMINI_DIR / f"{stem}.stage_timeline.json"
        player_path = GEMINI_DIR / f"{stem}_player.html"
        try:
            gem = json.loads(p.read_text())
        except Exception:
            continue
        segs = gem.get("segments") or []
        ang = gem.get("anger_analysis") or {}
        sets.append({
            "stem": stem,
            "title": stem.replace("_gemini", "").replace("_", " ").title(),
            "duration_s": segs[-1].get("t1") if segs else None,
            "n_segments": len(segs),
            "dominant_emotion": (gem.get("overall") or {}).get("dominant_emotion"),
            "anger_present": ang.get("present"),
            "anger_type": ang.get("type"),
            "has_timeline": tl_path.exists(),
            "has_player": player_path.exists(),
            "player_url": f"/stage/gemini/{stem}/player" if player_path.exists() else None,
            "timeline_url": f"/api/stage/gemini/{stem}/timeline" if tl_path.exists() else None,
        })
    return jsonify({"sets": sets, "count": len(sets)})


@app.get("/api/stage/gemini/<stem>/timeline")
def stage_gemini_timeline(stem: str):
    """Serve a Gemini→Stage Lab performance.v1 timeline."""
    tl_path = GEMINI_DIR / f"{stem}.stage_timeline.json"
    if not tl_path.exists():
        return jsonify({"error": "unknown gemini set"}), 404
    return jsonify(json.loads(tl_path.read_text()))


@app.get("/api/stage/gemini/<stem>/raw")
def stage_gemini_raw(stem: str):
    """Serve the raw Gemini analysis JSON."""
    p = GEMINI_DIR / f"{stem}.gemini.json"
    if not p.exists():
        return jsonify({"error": "unknown gemini set"}), 404
    return jsonify(json.loads(p.read_text()))


@app.get("/stage/gemini/<stem>/player")
def stage_gemini_player(stem: str):
    """Serve the standalone Ralph player HTML for a Gemini set."""
    p = GEMINI_DIR / f"{stem}_player.html"
    if not p.exists():
        return jsonify({"error": "no player"}), 404
    return send_file(p, mimetype="text/html")


@app.get("/stage/gemini")
def stage_gemini_gallery():
    """Gallery page listing all Gemini performance sets."""
    return send_file(GEMINI_DIR.parent.parent / "audition" / "static" / "gemini_stage.html",
                     mimetype="text/html")


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval on a proportion. Significant iff CI excludes 0.5."""
    if n <= 0:
        return (0.0, 1.0)
    p = wins / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


@app.get("/arena")
def arena_page():
    return send_file(HERE / "static" / "arena.html")


@app.post("/api/arena/contenders")
def arena_add():
    import re as _re
    import urllib.request as _url
    data = request.get_json(force=True) or {}
    kind = data.get("kind", "")
    ref = (data.get("ref") or "").strip()
    title = (data.get("title") or "").strip()[:120]
    if kind == "youtube":
        m = _re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", ref) or _re.fullmatch(r"[\w-]{11}", ref)
        vid = (m.group(1) if m and m.groups() else ref) if m else ""
        if not _re.fullmatch(r"[\w-]{11}", vid or ""):
            return jsonify({"error": "need a YouTube Shorts URL or 11-char video id"}), 400
        try:  # oEmbed: verifies existence + embeddability without API quota
            o = _url.urlopen(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json",
                             timeout=15)
            meta = json.loads(o.read().decode())
            title = title or (meta.get("title", "") + f" — {meta.get('author_name','')}")[:120]
        except Exception:
            return jsonify({"error": "video not found or embedding disabled (respect owner's setting)"}), 400
        ref = vid
    elif kind == "audition":
        conn = _conn()
        try:
            aud = store.get_audition(conn, ref)
        finally:
            conn.close()
        if not aud:
            return jsonify({"error": "unknown audition id"}), 404
        title = title or f"{aud['character_id']} · {aud['scenario_id']}"
    elif kind == "bluesky":
        # Import direction: any Bluesky post (video-friendly) can duel.
        # Official embeds only; handle->DID via public API, no auth needed.
        m = _re.search(r"bsky\.app/profile/([^/]+)/post/([A-Za-z0-9]+)", ref)
        if not m:
            return jsonify({"error": "need a Bluesky post URL (bsky.app/profile/…/post/…)"}), 400
        handle, rkey = m.group(1), m.group(2)
        try:
            dh = _url.urlopen(
                f"https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle?handle={handle}",
                timeout=15)
            did = json.loads(dh.read().decode())["did"]
            ph = _url.urlopen(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts?uris=" +
                f"at%3A%2F%2F{did}%2Fapp.bsky.feed.post%2F{rkey}", timeout=15)
            post = json.loads(ph.read().decode())["posts"][0]
            txt = (post.get("record", {}) or {}).get("text", "")
            title = title or (f"@{handle}: {txt[:90]}" if txt else f"@{handle} on Bluesky")
        except Exception:
            return jsonify({"error": "couldn't resolve that Bluesky post (deleted? private? typo?)"}), 400
        ref = f"{did}/app.bsky.feed.post/{rkey}"
    elif kind == "tavern":
        conn0 = _conn()
        try:
            t = conn0.execute("SELECT * FROM tavern_imports WHERE id=?", (ref,)).fetchone()
        finally:
            conn0.close()
        if not t:
            return jsonify({"error": "unknown tavern import id — import the card first"}), 404
        title = title or f"{t['name']} (community card)"
    else:
        return jsonify({"error": "kind must be youtube|audition|bluesky|tavern"}), 400
    theories: list = []
    operators: list = []
    if kind == "audition":
        # Link the vote to humour theory: copy the set's mechanism tags so
        # every duel is also evidence for/against the theories behind it.
        conn0 = _conn()
        try:
            aud0 = store.get_audition(conn0, ref)
        finally:
            conn0.close()
        if aud0:
            theories = list(aud0.get("theory_ids") or [])
            operators = list(aud0.get("operator_ids") or [])
    conn = _conn()
    try:
        if conn.execute("SELECT 1 FROM arena_contenders WHERE kind=? AND ref=?", (kind, ref)).fetchone():
            return jsonify({"error": "already in the arena"}), 409
        cid = store.new_id("arena")
        author = (data.get("author") or "").strip()[:40]
        if not author:
            # human funnier vs agent benchmarks vs characters: who made this?
            author = "character" if kind == "audition" else "human"
        conn.execute("INSERT INTO arena_contenders (id, kind, ref, title, elo, theories, operators, author_type, created_at)"
                     " VALUES (?,?,?,?,1500,?,?,?,?)",
                     (cid, kind, ref, title, json.dumps(theories), json.dumps(operators), author, time.time()))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"contender_id": cid, "kind": kind, "ref": ref, "title": title, "author_type": author})


@app.get("/api/arena/matchup")
def arena_matchup():
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute(
            """SELECT c.*, (SELECT COUNT(*) FROM arena_votes v
                 WHERE v.a_id=c.id OR v.b_id=c.id) AS bouts
              FROM arena_contenders c ORDER BY bouts, RANDOM() LIMIT 6""").fetchall()]
    finally:
        conn.close()
    if len(rows) < 2:
        return jsonify({"error": "need at least 2 contenders — add Shorts URLs or auditions"}), 400
    import random as _r
    a, b = _r.sample(rows, 2)
    if _r.random() < 0.5:
        a, b = b, a
    hide = lambda c: {"id": c["id"], "kind": c["kind"], "ref": c["ref"], "title": c["title"]}
    mid = store.new_id("match")
    conn2 = _conn()
    try:
        conn2.execute("INSERT INTO arena_matches (id, a_id, b_id, created_at) VALUES (?,?,?,?)",
                      (mid, a["id"], b["id"], time.time()))
        conn2.commit()
    finally:
        conn2.close()
    return jsonify({"match_id": mid, "a": hide(a), "b": hide(b),
                    "note": "titles shown, ratings hidden — vote the set, not the reputation"})


@app.post("/api/arena/vote")
def arena_vote():
    data = request.get_json(force=True) or {}
    a_id, b_id, w_id = data.get("a_id", ""), data.get("b_id", ""), data.get("winner_id", "")
    if not a_id or not b_id or w_id not in (a_id, b_id):
        return jsonify({"error": "need a_id, b_id and winner_id of one of them"}), 400
    voter = str(data.get("voter_id", "anon"))[:64]
    world = str(data.get("world_id", ""))[:64]
    try:
        context = json.dumps(data.get("context", {}) or {})[:500]
    except Exception:
        context = "{}"
    conn = _conn()
    try:
        m = None
        if data.get("match_id"):
            m = conn.execute("SELECT * FROM arena_matches WHERE id=?", (data["match_id"],)).fetchone()
            if not m or {m["a_id"], m["b_id"]} != {a_id, b_id}:
                return jsonify({"error": "stale matchup — fetch a fresh pair and vote again"}), 409
        ra = conn.execute("SELECT * FROM arena_contenders WHERE id=?", (a_id,)).fetchone()
        rb = conn.execute("SELECT * FROM arena_contenders WHERE id=?", (b_id,)).fetchone()
        if not ra or not rb:
            return jsonify({"error": "unknown contender"}), 404
        if conn.execute("SELECT 1 FROM arena_votes WHERE voter_id=? AND ((a_id=? AND b_id=?) OR (a_id=? AND b_id=?))",
                        (voter, a_id, b_id, b_id, a_id)).fetchone():
            return jsonify({"error": "already voted on this pair"}), 409
        ea, eb = float(ra["elo"]), float(rb["elo"])
        sa = 1.0 if w_id == a_id else 0.0
        xa = 1 / (1 + 10 ** ((eb - ea) / 400))
        K = 32
        ea2, eb2 = ea + K * (sa - xa), eb + K * ((1 - sa) - (1 - xa))
        conn.execute("UPDATE arena_contenders SET elo=? WHERE id=?", (round(ea2, 1), a_id))
        conn.execute("UPDATE arena_contenders SET elo=? WHERE id=?", (round(eb2, 1), b_id))
        conn.execute("INSERT INTO arena_votes (id, a_id, b_id, winner_id, voter_id, context, world_id, created_at)"
                     " VALUES (?,?,?,?,?,?,?,?)",
                     (store.new_id("vote"), a_id, b_id, w_id, voter, context, world, time.time()))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"a_elo": round(ea2, 1), "b_elo": round(eb2, 1)})


@app.get("/api/arena/leaderboard")
def arena_board():
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM arena_contenders").fetchall()]
        votes = [dict(r) for r in conn.execute("SELECT * FROM arena_votes").fetchall()]
    finally:
        conn.close()
    wins: dict[str, int] = {}
    bouts: dict[str, int] = {}
    for v in votes:
        bouts[v["a_id"]] = bouts.get(v["a_id"], 0) + 1
        bouts[v["b_id"]] = bouts.get(v["b_id"], 0) + 1
        wins[v["winner_id"]] = wins.get(v["winner_id"], 0) + 1
    board = []
    for c in rows:
        n, w = bouts.get(c["id"], 0), wins.get(c["id"], 0)
        lo, hi = _wilson(w, n)
        board.append({"id": c["id"], "kind": c["kind"], "ref": c["ref"], "title": c["title"],
                      "author_type": c.get("author_type") or ("character" if c["kind"] == "audition" else "human"),
                      "elo": c["elo"], "wins": w, "bouts": n,
                      "wilson_lo": round(lo, 3), "wilson_hi": round(hi, 3),
                      "significant": bool(n >= 30 and (hi < 0.5 or lo > 0.5))})
    board.sort(key=lambda r: -r["elo"])
    groups: dict[str, list] = {}
    for r in board:
        groups.setdefault(r["author_type"], []).append(r["id"])
    return jsonify({"board": board, "votes": len(votes), "groups": groups,
                    "note": "crowd-ranked with uncertainty — Wilson CI; 'funniest' needs n≥30 and CI excluding 0.5;"
                            " humans, agents and characters share one ballot but keep separate tables"})


@app.get("/api/arena/theories")
def arena_theories():
    """Which humour mechanisms are winning duels? Votes as theory evidence."""
    conn = _conn()
    try:
        conts = [dict(r) for r in conn.execute("SELECT * FROM arena_contenders").fetchall()]
        votes = [dict(r) for r in conn.execute("SELECT * FROM arena_votes").fetchall()]
    finally:
        conn.close()
    by_id = {c["id"]: c for c in conts}
    tw: dict[str, int] = {}
    tb: dict[str, int] = {}
    for v in votes:
        for cid, won in ((v["a_id"], v["winner_id"] == v["a_id"]),
                         (v["b_id"], v["winner_id"] == v["b_id"])):
            c = by_id.get(cid)
            if not c:
                continue
            try:
                tags = json.loads(c.get("theories") or "[]") + json.loads(c.get("operators") or "[]")
            except Exception:
                tags = []
            for t in set(tags):
                tb[t] = tb.get(t, 0) + 1
                if won:
                    tw[t] = tw.get(t, 0) + 1
    rows = []
    for t, n in sorted(tb.items(), key=lambda kv: -kv[1]):
        lo, hi = _wilson(tw.get(t, 0), n)
        rows.append({"theory": t, "wins": tw.get(t, 0), "bouts": n,
                     "wilson_lo": round(lo, 3), "wilson_hi": round(hi, 3)})
    return jsonify({"theories": rows,
                    "note": "duel votes double as mechanism evidence; KT priors were the seed, this is the harvest"})


@app.post("/api/arena/ai_bracket")
def arena_ai_bracket():
    """One-click AI bracket: each character's latest ready set enters the arena."""
    conn = _conn()
    try:
        chars = [c["id"] for c in generate.list_characters()]
        entered = []
        for ch in chars:
            r = conn.execute("SELECT id FROM auditions WHERE character_id=? AND status='ready'"
                             " ORDER BY created_at DESC LIMIT 1", (ch,)).fetchone()
            if not r:
                continue
            aud = store.get_audition(conn, r["id"])
            if conn.execute("SELECT 1 FROM arena_contenders WHERE kind='audition' AND ref=?",
                            (aud["id"],)).fetchone():
                entered.append({"audition_id": aud["id"], "status": "already in"})
                continue
            cid = store.new_id("arena")
            conn.execute("INSERT INTO arena_contenders (id, kind, ref, title, elo, theories, operators, author_type, created_at)"
                         " VALUES (?,?,?,?,1500,?,?,?,?)",
                         (cid, "audition", aud["id"],
                          f"{aud['character_id']} · {aud['scenario_id']}",
                          json.dumps(aud.get("theory_ids") or []),
                          json.dumps(aud.get("operator_ids") or []), "character", time.time()))
            entered.append({"audition_id": aud["id"], "contender_id": cid, "status": "entered"})
        conn.commit()
    finally:
        conn.close()
    return jsonify({"entered": entered,
                    "note": "humans vs AI on the same ballot — vote the set, not the species"})


@app.get("/tavern/portrait/<iid>")
def tavern_portrait(iid: str):
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM tavern_imports WHERE id=?", (iid,)).fetchone()
    finally:
        conn.close()
    if not r or not r["portrait_path"]:
        return jsonify({"error": "no portrait"}), 404
    p = Path(r["portrait_path"])
    if not p.exists():
        return jsonify({"error": "portrait file missing"}), 410
    return send_file(p, mimetype="image/png")


@app.get("/pogtown")
def pogtown_page():
    return send_file(HERE / "static" / "pogtown.html")


@app.get("/api/cards/ours/<character_id>")
def card_export(character_id: str):
    """Download one of ours as a Tavern V2 PNG (portrait + card + lorebook)."""
    import tavern as _tav
    from flask import Response as _Resp
    try:
        png, fn = _tav.export_card(character_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return _Resp(png, mimetype="image/png",
                 headers={"Content-Disposition": f"attachment; filename={fn}"})


@app.post("/api/cards/import")
def card_import():
    """Import a community card (upload field 'card' or JSON {url}). Stored, then arena-eligible."""
    import tavern as _tav
    import base64 as _b64
    raw, source = b"", ""
    if "card" in (request.files or {}):
        raw = request.files["card"].read(8 * 1024 * 1024)
    else:
        data = request.get_json(force=True, silent=True) or {}
        source = (data.get("url") or "").strip()
        if not source.startswith(("http://", "https://")):
            return jsonify({"error": "upload a card file or give an http(s) card URL"}), 400
        import urllib.request as _url
        try:
            raw = _url.urlopen(source, timeout=30).read(8 * 1024 * 1024)
        except Exception:
            return jsonify({"error": "couldn't fetch that URL"}), 400
    if not raw:
        return jsonify({"error": "empty card"}), 400
    try:
        card = _tav.import_card(raw, source)
    except Exception as e:
        return jsonify({"error": f"not a readable Tavern card: {e}"[:200]}), 400
    iid = store.new_id("tavern")
    ppath = ""
    if card.get("portrait"):
        ppath = str(HERE / "audio" / f"{iid}.png")
        open(ppath, "wb").write(_b64.b64decode(card["portrait"]))
        card["portrait"] = ""
    conn = _conn()
    try:
        conn.execute("INSERT INTO tavern_imports (id, name, spec, card_json, portrait_path, source_url, created_at)"
                     " VALUES (?,?,?,?,?,?,?)",
                     (iid, card["name"][:120], card.get("spec", ""), json.dumps(card),
                      ppath, source, time.time()))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"import_id": iid, "name": card["name"], "spec": card.get("spec"),
                    "book_entries": card.get("book_entries", 0),
                    "arena_ref": iid})


@app.get("/mp4/<aud_id>")
def mp4_serve(aud_id: str):
    """Real Shorts file: render-on-demand, cache keyed by content versions."""
    import render as _render
    import stage as _stage
    from pathlib import Path as _P
    conn = _conn()
    try:
        aud = store.get_audition(conn, aud_id)
    finally:
        conn.close()
    if not aud:
        return jsonify({"error": "unknown audition id"}), 404
    rig = _stage.load_rig("ralph")  # version probe; per-character rigs resolve in render
    try:
        import generate as _gen
        rigs = {r["character_id"]: r["rig_id"] for r in _stage.list_rigs()}
        chars = {c["id"]: c["id"] for c in _gen.list_characters()}
        _ = (rig, chars)
    except Exception:
        rigs = {}
    char_rig = rigs.get(aud["character_id"], "ralph")
    rver = (_stage.load_rig(char_rig) or {}).get("version", "?")
    dh = _stage._hash_beats(aud.get("beats") or [])
    key = {"rig": char_rig, "rig_version": rver, "delivery": dh,
           "renderer": "render_mp4_pil_v3"}
    out = _P(f"/tmp/opencode/{aud_id}.mp4")
    man = _P(f"/tmp/opencode/{aud_id}.mp4.json")
    fresh = False
    try:
        fresh = (out.exists() and out.stat().st_size > 100000 and man.exists()
                 and json.loads(man.read_text()).get("key") == key)
    except Exception:
        fresh = False
    if not fresh:
        import generate as _gen2
        _ = _gen2
        style = {"reptilian_ralph_middle_management": "adventurer",
                 "no_nose_nolan": "personas",
                 "rudy_dulce_hvac": "bottts",
                 "zeus_sky_sovereign": "adventurer",
                 "hera_queen_ledger": "lorelei"}.get(aud["character_id"], "adventurer")
        try:
            _render.render_mp4(aud, out, style=style)
            man.write_text(json.dumps({"key": key}))
        except Exception as e:
            return jsonify({"error": f"render failed: {e}"[:300]}), 500
    return send_file(out, mimetype="video/mp4", as_attachment=False,
                     download_name=f"{aud_id}.mp4")


if __name__ == "__main__":
    _startup_sweep()
    print("Audition app on http://127.0.0.1:8807/")
    app.run(host="127.0.0.1", port=8807, threaded=True)
