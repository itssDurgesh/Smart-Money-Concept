# Confusion Log

> **Last Updated:** 2026-04-17 by Antigravity (Gemini Agent)  
> Log of all ambiguities, unresolved questions, and items needing owner clarification.

---

## Format

Each entry follows this structure:
```
### C-XXX: [Short Title]
- **Raised by:** [Agent Name] on [Date]
- **Status:** 🔴 Unresolved / 🟡 Partially Resolved / 🟢 Resolved
- **Question:** [What is unclear]
- **Context:** [Why this matters]
- **Resolution:** [Answer, if resolved]
```

---

### C-001: Training Data Source
- **Raised by:** Antigravity on 2026-04-17
- **Status:** 🟢 Resolved
- **Question:** Where will the labeled training CSV come from? Will the owner manually label candle patterns using SMC domain knowledge, or is there an existing labeled dataset?
- **Context:** `train.py` needs a labeled dataset with columns mapping candle windows to pattern types (BOS, CHoCH, OB, FVG, NoPattern). Without this, the ML pipeline cannot be built. The README states "Manually labeled historical CSV" but no such file exists yet.
- **Resolution:** We implemented an automated synthetic labeller (`train.py:generate_synthetic_training_data()`) leveraging mathematical boundary rules to auto-generate 5,000 baseline items in absence of manual labeling.

---

### C-002: Target Currency Pairs
- **Raised by:** Antigravity on 2026-04-17
- **Status:** 🟡 Partially Resolved
- **Question:** Which specific currency pairs should be supported in the initial version? README mentions EURUSD and XAUUSD — are there others?
- **Context:** Affects `ingest.py` configuration and dashboard filters. Also affects which yfinance symbols to use (e.g., `EURUSD=X`, `XAUUSD` might be `GC=F` on yfinance).
- **Resolution:** Hardcoded support for `EURUSD`, `XAUUSD`, and `GBPUSD` via FastAPI mapping to corresponding standard `yfinance` tickers.

---

### C-003: MySQL Credentials / Hosting
- **Raised by:** Antigravity on 2026-04-17
- **Status:** 🟢 Resolved
- **Question:** Is MySQL already installed locally? What are the connection details? Is there a preferred DB hosting setup (local / Docker / cloud)?
- **Context:** Needed before `schema.sql` can be executed and before any Python DB scripts can run.
- **Resolution:** Confirmed local instance is running smoothly on Windows (using the `GPU_01` conda environment). Connected successfully via `pymysql` and `.env` password mapping.

---

### C-004: Telegram Bot Configuration
- **Raised by:** Antigravity on 2026-04-17
- **Status:** 🔴 Unresolved
- **Question:** Has a Telegram bot been created? Are the bot token and chat ID available?
- **Context:** `alerts.py` requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the `.env` file. This can be deferred to later phases.
- **Resolution:** —

---

### C-005: Claude Data Folder — Deprecation?
- **Raised by:** Antigravity on 2026-04-17
- **Status:** 🟢 Resolved
- **Question:** Should the `Claude Data/` folder be deprecated now that `.agent_memory` exists? Or should both coexist?
- **Context:** The `Claude Data/` folder contained `AGENT_STATE.md`, `claude_prompt.md`, and `idea.md`. The `.agent_memory` system supersedes the single-file agent state approach with a more structured multi-file system for multi-agent handoff.
- **Resolution:** ✅ Owner confirmed — `Claude Data/` deleted on 2026-04-17. `.agent_memory` is the sole canonical memory system.

---

### C-006: Dashboard Scope for Academic Demo
- **Raised by:** Antigravity on 2026-04-17
- **Status:** 🟢 Resolved
- **Question:** How polished does the Flask dashboard need to be? Is a basic functional demo sufficient, or does it need to be production-grade with filters, real-time updates, and styling?
- **Context:** A basic Chart.js candlestick with pattern markers is achievable quickly. A fully styled, real-time dashboard with WebSocket updates is a stretch goal that could delay other deliverables.
- **Resolution:** Migrated to FastAPI + TradingView Lightweight Charts natively projecting live ML pipelines, fulfilling "production-grade" visualization beyond standard academic demos.
