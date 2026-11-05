"""Discovery and content extraction nodes for DatasetOrchestrator."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import operator
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, TypedDict

from core.config import get_settings
from core.intent import IntentExtractionError, UserIntent
from core.intent_extractor import extract_intent
from core.orchestrator_pkg.constraint_analyzer import ConstraintAnalyzer
from core.orchestrator_pkg.state import (
    AgentState,
    Job,
    JobStatus,
    ConstraintAnalysis,
    _sanitize_metadata,
    _json_safe,
)

logger = logging.getLogger(__name__)


class DiscoveryNodeMixin:
    """Mixin providing source discovery, URL relevance checks, and content extraction nodes."""

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
