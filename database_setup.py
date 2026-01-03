import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import os


db_logger = logging.getLogger(__name__)

# =====================================================================
# مسیر دیتابیس (ثابت و مطمئن)
# =====================================================================


# =====================================================================
# مسیر دیتابیس (قابل تنظیم با ENV)
# =====================================================================

_DEFAULT_DB = "/root/smart-trader/trading_data.db"  # رفتار قبلی (prod)

def get_db_path() -> Path:
    """
    مسیر دیتابیس که هم bot هم API باید ازش استفاده کنند.
    - اگر SMARTTRADER_DB_PATH ست شده باشد، همان استفاده می‌شود.
    - در غیر این صورت، مسیر پیش‌فرض (رفتار قبلی) حفظ می‌شود.
    """
    return Path(os.getenv("SMARTTRADER_DB_PATH", _DEFAULT_DB))


def get_db_connection() -> Optional[sqlite3.Connection]:
    """
    اتصال امن به SQLite با row_factory = Row
    """
    try:
        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        db_logger.error(f"DB connection error: {e}")
        return None


# =====================================================================
# جدول اصلی لاگ تحلیل
# =====================================================================

TABLE_NAME = "trading_logs"

REQUIRED_COLUMNS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "timestamp": "TEXT NOT NULL",

    "open": "REAL",
    "high": "REAL",
    "low": "REAL",
    "price": "REAL NOT NULL",
    "volume": "REAL",

    "tf": "TEXT",
    "confirm_tf": "TEXT",

    "trend_raw": "REAL",
    "momentum_raw": "REAL",
    "meanrev_raw": "REAL",
    "breakout_raw": "REAL",

    "adx": "REAL",
    "atr": "REAL",

    "trend": "REAL",
    "momentum": "REAL",
    "meanrev": "REAL",
    "breakout": "REAL",
    "aggregate_s": "REAL",

    "confirm_s": "REAL",
    "confirm_adx": "REAL",
    "confirm_rsi": "REAL",

    "decision": "TEXT",
    "regime": "TEXT",
    "reasons_json": "TEXT",
    "regime_reasons": "TEXT",

    "stop_price": "REAL",
    "tp_price": "REAL",
    "pos_size": "REAL",
    "risk_amount": "REAL",

    "trend_gated": "INTEGER",
    "momentum_gated": "INTEGER",
    "meanrev_gated": "INTEGER",
    "breakout_gated": "INTEGER",

    "fingerprint": "TEXT",
}

# =====================================================================
# جدول ترید (OPEN/CLOSE)
# =====================================================================

TRADE_EVENTS_TABLE = "trade_events"

TRADE_EVENTS_COLS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "trade_id": "TEXT",
    "timestamp": "TEXT NOT NULL",
    "symbol": "TEXT NOT NULL",
    "event_type": "TEXT NOT NULL",  # OPEN / CLOSE / BE_BREAK / TP / SL ...
    "side": "TEXT",
    "qty": "REAL",
    "entry_price": "REAL",
    "close_price": "REAL",
    "stop_price": "REAL",
    "pnl": "REAL",
    "reason": "TEXT",
}

# =====================================================================
# جدول وضعیت حساب
# =====================================================================

ACCOUNT_STATE_TABLE = "account_state"

ACCOUNT_STATE_COLS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "timestamp": "TEXT NOT NULL",
    "symbol": "TEXT NOT NULL",
    "equity": "REAL",
    "balance": "REAL",
    "position_side": "TEXT",
    "position_qty": "REAL",
    "position_entry": "REAL",
    "position_stop": "REAL",
}

# =====================================================================
# SaaS Tables: Users, Plans, Insights
# =====================================================================

USERS_TABLE = "users"

USERS_COLS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "email": "TEXT UNIQUE NOT NULL",
    "password_hash": "TEXT NOT NULL",
    "role": "TEXT NOT NULL DEFAULT 'USER'",
    "is_active": "INTEGER NOT NULL DEFAULT 1",
    "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
}

USER_PLANS_TABLE = "user_plans"

USER_PLANS_COLS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "user_id": "INTEGER NOT NULL",
    "plan": "TEXT NOT NULL",
    "starts_at": "TEXT NOT NULL",
    "ends_at": "TEXT",
    "is_active": "INTEGER NOT NULL DEFAULT 1",
    "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
}

INSIGHTS_POSTS_TABLE = "insights_posts"

INSIGHTS_POSTS_COLS: Dict[str, str] = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "title": "TEXT NOT NULL",
    "content": "TEXT NOT NULL",
    "summary": "TEXT",
    "sentiment": "TEXT",
    "key_points": "TEXT",
    "author_id": "INTEGER",
    "is_published": "INTEGER NOT NULL DEFAULT 1",
    "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
    "updated_at": "TEXT",
}

