"""Tests for cross-provider AI fallback chain."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai.unified_ai_service import UnifiedAIService, AIResponse, AIMessage
from services.ai.rate_limiter import RateLimitExceededError
from config.ai_providers import AIProvider


class TestCompleteWithFallback:
    """Test cross-provider fallback in UnifiedAIService."""

    @pytest.fixture
    def service(self):
        """Create a UnifiedAIService with mocked adapters."""
        with patch.object(UnifiedAIService, "_initialize_adapters"):
            svc = UnifiedAIService()
            svc._adapters = {}
            return svc

    @pytest.mark.asyncio
    async def test_returns_first_provider_success(self, service):
        """If the first provider succeeds, return its response."""
        service._adapters = {AIProvider.OPENAI: MagicMock()}
        mock_response = AIResponse(
            content="Tax answer", model="gpt-4o", provider=AIProvider.OPENAI,
            input_tokens=10, output_tokens=20, latency_ms=100, cost_estimate=0.001,
        )
        with patch.object(service, "complete", new_callable=AsyncMock, return_value=mock_response):
            result = await service.complete_with_fallback("What deductions?")
            assert result.content == "Tax answer"

    @pytest.mark.asyncio
    async def test_falls_back_on_runtime_error(self, service):
        """If first provider raises RuntimeError, tries next."""
        # Two adapters: first fails, second succeeds
        mock_adapter1 = MagicMock()
        mock_adapter2 = MagicMock()
        service._adapters = {
            AIProvider.OPENAI: mock_adapter1,
            AIProvider.ANTHROPIC: mock_adapter2,
        }

        success_response = AIResponse(
            content="Fallback answer", model="claude", provider=AIProvider.ANTHROPIC,
            input_tokens=5, output_tokens=10, latency_ms=200, cost_estimate=0.002,
        )

        call_count = 0
        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Circuit breaker open")
            return success_response

        with patch.object(service, "complete", side_effect=mock_complete):
            result = await service.complete_with_fallback("Tax question")
            assert result.content == "Fallback answer"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_deterministic_fallback_when_all_fail(self, service):
        """If all providers fail, return deterministic fallback."""
        service._adapters = {AIProvider.OPENAI: MagicMock()}

        with patch.object(service, "complete", new_callable=AsyncMock, side_effect=RuntimeError("down")):
            result = await service.complete_with_fallback(
                "Question",
                deterministic_fallback="Please consult a CPA.",
            )
            assert result.content == "Please consult a CPA."
            assert result.model == "deterministic-fallback"
            assert result.cost_estimate == 0.0

    @pytest.mark.asyncio
    async def test_default_fallback_message(self, service):
        """If no custom fallback, uses default message."""
        service._adapters = {AIProvider.OPENAI: MagicMock()}

        with patch.object(service, "complete", new_callable=AsyncMock, side_effect=RuntimeError("down")):
            result = await service.complete_with_fallback("Question")
            assert "unable to process" in result.content.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_fallback(self, service):
        """RateLimitExceededError triggers fallback to next provider."""
        service._adapters = {AIProvider.OPENAI: MagicMock()}

        with patch.object(
            service, "complete", new_callable=AsyncMock,
            side_effect=RateLimitExceededError("openai", 5.0),
        ):
            result = await service.complete_with_fallback("Question")
            assert result.model == "deterministic-fallback"
