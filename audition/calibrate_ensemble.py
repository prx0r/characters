"""Calibrate ensemble on real human laugh events from AM specials.

Loads 5702 events with ground truth, runs ensemble on each,
trains meta-model to combine predictions.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from laugh_ensemble import LaughEnsemble


def load_events(path: str = "audition/voicelab/comedy_events.jsonl") -> list[dict]:
    """Load events with ground truth."""
    events = []
    for line in open(path):
        e = json.loads(line)
        if "ground_truth" in e and "measured" in e:
            events.append(e)
    return events


def features_from_event(event: dict) -> dict:
    """Convert event to ensemble features."""
    m = event.get("measured", {})
    return {
        "pause_after": m.get("pause_mean_ms", 0) / 1000.0,
        "pos": m.get("pos", 0.5),
        "energy_std": 0.02,  # placeholder — not in events
        "energy_mean": 0.03,
        "n_pauses": 2,
        "pause_total": 0.5,
        "heat": 0.0,
        "momentum": 0,
    }


def context_from_event(event: dict) -> dict:
    """Convert event to ensemble context."""
    return {
        "mechanism": "setup_punchline",  # default — not in events
        "beat_type": "punchline",
        "text": event.get("transcript", ""),
    }


def main():
    print("Loading human laugh events...")
    events = load_events()
    print(f"  {len(events)} events, {sum(e['ground_truth']['laugh_detected'] for e in events)} laughs")

    print("\nRunning ensemble on all events...")
    ens = LaughEnsemble()

    feature_list = []
    labels = []
    all_outputs = []

    for i, e in enumerate(events):
        feats = features_from_event(e)
        ctx = context_from_event(e)
        result = ens.predict(feats, ctx)

        feature_list.append(feats)
        labels.append(int(e["ground_truth"]["laugh_detected"]))
        all_outputs.append(result.model_outputs)

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(events)}")

    print(f"\nCalibrating meta-model on {len(labels)} human laughs...")
    weights = ens.calibrate(feature_list, labels)

    # Evaluate ensemble vs individual models
    from sklearn.metrics import roc_auc_score

    model_order = ["word_level", "delivery", "free_energy", "crowd_state", "lexical"]
    y = np.array(labels)

    print(f"\nIndividual model AUCs:")
    for m in model_order:
        probs = [o.get(m, 0.5) for o in all_outputs]
        auc = roc_auc_score(y, probs)
        print(f"  {m:15s} {auc:.3f}")

    # Ensemble AUC
    ens_probs = []
    for o in all_outputs:
        row = [o.get(m, 0.5) for m in model_order]
        if ens.meta_model:
            p = ens.meta_model.predict_proba([row])[0][1]
        else:
            p = np.mean(row)
        ens_probs.append(p)

    ens_auc = roc_auc_score(y, ens_probs)
    print(f"\nEnsemble AUC: {ens_auc:.3f}")
    print(f"Best single: {max(roc_auc_score(y, [o.get(m, 0.5) for o in all_outputs]) for m in model_order):.3f}")

    # Save calibrated ensemble
    out = Path("audition/voicelab/calibrated_ensemble.pkl")
    with open(out, "wb") as f:
        pickle.dump({
            "ensemble": ens,
            "weights": weights,
            "auc": ens_auc,
            "n_events": len(labels),
        }, f)
    print(f"\nSaved calibrated ensemble to {out}")


import pickle

if __name__ == "__main__":
    main()
