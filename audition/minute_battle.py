"""Minute battle: blind A/B of shortform comedy minutes (45-100s).

The funniest-minute-in-existence leaderboard. Pairs of minutes (YouTube
embeds with start/end or local wavs), blind vote, Elo + Wilson bounds.
Bluesky-style open ranking: transparent algorithm, auditable history.

Usage: python3 minute_battle.py            # run on :8809
       python3 minute_battle.py --seed     # load starter minutes
"""
from __future__ import annotations
import json, math, random, time
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "voicelab" / "minute_battle.json"
K = 32


def load() -> dict:
    if DATA.exists():
        return json.loads(DATA.read_text())
    return {"minutes": {}, "battles": [], "current": None}


def save(s: dict) -> None:
    DATA.write_text(json.dumps(s, indent=2))


def wilson(w: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = w / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    rad = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return round((centre - rad) / denom, 3)


def add_minute(s: dict, mid: str, title: str, source: str,
               yt_id: str = "", start: int = 0, end: int = 0,
               local_wav: str = "", performer: str = "") -> None:
    s["minutes"][mid] = {"title": title, "source": source, "yt_id": yt_id,
                         "start": start, "end": end, "local_wav": local_wav,
                         "performer": performer, "elo": 1500.0,
                         "wins": 0, "battles": 0}


def next_pair(s: dict) -> dict:
    mids = list(s["minutes"])
    random.shuffle(mids)
    pairs = [(a, b) for i, a in enumerate(mids) for b in mids[i+1:]]
    seen = {(x["a"], x["b"]) for x in s["battles"]}
    fresh = [p for p in pairs if p not in seen and p[::-1] not in seen]
    pool = fresh or pairs[:50]
    a, b = random.choice(pool)
    return {"a": a, "b": b}


def vote(s: dict, winner: str) -> None:
    cur = s["current"]
    loser = cur["b"] if winner == cur["a"] else cur["a"]
    ma, mb = s["minutes"][cur["a"]], s["minutes"][cur["b"]]
    ea = 1 / (1 + 10 ** ((mb["elo"] - ma["elo"]) / 400))
    sa = 1.0 if winner == cur["a"] else 0.0
    ma["elo"] += K * (sa - ea)
    mb["elo"] += K * ((1 - sa) - (1 - ea))
    ma["battles"] += 1; mb["battles"] += 1
    if winner == cur["a"]:
        ma["wins"] += 1
    else:
        mb["wins"] += 1
    s["battles"].append({"a": cur["a"], "b": cur["b"], "winner": winner,
                         "at": time.strftime("%H:%M:%S")})
    s["current"] = next_pair(s)
    save(s)
    print(f"{s['minutes'][winner]['title']} wins. next: {s['current']}")


def seed() -> None:
    s = load()
    starter = [
        ("ari_kt704", "Ari Matti — kt704 passport", "local",
         "", 0, 0, str(HERE / "voicelab/perf_sets/kt704_passport.wav"), "ari_matti"),
        ("casey_1", "Casey Rocket — set 1", "local",
         "", 0, 0, str(HERE / "voicelab/perf_sets/casey_rocket_1.wav"), "casey_rocket"),
        ("pickles_1", "Sir Winston Pickles — set 1", "local",
         "", 0, 0, str(HERE / "voicelab/perf_sets/sir_winston_pickles_1.wav"), "sir_winston_pickles"),
        ("louis_gen", "Louis-style (roadrage gen)", "local",
         "", 0, 0, str(HERE / "voicelab/perf_sets/louis_roadrage.wav"), "louis_ck"),
        ("dracula_map", "Dracula x Pickles engine", "local",
         "", 0, 0, str(HERE / "voicelab/swaps/dracula__pickles_set_mapping.wav"), "dracula"),
        ("joker_casey", "Joker x Casey derived", "local",
         "", 0, 0, str(HERE / "voicelab/swaps/joker__casey_derived.wav"), "joker"),
        ("kam_sponge", "Kam set x SpongeBob", "local",
         "", 0, 0, str(HERE / "voicelab/swaps/kam_set__spongebob.wav"), "kam"),
        ("ari_galactic", "Ari kt704 x Galactic", "local",
         "", 0, 0, str(HERE / "voicelab/swaps/ari_kt704__galactic.wav"), "ari_matti"),
    ]
    for args in starter:
        add_minute(s, *args)
    # youtube entries (real clips, 45-100s windows — trim via start/end)
    add_minute(s, "yt_norm_moth", "Norm Macdonald — Moth Joke (real)", "youtube",
               yt_id="nwmuByY6SZ4", start=30, end=120, performer="norm_macdonald")
    add_minute(s, "yt_louis_bit", "Louis C.K. — road rage (real)", "youtube",
               yt_id="BlM1FP-hcq8", start=0, end=90, performer="louis_ck")
    s["current"] = next_pair(s)
    save(s)
    print(f"seeded {len(s['minutes'])} minutes; first pair: {s['current']}")


if __name__ == "__main__":
    import sys
    if "--seed" in sys.argv:
        seed()
    else:
        from flask import Flask, jsonify, request, send_file
        app = Flask(__name__)

        @app.get("/")
        def home():
            s = load()
            cur = s["current"] or next_pair(s)
            m = s["minutes"]
            a, b = m[cur["a"]], m[cur["b"]]
            def player(side, mid, mm):
                if mm.get("local_wav") and Path(mm["local_wav"]).exists():
                    return f'<audio controls src="/wav/{mid}"></audio>'
                if mm.get("yt_id"):
                    yt = mm["yt_id"]
                    return (f'<iframe width="480" height="270" src="https://www.youtube.com/embed/{yt}'
                            f'?start={mm.get("start",0)}&end={mm.get("end",90)}" '
                            f'frameborder="0" allowfullscreen></iframe>')
                return "<em>no media</em>"
            return f"""<!doctype html><meta charset=utf-8><title>MINUTE BATTLE</title>
<style>body{{font-family:system-ui;background:#111;color:#eee;text-align:center}}
.grid{{display:flex;gap:24px;justify-content:center;margin:20px}}
.card{{background:#1c1c22;padding:16px;border-radius:12px;width:500px}}
button{{font-size:22px;padding:14px 40px;margin:12px;border-radius:10px;
border:none;cursor:pointer;background:#3ddc84}}button.b{{background:#ff6b6b}}
a{{color:#8cf}}</style>
<h1>MINUTE BATTLE <small>— which is funnier?</small></h1>
<h3><a href="/board">leaderboard</a></h3>
<div class=grid>
<div class=card><h2>A</h2><h3>{a['title']}</h3>{player('a', cur['a'], a)}</div>
<div class=card><h2>B</h2><h3>{b['title']}</h3>{player('b', cur['b'], b)}</div>
</div>
<button onclick="vote('a')">A is funnier</button>
<button class=b onclick="vote('b')">B is funnier</button>
<script>async function vote(w){{await fetch('/vote',{{method:'POST',
headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{winner:w}})}});
location.reload()}}</script>"""

        @app.post("/vote")
        def do_vote():
            s = load()
            vote(s, request.json["winner"])
            return jsonify({"ok": True})

        @app.get("/board")
        def board():
            s = load()
            rows = sorted(s["minutes"].items(), key=lambda kv: -kv[1]["elo"])
            html = ["<!doctype html><meta charset=utf-8><title>BOARD</title>"
                    "<style>body{font-family:system-ui;background:#111;color:#eee}"
                    "table{margin:auto}td,th{padding:8px 16px;border-bottom:#333}"
                    "a{color:#8cf}</style><h1>FUNNIEST MINUTE LEADERBOARD</h1>"
                    "<h3><a href='/'>back to battle</a></h3><table><tr><th>#</th>"
                    "<th>minute</th><th>elo</th><th>w-l</th><th>wilson LB</th></tr>"]
            for i, (mid, m) in enumerate(rows, 1):
                wl = wilson(m["wins"], m["battles"])
                html.append(f"<tr><td>{i}</td><td>{m['title']}</td>"
                            f"<td>{m['elo']:.0f}</td><td>{m['wins']}-{m['battles']-m['wins']}</td>"
                            f"<td>{wl}</td></tr>")
            html.append("</table>")
            return "".join(html)

        @app.get("/wav/<mid>")
        def wav(mid):
            m = load()["minutes"].get(mid)
            if m and m.get("local_wav"):
                return send_file(m["local_wav"])
            return "not found", 404

        @app.get("/data")
        def data():
            return jsonify(load())

        app.run(host="0.0.0.0", port=8809, debug=False)
