# Current State

## Project Status
The Smart Money Control project is a production-grade multi-page trading terminal with fully real-time data — all hardcoded/demo fallbacks have been eliminated.

## Architecture
- **Backend**: `app.py` (FastAPI) — serves APIs for candles, patterns, signals, stats, and a `/api/sync` endpoint that triggers the full ML pipeline (ingest → detect → signals) in the background.
- **Frontend**: Multi-page HTML templates extending `_base.html` — Dashboard (`/`), Signals (`/signals`), Patterns (`/patterns`), Analytics (`/analytics`).
- **Data Pipeline**: `ingest.py` fetches candle data from yFinance → `detect.py` runs XGBoost pattern detection → `signals.py` generates trade signals.
- **Database**: MySQL with tables: `candles`, `patterns`, `signals`, `trade_log`.

## Key Technical Details
- **Charting**: Lightweight Charts v4 (standalone CDN). Chart has a zoom toolbar (+ - Fit GoToLatest 1W 1M 3M 1Y) and keyboard shortcuts (+/-/Home/End/Arrows). `minBarSpacing: 1` allows deep zoom out. `axisPressedMouseMove` enables drag-to-scale on both axes. `axisDoubleClickReset` resets axis on double-click.
- **Background Polling**: Chart auto-refreshes every 15s. A `lastChartState` guard prevents `setData()` from resetting the user's zoom/pan when data hasn't changed.
- **Indicators**: Custom JS implementations of EMA-21, RSI-14, MACD(12,26,9).
- **Price Precision**: Dynamically set — 5 decimals for forex pairs, 2 decimals for JPY/XAU pairs.
- **Pairs Supported**: EURUSD, XAUUSD, GBPUSD (configured in `.env` via `DEFAULT_PAIRS`).
- **Timeframes Supported**: 1H, 4H, 1D (configured in `.env` via `DEFAULT_TIMEFRAMES`).
- **Data Range**: 365 days lookback (`LOOKBACK_DAYS=365` in `.env`).

## API Endpoints
| Endpoint | Method | Key Params | Notes |
|----------|--------|-----------|-------|
| `/api/candles` | GET | `pair`, `timeframe` | No limit — returns full year |
| `/api/signals` | GET | `pair`, `status`, `months=3`, `limit=1000` | Orders by `c.timestamp DESC` |
| `/api/patterns` | GET | `pair`, `timeframe`, `min_confidence=0.7`, `months=12`, `limit=5000` | 1-year history |
| `/api/stats` | GET | — | Includes `avg_confidence` |
| `/api/sync` | POST | — | Runs ingest→detect→signals in background |

## Pages & Data Sources
| Page | Data Source | Fallback |
|------|-----------|----------|
| Dashboard `/` | `/api/candles`, `/api/signals?limit=20`, `/api/stats` | Shows N/A or empty list |
| Signals `/signals` | `/api/signals` (last 3 months, limit 1000) | Empty table |
| Patterns `/patterns` | `/api/patterns?min_confidence=0.5` (last 12 months) | Empty table |
| Analytics `/analytics` | `/api/signals?limit=5000` + `/api/patterns?limit=5000` | Empty charts |

## Display Columns
- **Signals page**: #, Pair, TF, Direction, Pattern, Entry, SL, TP, R:R, Confidence, Status, Candle Time (uses `candle_time` field, NOT `created_at`)
- **Patterns page**: #, Time, Pair, TF, Pattern, Confidence, Confirmed, Action (View on Chart)

## Deep-Linking
- Patterns "View on Chart" button links to `/?pair=X&tf=Y&focus=Z`
- Dashboard parses `pair`, `tf`, `focus` URL params on load
- Auto-sets pair/timeframe dropdowns, scrolls chart to focused candle, adds red "TARGET PATTERN" marker

## Recent Changes (Session 2 — April 25, 2026)
1. Fixed signal ordering: `ORDER BY c.timestamp DESC`
2. Added `/api/sync` POST endpoint with background pipeline
3. Wired "Force Sync" button to call `/api/sync`
4. Added `lastChartState` guard to prevent polling from resetting zoom
5. Signals page: 3-month default filter, confidence slider (70-100%), Pair/TF columns, uses `candle_time`
6. Patterns page: 1-year data, "View on Chart" deep-link button
7. Analytics page: fetches full dataset (limit=5000), uses real `s.timeframe` (no random assignment)
8. Dashboard: zoom toolbar with 8 buttons + 6 keyboard shortcuts, `minBarSpacing: 1`, axis drag-to-scale
9. Dashboard: consolidated `fetchStats` — single `/api/stats` call (no redundant double-fetch), `avg_confidence` from real DB
10. **Eliminated ALL hardcoded/demo fallback data** from all 4 pages
