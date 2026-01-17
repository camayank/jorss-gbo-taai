"""
Recommendation Validation Module.

Enforces required fields for all recommendations. If any required field
is missing, the recommendation must not surface.

Required fields for every recommendation:
- reason: Why this recommendation applies to the taxpayer
- impact: Estimated tax savings or financial benefit
- confidence: Confidence level in the recommendation (0-100 or 0-1)
- irs_reference: IRS form, publication, or IRC section reference

This validation applies to ALL recommendation types:
- TaxSavingOpportunity
- TaxRecommendation
- CreditEligibility
- TaxStrategy
- Recommendation (domain model)
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# REQUIRED FIELDS DEFINITION
# =============================================================================

class RequiredField(str, Enum):
    """Required fields for all recommendations."""
    REASON = "reason"          # Why this recommendation applies
    IMPACT = "impact"          # Estimated tax savings/benefit
    CONFIDENCE = "confidence"  # Confidence level (0-100 or 0-1)
    IRS_REFERENCE = "irs_reference"  # IRS form/publication/IRC reference


# Field name mappings for different recommendation types
FIELD_MAPPINGS = {
    # TaxSavingOpportunity (recommendation_engine.py)
    "TaxSavingOpportunity": {
        RequiredField.REASON: ["description", "action_required"],
        RequiredField.IMPACT: ["estimated_savings"],
        RequiredField.CONFIDENCE: ["confidence"],
        RequiredField.IRS_REFERENCE: ["irs_reference"],
    },
    # TaxRecommendation (calculator/recommendations.py)
    "TaxRecommendation": {
        RequiredField.REASON: ["description"],
        RequiredField.IMPACT: ["potential_savings"],
        RequiredField.CONFIDENCE: ["confidence"],
        RequiredField.IRS_REFERENCE: ["irs_reference", "learn_more_topic"],
    },
    # CreditEligibility (credit_optimizer.py)
    "CreditEligibility": {
        RequiredField.REASON: ["eligibility_reason"],
        RequiredField.IMPACT: ["actual_amount", "potential_amount"],
        RequiredField.CONFIDENCE: ["confidence"],
        RequiredField.IRS_REFERENCE: ["irs_reference"],
    },
    # TaxStrategy (tax_strategy_advisor.py)
    "TaxStrategy": {
        RequiredField.REASON: ["description"],
        RequiredField.IMPACT: ["estimated_savings"],
        RequiredField.CONFIDENCE: ["confidence"],
        RequiredField.IRS_REFERENCE: ["irs_reference"],
    },
    # Recommendation (domain/aggregates.py)
    "Recommendation": {
        RequiredField.REASON: ["summary", "detailed_explanation"],
        RequiredField.IMPACT: ["estimated_savings"],
        RequiredField.CONFIDENCE: ["confidence_level"],
        RequiredField.IRS_REFERENCE: ["irs_references"],
    },
    # FilingStatusRecommendation (filing_status_optimizer.py)
    "FilingStatusRecommendation": {
        RequiredField.REASON: ["recommendation_reason"],
        RequiredField.IMPACT: ["potential_savings"],
        RequiredField.CONFIDENCE: ["confidence_score"],
        RequiredField.IRS_REFERENCE: ["irs_reference"],
    },
    # DeductionRecommendation (deduction_analyzer.py)
    "DeductionRecommendation": {
        RequiredField.REASON: ["explanation"],
        RequiredField.IMPACT: ["tax_savings_estimate"],
        RequiredField.CONFIDENCE: ["confidence_score"],
        RequiredField.IRS_REFERENCE: ["irs_reference"],
    },
    # CreditRecommendation (credit_optimizer.py)
    "CreditRecommendation": {
        RequiredField.REASON: ["summary"],
        RequiredField.IMPACT: ["total_credit_benefit"],
        RequiredField.CONFIDENCE: ["confidence_score"],
        RequiredField.IRS_REFERENCE: ["irs_reference"],
    },
}


# IRS reference patterns by category
IRS_REFERENCES = {
    "filing_status": ["IRC Section 2", "Publication 501", "Form 1040"],
    "deductions": ["Schedule A", "IRC Section 63", "Publication 17", "Form 1040"],
    "credits": {
        "child_tax_credit": ["IRC Section 24", "Schedule 8812", "Publication 972"],
        "eitc": ["IRC Section 32", "Schedule EIC", "Publication 596"],
        "education": ["IRC Section 25A", "Form 8863", "Publication 970"],
        "energy": ["IRC Section 25C", "IRC Section 25D", "Form 5695"],
        "child_care": ["IRC Section 21", "Form 2441", "Publication 503"],
        "saver": ["IRC Section 25B", "Form 8880"],
        "adoption": ["IRC Section 23", "Form 8839"],
        "foreign_tax": ["IRC Section 901", "Form 1116"],
        "general": ["Publication 17", "Form 1040"],
    },
    "retirement": {
        "401k": ["IRC Section 401(k)", "Publication 560"],
        "ira": ["IRC Section 408", "Publication 590-A", "Publication 590-B"],
        "roth": ["IRC Section 408A", "Publication 590-A"],
        "sep": ["IRC Section 408(k)", "Publication 560"],
        "simple": ["IRC Section 408(p)", "Publication 560"],
    },
    "healthcare": {
        "hsa": ["IRC Section 223", "Form 8889", "Publication 969"],
        "fsa": ["IRC Section 125", "Publication 15-B"],
        "premium_tax_credit": ["IRC Section 36B", "Form 8962"],
    },
    "investment": {
        "capital_gains": ["IRC Section 1", "Schedule D", "Publication 550"],
        "dividends": ["IRC Section 1(h)", "Publication 550"],
        "niit": ["IRC Section 1411", "Form 8960"],
    },
    "business": {
        "qbi": ["IRC Section 199A", "Form 8995", "Publication 535"],
        "self_employment": ["IRC Section 1401", "Schedule SE"],
        "home_office": ["IRC Section 280A", "Form 8829"],
    },
    "charitable": ["IRC Section 170", "Schedule A", "Publication 526"],
    "real_estate": {
        "mortgage_interest": ["IRC Section 163(h)", "Schedule A", "Publication 936"],
        "property_tax": ["IRC Section 164", "Schedule A"],
        "depreciation": ["IRC Section 167", "IRC Section 168", "Form 4562"],
    },
}


@dataclass
class ValidationResult:
    """Result of recommendation validation."""
    is_valid: bool
    recommendation_type: str
    missing_fields: List[str]
    warnings: List[str]
    original_data: Dict[str, Any]

    def __str__(self) -> str:
        if self.is_valid:
            return f"Valid {self.recommendation_type}"
        return f"Invalid {self.recommendation_type}: missing {', '.join(self.missing_fields)}"


class RecommendationValidator:
    """
    Validates recommendations before they surface.

    Rule: If any required field is missing, recommendation must not surface.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.

        Args:
            strict_mode: If True, IRS reference is strictly required.
                        If False, warnings are issued but recommendation can surface.
        """
        self.strict_mode = strict_mode
        self._validation_stats = {
            "total_validated": 0,
            "valid": 0,
            "invalid": 0,
            "missing_reason": 0,
            "missing_impact": 0,
            "missing_confidence": 0,
            "missing_irs_reference": 0,
        }

    def validate(
        self,
        recommendation: Any,
        recommendation_type: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a single recommendation.

        Args:
            recommendation: The recommendation object or dict to validate
            recommendation_type: Type name override (auto-detected if not provided)

        Returns:
            ValidationResult with validation status and details
        """
        self._validation_stats["total_validated"] += 1

        # Convert to dict if needed
        if hasattr(recommendation, "__dict__"):
            data = vars(recommendation) if not hasattr(recommendation, "dict") else recommendation.dict()
            rec_type = recommendation_type or type(recommendation).__name__
        elif hasattr(recommendation, "dict"):
            data = recommendation.dict()
            rec_type = recommendation_type or type(recommendation).__name__
        elif isinstance(recommendation, dict):
            data = recommendation
            rec_type = recommendation_type or data.get("_type", "Unknown")
        else:
            return ValidationResult(
                is_valid=False,
                recommendation_type="Unknown",
                missing_fields=["all"],
                warnings=["Cannot validate: unknown recommendation format"],
                original_data={}
            )

        # Get field mappings
        mappings = FIELD_MAPPINGS.get(rec_type, FIELD_MAPPINGS.get("TaxSavingOpportunity"))

        missing_fields = []
        warnings = []

        # Check each required field
        for required_field, possible_names in mappings.items():
            field_value = None

            # Try each possible field name
            for name in possible_names:
                value = data.get(name)
                if value is not None:
                    # For lists, check if non-empty
                    if isinstance(value, list) and len(value) > 0:
                        field_value = value
                        break
                    # For strings, check if non-empty
                    elif isinstance(value, str) and value.strip():
                        field_value = value
                        break
                    # For numbers, accept 0 as valid for impact
                    elif isinstance(value, (int, float)):
                        field_value = value
                        break

            if field_value is None:
                missing_fields.append(required_field.value)
                self._validation_stats[f"missing_{required_field.value}"] += 1

                # Add specific warning
                if required_field == RequiredField.IRS_REFERENCE:
                    warnings.append(
                        f"Missing IRS reference. Add one of: {', '.join(possible_names)}"
                    )

        # Determine validity
        if self.strict_mode:
            is_valid = len(missing_fields) == 0
        else:
            # In non-strict mode, only reason, impact, and confidence are required
            critical_missing = [
                f for f in missing_fields
                if f != RequiredField.IRS_REFERENCE.value
            ]
            is_valid = len(critical_missing) == 0
            if RequiredField.IRS_REFERENCE.value in missing_fields:
                warnings.append("IRS reference recommended but not required in non-strict mode")

        if is_valid:
            self._validation_stats["valid"] += 1
        else:
            self._validation_stats["invalid"] += 1
            logger.warning(
                f"Invalid recommendation ({rec_type}): missing {missing_fields}",
                extra={"recommendation_type": rec_type, "missing_fields": missing_fields}
            )

        return ValidationResult(
            is_valid=is_valid,
            recommendation_type=rec_type,
            missing_fields=missing_fields,
            warnings=warnings,
            original_data=data
        )

    def validate_batch(
        self,
        recommendations: List[Any],
        recommendation_type: Optional[str] = None
    ) -> List[ValidationResult]:
        """
        Validate a batch of recommendations.

        Args:
            recommendations: List of recommendations to validate
            recommendation_type: Type name override

        Returns:
            List of ValidationResult objects
        """
        return [
            self.validate(rec, recommendation_type)
            for rec in recommendations
        ]

    def filter_valid(
        self,
        recommendations: List[Any],
        recommendation_type: Optional[str] = None
    ) -> List[Any]:
        """
        Filter recommendations, returning only valid ones.

        Rule: If any required field is missing, recommendation must not surface.

        Args:
            recommendations: List of recommendations to filter
            recommendation_type: Type name override

        Returns:
            List of valid recommendations only
        """
        valid_recommendations = []

        for rec in recommendations:
            result = self.validate(rec, recommendation_type)
            if result.is_valid:
                valid_recommendations.append(rec)
            else:
                logger.info(
                    f"Filtering out invalid recommendation: {result}",
                    extra={"missing_fields": result.missing_fields}
                )

        return valid_recommendations

    def get_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return self._validation_stats.copy()

    def reset_stats(self) -> None:
        """Reset validation statistics."""
        for key in self._validation_stats:
            self._validation_stats[key] = 0


