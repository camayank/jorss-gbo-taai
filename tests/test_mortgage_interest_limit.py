"""
Tests for Mortgage Interest Deduction Limits (TCJA - IRS Publication 936)

Tests cover:
- Full deduction when principal under $750k limit
- Proportional reduction when principal exceeds limit
- Grandfathered debt ($1M limit for pre-Dec 2017 mortgages)
- MFS halved limits ($375k / $500k)
- Home equity interest exclusion (post-TCJA)
- Points follow same limitation ratio
- Backward compatibility (no principal = full deduction)
- Boundary conditions
"""

import pytest
from src.models.deductions import ItemizedDeductions


class TestMortgageUnderLimit:
    """Tests for mortgages under the TCJA $750k limit."""

    def test_full_deduction_under_limit(self):
        """Full interest deductible when principal under $750k."""
        itemized = ItemizedDeductions(
            mortgage_interest=25000.0,
            mortgage_principal=500000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 25000.0

    def test_full_deduction_at_exactly_limit(self):
        """Full interest deductible when principal exactly at $750k."""
        itemized = ItemizedDeductions(
            mortgage_interest=35000.0,
            mortgage_principal=750000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 35000.0

    def test_full_deduction_with_points(self):
        """Points also fully deductible under limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=20000.0,
            points_paid=3000.0,
            mortgage_principal=600000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 23000.0


class TestMortgageOverLimit:
    """Tests for mortgages exceeding the $750k limit."""

    def test_proportional_reduction_over_limit(self):
        """Interest reduced proportionally when over $750k limit."""
        # $1M principal, $750k limit = 75% deductible
        itemized = ItemizedDeductions(
            mortgage_interest=50000.0,
            mortgage_principal=1000000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        # 50000 * (750000 / 1000000) = 37500
        assert result == 37500.0

    def test_proportional_reduction_1_5_million(self):
        """50% reduction for $1.5M mortgage."""
        # $1.5M principal, $750k limit = 50% deductible
        itemized = ItemizedDeductions(
            mortgage_interest=75000.0,
            mortgage_principal=1500000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        # 75000 * (750000 / 1500000) = 37500
        assert result == 37500.0

    def test_proportional_reduction_with_points(self):
        """Points also reduced proportionally."""
        itemized = ItemizedDeductions(
            mortgage_interest=40000.0,
            points_paid=5000.0,
            mortgage_principal=1000000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        # Interest: 40000 * 0.75 = 30000
        # Points: 5000 * 0.75 = 3750
        # Total: 33750
        assert result == 33750.0


class TestGrandfatheredDebt:
    """Tests for pre-TCJA grandfathered mortgages ($1M limit)."""

    def test_full_deduction_under_grandfathered_limit(self):
        """Full deduction for grandfathered debt under $1M."""
        itemized = ItemizedDeductions(
            mortgage_interest=40000.0,
            mortgage_principal=800000.0,
            is_grandfathered_debt=True,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 40000.0

    def test_full_deduction_at_grandfathered_limit(self):
        """Full deduction at exactly $1M for grandfathered debt."""
        itemized = ItemizedDeductions(
            mortgage_interest=50000.0,
            mortgage_principal=1000000.0,
            is_grandfathered_debt=True,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 50000.0

    def test_proportional_reduction_over_grandfathered_limit(self):
        """Proportional reduction for grandfathered debt over $1M."""
        # $1.2M principal, $1M limit = 83.33% deductible
        itemized = ItemizedDeductions(
            mortgage_interest=60000.0,
            mortgage_principal=1200000.0,
            is_grandfathered_debt=True,
        )

        result = itemized.get_limited_mortgage_interest("single")
        # 60000 * (1000000 / 1200000) = 50000
        assert result == 50000.0


class TestMFSHalvedLimits:
    """Tests for Married Filing Separately halved limits."""

    def test_mfs_full_deduction_under_375k(self):
        """MFS: Full deduction under $375k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=15000.0,
            mortgage_principal=300000.0,
        )

        result = itemized.get_limited_mortgage_interest("married_separate")
        assert result == 15000.0

    def test_mfs_proportional_over_375k(self):
        """MFS: Proportional reduction over $375k limit."""
        # $500k principal, $375k limit = 75% deductible
        itemized = ItemizedDeductions(
            mortgage_interest=25000.0,
            mortgage_principal=500000.0,
        )

        result = itemized.get_limited_mortgage_interest("married_separate")
        # 25000 * (375000 / 500000) = 18750
        assert result == 18750.0

    def test_mfs_grandfathered_500k_limit(self):
        """MFS: Grandfathered debt uses $500k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=30000.0,
            mortgage_principal=600000.0,
            is_grandfathered_debt=True,
        )

        result = itemized.get_limited_mortgage_interest("married_separate")
        # 30000 * (500000 / 600000) = 25000
        assert result == 25000.0

    def test_mfs_under_grandfathered_limit(self):
        """MFS: Full deduction under grandfathered $500k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=20000.0,
            mortgage_principal=400000.0,
            is_grandfathered_debt=True,
        )

        result = itemized.get_limited_mortgage_interest("married_separate")
        assert result == 20000.0


