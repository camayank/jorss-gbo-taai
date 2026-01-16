"""
Tests for Form 8582 - Passive Activity Loss Limitations

Tests cover:
- Material participation tests (7 tests)
- Passive vs non-passive activity classification
- $25,000 rental real estate loss allowance
- AGI phaseout of rental allowance ($100k-$150k)
- Real estate professional exception
- Suspended loss carryforward
- Complete disposition release of suspended losses
- Publicly traded partnership (PTP) separate basket
- Integration with tax calculation engine
"""

import pytest
from models.form_8582 import (
    Form8582,
    PassiveActivity,
    RentalRealEstateAllowance,
    RealEstateProfessional,
    ActivityType,
    MaterialParticipationTest,
    DispositionType,
    calculate_agi_phaseout,
    check_material_participation_tests,
)
from models.income import Income, W2Info
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


# ============== Helper Functions ==============

def make_passive_activity(
    name: str = "Test Activity",
    activity_type: ActivityType = ActivityType.TRADE_OR_BUSINESS,
    gross_income: float = 0.0,
    deductions: float = 0.0,
    prior_loss: float = 0.0,
    taxpayer_hours: float = 0.0,
    is_rental: bool = False,
    is_active_participant: bool = False,
    is_material_participation: bool = False,
) -> PassiveActivity:
    """Helper to create PassiveActivity for tests."""
    return PassiveActivity(
        activity_name=name,
        activity_type=activity_type,
        gross_income=gross_income,
        deductions=deductions,
        prior_year_unallowed_loss=prior_loss,
        taxpayer_hours=taxpayer_hours,
        is_rental_real_estate=is_rental,
        is_active_participant=is_active_participant,
        is_material_participation=is_material_participation,
    )


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def create_tax_return(form_8582: Form8582 = None, wages: float = 50000.0) -> TaxReturn:
    """Helper to create TaxReturn with Form 8582."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            w2_forms=[make_w2(wages, wages * 0.15)],
            form_8582=form_8582,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


# ============== PassiveActivity Tests ==============

class TestPassiveActivity:
    """Tests for PassiveActivity model."""

    def test_net_income_loss_positive(self):
        """Test net income calculation."""
        activity = make_passive_activity(gross_income=10000, deductions=6000)
        assert activity.get_net_income_loss() == 4000.0

    def test_net_income_loss_negative(self):
        """Test net loss calculation."""
        activity = make_passive_activity(gross_income=5000, deductions=8000)
        assert activity.get_net_income_loss() == -3000.0

    def test_total_loss_with_prior_year(self):
        """Test total loss includes prior year suspended loss."""
        activity = make_passive_activity(
            gross_income=5000,
            deductions=10000,
            prior_loss=3000,
        )
        # Current loss: 5000, Prior loss: 3000
        assert activity.get_total_loss_available() == 8000.0

    def test_is_passive_no_material_participation(self):
        """Activity is passive without material participation."""
        activity = make_passive_activity(
            taxpayer_hours=100,
            is_material_participation=False,
        )
        assert activity.is_passive() is True

    def test_is_not_passive_material_participation(self):
        """Activity is non-passive with material participation."""
        activity = make_passive_activity(
            taxpayer_hours=600,
            is_material_participation=True,
        )
        assert activity.is_passive() is False

    def test_working_interest_oil_gas_never_passive(self):
        """Working interest in oil/gas is never passive."""
        activity = make_passive_activity(
            activity_type=ActivityType.WORKING_INTEREST_OIL_GAS,
        )
        assert activity.is_passive() is False


# ============== Material Participation Tests ==============

class TestMaterialParticipation:
    """Tests for material participation determination."""

    def test_material_participation_500_hours(self):
        """Test 1: 500+ hours = material participation."""
        activity = PassiveActivity(
            activity_name="Business",
            taxpayer_hours=550,
        )
        is_mp, test = activity.check_material_participation()
        assert is_mp is True
        assert test == MaterialParticipationTest.TEST_1_500_HOURS

    def test_material_participation_substantially_all(self):
        """Test 2: Substantially all participation."""
        activity = PassiveActivity(
            activity_name="Business",
            taxpayer_hours=450,
            total_activity_hours=480,  # 93.75% of total
        )
        is_mp, test = activity.check_material_participation()
        assert is_mp is True
        assert test == MaterialParticipationTest.TEST_2_SUBSTANTIALLY_ALL

    def test_material_participation_100_hours_not_less(self):
        """Test 3: 100+ hours and not less than others."""
        activity = PassiveActivity(
            activity_name="Business",
            taxpayer_hours=150,
            total_activity_hours=250,  # Taxpayer has 60% of hours
        )
        is_mp, test = activity.check_material_participation()
        assert is_mp is True
        assert test == MaterialParticipationTest.TEST_3_100_HOURS_NOT_LESS

    def test_no_material_participation_under_100_hours(self):
        """Less than 100 hours fails most tests."""
        activity = PassiveActivity(
            activity_name="Business",
            taxpayer_hours=50,
            total_activity_hours=1000,
        )
        is_mp, test = activity.check_material_participation()
        assert is_mp is False

    def test_spouse_hours_combined(self):
        """Spouse hours are combined with taxpayer."""
        activity = PassiveActivity(
            activity_name="Business",
            taxpayer_hours=300,
            spouse_hours=250,  # Combined = 550
        )
        is_mp, test = activity.check_material_participation()
        assert is_mp is True
        assert test == MaterialParticipationTest.TEST_1_500_HOURS


# ============== Rental Real Estate Allowance Tests ==============

class TestRentalRealEstateAllowance:
    """Tests for $25,000 rental loss allowance."""

    def test_full_allowance_low_agi(self):
        """Full $25k allowance when AGI under $100k."""
        allowance = RentalRealEstateAllowance(
            modified_agi=80000,
            eligible_rental_losses=30000,
        )
        result = allowance.calculate_allowance()
        assert result['max_allowance'] == 25000.0
        assert result['available_allowance'] == 25000.0
        assert result['allowance_used'] == 25000.0
        assert result['disallowed'] == 5000.0  # 30000 - 25000

    def test_partial_allowance_phaseout(self):
        """Partial allowance during phaseout range."""
        allowance = RentalRealEstateAllowance(
            modified_agi=120000,  # $20k over threshold
            eligible_rental_losses=25000,
        )
        result = allowance.calculate_allowance()
        # Phaseout: $20k * 50% = $10k reduction
        # Available: $25k - $10k = $15k
        assert result['available_allowance'] == 15000.0
        assert result['allowance_used'] == 15000.0

    def test_no_allowance_high_agi(self):
        """No allowance when AGI at or above $150k."""
        allowance = RentalRealEstateAllowance(
            modified_agi=150000,
            eligible_rental_losses=20000,
        )
        result = allowance.calculate_allowance()
        # Phaseout: $50k * 50% = $25k reduction (complete)
        assert result['available_allowance'] == 0.0
        assert result['allowance_used'] == 0.0

    def test_mfs_no_allowance_living_together(self):
        """MFS living together: no allowance."""
        allowance = RentalRealEstateAllowance(
            modified_agi=80000,
            eligible_rental_losses=20000,
            is_married_filing_separately=True,
            lived_apart_all_year=False,
        )
        result = allowance.calculate_allowance()
        assert result['max_allowance'] == 0.0
        assert result['allowance_used'] == 0.0

    def test_mfs_allowance_living_apart(self):
        """MFS living apart all year: $12,500 max."""
        allowance = RentalRealEstateAllowance(
            modified_agi=40000,  # Under $50k MFS threshold
            eligible_rental_losses=20000,
            is_married_filing_separately=True,
            lived_apart_all_year=True,
        )
        result = allowance.calculate_allowance()
        assert result['max_allowance'] == 12500.0
        assert result['available_allowance'] == 12500.0
        assert result['allowance_used'] == 12500.0

    def test_allowance_limited_to_losses(self):
        """Allowance limited to actual eligible losses."""
        allowance = RentalRealEstateAllowance(
            modified_agi=80000,
            eligible_rental_losses=10000,  # Less than $25k max
        )
        result = allowance.calculate_allowance()
        assert result['allowance_used'] == 10000.0


# ============== Real Estate Professional Tests ==============

class TestRealEstateProfessional:
    """Tests for real estate professional status."""

    def test_qualifies_as_professional(self):
        """Meets both 750 hours and 50% tests."""
        rep = RealEstateProfessional(
            real_property_hours=1000,
            total_work_hours=1800,  # 55.5% in RE
        )
        assert rep.qualifies_as_professional() is True

    def test_fails_750_hour_test(self):
        """Fails: Less than 750 hours."""
        rep = RealEstateProfessional(
            real_property_hours=600,
            total_work_hours=800,
        )
        assert rep.qualifies_as_professional() is False

    def test_fails_50_percent_test(self):
        """Fails: Less than 50% of time in RE."""
        rep = RealEstateProfessional(
            real_property_hours=800,
            total_work_hours=2000,  # Only 40% in RE
        )
        assert rep.qualifies_as_professional() is False

    def test_status_details(self):
        """Test detailed status calculation."""
        rep = RealEstateProfessional(
            real_property_hours=900,
            total_work_hours=1600,
            elected_to_aggregate_rentals=True,
        )
        status = rep.calculate_status()
        assert status['qualifies'] is True
        assert status['hours_test_met'] is True
        assert status['percentage_test_met'] is True
        assert status['percentage'] == 56.25
        assert status['aggregation_elected'] is True


# ============== Form 8582 Part I Tests ==============

class TestForm8582PartI:
    """Tests for Part I - Total Passive Activity Loss."""

    def test_rental_income_loss_categorization(self):
        """Rental activities categorized separately."""
        # Activity with net income
        rental_income = make_passive_activity(
            name="Rental Income Property",
            gross_income=15000,
            deductions=5000,  # Net income = 10000
            is_rental=True,
            is_active_participant=True,
        )
        # Activity with net loss
        rental_loss = make_passive_activity(
            name="Rental Loss Property",
            gross_income=3000,
            deductions=11000,  # Net loss = 8000
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(activities=[rental_income, rental_loss])
        result = form.calculate_part_i()

        assert result['line_1a_rental_income'] == 10000.0  # Net income from profitable rental
        assert result['line_1b_rental_loss'] == 8000.0  # Net loss from loss rental

    def test_other_passive_income_loss(self):
        """Non-rental passive activities."""
        # Activity with net income
        business_income = make_passive_activity(
            name="Partnership Income",
            activity_type=ActivityType.LIMITED_PARTNERSHIP,
            gross_income=10000,
            deductions=2000,  # Net income = 8000
        )
        # Activity with net loss
        business_loss = make_passive_activity(
            name="Partnership Loss",
            activity_type=ActivityType.LIMITED_PARTNERSHIP,
            gross_income=2000,
            deductions=8000,  # Net loss = 6000
        )
        form = Form8582(activities=[business_income, business_loss])
        result = form.calculate_part_i()

        assert result['line_2a_other_income'] == 8000.0  # Net income
        assert result['line_2b_other_loss'] == 6000.0  # Net loss

    def test_prior_year_losses_included(self):
        """Prior year suspended losses included."""
        activity = make_passive_activity(
            gross_income=0,
            deductions=5000,
            prior_loss=3000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(activities=[activity])
        result = form.calculate_part_i()

        assert result['line_1c_prior_rental_loss'] == 3000.0
        assert result['line_4_total_loss'] == 8000.0  # 5000 + 3000


# ============== Form 8582 Part II Tests ==============

class TestForm8582PartII:
    """Tests for Part II - Special Allowance."""

    def test_special_allowance_calculation(self):
        """Calculate $25k special allowance."""
        rental = make_passive_activity(
            name="Rental",
            gross_income=10000,
            deductions=30000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(
            modified_agi=80000,
            activities=[rental],
        )
        result = form.calculate_part_ii()

        # Loss = 20000, Max allowance = 25000
        assert result['line_5_rental_loss'] == 20000.0
        assert result['line_11_allowance_used'] == 20000.0

    def test_special_allowance_with_phaseout(self):
        """Special allowance reduced by AGI phaseout."""
        rental = make_passive_activity(
            name="Rental",
            gross_income=0,
            deductions=25000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(
            modified_agi=130000,  # $30k over threshold
            activities=[rental],
        )
        result = form.calculate_part_ii()

        # Phaseout: $30k * 50% = $15k reduction
        # Available: $25k - $15k = $10k
        assert result['line_10_allowance_available'] == 10000.0
        assert result['line_11_allowance_used'] == 10000.0


# ============== Form 8582 Part III Tests ==============

class TestForm8582PartIII:
    """Tests for Part III - Total Losses Allowed."""

    def test_losses_allowed_against_income(self):
        """Passive losses allowed against passive income."""
        income_activity = make_passive_activity(
            name="Income Activity",
            gross_income=20000,
            deductions=5000,  # Net income = 15000
        )
        loss_activity = make_passive_activity(
            name="Loss Activity",
            gross_income=2000,
            deductions=12000,  # Net loss = 10000
        )
        form = Form8582(activities=[income_activity, loss_activity])
        result = form.calculate_part_iii()

        # Net income: 15000 (from income_activity)
        # Net loss: 10000 (from loss_activity)
        # Losses allowed against income
        assert result['line_12_total_passive_income'] == 15000.0  # Net income
        assert result['line_13_total_passive_loss'] == 10000.0  # Net loss
        assert result['line_17_total_losses_allowed'] == 10000.0  # All loss allowed

    def test_suspended_loss_calculation(self):
        """Excess losses become suspended."""
        loss_activity = make_passive_activity(
            name="Loss Activity",
            gross_income=0,
            deductions=50000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(
            modified_agi=150000,  # No allowance (phased out)
            activities=[loss_activity],
        )
        result = form.calculate_part_iii()

        # No passive income, no allowance
        # All $50k suspended
        assert result['line_18_unallowed_loss'] == 50000.0


# ============== Disposition Tests ==============

class TestDisposition:
    """Tests for passive activity disposition."""

    def test_complete_taxable_disposition_releases_loss(self):
        """Complete taxable disposition releases suspended losses."""
        activity = PassiveActivity(
            activity_name="Sold Activity",
            gross_income=0,
            deductions=0,
            prior_year_unallowed_loss=15000.0,
            disposed_during_year=True,
            disposition_type=DispositionType.COMPLETE_TAXABLE,
            disposition_gain_loss=5000.0,
        )
        form = Form8582(activities=[activity])
        result = form.calculate_disposition_release()

        assert result['total_released'] == 15000.0

    def test_no_release_without_complete_disposition(self):
        """Partial disposition does not release suspended loss."""
        activity = PassiveActivity(
            activity_name="Partial Sale",
            prior_year_unallowed_loss=15000.0,
            disposed_during_year=True,
            disposition_type=DispositionType.PARTIAL,
        )
        form = Form8582(activities=[activity])
        result = form.calculate_disposition_release()

        assert result['total_released'] == 0.0


# ============== PTP Tests ==============

class TestPubliclyTradedPartnership:
    """Tests for PTP separate basket rules."""

    def test_ptp_income_loss_separate(self):
        """PTP income/loss calculated separately."""
        form = Form8582(
            ptp_income=10000.0,
            ptp_losses=15000.0,
            ptp_suspended_loss=5000.0,
        )
        result = form.calculate_ptp_separately()

        # Net: 10000 - 15000 - 5000 = -10000
        assert result['net_ptp'] == -10000.0
        assert result['ptp_suspended'] == 10000.0


# ============== Integration Tests ==============

class TestForm8582Integration:
    """Tests for Form 8582 integration with Income and Engine."""

    def test_income_helper_methods(self):
        """Test Income model Form 8582 helper methods."""
        rental = make_passive_activity(
            name="Rental",
            gross_income=5000,
            deductions=20000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(modified_agi=80000, activities=[rental])
        income = Income(form_8582=form)

        # Loss = 15000, allowance = 15000 (full)
        assert income.get_form_8582_passive_loss_allowed() == 15000.0
        assert income.get_form_8582_rental_allowance() == 15000.0
        assert income.get_form_8582_suspended_loss() == 0.0

    def test_income_suspended_loss(self):
        """Test suspended loss calculation."""
        rental = make_passive_activity(
            name="Big Loss Rental",
            gross_income=0,
            deductions=50000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(modified_agi=80000, activities=[rental])
        income = Income(form_8582=form)

        # Loss = 50000, allowance = 25000
        # Suspended = 25000
        assert income.get_form_8582_passive_loss_allowed() == 25000.0
        assert income.get_form_8582_suspended_loss() == 25000.0

    def test_engine_calculates_form_8582(self, engine):
        """Test engine calculates Form 8582 fields."""
        rental = make_passive_activity(
            name="Rental",
            gross_income=8000,
            deductions=20000,
            is_rental=True,
            is_active_participant=True,
        )
        form = Form8582(modified_agi=90000, activities=[rental])
        tax_return = create_tax_return(form_8582=form)

        breakdown = engine.calculate(tax_return)

        # Loss = 12000, full allowance available
        assert breakdown.form_8582_passive_loss_allowed == 12000.0
        assert breakdown.form_8582_rental_allowance == 12000.0

    def test_form_8582_summary(self):
        """Test Form 8582 summary generation."""
        activity = make_passive_activity(
            name="Business",
            gross_income=10000,
            deductions=15000,
        )
        form = Form8582(modified_agi=100000, activities=[activity])
        income = Income(form_8582=form)

        summary = income.get_form_8582_summary()
        assert summary is not None
        assert 'part_i_summary' in summary
        assert 'part_ii_rental_allowance' in summary
        assert 'summary' in summary


# ============== Edge Cases ==============

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_no_activities(self):
        """Form 8582 with no activities."""
        form = Form8582(activities=[])
        result = form.calculate_all()

        assert result['summary']['total_passive_income'] == 0.0
        assert result['summary']['total_passive_loss'] == 0.0

    def test_all_income_no_loss(self):
        """Only passive income, no losses."""
        activity = make_passive_activity(
            gross_income=20000,
            deductions=5000,
        )
        form = Form8582(activities=[activity])
        result = form.calculate_all()

        assert result['summary']['suspended_loss_carryforward'] == 0.0

    def test_re_professional_exception(self):
        """Real estate professional treats rental as non-passive."""
        rental = make_passive_activity(
            name="Rental",
            gross_income=0,
            deductions=30000,
            taxpayer_hours=600,  # Material participation
            is_rental=True,
            is_active_participant=True,
            is_material_participation=True,
        )
        re_prof = RealEstateProfessional(
            real_property_hours=900,
            total_work_hours=1600,
        )
        form = Form8582(
            modified_agi=200000,  # Would normally phase out allowance
            activities=[rental],
            real_estate_professional=re_prof,
        )
        result = form.calculate_part_i()

        # RE professional with material participation:
        # Rental should be excluded from passive activities
        assert result['line_1b_rental_loss'] == 0.0  # Not counted as passive

    def test_agi_exactly_at_threshold(self):
        """AGI exactly at phaseout threshold."""
        result = calculate_agi_phaseout(agi=100000.0)
        assert result == 25000.0  # Full allowance at threshold

    def test_agi_one_dollar_over_threshold(self):
        """AGI $1 over threshold - 50 cents reduction."""
        result = calculate_agi_phaseout(agi=100001.0)
        # $1 * 50% = $0.50 reduction
        assert result == 24999.50


# ============== Helper Function Tests ==============

class TestHelperFunctions:
    """Tests for standalone helper functions."""

    def test_calculate_agi_phaseout_low(self):
        """AGI below threshold - full allowance."""
        result = calculate_agi_phaseout(agi=80000)
        assert result == 25000.0

    def test_calculate_agi_phaseout_mid(self):
        """AGI in phaseout range."""
        result = calculate_agi_phaseout(agi=120000)
        # $20k over threshold * 50% = $10k reduction
        assert result == 15000.0

    def test_calculate_agi_phaseout_high(self):
        """AGI above phaseout - no allowance."""
        result = calculate_agi_phaseout(agi=200000)
        assert result == 0.0

    def test_check_material_participation_500_hours(self):
        """Check material participation tests - 500 hours."""
        result = check_material_participation_tests(
            taxpayer_hours=550,
        )
        assert result['test_1_500_hours'] is True
        assert result['any_test_met'] is True

    def test_check_material_participation_with_spouse(self):
        """Check material participation tests - spouse hours combined."""
        result = check_material_participation_tests(
            taxpayer_hours=300,
            spouse_hours=250,
        )
        assert result['test_1_500_hours'] is True
        assert result['any_test_met'] is True
