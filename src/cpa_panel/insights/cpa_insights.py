"""
CPA Insights Engine

Provides CPA-specific insights for tax return review:
- Review checklists
- Risk indicators and red flags
- Compliance alerts
- Optimization opportunities

Designed to help CPAs efficiently review returns and identify issues.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InsightCategory(str, Enum):
    """Categories for CPA insights."""
    REVIEW_REQUIRED = "review_required"
    RISK_FLAG = "risk_flag"
    COMPLIANCE = "compliance"
    OPTIMIZATION = "optimization"
    DATA_QUALITY = "data_quality"
    DOCUMENTATION = "documentation"


class InsightPriority(str, Enum):
    """Priority levels for insights."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class CPAInsight:
    """A CPA-specific insight."""
    id: str
    category: InsightCategory
    priority: InsightPriority
    title: str
    description: str
    action_required: Optional[str] = None
    reference: Optional[str] = None  # IRS reference, form number, etc.
    affected_fields: List[str] = field(default_factory=list)
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "action_required": self.action_required,
            "reference": self.reference,
            "affected_fields": self.affected_fields,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class InsightsSummary:
    """Summary of insights for a return."""
    total_insights: int
    by_category: Dict[str, int]
    by_priority: Dict[str, int]
    critical_count: int
    action_required_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_insights": self.total_insights,
            "by_category": self.by_category,
            "by_priority": self.by_priority,
            "critical_count": self.critical_count,
            "action_required_count": self.action_required_count,
        }


