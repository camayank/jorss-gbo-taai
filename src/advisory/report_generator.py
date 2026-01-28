"""
Advisory Report Generator - Orchestrates all tax engines to produce comprehensive reports.

This module LEVERAGES existing engines (doesn't rebuild them):
- Tax calculation engine (existing)
- Recommendation engine (existing - 80+ tests passing)
- Entity optimizer (existing - 48 tests passing)
- Multi-year projector (existing)
- Scenario comparison (existing)

Purpose: Combine all existing engines into unified advisory reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
import logging

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

# Import existing engines
from calculator.tax_calculator import TaxCalculator
from recommendation.recommendation_engine import (
    TaxRecommendationEngine,
    ComprehensiveRecommendation,
)
from recommendation.entity_optimizer import EntityStructureOptimizer
from projection.multi_year_projections import (
    MultiYearProjectionEngine,
    MultiYearProjectionResult,
)

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of advisory reports available."""
    EXECUTIVE_SUMMARY = "executive_summary"  # 2-3 pages, highlights only
    STANDARD_REPORT = "standard_report"      # 14-21 pages, comprehensive
    ENTITY_COMPARISON = "entity_comparison"  # Business structure analysis
    MULTI_YEAR = "multi_year"                # 3-5 year projections
    FULL_ANALYSIS = "full_analysis"          # Everything included


@dataclass
class AdvisoryReportSection:
    """Individual section of an advisory report."""
    section_id: str
    title: str
    content: Dict[str, Any]
    page_number: Optional[int] = None
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AdvisoryReportResult:
    """
    Complete advisory report result.

    This is the main output of the Advisory Report Generator.
    Contains all data needed to generate PDFs, show previews, etc.
    """
    # Metadata
    report_id: str
    report_type: ReportType
    tax_year: int
    generated_at: str

    # Client information
    taxpayer_name: str
    filing_status: str

    # Report sections (ordered)
    sections: List[AdvisoryReportSection]

    # Quick metrics (for dashboards/previews)
    current_tax_liability: Decimal
    potential_savings: Decimal
    confidence_score: Decimal  # 0-100

    # Recommendations summary
    top_recommendations_count: int
    immediate_action_items: List[Dict[str, Any]]

    # Status
    status: str = "complete"  # "generating", "complete", "error"
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "tax_year": self.tax_year,
            "generated_at": self.generated_at,
            "taxpayer_name": self.taxpayer_name,
            "filing_status": self.filing_status,
            "sections": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "content": s.content,
                    "page_number": s.page_number,
                }
                for s in self.sections
            ],
            "metrics": {
                "current_tax_liability": float(self.current_tax_liability),
                "potential_savings": float(self.potential_savings),
                "confidence_score": float(self.confidence_score),
            },
            "recommendations": {
                "total_count": self.top_recommendations_count,
                "immediate_actions": self.immediate_action_items,
            },
            "status": self.status,
            "error_message": self.error_message,
        }


