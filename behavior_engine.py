# -*- coding: utf-8 -*-
"""
SmartTrader Behavior Intelligence Engine
- Computes whale behavior proxies from market data
- Volume Spread Analysis (VSA): Effort vs Result detection
- Relative Volume (RVOL): Time-of-day comparison
- Whale Bias (Delta): Institutional order flow tracking
- Combined behavior score [0..100] with whale intelligence
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
import math

logger = logging.getLogger(__name__)

# =====================================================================
# Volume Spike Score
# =====================================================================


def compute_volume_spike_score(volume_history: List[float], window: int = 20) -> float:
    """
    Compute volume spike score [0..100].
    Compares recent volume to rolling mean.
    """
    if not volume_history or len(volume_history) < window:
        return 0.0

    volumes = np.array(volume_history[-window:])
    if np.all(volumes == 0):
        return 0.0

    recent_volume = volumes[-1]
    mean_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else recent_volume

    if mean_volume <= 0:
        return 0.0

    ratio = recent_volume / mean_volume
    # Normalize: 1.0 = 50, 2.0 = 75, 3.0+ = 100
    score = min(100.0, max(0.0, 50.0 + (ratio - 1.0) * 25.0))
    return float(score)


# =====================================================================
# Volatility Shift Score
# =====================================================================


def compute_volatility_shift_score(atr_history: List[float], window: int = 20) -> float:
    """
    Compute volatility shift score [0..100].
    Measures ATR expansion vs rolling mean.
    """
    if not atr_history or len(atr_history) < window:
        return 0.0

    atrs = np.array(atr_history[-window:])
    if np.all(atrs == 0):
        return 0.0

    recent_atr = atrs[-1]
    mean_atr = np.mean(atrs[:-1]) if len(atrs) > 1 else recent_atr

    if mean_atr <= 0:
        return 0.0

    ratio = recent_atr / mean_atr
    # Normalize: 1.0 = 50, 1.5 = 75, 2.0+ = 100
    score = min(100.0, max(0.0, 50.0 + (ratio - 1.0) * 50.0))
    return float(score)


# =====================================================================
# Momentum Burst Score
# =====================================================================


def compute_momentum_burst_score(price_history: List[float], window: int = 10) -> float:
    """
    Compute momentum burst score [0..100].
    Measures price impulse strength (rate of change).
    """
    if not price_history or len(price_history) < window:
        return 0.0

    prices = np.array(price_history[-window:])
    if len(prices) < 2:
        return 0.0

    # Compute returns
    returns = np.diff(prices) / prices[:-1]
    if len(returns) == 0:
        return 0.0

    # Recent return magnitude
    recent_return = abs(returns[-1]) if len(returns) > 0 else 0.0
    mean_return = np.mean(np.abs(returns[:-1])) if len(returns) > 1 else recent_return

    if mean_return <= 0:
        return 0.0

    ratio = recent_return / mean_return if mean_return > 0 else 0.0
    # Normalize: 1.0 = 50, 2.0 = 75, 3.0+ = 100
    score = min(100.0, max(0.0, 50.0 + (ratio - 1.0) * 25.0))
    return float(score)


# =====================================================================
# Volume Spread Analysis (VSA)
# =====================================================================


def compute_vsa_absorption(
    market_data: List[Dict[str, Any]],
    window: int = 20
) -> Tuple[float, str]:
    """
    VSA: Detect "Effort vs Result" - High volume with small spread = Absorption (Whale activity).
    
    Returns:
        (absorption_score: float, signal: str)
        - absorption_score: 0..100 (higher = stronger absorption)
        - signal: "ABSORPTION", "DISTRIBUTION", "NORMAL", "NO_DATA"
    """
    if not market_data or len(market_data) < window:
        return 0.0, "NO_DATA"
    
    # Extract recent candles
    recent = market_data[-window:]
    
    volumes = []
    spreads = []
    
    for candle in recent:
        vol = float(candle.get("volume", 0.0))
        high = float(candle.get("high", candle.get("close", 0.0)))
        low = float(candle.get("low", candle.get("close", 0.0)))
        spread = high - low
        
        if vol > 0 and spread > 0:
            volumes.append(vol)
            spreads.append(spread)
    
    if len(volumes) < 5:
        return 0.0, "NO_DATA"
    
    # Current candle (most recent)
    current_vol = volumes[-1]
    current_spread = spreads[-1]
    
    # Historical averages
    avg_vol = np.mean(volumes[:-1]) if len(volumes) > 1 else current_vol
    avg_spread = np.mean(spreads[:-1]) if len(spreads) > 1 else current_spread
    
    if avg_vol <= 0 or avg_spread <= 0:
        return 0.0, "NORMAL"
    
    # Effort vs Result ratio
    vol_ratio = current_vol / avg_vol
    spread_ratio = current_spread / avg_spread if avg_spread > 0 else 1.0
    
    # High effort (volume) but low result (spread) = Absorption
    effort_result_ratio = vol_ratio / (spread_ratio + 1e-6)
    
    # Normalize to 0-100 score
    # effort_result_ratio > 2.0 = strong absorption
    absorption_score = min(100.0, max(0.0, (effort_result_ratio - 1.0) * 50.0))
    
    # Determine signal
    if effort_result_ratio > 2.0 and vol_ratio > 1.5:
        signal = "ABSORPTION"
    elif effort_result_ratio < 0.5 and vol_ratio > 1.5:
        signal = "DISTRIBUTION"
    else:
        signal = "NORMAL"
    
    return float(absorption_score), signal


# =====================================================================
# Relative Volume (RVOL) - Time-of-Day Comparison
# =====================================================================


def compute_relative_volume(
    market_data: List[Dict[str, Any]],
    window: int = 50
) -> float:
    """
    RVOL: Compare current volume to average of same time-of-day in previous sessions.
    Returns RVOL ratio (1.0 = average, >1.0 = above average, <1.0 = below average).
    """
    if not market_data or len(market_data) < window:
        return 1.0
    
    # Extract timestamps and volumes
    candles_with_time = []
    for candle in market_data:
        time_val = candle.get("time")
        if time_val is None:
            continue
        vol = float(candle.get("volume", 0.0))
        if vol > 0:
            candles_with_time.append((time_val, vol))
    
    if len(candles_with_time) < window:
        return 1.0
    
    # Get current candle time (hour of day)
    current_time = candles_with_time[-1][0]
    try:
        current_dt = datetime.fromtimestamp(current_time, tz=timezone.utc)
        current_hour = current_dt.hour
    except Exception:
        return 1.0
    
    # Find candles at same hour of day (within ±1 hour tolerance)
    same_hour_volumes = []
    for ts, vol in candles_with_time[:-1]:  # Exclude current
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            hour = dt.hour
            if abs(hour - current_hour) <= 1:  # ±1 hour tolerance
                same_hour_volumes.append(vol)
        except Exception:
            continue
    
    if len(same_hour_volumes) < 5:
        # Fallback to simple rolling average
        volumes = [v for _, v in candles_with_time[-window:-1]]
        if len(volumes) < 5:
            return 1.0
        avg_vol = np.mean(volumes)
    else:
        avg_vol = np.mean(same_hour_volumes)
    
    current_vol = candles_with_time[-1][1]
    
    if avg_vol <= 0:
        return 1.0
    
    rvol = current_vol / avg_vol
    return float(np.clip(rvol, 0.1, 10.0))  # Clamp to reasonable range


# =====================================================================
# Whale Bias (Delta Tracking)
# =====================================================================


def compute_whale_bias(
    market_data: List[Dict[str, Any]],
    window: int = 20
) -> Tuple[float, str]:
    """
    Whale Bias: Track if big buy orders are absorbing sell-side liquidity.
    Uses price action and volume to infer institutional order flow.
    
    Returns:
        (whale_bias: float, direction: str)
        - whale_bias: -1.0 (strong sell pressure) to +1.0 (strong buy pressure)
        - direction: "BULLISH", "BEARISH", "NEUTRAL"
    """
    if not market_data or len(market_data) < window:
        return 0.0, "NEUTRAL"
    
    recent = market_data[-window:]
    
    # Calculate price change and volume for each candle
    deltas = []
    volumes = []
    
    for i, candle in enumerate(recent):
        close = float(candle.get("close", 0.0))
        open_price = float(candle.get("open", close))
        high = float(candle.get("high", close))
        low = float(candle.get("low", close))
        vol = float(candle.get("volume", 0.0))
        
        if vol <= 0:
            continue
        
        # Price change (normalized by price)
        price_change = (close - open_price) / (open_price + 1e-6)
        
        # Volume-weighted price action
        # Positive change with high volume = buy pressure
        # Negative change with high volume = sell pressure
        delta = price_change * min(vol / 1e6, 1.0)  # Normalize volume impact
        
        deltas.append(delta)
        volumes.append(vol)
    
    if len(deltas) < 5:
        return 0.0, "NEUTRAL"
    
    # Weight recent candles more heavily
    weights = np.exp(np.linspace(-2, 0, len(deltas)))  # Exponential decay
    weighted_delta = np.average(deltas, weights=weights)
    
    # Normalize to -1..+1 range
    whale_bias = float(np.tanh(weighted_delta * 10.0))
    
    # Determine direction
    if whale_bias > 0.3:
        direction = "BULLISH"
    elif whale_bias < -0.3:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return whale_bias, direction


# =====================================================================
# Combined Behavior Score (Enhanced with VSA, RVOL, Whale Bias)
# =====================================================================


def compute_behavior_score(
    symbol: str,
    market_data: List[Dict[str, Any]],
    volume_history: Optional[List[float]] = None,
    atr_history: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Compute combined behavior score with VSA, RVOL, and Whale Bias.
    Returns:
    {
        "behavior_score": 0..100,
        "volume_spike_score": 0..100,
        "volatility_shift_score": 0..100,
        "momentum_burst_score": 0..100,
        "vsa_absorption_score": 0..100,
        "vsa_signal": "ABSORPTION" | "DISTRIBUTION" | "NORMAL" | "NO_DATA",
        "rvol": float,  # Relative volume ratio
        "whale_bias": -1.0..+1.0,
        "whale_direction": "BULLISH" | "BEARISH" | "NEUTRAL",
        "supply_overcoming_demand": bool,  # True if VSA indicates supply > demand despite trend
        "explanations": [...]
    }
    """
    if not market_data or len(market_data) < 20:
        return {
            "behavior_score": 0.0,
            "volume_spike_score": 0.0,
            "volatility_shift_score": 0.0,
            "momentum_burst_score": 0.0,
            "vsa_absorption_score": 0.0,
            "vsa_signal": "NO_DATA",
            "rvol": 1.0,
            "whale_bias": 0.0,
            "whale_direction": "NEUTRAL",
            "supply_overcoming_demand": False,
            "explanations": ["Insufficient market data"],
        }

    # Extract data
    volumes = volume_history or [float(d.get("volume", 0.0)) for d in market_data]
    prices = [float(d.get("close", d.get("price", 0.0))) for d in market_data if d.get("close") or d.get("price")]

    # Compute ATR from price data if not provided
    if atr_history is None:
        atr_history = []
        for i in range(1, len(prices)):
            high = float(market_data[i].get("high", prices[i]))
            low = float(market_data[i].get("low", prices[i]))
            atr_history.append(high - low)

    # Compute legacy scores
    vol_score = compute_volume_spike_score(volumes)
    vol_shift_score = compute_volatility_shift_score(atr_history) if atr_history else 0.0
    momentum_score = compute_momentum_burst_score(prices)
    
    # Compute new VSA, RVOL, and Whale Bias
    vsa_score, vsa_signal = compute_vsa_absorption(market_data)
    rvol = compute_relative_volume(market_data)
    whale_bias, whale_direction = compute_whale_bias(market_data)
    
    # Determine if supply is overcoming demand (bearish VSA signal)
    supply_overcoming_demand = (
        vsa_signal == "DISTRIBUTION" or 
        (vsa_signal == "ABSORPTION" and whale_bias < -0.2)
    )

    # Enhanced weighted combination (include VSA and whale bias)
    weights = {
        "volume": 0.20,
        "volatility": 0.25,
        "momentum": 0.20,
        "vsa": 0.20,
        "whale": 0.15
    }
    
    # Convert whale_bias to 0-100 score
    whale_score = 50.0 + (whale_bias * 25.0)  # -1.0 -> 25, 0.0 -> 50, +1.0 -> 75
    
    behavior_score = (
        weights["volume"] * vol_score
        + weights["volatility"] * vol_shift_score
        + weights["momentum"] * momentum_score
        + weights["vsa"] * vsa_score
        + weights["whale"] * whale_score
    )

    # Generate explanations
    explanations = []
    
    if vol_score > 60:
        recent_vol = volumes[-1] if volumes else 0
        mean_vol = np.mean(volumes[:-1]) if len(volumes) > 1 else recent_vol
        ratio = recent_vol / mean_vol if mean_vol > 0 else 0
        explanations.append(f"Volume increased {ratio:.1f}x above average (spike score: {vol_score:.1f})")
    elif vol_score < 40:
        explanations.append(f"Volume below average (spike score: {vol_score:.1f})")

    if vol_shift_score > 60:
        recent_atr = atr_history[-1] if atr_history else 0
        mean_atr = np.mean(atr_history[:-1]) if len(atr_history) > 1 else recent_atr
        ratio = recent_atr / mean_atr if mean_atr > 0 else 0
        explanations.append(f"ATR expansion indicates high volatility (shift score: {vol_shift_score:.1f}, ratio: {ratio:.2f}x)")
    elif vol_shift_score < 40:
        explanations.append(f"Low volatility environment (shift score: {vol_shift_score:.1f})")

    if momentum_score > 60:
        explanations.append(f"Strong price impulse detected (momentum score: {momentum_score:.1f})")
    elif momentum_score < 40:
        explanations.append(f"Weak momentum (momentum score: {momentum_score:.1f})")
    
    # VSA explanations
    if vsa_signal == "ABSORPTION":
        explanations.append(f"VSA: Absorption detected (score: {vsa_score:.1f}) - High volume, small spread = Whale activity")
    elif vsa_signal == "DISTRIBUTION":
        explanations.append(f"VSA: Distribution detected (score: {vsa_score:.1f}) - Supply overcoming demand")
    
    # RVOL explanations
    if rvol > 1.5:
        explanations.append(f"RVOL: {rvol:.2f}x - Volume significantly above same-time-of-day average")
    elif rvol < 0.7:
        explanations.append(f"RVOL: {rvol:.2f}x - Volume below same-time-of-day average")
    
    # Whale bias explanations
    if whale_direction == "BULLISH":
        explanations.append(f"Whale Bias: {whale_bias:+.2f} ({whale_direction}) - Institutional buy pressure")
    elif whale_direction == "BEARISH":
        explanations.append(f"Whale Bias: {whale_bias:+.2f} ({whale_direction}) - Institutional sell pressure")
    
    if supply_overcoming_demand:
        explanations.append("⚠️ Supply overcoming demand - Potential reversal signal")

    if not explanations:
        explanations.append("Market behavior within normal ranges")

    return {
        "behavior_score": float(behavior_score),
        "volume_spike_score": float(vol_score),
        "volatility_shift_score": float(vol_shift_score),
        "momentum_burst_score": float(momentum_score),
        "vsa_absorption_score": float(vsa_score),
        "vsa_signal": vsa_signal,
        "rvol": float(rvol),
        "whale_bias": float(whale_bias),
        "whale_direction": whale_direction,
        "supply_overcoming_demand": supply_overcoming_demand,
        "explanations": explanations,
    }

