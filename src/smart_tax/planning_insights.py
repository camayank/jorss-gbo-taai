"""
Tax Planning Insights Engine

Provides proactive tax planning recommendations based on:
- Current year tax situation
- Multi-year tax optimization opportunities
- Life event tax implications
- Timing strategies for income and deductions

Key features:
- Quarterly estimated tax reminders
- Year-end tax planning checklist
- Retirement contribution optimization
- Income deferral/acceleration strategies
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from decimal import Decimal
from datetime import date, datetime
import calendar


class InsightCategory(str, Enum):
    """Categories of tax planning insights."""
    RETIREMENT = "retirement"
    TIMING = "timing"
    WITHHOLDING = "withholding"
    ESTIMATED_TAX = "estimated_tax"
    YEAR_END = "year_end"
    LIFE_EVENT = "life_event"
    INCOME_SHIFTING = "income_shifting"
    CHARITABLE = "charitable"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    BUSINESS = "business"


class InsightUrgency(str, Enum):
    """Urgency levels for planning insights."""
    IMMEDIATE = "immediate"  # Act now
    SOON = "soon"           # Within 30 days
    QUARTERLY = "quarterly"  # Before quarter end
    YEAR_END = "year_end"   # Before Dec 31
    FUTURE = "future"       # Long-term planning


class InsightImpact(str, Enum):
    """Potential tax impact levels."""
    HIGH = "high"       # $1,000+ savings
    MEDIUM = "medium"   # $200-$1,000 savings
    LOW = "low"         # Under $200 savings


@dataclass
class TaxPlanningInsight:
    """A single tax planning recommendation."""
    insight_id: str
    title: str
    description: str
    category: InsightCategory
    urgency: InsightUrgency
    impact: InsightImpact
    estimated_savings: Decimal
    deadline: Optional[date]
    action_steps: List[str]
    relevant_forms: List[str]
    caveats: List[str]
    applies_to_situations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "urgency": self.urgency.value,
            "impact": self.impact.value,
            "estimated_savings": float(self.estimated_savings),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "action_steps": self.action_steps,
            "relevant_forms": self.relevant_forms,
            "caveats": self.caveats,
            "applies_to_situations": self.applies_to_situations,
        }


@dataclass
class QuarterlyEstimate:
    """Quarterly estimated tax payment recommendation."""
    quarter: int
    due_date: date
    recommended_payment: Decimal
    ytd_income: Decimal
    ytd_tax_withheld: Decimal
    projected_annual_tax: Decimal
    safe_harbor_amount: Decimal
    penalty_risk: str  # "none", "low", "medium", "high"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quarter": self.quarter,
            "due_date": self.due_date.isoformat(),
            "recommended_payment": float(self.recommended_payment),
            "ytd_income": float(self.ytd_income),
            "ytd_tax_withheld": float(self.ytd_tax_withheld),
            "projected_annual_tax": float(self.projected_annual_tax),
            "safe_harbor_amount": float(self.safe_harbor_amount),
            "penalty_risk": self.penalty_risk,
        }


@dataclass
class PlanningReport:
    """Comprehensive tax planning report."""
    generated_at: datetime
    tax_year: int
    filing_status: str
    insights: List[TaxPlanningInsight]
    quarterly_estimates: List[QuarterlyEstimate]
    year_end_checklist: List[Dict[str, Any]]
    projected_tax_liability: Decimal
    projected_refund_or_owed: Decimal
    optimization_potential: Decimal
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "insights": [i.to_dict() for i in self.insights],
            "quarterly_estimates": [q.to_dict() for q in self.quarterly_estimates],
            "year_end_checklist": self.year_end_checklist,
            "projected_tax_liability": float(self.projected_tax_liability),
            "projected_refund_or_owed": float(self.projected_refund_or_owed),
            "optimization_potential": float(self.optimization_potential),
            "summary": self.summary,
        }


class TaxPlanningEngine:
    """
    Generates proactive tax planning insights and recommendations.

    Features:
    - Quarterly estimated tax calculation
    - Year-end planning strategies
    - Retirement contribution optimization
    - Income timing recommendations
    - Life event tax implications
    """

    # 2025 Tax Constants (IRS Rev. Proc. 2024-40)
    TAX_YEAR = 2025

    # Standard deduction amounts (2025)
    STANDARD_DEDUCTION = {
        "single": Decimal("15750"),
        "married_filing_jointly": Decimal("31500"),
        "married_filing_separately": Decimal("15750"),
        "head_of_household": Decimal("23850"),
    }

    # Retirement contribution limits (2025)
    CONTRIBUTION_LIMITS = {
        "401k": Decimal("23500"),
        "401k_catchup": Decimal("7500"),  # Age 50+
        "ira": Decimal("7000"),
        "ira_catchup": Decimal("1000"),   # Age 50+
        "hsa_individual": Decimal("4300"),
        "hsa_family": Decimal("8550"),
        "hsa_catchup": Decimal("1000"),   # Age 55+
    }

    # Quarterly estimated tax due dates for 2025
    QUARTERLY_DUE_DATES = {
        1: date(2025, 4, 15),    # Q1: Jan-Mar
        2: date(2025, 6, 16),    # Q2: Apr-May
        3: date(2025, 9, 15),    # Q3: Jun-Aug
        4: date(2026, 1, 15),    # Q4: Sep-Dec
    }

    def __init__(self):
        self.current_date = date.today()

    def generate_planning_report(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
        filing_status: str = "single",
        age: int = 35,
    ) -> PlanningReport:
        """
        Generate comprehensive tax planning report.

        Args:
            extracted_data: Data from tax documents
            answers: User's answers to questions
            filing_status: Tax filing status
            age: Taxpayer's age

        Returns:
            Complete planning report with insights and recommendations
        """
        # Calculate current situation
        total_income = self._calculate_total_income(extracted_data)
        total_withholding = self._calculate_total_withholding(extracted_data)
        current_deductions = self._calculate_current_deductions(extracted_data, answers)

        # Generate insights based on situation
        insights = []
        insights.extend(self._generate_retirement_insights(
            extracted_data, answers, total_income, age, filing_status
        ))
        insights.extend(self._generate_timing_insights(
            extracted_data, answers, total_income
        ))
        insights.extend(self._generate_withholding_insights(
            total_income, total_withholding, filing_status
        ))
        insights.extend(self._generate_year_end_insights(
            extracted_data, answers, total_income, current_deductions, filing_status
        ))
        insights.extend(self._generate_healthcare_insights(
            extracted_data, answers, age, filing_status
        ))

        # Calculate quarterly estimates
        quarterly_estimates = self._calculate_quarterly_estimates(
            total_income, total_withholding, filing_status
        )

        # Generate year-end checklist
        year_end_checklist = self._generate_year_end_checklist(
            extracted_data, answers, insights
        )

        # Project tax liability
        projected_tax = self._project_tax_liability(
            total_income, current_deductions, filing_status
        )

        # Calculate optimization potential
        optimization_potential = sum(
            i.estimated_savings for i in insights
        )

        # Generate summary
        summary = self._generate_summary(
            insights, projected_tax, total_withholding, optimization_potential
        )

        return PlanningReport(
            generated_at=datetime.now(),
            tax_year=self.TAX_YEAR,
            filing_status=filing_status,
            insights=sorted(insights, key=lambda i: (
                ["immediate", "soon", "quarterly", "year_end", "future"].index(i.urgency.value),
                ["high", "medium", "low"].index(i.impact.value)
            )),
            quarterly_estimates=quarterly_estimates,
            year_end_checklist=year_end_checklist,
            projected_tax_liability=projected_tax,
            projected_refund_or_owed=total_withholding - projected_tax,
            optimization_potential=optimization_potential,
            summary=summary,
        )

    def _calculate_total_income(self, extracted_data: Dict[str, Any]) -> Decimal:
        """Calculate total income from extracted data."""
        income_fields = [
            "wages", "interest_income", "ordinary_dividends",
            "qualified_dividends", "capital_gains", "nonemployee_compensation",
            "social_security_benefits", "pension_income", "rental_income",
        ]
        total = Decimal("0")
        for field in income_fields:
            value = extracted_data.get(field, 0)
            if value:
                total += Decimal(str(value))
        return total

    def _calculate_total_withholding(self, extracted_data: Dict[str, Any]) -> Decimal:
        """Calculate total tax withholding."""
        withholding_fields = [
            "federal_tax_withheld", "federal_income_tax_withheld"
        ]
        total = Decimal("0")
        for field in withholding_fields:
            value = extracted_data.get(field, 0)
            if value:
                total += Decimal(str(value))
        return total

    def _calculate_current_deductions(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
    ) -> Decimal:
        """Calculate current known deductions."""
        deductions = Decimal("0")

        # Above-the-line deductions
        above_line = [
            "student_loan_interest", "hsa_contributions",
            "traditional_ira_contributions", "self_employment_tax_deduction"
        ]
        for field in above_line:
            value = extracted_data.get(field, 0) or answers.get(field, 0)
            if value:
                deductions += Decimal(str(value))

        return deductions

    def _generate_retirement_insights(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
        total_income: Decimal,
        age: int,
        filing_status: str,
    ) -> List[TaxPlanningInsight]:
        """Generate retirement contribution insights."""
        insights = []

        # Check 401(k) contributions
        current_401k = Decimal(str(extracted_data.get("retirement_contributions", 0) or 0))
        limit_401k = self.CONTRIBUTION_LIMITS["401k"]
        if age >= 50:
            limit_401k += self.CONTRIBUTION_LIMITS["401k_catchup"]

        remaining_401k = limit_401k - current_401k
        if remaining_401k > 0:
            # Calculate tax savings (approximate marginal rate)
            marginal_rate = self._estimate_marginal_rate(total_income, filing_status)
            savings = remaining_401k * marginal_rate

            insights.append(TaxPlanningInsight(
                insight_id="retire_401k_max",
                title="Maximize 401(k) Contributions",
                description=f"You have ${remaining_401k:,.0f} of unused 401(k) contribution room for {self.TAX_YEAR}.",
                category=InsightCategory.RETIREMENT,
                urgency=InsightUrgency.YEAR_END,
                impact=InsightImpact.HIGH if savings > 1000 else InsightImpact.MEDIUM,
                estimated_savings=savings,
                deadline=date(self.TAX_YEAR, 12, 31),
                action_steps=[
                    "Contact HR to increase 401(k) contribution percentage",
                    "Consider front-loading contributions if cash flow allows",
                    "Review investment allocation in your 401(k)",
                ],
                relevant_forms=["W-2 Box 12 Code D"],
                caveats=[
                    "Must be employed with 401(k)-eligible employer",
                    "Contributions must be made by December 31",
                ],
                applies_to_situations=["employed", "has_401k"],
            ))

        # Check IRA contributions
        current_ira = Decimal(str(answers.get("ira_contributions", 0) or 0))
        limit_ira = self.CONTRIBUTION_LIMITS["ira"]
        if age >= 50:
            limit_ira += self.CONTRIBUTION_LIMITS["ira_catchup"]

        remaining_ira = limit_ira - current_ira
        if remaining_ira > 0:
            marginal_rate = self._estimate_marginal_rate(total_income, filing_status)
            savings = remaining_ira * marginal_rate

            insights.append(TaxPlanningInsight(
                insight_id="retire_ira_contribution",
                title="Contribute to IRA Before Tax Deadline",
                description=f"You can contribute up to ${remaining_ira:,.0f} more to a Traditional or Roth IRA.",
                category=InsightCategory.RETIREMENT,
                urgency=InsightUrgency.YEAR_END,
                impact=InsightImpact.MEDIUM if savings > 500 else InsightImpact.LOW,
                estimated_savings=savings,
                deadline=date(self.TAX_YEAR + 1, 4, 15),  # April 15 of next year
                action_steps=[
                    "Open IRA if you don't have one (Traditional or Roth)",
                    "Decide between Traditional (tax-deferred) or Roth (tax-free growth)",
                    "Contribute by April 15, specify it's for the prior year",
                ],
                relevant_forms=["Form 5498", "Form 8606 (if non-deductible)"],
                caveats=[
                    "Income limits may apply for Roth IRA",
                    "Deductibility of Traditional IRA depends on income and retirement plan coverage",
                ],
                applies_to_situations=["has_earned_income"],
            ))

        return insights

    def _generate_timing_insights(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
        total_income: Decimal,
    ) -> List[TaxPlanningInsight]:
        """Generate income/expense timing insights."""
        insights = []
        current_month = self.current_date.month

        # Year-end bonus timing
        if current_month >= 10:  # October onwards
            insights.append(TaxPlanningInsight(
                insight_id="timing_bonus_deferral",
                title="Consider Bonus Timing",
                description="If you expect a year-end bonus, consider whether deferring to January would be beneficial.",
                category=InsightCategory.TIMING,
                urgency=InsightUrgency.SOON if current_month == 12 else InsightUrgency.QUARTERLY,
                impact=InsightImpact.MEDIUM,
                estimated_savings=Decimal("300"),  # Approximate
                deadline=date(self.TAX_YEAR, 12, 31),
                action_steps=[
                    "Estimate your income for this year vs. next year",
                    "If next year will be lower income, defer bonus",
                    "If next year will be higher, take bonus this year",
                    "Discuss with employer if deferral is possible",
                ],
                relevant_forms=["W-2"],
                caveats=[
                    "Employer must agree to deferral",
                    "Consider cash flow needs",
                ],
                applies_to_situations=["expecting_bonus"],
            ))

        # Charitable giving bunching
        charitable = Decimal(str(answers.get("charitable_contributions", 0) or 0))
        if charitable > 0 and current_month >= 9:
            insights.append(TaxPlanningInsight(
                insight_id="timing_charitable_bunching",
                title="Consider Charitable Bunching Strategy",
                description="Bunching multiple years of charitable donations into one year can help you exceed the standard deduction.",
                category=InsightCategory.CHARITABLE,
                urgency=InsightUrgency.YEAR_END,
                impact=InsightImpact.MEDIUM,
                estimated_savings=Decimal("500"),
                deadline=date(self.TAX_YEAR, 12, 31),
                action_steps=[
                    "Consider using a Donor Advised Fund (DAF)",
                    "Make 2-3 years of donations this year",
                    "Take standard deduction next year",
                ],
                relevant_forms=["Schedule A", "Form 8283 (noncash >$500)"],
                caveats=[
                    "Only beneficial if bunched amount exceeds standard deduction",
                    "Cash contributions limited to 60% of AGI",
                ],
                applies_to_situations=["makes_charitable_donations"],
            ))

        return insights

    def _generate_withholding_insights(
        self,
        total_income: Decimal,
        total_withholding: Decimal,
        filing_status: str,
    ) -> List[TaxPlanningInsight]:
        """Generate tax withholding insights."""
        insights = []

        # Estimate tax liability
        projected_tax = self._project_tax_liability(
            total_income,
            Decimal("0"),  # Assume no deductions for this check
            filing_status
        )

        withholding_ratio = total_withholding / projected_tax if projected_tax > 0 else Decimal("1")

        if withholding_ratio < Decimal("0.85"):
            insights.append(TaxPlanningInsight(
                insight_id="withholding_increase",
                title="Increase Tax Withholding",
                description="Your withholding may be too low. You could owe taxes and penalties at filing.",
                category=InsightCategory.WITHHOLDING,
                urgency=InsightUrgency.IMMEDIATE,
                impact=InsightImpact.HIGH,
                estimated_savings=Decimal("200"),  # Penalty avoidance
                deadline=None,
                action_steps=[
                    "Submit new W-4 to your employer",
                    "Use IRS Tax Withholding Estimator at irs.gov",
                    "Consider making estimated tax payments",
                ],
                relevant_forms=["W-4", "Form 1040-ES"],
                caveats=[
                    "Changes may take 1-2 pay periods to take effect",
                ],
                applies_to_situations=["employed", "underwithholding"],
            ))
        elif withholding_ratio > Decimal("1.15"):
            insights.append(TaxPlanningInsight(
                insight_id="withholding_decrease",
                title="Consider Reducing Withholding",
                description="You may be overwithholding. Adjusting could increase your take-home pay.",
                category=InsightCategory.WITHHOLDING,
                urgency=InsightUrgency.FUTURE,
                impact=InsightImpact.LOW,
                estimated_savings=Decimal("0"),  # Cash flow, not savings
                deadline=None,
                action_steps=[
                    "Review your current W-4 allowances",
                    "Use IRS Tax Withholding Estimator",
                    "Consider if you prefer a larger refund or larger paycheck",
                ],
                relevant_forms=["W-4"],
                caveats=[
                    "Some prefer overwithholding as forced savings",
                    "Life changes may affect your actual tax liability",
                ],
                applies_to_situations=["employed", "overwithholding"],
            ))

        return insights

    def _generate_year_end_insights(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
        total_income: Decimal,
        current_deductions: Decimal,
        filing_status: str,
    ) -> List[TaxPlanningInsight]:
        """Generate year-end tax planning insights."""
        insights = []
        current_month = self.current_date.month

        if current_month < 10:
            return insights  # Too early for year-end planning

        standard_deduction = self.STANDARD_DEDUCTION.get(
            filing_status, self.STANDARD_DEDUCTION["single"]
        )

        # Check if close to itemizing threshold
        itemized_estimate = self._estimate_itemized_deductions(extracted_data, answers)

        if Decimal("0.8") * standard_deduction < itemized_estimate < Decimal("1.1") * standard_deduction:
            insights.append(TaxPlanningInsight(
                insight_id="year_end_itemize_threshold",
                title="Near Itemizing Threshold",
                description=f"Your itemized deductions (${itemized_estimate:,.0f}) are close to the standard deduction (${standard_deduction:,.0f}). Strategic moves could help.",
                category=InsightCategory.YEAR_END,
                urgency=InsightUrgency.YEAR_END,
                impact=InsightImpact.MEDIUM,
                estimated_savings=Decimal("400"),
                deadline=date(self.TAX_YEAR, 12, 31),
                action_steps=[
                    "Consider prepaying property taxes if under SALT limit",
                    "Make additional charitable contributions",
                    "Pay deductible expenses before year end",
                ],
                relevant_forms=["Schedule A"],
                caveats=[
                    "SALT deduction capped at $10,000",
                    "State tax prepayments may trigger AMT",
                ],
                applies_to_situations=["near_itemizing_threshold"],
            ))

        # Tax loss harvesting
        capital_gains = Decimal(str(extracted_data.get("capital_gains", 0) or 0))
        if capital_gains > 0:
            insights.append(TaxPlanningInsight(
                insight_id="year_end_loss_harvest",
                title="Consider Tax Loss Harvesting",
                description=f"You have ${capital_gains:,.0f} in capital gains. Selling losing positions could offset these gains.",
                category=InsightCategory.YEAR_END,
                urgency=InsightUrgency.YEAR_END,
                impact=InsightImpact.HIGH if capital_gains > 5000 else InsightImpact.MEDIUM,
                estimated_savings=capital_gains * Decimal("0.15"),  # 15% cap gains rate
                deadline=date(self.TAX_YEAR, 12, 31),
                action_steps=[
                    "Review your portfolio for positions with losses",
                    "Sell losing positions to realize losses",
                    "Wait 31 days before repurchasing (wash sale rule)",
                    "Can use up to $3,000 of net losses against ordinary income",
                ],
                relevant_forms=["Schedule D", "Form 8949"],
                caveats=[
                    "Wash sale rule: can't buy substantially identical security within 30 days",
                    "Consider if you want to maintain the position",
                ],
                applies_to_situations=["has_investments", "has_capital_gains"],
            ))

        return insights

    def _generate_healthcare_insights(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
        age: int,
        filing_status: str,
    ) -> List[TaxPlanningInsight]:
        """Generate healthcare-related tax insights."""
        insights = []

        # HSA contributions
        has_hdhp = answers.get("has_hdhp", False)
        if has_hdhp:
            current_hsa = Decimal(str(extracted_data.get("hsa_contributions", 0) or 0))
            is_family = filing_status in ["married_filing_jointly", "head_of_household"]
            limit_hsa = self.CONTRIBUTION_LIMITS["hsa_family"] if is_family else self.CONTRIBUTION_LIMITS["hsa_individual"]
            if age >= 55:
                limit_hsa += self.CONTRIBUTION_LIMITS["hsa_catchup"]

            remaining_hsa = limit_hsa - current_hsa
            if remaining_hsa > 0:
                insights.append(TaxPlanningInsight(
                    insight_id="healthcare_hsa_max",
                    title="Maximize HSA Contributions",
                    description=f"You have ${remaining_hsa:,.0f} of unused HSA contribution room. HSAs offer triple tax benefits.",
                    category=InsightCategory.HEALTHCARE,
                    urgency=InsightUrgency.YEAR_END,
                    impact=InsightImpact.HIGH,
                    estimated_savings=remaining_hsa * Decimal("0.30"),  # Tax + FICA savings
                    deadline=date(self.TAX_YEAR + 1, 4, 15),
                    action_steps=[
                        "Contribute additional amounts to your HSA",
                        "Can contribute through payroll (saves FICA too) or directly",
                        "Consider investing HSA funds for long-term growth",
                    ],
                    relevant_forms=["Form 8889", "Form 5498-SA"],
                    caveats=[
                        "Must have qualifying HDHP coverage",
                        "Can't be enrolled in Medicare",
                    ],
                    applies_to_situations=["has_hdhp"],
                ))

        # FSA use-it-or-lose-it
        fsa_balance = Decimal(str(answers.get("fsa_remaining_balance", 0) or 0))
        if fsa_balance > 0:
            insights.append(TaxPlanningInsight(
                insight_id="healthcare_fsa_use",
                title="Use Your FSA Balance",
                description=f"You have ${fsa_balance:,.0f} remaining in your FSA. Use it or lose it!",
                category=InsightCategory.HEALTHCARE,
                urgency=InsightUrgency.IMMEDIATE if self.current_date.month >= 11 else InsightUrgency.SOON,
                impact=InsightImpact.HIGH if fsa_balance > 500 else InsightImpact.MEDIUM,
                estimated_savings=fsa_balance,  # Total loss if not used
                deadline=date(self.TAX_YEAR, 12, 31),  # Or March 15 if grace period
                action_steps=[
                    "Schedule medical/dental/vision appointments",
                    "Purchase eligible medical supplies",
                    "Get new glasses or contacts",
                    "Stock up on OTC medications (now FSA eligible)",
                ],
                relevant_forms=[],
                caveats=[
                    "Check if your plan has rollover or grace period",
                    "Up to $610 may roll over if plan allows",
                ],
                applies_to_situations=["has_fsa"],
            ))

        return insights

    def _calculate_quarterly_estimates(
        self,
        total_income: Decimal,
        total_withholding: Decimal,
        filing_status: str,
    ) -> List[QuarterlyEstimate]:
        """Calculate quarterly estimated tax payments."""
        estimates = []

        projected_tax = self._project_tax_liability(total_income, Decimal("0"), filing_status)

        # Safe harbor: 100% of prior year or 90% of current year
        safe_harbor = projected_tax  # Simplified; would use prior year in real implementation

        required_annual = max(
            projected_tax * Decimal("0.9"),
            safe_harbor
        )

        # Calculate what's still needed
        remaining_tax = required_annual - total_withholding

        current_quarter = (self.current_date.month - 1) // 3 + 1

        for quarter in range(1, 5):
            due_date = self.QUARTERLY_DUE_DATES[quarter]

            # Calculate recommended payment for remaining quarters
            remaining_quarters = 5 - quarter
            recommended = remaining_tax / remaining_quarters if remaining_quarters > 0 else Decimal("0")

            # Determine penalty risk
            if quarter <= current_quarter:
                paid_ratio = total_withholding / required_annual if required_annual > 0 else Decimal("1")
                if paid_ratio < Decimal("0.22") * quarter:
                    penalty_risk = "high"
                elif paid_ratio < Decimal("0.25") * quarter:
                    penalty_risk = "medium"
                elif paid_ratio < Decimal("0.27") * quarter:
                    penalty_risk = "low"
                else:
                    penalty_risk = "none"
            else:
                penalty_risk = "none"

            estimates.append(QuarterlyEstimate(
                quarter=quarter,
                due_date=due_date,
                recommended_payment=max(recommended, Decimal("0")),
                ytd_income=total_income * quarter / 4,  # Simplified pro-rata
                ytd_tax_withheld=total_withholding * quarter / 4,
                projected_annual_tax=projected_tax,
                safe_harbor_amount=safe_harbor,
                penalty_risk=penalty_risk,
            ))

        return estimates

    def _generate_year_end_checklist(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
        insights: List[TaxPlanningInsight],
    ) -> List[Dict[str, Any]]:
        """Generate year-end tax planning checklist."""
        checklist = []

        # Always include these items
        base_items = [
            {
                "item": "Review W-4 withholding",
                "description": "Ensure withholding is on track for your actual tax liability",
                "completed": False,
            },
            {
                "item": "Maximize retirement contributions",
                "description": "Max out 401(k), IRA, and HSA if possible",
                "completed": False,
            },
            {
                "item": "Gather tax documents",
                "description": "Collect W-2s, 1099s, receipts for deductions",
                "completed": False,
            },
            {
                "item": "Review flexible spending accounts",
                "description": "Use or lose FSA funds by deadline",
                "completed": False,
            },
        ]
        checklist.extend(base_items)

        # Add items based on insights
        for insight in insights:
            if insight.urgency in [InsightUrgency.IMMEDIATE, InsightUrgency.SOON, InsightUrgency.YEAR_END]:
                checklist.append({
                    "item": insight.title,
                    "description": insight.description,
                    "completed": False,
                    "deadline": insight.deadline.isoformat() if insight.deadline else None,
                })

        return checklist

    def _project_tax_liability(
        self,
        total_income: Decimal,
        deductions: Decimal,
        filing_status: str,
    ) -> Decimal:
        """Project federal tax liability."""
        standard_deduction = self.STANDARD_DEDUCTION.get(
            filing_status, self.STANDARD_DEDUCTION["single"]
        )

        # Use larger of standard or itemized
        total_deduction = max(standard_deduction, deductions)

        taxable_income = max(total_income - total_deduction, Decimal("0"))

        # 2025 tax brackets (simplified - single filer rates, IRS Rev. Proc. 2024-40)
        brackets = [
            (Decimal("11925"), Decimal("0.10")),
            (Decimal("48475"), Decimal("0.12")),
            (Decimal("103350"), Decimal("0.22")),
            (Decimal("197300"), Decimal("0.24")),
            (Decimal("250525"), Decimal("0.32")),
            (Decimal("626350"), Decimal("0.35")),
            (Decimal("999999999"), Decimal("0.37")),
        ]

        tax = Decimal("0")
        prev_bracket = Decimal("0")

        for bracket_max, rate in brackets:
            if taxable_income <= 0:
                break
            bracket_income = min(taxable_income, bracket_max - prev_bracket)
            tax += bracket_income * rate
            taxable_income -= bracket_income
            prev_bracket = bracket_max

        return tax

    def _estimate_marginal_rate(
        self,
        total_income: Decimal,
        filing_status: str,
    ) -> Decimal:
        """Estimate marginal tax rate."""
        standard_deduction = self.STANDARD_DEDUCTION.get(
            filing_status, self.STANDARD_DEDUCTION["single"]
        )
        taxable_income = total_income - standard_deduction

        # 2025 brackets (IRS Rev. Proc. 2024-40)
        if taxable_income <= 11925:
            return Decimal("0.10")
        elif taxable_income <= 48475:
            return Decimal("0.12")
        elif taxable_income <= 103350:
            return Decimal("0.22")
        elif taxable_income <= 197300:
            return Decimal("0.24")
        elif taxable_income <= 250525:
            return Decimal("0.32")
        elif taxable_income <= 626350:
            return Decimal("0.35")
        else:
            return Decimal("0.37")

    def _estimate_itemized_deductions(
        self,
        extracted_data: Dict[str, Any],
        answers: Dict[str, Any],
    ) -> Decimal:
        """Estimate itemized deductions."""
        total = Decimal("0")

        # Mortgage interest
        mortgage_interest = Decimal(str(extracted_data.get("mortgage_interest", 0) or 0))
        total += mortgage_interest

        # SALT (capped at $10,000)
        state_taxes = Decimal(str(extracted_data.get("state_income_tax", 0) or 0))
        property_taxes = Decimal(str(extracted_data.get("property_taxes", 0) or 0))
        salt = min(state_taxes + property_taxes, Decimal("10000"))
        total += salt

        # Charitable contributions
        charitable = Decimal(str(answers.get("charitable_contributions", 0) or 0))
        total += charitable

        # Medical expenses (if over 7.5% of AGI - simplified)
        medical = Decimal(str(answers.get("medical_expenses", 0) or 0))
        agi = self._calculate_total_income(extracted_data)
        medical_threshold = agi * Decimal("0.075")
        if medical > medical_threshold:
            total += medical - medical_threshold

        return total

    def _generate_summary(
        self,
        insights: List[TaxPlanningInsight],
        projected_tax: Decimal,
        total_withholding: Decimal,
        optimization_potential: Decimal,
    ) -> str:
        """Generate planning report summary."""
        refund_or_owed = total_withholding - projected_tax

        urgent_count = sum(1 for i in insights if i.urgency == InsightUrgency.IMMEDIATE)
        high_impact_count = sum(1 for i in insights if i.impact == InsightImpact.HIGH)

        if refund_or_owed >= 0:
            status = f"projected refund of ${refund_or_owed:,.0f}"
        else:
            status = f"projected to owe ${-refund_or_owed:,.0f}"

        summary_parts = [
            f"Based on your current tax situation, you have a {status}.",
        ]

        if optimization_potential > 0:
            summary_parts.append(
                f"We identified ${optimization_potential:,.0f} in potential tax savings opportunities."
            )

        if urgent_count > 0:
            summary_parts.append(
                f"You have {urgent_count} action item(s) requiring immediate attention."
            )

        if high_impact_count > 0:
            summary_parts.append(
                f"There are {high_impact_count} high-impact opportunities to explore."
            )

        return " ".join(summary_parts)
