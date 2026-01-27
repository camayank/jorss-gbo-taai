"""
Tax Timeline Section - Important tax deadlines and calendar.

Provides:
- Key tax deadlines for the current year
- Filing reminders
- Estimated tax payment dates
- Extension deadlines
- Personalized deadline recommendations
"""

from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme


class DeadlineType(Enum):
    FILING = "filing"
    ESTIMATED_TAX = "estimated_tax"
    EXTENSION = "extension"
    RETIREMENT = "retirement"
    BUSINESS = "business"
    OTHER = "other"


@dataclass
class TaxDeadline:
    """Tax deadline information."""
    title: str
    date: date
    description: str
    deadline_type: DeadlineType
    applies_to: List[str]  # filing statuses or "all"
    penalty_info: Optional[str] = None
    extension_available: bool = False


class TaxTimelineRenderer:
    """Render tax timeline and deadline information."""

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
    ):
        self.data = data
        self.theme = theme
        self.tax_year = data.tax_year

    def get_deadlines(self) -> List[TaxDeadline]:
        """Get relevant tax deadlines for the tax year."""
        # Deadlines are for filing returns for tax_year
        filing_year = self.tax_year + 1

        # Core deadlines
        deadlines = [
            TaxDeadline(
                title="Individual Tax Return Due",
                date=date(filing_year, 4, 15),
                description="Form 1040 due date for individual tax returns",
                deadline_type=DeadlineType.FILING,
                applies_to=["all"],
                penalty_info="Failure-to-file penalty: 5% per month up to 25%",
                extension_available=True
            ),
            TaxDeadline(
                title="First Estimated Tax Payment (Q1)",
                date=date(filing_year, 4, 15),
                description="First quarterly estimated tax payment due",
                deadline_type=DeadlineType.ESTIMATED_TAX,
                applies_to=["self_employed", "business_owner"],
                penalty_info="Underpayment penalty may apply if not paid",
                extension_available=False
            ),
            TaxDeadline(
                title="Second Estimated Tax Payment (Q2)",
                date=date(filing_year, 6, 15),
                description="Second quarterly estimated tax payment due",
                deadline_type=DeadlineType.ESTIMATED_TAX,
                applies_to=["self_employed", "business_owner"],
                penalty_info="Underpayment penalty may apply if not paid",
                extension_available=False
            ),
            TaxDeadline(
                title="Third Estimated Tax Payment (Q3)",
                date=date(filing_year, 9, 15),
                description="Third quarterly estimated tax payment due",
                deadline_type=DeadlineType.ESTIMATED_TAX,
                applies_to=["self_employed", "business_owner"],
                penalty_info="Underpayment penalty may apply if not paid",
                extension_available=False
            ),
            TaxDeadline(
                title="Extended Return Due Date",
                date=date(filing_year, 10, 15),
                description="Final deadline for extended individual tax returns",
                deadline_type=DeadlineType.EXTENSION,
                applies_to=["all"],
                penalty_info="No further extension available after this date",
                extension_available=False
            ),
            TaxDeadline(
                title="Fourth Estimated Tax Payment (Q4)",
                date=date(filing_year + 1, 1, 15),
                description="Fourth quarterly estimated tax payment due",
                deadline_type=DeadlineType.ESTIMATED_TAX,
                applies_to=["self_employed", "business_owner"],
                penalty_info="Underpayment penalty may apply if not paid",
                extension_available=False
            ),
        ]

        # Retirement contribution deadlines
        retirement_deadlines = [
            TaxDeadline(
                title="IRA Contribution Deadline",
                date=date(filing_year, 4, 15),
                description=f"Last day to make IRA contributions for {self.tax_year}",
                deadline_type=DeadlineType.RETIREMENT,
                applies_to=["all"],
                penalty_info="Contributions after this date apply to next year",
                extension_available=False
            ),
            TaxDeadline(
                title="SEP-IRA Contribution Deadline",
                date=date(filing_year, 4, 15),
                description=f"SEP-IRA contribution deadline (with extension: Oct 15)",
                deadline_type=DeadlineType.RETIREMENT,
                applies_to=["self_employed", "business_owner"],
                extension_available=True
            ),
            TaxDeadline(
                title="Solo 401(k) Employee Contribution",
                date=date(self.tax_year, 12, 31),
                description=f"Employee contribution deadline for Solo 401(k)",
                deadline_type=DeadlineType.RETIREMENT,
                applies_to=["self_employed"],
                extension_available=False
            ),
            TaxDeadline(
                title="HSA Contribution Deadline",
                date=date(filing_year, 4, 15),
                description=f"Last day to make HSA contributions for {self.tax_year}",
                deadline_type=DeadlineType.RETIREMENT,
                applies_to=["all"],
                extension_available=False
            ),
        ]

        # Business deadlines
        business_deadlines = [
            TaxDeadline(
                title="S-Corporation Return Due (Form 1120-S)",
                date=date(filing_year, 3, 15),
                description="S-Corp tax returns due",
                deadline_type=DeadlineType.BUSINESS,
                applies_to=["s_corp"],
                penalty_info="$220 per shareholder per month penalty",
                extension_available=True
            ),
            TaxDeadline(
                title="Partnership Return Due (Form 1065)",
                date=date(filing_year, 3, 15),
                description="Partnership tax returns due",
                deadline_type=DeadlineType.BUSINESS,
                applies_to=["partnership"],
                penalty_info="$220 per partner per month penalty",
                extension_available=True
            ),
            TaxDeadline(
                title="C-Corporation Return Due (Form 1120)",
                date=date(filing_year, 4, 15),
                description="C-Corp tax returns due (calendar year)",
                deadline_type=DeadlineType.BUSINESS,
                applies_to=["c_corp"],
                penalty_info="Failure-to-file penalty applies",
                extension_available=True
            ),
            TaxDeadline(
                title="FBAR Filing Deadline (FinCEN 114)",
                date=date(filing_year, 4, 15),
                description="Foreign Bank Account Report due",
                deadline_type=DeadlineType.OTHER,
                applies_to=["foreign_accounts"],
                penalty_info="Severe penalties for non-compliance",
                extension_available=True
            ),
        ]

        # Year-end planning deadlines (for current year planning)
        year_end_deadlines = [
            TaxDeadline(
                title="401(k) Employee Contribution Deadline",
                date=date(self.tax_year, 12, 31),
                description="Last day for 401(k) employee contributions",
                deadline_type=DeadlineType.RETIREMENT,
                applies_to=["all"],
                extension_available=False
            ),
            TaxDeadline(
                title="Charitable Contribution Deadline",
                date=date(self.tax_year, 12, 31),
                description="Last day for charitable deductions",
                deadline_type=DeadlineType.OTHER,
                applies_to=["all"],
                extension_available=False
            ),
            TaxDeadline(
                title="Tax Loss Harvesting Deadline",
                date=date(self.tax_year, 12, 31),
                description="Last day to realize capital losses for tax purposes",
                deadline_type=DeadlineType.OTHER,
                applies_to=["investors"],
                extension_available=False
            ),
            TaxDeadline(
                title="Required Minimum Distribution (RMD)",
                date=date(self.tax_year, 12, 31),
                description="RMD must be taken by year end (if applicable)",
                deadline_type=DeadlineType.RETIREMENT,
                applies_to=["age_73_plus"],
                penalty_info="25% excise tax on missed RMD amount",
                extension_available=False
            ),
        ]

        all_deadlines = deadlines + retirement_deadlines + business_deadlines + year_end_deadlines

        # Sort by date
        return sorted(all_deadlines, key=lambda d: d.date)

    def filter_applicable_deadlines(self, deadlines: List[TaxDeadline]) -> List[TaxDeadline]:
        """Filter deadlines based on taxpayer's situation."""
        applicable = []

        # Determine taxpayer attributes
        has_business = any(
            inc.category.lower() in ['self-employment', 'business', 'schedule c', '1099-nec']
            for inc in self.data.income_items
        )
        has_investments = any(
            inc.category.lower() in ['investments', 'capital gains', 'dividends', 'interest']
            for inc in self.data.income_items
        )

        for deadline in deadlines:
            # All deadlines apply to everyone
            if "all" in deadline.applies_to:
                applicable.append(deadline)
            # Self-employed/business deadlines
            elif has_business and any(
                t in deadline.applies_to for t in ['self_employed', 'business_owner']
            ):
                applicable.append(deadline)
            # Investment-related deadlines
            elif has_investments and "investors" in deadline.applies_to:
                applicable.append(deadline)

        return applicable

    def render(self) -> str:
        """Render the complete tax timeline section."""
        primary = self.theme.primary_color if self.theme else "#2563eb"
        accent = self.theme.accent_color if self.theme else "#10b981"
        warning = self.theme.warning_color if self.theme else "#f59e0b"
        danger = self.theme.danger_color if self.theme else "#ef4444"

        # Get all deadlines
        all_deadlines = self.get_deadlines()
        applicable_deadlines = self.filter_applicable_deadlines(all_deadlines)

        # Separate into upcoming and past
        today = date.today()
        upcoming = [d for d in applicable_deadlines if d.date >= today]
        past = [d for d in applicable_deadlines if d.date < today]

        # Render timeline
        timeline_html = self._render_timeline(upcoming[:10], primary, accent, warning, danger)

        # Quick reference card
        quick_ref = self._render_quick_reference(primary, accent)

        # Estimated tax schedule
        estimated_html = ""
        if any(d.deadline_type == DeadlineType.ESTIMATED_TAX for d in applicable_deadlines):
            estimated_html = self._render_estimated_tax_schedule(primary)

        return f'''
<section class="tax-timeline" style="page-break-before: always;">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Important Tax Deadlines
  </h2>

  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 24px;">
    {quick_ref}
  </div>

  <h3 style="color: {primary}; margin: 24px 0 16px 0;">Upcoming Deadlines</h3>
  {timeline_html}

  {estimated_html}

  <div style="background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 16px; margin-top: 24px;">
    <p style="margin: 0; font-size: 0.875rem; color: #92400e;">
      <strong>Note:</strong> Deadlines may vary if they fall on weekends or holidays.
      Always verify specific deadlines with the IRS or your tax professional.
      Some states have different filing deadlines.
    </p>
  </div>
</section>
'''

    def _render_timeline(
        self,
        deadlines: List[TaxDeadline],
        primary: str,
        accent: str,
        warning: str,
        danger: str
    ) -> str:
        """Render visual timeline of deadlines."""
        if not deadlines:
            return '<p style="color: #6b7280;">No upcoming deadlines to display.</p>'

        today = date.today()
        items_html = ""

        for deadline in deadlines:
            days_until = (deadline.date - today).days

            # Color coding based on urgency
            if days_until <= 7:
                color = danger
                urgency = "Urgent"
            elif days_until <= 30:
                color = warning
                urgency = "Soon"
            else:
                color = accent
                urgency = ""

            # Format date
            date_str = deadline.date.strftime("%B %d, %Y")

            # Extension badge
            ext_badge = ""
            if deadline.extension_available:
                ext_badge = '<span style="background: #dbeafe; color: #1d4ed8; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; margin-left: 8px;">EXTENSION AVAILABLE</span>'

            items_html += f'''
<div style="display: flex; margin-bottom: 16px;">
  <div style="flex-shrink: 0; width: 100px; text-align: right; padding-right: 20px; border-right: 2px solid {primary};">
    <div style="font-size: 0.875rem; font-weight: 600; color: {primary};">{deadline.date.strftime("%b %d")}</div>
    <div style="font-size: 0.75rem; color: #6b7280;">{deadline.date.strftime("%Y")}</div>
    {f'<div style="font-size: 0.7rem; color: {color}; font-weight: 600; margin-top: 4px;">{urgency}</div>' if urgency else ''}
  </div>
  <div style="padding-left: 20px; position: relative;">
    <div style="position: absolute; left: -6px; top: 4px; width: 12px; height: 12px; background: {color}; border-radius: 50%;"></div>
    <div style="font-weight: 600; color: #111827; margin-bottom: 4px;">
      {deadline.title}
      {ext_badge}
    </div>
    <div style="font-size: 0.875rem; color: #6b7280;">{deadline.description}</div>
    {f'<div style="font-size: 0.8125rem; color: {danger}; margin-top: 4px;">⚠ {deadline.penalty_info}</div>' if deadline.penalty_info else ''}
  </div>
</div>
'''

        return f'<div style="margin: 20px 0;">{items_html}</div>'

    def _render_quick_reference(self, primary: str, accent: str) -> str:
        """Render quick reference cards."""
        filing_year = self.tax_year + 1

        return f'''
<div style="background: linear-gradient(135deg, {primary}08 0%, {primary}15 100%); border: 1px solid {primary}30; border-radius: 12px; padding: 20px;">
  <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Tax Return Deadline</div>
  <div style="font-size: 1.5rem; font-weight: 700; color: {primary}; margin-top: 8px;">April 15, {filing_year}</div>
  <div style="font-size: 0.875rem; color: #374151; margin-top: 8px;">Form 1040 Individual Return</div>
</div>

<div style="background: linear-gradient(135deg, {accent}08 0%, {accent}15 100%); border: 1px solid {accent}30; border-radius: 12px; padding: 20px;">
  <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Extended Deadline</div>
  <div style="font-size: 1.5rem; font-weight: 700; color: {accent}; margin-top: 8px;">October 15, {filing_year}</div>
  <div style="font-size: 0.875rem; color: #374151; margin-top: 8px;">If Form 4868 filed by April 15</div>
</div>

<div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 20px;">
  <div style="font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">IRA Contribution</div>
  <div style="font-size: 1.5rem; font-weight: 700; color: #dc2626; margin-top: 8px;">April 15, {filing_year}</div>
  <div style="font-size: 0.875rem; color: #374151; margin-top: 8px;">Last day for {self.tax_year} contributions</div>
</div>
'''

    def _render_estimated_tax_schedule(self, primary: str) -> str:
        """Render estimated tax payment schedule."""
        filing_year = self.tax_year + 1

        return f'''
<h3 style="color: {primary}; margin: 24px 0 16px 0;">Estimated Tax Payment Schedule</h3>

<div style="overflow-x: auto;">
  <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <thead>
      <tr style="background: {primary}; color: white;">
        <th style="padding: 12px 16px; text-align: left;">Payment Period</th>
        <th style="padding: 12px 16px; text-align: center;">Income Earned</th>
        <th style="padding: 12px 16px; text-align: center;">Due Date</th>
        <th style="padding: 12px 16px; text-align: center;">Form</th>
      </tr>
    </thead>
    <tbody>
      <tr style="border-bottom: 1px solid #e5e7eb;">
        <td style="padding: 12px 16px;">Q1 Payment</td>
        <td style="padding: 12px 16px; text-align: center;">Jan 1 - Mar 31</td>
        <td style="padding: 12px 16px; text-align: center; font-weight: 600;">April 15, {filing_year}</td>
        <td style="padding: 12px 16px; text-align: center;">1040-ES</td>
      </tr>
      <tr style="border-bottom: 1px solid #e5e7eb; background: #f9fafb;">
        <td style="padding: 12px 16px;">Q2 Payment</td>
        <td style="padding: 12px 16px; text-align: center;">Apr 1 - May 31</td>
        <td style="padding: 12px 16px; text-align: center; font-weight: 600;">June 15, {filing_year}</td>
        <td style="padding: 12px 16px; text-align: center;">1040-ES</td>
      </tr>
      <tr style="border-bottom: 1px solid #e5e7eb;">
        <td style="padding: 12px 16px;">Q3 Payment</td>
        <td style="padding: 12px 16px; text-align: center;">Jun 1 - Aug 31</td>
        <td style="padding: 12px 16px; text-align: center; font-weight: 600;">Sept 15, {filing_year}</td>
        <td style="padding: 12px 16px; text-align: center;">1040-ES</td>
      </tr>
      <tr style="background: #f9fafb;">
        <td style="padding: 12px 16px;">Q4 Payment</td>
        <td style="padding: 12px 16px; text-align: center;">Sep 1 - Dec 31</td>
        <td style="padding: 12px 16px; text-align: center; font-weight: 600;">Jan 15, {filing_year + 1}</td>
        <td style="padding: 12px 16px; text-align: center;">1040-ES</td>
      </tr>
    </tbody>
  </table>
</div>

<div style="background: #f3f4f6; border-radius: 8px; padding: 16px; margin-top: 16px;">
  <p style="margin: 0; font-size: 0.875rem; color: #374151;">
    <strong>Safe Harbor Rule:</strong> To avoid underpayment penalties, pay at least 90% of current year tax
    OR 100% of prior year tax (110% if AGI exceeds $150,000).
  </p>
</div>
'''
