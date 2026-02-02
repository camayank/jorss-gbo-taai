"""
Intelligent Multi-Model Chat Router.

Routes tax queries to optimal AI models based on:
- Query complexity analysis
- Task type detection (research, reasoning, extraction, etc.)
- Cost optimization
- Conversation context

Routing Logic:
- Simple questions → GPT-4o-mini (fast, cheap)
- Extraction tasks → GPT-4o (structured output)
- Complex reasoning → Claude Opus (best reasoning)
- Research needs → Perplexity (real-time data)
- Standard chat → Claude Sonnet (balanced)

Usage:
    from services.ai.chat_router import get_chat_router

    router = get_chat_router()
    response = await router.route_query(
        "Should I convert my 401k to a Roth IRA?",
        context=conversation_history
    )
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from config.ai_providers import AIProvider, ModelCapability
from services.ai.unified_ai_service import (
    UnifiedAIService,
    AIMessage,
    AIResponse,
    get_ai_service,
)

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of tax queries for routing."""
    SIMPLE_QUESTION = "simple_question"      # "What is the standard deduction?"
    COMPLEX_REASONING = "complex_reasoning"  # "Should I convert to Roth IRA?"
    RESEARCH = "research"                    # "What are 2025 401k limits?"
    EXTRACTION = "extraction"                # "Extract W-2 data from this text"
    CALCULATION = "calculation"              # "Calculate my tax liability"
    COMPARISON = "comparison"                # "Compare S-Corp vs LLC"
    GENERAL_CHAT = "general_chat"            # Conversational, follow-ups


@dataclass
class QueryAnalysis:
    """Analysis result for a query."""
    query_type: QueryType
    complexity_score: float  # 0-1 scale
    needs_realtime_data: bool
    requires_calculation: bool
    requires_extraction: bool
    detected_entities: List[str]  # Tax-specific entities mentioned
    recommended_capability: ModelCapability
    reasoning: str


@dataclass
class RoutingDecision:
    """Routing decision with explanation."""
    provider: AIProvider
    capability: ModelCapability
    model_hint: Optional[str]
    reasoning: str
    cost_tier: str  # "low", "medium", "high"


# =============================================================================
# QUERY COMPLEXITY PATTERNS
# =============================================================================

# Simple question patterns (low complexity)
SIMPLE_PATTERNS = [
    r"^what is (the |a )?",
    r"^when (is|does|do|should|can) ",
    r"^how much (is|are|does) ",
    r"^what (are|is) the (limit|deadline|rate|amount)",
    r"^can i (deduct|claim|file)",
    r"^(do|does) (my|i) (need|have|qualify)",
    r"^where (do|can|should) i",
]

# Complex reasoning patterns (high complexity)
COMPLEX_PATTERNS = [
    r"should i (convert|elect|choose|switch|contribute)",
    r"(compare|comparison|better|versus|vs\.?)",
    r"(strategy|strategies|optimize|optimization)",
    r"(multi-year|over time|long.?term)",
    r"(estate|trust|inheritance|succession)",
    r"(roth conversion|backdoor|mega backdoor)",
    r"(s.?corp|c.?corp|llc|partnership) (election|conversion)",
    r"(tax planning|tax strategy|minimize tax)",
    r"(capital gains|loss harvesting|wash sale)",
    r"(amt|alternative minimum tax)",
    r"(qsbs|qualified small business)",
    r"(carried interest|incentive compensation)",
]

# Research patterns (needs real-time data)
RESEARCH_PATTERNS = [
    r"(current|latest|new|recent|updated) (law|rule|regulation|limit)",
    r"(2025|2026|this year|next year) (limit|rule|change)",
    r"(irs|treasury|congress) (announce|release|update)",
    r"(court case|ruling|decision|precedent)",
    r"(state tax|state-specific|state law)",
    r"(form|schedule|publication) \d+",
    r"(inflation adjust|index|bracket)",
]

