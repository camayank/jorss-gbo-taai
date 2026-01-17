"""
Tests for Recommendation Validation Module.

These tests verify that:
1. All recommendation types are defined
2. Required fields are enforced: reason, impact, confidence, IRS reference
3. Recommendations with missing fields do not surface
"""

import pytest
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestRequiredFieldsDefinition:
    """Tests for required fields definition."""

    def test_required_fields_enum_exists(self):
        """Test that RequiredField enum is defined."""
        from recommendation.validation import RequiredField

        assert RequiredField.REASON is not None
        assert RequiredField.IMPACT is not None
        assert RequiredField.CONFIDENCE is not None
        assert RequiredField.IRS_REFERENCE is not None

    def test_field_mappings_for_all_types(self):
        """Test that field mappings exist for all recommendation types."""
        from recommendation.validation import FIELD_MAPPINGS

        expected_types = [
            "TaxSavingOpportunity",
            "TaxRecommendation",
            "CreditEligibility",
            "TaxStrategy",
            "Recommendation",
            "FilingStatusRecommendation",
            "DeductionRecommendation",
            "CreditRecommendation",
        ]

        for rec_type in expected_types:
            assert rec_type in FIELD_MAPPINGS, f"Missing mapping for {rec_type}"

    def test_each_mapping_has_all_required_fields(self):
        """Test that each mapping defines all required fields."""
        from recommendation.validation import FIELD_MAPPINGS, RequiredField

        for rec_type, mapping in FIELD_MAPPINGS.items():
            for required_field in RequiredField:
                assert required_field in mapping, \
                    f"{rec_type} missing mapping for {required_field.value}"


class TestRecommendationValidator:
    """Tests for RecommendationValidator class."""

    def test_validator_creation(self):
        """Test validator can be created."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()
        assert validator is not None
        assert validator.strict_mode is True

    def test_validator_non_strict_mode(self):
        """Test validator in non-strict mode."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator(strict_mode=False)
        assert validator.strict_mode is False

    def test_validate_complete_recommendation(self):
        """Test validating a complete recommendation."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        complete_rec = {
            "description": "This is why you should do this",
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(complete_rec, "TaxSavingOpportunity")

        assert result.is_valid is True
        assert len(result.missing_fields) == 0

    def test_validate_missing_reason(self):
        """Test that missing reason field fails validation."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        incomplete_rec = {
            # "description" missing - this is the reason field
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(incomplete_rec, "TaxSavingOpportunity")

        assert result.is_valid is False
        assert "reason" in result.missing_fields

    def test_validate_missing_impact(self):
        """Test that missing impact field fails validation."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        incomplete_rec = {
            "description": "This is why you should do this",
            # "estimated_savings" missing - this is the impact field
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(incomplete_rec, "TaxSavingOpportunity")

        assert result.is_valid is False
        assert "impact" in result.missing_fields

    def test_validate_missing_confidence(self):
        """Test that missing confidence field fails validation."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        incomplete_rec = {
            "description": "This is why you should do this",
            "estimated_savings": 1000.0,
            # "confidence" missing
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(incomplete_rec, "TaxSavingOpportunity")

        assert result.is_valid is False
        assert "confidence" in result.missing_fields

    def test_validate_missing_irs_reference(self):
        """Test that missing IRS reference field fails validation in strict mode."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator(strict_mode=True)

        incomplete_rec = {
            "description": "This is why you should do this",
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            # "irs_reference" missing
        }

        result = validator.validate(incomplete_rec, "TaxSavingOpportunity")

        assert result.is_valid is False
        assert "irs_reference" in result.missing_fields

    def test_validate_missing_irs_reference_non_strict(self):
        """Test that missing IRS reference passes in non-strict mode."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator(strict_mode=False)

        incomplete_rec = {
            "description": "This is why you should do this",
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            # "irs_reference" missing but ok in non-strict
        }

        result = validator.validate(incomplete_rec, "TaxSavingOpportunity")

        assert result.is_valid is True
        assert len(result.warnings) > 0  # Should have warning about missing IRS ref


