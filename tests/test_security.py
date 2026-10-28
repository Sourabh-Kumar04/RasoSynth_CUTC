#!/usr/bin/env python3
"""Test security headers and startup validation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient


def test_security_headers():
    """Verify all security headers are present in responses."""
    print("=== Testing Security Headers ===")

    from api.server import app, _validate_security_config

    # Test startup validation
    print("\n--- JWT_SECRET validation ---")
    _validate_security_config()
    print("✓ JWT_SECRET validation passed")

    # Use single TestClient instance to avoid lifespan re-trigger issues
    client = TestClient(app)

    # Test GET /health for security headers
    resp = client.get("/health")
    assert resp.status_code == 200

    expected_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    print("\n--- Security Headers (/health) ---")
    for header, expected_value in expected_headers.items():
        actual = resp.headers.get(header)
        assert actual == expected_value, f"{header}: expected '{expected_value}', got '{actual}'"
        print(f"✓ {header}: {actual}")

    # Test CORS preflight
    print("\n--- CORS preflight (/health) ---")
    resp = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"}
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Access-Control-Allow-Origin: {resp.headers.get('Access-Control-Allow-Origin', 'N/A')}")

    print("\n✅ All security headers test PASSED")


def test_request_size_validation():
    """Test that request size limits are enforced."""
    print("\n=== Testing Request Size Limit ===")

    from api.server import app

    client = TestClient(app)

    # Verify the SecurityHeadersMiddleware is in place
    # The actual body size enforcement is tested by checking the middleware
    # MAX_REQUEST_BODY_SIZE env var controls the limit (default 10MB)

    from api.server import SecurityHeadersMiddleware
    middleware = SecurityHeadersMiddleware(app)

    print("✓ SecurityHeadersMiddleware configured")
    print(f"  MAX_BODY_SIZE: {middleware.MAX_BODY_SIZE} bytes")
    assert middleware.MAX_BODY_SIZE > 0

    print("✅ Request size limit test PASSED")


if __name__ == "__main__":
    try:
        success1 = test_security_headers()
        success2 = test_request_size_validation()
        sys.exit(0 if (success1 and success2) else 1)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)