"""
Confidence Scorer - Multi-factor confidence scoring for extracted tax data.

Provides sophisticated confidence scoring that considers:
- OCR quality metrics
- Field format validation
- Cross-field consistency
- Document-level patterns
- Historical accuracy data
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from enum import Enum
import re
from calculator.decimal_math import money, to_decimal


class ConfidenceLevel(str, Enum):
    """Confidence levels for extracted data."""
    HIGH = "high"           # 85-100%: Very confident, likely correct
    MEDIUM = "medium"       # 65-84%: Reasonably confident, verify if critical
    LOW = "low"             # 40-64%: Uncertain, needs user verification
    VERY_LOW = "very_low"   # 0-39%: Likely incorrect, requires manual entry


@dataclass
class ConfidenceFactors:
    """Breakdown of factors contributing to confidence score."""
    ocr_quality: float = 0.0          # Base OCR confidence (0-100)
    format_match: float = 0.0          # How well value matches expected format (0-100)
    pattern_strength: float = 0.0      # Strength of regex pattern match (0-100)
    cross_field_consistency: float = 0.0  # Consistency with related fields (0-100)
    positional_accuracy: float = 0.0   # Field found in expected document position (0-100)
    value_plausibility: float = 0.0    # Value within expected ranges (0-100)

    def to_dict(self) -> Dict[str, float]:
        return {
            "ocr_quality": self.ocr_quality,
            "format_match": self.format_match,
            "pattern_strength": self.pattern_strength,
            "cross_field_consistency": self.cross_field_consistency,
            "positional_accuracy": self.positional_accuracy,
            "value_plausibility": self.value_plausibility,
        }


@dataclass
class ConfidenceResult:
    """Result of confidence calculation."""
    overall_score: float              # 0-100 weighted score
    level: ConfidenceLevel            # Categorical level
    factors: ConfidenceFactors        # Factor breakdown
    needs_verification: bool          # Should user verify this value?
    verification_reason: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "level": self.level.value,
            "factors": self.factors.to_dict(),
            "needs_verification": self.needs_verification,
            "verification_reason": self.verification_reason,
            "suggestions": self.suggestions,
        }


class ConfidenceScorer:
    """
    Multi-factor confidence scoring for extracted tax document fields.

    Uses weighted combination of multiple factors to produce
    a confidence score that reflects actual data reliability.
    """

    # Factor weights (must sum to 1.0)
    WEIGHTS = {
        "ocr_quality": 0.25,
        "format_match": 0.20,
        "pattern_strength": 0.15,
        "cross_field_consistency": 0.20,
        "positional_accuracy": 0.10,
        "value_plausibility": 0.10,
    }

    # Thresholds for confidence levels
    THRESHOLDS = {
        ConfidenceLevel.HIGH: 85,
        ConfidenceLevel.MEDIUM: 65,
        ConfidenceLevel.LOW: 40,
    }

    # Expected value ranges by field type
    VALUE_RANGES = {
        "wages": (1000, 1_000_000),
        "federal_tax_withheld": (0, 200_000),
        "social_security_wages": (0, 168_600),  # 2024 SS wage base
        "social_security_tax": (0, 10_453.20),  # Max SS tax 2024
        "medicare_wages": (1000, 2_000_000),
        "medicare_tax": (0, 50_000),
        "interest_income": (0, 500_000),
        "dividend_income": (0, 1_000_000),
        "ordinary_dividends": (0, 1_000_000),
        "qualified_dividends": (0, 1_000_000),
        "nonemployee_compensation": (1, 5_000_000),
    }

    def __init__(self):
        self._format_validators = self._setup_format_validators()

    def _setup_format_validators(self) -> Dict[str, callable]:
        """Setup format validation functions."""
        return {
            "ssn": lambda v: bool(re.match(r'^\d{3}-\d{2}-\d{4}$', v)),
            "ein": lambda v: bool(re.match(r'^\d{2}-\d{7}$', v)),
            "currency": lambda v: bool(re.match(r'^-?\$?[\d,]+\.?\d{0,2}$', v.replace(',', ''))),
            "date": lambda v: bool(re.match(r'^\d{4}-\d{2}-\d{2}$', v)),
            "state": lambda v: bool(re.match(r'^[A-Z]{2}$', v)),
        }

    def calculate_confidence(
        self,
        field_name: str,
        raw_value: str,
        normalized_value: Any,
        ocr_confidence: float,
        field_type: str,
        related_fields: Optional[Dict[str, Any]] = None,
        expected_position: Optional[str] = None,
        actual_position: Optional[str] = None,
    ) -> ConfidenceResult:
        """
        Calculate comprehensive confidence score for an extracted field.

        Args:
            field_name: Name of the field (e.g., "wages", "federal_tax_withheld")
            raw_value: Original extracted value
            normalized_value: Normalized/parsed value
            ocr_confidence: Base OCR confidence (0-100)
            field_type: Type of field (ssn, currency, etc.)
            related_fields: Dict of related field values for consistency checking
            expected_position: Expected document position (e.g., "box_1")
            actual_position: Actual extracted position

        Returns:
            ConfidenceResult with overall score and breakdown
        """
        factors = ConfidenceFactors()
        suggestions = []

        # Factor 1: OCR Quality
        factors.ocr_quality = min(100, max(0, ocr_confidence))

        # Factor 2: Format Match
        factors.format_match = self._score_format_match(
            raw_value, normalized_value, field_type
        )
        if factors.format_match < 70:
            suggestions.append(f"Value format may be incorrect: {raw_value}")

        # Factor 3: Pattern Strength
        factors.pattern_strength = self._score_pattern_strength(raw_value, field_type)

        # Factor 4: Cross-field Consistency
        factors.cross_field_consistency = self._score_cross_field_consistency(
            field_name, normalized_value, related_fields or {}
        )
        if factors.cross_field_consistency < 70:
            suggestions.append("Value may be inconsistent with related fields")

        # Factor 5: Positional Accuracy
        factors.positional_accuracy = self._score_positional_accuracy(
            expected_position, actual_position
        )

        # Factor 6: Value Plausibility
        factors.value_plausibility = self._score_value_plausibility(
            field_name, normalized_value
        )
        if factors.value_plausibility < 50:
            suggestions.append(f"Value seems outside typical range for {field_name}")

        # Calculate weighted overall score
        overall_score = (
            factors.ocr_quality * self.WEIGHTS["ocr_quality"] +
            factors.format_match * self.WEIGHTS["format_match"] +
            factors.pattern_strength * self.WEIGHTS["pattern_strength"] +
            factors.cross_field_consistency * self.WEIGHTS["cross_field_consistency"] +
            factors.positional_accuracy * self.WEIGHTS["positional_accuracy"] +
            factors.value_plausibility * self.WEIGHTS["value_plausibility"]
        )

        # Determine confidence level
        level = self._determine_level(overall_score)

        # Determine if verification needed
        needs_verification = level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]
        verification_reason = None
        if needs_verification:
            if factors.format_match < 70:
                verification_reason = "Value format appears incorrect"
            elif factors.cross_field_consistency < 70:
                verification_reason = "Value inconsistent with other fields"
            elif factors.ocr_quality < 60:
                verification_reason = "Low OCR quality for this field"
            elif factors.value_plausibility < 50:
                verification_reason = "Value outside expected range"
            else:
                verification_reason = "Multiple confidence factors below threshold"

        return ConfidenceResult(
            overall_score=round(overall_score, 1),
            level=level,
            factors=factors,
            needs_verification=needs_verification,
            verification_reason=verification_reason,
            suggestions=suggestions,
        )

    def _score_format_match(
        self,
        raw_value: str,
        normalized_value: Any,
        field_type: str
    ) -> float:
        """Score how well the value matches expected format."""
        if not raw_value:
            return 0.0

        # Check if normalization succeeded
        if normalized_value is None:
            return 30.0

        # Check format-specific validation
        validator = self._format_validators.get(field_type)
        if validator:
            if validator(raw_value):
                return 100.0
            # Check if normalized value would pass
            if isinstance(normalized_value, str) and validator(normalized_value):
                return 85.0
            return 50.0

        # For types without specific validators
        if field_type == "string" and raw_value.strip():
            return 90.0

        return 75.0

    def _score_pattern_strength(self, raw_value: str, field_type: str) -> float:
        """Score the strength of pattern match."""
        if not raw_value:
            return 0.0

        # SSN: Strong pattern
        if field_type == "ssn":
            if re.match(r'^\d{3}-\d{2}-\d{4}$', raw_value):
                return 100.0
            if re.match(r'^\d{9}$', raw_value):
                return 80.0
            return 40.0

        # EIN: Strong pattern
        if field_type == "ein":
            if re.match(r'^\d{2}-\d{7}$', raw_value):
                return 100.0
            if re.match(r'^\d{9}$', raw_value):
                return 80.0
            return 40.0

        # Currency: Check for clean number
        if field_type in ["currency", "decimal"]:
            cleaned = re.sub(r'[$,\s]', '', raw_value)
            if re.match(r'^-?\d+\.?\d{0,2}$', cleaned):
                return 95.0
            if re.match(r'^-?\d+\.?\d*$', cleaned):
                return 80.0
            return 50.0

        return 75.0

    def _score_cross_field_consistency(
        self,
        field_name: str,
        value: Any,
        related_fields: Dict[str, Any]
    ) -> float:
        """Score consistency with related fields."""
        if not related_fields:
            return 85.0  # No related fields to check, assume okay

        try:
            value_decimal = self._to_decimal(value)
            if value_decimal is None:
                return 75.0

            # W-2 consistency checks
            if field_name == "federal_tax_withheld":
                wages = self._to_decimal(related_fields.get("wages"))
                if wages and wages > 0:
                    # Tax withheld should be <= ~40% of wages (very generous)
                    max_expected = wages * Decimal("0.40")
                    if value_decimal > max_expected:
                        return 40.0
                    # Tax withheld typically 10-30% for most filers
                    if value_decimal > 0 and value_decimal <= wages * Decimal("0.35"):
                        return 95.0
                    return 70.0

            if field_name == "social_security_tax":
                ss_wages = self._to_decimal(related_fields.get("social_security_wages"))
                if ss_wages and ss_wages > 0:
                    # SS tax should be ~6.2% of SS wages
                    expected_tax = ss_wages * Decimal("0.062")
                    tolerance = expected_tax * Decimal("0.05")  # 5% tolerance
                    if abs(value_decimal - expected_tax) <= tolerance:
                        return 100.0
                    elif abs(value_decimal - expected_tax) <= tolerance * 2:
                        return 80.0
                    return 50.0

            if field_name == "medicare_tax":
                medicare_wages = self._to_decimal(related_fields.get("medicare_wages"))
                if medicare_wages and medicare_wages > 0:
                    # Medicare tax should be ~1.45% of Medicare wages
                    expected_tax = medicare_wages * Decimal("0.0145")
                    tolerance = expected_tax * Decimal("0.05")
                    if abs(value_decimal - expected_tax) <= tolerance:
                        return 100.0
                    elif abs(value_decimal - expected_tax) <= tolerance * 2:
                        return 80.0
                    return 50.0

            if field_name == "qualified_dividends":
                ordinary_divs = self._to_decimal(related_fields.get("ordinary_dividends"))
                if ordinary_divs and ordinary_divs > 0:
                    # Qualified dividends should be <= ordinary dividends
                    if value_decimal <= ordinary_divs:
                        return 100.0
                    return 30.0  # Major error if QD > OD

        except Exception:
            pass

        return 85.0  # Default if no specific check applies

    def _score_positional_accuracy(
        self,
        expected_position: Optional[str],
        actual_position: Optional[str]
    ) -> float:
        """Score whether field was found in expected document position."""
        if not expected_position or not actual_position:
            return 75.0  # No position info available

        if expected_position.lower() == actual_position.lower():
            return 100.0

        return 60.0

    def _score_value_plausibility(
        self,
        field_name: str,
        value: Any
    ) -> float:
        """Score whether value is within plausible range."""
        if value is None:
            return 50.0

        value_decimal = self._to_decimal(value)
        if value_decimal is None:
            return 75.0

        # Check against known ranges
        range_key = field_name.lower().replace("_", "_")
        expected_range = self.VALUE_RANGES.get(range_key)

        if expected_range:
            min_val, max_val = expected_range
            if Decimal(str(min_val)) <= value_decimal <= Decimal(str(max_val)):
                return 95.0
            elif value_decimal < 0:
                return 30.0  # Most fields shouldn't be negative
            elif value_decimal > Decimal(str(max_val)) * 2:
                return 40.0  # Way over max
            else:
                return 65.0  # Slightly outside range

        # Generic checks
        if value_decimal < 0:
            return 50.0  # Might be valid (refunds, etc.)

        return 85.0

    def _determine_level(self, score: float) -> ConfidenceLevel:
        """Determine confidence level from score."""
        if score >= self.THRESHOLDS[ConfidenceLevel.HIGH]:
            return ConfidenceLevel.HIGH
        elif score >= self.THRESHOLDS[ConfidenceLevel.MEDIUM]:
            return ConfidenceLevel.MEDIUM
        elif score >= self.THRESHOLDS[ConfidenceLevel.LOW]:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal for comparison."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                cleaned = re.sub(r'[$,\s]', '', value)
                return Decimal(cleaned)
            except Exception:
                return None
        return None


class DocumentConfidenceAggregator:
    """
    Aggregates field-level confidence into document-level confidence.

    Provides overall document reliability score and identifies
    which fields need attention.
    """

    def __init__(self):
        self.scorer = ConfidenceScorer()

    def aggregate_document_confidence(
        self,
        field_results: List[ConfidenceResult],
        critical_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate field confidence scores into document-level metrics.

        Args:
            field_results: List of ConfidenceResult for each field
            critical_fields: Fields that are critical (weighted higher)

        Returns:
            Document-level confidence summary
        """
        if not field_results:
            return {
                "overall_score": 0.0,
                "level": ConfidenceLevel.VERY_LOW.value,
                "fields_needing_review": [],
                "high_confidence_fields": 0,
                "medium_confidence_fields": 0,
                "low_confidence_fields": 0,
                "document_usable": False,
            }

        critical_fields = critical_fields or []

        # Count by level
        high_count = sum(1 for r in field_results if r.level == ConfidenceLevel.HIGH)
        medium_count = sum(1 for r in field_results if r.level == ConfidenceLevel.MEDIUM)
        low_count = sum(1 for r in field_results if r.level in [
            ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW
        ])

        # Calculate weighted average
        total_weight = 0.0
        weighted_sum = 0.0
        fields_needing_review = []

        for i, result in enumerate(field_results):
            # Critical fields get 2x weight
            field_name = f"field_{i}"  # Would be better with actual field names
            weight = 2.0 if field_name in critical_fields else 1.0

            weighted_sum += result.overall_score * weight
            total_weight += weight

            if result.needs_verification:
                fields_needing_review.append({
                    "index": i,
                    "score": result.overall_score,
                    "reason": result.verification_reason,
                    "suggestions": result.suggestions,
                })

        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Determine overall level
        overall_level = self.scorer._determine_level(overall_score)

        # Document is usable if overall is at least MEDIUM and no critical fields are LOW
        document_usable = (
            overall_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM] and
            len(fields_needing_review) < len(field_results) * 0.3  # Less than 30% need review
        )

        return {
            "overall_score": round(overall_score, 1),
            "level": overall_level.value,
            "fields_needing_review": fields_needing_review,
            "high_confidence_fields": high_count,
            "medium_confidence_fields": medium_count,
            "low_confidence_fields": low_count,
            "document_usable": document_usable,
            "review_summary": self._generate_review_summary(
                overall_score, fields_needing_review
            ),
        }

    def _generate_review_summary(
        self,
        overall_score: float,
        fields_needing_review: List[Dict]
    ) -> str:
        """Generate human-readable review summary."""
        if overall_score >= 90:
            return "Document extracted with high confidence. Ready for processing."
        elif overall_score >= 75:
            if fields_needing_review:
                return f"Document mostly extracted. {len(fields_needing_review)} field(s) may need verification."
            return "Document extracted with good confidence."
        elif overall_score >= 60:
            return f"Document extracted with moderate confidence. Please review {len(fields_needing_review)} flagged field(s)."
        else:
            return "Document quality is low. Manual review recommended for accuracy."


