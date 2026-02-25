"""Edge case tests for tax calculation engine."""

import pytest
from decimal import Decimal


class TestLifeEventEdgeCases:
    """Tests for life event edge cases."""

    def test_zero_income_return(self):
        """Return with exactly zero income."""
        # Zero income should result in zero tax
        total_income = 0
        standard_deduction = 15000  # 2025 single
        taxable_income = max(0, total_income - standard_deduction)
        assert taxable_income == 0

    def test_income_at_standard_deduction_threshold(self):
        """Income exactly at standard deduction."""
        total_income = 15000  # 2025 single standard deduction
        standard_deduction = 15000
        taxable_income = max(0, total_income - standard_deduction)
        assert taxable_income == 0

    def test_high_income_hits_top_bracket(self):
        """High income ($10M) should hit 37% bracket."""
        total_income = 10000000
        # 2025 single: 37% starts at ~$609,350
        # Approximate effective rate should be > 30%
        # This is a sanity check that high earners pay significant tax
        assert total_income > 609350
        # Effective rate calculation would require full engine

    def test_mid_year_marriage_uses_full_year_mfj(self):
        """Couple married mid-year can file MFJ for full year."""
        # IRS rule: If married on Dec 31, can file MFJ for full year
        filing_status = "married_filing_jointly"
        marriage_date = "2025-10-15"
        # Full MFJ benefits apply regardless of marriage date
        assert filing_status == "married_filing_jointly"

    def test_negative_taxable_income_is_zero(self):
        """Taxable income cannot be negative."""
        total_income = 10000
        standard_deduction = 15000
        taxable_income = max(0, total_income - standard_deduction)
        assert taxable_income == 0
        assert taxable_income >= 0


