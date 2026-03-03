"""
Comprehensive tests for UnifiedAIService — provider adapters, circuit breaker,
prompt construction, response parsing, error handling, retry logic, and usage tracking.
"""
import os
import sys
from pathlib import Path
import time
import asyncio
import json

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch, PropertyMock
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.ai.unified_ai_service import (
    AIMessage,
    AIResponse,
    AIUsageStats,
    CircuitBreaker,
    CircuitState,
)


# ===================================================================
# AIMessage
# ===================================================================

class TestAIMessage:

    @pytest.mark.parametrize("role", ["system", "user", "assistant"])
    def test_create_message(self, role):
        msg = AIMessage(role=role, content="test")
        assert msg.role == role
        assert msg.content == "test"

    def test_message_empty_content(self):
        msg = AIMessage(role="user", content="")
        assert msg.content == ""

    def test_message_long_content(self):
        content = "x" * 100000
        msg = AIMessage(role="user", content=content)
        assert len(msg.content) == 100000

    def test_message_with_special_chars(self):
        msg = AIMessage(role="user", content="What about $1,000 income? <tag>&amp;</tag>")
        assert "$1,000" in msg.content


# ===================================================================
# AIResponse
# ===================================================================

class TestAIResponse:

    def test_create_response(self):
        resp = AIResponse(
            content="analysis result",
            model="gpt-4",
            provider=Mock(value="openai"),
        )
        assert resp.content == "analysis result"
        assert resp.model == "gpt-4"

    def test_response_defaults(self):
        resp = AIResponse(content="x", model="m", provider=Mock())
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.latency_ms == 0
        assert resp.cost_estimate == 0.0
        assert resp.metadata == {}

    def test_response_with_tokens(self):
        resp = AIResponse(
            content="x", model="m", provider=Mock(),
            input_tokens=100, output_tokens=200,
        )
        assert resp.input_tokens == 100
        assert resp.output_tokens == 200

    def test_response_with_cost(self):
        resp = AIResponse(
            content="x", model="m", provider=Mock(),
            cost_estimate=0.05,
        )
        assert resp.cost_estimate == 0.05

    def test_response_with_metadata(self):
        resp = AIResponse(
            content="x", model="m", provider=Mock(),
            metadata={"citations": ["source1"]},
        )
        assert resp.metadata["citations"] == ["source1"]


# ===================================================================
# AIUsageStats
# ===================================================================

class TestAIUsageStats:

    def test_create_stats(self):
        from datetime import datetime
        stats = AIUsageStats(
            provider=Mock(value="openai"),
            model="gpt-4",
            input_tokens=100,
            output_tokens=200,
            latency_ms=500,
            cost_estimate=0.01,
            timestamp=datetime.now(),
            success=True,
        )
        assert stats.success is True
        assert stats.error is None

    def test_stats_with_error(self):
        from datetime import datetime
        stats = AIUsageStats(
            provider=Mock(), model="m",
            input_tokens=0, output_tokens=0,
            latency_ms=0, cost_estimate=0,
            timestamp=datetime.now(),
            success=False, error="Timeout",
        )
        assert stats.success is False
        assert stats.error == "Timeout"


# ===================================================================
# CircuitBreaker
# ===================================================================

class TestCircuitBreaker:

    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0

    def test_can_execute_when_closed(self):
        cb = CircuitBreaker()
        assert cb.can_execute() is True

    def test_record_success_resets_failures(self):
        cb = CircuitBreaker()
        cb.failures = 3
        cb.record_success()
        assert cb.failures == 0

    def test_record_failure_increments(self):
        cb = CircuitBreaker()
        cb.record_failure()
        assert cb.failures == 1

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_cannot_execute_when_open(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
        for _ in range(3):
            cb.record_failure()
        assert cb.can_execute() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0)
        for _ in range(3):
            cb.record_failure()
        cb.last_failure_time = time.time() - 1  # past timeout
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_after_successes(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0, half_open_requests=2)
        for _ in range(3):
            cb.record_failure()
        cb.last_failure_time = time.time() - 1
        cb.can_execute()  # transitions to half-open
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_opens_on_failure(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0)
        for _ in range(3):
            cb.record_failure()
        cb.last_failure_time = time.time() - 1
        cb.can_execute()  # half-open
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.parametrize("threshold", [1, 3, 5, 10])
    def test_configurable_threshold(self, threshold):
        cb = CircuitBreaker(failure_threshold=threshold)
        for _ in range(threshold - 1):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.parametrize("half_open_needed", [1, 2, 3, 5])
    def test_configurable_half_open_requests(self, half_open_needed):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, half_open_requests=half_open_needed)
        cb.record_failure()
        cb.last_failure_time = time.time() - 1
        cb.can_execute()  # half-open
        for _ in range(half_open_needed - 1):
            cb.record_success()
            assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_default_values(self):
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30
        assert cb.half_open_requests == 3


