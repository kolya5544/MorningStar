from __future__ import annotations

from fastapi import HTTPException

import pytest

from app.models.common import Role
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService


@pytest.mark.unit
def test_register_normalizes_email_sends_password_and_assigns_user_role(db_session, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.auth_service.generate_password", lambda: "Secret123")
    monkeypatch.setattr(
        "app.services.auth_service.send_password_email",
        lambda email, password: sent.update({"email": email, "password": password}),
    )
    service = AuthService(AuthRepository(db_session))

    service.register("  NewUser@Example.com  ")

    user = AuthRepository(db_session).get_user_by_email("newuser@example.com")
    assert user is not None
    assert user.role == Role.user
    assert sent == {"email": "newuser@example.com", "password": "Secret123"}


@pytest.mark.unit
def test_refresh_rejects_reused_token_and_revokes_session(db_session, user_factory):
    user = user_factory(email="refresh@example.com", password="Password123")
    service = AuthService(AuthRepository(db_session))
    pair = service.login("refresh@example.com", "Password123")

    rotated = service.refresh(pair.refresh_token)
    assert rotated.refresh_token != pair.refresh_token

    with pytest.raises(HTTPException) as exc:
        service.refresh(pair.refresh_token)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Refresh token reuse detected"
    session = AuthRepository(db_session).get_refresh_session(
        service.repository.list_users()[0].refresh_sessions[0].id
    )
    assert session is not None
    assert session.revoked_at is not None
    assert session.revoke_reason == "token_reuse_detected"
