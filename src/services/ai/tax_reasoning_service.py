"""
Tax Reasoning Service.

Specialized service for complex tax reasoning using Claude Opus.
Handles sophisticated tax analysis including:
- Roth conversion strategies
- Entity structure optimization
- Multi-year tax planning
- Estate planning implications
- AMT analysis
- Complex deduction strategies

Usage:
    from services.ai.tax_reasoning_service import get_tax_reasoning_service

    reasoning = get_tax_reasoning_service()

    # Analyze Roth conversion
    result = await reasoning.analyze_roth_conversion(
        traditional_balance=500000,
        current_bracket=0.24,
        projected_retirement_bracket=0.22,
        years_to_retirement=15
    )

    # Entity structure decision
    entity_analysis = await reasoning.analyze_entity_structure(
        gross_revenue=300000,
        business_expenses=80000,
        owner_salary=120000,
        state="CA"
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from config.ai_providers import AIProvider, ModelCapability
from services.ai.unified_ai_service import (
    UnifiedAIService,
    AIResponse,
    get_ai_service,
)

logger = logging.getLogger(__name__)


class ReasoningType(str, Enum):
    """Types of tax reasoning tasks."""
    ROTH_CONVERSION = "roth_conversion"
    ENTITY_STRUCTURE = "entity_structure"
    MULTI_YEAR_PLANNING = "multi_year_planning"
    ESTATE_PLANNING = "estate_planning"
    AMT_ANALYSIS = "amt_analysis"
    DEDUCTION_STRATEGY = "deduction_strategy"
    INCOME_TIMING = "income_timing"
    INVESTMENT_STRATEGY = "investment_strategy"
    GENERAL = "general"


@dataclass
class ReasoningResult:
    """Result of a tax reasoning analysis."""
    question: str
    reasoning_type: ReasoningType
    analysis: str
    recommendation: str
    key_factors: List[str]
    risks: List[str]
    action_items: List[str]
    assumptions: List[str]
    irc_references: List[str]
    confidence: float
    requires_professional_review: bool
    raw_response: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityComparison:
    """Comparison of business entity structures."""
    entity_type: str  # "sole_prop", "llc", "s_corp", "c_corp"
    annual_tax: float
    se_tax: float
    total_tax: float
    qbi_deduction: float
    complexity: str  # "low", "medium", "high"
    compliance_cost: float
    key_benefits: List[str]
    key_drawbacks: List[str]


@dataclass
class RothConversionAnalysis:
    """Analysis of Roth conversion strategy."""
    convert_recommended: bool
    optimal_conversion_amount: float
    tax_cost: float
    projected_benefit: float
    breakeven_years: int
    strategy_summary: str
    year_by_year: List[Dict[str, Any]]
    risks: List[str]


# =============================================================================
# REASONING PROMPTS
# =============================================================================

BASE_SYSTEM_PROMPT = """You are a senior tax partner at a Big 4 accounting firm with 30 years
of experience in complex tax planning. You provide sophisticated analysis that considers
all relevant factors, risks, and implications.

CRITICAL REQUIREMENTS:
1. Think step-by-step through complex scenarios
2. Consider federal AND state tax implications
3. Account for all relevant taxes (income, SE, FICA, NIIT, AMT)
4. Note phase-outs and limitations
5. Cite specific IRC sections
6. Identify risks and compliance considerations
7. Provide actionable recommendations
8. Flag when professional consultation is essential

Structure your analysis:
1. Understanding of the situation
2. Key factors to consider
3. Step-by-step analysis
4. Quantitative comparison (if applicable)
5. Recommendation with reasoning
6. Important caveats and risks
7. Action items"""


ROTH_CONVERSION_PROMPT = """Analyze this Roth conversion scenario:

**Current Situation:**
- Traditional IRA/401(k) Balance: ${balance:,.0f}
- Current Marginal Tax Bracket: {current_bracket:.0%}
- Current Age: {current_age}
- Years to Retirement: {years_to_retirement}
- Filing Status: {filing_status}

**Projected Retirement:**
- Expected Retirement Bracket: {retirement_bracket:.0%}
- Social Security Expected: ${social_security:,.0f}/year
- Other Retirement Income: ${other_income:,.0f}/year
- State of Retirement: {state}

**Analysis Required:**
1. Should the client convert to Roth? Full or partial?
2. What is the optimal annual conversion amount?
3. Calculate the break-even point in years
4. Consider IRMAA implications if applicable
5. Factor in RMD requirements
6. Account for estate planning goals

