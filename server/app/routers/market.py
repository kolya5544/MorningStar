from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.bybit import BybitService, BybitServiceError

router = APIRouter()
_service = BybitService()

_TTL = float(os.getenv("BYBIT_TICKER_TTL_SEC", "2.0"))
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


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

    try:
        data = _service.fetch_ticker(category=category, symbol=symbol)
    except BybitServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
    if not data:
        return None

    _cache[key] = (now, data)
    return BybitTicker(**data)


@router.get("/market/bybit/ticker/{base}", response_model=BybitTicker)
def bybit_ticker(
    base: str,
    category: str = Query(default="spot"),
    quote: str = Query(default="USDT"),
    fallback_linear: bool = Query(default=True),
):
    base = base.strip().upper()
    quote = quote.strip().upper()

    if not base or len(base) > 16:
        raise HTTPException(status_code=400, detail="Invalid base symbol")

    symbol = f"{base}{quote}"

    ticker = fetch_ticker(category, symbol)
    if ticker:
        return ticker

    if fallback_linear and category != "linear":
        ticker = fetch_ticker("linear", symbol)
        if ticker:
            return ticker

    raise HTTPException(status_code=404, detail=f"Ticker not found for {symbol}")
