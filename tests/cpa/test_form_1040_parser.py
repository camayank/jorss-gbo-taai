"""
Tests for Form1040Parser and related data structures.

Covers FilingStatus enum, Parsed1040Data dataclass, DependentInfo,
field extraction templates, and the parser itself with various
income combinations, edge cases, and filing statuses.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.services.form_1040_parser import (
    FilingStatus,
    Parsed1040Data,
    DependentInfo,
    Form1040Parser,
    create_1040_templates,
)


# =========================================================================
# FILING STATUS ENUM
# =========================================================================

class TestFilingStatusEnum:
    """Verify FilingStatus members and values."""

    @pytest.mark.parametrize("member,value", [
        (FilingStatus.SINGLE, "single"),
        (FilingStatus.MARRIED_FILING_JOINTLY, "married_filing_jointly"),
        (FilingStatus.MARRIED_FILING_SEPARATELY, "married_filing_separately"),
        (FilingStatus.HEAD_OF_HOUSEHOLD, "head_of_household"),
        (FilingStatus.QUALIFYING_SURVIVING_SPOUSE, "qualifying_surviving_spouse"),
    ])
    def test_filing_status_values(self, member, value):
        assert member.value == value

    def test_filing_status_count(self):
        assert len(FilingStatus) == 5

    @pytest.mark.parametrize("fs", list(FilingStatus))
    def test_filing_status_is_str(self, fs):
        assert isinstance(fs, str)


# =========================================================================
# DEPENDENT INFO
# =========================================================================

class TestDependentInfo:
    """Tests for DependentInfo dataclass."""

    def test_minimal(self):
        dep = DependentInfo(name="Child")
        assert dep.name == "Child"
        assert dep.ssn is None
        assert dep.child_tax_credit is False

    def test_full(self):
        dep = DependentInfo(
            name="Alice Smith",
            ssn="123-45-6789",
            relationship="daughter",
            child_tax_credit=True,
            other_dependent_credit=False,
        )
        assert dep.relationship == "daughter"
        assert dep.child_tax_credit is True

    @pytest.mark.parametrize("relationship", [
        "son", "daughter", "stepchild", "foster child", "sibling", "parent",
    ])
    def test_various_relationships(self, relationship):
        dep = DependentInfo(name="Dep", relationship=relationship)
        assert dep.relationship == relationship


# =========================================================================
# PARSED 1040 DATA
# =========================================================================

class TestParsed1040Data:
    """Tests for Parsed1040Data dataclass defaults, creation, and serialization."""

    def test_defaults(self):
        parsed = Parsed1040Data()
        assert parsed.tax_year == 2024
        assert parsed.taxpayer_name is None
        assert parsed.filing_status is None
        assert parsed.wages_salaries_tips is None
        assert parsed.total_dependents == 0
        assert parsed.dependents == []
        assert parsed.fields_missing == []
        assert parsed.warnings == []
        assert parsed.extraction_confidence == 0.0

    def test_full_creation(self, parsed_1040_single):
        assert parsed_1040_single.taxpayer_name == "Jane Doe"
        assert parsed_1040_single.filing_status == FilingStatus.SINGLE
        assert parsed_1040_single.wages_salaries_tips == Decimal("85000")
        assert parsed_1040_single.extraction_confidence == 92.0

    def test_mfj_with_dependents(self, parsed_1040_mfj):
        assert parsed_1040_mfj.filing_status == FilingStatus.MARRIED_FILING_JOINTLY
        assert parsed_1040_mfj.total_dependents == 2
        assert len(parsed_1040_mfj.dependents) == 2
        assert parsed_1040_mfj.spouse_name == "Mary Smith"

    def test_to_dict_structure(self, parsed_1040_single):
        d = parsed_1040_single.to_dict()
        expected_top_keys = {
            "tax_year", "personal_info", "filing_status",
            "dependents", "income", "adjustments", "deductions",
            "tax_and_credits", "payments", "refund_or_owed",
            "extraction_metadata",
        }
        assert set(d.keys()) == expected_top_keys

    def test_to_dict_income_section(self, parsed_1040_single):
        d = parsed_1040_single.to_dict()
        assert d["income"]["wages_salaries_tips"] == 85000.0
        assert d["income"]["total_income"] == 87000.0

    def test_to_dict_filing_status_string(self, parsed_1040_single):
        d = parsed_1040_single.to_dict()
        assert d["filing_status"] == "single"

    def test_to_dict_none_filing_status(self):
        parsed = Parsed1040Data()
        d = parsed.to_dict()
        assert d["filing_status"] is None

    def test_to_dict_dependents_section(self, parsed_1040_mfj):
        d = parsed_1040_mfj.to_dict()
        assert d["dependents"]["count"] == 2
        assert len(d["dependents"]["details"]) == 2
        assert d["dependents"]["details"][0]["name"] == "Alice Smith"
        assert d["dependents"]["details"][0]["child_tax_credit"] is True

    def test_to_dict_deductions(self, parsed_1040_single):
        d = parsed_1040_single.to_dict()
        assert d["deductions"]["standard_deduction"] == 14600.0
        assert d["deductions"]["taxable_income"] == 70400.0

    def test_to_dict_refund(self, parsed_1040_single):
        d = parsed_1040_single.to_dict()
        assert d["refund_or_owed"]["refund_amount"] == 732.0

    def test_to_dict_extraction_metadata(self, parsed_1040_single):
        d = parsed_1040_single.to_dict()
        assert d["extraction_metadata"]["confidence"] == 92.0
        assert d["extraction_metadata"]["fields_extracted"] == 18

    def test_to_dict_none_values_are_none(self):
        parsed = Parsed1040Data()
        d = parsed.to_dict()
        assert d["income"]["wages_salaries_tips"] is None
        assert d["income"]["capital_gain_or_loss"] is None
        assert d["adjustments"]["adjusted_gross_income"] is None

    @pytest.mark.parametrize("fs", list(FilingStatus))
    def test_to_dict_each_filing_status(self, fs):
        parsed = Parsed1040Data(filing_status=fs)
        d = parsed.to_dict()
        assert d["filing_status"] == fs.value


# =========================================================================
# INCOME COMBINATIONS
# =========================================================================

class TestIncomeCombinations:
    """Test Parsed1040Data with various income field combinations."""

    def test_wages_only(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("50000"),
            total_income=Decimal("50000"),
            adjusted_gross_income=Decimal("50000"),
        )
        d = parsed.to_dict()
        assert d["income"]["wages_salaries_tips"] == 50000.0

    def test_wages_plus_interest(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("50000"),
            taxable_interest=Decimal("500"),
            total_income=Decimal("50500"),
        )
        d = parsed.to_dict()
        assert d["income"]["taxable_interest"] == 500.0

    def test_wages_plus_dividends(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("80000"),
            qualified_dividends=Decimal("2000"),
            ordinary_dividends=Decimal("3000"),
        )
        d = parsed.to_dict()
        assert d["income"]["qualified_dividends"] == 2000.0
        assert d["income"]["ordinary_dividends"] == 3000.0

    def test_wages_plus_capital_gains(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("90000"),
            capital_gain_or_loss=Decimal("15000"),
        )
        d = parsed.to_dict()
        assert d["income"]["capital_gain_or_loss"] == 15000.0

    def test_all_income_types(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("80000"),
            tax_exempt_interest=Decimal("100"),
            taxable_interest=Decimal("500"),
            qualified_dividends=Decimal("1000"),
            ordinary_dividends=Decimal("1500"),
            ira_distributions=Decimal("5000"),
            ira_taxable_amount=Decimal("5000"),
            pensions_annuities=Decimal("12000"),
            pensions_taxable=Decimal("10000"),
            social_security=Decimal("18000"),
            social_security_taxable=Decimal("15300"),
            capital_gain_or_loss=Decimal("3000"),
            other_income=Decimal("2000"),
            total_income=Decimal("117300"),
        )
        d = parsed.to_dict()
        for key in ["wages_salaries_tips", "taxable_interest", "qualified_dividends",
                     "ordinary_dividends", "ira_distributions", "capital_gain_or_loss",
                     "other_income", "total_income"]:
            assert d["income"][key] is not None

    def test_negative_capital_loss(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("80000"),
            capital_gain_or_loss=Decimal("-3000"),
        )
        d = parsed.to_dict()
        assert d["income"]["capital_gain_or_loss"] == -3000.0

    @pytest.mark.parametrize("agi", [
        Decimal("0"), Decimal("1"), Decimal("12000"),
        Decimal("50000"), Decimal("100000"), Decimal("500000"),
        Decimal("1000000"), Decimal("10000000"),
    ])
    def test_various_agi_levels(self, agi):
        parsed = Parsed1040Data(adjusted_gross_income=agi)
        d = parsed.to_dict()
        assert d["adjustments"]["adjusted_gross_income"] == float(agi)

    def test_zero_income(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("0"),
            total_income=Decimal("0"),
            adjusted_gross_income=Decimal("0"),
            taxable_income=Decimal("0"),
            total_tax=Decimal("0"),
        )
        d = parsed.to_dict()
        assert d["income"]["total_income"] == 0.0
        assert d["tax_and_credits"]["total_tax"] == 0.0

    def test_very_high_income(self):
        parsed = Parsed1040Data(
            wages_salaries_tips=Decimal("5000000"),
            adjusted_gross_income=Decimal("5000000"),
        )
        d = parsed.to_dict()
        assert d["income"]["wages_salaries_tips"] == 5000000.0


# =========================================================================
# DEDUCTION SCENARIOS
# =========================================================================

class TestDeductionScenarios:
    """Test standard vs itemized deduction scenarios."""

    def test_standard_deduction(self):
        parsed = Parsed1040Data(
            standard_deduction=Decimal("14600"),
            total_deductions=Decimal("14600"),
        )
        d = parsed.to_dict()
        assert d["deductions"]["standard_deduction"] == 14600.0
        assert d["deductions"]["itemized_deductions"] is None

    def test_itemized_deduction(self):
        parsed = Parsed1040Data(
            itemized_deductions=Decimal("22000"),
            total_deductions=Decimal("22000"),
        )
        d = parsed.to_dict()
        assert d["deductions"]["itemized_deductions"] == 22000.0
        assert d["deductions"]["standard_deduction"] is None

    def test_qbi_deduction(self):
        parsed = Parsed1040Data(
            qualified_business_deduction=Decimal("5000"),
        )
        d = parsed.to_dict()
        assert d["deductions"]["qualified_business_deduction"] == 5000.0


# =========================================================================
# CREDITS AND PAYMENTS
# =========================================================================

class TestCreditsAndPayments:
    """Test credits and payment fields."""

    def test_child_tax_credit(self):
        parsed = Parsed1040Data(child_tax_credit=Decimal("4000"))
        d = parsed.to_dict()
        assert d["tax_and_credits"]["child_tax_credit"] == 4000.0

    def test_earned_income_credit(self):
        parsed = Parsed1040Data(earned_income_credit=Decimal("3000"))
        d = parsed.to_dict()
        assert d["payments"]["earned_income_credit"] == 3000.0

    def test_american_opportunity_credit(self):
        parsed = Parsed1040Data(american_opportunity_credit=Decimal("2500"))
        d = parsed.to_dict()
        assert d["payments"]["american_opportunity_credit"] == 2500.0

    def test_estimated_tax_payments(self):
        parsed = Parsed1040Data(estimated_tax_payments=Decimal("8000"))
        d = parsed.to_dict()
        assert d["payments"]["estimated_tax_payments"] == 8000.0

    def test_refund_vs_owed(self):
        parsed_refund = Parsed1040Data(refund_amount=Decimal("1500"))
        parsed_owed = Parsed1040Data(amount_owed=Decimal("2000"))
        assert parsed_refund.to_dict()["refund_or_owed"]["refund_amount"] == 1500.0
        assert parsed_owed.to_dict()["refund_or_owed"]["amount_owed"] == 2000.0


# =========================================================================
# MISSING FIELDS AND WARNINGS
# =========================================================================

class TestMetadata:
    """Test extraction metadata fields."""

    def test_fields_missing_tracked(self):
        parsed = Parsed1040Data(
            fields_missing=["wages_salaries_tips", "total_income"],
        )
        assert len(parsed.fields_missing) == 2

    def test_warnings_tracked(self):
        parsed = Parsed1040Data(
            warnings=["Low confidence on line 1", "SSN format issue"],
        )
        assert len(parsed.warnings) == 2

    def test_fields_extracted_count(self):
        parsed = Parsed1040Data(fields_extracted=15)
        d = parsed.to_dict()
        assert d["extraction_metadata"]["fields_extracted"] == 15

    @pytest.mark.parametrize("confidence", [0.0, 25.0, 50.0, 75.0, 90.0, 100.0])
    def test_various_confidence_levels(self, confidence):
        parsed = Parsed1040Data(extraction_confidence=confidence)
        d = parsed.to_dict()
        assert d["extraction_metadata"]["confidence"] == confidence


# =========================================================================
# 1040 FIELD TEMPLATES
# =========================================================================

class TestCreate1040Templates:
    """Tests for create_1040_templates."""

    def test_templates_returned(self):
        templates = create_1040_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_templates_have_required_fields(self):
        templates = create_1040_templates()
        for t in templates:
            assert hasattr(t, "field_name")
            assert hasattr(t, "field_label")
            assert hasattr(t, "patterns")

    def test_key_fields_present(self):
        templates = create_1040_templates()
        field_names = {t.field_name for t in templates}
        required = {
            "tax_year", "taxpayer_name", "filing_status",
            "wages_salaries_tips", "adjusted_gross_income",
            "total_tax", "federal_withholding",
        }
        assert required.issubset(field_names)

    def test_template_patterns_are_lists(self):
        import re
        templates = create_1040_templates()
        for t in templates:
            assert isinstance(t.patterns, list)
            # After __post_init__, patterns are compiled regex objects, not strings
            assert all(isinstance(p, re.Pattern) for p in t.patterns)

    @pytest.mark.parametrize("field_name", [
        "wages_salaries_tips", "taxable_interest", "qualified_dividends",
        "ordinary_dividends", "ira_distributions", "pensions_annuities",
        "social_security", "capital_gain_or_loss", "total_income",
        "adjusted_gross_income", "standard_deduction", "taxable_income",
        "total_tax", "federal_withholding", "refund_amount", "amount_owed",
    ])
    def test_income_and_tax_templates_exist(self, field_name):
        templates = create_1040_templates()
        field_names = {t.field_name for t in templates}
        assert field_name in field_names


# =========================================================================
# FORM 1040 PARSER
# =========================================================================

class TestForm1040Parser:
    """Tests for Form1040Parser class."""

    @pytest.fixture(autouse=True)
    def setup_parser(self):
        with patch("cpa_panel.services.form_1040_parser.FieldExtractor") as MockExtractor:
            self.mock_extractor = MockExtractor.return_value
            self.parser = Form1040Parser()

    def _make_mock_ocr_result(self, confidence=85.0):
        mock_result = MagicMock()
        mock_result.confidence = confidence
        mock_result.raw_text = "Form 1040 2024"
        return mock_result

    def _make_extracted_field(self, field_name, value, is_valid=True):
        field = MagicMock()
        field.field_name = field_name
        field.normalized_value = value
        field.is_valid = is_valid
        field.validation_errors = [] if is_valid else ["validation error"]
        return field

    def test_parse_returns_parsed_data(self):
        self.mock_extractor.extract.return_value = []
        result = self.parser.parse(self._make_mock_ocr_result())
        assert isinstance(result, Parsed1040Data)

    def test_parse_sets_confidence(self):
        self.mock_extractor.extract.return_value = []
        result = self.parser.parse(self._make_mock_ocr_result(confidence=92.5))
        assert result.extraction_confidence == 92.5

    def test_parse_maps_taxpayer_name(self):
        fields = [self._make_extracted_field("taxpayer_name", "John Doe")]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.taxpayer_name == "John Doe"

    def test_parse_maps_wages(self):
        fields = [self._make_extracted_field("wages_salaries_tips", Decimal("75000"))]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.wages_salaries_tips == Decimal("75000")

    def test_parse_maps_agi(self):
        fields = [self._make_extracted_field("adjusted_gross_income", Decimal("85000"))]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.adjusted_gross_income == Decimal("85000")

    def test_parse_maps_tax_year(self):
        fields = [self._make_extracted_field("tax_year", 2024)]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.tax_year == 2024

    def test_parse_maps_dependents(self):
        fields = [self._make_extracted_field("total_dependents", 3)]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.total_dependents == 3

    @pytest.mark.parametrize("raw_status,expected_fs", [
        ("Single", FilingStatus.SINGLE),
        ("single", FilingStatus.SINGLE),
        ("1", FilingStatus.SINGLE),
        ("Married filing jointly", FilingStatus.MARRIED_FILING_JOINTLY),
        ("MFJ", FilingStatus.MARRIED_FILING_JOINTLY),
        ("2", FilingStatus.MARRIED_FILING_JOINTLY),
        ("Married filing separately", FilingStatus.MARRIED_FILING_SEPARATELY),
        ("MFS", FilingStatus.MARRIED_FILING_SEPARATELY),
        ("3", FilingStatus.MARRIED_FILING_SEPARATELY),
        ("Head of household", FilingStatus.HEAD_OF_HOUSEHOLD),
        ("HOH", FilingStatus.HEAD_OF_HOUSEHOLD),
        ("4", FilingStatus.HEAD_OF_HOUSEHOLD),
        ("Qualifying surviving spouse", FilingStatus.QUALIFYING_SURVIVING_SPOUSE),
        ("5", FilingStatus.QUALIFYING_SURVIVING_SPOUSE),
    ])
    def test_filing_status_parsing(self, raw_status, expected_fs):
        fields = [self._make_extracted_field("filing_status", raw_status)]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.filing_status == expected_fs

    def test_missing_required_fields_tracked(self):
        self.mock_extractor.extract.return_value = []
        result = self.parser.parse(self._make_mock_ocr_result())
        assert "taxpayer_name" in result.fields_missing
        assert "wages_salaries_tips" in result.fields_missing
        assert "adjusted_gross_income" in result.fields_missing

    def test_fields_extracted_count(self):
        fields = [
            self._make_extracted_field("taxpayer_name", "John"),
            self._make_extracted_field("wages_salaries_tips", Decimal("50000")),
            self._make_extracted_field("total_income", None),  # not extracted
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.fields_extracted == 2

    def test_validation_warnings_captured(self):
        bad_field = self._make_extracted_field("wages_salaries_tips", Decimal("-1"), is_valid=False)
        self.mock_extractor.extract.return_value = [bad_field]
        result = self.parser.parse(self._make_mock_ocr_result())
        assert len(result.warnings) > 0

    def test_parse_all_income_fields(self):
        income_fields = [
            ("wages_salaries_tips", Decimal("80000")),
            ("tax_exempt_interest", Decimal("100")),
            ("taxable_interest", Decimal("500")),
            ("qualified_dividends", Decimal("1000")),
            ("ordinary_dividends", Decimal("1500")),
            ("ira_distributions", Decimal("5000")),
            ("ira_taxable_amount", Decimal("5000")),
            ("pensions_annuities", Decimal("12000")),
            ("pensions_taxable", Decimal("10000")),
            ("social_security", Decimal("18000")),
            ("social_security_taxable", Decimal("15300")),
            ("capital_gain_or_loss", Decimal("3000")),
            ("other_income", Decimal("2000")),
            ("total_income", Decimal("127300")),
        ]
        fields = [self._make_extracted_field(name, val) for name, val in income_fields]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.wages_salaries_tips == Decimal("80000")
        assert result.total_income == Decimal("127300")
        assert result.capital_gain_or_loss == Decimal("3000")

    def test_parse_deduction_fields(self):
        fields = [
            self._make_extracted_field("standard_deduction", Decimal("14600")),
            self._make_extracted_field("total_deductions", Decimal("14600")),
            self._make_extracted_field("taxable_income", Decimal("70400")),
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.standard_deduction == Decimal("14600")
        assert result.taxable_income == Decimal("70400")

    def test_parse_payment_fields(self):
        fields = [
            self._make_extracted_field("federal_withholding", Decimal("12000")),
            self._make_extracted_field("estimated_tax_payments", Decimal("3000")),
            self._make_extracted_field("earned_income_credit", Decimal("500")),
            self._make_extracted_field("total_payments", Decimal("15500")),
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.federal_withholding == Decimal("12000")
        assert result.total_payments == Decimal("15500")

    def test_parse_refund_fields(self):
        fields = [
            self._make_extracted_field("overpaid", Decimal("1500")),
            self._make_extracted_field("refund_amount", Decimal("1500")),
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.refund_amount == Decimal("1500")

    def test_parse_amount_owed(self):
        fields = [
            self._make_extracted_field("amount_owed", Decimal("2500")),
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.amount_owed == Decimal("2500")

    def test_parse_spouse_info(self):
        fields = [
            self._make_extracted_field("spouse_name", "Mary Smith"),
            self._make_extracted_field("spouse_ssn", "987-65-4321"),
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.spouse_name == "Mary Smith"
        assert result.spouse_ssn == "987-65-4321"

    def test_parse_ssn(self):
        fields = [
            self._make_extracted_field("taxpayer_ssn", "123-45-6789"),
        ]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.taxpayer_ssn == "123-45-6789"

    @pytest.mark.parametrize("confidence", [0.0, 25.0, 50.0, 75.0, 95.0, 100.0])
    def test_various_ocr_confidence(self, confidence):
        self.mock_extractor.extract.return_value = []
        result = self.parser.parse(self._make_mock_ocr_result(confidence))
        assert result.extraction_confidence == confidence

    def test_null_normalized_value_skipped(self):
        fields = [self._make_extracted_field("wages_salaries_tips", None)]
        self.mock_extractor.extract.return_value = fields
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.wages_salaries_tips is None

    def test_no_fields_extracted(self):
        self.mock_extractor.extract.return_value = []
        result = self.parser.parse(self._make_mock_ocr_result())
        assert result.fields_extracted == 0
        assert len(result.fields_missing) > 0


# =========================================================================
# EDGE CASES
# =========================================================================

class TestForm1040ParserEdgeCases:
    """Edge cases for the parser."""

    @pytest.fixture(autouse=True)
    def setup_parser(self):
        with patch("cpa_panel.services.form_1040_parser.FieldExtractor"):
            self.parser = Form1040Parser()

    def test_parse_from_text_creates_mock_ocr(self):
        """parse_from_text should delegate to parse with a mock OCR result."""
        with patch.object(self.parser, "parse") as mock_parse, \
             patch("cpa_panel.services.form_1040_parser.OCRResult") as MockOCRResult:
            mock_ocr_instance = MagicMock()
            mock_ocr_instance.raw_text = "some raw text"
            mock_ocr_instance.confidence = 80.0
            MockOCRResult.return_value = mock_ocr_instance

            mock_parse.return_value = Parsed1040Data()
            result = self.parser.parse_from_text("some raw text", confidence=80.0)
            mock_parse.assert_called_once()
            ocr_arg = mock_parse.call_args[0][0]
            assert ocr_arg.raw_text == "some raw text"
            assert ocr_arg.confidence == 80.0

    def test_filing_status_none_not_set(self):
        """If filing_status field not extracted, parsed.filing_status stays None."""
        self.parser.extractor.extract.return_value = []
        result = self.parser.parse(MagicMock(confidence=80.0))
        assert result.filing_status is None
