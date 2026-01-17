"""
Comprehensive tests for Schedule 1, 2, 3 (Form 1040)

Tests cover:
- Schedule 1: Additional Income and Adjustments to Income
- Schedule 2: Additional Taxes
- Schedule 3: Additional Credits and Payments
- Form 1040 routing logic
- IRS line item calculations
"""

import pytest
from models.schedule_1 import (
    Schedule1, Schedule1Part1, Schedule1Part2,
    OtherIncomeType, OtherAdjustmentType,
    OtherIncomeItem, OtherAdjustmentItem
)
from models.schedule_2 import (
    Schedule2, Schedule2Part1, Schedule2Part2,
    OtherTaxType, OtherTaxItem
)
from models.schedule_3 import (
    Schedule3, Schedule3Part1, Schedule3Part2,
    NonrefundableCreditType, RefundableCreditType,
    NonrefundableCreditItem, RefundableCreditItem
)


# =============================================================================
# Schedule 1 Tests
# =============================================================================

class TestSchedule1Part1:
    """Test Schedule 1 Part I: Additional Income."""

    def test_basic_business_income(self):
        """Test business income from Schedule C."""
        part1 = Schedule1Part1(line_3_business_income=50000)
        assert part1.line_9_total_additional_income == 50000

    def test_business_loss(self):
        """Test business loss (negative income)."""
        part1 = Schedule1Part1(line_3_business_income=-10000)
        assert part1.line_9_total_additional_income == -10000

    def test_unemployment_compensation(self):
        """Test unemployment compensation."""
        part1 = Schedule1Part1(line_7_unemployment=12000)
        assert part1.line_9_total_additional_income == 12000

    def test_gambling_income(self):
        """Test gambling winnings."""
        part1 = Schedule1Part1(line_8b_gambling_income=5000)
        assert part1.line_9_total_additional_income == 5000

    def test_foreign_income_exclusion_reduces_income(self):
        """Test that foreign earned income exclusion reduces total."""
        part1 = Schedule1Part1(
            line_3_business_income=150000,
            line_8d_foreign_income_exclusion=126500  # 2024 max exclusion
        )
        assert part1.line_9_total_additional_income == 150000 - 126500

    def test_alimony_received_pre_2019(self):
        """Test alimony received (divorce before 2019)."""
        part1 = Schedule1Part1(
            line_2a_alimony_received=24000,
            line_2b_divorce_date="2018-06-15"
        )
        assert part1.line_9_total_additional_income == 24000

    def test_schedule_e_rental_income(self):
        """Test rental/K-1 income from Schedule E."""
        part1 = Schedule1Part1(line_5_schedule_e_income=35000)
        assert part1.line_9_total_additional_income == 35000

    def test_form_4797_gains(self):
        """Test gains from Form 4797 (business property sales)."""
        part1 = Schedule1Part1(line_4_other_gains_losses=25000)
        assert part1.line_9_total_additional_income == 25000

    def test_nol_deduction_reduces_income(self):
        """Test NOL deduction reduces total income."""
        part1 = Schedule1Part1(
            line_3_business_income=100000,
            line_8a_nol_deduction=30000
        )
        assert part1.line_9_total_additional_income == 100000 - 30000

    def test_multiple_income_sources(self):
        """Test combining multiple income sources."""
        part1 = Schedule1Part1(
            line_3_business_income=75000,
            line_5_schedule_e_income=20000,
            line_7_unemployment=8000,
            line_8b_gambling_income=2000,
        )
        assert part1.line_9_total_additional_income == 105000

    def test_other_income_items(self):
        """Test other income items (Line 8z)."""
        part1 = Schedule1Part1(
            line_8z_other_income=[
                OtherIncomeItem(
                    income_type=OtherIncomeType.PRIZES_AWARDS,
                    description="Contest prize",
                    amount=5000
                ),
                OtherIncomeItem(
                    income_type=OtherIncomeType.JURY_DUTY,
                    description="Jury duty pay",
                    amount=150
                )
            ]
        )
        assert part1.line_8z_total == 5150
        assert part1.line_9_total_additional_income == 5150

    def test_taxable_hsa_distribution(self):
        """Test taxable HSA distribution."""
        part1 = Schedule1Part1(line_8e_taxable_hsa=2000)
        assert part1.line_9_total_additional_income == 2000


