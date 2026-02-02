"""
AI-Powered Lead Intelligence for CPA Panel.

Uses Claude (Anthropic) for intelligent lead analysis including:
- Deep lead qualification and scoring
- Client lifetime value prediction
- Cross-sell/upsell opportunity identification
- Personalized outreach strategy generation
- Engagement timing optimization
"""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from decimal import Decimal

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LeadQualityTier(Enum):
    """Lead quality tiers based on analysis."""
    PLATINUM = "platinum"  # High value, ready to engage
    GOLD = "gold"  # Good fit, needs nurturing
    SILVER = "silver"  # Potential, requires qualification
    BRONZE = "bronze"  # Low priority, monitor
    UNQUALIFIED = "unqualified"  # Not a fit


class ServiceTier(Enum):
    """Recommended service tiers."""
    ENTERPRISE = "enterprise"  # Full service, high complexity
    PREMIUM = "premium"  # Comprehensive service
    STANDARD = "standard"  # Core tax services
    BASIC = "basic"  # Simple returns only
    REFERRAL = "referral"  # Better fit for another provider


class EngagementUrgency(Enum):
    """Urgency level for engagement."""
    IMMEDIATE = "immediate"  # Contact within 24 hours
    HIGH = "high"  # Contact within 48 hours
    NORMAL = "normal"  # Contact within 1 week
    LOW = "low"  # Add to nurture sequence
    DEFERRED = "deferred"  # Wait for trigger event


@dataclass
class LeadScoring:
    """Detailed lead scoring breakdown."""
    overall_score: int  # 0-100
    fit_score: int  # How well they match ideal client profile
    intent_score: int  # Buying signals and readiness
    budget_score: int  # Ability to pay
    timing_score: int  # Urgency of need
    engagement_score: int  # Level of interaction
    scoring_factors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RevenueProjection:
    """Projected revenue from lead."""
    first_year_revenue: Decimal
    lifetime_value: Decimal
    confidence_level: float  # 0-1
    revenue_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)


@dataclass
class CrossSellOpportunity:
    """Cross-sell/upsell opportunity."""
    service_name: str
    description: str
    estimated_value: Decimal
    probability: float  # 0-1
    trigger_event: Optional[str] = None
    timing: Optional[str] = None
    approach: Optional[str] = None


@dataclass
class OutreachStrategy:
    """Personalized outreach strategy."""
    primary_channel: str  # email, phone, linkedin, etc.
    messaging_tone: str  # professional, friendly, urgent, etc.
    key_talking_points: List[str]
    pain_points_to_address: List[str]
    value_propositions: List[str]
    objection_handlers: Dict[str, str]
    follow_up_sequence: List[Dict[str, Any]]
    best_contact_times: List[str]


@dataclass
class LeadIntelligenceResult:
    """Complete lead intelligence analysis."""
    lead_id: str
    analysis_timestamp: datetime
    quality_tier: LeadQualityTier
    scoring: LeadScoring
    recommended_service_tier: ServiceTier
    engagement_urgency: EngagementUrgency
    revenue_projection: RevenueProjection
    cross_sell_opportunities: List[CrossSellOpportunity] = field(default_factory=list)
    outreach_strategy: Optional[OutreachStrategy] = None
    key_insights: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    next_best_actions: List[str] = field(default_factory=list)
    ai_confidence: float = 0.0
    raw_analysis: Optional[str] = None


@dataclass
class LeadData:
    """Input lead data for analysis."""
    lead_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    referral_source: Optional[str] = None
    estimated_income: Optional[Decimal] = None
    filing_status: Optional[str] = None
    has_business: bool = False
    business_type: Optional[str] = None
    business_revenue: Optional[Decimal] = None
    num_employees: Optional[int] = None
    tax_complexity_indicators: List[str] = field(default_factory=list)
    pain_points_mentioned: List[str] = field(default_factory=list)
    current_preparer: Optional[str] = None
    previous_interactions: List[Dict[str, Any]] = field(default_factory=list)
    website_behavior: Optional[Dict[str, Any]] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "lead_id": self.lead_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "job_title": self.job_title,
            "industry": self.industry,
            "source": self.source,
            "referral_source": self.referral_source,
            "estimated_income": str(self.estimated_income) if self.estimated_income else None,
            "filing_status": self.filing_status,
            "has_business": self.has_business,
            "business_type": self.business_type,
            "business_revenue": str(self.business_revenue) if self.business_revenue else None,
            "num_employees": self.num_employees,
            "tax_complexity_indicators": self.tax_complexity_indicators,
            "pain_points_mentioned": self.pain_points_mentioned,
            "current_preparer": self.current_preparer,
            "previous_interactions": self.previous_interactions,
            "website_behavior": self.website_behavior,
            "custom_fields": self.custom_fields,
        }


