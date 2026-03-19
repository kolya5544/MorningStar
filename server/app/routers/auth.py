from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.auth import require_roles, require_user
from app.dependencies.auth import get_auth_service
from app.models.common import Role
from app.services.auth_service import AuthService

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class RegisterResponse(BaseModel):
    ok: bool


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class MeResponse(BaseModel):
    id: str
    email: str
    role: Role


class UserListItemResponse(MeResponse):
    created_at: str


class UpdateRoleRequest(BaseModel):
    role: Role = Field(..., description="New role to assign to the user")


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)):
    auth_service.register(body.email)
    return RegisterResponse(ok=True)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    tokens = auth_service.login(body.email, body.password)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.access_expires_at,
        refresh_expires_in=tokens.refresh_expires_at,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)):
    tokens = auth_service.refresh(body.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.access_expires_at,
        refresh_expires_in=tokens.refresh_expires_at,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, auth_service: AuthService = Depends(get_auth_service)):
    auth_service.logout(body.refresh_token)
    return None


@router.get("/auth/me", response_model=MeResponse)
def me(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    payload = require_user(request)
    user = auth_service.me(str(payload["sub"]))
    return MeResponse(id=str(user.id), email=user.email, role=user.role)


@router.get("/auth/users", response_model=list[UserListItemResponse])
def list_users(request: Request, auth_service: AuthService = Depends(get_auth_service)):
    require_roles(request, [Role.admin])
    rows = auth_service.list_users()
    return [
        UserListItemResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            created_at=user.created_at.isoformat(),
        )
        for user in rows
    ]


@router.patch("/auth/users/{user_id}/role", response_model=MeResponse)
def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    require_roles(request, [Role.admin])
    user = auth_service.update_user_role(user_id, body.role)
    return MeResponse(id=str(user.id), email=user.email, role=user.role)
