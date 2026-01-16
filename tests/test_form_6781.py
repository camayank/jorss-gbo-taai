"""
Test suite for Form 6781 - Gains and Losses From Section 1256 Contracts and Straddles.

Tests cover:
- Part I: Section 1256 contracts marked to market
- 60/40 rule (60% long-term, 40% short-term)
- Mark-to-market adjustments
- Loss carryback election
- Part II: Straddles
"""

import pytest
from src.models.form_6781 import (
    Form6781,
    Section1256Contract,
    ContractType,
    StraddlePosition,
    StraddleType,
    calculate_section_1256_gain_loss,
)


class TestSection1256Contracts:
    """Tests for Section 1256 contract calculations."""

    def test_single_futures_gain(self):
        """Single regulated futures contract gain."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="S&P 500 Futures",
                    contract_type=ContractType.REGULATED_FUTURES,
                    proceeds=50000.0,
                    cost_basis=40000.0,
                )
            ]
        )
        result = form.calculate_part_i()

        assert result['line_4_net_gain_loss'] == 10000.0

    def test_single_futures_loss(self):
        """Single regulated futures contract loss."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Crude Oil Futures",
                    contract_type=ContractType.REGULATED_FUTURES,
                    proceeds=30000.0,
                    cost_basis=40000.0,
                )
            ]
        )
        result = form.calculate_part_i()

        assert result['line_4_net_gain_loss'] == -10000.0

    def test_nonequity_options(self):
        """Nonequity options (index options)."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="SPX Index Options",
                    contract_type=ContractType.NONEQUITY_OPTIONS,
                    proceeds=25000.0,
                    cost_basis=20000.0,
                )
            ]
        )
        result = form.calculate_part_i()

        assert result['line_4_net_gain_loss'] == 5000.0

    def test_foreign_currency_contracts(self):
        """Foreign currency contracts."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="EUR/USD Futures",
                    contract_type=ContractType.FOREIGN_CURRENCY,
                    proceeds=15000.0,
                    cost_basis=12000.0,
                )
            ]
        )
        result = form.calculate_part_i()

        assert result['line_4_net_gain_loss'] == 3000.0

    def test_multiple_contracts(self):
        """Multiple Section 1256 contracts."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract 1",
                    proceeds=20000.0,
                    cost_basis=15000.0,
                ),
                Section1256Contract(
                    description="Contract 2",
                    proceeds=10000.0,
                    cost_basis=12000.0,
                ),
            ]
        )
        result = form.calculate_part_i()

        # $5k gain + $2k loss = $3k net
        assert result['line_4_net_gain_loss'] == 3000.0


class TestMarkToMarket:
    """Tests for mark-to-market adjustments."""

    def test_unrealized_gain_increase(self):
        """Unrealized gain increases from prior year."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Open Position",
                    prior_year_unrealized=5000.0,
                    current_year_unrealized=8000.0,
                )
            ]
        )
        result = form.calculate_part_i()

        # Adjustment: $8k - $5k = $3k gain
        assert result['line_4_net_gain_loss'] == 3000.0

    def test_unrealized_gain_decrease(self):
        """Unrealized gain decreases from prior year."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Open Position",
                    prior_year_unrealized=10000.0,
                    current_year_unrealized=6000.0,
                )
            ]
        )
        result = form.calculate_part_i()

        # Adjustment: $6k - $10k = -$4k loss
        assert result['line_4_net_gain_loss'] == -4000.0

    def test_combined_realized_and_unrealized(self):
        """Combined realized and unrealized gains/losses."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=15000.0,
                    cost_basis=12000.0,  # $3k realized gain
                    prior_year_unrealized=2000.0,
                    current_year_unrealized=5000.0,  # $3k unrealized gain
                )
            ]
        )
        result = form.calculate_part_i()

        # Total: $3k + $3k = $6k
        assert result['line_4_net_gain_loss'] == 6000.0


class TestSixtyFortyRule:
    """Tests for 60/40 split rule."""

    def test_gain_60_40_split(self):
        """Gain split 60% long-term, 40% short-term."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=20000.0,
                    cost_basis=10000.0,  # $10k gain
                )
            ]
        )
        result = form.calculate_part_i()

        assert result['line_8_net_section_1256'] == 10000.0
        assert result['line_9_short_term_40_pct'] == 4000.0
        assert result['line_10_long_term_60_pct'] == 6000.0

    def test_loss_60_40_split(self):
        """Loss split 60% long-term, 40% short-term."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=15000.0,
                    cost_basis=25000.0,  # $10k loss
                )
            ]
        )
        result = form.calculate_part_i()

        assert result['line_8_net_section_1256'] == -10000.0
        assert result['line_9_short_term_40_pct'] == -4000.0
        assert result['line_10_long_term_60_pct'] == -6000.0


