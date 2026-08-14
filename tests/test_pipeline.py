"""Tests for pipeline stages."""
import pytest
from pipeline.discovery import DiscoveryPipeline, DiscoveredSource, SourceType
from pipeline.extraction import ExtractionPipeline, ExtractedContent
from pipeline.filtering import FilteringPipeline, FilteredSample
from pipeline.construction import ConstructionPipeline, ConstructedSample, DatasetType
from pipeline.export import ExportPipeline, ExportConfig
from pathlib import Path


def test_discovered_source():
    """Test DiscoveredSource dataclass."""
    source = DiscoveredSource(
        url="https://example.com",
        source_type=SourceType.WEB_PAGE,
        title="Example",
        description="Test description"
    )

    assert source.url == "https://example.com"
    assert source.source_type == SourceType.WEB_PAGE


def test_extracted_content():
    """Test ExtractedContent dataclass."""
    content = ExtractedContent(
        content="Test content",
        content_type="text",
        language="en",
        url="https://example.com",
        confidence=0.9
    )

    assert content.content == "Test content"
    assert content.confidence == 0.9


def test_filtered_sample():
    """Test FilteredSample dataclass."""
    sample = FilteredSample(
        content="Test content",
        quality_score=0.8,
        relevance_score=0.9,
        toxicity_score=0.1
    )

    assert sample.quality_score == 0.8
    assert len(sample.issues) == 0


def test_constructed_sample():
    """Test ConstructedSample dataclass."""
    sample = ConstructedSample(
        instruction="Test instruction",
        response="Test response",
        difficulty_tier=3,
        curriculum_order=1
    )

    assert sample.instruction == "Test instruction"
    assert sample.difficulty_tier == 3


def test_export_config():
    """Test ExportConfig dataclass."""
    config = ExportConfig(
        format="jsonl",
        output_dir=Path("outputs"),
        dataset_name="test_dataset"
    )

    assert config.format == "jsonl"
    assert config.dataset_name == "test_dataset"


@pytest.mark.asyncio
async def test_discovery_pipeline_init():
    """Test DiscoveryPipeline initialization."""
    config = {"allowed_domains": ["example.com"], "blocked_domains": ["spam.com"]}
    pipeline = DiscoveryPipeline(config)

    assert pipeline.domain_allowlist == ["example.com"]
    assert "facebook.com" in pipeline.domain_blocklist


@pytest.mark.asyncio
async def test_extraction_pipeline_init():
    """Test ExtractionPipeline initialization."""
    config = {"timeout": 60}
    pipeline = ExtractionPipeline(config)

    assert pipeline.timeout == 60


@pytest.mark.asyncio
async def test_filtering_pipeline_init():
    """Test FilteringPipeline initialization."""
    config = {"quality_threshold": 0.5, "toxicity_threshold": 0.7}
    pipeline = FilteringPipeline(None, config)

    assert pipeline.quality_threshold == 0.5
    assert pipeline.toxicity_threshold == 0.7


def test_construction_pipeline_dataset_types():
    """Test ConstructionPipeline supports all dataset types."""
    for dtype in DatasetType:
        config = {"dataset_type": dtype.value}
        pipeline = ConstructionPipeline(None, config)
        assert pipeline.dataset_type == dtype


def test_export_pipeline_init():
    """Test ExportPipeline initialization."""
    config = ExportConfig(
        format="jsonl",
        output_dir=Path("outputs"),
        dataset_name="test"
    )
    pipeline = ExportPipeline(config)

    assert pipeline.output_dir.name == "outputs"