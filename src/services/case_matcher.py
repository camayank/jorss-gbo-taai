"""
AI-Powered Case Matcher using OpenAI Embeddings.

Uses embeddings to find similar cases and situations:
- Find similar past client situations
- Match to relevant tax court cases
- Identify applicable IRS rulings
- Suggest strategies used in similar cases

Usage:
    from services.case_matcher import get_case_matcher

    matcher = get_case_matcher()

    # Find similar situations
    matches = await matcher.find_similar_situations(
        "Self-employed consultant claiming home office deduction"
    )

    # Match tax court cases
    cases = await matcher.find_relevant_cases(
        "Hobby loss vs business deduction",
        top_k=5
    )
"""

import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CaseType(str, Enum):
    """Types of cases in the knowledge base."""
    TAX_COURT = "tax_court"
    CIRCUIT_COURT = "circuit_court"
    SUPREME_COURT = "supreme_court"
    IRS_RULING = "irs_ruling"
    CLIENT_SITUATION = "client_situation"
    STRATEGY = "strategy"


class CaseOutcome(str, Enum):
    """Outcome of a tax case."""
    TAXPAYER_WIN = "taxpayer_win"
    IRS_WIN = "irs_win"
    SPLIT_DECISION = "split_decision"
    SETTLED = "settled"
    UNKNOWN = "unknown"


@dataclass
class CaseMatch:
    """A matched case from the knowledge base."""
    case_id: str
    case_type: CaseType
    title: str
    citation: Optional[str]
    year: Optional[int]
    summary: str
    key_facts: List[str]
    outcome: CaseOutcome
    relevance_score: float  # 0-1
    similarity_score: float  # 0-1 based on embeddings
    key_holdings: List[str]
    applicable_irc_sections: List[str]
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type.value,
            "title": self.title,
            "citation": self.citation,
            "year": self.year,
            "summary": self.summary,
            "key_facts": self.key_facts,
            "outcome": self.outcome.value,
            "relevance_score": self.relevance_score,
            "similarity_score": self.similarity_score,
            "key_holdings": self.key_holdings,
            "applicable_irc_sections": self.applicable_irc_sections,
            "tags": self.tags,
        }


@dataclass
class StrategyMatch:
    """A matched strategy from similar situations."""
    strategy_id: str
    title: str
    description: str
    applicable_situations: List[str]
    success_rate: float  # 0-1
    typical_savings: Optional[str]
    requirements: List[str]
    risks: List[str]
    similarity_score: float
    source_cases: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "title": self.title,
            "description": self.description,
            "applicable_situations": self.applicable_situations,
            "success_rate": self.success_rate,
            "typical_savings": self.typical_savings,
            "requirements": self.requirements,
            "risks": self.risks,
            "similarity_score": self.similarity_score,
            "source_cases": self.source_cases,
        }


