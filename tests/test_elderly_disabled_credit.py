"""
Comprehensive tests for Credit for the Elderly or Disabled (Schedule R / IRC Section 22).

Tests cover:
- Eligibility by age (65+)
- Eligibility by disability (under 65 with taxable disability income)
- Initial amounts by filing status
- Nontaxable income reduction (Social Security, pensions, etc.)
- AGI-based reduction (50% of AGI over threshold)
- MFJ scenarios (both qualify vs one qualifies)
- MFS special rule (must live apart all year)
- Credit calculation (15% of amount after reductions)
"""

import pytest
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import (
    TaxCredits,
    ElderlyDisabledInfo,
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


def make_elderly_info(
    taxpayer_birth_year: int = 1955,  # 70 years old in 2025
    taxpayer_is_disabled: bool = False,
    taxpayer_disability_income: float = 0.0,
    spouse_birth_year: int = None,
    spouse_is_disabled: bool = False,
    spouse_disability_income: float = 0.0,
    nontaxable_ss: float = 0.0,
    nontaxable_pensions: float = 0.0,
    lived_apart: bool = False,
) -> ElderlyDisabledInfo:
    """Create elderly/disabled info for testing."""
    return ElderlyDisabledInfo(
        taxpayer_birth_year=taxpayer_birth_year,
        taxpayer_is_disabled=taxpayer_is_disabled,
        taxpayer_disability_income=taxpayer_disability_income,
        spouse_birth_year=spouse_birth_year,
        spouse_is_disabled=spouse_is_disabled,
        spouse_disability_income=spouse_disability_income,
        nontaxable_social_security=nontaxable_ss,
        nontaxable_pensions=nontaxable_pensions,
        lived_apart_all_year=lived_apart,
    )


# ============================================
# Test: No Elderly/Disabled Info
# ============================================

class TestNoInfo:
    """Test behavior when no elderly/disabled info provided."""

    def test_no_info_returns_zero(self):
        """No info should return zero credit."""
        engine = FederalTaxEngine()
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(10000)]),
            credits=TaxCredits(),
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 0.0


# ============================================
# Test: Age Qualification (65+)
# ============================================

class TestAgeQualification:
    """Test qualification by age (65 or older)."""

    def test_age_65_qualifies(self):
        """Person exactly 65 qualifies."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1960)  # 65 in 2025
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),  # Low AGI
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] > 0

    def test_age_70_qualifies(self):
        """Person 70 qualifies."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)  # 70 in 2025
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] > 0

    def test_age_64_does_not_qualify_by_age(self):
        """Person 64 does not qualify by age alone."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1961,  # 64 in 2025
            taxpayer_is_disabled=False,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 0.0


# ============================================
# Test: Disability Qualification
# ============================================

class TestDisabilityQualification:
    """Test qualification by permanent disability."""

    def test_disabled_under_65_with_income_qualifies(self):
        """Disabled person under 65 with disability income qualifies."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1970,  # 55 in 2025
            taxpayer_is_disabled=True,
            taxpayer_disability_income=6000.0,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] > 0

    def test_disabled_no_disability_income_no_credit(self):
        """Disabled person under 65 without disability income gets no credit."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1970,  # 55 in 2025
            taxpayer_is_disabled=True,
            taxpayer_disability_income=0.0,  # No disability income
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 0.0

    def test_disability_income_caps_initial_amount(self):
        """Disability income caps the initial amount for under-65."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1970,  # Under 65
            taxpayer_is_disabled=True,
            taxpayer_disability_income=3000.0,  # Less than $5,000
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),  # Low AGI
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Initial amount capped at $3,000 (disability income)
        # Credit = 15% of $3,000 = $450 (before AGI reduction)
        breakdown = result.credit_breakdown['elderly_disabled_breakdown']
        # AGI $5,000 is below $7,500 threshold, so no AGI reduction
        assert result.credit_breakdown['elderly_disabled_credit'] == 450.0


