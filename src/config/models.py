"""
Configurable AI Model Versions

Model versions default to hardcoded values but can be overridden
via environment variables: AI_MODEL_{PROVIDER}_{CAPABILITY}

Example:
    AI_MODEL_ANTHROPIC_STANDARD=claude-sonnet-4-20260101
    AI_MODEL_OPENAI_FAST=gpt-4o-mini-2025-01
"""

import os
from typing import Optional

# Defaults — same values previously hardcoded in ai_providers.py
_DEFAULTS = {
    "openai": {
        "fast": "gpt-4o-mini",
        "standard": "gpt-4o",
        "complex": "gpt-4o",
        "extraction": "gpt-4o",
        "embeddings": "text-embedding-3-large",
        "multimodal": "gpt-4o",
    },
    "anthropic": {
        "fast": "claude-haiku-4-5-20251001",
        "standard": "claude-sonnet-4-6",
        "complex": "claude-opus-4-6",
        "extraction": "claude-sonnet-4-6",
    },
    "google": {
        "fast": "gemini-1.5-flash",
        "standard": "gemini-1.5-pro",
        "complex": "gemini-1.5-pro",
        "multimodal": "gemini-1.5-pro",
    },
    "perplexity": {
        "research": "llama-3.1-sonar-large-128k-online",
        "fast": "llama-3.1-sonar-small-128k-online",
    },
}


def get_model_version(provider: str, capability: str) -> Optional[str]:
    """Get model version — env var override > default.

    Env var format: AI_MODEL_{PROVIDER}_{CAPABILITY}
    Example: AI_MODEL_ANTHROPIC_STANDARD=claude-sonnet-4-20260101
    """
    env_key = f"AI_MODEL_{provider.upper()}_{capability.upper()}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    provider_defaults = _DEFAULTS.get(provider.lower())
    if provider_defaults is None:
        return None
    return provider_defaults.get(capability.lower())
