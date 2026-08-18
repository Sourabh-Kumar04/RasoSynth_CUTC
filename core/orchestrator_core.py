"""
CANONICAL ORCHESTRATOR - This is the only production orchestrator.

References:
- core/orchestrator_checkpoint_integrated.py (STUB/REFERENCE - nodes are stubs)
- orchestrator/autonomous_orchestrator.py (EXPERIMENTAL - not connected to API)

Enhanced orchestrator with intelligent reasoning and constraint handling.
"""
import asyncio
import logging
from typing import TypedDict, Annotated, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
try:
    from langgraph.checkpoint.postgres import AsyncPostgresSaver
    POSTGRES_SAVER_AVAILABLE = True
except ImportError:
    POSTGRES_SAVER_AVAILABLE = False
import operator
from core.intent import UserIntent, IntentExtractionError
from core.intent_extractor import extract_intent
import json


logger = logging.getLogger(__name__)


def _sanitize_metadata(meta: dict) -> dict:
    """JSON round-trip to guarantee all values are serializable."""
    try:
        import json as _json
        return _json.loads(_json.dumps(meta, default=str))
    except Exception:
        return {}


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
    feasibility_score: float = 0.5
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
            warnings.append(f"Time period constraint may limit available sources")
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
        analysis.estimated_cost = self._estimate_cost(config, analysis.estimated_samples)

        analysis.warnings = warnings
        analysis.fallback_strategies = strategies
        analysis.constraint_conflicts = conflicts

        return analysis

    def _is_niche_domain(self, domain: str) -> bool:
        """Check if domain appears niche."""
        niche_indicators = [
            "obscure", "specialized", "ancient", "historical",
            "rare", "esoteric", "niche", "arcane"
        ]
        return any(ind in domain.lower() for ind in niche_indicators)

    def _is_low_resource_domain(self, domain: str) -> bool:
        """Check if domain is likely low-resource."""
        low_resource_indicators = [
            "ancient", "historical", "medieval", "tribal",
            "endangered", "minority", "regional"
        ]
        return any(ind in domain.lower() for ind in low_resource_indicators)

    def _is_source_domain_relevant(self, source: dict, target_domain: str) -> bool:
        """Verify whether a discovered source is genuinely relevant to target_domain."""
        if not target_domain or target_domain.lower() in ("general", "custom", "all", "sft"):
            return True

        import re
        title = str(source.get("title", "")).lower()
        desc = str(source.get("description", "")).lower()
        url = str(source.get("url", "")).lower()
        text_body = str(source.get("text", "") or source.get("content", "")).lower()
        full_content = f"{title} {desc} {url} {text_body[:3000]}"

        # Reject web catalog badges, awesome lists, and HTML headers
        if any(bad in full_content for bad in [
            "awesome-datascience", "awesome data science", "<div align=", "<img src=",
            "table of contents", "badge.svg", "become a sponsor"
        ]):
            return False

        domain_keywords = [
            w for w in re.split(r'\W+', target_domain.lower())
            if len(w) > 3 and w not in ("dataset", "data", "file", "download", "train", "synthetic", "example", "examples")
        ]

        if not domain_keywords:
            return True

        match_count = sum(1 for kw in domain_keywords if kw in full_content)
        return match_count >= 1



    def _estimate_sources(self, config: dict) -> int:
        """Estimate number of discoverable sources."""
        base_estimate = 100

        # Reduce for constraints
        if config.get("allowed_domains"):
            base_estimate *= 0.7

        if config.get("time_period"):
            base_estimate *= 0.5

        # Increase for popular domains
        popular_domains = ["machine learning", "python", "programming", "science"]
        if any(d in config.get("target_domain", "").lower() for d in popular_domains):
            base_estimate *= 2

        return int(base_estimate)

    def _estimate_cost(self, config: dict, sample_count: int) -> float:
        """Estimate cost for dataset generation."""
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

        return min(base_cost, config.get("cost_budget_usd", 100.0))


