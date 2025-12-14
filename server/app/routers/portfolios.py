# app/routers/v1/portfolios.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.orm_models import PortfolioORM, AssetORM, TxORM

from app.models.common import Visibility, PortfolioKind, TxType
from app.models.portfolio import PortfolioCreate, PortfolioSummary, PortfolioDetail
from app.models.asset import AssetCreate, AssetSummary
from app.models.tx import TxCreate, TxItem
from app.models.timeseries import TimeseriesResponse, Timepoint  # оставляем, чтобы фронт не ломался


router = APIRouter()


# ===== helpers =====

def _p_or_404(db: Session, pid: UUID) -> PortfolioORM:
    p = db.get(PortfolioORM, str(pid))
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return p

def _a_or_404(db: Session, pid: UUID, aid: UUID) -> AssetORM:
    a = db.get(AssetORM, str(aid))
    if not a or a.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="Asset not found")
    return a

def _portfolio_detail(p: PortfolioORM) -> PortfolioDetail:
    return PortfolioDetail(
        id=UUID(p.id),
        name=p.name,
        emoji=p.emoji,
        balance_usd=p.balance_usd,
        pnl_day_usd=p.pnl_day_usd,
        kind=p.kind,
        visibility=p.visibility,
        created_at=p.created_at,
    )

def _portfolio_summary(p: PortfolioORM) -> PortfolioSummary:
    return PortfolioSummary(
        id=UUID(p.id),
        name=p.name,
        emoji=p.emoji,
        balance_usd=p.balance_usd,
        pnl_day_usd=p.pnl_day_usd,
        kind=p.kind,
        visibility=p.visibility,
    )

def _asset_summary(a: AssetORM) -> AssetSummary:
    return AssetSummary(
        id=UUID(a.id),
        symbol=a.symbol,
        display_name=a.display_name,
        emoji=a.emoji,
    )

def _tx_item(t: TxORM) -> TxItem:
    return TxItem(
        id=UUID(t.id),
        asset_id=UUID(t.asset_id),
        type=t.type,
        quantity=t.quantity,
        price_usd=t.price_usd,
        fee_usd=t.fee_usd,
        at=t.at,
        note=t.note,
        tx_hash=t.tx_hash,
    )


# ===== update payloads (фронт не использует, но для CRUD полезно) =====

class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    emoji: Optional[str] = Field(default=None, max_length=8)
    visibility: Optional[Visibility] = None

class AssetUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=32)
    emoji: Optional[str] = Field(default=None, max_length=8)


# ===== Portfolios =====

@router.get("/portfolios", response_model=list[PortfolioSummary])
def list_portfolios(db: Session = Depends(get_db)):
    rows = db.execute(select(PortfolioORM).order_by(PortfolioORM.created_at.desc())).scalars().all()
    return [_portfolio_summary(p) for p in rows]

