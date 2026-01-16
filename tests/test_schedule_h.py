"""
Test suite for Schedule H - Household Employment Taxes.

Tests cover:
- Filing threshold determination
- Social Security and Medicare tax calculation
- FUTA tax calculation
- Employee exemptions (spouse, family members)
- Multiple employees
- Convenience function
"""

import pytest
from models.schedule_h import (
    ScheduleH,
    HouseholdEmployee,
    HouseholdEmployeeType,
    calculate_household_employment_tax,
)


class TestScheduleHFilingRequirements:
    """Tests for Schedule H filing threshold determination."""

    def test_single_employee_over_threshold_must_file(self):
        """Single employee paid >= $2,700 requires Schedule H."""
        employee = HouseholdEmployee(
            employee_name="Jane Doe",
            employee_type=HouseholdEmployeeType.NANNY,
            total_cash_wages=5000.0,
        )
        schedule = ScheduleH(employees=[employee])

        must_file, reason = schedule.is_subject_to_household_employment_taxes()
        assert must_file is True
        assert "2,700" in reason

    def test_single_employee_under_threshold_no_file(self):
        """Single employee paid < $2,700 doesn't require Schedule H."""
        employee = HouseholdEmployee(
            employee_name="Jane Doe",
            total_cash_wages=2000.0,
        )
        schedule = ScheduleH(employees=[employee])

        must_file, reason = schedule.is_subject_to_household_employment_taxes()
        assert must_file is False

    def test_exactly_at_threshold_must_file(self):
        """Wages exactly at $2,700 requires Schedule H."""
        employee = HouseholdEmployee(
            total_cash_wages=2700.0,
        )
        schedule = ScheduleH(employees=[employee])

        must_file, _ = schedule.is_subject_to_household_employment_taxes()
        assert must_file is True

    def test_federal_tax_withheld_must_file(self):
        """Federal income tax withheld requires Schedule H."""
        employee = HouseholdEmployee(
            total_cash_wages=1000.0,  # Below threshold
            federal_income_tax_withheld=100.0,  # But tax was withheld
        )
        schedule = ScheduleH(employees=[employee])

        must_file, reason = schedule.is_subject_to_household_employment_taxes()
        assert must_file is True
        assert "withheld" in reason.lower()

    def test_quarterly_threshold_futa(self):
        """$1,000+ in any quarter triggers FUTA."""
        employee = HouseholdEmployee(
            total_cash_wages=2000.0,  # Below annual threshold
            q2_wages=1000.0,  # But Q2 hits quarterly threshold
        )
        schedule = ScheduleH(employees=[employee])

        must_file, reason = schedule.is_subject_to_household_employment_taxes()
        assert must_file is True
        assert "FUTA" in reason


