"""
SMC Pattern Detector — FastAPI Dashboard
Serves the web dashboard with candlestick charts, pattern overlays,
and signal history.

Routes:
    /                   — Main dashboard page
    /api/candles        — GET candle data (JSON)
    /api/patterns       — GET detected patterns (JSON)
    /api/signals        — GET trade signals (JSON)
    /api/stats          — GET summary statistics (JSON)
    /api/pairs          — GET available pairs (JSON)
    /api/sync           — POST run ingestion/detection pipeline

Usage:
    uvicorn app:app --host 0.0.0.0 --port 5000 --reload
"""

from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from typing import Optional, List
import subprocess

from config import engine, API_HOST, API_PORT, API_DEBUG

app = FastAPI(title="SMC Pattern Detector")
templates = Jinja2Templates(directory="templates")


# ============================================================
# Helper: Execute query and return as list of dicts
# ============================================================

def query_to_dict(sql: str, params: dict = None) -> list[dict]:
    """Execute a SQL query and return results as list of dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


# ============================================================
# Page Routes
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main chart page."""
    return templates.TemplateResponse(request, "dashboard.html", {"active_page": "chart"})


@app.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    """Serve the signals table page."""
    return templates.TemplateResponse(request, "signals.html", {"active_page": "signals"})


@app.get("/patterns", response_class=HTMLResponse)
async def patterns_page(request: Request):
    """Serve the patterns table page."""
    return templates.TemplateResponse(request, "patterns.html", {"active_page": "patterns"})


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Serve the analytics dashboard page."""
    return templates.TemplateResponse(request, "analytics.html", {"active_page": "analytics"})


# ============================================================
# API Routes
# ============================================================

@app.get("/api/pairs")
async def api_pairs():
    """Get list of available currency pairs in the database."""
    rows = query_to_dict("SELECT DISTINCT pair FROM candles ORDER BY pair")
    return [r["pair"] for r in rows]


@app.get("/api/candles")
async def api_candles(
    pair: str = Query("EURUSD", description="Currency pair"),
    timeframe: str = Query("1H", description="Timeframe"),
    limit: Optional[int] = Query(None, description="Number of candles (optional)")
):
    """Get candle data for charting."""
    query = """
        SELECT id, pair, timeframe, 
               CAST(open AS CHAR) as open, 
               CAST(high AS CHAR) as high, 
               CAST(low AS CHAR) as low, 
               CAST(close AS CHAR) as close, 
               volume, timestamp
        FROM candles
        WHERE pair = :pair AND timeframe = :timeframe
        ORDER BY timestamp DESC
    """
    params = {"pair": pair, "timeframe": timeframe}

    if limit is not None:
        query += " LIMIT :limit"
        params["limit"] = limit

    rows = query_to_dict(query, params)

    # Reverse to chronological order for chart
    rows.reverse()

    # Convert timestamp to string for JSON
    for r in rows:
        r["timestamp"] = str(r["timestamp"])

    return rows


@app.get("/api/patterns")
async def api_patterns(
    pair: Optional[str] = None,
    timeframe: Optional[str] = None,
    min_confidence: float = Query(0.7, description="Minimum confidence score"),
    months: int = Query(12, description="Months of history to fetch"),
    limit: int = Query(5000, description="Max limit")
):
    """Get detected patterns with candle info."""
    query = """
        SELECT p.id, p.pattern_type, 
               CAST(p.confidence_score AS CHAR) as confidence_score,
               p.timeframe, p.confirmed, p.detected_at,
               c.pair, c.timestamp as candle_timestamp,
               CAST(c.open AS CHAR) as candle_open,
               CAST(c.high AS CHAR) as candle_high,
               CAST(c.low AS CHAR) as candle_low,
               CAST(c.close AS CHAR) as candle_close
        FROM patterns p
        JOIN candles c ON p.candle_id = c.id
        WHERE p.confidence_score >= :min_conf
          AND c.timestamp >= DATE_SUB(NOW(), INTERVAL :months MONTH)
    """
    params = {"min_conf": min_confidence, "limit": limit, "months": months}

    if pair:
        query += " AND c.pair = :pair"
        params["pair"] = pair
    if timeframe:
        query += " AND p.timeframe = :timeframe"
        params["timeframe"] = timeframe

    query += " ORDER BY p.detected_at DESC LIMIT :limit"

    rows = query_to_dict(query, params)
    for r in rows:
        r["detected_at"] = str(r["detected_at"]) if r["detected_at"] else ""
        r["candle_timestamp"] = str(r["candle_timestamp"]) if r["candle_timestamp"] else ""

    return rows


@app.get("/api/signals")
async def api_signals(
    pair: Optional[str] = None,
    status: Optional[str] = None,
    months: int = Query(3, description="Months of history to fetch"),
    limit: int = Query(1000, description="Max limit")
):
    """Get trade signals with pattern and candle info."""
    query = """
        SELECT s.id, s.direction, 
               CAST(s.entry_price AS CHAR) as entry_price,
               CAST(s.stop_loss AS CHAR) as stop_loss,
               CAST(s.take_profit AS CHAR) as take_profit,
               CAST(s.rr_ratio AS CHAR) as rr_ratio,
               s.status, s.created_at,
               p.pattern_type, 
               CAST(p.confidence_score AS CHAR) as confidence,
               c.pair, c.timeframe, c.timestamp as candle_time
        FROM signals s
        JOIN patterns p ON s.pattern_id = p.id
        JOIN candles c ON p.candle_id = c.id
        WHERE c.timestamp >= DATE_SUB(NOW(), INTERVAL :months MONTH)
    """
    params = {"limit": limit, "months": months}

    if pair:
        query += " AND c.pair = :pair"
        params["pair"] = pair
    if status:
        query += " AND s.status = :status"
        params["status"] = status

    query += " ORDER BY c.timestamp DESC LIMIT :limit"

    rows = query_to_dict(query, params)
    for r in rows:
        r["created_at"] = str(r["created_at"]) if r["created_at"] else ""
        r["candle_time"] = str(r["candle_time"]) if "candle_time" in r and r["candle_time"] else ""

    return rows


@app.get("/api/stats")
async def api_stats():
    """Get summary statistics for the dashboard."""
    stats = {}

    # Total candles
    rows = query_to_dict("SELECT COUNT(*) as count FROM candles")
    stats["total_candles"] = rows[0]["count"] if rows else 0

    # Total patterns
    rows = query_to_dict("SELECT COUNT(*) as count FROM patterns WHERE confidence_score >= 0.70")
    stats["total_patterns"] = rows[0]["count"] if rows else 0

    # Total signals
    rows = query_to_dict("SELECT COUNT(*) as count FROM signals")
    stats["total_signals"] = rows[0]["count"] if rows else 0

    # Signals by status
    rows = query_to_dict("SELECT status, COUNT(*) as count FROM signals GROUP BY status")
    stats["signals_by_status"] = {r["status"]: r["count"] for r in rows}

    # Pattern type distribution
    rows = query_to_dict("""
        SELECT pattern_type, COUNT(*) as count 
        FROM patterns WHERE confidence_score >= 0.70
        GROUP BY pattern_type ORDER BY count DESC
    """)
    stats["pattern_distribution"] = {r["pattern_type"]: r["count"] for r in rows}

    # Average confidence
    rows = query_to_dict("SELECT AVG(confidence_score) as avg_conf FROM patterns WHERE confidence_score >= 0.70")
    stats["avg_confidence"] = round(float(rows[0]["avg_conf"]), 4) if rows and rows[0]["avg_conf"] else 0

    # Win rate (from trade_log)
    rows = query_to_dict("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins
        FROM trade_log
    """)
    if rows and rows[0]["total"] > 0:
        stats["total_trades"] = rows[0]["total"]
        stats["win_rate"] = round(rows[0]["wins"] / rows[0]["total"] * 100, 1)
    else:
        stats["total_trades"] = 0
        stats["win_rate"] = 0

    return stats

def run_sync_pipeline():
    try:
        subprocess.run(["python", "ingest.py", "--all"], check=True)
        subprocess.run(["python", "detect.py", "--all"], check=True)
        subprocess.run(["python", "signals.py"], check=True)
    except Exception as e:
        print(f"Sync pipeline failed: {e}")

@app.post("/api/sync")
async def api_sync(background_tasks: BackgroundTasks):
    """Run the ingestion and ML detection pipeline in the background."""
    background_tasks.add_task(run_sync_pipeline)
    return {"status": "success", "message": "Background sync started"}


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("[START] SMC Pattern Detector -- Dashboard")
    print(f"   http://{API_HOST}:{API_PORT}")
    print(f"   API Docs: http://{API_HOST}:{API_PORT}/docs")
    print("=" * 50)

    uvicorn.run(
        "app:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_DEBUG,
    )
