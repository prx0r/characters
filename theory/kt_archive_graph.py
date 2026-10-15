"""Full KT comedian graph from killtonyarchive.com (2046 sets,536 eps).

Per set: timestamp, comedian, Regular/Bucket/Special, topics, crowd
reaction (silence/light/moderate/big laughs/roaring), score, golden flag.
Aggregated per comedian: sets, avg score, reaction dist, topic counts.
Usage: python3 kt_archive_graph.py --episodes 40 [--start 787]
"""
from __future__ import annotations
import argparse, json, re, time, urllib.request
from collections import defaultdict, Counter
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "kt_archive_graph.json"
REACTIONS = ("roaring", "big laughs", "moderate", "light", "silence")
TOPICS = {"observational","shock humor","sex","race","relationships","self deprecation",
          "politics","family","absurdist","storytelling","drugs","disability","regional",
          "pop culture","work","religion","gender roles","food","other","military","animals",
          "music","celebrity","meta","technology","mental health","lgbtq","dating","age"}

def fetch(ep: int) -> list[dict]:
    url = f"https://killtonyarchive.com/episodes/{ep}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode(errors="replace")
    text = re.sub(r"<[^>]+>", "\n", html)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sets = []
    for i, l in enumerate(lines):
        if l in REACTIONS:
            # walk back: topics..., bucket-type, name, timestamp
            j = i - 1
            score = None
            if j >= 0 and lines[j].isdigit():
                score = int(lines[j]); j -= 1
            topics = []
            while j >= 0 and lines[j].lower() in TOPICS:
                topics.insert(0, lines[j].lower()); j -= 1
            bucket = lines[j] if j >= 0 and lines[j] in ("Regular","Bucket","Special") else ""
            if bucket: j -= 1
            name = lines[j] if j >= 0 else "?"
            ts = lines[j-1] if j >= 0 and re.match(r"\d{2}:\d{2}:\d{2}", lines[j-1] or "") else ""
            golden = any("GOLDEN TICKET" in x for x in lines[max(0,i-4):i+1])
            sets.append({"episode": ep, "time": ts, "comedian": name,
                         "type": bucket, "topics": topics, "reaction": l,
                         "score": score, "golden": golden})
    return sets

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--start", type=int, default=787)
    args = ap.parse_args()
    all_sets = []
    for ep in range(args.start, args.start - args.episodes, -1):
        try:
            sets = fetch(ep)
            all_sets.extend(sets)
            print(f"ep{ep}: {len(sets)} sets | {sum(1 for s in sets if s['golden'])} golden", flush=True)
        except Exception as e:
            print(f"ep{ep}: FAIL {str(e)[:60]}", flush=True)
        time.sleep(1.0)
    # aggregate per comedian
    per = defaultdict(lambda: {"sets": [], "reactions": Counter(), "topics": Counter(),
                               "scores": [], "golden": 0})
    for s in all_sets:
        c = per[s["comedian"]]
        c["sets"].append({k: s[k] for k in ("episode","time","type","reaction","score","golden")})
        c["reactions"][s["reaction"]] += 1
        c["topics"].update(s["topics"])
        if s["score"]: c["scores"].append(s["score"])
        c["golden"] += 1 if s["golden"] else 0
    graph = {}
    for name, c in per.items():
        graph[name] = {"n_sets": len(c["sets"]), "golden": c["golden"],
                       "avg_score": round(sum(c["scores"])/len(c["scores"]),1) if c["scores"] else None,
                       "reaction_dist": dict(c["reactions"].most_common()),
                       "top_topics": [t for t,_ in c["topics"].most_common(5)],
                       "sets": c["sets"]}
    doc = {"source": "killtonyarchive.com", "episodes": args.episodes,
           "n_sets": len(all_sets), "n_comedians": len(graph),
           "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "comedians": graph}
    OUT.write_text(json.dumps(doc, indent=2))
    print(f"\nGRAPH: {len(all_sets)} sets, {len(graph)} comedians -> {OUT}")
    top = sorted(graph.items(), key=lambda kv: -kv[1]["n_sets"])[:8]
    for n, g in top:
        print(f"  {n:24} sets={g['n_sets']:2} avg={g['avg_score']} {g['reaction_dist']}")

if __name__ == "__main__":
    main()
