"""Tests for OCR inference engine module."""

import pytest
from decimal import Decimal

from src.services.ocr.inference_engine import (
    FieldInferenceEngine,
    InferenceResult,
    InferredField,
    InferenceType,
    ValidationIssue,
    MultiDocumentInference,
    infer_document_fields,
    aggregate_multi_document_income,
)


class TestFieldInferenceEngine:
    """Tests for FieldInferenceEngine class."""

    def test_initialization(self):
        """Test engine initializes correctly."""
        engine = FieldInferenceEngine(tax_year=2024)
        assert engine.tax_year == 2024
        assert "ss_wage_base_2024" in engine.TAX_CONSTANTS

    def test_initialization_different_year(self):
        """Test engine with different tax year."""
        engine = FieldInferenceEngine(tax_year=2025)
        assert engine.tax_year == 2025
        assert "ss_wage_base_2025" in engine.TAX_CONSTANTS


class TestW2Inference:
    """Tests for W-2 field inference."""

    def test_infer_ss_wages_from_wages(self):
        """Test inferring SS wages when only wages provided."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "75000.00",
                "federal_tax_withheld": "10000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        # Should infer SS wages
        ss_wages_inferred = next(
            (f for f in result.inferred_fields if f.field_name == "social_security_wages"),
            None
        )
        assert ss_wages_inferred is not None
        assert ss_wages_inferred.inference_type == InferenceType.CALCULATED
        assert float(ss_wages_inferred.inferred_value) == 75000.0

    def test_infer_ss_wages_capped_at_wage_base(self):
        """Test SS wages capped at wage base for high earners."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "250000.00",
                "federal_tax_withheld": "50000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        ss_wages_inferred = next(
            (f for f in result.inferred_fields if f.field_name == "social_security_wages"),
            None
        )
        assert ss_wages_inferred is not None
        # Should be capped at wage base
        assert float(ss_wages_inferred.inferred_value) == 168600.0
        assert ss_wages_inferred.requires_confirmation == True

    def test_infer_ss_tax_from_ss_wages(self):
        """Test inferring SS tax from SS wages."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "50000.00",
                "social_security_wages": "50000.00",
                "federal_tax_withheld": "5000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        ss_tax_inferred = next(
            (f for f in result.inferred_fields if f.field_name == "social_security_tax"),
            None
        )
        assert ss_tax_inferred is not None
        # 50000 * 6.2% = 3100
        assert float(ss_tax_inferred.inferred_value) == 3100.00

    def test_infer_medicare_wages_from_wages(self):
        """Test inferring Medicare wages from wages."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "100000.00",
                "federal_tax_withheld": "15000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        medicare_inferred = next(
            (f for f in result.inferred_fields if f.field_name == "medicare_wages"),
            None
        )
        assert medicare_inferred is not None
        # Medicare wages should equal wages (no cap)
        assert float(medicare_inferred.inferred_value) == 100000.0

    def test_infer_medicare_tax_from_medicare_wages(self):
        """Test inferring Medicare tax from Medicare wages."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "100000.00",
                "medicare_wages": "100000.00",
                "federal_tax_withheld": "15000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        medicare_tax = next(
            (f for f in result.inferred_fields if f.field_name == "medicare_tax"),
            None
        )
        assert medicare_tax is not None
        # 100000 * 1.45% = 1450
        assert float(medicare_tax.inferred_value) == 1450.00


class TestW2Validation:
    """Tests for W-2 field validation."""

    def test_validate_ss_tax_matches_expected(self):
        """Test validation catches SS tax mismatch."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "50000.00",
                "social_security_wages": "50000.00",
                "social_security_tax": "5000.00",  # Wrong! Should be ~3100
                "federal_tax_withheld": "5000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        # Should have a validation warning
        ss_issue = next(
            (v for v in result.validation_issues if v.field_name == "social_security_tax"),
            None
        )
        assert ss_issue is not None
        assert ss_issue.severity == "warning"

    def test_validate_withholding_exceeds_50_percent(self):
        """Test validation catches excessive withholding."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "50000.00",
                "federal_tax_withheld": "30000.00",  # 60% - way too high
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        withholding_issue = next(
            (v for v in result.validation_issues if v.field_name == "federal_tax_withheld"),
            None
        )
        assert withholding_issue is not None
        assert withholding_issue.severity == "error"

    def test_validate_ss_wages_exceeds_base(self):
        """Test validation catches SS wages over wage base."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "200000.00",
                "social_security_wages": "200000.00",  # Over $168,600 base
                "federal_tax_withheld": "40000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        ss_wages_issue = next(
            (v for v in result.validation_issues if v.field_name == "social_security_wages"),
            None
        )
        assert ss_wages_issue is not None
        assert ss_wages_issue.severity == "error"


