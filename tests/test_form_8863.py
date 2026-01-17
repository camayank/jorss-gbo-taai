"""
Comprehensive tests for Form 8863 (Education Credits) and Form 1098-T (Tuition Statement)

Tests cover:
- American Opportunity Tax Credit (AOTC) calculation
- Lifetime Learning Credit (LLC) calculation
- Income phaseout calculations
- Form 1098-T processing
- Per-student vs per-return credits
- Refundable vs nonrefundable portions
- Eligibility requirements
"""

import pytest
from models.form_8863 import (
    Form8863, Form1098T, StudentExpenses,
    Form8863Part1, Form8863Part2,
    EnrollmentStatus, EducationLevel,
    calculate_education_credits
)


# =============================================================================
# Form 1098-T Tests
# =============================================================================

class TestForm1098T:
    """Test Form 1098-T Tuition Statement."""

    def test_basic_form_1098t(self):
        """Test basic Form 1098-T creation."""
        form = Form1098T(
            institution_name="State University",
            student_name="John Doe",
            box_1_payments_received=15000.00,
            box_5_scholarships_grants=5000.00
        )
        assert form.net_qualified_expenses == 10000.00

    def test_scholarships_exceed_tuition(self):
        """Test when scholarships exceed tuition (no expenses)."""
        form = Form1098T(
            institution_name="Community College",
            student_name="Jane Smith",
            box_1_payments_received=3000.00,
            box_5_scholarships_grants=5000.00
        )
        assert form.net_qualified_expenses == 0.0

    def test_half_time_student_aotc_eligible(self):
        """Test half-time student AOTC eligibility."""
        form = Form1098T(
            institution_name="University",
            student_name="Student",
            box_1_payments_received=10000.00,
            box_8_half_time_student=True,
            box_9_graduate_student=False
        )
        assert form.is_eligible_for_aotc is True
        assert form.is_eligible_for_llc is True

    def test_graduate_student_not_aotc_eligible(self):
        """Test graduate student not AOTC eligible."""
        form = Form1098T(
            institution_name="Graduate School",
            student_name="Grad Student",
            box_1_payments_received=20000.00,
            box_8_half_time_student=True,
            box_9_graduate_student=True
        )
        assert form.is_eligible_for_aotc is False
        assert form.is_eligible_for_llc is True

    def test_prior_year_adjustments(self):
        """Test prior year adjustments (Box 4 and 6)."""
        form = Form1098T(
            institution_name="University",
            student_name="Student",
            box_1_payments_received=12000.00,
            box_4_prior_year_adjustments=500.00,
            box_5_scholarships_grants=2000.00,
            box_6_prior_year_scholarship_adj=200.00
        )
        assert form.box_4_prior_year_adjustments == 500.00
        assert form.box_6_prior_year_scholarship_adj == 200.00

    def test_box_7_next_year_amounts(self):
        """Test Box 7 checkbox for next year amounts."""
        form = Form1098T(
            institution_name="University",
            student_name="Student",
            box_1_payments_received=8000.00,
            box_7_includes_next_year=True
        )
        assert form.box_7_includes_next_year is True


# =============================================================================
# Student Expenses Tests
# =============================================================================

class TestStudentExpenses:
    """Test StudentExpenses model."""

    def test_aotc_qualified_expenses(self):
        """Test AOTC qualified expense calculation."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            books_supplies_equipment=1500.00,
            scholarships_grants=3000.00
        )
        # AOTC includes books: 10000 + 1500 - 3000 = 8500
        assert student.aotc_qualified_expenses == 8500.00

    def test_llc_qualified_expenses(self):
        """Test LLC qualified expense calculation (no books)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            books_supplies_equipment=1500.00,
            scholarships_grants=3000.00
        )
        # LLC excludes books: 10000 - 3000 = 7000
        assert student.llc_qualified_expenses == 7000.00

    def test_total_tax_free_assistance(self):
        """Test total tax-free assistance calculation."""
        student = StudentExpenses(
            student_name="Student",
            scholarships_grants=5000.00,
            employer_assistance=2500.00,
            veterans_benefits=1000.00,
            other_tax_free_assistance=500.00
        )
        assert student.total_tax_free_assistance == 9000.00

    def test_aotc_eligible_full_time(self):
        """Test AOTC eligibility for full-time student."""
        student = StudentExpenses(
            student_name="Freshman",
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_pursuing_degree=True,
            is_first_four_years=True,
            years_aotc_previously_claimed=0,
            has_felony_drug_conviction=False,
            has_form_1098t=True
        )
        assert student.is_aotc_eligible is True

    def test_aotc_not_eligible_fifth_year(self):
        """Test AOTC not eligible after 4 years."""
        student = StudentExpenses(
            student_name="Fifth Year",
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_first_four_years=False
        )
        assert student.is_aotc_eligible is False

    def test_aotc_not_eligible_4_years_claimed(self):
        """Test AOTC not eligible when claimed 4 years already."""
        student = StudentExpenses(
            student_name="Senior",
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_first_four_years=True,
            years_aotc_previously_claimed=4
        )
        assert student.is_aotc_eligible is False

    def test_aotc_not_eligible_drug_conviction(self):
        """Test AOTC not eligible with felony drug conviction."""
        student = StudentExpenses(
            student_name="Student",
            enrollment_status=EnrollmentStatus.FULL_TIME,
            has_felony_drug_conviction=True
        )
        assert student.is_aotc_eligible is False

    def test_aotc_not_eligible_less_than_half_time(self):
        """Test AOTC not eligible for less than half-time."""
        student = StudentExpenses(
            student_name="Part-time Student",
            enrollment_status=EnrollmentStatus.LESS_THAN_HALF
        )
        assert student.is_aotc_eligible is False

    def test_llc_always_eligible(self):
        """Test LLC is always eligible (minimal requirements)."""
        student = StudentExpenses(
            student_name="Any Student",
            enrollment_status=EnrollmentStatus.LESS_THAN_HALF,
            is_first_four_years=False
        )
        assert student.is_llc_eligible is True


