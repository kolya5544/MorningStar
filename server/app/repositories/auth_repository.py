from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.orm_models import RefreshSessionORM, UserORM


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> UserORM | None:
        return self.db.execute(select(UserORM).where(UserORM.email == email)).scalar_one_or_none()

    def get_user_by_id(self, user_id: str) -> UserORM | None:
        return self.db.get(UserORM, user_id)

    def create_user(self, user: UserORM) -> UserORM:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user: UserORM) -> None:
        self.db.delete(user)
        self.db.commit()

    def list_users(self) -> list[UserORM]:
        return self.db.execute(select(UserORM).order_by(UserORM.created_at.asc())).scalars().all()

    def update_user_role(self, user: UserORM, role) -> UserORM:
        user.role = role
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_refresh_session(self, session: RefreshSessionORM) -> RefreshSessionORM:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_refresh_session(self, session_id: str) -> RefreshSessionORM | None:
        return self.db.get(RefreshSessionORM, session_id)

    def revoke_user_sessions(self, user_id: str, reason: str) -> int:
        sessions = self.db.execute(
            select(RefreshSessionORM).where(
                RefreshSessionORM.user_id == user_id,
                RefreshSessionORM.revoked_at.is_(None),
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for session in sessions:
            session.revoked_at = now
            session.revoke_reason = reason
            self.db.add(session)
        self.db.commit()
        return len(sessions)

    def revoke_session(self, session: RefreshSessionORM, reason: str) -> RefreshSessionORM:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoke_reason = reason
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def rotate_refresh_session(
        self,
        session: RefreshSessionORM,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshSessionORM:
        now = datetime.now(timezone.utc)
        session.token_hash = token_hash
        session.expires_at = expires_at
        session.rotated_at = now
        session.last_used_at = now
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
