"""
Tests for Disabled Access Credit (Form 8826 / IRC Section 44).

This credit helps eligible small businesses pay for making their
facilities and services accessible to persons with disabilities.

Key Rules:
- Eligible: gross receipts ≤ $1M OR ≤ 30 full-time employees
- Credit = 50% of eligible expenditures
- Eligible expenditures: $250 to $10,250
- Maximum credit: $5,000 per year

Reference: IRC Section 44, IRS Form 8826
"""

import pytest
from models.credits import (
    TaxCredits,
    DisabledAccessInfo,
    DisabledAccessExpenditure,
    DisabledAccessExpenditureType,
)


class TestDisabledAccessInfo:
    """Tests for the DisabledAccessInfo model."""

    def test_eligible_by_gross_receipts(self):
        """Test eligibility based on gross receipts ≤ $1M."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=50,  # Over 30, but receipts under $1M
            total_eligible_expenditures=5000,
        )
        assert info.is_eligible_small_business() is True

    def test_eligible_by_employees(self):
        """Test eligibility based on ≤ 30 employees."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=2000000,  # Over $1M, but employees under 30
            prior_year_full_time_employees=25,
            total_eligible_expenditures=5000,
        )
        assert info.is_eligible_small_business() is True

    def test_eligible_by_both(self):
        """Test eligibility when meeting both criteria."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=5000,
        )
        assert info.is_eligible_small_business() is True

    def test_not_eligible(self):
        """Test ineligibility when failing both criteria."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=2000000,  # Over $1M
            prior_year_full_time_employees=50,  # Over 30
            total_eligible_expenditures=5000,
        )
        assert info.is_eligible_small_business() is False

    def test_boundary_gross_receipts_exactly_1m(self):
        """Test eligibility at exactly $1M gross receipts."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=1000000,  # Exactly $1M
            prior_year_full_time_employees=50,
            total_eligible_expenditures=5000,
        )
        assert info.is_eligible_small_business() is True

    def test_boundary_employees_exactly_30(self):
        """Test eligibility at exactly 30 employees."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=2000000,
            prior_year_full_time_employees=30,  # Exactly 30
            total_eligible_expenditures=5000,
        )
        assert info.is_eligible_small_business() is True


class TestDisabledAccessEligibleAmount:
    """Tests for eligible amount calculation."""

    def test_below_minimum_threshold(self):
        """Test expenditures below $250 minimum."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=200,  # Below $250
        )
        assert info.calculate_eligible_amount() == 0.0

    def test_exactly_minimum_threshold(self):
        """Test expenditures at exactly $250."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=250,  # Exactly $250
        )
        assert info.calculate_eligible_amount() == 0.0  # Must exceed, not equal

    def test_just_above_minimum(self):
        """Test expenditures just above $250."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=500,
        )
        # $500 - $250 = $250 eligible
        assert info.calculate_eligible_amount() == 250.0

    def test_midrange_expenditure(self):
        """Test expenditures in the middle of the range."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=5000,
        )
        # $5,000 - $250 = $4,750 eligible
        assert info.calculate_eligible_amount() == 4750.0

    def test_maximum_eligible_amount(self):
        """Test expenditures at exactly $10,250 (maximum)."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=10250,
        )
        # $10,250 - $250 = $10,000 eligible (maximum)
        assert info.calculate_eligible_amount() == 10000.0

    def test_above_maximum(self):
        """Test expenditures above $10,250 (capped)."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=20000,
        )
        # Capped at $10,250 - $250 = $10,000 eligible
        assert info.calculate_eligible_amount() == 10000.0


