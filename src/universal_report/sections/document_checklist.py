"""
Document Checklist Section - Required documents for tax filing.

Provides:
- Personalized document checklist based on income sources
- Document status tracking
- Missing document alerts
- Document organization tips
"""

from __future__ import annotations

from typing import Optional, List, Dict, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from universal_report.data_collector import NormalizedReportData
    from universal_report.branding.theme_manager import BrandTheme


@dataclass
class DocumentItem:
    """Document requirement item."""
    name: str
    form_number: str
    description: str
    category: str
    deadline_info: str
    required: bool = True
    tips: Optional[str] = None


class DocumentChecklistRenderer:
    """Render personalized document checklist."""

    # Comprehensive document database
    DOCUMENT_DATABASE = {
        'identity': [
            DocumentItem(
                name="Social Security Numbers",
                form_number="SSN/ITIN",
                description="For taxpayer, spouse, and all dependents",
                category="Identity",
                deadline_info="Required before filing",
                tips="Keep cards in a secure location, use copies for filing"
            ),
            DocumentItem(
                name="Driver's License/State ID",
                form_number="State ID",
                description="Government-issued photo ID",
                category="Identity",
                deadline_info="Required before filing",
                required=False
            ),
            DocumentItem(
                name="Prior Year Tax Return",
                form_number="Form 1040",
                description="Last year's tax return for reference",
                category="Identity",
                deadline_info="Helpful for comparison",
                tips="Keep at least 7 years of tax returns"
            ),
            DocumentItem(
                name="IP PIN (if issued)",
                form_number="IRS Letter",
                description="Identity Protection PIN from IRS",
                category="Identity",
                deadline_info="New PIN issued annually in January",
                required=False,
                tips="Required if you've been a victim of tax identity theft"
            ),
        ],
        'w2_income': [
            DocumentItem(
                name="W-2 Wage Statement",
                form_number="Form W-2",
                description="Wage and tax statement from employer(s)",
                category="Income",
                deadline_info="Employers must mail by January 31",
                tips="Should receive one from each employer"
            ),
        ],
        'self_employment': [
            DocumentItem(
                name="1099-NEC for Services",
                form_number="Form 1099-NEC",
                description="Nonemployee compensation (contractor income)",
                category="Income",
                deadline_info="Payers must issue by January 31",
                tips="You should receive this if paid $600+ as contractor"
            ),
            DocumentItem(
                name="Business Income Records",
                form_number="Income Ledger",
                description="All business income from sales, services",
                category="Income",
                deadline_info="Track throughout year",
                tips="Include cash, credit card, and check payments"
            ),
            DocumentItem(
                name="Business Expense Receipts",
                form_number="Receipts/Invoices",
                description="All business-related expense documentation",
                category="Expenses",
                deadline_info="Track throughout year",
                tips="Categorize by expense type (supplies, travel, etc.)"
            ),
            DocumentItem(
                name="Vehicle Mileage Log",
                form_number="Mileage Record",
                description="Business miles driven during the year",
                category="Expenses",
                deadline_info="Track per trip basis",
                tips="Include date, destination, purpose, and miles"
            ),
            DocumentItem(
                name="Home Office Measurements",
                form_number="Square Footage",
                description="Measurements of home and office space",
                category="Expenses",
                deadline_info="Measure once, update if changed",
                required=False,
                tips="Requires exclusive and regular business use"
            ),
        ],
        'investments': [
            DocumentItem(
                name="1099-DIV Dividends",
                form_number="Form 1099-DIV",
                description="Dividend income from investments",
                category="Income",
                deadline_info="Brokers must issue by February 15"
            ),
            DocumentItem(
                name="1099-INT Interest",
                form_number="Form 1099-INT",
                description="Interest income from bank accounts, bonds",
                category="Income",
                deadline_info="Payers must issue by January 31"
            ),
            DocumentItem(
                name="1099-B Stock Sales",
                form_number="Form 1099-B",
                description="Proceeds from stock and securities sales",
                category="Income",
                deadline_info="Brokers must issue by February 15",
                tips="Verify cost basis is accurate"
            ),
            DocumentItem(
                name="Consolidated 1099",
                form_number="Consolidated 1099",
                description="Combined investment statement from brokerage",
                category="Income",
                deadline_info="Often arrives mid-February",
                tips="May include 1099-DIV, 1099-INT, and 1099-B"
            ),
            DocumentItem(
                name="K-1 Partnership/S-Corp",
                form_number="Schedule K-1",
                description="Share of partnership or S-corp income",
                category="Income",
                deadline_info="Often arrives late (March-April)",
                required=False,
                tips="May require filing extension if delayed"
            ),
        ],
        'rental': [
            DocumentItem(
                name="Rental Income Records",
                form_number="Rent Ledger",
                description="All rental payments received",
                category="Income",
                deadline_info="Track monthly",
                tips="Include security deposits returned"
            ),
            DocumentItem(
                name="Rental Expense Records",
                form_number="Expense Ledger",
                description="All rental property expenses",
                category="Expenses",
                deadline_info="Track throughout year",
                tips="Include repairs, insurance, property management"
            ),
            DocumentItem(
                name="Mortgage Interest Statement",
                form_number="Form 1098",
                description="Mortgage interest paid on rental property",
                category="Expenses",
                deadline_info="Lender must issue by January 31"
            ),
            DocumentItem(
                name="Property Tax Records",
                form_number="Tax Bill",
                description="Property taxes paid on rental property",
                category="Expenses",
                deadline_info="County tax records"
            ),
            DocumentItem(
                name="Depreciation Schedule",
                form_number="Form 4562",
                description="Prior year depreciation calculations",
                category="Expenses",
                deadline_info="From prior tax return",
                tips="Required for accurate depreciation continuation"
            ),
        ],
        'deductions': [
            DocumentItem(
                name="Mortgage Interest Statement",
                form_number="Form 1098",
                description="Mortgage interest paid on primary residence",
                category="Deductions",
                deadline_info="Lender must issue by January 31"
            ),
            DocumentItem(
                name="Property Tax Records",
                form_number="Tax Bill",
                description="Property taxes paid on primary residence",
                category="Deductions",
                deadline_info="County tax records",
                tips="Subject to $10,000 SALT cap"
            ),
            DocumentItem(
                name="State Income Tax Paid",
                form_number="Tax Records",
                description="State and local income taxes paid",
                category="Deductions",
                deadline_info="State tax return or withholding",
                tips="Subject to $10,000 SALT cap"
            ),
            DocumentItem(
                name="Charitable Contribution Receipts",
                form_number="Receipts/Letters",
                description="Documentation of charitable donations",
                category="Deductions",
                deadline_info="Get receipts when donating",
                tips="Need written acknowledgment for gifts $250+"
            ),
            DocumentItem(
                name="Medical Expense Records",
                form_number="Receipts/EOBs",
                description="Out-of-pocket medical expenses",
                category="Deductions",
                deadline_info="Track throughout year",
                tips="Only deductible if exceeds 7.5% of AGI"
            ),
        ],
        'retirement': [
            DocumentItem(
                name="IRA Contribution Records",
                form_number="Form 5498",
                description="Traditional and Roth IRA contributions",
                category="Retirement",
                deadline_info="Custodian issues by May 31"
            ),
            DocumentItem(
                name="401(k) Contribution Summary",
                form_number="Plan Statement",
                description="Employer retirement plan contributions",
                category="Retirement",
                deadline_info="From employer/plan administrator"
            ),
            DocumentItem(
                name="1099-R Retirement Distributions",
                form_number="Form 1099-R",
                description="Distributions from retirement accounts",
                category="Income",
                deadline_info="Payers must issue by January 31",
                required=False
            ),
        ],
        'health': [
            DocumentItem(
                name="1095-A Marketplace Coverage",
                form_number="Form 1095-A",
                description="Health insurance from HealthCare.gov",
                category="Health",
                deadline_info="Marketplace issues by January 31",
                required=False,
                tips="Required to reconcile premium tax credit"
            ),
            DocumentItem(
                name="1095-B Health Coverage",
                form_number="Form 1095-B",
                description="Health coverage verification",
                category="Health",
                deadline_info="Insurer issues by January 31",
                required=False
            ),
            DocumentItem(
                name="HSA Contribution Records",
                form_number="Form 5498-SA",
                description="Health Savings Account contributions",
                category="Health",
                deadline_info="Custodian issues by May 31",
                required=False
            ),
        ],
        'education': [
            DocumentItem(
                name="1098-T Tuition Statement",
                form_number="Form 1098-T",
                description="Tuition and education expenses paid",
                category="Education",
                deadline_info="School issues by January 31",
                required=False,
                tips="Required for education credits"
            ),
            DocumentItem(
                name="1098-E Student Loan Interest",
                form_number="Form 1098-E",
                description="Student loan interest paid",
                category="Education",
                deadline_info="Lender issues by January 31",
                required=False,
                tips="Up to $2,500 deduction"
            ),
            DocumentItem(
                name="529 Plan Statements",
                form_number="Plan Statement",
                description="529 education savings plan activity",
                category="Education",
                deadline_info="From plan administrator",
                required=False
            ),
        ],
        'other': [
            DocumentItem(
                name="1099-G Unemployment",
                form_number="Form 1099-G",
                description="Unemployment compensation received",
                category="Income",
                deadline_info="State issues by January 31",
                required=False
            ),
            DocumentItem(
                name="1099-G State Refund",
                form_number="Form 1099-G",
                description="State tax refund received",
                category="Income",
                deadline_info="State issues by January 31",
                required=False,
                tips="Taxable only if you itemized prior year"
            ),
            DocumentItem(
                name="Social Security Statement",
                form_number="SSA-1099",
                description="Social Security benefits received",
                category="Income",
                deadline_info="SSA issues by January 31",
                required=False
            ),
            DocumentItem(
                name="Alimony Payment Records",
                form_number="Payment Records",
                description="Alimony paid (pre-2019 agreements)",
                category="Deductions",
                deadline_info="Track payments made",
                required=False,
                tips="Only deductible for agreements before 2019"
            ),
            DocumentItem(
                name="Gambling Winnings",
                form_number="W-2G",
                description="Gambling and lottery winnings",
                category="Income",
                deadline_info="Payer issues when winning",
                required=False
            ),
        ],
    }

    def __init__(
        self,
        data: "NormalizedReportData",
        theme: Optional["BrandTheme"] = None,
    ):
        self.data = data
        self.theme = theme

    def get_required_documents(self) -> Dict[str, List[DocumentItem]]:
        """Determine required documents based on taxpayer's situation."""
        required_docs: Dict[str, List[DocumentItem]] = {}

        # Always need identity documents
        required_docs['Identity & Prior Returns'] = self.DOCUMENT_DATABASE['identity']

        # Check income sources
        has_w2 = any(
            inc.category.lower() in ['wages', 'salary', 'w-2', 'employment']
            for inc in self.data.income_items
        )
        has_self_employment = any(
            inc.category.lower() in ['self-employment', 'business', 'schedule c', '1099-nec', '1099']
            for inc in self.data.income_items
        )
        has_investments = any(
            inc.category.lower() in ['investments', 'capital gains', 'dividends', 'interest', 'stocks']
            for inc in self.data.income_items
        )
        has_rental = any(
            inc.category.lower() in ['rental', 'real estate', 'property']
            for inc in self.data.income_items
        )

        # Add relevant categories
        if has_w2:
            required_docs['W-2 Employment Income'] = self.DOCUMENT_DATABASE['w2_income']

        if has_self_employment:
            required_docs['Self-Employment/Business'] = self.DOCUMENT_DATABASE['self_employment']

        if has_investments:
            required_docs['Investments & Capital Gains'] = self.DOCUMENT_DATABASE['investments']

        if has_rental:
            required_docs['Rental Property'] = self.DOCUMENT_DATABASE['rental']

        # Add deductions if itemizing or has deductions
        if self.data.deduction_items or self.data.deduction_type == 'itemized':
            required_docs['Deductions'] = self.DOCUMENT_DATABASE['deductions']

        # Always include retirement if any retirement-related items
        if any(
            'retirement' in d.description.lower() or 'ira' in d.description.lower() or '401' in d.description.lower()
            for d in self.data.deduction_items
        ):
            required_docs['Retirement Accounts'] = self.DOCUMENT_DATABASE['retirement']

        # Health documents
        required_docs['Health Insurance'] = self.DOCUMENT_DATABASE['health']

        # Education if relevant deductions/credits
        has_education = any(
            'education' in d.description.lower() or 'student' in d.description.lower() or 'tuition' in d.description.lower()
            for d in self.data.deduction_items
        )
        if has_education:
            required_docs['Education'] = self.DOCUMENT_DATABASE['education']

        # Other income
        required_docs['Other Documents'] = self.DOCUMENT_DATABASE['other']

        return required_docs

    def render(self) -> str:
        """Render the document checklist section."""
        primary = self.theme.primary_color if self.theme else "#2563eb"
        accent = self.theme.accent_color if self.theme else "#10b981"

        # Get personalized documents
        required_docs = self.get_required_documents()

        # Count total documents
        total_docs = sum(len(docs) for docs in required_docs.values())
        required_count = sum(
            len([d for d in docs if d.required])
            for docs in required_docs.values()
        )

        # Render checklist
        checklist_html = self._render_checklist(required_docs, primary, accent)

        # Document tips
        tips_html = self._render_document_tips(primary)

        return f'''
<section class="document-checklist" style="page-break-before: always;">
  <h2 style="color: {primary}; border-bottom: 2px solid {primary}; padding-bottom: 8px; margin-bottom: 24px;">
    Tax Document Checklist
  </h2>

  <div style="background: linear-gradient(135deg, {primary}08 0%, {primary}15 100%); border: 1px solid {primary}30; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
      <div>
        <div style="font-size: 0.875rem; color: #6b7280;">Documents to Gather</div>
        <div style="font-size: 1.75rem; font-weight: 700; color: {primary};">{total_docs} Items</div>
      </div>
      <div style="text-align: right;">
        <div style="font-size: 0.875rem; color: #6b7280;">Required Documents</div>
        <div style="font-size: 1.75rem; font-weight: 700; color: {accent};">{required_count}</div>
      </div>
    </div>
  </div>

  <p style="margin-bottom: 24px; color: #374151;">
    Based on your tax situation, here are the documents you'll need for filing your {self.data.tax_year} tax return.
    Items marked with <span style="color: #ef4444; font-weight: 600;">*</span> are essential.
  </p>

  {checklist_html}

  {tips_html}
</section>
'''

    def _render_checklist(self, required_docs: Dict[str, List[DocumentItem]], primary: str, accent: str) -> str:
        """Render the document checklist categories."""
        categories_html = ""

        for category_name, documents in required_docs.items():
            items_html = ""
            for doc in documents:
                required_badge = '<span style="color: #ef4444; font-weight: 600;">*</span> ' if doc.required else ''
                tip_html = f'<div style="font-size: 0.75rem; color: #9ca3af; margin-top: 4px;">💡 {doc.tips}</div>' if doc.tips else ''

                items_html += f'''
<div style="display: flex; gap: 12px; padding: 12px; border-bottom: 1px solid #f3f4f6;">
  <div style="flex-shrink: 0;">
    <div style="width: 20px; height: 20px; border: 2px solid {primary}; border-radius: 4px;"></div>
  </div>
  <div style="flex: 1;">
    <div style="font-weight: 500; color: #111827;">{required_badge}{doc.name}</div>
    <div style="font-size: 0.8125rem; color: #6b7280;">{doc.description}</div>
    <div style="display: flex; gap: 16px; margin-top: 4px; font-size: 0.75rem;">
      <span style="color: {primary}; font-weight: 500;">{doc.form_number}</span>
      <span style="color: #9ca3af;">{doc.deadline_info}</span>
    </div>
    {tip_html}
  </div>
</div>
'''

            categories_html += f'''
<div style="margin-bottom: 24px;">
  <h3 style="color: {primary}; font-size: 1rem; margin-bottom: 12px; padding: 8px 12px; background: {primary}08; border-radius: 6px;">
    {category_name}
  </h3>
  <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
    {items_html}
  </div>
</div>
'''

        return categories_html

    def _render_document_tips(self, primary: str) -> str:
        """Render document organization tips."""
        return f'''
<div style="background: #f9fafb; border-radius: 12px; padding: 20px; margin-top: 24px;">
  <h3 style="color: {primary}; margin: 0 0 16px 0; font-size: 1rem;">Document Organization Tips</h3>

  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px;">
    <div style="display: flex; gap: 12px; align-items: flex-start;">
      <span style="font-size: 1.25rem;">📁</span>
      <div>
        <div style="font-weight: 500; color: #111827;">Create a Tax Folder</div>
        <div style="font-size: 0.8125rem; color: #6b7280;">Keep all documents in one dedicated folder</div>
      </div>
    </div>

    <div style="display: flex; gap: 12px; align-items: flex-start;">
      <span style="font-size: 1.25rem;">📅</span>
      <div>
        <div style="font-weight: 500; color: #111827;">Track Arrival Dates</div>
        <div style="font-size: 0.8125rem; color: #6b7280;">Note expected dates and follow up if late</div>
      </div>
    </div>

    <div style="display: flex; gap: 12px; align-items: flex-start;">
      <span style="font-size: 1.25rem;">💾</span>
      <div>
        <div style="font-weight: 500; color: #111827;">Make Digital Copies</div>
        <div style="font-size: 0.8125rem; color: #6b7280;">Scan or photograph important documents</div>
      </div>
    </div>

    <div style="display: flex; gap: 12px; align-items: flex-start;">
      <span style="font-size: 1.25rem;">🔒</span>
      <div>
        <div style="font-weight: 500; color: #111827;">Keep Records 7 Years</div>
        <div style="font-size: 0.8125rem; color: #6b7280;">IRS recommends retaining records for 7 years</div>
      </div>
    </div>
  </div>
</div>

<div style="background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 16px; margin-top: 16px;">
  <p style="margin: 0; font-size: 0.875rem; color: #92400e;">
    <strong>Missing a Document?</strong> If you haven't received expected tax forms by mid-February,
    contact the payer or check their online portal. You can also request a Wage and Income Transcript
    from the IRS at irs.gov.
  </p>
</div>
'''
