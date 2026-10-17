"""Predictive Processing Engine: audience as active inference agent.

Based on:
  - Friston's Free Energy Principle
  - IDyOM music expectancy model (inverted-U surprisal → liking)
  - Surfing uncertainty with screams (Royal Society 2023)
  - A Complexity Science Account of Humor (PMC9955919)

Core model:
  Audience maintains a GENERATIVE MODEL of what's coming.
  At each beat, they predict: "what type of material, what delivery, what topic?"
  The joke arrives → prediction error → free energy → laughter (if resolvable)

  L(funny) = f(incongruity × resolvability × precision)
  
  Where:
  - Incongruity: how much the joke violates predictions (V0 - V1)
  - Resolvability: can the audience resolve the incongruity?
  - Precision: how confident are they in their predictions? (crowd state)

  Inverted-U: too predictable = boring, too surprising = confusing,
  sweet spot = funny.

Usage:
  from predictive_engine import PredictiveAudience
  audience = PredictiveAudience(character="louis")
  for beat in beats:
      result = audience.process(beat)
      # result.prediction, result.surprisal, result.free_energy, result.p_laugh
"""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudiencePrediction:
    """What the audience predicts before a beat."""
    expected_type: str  # what they think is coming
    expected_topic: str
    confidence: float  # how sure they are
    precision: float  # precision weighting (high = confident)


@dataclass
class BeatResult:
    """Result of processing one beat."""
    prediction: AudiencePrediction
    actual_type: str
    surprisal: float  # -log P(actual | predicted)
    incongruity: float  # semantic distance
    resolvability: float  # can they resolve it?
    free_energy: float  # prediction error × precision
    p_laugh: float
    explanation: str
    updated_audience: dict  # audience state after this beat


