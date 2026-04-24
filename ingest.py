"""
SMC Pattern Detector -- Data Ingestion Script
Fetches OHLCV candle data from yfinance API or CSV files and inserts into MySQL.

Usage:
    python ingest.py --pair EURUSD --timeframe 1H --days 60
    python ingest.py --csv data/sample_candles.csv
    python ingest.py --all                          # Ingest all default pairs
"""

import argparse
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import text

from config import (
    get_db_session,
    engine,
    YFINANCE_SYMBOL_MAP,
    TIMEFRAME_MAP,
    DEFAULT_PAIRS,
    DEFAULT_TIMEFRAME,
    LOOKBACK_DAYS,
)


# ============================================================
# Core Ingestion Functions
# ============================================================

def fetch_from_yfinance(pair: str, timeframe: str, days: int) -> pd.DataFrame:
    """
    Fetch OHLCV data from yfinance API.
    
    Args:
        pair: Currency pair in our format (e.g., 'EURUSD')
        timeframe: Our timeframe notation (e.g., '1H')
        days: Number of days of historical data to fetch
    
    Returns:
        DataFrame with columns: pair, timeframe, open, high, low, close, volume, timestamp
    """
    # Map to yfinance symbol
    symbol = YFINANCE_SYMBOL_MAP.get(pair)
    if not symbol:
        print(f"[WARN] Unknown pair '{pair}'. Known pairs: {list(YFINANCE_SYMBOL_MAP.keys())}")
        return pd.DataFrame()

    # Map to yfinance interval
    interval = TIMEFRAME_MAP.get(timeframe)
    if not interval:
        print(f"[WARN] Unknown timeframe '{timeframe}'. Known: {list(TIMEFRAME_MAP.keys())}")
        return pd.DataFrame()

    # yfinance limits: 1m=7d, 5m/15m=60d, 1h=730d, 1d=unlimited
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"[FETCH] Fetching {pair} ({symbol}) | {timeframe} ({interval}) | {days} days...")

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval=interval)
    except Exception as e:
        print(f"[ERROR] yfinance error for {pair}: {e}")
        return pd.DataFrame()

    if df.empty:
        print(f"[WARN] No data returned for {pair} {timeframe}")
        return pd.DataFrame()

    # Normalize column names (yfinance returns capitalized)
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    # Keep only OHLCV columns
    df = df[["open", "high", "low", "close", "volume"]].copy()

    # Add metadata columns
    df["pair"] = pair
    df["timeframe"] = timeframe
    df["timestamp"] = df.index

    # Reset index for clean DataFrame
    df = df.reset_index(drop=True)

    # Reorder columns to match DB schema
    df = df[["pair", "timeframe", "open", "high", "low", "close", "volume", "timestamp"]]

    print(f"[OK] Fetched {len(df)} candles for {pair} {timeframe}")
    return df


def load_from_csv(filepath: str) -> pd.DataFrame:
    """
    Load OHLCV data from a CSV file.
    
    Expected CSV columns: pair, timeframe, open, high, low, close, volume, timestamp
    OR: Date/Datetime, Open, High, Low, Close, Volume (with pair/timeframe as args)
    """
    print(f"[LOAD] Loading CSV: {filepath}")

    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {filepath}")
        return pd.DataFrame()
    except Exception as e:
        print(f"[ERROR] CSV read error: {e}")
        return pd.DataFrame()

    # Normalize column names to lowercase
    df.columns = df.columns.str.lower().str.strip()

    # Check for required columns
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        missing = required - set(df.columns)
        print(f"[ERROR] CSV missing columns: {missing}")
        return pd.DataFrame()

    # Handle timestamp column (could be 'timestamp', 'date', 'datetime')
    ts_col = None
    for col in ["timestamp", "date", "datetime", "time"]:
        if col in df.columns:
            ts_col = col
            break

    if ts_col:
        df["timestamp"] = pd.to_datetime(df[ts_col])
    else:
        print("[ERROR] CSV must have a timestamp/date/datetime column")
        return pd.DataFrame()

    # Default pair/timeframe if not present
    if "pair" not in df.columns:
        df["pair"] = "UNKNOWN"
        print("[WARN] No 'pair' column in CSV -- defaulting to 'UNKNOWN'")
    if "timeframe" not in df.columns:
        df["timeframe"] = "1H"
        print("[WARN] No 'timeframe' column in CSV -- defaulting to '1H'")

    df = df[["pair", "timeframe", "open", "high", "low", "close", "volume", "timestamp"]]
    print(f"[OK] Loaded {len(df)} candles from CSV")
    return df


# ============================================================
# Database Insert
# ============================================================

def insert_candles(df: pd.DataFrame) -> int:
    """
    Insert candles into MySQL. Uses INSERT IGNORE to skip duplicates
    (based on the UNIQUE KEY on pair + timeframe + timestamp).
    
    Returns: number of rows inserted
    """
    if df.empty:
        print("[WARN] No data to insert.")
        return 0

    session = get_db_session()
    inserted = 0

    try:
        for _, row in df.iterrows():
            try:
                session.execute(
                    text("""
                        INSERT IGNORE INTO candles 
                        (pair, timeframe, open, high, low, close, volume, timestamp)
                        VALUES (:pair, :timeframe, :open, :high, :low, :close, :volume, :timestamp)
                    """),
                    {
                        "pair": row["pair"],
                        "timeframe": row["timeframe"],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row["volume"]),
                        "timestamp": row["timestamp"],
                    }
                )
                inserted += 1
            except Exception as e:
                print(f"[WARN] Row insert error: {e}")
                continue

        session.commit()
        print(f"[DB] Inserted {inserted} candles into MySQL (duplicates skipped)")

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
        description="SMC Pattern Detector -- Data Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python ingest.py --pair EURUSD --timeframe 1H --days 60
    python ingest.py --csv data/sample_candles.csv
    python ingest.py --all
        """
    )

    parser.add_argument("--pair", type=str, help="Currency pair (e.g., EURUSD)")
    parser.add_argument("--timeframe", type=str, default=DEFAULT_TIMEFRAME,
                        help=f"Timeframe (default: {DEFAULT_TIMEFRAME})")
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS,
                        help=f"Lookback days (default: {LOOKBACK_DAYS})")
    parser.add_argument("--csv", type=str, help="Path to CSV file to import")
    parser.add_argument("--all", action="store_true",
                        help=f"Ingest all default pairs: {DEFAULT_PAIRS}")

    args = parser.parse_args()

    total_inserted = 0

    if args.csv:
        # CSV import mode
        df = load_from_csv(args.csv)
        total_inserted = insert_candles(df)

    elif args.all:
        # Ingest all default pairs
        print(f"[SYNC] Ingesting all pairs: {DEFAULT_PAIRS}")
        for pair in DEFAULT_PAIRS:
            df = fetch_from_yfinance(pair, args.timeframe, args.days)
            total_inserted += insert_candles(df)

    elif args.pair:
        # Single pair mode
        df = fetch_from_yfinance(args.pair, args.timeframe, args.days)
        total_inserted = insert_candles(df)

    else:
        parser.print_help()
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"[DONE] Ingestion complete! Total candles inserted: {total_inserted}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