@dataclass
class SituationAnalysis:
    """Analysis of a tax situation with matched cases and strategies."""
    situation: str
    similar_cases: List[CaseMatch]
    recommended_strategies: List[StrategyMatch]
    risk_factors: List[str]
    key_considerations: List[str]
    suggested_research: List[str]
    confidence: float
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "situation": self.situation,
            "similar_cases": [c.to_dict() for c in self.similar_cases],
            "recommended_strategies": [s.to_dict() for s in self.recommended_strategies],
            "risk_factors": self.risk_factors,
            "key_considerations": self.key_considerations,
            "suggested_research": self.suggested_research,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class OpenAICaseMatcher:
    """
    OpenAI-powered case matcher using embeddings.

    Uses embeddings to find semantically similar:
    - Tax court cases
    - IRS rulings
    - Client situations
    - Tax strategies

    The system maintains a knowledge base of cases that can be
    searched using semantic similarity.
    """

    # Sample knowledge base entries (in production, this would be a vector database)
    # These represent the types of cases and strategies we can match against
    SAMPLE_CASES = [
        {
            "id": "tc_comm_1",
            "type": "tax_court",
            "title": "Commissioner v. Groetzinger",
            "citation": "480 U.S. 23 (1987)",
            "year": 1987,
            "summary": "Full-time gambling constitutes a trade or business for tax purposes",
            "key_facts": ["Full-time activity", "Profit motive", "Continuous effort"],
            "outcome": "taxpayer_win",
            "holdings": ["Gambling can be a trade or business if pursued full-time with profit motive"],
            "irc_sections": ["162", "183"],
            "tags": ["gambling", "trade or business", "hobby loss"],
        },
        {
            "id": "tc_hobby_1",
            "type": "tax_court",
            "title": "Nickerson v. Commissioner",
            "citation": "T.C. Memo 2020-100",
            "year": 2020,
            "summary": "Horse breeding activity held to be hobby rather than business",
            "key_facts": ["Continuous losses", "No business plan", "Personal pleasure element"],
            "outcome": "irs_win",
            "holdings": ["Nine-factor hobby loss test applied", "Losses disallowed under IRC 183"],
            "irc_sections": ["183", "162"],
            "tags": ["hobby loss", "horse breeding", "business vs hobby"],
        },
        {
            "id": "tc_home_office_1",
            "type": "tax_court",
            "title": "Hamacher v. Commissioner",
            "citation": "T.C. Memo 2014-235",
            "year": 2014,
            "summary": "Home office deduction allowed for employee with no other fixed location",
            "key_facts": ["No employer-provided office", "Regular and exclusive use", "Administrative tasks"],
            "outcome": "taxpayer_win",
            "holdings": ["Home office can qualify even if other work locations exist"],
            "irc_sections": ["280A"],
            "tags": ["home office", "employee", "exclusive use"],
        },
    ]

    SAMPLE_STRATEGIES = [
        {
            "id": "strat_1",
            "title": "S Corporation Election for Self-Employment Tax Savings",
            "description": "Converting from sole proprietor to S-Corp to reduce self-employment taxes",
            "applicable_situations": ["High self-employment income", "Stable business", "Can pay reasonable salary"],
            "success_rate": 0.85,
            "typical_savings": "$5,000 - $20,000 annually",
            "requirements": ["Reasonable salary", "Proper payroll", "Corporate formalities"],
            "risks": ["IRS reasonable compensation audits", "Compliance costs"],
            "source_cases": ["Watson v. Commissioner", "Various TAM rulings"],
        },
        {
            "id": "strat_2",
            "title": "Home Office Deduction - Regular and Exclusive Use",
            "description": "Claiming home office deduction for dedicated business space",
            "applicable_situations": ["Self-employed", "Dedicated home space", "Regular business use"],
            "success_rate": 0.75,
            "typical_savings": "$1,500 - $5,000 annually",
            "requirements": ["Exclusive use", "Regular use", "Principal place of business"],
            "risks": ["Audit risk", "Documentation requirements"],
            "source_cases": ["Hamacher v. Commissioner", "Popov v. Commissioner"],
        },
        {
            "id": "strat_3",
            "title": "Section 199A QBI Deduction Optimization",
            "description": "Maximizing the 20% qualified business income deduction",
            "applicable_situations": ["Pass-through income", "Below income thresholds", "Service business considerations"],
            "success_rate": 0.90,
            "typical_savings": "Up to 20% of QBI",
            "requirements": ["Qualified business income", "Not specified service business above threshold"],
            "risks": ["Aggregation rules complexity", "W-2 wage limitations"],
            "source_cases": ["Multiple IRS regulations"],
        },
    ]

    def __init__(self, ai_service=None):
        """
        Initialize case matcher.

        Args:
            ai_service: UnifiedAIService instance (lazy-loaded if not provided)
        """
        self._ai_service = ai_service
        self._embedding_cache: Dict[str, List[float]] = {}

    @property
    def ai_service(self):
        """Lazy-load AI service."""
        if self._ai_service is None:
            from services.ai.unified_ai_service import get_ai_service
            self._ai_service = get_ai_service()
        return self._ai_service

    async def find_similar_situations(
        self,
        situation: str,
        top_k: int = 5,
    ) -> SituationAnalysis:
        """
        Find similar tax situations and recommend strategies.

        Args:
            situation: Description of the tax situation
            top_k: Number of matches to return

        Returns:
            SituationAnalysis with matched cases and strategies
        """
        # Get embedding for the situation
        situation_embedding = await self._get_embedding(situation)

        # Find similar cases
        similar_cases = await self._match_cases(situation_embedding, top_k)

        # Find applicable strategies
        strategies = await self._match_strategies(situation_embedding, top_k)

        # Generate analysis
        analysis = await self._generate_situation_analysis(
            situation, similar_cases, strategies
        )

        return analysis

    async def find_relevant_cases(
        self,
        query: str,
        case_type: Optional[CaseType] = None,
        top_k: int = 5,
    ) -> List[CaseMatch]:
        """
        Find relevant tax court cases for a query.

        Args:
            query: Search query
            case_type: Optional filter by case type
            top_k: Number of results

        Returns:
            List of matched cases
        """
        query_embedding = await self._get_embedding(query)

        # Match against case database
        cases = await self._match_cases(query_embedding, top_k, case_type)

        return cases

    async def find_applicable_strategies(
        self,
        situation: str,
        top_k: int = 3,
    ) -> List[StrategyMatch]:
        """
        Find applicable tax strategies for a situation.

        Args:
            situation: Description of the situation
            top_k: Number of strategies to return

        Returns:
            List of matched strategies
        """
        situation_embedding = await self._get_embedding(situation)
        strategies = await self._match_strategies(situation_embedding, top_k)

        return strategies

    async def analyze_case_applicability(
        self,
        case: CaseMatch,
        situation: str,
    ) -> Dict[str, Any]:
        """
        Analyze how applicable a specific case is to a situation.

        Args:
            case: The case to analyze
            situation: The client situation

        Returns:
            Analysis of applicability
        """
        prompt = f"""Analyze how applicable this tax case is to the client's situation:

CASE:
Title: {case.title}
Citation: {case.citation}
Summary: {case.summary}
Key Facts: {json.dumps(case.key_facts)}
Holdings: {json.dumps(case.key_holdings)}
Outcome: {case.outcome.value}

CLIENT SITUATION:
{situation}

Analyze:
1. Factual similarities
2. Factual differences
3. Whether the case supports the taxpayer's position
4. How the case might be distinguished
5. Overall applicability

Return as JSON:
{{
    "factual_similarities": ["similarities"],
    "factual_differences": ["differences"],
    "supports_taxpayer": true/false,
    "distinguishing_factors": ["how case might be distinguished"],
    "applicability_score": 0.0-1.0,
    "recommendation": "how to use or address this case"
}}"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except Exception as e:
            logger.error(f"Failed to analyze case applicability: {e}")
            return {"error": str(e)}

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text, with caching."""
        cache_key = hashlib.md5(text.encode()).hexdigest()

        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        try:
            from config.ai_providers import AIProvider
            # Use OpenAI embeddings
            response = await self.ai_service.get_embedding(
                text=text,
                provider=AIProvider.OPENAI,
            )

            embedding = response.embedding
            self._embedding_cache[cache_key] = embedding

            return embedding

        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            # Return a simple hash-based pseudo-embedding as fallback
            return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> List[float]:
        """Generate a simple fallback embedding when API fails."""
        # This is a very basic fallback - not semantically meaningful
        # but allows the system to function
        import hashlib
        hash_bytes = hashlib.sha256(text.lower().encode()).digest()
        # Convert to 256-dimensional float vector
        return [float(b) / 255.0 for b in hash_bytes[:256]]

    async def _match_cases(
        self,
        query_embedding: List[float],
        top_k: int,
        case_type: Optional[CaseType] = None,
    ) -> List[CaseMatch]:
        """Match cases using embedding similarity."""
        matches = []

        for case_data in self.SAMPLE_CASES:
            # Filter by type if specified
            if case_type and case_data["type"] != case_type.value:
                continue

            # Get case embedding
            case_text = f"{case_data['title']} {case_data['summary']} {' '.join(case_data['tags'])}"
            case_embedding = await self._get_embedding(case_text)

            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, case_embedding)

            matches.append(CaseMatch(
                case_id=case_data["id"],
                case_type=CaseType(case_data["type"]),
                title=case_data["title"],
                citation=case_data.get("citation"),
                year=case_data.get("year"),
                summary=case_data["summary"],
                key_facts=case_data["key_facts"],
                outcome=CaseOutcome(case_data["outcome"]),
                relevance_score=similarity,
                similarity_score=similarity,
                key_holdings=case_data.get("holdings", []),
                applicable_irc_sections=case_data.get("irc_sections", []),
                tags=case_data.get("tags", []),
            ))

        # Sort by similarity and return top_k
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches[:top_k]

    async def _match_strategies(
        self,
        query_embedding: List[float],
        top_k: int,
    ) -> List[StrategyMatch]:
        """Match strategies using embedding similarity."""
        matches = []

        for strategy_data in self.SAMPLE_STRATEGIES:
            # Get strategy embedding
            strategy_text = f"{strategy_data['title']} {strategy_data['description']} {' '.join(strategy_data['applicable_situations'])}"
            strategy_embedding = await self._get_embedding(strategy_text)

            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, strategy_embedding)

            matches.append(StrategyMatch(
                strategy_id=strategy_data["id"],
                title=strategy_data["title"],
                description=strategy_data["description"],
                applicable_situations=strategy_data["applicable_situations"],
                success_rate=strategy_data["success_rate"],
                typical_savings=strategy_data.get("typical_savings"),
                requirements=strategy_data["requirements"],
                risks=strategy_data["risks"],
                similarity_score=similarity,
                source_cases=strategy_data.get("source_cases", []),
            ))

        # Sort by similarity and return top_k
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        return matches[:top_k]

    async def _generate_situation_analysis(
        self,
        situation: str,
        cases: List[CaseMatch],
        strategies: List[StrategyMatch],
    ) -> SituationAnalysis:
        """Generate comprehensive analysis using AI."""
        prompt = f"""Analyze this tax situation based on similar cases and strategies:

SITUATION:
{situation}

SIMILAR CASES:
{json.dumps([c.to_dict() for c in cases[:3]], indent=2)}

APPLICABLE STRATEGIES:
{json.dumps([s.to_dict() for s in strategies[:3]], indent=2)}

Provide analysis as JSON:
{{
    "risk_factors": ["potential risks in this situation"],
    "key_considerations": ["important factors to consider"],
    "suggested_research": ["additional research needed"],
    "confidence": 0.0-1.0
}}"""

        try:
            from config.ai_providers import AIProvider
            response = await self.ai_service.complete(
                prompt=prompt,
                provider=AIProvider.OPENAI,
            )

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return SituationAnalysis(
                situation=situation,
                similar_cases=cases,
                recommended_strategies=strategies,
                risk_factors=data.get("risk_factors", []),
                key_considerations=data.get("key_considerations", []),
                suggested_research=data.get("suggested_research", []),
                confidence=data.get("confidence", 0.7),
            )

        except Exception as e:
            logger.error(f"Failed to generate situation analysis: {e}")
            return SituationAnalysis(
                situation=situation,
                similar_cases=cases,
                recommended_strategies=strategies,
                risk_factors=["Analysis incomplete - consult tax professional"],
                key_considerations=[],
                suggested_research=["Comprehensive tax research recommended"],
                confidence=0.3,
            )

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            # Pad shorter vector
            min_len = min(len(a), len(b))
            a = a[:min_len]
            b = b[:min_len]

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_case_matcher: Optional[OpenAICaseMatcher] = None


def get_case_matcher() -> OpenAICaseMatcher:
    """Get the singleton case matcher instance."""
    global _case_matcher
    if _case_matcher is None:
        _case_matcher = OpenAICaseMatcher()
    return _case_matcher


__all__ = [
    "OpenAICaseMatcher",
    "CaseMatch",
    "StrategyMatch",
    "SituationAnalysis",
    "CaseType",
    "CaseOutcome",
    "get_case_matcher",
]
