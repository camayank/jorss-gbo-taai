"""
Tests for Form 8606: Nondeductible IRAs

Tests cover:
- Part I: Nondeductible contributions and Traditional IRA distributions
- Part II: Roth IRA conversions
- Part III: Roth IRA distributions
- Pro-rata rule calculations
- 5-year rules for Roth
- Early withdrawal penalties
- Integration with Income model and tax engine
"""

import pytest
from models.form_8606 import (
    Form8606,
    IRAInfo,
    IRAType,
    DistributionCode,
    IRADistribution,
    RothConversion,
    RothContributionYear,
)
from models.income import Income
from models.tax_return import TaxReturn
from models.taxpayer import FilingStatus, TaxpayerInfo
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import FederalTaxEngine


def create_tax_return(income: Income, ira_info: Form8606 = None) -> TaxReturn:
    """Helper to create TaxReturn with all required fields."""
    if ira_info:
        income = Income(**{**income.model_dump(), 'ira_info': ira_info})
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=FilingStatus.SINGLE,
            primary_ssn="123-45-6789",
        ),
        income=income,
        deductions=Deductions(),
        credits=TaxCredits(),
    )


class TestForm8606PartI:
    """Test Part I: Traditional IRA basis and distributions."""

    def test_total_basis_calculation(self):
        """Test Line 3: Total basis = prior + current nondeductible."""
        form = Form8606(
            nondeductible_contributions_current_year=5000.0,
            total_basis_prior_years=15000.0,
        )
        assert form.calculate_total_basis() == 20000.0

    def test_total_basis_no_prior(self):
        """Test basis with no prior year contributions."""
        form = Form8606(
            nondeductible_contributions_current_year=7000.0,
            total_basis_prior_years=0.0,
        )
        assert form.calculate_total_basis() == 7000.0

    def test_nontaxable_percentage_calculation(self):
        """Test pro-rata percentage calculation."""
        form = Form8606(
            nondeductible_contributions_current_year=0.0,
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=0.0,
            roth_conversion_amount=0.0,
        )
        # Basis 20k / Value 80k = 25%
        assert form.calculate_nontaxable_percentage() == 0.25

    def test_nontaxable_percentage_with_distributions(self):
        """Test pro-rata when distributions included in denominator."""
        form = Form8606(
            nondeductible_contributions_current_year=0.0,
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=70000.0,
            traditional_ira_distributions=10000.0,
            roth_conversion_amount=0.0,
        )
        # Basis 20k / (70k + 10k) = 25%
        assert form.calculate_nontaxable_percentage() == 0.25

    def test_part_i_no_distributions(self):
        """Test Part I when no distributions taken."""
        form = Form8606(
            nondeductible_contributions_current_year=5000.0,
            total_basis_prior_years=15000.0,
            year_end_value_all_traditional_iras=100000.0,
            traditional_ira_distributions=0.0,
        )
        result = form.calculate_part_i()
        assert result['line_1_nondeductible_contributions'] == 5000.0
        assert result['line_2_prior_basis'] == 15000.0
        assert result['line_3_total_basis'] == 20000.0
        assert result['line_7_distributions'] == 0.0
        assert result['line_13_taxable_amount'] == 0.0
        assert result['line_14_remaining_basis'] == 20000.0

    def test_part_i_with_distribution(self):
        """Test Part I with Traditional IRA distribution."""
        form = Form8606(
            nondeductible_contributions_current_year=0.0,
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=70000.0,
            traditional_ira_distributions=10000.0,
        )
        result = form.calculate_part_i()
        # Total value = 70k + 10k = 80k
        # Nontaxable % = 20k / 80k = 25%
        # Nontaxable amount = 10k * 25% = 2,500
        # Taxable = 10k - 2.5k = 7,500
        # Remaining basis = 20k - 2.5k = 17,500
        assert result['line_9_total_value'] == 80000.0
        assert result['line_10_nontaxable_percentage'] == 25.0
        assert result['line_11_nontaxable_amount'] == 2500.0
        assert result['line_13_taxable_amount'] == 7500.0
        assert result['line_14_remaining_basis'] == 17500.0

    def test_part_i_no_basis_fully_taxable(self):
        """Test distribution is fully taxable when no basis."""
        form = Form8606(
            nondeductible_contributions_current_year=0.0,
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=90000.0,
            traditional_ira_distributions=10000.0,
        )
        result = form.calculate_part_i()
        assert result['line_10_nontaxable_percentage'] == 0.0
        assert result['line_11_nontaxable_amount'] == 0.0
        assert result['line_13_taxable_amount'] == 10000.0

    def test_part_i_100_percent_basis(self):
        """Test when all IRA is basis (fully nontaxable)."""
        form = Form8606(
            nondeductible_contributions_current_year=0.0,
            total_basis_prior_years=50000.0,
            year_end_value_all_traditional_iras=40000.0,
            traditional_ira_distributions=10000.0,
        )
        result = form.calculate_part_i()
        # Basis 50k > Value 50k, but capped at 100%
        assert result['line_10_nontaxable_percentage'] == 100.0
        assert result['line_11_nontaxable_amount'] == 10000.0
        assert result['line_13_taxable_amount'] == 0.0


