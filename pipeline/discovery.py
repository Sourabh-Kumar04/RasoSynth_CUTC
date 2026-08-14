"""Enhanced web discovery pipeline with comprehensive source finding."""
import asyncio
import httpx
import logging
import os
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, AsyncIterator, Optional
from enum import Enum
from urllib.parse import urlparse, quote, unquote
import re
import json
import random

# ── Global query hard cap ──────────────────────────────────────────────────
_MAX_QUERY_CHARS = 200
# ── Global concurrency cap for outbound HTTP calls ─────────────────────────
_MAX_CONCURRENT_HTTP = 5


def _trim_query(q: str) -> str:
    """Trim a search query to _MAX_QUERY_CHARS, cutting cleanly on a word boundary."""
    q = q.strip()
    if len(q) <= _MAX_QUERY_CHARS:
        return q
    trimmed = q[:_MAX_QUERY_CHARS]
    last_space = trimmed.rfind(" ")
    if last_space > _MAX_QUERY_CHARS // 2:
        trimmed = trimmed[:last_space]
    return trimmed.strip()


# ────────────────────────────────────────────────────────────────────────────
# Rate Limiter — per-domain token-bucket + global semaphore
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class _DomainBucket:
    """Token bucket for a single domain."""
    tokens: float
    last_refill: float
    rate: float          # tokens per second
    max_tokens: float


class RateLimiter:
    """Per-domain rate limiter with global async-semaphore concurrency cap.

    Each domain gets its own token bucket so that a surge against
    openml.org never starves zenodo.org.  A global semaphore caps the
    total number of concurrent outbound HTTP calls across all domains.
    """

    def __init__(
        self,
        global_max_concurrent: int = _MAX_CONCURRENT_HTTP,
        default_rate: float = 3.0,    # 3 req/s per domain (polite)
        default_burst: float = 5.0,    # short-term burst allowance
    ):
        self._semaphore = asyncio.Semaphore(global_max_concurrent)
        self._buckets: dict[str, _DomainBucket] = {}
        self._default_rate = default_rate
        self._default_burst = default_burst
        self._lock = asyncio.Lock()

    # ── Per-domain rate profiles ─────────────────────────────────────────
    DOMAIN_PROFILES: dict[str, tuple[float, float]] = {
        # (req/s, burst)
        "api.github.com":            (3.0, 5.0),
        "huggingface.co":            (5.0, 8.0),
        "kaggle.com":                (1.0, 2.0),   # aggressive rate limiting
        "openml.org":                (2.0, 3.0),
        "zenodo.org":                (3.0, 5.0),
        "api.figshare.com":          (2.0, 3.0),
        "paperswithcode.com":        (3.0, 5.0),
        "opendata.aws":              (2.0, 3.0),
        "catalog.data.gov":          (2.0, 3.0),
        "data.europa.eu":            (2.0, 3.0),
        "datahub.io":                (3.0, 5.0),
        "archive.ics.uci.edu":       (2.0, 3.0),
        "api.worldbank.org":         (2.0, 3.0),
        "archive.org":               (2.0, 3.0),
        "dataverse.harvard.edu":     (2.0, 3.0),
        "snap.stanford.edu":         (1.0, 2.0),   # be extra polite
        "duckduckgo.com":            (1.0, 2.0),
        "export.arxiv.org":          (1.0, 1.0),   # strict: 1 req at a time
    }

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return url

    def _get_bucket(self, domain: str) -> _DomainBucket:
        rate, burst = self.DOMAIN_PROFILES.get(
            domain, (self._default_rate, self._default_burst),
        )
        if domain not in self._buckets:
            now = time.monotonic()
            self._buckets[domain] = _DomainBucket(
                tokens=burst, last_refill=now, rate=rate, max_tokens=burst,
            )
        return self._buckets[domain]

    def acquire(self, url: str):
        """Acquire a slot — blocks until both semaphore and token bucket allow.

        Usage:
            async with rate_limiter.acquire(url):
                response = await client.get(url)
        """
        return _RateLimitGuard(self, url)


class _RateLimitGuard:
    """Context-manager helper — acquires rate limiting resources on enter and releases on exit."""
    def __init__(self, rate_limiter: RateLimiter, url: str):
        self._rate_limiter = rate_limiter
        self._url = url
        self._acquired = False

    async def __aenter__(self):
        domain = self._rate_limiter._extract_domain(self._url)

        async with self._rate_limiter._lock:
            bucket = self._rate_limiter._get_bucket(domain)
            now = time.monotonic()
            elapsed = now - bucket.last_refill
            bucket.tokens = min(bucket.max_tokens, bucket.tokens + elapsed * bucket.rate)
            bucket.last_refill = now

            if bucket.tokens < 1.0:
                wait = (1.0 - bucket.tokens) / bucket.rate
            else:
                wait = 0.0
            bucket.tokens -= 1.0

        if wait > 0:
            await asyncio.sleep(wait)

        # The semaphore acquire happens outside the lock to avoid deadlocks
        await self._rate_limiter._semaphore.acquire()
        self._acquired = True
        return self

    async def __aexit__(self, *args):
        if self._acquired:
            self._rate_limiter._semaphore.release()


# ────────────────────────────────────────────────────────────────────────────
# Source Quality Scoring
# ────────────────────────────────────────────────────────────────────────────

# Authority scores: 1.0 = gold-standard dataset repo, 0.0 = untrusted
_SOURCE_AUTHORITY: dict[str, float] = {
    # Gold-standard dataset repositories
    "archive.ics.uci.edu":           1.00,
    "huggingface.co":                0.98,
    "kaggle.com":                    0.98,
    "openml.org":                    0.95,
    "paperswithcode.com":           0.95,
    "registry.opendata.aws":        0.90,
    "zenodo.org":                    0.88,
    "figshare.com":                  0.85,
    "dataverse.harvard.edu":        0.85,
    "snap.stanford.edu":            0.90,
    # Government portals
    "data.gov":                      0.92,
    "data.europa.eu":                0.92,
    "data.gov.uk":                   0.90,
    "data.gouv.fr":                  0.88,
    "open.canada.ca":                0.85,
    "worldbank.org":                 0.88,
    # Domain-specific
    "ncbi.nlm.nih.gov":             0.90,
    "pubmed.ncbi.nlm.nih.gov":      0.85,
    "earthdata.nasa.gov":           0.88,
    "noaa.gov":                      0.85,
    "commoncrawl.org":              0.80,
    # Research
    "arxiv.org":                     0.75,
    "export.arxiv.org":             0.75,
    "semanticscholar.org":          0.70,
    # Code repositories (secondary)
    "github.com":                    0.50,
    "gitlab.com":                    0.45,
    # Generic / unknown
    "wikipedia.org":                 0.60,
    "archive.org":                   0.70,
    "datahub.io":                    0.78,
}


def score_source(source: "DiscoveredSource") -> float:
    """Score a discovered source 0.0–1.0 based on authority, completeness, freshness.

    Weights: authority=0.50, completeness=0.30, freshness=0.20
    """
    authority = _score_authority(source.url)
    completeness = _score_completeness(source)
    freshness = _score_freshness(source)
    return round(authority * 0.50 + completeness * 0.30 + freshness * 0.20, 3)


def _score_authority(url: str) -> float:
    """Map domain to authority score via lookup table."""
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return 0.1
    # Try exact match, then partial match
    for known, score in _SOURCE_AUTHORITY.items():
        if known in domain or domain.endswith("." + known):
            return score
    # Unknown domains get a baseline of 0.3
    return 0.3


def _score_completeness(source: "DiscoveredSource") -> float:
    """Higher score = more metadata fields are present."""
    score = 0.0
    if source.title:
        score += 0.20
    if source.description and len(source.description) > 50:
        score += 0.25
    if source.license:
        score += 0.15
    if source.author:
        score += 0.10
    if source.date:
        score += 0.10
    if source.size_bytes:
        score += 0.10
    if source.metadata:
        score += min(0.10, len(source.metadata) * 0.02)
    return min(1.0, score)


def _score_freshness(source: "DiscoveredSource") -> float:
    """Score dataset freshness.  Recent = higher score."""
    if not source.date:
        return 0.3  # Unknown — neutral
    try:
        # Try ISO date parsing
        from datetime import datetime
        date_str = source.date[:10]  # YYYY-MM-DD
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        age_days = (time.time() - parsed.timestamp()) / 86400
        if age_days < 365:       # < 1 year
            return 1.0
        elif age_days < 730:     # 1–2 years
            return 0.8
        elif age_days < 1460:    # 2–4 years
            return 0.6
        elif age_days < 2920:    # 4–8 years
            return 0.4
        else:
            return 0.2
    except Exception:
        return 0.3


# ────────────────────────────────────────────────────────────────────────────
# URL Health Check
# ────────────────────────────────────────────────────────────────────────────

async def health_check_urls(
    sources: list["DiscoveredSource"],
    max_concurrent: int = 10,
    timeout: float = 10.0,
) -> tuple[list["DiscoveredSource"], list["DiscoveredSource"]]:
    """Verify URLs resolve. Returns (healthy, dead)."""
    sem = asyncio.Semaphore(max_concurrent)

    async def _check(source: "DiscoveredSource") -> "DiscoveredSource | None":
        async with sem:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout), follow_redirects=True,
                ) as client:
                    resp = await client.head(
                        source.url,
                        headers={"User-Agent": "RasoDataset-Agent/1.0"},
                    )
                    if resp.status_code < 400:
                        # Update metadata with resolved URL and status
                        source.metadata["health_checked"] = True
                        source.metadata["health_status"] = resp.status_code
                        source.metadata["resolved_url"] = str(resp.url)
                        return source
                    else:
                        source.metadata["health_checked"] = True
                        source.metadata["health_status"] = resp.status_code
                        source.metadata["health_error"] = f"HTTP {resp.status_code}"
                        return None
            except Exception as e:
                source.metadata["health_checked"] = True
                source.metadata["health_status"] = 0
                source.metadata["health_error"] = str(e)[:200]
                return None

    results = await asyncio.gather(
        *[_check(s) for s in sources], return_exceptions=True,
    )
    healthy = [r for r in results if r is not None and not isinstance(r, Exception)]
    dead: list["DiscoveredSource"] = []
    for src, res in zip(sources, results):
        if res is None or isinstance(res, Exception):
            dead.append(src)
    return healthy, dead


# ────────────────────────────────────────────────────────────────────────────
# Discovery Result Cache (optional Redis, in-memory fallback)
# ────────────────────────────────────────────────────────────────────────────

class DiscoveryCache:
    """Two-tier cache: in-memory dict, with optional Redis backend."""

    def __init__(self, ttl: int = 3600):
        self._ttl = ttl
        self._memory: dict[str, tuple[float, list[dict]]] = {}
        self._redis = None
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "")
            if redis_url:
                self._redis = aioredis.from_url(redis_url)
        except Exception:
            pass

    @staticmethod
    def _make_key(query: str, target_domain: str, source_type: str) -> str:
        return f"disc:{query[:80]}:{target_domain[:80]}:{source_type}"

    async def get(
        self, query: str, target_domain: str, source_type: str,
    ) -> list["DiscoveredSource"] | None:
        from copy import deepcopy
        key = self._make_key(query, target_domain, source_type)

        # Try Redis first
        if self._redis:
            try:
                raw = await self._redis.get(key)
                if raw:
                    data = json.loads(raw)
                    sources = []
                    for d in data:
                        d.pop("_cached", None)
                        sources.append(DiscoveredSource(**d))
                    return sources
            except Exception:
                pass

        # In-memory fallback
        entry = self._memory.get(key)
        if entry is not None:
            cached_at, cached_data = entry
            if time.time() - cached_at < self._ttl:
                sources = []
                for d in cached_data:
                    sources.append(DiscoveredSource(**deepcopy(d)))
                return sources
            else:
                del self._memory[key]
        return None

    async def set(
        self,
        query: str,
        target_domain: str,
        source_type: str,
        sources: list["DiscoveredSource"],
    ):
        key = self._make_key(query, target_domain, source_type)
        from dataclasses import asdict
        data = [asdict(s) for s in sources]

        # Store in memory
        self._memory[key] = (time.time(), data)

        # Store in Redis if available
        if self._redis:
            try:
                await self._redis.setex(
                    key, self._ttl, json.dumps(data, default=str),
                )
            except Exception:
                pass

    async def clear(self):
        self._memory.clear()
        if self._redis:
            try:
                await self._redis.flushdb()
            except Exception:
                pass

# ── Global query hard cap ──────────────────────────────────────────────────
_MAX_QUERY_CHARS = 200


