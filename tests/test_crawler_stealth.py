"""
Tests for Stealth Web Crawler & Anti-Blocking Architecture.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch

from core.crawler.stealth import (
    AntiBotCategory,
    AntiBotDetector,
    AntiBotInspectionResult,
    StealthHeaderGenerator,
    AdaptiveDomainCircuitBreaker,
    CircuitState,
    ProxyRotator,
    PlaywrightStealthDriver,
)
from pipeline.extraction import ExtractionPipeline, ExtractedContent


def test_stealth_header_generator():
    """Verify that StealthHeaderGenerator produces coherent browser fingerprints."""
    headers = StealthHeaderGenerator.generate(referer="https://google.com")
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "Accept-Encoding" in headers
    assert "Sec-Fetch-Mode" in headers
    assert headers["Referer"] == "https://google.com"

    # Ensure User-Agent is modern desktop/mobile
    ua = headers["User-Agent"]
    assert any(browser in ua for browser in ("Chrome", "Safari", "Firefox"))

    # Test without referer
    headers_no_ref = StealthHeaderGenerator.generate()
    assert "User-Agent" in headers_no_ref
    assert headers_no_ref["Sec-Fetch-Dest"] == "document"


def test_antibot_detector_waf_challenges():
    """Verify detection of Cloudflare, DataDome, and CAPTCHA signatures."""
    # 1. Cloudflare Turnstile / Challenge
    cf_body = "<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing. Cloudflare challenge</body></html>"
    res = AntiBotDetector.inspect(200, {}, cf_body)
    assert res.detected is True
    assert res.category == AntiBotCategory.CLOUDFLARE
    assert res.should_escalate_to_browser is True

    # 2. Cloudflare mitigation header
    res_hdr = AntiBotDetector.inspect(403, {"cf-mitigated": "challenge"}, "")
    assert res_hdr.detected is True
    assert res_hdr.category == AntiBotCategory.CLOUDFLARE

    # 3. DataDome
    dd_body = "<html><body>geo.captcha-delivery.com block</body></html>"
    res_dd = AntiBotDetector.inspect(403, {"x-datadome": "protected"}, dd_body)
    assert res_dd.detected is True
    assert res_dd.category == AntiBotCategory.DATADOME
    assert res_dd.should_rotate_proxy is True

    # 4. CAPTCHA verification
    captcha_body = "<div>Please verify that you are not a robot to proceed.</div>"
    res_c = AntiBotDetector.inspect(200, {}, captcha_body)
    assert res_c.detected is True
    assert res_c.category == AntiBotCategory.CAPTCHA
    assert res_c.should_escalate_to_browser is True

    # 5. Rate limit (429)
    res_429 = AntiBotDetector.inspect(429, {"retry-after": "15"}, "Too Many Requests")
    assert res_429.detected is True
    assert res_429.category == AntiBotCategory.RATE_LIMITED
    assert res_429.retry_after == 15.0
    assert res_429.should_rotate_proxy is True

    # 6. Clean content
    clean_body = "<html><head><title>Research Paper</title></head><body><h1>Deep Learning</h1><p>Content.</p></body></html>"
    res_clean = AntiBotDetector.inspect(200, {}, clean_body)
    assert res_clean.detected is False
    assert res_clean.category == AntiBotCategory.NONE


@pytest.mark.asyncio
async def test_adaptive_domain_circuit_breaker():
    """Verify circuit tripping on consecutive blocks and decorrelated jitter."""
    breaker = AdaptiveDomainCircuitBreaker(
        base_delay=0.1,
        max_delay=1.0,
        consecutive_failure_threshold=3,
        cooldown_period=0.5,
    )
    test_url = "https://target-site.com/data"

    # Initial state is CLOSED
    allowed, wait = await breaker.can_request(test_url)
    assert allowed is True

    # Record 2 blocks - still under threshold
    await breaker.record_block(test_url, retry_after=0.2)
    await breaker.record_block(test_url, retry_after=0.2)
    allowed, _ = await breaker.can_request(test_url)
    assert allowed is True

    # Third block trips circuit to OPEN
    cooldown = await breaker.record_block(test_url, retry_after=0.5)
    assert cooldown >= 0.5

    # Request rejected while OPEN
    allowed_open, wait_rem = await breaker.can_request(test_url)
    assert allowed_open is False
    assert wait_rem > 0

    # Wait for cooldown to expire
    await asyncio.sleep(0.55)

    # State transitions to HALF_OPEN probe
    allowed_probe, _ = await breaker.can_request(test_url)
    assert allowed_probe is True

    # Success in probe resets circuit to CLOSED
    await breaker.record_success(test_url)
    health = breaker._domains["target-site.com"]
    assert health.state == CircuitState.CLOSED
    assert health.consecutive_blocks == 0


@pytest.mark.asyncio
async def test_proxy_rotator():
    """Verify round-robin rotation and proxy quarantine."""
    rotator = ProxyRotator(["http://p1:8080", "http://p2:8080"])
    assert rotator.has_proxies is True

    p_a = await rotator.get_proxy()
    p_b = await rotator.get_proxy()
    assert {p_a, p_b} == {"http://p1:8080", "http://p2:8080"}

    # Quarantine p1
    await rotator.report_failure("http://p1:8080", quarantine_seconds=10.0)
    p_c = await rotator.get_proxy()
    p_d = await rotator.get_proxy()
    assert p_c == "http://p2:8080"
    assert p_d == "http://p2:8080"


@pytest.mark.asyncio
async def test_extraction_pipeline_anti_bot_detection_and_escalation():
    """Verify that ExtractionPipeline detects anti-bot pages and integrates with stealth components."""
    pipeline = ExtractionPipeline({
        "timeout": 5,
        "enable_browser_escalation": False,  # Test Tier-1 anti-bot block classification
    })

    # Mock response returning Cloudflare challenge
    mock_resp = AsyncMock()
    mock_resp.status_code = 403
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.text = "<html><body>Attention Required! | Cloudflare Checking your browser before accessing</body></html>"

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items = []
        async for item in pipeline.extract_from_url("https://example.com/protected"):
            items.append(item)

        assert len(items) == 1
        assert items[0].content_type == "error"
        assert any("anti_bot_garbage" in w for w in items[0].extraction_warnings)

    # Test Playwright browser escalation path
    pipeline_with_browser = ExtractionPipeline({
        "timeout": 5,
        "enable_browser_escalation": True,
    })

    clean_rendered = "<html><head><title>Decoded</title></head><body><article><p>Hydrated real content from JS</p></article></body></html>"
    mock_driver = AsyncMock()
    mock_driver.render_page.return_value = (True, clean_rendered, {"status_code": 200})
    pipeline_with_browser.stealth_driver = mock_driver

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items_esc = []
        async for item in pipeline_with_browser.extract_from_url("https://example.com/protected"):
            items_esc.append(item)

        assert len(items_esc) >= 1
        assert mock_driver.render_page.called
        # Content successfully extracted from browser-hydrated HTML
        assert any("Hydrated real content" in it.content for it in items_esc)
        assert any("Playwright stealth browser escalation tier" in w for it in items_esc for w in it.extraction_warnings)
