"""
Security Schemas

Schemas for RBAC, tenant isolation, rate limiting,
and security policy enforcement.
"""

from typing import Dict, List, Optional, Any, Set, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from api.schemas.base import BaseSchema


class RBACPermission(str, Enum):
    """RBAC permission types."""
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    DATASET_DELETE = "dataset:delete"
    DATASET_EXPORT = "dataset:export"

    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_DELETE = "workflow:delete"

    JOB_READ = "job:read"
    JOB_WRITE = "job:write"
    JOB_CANCEL = "job:cancel"

    PROVIDER_READ = "provider:read"
    PROVIDER_WRITE = "provider:write"

    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_ADMIN = "user:admin"

    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    TENANT_ADMIN = "tenant:admin"

    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_ADMIN = "system:admin"

    COST_VIEW = "cost:view"
    COST_MANAGE = "cost:manage"


class RoleType(str, Enum):
    """User role types."""
    ADMIN = "admin"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    GUEST = "guest"


class UserContext(BaseSchema):
    """User authentication context."""
    user_id: str
    username: str

    email: Optional[str] = None

    roles: List[RoleType] = Field(default_factory=lambda: [RoleType.VIEWER])

    permissions: Set[RBACPermission] = Field(default_factory=set)
    inherited_permissions: Set[RBACPermission] = Field(default_factory=set)

    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None

    mfa_enabled: bool = False
    authenticated_at: Optional[datetime] = None

    def has_permission(self, permission: RBACPermission) -> bool:
        """Check if user has permission."""
        return permission in self.permissions or permission in self.inherited_permissions

    def has_any_permission(self, permissions: List[RBACPermission]) -> bool:
        """Check if user has any of the permissions."""
        return any(p in self.permissions or p in self.inherited_permissions for p in permissions)

    def has_all_permissions(self, permissions: List[RBACPermission]) -> bool:
        """Check if user has all permissions."""
        return all(p in self.permissions or p in self.inherited_permissions for p in permissions)


class TenantContext(BaseSchema):
    """Multi-tenant context."""
    tenant_id: str
    tenant_name: str

    plan: Literal["free", "starter", "professional", "enterprise"] = "free"

    quotas: Dict[str, int] = Field(default_factory=dict)
    usage: Dict[str, int] = Field(default_factory=dict)

    features_enabled: Set[str] = Field(default_factory=set)
    features_disabled: Set[str] = Field(default_factory=set)

    region: str = "us-east-1"
    data_residency: Optional[str] = None

    compliance: List[str] = Field(default_factory=lambda: ["GDPR"])

    security_policy_id: Optional[str] = None
    rate_limit_policy_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_quota(self, resource: str) -> Optional[int]:
        """Get quota for resource."""
        return self.quotas.get(resource)

    def get_usage(self, resource: str) -> int:
        """Get current usage for resource."""
        return self.usage.get(resource, 0)

    def check_quota(self, resource: str, amount: int = 1) -> bool:
        """Check if quota allows the requested amount."""
        quota = self.get_quota(resource)
        if quota is None:
            return True
        return self.get_usage(resource) + amount <= quota


class RateLimitConfig(BaseSchema):
    """Rate limiting configuration."""
    enabled: bool = True

    requests_per_minute: int = 60
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None

    tokens_per_minute: Optional[int] = None

    burst_size: int = 10

    per_provider_limits: Dict[str, int] = Field(default_factory=dict)

    def check_rate_limit(
        self,
        request_count: int,
        window_start: datetime,
        window_type: Literal["minute", "hour", "day"] = "minute"
    ) -> tuple[bool, Optional[int]]:
        """Check rate limit, returns (allowed, remaining)."""
        limit = getattr(self, f"requests_per_{window_type}s") or self.requests_per_minute

        if request_count >= limit:
            return False, 0

        return True, limit - request_count


class SecurityPolicy(BaseSchema):
    """Security policy for tenant/request."""
    policy_id: str
    name: str

    allowed_ips: List[str] = Field(default_factory=list)
    blocked_ips: List[str] = Field(default_factory=list)

    allowed_providers: List[str] = Field(default_factory=lambda: [
        "google", "anthropic", "openai", "nvidia", "ollama"
    ])
    blocked_providers: List[str] = Field(default_factory=list)

    allowed_regions: List[str] = Field(default_factory=list)
    blocked_regions: List[str] = Field(default_factory=list)

    require_encryption: bool = True
    require_audit_log: bool = True

    max_request_size_mb: int = 100
    max_response_size_mb: int = 500

    sensitive_fields: List[str] = Field(default_factory=lambda: [
        "password", "secret", "api_key", "token", "credential"
    ])

    data_retention_days: int = 90

    compliance_requirements: List[str] = Field(default_factory=lambda: ["GDPR"])

    def is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed."""
        if ip in self.blocked_ips:
            return False
        if not self.allowed_ips:
            return True
        return ip in self.allowed_ips

    def is_provider_allowed(self, provider: str) -> bool:
        """Check if provider is allowed."""
        if provider in self.blocked_providers:
            return False
        if not self.allowed_providers:
            return True
        return provider in self.allowed_providers

    def is_region_allowed(self, region: str) -> bool:
        """Check if region is allowed."""
        if region in self.blocked_regions:
            return False
        if not self.allowed_regions:
            return True
        return region in self.allowed_regions


class AuditLogEntry(BaseSchema):
    """Audit log entry."""
    entry_id: str

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    user_id: Optional[str] = None
    tenant_id: Optional[str] = None

    action: str
    resource_type: str
    resource_id: Optional[str] = None

    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    changes: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    success: bool = True
    error_message: Optional[str] = None


class APIKey(BaseSchema):
    """API key for authentication."""
    key_id: str
    name: str

    user_id: str
    tenant_id: Optional[str] = None

    key_hash: str
    key_prefix: str

    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None

    expires_at: Optional[datetime] = None
    is_active: bool = True

    permissions: Set[RBACPermission] = Field(default_factory=set)

    rate_limit_requests_per_minute: int = 60

    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluation(BaseSchema):
    """Policy evaluation result."""
    request_id: str

    allowed: bool = True

    evaluated_policies: List[str] = Field(default_factory=list)

    matched_rules: List[str] = Field(default_factory=list)
    violated_rules: List[str] = Field(default_factory=list)

    reason: Optional[str] = None

    risk_level: Literal["low", "medium", "high", "critical"] = "low"

    recommended_actions: List[str] = Field(default_factory=list)