from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_password,
    hash_password,
    hash_refresh_token_id,
    new_refresh_token_id,
    refresh_expiry_datetime_from_ts,
    send_password_email,
    verify_password,
)
from app.models.common import Role
from app.orm_models import RefreshSessionORM, UserORM
from app.repositories.auth_repository import AuthRepository


@dataclass
class TokenPair:
    access_token: str
    access_expires_at: int
    refresh_token: str
    refresh_expires_at: int
    token_type: str = "bearer"


class AuthService:
    def __init__(self, repository: AuthRepository):
        self.repository = repository

    def register(self, email: str) -> None:
        normalized = email.strip().lower()
        if "@" not in normalized or "." not in normalized:
            raise HTTPException(status_code=422, detail="Invalid email")

        password = generate_password()
        user = UserORM(email=normalized, password_hash=hash_password(password), role=Role.user)

        try:
            self.repository.create_user(user)
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status_code=409, detail="User already exists")

        try:
            send_password_email(normalized, password)
        except Exception as exc:
            self.repository.delete_user(user)
            raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")

    def login(self, email: str, password: str) -> TokenPair:
        normalized = email.strip().lower()
        user = self.repository.get_user_by_email(normalized)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        self.repository.revoke_user_sessions(user.id, "replaced_by_new_login")
        return self._create_session_tokens(user)

    def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_refresh_token(refresh_token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid refresh token: {exc}")

        session = self.repository.get_refresh_session(str(payload["sid"]))
        if not session:
            raise HTTPException(status_code=401, detail="Refresh session not found")
        if session.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Refresh session revoked")
        if self._as_utc(session.expires_at) <= datetime.now(timezone.utc):
            self.repository.revoke_session(session, "expired")
            raise HTTPException(status_code=401, detail="Refresh session expired")

        token_hash = hash_refresh_token_id(str(payload["jti"]))
        if token_hash != session.token_hash:
            self.repository.revoke_session(session, "token_reuse_detected")
            raise HTTPException(status_code=401, detail="Refresh token reuse detected")

        user = self.repository.get_user_by_id(session.user_id)
        if not user:
            self.repository.revoke_session(session, "user_not_found")
            raise HTTPException(status_code=401, detail="User not found")

        next_refresh_id = new_refresh_token_id()
        new_refresh_token, refresh_exp = create_refresh_token(user.id, session.id, next_refresh_id)
        self.repository.rotate_refresh_session(
            session,
            token_hash=hash_refresh_token_id(next_refresh_id),
            expires_at=refresh_expiry_datetime_from_ts(refresh_exp),
        )
        access_token, access_exp = create_access_token(user.id, user.email, user.role.value, session.id)
        return TokenPair(
            access_token=access_token,
            access_expires_at=access_exp,
            refresh_token=new_refresh_token,
            refresh_expires_at=refresh_exp,
        )

    def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_refresh_token(refresh_token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid refresh token: {exc}")

        session = self.repository.get_refresh_session(str(payload["sid"]))
        if not session:
            return
        if session.revoked_at is None:
            self.repository.revoke_session(session, "logout")

    def me(self, user_id: str) -> UserORM:
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    def list_users(self) -> list[UserORM]:
        return self.repository.list_users()

    def update_user_role(self, user_id: str, role: Role) -> UserORM:
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        updated = self.repository.update_user_role(user, role)
        self.repository.revoke_user_sessions(updated.id, "role_changed")
        return updated

    def _create_session_tokens(self, user: UserORM) -> TokenPair:
        session_id = str(uuid4())
        refresh_id = new_refresh_token_id()
        refresh_token, refresh_exp = create_refresh_token(user.id, session_id, refresh_id)
        session = RefreshSessionORM(
            id=session_id,
            user_id=user.id,
            token_hash=hash_refresh_token_id(refresh_id),
            expires_at=refresh_expiry_datetime_from_ts(refresh_exp),
        )
        self.repository.create_refresh_session(session)
        access_token, access_exp = create_access_token(user.id, user.email, user.role.value, session_id)
        return TokenPair(
            access_token=access_token,
            access_expires_at=access_exp,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_exp,
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
