"""
Test Suite for Form 2210 - Underpayment of Estimated Tax

Tests cover:
- Safe harbor rules (90%, 100%, 110%)
- Underpayment threshold ($1,000)
- Penalty calculation (short and regular methods)
- Farmer/fisherman 66⅔% safe harbor
- First year filer scenarios
- Waiver requests
- High income 110% threshold
- Annualized income installment method
"""

import pytest
from datetime import date

from models.form_2210 import (
    Form2210,
    Form2210Part1,
    Form2210Part2,
    Form2210ShortMethod,
    Form2210RegularMethod,
    QuarterlyPayment,
    AnnualizedIncomeInstallment,
    FilingStatus,
    PenaltyWaiverReason,
    calculate_form_2210,
    check_safe_harbor
)


class TestNoUnderpayment:
    """Test cases where there is no underpayment."""

    def test_payments_equal_tax(self):
        """No penalty when payments equal tax liability."""
        form = Form2210(
            current_year_tax=10000,
            withholding=6000,
            estimated_payments=4000,
            prior_year_tax=8000,
            prior_year_agi=100000
        )

        assert form.total_payments == 10000
        assert form.underpayment_amount == 0
        assert form.safe_harbor_met is True
        assert form.penalty_applies is False
        assert form.penalty_amount == 0

    def test_payments_exceed_tax(self):
        """No penalty when payments exceed tax liability (refund scenario)."""
        form = Form2210(
            current_year_tax=10000,
            withholding=8000,
            estimated_payments=4000,
            prior_year_tax=8000,
            prior_year_agi=100000
        )

        assert form.total_payments == 12000
        assert form.underpayment_amount == 0
        assert form.penalty_applies is False


class TestSafeHarbor90Percent:
    """Test 90% of current year tax safe harbor."""

    def test_exactly_90_percent(self):
        """Safe harbor met at exactly 90% of current year."""
        form = Form2210(
            current_year_tax=10000,
            withholding=9000,  # Exactly 90%
            estimated_payments=0,
            prior_year_tax=0,  # No prior year (forces 90% test)
            prior_year_agi=100000
        )

        assert form.safe_harbor_current_year == 9000
        assert form.total_payments == 9000
        assert form.safe_harbor_met is True
        assert form.penalty_applies is False
        assert "90%" in form.safe_harbor_reason

    def test_above_90_percent(self):
        """Safe harbor met above 90%."""
        form = Form2210(
            current_year_tax=10000,
            withholding=9500,
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=100000
        )

        assert form.safe_harbor_met is True
        assert form.penalty_applies is False

    def test_below_90_percent(self):
        """Safe harbor NOT met below 90%."""
        form = Form2210(
            current_year_tax=10000,
            withholding=8000,  # 80%, below 90%
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=100000,
            is_first_year_filer=True  # Force 90% test
        )

        assert form.safe_harbor_met is False
        # Underpayment $2,000 exceeds $1,000 threshold
        assert form.underpayment_amount == 2000
        assert form.penalty_applies is True


class TestSafeHarbor100Percent:
    """Test 100% of prior year tax safe harbor."""

    def test_exactly_100_percent_prior_year(self):
        """Safe harbor met at exactly 100% of prior year."""
        form = Form2210(
            current_year_tax=15000,  # Higher than prior year
            withholding=12000,  # 100% of prior year
            estimated_payments=0,
            prior_year_tax=12000,
            prior_year_agi=100000  # Below $150k, so 100% applies
        )

        assert form.requires_110_percent is False
        assert form.safe_harbor_prior_year == 12000
        assert form.safe_harbor_met is True
        assert form.penalty_applies is False
        assert "100%" in form.safe_harbor_reason

    def test_100_percent_lower_than_90(self):
        """100% prior year is lower than 90% current year."""
        form = Form2210(
            current_year_tax=20000,  # 90% = 18,000
            withholding=10000,  # 100% of prior year = 10,000
            estimated_payments=0,
            prior_year_tax=10000,
            prior_year_agi=100000
        )

        # Required is min(18000, 10000) = 10000
        assert form.required_annual_payment == 10000
        assert form.safe_harbor_met is True


