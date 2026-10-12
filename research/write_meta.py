"""(Re)write meta.json hashes for a pack: python3 research/write_meta.py freaks/<slug>"""
import hashlib, json, sys, time
from pathlib import Path

for arg in sys.argv[1:]:
    pack = Path(arg)
    mp = pack / "meta.json"
    m = json.loads(mp.read_text()) if mp.exists() else {}
    c = json.loads((pack / "character.json").read_text())
    now = time.strftime("%a %Y-%m-%d %I:%M %p (UTC+07:00)", time.gmtime(time.time() + 7 * 3600))
    m.setdefault("slug", pack.name); m.setdefault("created_at", now); m["updated_at"] = now
    m.setdefault("creator", "characters-foundry-v1")
    m["status"] = m.get("status", "ready")
    files = {}
    for fn in ("character.json", "delivery.json", "scenarios.json", "set.wav"):
        if (pack / fn).exists():
            files[fn] = "sha256:" + hashlib.sha256((pack / fn).read_bytes()).hexdigest()
    m["files"] = files
    if (pack / "delivery.json").exists():
        d = json.loads((pack / "delivery.json").read_text())
        m["beat_count"] = len(d["beats"]); m["word_count"] = sum(len(b["text"].split()) for b in d["beats"])
        m["voice"] = (d.get("voice") or {}).get("voice_id", "")
    if c.get("world_type") == "human":
        pv = c.get("privacy") or {}
        m["visibility"] = pv.get("visibility", "private")
        m["league_eligible"] = pv.get("league_eligible", False)
        m["voice_cloning"] = pv.get("voice_cloning", False)
    m["lineage"] = m.get("lineage") or {"relation": "interpretation", "parent": None, "root": c.get("canon"), "depth": 1}
    mp.write_text(json.dumps(m, indent=2))
    print("wrote", mp)