# Extraction patterns
EXTRACTION_PATTERNS = [
    r"extract (the |from |data )",
    r"parse (this|the) (document|text|form)",
    r"(fill|populate) (the |this )?(form|field)",
    r"(identify|find) (the |all )?(numbers|amounts|figures)",
    r"(w-?2|1099|k-?1) (data|information|values)",
]

# Calculation patterns
CALCULATION_PATTERNS = [
    r"calculate (my |the )?",
    r"(what|how much) (is|would be|will be) (my |the )?(tax|liability|refund)",
    r"(compute|determine|figure out)",
    r"(if i|assuming) .+ (what|how much)",
    r"(estimate|projection|forecast)",
]

# Tax-specific entities for context enrichment
TAX_ENTITIES = [
    "401k", "403b", "ira", "roth", "traditional ira", "sep ira", "simple ira",
    "hsa", "fsa", "dependent care", "medical expense",
    "w-2", "w2", "1099", "k-1", "schedule c", "schedule e", "schedule d",
    "standard deduction", "itemized deduction", "salt", "mortgage interest",
    "charitable", "donation", "qcd", "donor advised fund",
    "capital gain", "capital loss", "loss harvesting", "wash sale",
    "depreciation", "section 179", "bonus depreciation", "macrs",
    "s-corp", "c-corp", "llc", "partnership", "sole proprietor",
    "self-employment", "se tax", "quarterly payment", "estimated tax",
    "qbi", "qualified business income", "199a",
    "amt", "alternative minimum tax", "niit", "irmaa",
    "social security", "medicare", "rmd", "inherited ira",
    "filing status", "married filing", "head of household",
    "dependent", "child tax credit", "eitc", "earned income credit",
    "education credit", "american opportunity", "lifetime learning",
]


# =============================================================================
# QUERY ANALYZER
# =============================================================================

