import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import datetime as dt

db_logger = logging.getLogger(__name__)

DB_NAME = "trading_data.db"

# =====================================================================
# جدول اصلی لاگ تحلیل
# =====================================================================
TABLE_NAME = "trading_logs"

REQUIRED_COLUMNS = {
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

    "fingerprint": "TEXT"
}

# =====================================================================
# جدول ترید (OPEN/CLOSE)
# =====================================================================
TRADE_EVENTS_TABLE = "trade_events"

TRADE_EVENTS_COLS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "trade_id": "TEXT",
    "timestamp": "TEXT NOT NULL",
    "symbol": "TEXT NOT NULL",
    "event_type": "TEXT NOT NULL",
    "side": "TEXT",
    "qty": "REAL",
    "entry_price": "REAL",
    "close_price": "REAL",
    "stop_price": "REAL",
    "pnl": "REAL",
    "reason": "TEXT"
}

# =====================================================================
# جدول وضعیت حساب
# =====================================================================
ACCOUNT_STATE_TABLE = "account_state"

ACCOUNT_STATE_COLS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "timestamp": "TEXT NOT NULL",
    "symbol": "TEXT NOT NULL",
    "equity": "REAL",
    "balance": "REAL",
    "position_side": "TEXT",
    "position_qty": "REAL",
    "position_entry": "REAL",
    "position_stop": "REAL"
}

# =====================================================================
# Helpers
# =====================================================================

def get_db_path() -> Path:
    return Path(__file__).parent / DB_NAME


def get_db_connection() -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        db_logger.error(f"DB connection error: {e}")
        return None


def _existing_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return [r["name"] for r in rows]


def _create_table(conn: sqlite3.Connection, table: str, cols: Dict[str, str]):
    cols_sql = ", ".join([f"{k} {v}" for k, v in cols.items()])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols_sql});")


def _migrate_table(conn: sqlite3.Connection, table: str, cols: Dict[str, str]):
    existing = _existing_columns(conn, table)
    for col, ctype in cols.items():
        if col not in existing:
            db_logger.warning(f"[MIGRATE] Adding missing column: {table}.{col}")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype};")


# =====================================================================
# Public: Ensure Schema (FULL MIGRATION)
# =====================================================================

def ensure_schema() -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        _create_table(conn, TABLE_NAME, REQUIRED_COLUMNS)
        _migrate_table(conn, TABLE_NAME, REQUIRED_COLUMNS)

        _create_table(conn, TRADE_EVENTS_TABLE, TRADE_EVENTS_COLS)
        _migrate_table(conn, TRADE_EVENTS_TABLE, TRADE_EVENTS_COLS)

        _create_table(conn, ACCOUNT_STATE_TABLE, ACCOUNT_STATE_COLS)
        _migrate_table(conn, ACCOUNT_STATE_TABLE, ACCOUNT_STATE_COLS)

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
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cols = [c for c in ACCOUNT_STATE_COLS if c != "id"]
        sql = f"""
            INSERT INTO {ACCOUNT_STATE_TABLE} 
            ({", ".join(cols)}) 
            VALUES ({", ".join(":"+c for c in cols)});
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
):
    def reason_has(txt):
        try:
            return 1 if any(txt in r for r in dc_primary.reasons) else 0
        except:
            return 0

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
        "reasons_json": getattr(dc_primary, "reasons", None),
        "regime_reasons": regime_reasons,

        "stop_price": getattr(getattr(dc_primary, "planned_position", None), "stop_price", None),
        "tp_price": tp_price,
        "pos_size": pos_size,
        "risk_amount": risk_amount,

        "trend_gated": reason_has("Trend gated"),
        "momentum_gated": reason_has("Momentum gated"),
        "meanrev_gated": reason_has("Mean-reversion gated"),
        "breakout_gated": reason_has("Breakout gated"),

        "fingerprint": fingerprint,
    }
