"""Tests for OCR confidence scoring module."""

import pytest
from decimal import Decimal

from src.services.ocr.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceLevel,
    ConfidenceFactors,
    ConfidenceResult,
    DocumentConfidenceAggregator,
    calculate_field_confidence,
    get_confidence_band,
)


class TestConfidenceScorer:
    """Tests for ConfidenceScorer class."""

    def test_initialization(self):
        """Test scorer initializes correctly."""
        scorer = ConfidenceScorer()
        assert scorer is not None
        assert len(scorer.WEIGHTS) == 6
        assert sum(scorer.WEIGHTS.values()) == 1.0

    def test_high_confidence_ssn(self):
        """Test high confidence for well-formatted SSN."""
        scorer = ConfidenceScorer()
        result = scorer.calculate_confidence(
            field_name="employee_ssn",
            raw_value="123-45-6789",
            normalized_value="123-45-6789",
            ocr_confidence=95.0,
            field_type="ssn",
        )
        assert result.level == ConfidenceLevel.HIGH
        assert result.overall_score >= 85
        assert not result.needs_verification

    def test_low_confidence_poor_ocr(self):
        """Test confidence is reduced when OCR quality is poor."""
        scorer = ConfidenceScorer()

        # Compare high OCR vs low OCR for same field
        high_ocr_result = scorer.calculate_confidence(
            field_name="wages",
            raw_value="12,345.67",
            normalized_value=Decimal("12345.67"),
            ocr_confidence=95.0,
            field_type="currency",
        )
        low_ocr_result = scorer.calculate_confidence(
            field_name="wages",
            raw_value="12,345.67",
            normalized_value=Decimal("12345.67"),
            ocr_confidence=40.0,
            field_type="currency",
        )

        # Low OCR should produce lower score than high OCR
        assert low_ocr_result.overall_score < high_ocr_result.overall_score
        # OCR quality factor should reflect the difference
        assert low_ocr_result.factors.ocr_quality < high_ocr_result.factors.ocr_quality

    def test_format_match_scoring(self):
        """Test format match affects confidence."""
        scorer = ConfidenceScorer()

        # Good format
        good_result = scorer.calculate_confidence(
            field_name="employer_ein",
            raw_value="12-3456789",
            normalized_value="12-3456789",
            ocr_confidence=90.0,
            field_type="ein",
        )

        # Bad format (missing dash)
        bad_result = scorer.calculate_confidence(
            field_name="employer_ein",
            raw_value="123456789",
            normalized_value="12-3456789",
            ocr_confidence=90.0,
            field_type="ein",
        )

        assert good_result.factors.format_match > bad_result.factors.format_match

    def test_cross_field_consistency_ss_tax(self):
        """Test cross-field validation for SS tax."""
        scorer = ConfidenceScorer()

        # Consistent values (6.2% of SS wages)
        related = {"social_security_wages": Decimal("50000")}
        consistent_result = scorer.calculate_confidence(
            field_name="social_security_tax",
            raw_value="3100.00",
            normalized_value=Decimal("3100.00"),
            ocr_confidence=90.0,
            field_type="currency",
            related_fields=related,
        )

        # Inconsistent values
        inconsistent_result = scorer.calculate_confidence(
            field_name="social_security_tax",
            raw_value="5000.00",
            normalized_value=Decimal("5000.00"),
            ocr_confidence=90.0,
            field_type="currency",
            related_fields=related,
        )

        assert consistent_result.factors.cross_field_consistency > inconsistent_result.factors.cross_field_consistency

    def test_value_plausibility_wages(self):
        """Test value plausibility scoring for wages."""
        scorer = ConfidenceScorer()

        # Plausible wages
        plausible = scorer.calculate_confidence(
            field_name="wages",
            raw_value="75000.00",
            normalized_value=Decimal("75000.00"),
            ocr_confidence=90.0,
            field_type="currency",
        )

        # Implausible wages (too high)
        implausible = scorer.calculate_confidence(
            field_name="wages",
            raw_value="50000000.00",
            normalized_value=Decimal("50000000.00"),
            ocr_confidence=90.0,
            field_type="currency",
        )

        assert plausible.factors.value_plausibility > implausible.factors.value_plausibility

    def test_result_has_suggestions(self):
        """Test that low confidence results include suggestions."""
        scorer = ConfidenceScorer()
        result = scorer.calculate_confidence(
            field_name="federal_tax_withheld",
            raw_value="100000.00",
            normalized_value=Decimal("100000.00"),
            ocr_confidence=50.0,
            field_type="currency",
            related_fields={"wages": Decimal("50000")},
        )

        # Should have suggestions due to withholding > 50% of wages
        assert len(result.suggestions) > 0 or result.needs_verification