Provide a year-by-year conversion strategy if partial conversion is recommended."""


ENTITY_STRUCTURE_PROMPT = """Analyze the optimal business entity structure:

**Business Information:**
- Gross Revenue: ${gross_revenue:,.0f}
- Business Expenses: ${expenses:,.0f}
- Net Business Income: ${net_income:,.0f}
- Owner's Target Salary: ${salary:,.0f}
- State: {state}
- Industry: {industry}
- Number of Employees: {employees}

**Owner Information:**
- Filing Status: {filing_status}
- Other Household Income: ${other_income:,.0f}
- Current Entity: {current_entity}

**Compare these structures:**
1. Sole Proprietorship (Schedule C)
2. Single-Member LLC (default tax treatment)
3. S-Corporation (with reasonable salary)
4. C-Corporation (if applicable)

For each structure, analyze:
- Total income tax liability
- Self-employment / FICA taxes
- QBI deduction (Section 199A)
- State-specific considerations
- Compliance costs and complexity
- Liability protection
- Future flexibility

Recommend the optimal structure with specific reasoning."""


MULTI_YEAR_PROMPT = """Develop a multi-year tax strategy:

**Current Situation:**
{current_situation}

**Major Events:**
{life_events}

**Financial Goals:**
{goals}

**Time Horizon:** {years} years

Create a comprehensive strategy covering:
1. Income timing and bracket management
2. Retirement contribution optimization
3. Investment tax efficiency
4. Charitable giving strategy
5. Estate planning considerations

Provide year-by-year action items with estimated tax impact."""


AMT_ANALYSIS_PROMPT = """Analyze Alternative Minimum Tax (AMT) exposure:

**Income and Deductions:**
- Regular Taxable Income: ${regular_income:,.0f}
- State and Local Tax Deduction: ${salt:,.0f}
- Miscellaneous Itemized Deductions: ${misc_deductions:,.0f}
- ISO Exercise Spread: ${iso_spread:,.0f}
- Tax-Exempt Interest: ${tax_exempt_interest:,.0f}

**Filing Information:**
- Filing Status: {filing_status}
- Dependents: {dependents}
- State: {state}

Analyze:
1. Calculate AMT exposure
2. Identify AMT triggers
3. Recommend AMT mitigation strategies
4. Model ISO exercise timing if applicable
5. Consider multi-year AMT credit planning"""


ESTATE_PLANNING_PROMPT = """Analyze estate and gift tax implications:

**Estate Information:**
- Estimated Estate Value: ${estate_value:,.0f}
- Annual Gifting Capacity: ${annual_gifting:,.0f}
- Existing Trust Structures: {trusts}
- Beneficiaries: {beneficiaries}
- State of Residence: {state}

**Goals:**
{goals}

Analyze:
1. Federal estate tax exposure
2. State estate/inheritance tax
3. Lifetime gift strategies
4. Trust planning opportunities
5. Generation-skipping considerations
6. Income tax basis planning (step-up)
7. Charitable planning opportunities

