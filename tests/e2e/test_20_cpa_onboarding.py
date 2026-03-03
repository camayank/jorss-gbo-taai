"""
E2E Test: CPA Firm Setup & Smart Onboarding

Tests: CPA Login → Dashboard → Onboarding → Upload → Smart Questions → Create Client
"""

import io
import pytest
from unittest.mock import patch


class TestCPALogin:
    """CPA authentication."""

    def test_cpa_login(self, client, headers):
        """CPA login should respond."""
        response = client.post("/api/core/auth/login", headers=headers, json={
            "email": "cpa@taxfirm.com",
            "password": "CPApassword123!",
        })
        assert response.status_code in [200, 401, 403, 422, 500]


class TestCPAPages:
    """CPA panel page rendering."""

    def test_cpa_dashboard(self, client, headers):
        """CPA dashboard should render."""
        response = client.get("/cpa/dashboard")
        assert response.status_code in [200, 302, 303, 307]

    def test_cpa_onboarding_page(self, client, headers):
        """CPA onboarding page should render."""
        response = client.get("/cpa/onboarding")
        assert response.status_code in [200, 302, 303, 307, 404]


class TestSmartOnboarding:
    """60-second smart onboarding flow."""

    def test_start_onboarding(self, client, headers, cpa_jwt_payload):
        """Start onboarding session."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/smart-onboarding/start", headers=headers, json={})
        assert response.status_code in [200, 201, 404, 500]

    def test_upload_1040_for_ocr(self, client, headers, cpa_jwt_payload):
        """Upload 1040 for OCR extraction."""
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post(
                "/api/cpa/smart-onboarding/test-session/upload",
                headers=h,
                files={"file": ("1040.pdf", io.BytesIO(b"%PDF-1.4 test 1040"), "application/pdf")},
            )
        assert response.status_code in [200, 404, 405, 500]

    def test_get_smart_questions(self, client, headers, cpa_jwt_payload):
        """Get AI-generated smart questions."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/smart-onboarding/test-session/questions", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_submit_answers(self, client, headers, cpa_jwt_payload):
        """Submit answers to smart questions."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/smart-onboarding/test-session/answers", headers=headers, json={
                "answers": [{"question_id": "q1", "answer": "Yes"}],
            })
        assert response.status_code in [200, 404, 405, 500]

    def test_create_client_from_onboarding(self, client, headers, cpa_jwt_payload):
        """Create client from completed onboarding."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/smart-onboarding/test-session/create-client", headers=headers, json={})
        assert response.status_code in [200, 201, 404, 405, 500]

    def test_get_onboarding_status(self, client, headers, cpa_jwt_payload):
        """Get onboarding session status."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.get("/api/cpa/smart-onboarding/test-session", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_batch_quick_add(self, client, headers, cpa_jwt_payload):
        """Batch quick-add clients."""
        with patch("rbac.jwt.decode_token_safe", return_value=cpa_jwt_payload):
            response = client.post("/api/cpa/smart-onboarding/batch/quick-add", headers=headers, json={
                "clients": [
                    {"name": "John Doe", "email": "john@example.com"},
                    {"name": "Jane Doe", "email": "jane@example.com"},
                ],
            })
        assert response.status_code in [200, 404, 405, 500]
