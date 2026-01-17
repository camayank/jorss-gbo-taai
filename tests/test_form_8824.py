"""
Tests for Form 8824 - Like-Kind Exchanges (Section 1031)

Comprehensive test suite covering:
- Basic like-kind exchange calculations
- Boot (cash/property) received
- Liability assumptions and relief
- 45-day identification period
- 180-day exchange period
- Related party rules
- Gain recognition and deferral
- Basis calculation for new property
"""

import pytest
from datetime import date, timedelta
from src.models.form_8824 import (
    Form8824,
    Form8824Part1,
    Form8824Part2,
    Form8824Part3,
    PropertyType,
    ExchangeType,
    RelatedPartyType,
    calculate_like_kind_exchange,
    calculate_exchange_timeline,
)


class TestForm8824Part1ExchangeInfo:
    """Test Part I: Exchange information and timeline."""

    def test_basic_exchange_dates(self):
        """Test basic exchange date tracking."""
        part1 = Form8824Part1(
            line_1_property_given_description="123 Main St, Rental Property",
            line_2_property_received_description="456 Oak Ave, Rental Property",
            line_3_date_acquired=date(2015, 1, 15),
            line_4_date_transferred=date(2025, 3, 1),
            line_5_date_identified=date(2025, 4, 1),
            line_6_date_received=date(2025, 6, 1),
        )
        assert part1.days_to_identify == 31  # 31 days
        assert part1.days_to_complete == 92  # 92 days

    def test_45_day_identification_period_met(self):
        """Test 45-day identification period is satisfied."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 1, 1),
            line_5_date_identified=date(2025, 2, 14),  # 44 days
            line_6_date_received=date(2025, 5, 1),
        )
        assert part1.days_to_identify == 44
        assert part1.identification_period_met is True

    def test_45_day_identification_period_exactly_45(self):
        """Test exactly 45 days is valid."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 1, 1),
            line_5_date_identified=date(2025, 2, 15),  # 45 days
            line_6_date_received=date(2025, 5, 1),
        )
        assert part1.days_to_identify == 45
        assert part1.identification_period_met is True

    def test_45_day_identification_period_exceeded(self):
        """Test 45-day identification period exceeded."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 1, 1),
            line_5_date_identified=date(2025, 2, 20),  # 50 days
            line_6_date_received=date(2025, 5, 1),
        )
        assert part1.days_to_identify == 50
        assert part1.identification_period_met is False

    def test_180_day_exchange_period_met(self):
        """Test 180-day exchange period is satisfied."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 1, 1),
            line_5_date_identified=date(2025, 2, 1),
            line_6_date_received=date(2025, 6, 15),  # 165 days
        )
        assert part1.days_to_complete == 165
        assert part1.exchange_period_met is True

    def test_180_day_exchange_period_exactly_180(self):
        """Test exactly 180 days is valid."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 1, 1),
            line_5_date_identified=date(2025, 2, 1),
            line_6_date_received=date(2025, 6, 30),  # 180 days
        )
        assert part1.days_to_complete == 180
        assert part1.exchange_period_met is True

    def test_180_day_exchange_period_exceeded(self):
        """Test 180-day exchange period exceeded."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 1, 1),
            line_5_date_identified=date(2025, 2, 1),
            line_6_date_received=date(2025, 7, 15),  # 195 days
        )
        assert part1.days_to_complete == 195
        assert part1.exchange_period_met is False

    def test_valid_exchange_timeline(self):
        """Test complete valid exchange timeline."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 3, 1),
            line_5_date_identified=date(2025, 4, 10),  # 40 days
            line_6_date_received=date(2025, 7, 1),  # 122 days
        )
        assert part1.valid_exchange_timeline is True

    def test_invalid_exchange_timeline_id_late(self):
        """Test invalid timeline - identification too late."""
        part1 = Form8824Part1(
            line_4_date_transferred=date(2025, 3, 1),
            line_5_date_identified=date(2025, 4, 20),  # 50 days - too late
            line_6_date_received=date(2025, 7, 1),
        )
        assert part1.valid_exchange_timeline is False

    def test_no_dates_returns_none(self):
        """Test missing dates return None."""
        part1 = Form8824Part1()
        assert part1.days_to_identify is None
        assert part1.days_to_complete is None


class TestForm8824Part2RelatedParty:
    """Test Part II: Related party exchange rules."""

    def test_not_related_party(self):
        """Test non-related party exchange."""
        part2 = Form8824Part2(
            line_8_relationship=RelatedPartyType.NONE
        )
        assert part2.is_related_party_exchange is False

    def test_family_related_party(self):
        """Test family member is related party."""
        part2 = Form8824Part2(
            line_7_related_party_name="John Smith",
            line_8_relationship=RelatedPartyType.FAMILY,
            line_9_related_party_tin="123-45-6789"
        )
        assert part2.is_related_party_exchange is True

    def test_controlled_entity_related(self):
        """Test controlled entity is related party."""
        part2 = Form8824Part2(
            line_7_related_party_name="Smith Holdings LLC",
            line_8_relationship=RelatedPartyType.CONTROLLED_ENTITY,
        )
        assert part2.is_related_party_exchange is True

    def test_no_disposition_compliant(self):
        """Test no disposition within 2 years is compliant."""
        part2 = Form8824Part2(
            line_8_relationship=RelatedPartyType.FAMILY,
            line_10_property_disposed=False,
            line_11_you_disposed=False
        )
        assert part2.gain_triggered_by_disposition is False

    def test_related_party_disposed_triggers_gain(self):
        """Test related party disposition triggers gain."""
        part2 = Form8824Part2(
            line_8_relationship=RelatedPartyType.FAMILY,
            line_10_property_disposed=True,  # Related party sold
        )
        assert part2.gain_triggered_by_disposition is True

    def test_you_disposed_triggers_gain(self):
        """Test your disposition triggers gain."""
        part2 = Form8824Part2(
            line_8_relationship=RelatedPartyType.FAMILY,
            line_11_you_disposed=True,  # You sold
        )
        assert part2.gain_triggered_by_disposition is True


class TestForm8824Part3BasicCalculations:
    """Test Part III: Basic gain/loss calculations."""

    def test_simple_equal_exchange_no_boot(self):
        """Test simple exchange with equal values, no boot."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=500000,
            line_19_basis_like_kind_given=300000,
        )
        # Total received = 500000, Total given = 300000
        # Realized gain = 500000 - 300000 = 200000
        assert part3.line_27_realized_gain == 200000
        # No boot, so no recognized gain
        assert part3.line_24_total_boot == 0
        assert part3.line_29_recognized_gain == 0

    def test_exchange_with_cash_boot(self):
        """Test exchange where cash boot is received."""
        part3 = Form8824Part3(
            line_15_cash_received=50000,  # Cash boot
            line_18_fmv_like_kind_received=450000,
            line_19_basis_like_kind_given=300000,
        )
        # Total boot = 50000
        assert part3.line_24_total_boot == 50000
        # Total received = 450000 + 50000 = 500000
        # Realized gain = 500000 - 300000 = 200000
        assert part3.line_27_realized_gain == 200000
        # Recognized gain = min(50000, 200000) = 50000
        assert part3.line_29_recognized_gain == 50000

    def test_exchange_with_property_boot(self):
        """Test exchange where non-like-kind property is received."""
        part3 = Form8824Part3(
            line_16_fmv_other_property_received=30000,  # Car received
            line_18_fmv_like_kind_received=470000,
            line_19_basis_like_kind_given=300000,
        )
        # Boot = 30000
        assert part3.line_17_total_boot_received == 30000
        # Realized gain = 500000 - 300000 = 200000
        # Recognized = min(30000, 200000) = 30000
        assert part3.line_29_recognized_gain == 30000

    def test_exchange_with_liability_relief(self):
        """Test exchange where mortgage is relieved (net boot)."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=500000,
            line_19_basis_like_kind_given=200000,
            line_20_liabilities_assumed_by_other=100000,  # Mortgage relieved
            line_22_liabilities_you_assumed=0,
        )
        # Net boot from liabilities = 100000 - 0 = 100000
        assert part3.line_23_net_boot_from_liabilities == 100000
        # Total boot = 100000
        assert part3.line_24_total_boot == 100000
        # Recognized = min(100000, realized gain)
        # Total received = 500000 + 100000 = 600000
        # Realized gain = 600000 - 200000 = 400000
        assert part3.line_27_realized_gain == 400000
        assert part3.line_29_recognized_gain == 100000

    def test_exchange_with_both_liabilities(self):
        """Test exchange where both parties have liabilities."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=600000,
            line_19_basis_like_kind_given=300000,
            line_20_liabilities_assumed_by_other=150000,  # They assumed your mortgage
            line_22_liabilities_you_assumed=100000,  # You assumed their mortgage
        )
        # Net boot = 150000 - 100000 = 50000
        assert part3.line_23_net_boot_from_liabilities == 50000
        assert part3.line_24_total_boot == 50000

    def test_exchange_assume_more_liabilities_no_boot(self):
        """Test exchange where you assume more liabilities (no boot)."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=500000,
            line_19_basis_like_kind_given=300000,
            line_20_liabilities_assumed_by_other=50000,
            line_22_liabilities_you_assumed=100000,  # You assumed more
        )
        # Net boot = max(0, 50000 - 100000) = 0
        assert part3.line_23_net_boot_from_liabilities == 0
        assert part3.line_24_total_boot == 0

    def test_boot_exceeds_gain_recognition_limited(self):
        """Test boot exceeds realized gain - recognition limited."""
        part3 = Form8824Part3(
            line_15_cash_received=100000,  # Large cash boot
            line_18_fmv_like_kind_received=400000,
            line_19_basis_like_kind_given=450000,  # High basis
        )
        # Total received = 500000, Total given = 450000
        # Realized gain = 50000
        assert part3.line_27_realized_gain == 50000
        # Boot = 100000, but only recognize up to gain
        assert part3.line_29_recognized_gain == 50000

    def test_realized_loss_not_recognized(self):
        """Test realized loss is not recognized in like-kind exchange."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=400000,
            line_19_basis_like_kind_given=500000,  # Basis exceeds FMV
        )
        # Loss = 500000 - 400000 = 100000
        assert part3.line_27_realized_gain == 0
        assert part3.line_28_realized_loss == 100000
        assert part3.line_29_recognized_gain == 0


