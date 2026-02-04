"""Entity Structure Optimizer.

Compares tax implications of different business entity structures:
- Sole Proprietorship (Schedule C)
- Single-Member LLC (default: Schedule C, or elect S-Corp)
- S-Corporation (Form 1120-S + W-2 + K-1)

Key factors analyzed:
- Self-employment tax savings
- Reasonable salary determination
- QBI (Section 199A) deduction impact
- State-specific considerations
- Total tax comparison

Reference: IRS Publication 334, 541, 542
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal


class EntityType(Enum):
    """Business entity types for comparison."""
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    SINGLE_MEMBER_LLC = "single_member_llc"
    S_CORPORATION = "s_corporation"
    PARTNERSHIP = "partnership"
    C_CORPORATION = "c_corporation"


@dataclass
class EntityAnalysis:
    """Analysis result for a single entity structure."""
    entity_type: EntityType
    entity_name: str

    # Income breakdown
    gross_revenue: float
    business_expenses: float
    net_business_income: float

    # S-Corp specific
    owner_salary: float = 0.0
    k1_distribution: float = 0.0

    # Tax components
    self_employment_tax: float = 0.0
    income_tax_on_business: float = 0.0
    payroll_taxes: float = 0.0  # Employer portion for S-Corp

    # Deductions
    se_tax_deduction: float = 0.0  # 50% of SE tax
    qbi_deduction: float = 0.0

    # Totals
    total_business_tax: float = 0.0
    effective_tax_rate: float = 0.0

    # Additional costs
    formation_cost: float = 0.0
    annual_compliance_cost: float = 0.0
    payroll_service_cost: float = 0.0

    # Net comparison
    total_annual_cost: float = 0.0  # Tax + compliance costs

    # Flags
    is_recommended: bool = False
    recommendation_notes: List[str] = field(default_factory=list)


@dataclass
class ReasonableSalaryAnalysis:
    """Analysis of reasonable salary for S-Corp."""
    recommended_salary: float
    salary_range_low: float
    salary_range_high: float
    methodology: str
    factors_considered: List[str] = field(default_factory=list)
    irs_risk_level: str = "low"  # low, medium, high
    notes: List[str] = field(default_factory=list)


@dataclass
class EntityComparisonResult:
    """Complete comparison of entity structures."""
    analyses: Dict[str, EntityAnalysis]
    recommended_entity: EntityType
    current_entity: Optional[EntityType]

    # Savings summary
    max_annual_savings: float
    savings_vs_current: float

    # Reasonable salary analysis (for S-Corp)
    salary_analysis: Optional[ReasonableSalaryAnalysis]

    # Recommendation details
    recommendation_reason: str
    confidence_score: float  # 0-100
    breakeven_revenue: float  # Revenue where S-Corp becomes beneficial

    # Considerations
    warnings: List[str] = field(default_factory=list)
    considerations: List[str] = field(default_factory=list)

    # Multi-year projection
    five_year_savings: float = 0.0


class EntityStructureOptimizer:
    """
    Analyzes and compares business entity structures for tax optimization.

    Primary use case: Should a business owner elect S-Corp status?

    Key S-Corp benefits:
    - Self-employment tax savings on distributions (not salary)
    - May reduce overall tax burden for profitable businesses

    Key S-Corp costs:
    - Reasonable salary requirement (subject to payroll taxes)
    - Additional compliance (payroll, Form 1120-S, etc.)
    - State fees and franchise taxes

    Rule of thumb: S-Corp beneficial when net income > $40-50k
    """

    # 2025 Tax Rates
    SE_TAX_RATE = 0.153  # 12.4% SS + 2.9% Medicare
    SE_NET_EARNINGS_FACTOR = 0.9235  # 92.35%
    SS_WAGE_BASE_2025 = 176100.0
    MEDICARE_RATE = 0.029
    SS_RATE = 0.124
    ADDITIONAL_MEDICARE_RATE = 0.009
    ADDITIONAL_MEDICARE_THRESHOLD = 200000.0  # Single filer

    # QBI deduction
    QBI_DEDUCTION_RATE = 0.20

    # S-Corp compliance costs (estimates)
    SCORP_FORMATION_COST = 500.0  # One-time
    SCORP_ANNUAL_COMPLIANCE = 1500.0  # Tax return, minutes, etc.
    PAYROLL_SERVICE_ANNUAL = 600.0  # Payroll processing

    def __init__(
        self,
        filing_status: str = "single",
        other_income: float = 0.0,
        state: Optional[str] = None
    ):
        """
        Initialize the optimizer.

        Args:
            filing_status: Taxpayer filing status
            other_income: Other taxable income (W-2, investments, etc.)
            state: State of residence for state tax considerations
        """
        self.filing_status = filing_status
        self.other_income = other_income
        self.state = state

    def compare_structures(
        self,
        gross_revenue: float,
        business_expenses: float,
        owner_salary: Optional[float] = None,
        current_entity: Optional[EntityType] = None
    ) -> EntityComparisonResult:
        """
        Compare tax implications of different entity structures.

        Args:
            gross_revenue: Total business revenue
            business_expenses: Total deductible business expenses
            owner_salary: Optional fixed salary for S-Corp (otherwise calculated)
            current_entity: Current entity type (for comparison)

        Returns:
            EntityComparisonResult with full analysis
        """
        net_income = gross_revenue - business_expenses

        if net_income <= 0:
            return self._create_no_income_result(gross_revenue, business_expenses)

        # Calculate reasonable salary for S-Corp
        salary_analysis = self.calculate_reasonable_salary(
            net_income, gross_revenue, owner_salary
        )
        scorp_salary = salary_analysis.recommended_salary

        # Analyze each entity type
        analyses = {}

        # Sole Proprietorship
        sole_prop = self._analyze_sole_proprietorship(
            gross_revenue, business_expenses, net_income
        )
        analyses[EntityType.SOLE_PROPRIETORSHIP.value] = sole_prop

        # Single-Member LLC (taxed as Sole Prop by default)
        llc = self._analyze_single_member_llc(
            gross_revenue, business_expenses, net_income
        )
        analyses[EntityType.SINGLE_MEMBER_LLC.value] = llc

        # S-Corporation
        scorp = self._analyze_s_corporation(
            gross_revenue, business_expenses, net_income, scorp_salary
        )
        analyses[EntityType.S_CORPORATION.value] = scorp

        # Find optimal entity
        recommended = self._determine_recommended_entity(analyses, net_income)

        # Mark recommended
        for key, analysis in analyses.items():
            if EntityType(key) == recommended:
                analysis.is_recommended = True

        # Calculate savings
        max_savings = self._calculate_max_savings(analyses)
        savings_vs_current = self._calculate_savings_vs_current(
            analyses, current_entity
        )

        # Calculate breakeven point
        breakeven = self._calculate_breakeven_revenue(business_expenses)

        # Generate warnings and considerations
        warnings = self._generate_warnings(net_income, scorp_salary, recommended)
        considerations = self._generate_considerations(
            net_income, recommended, current_entity
        )

        # Calculate 5-year projection
        five_year = max_savings * 5 if recommended == EntityType.S_CORPORATION else 0

        return EntityComparisonResult(
            analyses=analyses,
            recommended_entity=recommended,
            current_entity=current_entity,
            max_annual_savings=max_savings,
            savings_vs_current=savings_vs_current,
            salary_analysis=salary_analysis,
            recommendation_reason=self._generate_recommendation_reason(
                recommended, analyses, net_income
            ),
            confidence_score=self._calculate_confidence(analyses, net_income),
            breakeven_revenue=breakeven,
            warnings=warnings,
            considerations=considerations,
            five_year_savings=five_year,
        )

    def calculate_reasonable_salary(
        self,
        net_income: float,
        gross_revenue: float,
        fixed_salary: Optional[float] = None
    ) -> ReasonableSalaryAnalysis:
        """
        Calculate reasonable salary for S-Corp shareholder-employee.

        IRS requires "reasonable compensation" for shareholders who provide
        services. Factors include:
        - Industry standards
        - Training and experience
        - Duties and responsibilities
        - Time devoted to business
        - Comparable salaries

        Args:
            net_income: Net business income
            gross_revenue: Gross business revenue
            fixed_salary: Optional fixed salary to use

        Returns:
            ReasonableSalaryAnalysis with recommendation
        """
        if fixed_salary is not None:
            return ReasonableSalaryAnalysis(
                recommended_salary=fixed_salary,
                salary_range_low=fixed_salary * 0.9,
                salary_range_high=fixed_salary * 1.1,
                methodology="User-specified salary",
                factors_considered=["User input"],
                irs_risk_level="unknown",
                notes=["Salary was manually specified - verify it meets reasonable compensation standards"]
            )

        # Industry-agnostic calculation based on net income
        # Conservative: 50-70% of net income as salary
        # More aggressive: 40-60% of net income as salary

        factors = []

        # Base calculation: percentage of net income
        if net_income < 50000:
            # Lower income: higher salary percentage needed
            salary_pct = 0.70
            factors.append("Lower net income requires higher salary percentage")
        elif net_income < 100000:
            salary_pct = 0.60
            factors.append("Moderate net income allows 60% salary allocation")
        elif net_income < 200000:
            salary_pct = 0.55
            factors.append("Higher net income allows 55% salary allocation")
        else:
            salary_pct = 0.50
            factors.append("High net income allows 50% salary allocation")

        base_salary = net_income * salary_pct

        # Apply minimums based on reasonable market rates
        # Assume minimum $40k for full-time business owner
        minimum_salary = 40000.0 if net_income > 60000 else net_income * 0.80
        factors.append(f"Minimum reasonable salary floor: ${minimum_salary:,.0f}")

        # Cap at SS wage base (above this, less SE tax benefit)
        maximum_salary = min(net_income * 0.85, self.SS_WAGE_BASE_2025)
        factors.append(f"Maximum reasonable salary cap: ${maximum_salary:,.0f}")

        # Final recommended salary
        recommended = max(minimum_salary, min(base_salary, maximum_salary))

        # Ensure salary doesn't exceed net income
        recommended = min(recommended, net_income * 0.95)

        # Calculate range
        range_low = recommended * 0.85
        range_high = min(recommended * 1.15, net_income * 0.90)

        # Assess IRS risk
        salary_ratio = recommended / net_income if net_income > 0 else 0
        if salary_ratio >= 0.60:
            risk_level = "low"
        elif salary_ratio >= 0.45:
            risk_level = "medium"
        else:
            risk_level = "high"

        notes = []
        if risk_level == "high":
            notes.append("WARNING: Low salary ratio may attract IRS scrutiny")
            notes.append("Consider increasing salary or documenting justification")
        if recommended < 50000 and net_income > 100000:
            notes.append("Salary seems low relative to business income - review industry standards")

        return ReasonableSalaryAnalysis(
            recommended_salary=float(money(recommended)),
            salary_range_low=float(money(range_low)),
            salary_range_high=float(money(range_high)),
            methodology="Percentage of net income with market-rate adjustments",
            factors_considered=factors,
            irs_risk_level=risk_level,
            notes=notes,
        )

    def calculate_scorp_savings(
        self,
        net_business_income: float,
        reasonable_salary: float
    ) -> Dict[str, Any]:
        """
        Calculate SE tax savings from S-Corp election.

        Sole Prop: SE tax on entire net income
        S-Corp: SE tax (as payroll tax) only on salary

        Args:
            net_business_income: Net profit from business
            reasonable_salary: S-Corp shareholder salary

        Returns:
            Dict with savings breakdown
        """
        # Sole Proprietorship SE Tax
        se_earnings = net_business_income * self.SE_NET_EARNINGS_FACTOR
        sole_prop_se_tax = self._calculate_se_tax(se_earnings)
        sole_prop_se_deduction = sole_prop_se_tax / 2

        # S-Corp payroll taxes (employer + employee portions)
        # Employee pays: 6.2% SS + 1.45% Medicare
        # Employer pays: 6.2% SS + 1.45% Medicare
        # Total: 15.3% on salary (same as SE tax rate)

        ss_wages = min(reasonable_salary, self.SS_WAGE_BASE_2025)
        employer_ss = ss_wages * 0.062
        employer_medicare = reasonable_salary * 0.0145
        employer_payroll = employer_ss + employer_medicare

        employee_ss = ss_wages * 0.062
        employee_medicare = reasonable_salary * 0.0145
        employee_payroll = employee_ss + employee_medicare

        total_payroll_tax = employer_payroll + employee_payroll

        # K-1 distribution (no SE tax)
        k1_distribution = net_business_income - reasonable_salary - employer_payroll

        # Calculate savings
        se_tax_savings = sole_prop_se_tax - total_payroll_tax

        # QBI impact comparison
        # Sole Prop: QBI = net income - 50% SE tax deduction
        sole_prop_qbi_base = net_business_income - sole_prop_se_deduction
        sole_prop_qbi = sole_prop_qbi_base * self.QBI_DEDUCTION_RATE

        # S-Corp: QBI = K-1 distribution (salary not included in QBI)
        # But W-2 wages factor into the QBI limitation for high earners
        scorp_qbi = max(0, k1_distribution) * self.QBI_DEDUCTION_RATE

        qbi_difference = sole_prop_qbi - scorp_qbi

        return {
            "sole_prop_se_tax": float(money(sole_prop_se_tax)),
            "sole_prop_se_deduction": float(money(sole_prop_se_deduction)),
            "sole_prop_qbi_deduction": float(money(sole_prop_qbi)),
            "scorp_employer_payroll": float(money(employer_payroll)),
            "scorp_employee_payroll": float(money(employee_payroll)),
            "scorp_total_payroll": float(money(total_payroll_tax)),
            "scorp_k1_distribution": float(money(k1_distribution)),
            "scorp_qbi_deduction": float(money(scorp_qbi)),
            "se_tax_savings": float(money(se_tax_savings)),
            "qbi_difference": float(money(qbi_difference)),
            "net_tax_savings": float(money(se_tax_savings - qbi_difference * 0.22)),  # Approx tax on QBI diff
            "reasonable_salary_used": reasonable_salary,
        }

    def _calculate_se_tax(self, se_earnings: float) -> float:
        """Calculate self-employment tax on SE earnings."""
        # Social Security (12.4%) on earnings up to wage base
        ss_taxable = min(se_earnings, self.SS_WAGE_BASE_2025)
        ss_tax = ss_taxable * self.SS_RATE

        # Medicare (2.9%) on all earnings
        medicare_tax = se_earnings * self.MEDICARE_RATE

        # Additional Medicare (0.9%) on earnings over threshold
        additional_medicare = max(0, se_earnings - self.ADDITIONAL_MEDICARE_THRESHOLD) * self.ADDITIONAL_MEDICARE_RATE

        return ss_tax + medicare_tax + additional_medicare

    def _analyze_sole_proprietorship(
        self,
        gross_revenue: float,
        expenses: float,
        net_income: float
    ) -> EntityAnalysis:
        """Analyze tax burden for Sole Proprietorship."""
        # Self-employment tax
        se_earnings = net_income * self.SE_NET_EARNINGS_FACTOR
        se_tax = self._calculate_se_tax(se_earnings)
        se_deduction = se_tax / 2

        # QBI deduction (simplified - not accounting for all limitations)
        qbi_base = net_income - se_deduction
        qbi_deduction = qbi_base * self.QBI_DEDUCTION_RATE

        # Taxable business income (after SE deduction and QBI)
        taxable_business = net_income - se_deduction - qbi_deduction

        # Calculate income tax using progressive brackets
        total_taxable = taxable_business + self.other_income
        total_income_tax = self._calculate_progressive_tax(total_taxable)
        # Subtract tax on other income to get just business portion
        other_income_tax = self._calculate_progressive_tax(self.other_income)
        income_tax = total_income_tax - other_income_tax

        total_tax = se_tax + income_tax

        return EntityAnalysis(
            entity_type=EntityType.SOLE_PROPRIETORSHIP,
            entity_name="Sole Proprietorship (Schedule C)",
            gross_revenue=gross_revenue,
            business_expenses=expenses,
            net_business_income=net_income,
            self_employment_tax=float(money(se_tax)),
            income_tax_on_business=float(money(income_tax)),
            se_tax_deduction=float(money(se_deduction)),
            qbi_deduction=float(money(qbi_deduction)),
            total_business_tax=float(money(total_tax)),
            effective_tax_rate=float(money(total_tax / net_income * 100)) if net_income > 0 else 0,
            formation_cost=0.0,
            annual_compliance_cost=200.0,  # Basic Schedule C
            total_annual_cost=float(money(total_tax + 200)),
            recommendation_notes=[
                "Simplest structure with minimal compliance",
                "All net income subject to self-employment tax",
                "No liability protection",
            ],
        )

    def _analyze_single_member_llc(
        self,
        gross_revenue: float,
        expenses: float,
        net_income: float
    ) -> EntityAnalysis:
        """Analyze tax burden for Single-Member LLC (taxed as disregarded entity)."""
        # Tax calculation same as Sole Prop (disregarded entity)
        se_earnings = net_income * self.SE_NET_EARNINGS_FACTOR
        se_tax = self._calculate_se_tax(se_earnings)
        se_deduction = se_tax / 2

        qbi_base = net_income - se_deduction
        qbi_deduction = qbi_base * self.QBI_DEDUCTION_RATE

        taxable_business = net_income - se_deduction - qbi_deduction

        # Calculate income tax using progressive brackets
        total_taxable = taxable_business + self.other_income
        total_income_tax = self._calculate_progressive_tax(total_taxable)
        other_income_tax = self._calculate_progressive_tax(self.other_income)
        income_tax = total_income_tax - other_income_tax

        total_tax = se_tax + income_tax

        # LLC has additional costs
        formation_cost = 150.0  # State filing fee estimate
        annual_cost = 400.0  # Annual report + Schedule C

        return EntityAnalysis(
            entity_type=EntityType.SINGLE_MEMBER_LLC,
            entity_name="Single-Member LLC (Disregarded Entity)",
            gross_revenue=gross_revenue,
            business_expenses=expenses,
            net_business_income=net_income,
            self_employment_tax=float(money(se_tax)),
            income_tax_on_business=float(money(income_tax)),
            se_tax_deduction=float(money(se_deduction)),
            qbi_deduction=float(money(qbi_deduction)),
            total_business_tax=float(money(total_tax)),
            effective_tax_rate=float(money(total_tax / net_income * 100)) if net_income > 0 else 0,
            formation_cost=formation_cost,
            annual_compliance_cost=annual_cost,
            total_annual_cost=float(money(total_tax + annual_cost)),
            recommendation_notes=[
                "Provides liability protection",
                "Same tax treatment as Sole Prop (disregarded entity)",
                "Can elect S-Corp taxation if beneficial",
                "State filing requirements vary",
            ],
        )

    def _analyze_s_corporation(
        self,
        gross_revenue: float,
        expenses: float,
        net_income: float,
        salary: float
    ) -> EntityAnalysis:
        """Analyze tax burden for S-Corporation."""
        # Employer payroll taxes (deductible expense)
        ss_wages = min(salary, self.SS_WAGE_BASE_2025)
        employer_ss = ss_wages * 0.062
        employer_medicare = salary * 0.0145
        employer_payroll = employer_ss + employer_medicare

        # K-1 distribution (after salary and employer payroll)
        k1_distribution = net_income - salary - employer_payroll

        # Employee payroll taxes (paid by shareholder)
        employee_ss = ss_wages * 0.062
        employee_medicare = salary * 0.0145
        employee_payroll = employee_ss + employee_medicare

        # QBI deduction on K-1 income (not salary)
        qbi_deduction = max(0, k1_distribution) * self.QBI_DEDUCTION_RATE

        # Income tax calculation using progressive brackets
        # Salary taxed as ordinary income (W-2)
        # K-1 distribution taxed as ordinary income (reduced by QBI)
        taxable_income = salary + max(0, k1_distribution) - qbi_deduction
        total_taxable = taxable_income + self.other_income
        total_income_tax = self._calculate_progressive_tax(total_taxable)
        other_income_tax = self._calculate_progressive_tax(self.other_income)
        income_tax = total_income_tax - other_income_tax

        # Total tax burden (employer payroll + employee payroll + income tax)
        # Note: employer payroll reduces business income, so it's already factored in
        total_tax = employer_payroll + employee_payroll + income_tax

        # S-Corp compliance costs
        formation = self.SCORP_FORMATION_COST
        compliance = self.SCORP_ANNUAL_COMPLIANCE
        payroll = self.PAYROLL_SERVICE_ANNUAL
        total_compliance = compliance + payroll

        return EntityAnalysis(
            entity_type=EntityType.S_CORPORATION,
            entity_name="S-Corporation (Form 1120-S)",
            gross_revenue=gross_revenue,
            business_expenses=expenses,
            net_business_income=net_income,
            owner_salary=salary,
            k1_distribution=float(money(k1_distribution)),
            payroll_taxes=float(money(employer_payroll + employee_payroll)),
            income_tax_on_business=float(money(income_tax)),
            qbi_deduction=float(money(qbi_deduction)),
            total_business_tax=float(money(total_tax)),
            effective_tax_rate=float(money(total_tax / net_income * 100)) if net_income > 0 else 0,
            formation_cost=formation,
            annual_compliance_cost=total_compliance,
            payroll_service_cost=payroll,
            total_annual_cost=float(money(total_tax + total_compliance)),
            recommendation_notes=[
                f"Salary: ${salary:,.0f} (subject to payroll taxes)",
                f"K-1 Distribution: ${k1_distribution:,.0f} (no SE tax)",
                "Requires payroll processing and Form 1120-S filing",
                "Must maintain corporate formalities",
            ],
        )

    def _estimate_marginal_rate(self, taxable_income: float) -> float:
        """Estimate marginal tax rate based on income."""
        brackets = self._get_brackets()
        for threshold, rate in brackets:
            if taxable_income <= threshold:
                return rate
        return 0.37

    def _get_brackets(self) -> list:
        """Get tax brackets for filing status."""
        # 2025 brackets
        if self.filing_status == "married_joint":
            return [
                (23850, 0.10),
                (96950, 0.12),
                (206700, 0.22),
                (394600, 0.24),
                (501050, 0.32),
                (751600, 0.35),
                (float('inf'), 0.37),
            ]
        else:  # single, default
            return [
                (11925, 0.10),
                (48475, 0.12),
                (103350, 0.22),
                (197300, 0.24),
                (250525, 0.32),
                (626350, 0.35),
                (float('inf'), 0.37),
            ]

    def _calculate_progressive_tax(self, taxable_income: float) -> float:
        """Calculate income tax using progressive brackets."""
        if taxable_income <= 0:
            return 0.0

        brackets = self._get_brackets()
        tax = 0.0
        prev_threshold = 0.0

        for threshold, rate in brackets:
            if taxable_income <= threshold:
                tax += (taxable_income - prev_threshold) * rate
                break
            else:
                tax += (threshold - prev_threshold) * rate
                prev_threshold = threshold

        return tax

    def _determine_recommended_entity(
        self,
        analyses: Dict[str, EntityAnalysis],
        net_income: float
    ) -> EntityType:
        """Determine the recommended entity based on total annual cost."""
        # For low income, recommend simpler structures
        if net_income < 40000:
            return EntityType.SOLE_PROPRIETORSHIP

        # Compare total annual costs
        costs = {
            EntityType(k): v.total_annual_cost
            for k, v in analyses.items()
        }

        # Find minimum cost
        min_entity = min(costs, key=costs.get)

        # S-Corp needs significant savings to justify complexity
        scorp_cost = costs.get(EntityType.S_CORPORATION, float('inf'))
        sole_prop_cost = costs.get(EntityType.SOLE_PROPRIETORSHIP, float('inf'))

        # Require at least $2,000 annual savings to recommend S-Corp
        if min_entity == EntityType.S_CORPORATION:
            savings = sole_prop_cost - scorp_cost
            if savings < 2000:
                return EntityType.SINGLE_MEMBER_LLC

        return min_entity

    def _calculate_max_savings(self, analyses: Dict[str, EntityAnalysis]) -> float:
        """Calculate maximum annual savings from optimal entity choice."""
        costs = [a.total_annual_cost for a in analyses.values()]
        if len(costs) < 2:
            return 0.0
        return max(costs) - min(costs)

    def _calculate_savings_vs_current(
        self,
        analyses: Dict[str, EntityAnalysis],
        current: Optional[EntityType]
    ) -> float:
        """Calculate savings compared to current entity."""
        if not current:
            return 0.0

        current_analysis = analyses.get(current.value)
        if not current_analysis:
            return 0.0

        recommended = min(analyses.values(), key=lambda a: a.total_annual_cost)
        return current_analysis.total_annual_cost - recommended.total_annual_cost

    def _calculate_breakeven_revenue(self, expenses: float) -> float:
        """Calculate revenue where S-Corp becomes beneficial."""
        # S-Corp typically beneficial when net income > $40-50k
        # Account for additional compliance costs (~$2,100/year)
        # SE tax savings need to exceed compliance costs

        # Simplified: breakeven when SE tax savings > $2,500
        # SE tax on $50k income ≈ $7,065
        # With S-Corp (60% salary = $30k), payroll ≈ $4,590
        # Savings ≈ $2,475

        # So breakeven net income is around $50k
        breakeven_net = 50000.0
        return breakeven_net + expenses

    def _generate_warnings(
        self,
        net_income: float,
        salary: float,
        recommended: EntityType
    ) -> List[str]:
        """Generate warnings about the recommendation."""
        warnings = []

        if recommended == EntityType.S_CORPORATION:
            if salary / net_income < 0.40:
                warnings.append(
                    "WARNING: Low salary ratio may attract IRS scrutiny. "
                    "Ensure salary meets 'reasonable compensation' standards."
                )

            warnings.append(
                "S-Corp requires ongoing compliance: payroll, Form 1120-S, "
                "corporate minutes, and state filings."
            )

            if net_income < 60000:
                warnings.append(
                    "Net income may be too low to justify S-Corp complexity. "
                    "Monitor income growth before electing."
                )

        if net_income > 200000:
            warnings.append(
                "High income may trigger QBI deduction limitations. "
                "Consult a tax professional for detailed analysis."
            )

        return warnings

    def _generate_considerations(
        self,
        net_income: float,
        recommended: EntityType,
        current: Optional[EntityType]
    ) -> List[str]:
        """Generate additional considerations."""
        considerations = [
            "This analysis uses simplified calculations. Consult a tax professional for your specific situation.",
        ]

        if recommended == EntityType.S_CORPORATION and current != EntityType.S_CORPORATION:
            considerations.extend([
                "S-Corp election (Form 2553) must be filed by March 15 for current year.",
                "Late election relief may be available with reasonable cause.",
                "Consider state-specific S-Corp requirements and fees.",
            ])

        if net_income > 100000:
            considerations.append(
                "At this income level, consider retirement plan strategies "
                "(SEP-IRA, Solo 401k) which work with any entity type."
            )

        if self.state:
            considerations.append(
                f"State-specific rules for {self.state} may affect this analysis. "
                "Some states have additional S-Corp taxes or fees."
            )

        return considerations

    def _generate_recommendation_reason(
        self,
        recommended: EntityType,
        analyses: Dict[str, EntityAnalysis],
        net_income: float
    ) -> str:
        """Generate explanation for the recommendation."""
        rec_analysis = analyses.get(recommended.value)
        if not rec_analysis:
            return "Unable to determine recommendation."

        if recommended == EntityType.SOLE_PROPRIETORSHIP:
            return (
                f"Sole Proprietorship is recommended due to simplicity and low compliance costs. "
                f"At ${net_income:,.0f} net income, S-Corp savings don't justify the complexity."
            )

        if recommended == EntityType.SINGLE_MEMBER_LLC:
            return (
                f"Single-Member LLC provides liability protection with minimal additional cost. "
                f"S-Corp election can be made later if income grows."
            )

        if recommended == EntityType.S_CORPORATION:
            sole_prop = analyses.get(EntityType.SOLE_PROPRIETORSHIP.value)
            if sole_prop:
                savings = sole_prop.total_annual_cost - rec_analysis.total_annual_cost
                return (
                    f"S-Corporation is recommended with estimated annual savings of ${savings:,.0f}. "
                    f"Salary of ${rec_analysis.owner_salary:,.0f} with ${rec_analysis.k1_distribution:,.0f} "
                    f"in distributions avoids SE tax on the distribution portion."
                )

        return f"{recommended.value} is recommended based on your situation."

    def _calculate_confidence(
        self,
        analyses: Dict[str, EntityAnalysis],
        net_income: float
    ) -> float:
        """Calculate confidence score for the recommendation."""
        costs = sorted([a.total_annual_cost for a in analyses.values()])

        if len(costs) < 2:
            return 50.0

        # Higher confidence when savings are significant
        savings = costs[-1] - costs[0]
        savings_pct = (savings / costs[-1] * 100) if costs[-1] > 0 else 0

        # Base confidence
        confidence = 60.0

        # Add confidence for significant savings
        if savings > 5000:
            confidence += 20
        elif savings > 2000:
            confidence += 10

        # Add confidence for clear separation
        if savings_pct > 10:
            confidence += 10

        # Reduce confidence for edge cases
        if net_income < 50000 or net_income > 300000:
            confidence -= 10

        return min(100, max(50, confidence))

    def _create_no_income_result(
        self,
        gross_revenue: float,
        expenses: float
    ) -> EntityComparisonResult:
        """Create result for zero or negative income scenario."""
        return EntityComparisonResult(
            analyses={},
            recommended_entity=EntityType.SOLE_PROPRIETORSHIP,
            current_entity=None,
            max_annual_savings=0.0,
            savings_vs_current=0.0,
            salary_analysis=None,
            recommendation_reason="Business has no net income. Focus on profitability before entity optimization.",
            confidence_score=100.0,
            breakeven_revenue=expenses + 50000,
            warnings=["Business is not profitable - entity structure has minimal tax impact."],
            considerations=["Focus on increasing revenue or reducing expenses."],
        )