class TestSchedule1Part2:
    """Test Schedule 1 Part II: Adjustments to Income."""

    def test_educator_expenses(self):
        """Test educator expense deduction (max $300)."""
        part2 = Schedule1Part2(line_11_educator_expenses=300)
        assert part2.line_26_total_adjustments == 300

    def test_hsa_deduction(self):
        """Test HSA contribution deduction."""
        part2 = Schedule1Part2(line_13_hsa_deduction=4150)  # 2024 individual limit
        assert part2.line_26_total_adjustments == 4150

    def test_self_employment_tax_deduction(self):
        """Test deductible portion of SE tax (1/2)."""
        # If SE tax is $15,000, deduction is $7,500
        part2 = Schedule1Part2(line_15_se_tax_deduction=7500)
        assert part2.line_26_total_adjustments == 7500

    def test_sep_simple_contribution(self):
        """Test SEP/SIMPLE retirement contributions."""
        part2 = Schedule1Part2(line_16_sep_simple=25000)
        assert part2.line_26_total_adjustments == 25000

    def test_self_employed_health_insurance(self):
        """Test self-employed health insurance deduction."""
        part2 = Schedule1Part2(line_17_se_health_insurance=12000)
        assert part2.line_26_total_adjustments == 12000

    def test_student_loan_interest_max(self):
        """Test student loan interest deduction (max $2,500)."""
        part2 = Schedule1Part2(line_21_student_loan_interest=2500)
        assert part2.line_26_total_adjustments == 2500

    def test_ira_deduction(self):
        """Test traditional IRA deduction."""
        part2 = Schedule1Part2(line_20_ira_deduction=7000)  # 2024 limit
        assert part2.line_26_total_adjustments == 7000

    def test_alimony_paid_pre_2019(self):
        """Test alimony paid (divorce before 2019)."""
        part2 = Schedule1Part2(
            line_19a_alimony_paid=24000,
            line_19b_recipient_ssn="123-45-6789",
            line_19c_divorce_date="2017-09-01"
        )
        assert part2.line_26_total_adjustments == 24000

    def test_multiple_adjustments(self):
        """Test combining multiple adjustments."""
        part2 = Schedule1Part2(
            line_13_hsa_deduction=4150,
            line_15_se_tax_deduction=7500,
            line_16_sep_simple=20000,
            line_17_se_health_insurance=10000,
            line_21_student_loan_interest=2500,
        )
        assert part2.line_26_total_adjustments == 44150

    def test_other_adjustments(self):
        """Test other adjustments (Line 24z)."""
        part2 = Schedule1Part2(
            line_24z_other_adjustments=[
                OtherAdjustmentItem(
                    adjustment_type=OtherAdjustmentType.ATTORNEY_FEES,
                    description="Whistleblower attorney fees",
                    amount=10000
                )
            ]
        )
        assert part2.line_24z_total == 10000
        assert part2.line_25_total_other_adjustments == 10000

    def test_jury_duty_remit_to_employer(self):
        """Test jury duty pay remitted to employer."""
        part2 = Schedule1Part2(line_24a_jury_duty_remit=150)
        assert part2.line_25_total_other_adjustments == 150


