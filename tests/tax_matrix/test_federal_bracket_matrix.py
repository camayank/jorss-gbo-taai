"""
Federal tax bracket matrix tests.

Tests all 7 bracket boundaries across 5 filing statuses with multiple
income types.  Uses the real FederalTaxEngine -- no mocking.

Target: ~400 parametrised test cases.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from models.taxpayer import FilingStatus
from models.tax_return import TaxReturn
from calculator.tax_calculator import TaxCalculator
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig

from _helpers import (
    make_tax_return,
    compute_expected_tax_on_ordinary,
    BRACKETS_2025,
    STD_DEDUCTION,
    ALL_FILING_STATUSES,
)


# ---------------------------------------------------------------------------
# Bracket boundary incomes  (taxable_income just under / at / just over each
# bracket threshold).  We add std deduction back to get wages.
# ---------------------------------------------------------------------------

def _boundary_params():
    """
    Yield (filing_status, wages, bracket_rate) for each bracket boundary.

    For each filing status we test:
      - $1 below each bracket threshold  (should be taxed at prior rate)
      - exactly at the threshold          (first dollar at new rate)
      - $1 above the threshold            (new rate applies)
    That gives 3 x 7 boundaries x 5 statuses = 105 cases (some overlap at 0).
    """
    params = []
    for fs in ALL_FILING_STATUSES:
        fs_key = fs.value
        std = STD_DEDUCTION[fs_key]
        brackets = BRACKETS_2025[fs_key]
        for i, (threshold, rate) in enumerate(brackets):
            if threshold == 0:
                # Test a small income in the 10% bracket
                for taxable in [1, 100, 5000]:
                    wages = taxable + std
                    params.append((fs, wages, taxable, rate))
                continue
            # just under
            taxable_under = threshold - 1
            params.append((fs, taxable_under + std, taxable_under, brackets[i - 1][1]))
            # at boundary -- engine uses strict > so at threshold the prior rate still applies
            taxable_at = threshold
            params.append((fs, taxable_at + std, taxable_at, brackets[i - 1][1]))
            # just over
            taxable_over = threshold + 1
            params.append((fs, taxable_over + std, taxable_over, rate))
    return params


BOUNDARY_PARAMS = _boundary_params()


class TestBracketBoundaries:
    """Verify that the engine applies the correct marginal rate at each bracket boundary."""

    @pytest.mark.parametrize(
        "filing_status,wages,expected_taxable,marginal_rate",
        BOUNDARY_PARAMS,
        ids=[
            f"{fs.value}-taxable_{ti}"
            for fs, w, ti, r in BOUNDARY_PARAMS
        ],
    )
    def test_bracket_boundary(self, federal_engine, filing_status, wages, expected_taxable, marginal_rate):
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)
        # The taxable income should roughly match (allow small rounding)
        assert breakdown.taxable_income == pytest.approx(expected_taxable, abs=2.0)
        # The marginal rate recorded should match (engine returns percentage, e.g. 10.0 for 10%)
        assert breakdown.marginal_tax_rate == pytest.approx(marginal_rate * 100, abs=0.5)


# ---------------------------------------------------------------------------
# Bracket tax correctness -- verify total ordinary tax matches manual calc
# ---------------------------------------------------------------------------

def _tax_correctness_params():
    """
    Various taxable income levels x filing statuses to verify total ordinary tax.
    """
    taxable_levels = [
        0, 1, 5000, 10000, 11924, 11926, 25000, 48474, 48476,
        75000, 100000, 103349, 103351, 150000, 197299, 197301,
        200000, 250524, 250526, 400000, 500000, 626349, 626351,
        750000, 1000000, 2000000,
    ]
    params = []
    for fs in ALL_FILING_STATUSES:
        std = STD_DEDUCTION[fs.value]
        for taxable in taxable_levels:
            wages = taxable + std
            if wages < 0:
                continue
            expected = compute_expected_tax_on_ordinary(taxable, fs.value)
            params.append((fs, wages, taxable, expected))
    return params


TAX_CORRECTNESS_PARAMS = _tax_correctness_params()


class TestOrdinaryTaxCorrectness:
    """Verify that ordinary income tax equals the manually computed amount."""

    @pytest.mark.parametrize(
        "filing_status,wages,taxable,expected_tax",
        TAX_CORRECTNESS_PARAMS,
        ids=[
            f"{fs.value}-taxable_{ti}"
            for fs, w, ti, et in TAX_CORRECTNESS_PARAMS
        ],
    )
    def test_ordinary_tax_amount(self, federal_engine, filing_status, wages, taxable, expected_tax):
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)
        # Ordinary income tax should be close to our manual calculation
        # Allow tolerance for rounding differences in the engine
        assert breakdown.ordinary_income_tax == pytest.approx(expected_tax, abs=5.0)


# ---------------------------------------------------------------------------
# Income-type matrix: wages-only, SE-only, investment mix
# ---------------------------------------------------------------------------

INCOME_TYPE_AMOUNTS = [25000, 75000, 150000, 300000, 600000]


class TestIncomeTypeWagesOnly:
    """Tax calculation with W-2 wages as sole income source."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("wages", INCOME_TYPE_AMOUNTS)
    def test_wages_only(self, federal_engine, filing_status, wages):
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)
        # At low income levels (e.g. $25k MFJ), refundable credits like ACTC
        # can exceed tax liability, making total_tax negative.
        assert breakdown.ordinary_income_tax >= 0
        # No SE tax for W-2 income
        assert breakdown.self_employment_tax == 0.0


