# app/routers/v1/portfolios.py
from uuid import uuid4, UUID
from fastapi import APIRouter, HTTPException
from app.models.portfolio import PortfolioCreate, PortfolioSummary, PortfolioDetail, Visibility, PortfolioKind
from app.models.asset import AssetCreate, AssetSummary
from app.models.tx import TxCreate, TxItem
from app.models.timeseries import TimeseriesResponse, Timepoint
from datetime import datetime, timedelta
from decimal import Decimal

router = APIRouter()

# in-memory моки
_portfolios: dict[UUID, PortfolioDetail] = {}
_assets: dict[UUID, list[AssetSummary]] = {}
_txs: dict[UUID, list[TxItem]] = {}

@router.get("/portfolios", response_model=list[PortfolioSummary])
def list_portfolios():
    return list(_portfolios.values())

@router.post("/portfolios", response_model=PortfolioDetail, status_code=201)
def create_portfolio(body: PortfolioCreate):
    pid = uuid4()
    item = PortfolioDetail(
        id=pid,
        name=body.name,
        emoji=body.emoji,
        balance_usd=Decimal("0"),
        pnl_day_usd=Decimal("0"),
        kind=PortfolioKind.personal,
        visibility=body.visibility,
        created_at=datetime.utcnow(),
    )
    _portfolios[pid] = item
    _assets[pid] = []
    _txs[pid] = []
    return item

@router.get("/portfolios/{pid}", response_model=PortfolioDetail)
def get_portfolio(pid: UUID):
    if pid not in _portfolios:
        raise HTTPException(404, "Portfolio not found")
    return _portfolios[pid]

@router.delete("/portfolios/{pid}", status_code=204)
def delete_portfolio(pid: UUID):
    _portfolios.pop(pid, None)
    _assets.pop(pid, None)
    _txs.pop(pid, None)
    return

# Assets
@router.get("/portfolios/{pid}/assets", response_model=list[AssetSummary])
def list_assets(pid: UUID):
    return _assets.get(pid, [])

@router.post("/portfolios/{pid}/assets", response_model=AssetSummary, status_code=201)
def add_asset(pid: UUID, body: AssetCreate):
    aid = uuid4()
    item = AssetSummary(id=aid, symbol=body.symbol.upper(), display_name=body.display_name or body.symbol.upper(), emoji=body.emoji)
    _assets.setdefault(pid, []).append(item)
    return item

# Transactions
@router.get("/portfolios/{pid}/transactions", response_model=list[TxItem])
def list_transactions(pid: UUID):
    return _txs.get(pid, [])

@router.post("/portfolios/{pid}/transactions", response_model=TxItem, status_code=201)
def add_transaction(pid: UUID, body: TxCreate):
    tid = uuid4()
    item = TxItem(id=tid, **body.model_dump())
    _txs.setdefault(pid, []).append(item)
    return item

# Timeseries mock
@router.get("/portfolios/{pid}/timeseries", response_model=TimeseriesResponse)
def get_timeseries(pid: UUID, days: int = 14):
    now = datetime.utcnow()
    pts = [Timepoint(t=now - timedelta(days=i), balance_usd=Decimal(str(10000 + i * 123))) for i in range(days)][::-1]
    return TimeseriesResponse(points=pts)
