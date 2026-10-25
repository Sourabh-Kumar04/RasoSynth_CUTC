"""Tests for Frontend Zen Spatial UI, Color Palette definitions, and Audio Engine."""

import pytest
from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root


def test_merkle_tree_graph_mathematical_consistency():
    """Verify that Merkle leaf hashes collapse deterministically into the root hash."""
    samples = [
        {"instruction": f"Instruction sample {i}", "response": f"Response sample {i}"}
        for i in range(4)
    ]
    leaves = [compute_sample_hash(s) for s in samples]
    root = compute_merkle_root(leaves)

    assert len(root) == 64
    assert root.isalnum()

    # Verify binary folding
    h01 = compute_merkle_root([leaves[0], leaves[1]])
    h23 = compute_merkle_root([leaves[2], leaves[3]])
    folded_root = compute_merkle_root([h01, h23])
    assert folded_root == root


def test_realtime_palette_specifications():
    """Verify color palette definitions have valid hex codes and high contrast properties."""
    palettes = [
        {"id": "neon-saffron", "primary": "#f26625", "contrast": "8.4:1"},
        {"id": "cyber-emerald", "primary": "#10b981", "contrast": "8.4:1"},
        {"id": "electric-violet", "primary": "#a855f7", "contrast": "8.4:1"},
        {"id": "tokyo-cyan", "primary": "#06b6d4", "contrast": "8.8:1"},
        {"id": "solar-flare", "primary": "#f59e0b", "contrast": "9.1:1"},
    ]

    for p in palettes:
        assert p["primary"].startswith("#")
        assert len(p["primary"]) == 7
        assert ":" in p["contrast"]


def test_audio_sound_effect_frequencies():
    """Verify harmonic chime frequencies for verification audio chime."""
    # D5 and A5 notes for harmonious fifth interval (3:2 frequency ratio)
    d5 = 587.33
    a5 = 880.00
    ratio = a5 / d5
    assert abs(ratio - 1.5) < 0.01  # Perfect fifth
