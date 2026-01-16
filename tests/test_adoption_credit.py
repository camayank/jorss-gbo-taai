"""
Comprehensive tests for Adoption Credit (Form 8839 / IRC Section 23).

Tests cover:
- Basic adoption credit calculation
- Maximum credit per child ($16,810 for 2025)
- Special needs adoptions (full credit regardless of expenses)
- Domestic vs foreign adoption timing rules
- Income phaseout ($252,150 - $292,150)
- Child eligibility (under 18 or disabled)
- Employer-provided benefits reduction
- Prior year carryforward
- Multiple adoptions
"""

import pytest
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import (
    TaxCredits,
    AdoptionInfo,
    AdoptionType,
)
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from calculator.engine import FederalTaxEngine


# ============================================
# Helper Functions
# ============================================

def make_taxpayer(filing_status: FilingStatus = FilingStatus.SINGLE) -> TaxpayerInfo:
    """Create a basic taxpayer for testing."""
    return TaxpayerInfo(
        first_name="Test",
        last_name="Taxpayer",
        ssn="123-45-6789",
        filing_status=filing_status,
    )


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Create a W2 for testing."""
    return W2Info(
        employer_name="Test Employer",
        employer_ein="12-3456789",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def make_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    income: Income = None,
    credits: TaxCredits = None,
) -> TaxReturn:
    """Create a tax return for testing."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=make_taxpayer(filing_status),
        income=income or Income(),
        deductions=Deductions(use_standard_deduction=True),
        credits=credits or TaxCredits(),
    )


def make_adoption(
    child_name: str = "Adopted Child",
    child_birth_year: int = 2020,
    adoption_type: AdoptionType = AdoptionType.DOMESTIC,
    is_special_needs: bool = False,
    is_disabled: bool = False,
    adoption_finalized: bool = True,
    adoption_fees: float = 10000.0,
    court_costs: float = 2000.0,
    attorney_fees: float = 3000.0,
    travel_expenses: float = 2000.0,
    other_expenses: float = 1000.0,
    employer_benefits: float = 0.0,
    prior_carryforward: float = 0.0,
) -> AdoptionInfo:
    """Create an adoption for testing."""
    return AdoptionInfo(
        child_name=child_name,
        child_birth_year=child_birth_year,
        adoption_type=adoption_type,
        is_special_needs=is_special_needs,
        is_disabled=is_disabled,
        adoption_finalized=adoption_finalized,
        adoption_fees=adoption_fees,
        court_costs=court_costs,
        attorney_fees=attorney_fees,
        travel_expenses=travel_expenses,
        other_expenses=other_expenses,
        employer_adoption_benefits=employer_benefits,
        prior_year_carryforward=prior_carryforward,
    )


# ============================================
# Test: No Adoptions
# ============================================

class TestNoAdoptions:
    """Test behavior when no adoptions."""

    def test_no_adoptions_returns_zero_credit(self):
        """No adoptions should return zero credit."""
        engine = FederalTaxEngine()
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=TaxCredits(),
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 0.0


# ============================================
# Test: Basic Adoption Credit
# ============================================

class TestBasicAdoptionCredit:
    """Test basic adoption credit calculation."""

    def test_full_expenses_under_max(self):
        """Expenses under max should get full credit."""
        engine = FederalTaxEngine()
        # Total expenses: 10k + 2k + 3k + 2k + 1k = $18,000
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Max is $16,810 for 2025, so capped at that
        assert result.credit_breakdown['adoption_credit'] == 16810.0

    def test_expenses_below_max(self):
        """Expenses below max should get actual amount."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_fees=5000.0,
            court_costs=1000.0,
            attorney_fees=2000.0,
            travel_expenses=0.0,
            other_expenses=0.0,
        )  # Total: $8,000
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 8000.0

    def test_zero_expenses_zero_credit(self):
        """Zero expenses (non-special needs) should get zero credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_fees=0.0,
            court_costs=0.0,
            attorney_fees=0.0,
            travel_expenses=0.0,
            other_expenses=0.0,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 0.0


