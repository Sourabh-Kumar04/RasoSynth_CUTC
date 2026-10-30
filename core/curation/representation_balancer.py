"""Indic Regional & Demographic Representation Balancer.

Audits synthetic datasets for geographic distribution across Indian zones
and tier classification (Metro vs Urban vs Rural/Gramin) to prevent
geographic skew and ensure inclusive post-training alignment.

METHOD HONESTY NOTES — read before quoting any number from this module:
- Zones and tiers are KEYWORD matches against sample text (city/state
  names and rural markers), matched on token/phrase boundaries — never by
  substring, so "goal" does not match "goa" and "up" inside another word
  does not match a zone.
- A sample with no tier keyword is "unknown", NOT "tier_2_3_urban": the
  old default silently classified every unmarked sample as urban.
- Gender is NEVER inferred here. First names do not determine gender, so
  the previous 10+10 first-name lists and the ``gender_distribution`` output
  have been removed. There is no demographic parity claim in this module:
  ``representation_parity_score`` measures only how uniformly the
  keyword matches spread across the five zones.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional


ZONE_KEYWORDS = {
    "north": [
        "delhi", "noida", "gurgaon", "lucknow", "jaipur", "chandigarh", "kanpur",
        "punjab", "haryana", "rajasthan", "uttar pradesh", "varanasi", "dehradun",
    ],
    "south": [
        "bengaluru", "bangalore", "chennai", "hyderabad", "kochi", "kerala",
        "karnataka", "tamil nadu", "andhra", "telangana", "mysore", "coimbatore",
        "thiruvananthapuram", "visakhapatnam",
    ],
    "west": [
        "mumbai", "pune", "ahmedabad", "surat", "gujarat", "maharashtra",
        "nagpur", "nashik", "vadodara", "rajkot", "goa", "thane",
    ],
    "east": [
        "kolkata", "patna", "bhubaneswar", "ranchi", "west bengal", "bihar",
        "odisha", "jharkhand", "cuttack", "jamshedpur", "siliguri",
    ],
    "northeast": [
        "guwahati", "assam", "meghalaya", "shillong", "imphal", "manipur",
        "agartala", "tripura", "aizawl", "mizoram", "kohima", "nagaland", "gangtok",
    ],
}

TIER_KEYWORDS = {
    "tier_1_metro": ["delhi", "mumbai", "bengaluru", "chennai", "hyderabad", "kolkata"],
    "rural_gramin": [
        "gaon", "gramin", "panchayat", "kisan", "mandi", "agriculture", "farmer",
        "fasal", "kheti", "rural", "tahsil", "sarpanch", "patwari",
    ],
}


def _keyword_matches(keyword: str, lower_text: str, tokens: set) -> bool:
    """Match a keyword on token/phrase boundaries, never by substring.

    Single words match whole tokens; multi-word phrases match with word
    boundaries on both sides. "goal" therefore does not match "goa", and
    "group" does not match "goa" either.
    """
    if " " in keyword:
        return re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", lower_text) is not None
    return keyword in tokens


def audit_sample_representation(text: str) -> Dict[str, Any]:
    """Detect regional and urbanicity keyword indicators in sample text.

    Returns zones and a setting. ``setting`` is "unknown" when no tier
    keyword matches. No gender is inferred from names or from anything else.
    """
    lower = text.lower()
    tokens = set(re.findall(r"\w+", lower))

    # Zone detection (token/phrase boundary matching)
    matched_zones = []
    for zone, kws in ZONE_KEYWORDS.items():
        if any(_keyword_matches(kw, lower, tokens) for kw in kws):
            matched_zones.append(zone)

    # Tier / Setting detection — unknown unless a keyword actually matches
    setting = "unknown"
    if any(_keyword_matches(m, lower, tokens) for m in TIER_KEYWORDS["tier_1_metro"]):
        setting = "tier_1_metro"
    elif any(_keyword_matches(r, lower, tokens) for r in TIER_KEYWORDS["rural_gramin"]):
        setting = "rural_gramin"

    return {
        "zones": matched_zones if matched_zones else ["neutral"],
        "setting": setting,
        "method": "keyword_match_token_boundary",
        "gender_inference": "not_performed",
    }


def audit_dataset_representation(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Audit geographic distribution and urbanicity balance (keyword-based)."""
    if not samples:
        return {
            "total_samples": 0,
            "representation_parity_score": 0.0,
            "status": "empty",
            "zone_distribution": {},
            "setting_distribution": {},
            "underrepresented_zones": [],
            "unmatched_zone_samples": 0,
            "recommendations": ["Provide dataset samples to evaluate representation balance."],
        }

    total = len(samples)
    zone_counts = Counter()
    setting_counts = Counter()
    unmatched_zone_samples = 0

    for s in samples:
        inst = s.get("instruction", "")
        resp = s.get("response", "")
        text = f"{inst} {resp}"
        rep = audit_sample_representation(text)

        if rep["zones"] == ["neutral"]:
            unmatched_zone_samples += 1
        for z in rep["zones"]:
            zone_counts[z] += 1
        setting_counts[rep["setting"]] += 1

    # Regional distribution percentages
    zones = ["north", "south", "west", "east", "northeast"]
    regional_counts = {z: zone_counts.get(z, 0) for z in zones}
    regional_total = sum(regional_counts.values()) or 1

    zone_distribution = {
        z: {
            "count": regional_counts[z],
            "percentage": round((regional_counts[z] / regional_total) * 100, 1),
        }
        for z in zones
    }

    # Identify underrepresented zones (less than 10% representation)
    underrepresented_zones = [
        z for z, info in zone_distribution.items() if info["percentage"] < 10.0
    ]

    # Setting distribution (includes "unknown" — unmarked samples are not urban)
    setting_distribution = {
        s: {
            "count": setting_counts.get(s, 0),
            "percentage": round((setting_counts.get(s, 0) / total) * 100, 1),
        }
        for s in ["tier_1_metro", "tier_2_3_urban", "rural_gramin", "unknown"]
    }

    # Calculate Parity Score (0.0 - 1.0)
    # Target uniform distribution across 5 zones = 20% each
    ideal_pct = 20.0
    mae = sum(abs(info["percentage"] - ideal_pct) for info in zone_distribution.values()) / (ideal_pct * 5)
    parity_score = round(max(0.0, min(1.0, 1.0 - (mae * 0.5))), 2)

    recommendations = []
    if underrepresented_zones:
        recs = ", ".join(z.capitalize() for z in underrepresented_zones)
        recommendations.append(
            f"Increase synthetic prompt sampling for underrepresented regions: {recs}."
        )
    if setting_distribution["rural_gramin"]["percentage"] < 15.0:
        recommendations.append(
            "Increase rural/gramin scenarios (agriculture, local panchayat, mandi commerce) to prevent metro-only bias."
        )
    if not recommendations:
        recommendations.append("Geographic and demographic distribution is well-balanced across Indic regions.")

    return {
        "total_samples": total,
        "method": "keyword_match_token_boundary",
        "representation_parity_score": parity_score,
        "parity_note": "Uniformity of zone-keyword matches across 5 zones only; not a demographic representativeness measure, and no gender is inferred.",
        "zone_distribution_note": "Percentages are over zone-keyword matches, not over all samples; see unmatched_zone_samples.",
        "status": "balanced" if parity_score >= 0.70 else "skewed",
        "zone_distribution": zone_distribution,
        "setting_distribution": setting_distribution,
        "unmatched_zone_samples": unmatched_zone_samples,
        "underrepresented_zones": underrepresented_zones,
        "recommendations": recommendations,
    }
