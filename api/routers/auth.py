"""Authentication and CSRF token endpoints."""
from __future__ import annotations

import logging
import sys
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import User, UserRole, get_auth_manager, get_current_user
from api.security import (
    RateLimiter,
    get_client_ip,
    _csrf_manager,
    _login_rate_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


def _get_cache(fastapi_request: Request):
    server_mod = sys.modules.get("api.server")
    return getattr(fastapi_request.app.state, "cache", None) or (
        getattr(server_mod, "cache", None) if server_mod else None
    )


@router.post("/auth/login", tags=["Authentication"])
async def login(request: LoginRequest, fastapi_request: Request):
    """Authenticate user and return JWT token.

    Production requirements:
    - Users must be configured via ADMIN_USER and USER_USER env vars
    - AUTH_DISABLED must be false for production
    - No demo/fallback authentication
    - Rate limited: 5 attempts per minute per IP
    """
    auth = get_auth_manager()

    # Rate limiting on login (distributed Redis-backed with in-memory fallback)
    client_ip = get_client_ip(fastapi_request)
    cache = _get_cache(fastapi_request)
    redis_client = getattr(cache, "redis", None) if cache is not None else None
    if not await _login_rate_limiter.check_async(client_ip, redis_client=redis_client):
        logger.warning(f"Rate limit exceeded for login from IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please wait before trying again."
        )

    if auth.auth_disabled:
        if not auth._users:
            raise HTTPException(
                status_code=503,
                detail="Authentication not configured. Please set ADMIN_USER and USER_USER environment variables."
            )
        user_data = auth.authenticate(request.username, request.password)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        user_data = auth.authenticate(request.username, request.password)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth.create_token(user_data["user_id"], user_data["username"], UserRole(user_data["role"]))

    return LoginResponse(
        access_token=token,
        expires_in=auth.expiration_hours * 3600,
        user={
            "user_id": user_data["user_id"],
            "username": user_data["username"],
            "role": user_data["role"]
        }
    )


@router.post("/auth/logout", tags=["Authentication"])
async def logout(request: Request, current_user: User = Depends(get_current_user)):
    """Logout: revoke the presented token server-side.

    Revocation is in-memory for this process; tokens also expire automatically
    after the configured JWT lifetime. Clients must still discard the token.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        get_auth_manager().revoke_token(auth_header[7:])
    return {
        "message": "Logged out successfully",
        "revocation": "token_revoked",
        "note": "Revocation is in-memory for this process; tokens also expire automatically.",
    }


@router.get("/auth/me", tags=["Authentication"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role.value,
        "email": current_user.email
    }


@router.get("/auth/csrf-token", tags=["Authentication"])
async def get_csrf_token(current_user: User = Depends(get_current_user)):
    """Issue a stateless CSRF token bound to the authenticated user."""
    token = _csrf_manager.generate_token(current_user.user_id)
    return {
        "csrf_token": token,
        "user_id": current_user.user_id,
        "header_name": "X-CSRF-Token",
    }
