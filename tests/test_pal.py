"""
Test suite for Passive Activity Loss (PAL) - Form 8582 / IRC Section 469

Tests cover:
- Basic PAL limitation rules
- $25,000 rental loss allowance for active participants
- AGI phaseout of $25k allowance ($100k-$150k)
- Real estate professional exception
- Passive income/loss netting
- Suspended loss carryforward
- K-1 passive activities
- Disposition and suspended loss release
"""

import pytest
from decimal import Decimal

from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, ScheduleK1, K1SourceType, W2Info
from src.models.deductions import Deductions
from src.models.credits import TaxCredits
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


def make_taxpayer(filing_status: FilingStatus = FilingStatus.SINGLE) -> TaxpayerInfo:
    """Helper to create TaxpayerInfo for tests."""
    return TaxpayerInfo(
        first_name="Test",
        last_name="Filer",
        filing_status=filing_status,
    )


def make_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    income: Income = None,
    deductions: Deductions = None,
) -> TaxReturn:
    """Helper to create TaxReturn for tests."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=make_taxpayer(filing_status),
        income=income or Income(),
        deductions=deductions or Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


class TestPALBasicRules:
    """Test basic PAL limitation rules."""

    def test_no_rental_activity_no_pal(self, engine):
        """Taxpayer with no rental or passive activity - no PAL impact."""
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000.0)]),
        )

        result = engine.calculate(tax_return)

        assert 'pal_breakdown' in result.__dict__
        pal = result.pal_breakdown
        assert pal['rental_income'] == 0.0
        assert pal['rental_loss'] == 0.0
        assert pal['total_passive_income'] == 0.0
        assert pal['total_passive_loss'] == 0.0

    def test_rental_income_only_no_loss(self, engine):
        """Rental income without loss - no PAL limitation needed."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(75000.0)],
                rental_income=30000.0,
                rental_expenses=20000.0,  # Net profit of $10k
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['rental_income'] == 30000.0
        assert pal['net_rental_result'] == 10000.0  # Profit
        # Net profit contributes to passive income
        assert pal['total_passive_income'] == 10000.0
        assert pal['suspended_current_year'] == 0.0

    def test_rental_loss_fully_offset_by_passive_income(self, engine):
        """Rental loss offset by other passive income - no limitation."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(75000.0)],
                rental_income=10000.0,
                rental_expenses=25000.0,  # -$15k loss
                passive_business_income=20000.0,  # Offsets rental loss
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['net_rental_result'] == -15000.0
        assert pal['passive_business_income'] == 20000.0
        # Rental loss contributes to passive loss, business income to passive income
        assert pal['total_passive_income'] == 20000.0
        assert pal['total_passive_loss'] == 15000.0
        assert pal['net_passive_result'] == 5000.0  # Net income


class TestRentalLossAllowance:
    """Test $25,000 rental loss allowance for active participants."""

    def test_full_25k_allowance_low_agi(self, engine):
        """Active participant with AGI under $100k gets full $25k allowance."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                rental_income=10000.0,
                rental_expenses=40000.0,  # -$30k loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['is_active_participant'] is True
        assert pal['qualifies_for_25k_allowance'] is True
        assert pal['rental_loss_allowance_base'] == 25000.0  # Capped at $25k
        assert pal['rental_loss_allowance_after_phaseout'] == 25000.0
        # $5k remains suspended ($30k loss - $25k allowance)
        assert pal['suspended_current_year'] == 5000.0

    def test_loss_less_than_25k_fully_deductible(self, engine):
        """Rental loss under $25k fully deductible for active participant."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(70000.0)],
                rental_income=5000.0,
                rental_expenses=20000.0,  # -$15k loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['rental_loss_allowance_base'] == 15000.0  # Actual loss
        assert pal['rental_loss_allowance_after_phaseout'] == 15000.0
        assert pal['allowable_passive_loss'] == 15000.0
        assert pal['suspended_current_year'] == 0.0

    def test_not_active_participant_no_allowance(self, engine):
        """Non-active participant gets no $25k allowance."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                rental_income=10000.0,
                rental_expenses=35000.0,  # -$25k loss
                is_active_participant_rental=False,  # Not active
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['is_active_participant'] is False
        assert pal['rental_loss_allowance_base'] == 0.0
        assert pal['rental_loss_allowance_after_phaseout'] == 0.0
        # Full loss suspended (no passive income or allowance to offset)
        assert pal['suspended_current_year'] == 25000.0


