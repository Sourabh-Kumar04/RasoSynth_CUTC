"""Test Fireworks and Featherless OpenAI-compatible providers."""
import pytest
from providers.core_lib.plugin import PluginRegistry
from providers.fireworks import FireworksProvider
from providers.featherless import FeatherlessProvider
from providers.base_provider import ProviderConfig
from core.provider_router import ProviderRouter


def test_fireworks_provider_registered():
    """Verify Fireworks is registered in PluginRegistry."""
    cls = PluginRegistry.get("fireworks")
    assert cls is not None
    assert cls == FireworksProvider


def test_featherless_provider_registered():
    """Verify Featherless is registered in PluginRegistry."""
    cls = PluginRegistry.get("featherless")
    assert cls is not None
    assert cls == FeatherlessProvider


def test_fireworks_provider_initialization():
    """Test Fireworks provider configuration."""
    provider = FireworksProvider({
        "api_key": "fw_test_key_12345",
        "base_url": "https://api.fireworks.ai/inference/v1",
    })
    assert provider.name == "fireworks"
    assert provider.config.api_key == "fw_test_key_12345"
    assert provider.config.base_url == "https://api.fireworks.ai/inference/v1"
    models = provider.get_models()
    assert len(models) >= 3


def test_featherless_provider_initialization():
    """Test Featherless provider configuration."""
    provider = FeatherlessProvider({
        "api_key": "fl_test_key_67890",
        "base_url": "https://api.featherless.ai/v1",
    })
    assert provider.name == "featherless"
    assert provider.config.api_key == "fl_test_key_67890"
    assert provider.config.base_url == "https://api.featherless.ai/v1"
    models = provider.get_models()
    assert len(models) >= 3


def test_router_detects_fireworks_and_featherless():
    """Test that ProviderRouter detects both keys from config dict."""
    config = {
        "fireworks_api_key": "fw_fake_key",
        "featherless_api_key": "fl_fake_key",
    }
    router = ProviderRouter(config)
    assert "fireworks" in router._providers
    assert "featherless" in router._providers
    assert router._provider_configs["fireworks"]["api_key"] == "fw_fake_key"
    assert router._provider_configs["featherless"]["api_key"] == "fl_fake_key"
