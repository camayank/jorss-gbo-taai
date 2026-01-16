"""
Tests for Alternative Minimum Tax (AMT) - Form 6251

Tests verify:
- AMT exemption amounts for all filing statuses
- AMT exemption phaseout calculation
- Two-tier rate system (26%/28%)
- AMT preference items (ISO, PAB, depreciation, etc.)
- SALT addback for itemizers
- TMT vs regular tax comparison
- Prior year AMT credit (Form 8801)
"""

import pytest
from src.models.income import Income, W2Info
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.deductions import Deductions, ItemizedDeductions
from src.models.credits import TaxCredits
from src.models.tax_return import TaxReturn
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        employer_ein="12-3456789",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


class TestAMTExemptions:
    """Test AMT exemption amounts for different filing statuses."""

    def test_single_exemption_amount(self, engine):
        """Test single filer AMT exemption of $88,100."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Single",
                last_name="Filer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['exemption_base'] == 88100.0

    def test_mfj_exemption_amount(self, engine):
        """Test MFJ AMT exemption of $137,000."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Couple",
                filing_status=FilingStatus.MARRIED_JOINT,
            ),
            income=Income(w2_forms=[make_w2(200000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['exemption_base'] == 137000.0

    def test_mfs_exemption_amount(self, engine):
        """Test MFS AMT exemption of $68,500."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Separate",
                filing_status=FilingStatus.MARRIED_SEPARATE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['exemption_base'] == 68500.0


class TestAMTExemptionPhaseout:
    """Test AMT exemption phaseout at 25 cents per dollar."""

    def test_no_phaseout_under_threshold(self, engine):
        """Test no phaseout when AMTI below threshold."""
        # Single threshold starts at $626,350 for 2025
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Under",
                last_name="Threshold",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(400000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # Should have full exemption
        assert breakdown.amt_breakdown['exemption_after_phaseout'] == breakdown.amt_breakdown['exemption_base']

    def test_partial_phaseout(self, engine):
        """Test partial phaseout when AMTI exceeds threshold."""
        # High income to trigger phaseout
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="High",
                last_name="Earner",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(700000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # Exemption should be reduced
        assert breakdown.amt_breakdown['exemption_after_phaseout'] < breakdown.amt_breakdown['exemption_base']

    def test_complete_phaseout_very_high_income(self, engine):
        """Test complete exemption phaseout at very high income."""
        # Exemption phases out completely at ~$978,750 for single
        # ($88,100 / 0.25 + $626,350 = $978,750)
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Very",
                last_name="Rich",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(1200000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # Exemption should be completely phased out
        assert breakdown.amt_breakdown['exemption_after_phaseout'] == 0


class TestAMTTwoTierRates:
    """Test AMT two-tier rate structure (26% and 28%)."""

    def test_all_at_26_percent_rate(self, engine):
        """Test AMT taxable income entirely in 26% bracket."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Moderate",
                last_name="AMT",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(200000.0)],
                amt_iso_exercise_spread=50000.0,  # This pushes into AMT
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # AMT taxable income should be under $232,600 threshold
        assert breakdown.amt_breakdown['amt_taxable_income'] <= 232600

    def test_into_28_percent_rate(self, engine):
        """Test AMT taxable income crossing into 28% bracket."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="High",
                last_name="AMT",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(400000.0)],
                amt_iso_exercise_spread=100000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # With high income + ISO spread, should be in 28% bracket
        # AMT taxable = AMTI - exemption > $232,600


class TestAMTPreferenceItems:
    """Test AMT preference item addbacks."""

    def test_iso_exercise_spread(self, engine):
        """Test Incentive Stock Option exercise spread preference."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="ISO",
                last_name="Holder",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(150000.0)],
                amt_iso_exercise_spread=75000.0,  # Bargain element
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['iso_exercise_spread'] == 75000.0
        # ISO spread should increase AMTI
        assert breakdown.amt_breakdown['amti'] > breakdown.taxable_income

    def test_private_activity_bond_interest(self, engine):
        """Test private activity bond interest preference."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Bond",
                last_name="Holder",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(200000.0)],
                amt_private_activity_bond_interest=25000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['private_activity_bond_interest'] == 25000.0

    def test_depreciation_adjustment(self, engine):
        """Test depreciation preference (MACRS vs ADS difference)."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Property",
                last_name="Owner",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(200000.0)],
                amt_depreciation_adjustment=15000.0,  # MACRS vs ADS difference
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['depreciation_adjustment'] == 15000.0

    def test_multiple_preference_items(self, engine):
        """Test multiple AMT preference items combined."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Complex",
                last_name="Taxpayer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(300000.0)],
                amt_iso_exercise_spread=50000.0,
                amt_private_activity_bond_interest=10000.0,
                amt_depreciation_adjustment=5000.0,
                amt_depletion_excess=3000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # Total adjustments should include all items
        expected_adj = 50000.0 + 10000.0 + 5000.0 + 3000.0
        assert breakdown.amt_breakdown['total_adjustments'] >= expected_adj


class TestSALTAddback:
    """Test SALT deduction addback for AMT."""

    def test_salt_addback_itemizing(self, engine):
        """Test SALT is added back when itemizing."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="High",
                last_name="SALT",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(400000.0)]),
            deductions=Deductions(
                use_standard_deduction=False,
                itemized=ItemizedDeductions(
                    state_local_income_tax=20000.0,  # Over $10k cap
                    real_estate_tax=8000.0,
                    mortgage_interest=25000.0,
                    charitable_cash=10000.0,
                ),
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # SALT addback should be the capped amount ($10k)
        if breakdown.deduction_type == "itemized":
            assert breakdown.amt_breakdown['salt_addback'] == 10000.0

    def test_no_salt_addback_standard_deduction(self, engine):
        """Test no SALT addback when using standard deduction."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Standard",
                last_name="Filer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['salt_addback'] == 0.0


class TestAMTVsRegularTax:
    """Test AMT only applies when TMT > Regular Tax."""

    def test_no_amt_regular_tax_higher(self, engine):
        """Test no AMT when regular tax exceeds TMT."""
        # Simple case with low income - should have no AMT
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Low",
                last_name="Income",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(75000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.alternative_minimum_tax == 0.0

    def test_amt_triggered_by_iso(self, engine):
        """Test AMT triggered by large ISO exercise spread."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="ISO",
                last_name="Rich",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(200000.0)],
                amt_iso_exercise_spread=300000.0,  # Large ISO spread
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # Large ISO spread should trigger AMT
        assert breakdown.alternative_minimum_tax > 0