@router.post("/portfolios", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def create_portfolio(body: PortfolioCreate, db: Session = Depends(get_db)):
    p = PortfolioORM(
        name=body.name.strip(),
        emoji=(body.emoji.strip() if body.emoji else None),
        visibility=body.visibility,
        kind=PortfolioKind.personal,
        balance_usd=Decimal("0.00"),
        pnl_day_usd=Decimal("0.00"),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _portfolio_detail(p)

@router.get("/portfolios/{pid}", response_model=PortfolioDetail)
def get_portfolio(pid: UUID, db: Session = Depends(get_db)):
    return _portfolio_detail(_p_or_404(db, pid))

@router.put("/portfolios/{pid}", response_model=PortfolioDetail)
def update_portfolio(pid: UUID, body: PortfolioUpdate, db: Session = Depends(get_db)):
    p = _p_or_404(db, pid)

    if body.name is not None:
        p.name = body.name.strip()
    if body.emoji is not None:
        p.emoji = body.emoji.strip() if body.emoji else None
    if body.visibility is not None:
        p.visibility = body.visibility

    db.add(p)
    db.commit()
    db.refresh(p)
    return _portfolio_detail(p)

@router.delete("/portfolios/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(pid: UUID, db: Session = Depends(get_db)):
    p = _p_or_404(db, pid)
    db.delete(p)
    db.commit()
    return None


# ===== Assets =====

@router.get("/portfolios/{pid}/assets", response_model=list[AssetSummary])
def list_assets(pid: UUID, db: Session = Depends(get_db)):
    _p_or_404(db, pid)
    rows = db.execute(
        select(AssetORM).where(AssetORM.portfolio_id == str(pid)).order_by(AssetORM.symbol.asc())
    ).scalars().all()
    return [_asset_summary(a) for a in rows]

@router.post("/portfolios/{pid}/assets", response_model=AssetSummary, status_code=status.HTTP_201_CREATED)
def add_asset(pid: UUID, body: AssetCreate, db: Session = Depends(get_db)):
    _p_or_404(db, pid)

    symbol = body.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    a = AssetORM(
        portfolio_id=str(pid),
        symbol=symbol,
        display_name=(body.display_name.strip() if body.display_name else (symbol)),
        emoji=(body.emoji.strip() if body.emoji else None),
    )

    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Asset with this symbol already exists")
    db.refresh(a)
    return _asset_summary(a)

@router.put("/portfolios/{pid}/assets/{aid}", response_model=AssetSummary)
def update_asset(pid: UUID, aid: UUID, body: AssetUpdate, db: Session = Depends(get_db)):
    a = _a_or_404(db, pid, aid)

    if body.display_name is not None:
        a.display_name = body.display_name.strip() if body.display_name else None
    if body.emoji is not None:
        a.emoji = body.emoji.strip() if body.emoji else None

    db.add(a)
    db.commit()
    db.refresh(a)
    return _asset_summary(a)

@router.delete("/portfolios/{pid}/assets/{aid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(pid: UUID, aid: UUID, db: Session = Depends(get_db)):
    a = _a_or_404(db, pid, aid)
    db.delete(a)
    db.commit()
    return None


# ===== Transactions =====

@router.get("/portfolios/{pid}/transactions", response_model=list[TxItem])
def list_transactions(
    pid: UUID,
    asset_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    _p_or_404(db, pid)

    stmt = (
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .where(AssetORM.portfolio_id == str(pid))
    )

    if asset_id is not None:
        _a_or_404(db, pid, asset_id)
        stmt = stmt.where(TxORM.asset_id == str(asset_id))

    rows = db.execute(stmt.order_by(TxORM.at.desc())).scalars().all()
    return [_tx_item(t) for t in rows]

@router.put("/portfolios/{pid}/transactions/{tid}", response_model=TxItem)
def update_transaction(pid: UUID, tid: UUID, body: TxCreate, db: Session = Depends(get_db)):
    _p_or_404(db, pid)

    t = db.get(TxORM, str(tid))
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # tx должен принадлежать портфелю (через asset)
    a_old = db.get(AssetORM, t.asset_id)
    if not a_old or a_old.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="Transaction not found")

    # новый asset_id тоже обязан принадлежать этому портфелю
    _a_or_404(db, pid, body.asset_id)

    if body.quantity is None or Decimal(body.quantity) <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")
    if body.type in (TxType.buy, TxType.sell) and body.price_usd is None:
        raise HTTPException(status_code=400, detail="price_usd is required for buy/sell")

    t.asset_id = str(body.asset_id)
    t.type = body.type
    t.quantity = body.quantity
    t.price_usd = body.price_usd
    t.fee_usd = body.fee_usd
    t.at = body.at
    t.note = body.note
    t.tx_hash = body.tx_hash

    db.add(t)
    db.commit()
    db.refresh(t)
    return _tx_item(t)


@router.post("/portfolios/{pid}/transactions", response_model=TxItem, status_code=status.HTTP_201_CREATED)
def add_transaction(pid: UUID, body: TxCreate, db: Session = Depends(get_db)):
    _p_or_404(db, pid)

    # asset обязан принадлежать этому портфелю
    _a_or_404(db, pid, body.asset_id)

    # базовая валидация
    if body.quantity is None or Decimal(body.quantity) <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")

    if body.type in (TxType.buy, TxType.sell) and body.price_usd is None:
        raise HTTPException(status_code=400, detail="price_usd is required for buy/sell")

    t = TxORM(
        asset_id=str(body.asset_id),
        type=body.type,
        quantity=body.quantity,
        price_usd=body.price_usd,
        fee_usd=body.fee_usd,
        at=body.at,
        note=body.note,
        tx_hash=body.tx_hash,
    )

    db.add(t)
    db.commit()
    db.refresh(t)
    return _tx_item(t)

@router.delete("/portfolios/{pid}/transactions/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(pid: UUID, tid: UUID, db: Session = Depends(get_db)):
    _p_or_404(db, pid)
    t = db.get(TxORM, str(tid))
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # проверим принадлежность портфелю
    a = db.get(AssetORM, t.asset_id)
    if not a or a.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(t)
    db.commit()
    return None


# ===== Timeseries (оставляем, чтобы фронт не ломался) =====
# Сейчас это плоская линия по текущему balance_usd. Потом можно строить из tx/котировок.

@router.get("/portfolios/{pid}/timeseries", response_model=TimeseriesResponse)
def get_timeseries(pid: UUID, days: int = 14, db: Session = Depends(get_db)):
    p = _p_or_404(db, pid)

    now = datetime.now(timezone.utc)
    pts = [
        Timepoint(
            t=(now - timedelta(days=i)),
            balance_usd=p.balance_usd,
        )
        for i in range(max(1, days))
    ][::-1]

    return TimeseriesResponse(points=pts)
