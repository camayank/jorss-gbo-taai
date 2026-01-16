"""
Form 6781 - Gains and Losses From Section 1256 Contracts and Straddles

IRS Form for reporting:
- Part I: Section 1256 contracts marked to market
- Part II: Gains and losses from straddles
- Part III: Unrecognized gains from offsetting positions

Section 1256 Contracts Include:
- Regulated futures contracts (commodities, financial futures)
- Foreign currency contracts
- Nonequity options (index options, futures options)
- Dealer equity options
- Dealer securities futures contracts

Key Rules:
- Mark-to-market: Treated as sold at FMV on last day of tax year
- 60/40 Rule: Gains/losses are 60% long-term, 40% short-term
- Loss carryback: Can carry back net Section 1256 losses 3 years
- Straddles: Special rules for offsetting positions
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ContractType(str, Enum):
    """Type of Section 1256 contract."""
    REGULATED_FUTURES = "regulated_futures"
    FOREIGN_CURRENCY = "foreign_currency"
    NONEQUITY_OPTIONS = "nonequity_options"
    DEALER_EQUITY_OPTIONS = "dealer_equity_options"
    DEALER_SECURITIES_FUTURES = "dealer_securities_futures"


class StraddleType(str, Enum):
    """Type of straddle position."""
    IDENTIFIED = "identified"  # Identified straddle (properly elected)
    MIXED = "mixed"  # Mixed straddle (Section 1256 and non-1256)
    SECTION_1092 = "section_1092"  # General straddle rules


class Section1256Contract(BaseModel):
    """Individual Section 1256 contract or position."""
    description: str = Field(description="Description of contract")
    contract_type: ContractType = Field(
        default=ContractType.REGULATED_FUTURES,
        description="Type of Section 1256 contract"
    )
    broker_name: str = Field(default="", description="Broker name")

    # Form 1099-B amounts
    proceeds: float = Field(default=0.0, description="Proceeds from closed contracts")
    cost_basis: float = Field(default=0.0, description="Cost or other basis")

    # Mark-to-market adjustments
    prior_year_unrealized: float = Field(
        default=0.0,
        description="Unrealized gain/loss at end of prior year"
    )
    current_year_unrealized: float = Field(
        default=0.0,
        description="Unrealized gain/loss at end of current year"
    )

    def realized_gain_loss(self) -> float:
        """Calculate realized gain/loss from closed contracts."""
        return self.proceeds - self.cost_basis

    def unrealized_adjustment(self) -> float:
        """Calculate unrealized gain/loss adjustment (mark-to-market)."""
        return self.current_year_unrealized - self.prior_year_unrealized

    def total_gain_loss(self) -> float:
        """Calculate total gain/loss for tax purposes."""
        return self.realized_gain_loss() + self.unrealized_adjustment()


class StraddlePosition(BaseModel):
    """Straddle position for Part II."""
    description: str = Field(description="Description of straddle")
    straddle_type: StraddleType = Field(
        default=StraddleType.IDENTIFIED,
        description="Type of straddle"
    )

    # Gains and losses
    gain_on_disposition: float = Field(
        default=0.0, ge=0,
        description="Gain from disposition of position"
    )
    loss_on_disposition: float = Field(
        default=0.0, ge=0,
        description="Loss from disposition of position"
    )

    # Unrecognized amounts
    unrecognized_gain_prior: float = Field(
        default=0.0, ge=0,
        description="Unrecognized gain from prior year"
    )
    unrecognized_loss_current: float = Field(
        default=0.0, ge=0,
        description="Loss deferred to future year"
    )

    # Offsetting position information
    has_offsetting_position: bool = Field(
        default=False,
        description="Has an offsetting position"
    )


class Form6781(BaseModel):
    """
    Form 6781 - Gains and Losses From Section 1256 Contracts and Straddles

    Complete model for reporting regulated futures, options, and straddles.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Part I: Section 1256 Contracts Marked to Market
    section_1256_contracts: List[Section1256Contract] = Field(
        default_factory=list,
        description="List of Section 1256 contracts"
    )

    # Part II: Gains and Losses From Straddles
    straddles: List[StraddlePosition] = Field(
        default_factory=list,
        description="List of straddle positions"
    )

    # Loss carryback election
    elect_loss_carryback: bool = Field(
        default=False,
        description="Elect to carry back Section 1256 losses"
    )
    carryback_year_1: float = Field(
        default=0.0, ge=0,
        description="Amount to carry back 1 year"
    )
    carryback_year_2: float = Field(
        default=0.0, ge=0,
        description="Amount to carry back 2 years"
    )
    carryback_year_3: float = Field(
        default=0.0, ge=0,
        description="Amount to carry back 3 years"
    )

    # Prior year carryover
    prior_year_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Section 1256 loss carryover from prior year"
    )

    # Mixed straddle election
    mixed_straddle_election: bool = Field(
        default=False,
        description="Made mixed straddle election under Reg 1.1092(b)-4T"
    )

    def calculate_part_i(self) -> Dict[str, Any]:
        """
        Calculate Part I - Section 1256 Contracts Marked to Market.

        Returns 60/40 split of gains and losses.
        """
        total_realized = 0.0
        total_unrealized_adj = 0.0
        total_gain_loss = 0.0

        contract_details = []
        for contract in self.section_1256_contracts:
            realized = contract.realized_gain_loss()
            unrealized = contract.unrealized_adjustment()
            total = contract.total_gain_loss()

            total_realized += realized
            total_unrealized_adj += unrealized
            total_gain_loss += total

            contract_details.append({
                'description': contract.description,
                'type': contract.contract_type.value,
                'realized': round(realized, 2),
                'unrealized_adjustment': round(unrealized, 2),
                'total': round(total, 2),
            })

        # Line 1: Gain or loss from 1099-B
        line_1 = total_realized

        # Line 2: Add unrealized profit/loss at year end
        line_2 = 0.0  # Current year unrealized
        for contract in self.section_1256_contracts:
            line_2 += contract.current_year_unrealized

        # Line 3: Subtract unrealized profit/loss at prior year end
        line_3 = 0.0
        for contract in self.section_1256_contracts:
            line_3 += contract.prior_year_unrealized

        # Line 4: Net gain/loss (1 + 2 - 3)
        line_4 = line_1 + line_2 - line_3

        # Line 5: Form 1099-B adjustment (if different reporting)
        line_5 = 0.0

        # Line 6: Combine lines 4 and 5
        line_6 = line_4 + line_5

        # Line 7: Loss carryover from prior year (entered as negative)
        line_7 = -self.prior_year_loss_carryover if self.prior_year_loss_carryover > 0 else 0.0

        # Line 8: Net Section 1256 contracts gain/loss
        line_8 = line_6 + line_7

        # 60/40 Rule: 60% long-term, 40% short-term
        if line_8 >= 0:
            # Gain
            long_term_portion = line_8 * 0.60
            short_term_portion = line_8 * 0.40
            net_loss_for_carryback = 0.0
        else:
            # Loss
            long_term_portion = line_8 * 0.60
            short_term_portion = line_8 * 0.40
            net_loss_for_carryback = abs(line_8)

        return {
            'contract_count': len(self.section_1256_contracts),
            'contracts': contract_details,

            # Line items
            'line_1_1099b_gain_loss': round(line_1, 2),
            'line_2_unrealized_current': round(line_2, 2),
            'line_3_unrealized_prior': round(line_3, 2),
            'line_4_net_gain_loss': round(line_4, 2),
            'line_6_combined': round(line_6, 2),
            'line_7_loss_carryover': round(line_7, 2),
            'line_8_net_section_1256': round(line_8, 2),

            # 60/40 split
            'line_9_short_term_40_pct': round(short_term_portion, 2),
            'line_10_long_term_60_pct': round(long_term_portion, 2),

            # Loss carryback/carryover
            'net_loss_available': round(net_loss_for_carryback, 2),
            'elect_carryback': self.elect_loss_carryback,
        }

    def calculate_part_ii(self) -> Dict[str, Any]:
        """
        Calculate Part II - Gains and Losses From Straddles.
        """
        total_gains = 0.0
        total_losses = 0.0
        total_unrecognized = 0.0

        straddle_details = []
        for straddle in self.straddles:
            net = straddle.gain_on_disposition - straddle.loss_on_disposition

            total_gains += straddle.gain_on_disposition
            total_losses += straddle.loss_on_disposition
            total_unrecognized += straddle.unrecognized_loss_current

            straddle_details.append({
                'description': straddle.description,
                'type': straddle.straddle_type.value,
                'gain': round(straddle.gain_on_disposition, 2),
                'loss': round(straddle.loss_on_disposition, 2),
                'unrecognized': round(straddle.unrecognized_loss_current, 2),
                'net': round(net, 2),
            })

        net_straddle_gain_loss = total_gains - total_losses

        return {
            'straddle_count': len(self.straddles),
            'straddles': straddle_details,
            'total_gains': round(total_gains, 2),
            'total_losses': round(total_losses, 2),
            'total_unrecognized_loss': round(total_unrecognized, 2),
            'net_straddle_gain_loss': round(net_straddle_gain_loss, 2),
        }

    def calculate_loss_carryback(self) -> Dict[str, float]:
        """
        Calculate Section 1256 loss carryback amounts.

        Net Section 1256 losses can be carried back 3 years
        to offset prior Section 1256 gains.
        """
        part_i = self.calculate_part_i()
        net_loss = part_i['net_loss_available']

        if not self.elect_loss_carryback or net_loss <= 0:
            return {
                'carryback_elected': False,
                'carryback_year_1': 0.0,
                'carryback_year_2': 0.0,
                'carryback_year_3': 0.0,
                'remaining_carryforward': net_loss,
            }

        # Calculate carryback (limited to amounts specified)
        total_carryback = self.carryback_year_1 + self.carryback_year_2 + self.carryback_year_3
        actual_carryback = min(total_carryback, net_loss)
        remaining = max(0, net_loss - actual_carryback)

        return {
            'carryback_elected': True,
            'carryback_year_1': min(self.carryback_year_1, net_loss),
            'carryback_year_2': min(self.carryback_year_2, max(0, net_loss - self.carryback_year_1)),
            'carryback_year_3': min(self.carryback_year_3, max(0, net_loss - self.carryback_year_1 - self.carryback_year_2)),
            'total_carryback': round(actual_carryback, 2),
            'remaining_carryforward': round(remaining, 2),
        }

    def calculate_form_6781(self) -> Dict[str, Any]:
        """
        Calculate complete Form 6781.
        """
        part_i = self.calculate_part_i()
        part_ii = self.calculate_part_ii()
        carryback = self.calculate_loss_carryback()

        # Combined totals for Schedule D
        short_term_total = part_i['line_9_short_term_40_pct']
        long_term_total = part_i['line_10_long_term_60_pct']

        # Add straddle amounts (treated as short-term unless identified)
        short_term_total += part_ii['net_straddle_gain_loss']

        return {
            'tax_year': self.tax_year,

            # Part I summary
            'section_1256_net': part_i['line_8_net_section_1256'],
            'section_1256_short_term': part_i['line_9_short_term_40_pct'],
            'section_1256_long_term': part_i['line_10_long_term_60_pct'],

            # Part II summary
            'straddle_net': part_ii['net_straddle_gain_loss'],

            # Schedule D flows
            'schedule_d_short_term': round(short_term_total, 2),
            'schedule_d_long_term': round(long_term_total, 2),

            # Carryback/carryforward
            'loss_carryback': carryback,
            'new_carryforward': carryback['remaining_carryforward'],

            # Detailed breakdowns
            'part_i': part_i,
            'part_ii': part_ii,
        }

    def get_form_6781_summary(self) -> Dict[str, float]:
        """Get a concise summary of Form 6781."""
        result = self.calculate_form_6781()
        return {
            'section_1256_net': result['section_1256_net'],
            'short_term_40_pct': result['section_1256_short_term'],
            'long_term_60_pct': result['section_1256_long_term'],
            'straddle_net': result['straddle_net'],
        }


