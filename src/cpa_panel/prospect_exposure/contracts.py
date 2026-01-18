"""
Prospect Exposure Contracts

These contracts define the ONLY data structures that can be exposed to prospects.
All transformers MUST output these exact types - no raw numbers, no internal data.

Design Principles:
- Exact values → Directional bands
- Quantitative → Qualitative
- Advisory → Discovery
- Specific → Categorical
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# OUTCOME EXPOSURE ENUMS
# =============================================================================

class OutcomeType(str, Enum):
    """Directional outcome - never exact amounts."""
    LIKELY_REFUND = "likely_refund"
    LIKELY_OWED = "likely_owed"
    UNCLEAR = "unclear"


class AmountBand(str, Enum):
    """
    Amount bands for safe exposure.
    These are intentionally coarse to prevent reverse-engineering exact values.
    """
    BAND_0_500 = "0_to_500"
    BAND_500_2K = "500_to_2k"
    BAND_2K_5K = "2k_to_5k"
    BAND_5K_10K = "5k_to_10k"
    BAND_10K_25K = "10k_to_25k"
    BAND_25K_PLUS = "25k_plus"
    UNKNOWN = "unknown"


class ConfidenceBand(str, Enum):
    """Confidence level - never percentages."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DisclaimerCode(str, Enum):
    """Standard disclaimer codes - no custom advisory language."""
    DISCOVERY_ONLY = "discovery_only"
    SUBJECT_TO_CPA_REVIEW = "subject_to_cpa_review"
    PRELIMINARY_ESTIMATE = "preliminary_estimate"
    NOT_TAX_ADVICE = "not_tax_advice"


# =============================================================================
# COMPLEXITY EXPOSURE ENUMS
# =============================================================================

class ComplexityLevel(str, Enum):
    """Complexity classification - no scoring."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class ComplexityReason(str, Enum):
    """
    Categorical reasons for complexity.
    Max 3 can be exposed to prospect.
    """
    SELF_EMPLOYMENT = "self_employment"
    RENTAL_INCOME = "rental_income"
    CRYPTO_TRANSACTIONS = "crypto_transactions"
    FOREIGN_INCOME = "foreign_income"
    K1_PARTNERSHIP = "k1_partnership"
    MULTI_STATE = "multi_state"
    LARGE_INCOME = "large_income"
    ITEMIZING = "itemizing"
    CAPITAL_GAINS = "capital_gains"
    BUSINESS_ENTITY = "business_entity"


# =============================================================================
# DRIVER EXPOSURE ENUMS
# =============================================================================

class DriverCategory(str, Enum):
    """
    High-level driver categories.
    These describe WHAT drives the outcome, not HOW MUCH.
    """
    INCOME_MIX = "income_mix"
    DEDUCTION_MIX = "deduction_mix"
    CREDIT_ELIGIBILITY = "credit_eligibility"
    WITHHOLDING_PATTERN = "withholding_pattern"
    CAPITAL_GAINS = "capital_gains"
    BUSINESS_ACTIVITY = "business_activity"
    RETIREMENT_CONTRIBUTIONS = "retirement_contributions"
    DEPENDENT_SITUATION = "dependent_situation"


class DriverDirection(str, Enum):
    """Direction of impact - never magnitude."""
    PUSHES_TOWARD_REFUND = "pushes_toward_refund"
    PUSHES_TOWARD_OWED = "pushes_toward_owed"
    NEUTRAL = "neutral"


# =============================================================================
# OPPORTUNITY EXPOSURE ENUMS
# =============================================================================

class OpportunityCategory(str, Enum):
    """
    Opportunity categories - labels only, no specifics.
    These tell the prospect AREAS exist, not WHAT to do.
    """
    RETIREMENT = "retirement"
    BUSINESS_STRUCTURE = "business_structure"
    CHARITABLE = "charitable"
    EDUCATION = "education"
    DEPENDENTS = "dependents"
    HOUSING = "housing"
    HEALTH_SAVINGS = "health_savings"
    INVESTMENT_TAX = "investment_tax"
    FOREIGN_REPORTING = "foreign_reporting"
    CRYPTO_REPORTING = "crypto_reporting"
    STATE_TAX = "state_tax"
    OTHER = "other"


class OpportunitySeverity(str, Enum):
    """Relative importance - never dollar values."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =============================================================================
# SCENARIO EXPOSURE ENUMS
# =============================================================================

class ScenarioOutcomeShift(str, Enum):
    """Directional shift only - never amounts."""
    BETTER = "better"
    WORSE = "worse"
    NO_MEANINGFUL_CHANGE = "no_meaningful_change"
    UNKNOWN = "unknown"


# =============================================================================
# SUMMARY MESSAGE CODES
# =============================================================================

