"""
Health-Scored Proxy Pool Orchestrator with Domain-Sticky Routing.

Provides:
- ProxyHealthRecord: Tracks latency, success count, error count, and quarantine expiry.
- ProxyHealthOrchestrator: Intelligent proxy pool allocating the healthiest proxy,
  supporting sticky domain sessions and automatic quarantine upon consecutive bans.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ProxyHealthRecord:
    url: str
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    total_latency_ms: float = 0.0
    quarantine_until: float = 0.0
    last_used: float = 0.0

    @property
    def is_quarantined(self) -> bool:
        return time.time() < self.quarantine_until

    @property
    def average_latency_ms(self) -> float:
        if self.success_count == 0:
            return 500.0  # neutral initial baseline
        return self.total_latency_ms / self.success_count

    @property
    def health_score(self) -> float:
        """Composite health score between 0.0 and 1.0 (higher is better)."""
        if self.is_quarantined:
            return 0.0
        total_requests = self.success_count + self.failure_count
        if total_requests == 0:
            return 0.8  # initial optimistic score

        success_rate = self.success_count / total_requests
        # Penalize consecutive failures heavily
        penalty = min(0.6, self.consecutive_failures * 0.2)
        # Latency factor (normalized: <=200ms -> 1.0, >=2000ms -> 0.0)
        norm_latency = max(0.0, 1.0 - (self.average_latency_ms / 2000.0))

        score = (success_rate * 0.7 + norm_latency * 0.3) - penalty
        return max(0.01, min(1.0, score))


class ProxyHealthOrchestrator:
    """
    Manages an adaptive pool of HTTP/HTTPS/SOCKS proxies with:
    - Dynamic health scoring based on latency and block rates
    - Domain-sticky routing (pins multi-page flows to the same proxy)
    - Exponential quarantine for rate-limited or WAF-blocked proxies
    """

    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        max_consecutive_failures: int = 3,
        quarantine_duration_sec: float = 300.0,
    ):
        self.max_consecutive_failures = max_consecutive_failures
        self.quarantine_duration_sec = quarantine_duration_sec
        self._records: Dict[str, ProxyHealthRecord] = {}
        self._sticky_sessions: Dict[str, Tuple[str, float]] = {}  # domain -> (proxy, timestamp)
        self._lock = asyncio.Lock()

        if proxies:
            for p in proxies:
                p_clean = p.strip()
                if p_clean:
                    self._records[p_clean] = ProxyHealthRecord(url=p_clean)

    def add_proxy(self, proxy_url: str) -> None:
        p_clean = proxy_url.strip()
        if p_clean and p_clean not in self._records:
            self._records[p_clean] = ProxyHealthRecord(url=p_clean)

    async def get_proxy(self, target_url: Optional[str] = None) -> Optional[str]:
        """
        Select the best proxy for target_url.
        Uses sticky session if valid, otherwise picks highest health score.
        """
        if not self._records:
            return None

        domain = urlparse(target_url).netloc.lower() if target_url else ""
        now = time.time()

        async with self._lock:
            # Check existing sticky session (valid for 10 minutes)
            if domain and domain in self._sticky_sessions:
                cached_proxy, assigned_time = self._sticky_sessions[domain]
                rec = self._records.get(cached_proxy)
                if rec and not rec.is_quarantined and (now - assigned_time) < 600:
                    rec.last_used = now
                    return cached_proxy

            # Un-quarantine any proxies whose cooldown expired
            available = [r for r in self._records.values() if not r.is_quarantined]
            if not available:
                # If all quarantined, find the one closest to expiry
                closest = min(self._records.values(), key=lambda r: r.quarantine_until)
                return closest.url

            # Sort by composite health score descending
            best_record = max(available, key=lambda r: r.health_score)
            best_record.last_used = now

            if domain:
                self._sticky_sessions[domain] = (best_record.url, now)

            return best_record.url

    async def record_result(
        self,
        proxy_url: str,
        success: bool,
        latency_ms: float = 0.0,
        is_blocked: bool = False,
    ) -> None:
        """Update metrics for a proxy and trigger quarantine if banned."""
        async with self._lock:
            rec = self._records.get(proxy_url)
            if not rec:
                rec = ProxyHealthRecord(url=proxy_url)
                self._records[proxy_url] = rec

            now = time.time()
            if success:
                rec.success_count += 1
                rec.consecutive_failures = 0
                rec.total_latency_ms += latency_ms
            else:
                rec.failure_count += 1
                rec.consecutive_failures += 1

                if is_blocked or rec.consecutive_failures >= self.max_consecutive_failures:
                    # Exponential quarantine based on failure count
                    cooldown = self.quarantine_duration_sec * (2 ** min(rec.consecutive_failures - 1, 4))
                    rec.quarantine_until = now + cooldown
                    logger.warning(
                        "Proxy %s quarantined for %.1fs (failures: %d, blocked: %s)",
                        proxy_url[:30], cooldown, rec.consecutive_failures, is_blocked
                    )
