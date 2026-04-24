# Project Context

> **Last Updated:** 2026-04-17 by Antigravity (Gemini Agent)

---

## 🎯 Project Identity

| Field | Value |
|-------|-------|
| **Name** | SMC Pattern Detector |
| **Type** | DBMS Academic Project (B.Tech CSE, Semester 4) with real-world ML integration |
| **Domain** | Forex / Financial Trading |
| **Owner** | AutoStackAI Founder — B.Tech CSE Year 2 |
| **Repository** | `c:\Users\offic\Desktop\Projects\Smart Money Control` |

---

## 📝 Problem Statement

Retail traders consistently miss **institutional-grade setups** — Break of Structure (BOS), Order Blocks (OB), and Fair Value Gaps (FVG) — because identifying them manually in real time is nearly impossible.

This system solves that by:
1. Ingesting live/historical OHLCV candle data into a MySQL relational database
2. Running an XGBoost classifier to detect SMC patterns with confidence scores
3. Generating structured trade signals (entry, SL, TP, RR ratio) stored in SQL
4. Alerting traders via Telegram when a high-confidence pattern is detected
5. Visualizing everything on a live Flask dashboard with Chart.js candlestick overlays

---

## 🏗️ System Architecture (5 Layers)

```
Layer 1 — Data Ingestion:     OHLCV feed (yfinance / CSV) → normalized candle rows
Layer 2 — MySQL Database:     candles → patterns → signals → trade_log
Layer 3 — ML Detection:       Feature Extraction → XGBoost Classifier → Confidence
Layer 4 — Signal Generator:   entry/SL/TP written to signals → Telegram alert
Layer 5 — Flask Dashboard:    Candlestick chart + pattern overlay + signal history
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Database | **MySQL 8.0** |
| Backend / ML | **Python 3.10+** — pandas, scikit-learn, XGBoost, SQLAlchemy, pymysql |
| Web Dashboard | **Flask 2.x** + **Chart.js** |
| Data Source | **yfinance API** / TradingView CSV export |
| Alert System | **Telegram Bot API** / Webhook |

---

## 📁 Planned Project Structure

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
├── .agent_memory/          # Agent persistent memory (this folder)
├── Claude Data/            # Legacy agent state (from earlier sessions)
├── idea.md                 # Full project brief & context
└── README.md               # Public-facing project readme
```

---

## 🧠 SMC Domain Knowledge

| Term | Full Form | Description |
|------|-----------|-------------|
| **BOS** | Break of Structure | Price breaks a previous swing high/low — trend continuation signal |
| **CHoCH** | Change of Character | Opposite-direction BOS — potential trend reversal |
| **OB** | Order Block | Last up/down candle before a displacement move — institutional entry zone |
| **FVG** | Fair Value Gap | Gap between `candle[i-2].high` and `candle[i].low` — imbalance that fills |
| **Liquidity** | Liquidity Sweep | Price briefly takes out swing highs/lows to grab stop losses before reversing |

---

## 🎓 Academic Context

- **Course:** Database Management Systems (DBMS)
- **Why MySQL over NoSQL:** Strict relational integrity (a signal must have a pattern; a pattern must have a candle). ACID compliance ensures no half-written trade signals. The `rr_ratio` generated column demonstrates server-side SQL computation.
- **Why separate `patterns` table:** Single Responsibility Principle — multiple ML models can log multiple patterns per candle independently.
- **Why `rr_ratio` is generated:** Auto-computes `|TP - entry| / |entry - SL|` — ensures consistency, never manually entered, indexable.

---

## 🤖 ML Model Specification

| Property | Value |
|----------|-------|
| Task | Multi-class classification |
| Classes | `BOS`, `CHoCH`, `OrderBlock`, `FVG`, `NoPattern` |
| Model | XGBoost Classifier |
| Input window | 20–50 candles rolling lookback |
| Confidence threshold | `≥ 0.70` to generate a signal |
| Output | `predict_proba()` → stored as `confidence_score` in MySQL |
| Training data | Manually labeled historical CSV (SMC domain-expert labeled) |

### Feature Engineering (per candle window)
- Swing high / swing low positions (rolling lookback)
- Body-to-wick ratio per candle
- Displacement candle: body size relative to ATR
- FVG detection: gap between `candle[i-2].high` and `candle[i].low`
- Volume spike flag: `volume > 1.5× 20-period average`
- Structure break: close above/below previous swing high/low