class TestFilterValidRecommendations:
    """Tests for filtering invalid recommendations."""

    def test_filter_valid_keeps_complete_recommendations(self):
        """Test that complete recommendations are kept."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        recommendations = [
            {
                "description": "Recommendation 1",
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            {
                "description": "Recommendation 2",
                "estimated_savings": 500.0,
                "confidence": 75.0,
                "irs_reference": "IRC Section 32",
            },
        ]

        valid = validator.filter_valid(recommendations, "TaxSavingOpportunity")

        assert len(valid) == 2

    def test_filter_valid_removes_incomplete_recommendations(self):
        """Test that incomplete recommendations are filtered out."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        recommendations = [
            {
                "description": "Complete recommendation",
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            {
                # Missing description (reason)
                "estimated_savings": 500.0,
                "confidence": 75.0,
                "irs_reference": "IRC Section 32",
            },
            {
                "description": "Missing savings",
                # Missing estimated_savings (impact)
                "confidence": 75.0,
                "irs_reference": "IRC Section 32",
            },
        ]

        valid = validator.filter_valid(recommendations, "TaxSavingOpportunity")

        assert len(valid) == 1
        assert valid[0]["description"] == "Complete recommendation"

    def test_filter_valid_removes_all_if_all_invalid(self):
        """Test that all invalid recommendations are removed."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        recommendations = [
            {"estimated_savings": 1000.0},  # Missing most fields
            {"confidence": 75.0},  # Missing most fields
        ]

        valid = validator.filter_valid(recommendations, "TaxSavingOpportunity")

        assert len(valid) == 0


class TestValidationStats:
    """Tests for validation statistics."""

    def test_stats_tracking(self):
        """Test that validation stats are tracked."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()
        validator.reset_stats()

        # Validate some recommendations
        validator.validate({
            "description": "Test",
            "estimated_savings": 100,
            "confidence": 80,
            "irs_reference": "IRC 24",
        }, "TaxSavingOpportunity")

        validator.validate({
            "estimated_savings": 100,  # Missing description
            "confidence": 80,
            "irs_reference": "IRC 24",
        }, "TaxSavingOpportunity")

        stats = validator.get_stats()

        assert stats["total_validated"] == 2
        assert stats["valid"] == 1
        assert stats["invalid"] == 1
        assert stats["missing_reason"] == 1


class TestIRSReferences:
    """Tests for IRS reference lookup."""

    def test_get_irs_reference_credits(self):
        """Test getting IRS references for credits."""
        from recommendation.validation import get_irs_reference

        refs = get_irs_reference("credits", "child_tax_credit")
        assert len(refs) > 0
        assert any("24" in ref for ref in refs)  # IRC Section 24

    def test_get_irs_reference_deductions(self):
        """Test getting IRS references for deductions."""
        from recommendation.validation import get_irs_reference

        refs = get_irs_reference("deductions")
        assert len(refs) > 0
        assert any("Schedule A" in ref for ref in refs)

    def test_get_irs_reference_retirement(self):
        """Test getting IRS references for retirement."""
        from recommendation.validation import get_irs_reference

        refs = get_irs_reference("retirement", "401k")
        assert len(refs) > 0
        assert any("401" in ref for ref in refs)

    def test_get_irs_reference_unknown_category(self):
        """Test getting IRS references for unknown category."""
        from recommendation.validation import get_irs_reference

        refs = get_irs_reference("unknown_category")
        assert len(refs) > 0  # Should return default


