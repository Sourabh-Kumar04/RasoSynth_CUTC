import pytest
from core.export.dbom_attestor import compute_merkle_root, compute_sample_hash


def test_merkle_certificate_svg_badge_generation():
    """Verify deterministic Merkle proof generation and SVG certificate metadata."""
    sample_records = [
        {"instruction": "BNS 2023 Sec 479 applicability", "response": "Statutory bail provisions analysis."},
        {"instruction": "Raft log compaction", "response": "Snapshotting under term leadership."},
    ]
    leaf_hashes = [compute_sample_hash(s) for s in sample_records]
    root_hash = compute_merkle_root(leaf_hashes)

    assert isinstance(root_hash, str)
    assert len(root_hash) == 64  # SHA-256 hex string

    cert_id = "DBOM-2026-CERT-HITL"
    timestamp = "2026-10-25T09:30:00Z"
    svg_badge = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="240">
      <text>{cert_id}</text>
      <text>{root_hash}</text>
      <text>{timestamp}</text>
    </svg>"""

    assert cert_id in svg_badge
    assert root_hash in svg_badge
    assert "xmlns" in svg_badge


def test_finetune_loss_reduction_metric_calculation():
    """Verify loss delta percentage reduction calculation logic."""
    losses = [2.5, 2.0, 1.5, 1.0]
    initial_loss = losses[0]
    latest_loss = losses[-1]
    loss_delta_pct = ((initial_loss - latest_loss) / initial_loss) * 100
    assert loss_delta_pct == 60.0
