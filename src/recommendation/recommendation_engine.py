"""Tax Recommendation Engine.

The main orchestrator that combines all analysis modules to provide
comprehensive tax recommendations, optimizations, and strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import json

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.tax_calculator import TaxCalculator

from recommendation.filing_status_optimizer import (
    FilingStatusOptimizer,
    FilingStatusRecommendation,
)
from recommendation.deduction_analyzer import (
    DeductionAnalyzer,
    DeductionRecommendation,
)
from recommendation.credit_optimizer import (
    CreditOptimizer,
    CreditRecommendation,
)
from recommendation.tax_strategy_advisor import (
    TaxStrategyAdvisor,
    TaxStrategyReport,
)
from recommendation.validation import (
    validate_before_surface,
    get_irs_reference,
    RecommendationValidator,
)


@dataclass
class TaxSavingOpportunity:
    """Individual tax saving opportunity."""
    category: str
    title: str
    estimated_savings: float
    priority: str  # immediate, current_year, next_year, long_term
    description: str
    action_required: str
    confidence: float  # 0-100
    irs_reference: str = ""  # Required: IRS form/publication/IRC reference


@dataclass
class ComprehensiveRecommendation:
    """Complete tax recommendation package."""
    # Metadata
    tax_year: int
    generated_at: str
    taxpayer_name: str
    filing_status: str

    # Current situation
    current_federal_tax: float
    current_state_tax: float
    current_total_tax: float
    current_effective_rate: float
    current_marginal_rate: float

    # Optimized situation
    optimized_federal_tax: float
    optimized_state_tax: float
    optimized_total_tax: float
    optimized_effective_rate: float

    # Savings summary
    total_potential_savings: float
    immediate_action_savings: float
    current_year_savings: float
    long_term_annual_savings: float

    # Component recommendations
    filing_status_recommendation: FilingStatusRecommendation
    deduction_recommendation: DeductionRecommendation
    credit_recommendation: CreditRecommendation
    strategy_report: TaxStrategyReport

    # Prioritized action items
    top_opportunities: List[TaxSavingOpportunity]
    all_opportunities: List[TaxSavingOpportunity]

    # Summary and explanations
    executive_summary: str
    detailed_findings: List[str]
    warnings: List[str]
    disclaimers: List[str]

    # Confidence metrics
    overall_confidence: float
    data_completeness: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "generated_at": self.generated_at,
            "taxpayer_name": self.taxpayer_name,
            "filing_status": self.filing_status,
            "current_situation": {
                "federal_tax": self.current_federal_tax,
                "state_tax": self.current_state_tax,
                "total_tax": self.current_total_tax,
                "effective_rate": self.current_effective_rate,
                "marginal_rate": self.current_marginal_rate,
            },
            "optimized_situation": {
                "federal_tax": self.optimized_federal_tax,
                "state_tax": self.optimized_state_tax,
                "total_tax": self.optimized_total_tax,
                "effective_rate": self.optimized_effective_rate,
            },
            "savings_summary": {
                "total_potential": self.total_potential_savings,
                "immediate_action": self.immediate_action_savings,
                "current_year": self.current_year_savings,
                "long_term_annual": self.long_term_annual_savings,
            },
            "top_opportunities": [
                {
                    "category": o.category,
                    "title": o.title,
                    "savings": o.estimated_savings,
                    "priority": o.priority,
                    "description": o.description,
                    "action": o.action_required,
                    "confidence": o.confidence,
                    "irs_reference": o.irs_reference,
                }
                for o in self.top_opportunities
            ],
            "executive_summary": self.executive_summary,
            "warnings": self.warnings,
            "confidence": {
                "overall": self.overall_confidence,
                "data_completeness": self.data_completeness,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class TaxRecommendationEngine:
    """
    Comprehensive tax recommendation engine.

    This engine orchestrates all analysis modules to provide a complete
    picture of tax optimization opportunities, including:
    - Filing status optimization
    - Deduction strategy analysis
    - Credit identification and optimization
    - Tax-saving strategies
    - Multi-year planning recommendations

    The engine produces a prioritized list of actionable recommendations
    with estimated savings and confidence levels.
    """

    def __init__(self, calculator: Optional["TaxCalculator"] = None):
        """Initialize the recommendation engine with optional calculator."""
        self._calculator = calculator
        self._filing_optimizer = FilingStatusOptimizer(calculator)
        self._deduction_analyzer = DeductionAnalyzer(calculator)
        self._credit_optimizer = CreditOptimizer(calculator)
        self._strategy_advisor = TaxStrategyAdvisor(calculator)

    def analyze(self, tax_return: "TaxReturn") -> ComprehensiveRecommendation:
        """
        Perform comprehensive tax analysis and generate recommendations.

        This is the main entry point for the recommendation engine.
        It runs all analysis modules and combines their results into
        a unified, prioritized recommendation package.

        Args:
            tax_return: The tax return to analyze

        Returns:
            ComprehensiveRecommendation with all analysis and recommendations
        """
        # Get current situation
        current_federal = tax_return.tax_liability or 0.0
        current_state = tax_return.state_tax_liability or 0.0
        current_total = current_federal + current_state
        agi = tax_return.adjusted_gross_income or 1.0
        current_effective = (current_total / agi * 100) if agi > 0 else 0.0

        filing_status = tax_return.taxpayer.filing_status.value
        current_marginal = self._get_marginal_rate(filing_status, agi)

        # Run all analyzers
        filing_rec = self._filing_optimizer.analyze(tax_return)
        deduction_rec = self._deduction_analyzer.analyze(tax_return)
        credit_rec = self._credit_optimizer.analyze(tax_return)
        strategy_report = self._strategy_advisor.generate_strategy_report(tax_return)

        # Collect all opportunities
        opportunities = self._collect_opportunities(
            filing_rec, deduction_rec, credit_rec, strategy_report
        )

        # Sort by estimated savings
        opportunities.sort(key=lambda x: x.estimated_savings, reverse=True)
        top_opportunities = opportunities[:10]

        # Calculate total potential savings
        total_savings = sum(o.estimated_savings for o in opportunities)
        immediate_savings = sum(
            o.estimated_savings for o in opportunities if o.priority == "immediate"
        )
        current_year_savings = sum(
            o.estimated_savings for o in opportunities
            if o.priority in ("immediate", "current_year")
        )
        long_term_savings = sum(
            o.estimated_savings for o in opportunities if o.priority == "long_term"
        )

        # Calculate optimized situation
        optimized_federal = max(0, current_federal - filing_rec.potential_savings)
        optimized_state = current_state  # State optimization varies
        optimized_total = optimized_federal + optimized_state
        optimized_effective = (optimized_total / agi * 100) if agi > 0 else 0.0

        # Generate executive summary
        summary = self._generate_executive_summary(
            tax_return, total_savings, top_opportunities
        )

        # Generate detailed findings
        findings = self._generate_detailed_findings(
            filing_rec, deduction_rec, credit_rec, strategy_report
        )

        # Collect all warnings
        warnings = self._collect_warnings(
            filing_rec, deduction_rec, credit_rec, strategy_report
        )

        # Calculate confidence
        overall_confidence = self._calculate_overall_confidence(
            filing_rec, deduction_rec, credit_rec, strategy_report
        )
        data_completeness = self._calculate_data_completeness(tax_return)

        # Get taxpayer name
        taxpayer_name = getattr(tax_return.taxpayer, 'name', 'Taxpayer')
        if not taxpayer_name:
            first = getattr(tax_return.taxpayer, 'first_name', '')
            last = getattr(tax_return.taxpayer, 'last_name', '')
            taxpayer_name = f"{first} {last}".strip() or "Taxpayer"

        return ComprehensiveRecommendation(
            tax_year=2025,
            generated_at=datetime.now().isoformat(),
            taxpayer_name=taxpayer_name,
            filing_status=filing_status,
            current_federal_tax=round(current_federal, 2),
            current_state_tax=round(current_state, 2),
            current_total_tax=round(current_total, 2),
            current_effective_rate=round(current_effective, 2),
            current_marginal_rate=current_marginal,
            optimized_federal_tax=round(optimized_federal, 2),
            optimized_state_tax=round(optimized_state, 2),
            optimized_total_tax=round(optimized_total, 2),
            optimized_effective_rate=round(optimized_effective, 2),
            total_potential_savings=round(total_savings, 2),
            immediate_action_savings=round(immediate_savings, 2),
            current_year_savings=round(current_year_savings, 2),
            long_term_annual_savings=round(long_term_savings, 2),
            filing_status_recommendation=filing_rec,
            deduction_recommendation=deduction_rec,
            credit_recommendation=credit_rec,
            strategy_report=strategy_report,
            top_opportunities=top_opportunities,
            all_opportunities=opportunities,
            executive_summary=summary,
            detailed_findings=findings,
            warnings=warnings,
            disclaimers=self._get_disclaimers(),
            overall_confidence=round(overall_confidence, 1),
            data_completeness=round(data_completeness, 1),
        )

    def get_quick_analysis(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """
        Get a quick analysis summary without full detailed report.

        Useful for displaying summary cards or quick overviews.

        Args:
            tax_return: The tax return to analyze

        Returns:
            Dictionary with key metrics and top recommendations
        """
        filing_rec = self._filing_optimizer.analyze(tax_return)
        credit_rec = self._credit_optimizer.analyze(tax_return)

        return {
            "filing_status": {
                "current": filing_rec.current_status,
                "recommended": filing_rec.recommended_status,
                "potential_savings": filing_rec.potential_savings,
            },
            "credits": {
                "total_claimed": credit_rec.total_credit_benefit,
                "refundable": credit_rec.analysis.refundable_applied,
                "eligible_count": len(credit_rec.analysis.eligible_credits),
            },
            "quick_wins": credit_rec.immediate_actions[:3],
            "confidence": filing_rec.confidence_score,
        }

    def compare_scenarios(
        self,
        tax_return: "TaxReturn",
        scenarios: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple tax scenarios (what-if analysis).

        Args:
            tax_return: Base tax return
            scenarios: List of scenario modifications

        Returns:
            List of scenario results for comparison
        """
        from copy import deepcopy

        results = []

        # Baseline
        baseline = self.analyze(tax_return)
        results.append({
            "name": "Current Situation",
            "total_tax": baseline.current_total_tax,
            "effective_rate": baseline.current_effective_rate,
            "refund_or_owed": tax_return.refund_or_owed or 0,
        })

        # Each scenario
        for scenario in scenarios:
            test_return = deepcopy(tax_return)

            # Apply scenario modifications
            if "filing_status" in scenario:
                from models.taxpayer import FilingStatus
                status_map = {
                    "single": FilingStatus.SINGLE,
                    "married_joint": FilingStatus.MARRIED_JOINT,
                    "married_separate": FilingStatus.MARRIED_SEPARATE,
                    "head_of_household": FilingStatus.HEAD_OF_HOUSEHOLD,
                    "qualifying_widow": FilingStatus.QUALIFYING_WIDOW,
                }
                if scenario["filing_status"] in status_map:
                    test_return.taxpayer.filing_status = status_map[scenario["filing_status"]]

            if "additional_401k" in scenario:
                current = getattr(test_return.income, 'retirement_contributions_401k', 0) or 0
                test_return.income.retirement_contributions_401k = current + scenario["additional_401k"]

            if "additional_charitable" in scenario:
                current = getattr(test_return.deductions, 'charitable_cash', 0) or 0
                test_return.deductions.charitable_cash = current + scenario["additional_charitable"]

            # Recalculate
            if self._calculator:
                test_return = self._calculator.calculate_complete_return(test_return)

            analysis = self.analyze(test_return)

            results.append({
                "name": scenario.get("name", "Scenario"),
                "total_tax": analysis.current_total_tax,
                "effective_rate": analysis.current_effective_rate,
                "refund_or_owed": test_return.refund_or_owed or 0,
                "savings_vs_baseline": baseline.current_total_tax - analysis.current_total_tax,
            })

        return results

    def _get_marginal_rate(self, filing_status: str, agi: float) -> float:
        """Get marginal tax rate."""
        brackets = {
            "single": [
                (11925, 10), (48475, 12), (103350, 22),
                (197300, 24), (250525, 32), (626350, 35), (float('inf'), 37)
            ],
            "married_joint": [
                (23850, 10), (96950, 12), (206700, 22),
                (394600, 24), (501050, 32), (751600, 35), (float('inf'), 37)
            ],
            "married_filing_jointly": [
                (23850, 10), (96950, 12), (206700, 22),
                (394600, 24), (501050, 32), (751600, 35), (float('inf'), 37)
            ],
            "married_separate": [
                (11925, 10), (48475, 12), (103350, 22),
                (197300, 24), (250525, 32), (375800, 35), (float('inf'), 37)
            ],
            "head_of_household": [
                (17000, 10), (64850, 12), (103350, 22),
                (197300, 24), (250500, 32), (626350, 35), (float('inf'), 37)
            ],
        }

        status_brackets = brackets.get(filing_status, brackets["single"])
        for threshold, rate in status_brackets:
            if agi <= threshold:
                return float(rate)
        return 37.0

    def _collect_opportunities(
        self,
        filing_rec: FilingStatusRecommendation,
        deduction_rec: DeductionRecommendation,
        credit_rec: CreditRecommendation,
        strategy_report: TaxStrategyReport,
    ) -> List[TaxSavingOpportunity]:
        """
        Collect all tax saving opportunities from all analyzers.

        Each opportunity must have all required fields:
        - description (reason)
        - estimated_savings (impact)
        - confidence
        - irs_reference

        Opportunities missing required fields are filtered out.
        """
        opportunities = []

        # Filing status opportunity
        if filing_rec.potential_savings > 0:
            opportunities.append(TaxSavingOpportunity(
                category="filing_status",
                title=f"Change Filing Status to {filing_rec.recommended_status}",
                estimated_savings=filing_rec.potential_savings,
                priority="immediate",
                description=filing_rec.recommendation_reason,
                action_required=f"File as {filing_rec.recommended_status}",
                confidence=filing_rec.confidence_score,
                irs_reference="IRC Section 2; Publication 501",
            ))

        # Deduction opportunity
        if deduction_rec.analysis.deduction_difference > 0:
            opportunities.append(TaxSavingOpportunity(
                category="deductions",
                title=f"Switch to {deduction_rec.recommended_strategy.title()} Deduction",
                estimated_savings=deduction_rec.analysis.tax_savings_estimate,
                priority="immediate",
                description=deduction_rec.explanation,
                action_required=f"Use {deduction_rec.recommended_strategy} deduction",
                confidence=deduction_rec.confidence_score,
                irs_reference="IRC Section 63; Schedule A; Publication 17",
            ))

        # Bunching strategy
        if deduction_rec.bunching_strategy and deduction_rec.bunching_strategy.get("is_beneficial"):
            opportunities.append(TaxSavingOpportunity(
                category="deductions",
                title="Implement Deduction Bunching Strategy",
                estimated_savings=deduction_rec.bunching_strategy["two_year_savings"] / 2,
                priority="current_year",
                description=deduction_rec.bunching_strategy["explanation"],
                action_required="Bunch charitable donations and property taxes",
                confidence=75.0,
                irs_reference="IRC Section 170; Schedule A; Publication 526",
            ))

        # Credit opportunities
        for credit in credit_rec.analysis.eligible_credits.values():
            if credit.actual_amount > 0:
                # Get appropriate IRS reference for this credit type
                irs_ref = self._get_credit_irs_reference(credit.credit_code)
                opportunities.append(TaxSavingOpportunity(
                    category="credits",
                    title=f"Claim {credit.credit_name}",
                    estimated_savings=credit.actual_amount,
                    priority="immediate",
                    description=credit.eligibility_reason,
                    action_required="Claim credit on tax return",
                    confidence=90.0,
                    irs_reference=irs_ref,
                ))

        # Unclaimed credit opportunities - only add if we have enough info
        for action in credit_rec.immediate_actions:
            if action and len(action) > 10:  # Require meaningful description
                opportunities.append(TaxSavingOpportunity(
                    category="credits",
                    title="Potential Credit Available",
                    estimated_savings=500,  # Estimate
                    priority="immediate",
                    description=action,
                    action_required=action,
                    confidence=60.0,
                    irs_reference="Publication 17; Form 1040 Instructions",
                ))

        # Strategy opportunities
        for strategy in strategy_report.immediate_strategies:
            irs_ref = self._get_strategy_irs_reference(strategy.category)
            opportunities.append(TaxSavingOpportunity(
                category=strategy.category,
                title=strategy.title,
                estimated_savings=strategy.estimated_savings,
                priority="immediate",
                description=strategy.description,
                action_required=strategy.action_steps[0] if strategy.action_steps else strategy.title,
                confidence=80.0,
                irs_reference=irs_ref,
            ))

        for strategy in strategy_report.current_year_strategies:
            irs_ref = self._get_strategy_irs_reference(strategy.category)
            opportunities.append(TaxSavingOpportunity(
                category=strategy.category,
                title=strategy.title,
                estimated_savings=strategy.estimated_savings,
                priority="current_year",
                description=strategy.description,
                action_required=strategy.action_steps[0] if strategy.action_steps else strategy.title,
                confidence=75.0,
                irs_reference=irs_ref,
            ))

        for strategy in strategy_report.next_year_strategies:
            irs_ref = self._get_strategy_irs_reference(strategy.category)
            opportunities.append(TaxSavingOpportunity(
                category=strategy.category,
                title=strategy.title,
                estimated_savings=strategy.estimated_savings,
                priority="next_year",
                description=strategy.description,
                action_required=strategy.action_steps[0] if strategy.action_steps else strategy.title,
                confidence=70.0,
                irs_reference=irs_ref,
            ))

        for strategy in strategy_report.long_term_strategies:
            irs_ref = self._get_strategy_irs_reference(strategy.category)
            opportunities.append(TaxSavingOpportunity(
                category=strategy.category,
                title=strategy.title,
                estimated_savings=strategy.estimated_savings,
                priority="long_term",
                description=strategy.description,
                action_required=strategy.action_steps[0] if strategy.action_steps else strategy.title,
                confidence=65.0,
                irs_reference=irs_ref,
            ))

        # Validate and filter - only return opportunities with all required fields
        valid_opportunities = self._validate_opportunities(opportunities)

        return valid_opportunities

    def _get_credit_irs_reference(self, credit_code: str) -> str:
        """Get IRS reference for a specific credit."""
        credit_refs = {
            "child_tax_credit": "IRC Section 24; Schedule 8812",
            "eitc": "IRC Section 32; Schedule EIC; Publication 596",
            "education_credit": "IRC Section 25A; Form 8863; Publication 970",
            "aotc": "IRC Section 25A(b); Form 8863",
            "llc": "IRC Section 25A(c); Form 8863",
            "child_care": "IRC Section 21; Form 2441; Publication 503",
            "saver": "IRC Section 25B; Form 8880",
            "adoption": "IRC Section 23; Form 8839",
            "foreign_tax": "IRC Section 901; Form 1116",
            "residential_energy": "IRC Section 25C; Form 5695",
            "ev_credit": "IRC Section 30D; Form 8936",
            "premium_tax_credit": "IRC Section 36B; Form 8962",
        }
        return credit_refs.get(credit_code, "Publication 17; Form 1040")

    def _get_strategy_irs_reference(self, category: str) -> str:
        """Get IRS reference for a strategy category."""
        category_refs = {
            "retirement": "IRC Section 401(k); IRC Section 408; Publication 590-A",
            "healthcare": "IRC Section 223; Form 8889; Publication 969",
            "investment": "IRC Section 1; Schedule D; Publication 550",
            "education": "IRC Section 25A; Publication 970",
            "charitable": "IRC Section 170; Schedule A; Publication 526",
            "real_estate": "IRC Section 163(h); Schedule A; Publication 936",
            "business": "IRC Section 199A; Form 8995; Publication 535",
            "timing": "IRC Section 451; Publication 538",
            "state_specific": "State tax code varies by jurisdiction",
            "family": "IRC Section 152; Publication 501",
        }
        return category_refs.get(category, "Publication 17; Form 1040")

    def _validate_opportunities(
        self,
        opportunities: List[TaxSavingOpportunity]
    ) -> List[TaxSavingOpportunity]:
        """
        Validate opportunities and filter out those missing required fields.

        Rule: If any required field is missing, recommendation must not surface.
        """
        validator = RecommendationValidator(strict_mode=True)
        valid_opportunities = []

        for opp in opportunities:
            opp_dict = {
                "category": opp.category,
                "title": opp.title,
                "estimated_savings": opp.estimated_savings,
                "priority": opp.priority,
                "description": opp.description,
                "action_required": opp.action_required,
                "confidence": opp.confidence,
                "irs_reference": opp.irs_reference,
            }

            result = validator.validate(opp_dict, "TaxSavingOpportunity")

            if result.is_valid:
                valid_opportunities.append(opp)
            else:
                # Log but don't surface
                import logging
                logging.getLogger(__name__).warning(
                    f"Filtering recommendation '{opp.title}': missing {result.missing_fields}"
                )

        return valid_opportunities

    def _generate_executive_summary(
        self,
        tax_return: "TaxReturn",
        total_savings: float,
        top_opportunities: List[TaxSavingOpportunity]
    ) -> str:
        """Generate executive summary of recommendations."""
        agi = tax_return.adjusted_gross_income or 0
        tax = tax_return.tax_liability or 0
        filing_status = tax_return.taxpayer.filing_status.value

        summary_parts = []

        # Opening
        summary_parts.append(
            f"Based on your {filing_status.replace('_', ' ')} filing status "
            f"with ${agi:,.0f} in adjusted gross income and ${tax:,.0f} in "
            f"federal tax liability, we've identified several optimization opportunities."
        )

        # Total savings
        if total_savings > 0:
            summary_parts.append(
                f"Total potential tax savings identified: ${total_savings:,.0f}."
            )

        # Top opportunities
        if top_opportunities:
            top_titles = [o.title for o in top_opportunities[:3]]
            summary_parts.append(
                f"Top recommendations: {', '.join(top_titles)}."
            )

        # Immediate actions
        immediate = [o for o in top_opportunities if o.priority == "immediate"]
        if immediate:
            immediate_savings = sum(o.estimated_savings for o in immediate)
            summary_parts.append(
                f"Immediate actions can save approximately ${immediate_savings:,.0f}."
            )

        return " ".join(summary_parts)

    def _generate_detailed_findings(
        self,
        filing_rec: FilingStatusRecommendation,
        deduction_rec: DeductionRecommendation,
        credit_rec: CreditRecommendation,
        strategy_report: TaxStrategyReport,
    ) -> List[str]:
        """Generate detailed findings from all analyses."""
        findings = []

        # Filing status finding
        if filing_rec.recommended_status != filing_rec.current_status:
            findings.append(
                f"FILING STATUS: Changing from {filing_rec.current_status} to "
                f"{filing_rec.recommended_status} could save ${filing_rec.potential_savings:,.0f}."
            )
        else:
            findings.append(
                f"FILING STATUS: Your current status ({filing_rec.current_status}) is optimal."
            )

        # Deduction finding
        analysis = deduction_rec.analysis
        findings.append(
            f"DEDUCTIONS: {deduction_rec.recommended_strategy.title()} deduction "
            f"(${analysis.total_standard_deduction:,.0f} vs ${analysis.total_itemized_deductions:,.0f} itemized) "
            f"provides better benefit. Difference: ${abs(analysis.deduction_difference):,.0f}."
        )

        # Credit findings
        eligible_count = len(credit_rec.analysis.eligible_credits)
        total_credits = credit_rec.total_credit_benefit
        findings.append(
            f"CREDITS: You qualify for {eligible_count} tax credits totaling "
            f"${total_credits:,.0f}. Refundable portion: ${credit_rec.analysis.refundable_applied:,.0f}."
        )

        # Unused nonrefundable warning
        if credit_rec.analysis.unused_nonrefundable > 0:
            findings.append(
                f"NOTE: ${credit_rec.analysis.unused_nonrefundable:,.0f} in nonrefundable "
                f"credits cannot be used (exceeds tax liability)."
            )

        # Retirement finding
        retirement = strategy_report.retirement_analysis
        if retirement.additional_contribution_potential > 0:
            findings.append(
                f"RETIREMENT: You can contribute ${retirement.additional_contribution_potential:,.0f} more "
                f"to retirement accounts, saving approximately ${retirement.tax_savings_if_maxed:,.0f} in taxes."
            )

        return findings

    def _collect_warnings(
        self,
        filing_rec: FilingStatusRecommendation,
        deduction_rec: DeductionRecommendation,
        credit_rec: CreditRecommendation,
        strategy_report: TaxStrategyReport,
    ) -> List[str]:
        """Collect all warnings from analyzers."""
        warnings = []

        warnings.extend(filing_rec.warnings)
        warnings.extend(deduction_rec.analysis.warnings)
        warnings.extend(credit_rec.warnings)
        warnings.extend(strategy_report.warnings)

        return sorted(set(warnings))  # Remove duplicates, deterministic order

    def _calculate_overall_confidence(
        self,
        filing_rec: FilingStatusRecommendation,
        deduction_rec: DeductionRecommendation,
        credit_rec: CreditRecommendation,
        strategy_report: TaxStrategyReport,
    ) -> float:
        """Calculate overall confidence score."""
        scores = [
            filing_rec.confidence_score,
            deduction_rec.confidence_score,
            credit_rec.confidence_score,
            strategy_report.confidence_score,
        ]
        return sum(scores) / len(scores)

    def _calculate_data_completeness(self, tax_return: "TaxReturn") -> float:
        """Calculate how complete the tax return data is."""
        completeness = 50.0  # Base

        # Check key fields
        if tax_return.adjusted_gross_income:
            completeness += 10
        if tax_return.tax_liability:
            completeness += 10

        income = tax_return.income
        if hasattr(income, 'get_total_wages') and income.get_total_wages() > 0:
            completeness += 5
        if hasattr(income, 'retirement_contributions_401k'):
            completeness += 5
        if hasattr(income, 'self_employment_income'):
            completeness += 5

        deductions = tax_return.deductions
        if hasattr(deductions, 'mortgage_interest'):
            completeness += 5
        if hasattr(deductions, 'charitable_cash'):
            completeness += 5
        if hasattr(deductions, 'property_taxes'):
            completeness += 5

        return min(100.0, completeness)

    def _get_disclaimers(self) -> List[str]:
        """Get standard disclaimers."""
        return [
            "This analysis is for informational purposes only and does not constitute tax advice.",
            "Consult a qualified tax professional before making tax decisions.",
            "Tax laws change frequently; verify current rules with IRS.gov or your tax advisor.",
            "Savings estimates are approximate and depend on your specific circumstances.",
            "This analysis is based on federal tax law; state tax implications may vary.",
        ]

    def generate_report_markdown(self, recommendation: ComprehensiveRecommendation) -> str:
        """
        Generate a formatted markdown report from the recommendation.

        Args:
            recommendation: The comprehensive recommendation to format

        Returns:
            Markdown-formatted report string
        """
        lines = []

        # Header
        lines.append(f"# Tax Optimization Report - Tax Year {recommendation.tax_year}")
        lines.append(f"**Generated:** {recommendation.generated_at}")
        lines.append(f"**Taxpayer:** {recommendation.taxpayer_name}")
        lines.append(f"**Filing Status:** {recommendation.filing_status.replace('_', ' ').title()}")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append(recommendation.executive_summary)
        lines.append("")

        # Current vs Optimized
        lines.append("## Tax Comparison")
        lines.append("| Metric | Current | Optimized | Savings |")
        lines.append("|--------|---------|-----------|---------|")
        lines.append(
            f"| Federal Tax | ${recommendation.current_federal_tax:,.2f} | "
            f"${recommendation.optimized_federal_tax:,.2f} | "
            f"${recommendation.current_federal_tax - recommendation.optimized_federal_tax:,.2f} |"
        )
        lines.append(
            f"| State Tax | ${recommendation.current_state_tax:,.2f} | "
            f"${recommendation.optimized_state_tax:,.2f} | - |"
        )
        lines.append(
            f"| Total Tax | ${recommendation.current_total_tax:,.2f} | "
            f"${recommendation.optimized_total_tax:,.2f} | "
            f"${recommendation.current_total_tax - recommendation.optimized_total_tax:,.2f} |"
        )
        lines.append(
            f"| Effective Rate | {recommendation.current_effective_rate:.1f}% | "
            f"{recommendation.optimized_effective_rate:.1f}% | "
            f"{recommendation.current_effective_rate - recommendation.optimized_effective_rate:.1f}% |"
        )
        lines.append("")

        # Savings Summary
        lines.append("## Potential Savings Summary")
        lines.append(f"- **Total Potential Savings:** ${recommendation.total_potential_savings:,.2f}")
        lines.append(f"- **Immediate Action Savings:** ${recommendation.immediate_action_savings:,.2f}")
        lines.append(f"- **Current Year Savings:** ${recommendation.current_year_savings:,.2f}")
        lines.append(f"- **Long-Term Annual Savings:** ${recommendation.long_term_annual_savings:,.2f}")
        lines.append("")

        # Top Opportunities
        lines.append("## Top 10 Tax Saving Opportunities")
        for i, opp in enumerate(recommendation.top_opportunities, 1):
            lines.append(f"### {i}. {opp.title}")
            lines.append(f"- **Category:** {opp.category.replace('_', ' ').title()}")
            lines.append(f"- **Estimated Savings:** ${opp.estimated_savings:,.2f}")
            lines.append(f"- **Priority:** {opp.priority.replace('_', ' ').title()}")
            lines.append(f"- **Description:** {opp.description}")
            lines.append(f"- **Action Required:** {opp.action_required}")
            lines.append(f"- **Confidence:** {opp.confidence:.0f}%")
            lines.append("")

        # Detailed Findings
        lines.append("## Detailed Findings")
        for finding in recommendation.detailed_findings:
            lines.append(f"- {finding}")
        lines.append("")

        # Warnings
        if recommendation.warnings:
            lines.append("## Warnings")
            for warning in recommendation.warnings:
                lines.append(f"- ⚠️ {warning}")
            lines.append("")

        # Confidence Metrics
        lines.append("## Analysis Confidence")
        lines.append(f"- **Overall Confidence:** {recommendation.overall_confidence:.1f}%")
        lines.append(f"- **Data Completeness:** {recommendation.data_completeness:.1f}%")
        lines.append("")

        # Disclaimers
        lines.append("## Disclaimers")
        for disclaimer in recommendation.disclaimers:
            lines.append(f"- {disclaimer}")
        lines.append("")

        return "\n".join(lines)

    def generate_report_html(self, recommendation: ComprehensiveRecommendation) -> str:
        """
        Generate an HTML report from the recommendation.

        Args:
            recommendation: The comprehensive recommendation to format

        Returns:
            HTML-formatted report string
        """
        markdown = self.generate_report_markdown(recommendation)

        # Basic markdown to HTML conversion
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Tax Optimization Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #4CAF50; color: white; }",
            "h1 { color: #2E7D32; }",
            "h2 { color: #388E3C; border-bottom: 2px solid #4CAF50; padding-bottom: 5px; }",
            "h3 { color: #43A047; }",
            ".warning { color: #F57C00; }",
            ".savings { color: #2E7D32; font-weight: bold; }",
            "</style>",
            "</head>",
            "<body>",
        ]

        # Simple conversion (in production, use a proper markdown library)
        for line in markdown.split("\n"):
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("- "):
                html_lines.append(f"<li>{line[2:]}</li>")
            elif line.startswith("|"):
                # Table handling would go here
                pass
            elif line.startswith("**"):
                html_lines.append(f"<p><strong>{line}</strong></p>")
            elif line:
                html_lines.append(f"<p>{line}</p>")

        html_lines.extend(["</body>", "</html>"])

        return "\n".join(html_lines)
