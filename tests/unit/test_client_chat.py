"""Tests for authenticated client chat with tax context."""

import pytest
from unittest.mock import patch, MagicMock


def test_build_client_tax_context_returns_context():
    """Verify tax context built from client session data."""
    with patch("database.session_persistence.SessionPersistence") as MockPersistence:
        mock_persistence = MagicMock()
        mock_persistence.list_sessions_by_client.return_value = [{"session_id": "sess-1"}]
        mock_persistence.load_session.return_value = {
            "tax_computation": {
                "filing_status": "married_joint",
                "agi": 150000,
                "total_tax": 25000,
                "effective_rate": 16.7,
            }
        }
        MockPersistence.return_value = mock_persistence

        from cpa_panel.api.client_portal_routes import _build_client_tax_context
        result = _build_client_tax_context("client-123")

        assert "married_joint" in result
        assert "$150,000" in result
        assert "$25,000" in result


def test_build_client_tax_context_empty_on_no_client():
    """Empty string returned for empty client_id."""
    from cpa_panel.api.client_portal_routes import _build_client_tax_context
    assert _build_client_tax_context("") == ""


def test_build_client_tax_context_empty_on_exception():
    """Graceful degradation when persistence raises."""
    with patch("database.session_persistence.SessionPersistence", side_effect=Exception("db error")):
        from cpa_panel.api.client_portal_routes import _build_client_tax_context
        assert _build_client_tax_context("client-1") == ""


def test_client_chat_endpoint_exists():
    """Verify the chat endpoint is registered on the router."""
    from cpa_panel.api.client_portal_routes import router

    paths = [route.path for route in router.routes]
    assert "/client/chat/message" in paths


def test_client_chat_request_model():
    """Verify ChatRequest model validates correctly."""
    from cpa_panel.api.client_portal_routes import ClientChatRequest

    req = ClientChatRequest(message="What is my tax liability?")
    assert req.message == "What is my tax liability?"
    assert req.conversation_id is None

    req2 = ClientChatRequest(message="test", conversation_id="conv-1")
    assert req2.conversation_id == "conv-1"
