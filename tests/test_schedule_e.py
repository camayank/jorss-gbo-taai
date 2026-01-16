"""
Test suite for Schedule E (Form 1040) - Supplemental Income and Loss.

Tests cover:
- Part I: Rental real estate and royalties
- Part II: Partnerships and S corporations (K-1)
- Part III: Estates and trusts (K-1)
- Passive activity loss limitations
- Real estate professional rules
"""

import pytest
from src.models.schedule_e import (
    ScheduleE,
    RentalProperty,
    PropertyType,
    PartnershipSCorpK1,
    EstateTrustK1,
    create_schedule_e,
)


class TestPartIRentals:
    """Tests for Part I - Rental real estate and royalties."""

    def test_single_rental_profit(self):
        """Single rental property with profit."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="123 Main St",
                    rents_received=24000.0,
                    repairs=3000.0,
                    insurance=1200.0,
                    taxes=2400.0,
                    mortgage_interest=6000.0,
                    depreciation=5000.0,
                )
            ]
        )
        result = schedule.calculate_part_i_rentals()

        assert result['total_income'] == 24000.0
        assert result['total_expenses'] == 17600.0
        assert result['allowed_rental_income_loss'] == 6400.0

    def test_single_rental_loss(self):
        """Single rental property with loss."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="123 Main St",
                    rents_received=12000.0,
                    repairs=5000.0,
                    insurance=1200.0,
                    taxes=2400.0,
                    mortgage_interest=8000.0,
                    depreciation=6000.0,
                )
            ],
            is_active_participant=True,
            agi_for_pal=80000.0,
        )
        result = schedule.calculate_part_i_rentals()

        # Loss: $12k - $22.6k = -$10.6k
        assert result['net_rental_before_pal'] < 0
        # Active participant, AGI under $100k = full $25k allowance
        assert result['allowed_rental_income_loss'] < 0

    def test_passive_loss_limitation(self):
        """Passive loss limited without active participation."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="123 Main St",
                    rents_received=10000.0,
                    repairs=20000.0,  # Large loss
                )
            ],
            is_active_participant=False,
            agi_for_pal=100000.0,
        )
        result = schedule.calculate_part_i_rentals()

        # Not active participant - all loss suspended
        assert result['allowed_rental_income_loss'] == 0.0
        assert result['suspended_passive_loss'] > 0

    def test_pal_allowance_phaseout(self):
        """PAL $25k allowance phases out $100k-$150k AGI."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="123 Main St",
                    rents_received=10000.0,
                    repairs=30000.0,  # $20k loss
                )
            ],
            is_active_participant=True,
            agi_for_pal=120000.0,  # $20k over threshold
        )
        result = schedule.calculate_part_i_rentals()

        # Allowance reduced by 50% of excess: $25k - ($20k × 0.5) = $15k
        # But loss is only $20k, and allowance is $15k
        assert result['allowed_rental_income_loss'] == -15000.0

    def test_real_estate_professional(self):
        """Real estate professional not subject to PAL."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="123 Main St",
                    rents_received=10000.0,
                    repairs=40000.0,  # Large loss
                )
            ],
            is_real_estate_professional=True,
            agi_for_pal=200000.0,
        )
        result = schedule.calculate_part_i_rentals()

        # RE professional - full loss allowed
        assert result['allowed_rental_income_loss'] == -30000.0
        assert result['suspended_passive_loss'] == 0.0

    def test_multiple_properties(self):
        """Multiple rental properties aggregated."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="Property 1",
                    rents_received=15000.0,
                    repairs=5000.0,
                ),
                RentalProperty(
                    property_address="Property 2",
                    rents_received=18000.0,
                    repairs=8000.0,
                ),
            ]
        )
        result = schedule.calculate_part_i_rentals()

        assert result['property_count'] == 2
        assert result['total_income'] == 33000.0


