"""
Advisory Service - Application service for tax recommendations.

This service generates and manages tax optimization recommendations:
- Analyzing returns for optimization opportunities
- Generating actionable recommendations
- Tracking recommendation status and outcomes
- Producing advisory reports

This is an APPLICATION SERVICE - it orchestrates domain operations
but contains no business logic itself.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from .logging_config import get_logger
from .tax_return_service import TaxReturnService
from .scenario_service import ScenarioService

# Import domain models
from domain import (
    AdvisoryPlan,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    RecommendationAction,
    ScenarioType,
    RecommendationGenerated,
    RecommendationStatusChanged,
    AdvisoryPlanFinalized,
    publish_event,
)

from database.persistence import get_persistence


logger = get_logger(__name__)


class AdvisoryService:
    """
    Application service for tax advisory operations.

    Provides recommendation generation and management:
    - Retirement optimization (401k, IRA, HSA)
    - Deduction strategies (bunching, timing)
    - Credit optimization (education, energy)
    - Entity structure analysis
    - Filing status optimization
    """

    def __init__(
        self,
        tax_return_service: Optional[TaxReturnService] = None,
        scenario_service: Optional[ScenarioService] = None
    ):
        """
        Initialize AdvisoryService.

        Args:
            tax_return_service: Service for tax return operations
            scenario_service: Service for scenario analysis
        """
        self._tax_return_service = tax_return_service or TaxReturnService()
        self._scenario_service = scenario_service or ScenarioService()
        self._persistence = get_persistence()
        self._logger = get_logger(__name__)
        # In-memory plan storage (would be DB in production)
        self._plans: Dict[str, AdvisoryPlan] = {}

    def generate_recommendations(
        self,
        return_id: str,
        client_id: Optional[str] = None,
        categories: Optional[List[RecommendationCategory]] = None
    ) -> AdvisoryPlan:
        """
        Generate tax optimization recommendations for a return.

        Args:
            return_id: Return identifier
            client_id: Optional client identifier
            categories: Optional list of categories to focus on

        Returns:
            AdvisoryPlan with recommendations
        """
        # Load return data
        return_data = self._persistence.load_return(return_id)
        if not return_data:
            raise ValueError(f"Return not found: {return_id}")

        tax_year = return_data.get("tax_year", 2025)
        client_uuid = UUID(client_id) if client_id else uuid4()

        # Create advisory plan
        plan = AdvisoryPlan(
            client_id=client_uuid,
            return_id=UUID(return_id),
            tax_year=tax_year
        )

        # Generate recommendations for each category
        if categories is None:
            categories = list(RecommendationCategory)

        for category in categories:
            recs = self._generate_category_recommendations(return_data, category)
            for rec in recs:
                plan.add_recommendation(rec)

        # Store plan
        self._plans[str(plan.plan_id)] = plan

        # Publish event
        publish_event(RecommendationGenerated(
            plan_id=plan.plan_id,
            return_id=UUID(return_id),
            recommendation_count=len(plan.recommendations),
            total_potential_savings=plan.total_potential_savings,
            categories=[c.value for c in categories],
            aggregate_id=plan.plan_id,
            aggregate_type="advisory",
        ))

        self._logger.info(
            f"Generated {len(plan.recommendations)} recommendations",
            extra={'extra_data': {
                'plan_id': str(plan.plan_id),
                'return_id': return_id,
                'total_savings': plan.total_potential_savings,
            }}
        )

        return plan

    def _generate_category_recommendations(
        self,
        return_data: Dict[str, Any],
        category: RecommendationCategory
    ) -> List[Recommendation]:
        """Generate recommendations for a specific category."""
        generators = {
            RecommendationCategory.RETIREMENT: self._retirement_recommendations,
            RecommendationCategory.DEDUCTION: self._deduction_recommendations,
            RecommendationCategory.HEALTHCARE: self._healthcare_recommendations,
            RecommendationCategory.CHARITABLE: self._charitable_recommendations,
            RecommendationCategory.CREDIT: self._credit_recommendations,
            RecommendationCategory.INVESTMENT: self._investment_recommendations,
        }

        generator = generators.get(category)
        if generator:
            return generator(return_data)
        return []

    def _retirement_recommendations(self, return_data: Dict[str, Any]) -> List[Recommendation]:
        """Generate retirement-related recommendations."""
        recommendations = []
        deductions = return_data.get("deductions", {})
        income = return_data.get("income", {})
        taxpayer = return_data.get("taxpayer", {})

        # Get current contributions
        current_401k = deductions.get("retirement_contributions", 0)
        current_ira = deductions.get("ira_contributions", 0)
        is_age_50_plus = taxpayer.get("is_age_50_plus", False)

        # 2025 limits
        max_401k = 23500 + (7500 if is_age_50_plus else 0)
        max_ira = 7000 + (1000 if is_age_50_plus else 0)

        # Calculate taxable income for marginal rate estimation
        agi = return_data.get("adjusted_gross_income", 0)
        marginal_rate = self._estimate_marginal_rate(
            agi,
            taxpayer.get("filing_status", "single")
        )

        # 401k recommendation
        if current_401k < max_401k:
            additional = max_401k - current_401k
            estimated_savings = additional * marginal_rate

            recommendations.append(Recommendation(
                category=RecommendationCategory.RETIREMENT,
                priority=RecommendationPriority.IMMEDIATE if datetime.now().month >= 10 else RecommendationPriority.CURRENT_YEAR,
                title="Maximize 401(k) Contributions",
                summary=f"Contribute an additional ${additional:,.0f} to reach the ${max_401k:,.0f} limit",
                detailed_explanation=(
                    f"Your current 401(k) contribution is ${current_401k:,.0f}. "
                    f"The 2025 limit is ${max_401k:,.0f}. By contributing an additional "
                    f"${additional:,.0f}, you could reduce your taxable income and save "
                    f"approximately ${estimated_savings:,.0f} in federal taxes."
                ),
                estimated_savings=estimated_savings,
                confidence_level=0.9,
                complexity="low",
                action_steps=[
                    RecommendationAction(
                        step_number=1,
                        action="Contact HR or access your employer benefits portal",
                        estimated_time="15 minutes"
                    ),
                    RecommendationAction(
                        step_number=2,
                        action="Increase your 401(k) contribution percentage",
                        details=f"Increase by enough to contribute ${additional:,.0f} more by year end"
                    ),
                    RecommendationAction(
                        step_number=3,
                        action="Verify the change is reflected in your next paycheck"
                    )
                ],
                irs_references=["IRC Section 402(g)", "IRS Publication 560"]
            ))

        # IRA recommendation
        if current_ira < max_ira and agi < 153000:  # Simplified MAGI check
            additional = max_ira - current_ira
            estimated_savings = additional * marginal_rate * 0.8  # Lower confidence

            recommendations.append(Recommendation(
                category=RecommendationCategory.RETIREMENT,
                priority=RecommendationPriority.CURRENT_YEAR,
                title="Contribute to Traditional IRA",
                summary=f"Contribute up to ${additional:,.0f} to a Traditional IRA",
                detailed_explanation=(
                    f"You may be eligible to deduct IRA contributions up to ${max_ira:,.0f}. "
                    f"This depends on your income and whether you're covered by an employer plan. "
                    f"Potential tax savings of approximately ${estimated_savings:,.0f}."
                ),
                estimated_savings=estimated_savings,
                confidence_level=0.7,
                complexity="medium",
                action_steps=[
                    RecommendationAction(
                        step_number=1,
                        action="Verify IRA deduction eligibility based on income and employer plan coverage"
                    ),
                    RecommendationAction(
                        step_number=2,
                        action="Open or fund a Traditional IRA account",
                        deadline="April 15 of following year"
                    )
                ],
                irs_references=["IRC Section 219", "IRS Publication 590-A"]
            ))

        return recommendations

    def _healthcare_recommendations(self, return_data: Dict[str, Any]) -> List[Recommendation]:
        """Generate healthcare-related recommendations."""
        recommendations = []
        deductions = return_data.get("deductions", {})
        taxpayer = return_data.get("taxpayer", {})

        # Check for HSA eligibility
        has_hdhp = return_data.get("has_high_deductible_health_plan", False)
        current_hsa = deductions.get("hsa_contributions", 0)
        is_family = taxpayer.get("filing_status") in ["married_joint"]
        is_age_55_plus = taxpayer.get("is_age_55_plus", False)

        # 2025 HSA limits
        max_hsa = (8550 if is_family else 4300) + (1000 if is_age_55_plus else 0)

        if has_hdhp and current_hsa < max_hsa:
            additional = max_hsa - current_hsa
            agi = return_data.get("adjusted_gross_income", 0)
            marginal_rate = self._estimate_marginal_rate(
                agi,
                taxpayer.get("filing_status", "single")
            )
            # HSA has triple tax advantage
            estimated_savings = additional * (marginal_rate + 0.0765)  # Plus FICA

            recommendations.append(Recommendation(
                category=RecommendationCategory.HEALTHCARE,
                priority=RecommendationPriority.IMMEDIATE,
                title="Maximize HSA Contributions",
                summary=f"Contribute an additional ${additional:,.0f} to your HSA",
                detailed_explanation=(
                    f"HSAs offer a triple tax advantage: tax-deductible contributions, "
                    f"tax-free growth, and tax-free qualified withdrawals. "
                    f"Your 2025 limit is ${max_hsa:,.0f}. Current: ${current_hsa:,.0f}."
                ),
                estimated_savings=estimated_savings,
                confidence_level=0.95,
                complexity="low",
                action_steps=[
                    RecommendationAction(
                        step_number=1,
                        action="Log into your HSA account or employer benefits portal"
                    ),
                    RecommendationAction(
                        step_number=2,
                        action=f"Contribute ${additional:,.0f} additional to your HSA",
                        deadline="December 31" if datetime.now().month <= 12 else "April 15"
                    )
                ],
                irs_references=["IRC Section 223", "IRS Publication 969"]
            ))

        return recommendations

    def _deduction_recommendations(self, return_data: Dict[str, Any]) -> List[Recommendation]:
        """Generate deduction-related recommendations."""
        recommendations = []
        deductions = return_data.get("deductions", {})
        taxpayer = return_data.get("taxpayer", {})
        filing_status = taxpayer.get("filing_status", "single")

        # Get standard deduction for filing status
        standard_deductions = {
            "single": 15000,
            "married_joint": 30000,
            "married_separate": 15000,
            "head_of_household": 22500,
            "qualifying_widow": 30000,
        }
        standard = standard_deductions.get(filing_status, 15000)

        # Calculate current itemized deductions
        salt = min(deductions.get("state_local_taxes", 0), 10000)
        mortgage = deductions.get("mortgage_interest", 0)
        charitable = deductions.get("charitable_contributions", 0)
        medical = deductions.get("medical_expenses", 0)

        total_itemized = salt + mortgage + charitable + medical

        # Bunching recommendation if close to threshold
        if standard * 0.7 < total_itemized < standard * 1.3:
            bunching_potential = charitable * 2  # Rough estimate
            if bunching_potential > standard:
                estimated_savings = (bunching_potential - standard) * 0.22

                recommendations.append(Recommendation(
                    category=RecommendationCategory.DEDUCTION,
                    priority=RecommendationPriority.CURRENT_YEAR,
                    title="Consider Charitable Bunching Strategy",
                    summary="Concentrate 2 years of donations into 1 year to exceed standard deduction",
                    detailed_explanation=(
                        f"Your itemized deductions (${total_itemized:,.0f}) are close to the "
                        f"standard deduction (${standard:,.0f}). By 'bunching' two years of "
                        f"charitable contributions into one year, you could itemize that year "
                        f"and take the standard deduction the next year, potentially saving taxes."
                    ),
                    estimated_savings=estimated_savings,
                    confidence_level=0.75,
                    complexity="medium",
                    action_steps=[
                        RecommendationAction(
                            step_number=1,
                            action="Calculate your 2-year charitable giving plan"
                        ),
                        RecommendationAction(
                            step_number=2,
                            action="Consider a Donor Advised Fund for flexibility",
                            details="DAF allows immediate deduction with future distributions"
                        ),
                        RecommendationAction(
                            step_number=3,
                            action="Make concentrated donations before Dec 31"
                        )
                    ],
                    irs_references=["IRC Section 170", "IRS Publication 526"]
                ))

        return recommendations

    def _charitable_recommendations(self, return_data: Dict[str, Any]) -> List[Recommendation]:
        """Generate charitable giving recommendations."""
        recommendations = []
        income = return_data.get("income", {})
        taxpayer = return_data.get("taxpayer", {})

        # Check for appreciated assets
        ltcg = income.get("long_term_capital_gains", 0)
        if ltcg > 10000:
            estimated_savings = ltcg * 0.20  # Avoid LTCG tax

            recommendations.append(Recommendation(
                category=RecommendationCategory.CHARITABLE,
                priority=RecommendationPriority.LONG_TERM,
                title="Donate Appreciated Securities",
                summary="Donate appreciated stock instead of cash to avoid capital gains tax",
                detailed_explanation=(
                    f"If you have appreciated stock or mutual funds, donating them directly "
                    f"to charity allows you to avoid capital gains tax while still receiving "
                    f"a deduction for the full fair market value."
                ),
                estimated_savings=estimated_savings,
                confidence_level=0.85,
                complexity="medium",
                action_steps=[
                    RecommendationAction(
                        step_number=1,
                        action="Identify appreciated securities held over 1 year"
                    ),
                    RecommendationAction(
                        step_number=2,
                        action="Contact your broker to initiate a stock donation"
                    ),
                    RecommendationAction(
                        step_number=3,
                        action="Get written acknowledgment from the charity"
                    )
                ],
                irs_references=["IRC Section 170(e)", "IRS Publication 526"]
            ))

        return recommendations

    def _credit_recommendations(self, return_data: Dict[str, Any]) -> List[Recommendation]:
        """Generate tax credit recommendations."""
        recommendations = []
        taxpayer = return_data.get("taxpayer", {})
        dependents = taxpayer.get("dependents", [])

        # Check for education credits
        for dep in dependents:
            if dep.get("is_student", False):
                recommendations.append(Recommendation(
                    category=RecommendationCategory.CREDIT,
                    priority=RecommendationPriority.CURRENT_YEAR,
                    title="Claim Education Credits",
                    summary="American Opportunity Credit worth up to $2,500 per student",
                    detailed_explanation=(
                        f"If you have students in their first 4 years of college, "
                        f"the American Opportunity Credit provides up to $2,500 per student. "
                        f"The first $1,000 is fully refundable."
                    ),
                    estimated_savings=2500,
                    confidence_level=0.8,
                    complexity="low",
                    action_steps=[
                        RecommendationAction(
                            step_number=1,
                            action="Gather Form 1098-T from educational institution"
                        ),
                        RecommendationAction(
                            step_number=2,
                            action="Verify student meets eligibility requirements"
                        )
                    ],
                    irs_references=["IRC Section 25A", "IRS Form 8863"]
                ))
                break  # Only one recommendation needed

        return recommendations

    def _investment_recommendations(self, return_data: Dict[str, Any]) -> List[Recommendation]:
        """Generate investment-related recommendations."""
        recommendations = []
        income = return_data.get("income", {})

        # Tax loss harvesting
        stcg = income.get("short_term_capital_gains", 0)
        ltcg = income.get("long_term_capital_gains", 0)
        if stcg > 0 or ltcg > 0:
            recommendations.append(Recommendation(
                category=RecommendationCategory.INVESTMENT,
                priority=RecommendationPriority.CURRENT_YEAR,
                title="Consider Tax Loss Harvesting",
                summary="Sell losing investments to offset gains",
                detailed_explanation=(
                    f"Tax loss harvesting involves selling investments at a loss to offset "
                    f"capital gains. Losses first offset gains of the same type (short vs long), "
                    f"then cross over, and up to $3,000 can offset ordinary income."
                ),
                estimated_savings=(stcg + ltcg) * 0.15 * 0.5,  # Conservative estimate
                confidence_level=0.7,
                complexity="medium",
                action_steps=[
                    RecommendationAction(
                        step_number=1,
                        action="Review portfolio for unrealized losses"
                    ),
                    RecommendationAction(
                        step_number=2,
                        action="Sell losing positions before Dec 31"
                    ),
                    RecommendationAction(
                        step_number=3,
                        action="Wait 31 days before repurchasing (wash sale rule)"
                    )
                ],
                irs_references=["IRC Section 1211", "IRC Section 1091 (wash sales)"]
            ))

        return recommendations

    def _estimate_marginal_rate(self, agi: float, filing_status: str) -> float:
        """Estimate marginal tax rate based on AGI and filing status."""
        # Simplified 2025 brackets
        if filing_status == "married_joint":
            if agi > 731200:
                return 0.37
            elif agi > 487450:
                return 0.35
            elif agi > 383900:
                return 0.32
            elif agi > 201050:
                return 0.24
            elif agi > 94300:
                return 0.22
            elif agi > 23200:
                return 0.12
            else:
                return 0.10
        else:  # Single and others
            if agi > 609350:
                return 0.37
            elif agi > 243725:
                return 0.35
            elif agi > 191950:
                return 0.32
            elif agi > 100525:
                return 0.24
            elif agi > 47150:
                return 0.22
            elif agi > 11600:
                return 0.12
            else:
                return 0.10

    def get_plan(self, plan_id: str) -> Optional[AdvisoryPlan]:
        """Get an advisory plan by ID."""
        return self._plans.get(plan_id)

    def get_plans_for_client(self, client_id: str) -> List[AdvisoryPlan]:
        """Get all plans for a client."""
        return [
            p for p in self._plans.values()
            if str(p.client_id) == client_id
        ]

    def update_recommendation_status(
        self,
        plan_id: str,
        recommendation_id: str,
        status: RecommendationStatus,
        changed_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update a recommendation's status.

        Args:
            plan_id: Plan identifier
            recommendation_id: Recommendation identifier
            status: New status
            changed_by: Who made the change
            reason: Optional reason for the change

        Returns:
            True if updated successfully
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        rec = plan.get_recommendation(UUID(recommendation_id))
        if not rec:
            return False

        old_status = rec.status
        rec.update_status(status, changed_by, reason)

        # Publish event
        publish_event(RecommendationStatusChanged(
            recommendation_id=UUID(recommendation_id),
            plan_id=UUID(plan_id),
            old_status=old_status.value,
            new_status=status.value,
            changed_by=changed_by,
            reason=reason,
            aggregate_id=UUID(plan_id),
            aggregate_type="advisory",
        ))

        self._logger.info(
            f"Updated recommendation status",
            extra={'extra_data': {
                'recommendation_id': recommendation_id,
                'old_status': old_status.value,
                'new_status': status.value,
            }}
        )

        return True

    def record_recommendation_outcome(
        self,
        plan_id: str,
        recommendation_id: str,
        actual_savings: float,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record the actual outcome of an implemented recommendation.

        Args:
            plan_id: Plan identifier
            recommendation_id: Recommendation identifier
            actual_savings: Actual savings realized
            notes: Optional notes about the outcome

        Returns:
            True if updated successfully
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        rec = plan.get_recommendation(UUID(recommendation_id))
        if not rec:
            return False

        rec.record_outcome(actual_savings, notes)

        # Recalculate plan totals
        plan._recalculate_totals()

        self._logger.info(
            f"Recorded recommendation outcome",
            extra={'extra_data': {
                'recommendation_id': recommendation_id,
                'estimated': rec.estimated_savings,
                'actual': actual_savings,
            }}
        )

        return True

    def finalize_plan(self, plan_id: str, finalized_by: str) -> bool:
        """
        Finalize an advisory plan for client delivery.

        Args:
            plan_id: Plan identifier
            finalized_by: Name of person finalizing

        Returns:
            True if finalized successfully
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        plan.finalize(finalized_by)

        # Publish event
        publish_event(AdvisoryPlanFinalized(
            plan_id=UUID(plan_id),
            client_id=plan.client_id,
            total_recommendations=len(plan.recommendations),
            total_potential_savings=plan.total_potential_savings,
            finalized_by=finalized_by,
            aggregate_id=UUID(plan_id),
            aggregate_type="advisory",
        ))

        self._logger.info(
            f"Finalized advisory plan",
            extra={'extra_data': {
                'plan_id': plan_id,
                'recommendations': len(plan.recommendations),
                'potential_savings': plan.total_potential_savings,
            }}
        )

        return True

    def get_plan_summary(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of an advisory plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        return plan.get_summary()

    def export_advisory_report(
        self,
        plan_id: str,
        format: str = "text"
    ) -> Optional[str]:
        """
        Export an advisory plan as a report.

        Args:
            plan_id: Plan identifier
            format: Output format (text, html, markdown)

        Returns:
            Formatted report string
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        if format == "markdown":
            return self._export_markdown(plan)
        else:
            return self._export_text(plan)

    def _export_text(self, plan: AdvisoryPlan) -> str:
        """Export plan as plain text."""
        lines = [
            f"TAX ADVISORY PLAN - {plan.tax_year}",
            "=" * 50,
            f"",
            f"Total Potential Savings: ${plan.total_potential_savings:,.2f}",
            f"Total Recommendations: {len(plan.recommendations)}",
            f"",
            "RECOMMENDATIONS",
            "-" * 50,
        ]

        for priority in RecommendationPriority:
            recs = plan.get_by_priority(priority)
            if recs:
                lines.append(f"\n{priority.value.upper()} ACTIONS:")
                for i, rec in enumerate(recs, 1):
                    lines.append(f"\n{i}. {rec.title}")
                    lines.append(f"   Est. Savings: ${rec.estimated_savings:,.2f}")
                    lines.append(f"   {rec.summary}")

        return "\n".join(lines)

    def _export_markdown(self, plan: AdvisoryPlan) -> str:
        """Export plan as markdown."""
        lines = [
            f"# Tax Advisory Plan - {plan.tax_year}",
            f"",
            f"**Total Potential Savings:** ${plan.total_potential_savings:,.2f}",
            f"**Total Recommendations:** {len(plan.recommendations)}",
            f"",
            "## Recommendations",
        ]

        for priority in RecommendationPriority:
            recs = plan.get_by_priority(priority)
            if recs:
                lines.append(f"\n### {priority.value.replace('_', ' ').title()} Actions\n")
                for rec in recs:
                    lines.append(f"#### {rec.title}")
                    lines.append(f"**Estimated Savings:** ${rec.estimated_savings:,.2f}")
                    lines.append(f"\n{rec.summary}\n")
                    if rec.action_steps:
                        lines.append("**Action Steps:**")
                        for step in rec.action_steps:
                            lines.append(f"1. {step.action}")
                    lines.append("")

        return "\n".join(lines)
