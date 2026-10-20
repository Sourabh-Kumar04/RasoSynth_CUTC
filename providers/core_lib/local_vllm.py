"""Local Air-Gapped Synthesis Engine (vLLM & Ollama Provider).

Enables 100% offline, zero-network-egress synthetic data generation for air-gapped
enterprise, banking, and defense environments using local GPU clusters:
1. Native integration with vLLM OpenAI-compatible endpoints (http://localhost:8000/v1).
2. Native integration with local Ollama endpoints (http://localhost:11434/v1).
3. Air-gapped fallback generation for isolated test and disconnected environments.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class LocalInferenceEngine:
    """Client for local vLLM and Ollama instances running on local host or private VPC."""

    def __init__(
        self,
        engine_type: str = "vllm",
        base_url: Optional[str] = None,
        model: str = "sarvamai/sarvam-2b-v0.5",
        timeout_seconds: float = 30.0,
    ):
        self.engine_type = engine_type.lower()
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif self.engine_type == "ollama":
            self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        else:
            self.base_url = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")

        self.model = model
        self.timeout = timeout_seconds

    def is_available(self) -> bool:
        """Check if local endpoint is active and responding."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/models")
                return res.status_code == 200
        except Exception:
            return False

    def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate response via local vLLM/Ollama API with air-gapped fallback."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Try live local endpoint
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return {
                        "content": content,
                        "engine": self.engine_type,
                        "model": self.model,
                        "air_gapped": True,
                        "status": "live_local",
                    }
        except Exception as e:
            logger.debug(f"Local {self.engine_type} endpoint unavailable at {self.base_url}: {e}")

        # Air-gapped deterministic synthesis fallback
        fallback_content = f"Air-gapped local synthetic response for: '{prompt[:60]}...' generated under strict zero-egress data governance."
        return {
            "content": fallback_content,
            "engine": self.engine_type,
            "model": self.model,
            "air_gapped": True,
            "status": "air_gapped_offline",
        }
