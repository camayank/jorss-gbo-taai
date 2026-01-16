"""
Tests for Child and Dependent Care Credit (Form 2441)

Tests cover:
- Credit rate tiers (35% down to 20% based on AGI)
- Expense limits ($3,000 for 1 person, $6,000 for 2+)
- Earned income limitations
- Filing status variations
- Integration with engine
"""

import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


class TestDependentCareRates:
    """Tests for credit rate tiers based on AGI."""

    def test_35_percent_rate_lowest_income(self):
        """AGI $15,000 or less gets maximum 35% rate."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15000.0,
            earned_income_taxpayer=50000.0,
        )

        # $3,000 * 35% = $1,050
        assert result == 1050.0

    def test_34_percent_rate(self):
        """AGI between $15,001-$17,000 gets 34% rate."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=16000.0,
            earned_income_taxpayer=50000.0,
        )

        # $3,000 * 34% = $1,020
        assert result == 1020.0

    def test_27_percent_rate_mid_income(self):
        """AGI $30,000 gets 27% rate."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=30000.0,
            earned_income_taxpayer=50000.0,
        )

        # $3,000 * 27% = $810
        assert result == 810.0

    def test_20_percent_rate_high_income(self):
        """AGI over $43,000 gets minimum 20% rate."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=50000.0,
            earned_income_taxpayer=60000.0,
        )

        # $3,000 * 20% = $600
        assert result == 600.0


class TestDependentCareExpenseLimits:
    """Tests for expense limits based on qualifying persons."""

    def test_one_qualifying_person_limit_3000(self):
        """One qualifying person limits expenses to $3,000."""
        credits = TaxCredits(
            child_care_expenses=5000.0,  # Over limit
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15000.0,
            earned_income_taxpayer=50000.0,
        )

        # $3,000 cap * 35% = $1,050
        assert result == 1050.0

    def test_two_qualifying_persons_limit_6000(self):
        """Two qualifying persons limits expenses to $6,000."""
        credits = TaxCredits(
            child_care_expenses=8000.0,  # Over limit
            num_qualifying_persons=2,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15000.0,
            earned_income_taxpayer=50000.0,
        )

        # $6,000 cap * 35% = $2,100
        assert result == 2100.0

    def test_three_qualifying_persons_same_as_two(self):
        """Three+ qualifying persons still limited to $6,000."""
        credits = TaxCredits(
            child_care_expenses=10000.0,  # Way over limit
            num_qualifying_persons=3,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15000.0,
            earned_income_taxpayer=50000.0,
        )

        # $6,000 cap * 35% = $2,100
        assert result == 2100.0

    def test_expenses_under_limit(self):
        """Expenses under limit use actual amount."""
        credits = TaxCredits(
            child_care_expenses=1500.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15000.0,
            earned_income_taxpayer=50000.0,
        )

        # $1,500 * 35% = $525
        assert result == 525.0


