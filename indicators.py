# indicators.py

"""
================================================================================
Indicators with safeguards and light caching
================================================================================
- Replaces deprecated/invalid Series.fillna(method=...) usage with ffill()/bfill()
- Normalizes inputs, removes inf, and fills NaNs safely
- Keeps APIs: calculate_ema, calculate_rsi, calculate_adx, calculate_atr, donchian_channels
- Fixes smooth_vol_ratio to avoid fillna(method=None) error and zero-division
- Adds light edge-case handling and consistent numeric casting
================================================================================
"""

from typing import Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

_EPS = 1e-12


def _safe_series(s: pd.Series) -> pd.Series:
    """
    Ensure a numeric float series without infs and with NaNs forward/back filled.
    """
    # Coerce to float, handle non-numeric gracefully
    s = pd.to_numeric(s, errors="coerce").astype(float)
    # Replace infs with NaN, then forward/back fill
    s = s.replace([np.inf, -np.inf], np.nan)
    s = s.ffill().bfill()
    # In case the entire series was NaN, fallback to zeros
    if not np.isfinite(s.iloc[0]) or s.isna().all():
        s = s.fillna(0.0)
    return s


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Exponential moving average.
    """
    s = _safe_series(series)
    return s.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI).
    """
    s = _safe_series(series)
    delta = s.diff()

    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)

    roll_up = up.ewm(span=period, adjust=False).mean()
    roll_down = down.ewm(span=period, adjust=False).mean()

    rs = roll_up / (roll_down + _EPS)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Clamp RSI to [0, 100] defensively
    return rsi.clip(lower=0.0, upper=100.0)


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average Directional Index (ADX).
    Expects df to have columns: 'high', 'low', 'close'.
    """
    high = _safe_series(df["high"])
    low = _safe_series(df["low"])
    close = _safe_series(df["close"])

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.clip(lower=0.0)
    minus_dm = down_move.clip(lower=0.0)

    # Only keep the dominant movement per bar
    plus_dm = plus_dm.where(plus_dm >= minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    tr1 = (high - low)
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100.0 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / (atr + _EPS))
    minus_di = 100.0 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / (atr + _EPS))

    dx = 100.0 * (abs(plus_di - minus_di) / (plus_di + minus_di + _EPS))
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    # Clamp ADX to [0, 100]
    return adx.clip(lower=0.0, upper=100.0)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (ATR).
    Expects df to have columns: 'high', 'low', 'close'.
    """
    high = _safe_series(df["high"])
    low = _safe_series(df["low"])
    close = _safe_series(df["close"])

    tr1 = (high - low)
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    # Ensure non-negative ATR
    return atr.clip(lower=0.0)


def smooth_vol_ratio(atr: pd.Series, win_ma: int = 14, ema_span: int = 5) -> pd.Series:
    """
    Returns a smoothed volatility ratio series: vr = atr / atr_ma, then short EMA.
    - Robust to NaNs and zero denominators
    - No deprecated fillna(method=...) usage
    - Seeds early values to 1.0 (neutral)
    """
    atr = _safe_series(atr)

    # Moving average of ATR with partial windows allowed
    minp = max(1, win_ma // 2)
    atr_ma = atr.rolling(win_ma, min_periods=minp).mean()

    # Safe denominator: where atr_ma is NaN or near-zero, set NaN to be filled later
    safe_den = atr_ma.mask((atr_ma.abs() <= _EPS) | (atr_ma.isna()), other=np.nan)

    vr = atr / safe_den
    # Early/invalid values -> neutral 1.0, and clip to a sensible range
    vr = vr.fillna(1.0).clip(lower=0.1, upper=10.0)

    # Smooth with short EMA
    vr_smooth = vr.ewm(span=ema_span, adjust=False).mean()
    return vr_smooth


def donchian_channels(df: pd.DataFrame, period: int = 20) -> Tuple[pd.Series, pd.Series]:
    """
    Donchian channels upper/lower.
    Expects df to have columns: 'high', 'low'.
    Uses min_periods=period//2 for earlier availability with partial windows.
    """
    high = _safe_series(df["high"])
    low = _safe_series(df["low"])

    minp = max(1, period // 2)
    upper = high.rolling(period, min_periods=minp).max()
    lower = low.rolling(period, min_periods=minp).min()
    return upper, lower


@dataclass
class IndicatorCache:
    """
    Placeholder cache for future use if repeated rolling/windowed computations
    become a bottleneck. Not used currently.
    """
    store: dict = field(default_factory=dict)