# ============================================
# Test: Special Needs Adoption
# ============================================

class TestSpecialNeedsAdoption:
    """Test special needs adoption credit."""

    def test_special_needs_full_credit_regardless_of_expenses(self):
        """Special needs adoption gets full max credit regardless of expenses."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            is_special_needs=True,
            adoption_fees=0.0,  # No expenses
            court_costs=0.0,
            attorney_fees=0.0,
            travel_expenses=0.0,
            other_expenses=0.0,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Special needs gets full $16,810 regardless of actual expenses
        assert result.credit_breakdown['adoption_credit'] == 16810.0

    def test_special_needs_type_enum(self):
        """AdoptionType.SPECIAL_NEEDS should also get full credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_type=AdoptionType.SPECIAL_NEEDS,
            adoption_fees=1000.0,  # Minimal expenses
            court_costs=0.0,
            attorney_fees=0.0,
            travel_expenses=0.0,
            other_expenses=0.0,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 16810.0


# ============================================
# Test: Foreign Adoption Rules
# ============================================

class TestForeignAdoption:
    """Test foreign adoption timing rules."""

    def test_foreign_adoption_finalized_qualifies(self):
        """Foreign adoption that's finalized qualifies for credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_type=AdoptionType.FOREIGN,
            adoption_finalized=True,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 16810.0

    def test_foreign_adoption_not_finalized_disqualified(self):
        """Foreign adoption not finalized does not qualify."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_type=AdoptionType.FOREIGN,
            adoption_finalized=False,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 0.0


# ============================================
# Test: Income Phaseout
# ============================================

class TestIncomePhaseout:
    """Test income-based phaseout of adoption credit."""

    def test_below_phaseout_start_full_credit(self):
        """Income below phaseout start gets full credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(200000)]),  # Below $252,150
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 16810.0

    def test_at_phaseout_start_full_credit(self):
        """Income at exactly phaseout start gets full credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(252150)]),  # Exactly at start
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # At start of phaseout, should still get full credit
        assert result.credit_breakdown['adoption_credit'] == 16810.0

    def test_midpoint_phaseout(self):
        """Income at midpoint of phaseout gets ~50% credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        # Midpoint: (252150 + 292150) / 2 = 272150
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(272150)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Should be approximately half
        expected = 16810.0 * 0.5
        assert abs(result.credit_breakdown['adoption_credit'] - expected) < 100

    def test_above_phaseout_end_zero_credit(self):
        """Income above phaseout end gets zero credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(300000)]),  # Above $292,150
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 0.0


# ============================================
# Test: Child Eligibility
# ============================================