def _trim_query(q: str) -> str:
    """Trim a search query to _MAX_QUERY_CHARS, cutting cleanly on a word boundary."""
    q = q.strip()
    if len(q) <= _MAX_QUERY_CHARS:
        return q
    trimmed = q[:_MAX_QUERY_CHARS]
    last_space = trimmed.rfind(" ")
    if last_space > _MAX_QUERY_CHARS // 2:
        trimmed = trimmed[:last_space]
    return trimmed.strip()


class SourceType(Enum):
    WEB_PAGE = "web_page"
    GITHUB_REPO = "github_repo"
    GITHUB_FILE = "github_file"
    ARXIV_PAPER = "arxiv_paper"
    YOUTUBE_VIDEO = "youtube_video"
    PDF_DOCUMENT = "pdf_document"
    HACKERNEWS = "hackernews"
    STACKOVERFLOW = "stackoverflow"
    REDDIT_POST = "reddit_post"
    KAGGLE_DATASET = "kaggle_dataset"
    HF_DATASET = "hf_dataset"
    WIKIPEDIA = "wikipedia"
    WIKIDATA = "wikidata"
    GOOGLE_SCHOLAR = "google_scholar"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    PUBMED = "pubmed"
    TECH_DOCS = "tech_docs"
    RAW_CODE = "raw_code"
    DATASET_REPO = "dataset_repo"
    COMMON_CRAWL = "common_crawl"
    DIRECT_DATASET = "direct_dataset"
    OPEN_DATA_PORTAL = "open_data_portal"
    # ── Open data repositories ──────────────────────────────────────────
    OPENML = "openml"
    SNAP = "snap"                       # Stanford Network Analysis Project
    AWS_OPEN_DATA = "aws_open_data"     # AWS Registry of Open Data
    ZENODO = "zenodo"
    FIGSHARE = "figshare"
    DATAPORTALS_ORG = "dataportals_org"
    GOOGLE_DATASET_SEARCH = "google_dataset_search"
    DATAHUB_IO = "datahub_io"
    PAPERS_WITH_CODE = "papers_with_code"
    GOVERNMENT_DATA = "government_data"
    EUROSTAT = "eurostat"
    DATAONE = "dataone"
    MOLECULENET = "moleculenet"
    OPEN_IMAGES = "open_images"
    COMMON_VOICE = "common_voice"


@dataclass
class DiscoveredSource:
    """A discovered data source."""
    url: str
    source_type: SourceType
    title: str
    description: str | None = None
    metadata: dict = field(default_factory=dict)
    discovered_at: float = field(default_factory=lambda: __import__('time').time())
    author: str | None = None
    date: str | None = None
    license: str | None = None
    size_bytes: int | None = None
    stars: int | None = None
    raw_content_url: str | None = None
    quality_score: float = 0.0       # 0.0–1.0, computed by score_source()
    health_status: int | None = None  # HTTP status from health check (None=unchecked)


class SearchEngine(Enum):
    DUCKDUCKGO = "duckduckgo"
    GOOGLE = "google"
    SERPAPI = "serpapi"
    BRAVE = "brave"
    BING = "bing"
    YANDEX = "yandex"


