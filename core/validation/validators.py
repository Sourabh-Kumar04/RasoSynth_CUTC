"""Enterprise-grade validation framework for API inputs."""
import re
import os
from typing import Any, Callable, Optional, List, Type, Union, Set
from datetime import datetime
from enum import Enum
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ValidationInfo,
    PydanticInvalidForJsonSchema,
)
from pydantic.types import constr
from pydantic.functional_validators import AfterValidator
import html


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class SecurityError(Exception):
    """Raised when security validation fails."""
    pass


# === Security Validation ===

# Dangerous patterns for prompt injection
PROMPT_INJECTION_PATTERNS = [
    r"(?i)(ignore\s+(?:previous|above|prior|all)\s+(?:instructions?|rules?|constraints?))",
    r"(?i)(disregard\s+(?:previous|above|prior|all)\s+(?:instructions?|rules?))",
    r"(?i)(forget\s+(?:everything|all|your)\s+(?:instructions?|rules?|guidelines?))",
    r"(?i)(system\s*:\s*ignore)",
    r"(?i)(you\s+(?:are|become)\s+(?:now|just)\s+a)",
    r"(?i)(new\s+instruction)",
    r"(?i)(override\s+(?:previous|your|system))",
    r"(?i)(#\s*ignore\s+#)",
    r"(?i)(\{\{.*\}\})",  # Template injection
    r"(?i)(\[\[.*\]\])",  # Instruction chaining
    r"<script[^>]*>.*?</script>",  # XSS
    r"javascript:",  # JS protocol
    r"on\w+\s*=",  # Event handlers
]

# SQL injection patterns
SQL_INJECTION_PATTERNS = [
    r"(?i)(\bunion\b.*\bselect\b)",
    r"(?i)(\bselect\b.*\bfrom\b)",
    r"(?i)(\bdrop\b\s+\btable\b)",
    r"(?i)(\binsert\b.*\binto\b)",
    r"(?i)(\bupdate\b.*\bset\b)",
    r"(?i)(\bdelete\b.*\bfrom\b)",
    r"(?i)(\bexec\b\s*\()",
    r"(?i)(\bexecute\b\s*\()",
    r"(?i)(\bxp_\w+)",
    r"(--|\#|\/\*|\*\/)",  # SQL comments
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"\.\.\/",  # ../ or ..\
    r"\.\.\\",
    r"\/etc\/passwd",
    r"c:\\windows",
    r"%2e%2e",  # URL encoded
    r"%252e%252e",
]


def validate_no_injection(text: str) -> str:
    """Validate text doesn't contain injection attempts."""
    if not text:
        return text

    text_lower = text.lower()

    # Check prompt injection
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text):
            raise SecurityError(f"Potential prompt injection detected: {pattern}")

    # Check SQL injection
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text):
            raise SecurityError(f"Potential SQL injection detected")

    return text


def validate_no_path_traversal(path: str) -> str:
    """Validate path doesn't contain traversal attempts."""
    if not path:
        return path

    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, path, re.IGNORECASE):
            raise SecurityError(f"Potential path traversal detected")

    return path


def sanitize_html(text: str) -> str:
    """Sanitize HTML content."""
    return html.escape(text)


# === Domain Validators ===

def validate_domain(domain: str) -> str:
    """Validate domain name format."""
    if not domain:
        raise ValidationError("Domain cannot be empty")

    # Remove protocol if present
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.rstrip("/")

    # Basic domain regex
    if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$", domain):
        raise ValidationError(f"Invalid domain format: {domain}")

    return domain


def validate_filename(filename: str) -> str:
    """Validate filename for safety."""
    if not filename:
        raise ValidationError("Filename cannot be empty")

    # Check for path traversal
    validate_no_path_traversal(filename)

    # Check for dangerous extensions
    dangerous_exts = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js", ".jar"}
    ext = os.path.splitext(filename)[1].lower()
    if ext in dangerous_exts:
        raise SecurityError(f"Dangerous file extension: {ext}")

    # Only allow alphanumeric, dash, underscore, dot
    if not re.match(r"^[a-zA-Z0-9._-]+$", filename):
        raise ValidationError("Filename contains invalid characters")

    return filename


def validate_language_code(code: str) -> str:
    """Validate ISO 639-1 language code."""
    valid_codes = {
        "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
        "ar", "hi", "nl", "pl", "sv", "da", "no", "fi", "el", "he",
    }
    if code.lower() not in valid_codes:
        raise ValidationError(f"Unsupported language code: {code}")
    return code.lower()