class TestIncomeTypeSEOnly:
    """Tax calculation with self-employment as sole income source."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("se_income", INCOME_TYPE_AMOUNTS)
    def test_se_only(self, federal_engine, filing_status, se_income):
        tr = make_tax_return(filing_status=filing_status, se_income=se_income)
        breakdown = federal_engine.calculate(tr)
        assert breakdown.total_tax >= 0
        # SE income should generate SE tax
        assert breakdown.self_employment_tax > 0


class TestIncomeTypeInvestmentMix:
    """Tax calculation with a mix of investment income (interest, dividends, LTCG)."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("total_investment", INCOME_TYPE_AMOUNTS)
    def test_investment_mix(self, federal_engine, filing_status, total_investment):
        interest = total_investment * 0.3
        dividends = total_investment * 0.3
        qualified_div = dividends * 0.8
        lt_cap_gains = total_investment * 0.4
        tr = make_tax_return(
            filing_status=filing_status,
            interest=interest,
            dividends=dividends,
            qualified_dividends=qualified_div,
            lt_cap_gains=lt_cap_gains,
        )
        breakdown = federal_engine.calculate(tr)
        assert breakdown.total_tax >= 0
        # No SE tax for investment income
        assert breakdown.self_employment_tax == 0.0


# ---------------------------------------------------------------------------
# Combined income matrix: wages + SE + investment at various ratios
# ---------------------------------------------------------------------------

COMBINED_SCENARIOS = [
    # (wages, se_income, interest, dividends, ltcg)
    (50000, 30000, 5000, 2000, 3000),
    (100000, 50000, 10000, 5000, 10000),
    (75000, 0, 20000, 10000, 15000),
    (0, 80000, 15000, 8000, 12000),
    (200000, 100000, 30000, 20000, 50000),
    (30000, 10000, 0, 0, 0),
    (0, 0, 50000, 25000, 75000),
]


