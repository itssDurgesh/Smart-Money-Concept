# 📈 SMC Pattern Detector

> **Detecting institutional footprints in Forex markets using Smart Money Concepts (SMC) + XGBoost + MySQL**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange?logo=mysql)](https://mysql.com)
[![Flask](https://img.shields.io/badge/Flask-2.x-black?logo=flask)](https://flask.palletsprojects.com)
[![XGBoost](https://img.shields.io/badge/ML-XGBoost-brightgreen)](https://xgboost.readthedocs.io)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)

---

## 🧠 What Is This?

Retail traders consistently miss **institutional-grade setups** — Break of Structure (BOS), Order Blocks (OB), and Fair Value Gaps (FVG) — because identifying them manually in real time is nearly impossible.

This system solves that by:
1. **Ingesting** live/historical OHLCV candle data into a MySQL relational database
2. **Running** an XGBoost classifier to detect SMC patterns with confidence scores
3. **Generating** structured trade signals (entry, SL, TP, RR ratio) stored in SQL
4. **Alerting** traders via Telegram when a high-confidence pattern is detected
5. **Visualizing** everything on a live Flask dashboard with Chart.js candlestick overlays

> Built as a B.Tech CSE Semester 4 DBMS Academic Project — with real-world trading applicability.

---

## 🎯 SMC Pattern Glossary

| Term | Full Form | Description |
|------|-----------|-------------|
| **BOS** | Break of Structure | Price breaks a previous swing high/low — trend continuation signal |
| **CHoCH** | Change of Character | Opposite-direction BOS — potential trend reversal |
| **OB** | Order Block | Last up/down candle before a displacement move — institutional entry zone |
| **FVG** | Fair Value Gap | Gap between `candle[i-2].high` and `candle[i].low` — imbalance that fills |
| **Liquidity** | Liquidity Sweep | Price briefly takes out swing highs/lows to grab stop losses before reversing |

---

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────┐
│  Layer 1 — Data Ingestion                              │
│  OHLCV feed (yfinance / CSV) → normalized candle rows  │
└───────────────────────┬────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│  Layer 2 — MySQL Database                              │
│  candles  →  patterns  →  signals  →  trade_log        │
└───────────────────────┬────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│  Layer 3 — ML Detection Engine (Python)                │
│  Feature Extraction → XGBoost Classifier → Confidence  │
└───────────────────────┬────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│  Layer 4 — Signal Generator + Alert System             │
│  entry / SL / TP written to signals → Telegram alert   │
└───────────────────────┬────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│  Layer 5 — Fast-api Dashboard                          │
│  Candlestick chart + pattern overlay + signal history  │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Database | **MySQL 8.0** |
| Backend / ML | **Python** — pandas, scikit-learn, XGBoost, SQLAlchemy, pymysql |
| Web Dashboard | **Flask** + **Chart.js** |
| Data Source | **yfinance API** / TradingView CSV export |
| Alert System | **Telegram Bot API** / Webhook |

---

## 🗄️ Database Schema

### Entity Relationship

```
candles  (1) ──< (many)  patterns    [a pattern is detected ON a candle]
patterns (1) ──< (many)  signals     [a signal is generated FROM a pattern]
signals  (1) ──< (many)  trade_log   [a trade is executed FROM a signal]
```

### Table 1: `candles` — Raw OHLCV Price Data

```sql
CREATE TABLE candles (
    id         BIGINT PRIMARY KEY AUTO_INCREMENT,
    pair       VARCHAR(10)   NOT NULL,        -- e.g. 'EURUSD', 'XAUUSD'
    timeframe  VARCHAR(5)    NOT NULL,        -- '1M','5M','1H','4H','1D'
    open       DECIMAL(10,5) NOT NULL,
    high       DECIMAL(10,5) NOT NULL,
    low        DECIMAL(10,5) NOT NULL,
    close      DECIMAL(10,5) NOT NULL,
    volume     BIGINT        NOT NULL,
    timestamp  TIMESTAMP     NOT NULL,
    INDEX idx_pair_tf_ts (pair, timeframe, timestamp)
);
```

### Table 2: `patterns` — ML-Detected SMC Patterns

```sql
CREATE TABLE patterns (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    candle_id        BIGINT        NOT NULL,
    pattern_type     VARCHAR(20)   NOT NULL,  -- 'BOS','CHoCH','OB','FVG','liquidity'
    confidence_score DECIMAL(4,3)  NOT NULL,  -- 0.000 to 1.000 (from predict_proba)
    detected_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    timeframe        VARCHAR(5)    NOT NULL,
    confirmed        BOOLEAN       DEFAULT FALSE,
    FOREIGN KEY (candle_id) REFERENCES candles(id)
);
```

### Table 3: `signals` — Trade Signals with Auto-Computed RR

```sql
CREATE TABLE signals (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    pattern_id   BIGINT        NOT NULL,
    direction    ENUM('LONG','SHORT') NOT NULL,
    entry_price  DECIMAL(10,5) NOT NULL,
    stop_loss    DECIMAL(10,5) NOT NULL,
    take_profit  DECIMAL(10,5) NOT NULL,
    rr_ratio     DECIMAL(4,2)  GENERATED ALWAYS AS
                     (ABS(take_profit - entry_price) / ABS(entry_price - stop_loss)) STORED,
    status       ENUM('PENDING','ACTIVE','HIT_TP','HIT_SL','CANCELLED') DEFAULT 'PENDING',
    created_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pattern_id) REFERENCES patterns(id)
);
```

### Table 4: `trade_log` — Execution Results & Backtesting

```sql
CREATE TABLE trade_log (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    signal_id    BIGINT        NOT NULL,
    actual_entry DECIMAL(10,5),
    actual_exit  DECIMAL(10,5),
    pnl          DECIMAL(10,2),
    pips         DECIMAL(8,2),
    outcome      VARCHAR(10),                 -- 'WIN','LOSS','BE'
    opened_at    TIMESTAMP,
    closed_at    TIMESTAMP,
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);
```

---

## 🤖 ML Model Details

| Property | Value |
|----------|-------|
| **Task** | Multi-class classification |
| **Classes** | `BOS`, `CHoCH`, `OrderBlock`, `FVG`, `NoPattern` |
| **Model** | XGBoost Classifier |
| **Input window** | 20–50 candles rolling lookback |
| **Confidence threshold** | `≥ 0.70` to generate a signal |
| **Output** | `predict_proba()` → stored as `confidence_score` in MySQL |

### Feature Engineering (per candle window)

- Swing high / swing low positions (rolling lookback)
- Body-to-wick ratio per candle
- Displacement candle: body size relative to ATR
- FVG detection: gap between `candle[i-2].high` and `candle[i].low`
- Volume spike flag: `volume > 1.5× 20-period average`
- Structure break: close above/below previous swing high/low

---

## 📊 Key SQL Queries

```sql
-- 1. High-confidence BOS patterns on EURUSD 1H
SELECT c.pair, c.timeframe, c.timestamp, p.confidence_score
FROM patterns p
JOIN candles c ON p.candle_id = c.id
WHERE p.pattern_type = 'BOS'
  AND c.pair = 'EURUSD'
  AND c.timeframe = '1H'
  AND p.confidence_score >= 0.75
ORDER BY c.timestamp DESC;

-- 2. Win rate by pattern type
SELECT p.pattern_type,
       COUNT(*) AS total_signals,
       SUM(CASE WHEN tl.outcome = 'WIN' THEN 1 ELSE 0 END) AS wins,
       ROUND(SUM(CASE WHEN tl.outcome = 'WIN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS win_rate_pct
FROM trade_log tl
JOIN signals s ON tl.signal_id = s.id
JOIN patterns p ON s.pattern_id = p.id
GROUP BY p.pattern_type;

-- 3. Best RR pending signals
SELECT s.id, s.direction, s.entry_price, s.stop_loss, s.take_profit, s.rr_ratio, p.pattern_type
FROM signals s
JOIN patterns p ON s.pattern_id = p.id
WHERE s.status = 'PENDING'
  AND s.rr_ratio >= 2.0
ORDER BY s.rr_ratio DESC
LIMIT 10;

-- 4. Total PnL by currency pair
SELECT c.pair,
       SUM(tl.pnl) AS total_pnl,
       SUM(tl.pips) AS total_pips,
       COUNT(*) AS trades
FROM trade_log tl
JOIN signals s ON tl.signal_id = s.id
JOIN patterns p ON s.pattern_id = p.id
JOIN candles c ON p.candle_id = c.id
GROUP BY c.pair
ORDER BY total_pnl DESC;
```

---

## 📦 Project Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | MySQL schema (4 tables, indexes, generated column) | ✅ Designed |
| 2 | Python data ingestion script (CSV / yfinance → `candles`) | 🔲 Pending |
| 3 | ML feature extraction script (`candles` → feature matrix) | 🔲 Pending |
| 4 | Trained XGBoost model (`.pkl`, writes to `patterns`) | 🔲 Pending |
| 5 | Signal generation script (`patterns` → `signals`) | 🔲 Pending |
| 6 | Flask dashboard (candlestick chart + pattern overlay) | 🔲 Pending |
| 7 | ER Diagram | ✅ Designed |
| 8 | Project report | 🔲 Pending |

---

## 🚀 Getting Started

### Prerequisites

```bash
pip install pandas scikit-learn xgboost sqlalchemy pymysql flask yfinance
```

### MySQL Setup

```bash
mysql -u root -p < schema.sql
```

### Configuration

Create a `.env` file:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=smc_detector
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Run

```bash
# Ingest data
python ingest.py --pair EURUSD --timeframe 1H

# Run ML detection
python detect.py

# Start Flask dashboard
python app.py
```

---

## 📁 Project Structure

```
smc-pattern-detector/
├── schema.sql              # MySQL schema for all 4 tables
├── ingest.py               # Data ingestion (yfinance / CSV → candles)
├── features.py             # Feature extraction from candle windows
├── train.py                # XGBoost model training pipeline
├── detect.py               # Run trained model → write to patterns table
├── signals.py              # Signal generation from confirmed patterns
├── alerts.py               # Telegram bot alert system
├── app.py                  # Flask dashboard entry point
├── templates/
│   └── dashboard.html      # Chart.js candlestick + overlay UI
├── models/
│   └── xgb_smc.pkl         # Saved trained model
├── data/
│   └── sample_candles.csv  # Sample labeled training data
├── idea.md                 # Full project brief & context
└── README.md               # This file
```

---

## 🎓 Academic Context

- **Course:** Database Management Systems (DBMS) — B.Tech CSE, Semester 4
- **Domain Edge:** SMC knowledge sourced from HFT mentor background — not generic indicator-based trading
- **Why MySQL over NoSQL:** Strict relational integrity (a signal must have a pattern; a pattern must have a candle). ACID compliance ensures no half-written trade signals. The `rr_ratio` generated column demonstrates server-side SQL computation.
- **Why separate `patterns` table:** Single Responsibility Principle — multiple ML models can log multiple patterns per candle independently.

---

## 👤 Author

**AutoStackAI Founder** — B.Tech CSE Year 2, Semester 4  
*Building at the intersection of AI, trading systems, and full-stack engineering.*

---

*SMC Pattern Detector — Where institutional order flow meets machine learning.*
