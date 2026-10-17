"""Calibrate laughter predictions: map JEV confidence → actual human laugh rates.

Per user spec:
  "If Jev says strong_laugh with 0.9 confidence, that does NOT mean
   90% of humans will laugh hard. You need observed reactions to
   establish that mapping."

This module fits a small model on (JEV prediction, features) → observed laugh.
It's the bridge between JEV's opinions and reality.

Usage:
  from calibrate_laughter import Calibrator
  cal = Calibrator()
  cal.fit(predictions, ground_truth)  # train on observed reactions
  calibrated = cal.calibrate(prediction, audience_profile)
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
from typing import Any
import numpy as np

MODEL_PATH = Path(__file__).parent / "voicelab" / "laughter_calibrator.pkl"


class Calibrator:
    """Learn the mapping from JEV predictions to actual laugh rates."""

    def __init__(self):
        self.model = None
        self.feature_names = [
            "jev_prob", "jev_strength", "mech_encoded",
            "pace_wpm", "pause_ms", "energy_encoded",
        ]

    def fit(self, predictions: list[dict], ground_truth: list[dict]):
        """Fit calibrator on observed reactions.

        predictions: JEV outputs (audible_laughter_likely, reaction_strength, ...)
        ground_truth: actual laugh events (laugh_detected, laugh_strength, ...)
        """
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

        X_prob = []
        y_laugh = []
        y_strength = []

        for pred, truth in zip(predictions, ground_truth):
            # Features: JEV's opinion + event characteristics
            features = [
                pred.get("audible_laughter_likely", 0.5),
                pred.get("reaction_strength", 0) / 4.0,
                hash(pred.get("reaction_type", "silence")) % 10 / 10.0,
                pred.get("pace_wpm", 150) / 300.0,
                pred.get("pause_before_reveal_ms", 0) / 1000.0,
                hash(pred.get("vocal_energy", "moderate")) % 5 / 5.0,
            ]
            X_prob.append(features)

            # Ground truth
            laugh = truth.get("laugh_detected", False)
            y_laugh.append(int(laugh))
            y_strength.append(truth.get("laugh_strength", 0.0))

        X = np.array(X_prob)
        y = np.array(y_laugh)

        # Classifier: did they laugh?
        self.model = GradientBoostingClassifier(
            n_estimators=50, max_depth=3, random_state=42
        )
        self.model.fit(X, y)

        # Store strength model too
        self.strength_model = GradientBoostingRegressor(
            n_estimators=50, max_depth=3, random_state=42
        )
        self.strength_model.fit(X, np.array(y_strength))

        return self

    def calibrate(self, prediction: dict) -> dict:
        """Calibrate a single JEV prediction.

        Returns calibrated probability + strength estimate.
        """
        if self.model is None:
            # No calibrator fitted — return JEV's raw opinion with warning
            return {
                **prediction,
                "calibrated_probability": prediction.get("audible_laughter_likely", 0.5),
                "calibrated_strength": prediction.get("reaction_strength", 0),
                "calibration_status": "uncalibrated",
                "warning": "No calibrator fitted — using raw JEV opinion",
            }

        features = np.array([[
            prediction.get("audible_laughter_likely", 0.5),
            prediction.get("reaction_strength", 0) / 4.0,
            hash(prediction.get("reaction_type", "silence")) % 10 / 10.0,
            prediction.get("pace_wpm", 150) / 300.0,
            prediction.get("pause_before_reveal_ms", 0) / 1000.0,
            hash(prediction.get("vocal_energy", "moderate")) % 5 / 5.0,
        ]])

        prob = float(self.model.predict_proba(features)[0][1])
        strength = float(self.strength_model.predict(features)[0])

        return {
            **prediction,
            "calibrated_probability": round(prob, 3),
            "calibrated_strength": round(strength, 2),
            "calibration_status": "fitted",
        }

    def calibrate_batch(self, predictions: list[dict]) -> list[dict]:
        return [self.calibrate(p) for p in predictions]

    def save(self, path: str | Path = MODEL_PATH):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str | Path = MODEL_PATH) -> "Calibrator":
        path = Path(path)
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        return cls()


def evaluate_calibration(
    predictions: list[dict],
    ground_truth: list[dict],
) -> dict:
    """Evaluate how well JEV predictions match reality.

    Returns metrics: AUC, calibration error, agreement rate.
    """
    from sklearn.metrics import roc_auc_score, brier_score_loss

    y_true = [int(g.get("laugh_detected", False)) for g in ground_truth]
    y_prob = [p.get("audible_laughter_likely", 0.5) for p in predictions]

    if len(set(y_true)) < 2:
        return {"error": "Need both laugh and no-laugh examples"}

    auc = roc_auc_score(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)

    # Calibration: mean predicted prob vs actual rate
    mean_pred = np.mean(y_prob)
    mean_actual = np.mean(y_true)

    return {
        "auc": round(auc, 3),
        "brier_score": round(brier, 3),
        "mean_predicted_prob": round(mean_pred, 3),
        "mean_actual_rate": round(mean_actual, 3),
        "calibration_gap": round(abs(mean_pred - mean_actual), 3),
        "n": len(y_true),
    }


if __name__ == "__main__":
    # Demo with synthetic data
    np.random.seed(42)
    n = 100

    predictions = []
    ground_truth = []
    for i in range(n):
        prob = np.random.beta(2, 3)
        pred = {
            "audible_laughter_likely": prob,
            "reaction_strength": min(4, int(prob * 5)),
            "reaction_type": "laugh" if prob > 0.5 else "chuckle",
            "pace_wpm": 150 + np.random.randint(-30, 30),
            "pause_before_reveal_ms": np.random.randint(0, 500),
            "vocal_energy": np.random.choice(["restrained", "moderate", "high"]),
        }
        # Ground truth: laugh with probability related to pred but noisy
        actually_laughed = np.random.random() < prob * 0.7 + 0.1
        predictions.append(pred)
        ground_truth.append({
            "laugh_detected": actually_laughed,
            "laugh_strength": prob * 4 if actually_laughed else 0,
        })

    # Evaluate
    metrics = evaluate_calibration(predictions, ground_truth)
    print("Calibration metrics:", json.dumps(metrics, indent=2))

    # Fit calibrator
    cal = Calibrator().fit(predictions, ground_truth)

    # Test calibration
    test_pred = predictions[0]
    calibrated = cal.calibrate(test_pred)
    print(f"\nRaw JEV: {test_pred['audible_laughter_likely']}")
    print(f"Calibrated: {calibrated['calibrated_probability']}")
    print(f"Status: {calibrated['calibration_status']}")
