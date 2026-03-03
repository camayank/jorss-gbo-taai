"""
Fixtures for TaxAgent tests.
Provides conversation histories and mock AI services.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def mock_ai_service():
    """Mock the unified AI service."""
    mock_response = Mock()
    mock_response.content = "What is your last name?"

    ai_service = Mock()
    ai_service.chat = AsyncMock(return_value=mock_response)
    return ai_service


@pytest.fixture
def mock_run_async():
    """Mock the run_async helper."""
    mock_response = Mock()
    mock_response.content = "Thank you. What is your filing status?"
    return Mock(return_value=mock_response)


@pytest.fixture
def conversation_personal_info():
    """Conversation history at personal info stage."""
    return [
        {"role": "system", "content": "You are a tax preparation assistant..."},
        {"role": "assistant", "content": "Hello! Let's get started! What is your first name?"},
        {"role": "user", "content": "John"},
        {"role": "assistant", "content": "Nice to meet you, John! What is your last name?"},
    ]


@pytest.fixture
def conversation_income_stage():
    """Conversation history at income collection stage."""
    return [
        {"role": "system", "content": "You are a tax preparation assistant..."},
        {"role": "assistant", "content": "Hello! What is your first name?"},
        {"role": "user", "content": "John Smith"},
        {"role": "assistant", "content": "What is your filing status?"},
        {"role": "user", "content": "Single"},
        {"role": "assistant", "content": "Now let's collect your income. Do you have a W-2?"},
    ]


@pytest.fixture
def conversation_deductions_stage():
    """Conversation at deductions stage."""
    return [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "My wages are $75,000"},
        {"role": "assistant", "content": "Do you have any deductions?"},
    ]
