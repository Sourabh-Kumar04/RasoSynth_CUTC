"""
Provider Migration Adapter

Handles adaptation of prompts, payloads, and responses
between different providers during migration.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderCapability(Enum):
    """Extended provider capabilities for migration."""
    # Generation capabilities
    TEXT_GENERATION = "text_generation"
    TEXT_EMBEDDING = "text_embedding"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    TOOL_CALLING = "tool_calling"

    # Format capabilities
    JSON_MODE = "json_mode"
    STRUCTURED_OUTPUT = "structured_output"
    MARKDOWN = "markdown"

    # Performance capabilities
    LONG_CONTEXT = "long_context"
    FAST_INFERENCE = "fast_inference"
    REASONING = "reasoning"

    # Deployment capabilities
    LOCAL_INFERENCE = "local_inference"
    STREAMING = "streaming"
    EMBEDDING_COMPATIBLE = "embedding_compatible"


@dataclass
class ProviderSpec:
    """Specification for a provider's capabilities."""
    name: str
    capabilities: List[ProviderCapability]
    max_context_tokens: int = 128000
    max_output_tokens: int = 4096
    supports_streaming: bool = True
    supports_json: bool = True
    supports_vision: bool = False
    supports_tools: bool = False


# Provider specifications (would be loaded from config in production)
PROVIDER_SPECS = {
    "google_gemini": ProviderSpec(
        name="google_gemini",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.VISION,
            ProviderCapability.JSON_MODE,
            ProviderCapability.LONG_CONTEXT,
            ProviderCapability.STREAMING,
        ],
        max_context_tokens=128000,
        max_output_tokens=8192,
        supports_streaming=True,
        supports_json=True,
        supports_vision=True,
    ),
    "anthropic_claude": ProviderSpec(
        name="anthropic_claude",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.JSON_MODE,
            ProviderCapability.LONG_CONTEXT,
            ProviderCapability.REASONING,
        ],
        max_context_tokens=200000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_json=True,
    ),
    "openai": ProviderSpec(
        name="openai",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.FUNCTION_CALLING,
            ProviderCapability.JSON_MODE,
            ProviderCapability.STREAMING,
        ],
        max_context_tokens=128000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_json=True,
        supports_tools=True,
    ),
    "deepseek": ProviderSpec(
        name="deepseek",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.REASONING,
            ProviderCapability.JSON_MODE,
        ],
        max_context_tokens=64000,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_json=True,
    ),
    "groq": ProviderSpec(
        name="groq",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.FAST_INFERENCE,
        ],
        max_context_tokens=32768,
        max_output_tokens=4096,
        supports_streaming=True,
    ),
    "ollama": ProviderSpec(
        name="ollama",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.LOCAL_INFERENCE,
        ],
        max_context_tokens=8192,
        max_output_tokens=4096,
        supports_streaming=True,
        supports_json=False,
    ),
    "vllm": ProviderSpec(
        name="vllm",
        capabilities=[
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.LOCAL_INFERENCE,
            ProviderCapability.STREAMING,
        ],
        max_context_tokens=32768,
        max_output_tokens=4096,
        supports_streaming=True,
    ),
}


