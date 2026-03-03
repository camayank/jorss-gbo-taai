"""
Fixtures for AI service tests.
Provides mocked AI providers and response objects.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = "This is a tax deduction analysis response."
    response.usage = Mock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 200
    return response


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    response = Mock()
    response.content = [Mock()]
    response.content[0].text = "Claude analysis of tax scenario."
    response.usage = Mock()
    response.usage.input_tokens = 150
    response.usage.output_tokens = 250
    return response


@pytest.fixture
def mock_provider_config():
    """Mock provider configuration."""
    config = Mock()
    config.api_key = "test-api-key-123"
    config.default_model = "gpt-4"
    config.base_url = None
    config.rate_limit_rpm = 60
    config.models = {}
    return config


@pytest.fixture
def mock_ai_provider_enum():
    """Mock AIProvider enum."""
    provider = Mock()
    provider.value = "openai"
    provider.OPENAI = provider
    return provider


@pytest.fixture
def mock_model_capability():
    """Mock ModelCapability enum."""
    cap = Mock()
    cap.STANDARD = "standard"
    cap.COMPLEX = "complex"
    cap.RESEARCH = "research"
    cap.EXTRACTION = "extraction"
    cap.MULTIMODAL = "multimodal"
    return cap
