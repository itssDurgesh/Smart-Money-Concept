"""
SMC Pattern Detector -- Signal Generation Engine
Reads detected patterns from DB, calculates entry/SL/TP levels,
and writes trade signals to the `signals` table.

The rr_ratio is auto-computed by MySQL (generated column).

Usage:
    python signals.py                     # Process all unprocessed patterns
    python signals.py --pair EURUSD       # Process specific pair only
    python signals.py --min-confidence 0.80
"""

import argparse
from decimal import Decimal

import pandas as pd
from sqlalchemy import text

from config import get_db_session, CONFIDENCE_THRESHOLD, DEFAULT_PAIRS


# ============================================================
# Signal Calculation Logic (SMC Domain Rules)
# ============================================================

def calculate_signal(
    pattern_type: str,
    candle_open: float,
    candle_high: float,
    candle_low: float,
    candle_close: float,
    atr_estimate: float = None,
) -> dict | None:
    """
    Calculate entry, SL, TP based on pattern type and candle data.
    
    SMC Signal Logic:
    - BOS (bullish): Enter at close, SL below low, TP = 2x risk
    - BOS (bearish): Enter at close, SL above high, TP = 2x risk
    - CHoCH: Reversal signal -- enter opposite direction
    - OrderBlock: Enter at OB zone, SL beyond OB, TP = 2-3x risk
    - FVG: Enter at gap fill level, SL beyond gap, TP = 2x risk
    """
    body = candle_close - candle_open
    is_bullish = body > 0
    candle_range = candle_high - candle_low

    if candle_range == 0:
        return None  # Flat candle -- no signal

    # Estimate ATR if not provided (use candle range as proxy)
    if atr_estimate is None or atr_estimate == 0:
        atr_estimate = candle_range

    # Default risk buffer (small offset for SL)
    buffer = atr_estimate * 0.2

    signal = None

    if pattern_type == "BOS":
        if is_bullish:
            signal = {
                "direction": "LONG",
                "entry_price": round(candle_close, 5),
                "stop_loss": round(candle_low - buffer, 5),
                "take_profit": round(candle_close + 2 * (candle_close - candle_low + buffer), 5),
            }
        else:
            signal = {
                "direction": "SHORT",
                "entry_price": round(candle_close, 5),
                "stop_loss": round(candle_high + buffer, 5),
                "take_profit": round(candle_close - 2 * (candle_high + buffer - candle_close), 5),
            }

    elif pattern_type == "CHoCH":
        # CHoCH = reversal -- trade opposite to candle direction
        if is_bullish:
            # Bullish candle but CHoCH = expect bearish reversal
            signal = {
                "direction": "SHORT",
                "entry_price": round(candle_close, 5),
                "stop_loss": round(candle_high + buffer, 5),
                "take_profit": round(candle_close - 2 * (candle_high + buffer - candle_close), 5),
            }
        else:
            signal = {
                "direction": "LONG",
                "entry_price": round(candle_close, 5),
                "stop_loss": round(candle_low - buffer, 5),
                "take_profit": round(candle_close + 2 * (candle_close - candle_low + buffer), 5),
            }

    elif pattern_type == "OrderBlock":
        # OB = enter at the OB zone (candle body midpoint)
        midpoint = round((candle_open + candle_close) / 2, 5)
        if is_bullish:
            signal = {
                "direction": "LONG",
                "entry_price": midpoint,
                "stop_loss": round(candle_low - buffer, 5),
                "take_profit": round(midpoint + 2.5 * (midpoint - candle_low + buffer), 5),
            }
        else:
            signal = {
                "direction": "SHORT",
                "entry_price": midpoint,
                "stop_loss": round(candle_high + buffer, 5),
                "take_profit": round(midpoint - 2.5 * (candle_high + buffer - midpoint), 5),
            }

    elif pattern_type == "FVG":
        # FVG = enter expecting gap fill
        if is_bullish:
            signal = {
                "direction": "LONG",
                "entry_price": round(candle_low, 5),
                "stop_loss": round(candle_low - atr_estimate, 5),
                "take_profit": round(candle_low + 2 * atr_estimate, 5),
            }
        else:
            signal = {
                "direction": "SHORT",
                "entry_price": round(candle_high, 5),
                "stop_loss": round(candle_high + atr_estimate, 5),
                "take_profit": round(candle_high - 2 * atr_estimate, 5),
            }

    return signal


