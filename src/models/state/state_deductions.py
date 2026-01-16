"""State-specific deduction models."""

from typing import Optional
from pydantic import BaseModel, Field


class StateDeductions(BaseModel):
    """
    State-specific deduction information.

    Different states have different deduction rules and amounts.
    This model captures state-specific deduction data that may differ
    from federal deductions.
    """

    # Standard vs itemized choice (may differ from federal)
    use_standard_deduction: bool = True

    # State-specific adjustments
    state_income_tax_deduction: float = Field(
        default=0.0,
        ge=0,
        description="State income tax paid (for states that allow deduction)"
    )

    property_tax_paid: float = Field(
        default=0.0,
        ge=0,
        description="Property taxes paid (some states have different limits)"
    )

    # Rent paid (for states with renter credits/deductions)
    rent_paid: float = Field(
        default=0.0,
        ge=0,
        description="Annual rent paid (for renter credits)"
    )

    # Income exclusions
    pension_income_exclusion: float = Field(
        default=0.0,
        ge=0,
        description="Pension/retirement income exclusion amount"
    )

    social_security_exclusion: float = Field(
        default=0.0,
        ge=0,
        description="Social Security benefits exclusion"
    )

    military_pay_exclusion: float = Field(
        default=0.0,
        ge=0,
        description="Military pay exclusion for states that exempt it"
    )

    # 529 plan contributions (state deductible in many states)
    education_savings_contribution: float = Field(
        default=0.0,
        ge=0,
        description="529 plan contributions (deductible in many states)"
    )

    # Health savings account (some states don't follow federal treatment)
    hsa_contribution_addback: float = Field(
        default=0.0,
        ge=0,
        description="HSA contribution addback (for states like CA, NJ)"
    )

    def get_total_state_subtractions(self) -> float:
        """Calculate total state income subtractions."""
        return (
            self.pension_income_exclusion +
            self.social_security_exclusion +
            self.military_pay_exclusion +
            self.education_savings_contribution
        )

    def get_total_state_additions(self) -> float:
        """Calculate total state income additions."""
        return self.hsa_contribution_addback