class TestSchedule1Complete:
    """Test complete Schedule 1."""

    def test_schedule_1_is_required_with_business_income(self):
        """Test Schedule 1 required for business income."""
        sched1 = Schedule1(
            part_1=Schedule1Part1(line_3_business_income=50000)
        )
        assert sched1.is_required() is True

    def test_schedule_1_is_required_with_adjustments(self):
        """Test Schedule 1 required for adjustments."""
        sched1 = Schedule1(
            part_2=Schedule1Part2(line_21_student_loan_interest=1000)
        )
        assert sched1.is_required() is True

    def test_schedule_1_not_required_if_empty(self):
        """Test Schedule 1 not required if no entries."""
        sched1 = Schedule1()
        assert sched1.is_required() is False

    def test_form_1040_line_8_routing(self):
        """Test routing to Form 1040 Line 8."""
        sched1 = Schedule1(
            part_1=Schedule1Part1(
                line_3_business_income=50000,
                line_7_unemployment=5000
            )
        )
        assert sched1.form_1040_line_8 == 55000

    def test_form_1040_line_10_routing(self):
        """Test routing to Form 1040 Line 10."""
        sched1 = Schedule1(
            part_2=Schedule1Part2(
                line_13_hsa_deduction=4150,
                line_15_se_tax_deduction=7500
            )
        )
        assert sched1.form_1040_line_10 == 11650

    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        sched1 = Schedule1(
            tax_year=2025,
            part_1=Schedule1Part1(line_3_business_income=50000),
            part_2=Schedule1Part2(line_13_hsa_deduction=4150)
        )
        d = sched1.to_dict()
        assert d['tax_year'] == 2025
        assert d['part_1']['line_3_business_income'] == 50000
        assert d['part_2']['line_13_hsa_deduction'] == 4150
        assert d['form_1040_line_8'] == 50000
        assert d['form_1040_line_10'] == 4150


# =============================================================================
# Schedule 2 Tests
# =============================================================================

class TestSchedule2Part1:
    """Test Schedule 2 Part I: Tax."""

    def test_amt(self):
        """Test Alternative Minimum Tax."""
        part1 = Schedule2Part1(line_1_amt=15000)
        assert part1.line_3_total_part_1 == 15000

    def test_ptc_repayment(self):
        """Test excess advance PTC repayment."""
        part1 = Schedule2Part1(line_2_ptc_repayment=2500)
        assert part1.line_3_total_part_1 == 2500

    def test_both_amt_and_ptc(self):
        """Test both AMT and PTC repayment."""
        part1 = Schedule2Part1(
            line_1_amt=10000,
            line_2_ptc_repayment=1500
        )
        assert part1.line_3_total_part_1 == 11500


class TestSchedule2Part2:
    """Test Schedule 2 Part II: Other Taxes."""

    def test_self_employment_tax(self):
        """Test self-employment tax."""
        part2 = Schedule2Part2(line_4_self_employment_tax=15000)
        assert part2.line_21_total_part_2 == 15000

    def test_additional_medicare_tax(self):
        """Test Additional Medicare Tax (0.9%)."""
        part2 = Schedule2Part2(line_10_additional_medicare=2700)
        assert part2.line_21_total_part_2 == 2700

    def test_niit(self):
        """Test Net Investment Income Tax (3.8%)."""
        part2 = Schedule2Part2(line_11_niit=3800)
        assert part2.line_21_total_part_2 == 3800

    def test_ira_early_withdrawal_penalty(self):
        """Test 10% early IRA withdrawal penalty."""
        part2 = Schedule2Part2(line_7a_ira_additional_tax=1000)
        assert part2.line_21_total_part_2 == 1000

    def test_household_employment_taxes(self):
        """Test household employment taxes (Schedule H)."""
        part2 = Schedule2Part2(line_8_household_employment=2500)
        assert part2.line_21_total_part_2 == 2500

    def test_unreported_tip_tax(self):
        """Test SS/Medicare on unreported tips (Form 4137)."""
        part2 = Schedule2Part2(line_5_unreported_tip_tax=750)
        assert part2.line_21_total_part_2 == 750

    def test_multiple_other_taxes(self):
        """Test combining multiple other taxes."""
        part2 = Schedule2Part2(
            line_4_self_employment_tax=15000,
            line_10_additional_medicare=1500,
            line_11_niit=3800,
        )
        assert part2.line_21_total_part_2 == 20300

    def test_other_tax_items(self):
        """Test other tax items (Line 17z)."""
        part2 = Schedule2Part2(
            line_17z_other_taxes=[
                OtherTaxItem(
                    tax_type=OtherTaxType.GOLDEN_PARACHUTE,
                    description="Excise tax on excess parachute",
                    amount=50000,
                    form_reference="Form 8824"
                )
            ]
        )
        assert part2.line_17z_total == 50000
        assert part2.line_17_total_other_line_17 == 50000

    def test_installment_interest_453a(self):
        """Test interest on installment sale deferral (IRC 453A)."""
        part2 = Schedule2Part2(line_13_installment_interest_453a=5000)
        assert part2.line_21_total_part_2 == 5000