class TestForm8606PartII:
    """Test Part II: Roth IRA conversions."""

    def test_conversion_no_basis(self):
        """Test Roth conversion when no Traditional IRA basis."""
        form = Form8606(
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=90000.0,
            roth_conversion_amount=10000.0,
        )
        result = form.calculate_part_ii_conversion()
        assert result['conversion_amount'] == 10000.0
        assert result['taxable_conversion'] == 10000.0
        assert result['nontaxable_conversion'] == 0.0

    def test_conversion_with_basis(self):
        """Test Roth conversion with Traditional IRA basis."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            roth_conversion_amount=10000.0,
        )
        result = form.calculate_part_ii_conversion()
        # Basis 20k / (80k + 10k) = 22.22%
        # Nontaxable = 10k * 22.22% = 2,222
        # Taxable = 10k - 2,222 = 7,778
        assert result['conversion_amount'] == 10000.0
        assert abs(result['taxable_conversion'] - 7777.78) < 0.01
        assert abs(result['nontaxable_conversion'] - 2222.22) < 0.01

    def test_conversion_zero_amount(self):
        """Test when no conversion done."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            roth_conversion_amount=0.0,
        )
        result = form.calculate_part_ii_conversion()
        assert result['conversion_amount'] == 0.0
        assert result['taxable_conversion'] == 0.0

    def test_roth_conversion_object(self):
        """Test RothConversion model."""
        conversion = RothConversion(
            conversion_date="2025-06-15",
            conversion_amount=50000.0,
            taxable_amount=40000.0,
            nontaxable_amount=10000.0,
        )
        assert conversion.get_conversion_year() == 2025


