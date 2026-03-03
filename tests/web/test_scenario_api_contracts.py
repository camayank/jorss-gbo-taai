"""
Comprehensive tests for Scenario API — filing status comparison, deduction bunching,
entity structure, retirement optimization, and validation.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from web.scenario_api import (
    FilingStatusScenarioRequest,
    DeductionBunchingRequest,
    EntityStructureRequest,
    RetirementOptimizationRequest,
    _calculate_simplified_tax,
    _get_marginal_rate,
)
from models.taxpayer import FilingStatus


# ===================================================================
# FilingStatusScenarioRequest VALIDATION
# ===================================================================

class TestFilingStatusRequest:

    def test_valid_request(self):
        req = FilingStatusScenarioRequest(total_income=75000)
        assert req.total_income == 75000

    @pytest.mark.parametrize("income", [0, 1000, 50000, 100000, 1000000, 10000000])
    def test_valid_income_range(self, income):
        req = FilingStatusScenarioRequest(total_income=income)
        assert req.total_income == income

    def test_negative_income_rejected(self):
        with pytest.raises(Exception):
            FilingStatusScenarioRequest(total_income=-1)

    def test_income_exceeds_max(self):
        with pytest.raises(Exception):
            FilingStatusScenarioRequest(total_income=10000001)

    def test_default_dependents(self):
        req = FilingStatusScenarioRequest(total_income=75000)
        assert req.dependents == 0

    def test_default_age(self):
        req = FilingStatusScenarioRequest(total_income=75000)
        assert req.age == 35

    @pytest.mark.parametrize("dependents", [0, 1, 5, 10, 20])
    def test_valid_dependents(self, dependents):
        req = FilingStatusScenarioRequest(total_income=75000, dependents=dependents)
        assert req.dependents == dependents

    def test_negative_dependents_rejected(self):
        with pytest.raises(Exception):
            FilingStatusScenarioRequest(total_income=75000, dependents=-1)

    def test_too_many_dependents_rejected(self):
        with pytest.raises(Exception):
            FilingStatusScenarioRequest(total_income=75000, dependents=21)

    @pytest.mark.parametrize("age", [0, 18, 35, 65, 100, 120])
    def test_valid_ages(self, age):
        req = FilingStatusScenarioRequest(total_income=75000, age=age)
        assert req.age == age

    def test_deductions_exceeding_income(self):
        with pytest.raises(Exception):
            FilingStatusScenarioRequest(
                total_income=50000, itemized_deductions=60000
            )

    def test_deductions_equal_to_income(self):
        req = FilingStatusScenarioRequest(
            total_income=50000, itemized_deductions=50000
        )
        assert req.itemized_deductions == 50000


# ===================================================================
# DeductionBunchingRequest VALIDATION
# ===================================================================

class TestDeductionBunchingRequest:

    def test_valid_request(self):
        req = DeductionBunchingRequest(
            annual_income=100000,
            annual_charitable=5000,
            mortgage_interest=12000,
            state_local_taxes=8000,
        )
        assert req.annual_income == 100000

    def test_zero_income_rejected(self):
        with pytest.raises(Exception):
            DeductionBunchingRequest(
                annual_income=0,
                annual_charitable=5000,
                mortgage_interest=12000,
                state_local_taxes=8000,
            )

    @pytest.mark.parametrize("salt", [0, 5000, 10000])
    def test_salt_values(self, salt):
        req = DeductionBunchingRequest(
            annual_income=100000,
            annual_charitable=5000,
            mortgage_interest=12000,
            state_local_taxes=salt,
        )
        assert req.state_local_taxes == salt

    def test_salt_exceeds_cap(self):
        with pytest.raises(Exception):
            DeductionBunchingRequest(
                annual_income=100000,
                annual_charitable=5000,
                mortgage_interest=12000,
                state_local_taxes=10001,
            )

    @pytest.mark.parametrize("charitable", [0, 1000, 5000, 50000, 100000])
    def test_charitable_range(self, charitable):
        req = DeductionBunchingRequest(
            annual_income=200000,
            annual_charitable=charitable,
            mortgage_interest=12000,
            state_local_taxes=8000,
        )
        assert req.annual_charitable == charitable


# ===================================================================
# EntityStructureRequest VALIDATION
# ===================================================================

class TestEntityStructureRequest:

    def test_valid_request(self):
        req = EntityStructureRequest(
            gross_revenue=200000,
            business_expenses=80000,
        )
        assert req.gross_revenue == 200000

    def test_expenses_exceed_revenue(self):
        with pytest.raises(Exception):
            EntityStructureRequest(
                gross_revenue=100000,
                business_expenses=200000,
            )

    def test_expenses_equal_revenue(self):
        req = EntityStructureRequest(
            gross_revenue=100000,
            business_expenses=100000,
        )
        assert req.business_expenses == 100000

    @pytest.mark.parametrize("age", [18, 30, 40, 50, 65, 100])
    def test_valid_owner_ages(self, age):
        req = EntityStructureRequest(
            gross_revenue=200000,
            business_expenses=80000,
            owner_age=age,
        )
        assert req.owner_age == age

    @pytest.mark.parametrize("revenue", [0, 50000, 200000, 1000000, 10000000])
    def test_revenue_range(self, revenue):
        req = EntityStructureRequest(
            gross_revenue=revenue,
            business_expenses=0,
        )
        assert req.gross_revenue == revenue


# ===================================================================
# RetirementOptimizationRequest VALIDATION
# ===================================================================

class TestRetirementOptimizationRequest:

    def test_valid_request(self):
        req = RetirementOptimizationRequest(
            annual_income=100000,
            current_401k=20000,
            current_ira=6000,
            age=35,
        )
        assert req.annual_income == 100000

    @pytest.mark.parametrize("k401,age", [
        (20000, 35),
        (60000, 45),
        (66000, 49),
    ])
    def test_valid_401k_contributions(self, k401, age):
        req = RetirementOptimizationRequest(
            annual_income=200000,
            current_401k=k401,
            age=age,
        )
        assert req.current_401k == k401

    @pytest.mark.parametrize("ira,age", [
        (5000, 35),
        (7000, 49),
    ])
    def test_valid_ira_contributions(self, ira, age):
        req = RetirementOptimizationRequest(
            annual_income=200000,
            current_ira=ira,
            age=age,
        )
        assert req.current_ira == ira

    @pytest.mark.parametrize("match_pct", [0, 3, 5, 6, 10, 50, 100])
    def test_employer_match_percentages(self, match_pct):
        req = RetirementOptimizationRequest(
            annual_income=100000,
            employer_match_percent=match_pct,
        )
        assert req.employer_match_percent == match_pct

    def test_default_401k_zero(self):
        req = RetirementOptimizationRequest(annual_income=100000)
        assert req.current_401k == 0

    def test_default_ira_zero(self):
        req = RetirementOptimizationRequest(annual_income=100000)
        assert req.current_ira == 0

    def test_default_age(self):
        req = RetirementOptimizationRequest(annual_income=100000)
        assert req.age == 35


# ===================================================================
# SIMPLIFIED TAX CALCULATION
# ===================================================================

class TestSimplifiedTaxCalculation:

    def test_zero_income(self):
        assert _calculate_simplified_tax(0, FilingStatus.SINGLE) == 0

    def test_negative_income(self):
        assert _calculate_simplified_tax(-1000, FilingStatus.SINGLE) == 0

    @pytest.mark.parametrize("income,expected_min,expected_max", [
        (10000, 0, 2000),
        (50000, 5000, 12000),
        (100000, 15000, 25000),
        (250000, 50000, 80000),
        (500000, 100000, 200000),
    ])
    def test_tax_in_expected_range_single(self, income, expected_min, expected_max):
        tax = _calculate_simplified_tax(income, FilingStatus.SINGLE)
        assert expected_min <= tax <= expected_max

    @pytest.mark.parametrize("status", [
        FilingStatus.SINGLE,
        FilingStatus.MARRIED_JOINT,
        FilingStatus.HEAD_OF_HOUSEHOLD,
    ])
    def test_tax_calculated_for_each_status(self, status):
        tax = _calculate_simplified_tax(75000, status)
        assert tax > 0

    def test_married_joint_lower_than_single(self):
        single_tax = _calculate_simplified_tax(100000, FilingStatus.SINGLE)
        joint_tax = _calculate_simplified_tax(100000, FilingStatus.MARRIED_JOINT)
        assert joint_tax <= single_tax

    def test_progressive_taxation(self):
        tax_50k = _calculate_simplified_tax(50000, FilingStatus.SINGLE)
        tax_100k = _calculate_simplified_tax(100000, FilingStatus.SINGLE)
        tax_200k = _calculate_simplified_tax(200000, FilingStatus.SINGLE)
        assert tax_50k < tax_100k < tax_200k

    @pytest.mark.parametrize("income", [1, 100, 1000, 10000, 100000, 1000000, 5000000])
    def test_tax_always_non_negative(self, income):
        tax = _calculate_simplified_tax(income, FilingStatus.SINGLE)
        assert tax >= 0

    def test_very_high_income(self):
        tax = _calculate_simplified_tax(10_000_000, FilingStatus.SINGLE)
        assert tax > 0


# ===================================================================
# MARGINAL RATE
# ===================================================================

class TestMarginalRate:

    @pytest.mark.parametrize("income,expected_rate", [
        (5000, 0.10),
        (15000, 0.12),
        (60000, 0.22),
        (150000, 0.24),
        (250000, 0.32),
        (400000, 0.35),
        (700000, 0.37),
    ])
    def test_marginal_rates_single(self, income, expected_rate):
        rate = _get_marginal_rate(income, FilingStatus.SINGLE)
        assert rate == expected_rate

    @pytest.mark.parametrize("status", [
        FilingStatus.SINGLE,
        FilingStatus.MARRIED_JOINT,
        FilingStatus.HEAD_OF_HOUSEHOLD,
    ])
    def test_marginal_rate_for_each_status(self, status):
        rate = _get_marginal_rate(75000, status)
        assert 0.10 <= rate <= 0.37

    def test_highest_bracket(self):
        rate = _get_marginal_rate(1_000_000, FilingStatus.SINGLE)
        assert rate == 0.37

    def test_lowest_bracket(self):
        rate = _get_marginal_rate(1000, FilingStatus.SINGLE)
        assert rate == 0.10
