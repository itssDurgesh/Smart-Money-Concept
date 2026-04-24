"""
SMC Pattern Detector -- Telegram Alert System
Sends formatted trade signal notifications via Telegram Bot API.

Setup:
    1. Create a bot via @BotFather on Telegram
    2. Get your chat_id by messaging @userinfobot
    3. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env

Usage:
    python alerts.py --test                   # Send a test message
    python alerts.py --pending                # Alert all pending signals
"""

import argparse
import requests

from sqlalchemy import text

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, get_db_session


# ============================================================
# Telegram API
# ============================================================

def send_telegram_message(message: str, parse_mode: str = "HTML") -> bool:
    """
    Send a message via Telegram Bot API.
    
    Args:
        message: Text to send (supports HTML formatting)
        parse_mode: 'HTML' or 'Markdown'
    
    Returns:
        True if sent successfully
    """
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        print("[WARN] Telegram not configured -- set TELEGRAM_BOT_TOKEN in .env")
        print(f"   Message (console fallback):\n{message}")
        return False

    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        print("[WARN] Telegram chat ID not configured -- set TELEGRAM_CHAT_ID in .env")
        print(f"   Message (console fallback):\n{message}")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("[OK] Telegram alert sent!")
            return True
        else:
            print(f"[ERROR] Telegram API error: {response.status_code} -- {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        return False


# ============================================================
# Signal Formatting
# ============================================================

def format_signal_alert(
    pair: str,
    pattern_type: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    rr: float,
    confidence: float,
    timeframe: str = "",
) -> str:
    """Format a trade signal into a Telegram-friendly message."""

    emoji_dir = ">>" if direction == "LONG" else "<<"
    emoji_pattern = {
        "BOS": "[BOS]",
        "CHoCH": "[CHoCH]",
        "OrderBlock": "[OB]",
        "FVG": "[FVG]",
    }.get(pattern_type, "[PAT]")

    message = (
        f"<b>{emoji_pattern} SMC SIGNAL -- {pair}</b>\n"
        f"{'_' * 28}\n"
        f"\n"
        f"{emoji_dir} <b>Direction:</b> {direction}\n"
        f">> <b>Pattern:</b> {pattern_type}\n"
        f">> <b>Timeframe:</b> {timeframe}\n"
        f">> <b>Confidence:</b> {confidence:.1%}\n"
        f"\n"
        f"-> <b>Entry:</b> <code>{entry:.5f}</code>\n"
        f"XX <b>Stop Loss:</b> <code>{sl:.5f}</code>\n"
        f"OK <b>Take Profit:</b> <code>{tp:.5f}</code>\n"
        f"RR <b>Risk:Reward:</b> <code>1:{rr:.2f}</code>\n"
        f"\n"
        f"{'_' * 28}\n"
        f"<i>SMC Pattern Detector • AutoStackAI</i>"
    )
    return message


# ============================================================
# Alert Pending Signals
# ============================================================

def alert_pending_signals() -> int:
    """
    Fetch pending signals from DB, send Telegram alerts, and mark as ACTIVE.
    
    Returns:
        Number of alerts sent
    """
    session = get_db_session()
    sent = 0

    try:
        result = session.execute(text("""
            SELECT s.id, s.direction, s.entry_price, s.stop_loss, s.take_profit, 
                   s.rr_ratio, s.status,
                   p.pattern_type, p.confidence_score, p.timeframe,
                   c.pair
            FROM signals s
            JOIN patterns p ON s.pattern_id = p.id
            JOIN candles c ON p.candle_id = c.id
            WHERE s.status = 'PENDING'
            ORDER BY s.created_at DESC
            LIMIT 20
        """))

        rows = result.fetchall()

        if not rows:
            print("[WARN] No pending signals to alert.")
            return 0

        print(f"[FOUND] Found {len(rows)} pending signals to alert")

        for row in rows:
            signal_id = row[0]
            direction = row[1]
            entry = float(row[2])
            sl = float(row[3])
            tp = float(row[4])
            rr = float(row[5]) if row[5] else 0
            pattern_type = row[7]
            confidence = float(row[8])
            timeframe = row[9]
            pair = row[10]

            # Format and send alert
            message = format_signal_alert(
                pair=pair,
                pattern_type=pattern_type,
                direction=direction,
                entry=entry,
                sl=sl,
                tp=tp,
                rr=rr,
                confidence=confidence,
                timeframe=timeframe,
            )

            success = send_telegram_message(message)

            if success:
                # Mark signal as ACTIVE after alerting
                session.execute(
                    text("UPDATE signals SET status = 'ACTIVE' WHERE id = :id"),
                    {"id": signal_id}
                )
                sent += 1

        session.commit()
        print(f"[OK] Sent {sent} alerts")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error: {e}")
    finally:
        session.close()

    return sent


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SMC Pattern Detector -- Telegram Alerts",
    )
    parser.add_argument("--test", action="store_true", help="Send a test message")
    parser.add_argument("--pending", action="store_true", help="Alert all pending signals")

    args = parser.parse_args()

    if args.test:
        print("[TEST] Sending test message...")
        test_msg = format_signal_alert(
            pair="EURUSD",
            pattern_type="BOS",
            direction="LONG",
            entry=1.08500,
            sl=1.08200,
            tp=1.09100,
            rr=2.0,
            confidence=0.85,
            timeframe="1H",
        )
        send_telegram_message(test_msg)

    elif args.pending:
        alert_pending_signals()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
