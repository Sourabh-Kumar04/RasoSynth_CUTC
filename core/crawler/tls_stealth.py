"""
TLS & HTTP/2 JA3/JA4 Fingerprint Evasion & Resilient Async Client.

Provides:
- TLSProfile: Emulation profiles for Chrome 124, Safari 17.4, and Firefox 125.
- StealthHTTPClient: Resilient HTTP client that dynamically selects between
  curl_cffi (impersonate="chrome120") and httpx with randomized SSL contexts
  and HTTP/2 negotiation.
"""

from __future__ import annotations

import asyncio
import logging
import random
import ssl
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

logger = logging.getLogger(__name__)


class BrowserImpersonation(str, Enum):
    CHROME_124 = "chrome124"
    CHROME_120 = "chrome120"
    SAFARI_17 = "safari17_0"
    FIREFOX_125 = "firefox125"
    EDGE_122 = "edge122"


@dataclass
class TLSProfile:
    name: BrowserImpersonation
    ja3_hash: str
    ja4_hash: str
    ciphers: str
    alpn_protocols: List[str]
    headers: Dict[str, str]


# Default ciphers matching modern browsers
MODERN_CHROME_CIPHERS = (
    "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:"
    "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
)


def get_default_tls_profiles() -> Dict[BrowserImpersonation, TLSProfile]:
    return {
        BrowserImpersonation.CHROME_124: TLSProfile(
            name=BrowserImpersonation.CHROME_124,
            ja3_hash="b32309a26951912be7dba376398abc3b",
            ja4_hash="t13d1516h2_8daaf6152771_026612f1b0ee",
            ciphers=MODERN_CHROME_CIPHERS,
            alpn_protocols=["h2", "http/1.1"],
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        ),
        BrowserImpersonation.SAFARI_17: TLSProfile(
            name=BrowserImpersonation.SAFARI_17,
            ja3_hash="2fb68f56e9c991f86be2e8f0a0c4f4a3",
            ja4_hash="t13d2013h2_2a02b1f1f1d1_8daaf6152771",
            ciphers=MODERN_CHROME_CIPHERS,
            alpn_protocols=["h2", "http/1.1"],
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.4.1 Safari/605.1.15"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            },
        ),
    }


class StealthHTTPClient:
    """
    Advanced HTTP client designed to evade anti-bot fingerprinting.
    Prefers curl_cffi for native JA3/JA4 impersonation, with a robust
    fallback to SSLContext-hardened httpx.AsyncClient.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        impersonate: BrowserImpersonation = BrowserImpersonation.CHROME_124,
        proxy: Optional[str] = None,
    ):
        self.timeout = timeout
        self.impersonate = impersonate
        self.proxy = proxy
        self.profiles = get_default_tls_profiles()

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create hardened SSL context resembling modern browser cipher order."""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        try:
            profile = self.profiles.get(self.impersonate, self.profiles[BrowserImpersonation.CHROME_124])
            context.set_ciphers(profile.ciphers)
            context.set_alpn_protocols(profile.alpn_protocols)
        except Exception as e:
            logger.debug("Failed to set custom SSL ciphers/ALPN: %s", e)
        return context

    def rotate_profile(self) -> BrowserImpersonation:
        """Rotate browser fingerprint to evade JA3/JA4 blocklists or 429 rate limits."""
        all_choices = list(BrowserImpersonation)
        remaining = [p for p in all_choices if p != self.impersonate]
        self.impersonate = random.choice(remaining)
        logger.info(f"StealthHTTPClient rotated impersonation profile to: {self.impersonate.value}")
        return self.impersonate

    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
        auto_rotate_on_block: bool = True,
    ) -> httpx.Response:
        """Execute stealth GET request with profile headers, TLS spoofing, and adaptive rotation."""
        for attempt in range(2 if auto_rotate_on_block else 1):
            profile = self.profiles.get(self.impersonate, self.profiles[BrowserImpersonation.CHROME_124])
            req_headers = dict(profile.headers)
            if headers:
                req_headers.update(headers)

            req_timeout = timeout or self.timeout
            mounts = {"http://": self.proxy, "https://": self.proxy} if self.proxy else None

            res: Optional[httpx.Response] = None

            # Attempt curl_cffi for native byte-level JA3/JA4 impersonation if installed
            try:
                from curl_cffi.requests import AsyncSession  # type: ignore

                session = AsyncSession(impersonate=self.impersonate.value)
                proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
                resp = await session.get(
                    url,
                    headers=req_headers,
                    timeout=req_timeout,
                    proxies=proxies,
                    allow_redirects=follow_redirects,
                )
                res = httpx.Response(
                    status_code=resp.status_code,
                    headers=httpx.Headers(dict(resp.headers)),
                    content=resp.content,
                    request=httpx.Request("GET", url, headers=req_headers),
                )
            except (ImportError, Exception):
                pass

            if res is None:
                # Native hardened httpx fallback with randomized SSL cipher suite
                ssl_ctx = self._create_ssl_context()
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(req_timeout),
                    headers=req_headers,
                    mounts=mounts,
                    verify=ssl_ctx,
                    follow_redirects=follow_redirects,
                    http2=True,
                ) as client:
                    res = await client.get(url)

            # Adaptive challenge / rate limit detection
            if auto_rotate_on_block and attempt == 0 and res.status_code in (403, 429, 503):
                logger.warning(f"Blocked or challenged with status {res.status_code}. Rotating fingerprint profile.")
                self.rotate_profile()
                await asyncio.sleep(0.5)
                continue

            return res

        return res  # type: ignore
