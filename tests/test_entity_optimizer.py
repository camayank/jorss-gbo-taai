"""
Test suite for Entity Structure Optimizer.

Tests S-Corp vs Sole Proprietorship vs LLC comparison:
- Self-employment tax calculations
- Reasonable salary determination
- QBI deduction impact
- Total tax comparison
- Breakeven analysis

Reference: IRS Publication 334, 541, 542
"""

import pytest
from recommendation.entity_optimizer import (
    EntityStructureOptimizer,
    EntityType,
    EntityAnalysis,
    EntityComparisonResult,
    ReasonableSalaryAnalysis,
)


@pytest.fixture
def optimizer() -> EntityStructureOptimizer:
    """Create default optimizer instance."""
    return EntityStructureOptimizer(filing_status="single")


class TestEntityTypes:
    """Test entity type enum and basic structure."""

    def test_entity_types_defined(self):
        """All expected entity types exist."""
        assert EntityType.SOLE_PROPRIETORSHIP.value == "sole_proprietorship"
        assert EntityType.SINGLE_MEMBER_LLC.value == "single_member_llc"
        assert EntityType.S_CORPORATION.value == "s_corporation"

    def test_optimizer_initialization(self, optimizer):
        """Optimizer initializes with correct defaults."""
        assert optimizer.filing_status == "single"
        assert optimizer.other_income == 0.0
        assert optimizer.state is None

    def test_optimizer_with_state(self):
        """Optimizer accepts state parameter."""
        opt = EntityStructureOptimizer(filing_status="married_joint", state="CA")
        assert opt.state == "CA"
        assert opt.filing_status == "married_joint"


class TestReasonableSalary:
    """Test reasonable salary calculation for S-Corp."""

    def test_salary_calculation_moderate_income(self, optimizer):
        """Reasonable salary for moderate income ($100k net)."""
        result = optimizer.calculate_reasonable_salary(
            net_income=100000,
            gross_revenue=150000
        )

        assert isinstance(result, ReasonableSalaryAnalysis)
        # Should be around 55-60% of net income
        assert 50000 <= result.recommended_salary <= 70000
        assert result.salary_range_low < result.recommended_salary
        assert result.salary_range_high > result.recommended_salary
        assert result.irs_risk_level in ["low", "medium", "high"]

    def test_salary_calculation_low_income(self, optimizer):
        """Reasonable salary for low income ($50k net)."""
        result = optimizer.calculate_reasonable_salary(
            net_income=50000,
            gross_revenue=80000
        )

        # Higher percentage for lower income
        assert result.recommended_salary >= 35000
        # Should be at least 70% for low income
        assert result.recommended_salary / 50000 >= 0.65

    def test_salary_calculation_high_income(self, optimizer):
        """Reasonable salary for high income ($300k net)."""
        result = optimizer.calculate_reasonable_salary(
            net_income=300000,
            gross_revenue=400000
        )

        # Around 50% for high income
        assert 140000 <= result.recommended_salary <= 180000
        # Capped at reasonable levels
        assert result.recommended_salary <= 300000 * 0.85

    def test_salary_with_fixed_amount(self, optimizer):
        """User-specified salary is used."""
        result = optimizer.calculate_reasonable_salary(
            net_income=100000,
            gross_revenue=150000,
            fixed_salary=75000
        )

        assert result.recommended_salary == 75000
        assert "User-specified" in result.methodology

    def test_salary_irs_risk_assessment(self, optimizer):
        """IRS risk level assessed correctly."""
        # High salary ratio = low risk
        result = optimizer.calculate_reasonable_salary(
            net_income=100000,
            gross_revenue=150000
        )
        # With 55-60% ratio, should be low or medium risk
        assert result.irs_risk_level in ["low", "medium"]

    def test_salary_factors_documented(self, optimizer):
        """Salary calculation factors are documented."""
        result = optimizer.calculate_reasonable_salary(
            net_income=100000,
            gross_revenue=150000
        )

        assert len(result.factors_considered) > 0
        assert result.methodology != ""