def calculate_section_1256_gain_loss(
    futures_gain_loss: float = 0.0,
    options_gain_loss: float = 0.0,
    forex_gain_loss: float = 0.0,
    prior_year_unrealized: float = 0.0,
    current_year_unrealized: float = 0.0,
    prior_year_loss_carryover: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to calculate Form 6781 Section 1256 contracts.

    Args:
        futures_gain_loss: Realized gain/loss from regulated futures
        options_gain_loss: Realized gain/loss from nonequity options
        forex_gain_loss: Realized gain/loss from foreign currency contracts
        prior_year_unrealized: Unrealized gain/loss at prior year end
        current_year_unrealized: Unrealized gain/loss at current year end
        prior_year_loss_carryover: Loss carryover from prior year

    Returns:
        Dictionary with Form 6781 calculation results
    """
    contracts = []

    if futures_gain_loss != 0:
        contracts.append(Section1256Contract(
            description="Regulated Futures Contracts",
            contract_type=ContractType.REGULATED_FUTURES,
            proceeds=max(0, futures_gain_loss),
            cost_basis=max(0, -futures_gain_loss),
        ))

    if options_gain_loss != 0:
        contracts.append(Section1256Contract(
            description="Nonequity Options",
            contract_type=ContractType.NONEQUITY_OPTIONS,
            proceeds=max(0, options_gain_loss),
            cost_basis=max(0, -options_gain_loss),
        ))

    if forex_gain_loss != 0:
        contracts.append(Section1256Contract(
            description="Foreign Currency Contracts",
            contract_type=ContractType.FOREIGN_CURRENCY,
            proceeds=max(0, forex_gain_loss),
            cost_basis=max(0, -forex_gain_loss),
        ))

    # Add unrealized adjustment to first contract or create new one
    if contracts:
        contracts[0].prior_year_unrealized = prior_year_unrealized
        contracts[0].current_year_unrealized = current_year_unrealized
    elif prior_year_unrealized != 0 or current_year_unrealized != 0:
        contracts.append(Section1256Contract(
            description="Open Positions (Mark-to-Market)",
            prior_year_unrealized=prior_year_unrealized,
            current_year_unrealized=current_year_unrealized,
        ))

    form = Form6781(
        section_1256_contracts=contracts,
        prior_year_loss_carryover=prior_year_loss_carryover,
    )

    return form.calculate_form_6781()
