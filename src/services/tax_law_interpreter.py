"""
AI-Powered Tax Law Interpreter.

Uses Claude for complex tax law interpretation:
- Interpreting ambiguous tax code sections
- Applying regulations to specific situations
- Analyzing tax court precedents
- Generating defensible positions
- Risk assessment for tax positions

Usage:
    from services.tax_law_interpreter import get_tax_law_interpreter

    interpreter = get_tax_law_interpreter()

    # Interpret a specific IRC section
    interpretation = await interpreter.interpret_code_section(
        section="162(a)",
        situation=TaxSituation(description="Home office deduction for remote worker")
    )

    # Analyze a tax position
    analysis = await interpreter.analyze_tax_position(
        position="Claiming vehicle as 100% business use",
        facts={"miles_driven": 15000, "business_miles": 12000}
    )
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk levels for tax positions."""
    SUBSTANTIAL_AUTHORITY = "substantial_authority"  # >40% chance of success
    REASONABLE_BASIS = "reasonable_basis"            # >20% chance of success
    DISCLOSED_POSITION = "disclosed_position"        # Requires disclosure
    HIGH_RISK = "high_risk"                          # <20% chance, penalty risk
    FRIVOLOUS = "frivolous"                          # No legal basis


class PositionStrength(str, Enum):
    """Strength of a tax position."""
    STRONG = "strong"           # Well-supported by law
    MODERATE = "moderate"       # Supportable but debatable
    WEAK = "weak"               # Questionable support
    UNSUPPORTED = "unsupported" # No clear support


@dataclass
class TaxSituation:
    """A specific tax situation to analyze."""
    description: str
    facts: Dict[str, Any] = field(default_factory=dict)
    tax_year: int = 2025
    filing_status: Optional[str] = None
    state: Optional[str] = None
    prior_positions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "facts": self.facts,
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "state": self.state,
            "prior_positions": self.prior_positions,
        }


@dataclass
class LegalAuthority:
    """A legal authority supporting an interpretation."""
    authority_type: str  # "irc", "regulation", "case", "ruling", "publication"
    citation: str
    title: str
    relevance: str
    supports_position: bool
    strength: PositionStrength

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authority_type": self.authority_type,
            "citation": self.citation,
            "title": self.title,
            "relevance": self.relevance,
            "supports_position": self.supports_position,
            "strength": self.strength.value,
        }


@dataclass
class TaxInterpretation:
    """Interpretation of a tax code section."""
    section: str
    situation: TaxSituation
    primary_interpretation: str
    alternative_interpretations: List[str]
    supporting_authorities: List[LegalAuthority]
    contrary_authorities: List[LegalAuthority]
    risk_level: RiskLevel
    confidence: float  # 0-1
    action_recommendations: List[str]
    documentation_required: List[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section": self.section,
            "situation": self.situation.to_dict(),
            "primary_interpretation": self.primary_interpretation,
            "alternative_interpretations": self.alternative_interpretations,
            "supporting_authorities": [a.to_dict() for a in self.supporting_authorities],
            "contrary_authorities": [a.to_dict() for a in self.contrary_authorities],
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "action_recommendations": self.action_recommendations,
            "documentation_required": self.documentation_required,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class TaxPositionAnalysis:
    """Analysis of a specific tax position."""
    position: str
    facts: Dict[str, Any]
    position_strength: PositionStrength
    risk_level: RiskLevel
    success_probability: float  # 0-1
    supporting_arguments: List[str]
    weaknesses: List[str]
    irs_likely_challenges: List[str]
    defense_strategies: List[str]
    documentation_checklist: List[str]
    alternative_positions: List[str]
    penalty_exposure: Dict[str, Any]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "facts": self.facts,
            "position_strength": self.position_strength.value,
            "risk_level": self.risk_level.value,
            "success_probability": self.success_probability,
            "supporting_arguments": self.supporting_arguments,
            "weaknesses": self.weaknesses,
            "irs_likely_challenges": self.irs_likely_challenges,
            "defense_strategies": self.defense_strategies,
            "documentation_checklist": self.documentation_checklist,
            "alternative_positions": self.alternative_positions,
            "penalty_exposure": self.penalty_exposure,
            "generated_at": self.generated_at.isoformat(),
        }


