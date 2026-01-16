"""
Comprehensive Validation Layer for US Tax Returns.

This module provides:
1. Structural Validation - Data types, formats, required fields
2. Business Rules Validation - IRS rules, limits, eligibility
3. IRS Compliance Validation - E-file requirements, form completeness

Tax Year: 2025 (Filing in 2026)
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Any, Callable, Union
import re

from .schema import (
    FieldSpec, TaxReturnSchema, ValidationResult, BusinessRuleResult,
    ValidationSeverity, ValidationCategory, SchemaValidationReport
)


# =============================================================================
# STRUCTURAL VALIDATOR
# =============================================================================

class StructuralValidator:
    """
    Validates data structure against field specifications.

    Checks:
    - Required fields presence
    - Data type correctness
    - Value range constraints
    - Pattern matching (regex)
    - Enumeration membership
    """

    def __init__(self, schema: type = TaxReturnSchema):
        self.schema = schema
        self.field_specs = schema.get_all_fields()

    def validate_field(self, field_name: str, value: Any) -> ValidationResult:
        """
        Validate a single field against its specification.

        Args:
            field_name: Name of the field
            value: Value to validate

        Returns:
            ValidationResult with validation outcome
        """
        spec = self.field_specs.get(field_name)

        if not spec:
            return ValidationResult(
                is_valid=True,
                field_name=field_name,
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.STRUCTURAL,
                code="S000",
                message=f"Field '{field_name}' not in schema (custom field)"
            )

        # Required field check
        if spec.required and (value is None or value == ""):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S001",
                message=f"Required field '{field_name}' is missing",
                irs_reference=f"{spec.irs_form} {spec.irs_line or ''}".strip(),
                suggested_action=f"Provide a value for {field_name}"
            )

        # Null check (if not nullable)
        if not spec.nullable and value is None:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S002",
                message=f"Field '{field_name}' cannot be null",
                current_value=value
            )

        # Skip further validation if null and nullable
        if value is None:
            return ValidationResult(
                is_valid=True,
                field_name=field_name,
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.STRUCTURAL,
                code="S100",
                message=f"Field '{field_name}' is null (allowed)"
            )

        # Type-specific validation
        if spec.data_type == "string":
            return self._validate_string(field_name, value, spec)
        elif spec.data_type == "decimal":
            return self._validate_decimal(field_name, value, spec)
        elif spec.data_type == "integer":
            return self._validate_integer(field_name, value, spec)
        elif spec.data_type == "date":
            return self._validate_date(field_name, value, spec)
        elif spec.data_type == "boolean":
            return self._validate_boolean(field_name, value, spec)
        elif spec.data_type == "enum":
            return self._validate_enum(field_name, value, spec)

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S101",
            message=f"Field '{field_name}' passed validation"
        )

    def _validate_string(self, field_name: str, value: Any, spec: FieldSpec) -> ValidationResult:
        """Validate string field."""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S010",
                message=f"Field '{field_name}' must be a string, got {type(value).__name__}",
                current_value=value,
                expected_value="string"
            )

        # Length checks
        if spec.min_length and len(value) < spec.min_length:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S011",
                message=f"Field '{field_name}' is too short (min: {spec.min_length})",
                current_value=len(value),
                expected_value=f">= {spec.min_length}"
            )

        if spec.max_length and len(value) > spec.max_length:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S012",
                message=f"Field '{field_name}' is too long (max: {spec.max_length})",
                current_value=len(value),
                expected_value=f"<= {spec.max_length}"
            )

        # Pattern check
        if spec.pattern:
            if not re.match(spec.pattern, value):
                return ValidationResult(
                    is_valid=False,
                    field_name=field_name,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.STRUCTURAL,
                    code="S013",
                    message=f"Field '{field_name}' does not match required format",
                    current_value=value,
                    expected_value=spec.pattern,
                    suggested_action="Check the format and correct the value"
                )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S102",
            message=f"String field '{field_name}' is valid"
        )

    def _validate_decimal(self, field_name: str, value: Any, spec: FieldSpec) -> ValidationResult:
        """Validate decimal/monetary field."""
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S020",
                message=f"Field '{field_name}' must be a valid number",
                current_value=value
            )

        # Negative check
        if not spec.allow_negative and decimal_value < 0:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S021",
                message=f"Field '{field_name}' cannot be negative",
                current_value=float(decimal_value),
                expected_value=">= 0",
                irs_reference=spec.irs_form
            )

        # Range checks
        if spec.min_value is not None and decimal_value < spec.min_value:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S022",
                message=f"Field '{field_name}' is below minimum ({spec.min_value})",
                current_value=float(decimal_value),
                expected_value=f">= {spec.min_value}"
            )

        if spec.max_value is not None and decimal_value > spec.max_value:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S023",
                message=f"Field '{field_name}' exceeds maximum ({spec.max_value})",
                current_value=float(decimal_value),
                expected_value=f"<= {spec.max_value}",
                irs_reference=spec.irs_form
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S103",
            message=f"Decimal field '{field_name}' is valid"
        )

    def _validate_integer(self, field_name: str, value: Any, spec: FieldSpec) -> ValidationResult:
        """Validate integer field."""
        if not isinstance(value, int) or isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S030",
                message=f"Field '{field_name}' must be an integer",
                current_value=value
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S104",
            message=f"Integer field '{field_name}' is valid"
        )

    def _validate_date(self, field_name: str, value: Any, spec: FieldSpec) -> ValidationResult:
        """Validate date field."""
        if not isinstance(value, date):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S040",
                message=f"Field '{field_name}' must be a date",
                current_value=value
            )

        if spec.min_date and value < spec.min_date:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S041",
                message=f"Field '{field_name}' is before minimum date",
                current_value=str(value),
                expected_value=f">= {spec.min_date}"
            )

        if spec.max_date and value > spec.max_date:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S042",
                message=f"Field '{field_name}' is after maximum date",
                current_value=str(value),
                expected_value=f"<= {spec.max_date}"
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S105",
            message=f"Date field '{field_name}' is valid"
        )

    def _validate_boolean(self, field_name: str, value: Any, spec: FieldSpec) -> ValidationResult:
        """Validate boolean field."""
        if not isinstance(value, bool):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S050",
                message=f"Field '{field_name}' must be a boolean",
                current_value=value
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S106",
            message=f"Boolean field '{field_name}' is valid"
        )

    def _validate_enum(self, field_name: str, value: Any, spec: FieldSpec) -> ValidationResult:
        """Validate enumeration field."""
        if spec.valid_values and value not in spec.valid_values:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.STRUCTURAL,
                code="S060",
                message=f"Field '{field_name}' has invalid value",
                current_value=value,
                expected_value=f"One of: {', '.join(spec.valid_values)}"
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.STRUCTURAL,
            code="S107",
            message=f"Enum field '{field_name}' is valid"
        )

    def validate_all(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate all fields in data dictionary."""
        results = []

        # Check required fields
        for field_name in self.schema.get_required_fields():
            if field_name not in data:
                results.append(ValidationResult(
                    is_valid=False,
                    field_name=field_name,
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.STRUCTURAL,
                    code="S001",
                    message=f"Required field '{field_name}' is missing"
                ))

        # Validate each provided field
        for field_name, value in data.items():
            result = self.validate_field(field_name, value)
            results.append(result)

        return results


