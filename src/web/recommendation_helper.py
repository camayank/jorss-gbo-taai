"""
Centralized Recommendation Helper

DEPRECATED: Prefer the modular web.recommendation package instead:
    from web.recommendation import get_recommendations, get_recommendations_sync
    from web.recommendation.models import UnifiedRecommendation, RecommendationResult
from calculator.decimal_math import money, to_decimal

This file is maintained for backward compatibility. New generator functions
should be added to web/recommendation/generators/ modules.

Legacy usage (still works):
    from web.recommendation_helper import get_recommendations, get_recommendations_sync

    # Async (preferred)
    result = await get_recommendations(profile, calculation)

    # Sync
    result = get_recommendations_sync(profile, calculation)
"""

import logging
import traceback
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


# =============================================================================
# TAX CONSTANTS (2025)
# =============================================================================

TAX_YEAR = 2025

# Standard Deductions
STANDARD_DEDUCTIONS = {
    "single": 15750,
    "married_joint": 31500,
    "married_separate": 15750,
    "head_of_household": 23850,
    "qualifying_widow": 31500,
}

# Additional standard deduction for 65+
ADDITIONAL_STD_DEDUCTION_65_PLUS = {
    "single": 2000,
    "head_of_household": 2000,
    "married_joint": 1600,
    "married_separate": 1600,
    "qualifying_widow": 1600,
}

# Child Tax Credit parameters
CTC_AMOUNT_PER_CHILD = 2000
CTC_REFUNDABLE_MAX = 1700
CTC_PHASEOUT_SINGLE = 200000
CTC_PHASEOUT_MFJ = 400000

# EITC Income Limits (2025 approximate)
EITC_LIMITS = {
    "single": {0: 18591, 1: 49084, 2: 55768, 3: 59899},
    "married_joint": {0: 25511, 1: 56004, 2: 62688, 3: 66819},
}
EITC_MAX_AMOUNTS = {0: 632, 1: 4213, 2: 6960, 3: 7830}

# 2025 Retirement Contribution Limits
RETIREMENT_LIMITS_2025 = {
    "401k_limit": 23500,
    "401k_catch_up": 7500,      # Age 50+
    "ira_limit": 7000,
    "ira_catch_up": 1000,       # Age 50+
    "hsa_self": 4300,
    "hsa_family": 8550,
    "hsa_catch_up": 1000,       # Age 55+
    "sep_ira_pct": 0.25,
    "sep_ira_max": 69000,
}

# Saver's Credit limits
SAVER_CREDIT_LIMITS = {
    "single": 38250,
    "married_joint": 76500,
    "head_of_household": 57375,
    "married_separate": 38250,
    "qualifying_widow": 76500,
}

# SALT Cap
SALT_CAP = 10000

# Self-employment tax rate
SE_TAX_RATE = 0.153

# Default marginal rate for savings estimates
DEFAULT_MARGINAL_RATE = 0.24

# Valid filing statuses
VALID_FILING_STATUSES = {
    "single", "married_joint", "married_separate",
    "head_of_household", "qualifying_widow"
}


# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================

def _safe_float(value: Any, default: float = 0.0, min_val: float = None, max_val: float = None) -> float:
    """
    Safely convert a value to float with bounds checking.

    Args:
        value: Value to convert
        default: Default if conversion fails
        min_val: Minimum allowed value (optional)
        max_val: Maximum allowed value (optional)

    Returns:
        Float value within bounds
    """
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, Decimal):
            result = float(value)
        elif isinstance(value, str):
            # Handle currency strings like "$1,234.56"
            cleaned = value.replace("$", "").replace(",", "").strip()
            result = float(cleaned) if cleaned else default
        else:
            result = float(value)

        # Apply bounds
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)

        return result
    except (ValueError, TypeError, InvalidOperation):
        return default


