"""Portfolio and asset API routes with RBAC enforcement.

This module provides all endpoints for managing portfolios, assets and
transactions. It has been extended with role‑based access control
mechanisms. Depending on a user's role (``user``, ``manager`` or ``admin``),
different operations are permitted:

* ``user`` – can create and manage their own portfolios, assets and transactions.
* ``manager`` – can view any user's portfolios and their contents but cannot
  create, update or delete data.
* ``admin`` – has unrestricted access to all data.

Role checking is implemented by calling :func:`app.auth.require_user` to obtain
the token payload and inspect the ``role`` claim and :func:`app.auth.require_roles`
for operations restricted to certain roles.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.orm_models import PortfolioORM, AssetORM, TxORM
from app.models.common import Visibility, PortfolioKind, TxType, Role
from app.models.portfolio import PortfolioCreate, PortfolioSummary, PortfolioDetail
from app.models.asset import AssetCreate, AssetSummary
from app.models.tx import TxCreate, TxItem
from app.models.timeseries import TimeseriesResponse, Timepoint
from app.routers.market import fetch_ticker
from app.auth import require_user
import os
from pybit.unified_trading import HTTP
from collections import defaultdict


router = APIRouter()


def _q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _positions_by_asset(db: Session, pid: str) -> dict[str, Decimal]:
    # returns asset_id -> qty
    rows = db.execute(
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .where(AssetORM.portfolio_id == pid)
    ).scalars().all()

    pos: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for t in rows:
        if t.type in (TxType.buy, TxType.transfer_in):
            pos[t.asset_id] += t.quantity
        else:  # sell, transfer_out
            pos[t.asset_id] -= t.quantity
    return dict(pos)


def _user_and_role(request: Request) -> tuple[str, Role]:
    payload = require_user(request)
    return str(payload["sub"]), Role(payload["role"])


def _p_or_404(db: Session, pid: UUID, user_id: str) -> PortfolioORM:
    p = db.get(PortfolioORM, str(pid))
    if not p or p.user_id != user_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return p


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
    a = db.execute(stmt).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    return a


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
    t = db.execute(stmt).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return t


def _require_owner_level_write(request: Request) -> tuple[str, Role]:
    user_id, role = _user_and_role(request)
    if role not in (Role.user, Role.admin):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_id, role


def _p_for_write(db: Session, pid: UUID, user_id: str, role: Role) -> PortfolioORM:
    if role == Role.admin:
        p = db.get(PortfolioORM, str(pid))
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return p
    return _p_or_404(db, pid, user_id)


def _a_for_write(db: Session, pid: UUID, aid: UUID, user_id: str, role: Role) -> AssetORM:
    if role == Role.admin:
        a = db.get(AssetORM, str(aid))
        if not a or a.portfolio_id != str(pid):
            raise HTTPException(status_code=404, detail="Asset not found")
        return a
    return _a_or_404(db, pid, aid, user_id)


def _t_for_write(db: Session, pid: UUID, tid: UUID, user_id: str, role: Role) -> TxORM:
    if role == Role.admin:
        t = db.get(TxORM, str(tid))
        if not t:
            raise HTTPException(status_code=404, detail="Transaction not found")
        a = db.get(AssetORM, t.asset_id)
        if not a or a.portfolio_id != str(pid):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return t
    return _t_or_404(db, pid, tid, user_id)


def _portfolio_market_metrics(db: Session, pid: str) -> tuple[Decimal, Decimal]:
    pos = _positions_by_asset(db, pid)
    assets = db.execute(select(AssetORM).where(AssetORM.portfolio_id == pid)).scalars().all()

    balance = Decimal("0")
    pnl24h = Decimal("0")
    for a in assets:
        qty = pos.get(a.id, Decimal("0"))
        if qty == 0:
            continue

        symbol = f"{a.symbol.strip().upper()}USDT"
        tick = fetch_ticker("spot", symbol) or fetch_ticker("linear", symbol)
        if not tick:
            continue

        last = Decimal(tick.lastPrice or "0")
        pcnt = Decimal(tick.price24hPcnt or "0")
        balance += qty * last
        pnl24h += qty * last * pcnt

    return _q2(balance), _q2(pnl24h)


def _sync_portfolio_market_metrics(db: Session, p: PortfolioORM) -> None:
    balance, pnl24h = _portfolio_market_metrics(db, p.id)
    p.balance_usd = balance
    p.pnl_day_usd = pnl24h
    db.add(p)


def _portfolio_detail(db: Session, p: PortfolioORM) -> PortfolioDetail:
    balance, pnl24h = _portfolio_market_metrics(db, p.id)
    return PortfolioDetail(
        id=UUID(p.id),
        name=p.name,
        emoji=p.emoji,
        balance_usd=balance,
        pnl_day_usd=pnl24h,
        kind=p.kind,
        visibility=p.visibility,
        owner_id=UUID(p.user_id),
        owner_email=p.owner.email if getattr(p, "owner", None) else None,
        created_at=p.created_at,
    )


def _portfolio_summary(db: Session, p: PortfolioORM) -> PortfolioSummary:
    balance, pnl24h = _portfolio_market_metrics(db, p.id)
    return PortfolioSummary(
        id=UUID(p.id),
        name=p.name,
        emoji=p.emoji,
        balance_usd=balance,
        pnl_day_usd=pnl24h,
        kind=p.kind,
        visibility=p.visibility,
        owner_id=UUID(p.user_id),
        owner_email=p.owner.email if getattr(p, "owner", None) else None,
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


class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    emoji: Optional[str] = Field(default=None, max_length=8)
    visibility: Optional[Visibility] = None


class PortfolioImportRequest(BaseModel):
    source_id: UUID


class BybitKeysImportRequest(BaseModel):
    api_key: str = Field(min_length=6, max_length=128)
    api_secret: str = Field(min_length=6, max_length=256)


class AssetUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=32)
    emoji: Optional[str] = Field(default=None, max_length=8)


# ===== Portfolios =====

@router.get("/portfolios", response_model=list[PortfolioSummary])
def list_portfolios(request: Request, db: Session = Depends(get_db)):
    user_id, role = _user_and_role(request)
    if role in (Role.manager, Role.admin):
        rows = (
            db.execute(
                select(PortfolioORM).order_by(PortfolioORM.created_at.desc())
            ).scalars().all()
        )
    else:
        rows = (
            db.execute(
                select(PortfolioORM)
                .where(PortfolioORM.user_id == user_id)
                .order_by(PortfolioORM.created_at.desc())
            ).scalars().all()
        )
    return [_portfolio_summary(db, p) for p in rows]


@router.post("/portfolios", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def create_portfolio(request: Request, body: PortfolioCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    p = PortfolioORM(
        user_id=user_id,
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
    return _portfolio_detail(db, p)


@router.post("/portfolios/import", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def import_portfolio(
    request: Request,
    body: PortfolioImportRequest,
    db: Session = Depends(get_db),
):
    """Import a public portfolio by ID.

    Users may import into their own account. Admins may import as well.
    """
    user_id, role = _require_owner_level_write(request)
    src = db.get(PortfolioORM, str(body.source_id))
    if not src:
        raise HTTPException(status_code=404, detail="Source portfolio not found")
    if src.visibility != Visibility.public:
        raise HTTPException(status_code=403, detail="Source portfolio is private")
    # clone
    p = PortfolioORM(
        user_id=user_id,
        name=src.name,
        emoji=src.emoji,
        kind=PortfolioKind.subscribed,
        visibility=Visibility.private,
        balance_usd=src.balance_usd,
        pnl_day_usd=src.pnl_day_usd,
    )
    db.add(p)
    db.flush()
    # copy assets
    src_assets = db.execute(
        select(AssetORM).where(AssetORM.portfolio_id == src.id).order_by(AssetORM.symbol.asc())
    ).scalars().all()
    asset_id_map: dict[str, str] = {}
    for a in src_assets:
        na = AssetORM(
            portfolio_id=p.id,
            symbol=a.symbol,
            display_name=a.display_name,
            emoji=a.emoji,
        )
        db.add(na)
        db.flush()
        asset_id_map[a.id] = na.id
    src_txs = db.execute(
        select(TxORM)
        .join(AssetORM, TxORM.asset_id == AssetORM.id)
        .where(AssetORM.portfolio_id == src.id)
        .order_by(TxORM.at.asc())
    ).scalars().all()
    for t in src_txs:
        new_asset_id = asset_id_map.get(t.asset_id)
        if not new_asset_id:
            continue
        db.add(
            TxORM(
                asset_id=new_asset_id,
                type=t.type,
                quantity=t.quantity,
                price_usd=t.price_usd,
                fee_usd=t.fee_usd,
                at=t.at,
                note=t.note,
                tx_hash=t.tx_hash,
            )
        )
    db.commit()
    db.refresh(p)
    return _portfolio_detail(db, p)


@router.get("/portfolios/{pid}", response_model=PortfolioDetail)
def get_portfolio(request: Request, pid: UUID, db: Session = Depends(get_db)):
    user_id, role = _user_and_role(request)
    if role in (Role.manager, Role.admin):
        p = db.get(PortfolioORM, str(pid))
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return _portfolio_detail(db, p)
    # regular user: must own
    return _portfolio_detail(db, _p_or_404(db, pid, user_id))


@router.put("/portfolios/{pid}", response_model=PortfolioDetail)
def update_portfolio(
    request: Request,
    pid: UUID,
    body: PortfolioUpdate,
    db: Session = Depends(get_db),
):
    user_id, role = _require_owner_level_write(request)
    p = _p_for_write(db, pid, user_id, role)
    if body.name is not None:
        p.name = body.name.strip()
    if body.emoji is not None:
        p.emoji = body.emoji.strip() if body.emoji else None
    if body.visibility is not None:
        p.visibility = body.visibility
    db.add(p)
    db.commit()
    db.refresh(p)
    return _portfolio_detail(db, p)


@router.delete("/portfolios/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(request: Request, pid: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    p = _p_for_write(db, pid, user_id, role)
    db.delete(p)
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
    p = _p_for_write(db, pid, user_id, role)
    if role == Role.admin:
        user_id = p.user_id

    testnet = os.getenv("BYBIT_TESTNET", "0") == "1"

    session = HTTP(
        testnet=testnet,
        api_key=body.api_key,
        api_secret=body.api_secret,
    )

    try:
        r_unified = session.get_wallet_balance(accountType="UNIFIED")
        r_fund = session.get_coins_balance(accountType="FUND")  # coin не передаем => all coins (для FUND ок)
        r_ticks = session.get_tickers(category="spot")  # без symbol (как ты просил)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Bybit request failed: {e}")

    def _bybit_ok_or_502(r: dict, where: str) -> None:
        if not isinstance(r, dict) or r.get("retCode") != 0:
            msg = None
            if isinstance(r, dict):
                msg = r.get("retMsg") or r.get("retCode")
            raise HTTPException(status_code=502, detail=f"Bybit error at {where}: {msg}")

    def _d0(x) -> Decimal:
        try:
            s = (x if x is not None else "0")
            s = str(s).strip()
            if s == "":
                return Decimal("0")
            return Decimal(s)
        except Exception:
            return Decimal("0")

    def _parse_unified_wallet_balance(r: dict) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        lst = (((r.get("result") or {}).get("list")) or [])
        for acc in lst:
            coins = acc.get("coin") or []
            for c in coins:
                sym = (c.get("coin") or "").strip().upper()
                bal = _d0(c.get("walletBalance"))
                if sym and bal != 0:
                    out[sym] = out.get(sym, Decimal("0")) + bal
        return out

    def _parse_fund_all_balance(r: dict) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        bal_list = ((r.get("result") or {}).get("balance")) or []
        for it in bal_list:
            sym = (it.get("coin") or "").strip().upper()
            bal = _d0(it.get("walletBalance"))
            if sym and bal != 0:
                out[sym] = out.get(sym, Decimal("0")) + bal
        return out

    def _recalc_portfolio_market_metrics(db: Session, pid: UUID) -> None:
        p = db.get(PortfolioORM, str(pid))
        if not p:
            return
        rows = db.execute(
            select(TxORM)
            .join(AssetORM, TxORM.asset_id == AssetORM.id)
            .where(AssetORM.portfolio_id == str(pid))
        ).scalars().all()
        pos = defaultdict(lambda: Decimal("0"))
        for t in rows:
            if t.type in (TxType.buy, TxType.transfer_in):
                pos[t.asset_id] += Decimal(t.quantity)
            else:
                pos[t.asset_id] -= Decimal(t.quantity)
        assets = db.execute(
            select(AssetORM).where(AssetORM.portfolio_id == str(pid))
        ).scalars().all()
        balance = Decimal("0")
        pnl24h = Decimal("0")
        for a in assets:
            qty = pos.get(a.id, Decimal("0"))
            if qty == 0:
                continue
            symbol = f"{a.symbol.strip().upper()}USDT"
            t = fetch_ticker("spot", symbol) or fetch_ticker("linear", symbol)
            if not t:
                continue
            last = Decimal(t.lastPrice or "0")
            pcnt = Decimal(t.price24hPcnt or "0")
            balance += qty * last
            pnl24h += qty * last * pcnt
        p.balance_usd = _q2(balance)
        p.pnl_day_usd = _q2(pnl24h)
        db.add(p)

    _bybit_ok_or_502(r_unified, "wallet-balance")
    _bybit_ok_or_502(r_fund, "all-balance")
    _bybit_ok_or_502(r_ticks, "tickers")
    holdings: dict[str, Decimal] = {}
    for k, v in _parse_unified_wallet_balance(r_unified).items():
        holdings[k] = holdings.get(k, Decimal("0")) + v
    for k, v in _parse_fund_all_balance(r_fund).items():
        holdings[k] = holdings.get(k, Decimal("0")) + v
    prices: dict[str, Decimal] = {}
    tick_list = (((r_ticks.get("result") or {}).get("list")) or [])
    for it in tick_list:
        sym = (it.get("symbol") or "").strip().upper()
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        last = _d0(it.get("lastPrice"))
        if base and last > 0:
            prices[base] = last
    EXCLUDED = {"USDT", "USDC", "DAI"}
    THRESH = Decimal("0.5")
    assets_cache = (
        db.execute(select(AssetORM).where(AssetORM.portfolio_id == str(pid)))
        .scalars()
        .all()
    )
    asset_by_symbol = {a.symbol.strip().upper(): a for a in assets_cache}
    imported_symbols: list[str] = []
    now = datetime.now(timezone.utc)
    for coin, bal in holdings.items():
        coin = coin.strip().upper()
        if not coin or coin in EXCLUDED:
            continue
        px = prices.get(coin)
        if not px:
            continue
        usd_val = bal * px
        if usd_val < THRESH:
            continue
        a = asset_by_symbol.get(coin)
        if not a:
            a = AssetORM(
                portfolio_id=str(pid),
                symbol=coin,
                display_name=coin,
                emoji=None,
            )
            db.add(a)
            db.flush()
            asset_by_symbol[coin] = a
        db.add(
            TxORM(
                asset_id=str(a.id),
                type=TxType.transfer_in,
                quantity=bal,
                price_usd=None,
                fee_usd=None,
                at=now,
                note="Imported from Bybit",
                tx_hash=None,
            )
        )
        imported_symbols.append(coin)
    _sync_portfolio_market_metrics(db, p)
    db.commit()
    db.refresh(p)
    return _portfolio_detail(db, p)


# ===== Assets =====

@router.get("/portfolios/{pid}/assets", response_model=list[AssetSummary])
def list_assets(request: Request, pid: UUID, db: Session = Depends(get_db)):
    user_id, role = _user_and_role(request)
    # Access allowed to owners, managers, admins
    if role in (Role.manager, Role.admin):
        p = db.get(PortfolioORM, str(pid))
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
    else:
        _p_or_404(db, pid, user_id)
    rows = (
        db.execute(
            select(AssetORM)
            .where(AssetORM.portfolio_id == str(pid))
            .order_by(AssetORM.symbol.asc())
        )
        .scalars()
        .all()
    )
    return [_asset_summary(a) for a in rows]


@router.post("/portfolios/{pid}/assets", response_model=AssetSummary, status_code=status.HTTP_201_CREATED)
def add_asset(request: Request, pid: UUID, body: AssetCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    symbol = body.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    a = AssetORM(
        portfolio_id=str(pid),
        symbol=symbol,
        display_name=(body.display_name.strip() if body.display_name else symbol),
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
def update_asset(
    request: Request,
    pid: UUID,
    aid: UUID,
    body: AssetUpdate,
    db: Session = Depends(get_db),
):
    user_id, role = _require_owner_level_write(request)
    a = _a_for_write(db, pid, aid, user_id, role)
    if body.display_name is not None:
        a.display_name = body.display_name.strip() if body.display_name else None
    if body.emoji is not None:
        a.emoji = body.emoji.strip() if body.emoji else None
    db.add(a)
    db.commit()
    db.refresh(a)
    return _asset_summary(a)


@router.delete("/portfolios/{pid}/assets/{aid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(request: Request, pid: UUID, aid: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    a = _a_for_write(db, pid, aid, user_id, role)
    db.delete(a)
    db.commit()
    return None


# ===== Transactions =====

@router.get("/portfolios/{pid}/transactions", response_model=list[TxItem])
def list_transactions(
    request: Request,
    pid: UUID,
    asset_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    user_id, role = _user_and_role(request)
    if role in (Role.manager, Role.admin):
        # verify portfolio exists
        p = db.get(PortfolioORM, str(pid))
        if not p:
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
        # ensure asset belongs to portfolio and, if user role, to user
        if role in (Role.manager, Role.admin):
            a = db.get(AssetORM, str(asset_id))
            if not a or a.portfolio_id != str(pid):
                raise HTTPException(status_code=404, detail="Asset not found")
        else:
            _a_or_404(db, pid, asset_id, user_id)
        stmt = stmt.where(TxORM.asset_id == str(asset_id))
    rows = db.execute(stmt.order_by(TxORM.at.desc())).scalars().all()
    return [_tx_item(t) for t in rows]


@router.post("/portfolios/{pid}/transactions", response_model=TxItem, status_code=status.HTTP_201_CREATED)
def add_transaction(request: Request, pid: UUID, body: TxCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    _a_for_write(db, pid, body.asset_id, user_id, role)
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
    # recalc
    # reuse local recalc for this module
    p = db.get(PortfolioORM, str(pid))
    if p:
        _sync_portfolio_market_metrics(db, p)
    db.commit()
    db.refresh(t)
    return _tx_item(t)


@router.put("/portfolios/{pid}/transactions/{tid}", response_model=TxItem)
def update_transaction(request: Request, pid: UUID, tid: UUID, body: TxCreate, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    _p_for_write(db, pid, user_id, role)
    t = _t_for_write(db, pid, tid, user_id, role)
    _a_for_write(db, pid, body.asset_id, user_id, role)
    # validate inputs
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
    # recalc metrics
    p = db.get(PortfolioORM, str(pid))
    if p:
        _sync_portfolio_market_metrics(db, p)
    db.commit()
    db.refresh(t)
    return _tx_item(t)


@router.delete("/portfolios/{pid}/transactions/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(request: Request, pid: UUID, tid: UUID, db: Session = Depends(get_db)):
    user_id, role = _require_owner_level_write(request)
    t = _t_for_write(db, pid, tid, user_id, role)
    # recalc metrics after deletion
    db.delete(t)
    p = db.get(PortfolioORM, str(pid))
    if p:
        _sync_portfolio_market_metrics(db, p)
    db.commit()
    return None


# ===== Timeseries =====

@router.get("/portfolios/{pid}/timeseries", response_model=TimeseriesResponse)
def get_timeseries(request: Request, pid: UUID, days: int = 14, db: Session = Depends(get_db)):
    user_id, role = _user_and_role(request)
    if role in (Role.manager, Role.admin):
        p = db.get(PortfolioORM, str(pid))
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
    else:
        p = _p_or_404(db, pid, user_id)
    now = datetime.now(timezone.utc)
    balance, _ = _portfolio_market_metrics(db, str(pid))
    pts = [
        Timepoint(t=(now - timedelta(days=i)), balance_usd=balance)
        for i in range(max(1, days))
    ][::-1]
    return TimeseriesResponse(points=pts)
