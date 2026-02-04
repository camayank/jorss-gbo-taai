"""
Form 8863 - Education Credits (American Opportunity and Lifetime Learning Credits)
Form 1098-T - Tuition Statement

IRS Form 8863 calculates two education credits:

1. American Opportunity Tax Credit (AOTC) - IRC Section 25A(b)
   - Maximum $2,500 per eligible student ($2,000 + 25% of next $2,000)
   - First 4 years of post-secondary education only
   - Must be enrolled at least half-time
   - 40% refundable (up to $1,000)
   - No felony drug conviction
   - Qualified expenses: tuition, fees, books, supplies, equipment

2. Lifetime Learning Credit (LLC) - IRC Section 25A(c)
   - Maximum $2,000 per tax return (20% of first $10,000 expenses)
   - Any year of post-secondary education
   - No enrollment requirements
   - Nonrefundable
   - Qualified expenses: tuition and fees only

Income Limits (2025):
- AOTC: Phase-out $80,000-$90,000 single, $160,000-$180,000 MFJ
- LLC: Phase-out $80,000-$90,000 single, $160,000-$180,000 MFJ

Form 1098-T: Tuition Statement from eligible educational institutions
- Box 1: Payments received for qualified tuition and related expenses
- Box 4: Adjustments made for a prior year
- Box 5: Scholarships or grants
- Box 6: Adjustments to scholarships or grants for a prior year
- Box 7: Checkbox if Box 1 includes amounts for an academic period beginning January-March
- Box 8: At least half-time student checkbox
- Box 9: Graduate student checkbox
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field, computed_field, model_validator
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class AcademicPeriod(str, Enum):
    """Academic periods for enrollment tracking."""
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


class EnrollmentStatus(str, Enum):
    """Student enrollment status."""
    FULL_TIME = "full_time"  # 12+ credit hours undergraduate, 9+ graduate
    HALF_TIME = "half_time"  # 6+ credit hours undergraduate, 5+ graduate
    LESS_THAN_HALF = "less_than_half_time"


class EducationLevel(str, Enum):
    """Level of education."""
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    PROFESSIONAL = "professional"  # Law, medical, etc.
    VOCATIONAL = "vocational"


class Form1098T(BaseModel):
    """
    Form 1098-T: Tuition Statement

    Issued by eligible educational institutions to report qualified tuition
    and related expenses paid, and scholarships/grants received.
    """
    # Institution information
    institution_name: str = Field(description="Name of educational institution")
    institution_ein: str = Field(default="", description="Institution's EIN")
    institution_address: str = Field(default="", description="Institution's address")

    # Student information
    student_name: str = Field(description="Student's name as shown on Form")
    student_ssn: str = Field(default="", description="Student's SSN")
    student_address: str = Field(default="", description="Student's address")
    account_number: str = Field(default="", description="Account number (institution use)")

    # Tax year
    tax_year: int = Field(default=2025, description="Tax year")

    # Box 1: Payments received for qualified tuition and related expenses
    box_1_payments_received: float = Field(
        default=0.0, ge=0,
        description="Box 1: Payments received for qualified tuition/fees"
    )

    # Box 2: Reserved (not used since 2018)
    # box_2_amounts_billed is no longer reported

    # Box 3: Reserved (not used)

    # Box 4: Adjustments made for a prior year
    box_4_prior_year_adjustments: float = Field(
        default=0.0, ge=0,
        description="Box 4: Adjustments to qualified tuition for prior year (refunds)"
    )

    # Box 5: Scholarships or grants
    box_5_scholarships_grants: float = Field(
        default=0.0, ge=0,
        description="Box 5: Scholarships or grants"
    )

    # Box 6: Adjustments to scholarships or grants for a prior year
    box_6_prior_year_scholarship_adj: float = Field(
        default=0.0, ge=0,
        description="Box 6: Adjustments to scholarships/grants for prior year"
    )

    # Box 7: Next year checkbox
    box_7_includes_next_year: bool = Field(
        default=False,
        description="Box 7: Amount in Box 1 includes amounts for academic period Jan-Mar next year"
    )

    # Box 8: At least half-time student
    box_8_half_time_student: bool = Field(
        default=True,
        description="Box 8: At least half-time student"
    )

    # Box 9: Graduate student
    box_9_graduate_student: bool = Field(
        default=False,
        description="Box 9: Graduate student"
    )

    # Box 10: Insurance contract reimbursement or refund
    box_10_insurance_reimbursement: float = Field(
        default=0.0, ge=0,
        description="Box 10: Insurance contract reimbursement/refund"
    )

    @computed_field
    @property
    def net_qualified_expenses(self) -> float:
        """
        Net qualified tuition and related expenses.
        Box 1 - Box 5 (scholarships reduce qualified expenses).
        """
        return max(0, self.box_1_payments_received - self.box_5_scholarships_grants)

    @computed_field
    @property
    def is_eligible_for_aotc(self) -> bool:
        """Check if student is potentially AOTC eligible based on 1098-T."""
        # Must be at least half-time, cannot be graduate student for AOTC
        return self.box_8_half_time_student and not self.box_9_graduate_student

    @computed_field
    @property
    def is_eligible_for_llc(self) -> bool:
        """Check if student is potentially LLC eligible based on 1098-T."""
        # LLC has no enrollment requirements
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "institution_name": self.institution_name,
            "institution_ein": self.institution_ein,
            "student_name": self.student_name,
            "box_1_payments_received": self.box_1_payments_received,
            "box_4_prior_year_adjustments": self.box_4_prior_year_adjustments,
            "box_5_scholarships_grants": self.box_5_scholarships_grants,
            "box_6_prior_year_scholarship_adj": self.box_6_prior_year_scholarship_adj,
            "box_7_includes_next_year": self.box_7_includes_next_year,
            "box_8_half_time_student": self.box_8_half_time_student,
            "box_9_graduate_student": self.box_9_graduate_student,
            "net_qualified_expenses": self.net_qualified_expenses,
        }


class StudentExpenses(BaseModel):
    """
    Complete student information for Form 8863 education credit calculation.
    Maps to Form 8863 Part III (Students and Expenses).
    """
    # Student identification
    student_name: str = Field(description="Student's legal name")
    student_ssn: str = Field(default="", description="Student's SSN")
    relationship: str = Field(
        default="self",
        description="Relationship to taxpayer: self, spouse, dependent"
    )

    # Form 1098-T
    form_1098t: Optional[Form1098T] = Field(
        default=None,
        description="Form 1098-T from institution"
    )
    has_form_1098t: bool = Field(
        default=True,
        description="Whether Form 1098-T was received (required unless exception)"
    )

    # Institution information (if no 1098-T)
    institution_name: str = Field(default="", description="Name of institution attended")
    institution_ein: str = Field(default="", description="Institution's EIN")

    # Enrollment information
    enrollment_status: EnrollmentStatus = Field(
        default=EnrollmentStatus.FULL_TIME,
        description="Enrollment status during tax year"
    )
    education_level: EducationLevel = Field(
        default=EducationLevel.UNDERGRADUATE,
        description="Level of education"
    )
    is_pursuing_degree: bool = Field(
        default=True,
        description="Enrolled in program leading to degree/credential"
    )

    # AOTC-specific eligibility
    is_first_four_years: bool = Field(
        default=True,
        description="Student has not completed first 4 years of post-secondary education"
    )
    years_aotc_previously_claimed: int = Field(
        default=0, ge=0, le=4,
        description="Number of years AOTC was previously claimed for this student"
    )
    has_felony_drug_conviction: bool = Field(
        default=False,
        description="Student has felony drug conviction (disqualifies from AOTC)"
    )

    # Qualified expenses (Form 8863 Part III)
    tuition_and_fees: float = Field(
        default=0.0, ge=0,
        description="Line 27/28: Adjusted qualified education expenses (tuition and required fees)"
    )
    books_supplies_equipment: float = Field(
        default=0.0, ge=0,
        description="Books, supplies, and equipment required for courses (AOTC only)"
    )

    # Reductions to expenses
    scholarships_grants: float = Field(
        default=0.0, ge=0,
        description="Tax-free scholarships, grants (reduce qualified expenses)"
    )
    employer_assistance: float = Field(
        default=0.0, ge=0,
        description="Tax-free employer educational assistance (reduce qualified expenses)"
    )
    veterans_benefits: float = Field(
        default=0.0, ge=0,
        description="Veterans' educational benefits"
    )
    other_tax_free_assistance: float = Field(
        default=0.0, ge=0,
        description="Other tax-free educational assistance"
    )

    @computed_field
    @property
    def total_tax_free_assistance(self) -> float:
        """Total tax-free assistance that reduces qualified expenses."""
        return (
            self.scholarships_grants +
            self.employer_assistance +
            self.veterans_benefits +
            self.other_tax_free_assistance
        )

    @computed_field
    @property
    def aotc_qualified_expenses(self) -> float:
        """
        Qualified expenses for AOTC.
        Includes tuition, fees, books, supplies, equipment.
        Reduced by tax-free assistance.
        """
        gross = self.tuition_and_fees + self.books_supplies_equipment
        return max(0, gross - self.total_tax_free_assistance)

    @computed_field
    @property
    def llc_qualified_expenses(self) -> float:
        """
        Qualified expenses for LLC.
        Includes tuition and fees only (books only if required for enrollment).
        Reduced by tax-free assistance.
        """
        return max(0, self.tuition_and_fees - self.total_tax_free_assistance)

    @computed_field
    @property
    def is_aotc_eligible(self) -> bool:
        """
        Check if student is eligible for American Opportunity Tax Credit.

        Requirements:
        - Enrolled at least half-time for at least one academic period
        - Pursuing degree or credential
        - First 4 years of post-secondary education
        - AOTC not claimed for 4 years already
        - No felony drug conviction
        - Has Form 1098-T (or exception applies)
        """
        return (
            self.enrollment_status in [EnrollmentStatus.FULL_TIME, EnrollmentStatus.HALF_TIME] and
            self.is_pursuing_degree and
            self.is_first_four_years and
            self.years_aotc_previously_claimed < 4 and
            not self.has_felony_drug_conviction and
            self.has_form_1098t
        )

    @computed_field
    @property
    def is_llc_eligible(self) -> bool:
        """
        Check if student is eligible for Lifetime Learning Credit.

        Requirements (more flexible than AOTC):
        - Any level of post-secondary education
        - No enrollment requirements
        - No limit on years
        """
        return True  # LLC has minimal eligibility requirements


class Form8863Part1(BaseModel):
    """
    Form 8863 Part I: Refundable American Opportunity Credit

    Calculates the refundable portion of AOTC (40%, max $1,000 per student).
    """
    # Line 1: Total from Part III (tentative AOTC per student)
    line_1_tentative_aotc_total: float = Field(
        default=0.0, ge=0,
        description="Line 1: Total tentative AOTC from all students"
    )

    # Line 2: Enter $180,000 MFJ / $90,000 other
    line_2_phaseout_limit: float = Field(
        default=90000.0,
        description="Line 2: Phaseout limit ($180k MFJ, $90k other)"
    )

    # Line 3: MAGI
    line_3_magi: float = Field(
        default=0.0, ge=0,
        description="Line 3: Modified adjusted gross income"
    )

    # Line 4: Subtract Line 3 from Line 2
    @computed_field
    @property
    def line_4_excess(self) -> float:
        """Line 4: Line 2 - Line 3 (if zero or less, no credit)."""
        return max(0, self.line_2_phaseout_limit - self.line_3_magi)

    # Line 5: Enter $20,000 MFJ / $10,000 other
    line_5_phaseout_range: float = Field(
        default=10000.0,
        description="Line 5: Phaseout range ($20k MFJ, $10k other)"
    )

    # Line 6: Divide Line 4 by Line 5 (if 1 or more, enter 1.000)
    @computed_field
    @property
    def line_6_ratio(self) -> float:
        """Line 6: Phaseout ratio (Line 4 / Line 5, max 1.000)."""
        # If phaseout limit is 0 (MFS), no credit allowed
        if self.line_2_phaseout_limit == 0:
            return 0.0
        if self.line_5_phaseout_range == 0:
            return 1.0
        ratio = self.line_4_excess / self.line_5_phaseout_range
        return min(1.0, ratio)

    # Line 7: Multiply Line 1 by Line 6
    @computed_field
    @property
    def line_7_aotc_after_phaseout(self) -> float:
        """Line 7: AOTC after income phaseout."""
        return float(money(self.line_1_tentative_aotc_total * self.line_6_ratio))

    # Line 8: Refundable portion (40% of Line 7)
    @computed_field
    @property
    def line_8_refundable_aotc(self) -> float:
        """Line 8: Refundable American Opportunity Credit (40% of Line 7)."""
        return float(money(self.line_7_aotc_after_phaseout * 0.40))


class Form8863Part2(BaseModel):
    """
    Form 8863 Part II: Nonrefundable Education Credits

    Calculates AOTC nonrefundable portion and Lifetime Learning Credit.
    """
    # Line 9: From Part I Line 7 (AOTC after phaseout)
    line_9_aotc_after_phaseout: float = Field(
        default=0.0, ge=0,
        description="Line 9: AOTC from Part I Line 7"
    )

    # Line 10: From Part I Line 8 (refundable portion)
    line_10_refundable_aotc: float = Field(
        default=0.0, ge=0,
        description="Line 10: Refundable AOTC from Part I Line 8"
    )

    # Line 11: Subtract Line 10 from Line 9 (nonrefundable AOTC)
    @computed_field
    @property
    def line_11_nonrefundable_aotc(self) -> float:
        """Line 11: Nonrefundable AOTC (Line 9 - Line 10)."""
        return max(0, self.line_9_aotc_after_phaseout - self.line_10_refundable_aotc)

    # Line 12-17: LLC calculation
    # Line 12: Tentative LLC (from Part III)
    line_12_tentative_llc: float = Field(
        default=0.0, ge=0,
        description="Line 12: Tentative Lifetime Learning Credit"
    )

    # Line 13: Phaseout limit ($180k MFJ, $90k other)
    line_13_phaseout_limit: float = Field(
        default=90000.0,
        description="Line 13: LLC phaseout limit"
    )

    # Line 14: MAGI
    line_14_magi: float = Field(
        default=0.0, ge=0,
        description="Line 14: MAGI for LLC"
    )

    # Line 15: Subtract Line 14 from Line 13
    @computed_field
    @property
    def line_15_excess(self) -> float:
        """Line 15: Line 13 - Line 14."""
        return max(0, self.line_13_phaseout_limit - self.line_14_magi)

    # Line 16: Phaseout range ($20k MFJ, $10k other)
    line_16_phaseout_range: float = Field(
        default=10000.0,
        description="Line 16: LLC phaseout range"
    )

    # Line 17: Divide Line 15 by Line 16
    @computed_field
    @property
    def line_17_ratio(self) -> float:
        """Line 17: LLC phaseout ratio."""
        # If phaseout limit is 0 (MFS), no credit allowed
        if self.line_13_phaseout_limit == 0:
            return 0.0
        if self.line_16_phaseout_range == 0:
            return 1.0
        ratio = self.line_15_excess / self.line_16_phaseout_range
        return min(1.0, ratio)

    # Line 18: LLC after phaseout
    @computed_field
    @property
    def line_18_llc_after_phaseout(self) -> float:
        """Line 18: LLC after income phaseout."""
        return float(money(self.line_12_tentative_llc * self.line_17_ratio))

    # Line 19: Total nonrefundable education credits
    @computed_field
    @property
    def line_19_total_nonrefundable(self) -> float:
        """Line 19: Total nonrefundable education credits (Line 11 + Line 18)."""
        return self.line_11_nonrefundable_aotc + self.line_18_llc_after_phaseout


class Form8863(BaseModel):
    """
    Form 8863 - Education Credits (American Opportunity and Lifetime Learning Credits)

    Complete implementation of IRS Form 8863 with:
    - AOTC calculation ($2,500 max per student, 40% refundable)
    - LLC calculation ($2,000 max per return)
    - Income phaseout calculations
    - Per-student tracking
    """
    tax_year: int = Field(default=2025, description="Tax year")
    filing_status: str = Field(default="single", description="Filing status")

    # Student information (Part III)
    students: List[StudentExpenses] = Field(
        default_factory=list,
        description="Students claiming education credits"
    )

    # MAGI for phaseout calculation
    magi: float = Field(
        default=0.0, ge=0,
        description="Modified AGI for education credit phaseout"
    )

    # Part I and II are computed based on students

    def _get_phaseout_limits(self) -> Tuple[float, float]:
        """
        Get phaseout limits based on filing status.

        Returns:
            Tuple of (phaseout_start, phaseout_range)

        2025 AOTC and LLC Phaseouts:
        - Single/HOH: $80,000 - $90,000
        - MFJ: $160,000 - $180,000
        - MFS: Cannot claim education credits
        """
        if self.filing_status.lower() in ["married_joint", "married_filing_jointly", "mfj"]:
            return (180000.0, 20000.0)
        elif self.filing_status.lower() in ["married_separate", "married_filing_separately", "mfs"]:
            return (0.0, 0.0)  # Not eligible
        else:
            return (90000.0, 10000.0)

    @computed_field
    @property
    def is_eligible_for_credits(self) -> bool:
        """Check if taxpayer can claim education credits (MFS cannot)."""
        return self.filing_status.lower() not in ["married_separate", "married_filing_separately", "mfs"]

    def calculate_aotc_per_student(self, student: StudentExpenses) -> Dict[str, Any]:
        """
        Calculate AOTC for a single student.

        AOTC = 100% of first $2,000 + 25% of next $2,000 = $2,500 max

        Args:
            student: Student expense information

        Returns:
            Dict with calculation breakdown
        """
        result = {
            "student_name": student.student_name,
            "is_eligible": student.is_aotc_eligible,
            "qualified_expenses": student.aotc_qualified_expenses,
            "tentative_credit": 0.0,
            "calculation_note": ""
        }

        if not student.is_aotc_eligible:
            result["calculation_note"] = "Student not eligible for AOTC"
            return result

        expenses = student.aotc_qualified_expenses

        # AOTC formula: 100% of first $2,000 + 25% of next $2,000
        if expenses <= 0:
            result["tentative_credit"] = 0.0
            result["calculation_note"] = "No qualified expenses"
        elif expenses <= 2000:
            result["tentative_credit"] = expenses
            result["calculation_note"] = f"100% of ${expenses:.2f}"
        elif expenses <= 4000:
            first_tier = 2000.0
            second_tier = (expenses - 2000) * 0.25
            result["tentative_credit"] = first_tier + second_tier
            result["calculation_note"] = f"$2,000 + 25% of ${expenses - 2000:.2f}"
        else:
            result["tentative_credit"] = 2500.0  # Maximum
            result["calculation_note"] = "Maximum AOTC reached ($2,500)"

        return result

    def calculate_llc_total(self) -> Dict[str, Any]:
        """
        Calculate Lifetime Learning Credit (per return, not per student).

        LLC = 20% of first $10,000 qualified expenses = $2,000 max

        IMPORTANT: You cannot claim both AOTC and LLC for the same student.
        LLC only includes expenses from students NOT claiming AOTC.

        Returns:
            Dict with calculation breakdown
        """
        # Sum qualified expenses for students NOT claiming AOTC
        # (cannot claim both AOTC and LLC for same student)
        total_expenses = sum(
            s.llc_qualified_expenses
            for s in self.students
            if s.is_llc_eligible and not s.is_aotc_eligible
        )

        # LLC is 20% of up to $10,000
        capped_expenses = min(total_expenses, 10000.0)
        tentative_llc = capped_expenses * 0.20

        return {
            "total_qualified_expenses": total_expenses,
            "capped_expenses": capped_expenses,
            "tentative_credit": tentative_llc,
            "max_credit": 2000.0,
        }

    @computed_field
    @property
    def part1(self) -> Form8863Part1:
        """Calculate Part I: Refundable American Opportunity Credit."""
        phaseout_limit, phaseout_range = self._get_phaseout_limits()

        # Sum tentative AOTC for all eligible students
        total_tentative_aotc = sum(
            self.calculate_aotc_per_student(s)["tentative_credit"]
            for s in self.students
        )

        return Form8863Part1(
            line_1_tentative_aotc_total=total_tentative_aotc,
            line_2_phaseout_limit=phaseout_limit,
            line_3_magi=self.magi,
            line_5_phaseout_range=phaseout_range,
        )

    @computed_field
    @property
    def part2(self) -> Form8863Part2:
        """Calculate Part II: Nonrefundable Education Credits."""
        phaseout_limit, phaseout_range = self._get_phaseout_limits()
        part1 = self.part1
        llc_calc = self.calculate_llc_total()

        return Form8863Part2(
            line_9_aotc_after_phaseout=part1.line_7_aotc_after_phaseout,
            line_10_refundable_aotc=part1.line_8_refundable_aotc,
            line_12_tentative_llc=llc_calc["tentative_credit"],
            line_13_phaseout_limit=phaseout_limit,
            line_14_magi=self.magi,
            line_16_phaseout_range=phaseout_range,
        )

    @computed_field
    @property
    def total_aotc(self) -> float:
        """Total American Opportunity Tax Credit (refundable + nonrefundable)."""
        return self.part1.line_7_aotc_after_phaseout

    @computed_field
    @property
    def refundable_aotc(self) -> float:
        """Refundable portion of AOTC (40%, max $1,000 per student)."""
        return self.part1.line_8_refundable_aotc

    @computed_field
    @property
    def nonrefundable_aotc(self) -> float:
        """Nonrefundable portion of AOTC."""
        return self.part2.line_11_nonrefundable_aotc

    @computed_field
    @property
    def total_llc(self) -> float:
        """Total Lifetime Learning Credit after phaseout."""
        return self.part2.line_18_llc_after_phaseout

    @computed_field
    @property
    def total_nonrefundable_credits(self) -> float:
        """Total nonrefundable education credits (Schedule 3 Line 3)."""
        return self.part2.line_19_total_nonrefundable

    @computed_field
    @property
    def total_refundable_credits(self) -> float:
        """Total refundable education credits (Schedule 3 Line 13)."""
        return self.refundable_aotc

    @computed_field
    @property
    def total_education_credits(self) -> float:
        """Total education credits (refundable + nonrefundable)."""
        return self.total_refundable_credits + self.total_nonrefundable_credits

    def get_per_student_breakdown(self) -> List[Dict[str, Any]]:
        """Get AOTC calculation breakdown per student."""
        return [self.calculate_aotc_per_student(s) for s in self.students]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "magi": self.magi,
            "student_count": len(self.students),
            "is_eligible": self.is_eligible_for_credits,
            "part_1": {
                "line_1_tentative_aotc": self.part1.line_1_tentative_aotc_total,
                "line_7_aotc_after_phaseout": self.part1.line_7_aotc_after_phaseout,
                "line_8_refundable_aotc": self.part1.line_8_refundable_aotc,
            },
            "part_2": {
                "line_11_nonrefundable_aotc": self.part2.line_11_nonrefundable_aotc,
                "line_12_tentative_llc": self.part2.line_12_tentative_llc,
                "line_18_llc_after_phaseout": self.part2.line_18_llc_after_phaseout,
                "line_19_total_nonrefundable": self.part2.line_19_total_nonrefundable,
            },
            "summary": {
                "total_aotc": self.total_aotc,
                "refundable_aotc": self.refundable_aotc,
                "nonrefundable_aotc": self.nonrefundable_aotc,
                "total_llc": self.total_llc,
                "total_nonrefundable": self.total_nonrefundable_credits,
                "total_refundable": self.total_refundable_credits,
                "total_education_credits": self.total_education_credits,
            },
            "per_student": self.get_per_student_breakdown(),
        }


# Convenience function for quick credit calculation
def calculate_education_credits(
    students: List[StudentExpenses],
    magi: float,
    filing_status: str,
    tax_year: int = 2025
) -> Dict[str, Any]:
    """
    Calculate education credits for given students and income.

    Args:
        students: List of student expense information
        magi: Modified adjusted gross income
        filing_status: Filing status
        tax_year: Tax year

    Returns:
        Dictionary with credit amounts and breakdown
    """
    form = Form8863(
        tax_year=tax_year,
        filing_status=filing_status,
        students=students,
        magi=magi
    )
    return form.to_dict()
