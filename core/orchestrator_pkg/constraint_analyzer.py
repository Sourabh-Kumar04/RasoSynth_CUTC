"""Constraint analysis and feasibility estimation for dataset generation jobs."""
from __future__ import annotations

import re
from typing import Any, Dict

from core.discipline_matrix import is_content_discipline_compatible
from core.orchestrator_pkg.state import ConstraintAnalysis


class ConstraintAnalyzer:
    """Analyzes constraints and estimates feasibility."""

    def __init__(self, config: dict):
        self.config = config

    async def analyze(self, config: dict) -> ConstraintAnalysis:
        """Analyze job constraints and estimate feasibility."""
        analysis = ConstraintAnalysis(
            target_domain=config.get("target_domain", ""),
            constraints=config,
        )

        warnings = []
        conflicts = []
        strategies = []

        # Analyze domain scarcity
        domain = config.get("target_domain", "")
        if self._is_niche_domain(domain):
            warnings.append(f"Domain '{domain}' appears to be niche. Data may be limited.")
            strategies.append("Consider synthetic augmentation")
            strategies.append("Expand search to related domains")
            analysis.feasibility_score -= 0.2

        # Analyze time constraints
        if config.get("time_period"):
            warnings.append("Time period constraint may limit available sources")
            analysis.feasibility_score -= 0.1
            strategies.append("Consider broader time range")

        # Analyze licensing requirements
        license_req = config.get("licensing_requirements", "any")
        if license_req != "any":
            warnings.append(f"Licensing constraint ({license_req}) may limit sources")
            analysis.feasibility_score -= 0.15
            strategies.append("Expand licensing tolerance for initial collection")
            strategies.append("Apply license filtering post-collection")

        # Analyze language constraints
        languages = config.get("language", "en")
        if languages not in ["en", "english"]:
            warnings.append(f"Non-English language ({languages}) may limit sources")
            analysis.feasibility_score -= 0.1
            strategies.append("Use multilingual search engines")
            strategies.append("Consider code-switching detection")

        # Analyze quality vs cost tradeoff
        quality_level = config.get("quality_level", "standard")
        cost_budget = config.get("cost_budget_usd", 100.0)

        if quality_level == "research" and cost_budget < 200:
            warnings.append("Research quality with low budget may not be achievable")
            conflicts.append("quality_budget_conflict")
            strategies.append("Increase budget or reduce quality expectations")

        # Analyze synthetic data restrictions
        synthetic_ratio = config.get("synthetic_ratio", 0.0)
        if synthetic_ratio == 0 and self._is_low_resource_domain(domain):
            warnings.append("No synthetic data allowed in low-resource domain - may limit results")
            analysis.feasibility_score -= 0.3
            strategies.append("Relax synthetic data restriction")
            strategies.append("Accept smaller dataset")

        # Estimate results
        analysis.estimated_sources = self._estimate_sources(config)
        analysis.estimated_samples = min(
            config.get("dataset_size", 1000),
            analysis.estimated_sources * 10
        )
        # Cost projection follows the requested output size.
        analysis.estimated_cost = self._estimate_cost(
            config,
            int(config.get("dataset_size", analysis.estimated_samples) or analysis.estimated_samples),
        )
        if analysis.estimated_cost > cost_budget:
            warnings.append(
                f"Estimated generation cost (${analysis.estimated_cost:.2f}) exceeds the "
                f"configured budget (${cost_budget:.2f})."
            )
            conflicts.append("estimated_cost_exceeds_budget")
            strategies.append("Reduce the target dataset size or increase the budget")

        analysis.warnings = warnings
        analysis.fallback_strategies = strategies
        analysis.constraint_conflicts = conflicts

        return analysis

    def _is_niche_domain(self, domain: str) -> bool:
        """Check if domain appears niche based on string complexity."""
        return len(domain.split()) > 6 or any(char in domain for char in [":", "(", ")"])

    def _is_low_resource_domain(self, domain: str) -> bool:
        """Check if domain is likely low-resource."""
        return len(domain.split()) > 8

    def _is_source_domain_relevant(self, source: dict, target_domain: str, raw_input: str = "") -> bool:
        """Verify whether a discovered source is genuinely relevant to target_domain and query context."""
        if not target_domain or target_domain.lower() in ("general", "custom", "all", "sft"):
            return True

        title = str(source.get("title", "")).lower()
        desc = str(source.get("description", "")).lower()
        url = str(source.get("url", "")).lower()
        text_body = str(source.get("text", "") or source.get("content", "")).lower()
        full_content = f"{title} {desc} {url} {text_body[:3000]}"

        # Check if source is a specialized dataset repository
        source_type_val = str(source.get("source_type", "")).lower()
        is_dataset_source = (
            source_type_val in ("hf_dataset", "kaggle_dataset", "ai_kosh", "dataset_repo", "openml", "zenodo")
            or "huggingface.co/datasets" in url
            or "kaggle.com/datasets" in url
            or "openml.org" in url
            or "zenodo.org" in url
        )

        # Reject web catalog badges, awesome lists, file archives, and raw data dumps (only for general web pages)
        if not is_dataset_source and any(bad in full_content for bad in [
            "awesome-datascience", "awesome data science", "<div align=", "<img src=",
            "table of contents", "badge.svg", "become a sponsor", "train.csv", "test.csv",
            "available files:", "oleic acid.zip", "tug-891", "heat-pump", "q-methodology",
        ]):
            return False

        # Check jurisdictional conflict and cross-discipline homonym collisions
        cfg_domain = str(self.config.get("target_domain", "")).lower()
        compat, reason = is_content_discipline_compatible(
            content=full_content,
            domain=target_domain,
            raw_input=raw_input or cfg_domain,
            title=title,
            url=url
        )
        if not compat:
            return False

        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "are", "was", "not", "but",
            "all", "dataset", "data", "file", "download", "train", "synthetic", "example",
            "examples", "using", "into", "over", "under", "about", "such", "synthesize", "generate",
            "create", "pairs", "instruction", "response", "written", "plain", "simple", "each"
        }
        context_for_keywords = f"{target_domain} {raw_input}".lower() if raw_input else target_domain.lower()
        domain_keywords = [
            w for w in re.split(r'\W+', context_for_keywords)
            if len(w) >= 3 and w not in stop_words
        ]

        if not domain_keywords:
            return True

        # Check jurisdictional alignment: If user requested Indian context, reject explicitly foreign regional datasets
        if any(term in context_for_keywords for term in ["india", "indian", "bharat", "mci", "consumer protection"]):
            if any(term in full_content for term in ["european union", "eu legal", "groningen", "netherlands", "dutch", "uk nhs"]) and not any(term in full_content for term in ["india", "indian"]):
                return False

        def _kw_matches(kw: str, content: str) -> bool:
            if kw in content:
                return True
            if len(kw) > 4 and kw[:4] in content:
                return True
            return False

        match_count = sum(1 for kw in domain_keywords if _kw_matches(kw, full_content))
        if is_dataset_source:
            return match_count >= 1

        min_required = max(2, min(4, len(domain_keywords) // 4))
        overlap_ratio = match_count / max(1, len(domain_keywords))
        return match_count >= min_required or overlap_ratio >= 0.15

    def _estimate_sources(self, config: dict) -> int:
        """Estimate number of discoverable sources dynamically."""
        base_estimate = 150

        if config.get("allowed_domains"):
            base_estimate *= 0.7

        if config.get("time_period"):
            base_estimate *= 0.5

        return int(base_estimate)

    def _estimate_cost(self, config: dict, sample_count: int) -> float:
        """Estimate cost for dataset generation: unified price model of $0.06 per 1,000 rows ($0.00006/row)."""
        base_cost = (sample_count / 1000.0) * 0.06
        return round(base_cost, 2)
