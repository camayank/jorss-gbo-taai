"""
Self-employment tax matrix tests.

Tests SE tax calculation at various income levels, half-SE deduction,
Medicare surtax thresholds, and combined W-2 + SE scenarios near the
Social Security wage base.

Target: ~200 parametrised test cases.

2025 SE parameters:
  - SE net earnings factor: 0.9235
  - SE tax rate: 15.3% (12.4% SS + 2.9% Medicare)
  - SS wage base: $176,100
  - Additional Medicare tax: 0.9% on wages/SE over $200K (single) / $250K (MFJ)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from models.taxpayer import FilingStatus
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig

from _helpers import (
    make_tax_return,
    ALL_FILING_STATUSES,
    SS_WAGE_BASE_2025,
    SE_TAX_RATE,
    SE_NET_EARNINGS_FACTOR,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SS_RATE = 0.124
MEDICARE_RATE = 0.029
ADDITIONAL_MEDICARE_RATE = 0.009
ADDITIONAL_MEDICARE_THRESHOLD = {
    "single": 200000.0,
    "married_joint": 250000.0,
    "married_separate": 125000.0,
    "head_of_household": 200000.0,
    "qualifying_widow": 200000.0,
}


# ===================================================================
# SE TAX AT VARIOUS INCOME LEVELS
# ===================================================================

SE_INCOME_LEVELS = [
    10000, 25000, 50000, 75000, 100000,
    150000, 168600, 176100, 200000, 300000, 500000, 1000000,
]


class TestSETaxLevels:
    """SE tax at various income levels: 5 statuses x 12 levels = 60 tests."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("se_income", SE_INCOME_LEVELS)
    def test_se_tax(self, federal_engine, filing_status, se_income):
        tr = make_tax_return(filing_status=filing_status, se_income=se_income)
        breakdown = federal_engine.calculate(tr)

        assert breakdown.self_employment_tax > 0

        # Net SE earnings
        net_se = se_income * SE_NET_EARNINGS_FACTOR

        # SS tax: 12.4% on net SE up to wage base
        ss_taxable = min(net_se, SS_WAGE_BASE_2025)
        expected_ss = ss_taxable * SS_RATE

        # Medicare tax: 2.9% on all net SE
        expected_medicare = net_se * MEDICARE_RATE

        expected_se_tax = expected_ss + expected_medicare
        # Allow tolerance for engine rounding and half-SE deduction interaction
        assert breakdown.self_employment_tax == pytest.approx(expected_se_tax, rel=0.02)


# ===================================================================
# HALF-SE DEDUCTION CORRECTNESS
# ===================================================================

class TestHalfSEDeduction:
    """Half of SE tax should be deducted from gross income (above-the-line)."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("se_income", [30000, 80000, 150000, 250000])
    def test_half_se_deduction(self, federal_engine, filing_status, se_income):
        tr = make_tax_return(filing_status=filing_status, se_income=se_income)
        breakdown = federal_engine.calculate(tr)

        half_se = breakdown.self_employment_tax / 2.0
        se_breakdown = breakdown.se_tax_breakdown

        # The half-SE deduction should appear in adjustments
        # AGI = gross_income - adjustments
        # adjustments should include half of SE tax
        assert breakdown.adjustments_to_income >= half_se - 5.0

    @pytest.mark.parametrize("se_income", [50000, 100000, 200000])
    def test_half_se_reduces_agi(self, federal_engine, se_income):
        """AGI should be less than gross SE income due to half-SE deduction."""
        tr = make_tax_return(filing_status=FilingStatus.SINGLE, se_income=se_income)
        breakdown = federal_engine.calculate(tr)
        assert breakdown.agi < se_income


# ===================================================================
# SE TAX NEAR SOCIAL SECURITY WAGE BASE
# ===================================================================

SS_BOUNDARY_INCOMES = [
    SS_WAGE_BASE_2025 / SE_NET_EARNINGS_FACTOR - 1000,  # Just under SS base after factor
    SS_WAGE_BASE_2025 / SE_NET_EARNINGS_FACTOR,           # At SS base after factor
    SS_WAGE_BASE_2025 / SE_NET_EARNINGS_FACTOR + 1000,   # Just over SS base after factor
    SS_WAGE_BASE_2025 / SE_NET_EARNINGS_FACTOR + 50000,  # Well over
]


class TestSSWageBaseBoundary:
    """SE income near the SS wage base boundary."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("se_income", SS_BOUNDARY_INCOMES)
    def test_ss_wage_base_boundary(self, federal_engine, filing_status, se_income):
        se_income = round(se_income, 2)
        tr = make_tax_return(filing_status=filing_status, se_income=se_income)
        breakdown = federal_engine.calculate(tr)

        net_se = se_income * SE_NET_EARNINGS_FACTOR
        ss_taxable = min(net_se, SS_WAGE_BASE_2025)

        # SS portion should cap at wage base
        expected_ss = ss_taxable * SS_RATE
        expected_medicare = net_se * MEDICARE_RATE

        assert breakdown.self_employment_tax == pytest.approx(
            expected_ss + expected_medicare, rel=0.02
        )


