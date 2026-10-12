"""Character-graph operations — ONE of three distinct operations.

A CharacterGraph wraps identity + voice + interpretation. It knows WHO.
It never touches worlds (residents, lore, leagues) or formats (shows,
staging, scoring) — those are world_ops and formats/shows.

Any format accepts any list of CharacterGraphs: podcast(cast=[ralph, hera]),
react(reactors=[...]), surrounded(mob=[...]).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class CharacterGraph:
    """Identity + voice + interpretation for one performer."""

    def __init__(self, character_id: str):
        import generate as _gen
        self.id = character_id
        self._data = _gen.get_character(character_id)
        raw = self._data.get("raw") or {}
        self.name: str = self._data.get("name", character_id)
        self.deal: str = self._data.get("deal", "")
        self.want: str = self._data.get("want", "")
        self.blind_spots: list = list(self._data.get("blind_spots") or [])
        self.traits: list = list(self._data.get("traits") or [])
        self.misrule: str = raw.get("misinterpretation_rule", "")
        self.voice_id: str = ((self._data.get("raw") or {}).get("voice") or {}).get("voice_id", "") \
            or self._data.get("voice_id", "")
        self.first = self.name.split()[0].rstrip(",")

    def interpret(self, scenario: dict, state: dict | None = None,
                  memories: list | None = None) -> dict:
        """Actor decision: appraisal/goal/reaction from philosophy. No operators."""
        import generate as _gen
        return _gen.actor_decide(self._data, scenario, state or {}, memories or [],
                                 tilt="", explore=False)

    def say(self, text: str, tag: str) -> dict:
        """Speak one line in this voice. Returns {path, duration_ms}."""
        import formats as _f
        return _f.speak_line(self.id, text, tag)

    def brief(self) -> str:
        return (f"{self.name}: {self.deal[:140]} "
                f"Wants {self.want}; blind to {', '.join(self.blind_spots[:2])}").strip()