class TestCombinedIncome:
    """Tax calculation with combined income sources across all filing statuses."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize(
        "wages,se_income,interest,dividends,ltcg",
        COMBINED_SCENARIOS,
    )
    def test_combined_income(self, federal_engine, filing_status, wages, se_income, interest, dividends, ltcg):
        tr = make_tax_return(
            filing_status=filing_status,
            wages=wages,
            se_income=se_income,
            interest=interest,
            dividends=dividends,
            qualified_dividends=dividends * 0.7,
            lt_cap_gains=ltcg,
        )
        breakdown = federal_engine.calculate(tr)
        assert breakdown.total_tax >= 0
        assert breakdown.agi > 0


# ---------------------------------------------------------------------------
# Effective tax rate monotonicity -- higher income => higher effective rate
# ---------------------------------------------------------------------------

class TestEffectiveRateMonotonicity:
    """Effective tax rate should generally increase with income."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_effective_rate_increases(self, federal_engine, filing_status):
        income_levels = [20000, 50000, 100000, 200000, 500000, 1000000]
        rates = []
        for wages in income_levels:
            tr = make_tax_return(filing_status=filing_status, wages=wages)
            breakdown = federal_engine.calculate(tr)
            if breakdown.agi > 0:
                eff_rate = breakdown.total_tax / breakdown.agi
                rates.append(eff_rate)
            else:
                rates.append(0.0)
        # Effective rate should be non-decreasing (allow small tolerance for rounding)
        for i in range(1, len(rates)):
            assert rates[i] >= rates[i - 1] - 0.001, (
                f"{filing_status.value}: rate at {income_levels[i]} ({rates[i]:.4f}) "
                f"< rate at {income_levels[i-1]} ({rates[i-1]:.4f})"
            )


# ---------------------------------------------------------------------------
# Zero and negative scenarios
# ---------------------------------------------------------------------------

class TestZeroIncome:
    """Edge cases with zero or minimal income."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_zero_income_zero_tax(self, federal_engine, filing_status):
        tr = make_tax_return(filing_status=filing_status, wages=0)
        breakdown = federal_engine.calculate(tr)
        assert breakdown.total_tax == 0.0
        assert breakdown.taxable_income == 0.0

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_income_below_standard_deduction(self, federal_engine, filing_status):
        std = STD_DEDUCTION[filing_status.value]
        wages = std - 1000 if std > 1000 else 500
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)
        # Taxable income should be 0 since wages < standard deduction
        assert breakdown.taxable_income == 0.0
        assert breakdown.ordinary_income_tax == 0.0

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_income_exactly_at_standard_deduction(self, federal_engine, filing_status):
        std = STD_DEDUCTION[filing_status.value]
        tr = make_tax_return(filing_status=filing_status, wages=std)
        breakdown = federal_engine.calculate(tr)
        assert breakdown.taxable_income == pytest.approx(0.0, abs=1.0)


# ---------------------------------------------------------------------------
# High-income bracket tests (37% bracket)
# ---------------------------------------------------------------------------

HIGH_INCOME_LEVELS = [700000, 800000, 1000000, 2000000, 5000000, 10000000]


class TestHighIncomeBracket:
    """Verify the 37% top bracket applies correctly for high earners."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("wages", HIGH_INCOME_LEVELS)
    def test_top_bracket(self, federal_engine, filing_status, wages):
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)
        # At these income levels the marginal rate should be 35%+ (engine returns percentage)
        assert breakdown.marginal_tax_rate >= 35.0
        assert breakdown.total_tax > 0


# ---------------------------------------------------------------------------
# Bracket breakdown verification
# ---------------------------------------------------------------------------

class TestBracketBreakdown:
    """Verify the bracket_breakdown list in CalculationBreakdown sums correctly."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("wages", [30000, 80000, 200000, 500000])
    def test_bracket_breakdown_sums(self, federal_engine, filing_status, wages):
        tr = make_tax_return(filing_status=filing_status, wages=wages)
        breakdown = federal_engine.calculate(tr)
        if breakdown.bracket_breakdown:
            total_from_brackets = sum(
                b.get("tax", b.get("tax_amount", 0)) for b in breakdown.bracket_breakdown
            )
            assert total_from_brackets == pytest.approx(breakdown.ordinary_income_tax, abs=5.0)
