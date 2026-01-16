"""
Tests for Social Security Taxation (IRS Publication 915)

Tests cover:
- Tier 1: 0% taxable (provisional income <= base1)
- Tier 2: 50% of excess (base1 < provisional <= base2)
- Tier 3: 85% formula (provisional > base2)
- All filing statuses with correct base amounts
- MFS harsh treatment (0 base amounts)
- 85% cap enforcement
- K-1 income in provisional income
- Crypto income in provisional income
- Gambling income in provisional income
- Boundary conditions
"""

import pytest
from src.calculator.engine import FederalTaxEngine
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, ScheduleK1, K1SourceType, GamblingWinnings, GamblingType
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


class TestTier1ZeroTaxable:
    """Tests for Tier 1: Provisional income <= base1, 0% taxable."""

    def test_single_below_base1(self):
        """Single filer with provisional income below $25,000."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Single, $15k other income, $20k SS benefits
        # Provisional = 15k + 0 + 10k = 25k (exactly at base1)
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=15_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 0.0

    def test_mfj_below_base1(self):
        """MFJ with provisional income below $32,000."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MFJ, $20k other income, $20k SS benefits
        # Provisional = 20k + 0 + 10k = 30k < 32k base1
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.MARRIED_JOINT),
            income=Income(social_security_benefits=20_000.0, other_income=20_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 0.0

    def test_hoh_below_base1(self):
        """Head of Household with provisional income below $25,000."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.HEAD_OF_HOUSEHOLD),
            income=Income(social_security_benefits=20_000.0, other_income=10_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Provisional = 10k + 10k = 20k < 25k
        assert tr.income.taxable_social_security == 0.0

    def test_qualifying_widow_below_base1(self):
        """Qualifying Widow(er) uses single base amounts."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.QUALIFYING_WIDOW),
            income=Income(social_security_benefits=20_000.0, other_income=10_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 0.0


class TestTier2FiftyPercent:
    """Tests for Tier 2: base1 < provisional <= base2, 50% taxable."""

    def test_single_in_50_percent_band(self):
        """Single filer in 50% band ($25k < provisional <= $34k)."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Single, $24k other income, $20k SS benefits
        # Provisional = 24k + 0 + 10k = 34k (exactly at base2)
        # Taxable = 0.5 * (34k - 25k) = 0.5 * 9k = $4,500
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=24_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 4500.0

    def test_mfj_in_50_percent_band(self):
        """MFJ in 50% band ($32k < provisional <= $44k)."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MFJ, $30k other income, $20k SS benefits
        # Provisional = 30k + 0 + 10k = 40k (between 32k and 44k)
        # Taxable = 0.5 * (40k - 32k) = 0.5 * 8k = $4,000
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.MARRIED_JOINT),
            income=Income(social_security_benefits=20_000.0, other_income=30_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 4000.0

    def test_just_over_base1(self):
        """Just $1 over base1 results in $0.50 taxable."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Provisional = 15001 + 10000 = 25001 (just over $25k)
        # Taxable = 0.5 * 1 = $0.50
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=15_001.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 0.5


class TestTier3EightyFivePercent:
    """Tests for Tier 3: provisional > base2, 85% formula."""

    def test_single_in_85_percent_tier(self):
        """Single filer above $34k triggers 85% tier."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Single, $50k other income, $20k SS benefits
        # Provisional = 50k + 0 + 10k = 60k
        # Taxable = 0.85 * (60k - 34k) + min(4500, 0.5 * (60k - 25k))
        #         = 0.85 * 26k + min(4500, 0.5 * 35k)
        #         = 22100 + min(4500, 17500)
        #         = 22100 + 4500 = 26600
        # But capped at 85% of benefits = 0.85 * 20k = 17000
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=50_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Should be capped at 85% of $20k = $17,000
        assert tr.income.taxable_social_security == 17_000.0

    def test_mfj_in_85_percent_tier(self):
        """MFJ above $44k triggers 85% tier."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MFJ, $60k other income, $20k SS benefits
        # Provisional = 60k + 10k = 70k > 44k
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.MARRIED_JOINT),
            income=Income(social_security_benefits=20_000.0, other_income=60_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Should be capped at 85% of $20k = $17,000
        assert tr.income.taxable_social_security == 17_000.0


class TestMFSAlwaysTaxable:
    """Tests for MFS harsh treatment (0 base amounts)."""

    def test_mfs_all_ss_taxable_at_85_percent(self):
        """MFS gets 0 base amounts - 85% formula applies immediately."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # MFS, minimal income still triggers 85% taxation
        # Provisional = $5k + $10k (0.5 * SS) = $15k
        # With base1=0, base2=0: taxable = 0.85 * provisional = $12,750
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.MARRIED_SEPARATE),
            income=Income(social_security_benefits=20_000.0, other_income=5_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Taxable = 0.85 * $15k = $12,750 (below 85% cap of $17k)
        assert tr.income.taxable_social_security == 12_750.0

    def test_mfs_even_zero_other_income(self):
        """MFS with only SS benefits still triggers taxation."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Provisional = $0 + $10k (0.5 * SS) = $10k
        # With base1=0, base2=0: taxable = 0.85 * $10k = $8,500
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.MARRIED_SEPARATE),
            income=Income(social_security_benefits=20_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Taxable = 0.85 * $10k = $8,500 (below 85% cap of $17k)
        assert tr.income.taxable_social_security == 8_500.0


class TestEightyFivePercentCap:
    """Tests for 85% cap enforcement."""

    def test_cap_never_exceeded(self):
        """Taxable SS never exceeds 85% of total benefits."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Very high income to ensure cap kicks in
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=30_000.0, other_income=200_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # 85% of $30k = $25,500
        assert tr.income.taxable_social_security == 25_500.0
        assert tr.income.taxable_social_security <= 0.85 * tr.income.social_security_benefits

    def test_cap_with_small_benefits(self):
        """Cap applies proportionally to small benefits."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=5_000.0, other_income=100_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # 85% of $5k = $4,250
        assert tr.income.taxable_social_security == 4_250.0


class TestK1IncomeInProvisional:
    """Tests for K-1 income affecting provisional income."""

    def test_k1_income_pushes_into_taxable_tier(self):
        """K-1 income increases provisional income, triggering taxation."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Without K-1: provisional = 10k + 10k = 20k < 25k (Tier 1)
        # With $10k K-1: provisional = 20k + 10k = 30k (Tier 2)
        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Test Partnership",
            ordinary_business_income=10_000.0,
        )
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(
                social_security_benefits=20_000.0,
                other_income=10_000.0,
                schedule_k1_forms=[k1],
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Now in Tier 2: taxable = 0.5 * (30k - 25k) = $2,500
        assert tr.income.taxable_social_security == 2500.0

    def test_k1_preferential_income_included(self):
        """K-1 qualified dividends and LTCG included in provisional."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Note: ordinary_dividends must include qualified_dividends (qualified is a subset)
        k1 = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="Test S-Corp",
            ordinary_dividends=5_000.0,  # Total dividends (includes qualified)
            qualified_dividends=5_000.0,  # Subset taxed at preferential rates
            net_long_term_capital_gain=5_000.0,
        )
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(
                social_security_benefits=20_000.0,
                other_income=10_000.0,
                schedule_k1_forms=[k1],
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # K-1 ordinary income: (5k ord_div - 5k qual_div) + 0 = 0
        # K-1 preferential income: 5k qual_div + 5k LTCG = 10k
        # Provisional = 10k (other) + 10k (K-1) + 10k (0.5*SS) = 30k
        # Taxable = 0.5 * (30k - 25k) = $2,500
        assert tr.income.taxable_social_security == 2500.0


class TestGamblingIncomeInProvisional:
    """Tests for gambling income affecting provisional income."""

    def test_gambling_winnings_increase_provisional(self):
        """Gambling winnings are included in provisional income."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(
                social_security_benefits=20_000.0,
                other_income=10_000.0,
                gambling_winnings=[
                    GamblingWinnings(
                        gambling_type=GamblingType.CASINO,
                        gross_winnings=10_000.0,
                    )
                ],
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Provisional = 10k + 10k (gambling) + 10k = 30k (Tier 2)
        assert tr.income.taxable_social_security == 2500.0


class TestBoundaryConditions:
    """Tests for boundary conditions at exact thresholds."""

    def test_exactly_at_base1_single(self):
        """Exactly at base1 ($25k) results in zero taxable."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=15_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Provisional = 15k + 10k = 25k exactly
        assert tr.income.taxable_social_security == 0.0

    def test_exactly_at_base2_single(self):
        """Exactly at base2 ($34k) uses 50% formula."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=24_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Provisional = 24k + 10k = 34k exactly (still Tier 2)
        # Taxable = 0.5 * (34k - 25k) = $4,500
        assert tr.income.taxable_social_security == 4500.0

    def test_one_dollar_over_base2(self):
        """Just over base2 triggers 85% tier formula."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=20_000.0, other_income=24_001.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Provisional = 24001 + 10k = 34001 (Tier 3)
        # Taxable = 0.85 * 1 + min(4500, 0.5 * 9001) = 0.85 + 4500 = 4500.85
        assert tr.income.taxable_social_security == 4500.85


class TestNoSSBenefits:
    """Tests for zero or no SS benefits."""

    def test_zero_benefits_zero_taxable(self):
        """Zero SS benefits means zero taxable."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(social_security_benefits=0.0, other_income=100_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 0.0

    def test_no_ss_field_defaults_to_zero(self):
        """Missing SS benefits field defaults to zero."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(other_income=100_000.0),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        assert tr.income.taxable_social_security == 0.0


class TestTaxExemptInterest:
    """Tests for tax-exempt interest in provisional income."""

    def test_tax_exempt_interest_increases_provisional(self):
        """Tax-exempt interest is added to provisional income."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        # Without tax-exempt interest: prov = 10k + 10k = 20k (Tier 1)
        # With $10k tax-exempt: prov = 10k + 10k + 10k = 30k (Tier 2)
        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(
                social_security_benefits=20_000.0,
                other_income=10_000.0,
                tax_exempt_interest=10_000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Taxable = 0.5 * (30k - 25k) = $2,500
        assert tr.income.taxable_social_security == 2500.0


class TestPreExistingTaxableOverride:
    """Tests for pre-existing taxable_social_security value."""

    def test_respects_preset_taxable_value(self):
        """If taxable_social_security is already set, don't recalculate."""
        engine = FederalTaxEngine(TaxYearConfig.for_2025())

        tr = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(first_name="A", last_name="B", filing_status=FilingStatus.SINGLE),
            income=Income(
                social_security_benefits=20_000.0,
                taxable_social_security=5_000.0,  # Pre-set value
                other_income=100_000.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        engine.calculate(tr)
        # Should keep the pre-set value
        assert tr.income.taxable_social_security == 5_000.0
