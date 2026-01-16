"""
Form 8582 - Passive Activity Loss Limitations

Implements IRS Form 8582 per IRC Section 469 for limiting deductions
from passive activities.

Key Concepts:
- Passive activities: Business/rental activities without material participation
- Material participation: 7 tests to determine if taxpayer materially participates
- $25,000 rental loss allowance: Active participants can deduct up to $25k
- Real estate professional: Can treat rental activities as non-passive
- Suspended losses: Disallowed losses carried forward to future years
- Disposition rules: Suspended losses released on complete disposition

IRC References:
- Section 469: Passive activity loss limitations
- Section 469(c)(7): Real estate professional exception
- Section 469(i): $25,000 offset for rental real estate
- Section 469(g): Dispositions of entire interests
"""

from typing import Optional, List, Dict, ClassVar
from pydantic import BaseModel, Field
from enum import Enum


class ActivityType(str, Enum):
    """Types of activities for passive activity rules."""
    RENTAL_REAL_ESTATE = "rental_real_estate"
    RENTAL_OTHER = "rental_other"  # Equipment rental, etc.
    TRADE_OR_BUSINESS = "trade_or_business"
    WORKING_INTEREST_OIL_GAS = "working_interest_oil_gas"  # Exception to PAL
    LIMITED_PARTNERSHIP = "limited_partnership"
    S_CORPORATION = "s_corporation"
    PUBLICLY_TRADED_PARTNERSHIP = "publicly_traded_partnership"  # Separate basket


class MaterialParticipationTest(str, Enum):
    """
    Seven material participation tests under Reg. 1.469-5T.

    A taxpayer materially participates if ANY ONE test is met.
    """
    TEST_1_500_HOURS = "test_1_500_hours"
    # 500+ hours of participation during the year

    TEST_2_SUBSTANTIALLY_ALL = "test_2_substantially_all"
    # Taxpayer's participation constitutes substantially all participation

    TEST_3_100_HOURS_NOT_LESS = "test_3_100_hours_not_less"
    # 100+ hours and not less than any other individual

    TEST_4_SIGNIFICANT_PARTICIPATION = "test_4_significant_participation"
    # Significant participation activities (100-500 hrs) totaling 500+ hrs

    TEST_5_PRIOR_5_OF_10_YEARS = "test_5_prior_5_of_10_years"
    # Material participation in 5 of prior 10 years

    TEST_6_PERSONAL_SERVICE_3_YEARS = "test_6_personal_service_3_years"
    # Personal service activity with material participation in 3 prior years

    TEST_7_FACTS_AND_CIRCUMSTANCES = "test_7_facts_and_circumstances"
    # 100+ hours and facts/circumstances show regular, continuous, substantial


class DispositionType(str, Enum):
    """Types of passive activity dispositions."""
    COMPLETE_TAXABLE = "complete_taxable"  # Releases all suspended losses
    COMPLETE_NONTAXABLE = "complete_nontaxable"  # Like-kind exchange
    PARTIAL = "partial"  # Does not release suspended losses
    DEATH = "death"  # Special rules apply
    GIFT = "gift"  # Basis adjustment for suspended losses
    INSTALLMENT_SALE = "installment_sale"  # Pro-rata release


