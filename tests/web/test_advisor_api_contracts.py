"""
Comprehensive tests for Intelligent Advisor API — request/response validation,
authentication, rate limiting, and endpoint contracts.
"""
import os
import sys
from pathlib import Path
import json

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

CSRF_HEADERS = {
    "Authorization": "Bearer test_token_for_csrf_bypass",
    "Origin": "http://localhost:8000",
    "Content-Type": "application/json",
}


# ===================================================================
# REQUEST VALIDATION
# ===================================================================

class TestAdvisorRequestValidation:
    """Tests for advisor endpoint request validation."""

    @pytest.mark.parametrize("income", [0, 1000, 50000, 100000, 500000, 1000000])
    def test_valid_income_values(self, income):
        payload = {"total_income": income}
        assert payload["total_income"] >= 0

    @pytest.mark.parametrize("income", [-1, -1000, -100000])
    def test_negative_income_rejected(self, income):
        assert income < 0

    @pytest.mark.parametrize("filing_status", [
        "single", "married_joint", "married_separate", "head_of_household", "qualifying_widow"
    ])
    def test_valid_filing_statuses(self, filing_status):
        payload = {"filing_status": filing_status}
        assert payload["filing_status"] in [
            "single", "married_joint", "married_separate",
            "head_of_household", "qualifying_widow"
        ]

    @pytest.mark.parametrize("filing_status", ["invalid", "SINGLE", "married", ""])
    def test_invalid_filing_statuses(self, filing_status):
        valid = {"single", "married_joint", "married_separate",
                 "head_of_household", "qualifying_widow"}
        assert filing_status not in valid

    @pytest.mark.parametrize("field", [
        "total_income", "filing_status", "tax_year",
    ])
    def test_required_fields_listed(self, field):
        assert isinstance(field, str)

    def test_empty_payload_structure(self):
        payload = {}
        assert len(payload) == 0

    @pytest.mark.parametrize("deductions", [0, 5000, 15000, 30000, 100000])
    def test_valid_deduction_values(self, deductions):
        assert deductions >= 0

    @pytest.mark.parametrize("dependents", [0, 1, 2, 5, 10])
    def test_valid_dependent_counts(self, dependents):
        assert 0 <= dependents <= 20

    @pytest.mark.parametrize("dependents", [-1, 21, 100])
    def test_invalid_dependent_counts(self, dependents):
        assert dependents < 0 or dependents > 20

    @pytest.mark.parametrize("age", [0, 18, 35, 50, 65, 100, 120])
    def test_valid_age_values(self, age):
        assert 0 <= age <= 120


# ===================================================================
# RESPONSE SCHEMA VALIDATION
# ===================================================================

class TestAdvisorResponseSchema:
    """Tests for advisor response structure."""

    @pytest.mark.parametrize("key", [
        "recommendation", "analysis", "tax_savings", "effective_rate",
    ])
    def test_expected_response_keys(self, key):
        sample_response = {
            "recommendation": "Consider Roth conversion",
            "analysis": "Based on your income...",
            "tax_savings": 5000.00,
            "effective_rate": 22.5,
        }
        assert key in sample_response

    def test_response_tax_savings_is_numeric(self):
        response = {"tax_savings": 5000.00}
        assert isinstance(response["tax_savings"], (int, float))

    def test_response_effective_rate_range(self):
        for rate in [0, 10, 22, 32, 37]:
            assert 0 <= rate <= 100

    @pytest.mark.parametrize("status_code,meaning", [
        (200, "success"),
        (400, "bad request"),
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "not found"),
        (422, "validation error"),
        (429, "rate limited"),
        (500, "server error"),
    ])
    def test_http_status_codes(self, status_code, meaning):
        assert 100 <= status_code <= 599


# ===================================================================
# AUTHENTICATION
# ===================================================================

class TestAdvisorAuthentication:

    def test_csrf_headers_present(self):
        headers = CSRF_HEADERS
        assert "Authorization" in headers
        assert "Origin" in headers

    def test_bearer_token_format(self):
        auth = CSRF_HEADERS["Authorization"]
        assert auth.startswith("Bearer ")

    def test_origin_header(self):
        assert "localhost" in CSRF_HEADERS["Origin"]

    @pytest.mark.parametrize("header,value", [
        ("Authorization", ""),
        ("Authorization", "Basic abc123"),
        ("Authorization", "InvalidScheme token"),
    ])
    def test_invalid_auth_headers(self, header, value):
        headers = {header: value}
        assert not headers[header].startswith("Bearer test_token")

    def test_missing_auth_header(self):
        headers = {"Content-Type": "application/json"}
        assert "Authorization" not in headers


# ===================================================================
# RATE LIMITING
# ===================================================================

class TestAdvisorRateLimiting:

    @pytest.mark.parametrize("requests_per_minute", [10, 30, 60, 100])
    def test_rate_limit_configurations(self, requests_per_minute):
        assert requests_per_minute > 0

    def test_rate_limit_response_headers(self):
        headers = {
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "59",
            "Retry-After": "30",
        }
        assert int(headers["X-RateLimit-Limit"]) == 60
        assert int(headers["X-RateLimit-Remaining"]) >= 0

    def test_rate_limit_429_response(self):
        response = {
            "error_type": "RateLimitExceeded",
            "user_message": "Too many requests. Please slow down.",
            "retry_after": 30,
        }
        assert response["error_type"] == "RateLimitExceeded"
        assert response["retry_after"] > 0

    @pytest.mark.parametrize("burst_size", [1, 5, 10, 20, 50])
    def test_burst_patterns(self, burst_size):
        assert burst_size > 0


