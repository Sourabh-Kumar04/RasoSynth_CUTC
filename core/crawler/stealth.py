"""
Stealth Web Extraction & Anti-Blocking Architecture.

Provides:
- StealthHeaderGenerator: Realistic browser fingerprint and header rotation.
- AntiBotDetector: High-precision detection of Cloudflare, Akamai, DataDome, CAPTCHAs, and WAF blocks.
- AdaptiveDomainCircuitBreaker: Per-domain backoff with decorrelated jitter and cooldown circuits.
- ProxyRotator: Gateway and rotating proxy management.
- PlaywrightStealthDriver: Headless browser escalation with stealth evasions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class AntiBotCategory(str, Enum):
    CLOUDFLARE = "cloudflare"
    DATADOME = "datadome"
    AKAMAI = "akamai"
    PERIMETERX = "perimeterx"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    ACCESS_DENIED = "access_denied"
    JS_REQUIRED = "javascript_required"
    NONE = "none"


@dataclass
class AntiBotInspectionResult:
    detected: bool
    category: AntiBotCategory = AntiBotCategory.NONE
    matched_pattern: str = ""
    status_code: int = 200
    should_escalate_to_browser: bool = False
    should_rotate_proxy: bool = False
    retry_after: Optional[float] = None


class AntiBotDetector:
    """Inspects HTTP responses and DOM text for WAF challenges and bot walls."""

    # High-confidence regex patterns for anti-bot detection
    PATTERNS: Dict[AntiBotCategory, List[str]] = {
        AntiBotCategory.CLOUDFLARE: [
            r"cf-browser-verification",
            r"cloudflare\s+(?:\w+\s+)*challenge",
            r"ddos\s+protection\s+by\s+cloudflare",
            r"attention\s+required!\s*\|\s*cloudflare",
            r"checking\s+your\s+browser\s+before\s+accessing",
            r"just\s+a\s+moment\b(?:\s*\.\.\.)?",
            r"cf-turnstile",
            r"challenges\.cloudflare\.com/turnstile",
            r"ray\s+id:\s*[0-9a-f]{16}",
            r"error\s+1020\s*:\s*access\s+denied",
        ],
        AntiBotCategory.DATADOME: [
            r"datadome",
            r"geo\.captcha-delivery\.com",
            r"api-js\.datadome\.co",
        ],
        AntiBotCategory.AKAMAI: [
            r"ak_bmsc",
            r"akamai\s+bot\s+manager",
            r"reference\s+#\d+\.[0-9a-f]+\.[0-9a-f]+",
        ],
        AntiBotCategory.PERIMETERX: [
            r"perimeterx",
            r"_px3",
            r"px-captcha",
            r"client\.perimeterx\.net",
        ],
        AntiBotCategory.CAPTCHA: [
            r"g-recaptcha",
            r"hcaptcha\.com",
            r"recaptcha/api\.js",
            r"verify\s+(?:that\s+)?you(?:'re|\s+are)\s+(?:not\s+)?a\s+(?:robot|human)",
            r"prove\s+you(?:'re|\s+are)\s+(?:not\s+)?a\s+(?:robot|human)",
            r"are\s+you\s+a\s+human",
            r"security\s+check\s+to\s+access",
        ],
        AntiBotCategory.JS_REQUIRED: [
            r"javascript\s+is\s+disabled",
            r"javascript\s+not\s+enabled",
            r"enable\s+javascript",
            r"requires\s+javascript",
            r"please\s+turn\s+javascript\s+on",
            r"you\s+need\s+to\s+enable\s+javascript\s+to\s+run\s+this\s+app",
        ],
        AntiBotCategory.RATE_LIMITED: [
            r"429\s+too\s+many\s+requests",
            r"rate\s+limit\s+exceeded",
            r"too\s+many\s+requests\s+from\s+your\s+ip",
        ],
        AntiBotCategory.ACCESS_DENIED: [
            r"403\s+forbidden",
            r"access\s+denied",
            r"you\s+don't\s+have\s+permission\s+to\s+access",
        ],
    }

    @classmethod
    def inspect(
        cls,
        status_code: int,
        headers: Dict[str, str],
        body_text: str,
    ) -> AntiBotInspectionResult:
        """Analyze HTTP status, headers, and body content for bot detection."""
        # 1. Check HTTP Status codes
        if status_code == 429:
            retry_after = cls._parse_retry_after(headers.get("retry-after"))
            return AntiBotInspectionResult(
                detected=True,
                category=AntiBotCategory.RATE_LIMITED,
                matched_pattern=f"HTTP status {status_code}",
                status_code=status_code,
                should_escalate_to_browser=False,
                should_rotate_proxy=True,
                retry_after=retry_after,
            )

        # 2. Check WAF signature headers
        header_keys_lower = {k.lower(): v.lower() for k, v in headers.items()}
        if "cf-mitigated" in header_keys_lower or "cf-chl-bypass" in header_keys_lower:
            return AntiBotInspectionResult(
                detected=True,
                category=AntiBotCategory.CLOUDFLARE,
                matched_pattern="Cloudflare mitigation header",
                status_code=status_code,
                should_escalate_to_browser=True,
                should_rotate_proxy=True,
            )

        if "x-datadome" in header_keys_lower:
            return AntiBotInspectionResult(
                detected=True,
                category=AntiBotCategory.DATADOME,
                matched_pattern="DataDome response header",
                status_code=status_code,
                should_escalate_to_browser=True,
                should_rotate_proxy=True,
            )

        # 3. Check body text with regex
        body_lower = body_text.lower()[:50000] if body_text else ""

        for category, patterns in cls.PATTERNS.items():
            for pat in patterns:
                if re.search(pat, body_lower):
                    should_escalate = category in (
                        AntiBotCategory.CLOUDFLARE,
                        AntiBotCategory.CAPTCHA,
                        AntiBotCategory.JS_REQUIRED,
                        AntiBotCategory.DATADOME,
                    )
                    should_proxy = category in (
                        AntiBotCategory.RATE_LIMITED,
                        AntiBotCategory.ACCESS_DENIED,
                        AntiBotCategory.PERIMETERX,
                        AntiBotCategory.AKAMAI,
                    )
                    return AntiBotInspectionResult(
                        detected=True,
                        category=category,
                        matched_pattern=pat,
                        status_code=status_code,
                        should_escalate_to_browser=should_escalate,
                        should_rotate_proxy=should_proxy,
                    )

        # 4. Status 403 fallback if text didn't match specific WAF regex
        if status_code == 403:
            return AntiBotInspectionResult(
                detected=True,
                category=AntiBotCategory.ACCESS_DENIED,
                matched_pattern="HTTP 403 Forbidden",
                status_code=status_code,
                should_escalate_to_browser=True,
                should_rotate_proxy=True,
            )

        return AntiBotInspectionResult(detected=False, status_code=status_code)

    @staticmethod
    def _parse_retry_after(header_val: Optional[str]) -> Optional[float]:
        if not header_val:
            return None
        try:
            return max(1.0, float(header_val))
        except ValueError:
            return 30.0  # Default fallback if HTTP-date format


class StealthHeaderGenerator:
    """Generates coherent, realistic desktop and mobile browser fingerprints with matching Client Hints."""

    PROFILES = [
        # Chrome 124 on Windows 11
        {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"Windows"',
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept_language": "en-US,en;q=0.9",
        },
        # Chrome 125 on macOS Sonoma
        {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec_ch_ua_mobile": "?0",
            "sec_ch_ua_platform": '"macOS"',
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept_language": "en-US,en;q=0.9",
        },
        # Safari 17.4 on macOS
        {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
            "sec_ch_ua": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_platform": None,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept_language": "en-US,en;q=0.9",
        },
        # Firefox 126 on Windows
        {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "sec_ch_ua": None,
            "sec_ch_ua_mobile": None,
            "sec_ch_ua_platform": None,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept_language": "en-US,en;q=0.5",
        },
    ]

    @classmethod
    def generate(cls, referer: Optional[str] = None) -> Dict[str, str]:
        """Generate a random coherent browser header bundle."""
        profile = random.choice(cls.PROFILES)
        headers = {
            "User-Agent": profile["user_agent"],
            "Accept": profile["accept"],
            "Accept-Language": profile["accept_language"],
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site" if referer else "none",
            "Sec-Fetch-User": "?1",
        }

        if profile["sec_ch_ua"]:
            headers["Sec-Ch-Ua"] = profile["sec_ch_ua"]
            headers["Sec-Ch-Ua-Mobile"] = profile["sec_ch_ua_mobile"]
            headers["Sec-Ch-Ua-Platform"] = profile["sec_ch_ua_platform"]

        if referer:
            headers["Referer"] = referer
        else:
            # Common realistic search referrals
            common_referers = [
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://duckduckgo.com/",
            ]
            if random.random() < 0.4:
                headers["Referer"] = random.choice(common_referers)

        return headers


class CircuitState(str, Enum):
    CLOSED = "closed"        # Healthy, normal traffic
    OPEN = "open"            # Target domain blocking, traffic suspended
    HALF_OPEN = "half_open"  # Cooldown finished, probe request allowed


@dataclass
class DomainHealth:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    consecutive_blocks: int = 0
    last_block_time: float = 0.0
    cooldown_until: float = 0.0
    current_delay: float = 1.0


class AdaptiveDomainCircuitBreaker:
    """Domain-level rate limiter & circuit breaker with decorrelated jitter backoff."""

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        consecutive_failure_threshold: int = 3,
        cooldown_period: float = 45.0,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.threshold = consecutive_failure_threshold
        self.cooldown_period = cooldown_period
        self._domains: Dict[str, DomainHealth] = {}
        self._lock = asyncio.Lock()

    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower() or "default"
        except Exception:
            return "default"

    async def can_request(self, url: str) -> Tuple[bool, float]:
        """Check if request to domain is permitted. Returns (allowed, wait_seconds)."""
        domain = self._extract_domain(url)
        now = time.time()

        async with self._lock:
            health = self._domains.setdefault(domain, DomainHealth(current_delay=self.base_delay))

            if health.state == CircuitState.OPEN:
                if now >= health.cooldown_until:
                    # Transition to HALF_OPEN probe
                    health.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker for %s entered HALF_OPEN probe state", domain)
                    return True, 0.0
                return False, health.cooldown_until - now

            # Decorrelated Jitter delay
            wait = random.uniform(health.current_delay * 0.5, health.current_delay * 1.5)
            return True, wait

    async def record_success(self, url: str) -> None:
        """Reset or decay failure count on successful extraction."""
        domain = self._extract_domain(url)
        async with self._lock:
            if domain in self._domains:
                health = self._domains[domain]
                health.failure_count = 0
                health.consecutive_blocks = 0
                health.state = CircuitState.CLOSED
                # Decay delay towards base
                health.current_delay = max(self.base_delay, health.current_delay * 0.75)

    async def record_block(self, url: str, retry_after: Optional[float] = None) -> float:
        """Handle 429/WAF block using decorrelated jitter backoff and trip circuit if necessary."""
        domain = self._extract_domain(url)
        now = time.time()

        async with self._lock:
            health = self._domains.setdefault(domain, DomainHealth(current_delay=self.base_delay))
            health.consecutive_blocks += 1
            health.failure_count += 1
            health.last_block_time = now

            # Decorrelated jitter: delay = min(max_delay, uniform(base_delay, prev_delay * 3))
            next_delay = min(self.max_delay, random.uniform(self.base_delay, health.current_delay * 3.0))
            if retry_after and retry_after > next_delay:
                next_delay = min(self.max_delay, retry_after)
            health.current_delay = next_delay

            # If consecutive block threshold breached, trip the breaker to OPEN
            if health.consecutive_blocks >= self.threshold or health.state == CircuitState.HALF_OPEN:
                trip_cooldown = max(self.cooldown_period, (retry_after or self.cooldown_period))
                health.state = CircuitState.OPEN
                health.cooldown_until = now + trip_cooldown
                logger.warning(
                    "Circuit breaker TRIPPED for %s (consecutive_blocks=%d). Cooling down for %.1fs",
                    domain, health.consecutive_blocks, trip_cooldown
                )
                return trip_cooldown

            return health.current_delay


class ProxyRotator:
    """Manages proxy rotation, stickiness, and health monitoring."""

    def __init__(self, proxy_urls: Optional[List[str]] = None):
        # 1. Load from arguments or environment
        urls = list(proxy_urls or [])
        env_pool = os.environ.get("ROTATING_PROXY_POOL", "")
        if env_pool:
            urls.extend([p.strip() for p in env_pool.split(",") if p.strip()])

        default_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if default_proxy and default_proxy not in urls:
            urls.append(default_proxy)

        self._proxies: List[str] = urls
        self._dead_proxies: Dict[str, float] = {}
        self._index: int = 0
        self._lock = asyncio.Lock()

    @property
    def has_proxies(self) -> bool:
        return bool(self._proxies)

    async def get_proxy(self) -> Optional[str]:
        """Get next available healthy proxy using round-robin."""
        if not self._proxies:
            return None

        now = time.time()
        async with self._lock:
            # Re-admit dead proxies after 5-minute quarantine
            for p, dead_until in list(self._dead_proxies.items()):
                if now >= dead_until:
                    del self._dead_proxies[p]

            healthy = [p for p in self._proxies if p not in self._dead_proxies]
            if not healthy:
                # If all are in quarantine, take the one closest to expiry
                return self._proxies[0]

            self._index = (self._index + 1) % len(healthy)
            return healthy[self._index]

    async def report_failure(self, proxy: str, quarantine_seconds: float = 300.0) -> None:
        """Quarantine a proxy that received an IP ban or connection failure."""
        async with self._lock:
            self._dead_proxies[proxy] = time.time() + quarantine_seconds
            logger.info("Proxy quarantined: %s for %.1fs", proxy[:30], quarantine_seconds)


class PlaywrightStealthDriver:
    """Tier-2 Headless Playwright driver with browser fingerprint evasion scripts."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    async def render_page(
        self,
        url: str,
        proxy: Optional[str] = None,
        wait_for_selector: Optional[str] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Launch headless Chromium, inject evasions, and capture hydrated DOM."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return False, "", {"error": "Playwright is not installed (run 'pip install playwright && playwright install chromium')"}

        try:
            async with async_playwright() as p:
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                ]

                proxy_cfg = {"server": proxy} if proxy else None

                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=launch_args,
                    proxy=proxy_cfg,
                )

                headers = StealthHeaderGenerator.generate()
                context = await browser.new_context(
                    user_agent=headers["User-Agent"],
                    locale="en-US",
                    timezone_id="America/New_York",
                    viewport={"width": 1920, "height": 1080},
                )

                # Stealth evasion scripts injected before scripts run
                await context.add_init_script("""
                    // Overwrite navigator.webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });

                    // Emulate chrome runtime object
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };

                    // Emulate permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );

                    // Mock plugins and languages
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                """)

                page = await context.new_page()

                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    # Natural human delay for JavaScript/Turnstile execution
                    await asyncio.sleep(random.uniform(1.5, 3.0))

                    if wait_for_selector:
                        try:
                            await page.wait_for_selector(wait_for_selector, timeout=5000)
                        except Exception:
                            pass

                    content = await page.content()
                    status = response.status if response else 200

                    return True, content, {
                        "status_code": status,
                        "url": page.url,
                        "title": await page.title(),
                    }
                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            logger.warning("Playwright stealth extraction failed for %s: %s", url, e)
            return False, "", {"error": str(e)}
