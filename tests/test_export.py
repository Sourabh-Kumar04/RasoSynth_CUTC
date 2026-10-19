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

    async def test_export_sql(self, samples, tmp_path):
        config = ExportConfig(format="sql", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-sql", format="sql")
        assert "dataset" in result
        assert result["dataset"].exists()
        content = result["dataset"].read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS dataset_job_sql" in content
        assert "INSERT INTO dataset_job_sql" in content

    async def test_export_qdrant(self, samples, tmp_path):
        config = ExportConfig(format="qdrant", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-qdrant", format="qdrant")
        assert "dataset" in result
        assert result["dataset"].exists()
        import json
        payload = json.loads(result["dataset"].read_text(encoding="utf-8"))
        assert payload["collection_name"] == "dataset_job-qdrant"
        assert len(payload["points"]) == len(samples)
        assert "payload" in payload["points"][0]

    async def test_export_alpaca_format(self, samples, tmp_path):
        import json
        config = ExportConfig(format="jsonl", instruction_format="alpaca", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-alpaca")
        lines = result["dataset"].read_text(encoding="utf-8").strip().splitlines()
        first = json.loads(lines[0])
        assert "instruction" in first
        assert "response" in first
        assert first["instruction"] == "What is Python?"

    async def test_export_sharegpt_format(self, samples, tmp_path):
        import json
        config = ExportConfig(format="jsonl", instruction_format="sharegpt", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-sharegpt")
        lines = result["dataset"].read_text(encoding="utf-8").strip().splitlines()
        first = json.loads(lines[0])
        assert "conversations" in first
        assert len(first["conversations"]) == 2
        assert first["conversations"][0]["from"] == "human"
        assert first["conversations"][0]["value"] == "What is Python?"
        assert first["conversations"][1]["from"] == "gpt"
        assert first["conversations"][1]["value"] == "A programming language."

    async def test_export_chatml_format(self, samples, tmp_path):
        import json
        config = ExportConfig(format="jsonl", instruction_format="chatml", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-chatml")
        lines = result["dataset"].read_text(encoding="utf-8").strip().splitlines()
        first = json.loads(lines[0])
        assert "messages" in first
        assert "text" in first
        assert "<|im_start|>user" in first["text"]
        assert "<|im_start|>assistant" in first["text"]

    async def test_export_openai_jsonl_format(self, samples, tmp_path):
        import json
        config = ExportConfig(format="jsonl", instruction_format="openai_jsonl", output_dir=tmp_path)
        pipeline = ExportPipeline(config)
        result = await pipeline.export(samples, "job-openai")
        lines = result["dataset"].read_text(encoding="utf-8").strip().splitlines()
        first = json.loads(lines[0])
        assert "messages" in first
        roles = [m["role"] for m in first["messages"]]
        assert "system" in roles
        assert "user" in roles
        assert "assistant" in roles

