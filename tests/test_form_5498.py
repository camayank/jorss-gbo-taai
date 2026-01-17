"""
Tests for Form 5498 - IRA Contribution Information

Comprehensive test suite covering:
- Basic Form 5498 data capture
- IRA contribution limits (Traditional, Roth, SEP, SIMPLE)
- Catch-up contributions (age 50+)
- Roth income phase-out calculations
- Traditional IRA deduction limits
- RMD calculations
- Multiple account aggregation
"""

import pytest
from datetime import date
from src.models.form_5498 import (
    Form5498,
    IRAType,
    ContributionType,
    IRAContributionLimits,
    IRASummary,
    calculate_ira_contribution_limit,
    calculate_rmd,
)


class TestForm5498Basic:
    """Test basic Form 5498 data capture."""

    def test_create_traditional_ira(self):
        """Test creating a Traditional IRA form."""
        form = Form5498(
            tax_year=2025,
            trustee_name="Fidelity Investments",
            participant_name="John Doe",
            box_1_ira_contributions=7000,
            box_5_fmv=150000,
            box_7_ira_type=IRAType.TRADITIONAL,
        )
        assert form.box_1_ira_contributions == 7000
        assert form.box_5_fmv == 150000
        assert form.is_traditional is True
        assert form.is_roth is False

    def test_create_roth_ira(self):
        """Test creating a Roth IRA form."""
        form = Form5498(
            tax_year=2025,
            trustee_name="Vanguard",
            box_10_roth_contributions=7000,
            box_5_fmv=200000,
            box_7_ira_type=IRAType.ROTH,
        )
        assert form.box_10_roth_contributions == 7000
        assert form.is_roth is True
        assert form.is_traditional is False

    def test_create_sep_ira(self):
        """Test creating a SEP IRA form."""
        form = Form5498(
            box_8_sep_contributions=50000,
            box_5_fmv=500000,
            box_7_ira_type=IRAType.SEP,
        )
        assert form.box_8_sep_contributions == 50000
        assert form.is_employer_plan is True

    def test_create_simple_ira(self):
        """Test creating a SIMPLE IRA form."""
        form = Form5498(
            box_9_simple_contributions=16000,
            box_7_ira_type=IRAType.SIMPLE,
        )
        assert form.box_9_simple_contributions == 16000
        assert form.is_employer_plan is True

    def test_ira_types(self):
        """Test IRA type enum values."""
        assert IRAType.TRADITIONAL.value == "traditional"
        assert IRAType.ROTH.value == "roth"
        assert IRAType.SEP.value == "sep"
        assert IRAType.SIMPLE.value == "simple"

    def test_total_contributions(self):
        """Test total contributions calculation."""
        form = Form5498(
            box_1_ira_contributions=5000,
            box_10_roth_contributions=2000,
        )
        assert form.total_contributions == 7000


class TestForm5498Rollovers:
    """Test rollover and conversion reporting."""

    def test_rollover_contribution(self):
        """Test rollover contribution reporting."""
        form = Form5498(
            box_2_rollover_contributions=100000,
            box_5_fmv=100000,
            box_7_ira_type=IRAType.TRADITIONAL,
        )
        assert form.box_2_rollover_contributions == 100000

    def test_roth_conversion(self):
        """Test Roth conversion reporting."""
        form = Form5498(
            box_3_roth_conversion=50000,
            box_5_fmv=50000,
            box_7_ira_type=IRAType.ROTH,
        )
        assert form.box_3_roth_conversion == 50000

    def test_recharacterization(self):
        """Test recharacterized contribution reporting."""
        form = Form5498(
            box_4_recharacterized=7000,
        )
        assert form.box_4_recharacterized == 7000


class TestForm5498RMD:
    """Test RMD reporting."""

    def test_rmd_required_flag(self):
        """Test RMD required flag."""
        form = Form5498(
            box_5_fmv=500000,
            box_11_rmd_required=True,
            box_12a_rmd_date=date(2025, 12, 31),
            box_12b_rmd_amount=18248,
        )
        assert form.box_11_rmd_required is True
        assert form.box_12b_rmd_amount == 18248

    def test_no_rmd_required(self):
        """Test when RMD is not required."""
        form = Form5498(
            box_5_fmv=200000,
            box_11_rmd_required=False,
        )
        assert form.box_11_rmd_required is False
        assert form.box_12b_rmd_amount == 0