class TestForm8824Part3BasisCalculation:
    """Test Part III: New property basis calculations."""

    def test_basis_no_boot_no_gain_recognition(self):
        """Test basis calculation with no boot (full deferral)."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=500000,
            line_19_basis_like_kind_given=300000,
        )
        # Realized gain = 200000, Recognized = 0
        # Deferred gain = 200000
        # New basis = 500000 - 200000 = 300000 (carries over)
        assert part3.basis_of_like_kind_property_received == 300000

    def test_basis_with_boot_partial_recognition(self):
        """Test basis calculation with partial gain recognition."""
        part3 = Form8824Part3(
            line_15_cash_received=50000,
            line_18_fmv_like_kind_received=450000,
            line_19_basis_like_kind_given=300000,
        )
        # Realized gain = 200000, Boot = 50000
        # Recognized = 50000, Deferred = 150000
        # New basis = 450000 - 150000 = 300000
        assert part3.basis_of_like_kind_property_received == 300000

    def test_basis_with_full_recognition(self):
        """Test basis when all gain is recognized (boot >= gain)."""
        part3 = Form8824Part3(
            line_15_cash_received=100000,
            line_18_fmv_like_kind_received=400000,
            line_19_basis_like_kind_given=450000,
        )
        # Realized gain = 50000, Boot = 100000
        # Recognized = 50000 (all of it), Deferred = 0
        # New basis = 400000 - 0 = 400000 (FMV)
        assert part3.basis_of_like_kind_property_received == 400000

    def test_basis_with_liabilities(self):
        """Test basis calculation with liability exchange."""
        part3 = Form8824Part3(
            line_18_fmv_like_kind_received=600000,
            line_19_basis_like_kind_given=400000,
            line_20_liabilities_assumed_by_other=100000,
            line_22_liabilities_you_assumed=50000,
        )
        # Net boot = 50000
        # Total received = 600000 + 50000 = 650000
        # Total given = 400000 + 50000 = 450000
        # Realized gain = 650000 - 450000 = 200000
        # Recognized = min(50000, 200000) = 50000
        # Deferred = 150000
        # New basis = 600000 - 150000 = 450000
        assert part3.basis_of_like_kind_property_received == 450000


class TestForm8824CompleteExchange:
    """Test complete Form 8824 exchange scenarios."""

    def test_simple_rental_property_exchange(self):
        """Test simple rental property exchange."""
        form = Form8824(
            tax_year=2025,
            exchange_type=ExchangeType.DEFERRED,
            property_type=PropertyType.REAL_PROPERTY,
            part_1=Form8824Part1(
                line_1_property_given_description="123 Main St, Duplex",
                line_2_property_received_description="456 Oak Ave, Triplex",
                line_4_date_transferred=date(2025, 3, 1),
                line_5_date_identified=date(2025, 4, 1),
                line_6_date_received=date(2025, 6, 1),
            ),
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=750000,
                line_19_basis_like_kind_given=400000,
            )
        )
        assert form.is_valid_exchange() is True
        assert form.realized_gain == 350000
        assert form.recognized_gain == 0
        assert form.deferred_gain == 350000
        assert form.new_property_basis == 400000  # Carryover basis

    def test_exchange_with_boot_and_mortgage(self):
        """Test exchange with cash boot and mortgage assumption."""
        form = Form8824(
            part_3=Form8824Part3(
                line_15_cash_received=75000,  # Cash boot
                line_18_fmv_like_kind_received=600000,
                line_19_basis_like_kind_given=350000,
                line_20_liabilities_assumed_by_other=200000,  # Mortgage relieved
                line_22_liabilities_you_assumed=150000,  # Mortgage assumed
            )
        )
        # Net liability boot = 200000 - 150000 = 50000
        # Total boot = 75000 + 50000 = 125000
        assert form.total_boot_received == 125000

        # Total received = 600000 + 125000 = 725000
        # Total given = 350000 + 150000 = 500000
        # Realized gain = 225000
        assert form.realized_gain == 225000

        # Recognized = min(125000, 225000) = 125000
        assert form.recognized_gain == 125000
        assert form.deferred_gain == 100000

    def test_trading_up_no_boot(self):
        """Test trading up to more expensive property (no boot)."""
        form = Form8824(
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=1000000,
                line_19_basis_like_kind_given=500000,
                line_22_liabilities_you_assumed=300000,  # You take on bigger mortgage
                line_26_cash_paid=200000,  # You pay cash difference
            )
        )
        # No boot received (you're paying, not receiving)
        assert form.total_boot_received == 0
        # All gain deferred
        assert form.recognized_gain == 0

    def test_simultaneous_exchange_no_timeline_check(self):
        """Test simultaneous exchange doesn't require timeline."""
        form = Form8824(
            exchange_type=ExchangeType.SIMULTANEOUS,
            part_1=Form8824Part1(
                line_4_date_transferred=date(2025, 3, 1),
                line_6_date_received=date(2025, 3, 1),  # Same day
            ),
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=500000,
                line_19_basis_like_kind_given=300000,
            )
        )
        assert form.is_valid_exchange() is True

    def test_related_party_exchange_compliant(self):
        """Test compliant related party exchange."""
        form = Form8824(
            part_2=Form8824Part2(
                line_7_related_party_name="Smith Family Trust",
                line_8_relationship=RelatedPartyType.TRUST_BENEFICIARY,
                line_10_property_disposed=False,
                line_11_you_disposed=False,
            ),
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=400000,
                line_19_basis_like_kind_given=250000,
            )
        )
        assert form.is_related_party_compliant() is True
        assert form.recognized_gain == 0  # Full deferral

    def test_related_party_exchange_not_compliant(self):
        """Test non-compliant related party exchange (disposition)."""
        form = Form8824(
            part_2=Form8824Part2(
                line_8_relationship=RelatedPartyType.FAMILY,
                line_10_property_disposed=True,  # Related party sold within 2 years
            ),
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=400000,
                line_19_basis_like_kind_given=250000,
            )
        )
        assert form.is_related_party_compliant() is False


