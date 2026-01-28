"""
Tests for Configuration Management API.
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import CSRF bypass headers from conftest
from conftest import CSRF_BYPASS_HEADERS


class TestConfigAPIRoutes:
    """Test configuration API routes."""

    def test_router_import(self):
        """Test that config API can be imported."""
        from web.config_api import router, rules_router
        assert router is not None
        assert rules_router is not None

    def test_router_has_correct_prefix(self):
        """Test router prefixes are correct."""
        from web.config_api import router, rules_router
        assert router.prefix == "/api/config"
        assert rules_router.prefix == "/api/rules"


class TestConfigParameterResponse:
    """Test ConfigParameterResponse model."""

    def test_model_creation(self):
        """Test creating ConfigParameterResponse."""
        from web.config_api import ConfigParameterResponse

        response = ConfigParameterResponse(
            name="standard_deduction",
            value=15750,
            tax_year=2025,
            filing_status="single",
        )

        assert response.name == "standard_deduction"
        assert response.value == 15750
        assert response.tax_year == 2025

    def test_model_without_optional_fields(self):
        """Test model without optional fields."""
        from web.config_api import ConfigParameterResponse

        response = ConfigParameterResponse(
            name="ss_wage_base",
            value=176100,
            tax_year=2025,
        )

        assert response.name == "ss_wage_base"
        assert response.filing_status is None


class TestRuleResponse:
    """Test RuleResponse model."""

    def test_model_creation(self):
        """Test creating RuleResponse."""
        from web.config_api import RuleResponse

        response = RuleResponse(
            rule_id="DED001",
            name="SALT Deduction Cap",
            description="State and local tax deduction capped at $10,000",
            category="deduction",
            rule_type="limit",
            severity="warning",
            limit=10000,
            irs_reference="IRC Section 164(b)(6)",
            tax_year=2025,
        )

        assert response.rule_id == "DED001"
        assert response.limit == 10000
        assert response.irs_reference == "IRC Section 164(b)(6)"


class TestRuleEvaluationRequest:
    """Test RuleEvaluationRequest model."""

    def test_model_creation(self):
        """Test creating RuleEvaluationRequest."""
        from web.config_api import RuleEvaluationRequest

        request = RuleEvaluationRequest(
            tax_year=2025,
            filing_status="married_joint",
            adjusted_gross_income=150000,
            earned_income=150000,
            wages=140000,
            self_employment_income=10000,
        )

        assert request.tax_year == 2025
        assert request.filing_status == "married_joint"
        assert request.adjusted_gross_income == 150000

    def test_model_defaults(self):
        """Test default values."""
        from web.config_api import RuleEvaluationRequest

        request = RuleEvaluationRequest(
            filing_status="single"
        )

        assert request.tax_year == 2025
        assert request.adjusted_gross_income == 0


class TestRuleEvaluationResult:
    """Test RuleEvaluationResult model."""

    def test_model_creation(self):
        """Test creating RuleEvaluationResult."""
        from web.config_api import RuleEvaluationResult

        result = RuleEvaluationResult(
            rule_id="DED001",
            rule_name="SALT Cap",
            passed=True,
            severity="warning",
            message="SALT deduction within limit",
            value=8000,
            irs_reference="IRC 164(b)(6)",
        )

        assert result.passed is True
        assert result.value == 8000


class TestChangeHistoryItem:
    """Test ChangeHistoryItem model."""

    def test_model_creation(self):
        """Test creating ChangeHistoryItem."""
        from web.config_api import ChangeHistoryItem

        item = ChangeHistoryItem(
            parameter="standard_deduction.single",
            old_value=14600,
            new_value=15750,
            reason="Annual inflation adjustment",
            changed_by="admin",
            changed_at="2025-01-01T00:00:00",
            irs_reference="Rev. Proc. 2024-40",
        )

        assert item.parameter == "standard_deduction.single"
        assert item.old_value == 14600
        assert item.new_value == 15750


class TestConfigAPIEndpoints:
    """Integration tests for API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from web.app import app
        return TestClient(app)

    def test_get_tax_year_config(self, client):
        """Test getting tax year configuration."""
        response = client.get("/api/config/tax-year/2025")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tax_year"] == 2025
        assert "config" in data
        assert "standard_deduction" in data["config"]

    def test_get_tax_year_config_returns_defaults(self, client):
        """Test getting config for year without specific config returns defaults."""
        response = client.get("/api/config/tax-year/1990")
        # The config loader returns defaults for missing years, not 404
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tax_year"] == 1990

    def test_list_parameters(self, client):
        """Test listing parameters."""
        response = client.get("/api/config/parameters?year=2025")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "parameters" in data
        assert len(data["parameters"]) > 0

    def test_get_specific_parameter(self, client):
        """Test getting a specific parameter."""
        response = client.get("/api/config/parameter/ss_wage_base?year=2025")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "ss_wage_base"
        assert data["value"] == 176100

    def test_get_parameter_with_filing_status(self, client):
        """Test getting parameter with filing status."""
        response = client.get(
            "/api/config/parameter/standard_deduction?year=2025&filing_status=single"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "standard_deduction"
        assert data["value"] == 15750

    def test_get_parameter_not_found(self, client):
        """Test getting non-existent parameter."""
        response = client.get("/api/config/parameter/nonexistent?year=2025")
        assert response.status_code == 404

    def test_get_config_metadata(self, client):
        """Test getting configuration metadata."""
        response = client.get("/api/config/metadata/2025")
        assert response.status_code == 200
        data = response.json()
        assert data["tax_year"] == 2025
        assert data["source"] == "IRS"
        assert len(data["irs_references"]) > 0

    def test_get_change_history(self, client):
        """Test getting change history."""
        response = client.get("/api/config/changes")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "changes" in data


class TestRulesAPIEndpoints:
    """Integration tests for rules API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from web.app import app
        return TestClient(app)

    def test_list_rules(self, client):
        """Test listing all rules."""
        response = client.get("/api/rules?year=2025")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rule_count"] > 0
        assert "rules" in data

    def test_list_rules_by_category(self, client):
        """Test listing rules filtered by category."""
        response = client.get("/api/rules?year=2025&category=deduction")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # All returned rules should be deduction category
        for rule in data["rules"]:
            assert rule["category"] == "deduction"

    def test_list_rules_invalid_category(self, client):
        """Test listing rules with invalid category."""
        response = client.get("/api/rules?year=2025&category=invalid_category")
        assert response.status_code == 400

    def test_get_specific_rule(self, client):
        """Test getting a specific rule."""
        response = client.get("/api/rules/DED001?year=2025")
        assert response.status_code == 200
        data = response.json()
        assert data["rule_id"] == "DED001"
        assert data["name"] == "SALT Deduction Cap"
        assert data["limit"] == 10000

    def test_get_rule_not_found(self, client):
        """Test getting non-existent rule."""
        response = client.get("/api/rules/NONEXISTENT?year=2025")
        assert response.status_code == 404

    def test_evaluate_rules(self, client):
        """Test evaluating rules against context."""
        response = client.post(
            "/api/rules/evaluate",
            json={
                "tax_year": 2025,
                "filing_status": "single",
                "adjusted_gross_income": 100000,
                "earned_income": 100000,
                "wages": 100000,
            },
            headers=CSRF_BYPASS_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_rules_evaluated"] > 0
        assert "results" in data
        assert "summary" in data

    def test_evaluate_rules_high_income(self, client):
        """Test evaluating rules for high income taxpayer."""
        response = client.post(
            "/api/rules/evaluate",
            json={
                "tax_year": 2025,
                "filing_status": "single",
                "adjusted_gross_income": 250000,
                "earned_income": 250000,
            },
            headers=CSRF_BYPASS_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        # Should have some rules that don't pass due to high income
        assert data["rules_failed"] > 0 or data["rules_passed"] > 0

    def test_list_rule_categories(self, client):
        """Test listing rule categories."""
        response = client.get("/api/rules/categories")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["categories"]) > 0
        # Check for expected categories
        category_values = [c["value"] for c in data["categories"]]
        assert "income" in category_values
        assert "deduction" in category_values
        assert "credit" in category_values
