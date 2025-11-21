# web_app.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import sqlite3
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
import pytz

from database_setup import get_db_path, TABLE_NAME

app = FastAPI(title="Smart Trader Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = get_db_path()


def ts_to_unix_ms(ts_value):
    """
    تبدیل timestamp دیتابیس (ISO یا UNIX) → UNIX میلی‌ثانیه
    """
    if ts_value is None:
        return None

    # اگر ISO بود
    if isinstance(ts_value, str):
        try:
            dt = datetime.fromisoformat(ts_value)
            # تبدیل به timezone تهران
            tehran = pytz.timezone("Asia/Tehran")
            dt = dt.astimezone(tehran)
            return int(dt.timestamp() * 1000)
        except:
            pass

    # اگر عدد بود (مثلاً UNIX)
    try:
        return int(float(ts_value) * 1000)
    except:
        return None


def query_db(query: str, params=()) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


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


# سرو statics
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