class TestIRAContributionLimits:
    """Test IRA contribution limit calculations."""

    def test_traditional_ira_under_50(self):
        """Test Traditional IRA limit under age 50."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.TRADITIONAL,
            age=45,
        )
        assert max_contrib == 7000

    def test_traditional_ira_over_50(self):
        """Test Traditional IRA limit with catch-up."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.TRADITIONAL,
            age=55,
        )
        assert max_contrib == 8000  # 7000 + 1000 catch-up

    def test_roth_ira_under_50(self):
        """Test Roth IRA limit under age 50."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.ROTH,
            age=40,
        )
        assert max_contrib == 7000

    def test_roth_ira_over_50(self):
        """Test Roth IRA limit with catch-up."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.ROTH,
            age=52,
        )
        assert max_contrib == 8000

    def test_sep_ira_limit(self):
        """Test SEP IRA contribution limit."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.SEP,
            age=45,
            compensation=200000,
        )
        # 25% of 200000 = 50000
        assert max_contrib == 50000

    def test_sep_ira_max_cap(self):
        """Test SEP IRA maximum cap."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.SEP,
            age=45,
            compensation=500000,
        )
        # 25% of 500000 = 125000, but capped at 69000
        assert max_contrib == 69000

    def test_simple_ira_under_50(self):
        """Test SIMPLE IRA limit under age 50."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.SIMPLE,
            age=45,
        )
        assert max_contrib == 16000

    def test_simple_ira_over_50(self):
        """Test SIMPLE IRA limit with catch-up."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.SIMPLE,
            age=55,
        )
        assert max_contrib == 19500  # 16000 + 3500


class TestRothIncomePhaseout:
    """Test Roth IRA income phase-out calculations."""

    def test_roth_below_phaseout_single(self):
        """Test Roth limit below phase-out (single)."""
        limits = IRAContributionLimits(tax_year=2025)
        limit = limits.calculate_roth_limit(
            magi=100000,
            filing_status="single",
            age=40,
        )
        assert limit == 7000  # Full limit

    def test_roth_above_phaseout_single(self):
        """Test Roth limit above phase-out (single)."""
        limits = IRAContributionLimits(tax_year=2025)
        limit = limits.calculate_roth_limit(
            magi=170000,  # Above 165k
            filing_status="single",
            age=40,
        )
        assert limit == 0  # Phased out completely

    def test_roth_partial_phaseout_single(self):
        """Test Roth limit in phase-out range (single)."""
        limits = IRAContributionLimits(tax_year=2025)
        limit = limits.calculate_roth_limit(
            magi=157500,  # Middle of 150k-165k range
            filing_status="single",
            age=40,
        )
        # 50% through phase-out = 50% reduction
        assert limit == 3500  # Approximately half

    def test_roth_below_phaseout_mfj(self):
        """Test Roth limit below phase-out (MFJ)."""
        limits = IRAContributionLimits(tax_year=2025)
        limit = limits.calculate_roth_limit(
            magi=200000,
            filing_status="mfj",
            age=45,
        )
        assert limit == 7000

    def test_roth_above_phaseout_mfj(self):
        """Test Roth limit above phase-out (MFJ)."""
        limits = IRAContributionLimits(tax_year=2025)
        limit = limits.calculate_roth_limit(
            magi=250000,
            filing_status="mfj",
            age=45,
        )
        assert limit == 0


class TestTraditionalDeductionPhaseout:
    """Test Traditional IRA deduction phase-out."""

    def test_traditional_no_retirement_plan(self):
        """Test full deduction when no retirement plan."""
        limits = IRAContributionLimits(tax_year=2025)
        deductible = limits.calculate_traditional_deduction_limit(
            magi=200000,  # High income
            filing_status="single",
            has_retirement_plan=False,
            age=40,
        )
        # No phase-out if not covered by retirement plan
        assert deductible == 7000

    def test_traditional_with_plan_below_phaseout(self):
        """Test full deduction with plan below phase-out."""
        limits = IRAContributionLimits(tax_year=2025)
        deductible = limits.calculate_traditional_deduction_limit(
            magi=70000,  # Below 77k
            filing_status="single",
            has_retirement_plan=True,
            age=40,
        )
        assert deductible == 7000

    def test_traditional_with_plan_above_phaseout(self):
        """Test no deduction with plan above phase-out."""
        limits = IRAContributionLimits(tax_year=2025)
        deductible = limits.calculate_traditional_deduction_limit(
            magi=90000,  # Above 87k
            filing_status="single",
            has_retirement_plan=True,
            age=40,
        )
        assert deductible == 0

    def test_traditional_partial_phaseout(self):
        """Test partial deduction in phase-out range."""
        limits = IRAContributionLimits(tax_year=2025)
        deductible = limits.calculate_traditional_deduction_limit(
            magi=82000,  # Middle of 77k-87k
            filing_status="single",
            has_retirement_plan=True,
            age=40,
        )
        # 50% through phase-out
        assert deductible == 3500


