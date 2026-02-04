"""
Tax Opportunity Detector - AI-Powered Tax Savings Identification.

Proactively identifies tax-saving opportunities based on taxpayer profile.
This implements multi-function AI routing for intelligent analysis.

Resolves Audit Finding: "AI is Severely Underutilized (Biggest Opportunity)"
"""

from __future__ import annotations

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpportunityCategory(Enum):
    """Categories of tax-saving opportunities."""
    DEDUCTION = "deduction"
    CREDIT = "credit"
    RETIREMENT = "retirement"
    BUSINESS = "business"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    INVESTMENT = "investment"
    TIMING = "timing"
    FILING_STATUS = "filing_status"


class OpportunityPriority(Enum):
    """Priority levels for opportunities."""
    HIGH = "high"  # Immediate action, high savings
    MEDIUM = "medium"  # Good savings, worth exploring
    LOW = "low"  # Minor savings, nice to have


@dataclass
class TaxOpportunity:
    """A detected tax-saving opportunity."""
    id: str
    title: str
    description: str
    category: OpportunityCategory
    priority: OpportunityPriority
    estimated_savings: Optional[Decimal] = None
    savings_range: Optional[Tuple[Decimal, Decimal]] = None  # (min, max)
    action_required: str = ""
    irs_reference: Optional[str] = None  # IRS pub or form reference
    deadline: Optional[str] = None  # If time-sensitive
    confidence: float = 0.8  # 0-1 confidence score
    prerequisites: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)


@dataclass
class TaxpayerProfile:
    """Taxpayer profile for opportunity analysis."""
    # Basic info
    filing_status: str = "single"
    age: int = 35
    spouse_age: Optional[int] = None

    # Income
    w2_wages: Decimal = Decimal("0")
    self_employment_income: Decimal = Decimal("0")
    business_income: Decimal = Decimal("0")
    interest_income: Decimal = Decimal("0")
    dividend_income: Decimal = Decimal("0")
    capital_gains: Decimal = Decimal("0")
    rental_income: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")

    # Withholding
    federal_withheld: Decimal = Decimal("0")

    # Deductions already claimed
    mortgage_interest: Decimal = Decimal("0")
    property_taxes: Decimal = Decimal("0")
    state_local_taxes: Decimal = Decimal("0")
    charitable_contributions: Decimal = Decimal("0")
    medical_expenses: Decimal = Decimal("0")
    student_loan_interest: Decimal = Decimal("0")

    # Retirement
    traditional_401k: Decimal = Decimal("0")
    roth_401k: Decimal = Decimal("0")
    traditional_ira: Decimal = Decimal("0")
    roth_ira: Decimal = Decimal("0")
    hsa_contribution: Decimal = Decimal("0")

    # Family
    num_dependents: int = 0
    has_children_under_17: bool = False
    has_children_under_13: bool = False
    has_college_students: bool = False

    # Home
    owns_home: bool = False
    home_purchase_year: Optional[int] = None
    has_home_office: bool = False

    # Health
    has_hdhp: bool = False  # High Deductible Health Plan

    # Business
    has_business: bool = False
    business_type: Optional[str] = None
    is_sstb: Optional[bool] = None  # Specified Service Trade or Business
    business_net_income: Decimal = Decimal("0")

    # Education
    education_expenses: Decimal = Decimal("0")

    # Life events this year
    got_married: bool = False
    had_baby: bool = False
    bought_home: bool = False
    started_business: bool = False
    changed_jobs: bool = False

    @property
    def total_income(self) -> Decimal:
        """Calculate total gross income."""
        return (
            self.w2_wages + self.self_employment_income + self.business_income +
            self.interest_income + self.dividend_income + self.capital_gains +
            self.rental_income + self.other_income
        )

    @property
    def agi_estimate(self) -> Decimal:
        """Estimate AGI (simplified)."""
        above_line_deductions = (
            self.traditional_401k + self.traditional_ira +
            self.hsa_contribution + self.student_loan_interest
        )
        return max(Decimal("0"), self.total_income - above_line_deductions)