class PassiveActivity(BaseModel):
    """
    Individual passive activity for Form 8582 tracking.

    Tracks income, losses, material participation, and suspended losses
    for each separate activity.
    """
    # Activity identification
    activity_name: str = Field(description="Name/description of the activity")
    activity_type: ActivityType = Field(default=ActivityType.TRADE_OR_BUSINESS)

    # Activity ID for grouping (optional)
    activity_id: Optional[str] = Field(default=None)
    grouped_with: Optional[str] = Field(
        default=None,
        description="Activity ID this activity is grouped with"
    )

    # Current year amounts
    gross_income: float = Field(default=0.0, ge=0)
    deductions: float = Field(default=0.0, ge=0)
    prior_year_unallowed_loss: float = Field(
        default=0.0, ge=0,
        description="Suspended loss from prior years"
    )

    # Material participation
    taxpayer_hours: float = Field(default=0.0, ge=0, description="Taxpayer's hours")
    spouse_hours: float = Field(default=0.0, ge=0, description="Spouse's hours (if joint)")
    total_activity_hours: float = Field(
        default=0.0, ge=0,
        description="Total hours by all participants"
    )
    material_participation_test_met: Optional[MaterialParticipationTest] = Field(default=None)
    is_material_participation: bool = Field(default=False)

    # Rental real estate specific
    is_rental_real_estate: bool = Field(default=False)
    is_active_participant: bool = Field(
        default=False,
        description="Active participation (10%+ ownership, management involvement)"
    )
    ownership_percentage: float = Field(default=100.0, ge=0, le=100)

    # Disposition tracking
    disposed_during_year: bool = Field(default=False)
    disposition_type: Optional[DispositionType] = Field(default=None)
    disposition_gain_loss: float = Field(default=0.0)

    # At-risk limitation (Form 6198)
    at_risk_amount: Optional[float] = Field(
        default=None,
        description="Amount at risk (Form 6198). None = unlimited"
    )

    def get_net_income_loss(self) -> float:
        """Calculate net income or loss for current year."""
        return self.gross_income - self.deductions

    def get_total_loss_available(self) -> float:
        """Get total loss including prior year suspended loss."""
        current_loss = max(0.0, -self.get_net_income_loss())
        return current_loss + self.prior_year_unallowed_loss

    def is_passive(self) -> bool:
        """
        Determine if activity is passive.

        Not passive if:
        - Material participation in trade/business
        - Working interest in oil/gas (liability not limited)
        - Real estate professional with material participation
        """
        # Working interest in oil/gas is never passive (if liability not limited)
        if self.activity_type == ActivityType.WORKING_INTEREST_OIL_GAS:
            return False

        # Material participation makes trade/business non-passive
        if self.is_material_participation:
            return False

        return True

    def check_material_participation(self) -> tuple:
        """
        Check all material participation tests.

        Returns:
            Tuple of (is_material_participation, test_met)
        """
        combined_hours = self.taxpayer_hours + self.spouse_hours

        # Test 1: 500+ hours
        if combined_hours >= 500:
            return True, MaterialParticipationTest.TEST_1_500_HOURS

        # Test 2: Substantially all participation
        if self.total_activity_hours > 0:
            participation_ratio = combined_hours / self.total_activity_hours
            if participation_ratio >= 0.90:  # Substantially all
                return True, MaterialParticipationTest.TEST_2_SUBSTANTIALLY_ALL

        # Test 3: 100+ hours and not less than any other
        if combined_hours >= 100:
            if self.total_activity_hours <= combined_hours * 2:
                # Simplified: If taxpayer hours >= half of total, likely not less than others
                return True, MaterialParticipationTest.TEST_3_100_HOURS_NOT_LESS

        # Test 7: 100+ hours with facts/circumstances
        # This is subjective, so we use the is_material_participation flag
        if combined_hours >= 100 and self.is_material_participation:
            return True, MaterialParticipationTest.TEST_7_FACTS_AND_CIRCUMSTANCES

        # Tests 4, 5, 6 require additional data tracking (not implemented here)
        # They would need to be set externally

        return False, None


class RentalRealEstateAllowance(BaseModel):
    """
    Calculates the $25,000 special allowance for rental real estate losses.

    IRC Section 469(i):
    - Up to $25,000 of rental real estate losses allowed against non-passive income
    - Requires active participation (10%+ ownership + involvement in management)
    - Phases out between $100,000-$150,000 modified AGI
    - $12,500 for married filing separately (living apart all year)
    """
    # AGI for phaseout calculation
    modified_agi: float = Field(ge=0)

    # Filing status affects allowance and phaseout
    is_married_filing_separately: bool = Field(default=False)
    lived_apart_all_year: bool = Field(default=False)

    # Rental real estate losses eligible for allowance
    eligible_rental_losses: float = Field(default=0.0, ge=0)

    # Maximum allowance amounts
    MAX_ALLOWANCE_SINGLE: ClassVar[float] = 25000.0
    MAX_ALLOWANCE_MFS_APART: ClassVar[float] = 12500.0
    PHASEOUT_START_SINGLE: ClassVar[float] = 100000.0
    PHASEOUT_START_MFS: ClassVar[float] = 50000.0
    PHASEOUT_RATE: ClassVar[float] = 0.50  # $1 reduction for every $2 over threshold

    def calculate_allowance(self) -> dict:
        """
        Calculate the rental real estate loss allowance.

        Returns:
            Dict with allowance calculation details
        """
        result = {
            'max_allowance': 0.0,
            'phaseout_start': 0.0,
            'phaseout_amount': 0.0,
            'available_allowance': 0.0,
            'allowance_used': 0.0,
            'disallowed': 0.0,
        }

        # MFS not living apart: No allowance
        if self.is_married_filing_separately and not self.lived_apart_all_year:
            return result

        # Determine maximum allowance and phaseout threshold
        if self.is_married_filing_separately and self.lived_apart_all_year:
            result['max_allowance'] = self.MAX_ALLOWANCE_MFS_APART
            result['phaseout_start'] = self.PHASEOUT_START_MFS
        else:
            result['max_allowance'] = self.MAX_ALLOWANCE_SINGLE
            result['phaseout_start'] = self.PHASEOUT_START_SINGLE

        # Calculate phaseout
        if self.modified_agi > result['phaseout_start']:
            excess_agi = self.modified_agi - result['phaseout_start']
            result['phaseout_amount'] = excess_agi * self.PHASEOUT_RATE
            result['available_allowance'] = max(
                0.0,
                result['max_allowance'] - result['phaseout_amount']
            )
        else:
            result['available_allowance'] = result['max_allowance']

        # Apply allowance to eligible losses
        result['allowance_used'] = min(
            self.eligible_rental_losses,
            result['available_allowance']
        )
        result['disallowed'] = self.eligible_rental_losses - result['allowance_used']

        return result


