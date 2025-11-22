# ==============================================
#   web_app.py — Refactored, Optimized, Clean
# ==============================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import sqlite3
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import pytz

from database_setup import get_db_path, TABLE_NAME, TRADE_EVENTS_TABLE


# ==============================================
#   FastAPI APP INIT
# ==============================================

app = FastAPI(title="Smart Trader Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = get_db_path()


# ==============================================
#   DB Utils
# ==============================================

def db_connect() -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()


def query_db(query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    conn, cur = db_connect()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==============================================
#   TIME CONVERSION UTILS
# ==============================================

def ts_to_unix_ms(ts_value):
    """ convert DB timestamps (ISO / float / int) → unix ms """
    if ts_value is None:
        return None

    # ISO timestamp
    if isinstance(ts_value, str):
        try:
            dt = datetime.fromisoformat(ts_value)
            tehran = pytz.timezone("Asia/Tehran")
            dt = dt.astimezone(tehran)
            return int(dt.timestamp() * 1000)
        except:
            pass

    # Unix timestamp (seconds)
    try:
        return int(float(ts_value) * 1000)
    except:
        return None


# ==============================================
#   API ENDPOINTS
# ==============================================

# -----------------------------
#   Prices
# -----------------------------
@app.get("/api/prices")
def get_prices(limit: int = 500):
    rows = query_db(
        f"""
        SELECT timestamp, price, tf
        FROM {TABLE_NAME}
        WHERE price IS NOT NULL
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    for r in rows:
        r["timestamp"] = ts_to_unix_ms(r["timestamp"])

    rows.reverse()
    return rows


# -----------------------------
#   Trade Decisions
# -----------------------------
@app.get("/api/decisions")
def get_decisions(limit: int = 200):
    rows = query_db(
        f"""
        SELECT timestamp, price, decision, regime, reasons_json
        FROM {TABLE_NAME}
        WHERE decision IS NOT NULL AND decision <> ''
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    for r in rows:
        r["timestamp"] = ts_to_unix_ms(r["timestamp"])

    rows.reverse()
    return rows


# -----------------------------
#   Performance Summary
# -----------------------------
@app.get("/api/perf/summary")
def perf_summary():
    rows = query_db(
        f"""
        SELECT
            COUNT(*) AS total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losses,
            SUM(pnl) AS total_pnl
        FROM {TRADE_EVENTS_TABLE}
        WHERE event_type = 'CLOSE'
        """
    )

    if not rows:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "total_pnl": 0.0,
        }

    r = rows[0]
    total = int(r.get("total_trades") or 0)
    wins = int(r.get("wins") or 0)
    losses = int(r.get("losses") or 0)
    total_pnl = float(r.get("total_pnl") or 0.0)

    winrate = (wins / total * 100.0) if total > 0 else 0.0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "total_pnl": total_pnl,
    }


# -----------------------------
#   Daily PnL
# -----------------------------
@app.get("/api/perf/daily")
def perf_daily(limit: int = 30):
    rows = query_db(
        f"""
        SELECT
            DATE(timestamp) AS day,
            COUNT(*) AS n_trades,
            SUM(pnl) AS pnl,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losses
        FROM {TRADE_EVENTS_TABLE}
        WHERE event_type = 'CLOSE'
        GROUP BY DATE(timestamp)
        ORDER BY day DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows.reverse()
    return rows


# -----------------------------
#   Recent Trades
# -----------------------------
@app.get("/api/trades/recent")
def trades_recent(limit: int = 50):
    rows = query_db(
        f"""
        SELECT
            timestamp,
            symbol,
            trade_id,
            side,
            qty,
            entry_price,
            close_price,
            pnl,
            reason
        FROM {TRADE_EVENTS_TABLE}
        WHERE event_type = 'CLOSE'
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )

    for r in rows:
        r["timestamp"] = ts_to_unix_ms(r["timestamp"])

    return rows


# ==============================================
#   STATIC FILES
# ==============================================

BASE_DIR = Path(__file__).parent
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Smart Trader</h1><p>index.html هنوز ساخته نشده.</p>")

    return HTMLResponse(index_file.read_text(encoding="utf-8"))