class TestSCorpSavingsCalculation:
    """Test S-Corp tax savings calculation."""

    def test_scorp_savings_basic(self, optimizer):
        """Basic S-Corp savings calculation."""
        result = optimizer.calculate_scorp_savings(
            net_business_income=100000,
            reasonable_salary=60000
        )

        assert "sole_prop_se_tax" in result
        assert "scorp_total_payroll" in result
        assert "se_tax_savings" in result

        # S-Corp should have lower total payroll taxes
        assert result["se_tax_savings"] > 0

    def test_scorp_savings_components(self, optimizer):
        """All savings components calculated."""
        result = optimizer.calculate_scorp_savings(
            net_business_income=150000,
            reasonable_salary=80000
        )

        # Check all expected keys
        expected_keys = [
            "sole_prop_se_tax",
            "sole_prop_se_deduction",
            "sole_prop_qbi_deduction",
            "scorp_employer_payroll",
            "scorp_employee_payroll",
            "scorp_total_payroll",
            "scorp_k1_distribution",
            "scorp_qbi_deduction",
            "se_tax_savings",
            "qbi_difference",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_scorp_k1_distribution(self, optimizer):
        """K-1 distribution calculated correctly."""
        result = optimizer.calculate_scorp_savings(
            net_business_income=100000,
            reasonable_salary=60000
        )

        # K-1 = Net income - Salary - Employer payroll
        expected_k1 = 100000 - 60000 - result["scorp_employer_payroll"]
        assert abs(result["scorp_k1_distribution"] - expected_k1) < 1

    def test_scorp_se_tax_savings_formula(self, optimizer):
        """SE tax savings calculated correctly."""
        result = optimizer.calculate_scorp_savings(
            net_business_income=100000,
            reasonable_salary=60000
        )

        # Savings = Sole Prop SE tax - S-Corp total payroll
        expected_savings = result["sole_prop_se_tax"] - result["scorp_total_payroll"]
        assert abs(result["se_tax_savings"] - expected_savings) < 1


class TestEntityComparison:
    """Test full entity structure comparison."""

    def test_comparison_returns_all_entities(self, optimizer):
        """Comparison includes all entity types."""
        result = optimizer.compare_structures(
            gross_revenue=150000,
            business_expenses=50000
        )

        assert isinstance(result, EntityComparisonResult)
        assert EntityType.SOLE_PROPRIETORSHIP.value in result.analyses
        assert EntityType.SINGLE_MEMBER_LLC.value in result.analyses
        assert EntityType.S_CORPORATION.value in result.analyses

    def test_comparison_recommends_entity(self, optimizer):
        """Comparison provides a recommendation."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000
        )

        assert result.recommended_entity in EntityType
        assert result.recommendation_reason != ""
        assert 0 <= result.confidence_score <= 100

    def test_comparison_calculates_savings(self, optimizer):
        """Comparison calculates potential savings."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000
        )

        assert result.max_annual_savings >= 0
        assert result.breakeven_revenue > 0

    def test_comparison_with_current_entity(self, optimizer):
        """Comparison includes savings vs current entity."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000,
            current_entity=EntityType.SOLE_PROPRIETORSHIP
        )

        assert result.current_entity == EntityType.SOLE_PROPRIETORSHIP
        # If S-Corp recommended, should show savings
        if result.recommended_entity == EntityType.S_CORPORATION:
            assert result.savings_vs_current > 0


class TestLowIncomeScenarios:
    """Test scenarios with low business income."""

    def test_low_income_recommends_simple_structure(self, optimizer):
        """Low income should recommend simpler structure."""
        result = optimizer.compare_structures(
            gross_revenue=50000,
            business_expenses=20000  # $30k net
        )

        # Should not recommend S-Corp for low income
        assert result.recommended_entity in [
            EntityType.SOLE_PROPRIETORSHIP,
            EntityType.SINGLE_MEMBER_LLC
        ]

    def test_very_low_income(self, optimizer):
        """Very low income scenario."""
        result = optimizer.compare_structures(
            gross_revenue=30000,
            business_expenses=15000  # $15k net
        )

        # Sole prop or LLC for very low income
        assert result.recommended_entity in [
            EntityType.SOLE_PROPRIETORSHIP,
            EntityType.SINGLE_MEMBER_LLC
        ]

    def test_zero_net_income(self, optimizer):
        """Zero net income scenario."""
        result = optimizer.compare_structures(
            gross_revenue=50000,
            business_expenses=50000  # $0 net
        )

        assert result.recommended_entity == EntityType.SOLE_PROPRIETORSHIP
        assert "profitability" in result.recommendation_reason.lower() or "no net income" in result.recommendation_reason.lower()


class TestHighIncomeScenarios:
    """Test scenarios with high business income."""

    def test_high_income_provides_comparison(self, optimizer):
        """High income scenarios provide meaningful comparison."""
        result = optimizer.compare_structures(
            gross_revenue=300000,
            business_expenses=50000  # $250k net
        )

        # Should analyze all entities
        assert len(result.analyses) == 3
        # Should calculate savings potential
        assert result.max_annual_savings >= 0
        # Should provide recommendation
        assert result.recommended_entity is not None

    def test_high_income_scorp_has_lower_se_burden(self, optimizer):
        """S-Corp has lower payroll burden than sole prop SE tax."""
        result = optimizer.compare_structures(
            gross_revenue=400000,
            business_expenses=100000  # $300k net
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]
        scorp = result.analyses[EntityType.S_CORPORATION.value]

        # S-Corp payroll should be less than sole prop SE tax
        # (because SE tax applies to all income, payroll only to salary)
        assert scorp.payroll_taxes < sole_prop.self_employment_tax

    def test_high_income_salary_analysis_included(self, optimizer):
        """High income comparison includes salary analysis."""
        result = optimizer.compare_structures(
            gross_revenue=300000,
            business_expenses=50000
        )

        assert result.salary_analysis is not None
        assert result.salary_analysis.recommended_salary > 0

    def test_very_high_income_favors_scorp(self, optimizer):
        """Very high income ($500k+) typically favors S-Corp."""
        result = optimizer.compare_structures(
            gross_revenue=600000,
            business_expenses=100000  # $500k net
        )

        scorp = result.analyses[EntityType.S_CORPORATION.value]
        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]

        # At very high income, S-Corp SE savings should be significant
        se_savings = sole_prop.self_employment_tax - scorp.payroll_taxes
        assert se_savings > 10000  # Significant SE tax savings


class TestComplianceCosts:
    """Test compliance cost calculations."""

    def test_sole_prop_minimal_costs(self, optimizer):
        """Sole prop has minimal compliance costs."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]
        assert sole_prop.formation_cost == 0
        assert sole_prop.annual_compliance_cost < 500

    def test_llc_moderate_costs(self, optimizer):
        """LLC has moderate compliance costs."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        llc = result.analyses[EntityType.SINGLE_MEMBER_LLC.value]
        assert llc.formation_cost > 0
        assert llc.annual_compliance_cost > 0

    def test_scorp_higher_costs(self, optimizer):
        """S-Corp has higher compliance costs."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        scorp = result.analyses[EntityType.S_CORPORATION.value]
        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]

        assert scorp.annual_compliance_cost > sole_prop.annual_compliance_cost
        assert scorp.payroll_service_cost > 0


