"""Ensemble laugh predictor: multiple competing models, calibrated output.

Three model families:
  1. Delivery model (audio features: energy, pace, pauses)
  2. Free energy model (incongruity → prediction error → laugh)
  3. Crowd state model (heat/momentum/valence physics)

Each outputs P(laugh). Ensemble combines with learned weights.
Calibrated against real laugh events.

Usage:
  from ensemble_laugh import EnsembleLaughPredictor
  pred = EnsembleLaughPredictor()
  result = pred.predict(beat_features, crowd_state, joke_context)
  # result.p_laugh, result.model_outputs, result.uncertainty
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
from dataclasses import dataclass, field
import numpy as np

HERE = Path(__file__).parent


# ============================================================
# MODEL 1: DELIVERY MODEL (audio features)
# ============================================================

class DeliveryModel:
    """Predicts laugh from audio delivery features.

    Based on our finding: energy variation is the strongest signal (AUC 0.654).
    """

    def predict(self, features: dict, crowd: dict) -> dict:
        e_std = features.get("energy_std", 0.02)
        wps = features.get("wps", 2.7)
        pause = features.get("pause_before", 0.5)
        pos = features.get("pos", 0.5)

        # Energy variation (real signal)
        energy_score = min(1.0, e_std * 20) * 0.3

        # Pace (real data: faster = more laughs)
        if wps < 1.5:
            pace_score = -0.05
        elif wps < 2.5:
            pace_score = 0.0
        elif wps < 3.5:
            pace_score = 0.03
        else:
            pace_score = 0.08

        # Position (crowd warms up)
        pos_score = pos * 0.10

        # Base
        p = 0.45 + energy_score + pace_score + pos_score
        p = max(0.0, min(1.0, p))

        return {
            "p_laugh": p,
            "confidence": 0.6,  # AUC 0.654 → moderate confidence
            "model": "delivery",
        }


# ============================================================
# MODEL 2: FREE ENERGY MODEL (predictive processing)
# ============================================================

class FreeEnergyModel:
    """Predicts laugh from incongruity → prediction error → free energy.

    Based on: A Complexity Science Account of Humor (PMC9955919)
    - Setup establishes attractor V0
    - Punchline forces transition to V1
    - Resolvable incongruity (V0 - V1) = free energy = laughter
    """

    # Mechanism → incongruity level (how much expectation is violated)
    MECH_INCONGRUITY = {
        "setup_punchline": 0.6, "misdirection": 0.8,
        "escalation": 0.7, "callback": 0.5,
        "self_deprecation": 0.4, "deadpan": 0.3,
        "status_reversal": 0.75, "displacement": 0.5,
        "anti_humor": 0.3, "sarcasm": 0.55,
    }

    # Beat type → resolvability (can audience resolve the incongruity?)
    BEAT_RESOLVABILITY = {
        "punchline": 0.8, "tag": 0.6,
        "setup": 0.3, "opener": 0.2, "closer": 0.7,
    }

    def predict(self, features: dict, crowd: dict, context: dict) -> dict:
        mech = context.get("mechanism", "setup_punchline")
        beat_type = context.get("beat_type", "punchline")

        # Incongruity (how much expectation is violated)
        incongruity = self.MECH_INCONGRUITY.get(mech, 0.5)

        # Resolvability (can audience resolve it?)
        resolvability = self.BEAT_RESOLVABILITY.get(beat_type, 0.5)

        # Audience expectation (from crowd state + prior)
        # High heat = audience has strong expectations (they're engaged)
        expectation_strength = 0.3 + crowd.get("heat", 0) * 0.4

        # Free energy = incongruity × resolvability × expectation
        # (from the paper: V0 - V1, scaled by how well it can be resolved)
        free_energy = incongruity * resolvability * expectation_strength

        # Faster resolution = funnier (we approximate with beat type)
        if beat_type == "punchline":
            resolution_speed = 1.2  # fast
        elif beat_type == "tag":
            resolution_speed = 1.0
        else:
            resolution_speed = 0.8

        p = free_energy * resolution_speed
        p = max(0.0, min(1.0, p))

        return {
            "p_laugh": p,
            "incongruity": incongruity,
            "resolvability": resolvability,
            "expectation": expectation_strength,
            "free_energy": free_energy,
            "confidence": 0.5,  # theoretical model, not data-validated
            "model": "free_energy",
        }


# ============================================================
# MODEL 3: CROWD STATE MODEL (physics)
# ============================================================

class CrowdStateModel:
    """Predicts laugh from crowd physics (heat/momentum/valence).

    Based on: audience as state machine, SIR contagion model.
    """

    def predict(self, features: dict, crowd: dict) -> dict:
        heat = crowd.get("heat", 0.0)
        momentum = crowd.get("momentum", 0)
        valence = crowd.get("valence", 0.0)
        resistance = crowd.get("resistance", 1.0)

        # Heat: warm crowd laughs more (contagion)
        heat_score = heat * 0.4

        # Momentum: streak builds multiplier
        momentum_score = min(0.2, momentum * 0.03)

        # Valence: positive mood helps
        valence_score = valence * 0.1

        # Resistance: hard to get laugh when cold
        resistance_penalty = -resistance * 0.15

        p = 0.4 + heat_score + momentum_score + valence_score + resistance_penalty
        p = max(0.0, min(1.0, p))

        return {
            "p_laugh": p,
            "heat": heat,
            "momentum": momentum,
            "confidence": 0.4,  # physics model, not data-validated
            "model": "crowd_state",
        }


# ============================================================
# ENSEMBLE
# ============================================================

@dataclass
class EnsemblePrediction:
    """Combined prediction from all models."""
    p_laugh: float
    uncertainty: float
    model_outputs: dict
    crowd_state: dict
    explanation: str


class EnsembleLaughPredictor:
    """Ensemble of 3 models with calibrated combination.

    Weights learned from validation data (or defaults if not trained).
    """

    def __init__(self, weights: dict | None = None):
        self.delivery = DeliveryModel()
        self.free_energy = FreeEnergyModel()
        self.crowd_state = CrowdStateModel()

        # Default weights (from our findings: delivery is most reliable)
        self.weights = weights or {
            "delivery": 0.5,    # AUC 0.654 — most validated
            "free_energy": 0.3, # theoretical, not validated
            "crowd_state": 0.2, # physics, not validated
        }

    def predict(
        self,
        features: dict,
        crowd: dict,
        context: dict,
    ) -> EnsemblePrediction:
        """Get ensemble prediction."""
        # Run all models
        d = self.delivery.predict(features, crowd)
        f = self.free_energy.predict(features, crowd, context)
        c = self.crowd_state.predict(features, crowd)

        # Weighted combination
        p = (
            d["p_laugh"] * self.weights["delivery"] +
            f["p_laugh"] * self.weights["free_energy"] +
            c["p_laugh"] * self.weights["crowd_state"]
        )
        p = max(0.0, min(1.0, p))

        # Uncertainty: disagreement between models
        probs = [d["p_laugh"], f["p_laugh"], c["p_laugh"]]
        uncertainty = float(np.std(probs))

        # Explanation
        explanation = self._explain(d, f, c, p)

        return EnsemblePrediction(
            p_laugh=round(p, 3),
            uncertainty=round(uncertainty, 3),
            model_outputs={"delivery": d, "free_energy": f, "crowd_state": c},
            crowd_state=crowd,
            explanation=explanation,
        )

    def _explain(self, d: dict, f: dict, c: dict, p: float) -> str:
        """Human-readable explanation of the prediction."""
        parts = []

        # Delivery contribution
        if d["p_laugh"] > 0.6:
            parts.append("strong delivery (energy variation)")
        elif d["p_laugh"] < 0.4:
            parts.append("weak delivery (monotone)")

        # Free energy contribution
        if f.get("free_energy", 0) > 0.3:
            mech = f.get("incongruity", 0)
            parts.append(f"high incongruity ({mech:.1f})")

        # Crowd contribution
        if c.get("heat", 0) > 0.5:
            parts.append(f"warm crowd (heat={c['heat']:.2f})")
        elif c.get("heat", 0) < 0.2:
            parts.append("cold crowd")

        if not parts:
            parts.append("moderate across all signals")

        return "; ".join(parts)

    def calibrate(self, predictions: list, ground_truth: list):
        """Learn weights from validation data."""
        from sklearn.linear_model import LogisticRegression

        X = []
        y = []
        for pred, truth in zip(predictions, ground_truth):
            row = [
                pred["delivery"]["p_laugh"],
                pred["free_energy"]["p_laugh"],
                pred["crowd_state"]["p_laugh"],
            ]
            X.append(row)
            y.append(int(truth))

        X = np.array(X)
        y = np.array(y)

        if len(set(y)) < 2:
            print("Need both laugh and no-laugh examples for calibration")
            return

        lr = LogisticRegression(fit_intercept=False)
        lr.fit(X, y)

        # Normalize coefficients to weights
        coefs = np.abs(lr.coef_[0])
        total = coefs.sum()
        if total > 0:
            self.weights = {
                "delivery": float(coefs[0] / total),
                "free_energy": float(coefs[1] / total),
                "crowd_state": float(coefs[2] / total),
            }
        print(f"Calibrated weights: {self.weights}")


if __name__ == "__main__":
    # Demo: same joke, different crowd states
    print("Ensemble prediction: same joke, different crowd states")
    print("=" * 70)

    pred = EnsembleLaughPredictor()

    joke_context = {"mechanism": "misdirection", "beat_type": "punchline"}
    features = {"energy_std": 0.025, "wps": 2.7, "pause_before": 1.5, "pos": 0.6}

    scenarios = [
        ("Cold room", {"heat": 0.0, "momentum": 0, "valence": 0.0, "resistance": 1.0}),
        ("Warm room", {"heat": 0.5, "momentum": 3, "valence": 0.2, "resistance": 0.5}),
        ("KILLED", {"heat": 0.8, "momentum": 6, "valence": 0.4, "resistance": 0.2}),
    ]

    for name, crowd in scenarios:
        result = pred.predict(features, crowd, joke_context)
        bar = "█" * int(result.p_laugh * 20)
        print(f"\n{name}:")
        print(f"  P(laugh) = {result.p_laugh:.3f} {bar}")
        print(f"  Uncertainty: {result.uncertainty:.3f}")
        print(f"  Explanation: {result.explanation}")
        print(f"  Models: delivery={result.model_outputs['delivery']['p_laugh']:.2f} "
              f"free_energy={result.model_outputs['free_energy']['p_laugh']:.2f} "
              f"crowd={result.model_outputs['crowd_state']['p_laugh']:.2f}")
