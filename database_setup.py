# database_setup.py
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
import json
import datetime as dt

# ================================================================
# Logger
# ================================================================
db_logger = logging.getLogger(__name__)

# ================================================================
# Constants
# ================================================================
DB_NAME = "trading_data.db"

# اصلی‌ترین جدول لاگ تحلیل
TABLE_NAME = "trading_logs"

# جدول لاگ تریدها (OPEN/CLOSE)
TRADE_EVENTS_TABLE = "trade_events"

# جدول وضعیت حساب
ACCOUNT_STATE_TABLE = "account_state"

# ================================================================
# Database Path / Connection
# ================================================================
def get_db_path() -> Path:
    return Path(__file__).parent / DB_NAME


def get_db_connection() -> Optional[sqlite3.Connection]:
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        db_logger.error(f"Database connection error: {e}")
        return None


# ================================================================
# Canonical schema for trading_logs table
# ================================================================
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

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    {", ".join([f"{n} {t}" for n, t in REQUIRED_COLUMNS.items()])}
);
"""


# ================================================================
# Schemas for trade events & account snapshots
# ================================================================
TRADE_EVENTS_COLS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "trade_id": "TEXT",  # 👈 هر ترید یک شناسه ثابت دارد
    "timestamp": "TEXT NOT NULL",
    "symbol": "TEXT NOT NULL",
    "event_type": "TEXT NOT NULL",      # OPEN / CLOSE / ...
    "side": "TEXT",
    "qty": "REAL",
    "entry_price": "REAL",
    "close_price": "REAL",
    "stop_price": "REAL",
    "pnl": "REAL",
    "reason": "TEXT",
}

ACCOUNT_STATE_COLS = {
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


# ================================================================
# Helpers
# ================================================================
def _ensure_table(conn: sqlite3.Connection, table: str, cols: Dict[str, str]):
    cols_sql = ", ".join([f"{k} {v}" for k, v in cols.items()])
    sql = f"CREATE TABLE IF NOT EXISTS {table} ({cols_sql});"
    conn.execute(sql)


def _get_existing_columns(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({TABLE_NAME});").fetchall()
    return [r["name"] for r in rows]


def _add_missing_columns(conn: sqlite3.Connection, existing: List[str]):
    for col, ctype in REQUIRED_COLUMNS.items():
        if col not in existing:
            db_logger.info(f"Adding missing column: {col}")
            conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {ctype};")


# ================================================================
# Schema Initialization (main)
# ================================================================
def ensure_schema() -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        # جدول اصلی لاگ تحلیل
        conn.execute(CREATE_TABLE_SQL)
        existing = _get_existing_columns(conn)
        _add_missing_columns(conn, existing)

        # جدول ترید
        _ensure_table(conn, TRADE_EVENTS_TABLE, TRADE_EVENTS_COLS)

        # جدول وضعیت حساب
        _ensure_table(conn, ACCOUNT_STATE_TABLE, ACCOUNT_STATE_COLS)

        conn.commit()
        return True

    except sqlite3.Error as e:
        db_logger.error(f"Schema ensure error: {e}")
        return False

    finally:
        conn.close()


# ================================================================
# Insert functions
# ================================================================
def insert_trade_event(event: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cols = [c for c in TRADE_EVENTS_COLS if c != "id"]
        data = {c: event.get(c) for c in cols}

        sql = f"""
            INSERT INTO {TRADE_EVENTS_TABLE} ({", ".join(cols)})
            VALUES ({", ".join(":"+c for c in cols)})
        """

        conn.execute(sql, data)
        conn.commit()
        return True

    except sqlite3.Error as e:
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
        data = {c: state.get(c) for c in cols}

        sql = f"""
            INSERT INTO {ACCOUNT_STATE_TABLE} ({", ".join(cols)})
            VALUES ({", ".join(":"+c for c in cols)})
        """

        conn.execute(sql, data)
        conn.commit()
        return True

    except sqlite3.Error as e:
        db_logger.error(f"upsert_account_state error: {e}")
        return False

    finally:
        conn.close()


# ================================================================
# Insert trading_log
# ================================================================
def insert_trading_log(row: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        existing_cols = _get_existing_columns(conn)

        filtered = {
            k: row.get(k, None)
            for k in existing_cols
            if k in REQUIRED_COLUMNS
        }

        if "reasons_json" in filtered and isinstance(filtered["reasons_json"], list):
            filtered["reasons_json"] = json.dumps(filtered["reasons_json"], ensure_ascii=False)

        for g in ("trend_gated", "momentum_gated", "meanrev_gated", "breakout_gated"):
            if g in filtered and filtered[g] is not None:
                filtered[g] = 1 if bool(filtered[g]) else 0

        sql = f"""
            INSERT INTO {TABLE_NAME} ({", ".join(filtered.keys())})
            VALUES ({", ".join(":"+k for k in filtered.keys())})
        """

        conn.execute(sql, filtered)
        conn.commit()
        return True

    except sqlite3.Error as e:
        db_logger.error(f"insert_trading_log error: {e}")
        return False

    finally:
        conn.close()


# ================================================================
# dc_to_row
# ================================================================
def dc_to_row(
    decision: str,
    dc_primary: Any,
    dc_confirm: Optional[Any],
    tf: Optional[str],
    confirm_tf: Optional[str],
    pos_size: Optional[float] = None,
    risk_amount: Optional[float] = None,
    tp_price: Optional[float] = None,
    fingerprint: Optional[str] = None,
    regime_reasons: Optional[str] = None,
) -> Dict[str, Any]:

    def reason_has(substr: str) -> int:
        reasons = getattr(dc_primary, "reasons", None)
        return 1 if reasons and any(substr in r for r in reasons) else 0

    return {
        "timestamp": getattr(dc_primary, "timestamp", None)
        or dt.datetime.utcnow().isoformat(),

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
        "stop_price": getattr(getattr(dc_primary, "planned_position", None), "stop_price", None)
                        or getattr(dc_primary, "stop_price", None),
        "tp_price": tp_price,
        "pos_size": pos_size,
        "risk_amount": risk_amount,

        "trend_gated": reason_has("Trend gated"),
        "momentum_gated": reason_has("Momentum gated"),
        "meanrev_gated": reason_has("Mean-reversion gated"),
        "breakout_gated": reason_has("Breakout gated"),

        "fingerprint": fingerprint,
    }
