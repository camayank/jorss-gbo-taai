"""
Test suite for Schedule D (Form 1040) - Capital Gains and Losses.

Tests cover:
- Part I: Short-term capital gains/losses
- Part II: Long-term capital gains/losses
- Part III: Summary and tax computation
- Capital loss deduction limit ($3,000)
- Loss carryforward calculation
- 60/40 rule for qualified dividends
"""

import pytest
from src.models.schedule_d import (
    ScheduleD,
    Form8949Summary,
    create_schedule_d,
)


class TestPartIShortTerm:
    """Tests for Part I - Short-term capital gains/losses."""

    def test_short_term_gain(self):
        """Short-term gain from Form 8949."""
        schedule = ScheduleD(
            form_8949_box_a=Form8949Summary(
                box_code="A",
                gain_loss=5000.0,
            )
        )
        result = schedule.calculate_part_i_short_term()

        assert result['line_7_net_short_term'] == 5000.0

    def test_short_term_loss(self):
        """Short-term loss from Form 8949."""
        schedule = ScheduleD(
            form_8949_box_b=Form8949Summary(
                box_code="B",
                gain_loss=-3000.0,
            )
        )
        result = schedule.calculate_part_i_short_term()

        assert result['line_7_net_short_term'] == -3000.0

    def test_short_term_with_carryover(self):
        """Short-term with loss carryover from prior year."""
        schedule = ScheduleD(
            form_8949_box_a=Form8949Summary(box_code="A", gain_loss=2000.0),
            st_loss_carryover=1500.0,
        )
        result = schedule.calculate_part_i_short_term()

        # $2,000 gain - $1,500 carryover = $500 net
        assert result['line_6_st_carryover'] == -1500.0
        assert result['line_7_net_short_term'] == 500.0

    def test_short_term_passthrough(self):
        """Short-term from partnerships/S corps."""
        schedule = ScheduleD(
            st_passthrough_gain=1500.0,
        )
        result = schedule.calculate_part_i_short_term()

        assert result['line_5_passthrough'] == 1500.0
        assert result['line_7_net_short_term'] == 1500.0


class TestPartIILongTerm:
    """Tests for Part II - Long-term capital gains/losses."""

    def test_long_term_gain(self):
        """Long-term gain from Form 8949."""
        schedule = ScheduleD(
            form_8949_box_d=Form8949Summary(
                box_code="D",
                gain_loss=10000.0,
            )
        )
        result = schedule.calculate_part_ii_long_term()

        assert result['line_15_net_long_term'] == 10000.0

    def test_long_term_loss(self):
        """Long-term loss from Form 8949."""
        schedule = ScheduleD(
            form_8949_box_e=Form8949Summary(
                box_code="E",
                gain_loss=-8000.0,
            )
        )
        result = schedule.calculate_part_ii_long_term()

        assert result['line_15_net_long_term'] == -8000.0

    def test_capital_gain_distributions(self):
        """Capital gain distributions from mutual funds."""
        schedule = ScheduleD(
            capital_gain_distributions=2500.0,
        )
        result = schedule.calculate_part_ii_long_term()

        assert result['line_13_cap_gain_dist'] == 2500.0
        assert result['line_15_net_long_term'] == 2500.0

    def test_long_term_with_carryover(self):
        """Long-term with loss carryover from prior year."""
        schedule = ScheduleD(
            form_8949_box_d=Form8949Summary(box_code="D", gain_loss=5000.0),
            lt_loss_carryover=3000.0,
        )
        result = schedule.calculate_part_ii_long_term()

        assert result['line_14_lt_carryover'] == -3000.0
        assert result['line_15_net_long_term'] == 2000.0

    def test_long_term_from_form_4797(self):
        """Long-term gain from Form 4797."""
        schedule = ScheduleD(
            lt_gain_from_4797=7500.0,
        )
        result = schedule.calculate_part_ii_long_term()

        assert result['line_11_other_lt_gain'] == 7500.0