Coordinate estate plan with income tax strategy."""


# =============================================================================
# TAX REASONING SERVICE
# =============================================================================

class TaxReasoningService:
    """
    Specialized service for complex tax reasoning using Claude Opus.

    Features:
    - Deep multi-factor tax analysis
    - Step-by-step reasoning
    - Quantitative modeling
    - Risk assessment
    - Actionable recommendations
    """

    def __init__(self, ai_service: Optional[UnifiedAIService] = None):
        self.ai_service = ai_service or get_ai_service()

    async def analyze(
        self,
        problem: str,
        context: str,
        reasoning_type: ReasoningType = ReasoningType.GENERAL
    ) -> ReasoningResult:
        """
        Perform general tax reasoning analysis.

        Args:
            problem: The tax problem to analyze
            context: Additional context
            reasoning_type: Type of reasoning task

        Returns:
            ReasoningResult with analysis
        """
        response = await self.ai_service.reason(
            problem=problem,
            context=context
        )

        return self._parse_reasoning_response(
            question=problem,
            reasoning_type=reasoning_type,
            response=response
        )

    async def analyze_roth_conversion(
        self,
        traditional_balance: float,
        current_bracket: float,
        projected_retirement_bracket: float,
        current_age: int,
        years_to_retirement: int,
        filing_status: str = "married_filing_jointly",
        social_security: float = 0,
        other_retirement_income: float = 0,
        state: str = "CA"
    ) -> ReasoningResult:
        """
        Analyze Roth conversion strategy.

        Args:
            traditional_balance: Current traditional IRA/401k balance
            current_bracket: Current marginal tax bracket (e.g., 0.24 for 24%)
            projected_retirement_bracket: Expected retirement bracket
            current_age: Client's current age
            years_to_retirement: Years until planned retirement
            filing_status: Tax filing status
            social_security: Expected annual Social Security
            other_retirement_income: Other expected retirement income
            state: State of residence/retirement

        Returns:
            ReasoningResult with Roth conversion analysis
        """
        prompt = ROTH_CONVERSION_PROMPT.format(
            balance=traditional_balance,
            current_bracket=current_bracket,
            current_age=current_age,
            years_to_retirement=years_to_retirement,
            retirement_bracket=projected_retirement_bracket,
            filing_status=filing_status,
            social_security=social_security,
            other_income=other_retirement_income,
            state=state
        )

        response = await self.ai_service.reason(
            problem=prompt,
            context="Roth conversion strategy analysis"
        )

        result = self._parse_reasoning_response(
            question="Roth conversion analysis",
            reasoning_type=ReasoningType.ROTH_CONVERSION,
            response=response
        )

        result.metadata.update({
            "traditional_balance": traditional_balance,
            "current_bracket": current_bracket,
            "retirement_bracket": projected_retirement_bracket,
            "years_to_retirement": years_to_retirement,
        })

        return result

    async def analyze_entity_structure(
        self,
        gross_revenue: float,
        business_expenses: float,
        owner_salary: float,
        state: str,
        filing_status: str = "married_filing_jointly",
        other_income: float = 0,
        current_entity: str = "sole_prop",
        industry: str = "Professional Services",
        employees: int = 0
    ) -> ReasoningResult:
        """
        Analyze optimal business entity structure.

        Args:
            gross_revenue: Annual gross business revenue
            business_expenses: Annual business expenses
            owner_salary: Target owner salary (for S-Corp)
            state: State of operation
            filing_status: Owner's tax filing status
            other_income: Other household income
            current_entity: Current entity structure
            industry: Business industry
            employees: Number of employees

        Returns:
            ReasoningResult with entity comparison
        """
        net_income = gross_revenue - business_expenses

        prompt = ENTITY_STRUCTURE_PROMPT.format(
            gross_revenue=gross_revenue,
            expenses=business_expenses,
            net_income=net_income,
            salary=owner_salary,
            state=state,
            filing_status=filing_status,
            other_income=other_income,
            current_entity=current_entity,
            industry=industry,
            employees=employees
        )

        response = await self.ai_service.reason(
            problem=prompt,
            context="Business entity structure optimization"
        )

        result = self._parse_reasoning_response(
            question="Entity structure analysis",
            reasoning_type=ReasoningType.ENTITY_STRUCTURE,
            response=response
        )

        result.metadata.update({
            "gross_revenue": gross_revenue,
            "net_income": net_income,
            "proposed_salary": owner_salary,
            "state": state,
        })

        return result

    async def analyze_multi_year_strategy(
        self,
        current_situation: str,
        life_events: str,
        goals: str,
        years: int = 5
    ) -> ReasoningResult:
        """
        Develop multi-year tax strategy.

        Args:
            current_situation: Description of current tax situation
            life_events: Major life events expected (retirement, sale, etc.)
            goals: Financial and tax goals
            years: Planning horizon

        Returns:
            ReasoningResult with multi-year strategy
        """
        prompt = MULTI_YEAR_PROMPT.format(
            current_situation=current_situation,
            life_events=life_events,
            goals=goals,
            years=years
        )

        response = await self.ai_service.reason(
            problem=prompt,
            context="Multi-year tax planning"
        )

        result = self._parse_reasoning_response(
            question="Multi-year tax strategy",
            reasoning_type=ReasoningType.MULTI_YEAR_PLANNING,
            response=response
        )

        result.metadata["planning_horizon_years"] = years

        return result

    async def analyze_amt_exposure(
        self,
        regular_income: float,
        salt_deduction: float,
        misc_deductions: float = 0,
        iso_spread: float = 0,
        tax_exempt_interest: float = 0,
        filing_status: str = "married_filing_jointly",
        dependents: int = 0,
        state: str = "CA"
    ) -> ReasoningResult:
        """
        Analyze Alternative Minimum Tax exposure.

        Args:
            regular_income: Regular taxable income
            salt_deduction: State and local tax deduction
            misc_deductions: Other miscellaneous deductions
            iso_spread: Incentive stock option exercise spread
            tax_exempt_interest: Private activity bond interest
            filing_status: Tax filing status
            dependents: Number of dependents
            state: State of residence

        Returns:
            ReasoningResult with AMT analysis
        """
        prompt = AMT_ANALYSIS_PROMPT.format(
            regular_income=regular_income,
            salt=salt_deduction,
            misc_deductions=misc_deductions,
            iso_spread=iso_spread,
            tax_exempt_interest=tax_exempt_interest,
            filing_status=filing_status,
            dependents=dependents,
            state=state
        )

        response = await self.ai_service.reason(
            problem=prompt,
            context="AMT exposure analysis"
        )

        result = self._parse_reasoning_response(
            question="AMT analysis",
            reasoning_type=ReasoningType.AMT_ANALYSIS,
            response=response
        )

        result.metadata.update({
            "regular_income": regular_income,
            "salt_deduction": salt_deduction,
            "iso_spread": iso_spread,
        })

        return result

    async def analyze_estate_plan(
        self,
        estate_value: float,
        annual_gifting: float,
        trusts: str,
        beneficiaries: str,
        state: str,
        goals: str
    ) -> ReasoningResult:
        """
        Analyze estate planning implications.

        Args:
            estate_value: Estimated total estate value
            annual_gifting: Annual gifting capacity/interest
            trusts: Description of existing trust structures
            beneficiaries: Description of beneficiaries
            state: State of residence
            goals: Estate planning goals

        Returns:
            ReasoningResult with estate analysis
        """
        prompt = ESTATE_PLANNING_PROMPT.format(
            estate_value=estate_value,
            annual_gifting=annual_gifting,
            trusts=trusts,
            beneficiaries=beneficiaries,
            state=state,
            goals=goals
        )

        response = await self.ai_service.reason(
            problem=prompt,
            context="Estate planning analysis"
        )

        result = self._parse_reasoning_response(
            question="Estate planning analysis",
            reasoning_type=ReasoningType.ESTATE_PLANNING,
            response=response
        )

        result.metadata.update({
            "estate_value": estate_value,
            "state": state,
        })

        return result

    async def analyze_deduction_strategy(
        self,
        income: float,
        current_deductions: Dict[str, float],
        potential_deductions: Dict[str, float],
        filing_status: str,
        state: str
    ) -> ReasoningResult:
        """
        Analyze deduction optimization strategy.

        Args:
            income: Total income
            current_deductions: Current itemized deductions
            potential_deductions: Potential additional deductions
            filing_status: Filing status
            state: State of residence

        Returns:
            ReasoningResult with deduction strategy
        """
        current_str = "\n".join([f"- {k}: ${v:,.0f}" for k, v in current_deductions.items()])
        potential_str = "\n".join([f"- {k}: ${v:,.0f}" for k, v in potential_deductions.items()])

        prompt = f"""Analyze deduction optimization strategy:

