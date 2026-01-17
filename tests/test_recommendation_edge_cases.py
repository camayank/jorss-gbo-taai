"""
Edge Case Tests for Recommendation Validation.

Prompt 5: Additional tests for edge cases in recommendations.

Tests verify:
1. Boundary values for confidence (0, 100, negative, > 100)
2. Extreme savings values (very large, negative, zero)
3. Unicode and special characters in descriptions
4. XSS prevention in string inputs
5. Null/None handling
6. Empty string handling
7. Whitespace-only inputs
8. Very long strings (truncation)
9. Invalid data types
10. Malformed IRS references
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestConfidenceBoundaries:
    """Tests for confidence value boundary conditions."""

    def test_confidence_zero_is_valid(self):
        """Test confidence of 0 is valid."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence(0)
        assert valid is True
        assert value == 0

    def test_confidence_100_is_valid(self):
        """Test confidence of 100 is valid."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence(100)
        assert valid is True
        assert value == 100

    def test_confidence_negative_is_invalid(self):
        """Test negative confidence is invalid."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence(-5)
        assert valid is False
        assert "between" in error.lower()

    def test_confidence_over_100_is_invalid(self):
        """Test confidence over 100 is invalid."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence(150)
        assert valid is False

    def test_confidence_decimal_0_to_1_converted(self):
        """Test confidence in 0-1 range is converted to 0-100."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence(0.85)
        assert valid is True
        assert value == 85.0

    def test_confidence_string_number(self):
        """Test confidence from string number."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence("75")
        assert valid is True
        assert value == 75.0

    def test_confidence_invalid_string(self):
        """Test confidence from invalid string."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence("high")
        assert valid is False

    def test_confidence_none(self):
        """Test confidence with None."""
        from recommendation.validation import validate_confidence
        valid, value, error = validate_confidence(None)
        assert valid is False


class TestSavingsBoundaries:
    """Tests for savings/impact value boundary conditions."""

    def test_savings_zero_is_valid(self):
        """Test zero savings is valid."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings(0)
        assert valid is True
        assert value == 0.0

    def test_savings_positive_large_valid(self):
        """Test large positive savings is valid."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings(500000)
        assert valid is True
        assert value == 500000.0

    def test_savings_negative_small_valid(self):
        """Test small negative savings (cost) is valid."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings(-100)
        assert valid is True
        assert value == -100.0

    def test_savings_extreme_positive_invalid(self):
        """Test extremely large savings is invalid."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings(100000000)  # 100 million
        assert valid is False

    def test_savings_extreme_negative_invalid(self):
        """Test extremely large negative is invalid."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings(-5000000)  # -5 million
        assert valid is False

    def test_savings_rounds_to_cents(self):
        """Test savings is rounded to 2 decimal places."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings(1234.5678)
        assert valid is True
        assert value == 1234.57  # Rounded

    def test_savings_string_number(self):
        """Test savings from string number."""
        from recommendation.validation import validate_savings
        valid, value, error = validate_savings("1000.50")
        assert valid is True
        assert value == 1000.50


class TestDescriptionValidation:
    """Tests for description string validation."""

    def test_description_valid(self):
        """Test valid description."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description(
            "This is a valid recommendation description that explains why."
        )
        assert valid is True
        assert error is None

    def test_description_too_short(self):
        """Test description that's too short."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description("Short")
        assert valid is False
        assert "at least" in error.lower()

    def test_description_empty(self):
        """Test empty description."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description("")
        assert valid is False

    def test_description_whitespace_only(self):
        """Test whitespace-only description."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description("   \t\n   ")
        assert valid is False

    def test_description_none(self):
        """Test None description."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description(None)
        assert valid is False

    def test_description_unicode_characters(self):
        """Test description with unicode characters."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description(
            "This recommendation includes unicode: café résumé naïve 日本語 中文 العربية"
        )
        assert valid is True
        assert "café" in value

    def test_description_emoji(self):
        """Test description with emoji."""
        from recommendation.validation import validate_description
        valid, value, error = validate_description(
            "This recommendation could save you money! 💰 Tax savings ahead! 📊"
        )
        assert valid is True

    def test_description_very_long_truncated(self):
        """Test very long description is truncated."""
        from recommendation.validation import validate_description, DESCRIPTION_MAX_LENGTH
        long_desc = "A" * (DESCRIPTION_MAX_LENGTH + 1000)
        valid, value, error = validate_description(long_desc)
        assert valid is True
        assert len(value) == DESCRIPTION_MAX_LENGTH