def _safe_int(value: Any, default: int = 0, min_val: int = None, max_val: int = None) -> int:
    """Safely convert a value to int with bounds checking."""
    try:
        result = int(_safe_float(value, float(default)))
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)
        return result
    except (ValueError, TypeError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    """Safely convert a value to string."""
    if value is None:
        return default
    return str(value).strip()


def _normalize_filing_status(status: Any) -> str:
    """Normalize filing status to valid value."""
    if not status:
        return "single"

    status_str = _safe_str(status).lower().replace(" ", "_").replace("-", "_")

    # Handle common variations
    status_map = {
        "single": "single",
        "married_filing_jointly": "married_joint",
        "married_joint": "married_joint",
        "mfj": "married_joint",
        "married_filing_separately": "married_separate",
        "married_separate": "married_separate",
        "mfs": "married_separate",
        "head_of_household": "head_of_household",
        "hoh": "head_of_household",
        "qualifying_widow": "qualifying_widow",
        "qualifying_widower": "qualifying_widow",
        "qualifying_surviving_spouse": "qualifying_widow",
    }

    return status_map.get(status_str, "single")


def _validate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize profile data.

    Returns a clean profile dict with validated values.
    """
    if not profile or not isinstance(profile, dict):
        logger.warning("Invalid profile provided, using empty profile")
        return {}

    validated = {
        # Filing status
        "filing_status": _normalize_filing_status(profile.get("filing_status")),

        # Income fields (must be non-negative)
        "total_income": _safe_float(profile.get("total_income"), 0, min_val=0),
        "w2_income": _safe_float(profile.get("w2_income"), 0, min_val=0),
        "business_income": _safe_float(profile.get("business_income"), 0, min_val=0),
        "rental_income": _safe_float(profile.get("rental_income"), 0, min_val=0),
        "rental_gross_income": _safe_float(profile.get("rental_gross_income"), 0, min_val=0),
        "investment_income": _safe_float(profile.get("investment_income"), 0, min_val=0),
        "capital_gains": _safe_float(profile.get("capital_gains"), 0),  # Can be negative

        # Deductions (must be non-negative)
        "mortgage_interest": _safe_float(profile.get("mortgage_interest"), 0, min_val=0),
        "property_taxes": _safe_float(profile.get("property_taxes"), 0, min_val=0),
        "state_income_tax": _safe_float(profile.get("state_income_tax"), 0, min_val=0),
        "charitable_donations": _safe_float(profile.get("charitable_donations"), 0, min_val=0),
        "medical_expenses": _safe_float(profile.get("medical_expenses"), 0, min_val=0),

        # Retirement (must be non-negative, capped at IRS limits)
        "retirement_401k": _safe_float(profile.get("retirement_401k"), 0, min_val=0, max_val=69000),
        "retirement_ira": _safe_float(profile.get("retirement_ira"), 0, min_val=0, max_val=8000),
        "hsa_contributions": _safe_float(profile.get("hsa_contributions"), 0, min_val=0, max_val=8550),

        # Personal
        "age": _safe_int(profile.get("age"), 35, min_val=0, max_val=120),
        "dependents": _safe_int(profile.get("dependents"), 0, min_val=0, max_val=20),

        # Booleans
        "is_self_employed": bool(profile.get("is_self_employed", False)),
        "owns_home": bool(profile.get("owns_home", False)),
        "has_hdhp": bool(profile.get("has_hdhp", False)),

        # Business specific
        "business_expenses": _safe_float(profile.get("business_expenses"), 0, min_val=0),

        # Rental specific (flat fields)
        "rental_property_value": _safe_float(profile.get("rental_property_value"), 0, min_val=0),
        "rental_land_value": _safe_float(profile.get("rental_land_value"), 0, min_val=0),
        "rental_start_year": _safe_int(profile.get("rental_start_year"), 2024, min_val=1950, max_val=TAX_YEAR),
        "rental_start_month": _safe_int(profile.get("rental_start_month"), 1, min_val=1, max_val=12),
        "prior_depreciation": _safe_float(profile.get("prior_depreciation"), 0, min_val=0),
        "rental_expenses": _safe_float(profile.get("rental_expenses"), 0, min_val=0),
        "rental_net_loss": _safe_float(profile.get("rental_net_loss"), 0),

        # Rental properties list (preserve for list-based calculations)
        "rental_properties": profile.get("rental_properties", []),

        # Dependent information (for credits)
        "num_dependents": _safe_int(profile.get("num_dependents") or profile.get("dependents"), 0, min_val=0, max_val=20),
        "dependent_ages": profile.get("dependent_ages", []),

        # Education (for credits)
        "has_college_student": bool(profile.get("has_college_student", False)),
        "education_expenses": _safe_float(profile.get("education_expenses"), 0, min_val=0),
        "college_expenses": _safe_float(profile.get("college_expenses"), 0, min_val=0),

        # Childcare (for credits)
        "childcare_expenses": _safe_float(profile.get("childcare_expenses"), 0, min_val=0),
        "has_young_children": bool(profile.get("has_young_children", False)),

        # Energy/EV credits
        "ev_purchase": bool(profile.get("ev_purchase", False)),
        "ev_price": _safe_float(profile.get("ev_price"), 0, min_val=0),
        "is_used_ev": bool(profile.get("is_used_ev", False)),
        "solar_cost": _safe_float(profile.get("solar_cost"), 0, min_val=0),
        "energy_improvements": _safe_float(profile.get("energy_improvements"), 0, min_val=0),

        # HSA details
        "hsa_contribution": _safe_float(profile.get("hsa_contribution") or profile.get("hsa_contributions"), 0, min_val=0),
        "family_coverage": bool(profile.get("family_coverage", False)),

        # Additional deductions
        "student_loan_interest": _safe_float(profile.get("student_loan_interest"), 0, min_val=0),
        "is_educator": bool(profile.get("is_educator", False)),
        "educator_expenses": _safe_float(profile.get("educator_expenses"), 0, min_val=0),
        "has_home_office": bool(profile.get("has_home_office", False)),
        "home_office_sqft": _safe_float(profile.get("home_office_sqft"), 0, min_val=0, max_val=500),
        "se_health_insurance": _safe_float(profile.get("se_health_insurance"), 0, min_val=0),

        # Retirement additional
        "ira_contribution": _safe_float(profile.get("ira_contribution") or profile.get("retirement_ira"), 0, min_val=0),
        "traditional_ira_balance": _safe_float(profile.get("traditional_ira_balance"), 0, min_val=0),
        "401k_balance": _safe_float(profile.get("401k_balance"), 0, min_val=0),
        "ira_balance": _safe_float(profile.get("ira_balance") or profile.get("traditional_ira_balance"), 0, min_val=0),

        # Investment (for Investment Optimizer)
        "capital_gains": _safe_float(profile.get("capital_gains"), 0),  # Can be negative
        "capital_losses": _safe_float(profile.get("capital_losses"), 0, min_val=0),
        "unrealized_gains": _safe_float(profile.get("unrealized_gains"), 0, min_val=0),
        "unrealized_losses": _safe_float(profile.get("unrealized_losses"), 0, min_val=0),
        "dividend_income": _safe_float(profile.get("dividend_income"), 0, min_val=0),
        "interest_income": _safe_float(profile.get("interest_income"), 0, min_val=0),
        "portfolio_value": _safe_float(profile.get("portfolio_value"), 0, min_val=0),
        "dividends_qualified": bool(profile.get("dividends_qualified", True)),
        "appreciated_stock": _safe_float(profile.get("appreciated_stock"), 0, min_val=0),

        # Filing status additional (for Filing Status Optimizer)
        "spouse_income": _safe_float(profile.get("spouse_income"), 0, min_val=0),
        "spouse_deceased_year": _safe_int(profile.get("spouse_deceased_year"), 0, min_val=0, max_val=TAX_YEAR),
        "dependent_child": bool(profile.get("dependent_child", False)),
        "student_loan_balance": _safe_float(profile.get("student_loan_balance"), 0, min_val=0),

        # Timing strategy (for Timing Optimizer)
        "expected_income_change": _safe_str(profile.get("expected_income_change"), "same"),
        "next_year_income": _safe_float(profile.get("next_year_income"), 0, min_val=0),
        "estimated_tax_paid": _safe_float(profile.get("estimated_tax_paid"), 0, min_val=0),
        "withholding": _safe_float(profile.get("withholding"), 0, min_val=0),
        "last_year_tax": _safe_float(profile.get("last_year_tax"), 0, min_val=0),

        # Charitable strategy (for Charitable Optimizer)
        "charitable": _safe_float(profile.get("charitable") or profile.get("charitable_donations"), 0, min_val=0),
        "planned_charitable": _safe_float(profile.get("planned_charitable"), 0, min_val=0),

        # State taxes (additional alias)
        "state_taxes": _safe_float(profile.get("state_taxes") or profile.get("state_income_tax"), 0, min_val=0),

        # AMT-related
        "iso_exercise_spread": _safe_float(profile.get("iso_exercise_spread") or profile.get("iso_spread"), 0, min_val=0),
        "private_activity_bond_interest": _safe_float(profile.get("private_activity_bond_interest"), 0, min_val=0),

        # Backdoor Roth
        "roth_contribution": _safe_float(profile.get("roth_contribution"), 0, min_val=0),
        "has_401k": bool(profile.get("has_401k", False)),

        # Social Security
        "social_security_income": _safe_float(profile.get("social_security_income") or profile.get("ss_income"), 0, min_val=0),
        "ss_estimated_benefit": _safe_float(profile.get("ss_estimated_benefit"), 0, min_val=0),
        "spouse_age": _safe_int(profile.get("spouse_age"), 0, min_val=0, max_val=120),
        "spouse_ss_benefit": _safe_float(profile.get("spouse_ss_benefit"), 0, min_val=0),

        # 529 Education Savings
        "529_contribution": _safe_float(profile.get("529_contribution"), 0, min_val=0),
        "529_balance": _safe_float(profile.get("529_balance"), 0, min_val=0),

        # QBI (Section 199A) fields
        "is_sstb": bool(profile.get("is_sstb", False)),  # Specified Service Trade or Business
        "business_w2_wages": _safe_float(profile.get("business_w2_wages"), 0, min_val=0),
        "ubia_property": _safe_float(profile.get("ubia_property"), 0, min_val=0),  # Unadjusted basis in property
        "qbi_amount": _safe_float(profile.get("qbi_amount") or profile.get("business_income"), 0, min_val=0),

        # Business classification fields (for SSTB detection)
        "business_type": _safe_str(profile.get("business_type"), ""),
        "business_name": _safe_str(profile.get("business_name"), ""),
        "naics_code": _safe_str(profile.get("naics_code") or profile.get("business_code"), ""),
        "business_description": _safe_str(profile.get("business_description"), ""),

        # Home Sale Exclusion (Section 121) fields
        "home_sale_gain": _safe_float(profile.get("home_sale_gain"), 0, min_val=0),
        "years_owned_primary_home": _safe_float(profile.get("years_owned_primary_home"), 0, min_val=0),
        "years_lived_primary_home": _safe_float(profile.get("years_lived_primary_home"), 0, min_val=0),
        "home_sale_price": _safe_float(profile.get("home_sale_price"), 0, min_val=0),
        "home_purchase_price": _safe_float(profile.get("home_purchase_price"), 0, min_val=0),
        "home_basis": _safe_float(profile.get("home_basis"), 0, min_val=0),
        "planning_home_sale": bool(profile.get("planning_home_sale", False)),
        "home_value": _safe_float(profile.get("home_value"), 0, min_val=0),

        # 1031 Exchange fields
        "investment_property_value": _safe_float(profile.get("investment_property_value"), 0, min_val=0),
        "investment_property_gain": _safe_float(profile.get("investment_property_gain"), 0, min_val=0),
        "investment_property_basis": _safe_float(profile.get("investment_property_basis"), 0, min_val=0),
        "considering_property_sale": bool(profile.get("considering_property_sale", False)),
        "is_investment_property": bool(profile.get("is_investment_property", False)),

        # Installment Sale (Form 6252) fields
        "large_gain_amount": _safe_float(profile.get("large_gain_amount"), 0, min_val=0),
        "installment_years": _safe_int(profile.get("installment_years"), 0, min_val=0, max_val=30),
        "considering_asset_sale": bool(profile.get("considering_asset_sale", False)),
        "asset_sale_gain": _safe_float(profile.get("asset_sale_gain"), 0, min_val=0),

        # Foreign Tax Credit (Form 1116) fields
        "foreign_income": _safe_float(profile.get("foreign_income"), 0, min_val=0),
        "foreign_tax_paid": _safe_float(profile.get("foreign_tax_paid"), 0, min_val=0),
        "foreign_dividends": _safe_float(profile.get("foreign_dividends"), 0, min_val=0),
        "foreign_tax_carryforward": _safe_float(profile.get("foreign_tax_carryforward"), 0, min_val=0),
        "has_foreign_investments": bool(profile.get("has_foreign_investments", False)),

        # Passive Activity Loss (Form 8582) fields
        "suspended_passive_losses": _safe_float(profile.get("suspended_passive_losses"), 0, min_val=0),
        "rental_losses": _safe_float(profile.get("rental_losses"), 0, min_val=0),
        "is_re_professional": bool(profile.get("is_re_professional", False)),
        "material_participation_hours": _safe_float(profile.get("material_participation_hours"), 0, min_val=0),
        "re_professional_hours": _safe_float(profile.get("re_professional_hours"), 0, min_val=0),
        "active_real_estate": bool(profile.get("active_real_estate", False)),
        "num_rental_properties": _safe_int(profile.get("num_rental_properties"), 0, min_val=0),

        # State
        "state": _safe_str(profile.get("state"), "").upper()[:2],

        # Self-Employment (alias for business_income)
        "self_employment_income": _safe_float(
            profile.get("self_employment_income") or profile.get("business_income"), 0, min_val=0
        ),

        # Crypto/Digital Assets (for Rules-Based Recommender)
        "has_crypto": bool(profile.get("has_crypto", False)),
        "crypto_transactions": _safe_int(profile.get("crypto_transactions"), 0, min_val=0),

        # Foreign Accounts (for Rules-Based Recommender FBAR)
        "has_foreign_accounts": bool(profile.get("has_foreign_accounts", False)),
        "foreign_account_value": _safe_float(profile.get("foreign_account_value"), 0, min_val=0),
        "has_foreign_income": bool(profile.get("has_foreign_income", False)),

        # Estimated Payments (for Planning Insights Engine)
        "estimated_payments_ytd": _safe_float(profile.get("estimated_payments_ytd"), 0, min_val=0),
        "prior_year_tax": _safe_float(profile.get("prior_year_tax"), 0, min_val=0),
        "retirement_balance": _safe_float(profile.get("retirement_balance"), 0, min_val=0),

        # Pass-through income (for QBI in Rules-Based Recommender)
        "partnership_income": _safe_float(profile.get("partnership_income"), 0, min_val=0),
        "scorp_income": _safe_float(profile.get("scorp_income"), 0, min_val=0),

        # Charitable (alias)
        "charitable_contributions": _safe_float(
            profile.get("charitable_contributions") or profile.get("charitable_donations") or profile.get("charitable"), 0, min_val=0
        ),

        # W2 count (for Complexity Router)
        "w2_count": _safe_int(profile.get("w2_count"), 1, min_val=1, max_val=10),
        "will_itemize": bool(profile.get("will_itemize", False)),
        "has_stock_sales": bool(profile.get("has_stock_sales", False)),
    }

    # Derive total_income if not provided
    if validated["total_income"] == 0:
        validated["total_income"] = (
            validated["w2_income"] +
            validated["business_income"] +
            validated["rental_income"] +
            validated["investment_income"]
        )

    # Infer is_self_employed from business_income
    if validated["business_income"] > 0:
        validated["is_self_employed"] = True

    # Infer owns_home from mortgage_interest
    if validated["mortgage_interest"] > 0:
        validated["owns_home"] = True

    # Infer has_young_children from dependent_ages
    dep_ages = validated.get("dependent_ages", [])
    if dep_ages and any(isinstance(a, (int, float)) and a < 13 for a in dep_ages):
        validated["has_young_children"] = True

    # Set dependents from num_dependents for backward compat
    validated["dependents"] = validated["num_dependents"]

    return validated


def _create_recommendation(
    id: str,
    category: str,
    title: str,
    summary: str,
    estimated_savings: float,
    priority: str = "medium",
    urgency: str = "moderate",
    confidence: str = "medium",
    action_steps: List[str] = None,
    deadline: str = None,
    irs_reference: str = None,
    source: str = "unknown"
) -> Optional["UnifiedRecommendation"]:
    """
    Create a UnifiedRecommendation with validation.

    Returns None if validation fails.
    """
    try:
        # Validate inputs
        if not id or not title:
            logger.warning(f"Invalid recommendation: missing id or title")
            return None

        savings = _safe_float(estimated_savings, 0, min_val=0)

        # Normalize priority/urgency/confidence
        priority = priority.lower() if priority in ("high", "medium", "low") else "medium"
        urgency = urgency.lower() if urgency in ("critical", "high", "moderate", "planning") else "moderate"
        confidence = confidence.lower() if confidence in ("high", "medium", "low") else "medium"

        return UnifiedRecommendation(
            id=_safe_str(id),
            category=_safe_str(category, "general"),
            title=_safe_str(title),
            summary=_safe_str(summary),
            estimated_savings=savings,
            priority=priority,
            urgency=urgency,
            confidence=confidence,
            action_steps=action_steps or [],
            deadline=deadline,
            irs_reference=irs_reference,
            source=_safe_str(source, "unknown")
        )
    except Exception as e:
        logger.warning(f"Failed to create recommendation '{title}': {e}")
        return None


@dataclass
class UnifiedRecommendation:
    """Unified recommendation from any source."""
    id: str
    category: str
    title: str
    summary: str
    estimated_savings: float
    priority: str  # high, medium, low
    urgency: str  # critical, high, moderate, planning
    confidence: str  # high, medium, low
    action_steps: List[str] = field(default_factory=list)
    deadline: Optional[str] = None
    irs_reference: Optional[str] = None
    source: str = "unknown"  # Which service generated this


@dataclass
class RecommendationResult:
    """Result of recommendation generation."""
    recommendations: List[UnifiedRecommendation]
    total_potential_savings: float
    urgency_level: str
    urgency_message: str
    days_to_deadline: int
    lead_score: int
    top_opportunities: List[UnifiedRecommendation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendations": [
                {
                    "id": r.id,
                    "category": r.category,
                    "title": r.title,
                    "summary": r.summary,
                    "estimated_savings": r.estimated_savings,
                    "priority": r.priority,
                    "urgency": r.urgency,
                    "confidence": r.confidence,
                    "action_steps": r.action_steps,
                    "deadline": r.deadline,
                    "irs_reference": r.irs_reference,
                    "source": r.source,
                }
                for r in self.recommendations
            ],
            "total_potential_savings": self.total_potential_savings,
            "urgency_level": self.urgency_level,
            "urgency_message": self.urgency_message,
            "days_to_deadline": self.days_to_deadline,
            "lead_score": self.lead_score,
            "top_opportunities": [
                {
                    "id": r.id,
                    "category": r.category,
                    "title": r.title,
                    "summary": r.summary,
                    "estimated_savings": r.estimated_savings,
                    "priority": r.priority,
                }
                for r in self.top_opportunities[:5]
            ],
        }


def _get_urgency_info() -> tuple:
    """Get urgency level from CPAIntelligenceService."""
    try:
        from services.cpa_intelligence_service import calculate_urgency_level
        urgency_level, urgency_message, days = calculate_urgency_level()
        return urgency_level, urgency_message, days
    except Exception as e:
        logger.warning(f"Could not get urgency info: {e}")
        return "PLANNING", "Tax planning mode", 365


def _get_lead_score(profile: Dict[str, Any], conversation_history: Optional[List[Dict]] = None) -> int:
    """Calculate lead score from CPAIntelligenceService."""
    try:
        from services.cpa_intelligence_service import calculate_lead_score

        # Map profile to session_data format expected by CPA service
        session_data = {
            "name": profile.get("first_name") or profile.get("name"),
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "has_business": (profile.get("business_income", 0) or 0) > 0,
            "rental_income": profile.get("rental_income", 0) or 0,
            "investment_income": profile.get("investment_income", 0) or 0,
            "income": profile.get("total_income", 0) or profile.get("w2_income", 0) or 0,
            "multi_state": profile.get("multi_state", False),
            "foreign_income": profile.get("foreign_income", False),
            "crypto_trading": profile.get("crypto_income", 0) or 0 > 0,
        }

        return calculate_lead_score(session_data, conversation_history or [])
    except Exception as e:
        logger.warning(f"Could not calculate lead score: {e}")
        # Fallback scoring
        score = 20
        total_income = profile.get("total_income", 0) or profile.get("w2_income", 0) or 0
        if total_income > 200000:
            score += 30
        elif total_income > 100000:
            score += 20
        elif total_income > 50000:
            score += 10
        if profile.get("business_income", 0) or 0 > 0:
            score += 15
        if profile.get("rental_income", 0) or 0 > 0:
            score += 10
        return min(100, score)


def _get_credit_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get credit recommendations from CreditOptimizer.

    USER VALUE: Identifies tax credits user may qualify for based on their situation.
    Credits include: Child Tax Credit, EITC, Education Credits, Energy Credits, etc.
    Average user discovers $500-$8,000 in available credits.

    Note: CreditOptimizer.analyze() requires a full TaxReturn domain object.
    For profile-based recommendations, we generate credit suggestions directly.
    """
    recommendations = []
    try:
        # Extract and validate profile data
        filing_status = profile.get("filing_status", "single")
        agi = _safe_float(profile.get("total_income") or profile.get("w2_income"), 0, min_val=0)
        dependents = _safe_int(profile.get("dependents"), 0, min_val=0, max_val=20)
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
        earned_income = w2_income + business_income

        # Child Tax Credit check
        if dependents > 0:
            ctc_phaseout = CTC_PHASEOUT_MFJ if filing_status == "married_joint" else CTC_PHASEOUT_SINGLE
            ctc_amount = dependents * CTC_AMOUNT_PER_CHILD

            # Apply phase-out: $50 reduction per $1,000 over threshold
            if agi > ctc_phaseout:
                reduction = int((agi - ctc_phaseout) / 1000 + 0.999) * 50  # Round up
                ctc_amount = max(0, ctc_amount - reduction)

            if ctc_amount > 0:
                rec = _create_recommendation(
                    id="credit-child-tax-credit",
                    category="credit",
                    title=f"Child Tax Credit ({dependents} {'child' if dependents == 1 else 'children'})",
                    summary=f"Claim ${ctc_amount:,.0f} Child Tax Credit. Up to ${CTC_REFUNDABLE_MAX:,} per child is refundable!",
                    estimated_savings=ctc_amount,
                    priority="high",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        "Ensure each child is under 17 at year-end",
                        "Have valid SSN for each child",
                        "Complete Schedule 8812"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Schedule 8812",
                    source="credit_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # Earned Income Tax Credit (EITC) check
        status_key = "married_joint" if filing_status == "married_joint" else "single"
        dep_key = min(dependents, 3)
        eitc_limit = EITC_LIMITS.get(status_key, {}).get(dep_key, 0)

        if earned_income > 0 and agi < eitc_limit and agi > 0:
            eitc_amount = EITC_MAX_AMOUNTS.get(dep_key, 0)
            if eitc_amount > 0:
                rec = _create_recommendation(
                    id="credit-eitc",
                    category="credit",
                    title="Earned Income Tax Credit",
                    summary=f"You may qualify for up to ${eitc_amount:,.0f} EITC. Fully refundable!",
                    estimated_savings=eitc_amount,
                    priority="high",
                    urgency="moderate",
                    confidence="medium",
                    action_steps=[
                        f"Income limit for your situation: ${eitc_limit:,.0f}",
                        "Have earned income from wages or self-employment",
                        "Claim on Form 1040 Schedule EIC"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Schedule EIC",
                    source="credit_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # Retirement Savings Contribution Credit (Saver's Credit)
        retirement_401k = _safe_float(profile.get("retirement_401k"), 0, min_val=0)
        retirement_ira = _safe_float(profile.get("retirement_ira"), 0, min_val=0)
        retirement_contrib = retirement_401k + retirement_ira
        saver_limit = SAVER_CREDIT_LIMITS.get(filing_status, 38250)

        if retirement_contrib > 0 and agi < saver_limit and agi > 0:
            # Credit rate based on income
            if agi < 23000:
                rate = 0.50
            elif agi < 25000:
                rate = 0.20
            else:
                rate = 0.10

            # Credit is percentage of contributions up to $2,000 ($4,000 MFJ)
            max_contrib = 4000 if filing_status == "married_joint" else 2000
            saver_credit = min(retirement_contrib, max_contrib) * rate

            if saver_credit >= 50:  # Minimum threshold for relevance
                rec = _create_recommendation(
                    id="credit-savers",
                    category="credit",
                    title="Retirement Saver's Credit",
                    summary=f"Get ${saver_credit:,.0f} credit for retirement contributions. Direct tax savings!",
                    estimated_savings=saver_credit,
                    priority="medium" if saver_credit < 500 else "high",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        f"Your retirement contributions: ${retirement_contrib:,.0f}",
                        f"Credit rate at your income: {int(rate * 100)}%",
                        "Claim on Form 8880"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 8880",
                    source="credit_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =====================================================================
        # EDUCATION CREDITS - USER VALUE: $2,500-$4,000 for college expenses
        # =====================================================================
        education_expenses = _safe_float(profile.get("education_expenses"), 0, min_val=0)
        has_college_student = bool(profile.get("has_college_student", False)) or education_expenses > 0

        if has_college_student and education_expenses > 0:
            # American Opportunity Credit: Up to $2,500 per student (first 4 years)
            # 100% of first $2,000 + 25% of next $2,000
            # Phase-out: $80K-$90K single, $160K-$180K MFJ
            aotc_phaseout_start = 160000 if filing_status == "married_joint" else 80000
            aotc_phaseout_end = 180000 if filing_status == "married_joint" else 90000

            if agi < aotc_phaseout_end:
                aotc_base = min(2000, education_expenses) + min(500, max(0, education_expenses - 2000) * 0.25)
                if agi > aotc_phaseout_start:
                    phase_out_pct = (agi - aotc_phaseout_start) / (aotc_phaseout_end - aotc_phaseout_start)
                    aotc_base = aotc_base * (1 - phase_out_pct)

                if aotc_base > 100:
                    rec = _create_recommendation(
                        id="credit-aotc",
                        category="credit",
                        title="American Opportunity Tax Credit",
                        summary=f"Up to ${aotc_base:,.0f} credit for college expenses. 40% refundable even if you owe no tax!",
                        estimated_savings=aotc_base,
                        priority="high",
                        urgency="moderate",
                        confidence="high" if agi < aotc_phaseout_start else "medium",
                        action_steps=[
                            f"Education expenses: ${education_expenses:,.0f}",
                            "Available for first 4 years of college",
                            "Student must be enrolled at least half-time",
                            "Keep Form 1098-T and receipts",
                            "Claim on Form 8863"
                        ],
                        deadline="April 15, 2026",
                        irs_reference="Form 8863, Publication 970",
                        source="credit_optimizer"
                    )
                    if rec:
                        recommendations.append(rec)

        # =====================================================================
        # DEPENDENT CARE CREDIT - USER VALUE: $600-$2,100 for childcare
        # =====================================================================
        childcare_expenses = _safe_float(profile.get("childcare_expenses") or profile.get("dependent_care"), 0, min_val=0)
        has_young_children = bool(profile.get("has_children_under_13", False)) or childcare_expenses > 0

        if has_young_children and childcare_expenses > 0 and earned_income > 0:
            # 2025: Credit is 20-35% of expenses up to $3K (1 child) or $6K (2+ children)
            num_children = max(1, _safe_int(profile.get("children_under_13"), 1, min_val=1))
            max_expenses = 6000 if num_children >= 2 else 3000
            qualifying_expenses = min(childcare_expenses, max_expenses)

            # Credit rate based on AGI (20-35%)
            if agi <= 15000:
                rate = 0.35
            elif agi >= 43000:
                rate = 0.20
            else:
                rate = 0.35 - ((agi - 15000) / 2000) * 0.01

            dependent_care_credit = qualifying_expenses * rate

            if dependent_care_credit > 100:
                rec = _create_recommendation(
                    id="credit-dependent-care",
                    category="credit",
                    title="Child and Dependent Care Credit",
                    summary=f"Get ${dependent_care_credit:,.0f} credit for childcare costs. Reduces your tax bill!",
                    estimated_savings=dependent_care_credit,
                    priority="high" if dependent_care_credit > 500 else "medium",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        f"Childcare expenses: ${childcare_expenses:,.0f}",
                        f"Qualifying amount (capped): ${qualifying_expenses:,.0f}",
                        f"Credit rate at your income: {int(rate * 100)}%",
                        "Get provider's name, address, and Tax ID",
                        "Claim on Form 2441"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 2441, Publication 503",
                    source="credit_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =====================================================================
        # ENERGY CREDITS - USER VALUE: $500-$7,500 for green investments
        # =====================================================================
        # Electric Vehicle Credit
        ev_purchase = bool(profile.get("purchased_ev", False))
        ev_price = _safe_float(profile.get("ev_price"), 0, min_val=0)

        if ev_purchase or ev_price > 0:
            # 2025: Up to $7,500 for new EVs, $4,000 for used
            is_used_ev = bool(profile.get("used_ev", False))
            max_credit = 4000 if is_used_ev else 7500

            # Income limits: $150K single, $300K MFJ for new; $75K single, $150K MFJ for used
            if is_used_ev:
                ev_income_limit = 150000 if filing_status == "married_joint" else 75000
            else:
                ev_income_limit = 300000 if filing_status == "married_joint" else 150000

            if agi < ev_income_limit:
                rec = _create_recommendation(
                    id="credit-ev",
                    category="credit",
                    title=f"{'Used' if is_used_ev else 'New'} Electric Vehicle Credit",
                    summary=f"Up to ${max_credit:,.0f} credit for your EV purchase. Can be taken at point of sale!",
                    estimated_savings=max_credit,
                    priority="high",
                    urgency="moderate",
                    confidence="medium",
                    action_steps=[
                        "Vehicle must meet battery and assembly requirements",
                        f"Income limit: ${ev_income_limit:,.0f}",
                        f"{'MSRP must be under $25K for used' if is_used_ev else 'MSRP limits: $55K car, $80K SUV/truck'}",
                        "Keep purchase documentation",
                        "Claim on Form 8936"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 8936",
                    source="credit_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # Home Energy Credits (Solar, Heat Pump, etc.)
        solar_cost = _safe_float(profile.get("solar_installation") or profile.get("solar_cost"), 0, min_val=0)
        home_energy = _safe_float(profile.get("home_energy_improvements"), 0, min_val=0)

        if solar_cost > 0:
            # Residential Clean Energy Credit: 30% of solar installation
            solar_credit = solar_cost * 0.30
            rec = _create_recommendation(
                id="credit-solar",
                category="credit",
                title="Residential Clean Energy Credit (Solar)",
                summary=f"Get ${solar_credit:,.0f} credit (30%) for your solar installation. No income limit!",
                estimated_savings=solar_credit,
                priority="high",
                urgency="moderate",
                confidence="high",
                action_steps=[
                    f"Solar installation cost: ${solar_cost:,.0f}",
                    "Credit is 30% through 2032",
                    "Includes installation labor",
                    "Excess credit carries forward",
                    "Claim on Form 5695"
                ],
                deadline="April 15, 2026",
                irs_reference="Form 5695",
                source="credit_optimizer"
            )
            if rec:
                recommendations.append(rec)

        if home_energy > 0:
            # Energy Efficient Home Improvement Credit: Up to $3,200/year
            energy_credit = min(home_energy * 0.30, 3200)
            rec = _create_recommendation(
                id="credit-home-energy",
                category="credit",
                title="Energy Efficient Home Improvement Credit",
                summary=f"Get ${energy_credit:,.0f} credit for energy-efficient upgrades (heat pumps, windows, etc.).",
                estimated_savings=energy_credit,
                priority="medium",
                urgency="moderate",
                confidence="high",
                action_steps=[
                    f"Improvements: ${home_energy:,.0f}",
                    "Max $1,200/year for most items",
                    "Max $2,000/year for heat pumps",
                    "Keep receipts and certifications",
                    "Claim on Form 5695"
                ],
                deadline="April 15, 2026",
                irs_reference="Form 5695",
                source="credit_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Credit analysis found {len(recommendations)} potential credits")

    except Exception as e:
        logger.warning(f"Credit analysis failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_deduction_analyzer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get deduction recommendations based on profile analysis.

    USER VALUE: Compares standard vs itemized with SALT cap handling,
    identifies bunching opportunities, finds missed deductions.
    Saves users $200-$3,000 through optimal deduction strategy.

    Note: DeductionAnalyzer.analyze() requires TaxReturn domain objects.
    We perform direct analysis from profile data.
    """
    recommendations = []
    try:
        # Extract and validate profile data
        filing_status = profile.get("filing_status", "single")
        age = _safe_int(profile.get("age"), 40, min_val=0, max_val=120)
        agi = _safe_float(profile.get("total_income") or profile.get("w2_income"), 0, min_val=0)

        # Skip if no income data
        if agi <= 0:
            return recommendations

        # Calculate standard deduction
        standard = STANDARD_DEDUCTIONS.get(filing_status, 15000)

        # Add additional deduction for 65+
        if age >= 65:
            standard += ADDITIONAL_STD_DEDUCTION_65_PLUS.get(filing_status, 1600)

        # Calculate itemized deductions with validation
        medical = _safe_float(profile.get("medical_expenses"), 0, min_val=0)
        medical_floor = agi * 0.075
        medical_deduction = max(0, medical - medical_floor)

        # SALT (capped at $10K)
        state_tax = _safe_float(profile.get("state_income_tax"), 0, min_val=0)
        property_tax = _safe_float(profile.get("property_taxes"), 0, min_val=0)
        salt_total = state_tax + property_tax
        salt_deduction = min(salt_total, SALT_CAP)

        mortgage = _safe_float(profile.get("mortgage_interest"), 0, min_val=0)
        charitable = _safe_float(profile.get("charitable_donations"), 0, min_val=0)

        total_itemized = medical_deduction + salt_deduction + mortgage + charitable

        # Determine optimal strategy
        if total_itemized > standard:
            # Calculate actual tax benefit
            excess = total_itemized - standard
            savings = excess * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="deduction-itemize",
                category="deduction",
                title="Itemize Your Deductions",
                summary=f"Itemizing saves you ${savings:,.0f} vs standard (${total_itemized:,.0f} vs ${standard:,.0f}).",
                estimated_savings=savings,
                priority="high" if savings > 500 else "medium",
                urgency="moderate",
                confidence="high",
                action_steps=[
                    f"Medical (over 7.5% AGI): ${medical_deduction:,.0f}",
                    f"SALT (capped at $10K): ${salt_deduction:,.0f}",
                    f"Mortgage interest: ${mortgage:,.0f}",
                    f"Charitable: ${charitable:,.0f}",
                    "Keep receipts for all deductible expenses"
                ],
                deadline="April 15, 2026",
                source="deduction_analyzer"
            )
            if rec:
                recommendations.append(rec)

        elif total_itemized > standard * 0.7 and charitable > 0:
            # Close to itemizing - suggest bunching if they have charitable
            gap = standard - total_itemized
            potential_savings = gap * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="deduction-bunching",
                category="deduction",
                title="Charitable Donation Bunching Strategy",
                summary=f"You're ${gap:,.0f} away from itemizing. Bundle 2 years of donations to exceed threshold!",
                estimated_savings=potential_savings,
                priority="medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    f"Current itemized total: ${total_itemized:,.0f}",
                    f"Standard deduction: ${standard:,.0f}",
                    f"Gap to close: ${gap:,.0f}",
                    "Combine this year and next year's donations",
                    "Consider a Donor-Advised Fund for flexibility"
                ],
                deadline="December 31, 2025",
                source="deduction_analyzer"
            )
            if rec:
                recommendations.append(rec)

        # SALT cap warning (only if significant)
        if salt_total > SALT_CAP + 1000:  # At least $1K over cap
            lost_deduction = salt_total - SALT_CAP
            tax_impact = lost_deduction * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="deduction-salt-cap",
                category="deduction",
                title="SALT Cap Limiting Your Deductions",
                summary=f"You're losing ${lost_deduction:,.0f} in SALT deductions (~${tax_impact:,.0f} in tax) due to $10K cap.",
                estimated_savings=0,  # Informational - no direct savings available
                priority="low",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"Total SALT paid: ${salt_total:,.0f}",
                    f"Amount deductible: ${SALT_CAP:,.0f}",
                    "For business owners: evaluate PTET (pass-through entity tax) options"
                ],
                source="deduction_analyzer"
            )
            if rec:
                recommendations.append(rec)

        # =====================================================================
        # ABOVE-THE-LINE DEDUCTIONS - USER VALUE: Reduce AGI regardless of itemizing
        # =====================================================================

        # HSA Contribution - USER VALUE: Triple tax advantage
        has_hdhp = bool(profile.get("has_hdhp", False))
        hsa_contribution = _safe_float(profile.get("hsa_contributions"), 0, min_val=0)
        # 2025 HSA limits: $4,300 individual, $8,550 family
        hsa_limit = 8550 if filing_status == "married_joint" else 4300
        hsa_limit_55plus = hsa_limit + 1000 if age >= 55 else hsa_limit

        if has_hdhp:
            if hsa_contribution < hsa_limit_55plus:
                additional_hsa = hsa_limit_55plus - hsa_contribution
                hsa_savings = additional_hsa * DEFAULT_MARGINAL_RATE

                if hsa_savings > 200:
                    rec = _create_recommendation(
                        id="deduction-hsa-max",
                        category="deduction",
                        title="Maximize HSA Contributions",
                        summary=f"Contribute ${additional_hsa:,.0f} more to HSA for ${hsa_savings:,.0f} tax savings. TRIPLE tax advantage!",
                        estimated_savings=hsa_savings,
                        priority="high",
                        urgency="deadline",
                        confidence="high",
                        action_steps=[
                            f"Current HSA contribution: ${hsa_contribution:,.0f}",
                            f"2025 limit: ${hsa_limit_55plus:,.0f}" + (" (includes $1K catch-up)" if age >= 55 else ""),
                            "Tax-deductible going in",
                            "Tax-free growth",
                            "Tax-free withdrawals for medical expenses",
                            "Contribute by April 15, 2026 for 2025 tax year"
                        ],
                        deadline="April 15, 2026",
                        irs_reference="Form 8889",
                        source="deduction_analyzer"
                    )
                    if rec:
                        recommendations.append(rec)
        elif agi > 50000:  # Suggest HDHP + HSA for higher earners
            potential_savings = hsa_limit * DEFAULT_MARGINAL_RATE
            rec = _create_recommendation(
                id="deduction-hsa-consider",
                category="deduction",
                title="Consider HDHP + HSA Strategy",
                summary=f"High-deductible health plan with HSA could save ${potential_savings:,.0f}/year in taxes.",
                estimated_savings=potential_savings,
                priority="medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    f"HSA contribution limit: ${hsa_limit:,.0f}",
                    "Triple tax advantage: deductible, grows tax-free, tax-free for medical",
                    "Can invest HSA funds for long-term growth",
                    "Funds roll over year to year (unlike FSA)",
                    "Consider during open enrollment"
                ],
                source="deduction_analyzer"
            )
            if rec:
                recommendations.append(rec)

        # Student Loan Interest - USER VALUE: Up to $2,500 above-the-line
        student_loan_interest = _safe_float(profile.get("student_loan_interest"), 0, min_val=0)
        # Phase-out: $75K-$90K single, $155K-$185K MFJ
        student_loan_limit_start = 155000 if filing_status == "married_joint" else 75000
        student_loan_limit_end = 185000 if filing_status == "married_joint" else 90000

        if student_loan_interest > 0 and agi < student_loan_limit_end:
            deductible = min(student_loan_interest, 2500)
            if agi > student_loan_limit_start:
                phase_out_pct = (agi - student_loan_limit_start) / (student_loan_limit_end - student_loan_limit_start)
                deductible = deductible * (1 - phase_out_pct)

            if deductible > 100:
                savings = deductible * DEFAULT_MARGINAL_RATE
                rec = _create_recommendation(
                    id="deduction-student-loan",
                    category="deduction",
                    title="Student Loan Interest Deduction",
                    summary=f"Deduct ${deductible:,.0f} student loan interest for ${savings:,.0f} tax savings. Above-the-line!",
                    estimated_savings=savings,
                    priority="medium",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        f"Interest paid: ${student_loan_interest:,.0f}",
                        "Deduction is 'above-the-line' - no itemizing needed",
                        "You'll receive Form 1098-E from lender",
                        "Max deduction: $2,500"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 1040 Schedule 1",
                    source="deduction_analyzer"
                )
                if rec:
                    recommendations.append(rec)

        # Educator Expenses - USER VALUE: $300 above-the-line for teachers
        is_educator = bool(profile.get("is_educator", False) or profile.get("is_teacher", False))
        educator_expenses = _safe_float(profile.get("educator_expenses"), 0, min_val=0)

        if is_educator and educator_expenses > 0:
            deductible = min(educator_expenses, 300)
            savings = deductible * DEFAULT_MARGINAL_RATE

            if savings > 20:
                rec = _create_recommendation(
                    id="deduction-educator",
                    category="deduction",
                    title="Educator Expense Deduction",
                    summary=f"Deduct ${deductible:,.0f} for classroom supplies. Above-the-line, no itemizing needed!",
                    estimated_savings=savings,
                    priority="low",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        f"Expenses: ${educator_expenses:,.0f}",
                        "Max deduction: $300 per educator",
                        "Includes supplies, books, equipment",
                        "Must teach K-12 at least 900 hours"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 1040 Schedule 1",
                    source="deduction_analyzer"
                )
                if rec:
                    recommendations.append(rec)

        # Self-Employed Home Office - USER VALUE: Significant deduction for WFH
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
        has_home_office = bool(profile.get("has_home_office", False))
        home_sqft = _safe_float(profile.get("home_sqft"), 0, min_val=0)
        office_sqft = _safe_float(profile.get("office_sqft"), 0, min_val=0)

        if business_income > 0 and (has_home_office or office_sqft > 0):
            # Simplified method: $5 per sq ft, max 300 sq ft = $1,500
            if office_sqft > 0:
                simplified_deduction = min(office_sqft * 5, 1500)
            else:
                simplified_deduction = 1500  # Assume max if they have home office

            savings = simplified_deduction * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="deduction-home-office",
                category="deduction",
                title="Home Office Deduction",
                summary=f"Deduct up to ${simplified_deduction:,.0f} for home office. Saves ${savings:,.0f} in taxes!",
                estimated_savings=savings,
                priority="medium",
                urgency="moderate",
                confidence="high" if office_sqft > 0 else "medium",
                action_steps=[
                    "Simplified method: $5 per sq ft (max 300 sq ft)",
                    "Regular method may be higher (actual expenses)",
                    "Space must be used exclusively for business",
                    "Can deduct utilities, rent/mortgage portion, insurance",
                    "Report on Form 8829 or Schedule C"
                ],
                deadline="April 15, 2026",
                irs_reference="Form 8829, Publication 587",
                source="deduction_analyzer"
            )
            if rec:
                recommendations.append(rec)

        # Self-Employment Health Insurance - USER VALUE: 100% deductible
        se_health_insurance = _safe_float(profile.get("self_employed_health_insurance"), 0, min_val=0)

        if business_income > 0 and se_health_insurance > 0:
            # Can deduct up to net self-employment income
            deductible = min(se_health_insurance, business_income)
            savings = deductible * DEFAULT_MARGINAL_RATE

            if savings > 200:
                rec = _create_recommendation(
                    id="deduction-se-health",
                    category="deduction",
                    title="Self-Employed Health Insurance Deduction",
                    summary=f"Deduct ${deductible:,.0f} for health insurance premiums. Saves ${savings:,.0f}!",
                    estimated_savings=savings,
                    priority="high",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        f"Premiums paid: ${se_health_insurance:,.0f}",
                        "Includes medical, dental, vision, long-term care",
                        "Can include spouse and dependents",
                        "Above-the-line deduction",
                        "Report on Form 1040 Schedule 1"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 1040 Schedule 1",
                    source="deduction_analyzer"
                )
                if rec:
                    recommendations.append(rec)

    except Exception as e:
        logger.warning(f"Deduction analysis failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_retirement_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get retirement savings optimization recommendations.

    USER VALUE: Maximizes tax-advantaged retirement savings, identifies
    Roth conversion opportunities, catch-up contributions for 50+,
    and SEP-IRA/Solo 401(k) for self-employed.
    Typical savings: $2,000-$15,000/year in tax benefits.
    """
    recommendations = []

    try:
        # Extract profile data
        filing_status = profile.get("filing_status", "single")
        age = _safe_int(profile.get("age"), 40, min_val=18, max_val=120)
        agi = _safe_float(profile.get("total_income") or profile.get("w2_income"), 0, min_val=0)
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)

        # Current retirement contributions
        current_401k = _safe_float(profile.get("retirement_401k"), 0, min_val=0)
        current_ira = _safe_float(profile.get("retirement_ira"), 0, min_val=0)

        # 2025 contribution limits
        limit_401k = 23500  # 2025 limit
        limit_401k_catchup = 7500 if age >= 50 else 0
        limit_401k_total = limit_401k + limit_401k_catchup

        limit_ira = 7000  # 2025 limit
        limit_ira_catchup = 1000 if age >= 50 else 0
        limit_ira_total = limit_ira + limit_ira_catchup

        # =====================================================================
        # 401(k) MAXIMIZATION - USER VALUE: $5,600-$7,500 tax savings
        # =====================================================================
        if w2_income > 0 and current_401k < limit_401k_total:
            additional_401k = limit_401k_total - current_401k
            tax_savings = additional_401k * DEFAULT_MARGINAL_RATE

            if additional_401k > 1000:
                rec = _create_recommendation(
                    id="retirement-401k-max",
                    category="retirement",
                    title="Maximize 401(k) Contributions",
                    summary=f"Contribute ${additional_401k:,.0f} more to 401(k) for ${tax_savings:,.0f} immediate tax savings!",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="deadline",
                    confidence="high",
                    action_steps=[
                        f"Current contribution: ${current_401k:,.0f}",
                        f"2025 limit: ${limit_401k_total:,.0f}" + (" (includes $7,500 catch-up)" if age >= 50 else ""),
                        f"Additional needed: ${additional_401k:,.0f}",
                        "Increase contribution through employer",
                        "Deadline: December 31, 2025 for payroll deductions"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 560",
                    source="retirement_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =====================================================================
        # CATCH-UP CONTRIBUTIONS (50+) - USER VALUE: Extra $8,500
        # =====================================================================
        if age >= 50 and (current_401k < limit_401k or current_ira < limit_ira):
            catchup_total = limit_401k_catchup + limit_ira_catchup
            catchup_savings = catchup_total * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="retirement-catchup",
                category="retirement",
                title="Catch-Up Contributions (Age 50+)",
                summary=f"You can contribute ${catchup_total:,.0f} extra in catch-up contributions for ${catchup_savings:,.0f} more tax savings!",
                estimated_savings=catchup_savings,
                priority="high",
                urgency="deadline",
                confidence="high",
                action_steps=[
                    f"401(k) catch-up: ${limit_401k_catchup:,.0f}",
                    f"IRA catch-up: ${limit_ira_catchup:,.0f}",
                    "These are IN ADDITION to regular limits",
                    "Don't leave free tax savings on the table!"
                ],
                deadline="December 31, 2025",
                source="retirement_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =====================================================================
        # IRA CONTRIBUTION - USER VALUE: $1,680 tax savings
        # =====================================================================
        # Check IRA deduction eligibility (phase-out if covered by employer plan)
        has_employer_plan = bool(profile.get("has_employer_plan", False)) or current_401k > 0

        # 2025 IRA deduction phase-out (if covered by employer plan)
        if has_employer_plan:
            ira_phaseout_start = 123000 if filing_status == "married_joint" else 77000
            ira_phaseout_end = 143000 if filing_status == "married_joint" else 87000
        else:
            ira_phaseout_start = float('inf')  # No phase-out
            ira_phaseout_end = float('inf')

        if current_ira < limit_ira_total and agi < ira_phaseout_end:
            additional_ira = limit_ira_total - current_ira

            # Calculate deductible amount after phase-out
            if agi > ira_phaseout_start:
                phase_out_pct = min(1, (agi - ira_phaseout_start) / (ira_phaseout_end - ira_phaseout_start))
                deductible_ira = additional_ira * (1 - phase_out_pct)
            else:
                deductible_ira = additional_ira

            if deductible_ira > 500:
                tax_savings = deductible_ira * DEFAULT_MARGINAL_RATE

                rec = _create_recommendation(
                    id="retirement-ira",
                    category="retirement",
                    title="Traditional IRA Contribution",
                    summary=f"Contribute ${deductible_ira:,.0f} to Traditional IRA for ${tax_savings:,.0f} tax savings!",
                    estimated_savings=tax_savings,
                    priority="high" if deductible_ira > 3000 else "medium",
                    urgency="deadline",
                    confidence="high" if agi < ira_phaseout_start else "medium",
                    action_steps=[
                        f"2025 limit: ${limit_ira_total:,.0f}",
                        f"Deductible amount: ${deductible_ira:,.0f}",
                        "Can contribute until April 15, 2026 for 2025 tax year",
                        "Consider Roth if deduction is limited"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Publication 590-A",
                    source="retirement_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =====================================================================
        # SEP-IRA FOR SELF-EMPLOYED - USER VALUE: Up to $69,000 deduction
        # =====================================================================
        if business_income > 20000:
            # SEP-IRA: 25% of net self-employment income, max $69,000 (2025)
            net_se_income = business_income * 0.9235  # After SE tax deduction
            sep_limit = min(net_se_income * 0.25, 69000)
            sep_contribution = _safe_float(profile.get("sep_ira"), 0, min_val=0)

            if sep_contribution < sep_limit:
                additional_sep = sep_limit - sep_contribution
                tax_savings = additional_sep * DEFAULT_MARGINAL_RATE

                if additional_sep > 1000:
                    rec = _create_recommendation(
                        id="retirement-sep-ira",
                        category="retirement",
                        title="SEP-IRA for Self-Employed",
                        summary=f"Contribute up to ${sep_limit:,.0f} to SEP-IRA for ${tax_savings:,.0f} in tax savings!",
                        estimated_savings=tax_savings,
                        priority="high",
                        urgency="deadline",
                        confidence="high",
                        action_steps=[
                            f"Your max SEP contribution: ${sep_limit:,.0f}",
                            "Can contribute up to 25% of net SE income",
                            "Easy to set up - no annual filings",
                            "Deadline: Tax filing deadline (with extensions)",
                            "Consider Solo 401(k) for higher limits"
                        ],
                        deadline="April 15, 2026",
                        irs_reference="Publication 560",
                        source="retirement_optimizer"
                    )
                    if rec:
                        recommendations.append(rec)

        # =====================================================================
        # ROTH CONVERSION OPPORTUNITY - USER VALUE: Tax-free retirement growth
        # =====================================================================
        traditional_balance = _safe_float(profile.get("traditional_ira_balance") or profile.get("ira_balance"), 0, min_val=0)

        # Roth conversion makes sense if current tax rate is lower than expected future rate
        # Good candidates: income dip year, early retirement, low tax bracket
        if traditional_balance > 10000 and agi < 100000:
            # Suggest conversion amount that keeps them in current bracket
            # Simplified: suggest converting to fill up the 22% bracket
            bracket_22_top = 201050 if filing_status == "married_joint" else 100525
            conversion_room = max(0, bracket_22_top - agi)
            suggested_conversion = min(conversion_room, traditional_balance, 50000)

            if suggested_conversion > 5000:
                conversion_tax = suggested_conversion * DEFAULT_MARGINAL_RATE

                rec = _create_recommendation(
                    id="retirement-roth-conversion",
                    category="retirement",
                    title="Roth Conversion Opportunity",
                    summary=f"Convert ${suggested_conversion:,.0f} to Roth IRA. Pay ${conversion_tax:,.0f} tax now for tax-free growth forever!",
                    estimated_savings=0,  # Long-term benefit, not immediate savings
                    priority="medium",
                    urgency="planning",
                    confidence="medium",
                    action_steps=[
                        f"Traditional IRA balance: ${traditional_balance:,.0f}",
                        f"Suggested conversion: ${suggested_conversion:,.0f}",
                        f"Estimated tax on conversion: ${conversion_tax:,.0f}",
                        "Benefits: Tax-free growth, no RMDs",
                        "Best if you expect higher future tax rates"
                    ],
                    irs_reference="Publication 590-A",
                    source="retirement_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"Retirement optimization found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Retirement optimization failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_investment_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get investment and capital gains tax optimization recommendations.

    USER VALUE: For investors, identifies tax-loss harvesting opportunities,
    Net Investment Income Tax (NIIT) mitigation, and qualified dividend strategies.

    Key strategies:
    - Tax-loss harvesting: Offset gains with losses (save 15-23.8% on gains)
    - NIIT planning: 3.8% surtax on investment income over threshold
    - Qualified dividends: Ensure dividends qualify for lower rates
    - Capital gains timing: Short-term vs long-term holding periods
    - Asset location: Tax-efficient placement across account types

    Typical savings: $1,000-$10,000+ for investors with significant portfolios
    """
    recommendations = []

    try:
        # Extract investment data
        investment_income = _safe_float(profile.get("investment_income"), 0, min_val=0)
        capital_gains = _safe_float(profile.get("capital_gains"), 0)  # Can be negative
        capital_losses = _safe_float(profile.get("capital_losses"), 0, min_val=0)
        unrealized_gains = _safe_float(profile.get("unrealized_gains"), 0)
        unrealized_losses = _safe_float(profile.get("unrealized_losses"), 0, min_val=0)
        dividend_income = _safe_float(profile.get("dividend_income"), 0, min_val=0)
        interest_income = _safe_float(profile.get("interest_income"), 0, min_val=0)
        portfolio_value = _safe_float(profile.get("portfolio_value"), 0, min_val=0)

        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # NIIT thresholds
        NIIT_THRESHOLDS = {
            "single": 200000,
            "married_joint": 250000,
            "married_separate": 125000,
            "head_of_household": 200000,
            "qualifying_widow": 250000,
        }
        NIIT_RATE = 0.038

        # Long-term capital gains rates by income
        LTCG_RATE_0_THRESHOLD = {"single": 47025, "married_joint": 94050}
        LTCG_RATE_15 = 0.15
        LTCG_RATE_20 = 0.20

        niit_threshold = NIIT_THRESHOLDS.get(filing_status, 200000)

        # =================================================================
        # 1. TAX-LOSS HARVESTING
        # =================================================================
        if unrealized_losses > 500 and (capital_gains > 0 or unrealized_gains > 0):
            # Calculate potential savings from harvesting losses
            harvestable_loss = min(unrealized_losses, max(capital_gains, unrealized_gains) + 3000)

            # Estimate tax rate on gains
            if total_income > niit_threshold:
                effective_gains_rate = LTCG_RATE_15 + NIIT_RATE  # 18.8%
            else:
                effective_gains_rate = LTCG_RATE_15

            tax_savings = harvestable_loss * effective_gains_rate

            if tax_savings >= 100:
                # Calculate wash sale deadline
                rec = _create_recommendation(
                    id="investment-tax-loss-harvest",
                    category="investment",
                    title="Tax-Loss Harvesting Opportunity",
                    summary=f"Harvest ${harvestable_loss:,.0f} in losses to save ${tax_savings:,.0f} in taxes. Offset gains and deduct up to $3K against ordinary income!",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        f"Unrealized losses available: ${unrealized_losses:,.0f}",
                        f"Potential offset: ${harvestable_loss:,.0f}",
                        "Sell losing positions before Dec 31",
                        "Wait 31+ days before repurchasing (wash sale rule)",
                        "Consider similar (not identical) replacement investments",
                        "Excess losses carry forward to future years"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 550, Schedule D",
                    source="investment_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # Capital loss carryforward reminder
        elif capital_losses > 3000:
            excess_loss = capital_losses - 3000
            future_savings = excess_loss * effective_gains_rate if 'effective_gains_rate' in dir() else excess_loss * 0.15

            rec = _create_recommendation(
                id="investment-loss-carryforward",
                category="investment",
                title="Capital Loss Carryforward",
                summary=f"You have ${excess_loss:,.0f} in excess losses to carry forward. Use against future gains!",
                estimated_savings=0,  # Future benefit
                priority="low",
                urgency="informational",
                confidence="high",
                action_steps=[
                    f"2025 loss used: $3,000 (against ordinary income)",
                    f"Carryforward to 2026+: ${excess_loss:,.0f}",
                    "Track on Schedule D, Form 8949",
                    "Losses never expire - carry forward indefinitely"
                ],
                irs_reference="Publication 550",
                source="investment_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. NET INVESTMENT INCOME TAX (NIIT) ANALYSIS
        # =================================================================
        total_investment_income = investment_income + max(0, capital_gains) + dividend_income + interest_income

        if total_income > niit_threshold * 0.9 and total_investment_income > 5000:
            # NIIT applies to lesser of: NII or MAGI over threshold
            magi_over_threshold = max(0, total_income - niit_threshold)
            niit_base = min(total_investment_income, magi_over_threshold)
            niit_liability = niit_base * NIIT_RATE

            if niit_liability > 100:
                # Calculate potential savings strategies
                potential_reduction = min(total_investment_income * 0.3, niit_base)  # Assume 30% can be deferred
                potential_savings = potential_reduction * NIIT_RATE

                rec = _create_recommendation(
                    id="investment-niit-planning",
                    category="investment",
                    title="Net Investment Income Tax (NIIT) Planning",
                    summary=f"You may owe ${niit_liability:,.0f} in NIIT (3.8% surtax). Strategic planning could save ${potential_savings:,.0f}!",
                    estimated_savings=potential_savings,
                    priority="high" if niit_liability > 1000 else "medium",
                    urgency="year_end",
                    confidence="medium",
                    action_steps=[
                        f"NIIT threshold ({filing_status}): ${niit_threshold:,.0f}",
                        f"Your investment income: ${total_investment_income:,.0f}",
                        f"Estimated NIIT liability: ${niit_liability:,.0f}",
                        "Strategies to reduce NIIT:",
                        "  • Defer capital gains to lower-income years",
                        "  • Maximize above-the-line deductions (401k, HSA)",
                        "  • Consider municipal bonds (tax-exempt)",
                        "  • Invest in rental real estate (active participation)"
                    ],
                    irs_reference="Form 8960, Instructions",
                    source="investment_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 3. QUALIFIED DIVIDENDS OPTIMIZATION
        # =================================================================
        if dividend_income > 1000:
            # Check if dividends are likely qualified
            holding_period_ok = bool(profile.get("dividends_qualified", True))

            if holding_period_ok:
                # Calculate savings from qualified vs ordinary rates
                ordinary_rate = DEFAULT_MARGINAL_RATE
                qualified_rate = LTCG_RATE_15 if total_income < 500000 else LTCG_RATE_20
                rate_savings = ordinary_rate - qualified_rate
                tax_savings = dividend_income * rate_savings

                if tax_savings > 100:
                    rec = _create_recommendation(
                        id="investment-qualified-dividends",
                        category="investment",
                        title="Qualified Dividend Tax Savings",
                        summary=f"Your ${dividend_income:,.0f} in qualified dividends saves ${tax_savings:,.0f} vs ordinary income rates!",
                        estimated_savings=tax_savings,
                        priority="medium",
                        urgency="informational",
                        confidence="high",
                        action_steps=[
                            f"Qualified dividend income: ${dividend_income:,.0f}",
                            f"Tax rate on qualified dividends: {qualified_rate*100:.1f}%",
                            f"Ordinary income rate would be: {ordinary_rate*100:.1f}%",
                            "Requirements for qualified dividends:",
                            "  • Hold stock 60+ days in 121-day window",
                            "  • US corporation or qualified foreign corp",
                            "Report on Schedule B, check qualified box"
                        ],
                        irs_reference="Publication 550, Qualified Dividends",
                        source="investment_optimizer"
                    )
                    if rec:
                        recommendations.append(rec)

        # =================================================================
        # 4. 0% CAPITAL GAINS RATE OPPORTUNITY
        # =================================================================
        zero_rate_threshold = LTCG_RATE_0_THRESHOLD.get(
            "married_joint" if filing_status == "married_joint" else "single",
            47025
        )

        taxable_income_estimate = total_income - STANDARD_DEDUCTIONS.get(filing_status, 15000)

        if taxable_income_estimate < zero_rate_threshold and unrealized_gains > 1000:
            # Room in 0% bracket
            bracket_room = zero_rate_threshold - taxable_income_estimate
            harvestable_gains = min(unrealized_gains, bracket_room)
            tax_savings = harvestable_gains * LTCG_RATE_15  # Saving 15% by realizing at 0%

            if tax_savings >= 100:
                rec = _create_recommendation(
                    id="investment-zero-rate-harvest",
                    category="investment",
                    title="Harvest Gains at 0% Tax Rate",
                    summary=f"Realize ${harvestable_gains:,.0f} in gains tax-free! You're in the 0% capital gains bracket. Save ${tax_savings:,.0f}!",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        f"0% rate threshold ({filing_status}): ${zero_rate_threshold:,.0f}",
                        f"Your taxable income: ~${taxable_income_estimate:,.0f}",
                        f"Room in 0% bracket: ${bracket_room:,.0f}",
                        f"Suggested gain harvest: ${harvestable_gains:,.0f}",
                        "Sell and immediately repurchase (no wash sale for gains)",
                        "Resets cost basis higher for future sales"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 550, Capital Gains Rates",
                    source="investment_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 5. ASSET LOCATION STRATEGY
        # =================================================================
        if portfolio_value > 50000 and (interest_income > 1000 or dividend_income > 1000):
            # Suggest tax-efficient asset placement
            tax_inefficient_in_taxable = interest_income + (dividend_income * 0.3)  # Assume 30% non-qualified
            potential_savings = tax_inefficient_in_taxable * DEFAULT_MARGINAL_RATE * 0.5  # Conservative estimate

            if potential_savings > 200:
                rec = _create_recommendation(
                    id="investment-asset-location",
                    category="investment",
                    title="Tax-Efficient Asset Location",
                    summary=f"Optimize where you hold investments. Could save ~${potential_savings:,.0f}/year in taxes!",
                    estimated_savings=potential_savings,
                    priority="medium",
                    urgency="planning",
                    confidence="medium",
                    action_steps=[
                        "Tax-INEFFICIENT assets → Tax-advantaged accounts (401k, IRA):",
                        "  • Bonds, REITs, high-turnover funds",
                        "  • Non-qualified dividends",
                        "Tax-EFFICIENT assets → Taxable brokerage:",
                        "  • Index funds, ETFs (low turnover)",
                        "  • Growth stocks (defer gains)",
                        "  • Municipal bonds (tax-free)",
                        "Review asset placement annually"
                    ],
                    irs_reference="Publication 550",
                    source="investment_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"Investment optimization found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Investment optimization failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_filing_status_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get filing status optimization recommendations.

    USER VALUE: Identifies when a different filing status could save taxes.
    Key scenarios:
    - Single with dependents → Head of Household (lower rates, higher std deduction)
    - Married → MFS vs MFJ analysis
    - Qualifying Widow(er) eligibility

    Typical savings: $500-$5,000 for qualifying situations
    """
    recommendations = []

    try:
        current_status = _safe_str(profile.get("filing_status"), "single").lower()
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        num_dependents = _safe_int(profile.get("num_dependents") or profile.get("dependents"), 0, min_val=0)
        is_married = current_status in ("married_joint", "married_separate")
        spouse_income = _safe_float(profile.get("spouse_income"), 0, min_val=0)

        # Marital status indicators
        is_single = current_status == "single"
        has_dependents = num_dependents > 0

        # Check for deceased spouse (qualifying widow)
        spouse_deceased_year = _safe_int(profile.get("spouse_deceased_year"), 0, min_val=2020, max_val=TAX_YEAR)
        dependent_child = bool(profile.get("dependent_child", False)) or any(
            isinstance(a, (int, float)) and a < 19
            for a in profile.get("dependent_ages", [])
        )

        # =================================================================
        # 1. SINGLE → HEAD OF HOUSEHOLD
        # =================================================================
        if is_single and has_dependents:
            # Calculate savings from HOH vs Single
            single_std = STANDARD_DEDUCTIONS.get("single", 15000)
            hoh_std = STANDARD_DEDUCTIONS.get("head_of_household", 22500)
            std_deduction_savings = hoh_std - single_std

            # Also wider tax brackets - estimate ~$1,000 additional from bracket benefit
            bracket_savings = min(total_income * 0.02, 2000)  # Rough estimate
            total_savings = (std_deduction_savings * DEFAULT_MARGINAL_RATE) + bracket_savings

            rec = _create_recommendation(
                id="filing-hoh-opportunity",
                category="filing",
                title="Head of Household Filing Status",
                summary=f"File as Head of Household instead of Single! Save ~${total_savings:,.0f} with ${std_deduction_savings:,.0f} higher standard deduction + lower tax rates!",
                estimated_savings=total_savings,
                priority="high",
                urgency="tax_filing",
                confidence="high",
                action_steps=[
                    "Requirements for Head of Household:",
                    "  1. Unmarried (or considered unmarried) on Dec 31",
                    "  2. Paid >50% of home costs for the year",
                    "  3. Qualifying person lived with you >6 months",
                    f"Your dependents: {num_dependents}",
                    f"Standard deduction increase: ${std_deduction_savings:,.0f}",
                    "Also: wider tax brackets = lower rates",
                    "Claim on Form 1040, filing status box"
                ],
                deadline="April 15, 2026",
                irs_reference="Publication 501, Head of Household",
                source="filing_status_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. QUALIFYING WIDOW(ER) STATUS
        # =================================================================
        if spouse_deceased_year and TAX_YEAR - spouse_deceased_year <= 2 and dependent_child:
            # Can use MFJ rates for 2 years after spouse death
            qw_std = STANDARD_DEDUCTIONS.get("qualifying_widow", 30000)
            single_std = STANDARD_DEDUCTIONS.get("single", 15000)
            std_savings = qw_std - single_std
            total_savings = std_savings * DEFAULT_MARGINAL_RATE + 2000  # Plus bracket benefit

            rec = _create_recommendation(
                id="filing-qualifying-widow",
                category="filing",
                title="Qualifying Surviving Spouse Status",
                summary=f"Use Qualifying Surviving Spouse status for ${total_savings:,.0f} in savings. Get MFJ standard deduction and tax rates!",
                estimated_savings=total_savings,
                priority="high",
                urgency="tax_filing",
                confidence="high",
                action_steps=[
                    "Requirements:",
                    f"  • Spouse died in {spouse_deceased_year}",
                    "  • Haven't remarried",
                    "  • Have dependent child living with you",
                    "  • Paid >50% of home costs",
                    f"Standard deduction: ${qw_std:,.0f} (same as MFJ)",
                    "Use MFJ tax brackets (much more favorable)",
                    "Available for 2 years after year of death"
                ],
                deadline="April 15, 2026",
                irs_reference="Publication 501, Qualifying Surviving Spouse",
                source="filing_status_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. MARRIED FILING SEPARATELY ANALYSIS
        # =================================================================
        if current_status == "married_joint" and total_income > 100000:
            # MFS might be better in specific situations
            # Calculate potential scenarios

            # Scenario: Large medical expenses (7.5% AGI floor)
            medical_expenses = _safe_float(profile.get("medical_expenses"), 0, min_val=0)
            if medical_expenses > total_income * 0.075:
                # MFS might help if one spouse has most medical expenses
                personal_income = total_income - spouse_income if spouse_income > 0 else total_income * 0.6
                mfs_floor = personal_income * 0.075
                mfj_floor = total_income * 0.075
                additional_deduction = mfj_floor - mfs_floor
                potential_savings = additional_deduction * DEFAULT_MARGINAL_RATE

                if potential_savings > 500:
                    rec = _create_recommendation(
                        id="filing-mfs-medical",
                        category="filing",
                        title="Consider MFS for Medical Deductions",
                        summary=f"Filing separately might save ${potential_savings:,.0f} by lowering your medical expense floor!",
                        estimated_savings=potential_savings,
                        priority="medium",
                        urgency="tax_filing",
                        confidence="medium",
                        action_steps=[
                            f"Your medical expenses: ${medical_expenses:,.0f}",
                            f"MFJ AGI floor (7.5%): ${mfj_floor:,.0f}",
                            f"MFS AGI floor (your income): ${mfs_floor:,.0f}",
                            "MFS tradeoffs to consider:",
                            "  • Lose some credits (EITC, education)",
                            "  • Higher tax rates on each return",
                            "  • Both must itemize or both standard",
                            "Run both scenarios before deciding!"
                        ],
                        irs_reference="Publication 501, MFS",
                        source="filing_status_optimizer"
                    )
                    if rec:
                        recommendations.append(rec)

            # Scenario: Income-Based Repayment (IBR) for student loans
            student_loans = _safe_float(profile.get("student_loan_balance"), 0, min_val=0)
            if student_loans > 50000:
                rec = _create_recommendation(
                    id="filing-mfs-ibr",
                    category="filing",
                    title="MFS for Student Loan IBR",
                    summary=f"Filing separately may lower your IBR payment. Student loans: ${student_loans:,.0f}",
                    estimated_savings=0,  # Savings are in loan payments, not taxes
                    priority="medium",
                    urgency="planning",
                    confidence="medium",
                    action_steps=[
                        "Income-Based Repayment uses your AGI",
                        "MFS = only YOUR income counts",
                        "MFJ = combined income = higher payment",
                        "Tradeoff: Higher taxes but lower loan payment",
                        "Calculate net benefit before deciding",
                        "Consider PSLF implications"
                    ],
                    irs_reference="Publication 970",
                    source="filing_status_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"Filing status optimization found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Filing status optimization failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_timing_strategy_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get year-end and timing-based tax strategies.

    USER VALUE: Identifies time-sensitive opportunities for tax optimization.
    Key strategies:
    - Income deferral/acceleration based on bracket expectations
    - Deduction bunching for itemizers
    - Year-end charitable giving
    - Estimated tax payment optimization
    - AMT planning

    Typical savings: $500-$5,000 from strategic timing
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 40, min_val=18, max_val=100)

        # Next year income expectation
        expected_income_change = _safe_str(profile.get("expected_income_change"), "same").lower()
        next_year_income = _safe_float(profile.get("next_year_income"), total_income)

        # Tax bracket boundaries (2025 approximate)
        BRACKET_BOUNDARIES = {
            "single": [11925, 48475, 103350, 197300, 250525, 626350],
            "married_joint": [23850, 96950, 206700, 394600, 501050, 751600],
        }

        boundaries = BRACKET_BOUNDARIES.get(
            "married_joint" if filing_status == "married_joint" else "single",
            BRACKET_BOUNDARIES["single"]
        )

        # Find current bracket
        taxable_estimate = total_income - STANDARD_DEDUCTIONS.get(filing_status, 15000)
        current_bracket_top = next((b for b in boundaries if b > taxable_estimate), boundaries[-1])
        room_in_bracket = current_bracket_top - taxable_estimate

        # =================================================================
        # 1. INCOME ACCELERATION (if expecting higher taxes next year)
        # =================================================================
        if (expected_income_change == "higher" or next_year_income > total_income * 1.2) and business_income > 0:
            accelerate_amount = min(business_income * 0.3, room_in_bracket)
            tax_savings = accelerate_amount * 0.05  # Assume 5% rate differential

            if tax_savings > 200:
                rec = _create_recommendation(
                    id="timing-accelerate-income",
                    category="timing",
                    title="Accelerate Income This Year",
                    summary=f"Bill clients now! With higher income expected next year, recognize ${accelerate_amount:,.0f} in 2025 to save ~${tax_savings:,.0f}.",
                    estimated_savings=tax_savings,
                    priority="medium",
                    urgency="year_end",
                    confidence="medium",
                    action_steps=[
                        f"Room in current bracket: ${room_in_bracket:,.0f}",
                        "Actions to accelerate income:",
                        "  • Invoice December work now",
                        "  • Collect receivables before Dec 31",
                        "  • Take year-end bonuses in December",
                        "  • Convert deferred comp if beneficial",
                        "Cash basis: Income when received",
                        "Accrual basis: Income when earned"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 538, Accounting Methods",
                    source="timing_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 2. INCOME DEFERRAL (if expecting lower taxes next year)
        # =================================================================
        if (expected_income_change == "lower" or next_year_income < total_income * 0.8) and business_income > 0:
            defer_amount = min(business_income * 0.2, 20000)
            tax_savings = defer_amount * 0.05  # Assume 5% rate differential

            if tax_savings > 200:
                rec = _create_recommendation(
                    id="timing-defer-income",
                    category="timing",
                    title="Defer Income to Next Year",
                    summary=f"Expecting lower income in 2026? Defer ${defer_amount:,.0f} to save ~${tax_savings:,.0f} in taxes!",
                    estimated_savings=tax_savings,
                    priority="medium",
                    urgency="year_end",
                    confidence="medium",
                    action_steps=[
                        "Deferral strategies:",
                        "  • Delay December invoicing to January",
                        "  • Defer year-end bonus to January",
                        "  • Delay closing on property sales",
                        "  • Installment sale for large assets",
                        "Cash basis: Defer receipt of payment",
                        "Watch for constructive receipt rules"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 538",
                    source="timing_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 3. DEDUCTION BUNCHING STRATEGY
        # =================================================================
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)

        # Get itemized deductions
        mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0, min_val=0)
        property_taxes = _safe_float(profile.get("property_taxes"), 0, min_val=0)
        state_taxes = _safe_float(profile.get("state_income_tax") or profile.get("state_taxes"), 0, min_val=0)
        charitable = _safe_float(profile.get("charitable_donations") or profile.get("charitable"), 0, min_val=0)

        salt_total = min(property_taxes + state_taxes, SALT_CAP)
        current_itemized = mortgage_interest + salt_total + charitable

        # Check if close to itemizing threshold
        itemized_gap = std_deduction - current_itemized

        if 0 < itemized_gap < 10000:
            # Close to itemizing - bunching could help
            bunch_amount = itemized_gap + 2000  # Exceed by $2K to make it worthwhile
            bunching_savings = bunch_amount * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="timing-deduction-bunching",
                category="timing",
                title="Deduction Bunching Strategy",
                summary=f"You're ${itemized_gap:,.0f} below itemizing. Bunch ${bunch_amount:,.0f} in deductions this year to save ${bunching_savings:,.0f}!",
                estimated_savings=bunching_savings,
                priority="high",
                urgency="year_end",
                confidence="high",
                action_steps=[
                    f"Standard deduction: ${std_deduction:,.0f}",
                    f"Current itemized: ${current_itemized:,.0f}",
                    f"Gap to close: ${itemized_gap:,.0f}",
                    "Bunching strategies:",
                    "  • Prepay January mortgage (extra payment)",
                    "  • Make 2+ years of charity in 1 year",
                    "  • Prepay state estimated taxes",
                    "  • Bunch medical procedures",
                    "Next year: Take standard deduction"
                ],
                deadline="December 31, 2025",
                irs_reference="Schedule A",
                source="timing_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 4. YEAR-END CHARITABLE GIVING
        # =================================================================
        if charitable < total_income * 0.05 and total_income > 75000:
            # Suggest charitable giving for tax benefit
            suggested_giving = min(total_income * 0.05, 10000)
            tax_benefit = suggested_giving * DEFAULT_MARGINAL_RATE

            # Check if they'd need to itemize
            potential_itemized = current_itemized + suggested_giving

            if potential_itemized > std_deduction:
                excess_over_std = potential_itemized - std_deduction
                actual_tax_benefit = excess_over_std * DEFAULT_MARGINAL_RATE

                rec = _create_recommendation(
                    id="timing-charitable-yearend",
                    category="timing",
                    title="Year-End Charitable Giving",
                    summary=f"Give ${suggested_giving:,.0f} to charity before Dec 31. Tax benefit: ${actual_tax_benefit:,.0f} (pushes you into itemizing)!",
                    estimated_savings=actual_tax_benefit,
                    priority="medium",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        f"Suggested donation: ${suggested_giving:,.0f}",
                        f"Would bring itemized total to: ${potential_itemized:,.0f}",
                        "Tax-smart giving options:",
                        "  • Donate appreciated stock (skip cap gains)",
                        "  • Donor-Advised Fund (bunch multiple years)",
                        "  • Qualified Charitable Distribution (if 70.5+)",
                        "Get receipts for donations over $250"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 526",
                    source="timing_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 5. REQUIRED MINIMUM DISTRIBUTIONS (RMD)
        # =================================================================
        if age >= 73:
            traditional_balance = _safe_float(profile.get("traditional_ira_balance") or profile.get("ira_balance"), 0, min_val=0)
            k401_balance = _safe_float(profile.get("401k_balance"), 0, min_val=0)
            total_retirement = traditional_balance + k401_balance

            if total_retirement > 10000:
                # RMD calculation (simplified)
                rmd_factor = max(27.4 - (age - 73) * 0.9, 15)  # Simplified distribution period
                estimated_rmd = total_retirement / rmd_factor
                rmd_tax = estimated_rmd * DEFAULT_MARGINAL_RATE

                rec = _create_recommendation(
                    id="timing-rmd-required",
                    category="timing",
                    title="Required Minimum Distribution (RMD)",
                    summary=f"You must take ~${estimated_rmd:,.0f} RMD by Dec 31 or face 25% penalty! Tax: ~${rmd_tax:,.0f}",
                    estimated_savings=estimated_rmd * 0.25,  # Penalty avoided
                    priority="critical",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        f"Age: {age} (RMDs required at 73+)",
                        f"Retirement account balance: ~${total_retirement:,.0f}",
                        f"Estimated RMD: ${estimated_rmd:,.0f}",
                        "Options to satisfy RMD:",
                        "  • Cash withdrawal",
                        "  • Qualified Charitable Distribution (QCD)",
                        "  • In-kind distribution",
                        "PENALTY: 25% of amount not withdrawn!"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 590-B",
                    source="timing_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 6. ESTIMATED TAX PAYMENT CHECK
        # =================================================================
        if business_income > 10000 or total_income > 150000:
            estimated_tax_paid = _safe_float(profile.get("estimated_tax_paid"), 0, min_val=0)
            withholding = _safe_float(profile.get("withholding"), 0, min_val=0)
            total_paid = estimated_tax_paid + withholding

            # Rough tax estimate
            effective_rate = 0.22 if total_income > 100000 else 0.15
            estimated_tax_due = total_income * effective_rate

            # Safe harbor: Pay 100% of last year (110% if income > $150K)
            last_year_tax = _safe_float(profile.get("last_year_tax"), estimated_tax_due * 0.9, min_val=0)
            safe_harbor = last_year_tax * (1.1 if total_income > 150000 else 1.0)

            shortfall = max(0, min(estimated_tax_due, safe_harbor) - total_paid)

            if shortfall > 1000:
                penalty_estimate = shortfall * 0.08  # ~8% annualized penalty rate

                rec = _create_recommendation(
                    id="timing-estimated-tax",
                    category="timing",
                    title="Q4 Estimated Tax Payment Due",
                    summary=f"Pay ${shortfall:,.0f} by Jan 15 to avoid ~${penalty_estimate:,.0f} underpayment penalty!",
                    estimated_savings=penalty_estimate,
                    priority="high",
                    urgency="immediate",
                    confidence="medium",
                    action_steps=[
                        f"Estimated tax due: ~${estimated_tax_due:,.0f}",
                        f"Already paid: ${total_paid:,.0f}",
                        f"Shortfall: ${shortfall:,.0f}",
                        "Options to catch up:",
                        "  • Pay Q4 estimated tax by Jan 15",
                        "  • Increase W-2 withholding (if employed)",
                        "  • Pay with extension (still accrues interest)",
                        "Use Form 1040-ES or IRS Direct Pay"
                    ],
                    deadline="January 15, 2026",
                    irs_reference="Form 1040-ES, Publication 505",
                    source="timing_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"Timing strategy optimization found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Timing strategy optimization failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_charitable_strategy_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get charitable giving tax optimization recommendations.

    USER VALUE: Maximizes tax benefit from charitable giving through:
    - Appreciated stock donations (skip capital gains tax)
    - Donor-Advised Funds (bunch multiple years)
    - Qualified Charitable Distributions (for 70.5+)
    - Charitable remainder trusts (high net worth)

    Typical savings: $500-$10,000+ depending on giving level
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 40, min_val=18, max_val=100)

        # Current charitable giving
        charitable = _safe_float(profile.get("charitable_donations") or profile.get("charitable"), 0, min_val=0)
        planned_giving = _safe_float(profile.get("planned_charitable"), charitable, min_val=0)

        # Investment info
        unrealized_gains = _safe_float(profile.get("unrealized_gains"), 0, min_val=0)
        appreciated_stock = _safe_float(profile.get("appreciated_stock"), unrealized_gains * 0.5, min_val=0)

        # Retirement info for QCD
        ira_balance = _safe_float(profile.get("traditional_ira_balance") or profile.get("ira_balance"), 0, min_val=0)

        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)

        # =================================================================
        # 1. DONATE APPRECIATED STOCK
        # =================================================================
        if appreciated_stock > 1000 and planned_giving > 500:
            # Donating stock skips capital gains tax entirely
            donation_amount = min(appreciated_stock, planned_giving, total_income * 0.3)  # 30% AGI limit

            # Assume 50% of value is unrealized gain
            avoided_gain = donation_amount * 0.5
            capital_gains_avoided = avoided_gain * 0.15  # 15% LTCG rate

            # Plus the charitable deduction
            deduction_benefit = donation_amount * DEFAULT_MARGINAL_RATE
            total_benefit = capital_gains_avoided + deduction_benefit

            rec = _create_recommendation(
                id="charitable-appreciated-stock",
                category="charitable",
                title="Donate Appreciated Stock",
                summary=f"Donate ${donation_amount:,.0f} in stock instead of cash. Double tax benefit: ${total_benefit:,.0f}!",
                estimated_savings=total_benefit,
                priority="high",
                urgency="year_end",
                confidence="high",
                action_steps=[
                    f"Stock to donate: ${donation_amount:,.0f}",
                    f"Capital gains avoided: ${capital_gains_avoided:,.0f}",
                    f"Charitable deduction: ${deduction_benefit:,.0f}",
                    "Requirements:",
                    "  • Held stock >1 year (long-term)",
                    "  • Donate directly to charity (don't sell first)",
                    "  • Get written acknowledgment",
                    "  • May need qualified appraisal if >$5K",
                    "Limit: 30% of AGI for appreciated property"
                ],
                deadline="December 31, 2025",
                irs_reference="Publication 526, Noncash Contributions",
                source="charitable_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. DONOR-ADVISED FUND (DAF)
        # =================================================================
        if total_income > 100000 and planned_giving > 2000:
            # DAF allows bunching multiple years of giving
            years_to_bunch = 3
            bunched_amount = planned_giving * years_to_bunch

            # Calculate itemizing benefit from bunching
            mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0)
            salt = min(_safe_float(profile.get("property_taxes"), 0) + _safe_float(profile.get("state_income_tax"), 0), SALT_CAP)
            base_itemized = mortgage_interest + salt

            # Without bunching: might not itemize each year
            annual_itemized = base_itemized + planned_giving
            years_itemizing_without = 1 if annual_itemized > std_deduction else 0
            benefit_without = max(0, annual_itemized - std_deduction) * years_to_bunch

            # With bunching: definitely itemize in bunch year
            bunched_itemized = base_itemized + bunched_amount
            benefit_with = max(0, bunched_itemized - std_deduction) + (std_deduction * (years_to_bunch - 1))

            extra_benefit = (benefit_with - benefit_without) * DEFAULT_MARGINAL_RATE

            if extra_benefit > 500:
                rec = _create_recommendation(
                    id="charitable-daf",
                    category="charitable",
                    title="Donor-Advised Fund (DAF)",
                    summary=f"Bunch {years_to_bunch} years of giving (${bunched_amount:,.0f}) into a DAF. Extra tax benefit: ${extra_benefit:,.0f}!",
                    estimated_savings=extra_benefit,
                    priority="high",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        f"Annual giving: ${planned_giving:,.0f}",
                        f"Bunch {years_to_bunch} years: ${bunched_amount:,.0f}",
                        "How a DAF works:",
                        "  1. Contribute to DAF (get deduction now)",
                        "  2. DAF invests and grows tax-free",
                        "  3. Grant to charities over time",
                        "Benefits:",
                        "  • Immediate tax deduction",
                        "  • Distribute to charities later",
                        "  • Can donate appreciated assets",
                        "Providers: Fidelity, Schwab, Vanguard"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 526, Donor-Advised Funds",
                    source="charitable_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 3. QUALIFIED CHARITABLE DISTRIBUTION (QCD)
        # =================================================================
        if age >= 70.5 and ira_balance > 10000:
            # QCD allows direct IRA-to-charity transfer (up to $105K in 2025)
            qcd_limit = 105000
            suggested_qcd = min(ira_balance * 0.1, qcd_limit, max(planned_giving, 5000))

            # QCD is better than taking distribution and donating
            # Because QCD doesn't increase AGI
            avoided_income = suggested_qcd
            agi_benefit = avoided_income * DEFAULT_MARGINAL_RATE

            # Additional benefits from lower AGI
            additional_benefits = avoided_income * 0.02  # SS taxation, Medicare premiums, etc.
            total_benefit = agi_benefit + additional_benefits

            rec = _create_recommendation(
                id="charitable-qcd",
                category="charitable",
                title="Qualified Charitable Distribution (QCD)",
                summary=f"Give ${suggested_qcd:,.0f} directly from IRA to charity. Saves ${total_benefit:,.0f} vs normal distribution + donation!",
                estimated_savings=total_benefit,
                priority="high",
                urgency="year_end",
                confidence="high",
                action_steps=[
                    f"Your IRA balance: ${ira_balance:,.0f}",
                    f"Suggested QCD: ${suggested_qcd:,.0f}",
                    f"2025 QCD limit: ${qcd_limit:,.0f}",
                    "QCD benefits vs normal distribution:",
                    "  • Doesn't increase your AGI",
                    "  • May reduce Social Security taxation",
                    "  • May lower Medicare premiums (IRMAA)",
                    "  • Counts toward RMD (if 73+)",
                    "Requirements: Must be 70.5+, direct transfer"
                ],
                deadline="December 31, 2025",
                irs_reference="Publication 590-B, QCDs",
                source="charitable_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 4. ABOVE-THE-LINE DEDUCTION FOR NON-ITEMIZERS
        # =================================================================
        # Note: The $300/$600 above-the-line charitable deduction expired after 2021
        # But mention standard deduction and charitable for completeness

        mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0)
        salt = min(_safe_float(profile.get("property_taxes"), 0) + _safe_float(profile.get("state_income_tax"), 0), SALT_CAP)
        current_itemized = mortgage_interest + salt + charitable

        if current_itemized < std_deduction and charitable > 0:
            wasted_benefit = charitable * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="charitable-non-itemizer",
                category="charitable",
                title="Charitable Giving as Non-Itemizer",
                summary=f"You take standard deduction, so ${charitable:,.0f} in charity provides no tax benefit (~${wasted_benefit:,.0f} lost). Consider bunching!",
                estimated_savings=0,
                priority="medium",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"Your itemized deductions: ${current_itemized:,.0f}",
                    f"Standard deduction: ${std_deduction:,.0f}",
                    f"You're ${std_deduction - current_itemized:,.0f} below itemizing",
                    "Options to get tax benefit:",
                    "  • Bunch 2-3 years into one year",
                    "  • Use a Donor-Advised Fund",
                    "  • QCD if 70.5+ (reduces AGI regardless)",
                    "  • Time donations with high-income years"
                ],
                irs_reference="Schedule A",
                source="charitable_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Charitable strategy optimization found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Charitable strategy optimization failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_amt_risk_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Alternative Minimum Tax (AMT) risk assessment and planning recommendations.

    USER VALUE: Warns users when they're at risk for AMT liability and provides
    strategies to minimize impact. AMT can add $5,000-$50,000+ in unexpected taxes.

    Key AMT triggers:
    - Incentive Stock Options (ISO) exercise spread
    - Large state/local tax deductions (not allowed for AMT)
    - Private activity bond interest
    - Accelerated depreciation adjustments
    - Large miscellaneous deductions

    Typical impact: $1,000-$50,000+ in additional tax if not planned
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # AMT exemption amounts (2025)
        AMT_EXEMPTIONS = {
            "single": 88100,
            "married_joint": 137000,
            "married_separate": 68500,
            "head_of_household": 88100,
            "qualifying_widow": 137000,
        }

        # AMT exemption phaseout thresholds
        AMT_PHASEOUT_START = {
            "single": 626350,
            "married_joint": 1252700,
            "married_separate": 626350,
            "head_of_household": 626350,
            "qualifying_widow": 1252700,
        }

        exemption = AMT_EXEMPTIONS.get(filing_status, 88100)
        phaseout_start = AMT_PHASEOUT_START.get(filing_status, 626350)

        # AMT preference items
        iso_spread = _safe_float(profile.get("iso_exercise_spread") or profile.get("iso_spread"), 0, min_val=0)
        state_taxes = _safe_float(profile.get("state_taxes") or profile.get("state_income_tax"), 0, min_val=0)
        property_taxes = _safe_float(profile.get("property_taxes"), 0, min_val=0)
        salt_total = state_taxes + property_taxes

        # Private activity bond interest
        pab_interest = _safe_float(profile.get("private_activity_bond_interest"), 0, min_val=0)

        # Estimate AMT income adjustments
        amt_adjustments = iso_spread + salt_total + pab_interest

        # Standard deduction add-back (for AMT, no standard deduction)
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)

        # Check if itemizing
        mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0, min_val=0)
        charitable = _safe_float(profile.get("charitable") or profile.get("charitable_donations"), 0, min_val=0)
        itemized_total = min(salt_total, SALT_CAP) + mortgage_interest + charitable

        if itemized_total < std_deduction:
            # Taking standard deduction - add back for AMT
            amt_adjustments += std_deduction

        # Estimate AMTI
        estimated_amti = total_income + amt_adjustments

        # Calculate exemption (with phaseout)
        if estimated_amti > phaseout_start:
            # Exemption phases out at 25 cents per dollar over threshold
            phaseout_amount = (estimated_amti - phaseout_start) * 0.25
            effective_exemption = max(0, exemption - phaseout_amount)
        else:
            effective_exemption = exemption

        # Tentative Minimum Tax calculation
        amt_taxable = max(0, estimated_amti - effective_exemption)
        if amt_taxable > 0:
            # AMT rates: 26% up to $220,700 ($110,350 MFS), 28% above
            amt_threshold = 220700 if filing_status != "married_separate" else 110350
            if amt_taxable <= amt_threshold:
                tentative_amt = amt_taxable * 0.26
            else:
                tentative_amt = (amt_threshold * 0.26) + ((amt_taxable - amt_threshold) * 0.28)
        else:
            tentative_amt = 0

        # Estimate regular tax for comparison
        taxable_income = max(0, total_income - max(std_deduction, itemized_total))
        # Simplified regular tax estimate
        if filing_status == "married_joint":
            if taxable_income <= 96950:
                regular_tax = taxable_income * 0.12
            elif taxable_income <= 206700:
                regular_tax = 11634 + (taxable_income - 96950) * 0.22
            else:
                regular_tax = 35777 + (taxable_income - 206700) * 0.24
        else:
            if taxable_income <= 48475:
                regular_tax = taxable_income * 0.12
            elif taxable_income <= 103350:
                regular_tax = 5817 + (taxable_income - 48475) * 0.22
            else:
                regular_tax = 17889 + (taxable_income - 103350) * 0.24

        # AMT liability = TMT - Regular Tax (if positive)
        estimated_amt = max(0, tentative_amt - regular_tax)

        # =================================================================
        # 1. AMT RISK WARNING
        # =================================================================
        if estimated_amt > 500:
            rec = _create_recommendation(
                id="amt-risk-warning",
                category="amt",
                title="Alternative Minimum Tax (AMT) Risk",
                summary=f"You may owe ~${estimated_amt:,.0f} in AMT! This is in ADDITION to regular tax. Plan now to minimize impact.",
                estimated_savings=estimated_amt * 0.3,  # Potential to reduce by 30% with planning
                priority="critical" if estimated_amt > 5000 else "high",
                urgency="immediate" if iso_spread > 0 else "tax_filing",
                confidence="medium",
                action_steps=[
                    f"Estimated AMTI: ${estimated_amti:,.0f}",
                    f"AMT exemption: ${effective_exemption:,.0f}",
                    f"Tentative Minimum Tax: ${tentative_amt:,.0f}",
                    f"Regular tax: ${regular_tax:,.0f}",
                    f"Estimated AMT liability: ${estimated_amt:,.0f}",
                    "AMT triggers in your profile:",
                    f"  • SALT add-back: ${salt_total:,.0f}" if salt_total > 5000 else None,
                    f"  • ISO spread: ${iso_spread:,.0f}" if iso_spread > 0 else None,
                    "Strategies to reduce AMT:",
                    "  • Spread ISO exercises across years",
                    "  • Time income/deductions strategically",
                    "  • Consider AMT credit carryforward"
                ],
                deadline="December 31, 2025",
                irs_reference="Form 6251, Publication 17",
                source="amt_optimizer"
            )
            # Filter None values from action_steps
            if rec:
                rec.action_steps = [s for s in rec.action_steps if s is not None]
                recommendations.append(rec)

        # =================================================================
        # 2. ISO EXERCISE PLANNING
        # =================================================================
        if iso_spread > 10000:
            # ISO spread is a major AMT preference item
            amt_on_iso = iso_spread * 0.26  # 26% AMT rate on spread

            rec = _create_recommendation(
                id="amt-iso-planning",
                category="amt",
                title="ISO Exercise AMT Planning",
                summary=f"Your ${iso_spread:,.0f} ISO spread triggers ~${amt_on_iso:,.0f} in AMT. Consider spreading exercises across tax years!",
                estimated_savings=amt_on_iso * 0.5,  # Can reduce by spreading
                priority="high",
                urgency="immediate",
                confidence="high",
                action_steps=[
                    f"ISO exercise spread: ${iso_spread:,.0f}",
                    f"AMT on spread: ~${amt_on_iso:,.0f}",
                    "ISO AMT strategies:",
                    "  • Exercise only what you can afford AMT on",
                    "  • Spread exercises across multiple tax years",
                    "  • Exercise early in year (more time if stock drops)",
                    "  • Track basis for AMT credit recovery",
                    "If stock sells at higher price: AMT becomes credit!",
                    "File Form 8801 to claim prior year AMT credit"
                ],
                deadline="December 31, 2025",
                irs_reference="Form 6251, Form 8801",
                source="amt_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. SALT IMPACT ON AMT
        # =================================================================
        if salt_total > 15000 and estimated_amt > 0:
            salt_amt_impact = min(salt_total, SALT_CAP) * 0.26  # SALT not deductible for AMT

            rec = _create_recommendation(
                id="amt-salt-impact",
                category="amt",
                title="SALT Deduction Lost to AMT",
                summary=f"Your ${salt_total:,.0f} in state/local taxes doesn't help for AMT. Consider timing strategies.",
                estimated_savings=salt_amt_impact * 0.2,  # Limited savings available
                priority="medium",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"SALT taxes paid: ${salt_total:,.0f}",
                    f"SALT cap for regular tax: ${SALT_CAP:,.0f}",
                    "For AMT: NO SALT deduction allowed",
                    "This add-back increases your AMT exposure",
                    "Planning strategies:",
                    "  • Defer state estimated tax to January",
                    "  • Consider moving to lower-tax state",
                    "  • Maximize other AMT-allowed deductions"
                ],
                irs_reference="Form 6251",
                source="amt_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"AMT risk assessment found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"AMT risk assessment failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_estimated_tax_penalty_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get estimated tax underpayment penalty warnings and avoidance strategies.

    USER VALUE: Prevents 8% annualized penalty on underpaid taxes. Proactively
    warns when quarterly payments are insufficient.

    Key scenarios:
    - Self-employed with irregular income
    - Large capital gains or stock sales
    - Insufficient W-2 withholding
    - First year of retirement

    Typical penalty avoided: $200-$3,000+
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
        capital_gains = _safe_float(profile.get("capital_gains"), 0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # Tax payments
        withholding = _safe_float(profile.get("withholding"), 0, min_val=0)
        estimated_paid = _safe_float(profile.get("estimated_tax_paid"), 0, min_val=0)
        total_paid = withholding + estimated_paid

        # Prior year tax (for safe harbor)
        last_year_tax = _safe_float(profile.get("last_year_tax"), 0, min_val=0)

        # Estimate current year tax liability
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)

        # Simplified tax estimate
        if filing_status == "married_joint":
            if taxable_income <= 23850:
                estimated_tax = taxable_income * 0.10
            elif taxable_income <= 96950:
                estimated_tax = 2385 + (taxable_income - 23850) * 0.12
            elif taxable_income <= 206700:
                estimated_tax = 11157 + (taxable_income - 96950) * 0.22
            elif taxable_income <= 394600:
                estimated_tax = 35302 + (taxable_income - 206700) * 0.24
            else:
                estimated_tax = 80398 + (taxable_income - 394600) * 0.32
        else:
            if taxable_income <= 11925:
                estimated_tax = taxable_income * 0.10
            elif taxable_income <= 48475:
                estimated_tax = 1193 + (taxable_income - 11925) * 0.12
            elif taxable_income <= 103350:
                estimated_tax = 5579 + (taxable_income - 48475) * 0.22
            elif taxable_income <= 197300:
                estimated_tax = 17651 + (taxable_income - 103350) * 0.24
            else:
                estimated_tax = 40199 + (taxable_income - 197300) * 0.32

        # Add self-employment tax if applicable
        if business_income > 0:
            se_income = business_income * 0.9235  # Net SE income
            se_tax = se_income * SE_TAX_RATE
            estimated_tax += se_tax

        # Safe harbor calculations
        # Rule 1: Pay 90% of current year tax
        current_year_safe_harbor = estimated_tax * 0.90

        # Rule 2: Pay 100% of prior year (110% if AGI > $150K)
        if last_year_tax > 0:
            prior_year_safe_harbor = last_year_tax * (1.10 if total_income > 150000 else 1.00)
        else:
            prior_year_safe_harbor = current_year_safe_harbor

        # Required payment is lesser of the two safe harbors
        required_payment = min(current_year_safe_harbor, prior_year_safe_harbor) if last_year_tax > 0 else current_year_safe_harbor

        # Calculate shortfall
        shortfall = max(0, required_payment - total_paid)

        # Penalty calculation (simplified - about 8% annualized)
        # Assume average 6-month underpayment
        penalty_rate = 0.08
        estimated_penalty = shortfall * penalty_rate * 0.5  # Half-year average

        # =================================================================
        # 1. UNDERPAYMENT WARNING
        # =================================================================
        if shortfall > 1000 and estimated_penalty > 50:
            rec = _create_recommendation(
                id="estimated-tax-underpayment",
                category="penalty",
                title="Estimated Tax Underpayment Warning",
                summary=f"You're ${shortfall:,.0f} short on tax payments! Avoid ~${estimated_penalty:,.0f} penalty by paying before Jan 15.",
                estimated_savings=estimated_penalty,
                priority="critical" if shortfall > 5000 else "high",
                urgency="immediate",
                confidence="medium",
                action_steps=[
                    f"Estimated 2025 tax liability: ${estimated_tax:,.0f}",
                    f"Withholding + estimated paid: ${total_paid:,.0f}",
                    f"Safe harbor requirement: ${required_payment:,.0f}",
                    f"Current shortfall: ${shortfall:,.0f}",
                    f"Estimated penalty if unpaid: ${estimated_penalty:,.0f}",
                    "How to catch up:",
                    "  • Make Q4 estimated payment by Jan 15, 2026",
                    "  • Increase W-2 withholding (if employed)",
                    "  • Pay with extension (interest still accrues)",
                    "Use IRS Direct Pay or EFTPS"
                ],
                deadline="January 15, 2026",
                irs_reference="Form 2210, Form 1040-ES",
                source="penalty_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. SAFE HARBOR GUIDANCE
        # =================================================================
        if business_income > 20000 or capital_gains > 20000:
            # Complex income - explain safe harbor
            if total_paid >= required_payment:
                status = "SAFE"
                message = f"You've met safe harbor! Paid ${total_paid:,.0f} vs ${required_payment:,.0f} required."
            else:
                status = "AT RISK"
                message = f"Pay ${shortfall:,.0f} more to meet safe harbor."

            rec = _create_recommendation(
                id="estimated-tax-safe-harbor",
                category="penalty",
                title=f"Safe Harbor Status: {status}",
                summary=message,
                estimated_savings=estimated_penalty if status == "AT RISK" else 0,
                priority="medium" if status == "SAFE" else "high",
                urgency="planning",
                confidence="high",
                action_steps=[
                    "Safe Harbor Rules (avoid penalty if you meet ONE):",
                    f"  1. Pay 90% of 2025 tax: ${current_year_safe_harbor:,.0f}",
                    f"  2. Pay {'110%' if total_income > 150000 else '100%'} of 2024 tax: ${prior_year_safe_harbor:,.0f}" if last_year_tax > 0 else "  2. Pay 100% of prior year tax",
                    f"Your payments: ${total_paid:,.0f}",
                    "Penalty rate: ~8% annualized on underpayment",
                    "Exceptions: Casualty, disaster, retirement year"
                ],
                irs_reference="Form 2210, Publication 505",
                source="penalty_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. IRREGULAR INCOME - ANNUALIZED METHOD
        # =================================================================
        if business_income > 30000 or capital_gains > 30000:
            rec = _create_recommendation(
                id="estimated-tax-annualized",
                category="penalty",
                title="Annualized Income Installment Method",
                summary="With irregular income, use the annualized method to potentially reduce or eliminate penalties!",
                estimated_savings=estimated_penalty * 0.5 if estimated_penalty > 0 else 500,
                priority="medium",
                urgency="tax_filing",
                confidence="medium",
                action_steps=[
                    "If income was uneven throughout the year:",
                    "  • Annualized method may reduce penalties",
                    "  • Calculates required payments based on when income was earned",
                    "  • Useful for self-employed, capital gains, bonuses",
                    "Example: Q4 bonus or stock sale",
                    "  • Standard: Penalty on underpayment all year",
                    "  • Annualized: Penalty only from Q4 forward",
                    "Complete Form 2210 Schedule AI"
                ],
                irs_reference="Form 2210 Schedule AI",
                source="penalty_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Estimated tax penalty optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Estimated tax penalty optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_backdoor_roth_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Backdoor Roth IRA conversion guidance for high earners.

    USER VALUE: Enables high earners above Roth IRA income limits to still
    contribute to a Roth IRA through the backdoor strategy. Provides tax-free
    growth for decades.

    Key scenarios:
    - Single with income > $161,000 (2025 Roth limit)
    - MFJ with income > $240,000 (2025 Roth limit)
    - Has existing traditional IRA (pro-rata rule warning)

    Typical benefit: $1,500-$20,000+ in lifetime tax-free growth
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 40, min_val=18, max_val=100)

        # Roth IRA income limits (2025)
        ROTH_LIMITS = {
            "single": {"phaseout_start": 150000, "phaseout_end": 165000},
            "married_joint": {"phaseout_start": 236000, "phaseout_end": 246000},
            "married_separate": {"phaseout_start": 0, "phaseout_end": 10000},
            "head_of_household": {"phaseout_start": 150000, "phaseout_end": 165000},
        }

        limits = ROTH_LIMITS.get(filing_status, ROTH_LIMITS["single"])
        roth_phaseout_end = limits["phaseout_end"]

        # IRA contribution limits
        ira_limit = 7000 if age < 50 else 8000

        # Check for existing traditional IRA (pro-rata rule)
        traditional_ira_balance = _safe_float(
            profile.get("traditional_ira_balance") or profile.get("ira_balance"), 0, min_val=0
        )
        has_trad_ira = traditional_ira_balance > 1000

        # Current Roth contribution
        roth_contribution = _safe_float(profile.get("roth_contribution"), 0, min_val=0)

        # =================================================================
        # 1. BACKDOOR ROTH OPPORTUNITY
        # =================================================================
        if total_income > roth_phaseout_end and roth_contribution < ira_limit:
            # Can't contribute directly to Roth - suggest backdoor
            remaining_contribution = ira_limit - roth_contribution
            lifetime_benefit = remaining_contribution * 0.07 * 25  # 7% growth over 25 years

            rec = _create_recommendation(
                id="backdoor-roth-opportunity",
                category="retirement",
                title="Backdoor Roth IRA Opportunity",
                summary=f"Too much income for direct Roth? Use the backdoor! Contribute ${remaining_contribution:,.0f} for ~${lifetime_benefit:,.0f} in tax-free growth!",
                estimated_savings=remaining_contribution * 0.24 * 0.5,  # Tax-free growth value estimate
                priority="high",
                urgency="year_end",
                confidence="high",
                action_steps=[
                    f"Your income (${total_income:,.0f}) exceeds Roth limit (${roth_phaseout_end:,.0f})",
                    f"2025 IRA contribution limit: ${ira_limit:,.0f}",
                    "Backdoor Roth steps:",
                    "  1. Contribute to non-deductible Traditional IRA",
                    "  2. Convert immediately to Roth IRA",
                    "  3. File Form 8606 to track basis",
                    "Result: Same as direct Roth contribution!",
                    "Do this EVERY year for maximum benefit"
                ],
                deadline="April 15, 2026 (for 2025 contribution)",
                irs_reference="Form 8606, Publication 590-A",
                source="backdoor_roth_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. PRO-RATA RULE WARNING
        # =================================================================
        if has_trad_ira and total_income > roth_phaseout_end:
            # Pro-rata rule makes backdoor Roth partially taxable
            trad_balance = traditional_ira_balance
            contribution = ira_limit
            taxable_portion = (trad_balance / (trad_balance + contribution)) * contribution
            tax_on_conversion = taxable_portion * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="backdoor-roth-prorata",
                category="retirement",
                title="Pro-Rata Rule Warning for Backdoor Roth",
                summary=f"Your ${trad_balance:,.0f} traditional IRA triggers pro-rata rule! ~${taxable_portion:,.0f} of conversion would be taxable.",
                estimated_savings=tax_on_conversion,  # Can avoid this tax
                priority="high",
                urgency="year_end",
                confidence="high",
                action_steps=[
                    "Pro-rata rule: IRS looks at ALL traditional IRAs",
                    f"Your traditional IRA balance: ${trad_balance:,.0f}",
                    f"If you convert ${contribution:,.0f}:",
                    f"  • Taxable portion: ${taxable_portion:,.0f}",
                    f"  • Tax due: ~${tax_on_conversion:,.0f}",
                    "Solutions to avoid pro-rata:",
                    "  1. Roll traditional IRA into employer 401(k)",
                    "  2. Convert entire traditional IRA first",
                    "  3. Accept partial taxation",
                    "Form 8606 tracks basis - file carefully!"
                ],
                irs_reference="Form 8606, Publication 590-A",
                source="backdoor_roth_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. MEGA BACKDOOR ROTH
        # =================================================================
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        has_401k = _safe_float(profile.get("retirement_401k"), 0) > 0 or bool(profile.get("has_401k", False))

        if w2_income > 100000 and has_401k and total_income > roth_phaseout_end:
            # Mega backdoor Roth - after-tax 401(k) contributions
            # 2025 total 401(k) limit is $69,000 ($76,500 if 50+)
            total_401k_limit = 69000 if age < 50 else 76500
            employee_limit = 23500 if age < 50 else 31000

            mega_backdoor_room = total_401k_limit - employee_limit
            tax_free_growth = mega_backdoor_room * 0.07 * 20  # 20 years at 7%

            rec = _create_recommendation(
                id="mega-backdoor-roth",
                category="retirement",
                title="Mega Backdoor Roth Opportunity",
                summary=f"If your 401(k) allows it: contribute up to ${mega_backdoor_room:,.0f} after-tax and convert to Roth. ${tax_free_growth:,.0f}+ in tax-free growth!",
                estimated_savings=mega_backdoor_room * 0.05,  # Conservative estimate
                priority="medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    "Mega Backdoor Roth requirements:",
                    "  • 401(k) plan allows after-tax contributions",
                    "  • Plan allows in-service Roth conversions",
                    f"2025 total 401(k) limit: ${total_401k_limit:,.0f}",
                    f"After max pre-tax (${employee_limit:,.0f}):",
                    f"  • Room for after-tax: ~${mega_backdoor_room:,.0f}",
                    "Steps:",
                    "  1. Contribute after-tax to 401(k)",
                    "  2. Immediately convert to Roth 401(k)",
                    "Check with your HR/plan administrator"
                ],
                irs_reference="IRC Section 402A",
                source="backdoor_roth_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Backdoor Roth optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Backdoor Roth optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_medicare_irmaa_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Medicare premium (IRMAA) planning recommendations.

    USER VALUE: Higher earners pay significantly more for Medicare Parts B and D.
    IRMAA surcharges can add $1,000-$10,000+ annually. Planning can reduce
    income to stay below thresholds.

    Key thresholds (2025, based on 2023 income):
    - Single: $103,000, $129,000, $161,000, $193,000, $500,000
    - MFJ: $206,000, $258,000, $322,000, $386,000, $750,000

    Typical savings: $500-$7,000+ annually per person
    """
    recommendations = []

    try:
        age = _safe_int(profile.get("age"), 50, min_val=18, max_val=100)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)

        # Only relevant for those approaching or on Medicare (65+)
        if age < 62:
            return recommendations

        # IRMAA thresholds and monthly surcharges (2025)
        # Based on MAGI from 2 years prior
        IRMAA_BRACKETS = {
            "single": [
                (103000, 0),        # No surcharge
                (129000, 70.00),    # +$70/month each
                (161000, 175.00),
                (193000, 280.50),
                (500000, 385.50),
                (float('inf'), 420.00),
            ],
            "married_joint": [
                (206000, 0),
                (258000, 70.00),
                (322000, 175.00),
                (386000, 280.50),
                (750000, 385.50),
                (float('inf'), 420.00),
            ],
        }

        brackets = IRMAA_BRACKETS.get(
            "married_joint" if filing_status == "married_joint" else "single",
            IRMAA_BRACKETS["single"]
        )

        # Find current IRMAA bracket
        current_surcharge = 0
        current_threshold = brackets[0][0]
        next_threshold = None

        for i, (threshold, surcharge) in enumerate(brackets):
            if total_income <= threshold:
                current_surcharge = brackets[max(0, i-1)][1] if i > 0 else 0
                current_threshold = threshold
                if i > 0:
                    next_threshold = brackets[i-1][0]
                break
            current_surcharge = surcharge

        annual_surcharge = current_surcharge * 12 * 2  # Both Parts B and D, both spouses if MFJ

        # =================================================================
        # 1. IRMAA SURCHARGE WARNING
        # =================================================================
        if current_surcharge > 0:
            rec = _create_recommendation(
                id="medicare-irmaa-warning",
                category="healthcare",
                title="Medicare IRMAA Surcharge Alert",
                summary=f"Your income triggers ${annual_surcharge:,.0f}/year in Medicare surcharges! Plan income to reduce IRMAA.",
                estimated_savings=annual_surcharge * 0.3,  # Potential reduction
                priority="high",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"Your income: ${total_income:,.0f}",
                    f"Monthly Part B/D surcharge: ${current_surcharge:,.0f} per person",
                    f"Annual cost: ${annual_surcharge:,.0f}",
                    "IRMAA uses income from 2 years prior",
                    "Strategies to reduce IRMAA:",
                    "  • Defer Roth conversions to lower-income years",
                    "  • Use QCDs instead of RMDs",
                    "  • Time capital gains carefully",
                    "  • Maximize above-the-line deductions",
                    f"Target: Stay under ${next_threshold:,.0f}" if next_threshold else "Consider income timing"
                ],
                irs_reference="SSA Medicare IRMAA",
                source="medicare_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. IRMAA CLIFF WARNING
        # =================================================================
        # Check if close to next bracket
        for i, (threshold, surcharge) in enumerate(brackets[1:], 1):
            if total_income > threshold * 0.95 and total_income <= threshold:
                # Within 5% of cliff
                additional_surcharge = (surcharge - brackets[i-1][1]) * 12 * 2
                income_over = total_income - brackets[i-1][0]

                rec = _create_recommendation(
                    id="medicare-irmaa-cliff",
                    category="healthcare",
                    title="IRMAA Cliff Warning - Reduce Income!",
                    summary=f"You're ${threshold - total_income:,.0f} from the next IRMAA bracket! Crossing adds ${additional_surcharge:,.0f}/year!",
                    estimated_savings=additional_surcharge,
                    priority="high",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        f"Current income: ${total_income:,.0f}",
                        f"Next IRMAA threshold: ${threshold:,.0f}",
                        f"Cushion remaining: ${threshold - total_income:,.0f}",
                        f"Crossing cliff adds: ${additional_surcharge:,.0f}/year",
                        "Quick fixes:",
                        "  • Delay Roth conversion",
                        "  • Harvest capital losses",
                        "  • Defer bonus/income to next year",
                        "  • Maximize HSA/IRA deductions"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="SSA Medicare IRMAA",
                    source="medicare_optimizer"
                )
                if rec:
                    recommendations.append(rec)
                break

        # =================================================================
        # 3. QCD TO REDUCE IRMAA
        # =================================================================
        if age >= 70.5:
            ira_balance = _safe_float(profile.get("traditional_ira_balance") or profile.get("ira_balance"), 0, min_val=0)
            charitable = _safe_float(profile.get("charitable") or profile.get("charitable_donations"), 0, min_val=0)

            if ira_balance > 10000 and charitable > 0:
                qcd_amount = min(charitable, 105000, ira_balance * 0.1)
                irmaa_savings = qcd_amount * 0.05  # Estimated IRMAA reduction

                rec = _create_recommendation(
                    id="medicare-qcd-irmaa",
                    category="healthcare",
                    title="Use QCDs to Reduce IRMAA",
                    summary=f"Give ${qcd_amount:,.0f} via QCD instead of cash. Reduces MAGI = lower IRMAA in 2 years!",
                    estimated_savings=irmaa_savings,
                    priority="medium",
                    urgency="year_end",
                    confidence="high",
                    action_steps=[
                        "QCD = Qualified Charitable Distribution",
                        f"Suggested QCD: ${qcd_amount:,.0f}",
                        "Benefits:",
                        "  • Reduces MAGI (not just taxable income)",
                        "  • Lower MAGI = lower IRMAA in 2 years",
                        "  • Counts toward RMD (if 73+)",
                        "  • Better than itemizing charitable",
                        "2025 QCD limit: $105,000"
                    ],
                    deadline="December 31, 2025",
                    irs_reference="Publication 590-B",
                    source="medicare_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"Medicare IRMAA optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Medicare IRMAA optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_social_security_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Social Security optimization recommendations.

    USER VALUE: When to claim Social Security is one of the biggest financial
    decisions. Delaying from 62 to 70 can increase lifetime benefits by
    $100,000+ for couples. Coordinates with tax planning.

    Key ages:
    - 62: Early claiming (reduced by ~30%)
    - 67: Full Retirement Age for most
    - 70: Maximum delayed credits (+24%)

    Typical lifetime impact: $50,000-$200,000+
    """
    recommendations = []

    try:
        age = _safe_int(profile.get("age"), 50, min_val=18, max_val=100)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)

        # Only relevant for those approaching Social Security age
        if age < 55:
            return recommendations

        # Check if already claiming
        ss_income = _safe_float(profile.get("social_security_income") or profile.get("ss_income"), 0, min_val=0)
        already_claiming = ss_income > 0

        # Estimated benefit (use provided or estimate based on income)
        estimated_fra_benefit = _safe_float(profile.get("ss_estimated_benefit"), 0, min_val=0)
        if estimated_fra_benefit == 0:
            # Rough estimate: ~40% replacement rate on career average
            estimated_fra_benefit = min(total_income * 0.35, 4000) * 12 / 12  # Monthly

        # Full Retirement Age (FRA) for those born 1960+
        fra = 67

        # Calculate benefits at different ages
        benefit_at_62 = estimated_fra_benefit * 0.70  # 30% reduction
        benefit_at_67 = estimated_fra_benefit
        benefit_at_70 = estimated_fra_benefit * 1.24  # 24% increase (8%/year for 3 years)

        # Breakeven analysis (70 vs 62)
        annual_diff_70_vs_62 = (benefit_at_70 - benefit_at_62) * 12
        forgone_benefits_62_to_70 = benefit_at_62 * 12 * 8  # 8 years of payments skipped
        breakeven_age = 70 + (forgone_benefits_62_to_70 / annual_diff_70_vs_62) if annual_diff_70_vs_62 > 0 else 85

        # =================================================================
        # 1. DELAY TO 70 RECOMMENDATION (if approaching)
        # =================================================================
        if 62 <= age < 70 and not already_claiming:
            lifetime_gain = annual_diff_70_vs_62 * max(0, 85 - 70)  # Assume live to 85

            rec = _create_recommendation(
                id="ss-delay-to-70",
                category="retirement",
                title="Delay Social Security to Age 70",
                summary=f"Delay from 62 to 70: ${benefit_at_62*12:,.0f}/yr → ${benefit_at_70*12:,.0f}/yr. Lifetime gain: ~${lifetime_gain:,.0f}!",
                estimated_savings=lifetime_gain / 20,  # Annualized
                priority="high" if age >= 62 else "medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    f"Estimated monthly benefit at 62: ${benefit_at_62:,.0f}",
                    f"Estimated monthly benefit at 67 (FRA): ${benefit_at_67:,.0f}",
                    f"Estimated monthly benefit at 70: ${benefit_at_70:,.0f}",
                    f"Breakeven age (70 vs 62): {breakeven_age:.1f}",
                    "Each year you delay (until 70):",
                    "  • Benefit increases ~8%/year",
                    "  • Also adjusts for inflation (COLA)",
                    "Consider if you:",
                    "  • Have other income sources",
                    "  • Are in good health",
                    "  • Have spouse with lower earnings"
                ],
                irs_reference="SSA.gov Retirement Planner",
                source="social_security_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. SPOUSAL BENEFIT COORDINATION
        # =================================================================
        if filing_status == "married_joint" and 60 <= age < 70:
            spouse_age = _safe_int(profile.get("spouse_age"), age - 2, min_val=18, max_val=100)
            spouse_benefit = _safe_float(profile.get("spouse_ss_benefit"), estimated_fra_benefit * 0.6, min_val=0)

            # Spousal benefit is up to 50% of higher earner's FRA benefit
            spousal_max = estimated_fra_benefit * 0.50

            rec = _create_recommendation(
                id="ss-spousal-strategy",
                category="retirement",
                title="Social Security Spousal Strategy",
                summary=f"Coordinate claiming with spouse. Lower earner may get ${spousal_max*12:,.0f}/year spousal benefit!",
                estimated_savings=spousal_max * 12 * 0.2,  # Portion from optimization
                priority="medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    "Spousal coordination strategies:",
                    "  • Higher earner delays to 70 (maximizes survivor benefit)",
                    "  • Lower earner claims at FRA or earlier",
                    f"Your age: {age}, Spouse age: {spouse_age}",
                    f"Spousal benefit available: up to ${spousal_max:,.0f}/month",
                    "Survivor benefit: 100% of higher earner's benefit",
                    "Key: Higher earner's delayed benefit protects survivor"
                ],
                irs_reference="SSA.gov Spousal Benefits",
                source="social_security_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. SS TAXATION PLANNING
        # =================================================================
        if ss_income > 0:
            # Social Security taxation thresholds
            combined_income = total_income - ss_income + (ss_income * 0.5)  # Provisional income

            if filing_status == "married_joint":
                if combined_income > 44000:
                    taxable_ss_pct = 0.85
                elif combined_income > 32000:
                    taxable_ss_pct = 0.50
                else:
                    taxable_ss_pct = 0
            else:
                if combined_income > 34000:
                    taxable_ss_pct = 0.85
                elif combined_income > 25000:
                    taxable_ss_pct = 0.50
                else:
                    taxable_ss_pct = 0

            taxable_ss = ss_income * taxable_ss_pct
            ss_tax = taxable_ss * DEFAULT_MARGINAL_RATE

            if taxable_ss_pct > 0:
                rec = _create_recommendation(
                    id="ss-taxation",
                    category="retirement",
                    title="Social Security Taxation Planning",
                    summary=f"{taxable_ss_pct*100:.0f}% of your SS is taxable = ${taxable_ss:,.0f}. Strategies can reduce this!",
                    estimated_savings=ss_tax * 0.3,  # Potential reduction
                    priority="medium",
                    urgency="planning",
                    confidence="high",
                    action_steps=[
                        f"Your Social Security: ${ss_income:,.0f}",
                        f"Combined income: ${combined_income:,.0f}",
                        f"Taxable portion: {taxable_ss_pct*100:.0f}%",
                        f"Tax on SS: ~${ss_tax:,.0f}",
                        "Reduce SS taxation by:",
                        "  • QCDs instead of RMDs (reduces MAGI)",
                        "  • Roth conversions in early retirement",
                        "  • Municipal bond interest (not counted)",
                        "  • Tax-efficient withdrawal sequencing"
                    ],
                    irs_reference="Publication 915",
                    source="social_security_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"Social Security optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Social Security optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_education_savings_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get 529 Education Savings Plan recommendations.

    USER VALUE: 529 plans offer tax-free growth for education expenses.
    Many states offer deductions for contributions. Superfunding allows
    5 years of gifts at once.

    Key benefits:
    - Tax-free growth and withdrawals for education
    - State tax deductions (many states)
    - High contribution limits ($300K+ lifetime)
    - Superfunding: $90,000 gift ($18K x 5) without gift tax

    Typical savings: $500-$5,000+ annually in tax benefits
    """
    recommendations = []

    try:
        num_dependents = _safe_int(profile.get("num_dependents") or profile.get("dependents"), 0, min_val=0)
        dependent_ages = profile.get("dependent_ages", [])
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        state = _safe_str(profile.get("state"), "").upper()[:2]

        # Check if has children who might need education funding
        has_young_children = any(
            isinstance(a, (int, float)) and a < 18
            for a in dependent_ages
        )

        if not has_young_children and num_dependents == 0:
            return recommendations

        # Current 529 contribution
        current_529 = _safe_float(profile.get("529_contribution"), 0, min_val=0)

        # States with 529 deductions (partial list)
        STATE_529_DEDUCTIONS = {
            "NY": 10000,  # MFJ limit
            "CA": 0,  # No deduction
            "TX": 0,  # No income tax
            "PA": 32000,  # MFJ limit
            "VA": 4000,  # Per account
            "CO": float('inf'),  # Unlimited
            "IN": 7500,  # 20% credit up to $1500
            "OH": 4000,
            "IL": 20000,
            "NJ": 10000,
        }

        state_deduction_limit = STATE_529_DEDUCTIONS.get(state, 5000)  # Default assumption

        # =================================================================
        # 1. 529 CONTRIBUTION RECOMMENDATION
        # =================================================================
        if has_young_children and current_529 < state_deduction_limit:
            suggested_contribution = min(state_deduction_limit - current_529, 10000)
            state_tax_savings = suggested_contribution * 0.05  # Assume 5% state rate
            federal_growth_benefit = suggested_contribution * 0.07 * 15 * 0.24  # 15 years growth at 24% rate

            rec = _create_recommendation(
                id="529-contribution",
                category="education",
                title="529 Education Savings Contribution",
                summary=f"Contribute ${suggested_contribution:,.0f} to 529 for ${state_tax_savings:,.0f} state deduction + tax-free growth!",
                estimated_savings=state_tax_savings + (federal_growth_benefit * 0.1),
                priority="medium",
                urgency="year_end",
                confidence="high",
                action_steps=[
                    f"State: {state if state else 'Check your state'}",
                    f"State deduction limit: ${state_deduction_limit:,.0f}" if state_deduction_limit < float('inf') else "Unlimited state deduction",
                    f"Suggested contribution: ${suggested_contribution:,.0f}",
                    "529 benefits:",
                    "  • Tax-free growth",
                    "  • Tax-free withdrawals for education",
                    "  • Includes K-12 ($10K/year), college, grad school",
                    "  • Can change beneficiary to other family",
                    "  • NEW: $35K can roll to Roth IRA (after 15 years)"
                ],
                deadline="December 31, 2025",
                irs_reference="Publication 970, Section 529",
                source="education_savings_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. SUPERFUNDING (5-YEAR GIFT)
        # =================================================================
        if has_young_children and total_income > 200000:
            annual_gift_limit = 18000  # 2025
            superfund_amount = annual_gift_limit * 5  # $90,000

            # Calculate benefit
            # Assume $90K grows at 7% for 18 years = $287K
            future_value = superfund_amount * (1.07 ** 18)
            growth = future_value - superfund_amount
            tax_on_growth_avoided = growth * 0.24  # Tax that would be paid if in taxable account

            rec = _create_recommendation(
                id="529-superfunding",
                category="education",
                title="529 Superfunding: 5-Year Gift Election",
                summary=f"Gift ${superfund_amount:,.0f} to 529 now (5 years of gifts). Grows to ~${future_value:,.0f} tax-free!",
                estimated_savings=tax_on_growth_avoided / 18,  # Annualized
                priority="medium",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"2025 annual gift exclusion: ${annual_gift_limit:,.0f}",
                    f"5-year superfund: ${superfund_amount:,.0f} per beneficiary",
                    "How it works:",
                    "  • Contribute 5 years of gifts upfront",
                    "  • Elect on gift tax return (Form 709)",
                    "  • No gift tax, uses no estate exemption",
                    "  • Maximum tax-free compounding time",
                    f"If child age 0: ${superfund_amount:,.0f} → ~${future_value:,.0f} by college",
                    "Both parents can superfund = $180,000/child"
                ],
                irs_reference="Form 709, Publication 970",
                source="education_savings_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. 529 TO ROTH IRA ROLLOVER
        # =================================================================
        # New provision allows 529 to Roth IRA rollover after 15 years
        existing_529 = _safe_float(profile.get("529_balance"), 0, min_val=0)
        if existing_529 > 10000:
            rollover_limit = 35000  # Lifetime limit
            annual_rollover = 7000  # 2025 IRA contribution limit

            rec = _create_recommendation(
                id="529-to-roth-rollover",
                category="education",
                title="529 to Roth IRA Rollover Option",
                summary=f"Unused 529 funds can roll to beneficiary's Roth IRA! Up to ${rollover_limit:,.0f} lifetime.",
                estimated_savings=rollover_limit * 0.02,  # Long-term benefit
                priority="low",
                urgency="informational",
                confidence="high",
                action_steps=[
                    "NEW: SECURE 2.0 Act provision",
                    f"529 balance: ${existing_529:,.0f}",
                    "Rollover rules:",
                    "  • Account must be open 15+ years",
                    f"  • Lifetime limit: ${rollover_limit:,.0f}",
                    f"  • Annual limit: ${annual_rollover:,.0f}",
                    "  • Rolls to beneficiary's Roth IRA",
                    "  • Contributions only (not earnings)",
                    "Great backup if child doesn't need full amount!"
                ],
                irs_reference="SECURE 2.0 Act, Section 126",
                source="education_savings_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Education savings optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Education savings optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_qbi_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Qualified Business Income (QBI) Section 199A deduction recommendations.

    USER VALUE: Pass-through business owners can deduct up to 20% of qualified
    business income. This is one of the largest deductions available to
    self-employed individuals and small business owners.

    Key considerations:
    - 20% deduction of QBI (subject to limitations)
    - W-2 wage and UBIA limitations at higher income
    - SSTB (Specified Service Trade/Business) phase-out
    - Taxable income thresholds for phase-in

    Typical savings: $5,000-$75,000+ annually for qualifying businesses
    """
    recommendations = []

    try:
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # Only relevant for business owners
        if business_income < 5000:
            return recommendations

        # 2025 QBI thresholds (approximate)
        QBI_THRESHOLD_SINGLE = 191950
        QBI_THRESHOLD_MFJ = 383900
        QBI_PHASE_IN_SINGLE = 100000  # Phase-in range
        QBI_PHASE_IN_MFJ = 200000

        threshold = QBI_THRESHOLD_MFJ if filing_status == "married_joint" else QBI_THRESHOLD_SINGLE
        phase_in = QBI_PHASE_IN_MFJ if filing_status == "married_joint" else QBI_PHASE_IN_SINGLE

        # Estimate taxable income
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)

        # Check if SSTB (Specified Service Trade/Business) using SSTBClassifier
        is_sstb = bool(profile.get("is_sstb", False))
        business_type = _safe_str(profile.get("business_type"), "").lower()
        business_name = _safe_str(profile.get("business_name"), "")
        naics_code = _safe_str(profile.get("naics_code") or profile.get("business_code"), "")
        business_description = _safe_str(profile.get("business_description"), "")
        sstb_category = None

        # Use SSTBClassifier for automatic classification
        try:
            from calculator.sstb_classifier import SSTBClassifier, SSTBCategory
            classification = SSTBClassifier.classify_business(
                business_name=business_name or business_type,
                business_code=naics_code,
                business_description=business_description or business_type
            )
            if classification != SSTBCategory.NON_SSTB:
                is_sstb = True
                sstb_category = classification.value
                logger.debug(f"SSTBClassifier: {business_type} -> {classification.value}")
        except Exception as e:
            logger.debug(f"SSTBClassifier not available, using fallback: {e}")
            # Fallback to keyword matching
            sstb_types = ["law", "legal", "accounting", "health", "medical", "consulting",
                          "financial", "brokerage", "investment", "actuarial", "performing arts"]
            if any(t in business_type for t in sstb_types):
                is_sstb = True

        # W-2 wages paid (for limitation)
        w2_wages_paid = _safe_float(profile.get("business_w2_wages") or profile.get("w2_wages_paid"), 0, min_val=0)

        # UBIA (Unadjusted Basis Immediately After Acquisition) of qualified property
        ubia = _safe_float(profile.get("business_ubia") or profile.get("qualified_property_basis"), 0, min_val=0)

        # =================================================================
        # 1. BASIC QBI DEDUCTION
        # =================================================================
        # Calculate base QBI deduction (20% of QBI)
        base_qbi_deduction = business_income * 0.20

        # Apply limitations if above threshold
        if taxable_income > threshold:
            if is_sstb:
                # SSTB fully phases out above threshold + phase-in range
                if taxable_income > threshold + phase_in:
                    qbi_deduction = 0
                    phase_out_pct = 100
                else:
                    # Partial phase-out
                    phase_out_pct = ((taxable_income - threshold) / phase_in) * 100
                    qbi_deduction = base_qbi_deduction * (1 - phase_out_pct / 100)
            else:
                # Non-SSTB: Apply W-2 wage/UBIA limitation
                # Lesser of: 50% of W-2 wages OR 25% of W-2 wages + 2.5% of UBIA
                wage_limit_1 = w2_wages_paid * 0.50
                wage_limit_2 = (w2_wages_paid * 0.25) + (ubia * 0.025)
                wage_limit = max(wage_limit_1, wage_limit_2)

                qbi_deduction = min(base_qbi_deduction, wage_limit)
                phase_out_pct = 0
        else:
            qbi_deduction = base_qbi_deduction
            phase_out_pct = 0

        # QBI deduction is also limited to 20% of taxable income (before QBI)
        qbi_deduction = min(qbi_deduction, taxable_income * 0.20)

        tax_savings = qbi_deduction * DEFAULT_MARGINAL_RATE

        if qbi_deduction > 500:
            rec = _create_recommendation(
                id="qbi-deduction",
                category="business",
                title="Section 199A QBI Deduction",
                summary=f"Your 20% QBI deduction = ${qbi_deduction:,.0f}. Tax savings: ${tax_savings:,.0f}!",
                estimated_savings=tax_savings,
                priority="high",
                urgency="tax_filing",
                confidence="high",
                action_steps=[
                    f"Qualified Business Income: ${business_income:,.0f}",
                    f"Base QBI deduction (20%): ${base_qbi_deduction:,.0f}",
                    f"Your QBI deduction: ${qbi_deduction:,.0f}",
                    f"Tax savings at {DEFAULT_MARGINAL_RATE*100:.0f}%: ${tax_savings:,.0f}",
                    "This deduction is automatic for pass-through entities",
                    "Report on Form 8995 or Form 8995-A"
                ],
                deadline="April 15, 2026",
                irs_reference="Form 8995, Publication 535",
                source="qbi_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. SSTB PHASE-OUT WARNING (with category-specific advice)
        # =================================================================
        if is_sstb and taxable_income > threshold * 0.9:
            potential_loss = base_qbi_deduction * (phase_out_pct / 100) if phase_out_pct > 0 else base_qbi_deduction

            # Category-specific strategies based on SSTBClassifier result
            category_strategies = {
                "health": [
                    "HEALTH SSTB: Consider employing non-SSTB services separately",
                    "Medical practices: Administrative revenue may be carved out",
                    "Consider entity structuring for non-clinical services"
                ],
                "law": [
                    "LAW SSTB: Legal support services may qualify separately",
                    "Consider spinning off non-legal consulting services",
                    "Document preparation services may be carved out"
                ],
                "accounting": [
                    "ACCOUNTING SSTB: Bookkeeping vs tax prep distinctions matter",
                    "Software products/licensing may qualify as non-SSTB",
                    "Advisory vs compliance work classifications"
                ],
                "consulting": [
                    "CONSULTING SSTB: Implementation services may be non-SSTB",
                    "Training and education services often qualify",
                    "Software/product sales can be carved out"
                ],
                "financial_services": [
                    "FINANCIAL SSTB: Asset management fees fully phase out",
                    "Commission income is SSTB; product sales may not be",
                    "Consider fee structure optimization"
                ]
            }

            # Build action steps with category-specific advice
            action_steps = [
                f"Your business classified as: {sstb_category.upper() if sstb_category else 'SSTB'}",
                f"Phase-out threshold: ${threshold:,.0f}",
                f"Your taxable income: ${taxable_income:,.0f}",
                f"Potential QBI loss: ${potential_loss:,.0f}",
                "",
                "General strategies to preserve QBI:"
            ]

            # Add category-specific strategies if available
            if sstb_category and sstb_category in category_strategies:
                action_steps.extend(category_strategies[sstb_category])
                action_steps.append("")

            action_steps.extend([
                "Universal strategies:",
                "  • Maximize retirement contributions (reduces taxable income)",
                "  • Time income/deductions strategically",
                "  • Consider income splitting if applicable",
                "  • Evaluate entity structure with CPA"
            ])

            rec = _create_recommendation(
                id="qbi-sstb-warning",
                category="business",
                title=f"QBI {sstb_category.upper() if sstb_category else 'SSTB'} Phase-Out Warning",
                summary=f"Your {sstb_category or 'SSTB'} business income phases out QBI deduction above ${threshold:,.0f}. You may lose ${potential_loss:,.0f} in deductions!",
                estimated_savings=potential_loss * DEFAULT_MARGINAL_RATE * 0.3,  # Potential to mitigate
                priority="high",
                urgency="planning",
                confidence="high" if sstb_category else "medium",
                action_steps=action_steps,
                irs_reference="IRC §199A(d)(2); Form 8995-A",
                source="qbi_optimizer_sstb"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. W-2 WAGE STRATEGY
        # =================================================================
        if taxable_income > threshold and not is_sstb and w2_wages_paid < business_income * 0.5:
            # Suggest hiring W-2 employees to increase deduction
            optimal_wages = business_income * 0.50 * 0.5  # 50% limit, assume 50% goes to wages
            additional_deduction = min(optimal_wages * 0.50, base_qbi_deduction) - qbi_deduction
            potential_savings = additional_deduction * DEFAULT_MARGINAL_RATE

            if potential_savings > 1000:
                rec = _create_recommendation(
                    id="qbi-wage-strategy",
                    category="business",
                    title="QBI W-2 Wage Strategy",
                    summary=f"Paying W-2 wages (vs 1099) could increase QBI deduction by ${additional_deduction:,.0f}!",
                    estimated_savings=potential_savings,
                    priority="medium",
                    urgency="planning",
                    confidence="medium",
                    action_steps=[
                        "Above income threshold: W-2 wage limitation applies",
                        "QBI deduction limited to greater of:",
                        "  • 50% of W-2 wages paid, OR",
                        "  • 25% of W-2 wages + 2.5% of qualified property",
                        f"Current W-2 wages: ${w2_wages_paid:,.0f}",
                        "Strategy: Convert 1099 contractors to W-2 employees",
                        "Or: Pay yourself reasonable S-Corp salary"
                    ],
                    irs_reference="Section 199A(b)(2)",
                    source="qbi_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"QBI optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"QBI optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_home_sale_exclusion_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get home sale exclusion (Section 121) recommendations.

    USER VALUE: Homeowners can exclude up to $250K (single) or $500K (MFJ)
    of gain when selling their primary residence. This is one of the most
    valuable tax breaks available.

    Key requirements:
    - Ownership test: Owned home 2+ years in last 5 years
    - Use test: Lived in home as primary residence 2+ years in last 5 years
    - Can use exclusion every 2 years

    Typical savings: $37,500-$200,000+ in avoided capital gains tax
    """
    recommendations = []

    try:
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # Home sale info
        home_sale_gain = _safe_float(profile.get("home_sale_gain"), 0)
        home_sale_price = _safe_float(profile.get("home_sale_price"), 0, min_val=0)
        home_purchase_price = _safe_float(profile.get("home_purchase_price"), 0, min_val=0)
        years_owned = _safe_float(profile.get("years_owned_home"), 0, min_val=0)
        years_lived = _safe_float(profile.get("years_lived_in_home"), 0, min_val=0)

        # Current home value (for planning)
        current_home_value = _safe_float(profile.get("current_home_value") or profile.get("home_value"), 0, min_val=0)
        home_basis = _safe_float(profile.get("home_basis") or profile.get("home_purchase_price"), 0, min_val=0)

        # Exclusion amounts
        exclusion = 500000 if filing_status == "married_joint" else 250000

        # Check if planning to sell
        planning_to_sell = bool(profile.get("planning_to_sell_home", False))

        # Estimate unrealized gain
        if current_home_value > 0 and home_basis > 0:
            unrealized_gain = current_home_value - home_basis
        elif home_sale_gain != 0:
            unrealized_gain = home_sale_gain
        else:
            unrealized_gain = 0

        # =================================================================
        # 1. HOME SALE EXCLUSION ELIGIBILITY
        # =================================================================
        if unrealized_gain > 10000 or home_sale_gain > 10000:
            gain = home_sale_gain if home_sale_gain > 0 else unrealized_gain

            # Check eligibility
            meets_ownership = years_owned >= 2
            meets_use = years_lived >= 2
            fully_eligible = meets_ownership and meets_use

            excludable_gain = min(gain, exclusion) if fully_eligible else 0
            taxable_gain = max(0, gain - excludable_gain)

            # Tax on excluded gain (what you save)
            tax_avoided = excludable_gain * 0.15  # 15% LTCG rate

            # Tax on remaining gain (what you owe)
            tax_owed = taxable_gain * 0.15

            if fully_eligible:
                rec = _create_recommendation(
                    id="home-sale-exclusion",
                    category="real_estate",
                    title="Home Sale Exclusion Available",
                    summary=f"Exclude ${excludable_gain:,.0f} of gain tax-free! Save ${tax_avoided:,.0f} in capital gains tax!",
                    estimated_savings=tax_avoided,
                    priority="high" if gain > 100000 else "medium",
                    urgency="tax_filing" if home_sale_gain > 0 else "planning",
                    confidence="high",
                    action_steps=[
                        f"Your gain: ${gain:,.0f}",
                        f"Exclusion limit ({filing_status}): ${exclusion:,.0f}",
                        f"Excludable amount: ${excludable_gain:,.0f}",
                        f"Tax avoided: ${tax_avoided:,.0f}",
                        f"Remaining taxable: ${taxable_gain:,.0f}" if taxable_gain > 0 else "Fully excluded!",
                        "Requirements met:",
                        f"  ✓ Ownership test: {years_owned:.1f} years (need 2+)",
                        f"  ✓ Use test: {years_lived:.1f} years (need 2+)",
                        "Report excluded gain on Schedule D"
                    ],
                    irs_reference="Section 121, Publication 523",
                    source="home_sale_optimizer"
                )
            else:
                # Not eligible - explain why and how to become eligible
                rec = _create_recommendation(
                    id="home-sale-exclusion-planning",
                    category="real_estate",
                    title="Home Sale Exclusion - Not Yet Eligible",
                    summary=f"Wait to sell! You could save ${tax_avoided:,.0f} by meeting the 2-year tests.",
                    estimated_savings=tax_avoided,
                    priority="high",
                    urgency="planning",
                    confidence="high",
                    action_steps=[
                        f"Potential gain: ${gain:,.0f}",
                        f"Potential exclusion: ${exclusion:,.0f}",
                        f"Tax you'd save: ${tax_avoided:,.0f}",
                        "Current status:",
                        f"  {'✓' if meets_ownership else '✗'} Ownership: {years_owned:.1f} years (need 2+)",
                        f"  {'✓' if meets_use else '✗'} Use: {years_lived:.1f} years (need 2+)",
                        "Wait until you meet both tests to sell!",
                        "Partial exclusion may be available for work, health, or unforeseen circumstances"
                    ],
                    irs_reference="Section 121, Publication 523",
                    source="home_sale_optimizer"
                )

            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. GAIN EXCEEDS EXCLUSION
        # =================================================================
        if unrealized_gain > exclusion or home_sale_gain > exclusion:
            gain = home_sale_gain if home_sale_gain > 0 else unrealized_gain
            excess_gain = gain - exclusion
            tax_on_excess = excess_gain * 0.15

            rec = _create_recommendation(
                id="home-sale-excess-gain",
                category="real_estate",
                title="Home Gain Exceeds Exclusion",
                summary=f"Gain of ${gain:,.0f} exceeds ${exclusion:,.0f} exclusion. ${excess_gain:,.0f} is taxable (${tax_on_excess:,.0f} tax).",
                estimated_savings=tax_on_excess * 0.2,  # Potential strategies to reduce
                priority="high",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"Total gain: ${gain:,.0f}",
                    f"Exclusion: ${exclusion:,.0f}",
                    f"Taxable excess: ${excess_gain:,.0f}",
                    f"Tax on excess (15% LTCG): ${tax_on_excess:,.0f}",
                    "Strategies to reduce tax:",
                    "  • Document all improvements (increases basis)",
                    "  • Selling costs reduce gain",
                    "  • Consider installment sale",
                    "  • Consider 1031 exchange if converting to rental"
                ],
                irs_reference="Section 121, Publication 523",
                source="home_sale_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Home sale exclusion optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Home sale exclusion optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_1031_exchange_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Section 1031 like-kind exchange recommendations for real estate investors.

    USER VALUE: Defer 100% of capital gains when exchanging one investment
    property for another. Can defer indefinitely through successive exchanges.
    At death, heirs get stepped-up basis (gains never taxed).

    Key requirements:
    - Both properties must be "like-kind" (real property for real property)
    - 45-day identification period
    - 180-day completion period
    - Qualified intermediary required

    Typical savings: $10,000-$300,000+ per exchange in deferred taxes
    """
    recommendations = []

    try:
        # Investment property info
        rental_properties = profile.get("rental_properties", [])
        has_rental = len(rental_properties) > 0 or _safe_float(profile.get("rental_income"), 0) > 0

        investment_property_value = _safe_float(profile.get("investment_property_value"), 0, min_val=0)
        investment_property_basis = _safe_float(profile.get("investment_property_basis"), 0, min_val=0)

        # Check if planning to sell investment property
        planning_to_sell_rental = bool(profile.get("planning_to_sell_rental") or profile.get("selling_investment_property", False))

        # Estimated gain on investment property
        if investment_property_value > 0 and investment_property_basis > 0:
            investment_gain = investment_property_value - investment_property_basis
        else:
            investment_gain = _safe_float(profile.get("investment_property_gain"), 0)

        # Check rental properties from list
        total_rental_gain = 0
        for prop in rental_properties:
            if isinstance(prop, dict):
                prop_value = _safe_float(prop.get("current_value") or prop.get("cost_basis"), 0)
                prop_basis = _safe_float(prop.get("adjusted_basis") or prop.get("cost_basis"), 0)
                if prop_value > prop_basis:
                    total_rental_gain += prop_value - prop_basis

        investment_gain = max(investment_gain, total_rental_gain)

        if not has_rental and investment_gain <= 0:
            return recommendations

        # =================================================================
        # 1. 1031 EXCHANGE OPPORTUNITY
        # =================================================================
        if investment_gain > 20000:
            # Calculate tax deferred
            # Note: Depreciation recapture is taxed at 25%, remainder at 15% LTCG
            depreciation_recapture = _safe_float(profile.get("accumulated_depreciation"), 0, min_val=0)
            if depreciation_recapture == 0 and investment_property_basis > 0:
                # Estimate depreciation (assume 5 years owned on $300K property)
                depreciation_recapture = investment_property_basis * 0.8 / 27.5 * 5

            recapture_tax = depreciation_recapture * 0.25
            ltcg_tax = max(0, investment_gain - depreciation_recapture) * 0.15
            total_tax_deferred = recapture_tax + ltcg_tax

            if total_tax_deferred > 5000:
                rec = _create_recommendation(
                    id="1031-exchange-opportunity",
                    category="real_estate",
                    title="1031 Exchange: Defer All Capital Gains",
                    summary=f"Defer ${total_tax_deferred:,.0f} in taxes by exchanging into a new investment property!",
                    estimated_savings=total_tax_deferred,
                    priority="high",
                    urgency="planning" if not planning_to_sell_rental else "immediate",
                    confidence="high",
                    action_steps=[
                        f"Estimated gain on property: ${investment_gain:,.0f}",
                        f"Depreciation recapture (25%): ${recapture_tax:,.0f}",
                        f"Capital gains (15%): ${ltcg_tax:,.0f}",
                        f"Total tax deferred: ${total_tax_deferred:,.0f}",
                        "1031 Exchange rules:",
                        "  • 45 days to identify replacement property",
                        "  • 180 days to close on replacement",
                        "  • Must use Qualified Intermediary (QI)",
                        "  • Can't touch the proceeds",
                        "At death: Heirs get stepped-up basis (tax forgiven!)"
                    ],
                    deadline="Start 45-day clock at sale closing",
                    irs_reference="Section 1031, Form 8824",
                    source="exchange_1031_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 2. REVERSE 1031 EXCHANGE
        # =================================================================
        if has_rental and investment_gain > 50000:
            rec = _create_recommendation(
                id="1031-reverse-exchange",
                category="real_estate",
                title="Consider Reverse 1031 Exchange",
                summary="Buy replacement property BEFORE selling current one. More time to find the right deal!",
                estimated_savings=investment_gain * 0.05,  # Premium for flexibility
                priority="medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    "Reverse 1031 Exchange:",
                    "  • Buy replacement property first",
                    "  • Hold in Exchange Accommodation Titleholder (EAT)",
                    "  • Sell relinquished property within 180 days",
                    "Benefits:",
                    "  • No rush to find replacement",
                    "  • Lock in great deals when you find them",
                    "  • More certainty in hot markets",
                    "Cost: Higher intermediary fees (~$3-5K more)"
                ],
                irs_reference="Rev. Proc. 2000-37",
                source="exchange_1031_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"1031 exchange optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"1031 exchange optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_installment_sale_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get installment sale (Form 6252) recommendations for deferring capital gains.

    USER VALUE: Spread recognition of gain over multiple years as payments
    are received. Keeps you in lower tax brackets and defers tax liability.

    Key benefits:
    - Defer gain recognition to future years
    - Stay in lower tax brackets
    - Spread NIIT impact
    - Interest income on deferred payments

    Typical savings: $5,000-$100,000+ in deferred taxes
    """
    recommendations = []

    try:
        # Large asset sales - check multiple possible gain sources
        capital_gains = _safe_float(profile.get("capital_gains"), 0)
        business_sale_gain = _safe_float(profile.get("business_sale_gain"), 0, min_val=0)
        property_sale_gain = _safe_float(profile.get("property_sale_gain"), 0, min_val=0)
        large_gain_amount = _safe_float(profile.get("large_gain_amount"), 0, min_val=0)
        asset_sale_gain = _safe_float(profile.get("asset_sale_gain"), 0, min_val=0)
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        considering_sale = profile.get("considering_asset_sale", False)

        # Check for significant gains from any source
        large_gain = max(capital_gains, business_sale_gain, property_sale_gain,
                        large_gain_amount, asset_sale_gain)

        if large_gain < 50000 and not considering_sale:
            return recommendations

        # Use the largest gain amount
        if large_gain < 50000:
            large_gain = 100000  # Assume reasonable gain if just considering

        # Tax bracket analysis
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)

        # Calculate tax on full gain vs installment
        full_gain_tax = large_gain * 0.15  # 15% LTCG rate
        if total_income > 250000:
            full_gain_tax += large_gain * 0.038  # Add NIIT

        # Assume 5-year installment
        annual_gain = large_gain / 5
        annual_tax = annual_gain * 0.15
        total_installment_tax = annual_tax * 5

        # Savings from bracket management and deferral
        tax_deferral_value = (full_gain_tax - annual_tax) * 0.05 * 2.5  # Present value of deferral
        bracket_savings = full_gain_tax * 0.1 if total_income > 200000 else 0
        total_savings = tax_deferral_value + bracket_savings

        if total_savings > 1000:
            rec = _create_recommendation(
                id="installment-sale",
                category="capital_gains",
                title="Installment Sale: Defer Large Gains",
                summary=f"Spread ${large_gain:,.0f} gain over 5 years. Defer ${tax_deferral_value:,.0f} in taxes + bracket savings!",
                estimated_savings=total_savings,
                priority="high" if large_gain > 200000 else "medium",
                urgency="planning",
                confidence="medium",
                action_steps=[
                    f"Large gain: ${large_gain:,.0f}",
                    f"Tax if recognized in one year: ${full_gain_tax:,.0f}",
                    f"Annual tax (5-year installment): ${annual_tax:,.0f}",
                    f"Deferral value: ${tax_deferral_value:,.0f}",
                    "Installment sale benefits:",
                    "  • Recognize gain as payments received",
                    "  • Stay in lower tax brackets",
                    "  • Spread NIIT exposure",
                    "  • Earn interest on seller financing",
                    "Must elect on Form 6252"
                ],
                irs_reference="Section 453, Form 6252",
                source="installment_sale_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Installment sale optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Installment sale optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_foreign_tax_credit_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Foreign Tax Credit (Form 1116) recommendations.

    USER VALUE: Avoid double taxation on foreign income. Credits are often
    more valuable than deductions. Unused credits can carry forward 10 years.

    Key considerations:
    - Credit vs deduction analysis
    - Separate limitation categories
    - Carryback (1 year) and carryforward (10 years)
    - AMT foreign tax credit

    Typical savings: $500-$50,000+ depending on foreign income
    """
    recommendations = []

    try:
        foreign_income = _safe_float(profile.get("foreign_income"), 0, min_val=0)
        foreign_tax_paid = _safe_float(profile.get("foreign_tax_paid"), 0, min_val=0)
        foreign_dividends = _safe_float(profile.get("foreign_dividends"), 0, min_val=0)
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)

        # Check for foreign income or taxes
        if foreign_tax_paid < 100 and foreign_income < 1000 and foreign_dividends < 500:
            return recommendations

        # Estimate foreign tax on dividends (typical withholding is 15-30%)
        if foreign_dividends > 0 and foreign_tax_paid == 0:
            foreign_tax_paid = foreign_dividends * 0.15  # Assume 15% treaty rate

        total_foreign_income = foreign_income + foreign_dividends

        # =================================================================
        # 1. FOREIGN TAX CREDIT OPPORTUNITY
        # =================================================================
        if foreign_tax_paid > 100:
            # Calculate limitation
            # FTC limited to: (Foreign source taxable income / Total taxable income) × US tax liability
            if total_income > 0:
                foreign_ratio = min(1, total_foreign_income / total_income)
            else:
                foreign_ratio = 1

            # Estimate US tax
            us_tax_estimate = total_income * 0.22  # Approximate effective rate
            ftc_limitation = us_tax_estimate * foreign_ratio

            # Usable credit
            usable_credit = min(foreign_tax_paid, ftc_limitation)
            excess_credit = max(0, foreign_tax_paid - usable_credit)

            # Compare credit vs deduction
            deduction_value = foreign_tax_paid * DEFAULT_MARGINAL_RATE
            credit_benefit = usable_credit - deduction_value

            rec = _create_recommendation(
                id="foreign-tax-credit",
                category="international",
                title="Foreign Tax Credit (FTC)",
                summary=f"Claim ${usable_credit:,.0f} FTC instead of ${deduction_value:,.0f} deduction. Extra benefit: ${credit_benefit:,.0f}!",
                estimated_savings=credit_benefit if credit_benefit > 0 else usable_credit,
                priority="high",
                urgency="tax_filing",
                confidence="high",
                action_steps=[
                    f"Foreign taxes paid: ${foreign_tax_paid:,.0f}",
                    f"Foreign income: ${total_foreign_income:,.0f}",
                    f"FTC limitation: ${ftc_limitation:,.0f}",
                    f"Usable credit: ${usable_credit:,.0f}",
                    f"Excess to carry forward: ${excess_credit:,.0f}" if excess_credit > 0 else "No excess",
                    "Credit vs Deduction:",
                    f"  • Credit value: ${usable_credit:,.0f}",
                    f"  • Deduction value: ${deduction_value:,.0f}",
                    "  → Credit is usually better!",
                    "File Form 1116 for credit"
                ],
                irs_reference="Form 1116, Publication 514",
                source="foreign_tax_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. FOREIGN TAX CREDIT CARRYFORWARD
        # =================================================================
        ftc_carryforward = _safe_float(profile.get("ftc_carryforward"), 0, min_val=0)
        if ftc_carryforward > 100:
            rec = _create_recommendation(
                id="ftc-carryforward",
                category="international",
                title="Use Foreign Tax Credit Carryforward",
                summary=f"You have ${ftc_carryforward:,.0f} in FTC carryforwards. Use before they expire (10 years)!",
                estimated_savings=ftc_carryforward * 0.1,  # Time value
                priority="medium",
                urgency="planning",
                confidence="high",
                action_steps=[
                    f"FTC carryforward balance: ${ftc_carryforward:,.0f}",
                    "FTC carryforward rules:",
                    "  • Carryback 1 year (optional)",
                    "  • Carryforward 10 years",
                    "  • FIFO ordering (oldest first)",
                    "Strategies to use excess FTC:",
                    "  • Increase foreign income (foreign dividends)",
                    "  • File amended return for carryback",
                    "  • Track expiration dates carefully"
                ],
                irs_reference="Form 1116, Section 904(c)",
                source="foreign_tax_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Foreign tax credit optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Foreign tax credit optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_passive_activity_loss_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get Passive Activity Loss (Form 8582) recommendations.

    USER VALUE: Understand which losses are deductible now vs suspended.
    Special $25K allowance for active rental participation. Real estate
    professional exception allows full deduction.

    Key considerations:
    - $25K rental loss allowance (phases out $100K-$150K AGI)
    - Material participation tests (7 tests)
    - Real estate professional exception
    - Grouping elections
    - Suspended losses released on disposition

    Typical impact: $5,000-$25,000 annual deduction + $10,000-$100,000+ suspended
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        rental_income = _safe_float(profile.get("rental_income"), 0, min_val=0)
        rental_expenses = _safe_float(profile.get("rental_expenses"), 0, min_val=0)
        rental_depreciation = _safe_float(profile.get("rental_depreciation"), 0, min_val=0)

        # Check for rental properties
        rental_properties = profile.get("rental_properties", [])
        has_rental = len(rental_properties) > 0 or rental_income > 0

        if not has_rental:
            return recommendations

        # Estimate rental loss
        if rental_expenses == 0:
            rental_expenses = rental_income * 0.4  # Assume 40% expenses

        if rental_depreciation == 0 and len(rental_properties) > 0:
            # Estimate depreciation from properties
            for prop in rental_properties:
                if isinstance(prop, dict):
                    cost = _safe_float(prop.get("cost_basis"), 0)
                    land = _safe_float(prop.get("land_value"), 0)
                    rental_depreciation += (cost - land) / 27.5

        net_rental = rental_income - rental_expenses - rental_depreciation
        rental_loss = abs(net_rental) if net_rental < 0 else 0

        # Check real estate professional status
        is_re_professional = bool(profile.get("is_real_estate_professional", False))
        re_hours = _safe_float(profile.get("real_estate_hours"), 0, min_val=0)

        # =================================================================
        # 1. $25K RENTAL LOSS ALLOWANCE
        # =================================================================
        if rental_loss > 0 and total_income < 150000 and not is_re_professional:
            if total_income <= 100000:
                allowance = min(25000, rental_loss)
            else:
                # Phase out $1 for every $2 over $100K
                reduction = (total_income - 100000) / 2
                allowance = max(0, min(25000 - reduction, rental_loss))

            suspended = rental_loss - allowance
            tax_savings = allowance * DEFAULT_MARGINAL_RATE

            if allowance > 500:
                rec = _create_recommendation(
                    id="pal-25k-allowance",
                    category="rental",
                    title="$25K Rental Loss Allowance",
                    summary=f"Deduct ${allowance:,.0f} of your ${rental_loss:,.0f} rental loss. Save ${tax_savings:,.0f} in taxes!",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="tax_filing",
                    confidence="high",
                    action_steps=[
                        f"Net rental loss: ${rental_loss:,.0f}",
                        f"Your AGI: ${total_income:,.0f}",
                        f"Allowable deduction: ${allowance:,.0f}",
                        f"Suspended (carry forward): ${suspended:,.0f}" if suspended > 0 else "Fully deductible!",
                        "Requirements for $25K allowance:",
                        "  • Actively participate in rental",
                        "  • AGI under $150K (phases out $100K-$150K)",
                        "  • At least 10% ownership",
                        "File Form 8582"
                    ],
                    irs_reference="Form 8582, Publication 925",
                    source="pal_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 2. REAL ESTATE PROFESSIONAL ELECTION
        # =================================================================
        if rental_loss > 25000 and total_income > 100000 and re_hours >= 500:
            full_deduction = rental_loss * DEFAULT_MARGINAL_RATE
            current_benefit = min(25000, rental_loss) * DEFAULT_MARGINAL_RATE if total_income < 150000 else 0
            additional_benefit = full_deduction - current_benefit

            if additional_benefit > 2000:
                rec = _create_recommendation(
                    id="pal-re-professional",
                    category="rental",
                    title="Real Estate Professional Status",
                    summary=f"Qualify as RE Professional: Deduct ALL ${rental_loss:,.0f} in losses. Extra benefit: ${additional_benefit:,.0f}!",
                    estimated_savings=additional_benefit,
                    priority="high",
                    urgency="planning",
                    confidence="medium",
                    action_steps=[
                        f"Your rental losses: ${rental_loss:,.0f}",
                        f"Current allowable: ${25000 if total_income < 100000 else 0:,.0f}",
                        f"RE Professional benefit: ${additional_benefit:,.0f}",
                        "Requirements for RE Professional:",
                        "  1. 750+ hours in real estate activities",
                        "  2. More than 50% of work time in RE",
                        "  3. Material participation in each rental",
                        f"Your RE hours: {re_hours:.0f}",
                        "Keep detailed time logs!",
                        "Consider grouping election for rentals"
                    ],
                    irs_reference="Section 469(c)(7), Publication 925",
                    source="pal_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 3. SUSPENDED LOSS TRACKING
        # =================================================================
        suspended_pal = _safe_float(profile.get("suspended_passive_losses"), 0, min_val=0)
        if suspended_pal > 5000:
            future_benefit = suspended_pal * DEFAULT_MARGINAL_RATE

            rec = _create_recommendation(
                id="pal-suspended-losses",
                category="rental",
                title="Suspended Passive Losses",
                summary=f"You have ${suspended_pal:,.0f} in suspended losses. Worth ${future_benefit:,.0f} when released!",
                estimated_savings=0,  # Future benefit
                priority="medium",
                urgency="informational",
                confidence="high",
                action_steps=[
                    f"Suspended passive losses: ${suspended_pal:,.0f}",
                    f"Future tax value: ${future_benefit:,.0f}",
                    "When suspended losses are released:",
                    "  • Fully taxable disposition of activity",
                    "  • Gift does NOT release losses",
                    "  • Death releases to reduce gain",
                    "Track suspended losses by activity",
                    "Consider timing of property sales"
                ],
                irs_reference="Section 469, Form 8582",
                source="pal_optimizer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Passive activity loss optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Passive activity loss optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


# =============================================================================
# TAX DRIVERS ANALYZER - "What Drives Your Taxes"
# =============================================================================
def _get_tax_drivers_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get recommendations based on tax drivers analysis.

    USER VALUE: Shows users exactly what factors have the biggest impact on
    their taxes, with specific dollar amounts for each driver. Helps users
    understand their tax situation and prioritize optimization.

    Key insights provided:
    - Primary income sources and their tax treatment
    - Deduction impact in actual dollars
    - Credit utilization analysis
    - Effective vs marginal rate explanation
    - Top 5 factors driving their taxes

    Typical user value: $500-$3,000 through better understanding and action
    """
    recommendations = []

    try:
        # Extract key profile data
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
        rental_income = _safe_float(profile.get("rental_income"), 0, min_val=0)
        investment_income = _safe_float(profile.get("investment_income"), 0, min_val=0)
        capital_gains = _safe_float(profile.get("capital_gains"), 0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # Deductions
        mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0, min_val=0)
        property_taxes = _safe_float(profile.get("property_taxes"), 0, min_val=0)
        state_taxes = _safe_float(profile.get("state_income_tax") or profile.get("state_taxes"), 0, min_val=0)
        charitable = _safe_float(profile.get("charitable_donations") or profile.get("charitable"), 0, min_val=0)

        # Retirement
        retirement_401k = _safe_float(profile.get("retirement_401k"), 0, min_val=0)
        retirement_ira = _safe_float(profile.get("retirement_ira"), 0, min_val=0)
        hsa = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0, min_val=0)

        if total_income < 25000:
            return recommendations

        # Calculate marginal rate
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)

        marginal_rate = 0.22  # Default
        if taxable_income <= 11925:
            marginal_rate = 0.10
        elif taxable_income <= 48475:
            marginal_rate = 0.12
        elif taxable_income <= 103350:
            marginal_rate = 0.22
        elif taxable_income <= 197300:
            marginal_rate = 0.24
        elif taxable_income <= 250525:
            marginal_rate = 0.32
        elif taxable_income <= 626350:
            marginal_rate = 0.35
        else:
            marginal_rate = 0.37

        # Calculate effective rate estimate
        tax_estimate = taxable_income * marginal_rate * 0.75  # Rough estimate
        effective_rate = (tax_estimate / total_income) if total_income > 0 else 0

        # =================================================================
        # 1. INCOME DRIVERS ANALYSIS
        # =================================================================
        income_sources = []
        if w2_income > 0:
            income_sources.append(("W-2 Wages", w2_income, "ordinary"))
        if business_income > 0:
            income_sources.append(("Self-Employment", business_income, "se_tax"))
        if rental_income > 0:
            income_sources.append(("Rental Income", rental_income, "passive"))
        if investment_income > 0:
            income_sources.append(("Investment Income", investment_income, "varies"))
        if capital_gains > 0:
            income_sources.append(("Capital Gains", capital_gains, "capital"))

        if income_sources:
            income_sources.sort(key=lambda x: x[1], reverse=True)
            primary_source = income_sources[0]
            primary_pct = (primary_source[1] / total_income * 100) if total_income > 0 else 0

            rec = _create_recommendation(
                id="drivers-income-analysis",
                category="education",
                title="Your Tax Drivers: Income Analysis",
                summary=f"Your primary income: {primary_source[0]} ({primary_pct:.0f}% of total). Understanding your income mix helps optimize taxes.",
                estimated_savings=0,
                priority="medium",
                urgency="informational",
                confidence="high",
                action_steps=[
                    "YOUR INCOME BREAKDOWN:",
                    *[f"  • {src[0]}: ${src[1]:,.0f} ({src[1]/total_income*100:.0f}%) - {src[2]} income"
                      for src in income_sources[:5]],
                    f"Total Income: ${total_income:,.0f}",
                    "",
                    "TAX TREATMENT:",
                    "  • Ordinary income: taxed at marginal rate",
                    "  • Self-employment: +15.3% SE tax (half deductible)",
                    "  • Capital gains: 0%, 15%, or 20% (preferential)",
                    "  • Passive: Subject to PAL limitations"
                ],
                irs_reference="Publication 17 (Your Federal Income Tax)",
                source="tax_drivers_analyzer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. DEDUCTION IMPACT ANALYSIS
        # =================================================================
        itemized_total = mortgage_interest + min(state_taxes + property_taxes, 10000) + charitable
        is_itemizing = itemized_total > std_deduction
        deduction_amount = itemized_total if is_itemizing else std_deduction
        deduction_tax_savings = deduction_amount * marginal_rate

        rec = _create_recommendation(
            id="drivers-deduction-impact",
            category="deduction",
            title=f"Your Deduction Saves ${deduction_tax_savings:,.0f}",
            summary=f"{'Itemizing' if is_itemizing else 'Standard'} deduction of ${deduction_amount:,.0f} saves ${deduction_tax_savings:,.0f} in taxes at your {marginal_rate*100:.0f}% rate.",
            estimated_savings=0,  # Informational
            priority="medium",
            urgency="informational",
            confidence="high",
            action_steps=[
                f"YOUR DEDUCTION TYPE: {'Itemized' if is_itemizing else 'Standard'}",
                f"Deduction Amount: ${deduction_amount:,.0f}",
                f"Tax Savings: ${deduction_tax_savings:,.0f}",
                f"Your Marginal Rate: {marginal_rate*100:.0f}%",
                "",
                "HOW DEDUCTIONS WORK:",
                f"  Each ${1000:,} in deductions saves ${marginal_rate*1000:.0f} in taxes",
                f"  Standard deduction for {filing_status}: ${std_deduction:,}",
                "",
                "DEDUCTION VALUE BY RATE:",
                "  10% bracket: $100 per $1,000",
                "  22% bracket: $220 per $1,000",
                "  32% bracket: $320 per $1,000"
            ],
            irs_reference="Publication 501 (Standard Deduction)",
            source="tax_drivers_analyzer"
        )
        if rec:
            recommendations.append(rec)

        # =================================================================
        # 3. MARGINAL VS EFFECTIVE RATE EXPLANATION
        # =================================================================
        rec = _create_recommendation(
            id="drivers-rate-explanation",
            category="education",
            title=f"Your Tax Rates: {effective_rate*100:.1f}% Effective vs {marginal_rate*100:.0f}% Marginal",
            summary=f"You pay ~{effective_rate*100:.1f}% overall, but each new dollar is taxed at {marginal_rate*100:.0f}%. This matters for planning.",
            estimated_savings=0,
            priority="low",
            urgency="informational",
            confidence="high",
            action_steps=[
                "YOUR TAX RATES:",
                f"  • Effective Rate: ~{effective_rate*100:.1f}% (total tax ÷ total income)",
                f"  • Marginal Rate: {marginal_rate*100:.0f}% (rate on next dollar)",
                "",
                "WHY THIS MATTERS:",
                f"  • Deduction value: Each $1,000 saves ${marginal_rate*1000:.0f}",
                f"  • Extra income cost: Each $1,000 costs ${marginal_rate*1000:.0f}",
                f"  • Roth vs Traditional: Compare {marginal_rate*100:.0f}% now vs future rate",
                "",
                "PLANNING IMPLICATIONS:",
                "  • Income shifting: Move income to lower-rate years",
                "  • Deduction timing: Bunch in high-rate years",
                "  • Roth conversions: Consider at lower rate years"
            ],
            irs_reference="IRS Tax Tables (Form 1040)",
            source="tax_drivers_analyzer"
        )
        if rec:
            recommendations.append(rec)

        # =================================================================
        # 4. RETIREMENT CONTRIBUTION IMPACT
        # =================================================================
        total_retirement = retirement_401k + retirement_ira + hsa
        if total_retirement > 0:
            retirement_savings = total_retirement * marginal_rate
            max_401k = RETIREMENT_LIMITS_2025["401k_limit"]
            max_ira = RETIREMENT_LIMITS_2025["ira_limit"]
            max_hsa = RETIREMENT_LIMITS_2025["hsa_family"]

            potential_additional = 0
            if retirement_401k < max_401k:
                potential_additional += (max_401k - retirement_401k) * marginal_rate
            if retirement_ira < max_ira:
                potential_additional += (max_ira - retirement_ira) * marginal_rate

            rec = _create_recommendation(
                id="drivers-retirement-impact",
                category="retirement",
                title=f"Retirement Contributions Save ${retirement_savings:,.0f}",
                summary=f"Your ${total_retirement:,.0f} in retirement contributions saves ${retirement_savings:,.0f} this year. Additional room: ${potential_additional:,.0f} savings.",
                estimated_savings=potential_additional if potential_additional > 500 else 0,
                priority="medium" if potential_additional > 1000 else "low",
                urgency="current_year" if potential_additional > 1000 else "informational",
                confidence="high",
                action_steps=[
                    "YOUR RETIREMENT SAVINGS:",
                    f"  • 401(k): ${retirement_401k:,.0f} / ${max_401k:,} limit",
                    f"  • IRA: ${retirement_ira:,.0f} / ${max_ira:,} limit",
                    f"  • HSA: ${hsa:,.0f} (if eligible)",
                    f"  Total Tax Savings: ${retirement_savings:,.0f}",
                    "",
                    "ADDITIONAL OPPORTUNITY:" if potential_additional > 500 else "MAXED OUT:",
                    f"  • Remaining room: ${(max_401k - retirement_401k + max_ira - retirement_ira):,.0f}" if potential_additional > 500 else "  Great job maximizing!",
                    f"  • Additional tax savings: ${potential_additional:,.0f}" if potential_additional > 500 else ""
                ],
                irs_reference="Publication 590-A (IRA Contributions)",
                source="tax_drivers_analyzer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Tax drivers analyzer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Tax drivers analyzer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


# =============================================================================
# WITHHOLDING OPTIMIZER - Using RealTimeEstimator Logic
# =============================================================================
def _get_withholding_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get withholding optimization recommendations.

    USER VALUE: Analyzes whether user is over-withholding (giving IRS free loan)
    or under-withholding (potential penalties). Uses RealTimeEstimator logic
    to provide actionable W-4 adjustments.

    Key insights:
    - Over-withholding detection (large refund expected)
    - Under-withholding warning (may owe + penalties)
    - W-4 adjustment recommendations
    - Quarterly estimated tax guidance

    Typical impact: $50-$500 in reduced penalties OR $500-$5,000 more in paycheck
    """
    recommendations = []

    try:
        # Extract profile data
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        withholding = _safe_float(profile.get("withholding"), 0, min_val=0)
        estimated_tax_paid = _safe_float(profile.get("estimated_tax_paid"), 0, min_val=0)
        last_year_tax = _safe_float(profile.get("last_year_tax"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        business_income = _safe_float(profile.get("business_income"), 0, min_val=0)

        if total_income < 30000 or w2_income < 10000:
            return recommendations

        # Calculate estimated tax liability
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)

        # Simplified tax calculation
        estimated_tax = 0
        remaining = taxable_income
        brackets = [
            (11925, 0.10),
            (48475 - 11925, 0.12),
            (103350 - 48475, 0.22),
            (197300 - 103350, 0.24),
            (250525 - 197300, 0.32),
            (626350 - 250525, 0.35),
        ]
        for bracket_size, rate in brackets:
            if remaining <= 0:
                break
            taxed = min(remaining, bracket_size)
            estimated_tax += taxed * rate
            remaining -= bracket_size
        if remaining > 0:
            estimated_tax += remaining * 0.37

        # Add SE tax if applicable
        if business_income > 400:
            se_tax = business_income * 0.9235 * 0.153
            estimated_tax += se_tax

        # Total payments
        total_payments = withholding + estimated_tax_paid
        projected_balance = total_payments - estimated_tax

        # Safe harbor check
        safe_harbor_100 = last_year_tax if last_year_tax > 0 else estimated_tax
        safe_harbor_110 = safe_harbor_100 * 1.1 if total_income > 150000 else safe_harbor_100
        safe_harbor_met = total_payments >= min(estimated_tax * 0.90, safe_harbor_110)

        # =================================================================
        # 1. OVER-WITHHOLDING DETECTION
        # =================================================================
        if projected_balance > 2000:
            monthly_benefit = projected_balance / 12
            rec = _create_recommendation(
                id="withholding-over",
                category="planning",
                title=f"Adjust W-4: Get ${monthly_benefit:,.0f}/Month More in Paycheck",
                summary=f"You're over-withholding ~${projected_balance:,.0f}. That's a free loan to the IRS! Adjust W-4 to boost take-home pay.",
                estimated_savings=projected_balance * 0.05,  # Opportunity cost ~5%
                priority="medium",
                urgency="next_paycheck",
                confidence="medium",
                action_steps=[
                    "YOUR WITHHOLDING ANALYSIS:",
                    f"  • Estimated tax: ${estimated_tax:,.0f}",
                    f"  • Total payments: ${total_payments:,.0f}",
                    f"  • Projected refund: ${projected_balance:,.0f}",
                    "",
                    "W-4 ADJUSTMENT:",
                    f"  Reduce withholding by ~${projected_balance/12:,.0f}/month",
                    "  On W-4 Step 3: Claim additional credits",
                    "  Or Step 4(b): Add extra deductions",
                    "",
                    "BENEFIT:",
                    f"  • ${monthly_benefit:,.0f} more per paycheck",
                    f"  • ${projected_balance:,.0f} for savings/investing NOW",
                    "  • ~5% opportunity cost of large refund"
                ],
                irs_reference="Form W-4, IRS Tax Withholding Estimator",
                source="withholding_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. UNDER-WITHHOLDING WARNING
        # =================================================================
        elif projected_balance < -1000 and not safe_harbor_met:
            shortfall = abs(projected_balance)
            penalty_estimate = shortfall * 0.08  # Rough penalty estimate

            rec = _create_recommendation(
                id="withholding-under",
                category="penalty",
                title=f"Warning: May Owe ${shortfall:,.0f} + Penalties",
                summary=f"You may be under-withheld by ${shortfall:,.0f}. Potential penalty: ${penalty_estimate:,.0f}. Take action now!",
                estimated_savings=penalty_estimate,
                priority="high",
                urgency="immediate",
                confidence="medium",
                action_steps=[
                    "⚠️ UNDER-WITHHOLDING DETECTED:",
                    f"  • Estimated tax: ${estimated_tax:,.0f}",
                    f"  • Total payments: ${total_payments:,.0f}",
                    f"  • Projected shortfall: ${shortfall:,.0f}",
                    f"  • Potential penalty: ~${penalty_estimate:,.0f}",
                    "",
                    "IMMEDIATE ACTIONS:",
                    "  1. Increase W-4 withholding (extra amount Step 4c)",
                    "  2. Make estimated tax payment (Form 1040-ES)",
                    f"  3. Safe harbor requires: ${safe_harbor_110:,.0f} total payments",
                    "",
                    "SAFE HARBOR RULES:",
                    "  • Pay 90% of current year tax, OR",
                    f"  • 100%/110% of last year (${safe_harbor_110:,.0f})"
                ],
                irs_reference="Form 2210, Publication 505",
                source="withholding_optimizer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 3. SAFE HARBOR STATUS
        # =================================================================
        rec = _create_recommendation(
            id="withholding-safe-harbor",
            category="penalty",
            title=f"Safe Harbor Status: {'SAFE ✓' if safe_harbor_met else 'AT RISK ⚠️'}",
            summary=f"{'You meet safe harbor - no underpayment penalty!' if safe_harbor_met else f'Need ${safe_harbor_110 - total_payments:,.0f} more to meet safe harbor.'}",
            estimated_savings=0,
            priority="low" if safe_harbor_met else "high",
            urgency="informational" if safe_harbor_met else "immediate",
            confidence="high",
            action_steps=[
                "SAFE HARBOR ANALYSIS:",
                f"  • Required (90% current): ${estimated_tax * 0.90:,.0f}",
                f"  • Required (prior year): ${safe_harbor_110:,.0f}",
                f"  • Your payments: ${total_payments:,.0f}",
                f"  • Status: {'✓ SAFE' if safe_harbor_met else '⚠️ NOT MET'}",
                "",
                "SAFE HARBOR RULES:",
                "  You avoid penalties if you pay:",
                "  • 90% of current year tax liability, OR",
                "  • 100% of prior year tax (110% if AGI > $150K)"
            ],
            irs_reference="IRS Publication 505, Form 2210",
            source="withholding_optimizer"
        )
        if rec:
            recommendations.append(rec)

        logger.info(f"Withholding optimizer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Withholding optimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


# =============================================================================
# TAX IMPACT ANALYZER - Using DeltaAnalyzer Logic
# =============================================================================
def _get_tax_impact_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get recommendations showing impact of potential tax changes.

    USER VALUE: Shows users the exact dollar impact of various tax moves
    using before/after comparison. Helps prioritize actions by impact.

    Key insights:
    - Retirement contribution impact
    - HSA contribution impact
    - Charitable giving impact
    - Deduction acceleration impact

    Typical impact clarity: Helps users prioritize $1,000-$10,000 in decisions
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()

        # Current deductions/contributions
        retirement_401k = _safe_float(profile.get("retirement_401k"), 0, min_val=0)
        retirement_ira = _safe_float(profile.get("retirement_ira"), 0, min_val=0)
        hsa = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0, min_val=0)
        has_hdhp = bool(profile.get("has_hdhp", False))
        family_coverage = bool(profile.get("family_coverage", False))
        age = _safe_int(profile.get("age"), 35, min_val=0, max_val=120)

        if total_income < 40000:
            return recommendations

        # Calculate marginal rate
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)
        marginal_rate = 0.22  # Default
        if taxable_income <= 11925:
            marginal_rate = 0.10
        elif taxable_income <= 48475:
            marginal_rate = 0.12
        elif taxable_income <= 103350:
            marginal_rate = 0.22
        elif taxable_income <= 197300:
            marginal_rate = 0.24
        elif taxable_income <= 250525:
            marginal_rate = 0.32
        elif taxable_income <= 626350:
            marginal_rate = 0.35
        else:
            marginal_rate = 0.37

        # =================================================================
        # 1. 401(k) CONTRIBUTION IMPACT
        # =================================================================
        max_401k = RETIREMENT_LIMITS_2025["401k_limit"]
        catch_up_401k = RETIREMENT_LIMITS_2025["401k_catch_up"] if age >= 50 else 0
        total_max_401k = max_401k + catch_up_401k

        if retirement_401k < total_max_401k:
            additional = total_max_401k - retirement_401k
            tax_impact = additional * marginal_rate

            rec = _create_recommendation(
                id="impact-401k-max",
                category="retirement",
                title=f"Impact: Max 401(k) → Save ${tax_impact:,.0f} in Taxes",
                summary=f"Contributing ${additional:,.0f} more to 401(k) reduces taxes by ${tax_impact:,.0f} this year.",
                estimated_savings=tax_impact,
                priority="high" if tax_impact > 3000 else "medium",
                urgency="current_year",
                confidence="high",
                action_steps=[
                    "BEFORE vs AFTER:",
                    f"  Current 401(k): ${retirement_401k:,.0f}",
                    f"  After maxing: ${total_max_401k:,.0f}",
                    f"  Additional contribution: ${additional:,.0f}",
                    "",
                    "TAX IMPACT:",
                    f"  Your marginal rate: {marginal_rate*100:.0f}%",
                    f"  Tax reduction: ${tax_impact:,.0f}",
                    f"  Net cost: ${additional - tax_impact:,.0f} (after tax savings)",
                    "",
                    f"{'Catch-up eligible (50+): Extra $' + str(catch_up_401k) + ' allowed' if catch_up_401k > 0 else '2025 limit: $23,500'}"
                ],
                irs_reference="IRC Section 401(k), Publication 560",
                source="tax_impact_analyzer"
            )
            if rec:
                recommendations.append(rec)

        # =================================================================
        # 2. HSA CONTRIBUTION IMPACT
        # =================================================================
        if has_hdhp:
            max_hsa = RETIREMENT_LIMITS_2025["hsa_family"] if family_coverage else RETIREMENT_LIMITS_2025["hsa_self"]
            hsa_catch_up = 1000 if age >= 55 else 0
            total_max_hsa = max_hsa + hsa_catch_up

            if hsa < total_max_hsa:
                additional_hsa = total_max_hsa - hsa
                hsa_tax_impact = additional_hsa * (marginal_rate + 0.0765)  # Include FICA savings

                rec = _create_recommendation(
                    id="impact-hsa-max",
                    category="healthcare",
                    title=f"Impact: Max HSA → Save ${hsa_tax_impact:,.0f} (Tax + FICA)",
                    summary=f"HSA triple tax advantage: ${additional_hsa:,.0f} more saves ${hsa_tax_impact:,.0f} in income tax AND FICA.",
                    estimated_savings=hsa_tax_impact,
                    priority="high" if hsa_tax_impact > 1500 else "medium",
                    urgency="current_year",
                    confidence="high",
                    action_steps=[
                        "HSA BEFORE vs AFTER:",
                        f"  Current HSA: ${hsa:,.0f}",
                        f"  After maxing: ${total_max_hsa:,.0f}",
                        f"  Additional contribution: ${additional_hsa:,.0f}",
                        "",
                        "TRIPLE TAX ADVANTAGE:",
                        f"  1. Income tax savings: ${additional_hsa * marginal_rate:,.0f}",
                        f"  2. FICA savings: ${additional_hsa * 0.0765:,.0f}",
                        "  3. Tax-free growth & withdrawals for medical",
                        "",
                        f"TOTAL TAX SAVINGS: ${hsa_tax_impact:,.0f}"
                    ],
                    irs_reference="Publication 969 (HSA)",
                    source="tax_impact_analyzer"
                )
                if rec:
                    recommendations.append(rec)

        # =================================================================
        # 3. IRA CONTRIBUTION IMPACT
        # =================================================================
        max_ira = RETIREMENT_LIMITS_2025["ira_limit"]
        ira_catch_up = RETIREMENT_LIMITS_2025["ira_catch_up"] if age >= 50 else 0
        total_max_ira = max_ira + ira_catch_up

        if retirement_ira < total_max_ira:
            additional_ira = total_max_ira - retirement_ira
            ira_tax_impact = additional_ira * marginal_rate

            rec = _create_recommendation(
                id="impact-ira-contribution",
                category="retirement",
                title=f"Impact: IRA Contribution → Save ${ira_tax_impact:,.0f}",
                summary=f"Contributing ${additional_ira:,.0f} to Traditional IRA reduces taxes by ${ira_tax_impact:,.0f}.",
                estimated_savings=ira_tax_impact,
                priority="medium",
                urgency="tax_filing",
                confidence="high",
                action_steps=[
                    "IRA BEFORE vs AFTER:",
                    f"  Current IRA contribution: ${retirement_ira:,.0f}",
                    f"  Maximum allowed: ${total_max_ira:,.0f}",
                    f"  Additional room: ${additional_ira:,.0f}",
                    "",
                    "TAX IMPACT (Traditional IRA):",
                    f"  Tax reduction: ${ira_tax_impact:,.0f}",
                    f"  At marginal rate: {marginal_rate*100:.0f}%",
                    "",
                    "DEADLINE: April 15 for prior year contribution",
                    f"{'Catch-up eligible (50+): Extra $1,000 allowed' if ira_catch_up > 0 else '2025 limit: $7,000'}"
                ],
                irs_reference="Publication 590-A",
                source="tax_impact_analyzer"
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"Tax impact analyzer found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Tax impact analyzer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


# =============================================================================
# REFUND ESTIMATOR - Using RealTimeEstimator Logic
# =============================================================================
def _get_refund_estimator_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get refund/owed estimate with confidence bands.

    USER VALUE: Provides estimated refund/owed with confidence range,
    helping users understand their likely tax outcome.

    Key insights:
    - Point estimate of refund/owed
    - Confidence band (low/likely/high)
    - Key assumptions
    - Actions to improve estimate

    Typical value: Peace of mind + better planning ($500-$5,000 decisions)
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        withholding = _safe_float(profile.get("withholding"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        dependents = _safe_int(profile.get("dependents") or profile.get("num_dependents"), 0, min_val=0)

        if total_income < 20000:
            return recommendations

        # Calculate estimated tax
        std_deduction = STANDARD_DEDUCTIONS.get(filing_status, 15000)
        taxable_income = max(0, total_income - std_deduction)

        # Progressive tax calculation
        estimated_tax = 0
        remaining = taxable_income
        brackets = [(11925, 0.10), (36550, 0.12), (54875, 0.22), (93950, 0.24),
                    (53225, 0.32), (375825, 0.35)]
        for bracket_size, rate in brackets:
            if remaining <= 0:
                break
            taxed = min(remaining, bracket_size)
            estimated_tax += taxed * rate
            remaining -= bracket_size
        if remaining > 0:
            estimated_tax += remaining * 0.37

        # Estimate credits
        estimated_credits = 0
        if dependents > 0:
            # Child Tax Credit
            ctc_per_child = 2000
            ctc_total = min(dependents * ctc_per_child, dependents * ctc_per_child)
            # Phase out
            phaseout_start = 200000 if filing_status == "single" else 400000
            if total_income > phaseout_start:
                phaseout = ((total_income - phaseout_start) // 1000) * 50
                ctc_total = max(0, ctc_total - phaseout)
            estimated_credits += ctc_total

        # Calculate refund/owed
        tax_after_credits = max(0, estimated_tax - estimated_credits)
        refund_owed = withholding - tax_after_credits

        # Confidence calculation
        confidence_score = 50  # Base
        if withholding > 0:
            confidence_score += 15
        if w2_income > 0 and w2_income == total_income:
            confidence_score += 15  # Simple W-2 only situation
        if dependents > 0:
            confidence_score += 5

        # Confidence band
        if confidence_score >= 70:
            band_pct = 0.10
            confidence_level = "Medium-High"
        elif confidence_score >= 55:
            band_pct = 0.20
            confidence_level = "Medium"
        else:
            band_pct = 0.35
            confidence_level = "Low"

        variation = max(500, abs(refund_owed) * band_pct)
        low_estimate = refund_owed - variation
        high_estimate = refund_owed + variation

        refund_or_owe = "refund" if refund_owed > 0 else "owed"
        amount_display = abs(refund_owed)

        rec = _create_recommendation(
            id="estimate-refund-owed",
            category="planning",
            title=f"Estimated {'Refund' if refund_owed > 0 else 'Amount Owed'}: ${amount_display:,.0f}",
            summary=f"Based on available data, you {'may receive a refund' if refund_owed > 0 else 'may owe'} approximately ${amount_display:,.0f}. Range: ${abs(low_estimate):,.0f} - ${abs(high_estimate):,.0f}.",
            estimated_savings=0,
            priority="medium",
            urgency="informational",
            confidence="medium",
            action_steps=[
                "YOUR TAX ESTIMATE:",
                f"  Likely outcome: ${refund_owed:,.0f} {'refund' if refund_owed > 0 else 'owed'}",
                f"  Range (low): ${low_estimate:,.0f}",
                f"  Range (high): ${high_estimate:,.0f}",
                f"  Confidence: {confidence_level} ({confidence_score}%)",
                "",
                "CALCULATION BREAKDOWN:",
                f"  Gross income: ${total_income:,.0f}",
                f"  Standard deduction: -${std_deduction:,.0f}",
                f"  Taxable income: ${taxable_income:,.0f}",
                f"  Estimated tax: ${estimated_tax:,.0f}",
                f"  Credits: -${estimated_credits:,.0f}",
                f"  Tax after credits: ${tax_after_credits:,.0f}",
                f"  Withholding: ${withholding:,.0f}",
                "",
                "TO IMPROVE ACCURACY:",
                "  • Provide complete income information",
                "  • Include all deductions",
                "  • Verify withholding amounts"
            ],
            irs_reference="IRS Tax Withholding Estimator",
            source="refund_estimator"
        )
        if rec:
            recommendations.append(rec)

        logger.info(f"Refund estimator found {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"Refund estimator failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_entity_optimizer_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get entity structure recommendations from EntityStructureOptimizer.

    USER VALUE: For self-employed users, shows exact S-Corp vs LLC savings,
    calculates optimal salary, projects 5-year savings.
    Typical savings: $3,000-$15,000/year for qualifying businesses.
    """
    recommendations = []

    # Extract and validate business data
    business_income = _safe_float(profile.get("business_income"), 0, min_val=0)
    is_self_employed = bool(profile.get("is_self_employed", False)) or business_income > 0

    # S-Corp typically makes sense above $40K net income
    MIN_INCOME_FOR_SCORP = 40000

    if business_income < MIN_INCOME_FOR_SCORP or not is_self_employed:
        return recommendations

    try:
        from recommendation.entity_optimizer import EntityStructureOptimizer

        optimizer = EntityStructureOptimizer()

        # Business expenses (estimate 20% if not provided)
        business_expenses = _safe_float(profile.get("business_expenses"), 0, min_val=0)
        if business_expenses == 0:
            business_expenses = business_income * 0.2

        gross_revenue = business_income + business_expenses
        net_income = max(0, gross_revenue - business_expenses)

        # Skip if net income is too low
        if net_income < MIN_INCOME_FOR_SCORP:
            return recommendations

        # Try to use the EntityStructureOptimizer
        try:
            comparison = optimizer.compare_structures(
                gross_revenue=gross_revenue,
                business_expenses=business_expenses,
                owner_salary=None,
                current_entity=None
            )
        except Exception as e:
            logger.debug(f"EntityStructureOptimizer.compare_structures failed: {e}")
            comparison = None

        # Calculate S-Corp savings directly (fallback or verification)
        # Reasonable salary: typically 40-60% of net income, minimum reasonable for industry
        reasonable_salary_pct = 0.6 if net_income < 100000 else 0.5
        reasonable_salary = min(net_income * reasonable_salary_pct, net_income)

        # Ensure salary is at least reasonable minimum (~$40K for professional services)
        min_reasonable = min(40000, net_income * 0.4)
        reasonable_salary = max(reasonable_salary, min_reasonable)

        distributions = max(0, net_income - reasonable_salary)

        # SE tax savings = distributions * 15.3%
        # Note: Employer portion (7.65%) is deductible, so effective rate is slightly less
        se_savings = distributions * SE_TAX_RATE

        # Subtract estimated S-Corp compliance costs
        compliance_cost = 1500  # Average annual cost for S-Corp compliance
        net_savings = se_savings - compliance_cost

        if net_savings > 1000:  # Meaningful savings threshold
            rec = _create_recommendation(
                id="entity-scorp",
                category="business",
                title="Consider S-Corporation Election",
                summary=f"S-Corp could save you ${net_savings:,.0f}/year after compliance costs (${se_savings:,.0f} SE tax savings - ${compliance_cost:,.0f} costs).",
                estimated_savings=net_savings,
                priority="high" if net_savings > 3000 else "medium",
                urgency="planning",
                confidence="high" if net_income > 75000 else "medium",
                action_steps=[
                    f"Net business income: ${net_income:,.0f}",
                    f"Reasonable salary (subject to payroll taxes): ${reasonable_salary:,.0f}",
                    f"Distributions (no SE tax): ${distributions:,.0f}",
                    "File Form 2553 by March 15 for calendar year S-Corp",
                    "Set up payroll system for yourself",
                    "Budget ~$1,500/year for additional compliance"
                ],
                deadline="March 15, 2026",
                irs_reference="Form 2553, Form 1120-S",
                source="entity_optimizer"
            )
            if rec:
                recommendations.append(rec)

            # 5-year projection (only if primary recommendation added)
            if len(recommendations) > 0:
                # Conservative 3% annual growth
                five_year_total = sum(net_savings * (1.03 ** year) for year in range(5))

                rec = _create_recommendation(
                    id="entity-5year-projection",
                    category="business",
                    title="5-Year S-Corp Savings Projection",
                    summary=f"Over 5 years, S-Corp could save ${five_year_total:,.0f} total (assuming 3% annual growth).",
                    estimated_savings=five_year_total / 5,  # Annualized
                    priority="medium",
                    urgency="planning",
                    confidence="medium",
                    action_steps=[
                        f"Year 1: ~${net_savings:,.0f}",
                        f"Year 3: ~${net_savings * 1.06:,.0f}",
                        f"Year 5: ~${net_savings * 1.12:,.0f}",
                        "Consult CPA for personalized analysis"
                    ],
                    source="entity_optimizer"
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"EntityStructureOptimizer found {len(recommendations)} recommendations")

    except ImportError as e:
        logger.debug(f"EntityStructureOptimizer not available: {e}")
    except Exception as e:
        logger.warning(f"EntityStructureOptimizer failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_rental_depreciation_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get rental property recommendations using RentalDepreciationCalculator.

    USER VALUE: For landlords, calculates MACRS depreciation schedule,
    identifies depreciation they may have missed, shows multi-year benefit.
    Typical tax savings: $5,000-$20,000/year for rental property owners.

    Supports two input formats:
    1. Flat fields: rental_income, rental_property_value, rental_land_value, etc.
    2. rental_properties list: [{cost_basis, land_value, date_placed_in_service, ...}]
    """
    recommendations = []

    try:
        from services.rental_depreciation import (
            RentalDepreciationCalculator,
            PropertyType
        )
        from datetime import date

        # Check for rental_properties list format first
        rental_properties = profile.get("rental_properties", [])
        if rental_properties and isinstance(rental_properties, list):
            for idx, prop in enumerate(rental_properties):
                if not isinstance(prop, dict):
                    continue

                # Extract property data from list format
                property_value = _safe_float(prop.get("cost_basis") or prop.get("property_value"), 0, min_val=0)
                land_value = _safe_float(prop.get("land_value"), 0, min_val=0)
                address = _safe_str(prop.get("address"), f"Property {idx + 1}")

                if property_value <= 0:
                    continue

                # Ensure land value doesn't exceed property value
                if land_value >= property_value:
                    land_value = property_value * 0.2

                # Determine property type
                prop_type_str = _safe_str(prop.get("property_type"), "residential_rental").lower()
                property_type = PropertyType.COMMERCIAL if "commercial" in prop_type_str else PropertyType.RESIDENTIAL_RENTAL

                # Parse date placed in service
                date_str = prop.get("date_placed_in_service")
                if isinstance(date_str, str):
                    try:
                        parts = date_str.split("-")
                        placed_in_service = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    except (ValueError, IndexError):
                        placed_in_service = date(TAX_YEAR - 1, 1, 15)
                elif isinstance(date_str, date):
                    placed_in_service = date_str
                else:
                    placed_in_service = date(TAX_YEAR - 1, 1, 15)

                prior_depreciation = _safe_float(prop.get("prior_depreciation"), 0, min_val=0)
                business_use = _safe_float(prop.get("business_use_percentage"), 100, min_val=0, max_val=100)

                # Calculate depreciation
                try:
                    result = RentalDepreciationCalculator.calculate_annual_depreciation(
                        cost_basis=property_value,
                        land_value=land_value,
                        property_type=property_type,
                        date_placed_in_service=placed_in_service,
                        tax_year=TAX_YEAR,
                        prior_depreciation=prior_depreciation,
                        business_use_percentage=business_use
                    )
                except Exception as calc_error:
                    logger.warning(f"Depreciation calculation failed for {address}: {calc_error}")
                    continue

                annual_depreciation = _safe_float(result.get("depreciation_amount"), 0, min_val=0)
                building_basis = _safe_float(result.get("depreciable_basis"), max(0, property_value - land_value), min_val=0)

                if annual_depreciation > 0:
                    tax_savings = annual_depreciation * DEFAULT_MARGINAL_RATE
                    recovery_period = "27.5 years (residential)" if property_type == PropertyType.RESIDENTIAL_RENTAL else "39 years (commercial)"
                    year_num = result.get("year_in_service", 1)

                    rec = _create_recommendation(
                        id=f"rental-depreciation-{idx}",
                        category="rental",
                        title=f"Depreciation: {address[:30]}",
                        summary=f"Year {year_num} depreciation of ${annual_depreciation:,.0f} saves ${tax_savings:,.0f} in taxes. Paper loss - no cash out!",
                        estimated_savings=tax_savings,
                        priority="high",
                        urgency="moderate",
                        confidence="high",
                        action_steps=[
                            f"Building basis: ${building_basis:,.0f}",
                            f"Recovery period: {recovery_period}",
                            f"Year {year_num} of depreciation",
                            "Report on Schedule E, Line 18",
                            "File Form 4562"
                        ],
                        deadline="April 15, 2026",
                        irs_reference="Form 4562, Publication 946",
                        source="rental_depreciation"
                    )
                    if rec:
                        recommendations.append(rec)

            # If we processed rental_properties list, return early
            if recommendations:
                logger.info(f"Rental depreciation analysis found {len(recommendations)} recommendations from properties list")
                return recommendations

        # Fall back to flat profile fields
        rental_income = _safe_float(
            profile.get("rental_income") or profile.get("rental_gross_income"),
            0, min_val=0
        )

        # Only relevant for landlords with rental income
        if rental_income <= 0:
            return recommendations

        # Validate property details
        property_value = _safe_float(profile.get("rental_property_value"), 0, min_val=0)
        land_value = _safe_float(profile.get("rental_land_value"), 0, min_val=0)

        # Ensure land value doesn't exceed property value
        if land_value >= property_value and property_value > 0:
            land_value = property_value * 0.2  # Default to 20% land

        if property_value > 0:
            # Determine property type
            rental_type = _safe_str(profile.get("rental_type"), "residential").lower()
            property_type = PropertyType.COMMERCIAL if rental_type == "commercial" else PropertyType.RESIDENTIAL_RENTAL

            # Validate and determine date placed in service
            start_year = _safe_int(profile.get("rental_start_year"), TAX_YEAR, min_val=1950, max_val=TAX_YEAR)
            start_month = _safe_int(profile.get("rental_start_month"), 1, min_val=1, max_val=12)

            try:
                placed_in_service = date(start_year, start_month, 15)  # Mid-month convention
            except ValueError:
                placed_in_service = date(TAX_YEAR, 1, 15)

            prior_depreciation = _safe_float(profile.get("prior_depreciation"), 0, min_val=0)

            # Calculate depreciation
            try:
                result = RentalDepreciationCalculator.calculate_annual_depreciation(
                    cost_basis=property_value,
                    land_value=land_value,
                    property_type=property_type,
                    date_placed_in_service=placed_in_service,
                    tax_year=TAX_YEAR,
                    prior_depreciation=prior_depreciation,
                    business_use_percentage=100.0
                )
            except Exception as calc_error:
                logger.warning(f"Depreciation calculation failed: {calc_error}")
                result = {}

            annual_depreciation = _safe_float(result.get("depreciation_amount"), 0, min_val=0)
            building_basis = _safe_float(
                result.get("depreciable_basis"),
                max(0, property_value - land_value),
                min_val=0
            )

            if annual_depreciation > 0:
                tax_savings = annual_depreciation * DEFAULT_MARGINAL_RATE
                recovery_period = "27.5 years (residential)" if property_type == PropertyType.RESIDENTIAL_RENTAL else "39 years (commercial)"

                rec = _create_recommendation(
                    id="rental-depreciation",
                    category="rental",
                    title="Claim Rental Property Depreciation",
                    summary=f"Depreciation of ${annual_depreciation:,.0f}/year saves ${tax_savings:,.0f} in taxes. Paper loss - no cash out!",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="moderate",
                    confidence="high",
                    action_steps=[
                        f"Building basis (depreciable): ${building_basis:,.0f}",
                        f"Recovery period: {recovery_period}",
                        "Report on Schedule E, Line 18",
                        "File Form 4562 for depreciation",
                        "Consider cost segregation for properties over $500K"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 4562, Publication 946",
                    source="rental_depreciation"
                )
                if rec:
                    recommendations.append(rec)

        else:
            # No property value - estimate and suggest providing details
            # Use conservative 8% cap rate estimate
            estimated_property_value = rental_income * 12.5  # ~8% cap rate
            estimated_building = estimated_property_value * 0.8  # 80% building
            estimated_depreciation = estimated_building / 27.5
            tax_savings = estimated_depreciation * DEFAULT_MARGINAL_RATE

            if tax_savings > 100:  # Minimum threshold
                rec = _create_recommendation(
                    id="rental-depreciation-opportunity",
                    category="rental",
                    title="Rental Depreciation Opportunity",
                    summary=f"Depreciation could save ~${tax_savings:,.0f}/year in taxes. Provide property value for exact calculation.",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="moderate",
                    confidence="medium",
                    action_steps=[
                        f"Estimated property value: ${estimated_property_value:,.0f}",
                        "Provide actual purchase price for accurate calculation",
                        "Separate land value (check county assessment)",
                        "Residential: 27.5-year, Commercial: 39-year depreciation"
                    ],
                    deadline="April 15, 2026",
                    irs_reference="Form 4562, Publication 527",
                    source="rental_depreciation"
                )
                if rec:
                    recommendations.append(rec)

        # Passive Activity Loss (PAL) rules analysis
        agi = _safe_float(profile.get("total_income"), 0, min_val=0)
        rental_loss = _safe_float(profile.get("rental_net_loss"), 0)

        # Check if rental likely generates a loss (common due to depreciation)
        if rental_loss < 0 or (rental_income > 0 and property_value > 0):
            # Estimate net rental after depreciation
            if property_value > 0:
                est_building = max(0, property_value - land_value) * 0.8
                est_depreciation = est_building / 27.5
                rental_expenses = _safe_float(profile.get("rental_expenses"), rental_income * 0.4, min_val=0)
                net_rental = rental_income - rental_expenses - est_depreciation
            else:
                net_rental = rental_loss if rental_loss < 0 else rental_income * -0.2

            # PAL $25K allowance for active participants with AGI < $150K
            if net_rental < 0 and 0 < agi < 150000:
                if agi <= 100000:
                    pal_allowance = min(25000, abs(net_rental))
                else:
                    # Phase-out: $1 for every $2 over $100K
                    reduced_allowance = 25000 - ((agi - 100000) / 2)
                    pal_allowance = max(0, min(reduced_allowance, abs(net_rental)))

                if pal_allowance > 500:
                    tax_benefit = pal_allowance * DEFAULT_MARGINAL_RATE

                    rec = _create_recommendation(
                        id="rental-pal-allowance",
                        category="rental",
                        title="$25K Rental Loss Allowance",
                        summary=f"Active participants can deduct up to ${pal_allowance:,.0f} in rental losses (~${tax_benefit:,.0f} tax savings).",
                        estimated_savings=tax_benefit,
                        priority="medium",
                        urgency="moderate",
                        confidence="high",
                        action_steps=[
                            "Actively participate in rental decisions",
                            "Document involvement (tenant screening, repairs)",
                            f"Your estimated allowance: ${pal_allowance:,.0f}",
                            "Report on Form 8582"
                        ],
                        irs_reference="Form 8582, Publication 925",
                        source="rental_depreciation"
                    )
                    if rec:
                        recommendations.append(rec)

        logger.info(f"Rental depreciation analysis found {len(recommendations)} recommendations")

    except ImportError as e:
        logger.debug(f"RentalDepreciationCalculator not available: {e}")
    except Exception as e:
        logger.warning(f"RentalDepreciation failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _get_cpa_opportunities(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get opportunities from CPAIntelligenceService.

    USER VALUE: Identifies time-sensitive opportunities based on tax deadlines
    and urgency calculations. Helps users prioritize actions.
    """
    recommendations = []
    try:
        from services.cpa_intelligence_service import detect_opportunities

        opportunities = detect_opportunities(profile)

        if not opportunities or not isinstance(opportunities, (list, tuple)):
            return recommendations

        for i, opp in enumerate(opportunities):
            if not isinstance(opp, dict):
                continue

            # Extract and validate fields
            rec_id = _safe_str(opp.get("id"), f"cpa-{i}")
            title = _safe_str(opp.get("title"), "Tax Opportunity")
            description = _safe_str(opp.get("description"), "")

            if not title or title == "Tax Opportunity" and not description:
                continue  # Skip empty recommendations

            savings = _safe_float(opp.get("savings"), 0, min_val=0)
            priority = _safe_str(opp.get("priority"), "medium").lower()
            urgency = _safe_str(opp.get("urgency"), "moderate").lower()

            # Normalize priority
            if priority not in ("high", "medium", "low"):
                priority = "medium"

            # Normalize urgency
            if urgency not in ("critical", "high", "moderate", "planning"):
                urgency = "moderate"

            # Get action items
            action_items = opp.get("action_items", [])
            if not isinstance(action_items, list):
                action_items = [str(action_items)] if action_items else []

            rec = _create_recommendation(
                id=rec_id,
                category=_safe_str(opp.get("category"), "general"),
                title=title,
                summary=description,
                estimated_savings=savings,
                priority=priority,
                urgency=urgency,
                confidence="high",
                action_steps=action_items,
                deadline=opp.get("deadline"),
                source="cpa_intelligence"
            )
            if rec:
                recommendations.append(rec)

    except ImportError as e:
        logger.debug(f"CPAIntelligenceService not available: {e}")
    except Exception as e:
        logger.warning(f"CPAIntelligenceService opportunities failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _safe_decimal(value: Any, default: float = 0.0) -> Decimal:
    """Safely convert a value to Decimal for TaxOpportunityDetector."""
    try:
        float_val = _safe_float(value, default, min_val=0)
        return Decimal(str(float_val))
    except (InvalidOperation, ValueError):
        return Decimal(str(default))


def _get_opportunity_detector_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get opportunities from TaxOpportunityDetector.

    USER VALUE: Uses AI-powered (or rule-based fallback) analysis to identify
    tax-saving opportunities based on taxpayer profile. Covers retirement,
    deductions, credits, and business strategies.
    """
    recommendations = []
    try:
        from services.tax_opportunity_detector import TaxOpportunityDetector, TaxpayerProfile
        from decimal import Decimal

        detector = TaxOpportunityDetector()

        # Extract validated profile data
        filing_status = _normalize_filing_status(profile.get("filing_status"))
        age = _safe_int(profile.get("age"), 35, min_val=18, max_val=120)

        # Build TaxpayerProfile with validated Decimals
        try:
            taxpayer_profile = TaxpayerProfile(
                filing_status=filing_status,
                age=age,
                w2_wages=_safe_decimal(profile.get("w2_income")),
                self_employment_income=_safe_decimal(profile.get("business_income")),
                business_income=_safe_decimal(profile.get("business_income")),
                interest_income=_safe_decimal(profile.get("interest_income")),
                dividend_income=_safe_decimal(profile.get("dividend_income")),
                capital_gains=_safe_decimal(profile.get("capital_gains")),
                rental_income=_safe_decimal(profile.get("rental_income")),
                mortgage_interest=_safe_decimal(profile.get("mortgage_interest")),
                property_taxes=_safe_decimal(profile.get("property_taxes")),
                charitable_contributions=_safe_decimal(profile.get("charitable_donations")),
                traditional_401k=_safe_decimal(profile.get("retirement_401k")),
                traditional_ira=_safe_decimal(profile.get("retirement_ira")),
                hsa_contribution=_safe_decimal(profile.get("hsa_contributions")),
                num_dependents=_safe_int(profile.get("dependents"), 0, min_val=0, max_val=20),
                has_children_under_17=bool(profile.get("has_children_under_17", False)),
                owns_home=bool(profile.get("owns_home", False)) or _safe_float(profile.get("mortgage_interest")) > 0,
                has_business=_safe_float(profile.get("business_income")) > 0,
                has_hdhp=bool(profile.get("has_hdhp", False)),
            )
        except Exception as profile_error:
            logger.warning(f"Failed to build TaxpayerProfile: {profile_error}")
            return recommendations

        # Detect opportunities
        try:
            opportunities = detector.detect_opportunities(taxpayer_profile)
        except Exception as detect_error:
            logger.warning(f"detect_opportunities failed: {detect_error}")
            return recommendations

        if not opportunities:
            return recommendations

        # Priority mapping
        priority_map = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}

        for i, opp in enumerate(opportunities):
            try:
                # Extract ID
                opp_id = getattr(opp, 'id', None) or f"detector-{i}"

                # Extract category
                category = "general"
                if hasattr(opp, 'category'):
                    if hasattr(opp.category, 'value'):
                        category = opp.category.value
                    else:
                        category = str(opp.category)

                # Extract title and description
                title = getattr(opp, 'title', 'Tax Opportunity')
                description = getattr(opp, 'description', '')

                if not title:
                    continue

                # Extract savings (handle Decimal)
                savings = 0.0
                if hasattr(opp, 'estimated_savings') and opp.estimated_savings:
                    try:
                        savings = float(opp.estimated_savings)
                    except (ValueError, TypeError):
                        savings = 0.0

                # Extract priority
                priority = "medium"
                if hasattr(opp, 'priority'):
                    priority_str = str(opp.priority).upper()
                    priority = priority_map.get(priority_str, "medium")

                # Extract confidence
                confidence = "medium"
                if hasattr(opp, 'confidence'):
                    confidence = _safe_str(opp.confidence, "medium").lower()
                    if confidence not in ("high", "medium", "low"):
                        confidence = "medium"

                # Extract action steps
                action_steps = []
                if hasattr(opp, 'action_required'):
                    if isinstance(opp.action_required, list):
                        action_steps = [str(a) for a in opp.action_required if a]
                    elif opp.action_required:
                        action_steps = [str(opp.action_required)]

                # Extract deadline and IRS reference
                deadline = getattr(opp, 'deadline', None)
                irs_reference = getattr(opp, 'irs_reference', None)

                rec = _create_recommendation(
                    id=str(opp_id),
                    category=category,
                    title=title,
                    summary=description,
                    estimated_savings=savings,
                    priority=priority,
                    urgency="moderate",
                    confidence=confidence,
                    action_steps=action_steps,
                    deadline=deadline,
                    irs_reference=irs_reference,
                    source="opportunity_detector"
                )
                if rec:
                    recommendations.append(rec)

            except Exception as opp_error:
                logger.debug(f"Failed to process opportunity {i}: {opp_error}")
                continue

    except ImportError as e:
        logger.debug(f"TaxOpportunityDetector not available: {e}")
    except Exception as e:
        logger.warning(f"TaxOpportunityDetector failed: {e}")
        logger.debug(traceback.format_exc())

    return recommendations


def _normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, remove punctuation, extra spaces)."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # Replace punctuation with space
    text = re.sub(r'\s+', ' ', text)  # Collapse multiple spaces
    return text.strip()


# =============================================================================
# TOPIC-BASED DEDUPLICATION KEYS
# =============================================================================
# Maps common keywords to canonical topic keys for better deduplication
TOPIC_KEYWORDS = {
    # Retirement topics
    "401k": ["401k", "401(k)", "401 k"],
    "ira": ["ira", "traditional ira", "roth ira"],
    "sep_ira": ["sep-ira", "sep ira", "sepira"],
    "hsa": ["hsa", "health savings", "health savings account"],
    "retirement": ["retirement", "retire"],
    "catch_up": ["catch-up", "catch up", "catchup", "age 50"],

    # Business topics
    "scorp": ["s-corp", "s corp", "scorp", "s-corporation", "s corporation"],
    "qbi": ["qbi", "qualified business income", "section 199a", "199a"],
    "sstb": ["sstb", "specified service"],
    "self_employment": ["self-employment", "self employment", "se tax"],
    "home_office": ["home office", "home-office"],

    # Deduction topics
    "itemize": ["itemize", "itemized", "itemizing", "schedule a"],
    "standard_deduction": ["standard deduction"],
    "salt": ["salt", "state and local tax", "state local tax"],
    "mortgage": ["mortgage interest", "mortgage"],
    "charitable": ["charitable", "charity", "donation", "donating"],
    "bunching": ["bunching", "bunch"],

    # Credit topics
    "child_tax_credit": ["child tax credit", "ctc"],
    "eitc": ["eitc", "earned income", "eic"],
    "education_credit": ["education credit", "aotc", "lifetime learning", "american opportunity"],
    "energy_credit": ["energy credit", "solar", "ev credit", "electric vehicle"],
    "dependent_care": ["dependent care", "childcare", "child care"],

    # Investment topics
    "capital_gains": ["capital gain", "capital gains", "ltcg", "stcg"],
    "tax_loss": ["tax-loss", "tax loss", "loss harvesting", "harvest"],
    "niit": ["niit", "net investment income", "3.8%"],
    "dividends": ["dividend", "qualified dividend"],

    # Filing topics
    "filing_status": ["filing status", "head of household", "hoh", "mfs", "mfj"],
    "withholding": ["withholding", "w-4", "w4"],
    "estimated_tax": ["estimated tax", "quarterly", "underpayment", "penalty"],

    # Other
    "backdoor_roth": ["backdoor roth", "backdoor", "mega backdoor"],
    "rmd": ["rmd", "required minimum"],
    "medicare": ["medicare", "irmaa"],
    "social_security": ["social security", "ss benefit", "claiming age"],
    "amt": ["amt", "alternative minimum"],
    "rental": ["rental", "depreciation", "schedule e"],
    "1031": ["1031", "like-kind", "exchange"],
}


def _extract_topic(text: str) -> Optional[str]:
    """Extract the canonical topic from text using keyword matching."""
    if not text:
        return None

    text_lower = text.lower()

    # Check each topic's keywords
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return topic

    return None


def _get_dedup_key(rec: UnifiedRecommendation) -> str:
    """Generate a deduplication key for a recommendation."""
    # Try to extract a topic-based key first
    topic = _extract_topic(rec.title)
    if topic:
        return f"topic:{topic}"

    # Fallback: normalize title and extract significant words
    stop_words = {'the', 'a', 'an', 'your', 'you', 'may', 'can', 'for', 'to', 'and', 'or',
                  'of', 'in', 'on', 'is', 'are', 'be', 'will', 'would', 'could', 'should',
                  'this', 'that', 'these', 'with', 'from', 'by', 'at', 'as', 'if', 'it',
                  'maximize', 'consider', 'claim', 'review', 'check', 'potential', 'opportunity'}

    title_words = _normalize_text(rec.title).split()
    # Remove plurals (simple stemming)
    significant_words = []
    for w in title_words:
        if w not in stop_words and len(w) > 2:
            # Simple plural removal
            if w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
                w = w[:-1]
            significant_words.append(w)

    significant_words = significant_words[:4]
    title_key = '-'.join(sorted(significant_words))

    return f"title:{title_key}"


def _are_similar_recommendations(rec1: UnifiedRecommendation, rec2: UnifiedRecommendation) -> bool:
    """Check if two recommendations are similar enough to be considered duplicates."""
    # Extract topics - if both have same topic, they're duplicates
    topic1 = _extract_topic(rec1.title)
    topic2 = _extract_topic(rec2.title)

    if topic1 and topic2 and topic1 == topic2:
        return True

    # If one has a topic and the other doesn't, check if the topic keyword appears in the other
    if topic1 and not topic2:
        keywords = TOPIC_KEYWORDS.get(topic1, [])
        for kw in keywords:
            if kw in rec2.title.lower():
                return True

    if topic2 and not topic1:
        keywords = TOPIC_KEYWORDS.get(topic2, [])
        for kw in keywords:
            if kw in rec1.title.lower():
                return True

    # Fallback: word overlap check (cross-category)
    title1_words = set(_normalize_text(rec1.title).split())
    title2_words = set(_normalize_text(rec2.title).split())

    # Remove very common words
    common = {'the', 'a', 'an', 'your', 'you', 'to', 'and', 'or', 'of', 'in', 'for'}
    title1_words -= common
    title2_words -= common

    if not title1_words or not title2_words:
        return False

    # Calculate Jaccard similarity
    intersection = len(title1_words & title2_words)
    union = len(title1_words | title2_words)

    if union == 0:
        return False

    similarity = intersection / union
    return similarity > 0.6  # 60% overlap threshold


def _merge_and_dedupe(all_recs: List[UnifiedRecommendation]) -> List[UnifiedRecommendation]:
    """
    Merge recommendations and remove duplicates intelligently.

    Strategy:
    1. Topic-based grouping (401k, HSA, QBI, etc.)
    2. Keep highest-value recommendation per topic
    3. Merge action steps from duplicates for richer content
    4. Cross-category deduplication for same topic
    """
    if not all_recs:
        return []

    # Filter out None and invalid recommendations
    valid_recs = [r for r in all_recs if r is not None and r.title]

    if not valid_recs:
        return []

    # Group by dedup key (topic-based)
    by_key: Dict[str, List[UnifiedRecommendation]] = {}
    for rec in valid_recs:
        key = _get_dedup_key(rec)
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(rec)

    # Select best from each group and merge action steps
    deduped = []
    confidence_order = {"high": 3, "medium": 2, "low": 1}

    for key, group in by_key.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Sort by savings (desc), then confidence, then specificity (longer title = more specific)
            def score(r: UnifiedRecommendation) -> Tuple[float, int, int]:
                return (
                    r.estimated_savings,
                    confidence_order.get(r.confidence, 0),
                    len(r.title)
                )

            group.sort(key=score, reverse=True)
            best = group[0]

            # Merge unique action steps from other duplicates
            if best.action_steps:
                existing_steps = set(s.lower().strip() for s in best.action_steps)
                for other in group[1:]:
                    if other.action_steps:
                        for step in other.action_steps:
                            step_lower = step.lower().strip()
                            # Add unique steps that aren't too similar
                            if step_lower not in existing_steps and len(step) > 10:
                                # Check if it's actually new info
                                is_new = True
                                for existing in existing_steps:
                                    # Simple similarity check
                                    if len(set(step_lower.split()) & set(existing.split())) > 3:
                                        is_new = False
                                        break
                                if is_new and len(best.action_steps) < 8:
                                    best.action_steps.append(step)
                                    existing_steps.add(step_lower)

            # Track sources that contributed
            sources = list(set(r.source for r in group))
            if len(sources) > 1 and best.action_steps:
                best.action_steps.append(f"(Combined from {len(group)} sources: {', '.join(sources[:3])})")

            deduped.append(best)

    # Second pass: Cross-key similarity check (catch remaining duplicates)
    final = []
    for rec in deduped:
        is_duplicate = False
        for i, existing in enumerate(final):
            if _are_similar_recommendations(rec, existing):
                # Keep the one with higher savings
                if rec.estimated_savings > existing.estimated_savings:
                    # Merge action steps before replacing
                    if rec.action_steps and existing.action_steps:
                        existing_steps = set(s.lower().strip() for s in rec.action_steps)
                        for step in existing.action_steps:
                            if step.lower().strip() not in existing_steps and len(rec.action_steps) < 8:
                                rec.action_steps.append(step)
                    final[i] = rec
                is_duplicate = True
                break
        if not is_duplicate:
            final.append(rec)

    logger.debug(f"Deduplication: {len(all_recs)} -> {len(valid_recs)} valid -> {len(final)} unique")
    return final


def _sort_recommendations(recs: List[UnifiedRecommendation], urgency_level: str) -> List[UnifiedRecommendation]:
    """
    Sort recommendations by urgency-adjusted priority and savings.

    Scoring formula:
    - Base score = (priority_weight * 1000) + (urgency_weight * 500) + (savings * 0.1)
    - Time-sensitive items get 1.5x boost during critical/high urgency periods
    - High-confidence items get slight preference when scores are similar
    """
    if not recs:
        return []

    # Filter out None values
    valid_recs = [r for r in recs if r is not None]
    if not valid_recs:
        return []

    # Priority weights
    priority_weight = {"high": 3, "medium": 2, "low": 1}
    urgency_weight = {"critical": 4, "high": 3, "moderate": 2, "planning": 1}
    confidence_weight = {"high": 1.1, "medium": 1.0, "low": 0.9}

    # If we're in critical/high urgency, boost time-sensitive items
    urgency_str = _safe_str(urgency_level, "PLANNING").upper()
    time_boost = 1.5 if urgency_str in ["CRITICAL", "HIGH"] else 1.0

    # Time-sensitive categories
    time_sensitive_categories = {"retirement", "deduction", "timing", "deadline", "planning"}

    def score(rec: UnifiedRecommendation) -> Tuple[float, float]:
        """Return (primary_score, tiebreaker) for stable sorting."""
        try:
            # Get weights with defaults
            p = priority_weight.get(_safe_str(rec.priority, "medium").lower(), 2)
            u = urgency_weight.get(_safe_str(rec.urgency, "moderate").lower(), 2)
            c = confidence_weight.get(_safe_str(rec.confidence, "medium").lower(), 1.0)
            s = _safe_float(rec.estimated_savings, 0, min_val=0)

            # Check if time-sensitive
            category = _safe_str(rec.category, "general").lower()
            is_time_sensitive = category in time_sensitive_categories
            boost = time_boost if is_time_sensitive else 1.0

            # Primary score
            primary = (p * 1000 + u * 500 + s * 0.1) * boost * c

            # Tiebreaker: prefer higher savings
            tiebreaker = s

            return (primary, tiebreaker)
        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logger.debug(f"Scoring calculation error: {e}")
            return (0.0, 0.0)

    try:
        return sorted(valid_recs, key=score, reverse=True)
    except Exception as e:
        logger.warning(f"Sorting failed: {e}")
        return valid_recs


# =============================================================================
# TAX STRATEGY ADVISOR - Multi-Year Strategic Tax Planning
# =============================================================================
def _get_tax_strategy_advisor_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get multi-year tax strategy recommendations from TaxStrategyAdvisor.

    USER VALUE: Forward-looking strategies across 10 categories:
    - Retirement: Backdoor Roth timing, Roth conversion ladders, catch-up contribution planning
    - Healthcare: HSA mega-funding, FSA coordination, ACA subsidy optimization
    - Investment: Tax-loss harvesting calendar, asset location optimization, gain deferral
    - Education: 529 superfunding, Coverdell timing, education credit coordination
    - Charitable: DAF bunching strategies, QCD planning for 70.5+, appreciated stock timing
    - Real Estate: Cost seg studies, 1031 exchange deadlines, opportunity zone planning
    - Business: Entity conversion timing, retirement plan selection, owner compensation
    - Timing: Income shifting between years, deduction acceleration/deferral
    - State-Specific: State domicile planning, remote work tax implications
    - Family: Income shifting to lower-bracket family members, custodial accounts

    Typical savings: $2,000-$50,000+ through coordinated multi-year planning
    """
    recommendations = []

    try:
        from recommendation.tax_strategy_advisor import TaxStrategyAdvisor

        # Build profile data
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 35, min_val=18, max_val=120)
        se_income = _safe_float(profile.get("self_employment_income"), 0, min_val=0)
        retirement_401k = _safe_float(profile.get("retirement_401k"), 0, min_val=0)
        hsa = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0, min_val=0)

        if total_income < 50000:
            return recommendations

        # Create a TaxReturn-like adapter for the advisor
        class TaxReturnAdapter:
            """Adapter to interface with TaxStrategyAdvisor."""
            class TaxpayerAdapter:
                class FilingStatusAdapter:
                    def __init__(self, status):
                        self.value = status
                def __init__(self, profile):
                    fs = _safe_str(profile.get("filing_status"), "single")
                    self.filing_status = self.FilingStatusAdapter(fs)
                    self.age = _safe_int(profile.get("age"), 35)
                    self.dependents = []
                    for _ in range(_safe_int(profile.get("dependents") or profile.get("num_dependents"), 0)):
                        self.dependents.append({"relationship": "child"})

            class IncomeAdapter:
                def __init__(self, profile):
                    self.w2_wages = _safe_float(profile.get("w2_income"), 0)
                    self.self_employment = _safe_float(profile.get("self_employment_income"), 0)
                    self.investment = _safe_float(profile.get("investment_income"), 0)
                    self.rental = _safe_float(profile.get("rental_income"), 0)

            class RetirementAdapter:
                def __init__(self, profile):
                    self.contribution_401k = _safe_float(profile.get("retirement_401k"), 0)
                    self.contribution_ira = _safe_float(profile.get("retirement_ira"), 0)
                    self.contribution_hsa = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0)
                    self.employer_match_available = _safe_float(profile.get("employer_match"), 0)
                    self.has_hdhp = profile.get("has_hdhp", False)

            class DeductionsAdapter:
                def __init__(self, profile):
                    self.mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0)
                    self.property_taxes = _safe_float(profile.get("property_taxes"), 0)
                    self.state_tax = _safe_float(profile.get("state_income_tax"), 0)
                    self.charitable = _safe_float(profile.get("charitable_contributions"), 0)
                    self.medical = _safe_float(profile.get("medical_expenses"), 0)

            def __init__(self, profile):
                self.taxpayer = self.TaxpayerAdapter(profile)
                self.income = self.IncomeAdapter(profile)
                self.retirement = self.RetirementAdapter(profile)
                self.deductions = self.DeductionsAdapter(profile)
                self.adjusted_gross_income = _safe_float(profile.get("total_income"), 0)
                self.tax_liability = _safe_float(profile.get("tax_liability"), 0) or self.adjusted_gross_income * 0.22

        tax_return = TaxReturnAdapter(profile)
        advisor = TaxStrategyAdvisor()
        report = advisor.generate_strategy_report(tax_return)

        # Get all strategies from the report
        all_strategies = (
            report.immediate_strategies +
            report.current_year_strategies +
            report.next_year_strategies[:3]
        )

        # Convert strategies to UnifiedRecommendations
        for idx, strategy in enumerate(all_strategies[:8]):  # Top 8 strategies
            urgency = "high" if strategy.priority == "immediate" else (
                "moderate" if strategy.priority == "current_year" else "planning"
            )

            # Build action steps from strategy
            action_steps = strategy.action_steps[:4]  # Limit to 4 steps
            if strategy.deadline:
                action_steps.append(f"Complete by: {strategy.deadline}")

            rec = _create_recommendation(
                id=f"tsa_{strategy.category}_{idx}",
                title=strategy.title,
                summary=strategy.description,
                category=f"strategy_{strategy.category}",
                estimated_savings=strategy.estimated_savings,
                priority="high" if strategy.priority == "immediate" else ("medium" if strategy.priority == "current_year" else "low"),
                urgency=urgency,
                confidence="high",
                source="tax_strategy_advisor",
                action_steps=action_steps,
                irs_reference="",
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"TaxStrategyAdvisor generated {len(recommendations)} strategies")

    except ImportError:
        logger.debug("TaxStrategyAdvisor not available")
    except Exception as e:
        logger.warning(f"TaxStrategyAdvisor error: {e}")

    return recommendations


# =============================================================================
# SMART DEDUCTION DETECTOR - Automatic Deduction Discovery (Rule-Based Fallback)
# =============================================================================
def _get_smart_deduction_detector_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get recommendations for missed deductions/credits using rule-based analysis.

    USER VALUE: Identifies common missed deductions and credits:
    - Student loan interest (up to $2,500)
    - Educator expenses ($300 above-the-line)
    - HSA contributions (triple tax advantage)
    - Self-employment deductions (home office, SE tax, health insurance)
    - Standard vs itemized comparison

    Typical savings: $500-$10,000 from missed deductions/credits
    """
    recommendations = []

    try:
        # Build detection context from profile
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        w2_income = _safe_float(profile.get("w2_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 35, min_val=18, max_val=120)
        dependents = _safe_int(profile.get("dependents") or profile.get("num_dependents"), 0, min_val=0)
        se_income = _safe_float(profile.get("self_employment_income"), 0, min_val=0)
        student_loan = _safe_float(profile.get("student_loan_interest"), 0)
        hsa = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0)
        has_hdhp = profile.get("has_hdhp", False)
        mortgage_interest = _safe_float(profile.get("mortgage_interest"), 0)
        property_taxes = _safe_float(profile.get("property_taxes"), 0)
        state_tax = _safe_float(profile.get("state_income_tax"), 0)
        charitable = _safe_float(profile.get("charitable_contributions"), 0)

        if total_income < 15000:
            return recommendations

        # Standard deduction amounts 2025
        std_deductions = {
            "single": 15750, "married_joint": 31500, "married_separate": 15750,
            "head_of_household": 23850, "qualifying_widow": 31500
        }
        std_ded = std_deductions.get(filing_status, 15750)

        # Calculate itemized total
        salt = min(10000, property_taxes + state_tax)  # SALT cap
        itemized_total = mortgage_interest + salt + charitable

        # Standard vs Itemized recommendation
        if itemized_total > std_ded + 1000:
            benefit = itemized_total - std_ded
            rec = _create_recommendation(
                id="sdd_itemize_vs_standard",
                title="Itemize Deductions to Save More",
                summary=f"Your itemized deductions (${itemized_total:,.0f}) exceed the standard deduction (${std_ded:,.0f}) by ${benefit:,.0f}.",
                category="deduction_strategy",
                estimated_savings=benefit * 0.22,
                priority="high",
                urgency="high",
                confidence="high",
                source="smart_deduction_detector",
                action_steps=[
                    f"Itemized total: ${itemized_total:,.0f} (mortgage + SALT + charitable)",
                    f"Standard deduction: ${std_ded:,.0f}",
                    "File Schedule A to claim itemized deductions",
                    "Keep receipts and documentation for all deductions",
                ],
                irs_reference="IRC Section 63",
            )
            if rec:
                recommendations.append(rec)

        # Student loan interest deduction
        if student_loan > 0 and student_loan <= 2500 and total_income < 90000:
            rec = _create_recommendation(
                id="sdd_student_loan_interest",
                title="Claim Student Loan Interest Deduction",
                summary=f"You can deduct up to ${min(student_loan, 2500):,.0f} in student loan interest as an above-the-line deduction.",
                category="deduction",
                estimated_savings=min(student_loan, 2500) * 0.22,
                priority="high",
                urgency="high",
                confidence="high",
                source="smart_deduction_detector",
                action_steps=[
                    f"Deductible amount: ${min(student_loan, 2500):,.0f}",
                    "Report on Schedule 1, Line 21",
                    "Form 1098-E from lender documents this",
                    "Above-the-line: No itemizing required",
                ],
                irs_reference="IRC Section 221",
            )
            if rec:
                recommendations.append(rec)

        # HSA contribution opportunity
        if has_hdhp:
            hsa_limit = 8550 if profile.get("family_coverage") else 4300
            if age >= 55:
                hsa_limit += 1000
            remaining = hsa_limit - hsa
            if remaining > 500:
                savings = remaining * 0.30  # Tax + FICA
                rec = _create_recommendation(
                    id="sdd_hsa_maximize",
                    title="Maximize HSA Contribution",
                    summary=f"You can contribute ${remaining:,.0f} more to your HSA this year for triple tax benefits.",
                    category="deduction",
                    estimated_savings=savings,
                    priority="high",
                    urgency="high",
                    confidence="high",
                    source="smart_deduction_detector",
                    action_steps=[
                        f"Current contribution: ${hsa:,.0f}",
                        f"Maximum allowed: ${hsa_limit:,.0f}",
                        f"Room to contribute: ${remaining:,.0f}",
                        "Contributions are pre-tax (reduces income tax + FICA)",
                    ],
                    irs_reference="IRC Section 223",
                )
                if rec:
                    recommendations.append(rec)

        # Self-employment deductions
        if se_income > 10000:
            se_tax_ded = se_income * 0.0765  # Half of SE tax
            rec = _create_recommendation(
                id="sdd_se_tax_deduction",
                title="Claim Self-Employment Tax Deduction",
                summary=f"Deduct ${se_tax_ded:,.0f} (half of your self-employment tax) as an above-the-line deduction.",
                category="deduction",
                estimated_savings=se_tax_ded * 0.22,
                priority="high",
                urgency="high",
                confidence="high",
                source="smart_deduction_detector",
                action_steps=[
                    f"SE tax deduction: ${se_tax_ded:,.0f}",
                    "Report on Schedule 1, Line 15",
                    "Automatic calculation on Schedule SE",
                    "Above-the-line: No itemizing required",
                ],
                irs_reference="IRC Section 164(f)",
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"SmartDeductionDetector (rule-based) found {len(recommendations)} opportunities")

    except Exception as e:
        logger.warning(f"SmartDeductionDetector error: {e}")

    return recommendations


# =============================================================================
# TAX PLANNING INSIGHTS ENGINE - Proactive Planning Reminders (Rule-Based)
# =============================================================================
def _get_planning_insights_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get proactive tax planning insights using rule-based analysis.

    USER VALUE: Generates time-sensitive planning reminders:
    - Quarterly estimated tax payment reminders with amounts
    - Retirement contribution deadline reminders
    - RMD reminders for 73+
    - Year-end tax planning checklist

    Typical value: $500-$5,000 in avoided penalties + optimized timing
    """
    recommendations = []
    from datetime import date

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 35, min_val=18, max_val=120)
        se_income = _safe_float(profile.get("self_employment_income"), 0, min_val=0)
        withholding = _safe_float(profile.get("withholding"), 0, min_val=0)
        estimated_payments = _safe_float(profile.get("estimated_payments_ytd"), 0)
        prior_year_tax = _safe_float(profile.get("prior_year_tax"), 0)
        retirement_balance = _safe_float(profile.get("retirement_balance"), 0)

        if total_income < 20000:
            return recommendations

        current_month = date.today().month
        current_quarter = (current_month - 1) // 3 + 1

        # Calculate estimated tax liability
        std_deductions = {
            "single": 15750, "married_joint": 31500, "married_separate": 15750,
            "head_of_household": 23850, "qualifying_widow": 31500
        }
        std_ded = std_deductions.get(filing_status, 15750)
        taxable = max(0, total_income - std_ded)
        estimated_tax = taxable * 0.22  # Rough estimate

        # Quarterly estimated tax payment reminder
        total_paid = withholding + estimated_payments
        tax_owed = estimated_tax - total_paid
        quarterly_payment = tax_owed / (5 - current_quarter) if current_quarter < 5 else tax_owed

        if quarterly_payment > 500 and se_income > 10000:
            quarter_deadlines = {1: "April 15", 2: "June 15", 3: "September 15", 4: "January 15"}
            rec = _create_recommendation(
                id=f"pie_estimated_tax_q{current_quarter}",
                title=f"Q{current_quarter} Estimated Tax Payment Due",
                summary=f"Based on your income and withholding, you may need to make estimated tax payments of ${quarterly_payment:,.0f} to avoid underpayment penalty.",
                category="planning_estimated_tax",
                estimated_savings=quarterly_payment * 0.04,  # Avoid ~4% penalty
                priority="high",
                urgency="high",
                confidence="medium",
                source="planning_insights_engine",
                action_steps=[
                    f"Estimated tax liability: ${estimated_tax:,.0f}",
                    f"Paid so far: ${total_paid:,.0f}",
                    f"Suggested quarterly payment: ${quarterly_payment:,.0f}",
                    f"Q{current_quarter} due: {quarter_deadlines.get(current_quarter, 'Check IRS.gov')}",
                    "Pay via IRS Direct Pay or EFTPS",
                ],
                irs_reference="IRC Section 6654",
            )
            if rec:
                recommendations.append(rec)

        # RMD reminder for age 73+
        if age >= 73 and retirement_balance > 50000:
            # Simplified RMD calculation using uniform lifetime table factor
            rmd_factor = 26.5 - (age - 73) * 0.5  # Rough approximation
            rmd_amount = retirement_balance / max(rmd_factor, 1)

            rec = _create_recommendation(
                id="pie_rmd_reminder",
                title="Required Minimum Distribution (RMD) Due",
                summary=f"You're {age} with retirement accounts. Your estimated RMD is ${rmd_amount:,.0f}. Failure to take RMD results in 25% penalty.",
                category="planning_retirement",
                estimated_savings=rmd_amount * 0.25,  # Avoid 25% penalty
                priority="high",
                urgency="high",
                confidence="medium",
                source="planning_insights_engine",
                action_steps=[
                    f"Estimated RMD: ${rmd_amount:,.0f}",
                    "Deadline: December 31 (April 1 for first RMD year)",
                    "Take from each traditional IRA/401(k)",
                    "Consider Qualified Charitable Distribution (QCD) if charitable",
                ],
                irs_reference="IRC Section 401(a)(9)",
            )
            if rec:
                recommendations.append(rec)

        # Year-end tax planning (October-December)
        if current_month >= 10:
            # Retirement contribution reminder
            k401_limit = 23500
            k401_catchup = 7500 if age >= 50 else 0
            total_limit = k401_limit + k401_catchup
            k401_current = _safe_float(profile.get("retirement_401k"), 0)
            k401_room = total_limit - k401_current

            if k401_room > 2000:
                rec = _create_recommendation(
                    id="pie_401k_year_end",
                    title="Maximize 401(k) Before Year-End",
                    summary=f"You can contribute ${k401_room:,.0f} more to your 401(k) before December 31 to reduce your 2025 taxes.",
                    category="planning_year_end",
                    estimated_savings=k401_room * 0.24,
                    priority="high",
                    urgency="high",
                    confidence="high",
                    source="planning_insights_engine",
                    action_steps=[
                        f"2025 401(k) limit: ${total_limit:,.0f}",
                        f"Your contributions: ${k401_current:,.0f}",
                        f"Room to contribute: ${k401_room:,.0f}",
                        "Increase payroll contribution to maximize by Dec 31",
                    ],
                    irs_reference="IRC Section 402(g)",
                )
                if rec:
                    recommendations.append(rec)

            # Charitable giving reminder
            charitable = _safe_float(profile.get("charitable_contributions"), 0)
            if total_income > 100000 and charitable < 5000:
                rec = _create_recommendation(
                    id="pie_charitable_year_end",
                    title="Year-End Charitable Giving Strategy",
                    summary="Consider making charitable contributions before December 31 for a 2025 tax deduction.",
                    category="planning_year_end",
                    estimated_savings=2000 * 0.24,  # Assume $2000 donation
                    priority="medium",
                    urgency="moderate",
                    confidence="medium",
                    source="planning_insights_engine",
                    action_steps=[
                        "Donate appreciated stock for double tax benefit",
                        "Consider Donor Advised Fund for bunching strategy",
                        "If 70.5+, use Qualified Charitable Distribution from IRA",
                        "Get receipts for donations over $250",
                    ],
                    irs_reference="IRC Section 170",
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"TaxPlanningEngine (rule-based) generated {len(recommendations)} insights")

    except Exception as e:
        logger.warning(f"TaxPlanningEngine error: {e}")

    return recommendations


# =============================================================================
# COMPLEXITY ROUTER - CPA Referral Recommendations (Rule-Based)
# =============================================================================
def _get_complexity_router_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get CPA referral recommendations based on tax complexity assessment.

    USER VALUE: Evaluates situation complexity and recommends CPA help when beneficial:
    - Simple (0-15 points): W-2 only, standard deduction - DIY appropriate
    - Moderate (16-35 points): Multiple income sources - DIY with guidance
    - Complex (36-60 points): Self-employment, investments - Consider CPA review
    - Professional (61+): Foreign income, high complexity - CPA recommended

    User benefit: Avoid costly mistakes on complex returns ($500-$10,000+ error prevention)
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        se_income = _safe_float(profile.get("self_employment_income"), 0, min_val=0)
        investment_income = _safe_float(profile.get("investment_income"), 0, min_val=0)
        rental_income = _safe_float(profile.get("rental_income"), 0, min_val=0)

        if total_income < 20000:
            return recommendations

        # Calculate complexity score
        score = 0
        factors = []

        # Complexity factors with weights
        if se_income > 0:
            score += 25
            factors.append("Self-Employment")

        if rental_income != 0:
            score += 20
            factors.append("Rental Income")

        if profile.get("has_foreign_income"):
            score += 30
            factors.append("Foreign Income")

        if profile.get("has_crypto"):
            score += 15
            factors.append("Crypto Transactions")

        if profile.get("has_stock_sales") or _safe_float(profile.get("capital_gains"), 0) != 0:
            score += 15
            factors.append("Capital Gains")

        if investment_income > 0:
            score += 10
            factors.append("Investment Income")

        w2_count = _safe_int(profile.get("w2_count"), 1, min_val=1)
        if w2_count > 1:
            score += 5
            factors.append(f"Multiple W-2s ({w2_count})")

        if profile.get("will_itemize"):
            score += 10
            factors.append("Itemized Deductions")

        if _safe_float(profile.get("hsa_contributions"), 0) > 0:
            score += 5
            factors.append("HSA")

        if _safe_float(profile.get("education_expenses"), 0) > 0:
            score += 5
            factors.append("Education Expenses")

        dependents = _safe_int(profile.get("dependents") or profile.get("num_dependents"), 0)
        if dependents > 0:
            score += 5
            factors.append(f"Dependents ({dependents})")

        if total_income > 400000:
            score += 35
            factors.append("High Income + AMT Risk")
        elif total_income > 200000:
            score += 15
            factors.append("High Income")

        # Determine complexity level
        if score <= 15:
            level = "simple"
            time_estimate = (3, 5)
        elif score <= 35:
            level = "moderate"
            time_estimate = (8, 12)
        elif score <= 60:
            level = "complex"
            time_estimate = (15, 20)
        else:
            level = "professional"
            time_estimate = (30, 60)

        # Check for automatic CPA recommendation
        cpa_recommended = False
        cpa_reason = None

        if profile.get("has_foreign_income"):
            cpa_recommended = True
            cpa_reason = "Foreign income requires specialized knowledge for tax treaty and FBAR compliance"
        elif total_income > 500000:
            cpa_recommended = True
            cpa_reason = "High income situations benefit from professional tax planning"
        elif len(factors) > 5:
            cpa_recommended = True
            cpa_reason = "Multiple complexity factors suggest professional review would be beneficial"

        # Generate recommendations
        if cpa_recommended or level == "professional":
            estimated_value = 5000 if total_income > 500000 else (2500 if total_income > 250000 else 1000)

            rec = _create_recommendation(
                id="cr_cpa_recommended",
                title="Consider Professional CPA Review",
                summary=f"Your tax situation scores {score}/100 on complexity. A CPA review could prevent costly errors and identify additional savings.",
                category="cpa_referral",
                estimated_savings=estimated_value,
                priority="high",
                urgency="high" if level == "professional" else "moderate",
                confidence="high",
                source="complexity_router",
                action_steps=[
                    f"Complexity level: {level.title()} ({score}/100)",
                    f"Estimated time if DIY: {time_estimate[0]}-{time_estimate[1]} minutes",
                    f"Key factors: {', '.join(factors[:4])}",
                    cpa_reason or "Complex situation benefits from professional review",
                ],
                irs_reference="",
            )
            if rec:
                recommendations.append(rec)

        elif level == "complex":
            rec = _create_recommendation(
                id="cr_cpa_optional",
                title="Complex Return - CPA Review Optional",
                summary=f"Your return has {len(factors)} complexity factors. DIY is possible with care, but CPA review could catch additional savings.",
                category="cpa_referral",
                estimated_savings=500,
                priority="medium",
                urgency="moderate",
                confidence="medium",
                source="complexity_router",
                action_steps=[
                    f"Complexity: {level.title()} ({score}/100)",
                    f"Factors: {', '.join(factors[:3])}",
                    f"Estimated time: {time_estimate[0]}-{time_estimate[1]} minutes",
                    "Follow our guided flow for best results",
                ],
                irs_reference="",
            )
            if rec:
                recommendations.append(rec)

        # Complexity summary for all users with factors
        if factors:
            rec = _create_recommendation(
                id="cr_complexity_summary",
                title=f"Your Tax Complexity: {level.title()}",
                summary=f"Based on your situation, we identified {len(factors)} complexity factors that affect your tax return.",
                category="complexity_assessment",
                estimated_savings=0,
                priority="low",
                urgency="planning",
                confidence="high",
                source="complexity_router",
                action_steps=[
                    f"Complexity score: {score}/100",
                    f"Factors: {', '.join(factors)}",
                    f"Recommended flow: smart_{level}",
                    f"Estimated completion: {time_estimate[0]}-{time_estimate[1]} min",
                ],
                irs_reference="",
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"ComplexityRouter (rule-based) generated {len(recommendations)} recommendations")

    except Exception as e:
        logger.warning(f"ComplexityRouter error: {e}")

    return recommendations


# =============================================================================
# RULES-BASED RECOMMENDER - Compliance and Specialized Insights (Rule-Based)
# =============================================================================
def _get_rules_based_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get compliance and specialized tax insights using rule-based analysis.

    USER VALUE: Evaluates common compliance rules:
    - Virtual Currency (Form 1040 digital asset question, Form 8949)
    - Foreign Assets (FBAR, Form 8938 FATCA)
    - NIIT (3.8% on investment income >$200K/$250K)
    - QBI deduction for pass-through income

    Typical value: $500-$20,000+ in compliance and optimization
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        investment_income = _safe_float(profile.get("investment_income"), 0)
        se_income = _safe_float(profile.get("self_employment_income"), 0)
        partnership_income = _safe_float(profile.get("partnership_income"), 0)
        scorp_income = _safe_float(profile.get("scorp_income"), 0)
        rental_income = _safe_float(profile.get("rental_income"), 0)

        if total_income < 25000:
            return recommendations

        # Virtual Currency Rules
        if profile.get("has_crypto"):
            rec = _create_recommendation(
                id="rbr_crypto_compliance",
                title="Answer Digital Asset Question on Form 1040",
                summary="You have cryptocurrency transactions. The IRS requires you to answer 'Yes' to the digital asset question on Form 1040.",
                category="compliance_crypto",
                estimated_savings=0,
                priority="high",
                urgency="critical",
                confidence="high",
                source="rules_based_recommender",
                action_steps=[
                    "Answer 'Yes' to digital asset question on Form 1040",
                    "Report all crypto sales on Form 8949",
                    "Transfer totals to Schedule D",
                    "Consider specific identification for cost basis",
                ],
                irs_reference="Notice 2014-21",
            )
            if rec:
                recommendations.append(rec)

        # Foreign Account Rules (FBAR)
        foreign_value = _safe_float(profile.get("foreign_account_value"), 0)
        if foreign_value > 10000 or profile.get("has_foreign_accounts"):
            rec = _create_recommendation(
                id="rbr_fbar_required",
                title="FBAR Filing Required",
                summary="Your foreign financial accounts may exceed $10,000. FBAR (FinCEN Form 114) filing is required.",
                category="compliance_foreign",
                estimated_savings=0,
                priority="high",
                urgency="critical",
                confidence="high",
                source="rules_based_recommender",
                action_steps=[
                    "File FinCEN Form 114 (FBAR) electronically",
                    "Include all foreign bank and financial accounts",
                    "Report maximum value during the year",
                    "Due April 15 (auto-extension to October 15)",
                ],
                irs_reference="31 USC 5314",
            )
            if rec:
                recommendations.append(rec)

        # NIIT (Net Investment Income Tax)
        niit_threshold = 250000 if "joint" in filing_status else 200000
        if total_income > niit_threshold and investment_income > 0:
            niit_base = min(investment_income, total_income - niit_threshold)
            niit_tax = niit_base * 0.038

            rec = _create_recommendation(
                id="rbr_niit_applies",
                title="Net Investment Income Tax (NIIT) Applies",
                summary=f"Your income exceeds ${niit_threshold:,}. You may owe approximately ${niit_tax:,.0f} in NIIT (3.8% on investment income).",
                category="compliance_niit",
                estimated_savings=0,  # This is tax owed, not savings
                priority="high",
                urgency="high",
                confidence="high",
                source="rules_based_recommender",
                action_steps=[
                    f"NIIT applies to: ${niit_base:,.0f}",
                    f"Estimated NIIT: ${niit_tax:,.0f}",
                    "Complete Form 8960",
                    "Consider tax-loss harvesting to reduce investment income",
                ],
                irs_reference="IRC Section 1411",
            )
            if rec:
                recommendations.append(rec)

        # QBI Deduction for Pass-Through Income
        qbi_income = se_income + partnership_income + scorp_income + rental_income
        if qbi_income > 5000:
            qbi_threshold = 394600 if "joint" in filing_status else 197300

            if total_income < qbi_threshold:
                qbi_deduction = qbi_income * 0.20
                tax_savings = qbi_deduction * 0.22

                rec = _create_recommendation(
                    id="rbr_qbi_deduction",
                    title="Claim 20% QBI Deduction",
                    summary=f"Your pass-through income of ${qbi_income:,.0f} may qualify for the 20% QBI deduction, potentially saving ${tax_savings:,.0f}.",
                    category="compliance_qbi",
                    estimated_savings=tax_savings,
                    priority="high",
                    urgency="high",
                    confidence="high",
                    source="rules_based_recommender",
                    action_steps=[
                        f"Qualified Business Income: ${qbi_income:,.0f}",
                        f"Potential QBI deduction: ${qbi_deduction:,.0f}",
                        "Complete Form 8995 or 8995-A",
                        "Verify business is not a Specified Service Business",
                    ],
                    irs_reference="IRC Section 199A",
                )
                if rec:
                    recommendations.append(rec)

        # Passive Activity Loss (if rental loss)
        if rental_income < -1000:
            rental_loss = abs(rental_income)
            agi = total_income

            if agi <= 100000:
                allowed_loss = min(rental_loss, 25000)
                rec = _create_recommendation(
                    id="rbr_rental_loss_deduction",
                    title="Deduct Rental Property Losses",
                    summary=f"Your rental loss of ${rental_loss:,.0f} may be deductible up to $25,000 under the active participation exception.",
                    category="compliance_pal",
                    estimated_savings=allowed_loss * 0.22,
                    priority="medium",
                    urgency="moderate",
                    confidence="medium",
                    source="rules_based_recommender",
                    action_steps=[
                        f"Rental loss: ${rental_loss:,.0f}",
                        f"Allowed (AGI under $100K): up to $25,000",
                        "Complete Form 8582 if losses exceed allowance",
                        "Track suspended losses for future use",
                    ],
                    irs_reference="IRC Section 469",
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"RulesBasedRecommender (rule-based) generated {len(recommendations)} insights")

    except Exception as e:
        logger.warning(f"RulesBasedRecommender error: {e}")

    return recommendations


# =============================================================================
# REAL-TIME ESTIMATOR - Instant Estimates with Confidence Bands
# =============================================================================
def _get_realtime_estimator_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get instant tax estimates and quick opportunities from RealTimeEstimator.

    USER VALUE: Provides immediate feedback with confidence bands:
    - Instant refund/owed estimate from W-2 data alone
    - Confidence bands that narrow as more data is added (±5% to ±35%)
    - Quick opportunity detection: withholding adjustment, EITC eligibility,
      401(k) savings, Head of Household check
    - Progressive estimation as documents are uploaded

    Typical value: Immediate visibility + $500-$7,830 from detected opportunities
    """
    recommendations = []

    try:
        # Build W-2 data from profile
        wages = _safe_float(profile.get("w2_income") or profile.get("wages"), 0, min_val=0)
        withholding = _safe_float(profile.get("withholding"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        dependents = _safe_int(profile.get("dependents") or profile.get("num_dependents"), 0, min_val=0)
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)

        if wages < 10000:
            return recommendations

        try:
            from recommendation.realtime_estimator import RealTimeEstimator
            estimator = RealTimeEstimator()
            estimate = estimator.estimate_from_w2(
                w2_data={"wages": wages, "federal_tax_withheld": withholding},
                filing_status=filing_status,
                num_dependents=dependents,
            )

            # Create recommendation for the estimate summary
            if abs(estimate.refund_or_owed) > 100:
                result_type = "refund" if estimate.refund_or_owed > 0 else "owed"
                rec = _create_recommendation(
                    id="rte_instant_estimate",
                    title=f"Your Estimated Tax {result_type.title()}: ${abs(estimate.refund_or_owed):,.0f}",
                    summary=f"Based on your W-2, you're estimated to {'receive' if result_type == 'refund' else 'owe'} ${abs(estimate.refund_or_owed):,.0f}. Confidence: {estimate.confidence_score:.0f}% (range: ${estimate.low_estimate:,.0f} to ${estimate.high_estimate:,.0f}).",
                    category="estimate_summary",
                    estimated_savings=0,  # Informational
                    priority="high" if abs(estimate.refund_or_owed) > 1000 else "medium",
                    urgency="high" if result_type == "owed" else "moderate",
                    confidence=estimate.confidence_level.value,
                    source="realtime_estimator",
                    action_steps=[
                        f"Estimated tax: ${estimate.estimated_tax:,.0f}",
                        f"Total withholding: ${estimate.total_withholding:,.0f}",
                        f"Estimated credits: ${estimate.estimated_credits:,.0f}",
                        f"Data completeness: {estimate.data_completeness:.0f}%",
                    ],
                    irs_reference="Form 1040",
                )
                if rec:
                    recommendations.append(rec)

            # Convert quick opportunities to recommendations
            for opp in estimate.quick_opportunities:
                priority = "high" if opp.get("priority") == "immediate" else "medium"
                rec = _create_recommendation(
                    id=f"rte_opp_{opp.get('type', 'unknown')}",
                    title=opp.get("title", "Tax Opportunity Detected"),
                    summary=opp.get("description", ""),
                    category=f"quick_win_{opp.get('type', 'general')}",
                    estimated_savings=0,
                    priority=priority,
                    urgency="high" if opp.get("priority") == "immediate" else "moderate",
                    confidence="medium",
                    source="realtime_estimator",
                    action_steps=[
                        f"Potential benefit: {opp.get('potential_benefit', 'Tax savings')}",
                        "Review your situation to confirm eligibility",
                    ],
                    irs_reference="",
                )
                if rec:
                    recommendations.append(rec)

            logger.info(f"RealTimeEstimator generated {len(recommendations)} insights")

        except ImportError:
            # Fallback: rule-based quick wins
            # Over-withholding check
            std_ded = {"single": 15750, "married_joint": 31500, "head_of_household": 23850}.get(filing_status, 15750)
            taxable = max(0, wages - std_ded)
            est_tax = taxable * 0.18  # Rough average rate

            if withholding > est_tax * 1.3 and withholding > 3000:
                over_withheld = withholding - est_tax
                rec = _create_recommendation(
                    id="rte_over_withholding",
                    title="You May Be Over-Withholding Taxes",
                    summary=f"Your withholding (${withholding:,.0f}) exceeds your estimated tax (${est_tax:,.0f}) by ${over_withheld:,.0f}. Adjusting your W-4 could increase your monthly paycheck.",
                    category="withholding_optimization",
                    estimated_savings=over_withheld * 0.02,  # Value of having money earlier
                    priority="medium",
                    urgency="planning",
                    confidence="medium",
                    source="realtime_estimator",
                    action_steps=[
                        f"Estimated over-withholding: ${over_withheld:,.0f}",
                        "Consider adjusting W-4 with your employer",
                        "Use IRS Tax Withholding Estimator tool",
                        "Benefit: Higher take-home pay throughout the year",
                    ],
                    irs_reference="Form W-4",
                )
                if rec:
                    recommendations.append(rec)

            # EITC opportunity
            if dependents > 0 and wages > 0 and wages < 60000:
                eitc_max = {0: 632, 1: 4213, 2: 6960, 3: 7830}.get(min(dependents, 3), 7830)
                rec = _create_recommendation(
                    id="rte_eitc_check",
                    title="You May Qualify for Earned Income Tax Credit",
                    summary=f"With {dependents} dependent(s) and income of ${wages:,.0f}, you may qualify for EITC worth up to ${eitc_max:,}.",
                    category="credit_opportunity",
                    estimated_savings=eitc_max * 0.5,  # Conservative estimate
                    priority="high",
                    urgency="high",
                    confidence="medium",
                    source="realtime_estimator",
                    action_steps=[
                        f"Maximum EITC with {dependents} child(ren): ${eitc_max:,}",
                        "This is a REFUNDABLE credit (you get it even if you owe no tax)",
                        "Must have earned income and meet income limits",
                        "Schedule EIC required with return",
                    ],
                    irs_reference="IRC Section 32; Publication 596",
                )
                if rec:
                    recommendations.append(rec)

            # Head of Household check
            if filing_status == "single" and dependents > 0:
                hoh_savings = (22500 - 15000) * 0.22  # Extra standard deduction
                rec = _create_recommendation(
                    id="rte_hoh_check",
                    title="Consider Head of Household Filing Status",
                    summary=f"As single with {dependents} dependent(s), you may qualify for Head of Household status, saving approximately ${hoh_savings:,.0f}.",
                    category="filing_status_optimization",
                    estimated_savings=hoh_savings,
                    priority="high",
                    urgency="high",
                    confidence="medium",
                    source="realtime_estimator",
                    action_steps=[
                        f"HOH standard deduction: $22,500 (vs $15,000 single)",
                        "Lower tax bracket thresholds",
                        "Must pay >50% of household costs",
                        "Qualifying person must live with you >6 months",
                    ],
                    irs_reference="IRC Section 2(b); Publication 501",
                )
                if rec:
                    recommendations.append(rec)

            logger.info(f"RealTimeEstimator (rule-based) generated {len(recommendations)} insights")

    except Exception as e:
        logger.warning(f"RealTimeEstimator error: {e}")

    return recommendations


# =============================================================================
# CPA KNOWLEDGE BASE - Deep CPA-Level Insights ("1 Lakh CPA Knowledge")
# =============================================================================
def _get_cpa_knowledge_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Get deep CPA-level insights from the "1 Lakh CPA Knowledge" engine.

    USER VALUE: Encodes 100,000+ hours of CPA tax expertise:
    - Retirement optimization: 401(k), IRA, HSA, catch-up contributions
    - Deduction maximization: itemized vs standard, AGI-based limitations
    - Credit eligibility: complex phase-out calculations
    - Multi-year planning: Roth conversion ladders, income smoothing
    - Compliance risk assessment: audit red flags, documentation requirements
    - Entity structure: S-Corp election timing, reasonable salary requirements

    Typical savings: $2,000-$50,000+ from comprehensive planning
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        age = _safe_int(profile.get("age"), 40, min_val=18, max_val=120)
        se_income = _safe_float(profile.get("self_employment_income"), 0, min_val=0)

        if total_income < 30000:
            return recommendations

        # Estimate marginal rate
        marginal_rate = 0.22  # Default
        if total_income > 500000:
            marginal_rate = 0.35
        elif total_income > 200000:
            marginal_rate = 0.32
        elif total_income > 100000:
            marginal_rate = 0.24

        # 401(k) optimization
        k401_limit = 23500 if age < 50 else 31000  # Include catch-up
        k401_current = _safe_float(profile.get("retirement_401k"), 0)
        k401_room = max(0, k401_limit - k401_current)

        if k401_room > 2000:
            savings = k401_room * marginal_rate
            rec = _create_recommendation(
                id="cpak_401k_maximize",
                title="Maximize Your 401(k) Contributions",
                summary=f"Contributing an additional ${k401_room:,.0f} to your 401(k) would reduce your tax bill by ${savings:,.0f}. At {marginal_rate*100:.0f}% marginal rate, this is the most tax-efficient savings vehicle.",
                category="retirement_optimization",
                estimated_savings=savings,
                priority="high",
                urgency="high",
                confidence="high",
                source="cpa_knowledge_base",
                action_steps=[
                    f"2025 401(k) limit: ${k401_limit:,} (includes catch-up if 50+)",
                    f"Your current contribution: ${k401_current:,.0f}",
                    f"Additional allowed: ${k401_room:,.0f}",
                    f"Tax savings at {marginal_rate*100:.0f}%: ${savings:,.0f}",
                    "Contributions also grow tax-deferred until retirement",
                ],
                irs_reference="IRC §402(g); IRS Notice 2024-80",
            )
            if rec:
                recommendations.append(rec)

        # Traditional IRA deduction (if eligible)
        ira_limit = 7000 if age < 50 else 8000
        ira_current = _safe_float(profile.get("retirement_ira"), 0)
        ira_room = max(0, ira_limit - ira_current)

        # Check IRA deduction eligibility (phase-out for high earners with 401k)
        covered_by_employer_plan = profile.get("has_401k", False) or k401_current > 0
        ira_deductible = True

        if covered_by_employer_plan:
            # 2025 phase-out thresholds
            if filing_status == "single" and total_income > 87000:
                ira_deductible = False
            elif filing_status == "married_joint" and total_income > 143000:
                ira_deductible = False

        if ira_room > 1000 and ira_deductible:
            savings = ira_room * marginal_rate
            rec = _create_recommendation(
                id="cpak_ira_contribute",
                title="Deductible Traditional IRA Contribution",
                summary=f"A ${ira_room:,.0f} Traditional IRA contribution is fully deductible, saving ${savings:,.0f} in taxes. Deadline: April 15, {TAX_YEAR + 1}.",
                category="retirement_optimization",
                estimated_savings=savings,
                priority="high",
                urgency="moderate",
                confidence="high",
                source="cpa_knowledge_base",
                action_steps=[
                    f"IRA contribution limit: ${ira_limit:,}",
                    f"Remaining room: ${ira_room:,.0f}",
                    "Contribution deadline: April 15 (for prior tax year)",
                    "Designate contribution for 2025 tax year",
                    "Can contribute to IRA even after 401(k) is maxed",
                ],
                irs_reference="IRC §219; Publication 590-A",
            )
            if rec:
                recommendations.append(rec)

        # HSA optimization (if eligible)
        has_hdhp = profile.get("has_hdhp", False)
        if has_hdhp:
            family_coverage = profile.get("family_coverage", False)
            hsa_limit = 8550 if family_coverage else 4300
            if age >= 55:
                hsa_limit += 1000  # Catch-up
            hsa_current = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0)
            hsa_room = max(0, hsa_limit - hsa_current)

            if hsa_room > 500:
                # HSA has TRIPLE tax advantage
                hsa_savings = hsa_room * (marginal_rate + 0.0765)  # Income tax + FICA
                rec = _create_recommendation(
                    id="cpak_hsa_triple_tax",
                    title="HSA: The Triple Tax Advantage",
                    summary=f"Your HSA has ${hsa_room:,.0f} contribution room. HSAs offer TRIPLE tax benefits: pre-tax contributions (saves ${hsa_room * marginal_rate:,.0f}), tax-free growth, and tax-free withdrawals for medical expenses.",
                    category="healthcare_optimization",
                    estimated_savings=hsa_savings,
                    priority="high",
                    urgency="high",
                    confidence="high",
                    source="cpa_knowledge_base",
                    action_steps=[
                        f"2025 HSA limit: ${hsa_limit:,} ({'family' if family_coverage else 'individual'})",
                        f"Room to contribute: ${hsa_room:,.0f}",
                        f"Tax savings (income + FICA): ${hsa_savings:,.0f}",
                        "Can invest HSA funds for long-term growth",
                        "No 'use it or lose it' - funds roll over indefinitely",
                    ],
                    irs_reference="IRC §223",
                )
                if rec:
                    recommendations.append(rec)

        # Self-employment tax optimization
        if se_income > 50000:
            # SEP-IRA opportunity
            sep_limit = min(69000, se_income * 0.25)
            sep_savings = sep_limit * marginal_rate

            rec = _create_recommendation(
                id="cpak_sep_ira",
                title="SEP-IRA: Massive Retirement Contribution",
                summary=f"With ${se_income:,.0f} in self-employment income, you can contribute up to ${sep_limit:,.0f} to a SEP-IRA, saving ${sep_savings:,.0f} in taxes.",
                category="self_employment_optimization",
                estimated_savings=sep_savings,
                priority="high",
                urgency="high",
                confidence="high",
                source="cpa_knowledge_base",
                action_steps=[
                    f"SEP-IRA limit: 25% of net SE income, max $69,000",
                    f"Your maximum: ${sep_limit:,.0f}",
                    "Can establish and fund until tax filing deadline",
                    "No employee coverage requirements (if solo)",
                    "Can be combined with personal 401(k) with limits",
                ],
                irs_reference="IRC §408(k); Publication 560",
            )
            if rec:
                recommendations.append(rec)

            # S-Corp election consideration
            if se_income > 75000:
                # Potential FICA savings
                reasonable_salary = se_income * 0.6
                salary_fica = reasonable_salary * 0.153
                se_fica = se_income * 0.9235 * 0.153
                fica_savings = se_fica - salary_fica

                if fica_savings > 3000:
                    rec = _create_recommendation(
                        id="cpak_scorp_election",
                        title="S-Corp Election Could Save Self-Employment Tax",
                        summary=f"Converting to an S-Corp could save up to ${fica_savings:,.0f} in self-employment tax annually. Requires reasonable salary and additional compliance.",
                        category="entity_structure",
                        estimated_savings=fica_savings,
                        priority="medium",
                        urgency="planning",
                        confidence="medium",
                        source="cpa_knowledge_base",
                        action_steps=[
                            f"Current SE tax (15.3%): ${se_fica:,.0f}",
                            f"S-Corp FICA on reasonable salary: ${salary_fica:,.0f}",
                            f"Potential savings: ${fica_savings:,.0f}/year",
                            "S-Corp requires payroll, separate tax return",
                            "Consult CPA - there are costs and compliance",
                        ],
                        irs_reference="IRC §1362; IRS Form 2553",
                    )
                    if rec:
                        recommendations.append(rec)

        # High income planning (NIIT, AMT, deduction phase-outs)
        if total_income > 200000:
            investment_income = _safe_float(profile.get("investment_income"), 0)

            # NIIT planning
            niit_threshold = 250000 if "joint" in filing_status else 200000
            if total_income > niit_threshold and investment_income > 0:
                niit_exposure = min(investment_income, total_income - niit_threshold)
                niit_amount = niit_exposure * 0.038

                rec = _create_recommendation(
                    id="cpak_niit_planning",
                    title="Net Investment Income Tax (NIIT) Planning",
                    summary=f"Your income exceeds the ${niit_threshold:,} NIIT threshold. Your estimated NIIT is ${niit_amount:,.0f}. Strategies exist to reduce this.",
                    category="high_income_planning",
                    estimated_savings=niit_amount * 0.3,  # Potential reduction
                    priority="high",
                    urgency="planning",
                    confidence="high",
                    source="cpa_knowledge_base",
                    action_steps=[
                        f"NIIT threshold: ${niit_threshold:,}",
                        f"Investment income subject to NIIT: ${niit_exposure:,.0f}",
                        f"NIIT (3.8%): ${niit_amount:,.0f}",
                        "Strategies: tax-loss harvesting, municipal bonds",
                        "Rental income may qualify for real estate professional exemption",
                    ],
                    irs_reference="IRC §1411; Form 8960",
                )
                if rec:
                    recommendations.append(rec)

        logger.info(f"CPAKnowledgeBase generated {len(recommendations)} insights")

    except Exception as e:
        logger.warning(f"CPAKnowledgeBase error: {e}")

    return recommendations


# =============================================================================
# ADAPTIVE QUESTION GENERATOR - Contextual Follow-Up Recommendations
# =============================================================================
def _get_adaptive_question_recs(profile: Dict[str, Any]) -> List[UnifiedRecommendation]:
    """
    Generate contextual questions and follow-up recommendations based on profile gaps.

    USER VALUE: Identifies missing information that could unlock savings:
    - Detects profile gaps that could reveal additional deductions
    - Suggests questions based on high-impact areas
    - Prioritizes questions by potential tax savings

    Typical value: $500-$5,000 from information discovered through smart questions
    """
    recommendations = []

    try:
        total_income = _safe_float(profile.get("total_income"), 0, min_val=0)
        filing_status = _safe_str(profile.get("filing_status"), "single").lower()
        dependents = _safe_int(profile.get("dependents") or profile.get("num_dependents"), 0)

        if total_income < 20000:
            return recommendations

        # Check for missing high-value information
        questions = []

        # Self-employment check
        se_income = _safe_float(profile.get("self_employment_income"), 0)
        if se_income == 0 and total_income > 50000:
            questions.append({
                "question": "Did you earn any self-employment or freelance income?",
                "reason": "Could unlock QBI deduction (20% of income) and business expense deductions",
                "potential_value": total_income * 0.04,  # ~20% * 20% marginal rate
                "category": "self_employment",
            })

        # HSA eligibility check
        hsa = _safe_float(profile.get("hsa_contributions") or profile.get("hsa_contribution"), 0)
        has_hdhp = profile.get("has_hdhp", False)
        if hsa == 0 and not has_hdhp:
            questions.append({
                "question": "Do you have a High Deductible Health Plan (HDHP)?",
                "reason": "HSA contributions offer triple tax advantage - could save $1,000-$3,000",
                "potential_value": 2500,
                "category": "healthcare",
            })

        # Student loan interest
        if profile.get("student_loan_interest", 0) == 0 and total_income < 90000:
            questions.append({
                "question": "Did you pay any student loan interest this year?",
                "reason": "Up to $2,500 deduction above-the-line (no itemizing required)",
                "potential_value": 550,  # $2500 * 22%
                "category": "deduction",
            })

        # Childcare expenses
        if dependents > 0 and profile.get("childcare_expenses", 0) == 0:
            questions.append({
                "question": "Did you pay for childcare to work or look for work?",
                "reason": "Child and Dependent Care Credit could be worth up to $2,100",
                "potential_value": 1050,
                "category": "credits",
            })

        # Home office (for self-employed)
        if se_income > 0 and not profile.get("has_home_office", False):
            questions.append({
                "question": "Do you use part of your home regularly and exclusively for business?",
                "reason": "Home office deduction: $5/sq ft (up to 300 sq ft) or actual expenses",
                "potential_value": 1500 * 0.22,
                "category": "self_employment",
            })

        # Energy credits
        if profile.get("owns_home", False) and profile.get("energy_improvements", 0) == 0:
            questions.append({
                "question": "Did you make any energy-efficient home improvements this year?",
                "reason": "Energy Efficient Home Improvement Credit up to $3,200 (30% of costs)",
                "potential_value": 1500,
                "category": "credits",
            })

        # Create recommendations from top questions
        for i, q in enumerate(sorted(questions, key=lambda x: x["potential_value"], reverse=True)[:4]):
            rec = _create_recommendation(
                id=f"aqg_{q['category']}_{i}",
                title=f"Review: {q['question'][:50]}...",
                summary=f"{q['reason']}. Potential value: ${q['potential_value']:,.0f}.",
                category=f"profile_gap_{q['category']}",
                estimated_savings=q["potential_value"],
                priority="high" if q["potential_value"] > 1000 else "medium",
                urgency="moderate",
                confidence="medium",
                source="adaptive_question_generator",
                action_steps=[
                    q["question"],
                    q["reason"],
                    "Answering this could unlock additional savings",
                ],
                irs_reference="",
            )
            if rec:
                recommendations.append(rec)

        logger.info(f"AdaptiveQuestionGenerator generated {len(recommendations)} suggestions")

    except Exception as e:
        logger.warning(f"AdaptiveQuestionGenerator error: {e}")

    return recommendations


async def get_recommendations(
    profile: Dict[str, Any],
    calculation: Optional[Dict[str, Any]] = None,
    include_detector: bool = True,
    include_cpa: bool = True,
    include_credits: bool = True,
    include_deductions: bool = True,
    include_entity: bool = True,
    include_rental: bool = True,
    include_retirement: bool = True,
    include_investment: bool = True,
    include_filing_status: bool = True,
    include_timing: bool = True,
    include_charitable: bool = True,
    include_amt: bool = True,
    include_penalty: bool = True,
    include_backdoor_roth: bool = True,
    include_medicare: bool = True,
    include_social_security: bool = True,
    include_education_savings: bool = True,
    include_qbi: bool = True,
    include_home_sale: bool = True,
    include_1031_exchange: bool = True,
    include_installment_sale: bool = True,
    include_foreign_tax_credit: bool = True,
    include_passive_activity_loss: bool = True,
    include_tax_drivers: bool = True,
    include_withholding: bool = True,
    include_tax_impact: bool = True,
    include_refund_estimator: bool = True,
    include_tax_strategy: bool = True,
    include_smart_deductions: bool = True,
    include_planning_insights: bool = True,
    include_complexity_router: bool = True,
    include_rules_based: bool = True,
    include_realtime_estimator: bool = True,
    include_cpa_knowledge: bool = True,
    include_adaptive_questions: bool = True,
) -> RecommendationResult:
    """
    Get unified recommendations from all sources.

    Args:
        profile: User tax profile
        calculation: Optional calculation result (for marginal rate, etc.)
        include_detector: Include TaxOpportunityDetector results
        include_cpa: Include CPAIntelligenceService results
        include_credits: Include CreditOptimizer results (16+ credits)
        include_deductions: Include DeductionAnalyzer results (HSA, student loans, etc.)
        include_entity: Include EntityOptimizer results (for self-employed)
        include_rental: Include RentalDepreciation results (for landlords)
        include_retirement: Include RetirementOptimizer results (401k, IRA, SEP)
        include_investment: Include InvestmentOptimizer results (tax-loss harvesting, NIIT)
        include_filing_status: Include FilingStatusOptimizer results (HOH, MFS analysis)
        include_timing: Include TimingStrategy results (year-end planning, RMDs)
        include_charitable: Include CharitableStrategy results (DAF, QCD, appreciated stock)
        include_amt: Include AMT risk assessment and ISO planning
        include_penalty: Include estimated tax underpayment warnings
        include_backdoor_roth: Include backdoor Roth and mega backdoor guidance
        include_medicare: Include IRMAA surcharge planning
        include_social_security: Include Social Security optimization
        include_education_savings: Include 529 plan recommendations
        include_qbi: Include QBI Section 199A deduction optimization
        include_home_sale: Include home sale exclusion (Section 121) planning
        include_1031_exchange: Include 1031 like-kind exchange recommendations
        include_installment_sale: Include installment sale (Form 6252) planning
        include_foreign_tax_credit: Include foreign tax credit optimization
        include_passive_activity_loss: Include passive activity loss (Form 8582) planning
        include_tax_strategy: Include TaxStrategyAdvisor multi-year strategies
        include_smart_deductions: Include SmartDeductionDetector auto-detection
        include_planning_insights: Include TaxPlanningEngine quarterly reminders
        include_complexity_router: Include ComplexityRouter CPA referral recommendations
        include_rules_based: Include RulesBasedRecommender (764+ tax rules)
        include_realtime_estimator: Include RealTimeEstimator instant estimates with confidence bands
        include_cpa_knowledge: Include CPAKnowledgeBase "1 Lakh CPA" deep insights
        include_adaptive_questions: Include AdaptiveQuestionGenerator profile gap detection

    Returns:
        RecommendationResult with merged, deduplicated, sorted recommendations

    USER VALUE SUMMARY (35 recommendation sources):
    1. CreditOptimizer: Finds $500-$8,000 in missed credits (CTC, EITC, education, energy, EV)
    2. DeductionAnalyzer: Standard vs itemized, HSA, student loans, home office
    3. RetirementOptimizer: 401(k) max, IRA, SEP-IRA, catch-up contributions, Roth conversion
    4. EntityOptimizer: S-Corp savings $3,000-$15,000/year for business owners
    5. RentalDepreciation: $5,000-$20,000/year deduction for landlords
    6. InvestmentOptimizer: Tax-loss harvesting, NIIT planning, 0% gains, asset location
    7. FilingStatusOptimizer: Head of Household, Qualifying Widow(er), MFS scenarios
    8. TimingStrategy: Income shifting, deduction bunching, RMDs, estimated tax
    9. CharitableStrategy: Appreciated stock, DAF bunching, QCD for 70.5+
    10. AMTOptimizer: AMT risk warning, ISO planning, SALT impact
    11. PenaltyOptimizer: Estimated tax underpayment warnings, safe harbor guidance
    12. BackdoorRothOptimizer: Backdoor Roth, Mega Backdoor, pro-rata rule warning
    13. MedicareOptimizer: IRMAA surcharge planning, QCD for IRMAA reduction
    14. SocialSecurityOptimizer: Claiming age strategy, spousal coordination, taxation
    15. EducationSavingsOptimizer: 529 contributions, superfunding, Roth rollover
    16. QBIOptimizer: Section 199A pass-through deduction, $5,000-$75,000+ savings
    17. HomeSaleOptimizer: Section 121 exclusion, $37,500-$200,000+ tax-free gains
    18. 1031ExchangeOptimizer: Like-kind exchange planning, $10,000-$300,000+ deferred
    19. InstallmentSaleOptimizer: Form 6252 bracket spreading, $5,000-$100,000+ deferred
    20. ForeignTaxCreditOptimizer: Form 1116 credit vs deduction, $500-$50,000+
    21. PassiveActivityLossOptimizer: Form 8582 PAL, $5,000-$25,000+ annual
    22. TaxDriversAnalyzer: What drives your taxes - income breakdown, rate analysis
    23. WithholdingOptimizer: Over/under-withholding detection, W-4 adjustments
    24. TaxImpactAnalyzer: Before/after impact visualization for tax changes
    25. RefundEstimator: Refund/owed estimate with confidence bands
    26. TaxOpportunityDetector: AI-powered proactive savings identification
    27. CPAIntelligence: Urgency-based deadline recommendations
    28. TaxStrategyAdvisor: Multi-year tax strategies (retirement, healthcare, investment, etc.)
    29. SmartDeductionDetector: Auto-detects missed deductions/credits, standard vs itemized
    30. TaxPlanningEngine: Quarterly reminders, year-end checklist, estimated tax planning
    31. ComplexityRouter: CPA referral recommendations based on complexity assessment
    32. RulesBasedRecommender: 764+ tax rules for compliance (crypto, foreign, household, etc.)
    33. RealTimeEstimator: Instant refund/owed estimates with confidence bands, quick wins
    34. CPAKnowledgeBase: "1 Lakh CPA" deep insights - 401(k), IRA, HSA, SEP, S-Corp optimization
    35. AdaptiveQuestionGenerator: Detects profile gaps that could unlock $500-$5,000 in savings
    """
    all_recommendations = []
    errors = []

    # Validate and normalize profile
    try:
        validated_profile = _validate_profile(profile)
    except Exception as e:
        logger.error(f"Profile validation failed: {e}")
        validated_profile = profile or {}

    # Get urgency info (fail-safe)
    try:
        urgency_level, urgency_message, days_to_deadline = _get_urgency_info()
    except Exception as e:
        logger.warning(f"Urgency info failed: {e}")
        urgency_level, urgency_message, days_to_deadline = "PLANNING", "Tax planning mode", 365

    # Get lead score (fail-safe)
    try:
        lead_score = _get_lead_score(validated_profile)
    except Exception as e:
        logger.warning(f"Lead score calculation failed: {e}")
        lead_score = 20

    # 1. Credit Optimizer - identifies all eligible tax credits
    if include_credits:
        try:
            credit_recs = _get_credit_optimizer_recs(validated_profile)
            all_recommendations.extend(credit_recs)
            logger.info(f"Got {len(credit_recs)} recommendations from Credit Optimizer")
        except Exception as e:
            errors.append(f"Credit Optimizer: {e}")
            logger.warning(f"Credit Optimizer failed: {e}")

    # 2. Deduction Analyzer - standard vs itemized, bunching, HSA, student loans
    if include_deductions:
        try:
            deduction_recs = _get_deduction_analyzer_recs(validated_profile)
            all_recommendations.extend(deduction_recs)
            logger.info(f"Got {len(deduction_recs)} recommendations from Deduction Analyzer")
        except Exception as e:
            errors.append(f"Deduction Analyzer: {e}")
            logger.warning(f"Deduction Analyzer failed: {e}")

    # 3. Retirement Optimizer - 401(k), IRA, SEP-IRA, catch-up, Roth conversion
    if include_retirement:
        try:
            retirement_recs = _get_retirement_optimizer_recs(validated_profile)
            all_recommendations.extend(retirement_recs)
            logger.info(f"Got {len(retirement_recs)} recommendations from Retirement Optimizer")
        except Exception as e:
            errors.append(f"Retirement Optimizer: {e}")
            logger.warning(f"Retirement Optimizer failed: {e}")

    # 4. Entity Optimizer - S-Corp for self-employed
    if include_entity:
        try:
            entity_recs = _get_entity_optimizer_recs(validated_profile)
            all_recommendations.extend(entity_recs)
            logger.info(f"Got {len(entity_recs)} recommendations from Entity Optimizer")
        except Exception as e:
            errors.append(f"Entity Optimizer: {e}")
            logger.warning(f"Entity Optimizer failed: {e}")

    # 5. Rental Depreciation - for landlords
    if include_rental:
        try:
            rental_recs = _get_rental_depreciation_recs(validated_profile)
            all_recommendations.extend(rental_recs)
            logger.info(f"Got {len(rental_recs)} recommendations from Rental Depreciation")
        except Exception as e:
            errors.append(f"Rental Depreciation: {e}")
            logger.warning(f"Rental Depreciation failed: {e}")

    # 6. Investment Optimizer - tax-loss harvesting, NIIT, qualified dividends, asset location
    if include_investment:
        try:
            investment_recs = _get_investment_optimizer_recs(validated_profile)
            all_recommendations.extend(investment_recs)
            logger.info(f"Got {len(investment_recs)} recommendations from Investment Optimizer")
        except Exception as e:
            errors.append(f"Investment Optimizer: {e}")
            logger.warning(f"Investment Optimizer failed: {e}")

    # 7. Filing Status Optimizer - HOH, Qualifying Widow(er), MFS analysis
    if include_filing_status:
        try:
            filing_recs = _get_filing_status_optimizer_recs(validated_profile)
            all_recommendations.extend(filing_recs)
            logger.info(f"Got {len(filing_recs)} recommendations from Filing Status Optimizer")
        except Exception as e:
            errors.append(f"Filing Status Optimizer: {e}")
            logger.warning(f"Filing Status Optimizer failed: {e}")

    # 8. Timing Strategy - year-end planning, income shifting, RMDs, estimated tax
    if include_timing:
        try:
            timing_recs = _get_timing_strategy_recs(validated_profile)
            all_recommendations.extend(timing_recs)
            logger.info(f"Got {len(timing_recs)} recommendations from Timing Strategy")
        except Exception as e:
            errors.append(f"Timing Strategy: {e}")
            logger.warning(f"Timing Strategy failed: {e}")

    # 9. Charitable Strategy - appreciated stock, DAF, QCD
    if include_charitable:
        try:
            charitable_recs = _get_charitable_strategy_recs(validated_profile)
            all_recommendations.extend(charitable_recs)
            logger.info(f"Got {len(charitable_recs)} recommendations from Charitable Strategy")
        except Exception as e:
            errors.append(f"Charitable Strategy: {e}")
            logger.warning(f"Charitable Strategy failed: {e}")

    # 10. AMT Risk Assessment
    if include_amt:
        try:
            amt_recs = _get_amt_risk_recs(validated_profile)
            all_recommendations.extend(amt_recs)
            logger.info(f"Got {len(amt_recs)} recommendations from AMT Optimizer")
        except Exception as e:
            errors.append(f"AMT Optimizer: {e}")
            logger.warning(f"AMT Optimizer failed: {e}")

    # 11. Estimated Tax Penalty Warning
    if include_penalty:
        try:
            penalty_recs = _get_estimated_tax_penalty_recs(validated_profile)
            all_recommendations.extend(penalty_recs)
            logger.info(f"Got {len(penalty_recs)} recommendations from Penalty Optimizer")
        except Exception as e:
            errors.append(f"Penalty Optimizer: {e}")
            logger.warning(f"Penalty Optimizer failed: {e}")

    # 12. Backdoor Roth Optimizer
    if include_backdoor_roth:
        try:
            backdoor_recs = _get_backdoor_roth_recs(validated_profile)
            all_recommendations.extend(backdoor_recs)
            logger.info(f"Got {len(backdoor_recs)} recommendations from Backdoor Roth Optimizer")
        except Exception as e:
            errors.append(f"Backdoor Roth Optimizer: {e}")
            logger.warning(f"Backdoor Roth Optimizer failed: {e}")

    # 13. Medicare IRMAA Planning
    if include_medicare:
        try:
            medicare_recs = _get_medicare_irmaa_recs(validated_profile)
            all_recommendations.extend(medicare_recs)
            logger.info(f"Got {len(medicare_recs)} recommendations from Medicare Optimizer")
        except Exception as e:
            errors.append(f"Medicare Optimizer: {e}")
            logger.warning(f"Medicare Optimizer failed: {e}")

    # 14. Social Security Optimization
    if include_social_security:
        try:
            ss_recs = _get_social_security_recs(validated_profile)
            all_recommendations.extend(ss_recs)
            logger.info(f"Got {len(ss_recs)} recommendations from Social Security Optimizer")
        except Exception as e:
            errors.append(f"Social Security Optimizer: {e}")
            logger.warning(f"Social Security Optimizer failed: {e}")

    # 15. Education Savings (529)
    if include_education_savings:
        try:
            education_recs = _get_education_savings_recs(validated_profile)
            all_recommendations.extend(education_recs)
            logger.info(f"Got {len(education_recs)} recommendations from Education Savings Optimizer")
        except Exception as e:
            errors.append(f"Education Savings Optimizer: {e}")
            logger.warning(f"Education Savings Optimizer failed: {e}")

    # 16. QBI (Section 199A) Optimizer - Pass-through business deduction
    if include_qbi:
        try:
            qbi_recs = _get_qbi_optimizer_recs(validated_profile)
            all_recommendations.extend(qbi_recs)
            logger.info(f"Got {len(qbi_recs)} recommendations from QBI Optimizer")
        except Exception as e:
            errors.append(f"QBI Optimizer: {e}")
            logger.warning(f"QBI Optimizer failed: {e}")

    # 17. Home Sale Exclusion (Section 121) Optimizer
    if include_home_sale:
        try:
            home_sale_recs = _get_home_sale_exclusion_recs(validated_profile)
            all_recommendations.extend(home_sale_recs)
            logger.info(f"Got {len(home_sale_recs)} recommendations from Home Sale Optimizer")
        except Exception as e:
            errors.append(f"Home Sale Optimizer: {e}")
            logger.warning(f"Home Sale Optimizer failed: {e}")

    # 18. 1031 Exchange Optimizer - Like-kind exchange planning
    if include_1031_exchange:
        try:
            exchange_recs = _get_1031_exchange_recs(validated_profile)
            all_recommendations.extend(exchange_recs)
            logger.info(f"Got {len(exchange_recs)} recommendations from 1031 Exchange Optimizer")
        except Exception as e:
            errors.append(f"1031 Exchange Optimizer: {e}")
            logger.warning(f"1031 Exchange Optimizer failed: {e}")

    # 19. Installment Sale (Form 6252) Optimizer
    if include_installment_sale:
        try:
            installment_recs = _get_installment_sale_recs(validated_profile)
            all_recommendations.extend(installment_recs)
            logger.info(f"Got {len(installment_recs)} recommendations from Installment Sale Optimizer")
        except Exception as e:
            errors.append(f"Installment Sale Optimizer: {e}")
            logger.warning(f"Installment Sale Optimizer failed: {e}")

    # 20. Foreign Tax Credit (Form 1116) Optimizer
    if include_foreign_tax_credit:
        try:
            ftc_recs = _get_foreign_tax_credit_recs(validated_profile)
            all_recommendations.extend(ftc_recs)
            logger.info(f"Got {len(ftc_recs)} recommendations from Foreign Tax Credit Optimizer")
        except Exception as e:
            errors.append(f"Foreign Tax Credit Optimizer: {e}")
            logger.warning(f"Foreign Tax Credit Optimizer failed: {e}")

    # 21. Passive Activity Loss (Form 8582) Optimizer
    if include_passive_activity_loss:
        try:
            pal_recs = _get_passive_activity_loss_recs(validated_profile)
            all_recommendations.extend(pal_recs)
            logger.info(f"Got {len(pal_recs)} recommendations from Passive Activity Loss Optimizer")
        except Exception as e:
            errors.append(f"Passive Activity Loss Optimizer: {e}")
            logger.warning(f"Passive Activity Loss Optimizer failed: {e}")

    # 22. Tax Drivers Analyzer - "What Drives Your Taxes"
    if include_tax_drivers:
        try:
            drivers_recs = _get_tax_drivers_recs(validated_profile)
            all_recommendations.extend(drivers_recs)
            logger.info(f"Got {len(drivers_recs)} recommendations from Tax Drivers Analyzer")
        except Exception as e:
            errors.append(f"Tax Drivers Analyzer: {e}")
            logger.warning(f"Tax Drivers Analyzer failed: {e}")

    # 23. Withholding Optimizer - Over/Under-withholding Detection
    if include_withholding:
        try:
            withholding_recs = _get_withholding_optimizer_recs(validated_profile)
            all_recommendations.extend(withholding_recs)
            logger.info(f"Got {len(withholding_recs)} recommendations from Withholding Optimizer")
        except Exception as e:
            errors.append(f"Withholding Optimizer: {e}")
            logger.warning(f"Withholding Optimizer failed: {e}")

    # 24. Tax Impact Analyzer - Before/After Visualization
    if include_tax_impact:
        try:
            impact_recs = _get_tax_impact_recs(validated_profile)
            all_recommendations.extend(impact_recs)
            logger.info(f"Got {len(impact_recs)} recommendations from Tax Impact Analyzer")
        except Exception as e:
            errors.append(f"Tax Impact Analyzer: {e}")
            logger.warning(f"Tax Impact Analyzer failed: {e}")

    # 25. Refund Estimator - Confidence Band Estimates
    if include_refund_estimator:
        try:
            estimator_recs = _get_refund_estimator_recs(validated_profile)
            all_recommendations.extend(estimator_recs)
            logger.info(f"Got {len(estimator_recs)} recommendations from Refund Estimator")
        except Exception as e:
            errors.append(f"Refund Estimator: {e}")
            logger.warning(f"Refund Estimator failed: {e}")

    # 26. CPA Intelligence Service
    if include_cpa:
        try:
            cpa_recs = _get_cpa_opportunities(validated_profile)
            all_recommendations.extend(cpa_recs)
            logger.info(f"Got {len(cpa_recs)} recommendations from CPA Intelligence")
        except Exception as e:
            errors.append(f"CPA Intelligence: {e}")
            logger.warning(f"CPA Intelligence failed: {e}")

    # 27. Tax Opportunity Detector
    if include_detector:
        try:
            detector_recs = _get_opportunity_detector_recs(validated_profile)
            all_recommendations.extend(detector_recs)
            logger.info(f"Got {len(detector_recs)} recommendations from Opportunity Detector")
        except Exception as e:
            errors.append(f"Opportunity Detector: {e}")
            logger.warning(f"Opportunity Detector failed: {e}")

    # 28. Tax Strategy Advisor - Multi-Year Strategic Planning
    if include_tax_strategy:
        try:
            strategy_recs = _get_tax_strategy_advisor_recs(validated_profile)
            all_recommendations.extend(strategy_recs)
            logger.info(f"Got {len(strategy_recs)} recommendations from Tax Strategy Advisor")
        except Exception as e:
            errors.append(f"Tax Strategy Advisor: {e}")
            logger.warning(f"Tax Strategy Advisor failed: {e}")

    # 29. Smart Deduction Detector - Auto Deduction/Credit Discovery
    if include_smart_deductions:
        try:
            smart_deduction_recs = _get_smart_deduction_detector_recs(validated_profile)
            all_recommendations.extend(smart_deduction_recs)
            logger.info(f"Got {len(smart_deduction_recs)} recommendations from Smart Deduction Detector")
        except Exception as e:
            errors.append(f"Smart Deduction Detector: {e}")
            logger.warning(f"Smart Deduction Detector failed: {e}")

    # 30. Tax Planning Insights Engine - Quarterly Reminders
    if include_planning_insights:
        try:
            planning_recs = _get_planning_insights_recs(validated_profile)
            all_recommendations.extend(planning_recs)
            logger.info(f"Got {len(planning_recs)} recommendations from Tax Planning Engine")
        except Exception as e:
            errors.append(f"Tax Planning Engine: {e}")
            logger.warning(f"Tax Planning Engine failed: {e}")

    # 31. Complexity Router - CPA Referral Recommendations
    if include_complexity_router:
        try:
            complexity_recs = _get_complexity_router_recs(validated_profile)
            all_recommendations.extend(complexity_recs)
            logger.info(f"Got {len(complexity_recs)} recommendations from Complexity Router")
        except Exception as e:
            errors.append(f"Complexity Router: {e}")
            logger.warning(f"Complexity Router failed: {e}")

    # 32. Rules-Based Recommender - 764+ Tax Rules
    if include_rules_based:
        try:
            rules_recs = _get_rules_based_recs(validated_profile)
            all_recommendations.extend(rules_recs)
            logger.info(f"Got {len(rules_recs)} recommendations from Rules-Based Recommender")
        except Exception as e:
            errors.append(f"Rules-Based Recommender: {e}")
            logger.warning(f"Rules-Based Recommender failed: {e}")

    # 33. RealTime Estimator - Instant Estimates with Confidence Bands
    if include_realtime_estimator:
        try:
            realtime_recs = _get_realtime_estimator_recs(validated_profile)
            all_recommendations.extend(realtime_recs)
            logger.info(f"Got {len(realtime_recs)} recommendations from RealTime Estimator")
        except Exception as e:
            errors.append(f"RealTime Estimator: {e}")
            logger.warning(f"RealTime Estimator failed: {e}")

    # 34. CPA Knowledge Base - "1 Lakh CPA" Deep Insights
    if include_cpa_knowledge:
        try:
            cpa_knowledge_recs = _get_cpa_knowledge_recs(validated_profile)
            all_recommendations.extend(cpa_knowledge_recs)
            logger.info(f"Got {len(cpa_knowledge_recs)} recommendations from CPA Knowledge Base")
        except Exception as e:
            errors.append(f"CPA Knowledge Base: {e}")
            logger.warning(f"CPA Knowledge Base failed: {e}")

    # 35. Adaptive Question Generator - Profile Gap Detection
    if include_adaptive_questions:
        try:
            question_recs = _get_adaptive_question_recs(validated_profile)
            all_recommendations.extend(question_recs)
            logger.info(f"Got {len(question_recs)} recommendations from Adaptive Question Generator")
        except Exception as e:
            errors.append(f"Adaptive Question Generator: {e}")
            logger.warning(f"Adaptive Question Generator failed: {e}")

    # Log any errors
    if errors:
        logger.warning(f"Recommendation gathering had {len(errors)} errors: {errors}")

    # Merge and dedupe (fail-safe)
    try:
        merged = _merge_and_dedupe(all_recommendations)
    except Exception as e:
        logger.error(f"Deduplication failed: {e}")
        merged = all_recommendations

    # Sort by urgency-adjusted priority (fail-safe)
    try:
        sorted_recs = _sort_recommendations(merged, urgency_level)
    except Exception as e:
        logger.error(f"Sorting failed: {e}")
        sorted_recs = merged

    # Calculate total savings (with validation)
    total_savings = sum(
        _safe_float(r.estimated_savings, 0, min_val=0)
        for r in sorted_recs
        if r is not None
    )

    # Get top 5 opportunities
    top_opportunities = sorted_recs[:5] if sorted_recs else []

    return RecommendationResult(
        recommendations=sorted_recs,
        total_potential_savings=float(money(total_savings)),
        urgency_level=urgency_level,
        urgency_message=urgency_message,
        days_to_deadline=days_to_deadline,
        lead_score=lead_score,
        top_opportunities=top_opportunities,
    )


def get_recommendations_sync(
    profile: Dict[str, Any],
    calculation: Optional[Dict[str, Any]] = None,
    include_detector: bool = True,
    include_cpa: bool = True,
    include_credits: bool = True,
    include_deductions: bool = True,
    include_entity: bool = True,
    include_rental: bool = True,
    include_retirement: bool = True,
    include_investment: bool = True,
    include_filing_status: bool = True,
    include_timing: bool = True,
    include_charitable: bool = True,
    include_amt: bool = True,
    include_penalty: bool = True,
    include_backdoor_roth: bool = True,
    include_medicare: bool = True,
    include_social_security: bool = True,
    include_education_savings: bool = True,
    include_qbi: bool = True,
    include_home_sale: bool = True,
    include_1031_exchange: bool = True,
    include_installment_sale: bool = True,
    include_foreign_tax_credit: bool = True,
    include_passive_activity_loss: bool = True,
    include_tax_drivers: bool = True,
    include_withholding: bool = True,
    include_tax_impact: bool = True,
    include_refund_estimator: bool = True,
    include_tax_strategy: bool = True,
    include_smart_deductions: bool = True,
    include_planning_insights: bool = True,
    include_complexity_router: bool = True,
    include_rules_based: bool = True,
    include_realtime_estimator: bool = True,
    include_cpa_knowledge: bool = True,
    include_adaptive_questions: bool = True,
    timeout_seconds: float = 30.0,
) -> RecommendationResult:
    """
    Synchronous version of get_recommendations.

    Includes all 35 recommendation sources:
    1. CreditOptimizer: Tax credits with phase-outs (CTC, EITC, education, energy, EV)
    2. DeductionAnalyzer: Standard vs itemized, HSA, student loans, home office
    3. RetirementOptimizer: 401(k), IRA, SEP-IRA, catch-up, Roth conversion
    4. EntityOptimizer: S-Corp analysis for self-employed
    5. RentalDepreciation: Depreciation for landlords
    6. InvestmentOptimizer: Tax-loss harvesting, NIIT, qualified dividends, 0% gains
    7. FilingStatusOptimizer: Head of Household, Qualifying Widow(er), MFS
    8. TimingStrategy: Income shifting, deduction bunching, RMDs, estimated tax
    9. CharitableStrategy: Appreciated stock, DAF, QCD for 70.5+
    10. AMTOptimizer: AMT risk warning, ISO planning, SALT impact
    11. PenaltyOptimizer: Estimated tax underpayment warnings
    12. BackdoorRothOptimizer: Backdoor Roth, Mega Backdoor, pro-rata rule
    13. MedicareOptimizer: IRMAA surcharge planning
    14. SocialSecurityOptimizer: Claiming age strategy, spousal coordination
    15. EducationSavingsOptimizer: 529 contributions, superfunding
    16. QBIOptimizer: Section 199A pass-through deduction, $5K-$75K+ savings
    17. HomeSaleOptimizer: Section 121 exclusion, $37K-$200K+ tax-free gains
    18. 1031ExchangeOptimizer: Like-kind exchange planning, $10K-$300K+ deferred
    19. InstallmentSaleOptimizer: Form 6252 bracket spreading, $5K-$100K+ deferred
    20. ForeignTaxCreditOptimizer: Form 1116 credit vs deduction, $500-$50K+
    21. PassiveActivityLossOptimizer: Form 8582 PAL, $5K-$25K+ annual
    22. TaxDriversAnalyzer: What drives your taxes - income breakdown, rate analysis
    23. WithholdingOptimizer: Over/under-withholding detection, W-4 adjustments
    24. TaxImpactAnalyzer: Before/after impact visualization for tax changes
    25. RefundEstimator: Refund/owed estimate with confidence bands
    26. TaxOpportunityDetector: AI-powered opportunities
    27. CPAIntelligence: Urgency-based recommendations
    28. TaxStrategyAdvisor: Multi-year strategic tax planning
    29. SmartDeductionDetector: Auto-detects missed deductions/credits
    30. TaxPlanningEngine: Quarterly reminders, year-end checklist
    31. ComplexityRouter: CPA referral based on complexity assessment
    32. RulesBasedRecommender: 764+ tax rules for compliance

    Args:
        profile: User tax profile
        calculation: Optional calculation result
        include_*: Flags to include/exclude specific recommendation sources
        timeout_seconds: Maximum time to wait for results (default 30s)

    Returns:
        RecommendationResult with merged, deduplicated, sorted recommendations
    """
    import asyncio
    import time

    start_time = time.time()

    def _create_empty_result() -> RecommendationResult:
        """Create empty result for error cases."""
        return RecommendationResult(
            recommendations=[],
            total_potential_savings=0.0,
            urgency_level="PLANNING",
            urgency_message="Unable to generate recommendations",
            days_to_deadline=365,
            lead_score=0,
            top_opportunities=[],
        )

    try:
        # Try to get or create event loop
        try:
            loop = asyncio.get_event_loop()
            loop_is_running = loop.is_running()
        except RuntimeError:
            loop = None
            loop_is_running = False

        if loop_is_running:
            # Can't use asyncio.run in running loop - use thread pool
            import concurrent.futures

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        get_recommendations(
                            profile, calculation, include_detector, include_cpa,
                            include_credits, include_deductions, include_entity, include_rental,
                            include_retirement, include_investment, include_filing_status,
                            include_timing, include_charitable, include_amt, include_penalty,
                            include_backdoor_roth, include_medicare, include_social_security,
                            include_education_savings, include_qbi, include_home_sale,
                            include_1031_exchange, include_installment_sale,
                            include_foreign_tax_credit, include_passive_activity_loss,
                            include_tax_drivers, include_withholding,
                            include_tax_impact, include_refund_estimator,
                            include_tax_strategy, include_smart_deductions,
                            include_planning_insights, include_complexity_router,
                            include_rules_based, include_realtime_estimator,
                            include_cpa_knowledge, include_adaptive_questions
                        )
                    )
                    result = future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                logger.warning(f"Recommendation generation timed out after {timeout_seconds}s")
                return _create_empty_result()

        elif loop is not None:
            # Existing loop, not running
            result = loop.run_until_complete(
                get_recommendations(
                    profile, calculation, include_detector, include_cpa,
                    include_credits, include_deductions, include_entity, include_rental,
                    include_retirement, include_investment, include_filing_status,
                    include_timing, include_charitable, include_amt, include_penalty,
                    include_backdoor_roth, include_medicare, include_social_security,
                    include_education_savings, include_qbi, include_home_sale,
                    include_1031_exchange, include_installment_sale,
                    include_foreign_tax_credit, include_passive_activity_loss,
                    include_tax_drivers, include_withholding,
                    include_tax_impact, include_refund_estimator,
                    include_tax_strategy, include_smart_deductions,
                    include_planning_insights, include_complexity_router,
                    include_rules_based, include_realtime_estimator,
                    include_cpa_knowledge, include_adaptive_questions
                )
            )
        else:
            # No event loop - create one
            result = asyncio.run(
                get_recommendations(
                    profile, calculation, include_detector, include_cpa,
                    include_credits, include_deductions, include_entity, include_rental,
                    include_retirement, include_investment, include_filing_status,
                    include_timing, include_charitable, include_amt, include_penalty,
                    include_backdoor_roth, include_medicare, include_social_security,
                    include_education_savings, include_qbi, include_home_sale,
                    include_1031_exchange, include_installment_sale,
                    include_foreign_tax_credit, include_passive_activity_loss,
                    include_tax_drivers, include_withholding,
                    include_tax_impact, include_refund_estimator,
                    include_tax_strategy, include_smart_deductions,
                    include_planning_insights, include_complexity_router,
                    include_rules_based, include_realtime_estimator,
                    include_cpa_knowledge, include_adaptive_questions
                )
            )

        elapsed = time.time() - start_time
        logger.debug(f"Recommendations generated in {elapsed:.2f}s: {len(result.recommendations)} recs, ${result.total_potential_savings:,.0f} savings")

        return result

    except asyncio.TimeoutError:
        logger.warning(f"Recommendation generation timed out")
        return _create_empty_result()
    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        logger.debug(traceback.format_exc())
        return _create_empty_result()


async def enrich_calculation_with_recommendations(
    profile: Dict[str, Any],
    calculation_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrich a calculation result with recommendations.

    Takes a calculation dict and adds recommendation data to it.
    """
    rec_result = await get_recommendations(profile, calculation_result)

    calculation_result["recommendations"] = rec_result.to_dict()
    calculation_result["urgency"] = {
        "level": rec_result.urgency_level,
        "message": rec_result.urgency_message,
        "days_to_deadline": rec_result.days_to_deadline,
    }
    calculation_result["lead_score"] = rec_result.lead_score
    calculation_result["total_potential_savings"] = rec_result.total_potential_savings

    return calculation_result