class PredictiveAudience:
    """Audience as an active inference agent.

    Maintains a generative model of the comedian's material.
    Updates beliefs after each beat.
    Laugh = resolvable prediction error.
    """

    def __init__(
        self,
        character: str = "default",
        initial_heat: float = 0.0,
    ):
        self.character = character

        # Generative model parameters
        self.material_prior = {
            "setup_punchline": 0.4,
            "self_deprecation": 0.2,
            "escalation": 0.15,
            "callback": 0.1,
            "misdirection": 0.1,
            "other": 0.05,
        }
        self.topic_prior = {}
        self.delivery_prior = {"pace": 2.7, "energy": 0.02}

        # Belief state (updates after each beat)
        self.beliefs = {
            "heat": initial_heat,
            "momentum": 0,
            "valence": 0.0,
            "surprise_history": [],
            "free_energy_history": [],
            "n_beats": 0,
            "expected_next": "setup_punchline",
        }

    def process(self, beat: dict) -> BeatResult:
        """Process one beat through the predictive processing pipeline."""
        self.beliefs["n_beats"] += 1

        # 1. PREDICT: what does the audience expect?
        prediction = self._predict()

        # 2. OBSERVE: what actually happened?
        actual_type = beat.get("mechanism", "setup_punchline")
        actual_topic = beat.get("topic", "")

        # 3. COMPUTE SURPRISAL: -log P(actual | predicted)
        surprisal = self._surprisal(prediction, actual_type)

        # 4. COMPUTE INCONGRUITY: semantic distance
        incongruity = self._incongruity(prediction, actual_type, beat)

        # 5. COMPUTE RESOLVABILITY: can they resolve it?
        resolvability = self._resolvability(beat)

        # 6. COMPUTE FREE ENERGY: prediction error × precision
        # (from PMC9955919: V0 - V1, scaled by precision)
        free_energy = surprisal * incongruity * prediction.precision

        # 7. INVERTED-U: too little = boring, too much = confusing
        # (from IDyOM music model: liking follows inverted-U with surprisal)
        p_laugh = self._inverted_u(free_energy, resolvability)

        # 8. UPDATE BELIEFS: Bayesian updating
        self._update_beliefs(actual_type, surprisal, free_energy, p_laugh)

        explanation = self._explain(prediction, actual_type, surprisal, free_energy, p_laugh)

        return BeatResult(
            prediction=prediction,
            actual_type=actual_type,
            surprisal=round(surprisal, 3),
            incongruity=round(incongruity, 3),
            resolvability=round(resolvability, 3),
            free_energy=round(free_energy, 3),
            p_laugh=round(p_laugh, 3),
            explanation=explanation,
            updated_audience=dict(self.beliefs),
        )

    def _predict(self) -> AudiencePrediction:
        """Generate audience prediction based on current beliefs."""
        # Predict next beat type from material prior + recent history
        recent = self.beliefs["surprise_history"][-5:]
        if recent and np.mean(recent) > 1.5:
            # Audience expects more surprise (they're engaged)
            expected = "misdirection"
            confidence = 0.4
        else:
            # Audience expects continuation of pattern
            expected = self.beliefs["expected_next"]
            confidence = 0.6

        # Precision: how confident? (high when crowd is hot)
        precision = 0.3 + self.beliefs["heat"] * 0.5

        return AudiencePrediction(
            expected_type=expected,
            expected_topic="",
            confidence=confidence,
            precision=precision,
        )

    def _surprisal(self, prediction: AudiencePrediction, actual: str) -> float:
        """Surprisal = -log P(actual | predicted).

        High when actual differs from prediction.
        """
        # Probability of actual given prediction
        if actual == prediction.expected_type:
            p = prediction.confidence
        elif actual in self.material_prior:
            p = self.material_prior[actual] * 0.5
        else:
            p = 0.1

        p = max(p, 0.01)  # floor
        return -math.log2(p)

    def _incongruity(self, prediction: AudiencePrediction, actual: str, beat: dict) -> float:
        """Incongruity: semantic distance between expected and actual.

        From PMC9955919: V0 - V1 (resolvable incongruity).
        """
        # Mechanism distance matrix (simplified)
        distances = {
            ("setup_punchline", "misdirection"): 0.7,
            ("setup_punchline", "self_deprecation"): 0.4,
            ("setup_punchline", "callback"): 0.3,
            ("misdirection", "setup_punchline"): 0.7,
            ("misdirection", "callback"): 0.5,
            ("self_deprecation", "setup_punchline"): 0.4,
            ("callback", "setup_punchline"): 0.3,
            ("escalation", "setup_punchline"): 0.3,
        }

        key = (prediction.expected_type, actual)
        if key in distances:
            return distances[key]
        elif prediction.expected_type == actual:
            return 0.1  # same = low incongruity
        else:
            return 0.5  # default moderate

    def _resolvability(self, beat: dict) -> float:
        """Can the audience resolve the incongruity?

        From PMC9955919: faster resolution = funnier.
        """
        beat_type = beat.get("beat_type", "setup")

        # Beat type affects resolvability
        resolvability = {
            "punchline": 0.85,  # punchlines resolve clearly
            "tag": 0.65,
            "setup": 0.35,
            "opener": 0.25,
            "closer": 0.75,
        }

        base = resolvability.get(beat_type, 0.5)

        # Shorter text = faster resolution
        text = beat.get("text", "")
        if len(text.split()) < 8:
            base += 0.1

        return min(1.0, base)

    def _inverted_u(self, free_energy: float, resolvability: float) -> float:
        """Inverted-U mapping: optimal prediction error → max laughter.

        From IDyOM: liking follows inverted-U with surprisal.
        Too low = boring. Too high = confusing. Sweet spot = funny.
        """
        # Scale free_energy to 0-1 range
        fe_normalized = min(1.0, free_energy / 5.0)

        # Inverted-U: peak at 0.5, width controlled by resolvability
        center = 0.5
        width = 0.3 + resolvability * 0.3  # resolvable = wider sweet spot

        u = math.exp(-((fe_normalized - center) ** 2) / (2 * width ** 2))

        # Scale by resolvability (must be resolvable to laugh)
        p = u * resolvability

        # Crowd state modulation (warm crowd = easier)
        heat = self.beliefs["heat"]
        p *= (1.0 + heat * 0.3)

        return min(1.0, p)

    def _update_beliefs(self, actual: str, surprisal: float, free_energy: float, p_laugh: float):
        """Bayesian belief updating after observing a beat."""
        # Update material prior (Dirichlet-like)
        for mech in self.material_prior:
            if mech == actual:
                self.material_prior[mech] += 0.05
            else:
                self.material_prior[mech] *= 0.995

        # Normalize
        total = sum(self.material_prior.values())
        for mech in self.material_prior:
            self.material_prior[mech] /= total

        # Update expected_next
        self.beliefs["expected_next"] = actual

        # Update surprise history
        self.beliefs["surprise_history"].append(surprisal)
        if len(self.beliefs["surprise_history"]) > 20:
            self.beliefs["surprise_history"] = self.beliefs["surprise_history"][-20:]

        # Update free energy history
        self.beliefs["free_energy_history"].append(free_energy)
        if len(self.beliefs["free_energy_history"]) > 20:
            self.beliefs["free_energy_history"] = self.beliefs["free_energy_history"][-20:]

        # Update crowd state
        if p_laugh > 0.5:
            self.beliefs["heat"] = min(1.0, self.beliefs["heat"] + p_laugh * 0.1)
            self.beliefs["momentum"] += 1
            self.beliefs["valence"] = min(1.0, self.beliefs["valence"] + 0.05)
        else:
            self.beliefs["heat"] *= 0.97
            self.beliefs["momentum"] = max(0, self.beliefs["momentum"] - 1)

    def _explain(self, prediction, actual, surprisal, free_energy, p_laugh) -> str:
        """Human-readable explanation."""
        parts = []

        if prediction.expected_type != actual:
            parts.append(f"expected {prediction.expected_type}, got {actual}")

        if surprisal > 2.0:
            parts.append(f"high surprisal ({surprisal:.1f})")

        if free_energy > 2.0:
            parts.append(f"high free energy ({free_energy:.1f})")

        if p_laugh > 0.6:
            parts.append("sweet spot hit")
        elif p_laugh < 0.3:
            parts.append("too predictable or too confusing")

        if not parts:
            parts.append("moderate response")

        return "; ".join(parts)