# =====================================================================
# Helpers داخلی
# =====================================================================

def _existing_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return [r["name"] for r in rows]


def _create_table(conn: sqlite3.Connection, table: str, cols: Dict[str, str]) -> None:
    cols_sql = ", ".join([f"{k} {v}" for k, v in cols.items()])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols_sql});")


def _migrate_table(conn: sqlite3.Connection, table: str, cols: Dict[str, str]) -> None:
    existing = _existing_columns(conn, table)
    for col, ctype in cols.items():
        if col not in existing:
            db_logger.warning(f"[MIGRATE] Adding missing column: {table}.{col}")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype};")


# =====================================================================
# Public: Ensure Schema (FULL MIGRATION)
# =====================================================================

def ensure_schema() -> bool:
    """
    ساخت/آپدیت ۳ جدول اصلی:
      - trading_logs
      - trade_events
      - account_state
    بدون حذف هیچ دیتایی (فقط ADD COLUMN در صورت لزوم)
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        # trading_logs
        _create_table(conn, TABLE_NAME, REQUIRED_COLUMNS)
        _migrate_table(conn, TABLE_NAME, REQUIRED_COLUMNS)

        # trade_events
        _create_table(conn, TRADE_EVENTS_TABLE, TRADE_EVENTS_COLS)
        _migrate_table(conn, TRADE_EVENTS_TABLE, TRADE_EVENTS_COLS)

        # account_state
        _create_table(conn, ACCOUNT_STATE_TABLE, ACCOUNT_STATE_COLS)
        _migrate_table(conn, ACCOUNT_STATE_TABLE, ACCOUNT_STATE_COLS)

        # SaaS tables
        _create_table(conn, USERS_TABLE, USERS_COLS)
        _migrate_table(conn, USERS_TABLE, USERS_COLS)

        _create_table(conn, USER_PLANS_TABLE, USER_PLANS_COLS)
        _migrate_table(conn, USER_PLANS_TABLE, USER_PLANS_COLS)

        _create_table(conn, INSIGHTS_POSTS_TABLE, INSIGHTS_POSTS_COLS)
        _migrate_table(conn, INSIGHTS_POSTS_TABLE, INSIGHTS_POSTS_COLS)

        conn.commit()
        return True

    except Exception as e:
        db_logger.error(f"Schema initialization failed: {e}")
        return False

    finally:
        conn.close()


# =====================================================================
# Insert Operations
# =====================================================================

def insert_trade_event(event: Dict[str, Any]) -> bool:
    """
    درج یک رکورد در trade_events (OPEN / CLOSE / ...)
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cols = [c for c in TRADE_EVENTS_COLS if c != "id"]
        data = {c: event.get(c) for c in cols}

        sql = f"""
            INSERT INTO {TRADE_EVENTS_TABLE}
            ({", ".join(cols)})
            VALUES ({", ".join(":"+c for c in cols)})
        """

        conn.execute(sql, data)
        conn.commit()
        return True

    except Exception as e:
        db_logger.error(f"insert_trade_event error: {e}")
        return False

    finally:
        conn.close()


def upsert_account_state(state: Dict[str, Any]) -> bool:
    """
    فعلاً به صورت append عمل می‌کند؛ آخرین رکورد وضعیت فعلی حساب است.
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cols = [c for c in ACCOUNT_STATE_COLS if c != "id"]
        sql = f"""
            INSERT INTO {ACCOUNT_STATE_TABLE}
            ({", ".join(cols)})
            VALUES ({", ".join(":"+c for c in cols)})
        """
        conn.execute(sql, {c: state.get(c) for c in cols})
        conn.commit()
        return True

    except Exception as e:
        db_logger.error(f"upsert_account_state error: {e}")
        return False

    finally:
        conn.close()


def insert_trading_log(row: Dict[str, Any]) -> bool:
    """
    درج یک سطر از لاگ تحلیل (DecisionContext → Row)
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        existing = _existing_columns(conn, TABLE_NAME)
        filtered = {k: row.get(k) for k in existing}

        if isinstance(filtered.get("reasons_json"), list):
            filtered["reasons_json"] = json.dumps(filtered["reasons_json"], ensure_ascii=False)

        cols = ", ".join(filtered.keys())
        vals = ", ".join(":"+k for k in filtered.keys())

        conn.execute(f"INSERT INTO {TABLE_NAME} ({cols}) VALUES ({vals})", filtered)
        conn.commit()
        return True

    except Exception as e:
        db_logger.error(f"insert_trading_log error: {e}")
        return False

    finally:
        conn.close()


# =====================================================================
# Convert DecisionContext → DB Row  (USED BY main.py)
# =====================================================================

