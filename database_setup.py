# database_setup.py
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional, Any, List
import json
import datetime as dt

# Logger
db_logger = logging.getLogger(__name__)

DB_NAME = "trading_data.db"
TABLE_NAME = "trading_logs"

def get_db_path() -> Path:
    return Path(__file__).parent / DB_NAME

def get_db_connection() -> Optional[sqlite3.Connection]:
    """Establishes and returns a database connection."""
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        db_logger.error(f"Database connection error: {e}")
        return None

# Canonical schema (superset to allow safe migrations)
REQUIRED_COLUMNS: Dict[str, str] = {
    # Primary key and time
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "timestamp": "TEXT NOT NULL",

    # Raw candle data
    "open": "REAL",
    "high": "REAL",
    "low": "REAL",
    "price": "REAL NOT NULL",
    "volume": "REAL",

    # Timeframes
    "tf": "TEXT",
    "confirm_tf": "TEXT",

    # Raw channels (primary TF)
    "trend_raw": "REAL",
    "momentum_raw": "REAL",
    "meanrev_raw": "REAL",
    "breakout_raw": "REAL",

    # Indicators (primary TF)
    "adx": "REAL",
    "atr": "REAL",

    # Post-gate (primary TF)
    "trend": "REAL",
    "momentum": "REAL",
    "meanrev": "REAL",
    "breakout": "REAL",
    "aggregate_s": "REAL",

    # Confirm TF metrics (post-gate strength and common indicators)
    "confirm_s": "REAL",
    "confirm_adx": "REAL",
    "confirm_rsi": "REAL",

    # Decision and regime
    "decision": "TEXT",
    "regime": "TEXT",
    "reasons_json": "TEXT",       # JSON array of strings for primary reasons
    "regime_reasons": "TEXT",     # existing text for regime-specific notes

    # Planned execution fields
    "stop_price": "REAL",
    "tp_price": "REAL",
    "pos_size": "REAL",
    "risk_amount": "REAL",

    # Gating flags (diagnostics)
    "trend_gated": "INTEGER",     # 0/1
    "momentum_gated": "INTEGER",  # 0/1
    "meanrev_gated": "INTEGER",   # 0/1
    "breakout_gated": "INTEGER",  # 0/1

    # State fingerprint
    "fingerprint": "TEXT",
}

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    {", ".join([f"{name} {ctype}" for name, ctype in REQUIRED_COLUMNS.items()])}
);
"""

def _get_existing_columns(conn: sqlite3.Connection) -> List[str]:
    cur = conn.execute(f"PRAGMA table_info({TABLE_NAME});")
    return [row["name"] for row in cur.fetchall()]

def _add_missing_columns(conn: sqlite3.Connection, existing_cols: List[str]) -> None:
    for name, ctype in REQUIRED_COLUMNS.items():
        if name not in existing_cols:
            # SQLite allows ALTER TABLE ADD COLUMN with default NULL
            sql = f"ALTER TABLE {TABLE_NAME} ADD COLUMN {name} {ctype};"
            db_logger.info(f"Adding missing column: {name} {ctype}")
            conn.execute(sql)

def ensure_schema() -> bool:
    """Create table if missing and migrate columns to match REQUIRED_COLUMNS."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        conn.execute(CREATE_TABLE_SQL)
        existing_cols = _get_existing_columns(conn)
        _add_missing_columns(conn, existing_cols)
        conn.commit()
        return True
    except sqlite3.Error as e:
        db_logger.error(f"Schema ensure/migration failed: {e}")
        return False
    finally:
        conn.close()

def insert_trading_log(row: Dict[str, Any]) -> bool:
    """Insert a single log row. Unknown keys are ignored; missing keys set to NULL."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        existing_cols = _get_existing_columns(conn)
        # Filter to known columns
        filtered = {k: row.get(k, None) for k in existing_cols if k in REQUIRED_COLUMNS}
        # JSON-encode reasons list if provided as list
        if "reasons_json" in filtered and isinstance(filtered["reasons_json"], (list, tuple)):
            filtered["reasons_json"] = json.dumps(filtered["reasons_json"], ensure_ascii=False)
        # Normalize gating flags to 0/1
        for k in ("trend_gated", "momentum_gated", "meanrev_gated", "breakout_gated"):
            if k in filtered and filtered[k] is not None:
                filtered[k] = 1 if bool(filtered[k]) else 0

        cols = ", ".join(filtered.keys())
        placeholders = ", ".join([":" + k for k in filtered.keys()])
        sql = f"INSERT INTO {TABLE_NAME} ({cols}) VALUES ({placeholders})"
        conn.execute(sql, filtered)
        conn.commit()
        return True
    except sqlite3.Error as e:
        db_logger.error(f"Insert failed: {e}")
        return False
    finally:
        conn.close()

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
    """
    Convert DecisionContext objects into a DB row dict.
    - reasons_json: takes dc_primary.reasons
    - gating flags inferred from reasons text if present (best-effort)
    """
    # Infer gating flags via reasons content, default False
    def reason_has(substr: str) -> int:
        if getattr(dc_primary, "reasons", None):
            return 1 if any(substr in r for r in dc_primary.reasons) else 0
        return 0

    row: Dict[str, Any] = {
        "timestamp": getattr(dc_primary, "timestamp", None) or dt.datetime.utcnow().isoformat(),
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

        "stop_price": getattr(getattr(dc_primary, "planned_position", None), "stop_price", None) or getattr(dc_primary, "stop_price", None),
        "tp_price": tp_price,
        "pos_size": pos_size,
        "risk_amount": risk_amount,

        "trend_gated": reason_has("Trend gated"),
        "momentum_gated": reason_has("Momentum gated"),
        "meanrev_gated": reason_has("Mean-reversion gated"),
        "breakout_gated": reason_has("Breakout gated"),

        "fingerprint": fingerprint,
    }
    return row