class TestDependentCareEarnedIncome:
    """Tests for earned income limitations."""

    def test_limited_by_taxpayer_earned_income(self):
        """Credit limited to taxpayer's earned income (single)."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=20000.0,
            earned_income_taxpayer=2000.0,  # Less than expenses
            filing_status="single",
        )

        # Limited to $2,000 earned income * 32% = $640
        assert result == 640.0

    def test_mfj_limited_by_lower_spouse_income(self):
        """MFJ credit limited to lesser of spouses' earned income."""
        credits = TaxCredits(
            child_care_expenses=6000.0,
            num_qualifying_persons=2,
        )

        result = credits.calculate_dependent_care_credit(
            agi=40000.0,
            earned_income_taxpayer=50000.0,
            earned_income_spouse=3000.0,  # Lower earner
            filing_status="married_joint",
        )

        # Limited to $3,000 (lower spouse) * 22% = $660
        assert result == 660.0

    def test_mfj_both_high_earners(self):
        """MFJ with both high earners uses expense limit."""
        credits = TaxCredits(
            child_care_expenses=6000.0,
            num_qualifying_persons=2,
        )

        result = credits.calculate_dependent_care_credit(
            agi=50000.0,
            earned_income_taxpayer=40000.0,
            earned_income_spouse=35000.0,
            filing_status="married_joint",
        )

        # $6,000 * 20% = $1,200
        assert result == 1200.0

    def test_zero_earned_income_no_credit(self):
        """No credit when taxpayer has zero earned income."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=20000.0,
            earned_income_taxpayer=0.0,
        )

        assert result == 0.0


class TestDependentCareEligibility:
    """Tests for basic eligibility requirements."""

    def test_no_expenses_no_credit(self):
        """No credit when no expenses reported."""
        credits = TaxCredits(
            child_care_expenses=0.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=20000.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 0.0

    def test_no_qualifying_persons_no_credit(self):
        """No credit when no qualifying persons."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=0,
        )

        result = credits.calculate_dependent_care_credit(
            agi=20000.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 0.0

    def test_zero_expenses_no_credit(self):
        """Zero expenses returns zero."""
        credits = TaxCredits(
            child_care_expenses=0.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=20000.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 0.0


class TestDependentCareRateBoundaries:
    """Tests for AGI rate boundaries."""

    def test_at_15000_boundary(self):
        """AGI exactly $15,000 gets 35%."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15000.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 1050.0  # 35%

    def test_at_15001(self):
        """AGI $15,001 gets 34%."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=15001.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 1020.0  # 34%

    def test_at_43000_boundary(self):
        """AGI exactly $43,000 gets 21%."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=43000.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 630.0  # 21%

    def test_at_43001(self):
        """AGI $43,001 gets 20%."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        result = credits.calculate_dependent_care_credit(
            agi=43001.0,
            earned_income_taxpayer=50000.0,
        )

        assert result == 600.0  # 20%


class TestDependentCareEngineIntegration:
    """Tests for integration with the tax engine."""

    def test_basic_engine_calculation(self):
        """Engine correctly calculates dependent care credit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                child_care_expenses=3000.0,
                num_qualifying_persons=1,
            ),
        )

        breakdown = engine.calculate(tr)

        # AGI $50K = 20% rate, $3,000 * 20% = $600
        assert breakdown.credit_breakdown['child_care_credit'] == 600.0

    def test_engine_with_two_children(self):
        """Engine handles two qualifying persons."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            ),
            income=Income(w2_forms=[make_w2(30000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                child_care_expenses=6000.0,
                num_qualifying_persons=2,
            ),
        )

        breakdown = engine.calculate(tr)

        # AGI $30K = 27% rate, $6,000 * 27% = $1,620
        assert breakdown.credit_breakdown['child_care_credit'] == 1620.0

    def test_engine_no_qualifying_persons(self):
        """Engine returns zero when no qualifying persons."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                child_care_expenses=3000.0,
                num_qualifying_persons=0,  # No qualifying persons
            ),
        )

        breakdown = engine.calculate(tr)

        assert breakdown.credit_breakdown['child_care_credit'] == 0.0

    def test_credit_in_nonrefundable_total(self):
        """Dependent care credit is included in nonrefundable total."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(
                child_care_expenses=3000.0,
                num_qualifying_persons=1,
            ),
        )

        breakdown = engine.calculate(tr)

        child_care = breakdown.credit_breakdown['child_care_credit']
        total_nonref = breakdown.credit_breakdown['total_nonrefundable']

        assert child_care <= total_nonref
        assert child_care == 600.0


class TestDependentCareRateSchedule:
    """Comprehensive tests for the full rate schedule."""

    def test_full_rate_schedule(self):
        """Test all rate tiers in the schedule."""
        credits = TaxCredits(
            child_care_expenses=3000.0,
            num_qualifying_persons=1,
        )

        # Expected: (AGI, expected_rate, expected_credit)
        test_cases = [
            (10000, 0.35, 1050.0),   # 35%
            (16000, 0.34, 1020.0),   # 34%
            (18000, 0.33, 990.0),    # 33%
            (20000, 0.32, 960.0),    # 32%
            (22000, 0.31, 930.0),    # 31%
            (24000, 0.30, 900.0),    # 30%
            (26000, 0.29, 870.0),    # 29%
            (28000, 0.28, 840.0),    # 28%
            (30000, 0.27, 810.0),    # 27%
            (32000, 0.26, 780.0),    # 26%
            (34000, 0.25, 750.0),    # 25%
            (36000, 0.24, 720.0),    # 24%
            (38000, 0.23, 690.0),    # 23%
            (40000, 0.22, 660.0),    # 22%
            (42000, 0.21, 630.0),    # 21%
            (50000, 0.20, 600.0),    # 20%
        ]

        for agi, expected_rate, expected_credit in test_cases:
            result = credits.calculate_dependent_care_credit(
                agi=agi,
                earned_income_taxpayer=60000.0,
            )
            assert result == expected_credit, f"Failed at AGI ${agi:,}"


class TestDependentCareHelperMethod:
    """Tests for _get_dependent_care_rate helper method."""

    def test_rate_method_directly(self):
        """Test the rate lookup method directly."""
        credits = TaxCredits()

        assert credits._get_dependent_care_rate(10000) == 0.35
        assert credits._get_dependent_care_rate(15000) == 0.35
        assert credits._get_dependent_care_rate(15001) == 0.34
        assert credits._get_dependent_care_rate(43000) == 0.21
        assert credits._get_dependent_care_rate(43001) == 0.20
        assert credits._get_dependent_care_rate(100000) == 0.20
