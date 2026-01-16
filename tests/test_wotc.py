"""
Tests for Work Opportunity Tax Credit (Form 5884 / IRC Section 51).

WOTC is an employer credit for hiring individuals from target groups
who face significant barriers to employment.

Key Rules:
- Minimum 120 hours worked for any credit
- 25% rate for 120-399 hours
- 40% rate for 400+ hours
- Wage limits vary by target group ($3k-$24k)
- Certification (Form 8850) required
- Long-term family assistance: special 2-year credit

Reference: IRC Section 51, IRS Form 5884
"""

import pytest
from models.credits import TaxCredits, WOTCEmployee, WOTCTargetGroup


class TestWOTCEmployee:
    """Tests for the WOTCEmployee model."""

    def test_wage_limit_standard_groups(self):
        """Test $6,000 wage limit for standard target groups."""
        for group in [
            WOTCTargetGroup.TANF_RECIPIENT,
            WOTCTargetGroup.SNAP_RECIPIENT,
            WOTCTargetGroup.SSI_RECIPIENT,
            WOTCTargetGroup.VOCATIONAL_REHAB,
            WOTCTargetGroup.EX_FELON,
            WOTCTargetGroup.DESIGNATED_COMMUNITY,
            WOTCTargetGroup.VETERAN_SNAP,
            WOTCTargetGroup.VETERAN_UNEMPLOYED_6MO,
            WOTCTargetGroup.LONG_TERM_UNEMPLOYED,
        ]:
            emp = WOTCEmployee(
                employee_name="Test",
                target_group=group,
                hire_date="2025-01-15",
                first_year_wages=10000,
                hours_worked=500,
            )
            assert emp.get_wage_limit() == 6000.0

    def test_wage_limit_summer_youth(self):
        """Test $3,000 wage limit for summer youth."""
        emp = WOTCEmployee(
            employee_name="Youth Worker",
            target_group=WOTCTargetGroup.SUMMER_YOUTH,
            hire_date="2025-06-01",
            first_year_wages=5000,
            hours_worked=400,
        )
        assert emp.get_wage_limit() == 3000.0

    def test_wage_limit_disabled_veteran(self):
        """Test $12,000 wage limit for disabled veteran."""
        emp = WOTCEmployee(
            employee_name="Disabled Vet",
            target_group=WOTCTargetGroup.VETERAN_DISABLED,
            hire_date="2025-01-15",
            first_year_wages=15000,
            hours_worked=500,
        )
        assert emp.get_wage_limit() == 12000.0

    def test_wage_limit_disabled_unemployed_veteran(self):
        """Test $24,000 wage limit for disabled unemployed veteran."""
        emp = WOTCEmployee(
            employee_name="Disabled Unemployed Vet",
            target_group=WOTCTargetGroup.VETERAN_DISABLED_UNEMPLOYED,
            hire_date="2025-01-15",
            first_year_wages=30000,
            hours_worked=500,
        )
        assert emp.get_wage_limit() == 24000.0

    def test_wage_limit_long_term_family_assistance(self):
        """Test $10,000 wage limit for long-term family assistance."""
        emp = WOTCEmployee(
            employee_name="TANF Long-term",
            target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
            hire_date="2025-01-15",
            first_year_wages=12000,
            hours_worked=500,
        )
        assert emp.get_wage_limit() == 10000.0


class TestWOTCCreditRates:
    """Tests for WOTC credit rate calculations based on hours worked."""

    def test_zero_rate_under_120_hours(self):
        """Test 0% credit rate for < 120 hours."""
        emp = WOTCEmployee(
            employee_name="Short-term",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=5000,
            hours_worked=119,
        )
        assert emp.get_credit_rate() == 0.0
        assert emp.calculate_credit() == 0.0

    def test_25_percent_rate_120_hours(self):
        """Test 25% credit rate for exactly 120 hours."""
        emp = WOTCEmployee(
            employee_name="Min Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=120,
        )
        assert emp.get_credit_rate() == 0.25
        # 25% of $6,000 = $1,500
        assert emp.calculate_credit() == 1500.0

    def test_25_percent_rate_399_hours(self):
        """Test 25% credit rate for 399 hours (just under 400)."""
        emp = WOTCEmployee(
            employee_name="Under 400",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=399,
        )
        assert emp.get_credit_rate() == 0.25
        # 25% of $6,000 = $1,500
        assert emp.calculate_credit() == 1500.0

    def test_40_percent_rate_400_hours(self):
        """Test 40% credit rate for exactly 400 hours."""
        emp = WOTCEmployee(
            employee_name="Full Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=400,
        )
        assert emp.get_credit_rate() == 0.40
        # 40% of $6,000 = $2,400
        assert emp.calculate_credit() == 2400.0

    def test_40_percent_rate_many_hours(self):
        """Test 40% credit rate for 2000+ hours."""
        emp = WOTCEmployee(
            employee_name="Full Time",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=10000,
            hours_worked=2080,
        )
        assert emp.get_credit_rate() == 0.40
        # 40% of $6,000 (capped) = $2,400
        assert emp.calculate_credit() == 2400.0


