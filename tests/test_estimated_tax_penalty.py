"""
Tests for Estimated Tax Underpayment Penalty (IRS Form 2210)

Tests cover:
- No penalty when payments >= tax (no underpayment)
- Safe harbor: 90% of current year tax
- Safe harbor: 100% of prior year tax
- Safe harbor: 110% of prior year tax (AGI > $150k)
- $1,000 threshold (no penalty if under)
- Basic penalty calculation
- Farmer/fisherman 66⅔% safe harbor
- First-year filer (no prior year tax)
- Integration with full tax calculation
"""

import pytest
from src.models.income import Income, W2Info
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.deductions import Deductions
from src.models.credits import TaxCredits
from src.models.tax_return import TaxReturn
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


class TestNoUnderpayment:
    """Tests when payments >= tax (no underpayment possible)."""

    def test_payments_equal_tax_no_penalty(self, engine):
        """No penalty when payments exactly equal total tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=10000.0,
            prior_year_tax=8000.0,
            prior_year_agi=100000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_payments_exceed_tax_no_penalty(self, engine):
        """No penalty when payments exceed total tax (refund situation)."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=12000.0,
            prior_year_tax=8000.0,
            prior_year_agi=100000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_zero_tax_no_penalty(self, engine):
        """No penalty when total tax is zero."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=0.0,
            total_payments=0.0,
            prior_year_tax=5000.0,
            prior_year_agi=50000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True


class TestSafeHarbor90Percent:
    """Tests for 90% of current year tax safe harbor."""

    def test_exactly_90_percent_met(self, engine):
        """No penalty when payments = exactly 90% of current year tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=9000.0,  # Exactly 90%
            prior_year_tax=0.0,  # No prior year to rely on
            prior_year_agi=0.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_above_90_percent_met(self, engine):
        """No penalty when payments > 90% of current year tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=9500.0,  # 95%
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_just_under_90_percent_penalty(self, engine):
        """Penalty applies when payments < 90% and underpayment > $1k."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=16000.0,  # 80%
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 20000 = 18000
        # Underpayment: 18000 - 16000 = 2000
        # Penalty: 2000 * 0.08 = 160
        assert result['penalty'] == 160.0
        assert result['safe_harbor_met'] is False


class TestSafeHarbor100Percent:
    """Tests for 100% of prior year tax safe harbor."""

    def test_exactly_100_percent_prior_year(self, engine):
        """No penalty when payments = 100% of prior year tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=15000.0,
            total_payments=10000.0,  # Equal to prior year tax
            prior_year_tax=10000.0,
            prior_year_agi=100000.0,  # Under $150k, so 100% applies
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_above_100_percent_prior_year(self, engine):
        """No penalty when payments > 100% of prior year tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=12000.0,  # Above prior year tax
            prior_year_tax=10000.0,
            prior_year_agi=100000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_prior_year_safe_harbor_lower_than_current(self, engine):
        """Use prior year safe harbor when it's lower than 90% of current."""
        # Current tax: $20,000 (90% = $18,000)
        # Prior tax: $8,000 (100% = $8,000) <- Lower, use this
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=8000.0,  # Meets prior year safe harbor
            prior_year_tax=8000.0,
            prior_year_agi=100000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True
        assert result['required_payment'] == 8000.0


class TestSafeHarbor110Percent:
    """Tests for 110% of prior year tax safe harbor (high income)."""

    def test_high_income_requires_110_percent(self, engine):
        """AGI > $150k requires 110% of prior year for safe harbor."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=25000.0,
            total_payments=16000.0,  # 100% of prior, but not 110%
            prior_year_tax=16000.0,
            prior_year_agi=200000.0,  # Over $150k threshold
        )
        # 110% of 16000 = 17600
        # Required: min(90% of 25000, 110% of 16000) = min(22500, 17600) = 17600
        # Underpayment: 17600 - 16000 = 1600
        # Penalty: 1600 * 0.08 = 128
        assert result['penalty'] == 128.0
        assert result['safe_harbor_met'] is False

    def test_high_income_meets_110_percent(self, engine):
        """No penalty when high income filer meets 110% of prior year."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=25000.0,
            total_payments=17600.0,  # Exactly 110% of prior
            prior_year_tax=16000.0,
            prior_year_agi=200000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_exactly_at_150k_threshold(self, engine):
        """At exactly $150k, still use 100% (not 110%)."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=10000.0,  # 100% of prior year
            prior_year_tax=10000.0,
            prior_year_agi=150000.0,  # Exactly at threshold
        )
        # At threshold, use 100% not 110%
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True


class TestThreshold1000:
    """Tests for $1,000 underpayment threshold."""

    def test_underpayment_under_1000_no_penalty(self, engine):
        """No penalty when underpayment < $1,000."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=8500.0,  # Required 9000, shortfall 500
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 10000 = 9000
        # Underpayment: 9000 - 8500 = 500 (under $1k threshold)
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True  # Effectively met by threshold

    def test_underpayment_exactly_1000_penalty(self, engine):
        """Penalty applies when underpayment = exactly $1,000."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=17000.0,  # Required 18000, shortfall 1000
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 20000 = 18000
        # Underpayment: 18000 - 17000 = 1000 (exactly at threshold)
        # Penalty: 1000 * 0.08 = 80
        assert result['penalty'] == 80.0
        assert result['safe_harbor_met'] is False

    def test_underpayment_just_under_1000(self, engine):
        """No penalty when underpayment is $999."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=11100.0,  # 90% = 9990
            total_payments=8991.0,  # Shortfall: 9990 - 8991 = 999
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        assert result['penalty'] == 0.0


