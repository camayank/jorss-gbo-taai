"""Tests for Pennsylvania state tax calculator (flat tax)."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry
from calculator.state.configs.state_2025.pennsylvania import PennsylvaniaCalculator, get_pennsylvania_config
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import TaxCredits


@pytest.fixture
def pa_calculator():
    """Create Pennsylvania calculator instance."""
    return PennsylvaniaCalculator()


@pytest.fixture
def pa_config():
    """Get Pennsylvania config."""
    return get_pennsylvania_config()


def create_pa_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    state_withholding: float = 0.0,
) -> TaxReturn:
    """Helper to create a PA tax return."""
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            state="PA",
        ),
        income=Income(
            w2_forms=[
                W2Info(
                    employer_name="PA Employer",
                    wages=wages,
                    federal_tax_withheld=wages * 0.15,
                    state_tax_withheld=state_withholding,
                    state_code="PA",
                )
            ],
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence="PA",
    )
    tax_return.calculate()
    return tax_return


class TestPennsylvaniaConfig:
    """Tests for Pennsylvania configuration."""

    def test_config_basic_properties(self, pa_config):
        """Test basic config properties."""
        assert pa_config.state_code == "PA"
        assert pa_config.state_name == "Pennsylvania"
        assert pa_config.tax_year == 2025

    def test_config_flat_tax(self, pa_config):
        """Test PA is a flat tax state."""
        assert pa_config.is_flat_tax is True
        assert pa_config.flat_rate == 0.0307  # 3.07%

    def test_config_no_standard_deduction(self, pa_config):
        """Test PA has no standard deduction."""
        # PA doesn't have standard deduction - uses none
        assert pa_config.standard_deduction["single"] == 0

    def test_config_social_security_exempt(self, pa_config):
        """Test PA exempts Social Security."""
        assert pa_config.social_security_taxable is False


class TestPennsylvaniaCalculator:
    """Tests for Pennsylvania calculator."""

    def test_calculator_registration(self):
        """Test calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("PA", 2025)
        assert calc is not None
        assert isinstance(calc, PennsylvaniaCalculator)

    def test_flat_tax_rate(self, pa_calculator):
        """Test flat 3.07% tax rate."""
        tax_return = create_pa_return(wages=100000.0)
        breakdown = pa_calculator.calculate(tax_return)

        # PA flat tax: income * 3.07%
        expected_tax = 100000 * 0.0307
        assert abs(breakdown.state_tax_before_credits - expected_tax) < 1

    def test_flat_tax_various_incomes(self, pa_calculator):
        """Test flat tax at various income levels."""
        for wages in [30000, 50000, 75000, 100000, 200000]:
            tax_return = create_pa_return(wages=wages)
            breakdown = pa_calculator.calculate(tax_return)

            expected_tax = wages * 0.0307
            assert abs(breakdown.state_tax_before_credits - expected_tax) < 5

    def test_withholding_applied(self, pa_calculator):
        """Test state withholding is applied."""
        tax_return = create_pa_return(wages=80000.0, state_withholding=2456.0)
        breakdown = pa_calculator.calculate(tax_return)

        assert breakdown.state_withholding == 2456.0

    def test_refund_calculation(self, pa_calculator):
        """Test refund when withholding exceeds tax."""
        tax_return = create_pa_return(wages=50000.0, state_withholding=2000.0)
        breakdown = pa_calculator.calculate(tax_return)

        # Tax = 50000 * 0.0307 = 1535
        # Refund = 2000 - 1535 = 465
        assert breakdown.state_refund_or_owed > 0


class TestPennsylvaniaLocalTax:
    """Tests for Pennsylvania local income tax."""

    def test_local_tax_supported(self, pa_config):
        """Test PA supports local income tax."""
        assert pa_config.has_local_tax is True
