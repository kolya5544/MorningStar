from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pybit.unified_trading import HTTP


class BybitServiceError(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


@dataclass
class BybitPortfolioSnapshot:
    holdings: dict[str, Decimal]
    prices: dict[str, Decimal]


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        self.max_requests = max_requests
        self.window_sec = window_sec
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            bucket = self._events.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window_sec:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                raise BybitServiceError("Bybit rate limit exceeded. Please retry later.", retryable=True)
            bucket.append(now)


class BybitService:
    def __init__(self) -> None:
        self.testnet = os.getenv("BYBIT_TESTNET", "0") == "1"
        self.timeout_sec = float(os.getenv("BYBIT_TIMEOUT_SEC", "8"))
        self.retries = max(1, int(os.getenv("BYBIT_RETRIES", "3")))
        self.retry_delay_sec = float(os.getenv("BYBIT_RETRY_DELAY_SEC", "0.6"))
        self.rate_limiter = InMemoryRateLimiter(
            max_requests=max(1, int(os.getenv("BYBIT_RATE_LIMIT_COUNT", "12"))),
            window_sec=float(os.getenv("BYBIT_RATE_LIMIT_WINDOW_SEC", "1")),
        )

    def _client(self, api_key: str | None = None, api_secret: str | None = None) -> HTTP:
        return HTTP(
            testnet=self.testnet,
            api_key=api_key,
            api_secret=api_secret,
            timeout=self.timeout_sec,
        )

    def _request(self, rate_key: str, fn: Callable[[], dict], *, where: str) -> dict:
        last_error: BybitServiceError | None = None
        for attempt in range(1, self.retries + 1):
            try:
                self.rate_limiter.acquire(rate_key)
                payload = fn()
                if not isinstance(payload, dict):
                    raise BybitServiceError(f"Invalid Bybit response at {where}", retryable=True)
                if payload.get("retCode") != 0:
                    raise BybitServiceError(
                        f"Bybit error at {where}: {payload.get('retMsg') or 'unknown error'}",
                        retryable=attempt < self.retries,
                    )
                return payload
            except BybitServiceError as exc:
                last_error = exc
            except Exception as exc:  # pragma: no cover
                last_error = BybitServiceError(
                    f"Bybit request failed at {where}: {exc}",
                    retryable=attempt < self.retries,
                )

            if attempt < self.retries and last_error and last_error.retryable:
                time.sleep(self.retry_delay_sec * attempt)
                continue
            break

        raise last_error or BybitServiceError("Bybit request failed")

    @staticmethod
    def _decimal_or_zero(value: object) -> Decimal:
        try:
            raw = str(value if value is not None else "0").strip()
            return Decimal(raw or "0")
        except Exception:
            return Decimal("0")

    def fetch_ticker(self, *, category: str, symbol: str) -> dict | None:
        client = self._client()
        payload = self._request(
            f"public:{category}:{symbol}",
            lambda: client.get_tickers(category=category, symbol=symbol),
            where=f"ticker {category}:{symbol}",
        )
        result = payload.get("result") or {}
        items = result.get("list") or []
        if not items:
            return None
        item = items[0]
        return {
            "category": result.get("category") or category,
            "symbol": item.get("symbol") or symbol,
            "bid1Price": item.get("bid1Price") or "0",
            "bid1Size": item.get("bid1Size") or "0",
            "ask1Price": item.get("ask1Price") or "0",
            "ask1Size": item.get("ask1Size") or "0",
            "lastPrice": item.get("lastPrice") or "0",
            "prevPrice24h": item.get("prevPrice24h") or "0",
            "price24hPcnt": item.get("price24hPcnt") or "0",
            "highPrice24h": item.get("highPrice24h") or "0",
            "lowPrice24h": item.get("lowPrice24h") or "0",
            "turnover24h": item.get("turnover24h") or "0",
            "volume24h": item.get("volume24h") or "0",
            "usdIndexPrice": item.get("usdIndexPrice") or None,
        }

    def fetch_portfolio_snapshot(self, *, api_key: str, api_secret: str) -> BybitPortfolioSnapshot:
        client = self._client(api_key=api_key, api_secret=api_secret)
        unified = self._request(
            f"private:{api_key}:wallet",
            lambda: client.get_wallet_balance(accountType="UNIFIED"),
            where="wallet-balance",
        )
        funding = self._request(
            f"private:{api_key}:fund",
            lambda: client.get_coins_balance(accountType="FUND"),
            where="fund-balance",
        )
        tickers = self._request(
            "public:spot:tickers",
            lambda: client.get_tickers(category="spot"),
            where="spot-tickers",
        )

        holdings: dict[str, Decimal] = {}
        for account in (((unified.get("result") or {}).get("list")) or []):
            for coin in account.get("coin") or []:
                symbol = (coin.get("coin") or "").strip().upper()
                balance = self._decimal_or_zero(coin.get("walletBalance"))
                if symbol and balance != 0:
                    holdings[symbol] = holdings.get(symbol, Decimal("0")) + balance

        for item in (((funding.get("result") or {}).get("balance")) or []):
            symbol = (item.get("coin") or "").strip().upper()
            balance = self._decimal_or_zero(item.get("walletBalance"))
            if symbol and balance != 0:
                holdings[symbol] = holdings.get(symbol, Decimal("0")) + balance

        prices: dict[str, Decimal] = {}
        for item in (((tickers.get("result") or {}).get("list")) or []):
            symbol = (item.get("symbol") or "").strip().upper()
            if not symbol.endswith("USDT"):
                continue
            base = symbol[:-4]
            last = self._decimal_or_zero(item.get("lastPrice"))
            if base and last > 0:
                prices[base] = last

        return BybitPortfolioSnapshot(holdings=holdings, prices=prices)
