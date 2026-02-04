"""
Schedule E (Form 1040) - Supplemental Income and Loss

IRS Form for reporting:
- Part I: Rental real estate, royalties, partnerships, S corps, estates, trusts
- Part II: Income/loss from partnerships and S corporations (K-1)
- Part III: Income/loss from estates and trusts (K-1)
- Part IV: Income/loss from REMICs

Key Rules:
- Rental losses may be limited by passive activity rules (Form 8582)
- Active participation allows up to $25,000 rental loss deduction
- Real estate professionals not subject to passive loss limitations
- At-risk rules may further limit losses
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class PropertyType(str, Enum):
    """Type of rental property."""
    SINGLE_FAMILY = "single_family"
    MULTI_FAMILY = "multi_family"
    VACATION_SHORT_TERM = "vacation_short_term"
    COMMERCIAL = "commercial"
    LAND = "land"
    ROYALTY = "royalty"
    OTHER = "other"


class RentalProperty(BaseModel):
    """Information about a rental property."""
    property_address: str = Field(description="Property address")
    property_type: PropertyType = Field(
        default=PropertyType.SINGLE_FAMILY,
        description="Type of rental property"
    )
    fair_rental_days: int = Field(
        default=365, ge=0,
        description="Number of days property was rented at fair rental price"
    )
    personal_use_days: int = Field(
        default=0, ge=0,
        description="Number of days property was used personally"
    )
    qbi_eligible: bool = Field(
        default=True,
        description="Whether rental qualifies for QBI deduction"
    )

    # Income
    rents_received: float = Field(default=0.0, ge=0, description="Rents received")
    royalties_received: float = Field(default=0.0, ge=0, description="Royalties received")

    # Expenses
    advertising: float = Field(default=0.0, ge=0)
    auto_travel: float = Field(default=0.0, ge=0)
    cleaning_maintenance: float = Field(default=0.0, ge=0)
    commissions: float = Field(default=0.0, ge=0)
    insurance: float = Field(default=0.0, ge=0)
    legal_professional: float = Field(default=0.0, ge=0)
    management_fees: float = Field(default=0.0, ge=0)
    mortgage_interest: float = Field(default=0.0, ge=0)
    other_interest: float = Field(default=0.0, ge=0)
    repairs: float = Field(default=0.0, ge=0)
    supplies: float = Field(default=0.0, ge=0)
    taxes: float = Field(default=0.0, ge=0)
    utilities: float = Field(default=0.0, ge=0)
    depreciation: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)

    def total_income(self) -> float:
        """Calculate total income from this property."""
        return self.rents_received + self.royalties_received

    def total_expenses(self) -> float:
        """Calculate total expenses for this property."""
        return (
            self.advertising +
            self.auto_travel +
            self.cleaning_maintenance +
            self.commissions +
            self.insurance +
            self.legal_professional +
            self.management_fees +
            self.mortgage_interest +
            self.other_interest +
            self.repairs +
            self.supplies +
            self.taxes +
            self.utilities +
            self.depreciation +
            self.other_expenses
        )

    def net_income_loss(self) -> float:
        """Calculate net income or loss for this property."""
        return self.total_income() - self.total_expenses()


class PartnershipSCorpK1(BaseModel):
    """K-1 income from partnership or S corporation."""
    entity_name: str = Field(description="Name of partnership or S corporation")
    ein: str = Field(default="", description="Entity EIN")
    is_s_corp: bool = Field(
        default=False,
        description="True if S corporation, False if partnership"
    )
    is_passive: bool = Field(
        default=True,
        description="Whether activity is passive for this taxpayer"
    )
    ownership_percent: float = Field(
        default=0.0, ge=0, le=100,
        description="Ownership percentage"
    )

    # K-1 Box amounts
    ordinary_income_loss: float = Field(default=0.0, description="Box 1/2: Ordinary income/loss")
    net_rental_income_loss: float = Field(default=0.0, description="Box 2/3: Net rental RE income/loss")
    other_rental_income_loss: float = Field(default=0.0, description="Other rental income/loss")
    guaranteed_payments: float = Field(default=0.0, ge=0, description="Box 4: Guaranteed payments")
    interest_income: float = Field(default=0.0, ge=0, description="Interest income")
    ordinary_dividends: float = Field(default=0.0, ge=0, description="Ordinary dividends")
    qualified_dividends: float = Field(default=0.0, ge=0, description="Qualified dividends")
    royalties: float = Field(default=0.0, ge=0, description="Royalties")
    net_short_term_gain: float = Field(default=0.0, description="Net ST capital gain/loss")
    net_long_term_gain: float = Field(default=0.0, description="Net LT capital gain/loss")
    section_1231_gain: float = Field(default=0.0, description="Net Section 1231 gain/loss")
    other_income_loss: float = Field(default=0.0, description="Other income/loss")

    # Credits and other items
    section_179_deduction: float = Field(default=0.0, ge=0, description="Section 179 deduction")
    foreign_taxes_paid: float = Field(default=0.0, ge=0, description="Foreign taxes paid")
    self_employment_income: float = Field(default=0.0, description="SE income (partners only)")

    # QBI information
    qbi_income: float = Field(default=0.0, description="Qualified business income")
    w2_wages: float = Field(default=0.0, ge=0, description="W-2 wages for QBI")
    ubia: float = Field(default=0.0, ge=0, description="UBIA for QBI")


class EstateTrustK1(BaseModel):
    """K-1 income from estate or trust."""
    entity_name: str = Field(description="Name of estate or trust")
    ein: str = Field(default="", description="Entity EIN")
    is_estate: bool = Field(
        default=False,
        description="True if estate, False if trust"
    )

    # K-1 amounts (Form 1041 Schedule K-1)
    interest_income: float = Field(default=0.0, ge=0, description="Interest income")
    ordinary_dividends: float = Field(default=0.0, ge=0, description="Ordinary dividends")
    qualified_dividends: float = Field(default=0.0, ge=0, description="Qualified dividends")
    net_short_term_gain: float = Field(default=0.0, description="Net ST capital gain")
    net_long_term_gain: float = Field(default=0.0, description="Net LT capital gain")
    other_portfolio_income: float = Field(default=0.0, description="Other portfolio income")
    ordinary_business_income: float = Field(default=0.0, description="Ordinary business income")
    net_rental_income: float = Field(default=0.0, description="Net rental RE income")
    other_rental_income: float = Field(default=0.0, description="Other rental income")
    directly_apportioned_deductions: float = Field(default=0.0, ge=0)
    estate_tax_deduction: float = Field(default=0.0, ge=0, description="IRD estate tax deduction")


class ScheduleE(BaseModel):
    """
    Schedule E (Form 1040) - Supplemental Income and Loss

    Complete model for IRS Schedule E with all parts.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Part I: Rental Real Estate and Royalties
    rental_properties: List[RentalProperty] = Field(
        default_factory=list,
        description="List of rental properties"
    )
    is_active_participant: bool = Field(
        default=False,
        description="Active participant in rental activities"
    )
    is_real_estate_professional: bool = Field(
        default=False,
        description="Qualifies as real estate professional"
    )

    # Part II: Partnerships and S Corporations
    partnership_scorp_k1s: List[PartnershipSCorpK1] = Field(
        default_factory=list,
        description="K-1s from partnerships and S corporations"
    )

    # Part III: Estates and Trusts
    estate_trust_k1s: List[EstateTrustK1] = Field(
        default_factory=list,
        description="K-1s from estates and trusts"
    )

    # Part IV: REMICs
    remic_income: float = Field(
        default=0.0,
        description="Taxable income/loss from REMICs"
    )

    # Passive loss carryover
    prior_year_passive_loss: float = Field(
        default=0.0, ge=0,
        description="Suspended passive losses from prior years"
    )

    # Configuration
    agi_for_pal: float = Field(
        default=0.0, ge=0,
        description="AGI for passive activity loss allowance calculation"
    )
    PAL_ALLOWANCE: float = 25000.0  # $25,000 rental loss allowance
    PAL_PHASEOUT_START: float = 100000.0  # AGI where phaseout begins
    PAL_PHASEOUT_END: float = 150000.0  # AGI where allowance is zero

    def calculate_part_i_rentals(self) -> Dict[str, Any]:
        """
        Calculate Part I - Rental Real Estate and Royalties.

        Returns income, expenses, and net from all rental properties.
        """
        total_income = 0.0
        total_expenses = 0.0
        total_depreciation = 0.0

        property_details = []
        for prop in self.rental_properties:
            income = prop.total_income()
            expenses = prop.total_expenses()
            net = prop.net_income_loss()

            total_income += income
            total_expenses += expenses
            total_depreciation += prop.depreciation

            property_details.append({
                'address': prop.property_address,
                'type': prop.property_type.value,
                'fair_rental_days': prop.fair_rental_days,
                'personal_use_days': prop.personal_use_days,
                'income': float(money(income)),
                'expenses': float(money(expenses)),
                'depreciation': float(money(prop.depreciation)),
                'net': float(money(net)),
            })

        net_rental = total_income - total_expenses

        # Apply passive loss limitations if loss
        allowed_loss = net_rental
        suspended_loss = 0.0

        if net_rental < 0 and not self.is_real_estate_professional:
            # Calculate allowed rental loss
            if self.is_active_participant:
                # $25,000 allowance, phased out at AGI $100k-$150k
                if self.agi_for_pal <= self.PAL_PHASEOUT_START:
                    allowance = self.PAL_ALLOWANCE
                elif self.agi_for_pal >= self.PAL_PHASEOUT_END:
                    allowance = 0.0
                else:
                    reduction = (self.agi_for_pal - self.PAL_PHASEOUT_START) * 0.50
                    allowance = max(0, self.PAL_ALLOWANCE - reduction)

                # Include prior year suspended losses
                total_loss = abs(net_rental) + self.prior_year_passive_loss
                allowed_loss = -min(total_loss, allowance)
                suspended_loss = total_loss - abs(allowed_loss)
            else:
                # No active participation - all losses suspended
                allowed_loss = 0.0
                suspended_loss = abs(net_rental) + self.prior_year_passive_loss

        return {
            'property_count': len(self.rental_properties),
            'properties': property_details,
            'total_income': float(money(total_income)),
            'total_expenses': float(money(total_expenses)),
            'total_depreciation': float(money(total_depreciation)),
            'net_rental_before_pal': float(money(net_rental)),
            'is_active_participant': self.is_active_participant,
            'is_real_estate_professional': self.is_real_estate_professional,
            'pal_allowance_used': float(money(abs(allowed_loss))) if allowed_loss < 0 else 0.0,
            'allowed_rental_income_loss': float(money(allowed_loss)),
            'suspended_passive_loss': float(money(suspended_loss)),
        }

    def calculate_part_ii_partnerships(self) -> Dict[str, Any]:
        """
        Calculate Part II - Income from Partnerships and S Corporations.
        """
        total_passive_income = 0.0
        total_passive_loss = 0.0
        total_nonpassive_income = 0.0
        total_nonpassive_loss = 0.0
        total_se_income = 0.0
        total_qbi = 0.0

        k1_details = []
        for k1 in self.partnership_scorp_k1s:
            ordinary = k1.ordinary_income_loss + k1.guaranteed_payments
            rental = k1.net_rental_income_loss + k1.other_rental_income_loss
            total_from_entity = ordinary + rental + k1.other_income_loss

            if k1.is_passive:
                if total_from_entity >= 0:
                    total_passive_income += total_from_entity
                else:
                    total_passive_loss += abs(total_from_entity)
            else:
                if total_from_entity >= 0:
                    total_nonpassive_income += total_from_entity
                else:
                    total_nonpassive_loss += abs(total_from_entity)

            total_se_income += k1.self_employment_income
            total_qbi += k1.qbi_income

            k1_details.append({
                'name': k1.entity_name,
                'type': 'S Corporation' if k1.is_s_corp else 'Partnership',
                'passive': k1.is_passive,
                'ordinary': k1.ordinary_income_loss,
                'guaranteed': k1.guaranteed_payments,
                'rental': rental,
                'total': float(money(total_from_entity)),
                'se_income': k1.self_employment_income,
                'qbi': k1.qbi_income,
            })

        net_passive = total_passive_income - total_passive_loss
        net_nonpassive = total_nonpassive_income - total_nonpassive_loss

        return {
            'k1_count': len(self.partnership_scorp_k1s),
            'k1s': k1_details,
            'total_passive_income': float(money(total_passive_income)),
            'total_passive_loss': float(money(total_passive_loss)),
            'net_passive': float(money(net_passive)),
            'total_nonpassive_income': float(money(total_nonpassive_income)),
            'total_nonpassive_loss': float(money(total_nonpassive_loss)),
            'net_nonpassive': float(money(net_nonpassive)),
            'total_self_employment': float(money(total_se_income)),
            'total_qbi': float(money(total_qbi)),
        }

    def calculate_part_iii_estates_trusts(self) -> Dict[str, Any]:
        """
        Calculate Part III - Income from Estates and Trusts.
        """
        total_income = 0.0
        total_loss = 0.0

        k1_details = []
        for k1 in self.estate_trust_k1s:
            total_from_entity = (
                k1.interest_income +
                k1.ordinary_dividends +
                k1.net_short_term_gain +
                k1.net_long_term_gain +
                k1.other_portfolio_income +
                k1.ordinary_business_income +
                k1.net_rental_income +
                k1.other_rental_income -
                k1.directly_apportioned_deductions -
                k1.estate_tax_deduction
            )

            if total_from_entity >= 0:
                total_income += total_from_entity
            else:
                total_loss += abs(total_from_entity)

            k1_details.append({
                'name': k1.entity_name,
                'type': 'Estate' if k1.is_estate else 'Trust',
                'interest': k1.interest_income,
                'dividends': k1.ordinary_dividends,
                'capital_gains': k1.net_short_term_gain + k1.net_long_term_gain,
                'total': float(money(total_from_entity)),
            })

        return {
            'k1_count': len(self.estate_trust_k1s),
            'k1s': k1_details,
            'total_income': float(money(total_income)),
            'total_loss': float(money(total_loss)),
            'net_income_loss': float(money(total_income - total_loss)),
        }

    def calculate_schedule_e(self) -> Dict[str, Any]:
        """
        Calculate complete Schedule E with all parts.
        """
        part_i = self.calculate_part_i_rentals()
        part_ii = self.calculate_part_ii_partnerships()
        part_iii = self.calculate_part_iii_estates_trusts()

        # Total supplemental income/loss
        total_schedule_e = (
            part_i['allowed_rental_income_loss'] +
            part_ii['net_passive'] +
            part_ii['net_nonpassive'] +
            part_iii['net_income_loss'] +
            self.remic_income
        )

        return {
            'tax_year': self.tax_year,

            # Part totals
            'part_i_rental_total': part_i['allowed_rental_income_loss'],
            'part_ii_partnership_total': part_ii['net_passive'] + part_ii['net_nonpassive'],
            'part_iii_estate_trust_total': part_iii['net_income_loss'],
            'part_iv_remic_total': self.remic_income,

            # Combined total
            'total_supplemental_income': float(money(total_schedule_e)),

            # Self-employment (flows to Schedule SE)
            'self_employment_income': part_ii['total_self_employment'],

            # QBI (flows to Form 8995)
            'total_qbi': part_ii['total_qbi'],

            # Passive loss tracking
            'suspended_passive_loss': part_i['suspended_passive_loss'],

            # Detailed breakdowns
            'part_i': part_i,
            'part_ii': part_ii,
            'part_iii': part_iii,
        }

    def get_schedule_e_summary(self) -> Dict[str, float]:
        """Get a concise summary of Schedule E."""
        result = self.calculate_schedule_e()
        return {
            'rental_income_loss': result['part_i_rental_total'],
            'partnership_income_loss': result['part_ii_partnership_total'],
            'estate_trust_income_loss': result['part_iii_estate_trust_total'],
            'total_supplemental': result['total_supplemental_income'],
            'self_employment': result['self_employment_income'],
        }


