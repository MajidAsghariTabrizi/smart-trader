#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Smart Trader V0.10 - Main Execution Module (Refactored, Close-Logic C)
================================================================================
- Debounced live logs
- Soft regime scaling
- ADX-aware gating
- ATR-based stop helper
- Explicit MTF confirmation (soft)
- Smoothed volatility regime
- SQLite logging for all analysis data (O/H/L/C/V)
- Trade lifecycle persistence (OPEN/CLOSE) and account snapshot
- Timestamp based on real-time now_iso() (نه time کندل)
- DB log de-duplication via fingerprint (کم کردن لاگ‌های تکراری HOLD)
- Close Logic C:
    * TP/SL بر اساس R-multiple
    * Fallback stop درصدی اگر stop از استراتژی نیاید
    * بستن پوزیشن در صورت سیگنال معکوس (REVERSE_SIGNAL)
================================================================================

NOTE (compat):
این فایل طوری نوشته شده که با چند نسخه از market_providers سازگار باشد:
- اگر MarketDataGateway وجود داشته باشد، از آن استفاده می‌کند.
- اگر فقط get_market_data وجود داشته باشد، یک shim داخلی می‌سازد و همان خروجی را ارائه می‌دهد.
این دقیقاً برای جلوگیری از شکست Deploy/HealthCheck به خاطر ImportError است.
"""

import time
import json
import logging
from typing import Optional, Tuple, Any
from datetime import datetime, timezone
import uuid
from collections import deque

import numpy as np
import pandas as pd

import config as cfg
import database_setup
from wallex_client import WallexClient
from indicators import (
    calculate_ema, calculate_rsi, calculate_adx, calculate_atr,
    donchian_channels, IndicatorCache, smooth_vol_ratio,
)
from trading_logic import (
    SignalEngine, StrategyParams, DecisionContext,
    Account, Position, position_size_by_risk,
)
from telegram_client import TelegramClient
from logging_setup import setup_logging, get_child_logger

# --------------------------------------------------------
# Market Providers (compat shim)
# --------------------------------------------------------
# بعضی نسخه‌ها MarketDataGateway ندارند و فقط get_market_data دارند.
# این shim باعث می‌شود main.py بدون تغییر سایر فایل‌ها اجرا شود.
try:
    from market_providers import MarketDataGateway  # type: ignore
except Exception:  # pragma: no cover
    try:
        from market_providers import get_market_data  # type: ignore

        class MarketDataGateway:  # pylint: disable=too-few-public-methods
            """Compatibility wrapper around get_market_data()."""

            def __init__(self, logger: Optional[logging.Logger] = None):
                self._logger = logger or logging.getLogger("smart_trader.market")

            def get_candles(self, symbol: str, tf: str, limit: int = 120) -> Optional[dict]:
                try:
                    res = get_market_data(symbol, tf, limit)
                    if not res:
                        return None
                    data = res.get("data") or []
                    provider = res.get("provider")
                    return {"data": data, "providers_used": [provider] if provider else []}
                except Exception as e:
                    self._logger.warning(f"MarketDataGateway shim failed: {e}")
                    return None

    except Exception:
        MarketDataGateway = None  # type: ignore

try:
    from behavior_engine import compute_behavior_score  # type: ignore
except Exception:
    compute_behavior_score = None  # type: ignore

# --------------------------------------------------------
# Logging
# --------------------------------------------------------
LOG_DIR_FALLBACK = getattr(cfg, "LOG_DIR", None)
TELEGRAM_LOG_FILE = getattr(cfg, "TELEGRAM_LOG_FILE", "telegram.log")

logging.basicConfig(
    level=getattr(logging, str(getattr(cfg, "LOG_LEVEL", "INFO")).upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(getattr(cfg, "LOG_FILE", "smart_trader.log"), mode="a", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

try:
    if LOG_DIR_FALLBACK:
        logger = setup_logging(level=cfg.LOG_LEVEL, log_dir=LOG_DIR_FALLBACK, log_file=cfg.LOG_FILE)
        telegram_logger = get_child_logger(
            "smart_trader", "telegram",
            log_dir=LOG_DIR_FALLBACK,
            filename=TELEGRAM_LOG_FILE,
            level=cfg.LOG_LEVEL,
        )
    else:
        logger = setup_logging(level=cfg.LOG_LEVEL, log_file=cfg.LOG_FILE)
        telegram_logger = get_child_logger(
            "smart_trader", "telegram",
            filename=TELEGRAM_LOG_FILE,
            level=cfg.LOG_LEVEL,
        )
except Exception:
    logger = logging.getLogger("smart_trader")
    logger.setLevel(getattr(logging, str(getattr(cfg, "LOG_LEVEL", "INFO")).upper(), logging.INFO))
    telegram_logger = logging.getLogger("smart_trader.telegram")
    telegram_logger.setLevel(getattr(logging, str(getattr(cfg, "LOG_LEVEL", "INFO")).upper(), logging.INFO))

# --------------------------------------------------------
# Helpers
# --------------------------------------------------------
def utc_ts_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

def now_iso() -> str:
    # ISO بدون microsecond و با Z – سازگار با JS و UI
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def new_trade_id() -> str:
    return uuid.uuid4().hex

def compute_regime(trend_val: float, adx_val: float, vol_ratio: float) -> Tuple[str, list]:
    """
    Regime based on smoothed volatility ratio and trend strength.
    vol_ratio is vr = atr / atr_ma smoothed; around 1 is neutral.
    """
    reasons: list[str] = []
    vr = float(vol_ratio) if vol_ratio is not None else 0.0
    adx = float(adx_val) if adx_val is not None else 0.0

    strong_trend = abs(float(trend_val)) > 0.6 and adx >= cfg.STRATEGY["min_adx_for_trend"]

    if strong_trend and vr >= 1.1:
        regime = "HIGH"
        reasons.append(f"Strong trend |trend|={trend_val:.2f}, ADX={adx:.1f}, vr={vr:.2f}")
    elif vr >= 0.9:
        regime = "NEUTRAL"
        reasons.append(f"Moderate vr={vr:.2f}")
    else:
        regime = "LOW"
        reasons.append(f"Low vr={vr:.2f}")

    return regime, reasons

def make_fingerprint(dc_240: DecisionContext, dc_60: Optional[DecisionContext], price: float) -> str:
    parts = [
        round(float(getattr(dc_240, "aggregate_s", 0.0)), 3),
        round(float(getattr(dc_240, "trend", 0.0)), 3),
        round(float(getattr(dc_240, "momentum", 0.0)), 3),
        round(float(getattr(dc_240, "meanrev", 0.0)), 3),
        round(float(getattr(dc_240, "breakout", 0.0)), 3),
        round(float(price), -4) if price else 0,
    ]
    if dc_60:
        parts.append(round(float(getattr(dc_60, "aggregate_s", 0.0)), 3))
    return "|".join(map(str, parts))

def format_number(x: Any, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)

# --------------------------------------------------------
# Init
# --------------------------------------------------------
logger.info("Initializing database...")
database_setup.ensure_schema()

wl = WallexClient(
    base_url=cfg.WALLEX["base_url"],
    api_key=cfg.WALLEX["api_key"],
    rate_limit_per_sec=cfg.WALLEX["rate_limit_per_sec"],
    retries=cfg.WALLEX["retries"],
    timeout=cfg.WALLEX["timeout"],
)

md_gateway = None
if MarketDataGateway is not None:
    try:
        md_gateway = MarketDataGateway(logger=logger)  # type: ignore[arg-type]
    except TypeError:
        md_gateway = MarketDataGateway()  # type: ignore[call-arg]
    except Exception as e:
        logger.warning(f"MarketDataGateway init failed: {e}")
        md_gateway = None

signal_engine = SignalEngine(
    StrategyParams(
        weights=cfg.STRATEGY["weights"],
        s_buy=cfg.STRATEGY["s_buy"],
        s_sell=cfg.STRATEGY["s_sell"],
        min_adx_for_trend=cfg.STRATEGY["min_adx_for_trend"],
        allow_intracandle=cfg.STRATEGY["allow_intracandle"],
        regime_scale=cfg.STRATEGY["regime_scale"],
        max_risk_per_trade=cfg.STRATEGY["max_risk_per_trade"],
        atr_stop_mult=cfg.STRATEGY["atr_stop_mult"],
        require_mtf_agreement=cfg.STRATEGY["require_mtf_agreement"],
        decision_buffer=cfg.STRATEGY.get("decision_buffer", 0.02),
        mtf_confirm_bar=cfg.STRATEGY.get("mtf_confirm_bar", 0.30),
        min_vr_trade=cfg.STRATEGY.get("min_vr_trade", 0.88),
        min_vr_intracandle=cfg.STRATEGY.get("min_vr_intracandle", 0.95),
        vr_adapt_k=cfg.STRATEGY.get("vr_adapt_k", 0.25),
        vr_adapt_clamp=cfg.STRATEGY.get("vr_adapt_clamp", 0.08),
        impulse_only_high=cfg.STRATEGY.get("impulse_only_high", True),
    )
)

account = Account(equity=cfg.START_EQUITY, balance=cfg.START_EQUITY, position=None)
ind_cache = IndicatorCache()  # kept for compatibility even if unused

last_log_fingerprint: Optional[str] = None
last_db_fingerprint: Optional[str] = None
tg: Optional[TelegramClient] = None
last_executed_candle_ts: Optional[int] = None

signal_buffer = deque(maxlen=5)

def _format_position_state(price: float) -> Optional[str]:
    """
    Render a compact position state line for SMART ANALYSIS.
    """
    if not account.position:
        return None

    pos = account.position
    qty = float(pos.qty)
    entry = float(pos.entry_price)
    stop = float(pos.stop_price) if pos.stop_price else None
    notional = qty * entry

    if pos.side == "LONG":
        upnl = (price - entry) * qty
    else:
        upnl = (entry - price) * qty

    status = "WAITING_TO_CLOSE"
    return (
        f"-- Position State --\n"
        f"side: {pos.side}  qty: {qty:.6f}  entry: {entry:.2f}  stop: {stop}\n"
        f"notional: {notional:.2f}  uPnL: {upnl:.2f}  status: {status}"
    )

# --------------------------------------------------------
# Telegram client
# --------------------------------------------------------
def _build_tg_client() -> Optional[TelegramClient]:
    try:
        enabled = bool(cfg.TELEGRAM.get("enabled", False))
        token = cfg.TELEGRAM.get("bot_token", "") or ""
        chat_id = cfg.TELEGRAM.get("chat_id", "") or ""
        min_level = cfg.TELEGRAM.get("min_level", "INFO")

        masked = token[:6] + "..." if token else ""
        logger.info(
            f"Telegram cfg: enabled={enabled} chat_id={'set' if chat_id else 'missing'} "
            f"token_prefix={masked}"
        )

        if not enabled:
            logger.info("Telegram disabled in config.")
            return None
        if not token or not chat_id:
            logger.warning("Telegram enabled but bot_token/chat_id missing.")
            return None

        client = TelegramClient(
            cfg={"bot_token": token, "chat_id": chat_id, "min_level": min_level},
            logger=telegram_logger,
        )
        return client
    except Exception as e:
        logger.exception(f"Failed to build Telegram client: {e}")
        return None

def _tg_ping():
    if tg:
        try:
            tg.send("✅ Smart Trader started.", "INFO")
            logger.info("Startup Telegram ping sent.")
        except Exception as e:
            logger.exception(f"Failed to send Telegram startup ping: {e}")
    else:
        logger.info("Telegram client is None; startup ping skipped.")

tg = _build_tg_client()
_tg_ping()

# --------------------------------------------------------
# Persistence helpers
# --------------------------------------------------------
def _persist_account_snapshot():
    try:
        state = {
            "timestamp": now_iso(),
            "symbol": cfg.SYMBOL,
            "equity": float(account.equity),
            "balance": float(account.balance),
            "position_side": account.position.side if account.position else None,
            "position_qty": float(account.position.qty) if account.position else None,
            "position_entry": float(account.position.entry_price) if account.position else None,
            "position_stop": float(account.position.stop_price)
            if (account.position and account.position.stop_price)
            else None,
        }
        if hasattr(database_setup, "upsert_account_state"):
            database_setup.upsert_account_state(state)
        else:
            logger.debug(f"Account snapshot: {json.dumps(state)}")
    except Exception as e:
        logger.exception(f"Failed to persist account state: {e}")

def _log_trade_event(event_type: str, details: dict):
    try:
        event = {
            "timestamp": now_iso(),
            "symbol": cfg.SYMBOL,
            "event_type": event_type,
            **details,
        }
        if hasattr(database_setup, "insert_trade_event"):
            database_setup.insert_trade_event(event)
        else:
            logger.info(f"TRADE EVENT [{event_type}]: {json.dumps(event, ensure_ascii=False)}")
    except Exception as e:
        logger.exception(f"Failed to insert trade event: {e}")

# --------------------------------------------------------
# Close helpers
# --------------------------------------------------------
def _close_position(current_price: float, reason: str):
    """
    Close current position with given reason.
    - محاسبه‌ی PnL
    - آپدیت balance و equity
    - ثبت رویداد CLOSE
    - snapshot از account_state
    """
    if not account.position:
        return
    if current_price is None:
        return

    pos = account.position
    entry = float(pos.entry_price)
    qty = float(pos.qty)
    side = pos.side
    stop_price = float(pos.stop_price) if pos.stop_price is not None else None

    if qty <= 0.0 or entry <= 0.0:
        return

    if side == "LONG":
        pnl = (current_price - entry) * qty
        # لانگ: فروش دارایی
        account.balance += qty * current_price
    else:
        # شورت: شبیه cash-settled
        pnl = (entry - current_price) * qty
        account.balance += pnl

    account.position = None
    account.update_equity(current_price)

    trade_id = getattr(pos, "trade_id", None)

    _log_trade_event(
        "CLOSE",
        {
            "trade_id": trade_id,
            "side": side,
            "qty": qty,
            "entry_price": entry,
            "close_price": float(current_price),
            "stop_price": stop_price,
            "pnl": float(pnl),
            "reason": reason,
        },
    )
    logger.info(f"🛑 Closed {side} @ {current_price:.2f} pnl={pnl:.2f} ({reason})")

    if tg:
        try:
            tg.send(
                f"🛑 <b>Closed</b> {cfg.SYMBOL} {side} "
                f"qty={qty:.6f} @ {current_price:.2f}\n"
                f"PnL: {pnl:.2f} ({reason})",
                "INFO",
            )
        except Exception as e:
            logger.exception(f"Failed to send Telegram close message: {e}")

    _persist_account_snapshot()

def _maybe_close_position(current_price: float):
    """
    Exit management:
      - Hard stop (STOP_HIT)
      - Take-profit در حدود +1R (TP_HIT)
      - Move stop to breakeven در حدود +0.4R
    """
    if not account.position:
        return
    if current_price is None:
        return

    pos = account.position
    entry = float(pos.entry_price)
    qty = float(pos.qty)
    stop = pos.stop_price

    if qty <= 0.0 or entry <= 0.0:
        return

    # اگر استاپ نداریم، فعلاً فقط REVERSE_SIGNAL ما را می‌بندد
    if stop is not None:
        risk_per_unit = abs(entry - float(stop))
    else:
        risk_per_unit = 0.0

    # 1) مدیریت R-multiple (TP و BE) فقط اگر stop تعریف شده باشد
    if risk_per_unit > 0.0:
        direction = 1.0 if pos.side == "LONG" else -1.0
        r_mult = ((current_price - entry) * direction) / risk_per_unit

        # نسبت‌های جدید
        tp_r_level = 0.7   # حدود +1R همه پوزیشن را ببند
        be_r_level = 0.35  # حدود +0.4R استاپ را روی BE بیاور

        # 1.a) Take-profit کامل روی 1R
        if r_mult >= tp_r_level:
            logger.info(
                f"🎯 TP hit for {pos.side} trade_id={getattr(pos, 'trade_id', None)} "
                f"R={r_mult:.2f} (>= {tp_r_level:.2f})"
            )
            _close_position(current_price, "TP_HIT")
            return

        # 1.b) انتقال استاپ به break-even
        if r_mult >= be_r_level and not getattr(pos, "breakeven_armed", False):
            pos.stop_price = entry
            pos.breakeven_armed = True
            logger.info(
                f"🔒 Move stop to breakeven for {pos.side} "
                f"trade_id={getattr(pos, 'trade_id', None)} "
                f"R={r_mult:.2f} (>= {be_r_level:.2f})"
            )

    # 2) Hard stop check (STOP_HIT) – بعد از مدیریت TP/BE
    if pos.stop_price is None:
        return

    stop_now = float(pos.stop_price)
    breached = (
        (pos.side == "LONG" and current_price <= stop_now)
        or (pos.side == "SHORT" and current_price >= stop_now)
    )

    if not breached:
        return

    logger.info(
        f"⛔ Stop breached for {pos.side} trade_id={getattr(pos, 'trade_id', None)} "
        f"price={current_price:.2f}, stop={stop_now:.2f}"
    )
    _close_position(current_price, "STOP_HIT")

# --------------------------------------------------------
# Core loop
# --------------------------------------------------------
def analyze_once(iteration: int):
    global last_log_fingerprint, last_db_fingerprint, last_executed_candle_ts

    candles_240 = wl.get_candles(cfg.SYMBOL, cfg.PRIMARY_TF, cfg.MAX_CANDLES_PRIMARY)
    candles_60 = wl.get_candles(cfg.SYMBOL, cfg.CONFIRM_TF, cfg.MAX_CANDLES_CONFIRM)

    if not candles_240:
        logger.warning("No primary TF candles received")
        return

    df240 = pd.DataFrame(candles_240)
    df60 = pd.DataFrame(candles_60) if candles_60 else pd.DataFrame()

    # Normalize columns
    for df in (df240, df60):
        if df is None or df.empty:
            continue
        rename_map = {"c": "close", "h": "high", "l": "low", "o": "open", "t": "time", "v": "volume"}
        df.rename(columns=rename_map, inplace=True)
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = df[col].astype(float)
        if "time" in df.columns:
            df["time"] = df["time"].astype(int)

    current_ts = int(df240["time"].iloc[-1])

    if not cfg.STRATEGY["allow_intracandle"]:
        if last_executed_candle_ts == current_ts:
            return
        last_executed_candle_ts = current_ts

    # Live price override
    live_ticker = wl.get_ticker(cfg.SYMBOL)
    live_price = None
    try:
        if live_ticker:
            live_price = float(live_ticker.get("last", live_ticker.get("close", None)))
    except Exception:
        live_price = None

    candle_is_live = (live_price is not None)
    if live_price is not None:
        prev_close = df240["close"].iloc[-1]
        if abs(prev_close - live_price) > 1e-6:
            logger.info(f"💹 Live price override: {prev_close:.2f} → {live_price:.2f}")
            df240.at[df240.index[-1], "close"] = live_price
            df240.at[df240.index[-1], "high"] = max(df240["high"].iloc[-1], live_price)
            df240.at[df240.index[-1], "low"] = min(df240["low"].iloc[-1], live_price)

    latest_candle_data = df240.iloc[-1].to_dict()

    # ================= Behavior Intelligence (Option C) =================
    behavior_score = None
    behavior_bias = 0.0
    behavior_details = None
    behavior_providers = []

    if md_gateway is not None and compute_behavior_score is not None:
        try:
            md = md_gateway.get_candles(symbol=cfg.SYMBOL, tf=cfg.PRIMARY_TF, limit=120)
            if md and md.get("data"):
                behavior = compute_behavior_score(symbol=cfg.SYMBOL, market_data=md["data"])

                behavior_score = behavior.get("behavior_score")
                if behavior_score is not None:
                    behavior_bias = max(-1.0, min(1.0, (float(behavior_score) - 50.0) / 25.0))

                behavior_details = behavior
                behavior_providers = md.get("providers_used", []) or []
        except Exception as e:
            logger.warning(f"Behavior engine failed: {e}")

    # 240 TF indicators and channels
    close240 = df240["close"]
    ema_fast = calculate_ema(close240, 20)
    ema_slow = calculate_ema(close240, 50)
    rsi240 = calculate_rsi(close240, 14)
    adx240 = calculate_adx(df240, 14)
    atr240 = calculate_atr(df240, 14)

    vr_240 = float(smooth_vol_ratio(atr240).iloc[-1])

    trend_240 = float(np.tanh((ema_fast.iloc[-1] - ema_slow.iloc[-1]) / (1e-9 + atr240.iloc[-1])))
    momentum_240 = float((rsi240.iloc[-1] - 50.0) / 50.0)

    residual = close240 - ema_slow
    residual_std = float(residual.rolling(50, min_periods=20).std().iloc[-1] or 1.0)
    meanrev_240 = float(-np.tanh(residual.iloc[-1] / (1e-9 + residual_std)))

    up, lo = donchian_channels(df240, 20)
    rng = float((up.iloc[-1] - lo.iloc[-1]) or 1.0)
    breakout_240 = float(np.clip((close240.iloc[-1] - (up.iloc[-1] + lo.iloc[-1]) / 2) / (rng + 1e-9), -1, 1))

    adx_val_240 = float(adx240.iloc[-1])
    regime, regime_reasons = compute_regime(trend_240, adx_val_240, vr_240)

    ts_now = now_iso()

    dc240 = DecisionContext(
        trend_raw=trend_240,
        momentum_raw=momentum_240,
        meanrev_raw=meanrev_240,
        breakout_raw=breakout_240,
        adx=adx_val_240,
        atr=float(atr240.iloc[-1]),
        price=float(close240.iloc[-1]),
        tf=cfg.PRIMARY_TF,
        regime=regime,
        vol_ratio=vr_240,
        timestamp=ts_now,
    )
    dc240.reasons.extend(regime_reasons)

    # inject behavior first
    dc240.behavior_score = behavior_score
    dc240.behavior_bias = behavior_bias
    dc240.behavior_details = behavior_details
    dc240.behavior_providers = behavior_providers

    # then gate_and_weight
    dc240 = signal_engine.gate_and_weight(dc240)

    # Confirm TF
    dc60: Optional[DecisionContext] = None
    if not df60.empty:
        close60 = df60["close"]
        ema_fast60 = calculate_ema(close60, 20)
        ema_slow60 = calculate_ema(close60, 50)
        rsi60 = calculate_rsi(close60, 14)
        adx60 = calculate_adx(df60, 14)
        atr60 = calculate_atr(df60, 14)

        trend_60 = float(np.tanh((ema_fast60.iloc[-1] - ema_slow60.iloc[-1]) / (1e-9 + atr60.iloc[-1])))
        momentum_60 = float((rsi60.iloc[-1] - 50.0) / 50.0)
        residual60 = close60 - ema_slow60
        residual_std60 = float(residual60.rolling(50, min_periods=20).std().iloc[-1] or 1.0)
        meanrev_60 = float(-np.tanh(residual60.iloc[-1] / (1e-9 + residual_std60)))
        up60, lo60 = donchian_channels(df60, 20)
        rng60 = float((up60.iloc[-1] - lo60.iloc[-1]) or 1.0)
        breakout_60 = float(np.clip((close60.iloc[-1] - (up60.iloc[-1] + lo60.iloc[-1]) / 2) / (rng60 + 1e-9), -1, 1))

        dc60 = DecisionContext(
            trend_raw=trend_60,
            momentum_raw=momentum_60,
            meanrev_raw=meanrev_60,
            breakout_raw=breakout_60,
            adx=float(adx60.iloc[-1]),
            atr=float(atr60.iloc[-1]),
            price=float(close60.iloc[-1]),
            tf=cfg.CONFIRM_TF,
            regime=regime,
            vol_ratio=vr_240,
            timestamp=ts_now,
        )
        dc60 = signal_engine.gate_and_weight(dc60)

    action, trade = signal_engine.decide(dc240, dc60)

    # VOL_EXPAND_GUARD
    if cfg.STRATEGY.get("allow_intracandle", True) and candle_is_live and action in ("BUY", "SELL"):
        min_vr_live = float(cfg.STRATEGY.get("min_vr_intracandle", 0.95))
        if (vr_240 is not None) and (vr_240 < min_vr_live) and (dc240.regime != "HIGH"):
            dc240.reasons.append(f"VOL_EXPAND_GUARD: vr={vr_240:.3f} < {min_vr_live:.3f} (live) → HOLD")
            action, trade = "HOLD", None

    signal_buffer.append(action)
    if action == "BUY" and signal_buffer.count("BUY") < 3:
        return
    if action == "SELL" and signal_buffer.count("SELL") < 3:
        return

    # ---------------- DB logging (dedupe by fingerprint) ---------------- #
    try:
        from database_setup import dc_to_row, insert_trading_log

        fingerprint = make_fingerprint(dc240, dc60, dc240.price or 0)

        if fingerprint != last_db_fingerprint:
            row = dc_to_row(
                decision=action,
                dc_primary=dc240,
                dc_confirm=dc60,
                tf=cfg.PRIMARY_TF,
                confirm_tf=cfg.CONFIRM_TF,
                pos_size=(trade or {}).get("qty") if isinstance(trade, dict) else None,
                risk_amount=None,
                tp_price=(trade or {}).get("tp_price") if isinstance(trade, dict) else None,
                fingerprint=fingerprint,
                regime_reasons="; ".join(regime_reasons) if regime_reasons else None,
            )
            row.update(
                {
                    "open": latest_candle_data.get("open"),
                    "high": latest_candle_data.get("high"),
                    "low": latest_candle_data.get("low"),
                    "volume": latest_candle_data.get("volume", 0.0),
                    "timestamp": dc240.timestamp or ts_now,
                }
            )
            row.update({
                "behavior_score": getattr(dc240, "behavior_score", None),
                "behavior_bias": getattr(dc240, "behavior_bias", None),
                "behavior_json": json.dumps(getattr(dc240, "behavior_details", None), ensure_ascii=False)
                if getattr(dc240, "behavior_details", None) else None,
                "behavior_providers": ",".join(getattr(dc240, "behavior_providers", []) or []),
            })

            ok = insert_trading_log(row)
            if not ok:
                logger.error("Failed to insert trading log row")
            else:
                last_db_fingerprint = fingerprint
    except Exception as e:
        logger.error(f"Failed to log analysis to database: {e}")

    # ---------------- SMART ANALYSIS log / Telegram ---------------- #
    fp = make_fingerprint(dc240, dc60, dc240.price or 0)
    repeated = fp == last_log_fingerprint

    if not (candle_is_live and repeated):
        last_log_fingerprint = fp

        trade_preview = ""
        if isinstance(trade, dict):
            trade_preview = f"Trade: {trade}"
        elif isinstance(trade, Position):
            trade_preview = (
                f"Trade: Position(side='{trade.side}', qty={trade.qty}, "
                f"entry_price={trade.entry_price}, stop_price={trade.stop_price})"
            )

        pos_state_text = _format_position_state(dc240.price) or ""

        block = f"""
