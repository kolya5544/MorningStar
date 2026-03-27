from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional
from uuid import UUID

from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_user
from app.db import get_db
from app.models.asset import AssetCreate, AssetSummary
from app.models.common import PortfolioKind, Role, TxType, Visibility
from app.models.file import (
    PortfolioFileDownloadResponse,
    PortfolioFileItem,
    PortfolioFileUploadRequest,
)
from app.models.portfolio import (
    PortfolioCreate,
    PortfolioDetail,
    PortfolioListResponse,
    PortfolioSummary,
)
from app.models.timeseries import Timepoint, TimeseriesResponse
from app.models.tx import TxCreate, TxItem
from app.orm_models import AssetORM, PortfolioFileORM, PortfolioORM, TxORM, UserORM
from app.routers.market import fetch_ticker
from app.services.object_storage import (
    MAX_FILE_SIZE_BYTES,
    ObjectStorageError,
    ObjectStorageService,
)
from app.services.bybit import BybitService, BybitServiceError

router = APIRouter()
bybit_service = BybitService()

PortfolioSortField = Literal["created_at", "name", "balance_usd"]
SortDirection = Literal["asc", "desc"]


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _positions_by_asset(db: Session, portfolio_id: str) -> dict[str, Decimal]:
    rows = db.execute(
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .where(AssetORM.portfolio_id == portfolio_id)
    ).scalars().all()

    positions: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for tx in rows:
        if tx.type in (TxType.buy, TxType.transfer_in):
            positions[tx.asset_id] += tx.quantity
        else:
            positions[tx.asset_id] -= tx.quantity
    return dict(positions)


def _user_and_role(request: Request) -> tuple[str, Role]:
    payload = require_user(request)
    return str(payload["sub"]), Role(payload["role"])


def _p_or_404(db: Session, pid: UUID, user_id: str) -> PortfolioORM:
    portfolio = db.get(PortfolioORM, str(pid))
    if not portfolio or portfolio.user_id != user_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


def _a_or_404(db: Session, pid: UUID, aid: UUID, user_id: str) -> AssetORM:
    stmt = (
        select(AssetORM)
        .join(PortfolioORM, AssetORM.portfolio_id == PortfolioORM.id)
        .where(
            AssetORM.id == str(aid),
            AssetORM.portfolio_id == str(pid),
            PortfolioORM.user_id == user_id,
        )
    )
    asset = db.execute(stmt).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _t_or_404(db: Session, pid: UUID, tid: UUID, user_id: str) -> TxORM:
    stmt = (
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .join(PortfolioORM, AssetORM.portfolio_id == PortfolioORM.id)
        .where(
            TxORM.id == str(tid),
            AssetORM.portfolio_id == str(pid),
            PortfolioORM.user_id == user_id,
        )
    )
    tx = db.execute(stmt).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


def _require_owner_level_write(request: Request) -> tuple[str, Role]:
    user_id, role = _user_and_role(request)
    if role not in (Role.user, Role.manager, Role.admin):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_id, role


def _p_for_write(db: Session, pid: UUID, user_id: str, role: Role) -> PortfolioORM:
    if role == Role.admin:
        portfolio = db.get(PortfolioORM, str(pid))
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return portfolio
    return _p_or_404(db, pid, user_id)


def _a_for_write(db: Session, pid: UUID, aid: UUID, user_id: str, role: Role) -> AssetORM:
    if role == Role.admin:
        asset = db.get(AssetORM, str(aid))
        if not asset or asset.portfolio_id != str(pid):
            raise HTTPException(status_code=404, detail="Asset not found")
        return asset
    return _a_or_404(db, pid, aid, user_id)


def _t_for_write(db: Session, pid: UUID, tid: UUID, user_id: str, role: Role) -> TxORM:
    if role == Role.admin:
        tx = db.get(TxORM, str(tid))
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        asset = db.get(AssetORM, tx.asset_id)
        if not asset or asset.portfolio_id != str(pid):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return tx
    return _t_or_404(db, pid, tid, user_id)