class Test1099Inference:
    """Tests for 1099 field inference."""

    def test_infer_qualified_dividends(self):
        """Test inferring qualified dividends from ordinary."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="1099_div",
            extracted_fields={
                "payer_name": "Vanguard",
                "ordinary_dividends": "5000.00",
            },
        )

        qualified_inferred = next(
            (f for f in result.inferred_fields if f.field_name == "qualified_dividends"),
            None
        )
        assert qualified_inferred is not None
        assert qualified_inferred.inference_type == InferenceType.ESTIMATED
        # Should be ~80% estimate
        assert float(qualified_inferred.inferred_value) == 4000.00
        assert qualified_inferred.requires_confirmation == True

    def test_validate_qualified_exceeds_ordinary(self):
        """Test validation catches qualified > ordinary."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="1099_div",
            extracted_fields={
                "payer_name": "Fidelity",
                "ordinary_dividends": "3000.00",
                "qualified_dividends": "5000.00",  # Wrong! Can't exceed ordinary
            },
        )

        issue = next(
            (v for v in result.validation_issues if v.field_name == "qualified_dividends"),
            None
        )
        assert issue is not None
        assert issue.severity == "error"


class TestInferenceResult:
    """Tests for InferenceResult structure."""

    def test_complete_document(self):
        """Test result for complete document."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "75000.00",
                "federal_tax_withheld": "10000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        assert result.document_complete or len(result.missing_required) == 0
        assert result.completion_percentage >= 80
        assert result.can_proceed == True

    def test_incomplete_document(self):
        """Test result for incomplete document."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "75000.00",
                # Missing: federal_tax_withheld, employee_ssn, employer_ein
            },
        )

        assert len(result.missing_required) > 0
        assert result.document_complete == False

    def test_to_dict_serializable(self):
        """Test result can be serialized to dict."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "50000.00",
                "federal_tax_withheld": "5000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "inferred_fields" in result_dict
        assert "validation_issues" in result_dict
        assert "can_proceed" in result_dict


class TestFilingStatusInference:
    """Tests for filing status inference."""

    def test_infer_mfj_with_spouse(self):
        """Test inferring MFJ when spouse info present."""
        engine = FieldInferenceEngine(tax_year=2024)
        status, confidence, explanation = engine.infer_filing_status(
            fields={"spouse_ssn": "987-65-4321"},
        )

        assert status == "married_joint"
        assert confidence >= 70

    def test_infer_hoh_with_dependents(self):
        """Test inferring HOH with dependents but no spouse."""
        engine = FieldInferenceEngine(tax_year=2024)
        status, confidence, explanation = engine.infer_filing_status(
            fields={"dependents": [{"name": "Child"}]},
        )

        assert status == "head_of_household"

    def test_infer_prior_year_status(self):
        """Test using prior year status."""
        engine = FieldInferenceEngine(tax_year=2024)
        status, confidence, explanation = engine.infer_filing_status(
            fields={},
            prior_year_status="married_joint",
        )

        assert status == "married_joint"
        assert confidence >= 60

    def test_default_to_single(self):
        """Test defaulting to single when no info."""
        engine = FieldInferenceEngine(tax_year=2024)
        status, confidence, explanation = engine.infer_filing_status(fields={})

        assert status == "single"
        assert confidence <= 60


class TestDeductionTypeInference:
    """Tests for deduction type inference."""

    def test_recommend_standard_deduction(self):
        """Test recommending standard when itemized is lower."""
        engine = FieldInferenceEngine(tax_year=2024)
        deduction_type, confidence, explanation = engine.infer_deduction_type(
            extracted_fields={
                "mortgage_interest": "5000",
                "property_tax": "3000",
            },
            filing_status="single",
        )

        # $8000 itemized < $14,600 standard
        assert deduction_type == "standard"
        assert confidence >= 85

    def test_recommend_itemized_deduction(self):
        """Test recommending itemized when higher."""
        engine = FieldInferenceEngine(tax_year=2024)
        deduction_type, confidence, explanation = engine.infer_deduction_type(
            extracted_fields={
                "mortgage_interest": "15000",
                "property_tax": "8000",
                "charitable_contributions": "5000",
            },
            filing_status="single",
        )

        # Would exceed standard deduction
        assert deduction_type == "itemized"
        assert "saves" in explanation.lower()


class TestMultiDocumentInference:
    """Tests for multi-document inference."""

    def test_aggregate_multiple_w2s(self):
        """Test aggregating income from multiple W-2s."""
        engine = MultiDocumentInference(tax_year=2024)
        documents = [
            {
                "type": "w2",
                "fields": {
                    "wages": "50000",
                    "federal_tax_withheld": "7000",
                },
            },
            {
                "type": "w2",
                "fields": {
                    "wages": "30000",
                    "federal_tax_withheld": "4000",
                },
            },
        ]

        result = engine.aggregate_income(documents)

        assert result["total_wages"] == 80000
        assert result["total_federal_withheld"] == 11000
        assert result["w2_count"] == 2

    def test_aggregate_w2_and_1099(self):
        """Test aggregating W-2 and 1099 income."""
        engine = MultiDocumentInference(tax_year=2024)
        documents = [
            {
                "type": "w2",
                "fields": {
                    "wages": "60000",
                    "federal_tax_withheld": "8000",
                },
            },
            {
                "type": "1099_int",
                "fields": {
                    "interest_income": "500",
                },
            },
            {
                "type": "1099_div",
                "fields": {
                    "ordinary_dividends": "1000",
                    "qualified_dividends": "800",
                },
            },
        ]

        result = engine.aggregate_income(documents)

        assert result["total_wages"] == 60000
        assert result["total_interest"] == 500
        assert result["total_dividends"] == 1000
        assert result["estimated_agi"] == 61500  # 60000 + 500 + 1000

    def test_detect_self_employment(self):
        """Test detecting self-employment income."""
        engine = MultiDocumentInference(tax_year=2024)
        documents = [
            {
                "type": "w2",
                "fields": {"wages": "50000"},
            },
            {
                "type": "1099_nec",
                "fields": {"nonemployee_compensation": "10000"},
            },
        ]

        result = engine.aggregate_income(documents)

        assert result["has_self_employment"] == True
        assert result["total_nec_income"] == 10000

    def test_validate_duplicate_w2(self):
        """Test detecting duplicate W-2s."""
        engine = MultiDocumentInference(tax_year=2024)
        documents = [
            {
                "type": "w2",
                "fields": {
                    "wages": "50000",
                    "employer_ein": "12-3456789",
                },
            },
            {
                "type": "w2",
                "fields": {
                    "wages": "50000",
                    "employer_ein": "12-3456789",  # Same EIN
                },
            },
        ]

        issues = engine.validate_cross_document(documents)

        # Should warn about duplicate
        duplicate_issue = next(
            (v for v in issues if "duplicate" in v.message.lower()),
            None
        )
        assert duplicate_issue is not None

    def test_validate_total_ss_wages_over_base(self):
        """Test detecting total SS wages over wage base."""
        engine = MultiDocumentInference(tax_year=2024)
        documents = [
            {
                "type": "w2",
                "fields": {
                    "social_security_wages": "100000",
                    "employer_ein": "12-3456789",
                },
            },
            {
                "type": "w2",
                "fields": {
                    "social_security_wages": "100000",
                    "employer_ein": "98-7654321",  # Different employer
                },
            },
        ]

        issues = engine.validate_cross_document(documents)

        # Should note overpaid SS tax
        ss_issue = next(
            (v for v in issues if "exceed" in v.message.lower()),
            None
        )
        assert ss_issue is not None
        assert ss_issue.severity == "info"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_infer_document_fields(self):
        """Test convenience function for document inference."""
        result = infer_document_fields(
            document_type="w2",
            fields={
                "wages": "50000",
                "federal_tax_withheld": "5000",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        assert isinstance(result, InferenceResult)
        assert result.can_proceed == True

    def test_aggregate_multi_document_income(self):
        """Test convenience function for income aggregation."""
        documents = [
            {"type": "w2", "fields": {"wages": "60000"}},
            {"type": "1099_int", "fields": {"interest_income": "100"}},
        ]

        result = aggregate_multi_document_income(documents)

        assert result["total_wages"] == 60000
        assert result["total_interest"] == 100


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_fields(self):
        """Test handling empty fields dict."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={},
        )

        assert len(result.missing_required) == 4
        assert result.can_proceed == False

    def test_invalid_values(self):
        """Test handling invalid values."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "invalid",
                "federal_tax_withheld": "5000.00",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        # Should still process what it can
        assert result is not None

    def test_negative_values(self):
        """Test handling negative values."""
        engine = FieldInferenceEngine(tax_year=2024)
        result = engine.infer_and_validate(
            document_type="w2",
            extracted_fields={
                "wages": "-5000",  # Invalid negative wages
                "federal_tax_withheld": "0",
                "employee_ssn": "123-45-6789",
                "employer_ein": "12-3456789",
            },
        )

        # Should process but may have issues
        assert result is not None
