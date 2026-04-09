from __future__ import annotations

import pytest


@pytest.mark.integration
def test_auth_flow_register_login_refresh_logout_and_me(client, monkeypatch):
    monkeypatch.setattr("app.services.auth_service.generate_password", lambda: "Secret123")
    monkeypatch.setattr("app.services.auth_service.send_password_email", lambda *_: None)

    register_response = client.post("/api/v1/auth/register", json={"email": "Case@Test.com"})
    assert register_response.status_code == 201
    assert register_response.json() == {"ok": True}

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "case@test.com", "password": "Secret123"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert set(tokens) == {
        "access_token",
        "refresh_token",
        "token_type",
        "expires_in",
        "refresh_expires_in",
    }

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "case@test.com"

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["refresh_token"] != tokens["refresh_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_response.json()["refresh_token"]},
    )
    assert logout_response.status_code == 204

    reuse_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_response.json()["refresh_token"]},
    )
    assert reuse_response.status_code == 401
    assert "revoked" in reuse_response.json()["detail"].lower()


@pytest.mark.integration
def test_only_admin_can_manage_user_roles(client, user, admin, auth_headers):
    forbidden = client.get("/api/v1/auth/users", headers=auth_headers(user))
    assert forbidden.status_code == 403

    response = client.get("/api/v1/auth/users", headers=auth_headers(admin))
    assert response.status_code == 200
    assert len(response.json()) == 2

    promote = client.patch(
        f"/api/v1/auth/users/{user.id}/role",
        json={"role": "manager"},
        headers=auth_headers(admin),
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "manager"
