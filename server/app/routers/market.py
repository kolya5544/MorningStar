# app/routers/market.py
from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pybit.unified_trading import HTTP

router = APIRouter()

# публичные market данные — ключи не нужны
_bybit = HTTP(testnet=os.getenv("BYBIT_TESTNET", "0") == "1")

_TTL = float(os.getenv("BYBIT_TICKER_TTL_SEC", "2.0"))
_cache: dict[tuple[str, str], tuple[float, dict]] = {}  # (category,symbol) -> (ts,data)


class BybitTicker(BaseModel):
    category: str
    symbol: str
    bid1Price: str
    bid1Size: str
    ask1Price: str
    ask1Size: str
    lastPrice: str
    prevPrice24h: str
    price24hPcnt: str
    highPrice24h: str
    lowPrice24h: str
    turnover24h: str
    volume24h: str
    usdIndexPrice: Optional[str] = None


def fetch_ticker(category: str, symbol: str) -> Optional[BybitTicker]:
    key = (category, symbol)
    now = time.time()

    hit = _cache.get(key)
    if hit and (now - hit[0]) < _TTL:
        return BybitTicker(**hit[1])

    r = _bybit.get_tickers(category=category, symbol=symbol)
    if r.get("retCode") != 0:
        raise HTTPException(status_code=502, detail=f"Bybit error: {r.get('retMsg')}")

    result = r.get("result") or {}
    lst = result.get("list") or []
    if not lst:
        return None

    it = lst[0]
    data = {
        "category": result.get("category") or category,
        "symbol": it.get("symbol") or symbol,
        "bid1Price": it.get("bid1Price") or "0",
        "bid1Size": it.get("bid1Size") or "0",
        "ask1Price": it.get("ask1Price") or "0",
        "ask1Size": it.get("ask1Size") or "0",
        "lastPrice": it.get("lastPrice") or "0",
        "prevPrice24h": it.get("prevPrice24h") or "0",
        "price24hPcnt": it.get("price24hPcnt") or "0",
        "highPrice24h": it.get("highPrice24h") or "0",
        "lowPrice24h": it.get("lowPrice24h") or "0",
        "turnover24h": it.get("turnover24h") or "0",
        "volume24h": it.get("volume24h") or "0",
        "usdIndexPrice": (it.get("usdIndexPrice") or None),
    }

    _cache[key] = (now, data)
    return BybitTicker(**data)


@router.get("/market/bybit/ticker/{base}", response_model=BybitTicker)
def bybit_ticker(
    base: str,
    category: str = Query(default="spot"),   # spot | linear | inverse | option
    quote: str = Query(default="USDT"),      # обычно USDT
    fallback_linear: bool = Query(default=True),
):
    base = base.strip().upper()
    quote = quote.strip().upper()

    if not base or len(base) > 16:
        raise HTTPException(status_code=400, detail="Invalid base symbol")

    symbol = f"{base}{quote}"  # PEPE + USDT => PEPEUSDT

    t = fetch_ticker(category, symbol)
    if t:
        return t

    # часто монета есть только в перпах: попробуем linear как fallback
    if fallback_linear and category != "linear":
        t = fetch_ticker("linear", symbol)
        if t:
            return t

    raise HTTPException(status_code=404, detail=f"Ticker not found for {symbol}")
