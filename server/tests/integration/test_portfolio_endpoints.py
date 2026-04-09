from __future__ import annotations

import base64
from decimal import Decimal

import pytest

from app.services.bybit import BybitPortfolioSnapshot, BybitServiceError


@pytest.mark.integration
def test_list_portfolios_applies_filters_sorting_and_pagination(
    client,
    user,
    auth_headers,
    seed_portfolio,
):
    seed_portfolio(user.id, name="Zulu", visibility="private", balance_usd=Decimal("50.00"))
    seed_portfolio(user.id, name="Alpha", visibility="public", balance_usd=Decimal("150.00"))

    response = client.get(
        "/api/v1/portfolios?search=alp&visibility=public&sort_by=name&sort_dir=asc&page=1&page_size=1",
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total_items"] == 1
    assert data["total_pages"] == 1
    assert [item["name"] for item in data["items"]] == ["Alpha"]


@pytest.mark.integration
def test_user_cannot_access_other_users_portfolio(client, user, manager, auth_headers, seed_portfolio):
    other_portfolio = seed_portfolio(manager.id, name="Manager private")

    response = client.get(f"/api/v1/portfolios/{other_portfolio.id}", headers=auth_headers(user))
    assert response.status_code == 404


@pytest.mark.integration
def test_manager_can_view_but_not_modify_foreign_portfolio(
    client,
    user,
    manager,
    auth_headers,
    seed_portfolio,
):
    foreign_portfolio = seed_portfolio(user.id, name="User portfolio")

    view_response = client.get(f"/api/v1/portfolios/{foreign_portfolio.id}", headers=auth_headers(manager))
    assert view_response.status_code == 200

    delete_response = client.delete(
        f"/api/v1/portfolios/{foreign_portfolio.id}",
        headers=auth_headers(manager),
    )
    assert delete_response.status_code == 404


@pytest.mark.integration
def test_asset_tx_validation_and_duplicate_symbol_rules(
    client,
    user,
    auth_headers,
    seed_portfolio,
):
    portfolio = seed_portfolio(user.id)

    create_asset = client.post(
        f"/api/v1/portfolios/{portfolio.id}/assets",
        json={"symbol": "btc", "display_name": "Bitcoin"},
        headers=auth_headers(user),
    )
    assert create_asset.status_code == 201
    asset_id = create_asset.json()["id"]
    assert create_asset.json()["symbol"] == "BTC"

    duplicate_asset = client.post(
        f"/api/v1/portfolios/{portfolio.id}/assets",
        json={"symbol": "BTC"},
        headers=auth_headers(user),
    )
    assert duplicate_asset.status_code == 409

    missing_price = client.post(
        f"/api/v1/portfolios/{portfolio.id}/transactions",
        json={
            "asset_id": asset_id,
            "type": "buy",
            "quantity": "1.0",
            "price_usd": None,
            "fee_usd": None,
            "at": "2026-04-09T12:00:00Z",
            "note": None,
            "tx_hash": None,
        },
        headers=auth_headers(user),
    )
    assert missing_price.status_code == 400
    assert missing_price.json()["detail"] == "price_usd is required for buy/sell"

    invalid_page = client.get("/api/v1/portfolios?page=0", headers=auth_headers(user))
    assert invalid_page.status_code == 422
    assert invalid_page.json()["detail"] == "page must be >= 1"


@pytest.mark.integration
def test_public_import_requires_public_visibility(
    client,
    user,
    manager,
    auth_headers,
    seed_portfolio,
    seed_asset,
    seed_tx,
):
    private_source = seed_portfolio(user.id, visibility="private")
    public_source = seed_portfolio(user.id, name="Public source", visibility="public")
    public_asset = seed_asset(public_source.id, symbol="ETH")
    seed_tx(public_asset.id)

    forbidden = client.post(
        "/api/v1/portfolios/import",
        json={"source_id": private_source.id},
        headers=auth_headers(manager),
    )
    assert forbidden.status_code == 403

    imported = client.post(
        "/api/v1/portfolios/import",
        json={"source_id": public_source.id},
        headers=auth_headers(manager),
    )
    assert imported.status_code == 201
    assert imported.json()["kind"] == "subscribed"
    assert imported.json()["visibility"] == "private"


@pytest.mark.integration
def test_file_upload_download_and_invalid_signed_token(
    client,
    user,
    auth_headers,
    seed_portfolio,
):
    portfolio = seed_portfolio(user.id)
    payload = base64.b64encode(b"file-content").decode("ascii")

    upload = client.post(
        f"/api/v1/portfolios/{portfolio.id}/files",
        json={
            "file_name": "report.txt",
            "content_type": "text/plain",
            "content_base64": payload,
        },
        headers=auth_headers(user),
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    download_meta = client.get(
        f"/api/v1/portfolios/{portfolio.id}/files/{file_id}/download",
        headers=auth_headers(user),
    )
    assert download_meta.status_code == 200
    assert "download_url" in download_meta.json()

    url = download_meta.json()["download_url"]
    download = client.get(url, headers=auth_headers(user))
    assert download.status_code == 200
    assert download.content == b"file-content"

    forbidden = client.get(
        f"/api/v1/public/portfolios/{portfolio.id}/files/{file_id}/content?token=badtoken12345"
    )
    assert forbidden.status_code == 403


@pytest.mark.integration
def test_bybit_import_success_and_upstream_failure(
    client,
    user,
    auth_headers,
    seed_portfolio,
    monkeypatch,
):
    portfolio = seed_portfolio(user.id)

    monkeypatch.setattr(
        "app.routers.portfolios.bybit_service.fetch_portfolio_snapshot",
        lambda **kwargs: BybitPortfolioSnapshot(
            holdings={"BTC": Decimal("1.0"), "USDT": Decimal("12.0")},
            prices={"BTC": Decimal("120.0")},
        ),
    )
    success = client.post(
        f"/api/v1/portfolios/{portfolio.id}/import/bybit",
        json={"api_key": "key123456", "api_secret": "secret123456"},
        headers=auth_headers(user),
    )
    assert success.status_code == 200

    assets = client.get(f"/api/v1/portfolios/{portfolio.id}/assets", headers=auth_headers(user))
    assert assets.status_code == 200
    assert [asset["symbol"] for asset in assets.json()] == ["BTC"]

    monkeypatch.setattr(
        "app.routers.portfolios.bybit_service.fetch_portfolio_snapshot",
        lambda **kwargs: (_ for _ in ()).throw(BybitServiceError("Bybit unavailable")),
    )
    failure = client.post(
        f"/api/v1/portfolios/{portfolio.id}/import/bybit",
        json={"api_key": "key123456", "api_secret": "secret123456"},
        headers=auth_headers(user),
    )
    assert failure.status_code == 502
    assert failure.json()["detail"] == "Bybit unavailable"
