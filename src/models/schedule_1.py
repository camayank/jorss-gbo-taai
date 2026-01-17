"""
Schedule 1 (Form 1040) - Additional Income and Adjustments to Income

IRS Form for reporting:
- Part I: Additional Income (Lines 1-10)
  - Taxable refunds, credits, or offsets of state/local income taxes
  - Alimony received (divorce before 2019)
  - Business income (from Schedule C)
  - Capital gains/losses (from Schedule D)
  - Rental income (from Schedule E)
  - Farm income (from Schedule F)
  - Unemployment compensation
  - Other income (prizes, gambling, etc.)

- Part II: Adjustments to Income (Lines 11-26)
  - Educator expenses
  - HSA deduction
  - Moving expenses (military only)
  - Self-employment tax deduction (1/2 of SE tax)
  - Self-employed health insurance
  - SEP/SIMPLE/qualified plans
  - Student loan interest
  - IRA deduction
  - Other adjustments

Schedule 1 totals flow to:
- Form 1040 Line 8 (Additional income)
- Form 1040 Line 10 (Adjustments to income)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from calculator.engine import CalculationBreakdown


class OtherIncomeType(str, Enum):
    """Types of other income reported on Schedule 1 Line 8z."""
    PRIZES_AWARDS = "prizes_awards"  # Prizes and awards
    GAMBLING = "gambling"  # Gambling winnings
    JURY_DUTY = "jury_duty"  # Jury duty pay
    ALASKA_PFD = "alaska_pfd"  # Alaska Permanent Fund Dividend
    CANCELLATION_OF_DEBT = "cod"  # Cancellation of debt (non-1099-C)
    BARTERING = "bartering"  # Bartering income
    DIRECTOR_FEES = "director_fees"  # Board director fees
    NOTARY_FEES = "notary_fees"  # Notary public fees
    HOBBY_INCOME = "hobby_income"  # Hobby income (no loss deduction)
    FOREIGN_INCOME = "foreign_income"  # Foreign earned income (before exclusion)
    RECOVERY = "recovery"  # Recovery of tax benefit items
    TAXABLE_IRA_DISTRIBUTION = "taxable_ira"  # Taxable IRA distribution not reported elsewhere
    OTHER = "other"  # Other miscellaneous income


class OtherAdjustmentType(str, Enum):
    """Types of other adjustments on Schedule 1 Part II."""
    ARCHER_MSA = "archer_msa"  # Archer MSA deduction
    DOMESTIC_PRODUCTION = "domestic_production"  # Domestic production activities
    ATTORNEY_FEES = "attorney_fees"  # Attorney fees (employment discrimination)
    CLEAN_FUEL_REFUELING = "clean_fuel"  # Clean-fuel vehicle refueling property credit
    FOREIGN_HOUSING = "foreign_housing"  # Foreign housing deduction
    REPAYMENT = "repayment"  # Repayment of supplemental unemployment
    CONTRIBUTIONS = "contributions"  # Contributions to 501(c)(18)(D) plans
    SELF_EMPLOYED_RRTA = "se_rrta"  # Self-employed RRTA tax
    NONTAXABLE_OLYMPIC = "olympic"  # Nontaxable Olympic medals
    STUDENT_LOAN_DISCHARGE = "student_loan_discharge"  # Discharged student loan exclusion
    OTHER = "other"  # Other adjustments


class OtherIncomeItem(BaseModel):
    """Individual other income item for Line 8z."""
    income_type: OtherIncomeType = Field(description="Type of other income")
    description: str = Field(description="Description of income")
    amount: float = Field(ge=0, description="Income amount")


class OtherAdjustmentItem(BaseModel):
    """Individual other adjustment item for Line 24z."""
    adjustment_type: OtherAdjustmentType = Field(description="Type of adjustment")
    description: str = Field(description="Description of adjustment")
    amount: float = Field(ge=0, description="Adjustment amount")


class Schedule1Part1(BaseModel):
    """
    Schedule 1 Part I: Additional Income

    Lines 1-10 flow to Form 1040 Line 8.
    """
    # Line 1: Taxable refunds, credits, or offsets of state/local income taxes
    # Only taxable if taxpayer itemized in prior year AND deducted state taxes
    line_1_taxable_refunds: float = Field(
        default=0.0, ge=0,
        description="Taxable state/local refunds, credits, or offsets (Form 1099-G)"
    )

    # Line 2a: Alimony received (divorce finalized before 2019)
    line_2a_alimony_received: float = Field(
        default=0.0, ge=0,
        description="Alimony received (pre-2019 divorce only)"
    )
    # Line 2b: Date of original divorce decree
    line_2b_divorce_date: Optional[str] = Field(
        default=None,
        description="Date of divorce decree (required if alimony received)"
    )

    # Line 3: Business income/loss (attach Schedule C)
    line_3_business_income: float = Field(
        default=0.0,
        description="Net profit/loss from Schedule C (can be negative)"
    )

    # Line 4: Other gains/losses (attach Form 4797)
    line_4_other_gains_losses: float = Field(
        default=0.0,
        description="Gain/loss from Form 4797 (business property sales)"
    )

    # Line 5: Rental real estate, royalties, partnerships, S corps (attach Schedule E)
    line_5_schedule_e_income: float = Field(
        default=0.0,
        description="Net income/loss from Schedule E"
    )

    # Line 6: Farm income/loss (attach Schedule F)
    line_6_farm_income: float = Field(
        default=0.0,
        description="Net profit/loss from Schedule F"
    )

    # Line 7: Unemployment compensation
    line_7_unemployment: float = Field(
        default=0.0, ge=0,
        description="Unemployment compensation (Form 1099-G Box 1)"
    )

    # Line 8a: Net operating loss deduction (carryforward from prior year)
    line_8a_nol_deduction: float = Field(
        default=0.0, ge=0,
        description="Net operating loss deduction"
    )

    # Line 8b: Gambling income (Form W-2G)
    line_8b_gambling_income: float = Field(
        default=0.0, ge=0,
        description="Gambling income (Form W-2G)"
    )

    # Line 8c: Cancellation of debt income (Form 1099-C)
    line_8c_cod_income: float = Field(
        default=0.0, ge=0,
        description="Cancellation of debt income (Form 1099-C)"
    )

    # Line 8d: Foreign earned income exclusion (negative - reduces income)
    line_8d_foreign_income_exclusion: float = Field(
        default=0.0, ge=0,
        description="Foreign earned income exclusion from Form 2555"
    )

    # Line 8e: Taxable Health Savings Account distribution
    line_8e_taxable_hsa: float = Field(
        default=0.0, ge=0,
        description="Taxable HSA distribution (Form 8889 Line 16)"
    )

    # Line 8f: Alaska Permanent Fund dividends
    line_8f_alaska_pfd: float = Field(
        default=0.0, ge=0,
        description="Alaska Permanent Fund dividends"
    )

    # Line 8g: Jury duty pay (if remitted to employer, adjustment in Part II)
    line_8g_jury_duty_pay: float = Field(
        default=0.0, ge=0,
        description="Jury duty pay"
    )

    # Line 8h: Prizes and awards
    line_8h_prizes_awards: float = Field(
        default=0.0, ge=0,
        description="Prizes and awards"
    )

    # Line 8i: Activity not engaged in for profit income
    line_8i_hobby_income: float = Field(
        default=0.0, ge=0,
        description="Hobby income (activity not engaged in for profit)"
    )

    # Line 8j: Stock options (excess of FMV over amount paid)
    line_8j_stock_options: float = Field(
        default=0.0, ge=0,
        description="Stock options (NQSO) income"
    )

    # Line 8k: Income from rental of personal property
    line_8k_personal_property_rental: float = Field(
        default=0.0, ge=0,
        description="Income from rental of personal property (if not a business)"
    )

    # Line 8l: Olympic/Paralympic medal and USOC prize money
    line_8l_olympic_prizes: float = Field(
        default=0.0, ge=0,
        description="Olympic/Paralympic medal and USOC prize money"
    )

    # Line 8m: Section 951(a) inclusion (CFC)
    line_8m_section_951a: float = Field(
        default=0.0, ge=0,
        description="Section 951(a) inclusion from controlled foreign corporations"
    )

    # Line 8n: Section 951A(a) inclusion (GILTI)
    line_8n_gilti: float = Field(
        default=0.0, ge=0,
        description="Section 951A(a) GILTI inclusion"
    )

    # Line 8o: Section 461(l) excess business loss adjustment
    line_8o_excess_business_loss: float = Field(
        default=0.0, ge=0,
        description="Section 461(l) excess business loss adjustment"
    )

    # Line 8p: Taxable distributions from ABLE account
    line_8p_able_distribution: float = Field(
        default=0.0, ge=0,
        description="Taxable distributions from ABLE account"
    )

    # Line 8q: Scholarship/fellowship grant income included in W-2
    line_8q_scholarship_income: float = Field(
        default=0.0, ge=0,
        description="Taxable scholarship/fellowship grant income"
    )

    # Line 8r: Medicaid waiver payments excluded (safe harbor election)
    line_8r_medicaid_waiver_exclusion: float = Field(
        default=0.0, ge=0,
        description="Medicaid waiver payment exclusion (as negative)"
    )

    # Line 8s: Pension/annuity from nonqualified deferred compensation plan
    line_8s_nqdc: float = Field(
        default=0.0, ge=0,
        description="Nonqualified deferred compensation plan distribution"
    )

    # Line 8t: Wages earned while incarcerated
    line_8t_incarcerated_wages: float = Field(
        default=0.0, ge=0,
        description="Wages earned while incarcerated"
    )

    # Line 8z: Other income (itemized list)
    line_8z_other_income: List[OtherIncomeItem] = Field(
        default_factory=list,
        description="Other income items"
    )

    @computed_field
    @property
    def line_8z_total(self) -> float:
        """Total of Line 8z other income items."""
        return sum(item.amount for item in self.line_8z_other_income)

    @computed_field
    @property
    def line_9_total_additional_income(self) -> float:
        """
        Line 9: Total of Lines 1-8z.
        This is the total additional income that flows to Form 1040 Line 8.
        """
        # Note: Line 8d (foreign income exclusion) is subtracted
        return (
            self.line_1_taxable_refunds +
            self.line_2a_alimony_received +
            self.line_3_business_income +
            self.line_4_other_gains_losses +
            self.line_5_schedule_e_income +
            self.line_6_farm_income +
            self.line_7_unemployment -
            self.line_8a_nol_deduction +
            self.line_8b_gambling_income +
            self.line_8c_cod_income -
            self.line_8d_foreign_income_exclusion +
            self.line_8e_taxable_hsa +
            self.line_8f_alaska_pfd +
            self.line_8g_jury_duty_pay +
            self.line_8h_prizes_awards +
            self.line_8i_hobby_income +
            self.line_8j_stock_options +
            self.line_8k_personal_property_rental +
            self.line_8l_olympic_prizes +
            self.line_8m_section_951a +
            self.line_8n_gilti +
            self.line_8o_excess_business_loss +
            self.line_8p_able_distribution +
            self.line_8q_scholarship_income -
            self.line_8r_medicaid_waiver_exclusion +
            self.line_8s_nqdc +
            self.line_8t_incarcerated_wages +
            self.line_8z_total
        )


class Schedule1Part2(BaseModel):
    """
    Schedule 1 Part II: Adjustments to Income

    Lines 11-26 flow to Form 1040 Line 10.
    These reduce AGI ("above-the-line" deductions).
    """
    # Line 11: Educator expenses (max $300 per educator, $600 MFJ)
    line_11_educator_expenses: float = Field(
        default=0.0, ge=0, le=600,
        description="Educator expenses (max $300/person, $600 MFJ)"
    )

    # Line 12: Certain business expenses of reservists, performing artists, etc.
    line_12_business_expenses: float = Field(
        default=0.0, ge=0,
        description="Form 2106 employee business expenses (limited)"
    )

    # Line 13: Health savings account deduction (Form 8889)
    line_13_hsa_deduction: float = Field(
        default=0.0, ge=0,
        description="HSA deduction (Form 8889 Line 13)"
    )

    # Line 14: Moving expenses for Armed Forces (Form 3903)
    line_14_moving_expenses: float = Field(
        default=0.0, ge=0,
        description="Moving expenses for military (Form 3903)"
    )

    # Line 15: Deductible part of self-employment tax (1/2 of SE tax)
    line_15_se_tax_deduction: float = Field(
        default=0.0, ge=0,
        description="Deductible part of SE tax (Schedule SE)"
    )

    # Line 16: Self-employed SEP, SIMPLE, and qualified plans
    line_16_sep_simple: float = Field(
        default=0.0, ge=0,
        description="Self-employed retirement contributions"
    )

    # Line 17: Self-employed health insurance deduction
    line_17_se_health_insurance: float = Field(
        default=0.0, ge=0,
        description="Self-employed health insurance deduction"
    )

    # Line 18: Penalty on early withdrawal of savings
    line_18_early_withdrawal_penalty: float = Field(
        default=0.0, ge=0,
        description="Penalty on early withdrawal of savings (Form 1099-INT Box 2)"
    )

    # Line 19a: Alimony paid (divorce before 2019)
    line_19a_alimony_paid: float = Field(
        default=0.0, ge=0,
        description="Alimony paid (pre-2019 divorce only)"
    )
    # Line 19b: Recipient's SSN
    line_19b_recipient_ssn: Optional[str] = Field(
        default=None,
        description="SSN of alimony recipient"
    )
    # Line 19c: Date of original divorce decree
    line_19c_divorce_date: Optional[str] = Field(
        default=None,
        description="Date of divorce decree"
    )

    # Line 20: IRA deduction
    line_20_ira_deduction: float = Field(
        default=0.0, ge=0,
        description="Deductible traditional IRA contribution"
    )

    # Line 21: Student loan interest deduction (max $2,500)
    line_21_student_loan_interest: float = Field(
        default=0.0, ge=0, le=2500,
        description="Student loan interest deduction (max $2,500)"
    )

    # Line 22: Reserved for future use
    line_22_reserved: float = Field(
        default=0.0,
        description="Reserved for future use"
    )

    # Line 23: Archer MSA deduction
    line_23_archer_msa: float = Field(
        default=0.0, ge=0,
        description="Archer MSA deduction (Form 8853)"
    )

    # Line 24a: Jury duty pay given to employer
    line_24a_jury_duty_remit: float = Field(
        default=0.0, ge=0,
        description="Jury duty pay remitted to employer"
    )

    # Line 24b: Deductible expenses related to income from rental of personal property
    line_24b_personal_property_expenses: float = Field(
        default=0.0, ge=0,
        description="Expenses for rental of personal property"
    )

    # Line 24c: Nontaxable amount of value of Olympic medals
    line_24c_olympic_exclusion: float = Field(
        default=0.0, ge=0,
        description="Nontaxable Olympic medal exclusion"
    )

    # Line 24d: Reforestation amortization and expenses
    line_24d_reforestation: float = Field(
        default=0.0, ge=0,
        description="Reforestation amortization (Form T Part IV)"
    )

    # Line 24e: Repayment of supplemental unemployment benefits under Trade Act
    line_24e_unemployment_repay: float = Field(
        default=0.0, ge=0,
        description="Repayment of supplemental unemployment"
    )

    # Line 24f: Contributions by certain chaplains to 403(b) plans
    line_24f_chaplain_403b: float = Field(
        default=0.0, ge=0,
        description="Chaplain 403(b) contributions"
    )

    # Line 24g: Attorney fees for whistleblower/employment discrimination awards
    line_24g_attorney_fees: float = Field(
        default=0.0, ge=0,
        description="Attorney fees (whistleblower/discrimination awards)"
    )

    # Line 24h: Housing deduction from Form 2555
    line_24h_housing_deduction: float = Field(
        default=0.0, ge=0,
        description="Foreign housing deduction (Form 2555)"
    )

    # Line 24i: Excess deductions of section 67(e) expenses from Schedule K-1
    line_24i_section_67e_excess: float = Field(
        default=0.0, ge=0,
        description="Section 67(e) excess deductions from K-1"
    )

    # Line 24j: Deduction for recipients of qualified foster care payments
    line_24j_foster_care_deduction: float = Field(
        default=0.0, ge=0,
        description="Foster care provider deduction"
    )

    # Line 24k: Student loan interest deduction for income-driven repayment
    line_24k_student_loan_idr: float = Field(
        default=0.0, ge=0,
        description="Student loan IDR adjustment"
    )

    # Line 24z: Other adjustments (itemized list)
    line_24z_other_adjustments: List[OtherAdjustmentItem] = Field(
        default_factory=list,
        description="Other adjustment items"
    )

    @computed_field
    @property
    def line_24z_total(self) -> float:
        """Total of Line 24z other adjustments."""
        return sum(item.amount for item in self.line_24z_other_adjustments)

    @computed_field
    @property
    def line_25_total_other_adjustments(self) -> float:
        """Line 25: Total of Lines 24a-24z."""
        return (
            self.line_24a_jury_duty_remit +
            self.line_24b_personal_property_expenses +
            self.line_24c_olympic_exclusion +
            self.line_24d_reforestation +
            self.line_24e_unemployment_repay +
            self.line_24f_chaplain_403b +
            self.line_24g_attorney_fees +
            self.line_24h_housing_deduction +
            self.line_24i_section_67e_excess +
            self.line_24j_foster_care_deduction +
            self.line_24k_student_loan_idr +
            self.line_24z_total
        )

    @computed_field
    @property
    def line_26_total_adjustments(self) -> float:
        """
        Line 26: Total Adjustments to Income.
        Add lines 11-25. This flows to Form 1040 Line 10.
        """
        return (
            self.line_11_educator_expenses +
            self.line_12_business_expenses +
            self.line_13_hsa_deduction +
            self.line_14_moving_expenses +
            self.line_15_se_tax_deduction +
            self.line_16_sep_simple +
            self.line_17_se_health_insurance +
            self.line_18_early_withdrawal_penalty +
            self.line_19a_alimony_paid +
            self.line_20_ira_deduction +
            self.line_21_student_loan_interest +
            self.line_22_reserved +
            self.line_23_archer_msa +
            self.line_25_total_other_adjustments
        )


class Schedule1(BaseModel):
    """
    Schedule 1 (Form 1040) - Additional Income and Adjustments to Income

    Complete model implementing all IRS Schedule 1 line items.

    Flows to Form 1040:
    - Line 9 (Part I Total) -> Form 1040 Line 8
    - Line 26 (Part II Total) -> Form 1040 Line 10
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Part I: Additional Income
    part_1: Schedule1Part1 = Field(
        default_factory=Schedule1Part1,
        description="Part I: Additional Income"
    )

    # Part II: Adjustments to Income
    part_2: Schedule1Part2 = Field(
        default_factory=Schedule1Part2,
        description="Part II: Adjustments to Income"
    )

    def is_required(self) -> bool:
        """
        Determine if Schedule 1 must be filed.

        Required if:
        - Any additional income (Part I)
        - Any adjustments to income (Part II)
        """
        return (
            self.part_1.line_9_total_additional_income != 0 or
            self.part_2.line_26_total_adjustments > 0
        )

    @computed_field
    @property
    def form_1040_line_8(self) -> float:
        """Amount to report on Form 1040 Line 8 (Additional income)."""
        return self.part_1.line_9_total_additional_income

    @computed_field
    @property
    def form_1040_line_10(self) -> float:
        """Amount to report on Form 1040 Line 10 (Adjustments to income)."""
        return self.part_2.line_26_total_adjustments

    @classmethod
    def from_breakdown(cls, breakdown: "CalculationBreakdown", income: Any = None) -> "Schedule1":
        """
        Create Schedule 1 from CalculationBreakdown results.

        Args:
            breakdown: The calculation breakdown from the engine
            income: The Income model (optional, for additional fields)

        Returns:
            Populated Schedule 1
        """
        part1 = Schedule1Part1(
            line_3_business_income=getattr(income, 'self_employment_income', 0) - getattr(income, 'self_employment_expenses', 0) if income else 0,
            line_4_other_gains_losses=breakdown.form_4797_ordinary_income + breakdown.form_4797_section_1231_gain - breakdown.form_4797_section_1231_loss if hasattr(breakdown, 'form_4797_ordinary_income') else 0,
            line_5_schedule_e_income=breakdown.k1_ordinary_income if hasattr(breakdown, 'k1_ordinary_income') else 0,
            line_7_unemployment=getattr(income, 'unemployment_compensation', 0) if income else 0,
            line_8b_gambling_income=breakdown.gambling_income if hasattr(breakdown, 'gambling_income') else 0,
            line_8d_foreign_income_exclusion=breakdown.form_2555_total_exclusion if hasattr(breakdown, 'form_2555_total_exclusion') else 0,
            line_8e_taxable_hsa=breakdown.hsa_taxable_distributions if hasattr(breakdown, 'hsa_taxable_distributions') else 0,
        )

        part2 = Schedule1Part2(
            line_13_hsa_deduction=breakdown.hsa_deduction if hasattr(breakdown, 'hsa_deduction') else 0,
            line_15_se_tax_deduction=breakdown.self_employment_tax / 2 if hasattr(breakdown, 'self_employment_tax') else 0,
            line_17_se_health_insurance=getattr(income, 'self_employed_health_insurance', 0) if income else 0,
            line_21_student_loan_interest=min(getattr(income, 'student_loan_interest', 0), 2500) if income else 0,
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
                "line_1_taxable_refunds": self.part_1.line_1_taxable_refunds,
                "line_2a_alimony_received": self.part_1.line_2a_alimony_received,
                "line_3_business_income": self.part_1.line_3_business_income,
                "line_4_other_gains_losses": self.part_1.line_4_other_gains_losses,
                "line_5_schedule_e_income": self.part_1.line_5_schedule_e_income,
                "line_6_farm_income": self.part_1.line_6_farm_income,
                "line_7_unemployment": self.part_1.line_7_unemployment,
                "line_8a_nol_deduction": self.part_1.line_8a_nol_deduction,
                "line_8b_gambling_income": self.part_1.line_8b_gambling_income,
                "line_8d_foreign_income_exclusion": self.part_1.line_8d_foreign_income_exclusion,
                "line_8e_taxable_hsa": self.part_1.line_8e_taxable_hsa,
                "line_9_total": self.part_1.line_9_total_additional_income,
            },
            "part_2": {
                "line_11_educator_expenses": self.part_2.line_11_educator_expenses,
                "line_13_hsa_deduction": self.part_2.line_13_hsa_deduction,
                "line_15_se_tax_deduction": self.part_2.line_15_se_tax_deduction,
                "line_16_sep_simple": self.part_2.line_16_sep_simple,
                "line_17_se_health_insurance": self.part_2.line_17_se_health_insurance,
                "line_20_ira_deduction": self.part_2.line_20_ira_deduction,
                "line_21_student_loan_interest": self.part_2.line_21_student_loan_interest,
                "line_26_total": self.part_2.line_26_total_adjustments,
            },
            "form_1040_line_8": self.form_1040_line_8,
            "form_1040_line_10": self.form_1040_line_10,
            "is_required": self.is_required(),
        }