====================================

========== SMART ANALYSIS ==========
Iter: {iteration}  Time: {utc_ts_to_iso(current_ts)} UTC
Price: {format_number(dc240.price, nd=2)}
-- Raw Channels (240) --
trend_raw: {format_number(dc240.trend_raw)}  momentum_raw: {format_number(dc240.momentum_raw)}  meanrev_raw: {format_number(dc240.meanrev_raw)}  breakout_raw: {format_number(dc240.breakout_raw)}
adx: {format_number(dc240.adx)}  atr: {format_number(dc240.atr, nd=2)}  regime: {dc240.regime}
-- Post-Gate (240) --
trend: {format_number(dc240.trend)}  momentum: {format_number(dc240.momentum)}  meanrev: {format_number(dc240.meanrev)}  breakout: {format_number(dc240.breakout)}
Aggregate S (240): {format_number(dc240.aggregate_s)} | Thresh: BUY>={cfg.STRATEGY['s_buy']} SELL<={cfg.STRATEGY['s_sell']}
Behavior:
  score: {getattr(dc240, 'behavior_score', None)}
  bias: {format_number(getattr(dc240, 'behavior_bias', 0.0))}
  providers: {", ".join(getattr(dc240, 'behavior_providers', []) or [])}

{(("-- Post-Gate (60) --" + chr(10) + f"S(60): {format_number(dc60.aggregate_s)}  trend: {format_number(dc60.trend)}  mom: {format_number(dc60.momentum)}  mr: {format_number(dc60.meanrev)}  bo: {format_number(dc60.breakout)}") if dc60 is not None else "")}
Decision: {action}
{trade_preview}
{pos_state_text}

