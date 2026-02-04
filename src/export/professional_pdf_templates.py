"""
Professional PDF Templates with Charts and Visualizations.

Creates client-ready PDF reports with:
- Executive summary page
- Visual tax bracket positioning
- Savings opportunity charts
- Professional branding
- One-page summary option

Resolves Gap #3: Client PDF Polish
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import base64
import io

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from recommendation.recommendation_engine import ComprehensiveRecommendation


# ============================================================================
# Professional Color Scheme (matches web UI)
# ============================================================================

COLORS = {
    "primary": "#1e3a5f",
    "success": "#059669",
    "warning": "#d97706",
    "danger": "#dc2626",
    "gray_50": "#f9fafb",
    "gray_100": "#f3f4f6",
    "gray_700": "#374151",
    "gray_900": "#111827",
}


# ============================================================================
# Chart Generation (using matplotlib)
# ============================================================================

def generate_tax_bracket_chart(
    taxable_income: float,
    filing_status: str,
    total_tax: float
) -> str:
    """
    Generate tax bracket visualization showing taxpayer's position.

    Returns base64-encoded PNG image.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from io import BytesIO

        # 2025 tax brackets (Single as example)
        brackets = [
            {"limit": 11925, "rate": 0.10, "label": "10%"},
            {"limit": 48475, "rate": 0.12, "label": "12%"},
            {"limit": 103350, "rate": 0.22, "label": "22%"},
            {"limit": 197300, "rate": 0.24, "label": "24%"},
            {"limit": 250525, "rate": 0.32, "label": "32%"},
            {"limit": 626350, "rate": 0.35, "label": "35%"},
        ]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Draw brackets as horizontal bars
        y_position = 0
        for i, bracket in enumerate(brackets):
            # Calculate width proportional to bracket size
            if i == 0:
                width = bracket["limit"]
            else:
                width = bracket["limit"] - brackets[i-1]["limit"]

            # Color based on whether taxpayer is in this bracket
            if taxable_income > (brackets[i-1]["limit"] if i > 0 else 0):
                color = COLORS["primary"]
                alpha = 0.7
            else:
                color = COLORS["gray_100"]
                alpha = 0.3

            # Draw bar
            rect = patches.Rectangle(
                (brackets[i-1]["limit"] if i > 0 else 0, y_position),
                width, 1,
                linewidth=2, edgecolor='white',
                facecolor=color, alpha=alpha
            )
            ax.add_patch(rect)

            # Add label
            mid_point = (brackets[i-1]["limit"] if i > 0 else 0) + (width / 2)
            ax.text(mid_point, y_position + 0.5, bracket["label"],
                   ha='center', va='center', fontsize=12, fontweight='bold')

        # Mark taxpayer's position
        if taxable_income <= brackets[-1]["limit"]:
            ax.plot([taxable_income, taxable_income], [0, 1],
                   color=COLORS["danger"], linewidth=3, linestyle='--')
            ax.text(taxable_income, 1.2, f"Your Position\n${taxable_income:,.0f}",
                   ha='center', fontsize=10, fontweight='bold',
                   color=COLORS["danger"])

        # Configure axes
        ax.set_xlim(0, brackets[-1]["limit"])
        ax.set_ylim(-0.2, 1.5)
        ax.set_xlabel("Taxable Income ($)", fontsize=12, fontweight='bold')
        ax.set_title("Your Tax Bracket Position", fontsize=14, fontweight='bold', pad=20)
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        # Format x-axis
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))

        plt.tight_layout()

        # Convert to base64
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return f"data:image/png;base64,{image_base64}"

    except ImportError:
        # Fallback if matplotlib not available
        return ""