def create_schedule_e(
    rental_income: float = 0.0,
    rental_expenses: float = 0.0,
    rental_depreciation: float = 0.0,
    partnership_income: float = 0.0,
    s_corp_income: float = 0.0,
    is_active_participant: bool = True,
    agi: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to calculate Schedule E.

    Args:
        rental_income: Total rental income
        rental_expenses: Total rental expenses (excluding depreciation)
        rental_depreciation: Depreciation expense
        partnership_income: Income/loss from partnerships
        s_corp_income: Income/loss from S corporations
        is_active_participant: Active participant in rental activities
        agi: AGI for passive loss calculation

    Returns:
        Dictionary with Schedule E calculation results
    """
    properties = []
    if rental_income > 0 or rental_expenses > 0:
        properties.append(RentalProperty(
            property_address="Rental Property",
            rents_received=rental_income,
            repairs=rental_expenses * 0.3,  # Approximate allocation
            insurance=rental_expenses * 0.1,
            taxes=rental_expenses * 0.2,
            mortgage_interest=rental_expenses * 0.3,
            other_expenses=rental_expenses * 0.1,
            depreciation=rental_depreciation,
        ))

    k1s = []
    if partnership_income != 0:
        k1s.append(PartnershipSCorpK1(
            entity_name="Partnership",
            is_s_corp=False,
            ordinary_income_loss=partnership_income,
            is_passive=True,
        ))
    if s_corp_income != 0:
        k1s.append(PartnershipSCorpK1(
            entity_name="S Corporation",
            is_s_corp=True,
            ordinary_income_loss=s_corp_income,
            is_passive=True,
        ))

    schedule_e = ScheduleE(
        rental_properties=properties,
        partnership_scorp_k1s=k1s,
        is_active_participant=is_active_participant,
        agi_for_pal=agi,
    )

    return schedule_e.calculate_schedule_e()
