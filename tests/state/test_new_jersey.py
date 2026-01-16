"""Tests for New Jersey state tax calculator."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.new_jersey import NewJerseyCalculator, get_new_jersey_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def nj_calculator():
    """Create New Jersey calculator instance."""
    return NewJerseyCalculator()


@pytest.fixture
def nj_config():
    """Get New Jersey config."""
    return get_new_jersey_config()


def create_nj_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
    dependents: int = 0,
) -> TaxReturn:
    """Helper to create an NJ tax return."""
    from models.taxpayer import Dependent
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="NJ",
            dependents=[Dependent(name=f"Dep {i}", relationship="child", age=10) for i in range(dependents)],
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="NJ Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="NJ",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="NJ",
    )
    tax_return.calculate()
    return tax_return


class TestNewJerseyConfig:
    """Tests for New Jersey configuration."""

    def test_config_basic_properties(self, nj_config):
        """Test basic config properties."""
        assert nj_config.state_code == "NJ"
        assert nj_config.state_name == "New Jersey"
        assert nj_config.tax_year == 2025

    def test_config_progressive_brackets(self, nj_config):
        """Test NJ has progressive brackets."""
        assert nj_config.is_flat_tax is False
        assert len(nj_config.brackets["single"]) >= 6

    def test_config_social_security_exempt(self, nj_config):
        """Test NJ exempts Social Security."""
        assert nj_config.social_security_taxable is False

    def test_config_no_standard_deduction(self, nj_config):
        """Test NJ has no standard deduction (uses exemptions)."""
        # NJ doesn't have federal-style standard deduction
        assert nj_config.standard_deduction["single"] == 0


class TestNewJerseyCalculator:
    """Tests for New Jersey calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("NJ", 2025)
        assert calc is not None
        assert isinstance(calc, NewJerseyCalculator)

    def test_basic_calculation(self, nj_calculator):
        """Test basic NJ tax calculation."""
        tax_return = create_nj_return(wages=75000.0)
        breakdown = nj_calculator.calculate(tax_return)

        assert breakdown.state_code == "NJ"
        assert breakdown.state_tax_before_credits > 0

    def test_exemption_calculation(self, nj_calculator):
        """Test personal exemption."""
        tax_return = create_nj_return(wages=60000.0)
        breakdown = nj_calculator.calculate(tax_return)

        assert breakdown.personal_exemptions >= 1
        assert breakdown.exemption_amount > 0


class TestNewJerseyBrackets:
    """Tests for New Jersey tax brackets."""

    def test_low_income_rate(self, nj_calculator):
        """Test low income at 1.4% rate."""
        tax_return = create_nj_return(wages=25000.0)
        breakdown = nj_calculator.calculate(tax_return)

        # Low income faces low rates
        assert breakdown.state_tax_before_credits < 500

    def test_middle_income(self, nj_calculator):
        """Test middle income calculation."""
        tax_return = create_nj_return(wages=100000.0)
        breakdown = nj_calculator.calculate(tax_return)

        # Multiple brackets apply
        assert breakdown.state_tax_before_credits > 1500

    def test_high_income_millionaire_tax(self, nj_calculator):
        """Test high income (millionaire tax at 10.75%)."""
        tax_return = create_nj_return(wages=1500000.0)
        breakdown = nj_calculator.calculate(tax_return)

        # Very high earners face up to 10.75%
        assert breakdown.state_tax_before_credits > 80000


class TestNewJerseyCredits:
    """Tests for New Jersey tax credits."""

    def test_dependent_exemption(self, nj_calculator):
        """Test dependent exemption."""
        tax_return = create_nj_return(wages=75000.0, dependents=2)
        breakdown = nj_calculator.calculate(tax_return)

        assert breakdown.dependent_exemptions == 2
