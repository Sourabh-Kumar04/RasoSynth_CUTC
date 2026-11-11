"""Security, rate limiting, and cryptographic token verification helpers."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import tempfile
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import HTTPException, Request
except ImportError:
    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int = 500, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
    Request = Any  # type: ignore

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter supporting distributed Redis-backed coordination and in-memory fallback.

    Ensures rate limits apply uniformly across multi-worker (Uvicorn --workers N) deployments.
    Limits: max N requests per window_seconds per client_key (typically IP).
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60, prefix: str = "general"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.prefix = prefix
        self._buckets: Dict[str, list] = {}

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            k for k, v in self._buckets.items()
            if v and (now - v[-1]) > self.window_seconds
        ]
        for k in expired_keys:
            del self._buckets[k]

    def _check_memory(self, client_key: str) -> bool:
        now = time.time()
        self._cleanup()

        if client_key not in self._buckets:
            self._buckets[client_key] = []

        cutoff = now - self.window_seconds
        self._buckets[client_key] = [t for t in self._buckets[client_key] if t > cutoff]

        if len(self._buckets[client_key]) >= self.max_requests:
            return False

        self._buckets[client_key].append(now)
        return True

    async def check_async(self, client_key: str, redis_client=None) -> bool:
        """Asynchronously check rate limit, coordinating across workers via Redis if available."""
        if redis_client is not None:
            try:
                now = time.time()
                bucket_window = int(now // self.window_seconds)
                redis_key = f"ratelimit:{self.prefix}:{client_key}:{bucket_window}"
                count = await redis_client.incr(redis_key)
                if count == 1:
                    await redis_client.expire(redis_key, self.window_seconds + 5)
                if count > self.max_requests:
                    return False
                return True
            except Exception as e:
                logger.debug(f"Redis rate limiter fallback to memory: {e}")
        return self._check_memory(client_key)

    def check(self, client_key: str) -> bool:
        """Synchronous check using in-memory state."""
        return self._check_memory(client_key)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request.

    X-Forwarded-For is trusted ONLY when TRUST_PROXY=true (i.e. the app
    really sits behind a trusted proxy that sets it). By default it is
    ignored, because any client can forge it and login/provider-test
    rate limits keyed on a forged IP are trivially bypassed.
    """
    if os.getenv("TRUST_PROXY", "false").lower() in ("true", "1", "yes"):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Global rate limiters (multi-worker safe)
_login_rate_limiter = RateLimiter(max_requests=5, window_seconds=60, prefix="login")
_provider_test_rate_limiter = RateLimiter(max_requests=20, window_seconds=60, prefix="provider_test")


class CSRFTokenManager:
    """Manages CSRF tokens for state-changing operations.

    Uses HMAC-signed stateless tokens so they work across multi-worker deployments
    without shared in-memory state.
    """

    def __init__(self):
        self._token_ttl = int(os.getenv("CSRF_TOKEN_TTL_SECONDS", "3600"))  # 1 hour default
        secret = os.getenv("CSRF_SECRET")
        if not secret:
            # Check temp cached secret across multi-process workers on the same machine
            secret_file = Path(tempfile.gettempdir()) / ".rasosynth_auto_csrf_secret"
            cached = None
            if secret_file.exists():
                try:
                    c = secret_file.read_text(encoding="utf-8").strip()
                    if len(c) >= 32:
                        cached = c
                except Exception:
                    pass
            if not cached:
                cached = secrets.token_hex(32)
                try:
                    secret_file.write_text(cached, encoding="utf-8")
                except Exception:
                    pass
            secret = cached
            os.environ["CSRF_SECRET"] = secret
        self._secret = secret

    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret.encode(), payload.encode(), "sha256").hexdigest()[:16]

    def generate_token(self, user_id: str) -> str:
        """Generate a stateless CSRF token for a user."""
        timestamp = str(int(time.time()))
        raw = f"{user_id}:{timestamp}"
        sig = self._sign(raw)
        return f"{sig}:{timestamp}:{user_id}"

    def validate_token(self, token: str, user_id: str) -> bool:
        """Validate a CSRF token. Returns True if valid."""
        parts = token.split(":", 2)
        if len(parts) != 3:
            return False

        expected_sig, timestamp, token_user_id = parts

        # Verify user_id matches
        if token_user_id != user_id:
            return False

        # Verify signature
        raw = f"{user_id}:{timestamp}"
        expected = self._sign(raw)
        if not hmac.compare_digest(expected_sig, expected):
            return False

        # Check expiry
        age = time.time() - float(timestamp)
        if age > self._token_ttl:
            return False

        return True


_csrf_manager = CSRFTokenManager()


def _sign_approved_examples(query: str, examples: list[dict]) -> str:
    """Sign server-generated preview examples so jobs cannot inject records."""
    payload = json.dumps(
        {"query": query, "examples": examples},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    shared_secret = os.getenv("CSRF_SECRET") or os.getenv("JWT_SECRET")
    if not shared_secret:
        try:
            from core.config import get_settings
            shared_secret = get_settings().jwt_secret
        except Exception:
            pass
    shared_secret = shared_secret or _csrf_manager._secret
    return hmac.new(shared_secret.encode(), payload.encode(), "sha256").hexdigest()


def _get_download_signing_secret() -> str:
    """Resolve dedicated signing secret for download and preview URLs.

    Fails closed when absent: no fallback to JWT_SECRET or CSRF secret.
    """
    secret = os.getenv("DOWNLOAD_SIGNING_SECRET") or os.getenv("PREVIEW_SIGNING_SECRET")
    if not secret:
        try:
            from core.config import get_settings
            secret = getattr(get_settings(), "download_signing_secret", None)
        except Exception:
            secret = None
    if not secret:
        raise RuntimeError(
            "Dedicated download signing secret (DOWNLOAD_SIGNING_SECRET) is not configured; "
            "presigned URL signing fails closed without JWT_SECRET fallback."
        )
    return str(secret).strip()


def _sign_download_token(job_id: str, expires_at: int, user: str = "", format: str = "") -> str:
    """Generate an HMAC-SHA256 signature for presigned dataset downloads.

    Binds user, format, expiry, and single-purpose ("download") in the HMAC.
    Uses dedicated signing secret; fails closed if absent.
    """
    signing_secret = _get_download_signing_secret()
    payload = f"dataset_download:{job_id}:{user}:{format}:{expires_at}"
    return hmac.new(signing_secret.encode("utf-8"), payload.encode("utf-8"), "sha256").hexdigest()


def _verify_download_token(job_id: str, token: Optional[str], expires_at: Optional[int], user: str = "", format: str = "") -> bool:
    """Verify an ephemeral download token against expiration and HMAC signature.

    Fails closed if dedicated signing secret is not configured or token is invalid.
    No fallback to JWT_SECRET.
    """
    if not token or expires_at is None:
        return False
    try:
        expires_int = int(expires_at)
    except (ValueError, TypeError):
        return False

    if time.time() > (expires_int + 60):
        return False

    try:
        expected_sig = _sign_download_token(job_id, expires_int, user=user, format=format)
    except Exception:
        return False

    return hmac.compare_digest(expected_sig, str(token).strip())


def _enforce_owner(resource: Optional[dict], current_user, resource_name: str = "Resource"):
    """Enforce owner check: Admin can access any row; non-admin can only access own rows."""
    from api.auth import UserRole, enforce_owner
    if not resource:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
    if getattr(current_user, "role", None) == UserRole.ADMIN:
        return
    enforce_owner(resource, current_user, resource_name=resource_name)
