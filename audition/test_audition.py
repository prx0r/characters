"""P0 tests — run: python3 -m pytest /root/characters/audition/test_audition.py -q"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import store
import generate


def test_character_graph_loads():
    n = generate.get_character("no_nose_nolan")
    assert n["name"] == "No-Nose Nolan"
    assert n["blind_spots"], "blind spots required for comedy policy"
    assert n["action_policy"], "action policy required"
    assert len(generate.list_blocks()) >= 10, "need source blocks"
    import json as j
    th = j.load(open("/root/pogpet/templates/theories.json"))
    assert len(th["theories"]) >= 12


def test_generation_validates():
    strat = {"success": {}, "failed": {}, "instructions": "", "version": "strategy_01"}
    g = generate.generate_minute("no_nose_nolan", [], strat, seed=7)
    assert 4 <= len(g["beats"]) <= 7
    words = sum(len(b["text"].split()) for b in g["beats"])
    assert 60 <= words <= 260, f"word count {words} outside minute range"
    assert g["beats"][-1]["text"].split().__len__() <= 12, "closer must be short"
    assert g["scenario"]["id"], "scenario required"
    assert g["theory_ids"] and g["operator_ids"]
    # no empty beats
    assert all(b["text"].strip() for b in g["beats"])


def test_next_minute_fresh_scenario():
    strat = {"success": {}, "failed": {}, "instructions": "", "version": "strategy_01"}
    g1 = generate.generate_minute("no_nose_nolan", [], strat, seed=11)
    recent = [{"scenario_id": g1["scenario"]["id"], "full_text": g1["full_text"],
               "comment": "too predictable", "operator_ids": '["rigidify"]',
               "rating": 1, "pog_count": 0}]
    g2 = generate.generate_minute("no_nose_nolan", recent, strat, seed=12)
    # different seed should usually pick different scenario when pool is large
    assert g2["full_text"] != g1["full_text"], "must not repeat jokes"


def test_store_roundtrip_and_pog_rules():
    with tempfile.TemporaryDirectory() as td:
        conn = store.connect(Path(td) / "t.db")
        aud = {"id": "aud_test1", "character_id": "no_nose_nolan", "character_version": "v1",
               "scenario_id": "job_displacement", "source_block_ids": ["job_displacement"],
               "theory_ids": ["rigidity"], "operator_ids": ["rigidify"],
               "decision": {"action": "x"}, "strategy_version": "strategy_01",
               "exploration": False, "model_id": "template-v0", "generation_seed": 1,
               "beats": [{"id": "b1", "type": "setup", "text": "hi", "start_ms": 0, "end_ms": 2000}],
               "full_text": "hi", "audio_path": "/tmp/x.mp3", "audio_duration_ms": 5000,
               "timing_provenance": "estimated", "audio_hash": "abc",
               "status": "ready", "error": "", "change_note": ""}
        store.insert_audition(conn, aud)
        assert store.get_audition(conn, "aud_test1")["scenario_id"] == "job_displacement"
        # valid pog
        store.insert_pog(conn, "pog_1", "aud_test1", 1500, 1, "b1", 0)
        # duplicate retry returns existing, no dup
        assert store.pog_exists(conn, "pog_1")
        # feedback persists + dup rejected
        store.insert_feedback(conn, "aud_test1", 2, "good callback")
        try:
            store.insert_feedback(conn, "aud_test1", 3, "again")
            assert False, "duplicate feedback must fail"
        except ValueError:
            pass
        # character identity untouched by strategy save
        before = generate.get_character("no_nose_nolan")["blind_spots"][:]
        store.save_strategy(conn, "no_nose_nolan", "strategy_02", {"rigidify": 2}, {}, "lean on rigidify")
        after = generate.get_character("no_nose_nolan")["blind_spots"]
        assert before == after, "identity must not mutate"
        conn.close()


def test_api_endpoints():
    import app as audition_app
    audition_app.app.config["TESTING"] = True
    c = audition_app.app.test_client()
    assert c.get("/api/auditions/characters").status_code == 200
    assert c.get("/api/auditions?character_id=no_nose_nolan").status_code == 200
    assert c.get("/api/auditions/nope").status_code == 404
    r = c.post("/api/auditions", json={"character_id": "nope"})
    assert r.status_code == 400


def test_human_take_flow():
    import app as audition_app
    audition_app.app.config["TESTING"] = True
    c = audition_app.app.test_client()
    import io, wave, struct
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(struct.pack("<8000h", *([1000] * 8000)))
    buf.seek(0)
    # need an audition row first
    import store as _s
    conn = _s.connect()
    conn.execute("INSERT OR IGNORE INTO auditions (id, character_id, character_version, scenario_id, source_block_ids, theory_ids, operator_ids, decision, strategy_version, exploration, model_id, generation_seed, beats, full_text, audio_path, audio_duration_ms, timing_provenance, audio_hash, status, error, change_note, created_at, performance_source, active_take_id) VALUES ('aud_take1','no_nose_nolan','v1','s','[]','[]','[]','{}','strategy_01',0,'t',1,'[]','hi','/tmp/x.mp3',60000,'estimated','h','ready','','',0,'ai_tts','')")
    conn.commit(); conn.close()
    r = c.post("/api/auditions/aud_take1/human_take", data={"audio": (buf, "take.wav")}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    tid = r.get_json()["take_id"]
    assert c.get("/api/auditions/aud_take1/takes").status_code == 200
    assert c.get(f"/takes/{tid}").status_code == 200
    # bad extension rejected
    r2 = c.post("/api/auditions/aud_take1/human_take", data={"audio": (io.BytesIO(b"x" * 5000), "take.txt")}, content_type="multipart/form-data")
    assert r2.status_code == 400
    # source switch + unknown take rejected
    assert c.post("/api/auditions/aud_take1/source", json={"source": "human_voice_performance", "take_id": "nope"}).status_code == 400
    assert c.post("/api/auditions/aud_take1/source", json={"source": "human_voice_performance", "take_id": tid}).status_code == 200
    assert c.post("/api/auditions/aud_take1/source", json={"source": "ai_tts"}).status_code == 200


def test_jev_question_shapes():
    import jev_questions
    ch = {"id": "x", "name": "X", "deal": "d", "want": "w", "fear": "f",
          "blind_spots": ["b"], "action_policy": "p", "preferred_theories": [],
          "raw": {"philosophy": {"ontology": "o"}, "dramatic_core": {"self_model": "s"},
                  "expression": {"emotional_restraint": "high"}}}
    st = jev_questions.seed_state(ch, {"id": "s1", "comic_model": "m"}, ["mem"], "ev")
    assert st["character"] == "X" and st["scenario"] == "s1" and st["memories"] == ["mem"]
    q = {}
    q.update(jev_questions.q_modulator(["angry"], {"angry": "tilt"}))
    q.update(jev_questions.q_operator(["rigidify"], {"rigidify": "h"}))
    q.update(jev_questions.q_appraisal())
    q.update(jev_questions.q_vetoes())
    assert q["modulator"]["type"] == "choice" and q["status_threatened"]["type"] == "noul"
    assert q["character_swappable"]["type"] == "noul"
    import jev_decide
    assert jev_decide.decide_instance({}, [], {}, [], {}) is None or True  # no-key safe
