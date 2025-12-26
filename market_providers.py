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
from dataclasses import dataclass

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


# =====================================================================
# Market Data Gateway (Unified with Provider Tracking)
# =====================================================================


@dataclass
class MarketDataResponse:
    """Structured response from market data gateway."""
    data: Optional[List[Dict[str, Any]]]
    provider: str  # "wallex" | "coingecko" | "coincap" | "none"
    confidence: float  # 0.0-1.0 (1.0 = primary provider, lower = fallback)
    fallback_used: bool
    error: Optional[str] = None


class MarketDataGateway:
    """
    Unified gateway for market data with explicit provider tracking and logging.
    Used by API endpoints. Trading engine (main.py) continues using WallexClient directly.
    """

    def __init__(self, preferred_provider: Optional[str] = None):
        """
        Initialize gateway.
        preferred_provider: "wallex" | "coingecko" | "coincap" | None (auto-select)
        """
        self.preferred_provider = preferred_provider
        self._providers = {
            "wallex": WallexProvider,
            "coingecko": CoinGeckoProvider,
            "coincap": CoinCapProvider,
        }

    def get_candles(
        self,
        symbol: str,
        tf: str,
        limit: int,
        required_provider: Optional[str] = None,
    ) -> MarketDataResponse:
        """
        Get candles with explicit provider tracking and fallback logging.
        Returns MarketDataResponse with provider metadata.
        """
        provider_name = required_provider or self.preferred_provider

        if provider_name:
            # Single provider requested
            if provider_name.lower() not in self._providers:
                logger.error(f"Unknown provider requested: {provider_name}")
                return MarketDataResponse(
                    data=None,
                    provider="none",
                    confidence=0.0,
                    fallback_used=False,
                    error=f"Unknown provider: {provider_name}",
                )

            try:
                prov = self._providers[provider_name.lower()]()
                logger.info(f"[Gateway] Attempting {provider_name} for {symbol} {tf}")
                candles = prov.get_candles(symbol, tf, limit)
                if candles:
                    logger.info(f"[Gateway] ✓ {provider_name} succeeded: {len(candles)} candles")
                    return MarketDataResponse(
                        data=candles,
                        provider=provider_name.lower(),
                        confidence=1.0,
                        fallback_used=False,
                    )
                else:
                    logger.warning(f"[Gateway] ✗ {provider_name} returned no data")
                    return MarketDataResponse(
                        data=None,
                        provider=provider_name.lower(),
                        confidence=0.0,
                        fallback_used=False,
                        error=f"{provider_name} returned no data",
                    )
            except Exception as e:
                logger.error(f"[Gateway] ✗ {provider_name} failed: {e}")
                return MarketDataResponse(
                    data=None,
                    provider=provider_name.lower(),
                    confidence=0.0,
                    fallback_used=False,
                    error=str(e),
                )

        # Auto-select with fallback (wallex → coingecko → coincap)
        providers_order = ["wallex", "coingecko", "coincap"]
        attempted = []

        for idx, prov_name in enumerate(providers_order):
            try:
                prov = self._providers[prov_name]()
                logger.info(f"[Gateway] Attempting {prov_name} (attempt {idx + 1}/{len(providers_order)}) for {symbol} {tf}")
                attempted.append(prov_name)

                candles = prov.get_candles(symbol, tf, limit)
                if candles:
                    confidence = 1.0 - (idx * 0.2)  # Primary = 1.0, first fallback = 0.8, second = 0.6
                    fallback_used = idx > 0

                    if fallback_used:
                        logger.warning(
                            f"[Gateway] ✓ {prov_name} succeeded (FALLBACK, attempt {idx + 1}). "
                            f"Previous attempts: {', '.join(attempted[:-1])}"
                        )
                    else:
                        logger.info(f"[Gateway] ✓ {prov_name} succeeded (PRIMARY)")

                    return MarketDataResponse(
                        data=candles,
                        provider=prov_name,
                        confidence=confidence,
                        fallback_used=fallback_used,
                    )
                else:
                    logger.warning(f"[Gateway] ✗ {prov_name} returned no data, trying next...")

            except Exception as e:
                logger.warning(f"[Gateway] ✗ {prov_name} failed: {e}, trying next...")
                continue

        # All providers failed
        logger.error(
            f"[Gateway] ✗ ALL PROVIDERS FAILED for {symbol} {tf}. "
            f"Attempted: {', '.join(attempted)}"
        )
        return MarketDataResponse(
            data=None,
            provider="none",
            confidence=0.0,
            fallback_used=True,
            error=f"All providers failed. Attempted: {', '.join(attempted)}",
        )

    def get_ticker(
        self,
        symbol: str,
        required_provider: Optional[str] = None,
    ) -> MarketDataResponse:
        """
        Get ticker with explicit provider tracking.
        Returns MarketDataResponse with ticker data in .data field.
        """
        provider_name = required_provider or self.preferred_provider

        if provider_name:
            if provider_name.lower() not in self._providers:
                return MarketDataResponse(
                    data=None,
                    provider="none",
                    confidence=0.0,
                    fallback_used=False,
                    error=f"Unknown provider: {provider_name}",
                )

            try:
                prov = self._providers[provider_name.lower()]()
                ticker = prov.get_ticker(symbol)
                if ticker:
                    return MarketDataResponse(
                        data=[ticker],  # Wrap in list for consistency
                        provider=provider_name.lower(),
                        confidence=1.0,
                        fallback_used=False,
                    )
            except Exception as e:
                logger.error(f"[Gateway] Ticker fetch from {provider_name} failed: {e}")

        # Fallback chain
        for idx, prov_name in enumerate(["wallex", "coingecko", "coincap"]):
            try:
                prov = self._providers[prov_name]()
                ticker = prov.get_ticker(symbol)
                if ticker:
                    return MarketDataResponse(
                        data=[ticker],
                        provider=prov_name,
                        confidence=1.0 - (idx * 0.2),
                        fallback_used=idx > 0,
                    )
            except Exception:
                continue

        return MarketDataResponse(
            data=None,
            provider="none",
            confidence=0.0,
            fallback_used=True,
            error="All providers failed for ticker",
        )