def _portfolio_market_metrics(db: Session, portfolio_id: str) -> tuple[Decimal, Decimal]:
    positions = _positions_by_asset(db, portfolio_id)
    assets = db.execute(select(AssetORM).where(AssetORM.portfolio_id == portfolio_id)).scalars().all()

    balance = Decimal("0")
    pnl24h = Decimal("0")
    for asset in assets:
        qty = positions.get(asset.id, Decimal("0"))
        if qty == 0:
            continue

        symbol = f"{asset.symbol.strip().upper()}USDT"
        ticker = fetch_ticker("spot", symbol) or fetch_ticker("linear", symbol)
        if not ticker:
            continue

        last = Decimal(ticker.lastPrice or "0")
        percent = Decimal(ticker.price24hPcnt or "0")
        balance += qty * last
        pnl24h += qty * last * percent

    return _q2(balance), _q2(pnl24h)


def _sync_portfolio_market_metrics(db: Session, portfolio: PortfolioORM) -> None:
    balance, pnl24h = _portfolio_market_metrics(db, portfolio.id)
    portfolio.balance_usd = balance
    portfolio.pnl_day_usd = pnl24h
    db.add(portfolio)


def _portfolio_detail(db: Session, portfolio: PortfolioORM) -> PortfolioDetail:
    balance, pnl24h = _portfolio_market_metrics(db, portfolio.id)
    return PortfolioDetail(
        id=UUID(portfolio.id),
        name=portfolio.name,
        emoji=portfolio.emoji,
        balance_usd=balance,
        pnl_day_usd=pnl24h,
        kind=portfolio.kind,
        visibility=portfolio.visibility,
        owner_id=UUID(portfolio.user_id),
        owner_email=portfolio.owner.email if getattr(portfolio, "owner", None) else None,
        created_at=portfolio.created_at,
    )


def _portfolio_summary(db: Session, portfolio: PortfolioORM) -> PortfolioSummary:
    balance, pnl24h = _portfolio_market_metrics(db, portfolio.id)
    return PortfolioSummary(
        id=UUID(portfolio.id),
        name=portfolio.name,
        emoji=portfolio.emoji,
        balance_usd=balance,
        pnl_day_usd=pnl24h,
        kind=portfolio.kind,
        visibility=portfolio.visibility,
        owner_id=UUID(portfolio.user_id),
        owner_email=portfolio.owner.email if getattr(portfolio, "owner", None) else None,
    )


def _asset_summary(asset: AssetORM) -> AssetSummary:
    return AssetSummary(
        id=UUID(asset.id),
        symbol=asset.symbol,
        display_name=asset.display_name,
        emoji=asset.emoji,
    )


def _tx_item(tx: TxORM) -> TxItem:
    return TxItem(
        id=UUID(tx.id),
        asset_id=UUID(tx.asset_id),
        type=tx.type,
        quantity=tx.quantity,
        price_usd=tx.price_usd,
        fee_usd=tx.fee_usd,
        at=tx.at,
        note=tx.note,
        tx_hash=tx.tx_hash,
    )


def _file_item(file_meta: PortfolioFileORM) -> PortfolioFileItem:
    return PortfolioFileItem(
        id=UUID(file_meta.id),
        portfolio_id=UUID(file_meta.portfolio_id),
        uploaded_by_user_id=UUID(file_meta.uploaded_by_user_id),
        original_name=file_meta.original_name,
        content_type=file_meta.content_type,
        size_bytes=file_meta.size_bytes,
        created_at=file_meta.created_at,
    )


def _assert_portfolio_access(db: Session, request: Request, pid: UUID) -> PortfolioORM:
    user_id, role = _user_and_role(request)
    if role in (Role.manager, Role.admin):
        portfolio = db.get(PortfolioORM, str(pid))
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return portfolio
    return _p_or_404(db, pid, user_id)


def _validate_page(page: int, page_size: int) -> tuple[int, int]:
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if page_size < 1 or page_size > 50:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 50")
    return page, page_size


def _sort_clause(sort_by: PortfolioSortField, sort_dir: SortDirection):
    mapping = {
        "created_at": PortfolioORM.created_at,
        "name": func.lower(PortfolioORM.name),
        "balance_usd": PortfolioORM.balance_usd,
    }
    column = mapping[sort_by]
    return column.asc() if sort_dir == "asc" else column.desc()


class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    emoji: Optional[str] = Field(default=None, max_length=8)
    visibility: Optional[Visibility] = None


class PortfolioImportRequest(BaseModel):
    source_id: UUID


class BybitKeysImportRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, min_length=6, max_length=128)
    api_secret: Optional[str] = Field(default=None, min_length=6, max_length=256)


class AssetUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=32)
    emoji: Optional[str] = Field(default=None, max_length=8)


@router.get("/portfolios", response_model=PortfolioListResponse)
def list_portfolios(
    request: Request,
    db: Session = Depends(get_db),
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    kind: Optional[PortfolioKind] = Query(default=None),
    visibility: Optional[Visibility] = Query(default=None),
    sort_by: PortfolioSortField = Query(default="created_at"),
    sort_dir: SortDirection = Query(default="desc"),
    page: int = Query(default=1),
    page_size: int = Query(default=9),
):
    page, page_size = _validate_page(page, page_size)
    user_id, role = _user_and_role(request)

    stmt = select(PortfolioORM)
    count_stmt = select(func.count()).select_from(PortfolioORM)

    if role not in (Role.manager, Role.admin):
        stmt = stmt.where(PortfolioORM.user_id == user_id)
        count_stmt = count_stmt.where(PortfolioORM.user_id == user_id)

    if kind is not None:
        stmt = stmt.where(PortfolioORM.kind == kind)
        count_stmt = count_stmt.where(PortfolioORM.kind == kind)

    if visibility is not None:
        stmt = stmt.where(PortfolioORM.visibility == visibility)
        count_stmt = count_stmt.where(PortfolioORM.visibility == visibility)

    if search:
        term = f"%{search.strip().lower()}%"
        owner_subquery = select(PortfolioORM.id).join(UserORM, PortfolioORM.user_id == UserORM.id).where(
            or_(
                func.lower(PortfolioORM.name).like(term),
                func.lower(UserORM.email).like(term),
            )
        )
        stmt = stmt.where(PortfolioORM.id.in_(owner_subquery))
        count_stmt = count_stmt.where(PortfolioORM.id.in_(owner_subquery))

    total_items = int(db.execute(count_stmt).scalar_one())
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    stmt = (
        stmt.order_by(_sort_clause(sort_by, sort_dir))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).scalars().all()

    return PortfolioListResponse(
        items=[_portfolio_summary(db, portfolio) for portfolio in rows],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post("/portfolios", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def create_portfolio(request: Request, body: PortfolioCreate, db: Session = Depends(get_db)):
    user_id, _ = _require_owner_level_write(request)
    portfolio = PortfolioORM(
        user_id=user_id,
        name=body.name.strip(),
        emoji=(body.emoji.strip() if body.emoji else None),
        visibility=body.visibility,
        kind=PortfolioKind.personal,
        balance_usd=Decimal("0.00"),
        pnl_day_usd=Decimal("0.00"),
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return _portfolio_detail(db, portfolio)


@router.post("/portfolios/import", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def import_portfolio(request: Request, body: PortfolioImportRequest, db: Session = Depends(get_db)):
    user_id, _ = _require_owner_level_write(request)
    src = db.get(PortfolioORM, str(body.source_id))
    if not src:
        raise HTTPException(status_code=404, detail="Source portfolio not found")
    if src.visibility != Visibility.public:
        raise HTTPException(status_code=403, detail="Source portfolio is private")

    portfolio = PortfolioORM(
        user_id=user_id,
        name=src.name,
        emoji=src.emoji,
        kind=PortfolioKind.subscribed,
        visibility=Visibility.private,
        balance_usd=src.balance_usd,
        pnl_day_usd=src.pnl_day_usd,
    )
    db.add(portfolio)
    db.flush()

    src_assets = db.execute(
        select(AssetORM).where(AssetORM.portfolio_id == src.id).order_by(AssetORM.symbol.asc())
    ).scalars().all()
    asset_id_map: dict[str, str] = {}
    for asset in src_assets:
        new_asset = AssetORM(
            portfolio_id=portfolio.id,
            symbol=asset.symbol,
            display_name=asset.display_name,
            emoji=asset.emoji,
        )
        db.add(new_asset)
        db.flush()
        asset_id_map[asset.id] = new_asset.id

    src_txs = db.execute(
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .where(AssetORM.portfolio_id == src.id)
        .order_by(TxORM.at.asc())
    ).scalars().all()
    for tx in src_txs:
        if tx.asset_id not in asset_id_map:
            continue
        db.add(
            TxORM(
                asset_id=asset_id_map[tx.asset_id],
                type=tx.type,
                quantity=tx.quantity,
                price_usd=tx.price_usd,
                fee_usd=tx.fee_usd,
                at=tx.at,
                note=tx.note,
                tx_hash=tx.tx_hash,
            )
        )

    db.commit()
    db.refresh(portfolio)
    return _portfolio_detail(db, portfolio)


@router.get("/portfolios/{pid}", response_model=PortfolioDetail)
def get_portfolio(request: Request, pid: UUID, db: Session = Depends(get_db)):
    return _portfolio_detail(db, _assert_portfolio_access(db, request, pid))


@router.put("/portfolios/{pid}", response_model=PortfolioDetail)
def update_portfolio(request: Request, pid: UUID, body: PortfolioUpdate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    portfolio = _p_for_write(db, pid, user_id, role)
    if body.name is not None:
        portfolio.name = body.name.strip()
    if body.emoji is not None:
        portfolio.emoji = body.emoji.strip() if body.emoji else None
    if body.visibility is not None:
        portfolio.visibility = body.visibility
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return _portfolio_detail(db, portfolio)


@router.delete("/portfolios/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(request: Request, pid: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    portfolio = _p_for_write(db, pid, user_id, role)
    db.delete(portfolio)
    db.commit()
    return None


@router.post("/portfolios/{pid}/import/bybit", response_model=PortfolioDetail)
def import_bybit_keys(
    request: Request,
    pid: UUID,
    body: BybitKeysImportRequest,
    db: Session = Depends(get_db),
):
    user_id, role = _require_owner_level_write(request)
    portfolio = _p_for_write(db, pid, user_id, role)
    if role == Role.admin:
        user_id = portfolio.user_id

    resolved_api_key = (body.api_key or os.getenv("BYBIT_API_KEY") or "").strip()
    resolved_api_secret = (body.api_secret or os.getenv("BYBIT_API_SECRET") or "").strip()
    if not resolved_api_key or not resolved_api_secret:
        raise HTTPException(status_code=503, detail="Bybit credentials are not configured")

    try:
        snapshot = bybit_service.fetch_portfolio_snapshot(
            api_key=resolved_api_key,
            api_secret=resolved_api_secret,
        )
    except BybitServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message)

    excluded = {"USDT", "USDC", "DAI"}
    threshold = Decimal("0.5")
    assets_cache = db.execute(select(AssetORM).where(AssetORM.portfolio_id == str(pid))).scalars().all()
    asset_by_symbol = {asset.symbol.strip().upper(): asset for asset in assets_cache}
    now = datetime.now(timezone.utc)

    for coin, balance in snapshot.holdings.items():
        symbol = coin.strip().upper()
        if not symbol or symbol in excluded:
            continue
        price = snapshot.prices.get(symbol)
        if not price or balance * price < threshold:
            continue
        asset = asset_by_symbol.get(symbol)
        if not asset:
            asset = AssetORM(
                portfolio_id=str(pid),
                symbol=symbol,
                display_name=symbol,
                emoji=None,
            )
            db.add(asset)
            db.flush()
            asset_by_symbol[symbol] = asset
        db.add(
            TxORM(
                asset_id=str(asset.id),
                type=TxType.transfer_in,
                quantity=balance,
                price_usd=None,
                fee_usd=None,
                at=now,
                note="Imported from Bybit",
                tx_hash=None,
            )
        )

    _sync_portfolio_market_metrics(db, portfolio)
    db.commit()
    db.refresh(portfolio)
    return _portfolio_detail(db, portfolio)


@router.get("/portfolios/{pid}/assets", response_model=list[AssetSummary])
def list_assets(request: Request, pid: UUID, db: Session = Depends(get_db)):
    _assert_portfolio_access(db, request, pid)
    rows = db.execute(
        select(AssetORM)
        .where(AssetORM.portfolio_id == str(pid))
        .order_by(AssetORM.symbol.asc())
    ).scalars().all()
    return [_asset_summary(asset) for asset in rows]


@router.post("/portfolios/{pid}/assets", response_model=AssetSummary, status_code=status.HTTP_201_CREATED)
def add_asset(request: Request, pid: UUID, body: AssetCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    symbol = body.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    asset = AssetORM(
        portfolio_id=str(pid),
        symbol=symbol,
        display_name=(body.display_name.strip() if body.display_name else symbol),
        emoji=(body.emoji.strip() if body.emoji else None),
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Asset with this symbol already exists")
    db.refresh(asset)
    return _asset_summary(asset)


@router.put("/portfolios/{pid}/assets/{aid}", response_model=AssetSummary)
def update_asset(request: Request, pid: UUID, aid: UUID, body: AssetUpdate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    asset = _a_for_write(db, pid, aid, user_id, role)
    if body.display_name is not None:
        asset.display_name = body.display_name.strip() if body.display_name else None
    if body.emoji is not None:
        asset.emoji = body.emoji.strip() if body.emoji else None
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_summary(asset)


@router.delete("/portfolios/{pid}/assets/{aid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(request: Request, pid: UUID, aid: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    asset = _a_for_write(db, pid, aid, user_id, role)
    db.delete(asset)
    db.commit()
    return None


@router.get("/portfolios/{pid}/transactions", response_model=list[TxItem])
def list_transactions(request: Request, pid: UUID, asset_id: Optional[UUID] = Query(default=None), db: Session = Depends(get_db)):
    user_id, role = _user_and_role(request)
    if role in (Role.manager, Role.admin):
        if not db.get(PortfolioORM, str(pid)):
            raise HTTPException(status_code=404, detail="Portfolio not found")
    else:
        _p_or_404(db, pid, user_id)

    stmt = (
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .join(PortfolioORM, AssetORM.portfolio_id == PortfolioORM.id)
        .where(AssetORM.portfolio_id == str(pid))
    )
    if role not in (Role.manager, Role.admin):
        stmt = stmt.where(PortfolioORM.user_id == user_id)
    if asset_id is not None:
        if role in (Role.manager, Role.admin):
            asset = db.get(AssetORM, str(asset_id))
            if not asset or asset.portfolio_id != str(pid):
                raise HTTPException(status_code=404, detail="Asset not found")
        else:
            _a_or_404(db, pid, asset_id, user_id)
        stmt = stmt.where(TxORM.asset_id == str(asset_id))
    rows = db.execute(stmt.order_by(TxORM.at.desc())).scalars().all()
    return [_tx_item(tx) for tx in rows]


@router.post("/portfolios/{pid}/transactions", response_model=TxItem, status_code=status.HTTP_201_CREATED)
def add_transaction(request: Request, pid: UUID, body: TxCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    _a_for_write(db, pid, body.asset_id, user_id, role)
    if body.quantity is None or Decimal(body.quantity) <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")
    if body.type in (TxType.buy, TxType.sell) and body.price_usd is None:
        raise HTTPException(status_code=400, detail="price_usd is required for buy/sell")
    tx = TxORM(
        asset_id=str(body.asset_id),
        type=body.type,
        quantity=body.quantity,
        price_usd=body.price_usd,
        fee_usd=body.fee_usd,
        at=body.at,
        note=body.note,
        tx_hash=body.tx_hash,
    )
    db.add(tx)
    portfolio = db.get(PortfolioORM, str(pid))
    if portfolio:
        _sync_portfolio_market_metrics(db, portfolio)
    db.commit()
    db.refresh(tx)
    return _tx_item(tx)


@router.put("/portfolios/{pid}/transactions/{tid}", response_model=TxItem)
def update_transaction(request: Request, pid: UUID, tid: UUID, body: TxCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    tx = _t_for_write(db, pid, tid, user_id, role)
    _a_for_write(db, pid, body.asset_id, user_id, role)
    if body.quantity is None or Decimal(body.quantity) <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")
    if body.type in (TxType.buy, TxType.sell) and body.price_usd is None:
        raise HTTPException(status_code=400, detail="price_usd is required for buy/sell")
    tx.asset_id = str(body.asset_id)
    tx.type = body.type
    tx.quantity = body.quantity
    tx.price_usd = body.price_usd
    tx.fee_usd = body.fee_usd
    tx.at = body.at
    tx.note = body.note
    tx.tx_hash = body.tx_hash
    db.add(tx)
    portfolio = db.get(PortfolioORM, str(pid))
    if portfolio:
        _sync_portfolio_market_metrics(db, portfolio)
    db.commit()
    db.refresh(tx)
    return _tx_item(tx)


@router.delete("/portfolios/{pid}/transactions/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(request: Request, pid: UUID, tid: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    tx = _t_for_write(db, pid, tid, user_id, role)
    db.delete(tx)
    portfolio = db.get(PortfolioORM, str(pid))
    if portfolio:
        _sync_portfolio_market_metrics(db, portfolio)
    db.commit()
    return None


@router.get("/portfolios/{pid}/timeseries", response_model=TimeseriesResponse)
def get_timeseries(request: Request, pid: UUID, days: int = 14, db: Session = Depends(get_db)):
    portfolio = _assert_portfolio_access(db, request, pid)
    now = datetime.now(timezone.utc)
    balance, _ = _portfolio_market_metrics(db, str(pid))
    points = [
        Timepoint(t=(now - timedelta(days=offset)), balance_usd=balance)
        for offset in range(max(1, days))
    ][::-1]
    return TimeseriesResponse(points=points)


@router.get("/portfolios/{pid}/files", response_model=list[PortfolioFileItem])
def list_portfolio_files(request: Request, pid: UUID, db: Session = Depends(get_db)):
    _assert_portfolio_access(db, request, pid)
    files = db.execute(
        select(PortfolioFileORM)
        .where(PortfolioFileORM.portfolio_id == str(pid))
        .order_by(PortfolioFileORM.created_at.desc())
    ).scalars().all()
    return [_file_item(file_meta) for file_meta in files]


@router.post("/portfolios/{pid}/files", response_model=PortfolioFileItem, status_code=status.HTTP_201_CREATED)
def upload_portfolio_file(
    request: Request,
    pid: UUID,
    body: PortfolioFileUploadRequest,
    db: Session = Depends(get_db),
):
    user_id, role = _require_owner_level_write(request)
    portfolio = _p_for_write(db, pid, user_id, role)
    storage = ObjectStorageService()
    try:
        payload = storage.validate_upload(body.file_name, body.content_type, body.content_base64)
        storage_key = storage.put_bytes(payload, body.file_name)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_meta = PortfolioFileORM(
        portfolio_id=portfolio.id,
        uploaded_by_user_id=user_id if role != Role.admin else portfolio.user_id,
        original_name=body.file_name.strip(),
        storage_key=storage_key,
        content_type=body.content_type,
        size_bytes=len(payload),
    )
    db.add(file_meta)
    db.commit()
    db.refresh(file_meta)
    return _file_item(file_meta)


@router.get("/portfolios/{pid}/files/{file_id}/download", response_model=PortfolioFileDownloadResponse)
def get_portfolio_file_download(
    request: Request,
    pid: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
):
    _assert_portfolio_access(db, request, pid)
    file_meta = db.get(PortfolioFileORM, str(file_id))
    if not file_meta or file_meta.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="File not found")
    expires_at = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
    token = ObjectStorageService().build_presigned_token(file_meta.id, expires_at)
    return PortfolioFileDownloadResponse(
        download_url=f"/api/v1/public/portfolios/{pid}/files/{file_id}/content?token={token}",
        expires_at=expires_at,
    )


@router.get("/portfolios/{pid}/files/{file_id}/content")
def download_portfolio_file_content(
    request: Request,
    pid: UUID,
    file_id: UUID,
    token: str = Query(..., min_length=10),
    db: Session = Depends(get_db),
):
    _assert_portfolio_access(db, request, pid)
    file_meta = db.get(PortfolioFileORM, str(file_id))
    if not file_meta or file_meta.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="File not found")
    storage = ObjectStorageService()
    try:
        storage.verify_presigned_token(file_meta.id, token)
        payload = storage.read(file_meta.storage_key)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    headers = {
        "Content-Disposition": f'attachment; filename="{file_meta.original_name}"',
    }
    return Response(content=payload, media_type=file_meta.content_type, headers=headers)


@router.delete("/portfolios/{pid}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio_file(request: Request, pid: UUID, file_id: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    file_meta = db.get(PortfolioFileORM, str(file_id))
    if not file_meta or file_meta.portfolio_id != str(pid):
        raise HTTPException(status_code=404, detail="File not found")
    ObjectStorageService().delete(file_meta.storage_key)
    db.delete(file_meta)
    db.commit()
    return None
