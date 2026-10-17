"""Reaction-based laugh models: human clicks → prediction + personalization.

Two models from one data source:
  1. Global laugh predictor: aggregate across users → what joke structures land
  2. Per-user taste model: individual clicks → what THIS user finds funny

Data source: freaktown reactions.jsonl
  {t, slug, reaction, set_time_ms}
  reaction: laugh | clap | crickets | groan

Usage:
  from reaction_models import ReactionCollector, GlobalLaughModel, UserTasteModel

  # Collect
  collector = ReactionCollector()
  collector.add_reaction(slug="my-set", reaction="laugh", set_time_ms=4200)

  # Global model
  global_model = GlobalLaughModel()
  global_model.train(collector.load_all())
  p = global_model.predict(joke_features)

  # User taste
  user = UserTasteModel(user_id="alice")
  user.update("laugh", joke_features)
  scores = user.score_candidates(candidate_features)
"""
from __future__ import annotations
import json, time
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

REACTIONS_PATH = Path("/tmp/freaktown/reactions.jsonl")
VOTES_PATH = Path("/tmp/freaktown/votes.jsonl")

# Reaction semantics
REACTION_WEIGHT = {
    "laugh": 1.0,
    "clap": 0.6,
    "groan": -0.3,
    "crickets": -0.8,
}


@dataclass
class ReactionEvent:
    """One human reaction."""
    timestamp: float
    slug: str
    reaction: str
    set_time_ms: int
    weight: float

    def __post_init__(self):
        self.weight = REACTION_WEIGHT.get(self.reaction, 0.0)


