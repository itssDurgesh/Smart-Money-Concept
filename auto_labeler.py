"""
SMC Pattern Auto-Labeler
Fetches real historic market data via yfinance, applies strict mathematical 
Smart Money Concepts rules to identify patterns, and generates a labeled CSV dataset
for training the XGBoost ML model.
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np

# Configuration
SYMBOL = "EURUSD=X"
PERIOD = "2y"     # 2 years of data
INTERVAL = "1h"   # 1-hour hourly candles
OUTPUT_CSV = "data/smc_training_data.csv"

def fetch_data() -> pd.DataFrame:
    print(f"[FETCH] Fetching real {SYMBOL} data from Yahoo Finance...")
    ticker = yf.Ticker(SYMBOL)
    df = ticker.history(period=PERIOD, interval=INTERVAL)
    
    # Clean up dataframe
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    
    # yfinance datetime column varies ('date' or 'datetime')
    time_col = "datetime" if "datetime" in df.columns else "date"
    df.rename(columns={time_col: "timestamp"}, inplace=True)
    
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df = df.dropna().copy()
    print(f"[OK] Fetched {len(df)} 1-hour candles.")
    return df

def apply_smc_rules(df: pd.DataFrame) -> pd.DataFrame:
    print("[SMC] Applying Smart Money Concept (SMC) mathematical rules...")
    
    # Initialize label column
    df["label"] = "NoPattern"
    
    # 1. Structural Pivots (Swing Highs / Lows)
    lookback = 5
    df['swing_high'] = df['high'] == df['high'].rolling(window=lookback*2+1, center=True, min_periods=1).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=lookback*2+1, center=True, min_periods=1).min()
    
    # Track the last valid swing high and low values
    # Shift by 1 so we don't look into the future
    last_high = np.nan
    last_low = np.nan
    trend_direction = 0 # 1 for bullish, -1 for bearish
    
    for i in range(lookback*2, len(df)):
        # Check if the candle "lookback" steps ago was a swing high/low
        idx_check = i - lookback
        
        if df.at[df.index[idx_check], 'swing_high']:
            last_high = df.at[df.index[idx_check], 'high']
        if df.at[df.index[idx_check], 'swing_low']:
            last_low = df.at[df.index[idx_check], 'low']
            
        current_close = df.at[df.index[i], 'close']
        current_open = df.at[df.index[i], 'open']
        is_bullish_candle = current_close > current_open
        is_bearish_candle = current_close < current_open
        
        label_assigned = False
        
        # ----------------------------------------------------
        # Rule A: Break of Structure (BOS) & Change of Character (CHoCH)
        # ----------------------------------------------------
        if not np.isnan(last_high) and current_close > last_high:
            if trend_direction == -1:
                df.at[df.index[i], 'label'] = "CHoCH"  # Bullish Reversal
            else:
                df.at[df.index[i], 'label'] = "BOS"    # Bullish Continuation
            
            trend_direction = 1  # Trend is now bullish
            last_high = np.nan   # Consume the high
            label_assigned = True
            
            # --- Rule B: Order Block (OB) logic ---
            # If we just broke structure bullishly, the last bearish candle 
            # before this impulsive move is a Bullish Order Block.
            # Look back 1-8 candles for the last red candle.
            for j in range(1, 8):
                if i-j >= 0 and df.at[df.index[i-j], 'close'] < df.at[df.index[i-j], 'open']:
                    # Only label as OB if it hasn't been claimed by something else
                    if df.at[df.index[i-j], 'label'] == "NoPattern":
                        df.at[df.index[i-j], 'label'] = "OrderBlock"
                    break
                    
        elif not np.isnan(last_low) and current_close < last_low:
            if trend_direction == 1:
                df.at[df.index[i], 'label'] = "CHoCH"  # Bearish Reversal
            else:
                df.at[df.index[i], 'label'] = "BOS"    # Bearish Continuation
                
            trend_direction = -1 # Trend is now bearish
            last_low = np.nan    # Consume the low
            label_assigned = True
            
            # --- Rule B: Order Block (OB) logic ---
            # Look back for the last bullish candle before this bearish break
            for j in range(1, 8):
                if i-j >= 0 and df.at[df.index[i-j], 'close'] > df.at[df.index[i-j], 'open']:
                    if df.at[df.index[i-j], 'label'] == "NoPattern":
                        df.at[df.index[i-j], 'label'] = "OrderBlock"
                    break
        
        # ----------------------------------------------------
        # Rule C: Fair Value Gap (FVG)
        # ----------------------------------------------------
        if not label_assigned and i >= 2:
            prev2_high = df.at[df.index[i-2], 'high']
            prev2_low = df.at[df.index[i-2], 'low']
            curr_high = df.at[df.index[i], 'high']
            curr_low = df.at[df.index[i], 'low']
            
            atr_approx = (df.at[df.index[i], 'high'] - df.at[df.index[i], 'low'])
            min_gap_size = atr_approx * 0.1  # Gap must be somewhat noticeable
            
            bullish_gap = curr_low - prev2_high
            bearish_gap = prev2_low - curr_high
            
            if bullish_gap > min_gap_size:
                df.at[df.index[i-1], 'label'] = "FVG"  # The impulsive candle is the FVG
            elif bearish_gap > min_gap_size:
                df.at[df.index[i-1], 'label'] = "FVG"
                
    return df

def generate_training_data():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df = fetch_data()
    df_labeled = apply_smc_rules(df)
    
    # Drop helper columns
    df_labeled.drop(columns=['swing_high', 'swing_low'], inplace=True, errors='ignore')
    
    # Save cleanly
    df_labeled.to_csv(OUTPUT_CSV, index=False)
    
    # Print stats
    print("\n[STATS] Dataset Label Class Distribution:")
    counts = df_labeled["label"].value_counts()
    for cls, count in counts.items():
        print(f"   {cls}: {count} ({count/len(df_labeled)*100:.1f}%)")
        
    print(f"\n[OK] SUCCESS: Auto-labeled dataset saved to {OUTPUT_CSV}")
    print("   You can now pass this to the Machine Learning model via: python train.py")

if __name__ == "__main__":
    print("=" * 60)
    print("SMC Pattern Real-Data Auto-Labeler")
    print("=" * 60)
    generate_training_data()
