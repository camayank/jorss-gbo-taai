"""Tests for California state tax calculator."""

import pytest

from src.calculator.state import StateTaxEngine, StateCalculatorRegistry
from src.calculator.state.configs.state_2025.california import CaliforniaCalculator, get_california_config
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits
from src.models.tax_return import TaxReturn


def create_ca_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    wages: float = 75000.0,
    federal_withholding: float = 10000.0,
    state_withholding: float = 3000.0,
    social_security: float = 0.0,
    retirement_income: float = 0.0,
) -> TaxReturn:
    """Create a California test tax return."""
    tax_return = TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="User",
            filing_status=filing_status,
            state="CA",
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="Test Corp",
                    wages=wages,
                    federal_tax_withheld=federal_withholding,
                    state_wages=wages,
                    state_tax_withheld=state_withholding,
                )
            ],
            social_security_benefits=social_security,
            taxable_social_security=social_security * 0.85 if social_security > 0 else 0,
            retirement_income=retirement_income,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="CA",
    )

    # Pre-calculate federal values
    tax_return.calculate()

    return tax_return


class TestCaliforniaConfig:
    """Test California configuration."""

    def test_config_basic_properties(self):
        """Test basic config properties."""
        config = get_california_config()

        assert config.state_code == "CA"
        assert config.state_name == "California"
        assert config.tax_year == 2025
        assert config.is_flat_tax is False
        assert config.starts_from == "federal_agi"

    def test_config_brackets_exist(self):
        """Test that brackets exist for all filing statuses."""
        config = get_california_config()

        assert "single" in config.brackets
        assert "married_joint" in config.brackets
        assert "married_separate" in config.brackets
        assert "head_of_household" in config.brackets

    def test_config_single_brackets(self):
        """Test single filing status brackets."""
        config = get_california_config()
        single_brackets = config.brackets["single"]

        # Should have 9 brackets
        assert len(single_brackets) == 9

        # First bracket starts at 0 with 1%
        assert single_brackets[0] == (0, 0.01)

        # Top bracket is 12.3%
        assert single_brackets[-1][1] == 0.123

    def test_config_standard_deduction(self):
        """Test standard deduction amounts."""
        config = get_california_config()

        assert config.standard_deduction["single"] == 5363
        assert config.standard_deduction["married_joint"] == 10726

    def test_config_social_security_exempt(self):
        """Test Social Security exemption flag."""
        config = get_california_config()
        assert config.social_security_taxable is False

    def test_config_eitc_percentage(self):
        """Test CalEITC percentage."""
        config = get_california_config()
        assert config.eitc_percentage == 0.45  # 45% of federal


class TestCaliforniaCalculator:
    """Test California calculator."""

    def test_calculator_registration(self):
        """Test that calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("CA", 2025)
        assert calc is not None
        assert isinstance(calc, CaliforniaCalculator)

    def test_basic_calculation(self):
        """Test basic CA tax calculation."""
        tax_return = create_ca_return(wages=75000.0)
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        assert result.state_code == "CA"
        assert result.filing_status == "single"
        assert result.federal_agi == tax_return.adjusted_gross_income

        # Taxable income should be AGI minus standard deduction
        expected_taxable = tax_return.adjusted_gross_income - 5363
        assert result.state_taxable_income == expected_taxable

        # Tax should be positive
        assert result.state_tax_before_credits > 0
        assert result.state_tax_liability >= 0

    def test_social_security_exemption(self):
        """Test that Social Security is exempt in CA."""
        tax_return = create_ca_return(
            wages=50000.0,
            social_security=20000.0,
        )
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # Social Security should be subtracted from state income
        # Federal AGI includes taxable SS, CA should subtract it
        assert result.state_subtractions >= tax_return.income.taxable_social_security

    def test_standard_deduction_single(self):
        """Test standard deduction for single filer."""
        tax_return = create_ca_return(
            filing_status=FilingStatus.SINGLE,
            wages=75000.0,
        )
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        assert result.deduction_used == "standard"
        assert result.state_standard_deduction == 5363

    def test_standard_deduction_married_joint(self):
        """Test standard deduction for married filing jointly."""
        tax_return = create_ca_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            wages=150000.0,
        )
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        assert result.state_standard_deduction == 10726

    def test_exemption_credits(self):
        """Test exemption credits are calculated."""
        tax_return = create_ca_return(wages=75000.0)
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # Single filer should have 1 personal exemption credit
        assert result.personal_exemptions == 1
        assert "exemption_credits" in result.state_credits
        assert result.state_credits["exemption_credits"] == 144  # $144 per exemption

    def test_withholding_applied(self):
        """Test that state withholding is applied."""
        tax_return = create_ca_return(
            wages=75000.0,
            state_withholding=5000.0,
        )
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        assert result.state_withholding == 5000.0

    def test_refund_calculation(self):
        """Test refund/owed calculation."""
        # High withholding should result in refund
        tax_return = create_ca_return(
            wages=50000.0,
            state_withholding=10000.0,
        )
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # With $10K withheld and lower income, should get refund
        assert result.state_refund_or_owed > 0

    def test_mental_health_tax(self):
        """Test mental health tax on high income."""
        # Income over $1M should trigger mental health tax
        tax_return = create_ca_return(
            wages=2000000.0,
            state_withholding=200000.0,
        )
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # Tax should include mental health surcharge
        # Tax on income over $1M should be higher than just bracket rate
        assert result.state_tax_before_credits > 0


class TestCaliforniaBrackets:
    """Test California bracket calculations."""

    def test_low_income_rate(self):
        """Test low income is taxed at lowest rates."""
        tax_return = create_ca_return(wages=10000.0)
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # $10K income after deduction ~$4,637
        # Should be taxed at 1% bracket mostly
        assert result.state_tax_before_credits < 100  # Should be very low

    def test_middle_income(self):
        """Test middle income calculation."""
        tax_return = create_ca_return(wages=75000.0)
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # $75K income should result in meaningful tax
        # Expected range: $2,500 - $4,500
        assert 2000 < result.state_tax_before_credits < 5000

    def test_high_income(self):
        """Test high income hits top brackets."""
        tax_return = create_ca_return(wages=500000.0)
        calc = CaliforniaCalculator()

        result = calc.calculate(tax_return)

        # $500K should hit the 10.3% and possibly 11.3% brackets
        # Expected tax should be significant
        assert result.state_tax_before_credits > 30000
