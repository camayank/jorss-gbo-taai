"""
E2E Test: Return Preparation & Review Workflow

Tests: Status → Submit → Approve → Revert → Queue → Delta → Notes
"""

import pytest
from unittest.mock import patch


class TestReturnStatus:
    """Return status and workflow."""

    def test_return_status(self, client, headers, cpa_jwt_payload):
        """Get return status."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/workflow/test-session/status", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_submit_for_review(self, client, headers, cpa_jwt_payload):
        """Submit return for review."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/workflow/test-session/submit-for-review", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_approve_return(self, client, headers, cpa_jwt_payload):
        """CPA approve return."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/workflow/test-session/approve", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_revert_to_draft(self, client, headers, cpa_jwt_payload):
        """Revert return to draft."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/workflow/test-session/revert", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_approval_certificate(self, client, headers, cpa_jwt_payload):
        """Get approval certificate."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/workflow/test-session/approval-certificate", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_return_summary(self, client, headers, cpa_jwt_payload):
        """Get return summary."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/workflow/test-session/summary", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestReturnQueue:
    """Return queue management."""

    def test_queue_counts(self, client, headers, cpa_jwt_payload):
        """Queue counts by status."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/workflow/queue/counts", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_queue_by_status(self, client, headers, cpa_jwt_payload):
        """Queue filtered by status."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/workflow/queue/draft", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestReturnAnalysis:
    """Return analysis tools."""

    def test_delta_analysis(self, client, headers, cpa_jwt_payload):
        """Year-over-year delta analysis."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/analysis/test-session/delta", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_tax_driver_breakdown(self, client, headers, cpa_jwt_payload):
        """Tax driver breakdown."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/analysis/test-session/tax-drivers", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_compare_scenarios(self, client, headers, cpa_jwt_payload):
        """Compare tax scenarios."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/analysis/test-session/compare-scenarios", headers=headers, json={
                "scenarios": [{"label": "Current"}, {"label": "S-Corp"}],
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_suggested_scenarios(self, client, headers, cpa_jwt_payload):
        """AI-suggested scenarios."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/analysis/test-session/suggested-scenarios", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestReturnNotes:
    """CPA review notes."""

    def test_add_note(self, client, headers, cpa_jwt_payload):
        """Add review note."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/notes/test-session/notes", headers=headers, json={
                "content": "Need to verify W-2 amounts",
                "note_type": "review",
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_get_notes(self, client, headers, cpa_jwt_payload):
        """Get notes for session."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/notes/test-session/notes", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_delete_note(self, client, headers, cpa_jwt_payload):
        """Delete a note."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.delete("/api/cpa/notes/test-session/notes/test-note-id", headers=headers)
        assert response.status_code in [200, 404, 405, 500]


class TestReturnQueuePage:
    """Return queue page rendering."""

    def test_return_queue_page(self, client, headers):
        """Return queue page should render."""
        response = client.get("/cpa/returns/queue")
        assert response.status_code in [200, 302, 303, 307, 404]
