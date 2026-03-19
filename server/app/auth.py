from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import string
import time
from email.message import EmailMessage
from typing import Any, Dict, Sequence

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import SessionLocal
from app.models.common import Role
from app.orm_models import UserORM

_PBKDF2_ITERS = int(os.getenv("PBKDF2_ITERS", "200000"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", os.getenv("JWT_EXPIRE_MINUTES", "15"))
)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS, dklen=32)
    return (
        f"pbkdf2_sha256${_PBKDF2_ITERS}$"
        f"{base64.urlsafe_b64encode(salt).decode().rstrip('=')}$"
        f"{base64.urlsafe_b64encode(dk).decode().rstrip('=')}"
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64url_decode(salt_b64)
        dk_expected = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iters,
            dklen=len(dk_expected),
        )
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str, session_id: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "typ": "access",
        "sub": user_id,
        "email": email,
        "role": role,
        "sid": session_id,
        "iat": now,
        "exp": exp,
    }
    return _jwt_encode(payload, JWT_SECRET), exp


def create_refresh_token(user_id: str, session_id: str, token_id: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    payload = {
        "typ": "refresh",
        "sub": user_id,
        "sid": session_id,
        "jti": token_id,
        "iat": now,
        "exp": exp,
    }
    return _jwt_encode(payload, JWT_SECRET), exp


def decode_access_token(token: str) -> Dict[str, Any]:
    payload = _jwt_decode(token, JWT_SECRET)
    if payload.get("typ") != "access":
        raise ValueError("invalid token type")
    if "sub" not in payload or "email" not in payload or "role" not in payload or "sid" not in payload:
        raise ValueError("bad token payload")
    return payload


def decode_refresh_token(token: str) -> Dict[str, Any]:
    payload = _jwt_decode(token, JWT_SECRET)
    if payload.get("typ") != "refresh":
        raise ValueError("invalid token type")
    if "sub" not in payload or "sid" not in payload or "jti" not in payload:
        raise ValueError("bad token payload")
    return payload


def new_refresh_token_id() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token_id(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


def refresh_expiry_timestamp() -> int:
    return int(time.time()) + REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def refresh_expiry_datetime_from_ts(exp: int):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(exp, tz=timezone.utc)


def _jwt_encode(payload: Dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def _jwt_decode(token: str, secret: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("bad token")
    h, p, s = parts
    signing_input = f"{h}.{p}".encode("utf-8")
    sig = _b64url_decode(s)
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("bad signature")
    payload = json.loads(_b64url_decode(p).decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp and int(time.time()) >= exp:
        raise ValueError("token expired")
    return payload


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        request.state.auth_error = None

        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                payload = decode_access_token(token)
                with SessionLocal() as db:
                    user = db.get(UserORM, str(payload["sub"]))
                    if not user:
                        raise ValueError("user not found")
                    request.state.user = {
                        "sub": user.id,
                        "email": user.email,
                        "role": user.role.value,
                        "sid": str(payload["sid"]),
                    }
            except Exception as exc:
                request.state.auth_error = str(exc)

        return await call_next(request)


def require_user(request: Request) -> Dict[str, Any]:
    if request.state.user is None:
        detail = "Not authenticated"
        if request.state.auth_error:
            detail = f"Invalid token: {request.state.auth_error}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return request.state.user


def require_roles(request: Request, allowed_roles: Sequence[Role | str]) -> Dict[str, Any]:
    user = require_user(request)
    user_role = user.get("role")
    allowed = {role.value if isinstance(role, Role) else role for role in allowed_roles}
    if user_role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user


def send_password_email(to_email: str, password: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_TOKEN")
    from_email = os.getenv("SMTP_FROM") or username

    if not (host and username and smtp_pass and from_email):
        raise RuntimeError("SMTP is not configured (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM)")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = "MorningStar - your password"
    msg.set_content(
        "Your MorningStar account was created.\n\n"
        f"Email: {to_email}\n"
        f"Password: {password}\n\n"
        "Use this password to log in.\n"
        "If you did not request this, ignore this email.\n"
    )

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(username, smtp_pass)
        smtp.send_message(msg)