class RealEstateProfessional(BaseModel):
    """
    Real estate professional status determination.

    IRC Section 469(c)(7):
    To qualify, taxpayer must meet BOTH:
    1. More than 750 hours in real property trades/businesses
    2. More than 50% of personal services in real property activities

    Effect: Rental real estate activities can be treated as non-passive
    if taxpayer also materially participates in each rental activity.
    """
    # Hours in real property trades/businesses
    real_property_hours: float = Field(default=0.0, ge=0)

    # Total hours in all trades/businesses
    total_work_hours: float = Field(default=0.0, ge=0)

    # Election to aggregate rental activities
    elected_to_aggregate_rentals: bool = Field(default=False)

    def qualifies_as_professional(self) -> bool:
        """Check if taxpayer qualifies as real estate professional."""
        # Test 1: More than 750 hours in real property activities
        if self.real_property_hours <= 750:
            return False

        # Test 2: More than 50% of personal services in real property
        if self.total_work_hours > 0:
            if self.real_property_hours / self.total_work_hours <= 0.50:
                return False
        else:
            return False

        return True

    def calculate_status(self) -> dict:
        """Calculate real estate professional status with details."""
        qualifies = self.qualifies_as_professional()

        return {
            'qualifies': qualifies,
            'real_property_hours': self.real_property_hours,
            'total_work_hours': self.total_work_hours,
            'hours_test_met': self.real_property_hours > 750,
            'percentage_test_met': (
                self.total_work_hours > 0 and
                self.real_property_hours / self.total_work_hours > 0.50
            ),
            'percentage': (
                self.real_property_hours / self.total_work_hours * 100
                if self.total_work_hours > 0 else 0
            ),
            'aggregation_elected': self.elected_to_aggregate_rentals,
        }


