"""
Tests for Form 6251 - Alternative Minimum Tax - Individuals

Tests cover:
- AMTI calculation (Part I)
- AMT exemption with phaseout (Part II)
- Tentative Minimum Tax at 26%/28% rates
- AMT calculation (TMT vs Regular Tax)
- ISO exercise spread calculations
- Private activity bond interest preferences
- Depreciation adjustments
- Prior year AMT credit
- Integration with tax calculation engine
- Helper functions
"""

import pytest
from models.form_6251 import (
    Form6251,
    ISOExercise,
    PrivateActivityBond,
    DepreciationAdjustment,
    AMTAdjustment,
    AMTAdjustmentType,
    calculate_amt_exemption_phaseout,
    calculate_tentative_minimum_tax,
    check_amt_likely,
)
from models.income import Income, W2Info
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions, ItemizedDeductions
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
    form_6251: Form6251 = None,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    itemized: ItemizedDeductions = None,
) -> TaxReturn:
    """Helper to create TaxReturn with Form 6251."""
    deductions = Deductions(use_standard_deduction=True)
    if itemized:
        deductions = Deductions(
            use_standard_deduction=False,
            itemized=itemized
        )

    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
        ),
        income=Income(
            w2_forms=[make_w2(wages, wages * 0.20)],
            form_6251=form_6251,
        ),
        deductions=deductions,
        credits=TaxCredits(),
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


# ============== ISO Exercise Tests ==============

class TestISOExercise:
    """Tests for Incentive Stock Option exercise calculations."""

    def test_iso_spread_calculation(self):
        """Calculate ISO spread (bargain element)."""
        iso = ISOExercise(
            company_name="TechCorp",
            exercise_date="2025-06-15",
            shares_exercised=1000,
            exercise_price_per_share=10.0,
            fmv_per_share_at_exercise=50.0,
        )
        # Spread = FMV - Exercise = $50 - $10 = $40 per share
        assert iso.get_spread() == 40.0
        # Total spread = 1000 shares × $40 = $40,000
        assert iso.get_total_spread() == 40000.0
        # AMT adjustment equals total spread
        assert iso.get_amt_adjustment() == 40000.0

    def test_iso_same_year_sale_no_amt(self):
        """Same-year sale is disqualifying disposition - no AMT."""
        iso = ISOExercise(
            company_name="TechCorp",
            exercise_date="2025-06-15",
            shares_exercised=1000,
            exercise_price_per_share=10.0,
            fmv_per_share_at_exercise=50.0,
            same_year_sale=True,
            sale_price_per_share=55.0,
        )
        # Same year sale = disqualifying disposition = no AMT preference
        assert iso.get_amt_adjustment() == 0.0

    def test_iso_negative_spread_zero(self):
        """ISO spread cannot be negative (underwater options)."""
        iso = ISOExercise(
            company_name="TechCorp",
            exercise_date="2025-06-15",
            shares_exercised=1000,
            exercise_price_per_share=50.0,
            fmv_per_share_at_exercise=30.0,  # FMV < exercise (underwater)
        )
        # Spread is max(0, FMV - exercise) = 0
        assert iso.get_spread() == 0.0
        assert iso.get_amt_adjustment() == 0.0


# ============== Private Activity Bond Tests ==============

class TestPrivateActivityBond:
    """Tests for private activity bond interest calculations."""

    def test_pab_post_1986(self):
        """Post-1986 PAB interest is AMT preference."""
        pab = PrivateActivityBond(
            bond_name="Municipal Airport Bond",
            interest_received=5000.0,
            is_post_1986=True,
        )
        assert pab.get_amt_adjustment() == 5000.0

    def test_pab_pre_1986_exempt(self):
        """Pre-August 7, 1986 PAB interest is NOT AMT preference."""
        pab = PrivateActivityBond(
            bond_name="Old Municipal Bond",
            interest_received=5000.0,
            is_post_1986=False,
        )
        assert pab.get_amt_adjustment() == 0.0