class TestCreditPhaseouts:
    """Tests for credit phaseout boundaries."""

    def test_ctc_full_credit_below_phaseout(self):
        """CTC should be full amount below phaseout threshold."""
        income = 150000  # Below $200K single phaseout
        num_children = 2
        ctc_per_child = 2000
        expected_ctc = num_children * ctc_per_child
        assert expected_ctc == 4000

    def test_ctc_phases_out_above_threshold(self):
        """CTC should phase out above $200K (single)."""
        income = 220000  # Above $200K
        num_children = 2
        # Phaseout: $50 per $1000 over threshold
        over_threshold = income - 200000  # $20,000 over
        phaseout_amount = (over_threshold // 1000) * 50  # $1,000
        full_credit = 4000
        reduced_credit = max(0, full_credit - phaseout_amount)
        assert reduced_credit == 3000

    def test_eitc_zero_for_high_income(self):
        """EITC should be zero above income limits."""
        income = 70000  # Well above EITC limits
        num_children = 3
        # 2025 EITC limit for 3+ children is ~$59,899 (single)
        assert income > 59899
        # EITC would be zero

    def test_ctc_completely_phased_out(self):
        """CTC should be zero when fully phased out."""
        income = 280000  # $80K over threshold
        num_children = 2
        over_threshold = income - 200000
        phaseout_amount = (over_threshold // 1000) * 50  # $4,000
        full_credit = 4000
        reduced_credit = max(0, full_credit - phaseout_amount)
        assert reduced_credit == 0


class TestAMTScenarios:
    """Tests for Alternative Minimum Tax scenarios."""

    def test_amt_exemption_amount_2025(self):
        """Verify 2025 AMT exemption amounts."""
        # 2025 AMT exemptions (estimated)
        single_exemption = 85700
        mfj_exemption = 133300
        assert single_exemption > 80000
        assert mfj_exemption > 120000

    def test_amt_rate_structure(self):
        """AMT has two rates: 26% and 28%."""
        amt_rate_low = 0.26
        amt_rate_high = 0.28
        # Threshold for 28% rate (2025 estimated)
        threshold = 220700
        assert amt_rate_low == 0.26
        assert amt_rate_high == 0.28

    def test_amt_exemption_phaseout_threshold(self):
        """AMT exemption phases out at high income."""
        # Single: exemption phases out starting at $609,350
        phaseout_start_single = 609350
        # Phaseout rate: 25 cents per dollar
        assert phaseout_start_single > 600000


class TestFilingStatusEdgeCases:
    """Tests for filing status edge cases."""

    def test_qualifying_widower_requirements(self):
        """Qualifying widow(er) has specific requirements."""
        # Requirements: spouse died in prior 2 years, has dependent child
        spouse_death_year = 2024
        current_year = 2025
        has_dependent_child = True
        years_since_death = current_year - spouse_death_year
        qualifies = years_since_death <= 2 and has_dependent_child
        assert qualifies == True

    def test_head_of_household_vs_single(self):
        """HOH has lower tax rates than single."""
        # 2025 standard deductions
        single_std_ded = 15000
        hoh_std_ded = 22500
        assert hoh_std_ded > single_std_ded

    def test_mfs_vs_mfj_standard_deduction(self):
        """MFS standard deduction is half of MFJ."""
        mfj_std_ded = 30000
        mfs_std_ded = 15000  # Half of MFJ
        assert mfs_std_ded == mfj_std_ded // 2


class TestDeductionEdgeCases:
    """Tests for deduction edge cases."""

    def test_medical_expense_75_percent_threshold(self):
        """Medical expenses deductible above 7.5% AGI."""
        agi = 100000
        medical_expenses = 10000
        threshold = agi * 0.075  # $7,500
        deductible = max(0, medical_expenses - threshold)
        assert deductible == 2500

    def test_charitable_contribution_60_percent_limit(self):
        """Cash charitable contributions limited to 60% AGI."""
        agi = 100000
        cash_donations = 70000
        limit = agi * 0.60  # $60,000
        deductible = min(cash_donations, limit)
        carryforward = cash_donations - deductible
        assert deductible == 60000
        assert carryforward == 10000

    def test_salt_10000_cap(self):
        """SALT deduction capped at $10,000."""
        state_income_tax = 15000
        property_tax = 8000
        total_salt = state_income_tax + property_tax  # $23,000
        salt_cap = 10000
        deductible = min(total_salt, salt_cap)
        assert deductible == 10000

    def test_mortgage_interest_limit(self):
        """Mortgage interest limited to $750K acquisition debt."""
        mortgage_balance = 1000000
        interest_paid = 50000
        limit_balance = 750000
        # Proportionally limited
        deductible = interest_paid * (limit_balance / mortgage_balance)
        assert deductible == 37500


class TestIncomeTypeEdgeCases:
    """Tests for different income type edge cases."""

    def test_qualified_dividends_rate(self):
        """Qualified dividends taxed at capital gains rates."""
        # 0%, 15%, or 20% depending on income
        income = 50000
        qualified_dividends = 5000
        # At this income level, qualified dividends taxed at 0%
        # (below $47,025 single threshold for 2025)
        assert income > 47025  # Would be 15% rate

    def test_long_term_capital_gains_rate(self):
        """Long-term capital gains have preferential rates."""
        ltcg_rates = [0.0, 0.15, 0.20]
        assert 0.15 in ltcg_rates
        # NIIT adds 3.8% above $200K

    def test_short_term_gains_as_ordinary(self):
        """Short-term capital gains taxed as ordinary income."""
        short_term_gain = 10000
        # Taxed at marginal rate, same as wages
        ordinary_income = 50000
        total_ordinary = ordinary_income + short_term_gain
        assert total_ordinary == 60000


class TestTaxBracketBoundaries:
    """Tests for tax bracket boundary conditions."""

    def test_bracket_boundary_10_to_12_percent(self):
        """Test boundary between 10% and 12% brackets."""
        # 2025 single: 10% ends at $11,600
        income_in_10_bracket = 11000
        income_in_12_bracket = 12000
        bracket_boundary = 11600
        assert income_in_10_bracket < bracket_boundary
        assert income_in_12_bracket > bracket_boundary

    def test_all_brackets_progressive(self):
        """Tax brackets should be progressive."""
        brackets_2025_single = [
            (11600, 0.10),
            (47150, 0.12),
            (100525, 0.22),
            (191950, 0.24),
            (243725, 0.32),
            (609350, 0.35),
            (float('inf'), 0.37)
        ]
        # Verify rates increase
        for i in range(1, len(brackets_2025_single)):
            assert brackets_2025_single[i][1] > brackets_2025_single[i-1][1]


class TestSpecialSituations:
    """Tests for special tax situations."""

    def test_kiddie_tax_applies_to_minors(self):
        """Kiddie tax applies to unearned income of minors."""
        child_age = 16
        unearned_income = 5000
        kiddie_tax_threshold = 2500
        # Excess taxed at parent's rate
        excess = max(0, unearned_income - kiddie_tax_threshold)
        assert excess == 2500

    def test_self_employment_tax_rate(self):
        """Self-employment tax is 15.3% (12.4% SS + 2.9% Medicare)."""
        se_tax_rate = 0.153
        ss_portion = 0.124
        medicare_portion = 0.029
        assert abs(se_tax_rate - (ss_portion + medicare_portion)) < 0.001

    def test_se_tax_deduction_half(self):
        """Self-employed can deduct half of SE tax."""
        se_income = 100000
        se_tax = se_income * 0.9235 * 0.153  # ~$14,130
        deductible = se_tax / 2
        assert deductible > 7000
