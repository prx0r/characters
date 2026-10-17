"""Parallel track: shorts harvest for big UK names (old/rare clips included).

Skips videos titled "Apollo" (scrapeable TV material, not the target).
Captions-first; stores url + comedian tags. Resumable per name.

Usage: python3 big_names_harvest.py
"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uk_shorts_discovery import yt_search_shorts, s3, slugify, R2_BUCKET  # noqa: E402
import yt_captions  # noqa: E402

HERE = Path(__file__).parent
STATE = HERE / "index" / "big_names_state.json"

BIG_NAMES = [
    "Jimmy Carr", "Sean Lock", "Greg Davies", "Peter Kay", "Michael McIntyre",
    "John Bishop", "Sarah Millican", "Jason Manford", "Russell Howard",
    "Jack Whitehall", "Lee Evans", "Billy Connolly", "Frankie Boyle",
    "Kevin Bridges", "Dylan Moran", "Tommy Tiernan", "Dara O Briain",
    "Ed Byrne", "Alan Carr", "Micky Flanagan", "Rhod Gilbert", "Rob Beckett",
    "Romesh Ranganathan", "Sara Pascoe", "Katherine Ryan", "Aisling Bea",
    "Mo Gilligan", "Judi Love", "Guz Khan", "Stewart Lee", "Simon Amstell",
    "Josie Long", "Tony Law", "Tim Key", "Nina Conti", "Eddie Izzard",
    "Bill Bailey", "Adam Hills", "Ross Noble", "Alexei Sayle", "Ben Elton",
    "Victoria Wood", "Dawn French", "Jennifer Saunders", "Graham Norton",
    "Ardal O'Hanlon", "Jason Byrne", "David O'Doherty", "Lee Mack", "Tim Vine",
    "Milton Jones", "Gary Delaney", "Stewart Francis", "Marcus Brigstocke",
    "Mark Watson", "Ed Gamble", "James Acaster", "Nish Kumar", "Ivo Graham",
    "Josh Widdicombe", "Jon Richardson", "Seann Walsh", "Chris Ramsey",
    "Tom Allen", "Joe Lycett", "Maisie Adam", "Rosie Jones", "Fern Brady",
    "Iain Stirling", "Larry Dean", "Daniel Sloss", "Russell Brand",
    "Noel Fielding", "Rob Brydon", "Lee Nelson", "Simon Brodkin",
    "Seán Burke", "Kiri Pritchard-McLean", "Ellie Taylor", "Neil Delamere",
    "Des Bishop", "Andrew Maxwell", "Jason Byrne",
    # round 2 additions
    "Ricky Gervais", "Rowan Atkinson", "John Cleese", "Eric Idle",
    "Spike Milligan", "Dave Allen", "Tommy Cooper", "Les Dawson",
    "Ken Dodd", "Frank Skinner", "David Baddiel", "Vic Reeves",
    "Bob Mortimer", "Richard Herring", "Jethro", "Jim Davidson",
    "Roy Chubby Brown", "Catherine Tate", "Miranda Hart", "David Walliams",
    "Matt Lucas", "Paul Chowdhry", "Darren Harriott", "Desiree Burch",
    "Sindhu Vee", "Ahir Shah", "Sukh Ojla", "Rosie Holt", "Michael Odewale",
    "Fatiha El-Ghorri", "Josh Pugh", "Rhys James", "Fin Taylor",
    "Jack Skipper", "Dan Tiernan", "Ania Magliano", "Sikisa", "Helen Bauer",
    "Janine Harouni", "Laura Lexx", "Adam Rowe", "Dan Nightingale",
    "Paul Smith", "Russell Hicks", "Nabil Abdulrashid", "Axel Blake",
    "Kane Brown", "Tom Stade", "Deirdre O'Kane", "Maeve Higgins",
    "Eleanor Tiernan", "David McSavage", "Karl Spain", "Joanne McNally",
    "Emma Doran", "Colin Murphy", "Mario Rosenstock", "Janey Godley",
    "Craig Hill", "Susie McCabe", "Gary Little", "Raymond Mearns",
    "Fred MacAulay", "Elaine C. Smith", "Christopher Macarthur-Boyd",
    "Elis James", "Steve Williams", "Tom Houghton", "Micky P Kerr",
    "Jamali Maddix", "Stephen K Amos",
    "Omid Djalili", "Shappi Khorsandi", "Andi Osho", "Gina Yashere",
    "Doc Brown", "Ben Bailey Smith",
]


def harvest(name: str) -> int:
    cslug = slugify(name)
    seen, n = set(), 0
    results = yt_search_shorts(f"{name} stand up", 15) + \
        yt_search_shorts(f"{name}", 8)
    for r in results:
        vid = r.get("id")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        dur = r.get("duration")
        if dur is not None and dur > 185:
            continue
        title_l = (r.get("title") or "").lower()
        if "apollo" in title_l or "24/7" in title_l:
            continue
        key = f"comedians/{cslug}/clips/{cslug}-{vid.lower()}.json"
        try:
            s3.head_object(Bucket=R2_BUCKET, Key=key)
            n += 1
            continue
        except Exception:
            pass
        with tempfile.TemporaryDirectory() as td:
            try:
                cap = yt_captions.fetch_captions(vid, td)
            except Exception:
                cap = None
        if not cap:
            continue
        data = {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                "title": r["title"], "comedian": name,
                "channel": r.get("channel") or "", "views": r.get("views") or 0,
                "duration_s": dur, "source_group": "big-names-shorts",
                "transcript": cap["transcript"], "words": cap["words"],
                "transcript_method": cap["method"]}
        s3.put_object(Bucket=R2_BUCKET, Key=key,
                      Body=json.dumps(data).encode(), ContentType="application/json")
        n += 1
        time.sleep(0.8)
    return n


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    names = list(dict.fromkeys(BIG_NAMES))
    for i, name in enumerate(names):
        if name in state:
            continue
        t0 = time.time()
        try:
            n = harvest(name)
        except Exception as e:
            state[name] = {"status": "error", "error": str(e)[:120]}
            STATE.write_text(json.dumps(state, indent=0, ensure_ascii=False))
            continue
        state[name] = {"status": "done", "clips": n,
                       "secs": round(time.time() - t0)}
        STATE.write_text(json.dumps(state, indent=0, ensure_ascii=False))
        print(f"[{i+1}/{len(names)}] {name}: {n} clips in {state[name]['secs']}s",
              flush=True)
        time.sleep(1)
    state["__complete__"] = True
    STATE.write_text(json.dumps(state, indent=0, ensure_ascii=False))
    total = sum(v.get("clips", 0) for v in state.values() if isinstance(v, dict))
    print(f"DONE: {total} big-name shorts across {len(names)} names", flush=True)


if __name__ == "__main__":
    main()