def generate_savings_opportunity_chart(opportunities: List[Dict[str, Any]]) -> str:
    """
    Generate horizontal bar chart of top savings opportunities.

    Returns base64-encoded PNG image.
    """
    try:
        import matplotlib.pyplot as plt
        from io import BytesIO

        # Take top 5 opportunities
        top_opps = sorted(opportunities, key=lambda x: x.get("estimated_savings", 0), reverse=True)[:5]

        if not top_opps:
            return ""

        # Extract data
        labels = [opp.get("title", "Unknown")[:30] for opp in top_opps]
        values = [opp.get("estimated_savings", 0) for opp in top_opps]

        # Create horizontal bar chart
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bars
        bars = ax.barh(labels, values, color=COLORS["success"], alpha=0.7)

        # Add value labels
        for i, (bar, value) in enumerate(zip(bars, values)):
            ax.text(value, i, f'  ${value:,.0f}',
                   va='center', fontsize=11, fontweight='bold')

        # Configure axes
        ax.set_xlabel("Potential Savings ($)", fontsize=12, fontweight='bold')
        ax.set_title("Top Tax Savings Opportunities", fontsize=14, fontweight='bold', pad=20)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Format x-axis
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))

        plt.tight_layout()

        # Convert to base64
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return f"data:image/png;base64,{image_base64}"

    except ImportError:
        return ""


def generate_income_breakdown_pie_chart(income_sources: Dict[str, float]) -> str:
    """
    Generate pie chart of income sources.

    Returns base64-encoded PNG image.
    """
    try:
        import matplotlib.pyplot as plt
        from io import BytesIO

        # Filter out zero values
        income_sources = {k: v for k, v in income_sources.items() if v > 0}

        if not income_sources:
            return ""

        # Create pie chart
        fig, ax = plt.subplots(figsize=(8, 8))

        labels = list(income_sources.keys())
        values = list(income_sources.values())

        # Custom colors
        colors = ['#1e3a5f', '#059669', '#d97706', '#dc2626', '#5387c1', '#7ea5d1']

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct='%1.1f%%',
            colors=colors[:len(values)], startangle=90,
            textprops={'fontsize': 11, 'fontweight': 'bold'}
        )

        # Make percentage text white
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax.set_title("Income Sources Breakdown", fontsize=14, fontweight='bold', pad=20)

        plt.tight_layout()

        # Convert to base64
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return f"data:image/png;base64,{image_base64}"

    except ImportError:
        return ""


# ============================================================================
# HTML Template for PDF Generation
# ============================================================================

