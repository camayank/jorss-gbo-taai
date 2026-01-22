"""
Subscription Tier Control System

Manages feature access based on subscription tiers.
Critical for monetization - gates premium advisory reports.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class SubscriptionTier(str, Enum):
    """User subscription tiers"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"
    CPA_FIRM = "cpa_firm"  # Special tier for CPA firms


@dataclass
class TierLimits:
    """Limits and features for each tier"""
    # Report features
    top_opportunities_count: int
    detailed_findings: bool
    pdf_download: bool
    scenario_comparison: bool
    multi_year_projection: bool

    # Filing features
    returns_per_year: int
    state_returns_included: int
    amended_returns: bool
    prior_year_filing: bool

    # Support features
    email_support: bool
    priority_support: bool
    cpa_review: bool
    live_chat: bool

    # Advanced features
    tax_planning: bool
    quarterly_estimates: bool
    audit_protection: bool
    document_storage_gb: int


# Define tier configurations
TIER_CONFIG: Dict[SubscriptionTier, TierLimits] = {
    SubscriptionTier.FREE: TierLimits(
        # Report features
        top_opportunities_count=2,  # Show only top 2
        detailed_findings=False,
        pdf_download=False,
        scenario_comparison=False,
        multi_year_projection=False,
        # Filing features
        returns_per_year=1,  # 1 free return
        state_returns_included=0,  # Federal only
        amended_returns=False,
        prior_year_filing=False,
        # Support
        email_support=True,
        priority_support=False,
        cpa_review=False,
        live_chat=False,
        # Advanced
        tax_planning=False,
        quarterly_estimates=False,
        audit_protection=False,
        document_storage_gb=1,
    ),

    SubscriptionTier.BASIC: TierLimits(
        # Report features
        top_opportunities_count=5,
        detailed_findings=True,
        pdf_download=True,
        scenario_comparison=False,
        multi_year_projection=False,
        # Filing features
        returns_per_year=3,
        state_returns_included=1,
        amended_returns=True,
        prior_year_filing=True,  # 1 prior year
        # Support
        email_support=True,
        priority_support=False,
        cpa_review=False,
        live_chat=False,
        # Advanced
        tax_planning=False,
        quarterly_estimates=False,
        audit_protection=False,
        document_storage_gb=5,
    ),

    SubscriptionTier.PREMIUM: TierLimits(
        # Report features
        top_opportunities_count=999,  # Unlimited
        detailed_findings=True,
        pdf_download=True,
        scenario_comparison=True,
        multi_year_projection=True,
        # Filing features
        returns_per_year=999,  # Unlimited
        state_returns_included=999,  # All states
        amended_returns=True,
        prior_year_filing=True,  # Up to 3 years
        # Support
        email_support=True,
        priority_support=True,
        cpa_review=False,  # Not included (upgrade to Professional)
        live_chat=True,
        # Advanced
        tax_planning=True,
        quarterly_estimates=True,
        audit_protection=False,
        document_storage_gb=50,
    ),

    SubscriptionTier.PROFESSIONAL: TierLimits(
        # All Premium features PLUS:
        top_opportunities_count=999,
        detailed_findings=True,
        pdf_download=True,
        scenario_comparison=True,
        multi_year_projection=True,
        returns_per_year=999,
        state_returns_included=999,
        amended_returns=True,
        prior_year_filing=True,
        email_support=True,
        priority_support=True,
        cpa_review=True,  # CPA review included
        live_chat=True,
        tax_planning=True,
        quarterly_estimates=True,
        audit_protection=True,  # $1M audit defense
        document_storage_gb=999,  # Unlimited
    ),

    SubscriptionTier.CPA_FIRM: TierLimits(
        # CPA firms get all features for their clients
        top_opportunities_count=999,
        detailed_findings=True,
        pdf_download=True,
        scenario_comparison=True,
        multi_year_projection=True,
        returns_per_year=999,
        state_returns_included=999,
        amended_returns=True,
        prior_year_filing=True,
        email_support=True,
        priority_support=True,
        cpa_review=True,
        live_chat=True,
        tax_planning=True,
        quarterly_estimates=True,
        audit_protection=True,
        document_storage_gb=999,
    ),
}


