"""LangSmith Observability & Monitoring Integration.

Provides production-grade tracing for dataset generation pipelines, prompt mutations,
LLM calls, and quality scoring evaluations using LangSmith and LangChain tracing.
"""

import os
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Check for LangSmith library
try:
    import langsmith
    from langsmith import Client
    from langsmith.run_trees import RunTree
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    Client = None
    RunTree = None


class LangSmithTracer:
    """Production LangSmith tracer for dataset engineering pipelines."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.endpoint = os.getenv("LANGCHAIN_ENDPOINT") or "https://api.smith.langchain.com"
        self.api_key = api_key or os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
        self.project_name = project_name or os.getenv("LANGCHAIN_PROJECT") or "RasoSynthTune"

        # Explicitly enable if API key is present or explicitly set
        if enabled is not None:
            self.enabled = enabled and LANGSMITH_AVAILABLE
        else:
            self.enabled = bool(self.api_key) and LANGSMITH_AVAILABLE

        self.client: Optional[Client] = None
        self._active_runs: Dict[str, Any] = {}

        if self.enabled:
            try:
                # Set environment variables for LangChain/LangSmith tracing
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_PROJECT"] = self.project_name
                os.environ["LANGCHAIN_ENDPOINT"] = self.endpoint
                if self.api_key:
                    os.environ["LANGCHAIN_API_KEY"] = self.api_key

                self.client = Client(api_url=self.endpoint, api_key=self.api_key)
                logger.info(f"LangSmith Tracer initialized for project '{self.project_name}' at endpoint '{self.endpoint}'")
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith client: {e}")
                self.enabled = False
        else:
            logger.info("LangSmith Tracer running in local mode (LANGCHAIN_API_KEY not configured)")

    def trace_job_start(self, job_id: str, prompt: str, target_domain: str, config: Dict[str, Any]) -> Optional[Any]:
        """Start a top-level pipeline run trace in LangSmith."""
        if not self.enabled or not self.client:
            return None

        try:
            run = RunTree(
                name=f"DatasetGeneration:{target_domain}",
                run_type="chain",
                inputs={"prompt": prompt, "target_domain": target_domain, "config": config},
                project_name=self.project_name,
                extra={"job_id": job_id, "start_time": datetime.utcnow().isoformat()},
            )
            run.post()
            self._active_runs[job_id] = run
            return run
        except Exception as e:
            logger.warning(f"LangSmith trace_job_start error: {e}")
            return None

    def trace_stage(
        self,
        job_id: str,
        stage_name: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        duration_ms: float,
        error: Optional[str] = None,
    ):
        """Trace an individual pipeline stage (e.g. discovery, filtering, construction)."""
        if not self.enabled or not self.client:
            return

        try:
            parent_run = self._active_runs.get(job_id)
            child_run = RunTree(
                name=f"Stage:{stage_name}",
                run_type="tool",
                inputs=inputs,
                outputs=outputs,
                parent_run=parent_run,
                project_name=self.project_name,
                extra={"duration_ms": duration_ms, "error": error},
            )
            child_run.post()
            if parent_run:
                parent_run.child_runs.append(child_run)
        except Exception as e:
            logger.warning(f"LangSmith trace_stage error: {e}")

    def trace_llm_call(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        tokens_used: int = 0,
        latency_ms: float = 0.0,
    ):
        """Trace an individual LLM prompt/response interaction."""
        if not self.enabled or not self.client:
            return

        try:
            run = RunTree(
                name=f"LLMCall:{provider}/{model}",
                run_type="llm",
                inputs={"prompt": prompt, "provider": provider, "model": model},
                outputs={"response": response, "tokens_used": tokens_used},
                project_name=self.project_name,
                extra={"latency_ms": latency_ms},
            )
            run.post()
        except Exception as e:
            logger.warning(f"LangSmith trace_llm_call error: {e}")

    def trace_job_complete(self, job_id: str, samples_count: int, avg_quality: float, details: Dict[str, Any]):
        """Complete and post top-level job trace."""
        if not self.enabled or not self.client:
            return

        try:
            run = self._active_runs.pop(job_id, None)
            if run:
                run.end(outputs={"samples_count": samples_count, "avg_quality": avg_quality, "details": details})
                run.patch()
                logger.info(f"LangSmith trace completed for job {job_id} ({samples_count} samples)")
        except Exception as e:
            logger.warning(f"LangSmith trace_job_complete error: {e}")

    def trace_job_failure(self, job_id: str, error: str):
        """Fail top-level job trace."""
        if not self.enabled or not self.client:
            return

        try:
            run = self._active_runs.pop(job_id, None)
            if run:
                run.end(error=error)
                run.patch()
                logger.info(f"LangSmith trace failed for job {job_id}: {error}")
        except Exception as e:
            logger.warning(f"LangSmith trace_job_failure error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return status and health of the LangSmith tracer."""
        return {
            "available": LANGSMITH_AVAILABLE,
            "enabled": self.enabled,
            "project_name": self.project_name,
            "api_key_configured": bool(self.api_key),
            "active_runs": len(self._active_runs),
        }
