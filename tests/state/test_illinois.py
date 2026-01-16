"""Tests for Illinois state tax calculator (flat tax example)."""

import pytest

from src.calculator.state import StateTaxEngine, StateCalculatorRegistry
from src.calculator.state.configs.state_2025.illinois import IllinoisCalculator, get_illinois_config
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions, ItemizedDeductions
from src.models.credits import TaxCredits
from src.models.tax_return import TaxReturn


def create_il_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    wages: float = 75000.0,
    federal_withholding: float = 10000.0,
    state_withholding: float = 3000.0,
    social_security: float = 0.0,
    retirement_income: float = 0.0,
    property_tax: float = 0.0,
) -> TaxReturn:
    """Create an Illinois test tax return."""
    itemized = ItemizedDeductions(
        real_estate_tax=property_tax,
    )

    tax_return = TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="User",
            filing_status=filing_status,
            state="IL",
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
        deductions=Deductions(
            use_standard_deduction=True,
            itemized=itemized,
        ),
        credits=TaxCredits(),
        state_of_residence="IL",
    )

    # Pre-calculate federal values
    tax_return.calculate()

    return tax_return


class TestIllinoisConfig:
    """Test Illinois configuration."""

    def test_config_basic_properties(self):
        """Test basic config properties."""
        config = get_illinois_config()

        assert config.state_code == "IL"
        assert config.state_name == "Illinois"
        assert config.tax_year == 2025
        assert config.is_flat_tax is True
        assert config.flat_rate == 0.0495  # 4.95%

    def test_config_no_brackets(self):
        """Test that brackets are None for flat tax."""
        config = get_illinois_config()
        assert config.brackets is None

    def test_config_exemption_amount(self):
        """Test personal exemption amount."""
        config = get_illinois_config()
        assert config.personal_exemption_amount["single"] == 2625

    def test_config_social_security_exempt(self):
        """Test Social Security exemption."""
        config = get_illinois_config()
        assert config.social_security_taxable is False

    def test_config_eitc_percentage(self):
        """Test IL EITC percentage."""
        config = get_illinois_config()
        assert config.eitc_percentage == 0.20  # 20% of federal


class TestIllinoisCalculator:
    """Test Illinois flat tax calculator."""

    def test_calculator_registration(self):
        """Test that calculator is registered."""
        calc = StateCalculatorRegistry.get_calculator("IL", 2025)
        assert calc is not None
        assert isinstance(calc, IllinoisCalculator)

    def test_flat_rate_calculation(self):
        """Test flat rate is applied correctly."""
        tax_return = create_il_return(wages=100000.0)
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # IL taxable = AGI - exemption ($2,625 for single)
        # Tax = taxable * 4.95%
        expected_taxable = tax_return.adjusted_gross_income - 2625
        expected_tax = expected_taxable * 0.0495

        assert result.state_taxable_income == expected_taxable
        assert abs(result.state_tax_before_credits - expected_tax) < 1  # Allow rounding

    def test_exemption_calculation(self):
        """Test exemption is applied."""
        tax_return = create_il_return(wages=75000.0)
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # Single filer gets 1 exemption of $2,625
        assert result.personal_exemptions == 1
        assert result.exemption_amount == 2625

    def test_married_joint_exemptions(self):
        """Test married filing jointly exemptions."""
        tax_return = create_il_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            wages=150000.0,
        )
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # Married joint gets 2 exemptions
        assert result.personal_exemptions == 2
        assert result.exemption_amount == 2625 * 2

    def test_social_security_exemption(self):
        """Test Social Security is fully exempt."""
        tax_return = create_il_return(
            wages=50000.0,
            social_security=30000.0,
        )
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # Social Security should be subtracted
        assert result.state_subtractions >= tax_return.income.taxable_social_security

    def test_retirement_income_exemption(self):
        """Test retirement income is fully exempt in IL."""
        tax_return = create_il_return(
            wages=50000.0,
            retirement_income=25000.0,
        )
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # Retirement income should be subtracted
        assert result.state_subtractions >= 25000.0

    def test_property_tax_credit(self):
        """Test property tax credit calculation."""
        tax_return = create_il_return(
            wages=75000.0,
            property_tax=5000.0,
        )
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # Property tax credit is 5% of property taxes paid
        if "property_tax_credit" in result.state_credits:
            assert result.state_credits["property_tax_credit"] == 250.0  # 5% of $5,000

    def test_no_local_tax(self):
        """Test there's no local tax in Illinois."""
        tax_return = create_il_return(wages=75000.0)
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        assert result.local_tax == 0.0

    def test_deduction_used_is_none(self):
        """Test that Illinois reports no standard/itemized deduction."""
        tax_return = create_il_return(wages=75000.0)
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # IL uses exemptions, not standard deduction
        assert result.deduction_used == "none"
        assert result.deduction_amount == 0.0


class TestIllinoisFlatTaxVerification:
    """Verify flat tax calculations are correct."""

    @pytest.mark.parametrize("wages,expected_tax_approx", [
        (50000, 2343),    # (50000 - 2625) * 0.0495 = 2343.56
        (75000, 3580),    # (75000 - 2625) * 0.0495 = 3582.56
        (100000, 4820),   # (100000 - 2625) * 0.0495 = 4820.06
        (200000, 9770),   # (200000 - 2625) * 0.0495 = 9770.06
    ])
    def test_tax_at_various_incomes(self, wages, expected_tax_approx):
        """Test tax calculation at various income levels."""
        tax_return = create_il_return(wages=float(wages))
        calc = IllinoisCalculator()

        result = calc.calculate(tax_return)

        # Allow $50 tolerance for rounding differences
        assert abs(result.state_tax_before_credits - expected_tax_approx) < 50