class TestSchedule2Complete:
    """Test complete Schedule 2."""

    def test_schedule_2_is_required_with_amt(self):
        """Test Schedule 2 required for AMT."""
        sched2 = Schedule2(
            part_1=Schedule2Part1(line_1_amt=10000)
        )
        assert sched2.is_required() is True

    def test_schedule_2_is_required_with_se_tax(self):
        """Test Schedule 2 required for SE tax."""
        sched2 = Schedule2(
            part_2=Schedule2Part2(line_4_self_employment_tax=15000)
        )
        assert sched2.is_required() is True

    def test_schedule_2_not_required_if_empty(self):
        """Test Schedule 2 not required if no entries."""
        sched2 = Schedule2()
        assert sched2.is_required() is False

    def test_form_1040_line_17_routing(self):
        """Test routing to Form 1040 Line 17."""
        sched2 = Schedule2(
            part_1=Schedule2Part1(
                line_1_amt=10000,
                line_2_ptc_repayment=2000
            )
        )
        assert sched2.form_1040_line_17 == 12000

    def test_form_1040_line_23_routing(self):
        """Test routing to Form 1040 Line 23."""
        sched2 = Schedule2(
            part_2=Schedule2Part2(
                line_4_self_employment_tax=15000,
                line_10_additional_medicare=2000
            )
        )
        assert sched2.form_1040_line_23 == 17000

    def test_total_additional_taxes(self):
        """Test total additional taxes."""
        sched2 = Schedule2(
            part_1=Schedule2Part1(line_1_amt=10000),
            part_2=Schedule2Part2(line_4_self_employment_tax=15000)
        )
        assert sched2.total_additional_taxes == 25000

    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        sched2 = Schedule2(
            tax_year=2025,
            part_1=Schedule2Part1(line_1_amt=10000),
            part_2=Schedule2Part2(line_4_self_employment_tax=15000)
        )
        d = sched2.to_dict()
        assert d['tax_year'] == 2025
        assert d['part_1']['line_1_amt'] == 10000
        assert d['part_2']['line_4_self_employment_tax'] == 15000


# =============================================================================
# Schedule 3 Tests
# =============================================================================

