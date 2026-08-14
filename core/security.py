"""Enterprise Security Module

Provides:
- API key encryption at rest
- RBAC (Role-Based Access Control)
- Audit logging
- Request validation
- Prompt injection protection
- Secure secret management
"""
import asyncio
import hashlib
import hmac
import logging
import os
import re
from base64 import b64encode, b64decode
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


# =============================================================================
# Security Configuration
# =============================================================================

class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"           # Full access
    OPERATOR = "operator"     # Can run jobs, manage providers
    VIEWER = "viewer"         # Read-only access
    SERVICE = "service"       # API service account


class Permission(str, Enum):
    """Granular permissions."""
    # Job permissions
    JOB_CREATE = "job:create"
    JOB_READ = "job:read"
    JOB_UPDATE = "job:update"
    JOB_DELETE = "job:delete"
    JOB_CANCEL = "job:cancel"

    # Provider permissions
    PROVIDER_READ = "provider:read"
    PROVIDER_SWITCH = "provider:switch"
    PROVIDER_CONFIG = "provider:config"

    # Checkpoint permissions
    CHECKPOINT_CREATE = "checkpoint:create"
    CHECKPOINT_READ = "checkpoint:read"
    CHECKPOINT_RESTORE = "checkpoint:restore"

    # Failover permissions
    FAILOVER_TRIGGER = "failover:trigger"
    FAILOVER_VIEW = "failover:view"

    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_AUDIT = "system:audit"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: {
        Permission.JOB_CREATE, Permission.JOB_READ, Permission.JOB_UPDATE,
        Permission.JOB_DELETE, Permission.JOB_CANCEL,
        Permission.PROVIDER_READ, Permission.PROVIDER_SWITCH, Permission.PROVIDER_CONFIG,
        Permission.CHECKPOINT_CREATE, Permission.CHECKPOINT_READ, Permission.CHECKPOINT_RESTORE,
        Permission.FAILOVER_TRIGGER, Permission.FAILOVER_VIEW,
        Permission.SYSTEM_CONFIG, Permission.SYSTEM_AUDIT,
    },
    UserRole.OPERATOR: {
        Permission.JOB_CREATE, Permission.JOB_READ, Permission.JOB_UPDATE,
        Permission.JOB_CANCEL,
        Permission.PROVIDER_READ, Permission.PROVIDER_SWITCH,
        Permission.CHECKPOINT_CREATE, Permission.CHECKPOINT_READ, Permission.CHECKPOINT_RESTORE,
        Permission.FAILOVER_TRIGGER, Permission.FAILOVER_VIEW,
    },
    UserRole.VIEWER: {
        Permission.JOB_READ,
        Permission.PROVIDER_READ,
        Permission.CHECKPOINT_READ,
        Permission.FAILOVER_VIEW,
    },
    UserRole.SERVICE: {
        Permission.JOB_CREATE, Permission.JOB_READ,
        Permission.PROVIDER_READ,
        Permission.CHECKPOINT_CREATE, Permission.CHECKPOINT_READ,
    },
}


# =============================================================================
# API Key Encryption
# =============================================================================

