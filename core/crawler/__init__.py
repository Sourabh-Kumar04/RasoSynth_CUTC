"""Crawler and anti-blocking module."""
from core.crawler.stealth import (
    AntiBotCategory,
    AntiBotDetector,
    AntiBotInspectionResult,
    StealthHeaderGenerator,
    AdaptiveDomainCircuitBreaker,
    ProxyRotator,
    PlaywrightStealthDriver,
)

__all__ = [
    "AntiBotCategory",
    "AntiBotDetector",
    "AntiBotInspectionResult",
    "StealthHeaderGenerator",
    "AdaptiveDomainCircuitBreaker",
    "ProxyRotator",
    "PlaywrightStealthDriver",
]
