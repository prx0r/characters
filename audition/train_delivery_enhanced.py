"""Train delivery model with pitch + spectral features (T2 from deliveryreview).

Currently: wps/pause/pos/hist only → AUC 0.654
Adding: f0_std, centroid, mfcc1, rms_std, onset_rate → should push higher

Usage:
  python3 train_delivery_enhanced.py
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))


def load_kt_beats_with_audio():
    """Load KT beats + join librosa audio features."""
    beats_path = Path("/home/box/comedy-audio/laugh_training_beats.jsonl")
    librosa_path = Path("/home/box/comedy-audio/librosa_features.json")

    if not beats_path.exists():
        print("No KT beats found")
        return [], [], []

    beats = [json.loads(l) for l in open(beats_path)]
    librosa = json.loads(librosa_path.read_text()) if librosa_path.exists() else {}

    X, y, groups = [], [], []
    for b in beats:
        stem = b["stem"]

        # Base timing features
        base = [
            b.get("wps", 0) / 10.0,
            b.get("pause_before", 0) / 5.0,
            b.get("dur", 0) / 10.0,
            b.get("pos", 0),
            b.get("hist", 0) / 10.0,
        ]

        # Audio features (from librosa, per-stem)
        audio = librosa.get(stem, {})
        audio_feats = [
            audio.get("f0_std", 50) / 100.0,      # pitch variation
            audio.get("cent_mean", 2000) / 5000.0,  # brightness
            audio.get("rms_std", 0.05) / 0.1,       # energy variation
            audio.get("mfcc1_mean", -80) / 100.0,   # spectral shape
            audio.get("onset_rate", 2) / 5.0,       # articulation rate
        ]

        X.append(base + audio_feats)
        y.append(b.get("laugh", 0))
        groups.append(stem.split("_")[0])  # comedian

    return X, y, groups


def train_enhanced(X, y, groups):
    """Train with GroupKFold by comedian."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, brier_score_loss

    X = np.array(X)
    y = np.array(y)
    groups = np.array(groups)

    n_groups = min(5, len(set(groups)))
    gkf = GroupKFold(n_splits=n_groups)

    model = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)

    y_prob = cross_val_predict(model, X, y, cv=gkf, groups=groups, method="predict_proba")[:, 1]

    auc = roc_auc_score(y, y_prob)
    brier = brier_score_loss(y, y_prob)
    mean_pred = y_prob.mean()
    mean_actual = y.mean()

    print(f"Enhanced delivery model (timing + audio features):")
    print(f"  AUROC:      {auc:.3f}")
    print(f"  Brier:      {brier:.3f}")
    print(f"  Cal gap:    {abs(mean_pred - mean_actual):.3f}")
    print(f"  N:          {len(y)} beats from {len(set(groups))} comedians")

    # Fit on all
    model.fit(X, y)
    importances = model.feature_importances_
    names = ["wps", "pause", "dur", "pos", "hist",
             "f0_std", "centroid", "rms_std", "mfcc1", "onset"]
    print(f"\nFeature importances:")
    for name, imp in sorted(zip(names, importances), key=lambda x: -x[1]):
        print(f"  {name:10s} {imp:.3f}")

    return {
        "model": model,
        "auc": round(auc, 3),
        "brier": round(brier, 3),
        "calibration_gap": round(abs(mean_pred - mean_actual), 3),
        "n_beats": len(y),
        "n_comedians": len(set(groups)),
        "feature_names": names,
        "feature_importances": dict(zip(names, [round(f, 3) for f in importances])),
    }


if __name__ == "__main__":
    print("Loading KT beats + audio features...")
    X, y, groups = load_kt_beats_with_audio()

    if not X:
        print("No data found")
        sys.exit(1)

    print(f"\nTraining enhanced model...")
    result = train_enhanced(X, y, groups)

    # Save
    out = Path(__file__).parent / "voicelab" / "delivery_enhanced_model.pkl"
    with open(out, "wb") as f:
        pickle.dump(result, f)
    print(f"\nSaved to {out}")

    # Update MANIFEST
    manifest_path = Path(__file__).parent / "voicelab" / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest["models"]["delivery_enhanced_model.pkl"] = {
            "auc": result["auc"],
            "validation": "GroupKFold by comedian",
            "n_beats": result["n_beats"],
            "n_comedians": result["n_comedians"],
            "features": result["feature_names"],
            "note": "Timing + audio features (f0, centroid, mfcc, onset)",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print("MANIFEST updated")
