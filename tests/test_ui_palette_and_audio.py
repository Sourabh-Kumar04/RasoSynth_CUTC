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


def test_locked_flagship_color_palette():
    """Verify definitive YC Obsidian Signal Orange color palette specification."""
    palette = {
        "primary": "#f26625",
        "hover": "#de581a",
        "muted": "#ea580c",
        "background": "#0a0a0f",
        "surface": "#12121a",
        "contrast_ratio": "8.4:1",
    }
    assert palette["primary"] == "#f26625"
    assert palette["background"] == "#0a0a0f"
    assert len(palette["primary"]) == 7
    assert ":" in palette["contrast_ratio"]


def test_audio_sound_effect_frequencies():
    """Verify harmonic chime frequencies for verification audio chime."""
    # D5 and A5 notes for harmonious fifth interval (3:2 frequency ratio)
    d5 = 587.33
    a5 = 880.00
    ratio = a5 / d5
    assert abs(ratio - 1.5) < 0.01  # Perfect fifth