class TestForm8824ToDictionary:
    """Test Form 8824 to_dict serialization."""

    def test_to_dict_basic(self):
        """Test basic dictionary output."""
        form = Form8824(
            tax_year=2025,
            exchange_type=ExchangeType.DEFERRED,
            part_1=Form8824Part1(
                line_1_property_given_description="Old Property",
                line_2_property_received_description="New Property",
                line_4_date_transferred=date(2025, 3, 1),
                line_5_date_identified=date(2025, 4, 1),
                line_6_date_received=date(2025, 5, 15),
            ),
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=500000,
                line_19_basis_like_kind_given=300000,
                line_15_cash_received=25000,
            )
        )
        result = form.to_dict()

        assert result["tax_year"] == 2025
        assert result["exchange_type"] == "deferred"
        assert result["exchange_info"]["property_given"] == "Old Property"
        assert result["exchange_info"]["valid_timeline"] is True
        assert result["calculations"]["fmv_property_received"] == 500000
        assert result["calculations"]["boot_received"] == 25000
        assert result["calculations"]["recognized_gain"] == 25000

    def test_to_schedule_d(self):
        """Test Schedule D output."""
        form = Form8824(
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=500000,
                line_19_basis_like_kind_given=300000,
                line_15_cash_received=50000,
            )
        )
        result = form.to_schedule_d()

        # Total received = 500000 + 50000 = 550000
        # Total given = 300000
        # Realized gain = 250000, Boot = 50000
        # Recognized = 50000, Deferred = 200000
        assert result["gain_recognized"] == 50000
        assert result["gain_deferred"] == 200000


