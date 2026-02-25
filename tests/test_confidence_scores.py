"""Tests for confidence scores visibility."""

import pytest

from src.web.intelligent_advisor_api import ChatResponse


class TestChatResponseConfidenceFields:
    """Tests for ChatResponse confidence fields."""

    def test_chat_response_has_confidence_field(self):
        """ChatResponse should have response_confidence field."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting",
            response_confidence="high"
        )
        assert response.response_confidence == "high"

    def test_chat_response_has_confidence_reason_field(self):
        """ChatResponse should have confidence_reason field."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting",
            response_confidence="medium",
            confidence_reason="Some profile data missing"
        )
        assert response.confidence_reason == "Some profile data missing"

    def test_chat_response_confidence_defaults_to_high(self):
        """Confidence should default to high."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting"
        )
        assert response.response_confidence == "high"
        assert response.confidence_reason is None


class TestConfidenceCalculation:
    """Tests for confidence calculation logic."""

    def test_high_confidence_with_complete_profile(self):
        """Profile >=70% complete, no complex scenario = high confidence."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.75,
            has_complex_scenario=False
        )
        assert confidence == "high"
        assert reason is None

    def test_medium_confidence_with_partial_profile(self):
        """Profile 40-70% complete = medium confidence."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.55,
            has_complex_scenario=False
        )
        assert confidence == "medium"
        assert "missing" in reason.lower()

    def test_low_confidence_with_minimal_profile(self):
        """Profile <40% complete = low confidence."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.25,
            has_complex_scenario=False
        )
        assert confidence == "low"
        assert reason is not None

    def test_medium_confidence_with_complex_scenario(self):
        """Complex scenario reduces to medium even with complete profile."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.80,
            has_complex_scenario=True
        )
        assert confidence == "medium"
        assert "complex" in reason.lower() or "professional" in reason.lower()