def validate_url(url: str) -> str:
    """Validate URL format."""
    if not url:
        raise ValidationError("URL cannot be empty")

    # Basic URL regex
    url_pattern = r"^https?://[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?(/.*)?$"
    if not re.match(url_pattern, url):
        raise ValidationError(f"Invalid URL format: {url}")

    return url


def validate_json_string(json_str: str) -> str:
    """Validate string is valid JSON."""
    import json
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")
    return json_str


# === Constraint Validators ===

class ConstraintValidator:
    """Validator for dataset generation constraints."""

    MAX_DATASET_SIZE = 1_000_000
    MAX_BUDGET_USD = 10_000.0
    MAX_TOKENS_PER_REQUEST = 1_000_000

    @classmethod
    def validate_dataset_size(cls, size: int) -> int:
        """Validate dataset size is within limits."""
        if size < 1:
            raise ValidationError("Dataset size must be at least 1")
        if size > cls.MAX_DATASET_SIZE:
            raise ValidationError(
                f"Dataset size {size} exceeds maximum allowed {cls.MAX_DATASET_SIZE}"
            )
        return size

    @classmethod
    def validate_budget(cls, budget: float) -> float:
        """Validate budget is within limits."""
        if budget < 0:
            raise ValidationError("Budget cannot be negative")
        if budget > cls.MAX_BUDGET_USD:
            raise ValidationError(
                f"Budget {budget} exceeds maximum allowed {cls.MAX_BUDGET_USD}"
            )
        return budget

    @classmethod
    def validate_concurrent_jobs(cls, count: int) -> int:
        """Validate concurrent job count."""
        max_concurrent = int(os.getenv("MAX_CONCURRENT_JOBS", "100"))
        if count > max_concurrent:
            raise ValidationError(
                f"Concurrent jobs {count} exceeds limit {max_concurrent}"
            )
        return count


# === Pydantic Validators ===

class StrictString(str):
    """String with strict validation."""

    def __new__(cls, value: Any):
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}")
        validate_no_injection(value)
        return super().__new__(cls, value)

    @classmethod
    def __get_validators__(cls) -> List[Callable]:
        return [cls.validate]

    @classmethod
    def validate(cls, value: Any, info: ValidationInfo = None) -> str:
        return cls(value)


class SafeFilename(str):
    """Filename with strict validation."""

    def __new__(cls, value: Any):
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}")
        validate_filename(value)
        return super().__new__(cls, value)

    @classmethod
    def __get_validators__(cls) -> List[Callable]:
        return [cls.validate]

    @classmethod
    def validate(cls, value: Any, info: ValidationInfo = None) -> str:
        return cls(value)


class DomainName(str):
    """Domain name with validation."""

    def __new__(cls, value: Any):
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}")
        validate_domain(value)
        return super().__new__(cls, value)

    @classmethod
    def __get_validators__(cls) -> List[Callable]:
        return [cls.validate]

    @classmethod
    def validate(cls, value: Any, info: ValidationInfo = None) -> str:
        return cls(value)


class LanguageCode(str):
    """ISO language code with validation."""

    def __new__(cls, value: Any):
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}")
        validate_language_code(value)
        return super().__new__(cls, value)

    @classmethod
    def __get_validators__(cls) -> List[Callable]:
        return [cls.validate]

    @classmethod
    def validate(cls, value: Any, info: ValidationInfo = None) -> str:
        return cls(value)


class ValidURL(str):
    """URL with validation."""

    def __new__(cls, value: Any):
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}")
        validate_url(value)
        return super().__new__(cls, value)

    @classmethod
    def __get_validators__(cls) -> List[Callable]:
        return [cls.validate]

    @classmethod
    def validate(cls, value: Any, info: ValidationInfo = None) -> str:
        return cls(value)


# === Re-export for convenience ===

__all__ = [
    "ValidationError",
    "SecurityError",
    "validate_no_injection",
    "validate_no_path_traversal",
    "sanitize_html",
    "validate_domain",
    "validate_filename",
    "validate_language_code",
    "validate_url",
    "validate_json_string",
    "ConstraintValidator",
    "StrictString",
    "SafeFilename",
    "DomainName",
    "LanguageCode",
    "ValidURL",
]