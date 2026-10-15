"""Laugh predictor: P(laugh), onset timing, loudness — with live RL loop.

Trained on our corpus: casey riffs (laugh_triggered, wps, pause_before) +
louis series (AM-laugh GT per beat) + will/kam/lazer GT segments.
Features per beat: wps, pause_before, position, escalation trend,
laugh_history (TIC-TALK: history dominates — AUROC .643 baseline).
Output: P(laugh within 2s of beat end), predicted loudness bucket.
Live mode: step through beats; after each detected laugh, history updates
and the next prediction adapts (online RL, deterministic, $0).

Usage: python3 laugh_predictor.py train
       python3 laugh_predictor.py live --set louis_c05 [--audio clip.m4a]
"""
from __future__ import annotations
import argparse, json, math, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from jev_deliver import fixed_beats, gemini_label

HERE = Path(__file__).parent
REPO = HERE.parent
LAB = HERE / "voicelab"


def build_rows():
    """Feature rows from all labeled data."""
    rows = []
    # casey riffs
    db = json.loads((REPO / "theory/killtony-minutes/casey_rocket_riff_db.json").read_text())
    hist = 0
    for r in db["casey_riffs"]:
        if r.get("duration", 0) < 0.5 or r.get("words_per_sec") is None:
            continue
        rows.append({"wps": r["words_per_sec"], "pause_before": r.get("pause_before") or 0,
                     "duration": r["duration"], "riff_type": r.get("riff_type"),
                     "position_frac": min(1.0, (r.get("t0") or 0) / 3600),
                     "laugh_hist_10s": hist,
                     "laugh": 1 if r.get("laugh_triggered") else 0})
        hist = min(10, hist + (1 if r.get("laugh_triggered") else 0)) * 0.9
    # louis/will/kam/lazer GT segments
    for setname in sorted({p.name.split("_gemini")[0] for p in
                           (REPO / "theory/killtony-minutes").glob("*_gemini.gemini.json")}):
        if not any(setname.startswith(x) for x in ("louis_c", "will_", "kam_", "uncle_")):
            continue
        sp = REPO / f"theory/scribe/{setname}.json"
        gp = REPO / f"theory/killtony-minutes/{setname}_gemini.gemini.json"
        if not sp.exists() or not gp.exists():
            continue
        words = json.loads(sp.read_text())["words"]
        segs = json.loads(gp.read_text())["segments"]
        beats = fixed_beats(words)
        hist = 0
        for b in beats:
            emo = gemini_label(segs, b["t0"], b["t1"])
            in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]
                      and not w["text"].strip().startswith("[")]
            pause = (in_win[0]["start"] - max(w["end"] for w in words
                     if w["end"] <= b["t0"])) if in_win and any(w["end"] <= b["t0"] for w in words) else 0
            laugh = 1 if any("laugh_near=True" in (s.get("comedy") or {}).get("note", "")
                             for s in segs
                             if max(0, min(b["t1"], s["t1"]) - max(b["t0"], s["t0"])) > 0) else 0
            dur = (in_win[-1]["end"] - in_win[0]["start"]) if len(in_win) >= 2 else 1
            rows.append({"wps": len(in_win)/dur if dur > 0 else 0,
                         "pause_before": max(0, pause), "duration": b["t1"]-b["t0"],
                         "riff_type": "beat", "emotion": emo,
                         "position_frac": b["i"] / max(len(beats), 1),
                         "laugh_hist_10s": hist, "laugh": laugh})
            hist = min(10, hist + laugh) * 0.85
    return rows


