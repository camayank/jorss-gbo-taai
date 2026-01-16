"""
Big4-Level Professional Tax Computation Statement Generator

Generates professional-grade tax computation statements suitable for:
- Client presentation and review
- Audit documentation
- Professional firm workpapers
- IRS examination support

All assumptions are tracked and disclosed in footnotes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import json

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.engine import CalculationBreakdown


class AssumptionCategory(Enum):
    """Categories of assumptions made during computation."""
    FILING_STATUS = "Filing Status"
    INCOME = "Income"
    DEDUCTIONS = "Deductions"
    CREDITS = "Credits"
    ELECTIONS = "Elections"
    TIMING = "Timing"
    VALUATION = "Valuation"
    DEPENDENCY = "Dependency"
    ALLOCATION = "Allocation"
    CARRYFORWARD = "Carryforward"


@dataclass
class Assumption:
    """Represents a single assumption made during computation."""
    category: AssumptionCategory
    description: str
    impact: str  # Financial impact description
    reference: str  # IRS/IRC reference
    confidence: str  # "High", "Medium", "Low"
    requires_documentation: bool = False
    footnote_number: int = 0


@dataclass
class ComputationLine:
    """A single line in the computation statement."""
    line_number: str
    description: str
    amount: float
    form_reference: str = ""  # e.g., "Form 1040, Line 1a"
    schedule_reference: str = ""  # e.g., "Schedule C, Line 31"
    is_subtotal: bool = False
    is_total: bool = False
    indent_level: int = 0
    footnote_refs: List[int] = field(default_factory=list)
    supporting_detail: Optional[str] = None


@dataclass
class ComputationSection:
    """A section of the computation statement."""
    title: str
    lines: List[ComputationLine] = field(default_factory=list)
    subtotal: Optional[float] = None
    notes: List[str] = field(default_factory=list)


class TaxComputationStatement:
    """
    Professional-grade tax computation statement generator.

    Produces Big4-level computation statements with:
    - Complete income reconciliation
    - Detailed deduction analysis
    - Tax calculation breakdown
    - Credit application
    - Assumptions and footnotes
    - Draft return summary
    """

    def __init__(
        self,
        tax_return: "TaxReturn",
        breakdown: "CalculationBreakdown",
        preparer_name: str = "",
        firm_name: str = "",
    ):
        self.tax_return = tax_return
        self.breakdown = breakdown
        self.preparer_name = preparer_name
        self.firm_name = firm_name
        self.assumptions: List[Assumption] = []
        self.footnote_counter = 0
        self.sections: List[ComputationSection] = []
        self._generated_at = datetime.now()

    def generate(self) -> Dict[str, Any]:
        """
        Generate complete computation statement.

        Returns dictionary with all sections and supporting data.
        """
        # Track assumptions as we build the statement
        self._identify_assumptions()

        # Build all sections
        header = self._build_header()
        income_section = self._build_income_section()
        adjustments_section = self._build_adjustments_section()
        deductions_section = self._build_deductions_section()
        tax_computation = self._build_tax_computation_section()
        credits_section = self._build_credits_section()
        other_taxes = self._build_other_taxes_section()
        payments_section = self._build_payments_section()
        summary_section = self._build_summary_section()

        self.sections = [
            income_section,
            adjustments_section,
            deductions_section,
            tax_computation,
            credits_section,
            other_taxes,
            payments_section,
            summary_section,
        ]

        # Build footnotes from assumptions
        footnotes = self._build_footnotes()

        # Build validation notes
        validation = self._build_validation_notes()

        return {
            "header": header,
            "sections": [self._section_to_dict(s) for s in self.sections],
            "assumptions": [self._assumption_to_dict(a) for a in self.assumptions],
            "footnotes": footnotes,
            "validation": validation,
            "preparer_notes": self._build_preparer_notes(),
            "metadata": {
                "generated_at": self._generated_at.isoformat(),
                "tax_year": self.tax_return.tax_year,
                "preparer": self.preparer_name,
                "firm": self.firm_name,
                "software_version": "Jorss-Gbo v2025.1",
            }
        }

    def _identify_assumptions(self) -> None:
        """Identify all assumptions made during computation."""
        tr = self.tax_return
        bd = self.breakdown

        # Filing Status Assumptions
        filing_status = tr.taxpayer.filing_status.value if hasattr(tr.taxpayer.filing_status, 'value') else str(tr.taxpayer.filing_status)

        if filing_status == "head_of_household":
            self._add_assumption(
                AssumptionCategory.FILING_STATUS,
                "Taxpayer qualifies as Head of Household",
                "HOH filing status provides lower tax rates and higher standard deduction",
                "IRC §2(b); Pub. 501",
                "Medium",
                requires_documentation=True
            )

        if filing_status == "qualifying_widow":
            self._add_assumption(
                AssumptionCategory.FILING_STATUS,
                "Taxpayer qualifies as Qualifying Surviving Spouse",
                "Uses MFJ rates and standard deduction for 2 years after spouse's death",
                "IRC §2(a); Pub. 501",
                "Medium",
                requires_documentation=True
            )

        # Income Assumptions
        income = tr.income

        # W-2 wage assumption
        if hasattr(income, 'w2_forms') and income.w2_forms:
            self._add_assumption(
                AssumptionCategory.INCOME,
                f"W-2 wages reported as provided ({len(income.w2_forms)} form(s))",
                "Wages, salaries, and tips per W-2 Box 1",
                "Form 1040, Line 1a; IRC §61(a)(1)",
                "High"
            )

        # Self-employment income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 0:
            self._add_assumption(
                AssumptionCategory.INCOME,
                "Self-employment income reported on cash basis",
                f"Net profit ${se_income:,.2f} subject to SE tax",
                "Schedule C; IRC §1402",
                "Medium",
                requires_documentation=True
            )

        # Capital gains assumption
        if bd.net_long_term_gain_loss != 0 or bd.net_short_term_gain_loss != 0:
            self._add_assumption(
                AssumptionCategory.INCOME,
                "Capital gains/losses computed using FIFO cost basis",
                "Cost basis method affects gain/loss recognition",
                "IRC §1012; Reg. §1.1012-1",
                "Medium"
            )

        # Capital loss carryforward
        if bd.new_st_loss_carryforward > 0 or bd.new_lt_loss_carryforward > 0:
            total_cf = bd.new_st_loss_carryforward + bd.new_lt_loss_carryforward
            self._add_assumption(
                AssumptionCategory.CARRYFORWARD,
                f"Capital loss carryforward of ${total_cf:,.2f} to future years",
                "Losses exceeding $3,000 annual limit carried forward",
                "IRC §1211(b); IRC §1212(b)",
                "High"
            )

        # Social Security assumption
        ss_benefits = getattr(income, 'social_security_benefits', 0) or 0
        if ss_benefits > 0:
            self._add_assumption(
                AssumptionCategory.INCOME,
                "Social Security benefits taxable portion computed using IRS worksheet",
                f"Benefits of ${ss_benefits:,.2f} subject to up to 85% taxation",
                "IRC §86; Pub. 915; Form 1040, Line 6b",
                "High"
            )

        # Deduction Assumptions
        deductions = tr.deductions

        if bd.deduction_type == "standard":
            self._add_assumption(
                AssumptionCategory.DEDUCTIONS,
                "Standard deduction elected (greater than itemized)",
                f"Standard deduction of ${bd.deduction_amount:,.2f} applied",
                f"IRC §63(c); Form 1040, Line 12",
                "High"
            )
        else:
            self._add_assumption(
                AssumptionCategory.DEDUCTIONS,
                "Itemized deductions elected (greater than standard)",
                f"Itemized deductions of ${bd.deduction_amount:,.2f} applied",
                "Schedule A; IRC §63(d)",
                "High"
            )

            # SALT cap assumption - access itemized deduction fields
            itemized = getattr(deductions, 'itemized', None)
            if itemized:
                salt = (getattr(itemized, 'state_local_income_tax', 0) or 0) + \
                       (getattr(itemized, 'state_local_sales_tax', 0) or 0) + \
                       (getattr(itemized, 'real_estate_tax', 0) or 0) + \
                       (getattr(itemized, 'personal_property_tax', 0) or 0)
                if salt > 10000:
                    self._add_assumption(
                        AssumptionCategory.DEDUCTIONS,
                        f"SALT deduction limited to $10,000 (uncapped: ${salt:,.2f})",
                        f"TCJA limits SALT deduction; ${salt - 10000:,.2f} disallowed",
                        "IRC §164(b)(6); TCJA §11042",
                        "High"
                    )

        # Mortgage interest limitation - access itemized deduction fields
        itemized = getattr(deductions, 'itemized', None)
        mortgage_principal = getattr(itemized, 'mortgage_principal', 0) if itemized else 0
        if mortgage_principal > 750000:
            self._add_assumption(
                AssumptionCategory.DEDUCTIONS,
                f"Mortgage interest limited due to acquisition debt over $750,000",
                "Interest proportionally reduced for debt exceeding TCJA limit",
                "IRC §163(h)(3); TCJA §11043; Pub. 936",
                "High"
            )

        # QBI Deduction
        if bd.qbi_deduction > 0:
            self._add_assumption(
                AssumptionCategory.DEDUCTIONS,
                f"Qualified Business Income deduction of ${bd.qbi_deduction:,.2f}",
                "20% of QBI subject to taxable income limitation",
                "IRC §199A; Form 8995/8995-A",
                "Medium"
            )

        # Credit Assumptions
        credits_dict = bd.credit_breakdown or {}

        if credits_dict.get('child_tax_credit', 0) > 0:
            self._add_assumption(
                AssumptionCategory.CREDITS,
                "Child Tax Credit claimed for qualifying children",
                "Dependent meets QC tests: relationship, age, residency, support",
                "IRC §24; Pub. 972; Schedule 8812",
                "Medium",
                requires_documentation=True
            )

        if credits_dict.get('earned_income_credit', 0) > 0:
            self._add_assumption(
                AssumptionCategory.CREDITS,
                "Earned Income Tax Credit claimed",
                "Taxpayer meets earned income, AGI, and investment income limits",
                "IRC §32; Pub. 596; Schedule EIC",
                "Medium",
                requires_documentation=True
            )

        # AMT assumption
        if bd.alternative_minimum_tax > 0:
            self._add_assumption(
                AssumptionCategory.ELECTIONS,
                f"Alternative Minimum Tax applies: ${bd.alternative_minimum_tax:,.2f}",
                "Regular tax below TMT; SALT addback primary preference item",
                "IRC §55-59; Form 6251",
                "High"
            )

        # Estimated tax penalty
        if bd.estimated_tax_penalty > 0:
            self._add_assumption(
                AssumptionCategory.TIMING,
                f"Estimated tax underpayment penalty: ${bd.estimated_tax_penalty:,.2f}",
                "Safe harbor test not met; 8% annual rate applied",
                "IRC §6654; Form 2210; Pub. 505",
                "High"
            )
        elif not bd.safe_harbor_met:
            self._add_assumption(
                AssumptionCategory.TIMING,
                "Estimated tax underpayment under $1,000 threshold",
                "No penalty assessed due to de minimis underpayment",
                "IRC §6654(e)(1)",
                "High"
            )

    def _add_assumption(
        self,
        category: AssumptionCategory,
        description: str,
        impact: str,
        reference: str,
        confidence: str,
        requires_documentation: bool = False
    ) -> int:
        """Add an assumption and return its footnote number."""
        self.footnote_counter += 1
        assumption = Assumption(
            category=category,
            description=description,
            impact=impact,
            reference=reference,
            confidence=confidence,
            requires_documentation=requires_documentation,
            footnote_number=self.footnote_counter
        )
        self.assumptions.append(assumption)
        return self.footnote_counter

    def _build_header(self) -> Dict[str, Any]:
        """Build computation statement header."""
        tp = self.tax_return.taxpayer
        filing_status = tp.filing_status.value if hasattr(tp.filing_status, 'value') else str(tp.filing_status)

        status_display = {
            "single": "Single",
            "married_joint": "Married Filing Jointly",
            "married_separate": "Married Filing Separately",
            "head_of_household": "Head of Household",
            "qualifying_widow": "Qualifying Surviving Spouse"
        }.get(filing_status, filing_status)

        return {
            "title": "COMPUTATION OF FEDERAL INCOME TAX",
            "subtitle": f"Tax Year {self.tax_return.tax_year}",
            "taxpayer": {
                "name": f"{tp.first_name or ''} {tp.last_name or ''}".strip() or "Taxpayer",
                "ssn_masked": f"XXX-XX-{(tp.ssn or '')[-4:]}" if tp.ssn else "XXX-XX-XXXX",
                "filing_status": status_display,
            },
            "firm": self.firm_name or "Tax Preparation Services",
            "preparer": self.preparer_name or "Tax Professional",
            "date_prepared": self._generated_at.strftime("%B %d, %Y"),
            "disclaimer": (
                "DRAFT - FOR REVIEW PURPOSES ONLY. "
                "This computation is based on information provided and is subject to change. "
                "Final return should be reviewed for accuracy before filing."
            )
        }

    def _build_income_section(self) -> ComputationSection:
        """Build gross income computation section."""
        section = ComputationSection(title="PART I - GROSS INCOME")
        income = self.tax_return.income
        bd = self.breakdown

        line_num = 1

        # Wages, Salaries, Tips
        wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        if wages > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Wages, salaries, tips, etc.",
                amount=wages,
                form_reference="Form 1040, Line 1a",
                schedule_reference="W-2 Box 1"
            ))
            line_num += 1

        # Interest Income
        interest = getattr(income, 'interest_income', 0) or 0
        tax_exempt_int = getattr(income, 'tax_exempt_interest', 0) or 0
        if interest > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Taxable interest income",
                amount=interest,
                form_reference="Form 1040, Line 2b",
                schedule_reference="Schedule B, Part I"
            ))
            line_num += 1
        if tax_exempt_int > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Tax-exempt interest (informational)",
                amount=tax_exempt_int,
                form_reference="Form 1040, Line 2a",
                supporting_detail="Not included in taxable income"
            ))
            line_num += 1

        # Dividend Income
        ord_div = getattr(income, 'ordinary_dividends', 0) or 0
        qual_div = getattr(income, 'qualified_dividends', 0) or 0
        if ord_div > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Ordinary dividends",
                amount=ord_div,
                form_reference="Form 1040, Line 3b",
                schedule_reference="Schedule B, Part II"
            ))
            line_num += 1
        if qual_div > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="  Qualified dividends (preferential rate)",
                amount=qual_div,
                form_reference="Form 1040, Line 3a",
                indent_level=1,
                supporting_detail="Taxed at 0%/15%/20% preferential rates"
            ))
            line_num += 1

        # Capital Gains/Losses
        net_st = bd.net_short_term_gain_loss
        net_lt = bd.net_long_term_gain_loss
        cap_loss_ded = bd.capital_loss_deduction

        if net_st != 0 or net_lt != 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Net short-term capital gain/(loss)",
                amount=net_st,
                form_reference="Schedule D, Line 7",
            ))
            line_num += 1
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Net long-term capital gain/(loss)",
                amount=net_lt,
                form_reference="Schedule D, Line 15",
            ))
            line_num += 1

            if cap_loss_ded > 0:
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}",
                    description="Capital loss deduction (limited to $3,000)",
                    amount=-cap_loss_ded,
                    form_reference="Form 1040, Line 7",
                    supporting_detail="IRC §1211(b) - excess carried forward"
                ))
                line_num += 1

        # Self-Employment Income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0
        if se_income > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Business income (Schedule C)",
                amount=se_income - se_expenses,
                form_reference="Form 1040, Line 8",
                schedule_reference="Schedule C, Line 31"
            ))
            line_num += 1

        # K-1 Income
        if bd.k1_ordinary_income != 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Schedule K-1 ordinary income",
                amount=bd.k1_ordinary_income,
                form_reference="Schedule E, Part II",
                schedule_reference="K-1 Box 1/2/3"
            ))
            line_num += 1

        # Rental Income
        rental = getattr(income, 'rental_income', 0) or 0
        rental_exp = getattr(income, 'rental_expenses', 0) or 0
        if rental > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Rental real estate income/(loss)",
                amount=rental - rental_exp,
                form_reference="Form 1040, Line 8",
                schedule_reference="Schedule E, Part I"
            ))
            line_num += 1

        # Retirement Income
        retirement = getattr(income, 'retirement_income', 0) or 0
        if retirement > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="IRA distributions (taxable amount)",
                amount=retirement,
                form_reference="Form 1040, Lines 4a/4b"
            ))
            line_num += 1

        # Social Security Benefits
        ss_benefits = getattr(income, 'social_security_benefits', 0) or 0
        if ss_benefits > 0:
            # Calculate taxable portion based on breakdown
            # Typically shown in breakdown as part of ordinary income
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Social Security benefits (gross)",
                amount=ss_benefits,
                form_reference="Form 1040, Line 6a",
                supporting_detail="See taxable portion calculation below"
            ))
            line_num += 1

        # Gambling Income
        if bd.gambling_income > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Gambling winnings",
                amount=bd.gambling_income,
                form_reference="Form 1040, Line 8",
                schedule_reference="W-2G Box 1"
            ))
            line_num += 1

        # Other Income
        other_income = getattr(income, 'other_income', 0) or 0
        if other_income > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Other income",
                amount=other_income,
                form_reference="Form 1040, Line 8",
                schedule_reference="Schedule 1, Line 8z"
            ))
            line_num += 1

        # Gross Income Total
        section.lines.append(ComputationLine(
            line_number="",
            description="TOTAL GROSS INCOME",
            amount=bd.gross_income,
            form_reference="Form 1040, Line 9",
            is_total=True
        ))

        section.subtotal = bd.gross_income
        return section

    def _build_adjustments_section(self) -> ComputationSection:
        """Build adjustments to income section."""
        section = ComputationSection(title="PART II - ADJUSTMENTS TO INCOME (Above-the-Line)")
        deductions = self.tax_return.deductions
        bd = self.breakdown

        line_num = 1
        total_adj = 0.0

        # Educator expenses
        educator = getattr(deductions, 'educator_expenses', 0) or 0
        if educator > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Educator expenses (up to $300)",
                amount=educator,
                form_reference="Schedule 1, Line 11"
            ))
            total_adj += educator
            line_num += 1

        # HSA deduction
        hsa = getattr(deductions, 'hsa_contributions', 0) or 0
        if hsa > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Health savings account deduction",
                amount=hsa,
                form_reference="Schedule 1, Line 13",
                schedule_reference="Form 8889"
            ))
            total_adj += hsa
            line_num += 1

        # SE tax deduction (50% of SE tax)
        se_breakdown = bd.se_tax_breakdown or {}
        se_deduction = se_breakdown.get('se_tax_deduction', 0)
        if se_deduction > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Deductible part of self-employment tax",
                amount=se_deduction,
                form_reference="Schedule 1, Line 15",
                schedule_reference="Schedule SE, Line 13"
            ))
            total_adj += se_deduction
            line_num += 1

        # SE health insurance
        se_health = getattr(deductions, 'self_employed_health_insurance', 0) or 0
        if se_health > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Self-employed health insurance deduction",
                amount=se_health,
                form_reference="Schedule 1, Line 17"
            ))
            total_adj += se_health
            line_num += 1

        # SEP/SIMPLE/qualified plans
        sep = getattr(deductions, 'sep_contributions', 0) or 0
        if sep > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Self-employed SEP, SIMPLE, and qualified plans",
                amount=sep,
                form_reference="Schedule 1, Line 16"
            ))
            total_adj += sep
            line_num += 1

        # IRA deduction
        ira = getattr(deductions, 'ira_contributions', 0) or 0
        if ira > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="IRA deduction",
                amount=ira,
                form_reference="Schedule 1, Line 20",
                supporting_detail="Subject to MAGI phaseout if covered by employer plan"
            ))
            total_adj += ira
            line_num += 1

        # Student loan interest
        student_loan = getattr(deductions, 'student_loan_interest', 0) or 0
        if student_loan > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Student loan interest deduction (up to $2,500)",
                amount=student_loan,
                form_reference="Schedule 1, Line 21"
            ))
            total_adj += student_loan
            line_num += 1

        # Other adjustments
        other_adj = getattr(deductions, 'other_adjustments', 0) or 0
        if other_adj > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Other adjustments",
                amount=other_adj,
                form_reference="Schedule 1, Line 26"
            ))
            total_adj += other_adj
            line_num += 1

        # Total Adjustments
        section.lines.append(ComputationLine(
            line_number="",
            description="TOTAL ADJUSTMENTS TO INCOME",
            amount=bd.adjustments_to_income,
            form_reference="Schedule 1, Line 26",
            is_total=True
        ))

        # AGI Calculation
        section.lines.append(ComputationLine(
            line_number="",
            description="",
            amount=0,
            is_subtotal=False
        ))
        section.lines.append(ComputationLine(
            line_number="",
            description="ADJUSTED GROSS INCOME (AGI)",
            amount=bd.agi,
            form_reference="Form 1040, Line 11",
            is_total=True,
            supporting_detail=f"Gross Income ${bd.gross_income:,.2f} less Adjustments ${bd.adjustments_to_income:,.2f}"
        ))

        section.subtotal = bd.agi
        return section

    def _build_deductions_section(self) -> ComputationSection:
        """Build deductions from AGI section."""
        section = ComputationSection(title="PART III - DEDUCTIONS FROM AGI")
        deductions = self.tax_return.deductions
        bd = self.breakdown

        line_num = 1

        if bd.deduction_type == "standard":
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Standard deduction",
                amount=bd.deduction_amount,
                form_reference="Form 1040, Line 12",
                supporting_detail="Standard deduction elected as greater than itemized"
            ))
        else:
            # Itemized deductions breakdown
            section.notes.append("Schedule A - Itemized Deductions")

            # Medical expenses
            medical = getattr(deductions, 'medical_expenses', 0) or 0
            if medical > 0:
                floor = bd.agi * 0.075
                deductible = max(0, medical - floor)
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}a",
                    description="Medical and dental expenses",
                    amount=medical,
                    form_reference="Schedule A, Line 1",
                    indent_level=1
                ))
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}b",
                    description=f"  Less: 7.5% AGI floor (${floor:,.2f})",
                    amount=-floor,
                    form_reference="Schedule A, Line 3",
                    indent_level=2
                ))
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}c",
                    description="  Deductible medical expenses",
                    amount=deductible,
                    form_reference="Schedule A, Line 4",
                    indent_level=2,
                    is_subtotal=True
                ))
                line_num += 1

            # SALT (with $10k cap) - access itemized deduction fields
            itemized = getattr(deductions, 'itemized', None)
            salt_income = getattr(itemized, 'state_local_income_tax', 0) if itemized else 0
            salt_sales = getattr(itemized, 'state_local_sales_tax', 0) if itemized else 0
            real_estate = getattr(itemized, 'real_estate_tax', 0) if itemized else 0
            personal_prop = getattr(itemized, 'personal_property_tax', 0) if itemized else 0
            total_salt = salt_income + salt_sales + real_estate + personal_prop

            if total_salt > 0:
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}",
                    description="State and local taxes (SALT):",
                    amount=0,
                    indent_level=1
                ))
                if salt_income > 0:
                    section.lines.append(ComputationLine(
                        line_number="",
                        description="  State/local income taxes",
                        amount=salt_income,
                        form_reference="Schedule A, Line 5a",
                        indent_level=2
                    ))
                if real_estate > 0:
                    section.lines.append(ComputationLine(
                        line_number="",
                        description="  Real estate taxes",
                        amount=real_estate,
                        form_reference="Schedule A, Line 5b",
                        indent_level=2
                    ))
                if personal_prop > 0:
                    section.lines.append(ComputationLine(
                        line_number="",
                        description="  Personal property taxes",
                        amount=personal_prop,
                        form_reference="Schedule A, Line 5c",
                        indent_level=2
                    ))

                capped_salt = min(total_salt, 10000)
                section.lines.append(ComputationLine(
                    line_number="",
                    description=f"  SALT deduction (capped at $10,000)",
                    amount=capped_salt,
                    form_reference="Schedule A, Line 5e",
                    indent_level=2,
                    is_subtotal=True,
                    supporting_detail=f"Total ${total_salt:,.2f}; disallowed ${max(0, total_salt-10000):,.2f}" if total_salt > 10000 else None
                ))
                line_num += 1

            # Mortgage interest - access itemized deduction fields
            itemized = getattr(deductions, 'itemized', None)
            mortgage_int = getattr(itemized, 'mortgage_interest', 0) if itemized else 0
            points = getattr(itemized, 'points_paid', 0) if itemized else 0
            if mortgage_int > 0 or points > 0:
                filing_status = self.tax_return.taxpayer.filing_status.value if hasattr(self.tax_return.taxpayer.filing_status, 'value') else str(self.tax_return.taxpayer.filing_status)
                limited = itemized.get_limited_mortgage_interest(filing_status) if itemized and hasattr(itemized, 'get_limited_mortgage_interest') else mortgage_int + points
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}",
                    description="Home mortgage interest and points",
                    amount=limited,
                    form_reference="Schedule A, Lines 8a-8c",
                    supporting_detail="Limited per TCJA $750k debt ceiling" if limited < (mortgage_int + points) else None
                ))
                line_num += 1

            # Charitable contributions - access itemized deduction fields
            itemized = getattr(deductions, 'itemized', None)
            charity_cash = getattr(itemized, 'charitable_cash', 0) if itemized else 0
            charity_noncash = getattr(itemized, 'charitable_non_cash', 0) if itemized else 0
            total_charity = charity_cash + charity_noncash
            if total_charity > 0:
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}",
                    description="Charitable contributions",
                    amount=total_charity,
                    form_reference="Schedule A, Lines 11-14"
                ))
                line_num += 1

            # Gambling losses
            gambling_loss = bd.gambling_losses_deducted
            if gambling_loss > 0:
                section.lines.append(ComputationLine(
                    line_number=f"{line_num}",
                    description="Gambling losses (limited to winnings)",
                    amount=gambling_loss,
                    form_reference="Schedule A, Line 16",
                    supporting_detail=f"Limited to gambling income of ${bd.gambling_income:,.2f}"
                ))
                line_num += 1

            # Total itemized
            section.lines.append(ComputationLine(
                line_number="",
                description="Total itemized deductions",
                amount=bd.deduction_amount,
                form_reference="Schedule A, Line 17",
                is_subtotal=True
            ))

        # QBI Deduction
        if bd.qbi_deduction > 0:
            section.lines.append(ComputationLine(
                line_number="",
                description="",
                amount=0
            ))
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Qualified business income deduction (Section 199A)",
                amount=bd.qbi_deduction,
                form_reference="Form 1040, Line 13",
                schedule_reference="Form 8995/8995-A"
            ))

        # Total Deductions
        total_ded = bd.deduction_amount + bd.qbi_deduction
        section.lines.append(ComputationLine(
            line_number="",
            description="TOTAL DEDUCTIONS",
            amount=total_ded,
            form_reference="Form 1040, Lines 12+13",
            is_total=True
        ))

        # Taxable Income
        section.lines.append(ComputationLine(
            line_number="",
            description="",
            amount=0
        ))
        section.lines.append(ComputationLine(
            line_number="",
            description="TAXABLE INCOME",
            amount=bd.taxable_income,
            form_reference="Form 1040, Line 15",
            is_total=True,
            supporting_detail=f"AGI ${bd.agi:,.2f} less Deductions ${total_ded:,.2f}"
        ))

        section.subtotal = bd.taxable_income
        return section

    def _build_tax_computation_section(self) -> ComputationSection:
        """Build tax computation section."""
        section = ComputationSection(title="PART IV - TAX COMPUTATION")
        bd = self.breakdown

        line_num = 1

        # Ordinary income tax
        section.lines.append(ComputationLine(
            line_number=f"{line_num}",
            description="Tax on ordinary income",
            amount=bd.ordinary_income_tax,
            form_reference="Form 1040, Line 16",
            supporting_detail="Per tax rate schedules or tax tables"
        ))
        line_num += 1

        # Preferential rate tax (qualified dividends / LTCG)
        if bd.preferential_income_tax > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Tax on qualified dividends and long-term capital gains",
                amount=bd.preferential_income_tax,
                form_reference="Schedule D Tax Worksheet",
                supporting_detail="0%/15%/20% preferential rates"
            ))
            line_num += 1

        # Total income tax before other taxes
        income_tax = bd.ordinary_income_tax + bd.preferential_income_tax
        section.lines.append(ComputationLine(
            line_number="",
            description="Total income tax",
            amount=income_tax,
            is_subtotal=True
        ))

        section.subtotal = income_tax
        return section

    def _build_credits_section(self) -> ComputationSection:
        """Build tax credits section."""
        section = ComputationSection(title="PART V - TAX CREDITS")
        bd = self.breakdown
        credits = bd.credit_breakdown or {}

        line_num = 1
        total_nonrefundable = 0.0
        total_refundable = 0.0

        section.notes.append("Nonrefundable Credits (reduce tax to zero)")

        # Child Tax Credit
        ctc = credits.get('child_tax_credit', 0)
        if ctc > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Child tax credit",
                amount=ctc,
                form_reference="Schedule 8812, Line 14",
                indent_level=1
            ))
            total_nonrefundable += ctc
            line_num += 1

        # Other Dependent Credit
        odc = credits.get('other_dependent_credit', 0)
        if odc > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Credit for other dependents",
                amount=odc,
                form_reference="Schedule 8812",
                indent_level=1
            ))
            total_nonrefundable += odc
            line_num += 1

        # Education credits (nonrefundable portion)
        edu_nonref = credits.get('education_credit_nonrefundable', 0)
        if edu_nonref > 0:
            credit_type = credits.get('education_credit_type', 'AOTC/LLC')
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description=f"Education credit ({credit_type}) - nonrefundable",
                amount=edu_nonref,
                form_reference="Form 8863, Line 19",
                indent_level=1
            ))
            total_nonrefundable += edu_nonref
            line_num += 1

        # Foreign Tax Credit
        ftc = credits.get('foreign_tax_credit', 0)
        if ftc > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Foreign tax credit",
                amount=ftc,
                form_reference="Form 1116 or Form 1040",
                indent_level=1
            ))
            total_nonrefundable += ftc
            line_num += 1

        # Retirement savings credit
        savers = credits.get('retirement_savings_credit', 0)
        if savers > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Retirement savings contributions credit",
                amount=savers,
                form_reference="Form 8880",
                indent_level=1
            ))
            total_nonrefundable += savers
            line_num += 1

        # Child care credit
        care = credits.get('child_care_credit', 0)
        if care > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Child and dependent care credit",
                amount=care,
                form_reference="Form 2441",
                indent_level=1
            ))
            total_nonrefundable += care
            line_num += 1

        # Energy credits
        clean_energy = credits.get('residential_clean_energy_credit', 0)
        if clean_energy > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Residential clean energy credit",
                amount=clean_energy,
                form_reference="Form 5695, Part I",
                indent_level=1
            ))
            total_nonrefundable += clean_energy
            line_num += 1

        energy_eff = credits.get('energy_efficient_home_credit', 0)
        if energy_eff > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Energy efficient home improvement credit",
                amount=energy_eff,
                form_reference="Form 5695, Part II",
                indent_level=1
            ))
            total_nonrefundable += energy_eff
            line_num += 1

        # Total nonrefundable
        if total_nonrefundable > 0:
            section.lines.append(ComputationLine(
                line_number="",
                description="Total nonrefundable credits",
                amount=total_nonrefundable,
                form_reference="Schedule 3, Line 8",
                is_subtotal=True
            ))

        # Refundable Credits
        section.lines.append(ComputationLine(
            line_number="",
            description="",
            amount=0
        ))
        section.notes.append("Refundable Credits (may result in refund)")

        # EITC
        eitc = credits.get('earned_income_credit', 0)
        if eitc > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Earned income credit",
                amount=eitc,
                form_reference="Schedule EIC",
                indent_level=1
            ))
            total_refundable += eitc
            line_num += 1

        # Additional Child Tax Credit (refundable portion)
        actc = credits.get('additional_child_tax_credit', 0)
        if actc > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Additional child tax credit (refundable)",
                amount=actc,
                form_reference="Schedule 8812, Line 27",
                indent_level=1
            ))
            total_refundable += actc
            line_num += 1

        # Education credit (refundable AOTC portion)
        edu_ref = credits.get('education_credit_refundable', 0)
        if edu_ref > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="American opportunity credit (refundable 40%)",
                amount=edu_ref,
                form_reference="Form 8863, Line 8",
                indent_level=1
            ))
            total_refundable += edu_ref
            line_num += 1

        # Premium Tax Credit
        ptc = credits.get('premium_tax_credit', 0)
        if ptc > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Net premium tax credit",
                amount=ptc,
                form_reference="Form 8962",
                indent_level=1
            ))
            total_refundable += ptc
            line_num += 1

        # Total refundable
        if total_refundable > 0:
            section.lines.append(ComputationLine(
                line_number="",
                description="Total refundable credits",
                amount=total_refundable,
                form_reference="Form 1040, Line 32",
                is_subtotal=True
            ))

        # Total all credits
        section.lines.append(ComputationLine(
            line_number="",
            description="TOTAL TAX CREDITS",
            amount=bd.total_credits,
            is_total=True
        ))

        section.subtotal = bd.total_credits
        return section

    def _build_other_taxes_section(self) -> ComputationSection:
        """Build other taxes section."""
        section = ComputationSection(title="PART VI - OTHER TAXES")
        bd = self.breakdown

        line_num = 1
        total_other = 0.0

        # Self-employment tax
        if bd.self_employment_tax > 0:
            se_detail = bd.se_tax_breakdown or {}
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Self-employment tax",
                amount=bd.self_employment_tax,
                form_reference="Schedule 2, Line 4",
                schedule_reference="Schedule SE",
                supporting_detail=f"SS: ${se_detail.get('social_security_tax', 0):,.2f}, Medicare: ${se_detail.get('medicare_tax', 0):,.2f}"
            ))
            total_other += bd.self_employment_tax
            line_num += 1

        # Additional Medicare Tax
        if bd.additional_medicare_tax > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Additional Medicare Tax (0.9%)",
                amount=bd.additional_medicare_tax,
                form_reference="Schedule 2, Line 11",
                schedule_reference="Form 8959"
            ))
            total_other += bd.additional_medicare_tax
            line_num += 1

        # Net Investment Income Tax
        if bd.net_investment_income_tax > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Net investment income tax (3.8%)",
                amount=bd.net_investment_income_tax,
                form_reference="Schedule 2, Line 12",
                schedule_reference="Form 8960"
            ))
            total_other += bd.net_investment_income_tax
            line_num += 1

        # Alternative Minimum Tax
        if bd.alternative_minimum_tax > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Alternative minimum tax",
                amount=bd.alternative_minimum_tax,
                form_reference="Schedule 2, Line 1",
                schedule_reference="Form 6251"
            ))
            total_other += bd.alternative_minimum_tax
            line_num += 1

        # PTC Repayment
        if bd.ptc_repayment > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Excess advance premium tax credit repayment",
                amount=bd.ptc_repayment,
                form_reference="Schedule 2, Line 2",
                schedule_reference="Form 8962"
            ))
            total_other += bd.ptc_repayment
            line_num += 1

        # Estimated tax penalty
        if bd.estimated_tax_penalty > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Estimated tax underpayment penalty",
                amount=bd.estimated_tax_penalty,
                form_reference="Form 1040, Line 38",
                schedule_reference="Form 2210"
            ))
            total_other += bd.estimated_tax_penalty
            line_num += 1

        # Total other taxes
        section.lines.append(ComputationLine(
            line_number="",
            description="TOTAL OTHER TAXES",
            amount=total_other,
            form_reference="Schedule 2, Line 21",
            is_total=True
        ))

        section.subtotal = total_other
        return section

    def _build_payments_section(self) -> ComputationSection:
        """Build payments and withholdings section."""
        section = ComputationSection(title="PART VII - PAYMENTS AND WITHHOLDINGS")
        income = self.tax_return.income
        bd = self.breakdown

        line_num = 1

        # Federal withholding
        withholding = income.get_total_federal_withholding() if hasattr(income, 'get_total_federal_withholding') else 0
        if withholding > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Federal income tax withheld (W-2/W-2G)",
                amount=withholding,
                form_reference="Form 1040, Line 25a"
            ))
            line_num += 1

        # Estimated tax payments
        estimated = getattr(income, 'estimated_tax_payments', 0) or 0
        if estimated > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Estimated tax payments",
                amount=estimated,
                form_reference="Form 1040, Line 26"
            ))
            line_num += 1

        # Amount paid with extension
        extension = getattr(income, 'amount_paid_with_extension', 0) or 0
        if extension > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Amount paid with extension request",
                amount=extension,
                form_reference="Form 1040, Line 26"
            ))
            line_num += 1

        # Excess Social Security withholding
        excess_ss = getattr(income, 'excess_social_security_withholding', 0) or 0
        if excess_ss > 0:
            section.lines.append(ComputationLine(
                line_number=f"{line_num}",
                description="Excess Social Security tax withheld",
                amount=excess_ss,
                form_reference="Schedule 3, Line 11",
                supporting_detail="Multiple employer withholding over wage base"
            ))
            line_num += 1

        # Total payments
        section.lines.append(ComputationLine(
            line_number="",
            description="TOTAL PAYMENTS",
            amount=bd.total_payments,
            form_reference="Form 1040, Line 33",
            is_total=True
        ))

        section.subtotal = bd.total_payments
        return section

    def _build_summary_section(self) -> ComputationSection:
        """Build final tax summary section."""
        section = ComputationSection(title="PART VIII - TAX SUMMARY")
        bd = self.breakdown

        # Total Tax
        section.lines.append(ComputationLine(
            line_number="1",
            description="Total Tax",
            amount=bd.total_tax,
            form_reference="Form 1040, Line 24",
            is_subtotal=True
        ))

        # Total Payments
        section.lines.append(ComputationLine(
            line_number="2",
            description="Total Payments",
            amount=bd.total_payments,
            form_reference="Form 1040, Line 33",
            is_subtotal=True
        ))

        # Refund or Amount Owed
        if bd.refund_or_owed < 0:
            section.lines.append(ComputationLine(
                line_number="3",
                description="REFUND DUE",
                amount=abs(bd.refund_or_owed),
                form_reference="Form 1040, Line 35a",
                is_total=True
            ))
        else:
            section.lines.append(ComputationLine(
                line_number="3",
                description="AMOUNT OWED",
                amount=bd.refund_or_owed,
                form_reference="Form 1040, Line 37",
                is_total=True
            ))

        # Effective tax rate
        section.lines.append(ComputationLine(
            line_number="",
            description="",
            amount=0
        ))
        section.lines.append(ComputationLine(
            line_number="",
            description=f"Effective Tax Rate: {bd.effective_tax_rate:.2f}%",
            amount=0,
            supporting_detail=f"Total tax ${bd.total_tax:,.2f} / AGI ${bd.agi:,.2f}"
        ))
        section.lines.append(ComputationLine(
            line_number="",
            description=f"Marginal Tax Rate: {bd.marginal_tax_rate:.1f}%",
            amount=0
        ))

        # Safe harbor status
        if bd.safe_harbor_met:
            section.lines.append(ComputationLine(
                line_number="",
                description="Estimated Tax Safe Harbor: MET",
                amount=0,
                supporting_detail=f"Required payment: ${bd.required_annual_payment:,.2f}"
            ))
        else:
            section.lines.append(ComputationLine(
                line_number="",
                description="Estimated Tax Safe Harbor: NOT MET",
                amount=0,
                supporting_detail=f"Penalty: ${bd.estimated_tax_penalty:,.2f}"
            ))

        section.subtotal = bd.refund_or_owed
        return section

    def _build_footnotes(self) -> List[Dict[str, Any]]:
        """Build footnotes from assumptions."""
        footnotes = []
        for assumption in self.assumptions:
            footnotes.append({
                "number": assumption.footnote_number,
                "category": assumption.category.value,
                "text": assumption.description,
                "impact": assumption.impact,
                "reference": assumption.reference,
                "confidence": assumption.confidence,
                "documentation_required": assumption.requires_documentation
            })
        return footnotes

    def _build_validation_notes(self) -> List[str]:
        """Build validation notes for preparer review."""
        notes = []
        bd = self.breakdown

        # Filing requirements
        if bd.gross_income > 0:
            notes.append("FILING REQUIREMENT: Return is required based on gross income.")

        # Large deduction warning
        if bd.deduction_type == "itemized" and bd.deduction_amount > bd.agi * 0.5:
            notes.append("REVIEW: Itemized deductions exceed 50% of AGI - verify documentation.")

        # High SALT - access itemized deduction fields
        deductions = self.tax_return.deductions
        itemized = getattr(deductions, 'itemized', None)
        salt = ((getattr(itemized, 'state_local_income_tax', 0) or 0) +
                (getattr(itemized, 'state_local_sales_tax', 0) or 0) +
                (getattr(itemized, 'real_estate_tax', 0) or 0) +
                (getattr(itemized, 'personal_property_tax', 0) or 0)) if itemized else 0
        if salt > 10000:
            notes.append(f"NOTE: SALT limited to $10,000 (actual: ${salt:,.2f}).")

        # Large charitable - access itemized deduction fields
        charity = ((getattr(itemized, 'charitable_cash', 0) or 0) +
                   (getattr(itemized, 'charitable_non_cash', 0) or 0)) if itemized else 0
        if charity > bd.agi * 0.3:
            notes.append("REVIEW: Charitable contributions exceed 30% of AGI - verify receipts.")

        # SE tax
        if bd.self_employment_tax > 5000:
            notes.append("NOTE: Significant self-employment tax - consider estimated payments.")

        # Capital loss carryforward
        if bd.new_st_loss_carryforward > 0 or bd.new_lt_loss_carryforward > 0:
            total_cf = bd.new_st_loss_carryforward + bd.new_lt_loss_carryforward
            notes.append(f"CARRYFORWARD: ${total_cf:,.2f} capital loss to future years.")

        # Crypto activity
        if bd.had_virtual_currency_activity:
            notes.append("DISCLOSURE: Virtual currency activity - Form 1040 checkbox required.")

        # Estimated penalty
        if bd.estimated_tax_penalty > 0:
            notes.append(f"PENALTY: Estimated tax underpayment penalty of ${bd.estimated_tax_penalty:,.2f}.")

        return notes

    def _build_preparer_notes(self) -> List[str]:
        """Build preparer notes for workpaper documentation."""
        notes = []

        notes.append("PREPARER CHECKLIST:")
        notes.append("[ ] Verify all income documents received (W-2, 1099s, K-1s)")
        notes.append("[ ] Confirm filing status eligibility")
        notes.append("[ ] Review itemized vs standard deduction election")
        notes.append("[ ] Verify dependent qualification tests")
        notes.append("[ ] Check credit eligibility documentation")
        notes.append("[ ] Review prior year return for consistency")
        notes.append("[ ] Confirm estimated payment amounts")
        notes.append("[ ] Document any assumptions made")

        return notes

    def _section_to_dict(self, section: ComputationSection) -> Dict[str, Any]:
        """Convert section to dictionary."""
        return {
            "title": section.title,
            "lines": [
                {
                    "line_number": line.line_number,
                    "description": line.description,
                    "amount": line.amount,
                    "form_reference": line.form_reference,
                    "schedule_reference": line.schedule_reference,
                    "is_subtotal": line.is_subtotal,
                    "is_total": line.is_total,
                    "indent_level": line.indent_level,
                    "footnote_refs": line.footnote_refs,
                    "supporting_detail": line.supporting_detail,
                }
                for line in section.lines
            ],
            "subtotal": section.subtotal,
            "notes": section.notes,
        }

    def _assumption_to_dict(self, assumption: Assumption) -> Dict[str, Any]:
        """Convert assumption to dictionary."""
        return {
            "footnote_number": assumption.footnote_number,
            "category": assumption.category.value,
            "description": assumption.description,
            "impact": assumption.impact,
            "reference": assumption.reference,
            "confidence": assumption.confidence,
            "requires_documentation": assumption.requires_documentation,
        }

    def to_text(self) -> str:
        """Generate plain text computation statement."""
        data = self.generate()
        lines = []

        # Header
        header = data["header"]
        lines.append("=" * 80)
        lines.append(f"{header['title']:^80}")
        lines.append(f"{header['subtitle']:^80}")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Taxpayer:      {header['taxpayer']['name']}")
        lines.append(f"SSN:           {header['taxpayer']['ssn_masked']}")
        lines.append(f"Filing Status: {header['taxpayer']['filing_status']}")
        lines.append("")
        lines.append(f"Prepared by:   {header['preparer']}")
        lines.append(f"Firm:          {header['firm']}")
        lines.append(f"Date:          {header['date_prepared']}")
        lines.append("")
        lines.append(header['disclaimer'])
        lines.append("")

        # Sections
        for section in data["sections"]:
            lines.append("-" * 80)
            lines.append(section["title"])
            lines.append("-" * 80)

            for note in section.get("notes", []):
                lines.append(f"  ** {note}")

            for line in section["lines"]:
                if not line["description"]:
                    lines.append("")
                    continue

                indent = "  " * line["indent_level"]
                desc = line["description"]
                amount = line["amount"]

                if line["is_total"]:
                    lines.append("")
                    lines.append(f"{indent}{desc:.<50} ${amount:>15,.2f}")
                    lines.append("  " + "=" * 65)
                elif line["is_subtotal"]:
                    lines.append(f"{indent}{desc:.<50} ${amount:>15,.2f}")
                    lines.append("  " + "-" * 65)
                elif amount != 0 or line["form_reference"]:
                    if amount >= 0:
                        lines.append(f"{indent}{desc:<50} ${amount:>15,.2f}")
                    else:
                        lines.append(f"{indent}{desc:<50} (${abs(amount):>13,.2f})")
                else:
                    lines.append(f"{indent}{desc}")

                # Supporting detail
                if line.get("supporting_detail"):
                    lines.append(f"{indent}    [{line['supporting_detail']}]")

            lines.append("")

        # Assumptions and Footnotes
        if data["footnotes"]:
            lines.append("-" * 80)
            lines.append("ASSUMPTIONS AND FOOTNOTES")
            lines.append("-" * 80)
            for fn in data["footnotes"]:
                lines.append(f"[{fn['number']}] {fn['text']}")
                lines.append(f"    Impact: {fn['impact']}")
                lines.append(f"    Reference: {fn['reference']}")
                if fn['documentation_required']:
                    lines.append(f"    ** DOCUMENTATION REQUIRED **")
                lines.append("")

        # Validation Notes
        if data["validation"]:
            lines.append("-" * 80)
            lines.append("REVIEW NOTES")
            lines.append("-" * 80)
            for note in data["validation"]:
                lines.append(f"  * {note}")
            lines.append("")

        # Preparer Notes
        if data["preparer_notes"]:
            lines.append("-" * 80)
            lines.append("PREPARER WORKPAPER NOTES")
            lines.append("-" * 80)
            for note in data["preparer_notes"]:
                lines.append(f"  {note}")
            lines.append("")

        lines.append("=" * 80)
        lines.append(f"Generated: {data['metadata']['generated_at']}")
        lines.append(f"Software:  {data['metadata']['software_version']}")
        lines.append("=" * 80)

        return "\n".join(lines)

    def to_json(self) -> str:
        """Generate JSON computation statement."""
        return json.dumps(self.generate(), indent=2, default=str)
