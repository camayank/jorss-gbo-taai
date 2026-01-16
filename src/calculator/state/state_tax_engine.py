"""State tax engine - orchestrates state tax calculations."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from calculator.state.base_state_calculator import StateCalculationBreakdown
from calculator.state.state_registry import StateCalculatorRegistry, NO_INCOME_TAX_STATES


class StateTaxEngine:
    """
    Orchestrates state tax calculations.

    This engine looks up the appropriate state calculator from the registry
    and executes the calculation. It handles no-income-tax states by returning None.
    """

    def __init__(self, tax_year: int = 2025):
        """
        Initialize the state tax engine.

        Args:
            tax_year: Default tax year for calculations
        """
        self.tax_year = tax_year

    def calculate(
        self,
        tax_return: "TaxReturn",
        state_code: str
    ) -> Optional[StateCalculationBreakdown]:
        """
        Calculate state tax for the given return and state.

        Args:
            tax_return: The federal tax return with income, deductions, etc.
            state_code: Two-letter state code (e.g., "CA", "NY")

        Returns:
            StateCalculationBreakdown or None if state has no income tax
            or is not supported
        """
        state_upper = state_code.upper()

        # No income tax states
        if state_upper in NO_INCOME_TAX_STATES:
            return None

        # Get calculator from registry
        calculator = StateCalculatorRegistry.get_calculator(
            state_upper,
            self.tax_year
        )

        if not calculator:
            # State not supported yet
            return None

        return calculator.calculate(tax_return)

    def is_state_supported(self, state_code: str) -> bool:
        """
        Check if a state is supported.

        Args:
            state_code: Two-letter state code

        Returns:
            True if state has a registered calculator or has no income tax
        """
        state_upper = state_code.upper()

        # No income tax states are always "supported"
        if state_upper in NO_INCOME_TAX_STATES:
            return True

        return StateCalculatorRegistry.is_supported(state_upper, self.tax_year)

    def has_income_tax(self, state_code: str) -> bool:
        """
        Check if a state has income tax.

        Args:
            state_code: Two-letter state code

        Returns:
            True if state has income tax, False otherwise
        """
        return state_code.upper() not in NO_INCOME_TAX_STATES

    def get_supported_states(self) -> list:
        """
        Get list of states with registered calculators.

        Returns:
            Sorted list of supported state codes
        """
        return StateCalculatorRegistry.get_supported_states(self.tax_year)

    def get_no_income_tax_states(self) -> list:
        """
        Get list of states with no income tax.

        Returns:
            Sorted list of state codes with no income tax
        """
        return sorted(NO_INCOME_TAX_STATES)
