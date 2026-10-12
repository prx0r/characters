"""Real-human pack tests: python3 -m pytest audition/test_human_pack.py -q"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import gates  # noqa: E402
import generate  # noqa: E402
import validate_pack  # noqa: E402

SLUG = "chris-prior-golf-dad"


def _scen(i=0):
    return json.loads((ROOT / "freaks" / SLUG / "scenarios.json").read_text())["scenarios"][i]


def test_pack_loads_as_human():
    c = generate.get_character("chris_prior_golf_dad")
    assert c["name"].startswith("Chris Prior")
    assert generate.is_human(c)
    assert not generate.league_eligible("chris_prior_golf_dad")
    assert not generate.league_eligible("cathy_prior")


def test_packs_validate():
    for slug in (SLUG, "cathy-prior", "reptilian-ralph-middle-management"):
        r = validate_pack.validate(ROOT / "freaks" / slug)
        assert r["ok"], (slug, r["errors"])


def test_short_set_through_pipeline():
    strat = {"success": {}, "failed": {}, "instructions": "", "version": "strategy_01"}
    for i in range(4):
        g = generate.generate_minute("chris_prior_golf_dad", [], strat, seed=11 + i, scenario=_scen(i), length="short")
        assert generate.validate_minute(g, "chris_prior_golf_dad", fmt="short") == []
        assert g["decision"]["instance"]["operator"] in _scen(i)["punches"]
        assert g["beats"][-1]["type"] == "closer"
        assert sum(len(b["text"].split()) for b in g["beats"]) <= generate.SHORT_WORD_BUDGET


def test_privacy_hard_gates_veto():
    raw = generate.get_character("chris_prior_golf_dad")["raw"]
    bad = [{"id": "b1", "text": "Look at that belly, he's had a visit to the doctor."}]
    g = gates.check(bad, character=raw)
    assert not g["passed"]
    assert any("body_shaming" in v for v in g["vetoes"]) and any("medical" in v for v in g["vetoes"])
    ok = [{"id": "b1", "text": "I eat super healthily, and still they tease me."}]
    assert gates.check(ok, character=raw)["passed"]


def test_private_world_seed_and_sketch():
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "w.db")
        for w in ("prior-family", "greek"):
            subprocess.run([sys.executable, str(ROOT / "research/seed_world.py"), "--world", w, "--db", db],
                           check=True, capture_output=True, env={"PYTHONPATH": str(HERE), "PATH": "/usr/bin:/bin"})
        import store
        conn = store.connect(db)
        try:
            assert conn.execute("SELECT visibility FROM worlds WHERE world_id='prior-family'").fetchone()[0] == "private"
            r = conn.execute("SELECT role, league_eligible, visibility FROM world_residents"
                             " WHERE world_id='greek' AND canon_id=?", (SLUG,)).fetchone()
            assert tuple(r) == ("visitor", 0, "private")
            edge = conn.execute("SELECT charge FROM world_relationships WHERE world_id='prior-family'").fetchone()[0]
        finally:
            conn.close()
    import formats
    kit = json.loads((ROOT / "worlds/prior-family/kits/evening-audit.json").read_text())
    sk = formats.sketch_from_edge("prior-family", SLUG, "cathy-prior", edge, kit)
    assert sk["passed"] and sk["lines"][-1]["type"] == "closer" and sk["operator"] in kit["operators"]
