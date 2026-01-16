"""Tests for Texas - No state income tax."""

import pytest
from calculator.state.state_registry import StateCalculatorRegistry, NO_INCOME_TAX_STATES


class TestTexasNoIncomeTax:
    """Tests confirming Texas has no income tax."""

    def test_texas_in_no_tax_list(self):
        """Texas should be in the no income tax states list."""
        assert "TX" in NO_INCOME_TAX_STATES

    def test_texas_returns_none(self):
        """Texas calculator should return None."""
        calc = StateCalculatorRegistry.get_calculator("TX", 2025)
        assert calc is None

    def test_texas_is_supported(self):
        """Texas should still be marked as supported (returns 0 tax)."""
        assert StateCalculatorRegistry.is_supported("TX", 2025) is True


class TestAllNoIncomeTaxStates:
    """Tests for all no-income-tax states."""

    @pytest.mark.parametrize("state_code", ["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"])
    def test_no_income_tax_states(self, state_code):
        """Each no-income-tax state should return None calculator."""
        assert state_code in NO_INCOME_TAX_STATES
        calc = StateCalculatorRegistry.get_calculator(state_code, 2025)
        assert calc is None

    @pytest.mark.parametrize("state_code", ["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"])
    def test_no_income_tax_states_supported(self, state_code):
        """Each no-income-tax state should be marked as supported."""
        assert StateCalculatorRegistry.is_supported(state_code, 2025) is True