# =============================================================================
# BUSINESS RULES VALIDATOR
# =============================================================================

class BusinessRulesValidator:
    """
    Validates tax return against IRS business rules.

    Rules include:
    - Contribution limits (IRA, 401k, HSA)
    - Credit eligibility and phaseouts
    - Deduction limitations (SALT cap, medical floor)
    - Filing status requirements
    - Income consistency checks
    """

    TAX_YEAR = 2025

    def __init__(self):
        self.rules: List[Callable] = [
            self._rule_salt_cap,
            self._rule_ss_wage_base,
            self._rule_ira_contribution_limit,
            self._rule_hsa_contribution_limit,
            self._rule_401k_contribution_limit,
            self._rule_eitc_investment_income,
            self._rule_qualified_vs_ordinary_dividends,
            self._rule_taxable_vs_total_social_security,
            self._rule_medical_expense_floor,
            self._rule_charitable_contribution_limit,
            self._rule_capital_loss_limitation,
            self._rule_aotc_vs_llc_conflict,
            self._rule_dependent_age_ctc,
            self._rule_filing_status_spouse_consistency,
            self._rule_head_of_household_requirements,
            self._rule_w2_box_consistency,
            self._rule_self_employment_expense_limit,
            self._rule_estimated_tax_requirement,
        ]

    def validate(self, tax_return_data: Dict[str, Any]) -> List[BusinessRuleResult]:
        """
        Run all business rules against tax return data.

        Args:
            tax_return_data: Dictionary containing all tax return data

        Returns:
            List of BusinessRuleResult for each rule checked
        """
        results = []
        for rule in self.rules:
            try:
                result = rule(tax_return_data)
                if result:
                    results.append(result)
            except Exception as e:
                results.append(BusinessRuleResult(
                    rule_id="ERROR",
                    rule_name=rule.__name__,
                    passed=False,
                    severity=ValidationSeverity.WARNING,
                    message=f"Rule evaluation error: {str(e)}"
                ))
        return results

    def _rule_salt_cap(self, data: Dict) -> Optional[BusinessRuleResult]:
        """SALT deduction capped at $10,000."""
        salt_total = (
            Decimal(str(data.get("state_local_income_tax", 0))) +
            Decimal(str(data.get("state_local_sales_tax", 0))) +
            Decimal(str(data.get("real_estate_tax", 0))) +
            Decimal(str(data.get("personal_property_tax", 0)))
        )

        salt_cap = Decimal("10000")

        if salt_total > salt_cap:
            return BusinessRuleResult(
                rule_id="BR001",
                rule_name="SALT Cap Limitation",
                passed=True,  # Not a failure, just an application of limitation
                severity=ValidationSeverity.INFO,
                message=f"SALT deduction limited from ${salt_total:,.2f} to ${salt_cap:,.2f}",
                affected_fields=["state_local_income_tax", "real_estate_tax"],
                irs_reference="IRC Section 164(b)(6)",
                tax_impact=salt_total - salt_cap
            )
        return None

    def _rule_ss_wage_base(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Social Security wages cannot exceed wage base ($176,100 for 2025)."""
        ss_wages = Decimal(str(data.get("box_3_ss_wages", 0)))
        wage_base = Decimal("176100")

        if ss_wages > wage_base:
            return BusinessRuleResult(
                rule_id="BR002",
                rule_name="Social Security Wage Base",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"W-2 Box 3 SS wages (${ss_wages:,.2f}) exceeds wage base (${wage_base:,.2f})",
                affected_fields=["box_3_ss_wages"],
                irs_reference="IRC Section 3121(a)"
            )
        return None

    def _rule_ira_contribution_limit(self, data: Dict) -> Optional[BusinessRuleResult]:
        """IRA contributions limited to $7,000 ($8,000 if 50+)."""
        ira_contribution = Decimal(str(data.get("ira_contribution", 0)))
        age = data.get("age", 0)

        limit = Decimal("7000") if age < 50 else Decimal("8000")

        if ira_contribution > limit:
            return BusinessRuleResult(
                rule_id="BR003",
                rule_name="IRA Contribution Limit",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"IRA contribution (${ira_contribution:,.2f}) exceeds limit (${limit:,.2f})",
                affected_fields=["ira_contribution"],
                irs_reference="IRC Section 219(b)"
            )
        return None

    def _rule_hsa_contribution_limit(self, data: Dict) -> Optional[BusinessRuleResult]:
        """HSA contributions limited ($4,300 individual, $8,550 family for 2025)."""
        hsa_contribution = Decimal(str(data.get("hsa_contribution", 0)))
        hsa_coverage = data.get("hsa_coverage_type", "individual")
        age = data.get("age", 0)

        if hsa_coverage == "family":
            limit = Decimal("8550")
        else:
            limit = Decimal("4300")

        if age >= 55:
            limit += Decimal("1000")  # Catch-up contribution

        if hsa_contribution > limit:
            return BusinessRuleResult(
                rule_id="BR004",
                rule_name="HSA Contribution Limit",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"HSA contribution (${hsa_contribution:,.2f}) exceeds limit (${limit:,.2f})",
                affected_fields=["hsa_contribution"],
                irs_reference="IRC Section 223(b)"
            )
        return None

    def _rule_401k_contribution_limit(self, data: Dict) -> Optional[BusinessRuleResult]:
        """401(k) contributions limited to $23,500 ($31,000 if 50+, $34,750 if 60-63)."""
        contribution = Decimal(str(data.get("k401_contribution", 0)))
        age = data.get("age", 0)

        if age >= 60 and age <= 63:
            limit = Decimal("34750")  # Super catch-up
        elif age >= 50:
            limit = Decimal("31000")  # Regular catch-up
        else:
            limit = Decimal("23500")

        if contribution > limit:
            return BusinessRuleResult(
                rule_id="BR005",
                rule_name="401(k) Contribution Limit",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"401(k) contribution (${contribution:,.2f}) exceeds limit (${limit:,.2f})",
                affected_fields=["k401_contribution"],
                irs_reference="IRC Section 402(g)"
            )
        return None

    def _rule_eitc_investment_income(self, data: Dict) -> Optional[BusinessRuleResult]:
        """EITC disallowed if investment income exceeds $11,600 (2025)."""
        claiming_eitc = data.get("claiming_eitc", False)
        investment_income = (
            Decimal(str(data.get("interest_income", 0))) +
            Decimal(str(data.get("dividend_income", 0))) +
            Decimal(str(data.get("capital_gains", 0))) +
            Decimal(str(data.get("rental_income", 0)))
        )

        limit = Decimal("11600")

        if claiming_eitc and investment_income > limit:
            return BusinessRuleResult(
                rule_id="BR006",
                rule_name="EITC Investment Income Limit",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Investment income (${investment_income:,.2f}) exceeds EITC limit (${limit:,.2f})",
                affected_fields=["interest_income", "dividend_income", "capital_gains"],
                irs_reference="IRC Section 32(i)"
            )
        return None

    def _rule_qualified_vs_ordinary_dividends(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Qualified dividends cannot exceed ordinary dividends."""
        qualified = Decimal(str(data.get("qualified_dividends", 0)))
        ordinary = Decimal(str(data.get("ordinary_dividends", 0)))

        if qualified > ordinary:
            return BusinessRuleResult(
                rule_id="BR007",
                rule_name="Qualified vs Ordinary Dividends",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Qualified dividends (${qualified:,.2f}) cannot exceed ordinary dividends (${ordinary:,.2f})",
                affected_fields=["qualified_dividends", "ordinary_dividends"],
                irs_reference="Form 1040 Instructions"
            )
        return None

    def _rule_taxable_vs_total_social_security(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Taxable SS cannot exceed total SS benefits or 85% maximum."""
        taxable = Decimal(str(data.get("taxable_social_security", 0)))
        total = Decimal(str(data.get("total_social_security", 0)))
        max_taxable = total * Decimal("0.85")

        if taxable > total:
            return BusinessRuleResult(
                rule_id="BR008",
                rule_name="Social Security Taxability",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Taxable SS (${taxable:,.2f}) cannot exceed total SS (${total:,.2f})",
                affected_fields=["taxable_social_security", "total_social_security"],
                irs_reference="IRC Section 86"
            )

        if taxable > max_taxable:
            return BusinessRuleResult(
                rule_id="BR008B",
                rule_name="Social Security 85% Maximum",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Taxable SS (${taxable:,.2f}) cannot exceed 85% (${max_taxable:,.2f})",
                affected_fields=["taxable_social_security"],
                irs_reference="IRC Section 86(a)(2)"
            )
        return None

    def _rule_medical_expense_floor(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Medical expenses deductible only above 7.5% of AGI."""
        medical_expenses = Decimal(str(data.get("medical_expenses", 0)))
        agi = Decimal(str(data.get("agi", 0)))
        floor = agi * Decimal("0.075")

        if medical_expenses > 0 and medical_expenses <= floor:
            return BusinessRuleResult(
                rule_id="BR009",
                rule_name="Medical Expense Floor",
                passed=True,
                severity=ValidationSeverity.INFO,
                message=f"Medical expenses (${medical_expenses:,.2f}) do not exceed 7.5% AGI floor (${floor:,.2f})",
                affected_fields=["medical_expenses"],
                irs_reference="IRC Section 213(a)"
            )
        return None

    def _rule_charitable_contribution_limit(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Cash charitable contributions limited to 60% of AGI."""
        cash_charitable = Decimal(str(data.get("charitable_cash", 0)))
        agi = Decimal(str(data.get("agi", 0)))
        limit = agi * Decimal("0.60")

        if cash_charitable > limit:
            return BusinessRuleResult(
                rule_id="BR010",
                rule_name="Charitable Contribution Limit",
                passed=True,
                severity=ValidationSeverity.WARNING,
                message=f"Cash charitable (${cash_charitable:,.2f}) exceeds 60% AGI limit (${limit:,.2f}) - excess carries forward",
                affected_fields=["charitable_cash"],
                irs_reference="IRC Section 170(b)(1)(A)",
                tax_impact=cash_charitable - limit
            )
        return None

    def _rule_capital_loss_limitation(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Net capital loss deduction limited to $3,000."""
        net_capital = (
            Decimal(str(data.get("short_term_capital_gains", 0))) +
            Decimal(str(data.get("long_term_capital_gains", 0)))
        )
        limit = Decimal("-3000")

        if net_capital < limit:
            return BusinessRuleResult(
                rule_id="BR011",
                rule_name="Capital Loss Limitation",
                passed=True,
                severity=ValidationSeverity.INFO,
                message=f"Capital loss limited to $3,000 - ${abs(net_capital) - 3000:,.2f} carries forward",
                affected_fields=["short_term_capital_gains", "long_term_capital_gains"],
                irs_reference="IRC Section 1211(b)"
            )
        return None

    def _rule_aotc_vs_llc_conflict(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Cannot claim both AOTC and LLC for same student."""
        students_with_aotc = set(data.get("aotc_students", []))
        students_with_llc = set(data.get("llc_students", []))
        overlap = students_with_aotc & students_with_llc

        if overlap:
            return BusinessRuleResult(
                rule_id="BR012",
                rule_name="AOTC/LLC Conflict",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Cannot claim both AOTC and LLC for same student: {overlap}",
                affected_fields=["education_credits"],
                irs_reference="IRC Section 25A(c)(2)"
            )
        return None

    def _rule_dependent_age_ctc(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Child Tax Credit requires child under 17 at end of year."""
        dependents = data.get("dependents", [])
        ctc_claimed = data.get("child_tax_credit", 0)

        if ctc_claimed > 0:
            qualifying_children = [d for d in dependents if d.get("age", 99) < 17]
            if not qualifying_children:
                return BusinessRuleResult(
                    rule_id="BR013",
                    rule_name="CTC Age Requirement",
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message="Child Tax Credit requires qualifying child under 17",
                    affected_fields=["child_tax_credit", "dependents"],
                    irs_reference="IRC Section 24(c)"
                )
        return None

    def _rule_filing_status_spouse_consistency(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Married filing statuses require spouse information."""
        filing_status = data.get("filing_status", "")
        spouse_ssn = data.get("spouse_ssn")

        if filing_status in ["married_joint", "married_separate"]:
            if not spouse_ssn:
                return BusinessRuleResult(
                    rule_id="BR014",
                    rule_name="Spouse Information Required",
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Filing status '{filing_status}' requires spouse SSN",
                    affected_fields=["filing_status", "spouse_ssn"],
                    irs_reference="Form 1040 Instructions"
                )
        return None

    def _rule_head_of_household_requirements(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Head of Household requires qualifying person and unmarried status."""
        filing_status = data.get("filing_status", "")
        marital_status = data.get("marital_status", "")
        qualifying_person = data.get("has_qualifying_person", False)

        if filing_status == "head_of_household":
            if marital_status == "married":
                return BusinessRuleResult(
                    rule_id="BR015A",
                    rule_name="HOH Marital Status",
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message="Head of Household requires unmarried status",
                    affected_fields=["filing_status"],
                    irs_reference="IRC Section 2(b)"
                )
            if not qualifying_person:
                return BusinessRuleResult(
                    rule_id="BR015B",
                    rule_name="HOH Qualifying Person",
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message="Head of Household requires a qualifying person",
                    affected_fields=["filing_status", "dependents"],
                    irs_reference="IRC Section 2(b)"
                )
        return None

    def _rule_w2_box_consistency(self, data: Dict) -> Optional[BusinessRuleResult]:
        """W-2 boxes should be internally consistent."""
        box_1 = Decimal(str(data.get("box_1_wages", 0)))
        box_3 = Decimal(str(data.get("box_3_ss_wages", 0)))
        box_5 = Decimal(str(data.get("box_5_medicare_wages", 0)))

        # Medicare wages typically >= SS wages >= Box 1 wages
        if box_3 > box_5:
            return BusinessRuleResult(
                rule_id="BR016",
                rule_name="W-2 Box Consistency",
                passed=False,
                severity=ValidationSeverity.WARNING,
                message="W-2 Box 3 (SS wages) should not exceed Box 5 (Medicare wages)",
                affected_fields=["box_3_ss_wages", "box_5_medicare_wages"],
                irs_reference="W-2 Instructions"
            )
        return None

    def _rule_self_employment_expense_limit(self, data: Dict) -> Optional[BusinessRuleResult]:
        """Self-employment expenses cannot exceed income."""
        se_income = Decimal(str(data.get("self_employment_income", 0)))
        se_expenses = Decimal(str(data.get("self_employment_expenses", 0)))

        if se_expenses > se_income:
            return BusinessRuleResult(
                rule_id="BR017",
                rule_name="SE Expense Limit",
                passed=True,  # Business loss is allowed
                severity=ValidationSeverity.WARNING,
                message=f"Self-employment expenses (${se_expenses:,.2f}) exceed income (${se_income:,.2f}) - verify business loss",
                affected_fields=["self_employment_income", "self_employment_expenses"],
                irs_reference="Schedule C Instructions"
            )
        return None

    def _rule_estimated_tax_requirement(self, data: Dict) -> Optional[BusinessRuleResult]:
        """May require estimated tax payments if withholding insufficient."""
        total_tax = Decimal(str(data.get("total_tax", 0)))
        withholding = Decimal(str(data.get("total_withholding", 0)))
        prior_year_tax = Decimal(str(data.get("prior_year_tax", 0)))

        shortfall = total_tax - withholding

        if shortfall > Decimal("1000"):
            safe_harbor = max(prior_year_tax, total_tax * Decimal("0.90"))
            if withholding < safe_harbor:
                return BusinessRuleResult(
                    rule_id="BR018",
                    rule_name="Estimated Tax Requirement",
                    passed=True,
                    severity=ValidationSeverity.WARNING,
                    message=f"May owe estimated tax penalty - shortfall: ${shortfall:,.2f}",
                    affected_fields=["total_tax", "total_withholding"],
                    irs_reference="IRC Section 6654",
                    tax_impact=shortfall
                )
        return None


# =============================================================================
# IRS COMPLIANCE VALIDATOR
# =============================================================================

class IRSComplianceValidator:
    """
    Validates tax return for IRS e-file compliance.

    Checks:
    - E-file rejection codes
    - Required form attachments
    - Signature requirements
    - Filing deadlines
    """

    def validate_efile_requirements(self, data: Dict) -> List[ValidationResult]:
        """Check IRS e-file mandatory requirements."""
        results = []

        # SSN format (no dashes for e-file)
        ssn = data.get("ssn", "")
        if "-" in ssn:
            results.append(ValidationResult(
                is_valid=False,
                field_name="ssn",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.COMPLIANCE,
                code="C001",
                message="SSN must not contain dashes for e-file",
                irs_reference="IRS MeF Business Rules"
            ))

        # Filing status required
        if not data.get("filing_status"):
            results.append(ValidationResult(
                is_valid=False,
                field_name="filing_status",
                severity=ValidationSeverity.CRITICAL,
                category=ValidationCategory.COMPLIANCE,
                code="C002",
                message="Filing status is required for e-file",
                irs_reference="Form 1040 Line 1"
            ))

        # Signature/PIN required
        if not data.get("signature_pin") and not data.get("signature"):
            results.append(ValidationResult(
                is_valid=False,
                field_name="signature",
                severity=ValidationSeverity.CRITICAL,
                category=ValidationCategory.COMPLIANCE,
                code="C003",
                message="Electronic signature or PIN required for e-file",
                irs_reference="IRS e-file Signature Authorization"
            ))

        # Date of birth for age-related deductions
        if data.get("is_over_65") and not data.get("date_of_birth"):
            results.append(ValidationResult(
                is_valid=False,
                field_name="date_of_birth",
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.COMPLIANCE,
                code="C004",
                message="Date of birth recommended when claiming age-related deduction",
                irs_reference="Form 1040 Instructions"
            ))

        return results

    def check_rejection_codes(self, data: Dict) -> List[str]:
        """
        Check for common IRS rejection code scenarios.

        Returns list of potential rejection codes.
        """
        rejection_codes = []

        # R0000-504-02: Primary SSN already used
        # (Would require database check - placeholder)

        # R0000-902-01: Missing required schedule
        if data.get("self_employment_income", 0) > 0 and not data.get("has_schedule_c"):
            rejection_codes.append("R0000-902-01")

        # R0000-507-01: Invalid dependent SSN
        for dep in data.get("dependents", []):
            if not dep.get("ssn"):
                rejection_codes.append("R0000-507-01")
                break

        return rejection_codes
