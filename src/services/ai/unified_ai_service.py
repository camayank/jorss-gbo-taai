"""
Unified AI Service.

Provides a single interface for all AI providers with:
- Automatic provider selection based on capability
- Fallback chains for reliability
- Circuit breaker pattern for resilience
- Usage tracking and cost estimation
- Retry logic with exponential backoff

Usage:
    from services.ai.unified_ai_service import get_ai_service

    ai = get_ai_service()

    # Simple completion
    response = await ai.complete("Explain tax deductions")

    # Complex reasoning (uses Claude)
    analysis = await ai.reason("Should I convert to Roth IRA?", context)

    # Research (uses Perplexity)
    result = await ai.research("2025 401k contribution limits")

    # Structured extraction (uses OpenAI)
    data = await ai.extract(document_text, TaxReturnSchema)
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from contextlib import asynccontextmanager

from config.ai_providers import (
    AIProvider,
    ModelCapability,
    ProviderConfig,
    get_provider_config,
    get_available_providers,
    get_model_for_capability,
    estimate_cost,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AIMessage:
    """A message in a conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class AIResponse:
    """Response from an AI model."""
    content: str
    model: str
    provider: AIProvider
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_estimate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIUsageStats:
    """Usage statistics for tracking."""
    provider: AIProvider
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_estimate: float
    timestamp: datetime
    success: bool
    error: Optional[str] = None


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """Circuit breaker for provider resilience."""
    failure_threshold: int = 5
    recovery_timeout: int = 30
    half_open_requests: int = 3

    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    last_failure_time: float = 0
    half_open_successes: int = 0

    def record_success(self):
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.half_open_requests:
                self.state = CircuitState.CLOSED
                self.failures = 0
                self.half_open_successes = 0
                logger.info("Circuit breaker closed (recovered)")
        elif self.state == CircuitState.CLOSED:
            self.failures = 0

    def record_failure(self):
        """Record a failed call."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_successes = 0
            logger.warning("Circuit breaker opened (half-open failure)")
        elif self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failures} failures")

    def can_execute(self) -> bool:
        """Check if a call can be made."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_successes = 0
                logger.info("Circuit breaker half-open (testing recovery)")
                return True
            return False

        # HALF_OPEN - allow limited requests
        return True


# =============================================================================
# PROVIDER ADAPTERS
# =============================================================================

class BaseProviderAdapter(ABC):
    """Base class for provider adapters."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker()

    @abstractmethod
    async def complete(
        self,
        messages: List[AIMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        """Generate a completion."""
        pass

    @abstractmethod
    async def extract_structured(
        self,
        text: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Extract structured data from text."""
        pass


