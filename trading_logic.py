# trading_logic.py

"""
================================================================================
Trading logic: decision engine, risk, and account model
================================================================================
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
import math


@dataclass
class DecisionContext:
    # Raw channels
    trend_raw: float
    momentum_raw: float
    meanrev_raw: float
    breakout_raw: float
    adx: float
    atr: float
    price: float
    tf: str
    regime: str

    # Optional metadata
    timestamp: Optional[str] = None  # filled by caller (now_iso)

    # Post-gate values
    trend: float = 0.0
    momentum: float = 0.0
    meanrev: float = 0.0
    breakout: float = 0.0

    aggregate_s: float = 0.0
    confirm_s: float = 0.0
    confirm_adx: float = 0.0
    confirm_rsi: float = 0.0

    reasons: List[str] = field(default_factory=list)


@dataclass
class StrategyParams:
    weights: Dict[str, float]
    s_buy: float
    s_sell: float
    min_adx_for_trend: float
    allow_intracandle: bool
    regime_scale: Dict[str, float]
    max_risk_per_trade: float
    atr_stop_mult: float
    require_mtf_agreement: bool
    decision_buffer: float
    mtf_confirm_bar: float


@dataclass
class Position:
    side: str  # LONG or SHORT
    qty: float
    entry_price: float
    stop_price: Optional[float] = None
    trade_id: Optional[str] = None  # شناسه ترید برای لاگ

    # مدیریت پوزیشن (فقط در حافظه، توی DB ذخیره نمی‌شود)
    breakeven_armed: bool = False  # آیا استاپ به BE منتقل شده؟
    tp_hit: bool = False           # اگر TP بسته شد، True




@dataclass
class Account:
    equity: float
    balance: float
    position: Optional[Position] = None

    def update_equity(self, mark_price: float):
        if self.position:
            direction = 1 if self.position.side == "LONG" else -1
            pnl = (mark_price - self.position.entry_price) * self.position.qty * direction
        else:
            pnl = 0.0
        self.equity = self.balance + pnl

    def can_trade(self, min_notional: float, price: float) -> bool:
        return self.balance >= max(min_notional, 0.0) and price > 0.0


def _is_finite_positive(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0.0


def position_size_by_risk(equity: float, max_risk_frac: float, entry: float, stop: Optional[float]) -> float:
    """
    Sizing based on %risk of equity.
    """
    if stop is None or not _is_finite_positive(entry) or not math.isfinite(equity) or not math.isfinite(max_risk_frac):
        return 0.0
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0.0:
        return 0.0
    capital_risk = max(equity, 0.0) * max(max_risk_frac, 0.0)
    qty = capital_risk / risk_per_unit
    if not math.isfinite(qty) or qty <= 0.0:
        return 0.0
    return float(qty)


class SignalEngine:
    """
    Encapsulates gating, aggregation، MTF confirmation و ساخت سیگنال نهایی.
    """

    def __init__(self, params: StrategyParams):
        self.params = params  # یک نام واحد برای همه‌جا

    def _safe_get_weight(self, name: str) -> float:
        try:
            w = float(self.params.weights.get(name, 0.0))
            return w if math.isfinite(w) else 0.0
        except Exception:
            return 0.0

    # ---------------- Gating & Aggregation ---------------- #

    def gate_and_weight(self, dc: DecisionContext) -> DecisionContext:
        p = self.params

        adx_val = dc.adx if math.isfinite(dc.adx) else 0.0

        # 1) ADX gating on trend
        trend_component = dc.trend_raw if adx_val >= p.min_adx_for_trend else 0.0
        if adx_val < p.min_adx_for_trend:
            dc.reasons.append(f"Trend gated (ADX<{p.min_adx_for_trend:.1f})")

        # 2) سایر کانال‌ها (خام)
        mom = dc.momentum_raw
        mr = dc.meanrev_raw
        bo = dc.breakout_raw

        # 2.5) حل تضاد Trend vs Mean-Reversion
        # اگر جهت ترند و meanrev به‌شدت مخالف باشند → هر دو را صفر کن (ترید نکنیم).
        conflict = False
        mr_conf_level = 0.40  # شدت حداقلی برای اینکه بگیم "خیلی مخالف است"

        if dc.trend_raw > 0.0 and dc.meanrev_raw < -mr_conf_level:
            conflict = True
        elif dc.trend_raw < 0.0 and dc.meanrev_raw > mr_conf_level:
            conflict = True

        if conflict:
            dc.reasons.append(
                f"Trend/MeanRev conflict: trend_raw={dc.trend_raw:.3f}, "
                f"meanrev_raw={dc.meanrev_raw:.3f} → gating both to 0"
            )
            trend_component = 0.0
            mr = 0.0

        # 3) Regime scaling
        regime_scale = p.regime_scale.get(dc.regime, 1.0)
        if not math.isfinite(regime_scale):
            regime_scale = 1.0

        # 4) Weights
        w_trend = self._safe_get_weight("trend")
        w_mom = self._safe_get_weight("momentum")
        w_mr = self._safe_get_weight("meanrev")
        w_bo = self._safe_get_weight("breakout")

        # Assign post-gate components
        dc.trend = float(trend_component)
        dc.momentum = float(mom)
        dc.meanrev = float(mr)
        dc.breakout = float(bo)

        # 5) Aggregate S
        aggregate = (
                w_trend * dc.trend +
                w_mom * dc.momentum +
                w_mr * dc.meanrev +
                w_bo * dc.breakout
        )

        dc.aggregate_s = float(aggregate) * float(regime_scale)
        dc.reasons.append(f"Aggregate={dc.aggregate_s:.3f} (regime_scale={regime_scale:.2f})")
        return dc

    # ---------------- MTF Confirmation ---------------- #

    def _mtf_confirm_pass(
        self,
        dc_primary: DecisionContext,
        dc_confirm: Optional[DecisionContext]
    ) -> Tuple[bool, List[str]]:
        p = self.params
        reasons: List[str] = []

        if not p.require_mtf_agreement:
            reasons.append("MTF agreement not required")
            return True, reasons

        if dc_confirm is None:
            reasons.append("MTF reject: confirm TF missing")
            return False, reasons

        same_sign = (
            (dc_primary.aggregate_s >= 0 and dc_confirm.aggregate_s >= 0) or
            (dc_primary.aggregate_s < 0 and dc_confirm.aggregate_s < 0)
        )
        strong_enough = abs(dc_confirm.aggregate_s) >= p.mtf_confirm_bar

        if same_sign and strong_enough:
            reasons.append(
                f"MTF agree: confirm={dc_confirm.aggregate_s:.3f} >= {p.mtf_confirm_bar:.2f}"
            )
            return True, reasons

        reasons.append(
            f"MTF reject: confirm={dc_confirm.aggregate_s:.3f} "
            f"vs threshold {p.mtf_confirm_bar:.2f}, same_sign={same_sign}"
        )
        return False, reasons

    # ---------------- Stop Builder ---------------- #

    def _build_stop(self, side: str, entry: float, atr: float, atr_mult: float) -> Optional[float]:
        if not (_is_finite_positive(entry) and math.isfinite(atr) and math.isfinite(atr_mult)):
            return None
        if atr <= 0.0 or atr_mult <= 0.0:
            return None

        if side == "LONG":
            stop = entry - atr_mult * atr
        else:
            stop = entry + atr_mult * atr

        if not math.isfinite(stop):
            return None
        return max(stop, 0.0)

    # ---------------- Final Decision ---------------- #

    def decide(
        self,
        dc_primary: DecisionContext,
        dc_confirm: Optional[DecisionContext]
    ) -> Tuple[str, Optional[Position]]:
        """
        خروجی:
        - action در {"BUY", "SELL", "HOLD"}
        - position فقط برای BUY/SELL مقدار دارد (qty=0 تا main سایز را حساب کند)
        """
        p = self.params
        action = "HOLD"
        pos: Optional[Position] = None

        # تصمیم با حاشیه‌ی امنیت (buffer)
        buy_th = float(p.s_buy) + float(p.decision_buffer)
        sell_th = float(p.s_sell) + float(p.decision_buffer)

        # تأیید مولتی‌تایم‌فریم
        mtf_ok, mtf_reasons = self._mtf_confirm_pass(dc_primary, dc_confirm)
        dc_primary.reasons.extend(mtf_reasons)

        primary_s = float(dc_primary.aggregate_s)

        wants_long = (primary_s >= buy_th) and mtf_ok
        wants_short = (primary_s <= -sell_th) and mtf_ok

        entry = float(max(dc_primary.price, 0.0)) if math.isfinite(dc_primary.price) else 0.0
        atr = float(max(dc_primary.atr, 0.0)) if math.isfinite(dc_primary.atr) else 0.0

        stop_long = self._build_stop("LONG", entry, atr, p.atr_stop_mult)
        stop_short = self._build_stop("SHORT", entry, atr, p.atr_stop_mult)

        if wants_long:
            action = "BUY"
            pos = Position(side="LONG", qty=0.0, entry_price=entry, stop_price=stop_long)
            dc_primary.reasons.append(f"Decision BUY: s={primary_s:.3f} >= {buy_th:.3f}")
        elif wants_short:
            action = "SELL"
            pos = Position(side="SHORT", qty=0.0, entry_price=entry, stop_price=stop_short)
            dc_primary.reasons.append(f"Decision SELL: s={primary_s:.3f} <= {-sell_th:.3f}")
        else:
            action = "HOLD"
            dc_primary.reasons.append(
                f"HOLD: s={primary_s:.3f}, thresholds=({buy_th:.3f}, {-sell_th:.3f})"
            )

        return action, pos