class TestSchedule3Part1:
    """Test Schedule 3 Part I: Nonrefundable Credits."""

    def test_foreign_tax_credit(self):
        """Test foreign tax credit."""
        part1 = Schedule3Part1(line_1_foreign_tax_credit=1500)
        assert part1.line_8_total_nonrefundable == 1500

    def test_dependent_care_credit(self):
        """Test child and dependent care credit."""
        part1 = Schedule3Part1(line_2_dependent_care_credit=6000)
        assert part1.line_8_total_nonrefundable == 6000

    def test_education_credits(self):
        """Test education credits (Form 8863)."""
        part1 = Schedule3Part1(line_3_education_credits=2500)
        assert part1.line_8_total_nonrefundable == 2500

    def test_saver_credit(self):
        """Test retirement savings contributions credit."""
        part1 = Schedule3Part1(line_4_saver_credit=2000)
        assert part1.line_8_total_nonrefundable == 2000

    def test_residential_energy_credits(self):
        """Test residential energy credits."""
        part1 = Schedule3Part1(
            line_5a_clean_energy_credit=5000,
            line_5b_energy_improvement_credit=3200
        )
        assert part1.line_8_total_nonrefundable == 8200

    def test_prior_year_amt_credit(self):
        """Test prior year minimum tax credit."""
        part1 = Schedule3Part1(line_6a_prior_year_amt_credit=5000)
        assert part1.line_7_total_other_credits == 5000

    def test_clean_vehicle_credit(self):
        """Test clean vehicle credit (Form 8936)."""
        part1 = Schedule3Part1(line_6b_ev_credit=7500)
        assert part1.line_7_total_other_credits == 7500

    def test_general_business_credit(self):
        """Test general business credit (Form 3800)."""
        part1 = Schedule3Part1(line_6k_general_business=25000)
        assert part1.line_7_total_other_credits == 25000

    def test_multiple_nonrefundable_credits(self):
        """Test combining multiple nonrefundable credits."""
        part1 = Schedule3Part1(
            line_1_foreign_tax_credit=1000,
            line_2_dependent_care_credit=3000,
            line_3_education_credits=2500,
            line_4_saver_credit=1000,
        )
        assert part1.line_8_total_nonrefundable == 7500

    def test_other_nonrefundable_credits(self):
        """Test other nonrefundable credits (Line 6z)."""
        part1 = Schedule3Part1(
            line_6z_other_credits=[
                NonrefundableCreditItem(
                    credit_type=NonrefundableCreditType.ADOPTION,
                    description="Adoption credit",
                    amount=10000,
                    form_reference="Form 8839"
                )
            ]
        )
        assert part1.line_6z_total == 10000
        assert part1.line_7_total_other_credits == 10000


class TestSchedule3Part2:
    """Test Schedule 3 Part II: Other Payments and Refundable Credits."""

    def test_net_ptc(self):
        """Test net premium tax credit."""
        part2 = Schedule3Part2(line_9_ptc=3000)
        assert part2.line_15_total_part_2 == 3000

    def test_extension_payment(self):
        """Test payment with extension."""
        part2 = Schedule3Part2(line_10_extension_payment=2000)
        assert part2.line_15_total_part_2 == 2000

    def test_excess_ss_withheld(self):
        """Test excess Social Security tax withheld (multiple employers)."""
        part2 = Schedule3Part2(line_11_excess_ss_withheld=1500)
        assert part2.line_15_total_part_2 == 1500

    def test_fuel_credit(self):
        """Test federal fuel credit."""
        part2 = Schedule3Part2(line_12_fuel_credit=500)
        assert part2.line_15_total_part_2 == 500

    def test_ev_credit_refundable(self):
        """Test refundable clean vehicle credit."""
        part2 = Schedule3Part2(line_13h_ev_credit_refundable=7500)
        assert part2.line_14_total_other_payments == 7500

    def test_sick_leave_credit(self):
        """Test sick and family leave credits (Form 7202)."""
        part2 = Schedule3Part2(line_13d_sick_leave_credit=5000)
        assert part2.line_14_total_other_payments == 5000

    def test_multiple_payments_credits(self):
        """Test combining multiple payments/credits."""
        part2 = Schedule3Part2(
            line_9_ptc=2000,
            line_10_extension_payment=1000,
            line_11_excess_ss_withheld=500,
        )
        assert part2.line_15_total_part_2 == 3500

    def test_other_refundable_credits(self):
        """Test other refundable credits (Line 13z)."""
        part2 = Schedule3Part2(
            line_13z_other_payments=[
                RefundableCreditItem(
                    credit_type=RefundableCreditType.HEALTH_COVERAGE,
                    description="HCTC credit",
                    amount=1000,
                    form_reference="Form 8885"
                )
            ]
        )
        assert part2.line_13z_total == 1000
        assert part2.line_14_total_other_payments == 1000


