from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import sqlite3
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import pytz

from database_setup import (
    get_db_path,
    TABLE_NAME,
    TRADE_EVENTS_TABLE,
)

# -----------------------------------------------------------
#   APP INIT
# -----------------------------------------------------------

app = FastAPI(title="SmartTrader Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = get_db_path()


# -----------------------------------------------------------
#   DB Utils
# -----------------------------------------------------------

def db_connect() -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()


def query_db(query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    conn, cur = db_connect()
    try:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# -----------------------------------------------------------
#   Timestamp Normalizer
# -----------------------------------------------------------

def ts_to_unix_ms(ts_value):
    """
    ورودی می‌تواند:
      - رشته ISO
      - ثانیه‌ی یونیکس (float/int)
    خروجی: میلی‌ثانیه‌ی یونیکس (int) در تایم‌زون تهران
    """
    if ts_value is None:
        return None

    # اگر رشته‌ی ISO باشد
    if isinstance(ts_value, str):
        try:
            dt = datetime.fromisoformat(ts_value)
            dt = dt.astimezone(pytz.timezone("Asia/Tehran"))
            return int(dt.timestamp() * 1000)
        except Exception:
            pass

    # اگر مقدار عددی (ثانیه‌ی یونیکس) باشد
    try:
        return int(float(ts_value) * 1000)
    except Exception:
        return None


# -----------------------------------------------------------
#   PRICES
# -----------------------------------------------------------

@app.get("/api/prices")
def get_prices(limit: int = 500):
    """
    آخرین قیمت‌ها (برای چارت اصلی)
    """
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

    # چارت از قدیم به جدید
    rows.reverse()
    return rows


# -----------------------------------------------------------
#   DECISIONS
# -----------------------------------------------------------

@app.get("/api/decisions")
def get_decisions(limit: int = 200):
    """
    آخرین تصمیم‌های معاملاتی.

    نکته مهم:
    در دیتابیس ستون aggregate_s داریم ولی aggregate نداریم،
    پس فقط aggregate_s (و confirm_s) را برمی‌گردانیم تا ارور 500 نگیریم.
    """
    rows = query_db(
        f"""
        SELECT
            timestamp,
            price,
            decision,
            regime,
            reasons_json,
            aggregate_s,
            confirm_s,
            adx,
            confirm_adx
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


# -----------------------------------------------------------
#   BTC PRICE (TMN)
# -----------------------------------------------------------

@app.get("/api/btc_price")
def btc_price():
    """
    قیمت لحظه‌ای بیت‌کوین به تومان برای لندینگ (home.js).

    فعلاً از آخرین رکورد جدول trading_logs استفاده می‌کنیم.
    اگر بعداً چند سیمبل داشتی، اینجا می‌تونی فیلتر symbol اضافه کنی.
    """
    rows = query_db(
        f"""
        SELECT timestamp, price
        FROM {TABLE_NAME}
        WHERE price IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """
    )

    if not rows:
        return {"price_tmn": None, "timestamp": None}

    r = rows[0]
    return {
        "price_tmn": float(r.get("price") or 0.0),
        "timestamp": ts_to_unix_ms(r.get("timestamp")),
    }


# -----------------------------------------------------------
#   PERFORMANCE SUMMARY
# -----------------------------------------------------------

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
            "winrate": 0,
            "total_pnl": 0,
        }

    r = rows[0]
    total = int(r.get("total_trades") or 0)
    wins = int(r.get("wins") or 0)
    losses = int(r.get("losses") or 0)
    pnl = float(r.get("total_pnl") or 0.0)

    winrate = (wins / total * 100) if total else 0.0

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "total_pnl": round(pnl, 3),
    }


# -----------------------------------------------------------
#   DAILY PERFORMANCE
# -----------------------------------------------------------

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


# -----------------------------------------------------------
#   RECENT TRADES
# -----------------------------------------------------------

@app.get("/api/trades/recent")
def trades_recent(limit: int = 50):
    rows = query_db(
        f"""
        SELECT
            timestamp,
            symbol,
            side,
            qty,
            entry_price,
            close_price,
            pnl,
            reason
        FROM {TRADE_EVENTS_TABLE}
        WHERE event_type = 'CLOSE'
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    for r in rows:
        r["timestamp"] = ts_to_unix_ms(r["timestamp"])

    rows.reverse()
    return rows


# -----------------------------------------------------------
#   STATIC FILES & ROUTES (Home + Dashboard)
# -----------------------------------------------------------

BASE_DIR = Path(__file__).parent
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    """
    لندینگ بیزنسی جدید (home.html)
    """
    home_file = static_dir / "home.html"
    if not home_file.exists():
        return HTMLResponse("<h1>SmartTrader</h1><p>home.html موجود نیست.</p>")

    return HTMLResponse(home_file.read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """
    داشبورد تحلیل و چارت زنده (index.html)
    """
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>SmartTrader UI</h1><p>index.html موجود نیست.</p>")

    return HTMLResponse(index_file.read_text(encoding="utf-8"))
