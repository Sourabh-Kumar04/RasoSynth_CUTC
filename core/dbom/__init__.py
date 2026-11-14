"""
Core DBOM — Data Bill of Materials & Cryptographic Provenance Module.

Provides Merkle tree calculation, leaf hashing, tamper-evident DBOM attestation,
in-toto provenance generation, and ECDSA signature verification.
"""

from core.export.dbom_attestor import (
    compute_sample_hash,
    compute_merkle_root,
    generate_dbom_attestation,
    verify_dataset_dbom,
    generate_nutrition_label_markdown,
)
from core.export.attestation import (
    DatasetAttestationSigner,
    SignedAttestationBundle,
    InTotoStatement,
)
from core.export.badge_generator import (
    generate_dbom_badge_svg,
    generate_dbom_badge_markdown,
)

__all__ = [
    "compute_sample_hash",
    "compute_merkle_root",
    "generate_dbom_attestation",
    "verify_dataset_dbom",
    "generate_nutrition_label_markdown",
    "DatasetAttestationSigner",
    "SignedAttestationBundle",
    "InTotoStatement",
    "generate_dbom_badge_svg",
    "generate_dbom_badge_markdown",
]
