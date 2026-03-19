"""Authentication helpers for MorningStar.

This module provides password hashing, JSON Web Token (JWT) utilities
and FastAPI dependencies for authenticating and authorising users.
It extends the existing implementation to carry the user's ``role`` in
the JWT payload and provides helper functions for role‑based access
control (RBAC).
"""

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
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, Optional, Sequence

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.common import Role

# ===== Password hashing (stdlib PBKDF2) =====
_PBKDF2_ITERS = int(os.getenv("PBKDF2_ITERS", "200000"))


def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS, dklen=32)
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${base64.urlsafe_b64encode(salt).decode().rstrip('=')}${base64.urlsafe_b64encode(dk).decode().rstrip('=')}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64url_decode(salt_b64)
        dk_expected = _b64url_decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=len(dk_expected))
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


# ===== JWT HS256 (stdlib) =====
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


def create_access_token(user_id: str, email: str, role: str) -> tuple[str, int]:
    """Issue a JWT for ``user_id`` with an expiry and role.

    The token payload includes ``sub`` (subject, the user ID), ``email``, ``role``,
    issued at (``iat``) and expiry (``exp``) timestamps. Clients can use the
    ``role`` claim to adapt their UI, and the backend uses it to enforce
    RBAC via :func:`require_roles`.
    """
    now = int(time.time())
    exp = now + JWT_EXPIRE_MINUTES * 60
    payload = {"sub": user_id, "email": email, "role": role, "iat": now, "exp": exp}
    token = _jwt_encode(payload, JWT_SECRET)
    return token, exp


def decode_access_token(token: str) -> Dict[str, Any]:
    payload = _jwt_decode(token, JWT_SECRET)
    # basic shape checks
    if "sub" not in payload or "email" not in payload or "role" not in payload:
        raise ValueError("bad token payload")
    return payload


def _jwt_encode(payload: Dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    s = _b64url_encode(sig)
    return f"{h}.{p}.{s}"


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


# ===== Middleware =====
class AuthMiddleware(BaseHTTPMiddleware):
    """Attach decoded token payload (if present) to ``request.state.user``.

    If the token is missing or invalid, ``request.state.user`` remains ``None``.
    If the token is invalid, an error string is stored in ``request.state.auth_error``.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        request.state.auth_error = None

        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                request.state.user = decode_access_token(token)
            except Exception as e:
                request.state.auth_error = str(e)

        return await call_next(request)


def require_user(request: Request) -> Dict[str, Any]:
    """Ensure that ``request.state.user`` exists and return it.

    Raises ``401 Unauthorized`` if the user is missing or the token is invalid. Use
    this dependency at the top of endpoints that require any authenticated user.
    """
    if request.state.user is None:
        # если токен был, но плохой — даём 401
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
    """Ensure the authenticated user has one of ``allowed_roles``.

    This dependency builds on :func:`require_user` and checks the ``role`` claim of
    the JWT. It raises ``403 Forbidden`` if the role is not permitted. It returns
    the decoded token payload when successful.
    """
    payload = require_user(request)
    user_role = payload.get("role")
    # normalise allowed_roles to strings
    allowed = {r.value if isinstance(r, Role) else r for r in allowed_roles}
    if user_role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return payload


# ===== SMTP (Proton SMTP Submission) =====
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
    msg["Subject"] = "MorningStar — your password"
    msg.set_content(
        "Your MorningStar account was created.\n\n"
        f"Email: {to_email}\n"
        f"Password: {password}\n\n"
        "Use this password to log in.\n"
        "If you didn’t request this, ignore this email.\n"
    )

    with smtplib.SMTP(host, port, timeout=20) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(username, smtp_pass)
        s.send_message(msg)