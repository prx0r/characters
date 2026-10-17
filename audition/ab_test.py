"""A/B Test Framework: same joke, different conditions, different landing.

Core capability: compare how the SAME joke lands under different:
  - Room states (warm vs cold)
  - Delivery choices (Louis formula vs rushed)
  - Character profiles (who's telling it)

Usage:
  from ab_test import ABTester
  tester = ABTester()
  result = tester.compare_joke(
      joke_text="And I am not even mad.",
      mechanism="misdirection",
      conditions=[
          {"label": "Cold room", "crowd": {"heat": 0.0}},
          {"label": "Warm room", "crowd": {"heat": 0.7}},
          {"label": "Louis formula", "pause": 2.1, "wps": 2.7},
          {"label": "Rushed", "pause": 0.5, "wps": 4.0},
      ]
  )
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any

from ensemble_laugh import EnsembleLaughPredictor
from crowd_state import CrowdStateMachine


@dataclass
class ABResult:
    """Result of one condition in an A/B test."""
    label: str
    p_laugh: float
    uncertainty: float
    crowd_state: dict
    delivery: dict
    explanation: str


@dataclass
class ABComparison:
    """Full A/B comparison."""
    joke_text: str
    mechanism: str
    results: list
    best: str
    worst: str
    spread: float  # best - worst
    winner_factors: dict  # what made the difference


class ABTester:
    """Compare how jokes land under different conditions."""

    def __init__(self):
        self.ensemble = EnsembleLaughPredictor()

    def compare_joke(
        self,
        joke_text: str,
        mechanism: str = "setup_punchline",
        beat_type: str = "punchline",
        conditions: list[dict] | None = None,
    ) -> ABComparison:
        """Compare the same joke under different conditions.

        conditions: list of dicts with:
          - label: condition name
          - crowd: crowd state dict (heat, momentum, etc.)
          - pause: pause before punchline (seconds)
          - wps: words per second
          - energy_std: energy variation
          - character: character profile name
        """
        if conditions is None:
            # Default: cold vs warm vs killed
            conditions = [
                {"label": "Cold room", "crowd": {"heat": 0.0, "momentum": 0, "valence": 0.0}},
                {"label": "Warm room", "crowd": {"heat": 0.5, "momentum": 3, "valence": 0.2}},
                {"label": "KILLED", "crowd": {"heat": 0.8, "momentum": 6, "valence": 0.4}},
            ]

        results = []
        for cond in conditions:
            crowd = cond.get("crowd", {"heat": 0.0, "momentum": 0, "valence": 0.0, "resistance": 1.0})
            features = {
                "energy_std": cond.get("energy_std", 0.02),
                "wps": cond.get("wps", 2.7),
                "pause_before": cond.get("pause", 1.5),
                "pos": cond.get("pos", 0.5),
            }
            context = {
                "mechanism": mechanism,
                "beat_type": beat_type,
                "text": joke_text,
            }

            pred = self.ensemble.predict(features, crowd, context)

            results.append(ABResult(
                label=cond["label"],
                p_laugh=pred.p_laugh,
                uncertainty=pred.uncertainty,
                crowd_state=crowd,
                delivery=features,
                explanation=pred.explanation,
            ))

        # Find best/worst
        best = max(results, key=lambda r: r.p_laugh)
        worst = min(results, key=lambda r: r.p_laugh)
        spread = best.p_laugh - worst.p_laugh

        # Analyze what made the difference
        factors = self._analyze_factors(results, best, worst)

        return ABComparison(
            joke_text=joke_text,
            mechanism=mechanism,
            results=results,
            best=best.label,
            worst=worst.label,
            spread=round(spread, 3),
            winner_factors=factors,
        )

    def compare_deliveries(
        self,
        joke_text: str,
        mechanism: str,
        deliveries: list[dict],
    ) -> ABComparison:
        """Compare the same joke with different delivery choices."""
        conditions = []
        for d in deliveries:
            conditions.append({
                "label": d.get("label", "delivery"),
                "crowd": d.get("crowd", {"heat": 0.5, "momentum": 3, "valence": 0.2}),
                "pause": d.get("pause", 1.5),
                "wps": d.get("wps", 2.7),
                "energy_std": d.get("energy_std", 0.02),
            })
        return self.compare_joke(joke_text, mechanism, conditions=conditions)

    def _analyze_factors(self, results: list, best, worst) -> dict:
        """Analyze what factors distinguished best from worst."""
        factors = {}

        # Crowd difference
        heat_diff = best.crowd_state.get("heat", 0) - worst.crowd_state.get("heat", 0)
        if abs(heat_diff) > 0.1:
            factors["crowd_heat"] = f"{'warmer' if heat_diff > 0 else 'colder'} by {abs(heat_diff):.2f}"

        # Delivery difference
        pause_diff = best.delivery.get("pause_before", 0) - worst.delivery.get("pause_before", 0)
        if abs(pause_diff) > 0.3:
            factors["pause"] = f"{'longer' if pause_diff > 0 else 'shorter'} by {abs(pause_diff):.1f}s"

        wps_diff = best.delivery.get("wps", 0) - worst.delivery.get("wps", 0)
        if abs(wps_diff) > 0.5:
            factors["pace"] = f"{'faster' if wps_diff > 0 else 'slower'} by {abs(wps_diff):.1f} wps"

        return factors

    def print_comparison(self, comp: ABComparison):
        """Pretty-print an A/B comparison."""
        print(f"\n{'='*70}")
        print(f"A/B TEST: \"{comp.joke_text[:60]}...\"")
        print(f"Mechanism: {comp.mechanism}")
        print(f"{'='*70}")

        for r in comp.results:
            bar = "█" * int(r.p_laugh * 20)
            print(f"\n  {r.label}:")
            print(f"    P(laugh) = {r.p_laugh:.3f} {bar}")
            print(f"    Uncertainty: {r.uncertainty:.3f}")
            print(f"    Explanation: {r.explanation}")

        print(f"\n{'─'*70}")
        print(f"WINNER: {comp.best}")
        print(f"LOSER:  {comp.worst}")
        print(f"SPREAD: {comp.spread:.3f}")
        if comp.winner_factors:
            print(f"KEY FACTORS:")
            for k, v in comp.winner_factors.items():
                print(f"  {k}: {v}")


if __name__ == "__main__":
    tester = ABTester()

    # Test 1: Same joke, different room states
    joke = "And I am not even mad. I am impressed."
    comp = tester.compare_joke(
        joke_text=joke,
        mechanism="misdirection",
        conditions=[
            {"label": "Cold room (heat=0)", "crowd": {"heat": 0.0, "momentum": 0, "valence": 0.0}},
            {"label": "Warm room (heat=0.5)", "crowd": {"heat": 0.5, "momentum": 3, "valence": 0.2}},
            {"label": "KILLED (heat=0.8)", "crowd": {"heat": 0.8, "momentum": 6, "valence": 0.4}},
        ],
    )
    tester.print_comparison(comp)

    # Test 2: Same joke, different delivery
    comp2 = tester.compare_deliveries(
        joke_text=joke,
        mechanism="misdirection",
        deliveries=[
            {"label": "Rushed (amateur)", "pause": 0.4, "wps": 4.0, "energy_std": 0.01},
            {"label": "Normal", "pause": 1.2, "wps": 2.7, "energy_std": 0.02},
            {"label": "Louis formula", "pause": 2.1, "wps": 2.7, "energy_std": 0.025},
        ],
    )
    tester.print_comparison(comp2)
