"""
Tax Optimization Recommendations Engine

Analyzes tax returns and provides actionable recommendations to help
users reduce their tax liability and maximize refunds.

This is a key driver of product stickiness - users return because
they get valuable, personalized insights.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal


class RecommendationCategory(str, Enum):
    """Categories of tax recommendations."""
    IMMEDIATE_ACTION = "immediate_action"  # Can act on now for current year
    DEDUCTION_OPPORTUNITY = "deduction_opportunity"
    CREDIT_OPPORTUNITY = "credit_opportunity"
    RETIREMENT_PLANNING = "retirement_planning"
    INVESTMENT_STRATEGY = "investment_strategy"
    TIMING_OPTIMIZATION = "timing_optimization"
    WARNING = "warning"
    INFORMATIONAL = "informational"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    HIGH = "high"      # Potential savings > $500
    MEDIUM = "medium"  # Potential savings $100-$500
    LOW = "low"        # Potential savings < $100 or informational


@dataclass
class TaxRecommendation:
    """A single tax optimization recommendation."""
    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    description: str
    potential_savings: Optional[float] = None
    action_items: List[str] = field(default_factory=list)
    learn_more_topic: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "potential_savings": self.potential_savings,
            "action_items": self.action_items,
            "learn_more_topic": self.learn_more_topic,
        }


@dataclass
class RecommendationsResult:
    """Collection of recommendations for a tax return."""
    recommendations: List[TaxRecommendation]
    total_potential_savings: float
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "total_potential_savings": self.total_potential_savings,
            "summary": self.summary,
            "count_by_priority": {
                "high": len([r for r in self.recommendations if r.priority == RecommendationPriority.HIGH]),
                "medium": len([r for r in self.recommendations if r.priority == RecommendationPriority.MEDIUM]),
                "low": len([r for r in self.recommendations if r.priority == RecommendationPriority.LOW]),
            }
        }


class TaxRecommendationEngine:
    """
    Analyzes tax returns and generates personalized recommendations.

    This engine is critical for product stickiness - it provides value
    beyond just filing taxes by helping users save money.
    """

    # 2025 IRS limits for reference
    IRS_LIMITS_2025 = {
        "ira_contribution_limit": 7000,
        "ira_contribution_limit_50plus": 8000,
        "401k_contribution_limit": 23500,
        "401k_contribution_limit_50plus": 31000,
        "hsa_individual_limit": 4300,
        "hsa_family_limit": 8550,
        "hsa_catchup_55plus": 1000,
        "student_loan_interest_max": 2500,
        "educator_expense_max": 300,
        "salt_cap": 10000,
        "charitable_agi_limit_cash": 0.60,  # 60% of AGI
        "standard_deduction_single": 15750,  # 2025
        "standard_deduction_mfj": 31500,     # 2025
    }

    def __init__(self):
        pass

    def analyze(self, tax_return, calculation_breakdown=None) -> RecommendationsResult:
        """
        Analyze a tax return and generate recommendations.

        Args:
            tax_return: TaxReturn model instance
            calculation_breakdown: Optional CalculationBreakdown for more detailed analysis

        Returns:
            RecommendationsResult with all recommendations
        """
        recommendations = []

        # Run all analyzers
        recommendations.extend(self._analyze_retirement_opportunities(tax_return))
        recommendations.extend(self._analyze_deduction_opportunities(tax_return))
        recommendations.extend(self._analyze_credit_opportunities(tax_return))
        recommendations.extend(self._analyze_investment_opportunities(tax_return))
        recommendations.extend(self._analyze_timing_opportunities(tax_return))
        recommendations.extend(self._analyze_warnings(tax_return))

        # Calculate total potential savings
        total_savings = sum(
            r.potential_savings or 0
            for r in recommendations
            if r.potential_savings and r.potential_savings > 0
        )

        # Sort by priority
        priority_order = {
            RecommendationPriority.HIGH: 0,
            RecommendationPriority.MEDIUM: 1,
            RecommendationPriority.LOW: 2,
        }
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

        # Generate summary
        summary = self._generate_summary(recommendations, total_savings)

        return RecommendationsResult(
            recommendations=recommendations,
            total_potential_savings=float(money(total_savings)),
            summary=summary,
        )

    def _analyze_retirement_opportunities(self, tax_return) -> List[TaxRecommendation]:
        """Analyze retirement contribution opportunities."""
        recommendations = []

        taxpayer = tax_return.taxpayer
        deductions = tax_return.deductions
        income = tax_return.income
        agi = tax_return.adjusted_gross_income or 0

        # Check age for catch-up contributions
        is_50_plus = getattr(taxpayer, 'is_over_65', False)  # Simplified

        # IRA contribution check
        ira_limit = self.IRS_LIMITS_2025["ira_contribution_limit_50plus" if is_50_plus else "ira_contribution_limit"]
        current_ira = deductions.ira_contributions or 0

        if current_ira < ira_limit and agi > 0:
            remaining_ira = ira_limit - current_ira
            # Estimate tax savings (assume 22% bracket for simplicity)
            estimated_marginal_rate = self._estimate_marginal_rate(agi, taxpayer.filing_status.value)
            potential_savings = remaining_ira * estimated_marginal_rate

            if potential_savings > 50:  # Only recommend if meaningful savings
                recommendations.append(TaxRecommendation(
                    category=RecommendationCategory.RETIREMENT_PLANNING,
                    priority=RecommendationPriority.HIGH if potential_savings > 500 else RecommendationPriority.MEDIUM,
                    title="Maximize Your IRA Contribution",
                    description=f"You can still contribute up to ${remaining_ira:,.0f} to a Traditional IRA for 2025. "
                               f"This could reduce your taxable income and save you approximately ${potential_savings:,.0f} in taxes.",
                    potential_savings=float(money(potential_savings)),
                    action_items=[
                        f"Contribute up to ${remaining_ira:,.0f} to your Traditional IRA",
                        "Deadline: April 15, 2026 for 2025 tax year",
                        "Consider monthly contributions to make it easier"
                    ],
                    learn_more_topic="ira_contributions"
                ))

        # HSA contribution check (if applicable)
        hsa_contributions = deductions.hsa_contributions or 0
        if hsa_contributions > 0:  # User has HSA
            hsa_limit = self.IRS_LIMITS_2025["hsa_family_limit"]  # Assume family for max opportunity
            if hsa_contributions < hsa_limit:
                remaining_hsa = hsa_limit - hsa_contributions
                potential_savings = remaining_hsa * self._estimate_marginal_rate(agi, taxpayer.filing_status.value)

                if remaining_hsa > 100:
                    recommendations.append(TaxRecommendation(
                        category=RecommendationCategory.RETIREMENT_PLANNING,
                        priority=RecommendationPriority.MEDIUM,
                        title="Maximize HSA Contributions",
                        description=f"Health Savings Accounts offer triple tax benefits. "
                                   f"You may be able to contribute up to ${remaining_hsa:,.0f} more.",
                        potential_savings=float(money(potential_savings)),
                        action_items=[
                            "Check your HSA eligibility (requires HDHP)",
                            f"Consider contributing up to ${remaining_hsa:,.0f} more",
                            "HSA funds roll over year to year"
                        ],
                        learn_more_topic="hsa_benefits"
                    ))

        return recommendations

    def _analyze_deduction_opportunities(self, tax_return) -> List[TaxRecommendation]:
        """Analyze deduction optimization opportunities."""
        recommendations = []

        deductions = tax_return.deductions
        taxpayer = tax_return.taxpayer
        agi = tax_return.adjusted_gross_income or 0
        filing_status = taxpayer.filing_status.value

        # Standard vs Itemized comparison
        itemized = deductions.itemized
        standard = deductions._get_standard_deduction(
            filing_status,
            getattr(taxpayer, 'is_over_65', False),
            getattr(taxpayer, 'is_blind', False)
        )
        itemized_total = itemized.get_total_itemized(agi)

        if deductions.use_standard_deduction:
            # Check if they're close to itemizing
            gap = standard - itemized_total
            if 0 < gap < 3000:
                recommendations.append(TaxRecommendation(
                    category=RecommendationCategory.DEDUCTION_OPPORTUNITY,
                    priority=RecommendationPriority.MEDIUM,
                    title="You're Close to Itemizing",
                    description=f"Your itemized deductions (${itemized_total:,.0f}) are only ${gap:,.0f} below "
                               f"the standard deduction (${standard:,.0f}). Consider bunching deductions.",
                    potential_savings=None,
                    action_items=[
                        "Consider 'bunching' charitable donations into one year",
                        "Prepay property taxes if possible",
                        "Time medical procedures strategically"
                    ],
                    learn_more_topic="bunching_deductions"
                ))
        else:
            # Already itemizing - check for missed deductions
            if itemized.charitable_cash == 0 and itemized.charitable_non_cash == 0:
                recommendations.append(TaxRecommendation(
                    category=RecommendationCategory.DEDUCTION_OPPORTUNITY,
                    priority=RecommendationPriority.LOW,
                    title="Track Charitable Contributions",
                    description="You're itemizing but haven't recorded charitable contributions. "
                               "Even small donations can add up.",
                    potential_savings=None,
                    action_items=[
                        "Keep receipts for all donations",
                        "Don't forget non-cash donations (clothing, goods)",
                        "Consider donor-advised funds for flexibility"
                    ],
                    learn_more_topic="charitable_deductions"
                ))

        # Student loan interest check
        student_loan = deductions.student_loan_interest or 0
        if student_loan > 0 and student_loan < self.IRS_LIMITS_2025["student_loan_interest_max"]:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.INFORMATIONAL,
                priority=RecommendationPriority.LOW,
                title="Student Loan Interest Deduction",
                description=f"You claimed ${student_loan:,.0f} in student loan interest. "
                           f"The maximum deduction is ${self.IRS_LIMITS_2025['student_loan_interest_max']:,}.",
                potential_savings=None,
                action_items=[
                    "Ensure you received Form 1098-E from all loan servicers",
                    "Interest on qualified education loans is deductible"
                ],
                learn_more_topic="student_loan_interest"
            ))

        # Educator expenses check
        educator = deductions.educator_expenses or 0
        if educator > 0 and educator < self.IRS_LIMITS_2025["educator_expense_max"]:
            remaining = self.IRS_LIMITS_2025["educator_expense_max"] - educator
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.INFORMATIONAL,
                priority=RecommendationPriority.LOW,
                title="Educator Expense Deduction",
                description=f"You can deduct up to ${remaining:,.0f} more in educator expenses this year.",
                potential_savings=None,
                action_items=[
                    "Keep receipts for classroom supplies",
                    "Books, materials, and equipment qualify",
                    "Professional development courses may qualify"
                ],
                learn_more_topic="educator_expenses"
            ))

        return recommendations

    def _analyze_credit_opportunities(self, tax_return) -> List[TaxRecommendation]:
        """Analyze tax credit opportunities."""
        recommendations = []

        credits = tax_return.credits if hasattr(tax_return, 'credits') else None
        taxpayer = tax_return.taxpayer
        income = tax_return.income

        if not credits:
            return recommendations

        # Child Tax Credit analysis
        num_dependents = len(taxpayer.dependents) if taxpayer.dependents else 0
        num_ctc_children = getattr(credits, 'child_tax_credit_children', 0)

        if num_dependents > num_ctc_children:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.CREDIT_OPPORTUNITY,
                priority=RecommendationPriority.HIGH,
                title="Verify Child Tax Credit Eligibility",
                description=f"You have {num_dependents} dependents but only {num_ctc_children} qualify for Child Tax Credit. "
                           "Each qualifying child can provide up to $2,000 in credits.",
                potential_savings=(num_dependents - num_ctc_children) * 2000,
                action_items=[
                    "Children must be under 17 at end of tax year",
                    "Child must have valid SSN",
                    "Child must live with you for more than half the year"
                ],
                learn_more_topic="child_tax_credit"
            ))

        # Child care credit check
        child_care = getattr(credits, 'child_care_credit', 0) or 0
        child_care_expenses = getattr(credits, 'child_care_expenses', 0) or 0

        if num_dependents > 0 and child_care_expenses == 0:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.CREDIT_OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title="Child and Dependent Care Credit",
                description="If you pay for child care while working, you may qualify for a credit of 20-35% "
                           "of expenses up to $3,000 per child.",
                potential_savings=None,
                action_items=[
                    "Keep records of daycare/childcare payments",
                    "Get provider's Tax ID number",
                    "After-school programs may qualify"
                ],
                learn_more_topic="child_care_credit"
            ))

        # Education credits
        education_credits = getattr(credits, 'education_credits', 0) or 0
        if education_credits == 0 and num_dependents > 0:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.CREDIT_OPPORTUNITY,
                priority=RecommendationPriority.MEDIUM,
                title="Education Tax Credits Available",
                description="If you or a dependent is in college, you may qualify for the American Opportunity "
                           "Credit (up to $2,500) or Lifetime Learning Credit (up to $2,000).",
                potential_savings=2500,
                action_items=[
                    "Request Form 1098-T from educational institution",
                    "Keep receipts for tuition and required materials",
                    "AOTC is available for first 4 years of college"
                ],
                learn_more_topic="education_credits"
            ))

        # Retirement Savings Contributions Credit (Saver's Credit)
        agi = tax_return.adjusted_gross_income or 0
        ira_contributions = tax_return.deductions.ira_contributions or 0

        # Saver's Credit AGI limits for 2025 (estimated)
        savers_credit_limit = 38250 if taxpayer.filing_status.value == "single" else 76500

        if agi <= savers_credit_limit and ira_contributions > 0:
            if getattr(credits, 'retirement_savings_credit', 0) == 0:
                recommendations.append(TaxRecommendation(
                    category=RecommendationCategory.CREDIT_OPPORTUNITY,
                    priority=RecommendationPriority.MEDIUM,
                    title="Saver's Credit May Apply",
                    description="Based on your income, you may qualify for the Retirement Savings Contributions Credit "
                               "(Saver's Credit) of up to $1,000 ($2,000 if married filing jointly).",
                    potential_savings=1000 if taxpayer.filing_status.value == "single" else 2000,
                    action_items=[
                        "Review Form 8880 eligibility",
                        "Credit is in addition to IRA deduction",
                        "Must be 18+ and not a full-time student"
                    ],
                    learn_more_topic="savers_credit"
                ))

        return recommendations

    def _analyze_investment_opportunities(self, tax_return) -> List[TaxRecommendation]:
        """Analyze investment-related tax opportunities."""
        recommendations = []

        income = tax_return.income

        # Capital gains analysis
        short_term_gains = income.short_term_capital_gains or 0
        long_term_gains = income.long_term_capital_gains or 0

        if short_term_gains > 1000:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.INVESTMENT_STRATEGY,
                priority=RecommendationPriority.MEDIUM,
                title="Short-Term vs Long-Term Capital Gains",
                description=f"You have ${short_term_gains:,.0f} in short-term capital gains (taxed at ordinary rates). "
                           "Holding investments for over 1 year qualifies for lower long-term capital gains rates (0%, 15%, or 20%).",
                potential_savings=short_term_gains * 0.10,  # Estimate 10% rate difference
                action_items=[
                    "Consider holding investments for at least 1 year",
                    "Review upcoming sales for holding period",
                    "Long-term rate can be 0% for lower income taxpayers"
                ],
                learn_more_topic="capital_gains_rates"
            ))

        # Qualified dividends check
        ordinary_dividends = income.dividend_income or 0
        qualified_dividends = income.qualified_dividends or 0

        if ordinary_dividends > 0 and qualified_dividends < ordinary_dividends * 0.5:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.INVESTMENT_STRATEGY,
                priority=RecommendationPriority.LOW,
                title="Qualified Dividend Opportunity",
                description="Only a portion of your dividends are 'qualified' (taxed at lower rates). "
                           "Consider funds/stocks that pay qualified dividends.",
                potential_savings=None,
                action_items=[
                    "Hold dividend stocks for 60+ days around ex-dividend date",
                    "Index funds often pay qualified dividends",
                    "REIT dividends are typically not qualified"
                ],
                learn_more_topic="qualified_dividends"
            ))

        return recommendations

    def _analyze_timing_opportunities(self, tax_return) -> List[TaxRecommendation]:
        """Analyze timing-related tax opportunities."""
        recommendations = []

        agi = tax_return.adjusted_gross_income or 0
        filing_status = tax_return.taxpayer.filing_status.value

        # Check if near bracket boundary (2025 values - IRS Rev. Proc. 2024-40)
        bracket_boundaries = {
            "single": [11925, 48475, 103350, 197300, 250525, 626350],
            "married_joint": [23850, 96950, 206700, 394600, 501050, 751600],
            "married_separate": [11925, 48475, 103350, 197300, 250525, 375800],
            "head_of_household": [17000, 64850, 103350, 197300, 250500, 626350],
        }

        boundaries = bracket_boundaries.get(filing_status, bracket_boundaries["single"])

        for boundary in boundaries:
            if 0 < boundary - agi < 5000:
                recommendations.append(TaxRecommendation(
                    category=RecommendationCategory.TIMING_OPTIMIZATION,
                    priority=RecommendationPriority.MEDIUM,
                    title="Near Tax Bracket Boundary",
                    description=f"Your AGI (${agi:,.0f}) is close to the ${boundary:,} bracket boundary. "
                               "Additional deductions could keep you in a lower tax bracket.",
                    potential_savings=(boundary - agi) * 0.02,  # 2% rate difference
                    action_items=[
                        "Consider maximizing retirement contributions",
                        "Prepay deductible expenses if possible",
                        "Defer income to next year if feasible"
                    ],
                    learn_more_topic="tax_brackets"
                ))
                break

        return recommendations

    def _analyze_warnings(self, tax_return) -> List[TaxRecommendation]:
        """Generate warnings about potential issues."""
        recommendations = []

        income = tax_return.income
        taxpayer = tax_return.taxpayer

        # Estimated tax warning
        total_tax = tax_return.tax_liability or 0
        withholding = income.federal_withholding or 0

        if total_tax > 0 and withholding < total_tax * 0.90:
            underpayment = total_tax - withholding
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.WARNING,
                priority=RecommendationPriority.HIGH,
                title="Potential Underpayment Penalty",
                description=f"Your withholding (${withholding:,.0f}) is less than 90% of your tax liability "
                           f"(${total_tax:,.0f}). You may owe an underpayment penalty.",
                potential_savings=None,
                action_items=[
                    "Increase W-4 withholding for next year",
                    "Consider making estimated tax payments",
                    "File by deadline to minimize penalties"
                ],
                learn_more_topic="estimated_taxes"
            ))

        # Self-employment tax warning
        se_income = income.self_employment_income or 0
        if se_income > 0 and (income.estimated_tax_payments or 0) == 0:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.WARNING,
                priority=RecommendationPriority.MEDIUM,
                title="Self-Employment Tax Planning",
                description=f"You have ${se_income:,.0f} in self-employment income. "
                           "Self-employed individuals typically need to make quarterly estimated tax payments.",
                potential_savings=None,
                action_items=[
                    "Calculate quarterly estimated tax payments",
                    "Set aside 25-30% of SE income for taxes",
                    "Consider S-corp election if income is high"
                ],
                learn_more_topic="self_employment_tax"
            ))

        # Missing SSN warning
        if not taxpayer.ssn:
            recommendations.append(TaxRecommendation(
                category=RecommendationCategory.WARNING,
                priority=RecommendationPriority.HIGH,
                title="Social Security Number Required",
                description="A valid Social Security Number is required to file your tax return.",
                potential_savings=None,
                action_items=[
                    "Enter your SSN before filing",
                    "Ensure SSN matches Social Security records"
                ],
                learn_more_topic=None
            ))

        return recommendations

    def _estimate_marginal_rate(self, agi: float, filing_status: str) -> float:
        """Estimate marginal tax rate for savings calculations (2025 brackets)."""
        # 2025 bracket estimation (IRS Rev. Proc. 2024-40)
        if filing_status == "married_joint":
            if agi <= 23850:
                return 0.10
            elif agi <= 96950:
                return 0.12
            elif agi <= 206700:
                return 0.22
            elif agi <= 394600:
                return 0.24
            elif agi <= 501050:
                return 0.32
            elif agi <= 751600:
                return 0.35
            else:
                return 0.37
        else:  # Single and other
            if agi <= 11925:
                return 0.10
            elif agi <= 48475:
                return 0.12
            elif agi <= 103350:
                return 0.22
            elif agi <= 197300:
                return 0.24
            elif agi <= 250525:
                return 0.32
            elif agi <= 626350:
                return 0.35
            else:
                return 0.37

    def _generate_summary(self, recommendations: List[TaxRecommendation], total_savings: float) -> str:
        """Generate a human-readable summary of recommendations."""
        if not recommendations:
            return "Great news! We didn't find any immediate tax optimization opportunities. Your tax situation looks well-optimized."

        high_priority = [r for r in recommendations if r.priority == RecommendationPriority.HIGH]

        if high_priority:
            summary = f"We found {len(high_priority)} high-priority recommendation(s) that could save you money. "
        else:
            summary = f"We found {len(recommendations)} recommendation(s) to optimize your taxes. "

        if total_savings > 0:
            summary += f"Total potential savings: ${total_savings:,.0f}."

        return summary


# Convenience function
def get_recommendations(tax_return, calculation_breakdown=None) -> RecommendationsResult:
    """Get tax recommendations for a tax return."""
    engine = TaxRecommendationEngine()
    return engine.analyze(tax_return, calculation_breakdown)
