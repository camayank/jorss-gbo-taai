"""Tests for audit trail improvements."""

import pytest
from datetime import datetime


class TestAIResponseAuditEvent:
    """Tests for AI response audit events."""

    def test_audit_event_has_required_fields(self):
        """AIResponseAuditEvent should have all required fields."""
        from src.audit.audit_models import AIResponseAuditEvent

        event = AIResponseAuditEvent(
            session_id="test-123",
            model_version="gpt-4-turbo",
            prompt_hash="abc123",
            response_type="calculation",
            profile_completeness=0.75,
            response_confidence="high",
            user_message="What is my tax?",
            response_summary="Your estimated tax is..."
        )
        assert event.session_id == "test-123"
        assert event.model_version == "gpt-4-turbo"
        assert event.response_confidence == "high"

    def test_audit_event_has_timestamp(self):
        """Audit event should auto-set timestamp."""
        from src.audit.audit_models import AIResponseAuditEvent

        event = AIResponseAuditEvent(
            session_id="test-456",
            model_version="gpt-4",
            prompt_hash="def456",
            response_type="greeting",
            profile_completeness=0.0,
            response_confidence="high",
            user_message="Hello",
            response_summary="Hi there!"
        )
        assert event.timestamp is not None


class TestAuditLogging:
    """Tests for audit logging functions."""

    def test_log_ai_response_stores_event(self):
        """log_ai_response should store the event."""
        from src.audit.audit_models import AIResponseAuditEvent
        from src.audit.audit_logger import log_ai_response, get_ai_response_audit_trail

        event = AIResponseAuditEvent(
            session_id="test-log-789",
            model_version="gpt-4-turbo",
            prompt_hash="xyz789",
            response_type="strategy",
            profile_completeness=0.5,
            response_confidence="medium",
            user_message="How can I save on taxes?",
            response_summary="Here are some strategies..."
        )
        log_ai_response(event)

        trail = get_ai_response_audit_trail("test-log-789")
        assert len(trail) >= 1
        assert trail[-1].session_id == "test-log-789"

    def test_get_prompt_hash_is_consistent(self):
        """Same prompt should produce same hash."""
        from src.audit.audit_logger import get_prompt_hash

        hash1 = get_prompt_hash("test prompt")
        hash2 = get_prompt_hash("test prompt")
        assert hash1 == hash2

    def test_get_prompt_hash_different_for_different_prompts(self):
        """Different prompts should produce different hashes."""
        from src.audit.audit_logger import get_prompt_hash

        hash1 = get_prompt_hash("prompt one")
        hash2 = get_prompt_hash("prompt two")
        assert hash1 != hash2
