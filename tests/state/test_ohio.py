"""Tests for Ohio state tax calculator."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.ohio import OhioCalculator, get_ohio_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def oh_calculator():
    """Create Ohio calculator instance."""
    return OhioCalculator()


@pytest.fixture
def oh_config():
    """Get Ohio config."""
    return get_ohio_config()


def create_oh_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
) -> TaxReturn:
    """Helper to create an OH tax return."""
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="OH",
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="OH Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="OH",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="OH",
    )
    tax_return.calculate()
    return tax_return


class TestOhioConfig:
    """Tests for Ohio configuration."""

    def test_config_basic_properties(self, oh_config):
        """Test basic config properties."""
        assert oh_config.state_code == "OH"
        assert oh_config.state_name == "Ohio"
        assert oh_config.tax_year == 2025

    def test_config_progressive_brackets(self, oh_config):
        """Test Ohio has progressive brackets."""
        assert oh_config.is_flat_tax is False
        assert "single" in oh_config.brackets

    def test_config_social_security_exempt(self, oh_config):
        """Test OH exempts Social Security."""
        assert oh_config.social_security_taxable is False

    def test_config_local_tax(self, oh_config):
        """Test OH has local income tax."""
        assert oh_config.has_local_tax is True


class TestOhioCalculator:
    """Tests for Ohio calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("OH", 2025)
        assert calc is not None
        assert isinstance(calc, OhioCalculator)

    def test_basic_calculation(self, oh_calculator):
        """Test basic OH tax calculation."""
        tax_return = create_oh_return(wages=75000.0)
        breakdown = oh_calculator.calculate(tax_return)

        assert breakdown.state_code == "OH"
        assert breakdown.state_taxable_income > 0
        assert breakdown.state_tax_before_credits > 0

    def test_low_income_exemption(self, oh_calculator):
        """Test Ohio's low income exemption."""
        # Ohio has brackets starting at 0% for low income
        tax_return = create_oh_return(wages=20000.0)
        breakdown = oh_calculator.calculate(tax_return)

        # Very low tax due to low bracket
        assert breakdown.state_tax_before_credits < 500


class TestOhioBrackets:
    """Tests for Ohio tax brackets."""

    def test_middle_income(self, oh_calculator):
        """Test middle income calculation."""
        tax_return = create_oh_return(wages=80000.0)
        breakdown = oh_calculator.calculate(tax_return)

        assert breakdown.state_tax_before_credits > 1000

    def test_high_income(self, oh_calculator):
        """Test high income calculation."""
        tax_return = create_oh_return(wages=200000.0)
        breakdown = oh_calculator.calculate(tax_return)

        # Ohio max rate around 3.99%
        assert breakdown.state_tax_before_credits > 4000
