"""
Draft Tax Form PDF Generator

Generates professional draft IRS-style tax form PDFs using ReportLab.
Outputs Form 1040-like layouts with schedules and a clear DRAFT watermark.

This provides CPA-ready draft outputs that look professional and familiar
to tax professionals while clearly marked as drafts.
"""
from io import BytesIO
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.pdfgen import canvas


class DraftFormPDFGenerator:
    """
    Generates draft IRS-style tax form PDFs.

    Creates professional Form 1040 and schedule outputs with:
    - IRS-like form layout
    - Clear DRAFT watermark
    - Line-by-line breakdown
    - Supporting schedules
    - CPA review notes section
    """

    def __init__(self, tax_year: int = 2024):
        self.tax_year = tax_year
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles."""
        # Form title style
        self.styles.add(ParagraphStyle(
            'FormTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=6,
            textColor=colors.HexColor('#1a3a5f')
        ))

        # Form subtitle
        self.styles.add(ParagraphStyle(
            'FormSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            spaceAfter=12
        ))

        # Section header
        self.styles.add(ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#5387c1'),
            spaceBefore=12,
            spaceAfter=6,
            borderWidth=1,
            borderColor=colors.HexColor('#cbd5e0'),
            borderPadding=4
        ))

        # Line item style
        self.styles.add(ParagraphStyle(
            'LineItem',
            parent=self.styles['Normal'],
            fontSize=9,
            leading=12
        ))

        # Amount style
        self.styles.add(ParagraphStyle(
            'Amount',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=2  # Right align
        ))

        # Disclaimer
        self.styles.add(ParagraphStyle(
            'Disclaimer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            spaceBefore=20
        ))

    def _add_watermark(self, canvas_obj, doc):
        """Add DRAFT watermark to each page."""
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica-Bold', 60)
        canvas_obj.setFillColor(colors.Color(0.9, 0.9, 0.9))
        canvas_obj.translate(letter[0]/2, letter[1]/2)
        canvas_obj.rotate(45)
        canvas_obj.drawCentredString(0, 0, "DRAFT")
        canvas_obj.restoreState()

        # Add footer with page number and strong disclaimer
        canvas_obj.setFont('Helvetica-Bold', 8)
        canvas_obj.setFillColor(colors.red)
        page_num = canvas_obj.getPageNumber()
        canvas_obj.drawString(
            inch,
            0.5 * inch,
            f"DRAFT - NOT FOR FILING - CONSULT A CPA BEFORE FILING | Generated {datetime.now().strftime('%m/%d/%Y %I:%M %p')} | Page {page_num}"
        )

    def generate_form_1040(
        self,
        taxpayer_name: str,
        ssn: str = "XXX-XX-XXXX",
        filing_status: str = "Single",
        income_data: Dict[str, float] = None,
        deduction_data: Dict[str, float] = None,
        tax_data: Dict[str, float] = None,
        payment_data: Dict[str, float] = None
    ) -> bytes:
        """
        Generate a draft Form 1040 PDF.

        Args:
            taxpayer_name: Taxpayer's full name
            ssn: SSN (masked for privacy)
            filing_status: Filing status
            income_data: Income amounts by type
            deduction_data: Deduction amounts
            tax_data: Tax calculations
            payment_data: Payments and credits

        Returns:
            PDF bytes
        """
        income_data = income_data or {}
        deduction_data = deduction_data or {}
        tax_data = tax_data or {}
        payment_data = payment_data or {}

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=inch
        )

        story = []

        # Form header
        story.append(self._create_form_header("1040", "U.S. Individual Income Tax Return"))

        # Taxpayer info section
        story.append(self._create_section_header("Taxpayer Information"))
        story.append(self._create_info_table([
            ("Name", taxpayer_name),
            ("SSN", ssn),
            ("Filing Status", filing_status),
            ("Tax Year", str(self.tax_year))
        ]))
        story.append(Spacer(1, 12))

        # Income section
        story.append(self._create_section_header("Income"))
        income_lines = [
            ("1a", "Wages, salaries, tips (W-2)", income_data.get("wages", 0)),
            ("1b", "Household employee wages", income_data.get("household_wages", 0)),
            ("1c", "Tip income not on W-2", income_data.get("tip_income", 0)),
            ("2a", "Tax-exempt interest", income_data.get("tax_exempt_interest", 0)),
            ("2b", "Taxable interest", income_data.get("taxable_interest", 0)),
            ("3a", "Qualified dividends", income_data.get("qualified_dividends", 0)),
            ("3b", "Ordinary dividends", income_data.get("ordinary_dividends", 0)),
            ("4a", "IRA distributions", income_data.get("ira_distributions", 0)),
            ("4b", "Taxable IRA distributions", income_data.get("taxable_ira", 0)),
            ("5a", "Pensions and annuities", income_data.get("pensions", 0)),
            ("5b", "Taxable pensions", income_data.get("taxable_pensions", 0)),
            ("6a", "Social Security benefits", income_data.get("social_security", 0)),
            ("6b", "Taxable Social Security", income_data.get("taxable_ss", 0)),
            ("7", "Capital gain or (loss) [Schedule D]", income_data.get("capital_gains", 0)),
            ("8", "Other income [Schedule 1]", income_data.get("other_income", 0)),
            ("9", "Total income (add lines 1-8)", income_data.get("total_income", 0))
        ]
        story.append(self._create_form_lines_table(income_lines))

        # Adjustments section
        story.append(self._create_section_header("Adjusted Gross Income"))
        agi_lines = [
            ("10", "Adjustments to income [Schedule 1]", income_data.get("adjustments", 0)),
            ("11", "Adjusted Gross Income (AGI)", income_data.get("agi", 0))
        ]
        story.append(self._create_form_lines_table(agi_lines))

        # Deductions section
        story.append(self._create_section_header("Deductions"))
        deduction_lines = [
            ("12", "Standard deduction or itemized deductions", deduction_data.get("total_deduction", 0)),
            ("13", "Qualified business income deduction", deduction_data.get("qbi_deduction", 0)),
            ("14", "Add lines 12 and 13", deduction_data.get("total_deduction", 0) + deduction_data.get("qbi_deduction", 0)),
            ("15", "Taxable income (line 11 minus line 14)", tax_data.get("taxable_income", 0))
        ]
        story.append(self._create_form_lines_table(deduction_lines))

        # Tax computation section
        story.append(self._create_section_header("Tax and Credits"))
        tax_lines = [
            ("16", "Tax [see instructions]", tax_data.get("tax_before_credits", 0)),
            ("17", "Amount from Schedule 2, line 3", tax_data.get("schedule_2_tax", 0)),
            ("18", "Add lines 16 and 17", tax_data.get("total_tax_before_credits", 0)),
            ("19", "Child tax credit / other credits", tax_data.get("child_tax_credit", 0)),
            ("20", "Amount from Schedule 3, line 8", tax_data.get("schedule_3_credits", 0)),
            ("21", "Add lines 19 and 20", tax_data.get("total_credits", 0)),
            ("22", "Subtract line 21 from line 18", tax_data.get("tax_after_credits", 0)),
            ("23", "Other taxes [Schedule 2]", tax_data.get("other_taxes", 0)),
            ("24", "Total tax (add lines 22 and 23)", tax_data.get("total_tax", 0))
        ]
        story.append(self._create_form_lines_table(tax_lines))

        # Payments section
        story.append(self._create_section_header("Payments"))
        payment_lines = [
            ("25", "Federal tax withheld (W-2, 1099)", payment_data.get("withholding", 0)),
            ("26", "Estimated tax payments", payment_data.get("estimated_payments", 0)),
            ("27", "Refundable credits", payment_data.get("refundable_credits", 0)),
            ("28", "Total payments (add lines 25-27)", payment_data.get("total_payments", 0))
        ]
        story.append(self._create_form_lines_table(payment_lines))

        # Refund/Amount Due section
        story.append(self._create_section_header("Refund or Amount You Owe"))
        refund_owed = payment_data.get("total_payments", 0) - tax_data.get("total_tax", 0)
        if refund_owed >= 0:
            result_lines = [
                ("29", "Amount overpaid", abs(refund_owed)),
                ("30", "Amount to be refunded", abs(refund_owed))
            ]
        else:
            result_lines = [
                ("31", "Amount you owe", abs(refund_owed)),
                ("32", "Estimated tax penalty", payment_data.get("penalty", 0))
            ]
        story.append(self._create_form_lines_table(result_lines))

        # Summary box
        story.append(Spacer(1, 20))
        story.append(self._create_summary_box(
            total_income=income_data.get("total_income", 0),
            agi=income_data.get("agi", 0),
            taxable_income=tax_data.get("taxable_income", 0),
            total_tax=tax_data.get("total_tax", 0),
            total_payments=payment_data.get("total_payments", 0),
            refund_or_owed=refund_owed
        ))

        # Disclaimer - Strong legal warning
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            "<b>DRAFT - FOR REFERENCE ONLY - NOT FOR FILING</b><br/><br/>"
            "This document is a preliminary draft for informational purposes only. "
            "DO NOT FILE this document with the IRS or any state tax authority.<br/><br/>"
            "<b>IMPORTANT:</b> This platform provides tax information, NOT tax advice. "
            "All calculations are estimates based on general tax rules and may not reflect "
            "your actual tax situation. ALWAYS consult with a licensed CPA, Enrolled Agent, "
            "or tax attorney before making any tax decisions or filing any tax returns.<br/><br/>"
            "Generated by TaxAdvisor Pro - A tax information platform.",
            self.styles['Disclaimer']
        ))

        # Build PDF with watermark
        doc.build(story, onFirstPage=self._add_watermark, onLaterPages=self._add_watermark)

        buffer.seek(0)
        return buffer.getvalue()

    def _create_form_header(self, form_number: str, title: str) -> Table:
        """Create IRS-style form header."""
        header_data = [
            [
                Paragraph(f"<b>Form {form_number}</b>", self.styles['FormTitle']),
                Paragraph(f"<b>{title}</b>", self.styles['FormTitle'])
            ],
            [
                Paragraph("Department of the Treasury<br/>Internal Revenue Service", self.styles['FormSubtitle']),
                Paragraph(f"Tax Year {self.tax_year}", self.styles['FormSubtitle'])
            ]
        ]

        table = Table(header_data, colWidths=[1.5*inch, 5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#1a3a5f'))
        ]))
        return table

    def _create_section_header(self, title: str) -> Paragraph:
        """Create section header."""
        return Paragraph(f"<b>{title}</b>", self.styles['SectionHeader'])

    def _create_info_table(self, data: List[tuple]) -> Table:
        """Create taxpayer info table."""
        table_data = [[
            Paragraph(f"<b>{label}:</b>", self.styles['LineItem']),
            Paragraph(str(value), self.styles['LineItem'])
        ] for label, value in data]

        table = Table(table_data, colWidths=[1.5*inch, 4*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
        ]))
        return table

    def _create_form_lines_table(self, lines: List[tuple]) -> Table:
        """Create IRS form lines table."""
        table_data = []
        for line_num, description, amount in lines:
            table_data.append([
                Paragraph(f"<b>{line_num}</b>", self.styles['LineItem']),
                Paragraph(description, self.styles['LineItem']),
                Paragraph(self._format_amount(amount), self.styles['Amount'])
            ])

        table = Table(table_data, colWidths=[0.5*inch, 4.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOX', (2, 0), (2, -1), 1, colors.HexColor('#cbd5e0')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f7fafc'))
        ]))
        return table

    def _create_summary_box(
        self,
        total_income: float,
        agi: float,
        taxable_income: float,
        total_tax: float,
        total_payments: float,
        refund_or_owed: float
    ) -> Table:
        """Create summary box with key figures."""
        if refund_or_owed >= 0:
            result_label = "REFUND"
            result_color = colors.HexColor('#276749')  # Green
        else:
            result_label = "AMOUNT DUE"
            result_color = colors.HexColor('#c53030')  # Red

        summary_data = [
            [Paragraph("<b>SUMMARY</b>", self.styles['SectionHeader']), "", ""],
            ["Total Income", "", self._format_amount(total_income)],
            ["Adjusted Gross Income", "", self._format_amount(agi)],
            ["Taxable Income", "", self._format_amount(taxable_income)],
            ["Total Tax", "", self._format_amount(total_tax)],
            ["Total Payments", "", self._format_amount(total_payments)],
            [Paragraph(f"<b>{result_label}</b>", ParagraphStyle('Result', textColor=result_color, fontSize=12)),
             "",
             Paragraph(f"<b>{self._format_amount(abs(refund_or_owed))}</b>",
                       ParagraphStyle('ResultAmount', textColor=result_color, fontSize=14, alignment=2))]
        ]

        table = Table(summary_data, colWidths=[3*inch, 1*inch, 2*inch])
        table.setStyle(TableStyle([
            ('SPAN', (0, 0), (2, 0)),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2b6cb0')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ebf8ff')),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#bee3f8'))
        ]))
        return table

    def _format_amount(self, amount: float) -> str:
        """Format amount as currency."""
        if amount is None:
            return "$0"
        if amount < 0:
            return f"(${abs(amount):,.0f})"
        return f"${amount:,.0f}"

    def generate_schedule_summary(
        self,
        schedule_name: str,
        schedule_description: str,
        lines: List[tuple]
    ) -> bytes:
        """
        Generate a draft schedule PDF.

        Args:
            schedule_name: Schedule identifier (e.g., "A", "D", "E")
            schedule_description: Schedule title
            lines: List of (line_num, description, amount) tuples

        Returns:
            PDF bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=inch
        )

        story = []

        # Schedule header
        story.append(self._create_form_header(
            f"Schedule {schedule_name}",
            schedule_description
        ))
        story.append(Spacer(1, 20))

        # Lines table
        story.append(self._create_form_lines_table(lines))

        # Disclaimer - Strong legal warning
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            "<b>DRAFT - FOR REFERENCE ONLY - NOT FOR FILING</b><br/>"
            "This is a preliminary estimate. Consult a licensed CPA before filing.",
            self.styles['Disclaimer']
        ))

        doc.build(story, onFirstPage=self._add_watermark, onLaterPages=self._add_watermark)

        buffer.seek(0)
        return buffer.getvalue()


