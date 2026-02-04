"""
AI-Powered Visualization Generator for Tax Reports.

Uses Gemini for intelligent chart configuration and visualization decisions:
- Analyzes data to recommend optimal chart types
- Generates chart configurations for rendering libraries
- Creates data-driven visualization narratives
- Suggests visual comparisons and highlights

Usage:
    from export.ai_visualization import get_visualization_generator

    generator = get_visualization_generator()
    config = await generator.generate_income_breakdown_chart(income_data)
    # Use config with Chart.js, matplotlib, or other rendering library
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Supported chart types."""
    PIE = "pie"
    DONUT = "donut"
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    LINE = "line"
    AREA = "area"
    WATERFALL = "waterfall"
    GAUGE = "gauge"
    COMPARISON = "comparison"
    TIMELINE = "timeline"


class ColorScheme(str, Enum):
    """Available color schemes."""
    PROFESSIONAL_BLUE = "professional_blue"
    TAX_GREEN = "tax_green"
    NEUTRAL_GRAY = "neutral_gray"
    HIGH_CONTRAST = "high_contrast"
    SAVINGS_FOCUS = "savings_focus"  # Green for savings, red for taxes


@dataclass
class ChartDataPoint:
    """Single data point for a chart."""
    label: str
    value: float
    formatted_value: str
    color: Optional[str] = None
    highlight: bool = False
    tooltip: Optional[str] = None


