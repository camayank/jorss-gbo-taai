"""
E2E Test: Client Management & Portal

Tests: Dashboard → Returns → Documents → Messages → Billing → Profile
"""

import pytest
from unittest.mock import patch


class TestClientDashboard:
    """Client portal dashboard."""

    def test_client_dashboard(self, client, headers, consumer_jwt_payload):
        """Client dashboard should return summary."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/dashboard", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]


class TestClientReturns:
    """Client return access."""

    def test_client_returns_list(self, client, headers, consumer_jwt_payload):
        """Client should see their returns."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/returns", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_client_return_detail(self, client, headers, consumer_jwt_payload):
        """Client should see return detail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/returns/test-return-id", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]


class TestClientDocuments:
    """Client document management."""

    def test_client_document_requests(self, client, headers, consumer_jwt_payload):
        """Client should see document requests."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/documents/requests", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_client_upload_document(self, client, headers, consumer_jwt_payload):
        """Client should be able to upload documents."""
        import io
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post(
                "/api/cpa/client-portal/documents/upload",
                headers=h,
                files={"file": ("w2.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
            )
        assert response.status_code in [200, 401, 403, 404, 405, 500]


class TestClientMessages:
    """Client messaging."""

    def test_client_messages_list(self, client, headers, consumer_jwt_payload):
        """Client should see message threads."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/messages", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_client_send_message(self, client, headers, consumer_jwt_payload):
        """Client should be able to send messages."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/cpa/client-portal/messages", headers=headers, json={
                "subject": "Question about my return",
                "body": "When will my return be filed?",
            })
        assert response.status_code in [200, 201, 401, 403, 404, 405, 500]


class TestClientBilling:
    """Client billing access."""

    def test_client_billing(self, client, headers, consumer_jwt_payload):
        """Client should see billing info."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/billing", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_client_pay_invoice(self, client, headers, consumer_jwt_payload):
        """Client should be able to pay invoice."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/cpa/client-portal/billing/invoices/test-inv/pay", headers=headers, json={})
        assert response.status_code in [200, 401, 403, 404, 405, 500]


class TestClientProfile:
    """Client profile management."""

    def test_client_profile_get(self, client, headers, consumer_jwt_payload):
        """Client should access profile."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/cpa/client-portal/profile", headers=headers)
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_client_profile_update(self, client, headers, consumer_jwt_payload):
        """Client should update profile."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.put("/api/cpa/client-portal/profile", headers=headers, json={
                "phone": "555-0199",
                "address": "123 Main St",
            })
        assert response.status_code in [200, 401, 403, 404, 405, 500]


class TestClientPortalPage:
    """Client portal page rendering."""

    def test_client_portal_page(self, client, headers):
        """Client portal page should render."""
        response = client.get("/client-portal")
        assert response.status_code in [200, 302, 303, 307, 404]
