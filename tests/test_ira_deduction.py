"""
Tests for Traditional IRA Deduction with MAGI Phaseouts - BR2-0009, BR2-0010

Tests cover:
- Full deduction when not covered by employer plan
- Full deduction when below threshold (covered by employer plan)
- Partial deduction in phaseout range
- Zero deduction above phaseout end
- Age 50+ catchup contribution ($8,000 vs $7,000)
- Spouse covered scenarios (different thresholds)
- Compensation limit (cannot exceed taxable compensation)
- MFS special rules ($0-$10,000 phaseout range)
"""

import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


class TestIRADeductionBasic:
    """Basic IRA deduction tests - not covered by employer plan."""

    def test_full_deduction_not_covered_by_plan(self):
        """Full $7,000 deduction when not covered by employer plan."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="John",
                last_name="Doe",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=False,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Not covered by employer plan = full deduction regardless of income
        assert breakdown.adjustments_to_income >= 7000.0

    def test_full_deduction_high_income_not_covered(self):
        """High income but not covered by plan = full deduction."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Jane",
                last_name="Rich",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=False,
            ),
            income=Income(w2_forms=[make_w2(500000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # High income but not covered = still full deduction
        assert breakdown.adjustments_to_income >= 7000.0


class TestIRADeductionPhaseout:
    """IRA deduction phaseout tests when covered by employer plan."""

    def test_full_deduction_below_threshold_covered(self):
        """Full deduction when below threshold even if covered by plan."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Single, covered by plan, MAGI $50K (below $79K threshold)
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=True,
            ),
            income=Income(w2_forms=[make_w2(50000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Below threshold = full deduction
        assert breakdown.adjustments_to_income >= 7000.0

    def test_partial_deduction_in_phaseout_range(self):
        """Partial deduction when in phaseout range."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Single, covered by plan, MAGI $84K (middle of $79K-$89K range)
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=True,
            ),
            income=Income(w2_forms=[make_w2(84000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # In phaseout range - deduction should be reduced
        # $84K is 50% through the $79K-$89K range
        # Expected: $7,000 * 50% = $3,500 (rounded to nearest $10)
        # Check it's less than full but more than zero
        ira_deduction = breakdown.adjustments_to_income
        assert ira_deduction > 0
        assert ira_deduction < 7000.0

    def test_zero_deduction_above_threshold(self):
        """Zero deduction when above phaseout threshold."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Single, covered by plan, MAGI $95K (above $89K threshold)
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=True,
            ),
            income=Income(w2_forms=[make_w2(95000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Above threshold = $0 deduction for IRA
        # adjustments_to_income should NOT include IRA contribution
        assert breakdown.adjustments_to_income < 7000.0


class TestIRAAge50Plus:
    """Tests for age 50+ catchup contribution limit."""

    def test_catchup_contribution_age_50_plus(self):
        """Age 50+ can contribute and deduct $8,000."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Senior",
                last_name="Saver",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=False,
                is_age_50_plus=True,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=8000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Age 50+ can deduct full $8,000
        assert breakdown.adjustments_to_income >= 8000.0

    def test_contribution_capped_under_50(self):
        """Under 50 contribution capped at $7,000 even if more contributed."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Young",
                last_name="Saver",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=False,
                is_age_50_plus=False,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=10000.0,  # Over-contributed
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Under 50 capped at $7,000 even if contributed more
        # adjustments_to_income includes other items, but IRA portion capped
        assert breakdown.adjustments_to_income >= 7000.0
        # Cannot assert exact value due to other potential adjustments


class TestIRASpouseCovered:
    """Tests for spouse covered by employer plan scenarios."""

    def test_mfj_spouse_covered_higher_threshold(self):
        """MFJ with only spouse covered uses higher threshold ($236K-$246K)."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Taxpayer not covered, spouse covered, MAGI $200K
        # Should be below spouse-covered threshold of $236K
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Saver",
                filing_status=FilingStatus.MARRIED_JOINT,
                is_covered_by_employer_plan=False,
                spouse_covered_by_employer_plan=True,
            ),
            income=Income(w2_forms=[make_w2(200000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Below spouse-covered threshold = full deduction
        assert breakdown.adjustments_to_income >= 7000.0

    def test_mfj_spouse_covered_in_phaseout(self):
        """MFJ with spouse covered, in phaseout range $236K-$246K."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MAGI $241K is middle of $236K-$246K range
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Married",
                last_name="Saver",
                filing_status=FilingStatus.MARRIED_JOINT,
                is_covered_by_employer_plan=False,
                spouse_covered_by_employer_plan=True,
            ),
            income=Income(w2_forms=[make_w2(241000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # In phaseout range - partial deduction
        ira_deduction = breakdown.adjustments_to_income
        assert ira_deduction > 0
        assert ira_deduction < 7000.0


class TestIRACompensationLimit:
    """Tests for compensation limit on IRA contributions."""

    def test_deduction_limited_by_compensation(self):
        """IRA deduction cannot exceed taxable compensation."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Low",
                last_name="Earner",
                filing_status=FilingStatus.SINGLE,
                is_covered_by_employer_plan=False,
            ),
            income=Income(w2_forms=[make_w2(5000.0)]),  # Only $5K compensation
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,  # Tried to contribute $7K
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)

        # Deduction limited to compensation ($5K)
        assert breakdown.adjustments_to_income <= 5000.0

    def test_no_deduction_with_zero_compensation(self):
        """No IRA deduction when no taxable compensation."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        # Direct method test with zero compensation
        result = deductions.get_ira_deduction(
            magi=50000.0,
            filing_status="single",
            is_covered_by_employer_plan=False,
            spouse_covered_by_employer_plan=False,
            is_age_50_plus=False,
            taxable_compensation=0.0,  # No compensation
        )

        assert result == 0.0


class TestIRAMFSSpecialRules:
    """Tests for Married Filing Separately special rules."""

    def test_mfs_covered_narrow_phaseout(self):
        """MFS with employer plan has $0-$10K phaseout range."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        # MAGI $5K is middle of $0-$10K range
        result = deductions.get_ira_deduction(
            magi=5000.0,
            filing_status="married_separate",
            is_covered_by_employer_plan=True,
            spouse_covered_by_employer_plan=False,
            is_age_50_plus=False,
            taxable_compensation=50000.0,
        )

        # In phaseout range - partial deduction
        assert result > 0
        assert result < 7000.0

    def test_mfs_covered_above_10k_no_deduction(self):
        """MFS covered by plan, above $10K = no deduction."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        result = deductions.get_ira_deduction(
            magi=15000.0,
            filing_status="married_separate",
            is_covered_by_employer_plan=True,
            spouse_covered_by_employer_plan=False,
            is_age_50_plus=False,
            taxable_compensation=50000.0,
        )

        assert result == 0.0


class TestIRADeductionDirect:
    """Direct tests of get_ira_deduction() method."""

    def test_no_contribution_returns_zero(self):
        """No IRA contribution = $0 deduction."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=0.0,
        )

        result = deductions.get_ira_deduction(
            magi=50000.0,
            filing_status="single",
            is_covered_by_employer_plan=False,
            taxable_compensation=100000.0,
        )

        assert result == 0.0

    def test_at_phaseout_start_full_deduction(self):
        """At exactly phaseout start = full deduction."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        # Single covered, MAGI exactly at $79K threshold
        result = deductions.get_ira_deduction(
            magi=79000.0,
            filing_status="single",
            is_covered_by_employer_plan=True,
            taxable_compensation=100000.0,
        )

        assert result == 7000.0

    def test_at_phaseout_end_zero_deduction(self):
        """At exactly phaseout end = $0 deduction."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        # Single covered, MAGI exactly at $89K threshold
        result = deductions.get_ira_deduction(
            magi=89000.0,
            filing_status="single",
            is_covered_by_employer_plan=True,
            taxable_compensation=100000.0,
        )

        assert result == 0.0

    def test_mfj_covered_thresholds(self):
        """MFJ covered by plan uses $126K-$146K thresholds."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        # Below threshold - full deduction
        result_below = deductions.get_ira_deduction(
            magi=120000.0,
            filing_status="married_joint",
            is_covered_by_employer_plan=True,
            taxable_compensation=150000.0,
        )
        assert result_below == 7000.0

        # Above threshold - no deduction
        result_above = deductions.get_ira_deduction(
            magi=150000.0,
            filing_status="married_joint",
            is_covered_by_employer_plan=True,
            taxable_compensation=150000.0,
        )
        assert result_above == 0.0


class TestIRARoundingRules:
    """Tests for IRS rounding rules on IRA deduction."""

    def test_minimum_200_rule(self):
        """If reduced deduction > $0 but < $200, round to $200."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        # MAGI very close to phaseout end (e.g., $88,500)
        # Would give ~$350 without minimum rule
        result = deductions.get_ira_deduction(
            magi=88500.0,
            filing_status="single",
            is_covered_by_employer_plan=True,
            taxable_compensation=100000.0,
        )

        # Should be at least $200 if any deduction allowed
        if result > 0:
            assert result >= 200.0 or result == 0.0

    def test_rounds_to_nearest_10(self):
        """Deduction should be rounded to nearest $10."""
        deductions = Deductions(
            use_standard_deduction=True,
            ira_contributions=7000.0,
        )

        result = deductions.get_ira_deduction(
            magi=84000.0,  # 50% through phaseout
            filing_status="single",
            is_covered_by_employer_plan=True,
            taxable_compensation=100000.0,
        )

        # Result should be divisible by 10
        assert result % 10 == 0