class TestDisabledAccessItemizedExpenditures:
    """Tests for itemized expenditure handling."""

    def test_itemized_total(self):
        """Test total calculation from itemized expenditures."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            expenditures=[
                DisabledAccessExpenditure(
                    description="Install wheelchair ramp",
                    expenditure_type=DisabledAccessExpenditureType.BARRIER_REMOVAL,
                    amount=3000,
                ),
                DisabledAccessExpenditure(
                    description="Automatic door openers",
                    expenditure_type=DisabledAccessExpenditureType.EQUIPMENT_ACQUISITION,
                    amount=2000,
                ),
            ],
        )
        assert info.get_total_expenditures() == 5000.0

    def test_itemized_overrides_total(self):
        """Test that itemized expenditures override total field."""
        info = DisabledAccessInfo(
            prior_year_gross_receipts=500000,
            prior_year_full_time_employees=20,
            total_eligible_expenditures=1000,  # Should be ignored
            expenditures=[
                DisabledAccessExpenditure(
                    description="Sign language interpreter",
                    expenditure_type=DisabledAccessExpenditureType.INTERPRETER_SERVICES,
                    amount=5000,
                ),
            ],
        )
        assert info.get_total_expenditures() == 5000.0


class TestDisabledAccessCreditCalculation:
    """Tests for credit calculation."""

    def test_no_info(self):
        """Test with no disabled access info."""
        credits = TaxCredits()
        credit, breakdown = credits.calculate_disabled_access_credit()
        assert credit == 0.0
        assert breakdown['qualified'] is False

    def test_basic_credit_calculation(self):
        """Test basic credit calculation at 50%."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=5000,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        # Eligible: $5,000 - $250 = $4,750
        # Credit: 50% × $4,750 = $2,375
        assert credit == 2375.0
        assert breakdown['eligible_expenditures'] == 4750.0
        assert breakdown['credit_rate'] == 0.50
        assert breakdown['qualified'] is True

    def test_maximum_credit(self):
        """Test maximum credit of $5,000."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=15000,  # Above max threshold
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        # Eligible capped at $10,000
        # Credit: 50% × $10,000 = $5,000
        assert credit == 5000.0
        assert breakdown['eligible_expenditures'] == 10000.0
        assert breakdown['max_credit'] == 5000.0

    def test_small_expenditure(self):
        """Test small expenditure just above minimum."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=350,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        # Eligible: $350 - $250 = $100
        # Credit: 50% × $100 = $50
        assert credit == 50.0
        assert breakdown['eligible_expenditures'] == 100.0


