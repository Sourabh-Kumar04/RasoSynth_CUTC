"""Enhanced content extraction pipeline for messy, diverse, multilingual data."""
import asyncio
import httpx
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Callable
from pathlib import Path
from datetime import datetime

from pipeline.discovery import SourceType
from core.provider_router import TaskType

logger = logging.getLogger(__name__)


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Validate URL is not targeting internal/private infrastructure.

    Returns (is_safe, reason).
    """
    try:
        parsed = httpx.URL(url)

        # Block non-HTTP(S)
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme: {parsed.scheme}"

        # Block local/loopback hostnames
        hostname = parsed.host.lower()
        blocked_hostnames = {
            "localhost", "127.0.0.1", "::1", "0.0.0.0",
            "metadata.google.internal",  # GCP
            "metadata.goog",              # GCP short
            "169.254.169.254",           # AWS/AWS-like metadata
            "metadata.azure.com",         # Azure
            "kubernetes.default",          # K8s in-cluster
            "kubernetes.default.svc",
        }
        # Check exact hostname
        if hostname in blocked_hostnames:
            return False, f"Blocked hostname: {hostname}"

        # Resolve to IP and check private ranges
        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, socktype, proto, _, sockaddr in addr_info:
                ip = sockaddr[0]
                if isinstance(ip, str):
                    ip = ipaddress.ip_address(ip)
                else:
                    ip = ipaddress.ip_address(ip)

                # Block private, loopback, link-local, multicast
                if (ip.is_private or ip.is_loopback or ip.is_link_local or
                        ip.is_multicast or ip.is_reserved):
                    return False, f"Resolved to unsafe IP: {ip}"
        except (socket.gaierror, OSError):
            # If resolution fails, allow the URL but log a warning
            logging.getLogger(__name__).warning(f"Could not resolve hostname {hostname} for SSRF check")

        # Block URLs with credentials or unusual ports
        if parsed.username or parsed.password:
            return False, "URL contains embedded credentials"

        return True, ""

    except Exception as e:
        return False, f"Invalid URL: {e}"




@dataclass
class ExtractedContent:
    """Extracted content with comprehensive metadata."""
    content: str
    content_type: str  # markdown, text, html, code, table, ocr, multilingual
    language: str | None = None
    languages_detected: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    url: str = ""
    confidence: float = 1.0
    quality_score: float = 0.0
    encoding: str | None = None
    structure_detected: dict | None = None
    extraction_warnings: list[str] = field(default_factory=list)
    normalized_content: str | None = None


@dataclass
class DocumentStructure:
    """Detected document structure."""
    sections: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    code_blocks: list[dict] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    lists: list[dict] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    metadata_fields: dict = field(default_factory=dict)


class ContentAnalyzer:
    """Analyzes content to determine structure, quality, and type."""

    def __init__(self, router=None):
        self.router = router

    async def analyze(self, raw_content: str, content_type: str = "text") -> dict:
        """Analyze content structure and quality."""
        analysis = {
            "content_type": content_type,
            "language": await self._detect_language(raw_content),
            "languages_mixed": await self._detect_language_mixing(raw_content),
            "structure": self._detect_structure(raw_content),
            "quality": await self._assess_quality(raw_content),
            "encoding": self._detect_encoding(raw_content),
            "has_ocr_artifacts": self._detect_ocr_artifacts(raw_content),
            "has_historical_spelling": self._detect_historical_spelling(raw_content),
        }

        return analysis

    async def _detect_language(self, text: str) -> str:
        """Detect primary language."""
        try:
            from langdetect import detect
            return detect(text[:1000])
        except Exception:
            return self._simple_language_detection(text)

    def _simple_language_detection(self, text: str) -> str:
        """Simple heuristic language detection."""
        text_lower = text.lower()[:500]

        lang_indicators = {
            "en": [" the ", " is ", " are ", " and ", " of ", " to "],
            "de": [" der ", " die ", " und ", " ist ", " von "],
            "fr": [" le ", " la ", " les ", " et ", " est ", " des "],
            "es": [" el ", " la ", " los ", " las ", " es ", " de "],
            "zh": ["的", "是", "在", "了", "和"],
            "ja": ["の", "は", "です", "が", "を"],
            "ko": ["의", "은", "가", "를", "에"],
            "ar": [" ال", " في", " من", " على", " is"],
            "ru": [" и ", " в ", " не ", " на ", " это"],
        }

        scores = {}
        for lang, indicators in lang_indicators.items():
            score = sum(1 for ind in indicators if ind in text_lower)
            scores[lang] = score

        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "unknown"

    async def _detect_language_mixing(self, text: str) -> list[str]:
        """Detect multiple languages in text (code-switching)."""
        languages = [await self._detect_language(text)]

        # Check for mixed scripts
        if re.search(r'[一-鿿]', text):
            if "zh" not in languages:
                languages.append("zh")
        if re.search(r'[぀-ヿ]', text):
            if "ja" not in languages:
                languages.append("ja")
        if re.search(r'[가-힯]', text):
            if "ko" not in languages:
                languages.append("ko")
        if re.search(r'[؀-ۿ]', text):
            if "ar" not in languages:
                languages.append("ar")
        if re.search(r'[Ѐ-ӿ]', text):
            if "ru" not in languages:
                languages.append("ru")

        return languages

    def _detect_structure(self, text: str) -> dict:
        """Detect document structure (headings, lists, tables, code)."""
        structure = {
            "sections": [],
            "tables": self._detect_tables(text),
            "code_blocks": self._detect_code_blocks(text),
            "headings": self._extract_headings(text),
            "lists": self._extract_lists(text),
            "has_hierarchical_structure": bool(self._extract_headings(text)),
        }
        return structure

    def _detect_tables(self, text: str) -> list[dict]:
        """Detect tabular data in text."""
        tables = []
        lines = text.split('\n')

        # CSV-like patterns
        for i, line in enumerate(lines):
            if '\t' in line or '|' in line or ',' in line:
                if self._looks_like_table_row(line):
                    tables.append({"line": i, "type": "structured"})

        # Markdown table format
        md_tables = re.findall(r'\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n)+', text)
        for md_table in md_tables:
            tables.append({"type": "markdown", "rows": len(md_table.split('\n'))})

        return tables[:10]  # Limit to 10 tables

    def _looks_like_table_row(self, line: str) -> bool:
        """Check if line looks like a table row."""
        separators = ['|', '\t', ',']
        count = sum(1 for s in separators if s in line)
        return count >= 2

    def _detect_code_blocks(self, text: str) -> list[dict]:
        """Detect code blocks in text."""
        blocks = []

        # Markdown code blocks
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        for lang, code in matches:
            blocks.append({"language": lang or "unknown", "lines": code.count('\n') + 1})

        # Inline code
        inline_count = len(re.findall(r'`[^`]+`', text))

        return blocks[:20]

    def _extract_headings(self, text: str) -> list[str]:
        """Extract headings from text."""
        headings = []

        # Markdown headings
        md_headings = re.findall(r'^#{1,6}\s+(.+)$', text, re.MULTILINE)
        headings.extend(md_headings)

        # HTML headings
        html_headings = re.findall(r'<h[1-6][^>]*>(.+?)</h[1-6]>', text, re.IGNORECASE)
        headings.extend(html_headings)

        return headings[:50]

    def _extract_lists(self, text: str) -> list[dict]:
        """Extract lists from text."""
        lists = []

        # Markdown lists
        md_lists = re.findall(r'^[\s]*[-*+]\s+(.+)$', text, re.MULTILINE)
        ordered = re.findall(r'^[\s]*\d+\.\s+(.+)$', text, re.MULTILINE)

        if md_lists:
            lists.append({"type": "unordered", "items": len(md_lists)})
        if ordered:
            lists.append({"type": "ordered", "items": len(ordered)})

        return lists[:10]

    async def _assess_quality(self, text: str) -> dict:
        """Assess content quality indicators."""
        quality = {
            "char_count": len(text),
            "word_count": len(text.split()),
            "sentence_count": len(re.split(r'[.!?]+', text)),
            "avg_word_length": sum(len(w) for w in text.split()) / max(len(text.split()), 1),
            "unique_word_ratio": len(set(text.lower().split())) / max(len(text.split()), 1),
            "has_profanity": bool(re.search(r'\b(fuck|shit|damn)\b', text.lower())),
            "has_garbled_text": self._detect_garbled_text(text),
            "has_bot_challenge": self._detect_anti_bot_garbage(text),
            "completeness": self._assess_completeness(text),
        }

        return quality

    @staticmethod
    def _detect_anti_bot_garbage(text: str) -> bool:
        """Detect anti-bot, CAPTCHA, Cloudflare, or crawler-challenge text."""
        if not text:
            return False
        patterns = [
            r"javascript\s+is\s+disabled",
            r"javascript\s+not\s+enabled",
            r"enable\s+javascript",
            r"requires\s+javascript",
            r"please\s+turn\s+javascript\s+on",
            r"verify\s+(?:that\s+)?you(?:'re|\s+are)\s+(?:not\s+)?a\s+(?:robot|human)",
            r"prove\s+you(?:'re|\s+are)\s+(?:not\s+)?a\s+(?:robot|human)",
            r"are\s+you\s+a\s+human",
            r"cf-browser-verification",
            r"cloudflare\s+(?:\w+\s+)*challenge",
            r"ddos\s+protection\s+by\s+cloudflare",
            r"attention\s+required!\s*\|\s*cloudflare",
            r"checking\s+your\s+browser\s+before\s+accessing",
            r"just\s+a\s+moment\b",
            r"429\s+too\s+many\s+requests",
            r"403\s+forbidden",
            r"access\s+denied",
        ]
        text_lower = text.lower()
        return any(bool(re.search(p, text_lower)) for p in patterns)

    def _detect_garbled_text(self, text: str) -> bool:
        """Detect garbled or corrupted text."""
        # Check for excessive repeated characters
        if re.search(r'(.)\1{5,}', text):
            return True

        # Check for very long words (excluding URLs, markdown links, and HTML tags)
        cleaned_text = re.sub(r'\[.*?\]\(.*?\)', ' ', text)
        cleaned_text = re.sub(r'http[s]?://\S+', ' ', cleaned_text)
        cleaned_text = re.sub(r'<[^>]+>', ' ', cleaned_text)
        if any(len(w) > 50 for w in cleaned_text.split()):
            return True

        # Check for high ratio of non-printable characters
        non_printable = sum(1 for c in text if ord(c) < 32 and c not in '\n\t')
        if non_printable / max(len(text), 1) > 0.1:
            return True

        return False

    def _assess_completeness(self, text: str) -> dict:
        """Assess if content appears complete or truncated."""
        return {
            "ends_with_period": text.rstrip().endswith('.'),
            "has_unclosed_brackets": text.count('(') != text.count(')'),
            "has_unclosed_quotes": text.count('"') % 2 != 0,
            "appears_truncated": text.rstrip().endswith('...') or text.rstrip().endswith('…'),
        }

    def _detect_encoding(self, text: str) -> str:
        """Detect text encoding issues."""
        try:
            text.encode('utf-8')
            return "utf-8"
        except UnicodeEncodeError:
            return "legacy/encoded"

    def _detect_ocr_artifacts(self, text: str) -> bool:
        """Detect OCR artifacts in text."""
        indicators = [
            r'\b[lI]{2,}\b',  # lI confusion (common OCR error)
            r'\b[O0]{2,}\b',  # O0 confusion
            r'\b[nmu]{3,}\b',  # character repetition
            r'\s{2,}',  # multiple spaces
            r'[\x00-\x1f]',  # control characters
        ]

        for pattern in indicators:
            if re.search(pattern, text):
                return True

        return False

    def _detect_historical_spelling(self, text: str) -> bool:
        """Detect historical or archaic spelling patterns."""
        historical_patterns = [
            r'\bye\s+',  # "ye olde"
            r'\bwhilst\b',
            r'\bwhilst\b',
            r'\bwherefore\b',
            r'\btherefore\b',
            r'\bthou\b',
            r'\bthy\b',
            r'\b hath \b',
            r'\b doth \b',
        ]

        for pattern in historical_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False


class ExtractionPipeline:
    """Enhanced pipeline for extracting from diverse, messy, multilingual sources."""
    _LOG = logger

    def __init__(self, config: dict, router=None):
        self.config = config
        self.router = router
        self.analyzer = ContentAnalyzer(router)
        self.timeout = config.get("timeout", 120)
        self._LOG = logger

    async def extract(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract content from various source types."""
        # Normalize metadata attributes on source object
        meta = getattr(source, 'metadata', None) or getattr(source, 'metadata__', {}) or {}
        if isinstance(source, dict):
            meta = source.get('metadata') or source.get('metadata__') or {}
            class DummySource:
                pass
            
            source_obj = DummySource()
            for k, v in source.items():
                setattr(source_obj, k, v)
                
            source_obj.metadata__ = meta
            source_obj.metadata = meta
            
            if not hasattr(source_obj, 'url'):
                source_obj.url = ''
                
            source_type_val = source.get('source_type')
            if isinstance(source_type_val, str):
                try:
                    source_obj.source_type = SourceType(source_type_val)
                except ValueError:
                    source_obj.source_type = None
            
            source = source_obj
        else:
            if not hasattr(source, 'metadata__'):
                try:
                    source.metadata__ = meta
                except AttributeError:
                    pass
            if not hasattr(source, 'metadata'):
                try:
                    source.metadata = meta
                except AttributeError:
                    pass
            
        source_type = getattr(source, 'source_type', None)
        url = getattr(source, 'url', '')

        if source_type == SourceType.WEB_PAGE:
            async for content in self.extract_from_url(url):
                yield content
        elif source_type == SourceType.PDF_DOCUMENT:
            async for content in self.extract_from_pdf(Path(url)):
                yield content
        elif source_type == SourceType.GITHUB_REPO:
            async for content in self.extract_from_github(source):
                yield content
        elif source_type == SourceType.GITHUB_FILE:
            async for content in self.extract_from_github_file(url, source):
                yield content
        elif source_type == SourceType.ARXIV_PAPER:
            async for content in self.extract_from_arxiv(source):
                yield content
        elif source_type == SourceType.HF_DATASET:
            async for content in self.extract_from_huggingface(source):
                yield content
        elif source_type == SourceType.PUBMED:
            async for content in self.extract_from_pubmed(source):
                yield content
        elif source_type == SourceType.KAGGLE_DATASET:
            async for content in self.extract_from_kaggle(source):
                yield content
        elif source_type == SourceType.ZENODO:
            async for content in self.extract_from_zenodo(source):
                yield content
        elif source_type == SourceType.AI_KOSH:
            async for content in self.extract_from_aikosh(source):
                yield content
        elif (
            source_type in (SourceType.GOOGLE_SCHOLAR, SourceType.SEMANTIC_SCHOLAR)
            or "semanticscholar.org" in url
        ):
            async for content in self.extract_from_scholar(source):
                yield content
        elif source_type in (SourceType.WIKIPEDIA, SourceType.BOOKS, SourceType.BLOG):
            async for content in self.extract_from_url(url):
                yield content
        else:
            async for content in self.extract_from_url(url):
                yield content

    async def extract_from_aikosh(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Download and read one small, permitted text file from AIKosh."""
        import json
        import os
        import tempfile
        import unicodedata
        from pathlib import Path, PurePosixPath

        metadata = getattr(source, "metadata__", None) or getattr(source, "metadata", {}) or {}
        dataset_id = str(metadata.get("aikosh_dataset_id") or "").strip()
        file_info = metadata.get("aikosh_file") or {}
        remote_path = str(file_info.get("path") or "").strip().replace("\\", "/")
        filename = PurePosixPath(remote_path).name
        extension = Path(filename).suffix.lower()
        max_bytes = int(self.config.get("aikosh_max_file_size_bytes", 10 * 1024 * 1024))
        allowed_extensions = {".csv", ".tsv", ".parquet", ".json", ".jsonl", ".txt", ".md"}
        api_key = (
            self.config.get("aikosh_api_key")
            or self.config.get("ai_kosh_api_key")
            or os.getenv("AIKOSH_API_KEY")
            or os.getenv("AI_KOSH_API_KEY")
            or os.getenv("AIKOSH_ACCESS_KEY")
        )
        if not (dataset_id and remote_path and ".." not in PurePosixPath(remote_path).parts and filename and extension in allowed_extensions and api_key):
            yield ExtractedContent(
                content="", content_type="error", url=getattr(source, "url", ""),
                extraction_warnings=["AIKosh file access is unavailable or the listed file format is unsupported."],
            )
            return

        try:
            import aikosh
        except ImportError:
            yield ExtractedContent(
                content="", content_type="error", url=getattr(source, "url", ""),
                extraction_warnings=["The optional AIKosh SDK is not installed."],
            )
            return

        try:
            with tempfile.TemporaryDirectory(prefix="rasosynth-aikosh-") as temp_dir:
                destination = Path(temp_dir)

                def _download():
                    aikosh.set_api_key(api_key)
                    permitted = False
                    for page in range(1, 11):
                        file_listing = aikosh.list_files(
                            "dataset",
                            dataset_id,
                            filters={"directory_path": "", "page": page, "limit": 50},
                        )
                        payload = file_listing.get("data", {}) if isinstance(file_listing, dict) else {}
                        files = payload.get("items", payload.get("files", [])) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
                        for listed_file in files if isinstance(files, list) else []:
                            if not isinstance(listed_file, dict):
                                continue
                            listed_path = str(listed_file.get("file_path") or listed_file.get("filePath") or listed_file.get("path") or listed_file.get("fileName") or listed_file.get("name") or listed_file.get("key") or "").strip().replace("\\", "/")
                            if listed_path != remote_path:
                                continue
                            raw_listed_size = listed_file.get("size_bytes", listed_file.get("sizeBytes", listed_file.get("fileSize", listed_file.get("size"))))
                            try:
                                listed_size = int(raw_listed_size)
                            except (TypeError, ValueError):
                                match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(b|bytes|kb|mb|gb)\s*", str(raw_listed_size or "").lower())
                                if match:
                                    multiplier = {"b": 1, "bytes": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}[match.group(2)]
                                    listed_size = int(float(match.group(1)) * multiplier)
                                else:
                                    listed_size = 0
                            permitted = 0 < listed_size <= max_bytes
                            break
                        if permitted or not isinstance(files, list) or len(files) < 50:
                            break
                    if not permitted:
                        raise PermissionError("AIKosh no longer lists this file as an accessible file within the size limit")
                    return aikosh.download({
                        "identifier": dataset_id,
                        "type": "dataset",
                        "file_path": remote_path,
                        "destination_path": str(destination),
                        "filename": filename,
                    })

                result = await asyncio.to_thread(_download)
                local_file = destination / filename
                if not local_file.is_file():
                    possible_files = [path for path in destination.rglob("*") if path.is_file() and path.suffix.lower() in allowed_extensions]
                    if len(possible_files) == 1:
                        local_file = possible_files[0]
                if not local_file.is_file():
                    raise FileNotFoundError(f"AIKosh SDK did not return the requested file ({getattr(result, 'status', 'unknown status')})")
                actual_size = local_file.stat().st_size
                if actual_size <= 0 or actual_size > max_bytes:
                    raise ValueError(f"AIKosh file exceeds the {max_bytes}-byte ingestion limit")

                if extension == ".csv":
                    import pandas as pd
                    frame = pd.read_csv(local_file, nrows=100, dtype=str, keep_default_na=False)
                    file_content = frame.to_csv(index=False)
                elif extension == ".tsv":
                    import pandas as pd
                    frame = pd.read_csv(local_file, sep="\t", nrows=100, dtype=str, keep_default_na=False)
                    file_content = frame.to_csv(index=False, sep="\t")
                elif extension == ".parquet":
                    import pyarrow.parquet as pq
                    parquet_file = pq.ParquetFile(local_file)
                    column_names = parquet_file.schema.names[:100]
                    batch = next(parquet_file.iter_batches(batch_size=100, columns=column_names), None)
                    if batch is None:
                        raise ValueError("AIKosh Parquet file contains no readable rows")
                    frame = batch.to_pandas().fillna("").astype(str)
                    file_content = frame.to_csv(index=False)
                elif extension == ".json":
                    with local_file.open("r", encoding="utf-8-sig") as handle:
                        payload = json.load(handle)
                    if isinstance(payload, list):
                        payload = payload[:100]
                    file_content = json.dumps(payload, ensure_ascii=False, indent=2)[:100_000]
                elif extension == ".jsonl":
                    with local_file.open("r", encoding="utf-8-sig") as handle:
                        file_content = "".join(line for _, line in zip(range(100), handle))
                else:
                    file_content = local_file.read_text(encoding="utf-8-sig", errors="replace")[:100_000]

                content = "\n".join(filter(None, [
                    f"Dataset: {getattr(source, 'title', '')}",
                    f"Description: {getattr(source, 'description', '') or ''}",
                    f"File: {filename}",
                    file_content,
                ]))
                content = unicodedata.normalize("NFC", content)
                extracted = await self._process_text(content[:150_000], getattr(source, "url", ""), "utf-8")
                extracted.metadata.update({
                    "source_type": "ai_kosh",
                    "aikosh_dataset_id": dataset_id,
                    "aikosh_file_path": remote_path,
                    "aikosh_file_size_bytes": actual_size,
                    "unicode_normalization": "NFC",
                    "license": getattr(source, "license", None),
                })
                yield extracted
        except Exception as exc:
            self._LOG.warning("AIKosh file extraction failed for %s: %s", remote_path, exc)
            yield ExtractedContent(
                content="", content_type="error", url=getattr(source, "url", ""),
                extraction_warnings=[f"Could not download or read the AIKosh file: {exc}"],
            )

    async def extract_from_url(self, url: str) -> AsyncGenerator[ExtractedContent, None]:
        """Extract content from URL with intelligent type detection."""
        # SSRF protection: reject internal/private targets
        is_safe, reason = _is_safe_url(url)
        if not is_safe:
            yield ExtractedContent(
                content="",
                content_type="error",
                url=url,
                confidence=0.0,
                quality_score=0.0,
                extraction_warnings=[f"URL blocked by SSRF protection: {reason}"]
            )
            return

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=False,  # Disabled: let the caller track redirects for SSRF safety
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AI-Dataset-Engineer/1.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml,*/*"
                }
            ) as client:
                response = await client.get(url)
                if response.status_code >= 400:
                    yield ExtractedContent(
                        content="",
                        content_type="error",
                        url=url,
                        confidence=0.0,
                        quality_score=0.0,
                        extraction_warnings=[f"HTTP {response.status_code} error from source"]
                    )
                    return

                content_type = response.headers.get("content-type", "")

                # Detect encoding
                encoding = response.encoding or 'utf-8'
                raw_content = response.text

                # Immediate anti-bot verification check on raw response text
                if self.analyzer._detect_anti_bot_garbage(raw_content):
                    yield ExtractedContent(
                        content="",
                        content_type="error",
                        url=url,
                        confidence=0.0,
                        quality_score=0.0,
                        extraction_warnings=["anti_bot_garbage: Anti-bot verification page detected (CAPTCHA/Cloudflare)"]
                    )
                    return

                # Extract based on content type
                if "text/html" in content_type:
                    async for content in self._extract_html(raw_content, url, encoding):
                        yield content
                elif "application/pdf" in content_type:
                    yield ExtractedContent(
                        content="PDF content",
                        content_type="pdf",
                        encoding="binary",
                        url=url,
                        confidence=0.5,
                        extraction_warnings=["PDF download detected - use dedicated PDF extraction"]
                    )
                elif "text/plain" in content_type:
                    yield await self._process_text(raw_content, url, encoding)
                else:
                    # Try HTML extraction anyway
                    async for content in self._extract_html(raw_content, url, encoding):
                        yield content

        except Exception as e:
            yield ExtractedContent(
                content="",
                content_type="error",
                url=url,
                confidence=0.0,
                extraction_warnings=[f"Extraction failed: {str(e)}"]
            )

    async def _extract_html(
        self,
        html: str,
        url: str,
        encoding: str
    ) -> AsyncGenerator[ExtractedContent, None]:
        """Extract text from HTML with structure preservation."""
        if self.analyzer._detect_anti_bot_garbage(html):
            yield ExtractedContent(
                content="",
                content_type="error",
                url=url,
                confidence=0.0,
                quality_score=0.0,
                extraction_warnings=["anti_bot_garbage: Anti-bot verification page detected (CAPTCHA/Cloudflare)"]
            )
            return

        # Remove scripts and styles
        text = html
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Detect if it's a code repository
        if 'github.com' in url:
            async for content in self._extract_github_content(text, url):
                yield content
            return

        # Regular HTML extraction
        content = self._strip_html(text)

        if self.analyzer._detect_anti_bot_garbage(content):
            yield ExtractedContent(
                content="",
                content_type="error",
                url=url,
                confidence=0.0,
                quality_score=0.0,
                extraction_warnings=["anti_bot_garbage: Anti-bot verification page detected (CAPTCHA/Cloudflare)"]
            )
            return

        # Analyze structure
        structure = self.analyzer._detect_structure(html)

        # Process and analyze
        extracted = await self._process_text(content, url, encoding)

        # Add structure info
        extracted.structure_detected = structure

        # Check for multilingual content
        languages = await self.analyzer._detect_language_mixing(content)
        extracted.languages_detected = languages

        yield extracted

    async def _extract_github_content(
        self,
        html: str,
        url: str
    ) -> AsyncGenerator[ExtractedContent, None]:
        """Extract code and documentation from GitHub."""
        # Extract README content
        readme_patterns = [
            r'<article[^>]*class="markdown-body"[^>]*>(.*?)</article>',
            r'<div[^>]*id="readme"[^>]*>(.*?)</div>',
            r'<td[^>]*class="blob-code"[^>]*>(.*?)</td>',
        ]

        for pattern in readme_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                content = self._strip_html(match)
                if len(content) > 100:
                    extracted = await self._process_text(content, url, "utf-8")

                    # Detect code blocks
                    code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
                    if code_blocks:
                        extracted.metadata["code_blocks"] = len(code_blocks)
                        extracted.metadata["code_languages"] = list(set(cb[0] for cb in code_blocks if cb[0]))

                    yield extracted
                    return

        # Fallback: extract all text
        content = self._strip_html(html)
        yield await self._process_text(content[:5000], url, "utf-8")

    async def _process_text(
        self,
        content: str,
        url: str,
        encoding: str
    ) -> ExtractedContent:
        """Process raw text with analysis."""
        # Analyze content
        analysis = await self.analyzer.analyze(content)

        # Clean content
        cleaned = self._clean_text(content)

        # Detect anti-bot challenge upfront
        is_bot = (
            analysis.get("quality", {}).get("has_bot_challenge")
            or analysis.get("has_bot_challenge")
            or self.analyzer._detect_anti_bot_garbage(content)
            or self.analyzer._detect_anti_bot_garbage(cleaned)
        )
        if is_bot:
            return ExtractedContent(
                content="",
                content_type="error",
                language=analysis.get("language", "unknown"),
                url=url,
                confidence=0.0,
                quality_score=0.0,
                encoding=encoding,
                extraction_warnings=["anti_bot_garbage: Anti-bot verification page detected (CAPTCHA/Cloudflare)"],
            )

        # Detect quality issues
        quality_score = self._calculate_quality_score(analysis, cleaned)

        # Check for OCR artifacts
        has_ocr = self.analyzer._detect_ocr_artifacts(cleaned)

        # Generate normalized version if needed
        normalized = None
        if has_ocr or analysis.get("has_historical_spelling"):
            normalized = await self._normalize_text(cleaned, analysis)

        return ExtractedContent(
            content=cleaned,
            content_type=analysis["content_type"],
            language=analysis["language"],
            languages_detected=analysis["languages_mixed"],
            metadata={
                "analysis": analysis,
                "url": url,
                "encoding": encoding,
            },
            url=url,
            confidence=quality_score,
            quality_score=quality_score,
            encoding=encoding,
            structure_detected=analysis.get("structure"),
            extraction_warnings=self._generate_warnings(analysis, has_ocr),
            normalized_content=normalized,
        )

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags while preserving structure."""
        # Convert block elements to newlines
        for tag in ['</p>', '</div>', '</li>', '</tr>', '</h1>', '</h2>', '</h3>']:
            html = html.replace(tag, '\n')

        # Remove all tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def _clean_text(self, text: str) -> str:
        """Clean text while preserving structure."""
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _calculate_quality_score(self, analysis: dict, content: str) -> float:
        """Calculate content quality score."""
        if (
            analysis.get("has_bot_challenge")
            or analysis.get("quality", {}).get("has_bot_challenge")
            or self.analyzer._detect_anti_bot_garbage(content)
        ):
            return 0.0

        score = 1.0

        # Deduct for quality issues
        if analysis.get("has_garbled_text"):
            score -= 0.3

        if analysis.get("has_ocr_artifacts"):
            score -= 0.1

        quality = analysis.get("quality", {})
        if quality.get("unique_word_ratio", 1) < 0.3:
            score -= 0.2

        if len(content) < 100:
            score -= 0.3

        return max(0.0, min(1.0, score))

    def _generate_warnings(self, analysis: dict, has_ocr: bool) -> list[str]:
        """Generate extraction warnings."""
        warnings = []

        if analysis.get("has_bot_challenge") or analysis.get("quality", {}).get("has_bot_challenge"):
            warnings.append("anti_bot_garbage: Anti-bot verification page detected (CAPTCHA/Cloudflare)")

        if analysis.get("has_garbled_text"):
            warnings.append("Content may contain garbled/corrupted text")

        if has_ocr:
            warnings.append("Content may contain OCR artifacts")

        if analysis.get("has_historical_spelling"):
            warnings.append("Content contains historical/archaic spellings")

        if len(analysis.get("languages_mixed", [])) > 1:
            warnings.append(f"Mixed languages detected: {', '.join(analysis['languages_mixed'])}")

        structure = analysis.get("structure", {})
        if structure.get("has_unclosed_brackets"):
            warnings.append("Document structure may be incomplete")

        return warnings

    async def _normalize_text(self, text: str, analysis: dict) -> str:
        """Normalize text (OCR correction, historical spelling, etc.)."""
        normalized = text

        # Simple OCR corrections
        ocr_fixes = {
            r'\b(l|I)1\b': 'l' if 'l' in analysis.get("language", "en") else 'I',
            r'\b(O|0)0\b': 'oo',
            r'\s{2,}': ' ',
        }

        for pattern, replacement in ocr_fixes.items():
            normalized = re.sub(pattern, replacement, normalized)

        # If router available, use AI for intelligent normalization
        if self.router and (analysis.get("has_ocr_artifacts") or analysis.get("has_historical_spelling")):
            try:
                prompt = f"""The following text may contain OCR errors or historical spellings.
                Clean and normalize it while preserving meaning. Keep the same language.

                Text:
                {text[:2000]}

                Normalized:"""

                response = await self.router.route(TaskType.TEXT_GENERATION, prompt)
                normalized = response.content
            except Exception:
                pass  # Keep simple normalization

        return normalized

    async def extract_from_pdf(self, pdf_path: Path) -> AsyncGenerator[ExtractedContent, None]:
        """Extract text from PDF with OCR support."""
        try:
            # Try pdfplumber first
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""

                    if text.strip():
                        yield await self._process_text(text, str(pdf_path), "utf-8")
                        return
            except ImportError:
                pass

            # Try PyPDF2
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(pdf_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""

                if text.strip():
                    yield await self._process_text(text, str(pdf_path), "utf-8")
                    return
            except ImportError:
                pass

            # Use OCR if available
            yield ExtractedContent(
                content="",
                content_type="pdf_ocr_required",
                confidence=0.0,
                metadata={"note": "Install pdfplumber or PyPDF2, or enable OCR"},
                url=str(pdf_path),
                extraction_warnings=["PDF text extraction unavailable, OCR not implemented"]
            )

        except Exception as e:
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=str(pdf_path),
                extraction_warnings=[f"PDF extraction failed: {str(e)}"]
            )

    async def extract_from_github(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract README and code from GitHub repository."""
        try:
            readme_url = source.metadata.get("readme_url", "")
            if not readme_url:
                return

            # SSRF protection
            is_safe, reason = _is_safe_url(readme_url)
            if not is_safe:
                yield ExtractedContent(
                    content="",
                    content_type="error",
                    confidence=0.0,
                    url=readme_url,
                    extraction_warnings=[f"GitHub readme URL blocked by SSRF protection: {reason}"]
                )
                return

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(readme_url)
                if response.status_code == 200:
                    content = response.text
                    extracted = await self._process_text(content, source.url, "utf-8")
                    extracted.metadata["source_type"] = "github_readme"
                    extracted.metadata["repo"] = source.metadata.get("repo_url", "")
                    yield extracted

        except Exception as e:
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=source.url,
                extraction_warnings=[f"GitHub extraction failed: {str(e)}"]
            )

    async def extract_from_github_file(self, url: str, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract raw code file from GitHub."""
        try:
            # Convert to raw URL
            raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

            # SSRF protection
            is_safe, reason = _is_safe_url(raw_url)
            if not is_safe:
                yield ExtractedContent(
                    content="",
                    content_type="error",
                    confidence=0.0,
                    url=raw_url,
                    extraction_warnings=[f"GitHub file URL blocked by SSRF protection: {reason}"]
                )
                return

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(raw_url)
                if response.status_code == 200:
                    content = response.text

                    # Detect language from URL
                    ext = url.split('.')[-1] if '.' in url else ""
                    lang_map = {
                        "py": "python", "js": "javascript", "ts": "typescript",
                        "java": "java", "go": "go", "rs": "rust", "cpp": "cpp",
                        "c": "c", "rb": "ruby", "php": "php", "swift": "swift",
                        "kt": "kotlin", "scala": "scala", "md": "markdown"
                    }
                    language = lang_map.get(ext, "unknown")

                    extracted = ExtractedContent(
                        content=content,
                        content_type="code",
                        language=language,
                        url=url,
                        confidence=0.95,
                        quality_score=0.9,
                        metadata={
                            "file_type": ext,
                            "lines": len(content.split('\n')),
                            "source": "github"
                        }
                    )
                    yield extracted

        except Exception as e:
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=url,
                extraction_warnings=[f"GitHub file extraction failed: {str(e)}"]
            )

    async def extract_from_arxiv(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract content from ArXiv paper."""
        try:
            # Try to get PDF text first
            arxiv_id = source.metadata__.get("arxiv_id", "")
            if arxiv_id:
                # Already have description from discovery
                content = source.description or ""

                if content:
                    extracted = await self._process_text(content, source.url, "utf-8")
                    extracted.metadata["source_type"] = "arxiv_abstract"
                    extracted.metadata["arxiv_id"] = arxiv_id
                    extracted.metadata["authors"] = source.author
                    yield extracted

        except Exception as e:
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=source.url,
                extraction_warnings=[f"ArXiv extraction failed: {str(e)}"]
            )

    async def extract_from_huggingface(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract dataset information from HuggingFace, preferring actual sample data."""
        try:
            meta = getattr(source, "metadata", None) or getattr(source, "metadata__", {}) or {}
            target_lang = meta.get("language") or self.config.get("language") or "en"
            sample_content = None
            sample_rows = meta.get("sample_rows")
            if sample_rows and isinstance(sample_rows, list) and len(sample_rows) > 0:
                import json
                rows_to_show = sample_rows[:20]
                sample_lines = []
                for row in rows_to_show:
                    if isinstance(row, dict):
                        sample_lines.append(json.dumps(row, ensure_ascii=False))
                    else:
                        sample_lines.append(str(row))
                sample_content = "\n".join(sample_lines)
                if sample_content:
                    detected_lang = await self.analyzer._detect_language(sample_content)
                    resolved_lang = detected_lang if (detected_lang and detected_lang != "unknown") else target_lang
                    content = f"Dataset: {source.title}\nDescription: {getattr(source, 'description', '') or ''}\n\nSample data ({len(rows_to_show)} rows):\n{sample_content}"
                    extracted = ExtractedContent(
                        content=content,
                        content_type="huggingface_dataset_sample",
                        language=resolved_lang,
                        url=source.url,
                        confidence=0.95,
                        metadata={
                            "downloads": meta.get("downloads", 0),
                            "tags": meta.get("tags", []),
                            "author": getattr(source, "author", "") or meta.get("author", ""),
                            "source_type": "huggingface_dataset",
                            "sample_rows_used": len(rows_to_show),
                            "total_samples": len(sample_rows) if isinstance(sample_rows, list) else 0,
                            "language": resolved_lang,
                        }
                    )
                    yield extracted
                    return

            # Try to fetch actual rows using datasets streaming SDK
            try:
                import asyncio
                def _safe_load_hf():
                    from datasets import load_dataset, get_dataset_config_names
                    ds_id = meta.get("id") or getattr(source, "title", "")
                    if not ds_id:
                        return None
                    try:
                        configs = get_dataset_config_names(ds_id)
                        config = configs[0] if configs else None
                    except Exception:
                        config = None
                    kwargs = {"split": "train", "streaming": True, "trust_remote_code": False}
                    if config:
                        kwargs["name"] = config
                    ds = load_dataset(ds_id, **kwargs)
                    return list(ds.take(20))

                head = await asyncio.wait_for(asyncio.to_thread(_safe_load_hf), timeout=30.0)
                if head:
                    import json
                    sample_lines = []
                    for row in head:
                        if isinstance(row, dict):
                            sample_lines.append(json.dumps(row, ensure_ascii=False))
                        else:
                            sample_lines.append(str(row))
                    sample_content = "\n".join(sample_lines)
                    if sample_content:
                        detected_lang = await self.analyzer._detect_language(sample_content)
                        resolved_lang = detected_lang if (detected_lang and detected_lang != "unknown") else target_lang
                        content = f"Dataset: {source.title}\nDescription: {getattr(source, 'description', '') or ''}\n\nSample data ({len(head)} rows):\n{sample_content}"
                        extracted = ExtractedContent(
                            content=content,
                            content_type="huggingface_dataset_sample",
                            language=resolved_lang,
                            url=source.url,
                            confidence=0.9,
                            metadata={
                                "downloads": meta.get("downloads", 0),
                                "tags": meta.get("tags", []),
                                "author": getattr(source, "author", "") or meta.get("author", ""),
                                "source_type": "huggingface_dataset",
                                "fetched_via_sdk": True,
                                "sample_rows_used": len(head),
                                "language": resolved_lang,
                            }
                        )
                        yield extracted
                        return
            except Exception as sdk_err:
                logger.debug(f"HF SDK sample extraction safely bypassed for {source.url}: {sdk_err}")

            # Fallback to metadata / description if streaming SDK couldn't fetch sample rows
            desc = getattr(source, "description", "") or ""
            fallback_text = f"Dataset: {source.title}\nDescription: {desc}\nURL: {source.url}"
            yield ExtractedContent(
                content=fallback_text,
                content_type="huggingface_dataset",
                language=target_lang,
                url=source.url,
                confidence=0.75,
                metadata={
                    "downloads": meta.get("downloads", 0),
                    "tags": meta.get("tags", []),
                    "author": getattr(source, "author", "") or meta.get("author", ""),
                    "source_type": "huggingface_dataset",
                    "language": target_lang,
                }
            )
            return
        except Exception as e:
            logger.warning(f"HuggingFace extraction failed: {e}")
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=source.url,
                extraction_warnings=[f"HuggingFace extraction failed: {str(e)}"]
            )

    async def extract_from_pubmed(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract content from PubMed paper."""
        # Try to get full text when possible, fall back to abstract
        try:
            # For now, we'll use the abstract but note this is a limitation
            # In a production system, we might try to access full text via PMC or other sources
            content = f"{source.title}\n\n{source.description or ''}"
            extracted = await self._process_text(content, source.url, "utf-8")
            extracted.metadata["source_type"] = "pubmed"
            extracted.metadata["date"] = source.date
            # Mark as lower confidence since we're only using abstract, not full text
            extracted.confidence = 0.3  # Low confidence to avoid being ranked too high
            yield extracted
        except Exception as e:
            self._LOG.warning(f"PubMed extraction failed: {e}")
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=source.url,
                extraction_warnings=[f"PubMed extraction failed: {str(e)}"]
            )

    async def extract_from_scholar(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract academic content from scholar source using API abstract/metadata, avoiding Cloudflare web walls."""
        try:
            title = getattr(source, "title", "") or ""
            description = getattr(source, "description", "") or ""
            metadata = getattr(source, "metadata__", None) or getattr(source, "metadata", {}) or {}
            arxiv_id = metadata.get("arxiv_id", "")
            url = getattr(source, "url", "")

            content = f"{title}\n\n{description}".strip() if (title or description) else ""

            # Check if abstract is real content (not anti-bot)
            if content and not self.analyzer._detect_anti_bot_garbage(content) and len(content) > 30:
                extracted = await self._process_text(content, url, "utf-8")
                extracted.metadata["source_type"] = "academic_abstract"
                extracted.metadata["paper_id"] = metadata.get("paper_id", "")
                if arxiv_id:
                    extracted.metadata["arxiv_id"] = arxiv_id
                author = getattr(source, "author", "")
                if author:
                    extracted.metadata["authors"] = author
                yield extracted
            elif arxiv_id:
                async for c in self.extract_from_arxiv(source):
                    yield c
            else:
                yield ExtractedContent(
                    content="",
                    content_type="error",
                    confidence=0.0,
                    url=url,
                    extraction_warnings=["Scholar source abstract missing or empty; scraping bypassed to avoid bot challenge"]
                )
        except Exception as e:
            self._LOG.warning(f"Scholar extraction failed: {e}")
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=getattr(source, "url", ""),
                extraction_warnings=[f"Scholar extraction failed: {str(e)}"]
            )

    async def extract_from_kaggle(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract actual dataset files from Kaggle, not just metadata."""
        try:
            import tempfile
            meta = getattr(source, 'metadata', None) or getattr(source, 'metadata__', {}) or {}
            dataset_ref = meta.get('kaggle_dataset_ref') or meta.get('ref')
            if not dataset_ref and getattr(source, 'url', ''):
                import re
                match = re.search(r'/datasets/([^/]+/[^/?#]+)', source.url)
                if match:
                    dataset_ref = match.group(1)

            if not dataset_ref:
                return

            path = None
            # 1. Try kagglehub
            try:
                import kagglehub
                import asyncio
                path = await asyncio.wait_for(
                    asyncio.to_thread(kagglehub.dataset_download, dataset_ref),
                    timeout=15.0
                )
            except Exception as kh_err:
                logger.debug(f"kagglehub failed ({kh_err}), trying KaggleApi extended...")
                # 2. Try official KaggleApi with credentials
                try:
                    import os
                    kaggle_user = os.getenv("KAGGLE_USERNAME") or self.config.get("kaggle_username")
                    kaggle_key = os.getenv("KAGGLE_KEY") or self.config.get("kaggle_key")
                    kaggle_token = os.getenv("KAGGLE_API_TOKEN")
                    has_creds = (
                        (kaggle_user and kaggle_key)
                        or kaggle_token
                        or os.path.exists(os.path.expanduser("~/.kaggle/access_token"))
                        or os.path.exists(os.path.expanduser("~/.kaggle/kaggle.json"))
                    )
                    if has_creds:
                        if kaggle_user:
                            os.environ["KAGGLE_USERNAME"] = kaggle_user
                        if kaggle_key:
                            os.environ["KAGGLE_KEY"] = kaggle_key
                        if kaggle_token:
                            os.environ["KAGGLE_API_TOKEN"] = kaggle_token
                        from kaggle.api.kaggle_api_extended import KaggleApi
                        import asyncio
                        k_api = KaggleApi()
                        k_api.authenticate()
                        temp_dir = tempfile.mkdtemp(prefix="kaggle_")
                        await asyncio.wait_for(
                            asyncio.to_thread(k_api.dataset_download_files, dataset_ref, path=temp_dir, unzip=True),
                            timeout=30.0
                        )
                        path = temp_dir
                except Exception as k_err:
                    logger.debug(f"KaggleApi download failed: {k_err}")

            if path and os.path.exists(path):
                content_parts = [f"Dataset: {source.title}", f"Description: {getattr(source, 'description', '') or ''}"]
                import os
                for root, dirs, files in os.walk(path):
                    for file in files[:5]:
                        file_path = os.path.join(root, file)
                        file_ext = os.path.splitext(file)[1].lower()
                        try:
                            if file_ext == '.csv':
                                import pandas as pd
                                df = pd.read_csv(file_path, nrows=20)
                                content_parts.append(f"\nFile: {file}\n{df.to_string()}")
                            elif file_ext == '.json':
                                import json
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    data = json.load(f)
                                    preview = data[:10] if isinstance(data, list) else data
                                    content_parts.append(f"\nFile: {file}\n{json.dumps(preview, indent=2)[:1500]}")
                            elif file_ext in ['.parquet']:
                                import pandas as pd
                                df = pd.read_parquet(file_path)
                                content_parts.append(f"\nFile: {file}\n{df.head(20).to_string()}")
                            elif file_ext in ['.txt', '.md']:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content_parts.append(f"\nFile: {file}\n{f.read(2000)}")
                        except Exception as file_e:
                            logger.debug(f"Could not read Kaggle file {file}: {file_e}")
                            continue

                if len(content_parts) > 2:
                    content = "\n".join(content_parts)
                    extracted = await self._process_text(content, source.url, "utf-8")
                    extracted.metadata["source_type"] = "kaggle_dataset"
                    extracted.metadata["local_path"] = path
                    extracted.confidence = 0.9
                    yield extracted
                    return

            # Fallback to metadata / description if files could not be downloaded
            desc = getattr(source, "description", "") or ""
            fallback_text = f"Dataset: {source.title}\nDescription: {desc}\nURL: {getattr(source, 'url', '')}"
            kaggle_lang = meta.get("language") or self.config.get("language") or "en"
            yield ExtractedContent(
                content=fallback_text,
                content_type="kaggle_dataset",
                language=kaggle_lang,
                url=getattr(source, "url", ""),
                confidence=0.75,
                metadata={
                    "downloads": meta.get("downloads", 0),
                    "tags": meta.get("tags", []),
                    "author": getattr(source, "author", "") or meta.get("author", ""),
                    "source_type": "kaggle_dataset",
                    "ref": dataset_ref,
                    "language": kaggle_lang,
                }
            )
            return
        except Exception as e:
            logger.warning(f"Kaggle extraction failed: {e}")
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=getattr(source, "url", ""),
                extraction_warnings=[f"Kaggle extraction failed: {str(e)}"]
            )

    async def extract_from_zenodo(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract actual dataset files from Zenodo, not just metadata."""
        try:
            # Try to get the actual files from Zenodo record
            zenodo_id = None
            if hasattr(source, 'metadata__') and source.metadata__.get('zenodo_id'):
                zenodo_id = source.metadata__['zenodo_id']
            elif source.url:
                # Extract from URL like https://zenodo.org/record/1234565678
                import re
                match = re.search(r'/record/(\d+)', source.url)
                if match:
                    zenodo_id = match.group(1)

            if zenodo_id:
                # Try to get record metadata to find downloadable files
                import json
                api_url = f"https://zenodo.org/api/records/{zenodo_id}"
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                    response = await client.get(api_url)
                    if response.status_code == 200:
                        data = response.json()

                        content_parts = []
                        title = data.get('metadata', {}).get('title', source.title or '').strip()
                        if title:
                            content_parts.append(title)
                        description = data.get('metadata', {}).get('description', '')
                        if description:
                            # Clean HTML tags from description
                            import re
                            clean_description = re.sub('<[^<]+?>', '', description).strip()
                            if len(clean_description) > 60:
                                content_parts.append(clean_description[:2000])

                        # Try to get actual text files content (do NOT emit raw file names or byte counts as text)
                        files = data.get('files', [])
                        text_samples = []
                        if files:
                            for file_info in files[:3]:
                                file_name = (file_info.get('key') or '').lower()
                                file_size = file_info.get('size', 0)
                                # Only read small plain text/markdown/json files
                                if file_size < 100000 and any(file_name.endswith(ext) for ext in ('.txt', '.md', '.json', '.csv')):
                                    file_url = file_info.get('links', {}).get('self')
                                    if file_url:
                                        try:
                                            file_response = await client.get(file_url)
                                            if file_response.status_code == 200 and len(file_response.text.strip()) > 50:
                                                text_samples.append(file_response.text[:2000])
                                        except Exception:
                                            pass

                        if text_samples:
                            content_parts.extend(text_samples)

                        combined_text = "\n\n".join(content_parts).strip()
                        # Require substantive text (>120 chars) to prevent metadata / file listings from polluting synthesis
                        if len(combined_text) > 120:
                            extracted = await self._process_text(combined_text, source.url, "utf-8")
                            extracted.metadata["source_type"] = "zenodo"
                            extracted.metadata["zenodo_id"] = zenodo_id
                            extracted.confidence = 0.6 if text_samples else 0.4
                            yield extracted
                            return

            # If we can't access actual dataset files, don't yield anything
            # This prevents metadata from being used as dataset content
            pass

        except Exception as e:
            self._LOG.warning(f"Zenodo extraction failed: {e}")
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=source.url,
                extraction_warnings=[f"Zenodo extraction failed: {str(e)}"]
            )

    def extract_tables(self, html: str) -> list[dict]:
        """Extract tables from HTML."""
        tables = []

        # HTML tables
        table_pattern = r'<table[^>]*>(.*?)</table>'
        rows_pattern = r'<tr[^>]*>(.*?)</tr>'
        cell_pattern = r'<t[dh][^>]*>(.*?)</t[dh]>'

        for table_match in re.finditer(table_pattern, html, re.DOTALL | re.IGNORECASE):
            table_html = table_match.group(1)
            rows = []

            for row_match in re.finditer(rows_pattern, table_html, re.DOTALL | re.IGNORECASE):
                cells = re.findall(cell_pattern, row_match.group(1), re.DOTALL | re.IGNORECASE)
                cells = [self._strip_html(c).strip() for c in cells]
                if cells:
                    rows.append(cells)

            if rows:
                tables.append({"rows": rows, "headers": rows[0] if len(rows) > 1 else []})

        # CSV-like tables
        lines = html.split('\n')
        csv_tables = []
        for line in lines:
            if '\t' in line and self._looks_like_table_row(line):
                csv_tables.append([cell.strip() for cell in line.split('\t')])

        if csv_tables:
            tables.append({"rows": csv_tables, "type": "tab_separated"})

        return tables
