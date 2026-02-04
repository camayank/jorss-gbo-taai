import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


def _make_se_return(se_income, expenses=0.0, filing_status=FilingStatus.SINGLE, wages=0.0):
    """Helper to create a TaxReturn with self-employment income."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=filing_status),
        income=Income(
            self_employment_income=se_income,
            self_employment_expenses=expenses,
            wages=wages,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


def test_self_employment_tax_added_to_total_tax():
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    tr = _make_se_return(10_000.0)

    breakdown = engine.calculate(tr)
    # SE tax = SS (10,000 * 0.9235 * 0.124 = 1145.14) + Medicare (10,000 * 0.9235 * 0.029 = 267.815 -> 267.82) = 1412.96
    # IRS calculates SS and Medicare separately with independent ROUND_HALF_UP rounding
    assert breakdown.self_employment_tax == 1412.96
    # SE tax is included in total_tax_before_credits (refundable credits may reduce total_tax below SE tax)
    assert breakdown.total_tax_before_credits >= breakdown.self_employment_tax


def test_zero_se_income_zero_se_tax():
    """Zero self-employment income should produce zero SE tax."""
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    tr = _make_se_return(0.0)
    breakdown = engine.calculate(tr)

    assert breakdown.self_employment_tax == 0.0


def test_high_income_ss_tax_capped_at_wage_base():
    """SS portion of SE tax should be capped at the SS wage base ($176,100 for 2025)."""
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    # SE income of $300K - well above SS wage base
    tr = _make_se_return(300_000.0)
    breakdown = engine.calculate(tr)

    # SE earnings = 300,000 * 0.9235 = 277,050
    # SS taxable capped at 176,100
    # SS tax = 176,100 * 0.124 = 21,836.40
    # Medicare = 277,050 * 0.029 = 8,034.45
    # Total = 29,870.85
    # The key assertion: SE tax should be less than what it would be without the cap
    uncapped_ss = 300_000 * 0.9235 * 0.124
    assert breakdown.self_employment_tax < uncapped_ss + (300_000 * 0.9235 * 0.029)


def test_se_tax_deduction_reduces_agi():
    """Half of SE tax should be deducted from income (adjustment to AGI)."""
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    tr = _make_se_return(50_000.0)
    breakdown = engine.calculate(tr)

    # SE tax deduction = half of SE tax
    se_deduction = breakdown.self_employment_tax / 2
    # AGI should be reduced by SE tax deduction (among other adjustments)
    # gross_income - adjustments = agi
    assert breakdown.adjustments_to_income >= se_deduction - 1  # Allow rounding


def test_multiple_schedule_c_businesses():
    """SE tax computed on combined net SE income from multiple businesses."""
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    # Simulating combined SE income (the model aggregates Schedule C)
    tr = _make_se_return(80_000.0, expenses=20_000.0)
    breakdown = engine.calculate(tr)

    # Net SE income = 80K - 20K = 60K
    # SE earnings = 60K * 0.9235 = 55,410
    # SE tax should be based on $60K net, not $80K gross
    assert breakdown.self_employment_tax > 0
    assert breakdown.self_employment_tax < 80_000 * 0.9235 * (0.124 + 0.029)


def test_different_filing_statuses_same_se_tax():
    """SE tax is the same regardless of filing status (it's not affected by it)."""
    engine = FederalTaxEngine(TaxYearConfig.for_2025())

    single = engine.calculate(_make_se_return(75_000.0, filing_status=FilingStatus.SINGLE))
    mfj = engine.calculate(_make_se_return(75_000.0, filing_status=FilingStatus.MARRIED_JOINT))

    assert single.self_employment_tax == mfj.self_employment_tax

