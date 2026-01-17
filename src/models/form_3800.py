"""
Form 3800 - General Business Credit

Complete IRS Form 3800 implementation for aggregating business tax credits.

The General Business Credit is the total of various business-related credits:
- Investment credit (Form 3468)
- Work opportunity credit (Form 5884)
- Research credit (Form 6765)
- Low-income housing credit (Form 8586)
- Disabled access credit (Form 8826)
- Employer credit for paid family/medical leave (Form 8994)
- Small employer health insurance credit (Form 8941)
- And many more...

Key concepts:
- Credits are limited by tax liability
- Net income tax minus greater of TMT or 25% of net regular tax > $25,000
- Unused credits can be carried back 1 year, forward 20 years
- Some credits are "specified credits" with special ordering rules

Credit ordering:
1. Carryforward credits (oldest first)
2. General business credits earned current year
3. Carryback credits

Parts of Form 3800:
- Part I: Current year credit for credits not allowed against TMT
- Part II: Allowable credit
- Part III: General business credits (detailed listing)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field
from datetime import date


class CreditType(str, Enum):
    """Types of business credits that flow to Form 3800."""
    # Investment Credits (Form 3468)
    REHABILITATION = "rehabilitation"  # Historic rehabilitation
    ENERGY = "energy"  # Energy investment credit
    QUALIFYING_ADVANCED_ENERGY = "qualifying_advanced_energy"
    QUALIFYING_GASIFICATION = "qualifying_gasification"
    QUALIFYING_ADVANCED_COAL = "qualifying_advanced_coal"

    # Employment Credits
    WORK_OPPORTUNITY = "work_opportunity"  # Form 5884
    EMPOWERMENT_ZONE = "empowerment_zone"  # Form 8844
    INDIAN_EMPLOYMENT = "indian_employment"  # Form 8845
    EMPLOYER_SOCIAL_SECURITY = "employer_social_security"  # Form 8846
    PAID_FAMILY_LEAVE = "paid_family_leave"  # Form 8994

    # Research and Development
    RESEARCH = "research"  # Form 6765
    ORPHAN_DRUG = "orphan_drug"  # Form 8820

    # Housing Credits
    LOW_INCOME_HOUSING = "low_income_housing"  # Form 8586
    NEW_MARKETS = "new_markets"  # Form 8874

    # Small Business Credits
    DISABLED_ACCESS = "disabled_access"  # Form 8826
    SMALL_EMPLOYER_PENSION = "small_employer_pension"  # Form 8881
    SMALL_EMPLOYER_HEALTH = "small_employer_health"  # Form 8941

    # Other Credits
    BIODIESEL = "biodiesel"  # Form 8864
    RENEWABLE_ELECTRICITY = "renewable_electricity"  # Form 8835
    EMPLOYER_DIFFERENTIAL_WAGE = "employer_differential_wage"  # Form 8932
    CARBON_OXIDE_SEQUESTRATION = "carbon_oxide_sequestration"  # Form 8933
    CLEAN_VEHICLE = "clean_vehicle"  # Form 8936

    # General/Other
    OTHER = "other"


class CreditSource(str, Enum):
    """Source of the credit (current year, carryforward, carryback)."""
    CURRENT_YEAR = "current_year"
    CARRYFORWARD = "carryforward"
    CARRYBACK = "carryback"


class BusinessCredit(BaseModel):
    """
    Individual business credit entry.

    Represents a single credit from a specific source form.
    """
    credit_type: CreditType = Field(
        description="Type of business credit"
    )
    source_form: str = Field(
        default="",
        description="Source form number (e.g., 'Form 6765')"
    )
    description: str = Field(
        default="",
        description="Description of credit"
    )

    # Credit amounts
    credit_amount: float = Field(
        default=0.0, ge=0,
        description="Credit amount"
    )

    # Source tracking
    credit_source: CreditSource = Field(
        default=CreditSource.CURRENT_YEAR,
        description="Source of credit"
    )

    # For carryforward/carryback
    original_year: Optional[int] = Field(
        default=None,
        description="Original year credit was generated"
    )

    # Special credit flags
    is_specified_credit: bool = Field(
        default=False,
        description="Is this a specified credit (special ordering)?"
    )

    is_eligible_small_business: bool = Field(
        default=False,
        description="Is this from an eligible small business?"
    )

    # Passive activity limitation
    is_passive: bool = Field(
        default=False,
        description="Is this a passive activity credit?"
    )
    passive_allowed: float = Field(
        default=0.0, ge=0,
        description="Passive activity credit allowed"
    )


class Form3800Part1(BaseModel):
    """
    Form 3800 Part I: Current Year Credit for Credits Not Allowed Against TMT

    Calculates credits subject to the regular tax limitation.
    """
    # Line 1: General business credit from Part III
    line_1_general_business_credit: float = Field(
        default=0.0, ge=0,
        description="Line 1: General business credit"
    )

    # Line 2: Passive activity credits from Part III
    line_2_passive_credits: float = Field(
        default=0.0, ge=0,
        description="Line 2: Passive activity credits included on line 1"
    )

    # Line 3: Line 1 minus line 2
    @computed_field
    @property
    def line_3_subtract(self) -> float:
        """Line 3: Subtract passive from total."""
        return max(0, self.line_1_general_business_credit - self.line_2_passive_credits)

    # Line 4: Passive activity credits allowed
    line_4_passive_allowed: float = Field(
        default=0.0, ge=0,
        description="Line 4: Passive activity credits allowed"
    )

    # Line 5: Carryforward of GBC to 2025
    line_5_carryforward: float = Field(
        default=0.0, ge=0,
        description="Line 5: Carryforward from prior years"
    )

    # Line 6: Carryback of GBC from 2026
    line_6_carryback: float = Field(
        default=0.0, ge=0,
        description="Line 6: Carryback from later year"
    )

    # Line 7: Add lines 3 through 6
    @computed_field
    @property
    def line_7_total(self) -> float:
        """Line 7: Total current year credit."""
        return (
            self.line_3_subtract +
            self.line_4_passive_allowed +
            self.line_5_carryforward +
            self.line_6_carryback
        )


class Form3800Part2(BaseModel):
    """
    Form 3800 Part II: Allowable Credit

    Calculates the limitation and allowable credit amount.
    """
    # Line 8: Regular tax before credits
    line_8_regular_tax: float = Field(
        default=0.0, ge=0,
        description="Line 8: Regular tax before credits"
    )

    # Line 9: Alternative minimum tax
    line_9_amt: float = Field(
        default=0.0, ge=0,
        description="Line 9: Alternative minimum tax"
    )

    # Line 10: Add lines 8 and 9
    @computed_field
    @property
    def line_10_net_income_tax(self) -> float:
        """Line 10: Net income tax (regular + AMT)."""
        return self.line_8_regular_tax + self.line_9_amt

    # Line 11: Net regular tax (Line 8 minus credits)
    line_11_net_regular_tax: float = Field(
        default=0.0, ge=0,
        description="Line 11: Net regular tax"
    )

    # Line 12: Enter 25% of line 11 over $25,000
    @computed_field
    @property
    def line_12_25_percent_excess(self) -> float:
        """Line 12: 25% of net regular tax over $25,000."""
        excess = max(0, self.line_11_net_regular_tax - 25000)
        return excess * 0.25

    # Line 13: Tentative minimum tax
    line_13_tmt: float = Field(
        default=0.0, ge=0,
        description="Line 13: Tentative minimum tax"
    )

    # Line 14: Greater of line 12 or line 13
    @computed_field
    @property
    def line_14_greater(self) -> float:
        """Line 14: Greater of 25% excess or TMT."""
        return max(self.line_12_25_percent_excess, self.line_13_tmt)

    # Line 15: Subtract line 14 from line 10
    @computed_field
    @property
    def line_15_limitation(self) -> float:
        """Line 15: Credit limitation."""
        return max(0, self.line_10_net_income_tax - self.line_14_greater)

    # Line 16: Credit from Part I Line 7
    line_16_credit_from_part1: float = Field(
        default=0.0, ge=0,
        description="Line 16: Credit from Part I"
    )

    # Line 17-35 handle specified credits (simplified here)
    line_17_specified_credits: float = Field(
        default=0.0, ge=0,
        description="Lines 17-35: Specified credits"
    )

    # Line 36: Smaller of line 15 or line 16
    @computed_field
    @property
    def line_36_allowable_credit(self) -> float:
        """Line 36: Allowable general business credit."""
        return min(self.line_15_limitation, self.line_16_credit_from_part1)


class Form3800Part3(BaseModel):
    """
    Form 3800 Part III: General Business Credits

    Detailed listing of all business credits flowing to Form 3800.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    credits: List[BusinessCredit] = Field(
        default_factory=list,
        description="List of all business credits"
    )

    def add_credit(self, credit: BusinessCredit) -> None:
        """Add a business credit to the list."""
        self.credits.append(credit)

    @computed_field
    @property
    def total_current_year_credits(self) -> float:
        """Total credits from current year."""
        return sum(
            c.credit_amount for c in self.credits
            if c.credit_source == CreditSource.CURRENT_YEAR
        )

    @computed_field
    @property
    def total_carryforward_credits(self) -> float:
        """Total carryforward credits from prior years."""
        return sum(
            c.credit_amount for c in self.credits
            if c.credit_source == CreditSource.CARRYFORWARD
        )

    @computed_field
    @property
    def total_carryback_credits(self) -> float:
        """Total carryback credits from later years."""
        return sum(
            c.credit_amount for c in self.credits
            if c.credit_source == CreditSource.CARRYBACK
        )

    @computed_field
    @property
    def total_passive_credits(self) -> float:
        """Total passive activity credits."""
        return sum(c.credit_amount for c in self.credits if c.is_passive)

    @computed_field
    @property
    def total_specified_credits(self) -> float:
        """Total specified credits."""
        return sum(c.credit_amount for c in self.credits if c.is_specified_credit)

    @computed_field
    @property
    def total_all_credits(self) -> float:
        """Total of all credits."""
        return sum(c.credit_amount for c in self.credits)

    def by_credit_type(self) -> Dict[str, float]:
        """Group credits by type."""
        result = {}
        for credit in self.credits:
            key = credit.credit_type.value
            result[key] = result.get(key, 0) + credit.credit_amount
        return result

    def by_source(self) -> Dict[str, float]:
        """Group credits by source."""
        return {
            "current_year": self.total_current_year_credits,
            "carryforward": self.total_carryforward_credits,
            "carryback": self.total_carryback_credits,
        }