class Form8582(BaseModel):
    """
    IRS Form 8582 - Passive Activity Loss Limitations

    Limits deductions from passive activities to passive income.

    Parts:
    - Part I: Total passive activity loss
    - Part II: Special allowance for rental real estate
    - Part III: Total losses allowed

    Key Rules:
    1. Passive losses can only offset passive income
    2. $25,000 rental exception for active participants (AGI phaseout)
    3. Real estate professionals can treat rentals as non-passive
    4. Suspended losses carry forward indefinitely
    5. Complete disposition releases all suspended losses
    """
    # Tax year and filing information
    tax_year: int = Field(default=2025)
    modified_agi: float = Field(default=0.0, ge=0)
    is_married_filing_separately: bool = Field(default=False)
    lived_apart_all_year: bool = Field(default=False)

    # Passive activities
    activities: List[PassiveActivity] = Field(default_factory=list)

    # Real estate professional status
    real_estate_professional: Optional[RealEstateProfessional] = Field(default=None)

    # Carryforward from prior years
    prior_year_suspended_loss: float = Field(default=0.0, ge=0)

    # Publicly traded partnership (PTP) - separate basket
    ptp_income: float = Field(default=0.0, ge=0)
    ptp_losses: float = Field(default=0.0, ge=0)
    ptp_suspended_loss: float = Field(default=0.0, ge=0)

    def _get_passive_activities(self) -> List[PassiveActivity]:
        """Get list of activities that are passive."""
        passive = []
        for activity in self.activities:
            # Check material participation for each activity
            if not activity.is_material_participation:
                is_mp, test = activity.check_material_participation()
                activity.is_material_participation = is_mp
                activity.material_participation_test_met = test

            # Real estate professional exception
            if (self.real_estate_professional and
                self.real_estate_professional.qualifies_as_professional() and
                activity.is_rental_real_estate and
                activity.is_material_participation):
                # Rental treated as non-passive for RE professional
                continue

            if activity.is_passive():
                passive.append(activity)

        return passive

    def _get_rental_activities(self) -> List[PassiveActivity]:
        """Get rental real estate activities eligible for $25k allowance."""
        rentals = []
        for activity in self.activities:
            if (activity.is_rental_real_estate and
                activity.is_active_participant and
                activity.ownership_percentage >= 10):
                rentals.append(activity)
        return rentals

    def calculate_part_i(self) -> dict:
        """
        Calculate Part I - 2025 Passive Activity Loss.

        Combines:
        - Rental real estate activities with active participation
        - All other passive activities
        """
        result = {
            # Rental Real Estate With Active Participation
            'line_1a_rental_income': 0.0,
            'line_1b_rental_loss': 0.0,
            'line_1c_prior_rental_loss': 0.0,
            'line_1d_total_rental': 0.0,

            # All Other Passive Activities
            'line_2a_other_income': 0.0,
            'line_2b_other_loss': 0.0,
            'line_2c_prior_other_loss': 0.0,
            'line_2d_total_other': 0.0,

            # Combined totals
            'line_3_total_income': 0.0,
            'line_4_total_loss': 0.0,

            'activity_details': [],
        }

        passive_activities = self._get_passive_activities()

        for activity in passive_activities:
            net = activity.get_net_income_loss()
            prior_loss = activity.prior_year_unallowed_loss

            detail = {
                'name': activity.activity_name,
                'type': activity.activity_type.value,
                'net_income_loss': net,
                'prior_unallowed': prior_loss,
                'is_rental': activity.is_rental_real_estate,
                'is_active_participant': activity.is_active_participant,
            }
            result['activity_details'].append(detail)

            # Categorize into rental vs other
            if activity.is_rental_real_estate and activity.is_active_participant:
                if net > 0:
                    result['line_1a_rental_income'] += net
                else:
                    result['line_1b_rental_loss'] += abs(net)
                result['line_1c_prior_rental_loss'] += prior_loss
            else:
                if net > 0:
                    result['line_2a_other_income'] += net
                else:
                    result['line_2b_other_loss'] += abs(net)
                result['line_2c_prior_other_loss'] += prior_loss

        # Calculate totals for each category
        result['line_1d_total_rental'] = (
            result['line_1a_rental_income'] -
            result['line_1b_rental_loss'] -
            result['line_1c_prior_rental_loss']
        )

        result['line_2d_total_other'] = (
            result['line_2a_other_income'] -
            result['line_2b_other_loss'] -
            result['line_2c_prior_other_loss']
        )

        # Combined totals
        result['line_3_total_income'] = (
            result['line_1a_rental_income'] +
            result['line_2a_other_income']
        )

        result['line_4_total_loss'] = (
            result['line_1b_rental_loss'] +
            result['line_1c_prior_rental_loss'] +
            result['line_2b_other_loss'] +
            result['line_2c_prior_other_loss']
        )

        return result

    def calculate_part_ii(self) -> dict:
        """
        Calculate Part II - Special Allowance for Rental Real Estate.

        Up to $25,000 of rental real estate losses can be deducted
        against non-passive income if taxpayer actively participates.
        Phases out between $100,000-$150,000 MAGI.
        """
        # Get rental losses eligible for allowance
        rental_activities = self._get_rental_activities()
        eligible_loss = 0.0

        for activity in rental_activities:
            net = activity.get_net_income_loss()
            if net < 0:
                eligible_loss += abs(net) + activity.prior_year_unallowed_loss

        # Calculate allowance
        allowance_calc = RentalRealEstateAllowance(
            modified_agi=self.modified_agi,
            is_married_filing_separately=self.is_married_filing_separately,
            lived_apart_all_year=self.lived_apart_all_year,
            eligible_rental_losses=eligible_loss,
        )
        allowance_result = allowance_calc.calculate_allowance()

        return {
            'line_5_rental_loss': eligible_loss,
            'line_6_phaseout_reduction': allowance_result['phaseout_amount'],
            'line_7_max_allowance': allowance_result['max_allowance'],
            'line_8_modified_agi': self.modified_agi,
            'line_9_phaseout_threshold': allowance_result['phaseout_start'],
            'line_10_allowance_available': allowance_result['available_allowance'],
            'line_11_allowance_used': allowance_result['allowance_used'],
            'eligible_activities': len(rental_activities),
            'calculation_details': allowance_result,
        }

    def calculate_part_iii(self) -> dict:
        """
        Calculate Part III - Total Losses Allowed.

        Total allowed = passive income + special allowance
        """
        part_i = self.calculate_part_i()
        part_ii = self.calculate_part_ii()

        # Net passive income (if positive)
        net_passive_income = max(0.0, part_i['line_3_total_income'] - part_i['line_4_total_loss'])

        # If there's net passive income, all losses are allowed against it
        if net_passive_income > 0:
            # Losses up to passive income are allowed
            losses_against_income = min(part_i['line_4_total_loss'], part_i['line_3_total_income'])
        else:
            losses_against_income = part_i['line_3_total_income']

        # Add special allowance
        special_allowance = part_ii['line_11_allowance_used']

        # Total losses allowed
        total_allowed = losses_against_income + special_allowance

        # Unallowed loss (suspended)
        unallowed_loss = max(0.0, part_i['line_4_total_loss'] - total_allowed)

        return {
            'line_12_total_passive_income': part_i['line_3_total_income'],
            'line_13_total_passive_loss': part_i['line_4_total_loss'],
            'line_14_net_passive': part_i['line_3_total_income'] - part_i['line_4_total_loss'],
            'line_15_losses_against_income': losses_against_income,
            'line_16_special_allowance': special_allowance,
            'line_17_total_losses_allowed': total_allowed,
            'line_18_unallowed_loss': unallowed_loss,
        }

    def calculate_disposition_release(self) -> dict:
        """
        Calculate suspended loss release from complete dispositions.

        When a passive activity is completely disposed of in a
        fully taxable transaction, all suspended losses are released.
        """
        released_losses = 0.0
        disposition_details = []

        for activity in self.activities:
            if activity.disposed_during_year:
                if activity.disposition_type == DispositionType.COMPLETE_TAXABLE:
                    # Release all suspended losses
                    released = activity.prior_year_unallowed_loss
                    released_losses += released
                    disposition_details.append({
                        'activity': activity.activity_name,
                        'disposition_type': activity.disposition_type.value,
                        'gain_loss': activity.disposition_gain_loss,
                        'suspended_loss_released': released,
                    })
                elif activity.disposition_type == DispositionType.INSTALLMENT_SALE:
                    # Pro-rata release based on payments received
                    # Simplified: assume some portion released
                    released = activity.prior_year_unallowed_loss * 0.2  # Placeholder
                    released_losses += released
                    disposition_details.append({
                        'activity': activity.activity_name,
                        'disposition_type': activity.disposition_type.value,
                        'gain_loss': activity.disposition_gain_loss,
                        'suspended_loss_released': released,
                    })

        return {
            'total_released': released_losses,
            'dispositions': disposition_details,
        }

    def calculate_ptp_separately(self) -> dict:
        """
        Calculate publicly traded partnership (PTP) passive income/loss.

        PTPs are treated in a separate basket - PTP losses can only
        offset PTP income, not other passive income.
        """
        net_ptp = self.ptp_income - self.ptp_losses - self.ptp_suspended_loss

        return {
            'ptp_income': self.ptp_income,
            'ptp_losses': self.ptp_losses,
            'ptp_prior_suspended': self.ptp_suspended_loss,
            'net_ptp': net_ptp,
            'ptp_allowed': max(0.0, net_ptp) if net_ptp < 0 else self.ptp_losses,
            'ptp_suspended': max(0.0, -net_ptp) if net_ptp < 0 else 0.0,
        }

    def calculate_all(self) -> dict:
        """
        Calculate complete Form 8582.
        """
        part_i = self.calculate_part_i()
        part_ii = self.calculate_part_ii()
        part_iii = self.calculate_part_iii()
        disposition = self.calculate_disposition_release()
        ptp = self.calculate_ptp_separately()

        # Real estate professional status
        re_professional = None
        if self.real_estate_professional:
            re_professional = self.real_estate_professional.calculate_status()

        # Summary
        total_losses_allowed = (
            part_iii['line_17_total_losses_allowed'] +
            disposition['total_released']
        )

        suspended_loss_carryforward = (
            part_iii['line_18_unallowed_loss'] -
            disposition['total_released']
        )
        suspended_loss_carryforward = max(0.0, suspended_loss_carryforward)

        return {
            'tax_year': self.tax_year,
            'part_i': part_i,
            'part_ii': part_ii,
            'part_iii': part_iii,
            'disposition': disposition,
            'ptp': ptp,
            'real_estate_professional': re_professional,
            'summary': {
                'total_passive_income': part_i['line_3_total_income'],
                'total_passive_loss': part_i['line_4_total_loss'],
                'rental_allowance_used': part_ii['line_11_allowance_used'],
                'total_losses_allowed': total_losses_allowed,
                'suspended_loss_carryforward': suspended_loss_carryforward,
                'disposition_releases': disposition['total_released'],
            }
        }

    def get_total_passive_loss_allowed(self) -> float:
        """Get total passive activity loss allowed for current year."""
        result = self.calculate_all()
        return result['summary']['total_losses_allowed']

    def get_suspended_loss_carryforward(self) -> float:
        """Get suspended loss to carry forward to next year."""
        result = self.calculate_all()
        return result['summary']['suspended_loss_carryforward']

    def get_rental_allowance_used(self) -> float:
        """Get $25,000 rental allowance amount used."""
        result = self.calculate_all()
        return result['summary']['rental_allowance_used']

    def get_net_passive_income(self) -> float:
        """Get net passive income (if positive)."""
        result = self.calculate_all()
        net = result['summary']['total_passive_income'] - result['summary']['total_passive_loss']
        return max(0.0, net)

    def generate_form_8582_summary(self) -> dict:
        """Generate comprehensive Form 8582 summary."""
        result = self.calculate_all()

        return {
            'tax_year': self.tax_year,
            'modified_agi': self.modified_agi,
            'total_activities': len(self.activities),
            'passive_activities': len(self._get_passive_activities()),
            'rental_activities_eligible': len(self._get_rental_activities()),
            'part_i_summary': {
                'rental_income': result['part_i']['line_1a_rental_income'],
                'rental_loss': result['part_i']['line_1b_rental_loss'],
                'other_passive_income': result['part_i']['line_2a_other_income'],
                'other_passive_loss': result['part_i']['line_2b_other_loss'],
            },
            'part_ii_rental_allowance': {
                'eligible_loss': result['part_ii']['line_5_rental_loss'],
                'max_allowance': result['part_ii']['line_7_max_allowance'],
                'phaseout_reduction': result['part_ii']['line_6_phaseout_reduction'],
                'allowance_used': result['part_ii']['line_11_allowance_used'],
            },
            'part_iii_totals': {
                'total_allowed': result['part_iii']['line_17_total_losses_allowed'],
                'unallowed_suspended': result['part_iii']['line_18_unallowed_loss'],
            },
            'real_estate_professional': result['real_estate_professional'],
            'summary': result['summary'],
        }


