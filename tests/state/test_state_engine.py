"""Tests for state tax engine and registry."""

import pytest

from src.calculator.state import (
    StateTaxEngine,
    StateCalculatorRegistry,
    NO_INCOME_TAX_STATES,
)
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits
from src.models.tax_return import TaxReturn


def create_test_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    wages: float = 75000.0,
    state: str = "CA",
    federal_withholding: float = 10000.0,
    state_withholding: float = 3000.0,
) -> TaxReturn:
    """Create a test tax return with common defaults."""
    return TaxReturn(
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="User",
            filing_status=filing_status,
            state=state,
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
            ]
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
        state_of_residence=state,
    )


class TestNoIncomeTaxStates:
    """Test handling of states with no income tax."""

    def test_no_income_tax_states_list(self):
        """Verify the list of no-income-tax states."""
        expected = {"AK", "FL", "NV", "SD", "TX", "WA", "WY", "TN", "NH"}
        assert NO_INCOME_TAX_STATES == expected

    @pytest.mark.parametrize("state", ["TX", "FL", "WA", "NV", "WY", "SD", "AK"])
    def test_no_income_tax_state_returns_none(self, state):
        """States with no income tax should return None from engine."""
        engine = StateTaxEngine(tax_year=2025)
        tax_return = create_test_return(state=state)
        tax_return.adjusted_gross_income = 75000.0
        tax_return.taxable_income = 60000.0

        result = engine.calculate(tax_return, state)
        assert result is None

    def test_engine_has_income_tax_method(self):
        """Test has_income_tax method."""
        engine = StateTaxEngine(tax_year=2025)

        # States with income tax
        assert engine.has_income_tax("CA") is True
        assert engine.has_income_tax("NY") is True
        assert engine.has_income_tax("IL") is True

        # States without income tax
        assert engine.has_income_tax("TX") is False
        assert engine.has_income_tax("FL") is False


class TestStateRegistry:
    """Test state calculator registry."""

    def test_get_supported_states(self):
        """Test getting list of supported states."""
        supported = StateCalculatorRegistry.get_supported_states(2025)

        # Should include our implemented states
        assert "CA" in supported
        assert "NY" in supported
        assert "IL" in supported

    def test_get_calculator_for_supported_state(self):
        """Test retrieving calculator for supported state."""
        calc = StateCalculatorRegistry.get_calculator("CA", 2025)
        assert calc is not None
        assert calc.config.state_code == "CA"

    def test_get_calculator_for_unsupported_state(self):
        """Test retrieving calculator for unsupported state returns None."""
        calc = StateCalculatorRegistry.get_calculator("XX", 2025)
        assert calc is None

    def test_is_supported_method(self):
        """Test is_supported method."""
        assert StateCalculatorRegistry.is_supported("CA", 2025) is True
        assert StateCalculatorRegistry.is_supported("NY", 2025) is True
        assert StateCalculatorRegistry.is_supported("XX", 2025) is False

        # No-income-tax states are "supported" (return True)
        assert StateCalculatorRegistry.is_supported("TX", 2025) is True


class TestStateTaxEngine:
    """Test state tax engine orchestration."""

    def test_engine_initialization(self):
        """Test engine initializes with correct tax year."""
        engine = StateTaxEngine(tax_year=2025)
        assert engine.tax_year == 2025

    def test_engine_get_supported_states(self):
        """Test engine returns supported states."""
        engine = StateTaxEngine(tax_year=2025)
        supported = engine.get_supported_states()

        assert isinstance(supported, list)
        assert "CA" in supported

    def test_engine_get_no_income_tax_states(self):
        """Test engine returns no-income-tax states."""
        engine = StateTaxEngine(tax_year=2025)
        no_tax_states = engine.get_no_income_tax_states()

        assert "TX" in no_tax_states
        assert "FL" in no_tax_states
        assert "CA" not in no_tax_states

    def test_engine_is_state_supported(self):
        """Test engine is_state_supported method."""
        engine = StateTaxEngine(tax_year=2025)

        # Implemented states
        assert engine.is_state_supported("CA") is True
        assert engine.is_state_supported("NY") is True

        # No-income-tax states are "supported"
        assert engine.is_state_supported("TX") is True

    def test_engine_calculate_returns_breakdown(self):
        """Test that engine returns StateCalculationBreakdown."""
        engine = StateTaxEngine(tax_year=2025)
        tax_return = create_test_return(state="CA")

        # Need to pre-calculate federal values
        tax_return.adjusted_gross_income = 75000.0
        tax_return.taxable_income = 60000.0

        result = engine.calculate(tax_return, "CA")

        assert result is not None
        assert result.state_code == "CA"
        assert result.state_name == "California"
        assert result.tax_year == 2025