class TestForm8606PartIII:
    """Test Part III: Roth IRA distributions."""

    def test_qualified_roth_distribution(self):
        """Test qualified Roth distribution (5-year + age 59½)."""
        form = Form8606(
            first_roth_contribution_year=2018,
            total_roth_contributions=50000.0,
            roth_ira_distributions=20000.0,
            taxpayer_age=65,
        )
        result = form.calculate_part_iii_roth(current_year=2025)
        assert result['is_qualified'] is True
        assert result['taxable_amount'] == 0.0
        assert result['penalty_amount'] == 0.0
        assert result['from_contributions'] == 20000.0

    def test_nonqualified_roth_contribution_only(self):
        """Test non-qualified Roth distribution from contributions only."""
        form = Form8606(
            first_roth_contribution_year=2023,  # 5-year not met
            total_roth_contributions=50000.0,
            roth_ira_distributions=20000.0,
            taxpayer_age=45,
        )
        result = form.calculate_part_iii_roth(current_year=2025)
        # 5-year not met but only from contributions
        assert result['is_qualified'] is False
        assert result['from_contributions'] == 20000.0
        assert result['from_earnings'] == 0.0
        assert result['taxable_amount'] == 0.0  # Contributions are always tax-free
        assert result['penalty_amount'] == 0.0  # No penalty on contributions

    def test_nonqualified_roth_includes_earnings(self):
        """Test non-qualified Roth distribution that includes earnings."""
        form = Form8606(
            first_roth_contribution_year=2020,
            total_roth_contributions=30000.0,
            total_roth_conversions=0.0,
            roth_ira_distributions=40000.0,
            taxpayer_age=45,  # Under 59½
        )
        result = form.calculate_part_iii_roth(current_year=2025)
        # 40k distribution, 30k contributions, 10k earnings
        assert result['is_qualified'] is False
        assert result['from_contributions'] == 30000.0
        assert result['from_earnings'] == 10000.0
        assert result['taxable_amount'] == 10000.0  # Only earnings taxable
        assert result['penalty_amount'] == 1000.0  # 10% on earnings

    def test_nonqualified_roth_with_conversions(self):
        """Test non-qualified Roth distribution with recent conversions."""
        form = Form8606(
            first_roth_contribution_year=2015,
            total_roth_contributions=20000.0,
            total_roth_conversions=30000.0,
            roth_ira_distributions=40000.0,
            taxpayer_age=50,  # Under 59½
            roth_conversions=[
                RothConversion(
                    conversion_date="2023-01-15",
                    conversion_amount=30000.0,
                )
            ],
        )
        result = form.calculate_part_iii_roth(current_year=2025)
        # 40k distribution: 20k from contributions, 20k from conversions
        assert result['from_contributions'] == 20000.0
        assert result['from_conversions'] == 20000.0
        assert result['from_earnings'] == 0.0
        # 10% penalty on conversion (within 5 years, under 59½)
        assert result['penalty_amount'] == 2000.0  # 10% of 20k

    def test_roth_5_year_rule_met(self):
        """Test Roth with 5-year rule met but under 59½."""
        form = Form8606(
            first_roth_contribution_year=2018,
            total_roth_contributions=50000.0,
            roth_ira_distributions=20000.0,
            taxpayer_age=45,  # Under 59½
        )
        result = form.calculate_part_iii_roth(current_year=2025)
        # 5-year met but not age 59½, still non-qualified
        assert result['is_qualified'] is False

    def test_roth_disability_exception(self):
        """Test Roth distribution with disability exception."""
        form = Form8606(
            first_roth_contribution_year=2020,
            total_roth_contributions=30000.0,
            roth_ira_distributions=40000.0,
            taxpayer_age=45,
            is_disabled=True,
        )
        result = form.calculate_part_iii_roth(current_year=2025)
        # 5-year met + disability = qualified
        assert result['is_qualified'] is True
        assert result['taxable_amount'] == 0.0
        assert result['penalty_amount'] == 0.0


class TestEarlyWithdrawalPenalty:
    """Test 10% early withdrawal penalty calculations."""

    def test_traditional_ira_early_withdrawal(self):
        """Test 10% penalty on Traditional IRA early withdrawal."""
        form = Form8606(
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=90000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=45,  # Under 59½
        )
        penalty = form.calculate_early_withdrawal_penalty()
        # 10% on taxable portion (all 10k is taxable)
        assert penalty == 1000.0

    def test_traditional_ira_no_penalty_over_59(self):
        """Test no penalty when over 59½."""
        form = Form8606(
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=90000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=60,  # Over 59½
        )
        penalty = form.calculate_early_withdrawal_penalty()
        assert penalty == 0.0

    def test_traditional_ira_penalty_with_basis(self):
        """Test penalty only on taxable portion."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=45,
        )
        penalty = form.calculate_early_withdrawal_penalty()
        # Total value = 80k + 10k = 90k
        # Nontaxable % = 20k / 90k = 22.22%
        # Taxable = 10k * 77.78% = 7,778
        # Penalty = 7,778 * 10% = 777.8
        assert abs(penalty - 777.78) < 0.01

    def test_disability_exception(self):
        """Test no penalty with disability exception."""
        form = Form8606(
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=90000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=45,
            is_disabled=True,
        )
        penalty = form.calculate_early_withdrawal_penalty()
        assert penalty == 0.0

    def test_death_exception(self):
        """Test no penalty for beneficiary distribution."""
        form = Form8606(
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=90000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=45,
            is_beneficiary_distribution=True,
        )
        penalty = form.calculate_early_withdrawal_penalty()
        assert penalty == 0.0


class TestIRAInfo:
    """Test IRAInfo wrapper model."""

    def test_nondeductible_contribution_calculation(self):
        """Test nondeductible contribution calculation."""
        ira_info = IRAInfo(
            traditional_ira_contribution=7000.0,
            deductible_traditional_contribution=3000.0,
        )
        assert ira_info.get_nondeductible_contribution() == 4000.0

    def test_fully_deductible_contribution(self):
        """Test when contribution is fully deductible."""
        ira_info = IRAInfo(
            traditional_ira_contribution=7000.0,
            deductible_traditional_contribution=7000.0,
        )
        assert ira_info.get_nondeductible_contribution() == 0.0

    def test_taxable_distribution_with_form_8606(self):
        """Test taxable distribution from IRAInfo."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
        )
        ira_info = IRAInfo(form_8606=form)
        taxable = ira_info.get_taxable_distribution(current_year=2025)
        # Total value = 80k + 10k = 90k
        # Nontaxable % = 20k / 90k = 22.22%
        # Taxable = 10k * 77.78% = 7,778
        assert abs(taxable - 7777.78) < 0.01

    def test_no_form_8606_returns_zero(self):
        """Test methods return 0 when no Form 8606."""
        ira_info = IRAInfo()
        assert ira_info.get_taxable_distribution() == 0.0
        assert ira_info.get_early_withdrawal_penalty() == 0.0
        assert ira_info.get_roth_conversion_taxable() == 0.0


class TestIncomeIntegration:
    """Test Form 8606 integration with Income model."""

    def test_income_with_ira_info(self):
        """Test Income model with Form 8606."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=45,
        )
        income = Income(
            wages=50000.0,
            ira_info=form,
        )
        # Total value = 80k + 10k = 90k
        # Nontaxable % = 20k / 90k = 22.22%
        # Taxable = 10k * 77.78% = 7,778
        # Penalty = 7,778 * 10% = 777.8
        assert abs(income.get_ira_taxable_distribution() - 7777.78) < 0.01
        assert abs(income.get_ira_early_withdrawal_penalty() - 777.78) < 0.01

    def test_income_no_ira_info(self):
        """Test Income model without Form 8606."""
        income = Income(wages=50000.0)
        assert income.get_ira_taxable_distribution() == 0.0
        assert income.get_ira_early_withdrawal_penalty() == 0.0

    def test_get_total_ira_distributions(self):
        """Test total IRA distributions method."""
        form = Form8606(
            traditional_ira_distributions=10000.0,
            roth_ira_distributions=5000.0,
        )
        income = Income(ira_info=form)
        assert income.get_total_ira_distributions() == 15000.0

    def test_get_nontaxable_distribution(self):
        """Test nontaxable portion of distribution."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
        )
        income = Income(ira_info=form)
        # Total value = 80k + 10k = 90k
        # Nontaxable % = 20k / 90k = 22.22%
        # Nontaxable = 10k * 22.22% = 2,222
        assert abs(income.get_nontaxable_ira_distribution() - 2222.22) < 0.01

    def test_get_basis_carryforward(self):
        """Test basis carryforward for next year."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
        )
        income = Income(ira_info=form)
        # Total value = 80k + 10k = 90k
        # Nontaxable % = 20k / 90k = 22.22%
        # Remaining basis = 20k - (10k * 22.22%) = 17,778
        assert abs(income.get_ira_basis_carryforward() - 17777.78) < 0.01

    def test_form_8606_summary(self):
        """Test full Form 8606 summary generation."""
        form = Form8606(
            nondeductible_contributions_current_year=5000.0,
            total_basis_prior_years=15000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
            roth_conversion_amount=5000.0,
            taxpayer_age=45,
        )
        income = Income(ira_info=form)
        summary = income.get_form_8606_summary()
        assert summary is not None
        assert 'part_i_traditional_ira' in summary
        assert 'part_ii_roth_conversion' in summary
        assert 'part_iii_roth_distribution' in summary
        assert 'total_early_withdrawal_penalty' in summary


class TestEngineIntegration:
    """Test Form 8606 integration with tax engine."""

    def test_engine_ira_distribution(self):
        """Test engine processes IRA distributions."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=10000.0,
            taxpayer_age=65,  # No penalty
        )
        income = Income(wages=50000.0, ira_info=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        # Total value = 80k + 10k = 90k
        # Nontaxable % = 20k / 90k = 22.22%
        # Taxable = 10k * 77.78% = 7,778
        # Nontaxable = 10k * 22.22% = 2,222
        assert abs(result.ira_taxable_distributions - 7777.78) < 0.01
        assert abs(result.ira_nontaxable_distributions - 2222.22) < 0.01
        assert result.ira_early_withdrawal_penalty == 0.0
        assert abs(result.ira_basis_carryforward - 17777.78) < 0.01

    def test_engine_ira_early_withdrawal_penalty(self):
        """Test engine includes early withdrawal penalty."""
        form = Form8606(
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=100000.0,
            traditional_ira_distributions=20000.0,
            taxpayer_age=45,  # Under 59½
        )
        income = Income(wages=50000.0, ira_info=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        assert result.ira_taxable_distributions == 20000.0
        assert result.ira_early_withdrawal_penalty == 2000.0  # 10% of 20k
        # Penalty is included in total tax
        assert result.total_tax_before_credits >= 2000.0

    def test_engine_roth_conversion(self):
        """Test engine processes Roth conversion."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            roth_conversion_amount=10000.0,
            taxpayer_age=65,
        )
        income = Income(wages=50000.0, ira_info=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        # Taxable conversion = 10k * (1 - 20k/90k) = ~7,778
        assert abs(result.roth_conversion_taxable - 7777.78) < 0.01

    def test_engine_no_ira_info(self):
        """Test engine with no IRA info."""
        income = Income(wages=50000.0)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        assert result.ira_taxable_distributions == 0.0
        assert result.ira_early_withdrawal_penalty == 0.0


class TestDistributionCodes:
    """Test IRA distribution codes and handling."""

    def test_distribution_code_early(self):
        """Test early distribution code."""
        dist = IRADistribution(
            gross_distribution=10000.0,
            distribution_code=DistributionCode.EARLY_NO_EXCEPTION,
        )
        assert dist.is_early_distribution() is True

    def test_distribution_code_normal(self):
        """Test normal distribution code."""
        dist = IRADistribution(
            gross_distribution=10000.0,
            distribution_code=DistributionCode.NORMAL,
        )
        assert dist.is_early_distribution() is False

    def test_distribution_code_disability(self):
        """Test disability distribution code."""
        dist = IRADistribution(
            gross_distribution=10000.0,
            distribution_code=DistributionCode.DISABILITY,
        )
        assert dist.is_early_distribution() is False

    def test_qualified_roth_distribution_check(self):
        """Test qualified Roth distribution determination."""
        dist = IRADistribution(
            ira_type=IRAType.ROTH,
            gross_distribution=10000.0,
            first_roth_contribution_year=2018,
        )
        # Age 60, 2025, first contribution 2018 -> qualified
        assert dist.is_qualified_roth_distribution(taxpayer_age=60, current_year=2025) is True

    def test_nonqualified_roth_5_year_not_met(self):
        """Test non-qualified when 5-year not met."""
        dist = IRADistribution(
            ira_type=IRAType.ROTH,
            gross_distribution=10000.0,
            first_roth_contribution_year=2023,
        )
        # Age 60, 2025, first contribution 2023 -> not qualified (5-year not met)
        assert dist.is_qualified_roth_distribution(taxpayer_age=60, current_year=2025) is False


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_backdoor_roth_conversion(self):
        """Test backdoor Roth: nondeductible contribution + conversion."""
        form = Form8606(
            nondeductible_contributions_current_year=7000.0,
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=0.0,  # All converted
            roth_conversion_amount=7000.0,
        )
        result = form.calculate_part_ii_conversion()
        # 100% basis, so 0 taxable
        assert result['taxable_conversion'] == 0.0
        assert result['nontaxable_conversion'] == 7000.0

    def test_backdoor_roth_with_existing_ira(self):
        """Test backdoor Roth when pre-existing Traditional IRA exists."""
        form = Form8606(
            nondeductible_contributions_current_year=7000.0,
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=93000.0,  # Pre-tax money
            roth_conversion_amount=7000.0,
        )
        result = form.calculate_part_ii_conversion()
        # Basis 7k / Total 100k = 7%
        # Taxable = 7k * 93% = 6,510
        assert abs(result['taxable_conversion'] - 6510.0) < 1.0

    def test_multiple_distributions_same_year(self):
        """Test multiple IRA distributions in same year."""
        form = Form8606(
            total_basis_prior_years=30000.0,
            year_end_value_all_traditional_iras=60000.0,
            traditional_ira_distributions=15000.0,  # Combined total
            taxpayer_age=65,
        )
        result = form.calculate_part_i()
        # Basis 30k / (60k + 15k) = 40%
        # Nontaxable = 15k * 40% = 6,000
        assert result['line_11_nontaxable_amount'] == 6000.0
        assert result['line_13_taxable_amount'] == 9000.0

    def test_roth_ordering_rules_comprehensive(self):
        """Test complete Roth ordering: contributions, conversions, earnings."""
        form = Form8606(
            first_roth_contribution_year=2015,
            total_roth_contributions=25000.0,
            total_roth_conversions=50000.0,
            roth_ira_distributions=90000.0,  # More than contributions + conversions
            taxpayer_age=50,
            roth_conversions=[
                RothConversion(conversion_date="2022-01-15", conversion_amount=50000.0)
            ],
        )
        result = form.calculate_part_iii_roth(current_year=2025)

        # Ordering: 25k contributions, 50k conversions, 15k earnings
        assert result['from_contributions'] == 25000.0
        assert result['from_conversions'] == 50000.0
        assert result['from_earnings'] == 15000.0
        # Only earnings are taxable
        assert result['taxable_amount'] == 15000.0
        # Penalty: 10% on conversions (within 5 years) + 10% on earnings
        assert result['penalty_amount'] == 6500.0  # 5000 + 1500

    def test_first_year_filer(self):
        """Test first year with nondeductible contribution."""
        form = Form8606(
            nondeductible_contributions_current_year=7000.0,
            total_basis_prior_years=0.0,
            year_end_value_all_traditional_iras=7500.0,  # Includes some gains
            traditional_ira_distributions=0.0,
        )
        result = form.calculate_part_i()
        assert result['line_3_total_basis'] == 7000.0
        assert result['line_14_remaining_basis'] == 7000.0

    def test_complete_ira_distribution(self):
        """Test distributing entire IRA balance."""
        form = Form8606(
            total_basis_prior_years=25000.0,
            year_end_value_all_traditional_iras=0.0,  # All distributed
            traditional_ira_distributions=100000.0,
            taxpayer_age=65,
        )
        result = form.calculate_part_i()
        # Basis 25k / 100k = 25%
        assert result['line_11_nontaxable_amount'] == 25000.0
        assert result['line_13_taxable_amount'] == 75000.0
        assert result['line_14_remaining_basis'] == 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_basis(self):
        """Test with zero basis."""
        form = Form8606(
            total_basis_prior_years=0.0,
            nondeductible_contributions_current_year=0.0,
        )
        assert form.calculate_total_basis() == 0.0
        assert form.calculate_nontaxable_percentage() == 0.0

    def test_zero_distribution(self):
        """Test with zero distributions."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            traditional_ira_distributions=0.0,
        )
        taxable = form.calculate_taxable_traditional_distribution()
        assert taxable == 0.0

    def test_zero_ira_value(self):
        """Test with zero IRA value (shouldn't happen, but handle gracefully)."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=0.0,
            traditional_ira_distributions=0.0,
        )
        result = form.calculate_part_i()
        assert result['line_14_remaining_basis'] == 20000.0

    def test_very_small_distribution(self):
        """Test with small distribution amounts."""
        form = Form8606(
            total_basis_prior_years=20000.0,
            year_end_value_all_traditional_iras=80000.0,
            traditional_ira_distributions=100.0,
        )
        result = form.calculate_part_i()
        # Total value = 80k + 100 = 80,100
        # Nontaxable % = 20k / 80,100 = 24.97%
        # Nontaxable = 100 * 24.97% = 24.97
        assert abs(result['line_11_nontaxable_amount'] - 24.97) < 0.01
        assert abs(result['line_13_taxable_amount'] - 75.03) < 0.01

    def test_large_distribution(self):
        """Test with large distribution amounts."""
        form = Form8606(
            total_basis_prior_years=500000.0,
            year_end_value_all_traditional_iras=1500000.0,
            traditional_ira_distributions=200000.0,
        )
        result = form.calculate_part_i()
        # Basis 500k / 1.7M = ~29.4%
        assert result['line_13_taxable_amount'] > 0

    def test_roth_contribution_year_tracking(self):
        """Test Roth contribution year tracking."""
        contrib = RothContributionYear(
            tax_year=2020,
            contribution_amount=6000.0,
            conversion_amount=10000.0,
        )
        # In 2025, 5 years have passed
        assert contrib.is_contribution_qualified(current_year=2025) is True
        assert contrib.is_contribution_qualified(current_year=2024) is False
