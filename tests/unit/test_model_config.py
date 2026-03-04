"""Tests for configurable AI model versions."""

import os
import pytest
from unittest.mock import patch
from config.models import get_model_version


class TestModelConfig:
    """Model versions are configurable via environment variables."""

    def test_default_openai_models(self):
        assert get_model_version("openai", "fast") == "gpt-4o-mini"
        assert get_model_version("openai", "standard") == "gpt-4o"

    def test_default_anthropic_models(self):
        assert get_model_version("anthropic", "complex") == "claude-opus-4-20250514"
        assert get_model_version("anthropic", "standard") == "claude-sonnet-4-20250514"

    def test_env_var_override(self):
        with patch.dict(os.environ, {"AI_MODEL_ANTHROPIC_STANDARD": "claude-sonnet-4-20260101"}):
            assert get_model_version("anthropic", "standard") == "claude-sonnet-4-20260101"

    def test_unknown_provider_returns_none(self):
        assert get_model_version("fake_provider", "fast") is None

    def test_case_insensitive_provider(self):
        assert get_model_version("OpenAI", "FAST") == "gpt-4o-mini"

    def test_perplexity_defaults(self):
        assert get_model_version("perplexity", "research") == "llama-3.1-sonar-large-128k-online"