class TestConfidenceLevels:
    """Tests for confidence level determination."""

    def test_high_threshold(self):
        """Test HIGH confidence threshold."""
        scorer = ConfidenceScorer()
        assert scorer.THRESHOLDS[ConfidenceLevel.HIGH] == 85

    def test_medium_threshold(self):
        """Test MEDIUM confidence threshold."""
        scorer = ConfidenceScorer()
        assert scorer.THRESHOLDS[ConfidenceLevel.MEDIUM] == 65

    def test_low_threshold(self):
        """Test LOW confidence threshold."""
        scorer = ConfidenceScorer()
        assert scorer.THRESHOLDS[ConfidenceLevel.LOW] == 40


class TestDocumentConfidenceAggregator:
    """Tests for document-level confidence aggregation."""

    def test_aggregator_initialization(self):
        """Test aggregator initializes correctly."""
        aggregator = DocumentConfidenceAggregator()
        assert aggregator.scorer is not None

    def test_aggregate_empty_results(self):
        """Test aggregation of empty results."""
        aggregator = DocumentConfidenceAggregator()
        result = aggregator.aggregate_document_confidence([])

        assert result["overall_score"] == 0.0
        assert result["document_usable"] == False

    def test_aggregate_all_high_confidence(self):
        """Test aggregation of all high confidence fields."""
        aggregator = DocumentConfidenceAggregator()

        high_results = [
            ConfidenceResult(
                overall_score=90.0,
                level=ConfidenceLevel.HIGH,
                factors=ConfidenceFactors(),
                needs_verification=False,
            )
            for _ in range(5)
        ]

        result = aggregator.aggregate_document_confidence(high_results)

        assert result["overall_score"] >= 85
        assert result["high_confidence_fields"] == 5
        assert result["document_usable"] == True

    def test_aggregate_mixed_confidence(self):
        """Test aggregation of mixed confidence levels."""
        aggregator = DocumentConfidenceAggregator()

        results = [
            ConfidenceResult(
                overall_score=90.0,
                level=ConfidenceLevel.HIGH,
                factors=ConfidenceFactors(),
                needs_verification=False,
            ),
            ConfidenceResult(
                overall_score=70.0,
                level=ConfidenceLevel.MEDIUM,
                factors=ConfidenceFactors(),
                needs_verification=False,
            ),
            ConfidenceResult(
                overall_score=30.0,
                level=ConfidenceLevel.VERY_LOW,
                factors=ConfidenceFactors(),
                needs_verification=True,
                verification_reason="Low OCR quality",
            ),
        ]

        result = aggregator.aggregate_document_confidence(results)

        assert result["high_confidence_fields"] == 1
        assert result["medium_confidence_fields"] == 1
        assert result["low_confidence_fields"] == 1
        assert len(result["fields_needing_review"]) == 1