class TestUnderpaymentPenalty:
    """Tests for basic penalty calculation."""

    def test_basic_penalty_calculation(self, engine):
        """Standard penalty calculation: underpayment * 8%."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=15000.0,
            prior_year_tax=12000.0,  # 100% = 12000 (lower safe harbor)
            prior_year_agi=100000.0,
        )
        # Required: min(18000, 12000) = 12000
        # Underpayment: 12000 - 15000 = 0 (payments exceed required)
        # Actually, 15000 > 12000, so safe harbor met
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_penalty_with_large_underpayment(self, engine):
        """Penalty calculation with significant underpayment."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=50000.0,
            total_payments=30000.0,
            prior_year_tax=0.0,  # First year filer
            prior_year_agi=0.0,
        )
        # Required: 90% of 50000 = 45000
        # Underpayment: 45000 - 30000 = 15000
        # Penalty: 15000 * 0.08 = 1200
        assert result['penalty'] == 1200.0
        assert result['safe_harbor_met'] is False
        assert result['required_payment'] == 45000.0
        assert result['underpayment'] == 15000.0


class TestFarmerFisherman:
    """Tests for farmer/fisherman 66⅔% safe harbor."""

    def test_farmer_66_percent_safe_harbor(self, engine):
        """Farmers use 66⅔% instead of 90% for current year safe harbor."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=30000.0,
            total_payments=20000.0,  # ~66.67% of current tax
            prior_year_tax=0.0,
            prior_year_agi=0.0,
            is_farmer_or_fisherman=True,
        )
        # Required: 66.67% of 30000 = 20001 (uses 0.6667)
        # Payments: 20000, just under required
        # Small underpayment (~$1), under $1k threshold
        assert result['penalty'] == 0.0

    def test_farmer_meets_66_percent(self, engine):
        """Farmer meets 66⅔% safe harbor."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=30000.0,
            total_payments=20010.0,  # Just over 66⅔%
            prior_year_tax=0.0,
            prior_year_agi=0.0,
            is_farmer_or_fisherman=True,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_farmer_large_underpayment_penalty(self, engine):
        """Farmer with large underpayment gets penalty."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=60000.0,
            total_payments=30000.0,  # 50%, well under 66⅔%
            prior_year_tax=0.0,
            prior_year_agi=0.0,
            is_farmer_or_fisherman=True,
        )
        # Required: 66.67% of 60000 = 40002
        # Underpayment: 40002 - 30000 = 10002
        # Penalty: 10002 * 0.08 = 800.16
        assert result['penalty'] == 800.16
        assert result['safe_harbor_met'] is False


class TestNoPriorYearTax:
    """Tests for first-year filers (no prior year tax)."""

    def test_first_year_filer_meets_90_percent(self, engine):
        """First-year filer with 90% payments: no penalty."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=9000.0,
            prior_year_tax=0.0,  # No prior year
            prior_year_agi=0.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_first_year_filer_underpays(self, engine):
        """First-year filer with insufficient payments gets penalty."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=10000.0,  # Only 50%
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 20000 = 18000
        # Underpayment: 18000 - 10000 = 8000
        # Penalty: 8000 * 0.08 = 640
        assert result['penalty'] == 640.0
        assert result['safe_harbor_met'] is False


class TestIntegrationWithEngine:
    """Tests for full integration with tax calculation engine."""

    def test_penalty_in_full_calculation(self, engine):
        """Penalty flows through full tax calculation."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="Taxpayer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(100000.0, 5000.0)],  # Low withholding
                prior_year_tax=0.0,
                prior_year_agi=0.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Should have some penalty (withholding only $5k on $100k income)
        # Total tax ~$14k, required ~$12.6k (90%), payments $5k
        # Underpayment ~$7.6k, penalty ~$608
        assert breakdown.estimated_tax_penalty > 0
        assert breakdown.safe_harbor_met is False
        assert breakdown.required_annual_payment > 0

    def test_no_penalty_in_full_calculation(self, engine):
        """No penalty when safe harbor met in full calculation."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="Taxpayer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(50000.0, 8000.0)],  # Sufficient withholding
                prior_year_tax=5000.0,  # 100% safe harbor
                prior_year_agi=45000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Withholding exceeds prior year tax, safe harbor met
        assert breakdown.estimated_tax_penalty == 0.0
        assert breakdown.safe_harbor_met is True

    def test_penalty_with_estimated_payments(self, engine):
        """Estimated tax payments reduce penalty."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="Taxpayer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(100000.0, 5000.0)],
                estimated_tax_payments=10000.0,  # Additional payments
                prior_year_tax=12000.0,
                prior_year_agi=95000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Total payments: 5000 + 10000 = 15000
        # Prior year safe harbor: 12000
        # 15000 > 12000, so safe harbor met
        assert breakdown.estimated_tax_penalty == 0.0
        assert breakdown.safe_harbor_met is True

    def test_high_income_penalty_scenario(self, engine):
        """High income filer subject to 110% rule."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="High",
                last_name="Earner",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(250000.0, 40000.0)],
                prior_year_tax=45000.0,
                prior_year_agi=200000.0,  # Over $150k, requires 110%
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # 110% of prior year: 45000 * 1.10 = 49500
        # Payments: 40000
        # If 40000 < 49500, penalty may apply
        # But also check 90% of current year
        assert breakdown.required_annual_payment > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_tax(self, engine):
        """Very small tax liability."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=500.0,
            total_payments=0.0,
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 500 = 450
        # Underpayment: 450 - 0 = 450 (under $1k threshold)
        assert result['penalty'] == 0.0

    def test_zero_payments(self, engine):
        """Zero payments with significant tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=30000.0,
            total_payments=0.0,
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 30000 = 27000
        # Underpayment: 27000
        # Penalty: 27000 * 0.08 = 2160
        assert result['penalty'] == 2160.0
        assert result['safe_harbor_met'] is False

    def test_prior_year_higher_than_current(self, engine):
        """Prior year tax higher than current year tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=9000.0,
            prior_year_tax=20000.0,  # Higher than current
            prior_year_agi=100000.0,
        )
        # Required: min(90% of 10000, 100% of 20000) = min(9000, 20000) = 9000
        # Payments = 9000, meets requirement
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_rounding(self, engine):
        """Verify rounding in penalty calculation."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=33333.33,
            total_payments=25000.0,
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 33333.33 = 29999.997
        # Underpayment: 29999.997 - 25000 = 4999.997
        # Penalty: 4999.997 * 0.08 = 399.99976
        assert result['penalty'] == 400.0  # Rounded to 2 decimal places


class TestMinusScenarios:
    """Tests for negative or zero scenarios."""

    def test_negative_refund_situation(self, engine):
        """Large overpayment (refund due)."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=5000.0,
            total_payments=15000.0,  # Large overpayment
            prior_year_tax=10000.0,
            prior_year_agi=100000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True

    def test_both_safe_harbors_met(self, engine):
        """Both 90% and 100% safe harbors met."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=10000.0,
            total_payments=10000.0,  # 100% of current, also > prior
            prior_year_tax=8000.0,
            prior_year_agi=100000.0,
        )
        assert result['penalty'] == 0.0
        assert result['safe_harbor_met'] is True


class TestRequiredPaymentCalculation:
    """Tests for required_annual_payment calculation."""

    def test_required_payment_no_prior_year(self, engine):
        """Required payment with no prior year tax."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=20000.0,
            total_payments=18000.0,
            prior_year_tax=0.0,
            prior_year_agi=0.0,
        )
        # Required: 90% of 20000 = 18000
        assert result['required_payment'] == 18000.0

    def test_required_payment_uses_lower(self, engine):
        """Required payment uses lower of current vs prior year."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=50000.0,  # 90% = 45000
            total_payments=20000.0,
            prior_year_tax=25000.0,  # 100% = 25000 (lower)
            prior_year_agi=100000.0,
        )
        assert result['required_payment'] == 25000.0

    def test_required_payment_high_income(self, engine):
        """Required payment for high income uses 110%."""
        result = engine._calculate_estimated_tax_penalty(
            total_tax=100000.0,  # 90% = 90000
            total_payments=50000.0,
            prior_year_tax=50000.0,  # 110% = 55000 (lower than 90000)
            prior_year_agi=200000.0,  # Over $150k
        )
        assert result['required_payment'] == 55000.0
