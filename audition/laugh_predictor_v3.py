"""Laugh predictor v3: ALL sets, audio-derived labels (no GT leak).

Labels: AM 4-12Hz detector events on each clip's AUDIO (independent of
features). Features: word-timing wps/pause/duration/position/history +
cheap text features. No GT-derived emotions (that was the v2 leak).
Trains on every set with scribe+audio: ari/casey/pickles/louis/will/kam/lazer.

Usage: python3 laugh_predictor_v3.py train
"""
from __future__ import annotations
import array, json, subprocess, tempfile, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"
EVDIR = LAB / "am_events"

CLIPS = {}
import jev_loop
CLIPS.update(jev_loop.CLIPS)


def detect_laughs(path, sr=16000):
    with tempfile.NamedTemporaryFile(suffix=".pcm") as tmp:
        subprocess.run(["ffmpeg","-y","-v","error","-i",str(path),"-ac","1",
                        "-ar",str(sr),"-f","s16le",tmp.name],check=True,capture_output=True)
        raw = Path(tmp.name).read_bytes()
    a = array.array("h"); a.frombytes(raw)
    x = np.asarray(a, dtype="float64")/32768
    hop = int(0.01*sr)
    env = np.array([np.sqrt(np.mean(x[i:i+hop]**2)) for i in range(0,len(x)-hop,hop)]) if len(x)>hop else np.array([])
    ev, mod = [], []
    for i in range(0, max(0,len(env)-40), 20):
        e = env[i:i+40]
        if e.mean() < 0.01: continue
        sp = np.abs(np.fft.rfft((e-e.mean())*np.hanning(len(e))))
        freqs = np.fft.rfftfreq(len(e), 0.01)
        band = (freqs>=4)&(freqs<=12)
        m = sp[band].sum()/(sp.sum()+1e-9)
        if m > 0.5: ev.append((round(i*0.01,2), round((i+40)*0.01,2), round(float(m),2)))
    merged = []
    for s,e,m in ev:
        if merged and s - merged[-1][1] < 0.3:
            merged[-1] = (merged[-1][0], e, max(merged[-1][2], m))
        else:
            merged.append((s,e,m))
    return merged


def laugh_events(setname: str, clip: str) -> list:
    EVDIR.mkdir(parents=True, exist_ok=True)
    cache = EVDIR / f"{setname}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    ev = detect_laughs(clip)
    cache.write_text(json.dumps(ev))
    return ev


def build_rows():
    from jev_deliver import fixed_beats
    rows = []
    # casey event-level riffs (real per-event labels)
    db = json.loads((REPO / "theory/killtony-minutes/casey_rocket_riff_db.json").read_text())
    hist = 0.0
    for r in db["casey_riffs"]:
        if r.get("duration", 0) < 0.5 or r.get("words_per_sec") is None:
            continue
        rows.append({"set": "casey_riffs", "wps": r["words_per_sec"],
                     "pause_before": min(r.get("pause_before") or 0, 15),
                     "dur": min(r["duration"], 60),
                     "pos": min(1.0, (r.get("t0") or 0)/600),
                     "hist": hist, "laugh": 1 if r.get("laugh_triggered") else 0})
        hist = min(10, hist + (1 if r.get("laugh_triggered") else 0)) * 0.88
    # all sets with scribe + audio: label from AM events
    for setname, clip in sorted(CLIPS.items()):
        sp = REPO / f"theory/scribe/{setname}.json"
        if not sp.exists() or not Path(clip).exists():
            continue
        try:
            words = json.loads(sp.read_text())["words"]
            events = laugh_events(setname, clip)
        except Exception as e:
            print(f"  {setname}: skip ({str(e)[:60]})"); continue
        beats = fixed_beats(words)
        hist = 0.0
        for b in beats:
            # label: an AM-laugh onset in [b.t1-0.5, b.t1+2.0] (mid-approach allowed)
            laugh = 1 if any(b["t1"]-0.5 <= s <= b["t1"]+2.0 for s,_,_ in events) else 0
            in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]
                      and not w["text"].strip().startswith("[")]
            dur = (in_win[-1]["end"]-in_win[0]["start"]) if len(in_win) >= 2 else 1
            pause = 0.0
            if in_win:
                prev = [w for w in words if w["end"] <= b["t0"] and not w["text"].strip().startswith("[")]
                if prev:
                    pause = min(in_win[0]["start"] - prev[-1]["end"], 15)
            rows.append({"set": setname, "wps": len(in_win)/dur if dur > 0 else 0,
                         "pause_before": max(0, pause), "dur": b["t1"]-b["t0"],
                         "pos": b["i"]/max(len(beats),1), "hist": hist, "laugh": laugh})
            hist = min(10, hist + laugh) * 0.88
        print(f"  {setname}: {len(beats)} beats, {len(events)} AM events")
    return rows


def train(rows):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.metrics import roc_auc_score
    import pickle
    X = np.array([[r["wps"], r["pause_before"], r["dur"], r["pos"], r["hist"]] for r in rows])
    y = np.array([r["laugh"] for r in rows])
    sets = np.array([r["set"] for r in rows])
    print(f"\nn={len(rows)} positive_rate={y.mean():.2f}")
    clf = GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=7)
    proba = cross_val_predict(clf, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=7),
                              method="predict_proba")[:, 1]
    auc = roc_auc_score(y, proba)
    auc_h = roc_auc_score(y, X[:, 4])
    print(f"LOO-CV AUROC={auc:.3f} (history-only {auc_h:.3f})")
    # per-comedian AUC (where both classes exist)
    for s in sorted(set(sets)):
        m = sets == s
        if m.sum() >= 8 and y[m].std() > 0:
            a = roc_auc_score(y[m], proba[m])
            print(f"  {s:28} n={m.sum():3} auc={a:.2f} pos={y[m].mean():.2f}")
    clf.fit(X, y)
    imp = sorted(zip(["wps","pause","dur","pos","hist"], clf.feature_importances_),
                 key=lambda x: -x[1])
    print("importance:", [(f, round(i,3)) for f, i in imp])
    pickle.dump({"model": clf, "auc": auc}, open(LAB/"laugh_model_v3.pkl","wb"))
    print("-> voicelab/laugh_model_v3.pkl")
    return auc


if __name__ == "__main__":
    rows = build_rows()
    train(rows)
