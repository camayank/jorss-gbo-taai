"""
Complexity-Based Engagement Pricing Engine

P2: Provides CPAs with pricing guidance based on client tax complexity.

CRITICAL DISCLAIMER: This platform provides advisory preparation support
for CPAs. It is NOT an e-filing service. The CPA is responsible for:
- Client engagement and pricing decisions
- Tax return preparation and review
- Filing through their chosen e-filing provider
- All professional responsibilities under Circular 230
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ComplexityTier(str, Enum):
    """Engagement complexity tiers for pricing guidance."""
    TIER_1_SIMPLE = "tier_1_simple"
    TIER_2_MODERATE = "tier_2_moderate"
    TIER_3_COMPLEX = "tier_3_complex"
    TIER_4_HIGHLY_COMPLEX = "tier_4_highly_complex"
    TIER_5_ENTERPRISE = "tier_5_enterprise"


@dataclass
class PricingGuidance:
    """Pricing guidance for a specific complexity tier."""
    tier: ComplexityTier
    tier_name: str
    description: str
    typical_forms: List[str]
    complexity_indicators: List[str]
    estimated_hours_range: tuple  # (min, max)
    suggested_price_range: tuple  # (min, max) in USD
    value_justification: List[str]


# Pricing guidance by complexity tier
# NOTE: These are practical market-rate ranges for CPA advisory services.
# Advisory preparation and consultation is our core value proposition.
PRICING_TIERS: Dict[ComplexityTier, PricingGuidance] = {
    ComplexityTier.TIER_1_SIMPLE: PricingGuidance(
        tier=ComplexityTier.TIER_1_SIMPLE,
        tier_name="Simple Individual",
        description="W-2 income only, standard deduction, minimal complexity",
        typical_forms=["1040", "W-2"],
        complexity_indicators=[
            "Single or dual W-2 income sources",
            "Standard deduction",
            "No investments or rental income",
            "No self-employment",
        ],
        estimated_hours_range=(0.75, 1.5),
        suggested_price_range=(275, 450),
        value_justification=[
            "Professional accuracy review",
            "Ensure all credits captured (EITC, education, etc.)",
            "Withholding optimization for next year",
            "Audit support if needed",
        ],
    ),
    ComplexityTier.TIER_2_MODERATE: PricingGuidance(
        tier=ComplexityTier.TIER_2_MODERATE,
        tier_name="Moderate Complexity",
        description="Multiple income sources, itemized deductions, investment income",
        typical_forms=["1040", "Schedule A", "Schedule B", "Schedule D", "8949"],
        complexity_indicators=[
            "Multiple W-2s or 1099 income",
            "Itemized deductions decision",
            "Investment income (dividends, capital gains)",
            "Retirement distributions (1099-R)",
            "Education credits or HSA",
        ],
        estimated_hours_range=(1.5, 3.0),
        suggested_price_range=(450, 850),
        value_justification=[
            "Itemized vs standard deduction optimization",
            "Investment cost basis review",
            "Tax-loss harvesting identification",
            "Retirement contribution strategy",
            "Credit eligibility maximization",
        ],
    ),
    ComplexityTier.TIER_3_COMPLEX: PricingGuidance(
        tier=ComplexityTier.TIER_3_COMPLEX,
        tier_name="Complex - Business/Rental",
        description="Self-employment, rental properties, K-1 pass-through income",
        typical_forms=[
            "1040", "Schedule C", "Schedule E", "Schedule SE",
            "K-1", "4562", "8829", "8995"
        ],
        complexity_indicators=[
            "Self-employment income",
            "Rental property income/expenses",
            "Partnership or S-Corp K-1",
            "QBI deduction eligibility",
            "Home office deduction",
            "Asset depreciation",
        ],
        estimated_hours_range=(3.0, 5.0),
        suggested_price_range=(850, 1600),
        value_justification=[
            "Business expense maximization",
            "Entity structure advisory",
            "Quarterly estimated tax planning",
            "QBI deduction optimization (up to 20% savings)",
            "Depreciation and Section 179 strategy",
            "Reduced audit exposure through proper documentation",
        ],
    ),
    ComplexityTier.TIER_4_HIGHLY_COMPLEX: PricingGuidance(
        tier=ComplexityTier.TIER_4_HIGHLY_COMPLEX,
        tier_name="Highly Complex - Multi-Jurisdictional",
        description="Multi-state, foreign income, AMT exposure, equity compensation",
        typical_forms=[
            "1040", "Schedule C", "Schedule E", "K-1",
            "6251", "8938", "FBAR", "1116", "8949", "3921"
        ],
        complexity_indicators=[
            "Multi-state income and filing",
            "Foreign income or assets (FBAR/FATCA)",
            "Alternative Minimum Tax exposure",
            "Stock options (ISO/NSO), RSUs, ESPP",
            "Cryptocurrency transactions",
            "Passive activity loss limitations",
            "Trust or estate K-1 income",
        ],
        estimated_hours_range=(5.0, 10.0),
        suggested_price_range=(1600, 3200),
        value_justification=[
            "Multi-state allocation and credit optimization",
            "Foreign tax credit vs deduction analysis",
            "AMT planning and mitigation",
            "Equity compensation exercise timing strategy",
            "Crypto cost basis optimization",
            "Passive loss utilization strategy",
            "Penalty avoidance on complex compliance",
        ],
    ),
    ComplexityTier.TIER_5_ENTERPRISE: PricingGuidance(
        tier=ComplexityTier.TIER_5_ENTERPRISE,
        tier_name="Enterprise/High Net Worth",
        description="HNW individuals, multiple entities, comprehensive planning",
        typical_forms=[
            "1040", "1120/1120-S", "1065", "709", "706",
            "Multiple state returns", "International forms"
        ],
        complexity_indicators=[
            "Multiple business entities",
            "High income ($500K+ AGI)",
            "Estate and gift tax coordination",
            "Charitable giving strategies (DAF, CRT)",
            "International holdings or structures",
            "Year-round tax planning required",
            "Family office or wealth management coordination",
        ],
        estimated_hours_range=(10.0, 30.0),
        suggested_price_range=(3200, 12000),
        value_justification=[
            "Comprehensive multi-year tax planning",
            "Entity structure and income shifting optimization",
            "Estate and gift tax minimization",
            "Charitable giving strategy (often $10K+ tax savings)",
            "Coordination with wealth management team",
            "Year-round advisory relationship",
            "Audit representation and defense",
            "Potential six-figure lifetime tax savings",
        ],
    ),
}


class EngagementPricingEngine:
    """
    P2: Engine for determining engagement pricing based on complexity.

    IMPORTANT DISCLAIMER: This is an advisory support platform, NOT an
    e-filing service. Pricing guidance is for CPA advisory services only.
    The CPA makes all final pricing and engagement decisions.
    """

    # Service type disclaimer
    ADVISORY_DISCLAIMER = (
        "IMPORTANT: This platform provides tax advisory and preparation "
        "support for CPAs. It is NOT an e-filing service. Tax returns "
        "prepared using this platform must be filed through the CPA's "
        "chosen e-filing provider or paper filing method. The CPA retains "
        "full professional responsibility for all client engagements."
    )

    def __init__(self):
        """Initialize pricing engine."""
        self._tiers = PRICING_TIERS

    def assess_complexity(self, tax_return_data: Dict[str, Any]) -> ComplexityTier:
        """
        Assess complexity tier based on tax return characteristics.

        Args:
            tax_return_data: Tax return data dictionary

        Returns:
            Appropriate ComplexityTier
        """
        score = 0

        # Income complexity
        agi = float(tax_return_data.get("adjusted_gross_income") or 0)
        if agi > 1000000:
            score += 4
        elif agi > 500000:
            score += 3
        elif agi > 200000:
            score += 2
        elif agi > 100000:
            score += 1

        # Self-employment
        if tax_return_data.get("schedule_c") or tax_return_data.get("self_employment_income"):
            score += 2

        # Rental properties
        if tax_return_data.get("schedule_e") or tax_return_data.get("rental_income"):
            score += 2

        # K-1 income
        k1_count = len(tax_return_data.get("schedule_k1s") or [])
        if k1_count > 0:
            score += min(k1_count, 3)  # Cap at 3 points

        # Investments
        if tax_return_data.get("capital_gains") or tax_return_data.get("schedule_d"):
            score += 1

        # Foreign income/assets
        if tax_return_data.get("foreign_income") or tax_return_data.get("fbar_required"):
            score += 3

        # Cryptocurrency
        if tax_return_data.get("cryptocurrency_transactions"):
            score += 2

        # Multi-state
        state_count = len(tax_return_data.get("state_returns") or [])
        if state_count > 1:
            score += state_count

        # Stock options
        if tax_return_data.get("stock_options") or tax_return_data.get("equity_compensation"):
            score += 2

        # AMT exposure
        if tax_return_data.get("amt_liable"):
            score += 2

        # Map score to tier
        if score >= 12:
            return ComplexityTier.TIER_5_ENTERPRISE
        elif score >= 8:
            return ComplexityTier.TIER_4_HIGHLY_COMPLEX
        elif score >= 5:
            return ComplexityTier.TIER_3_COMPLEX
        elif score >= 2:
            return ComplexityTier.TIER_2_MODERATE
        else:
            return ComplexityTier.TIER_1_SIMPLE

    def get_pricing_guidance(
        self,
        tax_return_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get comprehensive pricing guidance for a tax return.

        Args:
            tax_return_data: Tax return data dictionary

        Returns:
            Pricing guidance with tier, ranges, and justification
        """
        tier = self.assess_complexity(tax_return_data)
        guidance = self._tiers[tier]

        # Identify specific complexity factors present
        detected_factors = self._detect_complexity_factors(tax_return_data)

        return {
            "disclaimer": self.ADVISORY_DISCLAIMER,
            "assessed_tier": tier.value,
            "tier_name": guidance.tier_name,
            "tier_description": guidance.description,
            "typical_forms": guidance.typical_forms,
            "complexity_indicators": guidance.complexity_indicators,
            "detected_factors": detected_factors,
            "estimated_hours": {
                "min": guidance.estimated_hours_range[0],
                "max": guidance.estimated_hours_range[1],
            },
            "suggested_price_range": {
                "min": guidance.suggested_price_range[0],
                "max": guidance.suggested_price_range[1],
                "currency": "USD",
            },
            "value_justification": guidance.value_justification,
            "pricing_note": (
                "These are suggested ranges based on industry benchmarks and "
                "complexity assessment. Final pricing is at the CPA's discretion "
                "based on their practice, location, and client relationship."
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _detect_complexity_factors(
        self,
        tax_return_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Detect specific complexity factors in the return."""
        factors = []

        if tax_return_data.get("schedule_c") or tax_return_data.get("self_employment_income"):
            factors.append({
                "factor": "self_employment",
                "description": "Self-employment income detected",
                "impact": "Adds Schedule C, SE, and potentially 8829",
            })

        if tax_return_data.get("schedule_e") or tax_return_data.get("rental_income"):
            factors.append({
                "factor": "rental_properties",
                "description": "Rental property income/expenses",
                "impact": "Adds Schedule E, depreciation calculations",
            })

        k1_count = len(tax_return_data.get("schedule_k1s") or [])
        if k1_count > 0:
            factors.append({
                "factor": "k1_income",
                "description": f"{k1_count} K-1 form(s) detected",
                "impact": "Partnership/S-Corp income, basis tracking, passive activity rules",
            })

        if tax_return_data.get("foreign_income") or tax_return_data.get("fbar_required"):
            factors.append({
                "factor": "foreign_reporting",
                "description": "Foreign income or assets detected",
                "impact": "May require FBAR, Form 8938, Form 1116",
            })

        if tax_return_data.get("cryptocurrency_transactions"):
            factors.append({
                "factor": "cryptocurrency",
                "description": "Cryptocurrency activity detected",
                "impact": "Form 8949 reporting, cost basis tracking",
            })

        state_count = len(tax_return_data.get("state_returns") or [])
        if state_count > 1:
            factors.append({
                "factor": "multi_state",
                "description": f"{state_count} state returns required",
                "impact": "State allocation, credits for taxes paid to other states",
            })

        if tax_return_data.get("stock_options") or tax_return_data.get("equity_compensation"):
            factors.append({
                "factor": "equity_compensation",
                "description": "Stock options or equity compensation",
                "impact": "ISO/NSO treatment, AMT considerations, Form 3921",
            })

        if tax_return_data.get("amt_liable"):
            factors.append({
                "factor": "amt_exposure",
                "description": "Alternative Minimum Tax exposure",
                "impact": "Form 6251, complex preference item calculations",
            })

        agi = float(tax_return_data.get("adjusted_gross_income") or 0)
        if agi > 500000:
            factors.append({
                "factor": "high_income",
                "description": f"High AGI (${agi:,.0f})",
                "impact": "Phaseouts, NIIT, additional Medicare tax",
            })

        return factors

    def get_all_tiers(self) -> Dict[str, Dict[str, Any]]:
        """Get all pricing tier information for reference."""
        return {
            "disclaimer": self.ADVISORY_DISCLAIMER,
            "tiers": {
                tier.value: {
                    "tier_name": guidance.tier_name,
                    "description": guidance.description,
                    "typical_forms": guidance.typical_forms,
                    "complexity_indicators": guidance.complexity_indicators,
                    "estimated_hours": {
                        "min": guidance.estimated_hours_range[0],
                        "max": guidance.estimated_hours_range[1],
                    },
                    "suggested_price_range": {
                        "min": guidance.suggested_price_range[0],
                        "max": guidance.suggested_price_range[1],
                        "currency": "USD",
                    },
                    "value_justification": guidance.value_justification,
                }
                for tier, guidance in self._tiers.items()
            },
            "note": (
                "Pricing guidance is for CPA advisory and preparation services. "
                "This platform does NOT provide e-filing services."
            ),
        }