class Form3800(BaseModel):
    """
    Form 3800 - General Business Credit

    Complete implementation of IRS Form 3800.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Taxpayer information
    taxpayer_name: str = Field(default="", description="Taxpayer name")
    taxpayer_tin: str = Field(default="", description="Taxpayer TIN/EIN")

    # Parts
    part_1: Form3800Part1 = Field(
        default_factory=Form3800Part1,
        description="Part I: Current year credit"
    )

    part_2: Form3800Part2 = Field(
        default_factory=Form3800Part2,
        description="Part II: Allowable credit"
    )

    part_3: Form3800Part3 = Field(
        default_factory=Form3800Part3,
        description="Part III: Credit details"
    )

    def add_credit(
        self,
        credit_type: CreditType,
        amount: float,
        source_form: str = "",
        description: str = "",
        source: CreditSource = CreditSource.CURRENT_YEAR,
        original_year: Optional[int] = None,
        is_specified: bool = False,
        is_passive: bool = False,
    ) -> None:
        """
        Add a business credit to Form 3800.

        Args:
            credit_type: Type of credit
            amount: Credit amount
            source_form: Source form number
            description: Description
            source: Credit source (current/carryforward/carryback)
            original_year: Original year for carryover credits
            is_specified: Is this a specified credit?
            is_passive: Is this a passive activity credit?
        """
        credit = BusinessCredit(
            credit_type=credit_type,
            credit_amount=amount,
            source_form=source_form,
            description=description,
            credit_source=source,
            original_year=original_year,
            is_specified_credit=is_specified,
            is_passive=is_passive,
        )
        self.part_3.add_credit(credit)

        # Update Part I
        self._update_part_1()

    def _update_part_1(self) -> None:
        """Update Part I totals from Part III."""
        self.part_1.line_1_general_business_credit = self.part_3.total_all_credits
        self.part_1.line_2_passive_credits = self.part_3.total_passive_credits
        self.part_1.line_5_carryforward = self.part_3.total_carryforward_credits
        self.part_1.line_6_carryback = self.part_3.total_carryback_credits

    def set_tax_liability(
        self,
        regular_tax: float,
        amt: float = 0.0,
        net_regular_tax: float = 0.0,
        tmt: float = 0.0,
    ) -> None:
        """
        Set tax liability information for calculating allowable credit.

        Args:
            regular_tax: Regular tax before credits
            amt: Alternative minimum tax
            net_regular_tax: Net regular tax (after other credits)
            tmt: Tentative minimum tax
        """
        self.part_2.line_8_regular_tax = regular_tax
        self.part_2.line_9_amt = amt
        self.part_2.line_11_net_regular_tax = net_regular_tax or regular_tax
        self.part_2.line_13_tmt = tmt
        self.part_2.line_16_credit_from_part1 = self.part_1.line_7_total

    @computed_field
    @property
    def total_credits_claimed(self) -> float:
        """Total credits before limitation."""
        return self.part_3.total_all_credits

    @computed_field
    @property
    def credit_limitation(self) -> float:
        """Credit limitation amount."""
        return self.part_2.line_15_limitation

    @computed_field
    @property
    def allowable_credit(self) -> float:
        """Allowable general business credit."""
        return self.part_2.line_36_allowable_credit

    @computed_field
    @property
    def unused_credit(self) -> float:
        """Credit that couldn't be used (potential carryforward)."""
        return max(0, self.total_credits_claimed - self.allowable_credit)

    @computed_field
    @property
    def has_carryforward(self) -> bool:
        """Check if there's unused credit to carry forward."""
        return self.unused_credit > 0

    def calculate_carryforward(self) -> Dict[str, Any]:
        """
        Calculate credit carryforward to future years.

        Credits can be carried forward 20 years.
        """
        if not self.has_carryforward:
            return {
                "has_carryforward": False,
                "amount": 0.0,
            }

        return {
            "has_carryforward": True,
            "amount": self.unused_credit,
            "expires_after_year": self.tax_year + 20,
            "from_year": self.tax_year,
        }

    def to_form_1040(self) -> Dict[str, float]:
        """Get amounts for Form 1040."""
        return {
            "schedule_3_line_6a": self.allowable_credit,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "credits": {
                "total_claimed": self.total_credits_claimed,
                "by_type": self.part_3.by_credit_type(),
                "by_source": self.part_3.by_source(),
                "specified_credits": self.part_3.total_specified_credits,
                "passive_credits": self.part_3.total_passive_credits,
            },
            "limitation": {
                "net_income_tax": self.part_2.line_10_net_income_tax,
                "limitation": self.credit_limitation,
            },
            "result": {
                "allowable_credit": self.allowable_credit,
                "unused_credit": self.unused_credit,
                "has_carryforward": self.has_carryforward,
            },
            "carryforward": self.calculate_carryforward(),
        }