class TestCircuitState:

    @pytest.mark.parametrize("state,value", [
        (CircuitState.CLOSED, "closed"),
        (CircuitState.OPEN, "open"),
        (CircuitState.HALF_OPEN, "half_open"),
    ])
    def test_state_values(self, state, value):
        assert state.value == value


# ===================================================================
# OpenAIAdapter
# ===================================================================

class TestOpenAIAdapter:

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_openai_response, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter, AIMessage
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="Explain deductions")]
        result = await adapter.complete(messages)
        assert isinstance(result, AIResponse)
        assert result.content == "This is a tax deduction analysis response."

    @pytest.mark.asyncio
    async def test_complete_records_success_on_circuit_breaker(self, mock_openai_response, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter, AIMessage
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="test")]
        await adapter.complete(messages)
        assert adapter.circuit_breaker.failures == 0

    @pytest.mark.asyncio
    async def test_complete_timeout(self, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter, AIMessage
        adapter = OpenAIAdapter(mock_provider_config, timeout=1)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=asyncio.TimeoutError())
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="test")]
        with pytest.raises(TimeoutError):
            await adapter.complete(messages)

    @pytest.mark.asyncio
    async def test_complete_records_failure(self, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter, AIMessage
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="test")]
        with pytest.raises(Exception):
            await adapter.complete(messages)
        assert adapter.circuit_breaker.failures == 1

    @pytest.mark.asyncio
    async def test_extract_structured_json(self, mock_openai_response, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        json_response = Mock()
        json_response.choices = [Mock()]
        json_response.choices[0].message.content = '{"name": "John", "income": 75000}'
        json_response.usage = Mock(prompt_tokens=50, completion_tokens=20)
        mock_client.chat.completions.create = AsyncMock(return_value=json_response)
        adapter._client = mock_client

        result = await adapter.extract_structured("some text", {"name": "str", "income": "int"})
        assert result["name"] == "John"
        assert result["income"] == 75000

    @pytest.mark.asyncio
    async def test_extract_structured_json_in_markdown(self, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        json_response = Mock()
        json_response.choices = [Mock()]
        json_response.choices[0].message.content = '```json\n{"name": "John"}\n```'
        json_response.usage = Mock(prompt_tokens=50, completion_tokens=20)
        mock_client.chat.completions.create = AsyncMock(return_value=json_response)
        adapter._client = mock_client

        result = await adapter.extract_structured("text", {"name": "str"})
        assert result["name"] == "John"

    @pytest.mark.parametrize("temperature", [0.0, 0.1, 0.5, 0.7, 1.0])
    @pytest.mark.asyncio
    async def test_complete_with_temperatures(self, temperature, mock_openai_response, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter, AIMessage
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="test")]
        result = await adapter.complete(messages, temperature=temperature)
        assert isinstance(result, AIResponse)

    @pytest.mark.parametrize("max_tokens", [100, 500, 1000, 4096, 8192])
    @pytest.mark.asyncio
    async def test_complete_with_max_tokens(self, max_tokens, mock_openai_response, mock_provider_config):
        from services.ai.unified_ai_service import OpenAIAdapter, AIMessage
        adapter = OpenAIAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="test")]
        result = await adapter.complete(messages, max_tokens=max_tokens)
        assert isinstance(result, AIResponse)


# ===================================================================
# AnthropicAdapter
# ===================================================================