class TaxOpportunityDetector:
    """
    AI-powered tax opportunity detector.

    Uses multi-function calling to:
    1. Analyze taxpayer profile
    2. Identify missed deductions
    3. Find eligible credits
    4. Recommend tax-saving strategies
    5. Provide personalized action items
    """

    # 2025 Tax Constants
    TAX_YEAR = 2025

    # Standard deductions 2025
    STANDARD_DEDUCTION = {
        "single": Decimal("15000"),
        "married_filing_jointly": Decimal("30000"),
        "married_filing_separately": Decimal("15000"),
        "head_of_household": Decimal("22500"),
        "qualifying_widow": Decimal("30000"),
    }

    # Contribution limits 2025
    CONTRIB_LIMITS = {
        "401k": Decimal("23500"),
        "401k_catchup": Decimal("7500"),  # Age 50+
        "ira": Decimal("7000"),
        "ira_catchup": Decimal("1000"),  # Age 50+
        "hsa_individual": Decimal("4300"),
        "hsa_family": Decimal("8550"),
        "hsa_catchup": Decimal("1000"),  # Age 55+
    }

    # SALT cap
    SALT_CAP = Decimal("10000")

    # Child Tax Credit
    CHILD_TAX_CREDIT = Decimal("2000")  # Per child under 17

    # EITC thresholds vary by children
    EITC_MAX = {
        0: Decimal("632"),
        1: Decimal("4213"),
        2: Decimal("6960"),
        3: Decimal("7830"),  # 3 or more
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize detector with OpenAI client."""
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        else:
            self.client = None
            self.model = None
            logger.warning("No OpenAI API key - running in rule-based mode only")

    def detect_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """
        Detect all tax-saving opportunities for a taxpayer.

        Uses both rule-based detection and AI analysis.
        """
        opportunities = []

        # Rule-based detection (fast, reliable)
        opportunities.extend(self._detect_retirement_opportunities(profile))
        opportunities.extend(self._detect_deduction_opportunities(profile))
        opportunities.extend(self._detect_credit_opportunities(profile))
        opportunities.extend(self._detect_hsa_opportunities(profile))
        opportunities.extend(self._detect_business_opportunities(profile))
        opportunities.extend(self._detect_education_opportunities(profile))
        opportunities.extend(self._detect_filing_status_opportunities(profile))
        opportunities.extend(self._detect_timing_opportunities(profile))

        # AI-powered analysis for nuanced opportunities
        if self.client:
            ai_opportunities = self._ai_detect_opportunities(profile)
            opportunities.extend(ai_opportunities)

        # Sort by priority and estimated savings
        opportunities.sort(
            key=lambda o: (
                0 if o.priority == OpportunityPriority.HIGH else
                1 if o.priority == OpportunityPriority.MEDIUM else 2,
                -(o.estimated_savings or Decimal("0"))
            )
        )

        return opportunities

    def _detect_retirement_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect retirement contribution opportunities."""
        opportunities = []

        # 401(k) under-contribution
        max_401k = self.CONTRIB_LIMITS["401k"]
        if profile.age >= 50:
            max_401k += self.CONTRIB_LIMITS["401k_catchup"]

        current_401k = profile.traditional_401k + profile.roth_401k
        if current_401k < max_401k and profile.total_income > Decimal("50000"):
            room = max_401k - current_401k
            # Estimate tax savings at 22% marginal rate
            estimated_savings = room * Decimal("0.22")

            opportunities.append(TaxOpportunity(
                id="retirement_401k_room",
                title="Maximize 401(k) Contribution",
                description=f"You have ${room:,.0f} in unused 401(k) contribution room for {self.TAX_YEAR}. "
                           f"Contributing the maximum reduces your taxable income.",
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=estimated_savings,
                action_required="Increase 401(k) contribution through your employer's payroll",
                irs_reference="IRS Publication 560",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.95,
                follow_up_questions=[
                    "Does your employer offer a 401(k) match?",
                    "What percentage are you currently contributing?"
                ]
            ))

        # IRA opportunity
        max_ira = self.CONTRIB_LIMITS["ira"]
        if profile.age >= 50:
            max_ira += self.CONTRIB_LIMITS["ira_catchup"]

        current_ira = profile.traditional_ira + profile.roth_ira
        if current_ira < max_ira and profile.total_income > Decimal("30000"):
            room = max_ira - current_ira
            estimated_savings = room * Decimal("0.22")

            opportunities.append(TaxOpportunity(
                id="retirement_ira_room",
                title="Contribute to IRA",
                description=f"You can contribute up to ${max_ira:,.0f} to an IRA for {self.TAX_YEAR}. "
                           f"Traditional IRA contributions may be tax-deductible.",
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH if room > Decimal("5000") else OpportunityPriority.MEDIUM,
                estimated_savings=estimated_savings,
                action_required="Open or contribute to an IRA before the tax filing deadline",
                irs_reference="IRS Publication 590-A",
                deadline=f"April 15, {self.TAX_YEAR + 1}",
                confidence=0.90,
                prerequisites=["Must have earned income"],
                follow_up_questions=[
                    "Do you already have an IRA?",
                    "Traditional or Roth - which is better for your situation?"
                ]
            ))

        return opportunities

    def _detect_hsa_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect HSA contribution opportunities."""
        opportunities = []

        if profile.has_hdhp:
            # Determine HSA limit based on coverage type
            is_family = profile.filing_status in ["married_filing_jointly", "head_of_household"] or profile.num_dependents > 0
            max_hsa = self.CONTRIB_LIMITS["hsa_family"] if is_family else self.CONTRIB_LIMITS["hsa_individual"]

            if profile.age >= 55:
                max_hsa += self.CONTRIB_LIMITS["hsa_catchup"]

            if profile.hsa_contribution < max_hsa:
                room = max_hsa - profile.hsa_contribution
                # HSA is triple tax-advantaged
                estimated_savings = room * Decimal("0.30")  # Federal + FICA

                opportunities.append(TaxOpportunity(
                    id="hsa_maximize",
                    title="Maximize HSA Contribution",
                    description=f"HSAs offer triple tax advantages: tax-deductible, tax-free growth, and tax-free withdrawals for medical expenses. "
                               f"You have ${room:,.0f} in unused contribution room.",
                    category=OpportunityCategory.HEALTHCARE,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=estimated_savings,
                    action_required="Contribute to your HSA before year-end or by April 15 for prior year",
                    irs_reference="IRS Publication 969",
                    deadline=f"April 15, {self.TAX_YEAR + 1}",
                    confidence=0.95,
                    follow_up_questions=["Do you have an HSA account set up?"]
                ))
        elif profile.total_income > Decimal("40000"):
            # Suggest HDHP + HSA if they don't have one
            opportunities.append(TaxOpportunity(
                id="hsa_consider",
                title="Consider High-Deductible Health Plan with HSA",
                description="If eligible, an HDHP with HSA can provide significant tax savings through "
                           "tax-deductible contributions and tax-free growth.",
                category=OpportunityCategory.HEALTHCARE,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("1000"), Decimal("3000")),
                action_required="Review health plan options during open enrollment",
                irs_reference="IRS Publication 969",
                confidence=0.70,
                follow_up_questions=[
                    "What type of health insurance do you currently have?",
                    "Do you have significant medical expenses?"
                ]
            ))

        return opportunities

    def _detect_deduction_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect missed deduction opportunities."""
        opportunities = []

        # Standard vs. Itemized analysis
        standard = self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000"))

        current_itemized = (
            profile.mortgage_interest +
            min(profile.property_taxes + profile.state_local_taxes, self.SALT_CAP) +
            profile.charitable_contributions +
            max(Decimal("0"), profile.medical_expenses - profile.agi_estimate * Decimal("0.075"))
        )

        itemized_benefit = current_itemized - standard

        if itemized_benefit > Decimal("0"):
            opportunities.append(TaxOpportunity(
                id="itemize_deductions",
                title="Consider Itemizing Deductions",
                description=f"Your itemized deductions (${current_itemized:,.0f}) exceed the standard deduction "
                           f"(${standard:,.0f}) by ${itemized_benefit:,.0f}. Itemizing will reduce your taxes.",
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.HIGH,
                estimated_savings=itemized_benefit * Decimal("0.22"),
                action_required="File Schedule A with itemized deductions",
                irs_reference="Schedule A (Form 1040)",
                confidence=0.95
            ))
        elif itemized_benefit > Decimal("-2000") and profile.charitable_contributions > 0:
            # Close to itemizing - bunching strategy
            gap = standard - current_itemized
            opportunities.append(TaxOpportunity(
                id="deduction_bunching",
                title="Deduction Bunching Strategy",
                description=f"You're ${gap:,.0f} away from itemizing. Consider 'bunching' deductions - "
                           f"prepaying property taxes or making charitable contributions before year-end to itemize this year.",
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=gap * Decimal("0.22"),
                action_required="Prepay deductible expenses before December 31",
                irs_reference="IRS Publication 17",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.80,
                follow_up_questions=[
                    "Can you prepay your property taxes?",
                    "Do you plan to make any charitable contributions?"
                ]
            ))

        # Student loan interest (above the line)
        if profile.student_loan_interest == 0 and profile.agi_estimate < Decimal("90000"):
            opportunities.append(TaxOpportunity(
                id="student_loan_interest",
                title="Student Loan Interest Deduction",
                description="If you paid student loan interest this year, you may deduct up to $2,500. "
                           "This is an 'above-the-line' deduction, meaning you can claim it even with the standard deduction.",
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("100"), Decimal("550")),
                action_required="Report student loan interest from Form 1098-E",
                irs_reference="IRS Publication 970",
                confidence=0.60,
                follow_up_questions=["Do you have student loans?", "Did you pay any interest this year?"]
            ))

        return opportunities

    def _detect_credit_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect tax credit opportunities."""
        opportunities = []

        # Child Tax Credit
        if profile.has_children_under_17:
            estimated_credit = self.CHILD_TAX_CREDIT * profile.num_dependents
            opportunities.append(TaxOpportunity(
                id="child_tax_credit",
                title="Child Tax Credit",
                description=f"You may qualify for up to ${self.CHILD_TAX_CREDIT:,.0f} per qualifying child under 17. "
                           f"With {profile.num_dependents} children, potential credit: ${estimated_credit:,.0f}.",
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=estimated_credit,
                action_required="Claim on Form 1040 and Schedule 8812 if applicable",
                irs_reference="IRS Publication 972",
                confidence=0.90,
                prerequisites=["Children must have SSN", "Income limits apply"]
            ))

        # Child and Dependent Care Credit
        if profile.has_children_under_13 and (profile.w2_wages > 0 or profile.self_employment_income > 0):
            max_credit = Decimal("1050") if profile.num_dependents == 1 else Decimal("2100")
            opportunities.append(TaxOpportunity(
                id="dependent_care_credit",
                title="Child and Dependent Care Credit",
                description="If you paid for childcare to work or look for work, you may claim a credit "
                           f"of up to ${max_credit:,.0f}.",
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=max_credit,
                action_required="File Form 2441 with your tax return",
                irs_reference="IRS Publication 503",
                confidence=0.85,
                follow_up_questions=[
                    "Did you pay for daycare or after-school care?",
                    "Do you have receipts with the provider's tax ID?"
                ]
            ))

        # EITC
        eitc_income_limit = {
            "single": Decimal("59899"),
            "married_filing_jointly": Decimal("66819"),
            "head_of_household": Decimal("59899"),
        }

        if profile.filing_status in eitc_income_limit:
            limit = eitc_income_limit[profile.filing_status]
            if profile.agi_estimate < limit and (profile.w2_wages > 0 or profile.self_employment_income > 0):
                children_key = min(profile.num_dependents, 3)
                max_eitc = self.EITC_MAX[children_key]

                opportunities.append(TaxOpportunity(
                    id="eitc",
                    title="Earned Income Tax Credit (EITC)",
                    description=f"Based on your income and family size, you may qualify for EITC of up to ${max_eitc:,.0f}. "
                               f"This is a refundable credit - you can get it even if you owe no tax.",
                    category=OpportunityCategory.CREDIT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=max_eitc,
                    action_required="File Schedule EIC with your tax return",
                    irs_reference="IRS Publication 596",
                    confidence=0.75,
                    prerequisites=["Must have earned income", "Investment income limit applies"]
                ))

        # Saver's Credit
        if profile.agi_estimate < Decimal("76500") and profile.filing_status == "married_filing_jointly":
            if profile.traditional_401k + profile.roth_401k + profile.traditional_ira + profile.roth_ira > 0:
                max_credit = Decimal("2000") if profile.filing_status == "married_filing_jointly" else Decimal("1000")
                opportunities.append(TaxOpportunity(
                    id="savers_credit",
                    title="Saver's Credit",
                    description="You may qualify for a credit of up to 50% of your retirement contributions "
                               f"(max ${max_credit:,.0f}) based on your income level.",
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.MEDIUM,
                    estimated_savings=max_credit,
                    action_required="File Form 8880 with your tax return",
                    irs_reference="IRS Form 8880",
                    confidence=0.80
                ))

        return opportunities

    def _detect_business_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect business-related opportunities."""
        opportunities = []

        if not profile.has_business and profile.self_employment_income == 0:
            return opportunities

        # QBI Deduction (Section 199A)
        qbi_eligible_income = profile.business_net_income or profile.self_employment_income
        if qbi_eligible_income > 0:
            # SSTB limitation check
            if profile.is_sstb and profile.agi_estimate > Decimal("191950"):
                opportunities.append(TaxOpportunity(
                    id="qbi_sstb_warning",
                    title="QBI Deduction Phase-Out (SSTB)",
                    description="As a Specified Service Trade or Business (SSTB), your QBI deduction "
                               "begins to phase out at your income level. Consider strategies to stay below the threshold.",
                    category=OpportunityCategory.BUSINESS,
                    priority=OpportunityPriority.MEDIUM,
                    action_required="Consider timing income/expenses to manage AGI",
                    irs_reference="IRC Section 199A",
                    confidence=0.85
                ))
            else:
                qbi_deduction = qbi_eligible_income * Decimal("0.20")
                opportunities.append(TaxOpportunity(
                    id="qbi_deduction",
                    title="Qualified Business Income (QBI) Deduction",
                    description=f"You may be eligible for a 20% deduction on qualified business income. "
                               f"Estimated deduction: ${qbi_deduction:,.0f}.",
                    category=OpportunityCategory.BUSINESS,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=qbi_deduction * Decimal("0.22"),
                    action_required="This is calculated automatically on Form 8995 or 8995-A",
                    irs_reference="IRS Form 8995",
                    confidence=0.90
                ))

        # Home Office Deduction
        if profile.has_home_office or profile.has_business:
            opportunities.append(TaxOpportunity(
                id="home_office",
                title="Home Office Deduction",
                description="If you use part of your home regularly and exclusively for business, "
                           "you can deduct home office expenses. Simplified method: $5/sq ft up to 300 sq ft ($1,500 max).",
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("500"), Decimal("1500")),
                action_required="Calculate using Form 8829 or simplified method",
                irs_reference="IRS Publication 587",
                confidence=0.75,
                follow_up_questions=[
                    "What is the square footage of your home office?",
                    "Is this space used exclusively for business?"
                ]
            ))

        # Self-Employment Tax Deduction
        if profile.self_employment_income > Decimal("400"):
            se_tax = profile.self_employment_income * Decimal("0.153")
            deduction = se_tax * Decimal("0.5")
            opportunities.append(TaxOpportunity(
                id="se_tax_deduction",
                title="Self-Employment Tax Deduction",
                description=f"You can deduct 50% of your self-employment tax (${deduction:,.0f}) "
                           "as an above-the-line deduction.",
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=deduction * Decimal("0.22"),
                action_required="This is calculated automatically on Schedule SE and Form 1040",
                irs_reference="Schedule SE",
                confidence=0.95
            ))

        # SEP-IRA for Self-Employed
        if profile.self_employment_income > Decimal("10000"):
            max_sep = min(profile.self_employment_income * Decimal("0.25"), Decimal("69000"))
            if profile.traditional_401k == 0:  # No employer 401k
                opportunities.append(TaxOpportunity(
                    id="sep_ira",
                    title="SEP-IRA for Self-Employed",
                    description=f"As a self-employed individual, you can contribute up to 25% of net self-employment "
                               f"earnings (max ${max_sep:,.0f}) to a SEP-IRA, reducing your taxable income.",
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=max_sep * Decimal("0.22"),
                    action_required="Open SEP-IRA and contribute by tax filing deadline (with extensions)",
                    irs_reference="IRS Publication 560",
                    deadline=f"October 15, {self.TAX_YEAR + 1} (with extension)",
                    confidence=0.90
                ))

        return opportunities

    def _detect_education_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect education-related opportunities."""
        opportunities = []

        if profile.has_college_students or profile.education_expenses > 0:
            # American Opportunity Credit
            opportunities.append(TaxOpportunity(
                id="aotc",
                title="American Opportunity Tax Credit",
                description="For the first 4 years of college, you may claim up to $2,500 per eligible student. "
                           "40% ($1,000) is refundable even if you owe no tax.",
                category=OpportunityCategory.EDUCATION,
                priority=OpportunityPriority.HIGH,
                estimated_savings=Decimal("2500"),
                action_required="File Form 8863 with your tax return",
                irs_reference="IRS Publication 970",
                confidence=0.85,
                prerequisites=["Student must be in first 4 years of higher education", "Income limits apply"],
                follow_up_questions=[
                    "What year of college is your student in?",
                    "Do you have Form 1098-T from the school?"
                ]
            ))

            # Lifetime Learning Credit
            opportunities.append(TaxOpportunity(
                id="llc",
                title="Lifetime Learning Credit",
                description="If not eligible for AOTC, you may claim up to $2,000 per tax return for "
                           "post-secondary education expenses.",
                category=OpportunityCategory.EDUCATION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=Decimal("2000"),
                action_required="File Form 8863 (choose either AOTC or LLC, not both for same student)",
                irs_reference="IRS Publication 970",
                confidence=0.75
            ))

        return opportunities

    def _detect_filing_status_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect filing status optimization opportunities."""
        opportunities = []

        # Head of Household analysis
        if profile.filing_status == "single" and profile.num_dependents > 0:
            standard_single = self.STANDARD_DEDUCTION["single"]
            standard_hoh = self.STANDARD_DEDUCTION["head_of_household"]
            benefit = standard_hoh - standard_single

            opportunities.append(TaxOpportunity(
                id="consider_hoh",
                title="Consider Head of Household Status",
                description=f"If you're unmarried and pay more than half the cost of keeping up a home for a qualifying person, "
                           f"you may file as Head of Household. This gives you a ${benefit:,.0f} higher standard deduction "
                           f"and more favorable tax brackets.",
                category=OpportunityCategory.FILING_STATUS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=benefit * Decimal("0.22"),
                action_required="Review Head of Household requirements",
                irs_reference="IRS Publication 501",
                confidence=0.70,
                follow_up_questions=[
                    "Did you pay more than half the cost of keeping up your home?",
                    "Does a qualifying person live with you?"
                ]
            ))

        # MFJ vs MFS analysis
        if profile.filing_status == "married_filing_jointly" and profile.spouse_age:
            opportunities.append(TaxOpportunity(
                id="mfj_vs_mfs",
                title="Compare Joint vs. Separate Filing",
                description="In most cases, Married Filing Jointly is better. However, filing separately may help "
                           "if you have income-based student loan payments, medical expenses >7.5% of AGI, "
                           "or want to separate liability.",
                category=OpportunityCategory.FILING_STATUS,
                priority=OpportunityPriority.LOW,
                action_required="Calculate taxes both ways to compare",
                irs_reference="IRS Publication 501",
                confidence=0.60,
                follow_up_questions=[
                    "Are you on an income-driven student loan repayment plan?",
                    "Do either of you have significant medical expenses?"
                ]
            ))

        return opportunities

    def _detect_timing_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect timing-related opportunities."""
        opportunities = []
        current_month = datetime.now().month

        if current_month >= 10:  # Q4 - year-end planning time
            # Tax-loss harvesting
            if profile.capital_gains > Decimal("3000"):
                opportunities.append(TaxOpportunity(
                    id="tax_loss_harvest",
                    title="Tax-Loss Harvesting",
                    description="If you have investments with losses, consider selling them to offset "
                               f"your ${profile.capital_gains:,.0f} in capital gains. You can deduct up to $3,000 "
                               "in excess losses against ordinary income.",
                    category=OpportunityCategory.INVESTMENT,
                    priority=OpportunityPriority.MEDIUM,
                    action_required="Review investment portfolio for loss positions before year-end",
                    deadline=f"December 31, {self.TAX_YEAR}",
                    irs_reference="IRS Publication 550",
                    confidence=0.75,
                    follow_up_questions=["Do you have any investments currently at a loss?"]
                ))

            # Charitable giving reminder
            if profile.charitable_contributions == 0 and profile.agi_estimate > Decimal("75000"):
                opportunities.append(TaxOpportunity(
                    id="charitable_yearend",
                    title="Year-End Charitable Giving",
                    description="Charitable contributions before December 31 can reduce this year's taxes. "
                               "Consider donating appreciated stock to avoid capital gains tax.",
                    category=OpportunityCategory.DEDUCTION,
                    priority=OpportunityPriority.MEDIUM,
                    action_required="Make donations before year-end and keep receipts",
                    deadline=f"December 31, {self.TAX_YEAR}",
                    irs_reference="IRS Publication 526",
                    confidence=0.70
                ))

        return opportunities

    def _ai_detect_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Use AI to detect nuanced opportunities that rules might miss."""
        opportunities = []

        if not self.client:
            return opportunities

        # Define multi-function schema for comprehensive analysis
        functions = [
            {
                "name": "identify_tax_opportunities",
                "description": "Identify personalized tax-saving opportunities based on taxpayer profile",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "opportunities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "category": {
                                        "type": "string",
                                        "enum": ["deduction", "credit", "retirement", "business",
                                                "education", "healthcare", "real_estate", "investment", "timing"]
                                    },
                                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                                    "estimated_savings_min": {"type": "number"},
                                    "estimated_savings_max": {"type": "number"},
                                    "action_required": {"type": "string"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                                },
                                "required": ["title", "description", "category", "priority", "action_required"]
                            }
                        }
                    },
                    "required": ["opportunities"]
                }
            }
        ]

        # Build profile summary for AI
        profile_summary = f"""
Taxpayer Profile for {self.TAX_YEAR}:
- Filing Status: {profile.filing_status}
- Age: {profile.age}
- Total Income: ${profile.total_income:,.0f}
  - W-2 Wages: ${profile.w2_wages:,.0f}
  - Self-Employment: ${profile.self_employment_income:,.0f}
  - Business Income: ${profile.business_income:,.0f}
  - Investment Income: ${profile.interest_income + profile.dividend_income + profile.capital_gains:,.0f}
- Estimated AGI: ${profile.agi_estimate:,.0f}
- Dependents: {profile.num_dependents}
- Owns Home: {profile.owns_home}
- Has Business: {profile.has_business}
- Business Type: {profile.business_type or 'N/A'}
- Current Retirement Contributions: ${profile.traditional_401k + profile.traditional_ira:,.0f}
- HSA Contribution: ${profile.hsa_contribution:,.0f}
- Has HDHP: {profile.has_hdhp}

Life Events This Year:
- Got Married: {profile.got_married}
- Had Baby: {profile.had_baby}
- Bought Home: {profile.bought_home}
- Started Business: {profile.started_business}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a tax expert identifying personalized tax-saving opportunities. "
                                  "Focus on actionable opportunities that could save the taxpayer money. "
                                  "Be specific and practical. Include opportunities that may not be obvious."
                    },
                    {
                        "role": "user",
                        "content": f"Based on this taxpayer profile, identify tax-saving opportunities:\n{profile_summary}"
                    }
                ],
                functions=functions,
                function_call={"name": "identify_tax_opportunities"},
                temperature=0.3
            )

            if response.choices[0].message.function_call:
                result = json.loads(response.choices[0].message.function_call.arguments)

                for opp_data in result.get("opportunities", []):
                    # Create unique ID
                    opp_id = f"ai_{opp_data['category']}_{hash(opp_data['title']) % 10000}"

                    savings = None
                    savings_range = None
                    if opp_data.get("estimated_savings_min") and opp_data.get("estimated_savings_max"):
                        savings_range = (
                            Decimal(str(opp_data["estimated_savings_min"])),
                            Decimal(str(opp_data["estimated_savings_max"]))
                        )
                        savings = (savings_range[0] + savings_range[1]) / 2

                    opportunities.append(TaxOpportunity(
                        id=opp_id,
                        title=opp_data["title"],
                        description=opp_data["description"],
                        category=OpportunityCategory(opp_data["category"]),
                        priority=OpportunityPriority(opp_data["priority"]),
                        estimated_savings=savings,
                        savings_range=savings_range,
                        action_required=opp_data["action_required"],
                        confidence=opp_data.get("confidence", 0.7)
                    ))

        except Exception as e:
            logger.error(f"AI opportunity detection failed: {e}")

        return opportunities

    def get_opportunity_summary(self, opportunities: List[TaxOpportunity]) -> Dict[str, Any]:
        """Get summary of detected opportunities."""
        total_savings = Decimal("0")
        min_savings = Decimal("0")
        max_savings = Decimal("0")

        by_category = {}
        by_priority = {"high": [], "medium": [], "low": []}

        for opp in opportunities:
            # Aggregate savings
            if opp.estimated_savings:
                total_savings += opp.estimated_savings
            if opp.savings_range:
                min_savings += opp.savings_range[0]
                max_savings += opp.savings_range[1]

            # Group by category
            cat = opp.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(opp.title)

            # Group by priority
            by_priority[opp.priority.value].append(opp.title)

        return {
            "total_opportunities": len(opportunities),
            "estimated_total_savings": float(total_savings),
            "savings_range": {
                "min": float(min_savings),
                "max": float(max_savings)
            },
            "high_priority_count": len(by_priority["high"]),
            "by_category": by_category,
            "by_priority": by_priority,
            "top_opportunities": [
                {"title": o.title, "savings": float(o.estimated_savings or 0)}
                for o in opportunities[:5]
            ]
        }

    def format_opportunities_for_chat(self, opportunities: List[TaxOpportunity], limit: int = 5) -> str:
        """Format opportunities for display in chat interface."""
        if not opportunities:
            return "No specific tax-saving opportunities identified based on your current information."

        lines = ["**💰 Tax-Saving Opportunities Detected:**\n"]

        # Show top opportunities
        for i, opp in enumerate(opportunities[:limit], 1):
            priority_emoji = "🔴" if opp.priority == OpportunityPriority.HIGH else "🟡" if opp.priority == OpportunityPriority.MEDIUM else "🟢"

            savings_str = ""
            if opp.estimated_savings:
                savings_str = f" (Est. savings: ${opp.estimated_savings:,.0f})"
            elif opp.savings_range:
                savings_str = f" (Est. savings: ${opp.savings_range[0]:,.0f}-${opp.savings_range[1]:,.0f})"

            lines.append(f"{i}. {priority_emoji} **{opp.title}**{savings_str}")
            lines.append(f"   {opp.description[:150]}...")
            lines.append(f"   → Action: {opp.action_required}")
            lines.append("")

        if len(opportunities) > limit:
            lines.append(f"*...and {len(opportunities) - limit} more opportunities identified.*")

        return "\n".join(lines)


def create_profile_from_tax_return(tax_return) -> TaxpayerProfile:
    """Create a TaxpayerProfile from a TaxReturn object."""
    profile = TaxpayerProfile()

    # Filing status
    if tax_return.taxpayer and tax_return.taxpayer.filing_status:
        profile.filing_status = tax_return.taxpayer.filing_status.value

    # Age
    if hasattr(tax_return.taxpayer, 'date_of_birth') and tax_return.taxpayer.date_of_birth:
        try:
            birth_date = datetime.strptime(str(tax_return.taxpayer.date_of_birth), "%Y-%m-%d")
            profile.age = (datetime.now() - birth_date).days // 365
        except (ValueError, TypeError):
            pass

    # Income from W-2s
    if tax_return.income and tax_return.income.w2_forms:
        for w2 in tax_return.income.w2_forms:
            profile.w2_wages += Decimal(str(w2.wages or 0))
            profile.federal_withheld += Decimal(str(w2.federal_tax_withheld or 0))

    # Other income
    if tax_return.income:
        profile.self_employment_income = Decimal(str(tax_return.income.self_employment_income or 0))
        profile.business_income = Decimal(str(tax_return.income.business_income or 0))
        profile.interest_income = Decimal(str(tax_return.income.interest_income or 0))
        profile.dividend_income = Decimal(str(tax_return.income.dividend_income or 0))
        profile.capital_gains = Decimal(str(tax_return.income.capital_gains or 0))
        profile.rental_income = Decimal(str(tax_return.income.rental_income or 0))
        profile.other_income = Decimal(str(tax_return.income.other_income or 0))

    # Deductions
    if tax_return.deductions:
        profile.mortgage_interest = Decimal(str(tax_return.deductions.mortgage_interest or 0))
        profile.property_taxes = Decimal(str(tax_return.deductions.property_tax or 0))
        profile.state_local_taxes = Decimal(str(tax_return.deductions.state_local_tax or 0))
        profile.charitable_contributions = Decimal(str(tax_return.deductions.charitable_contributions or 0))
        profile.student_loan_interest = Decimal(str(tax_return.deductions.student_loan_interest or 0))
        profile.hsa_contribution = Decimal(str(tax_return.deductions.hsa_contribution or 0))
        profile.traditional_401k = Decimal(str(tax_return.deductions.retirement_401k or 0))
        profile.traditional_ira = Decimal(str(tax_return.deductions.traditional_ira or 0))

    # Dependents
    if tax_return.taxpayer and hasattr(tax_return.taxpayer, 'dependents') and tax_return.taxpayer.dependents:
        profile.num_dependents = len(tax_return.taxpayer.dependents)
        for dep in tax_return.taxpayer.dependents:
            if hasattr(dep, 'birth_date') and dep.birth_date:
                try:
                    birth_date = datetime.strptime(str(dep.birth_date), "%Y-%m-%d")
                    age = (datetime.now() - birth_date).days // 365
                    if age < 17:
                        profile.has_children_under_17 = True
                    if age < 13:
                        profile.has_children_under_13 = True
                except (ValueError, TypeError):
                    pass

    # Home ownership
    profile.owns_home = profile.mortgage_interest > 0 or profile.property_taxes > 0

    # Business
    profile.has_business = profile.self_employment_income > 0 or profile.business_income > 0
    profile.business_net_income = profile.self_employment_income + profile.business_income

    return profile
