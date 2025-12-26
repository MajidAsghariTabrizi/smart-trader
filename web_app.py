# -*- coding: utf-8 -*-
"""
SmartTrader Web API + Dashboard
- فقط روی 3 جدول کار می‌کند:
  - trading_logs        (لاگ کامل تصمیم‌ها و کندل‌ها)
  - trade_events        (OPEN / CLOSE تریدها)
  - account_state       (اسنپ‌شات وضعیت حساب)

این ماژول فقط خوانش می‌کند؛ نوشتن در database_setup و main.py انجام می‌شود.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

import sqlite3

logger = logging.getLogger(__name__)
from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database_setup import (
    get_db_path,
    get_db_connection,
    TABLE_NAME,            # trading_logs
    TRADE_EVENTS_TABLE,    # trade_events
    ACCOUNT_STATE_TABLE,   # account_state
    USERS_TABLE,
    USER_PLANS_TABLE,
    INSIGHTS_POSTS_TABLE,
)
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
)
from plans import get_user_plan, assign_default_plan, set_user_plan
from market_providers import get_market_data, MarketDataGateway
from behavior_engine import compute_behavior_score

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="SmartTrader API", version="1.0")

# ----------------------------------------------------------------------
# CORS برای فرانت (لوکال و دامنه اصلی)
# ----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Static & Pages
# ----------------------------------------------------------------------

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _read_html(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "<h1>SmartTrader</h1><p>Dashboard is not built yet.</p>"


@app.get("/", response_class=HTMLResponse)
async def home_page() -> HTMLResponse:
    """
    صفحه‌ی اصلی — فایل صحیح در مسیر:
    /root/smart-trader/static/home.html
    """
    html = _read_html(BASE_DIR / "static/home.html")
    return HTMLResponse(html)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    """صفحه‌ی داشبورد اصلی (index.html)"""
    html = _read_html(BASE_DIR / "index.html")
    return HTMLResponse(html)

# ----------------------------------------------------------------------
# Helper: DB
# ----------------------------------------------------------------------


def query_db(sql: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """اجرای یک کوئری read-only و برگرداندن لیست dict."""
    conn = get_db_connection()
    try:
        cur = conn.execute(sql, params or {})
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _normalize_ts(ts: Any) -> Any:
    """
    نرمال‌کردن timestamp به فرم ISO کوتاه: YYYY-MM-DDTHH:MM:SSZ
    اگر string نباشد همان را برمی‌گردانیم.
    """
    if not isinstance(ts, str):
        return ts
    base = ts
    # جدا کردن offset
    if "+" in base:
        base = base.split("+", 1)[0]
    if "." in base:
        base = base.split(".", 1)[0]
    if base.endswith("Z"):
        return base
    return base + "Z"


# ----------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------

@app.get("/api/health")
async def health() -> JSONResponse:
    """برای چک کردن سالم بودن API و اتصال به DB."""
    db_path = str(get_db_path())
    result: Dict[str, Any] = {
        "status": "ok",
        "db_path": db_path,
        "tables": [],
    }
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        result["tables"] = [r["name"] for r in cur.fetchall()]
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return JSONResponse(result)

# ----------------------------------------------------------------------
# Prices (chart)
# ----------------------------------------------------------------------

@app.get("/api/prices")
async def api_prices(
    limit: int = Query(300, ge=10, le=5000),
) -> JSONResponse:
    """
    آخرین n کندل / قیمت برای نمودار قیمت.
    از جدول trading_logs می‌خوانیم.
    """
    rows = query_db(
        f"""
        SELECT
            timestamp,
            price,
            open,
            high,
            low,
            volume
        FROM {TABLE_NAME}
        WHERE price IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    # نرمال کردن timestampها
    for r in rows:
        r["timestamp"] = _normalize_ts(r.get("timestamp"))

    # برای نمودار، به ترتیب زمانی (قدیمی → جدید)
    rows = list(reversed(rows))
    return JSONResponse(rows)

# ----------------------------------------------------------------------
# Decisions (signals list + markers)
# ----------------------------------------------------------------------