# =============================================================================
# AOTC Calculation Tests
# =============================================================================

class TestAOTCCalculation:
    """Test American Opportunity Tax Credit calculations."""

    def test_aotc_under_2000_expenses(self):
        """Test AOTC with expenses under $2,000 (100% credit)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=1500.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        result = form.calculate_aotc_per_student(student)
        assert result["tentative_credit"] == 1500.00

    def test_aotc_exactly_2000_expenses(self):
        """Test AOTC with exactly $2,000 expenses."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=2000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        result = form.calculate_aotc_per_student(student)
        assert result["tentative_credit"] == 2000.00

    def test_aotc_between_2000_and_4000(self):
        """Test AOTC with expenses between $2,000 and $4,000."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=3000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        result = form.calculate_aotc_per_student(student)
        # $2,000 + 25% of $1,000 = $2,250
        assert result["tentative_credit"] == 2250.00

    def test_aotc_maximum_credit(self):
        """Test AOTC maximum at $4,000+ expenses."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        result = form.calculate_aotc_per_student(student)
        # Maximum AOTC is $2,500
        assert result["tentative_credit"] == 2500.00

    def test_aotc_refundable_portion(self):
        """Test 40% refundable portion of AOTC."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        # 40% of $2,500 = $1,000
        assert form.refundable_aotc == 1000.00
        assert form.nonrefundable_aotc == 1500.00

    def test_aotc_multiple_students(self):
        """Test AOTC with multiple students (per-student credit)."""
        students = [
            StudentExpenses(
                student_name="Student 1",
                tuition_and_fees=8000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME
            ),
            StudentExpenses(
                student_name="Student 2",
                tuition_and_fees=6000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME
            ),
        ]
        form = Form8863(
            students=students,
            magi=100000.00,
            filing_status="married_joint"
        )
        # Each student gets $2,500 max = $5,000 total
        assert form.total_aotc == 5000.00
        # 40% refundable = $2,000
        assert form.refundable_aotc == 2000.00


# =============================================================================
# LLC Calculation Tests
# =============================================================================

class TestLLCCalculation:
    """Test Lifetime Learning Credit calculations."""

    def test_llc_under_10000_expenses(self):
        """Test LLC with expenses under $10,000."""
        student = StudentExpenses(
            student_name="Grad Student",
            tuition_and_fees=5000.00,
            is_first_four_years=False,  # Not AOTC eligible, so LLC applies
            education_level=EducationLevel.GRADUATE
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        llc = form.calculate_llc_total()
        # 20% of $5,000 = $1,000
        assert llc["tentative_credit"] == 1000.00

    def test_llc_maximum_credit(self):
        """Test LLC maximum at $10,000 expenses."""
        student = StudentExpenses(
            student_name="Grad Student",
            tuition_and_fees=25000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_first_four_years=False,
            education_level=EducationLevel.GRADUATE
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        # LLC max is $2,000 (20% of $10,000)
        assert form.part2.line_12_tentative_llc == 2000.00

    def test_llc_per_return_not_per_student(self):
        """Test LLC is per-return, not per-student."""
        students = [
            StudentExpenses(
                student_name="Student 1",
                tuition_and_fees=8000.00,
                is_first_four_years=False  # Forces LLC
            ),
            StudentExpenses(
                student_name="Student 2",
                tuition_and_fees=8000.00,
                is_first_four_years=False
            ),
        ]
        form = Form8863(
            students=students,
            magi=50000.00,
            filing_status="single"
        )
        llc = form.calculate_llc_total()
        # Combined $16,000 expenses, but capped at $10,000
        # 20% of $10,000 = $2,000 max
        assert llc["total_qualified_expenses"] == 16000.00
        assert llc["capped_expenses"] == 10000.00
        assert llc["tentative_credit"] == 2000.00


# =============================================================================
# Income Phaseout Tests
# =============================================================================

class TestIncomePhaseout:
    """Test income phaseout calculations."""

    def test_single_below_phaseout(self):
        """Test single filer below phaseout ($80,000)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=70000.00,
            filing_status="single"
        )
        # Full credit (no phaseout)
        assert form.total_aotc == 2500.00

    def test_single_in_phaseout_range(self):
        """Test single filer in phaseout range ($80,000-$90,000)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=85000.00,  # Midpoint of phaseout
            filing_status="single"
        )
        # 50% of credit due to phaseout
        assert form.total_aotc == 1250.00

    def test_single_above_phaseout(self):
        """Test single filer above phaseout ($90,000)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=95000.00,
            filing_status="single"
        )
        # No credit (phased out)
        assert form.total_aotc == 0.0

    def test_mfj_below_phaseout(self):
        """Test MFJ below phaseout ($160,000)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=150000.00,
            filing_status="married_joint"
        )
        # Full credit
        assert form.total_aotc == 2500.00

    def test_mfj_in_phaseout_range(self):
        """Test MFJ in phaseout range ($160,000-$180,000)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=170000.00,  # Midpoint
            filing_status="married_joint"
        )
        # 50% of credit
        assert form.total_aotc == 1250.00

    def test_mfj_above_phaseout(self):
        """Test MFJ above phaseout ($180,000)."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=190000.00,
            filing_status="married_joint"
        )
        assert form.total_aotc == 0.0

    def test_mfs_not_eligible(self):
        """Test Married Filing Separately cannot claim credits."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="married_separate"
        )
        assert form.is_eligible_for_credits is False
        assert form.total_aotc == 0.0
        assert form.total_llc == 0.0