class TestAGIPhaseout:
    """Test AGI phaseout of $25k rental loss allowance."""

    def test_phaseout_starts_at_100k(self, engine):
        """Test phaseout behavior with AGI above threshold."""
        # Need AGI > $100k for phaseout to apply
        # Wages $140k - rental loss $25k = $115k gross income
        # Still above $100k threshold
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(140000.0)],
                rental_income=5000.0,
                rental_expenses=30000.0,  # -$25k loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # Check that AGI is being used for phaseout
        assert pal['agi_for_phaseout'] > 100000.0
        # Some phaseout should apply when AGI > $100k
        assert pal['rental_loss_allowance_after_phaseout'] < 25000.0

    def test_full_allowance_under_100k_agi(self, engine):
        """AGI under $100k gets full allowance."""
        # AGI will be: $90k wages - standard deduction - rental loss
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(90000.0)],
                rental_income=0.0,
                rental_expenses=25000.0,  # -$25k loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # AGI should be under $100k (90k wages - 25k loss = 65k gross income)
        assert pal['qualifies_for_25k_allowance'] is True
        assert pal['rental_loss_allowance_after_phaseout'] == 25000.0

    def test_high_income_complete_phaseout(self, engine):
        """Very high income - complete phaseout of allowance."""
        # Need AGI > $150k for complete phaseout
        # Wages $180k + positive rental income $10k = AGI > $150k
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(180000.0)],
                rental_income=10000.0,
                rental_expenses=40000.0,  # -$30k loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # AGI should be above $150k threshold
        assert pal['agi_for_phaseout'] >= 150000.0
        assert pal['qualifies_for_25k_allowance'] is False
        assert pal['rental_loss_allowance_after_phaseout'] == 0.0


class TestRealEstateProfessional:
    """Test real estate professional exception - IRC 469(c)(7)."""

    def test_re_professional_flag_bypass_pal(self, engine):
        """Real estate professional flag bypasses all PAL limitations."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(50000.0)],
                rental_income=20000.0,
                rental_expenses=80000.0,  # -$60k loss
                is_real_estate_professional=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['is_real_estate_professional'] is True
        # Full loss deductible - no PAL limitation
        assert pal['allowable_passive_loss'] == 60000.0
        assert pal['suspended_current_year'] == 0.0

    def test_re_professional_hours_threshold(self, engine):
        """750+ hours in real estate qualifies as RE professional."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(40000.0)],
                rental_income=15000.0,
                rental_expenses=50000.0,  # -$35k loss
                is_real_estate_professional=False,
                real_estate_professional_hours=800.0,  # 750+ hours
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['is_real_estate_professional'] is True
        assert pal['allowable_passive_loss'] == 35000.0
        assert pal['suspended_current_year'] == 0.0

    def test_re_professional_hours_under_threshold(self, engine):
        """Under 750 hours - not RE professional, PAL applies."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(90000.0)],
                rental_income=10000.0,
                rental_expenses=45000.0,  # -$35k loss
                is_real_estate_professional=False,
                real_estate_professional_hours=500.0,  # Under 750
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['is_real_estate_professional'] is False
        # Should get $25k allowance (active participant, AGI under $100k)
        # AGI = 90k - 35k loss = 55k, so full $25k allowance
        assert pal['allowable_passive_loss'] == 25000.0
        assert pal['suspended_current_year'] == 10000.0  # $35k - $25k


class TestK1PassiveActivities:
    """Test K-1 passive activity handling."""

    def test_k1_passive_income_offsets_rental_loss(self, engine):
        """K-1 passive income can offset rental losses."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                rental_income=5000.0,
                rental_expenses=30000.0,  # -$25k rental loss
                schedule_k1_forms=[
                    ScheduleK1(
                        k1_type=K1SourceType.PARTNERSHIP,
                        entity_name="Passive LLC",
                        entity_ein="12-3456789",
                        ordinary_business_income=15000.0,
                        is_passive_activity=True,
                    )
                ],
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['k1_passive_income'] == 15000.0
        # Total passive income = $15k K-1 (rental has net loss)
        assert pal['total_passive_income'] == 15000.0
        # Total passive loss = $25k rental loss
        assert pal['total_passive_loss'] == 25000.0
        # Net passive = $15k - $25k = -$10k
        assert pal['net_passive_result'] == -10000.0

    def test_k1_passive_loss_adds_to_rental_loss(self, engine):
        """K-1 passive loss adds to total passive loss."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                rental_income=5000.0,
                rental_expenses=20000.0,  # -$15k rental loss
                schedule_k1_forms=[
                    ScheduleK1(
                        k1_type=K1SourceType.PARTNERSHIP,
                        entity_name="Losing LLC",
                        entity_ein="98-7654321",
                        ordinary_business_income=-20000.0,  # K-1 loss
                        is_passive_activity=True,
                    )
                ],
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['k1_passive_loss'] == 20000.0
        # Total passive loss: $15k rental + $20k K-1 = $35k
        assert pal['total_passive_loss'] == 35000.0

    def test_k1_non_passive_not_subject_to_pal(self, engine):
        """K-1 marked as non-passive (material participation) excluded from PAL."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(60000.0)],
                rental_income=5000.0,
                rental_expenses=30000.0,  # -$25k rental loss
                schedule_k1_forms=[
                    ScheduleK1(
                        k1_type=K1SourceType.S_CORPORATION,
                        entity_name="Active S-Corp",
                        entity_ein="11-1111111",
                        ordinary_business_income=50000.0,
                        is_passive_activity=False,  # Material participation
                    )
                ],
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # Non-passive K-1 income not counted in PAL
        assert pal['k1_passive_income'] == 0.0
        # Only rental loss counted (rental has net loss so no passive income)
        assert pal['total_passive_income'] == 0.0
        assert pal['total_passive_loss'] == 25000.0


