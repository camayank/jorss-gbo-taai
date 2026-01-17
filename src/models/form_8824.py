"""
Form 8824 - Like-Kind Exchanges (Section 1031)

Complete IRS Form 8824 implementation for like-kind exchanges:

Part I: Information on the Like-Kind Exchange
- Identification of property given up and received
- Exchange dates and timelines

Part II: Related Party Exchange Information
- Identification of related parties
- Disposition rules

Part III: Realized Gain or (Loss), Recognized Gain, and Basis of Like-Kind Property Received
- FMV of property received
- Boot received/given
- Basis calculations
- Gain/loss recognition

Key Section 1031 Rules:
- Must be "like-kind" property (real property for real property post-2017)
- 45-day identification period
- 180-day exchange completion period
- Boot (cash/non-like-kind property) triggers recognition
- Related party restrictions (2-year holding period)

Tax Cuts and Jobs Act (2017) Changes:
- After 2017, only REAL PROPERTY qualifies for like-kind treatment
- Personal property (vehicles, equipment) NO LONGER qualifies
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, field_validator
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


class PropertyType(str, Enum):
    """Type of property exchanged."""
    REAL_PROPERTY = "real_property"  # Real estate (post-2017 only type allowed)
    PERSONAL_PROPERTY = "personal_property"  # Pre-2018 exchanges only
    MIXED = "mixed"  # Both real and personal


class ExchangeType(str, Enum):
    """Type of like-kind exchange."""
    SIMULTANEOUS = "simultaneous"  # Same-day exchange
    DEFERRED = "deferred"  # Starker exchange (45/180 day rules)
    REVERSE = "reverse"  # Receive replacement before relinquishing
    IMPROVEMENT = "improvement"  # Build-to-suit exchange


class RelatedPartyType(str, Enum):
    """Types of related parties under Section 267."""
    NONE = "none"
    FAMILY = "family"  # Siblings, spouse, ancestors, descendants
    CONTROLLED_ENTITY = "controlled_entity"  # >50% ownership
    TRUST_BENEFICIARY = "trust_beneficiary"
    PARTNERSHIP_PARTNER = "partnership_partner"


class Form8824Part1(BaseModel):
    """
    Form 8824 Part I: Information on the Like-Kind Exchange

    Details about the exchange including dates and property descriptions.
    """
    # Line 1: Description of like-kind property given up
    line_1_property_given_description: str = Field(
        default="",
        description="Line 1: Description of property given up"
    )

    # Line 2: Description of like-kind property received
    line_2_property_received_description: str = Field(
        default="",
        description="Line 2: Description of property received"
    )

    # Line 3: Date like-kind property given up was originally acquired
    line_3_date_acquired: Optional[date] = Field(
        default=None,
        description="Line 3: Date property given up was acquired"
    )

    # Line 4: Date property was transferred (gave up)
    line_4_date_transferred: Optional[date] = Field(
        default=None,
        description="Line 4: Date you transferred property"
    )

    # Line 5: Date replacement property identified
    line_5_date_identified: Optional[date] = Field(
        default=None,
        description="Line 5: Date replacement property identified"
    )

    # Line 6: Date replacement property received
    line_6_date_received: Optional[date] = Field(
        default=None,
        description="Line 6: Date replacement property received"
    )

    @computed_field
    @property
    def days_to_identify(self) -> Optional[int]:
        """Days from transfer to identification (must be <= 45)."""
        if self.line_4_date_transferred and self.line_5_date_identified:
            delta = self.line_5_date_identified - self.line_4_date_transferred
            return delta.days
        return None

    @computed_field
    @property
    def days_to_complete(self) -> Optional[int]:
        """Days from transfer to receipt (must be <= 180)."""
        if self.line_4_date_transferred and self.line_6_date_received:
            delta = self.line_6_date_received - self.line_4_date_transferred
            return delta.days
        return None

    @computed_field
    @property
    def identification_period_met(self) -> bool:
        """Check if 45-day identification period was met."""
        days = self.days_to_identify
        return days is not None and days <= 45

    @computed_field
    @property
    def exchange_period_met(self) -> bool:
        """Check if 180-day exchange period was met."""
        days = self.days_to_complete
        return days is not None and days <= 180

    @computed_field
    @property
    def valid_exchange_timeline(self) -> bool:
        """Check if entire exchange timeline is valid."""
        return self.identification_period_met and self.exchange_period_met


class Form8824Part2(BaseModel):
    """
    Form 8824 Part II: Related Party Exchange Information

    Must report if exchange is with a related party.
    Related party cannot dispose of property for 2 years.
    """
    # Line 7: Related party name
    line_7_related_party_name: str = Field(
        default="",
        description="Line 7: Name of related party"
    )

    # Line 8: Related party relationship
    line_8_relationship: RelatedPartyType = Field(
        default=RelatedPartyType.NONE,
        description="Line 8: Relationship to related party"
    )

    # Line 9: Related party TIN
    line_9_related_party_tin: str = Field(
        default="",
        description="Line 9: Related party TIN/SSN"
    )

    # Line 10: During this tax year, did the related party sell/dispose of the property?
    line_10_property_disposed: bool = Field(
        default=False,
        description="Line 10: Was property disposed by related party?"
    )

    # Line 11: During this tax year, did you sell/dispose of the property received?
    line_11_you_disposed: bool = Field(
        default=False,
        description="Line 11: Did you dispose of property received?"
    )

    @computed_field
    @property
    def is_related_party_exchange(self) -> bool:
        """Check if this is a related party exchange."""
        return self.line_8_relationship != RelatedPartyType.NONE

    @computed_field
    @property
    def gain_triggered_by_disposition(self) -> bool:
        """Check if disposition within 2 years triggers gain recognition."""
        return self.line_10_property_disposed or self.line_11_you_disposed


class Form8824Part3(BaseModel):
    """
    Form 8824 Part III: Realized Gain, Recognized Gain, and Basis

    Core calculation section for like-kind exchange taxation.
    """
    # Line 12: Fair market value of other property given up
    line_12_fmv_other_property_given: float = Field(
        default=0.0, ge=0,
        description="Line 12: FMV of other (non-like-kind) property given"
    )

    # Line 13: Adjusted basis of other property given up
    line_13_basis_other_property_given: float = Field(
        default=0.0, ge=0,
        description="Line 13: Adjusted basis of other property given"
    )

    # Line 14: Gain or loss from other property (Line 12 - Line 13)
    @computed_field
    @property
    def line_14_gain_loss_other_property(self) -> float:
        """Line 14: Gain/loss on other property given."""
        return self.line_12_fmv_other_property_given - self.line_13_basis_other_property_given

    # Line 15: Cash received, net of exchange expenses
    line_15_cash_received: float = Field(
        default=0.0, ge=0,
        description="Line 15: Cash received (boot)"
    )

    # Line 16: FMV of other property received
    line_16_fmv_other_property_received: float = Field(
        default=0.0, ge=0,
        description="Line 16: FMV of other property received (boot)"
    )

    # Line 17: Total boot received (Line 15 + Line 16)
    @computed_field
    @property
    def line_17_total_boot_received(self) -> float:
        """Line 17: Total boot received."""
        return self.line_15_cash_received + self.line_16_fmv_other_property_received

    # Line 18: FMV of like-kind property received
    line_18_fmv_like_kind_received: float = Field(
        default=0.0, ge=0,
        description="Line 18: FMV of like-kind property received"
    )

    # Line 19: Adjusted basis of like-kind property given up
    line_19_basis_like_kind_given: float = Field(
        default=0.0, ge=0,
        description="Line 19: Adjusted basis of like-kind property given"
    )

    # Line 20: Liabilities assumed by other party
    line_20_liabilities_assumed_by_other: float = Field(
        default=0.0, ge=0,
        description="Line 20: Liabilities other party assumed"
    )

    # Line 21: Total liabilities transferred (from Line 19 col b)
    # Note: In IRS form, this includes liabilities you were relieved of
    @computed_field
    @property
    def line_21_total_consideration_given(self) -> float:
        """Line 21: Basis + liabilities transferred."""
        return self.line_19_basis_like_kind_given + self.line_20_liabilities_assumed_by_other

    # Line 22: Liabilities you assumed
    line_22_liabilities_you_assumed: float = Field(
        default=0.0, ge=0,
        description="Line 22: Liabilities you assumed"
    )

    # Line 23: Net liabilities (Line 20 - Line 22, if positive)
    @computed_field
    @property
    def line_23_net_boot_from_liabilities(self) -> float:
        """Line 23: Net boot from liabilities (if relieved of more than assumed)."""
        return max(0, self.line_20_liabilities_assumed_by_other - self.line_22_liabilities_you_assumed)

    # Line 24: Total boot received (Line 17 + Line 23)
    @computed_field
    @property
    def line_24_total_boot(self) -> float:
        """Line 24: Total boot received (cash + property + net liabilities)."""
        return self.line_17_total_boot_received + self.line_23_net_boot_from_liabilities

    # Realized Gain Calculation
    # Line 25: FMV of like-kind property received + boot received
    @computed_field
    @property
    def line_25_total_received(self) -> float:
        """Line 25: Total value received."""
        return self.line_18_fmv_like_kind_received + self.line_24_total_boot

    # Line 26: Adjusted basis of like-kind property given + other property basis + cash paid
    line_26_cash_paid: float = Field(
        default=0.0, ge=0,
        description="Cash paid (boot given)"
    )

    @computed_field
    @property
    def line_26_total_given(self) -> float:
        """Line 26: Total value given up."""
        return (
            self.line_19_basis_like_kind_given +
            self.line_13_basis_other_property_given +
            self.line_26_cash_paid +
            self.line_22_liabilities_you_assumed
        )

    # Line 27: Realized Gain (Line 25 - Line 26, if positive)
    @computed_field
    @property
    def line_27_realized_gain(self) -> float:
        """Line 27: Realized gain (economic gain from exchange)."""
        gain = self.line_25_total_received - self.line_26_total_given
        return max(0, gain)

    # Line 28: Realized Loss (Line 26 - Line 25, if positive)
    @computed_field
    @property
    def line_28_realized_loss(self) -> float:
        """Line 28: Realized loss (not recognized in like-kind exchange)."""
        loss = self.line_26_total_given - self.line_25_total_received
        return max(0, loss)

    # Line 29: Recognized Gain (smaller of Line 24 or Line 27)
    @computed_field
    @property
    def line_29_recognized_gain(self) -> float:
        """Line 29: Recognized gain (taxable portion, limited to boot)."""
        return min(self.line_24_total_boot, self.line_27_realized_gain)

    # Basis Calculation for Property Received
    @computed_field
    @property
    def basis_of_like_kind_property_received(self) -> float:
        """
        Calculate basis of like-kind property received.

        Formula:
        Basis = FMV of received - Deferred gain
        OR equivalently:
        Basis = Basis of property given + boot paid - boot received + recognized gain
        """
        deferred_gain = self.line_27_realized_gain - self.line_29_recognized_gain
        return self.line_18_fmv_like_kind_received - deferred_gain


class Form8824(BaseModel):
    """
    Form 8824 - Like-Kind Exchanges (Section 1031)

    Complete implementation of IRS Form 8824 for reporting like-kind exchanges.

    A like-kind exchange allows deferral of gain when exchanging property
    held for investment or business use for similar property.

    Post-2017: Only real property qualifies for like-kind treatment.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Exchange type
    exchange_type: ExchangeType = Field(
        default=ExchangeType.DEFERRED,
        description="Type of like-kind exchange"
    )

    # Property type
    property_type: PropertyType = Field(
        default=PropertyType.REAL_PROPERTY,
        description="Type of property exchanged"
    )

    # Part I: Exchange Information
    part_1: Form8824Part1 = Field(
        default_factory=Form8824Part1,
        description="Part I: Exchange information"
    )

    # Part II: Related Party Information
    part_2: Form8824Part2 = Field(
        default_factory=Form8824Part2,
        description="Part II: Related party information"
    )

    # Part III: Gain/Loss and Basis Calculation
    part_3: Form8824Part3 = Field(
        default_factory=Form8824Part3,
        description="Part III: Gain/loss calculations"
    )

    @field_validator('property_type')
    @classmethod
    def validate_property_type(cls, v, info):
        """Validate property type based on tax year."""
        # After 2017, only real property qualifies
        tax_year = info.data.get('tax_year', 2025)
        if tax_year > 2017 and v == PropertyType.PERSONAL_PROPERTY:
            raise ValueError(
                "Personal property does not qualify for like-kind exchange after 2017"
            )
        return v

    @computed_field
    @property
    def realized_gain(self) -> float:
        """Total realized gain from the exchange."""
        return self.part_3.line_27_realized_gain

    @computed_field
    @property
    def realized_loss(self) -> float:
        """Total realized loss (not deductible in like-kind exchange)."""
        return self.part_3.line_28_realized_loss

    @computed_field
    @property
    def recognized_gain(self) -> float:
        """Taxable gain (limited to boot received)."""
        return self.part_3.line_29_recognized_gain

    @computed_field
    @property
    def deferred_gain(self) -> float:
        """Gain deferred through like-kind exchange."""
        return self.realized_gain - self.recognized_gain

    @computed_field
    @property
    def new_property_basis(self) -> float:
        """Basis in the like-kind property received."""
        return self.part_3.basis_of_like_kind_property_received

    @computed_field
    @property
    def total_boot_received(self) -> float:
        """Total boot (non-like-kind consideration) received."""
        return self.part_3.line_24_total_boot

    def is_valid_exchange(self) -> bool:
        """
        Check if the exchange qualifies for like-kind treatment.

        Requirements:
        1. Both properties must be like-kind (real for real post-2017)
        2. 45-day identification period must be met (deferred exchanges)
        3. 180-day exchange period must be met (deferred exchanges)
        4. Property must be held for business/investment use
        """
        if self.exchange_type == ExchangeType.SIMULTANEOUS:
            return True
        return self.part_1.valid_exchange_timeline

    def is_related_party_compliant(self) -> bool:
        """
        Check if related party rules are satisfied.

        Related parties cannot dispose of property within 2 years
        without triggering gain recognition.
        """
        if not self.part_2.is_related_party_exchange:
            return True
        return not self.part_2.gain_triggered_by_disposition

    def calculate_character_of_gain(self) -> Dict[str, float]:
        """
        Determine character of recognized gain.

        Returns breakdown of:
        - Ordinary income (depreciation recapture)
        - Section 1231 gain (business property)
        - Capital gain (investment property)
        """
        # Note: Full implementation would need depreciation history
        # This is a simplified version
        return {
            "ordinary_income": 0.0,  # Depreciation recapture (Section 1250)
            "section_1231_gain": self.recognized_gain,
            "capital_gain": 0.0,
        }

    def to_schedule_d(self) -> Dict[str, float]:
        """Get amounts for Schedule D reporting."""
        return {
            "proceeds": self.part_3.line_25_total_received,
            "basis": self.part_3.line_26_total_given,
            "gain_recognized": self.recognized_gain,
            "gain_deferred": self.deferred_gain,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "exchange_type": self.exchange_type.value,
            "property_type": self.property_type.value,
            "exchange_info": {
                "property_given": self.part_1.line_1_property_given_description,
                "property_received": self.part_1.line_2_property_received_description,
                "valid_timeline": self.is_valid_exchange(),
                "days_to_identify": self.part_1.days_to_identify,
                "days_to_complete": self.part_1.days_to_complete,
            },
            "related_party": {
                "is_related": self.part_2.is_related_party_exchange,
                "compliant": self.is_related_party_compliant(),
            },
            "calculations": {
                "fmv_property_received": self.part_3.line_18_fmv_like_kind_received,
                "basis_property_given": self.part_3.line_19_basis_like_kind_given,
                "boot_received": self.total_boot_received,
                "realized_gain": self.realized_gain,
                "recognized_gain": self.recognized_gain,
                "deferred_gain": self.deferred_gain,
                "new_property_basis": self.new_property_basis,
            },
        }