class SummaryMessageCode(str, Enum):
    """
    Pre-approved summary message codes.
    NO custom AI-generated language allowed.
    """
    STRAIGHTFORWARD_SITUATION = "straightforward_situation"
    MODERATE_COMPLEXITY = "moderate_complexity"
    COMPLEX_SITUATION = "complex_situation"
    MULTIPLE_OPPORTUNITIES = "multiple_opportunities"
    CPA_REVIEW_RECOMMENDED = "cpa_review_recommended"
    ADDITIONAL_INFO_NEEDED = "additional_info_needed"


# =============================================================================
# OUTPUT CONTRACTS
# =============================================================================

class ProspectOutcomeExposure(BaseModel):
    """
    Prospect-safe outcome exposure.

    RED LINE ENFORCEMENT:
    - outcome_type is directional, never exact
    - amount_band is coarse, never precise
    - confidence_band is qualitative, never percentage
    """
    outcome_type: OutcomeType
    amount_band: AmountBand
    confidence_band: ConfidenceBand
    disclaimer_code: DisclaimerCode = DisclaimerCode.DISCOVERY_ONLY

    class Config:
        frozen = True


class ProspectComplexityExposure(BaseModel):
    """
    Prospect-safe complexity exposure.

    RED LINE ENFORCEMENT:
    - reasons list is capped at 3 items
    - level is categorical, never scored
    """
    level: ComplexityLevel
    reasons: List[ComplexityReason] = Field(default_factory=list, max_length=3)

    @field_validator('reasons')
    @classmethod
    def enforce_max_reasons(cls, v):
        if len(v) > 3:
            raise ValueError("Maximum 3 complexity reasons allowed for prospect exposure")
        return v

    class Config:
        frozen = True


class DriverItem(BaseModel):
    """Single driver item - category and direction only."""
    category: DriverCategory
    rank: int = Field(ge=1, le=3)
    direction: DriverDirection

    class Config:
        frozen = True


class ProspectDriverExposure(BaseModel):
    """
    Prospect-safe driver exposure.

    RED LINE ENFORCEMENT:
    - top_drivers capped at 3 items
    - Only categories and directions, never amounts
    - Ranked 1-3, no scores
    """
    top_drivers: List[DriverItem] = Field(default_factory=list, max_length=3)

    @field_validator('top_drivers')
    @classmethod
    def enforce_max_drivers(cls, v):
        if len(v) > 3:
            raise ValueError("Maximum 3 drivers allowed for prospect exposure")
        # Ensure unique ranks
        ranks = [d.rank for d in v]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Driver ranks must be unique")
        return v

    class Config:
        frozen = True


class OpportunityLabel(BaseModel):
    """Single opportunity label - category only, no specifics."""
    category: OpportunityCategory
    severity: OpportunitySeverity

    class Config:
        frozen = True


class ProspectOpportunityExposure(BaseModel):
    """
    Prospect-safe opportunity exposure.

    RED LINE ENFORCEMENT:
    - visible list capped at 3 items
    - Only categories, never specific actions
    - hidden_count shows more exist without revealing what
    """
    total_flagged: int = Field(ge=0)
    visible: List[OpportunityLabel] = Field(default_factory=list, max_length=3)
    hidden_count: int = Field(ge=0)

    @field_validator('visible')
    @classmethod
    def enforce_max_visible(cls, v):
        if len(v) > 3:
            raise ValueError("Maximum 3 visible opportunities allowed for prospect exposure")
        return v

    class Config:
        frozen = True


class ScenarioComparison(BaseModel):
    """Single scenario comparison - direction only."""
    scenario_name: str = Field(max_length=50)
    outcome_shift: ScenarioOutcomeShift
    confidence_band: ConfidenceBand

    class Config:
        frozen = True


class ProspectScenarioExposure(BaseModel):
    """
    Prospect-safe scenario exposure.

    RED LINE ENFORCEMENT:
    - comparisons capped at 2 items
    - Only directional shifts, never dollar amounts
    """
    comparisons: List[ScenarioComparison] = Field(default_factory=list, max_length=2)

    @field_validator('comparisons')
    @classmethod
    def enforce_max_comparisons(cls, v):
        if len(v) > 2:
            raise ValueError("Maximum 2 scenario comparisons allowed for prospect exposure")
        return v

    class Config:
        frozen = True


class ProspectDiscoverySummary(BaseModel):
    """
    Complete prospect discovery summary.

    This is the ONLY output that should reach the prospect-facing layer.
    All internal data must be transformed through the appropriate
    transformer before being included here.

    RED LINE ENFORCEMENT:
    - All sub-components enforce their own limits
    - summary_message_code is pre-approved, not AI-generated
    - disclaimers are standard codes, not custom text
    """
    outcome: ProspectOutcomeExposure
    complexity: ProspectComplexityExposure
    drivers: ProspectDriverExposure
    opportunities: ProspectOpportunityExposure
    scenarios: ProspectScenarioExposure
    summary_message_code: SummaryMessageCode
    disclaimers: List[DisclaimerCode] = Field(default_factory=list)

    class Config:
        frozen = True