class TestScheduleHSocialSecurityMedicare:
    """Tests for Social Security and Medicare tax calculations."""

    def test_basic_ss_medicare_calculation(self):
        """Basic Social Security and Medicare calculation."""
        employee = HouseholdEmployee(
            total_cash_wages=50000.0,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_social_security_medicare()

        # SS: $50,000 × 12.4% = $6,200
        # Medicare: $50,000 × 2.9% = $1,450
        assert result['total_social_security_wages'] == 50000.0
        assert result['social_security_tax'] == pytest.approx(6200.0, rel=0.01)
        assert result['medicare_tax'] == pytest.approx(1450.0, rel=0.01)

    def test_ss_wage_cap(self):
        """Social Security wages capped at wage base."""
        employee = HouseholdEmployee(
            total_cash_wages=200000.0,  # Above SS wage base
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_social_security_medicare()

        # SS wages capped at $176,100
        assert result['total_social_security_wages'] == 176100.0
        # Medicare on full amount
        assert result['total_medicare_wages'] == 200000.0

    def test_additional_medicare_over_200k(self):
        """Additional Medicare tax on wages over $200k."""
        employee = HouseholdEmployee(
            total_cash_wages=250000.0,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_social_security_medicare()

        # Additional Medicare: $50,000 × 0.9% = $450
        assert result['additional_medicare_tax'] == pytest.approx(450.0, rel=0.01)

    def test_exempt_spouse_no_taxes(self):
        """Spouse is exempt from all employment taxes."""
        employee = HouseholdEmployee(
            total_cash_wages=50000.0,
            is_spouse=True,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_social_security_medicare()

        assert result['total_social_security_wages'] == 0.0
        assert result['social_security_tax'] == 0.0
        assert result['medicare_tax'] == 0.0

    def test_exempt_child_under_21(self):
        """Child under 21 is exempt from SS/Medicare."""
        employee = HouseholdEmployee(
            total_cash_wages=10000.0,
            is_family_member_under_21=True,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_social_security_medicare()

        assert result['social_security_tax'] == 0.0
        assert result['medicare_tax'] == 0.0

    def test_below_threshold_no_tax(self):
        """Wages below $2,700 threshold not subject to SS/Medicare."""
        employee = HouseholdEmployee(
            total_cash_wages=2000.0,  # Below threshold
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_social_security_medicare()

        assert result['social_security_tax'] == 0.0


class TestScheduleHFUTA:
    """Tests for FUTA (Federal Unemployment) tax calculations."""

    def test_basic_futa_calculation(self):
        """Basic FUTA tax calculation."""
        employee = HouseholdEmployee(
            total_cash_wages=10000.0,
            q1_wages=2500.0,
            q2_wages=2500.0,
            q3_wages=2500.0,
            q4_wages=2500.0,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_futa()

        # FUTA wages capped at $7,000
        # Net FUTA: $7,000 × 0.6% = $42
        assert result['subject_to_futa'] is True
        assert result['futa_wages'] == 7000.0
        assert result['net_futa_tax'] == pytest.approx(42.0, rel=0.01)

    def test_futa_not_applicable_below_threshold(self):
        """FUTA not applicable if quarterly wages below $1,000."""
        employee = HouseholdEmployee(
            total_cash_wages=3000.0,
            q1_wages=750.0,
            q2_wages=750.0,
            q3_wages=750.0,
            q4_wages=750.0,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_futa()

        assert result['subject_to_futa'] is False
        assert result['net_futa_tax'] == 0.0

    def test_spouse_exempt_from_futa(self):
        """Spouse is exempt from FUTA."""
        employee = HouseholdEmployee(
            total_cash_wages=10000.0,
            is_spouse=True,
            q1_wages=5000.0,  # Above quarterly threshold
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_futa()

        # No FUTA because spouse is exempt
        assert result['futa_wages'] == 0.0

    def test_futa_wage_base_cap(self):
        """FUTA wages capped at $7,000 per employee."""
        employee = HouseholdEmployee(
            total_cash_wages=50000.0,
            q1_wages=12500.0,
        )
        schedule = ScheduleH(employees=[employee])

        result = schedule.calculate_futa()

        assert result['futa_wages'] == 7000.0


class TestScheduleHMultipleEmployees:
    """Tests for multiple household employees."""

    def test_multiple_employees_combined_taxes(self):
        """Multiple employees' taxes are combined."""
        emp1 = HouseholdEmployee(
            employee_name="Nanny",
            total_cash_wages=30000.0,
            q1_wages=7500.0,
        )
        emp2 = HouseholdEmployee(
            employee_name="Housekeeper",
            total_cash_wages=20000.0,
            q1_wages=5000.0,
        )
        schedule = ScheduleH(employees=[emp1, emp2])

        result = schedule.calculate_schedule_h()

        # Total wages: $50,000
        assert result['total_wages_paid'] == 50000.0
        assert result['number_of_employees'] == 2
        assert result['total_ss_medicare_tax'] > 0

    def test_mixed_exempt_non_exempt_employees(self):
        """Mix of exempt and non-exempt employees."""
        emp_taxable = HouseholdEmployee(
            employee_name="Nanny",
            total_cash_wages=30000.0,
            q1_wages=7500.0,
        )
        emp_exempt = HouseholdEmployee(
            employee_name="Spouse Helper",
            total_cash_wages=10000.0,
            is_spouse=True,
        )
        schedule = ScheduleH(employees=[emp_taxable, emp_exempt])

        ss_result = schedule.calculate_social_security_medicare()

        # Only taxable employee's wages count
        assert ss_result['total_social_security_wages'] == 30000.0


class TestScheduleHCompleteCalculation:
    """Tests for complete Schedule H calculation."""

    def test_complete_schedule_h(self):
        """Complete Schedule H calculation with all components."""
        employee = HouseholdEmployee(
            employee_name="Full-Time Nanny",
            total_cash_wages=45000.0,
            federal_income_tax_withheld=3000.0,
            q1_wages=11250.0,
            q2_wages=11250.0,
            q3_wages=11250.0,
            q4_wages=11250.0,
        )
        schedule = ScheduleH(
            employer_name="Test Family",
            employees=[employee],
        )

        result = schedule.calculate_schedule_h()

        assert result['must_file'] is True
        assert result['total_ss_medicare_tax'] > 0
        assert result['total_futa_tax'] > 0
        assert result['total_household_employment_tax'] > 0
        assert result['federal_income_tax_withheld'] == 3000.0

    def test_balance_due_calculation(self):
        """Balance due calculated correctly."""
        employee = HouseholdEmployee(
            total_cash_wages=30000.0,
            q1_wages=7500.0,
        )
        schedule = ScheduleH(
            employees=[employee],
            prior_period_taxes_paid=0.0,
        )

        result = schedule.calculate_schedule_h()

        assert result['amount_owed'] > 0
        assert result['overpayment'] == 0.0

    def test_overpayment_calculation(self):
        """Overpayment calculated when prior payments exceed taxes."""
        employee = HouseholdEmployee(
            total_cash_wages=5000.0,
            q1_wages=2500.0,
        )
        schedule = ScheduleH(
            employees=[employee],
            prior_period_taxes_paid=5000.0,  # Large prior payment
        )

        result = schedule.calculate_schedule_h()

        # Should show overpayment
        assert result['overpayment'] > 0


class TestScheduleHConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_basic(self):
        """Convenience function calculates correctly."""
        result = calculate_household_employment_tax(
            wages_paid=30000.0,
            is_exempt=False,
        )

        assert result['must_file'] is True
        assert result['total_household_employment_tax'] > 0

    def test_convenience_function_exempt(self):
        """Convenience function handles exemption."""
        result = calculate_household_employment_tax(
            wages_paid=30000.0,
            is_exempt=True,  # Spouse
        )

        # Exempt employees have no taxes
        assert result['total_ss_medicare_tax'] == 0.0

    def test_convenience_function_below_threshold(self):
        """Convenience function handles below-threshold wages."""
        result = calculate_household_employment_tax(
            wages_paid=2000.0,
            is_exempt=False,
        )

        assert result['must_file'] is False


class TestScheduleHConstants:
    """Tests verifying 2025 constants."""

    def test_cash_wage_threshold(self):
        """Verify 2025 cash wage threshold."""
        assert ScheduleH.CASH_WAGE_THRESHOLD_2025 == 2700.0

    def test_futa_quarterly_threshold(self):
        """Verify FUTA quarterly threshold."""
        assert ScheduleH.FUTA_QUARTERLY_THRESHOLD == 1000.0

    def test_social_security_rate(self):
        """Verify Social Security rate."""
        assert ScheduleH.SOCIAL_SECURITY_RATE == 0.124

    def test_medicare_rate(self):
        """Verify Medicare rate."""
        assert ScheduleH.MEDICARE_RATE == 0.029

    def test_futa_net_rate(self):
        """Verify FUTA net rate after credit."""
        assert ScheduleH.FUTA_NET_RATE == 0.006