class TestWOTCWageLimit:
    """Tests for WOTC wage limit application."""

    def test_wages_below_limit(self):
        """Test credit when wages are below limit."""
        emp = WOTCEmployee(
            employee_name="Low Wages",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=4000,
            hours_worked=500,
        )
        # 40% of $4,000 = $1,600
        assert emp.calculate_credit() == 1600.0

    def test_wages_above_limit(self):
        """Test credit capped at wage limit."""
        emp = WOTCEmployee(
            employee_name="High Wages",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=50000,  # Well above $6k limit
            hours_worked=2000,
        )
        # 40% of $6,000 (capped) = $2,400
        assert emp.calculate_credit() == 2400.0

    def test_disabled_veteran_high_wages(self):
        """Test disabled veteran $12,000 limit with high wages."""
        emp = WOTCEmployee(
            employee_name="Disabled Vet",
            target_group=WOTCTargetGroup.VETERAN_DISABLED,
            hire_date="2025-01-15",
            first_year_wages=50000,
            hours_worked=2000,
        )
        # 40% of $12,000 = $4,800
        assert emp.calculate_credit() == 4800.0

    def test_disabled_unemployed_veteran_max_credit(self):
        """Test disabled unemployed veteran maximum credit."""
        emp = WOTCEmployee(
            employee_name="Disabled Unemployed Vet",
            target_group=WOTCTargetGroup.VETERAN_DISABLED_UNEMPLOYED,
            hire_date="2025-01-15",
            first_year_wages=50000,
            hours_worked=2000,
        )
        # 40% of $24,000 = $9,600
        assert emp.calculate_credit() == 9600.0


class TestWOTCCertification:
    """Tests for Form 8850 certification requirement."""

    def test_no_certification_no_credit(self):
        """Test that missing certification results in no credit."""
        emp = WOTCEmployee(
            employee_name="No Cert",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            certification_received=False,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=500,
        )
        assert emp.calculate_credit() == 0.0

    def test_with_certification(self):
        """Test that credit is calculated with certification."""
        emp = WOTCEmployee(
            employee_name="With Cert",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            certification_received=True,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=500,
        )
        assert emp.calculate_credit() == 2400.0


class TestWOTCLongTermFamilyAssistance:
    """Tests for long-term family assistance special rules."""

    def test_first_year_credit(self):
        """Test year 1: 40% of up to $10,000."""
        emp = WOTCEmployee(
            employee_name="LTFA Year 1",
            target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
            hire_date="2024-01-15",
            first_year_wages=10000,
            hours_worked=2000,
            is_second_year=False,
        )
        # Year 1: 40% of $10,000 = $4,000
        assert emp.calculate_credit() == 4000.0

    def test_second_year_credit(self):
        """Test year 2: 50% of up to $10,000."""
        emp = WOTCEmployee(
            employee_name="LTFA Year 2",
            target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
            hire_date="2024-01-15",
            first_year_wages=10000,
            second_year_wages=10000,
            hours_worked=2000,  # Hours from first year
            is_second_year=True,
        )
        # Year 2: 50% of $10,000 = $5,000
        assert emp.calculate_credit() == 5000.0

    def test_second_year_lower_wages(self):
        """Test year 2 with wages below limit."""
        emp = WOTCEmployee(
            employee_name="LTFA Year 2 Low",
            target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
            hire_date="2024-01-15",
            first_year_wages=10000,
            second_year_wages=6000,
            hours_worked=2000,
            is_second_year=True,
        )
        # Year 2: 50% of $6,000 = $3,000
        assert emp.calculate_credit() == 3000.0

    def test_first_year_wages_over_limit(self):
        """Test year 1 with wages over $10,000 limit."""
        emp = WOTCEmployee(
            employee_name="LTFA Over Limit",
            target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
            hire_date="2024-01-15",
            first_year_wages=50000,
            hours_worked=2000,
            is_second_year=False,
        )
        # Year 1: 40% of $10,000 (capped) = $4,000
        assert emp.calculate_credit() == 4000.0


