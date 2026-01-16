"""PDF Generator.

Generates professional PDF documents for tax returns including
Form 1040, supporting schedules, workpapers, and client summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from models.tax_return import TaxReturn


@dataclass
class PDFSection:
    """A section in the PDF document."""
    title: str
    content: List[Dict[str, Any]]
    page_break_before: bool = False
    page_break_after: bool = False


@dataclass
class PDFDocument:
    """Generated PDF document."""
    filename: str
    content: bytes  # PDF content (would be actual PDF bytes in production)
    text_content: str  # Text representation for preview
    page_count: int
    generated_at: str
    document_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaxReturnPDFGenerator:
    """
    Generates PDF documents for tax returns.

    Creates professional-quality PDF output including the main
    Form 1040, all required schedules, and summary pages.
    """

    def __init__(self):
        """Initialize the PDF generator."""
        self._page_width = 612  # Letter size
        self._page_height = 792
        self._margin = 72  # 1 inch

    def generate_complete_return(
        self, tax_return: "TaxReturn", options: Optional[Dict[str, Any]] = None
    ) -> PDFDocument:
        """
        Generate complete tax return PDF.

        Args:
            tax_return: The tax return to render
            options: Optional rendering options

        Returns:
            PDFDocument with complete return
        """
        options = options or {}

        sections = []

        # Cover page
        if options.get("include_cover", True):
            sections.append(self._generate_cover_page(tax_return))

        # Summary page
        sections.append(self._generate_summary_page(tax_return))

        # Form 1040
        sections.append(self._generate_form_1040(tax_return))

        # Schedule 1 if needed
        if self._needs_schedule_1(tax_return):
            sections.append(self._generate_schedule_1(tax_return))

        # Schedule 2 if needed
        if self._needs_schedule_2(tax_return):
            sections.append(self._generate_schedule_2(tax_return))

        # Schedule 3 if needed
        if self._needs_schedule_3(tax_return):
            sections.append(self._generate_schedule_3(tax_return))

        # Schedule A if itemizing
        if self._is_itemizing(tax_return):
            sections.append(self._generate_schedule_a(tax_return))

        # Schedule C if self-employed
        if self._has_self_employment(tax_return):
            sections.append(self._generate_schedule_c(tax_return))

        # State return summary
        if hasattr(tax_return, 'state_tax_result') and tax_return.state_tax_result:
            sections.append(self._generate_state_summary(tax_return))

        # W-2 summary
        sections.append(self._generate_w2_summary(tax_return))

        # Convert to text (would be actual PDF generation in production)
        text_content = self._render_to_text(sections)
        page_count = len(sections) + 2  # Estimate

        filename = self._generate_filename(tax_return, "return")

        return PDFDocument(
            filename=filename,
            content=text_content.encode(),
            text_content=text_content,
            page_count=page_count,
            generated_at=datetime.now().isoformat(),
            document_type="tax_return",
            metadata={
                "tax_year": 2025,
                "includes_state": hasattr(tax_return, 'state_tax_result'),
            },
        )

    def generate_client_summary(
        self, tax_return: "TaxReturn", options: Optional[Dict[str, Any]] = None
    ) -> PDFDocument:
        """Generate client-friendly summary PDF."""
        sections = []

        # Header
        sections.append(self._generate_client_header(tax_return))

        # Key numbers
        sections.append(self._generate_key_numbers(tax_return))

        # Income breakdown
        sections.append(self._generate_income_breakdown(tax_return))

        # Deduction comparison
        sections.append(self._generate_deduction_comparison(tax_return))

        # Credits summary
        sections.append(self._generate_credits_summary(tax_return))

        # Refund/owed summary
        sections.append(self._generate_result_summary(tax_return))

        # Next steps
        sections.append(self._generate_next_steps(tax_return))

        text_content = self._render_to_text(sections)
        filename = self._generate_filename(tax_return, "summary")

        return PDFDocument(
            filename=filename,
            content=text_content.encode(),
            text_content=text_content,
            page_count=2,
            generated_at=datetime.now().isoformat(),
            document_type="client_summary",
        )

    def _generate_cover_page(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate cover page."""
        taxpayer = tax_return.taxpayer
        name = f"{getattr(taxpayer, 'first_name', '')} {getattr(taxpayer, 'last_name', '')}"
        ssn_masked = self._mask_ssn(getattr(taxpayer, 'ssn', ''))

        return PDFSection(
            title="",
            content=[
                {"type": "header", "text": "Individual Income Tax Return", "size": "large"},
                {"type": "header", "text": "Tax Year 2025", "size": "medium"},
                {"type": "spacer", "height": 40},
                {"type": "text", "text": f"Prepared for:", "bold": True},
                {"type": "text", "text": name, "size": "large"},
                {"type": "text", "text": f"SSN: {ssn_masked}"},
                {"type": "spacer", "height": 40},
                {"type": "text", "text": f"Filing Status: {taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else taxpayer.filing_status}"},
                {"type": "spacer", "height": 60},
                {"type": "text", "text": f"Prepared: {datetime.now().strftime('%B %d, %Y')}"},
                {"type": "text", "text": "Prepared by: Gorss-Gbo Tax Software"},
            ],
            page_break_after=True,
        )

    def _generate_summary_page(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate summary page."""
        agi = tax_return.adjusted_gross_income or 0
        taxable = tax_return.taxable_income or 0
        federal_tax = tax_return.tax_liability or 0
        state_tax = getattr(tax_return, 'state_tax_liability', 0) or 0
        withholding = getattr(tax_return.income, 'federal_withholding', 0) or 0
        result = tax_return.refund_or_owed or 0

        return PDFSection(
            title="Tax Return Summary",
            content=[
                {"type": "header", "text": "Tax Return Summary", "size": "large"},
                {"type": "line"},
                {"type": "spacer", "height": 20},
                {"type": "row", "label": "Total Income", "value": f"${agi:,.2f}"},
                {"type": "row", "label": "Adjustments to Income", "value": "-"},
                {"type": "row", "label": "Adjusted Gross Income", "value": f"${agi:,.2f}", "bold": True},
                {"type": "spacer", "height": 10},
                {"type": "row", "label": "Deductions", "value": f"${(agi - taxable):,.2f}"},
                {"type": "row", "label": "Taxable Income", "value": f"${taxable:,.2f}", "bold": True},
                {"type": "spacer", "height": 10},
                {"type": "row", "label": "Federal Tax", "value": f"${federal_tax:,.2f}"},
                {"type": "row", "label": "State Tax", "value": f"${state_tax:,.2f}"},
                {"type": "row", "label": "Total Tax", "value": f"${(federal_tax + state_tax):,.2f}", "bold": True},
                {"type": "spacer", "height": 10},
                {"type": "row", "label": "Total Withholding", "value": f"${withholding:,.2f}"},
                {"type": "line"},
                {"type": "row",
                 "label": "REFUND" if result > 0 else "AMOUNT OWED",
                 "value": f"${abs(result):,.2f}",
                 "bold": True,
                 "highlight": True},
            ],
            page_break_after=True,
        )

    def _generate_form_1040(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate Form 1040 representation."""
        taxpayer = tax_return.taxpayer
        income = tax_return.income

        w2_wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        interest = getattr(income, 'interest_income', 0) or 0
        dividends = getattr(income, 'dividend_income', 0) or 0
        cap_gains = getattr(income, 'capital_gain_income', 0) or 0

        return PDFSection(
            title="Form 1040",
            content=[
                {"type": "header", "text": "Form 1040 - U.S. Individual Income Tax Return", "size": "large"},
                {"type": "text", "text": "Tax Year 2025"},
                {"type": "line"},
                {"type": "spacer", "height": 10},

                {"type": "header", "text": "Taxpayer Information", "size": "medium"},
                {"type": "row", "label": "Name", "value": f"{getattr(taxpayer, 'first_name', '')} {getattr(taxpayer, 'last_name', '')}"},
                {"type": "row", "label": "SSN", "value": self._mask_ssn(getattr(taxpayer, 'ssn', ''))},
                {"type": "row", "label": "Filing Status", "value": taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else str(taxpayer.filing_status)},

                {"type": "spacer", "height": 10},
                {"type": "header", "text": "Income", "size": "medium"},
                {"type": "row", "label": "1. Wages, salaries, tips", "value": f"${w2_wages:,.2f}"},
                {"type": "row", "label": "2b. Taxable interest", "value": f"${interest:,.2f}"},
                {"type": "row", "label": "3b. Ordinary dividends", "value": f"${dividends:,.2f}"},
                {"type": "row", "label": "7. Capital gain or (loss)", "value": f"${cap_gains:,.2f}"},
                {"type": "row", "label": "9. Total income", "value": f"${tax_return.adjusted_gross_income or 0:,.2f}", "bold": True},
                {"type": "row", "label": "11. Adjusted gross income", "value": f"${tax_return.adjusted_gross_income or 0:,.2f}", "bold": True},

                {"type": "spacer", "height": 10},
                {"type": "header", "text": "Tax and Credits", "size": "medium"},
                {"type": "row", "label": "15. Taxable income", "value": f"${tax_return.taxable_income or 0:,.2f}"},
                {"type": "row", "label": "16. Tax", "value": f"${tax_return.tax_liability or 0:,.2f}"},
                {"type": "row", "label": "24. Total tax", "value": f"${tax_return.tax_liability or 0:,.2f}", "bold": True},

                {"type": "spacer", "height": 10},
                {"type": "header", "text": "Payments", "size": "medium"},
                {"type": "row", "label": "25a. Federal tax withheld", "value": f"${getattr(income, 'federal_withholding', 0) or 0:,.2f}"},
                {"type": "row", "label": "33. Total payments", "value": f"${getattr(income, 'federal_withholding', 0) or 0:,.2f}", "bold": True},

                {"type": "spacer", "height": 10},
                {"type": "header", "text": "Refund or Amount Owed", "size": "medium"},
                {"type": "row",
                 "label": "35. Refund" if (tax_return.refund_or_owed or 0) > 0 else "37. Amount owed",
                 "value": f"${abs(tax_return.refund_or_owed or 0):,.2f}",
                 "bold": True},
            ],
            page_break_after=True,
        )

    def _generate_schedule_1(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate Schedule 1."""
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0

        return PDFSection(
            title="Schedule 1",
            content=[
                {"type": "header", "text": "Schedule 1 - Additional Income and Adjustments", "size": "large"},
                {"type": "line"},
                {"type": "header", "text": "Part I - Additional Income", "size": "medium"},
                {"type": "row", "label": "3. Business income", "value": f"${max(0, se_income - se_expenses):,.2f}"},
                {"type": "spacer", "height": 10},
                {"type": "header", "text": "Part II - Adjustments to Income", "size": "medium"},
                {"type": "row", "label": "15. Deductible SE tax", "value": f"${(se_income * 0.9235 * 0.153 / 2):,.2f}"},
            ],
        )

    def _generate_schedule_2(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate Schedule 2."""
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0
        net_se = max(0, se_income - se_expenses)
        se_tax = net_se * 0.9235 * 0.153

        return PDFSection(
            title="Schedule 2",
            content=[
                {"type": "header", "text": "Schedule 2 - Additional Taxes", "size": "large"},
                {"type": "line"},
                {"type": "row", "label": "4. Self-employment tax", "value": f"${se_tax:,.2f}"},
            ],
        )

    def _generate_schedule_3(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate Schedule 3."""
        return PDFSection(
            title="Schedule 3",
            content=[
                {"type": "header", "text": "Schedule 3 - Additional Credits and Payments", "size": "large"},
                {"type": "line"},
                {"type": "text", "text": "See attached for credit details"},
            ],
        )

    def _generate_schedule_a(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate Schedule A."""
        deductions = tax_return.deductions
        agi = tax_return.adjusted_gross_income or 0

        medical = getattr(deductions, 'medical_expenses', 0) or 0
        medical_deduct = max(0, medical - agi * 0.075)
        property_tax = getattr(deductions, 'property_taxes', 0) or 0
        state_tax = getattr(deductions, 'state_local_taxes', 0) or 0
        salt = min(property_tax + state_tax, 10000)
        mortgage = getattr(deductions, 'mortgage_interest', 0) or 0
        charity = (getattr(deductions, 'charitable_cash', 0) or 0) + \
                  (getattr(deductions, 'charitable_noncash', 0) or 0)

        total = medical_deduct + salt + mortgage + charity

        return PDFSection(
            title="Schedule A",
            content=[
                {"type": "header", "text": "Schedule A - Itemized Deductions", "size": "large"},
                {"type": "line"},
                {"type": "row", "label": "4. Medical/dental (exceeds 7.5% AGI)", "value": f"${medical_deduct:,.2f}"},
                {"type": "row", "label": "5. State and local taxes (max $10,000)", "value": f"${salt:,.2f}"},
                {"type": "row", "label": "8. Home mortgage interest", "value": f"${mortgage:,.2f}"},
                {"type": "row", "label": "14. Gifts to charity", "value": f"${charity:,.2f}"},
                {"type": "line"},
                {"type": "row", "label": "17. Total itemized deductions", "value": f"${total:,.2f}", "bold": True},
            ],
        )

    def _generate_schedule_c(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate Schedule C."""
        income = tax_return.income
        gross = getattr(income, 'self_employment_income', 0) or 0
        expenses = getattr(income, 'self_employment_expenses', 0) or 0

        return PDFSection(
            title="Schedule C",
            content=[
                {"type": "header", "text": "Schedule C - Profit or Loss from Business", "size": "large"},
                {"type": "line"},
                {"type": "row", "label": "1. Gross receipts", "value": f"${gross:,.2f}"},
                {"type": "row", "label": "7. Gross income", "value": f"${gross:,.2f}"},
                {"type": "row", "label": "28. Total expenses", "value": f"${expenses:,.2f}"},
                {"type": "line"},
                {"type": "row", "label": "31. Net profit or (loss)", "value": f"${(gross - expenses):,.2f}", "bold": True},
            ],
        )

    def _generate_state_summary(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate state tax summary."""
        state_result = tax_return.state_tax_result

        # Handle both dict and dataclass formats
        if isinstance(state_result, dict):
            state_code = state_result.get("state_code", "")
            taxable_income = state_result.get("state_taxable_income", 0) or 0
            tax_liability = state_result.get("state_tax_liability", 0) or 0
            withholding = state_result.get("state_withholding", 0) or 0
            refund_or_owed = state_result.get("state_refund_or_owed", 0) or 0
        else:
            state_code = getattr(state_result, "state_code", "")
            taxable_income = getattr(state_result, "state_taxable_income", 0) or 0
            tax_liability = getattr(state_result, "state_tax_liability", 0) or 0
            withholding = getattr(state_result, "state_withholding", 0) or 0
            refund_or_owed = getattr(state_result, "state_refund_or_owed", 0) or 0

        return PDFSection(
            title="State Tax Summary",
            content=[
                {"type": "header", "text": f"State Tax Summary - {state_code}", "size": "large"},
                {"type": "line"},
                {"type": "row", "label": "State Taxable Income", "value": f"${taxable_income:,.2f}"},
                {"type": "row", "label": "State Tax", "value": f"${tax_liability:,.2f}"},
                {"type": "row", "label": "State Withholding", "value": f"${withholding:,.2f}"},
                {"type": "line"},
                {"type": "row",
                 "label": "State Refund" if refund_or_owed > 0 else "State Amount Owed",
                 "value": f"${abs(refund_or_owed):,.2f}",
                 "bold": True},
            ],
        )

    def _generate_w2_summary(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate W-2 summary."""
        income = tax_return.income
        w2_wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        fed_withholding = getattr(income, 'federal_withholding', 0) or 0

        return PDFSection(
            title="W-2 Summary",
            content=[
                {"type": "header", "text": "W-2 Wage Summary", "size": "large"},
                {"type": "line"},
                {"type": "row", "label": "Total W-2 Wages", "value": f"${w2_wages:,.2f}"},
                {"type": "row", "label": "Federal Tax Withheld", "value": f"${fed_withholding:,.2f}"},
            ],
        )

    def _generate_client_header(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate client summary header."""
        taxpayer = tax_return.taxpayer
        return PDFSection(
            title="",
            content=[
                {"type": "header", "text": "Your 2025 Tax Return Summary", "size": "large"},
                {"type": "text", "text": f"Prepared for: {getattr(taxpayer, 'first_name', '')} {getattr(taxpayer, 'last_name', '')}"},
                {"type": "text", "text": f"Date: {datetime.now().strftime('%B %d, %Y')}"},
            ],
        )

    def _generate_key_numbers(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate key numbers section."""
        result = tax_return.refund_or_owed or 0
        result_type = "Refund" if result > 0 else "Amount Owed"

        return PDFSection(
            title="Key Numbers",
            content=[
                {"type": "header", "text": "Key Numbers", "size": "medium"},
                {"type": "box", "content": [
                    {"label": result_type, "value": f"${abs(result):,.2f}", "highlight": True},
                    {"label": "Federal Tax", "value": f"${tax_return.tax_liability or 0:,.2f}"},
                    {"label": "Effective Rate", "value": f"{((tax_return.tax_liability or 0) / (tax_return.adjusted_gross_income or 1) * 100):.1f}%"},
                ]},
            ],
        )

    def _generate_income_breakdown(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate income breakdown."""
        income = tax_return.income

        items = []
        w2 = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        if w2 > 0:
            items.append({"label": "W-2 Wages", "value": f"${w2:,.2f}"})

        interest = getattr(income, 'interest_income', 0) or 0
        if interest > 0:
            items.append({"label": "Interest", "value": f"${interest:,.2f}"})

        dividends = getattr(income, 'dividend_income', 0) or 0
        if dividends > 0:
            items.append({"label": "Dividends", "value": f"${dividends:,.2f}"})

        se = getattr(income, 'self_employment_income', 0) or 0
        if se > 0:
            items.append({"label": "Self-Employment", "value": f"${se:,.2f}"})

        items.append({"label": "Total (AGI)", "value": f"${tax_return.adjusted_gross_income or 0:,.2f}", "bold": True})

        return PDFSection(
            title="Income",
            content=[
                {"type": "header", "text": "Income Breakdown", "size": "medium"},
                {"type": "list", "items": items},
            ],
        )

    def _generate_deduction_comparison(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate deduction comparison."""
        filing_status = tax_return.taxpayer.filing_status.value if hasattr(tax_return.taxpayer.filing_status, 'value') else str(tax_return.taxpayer.filing_status)

        standard_amounts = {
            "single": 15750,
            "married_joint": 31500,
            "married_separate": 15750,
            "head_of_household": 23625,
        }

        standard = standard_amounts.get(filing_status, 15750)
        itemized = tax_return.total_deduction if hasattr(tax_return, 'total_deduction') else standard
        deduction_type = getattr(tax_return, 'deduction_type', 'standard')

        return PDFSection(
            title="Deductions",
            content=[
                {"type": "header", "text": "Deduction Comparison", "size": "medium"},
                {"type": "row", "label": "Standard Deduction", "value": f"${standard:,.2f}"},
                {"type": "row", "label": "Your Itemized Deductions", "value": f"${itemized:,.2f}"},
                {"type": "text", "text": f"We used the {deduction_type} deduction - the higher amount - to reduce your taxes.", "style": "italic"},
            ],
        )

    def _generate_credits_summary(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate credits summary."""
        return PDFSection(
            title="Credits",
            content=[
                {"type": "header", "text": "Tax Credits", "size": "medium"},
                {"type": "text", "text": "Tax credits directly reduce your tax bill."},
            ],
        )

    def _generate_result_summary(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate refund/owed summary."""
        result = tax_return.refund_or_owed or 0

        if result > 0:
            return PDFSection(
                title="Your Refund",
                content=[
                    {"type": "header", "text": "Your Refund", "size": "medium", "color": "green"},
                    {"type": "text", "text": f"You're getting a refund of ${result:,.2f}!"},
                    {"type": "text", "text": "This is because your withholding and credits exceeded your tax liability."},
                ],
            )
        else:
            return PDFSection(
                title="Amount Owed",
                content=[
                    {"type": "header", "text": "Amount Owed", "size": "medium", "color": "red"},
                    {"type": "text", "text": f"You owe ${abs(result):,.2f} to the IRS."},
                    {"type": "text", "text": "Payment is due by April 15, 2026."},
                ],
            )

    def _generate_next_steps(self, tax_return: "TaxReturn") -> PDFSection:
        """Generate next steps."""
        result = tax_return.refund_or_owed or 0

        steps = [
            "Review this summary for accuracy",
            "Sign and date your return",
        ]

        if result > 0:
            steps.append("Choose direct deposit for fastest refund (8-21 days)")
        else:
            steps.append(f"Pay ${abs(result):,.2f} by April 15, 2026")

        steps.append("Keep copies of your return and supporting documents for 7 years")

        return PDFSection(
            title="Next Steps",
            content=[
                {"type": "header", "text": "Next Steps", "size": "medium"},
                {"type": "numbered_list", "items": steps},
            ],
        )

    def _render_to_text(self, sections: List[PDFSection]) -> str:
        """Render sections to text format (placeholder for PDF rendering)."""
        lines = []
        lines.append("=" * 80)
        lines.append("TAX RETURN - TAX YEAR 2025")
        lines.append("=" * 80)
        lines.append("")

        for section in sections:
            if section.title:
                lines.append("-" * 80)
                lines.append(section.title.upper())
                lines.append("-" * 80)

            for item in section.content:
                item_type = item.get("type", "text")

                if item_type == "header":
                    size = item.get("size", "medium")
                    if size == "large":
                        lines.append("")
                        lines.append(item["text"].upper())
                        lines.append("")
                    else:
                        lines.append(item["text"])

                elif item_type == "text":
                    lines.append(item["text"])

                elif item_type == "row":
                    label = item["label"]
                    value = item["value"]
                    bold = " *" if item.get("bold") else ""
                    lines.append(f"  {label:<40} {value:>20}{bold}")

                elif item_type == "line":
                    lines.append("-" * 60)

                elif item_type == "spacer":
                    lines.append("")

                elif item_type == "list":
                    for list_item in item["items"]:
                        bold = " *" if list_item.get("bold") else ""
                        lines.append(f"  - {list_item['label']}: {list_item['value']}{bold}")

                elif item_type == "numbered_list":
                    for i, list_item in enumerate(item["items"], 1):
                        lines.append(f"  {i}. {list_item}")

            if section.page_break_after:
                lines.append("\n" + "=" * 80 + "\n")

        return "\n".join(lines)

    def _needs_schedule_1(self, tax_return: "TaxReturn") -> bool:
        """Check if Schedule 1 is needed."""
        income = tax_return.income
        se = getattr(income, 'self_employment_income', 0) or 0
        return se > 0

    def _needs_schedule_2(self, tax_return: "TaxReturn") -> bool:
        """Check if Schedule 2 is needed."""
        return self._needs_schedule_1(tax_return)

    def _needs_schedule_3(self, tax_return: "TaxReturn") -> bool:
        """Check if Schedule 3 is needed."""
        return False  # Simplified

    def _is_itemizing(self, tax_return: "TaxReturn") -> bool:
        """Check if itemizing."""
        return getattr(tax_return, 'deduction_type', 'standard') == 'itemized'

    def _has_self_employment(self, tax_return: "TaxReturn") -> bool:
        """Check for self-employment."""
        income = tax_return.income
        se = getattr(income, 'self_employment_income', 0) or 0
        return se > 0

    def _mask_ssn(self, ssn: str) -> str:
        """Mask SSN."""
        if not ssn:
            return "XXX-XX-XXXX"
        cleaned = ssn.replace("-", "")
        if len(cleaned) >= 4:
            return f"XXX-XX-{cleaned[-4:]}"
        return "XXX-XX-XXXX"

    def _generate_filename(self, tax_return: "TaxReturn", doc_type: str) -> str:
        """Generate filename."""
        taxpayer = tax_return.taxpayer
        last_name = (getattr(taxpayer, 'last_name', 'taxpayer') or 'taxpayer').replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"{last_name}_2025_{doc_type}_{timestamp}.pdf"


class WorkpaperGenerator:
    """
    Generates detailed workpapers for professional review.

    Creates documentation showing all calculations and source data
    for CPA/EA review and audit trail purposes.
    """

    def generate_workpapers(
        self, tax_return: "TaxReturn", options: Optional[Dict[str, Any]] = None
    ) -> PDFDocument:
        """Generate detailed workpapers."""
        sections = []

        # Calculation summary
        sections.append(self._generate_calculation_summary(tax_return))

        # Income reconciliation
        sections.append(self._generate_income_reconciliation(tax_return))

        # Deduction detail
        sections.append(self._generate_deduction_detail(tax_return))

        # Credit calculations
        sections.append(self._generate_credit_calculations(tax_return))

        # Tax computation
        sections.append(self._generate_tax_computation(tax_return))

        text_content = self._render_sections(sections)

        return PDFDocument(
            filename=f"workpapers_{datetime.now().strftime('%Y%m%d')}.pdf",
            content=text_content.encode(),
            text_content=text_content,
            page_count=len(sections),
            generated_at=datetime.now().isoformat(),
            document_type="workpapers",
        )

    def _generate_calculation_summary(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Generate calculation summary."""
        return {
            "title": "Calculation Summary",
            "content": [
                f"AGI: ${tax_return.adjusted_gross_income or 0:,.2f}",
                f"Taxable Income: ${tax_return.taxable_income or 0:,.2f}",
                f"Tax Liability: ${tax_return.tax_liability or 0:,.2f}",
                f"Refund/Owed: ${tax_return.refund_or_owed or 0:,.2f}",
            ],
        }

    def _generate_income_reconciliation(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Generate income reconciliation."""
        income = tax_return.income
        lines = []

        w2 = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        if w2 > 0:
            lines.append(f"W-2 Wages: ${w2:,.2f}")

        interest = getattr(income, 'interest_income', 0) or 0
        if interest > 0:
            lines.append(f"Interest Income: ${interest:,.2f}")

        dividends = getattr(income, 'dividend_income', 0) or 0
        if dividends > 0:
            lines.append(f"Dividend Income: ${dividends:,.2f}")

        se = getattr(income, 'self_employment_income', 0) or 0
        if se > 0:
            lines.append(f"Self-Employment Income: ${se:,.2f}")

        lines.append(f"TOTAL: ${tax_return.adjusted_gross_income or 0:,.2f}")

        return {
            "title": "Income Reconciliation",
            "content": lines,
        }

    def _generate_deduction_detail(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Generate deduction detail."""
        deductions = tax_return.deductions
        lines = []

        mortgage = getattr(deductions, 'mortgage_interest', 0) or 0
        if mortgage > 0:
            lines.append(f"Mortgage Interest: ${mortgage:,.2f}")

        property_tax = getattr(deductions, 'property_taxes', 0) or 0
        if property_tax > 0:
            lines.append(f"Property Taxes: ${property_tax:,.2f}")

        charity = (getattr(deductions, 'charitable_cash', 0) or 0) + \
                  (getattr(deductions, 'charitable_noncash', 0) or 0)
        if charity > 0:
            lines.append(f"Charitable: ${charity:,.2f}")

        return {
            "title": "Deduction Detail",
            "content": lines if lines else ["Using standard deduction"],
        }

    def _generate_credit_calculations(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Generate credit calculations."""
        return {
            "title": "Credit Calculations",
            "content": ["See Form 1040 and schedules for credit details"],
        }

    def _generate_tax_computation(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Generate tax computation workpaper."""
        lines = [
            f"Taxable Income: ${tax_return.taxable_income or 0:,.2f}",
            f"Tax (from tables): ${tax_return.tax_liability or 0:,.2f}",
            f"Credits: (see Schedule 3)",
            f"Net Tax: ${tax_return.tax_liability or 0:,.2f}",
        ]

        return {
            "title": "Tax Computation",
            "content": lines,
        }

    def _render_sections(self, sections: List[Dict[str, Any]]) -> str:
        """Render sections to text."""
        lines = ["WORKPAPERS - TAX YEAR 2025", "=" * 60]

        for section in sections:
            lines.append("")
            lines.append(section["title"].upper())
            lines.append("-" * 40)
            for item in section["content"]:
                lines.append(f"  {item}")

        return "\n".join(lines)
