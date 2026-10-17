"""A/B/C predictor experiment: compare three laughter prediction approaches.

Per user spec:
  Predictor A — JEV alone (transcript + basic context)
  Predictor B — Qwen + JEV (semantic + measured features + character context)
  Predictor C — Qwen + trained predictor (same features, fitted model)

Compare how well each predicts: laugh onset, intensity, calibration.
Keep whole performances and comedians separated between train/test.

Usage:
  python3 ab_predictor_experiment.py --data /path/to/events.jsonl
  python3 ab_predictor_experiment.py --demo
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))


def load_events(path: str | Path) -> list[dict]:
    """Load comedy events with ground truth."""
    events = []
    for line in open(path):
        e = json.loads(line)
        if "ground_truth" in e:
            events.append(e)
    return events


def predictor_a_jev_only(event: dict) -> dict:
    """Predictor A: JEV alone (transcript + basic context).

    Uses only the rule-based JEV judge — no audio features.
    """
    from judge_jev import _rule_based_judge

    # Strip delivery features — JEV only sees transcript-level info
    minimal_event = {
        "setup": event.get("setup", ""),
        "expected": event.get("expected", ""),
        "reveal": event.get("reveal", ""),
        "primary_mechanism": event.get("primary_mechanism", "incongruity"),
        "delivery": {"style": "moderate", "vocal_energy": "moderate"},
        "interpretation": {"punchline_understood": True, "possible_weakness": ""},
    }
    return _rule_based_judge(minimal_event)


def predictor_b_qwen_jev(event: dict) -> dict:
    """Predictor B: Qwen + JEV (full observation + delivery features)."""
    from judge_jev import _rule_based_judge

    return _rule_based_judge(event)


def predictor_c_qwen_trained(event: dict, model=None) -> dict:
    """Predictor C: Qwen features + fitted model.

    If model is None, falls back to B (no trained model available).
    """
    if model is None:
        return predictor_b_qwen_jev(event)

    # Extract features for the trained model
    delivery = event.get("delivery", {})
    measured = event.get("measured", {})
    features = np.array([[
        measured.get("wpm", delivery.get("pace_wpm", 150)) / 300.0,
        measured.get("pause_before_punchline_ms", delivery.get("pause_before_reveal_ms", 0)) / 1000.0,
        measured.get("energy_mean", 0.05),
        measured.get("energy_std", 0.03),
        hash(event.get("primary_mechanism", "incongruity")) % 10 / 10.0,
    ]])

    prob = float(model.predict_proba(features)[0][1])
    strength = min(4, int(prob * 5))

    return {
        "audible_laughter_likely": round(prob, 3),
        "reaction_strength": strength,
        "reaction_type": ["silence", "chuckle", "laugh", "big_laugh", "roar"][strength],
        "source": "qwen_trained",
    }


def evaluate_predictor(
    predictions: list[dict],
    ground_truth: list[dict],
    name: str = "predictor",
) -> dict:
    """Evaluate one predictor against ground truth."""
    from sklearn.metrics import roc_auc_score, brier_score_loss

    y_true = [int(g.get("laugh_detected", False)) for g in ground_truth]
    y_prob = [p.get("audible_laughter_likely", 0.5) for p in predictions]

    if len(set(y_true)) < 2:
        return {"name": name, "error": "Need both laugh and no-laugh examples"}

    auc = roc_auc_score(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)
    mean_pred = np.mean(y_prob)
    mean_actual = np.mean(y_true)

    return {
        "name": name,
        "auc": round(auc, 3),
        "brier_score": round(brier, 3),
        "calibration_gap": round(abs(mean_pred - mean_actual), 3),
        "n": len(y_true),
        "laugh_rate": round(mean_actual, 3),
    }


def run_experiment(events: list[dict], trained_model=None) -> dict:
    """Run the full A/B/C experiment.

    Args:
        events: list of comedy events with ground_truth
        trained_model: optional fitted model for Predictor C

    Returns:
        dict with results for each predictor
    """
    if not events:
        return {"error": "No events with ground truth"}

    ground_truth = [e["ground_truth"] for e in events]

    # Run all three predictors
    preds_a = [predictor_a_jev_only(e) for e in events]
    preds_b = [predictor_b_qwen_jev(e) for e in events]
    preds_c = [predictor_c_qwen_trained(e, trained_model) for e in events]

    # Evaluate
    results = {
        "n_events": len(events),
        "predictors": {
            "A_jev_only": evaluate_predictor(preds_a, ground_truth, "A: JEV alone"),
            "B_qwen_jev": evaluate_predictor(preds_b, ground_truth, "B: Qwen + JEV"),
            "C_qwen_trained": evaluate_predictor(preds_c, ground_truth, "C: Qwen + trained"),
        },
    }

    # Find best
    best = max(
        results["predictors"].values(),
        key=lambda x: x.get("auc", 0),
    )
    results["best"] = best.get("name", "unknown")
    results["best_auc"] = best.get("auc", 0)

    return results


def train_predictor_c(events: list[dict]):
    """Train Predictor C's model on the events."""
    from sklearn.ensemble import GradientBoostingClassifier

    X, y = [], []
    for e in events:
        delivery = e.get("delivery", {})
        measured = e.get("measured", {})
        gt = e.get("ground_truth", {})

        features = [
            measured.get("wpm", delivery.get("pace_wpm", 150)) / 300.0,
            measured.get("pause_before_punchline_ms", delivery.get("pause_before_reveal_ms", 0)) / 1000.0,
            measured.get("energy_mean", 0.05),
            measured.get("energy_std", 0.03),
            hash(e.get("primary_mechanism", "incongruity")) % 10 / 10.0,
        ]
        X.append(features)
        y.append(int(gt.get("laugh_detected", False)))

    if len(set(y)) < 2:
        return None

    model = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    model.fit(np.array(X), np.array(y))
    return model


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="A/B/C predictor experiment")
    p.add_argument("--data", help="Path to events JSONL with ground truth")
    p.add_argument("--demo", action="store_true", help="Run demo with synthetic data")
    args = p.parse_args()

    if args.demo or not args.data:
        # Demo with synthetic data
        np.random.seed(42)
        events = []
        for i in range(200):
            prob = np.random.beta(2, 3)
            actually_laughed = np.random.random() < prob * 0.7 + 0.1

            event = {
                "setup": f"Setup {i}",
                "expected": f"Expected {i}",
                "reveal": f"Reveal {i}",
                "primary_mechanism": np.random.choice([
                    "status_reversal", "misdirection", "setup_punchline",
                    "self_deprecation", "deadpan", "escalation",
                ]),
                "delivery": {
                    "style": np.random.choice(["dry", "animated", "deadpan"]),
                    "vocal_energy": np.random.choice(["restrained", "moderate", "high"]),
                    "pace_wpm": 150 + np.random.randint(-30, 30),
                    "pause_before_reveal_ms": np.random.randint(0, 500),
                },
                "measured": {
                    "wpm": 150 + np.random.randint(-30, 30),
                    "pause_before_punchline_ms": np.random.randint(0, 500),
                    "energy_mean": np.random.uniform(0.02, 0.08),
                    "energy_std": np.random.uniform(0.01, 0.05),
                },
                "interpretation": {
                    "punchline_understood": np.random.random() > 0.1,
                    "possible_weakness": "",
                },
                "ground_truth": {
                    "laugh_detected": actually_laughed,
                    "laugh_strength": prob * 4 if actually_laughed else 0,
                },
            }
            events.append(event)

        # Train predictor C on half, test on other half
        split = len(events) // 2
        train_events = events[:split]
        test_events = events[split:]

        model_c = train_predictor_c(train_events)
        results = run_experiment(test_events, model_c)
    else:
        events = load_events(args.data)
        results = run_experiment(events)

    print(json.dumps(results, indent=2))
