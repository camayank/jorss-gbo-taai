"""
Tests for Form 8889 - Health Savings Accounts (HSAs)

Tests cover:
- HSA contribution limits (self-only vs family)
- Catch-up contributions (age 55+)
- Pro-rata contribution limits (partial year coverage)
- Last-month rule
- Employer contributions
- HSA deduction calculation
- Distributions and qualified medical expenses
- Taxable distributions and 20% penalty
- Penalty exemptions (age 65+, disabled, deceased)
- Testing period failure
- Integration with Income model and engine
"""

import pytest

from models.form_8889 import (
    HSACoverageType,
    HDHPCoverageMonth,
    HSADistribution,
    HSAContribution,
    Form8889,
    HSAInfo,
)
from models.income import Income, W2Info
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


class TestContributionLimits:
    """Tests for HSA contribution limit calculations."""

    def test_self_only_limit(self):
        """Self-only coverage limit."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=4300.0,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 4300.0

    def test_family_limit(self):
        """Family coverage limit."""
        hsa = Form8889(
            coverage_type=HSACoverageType.FAMILY,
            taxpayer_contributions=8550.0,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 8550.0

    def test_catchup_contribution_55_plus(self):
        """Additional $1,000 catch-up for age 55+."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            is_age_55_or_older=True,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 5300.0  # 4300 + 1000

    def test_family_with_catchup(self):
        """Family coverage with catch-up contribution."""
        hsa = Form8889(
            coverage_type=HSACoverageType.FAMILY,
            is_age_55_or_older=True,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 9550.0  # 8550 + 1000


class TestProRataLimits:
    """Tests for pro-rata contribution limits (partial year coverage)."""

    def test_half_year_coverage(self):
        """6 months of coverage = half the annual limit."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            months_with_hdhp_coverage=6,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 2150.0  # 4300 * 6/12

    def test_one_month_coverage(self):
        """1 month of coverage."""
        hsa = Form8889(
            coverage_type=HSACoverageType.FAMILY,
            months_with_hdhp_coverage=1,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == round(8550 / 12, 2)  # 712.5

    def test_last_month_rule_full_limit(self):
        """Last-month rule allows full year limit."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            months_with_hdhp_coverage=1,  # Only December
            use_last_month_rule=True,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 4300.0  # Full year limit

    def test_last_month_rule_with_catchup(self):
        """Last-month rule with catch-up contribution."""
        hsa = Form8889(
            coverage_type=HSACoverageType.FAMILY,
            months_with_hdhp_coverage=3,
            use_last_month_rule=True,
            is_age_55_or_older=True,
        )
        limit = hsa.calculate_contribution_limit()
        assert limit == 9550.0  # Full family limit + catch-up

    def test_monthly_coverage_tracking(self):
        """Monthly coverage list syncs to months count."""
        months = [
            HDHPCoverageMonth(month=i, has_hdhp_coverage=i >= 7)
            for i in range(1, 13)
        ]
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            monthly_coverage=months,
        )
        # Covered Jul-Dec = 6 months
        assert hsa.months_with_hdhp_coverage == 6
        limit = hsa.calculate_contribution_limit()
        assert limit == 2150.0


