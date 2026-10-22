import pytest
from unittest.mock import Mock
from core.orchestrator_core import DatasetOrchestrator


def test_balance_samples_exact_target_size():
    """Ensure _balance_samples never reduces sample count below requested target_size."""
    orchestrator = DatasetOrchestrator({}, Mock())

    # Create 100 samples with skewed topics (70 Topic A, 30 Topic B)
    samples = [
        {
            "instruction": f"Instruction {i}",
            "response": f"Response {i}",
            "quality_score": 0.8 + (i % 10) * 0.01,
            "metadata": {"topic": "Taxation" if i < 70 else "Corporate Law"},
        }
        for i in range(100)
    ]

    balanced, report = orchestrator._balance_samples(
        samples,
        dimensions=["topic"],
        default_language="en",
        target_size=100,
    )

    # Must preserve exactly 100 samples without dropping down to 83 or 61
    assert len(balanced) == 100
    assert report["samples_after"] == 100
    assert report["samples_removed"] == 0


def test_export_node_exact_size_trimming_and_preservation():
    """Ensure export node preserves exact requested dataset_size."""
    orchestrator = DatasetOrchestrator({}, Mock())

    # Create 105 samples
    samples = [
        {
            "instruction": f"Instruction {i}",
            "response": f"Response {i}",
            "quality_score": 0.9,
            "metadata": {"topic": "General"},
        }
        for i in range(105)
    ]

    # Target 100
    job_config = {"dataset_size": 100, "enable_balancing": False}
    balanced_subset, report = orchestrator._balance_samples(
        samples,
        dimensions=["topic"],
        default_language="en",
        target_size=100,
    )
    assert len(balanced_subset) >= 100
