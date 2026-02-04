"""
Comprehensive Tax Validation Rules Engine.

Implements 100+ conditional rules for smart field visibility,
mandatory field validation, and intelligent data capture.

Based on IRS rules for Tax Year 2025.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import re


class FieldRequirement(str, Enum):
    """Field requirement levels."""
    MANDATORY = "mandatory"              # Always required
    CONDITIONAL_MANDATORY = "conditional"  # Required based on conditions
    OPTIONAL = "optional"                 # Never required
    HIDDEN = "hidden"                     # Should not be shown


class ValidationSeverity(str, Enum):
    """Validation message severity."""
    ERROR = "error"        # Blocks submission
    WARNING = "warning"    # Allows submission with confirmation
    INFO = "info"          # Informational only


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    message: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR
    field: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class FieldState:
    """State of a field based on conditions."""
    field_id: str
    requirement: FieldRequirement
    visible: bool = True
    enabled: bool = True
    default_value: Any = None
    label: Optional[str] = None
    hint: Optional[str] = None
    validation_rules: List[str] = field(default_factory=list)


@dataclass
class TaxContext:
    """Context containing all tax return data for rule evaluation."""
    # Personal Information
    first_name: str = ""
    last_name: str = ""
    ssn: str = ""
    date_of_birth: Optional[str] = None
    is_blind: bool = False

    # Spouse Information
    spouse_first_name: str = ""
    spouse_last_name: str = ""
    spouse_ssn: str = ""
    spouse_dob: Optional[str] = None
    spouse_is_blind: bool = False

    # Filing Status
    filing_status: str = ""

    # Address
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""

    # Dependents
    dependents: List[Dict[str, Any]] = field(default_factory=list)

    # Income
    wages: float = 0.0
    wages_secondary: float = 0.0
    interest_income: float = 0.0
    dividend_income: float = 0.0
    qualified_dividends: float = 0.0
    capital_gains_short: float = 0.0
    capital_gains_long: float = 0.0
    business_income: float = 0.0
    business_expenses: float = 0.0
    rental_income: float = 0.0
    rental_expenses: float = 0.0
    retirement_income: float = 0.0
    social_security: float = 0.0
    unemployment: float = 0.0
    other_income: float = 0.0

    # Withholding
    federal_withheld: float = 0.0
    state_withheld: float = 0.0

    # Deductions
    use_standard_deduction: bool = True
    medical_expenses: float = 0.0
    state_local_taxes: float = 0.0
    real_estate_taxes: float = 0.0
    mortgage_interest: float = 0.0
    charitable_cash: float = 0.0
    charitable_noncash: float = 0.0
    student_loan_interest: float = 0.0
    educator_expenses: float = 0.0
    hsa_contribution: float = 0.0
    ira_contribution: float = 0.0

    # Credits
    child_care_expenses: float = 0.0
    child_care_provider_name: str = ""
    child_care_provider_ein: str = ""
    education_expenses: float = 0.0
    student_name: str = ""
    school_name: str = ""
    energy_improvements: float = 0.0
    foreign_tax_paid: float = 0.0

    # State
    state_of_residence: str = ""

    # Calculated fields (set by engine)
    age: int = 0
    spouse_age: int = 0
    total_income: float = 0.0
    agi: float = 0.0
    num_dependents: int = 0
    num_qualifying_children: int = 0
    earned_income: float = 0.0

    def calculate_derived_fields(self) -> None:
        """Calculate all derived fields from input data."""
        # Calculate ages
        today = date.today()
        tax_year_end = date(2025, 12, 31)

        if self.date_of_birth:
            try:
                dob = self._parse_date(self.date_of_birth)
                self.age = self._calculate_age(dob, tax_year_end)
            except (ValueError, TypeError):
                self.age = 0

        if self.spouse_dob:
            try:
                spouse_dob = self._parse_date(self.spouse_dob)
                self.spouse_age = self._calculate_age(spouse_dob, tax_year_end)
            except (ValueError, TypeError):
                self.spouse_age = 0

        # Calculate income totals
        self.earned_income = self.wages + self.wages_secondary + max(0, self.business_income - self.business_expenses)
        self.total_income = (
            self.wages + self.wages_secondary +
            self.interest_income + self.dividend_income +
            self.capital_gains_short + self.capital_gains_long +
            max(0, self.business_income - self.business_expenses) +
            max(0, self.rental_income - self.rental_expenses) +
            self.retirement_income + self.social_security +
            self.unemployment + self.other_income
        )

        # Count dependents
        self.num_dependents = len(self.dependents)
        self.num_qualifying_children = sum(
            1 for d in self.dependents
            if d.get('age', 99) < 17
        )

    def _parse_date(self, date_str: str) -> date:
        """Parse date from various formats."""
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")

    def _calculate_age(self, dob: date, as_of: date) -> int:
        """Calculate age as of a specific date."""
        age = as_of.year - dob.year
        if (as_of.month, as_of.day) < (dob.month, dob.day):
            age -= 1
        return age


class TaxRulesEngine:
    """
    Comprehensive rules engine for tax form validation.

    Implements 100+ conditional rules for:
    - Field visibility (show/hide based on conditions)
    - Field requirements (mandatory, conditional, optional)
    - Data validation (format, range, cross-field)
    - Smart defaults and suggestions
    """

    # IRS Limits for 2025 (IRS Rev. Proc. 2024-40)
    LIMITS = {
        'standard_deduction_single': 15750,
        'standard_deduction_mfj': 31500,
        'standard_deduction_mfs': 15750,
        'standard_deduction_hoh': 23625,
        'standard_deduction_qw': 31500,
        'additional_deduction_65_single': 1950,
        'additional_deduction_65_married': 1550,
        'additional_deduction_blind_single': 1950,
        'additional_deduction_blind_married': 1550,
        'salt_cap': 10000,
        'student_loan_interest_max': 2500,
        'educator_expenses_max': 300,
        'ira_contribution_max': 7000,
        'ira_contribution_max_50plus': 8000,
        'hsa_individual_max': 4300,
        'hsa_family_max': 8550,
        'hsa_catchup_55plus': 1000,
        'eitc_max_no_children': 649,
        'eitc_max_1_child': 4328,
        'eitc_max_2_children': 7152,
        'eitc_max_3plus_children': 8046,
        'eitc_income_limit_single_no_child': 18591,
        'eitc_income_limit_single_1_child': 49084,
        'eitc_income_limit_single_2_children': 55768,
        'eitc_income_limit_single_3plus': 59899,
        'eitc_income_limit_mfj_no_child': 25511,
        'eitc_income_limit_mfj_1_child': 56004,
        'eitc_income_limit_mfj_2_children': 62688,
        'eitc_income_limit_mfj_3plus': 66819,
        'ctc_amount': 2000,
        'ctc_refundable_max': 1700,
        'ctc_phaseout_single': 200000,
        'ctc_phaseout_mfj': 400000,
        'dependent_care_max_1': 3000,
        'dependent_care_max_2plus': 6000,
        'aotc_max': 2500,
        'llc_max': 2000,
        'social_security_max_taxable': 176100,
        'medicare_additional_threshold_single': 200000,
        'medicare_additional_threshold_mfj': 250000,
        'amt_exemption_single': 88100,
        'amt_exemption_mfj': 137000,
        'capital_gains_0_rate_single': 48350,
        'capital_gains_0_rate_mfj': 96700,
        'capital_gains_15_rate_single': 533400,
        'capital_gains_15_rate_mfj': 600050,
        'nii_threshold_single': 200000,
        'nii_threshold_mfj': 250000,
    }

    def __init__(self):
        """Initialize the rules engine."""
        self._rules: Dict[str, List[Callable]] = {}
        self._field_rules: Dict[str, List[Callable]] = {}
        self._register_all_rules()

    def _register_all_rules(self) -> None:
        """Register all 100+ validation and conditional rules."""
        # ===== PERSONAL INFORMATION RULES =====
        self._register_personal_rules()

        # ===== FILING STATUS RULES =====
        self._register_filing_status_rules()

        # ===== SPOUSE RULES =====
        self._register_spouse_rules()

        # ===== DEPENDENT RULES =====
        self._register_dependent_rules()

        # ===== INCOME RULES =====
        self._register_income_rules()

        # ===== DEDUCTION RULES =====
        self._register_deduction_rules()

        # ===== CREDIT RULES =====
        self._register_credit_rules()

        # ===== STATE TAX RULES =====
        self._register_state_rules()

        # ===== CROSS-FIELD VALIDATION RULES =====
        self._register_cross_field_rules()

    def _register_personal_rules(self) -> None:
        """Register personal information validation rules."""

        # Rule 1: SSN format validation — delegates to canonical validator
        def validate_ssn(ctx: TaxContext) -> ValidationResult:
            if not ctx.ssn:
                return ValidationResult(False, "Social Security Number is required",
                                        ValidationSeverity.ERROR, "ssn")
            from web.validation_helpers import validate_ssn as _ssn_check
            is_valid, error_msg = _ssn_check(ctx.ssn)
            if not is_valid:
                return ValidationResult(False, error_msg or "Invalid SSN format",
                                        ValidationSeverity.ERROR, "ssn")
            return ValidationResult(True)

        self._rules['ssn'] = [validate_ssn]

        # Rule 2: Date of birth validation
        def validate_dob(ctx: TaxContext) -> ValidationResult:
            if not ctx.date_of_birth:
                return ValidationResult(False, "Date of birth is required",
                                        ValidationSeverity.ERROR, "date_of_birth")
            try:
                dob = ctx._parse_date(ctx.date_of_birth)
                today = date.today()
                if dob > today:
                    return ValidationResult(False, "Date of birth cannot be in the future",
                                            ValidationSeverity.ERROR, "date_of_birth")
                age = ctx._calculate_age(dob, today)
                if age < 0 or age > 125:
                    return ValidationResult(False, "Please verify date of birth",
                                            ValidationSeverity.WARNING, "date_of_birth")
                if age < 16:
                    return ValidationResult(False, "Taxpayer must be at least 16 to file independently",
                                            ValidationSeverity.WARNING, "date_of_birth")
            except (ValueError, TypeError, AttributeError):
                return ValidationResult(False, "Invalid date format. Use MM/DD/YYYY",
                                        ValidationSeverity.ERROR, "date_of_birth")
            return ValidationResult(True)

        self._rules['date_of_birth'] = [validate_dob]

        # Rule 3: Name validation
        def validate_name(ctx: TaxContext) -> ValidationResult:
            if not ctx.first_name or not ctx.first_name.strip():
                return ValidationResult(False, "First name is required",
                                        ValidationSeverity.ERROR, "first_name")
            if not ctx.last_name or not ctx.last_name.strip():
                return ValidationResult(False, "Last name is required",
                                        ValidationSeverity.ERROR, "last_name")
            # Check for invalid characters
            if not re.match(r"^[a-zA-Z\s\-'\.]+$", ctx.first_name):
                return ValidationResult(False, "First name contains invalid characters",
                                        ValidationSeverity.ERROR, "first_name")
            return ValidationResult(True)

        self._rules['name'] = [validate_name]

        # Rule 4: Address validation
        def validate_address(ctx: TaxContext) -> ValidationResult:
            if not ctx.street:
                return ValidationResult(False, "Street address is required",
                                        ValidationSeverity.ERROR, "street")
            if not ctx.city:
                return ValidationResult(False, "City is required",
                                        ValidationSeverity.ERROR, "city")
            if not ctx.state:
                return ValidationResult(False, "State is required",
                                        ValidationSeverity.ERROR, "state")
            if not ctx.zip_code:
                return ValidationResult(False, "ZIP code is required",
                                        ValidationSeverity.ERROR, "zip_code")
            # Validate ZIP format
            if not re.match(r'^\d{5}(-\d{4})?$', ctx.zip_code):
                return ValidationResult(False, "Invalid ZIP code format",
                                        ValidationSeverity.ERROR, "zip_code")
            return ValidationResult(True)

        self._rules['address'] = [validate_address]

    def _register_filing_status_rules(self) -> None:
        """Register filing status validation rules."""

        # Rule 5: Filing status required
        def validate_filing_status_required(ctx: TaxContext) -> ValidationResult:
            if not ctx.filing_status:
                return ValidationResult(False, "Filing status is required",
                                        ValidationSeverity.ERROR, "filing_status")
            valid_statuses = ['single', 'married_joint', 'married_separate',
                           'head_of_household', 'qualifying_widow']
            if ctx.filing_status not in valid_statuses:
                return ValidationResult(False, "Invalid filing status",
                                        ValidationSeverity.ERROR, "filing_status")
            return ValidationResult(True)

        self._rules['filing_status'] = [validate_filing_status_required]

        # Rule 6: Head of Household requires qualifying person
        def validate_hoh_requirements(ctx: TaxContext) -> ValidationResult:
            if ctx.filing_status != 'head_of_household':
                return ValidationResult(True)
            if ctx.num_dependents == 0:
                return ValidationResult(
                    False,
                    "Head of Household requires a qualifying person (dependent)",
                    ValidationSeverity.ERROR,
                    "filing_status",
                    "Consider filing as Single if you don't have dependents"
                )
            return ValidationResult(True)

        self._rules['hoh_requirements'] = [validate_hoh_requirements]

        # Rule 7: Qualifying Widow(er) requirements
        def validate_qw_requirements(ctx: TaxContext) -> ValidationResult:
            if ctx.filing_status != 'qualifying_widow':
                return ValidationResult(True)
            # Must have dependent child
            has_qualifying_child = any(
                d.get('age', 99) < 19 or (d.get('is_student', False) and d.get('age', 99) < 24)
                for d in ctx.dependents
            )
            if not has_qualifying_child:
                return ValidationResult(
                    False,
                    "Qualifying Widow(er) status requires a dependent child",
                    ValidationSeverity.ERROR,
                    "filing_status"
                )
            return ValidationResult(True)

        self._rules['qw_requirements'] = [validate_qw_requirements]

        # Rule 8: MFS special rules
        def validate_mfs_considerations(ctx: TaxContext) -> ValidationResult:
            if ctx.filing_status != 'married_separate':
                return ValidationResult(True)
            # Warning about limitations
            if ctx.num_qualifying_children > 0:
                return ValidationResult(
                    True,
                    "Married Filing Separately limits some credits like EITC and Child Tax Credit",
                    ValidationSeverity.WARNING,
                    "filing_status",
                    "Consider Married Filing Jointly for potentially better benefits"
                )
            return ValidationResult(True)

        self._rules['mfs_considerations'] = [validate_mfs_considerations]

    def _register_spouse_rules(self) -> None:
        """Register spouse-related validation rules."""

        # Rule 9-15: Spouse information conditional requirements
        def get_spouse_field_states(ctx: TaxContext) -> Dict[str, FieldState]:
            """Determine spouse field visibility and requirements."""
            is_married = ctx.filing_status in ('married_joint', 'married_separate')

            return {
                'spouse_first_name': FieldState(
                    'spouse_first_name',
                    FieldRequirement.CONDITIONAL_MANDATORY if is_married else FieldRequirement.HIDDEN,
                    visible=is_married
                ),
                'spouse_last_name': FieldState(
                    'spouse_last_name',
                    FieldRequirement.CONDITIONAL_MANDATORY if is_married else FieldRequirement.HIDDEN,
                    visible=is_married
                ),
                'spouse_ssn': FieldState(
                    'spouse_ssn',
                    FieldRequirement.CONDITIONAL_MANDATORY if is_married else FieldRequirement.HIDDEN,
                    visible=is_married
                ),
                'spouse_dob': FieldState(
                    'spouse_dob',
                    FieldRequirement.CONDITIONAL_MANDATORY if is_married else FieldRequirement.HIDDEN,
                    visible=is_married
                ),
                'spouse_is_blind': FieldState(
                    'spouse_is_blind',
                    FieldRequirement.OPTIONAL if is_married else FieldRequirement.HIDDEN,
                    visible=is_married and ctx.spouse_age >= 0  # Only show if DOB provided
                ),
            }

        self._field_rules['spouse_fields'] = get_spouse_field_states

        # Rule 16: Validate spouse SSN if married
        def validate_spouse_ssn(ctx: TaxContext) -> ValidationResult:
            if ctx.filing_status not in ('married_joint', 'married_separate'):
                return ValidationResult(True)
            if not ctx.spouse_ssn:
                return ValidationResult(False, "Spouse SSN is required for married filing",
                                        ValidationSeverity.ERROR, "spouse_ssn")
            ssn_clean = re.sub(r'[^0-9]', '', ctx.spouse_ssn)
            if len(ssn_clean) != 9:
                return ValidationResult(False, "Spouse SSN must be 9 digits",
                                        ValidationSeverity.ERROR, "spouse_ssn")
            # Check SSN is different from primary
            primary_ssn = re.sub(r'[^0-9]', '', ctx.ssn)
            if ssn_clean == primary_ssn:
                return ValidationResult(False, "Spouse SSN must be different from primary taxpayer",
                                        ValidationSeverity.ERROR, "spouse_ssn")
            return ValidationResult(True)

        self._rules['spouse_ssn'] = [validate_spouse_ssn]

    def _register_dependent_rules(self) -> None:
        """Register dependent-related validation rules."""

        # Rule 17-25: Dependent validation
        def validate_dependent(dep: Dict, ctx: TaxContext, index: int) -> List[ValidationResult]:
            """Validate a single dependent."""
            results = []
            prefix = f"dependent_{index}"

            # Name required
            if not dep.get('name'):
                results.append(ValidationResult(
                    False, f"Dependent {index + 1}: Name is required",
                    ValidationSeverity.ERROR, f"{prefix}_name"
                ))

            # SSN required
            if not dep.get('ssn'):
                results.append(ValidationResult(
                    False, f"Dependent {index + 1}: SSN is required for tax benefits",
                    ValidationSeverity.WARNING, f"{prefix}_ssn"
                ))

            # Relationship required
            if not dep.get('relationship'):
                results.append(ValidationResult(
                    False, f"Dependent {index + 1}: Relationship is required",
                    ValidationSeverity.ERROR, f"{prefix}_relationship"
                ))

            # Age validation
            age = dep.get('age')
            if age is None:
                results.append(ValidationResult(
                    False, f"Dependent {index + 1}: Age or date of birth is required",
                    ValidationSeverity.ERROR, f"{prefix}_age"
                ))
            else:
                # Child Tax Credit eligibility
                if age < 17:
                    results.append(ValidationResult(
                        True, f"Dependent {index + 1}: Eligible for Child Tax Credit",
                        ValidationSeverity.INFO, f"{prefix}_ctc"
                    ))
                elif age < 19 or (dep.get('is_student') and age < 24):
                    results.append(ValidationResult(
                        True, f"Dependent {index + 1}: May qualify as dependent but not for CTC",
                        ValidationSeverity.INFO, f"{prefix}_dependent"
                    ))
                elif age >= 24 and not dep.get('is_disabled'):
                    results.append(ValidationResult(
                        True, f"Dependent {index + 1}: Verify dependent eligibility - age 24+",
                        ValidationSeverity.WARNING, f"{prefix}_age_check"
                    ))

            return results

        def validate_all_dependents(ctx: TaxContext) -> List[ValidationResult]:
            results = []
            for i, dep in enumerate(ctx.dependents):
                results.extend(validate_dependent(dep, ctx, i))
            return results

        self._rules['dependents'] = [lambda ctx: validate_all_dependents(ctx)]

    def _register_income_rules(self) -> None:
        """Register income-related validation rules."""

        # Rule 26: Wages validation
        def validate_wages(ctx: TaxContext) -> ValidationResult:
            if ctx.wages < 0:
                return ValidationResult(False, "Wages cannot be negative",
                                        ValidationSeverity.ERROR, "wages")
            if ctx.wages > 10000000:
                return ValidationResult(True, "Please verify wage amount - unusually high",
                                        ValidationSeverity.WARNING, "wages")
            return ValidationResult(True)

        self._rules['wages'] = [validate_wages]

        # Rule 27: Withholding validation
        def validate_withholding(ctx: TaxContext) -> ValidationResult:
            if ctx.federal_withheld < 0:
                return ValidationResult(False, "Withholding cannot be negative",
                                        ValidationSeverity.ERROR, "federal_withheld")
            # Check if withholding seems reasonable
            total_wages = ctx.wages + ctx.wages_secondary
            if total_wages > 0 and ctx.federal_withheld > total_wages * 0.5:
                return ValidationResult(
                    True,
                    "Federal withholding seems high relative to wages. Please verify.",
                    ValidationSeverity.WARNING,
                    "federal_withheld"
                )
            return ValidationResult(True)

        self._rules['withholding'] = [validate_withholding]

        # Rule 28-30: Self-employment rules
        def get_self_employment_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            has_self_employment = ctx.business_income > 0 or ctx.business_expenses > 0
            return {
                'business_income': FieldState(
                    'business_income',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint="Income from self-employment, freelance, gig work"
                ),
                'business_expenses': FieldState(
                    'business_expenses',
                    FieldRequirement.CONDITIONAL_MANDATORY if ctx.business_income > 0 else FieldRequirement.OPTIONAL,
                    visible=ctx.business_income > 0 or ctx.business_expenses > 0,
                    hint="Deductible business expenses"
                ),
                'self_employment_tax_info': FieldState(
                    'self_employment_tax_info',
                    FieldRequirement.OPTIONAL,
                    visible=has_self_employment and (ctx.business_income - ctx.business_expenses) > 400,
                    hint="Self-employment tax applies to net earnings over $400"
                ),
            }

        self._field_rules['self_employment'] = get_self_employment_fields

        # Rule 31-35: Investment income rules
        def get_investment_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            has_dividends = ctx.dividend_income > 0
            has_capital_gains = ctx.capital_gains_short != 0 or ctx.capital_gains_long != 0

            return {
                'qualified_dividends': FieldState(
                    'qualified_dividends',
                    FieldRequirement.CONDITIONAL_MANDATORY if has_dividends else FieldRequirement.HIDDEN,
                    visible=has_dividends,
                    hint="Qualified dividends are taxed at lower capital gains rates"
                ),
                'capital_gains_short': FieldState(
                    'capital_gains_short',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint="Short-term gains (held < 1 year) taxed as ordinary income"
                ),
                'capital_gains_long': FieldState(
                    'capital_gains_long',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint="Long-term gains (held > 1 year) taxed at preferential rates"
                ),
            }

        self._field_rules['investment'] = get_investment_fields

        # Rule 36-40: Retirement income rules
        def get_retirement_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Retirement fields based on age."""
            is_retirement_age = ctx.age >= 59  # 59½ for penalty-free withdrawals

            return {
                'retirement_income': FieldState(
                    'retirement_income',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint="IRA, 401(k), pension distributions"
                ),
                'early_withdrawal_penalty': FieldState(
                    'early_withdrawal_penalty',
                    FieldRequirement.CONDITIONAL_MANDATORY if ctx.retirement_income > 0 and ctx.age < 59 else FieldRequirement.HIDDEN,
                    visible=ctx.retirement_income > 0 and ctx.age < 59,
                    hint="10% penalty may apply for withdrawals before age 59½"
                ),
                'rmd_notice': FieldState(
                    'rmd_notice',
                    FieldRequirement.HIDDEN,
                    visible=ctx.age >= 73,
                    hint="Required Minimum Distributions may apply at age 73+"
                ),
            }

        self._field_rules['retirement'] = get_retirement_fields

        # Rule 41-45: Social Security rules
        def get_social_security_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Social Security fields based on age."""
            is_ss_age = ctx.age >= 62  # Earliest SS eligibility

            return {
                'social_security': FieldState(
                    'social_security',
                    FieldRequirement.OPTIONAL,
                    visible=ctx.age >= 55 or ctx.social_security > 0,  # Show if near age or has income
                    hint="Enter total Social Security benefits received"
                ),
                'ss_taxable_info': FieldState(
                    'ss_taxable_info',
                    FieldRequirement.HIDDEN,
                    visible=ctx.social_security > 0,
                    hint="Up to 85% of benefits may be taxable based on total income"
                ),
            }

        self._field_rules['social_security'] = get_social_security_fields

    def _register_deduction_rules(self) -> None:
        """Register deduction-related validation rules."""

        # Rule 46-50: Standard vs Itemized decision
        def get_deduction_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Determine which deduction fields to show."""
            # Calculate standard deduction
            std_ded = self._get_standard_deduction(ctx)

            # Show itemized fields if user chooses itemized or if potentially beneficial
            show_itemized = not ctx.use_standard_deduction

            return {
                'use_standard_deduction': FieldState(
                    'use_standard_deduction',
                    FieldRequirement.MANDATORY,
                    visible=True,
                    default_value=True,
                    hint=f"Standard deduction for your status: ${std_ded:,.0f}"
                ),
                'medical_expenses': FieldState(
                    'medical_expenses',
                    FieldRequirement.OPTIONAL if show_itemized else FieldRequirement.HIDDEN,
                    visible=show_itemized,
                    hint=f"Only expenses exceeding 7.5% of AGI (${ctx.agi * 0.075:,.0f}) are deductible"
                ),
                'state_local_taxes': FieldState(
                    'state_local_taxes',
                    FieldRequirement.OPTIONAL if show_itemized else FieldRequirement.HIDDEN,
                    visible=show_itemized,
                    hint=f"SALT deduction capped at ${self.LIMITS['salt_cap']:,}"
                ),
                'mortgage_interest': FieldState(
                    'mortgage_interest',
                    FieldRequirement.OPTIONAL if show_itemized else FieldRequirement.HIDDEN,
                    visible=show_itemized
                ),
                'charitable_cash': FieldState(
                    'charitable_cash',
                    FieldRequirement.OPTIONAL if show_itemized else FieldRequirement.HIDDEN,
                    visible=show_itemized
                ),
            }

        self._field_rules['deductions'] = get_deduction_fields

        # Rule 51-55: Above-the-line deduction rules
        def get_adjustment_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Above-the-line adjustments (always available)."""
            is_educator = ctx.wages > 0  # Simplified check
            is_50_plus = ctx.age >= 50

            ira_limit = self.LIMITS['ira_contribution_max_50plus'] if is_50_plus else self.LIMITS['ira_contribution_max']

            return {
                'student_loan_interest': FieldState(
                    'student_loan_interest',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint=f"Maximum deduction: ${self.LIMITS['student_loan_interest_max']:,}"
                ),
                'educator_expenses': FieldState(
                    'educator_expenses',
                    FieldRequirement.OPTIONAL,
                    visible=is_educator,
                    hint=f"For K-12 teachers. Maximum: ${self.LIMITS['educator_expenses_max']:,}"
                ),
                'hsa_contribution': FieldState(
                    'hsa_contribution',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint=f"Must have HDHP. Max: ${self.LIMITS['hsa_family_max']:,} (family)"
                ),
                'ira_contribution': FieldState(
                    'ira_contribution',
                    FieldRequirement.OPTIONAL,
                    visible=True,
                    hint=f"Traditional IRA. Max: ${ira_limit:,}" + (" (includes catch-up)" if is_50_plus else "")
                ),
            }

        self._field_rules['adjustments'] = get_adjustment_fields

        # Rule 56-60: Validate deduction amounts
        def validate_salt_deduction(ctx: TaxContext) -> ValidationResult:
            total_salt = ctx.state_local_taxes + ctx.real_estate_taxes
            if total_salt > self.LIMITS['salt_cap']:
                return ValidationResult(
                    True,
                    f"SALT deduction is capped at ${self.LIMITS['salt_cap']:,}. You entered ${total_salt:,.0f}.",
                    ValidationSeverity.INFO,
                    "state_local_taxes"
                )
            return ValidationResult(True)

        self._rules['salt_deduction'] = [validate_salt_deduction]

    def _register_credit_rules(self) -> None:
        """Register credit-related validation rules."""

        # Rule 61-70: Child Tax Credit rules
        def get_ctc_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Child Tax Credit field visibility."""
            has_children = ctx.num_qualifying_children > 0

            # Check income phase-out
            threshold = (self.LIMITS['ctc_phaseout_mfj']
                        if ctx.filing_status == 'married_joint'
                        else self.LIMITS['ctc_phaseout_single'])
            is_phased_out = ctx.agi > threshold + 40000  # Rough phase-out

            return {
                'ctc_info': FieldState(
                    'ctc_info',
                    FieldRequirement.HIDDEN,
                    visible=has_children and not is_phased_out,
                    hint=f"You may qualify for ${self.LIMITS['ctc_amount'] * ctx.num_qualifying_children:,} in Child Tax Credit"
                ),
            }

        self._field_rules['ctc'] = get_ctc_fields

        # Rule 71-80: EITC rules
        def get_eitc_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """EITC field visibility based on income and filing status."""
            # Check EITC eligibility
            is_mfj = ctx.filing_status == 'married_joint'

            if ctx.num_qualifying_children >= 3:
                limit = self.LIMITS['eitc_income_limit_mfj_3plus' if is_mfj else 'eitc_income_limit_single_3plus']
            elif ctx.num_qualifying_children == 2:
                limit = self.LIMITS['eitc_income_limit_mfj_2_children' if is_mfj else 'eitc_income_limit_single_2_children']
            elif ctx.num_qualifying_children == 1:
                limit = self.LIMITS['eitc_income_limit_mfj_1_child' if is_mfj else 'eitc_income_limit_single_1_child']
            else:
                limit = self.LIMITS['eitc_income_limit_mfj_no_child' if is_mfj else 'eitc_income_limit_single_no_child']

            may_qualify = ctx.earned_income > 0 and ctx.agi <= limit

            # Age requirement for childless EITC
            childless_age_eligible = 25 <= ctx.age <= 64

            return {
                'eitc_info': FieldState(
                    'eitc_info',
                    FieldRequirement.HIDDEN,
                    visible=may_qualify and (ctx.num_qualifying_children > 0 or childless_age_eligible),
                    hint="You may qualify for Earned Income Tax Credit"
                ),
            }

        self._field_rules['eitc'] = get_eitc_fields

        # Rule 81-85: Dependent Care Credit rules
        def get_dependent_care_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Dependent care credit fields."""
            has_young_children = any(d.get('age', 99) < 13 for d in ctx.dependents)
            has_disabled_dependents = any(d.get('is_disabled', False) for d in ctx.dependents)

            show_care_credit = has_young_children or has_disabled_dependents

            max_expenses = (self.LIMITS['dependent_care_max_2plus']
                          if ctx.num_dependents >= 2
                          else self.LIMITS['dependent_care_max_1'])

            return {
                'child_care_expenses': FieldState(
                    'child_care_expenses',
                    FieldRequirement.OPTIONAL if show_care_credit else FieldRequirement.HIDDEN,
                    visible=show_care_credit,
                    hint=f"Maximum qualifying expenses: ${max_expenses:,}"
                ),
                'child_care_provider_name': FieldState(
                    'child_care_provider_name',
                    FieldRequirement.CONDITIONAL_MANDATORY if ctx.child_care_expenses > 0 else FieldRequirement.HIDDEN,
                    visible=ctx.child_care_expenses > 0,
                    hint="Provider's name or facility name"
                ),
                'child_care_provider_ein': FieldState(
                    'child_care_provider_ein',
                    FieldRequirement.CONDITIONAL_MANDATORY if ctx.child_care_expenses > 0 else FieldRequirement.HIDDEN,
                    visible=ctx.child_care_expenses > 0,
                    hint="Provider's Tax ID or SSN"
                ),
            }

        self._field_rules['dependent_care'] = get_dependent_care_fields

        # Rule 86-90: Education Credit rules
        def get_education_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Education credit fields."""
            has_student = any(d.get('is_student', False) for d in ctx.dependents)
            taxpayer_is_student = ctx.age < 30  # Simplified assumption

            show_education = has_student or taxpayer_is_student or ctx.education_expenses > 0

            return {
                'education_expenses': FieldState(
                    'education_expenses',
                    FieldRequirement.OPTIONAL if show_education else FieldRequirement.HIDDEN,
                    visible=show_education,
                    hint=f"AOTC: up to ${self.LIMITS['aotc_max']:,}, LLC: up to ${self.LIMITS['llc_max']:,}"
                ),
                'student_name': FieldState(
                    'student_name',
                    FieldRequirement.CONDITIONAL_MANDATORY if ctx.education_expenses > 0 else FieldRequirement.HIDDEN,
                    visible=ctx.education_expenses > 0
                ),
                'school_name': FieldState(
                    'school_name',
                    FieldRequirement.CONDITIONAL_MANDATORY if ctx.education_expenses > 0 else FieldRequirement.HIDDEN,
                    visible=ctx.education_expenses > 0
                ),
            }

        self._field_rules['education'] = get_education_fields

    def _register_state_rules(self) -> None:
        """Register state tax rules."""

        NO_INCOME_TAX_STATES = {'AK', 'FL', 'NV', 'SD', 'TX', 'WA', 'WY', 'TN', 'NH'}

        # Rule 91-95: State tax fields
        def get_state_tax_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """State tax field visibility."""
            has_state_tax = ctx.state_of_residence not in NO_INCOME_TAX_STATES

            return {
                'state_withholding': FieldState(
                    'state_withholding',
                    FieldRequirement.OPTIONAL if has_state_tax else FieldRequirement.HIDDEN,
                    visible=has_state_tax,
                    hint=f"State income tax withheld from wages"
                ),
                'state_estimated_payments': FieldState(
                    'state_estimated_payments',
                    FieldRequirement.OPTIONAL if has_state_tax else FieldRequirement.HIDDEN,
                    visible=has_state_tax and ctx.business_income > 0
                ),
            }

        self._field_rules['state_tax'] = get_state_tax_fields

    def _register_cross_field_rules(self) -> None:
        """Register cross-field validation rules."""

        # Rule 96: Age-based field visibility
        def get_age_based_fields(ctx: TaxContext) -> Dict[str, FieldState]:
            """Fields that depend on age."""
            is_65_plus = ctx.age >= 65
            spouse_65_plus = ctx.spouse_age >= 65 if ctx.filing_status in ('married_joint', 'married_separate') else False

            return {
                'is_65_or_older': FieldState(
                    'is_65_or_older',
                    FieldRequirement.HIDDEN,  # Auto-calculated from DOB
                    visible=False,
                    default_value=is_65_plus
                ),
                'is_blind': FieldState(
                    'is_blind',
                    FieldRequirement.OPTIONAL,
                    visible=True,  # Always show - not age dependent
                    hint="Additional standard deduction if legally blind"
                ),
                'spouse_is_65_or_older': FieldState(
                    'spouse_is_65_or_older',
                    FieldRequirement.HIDDEN,  # Auto-calculated
                    visible=False,
                    default_value=spouse_65_plus
                ),
                'spouse_is_blind': FieldState(
                    'spouse_is_blind',
                    FieldRequirement.OPTIONAL if ctx.filing_status in ('married_joint', 'married_separate') else FieldRequirement.HIDDEN,
                    visible=ctx.filing_status in ('married_joint', 'married_separate')
                ),
            }

        self._field_rules['age_based'] = get_age_based_fields

        # Rule 97-100: Income threshold warnings
        def validate_income_thresholds(ctx: TaxContext) -> List[ValidationResult]:
            results = []

            # AMT warning
            amt_threshold = (self.LIMITS['amt_exemption_mfj']
                           if ctx.filing_status == 'married_joint'
                           else self.LIMITS['amt_exemption_single'])
            if ctx.agi > amt_threshold * 2:
                results.append(ValidationResult(
                    True,
                    "Your income level may trigger Alternative Minimum Tax (AMT)",
                    ValidationSeverity.INFO,
                    "income_warning"
                ))

            # Net Investment Income Tax warning
            niit_threshold = (self.LIMITS['nii_threshold_mfj']
                            if ctx.filing_status == 'married_joint'
                            else self.LIMITS['nii_threshold_single'])
            investment_income = ctx.interest_income + ctx.dividend_income + ctx.capital_gains_long
            if ctx.agi > niit_threshold and investment_income > 0:
                results.append(ValidationResult(
                    True,
                    "3.8% Net Investment Income Tax may apply to your investment income",
                    ValidationSeverity.INFO,
                    "niit_warning"
                ))

            # Additional Medicare Tax warning
            medicare_threshold = (self.LIMITS['medicare_additional_threshold_mfj']
                                if ctx.filing_status == 'married_joint'
                                else self.LIMITS['medicare_additional_threshold_single'])
            if ctx.earned_income > medicare_threshold:
                results.append(ValidationResult(
                    True,
                    "0.9% Additional Medicare Tax applies to wages above threshold",
                    ValidationSeverity.INFO,
                    "medicare_warning"
                ))

            return results

        self._rules['income_thresholds'] = [lambda ctx: validate_income_thresholds(ctx)]

    def _get_standard_deduction(self, ctx: TaxContext) -> float:
        """Calculate standard deduction based on filing status and age."""
        status_map = {
            'single': self.LIMITS['standard_deduction_single'],
            'married_joint': self.LIMITS['standard_deduction_mfj'],
            'married_separate': self.LIMITS['standard_deduction_mfs'],
            'head_of_household': self.LIMITS['standard_deduction_hoh'],
            'qualifying_widow': self.LIMITS['standard_deduction_qw'],
        }
        base = status_map.get(ctx.filing_status, self.LIMITS['standard_deduction_single'])

        # Additional for 65+ and blind
        additional = 0
        is_married = ctx.filing_status in ('married_joint', 'married_separate', 'qualifying_widow')

        if ctx.age >= 65:
            additional += (self.LIMITS['additional_deduction_65_married']
                         if is_married else self.LIMITS['additional_deduction_65_single'])
        if ctx.is_blind:
            additional += (self.LIMITS['additional_deduction_blind_married']
                         if is_married else self.LIMITS['additional_deduction_blind_single'])

        # Spouse additional (MFJ only)
        if ctx.filing_status == 'married_joint':
            if ctx.spouse_age >= 65:
                additional += self.LIMITS['additional_deduction_65_married']
            if ctx.spouse_is_blind:
                additional += self.LIMITS['additional_deduction_blind_married']

        return base + additional

    def get_all_field_states(self, ctx: TaxContext) -> Dict[str, FieldState]:
        """Get current state of all fields based on context."""
        ctx.calculate_derived_fields()

        all_states = {}
        for rule_name, rule_func in self._field_rules.items():
            states = rule_func(ctx)
            all_states.update(states)

        return all_states

    def validate_all(self, ctx: TaxContext) -> List[ValidationResult]:
        """Run all validation rules and return results."""
        ctx.calculate_derived_fields()

        all_results = []
        for rule_name, rules in self._rules.items():
            for rule in rules:
                result = rule(ctx)
                if isinstance(result, list):
                    all_results.extend(result)
                else:
                    all_results.append(result)

        return [r for r in all_results if not r.valid or r.message]

    def validate_field(self, field_name: str, ctx: TaxContext) -> List[ValidationResult]:
        """Validate a specific field."""
        ctx.calculate_derived_fields()

        if field_name not in self._rules:
            return []

        results = []
        for rule in self._rules[field_name]:
            result = rule(ctx)
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)

        return [r for r in results if not r.valid or r.message]

    def get_field_requirement(self, field_name: str, ctx: TaxContext) -> FieldRequirement:
        """Get the requirement level for a specific field."""
        all_states = self.get_all_field_states(ctx)
        if field_name in all_states:
            return all_states[field_name].requirement
        return FieldRequirement.OPTIONAL

    def is_field_visible(self, field_name: str, ctx: TaxContext) -> bool:
        """Check if a field should be visible."""
        all_states = self.get_all_field_states(ctx)
        if field_name in all_states:
            return all_states[field_name].visible
        return True

    def get_smart_defaults(self, ctx: TaxContext) -> Dict[str, Any]:
        """Get smart default values based on context."""
        defaults = {}

        # Auto-calculate 65+ from DOB
        if ctx.age >= 65:
            defaults['is_65_or_older'] = True

        if ctx.spouse_age >= 65:
            defaults['spouse_is_65_or_older'] = True

        # Suggest standard deduction if likely better
        std_ded = self._get_standard_deduction(ctx)
        itemized_total = (
            max(0, ctx.medical_expenses - ctx.agi * 0.075) +
            min(ctx.state_local_taxes + ctx.real_estate_taxes, self.LIMITS['salt_cap']) +
            ctx.mortgage_interest +
            ctx.charitable_cash +
            ctx.charitable_noncash
        )

        defaults['use_standard_deduction'] = std_ded >= itemized_total
        defaults['recommended_deduction'] = 'standard' if std_ded >= itemized_total else 'itemized'
        defaults['standard_deduction_amount'] = std_ded
        defaults['itemized_deduction_amount'] = itemized_total

        return defaults


# Singleton instance
_engine = None

def get_rules_engine() -> TaxRulesEngine:
    """Get the singleton rules engine instance."""
    global _engine
    if _engine is None:
        _engine = TaxRulesEngine()
    return _engine
