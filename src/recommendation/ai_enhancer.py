"""
AI-Powered Recommendation Enhancer.

Enhances rule-based tax recommendations with AI-generated explanations,
personalized advice, and natural language summaries.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from recommendation.recommendation_engine import ComprehensiveRecommendation, TaxSavingOpportunity

from services.ai import get_ai_service, run_async
from services.ai.metrics_service import get_ai_metrics_service
from config.ai_providers import ModelCapability, get_available_providers

logger = logging.getLogger(__name__)


def _count_populated_enhancement(rec: "AIEnhancedRecommendation") -> int:
    """Count non-empty fields in an AIEnhancedRecommendation."""
    count = 0
    if rec.personalized_explanation:
        count += 1
    if rec.action_steps:
        count += 1
    if rec.common_questions:
        count += 1
    if rec.risk_considerations:
        count += 1
    if rec.related_opportunities:
        count += 1
    if rec.confidence_explanation:
        count += 1
    if rec.irs_reference:
        count += 1
    return count


@dataclass
class AIEnhancedRecommendation:
    """AI-enhanced version of a tax recommendation."""
    original_title: str
    original_description: str
    estimated_savings: float

    # AI-enhanced fields
    personalized_explanation: str
    action_steps: List[str]
    common_questions: List[Dict[str, str]]  # Q&A pairs
    risk_considerations: List[str]
    related_opportunities: List[str]
    confidence_explanation: str

    # Metadata
    irs_reference: str
    priority: str
    category: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIRecommendationSummary:
    """AI-generated summary of all recommendations."""
    executive_summary: str
    key_takeaways: List[str]
    priority_actions: List[str]
    estimated_total_savings: float
    confidence_summary: str
    personalized_advice: str
    warnings: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


CATEGORY_TEMPLATES = {
    "retirement": {
        "common_questions": [
            {"question": "Can I contribute to both a 401(k) and IRA?", "answer": "Yes, but IRA deductibility may be limited if you have a workplace plan and income above $87,000 (single) or $143,000 (MFJ)."},
            {"question": "What's the penalty for early withdrawal?", "answer": "Generally 10% penalty plus income tax if under 59½, with exceptions for hardship, first home, and education."},
        ],
        "risk_considerations": ["Contribution limits change annually", "Early withdrawal penalties apply before age 59½", "RMDs begin at age 73"],
        "related_opportunities": ["HSA Contributions", "Backdoor Roth IRA", "Mega Backdoor Roth"],
    },
    "credits": {
        "common_questions": [
            {"question": "What's the difference between refundable and non-refundable credits?", "answer": "Refundable credits can reduce your tax below zero (you get a refund). Non-refundable credits can only reduce your tax to zero."},
            {"question": "Can I claim multiple tax credits?", "answer": "Yes, you can claim all credits you qualify for. They are applied in a specific order on your return."},
        ],
        "risk_considerations": ["Income phase-outs may reduce credit amounts", "Some credits require specific documentation", "Credits may trigger additional IRS scrutiny"],
        "related_opportunities": ["Child Tax Credit", "Earned Income Tax Credit", "Education Credits"],
    },
    "deductions": {
        "common_questions": [
            {"question": "Should I itemize or take the standard deduction?", "answer": "Itemize if your total deductions exceed the standard deduction ($14,600 single, $29,200 MFJ for 2024). Consider bunching deductions across years."},
            {"question": "What records do I need for deductions?", "answer": "Keep receipts, bank statements, and written records. Charitable donations over $250 require written acknowledgment."},
        ],
        "risk_considerations": ["SALT deduction capped at $10,000", "Mortgage interest limited on loans over $750,000", "Miscellaneous deductions eliminated under TCJA"],
        "related_opportunities": ["Charitable Giving Strategies", "Medical Expense Deductions", "State Tax Planning"],
    },
    "healthcare": {
        "common_questions": [
            {"question": "Are health insurance premiums deductible?", "answer": "Self-employed can deduct 100% of premiums. W-2 employees can deduct medical expenses exceeding 7.5% of AGI if itemizing."},
            {"question": "What qualifies as a medical expense?", "answer": "Doctor visits, prescriptions, dental, vision, mental health, and some travel costs for medical care."},
        ],
        "risk_considerations": ["7.5% AGI threshold is hard to exceed", "HSA contributions have annual limits", "Premium tax credits have income requirements"],
        "related_opportunities": ["HSA Contributions", "FSA Optimization", "Self-Employed Health Deduction"],
    },
    "investment": {
        "common_questions": [
            {"question": "How are capital gains taxed?", "answer": "Short-term gains (held < 1 year) are taxed as ordinary income. Long-term gains get preferential rates: 0%, 15%, or 20%."},
            {"question": "Can I offset gains with losses?", "answer": "Yes, losses offset gains dollar-for-dollar. Excess losses can offset up to $3,000 of ordinary income, with remainder carried forward."},
        ],
        "risk_considerations": ["Wash sale rule prevents repurchasing within 30 days", "Net investment income tax of 3.8% above thresholds", "Cryptocurrency is treated as property"],
        "related_opportunities": ["Tax-Loss Harvesting", "Qualified Opportunity Zones", "Municipal Bond Income"],
    },
    "education": {
        "common_questions": [
            {"question": "What education tax benefits are available?", "answer": "American Opportunity Credit (up to $2,500/yr for 4 years), Lifetime Learning Credit (up to $2,000/yr), and student loan interest deduction (up to $2,500)."},
            {"question": "Can I use a 529 plan for K-12?", "answer": "Yes, up to $10,000 per year per student for K-12 tuition from 529 plans."},
        ],
        "risk_considerations": ["Cannot claim both AOTC and LLC for same student", "Income limits apply to education credits", "529 non-qualified withdrawals incur penalty"],
        "related_opportunities": ["529 Plan Contributions", "Coverdell ESA", "Employer Tuition Assistance"],
    },
    "charitable": {
        "common_questions": [
            {"question": "How much can I deduct for charitable donations?", "answer": "Generally up to 60% of AGI for cash donations to public charities, 30% for capital gains property. Excess carries forward 5 years."},
            {"question": "Do I need a receipt for donations?", "answer": "Written acknowledgment required for donations of $250+. For non-cash over $500, file Form 8283. Over $5,000 needs qualified appraisal."},
        ],
        "risk_considerations": ["Must itemize to deduct charitable contributions", "Donations to individuals are not deductible", "Quid pro quo contributions must subtract value received"],
        "related_opportunities": ["Donor-Advised Funds", "Qualified Charitable Distributions", "Bunching Strategy"],
    },
    "business": {
        "common_questions": [
            {"question": "What business expenses are deductible?", "answer": "Expenses that are ordinary (common in your trade) and necessary (helpful and appropriate) for your business, including supplies, equipment, travel, and home office."},
            {"question": "Should I use actual expenses or standard mileage?", "answer": "Compare both methods. Standard mileage rate is 70 cents/mile for 2025. Actual expenses may be higher for expensive vehicles."},
        ],
        "risk_considerations": ["Home office must be exclusive and regular business use", "Vehicle logs must be contemporaneous", "Hobby loss rules if no profit 3 of 5 years"],
        "related_opportunities": ["Section 179 Deduction", "Home Office Deduction", "Qualified Business Income Deduction"],
    },
    "timing": {
        "common_questions": [
            {"question": "When should I accelerate or defer income?", "answer": "Defer income if you expect a lower tax bracket next year. Accelerate income if you expect higher rates or brackets next year."},
            {"question": "What are estimated tax payment deadlines?", "answer": "Quarterly: April 15, June 15, September 15, January 15. Pay 100% of prior year tax or 90% of current year to avoid penalties."},
        ],
        "risk_considerations": ["Underpayment penalties if insufficient estimated payments", "AMT may negate timing benefits", "Tax law changes can affect strategy"],
        "related_opportunities": ["Income Deferral Strategies", "Expense Acceleration", "Year-End Tax Planning"],
    },
    "filing_status": {
        "common_questions": [
            {"question": "Which filing status gives me the lowest tax?", "answer": "Generally: MFJ has lowest rates and highest thresholds. Head of Household is better than Single. Compare MFJ vs MFS for specific situations."},
            {"question": "Can I file as Head of Household?", "answer": "You must be unmarried (or considered unmarried), pay >50% of household costs, and have a qualifying person living with you for more than half the year."},
        ],
        "risk_considerations": ["Married filing separately loses many credits and deductions", "Filing status determined on December 31", "Head of Household has strict qualifying rules"],
        "related_opportunities": ["Filing Status Optimization", "Innocent Spouse Relief", "Community Property Rules"],
    },
    "family": {
        "common_questions": [
            {"question": "What tax benefits are available for families?", "answer": "Child Tax Credit ($2,000/child), Child and Dependent Care Credit, Earned Income Tax Credit, and dependency exemption benefits built into credits."},
            {"question": "Can I claim my college student as a dependent?", "answer": "Yes, if under 24 and full-time student, you provide over 50% of support, and they don't provide over 50% of their own support."},
        ],
        "risk_considerations": ["Only one parent can claim a child in divorce situations", "Kiddie tax applies to children's unearned income", "Phase-outs reduce benefits at higher incomes"],
        "related_opportunities": ["Child Tax Credit", "Dependent Care FSA", "Education Credits for Dependents"],
    },
    "state_specific": {
        "common_questions": [
            {"question": "Can I deduct state taxes on my federal return?", "answer": "Yes, state and local taxes (income/sales + property) are deductible up to $10,000 combined when itemizing (SALT cap)."},
            {"question": "What if I work in a different state than I live?", "answer": "You may owe taxes in both states. Most states provide a credit for taxes paid to other states to prevent double taxation."},
        ],
        "risk_considerations": ["SALT deduction cap limits benefit of high state taxes", "State residency rules vary significantly", "Remote work may create nexus in employer's state"],
        "related_opportunities": ["State Tax Credit Optimization", "Residency Planning", "State-Specific Deductions"],
    },
}


class AIRecommendationEnhancer:
    """
    Enhances tax recommendations using AI.

    Takes rule-based recommendations from the TaxRecommendationEngine
    and adds:
    - Personalized natural language explanations
    - Step-by-step action guides
    - Common questions and answers
    - Risk considerations
    - Confidence explanations
    """

    def __init__(self):
        """Initialize the AI enhancer."""
        pass

    @property
    def is_available(self) -> bool:
        """Check if AI enhancement is available."""
        return len(get_available_providers()) > 0

    def enhance_recommendation(
        self,
        opportunity: "TaxSavingOpportunity",
        taxpayer_context: Optional[Dict[str, Any]] = None
    ) -> AIEnhancedRecommendation:
        """
        Enhance a single recommendation with AI-generated content.

        Args:
            opportunity: The original rule-based opportunity
            taxpayer_context: Optional context about the taxpayer

        Returns:
            AIEnhancedRecommendation with enhanced explanations
        """
        if not self.is_available:
            return self._fallback_enhancement(opportunity)

        try:
            # Build context for AI
            context = {
                "title": opportunity.title,
                "category": opportunity.category,
                "description": opportunity.description,
                "estimated_savings": opportunity.estimated_savings,
                "action_required": opportunity.action_required,
                "priority": opportunity.priority,
                "irs_reference": opportunity.irs_reference,
                "confidence": opportunity.confidence,
            }

            if taxpayer_context:
                context["taxpayer"] = {
                    "filing_status": taxpayer_context.get("filing_status"),
                    "income_range": self._get_income_range(taxpayer_context.get("agi", 0)),
                    "has_dependents": taxpayer_context.get("has_dependents", False),
                }

            # Generate enhanced content
            prompt = self._build_enhancement_prompt(context)
            response = self._call_openai(prompt)

            if response:
                enhanced = json.loads(response)
                result = AIEnhancedRecommendation(
                    original_title=opportunity.title,
                    original_description=opportunity.description,
                    estimated_savings=opportunity.estimated_savings,
                    personalized_explanation=enhanced.get("personalized_explanation", opportunity.description),
                    action_steps=enhanced.get("action_steps", [opportunity.action_required]),
                    common_questions=enhanced.get("common_questions", []),
                    risk_considerations=enhanced.get("risk_considerations", []),
                    related_opportunities=enhanced.get("related_opportunities", []),
                    confidence_explanation=enhanced.get("confidence_explanation", ""),
                    irs_reference=opportunity.irs_reference,
                    priority=opportunity.priority,
                    category=opportunity.category,
                    metadata={"_source": "ai", "_provider": "openai"},
                )
                get_ai_metrics_service().record_response_quality(
                    service="enhancer", source="ai",
                    response_fields_populated=_count_populated_enhancement(result),
                    total_fields=7,
                )
                return result
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "enhancer",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user receives template response instead of AI-personalized",
                },
            )

        return self._fallback_enhancement(opportunity)

    def generate_summary(
        self,
        recommendation: "ComprehensiveRecommendation"
    ) -> AIRecommendationSummary:
        """
        Generate an AI-enhanced summary of all recommendations.

        Args:
            recommendation: The comprehensive recommendation from the engine

        Returns:
            AIRecommendationSummary with natural language insights
        """
        if not self.is_available:
            return self._fallback_summary(recommendation)

        try:
            # Build context
            context = {
                "taxpayer_name": recommendation.taxpayer_name,
                "filing_status": recommendation.filing_status,
                "current_tax": recommendation.current_total_tax,
                "optimized_tax": recommendation.optimized_total_tax,
                "total_savings": recommendation.total_potential_savings,
                "immediate_savings": recommendation.immediate_action_savings,
                "top_opportunities": [
                    {
                        "title": opp.title,
                        "savings": opp.estimated_savings,
                        "category": opp.category,
                    }
                    for opp in recommendation.top_opportunities[:5]
                ],
                "warnings": recommendation.warnings[:3],
            }

            prompt = self._build_summary_prompt(context)
            response = self._call_openai(prompt)

            if response:
                summary = json.loads(response)
                result = AIRecommendationSummary(
                    executive_summary=summary.get("executive_summary", recommendation.executive_summary),
                    key_takeaways=summary.get("key_takeaways", []),
                    priority_actions=summary.get("priority_actions", []),
                    estimated_total_savings=recommendation.total_potential_savings,
                    confidence_summary=summary.get("confidence_summary", ""),
                    personalized_advice=summary.get("personalized_advice", ""),
                    warnings=summary.get("warnings", recommendation.warnings),
                    metadata={"_source": "ai"},
                )
                get_ai_metrics_service().record_response_quality(
                    service="enhancer_summary", source="ai",
                    response_fields_populated=sum(1 for v in [result.executive_summary, result.key_takeaways, result.priority_actions, result.confidence_summary, result.personalized_advice] if v),
                    total_fields=5,
                )
                return result
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "enhancer_summary",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user receives template summary instead of AI-personalized",
                },
            )

        return self._fallback_summary(recommendation)

    def explain_in_plain_language(
        self,
        opportunity: "TaxSavingOpportunity",
        education_level: str = "general"
    ) -> str:
        """
        Generate a plain-language explanation of a tax opportunity.

        Args:
            opportunity: The opportunity to explain
            education_level: "general", "detailed", or "expert"

        Returns:
            Plain-language explanation string
        """
        if not self.is_available:
            return opportunity.description

        try:
            prompt = f"""Explain this tax opportunity in plain language for a {education_level} audience.