class TestLossCarryover:
    """Tests for loss carryover and carryback."""

    def test_prior_year_loss_carryover(self):
        """Prior year loss carryover applied."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=20000.0,
                    cost_basis=15000.0,  # $5k gain
                )
            ],
            prior_year_loss_carryover=3000.0,
        )
        result = form.calculate_part_i()

        # $5k gain - $3k carryover = $2k net
        assert result['line_8_net_section_1256'] == 2000.0

    def test_loss_carryback_election(self):
        """Loss carryback election."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=10000.0,
                    cost_basis=30000.0,  # $20k loss
                )
            ],
            elect_loss_carryback=True,
            carryback_year_1=5000.0,
            carryback_year_2=5000.0,
            carryback_year_3=5000.0,
        )
        result = form.calculate_loss_carryback()

        assert result['carryback_elected'] is True
        assert result['total_carryback'] == 15000.0
        assert result['remaining_carryforward'] == 5000.0

    def test_no_carryback_for_gain(self):
        """No carryback available for gains."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=20000.0,
                    cost_basis=10000.0,  # $10k gain
                )
            ],
            elect_loss_carryback=True,
        )
        result = form.calculate_loss_carryback()

        # When there's a gain (not loss), carryback is not applicable
        assert result['carryback_elected'] is False
        assert result['remaining_carryforward'] == 0.0


class TestStraddles:
    """Tests for Part II - Straddles."""

    def test_identified_straddle_gain(self):
        """Identified straddle with gain."""
        form = Form6781(
            straddles=[
                StraddlePosition(
                    description="Stock/Option Straddle",
                    straddle_type=StraddleType.IDENTIFIED,
                    gain_on_disposition=5000.0,
                )
            ]
        )
        result = form.calculate_part_ii()

        assert result['total_gains'] == 5000.0
        assert result['net_straddle_gain_loss'] == 5000.0

    def test_straddle_loss(self):
        """Straddle with loss."""
        form = Form6781(
            straddles=[
                StraddlePosition(
                    description="Straddle",
                    loss_on_disposition=3000.0,
                )
            ]
        )
        result = form.calculate_part_ii()

        assert result['total_losses'] == 3000.0
        assert result['net_straddle_gain_loss'] == -3000.0

    def test_multiple_straddles(self):
        """Multiple straddle positions."""
        form = Form6781(
            straddles=[
                StraddlePosition(
                    description="Straddle 1",
                    gain_on_disposition=4000.0,
                ),
                StraddlePosition(
                    description="Straddle 2",
                    loss_on_disposition=2000.0,
                ),
            ]
        )
        result = form.calculate_part_ii()

        assert result['net_straddle_gain_loss'] == 2000.0


class TestCompleteForm6781:
    """Tests for complete Form 6781 calculation."""

    def test_complete_calculation(self):
        """Complete Form 6781 with contracts and straddles."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Futures",
                    proceeds=25000.0,
                    cost_basis=20000.0,
                )
            ],
            straddles=[
                StraddlePosition(
                    description="Straddle",
                    gain_on_disposition=2000.0,
                )
            ],
        )

        result = form.calculate_form_6781()

        assert result['section_1256_net'] == 5000.0
        assert result['section_1256_short_term'] == 2000.0
        assert result['section_1256_long_term'] == 3000.0
        assert result['straddle_net'] == 2000.0
        # Schedule D totals
        assert result['schedule_d_short_term'] == 4000.0  # $2k + $2k straddle
        assert result['schedule_d_long_term'] == 3000.0

    def test_summary_method(self):
        """Get Form 6781 summary."""
        form = Form6781(
            section_1256_contracts=[
                Section1256Contract(
                    description="Contract",
                    proceeds=30000.0,
                    cost_basis=20000.0,
                )
            ]
        )

        summary = form.get_form_6781_summary()

        assert summary['section_1256_net'] == 10000.0
        assert summary['short_term_40_pct'] == 4000.0
        assert summary['long_term_60_pct'] == 6000.0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_futures_gain(self):
        """Calculate futures gain with convenience function."""
        result = calculate_section_1256_gain_loss(
            futures_gain_loss=10000.0,
        )

        assert result['section_1256_net'] == 10000.0
        assert result['section_1256_short_term'] == 4000.0
        assert result['section_1256_long_term'] == 6000.0

    def test_convenience_function_options_loss(self):
        """Calculate options loss with convenience function."""
        result = calculate_section_1256_gain_loss(
            options_gain_loss=-5000.0,
        )

        assert result['section_1256_net'] == -5000.0

    def test_convenience_function_forex(self):
        """Calculate forex gain with convenience function."""
        result = calculate_section_1256_gain_loss(
            forex_gain_loss=3000.0,
        )

        assert result['section_1256_net'] == 3000.0

    def test_convenience_function_combined(self):
        """Combined futures, options, and forex."""
        result = calculate_section_1256_gain_loss(
            futures_gain_loss=8000.0,
            options_gain_loss=-3000.0,
            forex_gain_loss=2000.0,
        )

        # $8k + (-$3k) + $2k = $7k
        assert result['section_1256_net'] == 7000.0

    def test_convenience_function_unrealized(self):
        """Mark-to-market unrealized adjustments."""
        result = calculate_section_1256_gain_loss(
            prior_year_unrealized=5000.0,
            current_year_unrealized=8000.0,
        )

        # $8k - $5k = $3k adjustment
        assert result['section_1256_net'] == 3000.0

    def test_convenience_function_with_carryover(self):
        """With prior year loss carryover."""
        result = calculate_section_1256_gain_loss(
            futures_gain_loss=10000.0,
            prior_year_loss_carryover=4000.0,
        )

        # $10k - $4k = $6k net
        assert result['section_1256_net'] == 6000.0