class TestRecommendationEngineIntegration:
    """Integration tests for recommendation engine validation."""

    def test_tax_saving_opportunity_has_irs_reference(self):
        """Test that TaxSavingOpportunity includes irs_reference field."""
        from recommendation.recommendation_engine import TaxSavingOpportunity

        opp = TaxSavingOpportunity(
            category="credits",
            title="Test Credit",
            estimated_savings=1000.0,
            priority="immediate",
            description="Test description",
            action_required="Take action",
            confidence=85.0,
            irs_reference="IRC Section 24",
        )

        assert opp.irs_reference == "IRC Section 24"

    def test_collect_opportunities_adds_irs_references(self):
        """Verify that _collect_opportunities adds IRS references."""
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'recommendation', 'recommendation_engine.py'
        )

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify IRS references are added
        assert 'irs_reference="IRC Section' in source or "irs_reference='IRC Section" in source
        assert '_get_credit_irs_reference' in source
        assert '_get_strategy_irs_reference' in source

    def test_validate_opportunities_is_called(self):
        """Verify that _validate_opportunities is called."""
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'recommendation', 'recommendation_engine.py'
        )

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify validation is called
        assert '_validate_opportunities' in source
        assert 'valid_opportunities = self._validate_opportunities(opportunities)' in source


class TestValidateBeforeSurface:
    """Tests for validate_before_surface function."""

    def test_validate_before_surface_filters_invalid(self):
        """Test that validate_before_surface filters invalid recommendations."""
        from recommendation.validation import validate_before_surface

        recommendations = [
            {
                "description": "Valid recommendation",
                "estimated_savings": 1000.0,
                "confidence": 85.0,
                "irs_reference": "IRC Section 24",
            },
            {
                # Invalid - missing description
                "estimated_savings": 500.0,
                "confidence": 75.0,
                "irs_reference": "IRC Section 32",
            },
        ]

        valid = validate_before_surface(recommendations, "TaxSavingOpportunity")

        assert len(valid) == 1
        assert valid[0]["description"] == "Valid recommendation"


class TestRecommendationTypes:
    """Tests verifying all recommendation types."""

    def test_all_recommendation_types_documented(self):
        """Verify all recommendation types are documented in validation module."""
        from recommendation.validation import FIELD_MAPPINGS

        # All these types should be in FIELD_MAPPINGS
        expected_types = [
            "TaxSavingOpportunity",      # recommendation_engine.py
            "TaxRecommendation",          # calculator/recommendations.py
            "CreditEligibility",          # credit_optimizer.py
            "TaxStrategy",                # tax_strategy_advisor.py
            "Recommendation",             # domain/aggregates.py
            "FilingStatusRecommendation", # filing_status_optimizer.py
            "DeductionRecommendation",    # deduction_analyzer.py
            "CreditRecommendation",       # credit_optimizer.py
        ]

        for rec_type in expected_types:
            assert rec_type in FIELD_MAPPINGS, \
                f"Recommendation type '{rec_type}' not in FIELD_MAPPINGS"


class TestEdgeCases:
    """Edge case tests for validation."""

    def test_empty_string_description_invalid(self):
        """Test that empty string description is invalid."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        rec = {
            "description": "",  # Empty string
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        assert result.is_valid is False
        assert "reason" in result.missing_fields

    def test_whitespace_only_description_invalid(self):
        """Test that whitespace-only description is invalid."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        rec = {
            "description": "   ",  # Whitespace only
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        assert result.is_valid is False
        assert "reason" in result.missing_fields

    def test_zero_savings_is_valid(self):
        """Test that zero savings is valid (it's a valid impact)."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        rec = {
            "description": "Informational recommendation",
            "estimated_savings": 0.0,  # Zero is valid
            "confidence": 85.0,
            "irs_reference": "Publication 17",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        assert result.is_valid is True

    def test_none_values_invalid(self):
        """Test that None values are invalid."""
        from recommendation.validation import RecommendationValidator

        validator = RecommendationValidator()

        rec = {
            "description": None,
            "estimated_savings": 1000.0,
            "confidence": 85.0,
            "irs_reference": "IRC Section 24",
        }

        result = validator.validate(rec, "TaxSavingOpportunity")
        assert result.is_valid is False