# Specific credit calculation helpers

class ResearchCredit(BaseModel):
    """
    Form 6765 - Credit for Increasing Research Activities

    Simplified calculation for R&D tax credit.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Qualified Research Expenses (QREs)
    wages: float = Field(default=0.0, ge=0, description="Qualified wages")
    supplies: float = Field(default=0.0, ge=0, description="Qualified supplies")
    contract_research: float = Field(default=0.0, ge=0, description="Contract research (65%)")

    # Base amount for regular credit
    base_amount: float = Field(default=0.0, ge=0, description="Base amount")

    # Alternative Simplified Credit (ASC) election
    use_simplified_method: bool = Field(
        default=True,
        description="Use Alternative Simplified Credit method"
    )

    # Prior 3 years QREs for ASC
    prior_year_1_qre: float = Field(default=0.0, ge=0, description="Prior year 1 QREs")
    prior_year_2_qre: float = Field(default=0.0, ge=0, description="Prior year 2 QREs")
    prior_year_3_qre: float = Field(default=0.0, ge=0, description="Prior year 3 QREs")

    @computed_field
    @property
    def total_qre(self) -> float:
        """Total Qualified Research Expenses."""
        return self.wages + self.supplies + (self.contract_research * 0.65)

    @computed_field
    @property
    def average_prior_qre(self) -> float:
        """Average of prior 3 years QREs."""
        total = self.prior_year_1_qre + self.prior_year_2_qre + self.prior_year_3_qre
        return total / 3 if total > 0 else 0

    @computed_field
    @property
    def regular_credit(self) -> float:
        """Calculate regular research credit (20% method)."""
        excess = max(0, self.total_qre - self.base_amount)
        return excess * 0.20

    @computed_field
    @property
    def simplified_credit(self) -> float:
        """Calculate Alternative Simplified Credit."""
        # 14% of QRE exceeding 50% of average prior 3 years
        threshold = self.average_prior_qre * 0.50
        excess = max(0, self.total_qre - threshold)
        return excess * 0.14

    @computed_field
    @property
    def credit_amount(self) -> float:
        """Get the applicable credit amount."""
        if self.use_simplified_method:
            return self.simplified_credit
        return self.regular_credit

    def to_form_3800(self) -> BusinessCredit:
        """Convert to Form 3800 credit entry."""
        return BusinessCredit(
            credit_type=CreditType.RESEARCH,
            source_form="Form 6765",
            description="Credit for Increasing Research Activities",
            credit_amount=self.credit_amount,
            credit_source=CreditSource.CURRENT_YEAR,
        )


class WorkOpportunityCredit(BaseModel):
    """
    Form 5884 - Work Opportunity Credit

    Credit for hiring individuals from targeted groups.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Qualified wages by target group
    # Most groups: 40% of first $6,000 = $2,400 max per employee
    # Long-term family assistance: 40% of first $10,000 = $4,000 max

    qualified_first_year_wages: float = Field(
        default=0.0, ge=0,
        description="Qualified first-year wages (max $6,000 per employee)"
    )

    qualified_second_year_wages: float = Field(
        default=0.0, ge=0,
        description="Qualified second-year wages (long-term recipients only)"
    )

    long_term_recipient_wages: float = Field(
        default=0.0, ge=0,
        description="Long-term family assistance recipient wages"
    )

    summer_youth_wages: float = Field(
        default=0.0, ge=0,
        description="Summer youth employee wages (max $3,000)"
    )

    @computed_field
    @property
    def first_year_credit(self) -> float:
        """First year credit (40% of qualified wages)."""
        return self.qualified_first_year_wages * 0.40

    @computed_field
    @property
    def second_year_credit(self) -> float:
        """Second year credit (50% for long-term recipients)."""
        return self.qualified_second_year_wages * 0.50

    @computed_field
    @property
    def long_term_credit(self) -> float:
        """Long-term recipient credit (40% of first $10,000)."""
        return self.long_term_recipient_wages * 0.40

    @computed_field
    @property
    def summer_youth_credit(self) -> float:
        """Summer youth credit (40% of first $3,000)."""
        return self.summer_youth_wages * 0.40

    @computed_field
    @property
    def total_credit(self) -> float:
        """Total Work Opportunity Credit."""
        return (
            self.first_year_credit +
            self.second_year_credit +
            self.long_term_credit +
            self.summer_youth_credit
        )

    def to_form_3800(self) -> BusinessCredit:
        """Convert to Form 3800 credit entry."""
        return BusinessCredit(
            credit_type=CreditType.WORK_OPPORTUNITY,
            source_form="Form 5884",
            description="Work Opportunity Credit",
            credit_amount=self.total_credit,
            credit_source=CreditSource.CURRENT_YEAR,
        )