class TestIRASummary:
    """Test IRA summary aggregation."""

    def test_single_form_summary(self):
        """Test summary with single form."""
        summary = IRASummary(tax_year=2025, age=45, magi=80000)
        form = Form5498(
            box_1_ira_contributions=7000,
            box_5_fmv=100000,
        )
        summary.add_form(form)

        assert summary.total_traditional_contributions == 7000
        assert summary.total_fmv == 100000

    def test_multiple_forms_summary(self):
        """Test summary with multiple forms."""
        summary = IRASummary(tax_year=2025, age=55, magi=100000)

        # Traditional IRA at Fidelity
        summary.add_form(Form5498(
            box_1_ira_contributions=4000,
            box_5_fmv=150000,
        ))

        # Roth IRA at Vanguard
        summary.add_form(Form5498(
            box_10_roth_contributions=4000,
            box_5_fmv=200000,
            box_7_ira_type=IRAType.ROTH,
        ))

        assert summary.total_traditional_contributions == 4000
        assert summary.total_roth_contributions == 4000
        assert summary.total_fmv == 350000

    def test_summary_with_rollovers(self):
        """Test summary with rollover contributions."""
        summary = IRASummary(tax_year=2025)
        summary.add_form(Form5498(
            box_2_rollover_contributions=100000,
            box_5_fmv=100000,
        ))
        summary.add_form(Form5498(
            box_2_rollover_contributions=50000,
            box_5_fmv=50000,
        ))

        assert summary.total_rollovers == 150000

    def test_summary_with_conversions(self):
        """Test summary with Roth conversions."""
        summary = IRASummary(tax_year=2025)
        summary.add_form(Form5498(
            box_3_roth_conversion=25000,
            box_7_ira_type=IRAType.ROTH,
        ))

        assert summary.total_conversions == 25000

    def test_summary_rmd_aggregation(self):
        """Test RMD aggregation across accounts."""
        summary = IRASummary(tax_year=2025, age=75)

        summary.add_form(Form5498(
            box_5_fmv=300000,
            box_11_rmd_required=True,
            box_12b_rmd_amount=12000,
        ))
        summary.add_form(Form5498(
            box_5_fmv=200000,
            box_11_rmd_required=True,
            box_12b_rmd_amount=8000,
        ))

        assert summary.total_rmd_required == 20000
        assert summary.accounts_requiring_rmd == 2

    def test_deductible_ira_contribution(self):
        """Test deductible IRA calculation."""
        summary = IRASummary(
            tax_year=2025,
            age=45,
            magi=80000,
            filing_status="single",
            has_retirement_plan=True,
        )
        summary.add_form(Form5498(
            box_1_ira_contributions=7000,
        ))

        deductible = summary.get_deductible_ira_contribution()
        # MAGI 80k is in phase-out range (77k-87k)
        # 30% through phase-out = 70% deductible
        assert deductible == 4900  # Approximately

    def test_nondeductible_contribution(self):
        """Test nondeductible contribution calculation."""
        summary = IRASummary(
            tax_year=2025,
            age=45,
            magi=100000,  # Above phase-out
            filing_status="single",
            has_retirement_plan=True,
        )
        summary.add_form(Form5498(
            box_1_ira_contributions=7000,
        ))

        nondeductible = summary.get_nondeductible_ira_contribution()
        # All contributions are nondeductible
        assert nondeductible == 7000


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_calculate_ira_limit_traditional(self):
        """Test Traditional IRA limit calculation."""
        result = calculate_ira_contribution_limit(
            ira_type="traditional",
            age=45,
            earned_income=100000,
            magi=80000,
            filing_status="single",
            has_retirement_plan=True,
        )
        assert result["max_contribution"] == 7000
        assert result["catch_up_eligible"] is False
        # Deductible limited by phase-out
        assert "deductible_limit" in result

    def test_calculate_ira_limit_roth(self):
        """Test Roth IRA limit with phase-out."""
        result = calculate_ira_contribution_limit(
            ira_type="roth",
            age=40,
            earned_income=100000,
            magi=160000,  # In phase-out
            filing_status="single",
        )
        assert result["max_contribution"] == 7000
        assert result["after_phaseout"] < 7000
        assert result["phaseout_applied"] is True

    def test_calculate_ira_limit_sep(self):
        """Test SEP IRA limit calculation."""
        result = calculate_ira_contribution_limit(
            ira_type="sep",
            age=55,
            earned_income=200000,
        )
        # 25% of 200k = 50k
        assert result["max_contribution"] == 50000

    def test_calculate_ira_limit_catch_up(self):
        """Test catch-up contribution eligibility."""
        result = calculate_ira_contribution_limit(
            ira_type="traditional",
            age=52,
            earned_income=100000,
        )
        assert result["catch_up_eligible"] is True
        assert result["max_contribution"] == 8000


