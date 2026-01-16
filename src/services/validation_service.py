"""
Validation Service - Comprehensive tax return validation engine.

Provides multi-level validation:
1. Schema validation - Required fields, data types
2. Range validation - Values within valid bounds
3. Consistency validation - Cross-field logical checks
4. Tax rule validation - IRS-specific rules and limits

This is a DOMAIN SERVICE - it contains business logic for validation
that spans multiple aggregates.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Set

from .logging_config import get_logger

# Import models
from models.tax_return import TaxReturn
from models.taxpayer import FilingStatus

logger = get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""
    ERROR = "error"       # Must be fixed before filing
    WARNING = "warning"   # Should be reviewed
    INFO = "info"         # Informational note


class ValidationCategory(str, Enum):
    """Category of validation rule."""
    REQUIRED = "required"           # Required field missing
    FORMAT = "format"               # Invalid format
    RANGE = "range"                 # Value out of range
    CONSISTENCY = "consistency"     # Cross-field inconsistency
    TAX_RULE = "tax_rule"          # IRS rule violation
    LIMIT = "limit"                # Exceeds IRS limit
    DEADLINE = "deadline"          # Timing-related


@dataclass
class ValidationIssue:
    """
    Represents a validation issue found in a tax return.
    """
    code: str                              # Unique issue code (e.g., "W2_001")
    field_path: str                        # Dot-notation path to field
    message: str                           # Human-readable message
    severity: ValidationSeverity           # Error, warning, or info
    category: ValidationCategory           # Type of validation
    value: Any = None                      # Current value (if applicable)
    suggestion: Optional[str] = None       # Suggested fix
    irs_reference: Optional[str] = None    # IRS form/publication reference

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "field_path": self.field_path,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "value": self.value,
            "suggestion": self.suggestion,
            "irs_reference": self.irs_reference,
        }


@dataclass
class ValidationResult:
    """
    Result of validating a tax return.
    """
    is_valid: bool                         # True if no errors
    issues: List[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.utcnow)
    tax_year: int = 2025

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get only error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get only warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue and update validity."""
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.is_valid = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
            "validated_at": self.validated_at.isoformat(),
            "tax_year": self.tax_year,
        }