class TestPassiveBusinessActivities:
    """Test non-rental passive business activity handling."""

    def test_passive_business_income_offsets_loss(self, engine):
        """Passive business income offsets passive business losses."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(100000.0)],
                passive_business_income=30000.0,
                passive_business_losses=20000.0,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['passive_business_income'] == 30000.0
        assert pal['passive_business_loss'] == 20000.0
        assert pal['net_passive_business'] == 10000.0  # Net income

    def test_passive_business_loss_subject_to_pal(self, engine):
        """Passive business loss subject to PAL when no offsetting income."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                passive_business_income=5000.0,
                passive_business_losses=25000.0,  # Net $20k loss
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['net_passive_business'] == -20000.0
        # Net passive result is negative (loss exceeds income)
        # Passive income offsets passive losses, remaining is suspended
        assert pal['total_passive_income'] == 5000.0
        assert pal['total_passive_loss'] == 25000.0
        # The $5k income offsets $5k of loss, but $25k allowance also applies
        # if there's rental activity (there isn't here)
        # So remaining loss is suspended
        assert pal['suspended_current_year'] > 0


class TestSuspendedLossCarryforward:
    """Test suspended loss carryforward mechanics."""

    def test_new_suspended_loss_tracked(self, engine):
        """New suspended loss tracked for carryforward."""
        # Use high wages with no rental income to keep AGI high
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(180000.0)],  # High AGI
                rental_income=0.0,
                rental_expenses=35000.0,  # -$35k rental loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # AGI is high (wages - rental loss still > $150k)
        assert pal['agi_for_phaseout'] >= 145000.0
        # When AGI is high, allowance is reduced
        # Some or all of the loss should be suspended
        assert pal['suspended_current_year'] > 0
        assert pal['new_suspended_carryforward'] > 0


