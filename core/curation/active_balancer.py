"""Active Synthetic Data Re-Balancing & Targeted Mutation Engine.

Analyzes demographic, geographic, and topical representation deficits,
computing exact quota adjustments and formulating targeted prompt mutations
to bridge underrepresented clusters. Post-rebalance parity is a PROJECTION, not a measured outcome.
"""

from typing import Any, Dict, List, Optional


REGION_CONTEXT_TEMPLATES = {
    "north": {
        "metro": "NCR / Delhi commercial enterprises, trade licenses, and tax compliance",
        "urban": "Tier-2 industrial hubs in UP, Haryana, or Punjab (e.g. Kanpur, Ludhiana)",
        "rural": "Agricultural mandi transactions, kisan credit schemes, and rural panchayat grants in Haryana/UP",
    },
    "south": {
        "metro": "Bengaluru / Hyderabad tech startups, SaaS export compliance, and IT services billing",
        "urban": "Manufacturing and textile clusters in Coimbatore, Mysore, or Tirupur",
        "rural": "Plantation subsidies, spice board exports, and rural credit in Kerala/Karnataka",
    },
    "west": {
        "metro": "Mumbai BFSI, port logistics, and corporate restructuring compliance",
        "urban": "Gujarat diamond/textile trade in Surat or engineering MSMEs in Pune",
        "rural": "Dryland farmer cooperatives, dairy society billing, and mandi taxation in Maharashtra/Gujarat",
    },
    "east": {
        "metro": "Kolkata trading conglomerates, maritime freight, and customs clearance",
        "urban": "Mineral MSMEs and engineering units in Jamshedpur, Ranchi, or Bhubaneswar",
        "rural": "Jute farming, paddy procurement MSP billing, and SHG gramin microfinance in West Bengal/Bihar",
    },
    "northeast": {
        "metro": "Guwahati transit logistics, cross-border trade, and regional development compliance",
        "urban": "Eco-tourism enterprises, bamboo craft MSMEs in Shillong or Agartala",
        "rural": "Tea garden labor welfare funds, organic horticulture schemes in Assam/Meghalaya",
    },
}


def plan_active_rebalancing(
    audit_report: Dict[str, Any],
    target_sample_pool: int = 100,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute exact quota adjustments and targeted prompt directives to eliminate skew."""
    underrep_zones = audit_report.get("underrepresented_zones") or []
    zone_dist = audit_report.get("zone_distribution") or {}
    setting_dist = audit_report.get("setting_distribution") or {}

    # Target: 20% for each of the 5 zones
    ideal_zone_pct = 20.0
    quotas = {}
    total_deficit_units = 0

    for z in ["north", "south", "west", "east", "northeast"]:
        curr_pct = zone_dist.get(z, {}).get("percentage", 0.0)
        deficit = max(0.0, ideal_zone_pct - curr_pct)
        if deficit > 0:
            units = int(round((deficit / 100.0) * target_sample_pool))
            units = max(units, 5 if z in underrep_zones else 2)
            quotas[z] = units
            total_deficit_units += units

    # Setting deficits (ensure at least 25% rural/gramin)
    rural_pct = setting_dist.get("rural_gramin", {}).get("percentage", 0.0)
    rural_priority = rural_pct < 25.0

    # Formulate targeted synthesis directives
    targeted_directives = []
    for zone, count in quotas.items():
        templates = REGION_CONTEXT_TEMPLATES.get(zone, {})
        setting_target = "rural" if rural_priority else "urban"
        context_theme = templates.get(setting_target, templates.get("urban", f"Regional {zone} commerce"))

        directive = {
            "target_zone": zone,
            "target_setting": "rural_gramin" if setting_target == "rural" else "tier_2_3_urban",
            "allocated_sample_quota": count,
            "domain_focus": domain or "general",
            "scenario_context": context_theme,
            "prompt_directive": (
                f"Synthesize instruction-response scenarios specifically set in the {zone.upper()} region of India, "
                f"focusing on {context_theme}. Incorporate authentic regional statutory terminology and cultural context."
            ),
        }
        targeted_directives.append(directive)

    return {
        "status": "rebalancing_plan_generated",
        "initial_parity_score": audit_report.get("representation_parity_score", 0.0),
        "target_sample_pool": target_sample_pool,
        "total_rebalancing_samples_planned": sum(d["allocated_sample_quota"] for d in targeted_directives),
        "targeted_directives": targeted_directives,
        # Projected, not measured: no rebalance has run when this plan is produced.
        "projected_parity_score_post_rebalance": 0.95,
    }