class DatasetOrchestrator:
    """Enhanced orchestrator with constraint awareness and intelligent adaptation."""

    def __init__(self, config: dict, router, db=None, observability=None, ws_manager=None):
        self.config = config
        self.router = router
        self.db = db
        # Expose the raw DatabaseManager so nodes like _human_review_node can call update_job
        self.db_manager = getattr(db, "db", None) if db is not None else None
        self.ws_manager = ws_manager
        if observability:
            self.observability = observability
        else:
            from core.observability_manager import ObservabilityManager
            from core.config import Settings
            self.observability = ObservabilityManager(Settings())

        # Initialize checkpointer - use PostgreSQL for persistence when available
        if POSTGRES_SAVER_AVAILABLE and self.config.get("postgres_url"):
            try:
                self.checkpointer = AsyncPostgresSaver.from_conn_string(self.config["postgres_url"])
                logger.info("Using PostgreSQL for LangGraph checkpoint persistence")
            except Exception as e:
                logger.warning(f"Failed to initialize AsyncPostgresSaver: {e}. Falling back to MemorySaver.")
                self.checkpointer = MemorySaver()
        else:
            self.checkpointer = MemorySaver()
            if not POSTGRES_SAVER_AVAILABLE:
                logger.warning("AsyncPostgresSaver not available. Using MemorySaver for checkpoints (state lost on restart).")

        self.graph = self._build_graph()
        self.active_jobs: dict[str, Job] = {}
        self._cancellation_events: dict[str, asyncio.Event] = {}
        self.constraint_analyzer = ConstraintAnalyzer(config)
        self.redis_client = None  # Redis client for intent caching (optional)

    def _is_source_relevant(self, source) -> bool:
        """
        Reject a source if any term from intent.anti_domains appears
        in its title, description, or URL.
        """
        if self.intent is None:
            # Defensive: should never happen in normal flow
            return True
        if isinstance(source, dict):
            title = (source.get("title") or "").lower()
            description = (source.get("description") or "").lower()
            url = (source.get("url") or "").lower()
        else:
            # DiscoveredSource / any object with .title, .url, .description
            title = (getattr(source, "title", None) or "").lower()
            description = (getattr(source, "description", None) or "").lower()
            url = (getattr(source, "url", None) or "").lower()
        combined = f"{title} {description} {url}"
        for anti in self.intent.anti_domains:
            if anti in combined:
                logger.debug(f"Rejected source '{title}' – matched anti-domain '{anti}'")
                return False
        return True

    def _build_graph(self) -> StateGraph:
        """Build the orchestration graph with adaptive stages."""
        workflow = StateGraph(AgentState)

        # Core pipeline stages
        workflow.add_node("analyze_constraints", self._analyze_constraints_node)
        workflow.add_node("discover", self._discover_node)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("filter", self._filter_node)
        workflow.add_node("construct", self._construct_node)
        workflow.add_node("export", self._export_node)
        workflow.add_node("human_review", self._human_review_node)
        workflow.add_node("error_handler", self._error_handler_node)
        workflow.add_node("adapt_strategy", self._adapt_strategy_node)
        workflow.add_node("plan", self._plan_node)

        # NOTE: analyze_constraints intentionally has NO unconditional edge.
        # Adding both an unconditional edge AND a conditional edge from the same
        # node fires both paths in parallel, producing two writes to "job" in
        # the same step and raising INVALID_CONCURRENT_GRAPH_UPDATE. The
        # conditional edge below already routes "proceed" -> "discover".
        workflow.set_entry_point("analyze_constraints")

        # Main pipeline (only nodes that have NO conditional edges)
        workflow.add_edge("discover", "extract")
        workflow.add_edge("extract", "filter")
        workflow.add_edge("plan", "construct")
        workflow.add_edge("construct", "export")
        workflow.add_edge("export", END)

        # NOTE: filter intentionally has NO unconditional edge.
        # The add_conditional_edges below defines every possible target:
        #   "continue" → "construct" | "review" → "human_review"
        #   "retry" → "extract"        | "adapt" → "adapt_strategy"
        #   "fail" → END
        # Adding an unconditional add_edge("filter", "construct") on top
        # would duplicate the destination and trigger
        # INVALID_CONCURRENT_GRAPH_UPDATE on any state key returned by
        # both branches (because every node uses {**state}).

        # Adaptive edges
        workflow.add_conditional_edges(
            "analyze_constraints",
            self._feasibility_check,
            {
                "proceed": "discover",
                "proceed_synthetic": "plan",
                "negotiate": "adapt_strategy",
                "fail": END
            }
        )

        workflow.add_conditional_edges(
            "filter",
            self._quality_threshold_check,
            {
                "continue": "construct",
                "review": "human_review",
                "retry": "extract",
                "adapt": "adapt_strategy",
                "fail": END
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

        workflow.add_conditional_edges(
            "human_review",
            self._human_approval_check,
            {
                "approved": "construct",
                "rejected": END
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
            "warnings": state.get("warnings", []) + analysis.warnings,
            "messages": state["messages"] + [f"Constraint analysis: {analysis.feasibility_score:.0%} feasible"],
        }

    def _feasibility_check(self, state: AgentState) -> str:
        """Check if constraints are feasible."""
        job = state.get("job", {})
        config = job.get("config", {})
        mode = config.get("generation_mode", "hybrid")
        
        if mode == "synthetic":
            logger.info("Generation mode is set to synthetic. Proceeding directly to planning.")
            return "proceed_synthetic"

        analysis = state.get("constraint_analysis", {})
        score = analysis.get("feasibility_score", 0.5)

        if score < 0.3:
            return "fail"
        elif score < 0.5:
            return "negotiate"
        else:
            return "proceed"

    async def _plan_node(self, state: AgentState) -> AgentState:
        """Analyze user prompt and create a structured dataset plan."""
        job = state["job"]
        job_id = job["id"]
        config = job["config"]

        self._update_job_status(job_id, "plan", 0.3)

        from pipeline.planner import DatasetPlanner, CoveragePlanner

        planner = DatasetPlanner(self.router, config)
        cov_planner = CoveragePlanner(config)

        prompt = config.get("target_domain", "")

        plan = await planner.create_plan(prompt)
        coverage = cov_planner.generate_matrix(plan, target_size=config.get("dataset_size", 100))

        return {
            **state,
            "dataset_plan": plan.model_dump(),
            "coverage_matrix": coverage.model_dump(),
            "current_stage": "plan",
            "progress": 0.4,
            "messages": state["messages"] + [f"Generated dataset plan with {len(coverage.cells)} planned coverage cells"],
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
        config = job["config"]

        self._update_job_status(job_id, "discover", 0.1)

        from pipeline.discovery import DiscoveryPipeline, SourceType
        from core.pagination import BackpressureIterator, chunked_async_iter, StreamProgress

        discovery = DiscoveryPipeline(config, router=self.router)

        target_domain = config.get("target_domain", "")
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

        # Generate multiple query variations for better coverage
        queries = self._get_discovery_queries(self.intent)

        max_sources = min(config.get("max_results", 500), state.get("constraint_analysis", {}).get("estimated_sources", 200))
        batch_size = config.get("batch_size", 50)  # Process in batches

        # Create streaming source
        async def source_generator():
            for query in queries:
                if self._is_cancelled(job_id):
                    break
                async for source in discovery.discover(query, target_domain, source_types):
                    # Apply domain relevance pre-filter to skip off-topic sources early.
                    # ``_is_source_relevant`` lives on DatasetOrchestrator and uses intent.
                    if self._is_source_relevant(source):
                        yield source
                    else:
                        logger.debug(f"Skipping off-topic source: "
                                    f"{source.get('url','unknown') if isinstance(source, dict) else getattr(source, 'url', 'unknown')}")
                    if self._is_cancelled(job_id):
                        break

        # Use backpressure-aware iterator with bounded memory
        streaming_source = BackpressureIterator(
            source_generator(),
            buffer_size=batch_size,
            max_memory_mb=config.get("max_memory_mb", 512),
        )

        # Stream processing with bounded memory accumulation
        sources = []
        batch_count = 0
        progress = StreamProgress()

        async for source in streaming_source:
            sources.append({
                "url": source.url,
                "source_type": source.source_type.value,
                "title": source.title,
                "description": source.description,
                "metadata": source.metadata,
                "language": getattr(source, 'language', language),
            })
            progress.total_processed += 1

            # Update progress every batch
            if len(sources) % batch_size == 0:
                batch_count += 1
                self._update_job_progress(job_id, 0.1 + (len(sources) / max(max_sources, 1)) * 0.15)
                # Brief yield to event loop for backpressure
                await asyncio.sleep(0)

            # Memory-bounded: flush processed sources if accumulating too fast
            if progress.total_processed >= max_sources:
                break

            # Yield periodically to prevent unbounded memory growth
            if batch_count > 0 and batch_count % 10 == 0:
                # Log telemetry
                logger.info(
                    f"Discovery progress: {len(sources)} sources, "
                    f"rate: {progress.items_per_second:.1f}/s"
                )

        # Log any streaming errors
        errors = streaming_source.get_errors()
        if errors:
            logger.warning(f"Discovery streaming completed with {len(errors)} errors")
            for err in errors:
                state["warnings"].append(f"Discovery error: {str(err)}")

        # Update progress
        self._update_job_status(job_id, "discover", 0.3, sources_discovered=len(sources))

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
            "messages": state["messages"] + [
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

        # Base sources - always include these (prioritize high-quality dataset repositories)
        source_types = [
            SourceType.HF_DATASET,      # HuggingFace Datasets (primary)
            SourceType.KAGGLE_DATASET,  # Kaggle (primary)
            SourceType.OPENML,       SourceType.ZENODO,               # Zenodo (primary)
            SourceType.PAPERS_WITH_CODE, # Papers with Code (primary)
            SourceType.WEB_PAGE,         # General web (fallback)
            SourceType.GITHUB_REPO,      # GitHub repos (for code, not primary datasets)
        ]

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
                source_types.extend([SourceType.GOVERNMENT_DATA, SourceType.EUROSTAT, SourceType.DATAPORTALS_ORG, SourceType.DATAHUB_IO, SourceType.UNESCO, SourceType.WORLD_BANK])

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
        reachable_sources = []
        head_tasks = [_is_url_reachable(s.get("url", "") if isinstance(s, dict) else getattr(s, "url", "")) for s in sources]
        head_results = await asyncio.gather(*head_tasks, return_exceptions=True)

        for source, ok in zip(sources, head_results):
            if ok is True:
                reachable_sources.append(source)
            else:
                source_url = source.get("url","") if isinstance(source, dict) else getattr(source,"url","")
                logger.debug(f"Skipping unreachable source: {source_url}")

        sources = reachable_sources
        logger.info(f"[{job_id}] Pre-validation: {len(sources)}/{len(state['sources'])} sources reachable")

        self._update_job_status(job_id, "extract", 0.3)

        from pipeline.extraction import ExtractionPipeline

        extraction = ExtractionPipeline(self.config, self.router)
        extracted = []

        for source in sources:
            source_url = source.get("url") if isinstance(source, dict) else getattr(source, "url", "unknown")
            start_time = asyncio.get_event_loop().time()
            if self._is_cancelled(job_id):
                break

            try:
                source_extracted_count = 0
                async for content in extraction.extract(source):
                    source_extracted_count += 1
                    # Check for quality
                    if content.confidence > 0.3:
                        # Deep-sanitize metadata using JSON round-trip for serialization safety
                        safe_metadata = _sanitize_metadata(
                            {k: v for k, v in content.metadata.items() if k != "analysis"}
                        )
                        extracted.append({
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
                if source_extracted_count == 0:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    self.observability.log_pipeline_stage(
                        job_id=job_id,
                        stage="extraction",
                        source_url=source_url,
                        duration_ms=duration_ms,
                        decision="empty",
                        metadata={"info": "No items extracted from this source"}
                    )
            except Exception as e:
                # Security: Proper error handling with structured logging
                error_msg = f"Extraction error for {source_url}: {str(e)}"
                state["warnings"].append(error_msg)
                # Log for observability - don't silently swallow.
                # Use module-level logger (defined at top of this file); redefining
                # it here would make ``logger`` a function-local name, breaking reads
                # earlier in this function (UnboundLocalError on `_extract_node`).
                logger.error(f"Job {job_id}: {error_msg}", exc_info=True)
                
                duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                self.observability.log_pipeline_stage(
                    job_id=job_id,
                    stage="extraction",
                    source_url=source_url,
                    duration_ms=duration_ms,
                    decision="failed",
                    issues=[str(e)]
                )

        self._update_job_status(
            job_id,
            "extract",
            0.5,
            sources_extracted=len(sources),
            samples_processed=len(extracted)
        )

        return {
            **state,
            "extracted_content": extracted,
            "current_stage": "extract",
            "progress": 0.3,
            "messages": state["messages"] + [f"Extracted {len(extracted)} content items"],
        }

    async def _filter_node(self, state: AgentState) -> AgentState:
        """Enhanced filtering with adaptive thresholds."""
        job = state["job"]
        job_id = job["id"]
        extracted = state["extracted_content"]

        self._update_job_status(job_id, "filter", 0.5)

        from pipeline.filtering import FilteringPipeline

        filtering = FilteringPipeline(self.router, self.config)
        filtered = []

        target_domain = job["config"].get("target_domain", "")

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
                    filtering.filter(content, self.intent, return_all=True),
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
            relevant_extracted = [
                item for item in extracted
                if analyzer._is_source_domain_relevant(item, target_domain)
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
                    f"[{job_id}] All extracted items were off-topic for domain '{target_domain}'. "
                    f"Bypassing extracted sources to use pure seedless synthetic generation."
                )
                filtered = []  # Triggers seedless synthetic construction

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
            "messages": state["messages"] + [f"Filtered to {len(filtered)} quality samples"],
        }

    async def _construct_node(self, state: AgentState) -> AgentState:
        """Enhanced construction with schema inference and seedless synthetic support."""
        job = state["job"]
        job_id = job["id"]
        config = job["config"]
        filtered = state["filtered_samples"]

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

        # Check if we should use seedless synthetic generation
        generation_mode = config.get("generation_mode", "hybrid")
        allow_seedless = config.get("allow_seedless_generation", True)

        if not filtered and (generation_mode == "synthetic" or allow_seedless):
            logger.info("No crawled reference data found. Launching Pure Synthetic planning & generation.")
            
            # 1. Ensure Plan and Coverage Matrix exist
            plan_dict = state.get("dataset_plan")
            coverage_dict = state.get("coverage_matrix")

            if not plan_dict or not coverage_dict:
                logger.info("Initializing dataset plan and coverage matrix on-the-fly.")
                planner = DatasetPlanner(self.router, config)
                cov_planner = CoveragePlanner(config)
                prompt = config.get("target_domain", "")
                plan = await planner.create_plan(prompt)
                coverage = cov_planner.generate_matrix(plan, target_size=config.get("dataset_size", 100))
                plan_dict = plan.model_dump()
                coverage_dict = coverage.model_dump()
            
            # Parse plan_dict back to DatasetPlan object
            plan_obj = DatasetPlan(**plan_dict)
            
            # 2. Setup Generator and Validator
            generator = SeedlessGenerator(self.router, config)
            validator = MultiStageValidator(self.router, config)
            
            max_attempts = config.get("regeneration_attempts", 3)
            cells = coverage_dict.get("cells", [])

            # Generate samples using the coverage matrix cells
            for idx, cell in enumerate(cells):
                if self._is_cancelled(job_id):
                    break
                
                # Update progress incrementally
                if idx % max(1, len(cells) // 10) == 0:
                    prog = 0.7 + (idx / len(cells)) * 0.2
                    self._update_job_status(job_id, "construct", prog, samples_generated=len(samples))

                valid_sample = None
                for attempt in range(max_attempts):
                    sample = await generator.generate_sample(plan_obj, cell)
                    val_res = await validator.validate(sample)
                    if val_res.is_valid:
                        valid_sample = sample
                        break
                    else:
                        logger.warning(
                            f"Sample validation failed (attempt {attempt+1}/{max_attempts}): "
                            f"{', '.join(val_res.reasons)}"
                        )

                if valid_sample:
                    samples.append({
                        "instruction": valid_sample.instruction,
                        "response": valid_sample.response,
                        "input": valid_sample.input,
                        "conversation": getattr(valid_sample, "conversation", None),
                        "metadata": valid_sample.metadata,
                        "difficulty_tier": valid_sample.difficulty_tier,
                        "curriculum_order": len(samples),
                    })
        else:
            # Source-based / Hybrid source generation
            construction = ConstructionPipeline(self.router, config)
            for item in filtered:
                if self._is_cancelled(job_id):
                    break

                sample = type('Sample', (), {
                    "content": item["content"],
                    "quality_score": item.get("quality_score", 0.5),
                    "metadata": item.get("metadata", {}),
                })()

                async for constructed in construction.construct(
                    sample,
                    self.intent,
                    dataset_type=dataset_type
                ):
                    samples.append({
                        "instruction": constructed.instruction,
                        "response": constructed.response,
                        "input": constructed.input,
                        "conversation": getattr(constructed, "conversation", None),
                        "metadata": constructed.metadata,
                        "difficulty_tier": constructed.difficulty_tier,
                        "curriculum_order": constructed.curriculum_order,
                    })

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
            "messages": state["messages"] + [f"Constructed {len(samples)} training samples"],
        }

    async def _export_node(self, state: AgentState) -> AgentState:
        """Export stage."""
        job = state["job"]
        job_id = job["id"]
        raw_samples = state["constructed_samples"]

        self._update_job_status(job_id, "export", 0.9)

        # Convert dict samples to objects for downstream attribute access
        from types import SimpleNamespace
        samples = [
            SimpleNamespace(**s) if isinstance(s, dict) else s
            for s in raw_samples
        ]

        from pipeline.export import ExportPipeline, ExportConfig

        # Build export config from job config + global settings
        job_config = job.get("config", {})
        export_config = ExportConfig(
            format=job_config.get("export_format", "jsonl"),
            output_dir=self.config.get("output_dir", "outputs"),
            dataset_name=job_config.get("dataset_name", f"dataset_{job_id}"),
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

        # Persist dataset and samples to database
        if self.db and samples:
            try:
                # Create dataset record
                dataset_record = await self.db.create_dataset(
                    job_id=job_id,
                    name=export_config.dataset_name,
                    type=export_config.format,
                    size=len(samples),
                    metadata={"export_path": str(export_result.get("dataset", ""))},
                    output_path=str(export_result.get("dataset", ""))
                )

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

        self._update_job_status(
            job_id,
            "completed",
            1.0,
            samples_generated=len(samples)
        )

        return {
            **state,
            "current_stage": "export",
            "progress": 1.0,
            "messages": state["messages"] + [f"Exported {len(samples)} samples"],
        }

    async def _human_review_node(self, state: AgentState) -> AgentState:
        """
        Human-in-the-loop (HITL) gate.

        1. Submits all constructed samples to the persistent review queue.
        2. If `human_review_mode` is "blocking" (default when human_review=True),
           pauses the pipeline and awaits a reviewer calling
           POST /api/review/jobs/{job_id}/resume.
        3. Once resumed, marks the job approved and continues to export.

        Config keys:
          human_review        (bool, default True)  — enable HITL gate
          human_review_mode   (str)  — "blocking" | "async"
            blocking: wait for explicit /resume call (real HITL)
            async:    submit for review but continue immediately
          hitl_timeout_seconds (int) — max seconds to wait (0 = unlimited)
        """
        job = state["job"]
        job_id = job["id"]
        samples = state.get("constructed_samples", [])
        config = job.get("config", {})

        hitl_enabled = config.get("human_review", True)
        hitl_mode = config.get("human_review_mode", "blocking")
        hitl_timeout = int(config.get("hitl_timeout_seconds", 0))

        submitted = 0
        review_service = None

        if hitl_enabled and samples:
            # ── Resolve the ReviewService ──────────────────────────────
            # Try to get the shared instance from app state first
            try:
                # When running inside the FastAPI lifespan, the service is
                # stored as a module-level singleton via _review_service_instance.
                from core import _review_service_instance  # type: ignore
                review_service = _review_service_instance
            except (ImportError, AttributeError):
                review_service = None

            if review_service is not None:
                for sample in samples:
                    try:
                        await review_service.submit(
                            instruction=sample.get("instruction", ""),
                            response=sample.get("response", ""),
                            job_id=job_id,
                            dataset_id=sample.get("dataset_id", ""),
                            source_url=sample.get("metadata", {}).get("source_url", ""),
                            source_text=sample.get("source_text", ""),
                            quality_score=float(sample.get("quality_score", 0.5)),
                            hallucination_risk=float(sample.get("hallucination_risk", 0.0)),
                            duplicate_score=float(sample.get("duplicate_score", 0.0)),
                            diversity_score=float(sample.get("diversity_score", 0.0)),
                        )
                        submitted += 1
                    except Exception as sub_err:
                        logger.warning("Failed to submit sample for review: %s", sub_err)

                logger.info("Job %s: submitted %d samples for human review (mode=%s)",
                            job_id, submitted, hitl_mode)
            else:
                logger.warning("Job %s: review service not available — skipping submission", job_id)

        # ── Blocking HITL gate ─────────────────────────────────────────
        approved = False
        if hitl_enabled and hitl_mode == "blocking" and review_service is not None:
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
                if hitl_timeout > 0:
                    await asyncio.wait_for(event.wait(), timeout=float(hitl_timeout))
                else:
                    await event.wait()
                approved = True
                logger.info("Job %s resumed after HITL approval", job_id)
            except asyncio.TimeoutError:
                logger.warning("Job %s HITL timeout (%ds) — auto-approving", job_id, hitl_timeout)
                approved = True   # Timeout = auto-approve (configurable behaviour)
        else:
            # async mode or service unavailable — continue without waiting
            approved = True

        return {
            **state,
            "human_approval_needed": hitl_enabled,
            "human_approved": approved,
            "messages": state.get("messages", []) + [
                f"HITL gate: {submitted} samples submitted for review, "
                f"mode={hitl_mode}, approved={approved}"
            ],
        }

    async def _error_handler_node(self, state: AgentState) -> AgentState:
        """Error handling with adaptation suggestions."""
        errors = state.get("errors", [])
        return {
            **state,
            "errors": errors + ["Pipeline error occurred"],
            "should_retry": len(errors) < 3,
            "adaptation_notes": state.get("adaptation_notes", []) + ["Consider relaxing constraints"]
        }

    async def _adapt_strategy_node(self, state: AgentState) -> AgentState:
        """Adapt strategy — always increments retry counter to prevent loops."""
        analysis = state.get("constraint_analysis", {})
        retry_count = state.get("filter_retry_count", 0) + 1

        messages = list(state.get("messages", []))
        notes    = list(state.get("adaptation_notes", []))

        if "quality_budget_conflict" in analysis.get("conflicts", []):
            messages.append("Adapting: reducing quality threshold due to budget constraint")
            notes.append("quality_threshold_lowered")

        messages.append(f"Strategy adaptation #{retry_count} applied")

        return {
            **state,
            "filter_retry_count": retry_count,
            "messages": messages,
            "adaptation_notes": notes,
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
            mode = config.get("generation_mode", "hybrid")
            allow_fallback = config.get("allow_seedless_generation", True)
            
            if mode == "synthetic" or (mode == "hybrid" and allow_fallback):
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

    async def run(self, job: Job) -> dict:
        """Run the pipeline for a job."""
        job_id = job.id
        self.active_jobs[job_id] = job
        self._cancellation_events[job_id] = asyncio.Event()

        initial_state = {
            "job": job.to_dict(),
            "sources": [],
            "extracted_content": [],
            "filtered_samples": [],
            "constructed_samples": [],
            "errors": [],
            "warnings": [],
            "should_retry": False,
            "human_approval_needed": False,
            "human_approved": False,
            "messages": [],
            "current_stage": "pending",
            "progress": 0.0,
            "constraint_analysis": None,
            "low_resource_mode": False,
            "multilingual_mode": False,
            "adaptation_notes": [],
            "filter_retry_count": 0,
            "dataset_plan": None,
            "coverage_matrix": None,
        }
        # Intent extraction - the single source of truth for the request
        try:
            self.intent = await extract_intent(
                raw_input=json.dumps(job.config),
                provider_router=self.router,
                redis_client=getattr(self, 'redis_client', None),
            )
        except IntentExtractionError as e:
            raise e  # will be caught by outer try block


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

                if self.db:
                    try:
                        await self.db.update_job(
                            job_id,
                            status="completed",
                            progress=1.0,
                            current_stage=job.current_stage,
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
                        error_msg += f", 0 filtered (zero-sample situation)"
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
        job.updated_at = datetime.utcnow()
        if error:
            job.error = error
            job.status = JobStatus.FAILED
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
            asyncio.create_task(self._safe_db_update(job_id, db_fields))

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
        """Fire-and-forget DB update with error logging."""
        try:
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