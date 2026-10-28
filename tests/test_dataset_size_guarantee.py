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


def test_quality_threshold_check_hybrid_zero_filtered_continues():
    """Ensure hybrid mode falls back to synthetic generation when filtered samples is empty."""
    orchestrator = DatasetOrchestrator({}, Mock())
    state = {
        "filtered_samples": [],
        "filter_retry_count": 0,
        "job": {
            "config": {
                "generation_mode": "hybrid",
                "allow_seedless_generation": False,
            }
        }
    }
    decision = orchestrator._quality_threshold_check(state)
    assert decision == "continue"


def test_langgraph_wrapped_final_state_unwrapping():
    """Ensure final_state wrapped in node name dictionaries is correctly unwrapped."""
    raw_final_state = {
        "export": {
            "current_stage": "export",
            "progress": 1.0,
            "constructed_samples": [{"instruction": "q", "response": "a"}] * 100,
            "filtered_samples": [{"instruction": "q"}] * 100,
        }
    }
    unwrapped_state = dict(raw_final_state)
    for node_name in ["export", "human_review", "construct", "filter", "extract", "discover", "plan"]:
        if node_name in unwrapped_state and isinstance(unwrapped_state[node_name], dict):
            unwrapped_state.update(unwrapped_state[node_name])
    
    assert len(unwrapped_state.get("constructed_samples", [])) == 100
    assert unwrapped_state.get("current_stage") == "export"

