"""
Savings Gauge - SVG visualization for potential tax savings.

Generates a semi-circular gauge/meter showing:
- Current tax liability (red zone)
- Potential savings (green zone)
- Animated needle pointing to current position
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import math

if TYPE_CHECKING:
    from universal_report.branding.theme_manager import BrandTheme


class SavingsGauge:
    """
    Generate SVG savings gauge/meter visualization.

    The gauge shows a semi-circular meter with:
    - Red zone: Current tax liability area
    - Green zone: Potential savings area
    - Needle: Points to current position
    - Labels: Dollar amounts displayed
    """

    def __init__(self):
        self.width = 400
        self.height = 250
        self.center_x = 200
        self.center_y = 200
        self.radius = 150
        self.inner_radius = 100

    def render(
        self,
        current_liability: Decimal,
        potential_savings: Decimal,
        max_value: Optional[Decimal] = None,
        theme: Optional["BrandTheme"] = None,
        animate: bool = True,
    ) -> str:
        """
        Render SVG savings gauge.

        Args:
            current_liability: Current tax liability amount
            potential_savings: Potential savings amount
            max_value: Maximum value for gauge scale (auto-calculated if None)
            theme: Brand theme for colors
            animate: Whether to include CSS animation

        Returns:
            SVG string for the gauge
        """
        # Default colors if no theme
        primary_color = theme.primary_color if theme else "#2563eb"
        accent_color = theme.accent_color if theme else "#10b981"
        danger_color = theme.danger_color if theme else "#ef4444"

        # Calculate values
        current = float(current_liability or 0)
        savings = float(potential_savings or 0)
        optimized = max(0, current - savings)

        # Auto-calculate max value
        if max_value is None:
            max_value = Decimal(str(current * 1.2)) if current > 0 else Decimal("10000")
        max_val = float(max_value)

        # Calculate angles (180 degrees = full semi-circle)
        # Gauge goes from 180 degrees (left) to 0 degrees (right)
        savings_percentage = min(1.0, savings / current) if current > 0 else 0
        current_angle = 180 - (savings_percentage * 180)  # Needle position

        # Create SVG
        svg_parts = [
            f'''<svg viewBox="0 0 {self.width} {self.height}" xmlns="http://www.w3.org/2000/svg" class="savings-gauge">
  <defs>
    <!-- Gradient for the gauge arc -->
    <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{accent_color};stop-opacity:1" />
      <stop offset="50%" style="stop-color:#fbbf24;stop-opacity:1" />
      <stop offset="100%" style="stop-color:{danger_color};stop-opacity:1" />
    </linearGradient>

    <!-- Drop shadow for depth -->
    <filter id="gaugeShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.2"/>
    </filter>

    <!-- Glow effect for savings zone -->
    <filter id="savingsGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
'''
        ]

        # Background arc (gray track)
        svg_parts.append(self._create_arc(
            self.center_x, self.center_y, self.radius, self.inner_radius,
            180, 0, "#e5e7eb", "background-arc"
        ))

        # Savings zone (green arc on the left side)
        if savings_percentage > 0:
            savings_end_angle = 180 - (savings_percentage * 180)
            svg_parts.append(self._create_arc(
                self.center_x, self.center_y, self.radius, self.inner_radius,
                180, savings_end_angle, accent_color, "savings-arc",
                filter_id="savingsGlow"
            ))

        # Current liability zone (remaining portion)
        if savings_percentage < 1:
            liability_start_angle = 180 - (savings_percentage * 180)
            svg_parts.append(self._create_arc(
                self.center_x, self.center_y, self.radius, self.inner_radius,
                liability_start_angle, 0, danger_color, "liability-arc",
                opacity=0.7
            ))

        # Tick marks
        svg_parts.append(self._create_tick_marks(primary_color))

        # Needle
        needle_svg = self._create_needle(current_angle, primary_color, animate)
        svg_parts.append(needle_svg)

        # Center circle
        svg_parts.append(f'''
  <circle cx="{self.center_x}" cy="{self.center_y}" r="20" fill="white" filter="url(#gaugeShadow)"/>
  <circle cx="{self.center_x}" cy="{self.center_y}" r="15" fill="{primary_color}"/>
  <circle cx="{self.center_x}" cy="{self.center_y}" r="8" fill="white"/>
''')

        # Labels
        svg_parts.append(self._create_labels(current, savings, optimized, primary_color, accent_color))

        # Legend
        svg_parts.append(self._create_legend(accent_color, danger_color))

        # Animation styles
        if animate:
            svg_parts.append(f'''
  <style>
    .gauge-needle {{
      transform-origin: {self.center_x}px {self.center_y}px;
      animation: needleSweep 1.5s ease-out forwards;
    }}
    @keyframes needleSweep {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate({180 - current_angle}deg); }}
    }}
    .savings-arc {{
      stroke-dasharray: 1000;
      stroke-dashoffset: 1000;
      animation: arcDraw 1s ease-out forwards;
    }}
    @keyframes arcDraw {{
      to {{ stroke-dashoffset: 0; }}
    }}
  </style>
''')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _create_arc(
        self,
        cx: float,
        cy: float,
        outer_r: float,
        inner_r: float,
        start_angle: float,
        end_angle: float,
        color: str,
        class_name: str,
        filter_id: Optional[str] = None,
        opacity: float = 1.0
    ) -> str:
        """Create an arc path for the gauge."""
        # Convert angles to radians
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        # Calculate points
        outer_start_x = cx + outer_r * math.cos(start_rad)
        outer_start_y = cy - outer_r * math.sin(start_rad)
        outer_end_x = cx + outer_r * math.cos(end_rad)
        outer_end_y = cy - outer_r * math.sin(end_rad)

        inner_start_x = cx + inner_r * math.cos(start_rad)
        inner_start_y = cy - inner_r * math.sin(start_rad)
        inner_end_x = cx + inner_r * math.cos(end_rad)
        inner_end_y = cy - inner_r * math.sin(end_rad)

        # Determine if arc is large (> 180 degrees)
        large_arc = 1 if abs(start_angle - end_angle) > 180 else 0

        # Create path
        path = f'''M {outer_start_x} {outer_start_y}
                   A {outer_r} {outer_r} 0 {large_arc} 0 {outer_end_x} {outer_end_y}
                   L {inner_end_x} {inner_end_y}
                   A {inner_r} {inner_r} 0 {large_arc} 1 {inner_start_x} {inner_start_y}
                   Z'''

        filter_attr = f'filter="url(#{filter_id})"' if filter_id else ''

        return f'''
  <path d="{path}" fill="{color}" class="{class_name}" {filter_attr} opacity="{opacity}"/>
'''

    def _create_needle(self, angle: float, color: str, animate: bool) -> str:
        """Create the gauge needle."""
        needle_length = self.radius - 30
        rad = math.radians(angle)

        # Needle tip
        tip_x = self.center_x + needle_length * math.cos(rad)
        tip_y = self.center_y - needle_length * math.sin(rad)

        # Needle base (wider)
        base_width = 10
        base_rad1 = math.radians(angle + 90)
        base_rad2 = math.radians(angle - 90)

        base_x1 = self.center_x + base_width * math.cos(base_rad1)
        base_y1 = self.center_y - base_width * math.sin(base_rad1)
        base_x2 = self.center_x + base_width * math.cos(base_rad2)
        base_y2 = self.center_y - base_width * math.sin(base_rad2)

        needle_class = "gauge-needle" if animate else ""

        return f'''
  <polygon points="{tip_x},{tip_y} {base_x1},{base_y1} {base_x2},{base_y2}"
           fill="{color}" class="{needle_class}" filter="url(#gaugeShadow)"/>
'''

    def _create_tick_marks(self, color: str) -> str:
        """Create tick marks around the gauge."""
        ticks = []
        for i in range(11):  # 0%, 10%, 20%, ... 100%
            angle = 180 - (i * 18)  # 18 degrees per 10%
            rad = math.radians(angle)

            # Outer tick position
            outer_x = self.center_x + (self.radius + 5) * math.cos(rad)
            outer_y = self.center_y - (self.radius + 5) * math.sin(rad)

            # Inner tick position
            tick_length = 15 if i % 5 == 0 else 8
            inner_x = self.center_x + (self.radius + 5 + tick_length) * math.cos(rad)
            inner_y = self.center_y - (self.radius + 5 + tick_length) * math.sin(rad)

            stroke_width = 3 if i % 5 == 0 else 1.5
            ticks.append(f'''  <line x1="{outer_x}" y1="{outer_y}" x2="{inner_x}" y2="{inner_y}"
         stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round"/>''')

        return '\n'.join(ticks)

    def _create_labels(
        self,
        current: float,
        savings: float,
        optimized: float,
        primary_color: str,
        accent_color: str
    ) -> str:
        """Create value labels on the gauge."""
        return f'''
  <!-- Current Tax Label -->
  <text x="{self.center_x}" y="{self.center_y + 60}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="14" fill="#6b7280">
    Current Tax
  </text>
  <text x="{self.center_x}" y="{self.center_y + 85}" text-anchor="middle"
        font-family="Inter, Arial, sans-serif" font-size="24" font-weight="bold" fill="{primary_color}">
    ${current:,.0f}
  </text>

  <!-- Potential Savings Label (left side) -->
  <text x="40" y="{self.center_y - 20}" text-anchor="start"
        font-family="Inter, Arial, sans-serif" font-size="12" fill="#6b7280">
    Potential Savings
  </text>
  <text x="40" y="{self.center_y + 5}" text-anchor="start"
        font-family="Inter, Arial, sans-serif" font-size="20" font-weight="bold" fill="{accent_color}">
    ${savings:,.0f}
  </text>

  <!-- Optimized Tax Label (right side) -->
  <text x="{self.width - 40}" y="{self.center_y - 20}" text-anchor="end"
        font-family="Inter, Arial, sans-serif" font-size="12" fill="#6b7280">
    Optimized Tax
  </text>
  <text x="{self.width - 40}" y="{self.center_y + 5}" text-anchor="end"
        font-family="Inter, Arial, sans-serif" font-size="20" font-weight="bold" fill="{primary_color}">
    ${optimized:,.0f}
  </text>
'''

    def _create_legend(self, savings_color: str, liability_color: str) -> str:
        """Create legend for the gauge."""
        return f'''
  <!-- Legend -->
  <g transform="translate(120, 230)">
    <rect x="0" y="0" width="12" height="12" fill="{savings_color}" rx="2"/>
    <text x="18" y="10" font-family="Inter, Arial, sans-serif" font-size="11" fill="#6b7280">Savings Zone</text>

    <rect x="100" y="0" width="12" height="12" fill="{liability_color}" rx="2"/>
    <text x="118" y="10" font-family="Inter, Arial, sans-serif" font-size="11" fill="#6b7280">Current Liability</text>
  </g>
'''

    def render_mini(
        self,
        savings_percentage: float,
        theme: Optional["BrandTheme"] = None,
    ) -> str:
        """
        Render a mini gauge for compact displays.

        Args:
            savings_percentage: Savings as percentage (0-1)
            theme: Brand theme for colors

        Returns:
            SVG string for mini gauge
        """
        accent_color = theme.accent_color if theme else "#10b981"
        danger_color = theme.danger_color if theme else "#ef4444"

        percentage = min(1.0, max(0.0, savings_percentage))
        circumference = 2 * math.pi * 40
        savings_dash = circumference * percentage * 0.5  # Semi-circle

        return f'''<svg viewBox="0 0 100 60" xmlns="http://www.w3.org/2000/svg" class="mini-gauge">
  <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#e5e7eb" stroke-width="8" stroke-linecap="round"/>
  <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="{accent_color}" stroke-width="8"
        stroke-linecap="round" stroke-dasharray="{savings_dash} {circumference}"/>
  <text x="50" y="45" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="14" font-weight="bold" fill="{accent_color}">
    {percentage * 100:.0f}%
  </text>
  <text x="50" y="58" text-anchor="middle" font-family="Inter, Arial, sans-serif"
        font-size="8" fill="#6b7280">
    Savings
  </text>
</svg>'''
