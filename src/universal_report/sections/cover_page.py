"""
Cover Page Section - Professional report cover with key metrics.

Provides a visually appealing cover page with:
- CPA branding and logo
- Client information
- Key metrics summary
- Report credibility indicators
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from datetime import datetime
import html

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme
    from universal_report.branding.logo_handler import LogoHandler


class CoverPageRenderer:
    """Render professional cover page for tax advisory reports."""

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
        logo_handler: Optional["LogoHandler"] = None,
    ):
        self.data = data
        self.theme = theme
        self.logo_handler = logo_handler

    def render(self) -> str:
        """Render the complete cover page HTML."""
        primary = self.theme.primary_color if self.theme else "#1e3a5f"
        accent = self.theme.accent_color if self.theme else "#10b981"
        secondary = self.theme.secondary_color if self.theme else "#152b47"

        # Header with logo
        header_html = self._render_header()

        # Title section
        title_section = self._render_title_section(primary)

        # Key metrics
        metrics_section = self._render_metrics_grid(primary, accent)

        # Credibility badges
        credibility_section = self._render_credibility_badges(primary, accent)

        # Report scope summary
        scope_section = self._render_scope_summary(primary)

        # Confidentiality notice
        confidentiality = self._render_confidentiality_notice()

        return f'''
<div class="cover-page" style="min-height: 100vh; display: flex; flex-direction: column;">
  {header_html}

  <div style="flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 40px 0;">
    {title_section}
    {metrics_section}
    {credibility_section}
  </div>

  {scope_section}
  {confidentiality}
</div>
'''

    def _render_header(self) -> str:
        """Render header with logo and firm branding."""
        if self.logo_handler:
            return self.logo_handler.render_header_with_logo()

        # Fallback header
        firm_name = self.theme.firm_name if self.theme else "Tax Advisory"
        primary = self.theme.primary_color if self.theme else "#1e3a5f"

        return f'''
<header style="padding-bottom: 20px; border-bottom: 2px solid {primary}; margin-bottom: 30px;">
  <h1 style="font-size: 1.5rem; color: {primary}; margin: 0;">{firm_name}</h1>
</header>
'''

    def _render_title_section(self, primary: str) -> str:
        """Render main title and client info."""
        report_title = self.theme.report_title if self.theme else "Tax Advisory Report"
        advisor_info = ""

        if self.theme and self.theme.advisor_name:
            credentials = ", ".join(self.theme.advisor_credentials) if self.theme.advisor_credentials else ""
            advisor_info = f'''
    <div style="font-size: 0.9rem; color: #6b7280; margin-top: 16px;">
      Prepared by: <strong>{self.theme.advisor_name}</strong>{f" ({credentials})" if credentials else ""}
    </div>
'''

        return f'''
<div style="text-align: center; margin: 40px 0;">
  <div style="
    display: inline-block;
    padding: 8px 24px;
    background: {primary}10;
    border-radius: 20px;
    font-size: 0.75rem;
    color: {primary};
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 600;
    margin-bottom: 16px;
  ">
    Confidential Tax Analysis
  </div>

  <h1 style="font-size: 2.75rem; color: {primary}; margin: 16px 0; font-weight: 800;">
    {report_title}
  </h1>

  <div style="font-size: 1.5rem; color: #374151;">
    Prepared for: <strong style="color: {primary};">{html.escape(self.data.taxpayer_name)}</strong>
  </div>

  <div style="font-size: 1rem; color: #6b7280; margin-top: 12px;">
    Tax Year {self.data.tax_year} | {self.data.generated_at.strftime("%B %d, %Y")}
  </div>

  {advisor_info}
</div>
'''

    def _render_metrics_grid(self, primary: str, accent: str) -> str:
        """Render key metrics in a visually appealing grid."""
        if self.data.tax_liability is None:
            return ""

        # Calculate savings percentage
        savings_pct = 0
        if self.data.potential_savings_high and self.data.tax_liability:
            savings_pct = (float(self.data.potential_savings_high) / float(self.data.tax_liability)) * 100

        return f'''
<div style="
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
  margin: 40px auto;
  max-width: 600px;
">
  <!-- Tax Year -->
  <div style="
    padding: 24px;
    background: linear-gradient(135deg, {primary}08 0%, {primary}15 100%);
    border: 1px solid {primary}30;
    border-radius: 16px;
    text-align: center;
  ">
    <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Tax Year</div>
    <div style="font-size: 2rem; font-weight: 800; color: {primary}; margin-top: 8px;">{self.data.tax_year}</div>
  </div>

  <!-- Filing Status -->
  <div style="
    padding: 24px;
    background: linear-gradient(135deg, {primary}08 0%, {primary}15 100%);
    border: 1px solid {primary}30;
    border-radius: 16px;
    text-align: center;
  ">
    <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Filing Status</div>
    <div style="font-size: 1.25rem; font-weight: 700; color: {primary}; margin-top: 8px;">
      {self.data.filing_status.replace('_', ' ').title()}
    </div>
  </div>

  <!-- Current Tax -->
  <div style="
    padding: 24px;
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    border: 1px solid #fecaca;
    border-radius: 16px;
    text-align: center;
  ">
    <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Current Tax Liability</div>
    <div style="font-size: 2rem; font-weight: 800; color: #dc2626; margin-top: 8px;">
      ${float(self.data.tax_liability):,.0f}
    </div>
  </div>

  <!-- Potential Savings -->
  <div style="
    padding: 24px;
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    border: 1px solid #a7f3d0;
    border-radius: 16px;
    text-align: center;
    position: relative;
  ">
    <div style="
      position: absolute;
      top: -10px;
      right: 16px;
      background: {accent};
      color: white;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 0.7rem;
      font-weight: 600;
    ">
      {savings_pct:.0f}% SAVINGS
    </div>
    <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Potential Savings</div>
    <div style="font-size: 2rem; font-weight: 800; color: #059669; margin-top: 8px;">
      ${float(self.data.potential_savings_high or 0):,.0f}
    </div>
  </div>
</div>
'''

    def _render_credibility_badges(self, primary: str, accent: str) -> str:
        """Render credibility indicators."""
        rec_count = len(self.data.recommendations)
        confidence = self.data.savings_confidence or 0.85

        return f'''
<div style="
  display: flex;
  justify-content: center;
  gap: 16px;
  margin: 30px 0;
  flex-wrap: wrap;
">
  <div style="
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  ">
    <span style="font-size: 1.25rem;">📊</span>
    <span style="font-size: 0.875rem; color: #374151;"><strong>{rec_count}</strong> Optimization Strategies</span>
  </div>

  <div style="
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  ">
    <span style="font-size: 1.25rem;">✓</span>
    <span style="font-size: 0.875rem; color: #374151;"><strong>{confidence*100:.0f}%</strong> Analysis Confidence</span>
  </div>

  <div style="
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  ">
    <span style="font-size: 1.25rem;">📋</span>
    <span style="font-size: 0.875rem; color: #374151;">IRS Publication 17 Compliant</span>
  </div>
</div>
'''

    def _render_scope_summary(self, primary: str) -> str:
        """Render report scope summary."""
        sections_included = []

        if self.data.has_income_breakdown():
            sections_included.append("Income Analysis")
        if self.data.has_deduction_breakdown():
            sections_included.append("Deductions Review")
        if self.data.has_recommendations():
            sections_included.append("Tax Optimization Strategies")
        if self.data.has_entity_comparison():
            sections_included.append("Business Entity Analysis")
        if self.data.has_projection():
            sections_included.append("Multi-Year Projections")

        if not sections_included:
            return ""

        items_html = "".join([
            f'<li style="padding: 6px 0; color: #374151;">✓ {item}</li>'
            for item in sections_included
        ])

        return f'''
<div style="
  background: #f9fafb;
  border-radius: 12px;
  padding: 24px;
  margin: 30px 0;
">
  <h3 style="font-size: 1rem; color: {primary}; margin: 0 0 16px 0;">This Report Includes:</h3>
  <ul style="list-style: none; padding: 0; margin: 0; column-count: 2; column-gap: 40px;">
    {items_html}
  </ul>
</div>
'''

    def _render_confidentiality_notice(self) -> str:
        """Render confidentiality notice."""
        return '''
<div style="
  text-align: center;
  padding: 16px;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  margin-top: 20px;
">
  <p style="margin: 0; font-size: 0.8rem; color: #92400e;">
    <strong>CONFIDENTIAL:</strong> This report contains sensitive financial information and is intended
    solely for the use of the individual or entity to whom it is addressed. Any unauthorized review,
    use, disclosure, or distribution is prohibited.
  </p>
</div>
'''