class DraftReturnPackage:
    """
    Generates a complete draft tax return package including
    Form 1040 and all required schedules.
    """

    def __init__(self, tax_return, calculation_breakdown):
        """
        Initialize with tax return data and calculation results.

        Args:
            tax_return: TaxReturn model instance
            calculation_breakdown: CalculationBreakdown from engine
        """
        self.tax_return = tax_return
        self.breakdown = calculation_breakdown
        self.generator = DraftFormPDFGenerator(
            tax_year=getattr(tax_return, 'tax_year', 2024)
        )

    def generate_form_1040(self) -> bytes:
        """Generate Form 1040 PDF from tax return data."""
        tr = self.tax_return
        bd = self.breakdown

        # Extract taxpayer info
        taxpayer_name = f"{tr.taxpayer.first_name} {tr.taxpayer.last_name}"
        ssn = tr.taxpayer.ssn if tr.taxpayer.ssn else "XXX-XX-XXXX"
        filing_status = tr.taxpayer.filing_status.value if tr.taxpayer.filing_status else "single"

        # Build income data
        total_wages = sum(w2.wages for w2 in tr.income.w2_forms) if tr.income.w2_forms else 0

        income_data = {
            "wages": total_wages,
            "taxable_interest": getattr(tr.income, 'interest_income', 0) or 0,
            "ordinary_dividends": getattr(tr.income, 'dividend_income', 0) or 0,
            "qualified_dividends": getattr(tr.income, 'qualified_dividends', 0) or 0,
            "capital_gains": getattr(bd, 'capital_gain_loss', 0) or 0,
            "other_income": getattr(tr.income, 'other_income', 0) or 0,
            "total_income": getattr(bd, 'gross_income', 0) or 0,
            "adjustments": getattr(bd, 'adjustments_to_income', 0) or 0,
            "agi": getattr(bd, 'agi', 0) or 0
        }

        # Build deduction data
        deduction_data = {
            "total_deduction": getattr(bd, 'deduction_amount', 0) or 0,
            "qbi_deduction": getattr(bd, 'qbi_deduction', 0) or 0
        }

        # Build tax data
        tax_data = {
            "taxable_income": getattr(bd, 'taxable_income', 0) or 0,
            "tax_before_credits": getattr(bd, 'tax_liability', 0) or 0,
            "total_tax_before_credits": getattr(bd, 'tax_liability', 0) or 0,
            "child_tax_credit": getattr(bd, 'child_tax_credit', 0) or 0,
            "total_credits": getattr(bd, 'total_credits', 0) or 0,
            "tax_after_credits": getattr(bd, 'tax_after_credits', 0) or 0,
            "total_tax": getattr(bd, 'total_tax', 0) or 0
        }

        # Build payment data
        total_withholding = sum(w2.federal_tax_withheld for w2 in tr.income.w2_forms) if tr.income.w2_forms else 0

        payment_data = {
            "withholding": total_withholding,
            "estimated_payments": getattr(tr, 'estimated_payments', 0) or 0,
            "total_payments": getattr(bd, 'total_payments', 0) or total_withholding
        }

        return self.generator.generate_form_1040(
            taxpayer_name=taxpayer_name,
            ssn=ssn,
            filing_status=filing_status,
            income_data=income_data,
            deduction_data=deduction_data,
            tax_data=tax_data,
            payment_data=payment_data
        )

    def get_required_schedules(self) -> List[str]:
        """Determine which schedules are required."""
        schedules = []
        tr = self.tax_return

        # Schedule A - Itemized Deductions
        if getattr(tr.deductions, 'itemized', None):
            schedules.append("A")

        # Schedule B - Interest and Dividends
        if (getattr(tr.income, 'interest_income', 0) or 0) > 1500 or \
           (getattr(tr.income, 'dividend_income', 0) or 0) > 1500:
            schedules.append("B")

        # Schedule C - Business Income
        if (getattr(tr.income, 'business_income', 0) or 0) > 0:
            schedules.append("C")

        # Schedule D - Capital Gains
        if getattr(tr.income, 'capital_gains', None) or \
           getattr(tr.income, 'securities_portfolio', None):
            schedules.append("D")

        # Schedule E - Rental Income
        if getattr(tr.income, 'rental_income', 0) or 0 > 0 or \
           getattr(tr.income, 'k1_forms', None):
            schedules.append("E")

        # Schedule SE - Self-Employment Tax
        if (getattr(tr.income, 'self_employment_income', 0) or 0) > 400:
            schedules.append("SE")

        return schedules
