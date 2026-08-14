"""
Dataset Security & Access Control

Signed URLs, encryption, access tokens, and audit logging.
"""

import hashlib
import hmac
import base64
import json
import time
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum


class AccessLevel(Enum):
    """Access level for datasets."""
    PRIVATE = "private"
    ORGANIZATION = "organization"
    PUBLIC = "public"


@dataclass
class AccessToken:
    """Access token for dataset download."""
    token_id: str = ""
    dataset_id: str = ""
    access_level: AccessLevel = AccessLevel.PRIVATE
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow())
    usage_limit: Optional[int] = None
    usage_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class AccessLog:
    """Access log entry."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    token_id: str = ""
    dataset_id: str = ""
    action: str = ""  # download, view, share
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True


class SignedURLGenerator:
    """Generate signed URLs for secure temporary access."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        default_expiration_hours: int = 24
    ):
        self.secret_key = secret_key or "default-secret-key"
        self.default_expiration = default_expiration_hours

    def generate(
        self,
        resource: str,
        expiration_seconds: Optional[int] = None,
        custom_claims: Optional[dict] = None
    ) -> str:
        """Generate a signed URL."""
        expiration = expiration_seconds or (self.default_expiration * 3600)
        expires_at = int(time.time()) + expiration

        # Create payload
        payload = {
            "resource": resource,
            "expires": expires_at,
            "claims": custom_claims or {}
        }

        # Sign payload
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode()

        signature = self._sign(payload_b64)

        return f"{resource}?token={payload_b64}&sig={signature}"

    def verify(self, signed_url: str) -> Optional[dict]:
        """Verify a signed URL and return claims."""
        try:
            # Parse URL
            parts = signed_url.split("?token=")
            if len(parts) != 2:
                return None

            resource = parts[0]
            query = parts[1]
            token_part, sig_part = query.split("&sig=")

            # Verify signature
            if not self._verify(token_part, sig_part):
                return None

            # Decode payload
            payload = json.loads(
                base64.urlsafe_b64decode(token_part).decode()
            )

            # Check expiration
            if payload["expires"] < int(time.time()):
                return None

            return payload

        except Exception:
            return None

    def _sign(self, data: str) -> str:
        """Create HMAC signature."""
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def _verify(self, data: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self._sign(data)
        return hmac.compare_digest(expected, signature)


class EncryptionManager:
    """Handle dataset encryption."""

    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key or self._generate_key()

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data."""
        try:
            from cryptography.fernet import Fernet

            key = self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key
            fernet = Fernet(base64.urlsafe_b64encode(key[:32]))
            return fernet.encrypt(data)
        except ImportError:
            # Fallback: simple XOR (not secure, use only for testing)
            key_bytes = self.encryption_key.encode()[:32]
            return bytes(a ^ b for a, b in zip(data, (key_bytes * (len(data) // 32 + 1))[:len(data)]))

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data."""
        try:
            from cryptography.fernet import Fernet

            key = self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key
            fernet = Fernet(base64.urlsafe_b64encode(key[:32]))
            return fernet.decrypt(data)
        except ImportError:
            key_bytes = self.encryption_key.encode()[:32]
            return bytes(a ^ b for a, b in zip(data, (key_bytes * (len(data) // 32 + 1))[:len(data)]))

    def encrypt_file(self, input_path: str, output_path: str) -> None:
        """Encrypt a file."""
        with open(input_path, 'rb') as f:
            data = f.read()

        encrypted = self.encrypt(data)

        with open(output_path, 'wb') as f:
            f.write(encrypted)

    def decrypt_file(self, input_path: str, output_path: str) -> None:
        """Decrypt a file."""
        with open(input_path, 'rb') as f:
            data = f.read()

        decrypted = self.decrypt(data)

        with open(output_path, 'wb') as f:
            f.write(decrypted)

    def _generate_key(self) -> str:
        """Generate a new encryption key."""
        import secrets
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


class AccessController:
    """Control access to datasets."""

    def __init__(self):
        self._tokens: dict[str, AccessToken] = {}
        self._logs: list[AccessLog] = []
        self.signed_url_generator = SignedURLGenerator()

    def create_token(
        self,
        dataset_id: str,
        access_level: AccessLevel = AccessLevel.PRIVATE,
        expiration_hours: int = 24,
        usage_limit: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> AccessToken:
        """Create a new access token."""
        import uuid

        token_id = str(uuid.uuid4())
        token = AccessToken(
            token_id=token_id,
            dataset_id=dataset_id,
            access_level=access_level,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=expiration_hours),
            usage_limit=usage_limit,
            metadata=metadata or {}
        )

        self._tokens[token_id] = token
        return token

    def verify_token(self, token_id: str) -> bool:
        """Verify if token is valid."""
        token = self._tokens.get(token_id)
        if not token:
            return False

        # Check expiration
        if datetime.utcnow() > token.expires_at:
            return False

        # Check usage limit
        if token.usage_limit and token.usage_count >= token.usage_limit:
            return False

        return True

    def use_token(self, token_id: str) -> bool:
        """Record token usage."""
        token = self._tokens.get(token_id)
        if not token:
            return False

        if not self.verify_token(token_id):
            return False

        token.usage_count += 1
        return True

    def get_token(self, token_id: str) -> Optional[AccessToken]:
        """Get token details."""
        return self._tokens.get(token_id)

    def revoke_token(self, token_id: str) -> bool:
        """Revoke an access token."""
        if token_id in self._tokens:
            del self._tokens[token_id]
            return True
        return False

    def generate_download_url(
        self,
        dataset_id: str,
        expiration_hours: int = 24
    ) -> str:
        """Generate a temporary download URL."""
        resource = f"/datasets/{dataset_id}/download"
        return self.signed_url_generator.generate(resource, expiration_hours * 3600)

    def log_access(
        self,
        token_id: str,
        dataset_id: str,
        action: str,
        ip_address: Optional[str] = None,
        success: bool = True
    ) -> None:
        """Log dataset access."""
        log = AccessLog(
            timestamp=datetime.utcnow(),
            token_id=token_id,
            dataset_id=dataset_id,
            action=action,
            ip_address=ip_address,
            success=success
        )
        self._logs.append(log)

    def get_access_logs(
        self,
        dataset_id: Optional[str] = None,
        limit: int = 100
    ) -> list[AccessLog]:
        """Get access logs."""
        logs = self._logs
        if dataset_id:
            logs = [l for l in logs if l.dataset_id == dataset_id]
        return logs[-limit:]

    def get_access_summary(self, dataset_id: str) -> dict:
        """Get access summary for dataset."""
        logs = self.get_access_logs(dataset_id)
        downloads = [l for l in logs if l.action == "download"]

        return {
            "total_accesses": len(logs),
            "total_downloads": len(downloads),
            "unique_ips": len(set(l.ip_address for l in logs if l.ip_address)),
            "first_access": logs[0].timestamp if logs else None,
            "last_access": logs[-1].timestamp if logs else None,
        }


class SecureShareManager:
    """Manage secure sharing of datasets."""

    def __init__(self, access_controller: AccessController):
        self.access_controller = access_controller

    def create_share(
        self,
        dataset_id: str,
        recipient_email: Optional[str] = None,
        expiration_hours: int = 168,  # 7 days
        download_limit: Optional[int] = None,
        require_auth: bool = True
    ) -> dict:
        """Create a secure share link."""
        import uuid

        share_id = str(uuid.uuid4())

        token = self.access_controller.create_token(
            dataset_id=dataset_id,
            access_level=AccessLevel.ORGANIZATION if recipient_email else AccessLevel.PRIVATE,
            expiration_hours=expiration_hours,
            usage_limit=download_limit,
            metadata={
                "share_id": share_id,
                "recipient_email": recipient_email,
                "require_auth": require_auth
            }
        )

        download_url = self.access_controller.generate_download_url(
            dataset_id,
            expiration_hours
        )

        return {
            "share_id": share_id,
            "token_id": token.token_id,
            "download_url": download_url,
            "expires_at": token.expires_at.isoformat(),
            "download_limit": download_limit,
        }

    def get_share(self, share_id: str) -> Optional[dict]:
        """Get share details."""
        # Search tokens for share_id
        for token in self.access_controller._tokens.values():
            if token.metadata.get("share_id") == share_id:
                return {
                    "share_id": share_id,
                    "dataset_id": token.dataset_id,
                    "expires_at": token.expires_at.isoformat(),
                    "downloads_remaining": (
                        token.usage_limit - token.usage_count
                        if token.usage_limit else None
                    ),
                    "recipient": token.metadata.get("recipient_email"),
                }
        return None

    def revoke_share(self, share_id: str) -> bool:
        """Revoke a share."""
        for token in self.access_controller._tokens.values():
            if token.metadata.get("share_id") == share_id:
                return self.access_controller.revoke_token(token.token_id)
        return False