"""
SMC Pattern Detector — Shared Configuration
Loads environment variables and provides database engine + session factory.
Used by: ingest.py, features.py, detect.py, signals.py, alerts.py, app.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env file
load_dotenv()

# --- Database Configuration ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "smc_detector")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy engine and session
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# --- Telegram Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- API Configuration ---
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))
API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"

# --- ML Configuration ---
MODEL_PATH = os.getenv("MODEL_PATH", "models/xgb_smc.pkl")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))

# --- Data Ingestion Configuration ---
DEFAULT_PAIRS = os.getenv("DEFAULT_PAIRS", "EURUSD,XAUUSD,GBPUSD").split(",")
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1H")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "60"))

# --- yfinance symbol mapping ---
# yfinance uses '=X' suffix for forex pairs
YFINANCE_SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",       # Gold futures (yfinance proxy for XAUUSD)
    "XAGUSD": "SI=F",       # Silver futures
}

# Timeframe mapping: our notation → yfinance interval
TIMEFRAME_MAP = {
    "1M":  "1m",
    "5M":  "5m",
    "15M": "15m",
    "1H":  "1h",
    "4H":  "4h",  # Note: yfinance doesn't natively support 4h, we resample from 1h
    "1D":  "1d",
}


def get_db_session():
    """Get a new database session. Remember to close after use."""
    return SessionLocal()


def test_connection():
    """Test database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] MySQL connection successful!")
        return True
    except Exception as e:
        print(f"[ERROR] MySQL connection failed: {e}")
        return False


if __name__ == "__main__":
    from sqlalchemy import text
    print(f"Database URL: mysql+pymysql://{DB_USER}:****@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    test_connection()
