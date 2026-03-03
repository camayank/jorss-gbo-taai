"""
E2E Test: AI Advisor Flow

Tests: Advisor → Guided Analysis → Strategy Display → Report
1. Start a chat session
2. Send a greeting message
3. Send income information
4. Request analysis
5. Request report generation
"""

import pytest
from unittest.mock import patch, AsyncMock


class TestAdvisorChat:
    """Intelligent advisor chat flow."""

    def _chat(self, client, headers, session_id, token, message, profile=None):
        """Helper to call advisor chat endpoint."""
        h = {**headers, "X-Session-Token": token}
        payload = {"session_id": session_id, "message": message}
        if profile:
            payload["profile"] = profile
        return client.post("/api/advisor/chat", headers=h, json=payload)

    def test_greeting_message(self, client, headers, advisor_session):
        """First message should get a response."""
        session_id, token = advisor_session
        response = self._chat(client, headers, session_id, token, "Hello")

        assert response.status_code == 200
        data = response.json()
        assert "response" in data or "message" in data or "reply" in data

    def test_income_message(self, client, headers, advisor_session):
        """Income message should be understood."""
        session_id, token = advisor_session
        response = self._chat(
            client, headers, session_id, token,
            "I make $85,000 per year as a W-2 employee, single filer"
        )

        assert response.status_code == 200

    def test_profile_with_message(self, client, headers, advisor_session):
        """Structured profile data should be accepted."""
        session_id, token = advisor_session
        response = self._chat(
            client, headers, session_id, token,
            "Calculate my taxes",
            profile={
                "filing_status": "single",
                "total_income": 95000,
                "w2_income": 95000,
                "state": "CA",
            },
        )

        assert response.status_code == 200

    def test_missing_session_token_rejected(self, client, headers, advisor_session):
        """Request without X-Session-Token should be rejected."""
        session_id, _ = advisor_session
        response = client.post(
            "/api/advisor/chat",
            headers=headers,
            json={"session_id": session_id, "message": "Hello"},
        )
        assert response.status_code in [401, 403]

    def test_invalid_session_token_rejected(self, client, headers, advisor_session):
        """Request with wrong session token should be rejected."""
        session_id, _ = advisor_session
        h = {**headers, "X-Session-Token": "completely-wrong-token"}
        response = client.post(
            "/api/advisor/chat",
            headers=h,
            json={"session_id": session_id, "message": "Hello"},
        )
        assert response.status_code in [401, 403, 404]


class TestAdvisorAnalysis:
    """Full analysis endpoint."""

    def test_analysis_with_profile(self, client, headers, advisor_session):
        """Analysis endpoint should return tax calculation and strategies."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.post("/api/advisor/analyze", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "single",
                "total_income": 120000,
                "w2_income": 120000,
                "state": "CA",
            },
        })

        assert response.status_code == 200
        data = response.json()
        # Should have tax calculation results
        assert "current_tax" in data or "total_tax" in str(data).lower()

    def test_analysis_self_employed(self, client, headers, advisor_session):
        """Self-employed profile should trigger entity comparison."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}
        response = client.post("/api/advisor/analyze", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "single",
                "total_income": 150000,
                "business_income": 150000,
                "is_self_employed": True,
                "state": "TX",
            },
        })

        assert response.status_code == 200


class TestAdvisorReport:
    """Report generation endpoint."""

    def test_generate_report(self, client, headers, advisor_session):
        """Report generation should succeed after analysis."""
        session_id, token = advisor_session
        h = {**headers, "X-Session-Token": token}

        # First do an analysis to populate session
        client.post("/api/advisor/analyze", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "married_joint",
                "total_income": 200000,
                "w2_income": 200000,
                "state": "NY",
            },
        })

        # Then generate report
        response = client.post("/api/advisor/generate-report", headers=h, json={
            "session_id": session_id,
            "profile": {
                "filing_status": "married_joint",
                "total_income": 200000,
                "w2_income": 200000,
                "state": "NY",
            },
        })

        assert response.status_code == 200


class TestAdvisorSessionStats:
    """Session statistics (public endpoint)."""

    def test_session_stats_available(self, client, headers):
        response = client.get("/api/advisor/sessions/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "in_memory_sessions" in data
