# -*- coding: utf-8 -*-
"""
SmartTrader Market Data Provider Interface
- Unified interface for multiple market data providers
- Fallback mechanism (wallex → coingecko → coincap)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

import requests

from wallex_client import WallexClient

logger = logging.getLogger(__name__)

# =====================================================================
# Provider Interface
# =====================================================================


class MarketDataProvider:
    """Base interface for market data providers."""

    def get_candles(self, symbol: str, tf: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Get OHLCV candles. Returns normalized format: [{time, open, high, low, close, volume}]"""
        raise NotImplementedError

    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest ticker data."""
        raise NotImplementedError

    def normalize_candle(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw candle to standard format."""
        raise NotImplementedError


# =====================================================================
# Wallex Provider (Existing)
# =====================================================================


class WallexProvider(MarketDataProvider):
    """Wallex provider using existing WallexClient."""

    def __init__(self):
        from config import WALLEX

        self.client = WallexClient(
            base_url=WALLEX["base_url"],
            api_key=WALLEX.get("api_key", ""),
            rate_limit_per_sec=WALLEX.get("rate_limit_per_sec", 4),
            retries=WALLEX.get("retries", 3),
            timeout=WALLEX.get("timeout", 10),
        )

    def get_candles(self, symbol: str, tf: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Get candles from Wallex."""
        candles = self.client.get_candles(symbol, tf, limit)
        if not candles:
            return None
        return [self.normalize_candle(c) for c in candles]

    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get ticker from Wallex."""
        return self.client.get_ticker(symbol)

    def normalize_candle(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Wallex candles are already in correct format."""
        return {
            "time": raw.get("time"),
            "open": raw.get("open"),
            "high": raw.get("high"),
            "low": raw.get("low"),
            "close": raw.get("close"),
            "volume": raw.get("volume", 0.0),
        }


# =====================================================================
# CoinGecko Provider (Fallback)
# =====================================================================


class CoinGeckoProvider(MarketDataProvider):
    """CoinGecko provider (free tier, no API key required)."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def get_candles(self, symbol: str, tf: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Get candles from CoinGecko."""
        # Map symbol to CoinGecko ID (simplified: assume BTC)
        coin_id = "bitcoin"  # Default to BTC
        if "BTC" in symbol.upper():
            coin_id = "bitcoin"

        # Map timeframe
        tf_map = {"1": "1m", "5": "5m", "60": "1h", "240": "4h", "D": "1d"}
        days = max(1, limit // 1440)  # Rough estimate

        try:
            url = f"{self.BASE_URL}/coins/{coin_id}/ohlc"
            params = {"vs_currency": "usd", "days": min(days, 365)}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                return None

            # CoinGecko format: [timestamp, open, high, low, close]
            candles = []
            for row in data[-limit:]:
                candles.append({
                    "time": row[0] // 1000,  # Convert ms to seconds
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": 0.0,  # CoinGecko OHLC doesn't include volume
                })
            return candles
        except Exception as e:
            logger.warning(f"CoinGecko provider error: {e}")
            return None

    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get ticker from CoinGecko."""
        coin_id = "bitcoin"
        if "BTC" in symbol.upper():
            coin_id = "bitcoin"

        try:
            url = f"{self.BASE_URL}/simple/price"
            params = {"ids": coin_id, "vs_currencies": "usd"}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            price = data.get(coin_id, {}).get("usd")
            if price:
                return {"last": price, "close": price}
            return None
        except Exception as e:
            logger.warning(f"CoinGecko ticker error: {e}")
            return None

    def normalize_candle(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize CoinGecko candle."""
        return raw


# =====================================================================
# CoinCap Provider (Second Fallback)
# =====================================================================


class CoinCapProvider(MarketDataProvider):
    """CoinCap provider (free tier)."""

    BASE_URL = "https://api.coincap.io/v2"

    def get_candles(self, symbol: str, tf: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Get candles from CoinCap."""
        # CoinCap uses asset IDs
        asset_id = "bitcoin"  # Default
        if "BTC" in symbol.upper():
            asset_id = "bitcoin"

        try:
            # CoinCap doesn't have direct OHLC endpoint in free tier
            # Use history endpoint instead
            url = f"{self.BASE_URL}/assets/{asset_id}/history"
            interval_map = {"1": "m1", "5": "m5", "60": "h1", "240": "h4", "D": "d1"}
            interval = interval_map.get(tf, "h1")
            params = {"interval": interval}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data:
                return None

            history = data["data"][-limit:]
            candles = []
            for h in history:
                price = float(h.get("priceUsd", 0))
                candles.append({
                    "time": int(h.get("time", 0)) // 1000,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": float(h.get("volumeUsd", 0)),
                })
            return candles
        except Exception as e:
            logger.warning(f"CoinCap provider error: {e}")
            return None

    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get ticker from CoinCap."""
        asset_id = "bitcoin"
        if "BTC" in symbol.upper():
            asset_id = "bitcoin"

        try:
            url = f"{self.BASE_URL}/assets/{asset_id}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if "data" in data:
                price = float(data["data"].get("priceUsd", 0))
                return {"last": price, "close": price}
            return None
        except Exception as e:
            logger.warning(f"CoinCap ticker error: {e}")
            return None

    def normalize_candle(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize CoinCap candle."""
        return raw


# =====================================================================
# Unified Fetcher
# =====================================================================


def get_market_data(
    symbol: str,
    tf: str,
    limit: int,
    provider: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Get market data with automatic fallback.
    provider: "wallex" | "coingecko" | "coincap" | None (auto-select)
    """
    providers = []
    if provider:
        provider_map = {
            "wallex": WallexProvider,
            "coingecko": CoinGeckoProvider,
            "coincap": CoinCapProvider,
        }
        if provider.lower() in provider_map:
            providers = [provider_map[provider.lower()]()]
    else:
        # Auto-select with fallback
        providers = [WallexProvider(), CoinGeckoProvider(), CoinCapProvider()]

    for prov in providers:
        try:
            candles = prov.get_candles(symbol, tf, limit)
            if candles:
                logger.info(f"Market data fetched from {prov.__class__.__name__}")
                return candles
        except Exception as e:
            logger.warning(f"Provider {prov.__class__.__name__} failed: {e}")
            continue

    logger.error("All market data providers failed")
    return None