class TestRMDCalculation:
    """Test Required Minimum Distribution calculations."""

    def test_rmd_under_73(self):
        """Test RMD not required under age 73."""
        result = calculate_rmd(
            account_balance=500000,
            owner_age=72,
        )
        assert result["rmd_required"] is False
        assert result["rmd_amount"] == 0

    def test_rmd_at_73(self):
        """Test RMD required at age 73."""
        result = calculate_rmd(
            account_balance=500000,
            owner_age=73,
        )
        assert result["rmd_required"] is True
        # Life expectancy factor at 73 = 26.5
        # RMD = 500000 / 26.5 = 18867.92
        assert abs(result["rmd_amount"] - 18867.92) < 1

    def test_rmd_at_80(self):
        """Test RMD at age 80."""
        result = calculate_rmd(
            account_balance=400000,
            owner_age=80,
        )
        # Life expectancy factor at 80 = 20.2
        # RMD = 400000 / 20.2 = 19801.98
        assert abs(result["rmd_amount"] - 19801.98) < 1

    def test_rmd_roth_not_required(self):
        """Test Roth IRA doesn't require RMD for original owner."""
        result = calculate_rmd(
            account_balance=500000,
            owner_age=75,
            account_type="roth",
        )
        assert result["rmd_required"] is False


class TestToDictionary:
    """Test dictionary serialization."""

    def test_form_5498_to_dict(self):
        """Test Form 5498 has expected properties."""
        form = Form5498(
            tax_year=2025,
            box_1_ira_contributions=7000,
            box_5_fmv=100000,
        )
        assert form.total_contributions == 7000

    def test_summary_to_dict(self):
        """Test IRASummary to_dict."""
        summary = IRASummary(
            tax_year=2025,
            age=50,
            magi=100000,
            filing_status="single",
        )
        summary.add_form(Form5498(
            box_1_ira_contributions=7000,
            box_5_fmv=150000,
        ))

        result = summary.to_dict()
        assert result["tax_year"] == 2025
        assert result["account_count"] == 1
        assert result["contributions"]["traditional"] == 7000
        assert result["fmv"]["total"] == 150000


class TestEdgeCases:
    """Test edge cases."""

    def test_contribution_exceeds_earned_income(self):
        """Test limit when earned income is less than limit."""
        limits = IRAContributionLimits(tax_year=2025)
        max_contrib = limits.get_max_contribution(
            ira_type=IRAType.TRADITIONAL,
            age=30,
            compensation=5000,  # Less than 7000 limit
        )
        assert max_contrib == 5000

    def test_inherited_ira_types(self):
        """Test inherited IRA classification."""
        form = Form5498(box_7_ira_type=IRAType.INHERITED_TRADITIONAL)
        assert form.is_traditional is True
        assert form.is_roth is False

        form2 = Form5498(box_7_ira_type=IRAType.INHERITED_ROTH)
        assert form2.is_roth is True

    def test_schedule_1_output(self):
        """Test Schedule 1 line mapping."""
        summary = IRASummary(
            tax_year=2025,
            age=45,
            magi=70000,
            has_retirement_plan=False,
        )
        summary.add_form(Form5498(box_1_ira_contributions=7000))
        summary.add_form(Form5498(box_8_sep_contributions=25000))
        summary.add_form(Form5498(box_9_simple_contributions=16000))

        result = summary.to_schedule_1()
        assert result["line_20_ira_deduction"] == 7000
        assert result["line_16_sep_deduction"] == 25000
        assert result["line_15_simple_deduction"] == 16000
