# ========================================================================
# database_setup.py  (FULL FIXED + REAL MIGRATION SUPPORT)
# ========================================================================

import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
import json
import datetime as dt

db_logger = logging.getLogger(__name__)

DB_NAME = "trading_data.db"

TABLE_NAME = "trading_logs"
TRADE_EVENTS_TABLE = "trade_events"
ACCOUNT_STATE_TABLE = "account_state"

def get_db_path() -> Path:
    return Path(__file__).parent / DB_NAME


def get_db_connection() -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        db_logger.error(f"DB connection error: {e}")
        return None


# ================================================================
# CANONICAL SCHEMAS
# ================================================================

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

    "fingerprint": "TEXT",
}

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
# MIGRATION HELPERS
# ================================================================

def _existing_columns(conn, table_name: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    return [r["name"] for r in rows]


def _migrate_table(conn, table: str, schema: Dict[str, str]):
    """Add missing columns to a table without destroying data."""
    existing = _existing_columns(conn, table)

    for col, ctype in schema.items():
        if col not in existing:
            db_logger.warning(f"[MIGRATE] Adding missing column: {table}.{col}")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype};")


def _create_table(conn, table: str, schema: Dict[str, str]):
    cols = ", ".join([f"{k} {v}" for k, v in schema.items()])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols});")


# ================================================================
# MAIN: ENSURE SCHEMA
# ================================================================
def ensure_schema() -> bool:
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

        conn.commit()
        return True

    except Exception as e:
        db_logger.error(f"ensure_schema error: {e}")
        return False

    finally:
        conn.close()


# ================================================================
# INSERT OPERATIONS
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
            INSERT INTO {ACCOUNT_STATE_TABLE} ({", ".join(cols)})
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
    conn = get_db_connection()
    if not conn:
        return False
    try:
        schema_cols = _existing_columns(conn, TABLE_NAME)
        filtered = {k: row.get(k) for k in schema_cols}

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