**Income:** ${income:,.0f}
**Filing Status:** {filing_status}
**State:** {state}

**Current Deductions:**
{current_str}

**Potential Additional Deductions:**
{potential_str}

Analyze:
1. Standard vs. itemized comparison
2. Bunching strategy viability
3. SALT cap impact
4. Charitable giving optimization
5. Timing strategies
6. State tax considerations

Recommend optimal deduction strategy."""

        response = await self.ai_service.reason(
            problem=prompt,
            context="Deduction strategy optimization"
        )

        return self._parse_reasoning_response(
            question="Deduction strategy",
            reasoning_type=ReasoningType.DEDUCTION_STRATEGY,
            response=response
        )

    def _parse_reasoning_response(
        self,
        question: str,
        reasoning_type: ReasoningType,
        response: AIResponse
    ) -> ReasoningResult:
        """Parse AI response into ReasoningResult."""
        content = response.content

        # Extract key components
        key_factors = self._extract_list_items(content, ["key factors", "factors to consider", "considerations"])
        risks = self._extract_list_items(content, ["risks", "caveats", "concerns", "warnings"])
        action_items = self._extract_list_items(content, ["action items", "next steps", "recommendations", "action steps"])
        assumptions = self._extract_list_items(content, ["assumptions", "assuming"])
        irc_refs = self._extract_irc_references(content)

        # Determine if professional review is needed
        requires_professional = self._requires_professional_review(content, reasoning_type)

        # Extract recommendation
        recommendation = self._extract_recommendation(content)

        # Estimate confidence
        confidence = self._estimate_confidence(content, irc_refs, reasoning_type)

        return ReasoningResult(
            question=question,
            reasoning_type=reasoning_type,
            analysis=content,
            recommendation=recommendation,
            key_factors=key_factors,
            risks=risks,
            action_items=action_items,
            assumptions=assumptions,
            irc_references=irc_refs,
            confidence=confidence,
            requires_professional_review=requires_professional,
            raw_response=content,
            metadata={
                "model": response.model,
                "provider": response.provider.value,
                "tokens": response.input_tokens + response.output_tokens,
                "latency_ms": response.latency_ms,
            }
        )

    def _extract_list_items(
        self,
        content: str,
        section_keywords: List[str]
    ) -> List[str]:
        """Extract list items from sections matching keywords."""
        items = []
        lines = content.split('\n')

        in_section = False
        for line in lines:
            line_lower = line.lower()

            # Check if we're entering a relevant section
            if any(kw in line_lower for kw in section_keywords):
                in_section = True
                continue

            # Check if we're leaving the section (new heading)
            if in_section and line.strip() and (line.startswith('#') or line.startswith('**')):
                in_section = False
                continue

            # Extract list items
            if in_section:
                stripped = line.strip()
                if stripped and (stripped[0].isdigit() or stripped.startswith('-') or stripped.startswith('•')):
                    cleaned = stripped.lstrip('0123456789.-•) ').strip()
                    if cleaned:
                        items.append(cleaned)

        return items[:10]  # Limit to 10 items

    def _extract_irc_references(self, content: str) -> List[str]:
        """Extract IRC section references."""
        import re
        refs = []

        # IRC Section patterns
        patterns = [
            r'IRC (?:Section |§)?(\d+[a-z]?(?:\([a-z0-9]+\))?)',
            r'Section (\d+[a-z]?(?:\([a-z0-9]+\))?)',
            r'§(\d+[a-z]?(?:\([a-z0-9]+\))?)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            refs.extend([f"IRC §{m}" for m in matches])

        return list(set(refs))

    def _extract_recommendation(self, content: str) -> str:
        """Extract the main recommendation."""
        import re

        # Look for recommendation section
        patterns = [
            r'(?:Recommendation|Recommended|I recommend)[:\s]*([^\n]+(?:\n[^\n#*]+)*)',
            r'(?:In conclusion|Overall)[,:\s]*([^\n]+(?:\n[^\n#*]+)*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                rec = match.group(1).strip()
                return rec[:500] if len(rec) > 500 else rec

        # If no explicit recommendation, use last paragraph
        paragraphs = content.split('\n\n')
        if paragraphs:
            last = paragraphs[-1].strip()
            return last[:500] if len(last) > 500 else last

        return "See detailed analysis above."

    def _requires_professional_review(
        self,
        content: str,
        reasoning_type: ReasoningType
    ) -> bool:
        """Determine if professional review is required."""
        content_lower = content.lower()

        # High-risk indicators
        high_risk_phrases = [
            "consult a tax professional",
            "seek professional advice",
            "complex situation",
            "significant risk",
            "irs audit",
            "substantial penalty",
            "professional guidance",
            "beyond the scope",
        ]

        if any(phrase in content_lower for phrase in high_risk_phrases):
            return True

        # Certain reasoning types always need review
        high_risk_types = [
            ReasoningType.ESTATE_PLANNING,
            ReasoningType.ENTITY_STRUCTURE,
        ]

        if reasoning_type in high_risk_types:
            return True

        return False

    def _estimate_confidence(
        self,
        content: str,
        irc_refs: List[str],
        reasoning_type: ReasoningType
    ) -> float:
        """Estimate confidence in the reasoning."""
        confidence = 0.6  # Base confidence

        # IRC references boost confidence
        if len(irc_refs) > 3:
            confidence += 0.15
        elif len(irc_refs) > 0:
            confidence += 0.08

        # Detailed analysis boosts confidence
        if len(content) > 3000:
            confidence += 0.1

        # Quantitative analysis boosts confidence
        if '$' in content and any(c.isdigit() for c in content):
            confidence += 0.05

        # Uncertainty markers decrease confidence
        uncertainty_phrases = ["uncertain", "unclear", "may vary", "depends on"]
        for phrase in uncertainty_phrases:
            if phrase in content.lower():
                confidence -= 0.05

        return max(0.3, min(0.95, confidence))


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_tax_reasoning_service: Optional[TaxReasoningService] = None


def get_tax_reasoning_service() -> TaxReasoningService:
    """Get the singleton tax reasoning service instance."""
    global _tax_reasoning_service
    if _tax_reasoning_service is None:
        _tax_reasoning_service = TaxReasoningService()
    return _tax_reasoning_service


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TaxReasoningService",
    "ReasoningType",
    "ReasoningResult",
    "EntityComparison",
    "RothConversionAnalysis",
    "get_tax_reasoning_service",
]