class ClaudeLeadIntelligence:
    """
    AI-powered lead intelligence using Claude for comprehensive analysis.

    Provides deep lead qualification, value prediction, and personalized
    outreach strategies for CPA firms.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the lead intelligence service.

        Args:
            api_key: Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client: Optional[Any] = None

    @property
    def client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def analyze_lead(
        self,
        lead: LeadData,
        firm_profile: Optional[Dict[str, Any]] = None,
        ideal_client_profile: Optional[Dict[str, Any]] = None
    ) -> LeadIntelligenceResult:
        """
        Perform comprehensive lead intelligence analysis.

        Args:
            lead: Lead data to analyze.
            firm_profile: Information about the CPA firm.
            ideal_client_profile: Characteristics of ideal clients.

        Returns:
            LeadIntelligenceResult with complete analysis.
        """
        prompt = self._build_analysis_prompt(lead, firm_profile, ideal_client_profile)

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                system="""You are an expert CPA firm business development analyst specializing in
lead qualification, client value assessment, and personalized engagement strategies.

Analyze leads with the precision of a seasoned practice development professional.
Consider tax complexity, revenue potential, and strategic fit.
Always respond with valid JSON matching the requested structure."""
            )

            content = response.content[0].text
            return self._parse_intelligence_response(lead.lead_id, content)

        except Exception as e:
            return LeadIntelligenceResult(
                lead_id=lead.lead_id,
                analysis_timestamp=datetime.now(),
                quality_tier=LeadQualityTier.UNQUALIFIED,
                scoring=LeadScoring(
                    overall_score=0,
                    fit_score=0,
                    intent_score=0,
                    budget_score=0,
                    timing_score=0,
                    engagement_score=0
                ),
                recommended_service_tier=ServiceTier.BASIC,
                engagement_urgency=EngagementUrgency.DEFERRED,
                revenue_projection=RevenueProjection(
                    first_year_revenue=Decimal("0"),
                    lifetime_value=Decimal("0"),
                    confidence_level=0.0
                ),
                key_insights=[f"Analysis error: {str(e)}"],
                ai_confidence=0.0,
                raw_analysis=str(e)
            )

    def generate_outreach_strategy(
        self,
        lead: LeadData,
        intelligence: LeadIntelligenceResult,
        firm_voice: Optional[Dict[str, Any]] = None
    ) -> OutreachStrategy:
        """
        Generate personalized outreach strategy for a lead.

        Args:
            lead: The lead data.
            intelligence: Previous intelligence analysis.
            firm_voice: Firm's communication style preferences.

        Returns:
            Personalized OutreachStrategy.
        """
        prompt = f"""Create a detailed outreach strategy for this lead.

LEAD PROFILE:
{json.dumps(lead.to_dict(), indent=2, default=str)}

INTELLIGENCE ANALYSIS:
- Quality Tier: {intelligence.quality_tier.value}
- Overall Score: {intelligence.scoring.overall_score}/100
- Recommended Service: {intelligence.recommended_service_tier.value}
- Urgency: {intelligence.engagement_urgency.value}

FIRM VOICE/STYLE:
{json.dumps(firm_voice or {"tone": "professional yet approachable"}, indent=2)}

Create a comprehensive outreach strategy with:
1. Primary communication channel and why
2. Messaging tone and style
3. Key talking points (specific to this lead)
4. Pain points to address
5. Value propositions to emphasize
6. Objection handlers for common concerns
7. Follow-up sequence (timing and content)
8. Best times to reach out

