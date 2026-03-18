"""Tests for Pydantic validators on ChatMessage, ChatRequest, and TaxProfileInput."""

import pytest
from uuid import uuid4
from pydantic import ValidationError

from web.advisor.models import ChatMessage, ChatRequest, TaxProfileInput


# ---------------------------------------------------------------------------
# ChatMessage validators
# ---------------------------------------------------------------------------

class TestChatMessage:

    def test_valid_role_user(self):
        """ChatMessage with role='user' passes validation."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"

    def test_valid_role_assistant(self):
        """ChatMessage with role='assistant' passes validation."""
        msg = ChatMessage(role="assistant", content="Hi there")
        assert msg.role == "assistant"

    def test_invalid_role_raises(self):
        """ChatMessage with role='admin' raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessage(role="admin", content="Hello")
        assert "Role must be" in str(exc_info.value)

    def test_content_over_10000_chars_raises(self):
        """ChatMessage content exceeding 10000 characters raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ChatMessage(role="user", content="x" * 10001)
        assert "content" in str(exc_info.value).lower() or "too long" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# ChatRequest validators
# ---------------------------------------------------------------------------

class TestChatRequest:

    def _session_id(self) -> str:
        return str(uuid4())

    def test_message_over_4000_chars_raises(self):
        """ChatRequest message exceeding 4000 characters raises ValueError."""
        with pytest.raises(ValidationError):
            ChatRequest(
                session_id=self._session_id(),
                message="y" * 4001,
            )

    def test_conversation_history_over_50_items_raises(self):
        """ChatRequest conversation_history with >50 items raises ValueError."""
        history = [
            ChatMessage(role="user", content=f"msg {i}") for i in range(51)
        ]
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(
                session_id=self._session_id(),
                message="hello",
                conversation_history=history,
            )
        assert "too long" in str(exc_info.value).lower() or "history" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TaxProfileInput validators
# ---------------------------------------------------------------------------

class TestTaxProfileInput:

    def test_state_ca_passes(self):
        """TaxProfileInput with state='CA' passes validation."""
        profile = TaxProfileInput(state="CA")
        assert profile.state == "CA"

    def test_state_lowercase_raises(self):
        """TaxProfileInput with state='california' raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            TaxProfileInput(state="california")
        assert "2-letter" in str(exc_info.value) or "State" in str(exc_info.value)

    def test_negative_age_raises(self):
        """TaxProfileInput with age=-1 raises ValueError."""
        with pytest.raises(ValidationError):
            TaxProfileInput(age=-1)

    def test_age_150_raises(self):
        """TaxProfileInput with age=150 raises ValueError (max 120)."""
        with pytest.raises(ValidationError):
            TaxProfileInput(age=150)

    def test_dependents_25_raises(self):
        """TaxProfileInput with dependents=25 raises ValueError (max 20)."""
        with pytest.raises(ValidationError):
            TaxProfileInput(dependents=25)

    def test_total_income_over_100m_raises(self):
        """TaxProfileInput with total_income=200_000_000 raises ValueError."""
        with pytest.raises(ValidationError):
            TaxProfileInput(total_income=200_000_000)

    def test_valid_full_profile_passes(self):
        """TaxProfileInput with all valid fields passes validation."""
        profile = TaxProfileInput(
            filing_status="single",
            total_income=85000.0,
            w2_income=80000.0,
            investment_income=5000.0,
            dependents=2,
            age=35,
            state="TX",
            mortgage_interest=12000.0,
            property_taxes=4000.0,
            charitable_donations=2000.0,
            retirement_401k=19500.0,
            is_self_employed=False,
        )
        assert profile.total_income == 85000.0
        assert profile.state == "TX"
        assert profile.dependents == 2
        assert profile.age == 35