# =============================================================================
# Combined Credit Tests
# =============================================================================

class TestCombinedCredits:
    """Test combined AOTC and LLC scenarios."""

    def test_aotc_and_llc_different_students(self):
        """Test AOTC for one student, LLC for another."""
        students = [
            # Undergraduate - AOTC eligible
            StudentExpenses(
                student_name="Undergrad",
                tuition_and_fees=8000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME,
                is_first_four_years=True
            ),
            # Graduate - LLC only
            StudentExpenses(
                student_name="Grad Student",
                tuition_and_fees=15000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME,
                is_first_four_years=False,
                education_level=EducationLevel.GRADUATE
            ),
        ]
        form = Form8863(
            students=students,
            magi=100000.00,
            filing_status="married_joint"
        )

        # AOTC for undergrad: $2,500
        # LLC for grad: capped at $2,000
        assert form.total_aotc == 2500.00
        assert form.part2.line_12_tentative_llc == 2000.00

    def test_choose_aotc_over_llc_when_eligible(self):
        """Test that AOTC is better than LLC when eligible."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=4000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_first_four_years=True
        )

        # Calculate AOTC
        form_aotc = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )

        # AOTC: $2,500 (including $1,000 refundable)
        # LLC would be: 20% of $4,000 = $800
        assert form_aotc.total_aotc == 2500.00
        assert form_aotc.refundable_aotc == 1000.00

    def test_total_education_credits(self):
        """Test total education credits calculation."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )

        # AOTC only for AOTC-eligible student
        assert form.total_education_credits == 2500.00
        assert form.total_nonrefundable_credits == 1500.00
        assert form.total_refundable_credits == 1000.00


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_no_students(self):
        """Test with no students."""
        form = Form8863(
            students=[],
            magi=50000.00,
            filing_status="single"
        )
        assert form.total_aotc == 0.0
        assert form.total_llc == 0.0

    def test_zero_expenses(self):
        """Test with zero qualified expenses."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=0.0,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=50000.00,
            filing_status="single"
        )
        assert form.total_aotc == 0.0

    def test_scholarships_exceed_expenses(self):
        """Test when scholarships exceed expenses."""
        student = StudentExpenses(
            student_name="Full Scholarship",
            tuition_and_fees=10000.00,
            scholarships_grants=12000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        assert student.aotc_qualified_expenses == 0.0
        assert student.llc_qualified_expenses == 0.0

    def test_exactly_at_phaseout_start(self):
        """Test MAGI exactly at phaseout start."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=80000.00,  # Exactly at single phaseout start
            filing_status="single"
        )
        # Full credit (phaseout starts above this)
        assert form.total_aotc == 2500.00

    def test_exactly_at_phaseout_end(self):
        """Test MAGI exactly at phaseout end."""
        student = StudentExpenses(
            student_name="Student",
            tuition_and_fees=10000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            students=[student],
            magi=90000.00,  # Exactly at single phaseout end
            filing_status="single"
        )
        # Zero credit
        assert form.total_aotc == 0.0

    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        student = StudentExpenses(
            student_name="Test Student",
            tuition_and_fees=5000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME
        )
        form = Form8863(
            tax_year=2025,
            students=[student],
            magi=60000.00,
            filing_status="single"
        )
        d = form.to_dict()
        assert d["tax_year"] == 2025
        assert d["student_count"] == 1
        assert "summary" in d
        assert "per_student" in d

    def test_calculate_education_credits_function(self):
        """Test convenience function."""
        students = [
            StudentExpenses(
                student_name="Student",
                tuition_and_fees=8000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME
            )
        ]
        result = calculate_education_credits(
            students=students,
            magi=75000.00,
            filing_status="single",
            tax_year=2025
        )
        assert result["summary"]["total_aotc"] == 2500.00


