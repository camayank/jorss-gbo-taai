"""
Data Collector - Normalize data from all sources for report generation.

This module collects and normalizes tax data from various sources:
- Chatbot sessions (intelligent advisor)
- Lead magnet sessions
- Advisory analysis results
- Manual entry forms
- OCR document extraction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Types of data sources for report generation."""
    CHATBOT = "chatbot"
    ADVISORY = "advisory"
    LEAD_MAGNET = "lead_magnet"
    MANUAL = "manual"
    OCR = "ocr"


class PriorityLevel(str, Enum):
    """Priority levels for recommendations and actions."""
    IMMEDIATE = "immediate"
    CURRENT_YEAR = "current_year"
    NEXT_YEAR = "next_year"
    LONG_TERM = "long_term"


class RiskLevel(str, Enum):
    """Risk levels for identified factors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IncomeItem:
    """Individual income item for breakdown."""
    category: str  # e.g., "W-2 Wages", "Self-Employment", "Investments"
    description: str
    amount: Decimal
    is_taxable: bool = True
    tax_rate: Optional[float] = None  # For special treatment items
    source_document: Optional[str] = None  # e.g., "W-2", "1099-NEC"


@dataclass
class DeductionItem:
    """Individual deduction item for breakdown."""
    category: str  # e.g., "Above-the-line", "Itemized", "Business"
    description: str
    amount: Decimal
    is_above_line: bool = False
    irs_limit: Optional[Decimal] = None  # If there's a cap
    irs_reference: Optional[str] = None


@dataclass
class CreditItem:
    """Individual tax credit item."""
    name: str
    amount: Decimal
    is_refundable: bool = False
    phase_out_start: Optional[Decimal] = None
    phase_out_end: Optional[Decimal] = None
    irs_reference: Optional[str] = None


@dataclass
class Recommendation:
    """Tax optimization recommendation."""
    id: str
    category: str
    title: str
    description: str
    estimated_savings: Decimal
    confidence: float  # 0-1
    priority: PriorityLevel
    action_required: str
    deadline: Optional[str] = None
    irs_reference: Optional[str] = None
    requirements: List[str] = field(default_factory=list)


@dataclass
class RiskFactor:
    """Identified tax risk factor."""
    id: str
    category: str
    title: str
    description: str
    risk_level: RiskLevel
    potential_impact: Decimal
    mitigation: str
    deadline: Optional[str] = None


@dataclass
class Opportunity:
    """Tax optimization opportunity."""
    id: str
    category: str
    title: str
    description: str
    potential_savings_low: Decimal
    potential_savings_high: Decimal
    effort_level: str  # "easy", "moderate", "complex"
    time_sensitive: bool = False
    requirements: List[str] = field(default_factory=list)


@dataclass
class Scenario:
    """What-if tax scenario for comparison."""
    id: str
    name: str
    description: str
    changes: Dict[str, Any]  # What's different from baseline
    tax_liability: Decimal
    savings_vs_baseline: Decimal
    effective_rate: float
    is_recommended: bool = False


@dataclass
class TaxBracketInfo:
    """Tax bracket visualization data."""
    bracket_start: Decimal
    bracket_end: Decimal
    rate: float
    amount_in_bracket: Decimal
    tax_from_bracket: Decimal


@dataclass
class NormalizedReportData:
    """
    Universal data structure for report generation.

    This is the normalized format that all sources convert to.
    Report sections render conditionally based on what data is present.
    """
    # Source identification
    source_type: SourceType
    session_id: Optional[str] = None
    report_id: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.now)

    # Taxpayer info
    taxpayer_name: str = "Tax Client"
    filing_status: str = "single"
    tax_year: int = 2025
    state: Optional[str] = None

    # Financial summary (all optional - render if present)
    gross_income: Optional[Decimal] = None
    adjusted_gross_income: Optional[Decimal] = None
    taxable_income: Optional[Decimal] = None
    total_deductions: Optional[Decimal] = None
    total_credits: Optional[Decimal] = None
    tax_liability: Optional[Decimal] = None
    state_tax_liability: Optional[Decimal] = None
    self_employment_tax: Optional[Decimal] = None
    estimated_refund: Optional[Decimal] = None
    amount_owed: Optional[Decimal] = None

    # Tax rates
    effective_rate: Optional[float] = None
    marginal_rate: Optional[float] = None

    # Income breakdown (render if items present)
    income_items: List[IncomeItem] = field(default_factory=list)

    # Deduction breakdown
    deduction_items: List[DeductionItem] = field(default_factory=list)
    deduction_type: str = "standard"  # "standard" or "itemized"
    standard_deduction_amount: Optional[Decimal] = None
    itemized_deduction_amount: Optional[Decimal] = None

    # Credits
    credit_items: List[CreditItem] = field(default_factory=list)

    # AI Analysis (render if present)
    recommendations: List[Recommendation] = field(default_factory=list)
    risk_factors: List[RiskFactor] = field(default_factory=list)
    opportunities: List[Opportunity] = field(default_factory=list)

    # Scenarios (render if present)
    scenarios: List[Scenario] = field(default_factory=list)

    # Potential savings
    potential_savings_low: Optional[Decimal] = None
    potential_savings_high: Optional[Decimal] = None
    savings_confidence: Optional[float] = None  # 0-1 for gauge

    # Tax bracket breakdown
    tax_brackets: List[TaxBracketInfo] = field(default_factory=list)

    # Additional metadata
    key_insights: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)

    # Entity comparison (for business owners)
    entity_comparison: Optional[Dict[str, Any]] = None

    # Multi-year projection
    multi_year_projection: Optional[Dict[str, Any]] = None

    # Profile completeness for progress indicators
    profile_completeness: float = 0.0
    lead_score: int = 0
    complexity: str = "simple"  # "simple", "moderate", "complex", "professional"

    def has_income_breakdown(self) -> bool:
        """Check if income breakdown data is available."""
        return bool(self.income_items)

    def has_deduction_breakdown(self) -> bool:
        """Check if deduction breakdown data is available."""
        return bool(self.deduction_items)

    def has_credits(self) -> bool:
        """Check if credit data is available."""
        return bool(self.credit_items)

    def has_recommendations(self) -> bool:
        """Check if recommendations are available."""
        return bool(self.recommendations)

    def has_scenarios(self) -> bool:
        """Check if scenario comparisons are available."""
        return bool(self.scenarios)

    def has_savings_data(self) -> bool:
        """Check if savings data is available for gauge."""
        return self.potential_savings_high is not None

    def has_entity_comparison(self) -> bool:
        """Check if entity comparison data is available."""
        return self.entity_comparison is not None

    def has_projection(self) -> bool:
        """Check if multi-year projection is available."""
        return self.multi_year_projection is not None

    def get_total_potential_savings(self) -> Decimal:
        """Get total potential savings from all recommendations."""
        return sum(
            (r.estimated_savings for r in self.recommendations),
            Decimal("0")
        )

    def get_top_recommendations(self, limit: int = 5) -> List[Recommendation]:
        """Get top recommendations sorted by savings potential."""
        return sorted(
            self.recommendations,
            key=lambda r: r.estimated_savings,
            reverse=True
        )[:limit]

    def get_immediate_actions(self) -> List[Recommendation]:
        """Get recommendations with immediate priority."""
        return [
            r for r in self.recommendations
            if r.priority == PriorityLevel.IMMEDIATE
        ]


class ReportDataCollector:
    """
    Collect and normalize data from any source.

    This class handles the conversion from various data formats
    to the unified NormalizedReportData structure.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def from_chatbot_session(
        self,
        session_id: str,
        session_data: Dict[str, Any]
    ) -> NormalizedReportData:
        """
        Convert chatbot session data to normalized format.

        Args:
            session_id: Unique session identifier
            session_data: Session data from IntelligentChatEngine

        Returns:
            NormalizedReportData ready for report generation
        """
        profile = session_data.get("profile", {})
        calculations = session_data.get("calculations", {})
        strategies = session_data.get("strategies", [])

        # Handle calculations that might be a Pydantic model
        if hasattr(calculations, 'dict'):
            calculations = calculations.dict()
        elif calculations is None:
            calculations = {}

        # Build income items from profile
        income_items = self._build_income_items_from_profile(profile)

        # Build deduction items
        deduction_items = self._build_deduction_items_from_profile(profile, calculations)

        # Convert strategies to recommendations
        recommendations = self._convert_strategies_to_recommendations(strategies)

        # Calculate savings
        total_savings = sum(r.estimated_savings for r in recommendations)

        # Determine taxpayer name
        first_name = profile.get("first_name", "Tax")
        last_name = profile.get("last_name", "Client")
        taxpayer_name = f"{first_name} {last_name}".strip() or "Tax Client"

        return NormalizedReportData(
            source_type=SourceType.CHATBOT,
            session_id=session_id,
            taxpayer_name=taxpayer_name,
            filing_status=profile.get("filing_status", "single"),
            tax_year=2025,
            state=profile.get("state"),

            # Financial data
            gross_income=self._to_decimal(
                profile.get("total_income") or
                calculations.get("gross_income", 0)
            ),
            adjusted_gross_income=self._to_decimal(calculations.get("agi", 0)),
            taxable_income=self._to_decimal(calculations.get("taxable_income", 0)),
            total_deductions=self._to_decimal(calculations.get("deductions", 0)),
            total_credits=self._to_decimal(calculations.get("child_tax_credit", 0)),
            tax_liability=self._to_decimal(calculations.get("federal_tax", 0)),
            state_tax_liability=self._to_decimal(calculations.get("state_tax", 0)),
            self_employment_tax=self._to_decimal(calculations.get("self_employment_tax", 0)),

            # Rates
            effective_rate=calculations.get("effective_rate", 0),
            marginal_rate=calculations.get("marginal_rate", 22),

            # Refund/owed
            estimated_refund=self._to_decimal(
                calculations.get("refund_or_owed", 0)
            ) if calculations.get("is_refund", False) else None,
            amount_owed=self._to_decimal(
                abs(calculations.get("refund_or_owed", 0))
            ) if not calculations.get("is_refund", True) and calculations.get("refund_or_owed", 0) else None,

            # Breakdowns
            income_items=income_items,
            deduction_items=deduction_items,
            deduction_type=calculations.get("deduction_type", "standard"),

            # Recommendations
            recommendations=recommendations,

            # Savings
            potential_savings_low=self._to_decimal(total_savings * Decimal("0.7")),
            potential_savings_high=self._to_decimal(total_savings),
            savings_confidence=0.85 if recommendations else None,

            # Metadata
            profile_completeness=session_data.get("profile_completeness", 0.0),
            lead_score=session_data.get("lead_score", 0),
            complexity=session_data.get("complexity", "simple"),
            key_insights=session_data.get("key_insights", []),
            warnings=session_data.get("warnings", []),
        )

    def from_advisory_analysis(
        self,
        analysis_result: Dict[str, Any]
    ) -> NormalizedReportData:
        """
        Convert advisory analysis result to normalized format.

        Args:
            analysis_result: Result from AdvisoryReportGenerator

        Returns:
            NormalizedReportData ready for report generation
        """
        sections = analysis_result.get("sections", [])

        # Extract data from sections
        exec_summary = self._find_section(sections, "executive_summary")
        current_pos = self._find_section(sections, "current_position")
        recs_section = self._find_section(sections, "recommendations")
        action_plan = self._find_section(sections, "action_plan")
        entity_section = self._find_section(sections, "entity_comparison")
        projection_section = self._find_section(sections, "multi_year_projection")

        # Build recommendations from recommendations section
        recommendations = []
        if recs_section and "top_recommendations" in recs_section.get("content", {}):
            for i, rec in enumerate(recs_section["content"]["top_recommendations"]):
                recommendations.append(Recommendation(
                    id=f"rec_{i}",
                    category=rec.get("category", "general"),
                    title=rec.get("title", ""),
                    description=rec.get("description", ""),
                    estimated_savings=self._to_decimal(rec.get("savings", 0)),
                    confidence=rec.get("confidence", 0.8),
                    priority=PriorityLevel(rec.get("priority", "current_year")),
                    action_required=rec.get("action_required", ""),
                    irs_reference=rec.get("irs_reference"),
                ))

        # Get current liability info
        current_liability = {}
        if exec_summary:
            current_liability = exec_summary.get("content", {}).get("current_liability", {})

        return NormalizedReportData(
            source_type=SourceType.ADVISORY,
            report_id=analysis_result.get("report_id"),
            taxpayer_name=analysis_result.get("taxpayer_name", "Tax Client"),
            filing_status=analysis_result.get("filing_status", "single"),
            tax_year=analysis_result.get("tax_year", 2025),

            # Financial data from metrics
            tax_liability=self._to_decimal(
                analysis_result.get("metrics", {}).get("current_tax_liability", 0)
            ),
            state_tax_liability=self._to_decimal(current_liability.get("state", 0)),

            # From current position section
            gross_income=self._to_decimal(
                current_pos.get("content", {}).get("income_summary", {}).get("total_income", 0)
            ) if current_pos else None,
            adjusted_gross_income=self._to_decimal(
                current_pos.get("content", {}).get("income_summary", {}).get("agi", 0)
            ) if current_pos else None,
            taxable_income=self._to_decimal(
                current_pos.get("content", {}).get("income_summary", {}).get("taxable_income", 0)
            ) if current_pos else None,
            effective_rate=current_pos.get("content", {}).get("effective_rate", 0) if current_pos else None,

            # Recommendations
            recommendations=recommendations,

            # Savings
            potential_savings_low=self._to_decimal(
                analysis_result.get("metrics", {}).get("potential_savings", 0) * 0.7
            ),
            potential_savings_high=self._to_decimal(
                analysis_result.get("metrics", {}).get("potential_savings", 0)
            ),
            savings_confidence=analysis_result.get("metrics", {}).get("confidence_score", 0) / 100,

            # Entity comparison
            entity_comparison=entity_section.get("content") if entity_section else None,

            # Multi-year projection
            multi_year_projection=projection_section.get("content") if projection_section else None,

            # Action items
            action_items=analysis_result.get("recommendations", {}).get("immediate_actions", []),
        )

    def from_lead_magnet_session(
        self,
        session_id: str,
        session_data: Dict[str, Any]
    ) -> NormalizedReportData:
        """
        Convert lead magnet session to normalized format.

        Lead magnet sessions typically have limited data (teaser mode).

        Args:
            session_id: Session identifier
            session_data: Lead magnet session data

        Returns:
            NormalizedReportData for teaser report
        """
        profile = session_data.get("profile", {})

        # Lead magnet data is often more limited
        income = self._to_decimal(profile.get("total_income", 0))

        # Estimate potential savings (teaser)
        estimated_savings = income * Decimal("0.05")  # 5% estimated savings

        return NormalizedReportData(
            source_type=SourceType.LEAD_MAGNET,
            session_id=session_id,
            taxpayer_name=profile.get("name", "Tax Client"),
            filing_status=profile.get("filing_status", "single"),
            tax_year=2025,
            state=profile.get("state"),

            gross_income=income,

            # Teaser savings
            potential_savings_low=estimated_savings * Decimal("0.7"),
            potential_savings_high=estimated_savings,
            savings_confidence=0.6,  # Lower confidence for teaser

            profile_completeness=session_data.get("completeness", 0.3),
            lead_score=session_data.get("lead_score", 50),
            complexity="simple",
        )

    def from_manual_entry(
        self,
        form_data: Dict[str, Any]
    ) -> NormalizedReportData:
        """
        Convert manual form entry to normalized format.

        Args:
            form_data: Data from manual entry form

        Returns:
            NormalizedReportData from form data
        """
        # Build income items
        income_items = []
        if form_data.get("w2_wages"):
            income_items.append(IncomeItem(
                category="Employment",
                description="W-2 Wages",
                amount=self._to_decimal(form_data["w2_wages"]),
                source_document="W-2"
            ))
        if form_data.get("self_employment_income"):
            income_items.append(IncomeItem(
                category="Self-Employment",
                description="Business Income",
                amount=self._to_decimal(form_data["self_employment_income"]),
                source_document="1099-NEC"
            ))
        if form_data.get("investment_income"):
            income_items.append(IncomeItem(
                category="Investments",
                description="Investment Income",
                amount=self._to_decimal(form_data["investment_income"]),
                source_document="1099-DIV/1099-INT"
            ))

        # Calculate totals
        total_income = sum(item.amount for item in income_items)

        return NormalizedReportData(
            source_type=SourceType.MANUAL,
            taxpayer_name=form_data.get("taxpayer_name", "Tax Client"),
            filing_status=form_data.get("filing_status", "single"),
            tax_year=form_data.get("tax_year", 2025),
            state=form_data.get("state"),

            gross_income=total_income,
            income_items=income_items,

            profile_completeness=1.0,  # Manual entry is complete
        )

    def from_ocr_extraction(
        self,
        ocr_result: Dict[str, Any]
    ) -> NormalizedReportData:
        """
        Convert OCR extraction result to normalized format.

        Args:
            ocr_result: Result from document OCR extraction

        Returns:
            NormalizedReportData from OCR data
        """
        extracted_data = ocr_result.get("extracted_data", {})

        # Build income items from extracted documents
        income_items = []
        for doc in ocr_result.get("documents", []):
            doc_type = doc.get("type", "unknown")
            if doc_type == "W-2":
                income_items.append(IncomeItem(
                    category="Employment",
                    description=f"W-2 from {doc.get('employer', 'Employer')}",
                    amount=self._to_decimal(doc.get("wages", 0)),
                    source_document="W-2"
                ))
            elif doc_type == "1099-NEC":
                income_items.append(IncomeItem(
                    category="Self-Employment",
                    description=f"1099-NEC from {doc.get('payer', 'Payer')}",
                    amount=self._to_decimal(doc.get("amount", 0)),
                    source_document="1099-NEC"
                ))

        total_income = sum(item.amount for item in income_items)

        return NormalizedReportData(
            source_type=SourceType.OCR,
            taxpayer_name=extracted_data.get("taxpayer_name", "Tax Client"),
            filing_status=extracted_data.get("filing_status", "single"),
            tax_year=extracted_data.get("tax_year", 2025),

            gross_income=total_income,
            income_items=income_items,

            # OCR confidence
            profile_completeness=ocr_result.get("confidence", 0.8),
        )

    # Helper methods

    def _to_decimal(self, value: Any) -> Decimal:
        """Safely convert value to Decimal."""
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _build_income_items_from_profile(
        self,
        profile: Dict[str, Any]
    ) -> List[IncomeItem]:
        """Build income items from chatbot profile."""
        items = []

        if profile.get("w2_income"):
            items.append(IncomeItem(
                category="Employment",
                description="W-2 Wages",
                amount=self._to_decimal(profile["w2_income"]),
                source_document="W-2"
            ))

        if profile.get("business_income"):
            items.append(IncomeItem(
                category="Self-Employment",
                description="Business Income",
                amount=self._to_decimal(profile["business_income"]),
                source_document="Schedule C"
            ))

        if profile.get("investment_income"):
            items.append(IncomeItem(
                category="Investments",
                description="Investment Income",
                amount=self._to_decimal(profile["investment_income"]),
                source_document="1099-DIV/INT"
            ))

        if profile.get("rental_income"):
            items.append(IncomeItem(
                category="Rental",
                description="Rental Income",
                amount=self._to_decimal(profile["rental_income"]),
                source_document="Schedule E"
            ))

        if profile.get("capital_gains") or profile.get("capital_gains_long"):
            items.append(IncomeItem(
                category="Capital Gains",
                description="Long-term Capital Gains",
                amount=self._to_decimal(
                    profile.get("capital_gains_long") or profile.get("capital_gains", 0)
                ),
                tax_rate=0.15,  # Preferential rate
                source_document="Schedule D"
            ))

        if profile.get("dividend_income"):
            items.append(IncomeItem(
                category="Investments",
                description="Dividend Income",
                amount=self._to_decimal(profile["dividend_income"]),
                source_document="1099-DIV"
            ))

        return items

    def _build_deduction_items_from_profile(
        self,
        profile: Dict[str, Any],
        calculations: Dict[str, Any]
    ) -> List[DeductionItem]:
        """Build deduction items from profile and calculations."""
        items = []

        # Above-the-line deductions
        if profile.get("retirement_401k"):
            items.append(DeductionItem(
                category="Retirement",
                description="401(k) Contributions",
                amount=self._to_decimal(profile["retirement_401k"]),
                is_above_line=True,
                irs_limit=Decimal("23500"),
                irs_reference="IRC 402(g)"
            ))

        if profile.get("retirement_ira"):
            items.append(DeductionItem(
                category="Retirement",
                description="Traditional IRA Contributions",
                amount=self._to_decimal(profile["retirement_ira"]),
                is_above_line=True,
                irs_limit=Decimal("7000"),
                irs_reference="IRC 219"
            ))

        if profile.get("hsa_contributions"):
            items.append(DeductionItem(
                category="Health",
                description="HSA Contributions",
                amount=self._to_decimal(profile["hsa_contributions"]),
                is_above_line=True,
                irs_reference="IRC 223"
            ))

        if profile.get("student_loan_interest"):
            items.append(DeductionItem(
                category="Education",
                description="Student Loan Interest",
                amount=self._to_decimal(profile["student_loan_interest"]),
                is_above_line=True,
                irs_limit=Decimal("2500"),
                irs_reference="IRC 221"
            ))

        # Itemized deductions
        if calculations.get("deduction_type") == "itemized":
            if profile.get("mortgage_interest"):
                items.append(DeductionItem(
                    category="Itemized",
                    description="Mortgage Interest",
                    amount=self._to_decimal(profile["mortgage_interest"]),
                    irs_reference="IRC 163(h)"
                ))

            salt_amount = min(
                self._to_decimal(profile.get("property_taxes", 0)) +
                self._to_decimal(profile.get("state_income_tax", 0)),
                Decimal("10000")
            )
            if salt_amount > 0:
                items.append(DeductionItem(
                    category="Itemized",
                    description="State and Local Taxes (SALT)",
                    amount=salt_amount,
                    irs_limit=Decimal("10000"),
                    irs_reference="IRC 164"
                ))

            if profile.get("charitable_donations"):
                items.append(DeductionItem(
                    category="Itemized",
                    description="Charitable Contributions",
                    amount=self._to_decimal(profile["charitable_donations"]),
                    irs_reference="IRC 170"
                ))

        return items

    def _convert_strategies_to_recommendations(
        self,
        strategies: List[Any]
    ) -> List[Recommendation]:
        """Convert strategy objects to Recommendation dataclass."""
        recommendations = []

        for i, strategy in enumerate(strategies):
            # Handle both dict and object forms
            if hasattr(strategy, 'dict'):
                strategy = strategy.dict()
            elif not isinstance(strategy, dict):
                continue

            priority_str = strategy.get("priority", "current_year")
            try:
                priority = PriorityLevel(priority_str)
            except ValueError:
                priority = PriorityLevel.CURRENT_YEAR

            recommendations.append(Recommendation(
                id=strategy.get("id", f"strategy_{i}"),
                category=strategy.get("category", "general"),
                title=strategy.get("title", ""),
                description=strategy.get("detailed_explanation", strategy.get("summary", "")),
                estimated_savings=self._to_decimal(strategy.get("estimated_savings", 0)),
                confidence=self._parse_confidence(strategy.get("confidence", "medium")),
                priority=priority,
                action_required=strategy.get("action_steps", ["Review with CPA"])[0] if strategy.get("action_steps") else "Review with CPA",
                deadline=strategy.get("deadline"),
                irs_reference=strategy.get("irs_reference"),
            ))

        return recommendations

    def _parse_confidence(self, confidence: Any) -> float:
        """Parse confidence value to float 0-1."""
        if isinstance(confidence, (int, float)):
            return min(1.0, max(0.0, float(confidence)))
        if isinstance(confidence, str):
            mapping = {
                "high": 0.9,
                "medium": 0.7,
                "low": 0.5,
            }
            return mapping.get(confidence.lower(), 0.7)
        return 0.7

    def _find_section(
        self,
        sections: List[Dict],
        section_id: str
    ) -> Optional[Dict]:
        """Find a section by ID in sections list."""
        for section in sections:
            if section.get("section_id") == section_id:
                return section
        return None