class TestHomeEquityNotDeductible:
    """Tests for home equity interest exclusion (post-TCJA)."""

    def test_home_equity_interest_not_included(self):
        """Home equity interest is tracked but NOT deductible."""
        itemized = ItemizedDeductions(
            mortgage_interest=20000.0,
            home_equity_interest=5000.0,
            mortgage_principal=400000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        # Only mortgage interest, NOT home equity
        assert result == 20000.0

    def test_home_equity_only_returns_zero(self):
        """Only home equity interest returns zero deduction."""
        itemized = ItemizedDeductions(
            mortgage_interest=0.0,
            home_equity_interest=10000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 0.0


class TestBackwardCompatibility:
    """Tests for backward compatibility when principal not provided."""

    def test_no_principal_full_deduction(self):
        """No principal provided = full deduction (legacy behavior)."""
        itemized = ItemizedDeductions(
            mortgage_interest=50000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 50000.0

    def test_zero_principal_full_deduction(self):
        """Zero principal = full deduction (legacy behavior)."""
        itemized = ItemizedDeductions(
            mortgage_interest=50000.0,
            mortgage_principal=0.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 50000.0


class TestBoundaryConditions:
    """Tests for exact boundary values."""

    def test_exactly_one_dollar_over_limit(self):
        """$750,001 principal triggers proportional reduction."""
        itemized = ItemizedDeductions(
            mortgage_interest=35000.0,
            mortgage_principal=750001.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        # Very slight reduction
        expected = round(35000.0 * (750000.0 / 750001.0), 2)
        assert result == expected

    def test_zero_interest_returns_zero(self):
        """Zero interest always returns zero."""
        itemized = ItemizedDeductions(
            mortgage_interest=0.0,
            mortgage_principal=500000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 0.0

    def test_negative_interest_not_possible(self):
        """Negative interest prevented by field validation."""
        # Pydantic validation with ge=0 prevents negative values
        with pytest.raises(Exception):
            ItemizedDeductions(mortgage_interest=-1000.0)


class TestAllFilingStatuses:
    """Tests for all filing status variations."""

    def test_single_uses_750k_limit(self):
        """Single uses $750k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=40000.0,
            mortgage_principal=1000000.0,
        )

        result = itemized.get_limited_mortgage_interest("single")
        assert result == 30000.0  # 75%

    def test_mfj_uses_750k_limit(self):
        """Married Filing Jointly uses $750k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=40000.0,
            mortgage_principal=1000000.0,
        )

        result = itemized.get_limited_mortgage_interest("married_joint")
        assert result == 30000.0  # 75%

    def test_hoh_uses_750k_limit(self):
        """Head of Household uses $750k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=40000.0,
            mortgage_principal=1000000.0,
        )

        result = itemized.get_limited_mortgage_interest("head_of_household")
        assert result == 30000.0  # 75%

    def test_qw_uses_750k_limit(self):
        """Qualifying Widow(er) uses $750k limit."""
        itemized = ItemizedDeductions(
            mortgage_interest=40000.0,
            mortgage_principal=1000000.0,
        )

        result = itemized.get_limited_mortgage_interest("qualifying_widow")
        assert result == 30000.0  # 75%


class TestIntegrationWithTotalItemized:
    """Tests for integration with get_total_itemized()."""

    def test_limited_interest_in_total(self):
        """Limited mortgage interest flows through to total itemized."""
        itemized = ItemizedDeductions(
            mortgage_interest=50000.0,
            mortgage_principal=1000000.0,  # Over limit
            state_local_income_tax=8000.0,
        )

        # Direct call to get_limited_mortgage_interest
        limited = itemized.get_limited_mortgage_interest("single")
        assert limited == 37500.0  # 75% of 50000

        # Total should include limited amount
        total = itemized.get_total_itemized(agi=100000.0, filing_status="single")
        # 37500 (limited mortgage) + 8000 (SALT) = 45500
        assert total == 45500.0

    def test_mfs_limit_in_total(self):
        """MFS halved limit flows through to total itemized."""
        itemized = ItemizedDeductions(
            mortgage_interest=25000.0,
            mortgage_principal=500000.0,
            state_local_income_tax=5000.0,
        )

        total = itemized.get_total_itemized(agi=100000.0, filing_status="married_separate")
        # 18750 (75% of 25000) + 5000 (SALT) = 23750
        assert total == 23750.0