Reasons:
  - {(chr(10) + "  - ").join(dc240.reasons)}
====================================
""".rstrip()

        logger.info(block)
        if tg:
            try:
                sent = tg.send_smart_analysis(block)
                if not sent:
                    telegram_logger.warning("SMART ANALYSIS telegram send failed.")
            except Exception as e:
                telegram_logger.exception(f"SMART ANALYSIS send exception: {e}")

    # ---------------- Risk / Execution layer ---------------- #
    # 1) TP/SL
    _maybe_close_position(dc240.price)

    # 2) Reverse signal
    if account.position and action in ("BUY", "SELL"):
        desired_side = "LONG" if action == "BUY" else "SHORT"
        if account.position.side != desired_side:
            logger.info(
                f"🔄 Reverse signal: closing {account.position.side} "
                f"due to {action} signal at price={dc240.price:.2f}"
            )
            _close_position(dc240.price, "REVERSE_SIGNAL")

    # Entry policy / allow_intracandle
    execute_now = True
    if not cfg.STRATEGY.get("allow_intracandle", True) and candle_is_live and action in ("BUY", "SELL"):
        execute_now = False
        dc240.reasons.append("Intracandle disabled: live candle → skip trade")

    # Only one open position at a time
    if account.position:
        return

    min_trade_value = getattr(cfg, "MIN_TRADE_VALUE", 100000)

    if execute_now and action in ("BUY", "SELL"):
        if action == "SELL" and not getattr(cfg, "ALLOW_SHORT", True):
            return
        if dc240.price is None or dc240.price <= 0:
            logger.info("Skipping trade: invalid price")
            return

        account.update_equity(dc240.price)

        if not account.can_trade(min_trade_value, dc240.price):
            logger.info("Skipping trade: insufficient balance or below min notional")
            return

        # stop from strategy output
        stop_price = None
        if isinstance(trade, dict):
            stop_price = trade.get("stop_price") or trade.get("stop")
        elif isinstance(trade, Position):
            stop_price = trade.stop_price

        side = "LONG" if action == "BUY" else "SHORT"

        # Fallback stop
        if stop_price is None:
            default_stop_pct = getattr(cfg, "DEFAULT_STOP_PCT", 0.01)
            if side == "LONG":
                stop_price = dc240.price * (1.0 - default_stop_pct)
            else:
                stop_price = dc240.price * (1.0 + default_stop_pct)

        # position sizing by risk
        if stop_price:
            qty = position_size_by_risk(
                account.equity,
                cfg.STRATEGY["max_risk_per_trade"],
                dc240.price,
                float(stop_price),
            )
        else:
            qty = max(min_trade_value / dc240.price, 0.0)

        qty = float(qty or 0.0)
        if qty <= 0:
            logger.info("Skipping trade: computed qty <= 0")
            return

        notional = qty * dc240.price
        if notional < min_trade_value:
            need_qty = min_trade_value / dc240.price
            if side == "LONG" and (need_qty * dc240.price) > account.balance:
                logger.info("Skipping trade: cannot scale to reach MIN_TRADE_VALUE due to balance")
                return
            qty = need_qty
            notional = qty * dc240.price

        trade_id = new_trade_id()

        account.position = Position(
            side=side,
            qty=qty,
            entry_price=dc240.price,
            stop_price=float(stop_price) if stop_price else None,
            trade_id=trade_id,
            opened_at_ts=int(time.time()),
        )

        if side == "LONG":
            account.balance -= notional

        account.update_equity(dc240.price)

        _log_trade_event(
            "OPEN",
            {
                "trade_id": trade_id,
                "side": side,
                "qty": float(qty),
                "entry_price": float(dc240.price),
                "stop_price": float(stop_price) if stop_price else None,
            },
        )
        _persist_account_snapshot()

        logger.info(
            f"📈 Executed {action} qty={qty:.6f} at {dc240.price:.2f} "
            f"(notional={notional:.2f}) stop={stop_price}"
        )
        if tg:
            try:
                tg.send(
                    f"<b>Trade</b> {action} {cfg.SYMBOL} qty={qty:.6f} @ {dc240.price:.2f}\n"
                    f"Notional: {notional:.2f}\nStop: {stop_price}",
                    "INFO",
                )
            except Exception as e:
                logger.exception(f"Failed to send Telegram trade message: {e}")

def main():
    logger.info("Re-checking database initialization...")
    database_setup.ensure_schema()

    iteration = 0
    while True:
        try:
            iteration += 1
            analyze_once(iteration)
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
        time.sleep(cfg.LIVE_POLL_SECONDS)

if __name__ == "__main__":
    main()