class AdvisoryReportGenerator:
    """
    Generates comprehensive tax advisory reports using existing engines.

    This class ORCHESTRATES existing functionality:
    - TaxCalculator (calculates current position)
    - TaxRecommendationEngine (generates recommendations)
    - EntityStructureOptimizer (compares business structures)
    - MultiYearProjectionEngine (projects future years)

    It does NOT reimplement any tax logic - it just combines results.
    """

    def __init__(
        self,
        tax_calculator: Optional[TaxCalculator] = None,
        recommendation_engine: Optional[TaxRecommendationEngine] = None,
        entity_optimizer: Optional[EntityStructureOptimizer] = None,
        projection_engine: Optional[MultiYearProjectionEngine] = None,
    ):
        """
        Initialize advisory report generator.

        All engines are optional - will create defaults if not provided.
        This allows for dependency injection and easier testing.
        """
        self.tax_calculator = tax_calculator or TaxCalculator()
        self.recommendation_engine = recommendation_engine or TaxRecommendationEngine(self.tax_calculator)
        self.entity_optimizer = entity_optimizer or EntityStructureOptimizer()
        self.projection_engine = projection_engine or MultiYearProjectionEngine()

        logger.info("Advisory Report Generator initialized")

    def generate_report(
        self,
        tax_return: "TaxReturn",
        report_type: ReportType = ReportType.STANDARD_REPORT,
        include_entity_comparison: bool = False,
        include_multi_year: bool = True,
        years_ahead: int = 3,
    ) -> AdvisoryReportResult:
        """
        Generate a comprehensive advisory report.

        Args:
            tax_return: The tax return to analyze (from existing models)
            report_type: Type of report to generate
            include_entity_comparison: Whether to include business entity analysis
            include_multi_year: Whether to include multi-year projections
            years_ahead: Number of years to project (default 3)

        Returns:
            AdvisoryReportResult with all sections and data
        """
        taxpayer_name = f"{tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}"
        logger.info(f"Generating {report_type.value} report for {taxpayer_name}")

        report_id = self._generate_report_id(tax_return)
        sections: List[AdvisoryReportSection] = []

        try:
            # Section 1: Executive Summary
            sections.append(self._generate_executive_summary(tax_return))

            # Section 2: Current Tax Position (uses existing calculator)
            sections.append(self._generate_current_position(tax_return))

            # Section 3: Recommendations (uses existing recommendation engine)
            recommendations_section, recommendation_data = self._generate_recommendations(tax_return)
            sections.append(recommendations_section)

            # Section 4: Entity Comparison (if business income exists)
            entity_section = None
            if include_entity_comparison and self._has_business_income(tax_return):
                entity_section = self._generate_entity_comparison(tax_return)
                if entity_section:
                    sections.append(entity_section)

            # Section 5: Multi-Year Projections (uses existing projector)
            projection_section = None
            if include_multi_year:
                projection_section = self._generate_multi_year_projection(tax_return, years_ahead)
                if projection_section:
                    sections.append(projection_section)

            # Section 6: Action Plan
            sections.append(self._generate_action_plan(tax_return, recommendation_data))

            # Section 7: Disclaimers & Methodology
            sections.append(self._generate_disclaimers())

            # Calculate summary metrics
            current_tax = Decimal(str(tax_return.tax_liability or 0))
            potential_savings = Decimal(str(recommendation_data.total_potential_savings))
            confidence = Decimal(str(recommendation_data.overall_confidence))

            # Extract immediate actions
            immediate_actions = [
                {
                    "title": opp.title,
                    "savings": float(opp.estimated_savings),
                    "action": opp.action_required,
                }
                for opp in recommendation_data.top_opportunities[:5]
                if opp.priority in ("immediate", "current_year")
            ]

            return AdvisoryReportResult(
                report_id=report_id,
                report_type=report_type,
                tax_year=tax_return.tax_year,
                generated_at=datetime.now().isoformat(),
                taxpayer_name=taxpayer_name,
                filing_status=tax_return.taxpayer.filing_status.value,
                sections=sections,
                current_tax_liability=current_tax,
                potential_savings=potential_savings,
                confidence_score=confidence,
                top_recommendations_count=len(recommendation_data.top_opportunities),
                immediate_action_items=immediate_actions,
                status="complete",
            )

        except Exception as e:
            logger.error(f"Error generating report: {str(e)}", exc_info=True)
            error_taxpayer_name = f"{tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}"
            return AdvisoryReportResult(
                report_id=report_id,
                report_type=report_type,
                tax_year=tax_return.tax_year,
                generated_at=datetime.now().isoformat(),
                taxpayer_name=error_taxpayer_name,
                filing_status=tax_return.taxpayer.filing_status.value,
                sections=[],
                current_tax_liability=Decimal("0"),
                potential_savings=Decimal("0"),
                confidence_score=Decimal("0"),
                top_recommendations_count=0,
                immediate_action_items=[],
                status="error",
                error_message=str(e),
            )

    def _generate_report_id(self, tax_return: "TaxReturn") -> str:
        """Generate unique report ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ADV_{tax_return.tax_year}_{timestamp}"

    def _generate_executive_summary(self, tax_return: "TaxReturn") -> AdvisoryReportSection:
        """Generate executive summary section."""
        logger.debug("Generating executive summary")

        # Calculate key metrics using existing calculator
        tax_result = self.tax_calculator.calculate_complete_return(tax_return)

        taxpayer_name = f"{tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}"
        content = {
            "overview": f"Tax advisory report for {taxpayer_name}",
            "tax_year": tax_return.tax_year,
            "filing_status": tax_return.taxpayer.filing_status.value,
            "current_liability": {
                "federal": float(tax_result.tax_liability or 0),
                "state": float(tax_result.state_tax_liability or 0),
                "total": float((tax_result.tax_liability or 0) + (tax_result.state_tax_liability or 0)),
            },
            "agi": float(tax_result.adjusted_gross_income or 0),
            "taxable_income": float(tax_result.taxable_income or 0),
        }

        return AdvisoryReportSection(
            section_id="executive_summary",
            title="Executive Summary",
            content=content,
            page_number=1,
        )

    def _generate_current_position(self, tax_return: "TaxReturn") -> AdvisoryReportSection:
        """Generate current tax position section using existing calculator."""
        logger.debug("Generating current tax position")

        # Use existing tax calculator (already tested with 40+ tests)
        tax_result = self.tax_calculator.calculate_complete_return(tax_return)

        # Calculate total income from income model
        total_income = tax_result.income.get_total_income()

        # Calculate deductions (AGI - taxable income)
        agi = float(tax_result.adjusted_gross_income or 0)
        taxable = float(tax_result.taxable_income or 0)
        total_deductions = agi - taxable

        content = {
            "income_summary": {
                "total_income": float(total_income),
                "agi": agi,
                "taxable_income": taxable,
            },
            "deductions": {
                "standard_or_itemized": "standard" if tax_result.deductions.use_standard_deduction else "itemized",
                "total_deductions": total_deductions,
            },
            "tax_liability": {
                "federal_tax": float(tax_result.tax_liability or 0),
                "state_tax": float(tax_result.state_tax_liability or 0),
                "total_tax": float((tax_result.tax_liability or 0) + (tax_result.state_tax_liability or 0)),
            },
            "effective_rate": self._calculate_effective_rate(tax_result),
        }

        return AdvisoryReportSection(
            section_id="current_position",
            title="Current Tax Position",
            content=content,
            page_number=2,
        )

    def _generate_recommendations(
        self, tax_return: "TaxReturn"
    ) -> tuple[AdvisoryReportSection, ComprehensiveRecommendation]:
        """Generate recommendations section using existing recommendation engine."""
        logger.debug("Generating recommendations")

        # Use existing recommendation engine (80+ tests passing!)
        recommendations = self.recommendation_engine.analyze(tax_return)

        content = {
            "total_opportunities": len(recommendations.all_opportunities),
            "total_potential_savings": float(recommendations.total_potential_savings),
            "confidence": float(recommendations.overall_confidence),
            "top_recommendations": [
                {
                    "category": opp.category,
                    "title": opp.title,
                    "savings": float(opp.estimated_savings),
                    "priority": opp.priority,
                    "description": opp.description,
                    "action_required": opp.action_required,
                    "confidence": float(opp.confidence),
                    "irs_reference": opp.irs_reference,
                }
                for opp in recommendations.top_opportunities
            ],
        }

        return (
            AdvisoryReportSection(
                section_id="recommendations",
                title="Tax Optimization Recommendations",
                content=content,
                page_number=3,
            ),
            recommendations,
        )

    def _generate_entity_comparison(self, tax_return: "TaxReturn") -> Optional[AdvisoryReportSection]:
        """Generate entity comparison section using existing entity optimizer."""
        logger.debug("Generating entity comparison")

        # Extract business income
        business_income = self._extract_business_income(tax_return)
        if not business_income:
            return None

        # Use existing entity optimizer with correct API
        try:
            # Create optimizer with filing status and state
            optimizer = EntityStructureOptimizer(
                filing_status=tax_return.taxpayer.filing_status.value,
                other_income=float(getattr(tax_return.income, 'w2_wages', 0) or 0),
                state=getattr(tax_return.taxpayer, "state", "CA"),
            )

            # Call compare_structures (correct method name)
            comparison_result = optimizer.compare_structures(
                gross_revenue=business_income["gross_income"],
                business_expenses=business_income["expenses"],
            )

            # Convert EntityComparisonResult to dict for content
            # Access analyses dict by entity type value
            sole_prop = comparison_result.analyses.get("sole_proprietorship")
            s_corp = comparison_result.analyses.get("s_corporation")

            content = {
                "business_income": business_income,
                "entity_comparison": {
                    "sole_proprietor": {
                        "total_tax": float(sole_prop.total_business_tax if sole_prop else 0),
                        "self_employment_tax": float(sole_prop.self_employment_tax if sole_prop else 0),
                        "net_benefit": 0.0,  # Baseline
                        "recommended": comparison_result.recommended_entity.value == "sole_proprietorship" if comparison_result.recommended_entity else False,
                    },
                    "s_corp": {
                        "total_tax": float(s_corp.total_business_tax if s_corp else 0),
                        "self_employment_tax": float(s_corp.self_employment_tax if s_corp else 0),
                        "net_benefit": float(comparison_result.max_annual_savings),
                        "recommended": comparison_result.recommended_entity.value == "s_corporation" if comparison_result.recommended_entity else False,
                    },
                },
            }

            return AdvisoryReportSection(
                section_id="entity_comparison",
                title="Business Entity Comparison",
                content=content,
                page_number=5,
            )
        except Exception as e:
            logger.warning(f"Could not generate entity comparison: {str(e)}")
            return None

    def _generate_multi_year_projection(
        self, tax_return: "TaxReturn", years_ahead: int
    ) -> Optional[AdvisoryReportSection]:
        """Generate multi-year projection using existing projection engine."""
        logger.debug(f"Generating {years_ahead}-year projection")

        try:
            # Build assumptions for projection engine
            assumptions = {
                'income_growth': 0.03,  # 3% default
                'inflation': 0.025,     # 2.5% default
            }

            # Use existing multi-year projection engine
            projection = self.projection_engine.project_multi_year(
                tax_return=tax_return,
                years=years_ahead,
                assumptions=assumptions,
            )

            content = {
                "base_year": projection.base_year,
                "years_projected": projection.projection_years,
                "yearly_data": [
                    {
                        "year": proj.year,
                        "total_income": float(proj.total_income),
                        "taxable_income": float(proj.taxable_income),
                        "total_tax": float(proj.total_tax),
                        "effective_rate": float(proj.effective_rate),
                        "cumulative_tax": float(proj.cumulative_tax_paid),
                    }
                    for proj in projection.yearly_projections
                ],
                "summary": {
                    "total_projected_income": float(projection.total_projected_income),
                    "total_projected_tax": float(projection.total_projected_tax),
                    "total_strategy_savings": float(projection.total_strategy_savings),
                },
            }

            return AdvisoryReportSection(
                section_id="multi_year_projection",
                title=f"{years_ahead}-Year Tax Projection",
                content=content,
                page_number=7,
            )
        except Exception as e:
            logger.warning(f"Could not generate multi-year projection: {str(e)}")
            return None

    def _generate_action_plan(
        self, tax_return: "TaxReturn", recommendations: ComprehensiveRecommendation
    ) -> AdvisoryReportSection:
        """Generate prioritized action plan."""
        logger.debug("Generating action plan")

        # Group recommendations by priority
        immediate = [o for o in recommendations.top_opportunities if o.priority == "immediate"]
        current_year = [o for o in recommendations.top_opportunities if o.priority == "current_year"]
        next_year = [o for o in recommendations.top_opportunities if o.priority == "next_year"]
        long_term = [o for o in recommendations.top_opportunities if o.priority == "long_term"]

        content = {
            "immediate_actions": [
                {"title": o.title, "action": o.action_required, "savings": float(o.estimated_savings)}
                for o in immediate
            ],
            "current_year_actions": [
                {"title": o.title, "action": o.action_required, "savings": float(o.estimated_savings)}
                for o in current_year
            ],
            "next_year_planning": [
                {"title": o.title, "action": o.action_required, "savings": float(o.estimated_savings)}
                for o in next_year
            ],
            "long_term_strategies": [
                {"title": o.title, "action": o.action_required, "savings": float(o.estimated_savings)}
                for o in long_term
            ],
        }

        return AdvisoryReportSection(
            section_id="action_plan",
            title="Prioritized Action Plan",
            content=content,
            page_number=10,
        )

    def _generate_disclaimers(self) -> AdvisoryReportSection:
        """Generate disclaimers and methodology section."""
        content = {
            "disclaimers": [
                "This report is for informational purposes only and does not constitute tax advice.",
                "Tax calculations are estimates based on current tax law and provided information.",
                "Consult with a licensed tax professional before making tax decisions.",
                "Individual results may vary based on complete financial picture.",
            ],
            "methodology": [
                "Calculations use IRS Publication 17 and current tax brackets.",
                "Recommendations based on proven tax optimization strategies.",
                "Entity comparisons include SE tax, QBI deductions, and compliance costs.",
                "Multi-year projections assume 3% income growth and 2.5% inflation unless specified.",
            ],
        }

        return AdvisoryReportSection(
            section_id="disclaimers",
            title="Disclaimers & Methodology",
            content=content,
            page_number=15,
        )

    # Helper methods

    def _has_business_income(self, tax_return: "TaxReturn") -> bool:
        """Check if tax return has business income."""
        return bool(self._extract_business_income(tax_return))

    def _extract_business_income(self, tax_return: "TaxReturn") -> Optional[Dict[str, float]]:
        """Extract business income from tax return."""
        # Check for self-employment income
        if hasattr(tax_return.income, 'self_employment_income') and tax_return.income.self_employment_income:
            return {
                "gross_income": float(tax_return.income.self_employment_income),
                "expenses": float(getattr(tax_return.income, 'self_employment_expenses', 0)),
            }
        return None

    def _calculate_effective_rate(self, tax_return: "TaxReturn") -> float:
        """Calculate effective tax rate."""
        agi = float(tax_return.adjusted_gross_income or 1)
        total_tax = float((tax_return.tax_liability or 0) + (tax_return.state_tax_liability or 0))
        return round((total_tax / agi * 100), 2) if agi > 0 else 0.0

    def _tax_return_to_projection_data(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Convert TaxReturn to dict for projection engine."""
        total_income = tax_return.income.get_total_income()
        return {
            "filing_status": tax_return.taxpayer.filing_status.value,
            "total_income": float(total_income),
            "agi": float(tax_return.adjusted_gross_income or 0),
            "taxable_income": float(tax_return.taxable_income or 0),
            "tax_liability": float(tax_return.tax_liability or 0),
        }


# Convenience function for quick report generation
def generate_advisory_report(
    tax_return: "TaxReturn",
    report_type: ReportType = ReportType.STANDARD_REPORT,
    **kwargs
) -> AdvisoryReportResult:
    """
    Quick function to generate an advisory report.

    Usage:
        from advisory.report_generator import generate_advisory_report, ReportType

        report = generate_advisory_report(
            tax_return=my_tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=True,
            years_ahead=5,
        )
    """
    generator = AdvisoryReportGenerator()
    return generator.generate_report(tax_return, report_type, **kwargs)