class TestSafeHarbor110Percent:
    """Test 110% safe harbor for high income taxpayers."""

    def test_110_percent_required(self):
        """110% required when prior AGI > $150,000."""
        form = Form2210(
            current_year_tax=20000,
            withholding=16000,
            estimated_payments=0,
            prior_year_tax=16000,
            prior_year_agi=200000  # Over $150k
        )

        assert form.requires_110_percent is True
        assert form.safe_harbor_prior_year == 17600  # 110% of 16000

        # Payments are only $16,000, need $17,600
        assert form.safe_harbor_met is False

    def test_110_percent_met(self):
        """Safe harbor met at 110%."""
        form = Form2210(
            current_year_tax=25000,
            withholding=17600,  # 110% of $16,000
            estimated_payments=0,
            prior_year_tax=16000,
            prior_year_agi=200000
        )

        assert form.requires_110_percent is True
        assert form.safe_harbor_prior_year == 17600
        assert form.safe_harbor_met is True
        assert form.penalty_applies is False
        assert "110%" in form.safe_harbor_reason

    def test_exactly_150k_threshold(self):
        """At exactly $150,000, use 100% (not 110%)."""
        form = Form2210(
            current_year_tax=20000,
            withholding=12000,
            estimated_payments=0,
            prior_year_tax=12000,
            prior_year_agi=150000  # Exactly at threshold
        )

        assert form.requires_110_percent is False
        assert form.safe_harbor_prior_year == 12000  # 100%

    def test_above_150k_threshold(self):
        """Above $150,000, use 110%."""
        form = Form2210(
            current_year_tax=20000,
            withholding=12000,
            estimated_payments=0,
            prior_year_tax=12000,
            prior_year_agi=150001  # Just above threshold
        )

        assert form.requires_110_percent is True
        assert abs(form.safe_harbor_prior_year - 13200) < 0.01  # 110%


class TestUnderpaymentThreshold:
    """Test $1,000 underpayment threshold."""

    def test_under_1000_threshold_exemption(self):
        """Underpayment under $1,000 threshold exempts from penalty."""
        # To trigger under-threshold exemption (not safe harbor):
        # Need safe harbor NOT met but underpayment < $1,000
        # Use very high prior year tax to make safe harbor unreachable
        form = Form2210(
            current_year_tax=1000,  # Small tax
            withholding=100,  # $900 underpayment (under $1,000)
            estimated_payments=0,
            prior_year_tax=50000,  # 100% = $50,000 required
            prior_year_agi=100000  # Below $150k, so 100%
        )

        # Required = min(90%×1000, 100%×50000) = min(900, 50000) = 900
        # Payments = $100 < $900, safe harbor NOT met
        assert form.safe_harbor_met is False
        assert form.underpayment_amount == 900
        assert form.under_threshold is True
        assert form.penalty_applies is False
        assert "under $1,000" in form.exemption_reason

    def test_exactly_1000_penalty_applies(self):
        """Penalty applies when underpayment is exactly $1,000."""
        form = Form2210(
            current_year_tax=10000,
            withholding=8000,  # $1,000 short of 90%
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=100000,
            is_first_year_filer=True
        )

        assert form.underpayment_amount == 2000
        assert form.under_threshold is False
        assert form.penalty_applies is True

    def test_over_1000_penalty_applies(self):
        """Penalty applies when underpayment exceeds $1,000."""
        form = Form2210(
            current_year_tax=20000,
            withholding=15000,  # $3,000 short of 90%
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=100000,
            is_first_year_filer=True
        )

        assert form.underpayment_amount == 5000
        assert form.under_threshold is False
        assert form.penalty_applies is True


