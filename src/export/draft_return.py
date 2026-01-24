"""
Draft Tax Return Generator

Generates comprehensive draft tax returns suitable for:
- Client review and signature
- Professional filing preparation
- Audit documentation
- Big4-level client deliverables

Includes:
- Complete Form 1040 summary
- All required schedules
- Supporting computations
- Assumptions and disclosures
- Preparer notes
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

from export.computation_statement import TaxComputationStatement, AssumptionCategory


class CompletionStatus(Enum):
    """Status of return completion."""
    COMPLETE = "Complete"
    INCOMPLETE = "Incomplete - Missing Information"
    PENDING_REVIEW = "Pending Review"
    READY_FOR_SIGNATURE = "Ready for Signature"


@dataclass
class MissingItem:
    """Represents a missing item needed for return completion."""
    category: str
    description: str
    form_reference: str
    priority: str  # "Required", "Recommended", "Optional"
    impact: str


@dataclass
class ScheduleRequirement:
    """Requirement for a specific schedule."""
    schedule_name: str
    form_number: str
    required: bool
    reason: str
    data_present: bool


class DraftReturnGenerator:
    """
    Generates comprehensive draft tax returns.

    Features:
    - Completeness analysis
    - Missing information identification
    - Schedule requirements determination
    - Professional-grade output
    - Client-ready presentation
    """

    def __init__(
        self,
        tax_return: "TaxReturn",
        breakdown: "CalculationBreakdown",
        preparer_name: str = "",
        firm_name: str = "",
        client_id: str = "",
    ):
        self.tax_return = tax_return
        self.breakdown = breakdown
        self.preparer_name = preparer_name
        self.firm_name = firm_name
        self.client_id = client_id
        self._generated_at = datetime.now()

        # Analysis results
        self.missing_items: List[MissingItem] = []
        self.schedule_requirements: List[ScheduleRequirement] = []
        self.completion_status = CompletionStatus.INCOMPLETE

    def generate(self) -> Dict[str, Any]:
        """Generate complete draft return package."""
        # Run completeness analysis
        self._analyze_completeness()
        self._determine_schedule_requirements()

        # Generate computation statement
        computation = TaxComputationStatement(
            self.tax_return,
            self.breakdown,
            self.preparer_name,
            self.firm_name
        )
        computation_data = computation.generate()

        return {
            "draft_return": {
                "header": self._build_return_header(),
                "form_1040_summary": self._build_form_1040_summary(),
                "schedules_required": self._get_schedules_summary(),
                "computation_statement": computation_data,
                "completion_analysis": self._build_completion_analysis(),
                "client_instructions": self._build_client_instructions(),
                "engagement_letter_items": self._build_engagement_items(),
            },
            "metadata": {
                "generated_at": self._generated_at.isoformat(),
                "tax_year": self.tax_return.tax_year,
                "preparer": self.preparer_name,
                "firm": self.firm_name,
                "client_id": self.client_id,
                "status": self.completion_status.value,
            }
        }

    def _analyze_completeness(self) -> None:
        """Analyze return for completeness."""
        tr = self.tax_return
        income = tr.income
        deductions = tr.deductions
        bd = self.breakdown

        # Check for common missing items
        self.missing_items = []

        # SSN validation
        if not tr.taxpayer.ssn or len(tr.taxpayer.ssn.replace("-", "")) != 9:
            self.missing_items.append(MissingItem(
                category="Taxpayer Information",
                description="Valid Social Security Number required",
                form_reference="Form 1040, top",
                priority="Required",
                impact="Return cannot be filed without valid SSN"
            ))

        # Date of birth for age-based calculations
        if not hasattr(tr.taxpayer, 'date_of_birth') or not tr.taxpayer.date_of_birth:
            self.missing_items.append(MissingItem(
                category="Taxpayer Information",
                description="Date of birth needed for age-based calculations",
                form_reference="Various",
                priority="Recommended",
                impact="May affect standard deduction, IRA limits, EITC eligibility"
            ))

        # W-2 employer information
        if hasattr(income, 'w2_forms') and income.w2_forms:
            for i, w2 in enumerate(income.w2_forms):
                if not getattr(w2, 'employer_ein', None):
                    self.missing_items.append(MissingItem(
                        category="Income Documentation",
                        description=f"W-2 #{i+1}: Employer EIN missing",
                        form_reference="W-2 Box b",
                        priority="Required",
                        impact="E-file may be rejected without employer EIN"
                    ))

        # Self-employment documentation
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 0:
            if not getattr(income, 'business_name', None):
                self.missing_items.append(MissingItem(
                    category="Self-Employment",
                    description="Business name or description",
                    form_reference="Schedule C, Line A",
                    priority="Required",
                    impact="Required for Schedule C filing"
                ))

            # Estimated payments tracking
            est_payments = getattr(income, 'estimated_tax_payments', 0) or 0
            if se_income > 50000 and est_payments == 0:
                self.missing_items.append(MissingItem(
                    category="Payments",
                    description="Verify estimated tax payments made",
                    form_reference="Form 1040, Line 26",
                    priority="Recommended",
                    impact="Potential underpayment penalty if payments not made"
                ))

        # Itemized deduction documentation
        if bd.deduction_type == "itemized":
            # Mortgage interest
            mortgage_int = getattr(deductions, 'mortgage_interest', 0) or 0
            if mortgage_int > 0:
                if not getattr(deductions, 'mortgage_principal', None):
                    self.missing_items.append(MissingItem(
                        category="Deductions",
                        description="Form 1098 mortgage interest statement",
                        form_reference="Schedule A, Line 8a",
                        priority="Required",
                        impact="Verify Form 1098 matches claimed interest"
                    ))

            # Charitable contributions
            charity = (getattr(deductions, 'charitable_cash', 0) or 0) + \
                      (getattr(deductions, 'charitable_noncash', 0) or 0)
            if charity > 250:
                self.missing_items.append(MissingItem(
                    category="Deductions",
                    description="Written acknowledgments for donations over $250",
                    form_reference="Schedule A, Lines 11-12",
                    priority="Required",
                    impact="Donations over $250 require contemporaneous written acknowledgment"
                ))

            if (getattr(deductions, 'charitable_noncash', 0) or 0) > 500:
                self.missing_items.append(MissingItem(
                    category="Deductions",
                    description="Form 8283 for noncash donations over $500",
                    form_reference="Form 8283",
                    priority="Required",
                    impact="Form 8283 required for noncash contributions over $500"
                ))

        # Capital gains documentation
        if bd.net_short_term_gain_loss != 0 or bd.net_long_term_gain_loss != 0:
            self.missing_items.append(MissingItem(
                category="Investments",
                description="Confirm cost basis documentation for all sales",
                form_reference="Form 8949",
                priority="Required",
                impact="Cost basis must be documented for all security sales"
            ))

        # Child tax credit documentation
        credits_dict = bd.credit_breakdown or {}
        if credits_dict.get('child_tax_credit', 0) > 0 or credits_dict.get('earned_income_credit', 0) > 0:
            self.missing_items.append(MissingItem(
                category="Credits",
                description="Dependent SSN and relationship documentation",
                form_reference="Schedule 8812 / Schedule EIC",
                priority="Required",
                impact="Dependent credits require valid SSN and relationship proof"
            ))

        # Determine completion status
        required_missing = [m for m in self.missing_items if m.priority == "Required"]
        if not required_missing:
            if self.missing_items:
                self.completion_status = CompletionStatus.PENDING_REVIEW
            else:
                self.completion_status = CompletionStatus.READY_FOR_SIGNATURE
        else:
            self.completion_status = CompletionStatus.INCOMPLETE

    def _determine_schedule_requirements(self) -> None:
        """Determine which schedules are required."""
        tr = self.tax_return
        income = tr.income
        deductions = tr.deductions
        bd = self.breakdown

        self.schedule_requirements = []

        # Schedule 1 - Additional Income and Adjustments
        needs_sch1 = (
            bd.adjustments_to_income > 0 or
            getattr(income, 'other_income', 0) or 0 > 0 or
            bd.k1_ordinary_income != 0 or
            (getattr(income, 'rental_income', 0) or 0) > 0
        )
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule 1",
            form_number="Additional Income and Adjustments",
            required=needs_sch1,
            reason="Required for above-the-line deductions or additional income",
            data_present=needs_sch1
        ))

        # Schedule 2 - Additional Taxes
        needs_sch2 = (
            bd.self_employment_tax > 0 or
            bd.additional_medicare_tax > 0 or
            bd.net_investment_income_tax > 0 or
            bd.alternative_minimum_tax > 0
        )
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule 2",
            form_number="Additional Taxes",
            required=needs_sch2,
            reason="Required for SE tax, AMT, NIIT, or additional Medicare tax",
            data_present=needs_sch2
        ))

        # Schedule 3 - Additional Credits and Payments
        needs_sch3 = bd.nonrefundable_credits > 0 or bd.refundable_credits > 0
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule 3",
            form_number="Additional Credits and Payments",
            required=needs_sch3,
            reason="Required for tax credits",
            data_present=needs_sch3
        ))

        # Schedule A - Itemized Deductions
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule A",
            form_number="Itemized Deductions",
            required=bd.deduction_type == "itemized",
            reason="Required when itemizing deductions",
            data_present=bd.deduction_type == "itemized"
        ))

        # Schedule B - Interest and Dividends
        interest = getattr(income, 'interest_income', 0) or 0
        dividends = getattr(income, 'ordinary_dividends', 0) or 0
        needs_schb = interest > 1500 or dividends > 1500
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule B",
            form_number="Interest and Ordinary Dividends",
            required=needs_schb,
            reason="Required if interest or dividends exceed $1,500",
            data_present=needs_schb
        ))

        # Schedule C - Self-Employment
        se_income = getattr(income, 'self_employment_income', 0) or 0
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule C",
            form_number="Profit or Loss from Business",
            required=se_income > 0,
            reason="Required for self-employment income",
            data_present=se_income > 0
        ))

        # Schedule D - Capital Gains and Losses
        has_cap_gains = bd.net_short_term_gain_loss != 0 or bd.net_long_term_gain_loss != 0
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule D",
            form_number="Capital Gains and Losses",
            required=has_cap_gains,
            reason="Required for capital gain/loss reporting",
            data_present=has_cap_gains
        ))

        # Schedule E - Supplemental Income
        rental = getattr(income, 'rental_income', 0) or 0
        has_k1 = bd.k1_ordinary_income != 0 or bd.k1_preferential_income != 0
        needs_sche = rental > 0 or has_k1
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule E",
            form_number="Supplemental Income and Loss",
            required=needs_sche,
            reason="Required for rental income or K-1 pass-through income",
            data_present=needs_sche
        ))

        # Schedule SE - Self-Employment Tax
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule SE",
            form_number="Self-Employment Tax",
            required=bd.self_employment_tax > 0,
            reason="Required when self-employment tax applies",
            data_present=bd.self_employment_tax > 0
        ))

        # Form 8949 - Capital Asset Sales
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Form 8949",
            form_number="Sales of Capital Assets",
            required=has_cap_gains,
            reason="Required to report individual capital transactions",
            data_present=has_cap_gains
        ))

        # Form 8863 - Education Credits
        edu_credits = (bd.credit_breakdown or {}).get('education_credit_nonrefundable', 0) + \
                      (bd.credit_breakdown or {}).get('education_credit_refundable', 0)
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Form 8863",
            form_number="Education Credits",
            required=edu_credits > 0,
            reason="Required for AOTC or LLC education credits",
            data_present=edu_credits > 0
        ))

        # Schedule 8812 - Child Tax Credit
        ctc = (bd.credit_breakdown or {}).get('child_tax_credit', 0) + \
              (bd.credit_breakdown or {}).get('additional_child_tax_credit', 0)
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule 8812",
            form_number="Credits for Qualifying Children",
            required=ctc > 0,
            reason="Required for child tax credit",
            data_present=ctc > 0
        ))

        # Schedule EIC - Earned Income Credit
        eitc = (bd.credit_breakdown or {}).get('earned_income_credit', 0)
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Schedule EIC",
            form_number="Earned Income Credit",
            required=eitc > 0,
            reason="Required for EITC with qualifying children",
            data_present=eitc > 0
        ))

        # Form 6251 - AMT
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Form 6251",
            form_number="Alternative Minimum Tax",
            required=bd.alternative_minimum_tax > 0,
            reason="Required when AMT applies",
            data_present=bd.alternative_minimum_tax > 0
        ))

        # Form 8959 - Additional Medicare Tax
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Form 8959",
            form_number="Additional Medicare Tax",
            required=bd.additional_medicare_tax > 0,
            reason="Required for 0.9% Additional Medicare Tax",
            data_present=bd.additional_medicare_tax > 0
        ))

        # Form 8960 - NIIT
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Form 8960",
            form_number="Net Investment Income Tax",
            required=bd.net_investment_income_tax > 0,
            reason="Required for 3.8% Net Investment Income Tax",
            data_present=bd.net_investment_income_tax > 0
        ))

        # Form 2210 - Underpayment Penalty
        self.schedule_requirements.append(ScheduleRequirement(
            schedule_name="Form 2210",
            form_number="Underpayment of Estimated Tax",
            required=bd.estimated_tax_penalty > 0,
            reason="Required when underpayment penalty applies",
            data_present=bd.estimated_tax_penalty > 0
        ))

    def _build_return_header(self) -> Dict[str, Any]:
        """Build draft return header."""
        tp = self.tax_return.taxpayer
        filing_status = tp.filing_status.value if hasattr(tp.filing_status, 'value') else str(tp.filing_status)

        status_display = {
            "single": "1 - Single",
            "married_joint": "2 - Married Filing Jointly",
            "married_separate": "3 - Married Filing Separately",
            "head_of_household": "4 - Head of Household",
            "qualifying_widow": "5 - Qualifying Surviving Spouse"
        }.get(filing_status, filing_status)

        return {
            "title": "DRAFT FEDERAL INCOME TAX RETURN",
            "form": "Form 1040",
            "tax_year": self.tax_return.tax_year,
            "taxpayer": {
                "name": f"{tp.first_name or ''} {tp.last_name or ''}".strip(),
                "ssn": f"XXX-XX-{(tp.ssn or '')[-4:]}" if tp.ssn else "XXX-XX-XXXX",
                "filing_status": status_display,
                "address": getattr(tp, 'address', 'Address on file'),
            },
            "firm": {
                "name": self.firm_name or "Tax Preparation Services",
                "preparer": self.preparer_name or "Tax Professional",
                "ptin": "P00000000",  # Placeholder
            },
            "status": self.completion_status.value,
            "date_prepared": self._generated_at.strftime("%B %d, %Y"),
            "disclaimer": (
                "DRAFT - FOR REFERENCE ONLY - NOT FOR FILING\n\n"
                "IMPORTANT LEGAL NOTICE: This document is for informational and educational "
                "purposes only. TaxAdvisor Pro is a tax information platform, NOT a tax preparation "
                "service or tax advisory service. This draft return must NOT be filed with the IRS "
                "or any state tax authority without professional review.\n\n"
                "ALWAYS consult with a licensed CPA, Enrolled Agent, or tax attorney before making "
                "any tax decisions or filing any tax returns. All calculations are estimates based "
                "on general tax rules and may not reflect your actual tax situation."
            )
        }

    def _build_form_1040_summary(self) -> Dict[str, Any]:
        """Build Form 1040 line-by-line summary."""
        bd = self.breakdown
        income = self.tax_return.income

        withholding = income.get_total_federal_withholding() if hasattr(income, 'get_total_federal_withholding') else 0

        return {
            "income": {
                "line_1a": {"description": "Total amount from Form(s) W-2", "amount": income.get_total_wages() if hasattr(income, 'get_total_wages') else 0},
                "line_2b": {"description": "Taxable interest", "amount": getattr(income, 'interest_income', 0) or 0},
                "line_3b": {"description": "Ordinary dividends", "amount": getattr(income, 'ordinary_dividends', 0) or 0},
                "line_7": {"description": "Capital gain or (loss)", "amount": bd.net_short_term_gain_loss + bd.net_long_term_gain_loss - bd.capital_loss_deduction},
                "line_8": {"description": "Other income from Schedule 1", "amount": bd.k1_ordinary_income + (getattr(income, 'self_employment_income', 0) or 0) - (getattr(income, 'self_employment_expenses', 0) or 0)},
                "line_9": {"description": "Total income", "amount": bd.gross_income},
                "line_10": {"description": "Adjustments from Schedule 1", "amount": bd.adjustments_to_income},
                "line_11": {"description": "Adjusted gross income", "amount": bd.agi},
            },
            "deductions": {
                "line_12": {"description": f"{'Standard' if bd.deduction_type == 'standard' else 'Itemized'} deduction", "amount": bd.deduction_amount},
                "line_13": {"description": "Qualified business income deduction", "amount": bd.qbi_deduction},
                "line_14": {"description": "Total deductions", "amount": bd.deduction_amount + bd.qbi_deduction},
                "line_15": {"description": "Taxable income", "amount": bd.taxable_income},
            },
            "tax_and_credits": {
                "line_16": {"description": "Tax (from tax tables or Sch D)", "amount": bd.ordinary_income_tax + bd.preferential_income_tax},
                "line_17": {"description": "Amount from Schedule 2, line 3", "amount": bd.alternative_minimum_tax},
                "line_18": {"description": "Add lines 16 and 17", "amount": bd.ordinary_income_tax + bd.preferential_income_tax + bd.alternative_minimum_tax},
                "line_19": {"description": "Child tax credit or ODC", "amount": (bd.credit_breakdown or {}).get('child_tax_credit', 0) + (bd.credit_breakdown or {}).get('other_dependent_credit', 0)},
                "line_20": {"description": "Amount from Schedule 3, line 8", "amount": bd.nonrefundable_credits - ((bd.credit_breakdown or {}).get('child_tax_credit', 0) + (bd.credit_breakdown or {}).get('other_dependent_credit', 0))},
                "line_21": {"description": "Total credits", "amount": bd.nonrefundable_credits},
                "line_22": {"description": "Subtract line 21 from line 18", "amount": max(0, bd.ordinary_income_tax + bd.preferential_income_tax + bd.alternative_minimum_tax - bd.nonrefundable_credits)},
                "line_23": {"description": "Other taxes from Schedule 2", "amount": bd.self_employment_tax + bd.additional_medicare_tax + bd.net_investment_income_tax},
                "line_24": {"description": "Total tax", "amount": bd.total_tax},
            },
            "payments": {
                "line_25a": {"description": "Federal income tax withheld W-2s", "amount": withholding},
                "line_26": {"description": "Estimated tax payments", "amount": getattr(income, 'estimated_tax_payments', 0) or 0},
                "line_27": {"description": "Earned income credit (EIC)", "amount": (bd.credit_breakdown or {}).get('earned_income_credit', 0)},
                "line_28": {"description": "Additional child tax credit", "amount": (bd.credit_breakdown or {}).get('additional_child_tax_credit', 0)},
                "line_29": {"description": "American opportunity credit", "amount": (bd.credit_breakdown or {}).get('education_credit_refundable', 0)},
                "line_33": {"description": "Total payments", "amount": bd.total_payments},
            },
            "result": {
                "line_34": {"description": "Refund" if bd.refund_or_owed < 0 else "Amount you owe", "amount": abs(bd.refund_or_owed)},
                "is_refund": bd.refund_or_owed < 0,
                "estimated_penalty": bd.estimated_tax_penalty,
            }
        }

    def _get_schedules_summary(self) -> List[Dict[str, Any]]:
        """Get summary of required schedules."""
        return [
            {
                "name": sched.schedule_name,
                "form_number": sched.form_number,
                "required": sched.required,
                "reason": sched.reason,
                "data_present": sched.data_present,
            }
            for sched in self.schedule_requirements
            if sched.required
        ]

    def _build_completion_analysis(self) -> Dict[str, Any]:
        """Build completion analysis section."""
        return {
            "status": self.completion_status.value,
            "missing_items": [
                {
                    "category": item.category,
                    "description": item.description,
                    "form_reference": item.form_reference,
                    "priority": item.priority,
                    "impact": item.impact,
                }
                for item in self.missing_items
            ],
            "required_count": len([m for m in self.missing_items if m.priority == "Required"]),
            "recommended_count": len([m for m in self.missing_items if m.priority == "Recommended"]),
            "optional_count": len([m for m in self.missing_items if m.priority == "Optional"]),
        }

    def _build_client_instructions(self) -> List[str]:
        """Build client instructions for draft review."""
        instructions = [
            "INSTRUCTIONS FOR CLIENT REVIEW",
            "",
            "Please review this draft return carefully and:",
            "",
            "1. VERIFY ALL INCOME - Confirm all wages, interest, dividends, and other",
            "   income matches your records and Forms W-2, 1099s, etc.",
            "",
            "2. CHECK DEDUCTIONS - Review itemized deductions (if applicable) for accuracy.",
            "   Ensure you have documentation for all claimed deductions.",
            "",
            "3. CONFIRM DEPENDENTS - Verify dependent information is correct, including",
            "   SSNs and relationship to you.",
            "",
            "4. REVIEW PAYMENTS - Confirm estimated tax payments and withholding amounts.",
            "",
            "5. SIGN AND DATE - If all information is correct, sign the authorization",
            "   form to allow electronic filing.",
            "",
        ]

        # Add missing items instructions
        if self.missing_items:
            instructions.extend([
                "ITEMS REQUIRING YOUR ATTENTION:",
                ""
            ])
            for item in self.missing_items:
                instructions.append(f"  [{item.priority}] {item.description}")
                instructions.append(f"              Impact: {item.impact}")
                instructions.append("")

        return instructions

    def _build_engagement_items(self) -> List[str]:
        """Build engagement letter items for firm documentation."""
        items = [
            "ENGAGEMENT SCOPE ITEMS",
            "",
            "Services included in this engagement:",
            "- Preparation of federal Form 1040 individual income tax return",
        ]

        # Add required schedules
        required_schedules = [s for s in self.schedule_requirements if s.required]
        if required_schedules:
            items.append("- Preparation of the following schedules:")
            for sched in required_schedules:
                items.append(f"    * {sched.schedule_name}: {sched.form_number}")

        items.extend([
            "",
            "Client responsibilities:",
            "- Provide accurate and complete information",
            "- Maintain supporting documentation for all claimed items",
            "- Notify preparer of any changes or omissions",
            "- Review draft return for accuracy before signing",
            "",
            "Preparer responsibilities:",
            "- Prepare return in accordance with applicable tax law",
            "- Exercise due diligence in return preparation",
            "- Maintain client confidentiality",
            "- File return upon client authorization",
        ])

        return items

    def to_text(self) -> str:
        """Generate plain text draft return."""
        data = self.generate()
        lines = []

        # Header
        header = data["draft_return"]["header"]
        lines.append("=" * 80)
        lines.append(f"{header['title']:^80}")
        lines.append(f"{'Tax Year ' + str(header['tax_year']):^80}")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"STATUS: {header['status']}")
        lines.append("")
        lines.append(f"Taxpayer:      {header['taxpayer']['name']}")
        lines.append(f"SSN:           {header['taxpayer']['ssn']}")
        lines.append(f"Filing Status: {header['taxpayer']['filing_status']}")
        lines.append("")
        lines.append(f"Prepared by:   {header['firm']['preparer']}")
        lines.append(f"Firm:          {header['firm']['name']}")
        lines.append(f"Date:          {header['date_prepared']}")
        lines.append("")
        lines.append("-" * 80)
        lines.append(header['disclaimer'])
        lines.append("-" * 80)
        lines.append("")

        # Form 1040 Summary
        summary = data["draft_return"]["form_1040_summary"]

        lines.append("FORM 1040 SUMMARY")
        lines.append("=" * 80)
        lines.append("")

        # Income section
        lines.append("INCOME")
        lines.append("-" * 40)
        for line_key, line_data in summary["income"].items():
            lines.append(f"{line_key.upper():8} {line_data['description']:<45} ${line_data['amount']:>12,.2f}")
        lines.append("")

        # Deductions section
        lines.append("DEDUCTIONS")
        lines.append("-" * 40)
        for line_key, line_data in summary["deductions"].items():
            lines.append(f"{line_key.upper():8} {line_data['description']:<45} ${line_data['amount']:>12,.2f}")
        lines.append("")

        # Tax and Credits section
        lines.append("TAX AND CREDITS")
        lines.append("-" * 40)
        for line_key, line_data in summary["tax_and_credits"].items():
            lines.append(f"{line_key.upper():8} {line_data['description']:<45} ${line_data['amount']:>12,.2f}")
        lines.append("")

        # Payments section
        lines.append("PAYMENTS")
        lines.append("-" * 40)
        for line_key, line_data in summary["payments"].items():
            lines.append(f"{line_key.upper():8} {line_data['description']:<45} ${line_data['amount']:>12,.2f}")
        lines.append("")

        # Result
        lines.append("=" * 80)
        result = summary["result"]
        result_amount = result["line_34"]["amount"]
        if result["is_refund"]:
            lines.append(f"{'REFUND DUE':^80}")
            amount_str = f"${result_amount:,.2f}"
            lines.append(f"{amount_str:^80}")
        else:
            lines.append(f"{'AMOUNT OWED':^80}")
            amount_str = f"${result_amount:,.2f}"
            lines.append(f"{amount_str:^80}")

        if result["estimated_penalty"] > 0:
            penalty_str = f"(Plus estimated tax penalty of ${result['estimated_penalty']:,.2f})"
            lines.append(f"{penalty_str:^80}")
        lines.append("=" * 80)
        lines.append("")

        # Schedules Required
        schedules = data["draft_return"]["schedules_required"]
        if schedules:
            lines.append("SCHEDULES REQUIRED")
            lines.append("-" * 80)
            for sched in schedules:
                lines.append(f"  {sched['name']:15} {sched['form_number']}")
                lines.append(f"                  Reason: {sched['reason']}")
            lines.append("")

        # Completion Analysis
        completion = data["draft_return"]["completion_analysis"]
        lines.append("COMPLETION ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Status: {completion['status']}")
        lines.append(f"Required items missing: {completion['required_count']}")
        lines.append(f"Recommended items missing: {completion['recommended_count']}")
        lines.append("")

        if completion["missing_items"]:
            lines.append("MISSING ITEMS:")
            for item in completion["missing_items"]:
                lines.append(f"  [{item['priority']}] {item['description']}")
                lines.append(f"              Form: {item['form_reference']}")
                lines.append(f"              Impact: {item['impact']}")
                lines.append("")

        # Client Instructions
        lines.append("")
        for instruction in data["draft_return"]["client_instructions"]:
            lines.append(instruction)

        # Footer
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"Generated: {data['metadata']['generated_at']}")
        lines.append("Software: Jorss-Gbo Tax Software v2025.1")
        lines.append("=" * 80)

        return "\n".join(lines)

    def to_json(self) -> str:
        """Generate JSON draft return."""
        return json.dumps(self.generate(), indent=2, default=str)


def generate_complete_draft_package(
    tax_return: "TaxReturn",
    breakdown: "CalculationBreakdown",
    preparer_name: str = "",
    firm_name: str = "",
) -> Dict[str, str]:
    """
    Generate complete draft return package with all components.

    Returns dict with:
    - draft_return_text: Plain text draft return
    - computation_text: Big4-level computation statement
    - draft_return_json: JSON format for API/integration
    """
    # Generate draft return
    draft_gen = DraftReturnGenerator(
        tax_return, breakdown, preparer_name, firm_name
    )

    # Generate computation statement
    comp_gen = TaxComputationStatement(
        tax_return, breakdown, preparer_name, firm_name
    )

    return {
        "draft_return_text": draft_gen.to_text(),
        "computation_text": comp_gen.to_text(),
        "draft_return_json": draft_gen.to_json(),
        "computation_json": comp_gen.to_json(),
    }
