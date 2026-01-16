"""
Test suite for Schedule A (Form 1040) - Itemized Deductions.

Tests cover:
- Medical expense deduction (7.5% AGI floor)
- SALT deduction with $10,000 cap
- Mortgage interest deduction with TCJA limits
- Charitable contribution deductions
- Other itemized deductions
- Complete Schedule A calculation
"""

import pytest
from src.models.schedule_a import (
    ScheduleA,
    MortgageInterestInfo,
    MortgageType,
    CharitableContribution,
    CharitableContributionType,
    create_schedule_a,
)


class TestMedicalExpenseDeduction:
    """Tests for medical expense deduction calculation."""

    def test_medical_expense_over_floor(self):
        """Medical expenses over 7.5% floor are deductible."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            medical_expenses_total=10000.0,
        )
        result = schedule.calculate_medical_deduction()

        assert result['floor_amount'] == 7500.0  # 7.5% of $100k
        assert result['deductible_amount'] == 2500.0  # $10k - $7.5k

    def test_medical_expense_under_floor(self):
        """Medical expenses under 7.5% floor are not deductible."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            medical_expenses_total=5000.0,
        )
        result = schedule.calculate_medical_deduction()

        assert result['deductible_amount'] == 0.0

    def test_medical_expense_exact_floor(self):
        """Medical expenses at exactly floor amount."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            medical_expenses_total=7500.0,
        )
        result = schedule.calculate_medical_deduction()

        assert result['deductible_amount'] == 0.0


class TestSALTDeduction:
    """Tests for state and local tax deduction with cap."""

    def test_salt_under_cap(self):
        """SALT under $10,000 cap is fully deductible."""
        schedule = ScheduleA(
            state_income_tax=5000.0,
            real_estate_taxes=3000.0,
        )
        result = schedule.calculate_taxes_paid_deduction()

        assert result['deductible_amount'] == 8000.0

    def test_salt_at_cap(self):
        """SALT at exactly $10,000 cap."""
        schedule = ScheduleA(
            state_income_tax=6000.0,
            real_estate_taxes=4000.0,
        )
        result = schedule.calculate_taxes_paid_deduction()

        assert result['deductible_amount'] == 10000.0

    def test_salt_over_cap(self):
        """SALT over $10,000 cap is limited."""
        schedule = ScheduleA(
            state_income_tax=8000.0,
            real_estate_taxes=6000.0,
            personal_property_taxes=2000.0,
        )
        result = schedule.calculate_taxes_paid_deduction()

        assert result['total_before_cap'] == 16000.0
        assert result['deductible_amount'] == 10000.0
        assert result['amount_over_cap'] == 6000.0

    def test_salt_cap_married_separate(self):
        """MFS has $5,000 SALT cap."""
        schedule = ScheduleA(
            state_income_tax=4000.0,
            real_estate_taxes=3000.0,
            filing_status="married_separate",
        )
        result = schedule.calculate_taxes_paid_deduction()

        assert result['salt_cap'] == 5000.0
        assert result['deductible_amount'] == 5000.0

    def test_salt_sales_tax_election(self):
        """Elect sales tax instead of income tax."""
        schedule = ScheduleA(
            state_income_tax=5000.0,
            state_sales_tax=6000.0,
            use_sales_tax=True,
        )
        result = schedule.calculate_taxes_paid_deduction()

        assert result['state_local_tax'] == 6000.0  # Sales tax used


class TestMortgageInterestDeduction:
    """Tests for mortgage interest deduction."""

    def test_mortgage_under_limit(self):
        """Mortgage under $750,000 limit is fully deductible."""
        schedule = ScheduleA(
            mortgages=[
                MortgageInterestInfo(
                    lender_name="Bank",
                    interest_paid=15000.0,
                    outstanding_balance=500000.0,
                )
            ]
        )
        result = schedule.calculate_interest_deduction()

        assert result['deductible_mortgage_interest'] == 15000.0

    def test_mortgage_over_limit(self):
        """Mortgage over $750,000 limit is prorated."""
        schedule = ScheduleA(
            mortgages=[
                MortgageInterestInfo(
                    lender_name="Bank",
                    interest_paid=30000.0,
                    outstanding_balance=1000000.0,
                )
            ]
        )
        result = schedule.calculate_interest_deduction()

        # 750k/1000k = 75% of interest is deductible
        assert result['deductible_mortgage_interest'] == 22500.0

    def test_grandfathered_mortgage(self):
        """Grandfathered mortgage has $1M limit."""
        schedule = ScheduleA(
            mortgages=[
                MortgageInterestInfo(
                    lender_name="Bank",
                    interest_paid=40000.0,
                    outstanding_balance=900000.0,
                    is_grandfathered=True,
                )
            ]
        )
        result = schedule.calculate_interest_deduction()

        # Under $1M grandfathered limit
        assert result['deductible_mortgage_interest'] == 40000.0

    def test_investment_interest(self):
        """Investment interest is added to total."""
        schedule = ScheduleA(
            mortgages=[
                MortgageInterestInfo(
                    lender_name="Bank",
                    interest_paid=10000.0,
                    outstanding_balance=400000.0,
                )
            ],
            investment_interest=2000.0,
        )
        result = schedule.calculate_interest_deduction()

        assert result['total_deductible'] == 12000.0


class TestCharitableDeduction:
    """Tests for charitable contribution deduction."""

    def test_cash_contributions(self):
        """Cash contributions are deductible."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            charitable_contributions=[
                CharitableContribution(
                    organization_name="Charity",
                    contribution_type=CharitableContributionType.CASH,
                    amount=5000.0,
                )
            ],
        )
        result = schedule.calculate_charitable_deduction()

        assert result['cash_contributions'] == 5000.0
        assert result['deductible_amount'] == 5000.0

    def test_property_contributions(self):
        """Property contributions are deductible."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            charitable_contributions=[
                CharitableContribution(
                    organization_name="Charity",
                    contribution_type=CharitableContributionType.PROPERTY,
                    amount=3000.0,
                )
            ],
        )
        result = schedule.calculate_charitable_deduction()

        assert result['property_contributions'] == 3000.0

    def test_charitable_agi_limitation(self):
        """Charitable contributions limited by AGI."""
        schedule = ScheduleA(
            agi_for_medical=10000.0,
            charitable_contributions=[
                CharitableContribution(
                    organization_name="Charity",
                    contribution_type=CharitableContributionType.CASH,
                    amount=8000.0,  # 80% of AGI, exceeds 60% limit
                )
            ],
        )
        result = schedule.calculate_charitable_deduction()

        # Limited to 60% of AGI = $6,000
        assert result['deductible_amount'] == 6000.0

    def test_charitable_carryover(self):
        """Carryover from prior year is included."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            charitable_contributions=[
                CharitableContribution(
                    organization_name="Charity",
                    contribution_type=CharitableContributionType.CASH,
                    amount=2000.0,
                )
            ],
            carryover_from_prior_year=1000.0,
        )
        result = schedule.calculate_charitable_deduction()

        assert result['carryover_used'] == 1000.0


