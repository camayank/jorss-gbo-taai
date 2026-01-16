"""
Schedule H - Household Employment Taxes (Nanny Tax)

Implements household employment tax calculations for taxpayers who employ
domestic workers such as nannies, housekeepers, gardeners, or other
household employees.

Who Must File Schedule H:
1. Paid any one household employee cash wages of $2,700 or more in 2025
2. Withheld federal income tax at employee's request
3. Paid total cash wages of $1,000+ in any calendar quarter to ALL
   household employees (makes you subject to FUTA)

Household Employees Include:
- Nannies, babysitters (regular)
- Housekeepers, maids
- Cooks, gardeners
- Personal attendants, caregivers
- Drivers (household purposes)

NOT Household Employees:
- Independent contractors (they control how work is done)
- Employees of agencies
- Family members under 21 (for Social Security/Medicare)
- Spouse (for all employment taxes)
- Parent caring for your child under 18 (under certain conditions)

2025 Thresholds:
- Social Security wage threshold: $176,100 (estimated)
- Medicare threshold: None (all wages subject)
- FUTA wage base: $7,000
- Household employee threshold: $2,700
- FUTA quarterly threshold: $1,000

Per IRS Schedule H Instructions, Publication 926, and IRC Sections 3121, 3306.
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from datetime import date


class HouseholdEmployeeType(str, Enum):
    """Types of household employees."""
    NANNY = "nanny"
    BABYSITTER = "babysitter"
    HOUSEKEEPER = "housekeeper"
    MAID = "maid"
    COOK = "cook"
    GARDENER = "gardener"
    CAREGIVER = "caregiver"
    PERSONAL_ATTENDANT = "personal_attendant"
    DRIVER = "driver"
    OTHER = "other"


class HouseholdEmployee(BaseModel):
    """Information about a single household employee."""
    employee_name: str = Field(default="", description="Employee's name")
    employee_ssn: Optional[str] = Field(default=None, description="Employee's SSN")
    employee_type: HouseholdEmployeeType = Field(
        default=HouseholdEmployeeType.OTHER,
        description="Type of household employee"
    )

    # Wages paid
    total_cash_wages: float = Field(
        default=0.0,
        ge=0,
        description="Total cash wages paid during year"
    )

    # Quarterly wages for FUTA determination
    q1_wages: float = Field(default=0.0, ge=0, description="Q1 wages (Jan-Mar)")
    q2_wages: float = Field(default=0.0, ge=0, description="Q2 wages (Apr-Jun)")
    q3_wages: float = Field(default=0.0, ge=0, description="Q3 wages (Jul-Sep)")
    q4_wages: float = Field(default=0.0, ge=0, description="Q4 wages (Oct-Dec)")

    # Withholding
    federal_income_tax_withheld: float = Field(
        default=0.0,
        ge=0,
        description="Federal income tax withheld at employee's request"
    )
    social_security_withheld: float = Field(
        default=0.0,
        ge=0,
        description="Employee's share of Social Security withheld"
    )
    medicare_withheld: float = Field(
        default=0.0,
        ge=0,
        description="Employee's share of Medicare withheld"
    )
    additional_medicare_withheld: float = Field(
        default=0.0,
        ge=0,
        description="Additional Medicare withheld (wages > $200k)"
    )

    # Exemptions
    is_family_member_under_21: bool = Field(
        default=False,
        description="Employee is your child under 21 (exempt from SS/Medicare)"
    )
    is_spouse: bool = Field(
        default=False,
        description="Employee is your spouse (exempt from all employment taxes)"
    )
    is_parent_caring_for_child: bool = Field(
        default=False,
        description="Employee is parent caring for your child under 18"
    )
    is_under_18_student: bool = Field(
        default=False,
        description="Employee is under 18 and student (exempt from SS/Medicare)"
    )

    def is_exempt_from_social_security_medicare(self) -> bool:
        """Check if employee is exempt from SS/Medicare taxes."""
        return (
            self.is_spouse or
            self.is_family_member_under_21 or
            self.is_under_18_student
        )

    def get_quarterly_wages(self) -> List[float]:
        """Get wages by quarter."""
        return [self.q1_wages, self.q2_wages, self.q3_wages, self.q4_wages]


class ScheduleH(BaseModel):
    """
    Schedule H - Household Employment Taxes.

    Calculates Social Security, Medicare, and FUTA taxes for household
    employers.

    2025 Rates and Thresholds:
    - Social Security rate: 12.4% (6.2% employer + 6.2% employee)
    - Medicare rate: 2.9% (1.45% employer + 1.45% employee)
    - Additional Medicare: 0.9% (employee only, wages > $200k)
    - FUTA rate: 6.0% (usually 0.6% after state credit)
    - FUTA wage base: $7,000 per employee
    - Household employee threshold: $2,700
    """

    # 2025 thresholds and rates
    CASH_WAGE_THRESHOLD_2025: ClassVar[float] = 2700.0
    FUTA_QUARTERLY_THRESHOLD: ClassVar[float] = 1000.0
    SOCIAL_SECURITY_WAGE_BASE_2025: ClassVar[float] = 176100.0
    FUTA_WAGE_BASE: ClassVar[float] = 7000.0

    # Tax rates
    SOCIAL_SECURITY_RATE: ClassVar[float] = 0.124  # 12.4% total
    MEDICARE_RATE: ClassVar[float] = 0.029  # 2.9% total
    ADDITIONAL_MEDICARE_RATE: ClassVar[float] = 0.009  # 0.9% employee only
    ADDITIONAL_MEDICARE_THRESHOLD: ClassVar[float] = 200000.0
    FUTA_RATE: ClassVar[float] = 0.060  # 6.0% before credit
    FUTA_CREDIT_RATE: ClassVar[float] = 0.054  # 5.4% credit for state UI
    FUTA_NET_RATE: ClassVar[float] = 0.006  # 0.6% after credit

    # Employer info
    employer_name: str = Field(default="", description="Employer's name")
    employer_ein: Optional[str] = Field(default=None, description="Employer EIN (if any)")

    # Employees
    employees: List[HouseholdEmployee] = Field(
        default_factory=list,
        description="List of household employees"
    )

    # State unemployment
    state_code: str = Field(default="", description="State where wages paid")
    state_unemployment_paid: float = Field(
        default=0.0,
        ge=0,
        description="State unemployment contributions paid"
    )
    state_has_credit_reduction: bool = Field(
        default=False,
        description="State has FUTA credit reduction (rare)"
    )
    credit_reduction_rate: float = Field(
        default=0.0,
        ge=0,
        le=0.054,
        description="Credit reduction rate if applicable"
    )

    # Prior payments
    prior_period_taxes_paid: float = Field(
        default=0.0,
        ge=0,
        description="Taxes paid in prior periods of same year"
    )

    def get_total_cash_wages(self) -> float:
        """Get total cash wages paid to all employees."""
        return sum(emp.total_cash_wages for emp in self.employees)

    def get_max_quarterly_wages(self) -> float:
        """Get maximum total wages paid in any single quarter."""
        if not self.employees:
            return 0.0

        # Sum wages by quarter across all employees
        q1 = sum(emp.q1_wages for emp in self.employees)
        q2 = sum(emp.q2_wages for emp in self.employees)
        q3 = sum(emp.q3_wages for emp in self.employees)
        q4 = sum(emp.q4_wages for emp in self.employees)

        return max(q1, q2, q3, q4)

    def is_subject_to_household_employment_taxes(self) -> tuple[bool, str]:
        """
        Determine if employer must file Schedule H.

        Must file if:
        1. Paid any one employee >= $2,700, OR
        2. Withheld federal income tax, OR
        3. Paid total >= $1,000 in any quarter (for FUTA)
        """
        # Check individual employee threshold
        for emp in self.employees:
            if emp.total_cash_wages >= self.CASH_WAGE_THRESHOLD_2025:
                return True, f"Employee {emp.employee_name or 'unnamed'} paid >= ${self.CASH_WAGE_THRESHOLD_2025:,.0f}"

            if emp.federal_income_tax_withheld > 0:
                return True, "Federal income tax withheld at employee request"

        # Check quarterly threshold
        if self.get_max_quarterly_wages() >= self.FUTA_QUARTERLY_THRESHOLD:
            return True, f"Quarterly wages >= ${self.FUTA_QUARTERLY_THRESHOLD:,.0f} (FUTA applicable)"

        return False, "Below all thresholds"

    def calculate_social_security_medicare(self) -> dict:
        """
        Calculate Part I - Social Security and Medicare taxes.

        Social Security: 12.4% on wages up to wage base
        Medicare: 2.9% on all wages
        Additional Medicare: 0.9% on wages over $200k (employee portion only)
        """
        result = {
            'total_social_security_wages': 0.0,
            'total_medicare_wages': 0.0,
            'social_security_tax': 0.0,
            'medicare_tax': 0.0,
            'additional_medicare_tax': 0.0,
            'total_tax': 0.0,
            'employee_details': [],
        }

        for emp in self.employees:
            emp_detail = {
                'name': emp.employee_name,
                'wages': emp.total_cash_wages,
                'exempt': emp.is_exempt_from_social_security_medicare(),
                'ss_wages': 0.0,
                'medicare_wages': 0.0,
                'ss_tax': 0.0,
                'medicare_tax': 0.0,
                'additional_medicare': 0.0,
            }

            # Skip exempt employees
            if emp.is_exempt_from_social_security_medicare():
                result['employee_details'].append(emp_detail)
                continue

            # Check if wages meet threshold
            if emp.total_cash_wages < self.CASH_WAGE_THRESHOLD_2025:
                result['employee_details'].append(emp_detail)
                continue

            # Social Security wages (capped at wage base)
            ss_wages = min(emp.total_cash_wages, self.SOCIAL_SECURITY_WAGE_BASE_2025)
            emp_detail['ss_wages'] = ss_wages
            result['total_social_security_wages'] += ss_wages

            # Medicare wages (no cap)
            medicare_wages = emp.total_cash_wages
            emp_detail['medicare_wages'] = medicare_wages
            result['total_medicare_wages'] += medicare_wages

            # Calculate taxes
            ss_tax = ss_wages * self.SOCIAL_SECURITY_RATE
            emp_detail['ss_tax'] = round(ss_tax, 2)
            result['social_security_tax'] += ss_tax

            medicare_tax = medicare_wages * self.MEDICARE_RATE
            emp_detail['medicare_tax'] = round(medicare_tax, 2)
            result['medicare_tax'] += medicare_tax

            # Additional Medicare (employee portion only, above $200k)
            if medicare_wages > self.ADDITIONAL_MEDICARE_THRESHOLD:
                excess = medicare_wages - self.ADDITIONAL_MEDICARE_THRESHOLD
                add_medicare = excess * self.ADDITIONAL_MEDICARE_RATE
                emp_detail['additional_medicare'] = round(add_medicare, 2)
                result['additional_medicare_tax'] += add_medicare

            result['employee_details'].append(emp_detail)

        # Round totals
        result['social_security_tax'] = round(result['social_security_tax'], 2)
        result['medicare_tax'] = round(result['medicare_tax'], 2)
        result['additional_medicare_tax'] = round(result['additional_medicare_tax'], 2)
        result['total_tax'] = round(
            result['social_security_tax'] +
            result['medicare_tax'] +
            result['additional_medicare_tax'],
            2
        )

        return result

    def calculate_futa(self) -> dict:
        """
        Calculate Part II - Federal Unemployment (FUTA) Tax.

        FUTA: 6.0% on first $7,000 of wages per employee
        Credit: 5.4% for state unemployment contributions
        Net rate: 0.6% (or higher if state has credit reduction)
        """
        result = {
            'subject_to_futa': False,
            'futa_wages': 0.0,
            'gross_futa_tax': 0.0,
            'state_credit': 0.0,
            'credit_reduction': 0.0,
            'net_futa_tax': 0.0,
            'employee_details': [],
        }

        # Check if subject to FUTA (quarterly threshold)
        max_quarterly = self.get_max_quarterly_wages()
        if max_quarterly < self.FUTA_QUARTERLY_THRESHOLD:
            return result

        result['subject_to_futa'] = True

        for emp in self.employees:
            emp_detail = {
                'name': emp.employee_name,
                'total_wages': emp.total_cash_wages,
                'futa_wages': 0.0,
                'futa_tax': 0.0,
            }

            # Spouse is exempt from FUTA
            if emp.is_spouse:
                result['employee_details'].append(emp_detail)
                continue

            # FUTA wages are capped at wage base
            futa_wages = min(emp.total_cash_wages, self.FUTA_WAGE_BASE)
            emp_detail['futa_wages'] = futa_wages
            result['futa_wages'] += futa_wages

            # Gross FUTA tax
            futa_tax = futa_wages * self.FUTA_RATE
            emp_detail['futa_tax'] = round(futa_tax, 2)
            result['gross_futa_tax'] += futa_tax

            result['employee_details'].append(emp_detail)

        # Calculate credit (5.4% standard, reduced if state has issues)
        credit_rate = self.FUTA_CREDIT_RATE - self.credit_reduction_rate
        result['state_credit'] = round(result['futa_wages'] * credit_rate, 2)

        # Credit reduction if applicable
        if self.state_has_credit_reduction:
            result['credit_reduction'] = round(
                result['futa_wages'] * self.credit_reduction_rate, 2
            )

        # Net FUTA tax
        result['gross_futa_tax'] = round(result['gross_futa_tax'], 2)
        result['net_futa_tax'] = round(
            result['gross_futa_tax'] - result['state_credit'], 2
        )

        return result

    def calculate_total_withheld(self) -> dict:
        """Calculate total amounts withheld from employees."""
        result = {
            'federal_income_tax': 0.0,
            'social_security': 0.0,
            'medicare': 0.0,
            'additional_medicare': 0.0,
            'total': 0.0,
        }

        for emp in self.employees:
            result['federal_income_tax'] += emp.federal_income_tax_withheld
            result['social_security'] += emp.social_security_withheld
            result['medicare'] += emp.medicare_withheld
            result['additional_medicare'] += emp.additional_medicare_withheld

        result['total'] = (
            result['federal_income_tax'] +
            result['social_security'] +
            result['medicare'] +
            result['additional_medicare']
        )

        return result

    def calculate_schedule_h(self) -> dict:
        """
        Complete Schedule H calculation.

        Returns comprehensive breakdown including:
        - Eligibility determination
        - Social Security and Medicare taxes
        - FUTA tax
        - Total household employment taxes
        - Balance due or refund
        """
        result = {
            'employer_name': self.employer_name,

            # Eligibility
            'must_file': False,
            'reason': '',

            # Part I: Social Security and Medicare
            'social_security_medicare': {},
            'total_ss_medicare_tax': 0.0,

            # Part II: FUTA
            'futa': {},
            'total_futa_tax': 0.0,

            # Part III: Total Taxes
            'total_household_employment_tax': 0.0,
            'federal_income_tax_withheld': 0.0,
            'total_taxes_and_withholding': 0.0,

            # Part IV: Balance
            'prior_payments': self.prior_period_taxes_paid,
            'amount_owed': 0.0,
            'overpayment': 0.0,

            # Summary
            'total_wages_paid': self.get_total_cash_wages(),
            'number_of_employees': len(self.employees),
        }

        # Check if must file
        must_file, reason = self.is_subject_to_household_employment_taxes()
        result['must_file'] = must_file
        result['reason'] = reason

        if not must_file:
            return result

        # Calculate Social Security and Medicare
        ss_medicare = self.calculate_social_security_medicare()
        result['social_security_medicare'] = ss_medicare
        result['total_ss_medicare_tax'] = ss_medicare['total_tax']

        # Calculate FUTA
        futa = self.calculate_futa()
        result['futa'] = futa
        result['total_futa_tax'] = futa['net_futa_tax']

        # Total household employment taxes
        result['total_household_employment_tax'] = round(
            result['total_ss_medicare_tax'] + result['total_futa_tax'], 2
        )

        # Federal income tax withheld (passed through to Form 1040)
        withheld = self.calculate_total_withheld()
        result['federal_income_tax_withheld'] = withheld['federal_income_tax']

        # Total (taxes + withheld FIT)
        result['total_taxes_and_withholding'] = round(
            result['total_household_employment_tax'] +
            result['federal_income_tax_withheld'],
            2
        )

        # Balance due or overpayment
        balance = result['total_taxes_and_withholding'] - self.prior_period_taxes_paid
        if balance > 0:
            result['amount_owed'] = round(balance, 2)
        else:
            result['overpayment'] = round(abs(balance), 2)

        return result

    def get_schedule_h_summary(self) -> dict:
        """Get summary suitable for tax return integration."""
        calc = self.calculate_schedule_h()
        return {
            'must_file': calc['must_file'],
            'total_household_employment_tax': calc['total_household_employment_tax'],
            'social_security_medicare_tax': calc['total_ss_medicare_tax'],
            'futa_tax': calc['total_futa_tax'],
            'amount_owed': calc['amount_owed'],
        }


def calculate_household_employment_tax(
    wages_paid: float,
    is_exempt: bool = False,
    withheld_fit: float = 0.0,
) -> dict:
    """
    Convenience function for simple household employment tax calculation.

    Args:
        wages_paid: Total cash wages paid to household employee
        is_exempt: Whether employee is exempt (spouse, child under 21)
        withheld_fit: Federal income tax withheld at employee's request

    Returns:
        Dictionary with tax calculations
    """
    employee = HouseholdEmployee(
        total_cash_wages=wages_paid,
        federal_income_tax_withheld=withheld_fit,
        is_spouse=is_exempt,
        # Distribute wages evenly across quarters for FUTA determination
        q1_wages=wages_paid / 4,
        q2_wages=wages_paid / 4,
        q3_wages=wages_paid / 4,
        q4_wages=wages_paid / 4,
    )

    schedule = ScheduleH(employees=[employee])
    return schedule.calculate_schedule_h()
