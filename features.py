"""
SMC Pattern Detector -- Feature Extraction Engine
Reads raw candle data and computes SMC-relevant features for ML classification.

Features computed:
    1. Swing high/low positions (rolling lookback)
    2. Body-to-wick ratio per candle
    3. Displacement candle detection (body vs ATR)
    4. FVG (Fair Value Gap) detection
    5. Volume spike flag
    6. Structure break detection (BOS/CHoCH proxy)

Usage:
    from features import extract_features
    feature_df = extract_features(candle_df, lookback=20)
"""

import numpy as np
import pandas as pd
from sqlalchemy import text

from config import get_db_session


# ============================================================
# Individual Feature Functions
# ============================================================

def compute_body_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """
    Body-to-wick ratio: |close - open| / (high - low)
    High ratio = strong directional candle (displacement)
    Low ratio = indecision (doji-like)
    """
    body = (df["close"] - df["open"]).abs()
    total_range = df["high"] - df["low"]
    # Avoid division by zero for flat candles
    ratio = body / total_range.replace(0, np.nan)
    return ratio.fillna(0).round(5)


def compute_candle_direction(df: pd.DataFrame) -> pd.Series:
    """
    Candle direction: 1 = bullish, -1 = bearish, 0 = doji
    """
    return np.sign(df["close"] - df["open"]).astype(int)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range -- measures volatility.
    Used to identify displacement candles.
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period, min_periods=1).mean()
    return atr.round(5)


def compute_displacement_flag(df: pd.DataFrame, atr: pd.Series, multiplier: float = 1.5) -> pd.Series:
    """
    Displacement candle: body size > multiplier × ATR.
    These are strong institutional moves.
    """
    body = (df["close"] - df["open"]).abs()
    return (body > multiplier * atr).astype(int)


def compute_volume_spike(df: pd.DataFrame, period: int = 20, threshold: float = 1.5) -> pd.Series:
    """
    Volume spike flag: volume > threshold × rolling average volume.
    Indicates institutional participation.
    """
    avg_volume = df["volume"].rolling(window=period, min_periods=1).mean()
    return (df["volume"] > threshold * avg_volume).astype(int)