class TestOtherDeductions:
    """Tests for other itemized deductions."""

    def test_gambling_losses_limited(self):
        """Gambling losses limited to winnings."""
        schedule = ScheduleA(
            gambling_losses=5000.0,
            gambling_winnings=3000.0,
        )
        result = schedule.calculate_other_deductions()

        assert result['deductible_gambling_losses'] == 3000.0

    def test_gambling_losses_under_winnings(self):
        """Gambling losses less than winnings."""
        schedule = ScheduleA(
            gambling_losses=2000.0,
            gambling_winnings=5000.0,
        )
        result = schedule.calculate_other_deductions()

        assert result['deductible_gambling_losses'] == 2000.0

    def test_casualty_loss(self):
        """Casualty loss from federally declared disaster."""
        schedule = ScheduleA(
            casualty_loss_amount=10000.0,
        )
        result = schedule.calculate_other_deductions()

        assert result['casualty_loss'] == 10000.0


class TestCompleteScheduleA:
    """Tests for complete Schedule A calculation."""

    def test_complete_calculation(self):
        """Complete Schedule A with all categories."""
        schedule = ScheduleA(
            agi_for_medical=150000.0,
            medical_expenses_total=15000.0,  # $15k - $11.25k (7.5%) = $3,750
            state_income_tax=8000.0,
            real_estate_taxes=6000.0,  # $14k total, capped at $10k
            mortgages=[
                MortgageInterestInfo(
                    lender_name="Bank",
                    interest_paid=12000.0,
                    outstanding_balance=400000.0,
                )
            ],
            charitable_contributions=[
                CharitableContribution(
                    organization_name="Charity",
                    contribution_type=CharitableContributionType.CASH,
                    amount=5000.0,
                )
            ],
        )

        result = schedule.calculate_schedule_a()

        assert result['line_4_medical_deduction'] == 3750.0
        assert result['line_5e_salt_deduction'] == 10000.0
        assert result['line_10_interest_total'] == 12000.0
        assert result['line_14_charitable_total'] == 5000.0
        assert result['line_17_total_itemized'] == 30750.0

    def test_summary_method(self):
        """Get schedule A summary."""
        schedule = ScheduleA(
            agi_for_medical=100000.0,
            state_income_tax=5000.0,
            real_estate_taxes=4000.0,
        )

        summary = schedule.get_schedule_a_summary()

        assert 'total_itemized' in summary
        assert 'taxes_paid' in summary
        assert summary['taxes_paid'] == 9000.0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function(self):
        """Create Schedule A with convenience function."""
        result = create_schedule_a(
            agi=100000.0,
            medical_expenses=10000.0,
            state_income_tax=5000.0,
            real_estate_taxes=4000.0,
            mortgage_interest=8000.0,
            mortgage_balance=300000.0,
            charitable_cash=3000.0,
        )

        assert result['line_4_medical_deduction'] == 2500.0  # $10k - $7.5k
        assert result['line_5e_salt_deduction'] == 9000.0
        assert result['line_10_interest_total'] == 8000.0
        assert result['line_14_charitable_total'] == 3000.0

    def test_convenience_function_simple(self):
        """Simple Schedule A calculation."""
        result = create_schedule_a(
            agi=80000.0,
            state_income_tax=6000.0,
            real_estate_taxes=5000.0,
        )

        assert result['line_5e_salt_deduction'] == 10000.0  # Capped
        assert result['total_itemized_deductions'] == 10000.0