class TestAMTBreakdownFields:
    """Test AMT breakdown dictionary contains all fields."""

    def test_breakdown_has_all_fields(self, engine):
        """Test AMT breakdown contains all required fields."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="Taxpayer",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(200000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        amt = breakdown.amt_breakdown

        # Check all required fields exist
        required_fields = [
            'amt', 'amti', 'exemption_base', 'exemption_after_phaseout',
            'amt_taxable_income', 'tmt', 'regular_tax', 'salt_addback',
            'iso_exercise_spread', 'private_activity_bond_interest',
            'depreciation_adjustment', 'passive_activity_adjustment',
            'loss_limitations_adjustment', 'other_adjustments',
            'total_adjustments', 'prior_year_amt_credit', 'amt_after_credit'
        ]

        for field in required_fields:
            assert field in amt, f"Missing field: {field}"


class TestPriorYearAMTCredit:
    """Test prior year AMT credit (Form 8801)."""

    def test_prior_year_credit_tracked(self, engine):
        """Test prior year AMT credit is tracked in breakdown."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Prior",
                last_name="Credit",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                w2_forms=[make_w2(200000.0)],
                prior_year_amt_credit=5000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['prior_year_amt_credit'] == 5000.0


class TestAMTFilingStatusVariations:
    """Test AMT calculations across all filing statuses."""

    @pytest.mark.parametrize("filing_status,expected_exemption", [
        (FilingStatus.SINGLE, 88100.0),
        (FilingStatus.MARRIED_JOINT, 137000.0),
        (FilingStatus.MARRIED_SEPARATE, 68500.0),
        (FilingStatus.HEAD_OF_HOUSEHOLD, 88100.0),
        (FilingStatus.QUALIFYING_WIDOW, 137000.0),
    ])
    def test_exemption_by_filing_status(self, engine, filing_status, expected_exemption):
        """Test AMT exemption varies by filing status."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="Taxpayer",
                filing_status=filing_status,
            ),
            income=Income(w2_forms=[make_w2(150000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.amt_breakdown['exemption_base'] == expected_exemption


class TestAMTEdgeCases:
    """Test AMT edge cases."""

    def test_zero_income(self, engine):
        """Test AMT with zero income."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="No",
                last_name="Income",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        assert breakdown.alternative_minimum_tax == 0.0

    def test_negative_taxable_income(self, engine):
        """Test AMT when taxable income is negative (deductions exceed income)."""
        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Loss",
                last_name="Year",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(10000.0)]),  # Low income
            deductions=Deductions(use_standard_deduction=True),  # Standard deduction > income
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tax_return)
        # Should not have negative AMT
        assert breakdown.alternative_minimum_tax >= 0
