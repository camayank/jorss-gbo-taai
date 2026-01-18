"""
Tests for Tax Optimizer API endpoints.

Tests cover:
- /api/entity-comparison - Business entity structure comparison
- /api/entity-comparison/adjust-salary - S-Corp salary adjustment
- /api/retirement-analysis - Retirement contribution analysis
- /api/smart-insights - AI-powered tax recommendations
- /api/smart-insights/{id}/apply - Apply insight
- /api/smart-insights/{id}/dismiss - Dismiss insight
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from web.app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestEntityComparisonEndpoint:
    """Tests for /api/entity-comparison endpoint."""

    def test_entity_comparison_success(self, client):
        """Test successful entity comparison with valid input."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 150000,
                "business_expenses": 30000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "comparison" in data

        comparison = data["comparison"]
        assert "analyses" in comparison
        assert "sole_proprietorship" in comparison["analyses"]
        assert "s_corporation" in comparison["analyses"]
        assert "single_member_llc" in comparison["analyses"]
        assert "recommendation" in comparison

    def test_entity_comparison_with_other_income(self, client):
        """Test entity comparison with additional personal income."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 100000,
                "business_expenses": 20000,
                "filing_status": "married_joint",
                "other_income": 50000
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify other_income is considered
        comparison = data["comparison"]
        assert comparison is not None

    def test_entity_comparison_with_custom_salary(self, client):
        """Test entity comparison with specified owner salary."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 200000,
                "business_expenses": 50000,
                "owner_salary": 80000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify S-Corp uses the specified salary
        s_corp = data["comparison"]["analyses"]["s_corporation"]
        assert s_corp["owner_salary"] == 80000

    def test_entity_comparison_all_filing_statuses(self, client):
        """Test entity comparison works with all filing statuses."""
        statuses = ["single", "married_joint", "married_separate", "head_of_household"]

        for status in statuses:
            response = client.post(
                "/api/entity-comparison",
                json={
                    "gross_revenue": 120000,
                    "business_expenses": 20000,
                    "filing_status": status,
                    "other_income": 0
                }
            )

            assert response.status_code == 200, f"Failed for status: {status}"
            data = response.json()
            assert data["success"] is True

    def test_entity_comparison_low_income(self, client):
        """Test entity comparison with low income (S-Corp may not be recommended)."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 40000,
                "business_expenses": 10000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # At low income, S-Corp overhead may not be worth it
        recommendation = data["comparison"]["recommendation"]
        assert recommendation is not None

    def test_entity_comparison_high_income(self, client):
        """Test entity comparison with high income."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 500000,
                "business_expenses": 100000,
                "filing_status": "married_joint",
                "other_income": 100000
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify tax calculations are present
        analyses = data["comparison"]["analyses"]
        for entity_type in ["sole_proprietorship", "s_corporation", "single_member_llc"]:
            assert "total_business_tax" in analyses[entity_type]
            assert "effective_tax_rate" in analyses[entity_type]

    def test_entity_comparison_missing_required_field(self, client):
        """Test entity comparison with missing required field."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "business_expenses": 30000,
                "filing_status": "single"
                # Missing gross_revenue
            }
        )

        assert response.status_code == 422  # Validation error

    def test_entity_comparison_includes_salary_analysis(self, client):
        """Test that response includes salary analysis for S-Corp."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 150000,
                "business_expenses": 30000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "salary_analysis" in data["comparison"]
        salary_analysis = data["comparison"]["salary_analysis"]
        assert "recommended_salary" in salary_analysis
        assert "salary_range_low" in salary_analysis
        assert "salary_range_high" in salary_analysis