Title: {opportunity.title}
Category: {opportunity.category}
Description: {opportunity.description}
Potential Savings: ${opportunity.estimated_savings:,.0f}
IRS Reference: {opportunity.irs_reference}

Provide a clear, conversational explanation that:
1. Explains what this is in simple terms
2. Why it matters for the taxpayer
3. How much they could save
4. What they need to do

Keep it concise (2-3 sentences for general, 4-5 for detailed)."""

            response = self._call_openai(prompt, as_json=False)
            return response or opportunity.description
        except Exception as e:
            logger.warning(
                "AI fallback activated",
                extra={
                    "service": "enhancer_explain",
                    "source": "fallback",
                    "reason": str(e),
                    "impact": "user receives raw description instead of plain-language explanation",
                },
            )
            return opportunity.description

    def _build_enhancement_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for enhancing a recommendation."""
        return f"""You are a tax advisor AI. Enhance this tax recommendation with helpful explanations.

Recommendation Context:
{json.dumps(context, indent=2)}

Generate a JSON response with these fields:
{{
  "personalized_explanation": "A clear, personalized explanation of why this matters for the taxpayer",
  "action_steps": ["Step 1", "Step 2", ...],
  "common_questions": [
    {{"question": "Q1?", "answer": "A1"}},
    ...
  ],
  "risk_considerations": ["Risk 1", ...],
  "related_opportunities": ["Related opportunity 1", ...],
  "confidence_explanation": "Why we are confident/uncertain about this recommendation"
}}

Focus on being helpful, accurate, and actionable. Reference IRS rules when appropriate.
Return only valid JSON, no markdown code blocks."""

    def _build_summary_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for generating a summary."""
        return f"""You are a tax advisor AI. Generate a personalized summary of tax recommendations.

