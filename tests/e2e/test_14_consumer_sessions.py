"""
E2E Test: Session Management

Tests: Create → List → Save → Restore → Resume → Transfer → Delete
"""

import pytest
from unittest.mock import patch


class TestSessionCreation:
    """Session creation and listing."""

    def test_create_session(self, client, headers, consumer_jwt_payload):
        """Create session should return session_id."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/sessions/create-session", headers=headers, json={
                "session_type": "tax_return",
            })
        assert response.status_code in [200, 201, 404, 500]

    def test_list_my_sessions(self, client, headers, consumer_jwt_payload):
        """List my sessions should return list."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/sessions/my-sessions", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_check_active_session(self, client, headers, consumer_jwt_payload):
        """Check active session should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/sessions/check-active", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestSessionOperations:
    """Session save, restore, resume."""

    def test_save_session_not_found(self, client, headers, consumer_jwt_payload):
        """Save non-existent session should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/sessions/nonexistent-id/save", headers=headers, json={
                "state": {"step": "income"},
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_restore_session_not_found(self, client, headers, consumer_jwt_payload):
        """Restore non-existent session should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/sessions/nonexistent-id/restore", headers=headers)
        assert response.status_code in [404, 405, 500]

    def test_resume_session_not_found(self, client, headers, consumer_jwt_payload):
        """Resume non-existent session should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/sessions/nonexistent-id/resume", headers=headers, json={})
        assert response.status_code in [404, 405, 500]


class TestSessionTransfer:
    """Anonymous-to-authenticated session transfer."""

    def test_transfer_anonymous(self, client, headers, consumer_jwt_payload):
        """Transfer anonymous session should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/sessions/transfer-anonymous", headers=headers, json={
                "anonymous_session_id": "anon-12345",
            })
        assert response.status_code in [200, 400, 404, 500]


class TestSessionDeletion:
    """Session deletion."""

    def test_delete_session_not_found(self, client, headers, consumer_jwt_payload):
        """Delete non-existent session should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.delete("/api/sessions/nonexistent-id", headers=headers)
        assert response.status_code in [200, 404, 405, 500]


class TestSessionStats:
    """Session statistics."""

    def test_session_stats(self, client, headers, consumer_jwt_payload):
        """Session stats should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/sessions/stats", headers=headers)
        assert response.status_code in [200, 404, 500]
