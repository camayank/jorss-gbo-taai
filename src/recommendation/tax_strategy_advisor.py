"""Tax Strategy Advisor.

Provides comprehensive tax-saving strategies and recommendations based on
the taxpayer's complete financial picture and circumstances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum
from datetime import date

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.tax_calculator import TaxCalculator


class StrategyCategory(Enum):
    """Categories of tax strategies."""
    RETIREMENT = "retirement"
    HEALTHCARE = "healthcare"
    INVESTMENT = "investment"
    EDUCATION = "education"
    CHARITABLE = "charitable"
    REAL_ESTATE = "real_estate"
    BUSINESS = "business"
    TIMING = "timing"
    STATE_SPECIFIC = "state_specific"
    FAMILY = "family"


class StrategyPriority(Enum):
    """Priority levels for strategies."""
    IMMEDIATE = "immediate"  # Do this now
    CURRENT_YEAR = "current_year"  # Before Dec 31
    NEXT_YEAR = "next_year"  # Plan for next year
    LONG_TERM = "long_term"  # Multi-year planning


@dataclass
class TaxStrategy:
    """Individual tax strategy recommendation."""
    title: str
    category: str
    priority: str
    estimated_savings: float  # Annual or one-time
    description: str
    action_steps: List[str]
    requirements: List[str]
    risks_considerations: List[str]
    deadline: Optional[str] = None
    complexity: str = "simple"  # simple, moderate, complex
    professional_help_recommended: bool = False


@dataclass
class RetirementAnalysis:
    """Analysis of retirement contribution strategies."""
    current_401k_contribution: float
    max_401k_contribution: float  # $23,500 for 2025
    current_ira_contribution: float
    max_ira_contribution: float  # $7,000 for 2025
    catch_up_eligible: bool  # Age 50+
    catch_up_amount: float  # $7,500 for 401k, $1,000 for IRA
    roth_vs_traditional_recommendation: str
    employer_match_captured: float
    employer_match_available: float
    additional_contribution_potential: float
    tax_savings_if_maxed: float


@dataclass
class InvestmentAnalysis:
    """Analysis of investment-related tax strategies."""
    unrealized_gains: float
    unrealized_losses: float
    tax_loss_harvesting_potential: float
    qualified_dividend_amount: float
    long_term_vs_short_term_gains: Dict[str, float]
    estimated_niit_exposure: float  # Net Investment Income Tax
    tax_efficient_placement_recommendations: List[str]


@dataclass
class TaxStrategyReport:
    """Complete tax strategy report."""
    filing_status: str
    tax_year: int
    current_tax_liability: float
    current_effective_rate: float

    # Analysis sections
    retirement_analysis: RetirementAnalysis
    investment_analysis: InvestmentAnalysis

    # Strategies organized by priority
    immediate_strategies: List[TaxStrategy]
    current_year_strategies: List[TaxStrategy]
    next_year_strategies: List[TaxStrategy]
    long_term_strategies: List[TaxStrategy]

    # Summary
    total_potential_savings: float
    top_three_recommendations: List[str]
    confidence_score: float
    warnings: List[str] = field(default_factory=list)


class TaxStrategyAdvisor:
    """
    Provides comprehensive tax planning strategies and recommendations.

    This advisor analyzes the taxpayer's complete financial picture and
    identifies opportunities for tax optimization across all areas including
    retirement, investments, healthcare, education, and more.
    """

    # 2025 Limits and Thresholds
    LIMITS_2025 = {
        "401k_limit": 23500,
        "401k_catch_up": 7500,
        "ira_limit": 7000,
        "ira_catch_up": 1000,
        "hsa_individual": 4300,
        "hsa_family": 8550,
        "hsa_catch_up": 1000,
        "fsa_limit": 3300,
        "social_security_wage_base": 176100,
        "niit_threshold_single": 200000,
        "niit_threshold_mfj": 250000,
        "amt_exemption_single": 88100,
        "amt_exemption_mfj": 137000,
        "estate_exemption": 13990000,
        "gift_annual_exclusion": 19000,
        "qcd_limit": 105000,  # Qualified Charitable Distribution
    }

    # Tax Brackets for marginal rate calculation
    TAX_BRACKETS_2025 = {
        "single": [
            (11925, 0.10), (48475, 0.12), (103350, 0.22),
            (197300, 0.24), (250525, 0.32), (626350, 0.35), (float('inf'), 0.37)
        ],
        "married_joint": [
            (23850, 0.10), (96950, 0.12), (206700, 0.22),
            (394600, 0.24), (501050, 0.32), (751600, 0.35), (float('inf'), 0.37)
        ],
    }

    def __init__(self, calculator: Optional["TaxCalculator"] = None):
        """Initialize the advisor with an optional calculator."""
        self._calculator = calculator

    def generate_strategy_report(self, tax_return: "TaxReturn") -> TaxStrategyReport:
        """
        Generate comprehensive tax strategy report.

        Args:
            tax_return: The tax return to analyze

        Returns:
            TaxStrategyReport with all strategies and recommendations
        """
        filing_status = self._normalize_filing_status(
            tax_return.taxpayer.filing_status.value
        )
        agi = tax_return.adjusted_gross_income or 0.0
        tax_liability = tax_return.tax_liability or 0.0

        # Calculate effective rate
        effective_rate = (tax_liability / agi * 100) if agi > 0 else 0.0

        # Get marginal rate
        marginal_rate = self._get_marginal_rate(filing_status, agi)

        # Run analyses
        retirement_analysis = self._analyze_retirement(tax_return, filing_status, agi, marginal_rate)
        investment_analysis = self._analyze_investments(tax_return, filing_status, agi)

        # Generate strategies by category
        all_strategies = []

        all_strategies.extend(self._retirement_strategies(tax_return, retirement_analysis, marginal_rate))
        all_strategies.extend(self._healthcare_strategies(tax_return, filing_status, agi, marginal_rate))
        all_strategies.extend(self._investment_strategies(tax_return, investment_analysis, marginal_rate))
        all_strategies.extend(self._education_strategies(tax_return, filing_status, agi))
        all_strategies.extend(self._charitable_strategies(tax_return, filing_status, agi, marginal_rate))
        all_strategies.extend(self._timing_strategies(tax_return, filing_status, agi, marginal_rate))
        all_strategies.extend(self._business_strategies(tax_return, filing_status, agi, marginal_rate))
        all_strategies.extend(self._family_strategies(tax_return, filing_status, agi))
        all_strategies.extend(self._state_strategies(tax_return, filing_status, agi))

        # Sort by priority and estimated savings
        immediate = [s for s in all_strategies if s.priority == "immediate"]
        current_year = [s for s in all_strategies if s.priority == "current_year"]
        next_year = [s for s in all_strategies if s.priority == "next_year"]
        long_term = [s for s in all_strategies if s.priority == "long_term"]

        # Sort each list by savings
        immediate.sort(key=lambda x: x.estimated_savings, reverse=True)
        current_year.sort(key=lambda x: x.estimated_savings, reverse=True)
        next_year.sort(key=lambda x: x.estimated_savings, reverse=True)
        long_term.sort(key=lambda x: x.estimated_savings, reverse=True)

        # Calculate total potential savings
        total_savings = sum(s.estimated_savings for s in all_strategies)

        # Get top 3 recommendations
        all_sorted = sorted(all_strategies, key=lambda x: x.estimated_savings, reverse=True)
        top_three = [s.title for s in all_sorted[:3]]

        # Generate warnings
        warnings = self._generate_warnings(tax_return, agi, marginal_rate)

        # Calculate confidence
        confidence = self._calculate_confidence(tax_return, all_strategies)

        return TaxStrategyReport(
            filing_status=filing_status,
            tax_year=2025,
            current_tax_liability=round(tax_liability, 2),
            current_effective_rate=round(effective_rate, 2),
            retirement_analysis=retirement_analysis,
            investment_analysis=investment_analysis,
            immediate_strategies=immediate[:5],  # Top 5 per category
            current_year_strategies=current_year[:5],
            next_year_strategies=next_year[:5],
            long_term_strategies=long_term[:5],
            total_potential_savings=round(total_savings, 2),
            top_three_recommendations=top_three,
            confidence_score=confidence,
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
            "qualifying_widow": "married_joint",
        }
        return status_map.get(status.lower(), "single")

    def _get_marginal_rate(self, filing_status: str, agi: float) -> float:
        """Get marginal tax rate."""
        brackets = self.TAX_BRACKETS_2025.get(filing_status, self.TAX_BRACKETS_2025["single"])
        for threshold, rate in brackets:
            if agi <= threshold:
                return rate * 100
        return 37.0

    def _analyze_retirement(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float,
        marginal_rate: float
    ) -> RetirementAnalysis:
        """Analyze retirement contribution opportunities."""
        income = tax_return.income
        taxpayer = tax_return.taxpayer

        # Get current contributions
        current_401k = getattr(income, 'retirement_contributions_401k', 0) or 0
        current_ira = getattr(income, 'retirement_contributions_ira', 0) or 0

        # Check age for catch-up
        age = getattr(taxpayer, 'age', 40)
        catch_up_eligible = age >= 50

        # Calculate limits
        max_401k = self.LIMITS_2025["401k_limit"]
        max_ira = self.LIMITS_2025["ira_limit"]

        if catch_up_eligible:
            max_401k += self.LIMITS_2025["401k_catch_up"]
            max_ira += self.LIMITS_2025["ira_catch_up"]

        catch_up_amount = (
            self.LIMITS_2025["401k_catch_up"] + self.LIMITS_2025["ira_catch_up"]
            if catch_up_eligible else 0
        )

        # Employer match
        employer_match_rate = getattr(income, 'employer_match_rate', 0.03) or 0.03
        employer_match_limit = getattr(income, 'employer_match_limit', 0.06) or 0.06
        wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0

        match_eligible = min(current_401k, wages * employer_match_limit)
        employer_match_captured = match_eligible * (employer_match_rate / employer_match_limit)
        employer_match_available = wages * employer_match_limit * (employer_match_rate / employer_match_limit)

        # Additional contribution potential
        additional_401k = max(0, max_401k - current_401k)
        additional_ira = max(0, max_ira - current_ira)
        additional_potential = additional_401k + additional_ira

        # Tax savings if maxed
        tax_savings = additional_potential * (marginal_rate / 100)

        # Roth vs Traditional recommendation
        if marginal_rate >= 32:
            roth_rec = "Traditional (pre-tax) recommended - high current marginal rate"
        elif marginal_rate <= 12:
            roth_rec = "Roth recommended - low current marginal rate, tax-free growth"
        else:
            roth_rec = "Consider split strategy - both traditional and Roth for flexibility"

        return RetirementAnalysis(
            current_401k_contribution=current_401k,
            max_401k_contribution=max_401k,
            current_ira_contribution=current_ira,
            max_ira_contribution=max_ira,
            catch_up_eligible=catch_up_eligible,
            catch_up_amount=catch_up_amount,
            roth_vs_traditional_recommendation=roth_rec,
            employer_match_captured=round(employer_match_captured, 2),
            employer_match_available=round(employer_match_available, 2),
            additional_contribution_potential=round(additional_potential, 2),
            tax_savings_if_maxed=round(tax_savings, 2),
        )

    def _analyze_investments(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float
    ) -> InvestmentAnalysis:
        """Analyze investment tax opportunities."""
        income = tax_return.income

        # Get investment income
        capital_gains = getattr(income, 'capital_gain_income', 0) or 0
        dividends = getattr(income, 'dividend_income', 0) or 0
        qualified_dividends = getattr(income, 'qualified_dividends', 0) or dividends * 0.8

        # Estimate unrealized positions (simplified)
        unrealized_gains = getattr(income, 'unrealized_gains', 0) or 0
        unrealized_losses = getattr(income, 'unrealized_losses', 0) or 0

        # Tax loss harvesting potential
        # Can offset gains plus $3,000 of ordinary income
        loss_potential = min(unrealized_losses, unrealized_gains + 3000)

        # Long-term vs short-term
        lt_gains = getattr(income, 'long_term_gains', capital_gains * 0.7) or 0
        st_gains = getattr(income, 'short_term_gains', capital_gains * 0.3) or 0

        # NIIT exposure (3.8% on investment income over threshold)
        threshold = (self.LIMITS_2025["niit_threshold_mfj"]
                    if filing_status == "married_joint"
                    else self.LIMITS_2025["niit_threshold_single"])
        investment_income = capital_gains + dividends + getattr(income, 'interest_income', 0)
        niit_exposure = max(0, min(investment_income, agi - threshold)) * 0.038

        # Placement recommendations
        recommendations = []
        if qualified_dividends > 0:
            recommendations.append(
                "Hold dividend stocks in taxable accounts (0% LTCG rate possible)"
            )
        if getattr(income, 'interest_income', 0) > 1000:
            recommendations.append(
                "Hold bonds/CDs in tax-advantaged accounts (interest taxed as ordinary)"
            )
        if capital_gains > 10000:
            recommendations.append(
                "Consider tax-managed funds or ETFs to minimize distributions"
            )

        return InvestmentAnalysis(
            unrealized_gains=unrealized_gains,
            unrealized_losses=unrealized_losses,
            tax_loss_harvesting_potential=loss_potential,
            qualified_dividend_amount=qualified_dividends,
            long_term_vs_short_term_gains={"long_term": lt_gains, "short_term": st_gains},
            estimated_niit_exposure=round(niit_exposure, 2),
            tax_efficient_placement_recommendations=recommendations,
        )

    def _retirement_strategies(
        self,
        tax_return: "TaxReturn",
        analysis: RetirementAnalysis,
        marginal_rate: float
    ) -> List[TaxStrategy]:
        """Generate retirement-related strategies."""
        strategies = []

        # 401(k) maximization
        if analysis.additional_contribution_potential > 0:
            additional_401k = analysis.max_401k_contribution - analysis.current_401k_contribution
            if additional_401k > 0:
                savings = additional_401k * (marginal_rate / 100)
                strategies.append(TaxStrategy(
                    title="Maximize 401(k) Contributions",
                    category="retirement",
                    priority="current_year",
                    estimated_savings=savings,
                    description=(
                        f"Increase 401(k) contributions by ${additional_401k:,.0f} to reach "
                        f"the ${analysis.max_401k_contribution:,.0f} limit."
                    ),
                    action_steps=[
                        "Log into employer benefits portal",
                        "Increase contribution percentage",
                        f"Target ${additional_401k / 12:,.0f} additional per month",
                    ],
                    requirements=["401(k) plan access", "Sufficient cash flow"],
                    risks_considerations=["Reduced take-home pay", "Cannot access until 59.5"],
                    deadline="December 31, 2025",
                ))

        # Employer match capture
        if analysis.employer_match_captured < analysis.employer_match_available:
            uncaptured = analysis.employer_match_available - analysis.employer_match_captured
            strategies.append(TaxStrategy(
                title="Capture Full Employer 401(k) Match",
                category="retirement",
                priority="immediate",
                estimated_savings=uncaptured,
                description=(
                    f"You're leaving ${uncaptured:,.0f} of employer match on the table. "
                    "This is free money - a guaranteed 100% return."
                ),
                action_steps=[
                    "Increase 401(k) contribution to at least employer match threshold",
                    "Even if debt exists, prioritize free match money",
                ],
                requirements=["401(k) plan with employer match"],
                risks_considerations=["None - this is free money"],
                deadline="Next payroll date",
            ))

        # IRA contribution
        if analysis.current_ira_contribution < analysis.max_ira_contribution:
            additional_ira = analysis.max_ira_contribution - analysis.current_ira_contribution
            savings = additional_ira * (marginal_rate / 100)
            strategies.append(TaxStrategy(
                title="Contribute to Traditional/Roth IRA",
                category="retirement",
                priority="current_year",
                estimated_savings=savings,
                description=(
                    f"Contribute ${additional_ira:,.0f} to an IRA. "
                    f"{analysis.roth_vs_traditional_recommendation}"
                ),
                action_steps=[
                    "Open IRA if needed (Fidelity, Vanguard, Schwab)",
                    f"Contribute ${additional_ira:,.0f} before April 15, 2026",
                    "Choose Traditional or Roth based on tax situation",
                ],
                requirements=["Earned income", "Under income limits for deductibility"],
                risks_considerations=["Income limits may affect Traditional IRA deductibility"],
                deadline="April 15, 2026 (for 2025 contribution)",
            ))

        # Catch-up contributions
        if analysis.catch_up_eligible and analysis.catch_up_amount > 0:
            strategies.append(TaxStrategy(
                title="Make Age 50+ Catch-Up Contributions",
                category="retirement",
                priority="current_year",
                estimated_savings=analysis.catch_up_amount * (marginal_rate / 100),
                description=(
                    f"As someone 50+, you can contribute an extra ${analysis.catch_up_amount:,.0f} "
                    "annually to retirement accounts."
                ),
                action_steps=[
                    f"Add ${self.LIMITS_2025['401k_catch_up']:,} to 401(k)",
                    f"Add ${self.LIMITS_2025['ira_catch_up']:,} to IRA",
                ],
                requirements=["Age 50 or older by Dec 31"],
                risks_considerations=["May need to adjust budget"],
                deadline="December 31, 2025",
            ))

        return strategies

    def _healthcare_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float,
        marginal_rate: float
    ) -> List[TaxStrategy]:
        """Generate healthcare-related strategies."""
        strategies = []
        income = tax_return.income

        # HSA contribution
        hsa_contribution = getattr(income, 'hsa_contribution', 0) or 0
        has_hdhp = getattr(tax_return, 'has_hdhp', None)

        if has_hdhp is None or has_hdhp:
            # Assume family coverage if married
            is_family = filing_status in ("married_joint", "head_of_household")
            max_hsa = (self.LIMITS_2025["hsa_family"] if is_family
                      else self.LIMITS_2025["hsa_individual"])

            # Add catch-up if 55+
            taxpayer = tax_return.taxpayer
            age = getattr(taxpayer, 'age', 40)
            if age >= 55:
                max_hsa += self.LIMITS_2025["hsa_catch_up"]

            additional_hsa = max(0, max_hsa - hsa_contribution)
            if additional_hsa > 0:
                # HSA has triple tax benefit
                savings = additional_hsa * (marginal_rate / 100)
                strategies.append(TaxStrategy(
                    title="Maximize HSA Contributions",
                    category="healthcare",
                    priority="current_year",
                    estimated_savings=savings,
                    description=(
                        f"HSA offers triple tax benefits: deductible contribution, "
                        f"tax-free growth, tax-free medical withdrawals. "
                        f"Contribute ${additional_hsa:,.0f} more to max out."
                    ),
                    action_steps=[
                        "Verify you have qualifying HDHP coverage",
                        f"Set up automatic contributions totaling ${additional_hsa:,.0f}",
                        "Consider investing HSA funds for long-term growth",
                    ],
                    requirements=["High-deductible health plan (HDHP)"],
                    risks_considerations=[
                        "Must have HDHP all year for full contribution",
                        "20% penalty + tax for non-medical withdrawals before 65",
                    ],
                    deadline="April 15, 2026",
                ))

        # FSA usage reminder
        fsa_balance = getattr(income, 'fsa_balance', 0)
        if fsa_balance and fsa_balance > 500:
            strategies.append(TaxStrategy(
                title="Use FSA Balance Before Year-End",
                category="healthcare",
                priority="immediate",
                estimated_savings=fsa_balance * (marginal_rate / 100),
                description=(
                    f"Use your ${fsa_balance:,.0f} FSA balance before it expires. "
                    "Most FSA funds are use-it-or-lose-it."
                ),
                action_steps=[
                    "Schedule medical/dental appointments",
                    "Stock up on FSA-eligible items (glasses, contacts, first aid)",
                    "Check if employer offers grace period or carryover",
                ],
                requirements=["Active FSA account with balance"],
                risks_considerations=["Forfeit unused funds after deadline"],
                deadline="Check employer's grace period (usually March 15)",
            ))

        # Medical expense timing
        deductions = tax_return.deductions
        medical = getattr(deductions, 'medical_expenses', 0) or 0
        threshold = agi * 0.075

        if medical > 0 and medical < threshold:
            needed = threshold - medical
            strategies.append(TaxStrategy(
                title="Medical Expense Bunching Strategy",
                category="healthcare",
                priority="next_year",
                estimated_savings=medical * (marginal_rate / 100) if medical > threshold else 0,
                description=(
                    f"Medical expenses must exceed ${threshold:,.0f} (7.5% of AGI) to deduct. "
                    f"You're ${needed:,.0f} short. Consider timing elective procedures."
                ),
                action_steps=[
                    "Schedule elective medical procedures in same year",
                    "Purchase needed medical equipment before year-end",
                    "Combine with spouse's medical expenses",
                ],
                requirements=["Must itemize deductions to benefit"],
                risks_considerations=["Don't delay necessary medical care for tax savings"],
                complexity="moderate",
            ))

        return strategies

    def _investment_strategies(
        self,
        tax_return: "TaxReturn",
        analysis: InvestmentAnalysis,
        marginal_rate: float
    ) -> List[TaxStrategy]:
        """Generate investment-related strategies."""
        strategies = []

        # Tax loss harvesting
        if analysis.tax_loss_harvesting_potential > 0:
            savings = min(analysis.tax_loss_harvesting_potential, 3000) * (marginal_rate / 100)
            if analysis.unrealized_gains > 0:
                savings += min(analysis.tax_loss_harvesting_potential - 3000,
                              analysis.unrealized_gains) * 0.15  # LTCG rate

            strategies.append(TaxStrategy(
                title="Tax Loss Harvesting",
                category="investment",
                priority="current_year",
                estimated_savings=savings,
                description=(
                    f"Harvest ${analysis.tax_loss_harvesting_potential:,.0f} in losses to offset "
                    "gains and up to $3,000 of ordinary income."
                ),
                action_steps=[
                    "Identify positions with unrealized losses",
                    "Sell losing positions before Dec 31",
                    "Reinvest in similar (not identical) assets to maintain allocation",
                    "Wait 31 days before repurchasing same security (wash sale rule)",
                ],
                requirements=["Positions with unrealized losses"],
                risks_considerations=[
                    "Wash sale rule: can't buy substantially identical security within 30 days",
                    "May want to hold losers for potential recovery",
                ],
                deadline="December 31, 2025",
                complexity="moderate",
            ))

        # Long-term holding strategy
        st_gains = analysis.long_term_vs_short_term_gains.get("short_term", 0)
        if st_gains > 5000:
            savings = st_gains * (marginal_rate / 100 - 0.15)  # Diff between ordinary and LTCG
            strategies.append(TaxStrategy(
                title="Hold Investments for Long-Term Rates",
                category="investment",
                priority="long_term",
                estimated_savings=savings,
                description=(
                    f"Short-term gains are taxed at {marginal_rate}%. "
                    "Long-term gains (held >1 year) taxed at 0-20%."
                ),
                action_steps=[
                    "Check holding period before selling",
                    "Wait until 1 year + 1 day to qualify for LTCG rates",
                    "Use specific identification to sell older lots first",
                ],
                requirements=["Patience to hold investments"],
                risks_considerations=[
                    "Investment risk of holding longer",
                    "Opportunity cost if market declines",
                ],
            ))

        # Tax-efficient fund placement
        if analysis.tax_efficient_placement_recommendations:
            strategies.append(TaxStrategy(
                title="Tax-Efficient Asset Location",
                category="investment",
                priority="next_year",
                estimated_savings=500,  # Estimated
                description="Place tax-inefficient investments in tax-advantaged accounts.",
                action_steps=analysis.tax_efficient_placement_recommendations,
                requirements=["Both taxable and tax-advantaged accounts"],
                risks_considerations=["Rebalancing complexity increases"],
                complexity="moderate",
            ))

        # NIIT avoidance
        if analysis.estimated_niit_exposure > 500:
            strategies.append(TaxStrategy(
                title="Net Investment Income Tax Planning",
                category="investment",
                priority="current_year",
                estimated_savings=analysis.estimated_niit_exposure,
                description=(
                    f"You're subject to ${analysis.estimated_niit_exposure:,.0f} in NIIT (3.8%). "
                    "Consider strategies to reduce MAGI or investment income."
                ),
                action_steps=[
                    "Maximize pre-tax retirement contributions to lower MAGI",
                    "Defer income recognition where possible",
                    "Consider tax-exempt municipal bonds",
                    "Time capital gains realization strategically",
                ],
                requirements=["High income or investment income"],
                risks_considerations=["May not be feasible depending on income sources"],
                complexity="complex",
                professional_help_recommended=True,
            ))

        return strategies

    def _education_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float
    ) -> List[TaxStrategy]:
        """Generate education-related strategies."""
        strategies = []
        taxpayer = tax_return.taxpayer
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []

        # Check for young children for 529 planning
        young_children = sum(1 for d in dependents if getattr(d, 'age', 99) < 10)

        if young_children > 0:
            strategies.append(TaxStrategy(
                title="Start or Increase 529 Plan Contributions",
                category="education",
                priority="current_year",
                estimated_savings=0,  # State-dependent
                description=(
                    "529 plans offer tax-free growth for education expenses. "
                    "Many states offer tax deductions for contributions."
                ),
                action_steps=[
                    "Open 529 plan if not already have one",
                    f"Check your state's tax deduction for 529 contributions",
                    "Consider superfunding (5 years of gift exclusion at once)",
                    "Set up automatic monthly contributions",
                ],
                requirements=["529 plan account"],
                risks_considerations=[
                    "10% penalty + tax if not used for education",
                    "Can transfer to other family members if needed",
                ],
                complexity="simple",
            ))

        # Student loan interest
        income = tax_return.income
        student_loan_interest = getattr(income, 'student_loan_interest', 0) or 0
        if student_loan_interest == 0:
            # Check if they might have loans
            age = getattr(taxpayer, 'age', 40)
            if 22 <= age <= 40:
                strategies.append(TaxStrategy(
                    title="Claim Student Loan Interest Deduction",
                    category="education",
                    priority="immediate",
                    estimated_savings=2500 * 0.22,  # Max deduction * avg rate
                    description=(
                        "Deduct up to $2,500 in student loan interest as an "
                        "above-the-line deduction (no itemizing required)."
                    ),
                    action_steps=[
                        "Gather Form 1098-E from loan servicers",
                        "Enter interest paid on tax return",
                    ],
                    requirements=[
                        "Student loans for yourself, spouse, or dependent",
                        "MAGI under $100,000 (single/HOH) or $200,000 (MFJ) - phaseout begins at $85,000/$170,000",
                        "Cannot claim if filing status is Married Filing Separately",
                    ],
                    risks_considerations=["Phase-out applies between $85K-$100K (single) or $170K-$200K (MFJ)"],
                ))

        return strategies

    def _charitable_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float,
        marginal_rate: float
    ) -> List[TaxStrategy]:
        """Generate charitable giving strategies."""
        strategies = []
        deductions = tax_return.deductions
        taxpayer = tax_return.taxpayer

        charitable = (
            getattr(deductions, 'charitable_cash', 0) +
            getattr(deductions, 'charitable_noncash', 0)
        ) or 0

        # Donor-Advised Fund bunching
        standard = 31500 if filing_status == "married_joint" else 15750
        if charitable > 0 and charitable < standard * 0.5:
            savings = min(charitable * 2 - standard, charitable) * (marginal_rate / 100)
            strategies.append(TaxStrategy(
                title="Donor-Advised Fund Bunching Strategy",
                category="charitable",
                priority="current_year",
                estimated_savings=savings if savings > 0 else 0,
                description=(
                    "Bunch multiple years of charitable giving into one year "
                    "using a Donor-Advised Fund to exceed standard deduction."
                ),
                action_steps=[
                    "Open DAF at Fidelity Charitable, Schwab Charitable, etc.",
                    "Contribute 2-3 years of typical giving at once",
                    "Take itemized deduction this year, standard next year",
                    "Distribute from DAF to charities over time",
                ],
                requirements=["$5,000+ to open most DAFs"],
                risks_considerations=[
                    "Contributions to DAF are irrevocable",
                    "Must distribute within reasonable time",
                ],
                complexity="moderate",
            ))

        # QCD for 70.5+
        age = getattr(taxpayer, 'age', 50)
        if age >= 70:
            strategies.append(TaxStrategy(
                title="Qualified Charitable Distribution (QCD)",
                category="charitable",
                priority="current_year",
                estimated_savings=min(self.LIMITS_2025["qcd_limit"], 20000) * (marginal_rate / 100),
                description=(
                    f"Donate up to ${self.LIMITS_2025['qcd_limit']:,} directly from IRA to charity. "
                    "Satisfies RMD without increasing taxable income."
                ),
                action_steps=[
                    "Contact IRA custodian to initiate QCD",
                    "Ensure check goes directly to charity (not to you)",
                    "Get acknowledgment letter from charity",
                ],
                requirements=[
                    "Age 70.5 or older",
                    "Traditional IRA (not 401k)",
                    "Direct transfer to qualified charity",
                ],
                risks_considerations=[
                    "Cannot claim charitable deduction for QCD",
                    "Must be completed before year-end",
                ],
                deadline="December 31, 2025",
            ))

        # Appreciated stock donation
        income = tax_return.income
        cap_gains = getattr(income, 'capital_gain_income', 0) or 0
        if cap_gains > 10000 or getattr(income, 'unrealized_gains', 0) > 10000:
            strategies.append(TaxStrategy(
                title="Donate Appreciated Securities",
                category="charitable",
                priority="current_year",
                estimated_savings=5000 * 0.15,  # Avoid 15% LTCG on $5k
                description=(
                    "Donate appreciated stock instead of cash. "
                    "Deduct full market value, avoid capital gains tax."
                ),
                action_steps=[
                    "Identify highly appreciated long-term holdings",
                    "Transfer shares directly to charity or DAF",
                    "Do NOT sell first (that triggers capital gains)",
                    "Get qualified appraisal for donations over $5,000",
                ],
                requirements=[
                    "Appreciated securities held over 1 year",
                    "Charity accepts stock donations",
                ],
                risks_considerations=[
                    "Deduction limited to 30% of AGI for appreciated property",
                    "Excess carries forward 5 years",
                ],
                complexity="moderate",
            ))

        return strategies

    def _timing_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float,
        marginal_rate: float
    ) -> List[TaxStrategy]:
        """Generate income/deduction timing strategies."""
        strategies = []

        # Defer income if high bracket this year
        if marginal_rate >= 32:
            strategies.append(TaxStrategy(
                title="Defer Income to Next Year",
                category="timing",
                priority="current_year",
                estimated_savings=5000 * 0.10,  # Example
                description=(
                    f"At {marginal_rate}% marginal rate, consider deferring income. "
                    "If you expect lower income next year, defer where possible."
                ),
                action_steps=[
                    "Delay year-end bonus to January if employer allows",
                    "Defer self-employment billings until January",
                    "Hold off on exercising stock options",
                    "Delay selling appreciated assets",
                ],
                requirements=["Flexibility to time income"],
                risks_considerations=[
                    "Tax rates could increase next year",
                    "Cash flow needs may override tax planning",
                ],
                deadline="December 31, 2025",
            ))

        # Accelerate deductions if high income year
        if marginal_rate >= 24:
            strategies.append(TaxStrategy(
                title="Accelerate Deductions",
                category="timing",
                priority="current_year",
                estimated_savings=3000 * (marginal_rate / 100),
                description=(
                    "Shift deductible expenses into this higher-income year "
                    "to maximize tax benefit."
                ),
                action_steps=[
                    "Prepay Q1 2026 property taxes before Dec 31 (up to SALT cap)",
                    "Make January mortgage payment in December",
                    "Accelerate charitable giving into this year",
                    "Pay outstanding medical bills before year-end",
                ],
                requirements=["Cash available for prepayments"],
                risks_considerations=[
                    "SALT cap limits property tax prepayment benefit",
                    "Must actually itemize to benefit",
                ],
                deadline="December 31, 2025",
            ))

        return strategies

    def _business_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float,
        marginal_rate: float
    ) -> List[TaxStrategy]:
        """Generate self-employment/business strategies."""
        strategies = []
        income = tax_return.income

        se_income = getattr(income, 'self_employment_income', 0) or 0

        if se_income > 10000:
            # SEP-IRA or Solo 401(k)
            max_sep = min(se_income * 0.25, 69000)  # 2025 limit
            strategies.append(TaxStrategy(
                title="Open SEP-IRA or Solo 401(k)",
                category="business",
                priority="current_year",
                estimated_savings=max_sep * (marginal_rate / 100),
                description=(
                    f"Self-employed individuals can contribute up to ${max_sep:,.0f} "
                    "(25% of net SE income, up to $69,000) to SEP-IRA."
                ),
                action_steps=[
                    "Compare SEP-IRA vs Solo 401(k) based on your situation",
                    "Open account before tax filing deadline",
                    "Contribute before personal tax deadline (April 15 + extensions)",
                ],
                requirements=[
                    "Net self-employment income",
                    "No employees (or limited for Solo 401k)",
                ],
                risks_considerations=[
                    "SEP-IRA deadline is tax filing deadline (with extensions)",
                    "Solo 401(k) must be established by Dec 31",
                ],
                deadline="April 15, 2026 (or October 15 with extension)",
            ))

            # QBI deduction reminder
            strategies.append(TaxStrategy(
                title="Claim Qualified Business Income Deduction",
                category="business",
                priority="immediate",
                estimated_savings=se_income * 0.20 * (marginal_rate / 100),
                description=(
                    "The QBI deduction allows up to 20% deduction on qualified "
                    "business income from pass-through entities."
                ),
                action_steps=[
                    "Calculate QBI deduction on Form 8995 or 8995-A",
                    "Verify your business type qualifies (most do)",
                    "Check income thresholds for service businesses",
                ],
                requirements=[
                    "Pass-through business income",
                    f"SSTB limits apply above ${213500 if filing_status == 'married_joint' else 170050}",
                ],
                risks_considerations=[
                    "Complex rules for high-income service businesses",
                    "Phase-outs and W-2 wage limitations",
                ],
                professional_help_recommended=se_income > 100000,
            ))

            # Home office deduction
            if getattr(income, 'home_office_deduction', 0) == 0:
                strategies.append(TaxStrategy(
                    title="Claim Home Office Deduction",
                    category="business",
                    priority="immediate",
                    estimated_savings=1500 * (marginal_rate / 100),  # Simplified method max
                    description=(
                        "If you have dedicated workspace at home for business, "
                        "you may qualify for the home office deduction."
                    ),
                    action_steps=[
                        "Measure square footage of dedicated office space",
                        "Choose simplified ($5/sq ft, max 300 sq ft) or actual expense method",
                        "Keep records of exclusive business use",
                    ],
                    requirements=[
                        "Regular and exclusive business use",
                        "Principal place of business",
                    ],
                    risks_considerations=[
                        "Audit risk slightly higher with home office",
                        "Must be EXCLUSIVE business use (not dual-purpose)",
                    ],
                ))

        return strategies

    def _family_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float
    ) -> List[TaxStrategy]:
        """Generate family-related tax strategies."""
        strategies = []
        taxpayer = tax_return.taxpayer
        dependents = taxpayer.dependents if hasattr(taxpayer, 'dependents') else []

        # Kiddie tax / family income shifting
        if len(dependents) > 0:
            strategies.append(TaxStrategy(
                title="Gift Appreciated Assets to Children",
                category="family",
                priority="long_term",
                estimated_savings=self.LIMITS_2025["gift_annual_exclusion"] * 0.15,
                description=(
                    f"Gift up to ${self.LIMITS_2025['gift_annual_exclusion']:,} per child "
                    "annually tax-free. Consider appreciated stock for children in lower brackets."
                ),
                action_steps=[
                    "Open custodial account (UTMA/UGMA) for each child",
                    f"Gift up to ${self.LIMITS_2025['gift_annual_exclusion']:,} per person per year",
                    "Consider gifting appreciated stock for 0% LTCG rate",
                ],
                requirements=["Gift tax exclusion limits"],
                risks_considerations=[
                    "Kiddie tax applies to unearned income over $2,500 for under 19 (24 if student)",
                    "Assets become child's at age of majority",
                ],
            ))

        # Dependent care FSA
        young_children = sum(1 for d in dependents if getattr(d, 'age', 99) < 13)
        if young_children > 0:
            strategies.append(TaxStrategy(
                title="Enroll in Dependent Care FSA",
                category="family",
                priority="next_year",
                estimated_savings=5000 * 0.22,  # Pre-tax savings
                description=(
                    "Contribute up to $5,000 pre-tax to dependent care FSA "
                    "for childcare expenses. Reduces taxable income."
                ),
                action_steps=[
                    "Enroll during open enrollment period",
                    "Estimate childcare costs for the year",
                    "Compare to Child Care Tax Credit to choose better option",
                ],
                requirements=[
                    "Both parents must work (or one in school)",
                    "Children under 13",
                ],
                risks_considerations=[
                    "Use-it-or-lose-it (FSA funds)",
                    "Cannot use same expenses for Child Care Credit",
                ],
            ))

        return strategies

    def _state_strategies(
        self,
        tax_return: "TaxReturn",
        filing_status: str,
        agi: float
    ) -> List[TaxStrategy]:
        """Generate state-specific tax strategies."""
        strategies = []

        state = getattr(tax_return.taxpayer, 'state_of_residence', None) or \
                getattr(tax_return, 'state_of_residence', 'CA')

        # State-specific strategies
        high_tax_states = ['CA', 'NY', 'NJ', 'CT', 'HI', 'DC', 'OR', 'MN', 'VT', 'IA']
        no_tax_states = ['TX', 'FL', 'WA', 'NV', 'WY', 'AK', 'SD', 'TN', 'NH']

        if state in high_tax_states:
            strategies.append(TaxStrategy(
                title="State Tax Minimization Strategies",
                category="state_specific",
                priority="long_term",
                estimated_savings=agi * 0.02,  # 2% potential savings
                description=(
                    f"Living in {state} means higher state taxes. "
                    "Consider tax-efficient strategies or relocation if retiring."
                ),
                action_steps=[
                    "Maximize state income tax deductions",
                    "Consider municipal bonds for tax-free income",
                    "If retiring, evaluate relocation to no-tax state",
                    "Check state-specific retirement income exclusions",
                ],
                requirements=["State income tax exposure"],
                risks_considerations=[
                    "SALT cap limits federal deductibility",
                    "Relocation has non-tax costs to consider",
                ],
                complexity="complex",
                professional_help_recommended=True,
            ))

        # SALT workaround for business owners
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 50000 and state not in no_tax_states:
            strategies.append(TaxStrategy(
                title="SALT Cap Workaround (Pass-Through Entity Tax)",
                category="state_specific",
                priority="current_year",
                estimated_savings=min(se_income * 0.05, 5000),
                description=(
                    "Many states offer pass-through entity tax elections "
                    "allowing business owners to circumvent SALT cap."
                ),
                action_steps=[
                    f"Check if {state} offers PTET election",
                    "Work with CPA to evaluate if beneficial",
                    "Make election by state deadline",
                ],
                requirements=[
                    "Pass-through business entity (S-Corp, LLC, Partnership)",
                    "State offers PTET option",
                ],
                risks_considerations=[
                    "Complex calculations required",
                    "May affect estimated payments",
                ],
                complexity="complex",
                professional_help_recommended=True,
            ))

        return strategies

    def _generate_warnings(
        self,
        tax_return: "TaxReturn",
        agi: float,
        marginal_rate: float
    ) -> List[str]:
        """Generate warnings about tax situation."""
        warnings = []

        # High marginal rate warning
        if marginal_rate >= 35:
            warnings.append(
                f"Your {marginal_rate}% marginal rate means aggressive tax planning "
                "is especially valuable. Consider all strategies above."
            )

        # AMT warning
        if agi > self.LIMITS_2025["amt_exemption_single"]:
            warnings.append(
                "Your income level may expose you to Alternative Minimum Tax (AMT). "
                "Consult tax professional about AMT planning strategies."
            )

        # Estimated tax warning
        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 50000 or getattr(income, 'investment_income', 0) > 50000:
            warnings.append(
                "High non-wage income may require quarterly estimated tax payments "
                "to avoid underpayment penalties."
            )

        return warnings

    def _calculate_confidence(
        self,
        tax_return: "TaxReturn",
        strategies: List[TaxStrategy]
    ) -> float:
        """Calculate confidence score for strategy report."""
        # Base confidence
        confidence = 70.0

        # More strategies with savings increases confidence
        savings_strategies = [s for s in strategies if s.estimated_savings > 100]
        confidence += min(len(savings_strategies) * 2, 15)

        # Complete data increases confidence
        if hasattr(tax_return.income, 'retirement_contributions_401k'):
            confidence += 5
        if hasattr(tax_return.deductions, 'charitable_cash'):
            confidence += 5

        return min(100, confidence)
