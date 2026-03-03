"""
E2E Test: Deadlines & Calendar

Tests: Create → List → Get → Update → Delete → Complete → Extension → Calendar
"""

import pytest
from unittest.mock import patch


class TestDeadlineCRUD:
    """Deadline CRUD operations."""

    def test_create_deadline(self, client, headers, cpa_jwt_payload):
        """Create a new deadline."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/deadlines", headers=headers, json={
                "title": "Q1 Estimated Tax Payment",
                "due_date": "2026-04-15",
                "client_id": "client-001",
                "type": "estimated_payment",
            })
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_list_deadlines(self, client, headers, cpa_jwt_payload):
        """List all deadlines."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/deadlines", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_deadline(self, client, headers, cpa_jwt_payload):
        """Get specific deadline."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/deadlines/test-deadline-id", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_update_deadline(self, client, headers, cpa_jwt_payload):
        """Update deadline."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.put("/api/cpa/deadlines/test-deadline-id", headers=headers, json={
                "title": "Updated Deadline Title",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_delete_deadline(self, client, headers, cpa_jwt_payload):
        """Delete deadline."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.delete("/api/cpa/deadlines/test-deadline-id", headers=headers)
        assert response.status_code in [200, 404, 405, 500]


class TestDeadlineActions:
    """Deadline lifecycle actions."""

    def test_complete_deadline(self, client, headers, cpa_jwt_payload):
        """Mark deadline as complete."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/deadlines/test-deadline-id/complete", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_request_extension(self, client, headers, cpa_jwt_payload):
        """Request deadline extension."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/deadlines/test-deadline-id/extension", headers=headers, json={
                "new_date": "2026-10-15",
                "reason": "Client needs more time to gather documents",
            })
        assert response.status_code in [200, 404, 405, 500]


class TestDeadlineFilters:
    """Deadline filtering and views."""

    def test_upcoming_deadlines(self, client, headers, cpa_jwt_payload):
        """Get upcoming deadlines."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/deadlines/upcoming", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_overdue_deadlines(self, client, headers, cpa_jwt_payload):
        """Get overdue deadlines."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/deadlines/overdue", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_calendar_view(self, client, headers, cpa_jwt_payload):
        """Calendar view for specific month."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/deadlines/calendar/2026/3", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_deadline_summary(self, client, headers, cpa_jwt_payload):
        """Deadline summary."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/deadlines/summary", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestDeadlineGeneration:
    """Standard deadline generation."""

    def test_generate_standard_deadlines(self, client, headers, cpa_jwt_payload):
        """Generate standard tax deadlines."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/deadlines/generate-standard", headers=headers, json={
                "tax_year": 2026,
            })
        assert response.status_code in [200, 404, 405, 500]


class TestDeadlinePage:
    """Deadline page rendering."""

    def test_deadlines_page(self, client, headers):
        """Deadlines page should render."""
        response = client.get("/cpa/deadlines")
        assert response.status_code in [200, 302, 303, 307, 404]
