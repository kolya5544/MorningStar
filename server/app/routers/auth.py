# app/routers/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.orm_models import UserORM
from app.auth import generate_password, hash_password, verify_password, create_access_token, send_password_email, require_user

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


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=422, detail="Invalid email")

    password = generate_password()
    user = UserORM(email=email, password_hash=hash_password(password))

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
    email = body.email.strip().lower()

    u = db.execute(select(UserORM).where(UserORM.email == email)).scalar_one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, exp = create_access_token(u.id, u.email)
    return TokenResponse(access_token=token, expires_in=exp)


@router.get("/auth/me", response_model=MeResponse)
def me(request: Request):
    payload = require_user(request)
    return MeResponse(id=str(payload["sub"]), email=str(payload["email"]))
