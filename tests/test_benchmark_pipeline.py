import time
import hashlib
import pytest
from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root


def test_merkle_root_folding_benchmark():
    """Benchmark SHA-256 Merkle root computation over 1,000 samples (< 100ms requirement)."""
    samples = [
        {
            "instruction": f"Benchmark query {i} regarding statutory tax compliance and regulatory filings.",
            "response": f"Benchmark response {i} explaining deduction rules, threshold limits, and input tax credits.",
        }
        for i in range(1000)
    ]

    start = time.perf_counter()
    leaves = [compute_sample_hash(s) for s in samples]
    root = compute_merkle_root(leaves)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(root) == 64
    assert len(leaves) == 1000
    # Merkle folding of 1000 items should complete in well under 100 milliseconds
    assert elapsed_ms < 100.0, f"Merkle fold too slow: {elapsed_ms:.2f}ms"


def test_merkle_single_byte_tamper_detection():
    """Verify that altering a single character in one sample changes the Merkle root completely."""
    samples = [
        {"instruction": f"Instruction {i}", "response": f"Response {i}"}
        for i in range(16)
    ]
    orig_leaves = [compute_sample_hash(s) for s in samples]
    orig_root = compute_merkle_root(orig_leaves)

    # Tamper with 1 character in sample 5
    tampered_samples = list(samples)
    tampered_samples[5] = {"instruction": "Instruction 5", "response": "Response 5."}
    tampered_leaves = [compute_sample_hash(s) for s in tampered_samples]
    tampered_root = compute_merkle_root(tampered_leaves)

    assert orig_root != tampered_root
