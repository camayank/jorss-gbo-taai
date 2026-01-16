"""Tests for Georgia state tax calculator."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.georgia import GeorgiaCalculator, get_georgia_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def ga_calculator():
    """Create Georgia calculator instance."""
    return GeorgiaCalculator()


@pytest.fixture
def ga_config():
    """Get Georgia config."""
    return get_georgia_config()


def create_ga_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
) -> TaxReturn:
    """Helper to create a GA tax return."""
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="GA",
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="GA Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="GA",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="GA",
    )
    tax_return.calculate()
    return tax_return


class TestGeorgiaConfig:
    """Tests for Georgia configuration."""

    def test_config_basic_properties(self, ga_config):
        """Test basic config properties."""
        assert ga_config.state_code == "GA"
        assert ga_config.state_name == "Georgia"
        assert ga_config.tax_year == 2025

    def test_config_flat_tax_transition(self, ga_config):
        """Test Georgia's flat tax (transitioning from graduated)."""
        # Georgia moved to flat tax starting 2024
        assert ga_config.is_flat_tax is True
        assert ga_config.flat_rate == 0.0539  # 5.39% for 2025

    def test_config_standard_deduction(self, ga_config):
        """Test GA standard deduction."""
        assert ga_config.standard_deduction["single"] > 0
        assert ga_config.standard_deduction["married_joint"] > ga_config.standard_deduction["single"]


class TestGeorgiaCalculator:
    """Tests for Georgia calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("GA", 2025)
        assert calc is not None
        assert isinstance(calc, GeorgiaCalculator)

    def test_basic_calculation(self, ga_calculator):
        """Test basic GA tax calculation."""
        tax_return = create_ga_return(wages=75000.0)
        breakdown = ga_calculator.calculate(tax_return)

        assert breakdown.state_code == "GA"
        assert breakdown.state_taxable_income > 0
        assert breakdown.state_tax_before_credits > 0

    def test_flat_tax_rate(self, ga_calculator):
        """Test flat 5.39% tax rate."""
        tax_return = create_ga_return(wages=100000.0)
        breakdown = ga_calculator.calculate(tax_return)

        # After standard deduction and exemptions
        # Tax should be reasonable for flat rate state
        assert breakdown.state_tax_before_credits > 3000
        assert breakdown.state_tax_before_credits < 6000

    def test_standard_deduction_single(self, ga_calculator):
        """Test standard deduction for single filer."""
        tax_return = create_ga_return(wages=50000.0, filing_status=FilingStatus.SINGLE)
        breakdown = ga_calculator.calculate(tax_return)

        assert breakdown.state_standard_deduction > 0


class TestGeorgiaBrackets:
    """Tests for Georgia tax computation."""

    def test_middle_income(self, ga_calculator):
        """Test middle income calculation."""
        tax_return = create_ga_return(wages=60000.0)
        breakdown = ga_calculator.calculate(tax_return)

        # Should have meaningful tax
        assert breakdown.state_tax_before_credits > 1500

    def test_high_income(self, ga_calculator):
        """Test high income calculation."""
        tax_return = create_ga_return(wages=200000.0)
        breakdown = ga_calculator.calculate(tax_return)

        # High earners face flat 5.39%
        assert breakdown.state_tax_before_credits > 8000