class ProviderMigrationAdapter:
    """
    Adapts between providers during migration.

    Handles:
    - Prompt adaptation for different capabilities
    - Response format conversion
    - Context length adjustment
    - Tool/function calling adaptation
    """

    def __init__(self):
        self.provider_specs = PROVIDER_SPECS

    def get_provider_spec(self, provider: str) -> ProviderSpec:
        """Get specification for a provider."""
        return self.provider_specs.get(provider, ProviderSpec(
            name=provider,
            capabilities=[ProviderCapability.TEXT_GENERATION]
        ))

    async def adapt_prompt(
        self,
        prompt: str,
        from_provider: str,
        to_provider: str,
    ) -> str:
        """
        Adapt prompt for target provider.

        Handles:
        - Tool calling syntax differences
        - JSON mode requirements
        - Context limits
        """

        from_spec = self.get_provider_spec(from_provider)
        to_spec = self.get_provider_spec(to_provider)

        adapted_prompt = prompt

        # If target doesn't support tools but source did, convert to regular text
        if ProviderCapability.FUNCTION_CALLING not in to_spec.capabilities:
            if ProviderCapability.FUNCTION_CALLING in from_spec.capabilities:
                # Remove tool calls from prompt
                adapted_prompt = self._remove_tool_calls(prompt)

        # If target has smaller context, may need to truncate
        if to_spec.max_context_tokens < from_spec.max_context_tokens:
            # Estimate tokens (rough: 4 chars per token)
            estimated_tokens = len(prompt) // 4
            if estimated_tokens > to_spec.max_context_tokens * 0.8:
                # Truncate to 80% of max to leave room for output
                max_chars = int(to_spec.max_context_tokens * 0.8 * 4)
                adapted_prompt = prompt[:max_chars] + "\n\n[Truncated for provider limits]"

        # Add JSON mode wrapper if needed
        if ProviderCapability.JSON_MODE in to_spec.capabilities:
            if not self._is_json_mode(prompt):
                adapted_prompt = f"Respond in JSON format:\n{prompt}"

        logger.info(f"Adapted prompt: {from_provider} -> {to_provider}")
        return adapted_prompt

    def adapt_response(
        self,
        response: str,
        from_provider: str,
        to_provider: str,
        expected_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Adapt response from source provider format to expected format.

        Handles:
        - JSON parsing differences
        - Structured output differences
        - Markdown vs plain text
        """

        from_spec = self.get_provider_spec(from_provider)
        to_spec = self.get_provider_spec(to_provider)

        # Try to parse as JSON if target expects JSON
        if expected_format == "json":
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown
                extracted = self._extract_json_from_text(response)
                if extracted:
                    return extracted
                # Fallback: wrap in basic structure
                return {"content": response}

        # If target is non-JSON but source was JSON, extract text
        if ProviderCapability.JSON_MODE not in to_spec.capabilities:
            if self._is_json_like(response):
                return {"content": self._strip_json_wrapper(response)}

        return {"content": response, "raw": response}

    async def adapt_outputs(
        self,
        existing_outputs: Dict[str, Any],
        from_provider: str,
        to_provider: str,
    ) -> Dict[str, Any]:
        """
        Adapt all outputs when migrating providers.

        Preserves:
        - Extracted content (re-process if needed)
        - Generated samples (usually compatible)
        - Embeddings (may need recomputation)
        """

        adapted = {
            "extracted_content": existing_outputs.get("extracted_content", []),
            "filtered_samples": existing_outputs.get("filtered_samples", []),
            "constructed_samples": existing_outputs.get("constructed_samples", []),
            "metadata": existing_outputs.get("metadata", {}),
        }

        from_spec = self.get_provider_spec(from_provider)
        to_spec = self.get_provider_spec(to_provider)

        # Handle embedding incompatibility
        if ProviderCapability.TEXT_EMBEDDING not in to_spec.capabilities:
            # Mark embeddings as needing regeneration
            adapted["metadata"]["embeddings_need_regen"] = True
            adapted["metadata"]["original_embedding_provider"] = from_provider

        # Handle multimodal content
        if ProviderCapability.VISION not in to_spec.capabilities:
            # Remove image references that target can't process
            adapted["extracted_content"] = self._remove_vision_references(
                adapted["extracted_content"]
            )

        # Preserve construction samples (usually text-based, compatible)
        # Preserve filtered samples

        logger.info(f"Adapted outputs: {from_provider} -> {to_provider}")
        return adapted

    def check_capability_compatibility(
        self,
        from_provider: str,
        to_provider: str,
        required_capabilities: List[ProviderCapability],
    ) -> Dict[str, Any]:
        """Check if target provider supports required capabilities."""

        from_spec = self.get_provider_spec(from_provider)
        to_spec = self.get_provider_spec(to_provider)

        missing = []
        for cap in required_capabilities:
            if cap not in to_spec.capabilities:
                missing.append(cap.value)

        return {
            "compatible": len(missing) == 0,
            "missing_capabilities": missing,
            "from_provider": from_provider,
            "to_provider": to_provider,
        }

    # Helper methods

    def _remove_tool_calls(self, prompt: str) -> str:
        """Remove tool call formatting from prompt."""
        # Simple removal - would need more robust parsing in production
        import re
        # Remove function definitions and calls
        prompt = re.sub(r'Function:[\s\S]*?Arguments:', '', prompt)
        prompt = re.sub(r'<function=[\s\S]*?</function_call>', '', prompt)
        return prompt

    def _is_json_mode(self, text: str) -> bool:
        """Check if prompt already expects JSON."""
        text_lower = text.lower()
        return 'json' in text_lower or 'respond in json' in text_lower

    def _is_json_like(self, text: str) -> bool:
        """Check if text looks like JSON."""
        text = text.strip()
        return (text.startswith('{') and text.endswith('}')) or \
               (text.startswith('[') and text.endswith(']'))

    def _extract_json_from_text(self, text: str) -> Optional[Dict]:
        """Extract JSON from markdown code blocks."""
        import re
        # Look for ```json blocks
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass

        # Look for first { and last }
        start = text.find('{')
        if start >= 0:
            end = text.rfind('}')
            if end > start:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass
        return None

    def _strip_json_wrapper(self, text: str) -> str:
        """Strip JSON formatting to get raw content."""
        # If wrapped in markdown, extract content
        if text.startswith('```'):
            lines = text.split('\n')
            return '\n'.join(lines[1:-1])
        return text

    def _remove_vision_references(self, content: List[Dict]) -> List[Dict]:
        """Remove or mark image references that target can't process."""
        for item in content:
            if isinstance(item, dict):
                if "image_url" in item:
                    item["image_url"] = "[Image - cannot process]"
                if "image_urls" in item:
                    item["image_urls"] = ["[Images - cannot process]"]
        return content


class ProviderRegistryExtended:
    """
    Extended provider registry with capability tracking.
    """

    def __init__(self):
        self.providers: Dict[str, ProviderSpec] = self.provider_specs

    def register_provider(self, name: str, spec: ProviderSpec) -> None:
        """Register a new provider."""
        self.providers[name] = spec

    def get_capabilities(self, provider: str) -> List[ProviderCapability]:
        """Get provider capabilities."""
        spec = self.providers.get(provider)
        return spec.capabilities if spec else []

    def find_providers_with_capability(
        self,
        capability: ProviderCapability
    ) -> List[str]:
        """Find all providers with a specific capability."""
        return [
            name for name, spec in self.providers.items()
            if capability in spec.capabilities
        ]

    def get_fallback_chain(
        self,
        primary: str,
        required_capabilities: List[ProviderCapability],
    ) -> List[str]:
        """Get fallback chain sorted by capability match."""
        from_spec = self.providers.get(primary)
        if not from_spec:
            return []

        # Find all providers with required capabilities
        candidates = []
        for name, spec in self.providers.items():
            if name == primary:
                continue
            # Check if has all required
            if all(cap in spec.capabilities for cap in required_capabilities):
                # Score by similarity to primary
                score = len(set(from_spec.capabilities) & set(spec.capabilities))
                candidates.append((name, score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates]