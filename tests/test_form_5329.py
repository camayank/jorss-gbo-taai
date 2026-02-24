"""
Tests for Form 5329: Additional Taxes on Qualified Plans and Other Tax-Favored Accounts

Tests cover:
- Part I: Early distribution penalties and exception codes
- Part II: Traditional IRA excess contributions
- Part III: Roth IRA excess contributions
- Part IV-VII: Other excess contributions (Coverdell, Archer MSA, HSA, ABLE)
- Part VIII: RMD failure penalties
- Part IX: Section 529 excess contributions
- Integration with Income model and tax engine
"""

import pytest
from models.form_5329 import (
    Form5329,
    EarlyDistribution,
    EarlyDistributionExceptionCode,
    ExcessContribution,
    RMDFailure,
    calculate_roth_contribution_limit,
    IRA_CONTRIBUTION_LIMITS_2025,
)
from models.income import Income
from models.tax_return import TaxReturn
from models.taxpayer import FilingStatus, TaxpayerInfo
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import FederalTaxEngine


def create_tax_return(income: Income) -> TaxReturn:
    """Helper to create TaxReturn with all required fields."""
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


class TestEarlyDistributionPenalty:
    """Test Part I: Early Distribution Penalty."""

    def test_no_early_distribution(self):
        """Test when no early distributions."""
        form = Form5329()
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0

    def test_early_distribution_no_exception(self):
        """Test 10% penalty on early distribution without exception."""
        form = Form5329()
        form.add_early_distribution(10000.0)
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_1_total_distributions'] == 10000.0
        assert result['line_2_exceptions'] == 0.0
        assert result['line_3_subject_to_penalty'] == 10000.0
        assert result['line_4_penalty'] == 1000.0  # 10%

    def test_early_distribution_disability_exception(self):
        """Test disability exception (code 03)."""
        form = Form5329()
        form.add_early_distribution(
            10000.0,
            exception_code=EarlyDistributionExceptionCode.DISABILITY,
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_2_exceptions'] == 10000.0
        assert result['line_4_penalty'] == 0.0

    def test_early_distribution_death_exception(self):
        """Test death/beneficiary exception (code 04)."""
        form = Form5329()
        form.add_early_distribution(
            25000.0,
            exception_code=EarlyDistributionExceptionCode.DEATH,
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0

    def test_early_distribution_sepp_exception(self):
        """Test 72(t) substantially equal periodic payments exception."""
        form = Form5329()
        form.add_early_distribution(
            12000.0,
            exception_code=EarlyDistributionExceptionCode.SEPP,
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0

    def test_early_distribution_first_home_exception(self):
        """Test first-time homebuyer exception ($10,000 limit)."""
        form = Form5329()
        form.add_early_distribution(
            15000.0,
            exception_code=EarlyDistributionExceptionCode.FIRST_HOME,
            exception_amount=10000.0,  # $10k limit
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_2_exceptions'] == 10000.0
        assert result['line_3_subject_to_penalty'] == 5000.0
        assert result['line_4_penalty'] == 500.0  # 10% of 5k

    def test_early_distribution_higher_education(self):
        """Test higher education expense exception."""
        form = Form5329()
        form.add_early_distribution(
            8000.0,
            exception_code=EarlyDistributionExceptionCode.HIGHER_EDUCATION,
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0

    def test_early_distribution_medical_expenses(self):
        """Test medical expenses exception."""
        form = Form5329()
        form.add_early_distribution(
            5000.0,
            exception_code=EarlyDistributionExceptionCode.MEDICAL_EXPENSES,
            exception_amount=3000.0,  # Only amount exceeding 7.5% AGI
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_3_subject_to_penalty'] == 2000.0
        assert result['line_4_penalty'] == 200.0

    def test_early_distribution_birth_adoption(self):
        """Test qualified birth or adoption distribution (SECURE Act)."""
        form = Form5329()
        form.add_early_distribution(
            5000.0,
            exception_code=EarlyDistributionExceptionCode.BIRTH_ADOPTION,
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0

    def test_multiple_early_distributions(self):
        """Test multiple distributions with different exceptions."""
        form = Form5329()
        # Distribution 1: No exception
        form.add_early_distribution(10000.0)
        # Distribution 2: Disability exception
        form.add_early_distribution(
            5000.0,
            exception_code=EarlyDistributionExceptionCode.DISABILITY,
        )
        # Distribution 3: Partial exception
        form.add_early_distribution(
            8000.0,
            exception_code=EarlyDistributionExceptionCode.FIRST_HOME,
            exception_amount=8000.0,
        )

        result = form.calculate_part_i_early_distribution_penalty()
        # Total distributions: 10k + 5k + 8k = 23k
        # Exceptions: 5k + 8k = 13k
        # Subject to penalty: 10k
        assert result['line_1_total_distributions'] == 23000.0
        assert result['line_2_exceptions'] == 13000.0
        assert result['line_3_subject_to_penalty'] == 10000.0
        assert result['line_4_penalty'] == 1000.0

    def test_taxable_amount_differs_from_gross(self):
        """Test when taxable amount differs from gross distribution."""
        dist = EarlyDistribution(
            distribution_amount=10000.0,
            taxable_amount=7500.0,  # Only 75% taxable (has basis)
            exception_code=EarlyDistributionExceptionCode.NO_EXCEPTION,
        )
        assert dist.get_taxable_amount() == 7500.0
        assert dist.get_amount_subject_to_penalty() == 7500.0


class TestTraditionalIRAExcess:
    """Test Part II: Traditional IRA Excess Contributions."""

    def test_no_excess_contribution(self):
        """Test when contribution is within limit."""
        excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=6000.0,
            contribution_limit=7000.0,
        )
        assert excess.calculate_current_year_excess() == 0.0
        assert excess.calculate_excise_tax() == 0.0

    def test_excess_contribution_current_year(self):
        """Test excess contribution in current year."""
        excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=9000.0,
            contribution_limit=7000.0,
        )
        assert excess.calculate_current_year_excess() == 2000.0
        assert excess.calculate_excise_tax() == 120.0  # 6% of 2k

    def test_excess_with_prior_year_carryover(self):
        """Test excess including prior year carryover."""
        excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=7000.0,
            contribution_limit=7000.0,
            prior_year_excess=1000.0,
        )
        # No current year excess, but prior year excess remains
        assert excess.calculate_current_year_excess() == 0.0
        assert excess.calculate_total_excess() == 1000.0
        assert excess.calculate_excise_tax() == 60.0

    def test_excess_corrected_by_withdrawal(self):
        """Test excess corrected by timely withdrawal."""
        excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=9000.0,
            contribution_limit=7000.0,
            excess_withdrawn=2000.0,
        )
        assert excess.calculate_current_year_excess() == 2000.0
        assert excess.calculate_total_excess() == 0.0  # Withdrawn
        assert excess.calculate_excise_tax() == 0.0

    def test_excess_corrected_by_recharacterization(self):
        """Test excess corrected by recharacterization to Roth."""
        excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=9000.0,
            contribution_limit=7000.0,
            recharacterized_amount=2000.0,
        )
        assert excess.calculate_total_excess() == 0.0
        assert excess.calculate_excise_tax() == 0.0

    def test_form_5329_part_ii(self):
        """Test Form 5329 Part II calculation."""
        form = Form5329()
        form.add_traditional_ira_excess(
            contributions=9000.0,
            limit=7000.0,
        )
        result = form.calculate_part_ii_traditional_ira_excess()
        assert result['excess_amount'] == 2000.0
        assert result['excise_tax'] == 120.0


class TestRothIRAExcess:
    """Test Part III: Roth IRA Excess Contributions."""

    def test_roth_excess_from_phaseout(self):
        """Test Roth excess due to MAGI phaseout."""
        # High income single filer - Roth limit reduced
        allowed = calculate_roth_contribution_limit(
            magi=160000.0,
            filing_status='single',
        )
        # At $160k MAGI (between $150k-$165k), contribution is reduced
        assert allowed < 7000.0
        assert allowed >= 0.0

    def test_roth_excess_over_phaseout(self):
        """Test Roth excess when over income limit."""
        allowed = calculate_roth_contribution_limit(
            magi=170000.0,
            filing_status='single',
        )
        assert allowed == 0.0

    def test_form_5329_part_iii(self):
        """Test Form 5329 Part III calculation."""
        form = Form5329()
        form.add_roth_ira_excess(
            contributions=7000.0,
            limit=0.0,  # Over income limit, no Roth allowed
        )
        result = form.calculate_part_iii_roth_ira_excess()
        assert result['excess_amount'] == 7000.0
        assert result['excise_tax'] == 420.0  # 6% of 7k


class TestOtherExcessContributions:
    """Test Parts IV-VII: Other Excess Contributions."""

    def test_coverdell_esa_excess(self):
        """Test Coverdell ESA excess (Part IV)."""
        form = Form5329()
        form.coverdell_esa_excess = ExcessContribution(
            account_type="coverdell_esa",
            current_year_contributions=3000.0,
            contribution_limit=2000.0,
        )
        result = form.calculate_part_iv_coverdell_excess()
        assert result['excess_amount'] == 1000.0
        assert result['excise_tax'] == 60.0

    def test_hsa_excess(self):
        """Test HSA excess (Part VI)."""
        form = Form5329()
        form.hsa_excess = ExcessContribution(
            account_type="hsa",
            current_year_contributions=5000.0,
            contribution_limit=4300.0,  # 2025 self-only limit
        )
        result = form.calculate_part_vi_hsa_excess()
        assert result['excess_amount'] == 700.0
        assert result['excise_tax'] == 42.0

    def test_able_excess(self):
        """Test ABLE account excess (Part VII)."""
        form = Form5329()
        form.able_excess = ExcessContribution(
            account_type="able",
            current_year_contributions=20000.0,
            contribution_limit=18000.0,
        )
        result = form.calculate_part_vii_able_excess()
        assert result['excess_amount'] == 2000.0
        assert result['excise_tax'] == 120.0


class TestRMDPenalty:
    """Test Part VIII: RMD Failure Penalty."""

    def test_no_rmd_failure(self):
        """Test when RMD is fully taken."""
        failure = RMDFailure(
            required_minimum_distribution=10000.0,
            actual_distribution=10000.0,
            rmd_year=2024,
        )
        assert failure.calculate_shortfall() == 0.0
        assert failure.calculate_excise_tax() == 0.0

    def test_rmd_shortfall_standard_penalty(self):
        """Test 25% penalty on RMD shortfall."""
        failure = RMDFailure(
            required_minimum_distribution=10000.0,
            actual_distribution=6000.0,
            rmd_year=2024,
        )
        assert failure.calculate_shortfall() == 4000.0
        assert failure.calculate_excise_tax() == 1000.0  # 25% of 4k

    def test_rmd_shortfall_corrected_timely(self):
        """Test 10% reduced penalty when corrected timely."""
        failure = RMDFailure(
            required_minimum_distribution=10000.0,
            actual_distribution=0.0,
            rmd_year=2024,
            is_corrected_timely=True,
        )
        assert failure.calculate_shortfall() == 10000.0
        assert failure.calculate_excise_tax() == 1000.0  # 10% of 10k

    def test_rmd_waiver_requested(self):
        """Test reasonable cause waiver request."""
        failure = RMDFailure(
            required_minimum_distribution=10000.0,
            actual_distribution=0.0,
            rmd_year=2024,
            reasonable_cause_waiver_requested=True,
        )
        # Waiver requested - taxpayer reports $0 and attaches explanation
        assert failure.calculate_excise_tax() == 0.0

    def test_form_5329_part_viii(self):
        """Test Form 5329 Part VIII calculation."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=20000.0,
            actual_amount=15000.0,
            rmd_year=2024,
        )
        result = form.calculate_part_viii_rmd_penalty()
        assert result['total_shortfall'] == 5000.0
        assert result['total_penalty'] == 1250.0  # 25% of 5k

    def test_multiple_rmd_failures(self):
        """Test multiple RMD failures."""
        form = Form5329()
        # Traditional IRA failure
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=8000.0,
            rmd_year=2024,
            account_type="traditional_ira",
        )
        # 401k failure (corrected timely)
        form.add_rmd_failure(
            required_amount=5000.0,
            actual_amount=0.0,
            rmd_year=2024,
            account_type="401k",
            is_corrected=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # IRA: 2k shortfall * 25% = 500
        # 401k: 5k shortfall * 10% = 500
        assert result['total_shortfall'] == 7000.0
        assert result['total_penalty'] == 1000.0


class TestSection529Excess:
    """Test Part IX: Section 529 Excess Contributions."""

    def test_529_no_federal_limit(self):
        """Test 529 contribution (no federal contribution limit)."""
        # 529 plans don't have a federal contribution limit,
        # but gift tax rules apply ($18k/year exclusion for 2024)
        form = Form5329()
        form.section_529_excess = ExcessContribution(
            account_type="529",
            current_year_contributions=20000.0,
            contribution_limit=20000.0,  # State-specific limits
        )
        result = form.calculate_part_ix_529_excess()
        assert result['excess_amount'] == 0.0


class TestTotalAdditionalTax:
    """Test total additional tax calculation."""

    def test_combined_penalties(self):
        """Test combined penalties from multiple parts."""
        form = Form5329(taxpayer_age=45)

        # Part I: Early distribution
        form.add_early_distribution(10000.0)

        # Part II: Traditional IRA excess
        form.add_traditional_ira_excess(
            contributions=9000.0,
            limit=7000.0,
        )

        # Part VIII: RMD failure
        form.add_rmd_failure(
            required_amount=5000.0,
            actual_amount=0.0,
            rmd_year=2024,
        )

        total = form.calculate_total_additional_tax()
        # Early dist: 10k * 10% = 1000
        # Traditional excess: 2k * 6% = 120
        # RMD: 5k * 25% = 1250
        assert total == 2370.0

    def test_summary_generation(self):
        """Test complete Form 5329 summary."""
        form = Form5329(taxpayer_age=50, tax_year=2025)
        form.add_early_distribution(
            5000.0,
            exception_code=EarlyDistributionExceptionCode.DISABILITY,
        )
        form.add_roth_ira_excess(
            contributions=8000.0,
            limit=7000.0,
        )

        summary = form.generate_form_5329_summary()
        assert summary['tax_year'] == 2025
        assert summary['part_i_early_distribution']['line_4_penalty'] == 0.0
        assert summary['part_iii_roth_ira_excess']['excise_tax'] == 60.0
        assert summary['total_additional_tax'] == 60.0


class TestIncomeIntegration:
    """Test Form 5329 integration with Income model."""

    def test_income_with_form_5329(self):
        """Test Income model with Form 5329."""
        form = Form5329()
        form.add_early_distribution(10000.0)

        income = Income(
            wages=50000.0,
            form_5329=form,
        )
        assert income.get_form_5329_early_distribution_penalty() == 1000.0
        assert income.get_form_5329_total_additional_tax() == 1000.0

    def test_income_no_form_5329(self):
        """Test Income model without Form 5329."""
        income = Income(wages=50000.0)
        assert income.get_form_5329_early_distribution_penalty() == 0.0
        assert income.get_form_5329_total_additional_tax() == 0.0

    def test_get_excess_contribution_tax(self):
        """Test excess contribution tax method."""
        form = Form5329()
        form.add_traditional_ira_excess(contributions=9000.0, limit=7000.0)
        form.add_roth_ira_excess(contributions=8000.0, limit=7000.0)

        income = Income(form_5329=form)
        # Traditional: 2k * 6% = 120
        # Roth: 1k * 6% = 60
        assert income.get_form_5329_excess_contribution_tax() == 180.0

    def test_get_rmd_penalty(self):
        """Test RMD penalty method."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=5000.0,
            rmd_year=2024,
        )

        income = Income(form_5329=form)
        # 5k shortfall * 25% = 1250
        assert income.get_form_5329_rmd_penalty() == 1250.0

    def test_get_form_5329_summary(self):
        """Test Form 5329 summary from Income."""
        form = Form5329(tax_year=2025)
        form.add_early_distribution(5000.0)

        income = Income(form_5329=form)
        summary = income.get_form_5329_summary()
        assert summary is not None
        assert summary['total_additional_tax'] == 500.0


class TestEngineIntegration:
    """Test Form 5329 integration with tax engine."""

    def test_engine_early_distribution_penalty(self):
        """Test engine includes early distribution penalty."""
        form = Form5329()
        form.add_early_distribution(10000.0)

        income = Income(wages=50000.0, form_5329=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        assert result.form_5329_early_distribution_penalty == 1000.0
        assert result.form_5329_total_additional_tax == 1000.0
        # Penalty is included in total tax
        assert result.total_tax_before_credits >= 1000.0

    def test_engine_excess_contribution_tax(self):
        """Test engine includes excess contribution tax."""
        form = Form5329()
        form.add_traditional_ira_excess(contributions=10000.0, limit=7000.0)

        income = Income(wages=50000.0, form_5329=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        assert result.form_5329_excess_contribution_tax == 180.0  # 3k * 6%

    def test_engine_rmd_penalty(self):
        """Test engine includes RMD penalty."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=20000.0,
            actual_amount=10000.0,
            rmd_year=2024,
        )

        income = Income(wages=50000.0, form_5329=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        # 10k shortfall * 25% = 2500
        assert result.form_5329_rmd_penalty == 2500.0

    def test_engine_combined_penalties(self):
        """Test engine with multiple Form 5329 penalties."""
        form = Form5329()
        form.add_early_distribution(5000.0)  # 500 penalty
        form.add_roth_ira_excess(contributions=8000.0, limit=7000.0)  # 60 penalty

        income = Income(wages=50000.0, form_5329=form)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        assert result.form_5329_total_additional_tax == 560.0

    def test_engine_no_form_5329(self):
        """Test engine with no Form 5329."""
        income = Income(wages=50000.0)
        tax_return = create_tax_return(income)
        engine = FederalTaxEngine()
        result = engine.calculate(tax_return)

        assert result.form_5329_early_distribution_penalty == 0.0
        assert result.form_5329_excess_contribution_tax == 0.0
        assert result.form_5329_rmd_penalty == 0.0
        assert result.form_5329_total_additional_tax == 0.0


class TestExceptionCodes:
    """Test all early distribution exception codes."""

    @pytest.mark.parametrize("code,description", [
        (EarlyDistributionExceptionCode.DISABILITY, "DISABILITY"),
        (EarlyDistributionExceptionCode.DEATH, "DEATH"),
        (EarlyDistributionExceptionCode.SEPP, "SEPP"),
        (EarlyDistributionExceptionCode.FIRST_HOME, "FIRST_HOME"),
        (EarlyDistributionExceptionCode.HIGHER_EDUCATION, "HIGHER_EDUCATION"),
        (EarlyDistributionExceptionCode.MEDICAL_EXPENSES, "MEDICAL_EXPENSES"),
        (EarlyDistributionExceptionCode.HEALTH_INSURANCE_UNEMPLOYED, "HEALTH_INSURANCE_UNEMPLOYED"),
        (EarlyDistributionExceptionCode.BIRTH_ADOPTION, "BIRTH_ADOPTION"),
        (EarlyDistributionExceptionCode.RESERVIST, "RESERVIST"),
        (EarlyDistributionExceptionCode.TERMINAL_ILLNESS, "TERMINAL_ILLNESS"),
    ])
    def test_exception_code_no_penalty(self, code, description):
        """Test that valid exception codes eliminate penalty."""
        form = Form5329()
        form.add_early_distribution(
            10000.0,
            exception_code=code,
        )
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0, f"Failed for {description}"


class TestContributionLimits:
    """Test contribution limit calculations."""

    def test_ira_limits_2025(self):
        """Test 2025 IRA contribution limits."""
        assert IRA_CONTRIBUTION_LIMITS_2025['traditional_ira_base'] == 7000.0
        assert IRA_CONTRIBUTION_LIMITS_2025['traditional_ira_catchup_50_plus'] == 1000.0
        assert IRA_CONTRIBUTION_LIMITS_2025['roth_ira_base'] == 7000.0

    def test_roth_limit_under_phaseout(self):
        """Test Roth limit when under phaseout threshold."""
        limit = calculate_roth_contribution_limit(
            magi=100000.0,
            filing_status='single',
        )
        assert limit == 7000.0

    def test_roth_limit_in_phaseout(self):
        """Test Roth limit in phaseout range."""
        limit = calculate_roth_contribution_limit(
            magi=157500.0,  # Midpoint of $150k-$165k
            filing_status='single',
        )
        assert 0 < limit < 7000.0

    def test_roth_limit_over_phaseout(self):
        """Test Roth limit over phaseout threshold."""
        limit = calculate_roth_contribution_limit(
            magi=200000.0,
            filing_status='single',
        )
        assert limit == 0.0

    def test_roth_limit_married_joint(self):
        """Test Roth limit for married filing jointly."""
        limit = calculate_roth_contribution_limit(
            magi=200000.0,
            filing_status='married_joint',
        )
        assert limit == 7000.0  # Under $236k phaseout start

    def test_roth_limit_with_catchup(self):
        """Test Roth limit with age 50+ catchup."""
        limit = calculate_roth_contribution_limit(
            magi=100000.0,
            filing_status='single',
            is_age_50_plus=True,
        )
        assert limit == 8000.0  # 7000 + 1000 catchup


class TestSecure2RmdPenaltyRates:
    """Test SECURE 2.0 reduced RMD penalty rates."""

    def test_standard_penalty_25_percent(self):
        """Standard RMD failure penalty is 25% (reduced from 50%)."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=0.0,
            rmd_year=2025,
            is_corrected=False,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 25% of $10,000 shortfall = $2,500
        assert result['total_penalty'] == pytest.approx(2500.0, rel=0.01)

    def test_corrected_penalty_10_percent(self):
        """Timely corrected RMD failure penalty is 10%."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=0.0,
            rmd_year=2025,
            is_corrected=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 10% of $10,000 shortfall = $1,000
        assert result['total_penalty'] == pytest.approx(1000.0, rel=0.01)

    def test_partial_shortfall_standard_rate(self):
        """Partial shortfall at 25% rate."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=6000.0,  # $4,000 shortfall
            rmd_year=2025,
            is_corrected=False,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 25% of $4,000 = $1,000
        assert result['total_penalty'] == pytest.approx(1000.0, rel=0.01)

    def test_partial_shortfall_corrected_rate(self):
        """Partial shortfall at 10% corrected rate."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=6000.0,  # $4,000 shortfall
            rmd_year=2025,
            is_corrected=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 10% of $4,000 = $400
        assert result['total_penalty'] == pytest.approx(400.0, rel=0.01)

    def test_waiver_requested_zero_penalty(self):
        """Waiver request results in zero penalty (taxpayer must justify)."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=0.0,
            rmd_year=2025,
            waiver_requested=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        assert result['total_penalty'] == 0.0


class TestSecure2RmdAge:
    """Test SECURE 2.0 RMD starting age determination."""

    def test_birth_year_1950_age_72(self):
        """Birth year 1950 or earlier: RMD starts at 72."""
        form = Form5329()
        assert form.get_rmd_starting_age(1950) == 72
        assert form.get_rmd_starting_age(1945) == 72
        assert form.get_rmd_starting_age(1940) == 72

    def test_birth_year_1951_1959_age_73(self):
        """Birth years 1951-1959: RMD starts at 73."""
        form = Form5329()
        assert form.get_rmd_starting_age(1951) == 73
        assert form.get_rmd_starting_age(1955) == 73
        assert form.get_rmd_starting_age(1959) == 73

    def test_birth_year_1960_plus_age_75(self):
        """Birth year 1960 or later: RMD starts at 75."""
        form = Form5329()
        assert form.get_rmd_starting_age(1960) == 75
        assert form.get_rmd_starting_age(1965) == 75
        assert form.get_rmd_starting_age(1980) == 75


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_distribution(self):
        """Test with zero distribution."""
        form = Form5329()
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_4_penalty'] == 0.0

    def test_partial_exception(self):
        """Test partial exception amount."""
        form = Form5329()
        form.add_early_distribution(
            20000.0,
            exception_code=EarlyDistributionExceptionCode.MEDICAL_EXPENSES,
            exception_amount=5000.0,  # Only 5k qualifies
        )
        result = form.calculate_part_i_early_distribution_penalty()
        # 20k - 5k = 15k subject to penalty
        assert result['line_3_subject_to_penalty'] == 15000.0
        assert result['line_4_penalty'] == 1500.0

    def test_excess_greater_than_withdrawn(self):
        """Test when withdrawn amount exceeds excess."""
        excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=9000.0,
            contribution_limit=7000.0,
            excess_withdrawn=5000.0,  # Withdrew more than excess
        )
        # Excess is 2k, but withdrew 5k - should be 0 excess
        assert excess.calculate_total_excess() == 0.0

    def test_rmd_over_distribution(self):
        """Test when actual distribution exceeds RMD."""
        failure = RMDFailure(
            required_minimum_distribution=10000.0,
            actual_distribution=15000.0,  # Took more than required
            rmd_year=2024,
        )
        assert failure.calculate_shortfall() == 0.0
        assert failure.calculate_excise_tax() == 0.0

    def test_from_1099r_total(self):
        """Test using total from 1099-R without detailed distributions."""
        form = Form5329(total_early_distributions_from_1099r=10000.0)
        result = form.calculate_part_i_early_distribution_penalty()
        assert result['line_1_total_distributions'] == 10000.0
        assert result['line_4_penalty'] == 1000.0
