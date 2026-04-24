# Data Inventory

> **Last Updated:** 2026-04-17 by Antigravity (Gemini Agent)  
> All database schemas, data sources, table relationships, and data flow documentation.

---

## 🗄️ Database: `smc_detector` (MySQL 8.0)

### Entity Relationships

```
candles  (1) ──< (many)  patterns    [a pattern is detected ON a candle]
patterns (1) ──< (many)  signals     [a signal is generated FROM a pattern]
signals  (1) ──< (many)  trade_log   [a trade is executed FROM a signal]
```

**Dependency Order (for DROP/CREATE):** `trade_log → signals → patterns → candles`

---

### Table 1: `candles` — Raw OHLCV Price Data

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PK, AUTO_INCREMENT | Unique candle identifier |
| pair | VARCHAR(10) | NOT NULL | Currency pair, e.g. 'EURUSD', 'XAUUSD' |
| timeframe | VARCHAR(5) | NOT NULL | '1M','5M','1H','4H','1D' |
| open | DECIMAL(10,5) | NOT NULL | Opening price |
| high | DECIMAL(10,5) | NOT NULL | Highest price |
| low | DECIMAL(10,5) | NOT NULL | Lowest price |
| close | DECIMAL(10,5) | NOT NULL | Closing price |
| volume | BIGINT | NOT NULL | Trade volume |
| timestamp | TIMESTAMP | NOT NULL | Candle datetime |

**Indexes:** `idx_pair_tf_ts (pair, timeframe, timestamp)`

---

### Table 2: `patterns` — ML-Detected SMC Patterns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PK, AUTO_INCREMENT | Unique pattern identifier |
| candle_id | BIGINT | FK → candles(id), NOT NULL | Which candle this pattern was detected on |
| pattern_type | VARCHAR(20) | NOT NULL | 'BOS','CHoCH','OB','FVG','liquidity' |
| confidence_score | DECIMAL(4,3) | NOT NULL | 0.000 to 1.000 (from `predict_proba`) |
| detected_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When the pattern was detected |
| timeframe | VARCHAR(5) | NOT NULL | Timeframe of detection |
| confirmed | BOOLEAN | DEFAULT FALSE | Whether the pattern has been confirmed |

---

### Table 3: `signals` — Trade Signals with Auto-Computed RR

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PK, AUTO_INCREMENT | Unique signal identifier |
| pattern_id | BIGINT | FK → patterns(id), NOT NULL | Which pattern triggered this signal |
| direction | ENUM('LONG','SHORT') | NOT NULL | Trade direction |
| entry_price | DECIMAL(10,5) | NOT NULL | Entry price level |
| stop_loss | DECIMAL(10,5) | NOT NULL | Stop loss level |
| take_profit | DECIMAL(10,5) | NOT NULL | Take profit level |
| rr_ratio | DECIMAL(4,2) | **GENERATED** (STORED) | `ABS(TP - entry) / ABS(entry - SL)` |
| status | ENUM | DEFAULT 'PENDING' | 'PENDING','ACTIVE','HIT_TP','HIT_SL','CANCELLED' |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When the signal was created |

**Note:** `rr_ratio` is a MySQL generated column — computed automatically, never manually entered.

---

### Table 4: `trade_log` — Execution Results & Backtesting

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BIGINT | PK, AUTO_INCREMENT | Unique trade identifier |
| signal_id | BIGINT | FK → signals(id), NOT NULL | Which signal was traded |
| actual_entry | DECIMAL(10,5) | nullable | Actual entry price |
| actual_exit | DECIMAL(10,5) | nullable | Actual exit price |
| pnl | DECIMAL(10,2) | nullable | Profit/Loss in account currency |
| pips | DECIMAL(8,2) | nullable | Profit/Loss in pips |
| outcome | VARCHAR(10) | nullable | 'WIN', 'LOSS', 'BE' (breakeven) |
| opened_at | TIMESTAMP | nullable | When trade was opened |
| closed_at | TIMESTAMP | nullable | When trade was closed |

---

## 📊 Data Sources

| Source | Format | Usage | Status |
|--------|--------|-------|--------|
| **yfinance API** | API → DataFrame | Primary live/historical data feed | 🔲 Not integrated |
| **TradingView CSV** | CSV file | Fallback / manual data import | 🔲 Not integrated |
| **Manual labeled CSV** | CSV file | ML training data (expert-labeled SMC patterns) | 🔲 Not created |

---

## 🔄 Data Flow

```
yfinance / CSV
      ↓
  [ingest.py]  →  INSERT INTO candles
      ↓
  [features.py]  →  Read candles, compute feature matrix (in-memory)
      ↓
  [train.py / detect.py]  →  XGBoost predict_proba()
      ↓
  INSERT INTO patterns  (confidence ≥ 0.70 only)
      ↓
  [signals.py]  →  Calculate entry/SL/TP
      ↓
  INSERT INTO signals  (rr_ratio auto-computed by MySQL)
      ↓
  [alerts.py]  →  Telegram notification
  [app.py]     →  Flask dashboard reads all tables
```

---

## 📋 Key SQL Queries (Validated)

These queries are confirmed correct and documented in the README:

1. **High-confidence BOS patterns** — JOIN patterns + candles, filter by type/pair/timeframe/confidence
2. **Win rate by pattern type** — GROUP BY pattern_type on trade_log + signals + patterns
3. **Best RR pending signals** — Filter signals WHERE status='PENDING' AND rr_ratio ≥ 2.0
4. **Total PnL by currency pair** — SUM pnl/pips grouped by pair across full join chain
