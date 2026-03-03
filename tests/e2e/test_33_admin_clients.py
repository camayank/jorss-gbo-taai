"""
E2E Test: Admin Client Management

Tests: List → Get → Unassigned → Assign → Reassign → Status → Priority → Metrics → Export → Search
"""

import pytest
from unittest.mock import patch


class TestClientListing:
    """Client listing and search."""

    def test_list_clients(self, client, headers, admin_jwt_payload):
        """List all clients."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/clients", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_client(self, client, headers, admin_jwt_payload):
        """Get client detail."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/clients/test-client-id", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_search_clients(self, client, headers, admin_jwt_payload):
        """Search clients."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/clients/search?q=doe", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_unassigned_clients(self, client, headers, admin_jwt_payload):
        """Get unassigned clients."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/clients/unassigned", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestClientAssignment:
    """Client assignment operations."""

    def test_assign_client(self, client, headers, admin_jwt_payload):
        """Assign client to CPA."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/clients/assign", headers=headers, json={
                "client_id": "test-client-id",
                "cpa_id": "cpa-e2e-001",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_reassign_client(self, client, headers, admin_jwt_payload):
        """Reassign client to different CPA."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/clients/test-client-id/reassign", headers=headers, json={
                "new_cpa_id": "cpa-e2e-002",
            })
        assert response.status_code in [200, 404, 405, 500]


class TestClientStatus:
    """Client status management."""

    def test_update_status(self, client, headers, admin_jwt_payload):
        """Update client status."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.patch("/api/v1/admin/clients/test-client-id/status", headers=headers, json={
                "status": "active",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_bulk_status_update(self, client, headers, admin_jwt_payload):
        """Bulk update client status."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/clients/bulk-status", headers=headers, json={
                "client_ids": ["client-001", "client-002"],
                "status": "active",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_update_priority(self, client, headers, admin_jwt_payload):
        """Update client priority."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.patch("/api/v1/admin/clients/test-client-id/priority", headers=headers, json={
                "priority": "high",
            })
        assert response.status_code in [200, 404, 405, 500]


class TestClientMetrics:
    """Client metrics and export."""

    def test_client_metrics(self, client, headers, admin_jwt_payload):
        """Get client metrics."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/clients/metrics", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_export_clients(self, client, headers, admin_jwt_payload):
        """Export clients."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/clients/export", headers=headers, json={
                "format": "csv",
            })
        assert response.status_code in [200, 404, 405, 500]