class TestSchedule3Complete:
    """Test complete Schedule 3."""

    def test_schedule_3_is_required_with_foreign_tax_credit(self):
        """Test Schedule 3 required for foreign tax credit."""
        sched3 = Schedule3(
            part_1=Schedule3Part1(line_1_foreign_tax_credit=1000)
        )
        assert sched3.is_required() is True

    def test_schedule_3_is_required_with_ptc(self):
        """Test Schedule 3 required for PTC."""
        sched3 = Schedule3(
            part_2=Schedule3Part2(line_9_ptc=2000)
        )
        assert sched3.is_required() is True

    def test_schedule_3_not_required_if_empty(self):
        """Test Schedule 3 not required if no entries."""
        sched3 = Schedule3()
        assert sched3.is_required() is False

    def test_form_1040_line_20_routing(self):
        """Test routing to Form 1040 Line 20."""
        sched3 = Schedule3(
            part_1=Schedule3Part1(
                line_1_foreign_tax_credit=1000,
                line_3_education_credits=2500
            )
        )
        assert sched3.form_1040_line_20 == 3500

    def test_form_1040_line_31_routing(self):
        """Test routing to Form 1040 Line 31."""
        sched3 = Schedule3(
            part_2=Schedule3Part2(
                line_9_ptc=2000,
                line_10_extension_payment=1000
            )
        )
        assert sched3.form_1040_line_31 == 3000

    def test_total_additional_credits(self):
        """Test total additional credits."""
        sched3 = Schedule3(
            part_1=Schedule3Part1(line_1_foreign_tax_credit=1000),
            part_2=Schedule3Part2(line_9_ptc=2000)
        )
        assert sched3.total_additional_credits == 3000

    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        sched3 = Schedule3(
            tax_year=2025,
            part_1=Schedule3Part1(line_1_foreign_tax_credit=1000),
            part_2=Schedule3Part2(line_9_ptc=2000)
        )
        d = sched3.to_dict()
        assert d['tax_year'] == 2025
        assert d['part_1']['line_1_foreign_tax_credit'] == 1000
        assert d['part_2']['line_9_ptc'] == 2000


# =============================================================================
# Integration Tests
# =============================================================================