def detect_swing_highs(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Detect swing highs: candle where high is the highest in ±lookback window.
    Returns 1 if swing high, 0 otherwise.
    """
    rolling_max = df["high"].rolling(window=2 * lookback + 1, center=True, min_periods=1).max()
    return (df["high"] == rolling_max).astype(int)


def detect_swing_lows(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Detect swing lows: candle where low is the lowest in ±lookback window.
    Returns 1 if swing low, 0 otherwise.
    """
    rolling_min = df["low"].rolling(window=2 * lookback + 1, center=True, min_periods=1).min()
    return (df["low"] == rolling_min).astype(int)


def detect_fvg(df: pd.DataFrame) -> pd.Series:
    """
    Fair Value Gap detection (bullish FVG):
    Gap exists when candle[i].low > candle[i-2].high
    
    Returns the size of the FVG (0 if no gap).
    """
    if len(df) < 3:
        return pd.Series(0, index=df.index)

    prev2_high = df["high"].shift(2)
    curr_low = df["low"]

    # Bullish FVG: current low > 2-candles-ago high
    bullish_fvg = (curr_low - prev2_high).clip(lower=0)

    # Bearish FVG: 2-candles-ago low > current high
    prev2_low = df["low"].shift(2)
    curr_high = df["high"]
    bearish_fvg = (prev2_low - curr_high).clip(lower=0)

    # Combined: positive = bullish FVG, negative = bearish FVG
    fvg = bullish_fvg - bearish_fvg
    return fvg.fillna(0).round(5)


def detect_structure_break(df: pd.DataFrame, lookback: int = 10) -> pd.Series:
    """
    Structure break detection:
    +1 = close broke above rolling swing high (bullish BOS)
    -1 = close broke below rolling swing low (bearish BOS)
     0 = no break
    """
    rolling_high = df["high"].rolling(window=lookback, min_periods=1).max().shift(1)
    rolling_low = df["low"].rolling(window=lookback, min_periods=1).min().shift(1)

    bullish_break = (df["close"] > rolling_high).astype(int)
    bearish_break = (df["close"] < rolling_low).astype(int)

    return bullish_break - bearish_break


def compute_price_change_pct(df: pd.DataFrame) -> pd.Series:
    """Percentage change from previous close."""
    return df["close"].pct_change().fillna(0).round(6)


def compute_upper_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Upper wick as proportion of total range. High = rejection."""
    total_range = df["high"] - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    return (upper_wick / total_range.replace(0, np.nan)).fillna(0).round(5)


def compute_lower_wick_ratio(df: pd.DataFrame) -> pd.Series:
    """Lower wick as proportion of total range. High = rejection."""
    total_range = df["high"] - df["low"]
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    return (lower_wick / total_range.replace(0, np.nan)).fillna(0).round(5)


# ============================================================
# Master Feature Extraction Pipeline
# ============================================================

def extract_features(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Extract all SMC-relevant features from candle DataFrame.
    
    Args:
        df: DataFrame with columns: open, high, low, close, volume, timestamp
        lookback: window size for rolling calculations
    
    Returns:
        DataFrame with original candle data + computed feature columns
    """
    if df.empty:
        print("[WARN] Empty DataFrame -- no features to extract.")
        return df

    features = df.copy()

    # --- Candle properties ---
    features["body_wick_ratio"] = compute_body_wick_ratio(df)
    features["candle_direction"] = compute_candle_direction(df)
    features["upper_wick_ratio"] = compute_upper_wick_ratio(df)
    features["lower_wick_ratio"] = compute_lower_wick_ratio(df)
    features["price_change_pct"] = compute_price_change_pct(df)

    # --- Volatility ---
    atr = compute_atr(df, period=14)
    features["atr"] = atr
    features["displacement_flag"] = compute_displacement_flag(df, atr, multiplier=1.5)

    # --- Volume ---
    features["volume_spike"] = compute_volume_spike(df, period=20, threshold=1.5)

    # --- Structure ---
    features["swing_high"] = detect_swing_highs(df, lookback=lookback // 2)
    features["swing_low"] = detect_swing_lows(df, lookback=lookback // 2)
    features["structure_break"] = detect_structure_break(df, lookback=lookback)

    # --- Imbalance ---
    features["fvg_size"] = detect_fvg(df)

    # --- Rolling statistics ---
    features["rolling_avg_body"] = (df["close"] - df["open"]).abs().rolling(
        window=lookback, min_periods=1
    ).mean().round(5)

    features["rolling_vol_ratio"] = (
        df["volume"] / df["volume"].rolling(window=lookback, min_periods=1).mean()
    ).fillna(1).round(3)

    print(f"[OK] Extracted {len(features.columns) - len(df.columns)} features from {len(df)} candles")
    return features


# ============================================================
# Database Helper: Fetch candles and extract features
# ============================================================

def get_features_for_pair(pair: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """
    Fetch candles from MySQL and extract features.
    
    Args:
        pair: Currency pair (e.g., 'EURUSD')
        timeframe: Timeframe (e.g., '1H')
        limit: Max candles to fetch
    
    Returns:
        Feature DataFrame ready for ML model
    """
    session = get_db_session()

    try:
        result = session.execute(
            text("""
                SELECT id, pair, timeframe, open, high, low, close, volume, timestamp
                FROM candles
                WHERE pair = :pair AND timeframe = :timeframe
                ORDER BY timestamp ASC
                LIMIT :limit
            """),
            {"pair": pair, "timeframe": timeframe, "limit": limit}
        )

        rows = result.fetchall()
        if not rows:
            print(f"[WARN] No candles found for {pair} {timeframe}")
            return pd.DataFrame()

        columns = ["id", "pair", "timeframe", "open", "high", "low", "close", "volume", "timestamp"]
        df = pd.DataFrame(rows, columns=columns)

        # Convert numeric columns
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        df["volume"] = df["volume"].astype(int)

        print(f"[FETCH] Fetched {len(df)} candles for {pair} {timeframe}")
        return extract_features(df)

    except Exception as e:
        print(f"[ERROR] Error fetching candles: {e}")
        return pd.DataFrame()
    finally:
        session.close()


# ============================================================
# Feature column list (for ML model input)
# ============================================================

FEATURE_COLUMNS = [
    "body_wick_ratio",
    "candle_direction",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "price_change_pct",
    "atr",
    "displacement_flag",
    "volume_spike",
    "swing_high",
    "swing_low",
    "structure_break",
    "fvg_size",
    "rolling_avg_body",
    "rolling_vol_ratio",
]


if __name__ == "__main__":
    # Demo: generate features from sample data
    print("=" * 60)
    print("SMC Feature Extraction — Demo Mode")
    print("=" * 60)

    # Create sample data for testing (without DB)
    np.random.seed(42)
    n = 100
    base_price = 1.1000

    sample = pd.DataFrame({
        "open": base_price + np.random.randn(n).cumsum() * 0.001,
        "high": 0, "low": 0,
        "close": base_price + np.random.randn(n).cumsum() * 0.001,
        "volume": np.random.randint(1000, 50000, n),
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="1h"),
    })
    sample["high"] = sample[["open", "close"]].max(axis=1) + abs(np.random.randn(n)) * 0.0005
    sample["low"] = sample[["open", "close"]].min(axis=1) - abs(np.random.randn(n)) * 0.0005

    features = extract_features(sample)
    print(f"\nFeature columns: {FEATURE_COLUMNS}")
    print(f"\nSample output (first 5 rows):")
    print(features[FEATURE_COLUMNS].head().to_string())
