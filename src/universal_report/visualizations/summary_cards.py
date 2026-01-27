"""
Summary Cards - Key metric display cards for tax reports.

Generates visual summary cards showing:
- Key tax metrics (income, deductions, tax liability)
- Savings potential
- Quick statistics
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from universal_report.branding.theme_manager import BrandTheme


class SummaryCards:
    """
    Generate HTML summary cards for key tax metrics.

    Cards are designed to be responsive and work in both
    HTML and PDF outputs.
    """

    def __init__(self, theme: Optional["BrandTheme"] = None):
        self.theme = theme

    def _get_color(self, color_name: str) -> str:
        """Get color from theme or default."""
        defaults = {
            "primary": "#2563eb",
            "secondary": "#1d4ed8",
            "accent": "#10b981",
            "warning": "#f59e0b",
            "danger": "#ef4444",
            "text": "#1f2937",
            "muted": "#6b7280",
            "background": "#ffffff",
            "border": "#e5e7eb",
        }
        if self.theme:
            color_map = {
                "primary": self.theme.primary_color,
                "secondary": self.theme.secondary_color,
                "accent": self.theme.accent_color,
                "warning": self.theme.warning_color,
                "danger": self.theme.danger_color,
            }
            return color_map.get(color_name, defaults.get(color_name, "#000000"))
        return defaults.get(color_name, "#000000")

    def render_metric_card(
        self,
        title: str,
        value: str,
        subtitle: Optional[str] = None,
        icon: Optional[str] = None,
        color: str = "primary",
        trend: Optional[str] = None,  # "up", "down", "neutral"
        trend_value: Optional[str] = None,
    ) -> str:
        """
        Render a single metric card.

        Args:
            title: Card title
            value: Main value to display
            subtitle: Optional subtitle text
            icon: Optional icon (emoji or SVG path)
            color: Color scheme (primary, accent, warning, danger)
            trend: Trend direction
            trend_value: Trend percentage or amount

        Returns:
            HTML string for the card
        """
        card_color = self._get_color(color)
        border_color = self._get_color("border")
        text_color = self._get_color("text")
        muted_color = self._get_color("muted")

        trend_html = ""
        if trend and trend_value:
            trend_color = self._get_color("accent") if trend == "up" else self._get_color("danger")
            trend_icon = "↑" if trend == "up" else "↓" if trend == "down" else "→"
            trend_html = f'''
        <div style="display: flex; align-items: center; gap: 4px; margin-top: 8px;">
          <span style="color: {trend_color}; font-size: 12px;">{trend_icon} {trend_value}</span>
        </div>
'''

        icon_html = ""
        if icon:
            icon_html = f'''
        <div style="font-size: 24px; margin-bottom: 8px;">{icon}</div>
'''

        subtitle_html = ""
        if subtitle:
            subtitle_html = f'''
        <div style="font-size: 12px; color: {muted_color}; margin-top: 4px;">{subtitle}</div>
'''

        return f'''
<div class="metric-card" style="
  background: white;
  border: 1px solid {border_color};
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  border-top: 4px solid {card_color};
">
  {icon_html}
  <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: {muted_color}; font-weight: 600;">
    {title}
  </div>
  <div style="font-size: 28px; font-weight: 700; color: {text_color}; margin-top: 8px;">
    {value}
  </div>
  {subtitle_html}
  {trend_html}
</div>
'''

    def render_metric_grid(
        self,
        metrics: List[dict],
        columns: int = 3,
    ) -> str:
        """
        Render a grid of metric cards.

        Args:
            metrics: List of metric card configurations
            columns: Number of columns in the grid

        Returns:
            HTML string for the card grid
        """
        cards_html = []
        for metric in metrics:
            cards_html.append(self.render_metric_card(**metric))

        return f'''
<div class="metric-grid" style="
  display: grid;
  grid-template-columns: repeat({columns}, 1fr);
  gap: 20px;
  margin: 20px 0;
">
  {"".join(cards_html)}
</div>
'''

    def render_tax_summary_cards(
        self,
        gross_income: Decimal,
        agi: Decimal,
        taxable_income: Decimal,
        total_tax: Decimal,
        effective_rate: float,
        potential_savings: Optional[Decimal] = None,
    ) -> str:
        """
        Render standard tax summary cards.

        Args:
            gross_income: Total gross income
            agi: Adjusted gross income
            taxable_income: Taxable income
            total_tax: Total tax liability
            effective_rate: Effective tax rate
            potential_savings: Optional potential savings

        Returns:
            HTML string for tax summary cards
        """
        metrics = [
            {
                "title": "Gross Income",
                "value": f"${float(gross_income):,.0f}",
                "icon": "💰",
                "color": "primary",
            },
            {
                "title": "Adjusted Gross Income",
                "value": f"${float(agi):,.0f}",
                "icon": "📊",
                "color": "primary",
            },
            {
                "title": "Taxable Income",
                "value": f"${float(taxable_income):,.0f}",
                "icon": "📋",
                "color": "primary",
            },
            {
                "title": "Total Tax",
                "value": f"${float(total_tax):,.0f}",
                "subtitle": f"Effective Rate: {effective_rate:.1f}%",
                "icon": "🏛️",
                "color": "danger",
            },
        ]

        if potential_savings:
            metrics.append({
                "title": "Potential Savings",
                "value": f"${float(potential_savings):,.0f}",
                "icon": "✨",
                "color": "accent",
            })

        return self.render_metric_grid(metrics, columns=min(len(metrics), 3))

    def render_savings_highlight_card(
        self,
        current_tax: Decimal,
        potential_savings: Decimal,
        optimized_tax: Optional[Decimal] = None,
        confidence: float = 0.85,
    ) -> str:
        """
        Render a highlighted savings card with visual emphasis.

        Args:
            current_tax: Current tax liability
            potential_savings: Potential tax savings
            optimized_tax: Tax after optimization
            confidence: Confidence score (0-1)

        Returns:
            HTML string for savings highlight card
        """
        accent = self._get_color("accent")
        primary = self._get_color("primary")

        if optimized_tax is None:
            optimized_tax = current_tax - potential_savings

        savings_percent = (float(potential_savings) / float(current_tax) * 100) if current_tax else 0

        return f'''
<div class="savings-highlight" style="
  background: linear-gradient(135deg, {accent}10 0%, {primary}10 100%);
  border: 2px solid {accent};
  border-radius: 16px;
  padding: 24px;
  margin: 24px 0;
  text-align: center;
">
  <div style="font-size: 14px; color: {self._get_color('muted')}; text-transform: uppercase; letter-spacing: 1px;">
    Your Potential Tax Savings
  </div>

  <div style="font-size: 48px; font-weight: 800; color: {accent}; margin: 16px 0;">
    ${float(potential_savings):,.0f}
  </div>

  <div style="display: flex; justify-content: center; gap: 40px; margin-top: 24px;">
    <div>
      <div style="font-size: 12px; color: {self._get_color('muted')};">Current Tax</div>
      <div style="font-size: 20px; font-weight: 600; color: {self._get_color('danger')};">
        ${float(current_tax):,.0f}
      </div>
    </div>
    <div style="display: flex; align-items: center; font-size: 24px; color: {accent};">
      →
    </div>
    <div>
      <div style="font-size: 12px; color: {self._get_color('muted')};">Optimized Tax</div>
      <div style="font-size: 20px; font-weight: 600; color: {accent};">
        ${float(optimized_tax):,.0f}
      </div>
    </div>
  </div>

  <div style="margin-top: 20px; display: flex; justify-content: center; gap: 20px;">
    <span style="
      background: {accent};
      color: white;
      padding: 6px 16px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
    ">
      {savings_percent:.0f}% Reduction
    </span>
    <span style="
      background: {self._get_color('border')};
      color: {self._get_color('text')};
      padding: 6px 16px;
      border-radius: 20px;
      font-size: 12px;
    ">
      {confidence*100:.0f}% Confidence
    </span>
  </div>
</div>
'''

    def render_recommendation_card(
        self,
        title: str,
        description: str,
        savings: Decimal,
        priority: str = "current_year",
        category: str = "general",
        action: Optional[str] = None,
    ) -> str:
        """
        Render a recommendation card.

        Args:
            title: Recommendation title
            description: Detailed description
            savings: Estimated savings
            priority: Priority level
            category: Category name
            action: Required action

        Returns:
            HTML string for recommendation card
        """
        priority_colors = {
            "immediate": self._get_color("danger"),
            "current_year": self._get_color("warning"),
            "next_year": self._get_color("primary"),
            "long_term": self._get_color("muted"),
        }
        priority_color = priority_colors.get(priority, self._get_color("primary"))

        action_html = ""
        if action:
            action_html = f'''
      <div style="
        margin-top: 16px;
        padding: 12px;
        background: {self._get_color('primary')}08;
        border-left: 3px solid {self._get_color('primary')};
        border-radius: 4px;
      ">
        <div style="font-size: 11px; color: {self._get_color('muted')}; margin-bottom: 4px;">
          ACTION REQUIRED
        </div>
        <div style="font-size: 13px; color: {self._get_color('text')};">
          {action}
        </div>
      </div>
'''

        return f'''
<div class="recommendation-card" style="
  background: white;
  border: 1px solid {self._get_color('border')};
  border-radius: 12px;
  padding: 20px;
  margin: 12px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
">
  <div style="display: flex; justify-content: space-between; align-items: flex-start;">
    <div style="flex: 1;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <span style="
          background: {priority_color}20;
          color: {priority_color};
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
        ">
          {priority.replace('_', ' ')}
        </span>
        <span style="font-size: 11px; color: {self._get_color('muted')};">
          {category}
        </span>
      </div>
      <div style="font-size: 16px; font-weight: 600; color: {self._get_color('text')};">
        {title}
      </div>
      <div style="font-size: 13px; color: {self._get_color('muted')}; margin-top: 8px; line-height: 1.5;">
        {description}
      </div>
      {action_html}
    </div>
    <div style="text-align: right; margin-left: 20px;">
      <div style="font-size: 11px; color: {self._get_color('muted')};">Est. Savings</div>
      <div style="font-size: 24px; font-weight: 700; color: {self._get_color('accent')};">
        ${float(savings):,.0f}
      </div>
    </div>
  </div>
</div>
'''

    def render_insight_badges(
        self,
        insights: List[str],
        badge_type: str = "info",  # "info", "warning", "success"
    ) -> str:
        """
        Render insight badges.

        Args:
            insights: List of insight strings
            badge_type: Type of badge styling

        Returns:
            HTML string for insight badges
        """
        colors = {
            "info": self._get_color("primary"),
            "warning": self._get_color("warning"),
            "success": self._get_color("accent"),
        }
        color = colors.get(badge_type, self._get_color("primary"))

        badges_html = []
        for insight in insights:
            badges_html.append(f'''
        <span style="
          display: inline-block;
          background: {color}15;
          color: {color};
          padding: 8px 16px;
          border-radius: 20px;
          font-size: 13px;
          margin: 4px;
          border: 1px solid {color}30;
        ">
          {insight}
        </span>
''')

        return f'''
<div class="insight-badges" style="margin: 16px 0;">
  {"".join(badges_html)}
</div>
'''

    def render_progress_indicator(
        self,
        value: float,
        label: str,
        max_value: float = 100,
        color: str = "primary",
    ) -> str:
        """
        Render a progress bar indicator.

        Args:
            value: Current value
            label: Progress label
            max_value: Maximum value
            color: Bar color

        Returns:
            HTML string for progress indicator
        """
        bar_color = self._get_color(color)
        percentage = min(100, (value / max_value * 100)) if max_value > 0 else 0

        return f'''
<div class="progress-indicator" style="margin: 12px 0;">
  <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
    <span style="font-size: 13px; color: {self._get_color('text')};">{label}</span>
    <span style="font-size: 13px; font-weight: 600; color: {bar_color};">{percentage:.0f}%</span>
  </div>
  <div style="
    width: 100%;
    height: 8px;
    background: {self._get_color('border')};
    border-radius: 4px;
    overflow: hidden;
  ">
    <div style="
      width: {percentage}%;
      height: 100%;
      background: {bar_color};
      border-radius: 4px;
      transition: width 0.5s ease;
    "></div>
  </div>
</div>
'''

    def render_detailed_recommendation_card(
        self,
        title: str,
        description: str,
        savings: Decimal,
        priority: str = "current_year",
        category: str = "general",
        action: Optional[str] = None,
        implementation_steps: Optional[List[str]] = None,
        irs_reference: Optional[str] = None,
        complexity: str = "medium",  # "low", "medium", "high"
        timeline: Optional[str] = None,
        requirements: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        expanded: bool = False,
    ) -> str:
        """
        Render an enhanced recommendation card with full details.

        Args:
            title: Recommendation title
            description: Detailed description
            savings: Estimated savings
            priority: Priority level
            category: Category name
            action: Required action
            implementation_steps: List of implementation steps
            irs_reference: IRS publication or form reference
            complexity: Implementation complexity level
            timeline: Suggested timeline
            requirements: Prerequisites or requirements
            risks: Potential risks or considerations
            expanded: Whether to show full details

        Returns:
            HTML string for detailed recommendation card
        """
        priority_colors = {
            "immediate": self._get_color("danger"),
            "current_year": self._get_color("warning"),
            "next_year": self._get_color("primary"),
            "long_term": self._get_color("muted"),
        }
        priority_color = priority_colors.get(priority, self._get_color("primary"))

        complexity_colors = {
            "low": self._get_color("accent"),
            "medium": self._get_color("warning"),
            "high": self._get_color("danger"),
        }
        complexity_color = complexity_colors.get(complexity, self._get_color("warning"))

        complexity_labels = {
            "low": "Easy to implement",
            "medium": "Moderate effort",
            "high": "Complex - may need professional help",
        }

        # Action section
        action_html = ""
        if action:
            action_html = f'''
      <div style="
        margin-top: 16px;
        padding: 12px;
        background: {self._get_color('primary')}08;
        border-left: 3px solid {self._get_color('primary')};
        border-radius: 4px;
      ">
        <div style="font-size: 11px; color: {self._get_color('muted')}; margin-bottom: 4px;">
          ACTION REQUIRED
        </div>
        <div style="font-size: 13px; color: {self._get_color('text')};">
          {action}
        </div>
      </div>
'''

        # Implementation steps section
        steps_html = ""
        if implementation_steps:
            steps_items = ""
            for i, step in enumerate(implementation_steps, 1):
                steps_items += f'''
          <li style="padding: 8px 0; border-bottom: 1px solid {self._get_color('border')}; display: flex; gap: 12px;">
            <span style="
              flex-shrink: 0;
              width: 24px;
              height: 24px;
              background: {self._get_color('primary')};
              color: white;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 12px;
              font-weight: 600;
            ">{i}</span>
            <span style="font-size: 13px; color: {self._get_color('text')}; line-height: 1.5;">{step}</span>
          </li>
'''
            steps_html = f'''
      <div style="margin-top: 16px;">
        <div style="font-size: 12px; font-weight: 600; color: {self._get_color('text')}; margin-bottom: 8px;">
          Implementation Steps
        </div>
        <ol style="list-style: none; padding: 0; margin: 0;">
          {steps_items}
        </ol>
      </div>
'''

        # Requirements section
        requirements_html = ""
        if requirements:
            req_items = "".join([
                f'<li style="padding: 4px 0; font-size: 13px; color: {self._get_color("text")};">• {req}</li>'
                for req in requirements
            ])
            requirements_html = f'''
      <div style="margin-top: 16px; padding: 12px; background: #f9fafb; border-radius: 8px;">
        <div style="font-size: 12px; font-weight: 600; color: {self._get_color('text')}; margin-bottom: 8px;">
          Requirements
        </div>
        <ul style="list-style: none; padding: 0; margin: 0;">
          {req_items}
        </ul>
      </div>
'''

        # Risks section
        risks_html = ""
        if risks:
            risk_items = "".join([
                f'<li style="padding: 4px 0; font-size: 13px; color: {self._get_color("danger")};">⚠ {risk}</li>'
                for risk in risks
            ])
            risks_html = f'''
      <div style="margin-top: 16px; padding: 12px; background: #fef2f2; border-radius: 8px;">
        <div style="font-size: 12px; font-weight: 600; color: {self._get_color('danger')}; margin-bottom: 8px;">
          Considerations
        </div>
        <ul style="list-style: none; padding: 0; margin: 0;">
          {risk_items}
        </ul>
      </div>
'''

        # IRS reference badge
        irs_html = ""
        if irs_reference:
            irs_html = f'''
        <span style="
          display: inline-block;
          background: #dbeafe;
          color: #1d4ed8;
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 10px;
          font-weight: 500;
          margin-left: 8px;
        ">
          📋 {irs_reference}
        </span>
'''

        # Timeline badge
        timeline_html = ""
        if timeline:
            timeline_html = f'''
        <span style="
          display: inline-block;
          background: {self._get_color('primary')}15;
          color: {self._get_color('primary')};
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 10px;
          font-weight: 500;
          margin-left: 8px;
        ">
          ⏱ {timeline}
        </span>
'''

        return f'''
<div class="recommendation-card-detailed" style="
  background: white;
  border: 1px solid {self._get_color('border')};
  border-radius: 12px;
  padding: 24px;
  margin: 16px 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
">
  <!-- Header -->
  <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
    <div style="flex: 1;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
        <span style="
          background: {priority_color}20;
          color: {priority_color};
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
        ">
          {priority.replace('_', ' ')}
        </span>
        <span style="
          background: {complexity_color}15;
          color: {complexity_color};
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 500;
        ">
          {complexity_labels.get(complexity, 'Moderate effort')}
        </span>
        <span style="font-size: 12px; color: {self._get_color('muted')};">
          {category}
        </span>
        {irs_html}
        {timeline_html}
      </div>
      <h3 style="font-size: 18px; font-weight: 700; color: {self._get_color('text')}; margin: 0;">
        {title}
      </h3>
    </div>
    <div style="text-align: right; margin-left: 24px; flex-shrink: 0;">
      <div style="font-size: 11px; color: {self._get_color('muted')}; text-transform: uppercase;">Est. Savings</div>
      <div style="font-size: 28px; font-weight: 800; color: {self._get_color('accent')};">
        ${float(savings):,.0f}
      </div>
    </div>
  </div>

  <!-- Description -->
  <div style="font-size: 14px; color: {self._get_color('muted')}; line-height: 1.6; margin-bottom: 16px;">
    {description}
  </div>

  {action_html}
  {steps_html}
  {requirements_html}
  {risks_html}
</div>
'''

    def render_comparison_table(
        self,
        title: str,
        columns: List[str],
        rows: List[List[str]],
        highlight_row: Optional[int] = None,
    ) -> str:
        """
        Render a comparison table.

        Args:
            title: Table title
            columns: Column headers
            rows: Table rows (list of lists)
            highlight_row: Index of row to highlight

        Returns:
            HTML string for comparison table
        """
        primary = self._get_color("primary")
        accent = self._get_color("accent")

        # Build header
        header_cells = "".join([
            f'<th style="padding: 12px 16px; text-align: left; font-weight: 600; color: white;">{col}</th>'
            for col in columns
        ])

        # Build rows
        body_rows = ""
        for i, row in enumerate(rows):
            is_highlighted = highlight_row is not None and i == highlight_row
            row_style = f'background: {accent}10; border: 2px solid {accent};' if is_highlighted else 'border-bottom: 1px solid #e5e7eb;'

            cells = "".join([
                f'<td style="padding: 12px 16px; {"font-weight: 600; color: " + accent if is_highlighted else ""}">{cell}</td>'
                for cell in row
            ])
            body_rows += f'<tr style="{row_style}">{cells}</tr>'

        return f'''
<div style="margin: 20px 0;">
  <h4 style="color: {primary}; margin-bottom: 12px;">{title}</h4>
  <div style="overflow-x: auto;">
    <table style="width: 100%; border-collapse: collapse; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <thead>
        <tr style="background: {primary};">
          {header_cells}
        </tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </div>
</div>
'''

    def render_stat_comparison(
        self,
        label: str,
        current_value: str,
        optimized_value: str,
        improvement: str,
    ) -> str:
        """
        Render a before/after stat comparison.

        Args:
            label: Stat label
            current_value: Current value
            optimized_value: Optimized value
            improvement: Improvement description

        Returns:
            HTML string for stat comparison
        """
        accent = self._get_color("accent")
        danger = self._get_color("danger")

        return f'''
<div style="display: flex; align-items: center; padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px; margin: 8px 0;">
  <div style="flex: 1;">
    <div style="font-size: 13px; color: {self._get_color('muted')};">{label}</div>
  </div>
  <div style="display: flex; align-items: center; gap: 16px;">
    <div style="text-align: center;">
      <div style="font-size: 11px; color: {self._get_color('muted')};">Current</div>
      <div style="font-size: 18px; font-weight: 600; color: {danger};">{current_value}</div>
    </div>
    <div style="font-size: 20px; color: {accent};">→</div>
    <div style="text-align: center;">
      <div style="font-size: 11px; color: {self._get_color('muted')};">Optimized</div>
      <div style="font-size: 18px; font-weight: 600; color: {accent};">{optimized_value}</div>
    </div>
    <div style="background: {accent}15; color: {accent}; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;">
      {improvement}
    </div>
  </div>
</div>
'''