# ============================================================
# Process Patterns and Generate Signals
# ============================================================

def generate_signals(
    pair: str = None,
    min_confidence: float = None,
) -> int:
    """
    Read unprocessed patterns from DB, generate signals, and write to signals table.
    
    Args:
        pair: Optional -- filter by currency pair
        min_confidence: Minimum confidence threshold
    
    Returns:
        Number of signals generated
    """
    if min_confidence is None:
        min_confidence = CONFIDENCE_THRESHOLD

    session = get_db_session()
    generated = 0

    try:
        # Fetch patterns that don't have a signal yet
        query = """
            SELECT p.id AS pattern_id, p.pattern_type, p.confidence_score, p.timeframe,
                   c.id AS candle_id, c.pair, c.open, c.high, c.low, c.close, c.volume
            FROM patterns p
            JOIN candles c ON p.candle_id = c.id
            LEFT JOIN signals s ON s.pattern_id = p.id
            WHERE s.id IS NULL
              AND p.confidence_score >= :min_confidence
        """
        params = {"min_confidence": min_confidence}

        if pair:
            query += " AND c.pair = :pair"
            params["pair"] = pair

        query += " ORDER BY p.detected_at DESC"

        result = session.execute(text(query), params)
        rows = result.fetchall()

        if not rows:
            print(f"[WARN] No unprocessed patterns found (threshold: {min_confidence})")
            return 0

        print(f"[FOUND] Found {len(rows)} unprocessed patterns")

        for row in rows:
            pattern_id = row[0]
            pattern_type = row[1]
            confidence = float(row[2])
            candle_open = float(row[6])
            candle_high = float(row[7])
            candle_low = float(row[8])
            candle_close = float(row[9])
            pair_name = row[5]

            # Calculate signal levels
            signal = calculate_signal(
                pattern_type=pattern_type,
                candle_open=candle_open,
                candle_high=candle_high,
                candle_low=candle_low,
                candle_close=candle_close,
            )

            if signal is None:
                continue

            # Insert signal (rr_ratio is auto-computed by MySQL)
            try:
                session.execute(
                    text("""
                        INSERT INTO signals
                        (pattern_id, direction, entry_price, stop_loss, take_profit)
                        VALUES (:pattern_id, :direction, :entry_price, :stop_loss, :take_profit)
                    """),
                    {
                        "pattern_id": pattern_id,
                        "direction": signal["direction"],
                        "entry_price": signal["entry_price"],
                        "stop_loss": signal["stop_loss"],
                        "take_profit": signal["take_profit"],
                    }
                )
                generated += 1
                print(f"   [OK] {pair_name} | {pattern_type} ({confidence:.3f}) -> "
                      f"{signal['direction']} @ {signal['entry_price']} | "
                      f"SL: {signal['stop_loss']} | TP: {signal['take_profit']}")

            except Exception as e:
                print(f"   [WARN] Signal insert error for pattern {pattern_id}: {e}")
                continue

        session.commit()
        print(f"\n[DB] Generated {generated} signals")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error: {e}")
    finally:
        session.close()

    return generated


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SMC Pattern Detector -- Signal Generation",
    )
    parser.add_argument("--pair", type=str, help="Filter by currency pair")
    parser.add_argument("--min-confidence", type=float, default=CONFIDENCE_THRESHOLD,
                        help=f"Min confidence (default: {CONFIDENCE_THRESHOLD})")

    args = parser.parse_args()

    print("=" * 50)
    print("[SIG] SMC Signal Generator")
    print("=" * 50)

    count = generate_signals(
        pair=args.pair,
        min_confidence=args.min_confidence,
    )

    print(f"\n[DONE] Done! {count} new signals generated.")


if __name__ == "__main__":
    main()