# ============== Depreciation Adjustment Tests ==============

class TestDepreciationAdjustment:
    """Tests for depreciation adjustments (MACRS vs ADS)."""

    def test_positive_adjustment(self):
        """MACRS > ADS = positive adjustment (add to AMTI)."""
        dep = DepreciationAdjustment(
            asset_description="Equipment",
            regular_depreciation=10000.0,  # MACRS
            amt_depreciation=7000.0,  # ADS (slower)
        )
        # Adjustment = MACRS - ADS = $10,000 - $7,000 = $3,000
        assert dep.get_adjustment() == 3000.0

    def test_negative_adjustment(self):
        """ADS > MACRS in later years = negative adjustment."""
        dep = DepreciationAdjustment(
            asset_description="Equipment Year 5",
            regular_depreciation=5000.0,
            amt_depreciation=8000.0,  # ADS catches up
        )
        # Adjustment = $5,000 - $8,000 = -$3,000
        assert dep.get_adjustment() == -3000.0


# ============== Form 6251 Part I Tests ==============

class TestForm6251PartI:
    """Tests for Part I - Alternative Minimum Taxable Income."""

    def test_basic_amti_calculation(self):
        """Calculate AMTI from taxable income + adjustments."""
        form = Form6251(
            taxable_income=200000.0,
            line_2a_taxes=10000.0,  # SALT addback
            line_2i_iso=50000.0,  # ISO spread
        )
        result = form.calculate_part_i()

        assert result['line_1_taxable_income'] == 200000.0
        assert result['adjustments']['line_2a_taxes'] == 10000.0
        assert result['adjustments']['line_2i_iso'] == 50000.0
        # AMTI = 200000 + 10000 + 50000 = 260000
        assert result['line_4_amti'] == 260000.0
        assert result['total_adjustments'] == 60000.0

    def test_amti_with_iso_records(self):
        """AMTI includes ISO from detailed records."""
        form = Form6251(
            taxable_income=200000.0,
            iso_exercises=[
                ISOExercise(
                    company_name="TechCorp",
                    exercise_date="2025-06-15",
                    shares_exercised=500,
                    exercise_price_per_share=10.0,
                    fmv_per_share_at_exercise=30.0,
                ),
                ISOExercise(
                    company_name="StartupInc",
                    exercise_date="2025-08-01",
                    shares_exercised=1000,
                    exercise_price_per_share=5.0,
                    fmv_per_share_at_exercise=15.0,
                ),
            ],
        )
        result = form.calculate_part_i()

        # ISO 1: 500 × ($30 - $10) = $10,000
        # ISO 2: 1000 × ($15 - $5) = $10,000
        # Total: $20,000
        assert result['adjustments']['line_2i_iso'] == 20000.0
        assert result['line_4_amti'] == 220000.0

    def test_amti_with_pab_records(self):
        """AMTI includes PAB interest from records."""
        form = Form6251(
            taxable_income=150000.0,
            private_activity_bonds=[
                PrivateActivityBond(
                    bond_name="Airport Bond",
                    interest_received=3000.0,
                    is_post_1986=True,
                ),
                PrivateActivityBond(
                    bond_name="Old Bond",
                    interest_received=2000.0,
                    is_post_1986=False,
                ),
            ],
        )
        result = form.calculate_part_i()

        # Only post-1986 bonds are AMT preference
        assert result['adjustments']['line_2g_pab_interest'] == 3000.0
        assert result['line_4_amti'] == 153000.0

    def test_amti_with_depreciation_records(self):
        """AMTI includes depreciation adjustments from records."""
        form = Form6251(
            taxable_income=300000.0,
            depreciation_adjustments=[
                DepreciationAdjustment(
                    asset_description="Building",
                    regular_depreciation=15000.0,
                    amt_depreciation=12000.0,
                ),
                DepreciationAdjustment(
                    asset_description="Equipment",
                    regular_depreciation=8000.0,
                    amt_depreciation=5000.0,
                ),
            ],
        )
        result = form.calculate_part_i()

        # Depreciation adj: (15000-12000) + (8000-5000) = 3000 + 3000 = 6000
        assert result['adjustments']['line_2l_depreciation'] == 6000.0
        assert result['line_4_amti'] == 306000.0


