"""
Tests for the quality benchmark suite.
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

from research.quality_benchmark import QualityBenchmark, BenchmarkResults


class TestBenchmarkResults:
    """Tests for the BenchmarkResults container."""

    def test_initialization(self):
        """Test that BenchmarkResults initializes with empty state."""
        br = BenchmarkResults()
        assert br.results == {}
        assert br.timestamps == {}

    def test_add(self):
        """Test adding a benchmark result."""
        br = BenchmarkResults()
        br.add("test_bench", {"status": "completed", "score": 95})
        assert "test_bench" in br.results
        assert br.results["test_bench"]["score"] == 95
        assert "test_bench" in br.timestamps

    def test_to_dict(self):
        """Test conversion to dictionary."""
        br = BenchmarkResults()
        br.add("bench1", {"score": 10})
        result = br.to_dict()
        assert "results" in result
        assert "timestamps" in result
        assert "generated_at" in result
        assert result["results"]["bench1"]["score"] == 10


class TestQualityBenchmark:
    """Tests for the QualityBenchmark suite."""

    @pytest.fixture
    def benchmark(self):
        """Create a QualityBenchmark instance."""
        return QualityBenchmark()

    def test_initialization(self, benchmark):
        """Test initialization with default config."""
        assert benchmark.config == {}
        assert isinstance(benchmark.results, BenchmarkResults)

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = {"target_domain": "test", "max_samples": 100}
        bm = QualityBenchmark(config=config)
        assert bm.config["target_domain"] == "test"
        assert bm.config["max_samples"] == 100

    @pytest.mark.asyncio
    async def test_run_all(self, benchmark):
        """Test run_all returns results dict."""
        results = await benchmark.run_all()
        assert "results" in results
        assert "timestamps" in results
        assert "generated_at" in results
        # Ensure all benchmarks were recorded
        assert "benchmark_generation_quality" in results["results"]
        assert "benchmark_latency" in results["results"]
        assert "benchmark_provider_quality" in results["results"]
        assert "benchmark_cost_efficiency" in results["results"]

    @pytest.mark.asyncio
    async def test_benchmark_generation_quality(self, benchmark):
        """Test generation quality benchmark returns expected structure."""
        result = await benchmark.benchmark_generation_quality()
        assert result["status"] == "not_implemented"

    @pytest.mark.asyncio
    async def test_benchmark_latency(self, benchmark):
        """Test latency benchmark returns expected structure."""
        result = await benchmark.benchmark_latency()
        assert result["status"] == "not_implemented"

    @pytest.mark.asyncio
    async def test_benchmark_provider_quality(self, benchmark):
        """Test provider quality benchmark returns expected structure."""
        result = await benchmark.benchmark_provider_quality()
        assert result["status"] == "not_implemented"

    @pytest.mark.asyncio
    async def test_benchmark_cost_efficiency(self, benchmark):
        """Test cost efficiency benchmark returns expected structure."""
        result = await benchmark.benchmark_cost_efficiency()
        assert result["status"] == "not_implemented"

    @pytest.mark.asyncio
    async def test_benchmark_dataset_quality(self, benchmark):
        """Test dataset quality benchmarking with a real file."""
        # Create a temporary JSONL dataset
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps({"instruction": "Solve 2+2", "response": "4"}) + "\n")
            f.write(json.dumps({"instruction": "Define AI", "response": "Artificial Intelligence"}) + "\n")
            f.write(json.dumps({"instruction": "What is Python?", "response": "A programming language"}) + "\n")
            temp_path = f.name

        try:
            result = await benchmark.benchmark_dataset_quality(temp_path)
            assert result["total_samples"] == 3
            assert result["avg_instruction_length"] > 0
            assert result["avg_response_length"] > 0
            assert result["unique_instructions"] == 3
            assert result["path"] == temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_benchmark_dataset_quality_empty_file(self, benchmark):
        """Test dataset quality with empty file returns error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name

        try:
            result = await benchmark.benchmark_dataset_quality(temp_path)
            assert "error" in result
            assert result["error"] == "empty_dataset"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_benchmark_dataset_quality_calculates_metrics_correctly(self, benchmark):
        """Test that quality metrics are calculated correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps({"instruction": "A", "response": "B"}) + "\n")
            f.write(json.dumps({"instruction": "BB", "response": "CC"}) + "\n")
            temp_path = f.name

        try:
            result = await benchmark.benchmark_dataset_quality(temp_path)
            assert result["avg_instruction_length"] == 1.5  # (1 + 2) / 2
            assert result["avg_response_length"] == 1.5  # (1 + 2) / 2
            assert result["min_instruction_length"] == 1
            assert result["max_response_length"] == 2
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_generate_report_with_results(self, benchmark):
        """Test report generation with provided results."""
        results = {
            "results": {
                "test_bench": {
                    "status": "completed",
                    "score": 95,
                    "samples": 100,
                }
            },
            "timestamps": {"test_bench": "2026-01-01T00:00:00"},
            "generated_at": "2026-01-01T00:00:00",
        }
        report = benchmark.generate_report(results)
        assert "# Quality Benchmark Report" in report
        assert "## Summary" in report
        assert "### test_bench" in report
        assert "completed" in report
        assert "95" in report
        assert "100" in report

    def test_generate_report_empty_results(self, benchmark):
        """Test report generation with no results."""
        report = benchmark.generate_report({"results": {}, "timestamps": {}, "generated_at": "now"})
        assert "# Quality Benchmark Report" in report
        assert "## Summary" in report

    def test_generate_report_uses_stored_results(self, benchmark):
        """Test that generate_report uses stored results when none provided."""
        benchmark.results.add("auto_bench", {"status": "completed", "metric": 42})
        report = benchmark.generate_report()
        assert "auto_bench" in report
        assert "42" in report

    @pytest.mark.asyncio
    async def test_run_all_populates_results(self, benchmark):
        """Test that run_all populates the internal results container."""
        await benchmark.run_all()
        assert len(benchmark.results.results) >= 4


class TestQualityBenchmarkEdgeCases:
    """Edge case tests for QualityBenchmark."""

    @pytest.mark.asyncio
    async def test_benchmark_dataset_quality_duplicate_instructions(self):
        """Test that duplicate instructions are counted correctly."""
        bm = QualityBenchmark()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps({"instruction": "Same", "response": "A"}) + "\n")
            f.write(json.dumps({"instruction": "Same", "response": "B"}) + "\n")
            f.write(json.dumps({"instruction": "Same", "response": "C"}) + "\n")
            temp_path = f.name

        try:
            result = await bm.benchmark_dataset_quality(temp_path)
            assert result["total_samples"] == 3
            assert result["unique_instructions"] == 1
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_benchmark_dataset_quality_missing_fields(self):
        """Test dataset with missing instruction/response fields."""
        bm = QualityBenchmark()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps({"instruction": "Hi"}) + "\n")  # No response
            f.write(json.dumps({"response": "Hello"}) + "\n")  # No instruction
            f.write(json.dumps({}) + "\n")  # Empty object
            temp_path = f.name

        try:
            result = await bm.benchmark_dataset_quality(temp_path)
            assert result["total_samples"] == 3
            # Missing fields should be treated as empty strings
            assert result["avg_instruction_length"] >= 0
            assert result["avg_response_length"] >= 0
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_large_dataset_benchmark_performance(self):
        """Test that dataset quality benchmarking handles larger files."""
        bm = QualityBenchmark()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for i in range(1000):
                f.write(json.dumps({
                    "instruction": f"Instruction number {i}",
                    "response": f"Response for instruction {i} " * 5,
                }) + "\n")
            temp_path = f.name

        try:
            start = time.time()
            result = await bm.benchmark_dataset_quality(temp_path)
            elapsed = time.time() - start

            assert result["total_samples"] == 1000
            assert result["unique_instructions"] == 1000
            assert elapsed < 5.0, "Benchmarking 1000 samples should complete in under 5 seconds"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_generate_report_handles_missing_status(self, benchmark):
        """Test generate_report handles results with no status field."""
        results = {
            "results": {"some_bench": {"value": 10}},
            "timestamps": {},
            "generated_at": "now",
        }
        report = benchmark.generate_report(results)
        assert "completed" in report  # Default status
        assert "10" in report