"""
Report Templates - Tiered Report Generation for Lead Magnet Flow

Tier 1 (FREE): Lead magnet teaser report with CPA branding
Tier 2 (Full): Complete report unlocked after engagement

Reports are generated as HTML for display and can be exported to PDF.
"""

from __future__ import annotations

import uuid
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import sqlite3

from .lead_magnet_service import (
    CPAProfile,
    TaxProfile,
    TaxInsight,
    LeadMagnetLead,
    TaxComplexity,
)
from ..disclaimers import PlatformDisclaimers, ClientFacingDisclaimers

logger = logging.getLogger(__name__)


# =============================================================================
# TIER 1 REPORT TEMPLATE (FREE - Lead Magnet)
# =============================================================================

TIER_1_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tax Advisory Report - {client_name}</title>
    <style>
        :root {{
            --primary: #1e40af;
            --primary-light: #dbeafe;
            --secondary: #059669;
            --secondary-light: #d1fae5;
            --accent: #f59e0b;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-500: #6b7280;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-900: #111827;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--gray-700);
            background: var(--gray-50);
        }}

        .report {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .cpa-logo {{
            width: 80px;
            height: 80px;
            background: white;
            border-radius: 12px;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            color: var(--primary);
        }}

        .cpa-name {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .cpa-firm {{
            font-size: 14px;
            opacity: 0.9;
        }}

        .report-title {{
            margin-top: 24px;
            font-size: 28px;
            font-weight: 300;
        }}

        .client-section {{
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 20px;
            margin-top: 24px;
        }}

        .client-name {{
            font-size: 20px;
            font-weight: 600;
        }}

        .client-detail {{
            font-size: 14px;
            opacity: 0.9;
        }}

        .summary {{
            padding: 40px;
            background: var(--gray-50);
            border-bottom: 1px solid var(--gray-200);
        }}

        .summary-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 16px;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}

        .summary-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}

        .summary-label {{
            font-size: 12px;
            color: var(--gray-500);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .summary-value {{
            font-size: 24px;
            font-weight: 700;
            color: var(--primary);
        }}

        .summary-value.savings {{
            color: var(--secondary);
        }}

        .insights {{
            padding: 40px;
        }}

        .insights-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 8px;
        }}

        .insights-subtitle {{
            font-size: 14px;
            color: var(--gray-500);
            margin-bottom: 24px;
        }}

        .insight-card {{
            background: var(--gray-50);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 16px;
            border-left: 4px solid var(--secondary);
        }}

        .insight-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .insight-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--gray-900);
        }}

        .insight-category {{
            font-size: 11px;
            background: var(--primary-light);
            color: var(--primary);
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 500;
            text-transform: uppercase;
        }}

        .insight-description {{
            font-size: 14px;
            color: var(--gray-600);
            margin-bottom: 12px;
        }}

        .insight-savings {{
            display: inline-block;
            background: var(--secondary-light);
            color: var(--secondary);
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 14px;
        }}

        .locked-insights {{
            background: linear-gradient(to bottom, var(--gray-100), var(--gray-200));
            border-radius: 12px;
            padding: 32px;
            text-align: center;
            margin-top: 24px;
        }}

        .locked-icon {{
            font-size: 48px;
            margin-bottom: 16px;
        }}

        .locked-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 8px;
        }}

        .locked-text {{
            font-size: 14px;
            color: var(--gray-600);
            margin-bottom: 20px;
        }}

        .cta-section {{
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            padding: 40px;
            text-align: center;
            color: white;
        }}

        .cta-title {{
            font-size: 22px;
            font-weight: 600;
            margin-bottom: 12px;
        }}

        .cta-text {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 24px;
        }}

        .cta-button {{
            display: inline-block;
            background: white;
            color: var(--primary);
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            text-decoration: none;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .cta-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}

        .contact-info {{
            display: flex;
            justify-content: center;
            gap: 32px;
            margin-top: 24px;
            font-size: 14px;
        }}

        .contact-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .disclaimer {{
            padding: 24px 40px;
            background: var(--gray-100);
            font-size: 11px;
            color: var(--gray-500);
            line-height: 1.5;
        }}

        .disclaimer-title {{
            font-weight: 600;
            color: var(--gray-600);
            margin-bottom: 8px;
        }}

        @media (max-width: 600px) {{
            .summary-grid {{
                grid-template-columns: 1fr;
            }}
            .header, .summary, .insights, .cta-section {{
                padding: 24px;
            }}
            .contact-info {{
                flex-direction: column;
                gap: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="report">
        <!-- Header with CPA Branding -->
        <div class="header">
            <div class="cpa-logo">{cpa_logo}</div>
            <div class="cpa-name">{cpa_display_name}</div>
            <div class="cpa-firm">{cpa_firm}</div>

            <h1 class="report-title">Tax Advisory Report</h1>

            <div class="client-section">
                <div class="client-name">{client_name}</div>
                <div class="client-detail">Tax Year 2024 | {filing_status} | {complexity}</div>
            </div>
        </div>

        <!-- Summary Section -->
        <div class="summary">
            <h2 class="summary-title">Your Tax Situation Overview</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-label">Filing Status</div>
                    <div class="summary-value">{filing_status_short}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Complexity</div>
                    <div class="summary-value">{complexity}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Potential Savings</div>
                    <div class="summary-value savings">{savings_range}</div>
                </div>
            </div>
        </div>

        <!-- Insights Section -->
        <div class="insights">
            <h2 class="insights-title">Tax Optimization Opportunities</h2>
            <p class="insights-subtitle">We identified {total_insights} opportunities. Here's a preview:</p>

            {insight_cards}

            <!-- Locked Insights -->
            <div class="locked-insights">
                <div class="locked-icon">&#128274;</div>
                <h3 class="locked-title">{locked_count} More Opportunities Identified</h3>
                <p class="locked-text">
                    Contact {cpa_first_name} to unlock your complete analysis including
                    specific dollar amounts, action items, IRS references, and deadlines.
                </p>
            </div>
        </div>

        <!-- CTA Section -->
        <div class="cta-section">
            <h2 class="cta-title">Ready to Maximize Your Tax Savings?</h2>
            <p class="cta-text">
                Schedule a consultation with {cpa_display_name} to discuss
                your personalized tax strategy and unlock your full analysis.
            </p>
            <a href="{booking_link}" class="cta-button">Schedule Free Consultation</a>

            <div class="contact-info">
                {contact_items}
            </div>
        </div>

        <!-- Disclaimer -->
        <div class="disclaimer">
            <div class="disclaimer-title">Important Disclosures</div>
            <p>{disclaimer}</p>
        </div>
    </div>
</body>
</html>
"""


# =============================================================================
# TIER 2 REPORT TEMPLATE (FULL - After Engagement)
# =============================================================================

TIER_2_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Complete Tax Advisory Report - {client_name}</title>
    <style>
        :root {{
            --primary: #1e40af;
            --primary-light: #dbeafe;
            --secondary: #059669;
            --secondary-light: #d1fae5;
            --accent: #f59e0b;
            --accent-light: #fef3c7;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-500: #6b7280;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-900: #111827;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--gray-700);
            background: var(--gray-50);
        }}

        .report {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            color: white;
            padding: 40px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}

        .header-left {{
            flex: 1;
        }}

        .header-right {{
            text-align: right;
        }}

        .cpa-info {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
        }}

        .cpa-logo {{
            width: 60px;
            height: 60px;
            background: white;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: var(--primary);
        }}

        .cpa-name {{
            font-size: 20px;
            font-weight: 700;
        }}

        .cpa-firm {{
            font-size: 13px;
            opacity: 0.9;
        }}

        .report-title {{
            font-size: 28px;
            font-weight: 300;
            margin-bottom: 8px;
        }}

        .report-badge {{
            display: inline-block;
            background: var(--secondary);
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}

        .client-name {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 4px;
        }}

        .report-date {{
            font-size: 13px;
            opacity: 0.8;
        }}

        .summary {{
            padding: 40px;
            background: var(--gray-50);
            border-bottom: 1px solid var(--gray-200);
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }}

        .summary-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}

        .summary-card.highlight {{
            background: var(--secondary);
            color: white;
        }}

        .summary-label {{
            font-size: 11px;
            color: var(--gray-500);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .summary-card.highlight .summary-label {{
            color: rgba(255,255,255,0.8);
        }}

        .summary-value {{
            font-size: 22px;
            font-weight: 700;
            color: var(--primary);
        }}

        .summary-card.highlight .summary-value {{
            color: white;
        }}

        .insights-section {{
            padding: 40px;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 8px;
        }}

        .section-subtitle {{
            font-size: 14px;
            color: var(--gray-500);
            margin-bottom: 24px;
        }}

        .insight-card {{
            background: var(--gray-50);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            border-left: 4px solid var(--secondary);
        }}

        .insight-card.high-priority {{
            border-left-color: var(--accent);
        }}

        .insight-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }}

        .insight-title {{
            font-size: 17px;
            font-weight: 600;
            color: var(--gray-900);
        }}

        .insight-meta {{
            display: flex;
            gap: 8px;
        }}

        .insight-category {{
            font-size: 10px;
            background: var(--primary-light);
            color: var(--primary);
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 500;
            text-transform: uppercase;
        }}

        .insight-priority {{
            font-size: 10px;
            background: var(--accent-light);
            color: var(--accent);
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 500;
            text-transform: uppercase;
        }}

        .insight-description {{
            font-size: 14px;
            color: var(--gray-600);
            margin-bottom: 16px;
        }}

        .insight-savings {{
            display: flex;
            gap: 20px;
            margin-bottom: 16px;
        }}

        .savings-item {{
            background: white;
            padding: 12px 16px;
            border-radius: 8px;
        }}

        .savings-label {{
            font-size: 11px;
            color: var(--gray-500);
            margin-bottom: 4px;
        }}

        .savings-value {{
            font-size: 18px;
            font-weight: 700;
            color: var(--secondary);
        }}

        .action-items {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }}

        .action-title {{
            font-size: 13px;
            font-weight: 600;
            color: var(--gray-700);
            margin-bottom: 8px;
        }}

        .action-list {{
            list-style: none;
        }}

        .action-list li {{
            font-size: 13px;
            color: var(--gray-600);
            padding: 6px 0;
            padding-left: 20px;
            position: relative;
        }}

        .action-list li:before {{
            content: "\\2713";
            position: absolute;
            left: 0;
            color: var(--secondary);
            font-weight: bold;
        }}

        .insight-footer {{
            display: flex;
            gap: 24px;
            font-size: 12px;
            color: var(--gray-500);
        }}

        .footer-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .tax-calendar {{
            padding: 40px;
            background: var(--gray-50);
        }}

        .calendar-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }}

        .calendar-item {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            display: flex;
            gap: 16px;
        }}

        .calendar-date {{
            background: var(--primary);
            color: white;
            border-radius: 8px;
            padding: 10px 14px;
            text-align: center;
            min-width: 60px;
        }}

        .calendar-month {{
            font-size: 11px;
            opacity: 0.9;
        }}

        .calendar-day {{
            font-size: 22px;
            font-weight: 700;
        }}

        .calendar-content h4 {{
            font-size: 14px;
            color: var(--gray-900);
            margin-bottom: 4px;
        }}

        .calendar-content p {{
            font-size: 13px;
            color: var(--gray-500);
        }}

        .next-steps {{
            padding: 40px;
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            color: white;
            text-align: center;
        }}

        .next-steps h2 {{
            font-size: 22px;
            margin-bottom: 16px;
        }}

        .next-steps p {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 24px;
        }}

        .cta-button {{
            display: inline-block;
            background: white;
            color: var(--primary);
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
        }}

        .contact-grid {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 24px;
            font-size: 14px;
        }}

        .disclaimer {{
            padding: 24px 40px;
            background: var(--gray-100);
            font-size: 11px;
            color: var(--gray-500);
        }}

        @media (max-width: 768px) {{
            .header {{
                flex-direction: column;
            }}
            .header-right {{
                text-align: left;
                margin-top: 16px;
            }}
            .summary-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .calendar-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        @media print {{
            .report {{
                box-shadow: none;
            }}
            .next-steps {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="report">
        <!-- Header -->
        <div class="header">
            <div class="header-left">
                <div class="cpa-info">
                    <div class="cpa-logo">{cpa_logo}</div>
                    <div>
                        <div class="cpa-name">{cpa_display_name}</div>
                        <div class="cpa-firm">{cpa_firm}</div>
                    </div>
                </div>
                <h1 class="report-title">Complete Tax Advisory Report</h1>
                <span class="report-badge">FULL ANALYSIS</span>
            </div>
            <div class="header-right">
                <div class="client-name">{client_name}</div>
                <div class="report-date">Generated: {report_date}</div>
                <div class="report-date">Tax Year: 2024</div>
            </div>
        </div>

        <!-- Summary -->
        <div class="summary">
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-label">Filing Status</div>
                    <div class="summary-value">{filing_status_short}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Complexity</div>
                    <div class="summary-value">{complexity}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Opportunities</div>
                    <div class="summary-value">{total_insights}</div>
                </div>
                <div class="summary-card highlight">
                    <div class="summary-label">Total Potential Savings</div>
                    <div class="summary-value">{total_savings}</div>
                </div>
            </div>
        </div>

        <!-- Insights -->
        <div class="insights-section">
            <h2 class="section-title">Your Tax Optimization Opportunities</h2>
            <p class="section-subtitle">
                Detailed analysis with specific actions and IRS references
            </p>

            {insight_cards}
        </div>

        <!-- Tax Calendar -->
        <div class="tax-calendar">
            <h2 class="section-title">Important Tax Deadlines</h2>
            <p class="section-subtitle" style="margin-bottom: 24px;">
                Key dates for your tax planning
            </p>
            <div class="calendar-grid">
                {calendar_items}
            </div>
        </div>

        <!-- Next Steps -->
        <div class="next-steps">
            <h2>Ready to Take Action?</h2>
            <p>
                {cpa_first_name} is ready to help you implement these strategies
                and maximize your tax savings.
            </p>
            <a href="{booking_link}" class="cta-button">Schedule Consultation</a>
            <div class="contact-grid">
                {contact_items}
            </div>
        </div>

        <!-- Disclaimer -->
        <div class="disclaimer">
            <strong>Important Disclosures</strong><br>
            {disclaimer}
        </div>
    </div>
</body>
</html>
"""


# =============================================================================
# REPORT GENERATOR SERVICE
# =============================================================================

class ReportTemplateService:
    """
    Service for generating tiered tax advisory reports.

    Tier 1: FREE lead magnet report (teaser)
    Tier 2: Full report (after engagement)
    """

    def __init__(self):
        pass

    def _get_db_connection(self):
        """Get database connection."""
        db_path = Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def generate_tier_one_report(
        self,
        cpa_profile: CPAProfile,
        lead: LeadMagnetLead,
        insights: List[TaxInsight],
        max_insights_shown: int = 3,
    ) -> str:
        """
        Generate Tier 1 (FREE) report.

        Shows:
        - CPA name & credentials (full)
        - Client name (full)
        - Filing status & complexity (full)
        - Savings estimate (range only)
        - 3-5 teaser insights
        - Prominent CTA to contact CPA

        Hides:
        - Specific dollar amounts
        - Action items
        - IRS references
        """
        # Format insights for display
        shown_insights = insights[:max_insights_shown]
        locked_count = max(0, len(insights) - max_insights_shown)

        insight_cards_html = ""
        for insight in shown_insights:
            insight_cards_html += f"""
            <div class="insight-card">
                <div class="insight-header">
                    <div class="insight-title">{insight.title}</div>
                    <span class="insight-category">{insight.category}</span>
                </div>
                <p class="insight-description">{insight.description_teaser}</p>
                <span class="insight-savings">
                    Potential: ${insight.savings_low:,.0f} - ${insight.savings_high:,.0f}
                </span>
            </div>
            """

        # Format contact info
        contact_items = ""
        if cpa_profile.phone:
            contact_items += f'<span class="contact-item">&#128222; {cpa_profile.phone}</span>'
        if cpa_profile.email:
            contact_items += f'<span class="contact-item">&#9993; {cpa_profile.email}</span>'

        # Filing status display
        filing_status_map = {
            "single": "Single",
            "married_jointly": "Married Filing Jointly",
            "married_separately": "Married Filing Separately",
            "head_of_household": "Head of Household",
            "qualifying_widow": "Qualifying Widow(er)",
        }
        filing_status = filing_status_map.get(lead.filing_status or "", "Single")
        filing_status_short = {
            "single": "Single",
            "married_jointly": "MFJ",
            "married_separately": "MFS",
            "head_of_household": "HoH",
            "qualifying_widow": "QW",
        }.get(lead.filing_status or "", "Single")

        # Complexity display
        complexity_display = lead.complexity.value.title()

        # Generate HTML
        html = TIER_1_TEMPLATE.format(
            cpa_logo="&#9830;",  # Diamond symbol or could be img tag
            cpa_display_name=cpa_profile.display_name,
            cpa_firm=cpa_profile.firm_name or "",
            cpa_first_name=cpa_profile.first_name,
            client_name=lead.first_name,
            filing_status=filing_status,
            filing_status_short=filing_status_short,
            complexity=complexity_display,
            savings_range=f"${lead.savings_range_low:,.0f} - ${lead.savings_range_high:,.0f}",
            total_insights=len(insights),
            insight_cards=insight_cards_html,
            locked_count=locked_count,
            booking_link=cpa_profile.booking_link or "#contact",
            contact_items=contact_items,
            disclaimer=ClientFacingDisclaimers.ESTIMATE_DISCLAIMER,
        )

        # Store report
        self._store_report(
            session_id=lead.session_id,
            lead_id=lead.lead_id,
            cpa_id=cpa_profile.cpa_id,
            report_tier=1,
            report_html=html,
            insights_shown=len(shown_insights),
            total_insights=len(insights),
        )

        return html

    def generate_tier_two_report(
        self,
        cpa_profile: CPAProfile,
        lead: LeadMagnetLead,
        insights: List[TaxInsight],
    ) -> str:
        """
        Generate Tier 2 (Full) report.

        Shows everything from Tier 1 plus:
        - Exact savings amounts
        - All insights (8+)
        - Action items with deadlines
        - IRS form references
        - Tax calendar
        """
        # Generate insight cards with full details
        insight_cards_html = ""
        for insight in insights:
            priority_class = "high-priority" if insight.priority == "high" else ""
            priority_badge = f'<span class="insight-priority">{insight.priority}</span>' if insight.priority == "high" else ""

            action_items_html = ""
            if insight.action_items:
                items = "".join(f"<li>{item}</li>" for item in insight.action_items)
                action_items_html = f"""
                <div class="action-items">
                    <div class="action-title">Action Items</div>
                    <ul class="action-list">{items}</ul>
                </div>
                """

            footer_items = ""
            if insight.irs_reference:
                footer_items += f'<span class="footer-item">&#128196; {insight.irs_reference}</span>'
            if insight.deadline:
                footer_items += f'<span class="footer-item">&#128197; Deadline: {insight.deadline}</span>'

            insight_cards_html += f"""
            <div class="insight-card {priority_class}">
                <div class="insight-header">
                    <div class="insight-title">{insight.title}</div>
                    <div class="insight-meta">
                        <span class="insight-category">{insight.category}</span>
                        {priority_badge}
                    </div>
                </div>
                <p class="insight-description">{insight.description_full}</p>
                <div class="insight-savings">
                    <div class="savings-item">
                        <div class="savings-label">Conservative Estimate</div>
                        <div class="savings-value">${insight.savings_low:,.0f}</div>
                    </div>
                    <div class="savings-item">
                        <div class="savings-label">Maximum Potential</div>
                        <div class="savings-value">${insight.savings_high:,.0f}</div>
                    </div>
                </div>
                {action_items_html}
                <div class="insight-footer">
                    {footer_items}
                </div>
            </div>
            """

        # Tax calendar items
        calendar_items_html = """
            <div class="calendar-item">
                <div class="calendar-date">
                    <div class="calendar-month">APR</div>
                    <div class="calendar-day">15</div>
                </div>
                <div class="calendar-content">
                    <h4>Tax Filing Deadline</h4>
                    <p>Federal and most state returns due</p>
                </div>
            </div>
            <div class="calendar-item">
                <div class="calendar-date">
                    <div class="calendar-month">APR</div>
                    <div class="calendar-day">15</div>
                </div>
                <div class="calendar-content">
                    <h4>IRA Contribution Deadline</h4>
                    <p>Last day to contribute for prior tax year</p>
                </div>
            </div>
            <div class="calendar-item">
                <div class="calendar-date">
                    <div class="calendar-month">JUN</div>
                    <div class="calendar-day">15</div>
                </div>
                <div class="calendar-content">
                    <h4>Q2 Estimated Taxes</h4>
                    <p>Due for self-employed and investors</p>
                </div>
            </div>
            <div class="calendar-item">
                <div class="calendar-date">
                    <div class="calendar-month">DEC</div>
                    <div class="calendar-day">31</div>
                </div>
                <div class="calendar-content">
                    <h4>Year-End Tax Planning</h4>
                    <p>Last day for tax-loss harvesting, charitable gifts</p>
                </div>
            </div>
        """

        # Contact items
        contact_items = ""
        if cpa_profile.phone:
            contact_items += f'<span>&#128222; {cpa_profile.phone}</span>'
        if cpa_profile.email:
            contact_items += f'<span>&#9993; {cpa_profile.email}</span>'

        # Filing status
        filing_status_short = {
            "single": "Single",
            "married_jointly": "MFJ",
            "married_separately": "MFS",
            "head_of_household": "HoH",
            "qualifying_widow": "QW",
        }.get(lead.filing_status or "", "Single")

        # Calculate totals
        total_savings_low = sum(i.savings_low for i in insights)
        total_savings_high = sum(i.savings_high for i in insights)
        total_savings = f"${total_savings_low:,.0f} - ${total_savings_high:,.0f}"

        # Generate HTML
        html = TIER_2_TEMPLATE.format(
            cpa_logo="&#9830;",
            cpa_display_name=cpa_profile.display_name,
            cpa_firm=cpa_profile.firm_name or "",
            cpa_first_name=cpa_profile.first_name,
            client_name=lead.first_name,
            report_date=datetime.utcnow().strftime("%B %d, %Y"),
            filing_status_short=filing_status_short,
            complexity=lead.complexity.value.title(),
            total_insights=len(insights),
            total_savings=total_savings,
            insight_cards=insight_cards_html,
            calendar_items=calendar_items_html,
            booking_link=cpa_profile.booking_link or "#contact",
            contact_items=contact_items,
            disclaimer=(
                f"{ClientFacingDisclaimers.ESTIMATE_DISCLAIMER}\n\n"
                f"{PlatformDisclaimers.CIRCULAR_230_DISCLAIMER}"
            ),
        )

        # Store report
        self._store_report(
            session_id=lead.session_id,
            lead_id=lead.lead_id,
            cpa_id=cpa_profile.cpa_id,
            report_tier=2,
            report_html=html,
            insights_shown=len(insights),
            total_insights=len(insights),
        )

        return html

    def _store_report(
        self,
        session_id: str,
        lead_id: str,
        cpa_id: str,
        report_tier: int,
        report_html: str,
        insights_shown: int,
        total_insights: int,
    ):
        """Store generated report in database."""
        report_id = f"report-{uuid.uuid4().hex[:12]}"

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tiered_reports (
                    report_id, session_id, lead_id, cpa_id,
                    report_tier, report_html, insights_shown, total_insights
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, session_id, lead_id, cpa_id,
                report_tier, report_html, insights_shown, total_insights,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to store report: {e}")

    def get_report(
        self,
        session_id: str,
        tier: int = 1,
    ) -> Optional[str]:
        """Get stored report HTML by session ID and tier."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_html FROM tiered_reports
                WHERE session_id = ? AND report_tier = ?
                ORDER BY generated_at DESC LIMIT 1
            """, (session_id, tier))
            row = cursor.fetchone()
            conn.close()

            if row:
                return row["report_html"]
        except Exception as e:
            logger.error(f"Failed to get report: {e}")

        return None


# =============================================================================
# SINGLETON
# =============================================================================

_report_template_service: Optional[ReportTemplateService] = None


def get_report_template_service() -> ReportTemplateService:
    """Get the singleton report template service instance."""
    global _report_template_service
    if _report_template_service is None:
        _report_template_service = ReportTemplateService()
    return _report_template_service