class ReportAccessControl:
    """Control access to advisory reports based on tier"""

    @staticmethod
    def filter_report(
        full_report: Dict[str, Any],
        tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """
        Filter advisory report based on subscription tier.

        Args:
            full_report: Complete advisory report with all findings
            tier: User's subscription tier

        Returns:
            Filtered report appropriate for tier
        """
        limits = TIER_CONFIG[tier]

        # Base data (always included)
        filtered = {
            "current_federal_tax": full_report.get("current_federal_tax"),
            "refund": full_report.get("refund"),
            "tax_owed": full_report.get("tax_owed"),
            "effective_rate": full_report.get("effective_rate"),
            "tier": tier.value,
        }

        # Top opportunities (limited by tier)
        all_opportunities = full_report.get("top_opportunities", [])
        filtered["top_opportunities"] = all_opportunities[:limits.top_opportunities_count]

        # Track what's hidden for upgrade prompt
        hidden_count = max(0, len(all_opportunities) - limits.top_opportunities_count)
        hidden_savings = sum(
            o.get("estimated_savings", 0)
            for o in all_opportunities[limits.top_opportunities_count:]
        )

        # Detailed findings (premium tiers only)
        if limits.detailed_findings:
            filtered["detailed_findings"] = full_report.get("detailed_findings", [])
            filtered["executive_summary"] = full_report.get("executive_summary", "")
            filtered["confidence"] = full_report.get("overall_confidence", 0)
        else:
            filtered["detailed_findings"] = []
            filtered["executive_summary"] = (
                "📊 Upgrade to see detailed tax-saving strategies and "
                "personalized recommendations from our tax experts."
            )
            filtered["confidence"] = None

        # Scenario comparison (premium only)
        if limits.scenario_comparison:
            filtered["scenarios"] = full_report.get("scenarios", [])
        else:
            filtered["scenarios"] = []

        # Multi-year projection (premium only)
        if limits.multi_year_projection:
            filtered["projections"] = full_report.get("projections", [])
        else:
            filtered["projections"] = []

        # PDF download capability
        filtered["can_download_pdf"] = limits.pdf_download

        # Add upgrade prompt for users with hidden content
        if hidden_count > 0 or not limits.detailed_findings:
            filtered["upgrade_prompt"] = ReportAccessControl._create_upgrade_prompt(
                tier=tier,
                hidden_count=hidden_count,
                hidden_savings=hidden_savings,
                has_detailed_findings=limits.detailed_findings
            )

        return filtered

    @staticmethod
    def _create_upgrade_prompt(
        tier: SubscriptionTier,
        hidden_count: int,
        hidden_savings: float,
        has_detailed_findings: bool
    ) -> Dict[str, Any]:
        """Create persuasive upgrade prompt"""

        if tier == SubscriptionTier.FREE:
            return {
                "title": f"💎 Unlock {hidden_count} More Tax-Saving Opportunities!",
                "message": (
                    f"You're missing out on ${hidden_savings:,.0f} in potential "
                    f"tax savings. Upgrade to Premium to see all opportunities."
                ),
                "cta": "Upgrade to Premium - $49/year",
                "features": [
                    f"✓ See all {hidden_count} hidden opportunities",
                    "✓ Detailed tax-saving strategies",
                    "✓ Downloadable PDF reports",
                    "✓ Multi-scenario comparison",
                    "✓ 5-year tax projections",
                    "✓ Priority email support"
                ],
                "savings_potential": hidden_savings,
                "upgrade_url": "/pricing?from=report&tier=premium",
                "trial_available": True
            }

        elif tier == SubscriptionTier.BASIC:
            return {
                "title": "🚀 Upgrade to Premium for Advanced Features",
                "message": (
                    "Unlock scenario comparison and multi-year projections to "
                    "optimize your long-term tax strategy."
                ),
                "cta": "Upgrade to Premium - $29/year",  # Discount for existing users
                "features": [
                    "✓ Everything in Basic, plus:",
                    "✓ Scenario comparison tool",
                    "✓ 5-year tax projections",
                    "✓ Tax planning guidance",
                    "✓ Quarterly estimate calculator",
                    "✓ Priority support"
                ],
                "upgrade_url": "/pricing?from=report&tier=premium&current=basic",
            }

        return {}

    @staticmethod
    def can_access_feature(tier: SubscriptionTier, feature: str) -> bool:
        """
        Check if user's tier allows access to specific feature.

        Args:
            tier: User's subscription tier
            feature: Feature name (e.g., "pdf_download", "cpa_review")

        Returns:
            True if feature is available for this tier
        """
        limits = TIER_CONFIG[tier]
        return getattr(limits, feature, False)

    @staticmethod
    def get_tier_comparison() -> Dict[str, Any]:
        """Generate tier comparison table for pricing page"""
        features = [
            "top_opportunities_count",
            "detailed_findings",
            "pdf_download",
            "scenario_comparison",
            "multi_year_projection",
            "returns_per_year",
            "state_returns_included",
            "cpa_review",
            "priority_support",
            "audit_protection"
        ]

        comparison = {}
        for tier in [SubscriptionTier.FREE, SubscriptionTier.BASIC,
                     SubscriptionTier.PREMIUM, SubscriptionTier.PROFESSIONAL]:
            limits = TIER_CONFIG[tier]
            comparison[tier.value] = {
                feature: getattr(limits, feature)
                for feature in features
            }

        return comparison


# Convenience function for API endpoints
def get_user_tier(user_id: Optional[str]) -> SubscriptionTier:
    """
    Get subscription tier for a user.

    TODO: Integrate with payment system (Stripe, etc.)
    For now, returns FREE for anonymous, checks database for authenticated.
    """
    if not user_id:
        return SubscriptionTier.FREE

    # TODO: Query subscription database
    # For now, return FREE (implement payment integration later)
    return SubscriptionTier.FREE


__all__ = [
    'SubscriptionTier',
    'TierLimits',
    'TIER_CONFIG',
    'ReportAccessControl',
    'get_user_tier',
]
