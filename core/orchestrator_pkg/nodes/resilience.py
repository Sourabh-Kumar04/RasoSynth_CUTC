"""Resilience, error handling, and adaptive strategy nodes for DatasetOrchestrator."""
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


class ResilienceNodeMixin:
    """Mixin providing error handling, dynamic fallback adaptation, and threshold evaluation."""

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
