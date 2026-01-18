"""
Scenario Service for What-If Tax Analysis

Provides pre-built scenarios and scenario comparison capabilities
for CPA what-if analysis sessions with clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime
import logging

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

from cpa_panel.analysis.scenario_comparison import (
    ScenarioComparator,
    Scenario,
    ScenarioAdjustment,
    ComparisonResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ScenarioTemplate:
    """Pre-built scenario template."""
    template_id: str
    name: str
    description: str
    category: str
    adjustments: List[Dict[str, Any]]
    variables: List[str]  # Variables that can be customized
    default_values: Dict[str, float]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "adjustments": self.adjustments,
            "variables": self.variables,
            "default_values": self.default_values,
            "notes": self.notes,
        }

    def create_scenario(self, custom_values: Optional[Dict[str, float]] = None) -> Scenario:
        """Create a Scenario from this template with optional customization."""
        values = {**self.default_values, **(custom_values or {})}

        adjustments = []
        for adj_template in self.adjustments:
            value_key = adj_template.get("value_key")
            if value_key and value_key in values:
                value = values[value_key]
            else:
                value = adj_template.get("value", 0)

            adjustments.append(ScenarioAdjustment(
                field=adj_template["field"],
                value=value,
                description=adj_template.get("description"),
            ))

        return Scenario(
            name=self.name,
            adjustments=adjustments,
            description=self.description,
        )


# =============================================================================
# PRE-BUILT SCENARIO TEMPLATES
# =============================================================================

SCENARIO_TEMPLATES: Dict[str, ScenarioTemplate] = {
    # Retirement Contribution Scenarios
    "max_401k": ScenarioTemplate(
        template_id="max_401k",
        name="Max 401(k) Contribution",
        description="Maximize 401(k) contributions to $23,500 (2025 limit)",
        category="retirement",
        adjustments=[
            {
                "field": "401k_contribution",
                "value_key": "contribution_amount",
                "description": "Additional 401(k) contribution",
            }
        ],
        variables=["contribution_amount"],
        default_values={"contribution_amount": 23500},
        notes=[
            "2025 limit is $23,500 (or $31,000 if age 50+)",
            "Reduces AGI dollar-for-dollar",
            "Check employer match to maximize benefit",
        ],
    ),
    "max_ira": ScenarioTemplate(
        template_id="max_ira",
        name="Traditional IRA Contribution",
        description="Add Traditional IRA contribution ($7,000 limit)",
        category="retirement",
        adjustments=[
            {
                "field": "ira_contribution",
                "value_key": "contribution_amount",
                "description": "Traditional IRA contribution",
            }
        ],
        variables=["contribution_amount"],
        default_values={"contribution_amount": 7000},
        notes=[
            "2025 limit is $7,000 (or $8,000 if age 50+)",
            "Deductibility depends on income and employer plan coverage",
            "Can contribute until April 15 for prior year",
        ],
    ),
    "max_hsa": ScenarioTemplate(
        template_id="max_hsa",
        name="Max HSA Contribution",
        description="Maximize HSA contribution (family coverage: $8,550)",
        category="retirement",
        adjustments=[
            {
                "field": "ira_contribution",  # HSA treated similarly for AGI
                "value_key": "contribution_amount",
                "description": "HSA contribution",
            }
        ],
        variables=["contribution_amount"],
        default_values={"contribution_amount": 8550},
        notes=[
            "2025 family limit is $8,550 (individual: $4,300)",
            "Triple tax benefit: deduction + tax-free growth + tax-free withdrawal",
            "Must have HDHP coverage",
        ],
    ),
    "all_retirement": ScenarioTemplate(
        template_id="all_retirement",
        name="Max All Retirement Accounts",
        description="Max out 401(k), IRA, and HSA contributions",
        category="retirement",
        adjustments=[
            {
                "field": "401k_contribution",
                "value": 23500,
                "description": "Max 401(k)",
            },
            {
                "field": "ira_contribution",
                "value": 7000,
                "description": "Max IRA",
            },
        ],
        variables=[],
        default_values={},
        notes=[
            "Combined $30,500+ in tax-deferred savings",
            "Significant AGI reduction",
            "Check contribution room and eligibility",
        ],
    ),

    # Filing Status Scenarios
    "mfj_vs_mfs": ScenarioTemplate(
        template_id="mfj_vs_mfs",
        name="Married Filing Separately",
        description="Compare Married Filing Jointly vs Separately",
        category="filing_status",
        adjustments=[
            {
                "field": "deduction",
                "value": -15750,  # Negative because MFS has lower standard deduction
                "description": "Reduced standard deduction for MFS",
            }
        ],
        variables=[],
        default_values={},
        notes=[
            "MFS may help with income-based student loan payments",
            "MFS may protect from spouse's tax liabilities",
            "Usually results in higher combined tax",
        ],
    ),

    # Charitable Scenarios
    "charitable_bunching": ScenarioTemplate(
        template_id="charitable_bunching",
        name="Charitable Bunching (2-Year)",
        description="Bunch 2 years of charitable giving into one year",
        category="charitable",
        adjustments=[
            {
                "field": "deduction",
                "value_key": "donation_amount",
                "description": "Doubled charitable contribution",
            }
        ],
        variables=["donation_amount"],
        default_values={"donation_amount": 10000},
        notes=[
            "Donate 2 years' worth this year, skip next year",
            "Helps itemize every other year",
            "Consider donor-advised fund for flexibility",
        ],
    ),
    "daf_contribution": ScenarioTemplate(
        template_id="daf_contribution",
        name="Donor-Advised Fund",
        description="Contribute to donor-advised fund for bunched deduction",
        category="charitable",
        adjustments=[
            {
                "field": "deduction",
                "value_key": "contribution_amount",
                "description": "DAF contribution",
            }
        ],
        variables=["contribution_amount"],
        default_values={"contribution_amount": 25000},
        notes=[
            "Full deduction in contribution year",
            "Grant to charities over time",
            "Can contribute appreciated securities",
        ],
    ),

    # Business Deduction Scenarios
    "home_office": ScenarioTemplate(
        template_id="home_office",
        name="Home Office Deduction",
        description="Add home office deduction ($5/sqft, max 300 sqft)",
        category="business",
        adjustments=[
            {
                "field": "deduction",
                "value_key": "deduction_amount",
                "description": "Home office deduction",
            }
        ],
        variables=["deduction_amount"],
        default_values={"deduction_amount": 1500},  # 300 sqft * $5
        notes=[
            "Simplified method: $5/sqft up to 300 sqft ($1,500 max)",
            "Regular method may allow larger deduction",
            "Must use exclusively and regularly for business",
        ],
    ),
    "vehicle_deduction": ScenarioTemplate(
        template_id="vehicle_deduction",
        name="Vehicle Business Use",
        description="Add business vehicle deduction",
        category="business",
        adjustments=[
            {
                "field": "deduction",
                "value_key": "deduction_amount",
                "description": "Vehicle business use deduction",
            }
        ],
        variables=["deduction_amount"],
        default_values={"deduction_amount": 5000},
        notes=[
            "2025 standard mileage rate: $0.70/mile",
            "Track mileage log for documentation",
            "Actual expenses may be larger deduction",
        ],
    ),
    "business_equipment": ScenarioTemplate(
        template_id="business_equipment",
        name="Section 179 Equipment",
        description="Add Section 179 deduction for business equipment",
        category="business",
        adjustments=[
            {
                "field": "deduction",
                "value_key": "equipment_cost",
                "description": "Section 179 equipment deduction",
            }
        ],
        variables=["equipment_cost"],
        default_values={"equipment_cost": 10000},
        notes=[
            "2025 Section 179 limit: $1,220,000",
            "Must be placed in service this year",
            "Deduct full cost instead of depreciating",
        ],
    ),

    # Income Timing Scenarios
    "defer_income": ScenarioTemplate(
        template_id="defer_income",
        name="Defer Income to Next Year",
        description="Defer income to lower current year tax",
        category="income_timing",
        adjustments=[
            {
                "field": "income",
                "value_key": "deferral_amount",
                "description": "Deferred income (negative)",
            }
        ],
        variables=["deferral_amount"],
        default_values={"deferral_amount": -10000},  # Negative = reduction
        notes=[
            "Self-employed: delay billing until January",
            "Consider if lower bracket expected next year",
            "Watch for estimated tax payment requirements",
        ],
    ),
    "accelerate_income": ScenarioTemplate(
        template_id="accelerate_income",
        name="Accelerate Income This Year",
        description="Pull income into current year",
        category="income_timing",
        adjustments=[
            {
                "field": "income",
                "value_key": "acceleration_amount",
                "description": "Accelerated income",
            }
        ],
        variables=["acceleration_amount"],
        default_values={"acceleration_amount": 10000},
        notes=[
            "May help if higher bracket expected next year",
            "Can trigger earlier if low-income year",
            "Consider tax rate trends",
        ],
    ),

    # Additional Income Scenarios
    "side_income_10k": ScenarioTemplate(
        template_id="side_income_10k",
        name="$10K Side Income",
        description="See impact of earning $10,000 additional income",
        category="income",
        adjustments=[
            {
                "field": "income",
                "value": 10000,
                "description": "Additional $10,000 income",
            }
        ],
        variables=[],
        default_values={},
        notes=[
            "See marginal rate impact",
            "May affect credit eligibility",
            "Consider withholding adjustments",
        ],
    ),
    "side_income_25k": ScenarioTemplate(
        template_id="side_income_25k",
        name="$25K Side Income",
        description="See impact of earning $25,000 additional income",
        category="income",
        adjustments=[
            {
                "field": "income",
                "value": 25000,
                "description": "Additional $25,000 income",
            }
        ],
        variables=[],
        default_values={},
        notes=[
            "May push into higher bracket",
            "Estimated payments likely needed",
            "Consider entity structure if self-employment",
        ],
    ),

    # Education Scenarios
    "education_credits": ScenarioTemplate(
        template_id="education_credits",
        name="Education Expenses",
        description="Add qualified education expenses for credits",
        category="education",
        adjustments=[
            {
                "field": "credit",
                "value_key": "credit_amount",
                "description": "American Opportunity Credit (or LLC)",
            }
        ],
        variables=["credit_amount"],
        default_values={"credit_amount": 2500},
        notes=[
            "AOTC max: $2,500/student (40% refundable)",
            "LLC max: $2,000/return",
            "Income limits apply",
        ],
    ),

    # Energy Scenarios
    "solar_installation": ScenarioTemplate(
        template_id="solar_installation",
        name="Solar Panel Installation",
        description="30% Residential Clean Energy Credit for solar",
        category="energy",
        adjustments=[
            {
                "field": "credit",
                "value_key": "credit_amount",
                "description": "Residential Clean Energy Credit",
            }
        ],
        variables=["credit_amount", "installation_cost"],
        default_values={"credit_amount": 7500, "installation_cost": 25000},
        notes=[
            "30% of installation cost",
            "No income limit",
            "Unused credit can carry forward",
        ],
    ),
    "ev_purchase": ScenarioTemplate(
        template_id="ev_purchase",
        name="Electric Vehicle Credit",
        description="Clean Vehicle Credit for new EV purchase",
        category="energy",
        adjustments=[
            {
                "field": "credit",
                "value_key": "credit_amount",
                "description": "Clean Vehicle Credit",
            }
        ],
        variables=["credit_amount"],
        default_values={"credit_amount": 7500},
        notes=[
            "New EV: up to $7,500",
            "Used EV: up to $4,000",
            "Income and price limits apply",
            "Can be taken at point of sale",
        ],
    ),
}


class ScenarioService:
    """
    Service for scenario-based what-if tax analysis.

    Provides:
    - Pre-built scenario templates
    - Custom scenario creation
    - Multi-scenario comparison
    - Impact visualization data
    """

    def __init__(self):
        """Initialize scenario service."""
        self.comparator = ScenarioComparator()
        self.templates = SCENARIO_TEMPLATES

    def get_tax_return(self, session_id: str) -> Optional["TaxReturn"]:
        """Get tax return from session in optimizer-compatible format."""
        try:
            from cpa_panel.adapters import TaxReturnAdapter
            adapter = TaxReturnAdapter()
            # Use optimizer-compatible method for scenario analysis
            return adapter.get_optimizer_compatible_return(session_id)
        except Exception as e:
            logger.error(f"Failed to get tax return for {session_id}: {e}")
            return None

    def get_templates(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available scenario templates.

        Args:
            category: Optional category filter

        Returns:
            List of template dictionaries
        """
        templates = []
        for template in self.templates.values():
            if category is None or template.category == category:
                templates.append(template.to_dict())

        return templates

    def get_template_categories(self) -> List[Dict[str, Any]]:
        """Get list of template categories with counts."""
        categories = {}
        for template in self.templates.values():
            cat = template.category
            if cat not in categories:
                categories[cat] = {
                    "category": cat,
                    "count": 0,
                    "templates": [],
                }
            categories[cat]["count"] += 1
            categories[cat]["templates"].append(template.template_id)

        return list(categories.values())

    def compare_scenarios(
        self,
        session_id: str,
        scenario_configs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare multiple scenarios against base case.

        Args:
            session_id: Client session ID
            scenario_configs: List of scenario configurations, each with:
                - template_id: Use a pre-built template
                - OR name, adjustments: Custom scenario

        Returns:
            Comparison result with all scenarios
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        # Build scenarios from configs
        scenarios = []
        for config in scenario_configs[:4]:  # Limit to 4
            scenario = self._build_scenario(config)
            if scenario:
                scenarios.append(scenario)

        if not scenarios:
            return {
                "success": False,
                "error": "No valid scenarios provided",
            }

        try:
            result = self.comparator.compare(
                session_id=session_id,
                tax_return=tax_return,
                scenarios=scenarios,
            )

            return {
                "success": True,
                **result.to_dict(),
            }

        except Exception as e:
            logger.error(f"Scenario comparison failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def compare_from_templates(
        self,
        session_id: str,
        template_ids: List[str],
        custom_values: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Compare scenarios using pre-built templates.

        Args:
            session_id: Client session ID
            template_ids: List of template IDs to compare
            custom_values: Optional {template_id: {variable: value}} overrides

        Returns:
            Comparison result
        """
        custom_values = custom_values or {}

        scenarios = []
        for template_id in template_ids[:4]:
            template = self.templates.get(template_id)
            if template:
                values = custom_values.get(template_id)
                scenario = template.create_scenario(values)
                scenarios.append(scenario)

        if not scenarios:
            return {
                "success": False,
                "error": "No valid templates found",
            }

        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        try:
            result = self.comparator.compare(
                session_id=session_id,
                tax_return=tax_return,
                scenarios=scenarios,
            )

            return {
                "success": True,
                **result.to_dict(),
            }

        except Exception as e:
            logger.error(f"Template comparison failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def quick_compare(
        self,
        session_id: str,
        adjustments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Quick comparison without full tax calculation.

        Uses marginal rate approximation for fast what-if.

        Args:
            session_id: Client session ID
            adjustments: List of {field, value} adjustments

        Returns:
            Quick comparison result
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        try:
            base_liability = float(tax_return.tax_liability or 0)
            taxable_income = float(tax_return.taxable_income or 0)
            filing_status = getattr(tax_return, "filing_status", "single") or "single"

            # Get marginal rate based on filing status
            marginal_rate = self._get_marginal_rate(taxable_income, filing_status)

            result = self.comparator.quick_compare(
                base_liability=base_liability,
                marginal_rate=marginal_rate,
                adjustments=adjustments,
            )

            return {
                "success": True,
                "session_id": session_id,
                **result,
            }

        except Exception as e:
            logger.error(f"Quick compare failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_common_scenarios(self, session_id: str) -> Dict[str, Any]:
        """
        Get common/suggested scenarios based on client profile.

        Analyzes the tax return to suggest relevant scenarios.
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        try:
            scenarios = self.comparator.create_common_scenarios(tax_return)

            return {
                "success": True,
                "session_id": session_id,
                "suggested_scenarios": [s.to_dict() for s in scenarios],
                "total_scenarios": len(scenarios),
            }

        except Exception as e:
            logger.error(f"Common scenarios failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _build_scenario(self, config: Dict[str, Any]) -> Optional[Scenario]:
        """Build a scenario from configuration."""
        # Template-based
        template_id = config.get("template_id")
        if template_id and template_id in self.templates:
            template = self.templates[template_id]
            custom_values = config.get("values")
            return template.create_scenario(custom_values)

        # Custom scenario
        name = config.get("name")
        adjustments_data = config.get("adjustments", [])

        if name and adjustments_data:
            adjustments = [
                ScenarioAdjustment(
                    field=a.get("field", ""),
                    value=float(a.get("value", 0)),
                    description=a.get("description"),
                )
                for a in adjustments_data
            ]
            return Scenario(
                name=name,
                adjustments=adjustments,
                description=config.get("description"),
            )

        return None

    def _get_marginal_rate(
        self, taxable_income: float, filing_status: str = "single"
    ) -> float:
        """Get marginal tax rate based on filing status (2025 brackets)."""
        # 2025 Tax Brackets by filing status
        brackets_by_status = {
            "single": [
                (11925, 0.10),
                (48475, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250500, 0.32),
                (626350, 0.35),
                (float("inf"), 0.37),
            ],
            "married_filing_jointly": [
                (23850, 0.10),
                (96950, 0.12),
                (206700, 0.22),
                (394600, 0.24),
                (501000, 0.32),
                (751600, 0.35),
                (float("inf"), 0.37),
            ],
            "married_filing_separately": [
                (11925, 0.10),
                (48475, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250500, 0.32),
                (375800, 0.35),
                (float("inf"), 0.37),
            ],
            "head_of_household": [
                (17000, 0.10),
                (64850, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250500, 0.32),
                (626350, 0.35),
                (float("inf"), 0.37),
            ],
            "qualifying_surviving_spouse": [
                (23850, 0.10),
                (96950, 0.12),
                (206700, 0.22),
                (394600, 0.24),
                (501000, 0.32),
                (751600, 0.35),
                (float("inf"), 0.37),
            ],
        }

        # Normalize filing status
        status_key = filing_status.lower().replace(" ", "_") if filing_status else "single"
        brackets = brackets_by_status.get(status_key, brackets_by_status["single"])

        for threshold, rate in brackets:
            if taxable_income <= threshold:
                return rate
        return 0.37


# Singleton instance
_scenario_service: Optional[ScenarioService] = None


def get_scenario_service() -> ScenarioService:
    """Get or create singleton scenario service."""
    global _scenario_service
    if _scenario_service is None:
        _scenario_service = ScenarioService()
    return _scenario_service
