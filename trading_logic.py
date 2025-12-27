# trading_logic.py
"""
================================================================================
Trading logic: decision engine, risk, and account model
================================================================================
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
import math


def _clamp(x: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo


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

    # Volatility metadata (optional)
    vol_ratio: Optional[float] = None  # e.g. atr/atr_ma smoothed

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
    # === Behavior Intelligence (Option C) ===
    behavior_score: Optional[float] = None        # 0..100
    behavior_bias: float = 0.0                    # [-1 .. +1]
    behavior_details: Optional[dict] = None
    behavior_providers: Optional[List[str]] = None


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

    # Volatility / execution guards (best-practice, safe defaults)
    min_vr_trade: float = 0.88          # below this, avoid trading (range/low-vol chop)
    min_vr_intracandle: float = 0.95    # live-trade only if vr is expanding enough
    vr_adapt_k: float = 0.25            # threshold adaptation slope
    vr_adapt_clamp: float = 0.08        # max absolute threshold shift
    impulse_only_high: bool = True      # fast-path only in HIGH regime
    # --- Behavior weight (Option C) ---
    behavior_weight: float = 0.15


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
    opened_at_ts: Optional[int] = None


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
        self.params = params

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

        # 1) ADX-aware gating روی ترند (نرم)
        trend_component = dc.trend_raw
        if adx_val < p.min_adx_for_trend:
            trend_component *= 0.4
            dc.reasons.append(f"Trend downscaled (ADX<{p.min_adx_for_trend:.1f})")
        else:
            dc.reasons.append(f"Trend active (ADX>={p.min_adx_for_trend:.1f})")

        # 2) سایر کانال‌ها
        mom = dc.momentum_raw
        mr = dc.meanrev_raw
        bo = dc.breakout_raw

        # 2.5) تضاد Trend vs Mean-Reversion:
        conflict = False
        mr_conf_level = 0.40

        if dc.trend_raw > 0.0 and dc.meanrev_raw < -mr_conf_level:
            conflict = True
        elif dc.trend_raw < 0.0 and dc.meanrev_raw > mr_conf_level:
            conflict = True

        if conflict:
            mr *= 0.2
            dc.reasons.append(
                f"Trend/MeanRev conflict: trend_raw={dc.trend_raw:.3f}, "
                f"meanrev_raw={dc.meanrev_raw:.3f} → meanrev suppressed"
            )

        # 3) Regime scaling
        regime_scale = p.regime_scale.get(dc.regime, 1.0)
        if not math.isfinite(regime_scale):
            regime_scale = 1.0

        # 4) Weights
        w_trend = self._safe_get_weight("trend")
        w_mom = self._safe_get_weight("momentum")
        w_mr = self._safe_get_weight("meanrev")
        w_bo = self._safe_get_weight("breakout")

        # 5) مقدارهای post-gate
        dc.trend = float(trend_component)
        dc.momentum = float(mom)
        dc.meanrev = float(mr)
        dc.breakout = float(bo)

        # --- Behavior bias (Option C) ---
        behavior_bias = float(dc.behavior_bias or 0.0)
        w_behavior = self._safe_get_weight("behavior")

        aggregate = (
            w_trend * dc.trend +
            w_mom * dc.momentum +
            w_mr * dc.meanrev +
            w_bo * dc.breakout +
            w_behavior * behavior_bias
        )

        dc.aggregate_s = float(aggregate) * float(regime_scale)
        dc.reasons.append(
            f"Aggregate={dc.aggregate_s:.3f} "
            f"(regime_scale={regime_scale:.2f}, behavior_bias={behavior_bias:.3f})"
        )
        return dc

    # ---------------- MTF Confirmation ---------------- #

    def _mtf_confirm_pass(
        self,
        dc_primary: DecisionContext,
        dc_confirm: Optional[DecisionContext]
    ) -> Tuple[bool, List[str]]:
        """
        Veto-style MTF confirmation (best practice):
        - require_mtf_agreement=False → PASS
        - require_mtf_agreement=True → confirm TF only vetoes when it is *strongly opposite*
        - missing confirm TF does NOT reject
        """
        p = self.params
        reasons: List[str] = []

        if not p.require_mtf_agreement:
            reasons.append("MTF agreement not required")
            return True, reasons

        primary_s = float(dc_primary.aggregate_s)

        if dc_confirm is None:
            reasons.append("MTF missing → PASS (no veto)")
            return True, reasons

        confirm_s = float(dc_confirm.aggregate_s)

        veto_bar = max(float(p.decision_buffer) * 2.0, float(p.mtf_confirm_bar) * 0.35, 0.05)

        if primary_s > 0.0 and confirm_s < -veto_bar:
            reasons.append(
                f"MTF veto: primary={primary_s:.3f}, confirm={confirm_s:.3f}, veto_bar={veto_bar:.3f}"
            )
            return False, reasons

        if primary_s < 0.0 and confirm_s > veto_bar:
            reasons.append(
                f"MTF veto: primary={primary_s:.3f}, confirm={confirm_s:.3f}, veto_bar={veto_bar:.3f}"
            )
            return False, reasons

        reasons.append(f"MTF pass (no veto): primary={primary_s:.3f}, confirm={confirm_s:.3f}")
        return True, reasons

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

        # -------- Base thresholds (with buffer) --------
        buf = float(p.decision_buffer) if math.isfinite(p.decision_buffer) else 0.0
        base_buy_th = float(p.s_buy) - max(buf, 0.0)
        base_sell_th = float(p.s_sell) - max(buf, 0.0)

        # -------- Volatility-aware threshold adaptation --------
        vr: Optional[float] = None
        if dc_primary.vol_ratio is not None and math.isfinite(dc_primary.vol_ratio):
            vr = float(dc_primary.vol_ratio)
        else:
            # fallback from regime (keeps compatibility if vol_ratio isn't provided)
            vr = {"LOW": 0.85, "NEUTRAL": 1.0, "HIGH": 1.15}.get(dc_primary.regime or "NEUTRAL", 1.0)

        vr_shift = _clamp(
            (vr - 1.0) * float(p.vr_adapt_k),
            -float(p.vr_adapt_clamp),
            float(p.vr_adapt_clamp),
        )

        # High vr => easier entries (lower thresholds). Low vr => stricter.
        buy_th = base_buy_th - vr_shift
        sell_th = base_sell_th - vr_shift

        dc_primary.reasons.append(f"VR={vr:.3f} shift={vr_shift:+.3f} buy_th={buy_th:.3f} sell_th={sell_th:.3f}")

        # -------- MTF (veto-style) --------
        mtf_ok, mtf_reasons = self._mtf_confirm_pass(dc_primary, dc_confirm)
        dc_primary.reasons.extend(mtf_reasons)

        primary_s = float(dc_primary.aggregate_s)

        # -------- Volatility trade guard (avoid low-vol chop) --------
        low_vol_guard = (vr is not None) and math.isfinite(vr) and (vr < float(p.min_vr_trade))
        if low_vol_guard:
            dc_primary.reasons.append(
                f"VOL_GUARD: vr={vr:.3f} < min_vr_trade={float(p.min_vr_trade):.3f}"
            )

        entry = float(max(dc_primary.price, 0.0)) if math.isfinite(dc_primary.price) else 0.0
        atr = float(max(dc_primary.atr, 0.0)) if math.isfinite(dc_primary.atr) else 0.0

        # -------- FAST PATH: Trend + Breakout impulse --------
        adx_val = float(dc_primary.adx) if math.isfinite(dc_primary.adx) else 0.0
        trend_val = float(dc_primary.trend)
        bo_val = float(dc_primary.breakout)

        impulse = (
            abs(trend_val) >= 0.45 and
            abs(bo_val) >= 0.35 and
            adx_val >= float(p.min_adx_for_trend) and
            mtf_ok
        )

        if bool(getattr(p, "impulse_only_high", True)):
            impulse = impulse and (dc_primary.regime == "HIGH")

        if impulse and entry > 0.0:
            if trend_val > 0.0:
                action = "BUY"
                side = "LONG"
            else:
                action = "SELL"
                side = "SHORT"

            stop_price = self._build_stop(side, entry, atr, p.atr_stop_mult)
            pos = Position(side=side, qty=0.0, entry_price=entry, stop_price=stop_price)
            dc_primary.reasons.append(
                f"FAST_DECISION: impulse trend={trend_val:.3f} breakout={bo_val:.3f} adx={adx_val:.1f}"
            )
            return action, pos

        # If volatility is too low and no impulse, stand down.
        if low_vol_guard:
            dc_primary.reasons.append("VOL_GUARD: No impulse in low vr → HOLD")
            return "HOLD", None

        # -------- Normal threshold decision --------
        wants_long = (primary_s >= buy_th) and mtf_ok
        wants_short = (primary_s <= -sell_th) and mtf_ok

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
            dc_primary.reasons.append(f"HOLD: s={primary_s:.3f}, thresholds=({buy_th:.3f}, {-sell_th:.3f})")

        return action, pos
