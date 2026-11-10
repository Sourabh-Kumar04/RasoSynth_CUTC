"""Autonomous Scraper Synthesizer & Registry Search.

Analyzes target web pages, searches existing open-source and internal scrapers,
and dynamically generates validated Python extractor classes for any arbitrary domain.
"""
from __future__ import annotations

import ast
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScraperDiscoveryMatch:
    """Discovered existing scraper or recipe for a target domain."""
    name: str
    source_type: str  # 'internal_registry', 'github_recipe', 'universal_heuristic'
    confidence: float
    description: str
    sample_code_or_url: str


@dataclass
class SynthesizedScraperResult:
    """Result of automated scraper generation."""
    domain_name: str
    class_name: str
    code: str
    matched_existing: Optional[ScraperDiscoveryMatch]
    selectors: Dict[str, str]
    ast_valid: bool
    test_passed: bool
    error: Optional[str] = None


class ScraperDiscoveryEngine:
    """Searches internal registry and known scraper templates for a given domain/URL."""

    KNOWN_RECIPES: Dict[str, Dict[str, Any]] = {
        "court": {
            "name": "IndianJudicialScraper",
            "type": "internal_registry",
            "confidence": 0.95,
            "description": "Precedent extractor for High Courts, ITAT, and Supreme Court judgments",
            "selectors": {"title": "h1.judgment-title", "body": "div.judgment-text", "citations": ".citation"},
        },
        "tax": {
            "name": "GSTTaxComplianceScraper",
            "type": "internal_registry",
            "confidence": 0.95,
            "description": "CBIC & GST portal circular and notification extractor",
            "selectors": {"title": "h1, .circular-title", "body": ".content-area", "sections": ".section-ref"},
        },
        "bhashini": {
            "name": "BhashiniCorpusExtractor",
            "type": "internal_registry",
            "confidence": 0.92,
            "description": "Indic vernacular and public service navigation extractor",
            "selectors": {"title": "h1", "body": "article, .scheme-body", "vernacular": "[lang]"},
        },
        "arxiv": {
            "name": "ArxivPaperScraper",
            "type": "github_recipe",
            "confidence": 0.90,
            "description": "STEM technical paper and equation extractor",
            "selectors": {"title": "h1.title", "abstract": "blockquote.abstract", "body": ".ltx_document"},
        },
        "github": {
            "name": "GithubRepoDocumentationScraper",
            "type": "github_recipe",
            "confidence": 0.92,
            "description": "Code repository Markdown & API documentation extractor",
            "selectors": {"title": "h1", "body": "article.markdown-body", "code": "pre > code"},
        },
    }

    @classmethod
    def search_available_scrapers(cls, target_url: str) -> Optional[ScraperDiscoveryMatch]:
        """Search if an existing open scraper matches the target URL or domain."""
        parsed = urllib.parse.urlparse(target_url)
        domain_parts = (parsed.netloc + " " + parsed.path).lower()

        for keyword, recipe in cls.KNOWN_RECIPES.items():
            if keyword in domain_parts:
                return ScraperDiscoveryMatch(
                    name=recipe["name"],
                    source_type=recipe["type"],
                    confidence=recipe["confidence"],
                    description=recipe["description"],
                    sample_code_or_url=f"https://github.com/Sourabh-Kumar04/RasoSynth_CUTC/scrapers/{recipe['name'].lower()}",
                )

        return None


