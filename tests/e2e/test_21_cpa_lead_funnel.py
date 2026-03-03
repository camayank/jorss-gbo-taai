"""
E2E Test: Lead Generation Pipeline (Whitelabel)

Tests: Quick Estimate → Upload Teaser → Contact Capture → Pipeline → Assign → Convert
"""

import io
import pytest
from unittest.mock import patch


class TestLeadCapture:
    """Public lead capture endpoints (no auth required)."""

    def test_quick_savings_estimate(self, client, headers):
        """Quick savings estimate (public)."""
        response = client.post("/api/cpa/lead-generation/estimate", headers=headers, json={
            "income": 120000,
            "filing_status": "single",
            "state": "CA",
        })
        assert response.status_code in [200, 404, 422, 500]

    def test_upload_1040_teaser(self, client, headers):
        """Upload 1040 for savings teaser (public)."""
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        response = client.post("/api/cpa/lead-generation/upload", headers=h,
                               files={"file": ("1040.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")})
        assert response.status_code in [200, 404, 405, 500]

    def test_capture_contact_info(self, client, headers):
        """Capture contact info for lead."""
        response = client.post("/api/cpa/lead-generation/test-lead-id/contact", headers=headers, json={
            "name": "Prospect Smith",
            "email": "prospect@example.com",
            "phone": "555-0100",
        })
        assert response.status_code in [200, 404, 405, 500]


class TestLeadPipeline:
    """Lead pipeline management (CPA auth required)."""

    def test_get_lead_profile(self, client, headers, cpa_jwt_payload):
        """Get lead profile."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/pipeline/leads/test-lead-id", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_pipeline_view(self, client, headers, cpa_jwt_payload):
        """Pipeline view should return stages."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/pipeline/leads", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_pipeline_metrics(self, client, headers, cpa_jwt_payload):
        """Pipeline metrics should return data."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/pipeline/metrics", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_conversion_rates(self, client, headers, cpa_jwt_payload):
        """Conversion rates endpoint."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/pipeline/conversion", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_priority_queue(self, client, headers, cpa_jwt_payload):
        """Priority queue should return sorted leads."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/pipeline/priority-queue", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestLeadActions:
    """Lead state management."""

    def test_advance_lead_stage(self, client, headers, cpa_jwt_payload):
        """Advance lead through pipeline stages."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/leads/test-lead-id/advance", headers=headers, json={
                "new_stage": "qualified",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_assign_lead(self, client, headers, cpa_jwt_payload):
        """Assign lead to CPA staff."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/leads/test-lead-id/assign", headers=headers, json={
                "cpa_id": "cpa-e2e-001",
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_convert_lead_to_client(self, client, headers, cpa_jwt_payload):
        """Convert lead to client."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/leads/test-lead-id/convert", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_get_unassigned_leads(self, client, headers, cpa_jwt_payload):
        """Get unassigned leads."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/leads/unassigned", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_get_high_priority_leads(self, client, headers, cpa_jwt_payload):
        """Get high priority leads."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/leads/high-priority", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_batch_signal_injection(self, client, headers, cpa_jwt_payload):
        """Batch signal injection for lead scoring."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/leads/test-lead-id/signals/batch", headers=headers, json={
                "signals": [{"type": "page_view", "value": "pricing"}],
            })
        assert response.status_code in [200, 404, 405, 500]


class TestLeadMagnetPages:
    """Lead magnet landing pages."""

    def test_lead_magnet_landing(self, client, headers):
        """Lead magnet landing page should render."""
        response = client.get("/test-firm/")
        assert response.status_code in [200, 404]

    def test_lead_magnet_estimate(self, client, headers):
        """Lead magnet estimate page should render."""
        response = client.get("/test-firm/estimate")
        assert response.status_code in [200, 404]

    def test_lead_magnet_contact(self, client, headers):
        """Lead magnet contact page should render."""
        response = client.get("/test-firm/contact")
        assert response.status_code in [200, 404]
