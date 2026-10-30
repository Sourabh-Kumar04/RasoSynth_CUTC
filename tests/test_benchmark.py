"""
Tests for the quality benchmark suite.
"""
import json
import tempfile
import time
from pathlib import Path

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
        assert result["status"] == "completed"
        assert "samples_evaluated" in result

    @pytest.mark.asyncio
    async def test_benchmark_latency(self, benchmark):
        """Test latency benchmark returns expected structure."""
        result = await benchmark.benchmark_latency()
        assert result["status"] == "completed"
        assert "throughput_samples_per_sec" in result

    @pytest.mark.asyncio
    async def test_benchmark_provider_quality(self, benchmark):
        """Test provider quality benchmark returns expected structure."""
        result = await benchmark.benchmark_provider_quality()
        assert result["status"] == "completed"
        assert "supported_providers" in result

    @pytest.mark.asyncio
    async def test_benchmark_cost_efficiency(self, benchmark):
        """Test cost efficiency benchmark returns expected structure."""
        result = await benchmark.benchmark_cost_efficiency()
        assert result["status"] == "completed"
        assert "cost_reduction_pct" in result

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

    @pytest.fixture
    def benchmark(self):
        """Create a QualityBenchmark instance."""
        return QualityBenchmark()

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

    @pytest.mark.asyncio
    async def test_compare_datasets(self, benchmark):
        """Test comparing a raw dataset with a refined dataset."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f_raw:
            f_raw.write(json.dumps({"instruction": "repeat", "response": "dup"}) + "\n")
            f_raw.write(json.dumps({"instruction": "repeat", "response": "dup"}) + "\n")
            raw_path = f_raw.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f_ref:
            f_ref.write(json.dumps({"instruction": "unique task A", "response": "detailed output A"}) + "\n")
            f_ref.write(json.dumps({"instruction": "unique task B", "response": "detailed output B"}) + "\n")
            ref_path = f_ref.name

        try:
            comparison = await benchmark.compare_datasets(raw_path, ref_path)
            assert "raw_dataset" in comparison
            assert "refined_dataset" in comparison
            assert "improvements" in comparison
            assert comparison["improvements"]["uniqueness_improvement_pct"] > 0
            assert "verdict" in comparison
        finally:
            Path(raw_path).unlink(missing_ok=True)
            Path(ref_path).unlink(missing_ok=True)


class TestP1_16StatisticalValidation:
    """Welch t-test significance/CIs and computed (not hardcoded) verdicts."""

    def test_welch_clearly_different_vs_identical(self):
        from research.benchmarking import welch_t_test

        different = welch_t_test([10.0, 10.2, 9.8, 10.1, 9.9], [12.0, 12.3, 11.8, 12.1, 11.9])
        assert different["p_value"] is not None and different["p_value"] < 0.05
        assert different["ci_low"] < different["mean_diff"] < different["ci_high"]
        identical = welch_t_test([1.0, 1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0, 1.0])
        assert identical["p_value"] == 1.0
        assert welch_t_test([1.0], [2.0, 3.0])["p_value"] is None

    @pytest.mark.asyncio
    async def test_runner_significance_uses_p_value(self):
        from research.benchmarking import BenchmarkCategory, BenchmarkConfig, BenchmarkRunner

        async def base(metric, ctx):
            return {metric: 10.0}

        async def var(metric, ctx):
            return {metric: 12.0}

        runner = BenchmarkRunner()
        comp = await runner.run_comparison(
            BenchmarkConfig(name="t", category=BenchmarkCategory.QUALITY, baseline_fn=base,
                            variant_fn=var, metric_names=["m"], iterations=5, warmup_iterations=0)
        )
        assert comp.metrics[0].statistical_test == "welch_t_test"
        assert comp.metrics[0].p_value == 0.0

    @pytest.mark.asyncio
    async def test_compare_datasets_verdict_follows_deltas(self):
        import json as _json
        import tempfile as _tf

        benchmark = QualityBenchmark()

        with _tf.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f_raw:
            f_raw.write(_json.dumps({"instruction": "unique task A", "response": "detailed output A"}) + "\n")
            f_raw.write(_json.dumps({"instruction": "unique task B", "response": "detailed output B"}) + "\n")
            raw_path = f_raw.name
        with _tf.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f_ref:
            f_ref.write(_json.dumps({"instruction": "repeat", "response": "dup"}) + "\n")
            f_ref.write(_json.dumps({"instruction": "repeat", "response": "dup"}) + "\n")
            ref_path = f_ref.name
        try:
            worse = await benchmark.compare_datasets(raw_path, ref_path)
            assert "lower" in worse["verdict"]
            assert "demonstrated higher diversity" not in worse["verdict"]
        finally:
            Path(raw_path).unlink(missing_ok=True)
            Path(ref_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_provider_quality_is_demo_flagged(self):
        benchmark = QualityBenchmark()
        result = await benchmark.benchmark_provider_quality()
        assert result["demo"] is True
        assert result["documents_evaluated"] == 1
        assert result["corpus_type"] == "single_hardcoded_document"