class TestConvenienceFunction:
    """Test calculate_like_kind_exchange convenience function."""

    def test_simple_exchange(self):
        """Test simple like-kind exchange."""
        result = calculate_like_kind_exchange(
            fmv_property_received=500000,
            basis_property_given=300000,
        )
        assert result["realized_gain"] == 200000
        assert result["recognized_gain"] == 0
        assert result["deferred_gain"] == 200000
        assert result["new_property_basis"] == 300000
        assert result["is_taxable"] is False

    def test_exchange_with_cash(self):
        """Test exchange receiving cash boot."""
        result = calculate_like_kind_exchange(
            fmv_property_received=450000,
            basis_property_given=300000,
            cash_received=50000,
        )
        assert result["boot_received"] == 50000
        assert result["recognized_gain"] == 50000
        assert result["is_taxable"] is True

    def test_exchange_with_liabilities(self):
        """Test exchange with mortgage swap."""
        result = calculate_like_kind_exchange(
            fmv_property_received=600000,
            basis_property_given=400000,
            liabilities_relieved=200000,
            liabilities_assumed=100000,
        )
        # Net boot = 100000 from liability relief
        assert result["boot_received"] == 100000
        assert result["recognized_gain"] == 100000


class TestExchangeTimeline:
    """Test calculate_exchange_timeline function."""

    def test_timeline_calculation(self):
        """Test timeline deadline calculations."""
        result = calculate_exchange_timeline(
            transfer_date=date(2025, 3, 1)
        )
        assert result["transfer_date"] == "2025-03-01"
        assert result["identification_deadline"] == "2025-04-15"  # +45 days
        assert result["exchange_deadline"] == "2025-08-28"  # +180 days

    def test_timeline_with_dates(self):
        """Test timeline with actual dates."""
        result = calculate_exchange_timeline(
            transfer_date=date(2025, 3, 1),
            identification_date=date(2025, 4, 1),  # 31 days
            receipt_date=date(2025, 6, 1),  # 92 days
        )
        assert result["days_to_identify"] == 31
        assert result["identification_valid"] is True
        assert result["days_to_complete"] == 92
        assert result["exchange_valid"] is True

    def test_timeline_invalid_identification(self):
        """Test invalid identification period."""
        result = calculate_exchange_timeline(
            transfer_date=date(2025, 3, 1),
            identification_date=date(2025, 4, 20),  # 50 days - too late
        )
        assert result["days_to_identify"] == 50
        assert result["identification_valid"] is False