# ============== Form 6251 Part II Tests ==============

class TestForm6251PartII:
    """Tests for Part II - AMT Exemption and TMT."""

    def test_exemption_single_no_phaseout(self):
        """Single filer below phaseout threshold."""
        form = Form6251(
            taxable_income=200000.0,
            filing_status="single",
        )
        result = form.calculate_part_ii()

        assert result['line_5_exemption_base'] == 88100.0
        assert result['line_7_exemption_after_phaseout'] == 88100.0
        # AMT taxable = 200000 - 88100 = 111900
        assert result['line_8_amt_taxable_income'] == 111900.0

    def test_exemption_mfj_no_phaseout(self):
        """Married filing jointly below phaseout."""
        form = Form6251(
            taxable_income=400000.0,
            filing_status="married_joint",
        )
        result = form.calculate_part_ii()

        assert result['line_5_exemption_base'] == 137000.0
        assert result['line_7_exemption_after_phaseout'] == 137000.0

    def test_exemption_mfs_half(self):
        """Married filing separately gets half exemption."""
        form = Form6251(
            taxable_income=200000.0,
            filing_status="married_separate",
        )
        result = form.calculate_part_ii()

        assert result['line_5_exemption_base'] == 68500.0

    def test_exemption_phaseout_single(self):
        """Exemption phases out at 25 cents per dollar."""
        form = Form6251(
            taxable_income=700000.0,  # Over $626,350 threshold
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # Excess over threshold: 700000 - 626350 = 73650
        # Reduction: 73650 × 0.25 = 18412.50
        # Exemption: 88100 - 18412.50 = 69687.50
        assert result['line_6_excess_over_threshold'] == 73650.0
        assert result['line_7_exemption_reduction'] == 73650 * 0.25
        assert result['line_7_exemption_after_phaseout'] == 88100.0 - (73650 * 0.25)

    def test_exemption_fully_phased_out(self):
        """Exemption fully phased out at high AMTI."""
        # Exemption phases out when AMTI > phaseout_start + (exemption / 0.25)
        # For single: 626350 + (88100 / 0.25) = 626350 + 352400 = 978750
        form = Form6251(
            taxable_income=1000000.0,  # Over full phaseout
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # Excess: 1000000 - 626350 = 373650
        # Reduction: 373650 × 0.25 = 93412.50 (exceeds 88100)
        # Exemption: max(0, 88100 - 93412.50) = 0
        assert result['line_7_exemption_after_phaseout'] == 0.0

    def test_tmt_26_percent_rate(self):
        """TMT at 26% rate below threshold."""
        form = Form6251(
            taxable_income=200000.0,
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # AMT taxable = 200000 - 88100 = 111900
        # TMT at 26%: 111900 × 0.26 = 29094
        assert result['line_8_amt_taxable_income'] == 111900.0
        assert result['line_11_tentative_minimum_tax'] == round(111900 * 0.26, 2)

    def test_tmt_28_percent_rate_kicks_in(self):
        """TMT at 28% rate above threshold."""
        form = Form6251(
            taxable_income=400000.0,  # Will have AMT taxable > 232600
            filing_status="single",
        )
        result = form.calculate_part_ii()

        # AMT taxable = 400000 - 88100 = 311900
        # 26% on first 232600: 232600 × 0.26 = 60476
        # 28% on excess: (311900 - 232600) × 0.28 = 79300 × 0.28 = 22204
        # TMT = 60476 + 22204 = 82680
        expected_tmt = (232600 * 0.26) + ((311900 - 232600) * 0.28)
        assert result['line_8_amt_taxable_income'] == 311900.0
        assert result['line_11_tentative_minimum_tax'] == round(expected_tmt, 2)


# ============== Full AMT Calculation Tests ==============

class TestAMTCalculation:
    """Tests for complete AMT calculation."""

    def test_no_amt_when_tmt_less_than_regular(self):
        """No AMT when TMT < regular tax."""
        form = Form6251(
            taxable_income=100000.0,
            filing_status="single",
        )
        # Regular tax on $100k single ~= $17,400
        # AMT taxable = 100000 - 88100 = 11900
        # TMT = 11900 × 0.26 = 3094
        # AMT = max(0, 3094 - 17400) = 0
        result = form.calculate_amt(regular_tax=17400.0)

        assert result['amt'] == 0.0
        assert result['has_amt_liability'] is False

    def test_amt_when_tmt_exceeds_regular(self):
        """AMT due when TMT > regular tax."""
        form = Form6251(
            taxable_income=150000.0,
            line_2i_iso=100000.0,  # Large ISO spread
            filing_status="single",
        )
        # AMTI = 150000 + 100000 = 250000
        # Exemption = 88100 (no phaseout yet at 250k)
        # AMT taxable = 250000 - 88100 = 161900
        # TMT = 161900 × 0.26 = 42094
        # Regular tax on $150k ~= $30,000
        result = form.calculate_amt(regular_tax=30000.0)

        # AMT = max(0, 42094 - 30000) = 12094
        assert result['amt'] > 0
        assert result['has_amt_liability'] is True

    def test_prior_year_amt_credit_applied(self):
        """Prior year AMT credit reduces current AMT."""
        form = Form6251(
            taxable_income=200000.0,
            line_2i_iso=100000.0,
            prior_year_amt_credit=5000.0,
            filing_status="single",
        )
        result = form.calculate_amt(regular_tax=40000.0)

        # AMT before credit
        amt_before = result['amt']
        # AMT after credit
        amt_after = result['amt_after_credit']

        assert amt_after == max(0, amt_before - 5000.0)
        assert result['prior_year_credit_used'] == min(5000.0, amt_before)


# ============== Integration Tests ==============

class TestForm6251Integration:
    """Tests for Form 6251 integration with tax engine."""

    def test_engine_uses_form_6251(self, engine):
        """Engine calculates AMT using Form 6251."""
        form = Form6251(
            line_2i_iso=50000.0,  # ISO spread
        )
        tax_return = create_tax_return(wages=150000.0, form_6251=form)
        breakdown = engine.calculate(tax_return)

        # AMT should be calculated
        assert 'amt_breakdown' in dir(breakdown)
        assert breakdown.amt_breakdown['iso_exercise_spread'] == 50000.0

    def test_engine_without_form_6251(self, engine):
        """Engine falls back to individual AMT fields."""
        tax_return = create_tax_return(wages=150000.0)
        tax_return.income.amt_iso_exercise_spread = 50000.0

        breakdown = engine.calculate(tax_return)

        assert breakdown.amt_breakdown['iso_exercise_spread'] == 50000.0

    def test_engine_with_salt_itemizing(self, engine):
        """Engine adds SALT when itemizing."""
        # Need enough itemized to exceed standard deduction (~$15,200)
        # SALT: $10,000 (capped), Mortgage: $12,000 = $22,000 total
        itemized = ItemizedDeductions(
            state_local_income_tax=15000.0,  # Over $10k cap
            real_estate_tax=8000.0,
            mortgage_interest=12000.0,  # Additional to exceed standard
        )
        form = Form6251()
        tax_return = create_tax_return(
            wages=300000.0,
            form_6251=form,
            itemized=itemized,
        )
        breakdown = engine.calculate(tax_return)

        # Verify itemized was used
        assert breakdown.deduction_type == "itemized"
        # SALT should be added back (up to $10k cap)
        assert breakdown.amt_breakdown['salt_addback'] == 10000.0

    def test_income_helper_methods(self):
        """Income model has Form 6251 helper methods."""
        form = Form6251(
            taxable_income=200000.0,
            line_2i_iso=30000.0,
            line_2g_pab_interest=5000.0,
        )
        income = Income(
            w2_forms=[make_w2(200000.0)],
            form_6251=form,
        )

        assert income.get_form_6251_iso_spread() == 30000.0
        assert income.get_form_6251_pab_interest() == 5000.0
        assert income.has_amt_preference_items() is True


# ============== Helper Function Tests ==============

class TestHelperFunctions:
    """Tests for Form 6251 helper functions."""

    def test_exemption_phaseout_below_threshold(self):
        """No phaseout below threshold."""
        result = calculate_amt_exemption_phaseout(
            amti=500000.0,
            filing_status="single",
        )
        assert result['exemption_after_phaseout'] == 88100.0
        assert result['fully_phased_out'] is False

    def test_exemption_phaseout_above_threshold(self):
        """Partial phaseout above threshold."""
        result = calculate_amt_exemption_phaseout(
            amti=700000.0,
            filing_status="single",
        )
        # Excess: 700000 - 626350 = 73650
        # Reduction: 73650 × 0.25 = 18412.50
        expected = 88100.0 - (73650 * 0.25)
        assert result['exemption_after_phaseout'] == expected

    def test_tmt_calculation_26_only(self):
        """TMT at 26% only."""
        result = calculate_tentative_minimum_tax(
            amt_taxable_income=100000.0,
            filing_status="single",
        )
        assert result['tax_at_26'] == round(100000 * 0.26, 2)
        assert result['tax_at_28'] == 0.0
        assert result['tmt'] == round(100000 * 0.26, 2)

    def test_tmt_calculation_26_and_28(self):
        """TMT at both 26% and 28%."""
        result = calculate_tentative_minimum_tax(
            amt_taxable_income=300000.0,
            filing_status="single",
        )
        # 26% on 232600, 28% on remainder
        tax_26 = 232600 * 0.26
        tax_28 = (300000 - 232600) * 0.28
        assert result['tax_at_26'] == round(tax_26, 2)
        assert result['tax_at_28'] == round(tax_28, 2)
        assert result['tmt'] == round(tax_26 + tax_28, 2)

    def test_check_amt_likely_iso(self):
        """Large ISO spread triggers AMT warning."""
        result = check_amt_likely(
            taxable_income=200000.0,
            salt_deduction=10000.0,
            iso_spread=75000.0,
            filing_status="single",
        )
        assert result['likely_amt'] is True
        assert "ISO exercise spread" in str(result['risk_factors'])

    def test_check_amt_likely_high_salt(self):
        """High SALT deduction is a risk factor."""
        result = check_amt_likely(
            taxable_income=200000.0,
            salt_deduction=15000.0,  # Over $10k
            filing_status="single",
        )
        assert "High SALT deduction" in str(result['risk_factors'])

    def test_check_amt_unlikely_low_income(self):
        """Low income unlikely to have AMT."""
        result = check_amt_likely(
            taxable_income=75000.0,
            salt_deduction=5000.0,
            filing_status="single",
        )
        assert result['likely_amt'] is False


# ============== Edge Cases ==============

class TestEdgeCases:
    """Edge case tests for Form 6251."""

    def test_zero_taxable_income(self):
        """Handle zero taxable income."""
        form = Form6251(
            taxable_income=0.0,
            line_2i_iso=50000.0,  # ISO creates positive AMTI
        )
        result = form.calculate_amt(regular_tax=0.0)

        # AMTI = 0 + 50000 = 50000
        # Below exemption, so no AMT
        assert result['amti'] == 50000.0
        assert result['amt'] == 0.0

    def test_negative_taxable_income(self):
        """Handle negative taxable income (NOL)."""
        form = Form6251(
            taxable_income=-10000.0,  # NOL
            line_2i_iso=100000.0,
        )
        result = form.calculate_part_i()

        # AMTI = -10000 + 100000 = 90000
        assert result['line_4_amti'] == 90000.0

    def test_all_filing_statuses(self):
        """Test all filing status exemptions."""
        statuses = [
            ("single", 88100.0),
            ("married_joint", 137000.0),
            ("married_separate", 68500.0),
            ("head_of_household", 88100.0),
            ("qualifying_widow", 137000.0),
        ]
        for status, expected_exemption in statuses:
            form = Form6251(
                taxable_income=200000.0,
                filing_status=status,
            )
            result = form.calculate_part_ii()
            assert result['line_5_exemption_base'] == expected_exemption

    def test_mfs_28_threshold_half(self):
        """MFS has half the 28% threshold."""
        form = Form6251(
            taxable_income=200000.0,
            filing_status="married_separate",
        )
        result = form.calculate_part_ii()

        # MFS threshold is $116,300 (half of $232,600)
        # AMT taxable = 200000 - 68500 = 131500
        # This is over $116,300, so 28% applies
        threshold = 116300
        amt_taxable = 200000 - 68500
        expected_tmt = (threshold * 0.26) + ((amt_taxable - threshold) * 0.28)

        assert result['line_11_tentative_minimum_tax'] == round(expected_tmt, 2)

    def test_large_prior_year_credit(self):
        """Prior year credit larger than AMT."""
        form = Form6251(
            taxable_income=200000.0,
            line_2i_iso=50000.0,
            prior_year_amt_credit=100000.0,  # Very large credit
            filing_status="single",
        )
        result = form.calculate_amt(regular_tax=30000.0)

        # Credit cannot reduce AMT below zero
        assert result['amt_after_credit'] >= 0.0

    def test_multiple_adjustment_types(self):
        """Multiple AMT adjustments combine correctly."""
        form = Form6251(
            taxable_income=300000.0,
            line_2a_taxes=10000.0,
            line_2i_iso=25000.0,
            line_2g_pab_interest=5000.0,
            line_2l_depreciation=3000.0,
            line_2m_passive_activities=2000.0,
            filing_status="single",
        )
        result = form.calculate_part_i()

        total = 10000 + 25000 + 5000 + 3000 + 2000
        assert result['total_adjustments'] == total
        assert result['line_4_amti'] == 300000 + total


# ============== AMT Summary Tests ==============

class TestAMTSummary:
    """Tests for AMT summary generation."""

    def test_summary_basic(self):
        """Basic AMT summary."""
        form = Form6251(
            taxable_income=200000.0,
            line_2a_taxes=10000.0,
            line_2i_iso=30000.0,
            filing_status="single",
        )
        summary = form.get_amt_summary()

        assert summary['amti'] == 240000.0
        assert summary['total_adjustments'] == 40000.0
        assert summary['major_adjustments']['salt_addback'] == 10000.0
        assert summary['major_adjustments']['iso_spread'] == 30000.0

    def test_summary_may_owe_amt(self):
        """Summary indicates AMT likelihood."""
        # High income over phaseout threshold
        form = Form6251(
            taxable_income=700000.0,
            filing_status="single",
        )
        summary = form.get_amt_summary()

        assert summary['may_owe_amt'] is True


# ============== Part III Capital Gains Tests ==============

class TestForm6251PartIII:
    """Tests for Part III - Capital Gains under AMT."""

    def test_no_capital_gains(self):
        """No Part III when no preferential income."""
        form = Form6251(
            taxable_income=200000.0,
            filing_status="single",
        )
        result = form.calculate_part_iii(amt_taxable_income=111900.0)

        assert result['uses_part_iii'] is False

    def test_with_capital_gains(self):
        """Part III applies with capital gains."""
        form = Form6251(
            taxable_income=200000.0,
            net_capital_gain=50000.0,
            qualified_dividends=10000.0,
            filing_status="single",
        )
        result = form.calculate_part_iii(
            amt_taxable_income=111900.0,
            regular_tax_capital_gains=9000.0,
        )

        assert result['uses_part_iii'] is True
        assert result['total_preferential_income'] == 60000.0