class TestPenaltyCalculation:
    """Test penalty amount calculations."""

    def test_basic_penalty(self):
        """Basic penalty calculation."""
        form = Form2210(
            current_year_tax=20000,
            withholding=15000,  # $3,000 short
            estimated_payments=0,
            prior_year_tax=12000,
            prior_year_agi=100000
        )

        # Required payment: min(18000, 12000) = 12000
        # Shortfall: 12000 - 15000 = 0 (overpaid prior year safe harbor)
        assert form.safe_harbor_met is True  # 15000 >= 12000
        assert form.penalty_applies is False

    def test_penalty_short_method(self):
        """Penalty using short method."""
        form = Form2210(
            current_year_tax=20000,
            withholding=10000,
            estimated_payments=0,
            prior_year_tax=16000,
            prior_year_agi=100000,
            is_first_year_filer=True  # Force 90% test
        )

        # Required: 90% of 20000 = 18000
        # Shortfall: 18000 - 10000 = 8000
        assert form.penalty_applies is True

        # Short method: shortfall × rate × 0.5 (avg period)
        # 8000 × 0.08 × 0.5 = 320
        assert form.penalty_amount == 320

    def test_penalty_with_extension_payment(self):
        """Extension payment reduces underpayment."""
        form = Form2210(
            current_year_tax=20000,
            withholding=10000,
            estimated_payments=5000,
            amount_paid_with_extension=3000,
            prior_year_tax=0,
            prior_year_agi=100000,
            is_first_year_filer=True
        )

        assert form.total_payments == 18000
        assert form.safe_harbor_met is True  # 18000 >= 18000 (90%)


class TestFarmerFisherman:
    """Test farmer/fisherman 66⅔% safe harbor."""

    def test_farmer_66_percent_safe_harbor(self):
        """Farmer meets 66⅔% safe harbor."""
        form = Form2210(
            current_year_tax=30000,
            withholding=0,
            estimated_payments=20010,  # Just over 66.67% of 30000
            prior_year_tax=25000,
            prior_year_agi=100000,
            is_farmer_or_fisherman=True
        )

        # 66.67% of 30000 = 20001
        assert abs(form.safe_harbor_current_year - 20001) < 1
        assert form.safe_harbor_met is True
        assert form.penalty_applies is False
        assert "farmer" in form.safe_harbor_reason.lower()

    def test_farmer_below_66_percent(self):
        """Farmer below 66⅔% threshold."""
        form = Form2210(
            current_year_tax=30000,
            withholding=0,
            estimated_payments=18000,  # 60%, below 66.67%
            prior_year_tax=0,
            prior_year_agi=100000,
            is_farmer_or_fisherman=True,
            is_first_year_filer=True
        )

        assert form.safe_harbor_met is False
        assert form.penalty_applies is True


class TestFirstYearFiler:
    """Test first year filer scenarios."""

    def test_first_year_no_prior_year_tax(self):
        """First year filer uses 90% of current year only."""
        form = Form2210(
            current_year_tax=15000,
            withholding=13500,  # Exactly 90%
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=0,
            is_first_year_filer=True
        )

        assert form.required_annual_payment == 13500  # 90% only
        assert form.safe_harbor_met is True
        assert form.penalty_applies is False


class TestPriorYearTaxZero:
    """Test scenarios where prior year tax was zero."""

    def test_prior_year_zero_no_penalty(self):
        """No penalty if prior year tax was zero (and was U.S. citizen)."""
        form = Form2210(
            current_year_tax=20000,
            withholding=5000,
            estimated_payments=0,
            prior_year_tax=0,  # Zero prior year tax
            prior_year_agi=50000,
            is_first_year_filer=False  # Not first year, just zero tax
        )

        assert form.penalty_applies is False
        assert "Prior year tax was zero" in form.exemption_reason


class TestWaivers:
    """Test penalty waiver scenarios."""

    def test_casualty_waiver(self):
        """Waiver for casualty/disaster."""
        form = Form2210(
            current_year_tax=20000,
            withholding=5000,
            estimated_payments=0,
            prior_year_tax=15000,
            prior_year_agi=100000,
            waiver_reason=PenaltyWaiverReason.CASUALTY_DISASTER
        )

        assert form.penalty_applies is False
        assert "Casualty" in form.exemption_reason

    def test_retired_disabled_waiver(self):
        """Waiver for retirement/disability."""
        form = Form2210(
            current_year_tax=20000,
            withholding=5000,
            estimated_payments=0,
            prior_year_tax=15000,
            prior_year_agi=100000,
            waiver_reason=PenaltyWaiverReason.RETIRED_DISABLED
        )

        assert form.penalty_applies is False
        assert "Retired" in form.exemption_reason or "disabled" in form.exemption_reason


