"""
PDF Visualization Module - Integrates Universal Report visualizations into PDFs.

This module provides:
- Matplotlib-based chart generation for PDFs
- SVG to PNG conversion for ReportLab embedding
- Savings gauge visualization
- Income/deduction pie charts
- Tax bracket bar charts
- Comparison charts

Usage:
    from export.pdf_visualizations import PDFChartGenerator

    generator = PDFChartGenerator()

    # Generate savings gauge
    gauge_image = generator.create_savings_gauge(
        current_tax=25000,
        potential_savings=5000
    )

    # Generate income pie chart
    pie_image = generator.create_income_pie_chart(income_items)
"""

from __future__ import annotations

import io
import base64
import logging
from typing import List, Optional, Dict, Any, Tuple, TYPE_CHECKING
from decimal import Decimal

logger = logging.getLogger(__name__)

# Check for matplotlib availability
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend for server-side rendering
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.patches import FancyBboxPatch, Circle, Wedge
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib not available - PDF charts will be disabled")

# Check for ReportLab availability
try:
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.units import inch
    from reportlab.platypus import Image as RLImage
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available - PDF image embedding will be disabled")


# Color scheme matching Universal Report theme
COLORS = {
    'primary': '#1a365d',
    'primary_light': '#2c5282',
    'accent': '#2563eb',
    'success': '#10b981',
    'success_dark': '#059669',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'gray_100': '#f3f4f6',
    'gray_200': '#e5e7eb',
    'gray_300': '#d1d5db',
    'gray_500': '#6b7280',
    'gray_700': '#374151',
    'gray_800': '#1f2937',
    'white': '#ffffff',
}

# Tax bracket colors (gradient from low to high rates)
BRACKET_COLORS = [
    '#10b981',  # 10% - green
    '#34d399',  # 12% - light green
    '#fbbf24',  # 22% - yellow
    '#f59e0b',  # 24% - amber
    '#f97316',  # 32% - orange
    '#ef4444',  # 35% - red
    '#dc2626',  # 37% - dark red
]

# Income category colors
INCOME_COLORS = [
    '#2563eb',  # Blue - W-2
    '#7c3aed',  # Purple - Business
    '#10b981',  # Green - Investment
    '#f59e0b',  # Amber - Rental
    '#ef4444',  # Red - Capital Gains
    '#6366f1',  # Indigo - Other
]


