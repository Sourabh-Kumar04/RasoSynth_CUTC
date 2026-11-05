"""Preview and planning nodes for DatasetOrchestrator."""
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


class PreviewNodeMixin:
    """Mixin providing early preview, feasibility analysis, query optimization, and planning nodes."""

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