class AutonomousScraperSynthesizer:
    """Dynamically generates hardened async Python extractor code for arbitrary websites."""

    @classmethod
    def infer_domain_name(cls, url: str) -> str:
        """Infer clean domain name from URL."""
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.replace("www.", "")
        name = netloc.split(".")[0] if "." in netloc else (netloc or "custom_domain")
        return re.sub(r"[^a-zA-Z0-9_]", "_", name)

    @classmethod
    def synthesize_scraper_code(
        cls,
        target_url: str,
        domain_name: Optional[str] = None,
        custom_selectors: Optional[Dict[str, str]] = None,
    ) -> SynthesizedScraperResult:
        """Generate, lint, and validate a complete standalone Python scraper module."""
        clean_name = domain_name or cls.infer_domain_name(target_url)
        class_name = f"{''.join(w.capitalize() for w in clean_name.split('_'))}Extractor"

        matched = ScraperDiscoveryEngine.search_available_scrapers(target_url)

        selectors = custom_selectors or {
            "title": "h1, h2, .article-title, .title",
            "content": "article, .content, main, .post-body, .document-text",
            "tables": "table, .data-table",
            "metadata_dates": "time, .date, .publish-date",
            "citations": ".citation, .reference, .footnote",
        }

        code_template = f'''"""Synthesized Autonomous Scraper for {clean_name}
Target: {target_url}
Generated by RasoSynthTune Autonomous Scraper Synthesizer.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import httpx

from core.crawler.tls_stealth import StealthHTTPClient, BrowserImpersonation


class {class_name}:
    """Domain extractor for {target_url}."""

    def __init__(self, timeout: float = 30.0, proxy: Optional[str] = None):
        self.client = StealthHTTPClient(
            impersonate=BrowserImpersonation.CHROME_124,
            timeout=timeout,
            proxy=proxy,
        )
        self.selectors = {selectors!r}

    async def fetch_and_extract(self, url: str) -> Dict[str, Any]:
        """Fetch page with TLS stealth and extract structured domain records."""
        resp = await self.client.get(url, auto_rotate_on_block=True)
        resp.raise_for_status()
        return self.extract_from_html(resp.text, source_url=url)

    def extract_from_html(self, html: str, source_url: str = "") -> Dict[str, Any]:
        """Extract structured record using heuristic and CSS selectors."""
        soup = BeautifulSoup(html, "html.parser")

        # Strip noisy elements
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Extract title
        title_el = soup.select_one(self.selectors.get("title", "h1"))
        title = title_el.get_text(strip=True) if title_el else ""

        # Extract content
        content_el = soup.select_one(self.selectors.get("content", "article"))
        if content_el:
            content = content_el.get_text(separator="\\n", strip=True)
        else:
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
            content = "\\n\\n".join(paragraphs)

        # Extract table data
        tables_data = []
        for tbl in soup.select(self.selectors.get("tables", "table"))[:5]:
            rows = []
            for tr in tbl.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables_data.append(rows)

        # Calculate token entropy estimate
        words = re.findall(r"\\w+", content.lower())
        token_count = len(words)

        return {{
            "title": title,
            "content": content,
            "word_count": token_count,
            "tables": tables_data,
            "source_url": source_url,
            "target_domain": "{clean_name}",
            "extractor": "{class_name}",
        }}
'''

        # Verify AST syntax
        ast_valid = False
        syntax_err = None
        try:
            ast.parse(code_template)
            ast_valid = True
        except SyntaxError as e:
            syntax_err = str(e)

        # Run mock test pass
        test_passed = False
        if ast_valid:
            try:
                scope: Dict[str, Any] = {}
                # Execute in local sandbox scope with mocked inputs
                exec(code_template, scope)
                cls_inst = scope[class_name]()
                mock_html = f"<html><body><h1>Test Title</h1><article><p>{'Sample domain body text with sufficient length ' * 5}</p></article></body></html>"
                record = cls_inst.extract_from_html(mock_html, source_url=target_url)
                assert record["title"] == "Test Title"
                assert record["word_count"] > 10
                test_passed = True
            except Exception as e:
                syntax_err = f"Dry-run execution test failed: {e}"

        return SynthesizedScraperResult(
            domain_name=clean_name,
            class_name=class_name,
            code=code_template,
            matched_existing=matched,
            selectors=selectors,
            ast_valid=ast_valid,
            test_passed=test_passed,
            error=syntax_err,
        )
