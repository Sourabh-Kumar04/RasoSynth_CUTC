"""Tests for the pipeline export module."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.export import ExportPipeline, ExportConfig


class Sample:
    """Mock sample for testing."""
    def __init__(self, instruction="inst", response="resp", input="", metadata=None, difficulty_tier=3, curriculum_order=0):
        self.instruction = instruction
        self.response = response
        self.input = input
        self.metadata = metadata or {}
        self.difficulty_tier = difficulty_tier
        self.curriculum_order = curriculum_order


@pytest.fixture
def samples():
    return [
        Sample("What is Python?", "A programming language."),
        Sample("What is AI?", "Artificial Intelligence."),
    ]


@pytest.fixture
def tmp_path(tmp_path) -> Path:
    return tmp_path


class TestExportPipeline:
    async def test_export_jsonl(self, samples, tmp_path):
        config = ExportConfig(format="jsonl", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-1")
        assert "dataset" in result
        assert result["dataset"].suffix == ".jsonl"
        assert result["dataset"].exists()

    async def test_export_csv(self, samples, tmp_path):
        config = ExportConfig(format="csv", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-2")
        assert "dataset" in result
        assert result["dataset"].suffix == ".csv"
        assert result["dataset"].exists()

    async def test_export_parquet(self, samples, tmp_path):
        config = ExportConfig(format="parquet", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-3")
        assert "dataset" in result
        assert result["dataset"].suffix == ".parquet"
        assert result["dataset"].exists()

    async def test_export_huggingface(self, samples, tmp_path):
        config = ExportConfig(format="huggingface", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-4")
        assert "dataset" in result
        assert result["dataset"].is_dir()

    async def test_export_s3(self, samples, tmp_path):
        """S3 export should upload files and return s3:// URL."""
        config = ExportConfig(
            format="jsonl",
            output_dir=tmp_path,
            s3_bucket="my-bucket",
            s3_region="us-west-2",
        )
        pipeline = ExportPipeline(config)
        with patch("pipeline.export.boto3") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.client.return_value = mock_s3
            result = await pipeline.export(samples, "job-s3", format="s3")
            assert result["dataset"].startswith("s3://")
            # upload_file should be called at least once for each exported file
            assert mock_s3.upload_file.call_count >= 1

    async def test_export_hf_hub(self, samples, tmp_path):
        config = ExportConfig(
            format="jsonl",
            output_dir=tmp_path,
            dataset_name="test-dataset",
            hf_dataset_org="test-org",
            hf_token="fake-token",
        )
        pipeline = ExportPipeline(config)
        # Patch the actual module where the imports happen inside the method
        with patch("huggingface_hub.create_repo") as mock_create_repo, \
             patch("huggingface_hub.HfApi") as mock_hf_api:
            # HfApi mock instance with upload_file method
            mock_api_instance = MagicMock()
            mock_hf_api.return_value = mock_api_instance
            result = await pipeline.export(samples, "job-hf", format="hf_hub")
            assert "https://huggingface.co/datasets/" in result["dataset"]
            mock_create_repo.assert_called_once()

    async def test_export_kaggle(self, samples, tmp_path):
        config = ExportConfig(
            format="jsonl",
            output_dir=tmp_path,
            dataset_name="test-dataset",
            kaggle_username="testuser",
            kaggle_key="fake-key",
        )
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-kaggle", format="kaggle")
        assert "https://www.kaggle.com/datasets/" in result["dataset"]

    async def test_export_empty_samples(self, tmp_path):
        config = ExportConfig(format="jsonl", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export([], "job-empty")
        assert "dataset" in result
        assert result["dataset"].exists()