class TestTaxCreditsWOTCCalculation:
    """Tests for TaxCredits.calculate_wotc() method."""

    def test_no_employees(self):
        """Test with no WOTC employees."""
        credits = TaxCredits()
        credit, breakdown = credits.calculate_wotc()
        assert credit == 0.0
        assert breakdown['employees_qualified'] == 0
        assert breakdown['employees_disqualified'] == 0

    def test_single_qualified_employee(self):
        """Test with one qualified employee."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="John Smith",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-01-15",
                    first_year_wages=6000,
                    hours_worked=500,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        assert credit == 2400.0
        assert breakdown['employees_qualified'] == 1
        assert breakdown['employees_disqualified'] == 0
        assert breakdown['total_first_year_credit'] == 2400.0

    def test_multiple_employees(self):
        """Test with multiple employees from different groups."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="SNAP Employee",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-01-15",
                    first_year_wages=6000,
                    hours_worked=500,
                ),
                WOTCEmployee(
                    employee_name="Disabled Vet",
                    target_group=WOTCTargetGroup.VETERAN_DISABLED,
                    hire_date="2025-02-01",
                    first_year_wages=12000,
                    hours_worked=2000,
                ),
                WOTCEmployee(
                    employee_name="Ex-Felon",
                    target_group=WOTCTargetGroup.EX_FELON,
                    hire_date="2025-03-01",
                    first_year_wages=6000,
                    hours_worked=400,
                ),
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        # SNAP: $2,400 + Disabled Vet: $4,800 + Ex-Felon: $2,400 = $9,600
        assert credit == 9600.0
        assert breakdown['employees_qualified'] == 3
        assert breakdown['employees_disqualified'] == 0

    def test_mix_of_qualified_and_disqualified(self):
        """Test with mix of qualified and disqualified employees."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Qualified",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-01-15",
                    first_year_wages=6000,
                    hours_worked=500,
                ),
                WOTCEmployee(
                    employee_name="Too Few Hours",
                    target_group=WOTCTargetGroup.SSI_RECIPIENT,
                    hire_date="2025-02-01",
                    first_year_wages=6000,
                    hours_worked=100,  # < 120 hours
                ),
                WOTCEmployee(
                    employee_name="No Cert",
                    target_group=WOTCTargetGroup.EX_FELON,
                    certification_received=False,
                    hire_date="2025-03-01",
                    first_year_wages=6000,
                    hours_worked=500,
                ),
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        assert credit == 2400.0  # Only first employee qualifies
        assert breakdown['employees_qualified'] == 1
        assert breakdown['employees_disqualified'] == 2

    def test_target_group_breakdown(self):
        """Test target group breakdown in results."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="SNAP 1",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-01-15",
                    first_year_wages=6000,
                    hours_worked=500,
                ),
                WOTCEmployee(
                    employee_name="SNAP 2",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-02-01",
                    first_year_wages=4000,
                    hours_worked=400,
                ),
                WOTCEmployee(
                    employee_name="SSI Employee",
                    target_group=WOTCTargetGroup.SSI_RECIPIENT,
                    hire_date="2025-03-01",
                    first_year_wages=6000,
                    hours_worked=500,
                ),
            ]
        )
        credit, breakdown = credits.calculate_wotc()

        # SNAP: $2,400 + $1,600 = $4,000
        # SSI: $2,400
        assert credit == 6400.0

        assert 'snap' in breakdown['by_target_group']
        assert breakdown['by_target_group']['snap']['count'] == 2
        assert breakdown['by_target_group']['snap']['total_credit'] == 4000.0

        assert 'ssi' in breakdown['by_target_group']
        assert breakdown['by_target_group']['ssi']['count'] == 1
        assert breakdown['by_target_group']['ssi']['total_credit'] == 2400.0

    def test_long_term_family_first_and_second_year(self):
        """Test long-term family assistance with both years."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="LTFA Year 1",
                    target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
                    hire_date="2024-01-15",
                    first_year_wages=10000,
                    hours_worked=2000,
                    is_second_year=False,
                ),
                WOTCEmployee(
                    employee_name="LTFA Year 2",
                    target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
                    hire_date="2023-01-15",
                    first_year_wages=10000,
                    second_year_wages=10000,
                    hours_worked=2000,
                    is_second_year=True,
                ),
            ]
        )
        credit, breakdown = credits.calculate_wotc()

        # Year 1: 40% of $10,000 = $4,000
        # Year 2: 50% of $10,000 = $5,000
        assert credit == 9000.0
        assert breakdown['total_first_year_credit'] == 4000.0
        assert breakdown['total_second_year_credit'] == 5000.0


class TestWOTCMaxCredits:
    """Tests for maximum credit amounts by target group."""

    def test_summer_youth_max_credit(self):
        """Test summer youth maximum credit ($1,200)."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Summer Youth",
                    target_group=WOTCTargetGroup.SUMMER_YOUTH,
                    hire_date="2025-06-01",
                    first_year_wages=10000,  # Above $3k limit
                    hours_worked=500,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        # 40% of $3,000 = $1,200
        assert credit == 1200.0

    def test_standard_group_max_credit(self):
        """Test standard group maximum credit ($2,400)."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Standard",
                    target_group=WOTCTargetGroup.VOCATIONAL_REHAB,
                    hire_date="2025-01-15",
                    first_year_wages=50000,
                    hours_worked=2000,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        # 40% of $6,000 = $2,400
        assert credit == 2400.0

    def test_disabled_veteran_max_credit(self):
        """Test disabled veteran maximum credit ($4,800)."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Disabled Vet",
                    target_group=WOTCTargetGroup.VETERAN_DISABLED,
                    hire_date="2025-01-15",
                    first_year_wages=50000,
                    hours_worked=2000,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        # 40% of $12,000 = $4,800
        assert credit == 4800.0

    def test_disabled_unemployed_veteran_max_credit(self):
        """Test disabled unemployed veteran maximum credit ($9,600)."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Disabled Unemployed Vet",
                    target_group=WOTCTargetGroup.VETERAN_DISABLED_UNEMPLOYED,
                    hire_date="2025-01-15",
                    first_year_wages=50000,
                    hours_worked=2000,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()
        # 40% of $24,000 = $9,600
        assert credit == 9600.0

    def test_ltfa_max_total_credit(self):
        """Test long-term family assistance maximum total credit ($9,000)."""
        # Maximum over 2 years: $4,000 (yr1) + $5,000 (yr2) = $9,000
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="LTFA Combined",
                    target_group=WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE,
                    hire_date="2023-01-15",
                    first_year_wages=10000,
                    second_year_wages=10000,
                    hours_worked=2000,
                    is_second_year=True,
                )
            ]
        )
        credit, _ = credits.calculate_wotc()
        # Year 2: 50% of $10,000 = $5,000
        assert credit == 5000.0


class TestWOTCHoursThresholds:
    """Tests for hours worked threshold edge cases."""

    def test_119_hours_no_credit(self):
        """Test 119 hours results in no credit."""
        emp = WOTCEmployee(
            employee_name="119 Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=119,
        )
        assert emp.calculate_credit() == 0.0

    def test_120_hours_25_percent(self):
        """Test 120 hours results in 25% credit."""
        emp = WOTCEmployee(
            employee_name="120 Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=120,
        )
        # 25% of $6,000 = $1,500
        assert emp.calculate_credit() == 1500.0

    def test_250_hours_25_percent(self):
        """Test 250 hours still results in 25% credit."""
        emp = WOTCEmployee(
            employee_name="250 Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=250,
        )
        # 25% of $6,000 = $1,500
        assert emp.calculate_credit() == 1500.0

    def test_399_hours_25_percent(self):
        """Test 399 hours results in 25% credit."""
        emp = WOTCEmployee(
            employee_name="399 Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=399,
        )
        # 25% of $6,000 = $1,500
        assert emp.calculate_credit() == 1500.0

    def test_400_hours_40_percent(self):
        """Test 400 hours results in 40% credit."""
        emp = WOTCEmployee(
            employee_name="400 Hours",
            target_group=WOTCTargetGroup.SNAP_RECIPIENT,
            hire_date="2025-01-15",
            first_year_wages=6000,
            hours_worked=400,
        )
        # 40% of $6,000 = $2,400
        assert emp.calculate_credit() == 2400.0


class TestWOTCAllTargetGroups:
    """Tests to verify all target groups calculate correctly."""

    @pytest.mark.parametrize("target_group,wage_limit,expected_max_credit", [
        (WOTCTargetGroup.TANF_RECIPIENT, 6000, 2400),
        (WOTCTargetGroup.SNAP_RECIPIENT, 6000, 2400),
        (WOTCTargetGroup.SSI_RECIPIENT, 6000, 2400),
        (WOTCTargetGroup.VOCATIONAL_REHAB, 6000, 2400),
        (WOTCTargetGroup.EX_FELON, 6000, 2400),
        (WOTCTargetGroup.DESIGNATED_COMMUNITY, 6000, 2400),
        (WOTCTargetGroup.VETERAN_SNAP, 6000, 2400),
        (WOTCTargetGroup.VETERAN_DISABLED, 12000, 4800),
        (WOTCTargetGroup.VETERAN_UNEMPLOYED_6MO, 6000, 2400),
        (WOTCTargetGroup.VETERAN_DISABLED_UNEMPLOYED, 24000, 9600),
        (WOTCTargetGroup.SUMMER_YOUTH, 3000, 1200),
        (WOTCTargetGroup.LONG_TERM_FAMILY_ASSISTANCE, 10000, 4000),
        (WOTCTargetGroup.LONG_TERM_UNEMPLOYED, 6000, 2400),
    ])
    def test_all_target_groups(self, target_group, wage_limit, expected_max_credit):
        """Test each target group has correct wage limit and max credit."""
        emp = WOTCEmployee(
            employee_name=f"Employee-{target_group.value}",
            target_group=target_group,
            hire_date="2025-01-15",
            first_year_wages=100000,  # Very high to ensure limit applies
            hours_worked=2000,  # Full 40% rate
        )
        assert emp.get_wage_limit() == wage_limit
        assert emp.calculate_credit() == expected_max_credit


class TestWOTCBreakdownDetails:
    """Tests for detailed breakdown information."""

    def test_employee_details_in_breakdown(self):
        """Test employee details are captured in breakdown."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Test Employee",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-01-15",
                    first_year_wages=5000,
                    hours_worked=450,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()

        assert len(breakdown['employees']) == 1
        emp_detail = breakdown['employees'][0]

        assert emp_detail['name'] == "Test Employee"
        assert emp_detail['target_group'] == 'snap'
        assert emp_detail['hours_worked'] == 450
        assert emp_detail['first_year_wages'] == 5000
        assert emp_detail['credit_rate'] == 0.40
        assert emp_detail['wage_limit'] == 6000
        assert emp_detail['qualified_wages'] == 5000
        assert emp_detail['credit'] == 2000.0  # 40% of $5,000
        assert emp_detail['qualified'] is True

    def test_disqualification_reason_hours(self):
        """Test disqualification reason for insufficient hours."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="Short Timer",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    hire_date="2025-01-15",
                    first_year_wages=6000,
                    hours_worked=50,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()

        emp_detail = breakdown['employees'][0]
        assert emp_detail['qualified'] is False
        assert "50" in emp_detail['disqualification_reason']
        assert "120" in emp_detail['disqualification_reason']

    def test_disqualification_reason_certification(self):
        """Test disqualification reason for missing certification."""
        credits = TaxCredits(
            wotc_employees=[
                WOTCEmployee(
                    employee_name="No Cert",
                    target_group=WOTCTargetGroup.SNAP_RECIPIENT,
                    certification_received=False,
                    hire_date="2025-01-15",
                    first_year_wages=6000,
                    hours_worked=500,
                )
            ]
        )
        credit, breakdown = credits.calculate_wotc()

        emp_detail = breakdown['employees'][0]
        assert emp_detail['qualified'] is False
        assert "certification" in emp_detail['disqualification_reason'].lower()
