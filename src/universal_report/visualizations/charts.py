"""
Report Charts - SVG chart visualizations for tax reports.

Generates various chart types:
- Income breakdown pie/donut chart
- Deduction comparison bar chart
- Scenario comparison grouped bars
- Tax bracket visualization
- Year-over-year trend line chart
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
import math

if TYPE_CHECKING:
    from universal_report.data_collector import IncomeItem, Scenario, TaxBracketInfo
    from universal_report.branding.theme_manager import BrandTheme


class ReportCharts:
    """
    Generate SVG chart visualizations for tax reports.

    All charts are rendered as inline SVG for maximum compatibility
    with both HTML and PDF outputs.
    """

    # Color palettes
    DEFAULT_PALETTE = [
        "#1e3a5f",  # Navy
        "#10b981",  # Green
        "#f59e0b",  # Yellow
        "#ef4444",  # Red
        "#0d9488",  # Teal
        "#06b6d4",  # Cyan
        "#ec4899",  # Pink
        "#1e3a5f",  # Indigo
    ]

    def __init__(self, theme: Optional["BrandTheme"] = None):
        self.theme = theme
        self.palette = self._get_palette()

    def _get_palette(self) -> List[str]:
        """Get color palette from theme or default."""
        if self.theme:
            return [
                self.theme.primary_color,
                self.theme.accent_color,
                self.theme.warning_color,
                self.theme.danger_color,
                self.theme.secondary_color,
            ] + self.DEFAULT_PALETTE[5:]
        return self.DEFAULT_PALETTE

    def income_breakdown_pie(
        self,
        income_items: List["IncomeItem"],
        width: int = 400,
        height: int = 300,
        show_legend: bool = True,
    ) -> str:
        """
        Generate a donut chart showing income breakdown by category.

        Args:
            income_items: List of IncomeItem objects
            width: SVG width
            height: SVG height
            show_legend: Whether to show legend

        Returns:
            SVG string for donut chart
        """
        if not income_items:
            return self._empty_chart(width, height, "No income data available")

        # Calculate total and percentages
        total = sum(float(item.amount) for item in income_items)
        if total == 0:
            return self._empty_chart(width, height, "No income data available")

        # Prepare data
        data = []
        for item in income_items:
            amount = float(item.amount)
            data.append({
                "label": item.category,
                "value": amount,
                "percentage": (amount / total) * 100 if total > 0 else 0,
            })

        # Sort by value descending
        data.sort(key=lambda x: x["value"], reverse=True)

        # Chart dimensions
        cx, cy = 150, 150
        outer_r = 100
        inner_r = 60

        svg_parts = [
            f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="income-pie-chart">
  <defs>
    <filter id="pieShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.15"/>
    </filter>
  </defs>
'''
        ]

        # Draw slices
        start_angle = -90  # Start at top
        for i, item in enumerate(data):
            color = self.palette[i % len(self.palette)]
            sweep_angle = (item["percentage"] / 100) * 360

            if sweep_angle > 0:
                path = self._create_donut_slice(
                    cx, cy, outer_r, inner_r, start_angle, sweep_angle
                )
                svg_parts.append(
                    f'  <path d="{path}" fill="{color}" filter="url(#pieShadow)" '
                    f'class="pie-slice" data-value="{item["value"]:,.0f}"/>\n'
                )
                start_angle += sweep_angle

        # Center text
        svg_parts.append(f'''
  <text x="{cx}" y="{cy - 10}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="12" fill="#6b7280">Total Income</text>
  <text x="{cx}" y="{cy + 15}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="20" font-weight="bold" fill="#1f2937">
    ${total:,.0f}
  </text>
''')

        # Legend
        if show_legend:
            svg_parts.append(self._create_legend(data, 310, 30))

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    def deduction_comparison_bar(
        self,
        standard_deduction: Decimal,
        itemized_deduction: Decimal,
        deduction_type: str = "standard",
        width: int = 400,
        height: int = 200,
    ) -> str:
        """
        Generate side-by-side bar chart comparing standard vs itemized deductions.

        Args:
            standard_deduction: Standard deduction amount
            itemized_deduction: Itemized deduction amount
            deduction_type: Which deduction is being used
            width: SVG width
            height: SVG height

        Returns:
            SVG string for bar chart
        """
        standard = float(standard_deduction or 0)
        itemized = float(itemized_deduction or 0)
        max_val = max(standard, itemized, 1)

        # Bar dimensions
        bar_width = 80
        max_bar_height = 120
        chart_left = 80
        chart_bottom = height - 40

        # Calculate bar heights
        standard_height = (standard / max_val) * max_bar_height
        itemized_height = (itemized / max_val) * max_bar_height

        # Colors based on which is selected
        standard_color = self.palette[0] if deduction_type == "standard" else "#9ca3af"
        itemized_color = self.palette[1] if deduction_type == "itemized" else "#9ca3af"

        svg = f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="deduction-comparison">
  <defs>
    <filter id="barShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.1"/>
    </filter>
  </defs>

  <!-- Chart title -->
  <text x="{width/2}" y="25" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="14" font-weight="600" fill="#374151">Deduction Comparison</text>

  <!-- Y-axis -->
  <line x1="{chart_left}" y1="40" x2="{chart_left}" y2="{chart_bottom}" stroke="#e5e7eb" stroke-width="1"/>

  <!-- X-axis -->
  <line x1="{chart_left}" y1="{chart_bottom}" x2="{width - 40}" y2="{chart_bottom}" stroke="#e5e7eb" stroke-width="1"/>

  <!-- Standard Deduction Bar -->
  <rect x="{chart_left + 30}" y="{chart_bottom - standard_height}"
        width="{bar_width}" height="{standard_height}"
        fill="{standard_color}" rx="4" filter="url(#barShadow)"/>
  <text x="{chart_left + 30 + bar_width/2}" y="{chart_bottom - standard_height - 8}"
        text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="600"
        fill="{standard_color}">${standard:,.0f}</text>
  <text x="{chart_left + 30 + bar_width/2}" y="{chart_bottom + 20}"
        text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="11" fill="#6b7280">Standard</text>

  <!-- Itemized Deduction Bar -->
  <rect x="{chart_left + 150}" y="{chart_bottom - itemized_height}"
        width="{bar_width}" height="{itemized_height}"
        fill="{itemized_color}" rx="4" filter="url(#barShadow)"/>
  <text x="{chart_left + 150 + bar_width/2}" y="{chart_bottom - itemized_height - 8}"
        text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="12" font-weight="600"
        fill="{itemized_color}">${itemized:,.0f}</text>
  <text x="{chart_left + 150 + bar_width/2}" y="{chart_bottom + 20}"
        text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="11" fill="#6b7280">Itemized</text>

  <!-- Recommendation badge -->
  <g transform="translate({chart_left + 30 + bar_width/2 if deduction_type == 'standard' else chart_left + 150 + bar_width/2}, 50)">
    <rect x="-35" y="-12" width="70" height="20" fill="{self.palette[0]}" rx="10"/>
    <text x="0" y="3" text-anchor="middle" font-family="Inter, Arial, sans-serif"
          font-size="10" font-weight="600" fill="white">SELECTED</text>
  </g>
</svg>'''

        return svg

    def scenario_comparison(
        self,
        scenarios: List["Scenario"],
        width: int = 500,
        height: int = 300,
    ) -> str:
        """
        Generate grouped bar chart comparing tax scenarios.

        Args:
            scenarios: List of Scenario objects
            width: SVG width
            height: SVG height

        Returns:
            SVG string for scenario comparison
        """
        if not scenarios:
            return self._empty_chart(width, height, "No scenarios to compare")

        # Prepare data
        data = []
        for scenario in scenarios:
            data.append({
                "name": scenario.name,
                "tax": float(scenario.tax_liability),
                "savings": float(scenario.savings_vs_baseline),
                "recommended": scenario.is_recommended,
            })

        max_tax = max(d["tax"] for d in data)
        if max_tax == 0:
            max_tax = 1

        # Chart dimensions
        chart_left = 80
        chart_right = width - 40
        chart_top = 60
        chart_bottom = height - 60
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top

        bar_width = min(60, (chart_width / len(data)) - 20)

        svg_parts = [
            f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="scenario-comparison">
  <defs>
    <filter id="scenarioShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.1"/>
    </filter>
  </defs>

  <!-- Title -->
  <text x="{width/2}" y="25" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="16" font-weight="600" fill="#374151">Tax Scenario Comparison</text>

  <!-- Subtitle -->
  <text x="{width/2}" y="45" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="11" fill="#6b7280">Compare different tax strategies</text>

  <!-- Y-axis -->
  <line x1="{chart_left}" y1="{chart_top}" x2="{chart_left}" y2="{chart_bottom}"
        stroke="#e5e7eb" stroke-width="1"/>

  <!-- X-axis -->
  <line x1="{chart_left}" y1="{chart_bottom}" x2="{chart_right}" y2="{chart_bottom}"
        stroke="#e5e7eb" stroke-width="1"/>

  <!-- Y-axis labels -->
'''
        ]

        # Y-axis labels
        for i in range(5):
            y = chart_bottom - (i / 4) * chart_height
            val = (i / 4) * max_tax
            svg_parts.append(
                f'  <text x="{chart_left - 10}" y="{y + 4}" text-anchor="end" '
                f'font-family="Inter, Arial, sans-serif" font-size="10" fill="#9ca3af">'
                f'${val:,.0f}</text>\n'
            )
            svg_parts.append(
                f'  <line x1="{chart_left}" y1="{y}" x2="{chart_right}" y2="{y}" '
                f'stroke="#f3f4f6" stroke-width="1"/>\n'
            )

        # Bars
        for i, item in enumerate(data):
            x = chart_left + (i + 0.5) * (chart_width / len(data)) - bar_width / 2
            bar_height = (item["tax"] / max_tax) * chart_height
            y = chart_bottom - bar_height

            color = self.palette[0] if item["recommended"] else self.palette[2]

            svg_parts.append(f'''
  <!-- {item["name"]} -->
  <rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}"
        fill="{color}" rx="4" filter="url(#scenarioShadow)"/>
  <text x="{x + bar_width/2}" y="{y - 8}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="11" font-weight="600" fill="{color}">
    ${item["tax"]:,.0f}
  </text>
  <text x="{x + bar_width/2}" y="{chart_bottom + 15}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="10" fill="#6b7280">
    {item["name"][:12]}
  </text>
''')

            # Recommended badge
            if item["recommended"]:
                svg_parts.append(f'''
  <g transform="translate({x + bar_width/2}, {y - 25})">
    <polygon points="0,-8 8,0 0,8 -8,0" fill="{self.palette[0]}"/>
    <text x="0" y="2" text-anchor="middle" font-family="Inter, Arial, sans-serif"
          font-size="8" fill="white">✓</text>
  </g>
''')

            # Savings indicator
            if item["savings"] > 0:
                svg_parts.append(f'''
  <text x="{x + bar_width/2}" y="{chart_bottom + 28}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="9" fill="{self.palette[1]}">
    Save ${item["savings"]:,.0f}
  </text>
''')

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    def tax_bracket_visualization(
        self,
        taxable_income: Decimal,
        filing_status: str,
        width: int = 500,
        height: int = 200,
    ) -> str:
        """
        Generate horizontal stacked bar showing tax bracket breakdown.

        Args:
            taxable_income: Taxable income amount
            filing_status: Filing status for bracket determination
            width: SVG width
            height: SVG height

        Returns:
            SVG string for tax bracket visualization
        """
        income = float(taxable_income or 0)

        # 2025 Tax Brackets
        brackets = self._get_tax_brackets(filing_status)

        # Calculate amount in each bracket
        bracket_data = []
        remaining = income
        colors = ["#10b981", "#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444", "#dc2626"]

        for i, (limit, rate) in enumerate(brackets):
            if remaining <= 0:
                break
            if i == 0:
                prev_limit = 0
            else:
                prev_limit = brackets[i - 1][0]

            bracket_size = limit - prev_limit
            amount_in_bracket = min(remaining, bracket_size)
            remaining -= amount_in_bracket

            if amount_in_bracket > 0:
                bracket_data.append({
                    "rate": rate,
                    "amount": amount_in_bracket,
                    "color": colors[i % len(colors)],
                })

        if not bracket_data:
            return self._empty_chart(width, height, "No taxable income")

        # Chart dimensions
        chart_left = 60
        chart_right = width - 20
        chart_width = chart_right - chart_left
        bar_y = 100
        bar_height = 40

        svg_parts = [
            f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="tax-bracket-chart">
  <!-- Title -->
  <text x="{width/2}" y="25" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="14" font-weight="600" fill="#374151">Tax Bracket Breakdown</text>
  <text x="{width/2}" y="45" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="11" fill="#6b7280">Taxable Income: ${income:,.0f}</text>

  <!-- Background bar -->
  <rect x="{chart_left}" y="{bar_y}" width="{chart_width}" height="{bar_height}"
        fill="#f3f4f6" rx="4"/>
'''
        ]

        # Draw bracket segments
        x = chart_left
        for item in bracket_data:
            segment_width = (item["amount"] / income) * chart_width if income > 0 else 0
            if segment_width > 0:
                svg_parts.append(f'''
  <rect x="{x}" y="{bar_y}" width="{segment_width}" height="{bar_height}"
        fill="{item["color"]}" rx="4"/>
''')
                # Label if wide enough
                if segment_width > 40:
                    svg_parts.append(f'''
  <text x="{x + segment_width/2}" y="{bar_y + bar_height/2 + 4}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="10" font-weight="600" fill="white">
    {item["rate"]*100:.0f}%
  </text>
''')
                x += segment_width

        # Legend
        legend_y = 160
        legend_x = chart_left
        for item in bracket_data:
            svg_parts.append(f'''
  <rect x="{legend_x}" y="{legend_y}" width="12" height="12" fill="{item["color"]}" rx="2"/>
  <text x="{legend_x + 16}" y="{legend_y + 10}" font-family="Inter, Arial, sans-serif"
        font-size="10" fill="#6b7280">{item["rate"]*100:.0f}%: ${item["amount"]:,.0f}</text>
''')
            legend_x += 100

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    def year_over_year_trend(
        self,
        historical_data: List[Dict[str, Any]],
        width: int = 500,
        height: int = 250,
    ) -> str:
        """
        Generate line chart showing year-over-year tax trends.

        Args:
            historical_data: List of {year, income, tax, effective_rate}
            width: SVG width
            height: SVG height

        Returns:
            SVG string for trend chart
        """
        if not historical_data or len(historical_data) < 2:
            return self._empty_chart(width, height, "Insufficient historical data")

        # Chart dimensions
        chart_left = 70
        chart_right = width - 40
        chart_top = 50
        chart_bottom = height - 50
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top

        # Get data ranges
        years = [d.get("year", 2020 + i) for i, d in enumerate(historical_data)]
        taxes = [float(d.get("tax", 0)) for d in historical_data]
        max_tax = max(taxes) if taxes else 1

        svg_parts = [
            f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="trend-chart">
  <defs>
    <linearGradient id="trendGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{self.palette[0]};stop-opacity:0.3" />
      <stop offset="100%" style="stop-color:{self.palette[0]};stop-opacity:0.05" />
    </linearGradient>
  </defs>

  <!-- Title -->
  <text x="{width/2}" y="25" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="14" font-weight="600" fill="#374151">Tax Liability Trend</text>

  <!-- Axes -->
  <line x1="{chart_left}" y1="{chart_top}" x2="{chart_left}" y2="{chart_bottom}"
        stroke="#e5e7eb" stroke-width="1"/>
  <line x1="{chart_left}" y1="{chart_bottom}" x2="{chart_right}" y2="{chart_bottom}"
        stroke="#e5e7eb" stroke-width="1"/>
'''
        ]

        # Calculate points
        points = []
        for i, (year, tax) in enumerate(zip(years, taxes)):
            x = chart_left + (i / (len(years) - 1)) * chart_width if len(years) > 1 else chart_left
            y = chart_bottom - (tax / max_tax) * chart_height if max_tax > 0 else chart_bottom
            points.append((x, y, year, tax))

        # Draw area under line
        area_points = [f"{chart_left},{chart_bottom}"]
        for x, y, _, _ in points:
            area_points.append(f"{x},{y}")
        area_points.append(f"{chart_right},{chart_bottom}")

        svg_parts.append(
            f'  <polygon points="{" ".join(area_points)}" fill="url(#trendGradient)"/>\n'
        )

        # Draw line
        line_points = " ".join([f"{x},{y}" for x, y, _, _ in points])
        svg_parts.append(
            f'  <polyline points="{line_points}" fill="none" stroke="{self.palette[0]}" '
            f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>\n'
        )

        # Draw points and labels
        for x, y, year, tax in points:
            svg_parts.append(f'''
  <circle cx="{x}" cy="{y}" r="5" fill="white" stroke="{self.palette[0]}" stroke-width="2"/>
  <text x="{x}" y="{chart_bottom + 20}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="10" fill="#6b7280">{year}</text>
  <text x="{x}" y="{y - 12}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="10" font-weight="600" fill="{self.palette[0]}">
    ${tax:,.0f}
  </text>
''')

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    # Helper methods

    def _create_donut_slice(
        self,
        cx: float,
        cy: float,
        outer_r: float,
        inner_r: float,
        start_angle: float,
        sweep_angle: float,
    ) -> str:
        """Create SVG path for donut slice."""
        start_rad = math.radians(start_angle)
        end_rad = math.radians(start_angle + sweep_angle)

        # Outer arc points
        outer_start_x = cx + outer_r * math.cos(start_rad)
        outer_start_y = cy + outer_r * math.sin(start_rad)
        outer_end_x = cx + outer_r * math.cos(end_rad)
        outer_end_y = cy + outer_r * math.sin(end_rad)

        # Inner arc points
        inner_start_x = cx + inner_r * math.cos(start_rad)
        inner_start_y = cy + inner_r * math.sin(start_rad)
        inner_end_x = cx + inner_r * math.cos(end_rad)
        inner_end_y = cy + inner_r * math.sin(end_rad)

        large_arc = 1 if sweep_angle > 180 else 0

        return (
            f"M {outer_start_x} {outer_start_y} "
            f"A {outer_r} {outer_r} 0 {large_arc} 1 {outer_end_x} {outer_end_y} "
            f"L {inner_end_x} {inner_end_y} "
            f"A {inner_r} {inner_r} 0 {large_arc} 0 {inner_start_x} {inner_start_y} Z"
        )

    def _create_legend(
        self,
        data: List[Dict[str, Any]],
        x: float,
        y: float,
    ) -> str:
        """Create chart legend."""
        legend_parts = [f'  <g class="chart-legend">']

        for i, item in enumerate(data[:6]):  # Max 6 items
            color = self.palette[i % len(self.palette)]
            ly = y + i * 25

            legend_parts.append(f'''
    <rect x="{x}" y="{ly}" width="14" height="14" fill="{color}" rx="2"/>
    <text x="{x + 20}" y="{ly + 11}" font-family="Inter, Arial, sans-serif"
          font-size="11" fill="#374151">{item["label"][:15]}</text>
    <text x="{x + 20}" y="{ly + 24}" font-family="Inter, Arial, sans-serif"
          font-size="10" fill="#6b7280">{item["percentage"]:.1f}%</text>
''')

        legend_parts.append('  </g>')
        return '\n'.join(legend_parts)

    def _empty_chart(self, width: int, height: int, message: str) -> str:
        """Generate empty state chart."""
        return f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="empty-chart">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#f9fafb" rx="8"/>
  <text x="{width/2}" y="{height/2}" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="14" fill="#9ca3af">{message}</text>
</svg>'''

    def _get_tax_brackets(self, filing_status: str) -> List[Tuple[float, float]]:
        """Get 2025 tax brackets for filing status."""
        brackets = {
            "single": [
                (11925, 0.10),
                (48475, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250500, 0.32),
                (626350, 0.35),
                (float('inf'), 0.37),
            ],
            "married_joint": [
                (23850, 0.10),
                (96950, 0.12),
                (206700, 0.22),
                (394600, 0.24),
                (501050, 0.32),
                (751600, 0.35),
                (float('inf'), 0.37),
            ],
            "head_of_household": [
                (17000, 0.10),
                (64850, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250500, 0.32),
                (626350, 0.35),
                (float('inf'), 0.37),
            ],
        }
        return brackets.get(filing_status, brackets["single"])