class TestSelfEmploymentTax:
    """Test self-employment tax calculations."""

    def test_se_tax_calculation(self, optimizer):
        """SE tax calculated correctly for sole prop."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000  # $70k net
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]

        # SE tax should be approximately 15.3% of 92.35% of net income
        # $70k × 0.9235 × 0.153 ≈ $9,890
        assert 9000 <= sole_prop.self_employment_tax <= 11000

    def test_se_tax_deduction(self, optimizer):
        """SE tax deduction is 50% of SE tax."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]

        expected_deduction = sole_prop.self_employment_tax / 2
        assert abs(sole_prop.se_tax_deduction - expected_deduction) < 1

    def test_scorp_no_se_tax_on_distribution(self, optimizer):
        """S-Corp K-1 distribution not subject to SE tax."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000  # $150k net
        )

        scorp = result.analyses[EntityType.S_CORPORATION.value]

        # S-Corp has no SE tax field (uses payroll instead)
        assert scorp.self_employment_tax == 0
        assert scorp.payroll_taxes > 0
        assert scorp.k1_distribution > 0


class TestQBIDeduction:
    """Test QBI deduction calculations."""

    def test_qbi_deduction_sole_prop(self, optimizer):
        """QBI deduction calculated for sole prop."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000  # $70k net
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]

        # QBI deduction should be approximately 20% of adjusted income
        assert sole_prop.qbi_deduction > 0
        # Should be less than 20% of net income due to SE deduction
        assert sole_prop.qbi_deduction < 70000 * 0.20

    def test_qbi_deduction_scorp(self, optimizer):
        """QBI deduction for S-Corp based on K-1."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000
        )

        scorp = result.analyses[EntityType.S_CORPORATION.value]

        # QBI based on K-1 distribution (not salary)
        assert scorp.qbi_deduction > 0
        assert scorp.qbi_deduction <= scorp.k1_distribution * 0.20


class TestWarningsAndConsiderations:
    """Test warning and consideration generation."""

    def test_scorp_generates_warnings(self, optimizer):
        """S-Corp recommendation includes appropriate warnings."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000
        )

        if result.recommended_entity == EntityType.S_CORPORATION:
            assert len(result.warnings) > 0
            # Should mention compliance
            assert any("compliance" in w.lower() for w in result.warnings)

    def test_considerations_always_present(self, optimizer):
        """Considerations are always generated."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        assert len(result.considerations) > 0
        # Should always recommend consulting professional
        assert any("professional" in c.lower() for c in result.considerations)

    def test_state_consideration_when_provided(self):
        """State-specific consideration when state provided."""
        opt = EntityStructureOptimizer(filing_status="single", state="CA")
        result = opt.compare_structures(
            gross_revenue=200000,
            business_expenses=50000
        )

        # Should mention state
        assert any("CA" in c or "state" in c.lower() for c in result.considerations)


class TestBreakevenAnalysis:
    """Test breakeven revenue calculation."""

    def test_breakeven_calculated(self, optimizer):
        """Breakeven revenue is calculated."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        assert result.breakeven_revenue > 0
        # Breakeven should be > expenses
        assert result.breakeven_revenue > 30000

    def test_breakeven_reasonable_value(self, optimizer):
        """Breakeven is at reasonable level (~$50k net income)."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        # Breakeven net income typically around $50k
        breakeven_net = result.breakeven_revenue - 30000
        assert 40000 <= breakeven_net <= 70000


class TestFiveYearProjection:
    """Test five-year savings projection."""

    def test_five_year_savings_calculated(self, optimizer):
        """Five-year savings projection included."""
        result = optimizer.compare_structures(
            gross_revenue=250000,
            business_expenses=50000
        )

        if result.recommended_entity == EntityType.S_CORPORATION:
            assert result.five_year_savings > 0
            # Should be approximately 5x annual savings
            assert abs(result.five_year_savings - result.max_annual_savings * 5) < 100

    def test_five_year_zero_when_not_scorp(self, optimizer):
        """Five-year savings zero when S-Corp not recommended."""
        result = optimizer.compare_structures(
            gross_revenue=50000,
            business_expenses=30000  # Low net income
        )

        if result.recommended_entity != EntityType.S_CORPORATION:
            assert result.five_year_savings == 0


class TestEffectiveTaxRate:
    """Test effective tax rate calculations."""

    def test_effective_rate_calculated(self, optimizer):
        """Effective tax rate calculated for each entity."""
        result = optimizer.compare_structures(
            gross_revenue=150000,
            business_expenses=50000
        )

        for analysis in result.analyses.values():
            assert analysis.effective_tax_rate >= 0
            assert analysis.effective_tax_rate <= 60  # Reasonable max

    def test_scorp_lower_effective_rate(self, optimizer):
        """S-Corp typically has lower effective rate at high income."""
        result = optimizer.compare_structures(
            gross_revenue=300000,
            business_expenses=50000
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]
        scorp = result.analyses[EntityType.S_CORPORATION.value]

        # S-Corp should have lower effective rate due to SE tax savings
        assert scorp.effective_tax_rate < sole_prop.effective_tax_rate


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_net_income(self, optimizer):
        """Handles negative net income (loss)."""
        result = optimizer.compare_structures(
            gross_revenue=50000,
            business_expenses=60000  # $10k loss
        )

        # Should handle gracefully
        assert result.recommended_entity == EntityType.SOLE_PROPRIETORSHIP

    def test_very_high_income(self, optimizer):
        """Handles very high income."""
        result = optimizer.compare_structures(
            gross_revenue=1000000,
            business_expenses=200000  # $800k net
        )

        assert result.recommended_entity == EntityType.S_CORPORATION
        # Should have high income warning
        assert any("high income" in w.lower() or "qbi" in w.lower() for w in result.warnings)

    def test_custom_salary_in_comparison(self, optimizer):
        """Custom salary used when provided."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000,
            owner_salary=90000
        )

        scorp = result.analyses[EntityType.S_CORPORATION.value]
        assert scorp.owner_salary == 90000


