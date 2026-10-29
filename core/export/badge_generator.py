"""Cryptographic DBOM Verification Badge Generator.

Generates scalable SVG and Markdown shields badges for embedding into Hugging Face dataset cards,
GitHub READMEs, and enterprise data catalogs:
[🛡️ DBOM | Cryptographically Verified | SHA-256 Merkle Root]
"""

from typing import Any, Dict, Optional


def generate_dbom_badge_svg(
    certificate_id: str = "DBOM-UNVERIFIED",
    merkle_root: str = "",
    status: str = "unverified",
    verified: bool = False,
) -> str:
    """Generate a clean, high-contrast SVG badge for dataset verification.

    Refuses a caller-supplied 'verified' status unless the verified flag is
    explicitly set by a real verification procedure.
    """
    is_verified = bool(verified) and status.lower() in ("verified", "valid", "cryptographically_verified")
    
    label = "DBOM"
    short_hash = (merkle_root[:8] + "…" + merkle_root[-4:]) if len(merkle_root) >= 12 else "SHA-256"
    status_text = f"Verified: {short_hash}" if is_verified else "Unverified"
    
    bg_left = "#1e1e2e"
    bg_right = "#059669" if is_verified else "#dc2626"
    
    total_width = 240
    split_x = 65
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="28" viewBox="0 0 {total_width} 28" role="img" aria-label="{label}: {status_text}">
  <title>{label}: {status_text}</title>
  <clipPath id="r">
    <rect width="{total_width}" height="28" rx="6" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{split_x}" height="28" fill="{bg_left}"/>
    <rect x="{split_x}" width="{total_width - split_x}" height="28" fill="{bg_right}"/>
    <rect id="highlight" width="{total_width}" height="28" fill="url(#gloss)" opacity="0.1"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif" font-size="11" font-weight="600">
    <text x="32" y="18" fill="#a5b4fc">🛡️ {label}</text>
    <text x="{split_x + (total_width - split_x) / 2}" y="18" fill="#ffffff">{status_text}</text>
  </g>
</svg>"""
    return svg


def generate_dbom_badge_markdown(
    dataset_name: str,
    certificate_id: str,
    api_base_url: str = "http://localhost:8000",
) -> str:
    """Generate Markdown snippet to embed the dynamic DBOM verification badge."""
    badge_url = f"{api_base_url.rstrip('/')}/badges/dbom/{certificate_id}.svg"
    return f"[![Cryptographic DBOM Verified]({badge_url})]({api_base_url.rstrip('/')}/datasets/{certificate_id}/dbom)"