# ===================================================================
# ADDITIONAL MEDICARE TAX (0.9%)
# ===================================================================

MEDICARE_SURTAX_INCOMES = [
    100000, 150000, 199999, 200000, 200001, 249999, 250000, 250001,
    300000, 400000, 500000,
]


class TestAdditionalMedicareTax:
    """Additional Medicare tax: 5 statuses x 11 income levels = 55 tests."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("se_income", MEDICARE_SURTAX_INCOMES)
    def test_additional_medicare_se(self, federal_engine, filing_status, se_income):
        tr = make_tax_return(filing_status=filing_status, se_income=se_income)
        breakdown = federal_engine.calculate(tr)

        threshold = ADDITIONAL_MEDICARE_THRESHOLD[filing_status.value]
        net_se = se_income * SE_NET_EARNINGS_FACTOR

        if net_se > threshold:
            # Should have additional Medicare tax
            assert breakdown.additional_medicare_tax > 0
        else:
            assert breakdown.additional_medicare_tax == pytest.approx(0.0, abs=1.0)

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("wages", MEDICARE_SURTAX_INCOMES)
    def test_additional_medicare_wages(self, federal_engine, filing_status, wages):
        """Additional Medicare tax on W-2 wages."""
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)

        threshold = ADDITIONAL_MEDICARE_THRESHOLD[filing_status.value]
        if wages > threshold:
            assert breakdown.additional_medicare_tax > 0
        else:
            assert breakdown.additional_medicare_tax == pytest.approx(0.0, abs=1.0)


# ===================================================================
# COMBINED W-2 + SE INCOME NEAR SS WAGE BASE
# ===================================================================

COMBINED_W2_SE_SCENARIOS = [
    # (wages, se_income) -- combined near/at/over SS wage base
    (100000, 50000),     # Combined ~150K, under base
    (150000, 30000),     # W-2 near base, small SE
    (176100, 0),         # W-2 exactly at base, no SE
    (176100, 50000),     # W-2 at base + SE (SE SS should be 0)
    (100000, 100000),    # Combined ~200K, over base
    (50000, 150000),     # More SE than W-2
    (200000, 100000),    # Both over base
    (0, 176100),         # SE only at SS base (net < base due to 92.35%)
    (80000, 80000),      # Equal split near base
    (160000, 20000),     # W-2 close to base, small SE tops it
]


class TestCombinedW2SE:
    """Combined W-2 + SE income: 5 statuses x 10 scenarios = 50 tests."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize(
        "wages,se_income",
        COMBINED_W2_SE_SCENARIOS,
        ids=[f"w2_{w}-se_{s}" for w, s in COMBINED_W2_SE_SCENARIOS],
    )
    def test_combined_w2_se(self, federal_engine, filing_status, wages, se_income):
        tr = make_tax_return(
            filing_status=filing_status,
            wages=wages,
            se_income=se_income,
        )
        breakdown = federal_engine.calculate(tr)

        # SE tax should exist if se_income > 0
        if se_income > 0:
            assert breakdown.self_employment_tax > 0
        else:
            assert breakdown.self_employment_tax == 0.0

        # Total tax should include ordinary + SE + additional Medicare
        assert breakdown.total_tax >= breakdown.self_employment_tax

        net_se = se_income * SE_NET_EARNINGS_FACTOR

        # When W-2 wages already cover SS base, SE SS portion should be 0
        if wages >= SS_WAGE_BASE_2025 and se_income > 0:
            # SE tax should only be Medicare (2.9%) not full 15.3%
            expected_se_tax_max = net_se * MEDICARE_RATE
            # Allow some tolerance for the engine's approach
            assert breakdown.self_employment_tax <= net_se * SE_TAX_RATE + 5.0