def generate_executive_summary_html(
    tax_return: "TaxReturn",
    recommendation: Optional["ComprehensiveRecommendation"] = None
) -> str:
    """
    Generate executive summary page HTML.

    This is the first page clients see - make it count!
    """
    taxpayer_name = f"{tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}"
    filing_status = tax_return.taxpayer.filing_status.value.replace('_', ' ').title()

    # Calculate key metrics
    total_income = tax_return.income.get_total_income() if hasattr(tax_return.income, 'get_total_income') else 0
    total_tax = getattr(tax_return, 'total_tax', 0) or 0
    effective_rate = (total_tax / total_income * 100) if total_income > 0 else 0

    refund_or_owe = "REFUND" if total_tax < 0 else "AMOUNT OWED"
    amount_color = COLORS["success"] if total_tax < 0 else COLORS["danger"]

    # Get savings opportunities
    total_savings = 0
    top_opportunities_html = ""
    if recommendation:
        total_savings = getattr(recommendation, 'total_potential_savings', 0) or 0

        top_opps = getattr(recommendation, 'top_opportunities', [])[:3]
        for opp in top_opps:
            top_opportunities_html += f"""
            <div style="padding: 12px; background: {COLORS['gray_50']}; border-radius: 8px; margin-bottom: 8px;">
                <div style="font-weight: 600; color: {COLORS['gray_900']};">{getattr(opp, 'title', 'Opportunity')}</div>
                <div style="color: {COLORS['success']}; font-weight: 700; font-size: 18px;">
                    Save ${getattr(opp, 'estimated_savings', 0):,.0f}
                </div>
                <div style="color: {COLORS['gray_700']}; font-size: 14px; margin-top: 4px;">
                    {getattr(opp, 'description', '')[:100]}...
                </div>
            </div>
            """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: letter;
                margin: 0.5in;
            }}
            body {{
                font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
                color: {COLORS['gray_900']};
                line-height: 1.6;
            }}
            .header {{
                background: linear-gradient(135deg, {COLORS['primary']} 0%, #152b47 100%);
                color: white;
                padding: 40px;
                border-radius: 12px;
                margin-bottom: 30px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 10px;
            }}
            .client-name {{
                font-size: 32px;
                font-weight: 700;
                margin-bottom: 5px;
            }}
            .subtitle {{
                font-size: 16px;
                opacity: 0.9;
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 20px;
                margin-bottom: 30px;
            }}
            .metric-card {{
                background: white;
                border: 2px solid {COLORS['gray_100']};
                border-radius: 12px;
                padding: 24px;
                text-align: center;
            }}
            .metric-label {{
                font-size: 14px;
                color: {COLORS['gray_700']};
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-weight: 600;
            }}
            .metric-value {{
                font-size: 36px;
                font-weight: 700;
                color: {COLORS['gray_900']};
            }}
            .metric-value.refund {{
                color: {COLORS['success']};
            }}
            .metric-value.owe {{
                color: {COLORS['danger']};
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section-title {{
                font-size: 20px;
                font-weight: 700;
                margin-bottom: 16px;
                color: {COLORS['gray_900']};
                padding-bottom: 8px;
                border-bottom: 3px solid {COLORS['primary']};
            }}
            .savings-highlight {{
                background: {COLORS['success']};
                color: white;
                padding: 24px;
                border-radius: 12px;
                margin-bottom: 20px;
                text-align: center;
            }}
            .savings-amount {{
                font-size: 48px;
                font-weight: 700;
                margin: 10px 0;
            }}
            .footer {{
                margin-top: 50px;
                padding-top: 20px;
                border-top: 2px solid {COLORS['gray_100']};
                font-size: 12px;
                color: {COLORS['gray_700']};
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <!-- Header -->
        <div class="header">
            <div class="logo">🎯 Tax Decision Intelligence Platform</div>
            <div class="client-name">{taxpayer_name}</div>
            <div class="subtitle">Tax Year 2025 | {filing_status}</div>
        </div>

        <!-- Key Metrics -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total Income</div>
                <div class="metric-value">${total_income:,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">{refund_or_owe}</div>
                <div class="metric-value {'refund' if total_tax < 0 else 'owe'}">${abs(total_tax):,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Effective Rate</div>
                <div class="metric-value">{effective_rate:.1f}%</div>
            </div>
        </div>

        <!-- Savings Opportunities -->
        {f'''
        <div class="savings-highlight">
            <div style="font-size: 18px; font-weight: 600;">💰 Total Identified Savings</div>
            <div class="savings-amount">${total_savings:,.0f}</div>
            <div>in tax reduction opportunities discovered</div>
        </div>

        <div class="section">
            <div class="section-title">Top 3 Opportunities</div>
            {top_opportunities_html}
        </div>
        ''' if total_savings > 0 else ''}

        <!-- Executive Summary -->
        <div class="section">
            <div class="section-title">Executive Summary</div>
            <div style="padding: 20px; background: {COLORS['gray_50']}; border-radius: 8px; line-height: 1.8;">
                <p>This comprehensive tax analysis for <strong>{taxpayer_name}</strong> identifies opportunities to optimize your tax position for 2025.</p>

                <p>Based on your total income of <strong>${total_income:,.0f}</strong> and filing status of <strong>{filing_status}</strong>, we've analyzed multiple tax strategies across income optimization, deduction planning, and credit utilization.</p>

                {f'<p>Our analysis identified <strong>${total_savings:,.0f}</strong> in potential tax savings through strategic planning and optimization of your tax position.</p>' if total_savings > 0 else ''}

                <p>This report includes detailed scenario analysis, recommendations with IRS references, and actionable next steps.</p>
            </div>
        </div>

        <!-- Table of Contents -->
        <div class="section">
            <div class="section-title">Report Contents</div>
            <div style="padding: 20px;">
                <ol style="line-height: 2.0;">
                    <li><strong>Tax Summary</strong> - Complete breakdown of income, deductions, and credits</li>
                    <li><strong>Scenario Analysis</strong> - What-if comparisons and alternative strategies</li>
                    <li><strong>Recommendations</strong> - Prioritized tax optimization opportunities</li>
                    <li><strong>Supporting Documents</strong> - Form 1040 and required schedules</li>
                    <li><strong>Action Plan</strong> - Timeline and next steps</li>
                </ol>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <div>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
            <div>Powered by Tax Decision Intelligence Platform | Tax Year 2025</div>
            <div style="margin-top: 10px; font-style: italic;">
                This report provides tax planning insights based on the information provided.
                Consult with a licensed tax professional before making decisions.
            </div>
        </div>
    </body>
    </html>
    """

    return html


def generate_one_page_summary_html(
    tax_return: "TaxReturn",
    recommendation: Optional["ComprehensiveRecommendation"] = None
) -> str:
    """
    Generate one-page summary for quick review.

    Perfect for clients who want the highlights.
    """
    taxpayer_name = f"{tax_return.taxpayer.first_name} {tax_return.taxpayer.last_name}"

    total_income = tax_return.income.get_total_income() if hasattr(tax_return.income, 'get_total_income') else 0
    total_tax = getattr(tax_return, 'total_tax', 0) or 0

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: letter; margin: 0.25in; }}
            body {{
                font-family: 'Inter', Arial, sans-serif;
                font-size: 11px;
                line-height: 1.4;
            }}
            .container {{
                border: 3px solid {COLORS['primary']};
                padding: 20px;
                height: 100%;
            }}
            h1 {{
                color: {COLORS['primary']};
                font-size: 22px;
                margin-bottom: 5px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin: 15px 0;
            }}
            .box {{
                background: {COLORS['gray_50']};
                padding: 10px;
                border-radius: 6px;
                text-align: center;
            }}
            .box-label {{ font-size: 9px; text-transform: uppercase; color: {COLORS['gray_700']}; }}
            .box-value {{ font-size: 20px; font-weight: 700; color: {COLORS['gray_900']}; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 10px 0;
                font-size: 10px;
            }}
            td, th {{
                padding: 4px;
                border-bottom: 1px solid {COLORS['gray_100']};
            }}
            th {{ font-weight: 700; background: {COLORS['gray_50']}; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 {taxpayer_name} - 2025 Tax Summary</h1>
            <p style="color: {COLORS['gray_700']};">One-Page Executive Overview | {datetime.now().strftime('%B %d, %Y')}</p>

            <div class="grid">
                <div class="box">
                    <div class="box-label">Total Income</div>
                    <div class="box-value">${total_income:,.0f}</div>
                </div>
                <div class="box">
                    <div class="box-label">Total Tax</div>
                    <div class="box-value">${total_tax:,.0f}</div>
                </div>
                <div class="box">
                    <div class="box-label">Effective Rate</div>
                    <div class="box-value">{(total_tax/total_income*100):.1f}%</div>
                </div>
                <div class="box" style="background: {COLORS['success']}; color: white;">
                    <div class="box-label" style="color: white; opacity: 0.9;">Potential Savings</div>
                    <div class="box-value" style="color: white;">
                        ${getattr(recommendation, 'total_potential_savings', 0):,.0f}
                    </div>
                </div>
            </div>

            <table>
                <tr>
                    <th colspan="2">Income Breakdown</th>
                </tr>
                <tr><td>W-2 Wages</td><td style="text-align: right;">${sum(w2.wages for w2 in tax_return.income.w2_forms):,.0f}</td></tr>
                <tr><td>Interest & Dividends</td><td style="text-align: right;">$0</td></tr>
                <tr><td>Capital Gains</td><td style="text-align: right;">$0</td></tr>
            </table>

            <table>
                <tr>
                    <th colspan="2">Top Recommendations</th>
                </tr>
                {(''.join([
                    f'<tr><td>{getattr(opp, "title", "")}</td><td style="text-align: right; color: {COLORS["success"]}; font-weight: 700;">${getattr(opp, "estimated_savings", 0):,.0f}</td></tr>'
                    for opp in getattr(recommendation, 'top_opportunities', [])[:5]
                ]) if recommendation else '')}
            </table>

            <div style="margin-top: 20px; padding: 10px; background: {COLORS['primary']}; color: white; border-radius: 6px; text-align: center;">
                <strong>Next Steps:</strong> Review full report for detailed analysis and implementation timeline
            </div>
        </div>
    </body>
    </html>
    """

    return html


@dataclass
class ProfessionalPDFReport:
    """
    Container for a professional PDF report with all components.
    """
    executive_summary_html: str
    one_page_summary_html: str
    tax_bracket_chart: str  # base64 image
    savings_chart: str  # base64 image
    income_chart: str  # base64 image
    full_report_html: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


def generate_professional_pdf_report(
    tax_return: "TaxReturn",
    recommendation: Optional["ComprehensiveRecommendation"] = None,
    include_charts: bool = True
) -> ProfessionalPDFReport:
    """
    Generate complete professional PDF report with all components.

    Args:
        tax_return: The tax return to generate report for
        recommendation: Optional recommendations from advisory system
        include_charts: Whether to generate charts (requires matplotlib)

    Returns:
        ProfessionalPDFReport with all components ready for PDF generation
    """
    # Generate HTML components
    executive_summary = generate_executive_summary_html(tax_return, recommendation)
    one_page_summary = generate_one_page_summary_html(tax_return, recommendation)

    # Generate charts if requested
    tax_bracket_chart = ""
    savings_chart = ""
    income_chart = ""

    if include_charts:
        taxable_income = getattr(tax_return, 'taxable_income', 0) or 0
        total_tax = getattr(tax_return, 'total_tax', 0) or 0
        filing_status = tax_return.taxpayer.filing_status.value

        tax_bracket_chart = generate_tax_bracket_chart(
            taxable_income, filing_status, total_tax
        )

        if recommendation:
            top_opps = getattr(recommendation, 'top_opportunities', [])
            opportunities_data = [
                {
                    "title": getattr(opp, 'title', ''),
                    "estimated_savings": getattr(opp, 'estimated_savings', 0)
                }
                for opp in top_opps
            ]
            savings_chart = generate_savings_opportunity_chart(opportunities_data)

        # Income breakdown
        income_sources = {
            "W-2 Wages": sum(w2.wages for w2 in tax_return.income.w2_forms),
            "Interest": getattr(tax_return.income, 'interest_income', 0) or 0,
            "Dividends": getattr(tax_return.income, 'dividend_income', 0) or 0,
            "Capital Gains": getattr(tax_return.income, 'capital_gain_income', 0) or 0,
        }
        income_chart = generate_income_breakdown_pie_chart(income_sources)

    # Combine everything into full report
    full_report = f"""
    {executive_summary}
    <div style="page-break-after: always;"></div>

    {one_page_summary}
    <div style="page-break-after: always;"></div>

    <!-- Charts and visualizations would follow -->
    """

    return ProfessionalPDFReport(
        executive_summary_html=executive_summary,
        one_page_summary_html=one_page_summary,
        tax_bracket_chart=tax_bracket_chart,
        savings_chart=savings_chart,
        income_chart=income_chart,
        full_report_html=full_report
    )
