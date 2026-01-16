"""
Test suite for Schedule B (Form 1040) - Interest and Ordinary Dividends.

Tests cover:
- Part I: Interest income reporting
- Part II: Dividend income reporting
- Part III: Foreign account reporting (FBAR triggers)
- Schedule B filing requirements
"""

import pytest
from src.models.schedule_b import (
    ScheduleB,
    InterestPayer,
    InterestType,
    DividendPayer,
    ForeignAccount,
    create_schedule_b,
)


class TestPartIInterest:
    """Tests for Part I - Interest income."""

    def test_single_interest_payer(self):
        """Single interest payer reported correctly."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(
                    payer_name="ABC Bank",
                    amount=1000.0,
                )
            ]
        )
        result = schedule.calculate_part_i_interest()

        assert result['payer_count'] == 1
        assert result['taxable_interest'] == 1000.0

    def test_multiple_interest_payers(self):
        """Multiple interest payers totaled."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(payer_name="Bank A", amount=500.0),
                InterestPayer(payer_name="Bank B", amount=750.0),
                InterestPayer(payer_name="Bank C", amount=250.0),
            ]
        )
        result = schedule.calculate_part_i_interest()

        assert result['payer_count'] == 3
        assert result['taxable_interest'] == 1500.0

    def test_tax_exempt_interest(self):
        """Tax-exempt interest tracked separately."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(
                    payer_name="Muni Bond Fund",
                    amount=0.0,
                    tax_exempt_interest=2000.0,
                    interest_type=InterestType.TAX_EXEMPT,
                )
            ]
        )
        result = schedule.calculate_part_i_interest()

        assert result['taxable_interest'] == 0.0
        assert result['tax_exempt_interest'] == 2000.0

    def test_early_withdrawal_penalty(self):
        """Early withdrawal penalty reported."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(
                    payer_name="CD Bank",
                    amount=500.0,
                    early_withdrawal_penalty=100.0,
                )
            ]
        )
        result = schedule.calculate_part_i_interest()

        assert result['early_withdrawal_penalty'] == 100.0

    def test_filing_threshold_met(self):
        """Schedule B required if interest > $1,500."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(payer_name="Bank", amount=2000.0),
            ]
        )
        result = schedule.calculate_part_i_interest()

        assert result['requires_schedule_b'] is True

    def test_filing_threshold_not_met(self):
        """Schedule B not required if interest <= $1,500."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(payer_name="Bank", amount=1000.0),
            ]
        )
        result = schedule.calculate_part_i_interest()

        assert result['requires_schedule_b'] is False


class TestPartIIDividends:
    """Tests for Part II - Dividend income."""

    def test_ordinary_dividends(self):
        """Ordinary dividends reported correctly."""
        schedule = ScheduleB(
            dividend_payers=[
                DividendPayer(
                    payer_name="Stock Fund",
                    ordinary_dividends=2000.0,
                    qualified_dividends=1500.0,
                )
            ]
        )
        result = schedule.calculate_part_ii_dividends()

        assert result['ordinary_dividends'] == 2000.0
        assert result['qualified_dividends'] == 1500.0

    def test_capital_gain_distributions(self):
        """Capital gain distributions tracked."""
        schedule = ScheduleB(
            dividend_payers=[
                DividendPayer(
                    payer_name="Mutual Fund",
                    ordinary_dividends=1000.0,
                    capital_gain_distributions=500.0,
                )
            ]
        )
        result = schedule.calculate_part_ii_dividends()

        assert result['capital_gain_distributions'] == 500.0

    def test_section_199a_dividends(self):
        """Section 199A dividends from REITs tracked."""
        schedule = ScheduleB(
            dividend_payers=[
                DividendPayer(
                    payer_name="REIT Fund",
                    ordinary_dividends=3000.0,
                    section_199a_dividends=2500.0,
                )
            ]
        )
        result = schedule.calculate_part_ii_dividends()

        assert result['section_199a_dividends'] == 2500.0

    def test_dividend_filing_threshold(self):
        """Schedule B required if dividends > $1,500."""
        schedule = ScheduleB(
            dividend_payers=[
                DividendPayer(payer_name="Fund", ordinary_dividends=2000.0),
            ]
        )
        result = schedule.calculate_part_ii_dividends()

        assert result['requires_schedule_b'] is True


