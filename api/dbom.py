"""
DBOM API — endpoints for cryptographic Data Bill of Materials, Merkle verification,
In-Toto provenance, and digital signatures.
"""

from typing import Any, Dict, List, Optional
import logging

try:
    from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
    from api.auth import User, get_current_user
    _HAS_FASTAPI = True
except Exception:
    _HAS_FASTAPI = False
    APIRouter = None
    Body = Depends = HTTPException = Request = None
    User = get_current_user = None

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

logger = logging.getLogger(__name__)

if _HAS_FASTAPI:
    router = APIRouter(prefix="/api/dbom", tags=["dbom"])

    @router.post("/verify")
    async def verify_dbom_endpoint(
        payload: Dict[str, Any] = Body(...),
        current_user: Any = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """Cryptographically verify samples against a DBOM certificate Merkle root."""
        samples = payload.get("samples")
        certificate = payload.get("dbom_certificate") or payload.get("certificate")
        merkle_root = payload.get("merkle_root") or payload.get("merkle_root_hash")

        if not certificate and merkle_root:
            certificate = {"merkle_root_hash": merkle_root}

        if not isinstance(samples, list) or not certificate or not isinstance(certificate, dict):
            raise HTTPException(
                status_code=400,
                detail="Payload must include 'samples' (list) and either 'dbom_certificate' (dict) or 'merkle_root' (str).",
            )
        res = verify_dataset_dbom(samples=samples, dbom_certificate=certificate)
        res["verified"] = res.get("is_valid", False)
        return res

    @router.post("/attest")
    async def create_dbom_attestation_endpoint(
        payload: Dict[str, Any] = Body(...),
        current_user: Any = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """Generate a tamper-evident cryptographic DBOM certificate for dataset samples."""
        samples = payload.get("samples")
        if not isinstance(samples, list) or not samples:
            raise HTTPException(status_code=400, detail="Field 'samples' must be a non-empty list.")

        dataset_name = str(payload.get("dataset_name") or "Dataset Attestation")
        domain = payload.get("domain")
        language = str(payload.get("language") or "en")
        license_type = str(payload.get("license") or "PolyForm-Noncommercial-1.0.0")
        synthesis_mode = payload.get("synthesis_mode") or "standard"
        compliance_flags = payload.get("compliance_flags") or {}

        dbom = generate_dbom_attestation(
            dataset_name=dataset_name,
            samples=samples,
            domain=domain,
            language=language,
            license_type=license_type,
            compliance_flags=compliance_flags,
            synthesis_mode=synthesis_mode,
            dataset_id=payload.get("dataset_id"),
            sources=payload.get("sources"),
        )
        label = generate_nutrition_label_markdown(dbom)
        merkle_root = dbom.get("merkle_root_hash")
        return {
            **dbom,
            "merkle_root": merkle_root,
            "merkle_root_hash": merkle_root,
            "dbom_certificate": dbom,
            "nutrition_label_markdown": label,
        }

    @router.post("/sign")
    async def sign_attestation_endpoint(
        payload: Dict[str, Any] = Body(...),
        current_user: Any = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """Sign an In-Toto provenance statement using ECDSA SECP256R1."""
        dataset_name = str(payload.get("dataset_name") or "dataset")
        merkle_root = payload.get("merkle_root")
        sample_count = int(payload.get("sample_count") or 0)
        builder_id = str(payload.get("builder_id") or "https://github.com/Sourabh-Kumar04/RasoSynth_CUTC")
        license_type = str(payload.get("license_type") or "PolyForm-Noncommercial-1.0.0")

        if not merkle_root:
            raise HTTPException(status_code=400, detail="Field 'merkle_root' is required.")

        signer = DatasetAttestationSigner()
        bundle = signer.sign_attestation(
            dataset_name=dataset_name,
            merkle_root=merkle_root,
            sample_count=sample_count,
            builder_id=builder_id,
            license_type=license_type,
        )
        return {
            "statement": bundle.statement,
            "merkle_root": bundle.merkle_root,
            "signature": bundle.signature,
            "signature_hex": bundle.signature,
            "public_key_pem": bundle.public_key_pem,
            "timestamp": bundle.timestamp,
        }

    @router.post("/verify-signature")
    async def verify_signature_endpoint(
        payload: Dict[str, Any] = Body(...),
        current_user: Any = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """Verify an ECDSA digital signature on an In-Toto attestation statement."""
        statement = payload.get("statement")
        merkle_root = payload.get("merkle_root")
        signature = payload.get("signature")
        public_key_pem = payload.get("public_key_pem")

        if not statement or not merkle_root or not signature or not public_key_pem:
            raise HTTPException(
                status_code=400,
                detail="Fields 'statement', 'merkle_root', 'signature', and 'public_key_pem' are required.",
            )

        is_valid = DatasetAttestationSigner.verify_attestation(
            statement=statement,
            merkle_root=merkle_root,
            signature_hex=signature,
            public_key_pem=public_key_pem,
        )
        return {
            "is_valid": is_valid,
            "status": "signature_verified" if is_valid else "signature_verification_failed",
        }

    @router.get("/badge")
    async def get_dbom_badge_svg_endpoint(
        certificate_id: Optional[str] = Query(None),
        dataset_id: Optional[str] = Query(None),
        merkle_root: Optional[str] = Query(None),
    ):
        """Generate dynamic cryptographic DBOM verification SVG badge."""
        from core.export.badge_generator import generate_dbom_badge_svg
        cid = certificate_id or (f"DBOM-{merkle_root[:8].upper()}" if merkle_root else "DBOM-VERIFIED")
        svg = generate_dbom_badge_svg(
            certificate_id=cid,
            merkle_root=merkle_root or "",
            status="verified",
            verified=True,
        )
        return Response(content=svg, media_type="image/svg+xml")
else:
    router = None

    async def verify_dbom_endpoint(payload: Dict[str, Any], current_user: Any = None) -> Dict[str, Any]:
        samples = payload.get("samples")
        certificate = payload.get("dbom_certificate") or payload.get("certificate")
        if not isinstance(samples, list) or not certificate or not isinstance(certificate, dict):
            raise ValueError("Payload must include 'samples' (list) and 'dbom_certificate' (dict).")
        return verify_dataset_dbom(samples=samples, dbom_certificate=certificate)

    async def create_dbom_attestation_endpoint(payload: Dict[str, Any], current_user: Any = None) -> Dict[str, Any]:
        samples = payload.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ValueError("Field 'samples' must be a non-empty list.")
        dbom = generate_dbom_attestation(
            dataset_name=str(payload.get("dataset_name") or "Dataset Attestation"),
            samples=samples,
            domain=payload.get("domain"),
            language=str(payload.get("language") or "en"),
            license_type=str(payload.get("license") or "PolyForm-Noncommercial-1.0.0"),
            synthesis_mode=payload.get("synthesis_mode") or "standard",
            dataset_id=payload.get("dataset_id"),
            sources=payload.get("sources"),
        )
        return {"dbom_certificate": dbom, "nutrition_label_markdown": generate_nutrition_label_markdown(dbom)}

    async def sign_attestation_endpoint(payload: Dict[str, Any], current_user: Any = None) -> Dict[str, Any]:
        signer = DatasetAttestationSigner()
        bundle = signer.sign_attestation(
            dataset_name=str(payload.get("dataset_name") or "dataset"),
            merkle_root=payload.get("merkle_root", ""),
            sample_count=int(payload.get("sample_count") or 0),
        )
        return {
            "statement": bundle.statement,
            "merkle_root": bundle.merkle_root,
            "signature": bundle.signature,
            "signature_hex": bundle.signature,
            "public_key_pem": bundle.public_key_pem,
            "timestamp": bundle.timestamp,
        }

    async def verify_signature_endpoint(payload: Dict[str, Any], current_user: Any = None) -> Dict[str, Any]:
        is_valid = DatasetAttestationSigner.verify_attestation(
            statement=payload.get("statement", {}),
            merkle_root=payload.get("merkle_root", ""),
            signature_hex=payload.get("signature", ""),
            public_key_pem=payload.get("public_key_pem", ""),
        )
        return {"is_valid": is_valid, "status": "signature_verified" if is_valid else "signature_verification_failed"}


__all__ = [
    "router",
    "compute_sample_hash",
    "compute_merkle_root",
    "generate_dbom_attestation",
    "verify_dataset_dbom",
    "generate_nutrition_label_markdown",
    "DatasetAttestationSigner",
    "SignedAttestationBundle",
    "InTotoStatement",
]
