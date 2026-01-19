"""
Tax Return Schema Definitions and Validation.

This module defines:
- Structural templates for IRS tax return adherence
- Data type specifications with validation
- Business rules enforcement
- Schema versioning for tax year updates

Tax Year: 2025 (Filing in 2026)
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable
import re


# =============================================================================
# VALIDATION RESULT TYPES
# =============================================================================

class ValidationSeverity(str, Enum):
    """Severity levels for validation results."""
    ERROR = "error"          # Blocks filing
    WARNING = "warning"      # Requires review
    INFO = "info"            # Informational
    CRITICAL = "critical"    # Data integrity issue


class ValidationCategory(str, Enum):
    """Categories of validation checks."""
    STRUCTURAL = "structural"      # Data type, format, required fields
    BUSINESS_RULE = "business"     # IRS rules, limits, eligibility
    CONSISTENCY = "consistency"    # Cross-field consistency
    COMPLIANCE = "compliance"      # IRS e-file requirements
    SECURITY = "security"          # PII, encryption requirements


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    is_valid: bool
    field_name: str
    severity: ValidationSeverity
    category: ValidationCategory
    code: str                      # Unique error code (e.g., "E001", "W023")
    message: str
    irs_reference: Optional[str] = None
    suggested_action: Optional[str] = None
    current_value: Optional[Any] = None
    expected_value: Optional[Any] = None


@dataclass
class BusinessRuleResult:
    """Result of business rule evaluation."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: ValidationSeverity
    message: str
    affected_fields: List[str] = field(default_factory=list)
    irs_reference: Optional[str] = None
    tax_impact: Optional[Decimal] = None


@dataclass
class SchemaValidationReport:
    """Complete validation report for a tax return."""
    return_id: str
    tax_year: int
    validation_timestamp: datetime
    is_filing_ready: bool
    total_checks: int
    errors: List[ValidationResult]
    warnings: List[ValidationResult]
    info: List[ValidationResult]
    business_rule_results: List[BusinessRuleResult]
    compliance_score: float  # 0-100


# =============================================================================
# FIELD SPECIFICATIONS
# =============================================================================

@dataclass
class FieldSpec:
    """
    Field specification for structural validation.

    Defines data type, constraints, and validation rules for each field.
    """
    name: str
    data_type: str                     # string, decimal, integer, date, boolean, enum
    required: bool = False
    nullable: bool = True

    # Numeric constraints
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    precision: int = 2                  # Decimal places
    allow_negative: bool = False

    # String constraints
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None       # Regex pattern
    valid_values: Optional[List[str]] = None

    # Date constraints
    min_date: Optional[date] = None
    max_date: Optional[date] = None

    # IRS mapping
    irs_form: Optional[str] = None      # Form 1040, Schedule A, etc.
    irs_line: Optional[str] = None      # Line number
    irs_box: Optional[str] = None       # Box number (for W-2, 1099)

    # Computation
    computed: bool = False
    computation_formula: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)

    # Flags
    is_pii: bool = False                # Requires encryption
    is_monetary: bool = False           # Currency formatting
    filing_status_specific: bool = False


# =============================================================================
# TAX RETURN SCHEMA
# =============================================================================