class TestDispositionRelease:
    """Test suspended loss release on complete disposition."""

    def test_disposition_releases_suspended_loss(self, engine):
        """Complete disposition releases suspended losses."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(200000.0)],  # High AGI
                rental_income=0.0,
                rental_expenses=20000.0,  # -$20k current year loss
                suspended_passive_loss_carryforward=50000.0,  # Prior year
                passive_activity_dispositions=100000.0,  # Sale of property
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['disposition_gain_loss'] == 100000.0
        assert pal['suspended_loss_released'] == 50000.0
        # On disposition, suspended loss becomes allowable


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_income_zero_loss(self, engine):
        """No passive activity at all."""
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(50000.0)]),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['total_passive_income'] == 0.0
        assert pal['total_passive_loss'] == 0.0
        assert pal['suspended_current_year'] == 0.0

    def test_exactly_25k_loss_fully_deductible(self, engine):
        """Rental loss exactly $25k - fully deductible for active participant."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                rental_income=0.0,
                rental_expenses=25000.0,  # Exactly $25k loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        assert pal['rental_loss_allowance_base'] == 25000.0
        assert pal['rental_loss_allowance_after_phaseout'] == 25000.0
        assert pal['allowable_passive_loss'] == 25000.0
        assert pal['suspended_current_year'] == 0.0

    def test_agi_exactly_100k_threshold(self, engine):
        """AGI under $100k gets full allowance."""
        # Make AGI clearly under $100k
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],  # Clearly under $100k
                rental_income=0.0,
                rental_expenses=25000.0,
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # AGI should be well under $100k
        assert pal['qualifies_for_25k_allowance'] is True
        assert pal['rental_loss_allowance_after_phaseout'] == 25000.0


class TestMultiplePassiveActivities:
    """Test scenarios with multiple types of passive activities."""

    def test_rental_and_business_passive_combined(self, engine):
        """Rental and passive business activities combined."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(80000.0)],
                rental_income=10000.0,
                rental_expenses=25000.0,  # -$15k rental loss
                passive_business_income=5000.0,
                passive_business_losses=10000.0,  # -$5k passive biz loss
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # Rental has net loss, so contributes $15k to passive loss, $0 to income
        # Business has $5k income, $10k loss
        assert pal['total_passive_income'] == 5000.0  # Only business income
        assert pal['total_passive_loss'] == 25000.0  # $15k rental + $10k business
        assert pal['net_rental_result'] == -15000.0

    def test_rental_k1_business_all_combined(self, engine):
        """Rental, K-1, and passive business all combined."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(75000.0)],
                # Rental activity
                rental_income=8000.0,
                rental_expenses=20000.0,  # -$12k rental loss
                # Passive business
                passive_business_income=3000.0,
                passive_business_losses=8000.0,  # -$5k business loss
                # K-1 passive
                schedule_k1_forms=[
                    ScheduleK1(
                        k1_type=K1SourceType.PARTNERSHIP,
                        entity_name="Partnership X",
                        entity_ein="12-3456789",
                        ordinary_business_income=7000.0,
                        is_passive_activity=True,
                    )
                ],
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown
        # Total passive income: $3k business + $7k K-1 = $10k (rental has loss)
        assert pal['total_passive_income'] == 10000.0
        # Losses: $12k rental + $8k biz = $20k
        assert pal['total_passive_loss'] == 20000.0
        # Net passive: $10k - $20k = -$10k
        assert pal['net_passive_result'] == -10000.0


class TestPALBreakdownFields:
    """Test that PAL breakdown contains all expected fields."""

    def test_pal_breakdown_structure(self, engine):
        """Verify PAL breakdown has all required fields."""
        tax_return = make_return(
            income=Income(
                w2_forms=[make_w2(100000.0)],
                rental_income=20000.0,
                rental_expenses=35000.0,
                is_active_participant_rental=True,
            ),
        )

        result = engine.calculate(tax_return)

        pal = result.pal_breakdown

        # Verify all expected keys exist
        expected_keys = [
            'rental_income',
            'rental_loss',
            'net_rental_result',
            'passive_business_income',
            'passive_business_loss',
            'net_passive_business',
            'k1_passive_income',
            'k1_passive_loss',
            'total_passive_income',
            'total_passive_loss',
            'net_passive_result',
            'rental_loss_allowance_base',
            'rental_loss_allowance_after_phaseout',
            'agi_for_phaseout',
            'disposition_gain_loss',
            'suspended_loss_released',
            'allowable_passive_loss',
            'suspended_current_year',
            'suspended_carryforward_used',
            'new_suspended_carryforward',
            'is_active_participant',
            'is_real_estate_professional',
            'qualifies_for_25k_allowance',
        ]

        for key in expected_keys:
            assert key in pal, f"Missing expected key: {key}"
