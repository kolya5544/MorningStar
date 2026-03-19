"""Database ORM models.

This module defines SQLAlchemy ORM models for users, portfolios, assets and transactions.
It extends the existing data model with a ``role`` attribute on ``UserORM`` to support
role‑based access control (RBAC). Users may be ``user`` (default), ``manager`` or
``admin``, as defined in :class:`app.models.common.Role`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import String, DateTime, ForeignKey, Numeric, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import Visibility, PortfolioKind, TxType, Role


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class UserORM(Base):
    """User model.

    Each user has a globally unique ``id``, an ``email``, a ``password_hash`` and
    a ``role``. The ``role`` controls access to API endpoints according to the RBAC
    rules implemented in the application. By default new users are assigned the
    ``Role.user`` role.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    role: Mapped[Role] = mapped_column(SAEnum(Role), nullable=False, default=Role.user)

    portfolios: Mapped[list["PortfolioORM"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_sessions: Mapped[list["RefreshSessionORM"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class PortfolioORM(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner: Mapped["UserORM"] = relationship(back_populates="portfolios")

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


class RefreshSessionORM(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["UserORM"] = relationship(back_populates="refresh_sessions")
