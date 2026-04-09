from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from fastapi import APIRouter


def configure_env(root: Path) -> Path:
    storage_root = root / "test_object_storage"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{(root / 'test_app.db').as_posix()}")
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ.setdefault("OBJECT_STORAGE_SECRET", "test-storage-secret")
    os.environ.setdefault("OBJECT_STORAGE_ROOT", str(storage_root))
    os.environ.setdefault("BYBIT_API_KEY", "test-key")
    os.environ.setdefault("BYBIT_API_SECRET", "test-secret")
    return storage_root


ROOT = Path(__file__).resolve().parent
STORAGE_ROOT = configure_env(ROOT)

from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.models.common import PortfolioKind, Role, TxType, Visibility
from app.orm_models import AssetORM, PortfolioORM, TxORM, UserORM
from app.main import app
from app.routers import market, portfolios
from app.services.bybit import BybitPortfolioSnapshot, BybitServiceError


def reset_state() -> None:
    if STORAGE_ROOT.exists():
        shutil.rmtree(STORAGE_ROOT)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        user = UserORM(
            email="user@example.com",
            password_hash=hash_password("UserPass123"),
            role=Role.user,
        )
        manager = UserORM(
            email="manager@example.com",
            password_hash=hash_password("ManagerPass123"),
            role=Role.manager,
        )
        admin = UserORM(
            email="admin@example.com",
            password_hash=hash_password("AdminPass123"),
            role=Role.admin,
        )
        source_owner = UserORM(
            email="source@example.com",
            password_hash=hash_password("SourcePass123"),
            role=Role.user,
        )
        session.add_all([user, manager, admin, source_owner])
        session.flush()

        portfolios_to_create: list[PortfolioORM] = [
            PortfolioORM(
                user_id=user.id,
                name="User Core Portfolio",
                emoji="U",
                kind=PortfolioKind.personal,
                visibility=Visibility.private,
                balance_usd=Decimal("1250.00"),
                pnl_day_usd=Decimal("20.00"),
            ),
            PortfolioORM(
                user_id=user.id,
                name="Alpha Income",
                emoji="A",
                kind=PortfolioKind.personal,
                visibility=Visibility.public,
                balance_usd=Decimal("950.00"),
                pnl_day_usd=Decimal("15.00"),
            ),
            PortfolioORM(
                user_id=source_owner.id,
                name="Public Signal",
                emoji="S",
                kind=PortfolioKind.personal,
                visibility=Visibility.public,
                balance_usd=Decimal("777.00"),
                pnl_day_usd=Decimal("11.00"),
            ),
            PortfolioORM(
                user_id=source_owner.id,
                name="Private Source",
                emoji="P",
                kind=PortfolioKind.personal,
                visibility=Visibility.private,
                balance_usd=Decimal("333.00"),
                pnl_day_usd=Decimal("7.00"),
            ),
        ]

        for index in range(1, 9):
            portfolios_to_create.append(
                PortfolioORM(
                    user_id=user.id,
                    name=f"Paged Portfolio {index}",
                    emoji=str(index),
                    kind=PortfolioKind.personal,
                    visibility=Visibility.private if index % 2 else Visibility.public,
                    balance_usd=Decimal(str(100 * index)),
                    pnl_day_usd=Decimal("5.00"),
                    created_at=datetime.now(timezone.utc) - timedelta(days=index),
                )
            )

        session.add_all(portfolios_to_create)
        session.flush()

        core_portfolio = portfolios_to_create[0]
        source_portfolio = portfolios_to_create[2]

        btc = AssetORM(
            portfolio_id=core_portfolio.id,
            symbol="BTC",
            display_name="Bitcoin",
            emoji="B",
        )
        eth = AssetORM(
            portfolio_id=source_portfolio.id,
            symbol="ETH",
            display_name="Ethereum",
            emoji="E",
        )
        session.add_all([btc, eth])
        session.flush()

        session.add_all(
            [
                TxORM(
                    asset_id=btc.id,
                    type=TxType.buy,
                    quantity=Decimal("1.25000000"),
                    price_usd=Decimal("100.00"),
                    fee_usd=None,
                    at=datetime.now(timezone.utc) - timedelta(days=2),
                    note="Seed buy",
                    tx_hash=None,
                ),
                TxORM(
                    asset_id=eth.id,
                    type=TxType.buy,
                    quantity=Decimal("2.00000000"),
                    price_usd=Decimal("50.00"),
                    fee_usd=None,
                    at=datetime.now(timezone.utc) - timedelta(days=1),
                    note="Source buy",
                    tx_hash=None,
                ),
            ]
        )
        session.commit()


def patch_integrations() -> None:
    market._cache.clear()
    market._service.fetch_ticker = lambda category, symbol: {
        "category": category,
        "symbol": symbol,
        "bid1Price": "99",
        "bid1Size": "1",
        "ask1Price": "101",
        "ask1Size": "1",
        "lastPrice": "100",
        "prevPrice24h": "90",
        "price24hPcnt": "0.10",
        "highPrice24h": "110",
        "lowPrice24h": "80",
        "turnover24h": "1000",
        "volume24h": "10",
        "usdIndexPrice": None,
    }

    portfolios.fetch_ticker = lambda category, symbol: SimpleNamespace(
        lastPrice="100.00",
        price24hPcnt="0.10",
    )

    def mock_snapshot(*, api_key: str, api_secret: str) -> BybitPortfolioSnapshot:
        if api_key == "fail-key":
            raise BybitServiceError("Bybit unavailable")
        return BybitPortfolioSnapshot(
            holdings={"SOL": Decimal("0.75"), "USDT": Decimal("100.0")},
            prices={"SOL": Decimal("120.0")},
        )

    portfolios.bybit_service.fetch_portfolio_snapshot = mock_snapshot


test_router = APIRouter(prefix="/api/test", tags=["test"])


@test_router.post("/reset", status_code=204)
def reset_endpoint():
    reset_state()
    patch_integrations()
    return None


app.include_router(test_router)


def main() -> None:
    reset_state()
    patch_integrations()
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
