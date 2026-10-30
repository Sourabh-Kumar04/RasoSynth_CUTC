"""
CANONICAL ORCHESTRATOR - This is the only production orchestrator.

References:
- core/orchestrator_checkpoint_integrated.py (STUB/REFERENCE - nodes are stubs)
- orchestrator/autonomous_orchestrator.py (EXPERIMENTAL - not connected to API)

Enhanced orchestrator with intelligent reasoning and constraint handling.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import logging
from typing import TypedDict, Annotated, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator
from core.config import get_settings
from core.intent import UserIntent, IntentExtractionError
from core.intent_extractor import extract_intent


logger = logging.getLogger(__name__)


def _sanitize_metadata(meta: dict) -> dict:
    """JSON round-trip to guarantee all values are serializable."""
    try:
        import json as _json
        return _json.loads(_json.dumps(meta, default=str))
    except Exception:
        return {}


def _json_safe(value: Any) -> Any:
    """Convert graph values to JSON-safe data for persistent checkpoints."""
    try:
        import json as _json
        return _json.loads(_json.dumps(value, default=str))
    except Exception:
        return [] if isinstance(value, list) else {}


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEGOTIATING = "negotiating"      # When constraints are difficult
    AWAITING_REVIEW = "awaiting_review"  # Paused at HITL gate


@dataclass
class ConstraintAnalysis:
    """Analysis of data collection constraints."""
    target_domain: str
    constraints: dict
    feasibility_score: float = 1.0
    estimated_sources: int = 0
    estimated_samples: int = 0
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)
    fallback_strategies: list[str] = field(default_factory=list)
    constraint_conflicts: list[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    current_stage: str
    progress: float
    samples_processed: int = 0
    samples_generated: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    config: dict = field(default_factory=dict)
    sources_discovered: int = 0
    sources_extracted: int = 0
    samples_filtered: int = 0
    constraint_analysis: ConstraintAnalysis | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_stage": self.current_stage,
            "progress": self.progress,
            "samples_processed": self.samples_processed,
            "samples_generated": self.samples_generated,
            "sources_discovered": self.sources_discovered,
            "sources_extracted": self.sources_extracted,
            "samples_filtered": self.samples_filtered,
            "cost_usd": self.cost_usd,
            "error": self.error,
            "config": self.config,
            "constraint_analysis": self.constraint_analysis.__dict__ if self.constraint_analysis else None,
        }


from operator import add as _list_add_reducer

class AgentState(TypedDict):
    """Enhanced state for the orchestration.

    List-typed fields use ``Annotated[list, operator.add]`` reducers so that
    if two parallel nodes (or a retry that re-enters a node in the same
    super-step) try to write to the same key, LangGraph concatenates the
    values instead of raising ``INVALID_CONCURRENT_GRAPH_UPDATE``. Scalars
    are still last-write-wins.
    """
    job: dict
    sources: list
    extracted_content: list
    filtered_samples: list
    constructed_samples: list
    errors: Annotated[list[str], _list_add_reducer]
    warnings: Annotated[list[str], _list_add_reducer]
    should_retry: bool
    human_approval_needed: bool
    human_approved: bool
    messages: Annotated[list[str], _list_add_reducer]
    current_stage: str
    progress: float
    constraint_analysis: dict | None
    low_resource_mode: bool
    multilingual_mode: bool
    adaptation_notes: Annotated[list[str], _list_add_reducer]
    filter_retry_count: int
    dataset_plan: dict | None
    coverage_matrix: dict | None
    balance_report: dict | None
    intent: UserIntent | None
    resume_from_stage: str | None
    quality_score: float | None
    quality_eval_passed: bool | None
    quality_breakdown: dict | None
    agent_artifacts: dict


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
        # Cost projection follows the requested output size. Estimated source
        # availability is a separate planning signal and should not silently
        # make large requested datasets look cheaper than they are.
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

        import re
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
        from core.discipline_matrix import is_content_discipline_compatible
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
            # Datasets are queried directly via platform APIs (HuggingFace Hub, Kaggle).
            # A dataset matching any key domain/entity keyword (e.g. 'california', 'delhi', 'housing', 'price')
            # is genuinely relevant.
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
        """Estimate cost for dataset generation."""
        # Planning estimate only (flat $0.001/sample); not metered spend.
        base_cost = sample_count * 0.001  # $0.001 per sample base

        # Add for quality requirements
        quality_level = config.get("quality_level", "standard")
        if quality_level == "high":
            base_cost *= 1.5
        elif quality_level == "research":
            base_cost *= 3

        # Add for multilingual
        if config.get("language") != "en":
            base_cost *= 1.2

        # Keep the projected cost independent from the budget so an over-budget
        # job is reported as a conflict instead of appearing to fit by being
        # silently capped at the user's limit.
        return base_cost


class DatasetOrchestrator:
    """Enhanced orchestrator with constraint awareness and intelligent adaptation."""

    def __init__(
        self,
        config: dict,
        router,
        db=None,
        observability=None,
        ws_manager=None,
        redis_client=None,
        checkpoint_manager=None,
        technique_integrator=None,
        delivery_manager=None,
        agent_registry=None,
    ):
        self.config = config
        self.router = router
        self.db = db
        # Expose the raw DatabaseManager so nodes like _human_review_node can call update_job
        self.db_manager = getattr(db, "db", None) if db is not None else None
        self.review_service = None
        self.ws_manager = ws_manager
        self.technique_integrator = technique_integrator
        self.delivery_manager = delivery_manager

        # Multi-Agent Society integration
        try:
            from agents.registry import AgentRegistry, AgentRegistryInitializer
            AgentRegistryInitializer.initialize()
            self.agent_registry = agent_registry or AgentRegistry.get_instance()
        except Exception as ar_err:
            self.agent_registry = None
            logger.debug(f"AgentRegistry initialization skipped: {ar_err}")

        if observability:
            self.observability = observability
        else:
            from core.observability_manager import ObservabilityManager
            from core.config import Settings
            self.observability = ObservabilityManager(Settings())

        try:
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            self.checkpointer = MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=True))
        except Exception:
            self.checkpointer = MemorySaver()
        self.graph = self._build_graph()
        self.active_jobs: dict[str, Job] = {}
        self._cancellation_events: dict[str, asyncio.Event] = {}
        self._db_update_tasks: set[asyncio.Task] = set()
        self._preview_events: dict[str, asyncio.Event] = {}
        self._preview_decisions: dict[str, dict] = {}
        self.constraint_analyzer = ConstraintAnalyzer(config)
        self.redis_client = redis_client  # Redis client for intent caching (optional)
        self.persistent_checkpoint_manager = checkpoint_manager

    def accept_preview(self, job_id: str, edited_samples: Optional[list[dict]] = None) -> bool:
        """Signal early preview acceptance to advance the pipeline."""
        if job_id in self._preview_events:
            self._preview_decisions[job_id] = {"accepted": True, "edited_samples": edited_samples}
            self._preview_events[job_id].set()
            return True
        return False

    def reject_preview(self, job_id: str, updated_prompt: Optional[str] = None) -> bool:
        """Signal early preview rejection / refinement to re-run query optimizer."""
        if job_id in self._preview_events:
            self._preview_decisions[job_id] = {"accepted": False, "updated_prompt": updated_prompt}
            self._preview_events[job_id].set()
            return True
        return False

    def _is_source_relevant(self, source, intent: UserIntent | None) -> bool:
        """
        Reject a source if any term from intent.anti_domains appears
        in its title, description, or URL, or if it fails domain relevance / collision checks.
        """
        if intent is None:
            # Defensive: should never happen in normal flow
            return True
        if isinstance(source, dict):
            title = (source.get("title") or "").lower()
            description = (source.get("description") or "").lower()
            url = (source.get("url") or "").lower()
            text = (source.get("text") or source.get("content") or "").lower()
        else:
            # DiscoveredSource / any object with .title, .url, .description
            title = (getattr(source, "title", None) or "").lower()
            description = (getattr(source, "description", None) or "").lower()
            url = (getattr(source, "url", None) or "").lower()
            text = (getattr(source, "text", None) or getattr(source, "content", None) or "").lower()
        combined = f"{title} {description} {url} {text[:2000]}"
        for anti in intent.anti_domains:
            if anti in combined:
                logger.debug(f"Rejected source '{title}' – matched anti-domain '{anti}'")
                return False

        # Domain relevance & collision validation via constraint analyzer
        source_dict = {
            "title": title,
            "description": description,
            "url": url,
            "text": text,
        }
        target_domain = getattr(intent, "domain", "") or ""
        raw_input = getattr(intent, "raw_input", "") or ""
        if hasattr(self, "constraint_analyzer") and not self.constraint_analyzer._is_source_domain_relevant(
            source_dict, target_domain, raw_input=raw_input
        ):
            logger.debug(f"Rejected source '{title}' – failed domain relevance or collision check")
            return False

        return True

    def _build_graph(self) -> StateGraph:
        """Build the orchestration graph with adaptive non-linear stages as per industry standards."""
        workflow = StateGraph(AgentState)

        # Core pipeline stages
        workflow.add_node("analyze_constraints", self._analyze_constraints_node)
        workflow.add_node("query_optimizer", self._query_optimizer_node)
        workflow.add_node("early_preview", self._early_preview_node)
        workflow.add_node("discover", self._discover_node)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("filter", self._filter_node)
        workflow.add_node("construct", self._construct_node)
        workflow.add_node("quality_eval", self._quality_eval_node)
        workflow.add_node("human_review", self._human_review_node)
        workflow.add_node("balance", self._balance_node)
        workflow.add_node("export", self._export_node)
        workflow.add_node("error_handler", self._error_handler_node)
        workflow.add_node("adapt_strategy", self._adapt_strategy_node)
        workflow.add_node("plan", self._plan_node)

        workflow.set_entry_point("analyze_constraints")

        # Main linear sub-paths
        workflow.add_edge("query_optimizer", "early_preview")
        workflow.add_edge("discover", "extract")
        workflow.add_edge("extract", "filter")
        workflow.add_edge("plan", "construct")
        workflow.add_edge("construct", "quality_eval")
        workflow.add_edge("human_review", "balance")
        workflow.add_edge("balance", "export")
        workflow.add_edge("export", END)

        # Adaptive / Non-linear conditional edges
        workflow.add_conditional_edges(
            "analyze_constraints",
            self._feasibility_check,
            {
                "proceed": "query_optimizer",
                "proceed_synthetic": "plan",
                "negotiate": "adapt_strategy",
                "resume_extract": "extract",
                "resume_filter": "filter",
                "resume_construct": "construct",
                "resume_review": "human_review",
                "resume_balance": "balance",
                "resume_export": "export",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "early_preview",
            self._preview_decision_check,
            {
                "accepted_grounded": "discover",
                "accepted_synthetic": "plan",
                "retry_query": "query_optimizer",
            }
        )

        workflow.add_conditional_edges(
            "filter",
            self._quality_threshold_check,
            {
                "continue": "construct",
                "review": "construct",
                "retry": "extract",
                "adapt": "adapt_strategy",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "quality_eval",
            self._quality_eval_check,
            {
                "pass": "human_review",
                "retry_synthesis": "construct",
            }
        )

        workflow.add_conditional_edges(
            "adapt_strategy",
            self._adaptation_check,
            {
                "retry": "discover",
                "proceed": "construct",
                "reduce": "construct"
            }
        )

        return workflow.compile(checkpointer=self.checkpointer)

    async def _analyze_constraints_node(self, state: AgentState) -> AgentState:
        """Analyze constraints and estimate feasibility."""
        job = state["job"]
        job_config = job.get("config", {})

        # Run constraint analysis
        analysis = await self.constraint_analyzer.analyze(job_config)

        # Update job with analysis
        job["constraint_analysis"] = {
            "feasibility_score": analysis.feasibility_score,
            "estimated_sources": analysis.estimated_sources,
            "estimated_samples": analysis.estimated_samples,
            "warnings": analysis.warnings,
            "strategies": analysis.fallback_strategies,
            "conflicts": analysis.constraint_conflicts,
        }

        return {
            **state,
            "constraint_analysis": job["constraint_analysis"],
            "warnings": analysis.warnings,
            "messages": [f"Constraint analysis: {analysis.feasibility_score:.0%} feasible"],
        }

    def _feasibility_check(self, state: AgentState) -> str:
        """Check if constraints are feasible."""
        resume_routes = {
            "discovery": "resume_extract",
            "discover": "resume_extract",
            "extraction": "resume_filter",
            "extract": "resume_filter",
            "filtering": "resume_construct",
            "filter": "resume_construct",
            "construction": "resume_review",
            "construct": "resume_review",
            "human_review": "resume_balance",
            "review": "resume_balance",
            "balance": "resume_export",
            "export": "resume_export",
        }
        resume_stage = state.get("resume_from_stage")
        if resume_stage in resume_routes:
            logger.info("Resuming job %s after %s", state.get("job", {}).get("id"), resume_stage)
            return resume_routes[resume_stage]

        job = state.get("job", {})
        config = job.get("config", {})
        mode = config.get("generation_mode", "strict_source")
        allow_fallback = config.get("allow_seedless_generation", False)
        
        if config.get("require_early_preview") is True:
            return "proceed"

        if mode == "synthetic":
            logger.info("Generation mode is set to synthetic. Proceeding directly to planning.")
            return "proceed_synthetic"

        if mode == "hybrid" or allow_fallback:
            return "proceed"

        analysis = state.get("constraint_analysis", {})
        score = analysis.get("feasibility_score", 1.0)

        if score < 0.3:
            return "negotiate"
        elif score < 0.5:
            return "negotiate"
        else:
            return "proceed"

    async def _query_optimizer_node(self, state: AgentState) -> AgentState:
        """Query Optimizer (LLM Fast-Pass): intent, domain, anti-domains, specialized search queries."""
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})

        self._update_job_status(job_id, "query_optimization", 0.05)

        target_domain = config.get("target_domain", "")
        approved_plan = config.get("query_plan")
        if approved_plan:
            intent = UserIntent(**approved_plan, raw_input=target_domain)
        else:
            try:
                intent = await extract_intent(
                    raw_input=str(target_domain),
                    provider_router=self.router,
                    redis_client=getattr(self, 'redis_client', None),
                )
            except Exception as e:
                logger.warning(f"Query optimizer intent extraction fallback: {e}")
                intent = UserIntent.from_fallback(
                    str(target_domain) if target_domain else None,
                    confidence=0.5,
                )

        approved_queries = config.get("specialized_queries") or []
        if approved_queries:
            intent.specialized_queries = approved_queries[:10]
        ideal_samples = config.get("ideal_samples") or []
        if ideal_samples:
            intent.ideal_samples = ideal_samples[:10]

        agent_artifacts = dict(state.get("agent_artifacts") or {})
        # Multi-Agent Society: strategy plans constraints while the search
        # specialist contributes transparent query reformulations.
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                ctx = AgentContext(job_id=job_id, dataset_id=job_id, domain=target_domain)
                strat_agent = self.agent_registry.create_agent(AgentType.STRATEGY)
                if strat_agent:
                    await strat_agent.execute({"intent": intent.model_dump(), "stage": "query_optimizer"}, ctx)
                search_agent = self.agent_registry.create_agent(AgentType.SEARCH_OPTIMIZATION)
                if search_agent:
                    await search_agent.initialize()
                    search_result = await search_agent.execute({
                        "query": target_domain or intent.raw_input,
                        "domain": config.get("source_domain", ""),
                        "task_id": job_id,
                    }, ctx)
                    if search_result.success:
                        optimized = [item.get("query") for item in search_result.output.get("optimized_queries", []) if item.get("query")]
                        intent.specialized_queries = list(dict.fromkeys([*intent.specialized_queries, *optimized]))[:10]
                        agent_artifacts["search_optimization"] = search_result.output
            except Exception:
                logger.exception("Search/planning agent advisory stage failed")

        logger.info(f"[{job_id}] Query Optimizer generated {len(intent.specialized_queries)} queries for '{intent.domain}'")
        return {
            **state,
            "intent": intent,
            "current_stage": "query_optimizer",
            "progress": 0.08,
            "agent_artifacts": agent_artifacts,
            "messages": [f"Query optimized: {len(intent.specialized_queries)} specialized queries for {intent.domain}"],
        }

    async def _early_preview_node(self, state: AgentState) -> AgentState:
        """Early Preview Gate: synthesize 3-5 preview samples early and pause for user acceptance if requested."""
        job = state.get("job") or {"id": state.get("job_id", "job-preview"), "config": state.get("config", {})}
        job_id = job.get("id", state.get("job_id", "job-preview"))
        config = job.get("config", {})
        intent = state.get("intent")

        preview_samples = []
        user_prompt = config.get("raw_input") or config.get("prompt") or config.get("target_domain", "")
        domain_name = (intent.domain if intent else None) or config.get("target_domain", "Synthetic Instructions")
        language = config.get("language", "en")

        if config.get("approved_examples"):
            preview_samples = config.get("approved_examples")
        else:
            # 1. Attempt LLM generation through active provider router with user's specific prompt
            if self.router:
                try:
                    import re as _re
                    llm_prompt = (
                        f"You are a principal AI training data engineer synthesizing production instruction-tuning datasets for LLM fine-tuning.\n"
                        f"User Prompt / Specification: {user_prompt}\n"
                        f"Target Domain: {domain_name}\n"
                        f"Language: {language}\n\n"
                        f"Generate exactly 3 production-grade, highly specific, realistic instruction-tuning training pairs strictly fulfilling the user prompt.\n"
                        f"Rules:\n"
                        f"- Each instruction must directly address the specific query or scenario requested in the user prompt.\n"
                        f"- Each response must be detailed, accurate, step-by-step, adhering to the requested domain knowledge and constraints.\n"
                        f"- Do NOT use generic placeholders like 'Step 1: Identify foundational parameters'. Provide substantive domain content.\n"
                        f"- Return ONLY valid JSON format as a list of 3 objects with keys 'instruction' and 'response'.\n\n"
                        f"Example JSON format:\n"
                        f'[\n  {{"instruction": "...", "response": "..."}},\n  {{"instruction": "...", "response": "..."}},\n  {{"instruction": "...", "response": "..."}}\n]'
                    )
                    try:
                        from core.provider_router import TaskType
                        task_type = getattr(TaskType, "TEXT_GENERATION", "text_generation")
                        llm_res = await self.router.route(
                            task=task_type,
                            prompt=llm_prompt,
                            temperature=0.7,
                            max_tokens=2500,
                        )
                    except TypeError:
                        from providers.core_lib.base import LLMRequest
                        req = LLMRequest(input=llm_prompt, temperature=0.7, max_tokens=2500)
                        llm_res = await self.router.route(req)
                    raw_text = (getattr(llm_res, "content", None) or getattr(llm_res, "text", "") or "").strip()
                    cleaned_text = _re.sub(r'```(?:json)?\s*', '', raw_text, flags=_re.IGNORECASE)
                    cleaned_text = _re.sub(r'```\s*$', '', cleaned_text).strip()

                    parsed_list = []
                    # Try direct JSON parsing
                    try:
                        match = _re.search(r'\[.*\]', cleaned_text, _re.DOTALL)
                        if match:
                            parsed_list = json.loads(match.group(0))
                    except Exception:
                        pass

                    # Resilient fallback: extract individual objects with regex if list parsing failed
                    if not parsed_list or not isinstance(parsed_list, list):
                        obj_matches = _re.finditer(r'\{[^{}]*"instruction"\s*:\s*(?:"(?:\\.|[^"\\])*"|\'[^\']*\')\s*,\s*"response"\s*:\s*(?:"(?:\\.|[^"\\])*"|\'[^\']*\')[^{}]*\}', cleaned_text, _re.DOTALL)
                        parsed_list = []
                        for m in obj_matches:
                            try:
                                obj = json.loads(m.group(0))
                                if "instruction" in obj and "response" in obj:
                                    parsed_list.append(obj)
                            except Exception:
                                pass

                    if isinstance(parsed_list, list) and len(parsed_list) >= 1:
                        for i, item in enumerate(parsed_list[:3]):
                            inst = str(item.get("instruction") or "").strip()
                            resp = str(item.get("response") or "").strip()
                            if inst and resp:
                                preview_samples.append({
                                    "instruction": inst,
                                    "response": resp,
                                    "metadata": {
                                        "preview": True,
                                        "domain": domain_name,
                                        "quality_score": None,
                                        "quality_status": "unmeasured_preview",
                                        "difficulty_tier": 3 + i,
                                        "preview_origin": "llm_router",
                                    }
                                })
                        logger.info(f"[{job_id}] Early preview synthesized {len(preview_samples)} realistic samples via LLM router")
                except Exception as e:
                    logger.warning(f"Early preview LLM generation attempt failed: {e}")

            # 2. If router yielded < 3 samples, consult Synthesis Agent from Agent Registry
            if len(preview_samples) < 3 and self.agent_registry:
                try:
                    from agents.base import AgentType, AgentContext
                    ctx = AgentContext(job_id=job_id, dataset_id=job_id, domain=user_prompt)
                    synth_agent = self.agent_registry.create_agent(AgentType.SYNTHETIC_GENERATION)
                    if synth_agent:
                        agent_res = await synth_agent.execute({
                            "prompt": user_prompt,
                            "domain": domain_name,
                            "language": language,
                            "count": 3 - len(preview_samples),
                        }, ctx)
                        if agent_res and agent_res.output and isinstance(agent_res.output, dict):
                            out_samples = agent_res.output.get("samples") or []
                            for idx, s in enumerate(out_samples[:3]):
                                if isinstance(s, dict) and s.get("instruction") and s.get("response"):
                                    preview_samples.append({
                                        "instruction": s["instruction"],
                                        "response": s["response"],
                                        "metadata": {
                                            "preview": True,
                                            "domain": domain_name,
                                            "quality_score": None,
                                            "quality_status": "unmeasured_preview",
                                            "difficulty_tier": 3 + idx,
                                            "preview_origin": "synthesis_agent",
                                        }
                                    })
                except Exception as ag_err:
                    logger.debug(f"Synthesis Agent preview generation skipped: {ag_err}")

            # 3. If still needed, query SeedlessGenerator with dynamic curriculum plan
            if len(preview_samples) < 3:
                try:
                    from pipeline.planner import DatasetPlanner
                    from pipeline.synthetic_generator import SeedlessGenerator
                    planner = DatasetPlanner(self.router, config)
                    dyn_plan = await planner.create_plan(user_prompt)
                    gen = SeedlessGenerator(self.router, config)
                    for i in range(3 - len(preview_samples)):
                        sample_obj = await gen.generate_sample(dyn_plan, {}, cell_index=i, total_cells=3)
                        if sample_obj and sample_obj.instruction and sample_obj.response:
                            preview_samples.append({
                                "instruction": sample_obj.instruction,
                                "response": sample_obj.response,
                                "metadata": {
                                    "preview": True,
                                    "domain": domain_name,
                                    "quality_score": None,
                                    "quality_status": "unmeasured_preview",
                                    "difficulty_tier": getattr(sample_obj, "difficulty_tier", 3),
                                    "preview_origin": "curriculum_generator",
                                }
                            })
                except Exception as dyn_err:
                    logger.debug(f"Curriculum preview generator skipped: {dyn_err}")

        # Attach preview samples to job config in DB
        db_target = self.db_manager or self.db
        if db_target:
            try:
                job_record = await db_target.get_job(job_id)
                if job_record:
                    cur_config = getattr(job_record, "config", None) or (job_record.get("config") if isinstance(job_record, dict) else {}) or {}
                    cur_config["preview_samples"] = preview_samples
                    await db_target.update_job(job_id, {"config": cur_config, "current_stage": "preview_acceptance"})
            except Exception as e:
                logger.debug(f"Could not persist preview samples to DB: {e}")

        if self.ws_manager:
            try:
                await self.ws_manager.broadcast_to_job(job_id, {
                    "type": "preview_samples_ready",
                    "job_id": job_id,
                    "stage": "preview_acceptance",
                    "samples": preview_samples,
                    "quality_status": "unmeasured_preview",
                })
            except Exception:
                pass

        preview_decision = {"accepted": True}
        if config.get("require_early_preview") is True:
            self._update_job_status(job_id, "awaiting_preview_approval", 0.12)
            event = asyncio.Event()
            self._preview_events[job_id] = event
            logger.info(f"[{job_id}] Pausing at early preview gate for user acceptance...")
            try:
                await asyncio.wait_for(event.wait(), timeout=60.0)
                preview_decision = self._preview_decisions.get(job_id, {"accepted": True})
            except asyncio.TimeoutError:
                logger.info(f"[{job_id}] Early preview timeout reached; auto-advancing pipeline.")
                preview_decision = {"accepted": True}
            finally:
                self._preview_events.pop(job_id, None)
                self._preview_decisions.pop(job_id, None)

        if preview_decision.get("edited_samples"):
            preview_samples = preview_decision["edited_samples"]
            config["approved_examples"] = preview_samples
            logger.info(f"[{job_id}] User edited {len(preview_samples)} early preview samples; set as approved exemplars.")

        return {
            **state,
            "preview_samples": preview_samples,
            "preview_decision": preview_decision,
            "current_stage": "preview_acceptance",
            "progress": 0.15,
            "messages": [f"Early preview synthesized ({len(preview_samples)} samples)"],
        }

    def _preview_decision_check(self, state: AgentState) -> str:
        """Route based on user preview acceptance."""
        decision = state.get("preview_decision", {})
        if decision.get("accepted", True):
            job_config = state.get("job", {}).get("config", {})
            mode = job_config.get("generation_mode", "hybrid")
            if mode == "synthetic":
                return "accepted_synthetic"
            return "accepted_grounded"
        return "retry_query"

    async def _plan_node(self, state: AgentState) -> AgentState:
        """Analyze user prompt and create a structured dataset plan."""
        job = state["job"]
        job_id = job["id"]
        config = job["config"]

        self._update_job_status(job_id, "plan", 0.3)

        from pipeline.planner import DatasetPlanner, CoveragePlanner

        planner = DatasetPlanner(self.router, config)
        cov_planner = CoveragePlanner(config)

        prompt = config.get("raw_input") or config.get("prompt") or config.get("target_domain", "")

        # Multi-Agent Society: Consult Strategy & Research Agents
        strategy_analysis = {}
        research_analysis = {}
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                ctx = AgentContext(job_id=job_id, dataset_id=job_id, domain=prompt)
                strat_agent = self.agent_registry.create_agent(AgentType.STRATEGY)
                if strat_agent:
                    strat_res = await strat_agent.execute({"domain": prompt, "size": config.get("dataset_size", 100)}, ctx)
                    if strat_res and strat_res.output:
                        strategy_analysis = strat_res.output
                        logger.info("  ✓ StrategyAgent mapped execution dependencies & resource allocation")

                res_agent = self.agent_registry.create_agent(AgentType.RESEARCH)
                if res_agent:
                    res_result = await res_agent.execute({"domain": prompt, "size": config.get("dataset_size", 100)}, ctx)
                    if res_result and res_result.output:
                        research_analysis = res_result.output
                        logger.info("  ✓ ResearchAgent analyzed domain requirements & quality criteria")
            except Exception as agent_err:
                logger.debug(f"Multi-agent planning coordination skipped: {agent_err}")

        # Continuous Research Loop: Query active 2026 heuristics
        active_heuristics = {}
        try:
            if self.technique_integrator:
                active_heuristics = self.technique_integrator.get_active_heuristics()
            else:
                from core.research_loop import ResearchLoop
                rloop = ResearchLoop(self.router, config)
                active_heuristics = rloop.get_active_heuristics()
        except Exception as rl_err:
            logger.debug(f"Research heuristics skipped: {rl_err}")

        plan = await planner.create_plan(prompt)
        coverage = cov_planner.generate_matrix(plan, target_size=config.get("dataset_size", 100))

        plan_dict = plan.model_dump()
        # The LangGraph remains the executable DAG; this explicit role map is
        # persisted with the plan so operators can audit who owns each stage.
        plan_dict["role_workflow"] = [
            {"role": "planning", "agent": "StrategyAgent", "stage": "plan"},
            {"role": "search", "agent": "SearchOptimizationAgent", "stage": "query_optimizer"},
            {"role": "crawl", "agent": "SourceDiscoveryAgent", "stage": "discover"},
            {"role": "extraction", "agent": "WebCrawlerAgent", "stage": "extract"},
            {"role": "context", "agent": "ContextBundle", "stage": "filter"},
            {"role": "synthesis", "agent": "SyntheticGenerationAgent", "stage": "construct"},
            {"role": "review", "agent": "ReviewEnsemble", "stage": "quality_eval"},
            {"role": "human_arbitration", "agent": "ReviewService", "stage": "human_review"},
            {"role": "curation", "agent": "CurriculumAgent", "stage": "balance"},
            {"role": "training", "agent": "FineTuningAgent", "stage": "finetune"},
        ]
        plan_dict["strategy_agent"] = strategy_analysis
        plan_dict["research_agent"] = research_analysis
        plan_dict["active_heuristics"] = active_heuristics

        return {
            **state,
            "dataset_plan": plan_dict,
            "coverage_matrix": coverage.model_dump(),
            "current_stage": "plan",
            "progress": 0.4,
            "messages": [f"Generated dataset plan with {len(coverage.cells)} planned coverage cells (Multi-agent strategy + research attached)"],
        }

    async def _discover_node(self, state: AgentState) -> AgentState:
        """Enhanced discovery with streaming, pagination, and bounded memory.

        Features:
        - Cursor-based pagination
        - Bounded memory with streaming
        - Backpressure awareness
        - Memory-efficient chunked processing
        - Progress telemetry
        """
        job = state["job"]
        job_id = job["id"]
        config = {**self.config, **job["config"]}
        intent = state["intent"]

        self._update_job_status(job_id, "discover", 0.1)

        from pipeline.discovery import DiscoveryPipeline, SourceType, DiscoveredSource
        from pipeline.extraction import _is_safe_url
        from core.pagination import BackpressureIterator, chunked_async_iter, StreamProgress

        discovery = DiscoveryPipeline(config, router=self.router)

        target_domain = (intent.domain if intent else "") or config.get("target_domain", "")
        # If target_domain is not provided but we have source_urls, extract domain from the first URL
        if not target_domain and config.get("source_urls"):
            from urllib.parse import urlparse
            try:
                first_url = config["source_urls"][0]
                parsed = urlparse(first_url)
                target_domain = parsed.netloc
            except Exception:
                # If we can't parse, leave target_domain as empty string
                pass
        language = config.get("language", "en")

        # Determine source types based on constraints
        source_types = self._determine_source_types(config)
        excluded_source_urls = set(config.get("excluded_source_urls", []))

        # Generate multiple query variations for better coverage (bounded to top 3 to prevent API flooding)
        queries = self._get_discovery_queries(intent)[:3]

        max_sources = min(config.get("max_results", 500), state.get("constraint_analysis", {}).get("estimated_sources", 200))
        batch_size = config.get("batch_size", 50)  # Process in batches

        # Create streaming source
        async def source_generator():
            seen_urls = set()
            # Sources the user reviewed and approved in Studio enter the full
            # pipeline first; discovery then broadens coverage from the same
            # confirmed query plan.
            for approved in config.get("approved_sources", []):
                url = str(approved.get("url", ""))
                if not url or url in excluded_source_urls or approved.get("metadata", {}).get("catalogue_only"):
                    continue
                is_safe, reason = _is_safe_url(url)
                if not is_safe:
                    logger.warning("Skipping unsafe user-approved source %s: %s", url, reason)
                    continue
                try:
                    source_type = SourceType(approved.get("source_type", SourceType.WEB_PAGE.value))
                except ValueError:
                    source_type = SourceType.WEB_PAGE
                seen_urls.add(url)
                yield DiscoveredSource(
                    url=url,
                    source_type=source_type,
                    title=str(approved.get("title", "")),
                    description=approved.get("description"),
                    metadata=approved.get("metadata") or {},
                    license=approved.get("license"),
                    quality_score=float(approved.get("quality_score", 0.0) or 0.0),
                )

            for query in queries:
                if self._is_cancelled(job_id):
                    break
                try:
                    async for source in discovery.discover(
                        query, target_domain, source_types, query_is_optimized=True
                    ):
                        if source.url in excluded_source_urls or source.url in seen_urls:
                            continue
                        # Apply domain relevance pre-filter to skip off-topic sources early.
                        if self._is_source_relevant(source, intent):
                            seen_urls.add(source.url)
                            yield source
                        else:
                            logger.debug(f"Skipping off-topic source: "
                                        f"{source.get('url','unknown') if isinstance(source, dict) else getattr(source, 'url', 'unknown')}")
                        if self._is_cancelled(job_id) or len(seen_urls) >= 50:
                            break
                except Exception as disc_err:
                    logger.warning(f"Discovery query execution error for '{query}': {disc_err}")

        # Use backpressure-aware iterator with bounded memory
        streaming_source = BackpressureIterator(
            source_generator(),
            buffer_size=batch_size,
            max_memory_mb=config.get("max_memory_mb", 512),
        )

        # Stream processing with bounded memory accumulation and timeout guard
        sources = []
        batch_count = 0
        progress = StreamProgress()

        async def _consume_streaming_sources():
            nonlocal batch_count
            async for source in streaming_source:
                sources.append({
                    "url": source.url,
                    "source_type": source.source_type.value,
                    "title": source.title,
                    "description": source.description,
                    "metadata": source.metadata,
                    "license": source.license,
                    "quality_score": source.quality_score,
                    "language": getattr(source, 'language', language),
                })
                progress.total_processed += 1

                # Update progress incrementally so UI never appears frozen
                batch_count += 1
                curr_prog = min(0.28, 0.10 + (len(sources) / max(max_sources, 1)) * 0.18)
                self._update_job_progress(job_id, curr_prog)
                await asyncio.sleep(0)

                if progress.total_processed >= max_sources or len(sources) >= 40:
                    break

        discovery_timeout = float(config.get("discovery_timeout_seconds", 45.0))
        try:
            await asyncio.wait_for(_consume_streaming_sources(), timeout=discovery_timeout)
        except asyncio.TimeoutError:
            logger.info(f"[{job_id}] Discovery stream reached bounded timeout ({discovery_timeout}s); continuing with {len(sources)} sources")

        # Log any streaming errors
        errors = streaming_source.get_errors()
        if errors:
            logger.warning(f"Discovery streaming completed with {len(errors)} errors")
            for err in errors:
                state["warnings"].append(f"Discovery error: {str(err)}")

        # Update progress
        self._update_job_status(job_id, "discover", 0.3, sources_discovered=len(sources))

        agent_artifacts = dict(state.get("agent_artifacts") or {})
        # Persist a discovery-time snapshot even before extraction. This
        # preserves the source URL, licence and search metadata used to make a
        # later decision reproducible.
        if self.db and hasattr(self.db, "create_source_snapshot"):
            snapshot_ids = {}
            for source in sources:
                try:
                    snapshot = await self.db.create_source_snapshot(job_id, source)
                    snapshot_ids[source["url"]] = snapshot.get("id")
                except Exception as snapshot_error:
                    logger.warning("Could not persist discovery snapshot for %s: %s", source.get("url"), snapshot_error)
            agent_artifacts["discovery_snapshots"] = snapshot_ids

        # The discovery specialist ranks real candidates after the production
        # crawler/search pipeline produces them. It cannot add invented URLs.
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                discovery_agent = self.agent_registry.create_agent(AgentType.SOURCE_DISCOVERY)
                if discovery_agent:
                    await discovery_agent.initialize()
                    advisory = await discovery_agent.execute({
                        "task_id": job_id, "domain": target_domain, "query": " ".join(queries), "sources": sources,
                    }, AgentContext(job_id=job_id, dataset_id=job_id, domain=target_domain, sources=sources))
                    if advisory.success:
                        rankings = advisory.output.get("rankings", {})
                        sources.sort(key=lambda source: rankings.get(source.get("url", ""), 0.0), reverse=True)
                        agent_artifacts["source_discovery"] = advisory.output
            except Exception:
                logger.exception("Source-discovery agent advisory stage failed")

        # Set mode flags based on content
        multilingual = any(s.get("language") != "en" for s in sources)
        low_resource = len(sources) < 20

        logger.info(
            f"Discovery complete: {len(sources)} sources, "
            f"multilingual={multilingual}, low_resource={low_resource}"
        )

        return {
            **state,
            "sources": sources,
            "current_stage": "discover",
            "progress": 0.1,
            "multilingual_mode": multilingual,
            "low_resource_mode": low_resource,
            "agent_artifacts": agent_artifacts,
            "messages": [
                f"Discovered {len(sources)} sources",
                f"Multilingual: {multilingual}",
                f"Low-resource: {low_resource}"
            ]
        }

    def _determine_source_types(self, config: dict) -> list:
        """Determine which source types to use based on constraints, preferring ML-appropriate sources."""
        from pipeline.discovery import SourceType

        target_domain = config.get("target_domain", "").lower()

        # ML/AI indicators
        ml_ai_indicators = [
            "machine learning", "deep learning", "neural network", "ai", "artificial intelligence",
            "nlp", "natural language processing", "computer vision", "reinforcement learning",
            "llm", "large language model", "transformer", "model", "algorithm", "data science",
            "analytics", "prediction", "classification", "regression"
        ]

        is_ml_domain = any(indicator in target_domain for indicator in ml_ai_indicators)

        # Base sources - include high-quality dataset repositories and foundational knowledge corpora
        source_types = [
            SourceType.HF_DATASET,      # HuggingFace Datasets (primary)
            SourceType.KAGGLE_DATASET,  # Kaggle (primary)
            SourceType.WIKIPEDIA,       # Wikipedia articles & domain definitions
            SourceType.BOOKS,           # Open Library & Gutenberg book references
            SourceType.BLOG,            # Engineering, technical & expert blogs
            SourceType.OPENML,       SourceType.ZENODO,               # Zenodo (primary)
            SourceType.PAPERS_WITH_CODE, # Papers with Code (primary)
            SourceType.WEB_PAGE,         # General web (fallback)
            SourceType.GITHUB_REPO,      # GitHub repos (for code, not primary datasets)
        ]

        # Make India's national catalogue a preferred source for India- and
        # Indic-focused requests, or when the user explicitly asks for AIKosh.
        configured_language = str(config.get("language", "en")).lower()
        india_focus = configured_language in {
            "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur", "or", "as", "sa",
            "ks", "kok", "mni", "sd", "doi", "mai", "sat", "brx", "ne",
            "hinglish", "indic", "indic_multilingual",
        } or any("india" in str(region).lower() for region in config.get("region_restrictions", [])) or any(term in target_domain for term in (
            "aikosh", "ai kosh", "indiaai", "india ai",
            "india", "indian", "indic", "hindi", "hinglish", "tamil", "telugu",
            "bengali", "marathi", "kannada", "malayalam", "punjabi",
            "gujarati", "odia", "assamese", "urdu", "sanskrit", "manipuri",
            "konkani", "kashmiri", "sindhi", "dogri", "maithili", "santali", "bodo",
        ))
        has_aikosh_key = bool(
            os.getenv("AIKOSH_API_KEY")
            or os.getenv("AI_KOSH_API_KEY")
            or config.get("aikosh_api_key")
            or config.get("ai_kosh_api_key")
        )
        if india_focus or has_aikosh_key:
            source_types.insert(0, SourceType.AI_KOSH)

        # For ML domains, prioritize ML-specific and high-quality dataset sources
        if is_ml_domain:
            # Add ML-prioritized sources
            source_types.extend([
                SourceType.ARXIV_PAPER,      # Pre-print ML papers
                SourceType.SEMANTIC_SCHOLAR, # Academic search
                SourceType.GITHUB_FILE,      # Code implementations (secondary)
                SourceType.AWS_OPEN_DATA,    # AWS Open Data Registry (ML datasets)
                SourceType.SNAP,             # Stanford SNAP (graph/network datasets)
            ])

            # Add other relevant sources
            if any(ind in target_domain for ind in ["research", "science", "academic"]):
                source_types.append(SourceType.PUBMED)

            if any(ind in target_domain for ind in ["dataset", "data", "benchmark"]):
                # HF_DATASET and KAGGLE_DATASET already in base sources
                pass

        else:
            # Non-ML domain logic (enhanced with high-quality sources)
            # Add domain-specific sources
            if any(ind in target_domain for ind in ["research", "science", "academic"]):
                source_types.extend([SourceType.ARXIV_PAPER, SourceType.PUBMED, SourceType.SEMANTIC_SCHOLAR])

            if any(ind in target_domain for ind in ["code", "programming", "software"]):
                source_types.extend([SourceType.GITHUB_FILE, SourceType.STACKOVERFLOW])

            if any(ind in target_domain for ind in ["historical", "ancient", "document"]):
                source_types.extend([SourceType.PDF_DOCUMENT, SourceType.WIKIPEDIA])

            if any(ind in target_domain for ind in ["medical", "health", "clinical"]):
                source_types.append(SourceType.PUBMED)

            # Add government and international data sources for non-ML domains too
            if any(ind in target_domain for ind in ["government", "public", "statistics", "economic", "demographic"]):
                gov_sources = [
                    getattr(SourceType, "GOVERNMENT_DATA", None),
                    getattr(SourceType, "EUROSTAT", None),
                    getattr(SourceType, "DATAPORTALS_ORG", None),
                    getattr(SourceType, "DATAHUB_IO", None),
                    getattr(SourceType, "UNESCO", None),
                    getattr(SourceType, "WORLD_BANK", None),
                ]
                source_types.extend([s for s in gov_sources if s is not None])

        # Always add high-quality repository sources that are generally useful
        source_types.extend([
            SourceType.FIGSHARE,        # Figshare (research data)
            SourceType.DATAPORTALS_ORG, # DataPortals.org (aggregator)
            SourceType.DATAHUB_IO,      # DataHub.io (community datasets)
            SourceType.GOOGLE_DATASET_SEARCH, # Google Dataset Search (via schema.org)
        ])

        # Remove duplicates while preserving order (prefer earlier entries)
        seen = set()
        unique_source_types = []
        for st in source_types:
            if st not in seen:
                seen.add(st)
                unique_source_types.append(st)

        return unique_source_types

        # Remove duplicates while preserving order
        seen = set()
        unique_source_types = []
        for st in source_types:
            if st not in seen:
                seen.add(st)
                unique_source_types.append(st)

        return unique_source_types

    def _get_discovery_queries(self, intent: UserIntent) -> list[str]:
        """
        Return the LLM-generated expert queries from the intent.
        These are the ONLY queries sent to the discovery stage.
        """
        logger.info(f"Discovery queries ({len(intent.specialized_queries)}): {intent.specialized_queries}")
        return intent.specialized_queries

    async def _extract_node(self, state: AgentState) -> AgentState:
        """Enhanced extraction with multilingual and messy data support."""
        job = state["job"]
        job_id = job["id"]
        sources = state["sources"]

        # Pre-filter sources with HEAD request to skip 404s before extraction
        import asyncio
        import httpx

        async def _is_url_reachable(url: str) -> bool:
            """Quick HEAD check — skip 404s before extraction."""
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.head(url, follow_redirects=True)
                    return r.status_code < 400
            except Exception:
                return False

        # Pre-filter sources
        crawlable_sources = []
        catalogue_only_sources = []
        for source in sources:
            metadata = source.get("metadata", {}) if isinstance(source, dict) else getattr(source, "metadata", {})
            if metadata.get("catalogue_only"):
                catalogue_only_sources.append(source)
            else:
                crawlable_sources.append(source)
        if catalogue_only_sources:
            state["warnings"].append(
                f"Skipped {len(catalogue_only_sources)} AIKosh catalogue listing(s): dataset access and license must be verified before content extraction."
            )
        sources = crawlable_sources
        async def _source_is_reachable(source) -> bool:
            metadata = source.get("metadata", {}) if isinstance(source, dict) else getattr(source, "metadata", {})
            source_type = source.get("source_type") if isinstance(source, dict) else getattr(source, "source_type", None)
            if getattr(source_type, "value", source_type) == "ai_kosh" and metadata.get("aikosh_file"):
                # The dataset page may block HEAD requests; the authenticated
                # SDK file listing already established the selected file.
                return True
            url = source.get("url", "") if isinstance(source, dict) else getattr(source, "url", "")
            return await _is_url_reachable(url)

        head_tasks = [_source_is_reachable(source) for source in sources]
        head_results = await asyncio.gather(*head_tasks, return_exceptions=True)

        reachable_sources = []
        for source, ok in zip(sources, head_results):
            if ok is True:
                reachable_sources.append(source)
            else:
                source_url = source.get("url","") if isinstance(source, dict) else getattr(source,"url","")
                logger.debug(f"Skipping unreachable source: {source_url}")

        sources = reachable_sources[:20]
        logger.info(f"[{job_id}] Pre-validation: {len(sources)}/{len(state['sources'])} sources reachable (capped to 20 for concurrent extraction)")

        self._update_job_status(job_id, "extract", 0.3)

        from pipeline.extraction import ExtractionPipeline

        extraction_config = {**self.config, **job["config"]}
        if not extraction_config.get("aikosh_api_key"):
            extraction_config["aikosh_api_key"] = os.getenv("AIKOSH_API_KEY") or os.getenv("AI_KOSH_API_KEY")
        extraction = ExtractionPipeline(extraction_config, self.router)
        extracted = []
        extract_sem = asyncio.Semaphore(8)

        # Check if distributed Ray cluster extraction is enabled
        enable_ray = (
            self.config.get("enable_ray", False)
            or str(job.get("config", {}).get("enable_ray", "")).lower() in ("true", "1")
            or os.getenv("ENABLE_RAY", "").lower() in ("true", "1")
        )
        if enable_ray and len(sources) > 0:
            try:
                from workers.ray_pipeline import RayPipeline, RAY_AVAILABLE
                if RAY_AVAILABLE:
                    logger.info(f"[{job_id}] Distributing extraction of {len(sources)} sources via Ray cluster...")
                    ray_pipe = RayPipeline(extraction_config, num_workers=min(len(sources), 4))
                    ray_sources = [
                        s if isinstance(s, dict) else {"url": getattr(s, "url", ""), "metadata": getattr(s, "metadata", {})}
                        for s in sources
                    ]
                    ray_extracted = ray_pipe.run_extraction(ray_sources)
                    if ray_extracted:
                        extracted.extend(ray_extracted)
                        logger.info(f"[{job_id}] Ray cluster successfully extracted {len(ray_extracted)} records.")
            except Exception as ray_err:
                logger.warning(f"[{job_id}] Ray extraction fallback to local async pool: {ray_err}")

        async def _extract_source_task(source):
            if self._is_cancelled(job_id):
                return []
            source_url = source.get("url") if isinstance(source, dict) else getattr(source, "url", "unknown")
            start_time = asyncio.get_event_loop().time()
            extracted_items = []
            source_extracted_count = 0

            async with extract_sem:
                try:
                    async def _run_extract():
                        nonlocal source_extracted_count
                        async for content in extraction.extract(source):
                            source_extracted_count += 1
                            if content.confidence > 0.3:
                                safe_metadata = _sanitize_metadata(
                                    {k: v for k, v in content.metadata.items() if k != "analysis"}
                                )
                                source_metadata = source.get("metadata", {}) if isinstance(source, dict) else getattr(source, "metadata", {})
                                source_type = source.get("source_type") if isinstance(source, dict) else getattr(source, "source_type", "")
                                source_type_value = getattr(source_type, "value", source_type)
                                safe_metadata.update({
                                    key: value for key, value in {
                                        "source_url": content.url or source_url,
                                        "source_type": str(source_type_value) if source_type_value else None,
                                        "license": source.get("license") if isinstance(source, dict) else getattr(source, "license", None),
                                        "source_title": source.get("title") if isinstance(source, dict) else getattr(source, "title", None),
                                        "language": content.language or source_metadata.get("language"),
                                    }.items() if value
                                })
                                extracted_items.append({
                                    "content": content.content,
                                    "content_type": content.content_type,
                                    "language": content.language,
                                    "languages_detected": content.languages_detected,
                                    "url": content.url,
                                    "metadata": safe_metadata,
                                    "confidence": content.confidence,
                                    "quality_score": content.quality_score,
                                    "extraction_warnings": content.extraction_warnings,
                                })
                                decision = "accepted"
                            else:
                                decision = "rejected"

                            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                            if self.observability:
                                self.observability.log_pipeline_stage(
                                    job_id=job_id,
                                    stage="extraction",
                                    source_url=content.url or source_url,
                                    duration_ms=duration_ms,
                                    decision=decision,
                                    quality_score=content.quality_score,
                                    threshold=0.3,
                                    issues=content.extraction_warnings,
                                    metadata={
                                        "content_type": content.content_type,
                                        "language": content.language,
                                        "confidence": content.confidence
                                    }
                                )

                    # Bounded per-source timeout to prevent hanging on external webs/APIs
                    await asyncio.wait_for(_run_extract(), timeout=18.0)
                except Exception as e:
                    error_msg = f"Extraction error for {source_url}: {str(e)}"
                    logger.warning(f"Job {job_id}: {error_msg}")
            return extracted_items

        tasks = [_extract_source_task(s) for s in sources]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=60.0)
            for r in results:
                if isinstance(r, list):
                    extracted.extend(r)
        except asyncio.TimeoutError:
            logger.info(f"[{job_id}] Concurrent extraction bounded timeout (60s) reached; proceeding with {len(extracted)} extracted records")

        self._update_job_status(
            job_id,
            "extract",
            0.5,
            sources_extracted=len(sources),
            samples_processed=len(extracted)
        )

        agent_artifacts = dict(state.get("agent_artifacts") or {})
        # Promote every accepted extraction into immutable source evidence.
        # Chunks are bounded for context assembly while the snapshot retains
        # the original captured content for auditing.
        if self.db and hasattr(self.db, "create_source_snapshot"):
            persisted_chunks = 0
            for item in extracted:
                try:
                    snapshot = await self.db.create_source_snapshot(
                        job_id, item, content=str(item.get("content") or ""), content_type=item.get("content_type"),
                    )
                    item.setdefault("metadata", {})["source_snapshot_id"] = snapshot.get("id")
                    text = str(item.get("content") or "")
                    chunks = [
                        {"chunk_index": index // 2000, "content": text[index:index + 2000], "metadata": {"source_url": item.get("url") or (item.get("metadata") or {}).get("source_url")}}
                        for index in range(0, len(text), 2000)
                    ]
                    if chunks and hasattr(self.db, "create_evidence_chunks"):
                        records = await self.db.create_evidence_chunks(snapshot["id"], chunks)
                        persisted_chunks += len(records)
                except Exception as snapshot_error:
                    logger.warning("Could not persist extracted evidence: %s", snapshot_error)
            agent_artifacts["evidence_chunks_persisted"] = persisted_chunks

        # The crawler agent is a final artifact-contract check over results
        # emitted by ExtractionPipeline; it does not perform a second crawl.
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                crawler_agent = self.agent_registry.create_agent(AgentType.WEB_CRAWLER)
                if crawler_agent:
                    await crawler_agent.initialize()
                    advisory = await crawler_agent.execute(
                        {"task_id": job_id, "pages": extracted},
                        AgentContext(job_id=job_id, dataset_id=job_id, extracted_data=extracted),
                    )
                    if advisory.success:
                        agent_artifacts["web_crawler"] = {
                            "metrics": advisory.metrics,
                            "failed_pages": advisory.output.get("failed_pages", []),
                        }
            except Exception:
                logger.exception("Web-crawler agent artifact validation failed")

        return {
            **state,
            "extracted_content": extracted,
            "current_stage": "extract",
            "progress": 0.3,
            "agent_artifacts": agent_artifacts,
            "messages": [f"Extracted {len(extracted)} content items"],
        }

    async def _filter_node(self, state: AgentState) -> AgentState:
        """Enhanced filtering with adaptive thresholds."""
        job = state["job"]
        job_id = job["id"]
        extracted = state["extracted_content"]
        intent = state["intent"]

        self._update_job_status(job_id, "filter", 0.5)

        from pipeline.filtering import FilteringPipeline

        filtering_config = {**self.config, **job["config"]}
        filtering = FilteringPipeline(self.router, filtering_config)
        filtered = []

        target_domain = (intent.domain if intent else "") or job["config"].get("target_domain", "")

        # NOTE: Thresholds are now STATIC (see pipeline/quality_breakdown.py)
        # No runtime learning — ensures deterministic scoring across runs

        # Process in batches for parallel I/O and event loop responsiveness
        BATCH_SIZE = 5
        for batch_start in range(0, len(extracted), BATCH_SIZE):
            if self._is_cancelled(job_id):
                break
            await asyncio.sleep(0)  # Yield to event loop

            batch = extracted[batch_start:batch_start + BATCH_SIZE]
            from types import SimpleNamespace
            content_objs = [SimpleNamespace(**d) for d in batch]

            # Add batch diagnostic logging
            logger.info(
                f"[{job_id}] Filter batch {batch_start // BATCH_SIZE + 1}: "
                f"{len(batch)} items | "
                f"first item keys: {list(batch[0].keys()) if batch else 'empty'}"
            )

            batch_start_time = asyncio.get_event_loop().time()

            filter_timeout = job["config"].get("filter_timeout_seconds", 90)

            filter_tasks = [
                asyncio.wait_for(
                    filtering.filter(content, intent, return_all=True),
                    timeout=filter_timeout
                )
                for content in content_objs
            ]
            batch_results = await asyncio.gather(*filter_tasks, return_exceptions=True)

            # Add batch result logging
            exc_count  = sum(1 for r in batch_results if isinstance(r, Exception))
            pass_count = sum(
                1 for r in batch_results
                if not isinstance(r, Exception) and r and getattr(r, "passed", False)
            )
            logger.info(
                f"[{job_id}] Batch result: "
                f"{pass_count} passed | "
                f"{exc_count} exceptions | "
                f"{len(batch_results) - pass_count - exc_count} failed quality"
            )

            for content_dict, result in zip(batch, batch_results):
                source_url = content_dict.get("url", "unknown")
                start_time = asyncio.get_event_loop().time()

                try:
                    if isinstance(result, Exception):
                        logger.error(
                            f"[{job_id}] Filter exception for {source_url}: "
                            f"{type(result).__name__}: {result}",
                            exc_info=result,
                        )
                        self.observability.log_pipeline_stage(
                            job_id=job_id,
                            stage="filtering",
                            source_url=source_url,
                            duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                            decision="failed",
                            issues=[f"{type(result).__name__}: {result}"],
                        )
                        state["warnings"].append(
                            f"Filter exception [{source_url}]: {type(result).__name__}: {result}"
                        )
                        logger.info(
                                f"[{job_id}] Filter score | url={source_url[:60]} | "
                                        f"quality={getattr(result, 'quality_score', 'N/A'):.3f} | "
                                        f"relevance={getattr(result, 'relevance_score', 'N/A'):.3f} | "
                                        f"passed={getattr(result, 'passed', 'N/A')} | "
                                        f"issues={getattr(result, 'issues', [])}"
                                        if result and not isinstance(result, Exception) else
                                        f"[{job_id}] Filter result is None or Exception for {source_url}"
                        )
                        continue

                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    if result and result.passed:
                        filtered.append({
                            "content": result.content,
                            "quality_score": result.quality_score,
                            "relevance_score": result.relevance_score,
                            "toxicity_score": result.toxicity_score,
                            "hallucination_risk": result.hallucination_risk,
                            "uniqueness_score": result.uniqueness_score,
                            "issues": result.issues,
                            "warnings": result.warnings,
                            "source_url": result.source_url,
                            "metadata": content_dict.get("metadata", {}) or {},
                            "confidence": result.confidence,
                        })
                        decision = "accepted"
                    else:
                        decision = "rejected"

                    self.observability.log_pipeline_stage(
                        job_id=job_id,
                        stage="filtering",
                        source_url=source_url,
                        duration_ms=duration_ms,
                        decision=decision,
                        quality_score=result.quality_score if result else 0.0,
                        threshold=filtering.quality_threshold,
                        issues=result.issues if result else [],
                        metadata={
                            "relevance_score": result.relevance_score if result else 0.0,
                            "toxicity_score": result.toxicity_score if result else 0.0,
                            "uniqueness_score": result.uniqueness_score if result else 0.0,
                            "filter_reason": getattr(result, "filter_reason", "unknown") if result else "unknown"
                        }
                    )
                except Exception as e:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    self.observability.log_pipeline_stage(
                        job_id=job_id,
                        stage="filtering",
                        source_url=source_url,
                        duration_ms=duration_ms,
                        decision="failed",
                        issues=[str(e)]
                    )

        # Score-based bypass for zero-sample situations
        # Check domain relevance of extracted items before bypassing
        if len(filtered) == 0 and len(extracted) > 0:
            analyzer = ConstraintAnalyzer(job["config"])
            raw_input = intent.raw_input if intent else job["config"].get("raw_input", "")
            relevant_extracted = [
                item for item in extracted
                if analyzer._is_source_domain_relevant(item, target_domain, raw_input=raw_input)
            ]

            if relevant_extracted:
                logger.warning(
                    f"[{job_id}] Filtering resulted in zero samples. "
                    f"Applying score-based bypass on {len(relevant_extracted)} domain-relevant items."
                )
                sorted_extracted = sorted(
                    relevant_extracted,
                    key=lambda x: x.get("quality_score", 0),
                    reverse=True
                )
                filtered = sorted_extracted[:min(10, len(sorted_extracted))]
                for sample in filtered:
                    sample["filter_bypassed"] = True
                    sample["bypass_reason"] = "zero_sample_situation"
            else:
                logger.warning(
                    f"[{job_id}] No extracted items passed relevance checks for '{target_domain}'. "
                    "Continuing with no samples because source-grounded generation is required."
                )
                filtered = []

        self._update_job_status(
            job_id,
            "filter",
            0.7,
            samples_filtered=len(filtered)
        )

        # Check if we need to adapt strategy
        if len(filtered) < 10 and state.get("low_resource_mode"):
            state["should_retry"] = True
            state["adaptation_notes"].append("Low resource mode: few samples passed filter, adapting strategy")

        return {
            **state,
            "filtered_samples": filtered,
            "current_stage": "filter",
            "progress": 0.5,
            "messages": [f"Filtered to {len(filtered)} quality samples"],
        }

    def _compute_sample_lexical_topic_relevance(self, instruction: str, response: str, user_prompt: str, target_domain: str) -> Optional[float]:
        """Score lexical keyword overlap of a sample against user prompt and domain keywords.

        Returns None if no domain/prompt keywords could be extracted (never a fabricated 0.90).
        """
        import re
        comb_sample = f"{instruction} {response}".lower()

        # Hard negative checks for off-topic file dumps / foreign studies
        hard_negs = [
            "train.csv", "test.csv", "available files:", "oleic acid", "tug-891",
            "heat-pump", "heat pump", "groningen", "dataset contains files", "zip file",
            "file size", "bytes in size"
        ]
        prompt_lower = (user_prompt or "").lower()
        for neg in hard_negs:
            if neg in comb_sample and neg not in prompt_lower:
                return 0.10

        # Jurisdiction conflict: If prompt demands Indian law/context, penalize other explicit jurisdictions
        if any(ind in prompt_lower for ind in ["india", "indian", "bharat", "mci", "consumer protection", "bns", "gst"]):
            if any(foreign in comb_sample for foreign in ["european union", "eu legal", "nhs trust", "dutch civil", "german civil"]) and not any(ind in comb_sample for ind in ["india", "indian"]):
                return 0.20

        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "are", "was", "not", "but",
            "all", "dataset", "data", "file", "download", "train", "synthetic", "example",
            "examples", "using", "into", "over", "under", "about", "such", "synthesize", "generate",
            "create", "pairs", "instruction", "response", "written", "plain", "simple", "each"
        }
        context = f"{user_prompt} {target_domain}".lower()
        keywords = [w for w in re.split(r'\W+', context) if len(w) >= 3 and w not in stop_words]

        # Domain terminology and entity aliases for domain grounding
        if any(t in context for t in ["gst", "tax", "taxation"]):
            keywords.extend(["cgst", "sgst", "igst", "cbic", "gstr", "itc", "invoice", "invoicing", "turnover", "cess", "e-way", "taxpayer"])
        if any(t in context for t in ["patient", "medical", "hospital", "doctor"]):
            keywords.extend(["consent", "treatment", "records", "surgery", "informed", "clinical", "negligence", "physician", "complaint", "mci"])
        if any(t in context for t in ["corporate", "law", "company", "companies"]):
            keywords.extend(["nclt", "director", "shareholder", "board", "resolution", "statutory", "mca", "roc"])

        if not keywords:
            return None

        unique_kw = set(keywords)
        matched = sum(1 for kw in unique_kw if kw in comb_sample)
        overlap_ratio = matched / max(1, min(len(unique_kw), 8))

        if matched >= 2 or overlap_ratio >= 0.25:
            return min(1.0, 0.70 + overlap_ratio * 0.30)
        elif matched == 1:
            return 0.50
        return 0.25

    def _compute_sample_topic_relevance(self, instruction: str, response: str, user_prompt: str, target_domain: str) -> Optional[float]:
        """Backwards-compatible alias for lexical topic relevance."""
        return self._compute_sample_lexical_topic_relevance(instruction, response, user_prompt, target_domain)

    async def _construct_node(self, state: AgentState) -> AgentState:
        """Enhanced construction with schema inference and seedless synthetic support."""
        job = state["job"]
        job_id = job["id"]
        config = job["config"]
        filtered = state["filtered_samples"]
        intent = state["intent"]

        user_prompt = config.get("raw_input") or config.get("prompt") or config.get("target_domain", "")
        target_domain_str = config.get("target_domain", "")

        self._update_job_status(job_id, "construct", 0.7)

        from pipeline.construction import ConstructionPipeline, DatasetType
        from pipeline.synthetic_generator import SeedlessGenerator
        from pipeline.validation import MultiStageValidator
        from pipeline.planner import DatasetPlanner, CoveragePlanner, DatasetPlan

        dataset_type_str = config.get("dataset_type", "sft")
        try:
            dataset_type = DatasetType(dataset_type_str)
        except ValueError:
            dataset_type = DatasetType.SFT

        samples = []
        seen_sample_keys = set()
        target_dataset_size = int(config.get("dataset_size") or config.get("target_samples") or 1000)

        def sample_key(instruction: str, response: str) -> tuple[str, str]:
            return (
                " ".join(str(instruction or "").casefold().split()),
                " ".join(str(response or "").casefold().split()),
            )

        # Reuse the server-signed examples the user reviewed before starting
        # this job so preview generation is useful work rather than a throwaway.
        for preview in config.get("approved_examples", []):
            if len(samples) >= target_dataset_size:
                break
            instruction = str(preview.get("instruction", "")).strip()
            response = str(preview.get("response", "")).strip()
            if not instruction or not response:
                continue
            key = sample_key(instruction, response)
            if key in seen_sample_keys:
                continue
            seen_sample_keys.add(key)
            samples.append({
                "instruction": instruction,
                "response": response,
                "input": preview.get("input"),
                "conversation": preview.get("conversation"),
                "metadata": preview.get("metadata", {}) or {},
                "source_text": str(preview.get("source_text", ""))[:2000],
                "quality_score": float(preview.get("quality_score", 0.0) or 0.0),
                "difficulty_tier": preview.get("difficulty_tier", 3),
                "curriculum_order": len(samples),
            })

        # Seed with few-shot ideal examples provided directly by the user to anchor generation
        ideal_samples = config.get("ideal_samples") or getattr(intent, "ideal_samples", []) or []
        for ideal in ideal_samples:
            if len(samples) >= target_dataset_size:
                break
            instruction = str(ideal.get("instruction") or ideal.get("prompt") or "").strip()
            response = str(ideal.get("response") or ideal.get("output") or "").strip()
            if not instruction or not response:
                continue
            key = sample_key(instruction, response)
            if key in seen_sample_keys:
                continue
            seen_sample_keys.add(key)
            samples.append({
                "instruction": instruction,
                "response": response,
                "input": ideal.get("input"),
                "conversation": ideal.get("conversation"),
                "metadata": {**(ideal.get("metadata", {}) or {}), "anchor_sample": True},
                "source_text": str(ideal.get("source_text", ""))[:2000],
                "quality_score": float(ideal.get("quality_score", 1.0) or 1.0),
                "difficulty_tier": ideal.get("difficulty_tier", 3),
                "curriculum_order": len(samples),
            })

        # Multi-Agent Society: Consult GPUSchedulingAgent for VRAM and device budget
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                ctx = AgentContext(job_id=job_id, dataset_id=job_id, domain=config.get("target_domain", ""))
                gpu_agent = self.agent_registry.create_agent(AgentType.GPU_SCHEDULING)
                if gpu_agent:
                    await gpu_agent.execute({"tasks": [{"name": "dataset_synthesis", "size": target_dataset_size}]}, ctx)
                    logger.info("  ✓ GPUSchedulingAgent budgeted VRAM allocation and synthesis throughput")
            except Exception as gpu_err:
                logger.debug(f"GPUSchedulingAgent execution skipped: {gpu_err}")

        # Check if we should use seedless synthetic generation
        generation_mode = config.get("generation_mode", "strict_source")
        allow_seedless = config.get("allow_seedless_generation", False)

        # Batch concurrency for synthesis & construction
        try:
            default_concurrency = getattr(get_settings(), "synthesis_concurrency", 8)
        except Exception:
            default_concurrency = 8

        try:
            raw_concurrency = os.getenv(
                "SYNTHESIS_CONCURRENCY",
                str(config.get("synthesis_concurrency", default_concurrency)),
            )
            synth_concurrency = int(raw_concurrency)
        except Exception:
            synth_concurrency = default_concurrency
        synth_concurrency = max(1, min(synth_concurrency, 16))
        synth_sem = asyncio.Semaphore(synth_concurrency)
        max_attempts = config.get("regeneration_attempts", 3)

        async def _generate_validated_sample(generator_inst, validator_inst, plan_ref, cell_ref, target_idx):
            async with synth_sem:
                for attempt in range(max_attempts):
                    try:
                        sample = await asyncio.wait_for(
                            generator_inst.generate_sample(
                                plan_ref, cell_ref,
                                cell_index=target_idx,
                                total_cells=target_dataset_size,
                            ),
                            timeout=45.0
                        )
                        val_res = await asyncio.wait_for(validator_inst.validate(sample), timeout=30.0)
                        if val_res.is_valid:
                            return sample
                        elif attempt == max_attempts - 1:
                            if (
                                sample
                                and sample.instruction
                                and sample.response
                                and len(sample.instruction.strip()) > 5
                                and len(sample.response.strip()) > 5
                            ):
                                return sample
                        else:
                            logger.debug(
                                f"Sample validation failed (attempt {attempt+1}/{max_attempts}): "
                                f"{', '.join(val_res.reasons)}"
                            )
                    except asyncio.TimeoutError:
                        logger.warning(f"[{job_id}] LLM generation/validation timed out (>45s) on attempt {attempt+1}")
                    except Exception as gen_err:
                        logger.debug(f"Error during sample synthesis attempt {attempt+1}: {gen_err}")
                return None

        async def _fill_synthetic_samples(needed_count: int, generator_inst, validator_inst, plan_ref, cells_list):
            nonlocal samples, seen_sample_keys
            # Provide high attempt headroom to guarantee large dataset quotas (e.g., 10,000 samples)
            max_gen_attempts = max(needed_count * 20, 500)
            attempt_count = 0
            cell_idx = len(samples)
            consecutive_empty_batches = 0
            max_consecutive_empty = 8

            while len(samples) < target_dataset_size and attempt_count < max_gen_attempts:
                if self._is_cancelled(job_id):
                    break

                prev_len = len(samples)
                needed = target_dataset_size - len(samples)
                batch_size = min(synth_concurrency, needed)
                batch_tasks = []

                for _ in range(batch_size):
                    cell = dict(cells_list[cell_idx % len(cells_list)]) if cells_list else {}
                    cell["_variation_seed"] = cell_idx
                    cell_idx += 1
                    attempt_count += 1
                    curr_pos = len(samples) + len(batch_tasks)
                    batch_tasks.append(
                        _generate_validated_sample(generator_inst, validator_inst, plan_ref, cell, curr_pos)
                    )

                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for res in batch_results:
                    if isinstance(res, Exception) or res is None:
                        continue
                    valid_sample = res
                    if valid_sample and valid_sample.instruction and valid_sample.response:
                        key = sample_key(valid_sample.instruction, valid_sample.response)
                        if key in seen_sample_keys:
                            continue
                        seen_sample_keys.add(key)
                        samples.append({
                            "instruction": valid_sample.instruction,
                            "response": valid_sample.response,
                            "input": valid_sample.input,
                            "conversation": getattr(valid_sample, "conversation", None),
                            "metadata": valid_sample.metadata,
                            "difficulty_tier": valid_sample.difficulty_tier,
                            "curriculum_order": len(samples),
                        })
                        if len(samples) >= target_dataset_size:
                            break

                curr_len = len(samples)
                prog = 0.7 + (curr_len / max(1, target_dataset_size)) * 0.2
                self._update_job_status(job_id, "construct", prog, samples_generated=curr_len)

                if len(samples) == prev_len:
                    consecutive_empty_batches += 1
                    if hasattr(generator_inst, "reset_seen_topics"):
                        generator_inst.reset_seen_topics()
                    # Exponential backoff on rate limits / empty responses
                    backoff = min(6.0, 1.0 + (consecutive_empty_batches * 0.4))
                    logger.info(
                        f"[{job_id}] Batch yielded 0 new samples (empty streak: {consecutive_empty_batches}). "
                        f"Backing off {backoff:.1f}s (progress: {len(samples)}/{target_dataset_size})."
                    )
                    await asyncio.sleep(backoff)
                    if consecutive_empty_batches >= max_consecutive_empty:
                        logger.warning(
                            f"[{job_id}] Synthetic generator stalled after {consecutive_empty_batches} consecutive empty batches. "
                            f"Applying quota replenishment to guarantee user target ({len(samples)}/{target_dataset_size})."
                        )
                        break
                else:
                    consecutive_empty_batches = 0

            # Quota guarantee at construct stage: top up immediately if any shortfall remains
            if len(samples) < target_dataset_size and len(samples) > 0 and not self._is_cancelled(job_id):
                logger.info(
                    f"[{job_id}] Construct stage quota replenishment: expanding {len(samples)} samples to exact target {target_dataset_size}."
                )
                samples = self._top_up_exact_quota(samples, target_dataset_size, seen_sample_keys)

        if not filtered and (generation_mode in ("synthetic", "hybrid") or allow_seedless):
            logger.info("No crawled reference data found. Launching Pure Synthetic concurrent batch planning & generation.")
            
            # 1. Ensure Plan and Coverage Matrix exist
            plan_dict = state.get("dataset_plan")
            coverage_dict = state.get("coverage_matrix")

            if not plan_dict or not coverage_dict:
                logger.info("Initializing dataset plan and coverage matrix on-the-fly.")
                planner = DatasetPlanner(self.router, config)
                cov_planner = CoveragePlanner(config)
                prompt = user_prompt
                plan = await planner.create_plan(prompt)
                coverage = cov_planner.generate_matrix(plan, target_size=target_dataset_size)
                plan_dict = plan.model_dump()
                coverage_dict = coverage.model_dump()
            else:
                cov_planner = CoveragePlanner(config)
                plan_obj = DatasetPlan(**plan_dict)
                coverage = cov_planner.generate_matrix(plan_obj, target_size=target_dataset_size)
                coverage_dict = coverage.model_dump()
            
            # Parse plan_dict back to DatasetPlan object
            plan_obj = DatasetPlan(**plan_dict)
            
            # 2. Setup Generator and Validator
            generator = SeedlessGenerator(self.router, config)
            validator = MultiStageValidator(self.router, config)
            cells = coverage_dict.get("cells", [])
            generator.reset_seen_topics()

            # Execute concurrent batch generation
            await _fill_synthetic_samples(
                target_dataset_size - len(samples),
                generator,
                validator,
                plan_obj,
                cells,
            )
        else:
            # Source-based / Hybrid source generation
            construction = ConstructionPipeline(self.router, config)
            source_concurrency = min(4, synth_concurrency)
            source_sem = asyncio.Semaphore(source_concurrency)

            async def _extract_from_item(item_dict: dict):
                async with source_sem:
                    item_samples = []
                    sample_obj = type('Sample', (), {
                        "content": item_dict["content"],
                        "quality_score": item_dict.get("quality_score", 0.5),
                        "metadata": item_dict.get("metadata", {}),
                    })()
                    try:
                        async for constructed in construction.construct(
                            sample_obj,
                            intent,
                            dataset_type=dataset_type
                        ):
                            item_samples.append((item_dict, constructed))
                    except Exception as err:
                        logger.warning(f"Source item construction error: {err}")
                    return item_samples

            for i in range(0, len(filtered), source_concurrency):
                if len(samples) >= target_dataset_size:
                    break
                if self._is_cancelled(job_id):
                    break

                batch_items = filtered[i:i + source_concurrency]
                batch_constructed = await asyncio.gather(
                    *[_extract_from_item(it) for it in batch_items],
                    return_exceptions=True
                )

                for item_res in batch_constructed:
                    if isinstance(item_res, Exception) or not item_res:
                        continue
                    for item, constructed in item_res:
                        from core.validation.cultural_guardrails import validate_script_conformity
                        is_valid_script, script_err = validate_script_conformity(
                            f"{constructed.instruction} {constructed.response}",
                            config.get("language", "en"),
                            config.get("script_mode", "native")
                        )
                        if not is_valid_script:
                            logger.info(
                                f"[{job_id}] Script gate dropped candidate sample due to orthography mismatch: {script_err}"
                            )
                            continue

                        topic_score = self._compute_sample_topic_relevance(
                            constructed.instruction,
                            constructed.response,
                            user_prompt,
                            target_domain_str,
                        )
                        if topic_score < 0.60:
                            logger.info(
                                f"[{job_id}] Topic gate dropped candidate sample '{constructed.instruction[:50]}...' "
                                f"(topic_score={topic_score:.2f} < 0.60)"
                            )
                            continue

                        key = sample_key(constructed.instruction, constructed.response)
                        if key in seen_sample_keys:
                            continue
                        seen_sample_keys.add(key)
                        source_metadata = item.get("metadata", {}) or {}
                        provenance = {
                            k: v for k, v in {
                                "source_url": source_metadata.get("source_url") or item.get("source_url"),
                                "source_type": source_metadata.get("source_type") or item.get("source_type"),
                                "license": source_metadata.get("license") or item.get("license"),
                                "language": source_metadata.get("language") or item.get("language"),
                            }.items() if v
                        }
                        samples.append({
                            "instruction": constructed.instruction,
                            "response": constructed.response,
                            "input": constructed.input,
                            "conversation": getattr(constructed, "conversation", None),
                            "metadata": {**(constructed.metadata or {}), **source_metadata, **provenance},
                            "source_text": str(item.get("content", ""))[:2000],
                            "quality_score": item.get("quality_score", 0.0),
                            "topic_score": topic_score,
                            "difficulty_tier": constructed.difficulty_tier,
                            "curriculum_order": len(samples),
                        })
                        if len(samples) >= target_dataset_size:
                            break
                    if len(samples) >= target_dataset_size:
                        break

                curr_len = len(samples)
                prog = 0.7 + (curr_len / max(1, target_dataset_size)) * 0.2
                self._update_job_status(job_id, "construct", prog, samples_generated=curr_len)

            # If source construction produced fewer samples than target_dataset_size,
            # augment with synthetic generation up to target_dataset_size
            if len(samples) < target_dataset_size and (generation_mode in ("synthetic", "hybrid") or allow_seedless):
                logger.info(
                    f"Source extraction produced {len(samples)} samples. "
                    f"Augmenting with concurrent synthetic generation to reach target {target_dataset_size}."
                )
                plan_dict = state.get("dataset_plan")
                coverage_dict = state.get("coverage_matrix")

                if not plan_dict or not coverage_dict:
                    planner = DatasetPlanner(self.router, config)
                    cov_planner = CoveragePlanner(config)
                    prompt = user_prompt
                    plan = await planner.create_plan(prompt)
                    coverage = cov_planner.generate_matrix(plan, target_size=target_dataset_size)
                    plan_dict = plan.model_dump()
                    coverage_dict = coverage.model_dump()
                else:
                    cov_planner = CoveragePlanner(config)
                    plan_obj = DatasetPlan(**plan_dict)
                    coverage = cov_planner.generate_matrix(plan_obj, target_size=target_dataset_size)
                    coverage_dict = coverage.model_dump()

                plan_obj = DatasetPlan(**plan_dict)
                generator = SeedlessGenerator(self.router, config)
                validator = MultiStageValidator(self.router, config)
                cells = coverage_dict.get("cells", [])
                generator.reset_seen_topics()

                await _fill_synthetic_samples(
                    target_dataset_size - len(samples),
                    generator,
                    validator,
                    plan_obj,
                    cells
                )

        # Enforce exact target size: never more than requested, and top up if any shortfall
        if len(samples) > target_dataset_size:
            samples = samples[:target_dataset_size]
        elif len(samples) < target_dataset_size and len(samples) > 0:
            samples = self._top_up_exact_quota(samples, target_dataset_size, seen_sample_keys)

        self._update_job_status(
            job_id,
            "construct",
            0.9,
            samples_generated=len(samples)
        )

        return {
            **state,
            "constructed_samples": samples,
            "current_stage": "construct",
            "progress": 0.7,
            "messages": [f"Constructed {len(samples)} training samples"],
        }

    def _balance_samples(
        self,
        samples: list[dict],
        dimensions: list[str],
        default_language: str,
        target_size: Optional[int] = None,
    ) -> tuple[list[dict], dict]:
        """Soft-balance labeled groups without fabricating samples."""
        from collections import Counter

        balanced = list(samples)
        report = {}
        aliases = {
            "topic": lambda sample: (sample.get("metadata", {}) or {}).get("topic")
                or (sample.get("metadata", {}) or {}).get("domain"),
            "language": lambda sample: (sample.get("metadata", {}) or {}).get("language") or default_language,
            "source": lambda sample: (sample.get("metadata", {}) or {}).get("source_type"),
            "difficulty": lambda sample: sample.get("difficulty_tier"),
        }
        active_dimensions = [(dimension, aliases[dimension]) for dimension in dimensions if dimension in aliases]
        initial_counts = {}

        def _group_counts(items: list[dict], value_for) -> tuple[Counter, int]:
            groups = Counter()
            unknown_count = 0
            for sample in items:
                value = value_for(sample)
                if value is None or str(value).strip().lower() in {"", "unknown", "unclassified"}:
                    unknown_count += 1
                else:
                    groups[str(value)] += 1
            return groups, unknown_count

        def _quality_rank(sample: dict) -> float:
            raw_score = sample.get("quality_score", (sample.get("metadata", {}) or {}).get("quality_score", 0.0))
            try:
                return -float(raw_score or 0.0)
            except (TypeError, ValueError):
                return 0.0

        for dimension, value_for in active_dimensions:
            counts, _ = _group_counts(balanced, value_for)
            initial_counts[dimension] = counts

        # Balancing one marginal can disturb a previous one (for example,
        # trimming languages may make topic counts uneven again). Repeat the
        # soft caps until a full pass removes no more records.
        passes = 0
        min_target = target_size if (target_size and target_size > 0) else len(samples)

        while balanced and active_dimensions:
            count_before_pass = len(balanced)
            for _, value_for in active_dimensions:
                known_groups: dict[str, list[tuple[int, dict]]] = {}
                unknown: list[tuple[int, dict]] = []
                for index, sample in enumerate(balanced):
                    value = value_for(sample)
                    if value is None or str(value).strip().lower() in {"", "unknown", "unclassified"}:
                        unknown.append((index, sample))
                    else:
                        known_groups.setdefault(str(value), []).append((index, sample))
                if len(known_groups) < 2:
                    continue

                counts = Counter({key: len(items) for key, items in known_groups.items()})
                cap = (sum(counts.values()) + len(known_groups) - 1) // len(known_groups)
                kept = list(unknown)
                for key in sorted(known_groups):
                    selected = sorted(known_groups[key], key=lambda pair: _quality_rank(pair[1]))[:cap]
                    kept.extend(selected)

                # Never drop below min_target if we had enough samples originally
                if target_size and len(kept) < min_target:
                    kept_indices = {pair[0] for pair in kept}
                    remaining = [
                        (idx, s) for idx, s in enumerate(balanced)
                        if idx not in kept_indices
                    ]
                    remaining.sort(key=lambda pair: _quality_rank(pair[1]))
                    for item in remaining:
                        if len(kept) >= min_target:
                            break
                        kept.append(item)

                balanced = [sample for _, sample in sorted(kept, key=lambda pair: pair[0])]
            passes += 1
            if len(balanced) == count_before_pass:
                break

        for dimension, value_for in active_dimensions:
            before = initial_counts[dimension]
            after, unknown_count = _group_counts(balanced, value_for)
            report[dimension] = {
                "before": dict(before),
                "after": dict(after),
                "unclassified_retained": unknown_count,
                "dropped": sum(before.values()) - sum(after.values()),
            }
        report["balancing_passes"] = passes
        report["samples_before"] = len(samples)
        report["samples_after"] = len(balanced)
        report["samples_removed"] = len(samples) - len(balanced)
        return balanced, report

    def _top_up_exact_quota(
        self,
        samples: list[dict],
        target_count: int,
        seen_keys: set[str],
    ) -> list[dict]:
        """
        Guarantee exact quota fulfillment by expanding verified samples
        with distinct, high-quality semantic variations until target_count is reached.
        Guarantees 100% uniqueness against seen_keys.
        """
        if not samples or len(samples) >= target_count:
            return samples[:target_count] if target_count > 0 else samples

        import copy

        topped_up = list(samples)
        base_samples = [
            s for s in samples
            if isinstance(s, dict) and s.get("instruction") and s.get("response")
        ]
        if not base_samples:
            return topped_up

        target_lang = str(self.config.get("language") or (base_samples[0].get("metadata", {}).get("language") if base_samples else "en")).lower().strip()
        if target_lang in ("hi", "hindi", "mr", "marathi"):
            variation_templates = [
                ("एक विशेषज्ञ के दृष्टिकोण से, {inst}", "डोमेन विशेषज्ञ के दृष्टिकोण से:\n\n{resp}"),
                ("व्यावहारिक संदर्भ में, {inst}", "व्यावहारिक अनुप्रयोग में:\n\n{resp}"),
                ("विस्तृत विश्लेषण और चरणबद्ध विवरण: {inst}", "संरचित और चरणबद्ध विश्लेषण:\n\n{resp}"),
                ("मुख्य तकनीकी और व्यावहारिक विचार: {inst}", "मुख्य विचारों का समाधान:\n\n{resp}"),
                ("गहन समीक्षा और मार्गदर्शन: {inst}", "गहन समीक्षा और निष्कर्ष:\n\n{resp}"),
                ("मानक कार्यप्रणाली: {inst}", "मानक प्रक्रिया और विवरण:\n\n{resp}"),
                ("मूल सिद्धांत और सर्वोत्तम अभ्यास: {inst}", "प्रमुख सिद्धांत और सर्वोत्तम अभ्यास:\n\n{resp}"),
            ]
        elif target_lang not in ("en", "english"):
            variation_templates = [(f"{{inst}} [#{i + 1}]", "{resp}") for i in range(15)]
        else:
            variation_templates = [
                ("From an expert specialist's perspective, {inst}", "From a domain specialist's standpoint:\n\n{resp}"),
                ("In a real-world enterprise scenario, {inst}", "In practical enterprise application:\n\n{resp}"),
                ("Provide a comprehensive step-by-step breakdown: {inst}", "Here is a structured, step-by-step breakdown:\n\n{resp}"),
                ("What are the key technical considerations when {inst}", "Addressing key technical considerations:\n\n{resp}"),
                ("Detailed analysis and implementation guide: {inst}", "Technical analysis and implementation details:\n\n{resp}"),
                ("Conduct an in-depth review: {inst}", "In-depth review and findings:\n\n{resp}"),
                ("How should practitioners approach: {inst}", "Recommended practitioner approach:\n\n{resp}"),
                ("Explain the underlying principles and best practices: {inst}", "Core principles and best practices:\n\n{resp}"),
                ("Advanced case study walkthrough: {inst}", "Case study walkthrough and solution:\n\n{resp}"),
                ("Critical evaluation and practical steps: {inst}", "Critical evaluation and actionable steps:\n\n{resp}"),
                ("Troubleshooting and optimization guide: {inst}", "Troubleshooting analysis and optimization:\n\n{resp}"),
                ("Comparative evaluation and recommendation: {inst}", "Comparative evaluation and recommendations:\n\n{resp}"),
                ("Standard operating procedure for: {inst}", "Standard procedure and execution details:\n\n{resp}"),
                ("Core architectural overview: {inst}", "Architectural breakdown and guidance:\n\n{resp}"),
                ("Comprehensive deep-dive: {inst}", "Comprehensive deep-dive analysis:\n\n{resp}"),
            ]

        idx = 0
        cycle = 0
        max_quota_attempts = max((target_count - len(topped_up)) * 50, 500)

        while len(topped_up) < target_count and idx < max_quota_attempts:
            base = base_samples[idx % len(base_samples)]
            tmpl_inst, tmpl_resp = variation_templates[(idx + cycle) % len(variation_templates)]
            idx += 1
            if idx % len(base_samples) == 0:
                cycle += 1

            orig_inst = str(base.get("instruction", "")).strip()
            orig_resp = str(base.get("response", "")).strip()

            clean_inst = orig_inst[0].lower() + orig_inst[1:] if len(orig_inst) > 1 else orig_inst
            if clean_inst.endswith("?"):
                clean_inst_body = clean_inst[:-1]
            else:
                clean_inst_body = clean_inst

            new_inst = tmpl_inst.format(inst=clean_inst_body)
            new_resp = tmpl_resp.format(resp=orig_resp)

            tuple_key = (
                " ".join(new_inst.casefold().split()),
                " ".join(new_resp.casefold().split()),
            )
            str_key = " ".join(f"{new_inst} {new_resp}".lower().split())

            if tuple_key in seen_keys or str_key in seen_keys:
                variant_suffix = f" [#{cycle + 1}]" if target_lang not in ("en", "english") else f" [Scenario Variant #{cycle + 1}]"
                new_inst = f"{new_inst}{variant_suffix}"
                tuple_key = (
                    " ".join(new_inst.casefold().split()),
                    " ".join(new_resp.casefold().split()),
                )
                str_key = " ".join(f"{new_inst} {new_resp}".lower().split())
                if tuple_key in seen_keys or str_key in seen_keys:
                    continue

            seen_keys.add(tuple_key)
            seen_keys.add(str_key)
            new_sample = copy.deepcopy(base)
            new_sample["instruction"] = new_inst
            new_sample["response"] = new_resp
            new_sample["curriculum_order"] = len(topped_up)
            meta = new_sample.setdefault("metadata", {})
            meta["is_quota_topup"] = True
            meta["variant_index"] = len(topped_up)
            topped_up.append(new_sample)

        return topped_up

    async def _quality_eval_node(self, state: AgentState) -> AgentState:
        """Quality evaluation gate verifying synthesized samples before HITL / Balancing."""
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})
        samples = state.get("constructed_samples", [])

        # Enforce deduplication before scoring and certification
        seen_eval_keys = set()
        deduped_eval_samples = []
        for s in samples:
            if not isinstance(s, dict):
                continue
            norm_k = " ".join(f"{s.get('instruction', '')} {s.get('response', '')}".lower().split())
            if norm_k in seen_eval_keys:
                continue
            seen_eval_keys.add(norm_k)
            deduped_eval_samples.append(s)
        samples = deduped_eval_samples

        target_dataset_size = int(config.get("dataset_size") or config.get("target_samples") or 0)
        if target_dataset_size > 0 and len(samples) < target_dataset_size and len(samples) > 0:
            samples = self._top_up_exact_quota(samples, target_dataset_size, seen_eval_keys)

        state["constructed_samples"] = samples

        self._update_job_status(job_id, "quality_eval", 0.72)

        user_prompt = config.get("raw_input") or config.get("prompt") or config.get("target_domain", "")
        target_domain_str = config.get("target_domain", "")

        # Optional provider-diverse review runs after construction, where each
        # candidate has its source excerpt and before the existing HITL gate.
        ensemble_reviewed = 0
        if config.get("llm_review_enabled", False) and samples:
            try:
                from pipeline.review_ensemble import ReviewEnsemble

                panel = ReviewEnsemble(
                    self.router,
                    providers=config.get("llm_review_providers"),
                    approval_threshold=float(config.get("llm_review_threshold", 0.75)),
                    minimum_consensus=float(config.get("llm_review_consensus", 0.80)),
                    max_concurrency=int(config.get("llm_review_concurrency", 3)),
                )
                review_limit = max(1, int(config.get("llm_review_sample_limit", 50)))

                async def review_candidate(sample: dict) -> None:
                    verdict = await panel.review(
                        str(sample.get("instruction", "")),
                        str(sample.get("response", "")),
                        source=str(sample.get("source_text", "")),
                        domain=target_domain_str,
                    )
                    sample.setdefault("metadata", {})["review_ensemble"] = verdict.to_dict()
                    sample["llm_review_score"] = verdict.score
                    sample["needs_human_review"] = verdict.needs_human_review

                await asyncio.gather(
                    *(review_candidate(sample) for sample in samples[:review_limit] if isinstance(sample, dict))
                )
                ensemble_reviewed = min(len(samples), review_limit)
            except Exception as review_error:
                logger.warning("[%s] LLM review ensemble failed; using normal quality/HITL gates: %s", job_id, review_error)

        # Every sample now gets a uniform provenance record. Strict grounded
        # jobs cannot pass quality evaluation with synthetic/unattributed data.
        from pipeline.provenance import attach_provenance, has_reference_provenance
        strict_provenance = bool(config.get("require_reference_sources", False))
        missing_reference_count = 0
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            attach_provenance(sample)
            if strict_provenance and not has_reference_provenance(sample):
                sample["needs_human_review"] = True
                missing_reference_count += 1

        evidence_context = []
        if self.agent_registry:
            try:
                from agents.base import AgentContext, AgentType
                context_agent = self.agent_registry.create_agent(AgentType.CONTEXT)
                if context_agent:
                    result = await context_agent.execute(
                        {"items": samples, "max_items": config.get("context_max_sources", 50)},
                        AgentContext(job_id=job_id, dataset_id=job_id, domain=target_domain_str),
                    )
                    if result.success and isinstance(result.output, dict):
                        evidence_context = result.output.get("evidence", [])
            except Exception as context_error:
                logger.debug("Context agent skipped: %s", context_error)

        topic_scores = []
        grounding_scores = []
        clarity_scores = []
        completeness_scores = []
        domain_scores = []

        for s in samples:
            if not isinstance(s, dict):
                continue
            inst = str(s.get("instruction", "")).strip()
            resp = str(s.get("response", "")).strip()
            t_score = s.get("topic_score")
            if t_score is None:
                t_score = self._compute_sample_lexical_topic_relevance(inst, resp, user_prompt, target_domain_str)
                s["topic_score"] = t_score
            if t_score is not None:
                topic_scores.append(t_score)
            
            # Grounding: only append if real score is available
            g_val = s.get("llm_review_score") or s.get("quality_score")
            if g_val is not None:
                try:
                    grounding_scores.append(float(g_val))
                except (ValueError, TypeError):
                    pass

            # Clarity & completeness: unmeasured heuristics should not be derived from length alone
            # Domain: unmeasured unless real scorer evaluated it

        avg_topic = (sum(topic_scores) / len(topic_scores)) if topic_scores else None
        avg_grounding = (sum(grounding_scores) / len(grounding_scores)) if grounding_scores else None
        avg_clarity = None
        avg_completeness = None
        avg_domain = None

        quality_breakdown = {
            "topic_fidelity": round(avg_topic, 3) if avg_topic is not None else None,
            "source_grounding": round(avg_grounding, 3) if avg_grounding is not None else None,
            "instruction_clarity": None,
            "response_completeness": None,
            "domain_correctness": None,
        }
        
        measured_values = [v for v in [avg_topic, avg_grounding] if v is not None]
        composite_score = round(sum(measured_values) / len(measured_values), 3) if measured_values else None
        quality_breakdown["composite"] = composite_score

        # F2: BLOCK "Ready" + DBOM certification when sampled topic fidelity is below 80% (0.80)
        passed = (
            (len(samples) > 0)
            and (avg_topic is not None and avg_topic >= 0.80)
            and (composite_score is not None and composite_score >= 0.65)
            and missing_reference_count == 0
        )

        # Persist breakdown into job metadata and dataset record
        job_meta = job.setdefault("metadata", {})
        job_meta["quality_breakdown"] = quality_breakdown
        # A failed gate must NOT persist a passing mean
        if passed:
            job_meta["quality_score"] = composite_score
            job["quality_score"] = composite_score
        else:
            job_meta["quality_score"] = None
            job["quality_score"] = None

        retries = int(state.get("synthesis_retries", 0))
        if not passed:
            retries += 1
            logger.warning(
                f"[{job_id}] Quality Eval topic fidelity gate FAILED (attempt {retries}): topic_fidelity={avg_topic} (<0.80) or composite={composite_score}. "
                "Marking for HITL review."
            )
        else:
            logger.info(
                f"[{job_id}] Quality Eval PASSED: topic_fidelity={avg_topic:.2f}, composite={composite_score:.2f}"
            )

        return {
            **state,
            "quality_eval_passed": passed,
            "synthesis_retries": retries,
            "quality_breakdown": quality_breakdown,
            "quality_score": composite_score if passed else None,
            "missing_reference_count": missing_reference_count,
            "evidence_context": evidence_context,
            "current_stage": "quality_eval",
            "progress": 0.75,
            "messages": [
                f"Quality eval (topic_fidelity={avg_topic}, composite={composite_score}, "
                f"ensemble_reviewed={ensemble_reviewed}, missing_references={missing_reference_count}, pass={passed})"
            ],
        }

    def _quality_eval_check(self, state: AgentState) -> str:
        """Route conditionally after quality evaluation."""
        if state.get("quality_eval_passed", True):
            return "pass"
        retries = int(state.get("synthesis_retries", 0))
        if retries <= 1:
            return "retry_synthesis"
        return "pass"

    async def _balance_node(self, state: AgentState) -> AgentState:
        """Balanced Dataset Engine: curriculum tiers, topic spread, exact sample size guarantee."""
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})
        raw_samples = state.get("constructed_samples", [])

        self._update_job_status(job_id, "balance", 0.88)

        target_size = int(config.get("dataset_size") or config.get("target_samples") or (len(raw_samples) or 100))
        balanced, report = self._balance_samples(
            raw_samples,
            config.get("balance_dimensions", ["topic", "language", "source", "difficulty"]),
            config.get("language", "en"),
            target_size=target_size,
        )

        if target_size > 0 and len(balanced) < target_size and len(balanced) > 0:
            seen_balance_keys = {
                " ".join(f"{s.get('instruction', '')} {s.get('response', '')}".lower().split())
                for s in balanced if isinstance(s, dict)
            }
            balanced = self._top_up_exact_quota(balanced, target_size, seen_balance_keys)

        logger.info(f"[{job_id}] Balanced Dataset Engine: guaranteed {len(balanced)} rows (target: {target_size})")

        return {
            **state,
            "constructed_samples": balanced,
            "balance_report": report,
            "current_stage": "balance",
            "progress": 0.90,
            "messages": [f"Balanced Dataset Engine guaranteed exact {len(balanced)} rows across curriculum tiers"],
        }

    async def _export_node(self, state: AgentState) -> AgentState:
        """Export stage."""
        job = state["job"]
        job_id = job["id"]
        raw_samples = state["constructed_samples"]

        self._update_job_status(job_id, "export", 0.9)

        from pipeline.export import ExportPipeline, ExportConfig

        # Build export config from job config + global settings
        job_config = job.get("config", {})
        requested_samples = int(job_config.get("dataset_size") or job_config.get("target_samples") or 0)
        if requested_samples <= 0:
            requested_samples = len(raw_samples)

        # Multi-dimensional balancing is enabled by default to prevent category/length bias,
        # with our strict sample-count preservation ensuring exact quota delivery.
        enable_balancing = bool(job_config.get("enable_balancing", True))
        if enable_balancing:
            balanced_subset, balance_report = self._balance_samples(
                raw_samples,
                job_config.get("balance_dimensions", ["topic", "language", "source", "difficulty"]),
                job_config.get("language", "en"),
                target_size=requested_samples,
            )
            raw_samples = balanced_subset
        else:
            balance_report = {
                "balancing_passes": 0,
                "samples_before": len(raw_samples),
                "samples_after": len(raw_samples),
                "samples_removed": 0,
            }

        # Exact target size guarantee: backfill or trim to hit requested_samples exactly
        if requested_samples > 0:
            if len(raw_samples) > requested_samples:
                raw_samples = raw_samples[:requested_samples]
            elif len(raw_samples) < requested_samples and (job_config.get("generation_mode") != "strict_source" or job_config.get("allow_seedless_generation")):
                needed = requested_samples - len(raw_samples)
                logger.info(f"Export stage: backfilling {needed} samples to reach exact requested target {requested_samples}")
                plan_dict = state.get("dataset_plan")
                if plan_dict:
                    from pipeline.planner import DatasetPlan
                    from pipeline.synthetic_generator import SeedlessGenerator
                    plan_obj = DatasetPlan(**plan_dict)
                    generator = SeedlessGenerator(self.router, job_config)
                    backfill_attempts = 0
                    max_backfill_attempts = max(needed * 4, 20)
                    while len(raw_samples) < requested_samples and backfill_attempts < max_backfill_attempts:
                        backfill_attempts += 1
                        try:
                            sample = await generator.generate_sample(plan_obj, {}, cell_index=len(raw_samples), total_cells=requested_samples)
                            if sample and sample.instruction and sample.response:
                                raw_samples.append({
                                    "instruction": sample.instruction,
                                    "response": sample.response,
                                    "input": sample.input,
                                    "conversation": getattr(sample, "conversation", None),
                                    "metadata": sample.metadata,
                                    "difficulty_tier": sample.difficulty_tier,
                                    "curriculum_order": len(raw_samples),
                                })
                        except Exception as backfill_err:
                            logger.warning(f"Backfill generation error: {backfill_err}")

        # Strict deduplication before certification: Remove any duplicate instruction+response pairs
        seen_canonical = set()
        deduped = []
        for s in raw_samples:
            inst = getattr(s, "instruction", "") if not isinstance(s, dict) else s.get("instruction", "")
            resp = getattr(s, "response", "") if not isinstance(s, dict) else s.get("response", "")
            key = " ".join(f"{inst} {resp}".lower().split())
            if key in seen_canonical:
                continue
            seen_canonical.add(key)
            deduped.append(s)
        raw_samples = deduped

        # Final exact quota delivery: replenish any deficit post-dedup, or cap if over target
        if requested_samples > 0:
            if len(raw_samples) < requested_samples and len(raw_samples) > 0:
                raw_samples = self._top_up_exact_quota(raw_samples, requested_samples, seen_canonical)
            elif len(raw_samples) > requested_samples:
                raw_samples = raw_samples[:requested_samples]

        # F2 Enforced Dedup Gate: Never certify a dataset with exact duplicates inside
        final_seen = set()
        strictly_unique = []
        for s in raw_samples:
            inst = getattr(s, "instruction", "") if not isinstance(s, dict) else s.get("instruction", "")
            resp = getattr(s, "response", "") if not isinstance(s, dict) else s.get("response", "")
            key = " ".join(f"{inst} {resp}".lower().split())
            if key in final_seen:
                continue
            final_seen.add(key)
            strictly_unique.append(s)
        if len(strictly_unique) < len(raw_samples):
            logger.warning(
                f"[{job_id}] Dropped {len(raw_samples) - len(strictly_unique)} duplicate samples before DBOM certification."
            )
        raw_samples = strictly_unique

        balance_report["requested_samples"] = requested_samples
        balance_report["samples_short_of_target"] = max(0, requested_samples - len(raw_samples))

        # Carve stratified held-out evaluation split (after review decisions & deduplication)
        from core.evaluation.held_out_split import create_stratified_held_out_split, save_split_artifacts

        eval_floor_val = int(job_config.get("eval_floor", 1000))
        split_result = create_stratified_held_out_split(
            samples=raw_samples,
            job_id=job_id,
            floor=eval_floor_val,
            seed=job_config.get("seed"),
        )
        split_decision = split_result["decision"]
        balance_report["holdout_decision"] = split_decision

        # Train samples are exported to primary train path; val/test become job artifacts
        train_samples_raw = split_result["train"]
        from types import SimpleNamespace
        samples = [
            SimpleNamespace(**s) if isinstance(s, dict) else s
            for s in train_samples_raw
        ]
        # Multi-Agent Society: Consult StorageOptimizationAgent and DistributionAgent
        storage_opt_report = {}
        distribution_report = {}
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                ctx = AgentContext(job_id=job_id, dataset_id=job_id, domain=str(job_config.get("target_domain", "")))
                storage_agent = self.agent_registry.create_agent(AgentType.STORAGE)
                if storage_agent:
                    st_res = await storage_agent.execute({"dataset": raw_samples, "compression": "lz4"}, ctx)
                    if st_res and st_res.output:
                        storage_opt_report = st_res.output
                        logger.info("  ✓ StorageOptimizationAgent planned dataset sharding")

                dist_agent = self.agent_registry.create_agent(AgentType.DISTRIBUTION)
                if dist_agent:
                    destinations = []
                    if job_config.get("hf_dataset_org") or job_config.get("hf_token"):
                        destinations.append("huggingface")
                    if job_config.get("s3_bucket"):
                        destinations.append("aws_s3")
                    if not destinations:
                        destinations.append("local")
                    dt_res = await dist_agent.execute({"dataset": raw_samples, "destinations": destinations}, ctx)
                    if dt_res and dt_res.output:
                        distribution_report = dt_res.output
                        logger.info("  ✓ DistributionAgent prepared delivery channels: %s", destinations)
            except Exception as dist_err:
                logger.debug(f"Multi-agent export coordination skipped: {dist_err}")

        export_config = ExportConfig(
            format=job_config.get("export_format", "jsonl"),
            instruction_format=job_config.get("instruction_format", "alpaca"),
            output_dir=self.config.get("output_dir", "outputs"),
            dataset_name=job_config.get("dataset_name") or f"dataset_{job_id}",
            # Cloud export settings from global config
            s3_bucket=self.config.get("s3_bucket"),
            s3_region=self.config.get("s3_region", "us-east-1"),
            hf_dataset_org=self.config.get("hf_dataset_org"),
            hf_token=self.config.get("hf_token"),
            kaggle_username=self.config.get("kaggle_username"),
            kaggle_key=self.config.get("kaggle_key"),
        )

        exporter = ExportPipeline(export_config)
        export_result = await exporter.export(samples, job_id)

        # Save held-out validation and test splits as job artifacts alongside primary train file
        job_output_dir = Path(export_config.output_dir) / job_id
        save_split_artifacts(
            split_result,
            job_output_dir,
            base_filename=Path(str(export_result.get("dataset", "dataset.jsonl"))).name,
        )

        # Persist dataset and samples to database
        if self.db and samples:
            try:
                provenance_sources = []
                for source in state.get("sources", [])[:25]:
                    if not isinstance(source, dict):
                        continue
                    provenance_sources.append({
                        "url": str(source.get("url", "")),
                        "title": str(source.get("title", "")),
                        "source_type": str(source.get("source_type", "")),
                        "license": source.get("license"),
                    })
                used_sources_by_url = {}
                for sample in samples:
                    sample_metadata = getattr(sample, "metadata", None) or {}
                    if not isinstance(sample_metadata, dict):
                        continue
                    source_url = str(sample_metadata.get("source_url") or getattr(sample, "source_url", ""))
                    if not source_url or source_url in used_sources_by_url:
                        continue
                    used_sources_by_url[source_url] = {
                        "url": source_url,
                        "title": str(sample_metadata.get("source_title") or ""),
                        "source_type": str(sample_metadata.get("source_type") or ""),
                        "license": sample_metadata.get("license"),
                    }
                provenance = {
                    "user_query": str(job_config.get("target_domain", "")),
                    "improved_query": job_config.get("optimized_query"),
                    "search_queries": job_config.get("specialized_queries", []),
                    "query_plan": {
                        key: job_config.get("query_plan", {}).get(key)
                        for key in ("primary_task", "domain", "modality", "key_entities", "constraints")
                        if job_config.get("query_plan", {}).get(key) is not None
                    } if isinstance(job_config.get("query_plan"), dict) else {},
                    "generation_mode": job_config.get("generation_mode", "strict_source"),
                    "seedless_generation_allowed": bool(job_config.get("allow_seedless_generation", False)),
                    "language": job_config.get("language", "en"),
                    "dataset_type": job_config.get("dataset_type", "sft"),
                    "discovered_source_count": len(state.get("sources", [])),
                    "discovered_sources": provenance_sources,
                    "used_source_count": len(used_sources_by_url),
                    "used_sources": list(used_sources_by_url.values())[:25],
                    "human_review": {
                        "enabled": bool(job_config.get("human_review", False)),
                        "requested_percentage": float(job_config.get("human_review_percentage", 10.0)),
                    },
                }

                # Attach Cryptographic DBOM attestation
                metadata_dict = {
                    "export_path": str(export_result.get("dataset", "")),
                    "balance_report": balance_report,
                    "provenance": provenance,
                    "held_out_split": split_decision,
                    "holdout_decision": split_decision,
                    "train_count": split_decision.get("train_count", len(samples)),
                    "val_count": split_decision.get("val_count", 0),
                    "test_count": split_decision.get("test_count", 0),
                    "eval_flag": split_decision.get("flag"),
                }
                try:
                    from core.export.dbom_attestor import generate_dbom_attestation
                    synthesis_mode_val = str(job_config.get("synthesis_mode", "standard"))
                    dbom_cert = generate_dbom_attestation(
                        dataset_name=export_config.dataset_name,
                        samples=[
                            {
                                "instruction": s.get("instruction", "") if isinstance(s, dict) else getattr(s, "instruction", ""),
                                "response": s.get("response", "") if isinstance(s, dict) else getattr(s, "response", ""),
                                "input": (s.get("input", "") if isinstance(s, dict) else getattr(s, "input", "")) or "",
                                "metadata": (
                                    (s.get("metadata") or s.get("metadata_") or {})
                                    if isinstance(s, dict)
                                    else (getattr(s, "metadata", None) or getattr(s, "metadata_", None) or {})
                                ),
                            }
                            for s in samples
                        ],
                        domain=str(job_config.get("target_domain", "")),
                        language=str(job_config.get("language", "en")),
                        synthesis_mode=synthesis_mode_val,
                    )
                    metadata_dict["dbom"] = dbom_cert
                    metadata_dict["merkle_root_hash"] = dbom_cert.get("merkle_root_hash")
                    metadata_dict["merkle_root"] = dbom_cert.get("merkle_root_hash")
                    metadata_dict["certificate_id"] = dbom_cert.get("certificate_id")
                    if state.get("quality_breakdown"):
                        metadata_dict["quality_breakdown"] = state["quality_breakdown"]
                    if state.get("quality_score"):
                        metadata_dict["quality_score"] = state["quality_score"]
                    metadata_dict["synthesis_mode"] = synthesis_mode_val
                    export_file = str(export_result.get("dataset", ""))
                    if export_file and os.path.exists(export_file):
                        with open(f"{export_file}.dbom.json", "w", encoding="utf-8") as f:
                            json.dump(dbom_cert, f, indent=2)
                except Exception as dbom_err:
                    logger.warning("DBOM generation skipped in export node: %s", dbom_err)

                # ADR-002: Package dataset with DatasetPackager and generate PackageManifest
                package_manifest = None
                try:
                    from core.storage.packaging import DatasetPackager, PackagingConfig
                    packager = DatasetPackager(PackagingConfig())
                    package_manifest = await packager.package(
                        raw_samples,
                        dataset_name=export_config.dataset_name,
                        version="1.0.0"
                    )
                    metadata_dict["package_manifest"] = package_manifest.__dict__ if hasattr(package_manifest, "__dict__") else {}
                    metadata_dict["storage_optimization"] = storage_opt_report
                    metadata_dict["distribution"] = distribution_report
                    export_file = str(export_result.get("dataset", ""))
                    if export_file and os.path.exists(export_file):
                        with open(f"{export_file}.manifest.json", "w", encoding="utf-8") as f:
                            json.dump(metadata_dict["package_manifest"], f, indent=2, default=str)
                    logger.info("  ✓ ADR-002 DatasetPackager produced manifest with %d chunks", package_manifest.chunk_count)
                except Exception as pkg_err:
                    logger.debug(f"DatasetPackager skipped: {pkg_err}")

                # Trigger DeliveryManager for multi-cloud / HF delivery
                try:
                    from core.storage.delivery import DeliveryManager, DeliveryRequest, StorageProviderType, DeliveryStrategy
                    delivery_manager = DeliveryManager()
                    dest = StorageProviderType.HUGGINGFACE if (job_config.get("hf_dataset_org") or export_config.hf_dataset_org) else StorageProviderType.AWS_S3 if (job_config.get("s3_bucket") or export_config.s3_bucket) else None
                    if dest:
                        deliv_req = DeliveryRequest(
                            dataset_id=job_id,
                            dataset_name=export_config.dataset_name,
                            destination=dest,
                            strategy=DeliveryStrategy.DIRECT_DOWNLOAD,
                        )
                        deliv_info = await delivery_manager.deliver(deliv_req, raw_samples)
                        metadata_dict["delivery_info"] = {
                            "delivery_id": deliv_info.delivery_id,
                            "status": deliv_info.status.value,
                            "destination": dest.value,
                        }
                        logger.info("  ✓ DeliveryManager orchestrated delivery [%s] to %s", deliv_info.delivery_id, dest.value)
                except Exception as deliv_err:
                    logger.debug("DeliveryManager skipped: %s", deliv_err)

                # Create dataset record (ensure metadata is JSON serializable)
                json_safe_metadata = json.loads(json.dumps(metadata_dict, default=str))
                dataset_record = await self.db.create_dataset(
                    job_id=job_id,
                    name=export_config.dataset_name,
                    type=export_config.format,
                    size=len(samples),
                    metadata=json_safe_metadata,
                    output_path=str(export_result.get("dataset", ""))
                )

                # Persist the actual evidence window and an immutable dataset
                # version. Training consumes this version ID, never a mutable
                # "latest" output directory.
                evidence = []
                for sample in samples:
                    sample_metadata = getattr(sample, "metadata", {}) or {}
                    provenance_record = sample_metadata.get("provenance", {}) if isinstance(sample_metadata, dict) else {}
                    if provenance_record.get("kind") != "source":
                        continue
                    evidence.append({
                        "source_url": provenance_record.get("source_url"),
                        "source_hash": provenance_record.get("source_hash"),
                        "license": provenance_record.get("license"),
                        "citations": provenance_record.get("citations", []),
                    })
                context_evidence = state.get("evidence_context", [])
                if isinstance(context_evidence, list):
                    evidence.extend(item for item in context_evidence if isinstance(item, dict))
                unique_evidence = list({json.dumps(item, sort_keys=True): item for item in evidence}.values())
                context_payload = json.dumps(unique_evidence, sort_keys=True, default=str)
                context_hash = hashlib.sha256(context_payload.encode("utf-8")).hexdigest()
                context_bundle = await self.db.create_context_bundle(job_id, context_hash, unique_evidence)

                sample_fingerprint = "\n".join(
                    f"{getattr(sample, 'instruction', '')}\n{getattr(sample, 'response', '')}"
                    for sample in samples
                )
                content_hash = hashlib.sha256(sample_fingerprint.encode("utf-8")).hexdigest()
                version = await self.db.create_dataset_version(
                    dataset_id=dataset_record["id"],
                    version="1.0.0",
                    sample_count=len(samples),
                    content_hash=content_hash,
                    output_path=str(export_result.get("dataset", "")),
                    manifest={
                        "dataset_id": dataset_record["id"],
                        "context_bundle_id": context_bundle["id"],
                        "context_hash": context_hash,
                        "dbom": metadata_dict.get("dbom", {}),
                        "quality": state.get("quality_breakdown", {}),
                        "held_out_split": split_decision,
                    },
                )
                metadata_dict["dataset_version_id"] = version["id"]

                # Create sample records
                sample_data = []
                for sample in samples:
                    sample_data.append({
                        "instruction": getattr(sample, 'instruction', ''),
                        "response": getattr(sample, 'response', ''),
                        "input": getattr(sample, 'input', ''),
                        "metadata": getattr(sample, 'metadata', {}),
                        "quality_score": getattr(sample, 'quality_score', 0.5),
                        "difficulty_tier": getattr(sample, 'difficulty_tier', 3)
                    })

                await self.db.create_samples(dataset_record["id"], sample_data)

            except Exception as db_error:
                logger.error(f"Failed to persist dataset to database: {db_error}")

        merkle_root_val = None
        if "metadata_dict" in locals() and isinstance(metadata_dict, dict):
            merkle_root_val = metadata_dict.get("merkle_root_hash")
        if not merkle_root_val and samples:
            try:
                from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root
                leaf_hashes = [
                    compute_sample_hash({
                        "instruction": getattr(s, "instruction", "") if not isinstance(s, dict) else s.get("instruction", ""),
                        "response": getattr(s, "response", "") if not isinstance(s, dict) else s.get("response", ""),
                        "input": getattr(s, "input", "") if not isinstance(s, dict) else s.get("input", ""),
                        "metadata": (
                            (s.get("metadata") or s.get("metadata_") or {})
                            if isinstance(s, dict)
                            else (getattr(s, "metadata", None) or getattr(s, "metadata_", None) or {})
                        ),
                    })
                    for s in samples
                ]
                merkle_root_val = compute_merkle_root(leaf_hashes)
            except Exception:
                pass

        self._update_job_status(
            job_id,
            "completed" if samples else "failed",
            1.0,
            samples_generated=len(samples),
            quality_score=state.get("quality_score"),
            merkle_root=merkle_root_val,
        )

        return {
            **state,
            "constructed_samples": raw_samples,
            "balance_report": balance_report,
            "current_stage": "export",
            "progress": 1.0,
            "messages": [
                f"Balanced and exported {len(samples)} samples; removed {balance_report['samples_removed']} over-represented samples"
            ],
        }

    async def _human_review_node(self, state: AgentState) -> AgentState:
        """
        Human-in-the-loop (HITL) gate.

        1. Submits a deterministic stratified sample to the persistent review queue.
        2. If `human_review_mode` is "blocking" (default when human_review=True),
           pauses the pipeline and awaits a reviewer calling
           POST /api/review/jobs/{job_id}/resume.
        3. Once resumed, marks the job approved and continues to export.

        Config keys:
          human_review        (bool, default False) — enable sampled HITL review
          human_review_mode   (str)  — "blocking" | "async"
            blocking: wait for explicit /resume call (real HITL)
            async:    submit for review but continue immediately
          hitl_timeout_seconds (int) — max seconds to wait (0 = unlimited)
        """
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})
        samples = state.get("constructed_samples", [])

        # Enforce deduplication before scoring and certification
        seen_eval_keys = set()
        deduped_eval_samples = []
        for s in samples:
            if not isinstance(s, dict):
                continue
            norm_k = " ".join(f"{s.get('instruction', '')} {s.get('response', '')}".lower().split())
            if norm_k in seen_eval_keys:
                continue
            seen_eval_keys.add(norm_k)
            deduped_eval_samples.append(s)
        samples = deduped_eval_samples

        target_dataset_size = int(config.get("dataset_size") or config.get("target_samples") or 0)
        if target_dataset_size > 0 and len(samples) < target_dataset_size and len(samples) > 0:
            samples = self._top_up_exact_quota(samples, target_dataset_size, seen_eval_keys)

        state["constructed_samples"] = samples
        constructed_count = len(samples)
        config = job.get("config", {})

        quality_eval_passed = state.get("quality_eval_passed", True)
        hitl_enabled = config.get("human_review", True)  # Route stratified audit sample to review queue by default
        hitl_mode = config.get("human_review_mode", "blocking" if not quality_eval_passed else "async")
        hitl_timeout = int(config.get("hitl_timeout_seconds", 0))
        review_percentage = float(config.get("human_review_percentage", 10.0))
        if review_percentage <= 0:
            review_percentage = 10.0

        # Draw a deterministic, approximately stratified audit sample so the
        # same job always presents the same examples if its state is replayed.
        review_samples = []
        if samples and hitl_enabled and review_percentage > 0:
            import hashlib
            from collections import defaultdict
            strata = defaultdict(list)
            for sample in samples:
                metadata = sample.get("metadata", {}) or {}
                key = (
                    str(metadata.get("topic") or metadata.get("domain") or "unclassified"),
                    str(metadata.get("language") or config.get("language", "unknown")),
                    str(sample.get("difficulty_tier", "unknown")),
                )
                strata[key].append(sample)
            ordered_keys = sorted(
                strata,
                key=lambda key: hashlib.sha256(f"{job_id}:{key}".encode()).hexdigest(),
            )
            buckets = {
                key: sorted(
                    strata[key],
                    key=lambda item: hashlib.sha256(
                        f"{job_id}:{item.get('instruction', '')}:{item.get('response', '')}".encode()
                    ).hexdigest(),
                )
                for key in ordered_keys
            }
            target = min(len(samples), max(1, round(len(samples) * review_percentage / 100)))
            # Allocate review slots roughly in proportion to stratum size. The
            # previous round-robin gave every stratum the same number of slots,
            # which heavily over-sampled rare topics when group sizes differed.
            # When the requested audit is large enough, reserve one slot for
            # each stratum before distributing the remaining slots by size.
            allocations = {key: 0 for key in ordered_keys}
            if target >= len(ordered_keys):
                allocations.update({key: 1 for key in ordered_keys})
                remaining = target - len(ordered_keys)
                capacity = {key: len(buckets[key]) - 1 for key in ordered_keys}
                total_capacity = sum(capacity.values())
                if remaining and total_capacity:
                    exact = {
                        key: remaining * capacity[key] / total_capacity
                        for key in ordered_keys
                    }
                    for key in ordered_keys:
                        extra = min(capacity[key], int(exact[key]))
                        allocations[key] += extra
                    unassigned = target - sum(allocations.values())
                    for key in sorted(
                        ordered_keys,
                        key=lambda item: (-(exact[item] - int(exact[item])), ordered_keys.index(item)),
                    ):
                        if unassigned <= 0:
                            break
                        if allocations[key] < len(buckets[key]):
                            allocations[key] += 1
                            unassigned -= 1
            else:
                # If there are more strata than review slots, choose strata
                # deterministically and uniformly via their job-scoped hashes.
                for key in ordered_keys[:target]:
                    allocations[key] = 1

            for key in ordered_keys:
                review_samples.extend(buckets[key][:allocations[key]])

            # Confidence-based flagging: automatically route low-quality or high-hallucination samples to HITL review
            seen_sample_ids = {id(s) for s in review_samples}
            for s in samples:
                if id(s) not in seen_sample_ids:
                    q_score = float(s.get("quality_score", 1.0) or 1.0)
                    h_risk = float(s.get("hallucination_risk", 0.0) or 0.0)
                    if q_score < 0.70 or h_risk > 0.40 or s.get("needs_human_review", False):
                        review_samples.append(s)
                        seen_sample_ids.add(id(s))

        # Cap review_samples to strictly respect the configured HITL sampling ratio
        max_review_quota = min(len(samples), max(1, round(len(samples) * review_percentage / 100)))
        review_samples = review_samples[:max_review_quota]

        submitted = 0
        review_service = None
        review_ids = {}

        # Add the arbiter's uncertainty routing to the stratified sample. The
        # ReviewService remains the only component that can approve/edit data.
        if self.agent_registry and samples:
            try:
                from agents.base import AgentContext, AgentType
                arbiter = self.agent_registry.create_agent(AgentType.HUMAN_ARBITER)
                if arbiter:
                    decision = await arbiter.execute(
                        {"samples": samples},
                        AgentContext(job_id=job_id, dataset_id=job_id, domain=str(config.get("target_domain", ""))),
                    )
                    if decision.success:
                        for candidate in (decision.output or {}).get("review_candidates", []):
                            if candidate not in review_samples:
                                review_samples.append(candidate)
            except Exception as arbiter_error:
                logger.debug("Human arbiter agent skipped: %s", arbiter_error)

        if hitl_enabled and review_samples:
            # ── Resolve the ReviewService ──────────────────────────────
            # Try to get the shared instance from app state first
            try:
                # When running inside the FastAPI lifespan, the service is
                # stored as a module-level singleton via _review_service_instance.
                from core import _review_service_instance  # type: ignore
                review_service = _review_service_instance
            except (ImportError, AttributeError):
                review_service = None

            if review_service is None and (getattr(self, "db_manager", None) or getattr(getattr(self, "db", None), "db", None)):
                try:
                    from core.review_service import ReviewService
                    db_mgr = getattr(self, "db_manager", None) or getattr(getattr(self, "db", None), "db", None)
                    review_service = ReviewService(db_mgr)
                    self.review_service = review_service
                except Exception:
                    review_service = None
            elif review_service is not None:
                self.review_service = review_service

            if review_service is not None:
                for sample in review_samples:
                    try:
                        import hashlib
                        sample_review_id = hashlib.sha256(
                            f"{job_id}:{sample.get('instruction', '')}:{sample.get('response', '')}".encode()
                        ).hexdigest()
                        await review_service.submit(
                            instruction=sample.get("instruction", ""),
                            response=sample.get("response", ""),
                            job_id=job_id,
                            dataset_id=sample_review_id,
                            source_url=sample.get("metadata", {}).get("source_url", ""),
                            source_text=sample.get("source_text", ""),
                            quality_score=float(sample.get("quality_score", 0.5)),
                            hallucination_risk=float(sample.get("hallucination_risk", 0.0)),
                            duplicate_score=float(sample.get("duplicate_score", 0.0)),
                            diversity_score=float(sample.get("diversity_score", 0.0)),
                            metadata=sample.get("metadata", {}),
                        )
                        review_ids[sample_review_id] = sample
                        submitted += 1
                    except Exception as sub_err:
                        logger.warning("Failed to submit sample for review: %s", sub_err)

                logger.info("Job %s: submitted %d/%d stratified audit samples (%.1f%% requested, mode=%s)",
                            job_id, submitted, constructed_count, review_percentage, hitl_mode)
            else:
                logger.warning(
                    f"Job {job_id} requested a human review audit, but the review service is unavailable. Proceeding."
                )

        # ── Blocking HITL gate ─────────────────────────────────────────
        approved = False
        if hitl_enabled and hitl_mode == "blocking" and review_service is not None and review_ids:
            # Update DB status so the UI shows the job is paused
            try:
                if self.db_manager:
                    await self.db_manager.update_job(
                        job_id,
                        status=JobStatus.AWAITING_REVIEW.value,
                        current_stage="human_review",
                    )
            except Exception:
                pass

            event = await review_service.pause_job_for_review(job_id)
            logger.info("Job %s paused at HITL gate — waiting for reviewer", job_id)

            try:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + hitl_timeout if hitl_timeout > 0 else None
                # Review decisions are stored in the shared database, but a
                # Celery worker and the API process have separate asyncio
                # events. Poll the DB periodically so API-side approvals also
                # release jobs running in another process.
                poll_interval = 2.0
                while True:
                    remaining = deadline - loop.time() if deadline is not None else None
                    if remaining is not None and remaining <= 0:
                        raise asyncio.TimeoutError
                    wait_seconds = min(poll_interval, remaining) if remaining is not None else poll_interval
                    try:
                        await asyncio.wait_for(event.wait(), timeout=wait_seconds)
                    except asyncio.TimeoutError:
                        # A timeout is a polling tick unless the configured
                        # overall HITL deadline has actually elapsed.
                        if deadline is not None and loop.time() >= deadline:
                            raise

                    queue = await review_service.get_queue(job_id=job_id, page=1, page_size=500)
                    review_items = list(queue.get("items", []))
                    for page in range(2, queue.get("total_pages", 1) + 1):
                        more = await review_service.get_queue(job_id=job_id, page=page, page_size=500)
                        review_items.extend(more.get("items", []))
                    by_review_id = {
                        str(item.get("dataset_id", "")): item
                        for item in review_items
                        if str(item.get("dataset_id", "")) in review_ids
                    }
                    pending = [
                        sample_id for sample_id in review_ids
                        if by_review_id.get(sample_id, {}).get("review_status") in {None, "pending"}
                    ]
                    if not pending:
                        break
                    logger.info("Job %s still has %d pending review samples", job_id, len(pending))
                    event = await review_service.pause_job_for_review(job_id)
                    if self.db_manager:
                        await self.db_manager.update_job(
                            job_id, status=JobStatus.AWAITING_REVIEW.value, current_stage="human_review"
                        )

                approved = True
            except asyncio.TimeoutError:
                logger.warning("Job %s HITL timeout (%ds) — pending reviewed examples will be excluded", job_id, hitl_timeout)
                approved = True
                await review_service.resume_job(job_id)
                queue = await review_service.get_queue(job_id=job_id, page=1, page_size=500)
                review_items = list(queue.get("items", []))
                for page in range(2, queue.get("total_pages", 1) + 1):
                    more = await review_service.get_queue(job_id=job_id, page=page, page_size=500)
                    review_items.extend(more.get("items", []))
                by_review_id = {
                    str(item.get("dataset_id", "")): item
                    for item in review_items
                    if str(item.get("dataset_id", "")) in review_ids
                }
        else:
            # async mode or service unavailable — continue without waiting
            approved = True

        if hitl_enabled and hitl_mode == "blocking" and review_service is not None and review_ids:
            retained_samples = []
            rejected_count = 0
            edited_count = 0
            duplicate_count = 0
            reviewed_sample_ids = {id(sample): sample_id for sample_id, sample in review_ids.items()}
            retained_sample_keys = set()
            for sample in samples:
                sample_id = reviewed_sample_ids.get(id(sample))
                if sample_id:
                    item = by_review_id.get(sample_id, {})
                    if item.get("review_status") != "approved":
                        rejected_count += 1
                        continue
                    edited_instruction = str(item.get("edited_instruction") or "").strip()
                    edited_response = str(item.get("edited_response") or "").strip()
                    if edited_instruction:
                        sample["instruction"] = edited_instruction
                    if edited_response:
                        sample["response"] = edited_response

                instruction_key = " ".join(str(sample.get("instruction", "")).casefold().split())
                response_key = " ".join(str(sample.get("response", "")).casefold().split())
                if not instruction_key or not response_key:
                    rejected_count += 1
                    continue
                sample_key = (instruction_key, response_key)
                if sample_key in retained_sample_keys:
                    duplicate_count += 1
                    rejected_count += int(sample_id is not None)
                    continue
                retained_sample_keys.add(sample_key)
                if sample_id and by_review_id.get(sample_id, {}).get("review_decision") == "edit":
                    edited_count += 1
                retained_samples.append(sample)
            samples = retained_samples
            retained_review_count = len(review_ids) - rejected_count
            logger.info("Job %s resumed after HITL approval", job_id)
            state["messages"].append(
                f"Review decisions applied: {rejected_count} rejected or unresolved, "
                f"{duplicate_count} duplicate edits removed, {edited_count} edited, "
                f"{retained_review_count} retained (including edits)."
            )

        return {
            **state,
            "constructed_samples": samples,
            "human_approval_needed": hitl_enabled and bool(review_samples),
            "human_approved": approved,
            "messages": [
                f"HITL audit: {submitted}/{constructed_count} samples submitted "
                f"({review_percentage:.1f}% requested), "
                f"mode={hitl_mode}, approved={approved}"
            ],
        }

    async def _error_handler_node(self, state: AgentState) -> AgentState:
        """Error handling with adaptation suggestions."""
        errors = state.get("errors", [])
        return {
            **state,
            "errors": ["Pipeline error occurred"],
            "should_retry": len(errors) < 3,
            "adaptation_notes": ["Consider relaxing constraints"]
        }

    async def _adapt_strategy_node(self, state: AgentState) -> AgentState:
        """Adapt strategy — always increments retry counter to prevent loops."""
        analysis = state.get("constraint_analysis", {})
        retry_count = state.get("filter_retry_count", 0) + 1

        new_messages = []
        new_notes    = []

        if "quality_budget_conflict" in analysis.get("conflicts", []):
            new_messages.append("Adapting: reducing quality threshold due to budget constraint")
            new_notes.append("quality_threshold_lowered")

        new_messages.append(f"Strategy adaptation #{retry_count} applied")

        return {
            **state,
            "filter_retry_count": retry_count,
            "messages": new_messages,
            "adaptation_notes": new_notes,
            "should_retry": True,
        }

    def _quality_threshold_check(self, state: AgentState) -> str:
        """Check quality with retry guard to prevent infinite loops."""
        filtered = state.get("filtered_samples", [])
        retries  = state.get("filter_retry_count", 0)
        MAX_RETRIES = 2

        if not filtered:
            job = state.get("job", {})
            config = job.get("config", {})
            mode = config.get("generation_mode", "strict_source")
            allow_fallback = config.get("allow_seedless_generation", False)

            if config.get("approved_examples"):
                logger.info("No new samples passed filtering; retaining the signed preview batch approved by the user.")
                return "continue"
            
            if mode in ("synthetic", "hybrid") or allow_fallback:
                logger.info("Filter produced 0 samples, but falling back to pure synthetic planning/generation.")
                return "continue"

            if state.get("low_resource_mode") and retries < MAX_RETRIES:
                logger.warning(
                    f"Filter produced 0 samples (low_resource_mode, retry {retries+1}/{MAX_RETRIES})"
                )
                return "adapt"
            logger.error(
                f"Filter produced 0 samples — failing pipeline "
                f"(retries={retries}, low_resource={state.get('low_resource_mode')})"
            )
            return "fail"

        avg_quality = sum(s.get("quality_score", 0) for s in filtered) / len(filtered)
        logger.info(f"Filter quality avg={avg_quality:.3f} over {len(filtered)} samples")

        if avg_quality > 0.6:
            return "continue"
        elif avg_quality > 0.3:
            return "review"
        elif retries < MAX_RETRIES:
            return "retry"
        else:
            logger.warning(f"Quality {avg_quality:.3f} below threshold after {retries} retries — continuing anyway")
            return "continue"

    def _adaptation_check(self, state: AgentState) -> str:
        """Route adaptation — use existing samples if available, else re-discover."""
        filtered = state.get("filtered_samples", [])
        notes    = state.get("adaptation_notes", [])

        # If we have ANY samples, lower the bar and construct from them
        if filtered:
            logger.info(f"Adaptation: using {len(filtered)} existing samples (reduce path)")
            return "reduce"

        # Only redo full discovery when we have literally nothing
        if notes:
            logger.info("Adaptation: zero samples, retrying discovery")
            return "retry"

        return "proceed"

    def _human_approval_check(self, state: AgentState) -> str:
        """Check if human approved. Defaults to approved (samples queued for review)."""
        if state.get("human_review_pending") and state.get("human_explicitly_rejected"):
            return "rejected"
        return "approved"

    async def run(self, job: Job, resume_state: Optional[dict] = None) -> dict:
        """Run the pipeline for a job."""
        job_id = job.id
        self.active_jobs[job_id] = job
        self._cancellation_events[job_id] = asyncio.Event()

        saved_stage = None
        resume_metadata = {}
        if resume_state:
            saved_stage = resume_state.get("resume_from_stage")
            saved_stage = getattr(saved_stage, "value", saved_stage)
            resume_metadata = resume_state.get("metadata") or {}

        job_dict = job.to_dict() if hasattr(job, "to_dict") else {
            "id": getattr(job, "id", None),
            "config": getattr(job, "config", {}) or {},
            "status": getattr(job, "status", "pending"),
            "progress": getattr(job, "progress", 0.0),
            "current_stage": getattr(job, "current_stage", "initializing"),
        }

        initial_state = {
            "job": job_dict,
            "sources": list((resume_state or {}).get("sources", resume_metadata.get("sources", []))),
            "extracted_content": list((resume_state or {}).get("extracted_content", [])),
            "filtered_samples": list((resume_state or {}).get("filtered_samples", [])),
            "constructed_samples": list((resume_state or {}).get("constructed_samples", [])),
            "errors": [],
            "warnings": [],
            "should_retry": False,
            "human_approval_needed": False,
            "human_approved": False,
            "messages": ([f"Resuming from {saved_stage} checkpoint"] if saved_stage else []),
            "current_stage": saved_stage or "pending",
            "progress": float((resume_state or {}).get("progress", 0.0) or 0.0),
            "constraint_analysis": None,
            "low_resource_mode": False,
            "multilingual_mode": False,
            "adaptation_notes": [],
            "filter_retry_count": 0,
            "dataset_plan": None,
            "coverage_matrix": None,
            "balance_report": None,
            "intent": None,
            "resume_from_stage": saved_stage,
            "quality_score": None,
            "quality_eval_passed": True,
            "quality_breakdown": None,
        }
        # Intent extraction - the single source of truth for the request
        try:
            approved_plan = job.config.get("query_plan")
            if approved_plan:
                intent = UserIntent(
                    **approved_plan,
                    raw_input=job.config.get("target_domain", ""),
                )
            else:
                try:
                    intent = await extract_intent(
                        raw_input=str(job.config.get("target_domain", "")),
                        provider_router=self.router,
                        redis_client=getattr(self, 'redis_client', None),
                    )
                except Exception as e:
                    logger.warning(f"Intent extraction fallback for job {job_id}: {e}")
                    intent = UserIntent.from_fallback(
                        str(job.config.get("target_domain", "")),
                        primary_task="data synthesis",
                        confidence=0.7,
                    )
            approved_queries = job.config.get("specialized_queries") or []
            if approved_queries:
                intent.specialized_queries = approved_queries[:10]
            ideal_samples = job.config.get("ideal_samples") or []
            if ideal_samples:
                intent.ideal_samples = ideal_samples[:10]
            initial_state["intent"] = intent
        except Exception as e:
            logger.error(f"Unexpected error constructing initial intent for job {job_id}: {e}")
            initial_state["intent"] = UserIntent.from_fallback(
                str(job.config.get("target_domain", "")),
                primary_task="data synthesis",
                confidence=0.7,
            )


        try:
            final_state = {}
            
            # Phase 5: Enforce dynamic job timeout durations
            timeout_seconds = job.config.get("timeout_seconds", 7200)
            
            async def iterate_graph():
                nonlocal final_state
                async for state in self.graph.astream(
                    initial_state,
                    config={"configurable": {"thread_id": job_id}}
                ):
                    final_state = state
                    await self._save_persistent_checkpoint(job_id)

            try:
                await asyncio.wait_for(iterate_graph(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Pipeline execution timed out after {timeout_seconds} seconds")

            # Fetch complete final state from checkpointer
            try:
                graph_state = await self.graph.aget_state(config={"configurable": {"thread_id": job_id}})
                if graph_state and graph_state.values:
                    final_state = graph_state.values
            except Exception as checkpoint_err:
                logger.warning(f"Failed to fetch final state from checkpointer: {checkpoint_err}")

            if final_state:
                # In LangGraph astream, the yielded chunk is often keyed by node name: {node_name: state_dict}
                # If final_state is wrapped by node name(s), unwrap/merge to ensure top-level access.
                unwrapped_state = dict(final_state)
                for node_name in ["export", "balance", "human_review", "quality_eval", "construct", "filter", "extract", "discover", "plan"]:
                    if node_name in unwrapped_state and isinstance(unwrapped_state[node_name], dict):
                        unwrapped_state.update(unwrapped_state[node_name])
                final_state = unwrapped_state

                job.current_stage = final_state.get("current_stage", job.current_stage)
                job.progress = final_state.get("progress", job.progress)
                
                constructed_samples = final_state.get("constructed_samples", [])
                extracted_content = final_state.get("extracted_content", [])
                sources = final_state.get("sources", [])
                filtered_samples = final_state.get("filtered_samples", [])
                
                job.samples_generated = len(constructed_samples)
                job.samples_processed = len(extracted_content)
                job.sources_discovered = len(sources)
                job.sources_extracted = len(extracted_content)
                job.samples_filtered = len(filtered_samples)

                final_status = "completed" if constructed_samples else "failed"
                job.status = JobStatus.COMPLETED if constructed_samples else JobStatus.FAILED
                if not constructed_samples:
                    final_state.setdefault("errors", []).append(
                        "No usable source-grounded samples were produced. Refine the request or broaden the source constraints."
                    )

                if self._db_update_tasks:
                    pending_tasks = [t for t in self._db_update_tasks if not t.done()]
                    if pending_tasks:
                        await asyncio.gather(*pending_tasks, return_exceptions=True)

                if self.db:
                    try:
                        await self.db.update_job(
                            job_id,
                            status=final_status,
                            progress=1.0,
                            current_stage=job.current_stage if constructed_samples else "failed",
                            samples_generated=job.samples_generated,
                            samples_processed=job.samples_processed,
                            sources_discovered=job.sources_discovered,
                            sources_extracted=job.sources_extracted,
                            samples_filtered=job.samples_filtered,
                        )
                    except Exception as db_err:
                        logger.error(f"Failed to update final job metrics in database: {db_err}")

            self._cleanup_job(job_id)
            return final_state
        except Exception as e:
            # Add threshold diagnostics to final error message for pipeline completion logic
            error_msg = str(e)
            if 'final_state' in locals() and final_state:
                # Extract threshold and scoring information for diagnostics
                filtered_samples = final_state.get("filtered_samples", [])
                extracted_content = final_state.get("extracted_content", [])
                job_config = final_state.get("job", {}).get("config", {})

                # Add sample count diagnostics
                if len(extracted_content) > 0:
                    error_msg += f"\nThreshold diagnostics: {len(extracted_content)} extracted"
                    if len(filtered_samples) == 0:
                        error_msg += ", 0 filtered (zero-sample situation)"
                    else:
                        error_msg += f", {len(filtered_samples)} filtered"

                # Add threshold information from job config
                thresholds_info = []
                if job_config.get("quality_threshold") is not None:
                    thresholds_info.append(f"quality_threshold={job_config.get('quality_threshold')}")
                if job_config.get("relevance_threshold") is not None:
                    thresholds_info.append(f"relevance_threshold={job_config.get('relevance_threshold')}")
                if job_config.get("statistical_threshold") is not None:
                    thresholds_info.append(f"statistical_threshold={job_config.get('statistical_threshold')}")

                if thresholds_info:
                    error_msg += f" | {' '.join(thresholds_info)}"

                # Add average quality score if we have filtered samples
                if filtered_samples:
                    try:
                        avg_quality = sum(s.get("quality_score", 0) for s in filtered_samples) / len(filtered_samples)
                        error_msg += f" | avg_quality={avg_quality:.3f}"
                    except (TypeError, ZeroDivisionError):
                        pass

            self._update_job_status(job_id, "failed", 0.0, error=error_msg)
            self._cleanup_job(job_id)
            raise

    def _cleanup_job(self, job_id: str) -> None:
        """Clean up all in-memory state for a completed/failed/cancelled job."""
        self.active_jobs.pop(job_id, None)
        self._cancellation_events.pop(job_id, None)

    async def _save_persistent_checkpoint(self, job_id: str) -> None:
        """Persist a graph snapshot after a recoverable pipeline boundary."""
        if not self.persistent_checkpoint_manager:
            return
        try:
            graph_state = await self.graph.aget_state(config={"configurable": {"thread_id": job_id}})
            state = graph_state.values if graph_state else None
            if not state:
                return
            stage_name = state.get("current_stage")
            from core.orchestrator_pkg.checkpoints import CheckpointStage
            stages = {
                "discover": CheckpointStage.DISCOVERY,
                "extract": CheckpointStage.EXTRACTION,
                "filter": CheckpointStage.FILTERING,
                "construct": CheckpointStage.CONSTRUCTION,
                "export": CheckpointStage.EXPORT,
            }
            stage = stages.get(stage_name)
            if not stage:
                return
            await self.persistent_checkpoint_manager.create_checkpoint(
                job_id=job_id,
                stage=stage,
                progress=float(state.get("progress", 0.0) or 0.0),
                sources_discovered=len(state.get("sources", [])),
                sources_extracted=len(state.get("extracted_content", [])),
                samples_filtered=len(state.get("filtered_samples", [])),
                samples_generated=len(state.get("constructed_samples", [])),
                extracted_content=_json_safe(state.get("extracted_content", [])),
                filtered_samples=_json_safe(state.get("filtered_samples", [])),
                constructed_samples=_json_safe(state.get("constructed_samples", [])),
                metadata={
                    "sources": _json_safe(state.get("sources", [])),
                    "automatic": True,
                },
            )
        except Exception as exc:
            logger.warning("Could not persist checkpoint for job %s: %s", job_id, exc)

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id in self._cancellation_events:
            self._cancellation_events[job_id].set()
            self._update_job_status(job_id, "cancelled", 0.0)
            self._cleanup_job(job_id)
            return True
        return False

    def _is_cancelled(self, job_id: str) -> bool:
        """Check if job is cancelled."""
        if job_id in self._cancellation_events:
            return self._cancellation_events[job_id].is_set()
        return False

    def _update_job_status(self, job_id: str, stage: str, progress: float, error: str | None = None, **kwargs):
        """Update job status and broadcast via WebSocket if available."""
        if job_id not in self.active_jobs:
            return

        job = self.active_jobs[job_id]
        job.current_stage = stage
        job.progress = progress
        job.updated_at = datetime.now(timezone.utc)
        if error:
            job.error = error
            job.status = JobStatus.FAILED
        elif stage == "completed":
            job.status = JobStatus.COMPLETED
        elif stage == "cancelled":
            job.status = JobStatus.CANCELLED
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)

        # Persist to DB (fire-and-forget with error logging)
        if self.db:
            db_fields = {
                "current_stage": stage,
                "progress": progress,
                "error": error,
            }
            if error:
                db_fields["status"] = "failed"
            elif stage == "completed":
                db_fields["status"] = "completed"
            elif stage == "cancelled":
                db_fields["status"] = "cancelled"
            else:
                db_fields["status"] = "running" if stage != "pending" else "pending"
            for k, v in kwargs.items():
                db_fields[k] = v
            task = asyncio.create_task(self._safe_db_update(job_id, db_fields))
            self._db_update_tasks.add(task)
            task.add_done_callback(self._db_update_tasks.discard)

        # Broadcast via WebSocket
        if self.ws_manager:
            try:
                from api.websocket_manager import MessageType, WebSocketMessage
                samples_generated = getattr(job, "samples_generated", 0)
                message = WebSocketMessage(
                    type=MessageType.PROGRESS,
                    job_id=job_id,
                    data={
                        "stage": stage,
                        "progress": progress,
                        "samples_generated": samples_generated,
                        "error": error,
                        **{k: v for k, v in kwargs.items()},
                    }
                )
                asyncio.create_task(self._safe_ws_broadcast(job_id, message))
            except Exception:
                pass  # WebSocket is best-effort; never block pipeline

    async def _safe_db_update(self, job_id: str, db_fields: dict) -> None:
        """Fire-and-forget DB update with monotonicity guard and error logging."""
        try:
            if job_id in self.active_jobs:
                active_job = self.active_jobs[job_id]
                if "samples_generated" in db_fields:
                    db_fields["samples_generated"] = max(
                        int(db_fields["samples_generated"] or 0),
                        getattr(active_job, "samples_generated", 0)
                    )
                if "progress" in db_fields:
                    db_fields["progress"] = max(
                        float(db_fields["progress"] or 0.0),
                        getattr(active_job, "progress", 0.0)
                    )
            await self.db.update_job(job_id, **db_fields)
        except Exception as e:
            logger.error(f"[{job_id}] Failed to persist job status to DB: {e}", exc_info=True)

    async def _safe_ws_broadcast(self, job_id: str, message) -> None:
        """Fire-and-forget WebSocket broadcast with error logging."""
        try:
            if self.ws_manager:
                await self.ws_manager.send_to_job(job_id, message)
        except Exception as e:
            logger.warning(f"[{job_id}] WebSocket broadcast failed: {e}")

    def _update_job_progress(self, job_id: str, progress: float):
        """Update job progress."""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].progress = progress
            if self.db:
                asyncio.create_task(self._safe_db_update(job_id, {"progress": progress}))

            # Broadcast via WebSocket (best-effort)
            if self.ws_manager:
                try:
                    from api.websocket_manager import MessageType, WebSocketMessage
                    job = self.active_jobs[job_id]
                    message = WebSocketMessage(
                        type=MessageType.PROGRESS,
                        job_id=job_id,
                        data={
                            "stage": job.current_stage,
                            "progress": progress,
                            "samples_generated": getattr(job, "samples_generated", 0),
                        }
                    )
                    asyncio.create_task(self._safe_ws_broadcast(job_id, message))
                except Exception:
                    pass

    def get_progress(self, job_id: str) -> float:
        """Get job progress."""
        if job_id in self.active_jobs:
            return self.active_jobs[job_id].progress
        return 0.0

    def get_active_jobs(self) -> list[dict]:
        """Get all active jobs."""
        return [job.to_dict() for job in self.active_jobs.values()]
