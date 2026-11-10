"""Tests for the Autonomous Scraper Code Synthesizer Harness."""
import pytest
from core.crawler.scraper_synthesizer import (
    AutonomousScraperSynthesizer,
    ScraperDiscoveryEngine,
    ScraperDiscoveryMatch,
    SynthesizedScraperResult,
)


def test_scraper_discovery_engine_known_recipes():
    """Verify discovery engine matches known domain recipes."""
    # Test legal / court domain match
    match_court = ScraperDiscoveryEngine.search_available_scrapers("https://delhihighcourt.nic.in/court/judgments")
    assert match_court is not None
    assert match_court.name == "IndianJudicialScraper"
    assert match_court.confidence >= 0.9

    # Test tax portal match
    match_tax = ScraperDiscoveryEngine.search_available_scrapers("https://taxinformation.cbic.gov.in/circulars")
    assert match_tax is not None
    assert match_tax.name == "GSTTaxComplianceScraper"

    # Test STEM arxiv match
    match_arxiv = ScraperDiscoveryEngine.search_available_scrapers("https://arxiv.org/abs/2401.12345")
    assert match_arxiv is not None
    assert match_arxiv.name == "ArxivPaperScraper"

    # Test unmapped domain returns None
    match_unknown = ScraperDiscoveryEngine.search_available_scrapers("https://random-niche-shipping-service.com/terms")
    assert match_unknown is None


def test_autonomous_scraper_synthesizer_code_generation():
    """Verify zero-shot code generation, AST parsing, and sandboxed test execution."""
    result: SynthesizedScraperResult = AutonomousScraperSynthesizer.synthesize_scraper_code(
        target_url="https://maritime-regulations-authority.org/rules",
        domain_name="maritime_regulations",
    )

    assert result.domain_name == "maritime_regulations"
    assert result.class_name == "MaritimeRegulationsExtractor"
    assert result.ast_valid is True
    assert result.test_passed is True
    assert result.error is None
    assert "class MaritimeRegulationsExtractor:" in result.code
    assert "StealthHTTPClient" in result.code
    assert "def extract_from_html" in result.code


def test_synthesized_scraper_extraction_logic():
    """Verify the synthesized class correctly parses structured HTML and extracts records."""
    result = AutonomousScraperSynthesizer.synthesize_scraper_code(
        target_url="https://agritech-crops.gov.in/soil-health",
        domain_name="agritech_soil",
    )

    # Execute generated code in clean scope
    scope = {}
    exec(result.code, scope)
    extractor_cls = scope[result.class_name]
    extractor = extractor_cls()

    mock_html = """
    <html>
        <head><title>Page</title></head>
        <body>
            <h1>Soil Health Assessment Card 2026</h1>
            <article>
                <p>Nitrogen, Phosphorus, and Potassium NPK soil testing guidelines for high-yield cereal crops.</p>
                <p>Recommended macro-nutrient ratios and soil pH balance thresholds across alluvial tracts.</p>
                <table>
                    <tr><th>Nutrient</th><th>Optimal PPM</th></tr>
                    <tr><td>Nitrogen</td><td>280-560</td></tr>
                    <tr><td>Phosphorus</td><td>23-56</td></tr>
                </table>
            </article>
        </body>
    </html>
    """

    record = extractor.extract_from_html(mock_html, source_url="https://agritech-crops.gov.in/soil-health")
    assert record["title"] == "Soil Health Assessment Card 2026"
    assert "Nitrogen, Phosphorus, and Potassium" in record["content"]
    assert record["target_domain"] == "agritech_soil"
    assert len(record["tables"]) == 1
    assert record["tables"][0][1] == ["Nitrogen", "280-560"]
