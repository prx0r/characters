"""Train laugh predictor on prosody200 with proper validation.

Per peer review:
  "Split by comedian and preferably by show, not by random beat"
  "Keep whole performances and comedians separated between training and testing"

prosody200: 62042 segments × 15 features, with video IDs for grouping.
This is cleaner than KT beats (which had shuffle leakage).

Usage:
  python3 train_prosody200.py
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))


def load_prosody200():
    """Load prosody200 dataset with video group IDs."""
    data = np.load(
        "/home/box/repos/characters/theory/datasets/prosody200/top_200_videos_train.npz",
        allow_pickle=True,
    )
    X = data["features"]  # (62042, 15)
    y = data["labels"]    # (62042,) — 0=no laugh, 1=laugh
    vids = data["vids"]   # (62042,) — video ID for grouping
    return X, y, vids


def train_with_proper_cv(X, y, vids):
    """Train with GroupKFold — held-out videos, not shuffled beats."""
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.model_selection import GroupKFold, cross_val_score
    from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

    unique_vids = np.unique(vids)
    n_groups = min(10, len(unique_vids))
    print(f"{len(y)} segments from {len(unique_vids)} videos")
    print(f"Positive rate: {y.mean()*100:.1f}%")
    print(f"Using GroupKFold(n_splits={n_groups}) — held-out videos")

    # Model 1: Gradient Boosting
    gb = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, random_state=42, subsample=0.8
    )
    gkf = GroupKFold(n_splits=n_groups)

    # AUROC
    scores_auc = cross_val_score(gb, X, y, cv=gkf, groups=vids, scoring="roc_auc")
    # PR-AUC (more informative for imbalanced data)
    scores_pr = cross_val_score(gb, X, y, cv=gkf, groups=vids, scoring="average_precision")

    print(f"\nGradient Boosting (GroupKFold by video):")
    print(f"  AUROC:  {scores_auc.mean():.3f} +/- {scores_auc.std():.3f}")
    print(f"  PR-AUC: {scores_pr.mean():.3f} +/- {scores_pr.std():.3f}")

    # Model 2: Random Forest (for comparison)
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    scores_auc_rf = cross_val_score(rf, X, y, cv=gkf, groups=vids, scoring="roc_auc")
    print(f"\nRandom Forest (GroupKFold by video):")
    print(f"  AUROC:  {scores_auc_rf.mean():.3f} +/- {scores_auc_rf.std():.3f}")

    # Fit best model on all data
    best_model = gb if scores_auc.mean() >= scores_auc_rf.mean() else rf
    best_name = "GradientBoosting" if scores_auc.mean() >= scores_auc_rf.mean() else "RandomForest"
    best_model.fit(X, y)

    # Calibration check on training data (in-sample, for reference)
    y_prob = best_model.predict_proba(X)[:, 1]
    brier = brier_score_loss(y, y_prob)
    mean_pred = y_prob.mean()
    mean_actual = y.mean()
    print(f"\n{best_name} fitted on all data:")
    print(f"  Brier score: {brier:.3f}")
    print(f"  Mean predicted: {mean_pred:.3f} vs actual: {mean_actual:.3f}")
    print(f"  Calibration gap: {abs(mean_pred - mean_actual):.3f}")

    # Feature importances
    importances = best_model.feature_importances_
    print(f"\nFeature importances (15 features):")
    for i, imp in enumerate(importances):
        print(f"  f{i:02d}: {imp:.3f}")

    return {
        "model": best_model,
        "name": best_name,
        "auc_mean": scores_auc.mean() if best_name == "GradientBoosting" else scores_auc_rf.mean(),
        "auc_std": scores_auc.std() if best_name == "GradientBoosting" else scores_auc_rf.std(),
        "pr_auc": scores_pr.mean(),
        "brier": brier,
        "calibration_gap": abs(mean_pred - mean_actual),
        "n_segments": len(y),
        "n_videos": len(unique_vids),
    }


def save_model(result: dict, path: str | Path):
    """Save trained model with metadata."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(result, f)
    print(f"\nModel saved to {path}")


if __name__ == "__main__":
    print("Loading prosody200...")
    X, y, vids = load_prosody200()

    print("\nTraining with proper held-out-video validation...")
    result = train_with_proper_cv(X, y, vids)

    # Save
    out = Path(__file__).parent / "voicelab" / "prosody200_heldout_model.pkl"
    save_model(result, out)

    # Update MANIFEST
    manifest_path = Path(__file__).parent / "voicelab" / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest["models"]["prosody200_heldout_model.pkl"] = {
            "size_kb": out.stat().st_size // 1024,
            "auc": round(result["auc_mean"], 3),
            "pr_auc": round(result["pr_auc"], 3),
            "validation": "GroupKFold by video (held-out videos)",
            "n_segments": result["n_segments"],
            "n_videos": result["n_videos"],
            "note": "Proper validation — no shuffle leakage",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print("MANIFEST updated")