class TestDisabledAccessCreditDisqualifications:
    """Tests for disqualification scenarios."""

    def test_disqualified_both_tests_fail(self):
        """Test disqualification when both eligibility tests fail."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=2000000,  # Over $1M
                prior_year_full_time_employees=50,  # Over 30
                total_eligible_expenditures=5000,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert credit == 0.0
        assert breakdown['qualified'] is False
        assert breakdown['meets_gross_receipts_test'] is False
        assert breakdown['meets_employee_test'] is False
        assert 'does not qualify' in breakdown['disqualification_reason']

    def test_disqualified_below_minimum_expenditure(self):
        """Test disqualification when expenditures don't exceed $250."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=200,  # Below $250
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert credit == 0.0
        assert breakdown['qualified'] is False
        assert 'must exceed' in breakdown['disqualification_reason']

    def test_disqualified_exactly_minimum(self):
        """Test disqualification at exactly $250 (must exceed)."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=250,  # Exactly $250
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert credit == 0.0
        assert breakdown['qualified'] is False


class TestDisabledAccessCreditEligibilityTests:
    """Tests for eligibility test tracking in breakdown."""

    def test_passes_gross_receipts_test_only(self):
        """Test when only gross receipts test passes."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,  # Under $1M
                prior_year_full_time_employees=50,  # Over 30
                total_eligible_expenditures=5000,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert breakdown['meets_gross_receipts_test'] is True
        assert breakdown['meets_employee_test'] is False
        assert breakdown['qualified'] is True  # One test is enough

    def test_passes_employee_test_only(self):
        """Test when only employee test passes."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=2000000,  # Over $1M
                prior_year_full_time_employees=20,  # Under 30
                total_eligible_expenditures=5000,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert breakdown['meets_gross_receipts_test'] is False
        assert breakdown['meets_employee_test'] is True
        assert breakdown['qualified'] is True  # One test is enough


class TestDisabledAccessCreditBreakdown:
    """Tests for breakdown details."""

    def test_breakdown_contents(self):
        """Test that breakdown contains all expected fields."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=750000,
                prior_year_full_time_employees=25,
                total_eligible_expenditures=6000,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert 'credit_amount' in breakdown
        assert 'total_expenditures' in breakdown
        assert 'eligible_expenditures' in breakdown
        assert 'min_threshold' in breakdown
        assert 'max_threshold' in breakdown
        assert 'credit_rate' in breakdown
        assert 'max_credit' in breakdown
        assert 'prior_year_gross_receipts' in breakdown
        assert 'prior_year_employees' in breakdown
        assert 'meets_gross_receipts_test' in breakdown
        assert 'meets_employee_test' in breakdown

        assert breakdown['prior_year_gross_receipts'] == 750000
        assert breakdown['prior_year_employees'] == 25
        assert breakdown['total_expenditures'] == 6000.0
        assert breakdown['min_threshold'] == 250.0
        assert breakdown['max_threshold'] == 10250.0

    def test_breakdown_with_itemized_expenditures(self):
        """Test breakdown includes itemized expenditure details."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                expenditures=[
                    DisabledAccessExpenditure(
                        description="Wheelchair ramp",
                        expenditure_type=DisabledAccessExpenditureType.BARRIER_REMOVAL,
                        amount=3000,
                    ),
                    DisabledAccessExpenditure(
                        description="Braille signage",
                        expenditure_type=DisabledAccessExpenditureType.MATERIAL_FORMATS,
                        amount=1000,
                    ),
                ],
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        assert len(breakdown['expenditure_details']) == 2
        assert breakdown['expenditure_details'][0]['description'] == "Wheelchair ramp"
        assert breakdown['expenditure_details'][0]['type'] == 'barrier_removal'
        assert breakdown['expenditure_details'][0]['amount'] == 3000
        assert breakdown['expenditure_details'][1]['type'] == 'materials'


class TestDisabledAccessExpenditureTypes:
    """Tests for different expenditure types."""

    def test_barrier_removal(self):
        """Test barrier removal expenditure type."""
        exp = DisabledAccessExpenditure(
            description="Remove architectural barrier",
            expenditure_type=DisabledAccessExpenditureType.BARRIER_REMOVAL,
            amount=5000,
        )
        assert exp.expenditure_type == DisabledAccessExpenditureType.BARRIER_REMOVAL

    def test_interpreter_services(self):
        """Test interpreter services expenditure type."""
        exp = DisabledAccessExpenditure(
            description="Sign language interpreter",
            expenditure_type=DisabledAccessExpenditureType.INTERPRETER_SERVICES,
            amount=2000,
        )
        assert exp.expenditure_type == DisabledAccessExpenditureType.INTERPRETER_SERVICES

    def test_equipment_acquisition(self):
        """Test equipment acquisition expenditure type."""
        exp = DisabledAccessExpenditure(
            description="Adaptive equipment",
            expenditure_type=DisabledAccessExpenditureType.EQUIPMENT_ACQUISITION,
            amount=3000,
        )
        assert exp.expenditure_type == DisabledAccessExpenditureType.EQUIPMENT_ACQUISITION

    def test_all_types_in_calculation(self):
        """Test credit calculation with all expenditure types."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                expenditures=[
                    DisabledAccessExpenditure(
                        description="Ramp",
                        expenditure_type=DisabledAccessExpenditureType.BARRIER_REMOVAL,
                        amount=1000,
                    ),
                    DisabledAccessExpenditure(
                        description="Interpreter",
                        expenditure_type=DisabledAccessExpenditureType.INTERPRETER_SERVICES,
                        amount=500,
                    ),
                    DisabledAccessExpenditure(
                        description="Reader",
                        expenditure_type=DisabledAccessExpenditureType.READER_SERVICES,
                        amount=500,
                    ),
                    DisabledAccessExpenditure(
                        description="Equipment",
                        expenditure_type=DisabledAccessExpenditureType.EQUIPMENT_ACQUISITION,
                        amount=500,
                    ),
                    DisabledAccessExpenditure(
                        description="Braille",
                        expenditure_type=DisabledAccessExpenditureType.MATERIAL_FORMATS,
                        amount=500,
                    ),
                    DisabledAccessExpenditure(
                        description="Other",
                        expenditure_type=DisabledAccessExpenditureType.OTHER_ACCESSIBILITY,
                        amount=500,
                    ),
                ],
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        # Total: $3,500
        # Eligible: $3,500 - $250 = $3,250
        # Credit: 50% × $3,250 = $1,625
        assert credit == 1625.0
        assert breakdown['total_expenditures'] == 3500.0


class TestDisabledAccessCreditEdgeCases:
    """Tests for edge cases."""

    def test_zero_expenditures(self):
        """Test with zero expenditures."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=0,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()
        assert credit == 0.0
        assert breakdown['qualified'] is False

    def test_very_small_business(self):
        """Test with very small business (1 employee)."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=50000,
                prior_year_full_time_employees=1,
                total_eligible_expenditures=1000,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        # Eligible: $1,000 - $250 = $750
        # Credit: 50% × $750 = $375
        assert credit == 375.0
        assert breakdown['qualified'] is True

    def test_boundary_expenditure_251(self):
        """Test expenditure at $251 (just above minimum)."""
        credits = TaxCredits(
            disabled_access_info=DisabledAccessInfo(
                prior_year_gross_receipts=500000,
                prior_year_full_time_employees=20,
                total_eligible_expenditures=251,
            )
        )
        credit, breakdown = credits.calculate_disabled_access_credit()

        # Eligible: $251 - $250 = $1
        # Credit: 50% × $1 = $0.50
        assert credit == 0.50
        assert breakdown['eligible_expenditures'] == 1.0
