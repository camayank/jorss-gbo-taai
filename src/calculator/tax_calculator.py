"""
Federal and State Tax Calculator for 2025 Tax Year
Calculates tax liability based on taxable income and filing status
"""
from dataclasses import asdict
from typing import Dict, Optional
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig
from calculator.state import StateTaxEngine, NO_INCOME_TAX_STATES


class TaxCalculator:
    """Calculate federal and state income tax liability"""

    def __init__(
        self,
        config: Optional[TaxYearConfig] = None,
        include_state: bool = True
    ):
        """
        Initialize the tax calculator.

        Args:
            config: Federal tax configuration. Defaults to 2025.
            include_state: Whether to calculate state taxes. Defaults to True.
        """
        self._config = config or TaxYearConfig.for_2025()
        self._federal_engine = FederalTaxEngine(config=self._config)
        self._include_state = include_state
        self._state_engine = StateTaxEngine(tax_year=self._config.tax_year) if include_state else None

    def calculate_tax(self, tax_return: TaxReturn) -> float:
        """
        Calculate federal income tax liability (ordinary income + simplified SE tax).
        For a full breakdown, use FederalTaxEngine directly.
        """
        breakdown = self._federal_engine.calculate(tax_return)
        return breakdown.total_tax

    def calculate_complete_return(self, tax_return: TaxReturn) -> TaxReturn:
        """
        Perform complete tax calculation including federal and state taxes.

        Updates the tax_return object with:
        - Federal tax liability
        - State tax liability (if applicable)
        - Combined totals
        - Refund or amount owed

        Args:
            tax_return: The tax return to calculate

        Returns:
            Updated tax_return with all calculated values
        """
        # First calculate AGI and taxable income
        tax_return.calculate()

        # Calculate federal tax liability
        federal_breakdown = self._federal_engine.calculate(tax_return)
        tax_return.tax_liability = federal_breakdown.total_tax

        # Calculate state tax if enabled and state is provided
        state_code = self._get_state_code(tax_return)
        if self._include_state and self._state_engine and state_code:
            state_result = self._calculate_state_tax(tax_return, state_code)
            if state_result:
                # Store state result
                tax_return.state_tax_result = asdict(state_result)
                tax_return.state_tax_liability = state_result.state_tax_liability
                tax_return.state_refund_or_owed = state_result.state_refund_or_owed

                # Calculate combined totals
                tax_return.combined_tax_liability = (
                    federal_breakdown.total_tax + state_result.state_tax_liability
                )
            else:
                # No income tax state or not supported
                tax_return.state_tax_liability = 0.0
                tax_return.state_refund_or_owed = tax_return.income.get_state_withholding()
                tax_return.combined_tax_liability = federal_breakdown.total_tax
        else:
            # No state calculation
            tax_return.combined_tax_liability = federal_breakdown.total_tax

        # Recalculate federal refund/owed with updated liability
        tax_return.calculate()

        # Calculate combined refund/owed
        if tax_return.refund_or_owed is not None:
            state_refund = tax_return.state_refund_or_owed or 0.0
            tax_return.combined_refund_or_owed = tax_return.refund_or_owed + state_refund

        return tax_return

    def _get_state_code(self, tax_return: TaxReturn) -> Optional[str]:
        """
        Get state code for tax calculation.

        Checks state_of_residence first, then taxpayer.state.
        """
        if tax_return.state_of_residence:
            return tax_return.state_of_residence.upper()
        if tax_return.taxpayer.state:
            return tax_return.taxpayer.state.upper()
        return None

    def _calculate_state_tax(self, tax_return: TaxReturn, state_code: str):
        """
        Calculate state tax for the given state.

        Returns None if state has no income tax or is not supported.
        """
        if not self._state_engine:
            return None

        # Check if state has income tax
        if state_code.upper() in NO_INCOME_TAX_STATES:
            return None

        return self._state_engine.calculate(tax_return, state_code)

    def is_state_supported(self, state_code: str) -> bool:
        """Check if a state is supported for tax calculation."""
        if not self._state_engine:
            return False
        return self._state_engine.is_state_supported(state_code)

    def get_supported_states(self) -> list:
        """Get list of supported state codes."""
        if not self._state_engine:
            return []
        return self._state_engine.get_supported_states()

    def has_state_income_tax(self, state_code: str) -> bool:
        """Check if a state has income tax."""
        return state_code.upper() not in NO_INCOME_TAX_STATES