class TestConfidenceBand:
    """Tests for confidence band generation."""

    def test_high_confidence_narrow_band(self):
        """Test that high confidence produces narrow band."""
        band = get_confidence_band(
            low_estimate=4500,
            likely_estimate=5000,
            high_estimate=5500,
            confidence_score=90,
        )

        assert band["likely"] == 5000
        assert band["confidence_level"] == "high"
        # Band should be relatively narrow at high confidence
        assert band["band_width"] < 1500

    def test_low_confidence_wide_band(self):
        """Test that low confidence widens band."""
        band = get_confidence_band(
            low_estimate=4500,
            likely_estimate=5000,
            high_estimate=5500,
            confidence_score=40,
        )

        assert band["likely"] == 5000
        # Band should be wider at low confidence
        assert band["band_width"] > 1000

    def test_band_includes_disclaimer(self):
        """Test that band includes appropriate disclaimer."""
        band = get_confidence_band(
            low_estimate=4500,
            likely_estimate=5000,
            high_estimate=5500,
            confidence_score=90,
        )

        assert "disclaimer" in band
        assert isinstance(band["disclaimer"], str)

    def test_different_disclaimers_by_confidence(self):
        """Test different disclaimers for different confidence levels."""
        high_band = get_confidence_band(100, 500, 1000, 90)
        low_band = get_confidence_band(100, 500, 1000, 30)

        assert high_band["disclaimer"] != low_band["disclaimer"]


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_calculate_field_confidence(self):
        """Test convenience function works correctly."""
        result = calculate_field_confidence(
            field_name="wages",
            raw_value="50000.00",
            normalized_value=Decimal("50000.00"),
            ocr_confidence=85.0,
            field_type="currency",
        )

        assert isinstance(result, ConfidenceResult)
        assert result.overall_score > 0
        assert result.level is not None


class TestFactorWeights:
    """Tests for factor weight configuration."""

    def test_weights_sum_to_one(self):
        """Test that all weights sum to 1.0."""
        scorer = ConfidenceScorer()
        total = sum(scorer.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_factors_have_weights(self):
        """Test that all factor types have weights."""
        scorer = ConfidenceScorer()
        expected_factors = [
            "ocr_quality",
            "format_match",
            "pattern_strength",
            "cross_field_consistency",
            "positional_accuracy",
            "value_plausibility",
        ]
        for factor in expected_factors:
            assert factor in scorer.WEIGHTS


class TestValueRanges:
    """Tests for value range validation."""

    def test_wages_range_defined(self):
        """Test wages range is defined."""
        scorer = ConfidenceScorer()
        assert "wages" in scorer.VALUE_RANGES
        min_val, max_val = scorer.VALUE_RANGES["wages"]
        assert min_val < max_val

    def test_ss_wages_range_matches_wage_base(self):
        """Test SS wages max is around wage base."""
        scorer = ConfidenceScorer()
        _, max_ss_wages = scorer.VALUE_RANGES["social_security_wages"]
        # Should be around 2024 wage base
        assert max_ss_wages >= 160000
        assert max_ss_wages <= 180000


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_raw_value(self):
        """Test handling of empty raw value."""
        scorer = ConfidenceScorer()
        result = scorer.calculate_confidence(
            field_name="wages",
            raw_value="",
            normalized_value=None,
            ocr_confidence=0.0,
            field_type="currency",
        )

        assert result.overall_score < 50
        assert result.needs_verification

    def test_none_normalized_value(self):
        """Test handling of None normalized value."""
        scorer = ConfidenceScorer()
        result = scorer.calculate_confidence(
            field_name="employer_ein",
            raw_value="invalid",
            normalized_value=None,
            ocr_confidence=80.0,
            field_type="ein",
        )

        assert result.factors.format_match < 50

    def test_negative_value(self):
        """Test handling of negative values."""
        scorer = ConfidenceScorer()
        result = scorer.calculate_confidence(
            field_name="wages",
            raw_value="-5000",
            normalized_value=Decimal("-5000"),
            ocr_confidence=90.0,
            field_type="currency",
        )

        # Negative wages should lower plausibility
        assert result.factors.value_plausibility < 80