# =============================================================================
# Real-World Scenarios
# =============================================================================

class TestRealWorldScenarios:
    """Test real-world tax scenarios."""

    def test_typical_undergraduate_family(self):
        """Test typical family with undergraduate student."""
        student = StudentExpenses(
            student_name="College Freshman",
            tuition_and_fees=12000.00,
            books_supplies_equipment=1200.00,
            scholarships_grants=3000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_first_four_years=True,
            years_aotc_previously_claimed=0
        )
        form = Form8863(
            students=[student],
            magi=120000.00,
            filing_status="married_joint"
        )

        # Net expenses: 12000 + 1200 - 3000 = 10200
        # AOTC: $2,500 (max)
        # Full credit (below $160k phaseout)
        assert form.total_aotc == 2500.00
        assert form.refundable_aotc == 1000.00
        assert form.nonrefundable_aotc == 1500.00

    def test_grad_student_with_phaseout(self):
        """Test graduate student with income phaseout."""
        student = StudentExpenses(
            student_name="MBA Student",
            tuition_and_fees=50000.00,
            enrollment_status=EnrollmentStatus.FULL_TIME,
            is_first_four_years=False,
            education_level=EducationLevel.GRADUATE
        )
        form = Form8863(
            students=[student],
            magi=85000.00,  # In phaseout range
            filing_status="single"
        )

        # LLC only (not AOTC eligible)
        # Tentative: $2,000 (20% of $10,000 cap)
        # 50% phaseout = $1,000
        assert form.part2.line_12_tentative_llc == 2000.00
        assert form.total_llc == 1000.00

    def test_multiple_children_in_college(self):
        """Test family with 2 children in college."""
        students = [
            StudentExpenses(
                student_name="Child 1 - Junior",
                tuition_and_fees=15000.00,
                scholarships_grants=5000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME,
                is_first_four_years=True,
                years_aotc_previously_claimed=2
            ),
            StudentExpenses(
                student_name="Child 2 - Freshman",
                tuition_and_fees=12000.00,
                scholarships_grants=2000.00,
                enrollment_status=EnrollmentStatus.FULL_TIME,
                is_first_four_years=True,
                years_aotc_previously_claimed=0
            ),
        ]
        form = Form8863(
            students=students,
            magi=150000.00,
            filing_status="married_joint"
        )

        # Both AOTC eligible
        # Child 1: $2,500, Child 2: $2,500
        # Total: $5,000
        # Refundable: 40% = $2,000
        assert form.total_aotc == 5000.00
        assert form.refundable_aotc == 2000.00
        assert form.nonrefundable_aotc == 3000.00

    def test_part_time_vocational_student(self):
        """Test part-time vocational student (LLC only)."""
        student = StudentExpenses(
            student_name="Vocational Student",
            tuition_and_fees=4000.00,
            enrollment_status=EnrollmentStatus.LESS_THAN_HALF,
            education_level=EducationLevel.VOCATIONAL,
            is_first_four_years=True
        )
        form = Form8863(
            students=[student],
            magi=40000.00,
            filing_status="single"
        )

        # Not AOTC eligible (less than half-time)
        assert student.is_aotc_eligible is False
        # LLC: 20% of $4,000 = $800
        assert form.total_llc == 800.00
        assert form.total_aotc == 0.0
