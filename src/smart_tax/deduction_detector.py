"""
Smart Deduction Detector

Intelligently identifies potential deductions and credits based on:
- Extracted document data
- User profile information
- Income levels and filing status
- Common patterns and situations

Provides:
- Automatic deduction detection
- Standard vs Itemized comparison
- Credit eligibility analysis
- Savings opportunity ranking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from decimal import Decimal


class DeductionType(str, Enum):
    """Types of deductions."""
    ABOVE_THE_LINE = "above_the_line"  # Reduces AGI
    ITEMIZED = "itemized"              # Schedule A
    STANDARD = "standard"              # Standard deduction
    BUSINESS = "business"              # Schedule C/SE


class CreditType(str, Enum):
    """Types of tax credits."""
    REFUNDABLE = "refundable"           # Can result in refund
    NONREFUNDABLE = "nonrefundable"     # Only reduces tax owed
    PARTIALLY_REFUNDABLE = "partially_refundable"


@dataclass
class DetectedDeduction:
    """A deduction opportunity detected from data."""
    deduction_id: str
    name: str
    description: str
    deduction_type: DeductionType
    estimated_amount: Decimal
    confidence: float  # 0-1
    source: str  # Where the data came from
    requirements: List[str]
    irs_form: str
    irs_line: str
    action_required: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deduction_id": self.deduction_id,
            "name": self.name,
            "description": self.description,
            "deduction_type": self.deduction_type.value,
            "estimated_amount": float(self.estimated_amount),
            "confidence": self.confidence,
            "source": self.source,
            "requirements": self.requirements,
            "irs_form": self.irs_form,
            "irs_line": self.irs_line,
            "action_required": self.action_required,
        }


@dataclass
class DetectedCredit:
    """A tax credit opportunity detected from data."""
    credit_id: str
    name: str
    description: str
    credit_type: CreditType
    estimated_amount: Decimal
    confidence: float
    source: str
    eligibility_factors: List[str]
    phase_out_warning: Optional[str]
    irs_form: str
    action_required: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "credit_id": self.credit_id,
            "name": self.name,
            "description": self.description,
            "credit_type": self.credit_type.value,
            "estimated_amount": float(self.estimated_amount),
            "confidence": self.confidence,
            "source": self.source,
            "eligibility_factors": self.eligibility_factors,
            "phase_out_warning": self.phase_out_warning,
            "irs_form": self.irs_form,
            "action_required": self.action_required,
        }


@dataclass
class DeductionAnalysis:
    """Complete analysis of deductions and credits."""
    standard_deduction: Decimal
    total_itemized: Decimal
    recommendation: str  # "standard" or "itemize"
    savings_difference: Decimal
    detected_deductions: List[DetectedDeduction]
    detected_credits: List[DetectedCredit]
    total_potential_savings: Decimal
    missed_opportunities: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "standard_deduction": float(self.standard_deduction),
            "total_itemized": float(self.total_itemized),
            "recommendation": self.recommendation,
            "savings_difference": float(self.savings_difference),
            "detected_deductions": [d.to_dict() for d in self.detected_deductions],
            "detected_credits": [c.to_dict() for c in self.detected_credits],
            "total_potential_savings": float(self.total_potential_savings),
            "missed_opportunities": self.missed_opportunities,
        }


class SmartDeductionDetector:
    """
    Intelligent deduction and credit detection.

    Analyzes tax situation to find:
    - Deductions the user may qualify for
    - Credits based on income and family situation
    - Standard vs itemized comparison
    - Missed opportunities
    """

    # 2025 Standard Deductions (IRS Rev. Proc. 2024-40)
    STANDARD_DEDUCTIONS_2025 = {
        "single": Decimal("15750"),
        "married_joint": Decimal("31500"),
        "married_separate": Decimal("15750"),
        "head_of_household": Decimal("23850"),
        "widow": Decimal("31500"),
    }

    # 2025 Tax Brackets (Single)
    TAX_BRACKETS_SINGLE = [
        (Decimal("11925"), Decimal("0.10")),
        (Decimal("48475"), Decimal("0.12")),
        (Decimal("103350"), Decimal("0.22")),
        (Decimal("197300"), Decimal("0.24")),
        (Decimal("250525"), Decimal("0.32")),
        (Decimal("626350"), Decimal("0.35")),
        (Decimal("999999999"), Decimal("0.37")),
    ]

    # Credit thresholds
    CHILD_TAX_CREDIT_AMOUNT = Decimal("2000")
    CHILD_TAX_CREDIT_PHASEOUT_SINGLE = Decimal("200000")
    CHILD_TAX_CREDIT_PHASEOUT_MFJ = Decimal("400000")

    EITC_MAX_INVESTMENT_INCOME = Decimal("11950")  # 2025

    def __init__(self, tax_year: int = 2025):
        self.tax_year = tax_year

    def analyze(
        self,
        extracted_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        filing_status: str,
        num_dependents: int = 0,
        user_inputs: Optional[Dict[str, Any]] = None,
    ) -> DeductionAnalysis:
        """
        Perform comprehensive deduction and credit analysis.

        Args:
            extracted_data: Data extracted from documents
            documents: List of processed documents
            filing_status: Filing status
            num_dependents: Number of dependents
            user_inputs: Additional user-provided information

        Returns:
            Complete analysis with recommendations
        """
        user_inputs = user_inputs or {}

        # Detect deductions
        deductions = self._detect_deductions(
            extracted_data, documents, filing_status, user_inputs
        )

        # Detect credits
        credits = self._detect_credits(
            extracted_data, documents, filing_status, num_dependents, user_inputs
        )

        # Calculate standard vs itemized
        standard = self.STANDARD_DEDUCTIONS_2025.get(filing_status, Decimal("15750"))
        total_itemized = sum(d.estimated_amount for d in deductions if d.deduction_type == DeductionType.ITEMIZED)

        # Recommendation
        if total_itemized > standard:
            recommendation = "itemize"
            savings_diff = total_itemized - standard
        else:
            recommendation = "standard"
            savings_diff = standard - total_itemized

        # Find missed opportunities
        missed = self._find_missed_opportunities(
            extracted_data, documents, filing_status, num_dependents, user_inputs
        )

        # Calculate total potential savings
        # Estimate marginal tax rate
        total_income = Decimal(str(extracted_data.get("wages", 0) or 0))
        marginal_rate = self._get_marginal_rate(total_income, filing_status)

        deduction_savings = max(total_itemized, standard) * marginal_rate
        credit_savings = sum(c.estimated_amount for c in credits)
        total_savings = deduction_savings + credit_savings

        return DeductionAnalysis(
            standard_deduction=standard,
            total_itemized=total_itemized,
            recommendation=recommendation,
            savings_difference=savings_diff,
            detected_deductions=deductions,
            detected_credits=credits,
            total_potential_savings=total_savings,
            missed_opportunities=missed,
        )

    def _detect_deductions(
        self,
        extracted_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        filing_status: str,
        user_inputs: Dict[str, Any],
    ) -> List[DetectedDeduction]:
        """Detect applicable deductions."""
        deductions = []
        doc_types = set(d.get("type", "") for d in documents)

        # 1. Student Loan Interest (Above-the-line)
        if "1098_e" in doc_types or user_inputs.get("has_student_loans"):
            interest = Decimal(str(extracted_data.get("student_loan_interest", 0) or user_inputs.get("student_loan_interest", 0)))
            if interest > 0:
                capped_interest = min(interest, Decimal("2500"))
                deductions.append(DetectedDeduction(
                    deduction_id="student_loan_interest",
                    name="Student Loan Interest",
                    description="Deduct up to $2,500 of student loan interest paid",
                    deduction_type=DeductionType.ABOVE_THE_LINE,
                    estimated_amount=capped_interest,
                    confidence=0.95 if "1098_e" in doc_types else 0.7,
                    source="1098-E" if "1098_e" in doc_types else "User Input",
                    requirements=["Paid interest on qualified student loan", "Income under phase-out limit"],
                    irs_form="Schedule 1",
                    irs_line="Line 21",
                    action_required="Verify 1098-E amount",
                ))

        # 2. Educator Expenses (Above-the-line)
        if user_inputs.get("is_educator"):
            deductions.append(DetectedDeduction(
                deduction_id="educator_expenses",
                name="Educator Expenses",
                description="Teachers can deduct up to $300 for classroom supplies",
                deduction_type=DeductionType.ABOVE_THE_LINE,
                estimated_amount=Decimal("300"),
                confidence=0.6,
                source="User indicated educator status",
                requirements=["K-12 teacher, instructor, counselor, principal, or aide", "Work 900+ hours in school year"],
                irs_form="Schedule 1",
                irs_line="Line 11",
                action_required="Enter actual expenses paid",
            ))

        # 3. HSA Contributions (Above-the-line)
        if "1099_sa" in doc_types or user_inputs.get("has_hsa"):
            hsa_contrib = Decimal(str(user_inputs.get("hsa_contribution", 0)))
            if hsa_contrib > 0:
                deductions.append(DetectedDeduction(
                    deduction_id="hsa_contribution",
                    name="HSA Contribution",
                    description="Health Savings Account contributions are tax-deductible",
                    deduction_type=DeductionType.ABOVE_THE_LINE,
                    estimated_amount=hsa_contrib,
                    confidence=0.85,
                    source="User Input",
                    requirements=["Enrolled in High Deductible Health Plan", "Not enrolled in Medicare"],
                    irs_form="Form 8889",
                    irs_line="Line 13",
                    action_required="Verify contribution amount",
                ))

        # 4. Self-Employment Deductions (Above-the-line)
        if "1099_nec" in doc_types or user_inputs.get("has_self_employment"):
            se_income = Decimal(str(extracted_data.get("nonemployee_compensation", 0) or 0))
            if se_income > 0:
                # Self-employment tax deduction (half of SE tax)
                se_tax = se_income * Decimal("0.9235") * Decimal("0.153")
                se_deduction = se_tax / 2
                deductions.append(DetectedDeduction(
                    deduction_id="se_tax_deduction",
                    name="Self-Employment Tax Deduction",
                    description="Deduct half of your self-employment tax",
                    deduction_type=DeductionType.ABOVE_THE_LINE,
                    estimated_amount=se_deduction,
                    confidence=0.95,
                    source="1099-NEC",
                    requirements=["Have self-employment income"],
                    irs_form="Schedule 1",
                    irs_line="Line 15",
                    action_required="Automatic calculation",
                ))

                # Business expenses estimate
                if user_inputs.get("has_business_expenses"):
                    estimated_expenses = se_income * Decimal("0.20")  # Conservative 20% estimate
                    deductions.append(DetectedDeduction(
                        deduction_id="business_expenses",
                        name="Business Expenses",
                        description="Deduct ordinary and necessary business expenses",
                        deduction_type=DeductionType.BUSINESS,
                        estimated_amount=estimated_expenses,
                        confidence=0.5,
                        source="Estimated from self-employment income",
                        requirements=["Ordinary and necessary for business"],
                        irs_form="Schedule C",
                        irs_line="Various",
                        action_required="Enter actual business expenses",
                    ))

        # 5. IRA Contributions (Above-the-line)
        if user_inputs.get("has_retirement_contributions"):
            ira_contrib = Decimal(str(user_inputs.get("ira_contribution", 0)))
            if ira_contrib > 0:
                max_contrib = Decimal("7000")  # 2024 limit
                capped = min(ira_contrib, max_contrib)
                deductions.append(DetectedDeduction(
                    deduction_id="ira_contribution",
                    name="Traditional IRA Contribution",
                    description="Deduct contributions to a traditional IRA",
                    deduction_type=DeductionType.ABOVE_THE_LINE,
                    estimated_amount=capped,
                    confidence=0.8,
                    source="User Input",
                    requirements=["Under 70.5 years old", "Earned income", "Check income limits if covered by workplace plan"],
                    irs_form="Schedule 1",
                    irs_line="Line 20",
                    action_required="Verify contribution and eligibility",
                ))

        # 6. Mortgage Interest (Itemized)
        if "1098" in doc_types or user_inputs.get("has_mortgage"):
            mortgage_interest = Decimal(str(extracted_data.get("mortgage_interest", 0) or user_inputs.get("mortgage_interest", 0)))
            if mortgage_interest > 0:
                deductions.append(DetectedDeduction(
                    deduction_id="mortgage_interest",
                    name="Mortgage Interest",
                    description="Deduct interest paid on your home mortgage",
                    deduction_type=DeductionType.ITEMIZED,
                    estimated_amount=mortgage_interest,
                    confidence=0.95 if "1098" in doc_types else 0.7,
                    source="1098" if "1098" in doc_types else "User Input",
                    requirements=["Mortgage on primary or secondary residence", "Loan under $750,000 limit"],
                    irs_form="Schedule A",
                    irs_line="Line 8a",
                    action_required="Verify 1098 amount",
                ))

        # 7. State and Local Taxes (Itemized) - SALT
        state_withheld = Decimal(str(extracted_data.get("state_tax_withheld", 0) or 0))
        property_tax = Decimal(str(user_inputs.get("property_tax", 0)))
        salt_total = min(state_withheld + property_tax, Decimal("10000"))  # SALT cap
        if salt_total > 0:
            deductions.append(DetectedDeduction(
                deduction_id="salt",
                name="State and Local Taxes (SALT)",
                description="Deduct state income tax and property taxes (capped at $10,000)",
                deduction_type=DeductionType.ITEMIZED,
                estimated_amount=salt_total,
                confidence=0.9 if state_withheld > 0 else 0.6,
                source="W-2 and User Input",
                requirements=["State income tax or sales tax", "Property taxes"],
                irs_form="Schedule A",
                irs_line="Line 5d",
                action_required="Add property tax if not included",
            ))

        # 8. Charitable Donations (Itemized)
        if user_inputs.get("charitable_donations"):
            donations = Decimal(str(user_inputs.get("donation_amount", 0)))
            if donations > 0:
                deductions.append(DetectedDeduction(
                    deduction_id="charitable_donations",
                    name="Charitable Contributions",
                    description="Deduct donations to qualified charitable organizations",
                    deduction_type=DeductionType.ITEMIZED,
                    estimated_amount=donations,
                    confidence=0.7,
                    source="User Input",
                    requirements=["Donation to qualified 501(c)(3) organization", "Receipt for donations $250+"],
                    irs_form="Schedule A",
                    irs_line="Line 11",
                    action_required="Gather donation receipts",
                ))

        return deductions

    def _detect_credits(
        self,
        extracted_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        filing_status: str,
        num_dependents: int,
        user_inputs: Dict[str, Any],
    ) -> List[DetectedCredit]:
        """Detect applicable tax credits."""
        credits = []
        doc_types = set(d.get("type", "") for d in documents)
        total_income = Decimal(str(extracted_data.get("wages", 0) or 0))

        # 1. Child Tax Credit
        num_children = user_inputs.get("num_children_under_17", num_dependents)
        if num_children > 0:
            # Check phase-out
            phase_out = self.CHILD_TAX_CREDIT_PHASEOUT_MFJ if filing_status == "married_joint" else self.CHILD_TAX_CREDIT_PHASEOUT_SINGLE

            if total_income <= phase_out:
                ctc_amount = self.CHILD_TAX_CREDIT_AMOUNT * num_children
                credits.append(DetectedCredit(
                    credit_id="child_tax_credit",
                    name="Child Tax Credit",
                    description=f"Up to $2,000 per qualifying child under 17",
                    credit_type=CreditType.PARTIALLY_REFUNDABLE,
                    estimated_amount=ctc_amount,
                    confidence=0.85,
                    source="User Input",
                    eligibility_factors=[
                        "Child under 17 at end of year",
                        "Child is US citizen, national, or resident alien",
                        "Child lived with you for more than half the year",
                    ],
                    phase_out_warning=None if total_income < phase_out * Decimal("0.9") else "Income approaching phase-out threshold",
                    irs_form="Schedule 8812",
                    action_required="Provide SSN for each child",
                ))

        # 2. Child and Dependent Care Credit
        if user_inputs.get("childcare_expenses"):
            care_expenses = Decimal(str(user_inputs.get("childcare_amount", 0)))
            if care_expenses > 0:
                # Max expenses: $3,000 for 1, $6,000 for 2+
                max_expenses = Decimal("6000") if num_dependents > 1 else Decimal("3000")
                qualified = min(care_expenses, max_expenses)
                # Credit is 20-35% based on income
                credit_rate = Decimal("0.20")  # Conservative estimate
                credit_amount = qualified * credit_rate
                credits.append(DetectedCredit(
                    credit_id="child_dependent_care",
                    name="Child and Dependent Care Credit",
                    description="Credit for work-related childcare expenses",
                    credit_type=CreditType.NONREFUNDABLE,
                    estimated_amount=credit_amount,
                    confidence=0.7,
                    source="User Input",
                    eligibility_factors=[
                        "Care for qualifying child under 13 or disabled dependent",
                        "Care to allow you (and spouse) to work",
                        "Care provider not your spouse or parent",
                    ],
                    phase_out_warning=None,
                    irs_form="Form 2441",
                    action_required="Provide care provider's name, address, and EIN/SSN",
                ))

        # 3. Education Credits
        if "1098_t" in doc_types or user_inputs.get("has_education_expenses"):
            education_expenses = Decimal(str(extracted_data.get("amounts_billed", 0) or user_inputs.get("education_expenses", 0)))
            if education_expenses > 0:
                # American Opportunity Credit - up to $2,500
                aotc = min(education_expenses, Decimal("4000")) * Decimal("0.625")  # Simplified calc
                aotc = min(aotc, Decimal("2500"))
                credits.append(DetectedCredit(
                    credit_id="american_opportunity",
                    name="American Opportunity Tax Credit",
                    description="Up to $2,500 per student for first 4 years of college",
                    credit_type=CreditType.PARTIALLY_REFUNDABLE,
                    estimated_amount=aotc,
                    confidence=0.8 if "1098_t" in doc_types else 0.6,
                    source="1098-T" if "1098_t" in doc_types else "User Input",
                    eligibility_factors=[
                        "Student pursuing degree or credential",
                        "Enrolled at least half-time",
                        "First 4 years of post-secondary education",
                        "No felony drug conviction",
                    ],
                    phase_out_warning="Phases out at $80K single / $160K MFJ",
                    irs_form="Form 8863",
                    action_required="Verify enrollment status and expenses",
                ))

        # 4. Saver's Credit
        if user_inputs.get("has_retirement_contributions"):
            contribution = Decimal(str(user_inputs.get("ira_contribution", 0) or user_inputs.get("401k_contribution", 0)))
            if contribution > 0 and total_income < Decimal("36500"):  # Single threshold
                # Credit is 10-50% of up to $2,000
                max_contrib = Decimal("2000")
                qualified = min(contribution, max_contrib)
                credit_rate = Decimal("0.10")  # Conservative
                credits.append(DetectedCredit(
                    credit_id="savers_credit",
                    name="Saver's Credit",
                    description="Credit for retirement contributions by low-to-moderate income",
                    credit_type=CreditType.NONREFUNDABLE,
                    estimated_amount=qualified * credit_rate,
                    confidence=0.7,
                    source="User Input",
                    eligibility_factors=[
                        "Age 18 or older",
                        "Not a full-time student",
                        "Not claimed as dependent",
                        "Income under $36,500 single / $73,000 MFJ",
                    ],
                    phase_out_warning="Credit rate depends on income",
                    irs_form="Form 8880",
                    action_required="Verify contribution amount",
                ))

        # 5. Earned Income Tax Credit (EITC)
        # Only for lower income
        if total_income < Decimal("63398") and total_income > 0:
            # Simplified EITC estimate
            investment_income = Decimal(str(extracted_data.get("interest_income", 0) or 0)) + Decimal(str(extracted_data.get("ordinary_dividends", 0) or 0))
            if investment_income <= self.EITC_MAX_INVESTMENT_INCOME:
                # Very rough estimate - actual depends on many factors
                if num_children >= 3:
                    max_eitc = Decimal("7830")
                elif num_children == 2:
                    max_eitc = Decimal("6960")
                elif num_children == 1:
                    max_eitc = Decimal("4213")
                else:
                    max_eitc = Decimal("632")

                # Estimate based on income (very simplified)
                eitc_estimate = max_eitc * Decimal("0.5")  # Conservative

                credits.append(DetectedCredit(
                    credit_id="eitc",
                    name="Earned Income Tax Credit (EITC)",
                    description="Refundable credit for low-to-moderate income workers",
                    credit_type=CreditType.REFUNDABLE,
                    estimated_amount=eitc_estimate,
                    confidence=0.5,  # Low confidence - needs detailed calculation
                    source="Income Analysis",
                    eligibility_factors=[
                        "Earned income from working",
                        "Investment income under $11,600",
                        "US citizen or resident alien all year",
                        "Valid SSN for you, spouse, and qualifying children",
                    ],
                    phase_out_warning="Amount varies significantly based on exact income and number of children",
                    irs_form="Schedule EIC",
                    action_required="Complete detailed EITC worksheet",
                ))

        return credits

    def _find_missed_opportunities(
        self,
        extracted_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        filing_status: str,
        num_dependents: int,
        user_inputs: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Identify potential missed opportunities."""
        opportunities = []
        total_income = Decimal(str(extracted_data.get("wages", 0) or 0))

        # 1. Check if should consider Head of Household
        if filing_status == "single" and num_dependents > 0:
            opportunities.append({
                "opportunity": "Head of Household Filing Status",
                "description": "You may qualify for Head of Household status if you're unmarried and paid more than half the cost of keeping up a home for a qualifying person.",
                "potential_benefit": "Higher standard deduction ($21,900 vs $14,600) and more favorable tax brackets",
                "action": "Review HOH requirements",
            })

        # 2. Check for missing retirement contributions
        if not user_inputs.get("has_retirement_contributions") and total_income > Decimal("40000"):
            max_ira = Decimal("7000")
            tax_rate = self._get_marginal_rate(total_income, filing_status)
            savings = max_ira * tax_rate
            opportunities.append({
                "opportunity": "Traditional IRA Contribution",
                "description": "You could reduce your taxable income by contributing to a traditional IRA.",
                "potential_benefit": f"Up to ${float(savings):.0f} in tax savings if you contribute the full ${float(max_ira):.0f}",
                "action": "Contribute to IRA before tax deadline (April 15)",
            })

        # 3. Check for missing HSA contributions
        if not user_inputs.get("has_hsa") and total_income > Decimal("50000"):
            opportunities.append({
                "opportunity": "Health Savings Account (HSA)",
                "description": "If you have a high-deductible health plan, HSA contributions are tax-deductible.",
                "potential_benefit": "Up to $4,150 individual / $8,300 family deduction",
                "action": "Check if you're enrolled in an HDHP and can contribute",
            })

        # 4. Check for bunching strategy
        itemizable = Decimal(str(user_inputs.get("mortgage_interest", 0))) + Decimal(str(user_inputs.get("donation_amount", 0)))
        standard = self.STANDARD_DEDUCTIONS_2025.get(filing_status, Decimal("15750"))
        if itemizable > standard * Decimal("0.7") and itemizable < standard:
            opportunities.append({
                "opportunity": "Deduction Bunching Strategy",
                "description": "Your itemized deductions are close to the standard deduction. Consider bunching deductions in alternate years.",
                "potential_benefit": "Itemize one year, take standard the next to maximize total deductions",
                "action": "Consider prepaying mortgage interest or making charitable donations",
            })

        return opportunities

    def _get_marginal_rate(self, income: Decimal, filing_status: str) -> Decimal:
        """Get estimated marginal tax rate."""
        # Simplified - uses single brackets for all
        standard = self.STANDARD_DEDUCTIONS_2025.get(filing_status, Decimal("15750"))
        taxable = max(income - standard, Decimal("0"))

        for threshold, rate in self.TAX_BRACKETS_SINGLE:
            if taxable <= threshold:
                return rate

        return Decimal("0.37")


def analyze_deductions(
    extracted_data: Dict[str, Any],
    documents: List[Dict[str, Any]],
    filing_status: str = "single",
    num_dependents: int = 0,
    user_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function for deduction analysis.

    Returns dict ready for API response.
    """
    detector = SmartDeductionDetector()
    analysis = detector.analyze(
        extracted_data=extracted_data,
        documents=documents,
        filing_status=filing_status,
        num_dependents=num_dependents,
        user_inputs=user_inputs,
    )
    return analysis.to_dict()