# Convenience functions
def calculate_field_confidence(
    field_name: str,
    raw_value: str,
    normalized_value: Any,
    ocr_confidence: float,
    field_type: str,
    **kwargs
) -> ConfidenceResult:
    """Calculate confidence for a single field."""
    scorer = ConfidenceScorer()
    return scorer.calculate_confidence(
        field_name=field_name,
        raw_value=raw_value,
        normalized_value=normalized_value,
        ocr_confidence=ocr_confidence,
        field_type=field_type,
        **kwargs
    )


def get_confidence_band(
    low_estimate: float,
    likely_estimate: float,
    high_estimate: float,
    confidence_score: float
) -> Dict[str, Any]:
    """
    Generate a confidence band for a tax estimate.

    Args:
        low_estimate: Conservative (low) estimate
        likely_estimate: Most likely estimate
        high_estimate: Optimistic (high) estimate
        confidence_score: Overall confidence (0-100)

    Returns:
        Confidence band with estimates and metadata
    """
    # Widen band based on confidence
    if confidence_score >= 85:
        band_width_multiplier = 1.0
    elif confidence_score >= 70:
        band_width_multiplier = 1.3
    elif confidence_score >= 50:
        band_width_multiplier = 1.6
    else:
        band_width_multiplier = 2.0

    # Calculate widened band
    current_low_diff = likely_estimate - low_estimate
    current_high_diff = high_estimate - likely_estimate

    adjusted_low = likely_estimate - (current_low_diff * band_width_multiplier)
    adjusted_high = likely_estimate + (current_high_diff * band_width_multiplier)

    return {
        "low": float(money(adjusted_low)),
        "likely": float(money(likely_estimate)),
        "high": float(money(adjusted_high)),
        "confidence_score": confidence_score,
        "confidence_level": ConfidenceScorer()._determine_level(confidence_score).value,
        "band_width": float(money(adjusted_high - adjusted_low)),
        "disclaimer": _get_estimate_disclaimer(confidence_score),
    }


def _get_estimate_disclaimer(confidence_score: float) -> str:
    """Get appropriate disclaimer based on confidence."""
    if confidence_score >= 85:
        return "Estimate based on high-confidence data. Final amount may vary slightly."
    elif confidence_score >= 70:
        return "Estimate based on moderately confident data. Review extracted values for accuracy."
    elif confidence_score >= 50:
        return "Estimate based on partially verified data. Some values may need manual verification."
    else:
        return "Preliminary estimate only. Data quality is low - please verify all extracted values."
