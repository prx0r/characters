"""Ensemble laugh predictor: many models, calibrated on human laughs.

Architecture:
  5+ competing models → each outputs P(laugh) → meta-learner combines
  → calibrated against actual human laugh events.

Models in ensemble:
  1. Word-level (StandUp4AI: pause_after, position, timing)
  2. Delivery (energy variation, pace)
  3. Free energy (incongruity → prediction error)
  4. Crowd state (heat/momentum physics)
  5. Lexical (word-level text features from SMILE)

Calibration:
  - Each model outputs raw P(laugh)
  - Meta-learner (logistic regression) learns weights
  - Calibrated on human laugh events (AM specials + KT)

Usage:
  from laugh_ensemble import LaughEnsemble
  ens = LaughEnsemble()
  result = ens.predict(beat_features)
  # result.p_laugh, result.model_outputs, result.calibrated
"""
from __future__ import annotations
import json, pickle
from pathlib import Path
from dataclasses import dataclass, field
import numpy as np

HERE = Path(__file__).parent


@dataclass
class EnsembleResult:
    """Calibrated ensemble prediction."""
    p_laugh_raw: float
    p_laugh_calibrated: float
    model_outputs: dict
    uncertainty: float
    top_model: str
    explanation: str


class LaughEnsemble:
    """Ensemble of multiple laugh models with learned calibration."""

    def __init__(self):
        self.models = {}
        self.meta_model = None
        self.is_calibrated = False
        self._load_models()

    def _load_models(self):
        """Load all available sub-models."""
        # Word-level model
        wl_path = HERE / "voicelab" / "word_level_model.pkl"
        if wl_path.exists():
            with open(wl_path, "rb") as f:
                self.models["word_level"] = pickle.load(f)

        # Delivery model
        am_path = HERE / "voicelab" / "am_delivery_model.pkl"
        if am_path.exists():
            with open(am_path, "rb") as f:
                self.models["delivery"] = pickle.load(f)

        # Prosody200 model
        prosody_path = HERE / "voicelab" / "prosody200_clean_model.pkl"
        if prosody_path.exists():
            with open(prosody_path, "rb") as f:
                self.models["prosody"] = pickle.load(f)

        print(f"Loaded {len(self.models)} models: {list(self.models.keys())}")

    def predict(self, features: dict, context: dict | None = None) -> EnsembleResult:
        """Get ensemble prediction from all models."""
        outputs = {}

        # Model 1: Word-level (pause_after, position, timing)
        if "word_level" in self.models:
            wl_feats = np.array([[
                features.get("pause_after", 0),
                features.get("pos", 0.5),
                features.get("word_len", 5) / 20.0,
                float(features.get("is_sentence_end", False)),
                float(features.get("is_sentence_start", False)),
                float(features.get("is_capitalized", False)),
                float(features.get("has_punct", False)),
                features.get("pause_after", 0),
                features.get("next_word_len", 5) / 20.0,
                features.get("pause_before", 0),
                features.get("prev_word_len", 5) / 20.0,
            ]])
            try:
                p = float(self.models["word_level"]["model"].predict_proba(wl_feats)[0][1])
                outputs["word_level"] = p
            except Exception:
                pass

        # Model 2: Delivery (energy, pace)
        if "delivery" in self.models:
            e_std = features.get("energy_std", 0.02)
            e_mean = features.get("energy_mean", 0.03)
            e_max = features.get("energy_max", 0.05)
            e_min = features.get("energy_min", 0.01)
            n_pauses = features.get("n_pauses", 2)
            pause_total = features.get("pause_total", 0.5)
            pos = features.get("pos", 0.5)

            delivery_feats = np.array([[
                pos, e_mean, e_std, e_max, e_min, n_pauses, pause_total
            ]])
            try:
                p = float(self.models["delivery"]["model"].predict_proba(delivery_feats)[0][1])
                outputs["delivery"] = p
            except Exception:
                pass

        # Model 3: Free energy (incongruity)
        context = context or {}
        mech = context.get("mechanism", "setup_punchline")
        beat_type = context.get("beat_type", "punchline")

        mech_incongruity = {
            "misdirection": 0.8, "status_reversal": 0.75,
            "escalation": 0.7, "setup_punchline": 0.6,
            "callback": 0.5, "self_deprecation": 0.4,
            "deadpan": 0.3, "displacement": 0.5,
        }
        beat_resolvability = {
            "punchline": 0.85, "tag": 0.65,
            "setup": 0.35, "opener": 0.25, "closer": 0.75,
        }

        incongruity = mech_incongruity.get(mech, 0.5)
        resolvability = beat_resolvability.get(beat_type, 0.5)
        fe = incongruity * resolvability

        # Inverted-U
        import math
        u = math.exp(-((fe - 0.4) ** 2) / (2 * 0.25 ** 2))
        outputs["free_energy"] = u * resolvability

        # Model 4: Crowd state
        heat = features.get("heat", 0.0)
        momentum = features.get("momentum", 0)
        crowd_p = 0.3 + heat * 0.4 + min(0.2, momentum * 0.03)
        outputs["crowd_state"] = min(1.0, crowd_p)

        # Model 5: Lexical (text features)
        text = context.get("text", "")
        if text:
            words = text.split()
            has_question = "?" in text
            has_exclamation = "!" in text
            has_negation = any(w in text.lower() for w in ["not", "no", "never", "don't"])
            is_short = len(words) < 8
            lex_score = 0.3
            if is_short and (has_exclamation or has_negation):
                lex_score += 0.3
            if has_exclamation:
                lex_score += 0.1
            if has_negation:
                lex_score += 0.1
            outputs["lexical"] = min(1.0, lex_score)

        # Combine (equal weights if not calibrated)
        if self.meta_model is not None and self.is_calibrated:
            return self._meta_predict(outputs)
        else:
            # Equal weight average
            p_raw = np.mean(list(outputs.values())) if outputs else 0.5
            uncertainty = float(np.std(list(outputs.values()))) if len(outputs) > 1 else 0.3
            top = max(outputs, key=outputs.get) if outputs else "none"

            return EnsembleResult(
                p_laugh_raw=round(p_raw, 3),
                p_laugh_calibrated=round(p_raw, 3),
                model_outputs=outputs,
                uncertainty=round(uncertainty, 3),
                top_model=top,
                explanation=f"equal-weight ensemble, top={top}",
            )

    def _meta_predict(self, outputs: dict) -> EnsembleResult:
        """Use trained meta-model for combination."""
        model_order = ["word_level", "delivery", "free_energy", "crowd_state", "lexical"]
        X = np.array([[outputs.get(m, 0.5) for m in model_order]])
        p = float(self.meta_model.predict_proba(X)[0][1])
        uncertainty = float(np.std(list(outputs.values())))

        return EnsembleResult(
            p_laugh_raw=round(np.mean(list(outputs.values())), 3),
            p_laugh_calibrated=round(p, 3),
            model_outputs=outputs,
            uncertainty=round(uncertainty, 3),
            top_model=max(outputs, key=outputs.get),
            explanation="meta-learned combination",
        )

    def calibrate(self, feature_list: list[dict], labels: list[int]):
        """Train meta-model on human laugh events."""
        from sklearn.linear_model import LogisticRegression

        model_order = ["word_level", "delivery", "free_energy", "crowd_state", "lexical"]

        X = []
        y = []
        for feats, label in zip(feature_list, labels):
            result = self.predict(feats)
            row = [result.model_outputs.get(m, 0.5) for m in model_order]
            X.append(row)
            y.append(label)

        X = np.array(X)
        y = np.array(y)

        if len(set(y)) < 2:
            print("Need both laugh and no-laugh for calibration")
            return

        lr = LogisticRegression(fit_intercept=True)
        lr.fit(X, y)

        self.meta_model = lr
        self.is_calibrated = True

        # Evaluate
        from sklearn.metrics import roc_auc_score
        y_prob = lr.predict_proba(X)[:, 1]
        auc = roc_auc_score(y, y_prob)

        # Weights
        coefs = np.abs(lr.coef_[0])
        total = coefs.sum()
        weights = {m: round(float(c / total), 3) for m, c in zip(model_order, coefs)}

        print(f"Meta-model trained: AUC={auc:.3f}")
        print(f"Learned weights: {weights}")

        return weights


if __name__ == "__main__":
    ens = LaughEnsemble()

    # Test with a Louis CK beat
    features = {
        "pause_after": 0.3,
        "pos": 0.6,
        "energy_std": 0.025,
        "energy_mean": 0.03,
        "heat": 0.5,
        "momentum": 3,
    }
    context = {
        "mechanism": "misdirection",
        "beat_type": "punchline",
        "text": "And I am not even mad.",
    }

    result = ens.predict(features, context)
    print(f"\nEnsemble prediction:")
    print(f"  P(laugh) raw: {result.p_laugh_raw:.3f}")
    print(f"  P(laugh) calibrated: {result.p_laugh_calibrated:.3f}")
    print(f"  Uncertainty: {result.uncertainty:.3f}")
    print(f"  Top model: {result.top_model}")
    print(f"  Model outputs:")
    for m, p in result.model_outputs.items():
        bar = "█" * int(p * 15)
        print(f"    {m:15s} {p:.3f} {bar}")