class TestPartIIPartnerships:
    """Tests for Part II - Partnerships and S corporations."""

    def test_partnership_income(self):
        """Partnership K-1 income."""
        schedule = ScheduleE(
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="ABC Partnership",
                    is_s_corp=False,
                    ordinary_income_loss=25000.0,
                    is_passive=True,
                )
            ]
        )
        result = schedule.calculate_part_ii_partnerships()

        assert result['k1_count'] == 1
        assert result['total_passive_income'] == 25000.0
        assert result['net_passive'] == 25000.0

    def test_scorp_income(self):
        """S corporation K-1 income."""
        schedule = ScheduleE(
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="XYZ S Corp",
                    is_s_corp=True,
                    ordinary_income_loss=50000.0,
                    is_passive=False,  # Active in business
                )
            ]
        )
        result = schedule.calculate_part_ii_partnerships()

        assert result['total_nonpassive_income'] == 50000.0

    def test_partnership_loss(self):
        """Partnership with loss."""
        schedule = ScheduleE(
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="Loss Partnership",
                    ordinary_income_loss=-15000.0,
                    is_passive=True,
                )
            ]
        )
        result = schedule.calculate_part_ii_partnerships()

        assert result['total_passive_loss'] == 15000.0
        assert result['net_passive'] == -15000.0

    def test_guaranteed_payments(self):
        """Partnership guaranteed payments."""
        schedule = ScheduleE(
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="Partnership",
                    ordinary_income_loss=20000.0,
                    guaranteed_payments=10000.0,
                    is_passive=True,
                )
            ]
        )
        result = schedule.calculate_part_ii_partnerships()

        # Total: $20k + $10k = $30k
        assert result['net_passive'] == 30000.0

    def test_self_employment_income(self):
        """Partnership self-employment income."""
        schedule = ScheduleE(
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="GP Partnership",
                    self_employment_income=40000.0,
                )
            ]
        )
        result = schedule.calculate_part_ii_partnerships()

        assert result['total_self_employment'] == 40000.0

    def test_qbi_from_partnership(self):
        """QBI from partnership."""
        schedule = ScheduleE(
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="QBI Partnership",
                    ordinary_income_loss=50000.0,
                    qbi_income=50000.0,
                )
            ]
        )
        result = schedule.calculate_part_ii_partnerships()

        assert result['total_qbi'] == 50000.0


class TestPartIIIEstatesTrusts:
    """Tests for Part III - Estates and trusts."""

    def test_estate_income(self):
        """Estate K-1 income."""
        schedule = ScheduleE(
            estate_trust_k1s=[
                EstateTrustK1(
                    entity_name="Smith Estate",
                    is_estate=True,
                    interest_income=5000.0,
                    ordinary_dividends=3000.0,
                )
            ]
        )
        result = schedule.calculate_part_iii_estates_trusts()

        assert result['k1_count'] == 1
        assert result['net_income_loss'] == 8000.0

    def test_trust_income(self):
        """Trust K-1 income."""
        schedule = ScheduleE(
            estate_trust_k1s=[
                EstateTrustK1(
                    entity_name="Family Trust",
                    is_estate=False,
                    interest_income=10000.0,
                    net_long_term_gain=5000.0,
                )
            ]
        )
        result = schedule.calculate_part_iii_estates_trusts()

        assert result['net_income_loss'] == 15000.0


class TestCompleteScheduleE:
    """Tests for complete Schedule E calculation."""

    def test_complete_calculation(self):
        """Complete Schedule E with all parts."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="Rental",
                    rents_received=20000.0,
                    repairs=5000.0,
                    depreciation=4000.0,
                )
            ],
            partnership_scorp_k1s=[
                PartnershipSCorpK1(
                    entity_name="Partnership",
                    ordinary_income_loss=15000.0,
                    is_passive=True,
                )
            ],
            is_active_participant=True,
            agi_for_pal=80000.0,
        )

        result = schedule.calculate_schedule_e()

        assert result['part_i_rental_total'] == 11000.0
        assert result['part_ii_partnership_total'] == 15000.0
        assert result['total_supplemental_income'] == 26000.0

    def test_summary_method(self):
        """Get Schedule E summary."""
        schedule = ScheduleE(
            rental_properties=[
                RentalProperty(
                    property_address="Rental",
                    rents_received=18000.0,
                    repairs=6000.0,
                )
            ]
        )

        summary = schedule.get_schedule_e_summary()

        assert 'rental_income_loss' in summary
        assert summary['rental_income_loss'] == 12000.0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_rental(self):
        """Create Schedule E with rental income."""
        result = create_schedule_e(
            rental_income=24000.0,
            rental_expenses=8000.0,
            rental_depreciation=5000.0,
            is_active_participant=True,
            agi=80000.0,
        )

        # Income: $24k, Expenses: $8k allocated + $5k depreciation = $11k net
        assert result['part_i_rental_total'] == 11000.0

    def test_convenience_function_partnership(self):
        """Create Schedule E with partnership income."""
        result = create_schedule_e(
            partnership_income=30000.0,
        )

        assert result['part_ii_partnership_total'] == 30000.0

    def test_convenience_function_scorp(self):
        """Create Schedule E with S corp income."""
        result = create_schedule_e(
            s_corp_income=25000.0,
        )

        assert result['part_ii_partnership_total'] == 25000.0

    def test_convenience_function_combined(self):
        """Create Schedule E with rental and partnership."""
        result = create_schedule_e(
            rental_income=20000.0,
            rental_expenses=5000.0,
            partnership_income=15000.0,
            is_active_participant=True,
            agi=90000.0,
        )

        assert result['total_supplemental_income'] > 0