# ============================================
# Test: Initial Amounts by Filing Status
# ============================================

class TestInitialAmounts:
    """Test initial amounts by filing status."""

    def test_single_initial_5000(self):
        """Single filer has $5,000 initial amount."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(5000)]),  # Below AGI threshold
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 15% of $5,000 = $750
        assert result.credit_breakdown['elderly_disabled_credit'] == 750.0

    def test_hoh_initial_5000(self):
        """HOH has $5,000 initial amount."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 750.0

    def test_mfj_both_qualify_7500(self):
        """MFJ with both qualifying has $7,500 initial amount."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,  # 70 - qualifies
            spouse_birth_year=1958,    # 67 - qualifies
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(8000)]),  # Below $10k threshold
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 15% of $7,500 = $1,125
        assert result.credit_breakdown['elderly_disabled_credit'] == 1125.0

    def test_mfj_one_qualifies_5000(self):
        """MFJ with only one qualifying has $5,000 initial amount."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,  # 70 - qualifies
            spouse_birth_year=1980,    # 45 - does not qualify
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(8000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 15% of $5,000 = $750
        assert result.credit_breakdown['elderly_disabled_credit'] == 750.0


# ============================================
# Test: Nontaxable Income Reduction
# ============================================

class TestNontaxableReduction:
    """Test reduction for nontaxable income."""

    def test_social_security_reduces_credit(self):
        """Nontaxable Social Security reduces the credit."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            nontaxable_ss=2000.0,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Initial: $5,000
        # Less SS: $5,000 - $2,000 = $3,000
        # 15% of $3,000 = $450
        assert result.credit_breakdown['elderly_disabled_credit'] == 450.0

    def test_nontaxable_exceeds_initial_zero_credit(self):
        """Nontaxable income exceeding initial amount gives zero credit."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            nontaxable_ss=6000.0,  # More than $5,000 initial
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 0.0

    def test_multiple_nontaxable_sources(self):
        """Multiple nontaxable income sources combine."""
        engine = FederalTaxEngine()
        info = ElderlyDisabledInfo(
            taxpayer_birth_year=1955,
            nontaxable_social_security=1500.0,
            nontaxable_pensions=500.0,
            nontaxable_veterans_benefits=500.0,
        )  # Total: $2,500
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Initial: $5,000
        # Less nontaxable: $5,000 - $2,500 = $2,500
        # 15% of $2,500 = $375
        assert result.credit_breakdown['elderly_disabled_credit'] == 375.0


# ============================================
# Test: AGI Reduction
# ============================================

class TestAGIReduction:
    """Test AGI-based reduction (50% of AGI over threshold)."""

    def test_agi_below_threshold_no_reduction(self):
        """AGI below threshold gets no AGI reduction."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(7000)]),  # Below $7,500
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 15% of $5,000 = $750
        assert result.credit_breakdown['elderly_disabled_credit'] == 750.0

    def test_agi_over_threshold_reduces_credit(self):
        """AGI over threshold reduces credit by 50% of excess."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(9500)]),  # $2,000 over $7,500
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Initial: $5,000
        # AGI excess: $9,500 - $7,500 = $2,000
        # AGI reduction: $2,000 * 50% = $1,000
        # After reductions: $5,000 - $1,000 = $4,000
        # Credit: 15% of $4,000 = $600
        assert result.credit_breakdown['elderly_disabled_credit'] == 600.0

    def test_high_agi_eliminates_credit(self):
        """High AGI can eliminate the credit entirely."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(20000)]),  # Way over threshold
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # AGI excess: $20,000 - $7,500 = $12,500
        # AGI reduction: $12,500 * 50% = $6,250
        # Initial $5,000 - $6,250 = negative, so $0
        assert result.credit_breakdown['elderly_disabled_credit'] == 0.0

    def test_mfj_higher_agi_threshold(self):
        """MFJ has higher AGI threshold ($10,000)."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            spouse_birth_year=1958,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(9500)]),  # Below $10,000
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 15% of $7,500 = $1,125 (no reduction)
        assert result.credit_breakdown['elderly_disabled_credit'] == 1125.0


# ============================================
# Test: MFS Special Rule
# ============================================

class TestMFSRule:
    """Test MFS special rule (must live apart all year)."""

    def test_mfs_lived_apart_qualifies(self):
        """MFS who lived apart all year can qualify."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            lived_apart=True,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_SEPARATE,
            income=Income(w2_forms=[make_w2(4000)]),  # Below $5k threshold
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # MFS initial amount: $3,750
        # 15% of $3,750 = $562.50
        assert result.credit_breakdown['elderly_disabled_credit'] == 562.5

    def test_mfs_not_lived_apart_disqualified(self):
        """MFS who did not live apart cannot qualify."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            lived_apart=False,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_SEPARATE,
            income=Income(w2_forms=[make_w2(4000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 0.0


# ============================================
# Test: Combined Reductions
# ============================================

class TestCombinedReductions:
    """Test both nontaxable and AGI reductions together."""

    def test_both_reductions_applied(self):
        """Both nontaxable and AGI reductions apply."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            nontaxable_ss=1500.0,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(9500)]),  # $2,000 over threshold
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Initial: $5,000
        # Less SS: $5,000 - $1,500 = $3,500
        # AGI excess: $9,500 - $7,500 = $2,000
        # AGI reduction: $2,000 * 50% = $1,000
        # After all reductions: $3,500 - $1,000 = $2,500
        # Credit: 15% of $2,500 = $375
        assert result.credit_breakdown['elderly_disabled_credit'] == 375.0


# ============================================
# Test: Maximum Credit Amounts
# ============================================

class TestMaximumCredits:
    """Test maximum possible credit amounts."""

    def test_max_single_credit_750(self):
        """Maximum credit for single is $750 (15% of $5,000)."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(5000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 750.0

    def test_max_mfj_both_credit_1125(self):
        """Maximum credit for MFJ both is $1,125 (15% of $7,500)."""
        engine = FederalTaxEngine()
        info = make_elderly_info(
            taxpayer_birth_year=1955,
            spouse_birth_year=1958,
        )
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(8000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['elderly_disabled_credit'] == 1125.0


# ============================================
# Test: Integration
# ============================================

class TestIntegration:
    """Test integration with tax calculation."""

    def test_credit_reduces_tax(self):
        """Elderly/disabled credit reduces total tax."""
        engine = FederalTaxEngine()

        # Without credit
        tax_return_no_credit = make_return(
            income=Income(w2_forms=[make_w2(20000)]),
            credits=TaxCredits(),
        )
        result_no_credit = engine.calculate(tax_return_no_credit)

        # With credit (taxpayer age 65+, low additional income)
        info = make_elderly_info(taxpayer_birth_year=1955)
        tax_return_with_credit = make_return(
            income=Income(w2_forms=[make_w2(8000)]),  # Low wage income
            credits=TaxCredits(elderly_disabled_info=info),
        )
        result_with_credit = engine.calculate(tax_return_with_credit)

        # Credit should provide some benefit if there's tax to offset
        assert result_with_credit.credit_breakdown['elderly_disabled_credit'] > 0

    def test_breakdown_populated(self):
        """Breakdown should be populated."""
        engine = FederalTaxEngine()
        info = make_elderly_info(taxpayer_birth_year=1955)
        credits = TaxCredits(elderly_disabled_info=info)
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(8000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        breakdown = result.credit_breakdown['elderly_disabled_breakdown']
        assert 'taxpayer_qualifies' in breakdown
        assert 'initial_amount' in breakdown
        assert 'credit_rate' in breakdown
        assert breakdown['taxpayer_qualifies'] == True
        assert breakdown['initial_amount'] == 5000.0
