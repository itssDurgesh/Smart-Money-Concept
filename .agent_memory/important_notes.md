# Important Notes

> **Last Updated:** 2026-04-17 by Antigravity (Gemini Agent)  
> Critical decisions, constraints, gotchas, and rules that every agent MUST respect.

---

## 🔴 Hard Constraints

### 1. This is a DBMS Academic Project
- The primary evaluation is on the **MySQL schema, relationships, and SQL queries**
- ML and Flask dashboard are impressive additions, but the DB must be rock-solid
- Must demonstrate: foreign keys, indexes, generated columns, JOINs, aggregations

### 2. MySQL Is Mandatory — Not Negotiable
- **No switching to PostgreSQL, SQLite, or MongoDB**
- Reasons: course requirement + ACID compliance + generated columns + FK integrity
- All SQL must be MySQL 8.0 compatible syntax

### 3. Confidence Threshold = 0.70
- A signal should ONLY be generated if `confidence_score >= 0.70`
- This is a design decision, not arbitrary — below 0.70 is noise in SMC context
- Do not lower this threshold without owner's explicit approval

### 4. rr_ratio Is a Generated Column
- It is computed by MySQL itself: `ABS(take_profit - entry_price) / ABS(entry_price - stop_loss)`
- **Never try to INSERT a value for rr_ratio** — MySQL will reject the insert
- This is a key academic talking point (server-side computation)

---

## 🟡 Design Decisions (Made & Final)

### Why Separate `patterns` Table
- Multiple ML models could detect multiple patterns on the same candle
- Single Responsibility: `candles` = raw data, `patterns` = ML output
- Allows querying patterns independently without touching price data
- **Do not merge patterns into the candles table**

### Why 4 Tables and Not 2 or 3
- Each table represents a distinct entity in the pipeline
- `candles → patterns → signals → trade_log` mirrors the actual trading workflow
- Academic requirement: demonstrate ER relationships and normalization

### XGBoost Over Neural Networks
- Tabular data → XGBoost is state-of-the-art
- Fast, explainable, no GPU required
- Random Forest is acceptable as fallback
- **Do not switch to LSTM/Transformer unless owner explicitly requests it**

---

## 🟠 Domain-Specific Rules (SMC)

- **BOS (Break of Structure)** = trend continuation, NOT reversal
- **CHoCH (Change of Character)** = BOS in opposite direction = potential reversal
- **Order Blocks** form BEFORE the displacement move, not after
- **FVG** is the gap between `candle[i-2].high` and `candle[i].low` (for bullish FVG)
- **Liquidity sweep** goes PAST the swing high/low briefly, then reverses
- The owner has HFT mentor background — these are not generic indicator definitions

---

## 🔧 Technical Gotchas

1. **yfinance forex pairs** use format like `EURUSD=X` — the `=X` suffix is required
2. **MySQL DECIMAL(10,5)** supports up to 99999.99999 — sufficient for forex prices
3. **MySQL TIMESTAMP** has a 2038 limitation — acceptable for this project's scope
4. **FastAPI & TradingView** — Migrated away from Flask + Chart.js. The current project utilizes FastAPI + Starlette strictly serving `TemplateResponse` to TradingView Lightweight Charts `v4.1.0`.
5. **Windows Terminal Enforcement:** Python print statements MUST strictly use ASCII string characters. Any Unicode emoji (`✅`, `🔴`) crashes the `cp1252` Windows pipeline during training.
6. **TradingView Dependency Panic:** `unpkg.com` secretly resolves Lightweight Charts to version 5.x.x, which structurally breaks legacy physics initializers and internal container grids without throwing an error log. ALWAYS force the asset path to `@4.1.0` explicit boundaries in the HTML.

---

## 🔁 Mandatory Agent Workflow Rules

### WORK IN CHUNKS — Non-Negotiable
Agents MUST work in small, atomic chunks. After completing each chunk:
1. **Update `current_state.md`** — reflect what was just done
2. **Update `task_registry.md`** — mark tasks as `[x]` completed or `[/]` in-progress
3. **Append to `changelog.md`** — log what was built/changed
4. **Save any new confusion to `confusion_log.md`**

### WHY: Agent Termination Risk
- Agent sessions can terminate unexpectedly (timeout, crash, context limit)
- If work is done but memory isn't updated, the next agent has NO idea what happened
- **Orphan work = wasted work** — if it's not in `.agent_memory`, it doesn't exist

### Chunk Size Guidelines
| Task Type | Chunk Size |
|-----------|-----------|
| Creating a new file | 1 file = 1 chunk → update memory |
| Editing multiple files | Each file = 1 chunk → update memory |
| Multi-step pipeline | Each step = 1 chunk → update memory |
| Research/analysis | Each finding = 1 chunk → update memory |

### Example Workflow
```
1. Pick task T-007 from task_registry.md → mark as [/]
2. Build schema.sql
3. UPDATE task_registry.md → T-007 = [x]
4. UPDATE current_state.md → "schema.sql created"
5. APPEND changelog.md → log the work
6. THEN pick next task
```

**Never batch 3+ files without a memory update in between.**

---

## 📌 Owner Preferences (Observed)

- Prefers clean, well-documented code with clear separation of concerns
- Values agent continuity — wants handoff to be seamless between sessions
- Has existing `Claude Data/` folder with older agent state system — `.agent_memory` supersedes it
- Appreciates when agents understand the financial trading domain context