class ClaudeTaxLawInterpreter:
    """
    Claude-powered tax law interpreter.

    Provides CPA-level tax law analysis:
    - Interprets complex IRC sections
    - Applies regulations to specific facts
    - Identifies relevant case law
    - Assesses position risk levels
    - Generates defensible positions
    """

    # Common IRC sections and their topics
    IRC_SECTIONS = {
        "61": "Gross Income Defined",
        "62": "Adjusted Gross Income",
        "63": "Taxable Income Defined",
        "67": "2% Miscellaneous Itemized Deductions",
        "72": "Annuities; Certain Proceeds of Endowment",
        "74": "Prizes and Awards",
        "79": "Group-Term Life Insurance",
        "83": "Property Transferred in Connection with Services",
        "85": "Unemployment Compensation",
        "101": "Life Insurance Proceeds",
        "102": "Gifts and Inheritances",
        "104": "Compensation for Injuries or Sickness",
        "105": "Amounts Received Under Accident and Health Plans",
        "106": "Employer-Provided Health Coverage",
        "108": "Discharge of Indebtedness",
        "117": "Qualified Scholarships",
        "119": "Meals or Lodging for Employer's Convenience",
        "121": "Exclusion of Gain from Sale of Principal Residence",
        "125": "Cafeteria Plans",
        "127": "Educational Assistance Programs",
        "132": "Fringe Benefits",
        "162": "Trade or Business Expenses",
        "163": "Interest Deduction",
        "164": "Taxes",
        "165": "Losses",
        "166": "Bad Debts",
        "167": "Depreciation",
        "168": "MACRS Depreciation",
        "170": "Charitable Contributions",
        "179": "Section 179 Expensing",
        "183": "Activities Not Engaged In For Profit",
        "199A": "Qualified Business Income Deduction",
        "212": "Production of Income Expenses",
        "213": "Medical Expenses",
        "217": "Moving Expenses",
        "219": "Retirement Savings",
        "221": "Student Loan Interest",
        "262": "Personal Expenses",
        "263": "Capital Expenditures",
        "267": "Related Party Transactions",
        "274": "Entertainment and Meals",
        "280A": "Home Office",
        "401": "Qualified Pension Plans",
        "402": "Distributions from Qualified Plans",
        "408": "Individual Retirement Accounts",
        "408A": "Roth IRAs",
        "409A": "Nonqualified Deferred Compensation",
        "469": "Passive Activity Losses",
        "1001": "Gain or Loss on Sale",
        "1014": "Stepped-Up Basis at Death",
        "1031": "Like-Kind Exchanges",
        "1202": "QSBS Exclusion",
    }

    def __init__(self, ai_service=None):
        """
        Initialize tax law interpreter.

        Args:
            ai_service: UnifiedAIService instance (lazy-loaded if not provided)
        """
        self._ai_service = ai_service

    @property
    def ai_service(self):
        """Lazy-load AI service."""
        if self._ai_service is None:
            from services.ai.unified_ai_service import get_ai_service
            self._ai_service = get_ai_service()
        return self._ai_service

    async def interpret_code_section(
        self,
        section: str,
        situation: TaxSituation,
    ) -> TaxInterpretation:
        """
        Interpret an IRC section as applied to a specific situation.

        Args:
            section: IRC section number (e.g., "162(a)", "199A")
            situation: The specific tax situation

        Returns:
            TaxInterpretation with analysis and recommendations
        """
        section_title = self.IRC_SECTIONS.get(
            section.split("(")[0],
            f"Section {section}"
        )

        prompt = f"""You are a senior tax attorney interpreting Internal Revenue Code Section {section} ({section_title}).

SITUATION:
{json.dumps(situation.to_dict(), indent=2)}

Analyze how IRC Section {section} applies to this situation.

Consider:
1. Plain language of the statute
2. Treasury Regulations (Treas. Reg.)
3. Relevant Tax Court and Circuit Court cases
4. IRS Revenue Rulings and Revenue Procedures
5. IRS Publications and Instructions
6. Private Letter Rulings (for guidance only)

Provide your analysis as JSON:
{{
    "primary_interpretation": "Most likely correct interpretation",
    "alternative_interpretations": ["Other possible interpretations"],
    "supporting_authorities": [
        {{
            "authority_type": "irc|regulation|case|ruling|publication",
            "citation": "Full citation",
            "title": "Name/title",
            "relevance": "How it applies",
            "supports_position": true,
            "strength": "strong|moderate|weak|unsupported"
        }}
    ],
    "contrary_authorities": [same format],
    "risk_level": "substantial_authority|reasonable_basis|disclosed_position|high_risk|frivolous",
    "confidence": 0.0-1.0,
    "action_recommendations": ["What the taxpayer should do"],
    "documentation_required": ["Documentation needed to support position"]
}}

Be thorough but practical. Focus on the most relevant authorities."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            # Parse authorities
            supporting = [
                LegalAuthority(
                    authority_type=a.get("authority_type", "unknown"),
                    citation=a.get("citation", ""),
                    title=a.get("title", ""),
                    relevance=a.get("relevance", ""),
                    supports_position=a.get("supports_position", True),
                    strength=PositionStrength(a.get("strength", "moderate")),
                )
                for a in data.get("supporting_authorities", [])
            ]

            contrary = [
                LegalAuthority(
                    authority_type=a.get("authority_type", "unknown"),
                    citation=a.get("citation", ""),
                    title=a.get("title", ""),
                    relevance=a.get("relevance", ""),
                    supports_position=a.get("supports_position", False),
                    strength=PositionStrength(a.get("strength", "moderate")),
                )
                for a in data.get("contrary_authorities", [])
            ]

            return TaxInterpretation(
                section=section,
                situation=situation,
                primary_interpretation=data.get("primary_interpretation", ""),
                alternative_interpretations=data.get("alternative_interpretations", []),
                supporting_authorities=supporting,
                contrary_authorities=contrary,
                risk_level=RiskLevel(data.get("risk_level", "reasonable_basis")),
                confidence=data.get("confidence", 0.7),
                action_recommendations=data.get("action_recommendations", []),
                documentation_required=data.get("documentation_required", []),
            )

        except Exception as e:
            logger.error(f"Failed to interpret IRC Section {section}: {e}")
            return TaxInterpretation(
                section=section,
                situation=situation,
                primary_interpretation=f"Unable to complete analysis. Please consult a tax professional for IRC Section {section}.",
                alternative_interpretations=[],
                supporting_authorities=[],
                contrary_authorities=[],
                risk_level=RiskLevel.HIGH_RISK,
                confidence=0.0,
                action_recommendations=["Consult with a qualified tax professional"],
                documentation_required=["Maintain all relevant records"],
            )

    async def analyze_tax_position(
        self,
        position: str,
        facts: Dict[str, Any],
        tax_year: int = 2025,
    ) -> TaxPositionAnalysis:
        """
        Analyze the strength and risk of a specific tax position.

        Args:
            position: The tax position being taken
            facts: Relevant facts supporting the position
            tax_year: Tax year

        Returns:
            TaxPositionAnalysis with risk assessment and recommendations
        """
        prompt = f"""You are a senior tax attorney analyzing a tax position for a client.

