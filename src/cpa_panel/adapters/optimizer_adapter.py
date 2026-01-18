"""
Optimizer Adapter for CPA Panel

Bridges all tax optimization modules to the CPA panel, providing
unified access to credit, deduction, filing status, entity, and
strategy analysis capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import logging

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Generic optimization result wrapper."""
    success: bool
    session_id: str
    analysis_type: str
    timestamp: str
    data: Dict[str, Any]
    summary: str
    total_potential_savings: float
    confidence: float
    warnings: List[str]
    recommendations: List[str]


class OptimizerAdapter:
    """
    Unified adapter for all tax optimization modules.

    Provides CPA panel access to:
    - Credit Optimizer: Identifies all eligible tax credits
    - Deduction Analyzer: Standard vs itemized analysis
    - Filing Status Optimizer: Compares filing status options
    - Entity Optimizer: Business structure comparison
    - Tax Strategy Advisor: Comprehensive strategy analysis
    """

    def __init__(self):
        """Initialize optimizer instances lazily."""
        self._credit_optimizer = None
        self._deduction_analyzer = None
        self._filing_status_optimizer = None
        self._entity_optimizer = None
        self._tax_strategy_advisor = None

    @property
    def credit_optimizer(self):
        """Lazy load credit optimizer."""
        if self._credit_optimizer is None:
            from recommendation.credit_optimizer import CreditOptimizer
            self._credit_optimizer = CreditOptimizer()
        return self._credit_optimizer

    @property
    def deduction_analyzer(self):
        """Lazy load deduction analyzer."""
        if self._deduction_analyzer is None:
            from recommendation.deduction_analyzer import DeductionAnalyzer
            self._deduction_analyzer = DeductionAnalyzer()
        return self._deduction_analyzer

    @property
    def filing_status_optimizer(self):
        """Lazy load filing status optimizer."""
        if self._filing_status_optimizer is None:
            from recommendation.filing_status_optimizer import FilingStatusOptimizer
            self._filing_status_optimizer = FilingStatusOptimizer()
        return self._filing_status_optimizer

    @property
    def entity_optimizer(self):
        """Lazy load entity optimizer."""
        if self._entity_optimizer is None:
            from recommendation.entity_optimizer import EntityStructureOptimizer
            self._entity_optimizer = EntityStructureOptimizer()
        return self._entity_optimizer

    @property
    def tax_strategy_advisor(self):
        """Lazy load tax strategy advisor."""
        if self._tax_strategy_advisor is None:
            from recommendation.tax_strategy_advisor import TaxStrategyAdvisor
            self._tax_strategy_advisor = TaxStrategyAdvisor()
        return self._tax_strategy_advisor

    def get_tax_return(self, session_id: str) -> Optional["TaxReturn"]:
        """
        Get tax return from session in optimizer-compatible format.

        This method returns a TaxReturn object (or wrapped DatabaseTaxReturn)
        that can be used with the optimizer modules.
        """
        try:
            from cpa_panel.adapters import TaxReturnAdapter
            adapter = TaxReturnAdapter()
            # Use the optimizer-compatible method that wraps DatabaseTaxReturn
            return adapter.get_optimizer_compatible_return(session_id)
        except Exception as e:
            logger.error(f"Failed to get tax return for {session_id}: {e}")
            return None

    def get_credit_analysis(self, session_id: str) -> OptimizationResult:
        """
        Analyze all potential tax credits for a client.

        Returns comprehensive credit eligibility analysis including:
        - Eligible credits with amounts
        - Ineligible credits with reasons
        - Near-miss credits (close to qualifying)
        - Action items to maximize credits
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return self._error_result(session_id, "credit_analysis", "Tax return not found")

        try:
            recommendation = self.credit_optimizer.analyze(tax_return)

            # Convert credit eligibilities to serializable format
            eligible_credits = {
                code: self._credit_to_dict(credit)
                for code, credit in recommendation.analysis.eligible_credits.items()
            }

            ineligible_credits = {
                code: self._credit_to_dict(credit)
                for code, credit in recommendation.analysis.ineligible_credits.items()
            }

            return OptimizationResult(
                success=True,
                session_id=session_id,
                analysis_type="credit_analysis",
                timestamp=datetime.utcnow().isoformat(),
                data={
                    "filing_status": recommendation.analysis.filing_status,
                    "adjusted_gross_income": recommendation.analysis.adjusted_gross_income,
                    "tax_liability_before_credits": recommendation.analysis.tax_liability_before_credits,
                    "eligible_credits": eligible_credits,
                    "ineligible_credits": ineligible_credits,
                    "total_refundable_credits": recommendation.analysis.total_refundable_credits,
                    "total_nonrefundable_credits": recommendation.analysis.total_nonrefundable_credits,
                    "total_credits_claimed": recommendation.analysis.total_credits_claimed,
                    "nonrefundable_applied": recommendation.analysis.nonrefundable_applied,
                    "refundable_applied": recommendation.analysis.refundable_applied,
                    "unused_nonrefundable": recommendation.analysis.unused_nonrefundable,
                    "unclaimed_potential": recommendation.analysis.unclaimed_potential,
                    "near_miss_credits": recommendation.analysis.near_miss_credits,
                },
                summary=recommendation.summary,
                total_potential_savings=recommendation.total_credit_benefit,
                confidence=recommendation.confidence_score,
                warnings=recommendation.warnings,
                recommendations=recommendation.immediate_actions + recommendation.year_round_planning,
            )

        except Exception as e:
            logger.error(f"Credit analysis failed for {session_id}: {e}")
            return self._error_result(session_id, "credit_analysis", str(e))

    def get_deduction_analysis(self, session_id: str) -> OptimizationResult:
        """
        Analyze standard vs itemized deduction strategy.

        Returns comprehensive deduction analysis including:
        - Standard deduction amount
        - Itemized deduction breakdown
        - Recommended strategy
        - Bunching strategy viability
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return self._error_result(session_id, "deduction_analysis", "Tax return not found")

        try:
            recommendation = self.deduction_analyzer.analyze(tax_return)
            analysis = recommendation.analysis

            # Convert itemized breakdown to dict
            itemized_data = {
                "medical_expenses_total": analysis.itemized_breakdown.medical_expenses_total,
                "medical_deduction_allowed": analysis.itemized_breakdown.medical_deduction_allowed,
                "salt_total": analysis.itemized_breakdown.salt_total,
                "salt_deduction_allowed": analysis.itemized_breakdown.salt_deduction_allowed,
                "mortgage_interest": analysis.itemized_breakdown.mortgage_interest,
                "total_interest_deduction": analysis.itemized_breakdown.total_interest_deduction,
                "charitable_deduction_allowed": analysis.itemized_breakdown.charitable_deduction_allowed,
                "total_itemized_deductions": analysis.itemized_breakdown.total_itemized_deductions,
            }

            return OptimizationResult(
                success=True,
                session_id=session_id,
                analysis_type="deduction_analysis",
                timestamp=datetime.utcnow().isoformat(),
                data={
                    "filing_status": analysis.filing_status,
                    "adjusted_gross_income": analysis.adjusted_gross_income,
                    "standard_deduction_base": analysis.standard_deduction_base,
                    "additional_standard_deduction": analysis.additional_standard_deduction,
                    "total_standard_deduction": analysis.total_standard_deduction,
                    "itemized_breakdown": itemized_data,
                    "total_itemized_deductions": analysis.total_itemized_deductions,
                    "recommended_strategy": analysis.recommended_strategy,
                    "deduction_difference": analysis.deduction_difference,
                    "tax_savings_estimate": analysis.tax_savings_estimate,
                    "marginal_rate": analysis.marginal_rate,
                    "itemized_categories": analysis.itemized_categories,
                    "bunching_strategy": recommendation.bunching_strategy,
                },
                summary=recommendation.explanation,
                total_potential_savings=abs(analysis.deduction_difference) * (analysis.marginal_rate / 100),
                confidence=recommendation.confidence_score,
                warnings=analysis.warnings,
                recommendations=recommendation.current_year_actions + recommendation.next_year_planning,
            )

        except Exception as e:
            logger.error(f"Deduction analysis failed for {session_id}: {e}")
            return self._error_result(session_id, "deduction_analysis", str(e))

    def get_filing_status_comparison(self, session_id: str) -> OptimizationResult:
        """
        Compare tax implications of all eligible filing statuses.

        Returns filing status analysis including:
        - Tax liability for each eligible status
        - Recommended status
        - Potential savings from optimal choice
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return self._error_result(session_id, "filing_status_comparison", "Tax return not found")

        try:
            recommendation = self.filing_status_optimizer.analyze(tax_return)

            # Convert analyses to serializable format
            analyses_data = {}
            for status, analysis in recommendation.analyses.items():
                analyses_data[status] = {
                    "filing_status": analysis.filing_status,
                    "federal_tax": analysis.federal_tax,
                    "state_tax": analysis.state_tax,
                    "total_tax": analysis.total_tax,
                    "effective_rate": analysis.effective_rate,
                    "marginal_rate": analysis.marginal_rate,
                    "refund_or_owed": analysis.refund_or_owed,
                    "is_eligible": analysis.is_eligible,
                    "eligibility_reason": analysis.eligibility_reason,
                    "benefits": analysis.benefits,
                    "drawbacks": analysis.drawbacks,
                }

            return OptimizationResult(
                success=True,
                session_id=session_id,
                analysis_type="filing_status_comparison",
                timestamp=datetime.utcnow().isoformat(),
                data={
                    "recommended_status": recommendation.recommended_status,
                    "current_status": recommendation.current_status,
                    "potential_savings": recommendation.potential_savings,
                    "analyses": analyses_data,
                    "recommendation_reason": recommendation.recommendation_reason,
                },
                summary=recommendation.recommendation_reason,
                total_potential_savings=recommendation.potential_savings,
                confidence=recommendation.confidence_score,
                warnings=recommendation.warnings,
                recommendations=recommendation.additional_considerations,
            )

        except Exception as e:
            logger.error(f"Filing status comparison failed for {session_id}: {e}")
            return self._error_result(session_id, "filing_status_comparison", str(e))

    def get_entity_comparison(
        self,
        session_id: str,
        gross_revenue: Optional[float] = None,
        business_expenses: Optional[float] = None,
        owner_salary: Optional[float] = None,
    ) -> OptimizationResult:
        """
        Compare business entity structures (Sole Prop vs LLC vs S-Corp).

        Returns entity analysis including:
        - Tax liability for each structure
        - Recommended entity type
        - S-Corp reasonable salary analysis
        - 5-year savings projection
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return self._error_result(session_id, "entity_comparison", "Tax return not found")

        try:
            # Get self-employment income from return if not provided
            if gross_revenue is None:
                income = tax_return.income
                gross_revenue = getattr(income, 'self_employment_income', 0) or 0

            if business_expenses is None:
                business_expenses = getattr(tax_return.income, 'self_employment_expenses', 0) or 0

            if gross_revenue <= 0:
                return OptimizationResult(
                    success=True,
                    session_id=session_id,
                    analysis_type="entity_comparison",
                    timestamp=datetime.utcnow().isoformat(),
                    data={"message": "No self-employment income found"},
                    summary="Entity comparison requires self-employment income.",
                    total_potential_savings=0,
                    confidence=100,
                    warnings=["No business income detected for entity comparison"],
                    recommendations=["Enter self-employment income to compare entity structures"],
                )

            # Configure optimizer with filing status
            filing_status = tax_return.taxpayer.filing_status.value
            other_income = (tax_return.adjusted_gross_income or 0) - gross_revenue + business_expenses

            optimizer = self.entity_optimizer
            optimizer.filing_status = filing_status
            optimizer.other_income = max(0, other_income)

            # Run comparison
            from recommendation.entity_optimizer import EntityType
            comparison = optimizer.compare_structures(
                gross_revenue=gross_revenue,
                business_expenses=business_expenses,
                owner_salary=owner_salary,
                current_entity=EntityType.SOLE_PROPRIETORSHIP,
            )

            # Convert analyses to dict
            analyses_data = {}
            for entity_type, analysis in comparison.analyses.items():
                analyses_data[entity_type] = {
                    "entity_type": analysis.entity_type.value,
                    "entity_name": analysis.entity_name,
                    "gross_revenue": analysis.gross_revenue,
                    "business_expenses": analysis.business_expenses,
                    "net_business_income": analysis.net_business_income,
                    "owner_salary": analysis.owner_salary,
                    "k1_distribution": analysis.k1_distribution,
                    "self_employment_tax": analysis.self_employment_tax,
                    "income_tax_on_business": analysis.income_tax_on_business,
                    "payroll_taxes": analysis.payroll_taxes,
                    "qbi_deduction": analysis.qbi_deduction,
                    "total_business_tax": analysis.total_business_tax,
                    "effective_tax_rate": analysis.effective_tax_rate,
                    "formation_cost": analysis.formation_cost,
                    "annual_compliance_cost": analysis.annual_compliance_cost,
                    "total_annual_cost": analysis.total_annual_cost,
                    "is_recommended": analysis.is_recommended,
                    "recommendation_notes": analysis.recommendation_notes,
                }

            # Salary analysis
            salary_data = None
            if comparison.salary_analysis:
                salary_data = {
                    "recommended_salary": comparison.salary_analysis.recommended_salary,
                    "salary_range_low": comparison.salary_analysis.salary_range_low,
                    "salary_range_high": comparison.salary_analysis.salary_range_high,
                    "methodology": comparison.salary_analysis.methodology,
                    "factors_considered": comparison.salary_analysis.factors_considered,
                    "irs_risk_level": comparison.salary_analysis.irs_risk_level,
                    "notes": comparison.salary_analysis.notes,
                }

            return OptimizationResult(
                success=True,
                session_id=session_id,
                analysis_type="entity_comparison",
                timestamp=datetime.utcnow().isoformat(),
                data={
                    "analyses": analyses_data,
                    "recommended_entity": comparison.recommended_entity.value,
                    "current_entity": comparison.current_entity.value if comparison.current_entity else None,
                    "max_annual_savings": comparison.max_annual_savings,
                    "savings_vs_current": comparison.savings_vs_current,
                    "salary_analysis": salary_data,
                    "breakeven_revenue": comparison.breakeven_revenue,
                    "five_year_savings": comparison.five_year_savings,
                },
                summary=comparison.recommendation_reason,
                total_potential_savings=comparison.max_annual_savings,
                confidence=comparison.confidence_score,
                warnings=comparison.warnings,
                recommendations=comparison.considerations,
            )

        except Exception as e:
            logger.error(f"Entity comparison failed for {session_id}: {e}")
            return self._error_result(session_id, "entity_comparison", str(e))

    def get_full_strategy(self, session_id: str) -> OptimizationResult:
        """
        Generate comprehensive tax strategy analysis.

        Returns complete strategy report including:
        - Retirement contribution analysis
        - Investment tax strategies
        - Strategies by priority (immediate, current year, next year, long-term)
        - Total potential savings
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return self._error_result(session_id, "full_strategy", "Tax return not found")

        try:
            report = self.tax_strategy_advisor.generate_strategy_report(tax_return)

            # Convert retirement analysis
            retirement_data = {
                "current_401k_contribution": report.retirement_analysis.current_401k_contribution,
                "max_401k_contribution": report.retirement_analysis.max_401k_contribution,
                "current_ira_contribution": report.retirement_analysis.current_ira_contribution,
                "max_ira_contribution": report.retirement_analysis.max_ira_contribution,
                "catch_up_eligible": report.retirement_analysis.catch_up_eligible,
                "catch_up_amount": report.retirement_analysis.catch_up_amount,
                "roth_vs_traditional_recommendation": report.retirement_analysis.roth_vs_traditional_recommendation,
                "employer_match_captured": report.retirement_analysis.employer_match_captured,
                "employer_match_available": report.retirement_analysis.employer_match_available,
                "additional_contribution_potential": report.retirement_analysis.additional_contribution_potential,
                "tax_savings_if_maxed": report.retirement_analysis.tax_savings_if_maxed,
            }

            # Convert investment analysis
            investment_data = {
                "unrealized_gains": report.investment_analysis.unrealized_gains,
                "unrealized_losses": report.investment_analysis.unrealized_losses,
                "tax_loss_harvesting_potential": report.investment_analysis.tax_loss_harvesting_potential,
                "qualified_dividend_amount": report.investment_analysis.qualified_dividend_amount,
                "long_term_vs_short_term_gains": report.investment_analysis.long_term_vs_short_term_gains,
                "estimated_niit_exposure": report.investment_analysis.estimated_niit_exposure,
                "tax_efficient_placement_recommendations": report.investment_analysis.tax_efficient_placement_recommendations,
            }

            # Convert strategies
            def strategy_to_dict(s):
                return {
                    "title": s.title,
                    "category": s.category,
                    "priority": s.priority,
                    "estimated_savings": s.estimated_savings,
                    "description": s.description,
                    "action_steps": s.action_steps,
                    "requirements": s.requirements,
                    "risks_considerations": s.risks_considerations,
                    "deadline": s.deadline,
                    "complexity": s.complexity,
                    "professional_help_recommended": s.professional_help_recommended,
                }

            return OptimizationResult(
                success=True,
                session_id=session_id,
                analysis_type="full_strategy",
                timestamp=datetime.utcnow().isoformat(),
                data={
                    "filing_status": report.filing_status,
                    "tax_year": report.tax_year,
                    "current_tax_liability": report.current_tax_liability,
                    "current_effective_rate": report.current_effective_rate,
                    "retirement_analysis": retirement_data,
                    "investment_analysis": investment_data,
                    "immediate_strategies": [strategy_to_dict(s) for s in report.immediate_strategies],
                    "current_year_strategies": [strategy_to_dict(s) for s in report.current_year_strategies],
                    "next_year_strategies": [strategy_to_dict(s) for s in report.next_year_strategies],
                    "long_term_strategies": [strategy_to_dict(s) for s in report.long_term_strategies],
                    "top_three_recommendations": report.top_three_recommendations,
                },
                summary=f"Identified ${report.total_potential_savings:,.0f} in potential tax savings across {len(report.immediate_strategies) + len(report.current_year_strategies)} strategies.",
                total_potential_savings=report.total_potential_savings,
                confidence=report.confidence_score,
                warnings=report.warnings,
                recommendations=report.top_three_recommendations,
            )

        except Exception as e:
            logger.error(f"Full strategy analysis failed for {session_id}: {e}")
            return self._error_result(session_id, "full_strategy", str(e))

    def _credit_to_dict(self, credit) -> Dict[str, Any]:
        """Convert CreditEligibility to dictionary."""
        return {
            "credit_name": credit.credit_name,
            "credit_code": credit.credit_code,
            "credit_type": credit.credit_type,
            "is_eligible": credit.is_eligible,
            "potential_amount": credit.potential_amount,
            "actual_amount": credit.actual_amount,
            "eligibility_reason": credit.eligibility_reason,
            "phase_out_applied": credit.phase_out_applied,
            "requirements": credit.requirements,
            "missing_requirements": credit.missing_requirements,
            "documentation_needed": credit.documentation_needed,
            "optimization_tips": credit.optimization_tips,
        }

    def _error_result(self, session_id: str, analysis_type: str, error: str) -> OptimizationResult:
        """Create an error result."""
        return OptimizationResult(
            success=False,
            session_id=session_id,
            analysis_type=analysis_type,
            timestamp=datetime.utcnow().isoformat(),
            data={"error": error},
            summary=f"Analysis failed: {error}",
            total_potential_savings=0,
            confidence=0,
            warnings=[error],
            recommendations=[],
        )


# Singleton instance
_optimizer_adapter: Optional[OptimizerAdapter] = None


def get_optimizer_adapter() -> OptimizerAdapter:
    """Get or create singleton optimizer adapter."""
    global _optimizer_adapter
    if _optimizer_adapter is None:
        _optimizer_adapter = OptimizerAdapter()
    return _optimizer_adapter