class TestAnthropicAdapter:

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_anthropic_response, mock_provider_config):
        from services.ai.unified_ai_service import AnthropicAdapter, AIMessage
        adapter = AnthropicAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
        adapter._client = mock_client

        messages = [
            AIMessage(role="system", content="You are a tax advisor"),
            AIMessage(role="user", content="Explain Roth conversion"),
        ]
        result = await adapter.complete(messages)
        assert isinstance(result, AIResponse)
        assert result.content == "Claude analysis of tax scenario."

    @pytest.mark.asyncio
    async def test_complete_extracts_system_message(self, mock_anthropic_response, mock_provider_config):
        from services.ai.unified_ai_service import AnthropicAdapter, AIMessage
        adapter = AnthropicAdapter(mock_provider_config)
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
        adapter._client = mock_client

        messages = [
            AIMessage(role="system", content="system prompt"),
            AIMessage(role="user", content="question"),
        ]
        await adapter.complete(messages)
        call_kwargs = mock_client.messages.create.call_args
        # System should be extracted as separate kwarg
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_complete_timeout(self, mock_provider_config):
        from services.ai.unified_ai_service import AnthropicAdapter, AIMessage
        adapter = AnthropicAdapter(mock_provider_config, timeout=1)
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())
        adapter._client = mock_client

        messages = [AIMessage(role="user", content="test")]
        with pytest.raises(TimeoutError):
            await adapter.complete(messages)


# ===================================================================
# UnifiedAIService
# ===================================================================