class QueryAnalyzer:
    """Analyzes tax queries to determine optimal routing."""

    def __init__(self):
        # Compile patterns for efficiency
        self.simple_patterns = [re.compile(p, re.IGNORECASE) for p in SIMPLE_PATTERNS]
        self.complex_patterns = [re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS]
        self.research_patterns = [re.compile(p, re.IGNORECASE) for p in RESEARCH_PATTERNS]
        self.extraction_patterns = [re.compile(p, re.IGNORECASE) for p in EXTRACTION_PATTERNS]
        self.calculation_patterns = [re.compile(p, re.IGNORECASE) for p in CALCULATION_PATTERNS]

    def analyze(
        self,
        query: str,
        conversation_history: Optional[List[AIMessage]] = None
    ) -> QueryAnalysis:
        """
        Analyze a query to determine its type and complexity.

        Args:
            query: The user's query
            conversation_history: Previous messages for context

        Returns:
            QueryAnalysis with routing recommendations
        """
        query_lower = query.lower()

        # Detect tax entities
        detected_entities = self._detect_entities(query_lower)

        # Check patterns
        is_simple = any(p.search(query_lower) for p in self.simple_patterns)
        is_complex = any(p.search(query_lower) for p in self.complex_patterns)
        is_research = any(p.search(query_lower) for p in self.research_patterns)
        is_extraction = any(p.search(query_lower) for p in self.extraction_patterns)
        is_calculation = any(p.search(query_lower) for p in self.calculation_patterns)

        # Calculate complexity score
        complexity_score = self._calculate_complexity(
            query,
            detected_entities,
            is_complex,
            is_simple,
            conversation_history
        )

        # Determine query type
        query_type = self._determine_type(
            is_simple, is_complex, is_research,
            is_extraction, is_calculation,
            complexity_score
        )

        # Determine recommended capability
        capability, reasoning = self._recommend_capability(
            query_type, complexity_score, is_research
        )

        return QueryAnalysis(
            query_type=query_type,
            complexity_score=complexity_score,
            needs_realtime_data=is_research,
            requires_calculation=is_calculation,
            requires_extraction=is_extraction,
            detected_entities=detected_entities,
            recommended_capability=capability,
            reasoning=reasoning
        )

    def _detect_entities(self, query_lower: str) -> List[str]:
        """Detect tax-specific entities in the query."""
        found = []
        for entity in TAX_ENTITIES:
            if entity in query_lower:
                found.append(entity)
        return found

    def _calculate_complexity(
        self,
        query: str,
        entities: List[str],
        is_complex: bool,
        is_simple: bool,
        history: Optional[List[AIMessage]]
    ) -> float:
        """Calculate complexity score (0-1)."""
        score = 0.5  # Base score

        # Length factor
        word_count = len(query.split())
        if word_count > 50:
            score += 0.2
        elif word_count > 25:
            score += 0.1
        elif word_count < 10:
            score -= 0.1

        # Entity factor
        if len(entities) > 3:
            score += 0.15
        elif len(entities) > 1:
            score += 0.05

        # Pattern factor
        if is_complex:
            score += 0.25
        if is_simple:
            score -= 0.2

        # Context factor (longer conversations = more complex)
        if history and len(history) > 6:
            score += 0.1

        # Clamp to 0-1
        return max(0.0, min(1.0, score))

    def _determine_type(
        self,
        is_simple: bool,
        is_complex: bool,
        is_research: bool,
        is_extraction: bool,
        is_calculation: bool,
        complexity: float
    ) -> QueryType:
        """Determine the primary query type."""
        # Priority order matters
        if is_extraction:
            return QueryType.EXTRACTION
        if is_research:
            return QueryType.RESEARCH
        if is_calculation:
            return QueryType.CALCULATION
        if is_complex or complexity > 0.7:
            return QueryType.COMPLEX_REASONING
        if is_simple or complexity < 0.3:
            return QueryType.SIMPLE_QUESTION
        return QueryType.GENERAL_CHAT

    def _recommend_capability(
        self,
        query_type: QueryType,
        complexity: float,
        needs_research: bool
    ) -> Tuple[ModelCapability, str]:
        """Recommend the best capability for this query."""

        if query_type == QueryType.RESEARCH or needs_research:
            return (
                ModelCapability.RESEARCH,
                "Query requires real-time data; routing to Perplexity"
            )

        if query_type == QueryType.EXTRACTION:
            return (
                ModelCapability.EXTRACTION,
                "Structured extraction task; routing to extraction model"
            )

        if query_type == QueryType.COMPLEX_REASONING:
            return (
                ModelCapability.COMPLEX,
                "Complex tax reasoning required; routing to Claude Opus"
            )

        if query_type == QueryType.SIMPLE_QUESTION:
            return (
                ModelCapability.FAST,
                "Simple factual question; routing to fast model"
            )

        if query_type == QueryType.CALCULATION:
            return (
                ModelCapability.STANDARD,
                "Calculation with explanation needed; routing to standard model"
            )

        # Default for general chat
        if complexity > 0.5:
            return (
                ModelCapability.STANDARD,
                "Moderate complexity; routing to balanced model"
            )

        return (
            ModelCapability.FAST,
            "Low complexity query; routing to fast model"
        )


# =============================================================================
# CHAT ROUTER
# =============================================================================