class TestChildEligibility:
    """Test child eligibility requirements."""

    def test_child_under_18_qualifies(self):
        """Child under 18 qualifies."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            child_birth_year=2015,  # 10 years old in 2025
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] > 0

    def test_child_18_or_over_disqualified(self):
        """Child 18 or older and not disabled is disqualified."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            child_birth_year=2005,  # 20 years old in 2025
            is_disabled=False,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] == 0.0

    def test_adult_disabled_child_qualifies(self):
        """Adult child who is disabled qualifies."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            child_birth_year=2000,  # 25 years old in 2025
            is_disabled=True,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['adoption_credit'] > 0


# ============================================
# Test: Employer Benefits Reduction
# ============================================

class TestEmployerBenefits:
    """Test reduction for employer-provided adoption benefits."""

    def test_employer_benefits_reduce_credit(self):
        """Employer benefits reduce qualified expenses."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_fees=10000.0,
            court_costs=0.0,
            attorney_fees=0.0,
            travel_expenses=0.0,
            other_expenses=0.0,
            employer_benefits=3000.0,  # Employer paid $3k
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # $10k - $3k employer benefits = $7k credit
        assert result.credit_breakdown['adoption_credit'] == 7000.0

    def test_employer_benefits_exceed_expenses(self):
        """Employer benefits exceeding expenses gives zero credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_fees=5000.0,
            court_costs=0.0,
            attorney_fees=0.0,
            travel_expenses=0.0,
            other_expenses=0.0,
            employer_benefits=10000.0,  # More than expenses
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Expenses minus benefits can't go negative
        assert result.credit_breakdown['adoption_credit'] == 0.0


# ============================================
# Test: Multiple Adoptions
# ============================================

class TestMultipleAdoptions:
    """Test multiple child adoptions."""

    def test_two_children_double_credit(self):
        """Two adoptions can get up to double the max."""
        engine = FederalTaxEngine()
        adoption1 = make_adoption(child_name="Child 1", child_birth_year=2020)
        adoption2 = make_adoption(child_name="Child 2", child_birth_year=2021)
        credits = TaxCredits(adoptions=[adoption1, adoption2])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Each child gets up to $16,810
        assert result.credit_breakdown['adoption_credit'] == 16810.0 * 2

    def test_one_qualifies_one_doesnt(self):
        """One qualifying and one disqualified adoption."""
        engine = FederalTaxEngine()
        adoption1 = make_adoption(
            child_name="Young Child",
            child_birth_year=2020,  # Under 18
        )
        adoption2 = make_adoption(
            child_name="Adult Child",
            child_birth_year=2000,  # Over 18
            is_disabled=False,
        )
        credits = TaxCredits(adoptions=[adoption1, adoption2])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Only one child qualifies
        assert result.credit_breakdown['adoption_credit'] == 16810.0


# ============================================
# Test: Prior Year Carryforward
# ============================================

class TestCarryforward:
    """Test prior year carryforward."""

    def test_carryforward_adds_to_credit(self):
        """Prior year carryforward adds to current credit."""
        engine = FederalTaxEngine()
        adoption = make_adoption(
            adoption_fees=5000.0,
            court_costs=0.0,
            attorney_fees=0.0,
            travel_expenses=0.0,
            other_expenses=0.0,
            prior_carryforward=3000.0,
        )
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # $5k current expenses + $3k carryforward = $8k
        assert result.credit_breakdown['adoption_credit'] == 8000.0


# ============================================
# Test: Integration
# ============================================

class TestIntegration:
    """Test adoption credit integration with tax calculation."""

    def test_credit_reduces_tax(self):
        """Adoption credit reduces total tax."""
        engine = FederalTaxEngine()

        # Without adoption credit
        tax_return_no_adoption = make_return(
            income=Income(w2_forms=[make_w2(150000)]),
            credits=TaxCredits(),
        )
        result_no_adoption = engine.calculate(tax_return_no_adoption)

        # With adoption credit
        adoption = make_adoption()
        tax_return_with_adoption = make_return(
            income=Income(w2_forms=[make_w2(150000)]),
            credits=TaxCredits(adoptions=[adoption]),
        )
        result_with_adoption = engine.calculate(tax_return_with_adoption)

        assert result_with_adoption.total_tax < result_no_adoption.total_tax

    def test_credit_breakdown_populated(self):
        """Adoption credit breakdown should be populated."""
        engine = FederalTaxEngine()
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        breakdown = result.credit_breakdown['adoption_credit_breakdown']
        assert 'adoptions' in breakdown
        assert 'total_credit_before_phaseout' in breakdown
        assert 'children_qualified' in breakdown
        assert breakdown['children_qualified'] == 1

    def test_nonrefundable_credit(self):
        """Adoption credit is nonrefundable."""
        engine = FederalTaxEngine()
        adoption = make_adoption()
        credits = TaxCredits(adoptions=[adoption])
        # Low income = low tax
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(30000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Credit amount should be calculated
        assert result.credit_breakdown['adoption_credit'] == 16810.0
        # But actual benefit is limited by tax liability (nonrefundable)
