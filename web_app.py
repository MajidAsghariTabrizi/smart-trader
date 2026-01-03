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


@app.get("/insights", response_class=HTMLResponse)
async def insights_page() -> HTMLResponse:
    """Command Center dashboard (insights.html)"""
    html = _read_html(BASE_DIR / "static" / "pages" / "insights.html")
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
    # Optimized: Return {"status":"ok"} immediately for deployment health checks
    try:
        db_path = str(get_db_path())
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r["name"] for r in cur.fetchall()]
        conn.close()
        return JSONResponse({"status": "ok", "db_path": db_path, "tables": tables})
    except Exception as e:
        # Still return ok status to avoid deployment failures
        logger.error(f"Health check error: {e}")
        return JSONResponse({"status": "ok", "error": str(e)})

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
    Latest BTC/USDT price from trading_logs + short history.
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
            {"price": None, "price_usdt": None, "timestamp": None, "history": []}
        )

    # نرمال‌سازی و برعکس کردن برای قدیم → جدید
    for r in rows:
        r["timestamp"] = _normalize_ts(r.get("timestamp"))

    history = list(reversed(rows))
    last = history[-1]

    return JSONResponse(
        {
            "price": last["price"],
            "price_usdt": last["price"],  # Price in USDT/USD
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
    behavior = compute_behavior_score(symbol, candles)

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


# =====================================================================
# Command Center: Full Bot Brain Visualization
# =====================================================================

@app.get("/api/insights/command-center")
async def api_command_center() -> JSONResponse:
    """
    Comprehensive Command Center endpoint returning:
    - Latest decision with VSA/whale data
    - Dynamic weights based on current regime
    - Market regime and regime_scale
    - Price data with VSA markers
    - Relative volume data
    - Latest reasons_json for Live Logic Feed
    """
    import json
    from config import STRATEGY
    
    # Get latest decision with all fields
    latest_row = query_db(
        f"""
        SELECT
            timestamp, price, decision, regime, aggregate_s,
            trend, momentum, meanrev, breakout,
            trend_raw, momentum_raw, meanrev_raw, breakout_raw,
            adx, atr, confirm_s, confirm_adx,
            reasons_json, behavior_json, behavior_bias, behavior_score,
            volume, open, high, low
        FROM {TABLE_NAME}
        WHERE decision IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1
        """
    )
    
    if not latest_row:
        return JSONResponse({
            "error": "No decisions found",
            "whale_bias": 0.0,
            "vsa_signal": "NO_DATA",
            "supply_overcoming_demand": False,
            "current_regime": "NEUTRAL",
            "regime_scale": 1.0,
            "dynamic_weights": {},
            "latest_decision": None,
        })
    
    latest = latest_row[0]
    
    # Parse behavior_json
    behavior_details = {}
    whale_bias = 0.0
    vsa_signal = "NO_DATA"
    supply_overcoming_demand = False
    rvol = 1.0
    
    behavior_json_str = latest.get("behavior_json")
    if behavior_json_str:
        try:
            behavior_details = json.loads(behavior_json_str) if isinstance(behavior_json_str, str) else behavior_json_str
            whale_bias = float(behavior_details.get("whale_bias", 0.0))
            vsa_signal = behavior_details.get("vsa_signal", "NO_DATA")
            supply_overcoming_demand = bool(behavior_details.get("supply_overcoming_demand", False))
            rvol = float(behavior_details.get("rvol", 1.0))
        except Exception as e:
            logger.warning(f"Failed to parse behavior_json: {e}")
    
    # Calculate dynamic weights based on regime (same logic as trading_logic.py)
    regime = latest.get("regime", "NEUTRAL")
    base_weights = STRATEGY["weights"].copy()
    
    # Normalize base weights
    total = sum(base_weights.values())
    if total > 0:
        normalized = {k: v / total for k, v in base_weights.items()}
    else:
        normalized = base_weights
    
    # Apply regime-specific adjustments
    if regime == "LOW":
        normalized["meanrev"] *= 1.4
        normalized["trend"] *= 0.7
        normalized["breakout"] *= 0.8
    elif regime == "HIGH":
        normalized["breakout"] *= 1.3
        normalized["behavior"] *= 1.2
        normalized["meanrev"] *= 0.6
        normalized["trend"] *= 1.1
    
    # Renormalize after adjustments
    total = sum(normalized.values())
    if total > 0:
        normalized = {k: v / total for k, v in normalized.items()}
    
    # Get regime_scale
    regime_scale = STRATEGY["regime_scale"].get(regime, 1.0)
    
    # Parse reasons_json
    reasons = []
    reasons_json_str = latest.get("reasons_json")
    if reasons_json_str:
        try:
            reasons = json.loads(reasons_json_str) if isinstance(reasons_json_str, str) else reasons_json_str
            if not isinstance(reasons, list):
                reasons = [str(reasons)]
        except Exception:
            reasons = []
    
    # Get price history with VSA markers (last 200 candles)
    price_history = query_db(
        f"""
        SELECT
            timestamp, price, open, high, low, volume,
            behavior_json
        FROM {TABLE_NAME}
        WHERE price IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 200
        """
    )
    
    # Process price history with VSA markers
    candles_with_vsa = []
    rvol_data = []
    
    for candle in reversed(price_history):  # Oldest to newest
        candle_vsa = {
            "timestamp": _normalize_ts(candle.get("timestamp")),
            "price": float(candle.get("price", 0)),
            "open": float(candle.get("open", 0)),
            "high": float(candle.get("high", 0)),
            "low": float(candle.get("low", 0)),
            "volume": float(candle.get("volume", 0)),
            "vsa_signal": "NORMAL",
            "whale_footprint": None,
        }
        
        # Parse behavior_json for this candle
        candle_behavior_json = candle.get("behavior_json")
        if candle_behavior_json:
            try:
                candle_behavior = json.loads(candle_behavior_json) if isinstance(candle_behavior_json, str) else candle_behavior_json
                candle_vsa["vsa_signal"] = candle_behavior.get("vsa_signal", "NORMAL")
                candle_whale_bias = float(candle_behavior.get("whale_bias", 0.0))
                
                # Mark whale footprints (Absorption or Effort vs Result)
                if candle_vsa["vsa_signal"] == "ABSORPTION":
                    candle_vsa["whale_footprint"] = "ABSORPTION"
                elif candle_vsa["vsa_signal"] == "DISTRIBUTION":
                    candle_vsa["whale_footprint"] = "DISTRIBUTION"
                
                # Add RVOL data
                candle_rvol = float(candle_behavior.get("rvol", 1.0))
                rvol_data.append({
                    "timestamp": candle_vsa["timestamp"],
                    "rvol": candle_rvol,
                })
            except Exception:
                pass
        
        candles_with_vsa.append(candle_vsa)
    
    # Calculate average RVOL for comparison
    avg_rvol = sum(d["rvol"] for d in rvol_data) / len(rvol_data) if rvol_data else 1.0
    
    return JSONResponse({
        "latest_decision": {
            "timestamp": _normalize_ts(latest.get("timestamp")),
            "price": float(latest.get("price", 0)),
            "decision": latest.get("decision", "HOLD"),
            "regime": regime,
            "aggregate_s": float(latest.get("aggregate_s", 0.0)),
            "trend": float(latest.get("trend", 0.0)),
            "momentum": float(latest.get("momentum", 0.0)),
            "meanrev": float(latest.get("meanrev", 0.0)),
            "breakout": float(latest.get("breakout", 0.0)),
            "adx": float(latest.get("adx", 0.0)),
            "atr": float(latest.get("atr", 0.0)),
        },
        "whale_bias": whale_bias,
        "vsa_signal": vsa_signal,
        "supply_overcoming_demand": supply_overcoming_demand,
        "rvol": rvol,
        "current_regime": regime,
        "regime_scale": regime_scale,
        "dynamic_weights": {
            "trend": float(normalized.get("trend", 0.0)),
            "momentum": float(normalized.get("momentum", 0.0)),
            "meanrev": float(normalized.get("meanrev", 0.0)),
            "breakout": float(normalized.get("breakout", 0.0)),
            "behavior": float(normalized.get("behavior", 0.0)),
        },
        "reasons": reasons,
        "price_history": candles_with_vsa,
        "rvol_history": rvol_data,
        "avg_rvol": avg_rvol,
        "behavior_details": behavior_details,
    })


# =====================================================================
# Intelligence: Market DNA Summary (ADX, ATR, Regime)
# =====================================================================


@app.get("/api/intelligence/summary")
async def api_intelligence_summary() -> JSONResponse:
    """
    Aggregate ADX, ATR, and Regime data from last 100 trading_logs records.
    Returns market DNA summary for intelligence dashboard.
    """
    rows = query_db(
        f"""
        SELECT
            adx,
            atr,
            regime,
            aggregate_s,
            decision,
            timestamp
        FROM {TABLE_NAME}
        WHERE adx IS NOT NULL AND atr IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 100
        """
    )

    if not rows:
        return JSONResponse({
            "adx_avg": 0.0,
            "adx_latest": 0.0,
            "atr_avg": 0.0,
            "atr_latest": 0.0,
            "regime_distribution": {},
            "trend_strength": 0.0,
            "volatility_shift": 0.0,
        })

    # Calculate averages and latest
    adx_values = [float(r.get("adx", 0)) for r in rows if r.get("adx")]
    atr_values = [float(r.get("atr", 0)) for r in rows if r.get("atr")]

    latest = rows[0] if rows else {}
    adx_latest = float(latest.get("adx", 0))
    atr_latest = float(latest.get("atr", 0))

    # Regime distribution
    regime_counts = {}
    for r in rows:
        regime = r.get("regime", "NEUTRAL")
        regime_counts[regime] = regime_counts.get(regime, 0) + 1

    # Volatility shift: compare latest ATR to average
    atr_avg = sum(atr_values) / len(atr_values) if atr_values else 0.0
    volatility_shift = ((atr_latest / atr_avg) - 1.0) * 100 if atr_avg > 0 else 0.0

    # Trend strength: ADX normalized (0-100 scale, assuming max ADX ~50)
    trend_strength = min(100.0, (adx_latest / 50.0) * 100) if adx_latest else 0.0

    return JSONResponse({
        "adx_avg": sum(adx_values) / len(adx_values) if adx_values else 0.0,
        "adx_latest": adx_latest,
        "atr_avg": atr_avg,
        "atr_latest": atr_latest,
        "regime_distribution": regime_counts,
        "trend_strength": trend_strength,
        "volatility_shift": volatility_shift,
        "latest_regime": latest.get("regime", "NEUTRAL"),
        "latest_decision": latest.get("decision", "HOLD"),
    })

