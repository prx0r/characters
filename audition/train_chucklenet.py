"""Train word-level laugh model on ChuckleNet — FAST version.

Uses LogisticRegression (fast) instead of GradientBoosting (slow).
791 WavLM+prosody features, 48 videos, 39944 words.

Usage:
  python3 train_chucklenet.py
"""
from __future__ import annotations
import pickle, sys, time
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

        n = min(len(feat), len(labels))
        all_X.append(feat[:n])
        all_y.append(labels[:n])
        all_vids.extend([vid] * n)

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return X, y, all_vids


def train_fast(X, y, videos):
    """Train with LogisticRegression — fast, handles high dimensions."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
    from sklearn.preprocessing import StandardScaler

    unique_vids = list(set(videos))
    n_splits = min(10, len(unique_vids))
    gkf = GroupKFold(n_splits=n_splits)

    print(f"{len(y)} words from {len(unique_vids)} videos")
    print(f"Laugh rate: {y.mean()*100:.1f}%")
    print(f"Features: {X.shape[1]} dims")

    # Subsample for speed
    if len(y) > 10000:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(y), 10000, replace=False)
        X = X[idx]
        y = y[idx]
        videos = [videos[i] for i in idx]
        print(f"Subsampled to 10000 words")

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Use SGD classifier — much faster for high-dimensional data
    from sklearn.linear_model import SGDClassifier
    model = SGDClassifier(loss="log_loss", max_iter=200, random_state=42)

    t0 = time.time()
    y_prob = cross_val_predict(model, X_scaled, y, cv=gkf, groups=np.array(videos),
                               method="predict_proba")[:, 1]
    elapsed = time.time() - t0

    auc = roc_auc_score(y, y_prob)
    pr_auc = average_precision_score(y, y_prob)
    brier = brier_score_loss(y, y_prob)

    print(f"\nChuckleNet LogisticRegression (GroupKFold by video):")
    print(f"  AUROC:  {auc:.3f}")
    print(f"  PR-AUC: {pr_auc:.3f}")
    print(f"  Brier:  {brier:.3f}")
    print(f"  Time:   {elapsed:.1f}s")

    # Fit on all
    model.fit(X_scaled, y)

    return {
        "model": model,
        "scaler": scaler,
        "auc": round(auc, 3),
        "pr_auc": round(pr_auc, 3),
        "brier": round(brier, 3),
        "n_words": len(y),
        "n_videos": len(unique_vids),
        "n_features": X.shape[1],
    }


if __name__ == "__main__":
    print("Loading ChuckleNet...", flush=True)
    X, y, videos = load_all_videos()
    print(f"Loaded {len(y)} words from {len(set(videos))} videos", flush=True)

    print("\nTraining (LogisticRegression)...", flush=True)
    result = train_fast(X, y, videos)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "wb") as f:
        pickle.dump(result, f)
    print(f"\nSaved to {OUT}", flush=True)