TAX POSITION: {position}

FACTS:
{json.dumps(facts, indent=2)}

TAX YEAR: {tax_year}

Analyze this position considering:
1. Legal support for the position
2. IRS audit likelihood and likely challenges
3. Penalty exposure (accuracy-related, substantial understatement)
4. Documentation requirements
5. Alternative positions that might be safer

Provide analysis as JSON:
{{
    "position_strength": "strong|moderate|weak|unsupported",
    "risk_level": "substantial_authority|reasonable_basis|disclosed_position|high_risk|frivolous",
    "success_probability": 0.0-1.0,
    "supporting_arguments": ["Arguments supporting the position"],
    "weaknesses": ["Weaknesses in the position"],
    "irs_likely_challenges": ["How IRS would likely challenge this"],
    "defense_strategies": ["How to defend if challenged"],
    "documentation_checklist": ["Documents needed"],
    "alternative_positions": ["Safer alternative approaches"],
    "penalty_exposure": {{
        "accuracy_penalty_risk": "low|medium|high",
        "substantial_understatement_risk": "low|medium|high",
        "negligence_penalty_risk": "low|medium|high",
        "potential_penalty_amount": "estimated range"
    }}
}}

Be practical and specific to this situation."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return TaxPositionAnalysis(
                position=position,
                facts=facts,
                position_strength=PositionStrength(data.get("position_strength", "moderate")),
                risk_level=RiskLevel(data.get("risk_level", "reasonable_basis")),
                success_probability=data.get("success_probability", 0.5),
                supporting_arguments=data.get("supporting_arguments", []),
                weaknesses=data.get("weaknesses", []),
                irs_likely_challenges=data.get("irs_likely_challenges", []),
                defense_strategies=data.get("defense_strategies", []),
                documentation_checklist=data.get("documentation_checklist", []),
                alternative_positions=data.get("alternative_positions", []),
                penalty_exposure=data.get("penalty_exposure", {}),
            )

        except Exception as e:
            logger.error(f"Failed to analyze tax position: {e}")
            return TaxPositionAnalysis(
                position=position,
                facts=facts,
                position_strength=PositionStrength.WEAK,
                risk_level=RiskLevel.HIGH_RISK,
                success_probability=0.0,
                supporting_arguments=[],
                weaknesses=["Analysis failed - position requires professional review"],
                irs_likely_challenges=["Unknown"],
                defense_strategies=["Consult tax professional"],
                documentation_checklist=["Maintain all records"],
                alternative_positions=["Consult tax professional for alternatives"],
                penalty_exposure={"note": "Unable to assess"},
            )

    async def compare_positions(
        self,
        positions: List[Dict[str, Any]],
        facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare multiple tax positions to recommend the best approach.

        Args:
            positions: List of positions to compare
            facts: Common facts for all positions

        Returns:
            Comparison with recommended position
        """
        prompt = f"""Compare these tax positions and recommend the best approach:

POSITIONS:
{json.dumps(positions, indent=2)}

FACTS:
{json.dumps(facts, indent=2)}

For each position, assess:
1. Legal strength
2. Risk level
3. Tax savings potential
4. Audit risk
5. Documentation burden

Return as JSON:
{{
    "comparisons": [
        {{
            "position": "description",
            "legal_strength": "strong|moderate|weak",
            "risk_level": "low|medium|high",
            "tax_savings": "estimated savings",
            "audit_risk": "low|medium|high",
            "documentation_burden": "low|medium|high",
            "score": 1-10
        }}
    ],
    "recommended_position": "best position",
    "recommendation_reasoning": "why this is best",
    "caveats": ["important considerations"]
}}"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except Exception as e:
            logger.error(f"Failed to compare positions: {e}")
            return {
                "error": str(e),
                "recommendation": "Please consult a tax professional",
            }

    async def draft_position_memo(
        self,
        position: str,
        facts: Dict[str, Any],
        analysis: TaxPositionAnalysis,
    ) -> str:
        """
        Draft a tax position memorandum.

        Args:
            position: The tax position
            facts: Supporting facts
            analysis: Prior analysis of the position

        Returns:
            Formatted memo text
        """
        prompt = f"""Draft a professional tax position memorandum.

POSITION: {position}

FACTS:
{json.dumps(facts, indent=2)}

ANALYSIS:
{json.dumps(analysis.to_dict(), indent=2)}

Format as a professional memo with:
1. Issue statement
2. Conclusion
3. Facts
4. Analysis (citing authorities)
5. Authorities supporting position
6. Contrary authorities and distinctions
7. Recommendations

Write in formal legal memorandum style."""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.ANTHROPIC,
                system_prompt=self._get_system_prompt(),
                max_tokens=2000,
            )

            return response.content.strip()

        except Exception as e:
            logger.error(f"Failed to draft position memo: {e}")
            return f"Unable to generate memo. Error: {str(e)}"

    def _get_system_prompt(self) -> str:
        """Get system prompt for tax law analysis."""
        return """You are a senior tax attorney with 25 years of experience in federal tax law.

Your expertise includes:
- Internal Revenue Code interpretation
- Treasury Regulations analysis
- Tax Court and federal court case law
- IRS guidance (Revenue Rulings, Revenue Procedures, Notices)
- Tax planning and controversy

When analyzing tax issues:
1. Be thorough but practical
2. Cite specific authorities (IRC sections, Treas. Reg., cases)
3. Acknowledge uncertainty where it exists
4. Consider both IRS and taxpayer perspectives
5. Focus on defensible positions
6. Note documentation requirements

Always maintain professional standards:
- Circular 230 compliance
- Reasonable basis for positions
- Proper disclosure when required

Never advise positions that are frivolous or lack legal support."""


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_tax_law_interpreter: Optional[ClaudeTaxLawInterpreter] = None


def get_tax_law_interpreter() -> ClaudeTaxLawInterpreter:
    """Get the singleton tax law interpreter instance."""
    global _tax_law_interpreter
    if _tax_law_interpreter is None:
        _tax_law_interpreter = ClaudeTaxLawInterpreter()
    return _tax_law_interpreter


__all__ = [
    "ClaudeTaxLawInterpreter",
    "TaxSituation",
    "TaxInterpretation",
    "TaxPositionAnalysis",
    "LegalAuthority",
    "RiskLevel",
    "PositionStrength",
    "get_tax_law_interpreter",
]
