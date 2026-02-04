"""
Scenario Comparison for "What If" Analysis

CLIENT AHA MOMENT: See how different choices affect taxes side-by-side.

Enables comparison of multiple scenarios to help clients make
informed decisions about tax planning strategies.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)


@dataclass
class ScenarioAdjustment:
    """A single adjustment in a scenario."""
    field: str
    value: float
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "value": self.value,
            "description": self.description,
        }


@dataclass
class Scenario:
    """A tax scenario for comparison."""
    name: str
    adjustments: List[ScenarioAdjustment] = field(default_factory=list)
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "adjustments": [a.to_dict() for a in self.adjustments],
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scenario":
        """Create from dictionary."""
        adjustments = [
            ScenarioAdjustment(
                field=a.get("field", ""),
                value=float(a.get("value", 0)),
                description=a.get("description"),
            )
            for a in data.get("adjustments", [])
        ]
        return cls(
            name=data.get("name", "Scenario"),
            adjustments=adjustments,
            description=data.get("description"),
        )


@dataclass
class ScenarioMetrics:
    """Tax metrics for a scenario."""
    adjusted_gross_income: float = 0
    taxable_income: float = 0
    tax_liability: float = 0
    refund_or_owed: float = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "adjusted_gross_income": float(money(self.adjusted_gross_income)),
            "taxable_income": float(money(self.taxable_income)),
            "tax_liability": float(money(self.tax_liability)),
            "refund_or_owed": float(money(self.refund_or_owed)),
        }


@dataclass
class ScenarioDelta:
    """Delta from base case."""
    agi: float = 0
    taxable: float = 0
    tax: float = 0
    refund: float = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "agi": float(money(self.agi)),
            "taxable": float(money(self.taxable)),
            "tax": float(money(self.tax)),
            "refund": float(money(self.refund)),
        }


@dataclass
class ScenarioResult:
    """Result for a single scenario."""
    name: str
    metrics: ScenarioMetrics
    delta_from_base: ScenarioDelta
    adjustments: List[ScenarioAdjustment]
    is_base: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            **self.metrics.to_dict(),
            "adjustments": [a.to_dict() for a in self.adjustments],
            "is_base": self.is_base,
        }
        if not self.is_base:
            result["delta_from_base"] = self.delta_from_base.to_dict()
        return result


@dataclass
class ComparisonSummary:
    """Summary of scenario comparison."""
    best_scenario: str
    best_tax: float
    worst_scenario: str
    worst_tax: float
    max_savings: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "best_scenario": self.best_scenario,
            "best_tax": float(money(self.best_tax)),
            "worst_scenario": self.worst_scenario,
            "worst_tax": float(money(self.worst_tax)),
            "max_savings": float(money(self.max_savings)),
        }


@dataclass
class ComparisonResult:
    """Complete result of scenario comparison."""
    session_id: str
    scenarios: List[ScenarioResult]
    comparison: ComparisonSummary
    marginal_rate_used: float
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "comparison": self.comparison.to_dict(),
            "marginal_rate_used": self.marginal_rate_used,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "visualization": {
                "type": "comparison_chart",
                "metrics": ["tax_liability", "refund_or_owed"],
                "scenarios": [s.name for s in self.scenarios],
            }
        }


class ScenarioComparator:
    """
    Compares multiple tax scenarios side-by-side.

    CLIENT AHA MOMENT: "What if" analysis to help clients understand
    how different choices affect their taxes.
    """

    # Adjustment field mappings
    AGI_AFFECTING = ["income", "wages", "additional_income", "ira_contribution", "401k_contribution"]
    TAXABLE_AFFECTING = ["deduction", "additional_deduction"]
    CREDIT_AFFECTING = ["credit", "additional_credit"]

    def __init__(self):
        """Initialize scenario comparator."""
        pass

    def _get_marginal_rate(self, taxable_income: float) -> float:
        """Get marginal tax rate."""
        brackets = [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37),
        ]
        for threshold, rate in brackets:
            if taxable_income <= threshold:
                return rate
        return 0.37

    def compare(
        self,
        session_id: str,
        tax_return: Any,
        scenarios: List[Scenario],
    ) -> ComparisonResult:
        """
        Compare multiple scenarios against the base case.

        Args:
            session_id: Session/return identifier
            tax_return: Current TaxReturn object
            scenarios: List of scenarios to compare

        Returns:
            ComparisonResult with all scenarios compared
        """
        # Base case from current return
        base_agi = float(tax_return.adjusted_gross_income or 0)
        base_taxable = float(tax_return.taxable_income or 0)
        base_liability = float(tax_return.tax_liability or 0)
        base_refund = float(tax_return.refund_or_owed or 0)

        marginal_rate = self._get_marginal_rate(base_taxable)

        # Create base case result
        base_result = ScenarioResult(
            name="Current",
            metrics=ScenarioMetrics(
                adjusted_gross_income=base_agi,
                taxable_income=base_taxable,
                tax_liability=base_liability,
                refund_or_owed=base_refund,
            ),
            delta_from_base=ScenarioDelta(),
            adjustments=[],
            is_base=True,
        )

        results = [base_result]

        # Calculate each scenario
        for scenario in scenarios[:4]:  # Limit to 4 custom scenarios
            result = self._calculate_scenario(
                scenario=scenario,
                base_agi=base_agi,
                base_taxable=base_taxable,
                base_liability=base_liability,
                base_refund=base_refund,
                marginal_rate=marginal_rate,
            )
            results.append(result)

        # Find best and worst scenarios
        best = min(results, key=lambda r: r.metrics.tax_liability)
        worst = max(results, key=lambda r: r.metrics.tax_liability)

        comparison = ComparisonSummary(
            best_scenario=best.name,
            best_tax=best.metrics.tax_liability,
            worst_scenario=worst.name,
            worst_tax=worst.metrics.tax_liability,
            max_savings=worst.metrics.tax_liability - best.metrics.tax_liability,
        )

        return ComparisonResult(
            session_id=session_id,
            scenarios=results,
            comparison=comparison,
            marginal_rate_used=marginal_rate,
        )

    def _calculate_scenario(
        self,
        scenario: Scenario,
        base_agi: float,
        base_taxable: float,
        base_liability: float,
        base_refund: float,
        marginal_rate: float,
    ) -> ScenarioResult:
        """Calculate a single scenario."""
        agi_delta = 0
        taxable_delta = 0
        credit_delta = 0

        for adj in scenario.adjustments:
            field = adj.field.lower()
            value = adj.value

            if field in ["income", "wages", "additional_income"]:
                agi_delta += value
                taxable_delta += value
            elif field in ["ira_contribution", "401k_contribution"]:
                agi_delta -= value
                taxable_delta -= value
            elif field in ["deduction", "additional_deduction"]:
                taxable_delta -= value
            elif field in ["credit", "additional_credit"]:
                credit_delta += value

        # Calculate tax change
        tax_change = taxable_delta * marginal_rate - credit_delta

        new_agi = base_agi + agi_delta
        new_taxable = base_taxable + taxable_delta
        new_liability = base_liability + tax_change
        new_refund = base_refund - tax_change

        return ScenarioResult(
            name=scenario.name,
            metrics=ScenarioMetrics(
                adjusted_gross_income=new_agi,
                taxable_income=new_taxable,
                tax_liability=new_liability,
                refund_or_owed=new_refund,
            ),
            delta_from_base=ScenarioDelta(
                agi=agi_delta,
                taxable=taxable_delta,
                tax=tax_change,
                refund=-tax_change,
            ),
            adjustments=scenario.adjustments,
            is_base=False,
        )

    def create_common_scenarios(self, tax_return: Any) -> List[Scenario]:
        """
        Create common comparison scenarios.

        Args:
            tax_return: Current TaxReturn object

        Returns:
            List of common scenarios to consider
        """
        scenarios = []

        # Scenario: Max out 401k
        current_contribution = 0
        if tax_return.deductions and hasattr(tax_return.deductions, 'retirement_contributions'):
            current_contribution = tax_return.deductions.retirement_contributions or 0

        max_401k = 23500  # 2025 limit
        if current_contribution < max_401k:
            scenarios.append(Scenario(
                name="Max 401(k)",
                adjustments=[
                    ScenarioAdjustment(
                        field="401k_contribution",
                        value=max_401k - current_contribution,
                        description="Contribute max to 401(k)",
                    )
                ],
                description="Max out 401(k) contributions at $23,500",
            ))

        # Scenario: Add IRA contribution
        max_ira = 7000  # 2025 limit
        scenarios.append(Scenario(
            name="Add IRA",
            adjustments=[
                ScenarioAdjustment(
                    field="ira_contribution",
                    value=max_ira,
                    description="Contribute to Traditional IRA",
                )
            ],
            description="Contribute $7,000 to Traditional IRA",
        ))

        # Scenario: Charitable giving
        agi = float(tax_return.adjusted_gross_income or 0)
        if agi > 50000:
            charity_amount = round(agi * 0.02, -2)  # 2% of AGI, rounded
            scenarios.append(Scenario(
                name="Charitable Giving",
                adjustments=[
                    ScenarioAdjustment(
                        field="deduction",
                        value=charity_amount,
                        description=f"Donate ${charity_amount:,.0f} to charity",
                    )
                ],
                description=f"Make ${charity_amount:,.0f} in charitable donations",
            ))

        # Scenario: Side income
        scenarios.append(Scenario(
            name="+$10K Income",
            adjustments=[
                ScenarioAdjustment(
                    field="income",
                    value=10000,
                    description="Additional $10K income",
                )
            ],
            description="See impact of earning $10,000 more",
        ))

        return scenarios[:4]

    def quick_compare(
        self,
        base_liability: float,
        marginal_rate: float,
        adjustments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Quick comparison without full tax return.

        Args:
            base_liability: Current tax liability
            marginal_rate: Marginal tax rate
            adjustments: List of adjustment dicts

        Returns:
            Quick comparison result
        """
        tax_change = 0

        for adj in adjustments:
            field = adj.get("field", "").lower()
            value = float(adj.get("value", 0))

            if field in ["income", "wages"]:
                tax_change += value * marginal_rate
            elif field in ["deduction", "ira_contribution", "401k_contribution"]:
                tax_change -= value * marginal_rate
            elif field in ["credit"]:
                tax_change -= value

        return {
            "base_liability": float(money(base_liability)),
            "estimated_new_liability": float(money(base_liability + tax_change)),
            "estimated_change": float(money(tax_change)),
            "is_beneficial": tax_change < 0,
            "savings": float(money(-tax_change)) if tax_change < 0 else 0,
        }