class SmallEmployerHealthCredit(BaseModel):
    """
    Form 8941 - Credit for Small Employer Health Insurance Premiums

    Credit for small employers providing health insurance.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Eligibility requirements
    average_annual_wages: float = Field(
        default=0.0, ge=0,
        description="Average annual wages per FTE"
    )

    fte_count: float = Field(
        default=0.0, ge=0,
        description="Number of FTE employees"
    )

    # Credit calculation
    premiums_paid: float = Field(
        default=0.0, ge=0,
        description="Total premiums paid by employer"
    )

    state_average_premium: float = Field(
        default=0.0, ge=0,
        description="State average premium for small group market"
    )

    is_tax_exempt: bool = Field(
        default=False,
        description="Is employer a tax-exempt organization?"
    )

    @computed_field
    @property
    def is_eligible(self) -> bool:
        """Check if employer is eligible for credit."""
        # Must have < 25 FTEs and average wages < $56,000 (2025)
        return self.fte_count < 25 and self.average_annual_wages < 56000

    @computed_field
    @property
    def credit_percentage(self) -> float:
        """Calculate credit percentage (max 50%, 35% for tax-exempt)."""
        if not self.is_eligible:
            return 0.0

        base_rate = 0.35 if self.is_tax_exempt else 0.50

        # Phase-out for FTEs > 10
        if self.fte_count > 10:
            fte_reduction = (self.fte_count - 10) / 15
            base_rate *= (1 - fte_reduction)

        # Phase-out for wages > $28,000
        if self.average_annual_wages > 28000:
            wage_reduction = (self.average_annual_wages - 28000) / 28000
            base_rate *= (1 - wage_reduction)

        return max(0, base_rate)

    @computed_field
    @property
    def eligible_premiums(self) -> float:
        """Calculate eligible premium amount."""
        # Lesser of actual premiums or state average
        return min(self.premiums_paid, self.state_average_premium * self.fte_count)

    @computed_field
    @property
    def credit_amount(self) -> float:
        """Calculate credit amount."""
        return self.eligible_premiums * self.credit_percentage

    def to_form_3800(self) -> BusinessCredit:
        """Convert to Form 3800 credit entry."""
        return BusinessCredit(
            credit_type=CreditType.SMALL_EMPLOYER_HEALTH,
            source_form="Form 8941",
            description="Credit for Small Employer Health Insurance",
            credit_amount=self.credit_amount,
            credit_source=CreditSource.CURRENT_YEAR,
            is_specified_credit=True,  # Can offset AMT
        )


def calculate_general_business_credit(
    credits: List[Dict[str, Any]],
    regular_tax: float,
    amt: float = 0.0,
    net_regular_tax: float = 0.0,
    tmt: float = 0.0,
    tax_year: int = 2025,
) -> Dict[str, Any]:
    """
    Convenience function to calculate general business credit.

    Args:
        credits: List of credit dictionaries with type, amount, etc.
        regular_tax: Regular tax before credits
        amt: Alternative minimum tax
        net_regular_tax: Net regular tax (after other credits)
        tmt: Tentative minimum tax
        tax_year: Tax year

    Returns:
        Dictionary with credit calculation results
    """
    form = Form3800(tax_year=tax_year)

    for credit_info in credits:
        credit_type = CreditType(credit_info.get("type", "other"))
        form.add_credit(
            credit_type=credit_type,
            amount=credit_info.get("amount", 0),
            source_form=credit_info.get("source_form", ""),
            description=credit_info.get("description", ""),
            source=CreditSource(credit_info.get("source", "current_year")),
            is_specified=credit_info.get("is_specified", False),
            is_passive=credit_info.get("is_passive", False),
        )

    form.set_tax_liability(
        regular_tax=regular_tax,
        amt=amt,
        net_regular_tax=net_regular_tax or regular_tax,
        tmt=tmt,
    )

    return form.to_dict()
