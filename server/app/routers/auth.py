"""Authentication API routes.

This router exposes endpoints for user registration, login, retrieving the
authenticated user's details and administrative role management. It has been
extended to include the user's ``role`` claim in the JWT and adds an
endpoint for administrators to update other users' roles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.orm_models import UserORM
from app.auth import (
    generate_password,
    hash_password,
    verify_password,
    create_access_token,
    send_password_email,
    require_user,
    require_roles,
)
from app.models.common import Role

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class RegisterResponse(BaseModel):
    ok: bool


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # unix timestamp exp


class MeResponse(BaseModel):
    id: str
    email: str
    role: Role


class UserListItemResponse(MeResponse):
    created_at: str


class UpdateRoleRequest(BaseModel):
    role: Role = Field(..., description="New role to assign to the user")


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user.

    A password is generated and emailed to the new user. The new user is assigned the
    default ``Role.user`` role.
    """
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=422, detail="Invalid email")

    password = generate_password()
    user = UserORM(email=email, password_hash=hash_password(password), role=Role.user)

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists")

    # отправляем пароль на почту; если не вышло — удалим юзера, чтобы не оставлять “мертвый” аккаунт
    try:
        send_password_email(email, password)
    except Exception as e:
        db.delete(user)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    return RegisterResponse(ok=True)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and issue a JWT.

    The returned token embeds the user's role. If the credentials are invalid, a
    401 response is returned. The ``expires_in`` field is the absolute UNIX
    expiry timestamp (same as the ``exp`` claim).
    """
    email = body.email.strip().lower()

    u = db.execute(select(UserORM).where(UserORM.email == email)).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, exp = create_access_token(u.id, u.email, u.role.value)
    return TokenResponse(access_token=token, expires_in=exp)


@router.get("/auth/me", response_model=MeResponse)
def me(request: Request):
    """Return details about the current authenticated user."""
    payload = require_user(request)
    return MeResponse(id=str(payload["sub"]), email=str(payload["email"]), role=Role(payload["role"]))


@router.get("/auth/users", response_model=list[UserListItemResponse])
def list_users(request: Request, db: Session = Depends(get_db)):
    require_roles(request, [Role.admin])
    rows = db.execute(select(UserORM).order_by(UserORM.created_at.asc())).scalars().all()
    return [
        UserListItemResponse(
            id=str(u.id),
            email=u.email,
            role=u.role,
            created_at=u.created_at.isoformat(),
        )
        for u in rows
    ]


@router.patch("/auth/users/{user_id}/role", response_model=MeResponse)
def update_user_role(user_id: str, body: UpdateRoleRequest, request: Request, db: Session = Depends(get_db)):
    """Update the role of a user (admin only).

    This endpoint is restricted to admins. It allows changing another user's role to
    ``user``, ``manager`` or ``admin``. Returns the updated user record. Attempting
    to change your own role is also permitted (admins may demote themselves).
    """
    require_roles(request, [Role.admin])
    # fetch user
    u = db.get(UserORM, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.role = body.role
    db.add(u)
    db.commit()
    db.refresh(u)
    # issue new token for updated user? not here; admin might not be the same user
    return MeResponse(id=str(u.id), email=u.email, role=u.role)
