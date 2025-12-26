# -*- coding: utf-8 -*-
"""
SmartTrader Behavior Intelligence Engine
- Computes whale behavior proxies from market data
- Volume spikes, volatility shifts, momentum bursts
- Combined behavior score [0..100]
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

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
# Combined Behavior Score
# =====================================================================


def compute_behavior_score(
    symbol: str,
    market_data: List[Dict[str, Any]],
    volume_history: Optional[List[float]] = None,
    atr_history: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Compute combined behavior score and explanations.
    Returns:
    {
        "behavior_score": 0..100,
        "volume_spike_score": 0..100,
        "volatility_shift_score": 0..100,
        "momentum_burst_score": 0..100,
        "explanations": [...]
    }
    """
    if not market_data or len(market_data) < 20:
        return {
            "behavior_score": 0.0,
            "volume_spike_score": 0.0,
            "volatility_shift_score": 0.0,
            "momentum_burst_score": 0.0,
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

    # Compute individual scores
    vol_score = compute_volume_spike_score(volumes)
    vol_shift_score = compute_volatility_shift_score(atr_history) if atr_history else 0.0
    momentum_score = compute_momentum_burst_score(prices)

    # Weighted combination
    weights = {"volume": 0.3, "volatility": 0.35, "momentum": 0.35}
    behavior_score = (
        weights["volume"] * vol_score
        + weights["volatility"] * vol_shift_score
        + weights["momentum"] * momentum_score
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

    if not explanations:
        explanations.append("Market behavior within normal ranges")

    return {
        "behavior_score": float(behavior_score),
        "volume_spike_score": float(vol_score),
        "volatility_shift_score": float(vol_shift_score),
        "momentum_burst_score": float(momentum_score),
        "explanations": explanations,
    }