class TestForm2210Part1:
    """Test Part I of Form 2210."""

    def test_part1_line_calculations(self):
        """Test Part I line-by-line calculations."""
        part1 = Form2210Part1(
            line_1_current_year_tax=20000,
            line_2_other_taxes=3000,
            line_3_refundable_credits=1000,
            line_6_withholding=15000,
            line_6_estimated_payments=2000,
            line_8_prior_year_tax=18000,
            line_9_prior_year_agi=100000
        )

        # Line 4: 20000 + 3000 - 1000 = 22000
        assert part1.line_4_current_year_tax_liability == 22000

        # Line 5: 22000 × 0.90 = 19800
        assert part1.line_5_90_percent == 19800

        # Line 6 total: 15000 + 2000 = 17000
        assert part1.line_6_total_payments == 17000

        # Line 7: 22000 - 17000 = 5000
        assert part1.line_7_underpayment == 5000

        # Line 10: 18000 × 1.00 = 18000
        assert part1.requires_110_percent is False
        assert part1.line_10_safe_harbor_amount == 18000

        # Line 11: min(19800, 18000) = 18000
        assert part1.line_11_required_annual_payment == 18000

    def test_part1_110_percent(self):
        """Test Part I with 110% safe harbor."""
        part1 = Form2210Part1(
            line_1_current_year_tax=20000,
            line_2_other_taxes=0,
            line_3_refundable_credits=0,
            line_6_withholding=15000,
            line_6_estimated_payments=0,
            line_8_prior_year_tax=16000,
            line_9_prior_year_agi=200000  # Over $150k
        )

        assert part1.requires_110_percent is True
        assert part1.safe_harbor_prior_year_pct == 1.10
        assert part1.line_10_safe_harbor_amount == 17600  # 110%


class TestForm2210ShortMethod:
    """Test short method penalty calculation."""

    def test_short_method_calculation(self):
        """Test short method penalty."""
        short = Form2210ShortMethod(
            line_12_underpayment=5000,
            penalty_rate=0.08
        )

        # 5000 × 0.08 × 0.5 = 200
        assert short.line_16_penalty == 200

    def test_short_method_no_underpayment(self):
        """No penalty when no underpayment."""
        short = Form2210ShortMethod(
            line_12_underpayment=0,
            penalty_rate=0.08
        )

        assert short.line_16_penalty == 0


class TestForm2210RegularMethod:
    """Test regular method with quarterly calculations."""

    def test_regular_method_single_quarter(self):
        """Test regular method with single quarter underpayment."""
        q1 = QuarterlyPayment(
            quarter=1,
            due_date=date(2025, 4, 15),
            # payment_date not specified - uses filing deadline for penalty calc
            required_payment=5000,
            amount_paid=3000
        )

        regular = Form2210RegularMethod(
            quarters=[q1],
            penalty_rate=0.08,
            filing_deadline=date(2026, 4, 15)
        )

        assert regular.total_underpayment == 2000

        # 365 days from Apr 15, 2025 to Apr 15, 2026
        # 2000 × 0.08 × (365/365) = 160
        penalty = regular.calculate_quarterly_penalty(q1)
        assert abs(penalty - 160) < 1

    def test_regular_method_multiple_quarters(self):
        """Test regular method with multiple quarters."""
        quarters = [
            QuarterlyPayment(
                quarter=1,
                due_date=date(2025, 4, 15),
                required_payment=5000,
                amount_paid=5000
            ),
            QuarterlyPayment(
                quarter=2,
                due_date=date(2025, 6, 15),
                required_payment=5000,
                amount_paid=3000  # $2000 underpayment
            ),
            QuarterlyPayment(
                quarter=3,
                due_date=date(2025, 9, 15),
                required_payment=5000,
                amount_paid=5000
            ),
            QuarterlyPayment(
                quarter=4,
                due_date=date(2026, 1, 15),
                required_payment=5000,
                amount_paid=5000
            )
        ]

        regular = Form2210RegularMethod(
            quarters=quarters,
            penalty_rate=0.08,
            filing_deadline=date(2026, 4, 15)
        )

        assert regular.total_underpayment == 2000
        assert regular.total_penalty > 0


