from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
TEST_DB_PATH = ROOT / "test_app.db"
TEST_STORAGE_PATH = ROOT / "test_object_storage"

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("OBJECT_STORAGE_SECRET", "test-storage-secret")
os.environ.setdefault("OBJECT_STORAGE_ROOT", str(TEST_STORAGE_PATH))
os.environ.setdefault("BYBIT_API_KEY", "test-key")
os.environ.setdefault("BYBIT_API_SECRET", "test-secret")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import create_access_token, hash_password
from app.db import Base, SessionLocal, engine
from app.models.common import PortfolioKind, Role, Visibility, TxType
from app.orm_models import AssetORM, PortfolioORM, TxORM, UserORM
from app.main import app


@pytest.fixture(autouse=True)
def clean_state(monkeypatch: pytest.MonkeyPatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    if TEST_STORAGE_PATH.exists():
        shutil.rmtree(TEST_STORAGE_PATH)
    TEST_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

    ticker = SimpleNamespace(lastPrice="100.00", price24hPcnt="0.10")
    monkeypatch.setattr("app.routers.portfolios.fetch_ticker", lambda category, symbol: ticker)
    monkeypatch.setattr(
        "app.routers.market._service.fetch_ticker",
        lambda category, symbol: {
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
        },
    )
    yield
    Base.metadata.drop_all(bind=engine)
    if TEST_STORAGE_PATH.exists():
        shutil.rmtree(TEST_STORAGE_PATH)


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_user(
    *,
    email: str,
    role: Role = Role.user,
    password: str = "Password123",
) -> UserORM:
    with SessionLocal() as session:
        user = UserORM(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


@pytest.fixture
def user_factory():
    return _create_user


@pytest.fixture
def user():
    return _create_user(email="user@example.com")


@pytest.fixture
def manager():
    return _create_user(email="manager@example.com", role=Role.manager)


@pytest.fixture
def admin():
    return _create_user(email="admin@example.com", role=Role.admin)


@pytest.fixture
def auth_headers():
    def factory(user: UserORM) -> dict[str, str]:
        token, _ = create_access_token(user.id, user.email, user.role.value, "session-test")
        return {"Authorization": f"Bearer {token}"}

    return factory


@pytest.fixture
def seed_portfolio():
    def factory(
        owner_id: str,
        *,
        name: str = "Main",
        visibility: Visibility = Visibility.private,
        kind: PortfolioKind = PortfolioKind.personal,
        balance_usd: Decimal = Decimal("0.00"),
    ) -> PortfolioORM:
        with SessionLocal() as session:
            portfolio = PortfolioORM(
                user_id=owner_id,
                name=name,
                visibility=visibility,
                kind=kind,
                balance_usd=balance_usd,
                pnl_day_usd=Decimal("0.00"),
            )
            session.add(portfolio)
            session.commit()
            session.refresh(portfolio)
            session.expunge(portfolio)
            return portfolio

    return factory


@pytest.fixture
def seed_asset():
    def factory(
        portfolio_id: str,
        *,
        symbol: str = "BTC",
        display_name: str | None = None,
    ) -> AssetORM:
        with SessionLocal() as session:
            asset = AssetORM(
                portfolio_id=portfolio_id,
                symbol=symbol,
                display_name=display_name or symbol,
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
            session.expunge(asset)
            return asset

    return factory


@pytest.fixture
def seed_tx():
    def factory(
        asset_id: str,
        *,
        tx_type: TxType = TxType.buy,
        quantity: Decimal = Decimal("1.00000000"),
        price_usd: Decimal | None = Decimal("100.00"),
    ) -> TxORM:
        with SessionLocal() as session:
            tx = TxORM(
                asset_id=asset_id,
                type=tx_type,
                quantity=quantity,
                price_usd=price_usd,
                fee_usd=None,
                at=datetime.now(timezone.utc),
                note="seed",
                tx_hash=None,
            )
            session.add(tx)
            session.commit()
            session.refresh(tx)
            session.expunge(tx)
            return tx

    return factory
