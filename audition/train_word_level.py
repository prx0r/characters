"""Word-level laugh model trained on StandUp4AI examples.

Word-level sequence labeling: each word tagged L (laugh follows) or O (no laugh).
Features: word position, sentence context, lexical features, pause before.

Trained on 3203 words from 4 StandUp4AI example videos.
"""
from __future__ import annotations
import csv, json, pickle, re, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
STANDUP_DIR = HERE.parent / "theory" / "datasets" / "standup4ai" / "Examples_label"


def load_standup4ai() -> list[dict]:
    """Load word-level labels from StandUp4AI examples."""
    rows = []
    for csv_path in STANDUP_DIR.glob("*.csv"):
        video_id = csv_path.stem
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            words = list(reader)

        for i, w in enumerate(words):
            # Parse timestamp [start, end]
            ts = w["timestamp"].strip("[]").split(",")
            start = float(ts[0])
            end = float(ts[1])

            # Pause before this word
            if i > 0:
                prev_ts = words[i-1]["timestamp"].strip("[]").split(",")
                prev_end = float(prev_ts[1])
                pause_before = max(0, start - prev_end)
            else:
                pause_before = 0

            # Features
            text = w["text"]
            label = 1 if w["label"] == "L" else 0

            # Sentence boundary detection
            is_sentence_end = text.endswith((".", "!", "?", "..."))
            is_sentence_start = i == 0 or words[i-1]["text"].endswith((".", "!", "?"))

            # Position in video
            pos = i / len(words)

            rows.append({
                "video": video_id,
                "i": i,
                "text": text,
                "start": start,
                "end": end,
                "pause_before": pause_before,
                "label": label,
                "is_sentence_end": is_sentence_end,
                "is_sentence_start": is_sentence_start,
                "pos": pos,
                "word_len": len(text),
                "is_capitalized": text[0].isupper() if text else False,
                "has_punct": any(c in text for c in ".,!?;:"),
            })

    return rows


def extract_features(row: dict, context: list[dict]) -> list[float]:
    """Extract features for one word."""
    # Basic features
    feats = [
        row["pause_before"],
        row["pos"],
        row["word_len"] / 20.0,
        float(row["is_sentence_end"]),
        float(row["is_sentence_start"]),
        float(row["is_capitalized"]),
        float(row["has_punct"]),
    ]

    # Context: pause after (from next word's timing — NOT its label)
    if context:
        next_row = context[0]
        pause_after = max(0, next_row["start"] - row["end"])
        feats.append(pause_after)
        # Word length of next word (not label!)
        feats.append(next_row.get("word_len", 0) / 20.0)
    else:
        feats.append(0)
        feats.append(0)

    # Previous word features (timing only, not labels)
    if len(context) > 1:
        prev = context[1]
        feats.append(prev["pause_before"])
        feats.append(prev.get("word_len", 0) / 20.0)
    else:
        feats.append(0)
        feats.append(0)

    return feats


def build_dataset(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build feature matrix and labels."""
    X, y, videos = [], [], []

    # Group by video
    by_video = {}
    for r in rows:
        by_video.setdefault(r["video"], []).append(r)

    for video, vrows in by_video.items():
        for i, row in enumerate(vrows):
            # Context: next 2 words, previous 2 words
            context = []
            if i + 1 < len(vrows):
                context.append(vrows[i + 1])
            if i + 2 < len(vrows):
                context.append(vrows[i + 2])
            if i - 1 >= 0:
                context.append(vrows[i - 1])
            if i - 2 >= 0:
                context.append(vrows[i - 2])

            feats = extract_features(row, context)
            X.append(feats)
            y.append(row["label"])
            videos.append(video)

    return np.array(X), np.array(y), videos


def train_word_level_model():
    """Train a word-level laugh predictor."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

    print("Loading StandUp4AI word-level labels...")
    rows = load_standup4ai()
    print(f"  {len(rows)} words from {len(set(r['video'] for r in rows))} videos")
    print(f"  Laugh rate: {sum(r['label'] for r in rows)/len(rows)*100:.1f}%")

    X, y, videos = build_dataset(rows)
    print(f"  Feature matrix: {X.shape}")

    # GroupKFold by video
    unique_videos = list(set(videos))
    n_splits = min(4, len(unique_videos))
    gkf = GroupKFold(n_splits=n_splits)

    model = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)

    y_prob = cross_val_predict(model, X, y, cv=gkf, groups=np.array(videos), method="predict_proba")[:, 1]

    auc = roc_auc_score(y, y_prob)
    pr_auc = average_precision_score(y, y_prob)
    brier = brier_score_loss(y, y_prob)

    print(f"\nWord-level model (GroupKFold by video):")
    print(f"  AUROC:  {auc:.3f}")
    print(f"  PR-AUC: {pr_auc:.3f}")
    print(f"  Brier:  {brier:.3f}")

    # Fit on all data
    model.fit(X, y)

    # Feature importances
    names = ["pause_before", "pos", "word_len", "sent_end", "sent_start",
             "capitalized", "has_punct", "pause_after", "next_word_len",
             "prev_pause", "prev_word_len"]
    importances = model.feature_importances_
    print(f"\nFeature importances:")
    for name, imp in sorted(zip(names, importances), key=lambda x: -x[1]):
        print(f"  {name:15s} {imp:.3f}")

    # Save
    out = HERE / "voicelab" / "word_level_model.pkl"
    with open(out, "wb") as f:
        pickle.dump({
            "model": model,
            "auc": auc,
            "pr_auc": pr_auc,
            "brier": brier,
            "feature_names": names,
            "n_words": len(y),
            "n_videos": len(unique_videos),
        }, f)
    print(f"\nSaved to {out}")

    return model, auc


if __name__ == "__main__":
    model, auc = train_word_level_model()