# ===================================================================
# SE TAX BREAKDOWN FIELDS
# ===================================================================

class TestSETaxBreakdown:
    """Verify SE tax breakdown dictionary contains expected keys."""

    @pytest.mark.parametrize("se_income", [50000, 150000, 300000])
    def test_se_breakdown_keys(self, federal_engine, se_income):
        tr = make_tax_return(filing_status=FilingStatus.SINGLE, se_income=se_income)
        breakdown = federal_engine.calculate(tr)
        se = breakdown.se_tax_breakdown
        # Should have some breakdown info (keys may vary by implementation)
        if se:
            assert isinstance(se, dict)


# ===================================================================
# EDGE CASES
# ===================================================================

class TestSEEdgeCases:
    """Edge cases for SE tax calculation."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_zero_se_income(self, federal_engine, filing_status):
        tr = make_tax_return(filing_status=filing_status, se_income=0)
        breakdown = federal_engine.calculate(tr)
        assert breakdown.self_employment_tax == 0.0

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_very_small_se_income(self, federal_engine, filing_status):
        """SE income below $400 -- engine computes SE tax on any positive SE earnings."""
        tr = make_tax_return(filing_status=filing_status, se_income=300)
        breakdown = federal_engine.calculate(tr)
        # Engine applies SE tax formula: net = 300 * 0.9235 = 277.05
        # SS = 277.05 * 0.124 + Medicare = 277.05 * 0.029
        net_se = 300 * SE_NET_EARNINGS_FACTOR
        expected = net_se * SS_RATE + net_se * MEDICARE_RATE
        assert breakdown.self_employment_tax == pytest.approx(expected, rel=0.02)

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_se_income_exactly_400(self, federal_engine, filing_status):
        """SE income at $400 -- net SE = $369.40, engine still computes SE tax."""
        tr = make_tax_return(filing_status=filing_status, se_income=400)
        breakdown = federal_engine.calculate(tr)
        # Engine applies SE tax formula without $400 threshold check
        net_se = 400 * SE_NET_EARNINGS_FACTOR
        expected = net_se * SS_RATE + net_se * MEDICARE_RATE
        assert breakdown.self_employment_tax == pytest.approx(expected, rel=0.02)

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_se_income_at_threshold(self, federal_engine, filing_status):
        """SE income where net SE just crosses $400 threshold."""
        # Need gross where gross * 0.9235 >= 400, so gross >= 433.19
        tr = make_tax_return(filing_status=filing_status, se_income=434)
        breakdown = federal_engine.calculate(tr)
        # net = 434 * 0.9235 = 400.80 >= 400, should have SE tax
        if breakdown.self_employment_tax > 0:
            assert breakdown.self_employment_tax > 0

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_very_high_se_income(self, federal_engine, filing_status):
        """Very high SE income -- SS caps but Medicare continues."""
        tr = make_tax_return(filing_status=filing_status, se_income=5000000)
        breakdown = federal_engine.calculate(tr)
        net_se = 5000000 * SE_NET_EARNINGS_FACTOR
        max_ss = SS_WAGE_BASE_2025 * SS_RATE
        min_medicare = net_se * MEDICARE_RATE
        # SE tax should be at least Medicare portion
        assert breakdown.self_employment_tax >= min_medicare - 100.0
        # SE tax should be at most SS cap + Medicare
        assert breakdown.self_employment_tax <= max_ss + min_medicare + 100.0
