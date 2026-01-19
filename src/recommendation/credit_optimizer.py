"""Credit Optimizer.

Identifies all eligible tax credits and optimizes their utilization
based on the taxpayer's specific circumstances and income levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.tax_calculator import TaxCalculator


class CreditType(Enum):
    """Types of tax credits."""
    REFUNDABLE = "refundable"
    NONREFUNDABLE = "nonrefundable"
    PARTIALLY_REFUNDABLE = "partially_refundable"


@dataclass
class CreditEligibility:
    """Eligibility assessment for a specific credit."""
    credit_name: str
    credit_code: str
    credit_type: str  # refundable, nonrefundable, partially_refundable
    is_eligible: bool
    potential_amount: float
    actual_amount: float  # After phase-outs and limits
    eligibility_reason: str
    phase_out_applied: float = 0.0
    requirements: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    documentation_needed: List[str] = field(default_factory=list)
    optimization_tips: List[str] = field(default_factory=list)


@dataclass
class CreditAnalysis:
    """Complete credit analysis for a tax return."""
    filing_status: str
    adjusted_gross_income: float
    tax_liability_before_credits: float

    # Credit summaries
    eligible_credits: Dict[str, CreditEligibility]
    ineligible_credits: Dict[str, CreditEligibility]

    # Totals
    total_refundable_credits: float
    total_nonrefundable_credits: float
    total_credits_claimed: float

    # Applied amounts
    nonrefundable_applied: float  # Limited by tax liability
    refundable_applied: float
    unused_nonrefundable: float

    # Potential
    unclaimed_potential: float  # Credits missed due to missing info
    near_miss_credits: List[str]  # Credits close to eligibility


@dataclass
class CreditRecommendation:
    """Comprehensive credit recommendation."""
    analysis: CreditAnalysis
    total_credit_benefit: float
    confidence_score: float
    summary: str

    # Actionable recommendations
    immediate_actions: List[str] = field(default_factory=list)
    year_round_planning: List[str] = field(default_factory=list)
    documentation_reminders: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CreditOptimizer:
    """
    Analyzes and optimizes tax credit utilization.

    This optimizer identifies all eligible credits, calculates phase-outs,
    provides optimization strategies, and ensures maximum credit utilization
    while maintaining compliance with IRS requirements.
    """

    # 2025 Credit Parameters
    CREDITS_2025 = {
        "child_tax_credit": {
            "name": "Child Tax Credit",
            "type": CreditType.PARTIALLY_REFUNDABLE,
            "max_per_child": 2000,
            "refundable_max": 1700,  # Additional Child Tax Credit portion
            "child_max_age": 16,
            "phase_out_start": {"single": 200000, "married_joint": 400000},
            "phase_out_rate": 50,  # $50 per $1,000 over threshold
        },
        "other_dependent_credit": {
            "name": "Credit for Other Dependents",
            "type": CreditType.NONREFUNDABLE,
            "max_per_dependent": 500,
            "phase_out_start": {"single": 200000, "married_joint": 400000},
            "phase_out_rate": 50,
        },
        "eitc": {
            "name": "Earned Income Tax Credit",
            "type": CreditType.REFUNDABLE,
            # 2025 max amounts per IRS Rev. Proc. 2024-40
            "max_amounts": {0: 649, 1: 4328, 2: 7152, 3: 8046},
            "income_limits": {
                "single": {0: 18591, 1: 49084, 2: 55768, 3: 59899},
                "married_joint": {0: 25511, 1: 56004, 2: 62688, 3: 66819},
            },
            "investment_income_limit": 11950,  # 2025 limit
        },
        "child_dependent_care": {
            "name": "Child and Dependent Care Credit",
            "type": CreditType.NONREFUNDABLE,
            "max_expenses": {1: 3000, 2: 6000},  # 1 child, 2+ children
            "rate_schedule": [
                (15000, 35), (17000, 34), (19000, 33), (21000, 32),
                (23000, 31), (25000, 30), (27000, 29), (29000, 28),
                (31000, 27), (33000, 26), (35000, 25), (37000, 24),
                (39000, 23), (41000, 22), (43000, 21), (float('inf'), 20),
            ],
        },
        "american_opportunity": {
            "name": "American Opportunity Tax Credit",
            "type": CreditType.PARTIALLY_REFUNDABLE,
            "max_credit": 2500,
            "refundable_portion": 0.40,  # 40% refundable up to $1,000
            "phase_out_start": {"single": 80000, "married_joint": 160000},
            "phase_out_end": {"single": 90000, "married_joint": 180000},
        },
        "lifetime_learning": {
            "name": "Lifetime Learning Credit",
            "type": CreditType.NONREFUNDABLE,
            "max_credit": 2000,
            "rate": 0.20,  # 20% of first $10,000
            "phase_out_start": {"single": 80000, "married_joint": 160000},
            "phase_out_end": {"single": 90000, "married_joint": 180000},
        },
        "saver_credit": {
            "name": "Retirement Savings Contributions Credit",
            "type": CreditType.NONREFUNDABLE,
            "max_contribution": 2000,  # Per person
            "rate_schedule": {  # 2025 AGI limits (IRS Rev. Proc. 2024-40)
                "single": [(24750, 50), (26100, 20), (38250, 10)],
                "married_joint": [(49500, 50), (52200, 20), (76500, 10)],
                "head_of_household": [(37125, 50), (39150, 20), (57375, 10)],
            },
        },
        "adoption_credit": {
            "name": "Adoption Credit",
            "type": CreditType.NONREFUNDABLE,
            "max_credit": 16810,
            "phase_out_start": 252150,
            "phase_out_end": 292150,
        },
        "residential_clean_energy": {
            "name": "Residential Clean Energy Credit",
            "type": CreditType.NONREFUNDABLE,
            "rate": 0.30,  # 30% of qualified expenses
            "eligible_items": ["solar", "wind", "geothermal", "battery_storage"],
        },
        "ev_credit": {
            "name": "Clean Vehicle Credit",
            "type": CreditType.NONREFUNDABLE,
            "max_new_vehicle": 7500,
            "max_used_vehicle": 4000,
            "income_limits": {
                "new": {"single": 150000, "married_joint": 300000, "head_of_household": 225000},
                "used": {"single": 75000, "married_joint": 150000, "head_of_household": 112500},
            },
        },
        "premium_tax_credit": {
            "name": "Premium Tax Credit",
            "type": CreditType.REFUNDABLE,
            "fpl_range": (100, 400),  # 100% to 400% of FPL
        },
        "elderly_disabled": {
            "name": "Credit for Elderly or Disabled",
            "type": CreditType.NONREFUNDABLE,
            "base_amount": {"single": 5000, "married_joint": 7500},
            "age_requirement": 65,
            "income_limits": {"single": 17500, "married_joint": 25000},
        },
        "foreign_tax_credit": {
            "name": "Foreign Tax Credit",
            "type": CreditType.NONREFUNDABLE,
            "limit": "lesser of foreign taxes paid or US tax on foreign income",
        },
        "general_business_credit": {
            "name": "General Business Credit",
            "type": CreditType.NONREFUNDABLE,
            "includes": ["R&D", "work_opportunity", "disabled_access", "small_employer_pension"],
        },
    }

    def __init__(self, calculator: Optional["TaxCalculator"] = None):
        """Initialize the optimizer with an optional calculator."""
        self._calculator = calculator

    def analyze(self, tax_return: "TaxReturn") -> CreditRecommendation:
        """
        Analyze all potential credits and provide optimization recommendations.

        Args:
            tax_return: The tax return to analyze

        Returns:
            CreditRecommendation with analysis and strategies
        """
        filing_status = self._normalize_filing_status(
            tax_return.taxpayer.filing_status.value
        )
        agi = tax_return.adjusted_gross_income or 0.0
        tax_liability = tax_return.tax_liability or 0.0

        # Analyze each potential credit
        eligible_credits: Dict[str, CreditEligibility] = {}
        ineligible_credits: Dict[str, CreditEligibility] = {}

        # Child Tax Credit
        ctc = self._analyze_child_tax_credit(tax_return, filing_status, agi)
        if ctc.is_eligible:
            eligible_credits["child_tax_credit"] = ctc
        else:
            ineligible_credits["child_tax_credit"] = ctc

        # Other Dependent Credit
        odc = self._analyze_other_dependent_credit(tax_return, filing_status, agi)
        if odc.is_eligible:
            eligible_credits["other_dependent_credit"] = odc
        else:
            ineligible_credits["other_dependent_credit"] = odc

        # EITC
        eitc = self._analyze_eitc(tax_return, filing_status, agi)
        if eitc.is_eligible:
            eligible_credits["eitc"] = eitc
        else:
            ineligible_credits["eitc"] = eitc

        # Child and Dependent Care
        cdcc = self._analyze_child_care_credit(tax_return, filing_status, agi)
        if cdcc.is_eligible:
            eligible_credits["child_dependent_care"] = cdcc
        else:
            ineligible_credits["child_dependent_care"] = cdcc

        # Education Credits
        aotc = self._analyze_american_opportunity(tax_return, filing_status, agi)
        if aotc.is_eligible:
            eligible_credits["american_opportunity"] = aotc
        else:
            ineligible_credits["american_opportunity"] = aotc

        llc = self._analyze_lifetime_learning(tax_return, filing_status, agi)
        if llc.is_eligible:
            eligible_credits["lifetime_learning"] = llc
        else:
            ineligible_credits["lifetime_learning"] = llc

        # Saver's Credit
        saver = self._analyze_saver_credit(tax_return, filing_status, agi)
        if saver.is_eligible:
            eligible_credits["saver_credit"] = saver
        else:
            ineligible_credits["saver_credit"] = saver

        # Clean Vehicle Credit
        ev = self._analyze_ev_credit(tax_return, filing_status, agi)
        if ev.is_eligible:
            eligible_credits["ev_credit"] = ev
        else:
            ineligible_credits["ev_credit"] = ev

        # Residential Clean Energy
        energy = self._analyze_clean_energy_credit(tax_return, filing_status, agi)
        if energy.is_eligible:
            eligible_credits["residential_clean_energy"] = energy
        else:
            ineligible_credits["residential_clean_energy"] = energy

        # Premium Tax Credit
        ptc = self._analyze_premium_tax_credit(tax_return, filing_status, agi)
        if ptc.is_eligible:
            eligible_credits["premium_tax_credit"] = ptc
        else:
            ineligible_credits["premium_tax_credit"] = ptc

        # Elderly/Disabled Credit
        elderly = self._analyze_elderly_credit(tax_return, filing_status, agi)
        if elderly.is_eligible:
            eligible_credits["elderly_disabled"] = elderly
        else:
            ineligible_credits["elderly_disabled"] = elderly

        # Foreign Tax Credit
        foreign = self._analyze_foreign_tax_credit(tax_return, filing_status, agi)
        if foreign.is_eligible:
            eligible_credits["foreign_tax_credit"] = foreign
        else:
            ineligible_credits["foreign_tax_credit"] = foreign

        # Calculate totals
        total_refundable = sum(
            c.actual_amount for c in eligible_credits.values()
            if c.credit_type == "refundable"
        )
        total_partially_refundable = sum(
            c.actual_amount for c in eligible_credits.values()
            if c.credit_type == "partially_refundable"
        )
        total_nonrefundable = sum(
            c.actual_amount for c in eligible_credits.values()
            if c.credit_type == "nonrefundable"
        )

        # Calculate applied amounts
        nonrefundable_applied = min(
            total_nonrefundable + total_partially_refundable * 0.6,
            tax_liability
        )
        unused_nonrefundable = max(
            0, (total_nonrefundable + total_partially_refundable * 0.6) - tax_liability
        )

        refundable_applied = total_refundable + (total_partially_refundable * 0.4)

        total_claimed = nonrefundable_applied + refundable_applied

        # Calculate unclaimed potential
        unclaimed = self._calculate_unclaimed_potential(ineligible_credits)

        # Find near-miss credits
        near_miss = self._find_near_miss_credits(ineligible_credits, agi)

        # Create analysis
        analysis = CreditAnalysis(
            filing_status=filing_status,
            adjusted_gross_income=agi,
            tax_liability_before_credits=tax_liability,
            eligible_credits=eligible_credits,
            ineligible_credits=ineligible_credits,
            total_refundable_credits=round(total_refundable, 2),
            total_nonrefundable_credits=round(total_nonrefundable, 2),
            total_credits_claimed=round(total_claimed, 2),
            nonrefundable_applied=round(nonrefundable_applied, 2),
            refundable_applied=round(refundable_applied, 2),
            unused_nonrefundable=round(unused_nonrefundable, 2),
            unclaimed_potential=round(unclaimed, 2),
            near_miss_credits=near_miss,
        )

        # Generate recommendations
        immediate = self._generate_immediate_actions(analysis, tax_return)
        planning = self._generate_year_round_planning(analysis, tax_return)
        docs = self._generate_documentation_reminders(analysis)
        warnings = self._generate_warnings(analysis, tax_return)

        # Calculate confidence
        confidence = self._calculate_confidence(analysis)

        # Generate summary
        summary = self._generate_summary(analysis)

        return CreditRecommendation(
            analysis=analysis,
            total_credit_benefit=round(total_claimed, 2),
            confidence_score=confidence,
            summary=summary,
            immediate_actions=immediate,
            year_round_planning=planning,
            documentation_reminders=docs,
            warnings=warnings,
        )

    def _normalize_filing_status(self, status: str) -> str:
        """Normalize filing status string."""
        status_map = {
            "single": "single",
            "married_joint": "married_joint",
            "married_filing_jointly": "married_joint",
            "married_separate": "married_separate",
            "married_filing_separately": "married_separate",
            "head_of_household": "head_of_household",
            "qualifying_widow": "married_joint",  # Uses same thresholds
        }
        return status_map.get(status.lower(), "single")

    def _analyze_child_tax_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Child Tax Credit eligibility."""
        params = self.CREDITS_2025["child_tax_credit"]
        taxpayer = tax_return.taxpayer
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []

        # Count qualifying children under 17
        qualifying_children = 0
        for dep in dependents:
            dep_age = getattr(dep, 'age', 99)
            if dep_age <= params["child_max_age"]:
                qualifying_children += 1

        if qualifying_children == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="child_tax_credit",
                credit_type="partially_refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No qualifying children under age 17",
                requirements=["Child under age 17", "Valid SSN for child", "Child is dependent"],
                missing_requirements=["Qualifying child under 17"],
            )

        # Calculate potential amount
        potential = qualifying_children * params["max_per_child"]

        # Apply phase-out
        threshold = params["phase_out_start"].get(filing_status, 200000)
        if agi > threshold:
            excess = agi - threshold
            reduction = (excess // 1000) * params["phase_out_rate"]
            actual = max(0, potential - reduction)
            phase_out = potential - actual
        else:
            actual = potential
            phase_out = 0.0

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="child_tax_credit",
            credit_type="partially_refundable",
            is_eligible=True,
            potential_amount=potential,
            actual_amount=actual,
            eligibility_reason=f"{qualifying_children} qualifying child(ren) under 17",
            phase_out_applied=phase_out,
            requirements=[
                "Child under age 17 at end of year",
                "Valid Social Security Number for child",
                "Child claimed as dependent",
                "Child is US citizen, national, or resident alien",
            ],
            documentation_needed=[
                "Child's Social Security card",
                "Proof of relationship",
                "Proof of residency",
            ],
            optimization_tips=[
                f"Up to ${params['refundable_max']} per child is refundable (Additional CTC)",
                "Ensure each child has a valid SSN issued before tax return due date",
            ] if actual > 0 else [],
        )

    def _analyze_other_dependent_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Credit for Other Dependents."""
        params = self.CREDITS_2025["other_dependent_credit"]
        taxpayer = tax_return.taxpayer
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []

        # Count non-child dependents (age 17+ or non-child relatives)
        other_dependents = 0
        for dep in dependents:
            dep_age = getattr(dep, 'age', 0)
            if dep_age > 16:  # Age 17 or older
                other_dependents += 1

        if other_dependents == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="other_dependent_credit",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No qualifying other dependents",
                requirements=["Dependent age 17+", "Or qualifying relative"],
            )

        potential = other_dependents * params["max_per_dependent"]

        # Apply phase-out (same as CTC)
        threshold = params["phase_out_start"].get(filing_status, 200000)
        if agi > threshold:
            excess = agi - threshold
            reduction = (excess // 1000) * params["phase_out_rate"]
            actual = max(0, potential - reduction)
            phase_out = potential - actual
        else:
            actual = potential
            phase_out = 0.0

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="other_dependent_credit",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=potential,
            actual_amount=actual,
            eligibility_reason=f"{other_dependents} qualifying other dependent(s)",
            phase_out_applied=phase_out,
            requirements=[
                "Dependent must have ITIN or SSN",
                "Must meet dependent tests",
                "Cannot be claimed for CTC",
            ],
        )

    def _analyze_eitc(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Earned Income Tax Credit eligibility."""
        params = self.CREDITS_2025["eitc"]
        taxpayer = tax_return.taxpayer
        income = tax_return.income

        # Get earned income
        earned_income = (
            income.get_total_wages() +
            getattr(income, 'self_employment_income', 0) -
            getattr(income, 'self_employment_expenses', 0)
        )

        # Get investment income
        investment_income = (
            getattr(income, 'interest_income', 0) +
            getattr(income, 'dividend_income', 0) +
            max(0, getattr(income, 'capital_gain_income', 0))
        )

        # Count qualifying children
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []
        qualifying_children = min(3, len(dependents))  # Max 3 for EITC

        # Check investment income limit
        if investment_income > params["investment_income_limit"]:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="eitc",
                credit_type="refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Investment income (${investment_income:,.0f}) exceeds ${params['investment_income_limit']:,} limit",
                requirements=["Investment income under limit", "Earned income required"],
                missing_requirements=["Investment income must be under limit"],
            )

        # Check income limit
        status_key = "married_joint" if filing_status in ("married_joint",) else "single"
        income_limit = params["income_limits"][status_key][qualifying_children]

        if agi > income_limit or earned_income > income_limit:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="eitc",
                credit_type="refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Income exceeds ${income_limit:,} limit for {qualifying_children} children",
                requirements=[f"AGI under ${income_limit:,}", "Earned income required"],
                missing_requirements=["Income must be under limit"],
            )

        # Check for earned income
        if earned_income <= 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="eitc",
                credit_type="refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No earned income",
                requirements=["Must have earned income from work"],
                missing_requirements=["Earned income required"],
            )

        # Calculate EITC (simplified - actual calculation uses phase-in/phase-out)
        max_credit = params["max_amounts"][qualifying_children]
        # Simplified: Use percentage of max based on income relative to limit
        if earned_income < income_limit * 0.3:
            actual = max_credit * (earned_income / (income_limit * 0.3))
        elif earned_income < income_limit * 0.6:
            actual = max_credit
        else:
            actual = max_credit * ((income_limit - earned_income) / (income_limit * 0.4))

        actual = max(0, min(actual, max_credit))

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="eitc",
            credit_type="refundable",
            is_eligible=True,
            potential_amount=max_credit,
            actual_amount=round(actual, 2),
            eligibility_reason=f"Eligible with {qualifying_children} qualifying child(ren)",
            requirements=[
                "Valid Social Security Number",
                "US citizen or resident alien all year",
                "Filing status not Married Filing Separately",
                "Investment income under $11,600",
            ],
            documentation_needed=[
                "Form W-2 or proof of self-employment income",
                "Children's Social Security cards",
                "Proof children lived with you over 6 months",
            ],
            optimization_tips=[
                "EITC is fully refundable - increases tax refund",
                f"Maximum credit of ${max_credit:,} with {qualifying_children} children",
                "File even if not required to file - you may get a refund",
            ],
        )

    def _analyze_child_care_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Child and Dependent Care Credit."""
        params = self.CREDITS_2025["child_dependent_care"]
        taxpayer = tax_return.taxpayer
        deductions = tax_return.deductions

        # Check for qualifying dependents under 13 or disabled
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []
        qualifying = sum(1 for d in dependents if getattr(d, 'age', 99) < 13)

        if qualifying == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="child_dependent_care",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No qualifying children under 13",
                requirements=["Child under 13", "Or disabled dependent"],
                missing_requirements=["Qualifying dependent"],
            )

        # Get care expenses
        care_expenses = getattr(deductions, 'dependent_care_expenses', 0) or 0

        if care_expenses == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="child_dependent_care",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No dependent care expenses reported",
                requirements=["Work-related care expenses", "Care provider info"],
                missing_requirements=["Dependent care expenses"],
                optimization_tips=[
                    "Track daycare, preschool, before/after school care",
                    "Summer day camps qualify, overnight camps do not",
                ],
            )

        # Calculate credit
        expense_limit = params["max_expenses"].get(min(qualifying, 2), 3000)
        qualified_expenses = min(care_expenses, expense_limit)

        # Get credit rate based on AGI
        credit_rate = 20  # Default
        for threshold, rate in params["rate_schedule"]:
            if agi <= threshold:
                credit_rate = rate
                break

        actual = qualified_expenses * (credit_rate / 100)

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="child_dependent_care",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=expense_limit * 0.35,  # Max at 35% rate
            actual_amount=round(actual, 2),
            eligibility_reason=f"{qualifying} qualifying dependent(s), {credit_rate}% rate",
            requirements=[
                "Work-related expenses",
                "Care provider's name, address, and TIN",
                "Both parents must work (or one in school)",
            ],
            documentation_needed=[
                "Care provider's SSN or EIN",
                "Receipts or statements from provider",
                "Form W-10 from care provider",
            ],
            optimization_tips=[
                f"Credit rate is {credit_rate}% at your income level",
                f"Maximum expenses: ${expense_limit:,} for {qualifying} child(ren)",
                "Compare to employer's Dependent Care FSA ($5,000 max)",
            ],
        )

    def _analyze_american_opportunity(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze American Opportunity Tax Credit."""
        params = self.CREDITS_2025["american_opportunity"]
        credits = tax_return.credits

        # Check for education expenses
        education_expenses = getattr(credits, 'education_expenses', 0) or 0

        # Check income limits
        phase_out_start = params["phase_out_start"].get(filing_status, 80000)
        phase_out_end = params["phase_out_end"].get(filing_status, 90000)

        if agi >= phase_out_end:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="american_opportunity",
                credit_type="partially_refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Income (${agi:,.0f}) exceeds ${phase_out_end:,} limit",
                requirements=["MAGI under limit", "First 4 years of college"],
                missing_requirements=["Income under phase-out limit"],
            )

        if education_expenses == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="american_opportunity",
                credit_type="partially_refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No education expenses reported",
                requirements=["Qualified education expenses", "Student in first 4 years"],
                missing_requirements=["Education expenses"],
                optimization_tips=[
                    "Include tuition, fees, books, supplies, and equipment",
                    "Credit available for first 4 years of college",
                    "Student must be enrolled at least half-time",
                ],
            )

        # Calculate credit: 100% of first $2,000 + 25% of next $2,000
        if education_expenses <= 2000:
            potential = education_expenses
        else:
            potential = 2000 + min(education_expenses - 2000, 2000) * 0.25

        potential = min(potential, params["max_credit"])

        # Apply phase-out
        if agi <= phase_out_start:
            actual = potential
            phase_out = 0.0
        else:
            phase_out_range = phase_out_end - phase_out_start
            phase_out_pct = (agi - phase_out_start) / phase_out_range
            actual = potential * (1 - phase_out_pct)
            phase_out = potential - actual

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="american_opportunity",
            credit_type="partially_refundable",
            is_eligible=True,
            potential_amount=params["max_credit"],
            actual_amount=round(actual, 2),
            eligibility_reason="Qualified education expenses present",
            phase_out_applied=round(phase_out, 2),
            requirements=[
                "Student in first 4 years of postsecondary education",
                "Enrolled at least half-time",
                "No felony drug conviction",
                "Valid Form 1098-T from school",
            ],
            documentation_needed=[
                "Form 1098-T from educational institution",
                "Receipts for books and supplies",
            ],
            optimization_tips=[
                f"Up to ${params['max_credit'] * params['refundable_portion']:,.0f} is refundable",
                "Can be claimed for up to 4 tax years per student",
                "Cannot claim both AOTC and LLC for same student",
            ],
        )

    def _analyze_lifetime_learning(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Lifetime Learning Credit."""
        params = self.CREDITS_2025["lifetime_learning"]
        credits = tax_return.credits

        education_expenses = getattr(credits, 'education_expenses', 0) or 0

        phase_out_start = params["phase_out_start"].get(filing_status, 80000)
        phase_out_end = params["phase_out_end"].get(filing_status, 90000)

        if agi >= phase_out_end:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="lifetime_learning",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Income exceeds ${phase_out_end:,} limit",
                requirements=["MAGI under limit"],
            )

        if education_expenses == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="lifetime_learning",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No education expenses",
                requirements=["Qualified education expenses"],
                optimization_tips=[
                    "No limit on years you can claim",
                    "Can claim for graduate school",
                    "Can claim for professional development",
                ],
            )

        # Calculate credit: 20% of first $10,000
        potential = min(education_expenses * params["rate"], params["max_credit"])

        # Apply phase-out
        if agi <= phase_out_start:
            actual = potential
            phase_out = 0.0
        else:
            phase_out_range = phase_out_end - phase_out_start
            phase_out_pct = (agi - phase_out_start) / phase_out_range
            actual = potential * (1 - phase_out_pct)
            phase_out = potential - actual

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="lifetime_learning",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=params["max_credit"],
            actual_amount=round(actual, 2),
            eligibility_reason="Qualified education expenses present",
            phase_out_applied=round(phase_out, 2),
            requirements=[
                "Enrolled in eligible educational institution",
                "Expenses for courses to acquire/improve job skills",
            ],
            optimization_tips=[
                "No limit on number of years",
                "Available for graduate and professional degrees",
                "One or more courses qualifies (no half-time requirement)",
            ],
        )

    def _analyze_saver_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Retirement Savings Contributions Credit."""
        params = self.CREDITS_2025["saver_credit"]
        income = tax_return.income

        # Get retirement contributions
        retirement_contributions = (
            getattr(income, 'retirement_contributions_401k', 0) +
            getattr(income, 'retirement_contributions_ira', 0) +
            getattr(income, 'retirement_contributions', 0)
        ) or 0

        if retirement_contributions == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="saver_credit",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No eligible retirement contributions",
                requirements=["Contribution to 401(k), IRA, or similar"],
                missing_requirements=["Retirement contributions"],
                optimization_tips=[
                    "Contribute to 401(k), 403(b), or IRA",
                    "Credit is in addition to tax deduction for contribution",
                ],
            )

        # Check income limits
        rate_schedule = params["rate_schedule"].get(filing_status, params["rate_schedule"]["single"])

        credit_rate = 0
        for threshold, rate in rate_schedule:
            if agi <= threshold:
                credit_rate = rate
                break

        if credit_rate == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="saver_credit",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Income too high for credit",
                requirements=[f"AGI under ${rate_schedule[-1][0]:,}"],
                missing_requirements=["Income under limit"],
            )

        # Calculate credit
        qualified_contribution = min(retirement_contributions, params["max_contribution"])
        actual = qualified_contribution * (credit_rate / 100)

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="saver_credit",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=params["max_contribution"] * 0.50,  # Max at 50%
            actual_amount=round(actual, 2),
            eligibility_reason=f"{credit_rate}% rate on ${qualified_contribution:,.0f} contributions",
            requirements=[
                "Age 18 or older",
                "Not claimed as dependent",
                "Not a full-time student",
            ],
            optimization_tips=[
                f"Your credit rate is {credit_rate}%",
                f"Maximum contribution eligible: ${params['max_contribution']:,}",
                "Applies to 401(k), IRA, SIMPLE, SEP contributions",
            ],
        )

    def _analyze_ev_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Clean Vehicle Credit."""
        params = self.CREDITS_2025["ev_credit"]
        credits = tax_return.credits

        ev_purchase = getattr(credits, 'ev_purchase_amount', 0) or 0
        is_new = getattr(credits, 'ev_is_new', True)
        is_used = getattr(credits, 'ev_is_used', False)

        if ev_purchase == 0 and not (is_new or is_used):
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="ev_credit",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No electric vehicle purchase reported",
                requirements=["Purchase/lease qualifying EV", "Check IRS qualified vehicle list"],
                optimization_tips=[
                    "Up to $7,500 for new qualifying vehicles",
                    "Up to $4,000 for used qualifying vehicles",
                    "Can transfer credit to dealer at point of sale",
                ],
            )

        # Check income limits
        vehicle_type = "new" if is_new else "used"
        income_limits = params["income_limits"][vehicle_type]
        income_limit = income_limits.get(filing_status, income_limits.get("single", 150000))

        if agi > income_limit:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="ev_credit",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Income exceeds ${income_limit:,} limit for {vehicle_type} vehicles",
                requirements=[f"MAGI under ${income_limit:,}"],
                missing_requirements=["Income under limit"],
            )

        max_credit = params["max_new_vehicle"] if is_new else params["max_used_vehicle"]

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="ev_credit",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=max_credit,
            actual_amount=max_credit,  # Simplified - actual depends on vehicle
            eligibility_reason=f"Qualifying {'new' if is_new else 'used'} EV purchase",
            requirements=[
                "Vehicle must be on IRS qualified list",
                "Final assembly in North America (new)",
                f"MSRP limits apply (new: sedan $55K, SUV/truck $80K)",
            ],
            documentation_needed=[
                "Seller's certification of vehicle eligibility",
                "VIN and purchase documentation",
            ],
            optimization_tips=[
                "Credit can be transferred to dealer to reduce purchase price",
                "Check fueleconomy.gov for qualifying vehicles",
            ],
        )

    def _analyze_clean_energy_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Residential Clean Energy Credit."""
        params = self.CREDITS_2025["residential_clean_energy"]
        credits = tax_return.credits

        solar_expenses = getattr(credits, 'solar_expenses', 0) or 0
        energy_expenses = getattr(credits, 'clean_energy_expenses', 0) or 0
        total_expenses = solar_expenses + energy_expenses

        if total_expenses == 0:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="residential_clean_energy",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No clean energy expenses reported",
                requirements=["Install qualifying clean energy equipment at home"],
                optimization_tips=[
                    "30% credit for solar, wind, geothermal, battery storage",
                    "No dollar limit on credit amount",
                    "Unused credit carries forward to future years",
                ],
            )

        actual = total_expenses * params["rate"]

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="residential_clean_energy",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=total_expenses * params["rate"],
            actual_amount=round(actual, 2),
            eligibility_reason=f"${total_expenses:,.0f} in clean energy expenses",
            requirements=[
                "Equipment installed at your main or second home",
                "Original use must begin with you",
                "Meets all applicable performance standards",
            ],
            documentation_needed=[
                "Installation receipts and contracts",
                "Manufacturer certification statement",
            ],
            optimization_tips=[
                "Credit is 30% through 2032, then phases down",
                "Can include installation labor costs",
                "Excess credit carries forward indefinitely",
            ],
        )

    def _analyze_premium_tax_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Premium Tax Credit."""
        credits = tax_return.credits

        marketplace_premium = getattr(credits, 'marketplace_premium', 0) or 0
        advance_ptc = getattr(credits, 'advance_ptc_received', 0) or 0

        if marketplace_premium == 0:
            return CreditEligibility(
                credit_name="Premium Tax Credit",
                credit_code="premium_tax_credit",
                credit_type="refundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No Health Insurance Marketplace coverage",
                requirements=["Coverage through Healthcare.gov Marketplace"],
                optimization_tips=[
                    "If uninsured, check Healthcare.gov for coverage and credits",
                    "Credit based on income relative to Federal Poverty Level",
                ],
            )

        # Simplified calculation - actual requires FPL tables
        # Credit makes premium cost percentage of income
        household_size = 1 + len(tax_return.taxpayer.dependents)

        return CreditEligibility(
            credit_name="Premium Tax Credit",
            credit_code="premium_tax_credit",
            credit_type="refundable",
            is_eligible=True,
            potential_amount=marketplace_premium,
            actual_amount=max(0, marketplace_premium - advance_ptc),
            eligibility_reason="Health Marketplace coverage present",
            requirements=[
                "Coverage through Marketplace",
                "Not eligible for other coverage (employer, Medicare)",
                "Income 100-400% of Federal Poverty Level",
            ],
            documentation_needed=["Form 1095-A from Marketplace"],
            optimization_tips=[
                "Report income changes to Marketplace during year",
                "Reconcile advance payments on Form 8962",
            ],
        )

    def _analyze_elderly_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Credit for the Elderly or Disabled."""
        params = self.CREDITS_2025["elderly_disabled"]
        taxpayer = tax_return.taxpayer

        age = getattr(taxpayer, 'age', 0)
        is_disabled = getattr(taxpayer, 'is_disabled', False)

        if age < 65 and not is_disabled:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="elderly_disabled",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="Must be 65+ or permanently disabled",
                requirements=["Age 65 or older", "Or permanently/totally disabled"],
            )

        income_limit = params["income_limits"].get(filing_status, 17500)
        if agi > income_limit:
            return CreditEligibility(
                credit_name=params["name"],
                credit_code="elderly_disabled",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason=f"Income exceeds ${income_limit:,} limit",
                requirements=[f"AGI under ${income_limit:,}"],
            )

        base = params["base_amount"].get(filing_status, 5000)
        # Simplified - actual calculation more complex
        actual = min(base * 0.15, 750)  # Max credit

        return CreditEligibility(
            credit_name=params["name"],
            credit_code="elderly_disabled",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=base * 0.15,
            actual_amount=actual,
            eligibility_reason="Meets age or disability requirement",
            requirements=[
                "Age 65+ or permanently disabled",
                f"AGI under ${income_limit:,}",
                "Limited nontaxable Social Security",
            ],
            documentation_needed=[
                "Disability statement from physician (if disabled)",
            ],
        )

    def _analyze_foreign_tax_credit(
        self, tax_return: "TaxReturn", filing_status: str, agi: float
    ) -> CreditEligibility:
        """Analyze Foreign Tax Credit."""
        income = tax_return.income

        foreign_taxes_paid = (
            getattr(income, 'foreign_taxes_paid', 0) or
            getattr(income, 'foreign_tax_credit', 0) or 0
        )

        if foreign_taxes_paid == 0:
            return CreditEligibility(
                credit_name="Foreign Tax Credit",
                credit_code="foreign_tax_credit",
                credit_type="nonrefundable",
                is_eligible=False,
                potential_amount=0.0,
                actual_amount=0.0,
                eligibility_reason="No foreign taxes paid",
                requirements=["Income from foreign sources", "Foreign taxes paid"],
                optimization_tips=[
                    "Check mutual fund statements for foreign taxes withheld",
                    "Foreign dividends often have withholding",
                ],
            )

        return CreditEligibility(
            credit_name="Foreign Tax Credit",
            credit_code="foreign_tax_credit",
            credit_type="nonrefundable",
            is_eligible=True,
            potential_amount=foreign_taxes_paid,
            actual_amount=foreign_taxes_paid,  # Simplified - actual has limits
            eligibility_reason=f"${foreign_taxes_paid:,.0f} in foreign taxes paid",
            requirements=[
                "Foreign tax was legally imposed on you",
                "You paid or accrued the tax",
            ],
            documentation_needed=[
                "Form 1099-DIV showing foreign taxes",
                "Foreign tax statements/receipts",
            ],
            optimization_tips=[
                "Under $300 ($600 MFJ) can claim without Form 1116",
                "Compare credit vs deduction (credit usually better)",
            ],
        )

    def _calculate_unclaimed_potential(
        self, ineligible: Dict[str, CreditEligibility]
    ) -> float:
        """Calculate potential credits that could be claimed with more info."""
        potential = 0.0

        for credit in ineligible.values():
            if credit.missing_requirements:
                # Only count if missing info (not income limits)
                if any("expense" in req.lower() or "contribution" in req.lower()
                       for req in credit.missing_requirements):
                    potential += credit.potential_amount

        return potential

    def _find_near_miss_credits(
        self, ineligible: Dict[str, CreditEligibility], agi: float
    ) -> List[str]:
        """Find credits that are close to eligibility."""
        near_miss = []

        for code, credit in ineligible.items():
            reason = credit.eligibility_reason.lower()

            # Check if income is close to limit
            if "income" in reason and "exceeds" in reason:
                # Check if within 10% of limit
                if credit.phase_out_applied > 0 or "limit" in reason:
                    near_miss.append(
                        f"{credit.credit_name}: Consider retirement contributions "
                        "or HSA to reduce AGI"
                    )

        return near_miss

    def _generate_immediate_actions(
        self, analysis: CreditAnalysis, tax_return: "TaxReturn"
    ) -> List[str]:
        """Generate immediate action items."""
        actions = []

        # Check for education expenses
        if "american_opportunity" in analysis.ineligible_credits:
            credit = analysis.ineligible_credits["american_opportunity"]
            if "expense" in credit.eligibility_reason.lower():
                actions.append(
                    "Enter education expenses (tuition, fees, books) to claim "
                    "up to $2,500 American Opportunity Credit."
                )

        # Check for retirement contributions
        if "saver_credit" in analysis.ineligible_credits:
            credit = analysis.ineligible_credits["saver_credit"]
            if "contribution" in credit.eligibility_reason.lower():
                actions.append(
                    "Enter 401(k)/IRA contributions to potentially claim "
                    "the Saver's Credit (up to $1,000)."
                )

        # Check for child care
        if "child_dependent_care" in analysis.ineligible_credits:
            credit = analysis.ineligible_credits["child_dependent_care"]
            if "expense" in credit.eligibility_reason.lower():
                actions.append(
                    "Enter dependent care expenses (daycare, after-school) "
                    "to claim the Child Care Credit."
                )

        # EV credit
        if "ev_credit" in analysis.ineligible_credits:
            actions.append(
                "If you purchased an electric vehicle, enter purchase details "
                "for up to $7,500 credit."
            )

        return actions

    def _generate_year_round_planning(
        self, analysis: CreditAnalysis, tax_return: "TaxReturn"
    ) -> List[str]:
        """Generate year-round planning recommendations."""
        planning = []

        # EITC optimization
        if "eitc" in analysis.eligible_credits:
            planning.append(
                "EITC claimed - ensure you report all earned income "
                "accurately throughout the year."
            )
        elif "eitc" in analysis.ineligible_credits:
            credit = analysis.ineligible_credits["eitc"]
            if "income" in credit.eligibility_reason.lower():
                planning.append(
                    "Your income may qualify for EITC in future years. "
                    "Track changes in income and family size."
                )

        # Retirement contributions
        planning.append(
            "Maximize retirement contributions (401k: $23,500, IRA: $7,000) "
            "to potentially reduce AGI and qualify for more credits."
        )

        # Education planning
        if "american_opportunity" in analysis.eligible_credits:
            planning.append(
                "AOTC can be claimed for 4 years of college per student. "
                "Plan tuition payments to maximize credit timing."
            )

        # Child care FSA
        if "child_dependent_care" in analysis.eligible_credits:
            planning.append(
                "Consider employer's Dependent Care FSA ($5,000 pre-tax) "
                "in addition to or instead of Child Care Credit."
            )

        return planning

    def _generate_documentation_reminders(
        self, analysis: CreditAnalysis
    ) -> List[str]:
        """Generate documentation reminders for claimed credits."""
        reminders = []

        for code, credit in analysis.eligible_credits.items():
            if credit.documentation_needed:
                for doc in credit.documentation_needed[:2]:  # Top 2 per credit
                    reminders.append(f"{credit.credit_name}: {doc}")

        return reminders

    def _generate_warnings(
        self, analysis: CreditAnalysis, tax_return: "TaxReturn"
    ) -> List[str]:
        """Generate warnings about credit issues."""
        warnings = []

        # Nonrefundable credit waste
        if analysis.unused_nonrefundable > 500:
            warnings.append(
                f"${analysis.unused_nonrefundable:,.0f} in nonrefundable credits "
                "cannot be used (exceeds tax liability). "
                "Consider strategies to increase taxable income or reduce withholding."
            )

        # Education credit conflict
        ed_credits = ["american_opportunity", "lifetime_learning"]
        claimed_ed = [c for c in ed_credits if c in analysis.eligible_credits]
        if len(claimed_ed) > 1:
            warnings.append(
                "Cannot claim both AOTC and LLC for the same student. "
                "Compare which provides the better benefit."
            )

        return warnings

    def _calculate_confidence(self, analysis: CreditAnalysis) -> float:
        """Calculate confidence score for credit analysis."""
        # Higher confidence if more credits analyzed with complete data
        eligible_count = len(analysis.eligible_credits)
        ineligible_count = len(analysis.ineligible_credits)

        # Base confidence
        confidence = 70.0

        # Add for documented credits
        confidence += min(eligible_count * 5, 20)

        # Reduce for missing data
        missing_count = sum(
            1 for c in analysis.ineligible_credits.values()
            if c.missing_requirements
        )
        confidence -= min(missing_count * 3, 15)

        return max(50, min(100, confidence))

    def _generate_summary(self, analysis: CreditAnalysis) -> str:
        """Generate summary of credit analysis."""
        eligible_count = len(analysis.eligible_credits)
        total_benefit = analysis.total_credits_claimed

        if total_benefit > 0:
            return (
                f"You qualify for {eligible_count} tax credit(s) worth "
                f"${total_benefit:,.0f}. Refundable credits: "
                f"${analysis.refundable_applied:,.0f}, "
                f"Nonrefundable credits applied: ${analysis.nonrefundable_applied:,.0f}."
            )
        else:
            return (
                "No tax credits currently qualify based on provided information. "
                "Review 'immediate actions' for potential credits you may be missing."
            )
