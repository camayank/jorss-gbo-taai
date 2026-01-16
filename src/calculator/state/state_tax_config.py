"""State tax configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# Type alias for bracket tables: filing_status -> [(threshold, rate), ...]
StateBracketTable = Dict[str, List[Tuple[float, float]]]


@dataclass(frozen=True)
class StateTaxConfig:
    """
    Configuration for a specific state and tax year.

    This dataclass holds all the static data needed to calculate state income tax,
    including brackets, deductions, exemptions, and state-specific rules.
    """

    # Basic identification
    state_code: str
    state_name: str
    tax_year: int

    # Tax structure
    is_flat_tax: bool
    flat_rate: Optional[float] = None  # If is_flat_tax is True
    brackets: Optional[StateBracketTable] = None  # If progressive

    # Starting point for taxable income calculation
    # "federal_agi" - most common
    # "federal_taxable_income" - MN, OR, VT, etc.
    # "gross_income" - NJ
    starts_from: str = "federal_agi"

    # Standard deduction amounts by filing status
    standard_deduction: Dict[str, float] = field(default_factory=dict)

    # Personal exemption amounts
    personal_exemption_amount: Dict[str, float] = field(default_factory=dict)
    dependent_exemption_amount: float = 0.0

    # State-specific income rules
    allows_federal_tax_deduction: bool = False
    social_security_taxable: bool = False
    pension_exclusion_limit: Optional[float] = None
    military_pay_exempt: bool = False

    # State EITC (as percentage of federal EITC, e.g., 0.30 = 30%)
    eitc_percentage: Optional[float] = None

    # State child tax credit
    child_tax_credit_amount: float = 0.0

    # Local tax support (NYC, etc.)
    has_local_tax: bool = False
    local_tax_brackets: Optional[StateBracketTable] = None

    # Additional state-specific credits
    renter_credit_single: float = 0.0
    renter_credit_joint: float = 0.0
    renter_credit_income_limit: Optional[float] = None

    def get_standard_deduction(self, filing_status: str) -> float:
        """Get standard deduction for a filing status."""
        return self.standard_deduction.get(filing_status, 0.0)

    def get_personal_exemption(self, filing_status: str) -> float:
        """Get personal exemption amount for a filing status."""
        return self.personal_exemption_amount.get(filing_status, 0.0)

    def get_brackets(self, filing_status: str) -> List[Tuple[float, float]]:
        """Get tax brackets for a filing status."""
        if self.is_flat_tax:
            return [(0, self.flat_rate or 0.0)]
        if self.brackets:
            return self.brackets.get(filing_status, self.brackets.get("single", []))
        return []