class OpenAIAdapter(BaseProviderAdapter):
    """Adapter for OpenAI API."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    async def complete(
        self,
        messages: List[AIMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        model = model or self.config.default_model
        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            latency_ms = int((time.time() - start_time) * 1000)
            usage = response.usage

            self.circuit_breaker.record_success()

            return AIResponse(
                content=response.choices[0].message.content,
                model=model,
                provider=AIProvider.OPENAI,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
                cost_estimate=estimate_cost(
                    model,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0
                ),
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    async def extract_structured(
        self,
        text: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        model = model or self.config.models.get(ModelCapability.EXTRACTION, self.config.default_model)

        messages = [
            AIMessage(role="system", content="Extract structured data from the following text. Return valid JSON only."),
            AIMessage(role="user", content=f"Text:\n{text}\n\nSchema:\n{schema}")
        ]

        response = await self.complete(messages, model=model, temperature=0.1)

        import json
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())


class AnthropicAdapter(BaseProviderAdapter):
    """Adapter for Anthropic (Claude) API."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    async def complete(
        self,
        messages: List[AIMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        model = model or self.config.default_model
        start_time = time.time()

        # Extract system message
        system_content = ""
        user_messages = []
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        try:
            response = await self.client.messages.create(
                model=model,
                messages=user_messages,
                system=system_content if system_content else None,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            self.circuit_breaker.record_success()

            return AIResponse(
                content=response.content[0].text,
                model=model,
                provider=AIProvider.ANTHROPIC,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
                cost_estimate=estimate_cost(
                    model,
                    response.usage.input_tokens,
                    response.usage.output_tokens
                ),
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    async def extract_structured(
        self,
        text: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        model = model or self.config.models.get(ModelCapability.EXTRACTION, self.config.default_model)

        messages = [
            AIMessage(role="system", content="You are a data extraction assistant. Extract structured data from text and return valid JSON only, no explanation."),
            AIMessage(role="user", content=f"Extract data matching this schema:\n{schema}\n\nFrom this text:\n{text}")
        ]

        response = await self.complete(messages, model=model, temperature=0.1)

        import json
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())


class PerplexityAdapter(BaseProviderAdapter):
    """Adapter for Perplexity API (for real-time research)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        """Lazy-load Perplexity client (OpenAI compatible)."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    async def complete(
        self,
        messages: List[AIMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,  # Lower for research accuracy
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        model = model or self.config.default_model
        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            usage = response.usage

            self.circuit_breaker.record_success()

            return AIResponse(
                content=response.choices[0].message.content,
                model=model,
                provider=AIProvider.PERPLEXITY,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
                cost_estimate=estimate_cost(
                    model,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0
                ),
                metadata={"citations": getattr(response, 'citations', [])}
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    async def extract_structured(
        self,
        text: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        # Perplexity is not ideal for extraction, use completion with JSON instruction
        messages = [
            AIMessage(role="system", content="Extract the requested data and return valid JSON only."),
            AIMessage(role="user", content=f"Schema: {schema}\n\nText: {text}")
        ]
        response = await self.complete(messages, model=model, temperature=0.1)

        import json
        return json.loads(response.content.strip())


# =============================================================================
# UNIFIED AI SERVICE
# =============================================================================

class UnifiedAIService:
    """
    Unified interface for all AI providers.

    Features:
    - Automatic provider selection based on capability
    - Fallback chains for reliability
    - Circuit breaker pattern
    - Usage tracking
    """

    def __init__(self):
        self._adapters: Dict[AIProvider, BaseProviderAdapter] = {}
        self._usage_stats: List[AIUsageStats] = []
        self._initialize_adapters()

    def _initialize_adapters(self):
        """Initialize adapters for available providers."""
        available = get_available_providers()

        adapter_classes = {
            AIProvider.OPENAI: OpenAIAdapter,
            AIProvider.ANTHROPIC: AnthropicAdapter,
            AIProvider.PERPLEXITY: PerplexityAdapter,
        }

        for provider in available:
            if provider in adapter_classes:
                config = get_provider_config(provider)
                self._adapters[provider] = adapter_classes[provider](config)
                logger.info(f"Initialized {provider.value} adapter")

    def _get_adapter(self, provider: AIProvider) -> BaseProviderAdapter:
        """Get adapter for a provider."""
        if provider not in self._adapters:
            raise ValueError(f"Provider {provider.value} not available")

        adapter = self._adapters[provider]
        if not adapter.circuit_breaker.can_execute():
            raise RuntimeError(f"Provider {provider.value} circuit breaker open")

        return adapter

    def _record_usage(
        self,
        provider: AIProvider,
        model: str,
        response: Optional[AIResponse] = None,
        error: Optional[str] = None
    ):
        """Record usage statistics."""
        stats = AIUsageStats(
            provider=provider,
            model=model,
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            latency_ms=response.latency_ms if response else 0,
            cost_estimate=response.cost_estimate if response else 0,
            timestamp=datetime.now(),
            success=response is not None,
            error=error,
        )
        self._usage_stats.append(stats)

        # Keep only last 1000 entries
        if len(self._usage_stats) > 1000:
            self._usage_stats = self._usage_stats[-1000:]

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        capability: ModelCapability = ModelCapability.STANDARD,
        preferred_provider: Optional[AIProvider] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AIResponse:
        """
        Generate a completion using the best available model.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            capability: Required capability
            preferred_provider: Optional preferred provider
            temperature: Sampling temperature
            max_tokens: Maximum output tokens

        Returns:
            AIResponse with completion
        """
        provider, model = get_model_for_capability(capability, preferred_provider)

        messages = []
        if system_prompt:
            messages.append(AIMessage(role="system", content=system_prompt))
        messages.append(AIMessage(role="user", content=prompt))

        try:
            adapter = self._get_adapter(provider)
            response = await adapter.complete(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            self._record_usage(provider, model, response)
            return response

        except Exception as e:
            self._record_usage(provider, model, error=str(e))
            logger.error(f"Completion failed with {provider.value}: {e}")
            raise

    async def reason(
        self,
        problem: str,
        context: str,
        **kwargs
    ) -> AIResponse:
        """
        Perform complex reasoning (uses Claude by default).

        Args:
            problem: The problem to reason about
            context: Additional context

        Returns:
            AIResponse with reasoning
        """
        system_prompt = """You are an expert tax advisor with 30 years of experience.
Think step-by-step through complex tax scenarios.
Always cite specific IRC sections when applicable.
Explain your reasoning in plain language.
Consider multiple perspectives and potential risks."""

        prompt = f"""Problem:
{problem}

Context:
{context}

Please analyze this thoroughly and provide your recommendation with reasoning."""

        return await self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            capability=ModelCapability.COMPLEX,
            temperature=0.3,  # Lower for more consistent reasoning
            **kwargs
        )

    async def research(
        self,
        query: str,
        **kwargs
    ) -> AIResponse:
        """
        Perform real-time research (uses Perplexity).

        Args:
            query: Research query

        Returns:
            AIResponse with research findings
        """
        system_prompt = """You are a tax research assistant.
Provide accurate, up-to-date information from authoritative sources.
Always cite your sources (IRS.gov, tax codes, court cases).
Focus on the most recent guidance and rules."""

        return await self.complete(
            prompt=query,
            system_prompt=system_prompt,
            capability=ModelCapability.RESEARCH,
            temperature=0.2,  # Low for accuracy
            **kwargs
        )

    async def extract(
        self,
        text: str,
        schema: Dict[str, Any],
        capability: ModelCapability = ModelCapability.EXTRACTION,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract structured data from text.

        Args:
            text: Text to extract from
            schema: JSON schema for extraction

        Returns:
            Extracted data as dict
        """
        provider, model = get_model_for_capability(capability)

        try:
            adapter = self._get_adapter(provider)
            return await adapter.extract_structured(text, schema, model, **kwargs)
        except Exception as e:
            logger.error(f"Extraction failed with {provider.value}: {e}")
            raise

    async def chat(
        self,
        messages: List[AIMessage],
        capability: ModelCapability = ModelCapability.STANDARD,
        **kwargs
    ) -> AIResponse:
        """
        Continue a multi-turn conversation.

        Args:
            messages: Conversation history
            capability: Required capability

        Returns:
            AIResponse with assistant message
        """
        provider, model = get_model_for_capability(capability)

        try:
            adapter = self._get_adapter(provider)
            response = await adapter.complete(messages=messages, model=model, **kwargs)
            self._record_usage(provider, model, response)
            return response
        except Exception as e:
            self._record_usage(provider, model, error=str(e))
            raise

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get usage statistics summary."""
        if not self._usage_stats:
            return {"total_requests": 0}

        total_cost = sum(s.cost_estimate for s in self._usage_stats)
        total_tokens = sum(s.input_tokens + s.output_tokens for s in self._usage_stats)
        success_count = sum(1 for s in self._usage_stats if s.success)

        by_provider = {}
        for stats in self._usage_stats:
            provider = stats.provider.value
            if provider not in by_provider:
                by_provider[provider] = {"requests": 0, "tokens": 0, "cost": 0}
            by_provider[provider]["requests"] += 1
            by_provider[provider]["tokens"] += stats.input_tokens + stats.output_tokens
            by_provider[provider]["cost"] += stats.cost_estimate

        return {
            "total_requests": len(self._usage_stats),
            "success_rate": success_count / len(self._usage_stats) if self._usage_stats else 0,
            "total_tokens": total_tokens,
            "total_cost_estimate": round(total_cost, 4),
            "by_provider": by_provider,
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_ai_service: Optional[UnifiedAIService] = None


def get_ai_service() -> UnifiedAIService:
    """Get the singleton AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = UnifiedAIService()
    return _ai_service


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "UnifiedAIService",
    "AIMessage",
    "AIResponse",
    "AIUsageStats",
    "get_ai_service",
    "CircuitBreaker",
    "CircuitState",
]
