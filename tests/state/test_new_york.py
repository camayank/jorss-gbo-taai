"""Tests for New York state tax calculator."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.new_york import NewYorkCalculator, get_new_york_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def ny_calculator():
    """Create New York calculator instance."""
    return NewYorkCalculator()


@pytest.fixture
def ny_config():
    """Get New York config."""
    return get_new_york_config()


def create_ny_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
    dependents: int = 0,
) -> TaxReturn:
    """Helper to create a NY tax return."""
    from models.taxpayer import Dependent
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="NY",
            dependents=[Dependent(name=f"Dep {i}", relationship="child", age=10) for i in range(dependents)],
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="NY Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="NY",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="NY",
    )
    tax_return.calculate()
    return tax_return


class TestNewYorkConfig:
    """Tests for New York configuration."""

    def test_config_basic_properties(self, ny_config):
        """Test basic config properties."""
        assert ny_config.state_code == "NY"
        assert ny_config.state_name == "New York"
        assert ny_config.tax_year == 2025
        assert ny_config.is_flat_tax is False

    def test_config_brackets_exist(self, ny_config):
        """Test that brackets exist for all filing statuses."""
        assert "single" in ny_config.brackets
        assert "married_joint" in ny_config.brackets
        assert "married_separate" in ny_config.brackets
        assert "head_of_household" in ny_config.brackets

    def test_config_single_brackets(self, ny_config):
        """Test NY single brackets (8 brackets)."""
        single_brackets = ny_config.brackets["single"]
        assert len(single_brackets) >= 8
        # NY has progressive brackets from 4% to 10.9%
        assert single_brackets[0][1] == 0.04  # 4% lowest
        assert single_brackets[-1][1] == 0.109  # 10.9% highest

    def test_config_standard_deduction(self, ny_config):
        """Test NY standard deduction amounts."""
        # NY has relatively low standard deductions
        assert ny_config.standard_deduction["single"] == 8000
        assert ny_config.standard_deduction["married_joint"] == 16050

    def test_config_social_security_exempt(self, ny_config):
        """Test NY exempts Social Security."""
        assert ny_config.social_security_taxable is False


class TestNewYorkCalculator:
    """Tests for New York calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("NY", 2025)
        assert calc is not None
        assert isinstance(calc, NewYorkCalculator)

    def test_basic_calculation(self, ny_calculator):
        """Test basic NY tax calculation."""
        tax_return = create_ny_return(wages=75000.0)
        breakdown = ny_calculator.calculate(tax_return)

        assert breakdown.state_code == "NY"
        assert breakdown.state_taxable_income > 0
        assert breakdown.state_tax_before_credits > 0

    def test_standard_deduction_single(self, ny_calculator):
        """Test standard deduction for single filer."""
        tax_return = create_ny_return(wages=50000.0, filing_status=FilingStatus.SINGLE)
        breakdown = ny_calculator.calculate(tax_return)

        assert breakdown.state_standard_deduction == 8000

    def test_standard_deduction_married_joint(self, ny_calculator):
        """Test standard deduction for MFJ."""
        tax_return = create_ny_return(wages=100000.0, filing_status=FilingStatus.MARRIED_JOINT)
        breakdown = ny_calculator.calculate(tax_return)

        assert breakdown.state_standard_deduction == 16050

    def test_withholding_applied(self, ny_calculator):
        """Test state withholding is applied."""
        tax_return = create_ny_return(wages=80000.0, state_withholding=4000.0)
        breakdown = ny_calculator.calculate(tax_return)

        assert breakdown.state_withholding == 4000.0

    def test_refund_calculation(self, ny_calculator):
        """Test refund when withholding exceeds tax."""
        tax_return = create_ny_return(wages=40000.0, state_withholding=5000.0)
        breakdown = ny_calculator.calculate(tax_return)

        # Refund = withholding - tax liability
        expected_refund = breakdown.state_withholding - breakdown.state_tax_liability
        assert breakdown.state_refund_or_owed == expected_refund


class TestNewYorkBrackets:
    """Tests for New York tax brackets."""

    def test_low_income_rate(self, ny_calculator):
        """Test low income at lowest rate."""
        tax_return = create_ny_return(wages=20000.0)
        breakdown = ny_calculator.calculate(tax_return)

        # $20k - $8k std ded = $12k taxable
        # Tax should be reasonable for this income level
        assert breakdown.state_tax_before_credits > 0
        assert breakdown.state_tax_before_credits < 1000

    def test_middle_income(self, ny_calculator):
        """Test middle income with multiple brackets."""
        tax_return = create_ny_return(wages=80000.0)
        breakdown = ny_calculator.calculate(tax_return)

        # $80k - $8k = $72k taxable, spans multiple brackets
        assert breakdown.state_tax_before_credits > 2000
        assert breakdown.state_tax_before_credits < 6000

    def test_high_income(self, ny_calculator):
        """Test high income at top bracket."""
        tax_return = create_ny_return(wages=300000.0)
        breakdown = ny_calculator.calculate(tax_return)

        # High earners face up to 10.9%
        assert breakdown.state_tax_before_credits > 10000


class TestNewYorkYonkersTax:
    """Tests for Yonkers local tax."""

    def test_local_tax_available(self, ny_config):
        """Test NY supports local tax."""
        assert ny_config.has_local_tax is True


class TestNewYorkCredits:
    """Tests for New York tax credits."""

    def test_dependent_exemption(self, ny_calculator):
        """Test dependent exemption credit."""
        tax_return = create_ny_return(wages=75000.0, dependents=2)
        breakdown = ny_calculator.calculate(tax_return)

        assert breakdown.dependent_exemptions == 2
        assert breakdown.exemption_amount > 0
