"""
AI Provider Configuration Module.

Centralizes configuration for all AI providers:
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude Opus, Sonnet, Haiku)
- Google (Gemini 1.5 Pro, Flash)
- Perplexity (Sonar for real-time research)

Usage:
    from config.ai_providers import get_provider_config, AIProvider

    config = get_provider_config(AIProvider.ANTHROPIC)
    api_key = config.api_key
    model = config.models["complex"]
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from functools import lru_cache

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    PERPLEXITY = "perplexity"


class ModelCapability(str, Enum):
    """Model capability categories for routing."""
    FAST = "fast"              # Quick responses, lower cost
    STANDARD = "standard"      # Balanced performance
    COMPLEX = "complex"        # Complex reasoning
    EXTRACTION = "extraction"  # Structured data extraction
    EMBEDDINGS = "embeddings"  # Vector embeddings
    MULTIMODAL = "multimodal"  # Image/document processing
    RESEARCH = "research"      # Real-time web research


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    name: str
    api_key: Optional[str]
    base_url: Optional[str] = None
    models: Dict[str, str] = field(default_factory=dict)
    default_model: str = ""
    is_available: bool = False
    rate_limit_rpm: int = 60  # Requests per minute
    rate_limit_tpm: int = 100000  # Tokens per minute
    timeout_seconds: int = 60
    max_retries: int = 3

    def __post_init__(self):
        """Determine availability based on API key presence."""
        self.is_available = bool(self.api_key)
        if not self.default_model and self.models:
            self.default_model = list(self.models.values())[0]


# =============================================================================
# PROVIDER CONFIGURATIONS
# =============================================================================

def _get_openai_config() -> ProviderConfig:
    """Get OpenAI provider configuration."""
    return ProviderConfig(
        name="openai",
        api_key=os.environ.get("OPENAI_API_KEY"),
        models={
            ModelCapability.FAST: "gpt-4o-mini",
            ModelCapability.STANDARD: "gpt-4o",
            ModelCapability.COMPLEX: "gpt-4o",
            ModelCapability.EXTRACTION: "gpt-4o",
            ModelCapability.EMBEDDINGS: "text-embedding-3-large",
            ModelCapability.MULTIMODAL: "gpt-4o",
        },
        default_model="gpt-4o",
        rate_limit_rpm=500,
        rate_limit_tpm=200000,
        timeout_seconds=60,
    )


def _get_anthropic_config() -> ProviderConfig:
    """Get Anthropic (Claude) provider configuration."""
    return ProviderConfig(
        name="anthropic",
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        models={
            ModelCapability.FAST: "claude-3-5-haiku-20241022",
            ModelCapability.STANDARD: "claude-sonnet-4-20250514",
            ModelCapability.COMPLEX: "claude-opus-4-20250514",
            ModelCapability.EXTRACTION: "claude-sonnet-4-20250514",
        },
        default_model="claude-sonnet-4-20250514",
        rate_limit_rpm=60,
        rate_limit_tpm=100000,
        timeout_seconds=120,  # Claude can take longer for complex tasks
    )


def _get_google_config() -> ProviderConfig:
    """Get Google (Gemini) provider configuration."""
    return ProviderConfig(
        name="google",
        api_key=os.environ.get("GOOGLE_API_KEY"),
        models={
            ModelCapability.FAST: "gemini-1.5-flash",
            ModelCapability.STANDARD: "gemini-1.5-pro",
            ModelCapability.COMPLEX: "gemini-1.5-pro",
            ModelCapability.MULTIMODAL: "gemini-1.5-pro",
        },
        default_model="gemini-1.5-pro",
        rate_limit_rpm=60,
        rate_limit_tpm=1000000,  # Gemini has large context
        timeout_seconds=90,
    )


def _get_perplexity_config() -> ProviderConfig:
    """Get Perplexity provider configuration."""
    return ProviderConfig(
        name="perplexity",
        api_key=os.environ.get("PERPLEXITY_API_KEY"),
        base_url="https://api.perplexity.ai",
        models={
            ModelCapability.RESEARCH: "llama-3.1-sonar-large-128k-online",
            ModelCapability.FAST: "llama-3.1-sonar-small-128k-online",
        },
        default_model="llama-3.1-sonar-large-128k-online",
        rate_limit_rpm=20,  # Perplexity has lower rate limits
        rate_limit_tpm=50000,
        timeout_seconds=30,
    )


# =============================================================================
# CONFIGURATION ACCESS
# =============================================================================

_provider_configs: Dict[AIProvider, ProviderConfig] = {}


@lru_cache(maxsize=1)
def _load_all_configs() -> Dict[AIProvider, ProviderConfig]:
    """Load all provider configurations (cached)."""
    return {
        AIProvider.OPENAI: _get_openai_config(),
        AIProvider.ANTHROPIC: _get_anthropic_config(),
        AIProvider.GOOGLE: _get_google_config(),
        AIProvider.PERPLEXITY: _get_perplexity_config(),
    }


def get_provider_config(provider: AIProvider) -> ProviderConfig:
    """
    Get configuration for a specific provider.

    Args:
        provider: The AI provider to get config for

    Returns:
        ProviderConfig for the specified provider
    """
    configs = _load_all_configs()
    return configs[provider]


def get_available_providers() -> List[AIProvider]:
    """
    Get list of providers that have API keys configured.

    Returns:
        List of available AIProvider enums
    """
    configs = _load_all_configs()
    return [p for p, c in configs.items() if c.is_available]


def get_model_for_capability(
    capability: ModelCapability,
    preferred_provider: Optional[AIProvider] = None
) -> tuple[AIProvider, str]:
    """
    Get the best available model for a capability.

    Args:
        capability: The capability needed
        preferred_provider: Optional preferred provider

    Returns:
        Tuple of (provider, model_name)

    Raises:
        ValueError: If no provider available for capability
    """
    configs = _load_all_configs()

    # Try preferred provider first
    if preferred_provider:
        config = configs[preferred_provider]
        if config.is_available and capability in config.models:
            return preferred_provider, config.models[capability]

    # Provider priority by capability
    priority_map = {
        ModelCapability.COMPLEX: [AIProvider.ANTHROPIC, AIProvider.OPENAI, AIProvider.GOOGLE],
        ModelCapability.EXTRACTION: [AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.GOOGLE],
        ModelCapability.FAST: [AIProvider.OPENAI, AIProvider.GOOGLE, AIProvider.ANTHROPIC],
        ModelCapability.MULTIMODAL: [AIProvider.GOOGLE, AIProvider.OPENAI],
        ModelCapability.RESEARCH: [AIProvider.PERPLEXITY],
        ModelCapability.EMBEDDINGS: [AIProvider.OPENAI],
        ModelCapability.STANDARD: [AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.GOOGLE],
    }

    priority = priority_map.get(capability, list(AIProvider))

    for provider in priority:
        config = configs[provider]
        if config.is_available and capability in config.models:
            return provider, config.models[capability]

    raise ValueError(f"No provider available for capability: {capability}")


def validate_ai_configuration() -> Dict[str, any]:
    """
    Validate AI provider configuration.

    Returns:
        Dict with validation results for each provider
    """
    configs = _load_all_configs()
    results = {}

    for provider, config in configs.items():
        results[provider.value] = {
            "available": config.is_available,
            "api_key_set": bool(config.api_key),
            "models": list(config.models.keys()) if config.is_available else [],
            "default_model": config.default_model if config.is_available else None,
        }

    # Check minimum requirements
    available = get_available_providers()
    results["_summary"] = {
        "total_available": len(available),
        "providers": [p.value for p in available],
        "has_minimum": AIProvider.OPENAI in available,  # OpenAI is minimum requirement
        "recommendations": [],
    }

    if AIProvider.OPENAI not in available:
        results["_summary"]["recommendations"].append(
            "CRITICAL: Set OPENAI_API_KEY for basic AI functionality"
        )
    if AIProvider.ANTHROPIC not in available:
        results["_summary"]["recommendations"].append(
            "Recommended: Set ANTHROPIC_API_KEY for complex tax reasoning"
        )
    if AIProvider.PERPLEXITY not in available:
        results["_summary"]["recommendations"].append(
            "Recommended: Set PERPLEXITY_API_KEY for real-time tax research"
        )

    return results


# =============================================================================
# COST ESTIMATION
# =============================================================================

# Approximate costs per 1K tokens (input/output)
COST_PER_1K_TOKENS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "llama-3.1-sonar-large-128k-online": {"input": 0.001, "output": 0.001},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost for a model invocation.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    if model not in COST_PER_1K_TOKENS:
        return 0.0

    costs = COST_PER_1K_TOKENS[model]
    input_cost = (input_tokens / 1000) * costs["input"]
    output_cost = (output_tokens / 1000) * costs["output"]

    return input_cost + output_cost


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AIProvider",
    "ModelCapability",
    "ProviderConfig",
    "get_provider_config",
    "get_available_providers",
    "get_model_for_capability",
    "validate_ai_configuration",
    "estimate_cost",
    "COST_PER_1K_TOKENS",
]