class ValidationRule(ABC):
    """
    Abstract base class for validation rules.
    """

    @property
    @abstractmethod
    def code(self) -> str:
        """Unique rule identifier."""
        pass

    @property
    @abstractmethod
    def category(self) -> ValidationCategory:
        """Rule category."""
        pass

    @abstractmethod
    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Validate against this rule.

        Args:
            tax_return: TaxReturn model instance
            data: Raw tax return data dictionary

        Returns:
            List of issues found (empty if valid)
        """
        pass


# ============================================================
# Required Field Rules
# ============================================================

class RequiredFieldRule(ValidationRule):
    """Validates required fields are present."""

    @property
    def code(self) -> str:
        return "REQ_001"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.REQUIRED

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []

        # Taxpayer required fields
        if not tax_return.taxpayer.first_name:
            issues.append(ValidationIssue(
                code="REQ_001",
                field_path="taxpayer.first_name",
                message="First name is required",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.REQUIRED,
                suggestion="Enter taxpayer's legal first name"
            ))

        if not tax_return.taxpayer.last_name:
            issues.append(ValidationIssue(
                code="REQ_002",
                field_path="taxpayer.last_name",
                message="Last name is required",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.REQUIRED,
                suggestion="Enter taxpayer's legal last name"
            ))

        if not tax_return.taxpayer.ssn:
            issues.append(ValidationIssue(
                code="REQ_003",
                field_path="taxpayer.ssn",
                message="Social Security Number is required",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.REQUIRED,
                suggestion="Enter taxpayer's SSN in XXX-XX-XXXX format",
                irs_reference="Form 1040, Line 1"
            ))

        if not tax_return.taxpayer.filing_status:
            issues.append(ValidationIssue(
                code="REQ_004",
                field_path="taxpayer.filing_status",
                message="Filing status is required",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.REQUIRED,
                suggestion="Select a filing status",
                irs_reference="Form 1040, Filing Status"
            ))

        return issues


class SSNFormatRule(ValidationRule):
    """Validates SSN format."""

    @property
    def code(self) -> str:
        return "FMT_001"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.FORMAT

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        import re

        ssn_pattern = r'^\d{3}-\d{2}-\d{4}$'

        if tax_return.taxpayer.ssn:
            if not re.match(ssn_pattern, tax_return.taxpayer.ssn):
                issues.append(ValidationIssue(
                    code="FMT_001",
                    field_path="taxpayer.ssn",
                    message="SSN must be in XXX-XX-XXXX format",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.FORMAT,
                    value=tax_return.taxpayer.ssn[:3] + "-XX-XXXX",  # Masked
                    suggestion="Enter SSN as XXX-XX-XXXX"
                ))

        return issues


# ============================================================
# Range Validation Rules
# ============================================================

class IncomeRangeRule(ValidationRule):
    """Validates income values are within reasonable ranges."""

    @property
    def code(self) -> str:
        return "RNG_001"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.RANGE

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        income = tax_return.income

        # Check fields that exist on the Income model
        negative_checks = [
            ("dividend_income", getattr(income, 'dividend_income', 0), "Dividend income"),
            ("interest_income", getattr(income, 'interest_income', 0), "Interest income"),
            ("self_employment_income", getattr(income, 'self_employment_income', 0), "Self-employment income"),
        ]

        for field_name, value, display_name in negative_checks:
            if value < 0:
                issues.append(ValidationIssue(
                    code=f"RNG_{field_name.upper()}",
                    field_path=f"income.{field_name}",
                    message=f"{display_name} cannot be negative",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    value=value,
                    suggestion=f"Enter {display_name.lower()} as a positive amount"
                ))

        # Calculate total wages from W2 forms
        total_wages = sum(w2.wages for w2 in income.w2_forms) if income.w2_forms else 0

        # Unusually high income warning
        if total_wages > 10_000_000:
            issues.append(ValidationIssue(
                code="RNG_HIGH_WAGES",
                field_path="income.w2_forms",
                message="Total W-2 wages exceed $10 million - please verify",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.RANGE,
                value=total_wages,
                suggestion="Verify this amount is correct"
            ))

        return issues


class W2ValidationRule(ValidationRule):
    """Validates W-2 form values."""

    @property
    def code(self) -> str:
        return "W2_001"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.RANGE

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []

        for i, w2 in enumerate(tax_return.income.w2_forms):
            prefix = f"income.w2_forms[{i}]"

            # Wages must be non-negative
            if w2.wages < 0:
                issues.append(ValidationIssue(
                    code="W2_001",
                    field_path=f"{prefix}.wages",
                    message=f"W-2 wages cannot be negative ({w2.employer_name})",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    value=w2.wages
                ))

            # Federal withholding must be non-negative
            if w2.federal_tax_withheld < 0:
                issues.append(ValidationIssue(
                    code="W2_002",
                    field_path=f"{prefix}.federal_tax_withheld",
                    message=f"Federal withholding cannot be negative ({w2.employer_name})",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.RANGE,
                    value=w2.federal_tax_withheld
                ))

            # Social Security wages capped at wage base
            ss_wage_base_2025 = 176_100  # 2025 limit
            if w2.social_security_wages and w2.social_security_wages > ss_wage_base_2025:
                issues.append(ValidationIssue(
                    code="W2_003",
                    field_path=f"{prefix}.social_security_wages",
                    message=f"Social Security wages exceed {ss_wage_base_2025:,} limit ({w2.employer_name})",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.LIMIT,
                    value=w2.social_security_wages,
                    irs_reference="Social Security wage base limit"
                ))

            # Withholding should not exceed wages
            if w2.federal_tax_withheld > w2.wages:
                issues.append(ValidationIssue(
                    code="W2_004",
                    field_path=f"{prefix}.federal_tax_withheld",
                    message=f"Withholding exceeds wages ({w2.employer_name})",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    value=w2.federal_tax_withheld,
                    suggestion="Verify withholding amount"
                ))

            # Missing employer EIN
            if not w2.employer_ein:
                issues.append(ValidationIssue(
                    code="W2_005",
                    field_path=f"{prefix}.employer_ein",
                    message=f"Employer EIN missing ({w2.employer_name})",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.REQUIRED,
                    suggestion="Enter employer's EIN from W-2 box b"
                ))

        return issues


# ============================================================
# Consistency Validation Rules
# ============================================================

class FilingStatusConsistencyRule(ValidationRule):
    """Validates filing status is consistent with taxpayer situation."""

    @property
    def code(self) -> str:
        return "CON_001"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.CONSISTENCY

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        taxpayer = tax_return.taxpayer
        filing_status = taxpayer.filing_status

        # Married filing jointly but no spouse
        if filing_status == FilingStatus.MARRIED_JOINT:
            if not taxpayer.spouse_first_name or not taxpayer.spouse_last_name:
                issues.append(ValidationIssue(
                    code="CON_001",
                    field_path="taxpayer.filing_status",
                    message="Married Filing Jointly requires spouse information",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONSISTENCY,
                    suggestion="Enter spouse name or change filing status"
                ))
            if not taxpayer.spouse_ssn:
                issues.append(ValidationIssue(
                    code="CON_002",
                    field_path="taxpayer.spouse_ssn",
                    message="Spouse SSN required for Married Filing Jointly",
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.CONSISTENCY,
                    suggestion="Enter spouse's SSN"
                ))

        # Head of Household requires qualifying person
        if filing_status == FilingStatus.HEAD_OF_HOUSEHOLD:
            if len(taxpayer.dependents) == 0:
                issues.append(ValidationIssue(
                    code="CON_003",
                    field_path="taxpayer.filing_status",
                    message="Head of Household requires a qualifying person",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    suggestion="Add qualifying dependent or verify filing status",
                    irs_reference="Publication 501"
                ))

        return issues


class DividendConsistencyRule(ValidationRule):
    """Validates dividend amounts are consistent."""

    @property
    def code(self) -> str:
        return "CON_010"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.CONSISTENCY

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        income = tax_return.income

        # Qualified dividends cannot exceed total dividends
        if income.qualified_dividends > income.dividend_income:
            issues.append(ValidationIssue(
                code="CON_010",
                field_path="income.qualified_dividends",
                message="Qualified dividends cannot exceed total dividends",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.CONSISTENCY,
                value=income.qualified_dividends,
                suggestion=f"Qualified dividends should be at most ${income.dividend_income:,.2f}",
                irs_reference="Form 1040, Line 3a"
            ))

        return issues


class DeductionConsistencyRule(ValidationRule):
    """Validates deduction amounts are consistent."""

    @property
    def code(self) -> str:
        return "CON_020"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.CONSISTENCY

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        itemized = tax_return.deductions.itemized
        income = tax_return.income

        # Calculate total income from W2 and self-employment
        total_wages = sum(w2.wages for w2 in income.w2_forms) if income.w2_forms else 0
        total_income = total_wages + getattr(income, 'self_employment_income', 0)

        # Mortgage interest check
        mortgage_interest = getattr(itemized, 'mortgage_interest', 0)
        if mortgage_interest > 0 and total_income > 0:
            # Warning if very high relative to income
            if mortgage_interest > total_income * 0.5:
                issues.append(ValidationIssue(
                    code="CON_020",
                    field_path="deductions.itemized.mortgage_interest",
                    message="Mortgage interest exceeds 50% of income - verify",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    value=mortgage_interest
                ))

        # State/local taxes check
        total_salt = (
            getattr(itemized, 'state_local_income_tax', 0) +
            getattr(itemized, 'real_estate_tax', 0)
        )
        if total_salt > 0 and total_income > 0:
            # Check if reasonable relative to income
            if total_salt > total_income * 0.20:
                issues.append(ValidationIssue(
                    code="CON_021",
                    field_path="deductions.itemized",
                    message="State/local taxes exceed 20% of income - verify",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.CONSISTENCY,
                    value=total_salt
                ))

        return issues


# ============================================================
# Tax Rule / Limit Validation
# ============================================================

class SALTLimitRule(ValidationRule):
    """Validates SALT deduction limit."""

    SALT_LIMIT = 10_000  # $10,000 limit (or $5,000 MFS)

    @property
    def code(self) -> str:
        return "LIM_001"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.LIMIT

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []

        # Determine limit based on filing status
        limit = self.SALT_LIMIT
        if tax_return.taxpayer.filing_status == FilingStatus.MARRIED_SEPARATE:
            limit = 5_000

        # SALT includes state/local income tax, sales tax, real estate tax, personal property tax
        itemized = tax_return.deductions.itemized
        total_salt = (
            getattr(itemized, 'state_local_income_tax', 0) +
            getattr(itemized, 'state_local_sales_tax', 0) +
            getattr(itemized, 'real_estate_tax', 0) +
            getattr(itemized, 'personal_property_tax', 0)
        )

        if total_salt > limit:
            issues.append(ValidationIssue(
                code="LIM_001",
                field_path="deductions.itemized",
                message=f"SALT deduction exceeds ${limit:,} limit - will be capped",
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.LIMIT,
                value=total_salt,
                suggestion=f"Only ${limit:,} will be deductible",
                irs_reference="IRC Section 164(b)(6)"
            ))

        return issues


class RetirementContributionLimitRule(ValidationRule):
    """Validates retirement contribution limits."""

    # 2025 limits
    LIMIT_401K = 23_500
    LIMIT_401K_CATCHUP = 7_500  # Age 50+
    LIMIT_IRA = 7_000
    LIMIT_IRA_CATCHUP = 1_000  # Age 50+

    @property
    def code(self) -> str:
        return "LIM_010"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.LIMIT

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        deductions = tax_return.deductions

        # Check IRA contribution limit
        max_ira = self.LIMIT_IRA + (self.LIMIT_IRA_CATCHUP if self._is_50_plus(tax_return) else 0)
        ira_contributions = getattr(deductions, 'ira_contributions', 0)
        if ira_contributions > max_ira:
            issues.append(ValidationIssue(
                code="LIM_011",
                field_path="deductions.ira_contributions",
                message=f"IRA contribution exceeds ${max_ira:,} limit",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.LIMIT,
                value=ira_contributions,
                suggestion=f"Maximum allowed is ${max_ira:,}",
                irs_reference="IRC Section 219"
            ))

        # Check HSA contribution limit (2025 limits: $4,300 self, $8,550 family)
        hsa_contributions = getattr(deductions, 'hsa_contributions', 0)
        hsa_limit = 8_550  # Family limit
        if hsa_contributions > hsa_limit:
            issues.append(ValidationIssue(
                code="LIM_012",
                field_path="deductions.hsa_contributions",
                message=f"HSA contribution exceeds ${hsa_limit:,} limit",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.LIMIT,
                value=hsa_contributions,
                suggestion=f"Maximum allowed is ${hsa_limit:,}",
                irs_reference="IRC Section 223"
            ))

        return issues

    def _is_50_plus(self, tax_return: TaxReturn) -> bool:
        """Check if taxpayer is 50 or older."""
        # Check if date_of_birth exists and taxpayer is 50+
        if hasattr(tax_return.taxpayer, 'date_of_birth') and tax_return.taxpayer.date_of_birth:
            today = date.today()
            dob = tax_return.taxpayer.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age >= 50
        return False


class CharitableContributionLimitRule(ValidationRule):
    """Validates charitable contribution limits."""

    @property
    def code(self) -> str:
        return "LIM_020"

    @property
    def category(self) -> ValidationCategory:
        return ValidationCategory.LIMIT

    def validate(self, tax_return: TaxReturn, data: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []

        # Calculate AGI approximation for percentage limits
        income = tax_return.income
        total_wages = sum(w2.wages for w2 in income.w2_forms) if income.w2_forms else 0
        agi = total_wages + getattr(income, 'dividend_income', 0) + getattr(income, 'interest_income', 0)
        agi += getattr(income, 'self_employment_income', 0)

        # Get charitable contributions from itemized deductions
        itemized = tax_return.deductions.itemized
        charitable_cash = getattr(itemized, 'charitable_cash', 0)
        charitable_non_cash = getattr(itemized, 'charitable_non_cash', 0)

        # Cash contributions limited to 60% of AGI
        if agi > 0:
            cash_limit = agi * 0.60
            if charitable_cash > cash_limit:
                issues.append(ValidationIssue(
                    code="LIM_020",
                    field_path="deductions.itemized.charitable_cash",
                    message=f"Cash charitable contributions exceed 60% AGI limit",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.LIMIT,
                    value=charitable_cash,
                    suggestion=f"Maximum deductible is ${cash_limit:,.2f} (60% of AGI)",
                    irs_reference="IRC Section 170(b)"
                ))

            # Non-cash limited to 30% of AGI
            non_cash_limit = agi * 0.30
            if charitable_non_cash > non_cash_limit:
                issues.append(ValidationIssue(
                    code="LIM_021",
                    field_path="deductions.itemized.charitable_non_cash",
                    message=f"Non-cash charitable contributions exceed 30% AGI limit",
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.LIMIT,
                    value=charitable_non_cash,
                    suggestion=f"Maximum deductible is ${non_cash_limit:,.2f} (30% of AGI)",
                    irs_reference="IRC Section 170(b)"
                ))

        return issues


# ============================================================
# Validation Service
# ============================================================

class ValidationService:
    """
    Comprehensive validation service for tax returns.

    Runs all validation rules and collects issues.
    Supports custom rule sets and selective validation.
    """

    def __init__(self, rules: Optional[List[ValidationRule]] = None):
        """
        Initialize ValidationService.

        Args:
            rules: Optional custom rule list. Uses defaults if not provided.
        """
        self._rules = rules or self._default_rules()
        self._logger = get_logger(__name__)

    def _default_rules(self) -> List[ValidationRule]:
        """Create default validation rules."""
        return [
            # Required fields
            RequiredFieldRule(),
            SSNFormatRule(),

            # Range validation
            IncomeRangeRule(),
            W2ValidationRule(),

            # Consistency
            FilingStatusConsistencyRule(),
            DividendConsistencyRule(),
            DeductionConsistencyRule(),

            # Tax limits
            SALTLimitRule(),
            RetirementContributionLimitRule(),
            CharitableContributionLimitRule(),
        ]

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a custom validation rule."""
        self._rules.append(rule)

    def remove_rule(self, code: str) -> bool:
        """Remove a rule by code."""
        for i, rule in enumerate(self._rules):
            if rule.code == code:
                self._rules.pop(i)
                return True
        return False

    def validate(
        self,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any],
        categories: Optional[Set[ValidationCategory]] = None,
        stop_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate a tax return against all rules.

        Args:
            tax_return: TaxReturn model instance
            tax_return_data: Raw tax return data dictionary
            categories: Optional set of categories to validate (all if None)
            stop_on_error: Stop validation on first error

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult(
            is_valid=True,
            tax_year=tax_return_data.get("tax_year", 2025)
        )

        for rule in self._rules:
            # Filter by category if specified
            if categories and rule.category not in categories:
                continue

            try:
                issues = rule.validate(tax_return, tax_return_data)
                for issue in issues:
                    result.add_issue(issue)

                    if stop_on_error and issue.severity == ValidationSeverity.ERROR:
                        self._logger.info(
                            "Validation stopped on error",
                            extra={'extra_data': {'code': issue.code}}
                        )
                        return result

            except Exception as e:
                self._logger.error(
                    f"Validation rule {rule.code} failed: {e}",
                    extra={'extra_data': {'rule': rule.code}}
                )

        self._logger.info(
            "Validation complete",
            extra={'extra_data': {
                'is_valid': result.is_valid,
                'error_count': result.error_count,
                'warning_count': result.warning_count,
            }}
        )

        return result

    def validate_field(
        self,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any],
        field_path: str
    ) -> List[ValidationIssue]:
        """
        Validate a specific field.

        Args:
            tax_return: TaxReturn model instance
            tax_return_data: Raw tax return data
            field_path: Dot-notation path to field

        Returns:
            List of issues for that field
        """
        result = self.validate(tax_return, tax_return_data)
        return [issue for issue in result.issues if issue.field_path == field_path]

    def get_required_fields(self) -> List[str]:
        """Get list of required field paths."""
        return [
            "taxpayer.first_name",
            "taxpayer.last_name",
            "taxpayer.ssn",
            "taxpayer.filing_status",
        ]

    def quick_validate(
        self,
        tax_return: TaxReturn,
        tax_return_data: Dict[str, Any]
    ) -> bool:
        """
        Quick validation - checks only for errors.

        Args:
            tax_return: TaxReturn model instance
            tax_return_data: Raw tax return data

        Returns:
            True if no errors found
        """
        result = self.validate(
            tax_return,
            tax_return_data,
            categories={ValidationCategory.REQUIRED, ValidationCategory.FORMAT},
            stop_on_error=True
        )
        return result.is_valid


# Factory function
def create_validation_service(
    include_limits: bool = True,
    include_consistency: bool = True
) -> ValidationService:
    """
    Create a validation service with optional rule sets.

    Args:
        include_limits: Include IRS limit rules
        include_consistency: Include consistency rules

    Returns:
        Configured ValidationService
    """
    rules = [
        RequiredFieldRule(),
        SSNFormatRule(),
        IncomeRangeRule(),
        W2ValidationRule(),
    ]

    if include_consistency:
        rules.extend([
            FilingStatusConsistencyRule(),
            DividendConsistencyRule(),
            DeductionConsistencyRule(),
        ])

    if include_limits:
        rules.extend([
            SALTLimitRule(),
            RetirementContributionLimitRule(),
            CharitableContributionLimitRule(),
        ])

    return ValidationService(rules)
