"""JWT-based authentication for API endpoints with secure password hashing.

Security features:
- bcrypt password hashing with unique salts per password
- Constant-time comparison for all password verification
- Migration path for legacy plaintext/PBKDF2 hashes
- Enforced minimum JWT secret length (32+ chars)
- Critical logging when auth is disabled
- Token format validation even when auth is disabled
"""
import os
import logging
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import re

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

# Use bcrypt for secure password hashing (unique salt per password automatically)
try:
    import bcrypt as _bcrypt
    HAS_BCRYPT = True
except ImportError:
    _bcrypt = None
    HAS_BCRYPT = False

logger = logging.getLogger(__name__)

# Sentinel constant to mark legacy plaintext passwords for migration
_LEGACY_PREFIX = "$pbkdf2-sha256$"
_BCRYPT_PREFIX = "$2b$"


class UserRole(str, Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


@dataclass
class User:
    """User information."""
    user_id: str
    username: str
    role: UserRole
    email: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class TokenData:
    """JWT token data."""
    user_id: str
    username: str
    role: str
    exp: datetime


class AuthManager:
    """Manages authentication and authorization.

    Production configuration:
    - Users must be configured via environment variables or database
    - No hardcoded demo credentials
    - AUTH_DISABLED=false enforces authentication
    - Passwords hashed with bcrypt (unique salt per password)
    """

    def __init__(self):
        self.secret = os.getenv("JWT_SECRET")
        if not self.secret:
            raise ValueError("JWT_SECRET environment variable is required")

        if len(self.secret) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )

        # Reject weak/common secrets
        weak_patterns = ["password", "secret", "changeme", "demo", "test", "1234", "0000", "qwerty", "abcdef"]
        if any(p in self.secret.lower() for p in weak_patterns):
            raise ValueError(
                "JWT_SECRET contains common/weak patterns. "
                "Generate a cryptographically random secret with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )

        # Entropy check: ensure reasonable character variety
        unique_chars = len(set(self.secret))
        if unique_chars < 16:
            raise ValueError(
                f"JWT_SECRET has low character diversity ({unique_chars} unique chars). "
                "Generate a cryptographically random secret."
            )

        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

        if self.expiration_hours < 1 or self.expiration_hours > 168:
            raise ValueError("JWT_EXPIRATION_HOURS must be between 1 and 168 (7 days)")

        # Auth disabled mode - log critical warning
        self.auth_disabled = os.getenv("AUTH_DISABLED", "false").lower() == "true"
        if self.auth_disabled:
            logger.critical(
                "AUTH_DISABLED=True - Authentication is DISABLED. "
                "This should NEVER be used in production. "
                "Set AUTH_DISABLED=false and configure ADMIN_USER/USER_USER environment variables."
            )

        # Load users from environment - no hardcoded credentials
        # Format: ADMIN_USER=username:password, USER_USER=username:password
        self._users: Dict[str, Dict] = {}

        admin_user = os.getenv("ADMIN_USER")
        if admin_user and ":" in admin_user:
            username, password = admin_user.split(":", 1)
            self._users[username] = {
                "user_id": "admin-001",
                "username": username,
                "password_hash": self._hash_password(password),
                "role": UserRole.ADMIN,
                "email": os.getenv("ADMIN_EMAIL", "admin@example.com")
            }

        regular_user = os.getenv("USER_USER")
        if regular_user and ":" in regular_user:
            username, password = regular_user.split(":", 1)
            self._users[username] = {
                "user_id": "user-001",
                "username": username,
                "password_hash": self._hash_password(password),
                "role": UserRole.USER,
                "email": os.getenv("USER_EMAIL", "user@example.com")
            }

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt with unique salt per password.

        Falls back to PBKDF2 with random salt if bcrypt is unavailable.
        Returns a self-contained hash string that includes the salt and algorithm info.
        """
        if HAS_BCRYPT and _bcrypt is not None:
            # bcrypt generates a unique salt automatically per call
            password_bytes = password.encode("utf-8")
            hashed = _bcrypt.hashpw(password_bytes, _bcrypt.gensalt(rounds=12))
            return hashed.decode("utf-8")
        else:
            # Fallback: PBKDF2 with random 32-byte salt
            salt = os.urandom(32)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
            # Store as: $pbkdf2-sha256$<salt_hex>$<hash_hex>
            return f"{_LEGACY_PREFIX}{salt.hex()}${dk.hex()}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against its stored hash.

        Supports:
        1. bcrypt hashes ($2b$...) - preferred
        2. PBKDF2 hashes ($pbkdf2-sha256$...) - fallback/migration
        3. Legacy plaintext (no prefix) - migration path
        """
        if stored_hash.startswith(_BCRYPT_PREFIX) and HAS_BCRYPT and _bcrypt is not None:
            # bcrypt verification - constant time
            try:
                return _bcrypt.checkpw(
                    password.encode("utf-8"),
                    stored_hash.encode("utf-8")
                )
            except Exception:
                return False

        elif stored_hash.startswith(_LEGACY_PREFIX):
            # PBKDF2 verification - constant time
            try:
                parts = stored_hash[len(_LEGACY_PREFIX):].split("$")
                if len(parts) != 2:
                    return False
                salt = bytes.fromhex(parts[0])
                expected_hash = parts[1]
                dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
                return hmac.compare_digest(dk.hex(), expected_hash)
            except Exception:
                return False

        else:
            # Legacy plaintext password - migrate on successful verification
            logger.warning("Legacy plaintext password detected for migration. Consider re-hashing.")
            # Use constant-time comparison even for legacy
            return hmac.compare_digest(stored_hash, password)

    def create_token(self, user_id: str, username: str, role: UserRole) -> str:
        """Create JWT token for user."""
        exp = datetime.utcnow() + timedelta(hours=self.expiration_hours)

        payload = {
            "user_id": user_id,
            "username": username,
            "role": role.value,
            "exp": int(exp.timestamp())
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> TokenData:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return TokenData(
                user_id=payload["user_id"],
                username=payload["username"],
                role=payload["role"],
                exp=datetime.fromtimestamp(payload["exp"])
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user with username and password using bcrypt verification.

        Uses bcrypt for verification which provides:
        - Automatic unique salt per password
        - Constant-time comparison
        - Configurable cost factor (work factor)
        """
        user_data = self._users.get(username)
        if not user_data:
            # Prevent timing attacks - always perform equivalent work
            # even for invalid usernames. Use bcrypt if available.
            if HAS_BCRYPT and _bcrypt is not None:
                dummy_hash = _bcrypt.hashpw(b"dummy", _bcrypt.gensalt(rounds=12))
                _bcrypt.checkpw(b"dummy", dummy_hash)
            else:
                hashlib.pbkdf2_hmac('sha256', password.encode(), os.urandom(32), 600000)
            return None

        stored_hash = user_data["password_hash"]
        if not self._verify_password(password, stored_hash):
            return None

        return {
            "user_id": user_data["user_id"],
            "username": username,
            "role": user_data["role"].value,
            "email": user_data.get("email")
        }

    def create_user(self, username: str, password: str, role: UserRole = UserRole.USER, email: Optional[str] = None) -> str:
        """Create a new user with hashed password."""
        user_id = f"{username}-{len(self._users) + 1:03d}"
        self._users[username] = {
            "user_id": user_id,
            "username": username,
            "password_hash": self._hash_password(password),
            "role": role,
            "email": email
        }
        return user_id

    def get_user(self, username: str) -> Optional[User]:
        """Get user by username."""
        user_data = self._users.get(username)
        if not user_data:
            return None

        return User(
            user_id=user_data["user_id"],
            username=username,
            role=user_data["role"],
            email=user_data.get("email")
        )


# Global auth manager
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get or create the auth manager."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[User]:
    """Get current user from JWT token.

    Production behavior:
    - Always requires valid JWT token
    - No demo/fallback user mode
    - AUTH_DISABLED=true still validates token format for audit trail
    """
    auth = get_auth_manager()

    # Auth disabled mode - still require valid token if users are configured
    if auth.auth_disabled and auth._users:
        if not credentials:
            # Still require token for audit trail even if auth_disabled
            raise HTTPException(status_code=401, detail="Authentication required")
    elif not auth.auth_disabled:
        # Normal auth mode - always require credentials
        if not credentials:
            raise HTTPException(status_code=401, detail="Authentication required")

    # If no users configured and auth disabled, fail gracefully
    if auth.auth_disabled and not auth._users:
        raise HTTPException(
            status_code=503,
            detail="System not configured. Please set ADMIN_USER and USER_USER environment variables."
        )

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    token_data = auth.verify_token(credentials.credential)
    user = auth.get_user(token_data.username)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """Dependency to require specific roles."""
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}"
            )
        return user
    return role_checker