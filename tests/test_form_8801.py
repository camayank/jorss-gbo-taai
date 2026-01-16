"""
Tests for Form 8801 - Credit for Prior Year Minimum Tax

Tests cover:
- MTC (Minimum Tax Credit) calculation
- Deferral vs exclusion items
- Credit limit (regular tax - TMT)
- Carryforward tracking
- Prior year AMT detail tracking
- Integration with Form 6251
- Integration with tax calculation engine
- Helper functions
"""

import pytest
from models.form_8801 import (
    Form8801,
    PriorYearAMTDetail,
    MTCCarryforward,
    AMTItemType,
    calculate_mtc_from_amt,
    calculate_credit_limit,
    track_mtc_carryforward,
    estimate_mtc_benefit,
    reconcile_amt_to_mtc,
)
from models.form_6251 import Form6251
from models.income import Income, W2Info
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


# ============== Helper Functions ==============

def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def create_tax_return(
    wages: float = 100000.0,
    form_8801: Form8801 = None,
    form_6251: Form6251 = None,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    prior_year_amt_credit: float = 0.0,
) -> TaxReturn:
    """Helper to create TaxReturn with Form 8801."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
        ),
        income=Income(
            w2_forms=[make_w2(wages, wages * 0.20)],
            form_8801=form_8801,
            form_6251=form_6251,
            prior_year_amt_credit=prior_year_amt_credit,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


# ============== Prior Year AMT Detail Tests ==============

class TestPriorYearAMTDetail:
    """Tests for prior year AMT tracking."""

    def test_deferral_amt_calculation(self):
        """Calculate AMT from deferral items."""
        detail = PriorYearAMTDetail(
            tax_year=2024,
            total_amt_paid=15000.0,
            amt_from_iso=10000.0,
            amt_from_depreciation=3000.0,
            amt_from_other_deferral=2000.0,
        )
        # Deferral total: 10000 + 3000 + 2000 = 15000
        assert detail.get_deferral_amt() == 15000.0

    def test_exclusion_amt_calculation(self):
        """Calculate AMT from exclusion items."""
        detail = PriorYearAMTDetail(
            tax_year=2024,
            total_amt_paid=20000.0,
            amt_from_pab_interest=5000.0,
            amt_from_depletion=3000.0,
        )
        assert detail.get_exclusion_amt() == 8000.0

    def test_mtc_generated_from_deferral(self):
        """MTC generated equals deferral portion."""
        detail = PriorYearAMTDetail(
            tax_year=2024,
            total_amt_paid=25000.0,
            amt_from_iso=15000.0,
            amt_from_pab_interest=10000.0,  # Exclusion - no MTC
        )
        # Only ISO generates MTC
        assert detail.get_mtc_generated() == 15000.0

    def test_all_deferral_generates_full_mtc(self):
        """When all AMT is from deferral, full MTC generated."""
        detail = PriorYearAMTDetail(
            tax_year=2024,
            total_amt_paid=20000.0,
            amt_from_iso=20000.0,
        )
        assert detail.get_mtc_generated() == 20000.0


# ============== MTC Carryforward Tests ==============

class TestMTCCarryforward:
    """Tests for MTC carryforward tracking."""

    def test_carryforward_remaining(self):
        """Calculate remaining carryforward."""
        cf = MTCCarryforward(
            origin_year=2023,
            original_amount=10000.0,
            amount_used=3000.0,
        )
        assert cf.remaining == 7000.0

    def test_use_credit_partial(self):
        """Use partial credit amount."""
        cf = MTCCarryforward(
            origin_year=2023,
            original_amount=10000.0,
            amount_used=0.0,
        )
        used = cf.use_credit(4000.0)
        assert used == 4000.0
        assert cf.amount_used == 4000.0
        assert cf.remaining == 6000.0

    def test_use_credit_limited_to_remaining(self):
        """Credit usage limited to remaining amount."""
        cf = MTCCarryforward(
            origin_year=2023,
            original_amount=5000.0,
            amount_used=3000.0,
        )
        # Try to use more than remaining
        used = cf.use_credit(5000.0)
        assert used == 2000.0  # Limited to remaining
        assert cf.remaining == 0.0


# ============== Form 8801 Part I Tests ==============

class TestForm8801PartI:
    """Tests for Part I - Net Minimum Tax on Exclusion Items."""

    def test_exclusion_amti_calculation(self):
        """Calculate AMTI with only exclusion items."""
        form = Form8801(
            line_1_amti=300000.0,
            line_5_depreciation=-5000.0,  # Negative removes deferral
            line_7_iso=-20000.0,  # Negative removes deferral
            filing_status="single",
        )
        result = form.calculate_part_i()

        # Exclusion AMTI = 300000 - 5000 - 20000 = 275000
        assert result['line_10_exclusion_amti'] == 275000.0

    def test_exclusion_tmt_calculation(self):
        """Calculate TMT on exclusion items."""
        form = Form8801(
            line_1_amti=200000.0,
            line_7_iso=-50000.0,  # Remove ISO deferral
            filing_status="single",
        )
        result = form.calculate_part_i()

        # Exclusion AMTI = 200000 - 50000 = 150000
        # Exemption = 88100 (single)
        # AMT taxable = 150000 - 88100 = 61900
        # TMT = 61900 × 0.26 = 16094
        assert result['line_10_exclusion_amti'] == 150000.0
        assert result['line_12_amt_taxable'] == 150000.0 - 88100.0
        assert result['line_13_exclusion_tmt'] == round(61900 * 0.26, 2)

    def test_exemption_phaseout_in_part_i(self):
        """Exemption phases out based on exclusion AMTI."""
        form = Form8801(
            line_1_amti=700000.0,  # High AMTI
            line_7_iso=-50000.0,
            filing_status="single",
        )
        result = form.calculate_part_i()

        # Exclusion AMTI = 650000 (over phaseout threshold)
        # Exemption phases out
        assert result['line_10_exclusion_amti'] == 650000.0
        assert result['line_11_exemption'] < 88100.0  # Phased out


# ============== Form 8801 Part II Tests ==============

class TestForm8801PartII:
    """Tests for Part II - Minimum Tax Credit and Carryforward."""

    def test_basic_credit_calculation(self):
        """Calculate credit from prior year MTC."""
        form = Form8801(
            tax_year=2025,
            current_year_regular_tax=50000.0,
            current_year_tmt=20000.0,
            total_mtc_carryforward=15000.0,
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # Credit limit = 50000 - 20000 = 30000
        # MTC available = 15000
        # Credit allowed = min(15000, 30000) = 15000
        assert result['line_26_credit_limit'] == 30000.0
        assert result['credit_allowed'] == 15000.0
        assert result['carryforward_to_next_year'] == 0.0

    def test_credit_limited_by_limit(self):
        """Credit limited when limit < available."""
        form = Form8801(
            tax_year=2025,
            current_year_regular_tax=25000.0,
            current_year_tmt=20000.0,  # Small gap
            total_mtc_carryforward=15000.0,
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # Credit limit = 25000 - 20000 = 5000
        # Credit allowed = min(15000, 5000) = 5000
        # Carryforward = 15000 - 5000 = 10000
        assert result['line_26_credit_limit'] == 5000.0
        assert result['credit_allowed'] == 5000.0
        assert result['carryforward_to_next_year'] == 10000.0

    def test_no_credit_when_tmt_exceeds_regular(self):
        """No credit when TMT >= regular tax."""
        form = Form8801(
            tax_year=2025,
            current_year_regular_tax=15000.0,
            current_year_tmt=20000.0,  # TMT > regular
            total_mtc_carryforward=10000.0,
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # Credit limit = max(0, 15000 - 20000) = 0
        assert result['line_26_credit_limit'] == 0.0
        assert result['credit_allowed'] == 0.0
        # All carries forward
        assert result['carryforward_to_next_year'] == 10000.0

    def test_credit_from_multiple_carryforwards(self):
        """Use credit from multiple prior year carryforwards."""
        form = Form8801(
            tax_year=2025,
            current_year_regular_tax=40000.0,
            current_year_tmt=10000.0,
            mtc_carryforwards=[
                MTCCarryforward(origin_year=2022, original_amount=5000.0),
                MTCCarryforward(origin_year=2023, original_amount=8000.0),
                MTCCarryforward(origin_year=2024, original_amount=3000.0),
            ],
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # Total MTC = 5000 + 8000 + 3000 = 16000
        # Credit limit = 40000 - 10000 = 30000
        # Credit allowed = min(16000, 30000) = 16000
        assert result['line_21_prior_mtc'] == 16000.0
        assert result['credit_allowed'] == 16000.0


# ============== Full Credit Calculation Tests ==============

class TestCreditCalculation:
    """Tests for complete credit calculation."""

    def test_complete_credit_calculation(self):
        """Full Form 8801 credit calculation."""
        form = Form8801(
            tax_year=2025,
            current_year_regular_tax=60000.0,
            current_year_tmt=25000.0,
            line_1_amti=400000.0,
            line_7_iso=-100000.0,  # Remove ISO from AMTI
            total_mtc_carryforward=20000.0,
            filing_status="single",
        )
        result = form.calculate_credit()

        assert 'minimum_tax_credit' in result
        assert 'credit_limit' in result
        assert 'carryforward' in result
        assert result['credit_limit'] == 35000.0  # 60000 - 25000
        assert result['minimum_tax_credit'] == 20000.0  # All used
        assert result['carryforward'] == 0.0

    def test_credit_summary(self):
        """Get simplified credit summary."""
        form = Form8801(
            current_year_regular_tax=50000.0,
            current_year_tmt=30000.0,
            total_mtc_carryforward=10000.0,
        )
        summary = form.get_credit_summary()

        assert summary['credit_available'] == 10000.0
        assert summary['credit_limit'] == 20000.0
        assert summary['has_credit'] is True


# ============== Integration Tests ==============

class TestForm8801Integration:
    """Tests for Form 8801 integration with tax engine."""

    def test_engine_calculates_mtc(self, engine):
        """Engine calculates minimum tax credit."""
        form = Form8801(
            total_mtc_carryforward=10000.0,
        )
        tax_return = create_tax_return(
            wages=150000.0,
            form_8801=form,
        )
        breakdown = engine.calculate(tax_return)

        # Check MTC fields populated
        assert hasattr(breakdown, 'form_8801_credit_available')
        assert breakdown.form_8801_credit_available == 10000.0

    def test_engine_without_form_8801(self, engine):
        """Engine uses prior_year_amt_credit without Form 8801."""
        tax_return = create_tax_return(
            wages=150000.0,
            prior_year_amt_credit=5000.0,
        )
        breakdown = engine.calculate(tax_return)

        assert breakdown.form_8801_credit_available == 5000.0

    def test_income_helper_methods(self):
        """Income model has Form 8801 helper methods."""
        form = Form8801(
            current_year_regular_tax=40000.0,
            current_year_tmt=15000.0,
            total_mtc_carryforward=12000.0,
        )
        income = Income(
            w2_forms=[make_w2(100000.0)],
            form_8801=form,
        )

        # Test helper methods
        assert income.get_form_8801_credit_available() == 12000.0
        assert income.get_form_8801_credit_limit(40000.0, 15000.0) == 25000.0
        assert income.get_form_8801_credit_allowed(40000.0, 15000.0) == 12000.0
        assert income.has_mtc_carryforward() is True

    def test_income_helper_carryforward(self):
        """Calculate carryforward via helper."""
        form = Form8801(
            current_year_regular_tax=20000.0,
            current_year_tmt=15000.0,  # Only $5k credit limit
            total_mtc_carryforward=10000.0,
        )
        income = Income(
            w2_forms=[make_w2(100000.0)],
            form_8801=form,
        )

        # Credit limit = 5000, available = 10000
        # Carryforward = 10000 - 5000 = 5000
        assert income.get_form_8801_carryforward(20000.0, 15000.0) == 5000.0


# ============== Helper Function Tests ==============

class TestHelperFunctions:
    """Tests for Form 8801 helper functions."""

    def test_calculate_mtc_from_amt_all_deferral(self):
        """MTC from all-deferral AMT."""
        result = calculate_mtc_from_amt(
            total_amt=10000.0,
            iso_adjustment=10000.0,
        )
        assert result['mtc_generated'] == 10000.0
        assert result['deferral_percentage'] == 100.0

    def test_calculate_mtc_from_amt_mixed(self):
        """MTC from mixed deferral/exclusion AMT."""
        result = calculate_mtc_from_amt(
            total_amt=20000.0,
            iso_adjustment=10000.0,  # Deferral
            pab_interest=10000.0,  # Exclusion
        )
        # 50% deferral = 50% MTC
        assert result['mtc_generated'] == 10000.0
        assert result['deferral_percentage'] == 50.0

    def test_calculate_credit_limit(self):
        """Credit limit calculation."""
        # Regular tax > TMT
        assert calculate_credit_limit(50000.0, 20000.0) == 30000.0

        # Regular tax < TMT
        assert calculate_credit_limit(15000.0, 20000.0) == 0.0

        # Equal
        assert calculate_credit_limit(20000.0, 20000.0) == 0.0

    def test_track_mtc_carryforward_fifo(self):
        """Carryforward tracking uses FIFO."""
        carryforwards = [
            MTCCarryforward(origin_year=2022, original_amount=5000.0),
            MTCCarryforward(origin_year=2023, original_amount=8000.0),
        ]

        updated = track_mtc_carryforward(
            prior_carryforwards=carryforwards,
            current_year_mtc=0.0,
            credit_used=7000.0,
            current_year=2025,
        )

        # 2022 credit (5000) used first, then 2000 from 2023
        # Remaining: 6000 from 2023
        assert len(updated) == 1
        assert updated[0].origin_year == 2023
        assert updated[0].remaining == 6000.0

    def test_estimate_mtc_benefit(self):
        """Estimate MTC benefit."""
        result = estimate_mtc_benefit(
            mtc_available=15000.0,
            expected_regular_tax=40000.0,
            expected_tmt=20000.0,
        )

        assert result['credit_usable'] == 15000.0
        assert result['carryforward'] == 0.0
        assert result['tax_savings'] == 15000.0

    def test_estimate_mtc_benefit_limited(self):
        """Estimate when credit limit constrains."""
        result = estimate_mtc_benefit(
            mtc_available=20000.0,
            expected_regular_tax=30000.0,
            expected_tmt=25000.0,  # Only $5k limit
        )

        assert result['credit_limit'] == 5000.0
        assert result['credit_usable'] == 5000.0
        assert result['carryforward'] == 15000.0


# ============== Edge Cases ==============

class TestEdgeCases:
    """Edge case tests for Form 8801."""

    def test_zero_mtc(self):
        """Handle zero MTC carryforward."""
        form = Form8801(
            current_year_regular_tax=50000.0,
            current_year_tmt=20000.0,
            total_mtc_carryforward=0.0,
        )
        result = form.calculate_credit()

        assert result['minimum_tax_credit'] == 0.0
        assert result['carryforward'] == 0.0

    def test_zero_regular_tax(self):
        """Handle zero regular tax."""
        form = Form8801(
            current_year_regular_tax=0.0,
            current_year_tmt=0.0,
            total_mtc_carryforward=10000.0,
        )
        result = form.calculate_credit()

        # No credit limit, all carries forward
        assert result['credit_limit'] == 0.0
        assert result['minimum_tax_credit'] == 0.0
        assert result['carryforward'] == 10000.0

    def test_all_filing_statuses(self):
        """Test all filing statuses work."""
        statuses = ["single", "married_joint", "married_separate",
                    "head_of_household", "qualifying_widow"]

        for status in statuses:
            form = Form8801(
                line_1_amti=200000.0,
                filing_status=status,
                current_year_regular_tax=30000.0,
                current_year_tmt=10000.0,
                total_mtc_carryforward=5000.0,
            )
            result = form.calculate_credit()
            assert result['minimum_tax_credit'] == 5000.0

    def test_large_carryforward(self):
        """Handle large carryforward over multiple years."""
        form = Form8801(
            current_year_regular_tax=25000.0,
            current_year_tmt=20000.0,  # Only $5k limit each year
            total_mtc_carryforward=50000.0,  # 10 years to use
        )
        result = form.calculate_credit()

        assert result['minimum_tax_credit'] == 5000.0
        assert result['carryforward'] == 45000.0


# ============== Reconciliation Tests ==============

class TestReconciliation:
    """Tests for AMT to MTC reconciliation."""

    def test_reconcile_iso_only(self):
        """Reconcile AMT from ISO only."""
        result = reconcile_amt_to_mtc(
            prior_year_amti=300000.0,
            prior_year_adjustments={
                'iso_exercise': 100000.0,  # All deferral
            },
            prior_year_exemption=88100.0,
            prior_year_regular_tax=45000.0,
            filing_status="single",
        )

        assert result['deferral_adjustments'] == 100000.0
        assert result['exclusion_adjustments'] == 0.0
        # All AMT should generate MTC
        assert result['mtc_generated'] > 0

    def test_reconcile_mixed_items(self):
        """Reconcile AMT from mixed items."""
        result = reconcile_amt_to_mtc(
            prior_year_amti=350000.0,
            prior_year_adjustments={
                'iso_exercise': 50000.0,  # Deferral
                'private_activity_bond': 30000.0,  # Exclusion
            },
            prior_year_exemption=88100.0,
            prior_year_regular_tax=50000.0,
            filing_status="single",
        )

        assert result['deferral_adjustments'] == 50000.0
        assert result['exclusion_adjustments'] == 30000.0
        # MTC should be less than total AMT
        assert result['mtc_generated'] < result['total_amt']


# ============== Integration with Form 6251 ==============

class TestForm6251Integration:
    """Tests for Form 8801 + Form 6251 integration."""

    def test_mtc_reduces_amt_impact(self, engine):
        """MTC can offset regular tax from AMT scenario."""
        # Create scenario where prior ISO created AMT, now recovering
        form_6251 = Form6251(
            line_2i_iso=0.0,  # No current year ISO
        )
        form_8801 = Form8801(
            total_mtc_carryforward=10000.0,  # From prior ISO AMT
        )
        tax_return = create_tax_return(
            wages=150000.0,
            form_6251=form_6251,
            form_8801=form_8801,
        )
        breakdown = engine.calculate(tax_return)

        # Should have credit available
        assert breakdown.form_8801_credit_available == 10000.0
        # Credit should be allowed if regular tax > TMT
        if breakdown.amt_breakdown.get('regular_tax', 0) > breakdown.amt_breakdown.get('tmt', 0):
            assert breakdown.form_8801_credit_allowed > 0
