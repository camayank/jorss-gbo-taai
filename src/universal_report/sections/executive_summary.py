"""
Executive Summary Section - High-impact summary of tax analysis.

Provides:
- Key metrics at a glance
- Savings opportunity highlights
- Top recommendations preview
- Risk level indicator
- Action priority summary
"""

from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme


class ExecutiveSummaryRenderer:
    """Render comprehensive executive summary."""

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
    ):
        self.data = data
        self.theme = theme

    def render(self) -> str:
        """Render the complete executive summary."""
        primary = self.theme.primary_color if self.theme else "#1e3a5f"
        accent = self.theme.accent_color if self.theme else "#10b981"
        warning = self.theme.warning_color if self.theme else "#f59e0b"
        danger = self.theme.danger_color if self.theme else "#ef4444"

        # Key metrics cards
        metrics_html = self._render_key_metrics(primary, accent, danger)

        # Tax situation summary
        summary_html = self._render_tax_summary(primary)

        # Savings opportunities
        savings_html = self._render_savings_opportunities(primary, accent)

        # Top recommendations
        recs_html = self._render_top_recommendations(primary, accent, warning)

        # Quick insights
        insights_html = self._render_quick_insights(primary, warning)

        # Next steps
        next_steps_html = self._render_next_steps(primary, accent)

        return f'''
<section class="executive-summary">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Executive Summary
  </h2>

  {metrics_html}
  {summary_html}
  {savings_html}
  {recs_html}
  {insights_html}
  {next_steps_html}
</section>
'''

    def _render_key_metrics(self, primary: str, accent: str, danger: str) -> str:
        """Render key metrics cards."""
        # Calculate metrics
        gross = float(self.data.gross_income or 0)
        agi = float(self.data.adjusted_gross_income or gross)
        tax = float(self.data.tax_liability or 0)
        effective_rate = self.data.effective_rate or (tax / gross * 100 if gross > 0 else 0)
        savings = float(self.data.potential_savings_high or 0)
        savings_pct = (savings / tax * 100) if tax > 0 else 0

        return f'''
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px;">
  <!-- Gross Income -->
  <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border: 1px solid #7dd3fc; border-radius: 12px; padding: 16px; text-align: center;">
    <div style="font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Gross Income</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: #0369a1; margin-top: 8px;">${gross:,.0f}</div>
  </div>

  <!-- AGI -->
  <div style="background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%); border: 1px solid #c4b5fd; border-radius: 12px; padding: 16px; text-align: center;">
    <div style="font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Adjusted Gross</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: #0d9488; margin-top: 8px;">${agi:,.0f}</div>
  </div>

  <!-- Tax Liability -->
  <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 1px solid #fecaca; border-radius: 12px; padding: 16px; text-align: center;">
    <div style="font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Tax Liability</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: {danger}; margin-top: 8px;">${tax:,.0f}</div>
  </div>

  <!-- Effective Rate -->
  <div style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border: 1px solid #fcd34d; border-radius: 12px; padding: 16px; text-align: center;">
    <div style="font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Effective Rate</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: #b45309; margin-top: 8px;">{effective_rate:.1f}%</div>
  </div>

  <!-- Potential Savings -->
  <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border: 1px solid #6ee7b7; border-radius: 12px; padding: 16px; text-align: center; position: relative;">
    {f'<div style="position: absolute; top: -8px; right: 8px; background: {accent}; color: white; padding: 2px 8px; border-radius: 8px; font-size: 0.65rem; font-weight: 600;">{savings_pct:.0f}% SAVINGS</div>' if savings > 0 else ''}
    <div style="font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Potential Savings</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: {accent}; margin-top: 8px;">${savings:,.0f}</div>
  </div>

  <!-- Recommendations -->
  <div style="background: linear-gradient(135deg, {primary}08 0%, {primary}15 100%); border: 1px solid {primary}40; border-radius: 12px; padding: 16px; text-align: center;">
    <div style="font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Strategies</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: {primary}; margin-top: 8px;">{len(self.data.recommendations)}</div>
  </div>
</div>
'''

    def _render_tax_summary(self, primary: str) -> str:
        """Render tax situation summary paragraph."""
        # Build summary text
        parts = []

        if self.data.gross_income:
            parts.append(f"total gross income of **${float(self.data.gross_income):,.0f}**")

        if self.data.filing_status:
            status_display = self.data.filing_status.replace('_', ' ').title()
            parts.append(f"filing status of **{status_display}**")

        if self.data.tax_liability:
            parts.append(f"projected federal tax liability of **${float(self.data.tax_liability):,.0f}**")

        if self.data.effective_rate:
            parts.append(f"effective tax rate of **{self.data.effective_rate:.1f}%**")

        if not parts:
            return ""

        summary = f"Based on our comprehensive analysis, you have a {', '.join(parts[:2])}"
        if len(parts) > 2:
            summary += f", resulting in a {', '.join(parts[2:])}"
        summary += "."

        # Add savings context
        if self.data.potential_savings_high and self.data.tax_liability:
            savings = float(self.data.potential_savings_high)
            savings_pct = (savings / float(self.data.tax_liability)) * 100
            summary += f" We have identified optimization opportunities that could reduce your tax burden by up to **${savings:,.0f}** ({savings_pct:.0f}%)."

        # Convert markdown-style bold to HTML
        summary = summary.replace("**", "<strong>", 1)
        while "**" in summary:
            summary = summary.replace("**", "</strong>", 1).replace("**", "<strong>", 1)
        if summary.count("<strong>") > summary.count("</strong>"):
            summary += "</strong>"

        return f'''
<div style="background: #f9fafb; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
  <p style="margin: 0; font-size: 1rem; line-height: 1.7; color: #374151;">
    {summary}
  </p>
</div>
'''

    def _render_savings_opportunities(self, primary: str, accent: str) -> str:
        """Render savings opportunities summary."""
        if not self.data.potential_savings_high:
            return ""

        savings = float(self.data.potential_savings_high)
        confidence = self.data.savings_confidence or 0.85

        # Calculate range
        low = savings * 0.7
        high = savings

        return f'''
<div style="background: linear-gradient(135deg, {accent}08 0%, {accent}15 100%); border: 1px solid {accent}40; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
  <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
    <div>
      <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 4px;">Estimated Tax Savings Range</div>
      <div style="font-size: 2rem; font-weight: 700; color: {accent};">
        ${low:,.0f} - ${high:,.0f}
      </div>
    </div>
    <div style="text-align: right;">
      <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 4px;">Analysis Confidence</div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <div style="width: 80px; height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden;">
          <div style="width: {confidence*100}%; height: 100%; background: {accent}; border-radius: 4px;"></div>
        </div>
        <span style="font-weight: 600; color: {accent};">{confidence*100:.0f}%</span>
      </div>
    </div>
  </div>
</div>
'''

    def _render_top_recommendations(self, primary: str, accent: str, warning: str) -> str:
        """Render top 3 recommendations preview."""
        if not self.data.recommendations:
            return ""

        # Sort by savings and get top 3
        sorted_recs = sorted(
            self.data.recommendations,
            key=lambda r: r.estimated_savings,
            reverse=True
        )[:3]

        cards_html = ""
        for i, rec in enumerate(sorted_recs, 1):
            priority_color = accent if i == 1 else (warning if i == 2 else primary)
            cards_html += f'''
<div style="display: flex; gap: 16px; padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px;">
  <div style="flex-shrink: 0; width: 32px; height: 32px; background: {priority_color}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.875rem;">
    {i}
  </div>
  <div style="flex: 1;">
    <div style="font-weight: 600; color: #111827; margin-bottom: 4px;">{rec.title}</div>
    <div style="font-size: 0.875rem; color: #6b7280;">{rec.description[:100]}...</div>
  </div>
  <div style="text-align: right; flex-shrink: 0;">
    <div style="font-size: 0.75rem; color: #6b7280;">Est. Savings</div>
    <div style="font-size: 1.125rem; font-weight: 700; color: {accent};">${float(rec.estimated_savings):,.0f}</div>
  </div>
</div>
'''

        return f'''
<div style="margin-bottom: 24px;">
  <h3 style="color: {primary}; margin: 0 0 16px 0; font-size: 1rem;">Top Savings Opportunities</h3>
  {cards_html}
  <p style="font-size: 0.875rem; color: #6b7280; margin-top: 8px;">
    See the full Recommendations section for {len(self.data.recommendations)} total strategies.
  </p>
</div>
'''

    def _render_quick_insights(self, primary: str, warning: str) -> str:
        """Render quick insights and alerts."""
        insights_html = ""

        # Add key insights
        if self.data.key_insights:
            for insight in self.data.key_insights[:3]:
                insights_html += f'''
<div style="display: flex; gap: 12px; align-items: flex-start; padding: 12px; background: {primary}08; border-radius: 8px; margin-bottom: 8px;">
  <span style="color: {primary}; font-size: 1.25rem;">ℹ️</span>
  <span style="font-size: 0.875rem; color: #374151;">{insight}</span>
</div>
'''

        # Add warnings
        if self.data.warnings:
            for warning_text in self.data.warnings[:2]:
                insights_html += f'''
<div style="display: flex; gap: 12px; align-items: flex-start; padding: 12px; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; margin-bottom: 8px;">
  <span style="color: {warning}; font-size: 1.25rem;">⚠️</span>
  <span style="font-size: 0.875rem; color: #92400e;">{warning_text}</span>
</div>
'''

        if not insights_html:
            return ""

        return f'''
<div style="margin-bottom: 24px;">
  <h3 style="color: {primary}; margin: 0 0 16px 0; font-size: 1rem;">Key Insights</h3>
  {insights_html}
</div>
'''

    def _render_next_steps(self, primary: str, accent: str) -> str:
        """Render next steps section."""
        # Get immediate actions
        immediate = self.data.get_immediate_actions()[:3]

        steps_html = ""
        for i, action in enumerate(immediate, 1):
            steps_html += f'''
<div style="display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f3f4f6;">
  <div style="flex-shrink: 0; width: 24px; height: 24px; background: {primary}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600;">
    {i}
  </div>
  <div>
    <div style="font-weight: 500; color: #111827;">{action.title}</div>
    <div style="font-size: 0.8125rem; color: #6b7280; margin-top: 2px;">{action.action_required}</div>
  </div>
</div>
'''

        if not steps_html:
            steps_html = '''
<div style="padding: 16px; background: #f9fafb; border-radius: 8px; text-align: center;">
  <p style="margin: 0; color: #6b7280;">Review the full report for detailed recommendations and action items.</p>
</div>
'''

        return f'''
<div style="background: white; border: 2px solid {primary}; border-radius: 12px; padding: 20px;">
  <h3 style="color: {primary}; margin: 0 0 16px 0; font-size: 1rem; display: flex; align-items: center; gap: 8px;">
    <span style="font-size: 1.25rem;">🎯</span> Recommended Next Steps
  </h3>
  {steps_html}
</div>
'''
