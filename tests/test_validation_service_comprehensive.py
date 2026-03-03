"""
Comprehensive tests for Validation Service — severity/category enums,
issue/result dataclasses, all validation rules (required fields, SSN format,
income range, W2, filing status consistency, dividends, deductions, SALT limits,
retirement contributions, charitable contributions), and the service itself.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.validation_service import (
    ValidationSeverity,
    ValidationCategory,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    RequiredFieldRule,
    SSNFormatRule,
    IncomeRangeRule,
    W2ValidationRule,
    FilingStatusConsistencyRule,
    DividendConsistencyRule,
    DeductionConsistencyRule,
    SALTLimitRule,
    RetirementContributionLimitRule,
    CharitableContributionLimitRule,
    ValidationService,
    create_validation_service,
)
from models.taxpayer import FilingStatus


# ===================================================================
# HELPER — Minimal TaxReturn mock
# ===================================================================

def _make_taxpayer(**overrides):
    tp = Mock()
    tp.first_name = overrides.get("first_name", "John")
    tp.last_name = overrides.get("last_name", "Doe")
    tp.ssn = overrides.get("ssn", "123-45-6789")
    tp.filing_status = overrides.get("filing_status", FilingStatus.SINGLE)
    tp.dependents = overrides.get("dependents", [])
    tp.spouse_first_name = overrides.get("spouse_first_name", None)
    tp.spouse_last_name = overrides.get("spouse_last_name", None)
    tp.spouse_ssn = overrides.get("spouse_ssn", None)
    tp.date_of_birth = overrides.get("date_of_birth", None)
    return tp


def _make_w2(**overrides):
    w2 = Mock()
    w2.employer_name = overrides.get("employer_name", "Acme Corp")
    w2.employer_ein = overrides.get("employer_ein", "12-3456789")
    w2.wages = overrides.get("wages", 75000)
    w2.federal_tax_withheld = overrides.get("federal_tax_withheld", 12000)
    w2.social_security_wages = overrides.get("social_security_wages", 75000)
    return w2


def _make_income(**overrides):
    income = Mock()
    income.w2_forms = overrides.get("w2_forms", [_make_w2()])
    income.dividend_income = overrides.get("dividend_income", 0)
    income.qualified_dividends = overrides.get("qualified_dividends", 0)
    income.interest_income = overrides.get("interest_income", 0)
    income.self_employment_income = overrides.get("self_employment_income", 0)
    return income


def _make_itemized(**overrides):
    item = Mock()
    item.mortgage_interest = overrides.get("mortgage_interest", 0)
    item.state_local_income_tax = overrides.get("state_local_income_tax", 0)
    item.state_local_sales_tax = overrides.get("state_local_sales_tax", 0)
    item.real_estate_tax = overrides.get("real_estate_tax", 0)
    item.personal_property_tax = overrides.get("personal_property_tax", 0)
    item.charitable_cash = overrides.get("charitable_cash", 0)
    item.charitable_non_cash = overrides.get("charitable_non_cash", 0)
    return item


def _make_deductions(**overrides):
    ded = Mock()
    ded.itemized = overrides.get("itemized", _make_itemized())
    ded.ira_contributions = overrides.get("ira_contributions", 0)
    ded.hsa_contributions = overrides.get("hsa_contributions", 0)
    return ded


def _make_tax_return(**overrides):
    tr = Mock()
    tr.taxpayer = overrides.get("taxpayer", _make_taxpayer())
    tr.income = overrides.get("income", _make_income())
    tr.deductions = overrides.get("deductions", _make_deductions())
    return tr


# ===================================================================
# VALIDATION SEVERITY ENUM
# ===================================================================

class TestValidationSeverity:

    @pytest.mark.parametrize("severity,value", [
        (ValidationSeverity.ERROR, "error"),
        (ValidationSeverity.WARNING, "warning"),
        (ValidationSeverity.INFO, "info"),
    ])
    def test_severity_values(self, severity, value):
        assert severity.value == value

    def test_severity_count(self):
        assert len(ValidationSeverity) == 3

    @pytest.mark.parametrize("severity", list(ValidationSeverity))
    def test_severity_is_string(self, severity):
        assert isinstance(severity.value, str)


# ===================================================================
# VALIDATION CATEGORY ENUM
# ===================================================================

class TestValidationCategory:

    @pytest.mark.parametrize("category,value", [
        (ValidationCategory.REQUIRED, "required"),
        (ValidationCategory.FORMAT, "format"),
        (ValidationCategory.RANGE, "range"),
        (ValidationCategory.CONSISTENCY, "consistency"),
        (ValidationCategory.TAX_RULE, "tax_rule"),
        (ValidationCategory.LIMIT, "limit"),
        (ValidationCategory.DEADLINE, "deadline"),
    ])
    def test_category_values(self, category, value):
        assert category.value == value

    def test_category_count(self):
        assert len(ValidationCategory) == 7

    @pytest.mark.parametrize("category", list(ValidationCategory))
    def test_category_is_string(self, category):
        assert isinstance(category.value, str)


# ===================================================================
# VALIDATION ISSUE
# ===================================================================

class TestValidationIssue:

    def test_issue_creation(self):
        issue = ValidationIssue(
            code="TEST_001",
            field_path="taxpayer.first_name",
            message="First name missing",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.REQUIRED,
        )
        assert issue.code == "TEST_001"
        assert issue.field_path == "taxpayer.first_name"
        assert issue.severity == ValidationSeverity.ERROR

    def test_issue_defaults(self):
        issue = ValidationIssue(
            code="T", field_path="f", message="m",
            severity=ValidationSeverity.INFO,
            category=ValidationCategory.FORMAT,
        )
        assert issue.value is None
        assert issue.suggestion is None
        assert issue.irs_reference is None

    def test_issue_with_all_fields(self):
        issue = ValidationIssue(
            code="T", field_path="f", message="m",
            severity=ValidationSeverity.WARNING,
            category=ValidationCategory.LIMIT,
            value=15000,
            suggestion="Reduce amount",
            irs_reference="IRC Section 164",
        )
        assert issue.value == 15000
        assert issue.suggestion == "Reduce amount"
        assert issue.irs_reference == "IRC Section 164"

    def test_to_dict(self):
        issue = ValidationIssue(
            code="T1", field_path="f.g", message="msg",
            severity=ValidationSeverity.ERROR,
            category=ValidationCategory.REQUIRED,
        )
        d = issue.to_dict()
        assert d["code"] == "T1"
        assert d["severity"] == "error"
        assert d["category"] == "required"

    @pytest.mark.parametrize("severity", list(ValidationSeverity))
    def test_to_dict_severity_serialization(self, severity):
        issue = ValidationIssue(
            code="T", field_path="f", message="m",
            severity=severity, category=ValidationCategory.REQUIRED,
        )
        d = issue.to_dict()
        assert d["severity"] == severity.value

    @pytest.mark.parametrize("category", list(ValidationCategory))
    def test_to_dict_category_serialization(self, category):
        issue = ValidationIssue(
            code="T", field_path="f", message="m",
            severity=ValidationSeverity.INFO, category=category,
        )
        d = issue.to_dict()
        assert d["category"] == category.value


# ===================================================================
# VALIDATION RESULT
# ===================================================================

class TestValidationResult:

    def test_valid_result(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.issues == []
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_default_tax_year(self):
        result = ValidationResult(is_valid=True)
        assert result.tax_year == 2025

    def test_error_count(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="E1", field_path="f", message="m",
            severity=ValidationSeverity.ERROR, category=ValidationCategory.REQUIRED,
        ))
        result.add_issue(ValidationIssue(
            code="E2", field_path="f", message="m",
            severity=ValidationSeverity.ERROR, category=ValidationCategory.REQUIRED,
        ))
        assert result.error_count == 2

    def test_warning_count(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="W1", field_path="f", message="m",
            severity=ValidationSeverity.WARNING, category=ValidationCategory.RANGE,
        ))
        assert result.warning_count == 1

    def test_add_error_sets_invalid(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="E1", field_path="f", message="m",
            severity=ValidationSeverity.ERROR, category=ValidationCategory.REQUIRED,
        ))
        assert result.is_valid is False

    def test_add_warning_stays_valid(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="W1", field_path="f", message="m",
            severity=ValidationSeverity.WARNING, category=ValidationCategory.RANGE,
        ))
        assert result.is_valid is True

    def test_add_info_stays_valid(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="I1", field_path="f", message="m",
            severity=ValidationSeverity.INFO, category=ValidationCategory.LIMIT,
        ))
        assert result.is_valid is True

    def test_errors_property(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="E1", field_path="f", message="m",
            severity=ValidationSeverity.ERROR, category=ValidationCategory.REQUIRED,
        ))
        result.add_issue(ValidationIssue(
            code="W1", field_path="f", message="m",
            severity=ValidationSeverity.WARNING, category=ValidationCategory.RANGE,
        ))
        assert len(result.errors) == 1
        assert result.errors[0].code == "E1"

    def test_warnings_property(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="E1", field_path="f", message="m",
            severity=ValidationSeverity.ERROR, category=ValidationCategory.REQUIRED,
        ))
        result.add_issue(ValidationIssue(
            code="W1", field_path="f", message="m",
            severity=ValidationSeverity.WARNING, category=ValidationCategory.RANGE,
        ))
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "W1"

    def test_to_dict(self):
        result = ValidationResult(is_valid=True, tax_year=2025)
        d = result.to_dict()
        assert d["is_valid"] is True
        assert d["error_count"] == 0
        assert d["warning_count"] == 0
        assert d["tax_year"] == 2025
        assert "validated_at" in d
        assert isinstance(d["issues"], list)

    def test_to_dict_with_issues(self):
        result = ValidationResult(is_valid=True)
        result.add_issue(ValidationIssue(
            code="E", field_path="f", message="m",
            severity=ValidationSeverity.ERROR, category=ValidationCategory.REQUIRED,
        ))
        d = result.to_dict()
        assert len(d["issues"]) == 1
        assert d["is_valid"] is False

    def test_validated_at_timestamp(self):
        result = ValidationResult(is_valid=True)
        assert isinstance(result.validated_at, datetime)


# ===================================================================
# REQUIRED FIELD RULE
# ===================================================================

class TestRequiredFieldRule:

    def test_rule_code(self):
        rule = RequiredFieldRule()
        assert rule.code == "REQ_001"
        assert rule.category == ValidationCategory.REQUIRED

    def test_all_fields_present_no_issues(self):
        tr = _make_tax_return()
        rule = RequiredFieldRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    @pytest.mark.parametrize("field,expected_code", [
        ("first_name", "REQ_001"),
        ("last_name", "REQ_002"),
        ("ssn", "REQ_003"),
    ])
    def test_missing_required_field(self, field, expected_code):
        tr = _make_tax_return(taxpayer=_make_taxpayer(**{field: ""}))
        rule = RequiredFieldRule()
        issues = rule.validate(tr, {})
        codes = [i.code for i in issues]
        assert expected_code in codes

    def test_missing_filing_status(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(filing_status=None))
        rule = RequiredFieldRule()
        issues = rule.validate(tr, {})
        codes = [i.code for i in issues]
        assert "REQ_004" in codes

    def test_all_missing_four_errors(self):
        tp = _make_taxpayer(first_name="", last_name="", ssn="", filing_status=None)
        tr = _make_tax_return(taxpayer=tp)
        rule = RequiredFieldRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 4

    @pytest.mark.parametrize("field_path", [
        "taxpayer.first_name",
        "taxpayer.last_name",
        "taxpayer.ssn",
        "taxpayer.filing_status",
    ])
    def test_issue_field_paths(self, field_path):
        tp = _make_taxpayer(first_name="", last_name="", ssn="", filing_status=None)
        tr = _make_tax_return(taxpayer=tp)
        rule = RequiredFieldRule()
        issues = rule.validate(tr, {})
        paths = [i.field_path for i in issues]
        assert field_path in paths


# ===================================================================
# SSN FORMAT RULE
# ===================================================================

class TestSSNFormatRule:

    def test_rule_code(self):
        rule = SSNFormatRule()
        assert rule.code == "FMT_001"
        assert rule.category == ValidationCategory.FORMAT

    @pytest.mark.parametrize("ssn", [
        "123-45-6789",
        "999-99-9999",
        "001-01-0001",
    ])
    def test_valid_ssn_formats(self, ssn):
        tr = _make_tax_return(taxpayer=_make_taxpayer(ssn=ssn))
        rule = SSNFormatRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    @pytest.mark.parametrize("ssn", [
        "123456789",
        "12-345-6789",
        "123-456-789",
        "abc-de-fghi",
        "12345",
        "1234-5-6789",
    ])
    def test_invalid_ssn_formats(self, ssn):
        tr = _make_tax_return(taxpayer=_make_taxpayer(ssn=ssn))
        rule = SSNFormatRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 1
        assert issues[0].code == "FMT_001"

    def test_no_ssn_no_issue(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(ssn=""))
        rule = SSNFormatRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_ssn_masked_in_issue(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(ssn="123456789"))
        rule = SSNFormatRule()
        issues = rule.validate(tr, {})
        assert issues[0].value.endswith("-XX-XXXX")


# ===================================================================
# INCOME RANGE RULE
# ===================================================================

class TestIncomeRangeRule:

    def test_rule_code(self):
        rule = IncomeRangeRule()
        assert rule.code == "RNG_001"
        assert rule.category == ValidationCategory.RANGE

    def test_normal_income_no_issues(self):
        tr = _make_tax_return()
        rule = IncomeRangeRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    @pytest.mark.parametrize("field,value", [
        ("dividend_income", -100),
        ("interest_income", -50),
        ("self_employment_income", -1000),
    ])
    def test_negative_income_error(self, field, value):
        income = _make_income(**{field: value})
        tr = _make_tax_return(income=income)
        rule = IncomeRangeRule()
        issues = rule.validate(tr, {})
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_high_wages_warning(self):
        w2 = _make_w2(wages=15_000_000)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = IncomeRangeRule()
        issues = rule.validate(tr, {})
        assert any(
            i.code == "RNG_HIGH_WAGES" and i.severity == ValidationSeverity.WARNING
            for i in issues
        )

    def test_wages_under_10m_no_warning(self):
        w2 = _make_w2(wages=5_000_000)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = IncomeRangeRule()
        issues = rule.validate(tr, {})
        assert not any(i.code == "RNG_HIGH_WAGES" for i in issues)

    def test_no_w2_forms(self):
        income = _make_income(w2_forms=[])
        tr = _make_tax_return(income=income)
        rule = IncomeRangeRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0


# ===================================================================
# W2 VALIDATION RULE
# ===================================================================

class TestW2ValidationRule:

    def test_rule_code(self):
        rule = W2ValidationRule()
        assert rule.code == "W2_001"
        assert rule.category == ValidationCategory.RANGE

    def test_valid_w2_no_issues(self):
        tr = _make_tax_return()
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_negative_wages(self):
        w2 = _make_w2(wages=-1000)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "W2_001" for i in issues)

    def test_negative_withholding(self):
        w2 = _make_w2(federal_tax_withheld=-500)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "W2_002" for i in issues)

    def test_ss_wages_exceed_base(self):
        w2 = _make_w2(social_security_wages=200_000)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "W2_003" for i in issues)

    def test_ss_wages_under_base_no_issue(self):
        w2 = _make_w2(social_security_wages=100_000)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert not any(i.code == "W2_003" for i in issues)

    def test_withholding_exceeds_wages(self):
        w2 = _make_w2(wages=50000, federal_tax_withheld=60000)
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "W2_004" for i in issues)

    def test_missing_employer_ein(self):
        w2 = _make_w2(employer_ein="")
        income = _make_income(w2_forms=[w2])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "W2_005" for i in issues)

    def test_multiple_w2s_indexed(self):
        w2a = _make_w2(wages=-100, employer_name="Bad Corp")
        w2b = _make_w2(wages=50000, employer_name="Good Corp")
        income = _make_income(w2_forms=[w2a, w2b])
        tr = _make_tax_return(income=income)
        rule = W2ValidationRule()
        issues = rule.validate(tr, {})
        paths = [i.field_path for i in issues]
        assert any("w2_forms[0]" in p for p in paths)


# ===================================================================
# FILING STATUS CONSISTENCY RULE
# ===================================================================

class TestFilingStatusConsistencyRule:

    def test_rule_code(self):
        rule = FilingStatusConsistencyRule()
        assert rule.code == "CON_001"
        assert rule.category == ValidationCategory.CONSISTENCY

    def test_single_no_issues(self):
        tr = _make_tax_return()
        rule = FilingStatusConsistencyRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_married_joint_no_spouse_name(self):
        tp = _make_taxpayer(filing_status=FilingStatus.MARRIED_JOINT)
        tr = _make_tax_return(taxpayer=tp)
        rule = FilingStatusConsistencyRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "CON_001" for i in issues)

    def test_married_joint_no_spouse_ssn(self):
        tp = _make_taxpayer(
            filing_status=FilingStatus.MARRIED_JOINT,
            spouse_first_name="Jane",
            spouse_last_name="Doe",
            spouse_ssn=None,
        )
        tr = _make_tax_return(taxpayer=tp)
        rule = FilingStatusConsistencyRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "CON_002" for i in issues)

    def test_married_joint_with_spouse_info(self):
        tp = _make_taxpayer(
            filing_status=FilingStatus.MARRIED_JOINT,
            spouse_first_name="Jane",
            spouse_last_name="Doe",
            spouse_ssn="987-65-4321",
        )
        tr = _make_tax_return(taxpayer=tp)
        rule = FilingStatusConsistencyRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_hoh_no_dependents_warning(self):
        tp = _make_taxpayer(
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            dependents=[],
        )
        tr = _make_tax_return(taxpayer=tp)
        rule = FilingStatusConsistencyRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "CON_003" for i in issues)
        assert issues[0].severity == ValidationSeverity.WARNING

    def test_hoh_with_dependent_no_warning(self):
        dep = Mock()
        tp = _make_taxpayer(
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            dependents=[dep],
        )
        tr = _make_tax_return(taxpayer=tp)
        rule = FilingStatusConsistencyRule()
        issues = rule.validate(tr, {})
        assert not any(i.code == "CON_003" for i in issues)


# ===================================================================
# DIVIDEND CONSISTENCY RULE
# ===================================================================

class TestDividendConsistencyRule:

    def test_rule_code(self):
        rule = DividendConsistencyRule()
        assert rule.code == "CON_010"

    def test_qualified_under_total_no_issue(self):
        income = _make_income(dividend_income=5000, qualified_dividends=3000)
        tr = _make_tax_return(income=income)
        rule = DividendConsistencyRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_qualified_equal_total_no_issue(self):
        income = _make_income(dividend_income=5000, qualified_dividends=5000)
        tr = _make_tax_return(income=income)
        rule = DividendConsistencyRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_qualified_exceeds_total_error(self):
        income = _make_income(dividend_income=3000, qualified_dividends=5000)
        tr = _make_tax_return(income=income)
        rule = DividendConsistencyRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.ERROR


# ===================================================================
# DEDUCTION CONSISTENCY RULE
# ===================================================================

class TestDeductionConsistencyRule:

    def test_rule_code(self):
        rule = DeductionConsistencyRule()
        assert rule.code == "CON_020"

    def test_normal_deductions_no_warnings(self):
        tr = _make_tax_return()
        rule = DeductionConsistencyRule()
        issues = rule.validate(tr, {})
        # Should have no warnings for normal W2 + no itemized
        assert len(issues) == 0

    def test_mortgage_over_50_pct_income_warning(self):
        w2 = _make_w2(wages=100_000)
        income = _make_income(w2_forms=[w2])
        itemized = _make_itemized(mortgage_interest=60_000)
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(income=income, deductions=deductions)
        rule = DeductionConsistencyRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "CON_020" for i in issues)

    def test_salt_over_20_pct_income_warning(self):
        w2 = _make_w2(wages=100_000)
        income = _make_income(w2_forms=[w2])
        itemized = _make_itemized(state_local_income_tax=15_000, real_estate_tax=10_000)
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(income=income, deductions=deductions)
        rule = DeductionConsistencyRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "CON_021" for i in issues)


# ===================================================================
# SALT LIMIT RULE
# ===================================================================

class TestSALTLimitRule:

    def test_rule_code(self):
        rule = SALTLimitRule()
        assert rule.code == "LIM_001"
        assert rule.category == ValidationCategory.LIMIT

    def test_salt_limit_constant(self):
        assert SALTLimitRule.SALT_LIMIT == 10_000

    def test_under_limit_no_issue(self):
        itemized = _make_itemized(state_local_income_tax=5000, real_estate_tax=3000)
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(deductions=deductions)
        rule = SALTLimitRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0

    def test_over_limit_info(self):
        itemized = _make_itemized(
            state_local_income_tax=6000, real_estate_tax=5000,
            state_local_sales_tax=500, personal_property_tax=500,
        )
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(deductions=deductions)
        rule = SALTLimitRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.INFO

    def test_mfs_lower_limit(self):
        itemized = _make_itemized(
            state_local_income_tax=3000, real_estate_tax=3000,
        )
        deductions = _make_deductions(itemized=itemized)
        tp = _make_taxpayer(filing_status=FilingStatus.MARRIED_SEPARATE)
        tr = _make_tax_return(taxpayer=tp, deductions=deductions)
        rule = SALTLimitRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 1  # $6000 > $5000 MFS limit

    @pytest.mark.parametrize("status,limit", [
        (FilingStatus.SINGLE, 10_000),
        (FilingStatus.MARRIED_JOINT, 10_000),
        (FilingStatus.HEAD_OF_HOUSEHOLD, 10_000),
        (FilingStatus.MARRIED_SEPARATE, 5_000),
    ])
    def test_limit_by_filing_status(self, status, limit):
        # Just verify the rule applies correct limits by checking boundary
        itemized = _make_itemized(state_local_income_tax=limit)
        deductions = _make_deductions(itemized=itemized)
        tp = _make_taxpayer(filing_status=status)
        tr = _make_tax_return(taxpayer=tp, deductions=deductions)
        rule = SALTLimitRule()
        issues = rule.validate(tr, {})
        assert len(issues) == 0  # Exactly at limit, should not trigger


# ===================================================================
# RETIREMENT CONTRIBUTION LIMIT RULE
# ===================================================================

class TestRetirementContributionLimitRule:

    def test_rule_code(self):
        rule = RetirementContributionLimitRule()
        assert rule.code == "LIM_010"

    def test_2025_ira_limit(self):
        assert RetirementContributionLimitRule.LIMIT_IRA == 7_000

    def test_2025_ira_catchup(self):
        assert RetirementContributionLimitRule.LIMIT_IRA_CATCHUP == 1_000

    def test_2025_401k_limit(self):
        assert RetirementContributionLimitRule.LIMIT_401K == 23_500

    def test_ira_under_limit_no_issue(self):
        deductions = _make_deductions(ira_contributions=6000)
        tr = _make_tax_return(deductions=deductions)
        rule = RetirementContributionLimitRule()
        issues = rule.validate(tr, {})
        assert not any(i.code == "LIM_011" for i in issues)

    def test_ira_over_limit_error(self):
        deductions = _make_deductions(ira_contributions=8000)
        tr = _make_tax_return(deductions=deductions)
        rule = RetirementContributionLimitRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "LIM_011" for i in issues)

    def test_hsa_over_limit_error(self):
        deductions = _make_deductions(hsa_contributions=10_000)
        tr = _make_tax_return(deductions=deductions)
        rule = RetirementContributionLimitRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "LIM_012" for i in issues)

    def test_hsa_under_limit_no_issue(self):
        deductions = _make_deductions(hsa_contributions=4000)
        tr = _make_tax_return(deductions=deductions)
        rule = RetirementContributionLimitRule()
        issues = rule.validate(tr, {})
        assert not any(i.code == "LIM_012" for i in issues)


# ===================================================================
# CHARITABLE CONTRIBUTION LIMIT RULE
# ===================================================================

class TestCharitableContributionLimitRule:

    def test_rule_code(self):
        rule = CharitableContributionLimitRule()
        assert rule.code == "LIM_020"

    def test_under_60_pct_agi_no_issue(self):
        w2 = _make_w2(wages=100_000)
        income = _make_income(w2_forms=[w2])
        itemized = _make_itemized(charitable_cash=50_000)
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(income=income, deductions=deductions)
        rule = CharitableContributionLimitRule()
        issues = rule.validate(tr, {})
        assert not any(i.code == "LIM_020" for i in issues)

    def test_cash_over_60_pct_agi_warning(self):
        w2 = _make_w2(wages=100_000)
        income = _make_income(w2_forms=[w2])
        itemized = _make_itemized(charitable_cash=70_000)
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(income=income, deductions=deductions)
        rule = CharitableContributionLimitRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "LIM_020" for i in issues)

    def test_non_cash_over_30_pct_agi_warning(self):
        w2 = _make_w2(wages=100_000)
        income = _make_income(w2_forms=[w2])
        itemized = _make_itemized(charitable_non_cash=40_000)
        deductions = _make_deductions(itemized=itemized)
        tr = _make_tax_return(income=income, deductions=deductions)
        rule = CharitableContributionLimitRule()
        issues = rule.validate(tr, {})
        assert any(i.code == "LIM_021" for i in issues)


# ===================================================================
# VALIDATION SERVICE
# ===================================================================

class TestValidationService:

    def test_default_rules_loaded(self):
        svc = ValidationService()
        assert len(svc._rules) == 10

    def test_custom_rules(self):
        svc = ValidationService(rules=[RequiredFieldRule()])
        assert len(svc._rules) == 1

    def test_add_rule(self):
        # Note: ValidationService(rules=[]) falls back to defaults because [] is falsy.
        # Use a single-element list, then add one more.
        svc = ValidationService(rules=[SSNFormatRule()])
        svc.add_rule(RequiredFieldRule())
        assert len(svc._rules) == 2

    def test_remove_rule(self):
        svc = ValidationService()
        result = svc.remove_rule("REQ_001")
        assert result is True
        assert len(svc._rules) == 9

    def test_remove_nonexistent_rule(self):
        svc = ValidationService()
        result = svc.remove_rule("NONEXISTENT")
        assert result is False

    def test_validate_returns_result(self):
        tr = _make_tax_return()
        svc = ValidationService(rules=[RequiredFieldRule()])
        result = svc.validate(tr, {})
        assert isinstance(result, ValidationResult)

    def test_validate_valid_return(self):
        tr = _make_tax_return()
        svc = ValidationService(rules=[RequiredFieldRule()])
        result = svc.validate(tr, {})
        assert result.is_valid is True

    def test_validate_invalid_return(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(first_name=""))
        svc = ValidationService(rules=[RequiredFieldRule()])
        result = svc.validate(tr, {})
        assert result.is_valid is False

    def test_validate_with_category_filter(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(first_name=""))
        svc = ValidationService()
        result = svc.validate(tr, {}, categories={ValidationCategory.FORMAT})
        # Should only run FORMAT rules, not REQUIRED
        assert not any(i.code == "REQ_001" for i in result.issues)

    def test_stop_on_error(self):
        tp = _make_taxpayer(first_name="", last_name="", ssn="")
        tr = _make_tax_return(taxpayer=tp)
        svc = ValidationService(rules=[RequiredFieldRule()])
        result = svc.validate(tr, {}, stop_on_error=True)
        assert result.error_count == 1

    def test_validate_field(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(first_name=""))
        svc = ValidationService(rules=[RequiredFieldRule()])
        issues = svc.validate_field(tr, {}, "taxpayer.first_name")
        assert len(issues) == 1

    def test_validate_field_no_match(self):
        tr = _make_tax_return()
        svc = ValidationService(rules=[RequiredFieldRule()])
        issues = svc.validate_field(tr, {}, "nonexistent.field")
        assert len(issues) == 0

    def test_get_required_fields(self):
        svc = ValidationService()
        fields = svc.get_required_fields()
        assert "taxpayer.first_name" in fields
        assert "taxpayer.last_name" in fields
        assert "taxpayer.ssn" in fields
        assert "taxpayer.filing_status" in fields

    def test_quick_validate_valid(self):
        tr = _make_tax_return()
        svc = ValidationService(rules=[RequiredFieldRule()])
        assert svc.quick_validate(tr, {}) is True

    def test_quick_validate_invalid(self):
        tr = _make_tax_return(taxpayer=_make_taxpayer(first_name=""))
        svc = ValidationService(rules=[RequiredFieldRule()])
        assert svc.quick_validate(tr, {}) is False

    def test_rule_exception_handled(self):
        """Rule that raises exception should not crash the service."""
        bad_rule = Mock(spec=ValidationRule)
        bad_rule.code = "BAD"
        bad_rule.category = ValidationCategory.REQUIRED
        bad_rule.validate.side_effect = Exception("Rule crashed")
        svc = ValidationService(rules=[bad_rule])
        result = svc.validate(_make_tax_return(), {})
        assert result.is_valid is True  # No errors added from crashed rule

    def test_tax_year_from_data(self):
        tr = _make_tax_return()
        svc = ValidationService(rules=[])
        result = svc.validate(tr, {"tax_year": 2024})
        assert result.tax_year == 2024


# ===================================================================
# CREATE VALIDATION SERVICE FACTORY
# ===================================================================

class TestCreateValidationService:

    def test_default_all_rules(self):
        svc = create_validation_service()
        assert len(svc._rules) == 10

    def test_without_limits(self):
        svc = create_validation_service(include_limits=False)
        rule_codes = [r.code for r in svc._rules]
        assert "LIM_001" not in rule_codes
        assert "LIM_010" not in rule_codes

    def test_without_consistency(self):
        svc = create_validation_service(include_consistency=False)
        rule_codes = [r.code for r in svc._rules]
        assert "CON_001" not in rule_codes
        assert "CON_010" not in rule_codes

    def test_minimal_rules(self):
        svc = create_validation_service(include_limits=False, include_consistency=False)
        assert len(svc._rules) == 4  # Required, SSN, Income Range, W2

    @pytest.mark.parametrize("include_limits,include_consistency,expected_count", [
        (True, True, 10),
        (True, False, 7),
        (False, True, 7),
        (False, False, 4),
    ])
    def test_rule_count_combinations(self, include_limits, include_consistency, expected_count):
        svc = create_validation_service(
            include_limits=include_limits,
            include_consistency=include_consistency,
        )
        assert len(svc._rules) == expected_count
