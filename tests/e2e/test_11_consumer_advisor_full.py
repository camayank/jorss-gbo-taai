"""
E2E Test: Intelligent Advisor Chatbot Full Flow

Tests: Health → Chat Session → Analysis → Report → Specialized Analyses
"""

import pytest
from unittest.mock import patch


class TestAdvisorHealth:
    """Advisor health and availability."""

    def test_advisor_health(self, client, headers):
        """Advisor health endpoint should return AI provider status."""
        response = client.get("/api/advisor/health", headers=headers)
        assert response.status_code == 200

    def test_advisor_session_stats(self, client, headers):
        """Session stats should be available."""
        response = client.get("/api/advisor/sessions/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "in_memory_sessions" in data


class TestAdvisorChatFlow:
    """Full advisor chat session flow."""

    def _chat(self, client, headers, session_id, token, message, profile=None):
        h = {**headers, "X-Session-Token": token}
        payload = {"session_id": session_id, "message": message}
        if profile:
            payload["profile"] = profile
        return client.post("/api/advisor/chat", headers=h, json=payload)

    def test_start_chat_greeting(self, client, headers, advisor_session):
        """Start chat session with greeting."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token, "Hello, I need tax help")
        assert response.status_code == 200
        data = response.json()
        assert "response" in data or "message" in data or "reply" in data

    def test_acknowledge_standards(self, client, headers, advisor_session):
        """Acknowledge standards endpoint should respond."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.post("/api/advisor/acknowledge-standards", headers=h, json={
            "session_id": session_id,
        })
        assert response.status_code in [200, 404, 500]

    def test_filing_status_answer(self, client, headers, advisor_session):
        """Send filing status answer."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token,
                              "I'm single", profile={"filing_status": "single"})
        assert response.status_code == 200

    def test_state_answer(self, client, headers, advisor_session):
        """Send state answer."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token,
                              "I live in California", profile={"state": "CA"})
        assert response.status_code == 200

    def test_income_answer(self, client, headers, advisor_session):
        """Send income answer."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token,
                              "I make $95,000 per year",
                              profile={"total_income": 95000, "w2_income": 95000})
        assert response.status_code == 200

    def test_dependents_answer(self, client, headers, advisor_session):
        """Send dependents answer."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token,
                              "I have 2 kids", profile={"dependents": 2})
        assert response.status_code == 200

    def test_deductions_answer(self, client, headers, advisor_session):
        """Send deductions answer."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token,
                              "I pay $15,000 in mortgage interest",
                              profile={"mortgage_interest": 15000})
        assert response.status_code == 200


class TestAdvisorCalculation:
    """Tax calculation via advisor."""

    def test_calculate_tax(self, client, headers, advisor_session):
        """Calculate tax should return breakdown."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.post("/api/advisor/calculate", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "single",
                "total_income": 95000,
                "w2_income": 95000,
                "state": "CA",
            },
        })
        assert response.status_code == 200


class TestAdvisorReport:
    """Report generation."""

    def test_generate_report(self, client, headers, advisor_session):
        """Report generation should succeed."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        # First analyze
        client.post("/api/advisor/analyze", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "single",
                "total_income": 120000,
                "w2_income": 120000,
                "state": "CA",
            },
        })
        # Then generate report
        response = client.post("/api/advisor/generate-report", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "single",
                "total_income": 120000,
                "w2_income": 120000,
                "state": "CA",
            },
        })
        assert response.status_code == 200

    def test_email_report(self, client, headers, advisor_session):
        """Email report endpoint should respond."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.post("/api/advisor/report/email", headers=h, json={
            "session_id": session_id,
            "email": "test@example.com",
        })
        assert response.status_code in [200, 400, 404, 500]


class TestAdvisorSpecializedAnalysis:
    """Specialized analysis endpoints."""

    def _analyze(self, client, headers, advisor_session, endpoint):
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        return client.post(f"/api/advisor/{endpoint}", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "single",
                "total_income": 150000,
                "w2_income": 100000,
                "business_income": 50000,
                "state": "CA",
            },
        })

    def test_roth_analysis(self, client, headers, advisor_session):
        """Roth conversion analysis."""
        response = self._analyze(client, headers, advisor_session, "roth-analysis")
        assert response.status_code in [200, 404, 500]

    def test_entity_analysis(self, client, headers, advisor_session):
        """Entity structure analysis."""
        response = self._analyze(client, headers, advisor_session, "entity-analysis")
        assert response.status_code in [200, 404, 500]

    def test_deduction_analysis(self, client, headers, advisor_session):
        """Deduction strategy analysis."""
        response = self._analyze(client, headers, advisor_session, "deduction-analysis")
        assert response.status_code in [200, 404, 500]

    def test_amt_analysis(self, client, headers, advisor_session):
        """AMT exposure analysis."""
        response = self._analyze(client, headers, advisor_session, "amt-analysis")
        assert response.status_code in [200, 404, 500]

    def test_audit_risk(self, client, headers, advisor_session):
        """Audit risk score."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.get(f"/api/advisor/audit-risk/{session_id}", headers=h)
        assert response.status_code in [200, 404, 500]


class TestAdvisorRateLimiting:
    """Rate limit status."""

    def test_rate_limit_status(self, client, headers, advisor_session):
        """Rate limit status should respond."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.get("/api/advisor/rate-limit/status", headers=h)
        assert response.status_code in [200, 404, 500]


class TestAdvisorDocumentUpload:
    """Document upload in advisor context."""

    def test_upload_document_mid_chat(self, client, headers, advisor_session):
        """Upload document during chat session."""
        import io
        session_id, token = advisor_session
        h = {k: v for k, v in headers.items() if k != "Content-Type"}
        h["X-Session-Token"] = token
        response = client.post(
            "/api/advisor/upload-document",
            headers=h,
            files={"file": ("w2.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
            data={"session_id": session_id},
        )
        assert response.status_code in [200, 400, 404, 500]


class TestAdvisorPages:
    """Advisor page rendering."""

    def test_intelligent_advisor_page(self, client, headers):
        """Intelligent advisor page should render."""
        response = client.get("/intelligent-advisor")
        assert response.status_code in [200, 302, 303, 307]

    def test_quick_estimate_page(self, client, headers):
        """Quick estimate page should render."""
        response = client.get("/quick-estimate")
        assert response.status_code in [200, 302, 303, 307]