class TestPartIIIForeign:
    """Tests for Part III - Foreign accounts."""

    def test_no_foreign_accounts(self):
        """No foreign accounts reported."""
        schedule = ScheduleB()
        result = schedule.calculate_part_iii_foreign()

        assert result['has_foreign_accounts'] is False
        assert result['requires_fbar'] is False

    def test_foreign_account_under_threshold(self):
        """Foreign account under $10,000 FBAR threshold."""
        schedule = ScheduleB(
            has_foreign_accounts=True,
            foreign_accounts=[
                ForeignAccount(
                    country="Canada",
                    maximum_value=5000.0,
                )
            ]
        )
        result = schedule.calculate_part_iii_foreign()

        assert result['has_foreign_accounts'] is True
        assert result['requires_fbar'] is False

    def test_foreign_account_over_threshold(self):
        """Foreign account over $10,000 requires FBAR."""
        schedule = ScheduleB(
            foreign_accounts=[
                ForeignAccount(
                    country="Switzerland",
                    maximum_value=25000.0,
                )
            ]
        )
        result = schedule.calculate_part_iii_foreign()

        assert result['requires_fbar'] is True
        assert result['total_maximum_value'] == 25000.0

    def test_multiple_foreign_accounts(self):
        """Multiple foreign accounts aggregated."""
        schedule = ScheduleB(
            foreign_accounts=[
                ForeignAccount(country="UK", maximum_value=6000.0),
                ForeignAccount(country="Germany", maximum_value=8000.0),
            ]
        )
        result = schedule.calculate_part_iii_foreign()

        assert result['account_count'] == 2
        assert result['total_maximum_value'] == 14000.0
        assert result['requires_fbar'] is True
        assert len(result['countries']) == 2

    def test_foreign_trust_distribution(self):
        """Foreign trust distribution reported."""
        schedule = ScheduleB(
            received_foreign_trust_distribution=True,
        )
        result = schedule.calculate_part_iii_foreign()

        assert result['line_8_answer'] == 'Yes'


class TestCompleteScheduleB:
    """Tests for complete Schedule B calculation."""

    def test_complete_calculation(self):
        """Complete Schedule B with all parts."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(payer_name="Bank", amount=2500.0),
            ],
            dividend_payers=[
                DividendPayer(
                    payer_name="Fund",
                    ordinary_dividends=3000.0,
                    qualified_dividends=2000.0,
                    capital_gain_distributions=500.0,
                )
            ],
            has_foreign_accounts=True,
            foreign_accounts=[
                ForeignAccount(country="UK", maximum_value=15000.0),
            ]
        )

        result = schedule.calculate_schedule_b()

        assert result['form_1040_line_2b_taxable_interest'] == 2500.0
        assert result['form_1040_line_3b_ordinary_dividends'] == 3000.0
        assert result['form_1040_line_3a_qualified_dividends'] == 2000.0
        assert result['capital_gain_distributions'] == 500.0
        assert result['schedule_b_required'] is True
        assert result['fbar_required'] is True

    def test_summary_method(self):
        """Get Schedule B summary."""
        schedule = ScheduleB(
            interest_payers=[
                InterestPayer(payer_name="Bank", amount=1000.0),
            ],
            dividend_payers=[
                DividendPayer(
                    payer_name="Fund",
                    ordinary_dividends=2000.0,
                    qualified_dividends=1500.0,
                )
            ],
        )

        summary = schedule.get_schedule_b_summary()

        assert summary['taxable_interest'] == 1000.0
        assert summary['ordinary_dividends'] == 2000.0
        assert summary['qualified_dividends'] == 1500.0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_basic(self):
        """Create Schedule B with convenience function."""
        result = create_schedule_b(
            interest_income=2000.0,
            ordinary_dividends=3000.0,
            qualified_dividends=2500.0,
        )

        assert result['form_1040_line_2b_taxable_interest'] == 2000.0
        assert result['form_1040_line_3b_ordinary_dividends'] == 3000.0
        assert result['form_1040_line_3a_qualified_dividends'] == 2500.0

    def test_convenience_function_with_foreign(self):
        """Schedule B with foreign account."""
        result = create_schedule_b(
            interest_income=1000.0,
            has_foreign_accounts=True,
            foreign_account_value=20000.0,
            foreign_country="Canada",
        )

        assert result['fbar_required'] is True
        assert result['schedule_b_required'] is True

    def test_convenience_function_exempt_interest(self):
        """Schedule B with tax-exempt interest."""
        result = create_schedule_b(
            interest_income=500.0,
            tax_exempt_interest=1500.0,
        )

        assert result['form_1040_line_2b_taxable_interest'] == 500.0
        assert result['form_1040_line_2a_tax_exempt_interest'] == 1500.0