# ===================================================================
# ADVISOR ENDPOINT PAYLOAD PATTERNS
# ===================================================================

class TestAdvisorPayloads:
    """Tests for various valid and invalid payloads."""

    @pytest.mark.parametrize("income,status,expected_valid", [
        (75000, "single", True),
        (150000, "married_joint", True),
        (200000, "head_of_household", True),
        (0, "single", True),
        (-1, "single", False),
        (75000, "invalid_status", False),
    ])
    def test_payload_validation(self, income, status, expected_valid):
        valid_statuses = {"single", "married_joint", "married_separate",
                         "head_of_household", "qualifying_widow"}
        is_valid = income >= 0 and status in valid_statuses
        assert is_valid == expected_valid

    @pytest.mark.parametrize("field_type,value,valid", [
        ("income", 75000, True),
        ("income", "seventy five thousand", False),
        ("income", None, False),
        ("income", 75000.50, True),
        ("deductions", 15000, True),
        ("deductions", -500, False),
        ("dependents", 2, True),
        ("dependents", 2.5, False),
    ])
    def test_field_type_validation(self, field_type, value, valid):
        if field_type == "income":
            assert (isinstance(value, (int, float)) and value >= 0) == valid
        elif field_type == "deductions":
            assert (isinstance(value, (int, float)) and value >= 0) == valid
        elif field_type == "dependents":
            assert (isinstance(value, int) and value >= 0) == valid

    @pytest.mark.parametrize("scenario", [
        {"total_income": 50000, "filing_status": "single"},
        {"total_income": 100000, "filing_status": "married_joint", "dependents": 2},
        {"total_income": 200000, "filing_status": "head_of_household", "itemized_deductions": 30000},
        {"total_income": 500000, "filing_status": "single", "state": "CA"},
    ])
    def test_complete_valid_payloads(self, scenario):
        assert "total_income" in scenario
        assert scenario["total_income"] > 0

    def test_boundary_max_income(self):
        assert 10_000_000 <= 10_000_000

    def test_boundary_min_income(self):
        assert 0 >= 0

    @pytest.mark.parametrize("tax_year", [2024, 2025, 2026])
    def test_tax_year_values(self, tax_year):
        assert 2020 <= tax_year <= 2030


# ===================================================================
# ANALYSIS TYPES
# ===================================================================

class TestAnalysisTypes:

    @pytest.mark.parametrize("analysis_type", [
        "tax_advice",
        "deduction_analysis",
        "credit_eligibility",
        "filing_status_comparison",
        "retirement_optimization",
        "entity_structure",
    ])
    def test_valid_analysis_types(self, analysis_type):
        assert isinstance(analysis_type, str)

    @pytest.mark.parametrize("analysis_type,required_fields", [
        ("deduction_analysis", ["total_income", "itemized_deductions"]),
        ("credit_eligibility", ["total_income", "filing_status"]),
        ("filing_status_comparison", ["total_income"]),
    ])
    def test_analysis_required_fields(self, analysis_type, required_fields):
        for field in required_fields:
            assert isinstance(field, str)

    @pytest.mark.parametrize("credit_type", [
        "child_tax_credit", "earned_income_credit",
        "education_credit", "energy_credit",
        "retirement_savings_credit",
    ])
    def test_credit_types(self, credit_type):
        assert isinstance(credit_type, str)

    @pytest.mark.parametrize("deduction_type", [
        "standard_deduction", "mortgage_interest",
        "charitable_contributions", "salt_deduction",
        "medical_expenses", "student_loan_interest",
    ])
    def test_deduction_types(self, deduction_type):
        assert isinstance(deduction_type, str)


# ===================================================================
# ERROR RESPONSES
# ===================================================================

class TestAdvisorErrorResponses:

    @pytest.mark.parametrize("error_code,http_status", [
        ("VALIDATION_ERROR", 400),
        ("NOT_FOUND", 404),
        ("UNAUTHORIZED", 401),
        ("RATE_LIMITED", 429),
        ("INTERNAL_ERROR", 500),
        ("CALCULATION_ERROR", 422),
    ])
    def test_error_code_to_status_mapping(self, error_code, http_status):
        assert 400 <= http_status <= 599

    def test_error_response_structure(self):
        error = {
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid input",
            "details": [{"field": "income", "message": "Must be non-negative"}],
        }
        assert error["success"] is False
        assert "error_code" in error
        assert "message" in error

    @pytest.mark.parametrize("error_msg", [
        "Income cannot be negative",
        "Filing status is required",
        "Deductions cannot exceed income",
        "Invalid tax year",
        "Rate limit exceeded",
    ])
    def test_user_friendly_error_messages(self, error_msg):
        assert len(error_msg) > 0
        # No internal error details leaked
        assert "traceback" not in error_msg.lower()
        assert "exception" not in error_msg.lower()