class DiscoveryPipeline:
    """Enhanced pipeline for discovering data from comprehensive web sources."""

    # Comprehensive list of open data repositories and portals
    DATASET_PORTALS = [
        # ── Primary ML dataset repositories ────────────────────────────
        "huggingface.co/datasets",           # Hugging Face Datasets
        "kaggle.com/datasets",               # Kaggle
        "openml.org/search?type=data&q=",    # OpenML
        "archive.ics.uci.edu",               # UCI ML Repository
        "paperswithcode.com/datasets",       # Papers with Code
        "tensorflow.org/datasets",           # TensorFlow Datasets
        "pytorch.org/vision/stable/datasets",# TorchVision Datasets
        # ── Government & institutional open data ────────────────────────
        "data.gov",                          # U.S. Government Open Data
        "data.europa.eu",                    # EU Open Data Portal
        "data.gov.uk",                       # UK Government Open Data
        "opendata.swiss",                    # Swiss Open Data
        "data.berlin.de",                    # Berlin Open Data
        "data.gouv.fr",                      # French Open Data
        "open.canada.ca",                    # Canadian Open Data
        "data.gov.au",                       # Australian Open Data
        # ── Academic & research repositories ────────────────────────────
        "zenodo.org",                        # CERN Zenodo
        "figshare.com",                      # Figshare
        "datadryad.org",                     # Dryad
        "dataverse.harvard.edu",             # Harvard Dataverse
        "dataone.org",                       # DataONE (Earth/Env science)
        # ── Domain-specific data repositories ──────────────────────────
        "snap.stanford.edu/data",           # Stanford SNAP
        "registry.opendata.aws",            # AWS Open Data Registry
        "dataportals.org",                  # DataPortals.org aggregator
        "datahub.io",                       # DataHub.io
        # ── International organizations ─────────────────────────────────
        "worldbank.org",                    # World Bank Data
        "data.un.org",                      # UN Data
        "who.int/data",                     # WHO Health Data
        "imf.org/en/Data",                  # IMF Data
        # ── Science-specific ────────────────────────────────────────────
        "ncbi.nlm.nih.gov",                 # NCBI (Bio/Medical)
        "earthdata.nasa.gov",               # NASA Earth Data
        "noaa.gov/data",                    # NOAA Weather/Climate
        # ── Image & multimedia datasets ─────────────────────────────────
        "images.cv/dataset",                # Images.CV
        "roboflow.com",                     # Roboflow (CV datasets)
        "visualdata.io",                    # VisualData discovery
        # ── Text & NLP data ────────────────────────────────────────────
        "commoncrawl.org",                  # Common Crawl
        "opus.nlpl.eu",                     # OPUS (parallel corpora)
    ]

    CODE_REPOSITORIES = [
        "github.com/search?q=",
        "gitlab.com/search?search=",
        "bitbucket.org/search?q=",
    ]

    TECHNICAL_DOCS_SOURCES = [
        "docs.python.org",
        "developer.mozilla.org",
        "docs.microsoft.com",
        "cloud.google.com/docs",
        "docs.aws.amazon.com",
        "devdocs.io",
        "readthedocs.io",
    ]

    SEARCH_QUERIES = [
        # ── Primary dataset-focused queries ─────────────────────────────
        "{query} {domain} dataset",
        "{query} {domain} open data",
        "{query} {domain} labeled dataset",
        "{query} {domain} annotated corpus",
        # ── Repository-scoped searches (quality sources only) ───────────
        "{query} site:huggingface.co/datasets {query}",
        "{query} site:kaggle.com/datasets {query}",
        "{query} site:openml.org {query}",
        "{query} site:zenodo.org {query}",
        "{query} site:data.gov {query}",
        "{query} site:paperswithcode.com/datasets {query}",
        "{query} site:archive.ics.uci.edu {query}",
        "{query} site:snap.stanford.edu/data {query}",
        "{query} site:registry.opendata.aws {query}",
        "{query} site:figshare.com {query}",
        "{query} site:datahub.io {query}",
        "{query} site:dataverse.harvard.edu {query}",
        # ── File-type targeted ──────────────────────────────────────────
        "{query} filetype:csv {query} dataset",
        "{query} filetype:json {query} dataset",
        "{query} filetype:parquet {query} dataset",
        # ── Research & academic ─────────────────────────────────────────
        "{query} {domain} research data",
        "{query} {domain} benchmark",
        "{query} {domain} fine-tuning data",
        "{query} {domain} training data",
        # ── Documentation & learning (only for docs/tutorials) ──────────
        "{query} {domain} dataset documentation",
        "{query} {domain} data preparation tutorial",
    ]

    def __init__(self, config: dict, router=None):
        self.config = config
        self.router = router  # Pre-initialised ProviderRouter with API keys (preferred)
        self.domain_allowlist = config.get("allowed_domains", [])
        self.domain_blocklist = [
            "facebook.com", "twitter.com", "instagram.com", "tiktok.com",
            "linkedin.com", "pinterest.com"
        ] + config.get("blocked_domains", [])
        self.rate_limit = config.get("rate_limit", 5)
        self.max_results = config.get("max_results", 500)
        self.max_per_source = config.get("max_per_source", 50)
        self.search_engines = config.get("search_engines", ["duckduckgo"])
        self.serpapi_key = config.get("serpapi_key")
        self.google_search_key = config.get("google_search_api_key")
        self.brave_search_key = config.get("brave_search_api_key")
        self.github_token = config.get("github_token")
        # Explicit source URLs to fetch directly (highest priority)
        self._explicit_source_urls = config.get("source_urls", [])
        self._discovered_urls = set()
        self._http_timeout = config.get("http_timeout", 30.0)
        # ── New infrastructure ─────────────────────────────────────────
        self._rate_limiter = RateLimiter()
        self._cache = DiscoveryCache(ttl=config.get("cache_ttl", 3600))
        self._quality_filter_threshold = config.get("quality_min_score", 0.3)
        self._health_check_enabled = config.get("health_check_enabled", True)
        self._health_check_timeout = config.get("health_check_timeout", 10.0)
        self._cache = DiscoveryCache(ttl=config.get("cache_ttl", 3600))
        self._quality_filter_threshold = config.get("quality_min_score", 0.3)
        self._health_check_enabled = config.get("health_check_enabled", True)
        self._health_check_timeout = config.get("health_check_timeout", 10.0)

    def _should_retry_response(self, response: httpx.Response) -> bool:
        """Determine if a response should trigger a retry based on status code.

        Retries on:
        - 403 Forbidden (might be temporary rate limiting)
        - 429 Too Many Requests (rate limiting)
        - 5xx Server errors

        Does NOT retry on:
        - 404 Not Found (treated as dead link)
        - 4xx client errors (except 403, 429)
        """
        if response.status_code >= 500:
            return True
        if response.status_code in (403, 429):
            return True
        return False

    def _get_retry_after(self, response: httpx.Response) -> float:
        """Extract retry-after delay from response headers, defaulting to 1 second.

        Returns:
            Delay in seconds to wait before retrying
        """
        # Try to get Retry-After header
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                # Could be seconds or a date
                return float(retry_after)
            except ValueError:
                # If it's a date format, we'd need to parse it
                # For simplicity, default to 1 second if parsing fails
                pass
        return 1.0

    async def _get_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs
    ) -> httpx.Response:
        """HTTP GET with exponential backoff retry (max 3 retries, base delay 1s).

        Retries on 403, 429, and 5xx errors, and network failures.
        Does not retry on 404 (treated as dead link).
        Uses asyncio.sleep for non-blocking delays between retries.
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                response = await client.get(url, **kwargs)

                # Check if we should retry based on status code
                if self._should_retry_response(response):
                    # If this is not the last attempt, prepare to retry
                    if attempt < max_retries - 1:
                        # For 403 and 429, try to respect Retry-After header
                        if response.status_code in (403, 429):
                            retry_after = self._get_retry_after(response)
                            delay = max(retry_after, base_delay * (2 ** attempt))
                        else:
                            delay = base_delay * (2 ** attempt)

                        self._LOG.debug(f"Retrying {url} after {delay}s (attempt {attempt + 1}/{max_retries}, status: {response.status_code})")
                        await asyncio.sleep(delay)
                        continue
                    # If this is the last attempt, we'll fall through and return the response
                # Return immediately for non-retryable status codes (including 2xx, 400, 401, 404, etc.)
                return response

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_exception = e
                # For network errors, retry if not the last attempt
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    self._LOG.debug(f"Network error for {url}, retrying after {delay}s (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}")
                    await asyncio.sleep(delay)
                    continue
                # If this is the last attempt, we'll fall through

        # If we have an exception from the last attempt, raise it
        if last_exception:
            raise last_exception
        # Should not reach here; return a generic 503 response as fallback
        return httpx.Response(status_code=503, request=httpx.Request("GET", url))

    async def _fetch(
        self,
        url: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 30.0,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Rate-limited HTTP GET with retry — one-stop shop for all discovery calls.

        Combines:
          1. Per-domain rate limiting (token bucket + global semaphore)
          2. Exponential-backoff retry
          3. Automatic client management

        Usage:  response = await self._fetch("https://api.example.com/data", params={"q": "..."})
        """
        default_headers = {
            "User-Agent": "RasoDataset-Agent/1.0 (+https://github.com/raso/dataset-engineer)",
            "Accept": "application/json, text/html, */*",
        }
        if headers:
            default_headers.update(headers)

        async with self._rate_limiter.acquire(url):
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout), follow_redirects=True,
            ) as client:
                return await self._get_with_retry(
                    client, url,
                    max_retries=max_retries, base_delay=base_delay,
                    headers=default_headers, params=params,
                )

    _SANITIZE_RE = re.compile(r"^[\s\"']*", re.MULTILINE)
    _LOG = logging.getLogger(__name__)

    @dataclass
    class QueryExtractionResult:
        """Tracks which extraction tier fired and its output quality."""
        query: str
        method: str  # "emergency" | "small_llm" | "structured_json"
        model: str | None
        confidence: float  # 0.0–1.0
        details: str  # Human-readable summary

    # ── Helper: strip all known instruction headers ─────────────────────
    _INSTRUCTION_PREFIXES = (
        "Dataset Name:", "Goal:", "Dataset Type:", "Domains:",
        "Allowed Sources:", "Data Collection Strategy:", "Quality Requirements:",
        "Difficulty Distribution:", "Output Formats:", "Human Review:",
        "Benchmarking:", "Success Criteria:", "Target Size:",
    )

    def _strip_instruction_headers(self, text: str) -> str:
        """Aggressively strip known instruction headers and template noise."""
        # Strip each prefix wherever it appears (case‑insensitive)
        result = text
        for prefix in self._INSTRUCTION_PREFIXES:
            # Pattern to match the prefix up to a newline or end of string, then replace with empty
            pattern = re.compile(re.escape(prefix), re.IGNORECASE)
            result = pattern.sub('', result)
        # Collapse whitespace
        result = result.replace('\n', ' ').replace('\r', ' ')
        result = re.sub(r"\s+", " ", result).strip()
        # Remove stray markdown artifacts
        result = re.sub(r"^[-*+]\s*", "", result)
        return result

    # ── Emergency fallback — never uses LLM, only for total API failure ──
    def _emergency_fallback(self, query: str) -> tuple[str, str]:
        """Minimal extraction when ALL LLM tiers are unavailable. No emergency logic."""
        name_match = re.search(r"Dataset Name:\s*([A-Z][^\s\n]+)", query)
        if name_match:
            return _trim_query(name_match.group(1)), "emergency:dataset_name"
        goal_match = re.search(r"Goal:\s*\n?(.+?)(?=\n\n|\n[A-Z][a-z]|\n#$|\Z)", query, re.IGNORECASE | re.DOTALL)
        if goal_match:
            text = goal_match.group(1).strip().replace("\n", " ").replace("\r", " ")[:100]
            return _trim_query(text), "emergency:goal_text"
        stripped = re.sub(r"[^\w\s]", " ", query).strip()[:80]
        return _trim_query(stripped) or "dataset search", "emergency:stripped"

    # -------------------------------------------------------------------------
    # Tier 2 — Full LLM (comprehensive search query generation)
    # -------------------------------------------------------------------------
    async def _tier2_full_llm(self, query: str) -> tuple[str, str]:
        """Generate a polished search query via a full-capability LLM with reasoning."""
        try:
            from providers.core_lib.base import TaskType
        except ImportError as exc:
            return None, f"import_failed:{exc}"

        router = self.router
        if router is None:
            try:
                from core.provider_router import ProviderRouter
                router = ProviderRouter(self.config)
            except Exception:
                return None, "router_init_failed"

        system = (
            "You are a search-query optimization specialist. Given a dataset "
            "specification, produce a single concise search string (≤200 chars) "
            "that will find relevant datasets, GitHub repos, papers, or data sources. "
            "Return ONLY the query string — no markdown, no bullets, no explanations."
        )
        prompt = (
            "Analyze the dataset request below and output the best 1-line search query.\n\n"
            f"Dataset Request:\n{query[:2000]}\n\n"
            "Search Query:"
        )
        start = time.monotonic()
        try:
            response = await router.route(
                task=TaskType.TEXT_GENERATION,
                prompt=prompt,
                system_prompt=system,
                temperature=0.3,
                max_tokens=150,
            )
        except Exception as e:
            return None, f"full_llm_error:{str(e)[:60]}"
        latency_ms = (time.monotonic() - start) * 1000

        if not response:
            return None, "full_llm_empty_response"

        raw = response.content if hasattr(response, "content") else str(response)
        raw = re.sub(r"```[^`]*```", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"^[\s\"']|[\"']$", "", raw.strip()).strip()
        raw = re.sub(r"^[-*>(\d+).#]+\s*", "", raw).strip()
        raw = re.sub(r"\s+", " ", raw).strip()

        if not raw or len(raw) < 3 or len(raw) > 400:
            return None, f"full_llm_invalid_output({len(raw)} chars)"

        raw = _trim_query(raw)
        model = getattr(response, "model", None) or "unknown"
        self._LOG.info(
            "Query sanitisation TIER-2 (full LLM): model=%s latency=%.0fms "
            "input=%d chars → output=%d chars",
            model, latency_ms, len(query), len(raw),
        )
        return raw, f"full_llm:{model}({latency_ms:.0f}ms)"

    # -------------------------------------------------------------------------
    # Tier 1 — Small LLM (ProviderRouter → TEXT_GENERATION, cheap & fast)
    # -------------------------------------------------------------------------
    async def _tier1_small_llm(self, query: str) -> tuple[str, str]:
        """Extract keywords via a lightweight LLM call through ProviderRouter."""
        try:
            from providers.core_lib.base import TaskType
        except ImportError as exc:
            return None, f"import_failed:{exc}"

        # Prefer the pre-initialised server router (has API keys); fall back to new instance
        router = self.router
        if router is None:
            try:
                from core.provider_router import ProviderRouter
                router = ProviderRouter(self.config)
            except Exception:
                return None, "router_init_failed"

        system = (
            "You are a Production IR & Query Engineering Expert (Scale AI & DSPy standards).\n"
            "Given a dataset request, extract a high-precision, 2-to-3 word search query.\n\n"
            "<rules>\n"
            "1. Output strictly a single 2-to-3 word search phrase (e.g. 'news dataset' or 'python algorithm').\n"
            "2. Strip out all UI markers, goal statements, and formatting fluff.\n"
            "3. Do NOT output sentences, bullet points, or markdown formatting.\n"
            "</rules>"
        )
        prompt = (
            f"<task>Extract High-Precision Search Query</task>\n"
            f"<dataset_request>\n{query[:1500]}\n</dataset_request>\n\n"
            "Output strictly a 2-3 word search phrase:"
        )
        start = time.monotonic()
        try:
            response = await router.route(
                task=TaskType.TEXT_GENERATION,
                prompt=prompt,
                system_prompt=system,
                temperature=0.1,
                max_tokens=40,
            )
        except Exception as e:
            return None, f"llm_error:{str(e)[:60]}"
        latency_ms = (time.monotonic() - start) * 1000

        if not response:
            return None, "llm_empty_response"

        raw = response.content if hasattr(response, "content") else str(response)
        raw = re.sub(r"```[^`]*```", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"^['\"']|['\"']$", "", raw.strip()).strip()
        raw = re.sub(r"\s+", " ", raw).strip()

        if not raw or len(raw) < 3 or len(raw) > 400:
            return None, f"llm_invalid_output({len(raw)} chars)"

        if len(raw) > 80:
            raw = raw[:80].rsplit(" ", 1)[0]

        model = getattr(response, "model", None) or "unknown"
        self._LOG.info(
            "Query sanitisation TIER-2 DEFAULT (Full LLM HyDE): model=%s latency=%.0fms "
            "input=%d chars → output=%d chars (%r)",
            model, latency_ms, len(query), len(raw), raw
        )
        return raw, f"full_llm_hyde:{model}({latency_ms:.0f}ms)"

    # -------------------------------------------------------------------------
    # Tier 3 — Structured JSON (Full LLM → schema-parsed domain+keywords+size)
    # -------------------------------------------------------------------------
    async def _tier3_structured(self, query: str) -> tuple[str, str]:
        """Extract structured metadata via full LLM. Falls back to emergency on any failure — NEVER returns None."""
        try:
            from providers.core_lib.base import TaskType
        except ImportError as exc:
            # Fall back to emergency gracefully
            e_result = self._emergency_fallback(query)[0]
            return e_result, f"import_failed:{exc} → emergency:{e_result[:30]}"

        router = self.router
        if router is None:
            try:
                from core.provider_router import ProviderRouter
                router = ProviderRouter(self.config)
            except Exception:
                e_result = self._emergency_fallback(query)[0]
                return e_result, f"router_init_failed → emergency:{e_result[:30]}"

        system = (
            "You are a dataset requirement parser. Return ONLY valid JSON:\n"
            '{"dataset_name":"…","domain":"…","keywords":["…"],"target_size":"…","format":"…"}\n'
            "Return only the JSON — no markdown fences, no explanations."
        )
        start = time.monotonic()
        try:
            response = await router.route(
                task=TaskType.STRUCTURED_OUTPUT,
                prompt=query[:2000],
                system_prompt=system,
                temperature=0.3,
                max_tokens=300,
            )
        except Exception as e:
            e_result = self._emergency_fallback(query)[0]
            return e_result, f"structured_error:{str(e)[:40]} → emergency:{e_result[:30]}"

        if not response:
            e_result = self._emergency_fallback(query)[0]
            return e_result, f"empty_response → emergency:{e_result[:30]}"

        raw = response.content if hasattr(response, "content") else str(response)
        raw = re.sub(r"```json\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"```\s*", "", raw)
        raw = re.sub(r'^[\s"{]+', "", raw).strip()
        raw = re.sub(r'[\s}]+$', "", raw).strip()

        # ── Parse JSON safely; on failure try regex-extraction from raw text ───
        try:
            parsed = json.loads(raw)
        except Exception:
            # Regex fallback: extract domain name(s) directly from raw text
            domain_phrases = re.findall(
                r'"domain"\s*:\s*"([^"]{2,60})"', raw, re.IGNORECASE
            )
            keywords_found = re.findall(
                r'"keywords"\s*:\s*\[([^\]]{5,200})\]', raw
            )
            # Try to pull individual keyword strings from the raw response
            kw_items = re.findall(r'"([^"]{3,40})"', keywords_found[0] if keywords_found else "")
            domain = domain_phrases[0] if domain_phrases else ""
            keywords = kw_items[:6] if kw_items else []

            if domain or keywords:
                parts = [p for p in [domain] + keywords if p]
                fused = " ".join(parts)
                if len(fused) > 100:
                    fused = fused[:200].rsplit(" ", 1)[0]
                model = getattr(response, "model", None) or "unknown"
                latency_ms = (time.monotonic() - start) * 1000
                self._LOG.info(
                    "Query sanitisation TIER-3 (structured JSON): "
                    "model=%s parse_failed_using_regex → %r",
                    model, fused,
                )
                return fused, f"structured_regex_fallback:{model}({latency_ms:.0f}ms)"
            else:
                # Total parse failure — fall back to emergency
                e_result = self._emergency_fallback(query)[0]
                return e_result, f"json_parse_failed → emergency:{e_result[:30]}"

        domain = parsed.get("domain", "") or ""
        keywords = parsed.get("keywords", []) or []
        dataset_name = parsed.get("dataset_name", "") or ""

        # Industry Standard IR: Keep primary query short (2-3 words max) to avoid BM25/API search term explosion
        primary_term = dataset_name or domain or (keywords[0] if keywords else "")
        secondary_terms = [k for k in keywords if k.lower() != primary_term.lower()][:2]
        
        parts = [primary_term] + secondary_terms
        fused = " ".join([p for p in parts if p]).strip()

        if not fused or len(fused) < 3:
            e_result = self._emergency_fallback(query)[0]
            return e_result, f"empty_json_result → emergency:{e_result[:30]}"

        model = getattr(response, "model", None) or "unknown"
        latency_ms = (time.monotonic() - start) * 1000
        self._LOG.info(
            "Query sanitisation TIER-3 (structured JSON): model=%s latency=%.0fms "
            "domain=%r keywords=%r",
            model, latency_ms, domain,
            keywords[:3] if isinstance(keywords, list) else keywords,
        )
        return fused, f"structured_json:{model}({latency_ms:.0f}ms)"

    # -------------------------------------------------------------------------
    # Public entry-point — pure-LLM 3-tier cascade + emergency fallback
    # -------------------------------------------------------------------------
    async def _sanitize_query(
        self, raw_prompt: str
    ) -> "DiscoveryPipeline.QueryExtractionResult":
        """Chip Huyen AI Engineering Query Generation Cascade.

        Tier 2 (Full LLM):       PRIMARY DEFAULT - Comprehensive, XML-contracted query generation
        Tier 3 (Structured JSON): Rich schema-parsed fallback
        Tier 1 (Small LLM):      Fast keyword fallback
        Emergency:               Regex fallback
        """
        # ── Tier 2: Full LLM (PRIMARY DEFAULT as per AI Engineering book) ──────
        t2_query, t2_details = await self._tier2_full_llm(raw_prompt)
        if t2_query and len(t2_query) >= 3:
            t2_query = _trim_query(t2_query)
            model = "unknown"
            if ":" in t2_details:
                model = t2_details.split(":", 1)[1].split("(")[0]
            self._LOG.info(
                "Query sanitisation TIER-2 DEFAULT (FULL_LLM accepted): input=%d chars → %r",
                len(raw_prompt), t2_query,
            )
            return self.QueryExtractionResult(
                query=t2_query, method="full_llm_default",
                model=model, confidence=0.92, details=t2_details,
            )

        # ── Tier 3: Structured JSON ────────────────────────────────────────
        t3_query, t3_details = await self._tier3_structured(raw_prompt)
        if t3_query and len(t3_query) >= 3:
            t3_query = _trim_query(t3_query)
            model = "unknown"
            if ":" in t3_details:
                model = t3_details.split(":", 1)[1].split("(")[0]
            self._LOG.info(
                "Query sanitisation TIER-3 (STRUCTURED_JSON accepted): input=%d chars → %r",
                len(raw_prompt), t3_query,
            )
            return self.QueryExtractionResult(
                query=t3_query, method="structured_json",
                model=model, confidence=0.88, details=t3_details,
            )

        # ── Tier 1: Small LLM (fast fallback) ──────────────────────────────
        t1_query, t1_details = await self._tier1_small_llm(raw_prompt)
        if t1_query and len(t1_query) >= 3:
            t1_query = _trim_query(t1_query)
            model = "unknown"
            if ":" in t1_details:
                model = t1_details.split(":", 1)[1].split("(")[0]
            self._LOG.info(
                "Query sanitisation TIER-1 (SMALL_LLM accepted): input=%d chars → %r",
                len(raw_prompt), t1_query,
            )
            return self.QueryExtractionResult(
                query=t1_query, method="small_llm",
                model=model, confidence=0.80, details=t1_details,
            )

        # ── Tier 3: Structured JSON ────────────────────────────────────────
        t3_query, t3_details = await self._tier3_structured(raw_prompt)
        if t3_query and len(t3_query) >= 4:
            t3_query = _trim_query(t3_query)
            model = "unknown"
            if ":" in t3_details:
                model = t3_details.split(":", 1)[1].split("(")[0]
            self._LOG.info(
                "Query sanitisation TIER-3 (STRUCTURED_JSON accepted): input=%d chars → %r",
                len(raw_prompt), t3_query,
            )
            return self.QueryExtractionResult(
                query=t3_query, method="structured_json",
                model=model, confidence=0.95, details=t3_details,
            )

        # ── All LLM tiers failed: emergency extraction ────────────────────
        e_query, e_details = self._emergency_fallback(raw_prompt)
        self._LOG.warning(
            "Query sanitisation EMERGENCY FALLBACK (all LLM tiers failed: "
            "t1=%s t2=%s t3=%s). Using: %r",
            t1_details, t2_details, t3_details, e_query,
        )
        return self.QueryExtractionResult(
            query=e_query, method="emergency",
            model=None, confidence=0.3,
            details=f"all_llm_failed — emergency: {e_details}",
        )

    async def discover(
        self,
        query: str,
        target_domain: str,
        source_types: list[SourceType] | None = None
    ) -> AsyncGenerator[DiscoveredSource, None]:
        """Discover sources using multiple strategies and search engines.

        Priority order:
        1. Explicit source URLs (fetched directly, highest priority)
        2. Cache lookup
        3. API discovery (HuggingFace, Kaggle, etc.)
        4. Web search (last resort)

        Pipeline: explicit URLs → cache → API discovery → scoring → health check → yield.
        """
        # Handle explicit source URLs if provided (HIGHEST PRIORITY)
        # Explicit URLs are fetched directly and bypass ALL other discovery methods
        # (cache, repository search, web search, etc.) as per system prompt requirements
        if self._explicit_source_urls:
            for url in self._explicit_source_urls:
                try:
                    # Fetch the URL directly
                    response = await self._fetch(url, timeout=20.0)
                    if response.status_code == 200:
                        # Extract text content from the page
                        text_content = self._extract_text_from_html(response.text)
                        if text_content and len(text_content.strip()) > 50:
                            # Apply domain relevance pre-filter to skip off-topic sources early.
                            # ``_is_source_domain_relevant`` lives on ConstraintAnalyzer, not on
                            # DiscoveryPipeline; create a temporary analyzer instance.
                            from core.orchestrator_core import ConstraintAnalyzer
                            temp_analyzer = ConstraintAnalyzer(self.config)
                            if temp_analyzer._is_source_domain_relevant(
                                {
                                    "url": url,
                                    "title": self._extract_title_from_html(response.text) or self._clean_url_title(url),
                                    "description": text_content[:500] + ("..." if len(text_content) > 500 else "")
                                },
                                target_domain
                            ):
                                source = DiscoveredSource(
                                    url=url,
                                    source_type=SourceType.WEB_PAGE,
                                    title=self._extract_title_from_html(response.text) or self._clean_url_title(url),
                                    description=text_content[:500] + ("..." if len(text_content) > 500 else ""),
                                    metadata={
                                        "explicit_source": True,
                                        "source_type": "explicit_url",
                                        "content_length": len(text_content)
                                    }
                                )
                                # Score the source
                                source.quality_score = score_source(source)
                                yield source
                            else:
                                self._LOG.debug(f"Skipping off-topic explicit source URL {url}")
                except Exception as e:
                    self._LOG.warning(f"Failed to fetch explicit source URL {url}: {e}")
                    continue

        source_types = source_types or [
            # ── Primary dataset repositories (high-quality sources) ─────
            SourceType.HF_DATASET,           # HuggingFace Datasets
            SourceType.KAGGLE_DATASET,       # Kaggle
            SourceType.OPENML,               # OpenML
            SourceType.ZENODO,               # Zenodo
            SourceType.PAPERS_WITH_CODE,     # Papers with Code datasets
            SourceType.AWS_OPEN_DATA,        # AWS Open Data Registry
            SourceType.SNAP,                 # Stanford SNAP
            SourceType.GOVERNMENT_DATA,      # Data.gov & government portals
            SourceType.DATAPORTALS_ORG,      # DataPortals.org aggregator
            SourceType.DATAHUB_IO,           # DataHub.io
            SourceType.FIGSHARE,             # Figshare
            SourceType.DIRECT_DATASET,       # UCI & other academic portals
            SourceType.GOOGLE_DATASET_SEARCH,# Google Dataset Search
            # ── Secondary sources ───────────────────────────────────────
            SourceType.ARXIV_PAPER,          # ArXiv (research papers)
            SourceType.WEB_PAGE,             # General web (filtered)
            SourceType.PDF_DOCUMENT,         # PDF documents
            SourceType.WIKIPEDIA,            # Wikipedia
            SourceType.GITHUB_REPO,          # GitHub repos (dataset collections)
        ]

        # ── 3-tier query sanitisation ────────────────────────────────────
        extraction = await self._sanitize_query(query)
        self._LOG.info(
            "DISCOVERY query extraction: method=%s model=%s confidence=%.2f "
            "extracted=%r for raw prompt of %d chars",
            extraction.method, extraction.model, extraction.confidence,
            extraction.query, len(query),
        )
        sanitised_query = extraction.query

        # ── Defensively sanitise target_domain ──────────────────────────
        _DIRTY_MARKERS = ("Dataset Name:", "Goal:", "Domains:", "Target Size:")
        _is_dirty = (
            any(m in target_domain for m in _DIRTY_MARKERS)
            or len(target_domain) > _MAX_QUERY_CHARS
            or "\n" in target_domain
        )
        if _is_dirty:
            self._LOG.warning(
                "Target domain looks like raw prompt (len=%d, dirty=%s). "
                "Replacing with sanitised query (len=%d).",
                len(target_domain),
                any(m in target_domain for m in _DIRTY_MARKERS),
                len(sanitised_query),
            )
            target_domain = sanitised_query
        else:
            target_domain = _trim_query(target_domain)

        # Generate multiple search queries
        queries = self._generate_search_queries(sanitised_query, target_domain)

        # ── Phase 1: Check cache first ──────────────────────────────────
        for st in source_types:
            cached = await self._cache.get(
                sanitised_query, target_domain, st.value,
            )
            if cached:
                self._LOG.debug(
                    "Cache HIT for %s/%s → %d sources",
                    sanitised_query[:40], st.value, len(cached),
                )
                for src in cached:
                    if src.url not in self._discovered_urls:
                        src.quality_score = score_source(src)
                        self._discovered_urls.add(src.url)
                        yield src

        # ── Phase 2: API discovery with rate-limited concurrency ────────
        tasks = []
        for q in queries[:8]:  # Limit queries to avoid explosion
            for source_type in source_types:
                tasks.append(self._discover_source_type(q, target_domain, source_type))

        # Execute with semaphore-bounded concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_sources: list[DiscoveredSource] = []
        for result in results:
            if isinstance(result, list):
                all_sources.extend(result)

        # ── Phase 3: Score & filter ─────────────────────────────────────
        for src in all_sources:
            src.quality_score = score_source(src)

        # Sort by quality score (best first) and filter below threshold
        all_sources.sort(key=lambda s: s.quality_score, reverse=True)
        all_sources = [
            s for s in all_sources
            if s.quality_score >= self._quality_filter_threshold
        ]

        # ── Phase 4: Health check (verify URLs resolve) ─────────────────
        if self._health_check_enabled and all_sources:
            healthy, dead = await health_check_urls(
                all_sources,
                timeout=self._health_check_timeout,
            )
            self._LOG.info(
                "Health check: %d/%d alive, %d dead",
                len(healthy), len(all_sources), len(dead),
            )
            all_sources = healthy

        # ── Phase 5: Cache & yield ──────────────────────────────────────
        # Group by source_type for caching
        grouped: dict[str, list[DiscoveredSource]] = {}
        for src in all_sources:
            grouped.setdefault(src.source_type.value, []).append(src)

        for st_val, src_list in grouped.items():
            await self._cache.set(
                sanitised_query, target_domain, st_val, src_list,
            )

        # Yield deduplicated, ranked results
        yielded = 0
        for src in all_sources:
            if src.url not in self._discovered_urls:
                self._discovered_urls.add(src.url)
                yield src
                yielded += 1
                if yielded >= self.max_results:
                    break

    async def _discover_source_type(
        self,
        query: str,
        target_domain: str,
        source_type: SourceType
    ) -> list[DiscoveredSource]:
        """Discover from a specific source type."""
        try:
            if source_type == SourceType.WEB_PAGE:
                return await self._discover_web_enhanced(query, target_domain)
            # ── Primary dataset repositories ──────────────────
            elif source_type == SourceType.HF_DATASET:
                return await self._discover_huggingface(query, target_domain)
            elif source_type == SourceType.KAGGLE_DATASET:
                return await self._discover_kaggle(query, target_domain)
            elif source_type == SourceType.OPENML:
                return await self._discover_openml(query, target_domain)
            elif source_type == SourceType.ZENODO:
                return await self._discover_zenodo(query, target_domain)
            elif source_type == SourceType.PAPERS_WITH_CODE:
                return await self._discover_papers_with_code(query, target_domain)
            elif source_type == SourceType.AWS_OPEN_DATA:
                return await self._discover_aws_open_data(query, target_domain)
            elif source_type == SourceType.SNAP:
                return await self._discover_snap(query, target_domain)
            elif source_type == SourceType.GOVERNMENT_DATA:
                return await self._discover_government_data(query, target_domain)
            elif source_type == SourceType.DATAPORTALS_ORG:
                return await self._discover_dataportals(query, target_domain)
            elif source_type == SourceType.DATAHUB_IO:
                return await self._discover_datahub(query, target_domain)
            elif source_type == SourceType.FIGSHARE:
                return await self._discover_figshare(query, target_domain)
            elif source_type == SourceType.GOOGLE_DATASET_SEARCH:
                return await self._discover_google_dataset_search(query, target_domain)
            elif source_type == SourceType.DIRECT_DATASET:
                return await self._discover_dataset_portals(query, target_domain)
            # ── Secondary sources ─────────────────────────────
            elif source_type == SourceType.GITHUB_REPO:
                return await self._discover_github_repos(query, target_domain)
            elif source_type == SourceType.GITHUB_FILE:
                return await self._discover_github_code(query, target_domain)
            elif source_type == SourceType.ARXIV_PAPER:
                return await self._discover_arxiv(query, target_domain)
            elif source_type == SourceType.STACKOVERFLOW:
                return await self._discover_stackoverflow(query, target_domain)
            elif source_type == SourceType.WIKIPEDIA:
                return await self._discover_wikipedia(query, target_domain)
            elif source_type == SourceType.PDF_DOCUMENT:
                return await self._discover_pdfs(query, target_domain)
            elif source_type == SourceType.HACKERNEWS:
                return await self._discover_hackernews(query, target_domain)
            elif source_type == SourceType.SEMANTIC_SCHOLAR:
                return await self._discover_semantic_scholar(query, target_domain)
            elif source_type == SourceType.PUBMED:
                return await self._discover_pubmed(query, target_domain)
        except Exception as e:
            self._LOG.warning(f"Discovery error for {source_type}: {e}")

        return []

    def _generate_search_queries(self, query: str, target_domain: str) -> list[str]:
        """Generate diverse search queries for comprehensive coverage."""
        # ── Secondary safety guard: strip any leaked instruction headers ────
        query = self._strip_instruction_headers(query)
        target_domain = self._strip_instruction_headers(target_domain)

        # ── Avoid self-concatenation when target_domain == query ───────────
        if target_domain.strip() == query.strip():
            combined = query
        else:
            combined = f"{query} {target_domain}".strip()

        base_queries = [
            query,
            combined,
            f"{query} machine learning",
            f"{query} training data",
            f"{query} dataset",
        ]

        # Trim each base query then append suffixes
        seen: set[str] = set()
        result: list[str] = []
        suffixes = [
            "benchmark", "examples", "raw data", "API",
            "documentation", "tutorial", "research", "github",
        ]

        for q in base_queries:
            q = _trim_query(q)  # caps at _MAX_QUERY_CHARS
            if q not in seen:
                seen.add(q)
                result.append(q)
            for suffix in suffixes:
                variant = _trim_query(f"{q} {suffix}")
                if variant not in seen:
                    seen.add(variant)
                    result.append(variant)

        return result[:20]

    async def _discover_web_enhanced(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Enhanced web discovery with multiple search engines."""
        sources = []

        # DuckDuckGo search
        sources.extend(await self._search_duckduckgo(query))
        await asyncio.sleep(1 / self.rate_limit)

        # Try Google if API key available
        if self.google_search_key or self.serpapi_key:
            sources.extend(await self._search_google_api(query))
            await asyncio.sleep(1 / self.rate_limit)

        # Brave Search
        if self.brave_search_key:
            sources.extend(await self._search_brave(query))
            await asyncio.sleep(1 / self.rate_limit)

        return sources[:self.max_per_source]

    async def _search_duckduckgo(self, query: str) -> list[DiscoveredSource]:
        """Search with DDG HTML → DDG Lite fallback (rate-limited)."""
        sources = []

        DDG_HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # DDG HTML Attempt
        try:
            await asyncio.sleep(random.uniform(1.0, 3.0))
            async with self._rate_limiter.acquire("https://duckduckgo.com/"):
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True, headers=DDG_HEADERS) as client:
                    url = f"https://duckduckgo.com/html/?q={quote(query)}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        html = resp.text
                        urls = re.findall(r'href="(https?://[^"&]+)"', html)
                        urls = list(set(urls))  # Deduplicate
                        for url in urls[:30]:
                            if self._is_domain_allowed(url) and url not in self._discovered_urls:
                                title = self._clean_url_title(url)
                                sources.append(DiscoveredSource(
                                    url=url,
                                    source_type=SourceType.WEB_PAGE,
                                    title=title,
                                    description=f"Web result for: {query}",
                                    metadata={"search_engine": "duckduckgo", "query": query}
                                ))
                        if sources:
                            return sources
        except Exception as e:
            self._LOG.debug(f"DDG HTML failed: {e}")

        # DDG Lite Attempt
        try:
            async with self._rate_limiter.acquire("https://lite.duckduckgo.com/"):
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True, headers=DDG_HEADERS) as client:
                    url = f"https://lite.duckduckgo.com/lite/?q={quote(query)}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        html = resp.text
                        urls = re.findall(r'<a class="result-link" href="([^"]+)"', html)
                        urls = list(set(urls))  # Deduplicate
                        for url in urls[:30]:
                            if self._is_domain_allowed(url) and url not in self._discovered_urls:
                                title = self._clean_url_title(url)
                                sources.append(DiscoveredSource(
                                    url=url,
                                    source_type=SourceType.WEB_PAGE,
                                    title=title,
                                    description=f"Web result for: {query}",
                                    metadata={"search_engine": "duckduckgo-lite", "query": query}
                                ))
                        if sources:
                            return sources
        except Exception as e:
            self._LOG.debug(f"DDG Lite failed: {e}")

        # Brave Search API Fallback
        brave_key = os.getenv("BRAVE_API_KEY")
        if brave_key:
            try:
                async with self._rate_limiter.acquire("https://api.search.brave.com/"):
                    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                        url = f"https://api.search.brave.com/res/v1/web/search?q={quote(query)}&count=20"
                        resp = await client.get(
                            url,
                            headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            for item in data.get("web", {}).get("results", [])[:20]:
                                url = item.get("url", "")
                                if self._is_domain_allowed(url) and url not in self._discovered_urls:
                                    sources.append(DiscoveredSource(
                                        url=url,
                                        source_type=SourceType.WEB_PAGE,
                                        title=item.get("title", ""),
                                        description=item.get("description", ""),
                                        metadata={"search_engine": "brave", "query": query}
                                    ))
                            if sources:
                                return sources
            except Exception as e:
                self._LOG.warning(f"Brave Search fallback failed: {e}")

        return sources

    async def _search_google_api(self, query: str) -> list[DiscoveredSource]:
        """Search using Google Custom Search API or SerpAPI with rate limiting."""
        sources = []

        try:
            # Try SerpAPI first
            if self.serpapi_key:
                response = await self._fetch(
                    "https://serpapi.com/search",
                    params={
                        "q": query,
                        "api_key": self.serpapi_key,
                        "engine": "google"
                    },
                )
            elif self.google_search_key:
                response = await self._fetch(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "q": query,
                        "key": self.google_search_key,
                        "cx": self.config.get("google_cx", "")
                    },
                )
            else:
                return sources

            if response.status_code == 200:
                data = response.json()
                results = data.get("organic_results", []) or data.get("items", [])

                for item in results[:20]:
                    url = item.get("link", "")
                    if self._is_domain_allowed(url):
                        sources.append(DiscoveredSource(
                            url=url,
                            source_type=SourceType.WEB_PAGE,
                            title=item.get("title", ""),
                            description=item.get("snippet", ""),
                            metadata={
                                "search_engine": "google",
                                "query": query,
                                "display_link": item.get("displayLink", ""),
                            },
                        ))

        except Exception as e:
            self._LOG.warning(f"Google search error: {e}")

        return sources

    async def _search_brave(self, query: str) -> list[DiscoveredSource]:
        """Search using Brave Search API with rate limiting."""
        sources = []

        try:
            response = await self._fetch(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.brave_search_key
                },
            )

            if response.status_code == 200:
                data = response.json()

                for item in data.get("web", {}).get("results", [])[:20]:
                    url = item.get("url", "")
                    if self._is_domain_allowed(url):
                        sources.append(DiscoveredSource(
                            url=url,
                            source_type=SourceType.WEB_PAGE,
                            title=item.get("title", ""),
                            description=item.get("description", ""),
                            metadata={"search_engine": "brave", "query": query},
                        ))

        except Exception as e:
            self._LOG.warning(f"Brave search error: {e}")

        return sources

    def _github_q(self, query: str, target_domain: str, suffix: str = "") -> str:
        """Build a GitHub search `q` string capped at 256 chars."""
        base = f"{query} {target_domain}".strip()
        full = f"{base} {suffix}".strip() if suffix else base
        if len(full) > 250:
            # truncate query part, leave suffix intact
            base_max = 250 - len(suffix) - 1 if suffix else 250
            full = f"{base[:base_max]} {suffix}".strip() if suffix else base[:250]
        return full

    async def _discover_github_repos(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search GitHub for repositories."""
        sources = []

        try:
            await asyncio.sleep(random.uniform(1.0, 5.0))
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                headers = {"User-Agent": "AI-Dataset-Engineer/1.0"}
                if self.github_token:
                    headers["Authorization"] = f"token {self.github_token}"

                # Search for repos — cap q length to avoid GitHub 422
                q = self._github_q(query, target_domain, "in:name,description,readme")
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": q,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 30
                    },
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()

                    for item in data.get("items", [])[:20]:
                        repo_url = item.get("html_url", "")
                        full_name = item.get("full_name", "")

                        sources.append(DiscoveredSource(
                            url=repo_url,
                            source_type=SourceType.GITHUB_REPO,
                            title=item.get("name", ""),
                            description=item.get("description"),
                            author=item.get("owner", {}).get("login"),
                            license=item.get("license", {}).get("spdx_id") if item.get("license") else None,
                            stars=item.get("stargazers_count", 0),
                            metadata={
                                "stars": item.get("stargazers_count", 0),
                                "language": item.get("language"),
                                "topics": item.get("topics", []),
                                "forks": item.get("forks_count", 0),
                                "readme_url": f"https://raw.githubusercontent.com/{full_name}/HEAD/README.md"
                            }
                        ))

        except Exception as e:
            self._LOG.warning(f"GitHub repo search error: {e}")

        return sources

    async def _discover_github_code(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search GitHub for code files."""
        sources = []

        try:
            await asyncio.sleep(random.uniform(2.0, 6.0))
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                headers = {"User-Agent": "AI-Dataset-Engineer/1.0"}
                if self.github_token:
                    headers["Authorization"] = f"token {self.github_token}"

                # Search for code — cap q length to avoid GitHub 422
                q = self._github_q(query, target_domain)
                response = await client.get(
                    "https://api.github.com/search/code",
                    params={
                        "q": q,
                        "sort": "indexed",
                        "order": "desc",
                        "per_page": 30
                    },
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()

                    for item in data.get("items", [])[:20]:
                        html_url = item.get("html_url", "")
                        repo = item.get("repository", {})

                        sources.append(DiscoveredSource(
                            url=html_url,
                            source_type=SourceType.GITHUB_FILE,
                            title=item.get("name", ""),
                            description=f"Code file: {item.get('path', '')}",
                            author=repo.get("full_name", ""),
                            metadata={
                                "path": item.get("path", ""),
                                "sha": item.get("sha", ""),
                                "repo": repo.get("full_name", ""),
                                "raw_url": item.get("url", "").replace("api.github.com/repos", "raw.githubusercontent.com").replace("/contents/", "/HEAD/")
                            },
                            raw_content_url=item.get("url", "")
                        ))

        except Exception as e:
            self._LOG.warning(f"GitHub code search error: {e}")

        return sources

    async def _discover_huggingface(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search HuggingFace for datasets and models with rate limiting."""
        sources = []

        try:
            # Search datasets
            response = await self._fetch(
                "https://huggingface.co/api/datasets",
                params={"search": query, "sort": "downloads", "direction": -1},
            )

            if response.status_code == 200:
                data = response.json()
                for item in data[:15]:
                    sources.append(DiscoveredSource(
                        url=f"https://huggingface.co/datasets/{item.get('id', '')}",
                        source_type=SourceType.HF_DATASET,
                        title=item.get("id", ""),
                        description=item.get("description", ""),
                        author=item.get("author", ""),
                        metadata={
                            "downloads": item.get("downloads", 0),
                            "likes": item.get("likes", 0),
                            "tags": item.get("tags", []),
                            "id": item.get("id", ""),
                        },
                    ))

            # Also search models
            model_response = await self._fetch(
                "https://huggingface.co/api/models",
                params={"search": query, "sort": "downloads", "direction": -1},
            )

            if model_response.status_code == 200:
                models = model_response.json()
                for item in models[:10]:
                    sources.append(DiscoveredSource(
                        url=f"https://huggingface.co/{item.get('id', '')}",
                        source_type=SourceType.WEB_PAGE,
                        title=item.get("id", ""),
                        description=f"Model: {item.get('pipeline_tag', '')}",
                        metadata={
                            "downloads": item.get("downloads", 0),
                            "likes": item.get("likes", 0),
                            "model_type": item.get("pipeline_tag", ""),
                        },
                    ))

        except Exception as e:
            self._LOG.warning(f"HuggingFace search error: {e}")

        return sources

    async def _discover_huggingface_datasets(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search HuggingFace datasets with SDK-powered content inspection.

        Uses the `datasets` library to sample actual rows, verify configs,
        and estimate row counts when the SDK is available.  Falls back to
        the REST API with metadata-only results otherwise.
        """
        sources = []

        # ── Tier 1: Full API search ──────────────────────────────────
        try:
            hf_url = "https://huggingface.co/api/datasets"
            async with self._rate_limiter.acquire(hf_url):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0),
                ) as client:
                    for q in [query, f"{query} {target_domain}"]:
                        response = await client.get(
                            hf_url,
                            params={
                                "search": q,
                                "sort": "downloads",
                                "direction": -1,
                                "limit": 20,
                            },
                        )
                        if response.status_code != 200:
                            continue
                        data = response.json()
                        for item in data:
                            ds_id = item.get("id", "")
                            if ds_id in [s.title for s in sources]:
                                continue
                            src = DiscoveredSource(
                                url=f"https://huggingface.co/datasets/{ds_id}",
                                source_type=SourceType.HF_DATASET,
                                title=ds_id,
                                description=item.get("description", ""),
                                author=item.get("author", ""),
                                metadata={
                                    "downloads": item.get("downloads", 0),
                                    "likes": item.get("likes", 0),
                                    "tags": item.get("tags", []),
                                    "siblings": len(
                                        item.get("siblings", [])
                                    ),
                                },
                            )
                            sources.append(src)
        except Exception as e:
            self._LOG.warning(f"HuggingFace datasets search error: {e}")

        # ── Tier 2: SDK content inspection (top 5 results) ────────────
        for src in sources[:5]:
            await self._inspect_hf_dataset_sdk(src)

        return sources

    async def _inspect_hf_dataset_sdk(
        self, source: DiscoveredSource,
    ) -> None:
        """Use the HuggingFace `datasets` SDK to inspect dataset content.

        Populates source.metadata with:
          - num_rows, num_columns, columns (first config only)
          - sample_rows (first 5 rows as serialized JSON)
          - sdk_accessible: bool
          - sdk_error: str (on failure)
        """
        try:
            from datasets import get_dataset_config_names, load_dataset
        except ImportError:
            source.metadata["sdk_accessible"] = False
            source.metadata["sdk_error"] = "datasets library not installed"
            return

        ds_id = source.metadata.get("id") or source.title
        if not ds_id:
            return

        try:
            # ── Discover configs ─────────────────────────────────────
            configs = get_dataset_config_names(ds_id)
            config = configs[0] if configs else "default"
            source.metadata["configs"] = configs
        except Exception as e:
            source.metadata["sdk_accessible"] = False
            source.metadata["sdk_error"] = f"config_fetch: {str(e)[:120]}"
            return

        try:
            # ── Load streaming slice ─────────────────────────────────
            ds = load_dataset(
                ds_id,
                config,
                split="train",
                streaming=True,
                trust_remote_code=True,
            )
            head = list(ds.take(5))
            if head:
                num_cols = (
                    len(head[0].keys())
                    if isinstance(head[0], dict)
                    else "scalar"
                )
                source.metadata["sample_rows"] = [
                    {k: str(v)[:200] for k, v in row.items()}
                    if isinstance(row, dict) else str(row)[:200]
                    for row in head
                ]
                source.metadata["columns"] = (
                    list(head[0].keys())
                    if isinstance(head[0], dict) else ["value"]
                )
                source.metadata["num_columns"] = num_cols
            else:
                source.metadata["columns"] = []
                source.metadata["num_columns"] = 0

            # ── Estimate row count (from info if available) ───────────
            try:
                ds_info = ds.info
                if ds_info and hasattr(ds_info, "splits"):
                    for split_name, split_info in ds_info.splits.items():
                        if split_name == "train" or "train" in split_name:
                            source.metadata["num_rows"] = (
                                split_info.num_examples
                            )
                            source.size_bytes = (
                                split_info.num_bytes
                                if hasattr(split_info, "num_bytes") else None
                            )
                            break
            except Exception:
                pass

            source.metadata["sdk_accessible"] = True
            source.metadata["sdk_config_used"] = config

        except Exception as e:
            source.metadata["sdk_accessible"] = False
            source.metadata["sdk_error"] = f"load_failed: {str(e)[:120]}"

    async def _discover_kaggle(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Kaggle for datasets using the official kagglehub SDK.

        Falls back to the undocumented API endpoint if kagglehub is not
        installed, then to web search as a last resort.
        """
        sources = []

        # ── Tier 1: Official kagglehub SDK ────────────────────────────
        try:
            import kagglehub
            # kagglehub provides a native search, but it's limited.
            # We search with the query and also browse by tag when possible.
            results = kagglehub.search_datasets(query)
            for item in results[:15]:
                ref = getattr(item, "ref", "") or item.get("ref", "")
                title = getattr(item, "title", "") or item.get("title", "")
                desc = getattr(item, "subtitle", "") or item.get("subtitle", "")
                if not ref:
                    continue
                sources.append(DiscoveredSource(
                    url=f"https://kaggle.com/datasets/{ref}",
                    source_type=SourceType.KAGGLE_DATASET,
                    title=title,
                    description=desc,
                    author=getattr(item, "ownerName", None) or item.get("ownerName"),
                    size_bytes=(
                        int(item.get("totalBytes", 0))
                        if item.get("totalBytes") else None
                    ),
                    metadata={
                        "downloads": (
                            getattr(item, "downloadCount", 0)
                            or item.get("downloadCount", 0)
                        ),
                        "size": getattr(item, "size", "") or item.get("size", ""),
                        "tags": getattr(item, "tags", []) or item.get("tags", []),
                    },
                ))
            if sources:
                return sources
        except ImportError:
            self._LOG.debug("kagglehub not installed; falling back to API")
        except Exception as e:
            self._LOG.warning(f"kagglehub search error: {e}")

        # ── Tier 2: Undocumented REST API ──────────────────────────────
        try:
            kaggle_url = (
                "https://www.kaggle.com/api/i/documentation."
                "DatasetsService/DatasetsList"
            )
            async with self._rate_limiter.acquire(kaggle_url):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0),
                ) as client:
                    response = await client.get(
                        kaggle_url,
                        params={
                            "Query": query,
                            "SortBy": "DATASET_SORT_BY_DOWNLOADS",
                            "PageSize": 20,
                        },
                    )
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("datasets", [])[:15]:
                            sources.append(DiscoveredSource(
                                url=f"https://kaggle.com/datasets/{item.get('ref', '')}",
                                source_type=SourceType.KAGGLE_DATASET,
                                title=item.get("title", ""),
                                description=item.get("description", ""),
                                author=item.get("ownerUsername", ""),
                                metadata={
                                    "downloads": item.get("downloadCount", 0),
                                    "size": item.get("size", ""),
                                    "tags": item.get("tags", []),
                                },
                            ))
        except Exception as e:
            self._LOG.warning(f"Kaggle API search error: {e}")

        # ── Tier 3: Fallback web search ────────────────────────────────
        if not sources:
            sources.extend(await self._search_duckduckgo(
                f"site:kaggle.com {query} {target_domain} dataset",
            ))

        return sources

    async def _discover_arxiv(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search ArXiv for papers with rate limiting."""
        sources = []

        try:
            for search_query in [query, f"{query} {target_domain}"]:
                response = await self._fetch(
                    "http://export.arxiv.org/api/query",
                    params={
                        "search_query": f"all:{search_query}",
                        "start": 0,
                        "max_results": 15,
                        "sortBy": "relevance",
                    },
                    timeout=45.0,  # ArXiv can be slow
                    max_retries=2,
                )

                if response.status_code == 200:
                    xml = response.text
                    entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)

                    for entry in entries[:10]:
                        title_match = re.search(r'<title>(.*?)</title>', entry)
                        url_match = re.search(r'<id>(.*?)</id>', entry)
                        summary_match = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                        author_matches = re.findall(r'<name>(.*?)</name>', entry)
                        date_match = re.search(r'<published>(.*?)</published>', entry)
                        pdf_match = re.search(r'<link.*?title="pdf".*?href="(.*?)"', entry)

                        if title_match and url_match:
                            sources.append(DiscoveredSource(
                                url=url_match.group(1),
                                source_type=SourceType.ARXIV_PAPER,
                                title=title_match.group(1).strip().replace("\n", " "),
                                description=summary_match.group(1).strip()[:500] if summary_match else None,
                                author=", ".join(author_matches[:3]) if author_matches else None,
                                date=date_match.group(1)[:10] if date_match else None,
                                license="arXiv",
                                metadata={
                                    "arxiv_id": self._extract_arxiv_id(url_match.group(1)),
                                    "pdf_url": pdf_match.group(1) if pdf_match else None,
                                },
                            ))

        except Exception as e:
            self._LOG.warning(f"ArXiv search error: {e}")

        return sources

    async def _discover_stackoverflow(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Stack Overflow for Q&A with rate limiting."""
        sources = []

        try:
            response = await self._fetch(
                "https://api.stackexchange.com/2.3/search/excerpts",
                params={
                    "order": "desc",
                    "sort": "relevance",
                    "q": f"{query} {target_domain}",
                    "site": "stackoverflow",
                    "filter": "withbody",
                    "pagesize": 20,
                },
            )

            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", [])[:15]:
                    sources.append(DiscoveredSource(
                        url=item.get("link", ""),
                        source_type=SourceType.STACKOVERFLOW,
                        title=item.get("title", ""),
                        description=item.get("excerpt", "")[:300],
                        metadata={
                            "score": item.get("score", 0),
                            "answer_count": item.get("answer_count", 0),
                            "is_answered": item.get("is_answered", False),
                            "tags": item.get("tags", []),
                        },
                    ))

        except Exception as e:
            self._LOG.warning(f"StackOverflow search error: {e}")

        return sources

    async def _discover_wikipedia(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Wikipedia for articles with rate limiting."""
        sources = []

        try:
            for search_query in [query, f"{query} {target_domain}"]:
                response = await self._fetch(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": search_query,
                        "srlimit": 15,
                        "format": "json",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("query", {}).get("search", [])[:10]:
                        sources.append(DiscoveredSource(
                            url=f"https://en.wikipedia.org/wiki/{quote(item.get('title', ''))}",
                            source_type=SourceType.WIKIPEDIA,
                            title=item.get("title", ""),
                            description=item.get("snippet", "").replace("<span class='searchmatch'>", "").replace("</span>", ""),
                            metadata={
                                "page_id": item.get("pageid", 0),
                                "word_count": item.get("wordcount", 0),
                                "timestamp": item.get("timestamp", ""),
                            },
                        ))

        except Exception as e:
            self._LOG.warning(f"Wikipedia search error: {e}")

        return sources

    async def _discover_pdfs(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search for PDF documents."""
        sources = []

        # Search specifically for PDFs
        pdf_queries = [
            f'filetype:pdf "{query}"',
            f'filetype:pdf "{query} {target_domain}"',
            f'"{query}" site:arxiv.org/pdf',
            f'"{query}" site:arxiv.org',
        ]

        for pq in pdf_queries:
            sources.extend(await self._search_duckduckgo(pq))
            await asyncio.sleep(0.5)

        # Also search Google Scholar for PDFs
        sources.extend(await self._search_duckduckgo(f'"{query}" filetype:pdf academic'))

        return sources[:20]

    async def _discover_hackernews(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Hacker News."""
        sources = []

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # Search via Algolia HN API
                response = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={
                        "query": f"{query} {target_domain}",
                        "tags": "story",
                        "numericFilters": "points>10"
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    for item in data.get("hits", [])[:15]:
                        sources.append(DiscoveredSource(
                            url=item.get("url", item.get("_highlightResult", {}).get("url", {}).get("value", "")),
                            source_type=SourceType.HACKERNEWS,
                            title=item.get("title", ""),
                            description=item.get("excerpt", item.get("_highlightResult", {}).get("story_text", {}).get("value", ""))[:300],
                            author=item.get("author", ""),
                            date=item.get("created_at", "")[:10],
                            metadata={
                                "points": item.get("points", 0),
                                "num_comments": item.get("num_comments", 0),
                                "object_id": item.get("objectID", "")
                            }
                        ))

        except Exception as e:
            self._LOG.warning(f"HackerNews search error: {e}")

        return sources

    async def _discover_dataset_portals(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search multiple open data portals via native APIs with web fallback.

        Covers: UCI ML Repository, Harvard Dataverse, World Bank, Internet
        Archive, and more — each queried via its API where available.
        """
        sources = []

        # ── UCI Machine Learning Repository ──────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # UCI recently added a JSON API
                resp = await client.get(
                    "https://archive.ics.uci.edu/api/datasets",
                    params={"search": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ds_list = (
                        data if isinstance(data, list)
                        else data.get("datasets", [])
                    )
                    for item in ds_list[:15]:
                        name = item.get("name", item.get("title", ""))
                        ds_id = item.get("id", item.get("slug", ""))
                        sources.append(DiscoveredSource(
                            url=(
                                f"https://archive.ics.uci.edu/dataset/{ds_id}"
                                if ds_id
                                else f"https://archive.ics.uci.edu/ml/datasets.php"
                            ),
                            source_type=SourceType.DATASET_REPO,
                            title=name,
                            description=(
                                item.get("description",
                                         item.get("abstract", "")) or ""
                            )[:400],
                            metadata={
                                "source": "UCI ML Repository",
                                "dataset_id": ds_id,
                                "instances": (
                                    item.get("instances")
                                    or item.get("num_instances")
                                ),
                                "features": (
                                    item.get("features")
                                    or item.get("num_features")
                                ),
                            },
                        ))
        except Exception as e:
            self._LOG.debug(f"UCI API error: {e}")

        # ── Harvard Dataverse ───────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://dataverse.harvard.edu/api/search",
                    params={
                        "q": query,
                        "type": "dataset",
                        "per_page": 15,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (
                        data.get("data", {}).get("items", [])
                    )[:15]:
                        sources.append(DiscoveredSource(
                            url=item.get("url", ""),
                            source_type=SourceType.DATASET_REPO,
                            title=item.get("name", ""),
                            description=(
                                (item.get("description", "") or "")[:400]
                            ),
                            metadata={
                                "source": "Harvard Dataverse",
                                "doi": item.get("global_id"),
                                "published_at": item.get("published_at"),
                            },
                        ))
        except Exception as e:
            self._LOG.debug(f"Harvard Dataverse API error: {e}")

        # ── World Bank Data ──────────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://api.worldbank.org/v2/indicator",
                    params={
                        "search": query,
                        "format": "json",
                        "per_page": 15,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    indicators = data[1] if len(data) > 1 else []
                    for item in indicators[:15]:
                        item_data = item if isinstance(item, dict) else {}
                        sources.append(DiscoveredSource(
                            url=(
                                f"https://data.worldbank.org/indicator/"
                                f"{item_data.get('id', '')}"
                            ),
                            source_type=SourceType.OPEN_DATA_PORTAL,
                            title=item_data.get("name", ""),
                            description=(
                                item_data.get("sourceNote", "") or ""
                            )[:400],
                            metadata={
                                "source": "World Bank",
                                "indicator_id": item_data.get("id"),
                            },
                        ))
        except Exception as e:
            self._LOG.debug(f"World Bank API error: {e}")

        # ── Internet Archive ─────────────────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://archive.org/advancedsearch.php",
                    params={
                        "q": f"{query} AND mediatype:(data OR texts)",
                        "fl": "identifier,title,description",
                        "output": "json",
                        "rows": 15,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    docs = data.get("response", {}).get("docs", [])
                    for doc in docs[:15]:
                        sources.append(DiscoveredSource(
                            url=(
                                f"https://archive.org/details/"
                                f"{doc.get('identifier', '')}"
                            ),
                            source_type=SourceType.DATASET_REPO,
                            title=(
                                doc.get("title")
                                or doc.get("identifier", "")
                            ),
                            description=(
                                (doc.get("description", "") or "")[:400]
                            ),
                            metadata={"source": "Internet Archive"},
                        ))
        except Exception as e:
            self._LOG.debug(f"Internet Archive API error: {e}")

        # ── Fallback: web search across remaining portals ─────────────────
        if not sources:
            portal_queries = [
                f"site:data.gov {query}",
                f"site:data.europa.eu {query}",
                f"site:archive.org/details {query} dataset",
                f"site:dataverse.harvard.edu {query}",
                f"site:data.worldbank.org {query}",
            ]
            for pq in portal_queries:
                sources.extend(await self._search_duckduckgo(pq))
                await asyncio.sleep(0.3)

        return sources[:20]

    # ────────────────────────────────────────────────────────────────────
    # New open data repository discovery methods
    # ────────────────────────────────────────────────────────────────────

    async def _discover_openml(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search OpenML for ML datasets via the REST API.

        OpenML (openml.org) is a curated repository of ML datasets with
        rich metadata, task definitions, and benchmark flows.  No API key
        is required for read access.

        API: GET https://www.openml.org/api/v1/json/data/list/{filters}
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # Try name search first, then description search
                for search_param in [f"data_name/{quote(query)}", f"data_tag/{quote(query)}"]:
                    try:
                        resp = await client.get(
                            f"https://www.openml.org/api/v1/json/{search_param}"
                        )
                        if resp.status_code != 200:
                            continue

                        data = resp.json()
                        datasets = data.get("data", {}).get("dataset", [])
                        # Normalise to list
                        if isinstance(datasets, dict):
                            datasets = [datasets]

                        for item in datasets[:20]:
                            did = item.get("did", "")
                            name = item.get("name", "")
                            if not did:
                                continue
                            sources.append(DiscoveredSource(
                                url=f"https://www.openml.org/search?type=data&id={did}",
                                source_type=SourceType.OPENML,
                                title=name,
                                description=(
                                    f"OpenML dataset (id={did}) — "
                                    f"features: {item.get('NumberOfFeatures', 'N/A')}, "
                                    f"instances: {item.get('NumberOfInstances', 'N/A')}"
                                ),
                                metadata={
                                    "openml_id": did,
                                    "features": item.get("NumberOfFeatures"),
                                    "instances": item.get("NumberOfInstances"),
                                    "version": item.get("version"),
                                    "status": item.get("status"),
                                    "format": item.get("format"),
                                },
                            ))
                    except Exception:
                        continue

        except Exception as e:
            self._LOG.warning(f"OpenML search error: {e}")

        return sources

    async def _discover_zenodo(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Zenodo for open research datasets.

        Zenodo (zenodo.org) is CERN's general-purpose open-access repository
        hosting datasets, software, and publications with DOIs.
        No API key required for read access.

        API: GET https://zenodo.org/api/records?q=<query>&type=dataset
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://zenodo.org/api/records",
                    params={
                        "q": query,
                        "size": 20,
                        "type": "dataset",
                        "access_right": "open",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for hit in data.get("hits", {}).get("hits", [])[:20]:
                        meta = hit.get("metadata", {})
                        source_url = (
                            hit.get("links", {}).get("html")
                            or f"https://zenodo.org/records/{hit.get('id', '')}"
                        )
                        sources.append(DiscoveredSource(
                            url=source_url,
                            source_type=SourceType.ZENODO,
                            title=meta.get("title", hit.get("id", "")),
                            description=(
                                (meta.get("description", "") or "")[:300]
                            ),
                            license=(
                                meta.get("license", {}).get("id", "")
                                if meta.get("license") else None
                            ),
                            metadata={
                                "doi": hit.get("doi"),
                                "zenodo_id": hit.get("id"),
                                "downloads": (
                                    hit.get("stats", {}).get("downloads", 0)
                                ),
                                "views": hit.get("stats", {}).get("views", 0),
                                "created": hit.get("created"),
                                "resource_type": meta.get("resource_type", {}).get("title"),
                            },
                        ))

        except Exception as e:
            self._LOG.warning(f"Zenodo search error: {e}")

        return sources

    async def _discover_papers_with_code(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Papers with Code for datasets linked to research papers.

        Papers with Code (paperswithcode.com) maps ML papers to datasets,
        code implementations, and benchmarks.  No API key is required.

        API: GET https://paperswithcode.com/api/v1/datasets/?q=<query>
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://paperswithcode.com/api/v1/datasets/",
                    params={"q": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (data.get("results") or [])[:20]:
                        sources.append(DiscoveredSource(
                            url=f"https://paperswithcode.com{item.get('url', '')}",
                            source_type=SourceType.PAPERS_WITH_CODE,
                            title=item.get("name", ""),
                            description=item.get("description", "")[:400],
                            metadata={
                                "pwc_id": item.get("id"),
                                "papers_count": item.get("n_papers", 0),
                                "is_reviewed": item.get("is_reviewed", False),
                            },
                        ))

        except Exception as e:
            self._LOG.warning(f"Papers with Code search error: {e}")

        return sources

    async def _discover_aws_open_data(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search the AWS Registry of Open Data.

        The Registry of Open Data on AWS (registry.opendata.aws) lists
        publicly-available datasets hosted on AWS.  The registry itself
        is a GitHub repo of YAML entries — we search via the registry's
        built-in search API and fall back to web search.
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # The AWS Open Data registry provides a searchable API
                resp = await client.get(
                    "https://opendata.aws/api/v1/datasets",
                    params={"search": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (data.get("datasets") or [])[:15]:
                        name = item.get("Name", "")
                        sources.append(DiscoveredSource(
                            url=(
                                f"https://registry.opendata.aws/{item.get('Name', '').lower().replace(' ', '-')}/"
                            ),
                            source_type=SourceType.AWS_OPEN_DATA,
                            title=name,
                            description=item.get("Description", "")[:400],
                            metadata={
                                "aws_name": name,
                                "managed_by": item.get("ManagedBy", ""),
                                "tags": item.get("Tags", []),
                                "license": item.get("License", ""),
                                "region": item.get("Region", ""),
                            },
                        ))
        except Exception:
            pass  # Fall through to web search fallback

        # Fallback: web search for AWS open data
        if not sources:
            sources = await self._search_duckduckgo(
                f"site:registry.opendata.aws {query}"
            )

        return sources[:20]

    async def _discover_snap(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search the Stanford Large Network Dataset Collection (SNAP).

        SNAP (snap.stanford.edu/data) hosts large-scale network/graph datasets
        for social network analysis, community detection, link prediction, etc.

        The site has a searchable listing page — we scrape the index and
        fall back to web search.
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # Scrape the index page which lists all datasets
                resp = await client.get("https://snap.stanford.edu/data/index.html")
                if resp.status_code == 200:
                    html = resp.text
                    # Extract dataset entries — pattern: <a href="data/<name>.html">Title</a>
                    dataset_links = re.findall(
                        r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>',
                        html, re.IGNORECASE,
                    )
                    query_lower = query.lower()
                    for href, title in dataset_links[:30]:
                        title_clean = title.strip()
                        href_clean = href.strip()
                        if not title_clean or not href_clean:
                            continue
                        # Filter relevance against query keywords
                        keywords = query_lower.split()
                        if not any(
                            kw in title_clean.lower()
                            or kw in href_clean.lower()
                            for kw in keywords
                        ):
                            continue
                        url = (
                            f"https://snap.stanford.edu/{href_clean}"
                            if not href_clean.startswith("http")
                            else href_clean
                        )
                        sources.append(DiscoveredSource(
                            url=url,
                            source_type=SourceType.SNAP,
                            title=title_clean,
                            description=f"SNAP network dataset: {title_clean}",
                            metadata={"source": "Stanford SNAP"},
                        ))
        except Exception as e:
            self._LOG.debug(f"SNAP direct scrape failed: {e}")

        # Fallback: web search
        if not sources:
            sources = await self._search_duckduckgo(
                f"site:snap.stanford.edu {query} network dataset"
            )

        return sources[:15]

    async def _discover_government_data(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search government open data portals (data.gov, EU, UK, etc.).

        Uses CKAN-based APIs where available (data.gov, data.gov.uk)
        and web search for other government portals.
        """
        sources = []

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # ── data.gov (CKAN API) ────────────────────────────
                try:
                    resp = await client.get(
                        "https://catalog.data.gov/api/3/action/package_search",
                        params={"q": f"{query} {target_domain}", "rows": 15},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in (
                            data.get("result", {}).get("results", [])
                        )[:15]:
                            item_title = item.get("title", "")
                            item_org = (
                                item.get("organization", {}) or {}
                            ).get("title", "")
                            sources.append(DiscoveredSource(
                                url=(
                                    f"https://catalog.data.gov/dataset/{item.get('name', '')}"
                                ),
                                source_type=SourceType.GOVERNMENT_DATA,
                                title=item_title,
                                description=(
                                    (item.get("notes", "") or "")[:400]
                                ),
                                metadata={
                                    "portal": "data.gov",
                                    "organization": item_org,
                                    "formats": [
                                        r.get("format", "")
                                        for r in item.get("resources", [])
                                    ],
                                    "categories": [
                                        g.get("display_name", "")
                                        for g in item.get("groups", [])
                                    ],
                                },
                            ))
                except Exception as e:
                    self._LOG.debug(f"data.gov API error: {e}")

                # ── data.europa.eu (SPARQL-based; fall to web) ────
                try:
                    resp = await client.get(
                        "https://data.europa.eu/api/hub/search/search",
                        params={"q": f"{query} {target_domain}", "limit": 10},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in (data.get("result", {}).get("results", []) or [])[:10]:
                            item_id = item.get("id", "")
                            sources.append(DiscoveredSource(
                                url=f"https://data.europa.eu/data/datasets/{item_id}",
                                source_type=SourceType.GOVERNMENT_DATA,
                                title=item.get("title", {}).get("en", item.get("title", "")),
                                description=(
                                    (item.get("description", {}) or {}).get("en", "")
                                    or item.get("description", "")
                                )[:400],
                                metadata={
                                    "portal": "data.europa.eu",
                                    "publisher": item.get("publisher", {}).get("name", ""),
                                    "dataset_id": item_id,
                                },
                            ))
                except Exception as e:
                    self._LOG.debug(f"data.europa.eu API error: {e}")

        except Exception as e:
            self._LOG.warning(f"Government data search error: {e}")

        # Fallback: web search across multiple government portals
        if not sources:
            for portal_query in [
                f"site:data.gov {query}",
                f"site:data.europa.eu {query}",
                f"site:data.gov.uk {query}",
                f"site:data.gouv.fr {query}",
            ]:
                sources.extend(await self._search_duckduckgo(portal_query))

        return sources[:20]

    async def _discover_dataportals(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search DataPortals.org — a meta-aggregator of over 600 open data portals.

        DataPortals.org catalogues open data portals globally.  We search
        via web search and their built-in search.
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://dataportals.org/api/data",
                    params={"q": query},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (data.get("data", []) or [])[:15]:
                        name = item.get("name", "")
                        sources.append(DiscoveredSource(
                            url=item.get("url", ""),
                            source_type=SourceType.DATAPORTALS_ORG,
                            title=name,
                            description=(
                                f"{name} — {item.get('country', '')}: "
                                f"{item.get('description', '')}"
                            )[:400],
                            metadata={
                                "country": item.get("country"),
                                "portal_type": item.get("type"),
                                "categories": item.get("categories", []),
                            },
                        ))
        except Exception:
            pass

        # Fallback: web search
        if not sources:
            for search_q in [
                f"site:dataportals.org {query}",
                f'"{query}" open data portal',
            ]:
                sources.extend(await self._search_duckduckgo(search_q))

        return sources[:15]

    async def _discover_datahub(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search DataHub.io for datasets via its CKAN API.

        DataHub.io is a community-driven data management platform based
        on CKAN, hosting thousands of curated datasets.
        No API key required.

        API: GET https://datahub.io/api/3/action/package_search?q=<query>
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    "https://datahub.io/api/3/action/package_search",
                    params={"q": query, "rows": 20},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (
                        data.get("result", {}).get("results", [])
                    )[:20]:
                        title = item.get("title", "")
                        description = (item.get("notes", "") or "")[:400]
                        sources.append(DiscoveredSource(
                            url=(
                                f"https://datahub.io/dataset/{item.get('name', '')}"
                            ),
                            source_type=SourceType.DATAHUB_IO,
                            title=title,
                            description=description,
                            license=item.get("license_title"),
                            metadata={
                                "organization": (
                                    item.get("organization", {}) or {}
                                ).get("title", ""),
                                "formats": [
                                    r.get("format", "")
                                    for r in item.get("resources", [])
                                ],
                                "tags": [
                                    t.get("name", "")
                                    for t in item.get("tags", [])
                                ],
                            },
                        ))
        except Exception as e:
            self._LOG.warning(f"DataHub.io search error: {e}")

        return sources

    async def _discover_figshare(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Figshare for research datasets.

        Figshare (figshare.com) is a repository where researchers can
        preserve and share research outputs including datasets, figures,
        and papers.  No API key is required for public search.

        API: POST https://api.figshare.com/v2/articles/search
        """
        sources = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.post(
                    "https://api.figshare.com/v2/articles/search",
                    json={"search_for": f'"{query} {target_domain}"'},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data[:15]:
                        sources.append(DiscoveredSource(
                            url=(
                                item.get("url_public_html")
                                or f"https://figshare.com/articles/{item.get('id', '')}"
                            ),
                            source_type=SourceType.FIGSHARE,
                            title=item.get("title", ""),
                            description=(
                                (item.get("description", "") or "")[:400]
                            ),
                            author=(
                                item.get("authors", [{}])[0].get("full_name", "")
                                if item.get("authors") else None
                            ),
                            license=item.get("license", {}).get("name"),
                            date=str(item.get("published_date", ""))[:10],
                            metadata={
                                "figshare_id": item.get("id"),
                                "doi": item.get("doi"),
                                "views": item.get("views", 0),
                                "downloads": item.get("downloads", 0),
                                "citations": item.get("citations", 0),
                                "defined_type": item.get("defined_type_name"),
                            },
                        ))
        except Exception as e:
            self._LOG.warning(f"Figshare search error: {e}")

        return sources

    # ────────────────────────────────────────────────────────────────────────
    # Google Dataset Search via schema.org crawling
    # ────────────────────────────────────────────────────────────────────────

    async def _discover_google_dataset_search(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Simulate Google Dataset Search by finding schema.org/Dataset pages.

        Google Dataset Search (datasetsearch.research.google.com) indexes
        web pages that embed schema.org/Dataset JSON-LD markup.  There is
        no public API, so we:
          1. Search for pages explicitly annotated as datasets
          2. Parse schema.org/Dataset JSON-LD from found pages
          3. Scrape known sitemaps of dataset-heavy domains
        """
        sources = []
        seen_ids: set[str] = set()

        # ── Web searches targeting dataset annotations ────────────────
        dataset_queries = [
            f'site:data.world "{query}" dataset',
            f'site:opendatascience.com "{query}" dataset',
            f'site:datadryad.org "{query}"',
            f'site:dataverse.harvard.edu "{query}"',
            f'site:researchgate.net "{query}" dataset',
            f'"{query}" "schema.org/Dataset"',
            f'"{query}" "application/ld+json" dataset',
        ]
        for dq in dataset_queries[:5]:
            results = await self._search_duckduckgo(dq)
            for src in results:
                src.source_type = SourceType.GOOGLE_DATASET_SEARCH
            sources.extend(results)

        # ── Fetch top candidates and parse schema.org JSON-LD ─────────
        seen_urls: set[str] = set()
        for src in sources[:10]:
            if src.url in seen_urls:
                continue
            seen_urls.add(src.url)
            try:
                page_sources = await self._parse_schema_org_dataset(src.url)
                for ps in page_sources:
                    ps.source_type = SourceType.GOOGLE_DATASET_SEARCH
                    uid = ps.metadata.get("schema_id", ps.url)
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        sources.append(ps)
            except Exception:
                continue

        return sources[:20]

    async def _parse_schema_org_dataset(
        self, url: str,
    ) -> list[DiscoveredSource]:
        """Fetch a URL and extract schema.org/Dataset JSON-LD markup.

        Returns 0..N DiscoveredSource objects, one per embedded dataset
        annotation found on the page.
        """
        results: list[DiscoveredSource] = []
        try:
            async with self._rate_limiter.acquire(url):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(15.0), follow_redirects=True,
                ) as client:
                    resp = await client.get(
                        url,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (compatible; RasoDataset-Agent/1.0"
                                "; +https://github.com/raso/dataset-engineer)"
                            ),
                        },
                    )
                    if resp.status_code != 200:
                        return results

                    html = resp.text

                    # Find all <script type="application/ld+json"> blocks
                    ld_blocks = re.findall(
                        r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
                        html, re.IGNORECASE | re.DOTALL,
                    )
                    for block in ld_blocks:
                        try:
                            parsed = json.loads(block.strip())
                        except json.JSONDecodeError:
                            continue

                        # Handle @graph (multiple items in a graph)
                        items = parsed.get("@graph", [parsed])
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            item_type = item.get("@type", "")
                            if "Dataset" not in item_type:
                                continue

                            name = item.get("name", item.get(
                                "alternateName", "",
                            ))
                            desc = item.get(
                                "description", item.get("abstract", ""),
                            )
                            schema_url = item.get("url", item.get(
                                "@id", url,
                            ))
                            date_pub = item.get("datePublished", "")
                            license_url = item.get("license", "")

                            results.append(DiscoveredSource(
                                url=schema_url,
                                source_type=SourceType.GOOGLE_DATASET_SEARCH,
                                title=name,
                                description=(desc or "")[:500],
                                license=license_url,
                                date=date_pub[:10] if date_pub else None,
                                metadata={
                                    "schema_id": item.get("@id", ""),
                                    "found_on": url,
                                },
                            ))
        except Exception:
            pass
        return results

    async def _discover_semantic_scholar(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search Semantic Scholar for papers."""
        sources = []

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": f"{query} {target_domain}",
                        "limit": 20,
                        "fields": "title,abstract,authors,year,venue,externalIds"
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    for item in (data.get("data") or [])[:15]:
                        if not item:
                            continue
                        external = (item.get("externalIds") or {})
                        arxiv_id = external.get("ArXiv", "")

                        sources.append(DiscoveredSource(
                            url=f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}",
                            source_type=SourceType.GOOGLE_SCHOLAR,
                            title=item.get("title", ""),
                            description=item.get("abstract", "")[:500],
                            author=", ".join([a.get("name", "") for a in item.get("authors", [])[:3]]),
                            date=str(item.get("year", "")),
                            metadata={
                                "venue": item.get("venue", ""),
                                "arxiv_id": arxiv_id,
                                "paper_id": item.get("paperId", "")
                            }
                        ))

        except Exception as e:
            self._LOG.warning(f"Semantic Scholar search error: {e}")

        return sources

    async def _discover_pubmed(
        self,
        query: str,
        target_domain: str
    ) -> list[DiscoveredSource]:
        """Search PubMed for medical/scientific papers."""
        sources = []

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                # Search E-utilities
                search_response = await client.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                    params={
                        "db": "pubmed",
                        "term": f"{query} {target_domain}",
                        "retmax": 20,
                        "sort": "relevance"
                    }
                )

                if search_response.status_code == 200:
                    xml = search_response.text
                    ids = re.findall(r'<Id>(.*?)</Id>', xml)

                    if ids:
                        id_list = ",".join(ids[:10])

                        # Fetch details
                        fetch_response = await client.get(
                            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                            params={
                                "db": "pubmed",
                                "id": id_list,
                                "retmode": "json"
                            }
                        )

                        if fetch_response.status_code == 200:
                            data = fetch_response.json()
                            results = data.get("result", {})

                            for uid in ids[:10]:
                                if uid in results and uid != "u":
                                    item = results[uid]
                                    sources.append(DiscoveredSource(
                                        url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                                        source_type=SourceType.PUBMED,
                                        title=item.get("title", ""),
                                        description=item.get("abstract", ""),
                                        author=item.get("authors", [{}])[0].get("name", "") if item.get("authors") else None,
                                        date=item.get("pubdate", "")[:4] if item.get("pubdate") else None,
                                        metadata={
                                            "journal": item.get("source", ""),
                                            "pmid": uid,
                                        }
                                    ))

        except Exception as e:
            self._LOG.warning(f"PubMed search error: {e}")

        return sources

    def _is_domain_allowed(self, url: str) -> bool:
        """Check if domain is allowed based on allowlist/blocklist."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if self.domain_blocklist:
                for blocked in self.domain_blocklist:
                    if blocked in domain:
                        return False

            if self.domain_allowlist:
                for allowed in self.domain_allowlist:
                    if allowed in domain:
                        return True
                return False

            return True
        except Exception:
            return False

    async def _extract_title_from_url(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Extract title from URL."""
        try:
            response = await client.get(url, timeout=5.0, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
                if title_match:
                    return title_match.group(1).strip()
        except Exception:
            pass
        return None

    def _clean_url_title(self, url: str) -> str:
        """Clean URL to create a title."""
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path.strip("/"))
            parts = path.split("/")
            return parts[-1] if parts else parsed.netloc
        except Exception:
            return url

    def _extract_arxiv_id(self, url: str) -> str | None:
        """Extract ArXiv ID from URL."""
        match = re.search(r'(\d+\.\d+)', url)
        return match.group(1) if match else None

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text content from HTML, removing scripts, styles, etc."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Break into lines and remove leading/trailing space
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into separate lines
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Remove blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text
        except Exception:
            # Fallback to regex-based extraction if BeautifulSoup not available
            # Remove script and style content
            html = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html, flags=re.DOTALL | re.IGNORECASE)

            # Remove HTML tags
            text = re.sub('<[^<]+?>', '', html)

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

    def _extract_title_from_html(self, html: str) -> str | None:
        """Extract title from HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                return title_tag.get_text().strip()
        except Exception:
            pass
        return None

    def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            client = httpx.Client(timeout=httpx.Timeout(10.0))
            try:
                response = client.get(robots_url)
                if response.status_code == 200:
                    return "/robots.txt" in response.text or "User-agent: *" in response.text
                return True
            finally:
                client.close()
        except Exception:
            return True

