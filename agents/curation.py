"""Evidence-context and human-arbitration agents for the canonical workflow."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from agents.base import Agent, AgentConfig, AgentContext, AgentState, TaskResult


class ContextAgent(Agent):
    """Build a bounded, de-duplicated evidence pack from extracted documents."""

    async def initialize(self) -> bool:
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        started = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)
        try:
            payload = task if isinstance(task, dict) else {"items": task}
            items = payload.get("items", [])
            max_items = max(1, int(payload.get("max_items", 50)))
            seen: set[str] = set()
            evidence: list[dict] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("content") or item.get("source_text") or "").strip()
                metadata = item.get("metadata") or {}
                url = str(metadata.get("source_url") or item.get("url") or "").strip()
                if not text or not url:
                    continue
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                evidence.append({
                    "source_url": url,
                    "source_hash": digest,
                    "license": metadata.get("license") or item.get("license"),
                    "excerpt": text[:2000],
                    "citations": [{"start": 0, "end": min(len(text), 2000)}],
                })
                if len(evidence) >= max_items:
                    break
            return TaskResult(
                task_id=payload.get("task_id", context.job_id), agent_id=self.agent_id,
                success=True, output={"evidence": evidence, "source_count": len(evidence)},
                confidence=0.95,
                execution_time_ms=(datetime.now(timezone.utc) - started).total_seconds() * 1000,
            )
        except Exception as exc:
            return TaskResult(task_id=context.job_id, agent_id=self.agent_id, success=False, error=str(exc))
        finally:
            self.update_state(AgentState.IDLE)

    async def cleanup(self) -> None:
        self.update_state(AgentState.TERMINATED)


class HumanArbiterAgent(Agent):
    """Routes only uncertain, unsafe, or source-missing samples to human review.

    Samples with NO review score are treated as uncertain and routed to
    review: a missing score must never default to a passing value.
    """

    async def initialize(self) -> bool:
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        started = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)
        try:
            payload = task if isinstance(task, dict) else {"samples": task}
            selected = []
            for sample in payload.get("samples", []):
                if not isinstance(sample, dict):
                    continue
                provenance = (sample.get("metadata") or {}).get("provenance", {})
                # A missing score must NEVER default to 1.0 and sail past
                # review unreviewed: unscored (or unparseable) samples are
                # routed to human review.
                score_raw = sample.get("llm_review_score", sample.get("quality_score"))
                try:
                    score = float(score_raw) if score_raw is not None else None
                except (TypeError, ValueError):
                    score = None
                if sample.get("needs_human_review") or score is None or score < 0.75 or not provenance.get("source_url"):
                    selected.append(sample)
            return TaskResult(
                task_id=payload.get("task_id", context.job_id), agent_id=self.agent_id,
                success=True, output={"review_candidates": selected, "count": len(selected)},
                confidence=0.97,
                execution_time_ms=(datetime.now(timezone.utc) - started).total_seconds() * 1000,
            )
        except Exception as exc:
            return TaskResult(task_id=context.job_id, agent_id=self.agent_id, success=False, error=str(exc))
        finally:
            self.update_state(AgentState.IDLE)

    async def cleanup(self) -> None:
        self.update_state(AgentState.TERMINATED)
