"""Indic Regional & Demographic Representation Balancer.

Audits synthetic datasets for geographic distribution across Indian zones,
tier classification (Metro vs Urban vs Rural/Gramin), and persona parity
to prevent geographic skew and ensure inclusive post-training alignment.
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

FEMALE_NAMES = ["priya", "sunita", "lakshmi", "ananya", "fatima", "kavita", "pooja", "neha", "meera", "shreya"]
MALE_NAMES = ["rahul", "amit", "suresh", "rajesh", "vikram", "mohammed", "rohit", "arjun", "deepak", "anil"]


def audit_sample_representation(text: str) -> Dict[str, Any]:
    """Detect regional, urbanicity, and demographic indicators in sample text."""
    lower = text.lower()
    tokens = set(re.findall(r"\w+", lower))

    # Zone detection
    matched_zones = []
    for zone, kws in ZONE_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            matched_zones.append(zone)

    # Tier / Setting detection
    setting = "tier_2_3_urban"
    if any(m in lower for m in TIER_KEYWORDS["tier_1_metro"]):
        setting = "tier_1_metro"
    elif any(r in lower for r in TIER_KEYWORDS["rural_gramin"]):
        setting = "rural_gramin"

    # Gender name indicators
    has_female = any(name in tokens for name in FEMALE_NAMES)
    has_male = any(name in tokens for name in MALE_NAMES)

    return {
        "zones": matched_zones if matched_zones else ["neutral"],
        "setting": setting,
        "gender_indicator": "female" if (has_female and not has_male) else "male" if (has_male and not has_female) else "neutral",
    }


def audit_dataset_representation(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Audit geographic distribution, urbanicity balance, and demographic parity."""
    if not samples:
        return {
            "total_samples": 0,
            "representation_parity_score": 0.0,
            "status": "empty",
            "zone_distribution": {},
            "setting_distribution": {},
            "underrepresented_zones": [],
            "recommendations": ["Provide dataset samples to evaluate representation balance."],
        }

    total = len(samples)
    zone_counts = Counter()
    setting_counts = Counter()
    gender_counts = Counter()

    for s in samples:
        inst = s.get("instruction", "")
        resp = s.get("response", "")
        text = f"{inst} {resp}"
        rep = audit_sample_representation(text)

        for z in rep["zones"]:
            zone_counts[z] += 1
        setting_counts[rep["setting"]] += 1
        gender_counts[rep["gender_indicator"]] += 1

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

    # Setting distribution
    setting_distribution = {
        s: {
            "count": setting_counts.get(s, 0),
            "percentage": round((setting_counts.get(s, 0) / total) * 100, 1),
        }
        for s in ["tier_1_metro", "tier_2_3_urban", "rural_gramin"]
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
        "representation_parity_score": parity_score,
        "status": "balanced" if parity_score >= 0.70 else "skewed",
        "zone_distribution": zone_distribution,
        "setting_distribution": setting_distribution,
        "gender_distribution": {
            k: round((v / total) * 100, 1) for k, v in gender_counts.items()
        },
        "underrepresented_zones": underrepresented_zones,
        "recommendations": recommendations,
    }