class TestForm8824EdgeCases:
    """Test Form 8824 edge cases."""

    def test_zero_basis_property(self):
        """Test property with zero basis (fully depreciated)."""
        form = Form8824(
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=300000,
                line_19_basis_like_kind_given=0,  # Fully depreciated
            )
        )
        assert form.realized_gain == 300000
        assert form.recognized_gain == 0  # All deferred, no boot
        assert form.new_property_basis == 0  # Zero carryover basis

    def test_equal_fmv_and_basis(self):
        """Test no gain or loss scenario."""
        form = Form8824(
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=400000,
                line_19_basis_like_kind_given=400000,
            )
        )
        assert form.realized_gain == 0
        assert form.realized_loss == 0
        assert form.recognized_gain == 0

    def test_loss_exchange(self):
        """Test exchange with built-in loss."""
        form = Form8824(
            part_3=Form8824Part3(
                line_18_fmv_like_kind_received=300000,
                line_19_basis_like_kind_given=400000,  # Loss property
            )
        )
        assert form.realized_gain == 0
        assert form.realized_loss == 100000
        # Loss not deductible in like-kind exchange
        assert form.recognized_gain == 0

    def test_multiple_boot_types(self):
        """Test exchange with multiple types of boot."""
        form = Form8824(
            part_3=Form8824Part3(
                line_15_cash_received=25000,  # Cash
                line_16_fmv_other_property_received=15000,  # Car
                line_18_fmv_like_kind_received=500000,
                line_19_basis_like_kind_given=350000,
                line_20_liabilities_assumed_by_other=60000,  # Mortgage relief
                line_22_liabilities_you_assumed=20000,  # Mortgage assumed
            )
        )
        # Total boot = 25000 + 15000 + (60000 - 20000) = 80000
        assert form.total_boot_received == 80000