@app.get("/api/decisions")
async def api_decisions(
    limit: int = Query(80, ge=1, le=1000),
) -> JSONResponse:
    """
    آخرین تصمیم‌های معاملاتی از trading_logs.
    فرانت انتظار دارد فیلدهایی مثل decision, price, regime, aggregate_s و ...
    """
    rows = query_db(
        f"""
        SELECT
            timestamp,
            price,
            tf,
            confirm_tf,
            decision,
            regime,
            aggregate_s,
            trend,
            momentum,
            meanrev,
            breakout,
            adx,
            atr,
            confirm_s,
            confirm_adx,
            confirm_rsi,
            reasons_json,
            regime_reasons
        FROM {TABLE_NAME}
        WHERE decision IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    for r in rows:
        r["timestamp"] = _normalize_ts(r.get("timestamp"))

    # برای هماهنگی با home.js: آرایه به صورت قدیم → جدید
    rows = list(reversed(rows))

    return JSONResponse(rows)

# ----------------------------------------------------------------------
# BTC last price + history (for sparkline)
# ----------------------------------------------------------------------

@app.get("/api/btc_price")
async def api_btc_price() -> JSONResponse:
    """
    آخرین قیمت BTC/IRT از trading_logs + history کوتاه.
    برای باکس "قیمت لحظه‌ای" و اسپارکلاین در home.js.
    """
    # 60 رکورد آخر برای history
    rows = query_db(
        f"""
        SELECT price, timestamp
        FROM {TABLE_NAME}
        WHERE price IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 60
        """
    )

    if not rows:
        return JSONResponse(
            {"price": None, "price_tmn": None, "timestamp": None, "history": []}
        )

    # نرمال‌سازی و برعکس کردن برای قدیم → جدید
    for r in rows:
        r["timestamp"] = _normalize_ts(r.get("timestamp"))

    history = list(reversed(rows))
    last = history[-1]

    return JSONResponse(
        {
            "price": last["price"],
            "price_tmn": last["price"],  # فرض: price به تومان است
            "timestamp": last["timestamp"],
            "history": history,
        }
    )

# ----------------------------------------------------------------------
# Trades (recent closed trades)
# ----------------------------------------------------------------------

@app.get("/api/trades/recent")
async def api_trades_recent(
    limit: int = Query(50, ge=1, le=1000),
) -> JSONResponse:
    """
    آخرین تریدهای بسته‌شده از trade_events.
    برای جدول 'آخرین معاملات'.
    """
    rows = query_db(
        f"""
        SELECT
            id,
            trade_id,
            timestamp,
            symbol,
            event_type,
            side,
            qty,
            entry_price,
            close_price,
            stop_price,
            pnl,
            reason
        FROM {TRADE_EVENTS_TABLE}
        WHERE event_type = 'CLOSE'
        ORDER BY timestamp DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    for r in rows:
        r["timestamp"] = _normalize_ts(r.get("timestamp"))

    return JSONResponse(rows)

# ----------------------------------------------------------------------
# Perf: Summary
# ----------------------------------------------------------------------

@app.get("/api/perf/summary")
async def api_perf_summary() -> JSONResponse:
    """
    خلاصه‌ی عملکرد ربات:
      - total_trades
      - wins
      - losses
      - winrate
      - total_pnl  (تحقق‌یافته)

    منطق:
      1) اول از trade_events WHERE event_type='CLOSE' می‌خوانیم.
      2) اگر هیچ CLOSE نبود (ترید هنوز بسته نشده)،
         - مجموع تریدهای باز را از OPEN ها می‌گیریم
         - PnL را تقریبی از account_state (equity آخر - equity اول) حساب می‌کنیم
         تا داشبورد خالی نماند.
    """
    db_path = str(get_db_path())
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # مرحله ۱: فقط تریدهای بسته‌شده
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losses,
                SUM(pnl) AS total_pnl
            FROM {TRADE_EVENTS_TABLE}
            WHERE event_type = 'CLOSE'
            """
        ).fetchone()

        total_trades = row["total_trades"] or 0
        wins = row["wins"] or 0
        losses = row["losses"] or 0
        total_pnl = float(row["total_pnl"] or 0.0)

        # اگر ترید بسته نداشتیم → fallback
        if total_trades == 0:
            # تریدهای باز
            open_count_row = conn.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM {TRADE_EVENTS_TABLE}
                WHERE event_type = 'OPEN'
                """
            ).fetchone()
            open_trades = open_count_row["cnt"] or 0

            # PnL تقریبی از account_state
            acct_rows = conn.execute(
                f"""
                SELECT equity, balance
                FROM {ACCOUNT_STATE_TABLE}
                ORDER BY id ASC
                """
            ).fetchall()

            approx_pnl = 0.0
            if acct_rows:
                start_equity = (
                    acct_rows[0]["equity"]
                    or acct_rows[0]["balance"]
                    or 0.0
                )
                last_equity = (
                    acct_rows[-1]["equity"]
                    or acct_rows[-1]["balance"]
                    or start_equity
                )
                approx_pnl = float(last_equity - start_equity)

            total_trades = int(open_trades)
            wins = 0
            losses = int(open_trades)
            total_pnl = approx_pnl

        winrate = 0.0
        if total_trades > 0:
            winrate = round(100.0 * wins / float(total_trades), 2)

        return JSONResponse(
            {
                "total_trades": int(total_trades),
                "wins": int(wins),
                "losses": int(losses),
                "winrate": winrate,
                "total_pnl": total_pnl,
            }
        )

    finally:
        conn.close()

