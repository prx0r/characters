"""A/B/C predictor experiment on real comedy events.

Per peer review:
  "Compare semantic-plus-audio features against audio-only and simple baseline models"
  "Keep whole performances and comedians separated between training and testing"

Predictors:
  A — Audio-only baseline (measured features, no semantics)
  B — Audio + semantic features (measured + mechanism labels)
  C — Full pipeline (audio + semantic + history + character)

All evaluated with GroupKFold by special (held-out comedian/special).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

# Mechanism → numeric encoding
MECH_ENCODING = {
    "status_reversal": 1.0, "identity_contradiction": 0.9,
    "misdirection": 0.85, "setup_punchline": 0.7,
    "escalation": 0.75, "callback": 0.8,
    "self_deprecation": 0.6, "deadpan": 0.5,
    "anti_humor": 0.4, "sarcasm": 0.55,
    "absurdism": 0.45, "blue_humor": 0.7,
    "incongruity": 0.6, "benign_violation": 0.65,
    "garden_path": 0.62, "double_interpret": 0.6,
    "split_knowledge": 0.65, "expose_self_blindness": 0.55,
    "displacement": 0.5, "not_a_joke": 0.0,
}


def load_events(path: str | Path) -> list[dict]:
    """Load comedy events with ground truth."""
    events = []
    for line in open(path):
        e = json.loads(line)
        if "ground_truth" in e and "measured" in e:
            events.append(e)
    return events


def features_audio_only(event: dict) -> list[float]:
    """Predictor A: audio-only (measured features)."""
    m = event.get("measured", {})
    return [
        m.get("wps", 0) / 10.0,           # words per second
        m.get("pause_mean_ms", 0) / 1000.0,  # pause
        m.get("pos", 0),                     # position in set
        m.get("hist_rate", 0),               # laughter history
        m.get("n_words", 0) / 50.0,          # segment length
    ]


def features_audio_semantic(event: dict) -> list[float]:
    """Predictor B: audio + semantic (adds mechanism encoding)."""
    base = features_audio_only(event)
    # Add mechanism encoding (from semantic interpreter, or default)
    mech = event.get("primary_mechanism", "incongruity")
    mech_score = MECH_ENCODING.get(mech, 0.5)
    return base + [mech_score]


def features_full(event: dict) -> list[float]:
    """Predictor C: audio + semantic + history + context."""
    base = features_audio_semantic(event)
    m = event.get("measured", {})
    # Add more context features
    return base + [
        m.get("hist_rate", 0) ** 2,  # accelerating history
        m.get("pos", 0) * m.get("hist_rate", 0),  # position × history
    ]


def train_and_evaluate(events: list[dict], feature_fn, name: str, n_splits: int = 5):
    """Train with GroupKFold by special, evaluate."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

    X = np.array([feature_fn(e) for e in events])
    y = np.array([int(e["ground_truth"]["laugh_detected"]) for e in events])
    groups = np.array([e.get("special", "unknown") for e in events])

    n_groups = min(n_splits, len(set(groups)))
    gkf = GroupKFold(n_splits=n_groups)

    model = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)

    # Cross-validated predictions
    y_prob = cross_val_predict(model, X, y, cv=gkf, groups=groups, method="predict_proba")[:, 1]

    auc = roc_auc_score(y, y_prob)
    pr_auc = average_precision_score(y, y_prob)
    brier = brier_score_loss(y, y_prob)
    mean_pred = y_prob.mean()
    mean_actual = y.mean()

    return {
        "name": name,
        "auc": round(auc, 3),
        "pr_auc": round(pr_auc, 3),
        "brier": round(brier, 3),
        "calibration_gap": round(abs(mean_pred - mean_actual), 3),
        "n": len(y),
        "n_groups": n_groups,
        "laugh_rate": round(mean_actual, 3),
    }


def run_experiment(events: list[dict]) -> dict:
    """Run the full A/B/C experiment on real data."""
    if not events:
        return {"error": "No events"}

    print(f"Running A/B/C experiment on {len(events)} events from {len(set(e.get('special','?') for e in events))} specials")
    print("=" * 70)

    results_a = train_and_evaluate(events, features_audio_only, "A: Audio only")
    results_b = train_and_evaluate(events, features_audio_semantic, "B: Audio + semantic")
    results_c = train_and_evaluate(events, features_full, "C: Full pipeline")

    all_results = {
        "n_events": len(events),
        "predictors": {
            "A_audio_only": results_a,
            "B_audio_semantic": results_b,
            "C_full": results_c,
        },
    }

    # Print comparison
    print(f"\n{'Predictor':<25} {'AUROC':>6} {'PR-AUC':>6} {'Brier':>6} {'CalGap':>6}")
    print("-" * 55)
    for r in [results_a, results_b, results_c]:
        print(f"{r['name']:<25} {r['auc']:>6.3f} {r['pr_auc']:>6.3f} {r['brier']:>6.3f} {r['calibration_gap']:>6.3f}")

    # Find best
    best = max([results_a, results_b, results_c], key=lambda x: x["auc"])
    all_results["best"] = best["name"]
    all_results["best_auc"] = best["auc"]

    print(f"\nBest: {best['name']} (AUROC {best['auc']:.3f})")

    return all_results


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--data", default="audition/voicelab/comedy_events.jsonl")
    args = p.parse_args()

    events = load_events(args.data)
    results = run_experiment(events)

    # Save results
    out = Path("audition/voicelab/abc_experiment_results.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {out}")