class TestForm8824PropertyTypes:
    """Test property type validation."""

    def test_real_property_valid(self):
        """Test real property is valid for 2025."""
        form = Form8824(
            tax_year=2025,
            property_type=PropertyType.REAL_PROPERTY
        )
        assert form.property_type == PropertyType.REAL_PROPERTY

    def test_personal_property_post_2017_invalid(self):
        """Test personal property invalid after 2017."""
        with pytest.raises(ValueError) as excinfo:
            Form8824(
                tax_year=2025,
                property_type=PropertyType.PERSONAL_PROPERTY
            )
        assert "does not qualify" in str(excinfo.value)

    def test_exchange_type_values(self):
        """Test exchange type enum values."""
        assert ExchangeType.SIMULTANEOUS.value == "simultaneous"
        assert ExchangeType.DEFERRED.value == "deferred"
        assert ExchangeType.REVERSE.value == "reverse"
        assert ExchangeType.IMPROVEMENT.value == "improvement"


class TestForm8824GainCharacter:
    """Test gain character determination."""

    def test_gain_character_calculation(self):
        """Test character of gain calculation."""
        form = Form8824(
            part_3=Form8824Part3(
                line_15_cash_received=50000,
                line_18_fmv_like_kind_received=450000,
                line_19_basis_like_kind_given=300000,
            )
        )
        character = form.calculate_character_of_gain()
        assert "ordinary_income" in character
        assert "section_1231_gain" in character
        assert "capital_gain" in character
        # Basic implementation returns recognized as 1231
        assert character["section_1231_gain"] == 50000