# Need numpy for mean
import numpy as np


def analyze_set(beats: list[dict], character: str = "default") -> list[dict]:
    """Analyze a full set through the predictive processing engine."""
    audience = PredictiveAudience(character=character)
    results = []

    for beat in beats:
        result = audience.process(beat)
        results.append({
            "beat_index": beat.get("index", 0),
            "beat_type": beat.get("beat_type", ""),
            "mechanism": beat.get("mechanism", ""),
            "p_laugh": result.p_laugh,
            "surprisal": result.surprisal,
            "free_energy": result.free_energy,
            "expected": result.prediction.expected_type,
            "heat": result.updated_audience["heat"],
            "explanation": result.explanation,
        })

    return results


if __name__ == "__main__":
    # Demo: analyze a set with predictive processing
    beats = [
        {"index": 0, "text": "You know what I love about Monopoly?", "beat_type": "opener", "mechanism": "setup_punchline"},
        {"index": 1, "text": "The little houses.", "beat_type": "tag", "mechanism": "deadpan"},
        {"index": 2, "text": "They are so tiny.", "beat_type": "tag", "mechanism": "deadpan"},
        {"index": 3, "text": "Like, why are they so small?", "beat_type": "punchline", "mechanism": "misdirection"},
        {"index": 4, "text": "You are supposed to be building an empire.", "beat_type": "setup", "mechanism": "setup_punchline"},
        {"index": 5, "text": "And they give you these little green houses.", "beat_type": "setup", "mechanism": "setup_punchline"},
        {"index": 6, "text": "That look like they belong in a dollhouse.", "beat_type": "punchline", "mechanism": "misdirection"},
        {"index": 7, "text": "I played Monopoly with my kids.", "beat_type": "setup", "mechanism": "self_deprecation"},
        {"index": 8, "text": "My daughter, she is nine, she beat me.", "beat_type": "punchline", "mechanism": "self_deprecation"},
        {"index": 9, "text": "And I am not even mad.", "beat_type": "punchline", "mechanism": "misdirection"},
    ]

    print("Predictive Processing Analysis")
    print("=" * 80)
    results = analyze_set(beats, character="louis")

    for r in results:
        bar = "█" * int(r["p_laugh"] * 15)
        heat_bar = "▓" * int(r["heat"] * 15)
        print(f"\nBeat {r['beat_index']}: [{r['beat_type']:10s}] {r['mechanism']:20s}")
        print(f"  Expected: {r['expected']:20s} → Got: {r['mechanism']}")
        print(f"  Surprisal: {r['surprisal']:.2f}  Free Energy: {r['free_energy']:.2f}")
        print(f"  P(laugh): {r['p_laugh']:.3f} {bar}")
        print(f"  Heat: {r['heat']:.3f} {heat_bar}")
        print(f"  {r['explanation']}")