Respond with JSON:
{{
  "primary_channel": "channel name",
  "messaging_tone": "tone description",
  "key_talking_points": ["point 1", "point 2"],
  "pain_points_to_address": ["pain 1", "pain 2"],
  "value_propositions": ["value 1", "value 2"],
  "objection_handlers": {{"objection": "response"}},
  "follow_up_sequence": [
    {{"day": 1, "channel": "email", "content_theme": "introduction"}},
    {{"day": 3, "channel": "phone", "content_theme": "value add"}}
  ],
  "best_contact_times": ["Tuesday 10am", "Thursday 2pm"]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                return OutreachStrategy(
                    primary_channel=data.get("primary_channel", "email"),
                    messaging_tone=data.get("messaging_tone", "professional"),
                    key_talking_points=data.get("key_talking_points", []),
                    pain_points_to_address=data.get("pain_points_to_address", []),
                    value_propositions=data.get("value_propositions", []),
                    objection_handlers=data.get("objection_handlers", {}),
                    follow_up_sequence=data.get("follow_up_sequence", []),
                    best_contact_times=data.get("best_contact_times", [])
                )

        except Exception:
            pass

        return OutreachStrategy(
            primary_channel="email",
            messaging_tone="professional",
            key_talking_points=["Tax planning expertise", "Personalized service"],
            pain_points_to_address=["Tax complexity", "Compliance concerns"],
            value_propositions=["Save time", "Maximize deductions"],
            objection_handlers={},
            follow_up_sequence=[],
            best_contact_times=[]
        )

    def predict_lifetime_value(
        self,
        lead: LeadData,
        historical_client_data: Optional[List[Dict[str, Any]]] = None
    ) -> RevenueProjection:
        """
        Predict client lifetime value based on lead characteristics.

        Args:
            lead: Lead data.
            historical_client_data: Data from similar past clients.

        Returns:
            RevenueProjection with estimates and confidence.
        """
        prompt = f"""Predict client lifetime value for this lead.

LEAD DATA:
{json.dumps(lead.to_dict(), indent=2, default=str)}

HISTORICAL SIMILAR CLIENTS:
{json.dumps(historical_client_data or [], indent=2, default=str)}

Estimate:
1. First year revenue (tax prep, planning, other services)
2. 5-year lifetime value (assuming average retention)
3. Revenue breakdown by service type
4. Key assumptions made

Consider:
- Tax return complexity pricing
- Advisory service potential
- Referral value
- Upsell trajectory

Respond with JSON:
{{
  "first_year_revenue": 2500.00,
  "lifetime_value": 15000.00,
  "confidence_level": 0.75,
  "revenue_breakdown": {{
    "tax_preparation": 1500.00,
    "tax_planning": 500.00,
    "bookkeeping": 300.00,
    "advisory": 200.00
  }},
  "assumptions": [
    "3-year average retention",
    "10% annual service expansion"
  ]
}}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                return RevenueProjection(
                    first_year_revenue=Decimal(str(data.get("first_year_revenue", 0))),
                    lifetime_value=Decimal(str(data.get("lifetime_value", 0))),
                    confidence_level=data.get("confidence_level", 0.5),
                    revenue_breakdown={
                        k: Decimal(str(v))
                        for k, v in data.get("revenue_breakdown", {}).items()
                    },
                    assumptions=data.get("assumptions", [])
                )

        except Exception:
            pass

        return RevenueProjection(
            first_year_revenue=Decimal("0"),
            lifetime_value=Decimal("0"),
            confidence_level=0.0
        )

    def identify_cross_sell_opportunities(
        self,
        lead: LeadData,
        available_services: Optional[List[Dict[str, Any]]] = None
    ) -> List[CrossSellOpportunity]:
        """
        Identify cross-sell and upsell opportunities for a lead.

        Args:
            lead: Lead data.
            available_services: Services the firm offers.

        Returns:
            List of CrossSellOpportunity objects.
        """
        default_services = [
            {"name": "Tax Planning", "description": "Proactive tax strategy"},
            {"name": "Bookkeeping", "description": "Monthly bookkeeping services"},
            {"name": "Payroll", "description": "Payroll processing"},
            {"name": "Business Advisory", "description": "Strategic business consulting"},
            {"name": "Estate Planning", "description": "Estate and succession planning"},
            {"name": "Audit Support", "description": "IRS audit representation"},
        ]

        prompt = f"""Identify cross-sell opportunities for this lead.

LEAD DATA:
{json.dumps(lead.to_dict(), indent=2, default=str)}

AVAILABLE SERVICES:
{json.dumps(available_services or default_services, indent=2)}

For each relevant opportunity, provide:
1. Service name
2. Why it's relevant to this lead
3. Estimated annual value
4. Probability of conversion (0-1)
5. Best trigger event to introduce
6. Recommended timing
7. Approach strategy

Respond with JSON array:
[
  {{
    "service_name": "Tax Planning",
    "description": "Proactive strategies for business owner",
    "estimated_value": 2000.00,
    "probability": 0.7,
    "trigger_event": "After first tax return completion",
    "timing": "Q4 of first year",
    "approach": "Review meeting to discuss planning opportunities"
  }}
]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            json_start = content.find('[')
            json_end = content.rfind(']') + 1

            if json_start >= 0 and json_end > json_start:
                opportunities_data = json.loads(content[json_start:json_end])
                return [
                    CrossSellOpportunity(
                        service_name=opp.get("service_name", "Unknown"),
                        description=opp.get("description", ""),
                        estimated_value=Decimal(str(opp.get("estimated_value", 0))),
                        probability=opp.get("probability", 0.5),
                        trigger_event=opp.get("trigger_event"),
                        timing=opp.get("timing"),
                        approach=opp.get("approach")
                    )
                    for opp in opportunities_data
                ]

        except Exception:
            pass

        return []

    def score_lead_batch(
        self,
        leads: List[LeadData],
        ideal_client_profile: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Score multiple leads for prioritization.

        Args:
            leads: List of leads to score.
            ideal_client_profile: Ideal client characteristics.

        Returns:
            List of lead IDs with scores, sorted by priority.
        """
        results = []

        for lead in leads:
            try:
                intelligence = self.analyze_lead(lead, ideal_client_profile=ideal_client_profile)
                results.append({
                    "lead_id": lead.lead_id,
                    "name": lead.name,
                    "overall_score": intelligence.scoring.overall_score,
                    "quality_tier": intelligence.quality_tier.value,
                    "urgency": intelligence.engagement_urgency.value,
                    "projected_value": float(intelligence.revenue_projection.first_year_revenue),
                    "next_action": intelligence.next_best_actions[0] if intelligence.next_best_actions else "Review"
                })
            except Exception as e:
                results.append({
                    "lead_id": lead.lead_id,
                    "name": lead.name,
                    "overall_score": 0,
                    "quality_tier": "unqualified",
                    "urgency": "deferred",
                    "projected_value": 0,
                    "next_action": f"Error: {str(e)}"
                })

        # Sort by score descending
        results.sort(key=lambda x: x["overall_score"], reverse=True)
        return results

    def _build_analysis_prompt(
        self,
        lead: LeadData,
        firm_profile: Optional[Dict[str, Any]],
        ideal_client_profile: Optional[Dict[str, Any]]
    ) -> str:
        """Build the comprehensive analysis prompt."""
        return f"""Perform a comprehensive lead intelligence analysis.

LEAD DATA:
{json.dumps(lead.to_dict(), indent=2, default=str)}

CPA FIRM PROFILE:
{json.dumps(firm_profile or {"specialty": "Full-service tax and accounting"}, indent=2)}

IDEAL CLIENT PROFILE:
{json.dumps(ideal_client_profile or {
    "min_income": 75000,
    "preferred_complexity": "medium to high",
    "ideal_industries": ["professional services", "real estate", "healthcare"]
}, indent=2)}

Analyze this lead and provide:

1. LEAD SCORING (0-100 for each):
   - Overall Score
   - Fit Score (match to ideal client profile)
   - Intent Score (buying signals)
   - Budget Score (ability to pay)
   - Timing Score (urgency of need)
   - Engagement Score (interaction level)

2. QUALITY TIER: platinum/gold/silver/bronze/unqualified

3. RECOMMENDED SERVICE TIER: enterprise/premium/standard/basic/referral

4. ENGAGEMENT URGENCY: immediate/high/normal/low/deferred

5. REVENUE PROJECTION:
   - First year revenue estimate
   - Lifetime value (5-year)
   - Confidence level

6. CROSS-SELL OPPORTUNITIES (top 3)

7. KEY INSIGHTS (3-5 observations)

8. RISK FACTORS (potential concerns)

9. NEXT BEST ACTIONS (prioritized list)

Respond with JSON:
{{
  "quality_tier": "gold",
  "scoring": {{
    "overall_score": 75,
    "fit_score": 80,
    "intent_score": 70,
    "budget_score": 85,
    "timing_score": 65,
    "engagement_score": 75,
    "scoring_factors": [
      {{"factor": "Business owner", "impact": "+15", "reason": "Higher complexity needs"}}
    ]
  }},
  "recommended_service_tier": "premium",
  "engagement_urgency": "high",
  "revenue_projection": {{
    "first_year_revenue": 3500.00,
    "lifetime_value": 21000.00,
    "confidence_level": 0.75,
    "revenue_breakdown": {{"tax_prep": 2000, "planning": 1000, "other": 500}},
    "assumptions": ["Standard retention", "Annual growth"]
  }},
  "cross_sell_opportunities": [
    {{
      "service_name": "Tax Planning",
      "description": "Proactive tax strategy",
      "estimated_value": 1500.00,
      "probability": 0.8,
      "trigger_event": "Q4 planning season",
      "timing": "October",
      "approach": "Review meeting"
    }}
  ],
  "key_insights": [
    "Business owner with growth trajectory",
    "Currently underserved by basic preparer"
  ],
  "risk_factors": [
    "Price sensitive based on current provider"
  ],
  "next_best_actions": [
    "Schedule discovery call within 48 hours",
    "Prepare business owner case studies"
  ],
  "ai_confidence": 0.85
}}"""

    def _parse_intelligence_response(
        self,
        lead_id: str,
        content: str
    ) -> LeadIntelligenceResult:
        """Parse Claude's intelligence response."""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])

                # Parse scoring
                scoring_data = data.get("scoring", {})
                scoring = LeadScoring(
                    overall_score=scoring_data.get("overall_score", 50),
                    fit_score=scoring_data.get("fit_score", 50),
                    intent_score=scoring_data.get("intent_score", 50),
                    budget_score=scoring_data.get("budget_score", 50),
                    timing_score=scoring_data.get("timing_score", 50),
                    engagement_score=scoring_data.get("engagement_score", 50),
                    scoring_factors=scoring_data.get("scoring_factors", [])
                )

                # Parse revenue projection
                rev_data = data.get("revenue_projection", {})
                revenue_projection = RevenueProjection(
                    first_year_revenue=Decimal(str(rev_data.get("first_year_revenue", 0))),
                    lifetime_value=Decimal(str(rev_data.get("lifetime_value", 0))),
                    confidence_level=rev_data.get("confidence_level", 0.5),
                    revenue_breakdown={
                        k: Decimal(str(v))
                        for k, v in rev_data.get("revenue_breakdown", {}).items()
                    },
                    assumptions=rev_data.get("assumptions", [])
                )

                # Parse cross-sell opportunities
                cross_sells = []
                for opp in data.get("cross_sell_opportunities", []):
                    cross_sells.append(CrossSellOpportunity(
                        service_name=opp.get("service_name", "Unknown"),
                        description=opp.get("description", ""),
                        estimated_value=Decimal(str(opp.get("estimated_value", 0))),
                        probability=opp.get("probability", 0.5),
                        trigger_event=opp.get("trigger_event"),
                        timing=opp.get("timing"),
                        approach=opp.get("approach")
                    ))

                return LeadIntelligenceResult(
                    lead_id=lead_id,
                    analysis_timestamp=datetime.now(),
                    quality_tier=LeadQualityTier(data.get("quality_tier", "silver")),
                    scoring=scoring,
                    recommended_service_tier=ServiceTier(
                        data.get("recommended_service_tier", "standard")
                    ),
                    engagement_urgency=EngagementUrgency(
                        data.get("engagement_urgency", "normal")
                    ),
                    revenue_projection=revenue_projection,
                    cross_sell_opportunities=cross_sells,
                    key_insights=data.get("key_insights", []),
                    risk_factors=data.get("risk_factors", []),
                    next_best_actions=data.get("next_best_actions", []),
                    ai_confidence=data.get("ai_confidence", 0.7),
                    raw_analysis=content
                )

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Return default result on parse failure
        return LeadIntelligenceResult(
            lead_id=lead_id,
            analysis_timestamp=datetime.now(),
            quality_tier=LeadQualityTier.SILVER,
            scoring=LeadScoring(
                overall_score=50,
                fit_score=50,
                intent_score=50,
                budget_score=50,
                timing_score=50,
                engagement_score=50
            ),
            recommended_service_tier=ServiceTier.STANDARD,
            engagement_urgency=EngagementUrgency.NORMAL,
            revenue_projection=RevenueProjection(
                first_year_revenue=Decimal("0"),
                lifetime_value=Decimal("0"),
                confidence_level=0.0
            ),
            ai_confidence=0.0,
            raw_analysis=content
        )


# Singleton instance
_lead_intelligence: Optional[ClaudeLeadIntelligence] = None


def get_lead_intelligence() -> ClaudeLeadIntelligence:
    """Get the singleton ClaudeLeadIntelligence instance."""
    global _lead_intelligence
    if _lead_intelligence is None:
        _lead_intelligence = ClaudeLeadIntelligence()
    return _lead_intelligence


__all__ = [
    "ClaudeLeadIntelligence",
    "get_lead_intelligence",
    "LeadIntelligenceResult",
    "LeadData",
    "LeadScoring",
    "RevenueProjection",
    "CrossSellOpportunity",
    "OutreachStrategy",
    "LeadQualityTier",
    "ServiceTier",
    "EngagementUrgency",
]
