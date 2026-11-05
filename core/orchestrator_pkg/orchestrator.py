"""Canonical DatasetOrchestrator execution engine."""
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

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

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
from core.orchestrator_pkg.nodes.preview import PreviewNodeMixin
from core.orchestrator_pkg.nodes.discovery import DiscoveryNodeMixin
from core.orchestrator_pkg.nodes.synthesis import SynthesisNodeMixin
from core.orchestrator_pkg.nodes.evaluation import EvaluationNodeMixin
from core.orchestrator_pkg.nodes.export import ExportNodeMixin
from core.orchestrator_pkg.nodes.resilience import ResilienceNodeMixin

logger = logging.getLogger(__name__)


class DatasetOrchestrator(
    PreviewNodeMixin,
    DiscoveryNodeMixin,
    SynthesisNodeMixin,
    EvaluationNodeMixin,
    ExportNodeMixin,
    ResilienceNodeMixin,
):
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