def calculate_like_kind_exchange(
    fmv_property_received: float,
    basis_property_given: float,
    cash_received: float = 0.0,
    other_property_received_fmv: float = 0.0,
    liabilities_relieved: float = 0.0,
    liabilities_assumed: float = 0.0,
    cash_paid: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to calculate a basic like-kind exchange.

    Args:
        fmv_property_received: Fair market value of like-kind property received
        basis_property_given: Adjusted basis of property given up
        cash_received: Cash boot received
        other_property_received_fmv: FMV of non-like-kind property received
        liabilities_relieved: Mortgage/liabilities other party assumed
        liabilities_assumed: Mortgage/liabilities you assumed
        cash_paid: Cash you paid

    Returns:
        Dictionary with realized gain, recognized gain, deferred gain, and new basis
    """
    part3 = Form8824Part3(
        line_15_cash_received=cash_received,
        line_16_fmv_other_property_received=other_property_received_fmv,
        line_18_fmv_like_kind_received=fmv_property_received,
        line_19_basis_like_kind_given=basis_property_given,
        line_20_liabilities_assumed_by_other=liabilities_relieved,
        line_22_liabilities_you_assumed=liabilities_assumed,
        line_26_cash_paid=cash_paid,
    )

    form = Form8824(
        part_3=part3
    )

    return {
        "realized_gain": form.realized_gain,
        "recognized_gain": form.recognized_gain,
        "deferred_gain": form.deferred_gain,
        "boot_received": form.total_boot_received,
        "new_property_basis": form.new_property_basis,
        "is_taxable": form.recognized_gain > 0,
    }


def calculate_exchange_timeline(
    transfer_date: date,
    identification_date: Optional[date] = None,
    receipt_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Check if exchange timeline meets IRS requirements.

    Args:
        transfer_date: Date property was transferred
        identification_date: Date replacement property identified
        receipt_date: Date replacement property received

    Returns:
        Dictionary with timeline analysis
    """
    from datetime import timedelta

    result = {
        "transfer_date": transfer_date.isoformat(),
        "identification_deadline": (transfer_date + timedelta(days=45)).isoformat(),
        "exchange_deadline": (transfer_date + timedelta(days=180)).isoformat(),
    }

    if identification_date:
        days_to_id = (identification_date - transfer_date).days
        result["identification_date"] = identification_date.isoformat()
        result["days_to_identify"] = days_to_id
        result["identification_valid"] = days_to_id <= 45

    if receipt_date:
        days_to_complete = (receipt_date - transfer_date).days
        result["receipt_date"] = receipt_date.isoformat()
        result["days_to_complete"] = days_to_complete
        result["exchange_valid"] = days_to_complete <= 180

    return result