class ReactionCollector:
    """Collect and load human reactions from freaktown."""

    def __init__(self, reactions_path: str | Path = REACTIONS_PATH):
        self.path = Path(reactions_path)

    def add_reaction(self, slug: str, reaction: str, set_time_ms: int):
        """Log a reaction (called by freaktown API)."""
        entry = {
            "t": time.time(),
            "slug": slug,
            "reaction": reaction,
            "set_time_ms": set_time_ms,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def load_all(self) -> list[ReactionEvent]:
        """Load all reactions."""
        events = []
        if not self.path.exists():
            return events
        for line in open(self.path):
            try:
                d = json.loads(line)
                events.append(ReactionEvent(
                    timestamp=d["t"],
                    slug=d["slug"],
                    reaction=d["reaction"],
                    set_time_ms=d.get("set_time_ms", 0),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return events

    def load_by_slug(self, slug: str) -> list[ReactionEvent]:
        """Load reactions for one set."""
        return [e for e in self.load_all() if e.slug == slug]

    def stats(self) -> dict:
        """Summary stats."""
        events = self.load_all()
        by_reaction = defaultdict(int)
        by_slug = defaultdict(int)
        for e in events:
            by_reaction[e.reaction] += 1
            by_slug[e.slug] += 1
        return {
            "total": len(events),
            "by_reaction": dict(by_reaction),
            "n_sets": len(by_slug),
        }


class GlobalLaughModel:
    """Aggregate across all users → what joke structures land.

    Trained on: (joke_features, reaction_weight) pairs.
    Predicts: expected reaction weight for new jokes.
    """

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.n_samples = 0

    def train(self, events: list[ReactionEvent], joke_features_map: dict | None = None):
        """Train on reaction events.

        joke_features_map: {slug: features_dict} — if None, uses timestamp position.
        """
        from sklearn.ensemble import GradientBoostingRegressor

        X, y = [], []
        for e in events:
            if joke_features_map and e.slug in joke_features_map:
                feats = joke_features_map[e.slug]
                X.append([
                    feats.get("word_count", 0) / 100.0,
                    feats.get("n_beats", 0) / 10.0,
                    feats.get("pos", 0.5),
                    feats.get("pause_before", 0.5),
                    feats.get("mechanism_score", 0.5),
                ])
            else:
                # Fallback: use timestamp position only
                X.append([
                    e.set_time_ms / 60000.0,  # minutes into set
                    0.5, 0.5, 0.5, 0.5,
                ])
            y.append(e.weight)

        if len(y) < 10:
            print(f"Need more data: {len(y)} reactions (need 10+)")
            return

        X = np.array(X)
        y = np.array(y)

        self.model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
        self.model.fit(X, y)
        self.is_trained = True
        self.n_samples = len(y)

        # Feature importances
        names = ["word_count", "n_beats", "pos", "pause", "mechanism"]
        importances = dict(zip(names, [round(f, 3) for f in self.model.feature_importances_]))
        print(f"Global model trained on {len(y)} reactions")
        print(f"Feature importances: {importances}")

    def predict(self, features: dict) -> float:
        """Predict expected reaction weight for a joke."""
        if not self.is_trained:
            return 0.0

        X = np.array([[
            features.get("word_count", 0) / 100.0,
            features.get("n_beats", 0) / 10.0,
            features.get("pos", 0.5),
            features.get("pause_before", 0.5),
            features.get("mechanism_score", 0.5),
        ]])
        return float(self.model.predict(X)[0])


class UserTasteModel:
    """Per-user taste model: what THIS user finds funny.

    Lightweight — tracks user's reaction patterns per mechanism/topic.
    No heavy ML needed — simple frequency + recency weighting.
    """

    def __init__(self, user_id: str, data_dir: str = "/home/box/freaktown-user-models"):
        self.user_id = user_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / f"{user_id}.json"
        self.profile = self._load()

    def _load(self) -> dict:
        """Load user profile."""
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {
            "user_id": self.user_id,
            "mechanism_scores": {},  # mech -> avg reaction weight
            "mechanism_counts": {},  # mech -> n reactions
            "total_reactions": 0,
            "laugh_rate": 0.0,
            "preferred_pos": 0.5,  # where in set they laugh most
        }

    def _save(self):
        """Save user profile."""
        self.path.write_text(json.dumps(self.profile, indent=2))

    def update(self, reaction: str, joke_features: dict):
        """Update profile with a new reaction."""
        weight = REACTION_WEIGHT.get(reaction, 0.0)
        mech = joke_features.get("mechanism", "unknown")

        # Update mechanism score (exponential moving average)
        old_score = self.profile["mechanism_scores"].get(mech, 0.0)
        old_count = self.profile["mechanism_counts"].get(mech, 0)
        new_count = old_count + 1
        alpha = 0.3  # learning rate
        new_score = old_score * (1 - alpha) + weight * alpha

        self.profile["mechanism_scores"][mech] = round(new_score, 3)
        self.profile["mechanism_counts"][mech] = new_count
        self.profile["total_reactions"] += 1

        # Update laugh rate
        total = self.profile["total_reactions"]
        old_rate = self.profile["laugh_rate"]
        self.profile["laugh_rate"] = round(old_rate * (1 - alpha) + (1 if weight > 0 else 0) * alpha, 3)

        # Update preferred position
        pos = joke_features.get("pos", 0.5)
        self.profile["preferred_pos"] = round(
            self.profile["preferred_pos"] * 0.9 + pos * 0.1, 3
        )

        self._save()

    def score(self, joke_features: dict) -> float:
        """Score a joke for THIS user. -1 to 1."""
        mech = joke_features.get("mechanism", "unknown")
        mech_score = self.profile["mechanism_scores"].get(mech, 0.0)

        # Position match bonus
        pos = joke_features.get("pos", 0.5)
        pos_match = 1.0 - abs(pos - self.profile["preferred_pos"])

        return mech_score * 0.7 + pos_match * 0.3

    def score_candidates(self, candidates: list[dict]) -> list[dict]:
        """Score multiple candidates, return sorted by user preference."""
        scored = []
        for c in candidates:
            score = self.score(c)
            scored.append({**c, "user_score": round(score, 3)})
        return sorted(scored, key=lambda x: -x["user_score"])

    def summary(self) -> dict:
        """Human-readable taste summary."""
        mech_scores = self.profile["mechanism_scores"]
        top_mechs = sorted(mech_scores.items(), key=lambda x: -x[1])[:5]
        return {
            "user_id": self.user_id,
            "total_reactions": self.profile["total_reactions"],
            "laugh_rate": self.profile["laugh_rate"],
            "preferred_pos": self.profile["preferred_pos"],
            "top_mechanisms": [{"mech": m, "score": s} for m, s in top_mechs],
        }


if __name__ == "__main__":
    # Demo
    print("Reaction Models Demo")
    print("=" * 50)

    collector = ReactionCollector()
    stats = collector.stats()
    print(f"Existing reactions: {stats}")

    # Simulate some reactions
    print("\nSimulating reactions...")
    import tempfile
    test_path = Path(tempfile.mktemp(suffix=".jsonl"))
    collector = ReactionCollector(test_path)

    # Simulate a user laughing at certain mechanisms
    for i in range(20):
        mech = np.random.choice(["misdirection", "self_deprecation", "escalation", "deadpan"])
        pos = np.random.uniform(0, 1)
        # User likes misdirection and self-deprecation
        if mech in ("misdirection", "self_deprecation"):
            reaction = "laugh"
        elif mech == "deadpan":
            reaction = np.random.choice(["laugh", "crickets"])
        else:
            reaction = "clap"
        collector.add_reaction("test-set", reaction, int(pos * 60000))

    events = collector.load_all()
    print(f"Collected {len(events)} reactions")

    # Train global model
    print("\nGlobal model:")
    global_model = GlobalLaughModel()
    global_model.train(events)

    # User taste model
    print("\nUser taste model:")
    user = UserTasteModel("demo_user", data_dir="/tmp/test-user-models")
    for e in events[:10]:
        mech = np.random.choice(["misdirection", "self_deprecation", "escalation", "deadpan"])
        user.update(e.reaction, {"mechanism": mech, "pos": e.set_time_ms / 60000.0})

    summary = user.summary()
    print(f"  Total reactions: {summary['total_reactions']}")
    print(f"  Laugh rate: {summary['laugh_rate']:.1%}")
    print(f"  Top mechanisms: {[m['mech'] for m in summary['top_mechanisms']]}")

    # Score candidates
    print("\nCandidate scoring for this user:")
    candidates = [
        {"mechanism": "misdirection", "pos": 0.7, "text": "Setup... punchline!"},
        {"mechanism": "deadpan", "pos": 0.3, "text": "Flat delivery."},
        {"mechanism": "self_deprecation", "pos": 0.5, "text": "I'm so bad at..."},
    ]
    scored = user.score_candidates(candidates)
    for s in scored:
        print(f"  {s['mechanism']:20s} score={s['user_score']:.3f} | {s['text'][:30]}")

    # Cleanup
    test_path.unlink()
    import shutil
    shutil.rmtree("/tmp/test-user-models")