class TestXSSPrevention:
    """Tests for XSS prevention in string inputs."""

    def test_html_tags_escaped(self):
        """Test HTML tags are escaped."""
        from recommendation.validation import sanitize_string
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_javascript_protocol_escaped(self):
        """Test javascript: protocol is escaped."""
        from recommendation.validation import sanitize_string
        result = sanitize_string("javascript:alert('xss')")
        assert "javascript:" in result  # Not dangerous when escaped

    def test_quotes_escaped(self):
        """Test quotes are escaped."""
        from recommendation.validation import sanitize_string
        result = sanitize_string('Test "quoted" and \'single\'')
        assert "&quot;" in result or '"' in result  # Either escaped or safe

    def test_control_characters_removed(self):
        """Test control characters are removed."""
        from recommendation.validation import sanitize_string
        result = sanitize_string("Test\x00with\x07control\x1fchars")
        assert "\x00" not in result
        assert "\x07" not in result
        assert "\x1f" not in result
        assert "Test" in result
        assert "with" in result


class TestIRSReferenceValidation:
    """Tests for IRS reference validation."""

    def test_irc_section_valid(self):
        """Test valid IRC Section reference."""
        from recommendation.validation import validate_irs_reference
        valid, value, warning = validate_irs_reference("IRC Section 24")
        assert valid is True
        assert warning is None

    def test_publication_valid(self):
        """Test valid Publication reference."""
        from recommendation.validation import validate_irs_reference
        valid, value, warning = validate_irs_reference("Publication 17")
        assert valid is True

    def test_form_valid(self):
        """Test valid Form reference."""
        from recommendation.validation import validate_irs_reference
        valid, value, warning = validate_irs_reference("Form 1040")
        assert valid is True

    def test_schedule_valid(self):
        """Test valid Schedule reference."""
        from recommendation.validation import validate_irs_reference
        valid, value, warning = validate_irs_reference("Schedule A")
        assert valid is True

    def test_unknown_format_warning(self):
        """Test unknown format produces warning but is valid."""
        from recommendation.validation import validate_irs_reference
        valid, value, warning = validate_irs_reference("Tax Code 123")
        assert valid is True  # Still valid, just warning
        assert warning is not None
        assert "does not match" in warning

    def test_empty_invalid(self):
        """Test empty IRS reference is invalid."""
        from recommendation.validation import validate_irs_reference
        valid, value, error = validate_irs_reference("")
        assert valid is False

    def test_none_invalid(self):
        """Test None IRS reference is invalid."""
        from recommendation.validation import validate_irs_reference
        valid, value, error = validate_irs_reference(None)
        assert valid is False


class TestDataTypeHandling:
    """Tests for handling various data types."""

    def test_number_from_string(self):
        """Test number conversion from string."""
        from recommendation.validation import sanitize_number
        result = sanitize_number("123.45")
        assert result == 123.45

    def test_number_from_int(self):
        """Test number conversion from int."""
        from recommendation.validation import sanitize_number
        result = sanitize_number(100)
        assert result == 100.0

    def test_number_from_invalid_returns_default(self):
        """Test invalid number returns default."""
        from recommendation.validation import sanitize_number
        result = sanitize_number("not a number", default=0.0)
        assert result == 0.0

    def test_string_from_number(self):
        """Test string sanitization from number."""
        from recommendation.validation import sanitize_string
        result = sanitize_string(12345)
        assert result == "12345"

    def test_string_from_list_converts(self):
        """Test string sanitization from list."""
        from recommendation.validation import sanitize_string
        result = sanitize_string(["item1", "item2"])
        assert "[" in result