Context:
{json.dumps(context, indent=2)}

Generate a JSON response with these fields:
{{
  "executive_summary": "A 2-3 sentence executive summary of the tax situation and opportunities",
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"],
  "priority_actions": ["Action 1 (do first)", "Action 2", "Action 3"],
  "confidence_summary": "Brief explanation of how confident we are in these recommendations",
  "personalized_advice": "Specific advice based on their situation",
  "warnings": ["Important warning 1", ...]
}}

Be concise, professional, and helpful. Return only valid JSON, no markdown code blocks."""

    def _call_openai(self, prompt: str, as_json: bool = True) -> Optional[str]:
        """Make an AI API call via unified service."""
        if not self.is_available:
            return None

        try:
            ai = get_ai_service()
            response = run_async(ai.complete(
                prompt=prompt,
                system_prompt="You are a helpful tax advisor AI. Provide accurate, IRS-compliant advice.",
                capability=ModelCapability.FAST,
                temperature=0.3,
                max_tokens=1000,
            ))
            return response.content
        except Exception as e:
            logger.error(
                "AI API call failed",
                extra={
                    "service": "enhancer",
                    "source": "error",
                    "reason": str(e),
                    "impact": "upstream caller will receive None and use fallback path",
                },
            )
            return None

    def _fallback_enhancement(self, opportunity: "TaxSavingOpportunity") -> AIEnhancedRecommendation:
        """Create a fallback enhancement without AI, using category templates."""
        templates = CATEGORY_TEMPLATES.get(opportunity.category, {})
        result = AIEnhancedRecommendation(
            original_title=opportunity.title,
            original_description=opportunity.description,
            estimated_savings=opportunity.estimated_savings,
            personalized_explanation=opportunity.description,
            action_steps=[opportunity.action_required],
            common_questions=templates.get("common_questions", []),
            risk_considerations=templates.get("risk_considerations", []),
            related_opportunities=templates.get("related_opportunities", []),
            confidence_explanation=f"Confidence level: {opportunity.confidence:.0f}%",
            irs_reference=opportunity.irs_reference,
            priority=opportunity.priority,
            category=opportunity.category,
            metadata={"_source": "fallback", "_provider": "none"},
        )
        get_ai_metrics_service().record_response_quality(
            service="enhancer", source="fallback",
            response_fields_populated=_count_populated_enhancement(result),
            total_fields=7,
        )
        return result

    def _fallback_summary(self, recommendation: "ComprehensiveRecommendation") -> AIRecommendationSummary:
        """Create a fallback summary without AI."""
        result = AIRecommendationSummary(
            executive_summary=recommendation.executive_summary,
            key_takeaways=[
                f"Total potential savings: ${recommendation.total_potential_savings:,.0f}",
                f"Immediate action savings: ${recommendation.immediate_action_savings:,.0f}",
                f"Review {len(recommendation.top_opportunities)} opportunities",
            ],
            priority_actions=[opp.action_required for opp in recommendation.top_opportunities[:3]],
            estimated_total_savings=recommendation.total_potential_savings,
            confidence_summary=f"Overall confidence: {recommendation.overall_confidence:.0f}%",
            personalized_advice=self._build_personalized_fallback_advice(recommendation),
            warnings=recommendation.warnings,
            metadata={"_source": "fallback"},
        )
        get_ai_metrics_service().record_response_quality(
            service="enhancer_summary", source="fallback",
            response_fields_populated=2,  # executive_summary + confidence_summary are template-copied
            total_fields=5,
        )
        return result

    def _build_personalized_fallback_advice(self, recommendation: "ComprehensiveRecommendation") -> str:
        """Build personalized advice string for fallback summary."""
        filing_status = getattr(recommendation, "filing_status", "unknown")
        agi = getattr(recommendation, "current_total_tax", 0)
        income_range = self._get_income_range(agi)
        savings = recommendation.total_potential_savings
        top_categories = list({opp.category for opp in recommendation.top_opportunities[:5]})

        advice_parts = [
            f"Based on your {filing_status} filing status and income in the {income_range} range, "
            f"we've identified ${savings:,.0f} in potential savings."
        ]

        if savings > 5000:
            advice_parts.append(
                "Focus on the highest-impact opportunities first — even implementing your top 2-3 recommendations "
                "could meaningfully reduce your tax burden."
            )
        else:
            advice_parts.append(
                "While individual savings may seem modest, implementing multiple recommendations together "
                "can add up to meaningful tax reduction."
            )

        if top_categories:
            advice_parts.append(
                f"Your strongest opportunities are in: {', '.join(top_categories[:3])}. "
                "Consider consulting a tax professional to maximize these benefits."
            )

        return " ".join(advice_parts)

    def _get_income_range(self, agi: float) -> str:
        """Get income range description for context."""
        if agi < 50000:
            return "under $50,000"
        elif agi < 100000:
            return "$50,000-$100,000"
        elif agi < 200000:
            return "$100,000-$200,000"
        elif agi < 500000:
            return "$200,000-$500,000"
        else:
            return "over $500,000"


# Singleton instance
_enhancer_instance: Optional[AIRecommendationEnhancer] = None


def get_ai_enhancer() -> AIRecommendationEnhancer:
    """Get or create the singleton AI enhancer instance."""
    global _enhancer_instance
    if _enhancer_instance is None:
        _enhancer_instance = AIRecommendationEnhancer()
    return _enhancer_instance