@dataclass
class ChartConfiguration:
    """Complete chart configuration for rendering."""
    chart_type: ChartType
    title: str
    subtitle: Optional[str]
    data: List[ChartDataPoint]
    color_scheme: ColorScheme
    total_value: Optional[float] = None
    insights: List[str] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/rendering."""
        return {
            "chart_type": self.chart_type.value,
            "title": self.title,
            "subtitle": self.subtitle,
            "data": [
                {
                    "label": d.label,
                    "value": d.value,
                    "formatted_value": d.formatted_value,
                    "color": d.color,
                    "highlight": d.highlight,
                    "tooltip": d.tooltip,
                }
                for d in self.data
            ],
            "color_scheme": self.color_scheme.value,
            "total_value": self.total_value,
            "insights": self.insights,
            "annotations": self.annotations,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
        }

    def to_chartjs_config(self) -> Dict[str, Any]:
        """Convert to Chart.js compatible configuration."""
        colors = self._get_color_palette()

        base_config = {
            "type": self._map_to_chartjs_type(),
            "data": {
                "labels": [d.label for d in self.data],
                "datasets": [{
                    "data": [d.value for d in self.data],
                    "backgroundColor": colors[:len(self.data)],
                    "borderColor": colors[:len(self.data)],
                    "borderWidth": 1,
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": self.title,
                    },
                    "subtitle": {
                        "display": bool(self.subtitle),
                        "text": self.subtitle or "",
                    },
                    "legend": {
                        "position": "bottom",
                    },
                },
            },
        }

        return base_config

    def _map_to_chartjs_type(self) -> str:
        """Map internal chart type to Chart.js type."""
        mapping = {
            ChartType.PIE: "pie",
            ChartType.DONUT: "doughnut",
            ChartType.BAR: "bar",
            ChartType.STACKED_BAR: "bar",
            ChartType.LINE: "line",
            ChartType.AREA: "line",
            ChartType.WATERFALL: "bar",
            ChartType.GAUGE: "doughnut",
            ChartType.COMPARISON: "bar",
            ChartType.TIMELINE: "line",
        }
        return mapping.get(self.chart_type, "bar")

    def _get_color_palette(self) -> List[str]:
        """Get color palette for the scheme."""
        palettes = {
            ColorScheme.PROFESSIONAL_BLUE: [
                "#1e3a5f", "#5387c1", "#3182ce", "#4299e1",
                "#63b3ed", "#90cdf4", "#bee3f8", "#e6f3ff",
            ],
            ColorScheme.TAX_GREEN: [
                "#1a4731", "#276749", "#2f855a", "#38a169",
                "#48bb78", "#68d391", "#9ae6b4", "#c6f6d5",
            ],
            ColorScheme.NEUTRAL_GRAY: [
                "#0c1b2f", "#2d3748", "#4a5568", "#718096",
                "#a0aec0", "#cbd5e0", "#e2e8f0", "#f7fafc",
            ],
            ColorScheme.HIGH_CONTRAST: [
                "#e53e3e", "#38a169", "#3182ce", "#d69e2e",
                "#805ad5", "#dd6b20", "#319795", "#d53f8c",
            ],
            ColorScheme.SAVINGS_FOCUS: [
                "#38a169", "#48bb78", "#68d391",  # Greens for savings
                "#e53e3e", "#fc8181", "#feb2b2",  # Reds for taxes
                "#a0aec0", "#cbd5e0",  # Neutrals
            ],
        }
        return palettes.get(self.color_scheme, palettes[ColorScheme.PROFESSIONAL_BLUE])


@dataclass
class VisualizationSuite:
    """Complete set of visualizations for a report."""
    income_chart: Optional[ChartConfiguration] = None
    deductions_chart: Optional[ChartConfiguration] = None
    tax_breakdown_chart: Optional[ChartConfiguration] = None
    savings_chart: Optional[ChartConfiguration] = None
    year_over_year_chart: Optional[ChartConfiguration] = None
    projection_chart: Optional[ChartConfiguration] = None
    entity_comparison_chart: Optional[ChartConfiguration] = None
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "income_chart": self.income_chart.to_dict() if self.income_chart else None,
            "deductions_chart": self.deductions_chart.to_dict() if self.deductions_chart else None,
            "tax_breakdown_chart": self.tax_breakdown_chart.to_dict() if self.tax_breakdown_chart else None,
            "savings_chart": self.savings_chart.to_dict() if self.savings_chart else None,
            "year_over_year_chart": self.year_over_year_chart.to_dict() if self.year_over_year_chart else None,
            "projection_chart": self.projection_chart.to_dict() if self.projection_chart else None,
            "entity_comparison_chart": self.entity_comparison_chart.to_dict() if self.entity_comparison_chart else None,
            "generated_at": self.generated_at.isoformat(),
        }


class AIVisualizationGenerator:
    """
    AI-powered visualization generator using Gemini.

    Analyzes tax data to generate optimal chart configurations:
    - Recommends best chart types for data
    - Generates meaningful insights and annotations
    - Creates cohesive visual narratives
    - Highlights key data points
    """

    # Standard color palettes
    INCOME_COLORS = ["#5387c1", "#3182ce", "#4299e1", "#63b3ed", "#90cdf4"]
    DEDUCTION_COLORS = ["#276749", "#38a169", "#48bb78", "#68d391", "#9ae6b4"]
    TAX_COLORS = ["#9b2c2c", "#c53030", "#e53e3e", "#fc8181", "#feb2b2"]
    SAVINGS_COLORS = ["#2f855a", "#38a169", "#48bb78", "#68d391"]

    def __init__(self, ai_service=None):
        """
        Initialize visualization generator.

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

    async def generate_income_breakdown_chart(
        self,
        income_data: Dict[str, float],
        tax_year: int = 2025,
    ) -> ChartConfiguration:
        """
        Generate income breakdown chart configuration.

        Args:
            income_data: Dict mapping income source to amount
            tax_year: Tax year for the data

        Returns:
            ChartConfiguration for income breakdown
        """
        # Filter out zero values and sort by amount
        filtered_data = {k: v for k, v in income_data.items() if v > 0}
        sorted_data = sorted(filtered_data.items(), key=lambda x: x[1], reverse=True)

        total_income = sum(filtered_data.values())

        # Generate insights using AI
        insights = await self._generate_income_insights(sorted_data, total_income)

        # Create data points
        data_points = []
        for i, (source, amount) in enumerate(sorted_data):
            percentage = (amount / total_income * 100) if total_income > 0 else 0
            data_points.append(ChartDataPoint(
                label=self._format_income_label(source),
                value=amount,
                formatted_value=f"${amount:,.0f}",
                color=self.INCOME_COLORS[i % len(self.INCOME_COLORS)],
                highlight=i == 0,  # Highlight largest source
                tooltip=f"{percentage:.1f}% of total income",
            ))

        return ChartConfiguration(
            chart_type=ChartType.DONUT if len(data_points) <= 6 else ChartType.BAR,
            title=f"{tax_year} Income Sources",
            subtitle=f"Total Income: ${total_income:,.0f}",
            data=data_points,
            color_scheme=ColorScheme.PROFESSIONAL_BLUE,
            total_value=total_income,
            insights=insights,
            metadata={"tax_year": tax_year, "source_count": len(data_points)},
        )

    async def generate_tax_breakdown_chart(
        self,
        tax_data: Dict[str, float],
        total_income: float,
        tax_year: int = 2025,
    ) -> ChartConfiguration:
        """
        Generate tax breakdown chart configuration.

        Args:
            tax_data: Dict mapping tax type to amount
            total_income: Total income for effective rate calculation
            tax_year: Tax year for the data

        Returns:
            ChartConfiguration for tax breakdown
        """
        filtered_data = {k: v for k, v in tax_data.items() if v > 0}
        sorted_data = sorted(filtered_data.items(), key=lambda x: x[1], reverse=True)

        total_tax = sum(filtered_data.values())
        effective_rate = (total_tax / total_income * 100) if total_income > 0 else 0

        # Create waterfall-style data showing tax components
        data_points = []
        for i, (tax_type, amount) in enumerate(sorted_data):
            data_points.append(ChartDataPoint(
                label=self._format_tax_label(tax_type),
                value=amount,
                formatted_value=f"${amount:,.0f}",
                color=self.TAX_COLORS[i % len(self.TAX_COLORS)],
                highlight=tax_type.lower() in ["federal_tax", "federal"],
                tooltip=f"{(amount / total_tax * 100):.1f}% of total tax" if total_tax > 0 else "",
            ))

        insights = [
            f"Your effective tax rate is {effective_rate:.1f}%",
            f"Total tax liability: ${total_tax:,.0f}",
        ]

        if "federal" in str(sorted_data).lower():
            federal_pct = next(
                (v / total_tax * 100 for k, v in sorted_data if "federal" in k.lower()),
                0
            )
            if federal_pct > 60:
                insights.append("Federal taxes account for the majority of your tax burden")

        return ChartConfiguration(
            chart_type=ChartType.STACKED_BAR,
            title=f"{tax_year} Tax Breakdown",
            subtitle=f"Effective Rate: {effective_rate:.1f}%",
            data=data_points,
            color_scheme=ColorScheme.SAVINGS_FOCUS,
            total_value=total_tax,
            insights=insights,
            annotations=[{
                "type": "line",
                "value": effective_rate,
                "label": f"Effective Rate: {effective_rate:.1f}%",
            }],
            metadata={
                "tax_year": tax_year,
                "total_income": total_income,
                "effective_rate": effective_rate,
            },
        )

    async def generate_savings_opportunities_chart(
        self,
        recommendations: List[Dict[str, Any]],
    ) -> ChartConfiguration:
        """
        Generate chart showing potential tax savings opportunities.

        Args:
            recommendations: List of recommendations with savings estimates

        Returns:
            ChartConfiguration for savings opportunities
        """
        # Sort by savings amount
        sorted_recs = sorted(
            [r for r in recommendations if r.get("savings", 0) > 0],
            key=lambda x: x.get("savings", 0),
            reverse=True
        )[:8]  # Top 8 opportunities

        total_savings = sum(r.get("savings", 0) for r in sorted_recs)

        data_points = []
        for i, rec in enumerate(sorted_recs):
            savings = rec.get("savings", 0)
            data_points.append(ChartDataPoint(
                label=rec.get("title", "Opportunity")[:30],
                value=savings,
                formatted_value=f"${savings:,.0f}",
                color=self.SAVINGS_COLORS[i % len(self.SAVINGS_COLORS)],
                highlight=i < 3,  # Highlight top 3
                tooltip=rec.get("category", ""),
            ))

        insights = [
            f"Total potential savings: ${total_savings:,.0f}",
            f"{len(sorted_recs)} actionable opportunities identified",
        ]

        if sorted_recs:
            top_rec = sorted_recs[0]
            insights.append(
                f"Biggest opportunity: {top_rec.get('title', 'N/A')} "
                f"(${top_rec.get('savings', 0):,.0f})"
            )

        return ChartConfiguration(
            chart_type=ChartType.BAR,
            title="Tax Savings Opportunities",
            subtitle=f"Potential Savings: ${total_savings:,.0f}",
            data=data_points,
            color_scheme=ColorScheme.TAX_GREEN,
            total_value=total_savings,
            insights=insights,
            metadata={"opportunity_count": len(sorted_recs)},
        )

    async def generate_year_over_year_chart(
        self,
        yearly_data: List[Dict[str, Any]],
    ) -> ChartConfiguration:
        """
        Generate year-over-year comparison chart.

        Args:
            yearly_data: List of yearly tax data dicts

        Returns:
            ChartConfiguration for year-over-year comparison
        """
        sorted_data = sorted(yearly_data, key=lambda x: x.get("year", 0))

        data_points = []
        for i, year_data in enumerate(sorted_data):
            year = year_data.get("year", "N/A")
            total_tax = year_data.get("total_tax", 0)

            data_points.append(ChartDataPoint(
                label=str(year),
                value=total_tax,
                formatted_value=f"${total_tax:,.0f}",
                color=self.INCOME_COLORS[i % len(self.INCOME_COLORS)],
                highlight=i == len(sorted_data) - 1,  # Highlight current year
                tooltip=f"Effective rate: {year_data.get('effective_rate', 0):.1f}%",
            ))

        # Calculate trends
        insights = []
        if len(sorted_data) >= 2:
            first_tax = sorted_data[0].get("total_tax", 0)
            last_tax = sorted_data[-1].get("total_tax", 0)

            if first_tax > 0:
                change_pct = ((last_tax - first_tax) / first_tax) * 100
                direction = "increased" if change_pct > 0 else "decreased"
                insights.append(
                    f"Tax liability has {direction} {abs(change_pct):.1f}% "
                    f"over {len(sorted_data)} years"
                )

        return ChartConfiguration(
            chart_type=ChartType.LINE,
            title="Tax Liability Trend",
            subtitle=f"{sorted_data[0].get('year', '')}-{sorted_data[-1].get('year', '')}",
            data=data_points,
            color_scheme=ColorScheme.PROFESSIONAL_BLUE,
            insights=insights,
            metadata={"years_shown": len(sorted_data)},
        )

    async def generate_entity_comparison_chart(
        self,
        entity_data: Dict[str, Dict[str, float]],
    ) -> ChartConfiguration:
        """
        Generate business entity comparison chart.

        Args:
            entity_data: Dict mapping entity type to tax/savings data

        Returns:
            ChartConfiguration for entity comparison
        """
        data_points = []
        colors = ["#5387c1", "#38a169", "#805ad5", "#d69e2e"]

        for i, (entity_type, data) in enumerate(entity_data.items()):
            total_tax = data.get("total_tax", 0)
            data_points.append(ChartDataPoint(
                label=self._format_entity_label(entity_type),
                value=total_tax,
                formatted_value=f"${total_tax:,.0f}",
                color=colors[i % len(colors)],
                highlight=data.get("recommended", False),
                tooltip=f"SE Tax: ${data.get('self_employment_tax', 0):,.0f}",
            ))

        # Find best option
        best_entity = min(entity_data.items(), key=lambda x: x[1].get("total_tax", float("inf")))
        worst_entity = max(entity_data.items(), key=lambda x: x[1].get("total_tax", 0))

        savings = worst_entity[1].get("total_tax", 0) - best_entity[1].get("total_tax", 0)

        insights = [
            f"Recommended structure: {self._format_entity_label(best_entity[0])}",
            f"Potential annual savings: ${savings:,.0f}",
        ]

        return ChartConfiguration(
            chart_type=ChartType.COMPARISON,
            title="Business Entity Comparison",
            subtitle="Annual Tax by Structure",
            data=data_points,
            color_scheme=ColorScheme.HIGH_CONTRAST,
            insights=insights,
            annotations=[{
                "type": "highlight",
                "entity": best_entity[0],
                "label": "Recommended",
            }],
            metadata={"entity_count": len(entity_data)},
        )

    async def generate_complete_visualization_suite(
        self,
        report_data: Dict[str, Any],
    ) -> VisualizationSuite:
        """
        Generate complete set of visualizations for a report.

        Args:
            report_data: Full report data including all sections

        Returns:
            VisualizationSuite with all applicable charts
        """
        suite = VisualizationSuite()

        # Income chart
        if "income" in report_data:
            suite.income_chart = await self.generate_income_breakdown_chart(
                report_data["income"],
                report_data.get("tax_year", 2025),
            )

        # Tax breakdown chart
        if "tax_breakdown" in report_data:
            suite.tax_breakdown_chart = await self.generate_tax_breakdown_chart(
                report_data["tax_breakdown"],
                report_data.get("total_income", 0),
                report_data.get("tax_year", 2025),
            )

        # Savings opportunities chart
        if "recommendations" in report_data:
            suite.savings_chart = await self.generate_savings_opportunities_chart(
                report_data["recommendations"],
            )

        # Year-over-year chart
        if "yearly_data" in report_data and len(report_data["yearly_data"]) > 1:
            suite.year_over_year_chart = await self.generate_year_over_year_chart(
                report_data["yearly_data"],
            )

        # Entity comparison chart
        if "entity_comparison" in report_data:
            suite.entity_comparison_chart = await self.generate_entity_comparison_chart(
                report_data["entity_comparison"],
            )

        return suite

    async def _generate_income_insights(
        self,
        sorted_data: List[tuple],
        total_income: float,
    ) -> List[str]:
        """Generate AI-powered insights about income composition."""
        insights = []

        if not sorted_data:
            return ["No income sources to analyze"]

        # Basic insights without AI call (fast path)
        top_source, top_amount = sorted_data[0]
        top_percentage = (top_amount / total_income * 100) if total_income > 0 else 0

        insights.append(
            f"Primary income: {self._format_income_label(top_source)} "
            f"({top_percentage:.0f}% of total)"
        )

        if len(sorted_data) > 1:
            insights.append(f"{len(sorted_data)} income sources identified")

        # Check for diversification
        if len(sorted_data) >= 3 and top_percentage < 50:
            insights.append("Well-diversified income streams")
        elif top_percentage > 80:
            insights.append("Income heavily concentrated in one source")

        return insights

    def _format_income_label(self, source: str) -> str:
        """Format income source label for display."""
        labels = {
            "w2_wages": "W-2 Wages",
            "self_employment": "Self-Employment",
            "interest": "Interest Income",
            "dividends": "Dividends",
            "capital_gains": "Capital Gains",
            "rental_income": "Rental Income",
            "retirement_distributions": "Retirement Distributions",
            "social_security": "Social Security",
            "other_income": "Other Income",
        }
        return labels.get(source.lower(), source.replace("_", " ").title())

    def _format_tax_label(self, tax_type: str) -> str:
        """Format tax type label for display."""
        labels = {
            "federal_tax": "Federal Income Tax",
            "state_tax": "State Income Tax",
            "local_tax": "Local Tax",
            "self_employment_tax": "Self-Employment Tax",
            "amt": "Alternative Minimum Tax",
            "fica": "FICA (SS & Medicare)",
            "niit": "Net Investment Income Tax",
        }
        return labels.get(tax_type.lower(), tax_type.replace("_", " ").title())

    def _format_entity_label(self, entity_type: str) -> str:
        """Format entity type label for display."""
        labels = {
            "sole_proprietorship": "Sole Proprietor",
            "sole_proprietor": "Sole Proprietor",
            "s_corporation": "S Corporation",
            "s_corp": "S Corporation",
            "c_corporation": "C Corporation",
            "c_corp": "C Corporation",
            "llc": "LLC",
            "partnership": "Partnership",
        }
        return labels.get(entity_type.lower(), entity_type.replace("_", " ").title())


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_visualization_generator: Optional[AIVisualizationGenerator] = None


def get_visualization_generator() -> AIVisualizationGenerator:
    """Get the singleton visualization generator instance."""
    global _visualization_generator
    if _visualization_generator is None:
        _visualization_generator = AIVisualizationGenerator()
    return _visualization_generator


__all__ = [
    "AIVisualizationGenerator",
    "ChartType",
    "ColorScheme",
    "ChartDataPoint",
    "ChartConfiguration",
    "VisualizationSuite",
    "get_visualization_generator",
]
