"""Request size and resource limit validators."""
import os
from typing import Any, Dict, Optional
from pydantic import Field, field_validator


class RequestLimits:
    """Environment-aware request size limits."""

    # Default limits (can be overridden by environment)
    DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
    DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    DEFAULT_MAX_ITEMS = 10_000
    DEFAULT_MAX_DEPTH = 20

    @classmethod
    def get_max_body_size(cls) -> int:
        """Get max request body size from environment or default."""
        return int(os.getenv("MAX_REQUEST_BODY_SIZE", cls.DEFAULT_MAX_BODY_SIZE))

    @classmethod
    def get_max_file_size(cls) -> int:
        """Get max file upload size from environment or default."""
        return int(os.getenv("MAX_FILE_SIZE", cls.DEFAULT_MAX_FILE_SIZE))

    @classmethod
    def get_max_items(cls) -> int:
        """Get max items in a list from environment or default."""
        return int(os.getenv("MAX_ITEMS", cls.DEFAULT_MAX_ITEMS))

    @classmethod
    def get_max_depth(cls) -> int:
        """Get max nesting depth from environment or default."""
        return int(os.getenv("MAX_DEPTH", cls.DEFAULT_MAX_DEPTH))


class ResourceValidator:
    """Validator for resource constraints."""

    @staticmethod
    def validate_memory_size(size_mb: float) -> float:
        """Validate memory size is within limits."""
        max_memory = int(os.getenv("MAX_MEMORY_MB", "4096"))
        if size_mb > max_memory:
            raise ValueError(f"Memory size {size_mb}MB exceeds limit {max_memory}MB")
        return size_mb

    @staticmethod
    def validate_timeout(seconds: float) -> float:
        """Validate timeout is within limits."""
        max_timeout = int(os.getenv("MAX_TIMEOUT_SECONDS", "300"))
        if seconds > max_timeout:
            raise ValueError(f"Timeout {seconds}s exceeds limit {max_timeout}s")
        if seconds < 1:
            raise ValueError("Timeout must be at least 1 second")
        return seconds

    @staticmethod
    def validate_concurrency(count: int) -> int:
        """Validate concurrency is within limits."""
        max_concurrent = int(os.getenv("MAX_CONCURRENT_OPERATIONS", "100"))
        if count > max_concurrent:
            raise ValueError(f"Concurrency {count} exceeds limit {max_concurrent}")
        if count < 1:
            raise ValueError("Concurrency must be at least 1")
        return count


def validate_list_size(items: list, max_size: Optional[int] = None) -> list:
    """Validate list size is within limits."""
    max_size = max_size or RequestLimits.get_max_items()
    if len(items) > max_size:
        raise ValueError(f"List size {len(items)} exceeds maximum {max_size}")
    return items


def validate_dict_depth(data: Dict, current_depth: int = 0) -> Dict:
    """Recursively validate dict nesting depth."""
    max_depth = RequestLimits.get_max_depth()
    if current_depth > max_depth:
        raise ValueError(f"Dict nesting depth {current_depth} exceeds maximum {max_depth}")

    for value in data.values():
        if isinstance(value, dict):
            validate_dict_depth(value, current_depth + 1)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    validate_dict_depth(item, current_depth + 1)

    return data