class TaxReturnSchema:
    """
    Complete schema definition for IRS Form 1040 and supporting schedules.

    This schema defines:
    1. All fields with data type specifications
    2. Required vs optional fields by filing situation
    3. IRS form/line mappings
    4. Validation constraints
    5. Computation dependencies
    """

    TAX_YEAR = 2025

    # ==========================================================================
    # TAXPAYER INFORMATION FIELDS
    # ==========================================================================

    TAXPAYER_FIELDS: Dict[str, FieldSpec] = {
        "ssn": FieldSpec(
            name="ssn",
            data_type="string",
            required=True,
            nullable=False,
            pattern=r"^\d{3}-?\d{2}-?\d{4}$",
            min_length=9,
            max_length=11,
            is_pii=True,
            irs_form="Form 1040",
            irs_line="Your social security number"
        ),
        "first_name": FieldSpec(
            name="first_name",
            data_type="string",
            required=True,
            nullable=False,
            min_length=1,
            max_length=100,
            irs_form="Form 1040",
            irs_line="Your first name and middle initial"
        ),
        "last_name": FieldSpec(
            name="last_name",
            data_type="string",
            required=True,
            nullable=False,
            min_length=1,
            max_length=100,
            irs_form="Form 1040",
            irs_line="Last name"
        ),
        "date_of_birth": FieldSpec(
            name="date_of_birth",
            data_type="date",
            required=False,
            min_date=date(1900, 1, 1),
            max_date=date.today()
        ),
        "filing_status": FieldSpec(
            name="filing_status",
            data_type="enum",
            required=True,
            nullable=False,
            valid_values=[
                "single",
                "married_joint",
                "married_separate",
                "head_of_household",
                "qualifying_widow"
            ],
            irs_form="Form 1040",
            irs_line="Filing Status"
        ),
        "address": FieldSpec(
            name="address",
            data_type="string",
            required=True,
            max_length=200,
            irs_form="Form 1040",
            irs_line="Home address"
        ),
        "city": FieldSpec(
            name="city",
            data_type="string",
            required=True,
            max_length=100,
            irs_form="Form 1040"
        ),
        "state": FieldSpec(
            name="state",
            data_type="string",
            required=True,
            pattern=r"^[A-Z]{2}$",
            min_length=2,
            max_length=2,
            irs_form="Form 1040"
        ),
        "zip_code": FieldSpec(
            name="zip_code",
            data_type="string",
            required=True,
            pattern=r"^\d{5}(-\d{4})?$",
            irs_form="Form 1040"
        ),
    }

    # ==========================================================================
    # INCOME FIELDS (Form 1040 Lines 1-9)
    # ==========================================================================

    INCOME_FIELDS: Dict[str, FieldSpec] = {
        "line_1_wages": FieldSpec(
            name="line_1_wages",
            data_type="decimal",
            required=True,
            min_value=Decimal("0"),
            max_value=Decimal("99999999.99"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="1",
            irs_box="W-2 Box 1"
        ),
        "line_2a_tax_exempt_interest": FieldSpec(
            name="line_2a_tax_exempt_interest",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="2a"
        ),
        "line_2b_taxable_interest": FieldSpec(
            name="line_2b_taxable_interest",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="2b",
            irs_box="1099-INT Box 1"
        ),
        "line_3a_qualified_dividends": FieldSpec(
            name="line_3a_qualified_dividends",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="3a",
            irs_box="1099-DIV Box 1b"
        ),
        "line_3b_ordinary_dividends": FieldSpec(
            name="line_3b_ordinary_dividends",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="3b",
            irs_box="1099-DIV Box 1a"
        ),
        "line_4b_taxable_ira": FieldSpec(
            name="line_4b_taxable_ira",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="4b"
        ),
        "line_5b_taxable_pensions": FieldSpec(
            name="line_5b_taxable_pensions",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="5b"
        ),
        "line_6b_taxable_social_security": FieldSpec(
            name="line_6b_taxable_social_security",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="6b"
        ),
        "line_7_capital_gain": FieldSpec(
            name="line_7_capital_gain",
            data_type="decimal",
            allow_negative=True,  # Can be loss
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="7",
            depends_on=["schedule_d"]
        ),
        "line_8_other_income": FieldSpec(
            name="line_8_other_income",
            data_type="decimal",
            allow_negative=True,
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="8",
            depends_on=["schedule_1"]
        ),
        "line_9_total_income": FieldSpec(
            name="line_9_total_income",
            data_type="decimal",
            required=True,
            precision=2,
            is_monetary=True,
            computed=True,
            computation_formula="SUM(lines_1_through_8)",
            irs_form="Form 1040",
            irs_line="9"
        ),
    }

    # ==========================================================================
    # ADJUSTMENTS FIELDS (Form 1040 Lines 10-11)
    # ==========================================================================

    ADJUSTMENT_FIELDS: Dict[str, FieldSpec] = {
        "line_10_adjustments": FieldSpec(
            name="line_10_adjustments",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="10",
            depends_on=["schedule_1_part_2"]
        ),
        "line_11_agi": FieldSpec(
            name="line_11_agi",
            data_type="decimal",
            required=True,
            precision=2,
            is_monetary=True,
            computed=True,
            computation_formula="line_9_total_income - line_10_adjustments",
            irs_form="Form 1040",
            irs_line="11"
        ),
    }

    # ==========================================================================
    # DEDUCTION FIELDS (Form 1040 Lines 12-15)
    # ==========================================================================

    DEDUCTION_FIELDS: Dict[str, FieldSpec] = {
        "line_12a_standard_deduction": FieldSpec(
            name="line_12a_standard_deduction",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            filing_status_specific=True,
            irs_form="Form 1040",
            irs_line="12a"
        ),
        "line_12c_total_deduction": FieldSpec(
            name="line_12c_total_deduction",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            computed=True,
            irs_form="Form 1040",
            irs_line="12c"
        ),
        "line_13_qbi_deduction": FieldSpec(
            name="line_13_qbi_deduction",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="Form 1040",
            irs_line="13",
            depends_on=["form_8995"]
        ),
        "line_14_total_deductions": FieldSpec(
            name="line_14_total_deductions",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            computed=True,
            computation_formula="line_12c + line_13",
            irs_form="Form 1040",
            irs_line="14"
        ),
        "line_15_taxable_income": FieldSpec(
            name="line_15_taxable_income",
            data_type="decimal",
            min_value=Decimal("0"),  # Cannot be negative
            precision=2,
            is_monetary=True,
            computed=True,
            computation_formula="MAX(0, line_11_agi - line_14_total_deductions)",
            irs_form="Form 1040",
            irs_line="15"
        ),
    }

    # ==========================================================================
    # TAX AND CREDITS (Form 1040 Lines 16-24)
    # ==========================================================================

    TAX_FIELDS: Dict[str, FieldSpec] = {
        "line_16_tax": FieldSpec(
            name="line_16_tax",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            computed=True,
            irs_form="Form 1040",
            irs_line="16",
            depends_on=["tax_table", "qualified_dividends_worksheet"]
        ),
        "line_18_total_tax": FieldSpec(
            name="line_18_total_tax",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            computed=True,
            irs_form="Form 1040",
            irs_line="18"
        ),
        "line_24_total_tax_liability": FieldSpec(
            name="line_24_total_tax_liability",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            computed=True,
            irs_form="Form 1040",
            irs_line="24"
        ),
    }

    # ==========================================================================
    # W-2 FORM FIELDS
    # ==========================================================================

    W2_FIELDS: Dict[str, FieldSpec] = {
        "employer_ein": FieldSpec(
            name="employer_ein",
            data_type="string",
            pattern=r"^\d{2}-?\d{7}$",
            min_length=9,
            max_length=10,
            irs_form="W-2",
            irs_box="b"
        ),
        "employer_name": FieldSpec(
            name="employer_name",
            data_type="string",
            required=True,
            max_length=200,
            irs_form="W-2",
            irs_box="c"
        ),
        "box_1_wages": FieldSpec(
            name="box_1_wages",
            data_type="decimal",
            required=True,
            min_value=Decimal("0"),
            max_value=Decimal("99999999.99"),
            precision=2,
            is_monetary=True,
            irs_form="W-2",
            irs_box="1"
        ),
        "box_2_federal_tax": FieldSpec(
            name="box_2_federal_tax",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="W-2",
            irs_box="2"
        ),
        "box_3_ss_wages": FieldSpec(
            name="box_3_ss_wages",
            data_type="decimal",
            min_value=Decimal("0"),
            max_value=Decimal("176100"),  # 2025 SS wage base
            precision=2,
            is_monetary=True,
            irs_form="W-2",
            irs_box="3"
        ),
        "box_4_ss_tax": FieldSpec(
            name="box_4_ss_tax",
            data_type="decimal",
            min_value=Decimal("0"),
            max_value=Decimal("10918.20"),  # 6.2% of 176100
            precision=2,
            is_monetary=True,
            irs_form="W-2",
            irs_box="4"
        ),
        "box_5_medicare_wages": FieldSpec(
            name="box_5_medicare_wages",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="W-2",
            irs_box="5"
        ),
        "box_6_medicare_tax": FieldSpec(
            name="box_6_medicare_tax",
            data_type="decimal",
            min_value=Decimal("0"),
            precision=2,
            is_monetary=True,
            irs_form="W-2",
            irs_box="6"
        ),
    }

    # ==========================================================================
    # TAX YEAR 2025 CONSTANTS
    # ==========================================================================

    TAX_YEAR_LIMITS = {
        # Standard Deductions (2025) - IRS Rev. Proc. 2024-40
        "standard_deduction": {
            "single": Decimal("15750"),
            "married_joint": Decimal("31500"),
            "married_separate": Decimal("15750"),
            "head_of_household": Decimal("23625"),
            "qualifying_widow": Decimal("31500"),
        },
        # Additional Standard Deduction (65+ or blind) - 2025
        "additional_standard_deduction": {
            "single": Decimal("1950"),
            "married_joint": Decimal("1550"),
            "married_separate": Decimal("1550"),
            "head_of_household": Decimal("1950"),
            "qualifying_widow": Decimal("1550"),
        },
        # Contribution Limits
        "contribution_limits": {
            "traditional_ira": Decimal("7000"),
            "ira_catchup_50_plus": Decimal("1000"),
            "401k": Decimal("23500"),
            "401k_catchup_50_plus": Decimal("7500"),
            "hsa_individual": Decimal("4300"),
            "hsa_family": Decimal("8550"),
            "hsa_catchup_55_plus": Decimal("1000"),
            "sep_ira": Decimal("69000"),
        },
        # Credit Limits
        "credit_limits": {
            "child_tax_credit": Decimal("2000"),
            "additional_child_tax_credit": Decimal("1700"),
            "dependent_care_max_expenses": Decimal("3000"),  # per dependent
            "aotc_max": Decimal("2500"),
            "llc_max": Decimal("2000"),
            "saver_credit_max": Decimal("1000"),
        },
        # Other Limits
        "other_limits": {
            "salt_cap": Decimal("10000"),
            "ss_wage_base": Decimal("176100"),
            "medical_expense_floor_pct": Decimal("0.075"),  # 7.5% of AGI
            "educator_expense_max": Decimal("300"),
            "student_loan_interest_max": Decimal("2500"),
            "capital_loss_limit": Decimal("3000"),
        },
        # Income Thresholds
        "income_thresholds": {
            "eitc_investment_income_limit": Decimal("11950"),
            "niit_threshold_single": Decimal("200000"),
            "niit_threshold_mfj": Decimal("250000"),
            "additional_medicare_single": Decimal("200000"),
            "additional_medicare_mfj": Decimal("250000"),
        },
    }

    @classmethod
    def get_all_fields(cls) -> Dict[str, FieldSpec]:
        """Return all field specifications combined."""
        all_fields = {}
        all_fields.update(cls.TAXPAYER_FIELDS)
        all_fields.update(cls.INCOME_FIELDS)
        all_fields.update(cls.ADJUSTMENT_FIELDS)
        all_fields.update(cls.DEDUCTION_FIELDS)
        all_fields.update(cls.TAX_FIELDS)
        all_fields.update(cls.W2_FIELDS)
        return all_fields

    @classmethod
    def get_required_fields(cls) -> List[str]:
        """Return list of required field names."""
        return [
            name for name, spec in cls.get_all_fields().items()
            if spec.required
        ]

    @classmethod
    def get_computed_fields(cls) -> List[str]:
        """Return list of computed field names."""
        return [
            name for name, spec in cls.get_all_fields().items()
            if spec.computed
        ]

    @classmethod
    def get_pii_fields(cls) -> List[str]:
        """Return list of PII field names requiring encryption."""
        return [
            name for name, spec in cls.get_all_fields().items()
            if spec.is_pii
        ]

    @classmethod
    def get_standard_deduction(cls, filing_status: str, is_over_65: bool = False,
                               is_blind: bool = False, spouse_over_65: bool = False,
                               spouse_blind: bool = False) -> Decimal:
        """
        Calculate standard deduction amount based on filing status and age/blindness.

        Args:
            filing_status: Filing status code
            is_over_65: Primary taxpayer is 65 or older
            is_blind: Primary taxpayer is blind
            spouse_over_65: Spouse is 65 or older (MFJ/MFS only)
            spouse_blind: Spouse is blind (MFJ/MFS only)

        Returns:
            Total standard deduction amount
        """
        base = cls.TAX_YEAR_LIMITS["standard_deduction"].get(filing_status, Decimal("0"))
        additional = cls.TAX_YEAR_LIMITS["additional_standard_deduction"].get(filing_status, Decimal("0"))

        total = base

        # Add for primary taxpayer
        if is_over_65:
            total += additional
        if is_blind:
            total += additional

        # Add for spouse (MFJ/MFS only)
        if filing_status in ["married_joint", "married_separate"]:
            if spouse_over_65:
                total += additional
            if spouse_blind:
                total += additional

        return total
