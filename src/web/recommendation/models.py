"""
Recommendation Models - Data Classes

SPEC-006: Core data models for tax recommendations.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class RecommendationCategory(str, Enum):
    """Categories for tax recommendations."""
    CREDITS = "credits"
    DEDUCTIONS = "deductions"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    FILING_STATUS = "filing_status"
    TIMING = "timing"
    CHARITABLE = "charitable"
    AMT = "amt"
    PENALTY = "penalty"
    WITHHOLDING = "withholding"
    BUSINESS = "business"
    REAL_ESTATE = "real_estate"
    EDUCATION = "education"
    COMPLIANCE = "compliance"
    PLANNING = "planning"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationComplexity(str, Enum):
    """Complexity levels for implementation."""
    SIMPLE = "simple"      # Can do yourself
    MODERATE = "moderate"  # May need software
    COMPLEX = "complex"    # Needs professional help


@dataclass
class UnifiedRecommendation:
    """
    Unified recommendation data structure.

    Used across all recommendation generators for consistent output.
    """
    title: str
    description: str
    potential_savings: float
    priority: str = "medium"  # critical, high, medium, low
    category: str = "general"
    confidence: float = 0.8
    complexity: str = "moderate"  # simple, moderate, complex
    action_items: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source: str = "unified_advisor"
    tax_year: int = 2025
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "potential_savings": round(self.potential_savings, 2),
            "priority": self.priority,
            "category": self.category,
            "confidence": self.confidence,
            "complexity": self.complexity,
            "action_items": self.action_items,
            "requirements": self.requirements,
            "warnings": self.warnings,
            "source": self.source,
            "tax_year": self.tax_year,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedRecommendation":
        """Create from dictionary."""
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            potential_savings=data.get("potential_savings", 0),
            priority=data.get("priority", "medium"),
            category=data.get("category", "general"),
            confidence=data.get("confidence", 0.8),
            complexity=data.get("complexity", "moderate"),
            action_items=data.get("action_items", []),
            requirements=data.get("requirements", []),
            warnings=data.get("warnings", []),
            source=data.get("source", "unified_advisor"),
            tax_year=data.get("tax_year", 2025),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RecommendationResult:
    """
    Result container for recommendation generation.

    Contains recommendations plus metadata about the analysis.
    """
    recommendations: List[UnifiedRecommendation] = field(default_factory=list)
    profile_summary: Dict[str, Any] = field(default_factory=dict)
    lead_score: int = 0
    urgency_level: str = "normal"
    deadline_info: Optional[str] = None
    total_potential_savings: float = 0.0
    processing_time_ms: float = 0.0
    sources_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "profile_summary": self.profile_summary,
            "lead_score": self.lead_score,
            "urgency_level": self.urgency_level,
            "deadline_info": self.deadline_info,
            "total_potential_savings": round(self.total_potential_savings, 2),
            "count": len(self.recommendations),
            "processing_time_ms": self.processing_time_ms,
            "sources_used": self.sources_used,
            "errors": self.errors,
        }

    def add_recommendation(self, rec: UnifiedRecommendation) -> None:
        """Add a recommendation and update totals."""
        self.recommendations.append(rec)
        self.total_potential_savings += rec.potential_savings

    def sort_by_savings(self) -> None:
        """Sort recommendations by potential savings (highest first)."""
        self.recommendations.sort(key=lambda r: r.potential_savings, reverse=True)

    def sort_by_priority(self) -> None:
        """Sort recommendations by priority."""
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        self.recommendations.sort(key=lambda r: priority_order.get(r.priority, 2))

    def filter_by_category(self, category: str) -> List[UnifiedRecommendation]:
        """Get recommendations for a specific category."""
        return [r for r in self.recommendations if r.category == category]

    def get_top_n(self, n: int = 5) -> List[UnifiedRecommendation]:
        """Get top N recommendations by savings."""
        sorted_recs = sorted(self.recommendations, key=lambda r: r.potential_savings, reverse=True)
        return sorted_recs[:n]
