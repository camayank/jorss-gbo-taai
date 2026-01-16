"""State-specific tax credits."""

from typing import Optional
from pydantic import BaseModel, Field


class StateCredits(BaseModel):
    """
    State-specific tax credits.

    Many states offer their own tax credits that reduce state tax liability.
    This model captures state-specific credit amounts.
    """

    # State EITC (calculated from federal)
    state_eitc: float = Field(
        default=0.0,
        ge=0,
        description="State Earned Income Tax Credit"
    )

    # State child tax credit
    state_child_tax_credit: float = Field(
        default=0.0,
        ge=0,
        description="State child tax credit"
    )

    # State child and dependent care credit
    state_child_care_credit: float = Field(
        default=0.0,
        ge=0,
        description="State child and dependent care credit"
    )

    # Property tax credit
    property_tax_credit: float = Field(
        default=0.0,
        ge=0,
        description="Property tax credit (some states offer)"
    )

    # Renter's credit
    renters_credit: float = Field(
        default=0.0,
        ge=0,
        description="Renter's credit (CA, MN, etc.)"
    )

    # Education credits
    education_credit: float = Field(
        default=0.0,
        ge=0,
        description="State education tax credit"
    )

    # Elderly/disabled credit
    elderly_disabled_credit: float = Field(
        default=0.0,
        ge=0,
        description="Credit for elderly or disabled"
    )

    # Working families credit
    working_families_credit: float = Field(
        default=0.0,
        ge=0,
        description="Working families tax credit"
    )

    # Energy/environmental credits
    energy_credit: float = Field(
        default=0.0,
        ge=0,
        description="State energy efficiency credit"
    )

    # Other state credits
    other_credits: float = Field(
        default=0.0,
        ge=0,
        description="Other state-specific credits"
    )

    other_credits_description: Optional[str] = Field(
        default=None,
        description="Description of other credits"
    )

    def get_total_state_credits(self) -> float:
        """Calculate total state tax credits."""
        return (
            self.state_eitc +
            self.state_child_tax_credit +
            self.state_child_care_credit +
            self.property_tax_credit +
            self.renters_credit +
            self.education_credit +
            self.elderly_disabled_credit +
            self.working_families_credit +
            self.energy_credit +
            self.other_credits
        )