class TestDeductionCalculation:
    """Tests for HSA deduction calculation."""

    def test_basic_deduction(self):
        """Basic deduction = contributions (under limit)."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=3000.0,
        )
        result = hsa.calculate_deduction()
        assert result['hsa_deduction'] == 3000.0
        assert result['excess_contributions'] == 0.0

    def test_deduction_at_limit(self):
        """Deduction at exactly the limit."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=4300.0,
        )
        result = hsa.calculate_deduction()
        assert result['hsa_deduction'] == 4300.0
        assert result['excess_contributions'] == 0.0

    def test_excess_contributions(self):
        """Contributions over limit create excess."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=5000.0,
        )
        result = hsa.calculate_deduction()
        assert result['hsa_deduction'] == 4300.0
        assert result['excess_contributions'] == 700.0

    def test_employer_contributions_reduce_deduction(self):
        """Employer contributions reduce taxpayer deduction."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=3000.0,
            employer_contributions=1500.0,
        )
        result = hsa.calculate_deduction()
        # Total: 4500, limit: 4300, limited to 4300
        # Deduction: 4300 - 1500 employer = 2800
        assert result['limited_contribution'] == 4300.0
        assert result['hsa_deduction'] == 2800.0
        assert result['excess_contributions'] == 200.0

    def test_employer_covers_all(self):
        """Employer contribution covers entire limit."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=0.0,
            employer_contributions=4300.0,
        )
        result = hsa.calculate_deduction()
        assert result['hsa_deduction'] == 0.0
        assert result['employer_contributions'] == 4300.0


class TestEligibility:
    """Tests for HSA eligibility."""

    def test_medicare_ineligible(self):
        """Cannot contribute if enrolled in Medicare."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=4000.0,
            is_enrolled_in_medicare=True,
        )
        result = hsa.calculate_deduction()
        assert result['is_eligible'] is False
        assert result['hsa_deduction'] == 0.0
        assert 'Medicare' in result['ineligibility_reason']

    def test_dependent_ineligible(self):
        """Cannot contribute if can be claimed as dependent."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=4000.0,
            can_be_claimed_as_dependent=True,
        )
        result = hsa.calculate_deduction()
        assert result['is_eligible'] is False
        assert result['hsa_deduction'] == 0.0


class TestDistributions:
    """Tests for HSA distributions."""

    def test_qualified_distribution_no_tax(self):
        """Qualified medical expenses are not taxable."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=5000.0,
        )
        assert hsa.get_taxable_distributions() == 0.0

    def test_partially_qualified_distribution(self):
        """Partially qualified distributions are taxable."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=3000.0,
        )
        assert hsa.get_taxable_distributions() == 2000.0

    def test_unqualified_distribution_taxable(self):
        """Unqualified distributions are fully taxable."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
        )
        assert hsa.get_taxable_distributions() == 5000.0

    def test_detailed_distributions(self):
        """Detailed distribution tracking."""
        distributions = [
            HSADistribution(amount=3000.0, qualified_medical_expense=True),
            HSADistribution(amount=2000.0, qualified_medical_expense=False),
        ]
        hsa = Form8889(distributions=distributions)

        assert hsa.get_total_distributions() == 5000.0
        assert hsa.get_qualified_distributions() == 3000.0
        assert hsa.get_taxable_distributions() == 2000.0


