"""Tests for Virginia state tax calculator."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.virginia import VirginiaCalculator, get_virginia_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def va_calculator():
    """Create Virginia calculator instance."""
    return VirginiaCalculator()


@pytest.fixture
def va_config():
    """Get Virginia config."""
    return get_virginia_config()


def create_va_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
    dependents: int = 0,
) -> TaxReturn:
    """Helper to create a VA tax return."""
    from models.taxpayer import Dependent
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="VA",
            dependents=[Dependent(name=f"Dep {i}", relationship="child", age=10) for i in range(dependents)],
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="VA Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="VA",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="VA",
    )
    tax_return.calculate()
    return tax_return


class TestVirginiaConfig:
    """Tests for Virginia configuration."""

    def test_config_basic_properties(self, va_config):
        """Test basic config properties."""
        assert va_config.state_code == "VA"
        assert va_config.state_name == "Virginia"
        assert va_config.tax_year == 2025

    def test_config_progressive_brackets(self, va_config):
        """Test VA has progressive brackets."""
        assert va_config.is_flat_tax is False
        # VA has 4 brackets
        assert len(va_config.brackets["single"]) == 4

    def test_config_top_rate(self, va_config):
        """Test VA top rate is 5.75%."""
        brackets = va_config.brackets["single"]
        assert brackets[-1][1] == 0.0575  # 5.75% top rate

    def test_config_social_security_exempt(self, va_config):
        """Test VA exempts Social Security."""
        assert va_config.social_security_taxable is False

    def test_config_standard_deduction(self, va_config):
        """Test VA standard deduction."""
        assert va_config.standard_deduction["single"] > 0


class TestVirginiaCalculator:
    """Tests for Virginia calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("VA", 2025)
        assert calc is not None
        assert isinstance(calc, VirginiaCalculator)

    def test_basic_calculation(self, va_calculator):
        """Test basic VA tax calculation."""
        tax_return = create_va_return(wages=75000.0)
        breakdown = va_calculator.calculate(tax_return)

        assert breakdown.state_code == "VA"
        assert breakdown.state_taxable_income > 0
        assert breakdown.state_tax_before_credits > 0

    def test_personal_exemption(self, va_calculator):
        """Test personal exemption."""
        tax_return = create_va_return(wages=50000.0)
        breakdown = va_calculator.calculate(tax_return)

        assert breakdown.personal_exemptions >= 1
        assert breakdown.exemption_amount > 0


class TestVirginiaBrackets:
    """Tests for Virginia tax brackets."""

    def test_low_income_2_percent(self, va_calculator):
        """Test low income at 2% rate."""
        tax_return = create_va_return(wages=10000.0)
        breakdown = va_calculator.calculate(tax_return)

        # Low income faces 2% on first $3k
        assert breakdown.state_tax_before_credits < 500

    def test_middle_income(self, va_calculator):
        """Test middle income calculation."""
        tax_return = create_va_return(wages=70000.0)
        breakdown = va_calculator.calculate(tax_return)

        # Should be in higher brackets
        assert breakdown.state_tax_before_credits > 2000

    def test_high_income_at_max_rate(self, va_calculator):
        """Test high income at 5.75% max rate."""
        tax_return = create_va_return(wages=150000.0)
        breakdown = va_calculator.calculate(tax_return)

        # Most income at 5.75%
        assert breakdown.state_tax_before_credits > 6000


class TestVirginiaCredits:
    """Tests for Virginia tax credits."""

    def test_dependent_exemption(self, va_calculator):
        """Test dependent exemption."""
        tax_return = create_va_return(wages=80000.0, dependents=3)
        breakdown = va_calculator.calculate(tax_return)

        assert breakdown.dependent_exemptions == 3
