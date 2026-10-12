"""Character pack validator (Freaktown Character Pack v1 + human-pack rules).

  python3 audition/validate_pack.py freaks/<slug> [freaks/<slug> ...]   (or --all)

freaktown's scripts/validate_pack.py is not reachable from every box, so the
rules README.md states for packs are enforced here: name required, canon
exists, delivery is freaktown.delivery.v1 with 11 beats ending on a closer
under 8 words, metadata counts match, meta.json hashes match the files, and
gates.check passes on the beats. Real-human packs (world_type human) also need:
provenance on every fact (user_stated / invented), privacy private + not
league-eligible + no voice cloning, compilable hard gates that actually fire,
and age consistent with dob. Light nodes (node_weight light) skip delivery.
Exit 1 if any pack fails.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import gates  # noqa: E402

BEAT_TYPES = {"setup", "punchline", "tag", "closer", "callback", "misdirect", "escalation", "opener"}
PROV = {"user_stated", "invented"}


def _sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def validate(pack: Path) -> dict:
    errs, warns = [], []
    cj = pack / "character.json"
    if not cj.exists():
        return {"pack": pack.name, "ok": False, "errors": ["missing character.json"], "warnings": []}
    c = json.loads(cj.read_text())
    if not c.get("name"):
        errs.append("character.name REQUIRED")
    canon = c.get("canon")
    if canon and not (ROOT / "canon" / canon / "canon.json").exists():
        errs.append(f"canon '{canon}' has no canon/{canon}/canon.json")
    if not c.get("misinterpretation_rule"):
        warns.append("no misinterpretation_rule (joke-generating rule)")
    human = c.get("world_type") == "human" or str(canon or "").startswith("human")
    light = c.get("node_weight") == "light"
    if human:
        for k in ("id", "version"):
            if not c.get(k):
                errs.append(f"human pack needs {k}")
        prov = c.get("provenance") or []
        if not prov or any(p.get("kind") not in PROV for p in prov):
            errs.append("provenance[] required, each kind in user_stated|invented")
        per = c.get("persona") or {}
        if per.get("facts") and per.get("facts_provenance") != "user_stated":
            errs.append("persona.facts must be user_stated (flourishes go in persona.flourishes)")
        for f in per.get("flourishes") or []:
            if f.get("provenance") != "invented":
                errs.append(f"flourish without provenance=invented: {f.get('text', '')[:40]}")
        if c.get("misinterpretation_rule") and c.get("misinterpretation_rule_provenance") not in PROV:
            errs.append("misinterpretation_rule_provenance missing")
        pv = c.get("privacy") or {}
        if pv.get("visibility") != "private":
            errs.append("real person: privacy.visibility must be private")
        if pv.get("league_eligible") is not False or pv.get("public_league_entry") is not False:
            errs.append("real person: league_eligible/public_league_entry must be false")
        if pv.get("voice_cloning") is not False or (c.get("voice") or {}).get("cloning") not in (False, None):
            errs.append("real person: voice cloning must be off")
        hg = pv.get("hard_gates") or []
        if not hg:
            errs.append("real person: privacy.hard_gates required")
        for g in hg:
            try:
                re.compile(g["pattern"])
            except (re.error, KeyError):
                errs.append(f"hard gate {g.get('id')} pattern does not compile")
        # gates must actually fire: probe each gate with its own first alternative
        for g in hg:
            m = re.search(r"\(([^()|?]+)", g.get("pattern", ""))
            probe = (m.group(1).replace("\\b", "").replace("\\w*", "") if m else "")
            if probe and not gates.privacy_check([{"id": "probe", "text": f"x {probe} x"}], c):
                warns.append(f"hard gate {g.get('id')} did not fire on probe '{probe}'")
        if c.get("dob") and c.get("age"):
            dob = dt.date.fromisoformat(c["dob"])
            asof = dt.date.fromisoformat(c["age"]["as_of"])
            yrs = asof.year - dob.year - ((asof.month, asof.day) < (dob.month, dob.day))
            if yrs != c["age"].get("years"):
                errs.append(f"age.years {c['age'].get('years')} != {yrs} from dob")
            if c["age"].get("on"):
                on = dt.date.fromisoformat(c["age"]["on"])
                if (on.month, on.day) != (dob.month, dob.day) or on.year - dob.year != c["age"].get("turns"):
                    errs.append("age.turns/on inconsistent with dob")
        for r in c.get("relationships") or []:
            if not (ROOT / "freaks" / r.get("slug", "?") / "character.json").exists():
                errs.append(f"relationship target {r.get('slug')} has no pack")
    dj = pack / "delivery.json"
    if not light:
        if not dj.exists():
            errs.append("missing delivery.json")
        else:
            d = json.loads(dj.read_text())
            if d.get("version") != "freaktown.delivery.v1":
                errs.append("delivery.version must be freaktown.delivery.v1")
            beats = d.get("beats") or []
            if len(beats) != 11:
                (errs if human else warns).append(f"{len(beats)} beats (pack standard is 11)")
            for b in beats:
                if b.get("type") not in BEAT_TYPES:
                    errs.append(f"{b.get('id')}: bad type {b.get('type')}")
                for k in ("id", "text", "performance", "speech", "pause_after_ms"):
                    if k not in b:
                        errs.append(f"{b.get('id')}: missing {k}")
            if beats and beats[-1].get("type") != "closer":
                errs.append("last beat must be closer")
            if beats and len(beats[-1].get("text", "").split()) >= 8:
                errs.append("closer must be under 8 words")
            md = d.get("metadata") or {}
            wc = sum(len(b.get("text", "").split()) for b in beats)
            if md.get("beat_count") != len(beats):
                errs.append("metadata.beat_count mismatch")
            if md.get("word_count") != wc:
                errs.append(f"metadata.word_count {md.get('word_count')} != {wc}")
            if md.get("punchline_count") != sum(1 for b in beats if b.get("type") == "punchline"):
                errs.append("metadata.punchline_count mismatch")
            for k in ("profile", "voice"):
                if k not in d:
                    errs.append(f"delivery.{k} missing")
            g = gates.check(beats, others_present=c.get("others_present", []), character=c)
            errs.extend("GATE: " + v for v in g["vetoes"])
            warns.extend("gate flag: " + f for f in g["flags"])
    mj = pack / "meta.json"
    if mj.exists():
        m = json.loads(mj.read_text())
        if m.get("slug") != pack.name:
            errs.append("meta.slug != directory name")
        for fn, h in (m.get("files") or {}).items():
            p = pack / fn
            if not p.exists():
                errs.append(f"meta lists missing file {fn}")
            elif h != _sha(p):
                errs.append(f"meta hash stale for {fn}")
        if dj.exists() and not light:
            d = json.loads(dj.read_text())
            if m.get("beat_count") not in (None, len(d.get("beats", []))):
                errs.append("meta.beat_count mismatch")
            if m.get("word_count") not in (None, sum(len(b.get("text", "").split()) for b in d.get("beats", []))):
                errs.append("meta.word_count mismatch")
        if human and m.get("visibility") != "private":
            errs.append("meta.visibility must be private for a real person")
    else:
        (errs if human else warns).append("missing meta.json")
    return {"pack": pack.name, "ok": not errs, "human": human, "errors": errs, "warnings": warns}


def main(argv: list[str]) -> int:
    packs = sorted((ROOT / "freaks").iterdir()) if "--all" in argv else [Path(a) for a in argv if a != "--all"]
    bad = 0
    for p in packs:
        r = validate(p if p.is_absolute() else (Path.cwd() / p))
        bad += 0 if r["ok"] else 1
        print(("OK   " if r["ok"] else "FAIL ") + r["pack"] + ("  [human]" if r.get("human") else ""))
        for e in r["errors"]:
            print("   E", e)
        for w in r["warnings"]:
            print("   w", w)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