def calculate_agi_phaseout(
    agi: float,
    threshold: float = 100000.0,
    max_allowance: float = 25000.0,
    phaseout_rate: float = 0.50
) -> float:
    """
    Calculate AGI-based phaseout of rental allowance.

    Returns the remaining allowance after phaseout.
    """
    if agi <= threshold:
        return max_allowance

    reduction = (agi - threshold) * phaseout_rate
    return max(0.0, max_allowance - reduction)


def check_material_participation_tests(
    taxpayer_hours: float,
    spouse_hours: float = 0.0,
    total_activity_hours: float = 0.0,
    years_material_participation: int = 0,
    is_personal_service: bool = False
) -> Dict[str, bool]:
    """
    Check all seven material participation tests.

    Returns dict indicating which tests are met.
    """
    combined = taxpayer_hours + spouse_hours

    results = {
        'test_1_500_hours': combined >= 500,
        'test_2_substantially_all': (
            total_activity_hours > 0 and
            combined / total_activity_hours >= 0.90
        ),
        'test_3_100_hours_not_less': (
            combined >= 100 and
            total_activity_hours <= combined * 2  # Simplified
        ),
        'test_4_significant_participation': False,  # Requires multi-activity tracking
        'test_5_prior_5_of_10': years_material_participation >= 5,
        'test_6_personal_service_3_years': (
            is_personal_service and years_material_participation >= 3
        ),
        'test_7_facts_circumstances': combined >= 100,  # Subjective
        'any_test_met': False,
    }

    results['any_test_met'] = any([
        results['test_1_500_hours'],
        results['test_2_substantially_all'],
        results['test_3_100_hours_not_less'],
        results['test_5_prior_5_of_10'],
        results['test_6_personal_service_3_years'],
    ])

    return results
