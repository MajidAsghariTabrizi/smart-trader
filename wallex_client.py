# wallex_client.py

"""
================================================================================
Wallex Client - resilient HTTP client with basic rate limiting and retries
Uses UDF history endpoint: /v1/udf/history?symbol=...&resolution=...&from=...&to=...
================================================================================
"""

import time
import threading
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger("smart_trader")

class RateLimiter:
    def __init__(self, rate_per_sec: float):
        self.interval = 1.0 / max(rate_per_sec, 0.1)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            now = time.time()
            delta = now - self._last
            if delta < self.interval:
                time.sleep(self.interval - delta)
            self._last = time.time()

def _tf_minutes(tf_str: str) -> int:
    # Accept strings like "1","5","60","240","D" etc. Map D to 1440 if needed.
    s = str(tf_str).upper().strip()
    if s == "D":
        return 1440
    return int(s)

class WallexClient:
    def __init__(self, base_url: str, api_key: str, timeout: int, retries: int, rate_limit_per_sec: float):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = max(retries, 0)
        self.rate_limiter = RateLimiter(rate_limit_per_sec)

        self._session = requests.Session()
        # Wallex UDF endpoints generally don’t need auth, keep header optional
        if self.api_key:
            # Some endpoints may require a header; keep it harmless
            self._session.headers.update({"x-api-key": self.api_key})

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self.retries + 1):
            try:
                self.rate_limiter.wait()
                resp = self._session.request(method, url, params=params, timeout=self.timeout)
                if resp.status_code >= 500:
                    raise requests.RequestException(f"Server error {resp.status_code}")
                if resp.status_code == 429:
                    sleep_s = 1.0 + attempt
                    logger.warning(f"429 rate limited by server. Sleeping {sleep_s:.1f}s")
                    time.sleep(sleep_s)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt >= self.retries:
                    logger.error(f"Wallex request failed after {attempt+1} attempts: {e}")
                    return None
                backoff = 0.5 * (attempt + 1)
                logger.warning(f"Wallex request failed (attempt {attempt+1}), retrying in {backoff:.1f}s: {e}")
                time.sleep(backoff)
        return None

    def _compute_window(self, tf_min: str, limit: int) -> Tuple[int, int]:
        # Compute [from, to] in epoch seconds to roughly cover limit candles
        now = datetime.now(timezone.utc)
        tf_minutes = _tf_minutes(tf_min)
        span_minutes = tf_minutes * max(limit + 5, limit)  # a bit extra to ensure enough candles
        start = now - timedelta(minutes=span_minutes)
        return int(start.timestamp()), int(now.timestamp())

    def get_candles(self, symbol: str, tf_min: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        # Call UDF history endpoint
        from_ts, to_ts = self._compute_window(tf_min, limit)
        data = self._request(
            "GET",
            "v1/udf/history",
            params={"symbol": symbol, "resolution": str(tf_min), "from": from_ts, "to": to_ts},
        )
        if not data:
            return None

        # UDF shape: s: "ok"|"no_data", t:[], o:[], h:[], l:[], c:[], v:[]
        if data.get("s") not in ("ok", "no_data"):
            logger.warning(f"Unexpected UDF status: {data.get('s')}")
            return None
        if data.get("s") == "no_data":
            return []

        t = data.get("t", [])
        o = data.get("o", [])
        h = data.get("h", [])
        l = data.get("l", [])
        c = data.get("c", [])
        v = data.get("v", []) or [0.0] * len(t)

        n = min(len(t), len(o), len(h), len(l), len(c), len(v))
        if n == 0:
            return []
        # keep only last `limit`
        start_idx = max(0, n - limit)
        result = []
        for i in range(start_idx, n):
            try:
                result.append({
                    "time": int(t[i]),
                    "open": float(o[i]),
                    "high": float(h[i]),
                    "low": float(l[i]),
                    "close": float(c[i]),
                    "volume": float(v[i]) if i < len(v) else 0.0,
                })
            except Exception:
                continue
        return result

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        # If you have a proper ticker endpoint, implement here.
        # As a safe fallback, return empty and let caller handle it or derive from last candle.
        return {}