class TestForm1040Integration:
    """Test Form 1040 routing integration across all schedules."""

    def test_complete_self_employed_scenario(self):
        """Test self-employed taxpayer with all schedules."""
        # Schedule 1: Business income and adjustments
        sched1 = Schedule1(
            part_1=Schedule1Part1(line_3_business_income=100000),
            part_2=Schedule1Part2(
                line_13_hsa_deduction=4150,
                line_15_se_tax_deduction=7065,  # Half of $14,130 SE tax
                line_16_sep_simple=25000,
                line_17_se_health_insurance=12000,
            )
        )

        # Schedule 2: SE tax and NIIT
        sched2 = Schedule2(
            part_2=Schedule2Part2(
                line_4_self_employment_tax=14130,
                line_11_niit=3800,
            )
        )

        # Schedule 3: Credits
        sched3 = Schedule3(
            part_1=Schedule3Part1(
                line_1_foreign_tax_credit=500,
            )
        )

        # Verify all schedules are required
        assert sched1.is_required() is True
        assert sched2.is_required() is True
        assert sched3.is_required() is True

        # Verify Form 1040 line routing
        assert sched1.form_1040_line_8 == 100000  # Additional income
        assert sched1.form_1040_line_10 == 48215  # Adjustments
        assert sched2.form_1040_line_17 == 0  # No AMT/PTC
        assert sched2.form_1040_line_23 == 17930  # SE + NIIT
        assert sched3.form_1040_line_20 == 500  # Foreign tax credit
        assert sched3.form_1040_line_31 == 0  # No refundable credits

    def test_complex_investment_scenario(self):
        """Test taxpayer with investment income and AMT."""
        sched1 = Schedule1(
            part_1=Schedule1Part1(
                line_5_schedule_e_income=50000,  # K-1 income
                line_8b_gambling_income=10000,
            )
        )

        sched2 = Schedule2(
            part_1=Schedule2Part1(line_1_amt=15000),
            part_2=Schedule2Part2(
                line_10_additional_medicare=2000,
                line_11_niit=7600,
            )
        )

        sched3 = Schedule3(
            part_1=Schedule3Part1(
                line_1_foreign_tax_credit=3000,
                line_6a_prior_year_amt_credit=5000,
            )
        )

        # Verify totals
        assert sched1.form_1040_line_8 == 60000
        assert sched2.form_1040_line_17 == 15000
        assert sched2.form_1040_line_23 == 9600
        assert sched3.form_1040_line_20 == 8000

    def test_employee_with_adjustments_only(self):
        """Test W-2 employee with just adjustments (no Schedule 2/3)."""
        sched1 = Schedule1(
            part_2=Schedule1Part2(
                line_11_educator_expenses=300,
                line_21_student_loan_interest=2500,
            )
        )

        sched2 = Schedule2()
        sched3 = Schedule3()

        assert sched1.is_required() is True
        assert sched2.is_required() is False
        assert sched3.is_required() is False

        assert sched1.form_1040_line_8 == 0
        assert sched1.form_1040_line_10 == 2800

    def test_premium_tax_credit_scenario(self):
        """Test marketplace health insurance with PTC."""
        sched3 = Schedule3(
            part_2=Schedule3Part2(
                line_9_ptc=4800,  # Net PTC refund
            )
        )

        # Also test excess PTC repayment scenario
        sched2 = Schedule2(
            part_1=Schedule2Part1(
                line_2_ptc_repayment=1500  # Must repay excess APTC
            )
        )

        assert sched3.form_1040_line_31 == 4800
        assert sched2.form_1040_line_17 == 1500


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_amounts_not_required(self):
        """Test schedules with all zero amounts."""
        sched1 = Schedule1()
        sched2 = Schedule2()
        sched3 = Schedule3()

        assert sched1.is_required() is False
        assert sched2.is_required() is False
        assert sched3.is_required() is False

    def test_negative_business_income(self):
        """Test Schedule 1 with business loss."""
        sched1 = Schedule1(
            part_1=Schedule1Part1(line_3_business_income=-25000)
        )
        assert sched1.form_1040_line_8 == -25000
        assert sched1.is_required() is True

    def test_maximum_educator_expense(self):
        """Test educator expense at maximum."""
        part2 = Schedule1Part2(line_11_educator_expenses=600)  # MFJ max
        assert part2.line_26_total_adjustments == 600

    def test_maximum_student_loan_interest(self):
        """Test student loan interest at maximum."""
        part2 = Schedule1Part2(line_21_student_loan_interest=2500)
        assert part2.line_26_total_adjustments == 2500

    def test_empty_other_items_lists(self):
        """Test with empty other items lists."""
        part1 = Schedule1Part1()
        assert part1.line_8z_total == 0

        part2 = Schedule2Part2()
        assert part2.line_17z_total == 0

        part3_1 = Schedule3Part1()
        assert part3_1.line_6z_total == 0

        part3_2 = Schedule3Part2()
        assert part3_2.line_13z_total == 0

    def test_many_other_income_items(self):
        """Test with many other income items."""
        items = [
            OtherIncomeItem(
                income_type=OtherIncomeType.OTHER,
                description=f"Item {i}",
                amount=100.0
            )
            for i in range(10)
        ]
        part1 = Schedule1Part1(line_8z_other_income=items)
        assert part1.line_8z_total == 1000.0
