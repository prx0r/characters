"""Crowd State Machine: the audience as a physics engine.

Core insight (user, 2026-10-17):
  "Killed" is a STATE the crowd gets into. Once there, easier to stay.
  Like Guitar Hero: combo multiplier. Laughs reduce resistance,
  wrong comments increase it.

Physics model:
  - heat: 0-1, how warm the crowd is (the "killed" state)
  - resistance: 0-1, how hard to get the next laugh (inverse of heat)
  - momentum: laugh streak multiplier
  - valence: -1 to 1, positive/negative mood
  - arousal: 0-1, energy level

State transitions:
  laugh:     heat += intensity * (1 - heat) * 0.3
             momentum += 1
             valence += 0.1
  no_laugh:  heat *= 0.92
             momentum = max(0, momentum - 1)
  bomb:      heat *= 0.7  (big drop)
             valence -= 0.3
             momentum = 0
  kill:      heat += 0.2  (crossing threshold = "killed")
             momentum *= 1.5

Usage:
  from crowd_state import CrowdStateMachine
  crowd = CrowdStateMachine()
  crowd.beat(laughed=True, intensity=0.8)
  print(crowd.state)  # heat=0.24, momentum=1, valence=0.1
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict


@dataclass
class CrowdState:
    """Current crowd state."""
    heat: float = 0.0          # 0-1, how warm (killed = >0.7)
    resistance: float = 1.0    # 0-1, inverse of heat
    momentum: int = 0          # laugh streak
    valence: float = 0.0       # -1 to 1, mood
    arousal: float = 0.3       # 0-1, energy
    total_laughs: int = 0
    total_beats: int = 0
    kill_count: int = 0        # times crossed into "killed"
    bomb_count: int = 0        # times heat dropped sharply

    @property
    def is_killed(self) -> bool:
        return self.heat > 0.7

    @property
    def is_warm(self) -> bool:
        return self.heat > 0.4

    @property
    def multiplier(self) -> float:
        """Guitar Hero-style multiplier. Hot crowd = bigger laughs."""
        return 1.0 + self.momentum * 0.1 + self.heat * 0.5


class CrowdStateMachine:
    """Physics engine for audience state.

    The crowd has:
    - Heat (warmth): persists, decays slowly, boosted by laughs
    - Resistance: inverse of heat, how hard to get next laugh
    - Momentum: consecutive laughs, builds multiplier
    - Valence: mood, positive from laughs, negative from bombs
    - Arousal: energy level, affects laugh type
    """

    def __init__(
        self,
        initial_heat: float = 0.0,
        decay_rate: float = 0.92,
        bomb_threshold: float = 0.15,  # heat drop > this = bomb
        kill_threshold: float = 0.7,
    ):
        self.state = CrowdState(heat=initial_heat)
        self.decay_rate = decay_rate
        self.bomb_threshold = bomb_threshold
        self.kill_threshold = kill_threshold
        self.history = []

    def beat(
        self,
        laughed: bool = False,
        intensity: float = 0.0,
        laugh_type: str = "laugh",
        mechanism: str = "",
    ) -> CrowdState:
        """Process one beat. Returns updated state."""
        prev_heat = self.state.heat
        self.state.total_beats += 1

        if laughed:
            self._on_laugh(intensity, laugh_type)
        else:
            self._on_no_laugh()

        # Check for bomb (big heat drop)
        heat_drop = prev_heat - self.state.heat
        if heat_drop > self.bomb_threshold:
            self.state.bomb_count += 1
            self.state.valence -= 0.3
            self.state.momentum = 0

        # Check for kill (crossing threshold)
        if not self.state.is_killed and self.state.heat > self.kill_threshold:
            self.state.kill_count += 1

        # Update resistance (inverse of heat)
        self.state.resistance = 1.0 - self.state.heat

        # Record history
        self.history.append({
            "beat": self.state.total_beats,
            "heat": round(self.state.heat, 3),
            "momentum": self.state.momentum,
            "valence": round(self.state.valence, 3),
            "laughed": laughed,
            "intensity": intensity,
        })

        return self.state

    def _on_laugh(self, intensity: float, laugh_type: str):
        """Laugh reduces resistance, increases heat."""
        s = self.state

        # Heat boost: bigger laugh = more heat, but diminishing returns
        heat_boost = intensity * (1.0 - s.heat) * 0.3
        s.heat = min(1.0, s.heat + heat_boost)

        # Momentum builds
        s.momentum += 1

        # Valence positive
        s.valence = min(1.0, s.valence + 0.1 * intensity)

        # Arousal increases
        type_arousal = {
            "chuckle": 0.2, "laugh": 0.4,
            "big_laugh": 0.7, "roar": 1.0,
        }
        s.arousal = min(1.0, s.arousal + type_arousal.get(laugh_type, 0.4) * 0.2)

        s.total_laughs += 1

    def _on_no_laugh(self):
        """No laugh: heat decays, momentum drops."""
        s = self.state

        # Heat decays (slow — crowd warmth persists)
        s.heat *= self.decay_rate

        # Momentum drops
        s.momentum = max(0, s.momentum - 1)

        # Valence slightly negative (missed beat)
        s.valence = max(-1.0, s.valence - 0.05)

        # Arousal decays
        s.arousal *= 0.95

    def get_laugh_type(self) -> str:
        """What laugh type does the current state predict?"""
        s = self.state
        if s.heat < 0.2:
            return "chuckle"
        elif s.heat < 0.5:
            return "laugh"
        elif s.heat < 0.7:
            return "big_laugh"
        else:
            return "roar"  # killed!

    def predict_next(self, p_base: float) -> float:
        """Predict laugh probability given current state.

        Hot crowd + momentum = easier laugh.
        """
        s = self.state

        # Base probability modified by state
        p = p_base * (1.0 + s.heat * 0.5 + s.momentum * 0.05)

        # Resistance makes it harder
        p *= (1.0 - s.resistance * 0.3)

        return max(0.0, min(1.0, p))

    def summary(self) -> dict:
        """Human-readable state summary."""
        s = self.state
        status = "KILLED" if s.is_killed else ("warm" if s.is_warm else "cold")
        return {
            "status": status,
            "heat": round(s.heat, 3),
            "momentum": s.momentum,
            "multiplier": round(s.multiplier, 2),
            "valence": round(s.valence, 3),
            "arousal": round(s.arousal, 3),
            "total_laughs": s.total_laughs,
            "kill_count": s.kill_count,
            "bomb_count": s.bomb_count,
        }


def simulate_set(outcomes: list[dict]) -> list[dict]:
    """Simulate a full set with crowd state tracking.

    outcomes: list of {laughed: bool, intensity: float, laugh_type: str}
    """
    crowd = CrowdStateMachine()
    timeline = []

    for i, outcome in enumerate(outcomes):
        state = crowd.beat(
            laughed=outcome.get("laughed", False),
            intensity=outcome.get("intensity", 0),
            laugh_type=outcome.get("laugh_type", "laugh"),
        )
        timeline.append({
            "beat": i,
            **crowd.summary(),
        })

    return timeline


if __name__ == "__main__":
    # Simulate a comedian who starts cold, kills, then bombs
    print("Simulating a set: cold → kill → bomb → recovery")
    print("=" * 70)

    outcomes = [
        # Cold start
        {"laughed": False, "intensity": 0},
        {"laughed": True, "intensity": 0.3, "laugh_type": "chuckle"},
        {"laughed": False, "intensity": 0},
        # Warming up
        {"laughed": True, "intensity": 0.5, "laugh_type": "laugh"},
        {"laughed": True, "intensity": 0.6, "laugh_type": "laugh"},
        # Kill streak
        {"laughed": True, "intensity": 0.8, "laugh_type": "big_laugh"},
        {"laughed": True, "intensity": 0.9, "laugh_type": "roar"},
        {"laughed": True, "intensity": 0.8, "laugh_type": "big_laugh"},
        # Bomb
        {"laughed": False, "intensity": 0},
        {"laughed": False, "intensity": 0},
        # Recovery
        {"laughed": True, "intensity": 0.5, "laugh_type": "laugh"},
        {"laughed": True, "intensity": 0.6, "laugh_type": "laugh"},
    ]

    crowd = CrowdStateMachine()
    for i, o in enumerate(outcomes):
        state = crowd.beat(**o)
        status = "KILLED" if state.is_killed else ("warm" if state.is_warm else "cold")
        bar = "█" * int(state.heat * 20)
        print(f"  beat {i:2d}: {status:6s} heat={state.heat:.2f} {bar:20s} "
              f"mom={state.momentum} val={state.valence:+.2f} "
              f"{'LAUGH' if o.get('laughed') else 'miss'}")

    print(f"\nFinal: {crowd.summary()}")
    print(f"Predicted next laugh type: {crowd.get_laugh_type()}")
    print(f"Predicted P(laugh) if base=0.5: {crowd.predict_next(0.5):.3f}")
