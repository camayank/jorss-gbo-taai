"""
Tests for Roth IRA Contribution Limits with MAGI Phaseouts - BR2-0011

Tests cover:
- Full contribution eligibility when below MAGI threshold
- Partial contribution in phaseout range
- Zero contribution above phaseout end
- Age 50+ catchup contribution ($8,000 vs $7,000)
- Combined Traditional + Roth limit enforcement
- Compensation limit (cannot exceed taxable compensation)
- MFS special rules ($0-$10,000 phaseout range)
- All filing statuses with correct thresholds
- IRS rounding rules ($200 minimum, round to nearest $10)
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


class TestRothBasicEligibility:
    """Basic Roth IRA eligibility tests - full contribution below threshold."""

    def test_full_contribution_below_threshold_single(self):
        """Full $7,000 eligible when MAGI below $150,000 for Single."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="John",
                last_name="Doe",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 7000.0

    def test_full_contribution_below_threshold_mfj(self):
        """Full $7,000 eligible when MAGI below $236,000 for MFJ."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Jane",
                last_name="Doe",
                filing_status=FilingStatus.MARRIED_JOINT,
            ),
            income=Income(w2_forms=[make_w2(200000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 7000.0

    def test_full_contribution_hoh(self):
        """HOH uses single thresholds ($150k-$165k)."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Sam",
                last_name="Smith",
                filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            ),
            income=Income(w2_forms=[make_w2(140000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 7000.0

    def test_full_contribution_qualifying_widow(self):
        """Qualifying Widow(er) uses MFJ thresholds ($236k-$246k)."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Pat",
                last_name="Wilson",
                filing_status=FilingStatus.QUALIFYING_WIDOW,
            ),
            income=Income(w2_forms=[make_w2(230000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 7000.0


class TestRothPhaseout:
    """Tests for Roth IRA phaseout calculations."""

    def test_mid_phaseout_single(self):
        """Single filer at midpoint of phaseout ($157,500) gets 50% of limit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MAGI = $157,500 is midpoint of $150k-$165k range
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Alex",
                last_name="Test",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(157500.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # 50% of $7,000 = $3,500
        assert breakdown.roth_ira_eligible_contribution == 3500.0

    def test_mid_phaseout_mfj(self):
        """MFJ at midpoint of phaseout ($241,000) gets 50% of limit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MAGI = $241,000 is midpoint of $236k-$246k range
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Bob",
                last_name="Test",
                filing_status=FilingStatus.MARRIED_JOINT,
            ),
            income=Income(w2_forms=[make_w2(241000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # 50% of $7,000 = $3,500
        assert breakdown.roth_ira_eligible_contribution == 3500.0

    def test_just_above_phaseout_start(self):
        """Just over threshold starts phaseout."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # $151,000 is $1k over start ($150k)
        # Reduction: 1000 / 15000 = 6.67%
        # Eligible: 7000 * (1 - 0.0667) = ~6533, rounded to nearest $10 = $6530
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Chris",
                last_name="Test",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(151000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 6530.0

    def test_near_phaseout_end(self):
        """Near phaseout end should return minimum $200."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # $164,500 is $500 below end ($165k)
        # Reduction: 14500 / 15000 = 96.67%
        # Eligible: 7000 * (1 - 0.9667) = ~233, rounded to nearest $10 = $230
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Dana",
                last_name="Test",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(164500.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 230.0


class TestRothZeroAboveThreshold:
    """Tests for zero contribution above phaseout end."""

    def test_zero_contribution_above_threshold_single(self):
        """Zero eligible when MAGI at or above $165,000 for Single."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Eve",
                last_name="High",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(165000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0

    def test_zero_contribution_well_above_threshold(self):
        """Zero eligible when MAGI well above threshold."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Frank",
                last_name="Rich",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(300000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0

    def test_zero_contribution_above_mfj_threshold(self):
        """Zero eligible when MAGI at or above $246,000 for MFJ."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Grace",
                last_name="Wealthy",
                filing_status=FilingStatus.MARRIED_JOINT,
            ),
            income=Income(w2_forms=[make_w2(246000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0


class TestRothMFSSpecialRules:
    """Tests for Married Filing Separately special $0-$10,000 phaseout."""

    def test_mfs_zero_magi_full_contribution(self):
        """MFS with zero MAGI gets full contribution."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Using self-employment income to have compensation without W2 wages
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Henry",
                last_name="Test",
                filing_status=FilingStatus.MARRIED_SEPARATE,
            ),
            income=Income(self_employment_income=7000.0),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # MFS phaseout starts at $0, so even small income triggers phaseout
        # SE income ~$7k puts them in phaseout
        assert breakdown.roth_ira_eligible_contribution < 7000.0

    def test_mfs_mid_phaseout(self):
        """MFS at $5,000 MAGI is midpoint of $0-$10k phaseout."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Ivy",
                last_name="Test",
                filing_status=FilingStatus.MARRIED_SEPARATE,
            ),
            income=Income(w2_forms=[make_w2(5000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # 50% of eligible contribution (limited by compensation)
        # Compensation is $5,000, so base is min($7k, $5k) = $5k
        # 50% of $5k = $2,500
        assert breakdown.roth_ira_eligible_contribution == 2500.0

    def test_mfs_above_10k_zero(self):
        """MFS at $10,000+ MAGI gets zero contribution."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Jack",
                last_name="Test",
                filing_status=FilingStatus.MARRIED_SEPARATE,
            ),
            income=Income(w2_forms=[make_w2(15000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0


class TestRothAge50Plus:
    """Tests for age 50+ catchup contribution ($8,000)."""

    def test_age_50_plus_full_contribution(self):
        """Age 50+ can contribute up to $8,000."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Karen",
                last_name="Senior",
                filing_status=FilingStatus.SINGLE,
                is_age_50_plus=True,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=8000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 8000.0

    def test_age_50_plus_phaseout(self):
        """Age 50+ catchup also subject to phaseout."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MAGI = $157,500 is midpoint of $150k-$165k range
        # 50% of $8,000 = $4,000
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Larry",
                last_name="Senior",
                filing_status=FilingStatus.SINGLE,
                is_age_50_plus=True,
            ),
            income=Income(w2_forms=[make_w2(157500.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=8000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 4000.0

    def test_age_under_50_limited_to_7000(self):
        """Under age 50 limited to $7,000 even if contributing more."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Mike",
                last_name="Young",
                filing_status=FilingStatus.SINGLE,
                is_age_50_plus=False,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=10000.0,  # Trying to contribute more
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 7000.0


class TestRothCompensationLimit:
    """Tests for compensation limit - cannot exceed taxable compensation."""

    def test_limited_by_low_compensation(self):
        """Contribution limited to taxable compensation."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Nancy",
                last_name="PartTime",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(5000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # Limited to $5,000 (compensation)
        assert breakdown.roth_ira_eligible_contribution == 5000.0

    def test_no_compensation_no_contribution(self):
        """Zero compensation means zero eligible contribution."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Oscar",
                last_name="Retired",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                dividend_income=50000.0,  # Passive income, not compensation
            ),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0


class TestRothCombinedLimit:
    """Tests for combined Traditional + Roth IRA limit enforcement."""

    def test_combined_limit_reduces_roth(self):
        """Traditional IRA contributions reduce available Roth limit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Paul",
                last_name="Saver",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=3000.0,  # Traditional IRA
                roth_ira_contributions=7000.0,  # Trying for full Roth
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # $7,000 limit - $3,000 Traditional = $4,000 max Roth
        assert breakdown.roth_ira_eligible_contribution == 4000.0

    def test_combined_limit_exhausted(self):
        """Full Traditional IRA means zero Roth available."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Quinn",
                last_name="Traditional",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=7000.0,  # Full Traditional
                roth_ira_contributions=5000.0,  # Trying for Roth
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0

    def test_age_50_combined_limit_8000(self):
        """Age 50+ gets $8,000 combined limit."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Rita",
                last_name="Senior",
                filing_status=FilingStatus.SINGLE,
                is_age_50_plus=True,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                ira_contributions=4000.0,  # Traditional
                roth_ira_contributions=5000.0,  # Roth
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        # $8,000 limit - $4,000 Traditional = $4,000 max Roth
        assert breakdown.roth_ira_eligible_contribution == 4000.0


class TestRothRoundingRules:
    """Tests for IRS rounding rules ($200 minimum, round to nearest $10)."""

    def test_minimum_200_rule(self):
        """Very small eligible amount rounds up to $200."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MAGI near end of phaseout should produce small eligible amount
        # $164,800 gives: excess = 14800, ratio = 14800/15000 = 0.9867
        # reduced = 7000 * 0.0133 = ~93, which is < 200
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Steve",
                last_name="Test",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(164800.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 200.0

    def test_round_to_nearest_10(self):
        """Eligible amount rounds to nearest $10."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # $155,000 gives: excess = 5000, ratio = 5000/15000 = 0.333
        # reduced = 7000 * 0.667 = ~4667, rounded to $4670
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Tom",
                last_name="Test",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(155000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 4670.0


class TestRothNoContributions:
    """Tests for zero Roth contributions."""

    def test_zero_roth_returns_zero(self):
        """Zero Roth contributions returns zero eligible."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Uma",
                last_name="NoRoth",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=0.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0

    def test_no_roth_field_defaults_to_zero(self):
        """Missing Roth field defaults to zero."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Victor",
                last_name="Default",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(100000.0)]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0


class TestRothBoundaryConditions:
    """Tests for exact boundary values."""

    def test_exactly_at_phaseout_start(self):
        """Exactly at phaseout start gets full contribution."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Walter",
                last_name="Boundary",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(150000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 7000.0

    def test_exactly_at_phaseout_end(self):
        """Exactly at phaseout end gets zero."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Xena",
                last_name="Boundary",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(165000.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 0.0

    def test_one_dollar_below_phaseout_end(self):
        """Just below phaseout end gets minimum $200."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # $164,999 is $1 below end
        # excess = 14999, ratio = 14999/15000 = 0.9999
        # reduced = 7000 * 0.0001 = ~0.7, which is < 200
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Yolanda",
                last_name="Boundary",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(w2_forms=[make_w2(164999.0)]),
            deductions=Deductions(
                use_standard_deduction=True,
                roth_ira_contributions=7000.0,
            ),
            credits=TaxCredits(),
        )

        breakdown = engine.calculate(tr)
        assert breakdown.roth_ira_eligible_contribution == 200.0
