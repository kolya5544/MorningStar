# app/orm_models.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    String, DateTime, ForeignKey, Numeric, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import Visibility, PortfolioKind, TxType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioORM(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(8), nullable=True)

    kind: Mapped[PortfolioKind] = mapped_column(SAEnum(PortfolioKind), nullable=False, default=PortfolioKind.personal)
    visibility: Mapped[Visibility] = mapped_column(SAEnum(Visibility), nullable=False, default=Visibility.private)

    balance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    pnl_day_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    assets: Mapped[list["AssetORM"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AssetORM(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("portfolio_id", "symbol", name="uq_asset_portfolio_symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(8), nullable=True)

    portfolio: Mapped["PortfolioORM"] = relationship(back_populates="assets")
    txs: Mapped[list["TxORM"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TxORM(Base):
    __tablename__ = "tx"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    asset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[TxType] = mapped_column(SAEnum(TxType), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)

    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    fee_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(140), nullable=True)
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    asset: Mapped["AssetORM"] = relationship(back_populates="txs")
