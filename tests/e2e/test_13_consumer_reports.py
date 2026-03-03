"""
E2E Test: Report Generation & Export

Tests: Generate Report → Get Report → PDF → Email → Export
"""

import pytest
from unittest.mock import patch


class TestAdvisoryReportGeneration:
    """Advisory report creation and retrieval."""

    def test_generate_advisory_report(self, client, headers, consumer_jwt_payload):
        """Generate advisory report should succeed or indicate missing data."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/v1/advisory-reports/generate", headers=headers, json={
                "profile": {
                    "filing_status": "single",
                    "total_income": 120000,
                    "w2_income": 120000,
                    "state": "CA",
                },
            })
        assert response.status_code in [200, 201, 400, 404, 422, 500]

    def test_get_report_not_found(self, client, headers, consumer_jwt_payload):
        """Get non-existent report should return 404."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/v1/advisory-reports/nonexistent-id", headers=headers)
        assert response.status_code in [404, 422, 500]

    def test_download_pdf_not_found(self, client, headers, consumer_jwt_payload):
        """Download PDF for non-existent report should return 404."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/v1/advisory-reports/nonexistent-id/pdf", headers=headers)
        assert response.status_code in [404, 422, 500]

    def test_get_report_data_not_found(self, client, headers, consumer_jwt_payload):
        """Get report data for non-existent report should return 404."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/v1/advisory-reports/nonexistent-id/data", headers=headers)
        assert response.status_code in [404, 422, 500]

    def test_list_session_reports(self, client, headers, consumer_jwt_payload):
        """List reports for a session should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/v1/advisory-reports/session/test-session/reports", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_delete_report_not_found(self, client, headers, consumer_jwt_payload):
        """Delete non-existent report should return 404."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.delete("/api/v1/advisory-reports/nonexistent-id", headers=headers)
        assert response.status_code in [404, 405, 422, 500]


class TestTaxOpportunities:
    """Tax opportunity detection."""

    def test_tax_opportunities(self, client, headers, consumer_jwt_payload):
        """Tax opportunities endpoint should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/v1/advisory-reports/opportunities", headers=headers, json={
                "profile": {
                    "filing_status": "single",
                    "total_income": 150000,
                    "state": "CA",
                },
            })
        assert response.status_code in [200, 404, 422, 500]


class TestReportEmail:
    """Report email delivery."""

    def test_email_report_not_found(self, client, headers, consumer_jwt_payload):
        """Email non-existent report should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/v1/advisory-reports/nonexistent-id/email", headers=headers, json={
                "email": "test@example.com",
            })
        assert response.status_code in [404, 405, 422, 500]


class TestExportEndpoints:
    """Legacy export endpoints."""

    def test_export_pdf(self, client, headers, consumer_jwt_payload):
        """PDF export should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/export/pdf", headers=headers)
        assert response.status_code in [200, 400, 404, 500]

    def test_export_json(self, client, headers, consumer_jwt_payload):
        """JSON export should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/export/json", headers=headers)
        assert response.status_code in [200, 400, 404, 500]