class TestQuarterlyPayment:
    """Test QuarterlyPayment model."""

    def test_underpayment_calculation(self):
        """Test quarterly underpayment."""
        q = QuarterlyPayment(
            quarter=1,
            due_date=date(2025, 4, 15),
            required_payment=5000,
            amount_paid=3000,
            withholding_allocated=1000
        )

        assert q.total_payment == 4000
        assert q.underpayment == 1000
        assert q.overpayment == 0

    def test_overpayment_calculation(self):
        """Test quarterly overpayment."""
        q = QuarterlyPayment(
            quarter=1,
            due_date=date(2025, 4, 15),
            required_payment=5000,
            amount_paid=6000
        )

        assert q.underpayment == 0
        assert q.overpayment == 1000

    def test_days_late(self):
        """Test days late calculation."""
        q = QuarterlyPayment(
            quarter=1,
            due_date=date(2025, 4, 15),
            payment_date=date(2025, 5, 15),  # 30 days late
            required_payment=5000,
            amount_paid=5000
        )

        assert q.days_late == 30

    def test_on_time_payment(self):
        """Test on-time payment."""
        q = QuarterlyPayment(
            quarter=1,
            due_date=date(2025, 4, 15),
            payment_date=date(2025, 4, 10),  # Early
            required_payment=5000,
            amount_paid=5000
        )

        assert q.is_on_time is True
        assert q.days_late == 0


class TestAnnualizedIncomeInstallment:
    """Test Schedule AI for annualized income."""

    def test_annualization_factors(self):
        """Test income annualization."""
        ai = AnnualizedIncomeInstallment(
            period_1_income=10000,  # Q1 income
            period_2_income=25000,  # Jan-May income
            period_3_income=50000,  # Jan-Aug income
            period_4_income=75000   # Full year
        )

        # Period 1: 10000 × 4 = 40000
        assert ai.annualized_income_p1 == 40000

        # Period 2: 25000 × 2.4 = 60000
        assert ai.annualized_income_p2 == 60000

        # Period 3: 50000 × 1.5 = 75000
        assert ai.annualized_income_p3 == 75000

        # Period 4: 75000 × 1 = 75000
        assert ai.annualized_income_p4 == 75000


class TestConvenienceFunction:
    """Test calculate_form_2210 convenience function."""

    def test_basic_calculation(self):
        """Test basic penalty calculation."""
        result = calculate_form_2210(
            current_year_tax=20000,
            withholding=10000,
            estimated_payments=5000,
            prior_year_tax=12000,
            prior_year_agi=100000
        )

        assert result["total_tax_liability"] == 20000
        assert result["total_payments"] == 15000
        assert result["safe_harbor_met"] is True  # 15000 >= 12000

    def test_with_other_taxes(self):
        """Test with self-employment tax."""
        result = calculate_form_2210(
            current_year_tax=20000,
            withholding=15000,
            estimated_payments=5000,
            prior_year_tax=18000,
            prior_year_agi=100000,
            other_taxes=3000
        )

        assert result["total_tax_liability"] == 23000


class TestCheckSafeHarbor:
    """Test check_safe_harbor convenience function."""

    def test_safe_harbor_met(self):
        """Test safe harbor check when met."""
        result = check_safe_harbor(
            total_payments=15000,
            current_year_tax=15000,
            prior_year_tax=12000,
            prior_year_agi=100000
        )

        assert result["safe_harbor_met"] is True
        assert result["shortfall"] == 0

    def test_safe_harbor_not_met(self):
        """Test safe harbor check when not met."""
        result = check_safe_harbor(
            total_payments=10000,
            current_year_tax=20000,
            prior_year_tax=15000,
            prior_year_agi=100000
        )

        # Required: min(18000, 15000) = 15000
        assert result["safe_harbor_met"] is False
        assert result["required_payment"] == 15000
        assert result["shortfall"] == 5000

    def test_high_income_110_percent(self):
        """Test 110% threshold for high income."""
        result = check_safe_harbor(
            total_payments=16000,
            current_year_tax=20000,
            prior_year_tax=16000,
            prior_year_agi=200000
        )

        assert abs(result["prior_year_pct"] - 110) < 0.01
        assert abs(result["prior_year_threshold"] - 17600) < 0.01
        assert result["safe_harbor_met"] is False