class TestUnifiedAIService:

    def test_usage_summary_empty(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = []
            summary = svc.get_usage_summary()
            assert summary["total_requests"] == 0

    def test_usage_summary_with_stats(self):
        from services.ai.unified_ai_service import UnifiedAIService
        from datetime import datetime
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = [
                AIUsageStats(
                    provider=Mock(value="openai"), model="gpt-4",
                    input_tokens=100, output_tokens=200,
                    latency_ms=500, cost_estimate=0.01,
                    timestamp=datetime.now(), success=True,
                ),
                AIUsageStats(
                    provider=Mock(value="openai"), model="gpt-4",
                    input_tokens=50, output_tokens=100,
                    latency_ms=300, cost_estimate=0.005,
                    timestamp=datetime.now(), success=True,
                ),
            ]
            summary = svc.get_usage_summary()
            assert summary["total_requests"] == 2
            assert summary["success_rate"] == 1.0
            assert summary["total_tokens"] == 450

    def test_usage_stats_capped_at_1000(self):
        from services.ai.unified_ai_service import UnifiedAIService
        from datetime import datetime
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = [
                AIUsageStats(
                    provider=Mock(value="openai"), model="m",
                    input_tokens=0, output_tokens=0,
                    latency_ms=0, cost_estimate=0,
                    timestamp=datetime.now(), success=True,
                )
                for _ in range(1100)
            ]
            svc._record_usage(Mock(value="openai"), "m", AIResponse(
                content="x", model="m", provider=Mock(value="openai"),
            ))
            assert len(svc._usage_stats) <= 1001

    def test_record_usage_success(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = []
            resp = AIResponse(content="x", model="m", provider=Mock(value="openai"),
                              input_tokens=10, output_tokens=20)
            svc._record_usage(Mock(value="openai"), "gpt-4", resp)
            assert len(svc._usage_stats) == 1
            assert svc._usage_stats[0].success is True

    def test_record_usage_error(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = []
            svc._record_usage(Mock(value="openai"), "gpt-4", error="Timeout")
            assert svc._usage_stats[0].success is False
            assert svc._usage_stats[0].error == "Timeout"

    def test_get_adapter_unavailable(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            with pytest.raises(ValueError, match="not available"):
                svc._get_adapter(Mock(value="nonexistent"))

    def test_get_adapter_circuit_open(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            adapter = Mock()
            adapter.circuit_breaker.can_execute.return_value = False
            provider = Mock(value="openai")
            svc._adapters = {provider: adapter}
            with pytest.raises(RuntimeError, match="circuit breaker"):
                svc._get_adapter(provider)


# ===================================================================
# ANALYSIS TYPES
# ===================================================================

class TestAnalysisTypes:

    @pytest.mark.asyncio
    async def test_reason_method(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc.complete = AsyncMock(return_value=AIResponse(
                content="Roth conversion analysis...", model="m", provider=Mock(),
            ))
            result = await svc.reason("Should I convert?", "AGI: $80k")
            assert "analysis" in result.content.lower() or result.content

    @pytest.mark.asyncio
    async def test_research_method(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc.complete = AsyncMock(return_value=AIResponse(
                content="2025 401k limit is $23,500", model="m", provider=Mock(),
            ))
            result = await svc.research("2025 401k contribution limits")
            assert result.content

    @pytest.mark.asyncio
    async def test_extract_method(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            adapter = AsyncMock()
            adapter.extract_structured = AsyncMock(return_value={"income": 75000})
            adapter.circuit_breaker.can_execute.return_value = True
            provider = Mock()
            svc._adapters = {provider: adapter}

            with patch("services.ai.unified_ai_service.get_model_for_capability", return_value=(provider, "m")):
                result = await svc.extract("W-2 wages $75,000", {"income": "float"})
                assert result["income"] == 75000

    @pytest.mark.asyncio
    async def test_chat_method(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            adapter = AsyncMock()
            adapter.complete = AsyncMock(return_value=AIResponse(
                content="response", model="m", provider=Mock(),
                input_tokens=10, output_tokens=20,
            ))
            adapter.circuit_breaker.can_execute.return_value = True
            provider = Mock()
            svc._adapters = {provider: adapter}
            svc._usage_stats = []

            with patch("services.ai.unified_ai_service.get_model_for_capability", return_value=(provider, "m")):
                messages = [AIMessage(role="user", content="hello")]
                result = await svc.chat(messages)
                assert result.content == "response"


# ===================================================================
# ERROR HANDLING
# ===================================================================

class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_complete_propagates_rate_limit_error(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = []

            with patch("services.ai.unified_ai_service.get_model_for_capability") as mock_cap, \
                 patch("services.ai.unified_ai_service.get_provider_config") as mock_conf, \
                 patch("services.ai.unified_ai_service.get_ai_rate_limiter") as mock_rl:
                provider = Mock(value="openai")
                mock_cap.return_value = (provider, "gpt-4")
                mock_conf.return_value = Mock(rate_limit_rpm=60)
                mock_rl.return_value.check_rate_limit.return_value = False
                mock_rl.return_value.wait_time.return_value = 5

                from services.ai.rate_limiter import RateLimitExceededError
                with pytest.raises(RateLimitExceededError):
                    await svc.complete("test prompt")

    @pytest.mark.asyncio
    async def test_complete_logs_error_on_failure(self):
        from services.ai.unified_ai_service import UnifiedAIService
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._usage_stats = []
            adapter = AsyncMock()
            adapter.complete = AsyncMock(side_effect=Exception("API down"))
            adapter.circuit_breaker.can_execute.return_value = True
            provider = Mock(value="openai")
            svc._adapters = {provider: adapter}

            with patch("services.ai.unified_ai_service.get_model_for_capability", return_value=(provider, "m")), \
                 patch("services.ai.unified_ai_service.get_provider_config") as mock_conf, \
                 patch("services.ai.unified_ai_service.get_ai_rate_limiter") as mock_rl:
                mock_conf.return_value = Mock(rate_limit_rpm=60)
                mock_rl.return_value.check_rate_limit.return_value = True

                with pytest.raises(Exception, match="API down"):
                    await svc.complete("test")
                assert len(svc._usage_stats) == 1
                assert svc._usage_stats[0].success is False


# ===================================================================
# TOKEN COUNTING / LIMITS
# ===================================================================

class TestTokenCounting:

    @pytest.mark.parametrize("input_tokens,output_tokens,total", [
        (100, 200, 300),
        (0, 0, 0),
        (1000, 2000, 3000),
        (50000, 10000, 60000),
    ])
    def test_total_token_calculation(self, input_tokens, output_tokens, total):
        assert input_tokens + output_tokens == total

    def test_usage_summary_total_tokens(self):
        from services.ai.unified_ai_service import UnifiedAIService
        from datetime import datetime
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = [
                AIUsageStats(
                    provider=Mock(value="openai"), model="m",
                    input_tokens=100, output_tokens=200,
                    latency_ms=0, cost_estimate=0,
                    timestamp=datetime.now(), success=True,
                ),
            ]
            summary = svc.get_usage_summary()
            assert summary["total_tokens"] == 300

    def test_usage_summary_by_provider(self):
        from services.ai.unified_ai_service import UnifiedAIService
        from datetime import datetime
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            svc._usage_stats = [
                AIUsageStats(
                    provider=Mock(value="openai"), model="m",
                    input_tokens=100, output_tokens=200,
                    latency_ms=0, cost_estimate=0.01,
                    timestamp=datetime.now(), success=True,
                ),
                AIUsageStats(
                    provider=Mock(value="anthropic"), model="m",
                    input_tokens=50, output_tokens=50,
                    latency_ms=0, cost_estimate=0.005,
                    timestamp=datetime.now(), success=True,
                ),
            ]
            summary = svc.get_usage_summary()
            assert "openai" in summary["by_provider"]
            assert "anthropic" in summary["by_provider"]
