"""
Schedule 2 (Form 1040) - Additional Taxes

IRS Form for reporting taxes not calculated directly on Form 1040:
- Part I: Tax (Lines 1-4)
  - Alternative Minimum Tax (Form 6251)
  - Excess advance premium tax credit repayment (Form 8962)

- Part II: Other Taxes (Lines 5-21)
  - Self-employment tax (Schedule SE)
  - Unreported Social Security and Medicare tax (Forms 4137, 8919)
  - Additional tax on IRAs and retirement plans (Form 5329)
  - Household employment taxes (Schedule H)
  - Repayment of first-time homebuyer credit
  - Additional Medicare tax (Form 8959)
  - Net investment income tax (Form 8960)
  - Interest on tax due on installment income (IRC Section 453A)
  - Other additional taxes

Schedule 2 totals flow to:
- Form 1040 Line 17 (Part I: Add to tax)
- Form 1040 Line 23 (Part II: Other taxes)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from calculator.engine import CalculationBreakdown


class OtherTaxType(str, Enum):
    """Types of other taxes on Schedule 2 Line 17z."""
    GOLDEN_PARACHUTE = "golden_parachute"  # IRC Section 4999 excise tax
    TAX_ON_ACCUMULATION = "accumulation"  # Tax on accumulation distribution of trusts
    LOOK_BACK_INTEREST = "look_back"  # Look-back interest under IRC 460(b)
    TAX_ON_NQDC = "nqdc"  # Tax on nonqualified deferred compensation (IRC 409A)
    RECAPTURE_CREDITS = "credit_recapture"  # Recapture of federal mortgage subsidy
    INTEREST_453A_453I = "interest_453a_453i"  # Interest under IRC 453A or 453I(c)
    TAX_ON_QUAL_PLAN_DISTRIBUTIONS = "qual_plan_dist"  # Tax on qualified plan distributions
    SECTION_72M5_TAX = "section_72m5"  # IRC 72(m)(5) additional tax
    RECAPTURE_LOW_INCOME_HOUSING = "low_income_housing"  # Low-income housing credit recapture
    RECAPTURE_INVESTMENT_CREDIT = "investment_credit"  # Investment credit recapture
    RECAPTURE_OTHER_CREDITS = "other_credit_recapture"  # Other credit recaptures
    ARCHER_MSA_ADDITIONAL_TAX = "archer_msa"  # Additional tax on Archer MSA
    HEALTH_COVERAGE_TAX_CREDIT = "hctc"  # Health Coverage Tax Credit recapture
    LUMP_SUM_DISTRIBUTION = "lump_sum"  # Lump-sum distribution tax
    INTEREST_TAX_DEFERRED_ANNUITY = "annuity_interest"  # Interest on tax-deferred annuity
    OTHER = "other"  # Other taxes


class OtherTaxItem(BaseModel):
    """Individual other tax item for Line 17z."""
    tax_type: OtherTaxType = Field(description="Type of other tax")
    description: str = Field(description="Description of tax")
    amount: float = Field(ge=0, description="Tax amount")
    form_reference: Optional[str] = Field(default=None, description="Related IRS form")


class Schedule2Part1(BaseModel):
    """
    Schedule 2 Part I: Tax

    Additional taxes that are added to Form 1040 Line 17.
    """
    # Line 1: Alternative Minimum Tax (attach Form 6251)
    line_1_amt: float = Field(
        default=0.0, ge=0,
        description="Alternative minimum tax (Form 6251)"
    )

    # Line 2: Excess advance premium tax credit repayment (attach Form 8962)
    line_2_ptc_repayment: float = Field(
        default=0.0, ge=0,
        description="Excess advance PTC repayment (Form 8962)"
    )

    @computed_field
    @property
    def line_3_total_part_1(self) -> float:
        """Line 3: Add lines 1 and 2. Enter here and on Form 1040 Line 17."""
        return self.line_1_amt + self.line_2_ptc_repayment


class Schedule2Part2(BaseModel):
    """
    Schedule 2 Part II: Other Taxes

    Other taxes that flow to Form 1040 Line 23.
    """
    # Line 4: Self-employment tax (attach Schedule SE)
    line_4_self_employment_tax: float = Field(
        default=0.0, ge=0,
        description="Self-employment tax (Schedule SE)"
    )

    # Line 5: Social Security and Medicare tax on unreported tip income (Form 4137)
    line_5_unreported_tip_tax: float = Field(
        default=0.0, ge=0,
        description="SS/Medicare tax on unreported tips (Form 4137)"
    )

    # Line 6: Uncollected SS and Medicare tax on wages (Form 8919)
    line_6_uncollected_ss_med: float = Field(
        default=0.0, ge=0,
        description="Uncollected SS/Medicare tax on wages (Form 8919)"
    )

    # Line 7a: Total additional tax on IRAs (Form 5329, Part I)
    line_7a_ira_additional_tax: float = Field(
        default=0.0, ge=0,
        description="Additional tax on IRA early distributions (Form 5329)"
    )

    # Line 7b: Total additional tax on other qualified plans (Form 5329, Parts II-VII)
    line_7b_other_qual_plan_tax: float = Field(
        default=0.0, ge=0,
        description="Additional tax on other qualified retirement plans (Form 5329)"
    )

    # Line 8: Household employment taxes (attach Schedule H)
    line_8_household_employment: float = Field(
        default=0.0, ge=0,
        description="Household employment taxes (Schedule H)"
    )

    # Line 9: Repayment of first-time homebuyer credit (Form 5405)
    line_9_first_time_homebuyer: float = Field(
        default=0.0, ge=0,
        description="First-time homebuyer credit repayment (Form 5405)"
    )

    # Line 10: Additional Medicare Tax (attach Form 8959)
    line_10_additional_medicare: float = Field(
        default=0.0, ge=0,
        description="Additional Medicare Tax (Form 8959)"
    )

    # Line 11: Net investment income tax (attach Form 8960)
    line_11_niit: float = Field(
        default=0.0, ge=0,
        description="Net investment income tax (Form 8960)"
    )

    # Line 12: Interest on tax due on installment income from sale of
    # certain residential lots or timeshares (IRC 453(l)(3))
    line_12_installment_interest_453l: float = Field(
        default=0.0, ge=0,
        description="Interest under IRC 453(l)(3)"
    )

    # Line 13: Interest on deferred tax on gain from installment method (IRC 453A)
    line_13_installment_interest_453a: float = Field(
        default=0.0, ge=0,
        description="Interest under IRC 453A(c)"
    )

    # Line 14: Recapture of low-income housing credit (Form 8611)
    line_14_low_income_housing_recapture: float = Field(
        default=0.0, ge=0,
        description="Low-income housing credit recapture (Form 8611)"
    )

    # Line 15: Recapture of other credits (see instructions)
    line_15_other_credit_recapture: float = Field(
        default=0.0, ge=0,
        description="Other credit recaptures"
    )

    # Line 16: Section 72(m)(5) excess benefits tax
    line_16_section_72m5: float = Field(
        default=0.0, ge=0,
        description="Section 72(m)(5) excess benefits tax"
    )

    # Line 17a: Golden parachute payments (IRC 4999)
    line_17a_golden_parachute: float = Field(
        default=0.0, ge=0,
        description="Tax on golden parachute payments (IRC 4999)"
    )

    # Line 17b: Tax on accumulation distribution of trusts (IRC 667)
    line_17b_accumulation_distribution: float = Field(
        default=0.0, ge=0,
        description="Tax on accumulation distribution (IRC 667)"
    )

    # Line 17c: IRC 409A income inclusion tax
    line_17c_section_409a: float = Field(
        default=0.0, ge=0,
        description="Tax on nonqualified deferred comp (IRC 409A)"
    )

    # Line 17d: IRC 457A(c)(1)(B) income inclusion tax
    line_17d_section_457a: float = Field(
        default=0.0, ge=0,
        description="Tax on NQDC from tax-indifferent party (IRC 457A)"
    )

    # Line 17e: Look-back interest under section 167(g) or 460(b)
    line_17e_look_back_interest: float = Field(
        default=0.0, ge=0,
        description="Look-back interest (IRC 167(g) or 460(b))"
    )

    # Line 17f: Tax on recapture of qualified electric vehicle credit
    line_17f_ev_credit_recapture: float = Field(
        default=0.0, ge=0,
        description="EV credit recapture"
    )

    # Line 17g: Tax on recapture of previously deducted qualified film or TV production costs
    line_17g_film_production_recapture: float = Field(
        default=0.0, ge=0,
        description="Film/TV production cost recapture"
    )

    # Line 17h: Interest under IRC 453A(c) on certain installment obligations
    line_17h_453a_interest: float = Field(
        default=0.0, ge=0,
        description="Interest on installment obligations (IRC 453A(c))"
    )

    # Line 17z: Other additional taxes (itemized list)
    line_17z_other_taxes: List[OtherTaxItem] = Field(
        default_factory=list,
        description="Other additional taxes"
    )

    @computed_field
    @property
    def line_17z_total(self) -> float:
        """Total of Line 17z other taxes."""
        return sum(item.amount for item in self.line_17z_other_taxes)

    @computed_field
    @property
    def line_17_total_other_line_17(self) -> float:
        """Total of Lines 17a through 17z."""
        return (
            self.line_17a_golden_parachute +
            self.line_17b_accumulation_distribution +
            self.line_17c_section_409a +
            self.line_17d_section_457a +
            self.line_17e_look_back_interest +
            self.line_17f_ev_credit_recapture +
            self.line_17g_film_production_recapture +
            self.line_17h_453a_interest +
            self.line_17z_total
        )

    @computed_field
    @property
    def line_18_additional_taxes_subtotal(self) -> float:
        """Line 18: Add lines 4 through 17."""
        return (
            self.line_4_self_employment_tax +
            self.line_5_unreported_tip_tax +
            self.line_6_uncollected_ss_med +
            self.line_7a_ira_additional_tax +
            self.line_7b_other_qual_plan_tax +
            self.line_8_household_employment +
            self.line_9_first_time_homebuyer +
            self.line_10_additional_medicare +
            self.line_11_niit +
            self.line_12_installment_interest_453l +
            self.line_13_installment_interest_453a +
            self.line_14_low_income_housing_recapture +
            self.line_15_other_credit_recapture +
            self.line_16_section_72m5 +
            self.line_17_total_other_line_17
        )

    # Line 19: Section 965 net tax liability installment from Form 965-A
    line_19_section_965: float = Field(
        default=0.0, ge=0,
        description="Section 965 net tax liability installment (Form 965-A)"
    )

    # Line 20: Additional tax on eligible rollover distributions not rolled over
    line_20_rollover_tax: float = Field(
        default=0.0, ge=0,
        description="Tax on non-rolled over eligible rollover distributions"
    )

    @computed_field
    @property
    def line_21_total_part_2(self) -> float:
        """
        Line 21: Total Other Taxes.
        Add lines 18, 19, and 20. Enter here and on Form 1040 Line 23.
        """
        return (
            self.line_18_additional_taxes_subtotal +
            self.line_19_section_965 +
            self.line_20_rollover_tax
        )


class Schedule2(BaseModel):
    """
    Schedule 2 (Form 1040) - Additional Taxes

    Complete model implementing all IRS Schedule 2 line items.

    Flows to Form 1040:
    - Line 3 (Part I Total) -> Form 1040 Line 17
    - Line 21 (Part II Total) -> Form 1040 Line 23
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Part I: Tax
    part_1: Schedule2Part1 = Field(
        default_factory=Schedule2Part1,
        description="Part I: Tax"
    )

    # Part II: Other Taxes
    part_2: Schedule2Part2 = Field(
        default_factory=Schedule2Part2,
        description="Part II: Other Taxes"
    )

    def is_required(self) -> bool:
        """
        Determine if Schedule 2 must be filed.

        Required if:
        - Any additional tax (Part I)
        - Any other taxes (Part II)
        """
        return (
            self.part_1.line_3_total_part_1 > 0 or
            self.part_2.line_21_total_part_2 > 0
        )

    @computed_field
    @property
    def form_1040_line_17(self) -> float:
        """Amount to report on Form 1040 Line 17."""
        return self.part_1.line_3_total_part_1

    @computed_field
    @property
    def form_1040_line_23(self) -> float:
        """Amount to report on Form 1040 Line 23."""
        return self.part_2.line_21_total_part_2

    @computed_field
    @property
    def total_additional_taxes(self) -> float:
        """Total of all additional taxes from Schedule 2."""
        return self.form_1040_line_17 + self.form_1040_line_23

    @classmethod
    def from_breakdown(cls, breakdown: "CalculationBreakdown") -> "Schedule2":
        """
        Create Schedule 2 from CalculationBreakdown results.

        Args:
            breakdown: The calculation breakdown from the engine

        Returns:
            Populated Schedule 2
        """
        part1 = Schedule2Part1(
            line_1_amt=breakdown.alternative_minimum_tax if hasattr(breakdown, 'alternative_minimum_tax') else 0,
            line_2_ptc_repayment=breakdown.ptc_repayment if hasattr(breakdown, 'ptc_repayment') else 0,
        )

        part2 = Schedule2Part2(
            line_4_self_employment_tax=breakdown.self_employment_tax if hasattr(breakdown, 'self_employment_tax') else 0,
            line_5_unreported_tip_tax=breakdown.credit_breakdown.get('form_4137_tax', 0) if breakdown.credit_breakdown else 0,
            line_7a_ira_additional_tax=breakdown.form_5329_early_distribution_penalty if hasattr(breakdown, 'form_5329_early_distribution_penalty') else 0,
            line_7b_other_qual_plan_tax=(
                (breakdown.form_5329_excess_contribution_tax if hasattr(breakdown, 'form_5329_excess_contribution_tax') else 0) +
                (breakdown.form_5329_rmd_penalty if hasattr(breakdown, 'form_5329_rmd_penalty') else 0)
            ),
            line_8_household_employment=breakdown.schedule_h_total_tax if hasattr(breakdown, 'schedule_h_total_tax') else 0,
            line_10_additional_medicare=breakdown.additional_medicare_tax if hasattr(breakdown, 'additional_medicare_tax') else 0,
            line_11_niit=breakdown.net_investment_income_tax if hasattr(breakdown, 'net_investment_income_tax') else 0,
            line_13_installment_interest_453a=breakdown.form_6252_section_453a_interest if hasattr(breakdown, 'form_6252_section_453a_interest') else 0,
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
                "line_1_amt": self.part_1.line_1_amt,
                "line_2_ptc_repayment": self.part_1.line_2_ptc_repayment,
                "line_3_total": self.part_1.line_3_total_part_1,
            },
            "part_2": {
                "line_4_self_employment_tax": self.part_2.line_4_self_employment_tax,
                "line_5_unreported_tip_tax": self.part_2.line_5_unreported_tip_tax,
                "line_6_uncollected_ss_med": self.part_2.line_6_uncollected_ss_med,
                "line_7a_ira_additional_tax": self.part_2.line_7a_ira_additional_tax,
                "line_7b_other_qual_plan_tax": self.part_2.line_7b_other_qual_plan_tax,
                "line_8_household_employment": self.part_2.line_8_household_employment,
                "line_10_additional_medicare": self.part_2.line_10_additional_medicare,
                "line_11_niit": self.part_2.line_11_niit,
                "line_18_subtotal": self.part_2.line_18_additional_taxes_subtotal,
                "line_21_total": self.part_2.line_21_total_part_2,
            },
            "form_1040_line_17": self.form_1040_line_17,
            "form_1040_line_23": self.form_1040_line_23,
            "total_additional_taxes": self.total_additional_taxes,
            "is_required": self.is_required(),
        }
