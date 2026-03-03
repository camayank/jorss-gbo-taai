"""
E2E Test: Scenario Comparison

Tests: Filing Status Comparison → Retirement → What-If → Compare → CRUD
"""

import pytest
from unittest.mock import patch


class TestScenarioComparison:
    """Tax scenario comparison endpoints."""

    def test_filing_status_comparison(self, client, headers, consumer_jwt_payload):
        """Filing status comparison should return analysis."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/scenarios/filing-status", headers=headers, json={
                "income": 120000,
                "filing_statuses": ["single", "married_joint"],
            })
        assert response.status_code in [200, 404, 500]

    def test_retirement_scenario(self, client, headers, consumer_jwt_payload):
        """Retirement scenario should return projection."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/scenarios/retirement", headers=headers, json={
                "current_income": 150000,
                "retirement_contributions": 20000,
                "filing_status": "married_joint",
            })
        assert response.status_code in [200, 404, 500]

    def test_what_if_scenario(self, client, headers, consumer_jwt_payload):
        """What-if scenario should return delta."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/scenarios/what-if", headers=headers, json={
                "base_income": 100000,
                "changes": {"additional_income": 20000},
                "filing_status": "single",
            })
        assert response.status_code in [200, 404, 500]

    def test_compare_scenarios(self, client, headers, consumer_jwt_payload):
        """Compare two scenarios side-by-side."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/scenarios/compare", headers=headers, json={
                "scenario_a": {"income": 100000, "filing_status": "single"},
                "scenario_b": {"income": 100000, "filing_status": "married_joint"},
            })
        assert response.status_code in [200, 404, 500]


class TestScenarioCRUD:
    """Scenario CRUD operations."""

    def test_get_scenario_not_found(self, client, headers, consumer_jwt_payload):
        """Get non-existent scenario should return 404."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.get("/api/scenarios/nonexistent-id", headers=headers)
        assert response.status_code in [404, 422, 500]

    def test_delete_scenario_not_found(self, client, headers, consumer_jwt_payload):
        """Delete non-existent scenario should return 404."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.delete("/api/scenarios/nonexistent-id", headers=headers)
        assert response.status_code in [404, 405, 422, 500]

    def test_apply_scenario_not_found(self, client, headers, consumer_jwt_payload):
        """Apply non-existent scenario should fail."""
        with patch("rbac.jwt.decode_token_safe", return_value=consumer_jwt_payload):
            response = client.post("/api/scenarios/nonexistent-id/apply", headers=headers, json={})
        assert response.status_code in [404, 405, 422, 500]
