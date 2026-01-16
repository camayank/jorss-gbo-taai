"""State calculator registry for dynamic lookup."""

from __future__ import annotations

from typing import Dict, Type, Optional, List, Callable

from calculator.state.base_state_calculator import BaseStateCalculator


# States without income tax
NO_INCOME_TAX_STATES = frozenset({
    "AK",  # Alaska
    "FL",  # Florida
    "NV",  # Nevada
    "SD",  # South Dakota
    "TX",  # Texas
    "WA",  # Washington
    "WY",  # Wyoming
    "TN",  # Tennessee (no tax on wages, limited tax on interest/dividends being phased out)
    "NH",  # New Hampshire (no tax on wages, limited tax on interest/dividends being phased out)
})


class StateCalculatorRegistry:
    """
    Registry for state tax calculators.

    Uses a factory pattern to register and retrieve state-specific calculators
    based on state code and tax year.
    """

    # Storage: state_code -> tax_year -> calculator_class
    _calculators: Dict[str, Dict[int, Type[BaseStateCalculator]]] = {}

    @classmethod
    def register(
        cls,
        state_code: str,
        tax_year: int,
        calculator_class: Type[BaseStateCalculator]
    ) -> None:
        """
        Register a calculator for a state and year.

        Args:
            state_code: Two-letter state code (e.g., "CA", "NY")
            tax_year: Tax year this calculator handles
            calculator_class: The calculator class to register
        """
        state_upper = state_code.upper()
        if state_upper not in cls._calculators:
            cls._calculators[state_upper] = {}
        cls._calculators[state_upper][tax_year] = calculator_class

    @classmethod
    def get_calculator(
        cls,
        state_code: str,
        tax_year: int
    ) -> Optional[BaseStateCalculator]:
        """
        Get calculator instance for a state and year.

        Args:
            state_code: Two-letter state code
            tax_year: Tax year

        Returns:
            Calculator instance or None if not supported
        """
        state_upper = state_code.upper()

        # No income tax states return None
        if state_upper in NO_INCOME_TAX_STATES:
            return None

        state_calcs = cls._calculators.get(state_upper)
        if not state_calcs:
            return None

        calculator_class = state_calcs.get(tax_year)
        if not calculator_class:
            return None

        return calculator_class()

    @classmethod
    def get_supported_states(cls, tax_year: int) -> List[str]:
        """
        Get list of supported state codes for a tax year.

        Args:
            tax_year: Tax year to check

        Returns:
            Sorted list of supported state codes
        """
        supported = []
        for state_code, years in cls._calculators.items():
            if tax_year in years:
                supported.append(state_code)
        return sorted(supported)

    @classmethod
    def is_supported(cls, state_code: str, tax_year: int) -> bool:
        """
        Check if a state is supported for a tax year.

        Args:
            state_code: Two-letter state code
            tax_year: Tax year

        Returns:
            True if state has a registered calculator for the year
        """
        state_upper = state_code.upper()

        # No income tax states are "supported" (they just return 0 tax)
        if state_upper in NO_INCOME_TAX_STATES:
            return True

        state_calcs = cls._calculators.get(state_upper)
        if not state_calcs:
            return False

        return tax_year in state_calcs

    @classmethod
    def clear(cls) -> None:
        """Clear all registered calculators. Useful for testing."""
        cls._calculators.clear()


def register_state(state_code: str, tax_year: int) -> Callable:
    """
    Decorator to register a state calculator.

    Usage:
        @register_state("CA", 2025)
        class CaliforniaCalculator(BaseStateCalculator):
            ...
    """
    def decorator(cls: Type[BaseStateCalculator]) -> Type[BaseStateCalculator]:
        StateCalculatorRegistry.register(state_code, tax_year, cls)
        return cls
    return decorator
