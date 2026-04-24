"""
SMC Pattern Detector -- XGBoost Model Training Pipeline
Trains a multi-class classifier to detect SMC patterns from candle features.

Classes: BOS, CHoCH, OrderBlock, FVG, NoPattern

Usage:
    python train.py                           # Train with synthetic demo data
    python train.py --csv data/labeled.csv    # Train with labeled CSV
    python train.py --from-db --pair EURUSD   # Train from database (requires labels)
"""

import argparse
import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from xgboost import XGBClassifier

from features import extract_features, FEATURE_COLUMNS
from config import MODEL_PATH


# ============================================================
# Label Encoding
# ============================================================

PATTERN_CLASSES = ["NoPattern", "BOS", "CHoCH", "OrderBlock", "FVG"]
LABEL_MAP = {name: idx for idx, name in enumerate(PATTERN_CLASSES)}
REVERSE_LABEL_MAP = {idx: name for idx, name in enumerate(PATTERN_CLASSES)}


# ============================================================
# Synthetic Training Data Generator
# ============================================================

def generate_synthetic_training_data(n_samples: int = 2000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic labeled training data for initial model development.
    Uses heuristic rules based on SMC domain knowledge.
    
    This is a bootstrap method -- should be replaced with manually labeled data
    for production accuracy.
    """
    np.random.seed(seed)
    print(f"[GEN] Generating {n_samples} synthetic training samples...")

    base_price = 1.1000
    records = []

    for i in range(n_samples):
        # Generate a window of candle-like data
        o = base_price + np.random.randn() * 0.005
        body = np.random.randn() * 0.002
        c = o + body
        h = max(o, c) + abs(np.random.randn()) * 0.001
        l = min(o, c) - abs(np.random.randn()) * 0.001
        vol = np.random.randint(1000, 50000)

        record = {
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": vol,
            "timestamp": datetime(2025, 1, 1) + pd.Timedelta(hours=i),
        }

        # Assign label based on heuristic rules (SMC domain logic)
        body_size = abs(c - o)
        range_size = h - l
        body_ratio = body_size / range_size if range_size > 0 else 0

        # Rule-based labeling heuristics
        r = np.random.random()
        if body_ratio > 0.7 and body_size > 0.003 and vol > 30000:
            # Large body + high volume = displacement -> BOS
            record["label"] = "BOS"
        elif body_ratio > 0.6 and body < 0 and r < 0.3:
            # Bearish reversal candle -> CHoCH
            record["label"] = "CHoCH"
        elif body_ratio < 0.3 and vol > 25000:
            # Small body + high volume = accumulation -> OrderBlock
            record["label"] = "OrderBlock"
        elif range_size > 0.004 and body_ratio > 0.5:
            # Large range with gap potential -> FVG
            record["label"] = "FVG"
        else:
            record["label"] = "NoPattern"

        records.append(record)

    df = pd.DataFrame(records)

    # Print class distribution
    print(f"\n[STATS] Class distribution:")
    for cls, count in df["label"].value_counts().items():
        print(f"   {cls}: {count} ({count/len(df)*100:.1f}%)")

    return df


# ============================================================
# Training Pipeline
# ============================================================

def train_model(
    df: pd.DataFrame,
    label_col: str = "label",
    test_size: float = 0.2,
    save_path: str = None,
) -> dict:
    """
    Train XGBoost multi-class classifier on feature data.
    
    Args:
        df: DataFrame with candle data + 'label' column
        label_col: name of the label column
        test_size: fraction for test split
        save_path: path to save the trained model (.pkl)
    
    Returns:
        dict with model, metrics, and training info
    """
    if save_path is None:
        save_path = MODEL_PATH

    print("\n" + "=" * 60)
    print("[ML] XGBoost Training Pipeline")
    print("=" * 60)

    # --- Step 1: Extract features ---
    print("\n[1/7] Step 1: Extracting features...")
    labels = df[label_col].copy()
    feature_df = extract_features(df)

    # Ensure all feature columns exist
    missing_cols = [c for c in FEATURE_COLUMNS if c not in feature_df.columns]
    if missing_cols:
        print(f"[WARN] Missing feature columns (filling with 0): {missing_cols}")
        for col in missing_cols:
            feature_df[col] = 0

    X = feature_df[FEATURE_COLUMNS].values
    y = labels.map(LABEL_MAP).values

    # Handle NaN values
    X = np.nan_to_num(X, nan=0.0)

    print(f"   Features: {X.shape[1]} | Samples: {X.shape[0]}")

    # --- Step 2: Train/test split ---
    print("\n[2/7] Step 2: Splitting data...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    print(f"   Train: {len(X_train)} | Test: {len(X_test)}")

    # --- Step 3: Train XGBoost ---
    print("\n[3/7] Step 3: Training XGBoost classifier...")
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        objective="multi:softprob",
        num_class=len(PATTERN_CLASSES),
        eval_metric="mlogloss",
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # --- Step 4: Evaluate ---
    print("\n[4/7] Step 4: Evaluating model...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test, y_pred,
        target_names=PATTERN_CLASSES,
        output_dict=True,
    )
    report_str = classification_report(
        y_test, y_pred,
        target_names=PATTERN_CLASSES,
    )
    cm = confusion_matrix(y_test, y_pred)

    print(f"\n   Accuracy: {accuracy:.4f}")
    print(f"\n{report_str}")
    print(f"   Confusion Matrix:")
    print(f"   {cm}")

    # --- Step 5: Cross-validation ---
    print("\n[5/7] Step 5: Cross-validation (5-fold)...")
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    print(f"   CV Accuracy: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    # --- Step 6: Feature importance ---
    print("\n[6/7] Step 6: Feature importance:")
    importances = model.feature_importances_
    feat_imp = sorted(
        zip(FEATURE_COLUMNS, importances),
        key=lambda x: x[1],
        reverse=True,
    )
    for fname, imp in feat_imp:
        bar = "#" * int(imp * 50)
        print(f"   {fname:25s} {imp:.4f}  {bar}")

    # --- Step 7: Save model ---
    print(f"\n[7/7] Step 7: Saving model to {save_path}...")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        pickle.dump(model, f)
    print(f"   [OK] Model saved!")

    # Save training metadata alongside model
    metadata = {
        "trained_at": datetime.now().isoformat(),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_columns": FEATURE_COLUMNS,
        "classes": PATTERN_CLASSES,
        "accuracy": float(accuracy),
        "cv_accuracy_mean": float(cv_scores.mean()),
        "cv_accuracy_std": float(cv_scores.std()),
        "feature_importance": {k: float(v) for k, v in feat_imp},
    }
    meta_path = save_path.replace(".pkl", "_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"   [OK] Metadata saved to {meta_path}")

    print("\n" + "=" * 60)
    print("[DONE] Training complete!")
    print("=" * 60)

    return {
        "model": model,
        "accuracy": accuracy,
        "cv_scores": cv_scores,
        "report": report,
        "confusion_matrix": cm,
        "feature_importance": feat_imp,
        "metadata": metadata,
    }


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SMC Pattern Detector -- Model Training",
    )
    parser.add_argument("--csv", type=str, help="Path to labeled CSV (must have 'label' column)")
    parser.add_argument("--output", type=str, default=MODEL_PATH, help="Model save path")
    parser.add_argument("--synthetic", action="store_true", default=True,
                        help="Use synthetic data (default if no --csv)")
    parser.add_argument("--samples", type=int, default=2000, help="Synthetic sample count")

    args = parser.parse_args()

    if args.csv:
        print(f"[LOAD] Loading labeled data from: {args.csv}")
        df = pd.read_csv(args.csv)
        df.columns = df.columns.str.lower().str.strip()
        if "label" not in df.columns:
            print("[ERROR] CSV must have a 'label' column with values: BOS, CHoCH, OrderBlock, FVG, NoPattern")
            return
    else:
        df = generate_synthetic_training_data(n_samples=args.samples)

    results = train_model(df, save_path=args.output)
    print(f"\n[RESULT] Final accuracy: {results['accuracy']:.4f}")


if __name__ == "__main__":
    main()