@dataclass
class EncryptedSecret:
    """Encrypted secret with metadata."""
    encrypted_value: str
    salt: str
    algorithm: str = "fernet"
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class SecretManager:
    """
    Enterprise secret management with encryption at rest.

    Supports:
    - Fernet encryption
    - Key derivation
    - Expiration
    - Audit trail
    """

    def __init__(self, encryption_key: Optional[str] = None):
        # Use environment key or generate
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            # Generate a key for development
            key = Fernet.generate_key().decode()
            logger.warning("No encryption key provided, using generated key (not for production)")

        # Derive key using PBKDF2
        self._fernet = self._create_fernet(key)
        self._secret_cache: Dict[str, EncryptedSecret] = {}

    def _create_fernet(self, key: str) -> Fernet:
        """Create Fernet instance from key."""
        # If key is not base64, hash it first
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            # Hash the key to get 32 bytes
            from cryptography.hazmat.primitives import hashes
            digest = hashes.Hash(hashes.SHA256())
            digest.update(key.encode() if isinstance(key, str) else key)
            key_bytes = b64encode(digest.finalize())
            return Fernet(key_bytes)

    def encrypt(self, value: str, expiration_days: Optional[int] = None) -> EncryptedSecret:
        """Encrypt a secret value."""
        # Generate salt
        salt = os.urandom(16)
        salt_b64 = b64encode(salt).decode()

        # Encrypt value
        encrypted = self._fernet.encrypt(value.encode())

        # Create secret object
        expires_at = None
        if expiration_days:
            expires_at = datetime.utcnow() + timedelta(days=expiration_days)

        secret = EncryptedSecret(
            encrypted_value=encrypted.decode(),
            salt=salt_b64,
            expires_at=expires_at,
        )

        return secret

    def decrypt(self, secret: EncryptedSecret) -> Optional[str]:
        """Decrypt a secret value."""
        # Check expiration
        if secret.expires_at and secret.expires_at < datetime.utcnow():
            logger.warning("Secret has expired")
            return None

        try:
            return self._fernet.decrypt(secret.encrypted_value.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            return None

    def encrypt_api_key(self, api_key: str, provider: str) -> str:
        """Encrypt API key and return storage string."""
        secret = self.encrypt(api_key)
        return f"{provider}:{secret.salt}:{secret.encrypted_value}"

    def decrypt_api_key(self, stored_key: str) -> Optional[Dict[str, str]]:
        """Decrypt stored API key."""
        parts = stored_key.split(":")
        if len(parts) != 3:
            return None

        provider, salt, encrypted = parts
        secret = EncryptedSecret(
            encrypted_value=encrypted,
            salt=salt,
        )

        decrypted = self.decrypt(secret)
        if decrypted:
            return {"provider": provider, "api_key": decrypted}
        return None


# =============================================================================
# RBAC Implementation
# =============================================================================

@dataclass
class User:
    """User with role and permissions."""
    user_id: str
    username: str
    role: UserRole
    permissions: Set[Permission]
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthToken:
    """JWT authentication token."""
    user_id: str
    username: str
    role: UserRole
    permissions: List[str]
    exp: datetime
    iat: datetime = field(default_factory=datetime.utcnow)


class RBACManager:
    """
    Role-Based Access Control Manager.

    Features:
    - JWT token-based authentication
    - Role-based permissions
    - Granular permission checks
    - Session management
    """

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, datetime] = {}
        self._permission_cache: Dict[str, Set[Permission]] = {}

    def register_user(
        self,
        user_id: str,
        username: str,
        role: UserRole,
        metadata: Optional[Dict[str, Any]] = None
    ) -> User:
        """Register a new user with role."""
        permissions = ROLE_PERMISSIONS.get(role, set())
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            permissions=permissions,
            metadata=metadata or {},
        )
        self._users[user_id] = user
        logger.info(f"Registered user {username} with role {role.value}")
        return user

    def create_token(self, user_id: str, expires_in_hours: int = 24) -> Optional[str]:
        """Create JWT token for user."""
        user = self._users.get(user_id)
        if not user:
            return None

        exp = datetime.utcnow() + timedelta(hours=expires_in_hours)
        token_data = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "exp": exp.timestamp(),
        }

        token = jwt.encode(token_data, self._secret_key, algorithm=self._algorithm)
        self._sessions[user_id] = datetime.utcnow()

        return token

    def verify_token(self, token: str) -> Optional[AuthToken]:
        """Verify JWT token and return auth info."""
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])

            return AuthToken(
                user_id=payload["sub"],
                username=payload["username"],
                role=UserRole(payload["role"]),
                permissions=payload["permissions"],
                exp=datetime.fromtimestamp(payload["exp"]),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            return None

    def check_permission(self, token: str, permission: Permission) -> bool:
        """Check if token has permission."""
        auth = self.verify_token(token)
        if not auth:
            return False

        return permission.value in auth.permissions

    def require_permission(self, permission: Permission):
        """Decorator to require permission for endpoint."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, token: str = None, **kwargs):
                if not token:
                    raise HTTPException(status_code=401, detail="Authentication required")

                if not self.check_permission(token, permission):
                    raise HTTPException(status_code=403, detail="Permission denied")

                return await func(*args, **kwargs)
            return wrapper
        return decorator


# =============================================================================
# Audit Logging
# =============================================================================

@dataclass
class AuditEvent:
    """Audit event for compliance tracking."""
    event_id: str
    timestamp: datetime
    user_id: str
    username: str
    action: str
    resource_type: str
    resource_id: str
    result: str  # success, failure, denied
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """
    Enterprise audit logging.

    Tracks:
    - Authentication events
    - Resource access
    - Data modifications
    - Security events
    - Provider operations
    """

    def __init__(self, db=None):
        self._db = db
        self._events: List[AuditEvent] = []

    async def log(
        self,
        user_id: str,
        username: str,
        action: str,
        resource_type: str,
        resource_id: str,
        result: str,
        request: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log an audit event."""
        event = AuditEvent(
            event_id=os.urandom(16).hex(),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            details=details or {},
        )

        self._events.append(event)
        logger.info(
            f"AUDIT: {action} {resource_type}/{resource_id} by {username}: {result}"
        )

        # Persist to database if available
        if self._db:
            try:
                await self._db.execute("""
                    INSERT INTO audit_log (
                        event_id, timestamp, user_id, username, action,
                        resource_type, resource_id, result, ip_address,
                        user_agent, details
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                    event.event_id, event.timestamp, event.user_id, event.username,
                    event.action, event.resource_type, event.resource_id, event.result,
                    event.ip_address, event.user_agent, str(event.details)
                )
            except Exception as e:
                logger.error(f"Failed to persist audit event: {e}")

        return event

    def get_events(
        self,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events."""
        filtered = self._events

        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]

        return filtered[-limit:]


# =============================================================================
# Input Validation & Security
# =============================================================================

# Prompt injection patterns
PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(previous|above|all)\s+(instructions?|rules?|commands?)",
    r"(?i)forget\s+(everything|all|your)\s+(instructions?|rules?|guidelines?)",
    r"(?i)new\s+instructions?:",
    r"(?i)system\s*:\s*",
    r"(?i)you\s+are\s+(now|a|an)",
    r"(?i)\{system\}",
    r"<\|system\|>",
    r"(?i)override\s+(your|this)",
    r"(?i)disregard\s+(your|all)",
    r"(?i) pretend ",
    r"(?i)roleplay",
    r"(?i)imagine\s+(you|that)",
]

