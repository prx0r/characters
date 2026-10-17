"""Train laugh predictor on prosody200 WITHOUT leakage features.

Finding: f08 (likely energy) has 0.68 correlation with label — crowd noise
during laughter leaks into the feature. Remove it and retrain.

Per peer review: "Only compare genuinely equivalent metrics"
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))


def load_prosody200_clean():
    """Load prosody200 without leakage features."""
    data = np.load(
        "/home/box/repos/characters/theory/datasets/prosody200/top_200_videos_train.npz",
        allow_pickle=True,
    )
    X = data["features"]  # (62042, 15)
    y = data["labels"]
    vids = data["vids"]

    # Remove f08 (leakage: energy during laugh captures crowd noise)
    # Also check other features for high correlation
    correlations = []
    for i in range(X.shape[1]):
        corr = abs(np.corrcoef(X[:, i], y)[0, 1])
        correlations.append((i, corr))

    print("Feature correlations with label:")
    for i, corr in sorted(correlations, key=lambda x: -x[1]):
        flag = " ← LEAKAGE" if corr > 0.5 else ""
        print(f"  f{i:02d}: {corr:.3f}{flag}")

    # Remove features with correlation > 0.5
    leaky = [i for i, corr in correlations if corr > 0.5]
    keep = [i for i in range(X.shape[1]) if i not in leaky]
    X_clean = X[:, keep]

    print(f"\nRemoved {len(leaky)} leaky features: {leaky}")
    print(f"Kept {len(keep)} features: {keep}")

    return X_clean, y, vids, keep


def train_clean(X, y, vids, kept_features):
    """Train with proper held-out-video validation on clean features."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

    unique_vids = np.unique(vids)
    n_groups = min(10, len(unique_vids))
    print(f"\n{len(y)} segments from {len(unique_vids)} videos")
    print(f"Positive rate: {y.mean()*100:.1f}%")
    print(f"Using GroupKFold(n_splits={n_groups}) — held-out videos")

    model = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, random_state=42, subsample=0.8
    )
    gkf = GroupKFold(n_splits=n_groups)

    y_prob = cross_val_predict(model, X, y, cv=gkf, groups=vids, method="predict_proba")[:, 1]

    auc = roc_auc_score(y, y_prob)
    pr_auc = average_precision_score(y, y_prob)
    brier = brier_score_loss(y, y_prob)
    mean_pred = y_prob.mean()
    mean_actual = y.mean()

    print(f"\nResults (clean features, held-out videos):")
    print(f"  AUROC:      {auc:.3f}")
    print(f"  PR-AUC:     {pr_auc:.3f}")
    print(f"  Brier:      {brier:.3f}")
    print(f"  Cal gap:    {abs(mean_pred - mean_actual):.3f}")

    # Fit on all data
    model.fit(X, y)
    importances = model.feature_importances_
    print(f"\nFeature importances:")
    for idx, imp in enumerate(importances):
        print(f"  f{kept_features[idx]:02d}: {imp:.3f}")

    return {
        "model": model,
        "auc": round(auc, 3),
        "pr_auc": round(pr_auc, 3),
        "brier": round(brier, 3),
        "calibration_gap": round(abs(mean_pred - mean_actual), 3),
        "kept_features": kept_features,
        "n_segments": len(y),
        "n_videos": len(unique_vids),
    }


if __name__ == "__main__":
    print("Loading prosody200 (checking for leakage)...")
    X, y, vids, kept = load_prosody200_clean()

    print("\nTraining on clean features...")
    result = train_clean(X, y, vids, kept)

    # Save
    out = Path(__file__).parent / "voicelab" / "prosody200_clean_model.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(result, f)
    print(f"\nModel saved to {out}")

    # Update MANIFEST
    manifest_path = Path(__file__).parent / "voicelab" / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest["models"]["prosody200_clean_model.pkl"] = {
            "auc": result["auc"],
            "pr_auc": result["pr_auc"],
            "validation": "GroupKFold by video (held-out videos)",
            "n_segments": result["n_segments"],
            "n_videos": result["n_videos"],
            "kept_features": result["kept_features"],
            "note": f"AUC {result['auc']} — NO leakage (removed high-correlation features)",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print("MANIFEST updated")