def train(rows):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    import numpy as np
    emo_vocab = sorted({r.get("emotion", "none") for r in rows})
    type_vocab = sorted({r.get("riff_type", "beat") for r in rows})
    def feat(r):
        return ([r["wps"], r["pause_before"], r["duration"], r["position_frac"],
                 r["laugh_hist_10s"]]
                + [1 if r.get("emotion") == e else 0 for e in emo_vocab]
                + [1 if r.get("riff_type") == t else 0 for t in type_vocab])
    X = np.array([feat(r) for r in rows])
    y = np.array([r["laugh"] for r in rows])
    print(f"rows={len(rows)} positive_rate={y.mean():.2f} features={X.shape[1]}")
    clf = GradientBoostingClassifier(n_estimators=80, max_depth=3, random_state=7)
    cv = StratifiedKFold(5, shuffle=True, random_state=7)
    proba = cross_val_predict(clf, X, y, cv=cv, method="predict_proba")[:, 1]
    # AUROC manual
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(y, proba)
    # history-only baseline (TIC-TALK found history AUROC .643)
    auc_hist = roc_auc_score(y, X[:, 4])
    print(f"full model CV AUROC={auc:.3f}  history-only AUROC={auc_hist:.3f}")
    clf.fit(X, y)
    import pickle
    (LAB / "laugh_model.pkl").write_bytes(pickle.dumps({"model": clf, "emo": emo_vocab,
                                                        "types": type_vocab}))
    # feature importance
    imp = sorted(zip(["wps","pause","dur","pos","hist"]+emo_vocab+type_vocab,
                     clf.feature_importances_), key=lambda x: -x[1])[:8]
    print("top features:", [(f, round(i, 3)) for f, i in imp])
    return auc


def live(setname: str, audio: str | None):
    """Live RL demo: step beats, predict, then reveal actual (AM/audio) and update."""
    import pickle
    m = pickle.loads((LAB / "laugh_model.pkl").read_bytes())
    words = json.loads((REPO / f"theory/scribe/{setname}.json").read_text())["words"]
    gp = REPO / f"theory/killtony-minutes/{setname}_gemini.gemini.json"
    segs = json.loads(gp.read_text())["segments"] if gp.exists() else []
    beats = fixed_beats(words)
    import numpy as np
    hist = 0.0
    preds = []
    print(f"LIVE prediction over {setname} ({len(beats)} beats):")
    for b in beats:
        emo = gemini_label(segs, b["t0"], b["t1"]) if segs else "neutral"
        in_win = [w for w in words if b["t0"] <= w["start"] < b["t1"]
                  and not w["text"].strip().startswith("[")]
        dur = (in_win[-1]["end"] - in_win[0]["start"]) if len(in_win) >= 2 else 1
        wps = len(in_win)/dur if dur > 0 else 0
        vec = [wps, 0.5, b["t1"]-b["t0"], b["i"]/max(len(beats),1), hist]
        vec += [1 if emo == e else 0 for e in m["emo"]]
        vec += [1 if "beat" == t else 0 for t in m["types"]]
        x = np.array([vec])
        p = float(m["model"].predict_proba(x)[0, 1])
        # reveal actual (GT) and update history — the RL step
        actual = 0
        if segs:
            actual = 1 if any("laugh_near=True" in (s.get("comedy") or {}).get("note","")
                              for s in segs
                              if max(0, min(b["t1"], s["t1"])-max(b["t0"], s["t0"])) > 0) else 0
        err = p - actual
        hist = min(10, hist + actual) * 0.85  # history feature updates live
        preds.append({"seg": f"s{b['i']}", "p_laugh": round(p, 2),
                      "actual": actual, "calibration_err": round(err, 2),
                      "predicted_loudness": "roar" if p > 0.7 else ("light" if p > 0.4 else "none")})
        print(f"  s{b['i']}: P={p:.2f} -> actual={actual} err={err:+.2f} "
              f"loudness={preds[-1]['predicted_loudness']}")
    acc = sum(1 for r in preds if (r["p_laugh"] > 0.5) == r["actual"]) / max(len(preds),1)
    print(f"\nclassification acc={acc:.2f} (threshold .5)")
    (LAB / f"laughlive_{setname}.json").write_text(json.dumps(
        {"set": setname, "preds": preds, "acc": round(acc, 3)}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train")
    lv = sub.add_parser("live")
    lv.add_argument("--set", required=True)
    args = ap.parse_args()
    if args.cmd == "train":
        rows = build_rows()
        train(rows)
    elif args.cmd == "live":
        live(args.set, None)