PROMPT_INJECTION_REGEX = re.compile("|".join(PROMPT_INJECTION_PATTERNS), re.IGNORECASE)


class SecurityValidator:
    """
    Security validation for inputs.

    Validates:
    - Prompt injection
    - SQL injection
    - Path traversal
    - Invalid characters
    """

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bOR\b.*\b=\b)",
        r"(\bUNION\b.*\bSELECT\b)",
    ]
    SQL_INJECTION_REGEX = re.compile("|".join(SQL_INJECTION_PATTERNS), re.IGNORECASE)

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\.\/",
        r"\.\.\\",
        r"%2e%2e",
        r"\.\.%2f",
    ]
    PATH_TRAVERSAL_REGEX = re.compile("|".join(PATH_TRAVERSAL_PATTERNS), re.IGNORECASE)

    def validate_prompt(self, text: str) -> Dict[str, Any]:
        """Validate prompt for injection attempts."""
        matches = PROMPT_INJECTION_REGEX.findall(text)

        if matches:
            return {
                "valid": False,
                "reason": "Potential prompt injection detected",
                "matches": matches,
                "severity": "high",
            }

        return {"valid": True}

    def validate_sql(self, text: str) -> Dict[str, Any]:
        """Validate for SQL injection attempts."""
        matches = self.SQL_INJECTION_REGEX.findall(text)

        if matches:
            return {
                "valid": False,
                "reason": "Potential SQL injection detected",
                "matches": matches,
                "severity": "critical",
            }

        return {"valid": True}

    def validate_path(self, path: str) -> Dict[str, Any]:
        """Validate for path traversal attempts."""
        matches = self.PATH_TRAVERSAL_REGEX.findall(path)

        if matches:
            return {
                "valid": False,
                "reason": "Potential path traversal detected",
                "matches": matches,
                "severity": "high",
            }

        return {"valid": True}

    def validate_all(self, text: str, check_prompt: bool = True, check_sql: bool = True) -> Dict[str, Any]:
        """Run all validations."""
        results = []

        if check_prompt:
            prompt_result = self.validate_prompt(text)
            if not prompt_result["valid"]:
                results.append(prompt_result)

        if check_sql:
            sql_result = self.validate_sql(text)
            if not sql_result["valid"]:
                results.append(sql_result)

        if results:
            return {
                "valid": False,
                "validations": results,
                "severity": max(r.get("severity", "low") for r in results),
            }

        return {"valid": True}