def get_irs_reference(category: str, subcategory: Optional[str] = None) -> List[str]:
    """
    Get IRS references for a recommendation category.

    Args:
        category: Main category (e.g., "credits", "deductions")
        subcategory: Optional subcategory (e.g., "child_tax_credit")

    Returns:
        List of IRS reference strings
    """
    refs = IRS_REFERENCES.get(category)

    if refs is None:
        return ["Publication 17", "Form 1040"]

    if isinstance(refs, dict):
        if subcategory and subcategory in refs:
            return refs[subcategory]
        return refs.get("general", ["Publication 17"])

    return refs


def add_irs_reference(
    recommendation: Dict[str, Any],
    category: str,
    subcategory: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add IRS reference to a recommendation if missing.

    Args:
        recommendation: Recommendation dict to update
        category: Category for IRS reference lookup
        subcategory: Optional subcategory

    Returns:
        Updated recommendation dict
    """
    if not recommendation.get("irs_reference") and not recommendation.get("irs_references"):
        refs = get_irs_reference(category, subcategory)
        recommendation["irs_reference"] = refs[0] if refs else None
        recommendation["irs_references"] = refs

    return recommendation


# =============================================================================
# VALIDATION DECORATORS
# =============================================================================

def validate_recommendations(recommendation_type: str = "TaxSavingOpportunity"):
    """
    Decorator to validate recommendations returned by a function.

    Usage:
        @validate_recommendations("TaxStrategy")
        def get_strategies(tax_return):
            return [...]
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            if result is None:
                return result

            validator = RecommendationValidator(strict_mode=True)

            if isinstance(result, list):
                return validator.filter_valid(result, recommendation_type)
            else:
                validation = validator.validate(result, recommendation_type)
                return result if validation.is_valid else None

        return wrapper
    return decorator


# =============================================================================
# GLOBAL VALIDATOR INSTANCE
# =============================================================================

_validator: Optional[RecommendationValidator] = None


def get_validator(strict_mode: bool = True) -> RecommendationValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = RecommendationValidator(strict_mode=strict_mode)
    return _validator


def validate_before_surface(
    recommendations: List[Any],
    recommendation_type: str = "TaxSavingOpportunity"
) -> List[Any]:
    """
    Validate recommendations before surfacing to user.

    This is the main entry point for enforcing the rule:
    "If any required field is missing, recommendation must not surface."

    Args:
        recommendations: List of recommendations to validate
        recommendation_type: Type of recommendations

    Returns:
        List of valid recommendations only
    """
    validator = get_validator()
    return validator.filter_valid(recommendations, recommendation_type)