class TestAdditionalTax:
    """Tests for 20% additional tax on non-qualified distributions."""

    def test_penalty_on_unqualified(self):
        """20% penalty on non-qualified distributions."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
        )
        result = hsa.calculate_additional_tax()
        assert result['taxable_distributions'] == 5000.0
        assert result['additional_tax_penalty'] == 1000.0  # 20%
        assert result['is_penalty_exempt'] is False

    def test_age_65_exempt(self):
        """Age 65+ exempt from penalty (but still taxable)."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
            is_age_65_or_older=True,
        )
        result = hsa.calculate_additional_tax()
        assert result['taxable_distributions'] == 5000.0
        assert result['additional_tax_penalty'] == 0.0
        assert result['is_penalty_exempt'] is True
        assert result['exemption_reason'] == 'Age 65+'

    def test_disabled_exempt(self):
        """Disabled taxpayer exempt from penalty."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
            is_disabled=True,
        )
        result = hsa.calculate_additional_tax()
        assert result['additional_tax_penalty'] == 0.0
        assert result['exemption_reason'] == 'Disabled'

    def test_deceased_account_exempt(self):
        """Deceased account holder exempt from penalty."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
            is_deceased_account=True,
        )
        result = hsa.calculate_additional_tax()
        assert result['additional_tax_penalty'] == 0.0
        assert result['exemption_reason'] == 'Deceased account'

    def test_no_penalty_on_qualified(self):
        """No penalty on qualified distributions."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=5000.0,
        )
        result = hsa.calculate_additional_tax()
        assert result['taxable_distributions'] == 0.0
        assert result['additional_tax_penalty'] == 0.0


class TestTestingPeriod:
    """Tests for testing period failure (last-month rule)."""

    def test_testing_period_failure(self):
        """Testing period failure adds income and penalty."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            failed_testing_period=True,
            testing_period_income=3000.0,
        )
        result = hsa.calculate_additional_tax()
        assert result['testing_period_income'] == 3000.0
        assert result['testing_period_penalty'] == 600.0  # 20%
        assert result['total_additional_tax'] == 600.0

    def test_no_testing_period_failure(self):
        """No penalty when testing period is met."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            failed_testing_period=False,
        )
        result = hsa.calculate_additional_tax()
        assert result['testing_period_income'] == 0.0
        assert result['testing_period_penalty'] == 0.0


class TestForm8889Summary:
    """Tests for complete Form 8889 summary generation."""

    def test_full_summary(self):
        """Complete Form 8889 summary."""
        hsa = Form8889(
            coverage_type=HSACoverageType.FAMILY,
            taxpayer_contributions=6000.0,
            employer_contributions=2000.0,
            total_distributions=3000.0,
            qualified_medical_expenses=2500.0,
            is_age_55_or_older=True,
        )
        summary = hsa.generate_form_8889_summary()

        # Part I
        assert summary['part_i']['line_2_taxpayer_contributions'] == 6000.0
        assert summary['part_i']['line_9_employer_contributions'] == 2000.0
        assert summary['part_i']['line_3_contribution_limit'] == 9550.0

        # Part II
        assert summary['part_ii']['line_14a_total_distributions'] == 3000.0
        assert summary['part_ii']['line_15_qualified_expenses'] == 2500.0
        assert summary['part_ii']['line_16_taxable_distributions'] == 500.0

        # Summary
        assert summary['summary']['is_eligible'] is True


class TestHSAInfo:
    """Tests for simplified HSAInfo model."""

    def test_convert_to_form_8889(self):
        """HSAInfo converts to Form8889."""
        hsa_info = HSAInfo(
            coverage_type=HSACoverageType.FAMILY,
            taxpayer_contributions=5000.0,
            employer_contributions=1000.0,
            distributions=2000.0,
            qualified_expenses=2000.0,
            is_age_55_or_older=True,
            months_covered=12,
        )
        form = hsa_info.to_form_8889()

        assert form.coverage_type == HSACoverageType.FAMILY
        assert form.get_total_taxpayer_contributions() == 5000.0
        assert form.get_total_employer_contributions() == 1000.0
        assert form.is_age_55_or_older is True


class TestIncomeIntegration:
    """Tests for integration with Income model."""

    def test_income_with_hsa_info(self):
        """Income model with HSA info."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=4000.0,
        )
        income = Income(hsa_info=hsa)

        deduction = income.get_hsa_deduction()
        assert deduction == 4000.0

    def test_income_hsa_employer_from_w2(self):
        """Employer HSA from W-2 Box 12 code W."""
        w2 = W2Info(
            employer_name="Test Corp",
            wages=50000.0,
            federal_tax_withheld=5000.0,
            employer_hsa_contribution=1500.0,
        )
        income = Income(w2_forms=[w2])

        assert income.get_employer_hsa_contributions() == 1500.0

    def test_income_hsa_taxable_distributions(self):
        """HSA taxable distributions from Income model."""
        hsa = Form8889(
            total_distributions=3000.0,
            qualified_medical_expenses=1000.0,
        )
        income = Income(hsa_info=hsa)

        assert income.get_hsa_taxable_distributions() == 2000.0

    def test_income_hsa_additional_tax(self):
        """HSA additional tax from Income model."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
        )
        income = Income(hsa_info=hsa)

        assert income.get_hsa_additional_tax() == 1000.0  # 20%

    def test_income_without_hsa(self):
        """Income without HSA returns defaults."""
        income = Income()

        assert income.get_hsa_deduction() == 0.0
        assert income.get_hsa_taxable_distributions() == 0.0
        assert income.get_hsa_additional_tax() == 0.0
        assert income.get_form_8889_summary() is None


class TestEngineIntegration:
    """Tests for integration with tax calculation engine."""

    def test_engine_hsa_deduction(self):
        """Engine includes HSA deduction in adjustments."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=4000.0,
        )

        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[W2Info(
                    employer_name="Test Corp",
                    wages=50000.0,
                    federal_tax_withheld=5000.0,
                )],
                hsa_info=hsa,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        assert breakdown.hsa_deduction == 4000.0
        assert breakdown.hsa_additional_tax == 0.0

    def test_engine_hsa_additional_tax(self):
        """Engine includes HSA additional tax in total tax."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=0.0,
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
        )

        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[W2Info(
                    employer_name="Test Corp",
                    wages=50000.0,
                    federal_tax_withheld=5000.0,
                )],
                hsa_info=hsa,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # 20% penalty on $5000 = $1000
        assert breakdown.hsa_taxable_distributions == 5000.0
        assert breakdown.hsa_additional_tax == 1000.0
        # Additional tax should be included in total_tax_before_credits
        assert breakdown.total_tax_before_credits >= 1000.0

    def test_engine_hsa_age_65_no_penalty(self):
        """Engine: age 65+ no penalty on distributions."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
            is_age_65_or_older=True,
        )

        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[W2Info(
                    employer_name="Test Corp",
                    wages=50000.0,
                    federal_tax_withheld=5000.0,
                )],
                hsa_info=hsa,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)

        # Still taxable, but no penalty
        assert breakdown.hsa_taxable_distributions == 5000.0
        assert breakdown.hsa_additional_tax == 0.0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_contributions(self):
        """Zero contributions still valid."""
        hsa = Form8889(
            coverage_type=HSACoverageType.SELF_ONLY,
            taxpayer_contributions=0.0,
        )
        result = hsa.calculate_deduction()
        assert result['hsa_deduction'] == 0.0
        assert result['is_eligible'] is True

    def test_zero_distributions(self):
        """Zero distributions."""
        hsa = Form8889(
            total_distributions=0.0,
        )
        result = hsa.calculate_additional_tax()
        assert result['taxable_distributions'] == 0.0
        assert result['additional_tax_penalty'] == 0.0

    def test_distributions_exceed_qualified(self):
        """Distributions greater than qualified expenses."""
        hsa = Form8889(
            total_distributions=10000.0,
            qualified_medical_expenses=6000.0,
        )
        assert hsa.get_taxable_distributions() == 4000.0

    def test_qualified_exceeds_distributions(self):
        """Qualified expenses exceed distributions (capped)."""
        hsa = Form8889(
            total_distributions=3000.0,
            qualified_medical_expenses=5000.0,  # More than distributed
        )
        # Taxable cannot be negative
        assert hsa.get_taxable_distributions() == 0.0

    def test_detailed_contributions_list(self):
        """Using detailed contributions list."""
        contributions = [
            HSAContribution(amount=2000.0, is_employer_contribution=False),
            HSAContribution(amount=1500.0, is_employer_contribution=True),
            HSAContribution(amount=500.0, is_rollover=True),
        ]
        hsa = Form8889(contributions=contributions)

        assert hsa.get_total_taxpayer_contributions() == 2000.0
        assert hsa.get_total_employer_contributions() == 1500.0
        assert hsa.get_total_rollovers() == 500.0

    def test_combined_penalties(self):
        """Both distribution penalty and testing period penalty."""
        hsa = Form8889(
            total_distributions=5000.0,
            qualified_medical_expenses=0.0,
            failed_testing_period=True,
            testing_period_income=2000.0,
        )
        result = hsa.calculate_additional_tax()

        assert result['additional_tax_penalty'] == 1000.0  # 20% of 5000
        assert result['testing_period_penalty'] == 400.0  # 20% of 2000
        assert result['total_additional_tax'] == 1400.0
