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

    # ---------------- Dynamic Weighting Based on Regime ---------------- #

    def _get_dynamic_weights(self, regime: str) -> Dict[str, float]:
        """
        Dynamic weighting based on regime:
        - LOW volatility: Increase meanrev weight, decrease trend
        - HIGH volatility: Increase breakout and behavior weights
        - NEUTRAL: Use base weights
        """
        base_weights = {
            "trend": self._safe_get_weight("trend"),
            "momentum": self._safe_get_weight("momentum"),
            "meanrev": self._safe_get_weight("meanrev"),
            "breakout": self._safe_get_weight("breakout"),
            "behavior": self._safe_get_weight("behavior"),
        }
        
        # Normalize base weights to sum to 1.0
        total = sum(base_weights.values())
        if total <= 0:
            return base_weights
        
        normalized = {k: v / total for k, v in base_weights.items()}
        
        # Apply regime-specific adjustments
        if regime == "LOW":
            # Increase meanrev, decrease trend
            normalized["meanrev"] *= 1.4
            normalized["trend"] *= 0.7
            normalized["breakout"] *= 0.8
        elif regime == "HIGH":
            # Increase breakout and behavior, decrease meanrev
            normalized["breakout"] *= 1.3
            normalized["behavior"] *= 1.2
            normalized["meanrev"] *= 0.6
            normalized["trend"] *= 1.1
        # NEUTRAL: keep normalized weights as-is
        
        # Renormalize after adjustments
        total = sum(normalized.values())
        if total > 0:
            normalized = {k: v / total for k, v in normalized.items()}
        
        return normalized

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

        # 3) Dynamic weights based on regime
        dynamic_weights = self._get_dynamic_weights(dc.regime)
        dc.reasons.append(
            f"Dynamic weights (regime={dc.regime}): "
            f"trend={dynamic_weights['trend']:.3f}, "
            f"meanrev={dynamic_weights['meanrev']:.3f}, "
            f"breakout={dynamic_weights['breakout']:.3f}, "
            f"behavior={dynamic_weights['behavior']:.3f}"
        )

        # 4) Regime scaling (for confidence threshold, not weights)
        regime_scale = p.regime_scale.get(dc.regime, 1.0)
        if not math.isfinite(regime_scale):
            regime_scale = 1.0

        # 5) مقدارهای post-gate
        dc.trend = float(trend_component)
        dc.momentum = float(mom)
        dc.meanrev = float(mr)
        dc.breakout = float(bo)

        # --- Behavior bias (Option C) ---
        behavior_bias = float(dc.behavior_bias or 0.0)
        
        # Use dynamic weights for aggregation
        aggregate = (
            dynamic_weights["trend"] * dc.trend +
            dynamic_weights["momentum"] * dc.momentum +
            dynamic_weights["meanrev"] * dc.meanrev +
            dynamic_weights["breakout"] * dc.breakout +
            dynamic_weights["behavior"] * behavior_bias
        )

        # Regime scale applies to aggregate (confidence multiplier)
        # Clamp aggregate_s to prevent low-liquidity spikes from causing extreme values
        raw_aggregate = float(aggregate) * float(regime_scale)
        dc.aggregate_s = _clamp(raw_aggregate, -2.0, 2.0)  # Robust against spikes
        
        if abs(raw_aggregate) > 2.0:
            dc.reasons.append(
                f"Aggregate clamped from {raw_aggregate:.3f} to {dc.aggregate_s:.3f} "
                f"(low-liquidity spike protection)"
            )
        
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

    # ---------------- Whale Gating ---------------- #

    def _check_whale_gate(
        self,
        dc_primary: DecisionContext,
        trend_val: float,
        primary_s: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Whale Gating: If VSA indicates "Supply Overcoming Demand" despite high trend,
        the final decision MUST be HOLD to avoid bull trap.
        
        Returns:
            (should_hold: bool, reason: Optional[str])
        """
        behavior_details = dc_primary.behavior_details
        
        if not behavior_details or not isinstance(behavior_details, dict):
            return False, None
        
        supply_overcoming = behavior_details.get("supply_overcoming_demand", False)
        vsa_signal = behavior_details.get("vsa_signal", "")
        whale_bias = behavior_details.get("whale_bias", 0.0)
        
        # Check if we have a bullish trend signal but bearish whale activity
        is_bullish_trend = trend_val > 0.3 and primary_s > 0.0
        is_bearish_whale = (
            supply_overcoming or
            vsa_signal == "DISTRIBUTION" or
            (vsa_signal == "ABSORPTION" and whale_bias < -0.3)
        )
        
        if is_bullish_trend and is_bearish_whale:
            reason = (
                f"WHALE_GATE: Bullish trend (trend={trend_val:.3f}, s={primary_s:.3f}) "
                f"but supply overcoming demand (VSA={vsa_signal}, whale_bias={whale_bias:.3f}) → HOLD"
            )
            return True, reason
        
        # Check if we have a bearish trend signal but bullish whale activity
        is_bearish_trend = trend_val < -0.3 and primary_s < 0.0
        is_bullish_whale = (
            vsa_signal == "ABSORPTION" and whale_bias > 0.3
        )
        
        if is_bearish_trend and is_bullish_whale:
            reason = (
                f"WHALE_GATE: Bearish trend (trend={trend_val:.3f}, s={primary_s:.3f}) "
                f"but bullish whale activity (VSA={vsa_signal}, whale_bias={whale_bias:.3f}) → HOLD"
            )
            return True, reason
        
        return False, None

    # ---------------- Final Decision (with Pattern Matching) ---------------- #

    def decide(
        self,
        dc_primary: DecisionContext,
        dc_confirm: Optional[DecisionContext]
    ) -> Tuple[str, Optional[Position]]:
        """
        Final decision with pattern matching for complex Regime + Trend + Whale Bias combinations.
        Uses Python 3.10+ match statement for clarity.
        
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

        # -------- Regime-based threshold scaling --------
        # Use regime_scale from config.py (0.7, 1.0, 1.3) as multipliers for confidence threshold
        # Note: aggregate_s is already scaled by regime_scale in gate_and_weight
        # Here we adjust thresholds inversely to maintain consistent entry difficulty
        regime_scale = p.regime_scale.get(dc_primary.regime, 1.0)
        if not math.isfinite(regime_scale):
            regime_scale = 1.0
        
        # Apply regime scale: HIGH (1.3) = easier entries (lower threshold), LOW (0.7) = stricter (higher threshold)
        buy_th = base_buy_th / regime_scale
        sell_th = base_sell_th / regime_scale

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
        buy_th = buy_th - vr_shift
        sell_th = sell_th - vr_shift

        dc_primary.reasons.append(
            f"Thresholds: buy_th={buy_th:.3f} sell_th={sell_th:.3f} "
            f"(regime_scale={regime_scale:.2f}, vr={vr:.3f}, vr_shift={vr_shift:+.3f})"
        )

        # -------- MTF (veto-style) --------
        mtf_ok, mtf_reasons = self._mtf_confirm_pass(dc_primary, dc_confirm)
        dc_primary.reasons.extend(mtf_reasons)

        primary_s = float(dc_primary.aggregate_s)
        trend_val = float(dc_primary.trend)

        # -------- Volatility trade guard (avoid low-vol chop) --------
        low_vol_guard = (vr is not None) and math.isfinite(vr) and (vr < float(p.min_vr_trade))
        if low_vol_guard:
            dc_primary.reasons.append(
                f"VOL_GUARD: vr={vr:.3f} < min_vr_trade={float(p.min_vr_trade):.3f}"
            )

        entry = float(max(dc_primary.price, 0.0)) if math.isfinite(dc_primary.price) else 0.0
        atr = float(max(dc_primary.atr, 0.0)) if math.isfinite(dc_primary.atr) else 0.0

        # -------- Whale Gating (check before any decision) --------
        whale_hold, whale_reason = self._check_whale_gate(dc_primary, trend_val, primary_s)
        if whale_hold and whale_reason:
            dc_primary.reasons.append(whale_reason)
            return "HOLD", None

        # -------- Pattern Matching for Decision Logic (Python 3.10+) --------
        adx_val = float(dc_primary.adx) if math.isfinite(dc_primary.adx) else 0.0
        bo_val = float(dc_primary.breakout)
        
        # Build decision pattern tuple for matching
        regime = dc_primary.regime or "NEUTRAL"
        trend_strength = abs(trend_val)
        breakout_strength = abs(bo_val)
        has_strong_trend = trend_strength >= 0.45 and adx_val >= float(p.min_adx_for_trend)
        has_strong_breakout = breakout_strength >= 0.35
        
        # Pattern matching (Python 3.10+)
        match (regime, has_strong_trend, has_strong_breakout, mtf_ok, low_vol_guard):
            # Fast path: Strong impulse in HIGH regime
            case ("HIGH", True, True, True, False) if entry > 0.0:
                side = "LONG" if trend_val > 0.0 else "SHORT"
                stop_price = self._build_stop(side, entry, atr, p.atr_stop_mult)
                pos = Position(side=side, qty=0.0, entry_price=entry, stop_price=stop_price)
                action = "BUY" if side == "LONG" else "SELL"
                dc_primary.reasons.append(
                    f"FAST_DECISION: HIGH regime impulse "
                    f"(trend={trend_val:.3f}, breakout={bo_val:.3f}, adx={adx_val:.1f})"
                )
                return action, pos
            
            # Low volatility guard
            case (_, _, _, _, True):
                dc_primary.reasons.append("VOL_GUARD: Low volatility → HOLD")
                return "HOLD", None
            
            # Normal threshold-based decision
            case _:
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
                    dc_primary.reasons.append(
                        f"HOLD: s={primary_s:.3f}, thresholds=({buy_th:.3f}, {-sell_th:.3f})"
                    )

        return action, pos