class IntelligentChatRouter:
    """
    Routes tax queries to optimal AI models.

    Key features:
    - Automatic complexity analysis
    - Multi-provider routing
    - Cost-optimized model selection
    - Conversation context awareness
    - Tax-domain specialization
    """

    def __init__(self, ai_service: Optional[UnifiedAIService] = None):
        self.ai_service = ai_service or get_ai_service()
        self.analyzer = QueryAnalyzer()
        self._conversation_contexts: Dict[str, List[AIMessage]] = {}

    def get_tax_system_prompt(self, query_type: QueryType) -> str:
        """Get specialized system prompt based on query type."""

        base_prompt = """You are an expert tax advisor with deep knowledge of US tax law,
IRS regulations, and practical tax planning strategies. You provide accurate,
actionable advice while noting when professional consultation is recommended."""

        type_specific = {
            QueryType.SIMPLE_QUESTION: """
Answer questions directly and concisely. Cite specific IRC sections or IRS
publications when relevant. If the answer depends on the taxpayer's specific
situation, briefly note the key factors.""",

            QueryType.COMPLEX_REASONING: """
Think step-by-step through complex tax scenarios. Consider:
1. All relevant tax implications (federal, state, FICA, NIIT, AMT)
2. Short-term vs long-term impacts
3. Risk factors and compliance considerations
4. Alternative strategies with pros/cons

Always cite specific tax code sections. Explain your reasoning in plain language.
Recommend professional guidance for situations with significant complexity or risk.""",

            QueryType.RESEARCH: """
Provide current, accurate information from authoritative sources.
- Cite specific IRS guidance, publications, and revenue procedures
- Note effective dates for rules and limits
- Distinguish between settled law and areas of uncertainty
- Identify recent changes or pending legislation if relevant""",

            QueryType.EXTRACTION: """
Extract data accurately and completely from the provided text.
Return structured data matching the requested schema.
Flag any ambiguous or unclear information for review.
Note confidence levels for extracted values.""",

            QueryType.CALCULATION: """
Perform accurate tax calculations with clear explanations.
Show your work step-by-step. Note all assumptions made.
Validate inputs are within reasonable ranges.
Flag any unusual results that warrant verification.""",

            QueryType.COMPARISON: """
Provide balanced, thorough comparisons.
Create clear side-by-side analysis of options.
Quantify differences where possible.
Highlight key decision factors for the taxpayer's situation.""",

            QueryType.GENERAL_CHAT: """
Engage helpfully in tax-related discussion.
Ask clarifying questions when needed.
Provide educational context to help the user understand.
Guide toward more specific questions when appropriate.""",
        }

        specific = type_specific.get(query_type, type_specific[QueryType.GENERAL_CHAT])
        return f"{base_prompt}\n\n{specific}"

    async def route_query(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        force_capability: Optional[ModelCapability] = None,
        additional_context: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """
        Route a query to the optimal AI model.

        Args:
            query: The user's tax question
            conversation_id: Optional ID to maintain context
            force_capability: Override automatic routing
            additional_context: Extra context (e.g., user's tax situation)
            **kwargs: Additional arguments for the AI service

        Returns:
            AIResponse from the selected model
        """
        # Get conversation history
        history = self._get_conversation_history(conversation_id)

        # Analyze query
        analysis = self.analyzer.analyze(query, history)
        logger.info(
            f"Query analysis: type={analysis.query_type.value}, "
            f"complexity={analysis.complexity_score:.2f}, "
            f"capability={analysis.recommended_capability.value}"
        )

        # Determine capability (allow override)
        capability = force_capability or analysis.recommended_capability

        # Build system prompt
        system_prompt = self.get_tax_system_prompt(analysis.query_type)
        if additional_context:
            system_prompt += f"\n\nUser context:\n{additional_context}"

        # Build prompt with entity enrichment
        enriched_prompt = self._enrich_prompt(query, analysis)

        # Route to appropriate method based on capability
        if capability == ModelCapability.RESEARCH:
            response = await self.ai_service.research(enriched_prompt, **kwargs)
        elif capability == ModelCapability.COMPLEX:
            response = await self.ai_service.reason(
                problem=query,
                context=additional_context or self._summarize_history(history),
                **kwargs
            )
        else:
            response = await self.ai_service.complete(
                prompt=enriched_prompt,
                system_prompt=system_prompt,
                capability=capability,
                **kwargs
            )

        # Update conversation history
        if conversation_id:
            self._update_conversation(conversation_id, query, response.content)

        # Add routing metadata
        response.metadata["routing"] = {
            "query_type": analysis.query_type.value,
            "complexity_score": analysis.complexity_score,
            "detected_entities": analysis.detected_entities,
            "routing_reasoning": analysis.reasoning,
        }

        return response

    async def extract_from_text(
        self,
        text: str,
        schema: Dict[str, Any],
        document_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract structured tax data from text.

        Args:
            text: Text to extract from
            schema: Expected data schema
            document_type: Optional hint (e.g., "W-2", "1099-INT")

        Returns:
            Extracted data as dict
        """
        # Add document type context to improve extraction
        if document_type:
            context = f"Document type: {document_type}\n\n"
            text = context + text

        return await self.ai_service.extract(text, schema, **kwargs)

    async def compare_scenarios(
        self,
        question: str,
        scenarios: List[Dict[str, Any]],
        **kwargs
    ) -> AIResponse:
        """
        Compare tax scenarios using complex reasoning.

        Args:
            question: The comparison question
            scenarios: List of scenarios to compare

        Returns:
            Detailed comparison analysis
        """
        # Format scenarios for comparison
        scenario_text = "\n".join([
            f"Scenario {i+1} ({s.get('name', f'Option {i+1}')}):\n{s.get('description', str(s))}"
            for i, s in enumerate(scenarios)
        ])

        prompt = f"""Compare the following tax scenarios:

{scenario_text}

Question: {question}

Provide a detailed comparison including:
1. Tax implications of each scenario
2. Key differences and trade-offs
3. Recommended option with reasoning
4. Important caveats or considerations"""

        return await self.ai_service.reason(
            problem=prompt,
            context="Multi-scenario tax comparison",
            **kwargs
        )

    def _get_conversation_history(
        self,
        conversation_id: Optional[str]
    ) -> List[AIMessage]:
        """Get conversation history for context."""
        if not conversation_id:
            return []
        return self._conversation_contexts.get(conversation_id, [])

    def _update_conversation(
        self,
        conversation_id: str,
        user_query: str,
        assistant_response: str
    ):
        """Update conversation history."""
        if conversation_id not in self._conversation_contexts:
            self._conversation_contexts[conversation_id] = []

        history = self._conversation_contexts[conversation_id]
        history.append(AIMessage(role="user", content=user_query))
        history.append(AIMessage(role="assistant", content=assistant_response))

        # Keep last 20 messages to manage context window
        if len(history) > 20:
            self._conversation_contexts[conversation_id] = history[-20:]

    def _summarize_history(self, history: List[AIMessage]) -> str:
        """Summarize conversation history for context."""
        if not history:
            return ""

        summary_parts = []
        for msg in history[-6:]:  # Last 3 exchanges
            role = "User" if msg.role == "user" else "Assistant"
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            summary_parts.append(f"{role}: {content}")

        return "Recent conversation:\n" + "\n".join(summary_parts)

    def _enrich_prompt(self, query: str, analysis: QueryAnalysis) -> str:
        """Enrich prompt with detected context."""
        if not analysis.detected_entities:
            return query

        # For complex queries, add entity clarification
        if analysis.complexity_score > 0.5 and len(analysis.detected_entities) > 1:
            entities_note = f"\n\n[Topics detected: {', '.join(analysis.detected_entities)}]"
            return query + entities_note

        return query

    def clear_conversation(self, conversation_id: str):
        """Clear conversation history."""
        if conversation_id in self._conversation_contexts:
            del self._conversation_contexts[conversation_id]

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get statistics about routing decisions."""
        return {
            "active_conversations": len(self._conversation_contexts),
            "ai_service_usage": self.ai_service.get_usage_summary(),
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_chat_router: Optional[IntelligentChatRouter] = None


def get_chat_router() -> IntelligentChatRouter:
    """Get the singleton chat router instance."""
    global _chat_router
    if _chat_router is None:
        _chat_router = IntelligentChatRouter()
    return _chat_router


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "IntelligentChatRouter",
    "QueryAnalyzer",
    "QueryType",
    "QueryAnalysis",
    "RoutingDecision",
    "get_chat_router",
]
