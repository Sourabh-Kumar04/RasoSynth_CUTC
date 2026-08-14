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
            "completeness": self._assess_completeness(text),
        }

        return quality

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

    def __init__(self, config: dict, router=None):
        self.config = config
        self.router = router
        self.analyzer = ContentAnalyzer(router)
        self.timeout = config.get("timeout", 120)

    async def extract(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract content from various source types."""
        if isinstance(source, dict):
            class DummySource:
                pass
            
            source_obj = DummySource()
            for k, v in source.items():
                setattr(source_obj, k, v)
                
            if 'metadata' in source and not hasattr(source_obj, 'metadata__'):
                source_obj.metadata__ = source['metadata']
            
            if not hasattr(source_obj, 'url'):
                source_obj.url = ''
                
            source_type_val = source.get('source_type')
            if isinstance(source_type_val, str):
                try:
                    source_obj.source_type = SourceType(source_type_val)
                except ValueError:
                    source_obj.source_type = None
            
            source = source_obj
            
            source_type = getattr(source, 'source_type', None)
            url = getattr(source, 'url', '')
        else:
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
        else:
            async for content in self.extract_from_url(url):
                yield content

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
                content_type = response.headers.get("content-type", "")

                # Detect encoding
                encoding = response.encoding or 'utf-8'
                raw_content = response.text

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
            # Try to get actual sample data if available via datasets SDK
            sample_content = None
            # If we already have sample_rows from discovery inspection, use them
            sample_rows = source.metadata__.get("sample_rows")
            if sample_rows and isinstance(sample_rows, list) and len(sample_rows) > 0:
                # Convert sample rows to a readable string
                import json
                # Take up to 3 rows for brevity
                rows_to_show = sample_rows[:3]
                sample_lines = []
                for row in rows_to_show:
                    if isinstance(row, dict):
                        sample_lines.append(json.dumps(row, ensure_ascii=False))
                    else:
                        sample_lines.append(str(row))
                sample_content = "\n".join(sample_lines)
                if sample_content:
                    # Also include dataset title and description as context
                    content = f"Dataset: {source.title}\nDescription: {source.description or ''}\n\nSample data (first {len(rows_to_show)} rows):\n{sample_content}"
                    extracted = ExtractedContent(
                        content=content,
                        content_type="huggingface_dataset_sample",
                        language="en",
                        url=source.url,
                        confidence=0.95,  # High confidence because we have actual data
                        metadata={
                            "downloads": source.metadata__.get("downloads", 0),
                            "tags": source.metadata__.get("tags", []),
                            "author": source.metadata__.get("author", ""),
                            "source_type": "huggingface_dataset",
                            "sample_rows_used": len(rows_to_show),
                            "total_samples": len(sample_rows) if isinstance(sample_rows, list) else 0
                        }
                    )
                    yield extracted
                    return
            # If we don't have precomputed sample_rows, try to fetch a sample via datasets SDK
            try:
                from datasets import load_dataset, get_dataset_config_names
                ds_id = source.metadata__.get("id") or source.title
                if ds_id:
                    # Try to load the first config and a few rows
                    configs = get_dataset_config_names(ds_id)
                    config = configs[0] if configs else "default"
                    # Load streaming slice to get a few rows
                    ds = load_dataset(
                        ds_id,
                        config,
                        split="train",
                        streaming=True,
                        trust_remote_code=True,
                    )
                    head = list(ds.take(3))
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
                            content = f"Dataset: {source.title}\nDescription: {source.description or ''}\n\nSample data (first {len(head)} rows):\n{sample_content}"
                            extracted = ExtractedContent(
                                content=content,
                                content_type="huggingface_dataset_sample",
                                language="en",
                                url=source.url,
                                confidence=0.9,
                                metadata={
                                    "downloads": source.metadata__.get("downloads", 0),
                                    "tags": source.metadata__.get("tags", []),
                                    "author": source.metadata__.get("author", ""),
                                    "source_type": "huggingface_dataset",
                                    "fetched_via_sdk": True,
                                    "sample_rows_used": len(head)
                                }
                            )
                            yield extracted
                            return
            except Exception as sdk_err:
                # SDK not available or failed; fall back to metadata with low confidence
                self._LOG.debug(f"HF SDK sample extraction failed for {source.url}: {sdk_err}")
                pass
            # Fallback: do not yield metadata-only content to avoid irrelevant data
            # Under-delivering with no data is better than including irrelevant metadata
            return
        except Exception as e:
            self._LOG.warning(f"HuggingFace extraction failed: {e}")
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

    async def extract_from_kaggle(self, source) -> AsyncGenerator[ExtractedContent, None]:
        """Extract actual dataset files from Kaggle, not just metadata."""
        try:
            # Try to use kagglehub to download and access actual dataset files
            try:
                import kagglehub

                # Get the dataset reference from the URL or metadata
                dataset_ref = None
                if hasattr(source, 'metadata__') and source.metadata__.get('kaggle_dataset_ref'):
                    dataset_ref = source.metadata__['kaggle_dataset_ref']
                elif source.url:
                    # Extract from URL like https://kaggle.com/datasets/username/dataset-name
                    import re
                    match = re.search(r'/datasets/([^/]+/[^/]+)', source.url)
                    if match:
                        dataset_ref = match.group(1)

                if dataset_ref:
                    # Download the dataset to access actual files
                    path = kagglehub.dataset_download(dataset_ref)

                    # Read common file types to extract content
                    import os
                    content_parts = [f"Dataset: {source.title}", f"Description: {source.description or ''}"]

                    # Look for CSV, JSON, text files to extract actual data
                    for root, dirs, files in os.walk(path):
                        for file in files[:5]:  # Limit to first 5 files to avoid too much data
                            file_path = os.path.join(root, file)
                            file_ext = os.path.splitext(file)[1].lower()

                            try:
                                if file_ext == '.csv':
                                    import pandas as pd
                                    df = pd.read_csv(file_path, nrows=5)  # First 5 rows
                                    content_parts.append(f"\nFile: {file}\n{df.to_string()}")
                                elif file_ext == '.json':
                                    with open(file_path, 'r') as f:
                                        data = json.load(f)
                                        content_parts.append(f"\nFile: {file}\n{json.dumps(data, indent=2)[:500]}")
                                elif file_ext in ['.txt', '.md', '.py', '.r', '.java', '.cpp', '.c', '.html']:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        file_content = f.read(1000)  # First 1000 chars
                                        content_parts.append(f"\nFile: {file}\n{file_content}")
                            except Exception as file_e:
                                self._LOG.debug(f"Could not read file {file}: {file_e}")
                                continue

                    content = "\n".join(content_parts)
                    extracted = await self._process_text(content, source.url, "utf-8")
                    extracted.metadata["source_type"] = "kaggle_dataset"
                    extracted.metadata["local_path"] = path
                    extracted.confidence = 0.8  # High confidence since we have actual data
                    yield extracted
                    return

            except ImportError:
                self._LOG.debug("kagglehub not installed, falling back to metadata")
            except Exception as kaggle_e:
                self._LOG.warning(f"Kaggle dataset access failed: {kaggle_e}")

            # If we can't access actual dataset files, don't yield anything
            # This prevents metadata from being used as dataset content
            pass

        except Exception as e:
            self._LOG.warning(f"Kaggle extraction failed: {e}")
            yield ExtractedContent(
                content="",
                content_type="error",
                confidence=0.0,
                url=source.url,
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

                        content_parts = [f"Dataset: {data.get('metadata', {}).get('title', source.title or '')}"]
                        description = data.get('metadata', {}).get('description', '')
                        if description:
                            # Clean HTML tags from description
                            import re
                            clean_description = re.sub('<[^<]+?>', '', description)
                            content_parts.append(f"Description: {clean_description[:500]}")

                        # Try to get actual files
                        files = data.get('files', [])
                        if files:
                            content_parts.append("\nAvailable files:")
                            for file_info in files[:3]:  # First 3 files
                                file_name = file_info.get('key', 'unknown')
                                file_size = file_info.get('size', 0)
                                content_parts.append(f"- {file_name} ({file_size} bytes)")

                                # Try to download and read small text files
                                if file_size < 100000:  # Only files < 100KB
                                    file_url = file_info.get('links', {}).get('self')
                                    if file_url:
                                        try:
                                            file_response = await client.get(file_url)
                                            if file_response.status_code == 200:
                                                file_content = file_response.text[:500]  # First 500 chars
                                                content_parts.append(f"  Sample content: {file_content}")
                                        except Exception:
                                            pass

                        content = "\n".join(content_parts)
                        extracted = await self._process_text(content, source.url, "utf-8")
                        extracted.metadata["source_type"] = "zenodo"
                        extracted.metadata["zenodo_id"] = zenodo_id
                        # Medium confidence - we have structured info but not full file contents for large files
                        extracted.confidence = 0.6
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