"""Tests for PerplexityAdapter timeout and circuit-breaker behaviour."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config.ai_providers import ProviderConfig
from services.ai.unified_ai_service import (
    AIMessage,
    AIResponse,
    CircuitState,
    PerplexityAdapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> ProviderConfig:
    return ProviderConfig(
        name="perplexity",
        api_key="test-key",
        base_url="https://api.perplexity.ai",
        default_model="llama-3.1-sonar-small-128k-online",
    )


def _make_mock_response(content: str = "Hello from Perplexity") -> MagicMock:
    """Build a mock that looks like an OpenAI ChatCompletion response."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    response.citations = []
    return response


def _patch_client(adapter: PerplexityAdapter, create_coro):
    """Replace the lazy-loaded AsyncOpenAI client with a mock whose
    ``chat.completions.create`` returns *create_coro* (an awaitable)."""
    mock_client = MagicMock()
    mock_client.chat.completions.create = create_coro
    adapter._client = mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_succeeds_within_timeout():
    """complete() returns an AIResponse when the provider responds in time."""
    adapter = PerplexityAdapter(_make_config())

    mock_response = _make_mock_response("Research result")
    create_mock = AsyncMock(return_value=mock_response)
    _patch_client(adapter, create_mock)

    messages = [AIMessage(role="user", content="What is the weather?")]
    result = await adapter.complete(messages)

    assert isinstance(result, AIResponse)
    assert result.content == "Research result"
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_raises_timeout_error_on_slow_provider():
    """complete() raises asyncio.TimeoutError when the provider takes longer
    than the configured timeout (default 30 s)."""
    adapter = PerplexityAdapter(_make_config())

    async def _slow_create(**kwargs):
        await asyncio.sleep(999)  # intentionally way over the timeout
        return _make_mock_response()

    _patch_client(adapter, _slow_create)

    messages = [AIMessage(role="user", content="Slow query")]

    with pytest.raises(asyncio.TimeoutError):
        # Use a very short timeout so the test finishes fast
        await adapter.complete(messages, timeout=0.05)


@pytest.mark.asyncio
async def test_custom_timeout_overrides_default():
    """A custom ``timeout`` kwarg is respected instead of the 30 s default."""
    adapter = PerplexityAdapter(_make_config())

    async def _delayed_create(**kwargs):
        await asyncio.sleep(0.3)
        return _make_mock_response("Delayed but OK")

    _patch_client(adapter, _delayed_create)

    messages = [AIMessage(role="user", content="query")]

    # With a 0.1 s timeout the call should time out …
    with pytest.raises(asyncio.TimeoutError):
        await adapter.complete(messages, timeout=0.1)

    # … but with a 1 s timeout it should succeed.
    result = await adapter.complete(messages, timeout=1.0)
    assert result.content == "Delayed but OK"


@pytest.mark.asyncio
async def test_circuit_breaker_records_failure_on_timeout():
    """The circuit breaker must register a failure when a timeout occurs."""
    adapter = PerplexityAdapter(_make_config())
    assert adapter.circuit_breaker.state == CircuitState.CLOSED
    assert adapter.circuit_breaker.failures == 0

    async def _slow_create(**kwargs):
        await asyncio.sleep(999)
        return _make_mock_response()

    _patch_client(adapter, _slow_create)

    messages = [AIMessage(role="user", content="timeout query")]

    with pytest.raises(asyncio.TimeoutError):
        await adapter.complete(messages, timeout=0.05)

    assert adapter.circuit_breaker.failures == 1
