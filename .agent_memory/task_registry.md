# Task Registry

> **Last Updated:** 2026-04-20 by Antigravity (Gemini Agent)  
> This is the master task list. Every deliverable and sub-task lives here.

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[/]` | In progress |
| `[x]` | Completed |
| `[!]` | Blocked (with reason) |
| `[~]` | Skipped / deferred |

---

## Phase 1: Foundation & Schema

- [x] **T-001:** Finalize project idea and problem statement
- [x] **T-002:** Design MySQL schema (4 tables with relationships)
- [x] **T-003:** Define system architecture (5-layer model)
- [x] **T-004:** Write `README.md` with full documentation
- [x] **T-005:** Write `idea.md` with detailed project brief
- [x] **T-006:** Create `.agent_memory` system for agent continuity
- [x] **T-007:** Create `schema.sql` file with all CREATE TABLE statements
  - Include `DROP TABLE IF EXISTS` with correct dependency order
  - Include indexes and generated column for `rr_ratio`
- [x] **T-008:** Set up local MySQL database (`smc_detector`) — Connected & running via `GPU_01`
- [x] **T-009:** Create `.env` configuration file — Migrated to FastAPI config keys

---

## Phase 2: Data Ingestion

- [x] **T-010:** Build `ingest.py` — yfinance API data fetcher
  - Support pairs: EURUSD, XAUUSD, GBPUSD
  - Insert into `candles` table via SQLAlchemy
- [x] **T-011:** Build CSV fallback ingestion path — Implemented Synthetic generation via `train.py`
- [x] **T-012:** Create/obtain `data/sample_candles.csv` with labeled training data (Via `auto_labeler.py`)

---

## Phase 3: ML Pipeline

- [x] **T-013:** Build `features.py` — feature extraction engine
- [x] **T-014:** Build `train.py` — XGBoost training pipeline
- [x] **T-015:** Build `detect.py` — real-time pattern detection

---

## Phase 4: Signal Generation & Alerts

- [x] **T-016:** Build `signals.py` — trade signal generator
- [x] **T-017:** Build `alerts.py` — Telegram notification system

---

## Phase 5: Dashboard

- [x] **T-018:** Build `app.py` — **FastAPI backend**
  - Routes: / (dashboard), /api/candles, /api/patterns, /api/signals, /api/stats
- [x] **T-019:** Build `templates/dashboard.html` — TradingView UI
  - **T-019a:** Fix Windows `cp1252` encoding crashes (Removed emoji/unicode).
  - **T-019b:** Resolve Blank Chart Bug (`v4.1.0` forced).
  - **T-019c:** Implement Drawing Engine mapping ML Signal predictions recursively onto chart arrays.

---

## Phase 6: Academic Deliverables

- [x] **T-020:** Create ER Diagram (visual format — PNG/SVG)
- [ ] **T-021:** Write project report
  - Problem statement, schema, ER diagram, normalization
  - SQL queries with outputs
  - ML model explanation
  - Screenshots of dashboard
- [ ] **T-022:** Prepare viva talking points document

---

## Stretch Goals (Optional)

- [ ] **T-S01:** Backtesting engine (replay signals on historical data → `trade_log`)
- [ ] **T-S02:** Multi-timeframe confluence (e.g., 4H + 1H confirmation)
- [ ] **T-S03:** Auto-refresh dashboard with WebSocket