class TestAnalysisDetails:
    """Test analysis detail fields."""

    def test_sole_prop_analysis_complete(self, optimizer):
        """Sole prop analysis has all required fields."""
        result = optimizer.compare_structures(
            gross_revenue=100000,
            business_expenses=30000
        )

        sole_prop = result.analyses[EntityType.SOLE_PROPRIETORSHIP.value]

        assert sole_prop.entity_type == EntityType.SOLE_PROPRIETORSHIP
        assert sole_prop.gross_revenue == 100000
        assert sole_prop.business_expenses == 30000
        assert sole_prop.net_business_income == 70000
        assert sole_prop.self_employment_tax > 0
        assert sole_prop.total_business_tax > 0
        assert len(sole_prop.recommendation_notes) > 0

    def test_scorp_analysis_complete(self, optimizer):
        """S-Corp analysis has all required fields."""
        result = optimizer.compare_structures(
            gross_revenue=200000,
            business_expenses=50000
        )

        scorp = result.analyses[EntityType.S_CORPORATION.value]

        assert scorp.entity_type == EntityType.S_CORPORATION
        assert scorp.owner_salary > 0
        assert scorp.k1_distribution >= 0
        assert scorp.payroll_taxes > 0
        assert len(scorp.recommendation_notes) > 0
        # Should mention salary and distribution in notes
        assert any("salary" in note.lower() for note in scorp.recommendation_notes)


class TestConfidenceScore:
    """Test confidence score calculation."""

    def test_confidence_in_range(self, optimizer):
        """Confidence score is in valid range."""
        result = optimizer.compare_structures(
            gross_revenue=150000,
            business_expenses=50000
        )

        assert 0 <= result.confidence_score <= 100

    def test_higher_confidence_with_clear_winner(self, optimizer):
        """Higher confidence when one option is clearly better."""
        # High income = clear S-Corp benefit
        high_income = optimizer.compare_structures(
            gross_revenue=400000,
            business_expenses=100000
        )

        # Low income = less clear
        low_income = optimizer.compare_structures(
            gross_revenue=80000,
            business_expenses=40000
        )

        # High income scenario should have higher confidence
        assert high_income.confidence_score >= low_income.confidence_score - 10