@dataclass
class ReviewChecklist:
    """CPA review checklist item."""
    id: str
    item: str
    completed: bool = False
    notes: Optional[str] = None
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "item": self.item,
            "completed": self.completed,
            "notes": self.notes,
            "completed_by": self.completed_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class CPAInsightsEngine:
    """
    Generates CPA-specific insights for tax return review.

    Helps CPAs:
    - Identify items requiring review
    - Flag potential risks
    - Ensure compliance
    - Find optimization opportunities
    """

    def __init__(self):
        """Initialize insights engine."""
        pass

    def analyze(self, tax_return: Any) -> List[CPAInsight]:
        """
        Analyze a tax return and generate CPA insights.

        Args:
            tax_return: TaxReturn object

        Returns:
            List of CPAInsight
        """
        insights = []

        # Run all analysis methods
        insights.extend(self._check_data_quality(tax_return))
        insights.extend(self._check_income_items(tax_return))
        insights.extend(self._check_deductions(tax_return))
        insights.extend(self._check_credits(tax_return))
        insights.extend(self._check_compliance(tax_return))
        insights.extend(self._check_optimizations(tax_return))

        # Sort by priority
        priority_order = {
            InsightPriority.CRITICAL: 0,
            InsightPriority.HIGH: 1,
            InsightPriority.MEDIUM: 2,
            InsightPriority.LOW: 3,
            InsightPriority.INFO: 4,
        }
        insights.sort(key=lambda i: priority_order.get(i.priority, 5))

        return insights

    def get_summary(self, insights: List[CPAInsight]) -> InsightsSummary:
        """
        Get summary of insights.

        Args:
            insights: List of CPAInsight

        Returns:
            InsightsSummary
        """
        by_category = {}
        by_priority = {}
        critical_count = 0
        action_count = 0

        for insight in insights:
            cat = insight.category.value
            pri = insight.priority.value

            by_category[cat] = by_category.get(cat, 0) + 1
            by_priority[pri] = by_priority.get(pri, 0) + 1

            if insight.priority == InsightPriority.CRITICAL:
                critical_count += 1

            if insight.action_required:
                action_count += 1

        return InsightsSummary(
            total_insights=len(insights),
            by_category=by_category,
            by_priority=by_priority,
            critical_count=critical_count,
            action_required_count=action_count,
        )

    def _check_data_quality(self, tax_return: Any) -> List[CPAInsight]:
        """Check for data quality issues."""
        insights = []
        idx = 1

        # Check taxpayer info
        if tax_return.taxpayer:
            tp = tax_return.taxpayer

            if not tp.ssn:
                insights.append(CPAInsight(
                    id=f"DQ{idx:03d}",
                    category=InsightCategory.DATA_QUALITY,
                    priority=InsightPriority.CRITICAL,
                    title="Missing SSN",
                    description="Taxpayer Social Security Number is not provided",
                    action_required="Obtain and verify SSN before filing",
                    affected_fields=["taxpayer.ssn"],
                ))
                idx += 1

            if not tp.first_name or not tp.last_name:
                insights.append(CPAInsight(
                    id=f"DQ{idx:03d}",
                    category=InsightCategory.DATA_QUALITY,
                    priority=InsightPriority.HIGH,
                    title="Incomplete Name",
                    description="Taxpayer name is incomplete",
                    action_required="Complete taxpayer name information",
                    affected_fields=["taxpayer.first_name", "taxpayer.last_name"],
                ))
                idx += 1

        # Check income
        if tax_return.income:
            income = tax_return.income

            if income.w2_forms:
                for i, w2 in enumerate(income.w2_forms):
                    if w2.wages > 0 and w2.federal_tax_withheld == 0:
                        insights.append(CPAInsight(
                            id=f"DQ{idx:03d}",
                            category=InsightCategory.DATA_QUALITY,
                            priority=InsightPriority.MEDIUM,
                            title=f"W-2 #{i+1}: No Withholding",
                            description=f"W-2 from {w2.employer_name} shows wages but no federal withholding",
                            action_required="Verify W-2 data is complete",
                            affected_fields=[f"income.w2_forms[{i}].federal_tax_withheld"],
                        ))
                        idx += 1

        return insights

    def _check_income_items(self, tax_return: Any) -> List[CPAInsight]:
        """Check income items for review."""
        insights = []
        idx = 1

        if not tax_return.income:
            return insights

        income = tax_return.income

        # Large self-employment income
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 50000:
            insights.append(CPAInsight(
                id=f"INC{idx:03d}",
                category=InsightCategory.REVIEW_REQUIRED,
                priority=InsightPriority.HIGH,
                title="Significant Self-Employment Income",
                description=f"Self-employment income of ${se_income:,.0f} requires Schedule C review",
                action_required="Review Schedule C for accuracy and proper expense categorization",
                reference="Schedule C, Schedule SE",
                affected_fields=["income.self_employment_income"],
            ))
            idx += 1

        # Capital gains
        ltcg = getattr(income, 'long_term_capital_gains', 0) or 0
        stcg = getattr(income, 'short_term_capital_gains', 0) or 0
        if ltcg + stcg > 10000:
            insights.append(CPAInsight(
                id=f"INC{idx:03d}",
                category=InsightCategory.REVIEW_REQUIRED,
                priority=InsightPriority.MEDIUM,
                title="Capital Gains Review",
                description=f"Capital gains of ${ltcg + stcg:,.0f} require Schedule D review",
                action_required="Verify cost basis and holding periods",
                reference="Schedule D, Form 8949",
                affected_fields=["income.long_term_capital_gains", "income.short_term_capital_gains"],
            ))
            idx += 1

        # Rental income
        rental = getattr(income, 'rental_income', 0) or 0
        if rental > 0:
            insights.append(CPAInsight(
                id=f"INC{idx:03d}",
                category=InsightCategory.REVIEW_REQUIRED,
                priority=InsightPriority.MEDIUM,
                title="Rental Income Present",
                description=f"Rental income of ${rental:,.0f} requires Schedule E review",
                action_required="Review depreciation schedules and expense documentation",
                reference="Schedule E",
                affected_fields=["income.rental_income"],
            ))
            idx += 1

        return insights

    def _check_deductions(self, tax_return: Any) -> List[CPAInsight]:
        """Check deductions for review."""
        insights = []
        idx = 1

        if not tax_return.deductions:
            return insights

        deductions = tax_return.deductions

        # Large itemized deductions
        if deductions.itemized:
            itemized = deductions.itemized
            total = itemized.get_total_itemized()

            # SALT cap
            salt = itemized.state_local_taxes or 0
            if salt > 10000:
                insights.append(CPAInsight(
                    id=f"DED{idx:03d}",
                    category=InsightCategory.COMPLIANCE,
                    priority=InsightPriority.HIGH,
                    title="SALT Deduction Exceeds Cap",
                    description=f"State and local taxes of ${salt:,.0f} exceed $10,000 cap",
                    action_required="Verify SALT is limited to $10,000",
                    reference="IRC Section 164(b)(6)",
                    affected_fields=["deductions.itemized.state_local_taxes"],
                ))
                idx += 1

            # Large charitable
            charitable = (itemized.charitable_cash or 0) + (itemized.charitable_noncash or 0)
            agi = float(tax_return.adjusted_gross_income or 0)
            if agi > 0 and charitable / agi > 0.3:
                insights.append(CPAInsight(
                    id=f"DED{idx:03d}",
                    category=InsightCategory.REVIEW_REQUIRED,
                    priority=InsightPriority.HIGH,
                    title="Large Charitable Deductions",
                    description=f"Charitable deductions of ${charitable:,.0f} exceed 30% of AGI",
                    action_required="Verify documentation for all charitable contributions",
                    reference="IRC Section 170",
                    affected_fields=["deductions.itemized.charitable_cash", "deductions.itemized.charitable_noncash"],
                ))
                idx += 1

            # Medical expenses
            medical = itemized.medical_expenses or 0
            if medical > 0 and agi > 0:
                threshold = agi * 0.075
                if medical < threshold:
                    insights.append(CPAInsight(
                        id=f"DED{idx:03d}",
                        category=InsightCategory.INFO,
                        priority=InsightPriority.LOW,
                        title="Medical Expenses Below Threshold",
                        description=f"Medical expenses of ${medical:,.0f} may be below 7.5% AGI threshold",
                        reference="IRC Section 213",
                        affected_fields=["deductions.itemized.medical_expenses"],
                    ))
                    idx += 1

        return insights

    def _check_credits(self, tax_return: Any) -> List[CPAInsight]:
        """Check credits for review."""
        insights = []
        idx = 1

        if not tax_return.credits:
            return insights

        credits = tax_return.credits

        # EITC eligibility
        eic = getattr(credits, 'earned_income_credit', 0) or 0
        if eic > 0:
            insights.append(CPAInsight(
                id=f"CRD{idx:03d}",
                category=InsightCategory.COMPLIANCE,
                priority=InsightPriority.HIGH,
                title="EITC Due Diligence Required",
                description=f"Earned Income Credit of ${eic:,.0f} requires Form 8867 due diligence",
                action_required="Complete Form 8867 and document eligibility verification",
                reference="Form 8867",
                affected_fields=["credits.earned_income_credit"],
            ))
            idx += 1

        # Child Tax Credit
        ctc = getattr(credits, 'child_tax_credit', 0) or 0
        if ctc > 0:
            insights.append(CPAInsight(
                id=f"CRD{idx:03d}",
                category=InsightCategory.REVIEW_REQUIRED,
                priority=InsightPriority.MEDIUM,
                title="Child Tax Credit Verification",
                description=f"Child Tax Credit of ${ctc:,.0f} - verify dependent eligibility",
                action_required="Verify dependent information and custody documentation",
                reference="Schedule 8812",
                affected_fields=["credits.child_tax_credit"],
            ))
            idx += 1

        return insights

    def _check_compliance(self, tax_return: Any) -> List[CPAInsight]:
        """Check compliance items."""
        insights = []
        idx = 1

        # Filing status consistency
        if tax_return.taxpayer:
            tp = tax_return.taxpayer
            status = tp.filing_status.value

            dependents = getattr(tp, 'dependents', []) or []

            if status == "head_of_household" and not dependents:
                insights.append(CPAInsight(
                    id=f"CMP{idx:03d}",
                    category=InsightCategory.RISK_FLAG,
                    priority=InsightPriority.CRITICAL,
                    title="Head of Household Without Dependents",
                    description="Head of household status requires a qualifying person",
                    action_required="Verify dependent information or change filing status",
                    reference="IRC Section 2(b)",
                    affected_fields=["taxpayer.filing_status", "taxpayer.dependents"],
                ))
                idx += 1

            if status == "married_joint" and not getattr(tp, 'spouse_ssn', None):
                insights.append(CPAInsight(
                    id=f"CMP{idx:03d}",
                    category=InsightCategory.DATA_QUALITY,
                    priority=InsightPriority.HIGH,
                    title="Missing Spouse SSN",
                    description="Married filing jointly requires spouse SSN",
                    action_required="Obtain spouse SSN before filing",
                    affected_fields=["taxpayer.spouse_ssn"],
                ))
                idx += 1

        return insights

    def _check_optimizations(self, tax_return: Any) -> List[CPAInsight]:
        """Check for optimization opportunities."""
        insights = []
        idx = 1

        # Retirement contributions
        if tax_return.deductions:
            retirement = getattr(tax_return.deductions, 'retirement_contributions', 0) or 0

            if retirement < 23500:  # 2025 401k limit
                agi = float(tax_return.adjusted_gross_income or 0)
                if agi > 75000:
                    insights.append(CPAInsight(
                        id=f"OPT{idx:03d}",
                        category=InsightCategory.OPTIMIZATION,
                        priority=InsightPriority.MEDIUM,
                        title="401(k) Contribution Room",
                        description=f"Current 401(k) contributions leave ${23500 - retirement:,.0f} room for additional tax-deferred savings",
                        reference="IRC Section 402(g)",
                        affected_fields=["deductions.retirement_contributions"],
                    ))
                    idx += 1

        # Standard vs itemized
        if tax_return.deductions:
            deductions = tax_return.deductions
            status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer else "single"

            standard_amounts = {
                "single": 15750, "married_joint": 31500, "married_separate": 15750,
                "head_of_household": 23850, "widow": 31500
            }
            standard = standard_amounts.get(status, 15750)

            if deductions.itemized:
                itemized_total = deductions.itemized.get_total_itemized()

                if itemized_total < standard * 1.1:  # Within 10% of standard
                    insights.append(CPAInsight(
                        id=f"OPT{idx:03d}",
                        category=InsightCategory.OPTIMIZATION,
                        priority=InsightPriority.LOW,
                        title="Itemized vs Standard Review",
                        description=f"Itemized deductions (${itemized_total:,.0f}) are close to standard deduction (${standard:,.0f})",
                        action_required="Verify itemizing provides optimal benefit",
                        affected_fields=["deductions.itemized"],
                    ))
                    idx += 1

        return insights

    def get_review_checklist(self, tax_return: Any) -> List[ReviewChecklist]:
        """
        Generate a review checklist for the return.

        Args:
            tax_return: TaxReturn object

        Returns:
            List of ReviewChecklist items
        """
        checklist = [
            ReviewChecklist(
                id="RC001",
                item="Verify taxpayer identification (SSN, name, address)",
            ),
            ReviewChecklist(
                id="RC002",
                item="Confirm filing status is appropriate",
            ),
            ReviewChecklist(
                id="RC003",
                item="Review all W-2 forms against records",
            ),
            ReviewChecklist(
                id="RC004",
                item="Verify all 1099 forms are included",
            ),
            ReviewChecklist(
                id="RC005",
                item="Review deductions for completeness and accuracy",
            ),
            ReviewChecklist(
                id="RC006",
                item="Verify credit eligibility and calculations",
            ),
            ReviewChecklist(
                id="RC007",
                item="Check for estimated tax payments",
            ),
            ReviewChecklist(
                id="RC008",
                item="Review prior year carryovers",
            ),
            ReviewChecklist(
                id="RC009",
                item="Verify state return consistency",
            ),
            ReviewChecklist(
                id="RC010",
                item="Confirm return is complete for signature",
            ),
        ]

        # Add context-specific items
        if tax_return.income:
            income = tax_return.income

            if getattr(income, 'self_employment_income', 0):
                checklist.append(ReviewChecklist(
                    id="RC011",
                    item="Review Schedule C and self-employment tax calculation",
                ))

            if getattr(income, 'rental_income', 0):
                checklist.append(ReviewChecklist(
                    id="RC012",
                    item="Review Schedule E and depreciation schedules",
                ))

        if tax_return.credits:
            credits = tax_return.credits

            if getattr(credits, 'earned_income_credit', 0):
                checklist.append(ReviewChecklist(
                    id="RC013",
                    item="Complete Form 8867 EITC due diligence",
                ))

        return checklist