class TestPartIIISummary:
    """Tests for Part III - Summary and capital loss deduction."""

    def test_net_capital_gain(self):
        """Net capital gain calculation."""
        schedule = ScheduleD(
            form_8949_box_a=Form8949Summary(box_code="A", gain_loss=2000.0),
            form_8949_box_d=Form8949Summary(box_code="D", gain_loss=8000.0),
        )
        result = schedule.calculate_part_iii_summary()

        assert result['line_16_combined'] == 10000.0
        assert result['is_net_gain'] is True
        assert result['net_capital_gain'] == 10000.0
        assert result['capital_loss_deduction'] == 0.0

    def test_net_capital_loss_under_limit(self):
        """Net capital loss under $3,000 limit."""
        schedule = ScheduleD(
            form_8949_box_a=Form8949Summary(box_code="A", gain_loss=-2000.0),
        )
        result = schedule.calculate_part_iii_summary()

        assert result['line_16_combined'] == -2000.0
        assert result['is_net_loss'] is True
        assert result['capital_loss_deduction'] == 2000.0
        assert result['new_st_carryover'] == 0.0

    def test_net_capital_loss_over_limit(self):
        """Net capital loss over $3,000 limit creates carryforward."""
        schedule = ScheduleD(
            form_8949_box_e=Form8949Summary(box_code="E", gain_loss=-10000.0),
        )
        result = schedule.calculate_part_iii_summary()

        assert result['capital_loss_deduction'] == 3000.0
        assert result['total_new_carryover'] == 7000.0

    def test_capital_loss_limit_mfs(self):
        """Married filing separately has $1,500 limit."""
        schedule = ScheduleD(
            filing_status="married_separate",
            form_8949_box_a=Form8949Summary(box_code="A", gain_loss=-5000.0),
        )
        result = schedule.calculate_part_iii_summary()

        assert result['loss_limit'] == 1500.0
        assert result['capital_loss_deduction'] == 1500.0

    def test_qualified_dividends_worksheet(self):
        """Use QD/CG worksheet when preferential income exists."""
        schedule = ScheduleD(
            form_8949_box_d=Form8949Summary(box_code="D", gain_loss=5000.0),
            qualified_dividends=3000.0,
        )
        result = schedule.calculate_part_iii_summary()

        assert result['use_preferential_worksheet'] is True
        assert result['qualified_dividends'] == 3000.0


class TestCompleteScheduleD:
    """Tests for complete Schedule D calculation."""

    def test_complete_with_gain(self):
        """Complete Schedule D with net gain."""
        schedule = ScheduleD(
            form_8949_box_a=Form8949Summary(box_code="A", gain_loss=1000.0),
            form_8949_box_d=Form8949Summary(box_code="D", gain_loss=5000.0),
            capital_gain_distributions=500.0,
            qualified_dividends=2000.0,
        )

        result = schedule.calculate_schedule_d()

        assert result['net_short_term_gain_loss'] == 1000.0
        assert result['net_long_term_gain_loss'] == 5500.0
        assert result['net_capital_gain_loss'] == 6500.0
        assert result['form_1040_line_7'] == 6500.0
        assert result['preferential_income'] == 8500.0  # $6500 gain + $2000 QD

    def test_complete_with_loss(self):
        """Complete Schedule D with net loss."""
        schedule = ScheduleD(
            form_8949_box_a=Form8949Summary(box_code="A", gain_loss=-2000.0),
            form_8949_box_d=Form8949Summary(box_code="D", gain_loss=-5000.0),
        )

        result = schedule.calculate_schedule_d()

        assert result['net_capital_gain_loss'] == -7000.0
        assert result['capital_loss_deduction'] == 3000.0
        assert result['form_1040_line_7'] == -3000.0
        assert result['new_st_carryover'] + result['new_lt_carryover'] == 4000.0

    def test_summary_method(self):
        """Get Schedule D summary."""
        schedule = ScheduleD(
            form_8949_box_d=Form8949Summary(box_code="D", gain_loss=10000.0),
        )

        summary = schedule.get_schedule_d_summary()

        assert summary['net_long_term'] == 10000.0
        assert summary['net_capital_gain_loss'] == 10000.0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_gain(self):
        """Create Schedule D with convenience function - gain."""
        result = create_schedule_d(
            short_term_gain_loss=2000.0,
            long_term_gain_loss=8000.0,
            qualified_dividends=3000.0,
        )

        assert result['net_short_term_gain_loss'] == 2000.0
        assert result['net_long_term_gain_loss'] == 8000.0
        assert result['net_capital_gain_loss'] == 10000.0

    def test_convenience_function_loss(self):
        """Create Schedule D with convenience function - loss."""
        result = create_schedule_d(
            short_term_gain_loss=-5000.0,
            long_term_gain_loss=-3000.0,
        )

        assert result['net_capital_gain_loss'] == -8000.0
        assert result['capital_loss_deduction'] == 3000.0

    def test_convenience_function_with_carryover(self):
        """Schedule D with loss carryovers."""
        result = create_schedule_d(
            long_term_gain_loss=5000.0,
            st_loss_carryover=2000.0,
            lt_loss_carryover=1000.0,
        )

        # $5000 LT gain - $2000 ST carryover - $1000 LT carryover = $2000
        assert result['net_capital_gain_loss'] == 2000.0

    def test_convenience_function_cap_gain_dist(self):
        """Schedule D with capital gain distributions."""
        result = create_schedule_d(
            capital_gain_distributions=3000.0,
        )

        assert result['net_long_term_gain_loss'] == 3000.0
