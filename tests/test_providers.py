"""Tests for provider implementations."""
import pytest
from providers.base_provider import BaseProvider, ProviderConfig, ModelResponse, EmbeddingResponse


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        return ModelResponse(
            content="Mock response",
            model="mock-model",
            tokens_used=10,
            latency_ms=100,
            cost=0.001,
            provider="mock"
        )

    async def embed(self, text: str, **kwargs) -> EmbeddingResponse:
        return EmbeddingResponse(
            embedding=[0.1, 0.2, 0.3],
            model="mock-embed",
            tokens_used=5,
            provider="mock"
        )


def test_provider_config():
    """Test provider configuration."""
    config = ProviderConfig(
        api_key="test-key",
        max_tokens=2048,
        rate_limit_rpm=100
    )

    assert config.api_key == "test-key"
    assert config.max_tokens == 2048
    assert config.rate_limit_rpm == 100


def test_model_response():
    """Test model response structure."""
    response = ModelResponse(
        content="Test content",
        model="test-model",
        tokens_used=100,
        latency_ms=500,
        cost=0.01,
        provider="test"
    )

    assert response.content == "Test content"
    assert response.tokens_used == 100
    assert response.cost == 0.01


def test_embedding_response():
    """Test embedding response structure."""
    response = EmbeddingResponse(
        embedding=[0.1, 0.2, 0.3],
        model="embed-model",
        tokens_used=50,
        provider="test"
    )

    assert len(response.embedding) == 3
    assert response.model == "embed-model"


@pytest.mark.asyncio
async def test_mock_provider_generate():
    """Test mock provider generation."""
    config = ProviderConfig(api_key="test")
    provider = MockProvider(config, "mock")

    response = await provider.generate("Test prompt")

    assert response.content == "Mock response"
    assert response.provider == "mock"


@pytest.mark.asyncio
async def test_mock_provider_embed():
    """Test mock provider embedding."""
    config = ProviderConfig(api_key="test")
    provider = MockProvider(config, "mock")

    response = await provider.embed("Test text")

    assert len(response.embedding) == 3
    assert response.provider == "mock"


def test_provider_stats():
    """Test provider statistics."""
    config = ProviderConfig(api_key="test")
    provider = MockProvider(config, "mock")

    stats = provider.get_stats()

    assert stats["name"] == "mock"
    assert stats["request_count"] == 0