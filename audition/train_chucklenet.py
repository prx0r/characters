"""Train word-level laugh model on ChuckleNet (48 videos, 791-dim WavLM+prosody).

This is the real audio model we've been missing. 791 features per word
(WavLM speech embeddings + prosody), word-level laughter labels.

Usage:
  python3 train_chucklenet.py
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np

DATA_DIR = Path("/home/box/comedy-audio/chucklenet")
OUT = Path(__file__).parent / "voicelab" / "chucklenet_model.pkl"


def load_all_videos() -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load features + labels from all 48 videos."""
    feature_files = sorted(DATA_DIR.glob("features/*_features.npy"))

    all_X, all_y, all_vids = [], [], []

    for fpath in feature_files:
        vid = fpath.stem.replace("_features", "")
        label_path = DATA_DIR / "labels" / f"{vid}_labels.npy"

        if not label_path.exists():
            continue

        feat = np.load(fpath)
        labels = np.load(label_path)

        # Match lengths
        n = min(len(feat), len(labels))
        all_X.append(feat[:n])
        all_y.append(labels[:n])
        all_vids.extend([vid] * n)

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y)

    # Clean NaN/inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    return X, y, all_vids


def train(X, y, videos):
    """Train with GroupKFold by video."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

    unique_vids = list(set(videos))
    n_splits = min(10, len(unique_vids))
    gkf = GroupKFold(n_splits=n_splits)

    print(f"{len(y)} words from {len(unique_vids)} videos")
    print(f"Laugh rate: {y.mean()*100:.1f}%")
    print(f"Features: {X.shape[1]} dims")

    # Subsample for speed (791 features × 50K words is heavy)
    if len(y) > 20000:
        idx = np.random.RandomState(42).choice(len(y), 20000, replace=False)
        X = X[idx]
        y = y[idx]
        videos = [videos[i] for i in idx]
        print(f"Subsampled to 20000 words")

    model = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, random_state=42, subsample=0.8
    )

    y_prob = cross_val_predict(model, X, y, cv=gkf, groups=np.array(videos),
                               method="predict_proba")[:, 1]

    auc = roc_auc_score(y, y_prob)
    pr_auc = average_precision_score(y, y_prob)
    brier = brier_score_loss(y, y_prob)

    print(f"\nChuckleNet (GroupKFold by video):")
    print(f"  AUROC:  {auc:.3f}")
    print(f"  PR-AUC: {pr_auc:.3f}")
    print(f"  Brier:  {brier:.3f}")

    # Fit on all
    model.fit(X, y)

    return {
        "model": model,
        "auc": round(auc, 3),
        "pr_auc": round(pr_auc, 3),
        "brier": round(brier, 3),
        "n_words": len(y),
        "n_videos": len(unique_vids),
        "n_features": X.shape[1],
    }


if __name__ == "__main__":
    print("Loading ChuckleNet...")
    X, y, videos = load_all_videos()
    print(f"Loaded {len(y)} words from {len(set(videos))} videos")

    print("\nTraining...")
    result = train(X, y, videos)

    # Save
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "wb") as f:
        pickle.dump(result, f)
    print(f"\nSaved to {OUT}")