class PDFChartGenerator:
    """
    Generate charts and visualizations for PDF reports.

    Uses Matplotlib to create high-quality charts that can be
    embedded in ReportLab PDFs.
    """

    def __init__(self, dpi: int = 150):
        """
        Initialize the chart generator.

        Args:
            dpi: Resolution for generated images (higher = better quality, larger files)
        """
        self.dpi = dpi

        if MATPLOTLIB_AVAILABLE:
            # Set consistent styling
            plt.style.use('seaborn-v0_8-whitegrid')
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
            plt.rcParams['axes.titlesize'] = 14
            plt.rcParams['axes.labelsize'] = 11
            plt.rcParams['xtick.labelsize'] = 10
            plt.rcParams['ytick.labelsize'] = 10

    def create_savings_gauge(
        self,
        current_tax: float,
        potential_savings: float,
        width: float = 5,
        height: float = 3,
    ) -> Optional[io.BytesIO]:
        """
        Create a semi-circular savings gauge visualization.

        Args:
            current_tax: Current tax liability
            potential_savings: Potential tax savings
            width: Image width in inches
            height: Image height in inches

        Returns:
            BytesIO buffer containing PNG image, or None if matplotlib unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, ax = plt.subplots(figsize=(width, height))
            ax.set_xlim(-1.2, 1.2)
            ax.set_ylim(-0.2, 1.1)
            ax.set_aspect('equal')
            ax.axis('off')

            # Calculate savings percentage
            if current_tax > 0:
                savings_pct = min((potential_savings / current_tax) * 100, 100)
            else:
                savings_pct = 0

            # Draw background arc (gray)
            theta1, theta2 = 180, 0
            arc_bg = Wedge(
                (0, 0), 1, theta1, theta2,
                width=0.3,
                facecolor=COLORS['gray_200'],
                edgecolor='none'
            )
            ax.add_patch(arc_bg)

            # Draw savings arc (green gradient)
            savings_angle = 180 - (savings_pct * 1.8)
            arc_savings = Wedge(
                (0, 0), 1, 180, savings_angle,
                width=0.3,
                facecolor=COLORS['success'],
                edgecolor='none',
                alpha=0.9
            )
            ax.add_patch(arc_savings)

            # Draw needle
            needle_angle = np.radians(180 - (savings_pct * 1.8))
            needle_x = 0.7 * np.cos(needle_angle)
            needle_y = 0.7 * np.sin(needle_angle)

            ax.plot([0, needle_x], [0, needle_y],
                   color=COLORS['primary'], linewidth=3,
                   solid_capstyle='round', zorder=10)

            # Center circle
            center = Circle((0, 0), 0.1, facecolor=COLORS['primary'],
                          edgecolor='white', linewidth=2, zorder=11)
            ax.add_patch(center)

            # Add labels
            ax.text(-1.1, -0.15, '$0', fontsize=10, ha='center',
                   color=COLORS['gray_500'])
            ax.text(1.1, -0.15, f'${current_tax:,.0f}', fontsize=10,
                   ha='center', color=COLORS['gray_500'])

            # Savings amount in center
            ax.text(0, 0.5, f'${potential_savings:,.0f}', fontsize=20,
                   fontweight='bold', ha='center', va='center',
                   color=COLORS['success'])
            ax.text(0, 0.3, 'Potential Savings', fontsize=10,
                   ha='center', va='center', color=COLORS['gray_500'])

            # Percentage badge
            ax.text(0, 0.85, f'{savings_pct:.0f}%', fontsize=14,
                   fontweight='bold', ha='center', va='center',
                   color=COLORS['success'],
                   bbox=dict(boxstyle='round,pad=0.3',
                            facecolor=COLORS['gray_100'],
                            edgecolor=COLORS['success']))

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi,
                       bbox_inches='tight', facecolor='white',
                       edgecolor='none')
            plt.close(fig)
            buf.seek(0)

            return buf

        except Exception as e:
            logger.error(f"Error creating savings gauge: {e}")
            plt.close('all')
            return None

    def create_income_pie_chart(
        self,
        income_items: List[Dict[str, Any]],
        width: float = 5,
        height: float = 4,
        title: str = "Income Breakdown"
    ) -> Optional[io.BytesIO]:
        """
        Create a donut chart showing income breakdown by category.

        Args:
            income_items: List of income items with 'category' and 'amount' keys
            width: Image width in inches
            height: Image height in inches
            title: Chart title

        Returns:
            BytesIO buffer containing PNG image
        """
        if not MATPLOTLIB_AVAILABLE or not income_items:
            return None

        try:
            # Aggregate by category
            categories = {}
            for item in income_items:
                cat = item.get('category', 'Other')
                amount = float(item.get('amount', 0))
                if amount > 0:
                    categories[cat] = categories.get(cat, 0) + amount

            if not categories:
                return None

            fig, ax = plt.subplots(figsize=(width, height))

            labels = list(categories.keys())
            values = list(categories.values())
            total = sum(values)

            # Calculate percentages
            percentages = [(v / total) * 100 for v in values]

            # Create donut chart
            colors = INCOME_COLORS[:len(labels)]
            wedges, texts, autotexts = ax.pie(
                values,
                labels=None,
                colors=colors,
                autopct=lambda pct: f'{pct:.1f}%' if pct > 5 else '',
                pctdistance=0.75,
                startangle=90,
                wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2)
            )

            # Style percentage text
            for autotext in autotexts:
                autotext.set_fontsize(10)
                autotext.set_fontweight('bold')
                autotext.set_color('white')

            # Add center text
            ax.text(0, 0.05, f'${total:,.0f}', fontsize=16, fontweight='bold',
                   ha='center', va='center', color=COLORS['gray_800'])
            ax.text(0, -0.15, 'Total Income', fontsize=9, ha='center',
                   va='center', color=COLORS['gray_500'])

            # Add legend
            legend_labels = [f'{label}: ${value:,.0f}'
                          for label, value in zip(labels, values)]
            ax.legend(wedges, legend_labels, loc='center left',
                     bbox_to_anchor=(1, 0.5), fontsize=9)

            ax.set_title(title, fontsize=14, fontweight='bold',
                        color=COLORS['gray_800'], pad=10)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi,
                       bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)

            return buf

        except Exception as e:
            logger.error(f"Error creating income pie chart: {e}")
            plt.close('all')
            return None

    def create_tax_bracket_chart(
        self,
        taxable_income: float,
        filing_status: str = 'single',
        width: float = 6,
        height: float = 3.5,
    ) -> Optional[io.BytesIO]:
        """
        Create a horizontal bar chart showing tax bracket breakdown.

        Args:
            taxable_income: Taxable income amount
            filing_status: Filing status for bracket determination
            width: Image width in inches
            height: Image height in inches

        Returns:
            BytesIO buffer containing PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            # 2025 tax brackets
            brackets = self._get_tax_brackets(filing_status)

            # Calculate amount in each bracket
            bracket_data = []
            remaining = taxable_income

            for i, (start, end, rate) in enumerate(brackets):
                if remaining <= 0:
                    break

                bracket_size = end - start if end != float('inf') else remaining
                amount_in_bracket = min(remaining, bracket_size)
                tax_from_bracket = amount_in_bracket * rate

                if amount_in_bracket > 0:
                    bracket_data.append({
                        'rate': f'{int(rate * 100)}%',
                        'amount': amount_in_bracket,
                        'tax': tax_from_bracket,
                        'color': BRACKET_COLORS[min(i, len(BRACKET_COLORS) - 1)]
                    })

                remaining -= amount_in_bracket

            if not bracket_data:
                return None

            fig, ax = plt.subplots(figsize=(width, height))

            rates = [b['rate'] for b in bracket_data]
            amounts = [b['amount'] for b in bracket_data]
            colors = [b['color'] for b in bracket_data]

            y_pos = np.arange(len(rates))
            bars = ax.barh(y_pos, amounts, color=colors, edgecolor='white',
                          linewidth=1, height=0.6)

            # Add amount labels
            for i, (bar, data) in enumerate(zip(bars, bracket_data)):
                width = bar.get_width()
                ax.text(width + taxable_income * 0.02, bar.get_y() + bar.get_height()/2,
                       f'${data["amount"]:,.0f}',
                       va='center', fontsize=9, color=COLORS['gray_700'])

                # Tax amount inside bar (if bar is wide enough)
                if width > taxable_income * 0.15:
                    ax.text(width / 2, bar.get_y() + bar.get_height()/2,
                           f'Tax: ${data["tax"]:,.0f}',
                           va='center', ha='center', fontsize=8,
                           color='white', fontweight='bold')

            ax.set_yticks(y_pos)
            ax.set_yticklabels(rates)
            ax.set_xlabel('Amount in Bracket ($)')
            ax.set_title('Tax Bracket Breakdown', fontsize=14, fontweight='bold',
                        color=COLORS['gray_800'])

            # Format x-axis
            ax.xaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K' if x >= 1000 else f'${x:.0f}')
            )

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi,
                       bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)

            return buf

        except Exception as e:
            logger.error(f"Error creating tax bracket chart: {e}")
            plt.close('all')
            return None

    def create_comparison_chart(
        self,
        current_scenario: Dict[str, float],
        optimized_scenario: Dict[str, float],
        width: float = 6,
        height: float = 4,
    ) -> Optional[io.BytesIO]:
        """
        Create a grouped bar chart comparing current vs optimized tax scenarios.

        Args:
            current_scenario: Dict with tax values for current scenario
            optimized_scenario: Dict with tax values for optimized scenario
            width: Image width in inches
            height: Image height in inches

        Returns:
            BytesIO buffer containing PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, ax = plt.subplots(figsize=(width, height))

            categories = ['Federal Tax', 'State Tax', 'Total Tax']
            current_values = [
                current_scenario.get('federal_tax', 0),
                current_scenario.get('state_tax', 0),
                current_scenario.get('total_tax', 0),
            ]
            optimized_values = [
                optimized_scenario.get('federal_tax', 0),
                optimized_scenario.get('state_tax', 0),
                optimized_scenario.get('total_tax', 0),
            ]

            x = np.arange(len(categories))
            bar_width = 0.35

            bars1 = ax.bar(x - bar_width/2, current_values, bar_width,
                          label='Current', color=COLORS['gray_500'],
                          edgecolor='white', linewidth=1)
            bars2 = ax.bar(x + bar_width/2, optimized_values, bar_width,
                          label='Optimized', color=COLORS['success'],
                          edgecolor='white', linewidth=1)

            # Add value labels
            def add_labels(bars, values):
                for bar, val in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, height + 500,
                           f'${val:,.0f}', ha='center', va='bottom',
                           fontsize=9, fontweight='bold')

            add_labels(bars1, current_values)
            add_labels(bars2, optimized_values)

            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.set_ylabel('Amount ($)')
            ax.set_title('Current vs Optimized Tax Comparison',
                        fontsize=14, fontweight='bold', color=COLORS['gray_800'])
            ax.legend(loc='upper right')

            # Format y-axis
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K' if x >= 1000 else f'${x:.0f}')
            )

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Add savings annotation
            savings = current_scenario.get('total_tax', 0) - optimized_scenario.get('total_tax', 0)
            if savings > 0:
                ax.annotate(
                    f'Save ${savings:,.0f}',
                    xy=(2 + bar_width/2, optimized_values[2]),
                    xytext=(2.5, (current_values[2] + optimized_values[2]) / 2),
                    fontsize=12, fontweight='bold', color=COLORS['success'],
                    arrowprops=dict(arrowstyle='->', color=COLORS['success'])
                )

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi,
                       bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)

            return buf

        except Exception as e:
            logger.error(f"Error creating comparison chart: {e}")
            plt.close('all')
            return None

    def create_deduction_comparison(
        self,
        standard_deduction: float,
        itemized_deduction: float,
        selected_type: str = 'standard',
        width: float = 5,
        height: float = 3,
    ) -> Optional[io.BytesIO]:
        """
        Create a bar chart comparing standard vs itemized deductions.

        Args:
            standard_deduction: Standard deduction amount
            itemized_deduction: Total itemized deductions
            selected_type: Which deduction type was selected
            width: Image width in inches
            height: Image height in inches

        Returns:
            BytesIO buffer containing PNG image
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, ax = plt.subplots(figsize=(width, height))

            categories = ['Standard\nDeduction', 'Itemized\nDeductions']
            values = [standard_deduction, itemized_deduction]

            # Color based on selection
            colors = []
            for i, cat in enumerate(['standard', 'itemized']):
                if cat == selected_type:
                    colors.append(COLORS['success'])
                else:
                    colors.append(COLORS['gray_300'])

            bars = ax.bar(categories, values, color=colors, edgecolor='white',
                         linewidth=2, width=0.6)

            # Add value labels
            for bar, val in zip(bars, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, height + 500,
                       f'${val:,.0f}', ha='center', va='bottom',
                       fontsize=11, fontweight='bold', color=COLORS['gray_700'])

            # Add "Selected" badge
            selected_idx = 0 if selected_type == 'standard' else 1
            ax.text(selected_idx, values[selected_idx] * 0.5,
                   '✓ SELECTED', ha='center', va='center',
                   fontsize=9, fontweight='bold', color='white',
                   bbox=dict(boxstyle='round,pad=0.3',
                            facecolor=COLORS['success_dark'], alpha=0.9))

            ax.set_ylabel('Deduction Amount ($)')
            ax.set_title('Deduction Comparison', fontsize=14, fontweight='bold',
                        color=COLORS['gray_800'])

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # Format y-axis
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K' if x >= 1000 else f'${x:.0f}')
            )

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=self.dpi,
                       bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)

            return buf

        except Exception as e:
            logger.error(f"Error creating deduction comparison: {e}")
            plt.close('all')
            return None

    def _get_tax_brackets(self, filing_status: str) -> List[Tuple[float, float, float]]:
        """Get 2025 tax brackets for given filing status."""
        # 2025 brackets (start, end, rate)
        brackets = {
            'single': [
                (0, 11925, 0.10),
                (11925, 48475, 0.12),
                (48475, 103350, 0.22),
                (103350, 197300, 0.24),
                (197300, 250525, 0.32),
                (250525, 626350, 0.35),
                (626350, float('inf'), 0.37),
            ],
            'married_joint': [
                (0, 23850, 0.10),
                (23850, 96950, 0.12),
                (96950, 206700, 0.22),
                (206700, 394600, 0.24),
                (394600, 501050, 0.32),
                (501050, 751600, 0.35),
                (751600, float('inf'), 0.37),
            ],
            'married_separate': [
                (0, 11925, 0.10),
                (11925, 48475, 0.12),
                (48475, 103350, 0.22),
                (103350, 197300, 0.24),
                (197300, 250525, 0.32),
                (250525, 375800, 0.35),
                (375800, float('inf'), 0.37),
            ],
            'head_of_household': [
                (0, 17000, 0.10),
                (17000, 64850, 0.12),
                (64850, 103350, 0.22),
                (103350, 197300, 0.24),
                (197300, 250500, 0.32),
                (250500, 626350, 0.35),
                (626350, float('inf'), 0.37),
            ],
        }

        return brackets.get(filing_status, brackets['single'])

    def buffer_to_reportlab_image(
        self,
        buffer: io.BytesIO,
        width: float = 5,
        height: Optional[float] = None
    ):
        """
        Convert a BytesIO buffer to a ReportLab Image element.

        Args:
            buffer: BytesIO containing PNG image data
            width: Desired width in inches
            height: Desired height in inches (None for proportional)

        Returns:
            ReportLab Image object ready for embedding, or None
        """
        if not REPORTLAB_AVAILABLE or buffer is None:
            return None

        try:
            from reportlab.platypus import Image as RLImage
            from reportlab.lib.units import inch

            buffer.seek(0)
            img = RLImage(buffer, width=width*inch, height=height*inch if height else None)
            return img

        except Exception as e:
            logger.error(f"Error converting buffer to ReportLab image: {e}")
            return None


# Convenience functions for direct usage
def create_savings_gauge_for_pdf(current_tax: float, potential_savings: float):
    """Create a savings gauge image ready for PDF embedding."""
    generator = PDFChartGenerator()
    return generator.create_savings_gauge(current_tax, potential_savings)


def create_income_chart_for_pdf(income_items: List[Dict[str, Any]]):
    """Create an income pie chart ready for PDF embedding."""
    generator = PDFChartGenerator()
    return generator.create_income_pie_chart(income_items)


def create_bracket_chart_for_pdf(taxable_income: float, filing_status: str = 'single'):
    """Create a tax bracket chart ready for PDF embedding."""
    generator = PDFChartGenerator()
    return generator.create_tax_bracket_chart(taxable_income, filing_status)