# ----------------------------------------------------------------------
# Perf: Daily PnL
# ----------------------------------------------------------------------

@app.get("/api/perf/daily")
async def api_perf_daily(
    limit: int = Query(30, ge=1, le=365),
) -> JSONResponse:
    """
    PnL روزانه از روی trade_events (فقط CLOSE ها).
    برای نمودار/لیست PnL روزانه در داشبورد.
    فرانت انتظار دارد: day, day_pnl, n_trades
    """
    rows = query_db(
        f"""
        SELECT
            substr(timestamp, 1, 10) AS day,
            SUM(pnl) AS pnl,
            COUNT(*) AS n_trades
        FROM {TRADE_EVENTS_TABLE}
        WHERE event_type = 'CLOSE'
        GROUP BY day
        ORDER BY day DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )

    # از قدیم به جدید + اضافه کردن day_pnl برای راحتی فرانت
    rows = list(reversed(rows))
    for r in rows:
        r["day_pnl"] = r.get("pnl", 0.0)

    return JSONResponse(rows)

# =====================================================================
# SaaS: Auth Endpoints
# =====================================================================


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
async def api_auth_register(req: RegisterRequest) -> JSONResponse:
    """Register a new user. Auto-assigns FREE plan."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Check if user exists
        existing = conn.execute(
            f"SELECT id FROM {USERS_TABLE} WHERE email = ?",
            (req.email,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create user
        password_hash = hash_password(req.password)
        cursor = conn.execute(
            f"INSERT INTO {USERS_TABLE} (email, password_hash, role, is_active) VALUES (?, ?, 'USER', 1)",
            (req.email, password_hash),
        )
        user_id = cursor.lastrowid

        # Assign FREE plan
        assign_default_plan(user_id)

        # Generate token
        token = create_access_token({"sub": user_id})

        conn.commit()
        return JSONResponse({"user_id": user_id, "token": token, "email": req.email})
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        conn.close()


@app.post("/api/auth/login")
async def api_auth_login(req: LoginRequest) -> JSONResponse:
    """Login and get access token."""
    from auth import get_user_by_email, verify_password, create_access_token

    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("is_active", 0):
        raise HTTPException(status_code=401, detail="User account is inactive")

    token = create_access_token({"sub": user["id"]})
    plan = get_user_plan(user["id"])

    return JSONResponse({
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
        },
        "plan": plan.get("plan", "FREE") if plan else "FREE",
    })


@app.get("/api/auth/me")
async def api_auth_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> JSONResponse:
    """Get current user info and plan."""
    plan = get_user_plan(current_user["id"])
    return JSONResponse({
        "user": {
            "id": current_user["id"],
            "email": current_user["email"],
            "role": current_user["role"],
        },
        "plan": plan.get("plan", "FREE") if plan else "FREE",
    })


# =====================================================================
# SaaS: Insights Endpoints (Public)
# =====================================================================


@app.get("/api/insights/feed")
async def api_insights_feed(
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """Get published insights feed."""
    rows = query_db(
        f"""
        SELECT id, title, summary, sentiment, key_points, created_at
        FROM {INSIGHTS_POSTS_TABLE}
        WHERE is_published = 1
        ORDER BY created_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )
    return JSONResponse(rows)


@app.get("/api/insights/latest")
async def api_insights_latest() -> JSONResponse:
    """Get latest insights highlights."""
    rows = query_db(
        f"""
        SELECT title, summary, sentiment, key_points, created_at
        FROM {INSIGHTS_POSTS_TABLE}
        WHERE is_published = 1
        ORDER BY created_at DESC
        LIMIT 5
        """
    )
    if not rows:
        return JSONResponse({
            "highlights": [],
            "sentiment": "NEUTRAL",
            "key_points": [],
        })

    # Aggregate sentiment
    sentiments = [r.get("sentiment", "NEUTRAL") for r in rows]
    sentiment = "POSITIVE" if sentiments.count("POSITIVE") > sentiments.count("NEGATIVE") else "NEGATIVE" if sentiments.count("NEGATIVE") > 0 else "NEUTRAL"

    # Extract key points
    key_points = []
    for r in rows:
        kp = r.get("key_points")
        if kp:
            try:
                import json
                kp_list = json.loads(kp) if isinstance(kp, str) else kp
                if isinstance(kp_list, list):
                    key_points.extend(kp_list[:2])  # Max 2 per post
            except Exception:
                pass

    return JSONResponse({
        "highlights": rows[:3],
        "sentiment": sentiment,
        "key_points": key_points[:5],
    })


# =====================================================================
# SaaS: Market Endpoints (Public)
# =====================================================================


@app.get("/api/market/overview")
async def api_market_overview(
    symbol: str = Query("BTC", description="Symbol to query"),
) -> JSONResponse:
    """Get normalized market overview."""
    # Get latest candles via gateway (with provider tracking)
    gateway = MarketDataGateway()
    response = gateway.get_candles(symbol, "240", 100)
    
    if not response.data:
        logger.warning(f"Market overview failed: provider={response.provider}, error={response.error}")
        raise HTTPException(status_code=404, detail=f"Market data not available: {response.error or 'No data'}")
    
    candles = response.data
    # Log provider info for visibility
    if response.fallback_used:
        logger.info(f"Market overview used fallback provider: {response.provider} (confidence: {response.confidence:.2f})")

    latest = candles[-1]
    prices = [float(c.get("close", 0)) for c in candles if c.get("close")]

    # Compute basic metrics
    current_price = float(latest.get("close", 0))
    price_change_24h = 0.0
    if len(prices) >= 24:
        price_change_24h = ((prices[-1] - prices[-24]) / prices[-24]) * 100

    volume_24h = sum(float(c.get("volume", 0)) for c in candles[-24:])

    return JSONResponse({
        "symbol": symbol,
        "price": current_price,
        "price_change_24h": price_change_24h,
        "volume_24h": volume_24h,
        "high_24h": max(prices[-24:]) if len(prices) >= 24 else current_price,
        "low_24h": min(prices[-24:]) if len(prices) >= 24 else current_price,
        "timestamp": latest.get("time"),
    })


@app.get("/api/market/behavior")
async def api_market_behavior(
    symbol: str = Query("BTC", description="Symbol to query"),
) -> JSONResponse:
    """Get behavior score and explanations."""
    # Get market data via gateway (with provider tracking)
    gateway = MarketDataGateway()
    response = gateway.get_candles(symbol, "240", 100)
    
    if not response.data:
        logger.warning(f"Market behavior failed: provider={response.provider}, error={response.error}")
        raise HTTPException(status_code=404, detail=f"Market data not available: {response.error or 'No data'}")
    
    candles = response.data
    # Log provider info for visibility
    if response.fallback_used:
        logger.info(f"Market behavior used fallback provider: {response.provider} (confidence: {response.confidence:.2f})")

    # Extract volumes and prices
    volumes = [float(c.get("volume", 0.0)) for c in candles]
    prices = [float(c.get("close", 0.0)) for c in candles if c.get("close")]

    # Compute behavior score
    behavior = compute_behavior_score(symbol, candles, volumes, None)

    return JSONResponse(behavior)


# =====================================================================
# SaaS: App Endpoints (Auth Required)
# =====================================================================


@app.get("/api/app/me/summary")
async def api_app_me_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> JSONResponse:
    """Get user summary: plan, symbols, alert status, etc."""
    plan = get_user_plan(current_user["id"])

    # Get user's recent activity (placeholder)
    # In future: track user's watched symbols, alerts, etc.

    return JSONResponse({
        "user_id": current_user["id"],
        "email": current_user["email"],
        "plan": plan.get("plan", "FREE") if plan else "FREE",
        "plan_expires_at": plan.get("ends_at") if plan else None,
        "symbols": ["BTC"],  # Placeholder
        "alerts_enabled": plan.get("plan") in ("PRO", "PROFESSIONAL") if plan else False,
    })


# =====================================================================
# SaaS: Admin Endpoints
# =====================================================================


class SetPlanRequest(BaseModel):
    plan: str
    duration_days: Optional[int] = None


@app.post("/api/admin/users/{user_id}/plan")
async def api_admin_set_plan(
    user_id: int,
    req: SetPlanRequest,
    admin_user: Dict[str, Any] = Depends(require_admin),
) -> JSONResponse:
    """Admin endpoint to set user plan."""
    success = set_user_plan(user_id, req.plan, req.duration_days)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set user plan")
    return JSONResponse({"user_id": user_id, "plan": req.plan, "status": "updated"})
