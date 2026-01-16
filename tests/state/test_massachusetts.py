"""Tests for Massachusetts state tax calculator (flat tax with surtax)."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.massachusetts import MassachusettsCalculator, get_massachusetts_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def ma_calculator():
    """Create Massachusetts calculator instance."""
    return MassachusettsCalculator()


@pytest.fixture
def ma_config():
    """Get Massachusetts config."""
    return get_massachusetts_config()


def create_ma_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
    dependents: int = 0,
) -> TaxReturn:
    """Helper to create an MA tax return."""
    from models.taxpayer import Dependent
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="MA",
            dependents=[Dependent(name=f"Dep {i}", relationship="child", age=10) for i in range(dependents)],
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="MA Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="MA",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="MA",
    )
    tax_return.calculate()
    return tax_return


class TestMassachusettsConfig:
    """Tests for Massachusetts configuration."""

    def test_config_basic_properties(self, ma_config):
        """Test basic config properties."""
        assert ma_config.state_code == "MA"
        assert ma_config.state_name == "Massachusetts"
        assert ma_config.tax_year == 2025

    def test_config_flat_tax(self, ma_config):
        """Test MA is a flat tax state."""
        assert ma_config.is_flat_tax is True
        assert ma_config.flat_rate == 0.05  # 5.0%

    def test_config_social_security_exempt(self, ma_config):
        """Test MA exempts Social Security."""
        assert ma_config.social_security_taxable is False

    def test_config_no_local_tax(self, ma_config):
        """Test MA has no local income tax."""
        assert ma_config.has_local_tax is False


class TestMassachusettsCalculator:
    """Tests for Massachusetts calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("MA", 2025)
        assert calc is not None
        assert isinstance(calc, MassachusettsCalculator)

    def test_flat_tax_rate(self, ma_calculator):
        """Test flat 5% tax rate."""
        tax_return = create_ma_return(wages=100000.0)
        breakdown = ma_calculator.calculate(tax_return)

        # After exemptions, roughly 5% rate
        assert breakdown.state_tax_before_credits > 0
        # Effective rate close to 5% for most income
        effective_rate = breakdown.state_tax_before_credits / 100000
        assert 0.04 < effective_rate < 0.06

    def test_basic_calculation(self, ma_calculator):
        """Test basic MA tax calculation."""
        tax_return = create_ma_return(wages=75000.0)
        breakdown = ma_calculator.calculate(tax_return)

        assert breakdown.state_code == "MA"
        assert breakdown.state_tax_before_credits > 0


class TestMassachusettsFlatTax:
    """Tests for Massachusetts flat tax calculation."""

    def test_various_income_levels(self, ma_calculator):
        """Test flat tax at various income levels."""
        incomes = [40000, 60000, 80000, 100000, 150000]

        for income in incomes:
            tax_return = create_ma_return(wages=income)
            breakdown = ma_calculator.calculate(tax_return)

            # Tax should be roughly 5% of income (minus exemptions)
            assert breakdown.state_tax_before_credits > 0

    def test_withholding_applied(self, ma_calculator):
        """Test state withholding is applied."""
        tax_return = create_ma_return(wages=80000.0, state_withholding=4000.0)
        breakdown = ma_calculator.calculate(tax_return)

        assert breakdown.state_withholding == 4000.0

    def test_refund_when_overpaid(self, ma_calculator):
        """Test refund when withholding exceeds tax."""
        tax_return = create_ma_return(wages=50000.0, state_withholding=4000.0)
        breakdown = ma_calculator.calculate(tax_return)

        # 5% of $50k = $2,500, withholding $4k = refund
        assert breakdown.state_refund_or_owed > 0


class TestMassachusettsMillionaireTax:
    """Tests for Massachusetts millionaire surtax (4% on income over $1M)."""

    def test_under_million_no_surtax(self, ma_calculator):
        """Test no surtax for income under $1M."""
        tax_return = create_ma_return(wages=500000.0)
        breakdown = ma_calculator.calculate(tax_return)

        # At 5%, ~$25k tax
        expected_approx = 500000 * 0.05
        assert breakdown.state_tax_before_credits < expected_approx * 1.1

    def test_over_million_surtax_applies(self, ma_calculator):
        """Test 4% surtax on income over $1M."""
        tax_return = create_ma_return(wages=1500000.0)
        breakdown = ma_calculator.calculate(tax_return)

        # Base: 5% on $1.5M = $75k
        # Surtax: 4% on $500k (amount over $1M) = $20k
        # Total should be around $95k (minus exemptions)
        assert breakdown.state_tax_before_credits > 80000


class TestMassachusettsExemptions:
    """Tests for Massachusetts exemptions."""

    def test_personal_exemption(self, ma_calculator):
        """Test personal exemption."""
        tax_return = create_ma_return(wages=60000.0)
        breakdown = ma_calculator.calculate(tax_return)

        assert breakdown.personal_exemptions >= 1
        assert breakdown.exemption_amount > 0

    def test_dependent_exemption(self, ma_calculator):
        """Test dependent exemption."""
        tax_return = create_ma_return(wages=80000.0, dependents=2)
        breakdown = ma_calculator.calculate(tax_return)

        assert breakdown.dependent_exemptions == 2