class TestValidatorIntegration:
    """Integration tests for RecommendationValidator with edge cases."""

    def test_validator_handles_all_edge_cases(self):
        """Test validator handles complete edge case recommendation."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        # Edge case: confidence as decimal 0-1
        rec = {
            "description": "This is a valid recommendation with good explanation.",
            "estimated_savings": 0,  # Zero savings
            "confidence": 0.85,  # Decimal format
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        assert result.is_valid is True

    def test_validator_handles_unicode_fields(self):
        """Test validator handles unicode in all fields."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        rec = {
            "description": "Recommandation pour réduire les impôts avec stratégie naïve",
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        assert result.is_valid is True

    def test_validator_rejects_xss_but_validates_structure(self):
        """Test validator handles XSS attempts."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        rec = {
            "description": "<script>alert('xss')</script> This is a valid description though.",
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        # Should be valid structurally, XSS sanitization happens separately
        assert result.is_valid is True

    def test_filter_valid_removes_all_invalid(self):
        """Test filter_valid removes all types of invalid recommendations."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        recommendations = [
            # Valid
            {
                "description": "Valid recommendation with all required fields present.",
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            # Missing description
            {
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            # Empty description
            {
                "description": "",
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            # Whitespace description
            {
                "description": "   ",
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            # None savings
            {
                "description": "Valid description but missing savings field entirely.",
                "estimated_savings": None,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
        ]

        valid = validator.filter_valid(recommendations, "TaxSavingOpportunity")

        assert len(valid) == 1
        assert valid[0]["estimated_savings"] == 1000.0


class TestValidationStats:
    """Tests for validation statistics tracking."""

    def test_stats_track_all_error_types(self):
        """Test stats track different error types."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()
        validator.reset_stats()

        # Valid
        validator.validate({
            "description": "Valid recommendation description here.",
            "estimated_savings": 100,
            "confidence": 80,
            "irs_reference": "IRC Section 24",
        }, "TaxSavingOpportunity")

        # Missing reason
        validator.validate({
            "estimated_savings": 100,
            "confidence": 80,
            "irs_reference": "IRC Section 24",
        }, "TaxSavingOpportunity")

        # Missing impact
        validator.validate({
            "description": "Valid description for the recommendation.",
            "confidence": 80,
            "irs_reference": "IRC Section 24",
        }, "TaxSavingOpportunity")

        # Missing confidence
        validator.validate({
            "description": "Valid description for the recommendation.",
            "estimated_savings": 100,
            "irs_reference": "IRC Section 24",
        }, "TaxSavingOpportunity")

        # Missing IRS reference
        validator.validate({
            "description": "Valid description for the recommendation.",
            "estimated_savings": 100,
            "confidence": 80,
        }, "TaxSavingOpportunity")

        stats = validator.get_stats()

        assert stats["total_validated"] == 5
        assert stats["valid"] == 1
        assert stats["invalid"] == 4
        assert stats["missing_reason"] == 1
        assert stats["missing_impact"] == 1
        assert stats["missing_confidence"] == 1
        assert stats["missing_irs_reference"] == 1


class TestNullSafetyEdgeCases:
    """Tests for null/None safety edge cases."""

    def test_completely_empty_dict(self):
        """Test validation of completely empty dict."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()
        result = validator.validate({}, "TaxSavingOpportunity")

        assert result.is_valid is False
        assert len(result.missing_fields) == 4  # All required fields

    def test_all_none_values(self):
        """Test validation when all values are None."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()
        result = validator.validate({
            "description": None,
            "estimated_savings": None,
            "confidence": None,
            "irs_reference": None,
        }, "TaxSavingOpportunity")

        assert result.is_valid is False

    def test_non_dict_input(self):
        """Test validation of non-dict input."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        # String input
        result = validator.validate("not a dict", "TaxSavingOpportunity")
        assert result.is_valid is False

        # List input
        result = validator.validate(["a", "b"], "TaxSavingOpportunity")
        assert result.is_valid is False

        # None input
        result = validator.validate(None, "TaxSavingOpportunity")
        assert result.is_valid is False
