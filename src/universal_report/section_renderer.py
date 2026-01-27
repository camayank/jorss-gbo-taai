"""
Section Renderer - Conditionally render report sections based on data availability.

This module orchestrates the rendering of all report sections,
only including sections where data is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from decimal import Decimal
import logging
import html

from universal_report.visualizations.savings_gauge import SavingsGauge
from universal_report.visualizations.charts import ReportCharts
from universal_report.visualizations.summary_cards import SummaryCards
from universal_report.branding.logo_handler import LogoHandler

# Import dedicated section renderers
from universal_report.sections.cover_page import CoverPageRenderer
from universal_report.sections.executive_summary import ExecutiveSummaryRenderer
from universal_report.sections.tax_education import TaxEducationRenderer
from universal_report.sections.risk_assessment import RiskAssessmentRenderer
from universal_report.sections.tax_timeline import TaxTimelineRenderer
from universal_report.sections.document_checklist import DocumentChecklistRenderer

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme

logger = logging.getLogger(__name__)


@dataclass
class RenderedSection:
    """A rendered report section."""
    section_id: str
    title: str
    content: str  # HTML content
    order: int
    page_break_before: bool = False
    page_break_after: bool = False


class SectionRenderer:
    """
    Conditionally render report sections based on data availability.

    This class checks what data is available and only renders
    sections that have meaningful content to display.
    """

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
    ):
        self.data = data
        self.theme = theme
        self.charts = ReportCharts(theme)
        self.gauge = SavingsGauge()
        self.cards = SummaryCards(theme)
        self.logo_handler = LogoHandler(theme)

    def should_render(self, section: str) -> bool:
        """
        Check if a section has data to display.

        Args:
            section: Section identifier

        Returns:
            True if section should be rendered
        """
        checks = {
            'cover_page': True,  # Always render
            'executive_summary': True,  # Always render
            'savings_gauge': self.data.has_savings_data(),
            'income_breakdown': self.data.has_income_breakdown(),
            'income_analysis': self.data.gross_income is not None,
            'deductions': self.data.has_deduction_breakdown(),
            'deductions_analysis': self.data.total_deductions is not None,
            'credits': self.data.has_credits(),
            'tax_liability': self.data.tax_liability is not None,
            'recommendations': self.data.has_recommendations(),
            'scenarios': self.data.has_scenarios() and (self.theme.show_scenarios if self.theme else True),
            'entity_comparison': self.data.has_entity_comparison(),
            'projection': self.data.has_projection(),
            'action_items': bool(self.data.action_items) or self.data.has_recommendations(),
            'risk_assessment': True,  # Always render - helps with compliance
            'tax_timeline': True,  # Always render - helpful deadlines
            'document_checklist': True,  # Always render - useful reference
            'tax_education': self.data.has_recommendations(),  # Render when we have recommendations
            'disclaimers': True,  # Always render
            'footer': True,  # Always render
        }
        return checks.get(section, False)

    def render_all(self, tier_level: int = 2) -> List[RenderedSection]:
        """
        Render all applicable sections.

        Args:
            tier_level: Report detail level (1=teaser, 2=full, 3=complete)

        Returns:
            List of rendered sections in order
        """
        sections: List[RenderedSection] = []
        order = 0

        # Cover page - always render
        sections.append(RenderedSection(
            section_id="cover_page",
            title="Cover",
            content=self.render_cover_page(),
            order=order,
            page_break_after=True,
        ))
        order += 1

        # Executive summary - always render
        sections.append(RenderedSection(
            section_id="executive_summary",
            title="Executive Summary",
            content=self.render_executive_summary(),
            order=order,
        ))
        order += 1

        # Savings gauge
        if self.should_render('savings_gauge') and (self.theme is None or self.theme.show_savings_gauge):
            sections.append(RenderedSection(
                section_id="savings_gauge",
                title="Savings Potential",
                content=self.render_savings_section(),
                order=order,
            ))
            order += 1

        # Tax summary cards
        if self.should_render('tax_liability'):
            sections.append(RenderedSection(
                section_id="tax_summary",
                title="Tax Summary",
                content=self.render_tax_summary(),
                order=order,
            ))
            order += 1

        # Income analysis (tier 2+)
        if tier_level >= 2 and self.should_render('income_analysis'):
            sections.append(RenderedSection(
                section_id="income_analysis",
                title="Income Analysis",
                content=self.render_income_analysis(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Deductions analysis (tier 2+)
        if tier_level >= 2 and self.should_render('deductions_analysis'):
            sections.append(RenderedSection(
                section_id="deductions_analysis",
                title="Deductions Analysis",
                content=self.render_deductions_analysis(),
                order=order,
            ))
            order += 1

        # Tax bracket visualization (tier 2+)
        if tier_level >= 2 and self.data.taxable_income:
            sections.append(RenderedSection(
                section_id="tax_brackets",
                title="Tax Bracket Breakdown",
                content=self.render_tax_brackets(),
                order=order,
            ))
            order += 1

        # Recommendations (tier 2+)
        if tier_level >= 2 and self.should_render('recommendations'):
            sections.append(RenderedSection(
                section_id="recommendations",
                title="Tax Optimization Recommendations",
                content=self.render_recommendations(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Scenarios (tier 3)
        if tier_level >= 3 and self.should_render('scenarios'):
            sections.append(RenderedSection(
                section_id="scenarios",
                title="Scenario Comparison",
                content=self.render_scenarios(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Entity comparison (tier 3)
        if tier_level >= 3 and self.should_render('entity_comparison'):
            sections.append(RenderedSection(
                section_id="entity_comparison",
                title="Business Entity Analysis",
                content=self.render_entity_comparison(),
                order=order,
            ))
            order += 1

        # Multi-year projection (tier 3)
        if tier_level >= 3 and self.should_render('projection'):
            sections.append(RenderedSection(
                section_id="projection",
                title="Multi-Year Projection",
                content=self.render_projection(),
                order=order,
            ))
            order += 1

        # Action items
        if self.should_render('action_items'):
            sections.append(RenderedSection(
                section_id="action_items",
                title="Action Plan",
                content=self.render_action_items(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Tax Education (tier 2+) - provide context for recommendations
        if tier_level >= 2 and self.should_render('tax_education'):
            sections.append(RenderedSection(
                section_id="tax_education",
                title="Tax Strategy Education",
                content=self.render_tax_education(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Risk Assessment (tier 2+)
        if tier_level >= 2 and self.should_render('risk_assessment'):
            sections.append(RenderedSection(
                section_id="risk_assessment",
                title="Audit Risk Assessment",
                content=self.render_risk_assessment(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Tax Timeline (tier 2+)
        if tier_level >= 2 and self.should_render('tax_timeline'):
            sections.append(RenderedSection(
                section_id="tax_timeline",
                title="Important Deadlines",
                content=self.render_tax_timeline(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Document Checklist (tier 2+)
        if tier_level >= 2 and self.should_render('document_checklist'):
            sections.append(RenderedSection(
                section_id="document_checklist",
                title="Document Checklist",
                content=self.render_document_checklist(),
                order=order,
                page_break_before=True,
            ))
            order += 1

        # Disclaimers - always render
        sections.append(RenderedSection(
            section_id="disclaimers",
            title="Disclaimers",
            content=self.render_disclaimers(),
            order=order,
            page_break_before=True,
        ))
        order += 1

        return sections

    def render_cover_page(self) -> str:
        """Render the report cover page."""
        primary = self.theme.primary_color if self.theme else "#2563eb"
        accent = self.theme.accent_color if self.theme else "#10b981"

        # Header with logo
        header_html = self.logo_handler.render_header_with_logo()

        # Metrics for cover
        metrics_html = ""
        if self.data.tax_liability is not None:
            metrics_html = f'''
<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 30px 0;">
  <div style="padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Tax Year</div>
    <div style="font-size: 24px; font-weight: 700; color: {primary};">{self.data.tax_year}</div>
  </div>
  <div style="padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Filing Status</div>
    <div style="font-size: 24px; font-weight: 700; color: {primary};">{self.data.filing_status.replace('_', ' ').title()}</div>
  </div>
  <div style="padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Current Tax Liability</div>
    <div style="font-size: 24px; font-weight: 700; color: #ef4444;">${float(self.data.tax_liability):,.0f}</div>
  </div>
  <div style="padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Potential Savings</div>
    <div style="font-size: 24px; font-weight: 700; color: {accent};">${float(self.data.potential_savings_high or 0):,.0f}</div>
  </div>
</div>
'''

        report_title = self.theme.report_title if self.theme else "Tax Advisory Report"

        return f'''
<div class="cover-page">
  {header_html}

  <div style="text-align: center; margin: 60px 0;">
    <h1 style="font-size: 2.5rem; color: {primary}; margin-bottom: 16px;">
      {report_title}
    </h1>
    <div style="font-size: 1.5rem; color: #374151; margin-bottom: 8px;">
      Prepared for: <strong>{html.escape(self.data.taxpayer_name)}</strong>
    </div>
    <div style="font-size: 1rem; color: #6b7280;">
      {self.data.generated_at.strftime("%B %d, %Y")}
    </div>
  </div>

  {metrics_html}

  <div style="text-align: center; margin-top: 40px; padding: 20px; background: #f9fafb; border-radius: 12px;">
    <div style="font-size: 14px; color: #6b7280;">
      This report contains {len(self.data.recommendations)} tax optimization recommendations
    </div>
  </div>
</div>
'''

    def render_executive_summary(self) -> str:
        """Render executive summary section."""
        primary = self.theme.primary_color if self.theme else "#2563eb"

        # Key insights
        insights_html = ""
        if self.data.key_insights:
            insights_html = self.cards.render_insight_badges(
                self.data.key_insights[:5], "info"
            )

        # Warnings
        warnings_html = ""
        if self.data.warnings:
            warnings_html = self.cards.render_insight_badges(
                self.data.warnings[:3], "warning"
            )

        # Summary text
        summary_parts = []
        if self.data.gross_income:
            summary_parts.append(f"Total income of ${float(self.data.gross_income):,.0f}")
        if self.data.tax_liability:
            summary_parts.append(f"current tax liability of ${float(self.data.tax_liability):,.0f}")
        if self.data.effective_rate:
            summary_parts.append(f"effective tax rate of {self.data.effective_rate:.1f}%")

        summary_text = ""
        if summary_parts:
            summary_text = f'''
<p style="font-size: 1.1rem; line-height: 1.7; color: #374151; margin-bottom: 20px;">
  Based on our analysis of your tax situation, you have a {', '.join(summary_parts)}.
  {"We have identified potential savings opportunities totaling up to $" + f"{float(self.data.potential_savings_high):,.0f}" + "." if self.data.potential_savings_high else ""}
</p>
'''

        return f'''
<section class="executive-summary">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Executive Summary
  </h2>

  {summary_text}
  {insights_html}
  {warnings_html}
</section>
'''

    def render_savings_section(self) -> str:
        """Render savings gauge section."""
        if not self.data.potential_savings_high:
            return ""

        # Generate savings gauge
        gauge_svg = self.gauge.render(
            current_liability=self.data.tax_liability or Decimal("0"),
            potential_savings=self.data.potential_savings_high,
            theme=self.theme,
        )

        # Savings highlight card
        highlight_card = self.cards.render_savings_highlight_card(
            current_tax=self.data.tax_liability or Decimal("0"),
            potential_savings=self.data.potential_savings_high,
            confidence=self.data.savings_confidence or 0.85,
        )

        primary = self.theme.primary_color if self.theme else "#2563eb"

        return f'''
<section class="savings-section">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Your Tax Savings Potential
  </h2>

  <div style="display: flex; justify-content: center; margin: 30px 0;">
    {gauge_svg}
  </div>

  {highlight_card}
</section>
'''

    def render_tax_summary(self) -> str:
        """Render tax summary cards."""
        return self.cards.render_tax_summary_cards(
            gross_income=self.data.gross_income or Decimal("0"),
            agi=self.data.adjusted_gross_income or Decimal("0"),
            taxable_income=self.data.taxable_income or Decimal("0"),
            total_tax=self.data.tax_liability or Decimal("0"),
            effective_rate=self.data.effective_rate or 0,
            potential_savings=self.data.potential_savings_high,
        )

    def render_income_analysis(self) -> str:
        """Render income analysis section with pie chart."""
        primary = self.theme.primary_color if self.theme else "#2563eb"

        # Income breakdown chart
        chart_html = ""
        if self.data.income_items:
            chart_svg = self.charts.income_breakdown_pie(
                self.data.income_items,
                width=450,
                height=300,
            )
            chart_html = f'''
<div style="display: flex; justify-content: center; margin: 20px 0;">
  {chart_svg}
</div>
'''

        # Income table
        table_rows = ""
        if self.data.income_items:
            for item in self.data.income_items:
                table_rows += f'''
    <tr>
      <td style="padding: 12px 16px;">{item.category}</td>
      <td style="padding: 12px 16px;">{item.description}</td>
      <td style="padding: 12px 16px; text-align: right;">${float(item.amount):,.0f}</td>
      <td style="padding: 12px 16px; text-align: center;">{item.source_document or '-'}</td>
    </tr>
'''

        return f'''
<section class="income-analysis">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Income Analysis
  </h2>

  {chart_html}

  <table class="data-table" style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <thead>
      <tr style="background: {primary}; color: white;">
        <th style="padding: 12px 16px; text-align: left;">Category</th>
        <th style="padding: 12px 16px; text-align: left;">Description</th>
        <th style="padding: 12px 16px; text-align: right;">Amount</th>
        <th style="padding: 12px 16px; text-align: center;">Source</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
      <tr style="background: #f3f4f6; font-weight: bold;">
        <td colspan="2" style="padding: 12px 16px;">Total Income</td>
        <td style="padding: 12px 16px; text-align: right;">${float(self.data.gross_income or 0):,.0f}</td>
        <td></td>
      </tr>
    </tbody>
  </table>
</section>
'''

    def render_deductions_analysis(self) -> str:
        """Render deductions analysis section."""
        primary = self.theme.primary_color if self.theme else "#2563eb"

        # Deduction comparison chart
        chart_html = ""
        if self.data.standard_deduction_amount or self.data.itemized_deduction_amount:
            chart_svg = self.charts.deduction_comparison_bar(
                standard_deduction=self.data.standard_deduction_amount or Decimal("15000"),
                itemized_deduction=self.data.itemized_deduction_amount or Decimal("0"),
                deduction_type=self.data.deduction_type,
            )
            chart_html = f'''
<div style="display: flex; justify-content: center; margin: 20px 0;">
  {chart_svg}
</div>
'''

        # Deduction items table
        table_rows = ""
        if self.data.deduction_items:
            for item in self.data.deduction_items:
                row_type = "Above-the-line" if item.is_above_line else "Itemized"
                table_rows += f'''
    <tr>
      <td style="padding: 12px 16px;">{item.description}</td>
      <td style="padding: 12px 16px;">{row_type}</td>
      <td style="padding: 12px 16px; text-align: right;">${float(item.amount):,.0f}</td>
      <td style="padding: 12px 16px; text-align: right;">{f"${float(item.irs_limit):,.0f}" if item.irs_limit else '-'}</td>
    </tr>
'''

        return f'''
<section class="deductions-analysis">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Deductions Analysis
  </h2>

  <p style="margin-bottom: 20px;">
    You are using the <strong>{self.data.deduction_type}</strong> deduction method,
    which provides a total deduction of <strong>${float(self.data.total_deductions or 0):,.0f}</strong>.
  </p>

  {chart_html}

  <table class="data-table" style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <thead>
      <tr style="background: {primary}; color: white;">
        <th style="padding: 12px 16px; text-align: left;">Deduction</th>
        <th style="padding: 12px 16px; text-align: left;">Type</th>
        <th style="padding: 12px 16px; text-align: right;">Amount</th>
        <th style="padding: 12px 16px; text-align: right;">IRS Limit</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</section>
'''

    def render_tax_brackets(self) -> str:
        """Render tax bracket breakdown visualization."""
        if not self.data.taxable_income:
            return ""

        primary = self.theme.primary_color if self.theme else "#2563eb"

        chart_svg = self.charts.tax_bracket_visualization(
            taxable_income=self.data.taxable_income,
            filing_status=self.data.filing_status,
        )

        return f'''
<section class="tax-brackets">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Tax Bracket Breakdown
  </h2>

  <div style="display: flex; justify-content: center; margin: 20px 0;">
    {chart_svg}
  </div>

  <div style="background: #f9fafb; padding: 16px; border-radius: 8px; margin-top: 20px;">
    <p style="margin: 0; color: #6b7280; font-size: 14px;">
      <strong>Marginal Rate:</strong> {self.data.marginal_rate or 22}% |
      <strong>Effective Rate:</strong> {self.data.effective_rate or 0:.1f}%
    </p>
  </div>
</section>
'''

    def render_recommendations(self) -> str:
        """Render tax optimization recommendations."""
        if not self.data.recommendations:
            return ""

        primary = self.theme.primary_color if self.theme else "#2563eb"
        accent = self.theme.accent_color if self.theme else "#10b981"

        # Sort by savings
        sorted_recs = sorted(
            self.data.recommendations,
            key=lambda r: r.estimated_savings,
            reverse=True,
        )

        # Total potential savings
        total_savings = sum(r.estimated_savings for r in sorted_recs)

        # Render recommendation cards
        cards_html = ""
        for rec in sorted_recs[:10]:  # Top 10
            cards_html += self.cards.render_recommendation_card(
                title=rec.title,
                description=rec.description,
                savings=rec.estimated_savings,
                priority=rec.priority.value,
                category=rec.category,
                action=rec.action_required,
            )

        return f'''
<section class="recommendations">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Tax Optimization Recommendations
  </h2>

  <div style="background: linear-gradient(135deg, {accent}10 0%, {primary}10 100%); padding: 20px; border-radius: 12px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <div style="font-size: 14px; color: #6b7280;">Total Recommendations</div>
        <div style="font-size: 24px; font-weight: 700; color: {primary};">{len(sorted_recs)}</div>
      </div>
      <div style="text-align: right;">
        <div style="font-size: 14px; color: #6b7280;">Total Potential Savings</div>
        <div style="font-size: 24px; font-weight: 700; color: {accent};">${float(total_savings):,.0f}</div>
      </div>
    </div>
  </div>

  {cards_html}
</section>
'''

    def render_scenarios(self) -> str:
        """Render scenario comparison section."""
        if not self.data.scenarios:
            return ""

        primary = self.theme.primary_color if self.theme else "#2563eb"

        chart_svg = self.charts.scenario_comparison(
            self.data.scenarios,
            width=600,
            height=350,
        )

        return f'''
<section class="scenarios">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Tax Scenario Comparison
  </h2>

  <div style="display: flex; justify-content: center; margin: 20px 0;">
    {chart_svg}
  </div>
</section>
'''

    def render_entity_comparison(self) -> str:
        """Render business entity comparison section."""
        if not self.data.entity_comparison:
            return ""

        primary = self.theme.primary_color if self.theme else "#2563eb"

        # Build comparison table
        entities = self.data.entity_comparison.get("entity_comparison", {})
        table_rows = ""
        for entity_type, analysis in entities.items():
            recommended = "✓" if analysis.get("recommended") else ""
            table_rows += f'''
    <tr>
      <td style="padding: 12px 16px;">{entity_type.replace('_', ' ').title()}</td>
      <td style="padding: 12px 16px; text-align: right;">${analysis.get("total_tax", 0):,.0f}</td>
      <td style="padding: 12px 16px; text-align: right;">${analysis.get("self_employment_tax", 0):,.0f}</td>
      <td style="padding: 12px 16px; text-align: right;">${analysis.get("net_benefit", 0):,.0f}</td>
      <td style="padding: 12px 16px; text-align: center; color: {self.theme.accent_color if self.theme else "#10b981"};">{recommended}</td>
    </tr>
'''

        return f'''
<section class="entity-comparison">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Business Entity Comparison
  </h2>

  <p style="margin-bottom: 20px;">
    This analysis compares different business entity structures to help optimize your tax position.
  </p>

  <table class="data-table" style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <thead>
      <tr style="background: {primary}; color: white;">
        <th style="padding: 12px 16px; text-align: left;">Entity Type</th>
        <th style="padding: 12px 16px; text-align: right;">Total Tax</th>
        <th style="padding: 12px 16px; text-align: right;">SE Tax</th>
        <th style="padding: 12px 16px; text-align: right;">Net Benefit</th>
        <th style="padding: 12px 16px; text-align: center;">Recommended</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</section>
'''

    def render_projection(self) -> str:
        """Render multi-year projection section."""
        if not self.data.multi_year_projection:
            return ""

        primary = self.theme.primary_color if self.theme else "#2563eb"

        projection = self.data.multi_year_projection
        yearly_data = projection.get("yearly_data", [])

        # Create historical data format for chart
        historical = [
            {"year": y.get("year"), "tax": y.get("total_tax", 0)}
            for y in yearly_data
        ]

        chart_svg = ""
        if len(historical) >= 2:
            chart_svg = self.charts.year_over_year_trend(historical)

        # Projection table
        table_rows = ""
        for year_data in yearly_data:
            table_rows += f'''
    <tr>
      <td style="padding: 12px 16px;">{year_data.get("year", "N/A")}</td>
      <td style="padding: 12px 16px; text-align: right;">${year_data.get("total_income", 0):,.0f}</td>
      <td style="padding: 12px 16px; text-align: right;">${year_data.get("taxable_income", 0):,.0f}</td>
      <td style="padding: 12px 16px; text-align: right;">${year_data.get("total_tax", 0):,.0f}</td>
      <td style="padding: 12px 16px; text-align: right;">{year_data.get("effective_rate", 0):.1f}%</td>
    </tr>
'''

        return f'''
<section class="projection">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Multi-Year Tax Projection
  </h2>

  <div style="display: flex; justify-content: center; margin: 20px 0;">
    {chart_svg}
  </div>

  <table class="data-table" style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <thead>
      <tr style="background: {primary}; color: white;">
        <th style="padding: 12px 16px; text-align: left;">Year</th>
        <th style="padding: 12px 16px; text-align: right;">Total Income</th>
        <th style="padding: 12px 16px; text-align: right;">Taxable Income</th>
        <th style="padding: 12px 16px; text-align: right;">Total Tax</th>
        <th style="padding: 12px 16px; text-align: right;">Effective Rate</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</section>
'''

    def render_action_items(self) -> str:
        """Render prioritized action items."""
        primary = self.theme.primary_color if self.theme else "#2563eb"

        # Get immediate actions from recommendations
        immediate = self.data.get_immediate_actions()

        # Group by priority
        current_year = [
            r for r in self.data.recommendations
            if r.priority.value == "current_year"
        ]

        items_html = ""

        if immediate:
            items_html += '''
<h3 style="color: #ef4444; margin: 20px 0 12px 0;">Immediate Actions</h3>
<ul style="list-style: none; padding: 0;">
'''
            for item in immediate[:5]:
                items_html += f'''
  <li style="padding: 12px 16px; background: #fef2f2; border-left: 4px solid #ef4444; margin-bottom: 8px; border-radius: 4px;">
    <strong>{item.title}</strong> - Save ${float(item.estimated_savings):,.0f}
    <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">{item.action_required}</div>
  </li>
'''
            items_html += '</ul>'

        if current_year:
            items_html += '''
<h3 style="color: #f59e0b; margin: 20px 0 12px 0;">This Tax Year</h3>
<ul style="list-style: none; padding: 0;">
'''
            for item in current_year[:5]:
                items_html += f'''
  <li style="padding: 12px 16px; background: #fffbeb; border-left: 4px solid #f59e0b; margin-bottom: 8px; border-radius: 4px;">
    <strong>{item.title}</strong> - Save ${float(item.estimated_savings):,.0f}
    <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">{item.action_required}</div>
  </li>
'''
            items_html += '</ul>'

        return f'''
<section class="action-items">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Action Plan
  </h2>

  <p style="margin-bottom: 20px;">
    Based on our analysis, here are the prioritized actions to optimize your tax situation:
  </p>

  {items_html}
</section>
'''

    def render_disclaimers(self) -> str:
        """Render disclaimers section."""
        muted = self.theme.muted_color if self.theme else "#6b7280"

        custom_disclaimer = ""
        if self.theme and self.theme.disclaimer_text:
            custom_disclaimer = f'''
<p style="margin-bottom: 16px;">{self.theme.disclaimer_text}</p>
'''

        return f'''
<section class="disclaimers" style="color: {muted}; font-size: 12px;">
  <h2 style="font-size: 14px; color: {muted}; margin-bottom: 16px;">Important Disclaimers</h2>

  {custom_disclaimer}

  <p style="margin-bottom: 12px;">
    <strong>NOT TAX ADVICE:</strong> This report is for informational and educational purposes only.
    All calculations, estimates, and recommendations are approximations based on general tax rules
    and may not reflect your actual tax situation.
  </p>

  <p style="margin-bottom: 12px;">
    <strong>CONSULT A PROFESSIONAL:</strong> ALWAYS consult with a licensed CPA, Enrolled Agent,
    or tax attorney before making any tax decisions or filing any tax returns.
    Do not rely solely on this report for tax planning or filing decisions.
  </p>

  <p style="margin-bottom: 12px;">
    <strong>Methodology:</strong> Calculations use IRS Publication 17 and current tax brackets.
    Recommendations are based on proven tax optimization strategies. Multi-year projections
    assume 3% income growth and 2.5% inflation unless specified.
  </p>
</section>
'''

    def render_tax_education(self) -> str:
        """Render tax education section with strategy explanations."""
        renderer = TaxEducationRenderer(self.data, self.theme)
        return renderer.render()

    def render_risk_assessment(self) -> str:
        """Render audit risk assessment section."""
        renderer = RiskAssessmentRenderer(self.data, self.theme)
        return renderer.render()

    def render_tax_timeline(self) -> str:
        """Render tax timeline and deadlines section."""
        renderer = TaxTimelineRenderer(self.data, self.theme)
        return renderer.render()

    def render_document_checklist(self) -> str:
        """Render document checklist section."""
        renderer = DocumentChecklistRenderer(self.data, self.theme)
        return renderer.render()
