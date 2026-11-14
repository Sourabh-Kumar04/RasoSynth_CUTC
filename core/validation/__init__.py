"""Enterprise-grade validation framework."""
try:
    from core.validation.validators import (
        ValidationError,
        SecurityError,
        validate_no_injection,
        validate_no_path_traversal,
        sanitize_html,
        validate_domain,
        validate_filename,
        validate_language_code,
        validate_url,
        validate_json_string,
        ConstraintValidator,
        StrictString,
        SafeFilename,
        DomainName,
        LanguageCode,
        ValidURL,
    )
except ImportError:
    ValidationError = Exception  # type: ignore
    SecurityError = Exception     # type: ignore
    validate_no_injection = None  # type: ignore
    validate_no_path_traversal = None  # type: ignore
    sanitize_html = None          # type: ignore
    validate_domain = None        # type: ignore
    validate_filename = None      # type: ignore
    validate_language_code = None # type: ignore
    validate_url = None           # type: ignore
    validate_json_string = None   # type: ignore
    ConstraintValidator = None    # type: ignore
    StrictString = str            # type: ignore
    SafeFilename = str            # type: ignore
    DomainName = str              # type: ignore
    LanguageCode = str            # type: ignore
    ValidURL = str                # type: ignore
try:
    from core.validation.limits import (
        RequestLimits,
        ResourceValidator,
        validate_list_size,
        validate_dict_depth,
    )
except ImportError:
    RequestLimits = None       # type: ignore
    ResourceValidator = None   # type: ignore
    validate_list_size = None  # type: ignore
    validate_dict_depth = None # type: ignore

__all__ = [
    # Core validators
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
    # Custom types
    "StrictString",
    "SafeFilename",
    "DomainName",
    "LanguageCode",
    "ValidURL",
    # Resource limits
    "RequestLimits",
    "ResourceValidator",
    "validate_list_size",
    "validate_dict_depth",
]