def dc_to_row(
    decision: str,
    dc_primary,
    dc_confirm,
    tf: str,
    confirm_tf: str,
    pos_size=None,
    risk_amount=None,
    tp_price=None,
    fingerprint=None,
    regime_reasons=None,
) -> Dict[str, Any]:
    """
    تبدیل DecisionContext اصلی و confirm به یک dict مناسب برای insert_trading_log
    Includes VSA fingerprint and whale bias in fingerprint, stores whale override reasons.
    """

    def reason_has(txt: str) -> int:
        try:
            return 1 if any(txt in r for r in getattr(dc_primary, "reasons", []) or []) else 0
        except Exception:
            return 0
    
    # Extract behavior details for VSA and whale bias
    behavior_details = getattr(dc_primary, "behavior_details", None)
    vsa_fingerprint = None
    whale_bias = None
    whale_override_reasons = []
    
    if behavior_details and isinstance(behavior_details, dict):
        vsa_score = behavior_details.get("vsa_absorption_score", 0.0)
        vsa_signal = behavior_details.get("vsa_signal", "NORMAL")
        whale_bias = behavior_details.get("whale_bias", 0.0)
        whale_direction = behavior_details.get("whale_direction", "NEUTRAL")
        supply_overcoming = behavior_details.get("supply_overcoming_demand", False)
        rvol = behavior_details.get("rvol", 1.0)
        
        # Create VSA fingerprint component
        vsa_fingerprint = f"VSA:{vsa_score:.1f}:{vsa_signal[:3]}:WB:{whale_bias:.2f}:RVOL:{rvol:.2f}"
        
        # Check if whale gating occurred (check reasons for WHALE_GATE)
        reasons = getattr(dc_primary, "reasons", []) or []
        for reason in reasons:
            if "WHALE_GATE" in reason:
                whale_override_reasons.append(reason)
        
        # Add whale context to reasons if supply overcoming demand
        if supply_overcoming:
            whale_override_reasons.append(
                f"Whale context: supply_overcoming_demand=True, "
                f"whale_bias={whale_bias:.3f}, whale_direction={whale_direction}"
            )
    
    # Combine reasons with whale override reasons
    all_reasons = list(getattr(dc_primary, "reasons", []) or [])
    if whale_override_reasons:
        all_reasons.extend(whale_override_reasons)
    
    # Enhance fingerprint with VSA data if available
    enhanced_fingerprint = fingerprint
    if vsa_fingerprint and fingerprint:
        enhanced_fingerprint = f"{fingerprint}|{vsa_fingerprint}"
    elif vsa_fingerprint:
        enhanced_fingerprint = vsa_fingerprint

    return {
        "timestamp": getattr(dc_primary, "timestamp", None),
        "open": getattr(dc_primary, "open", None),
        "high": getattr(dc_primary, "high", None),
        "low": getattr(dc_primary, "low", None),
        "price": getattr(dc_primary, "price", None),
        "volume": getattr(dc_primary, "volume", None),

        "tf": tf,
        "confirm_tf": confirm_tf,

        "trend_raw": getattr(dc_primary, "trend_raw", None),
        "momentum_raw": getattr(dc_primary, "momentum_raw", None),
        "meanrev_raw": getattr(dc_primary, "meanrev_raw", None),
        "breakout_raw": getattr(dc_primary, "breakout_raw", None),

        "adx": getattr(dc_primary, "adx", None),
        "atr": getattr(dc_primary, "atr", None),

        "trend": getattr(dc_primary, "trend", None),
        "momentum": getattr(dc_primary, "momentum", None),
        "meanrev": getattr(dc_primary, "meanrev", None),
        "breakout": getattr(dc_primary, "breakout", None),
        "aggregate_s": getattr(dc_primary, "aggregate_s", None),

        "confirm_s": getattr(dc_confirm, "aggregate_s", None) if dc_confirm else None,
        "confirm_adx": getattr(dc_confirm, "adx", None) if dc_confirm else None,
        "confirm_rsi": getattr(dc_confirm, "rsi", None) if dc_confirm else None,

        "decision": decision,
        "regime": getattr(dc_primary, "regime", None),
        "reasons_json": all_reasons,  # Includes whale override reasons
        "regime_reasons": regime_reasons,

        "stop_price": getattr(getattr(dc_primary, "planned_position", None), "stop_price", None),
        "tp_price": tp_price,
        "pos_size": pos_size,
        "risk_amount": risk_amount,

        "trend_gated": reason_has("Trend gated"),
        "momentum_gated": reason_has("Momentum gated"),
        "meanrev_gated": reason_has("Mean-reversion gated"),
        "breakout_gated": reason_has("Breakout gated"),

        "fingerprint": enhanced_fingerprint,  # Includes VSA fingerprint and whale bias
    }