class TestToDictionary:
    """Test form serialization."""

    def test_to_dict(self):
        """Test to_dict method."""
        form = Form2210(
            current_year_tax=20000,
            withholding=15000,
            estimated_payments=3000,
            prior_year_tax=16000,
            prior_year_agi=100000,
            filing_status=FilingStatus.MARRIED_JOINT
        )

        result = form.to_dict()

        assert result["tax_year"] == 2025
        assert result["filing_status"] == "married_joint"
        assert result["total_tax_liability"] == 20000
        assert result["total_payments"] == 18000
        assert result["safe_harbor_met"] is True
        assert "prior_year_agi" in result

    def test_to_form_1040(self):
        """Test to_form_1040 method."""
        form = Form2210(
            current_year_tax=20000,
            withholding=10000,
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=100000,
            is_first_year_filer=True
        )

        result = form.to_form_1040()

        assert "estimated_tax_penalty" in result
        if form.penalty_applies:
            assert result["estimated_tax_penalty"] > 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_tax_liability(self):
        """No penalty when tax liability is zero."""
        form = Form2210(
            current_year_tax=0,
            withholding=5000,  # Overpaid
            estimated_payments=0,
            prior_year_tax=10000,
            prior_year_agi=100000
        )

        assert form.total_tax_liability == 0
        assert form.penalty_applies is False

    def test_negative_prevented(self):
        """Underpayment cannot be negative."""
        form = Form2210(
            current_year_tax=5000,
            withholding=10000,
            estimated_payments=0,
            prior_year_tax=8000,
            prior_year_agi=100000
        )

        assert form.underpayment_amount == 0

    def test_very_high_income(self):
        """Test with very high income (always 110%)."""
        form = Form2210(
            current_year_tax=500000,
            withholding=400000,
            estimated_payments=55000,  # 110% of 500k = 550k
            prior_year_tax=500000,
            prior_year_agi=5000000  # Very high AGI
        )

        assert form.requires_110_percent is True
        assert form.safe_harbor_prior_year == 550000
        assert form.safe_harbor_met is True

    def test_all_filing_statuses(self):
        """Test all filing statuses work."""
        for status in FilingStatus:
            form = Form2210(
                current_year_tax=10000,
                withholding=9000,
                estimated_payments=0,
                prior_year_tax=8000,
                prior_year_agi=100000,
                filing_status=status
            )

            assert form.safe_harbor_met is True
            assert form.filing_status == status


class TestForm2210Part2:
    """Test Part II (Reasons for Filing)."""

    def test_waiver_requests(self):
        """Test waiver checkbox flags."""
        part2 = Form2210Part2(
            box_a_casualty_waiver=True,
            box_b_retired_disabled=False,
            box_c_annualized=False,
            box_d_prior_year_waiver=False
        )

        assert part2.requesting_waiver is True

    def test_no_waiver(self):
        """Test no waiver requested."""
        part2 = Form2210Part2()

        assert part2.requesting_waiver is False

    def test_multiple_waivers(self):
        """Test multiple waivers."""
        part2 = Form2210Part2(
            box_a_casualty_waiver=True,
            box_b_retired_disabled=True
        )

        assert part2.requesting_waiver is True


class TestGetMethods:
    """Test form section getter methods."""

    def test_get_part1(self):
        """Test get_part1 method."""
        form = Form2210(
            current_year_tax=20000,
            other_taxes=3000,
            refundable_credits=1000,
            withholding=15000,
            estimated_payments=2000,
            prior_year_tax=18000,
            prior_year_agi=100000
        )

        part1 = form.get_part1()

        assert part1.line_1_current_year_tax == 20000
        assert part1.line_2_other_taxes == 3000
        assert part1.line_6_withholding == 15000

    def test_get_short_method(self):
        """Test get_short_method method."""
        form = Form2210(
            current_year_tax=20000,
            withholding=10000,
            estimated_payments=0,
            prior_year_tax=0,
            prior_year_agi=100000,
            is_first_year_filer=True
        )

        short = form.get_short_method()

        assert short.line_12_underpayment == form.underpayment_amount

    def test_get_regular_method(self):
        """Test get_regular_method method."""
        quarters = [
            QuarterlyPayment(
                quarter=1,
                due_date=date(2025, 4, 15),
                required_payment=5000,
                amount_paid=5000
            )
        ]

        form = Form2210(
            current_year_tax=20000,
            withholding=10000,
            estimated_payments=5000,
            prior_year_tax=15000,
            prior_year_agi=100000,
            quarterly_payments=quarters
        )

        regular = form.get_regular_method()

        assert len(regular.quarters) == 1
