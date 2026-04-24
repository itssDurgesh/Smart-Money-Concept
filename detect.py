"""
SMC Pattern Detector -- Pattern Detection Engine
Loads a trained XGBoost model and runs inference on candle data.
Writes detected patterns (with confidence scores) to the `patterns` table.

Usage:
    python detect.py --pair EURUSD --timeframe 1H
    python detect.py --all
"""

import argparse
import pickle
import os

import numpy as np
import pandas as pd
from sqlalchemy import text

from config import (
    get_db_session,
    MODEL_PATH,
    CONFIDENCE_THRESHOLD,
    DEFAULT_PAIRS,
    DEFAULT_TIMEFRAME,
)
from features import get_features_for_pair, FEATURE_COLUMNS
from train import PATTERN_CLASSES, REVERSE_LABEL_MAP


# ============================================================
# Model Loading
# ============================================================

def load_model(model_path: str = None):
    """Load trained XGBoost model from pickle file."""
    if model_path is None:
        model_path = MODEL_PATH

    if not os.path.exists(model_path):
        print(f"[ERROR] Model not found at: {model_path}")
        print("   Run 'python train.py' first to train the model.")
        return None

    with open(model_path, "rb") as f:
        model = pickle.load(f)

    print(f"[OK] Model loaded from {model_path}")
    return model


# ============================================================
# Pattern Detection
# ============================================================

def detect_patterns(
    pair: str,
    timeframe: str,
    model=None,
    threshold: float = None,
    limit: int = 500,
) -> list[dict]:
    """
    Run pattern detection on candles from the database.
    
    Args:
        pair: Currency pair (e.g., 'EURUSD')
        timeframe: Timeframe (e.g., '1H')
        model: Trained XGBoost model (loaded if None)
        threshold: Confidence threshold (uses config default if None)
        limit: Max candles to process
    
    Returns:
        List of detected pattern dicts
    """
    if threshold is None:
        threshold = CONFIDENCE_THRESHOLD

    if model is None:
        model = load_model()
        if model is None:
            return []

    # Fetch candles and extract features
    feature_df = get_features_for_pair(pair, timeframe, limit=limit)
    if feature_df.empty:
        return []

    # Prepare feature matrix
    X = feature_df[FEATURE_COLUMNS].values
    X = np.nan_to_num(X, nan=0.0)

    # Run prediction
    print(f"\n[SCAN] Running detection on {len(X)} candles for {pair} {timeframe}...")
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)

    # Collect detected patterns above threshold
    detected = []
    for i in range(len(predictions)):
        pred_class = int(predictions[i])
        pattern_name = REVERSE_LABEL_MAP.get(pred_class, "Unknown")

        # Skip NoPattern
        if pattern_name == "NoPattern":
            continue

        confidence = float(probabilities[i][pred_class])

        # Apply confidence threshold
        if confidence < threshold:
            continue

        detected.append({
            "candle_id": int(feature_df.iloc[i].get("id", 0)),
            "pattern_type": pattern_name,
            "confidence_score": round(confidence, 3),
            "timeframe": timeframe,
            "candle_index": i,
            "timestamp": str(feature_df.iloc[i].get("timestamp", "")),
        })

    print(f"[OK] Detected {len(detected)} patterns above {threshold:.0%} confidence")

    # Summary by pattern type
    if detected:
        from collections import Counter
        type_counts = Counter(p["pattern_type"] for p in detected)
        for ptype, count in type_counts.most_common():
            avg_conf = np.mean([
                p["confidence_score"] for p in detected if p["pattern_type"] == ptype
            ])
            print(f"   {ptype}: {count} detections (avg confidence: {avg_conf:.3f})")

    return detected


# ============================================================
# Write Patterns to Database
# ============================================================

def save_patterns_to_db(patterns: list[dict]) -> int:
    """
    Write detected patterns to the `patterns` table in MySQL.
    
    Returns: number of patterns inserted
    """
    if not patterns:
        print("[WARN] No patterns to save.")
        return 0

    session = get_db_session()
    inserted = 0

    try:
        for p in patterns:
            # Skip patterns without a valid candle_id
            if p["candle_id"] == 0:
                continue

            session.execute(
                text("""
                    INSERT INTO patterns 
                    (candle_id, pattern_type, confidence_score, timeframe, confirmed)
                    VALUES (:candle_id, :pattern_type, :confidence_score, :timeframe, FALSE)
                """),
                {
                    "candle_id": p["candle_id"],
                    "pattern_type": p["pattern_type"],
                    "confidence_score": p["confidence_score"],
                    "timeframe": p["timeframe"],
                }
            )
            inserted += 1

        session.commit()
        print(f"[DB] Saved {inserted} patterns to database")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Database error: {e}")
    finally:
        session.close()

    return inserted


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SMC Pattern Detector -- Run ML Detection",
    )
    parser.add_argument("--pair", type=str, help="Currency pair (e.g., EURUSD)")
    parser.add_argument("--timeframe", type=str, default=DEFAULT_TIMEFRAME,
                        help=f"Timeframe (default: {DEFAULT_TIMEFRAME})")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD,
                        help=f"Confidence threshold (default: {CONFIDENCE_THRESHOLD})")
    parser.add_argument("--model", type=str, default=MODEL_PATH, help="Model path")
    parser.add_argument("--limit", type=int, default=500, help="Max candles to process")
    parser.add_argument("--all", action="store_true",
                        help=f"Run on all default pairs: {DEFAULT_PAIRS}")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect patterns but don't write to DB")

    args = parser.parse_args()

    # Load model once
    model = load_model(args.model)
    if model is None:
        return

    total_patterns = 0

    if args.all:
        pairs = DEFAULT_PAIRS
    elif args.pair:
        pairs = [args.pair]
    else:
        parser.print_help()
        return

    for pair in pairs:
        print(f"\n{'='*50}")
        print(f"  Processing: {pair} | {args.timeframe}")
        print(f"{'='*50}")

        patterns = detect_patterns(
            pair=pair,
            timeframe=args.timeframe,
            model=model,
            threshold=args.threshold,
            limit=args.limit,
        )

        if not args.dry_run:
            save_patterns_to_db(patterns)

        total_patterns += len(patterns)

    print(f"\n{'='*50}")
    print(f"[DONE] Detection complete! Total patterns: {total_patterns}")
    if args.dry_run:
        print("   (dry-run mode -- nothing saved to DB)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