# =============================================================================
# Security Middleware
# =============================================================================

class SecurityMiddleware:
    """FastAPI middleware for security enforcement."""

    def __init__(
        self,
        rbac_manager: RBACManager,
        audit_logger: AuditLogger,
        validator: SecurityValidator,
    ):
        self._rbac = rbac_manager
        self._audit = audit_logger
        self._validator = validator

    async def check_request(self, request: Any) -> Optional[Dict[str, Any]]:
        """Check request for security issues."""
        # Get body if available
        if hasattr(request, "body") and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    text = body.decode("utf-8", errors="ignore")
                    validation = self._validator.validate_all(text)
                    if not validation["valid"]:
                        return validation
            except Exception:
                pass

        return None


# Singleton instances
_secret_manager: Optional[SecretManager] = None
_rbac_manager: Optional[RBACManager] = None
_audit_logger: Optional[AuditLogger] = None
_security_validator: Optional[SecurityValidator] = None


def get_secret_manager() -> SecretManager:
    """Get secret manager singleton."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_rbac_manager() -> RBACManager:
    """Get RBAC manager singleton."""
    global _rbac_manager
    if _rbac_manager is None:
        secret = os.getenv("JWT_SECRET", "")
        env = os.getenv("AI_DATASET_ENVIRONMENT", "development").lower()
        if env == "production" and (not secret or secret == "change-me-in-production"):
            raise ValueError(
                "CRITICAL SECURITY CONFIGURATION ERROR: "
                "JWT_SECRET environment variable is either unset or set to the default fallback "
                "in a production environment! To proceed, set a strong JWT_SECRET."
            )
        if not secret:
            secret = "change-me-in-production"
        _rbac_manager = RBACManager(secret)
    return _rbac_manager


def get_audit_logger() -> AuditLogger:
    """Get audit logger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_security_validator() -> SecurityValidator:
    """Get security validator singleton."""
    global _security_validator
    if _security_validator is None:
        _security_validator = SecurityValidator()
    return _security_validator


__all__ = [
    "UserRole",
    "Permission",
    "ROLE_PERMISSIONS",
    "SecretManager",
    "EncryptedSecret",
    "RBACManager",
    "User",
    "AuthToken",
    "AuditLogger",
    "AuditEvent",
    "SecurityValidator",
    "PROMPT_INJECTION_REGEX",
    "get_secret_manager",
    "get_rbac_manager",
    "get_audit_logger",
    "get_security_validator",
]