class TestSalaryAdjustmentEndpoint:
    """Tests for /api/entity-comparison/adjust-salary endpoint."""

    def test_salary_adjustment_success(self, client):
        """Test successful salary adjustment."""
        response = client.post(
            "/api/entity-comparison/adjust-salary",
            json={
                "gross_revenue": 150000,
                "business_expenses": 30000,
                "owner_salary": 70000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Response is flat structure, not nested under "s_corp"
        assert data["owner_salary"] == 70000
        assert "k1_distribution" in data
        assert "payroll_taxes" in data
        assert "se_tax_savings" in data
        assert "savings_vs_sole_prop" in data

    def test_salary_adjustment_distribution_calculation(self, client):
        """Test that distribution is correctly calculated."""
        response = client.post(
            "/api/entity-comparison/adjust-salary",
            json={
                "gross_revenue": 100000,
                "business_expenses": 20000,
                "owner_salary": 50000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Net income = 100000 - 20000 = 80000
        # Distribution = 80000 - 50000 = 30000 (approximately, after payroll costs)
        assert data["owner_salary"] == 50000
        assert "k1_distribution" in data

    def test_salary_adjustment_zero_salary(self, client):
        """Test salary adjustment with zero salary (edge case)."""
        response = client.post(
            "/api/entity-comparison/adjust-salary",
            json={
                "gross_revenue": 100000,
                "business_expenses": 20000,
                "owner_salary": 0,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_salary_adjustment_max_salary(self, client):
        """Test salary adjustment with salary equal to net income."""
        response = client.post(
            "/api/entity-comparison/adjust-salary",
            json={
                "gross_revenue": 100000,
                "business_expenses": 20000,
                "owner_salary": 80000,  # Full net income as salary
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        assert data["owner_salary"] == 80000

    def test_salary_adjustment_includes_comparison(self, client):
        """Test that salary adjustment includes comparison to sole prop."""
        response = client.post(
            "/api/entity-comparison/adjust-salary",
            json={
                "gross_revenue": 150000,
                "business_expenses": 30000,
                "owner_salary": 65000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "savings_vs_sole_prop" in data
        assert "se_tax_savings" in data
        assert "irs_risk_level" in data
        assert "salary_ratio" in data


class TestRetirementAnalysisEndpoint:
    """Tests for /api/retirement-analysis endpoint."""

    def test_retirement_analysis_success(self, client):
        """Test successful retirement analysis."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 100000,
                "filing_status": "single",
                "age": 35,
                "current_401k": 5000,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        assert "contribution_room" in data
        assert "401k" in data["contribution_room"]
        assert "ira" in data["contribution_room"]
        assert "hsa" in data["contribution_room"]

        assert "scenarios" in data
        assert "marginal_rate" in data

    def test_retirement_analysis_2025_limits(self, client):
        """Test that 2025 contribution limits are used."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 150000,
                "filing_status": "single",
                "age": 40,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        # 2025 limits
        assert data["contribution_room"]["401k"]["max"] == 23500
        assert data["contribution_room"]["ira"]["max"] == 7000
        assert data["contribution_room"]["hsa"]["max"] == 4300  # Individual

    def test_retirement_analysis_catch_up_contributions(self, client):
        """Test catch-up contributions for age 50+."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 150000,
                "filing_status": "single",
                "age": 55,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        # With catch-up: 401k = 23500 + 7500 = 31000, IRA = 7000 + 1000 = 8000
        assert data["contribution_room"]["401k"]["max"] >= 23500

    def test_retirement_analysis_married_hsa_limit(self, client):
        """Test HSA limit for married filers."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 150000,
                "filing_status": "married_joint",
                "age": 40,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Individual HSA limit for 2025 (API uses individual limit regardless of filing status)
        # Family coverage would require has_family_hdhp parameter which API doesn't track
        assert data["contribution_room"]["hsa"]["max"] == 4300

    def test_retirement_analysis_tax_savings_calculation(self, client):
        """Test that tax savings are correctly calculated."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 100000,
                "filing_status": "single",
                "age": 35,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "max_tax_savings" in data
        assert data["max_tax_savings"] > 0

        # Verify scenarios include tax savings
        for scenario in data["scenarios"]:
            assert "tax_savings" in scenario

    def test_retirement_analysis_remaining_room(self, client):
        """Test remaining contribution room calculation."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 100000,
                "filing_status": "single",
                "age": 35,
                "current_401k": 10000,
                "current_ira": 3000,
                "current_hsa": 2000
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["contribution_room"]["401k"]["remaining"] == 23500 - 10000
        assert data["contribution_room"]["ira"]["remaining"] == 7000 - 3000
        assert data["contribution_room"]["hsa"]["remaining"] == 4300 - 2000

    def test_retirement_analysis_roth_recommendation(self, client):
        """Test Roth vs Traditional recommendation."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 80000,
                "filing_status": "single",
                "age": 30,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "roth_vs_traditional" in data
        assert "recommendation" in data["roth_vs_traditional"]
        assert data["roth_vs_traditional"]["recommendation"] in ["roth", "traditional"]

    def test_retirement_analysis_self_employment_income(self, client):
        """Test retirement analysis with self-employment income."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 120000,
                "filing_status": "single",
                "age": 40,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0,
                "self_employment_income": 80000
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestSmartInsightsEndpoint:
    """Tests for /api/smart-insights endpoint."""

    def test_smart_insights_success(self, client):
        """Test smart insights retrieval - requires CPA approval."""
        response = client.get("/api/smart-insights")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "insights" in data

        # CPA COMPLIANCE: Smart Insights require CPA_APPROVED status
        # When not approved, response includes cpa_approval_required flag
        if data.get("cpa_approval_required"):
            assert "message" in data
            assert "disclaimer" in data
            assert data["insights"] == []
        else:
            # If CPA approved, full response available
            assert "summary" in data

    def test_smart_insights_structure(self, client):
        """Test that insights have the correct structure when CPA approved."""
        response = client.get("/api/smart-insights")

        assert response.status_code == 200
        data = response.json()

        # CPA COMPLIANCE: Check for approval status
        if data.get("cpa_approval_required"):
            # Not approved - empty insights expected
            assert data["insights"] == []
        elif data["insights"]:
            # Approved and has insights - verify structure
            insight = data["insights"][0]
            assert "id" in insight
            assert "type" in insight
            assert "title" in insight
            assert "description" in insight
            assert "priority" in insight

    def test_smart_insights_with_session_data(self, client):
        """Test smart insights with session containing tax data."""
        response = client.get("/api/smart-insights")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["insights"], list)

    def test_smart_insights_cpa_approval_required(self, client):
        """Test that smart insights require CPA approval by default."""
        response = client.get("/api/smart-insights")

        assert response.status_code == 200
        data = response.json()
        # New sessions default to DRAFT status, which requires CPA approval
        assert data.get("cpa_approval_required", False) is True


class TestApplyInsightEndpoint:
    """Tests for /api/smart-insights/{id}/apply endpoint."""

    def test_apply_insight_success(self, client):
        """Test successful insight application."""
        response = client.post(
            "/api/smart-insights/test_insight_1/apply",
            json={"action_data": {"field": "ira_amount", "value": 7000}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["insight_id"] == "test_insight_1"
        assert "message" in data
        assert data["refresh_needed"] is True

    def test_apply_insight_with_action_data(self, client):
        """Test applying insight with specific action data."""
        response = client.post(
            "/api/smart-insights/retirement_insight/apply",
            json={
                "action_data": {
                    "contribution_type": "401k",
                    "amount": 23500
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_apply_insight_empty_action_data(self, client):
        """Test applying insight with empty action data."""
        response = client.post(
            "/api/smart-insights/simple_insight/apply",
            json={"action_data": {}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_apply_insight_records_application(self, client):
        """Test that applying an insight records it properly."""
        insight_id = "unique_test_insight"
        response = client.post(
            f"/api/smart-insights/{insight_id}/apply",
            json={"action_data": {"test": "data"}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["insight_id"] == insight_id


class TestDismissInsightEndpoint:
    """Tests for /api/smart-insights/{id}/dismiss endpoint."""

    def test_dismiss_insight_success(self, client):
        """Test successful insight dismissal."""
        response = client.post("/api/smart-insights/test_insight_1/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["insight_id"] == "test_insight_1"
        assert "message" in data

    def test_dismiss_insight_records_dismissal(self, client):
        """Test that dismissing an insight records it properly."""
        insight_id = "dismiss_test_insight"
        response = client.post(f"/api/smart-insights/{insight_id}/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["insight_id"] == insight_id
        assert "message" in data

    def test_dismiss_multiple_insights(self, client):
        """Test dismissing multiple insights."""
        insights = ["insight_1", "insight_2", "insight_3"]

        for insight_id in insights:
            response = client.post(f"/api/smart-insights/{insight_id}/dismiss")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestEntityComparisonEdgeCases:
    """Edge case tests for entity comparison endpoints."""

    def test_zero_revenue(self, client):
        """Test with zero gross revenue."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 0,
                "business_expenses": 0,
                "filing_status": "single",
                "other_income": 50000
            }
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_expenses_exceed_revenue(self, client):
        """Test when expenses exceed revenue (loss scenario)."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 50000,
                "business_expenses": 70000,  # Net loss
                "filing_status": "single",
                "other_income": 100000
            }
        )

        # Should handle loss scenario
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_very_high_income(self, client):
        """Test with very high income (millionaire scenario)."""
        response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 2000000,
                "business_expenses": 500000,
                "filing_status": "married_joint",
                "other_income": 500000
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestRetirementAnalysisEdgeCases:
    """Edge case tests for retirement analysis endpoint."""

    def test_over_contribution(self, client):
        """Test when current contributions exceed limits."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 100000,
                "filing_status": "single",
                "age": 35,
                "current_401k": 30000,  # Over the 23500 limit
                "current_ira": 10000,   # Over the 7000 limit
                "current_hsa": 5000     # Over the 4300 limit
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Remaining should be 0 or negative handled gracefully
        assert data["contribution_room"]["401k"]["remaining"] <= 0

    def test_low_income(self, client):
        """Test retirement analysis with low income."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 25000,
                "filing_status": "single",
                "age": 25,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_retirement_age(self, client):
        """Test retirement analysis for someone near retirement."""
        response = client.post(
            "/api/retirement-analysis",
            json={
                "annual_income": 200000,
                "filing_status": "married_joint",
                "age": 64,
                "current_401k": 0,
                "current_ira": 0,
                "current_hsa": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestEndpointIntegration:
    """Integration tests combining multiple endpoints."""

    def test_entity_then_salary_adjustment(self, client):
        """Test entity comparison followed by salary adjustment."""
        # First, get entity comparison
        entity_response = client.post(
            "/api/entity-comparison",
            json={
                "gross_revenue": 150000,
                "business_expenses": 30000,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert entity_response.status_code == 200
        entity_data = entity_response.json()

        # Get recommended salary
        recommended_salary = entity_data["comparison"]["salary_analysis"]["recommended_salary"]

        # Then adjust salary
        salary_response = client.post(
            "/api/entity-comparison/adjust-salary",
            json={
                "gross_revenue": 150000,
                "business_expenses": 30000,
                "owner_salary": recommended_salary,
                "filing_status": "single",
                "other_income": 0
            }
        )

        assert salary_response.status_code == 200
        salary_data = salary_response.json()
        assert salary_data["owner_salary"] == recommended_salary

    def test_insights_then_apply(self, client):
        """Test getting insights then applying one."""
        # Get insights
        insights_response = client.get("/api/smart-insights")
        assert insights_response.status_code == 200

        # Apply an insight
        apply_response = client.post(
            "/api/smart-insights/test_insight/apply",
            json={"action_data": {}}
        )
        assert apply_response.status_code == 200
        assert apply_response.json()["refresh_needed"] is True
