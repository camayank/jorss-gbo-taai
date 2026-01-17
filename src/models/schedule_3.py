"""
Schedule 3 (Form 1040) - Additional Credits and Payments

IRS Form for reporting credits and payments not on Form 1040:
- Part I: Nonrefundable Credits (Lines 1-8)
  - Foreign tax credit (Form 1116)
  - Child and dependent care credit (Form 2441)
  - Education credits (Form 8863)
  - Retirement savings contributions credit (Form 8880)
  - Residential energy credits (Form 5695)
  - Other nonrefundable credits

- Part II: Other Payments and Refundable Credits (Lines 9-15)
  - Net premium tax credit (Form 8962)
  - Amount paid with extension
  - Excess Social Security and tier 1 RRTA withheld
  - Credit for federal tax on fuels (Form 4136)
  - Other payments or refundable credits

Schedule 3 totals flow to:
- Form 1040 Line 20 (Part I: Nonrefundable credits)
- Form 1040 Line 31 (Part II: Other payments/refundable credits)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from calculator.engine import CalculationBreakdown


class NonrefundableCreditType(str, Enum):
    """Types of nonrefundable credits on Schedule 3 Line 6."""
    GENERAL_BUSINESS = "general_business"  # Form 3800
    MORTGAGE_INTEREST = "mortgage_interest"  # Form 8396
    ADOPTION = "adoption"  # Form 8839 (nonrefundable portion)
    DISABILITY = "disability"  # Schedule R
    ELDERLY = "elderly"  # Schedule R (elderly/disabled)
    DC_HOMEBUYER = "dc_homebuyer"  # DC first-time homebuyer
    ALTERNATIVE_MOTOR = "alternative_motor"  # Form 8910
    QUALIFIED_PLUG_IN = "qualified_plug_in"  # Qualified plug-in credit
    CLEAN_VEHICLE = "clean_vehicle"  # Form 8936 (nonrefundable)
    PRIOR_YEAR_AMT = "prior_year_amt"  # Form 8801
    FOREIGN_TRUST = "foreign_trust"  # Credit from certain foreign trusts
    INVESTMENT_CREDIT = "investment_credit"  # Form 3468
    WORK_OPPORTUNITY = "work_opportunity"  # Form 5884
    INDIAN_EMPLOYMENT = "indian_employment"  # Form 8845
    ENHANCED_OIL = "enhanced_oil"  # Form 8830
    NEW_MARKETS = "new_markets"  # Form 8874
    EMPLOYER_SOCIAL_SECURITY = "employer_ss"  # Form 8846
    BIODIESEL = "biodiesel"  # Form 8864
    LOW_SULFUR_DIESEL = "low_sulfur"  # Form 8896
    DISTILLED_SPIRITS = "distilled_spirits"  # Form 8906
    RAILROAD_TRACK = "railroad_track"  # Form 8900
    EMPLOYER_DIFFERENTIAL = "employer_diff_pay"  # Form 8932
    CARBON_OXIDE = "carbon_oxide"  # Form 8933
    QUALIFIED_BONDS = "qualified_bonds"  # Form 8912 credit to holders
    NONBUSINESS_ENERGY = "nonbusiness_energy"  # Form 5695 Part I
    RESIDENTIAL_ENERGY = "residential_energy"  # Form 5695 Part II
    OTHER = "other"


class RefundableCreditType(str, Enum):
    """Types of refundable credits on Schedule 3 Part II."""
    HEALTH_COVERAGE = "health_coverage"  # Form 8885
    SICK_FAMILY_LEAVE = "sick_family_leave"  # Form 7202
    ADDITIONAL_CHILD = "additional_child_tax"  # Form 8812 (refundable portion)
    AMERICAN_OPPORTUNITY = "aoc_refundable"  # Form 8863 (40% of AOC)
    FUEL_TAX = "fuel_tax"  # Form 4136
    EARNED_INCOME = "eitc"  # Earned income credit (Schedule EIC)
    QUALIFIED_RETIREMENT = "qualified_retirement"  # Form 8880 (refundable part)
    CLEAN_VEHICLE = "clean_vehicle_refundable"  # Form 8936 (refundable)
    ELECTIVE_PAYMENT = "elective_payment"  # IRC 6417 elective payment
    FIRST_TIME_HOMEBUYER = "first_time_homebuyer"  # DC first-time homebuyer
    RECOVERY_REBATE = "recovery_rebate"  # Economic impact payment shortfall
    OTHER = "other"


class NonrefundableCreditItem(BaseModel):
    """Individual nonrefundable credit item for Line 6z."""
    credit_type: NonrefundableCreditType = Field(description="Type of credit")
    description: str = Field(description="Description of credit")
    amount: float = Field(ge=0, description="Credit amount")
    form_reference: Optional[str] = Field(default=None, description="Related IRS form")


class RefundableCreditItem(BaseModel):
    """Individual refundable credit/payment item for Line 14z."""
    credit_type: RefundableCreditType = Field(description="Type of credit/payment")
    description: str = Field(description="Description")
    amount: float = Field(ge=0, description="Amount")
    form_reference: Optional[str] = Field(default=None, description="Related IRS form")


class Schedule3Part1(BaseModel):
    """
    Schedule 3 Part I: Nonrefundable Credits

    Lines 1-8 flow to Form 1040 Line 20.
    """
    # Line 1: Foreign tax credit (attach Form 1116 if required)
    line_1_foreign_tax_credit: float = Field(
        default=0.0, ge=0,
        description="Foreign tax credit (Form 1116 or direct entry)"
    )
    line_1_form_1116_attached: bool = Field(
        default=False,
        description="Form 1116 attached (required if credit > $300/$600 MFJ)"
    )

    # Line 2: Credit for child and dependent care expenses (Form 2441)
    line_2_dependent_care_credit: float = Field(
        default=0.0, ge=0,
        description="Child and dependent care credit (Form 2441)"
    )

    # Line 3: Education credits (Form 8863)
    line_3_education_credits: float = Field(
        default=0.0, ge=0,
        description="Education credits - nonrefundable (Form 8863 Line 19)"
    )

    # Line 4: Retirement savings contributions credit (Form 8880)
    line_4_saver_credit: float = Field(
        default=0.0, ge=0,
        description="Saver's credit (Form 8880)"
    )

    # Line 5a: Residential clean energy credit (Form 5695, Part I)
    line_5a_clean_energy_credit: float = Field(
        default=0.0, ge=0,
        description="Residential clean energy credit (Form 5695 Part I)"
    )

    # Line 5b: Energy efficient home improvement credit (Form 5695, Part II)
    line_5b_energy_improvement_credit: float = Field(
        default=0.0, ge=0,
        description="Energy efficient home improvement credit (Form 5695 Part II)"
    )

    # Line 6a: Credit for prior year minimum tax (Form 8801)
    line_6a_prior_year_amt_credit: float = Field(
        default=0.0, ge=0,
        description="Prior year minimum tax credit (Form 8801)"
    )

    # Line 6b: Qualified electric vehicle credit (Form 8936)
    line_6b_ev_credit: float = Field(
        default=0.0, ge=0,
        description="Clean vehicle credit - nonrefundable (Form 8936)"
    )

    # Line 6c: Alternative fuel vehicle refueling property credit (Form 8911)
    line_6c_refueling_credit: float = Field(
        default=0.0, ge=0,
        description="Alternative fuel vehicle refueling credit (Form 8911)"
    )

    # Line 6d: Credit to holders of tax credit bonds (Form 8912)
    line_6d_bond_credit: float = Field(
        default=0.0, ge=0,
        description="Credit to holders of tax credit bonds (Form 8912)"
    )

    # Line 6e: Amount on Form 8978, line 14 (if filing separately after filing jointly)
    line_6e_form_8978: float = Field(
        default=0.0, ge=0,
        description="Partner's share of adjustment (Form 8978)"
    )

    # Line 6f: Disabled access credit (Form 8826)
    line_6f_disabled_access: float = Field(
        default=0.0, ge=0,
        description="Disabled access credit (Form 8826)"
    )

    # Line 6g: Employer credit for paid family and medical leave (Form 8994)
    line_6g_family_leave_credit: float = Field(
        default=0.0, ge=0,
        description="Employer paid family/medical leave credit (Form 8994)"
    )

    # Line 6h: Adoption credit (Form 8839)
    line_6h_adoption_credit: float = Field(
        default=0.0, ge=0,
        description="Adoption credit (Form 8839)"
    )

    # Line 6i: Credit for employer-provided childcare (Form 8882)
    line_6i_employer_childcare: float = Field(
        default=0.0, ge=0,
        description="Employer-provided childcare credit (Form 8882)"
    )

    # Line 6j: Qualified plug-in electric drive motor vehicle credit (Form 8936)
    line_6j_plug_in_vehicle: float = Field(
        default=0.0, ge=0,
        description="Previously owned clean vehicle credit (Form 8936)"
    )

    # Line 6k: General business credit (Form 3800)
    line_6k_general_business: float = Field(
        default=0.0, ge=0,
        description="General business credit (Form 3800)"
    )

    # Line 6l: Credit for elderly or disabled (Schedule R)
    line_6l_elderly_disabled: float = Field(
        default=0.0, ge=0,
        description="Credit for elderly or disabled (Schedule R)"
    )

    # Line 6m: Credit for repayment of amounts included in income in prior year
    line_6m_claim_of_right: float = Field(
        default=0.0, ge=0,
        description="Claim of right credit (IRC 1341)"
    )

    # Line 6z: Other nonrefundable credits (itemized list)
    line_6z_other_credits: List[NonrefundableCreditItem] = Field(
        default_factory=list,
        description="Other nonrefundable credits"
    )

    @computed_field
    @property
    def line_6z_total(self) -> float:
        """Total of Line 6z other nonrefundable credits."""
        return sum(item.amount for item in self.line_6z_other_credits)

    @computed_field
    @property
    def line_7_total_other_credits(self) -> float:
        """Line 7: Total of lines 6a through 6z."""
        return (
            self.line_6a_prior_year_amt_credit +
            self.line_6b_ev_credit +
            self.line_6c_refueling_credit +
            self.line_6d_bond_credit +
            self.line_6e_form_8978 +
            self.line_6f_disabled_access +
            self.line_6g_family_leave_credit +
            self.line_6h_adoption_credit +
            self.line_6i_employer_childcare +
            self.line_6j_plug_in_vehicle +
            self.line_6k_general_business +
            self.line_6l_elderly_disabled +
            self.line_6m_claim_of_right +
            self.line_6z_total
        )

    @computed_field
    @property
    def line_8_total_nonrefundable(self) -> float:
        """
        Line 8: Total Nonrefundable Credits.
        Add lines 1-5 and 7. Enter here and on Form 1040 Line 20.
        """
        return (
            self.line_1_foreign_tax_credit +
            self.line_2_dependent_care_credit +
            self.line_3_education_credits +
            self.line_4_saver_credit +
            self.line_5a_clean_energy_credit +
            self.line_5b_energy_improvement_credit +
            self.line_7_total_other_credits
        )


class Schedule3Part2(BaseModel):
    """
    Schedule 3 Part II: Other Payments and Refundable Credits

    Lines 9-15 flow to Form 1040 Line 31.
    """
    # Line 9: Net premium tax credit (Form 8962)
    line_9_ptc: float = Field(
        default=0.0, ge=0,
        description="Net premium tax credit (Form 8962)"
    )

    # Line 10: Amount paid with request for extension to file (Form 4868)
    line_10_extension_payment: float = Field(
        default=0.0, ge=0,
        description="Amount paid with extension (Form 4868)"
    )

    # Line 11: Excess Social Security and tier 1 RRTA tax withheld
    line_11_excess_ss_withheld: float = Field(
        default=0.0, ge=0,
        description="Excess Social Security/RRTA tax withheld"
    )

    # Line 12: Credit for federal tax on fuels (Form 4136)
    line_12_fuel_credit: float = Field(
        default=0.0, ge=0,
        description="Credit for federal tax on fuels (Form 4136)"
    )

    # Line 13a: Form 2439 credit
    line_13a_form_2439: float = Field(
        default=0.0, ge=0,
        description="Credit from Form 2439"
    )

    # Line 13b: Reserved for future use
    line_13b_reserved: float = Field(
        default=0.0, ge=0,
        description="Reserved"
    )

    # Line 13c: Credit for repayment of amounts under claim of right
    line_13c_claim_of_right: float = Field(
        default=0.0, ge=0,
        description="Claim of right repayment credit"
    )

    # Line 13d: Qualified sick and family leave credits from Schedule H and Form 7202
    line_13d_sick_leave_credit: float = Field(
        default=0.0, ge=0,
        description="Sick and family leave credits (Form 7202)"
    )

    # Line 13e: Health coverage tax credit (Form 8885)
    line_13e_health_coverage: float = Field(
        default=0.0, ge=0,
        description="Health coverage tax credit (Form 8885)"
    )

    # Line 13f: Credit for federal tax paid on fuels
    line_13f_fuel_paid: float = Field(
        default=0.0, ge=0,
        description="Additional fuel credit"
    )

    # Line 13g: Deferred amount of net 965 tax liability
    line_13g_section_965: float = Field(
        default=0.0, ge=0,
        description="Deferred 965 tax liability"
    )

    # Line 13h: Credit from Form 8936 (refundable portion)
    line_13h_ev_credit_refundable: float = Field(
        default=0.0, ge=0,
        description="Clean vehicle credit - refundable (Form 8936)"
    )

    # Line 13z: Other payments or refundable credits (itemized)
    line_13z_other_payments: List[RefundableCreditItem] = Field(
        default_factory=list,
        description="Other payments or refundable credits"
    )

    @computed_field
    @property
    def line_13z_total(self) -> float:
        """Total of Line 13z other payments/credits."""
        return sum(item.amount for item in self.line_13z_other_payments)

    @computed_field
    @property
    def line_14_total_other_payments(self) -> float:
        """Line 14: Total of lines 13a through 13z."""
        return (
            self.line_13a_form_2439 +
            self.line_13b_reserved +
            self.line_13c_claim_of_right +
            self.line_13d_sick_leave_credit +
            self.line_13e_health_coverage +
            self.line_13f_fuel_paid +
            self.line_13g_section_965 +
            self.line_13h_ev_credit_refundable +
            self.line_13z_total
        )

    @computed_field
    @property
    def line_15_total_part_2(self) -> float:
        """
        Line 15: Total Other Payments and Refundable Credits.
        Add lines 9-12 and 14. Enter here and on Form 1040 Line 31.
        """
        return (
            self.line_9_ptc +
            self.line_10_extension_payment +
            self.line_11_excess_ss_withheld +
            self.line_12_fuel_credit +
            self.line_14_total_other_payments
        )


class Schedule3(BaseModel):
    """
    Schedule 3 (Form 1040) - Additional Credits and Payments

    Complete model implementing all IRS Schedule 3 line items.

    Flows to Form 1040:
    - Line 8 (Part I Total) -> Form 1040 Line 20
    - Line 15 (Part II Total) -> Form 1040 Line 31
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Part I: Nonrefundable Credits
    part_1: Schedule3Part1 = Field(
        default_factory=Schedule3Part1,
        description="Part I: Nonrefundable Credits"
    )

    # Part II: Other Payments and Refundable Credits
    part_2: Schedule3Part2 = Field(
        default_factory=Schedule3Part2,
        description="Part II: Other Payments and Refundable Credits"
    )

    def is_required(self) -> bool:
        """
        Determine if Schedule 3 must be filed.

        Required if:
        - Any nonrefundable credits other than child tax credit (Part I)
        - Any other payments or refundable credits (Part II)
        """
        return (
            self.part_1.line_8_total_nonrefundable > 0 or
            self.part_2.line_15_total_part_2 > 0
        )

    @computed_field
    @property
    def form_1040_line_20(self) -> float:
        """Amount to report on Form 1040 Line 20 (Other credits)."""
        return self.part_1.line_8_total_nonrefundable

    @computed_field
    @property
    def form_1040_line_31(self) -> float:
        """Amount to report on Form 1040 Line 31 (Other payments/credits)."""
        return self.part_2.line_15_total_part_2

    @computed_field
    @property
    def total_additional_credits(self) -> float:
        """Total of all additional credits/payments from Schedule 3."""
        return self.form_1040_line_20 + self.form_1040_line_31

    @classmethod
    def from_breakdown(cls, breakdown: "CalculationBreakdown") -> "Schedule3":
        """
        Create Schedule 3 from CalculationBreakdown results.

        Args:
            breakdown: The calculation breakdown from the engine

        Returns:
            Populated Schedule 3
        """
        credit_breakdown = breakdown.credit_breakdown or {}

        part1 = Schedule3Part1(
            line_1_foreign_tax_credit=breakdown.form_1116_credit_allowed if hasattr(breakdown, 'form_1116_credit_allowed') else credit_breakdown.get('foreign_tax_credit', 0),
            line_2_dependent_care_credit=credit_breakdown.get('dependent_care_credit', 0),
            line_3_education_credits=credit_breakdown.get('education_credits_nonrefundable', 0),
            line_4_saver_credit=credit_breakdown.get('retirement_savings_credit', 0),
            line_5a_clean_energy_credit=credit_breakdown.get('residential_energy_credit', 0),
            line_5b_energy_improvement_credit=credit_breakdown.get('energy_improvement_credit', 0),
            line_6a_prior_year_amt_credit=breakdown.form_8801_credit_allowed if hasattr(breakdown, 'form_8801_credit_allowed') else 0,
            line_6b_ev_credit=credit_breakdown.get('clean_vehicle_credit', 0),
            line_6k_general_business=credit_breakdown.get('general_business_credit', 0),
            line_6l_elderly_disabled=credit_breakdown.get('elderly_disabled_credit', 0),
        )

        part2 = Schedule3Part2(
            line_9_ptc=credit_breakdown.get('net_premium_tax_credit', 0),
            line_10_extension_payment=credit_breakdown.get('extension_payment', 0),
            line_11_excess_ss_withheld=credit_breakdown.get('excess_ss_withheld', 0),
            line_12_fuel_credit=credit_breakdown.get('fuel_credit', 0),
            line_13h_ev_credit_refundable=credit_breakdown.get('clean_vehicle_credit_refundable', 0),
        )

        return cls(
            tax_year=breakdown.tax_year,
            part_1=part1,
            part_2=part2
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "part_1": {
                "line_1_foreign_tax_credit": self.part_1.line_1_foreign_tax_credit,
                "line_2_dependent_care_credit": self.part_1.line_2_dependent_care_credit,
                "line_3_education_credits": self.part_1.line_3_education_credits,
                "line_4_saver_credit": self.part_1.line_4_saver_credit,
                "line_5a_clean_energy_credit": self.part_1.line_5a_clean_energy_credit,
                "line_5b_energy_improvement_credit": self.part_1.line_5b_energy_improvement_credit,
                "line_7_other_credits": self.part_1.line_7_total_other_credits,
                "line_8_total": self.part_1.line_8_total_nonrefundable,
            },
            "part_2": {
                "line_9_ptc": self.part_2.line_9_ptc,
                "line_10_extension_payment": self.part_2.line_10_extension_payment,
                "line_11_excess_ss_withheld": self.part_2.line_11_excess_ss_withheld,
                "line_12_fuel_credit": self.part_2.line_12_fuel_credit,
                "line_14_other_payments": self.part_2.line_14_total_other_payments,
                "line_15_total": self.part_2.line_15_total_part_2,
            },
            "form_1040_line_20": self.form_1040_line_20,
            "form_1040_line_31": self.form_1040_line_31,
            "total_additional_credits": self.total_additional_credits,
            "is_required": self.is_required(),
        }
