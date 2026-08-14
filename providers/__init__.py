"""
Provider Routing & Orchestration System

Consolidated provider loading. Flat provider files register themselves
via @PluginRegistry.register decorators. Subdirectory wrappers and the
separate routing system have been removed.

Canonical router: core/provider_router.py
Canonical base types: providers/core_lib/base.py
Canonical plugin registry: providers/core_lib/plugin.py
"""

import logging
logger = logging.getLogger(__name__)

# Import core plugin registry and types
from providers.core_lib.plugin import PluginRegistry

# Import newly added providers (wrapped in try/except for optional deps)
try:
    from providers.deepseek import DeepSeekProvider
    from providers.groq import GroqProvider
    from providers.openrouter import OpenRouterProvider
    from providers.together import TogetherProvider
    NEW_PROVIDERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Some new providers not available: {e}")
    NEW_PROVIDERS_AVAILABLE = False
    DeepSeekProvider = None
    GroqProvider = None
    OpenRouterProvider = None
    TogetherProvider = None

# Register new providers (they don't have flat-file equivalents with decorators)
if NEW_PROVIDERS_AVAILABLE:
    if DeepSeekProvider:
        PluginRegistry.register("deepseek")(DeepSeekProvider)
    if GroqProvider:
        PluginRegistry.register("groq")(GroqProvider)
    if OpenRouterProvider:
        PluginRegistry.register("openrouter")(OpenRouterProvider)
    if TogetherProvider:
        PluginRegistry.register("together")(TogetherProvider)
    logger.info("Registered new providers: DeepSeek, Groq, OpenRouter, Together AI")

# Import flat provider files — their @PluginRegistry.register() decorators
# register each provider with the PluginRegistry at import time.
import providers.google_gemini  # noqa: F401, E402
import providers.anthropic_claude  # noqa: F401, E402
import providers.openai_provider  # noqa: F401, E402
import providers.nvidia_nim  # noqa: F401, E402
import providers.huggingface_provider  # noqa: F401, E402
import providers.ollama_provider  # noqa: F401, E402
import providers.xai_provider  # noqa: F401, E402
logger.info("Provider plugins imported and registered via @PluginRegistry.register")

__all__ = [
    "PluginRegistry",
]