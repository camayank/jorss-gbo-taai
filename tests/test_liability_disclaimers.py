"""Tests for liability disclaimer functionality."""

import pytest
from pydantic import ValidationError

from src.web.intelligent_advisor_api import ChatResponse, STANDARD_DISCLAIMER


class TestChatResponseDisclaimerFields:
    """Tests for ChatResponse disclaimer fields."""

    def test_chat_response_has_disclaimer_field(self):
        """ChatResponse should have optional disclaimer field."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting",
            disclaimer="Test disclaimer"
        )
        assert response.disclaimer == "Test disclaimer"

    def test_chat_response_has_requires_professional_review_field(self):
        """ChatResponse should have requires_professional_review field."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting",
            requires_professional_review=True
        )
        assert response.requires_professional_review is True

    def test_chat_response_disclaimer_defaults_to_none(self):
        """Disclaimer field should default to None."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting"
        )
        assert response.disclaimer is None
        assert response.requires_professional_review is False

    def test_standard_disclaimer_constant_exists(self):
        """STANDARD_DISCLAIMER constant should exist and contain key phrases."""
        assert "AI-generated" in STANDARD_DISCLAIMER
        assert "not professional tax advice" in STANDARD_DISCLAIMER
        assert "CPA or EA" in STANDARD_DISCLAIMER
