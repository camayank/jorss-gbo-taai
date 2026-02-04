"""
Schedule D (Form 1040) - Capital Gains and Losses

IRS Form for reporting:
- Short-term capital gains and losses (held 1 year or less)
- Long-term capital gains and losses (held more than 1 year)
- Capital loss carryovers from prior years
- Qualified dividends and capital gain tax computation

Key Rules:
- Net capital loss deduction limited to $3,000/year ($1,500 MFS)
- Excess losses carry forward indefinitely
- Long-term gains taxed at preferential rates (0%, 15%, 20%)
- Unrecaptured Section 1250 gain taxed at max 25%
- Collectibles gain taxed at max 28%
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class GainLossType(str, Enum):
    """Type of capital gain or loss."""
    SHORT_TERM = "short_term"  # Held 1 year or less
    LONG_TERM = "long_term"  # Held more than 1 year


class CapitalGainCategory(str, Enum):
    """Special categories of capital gains."""
    REGULAR = "regular"  # Regular capital gain
    SECTION_1250 = "section_1250"  # Unrecaptured Section 1250 gain (max 25%)
    COLLECTIBLES = "collectibles"  # Collectibles gain (max 28%)
    SECTION_1202 = "section_1202"  # Qualified small business stock (QSBS)


class Form8949Summary(BaseModel):
    """Summary of transactions from Form 8949."""
    box_code: str = Field(
        description="Box code (A-F) for 1099-B reporting"
    )
    proceeds: float = Field(default=0.0, description="Total proceeds")
    cost_basis: float = Field(default=0.0, description="Total cost basis")
    adjustments: float = Field(default=0.0, description="Total adjustments")
    gain_loss: float = Field(default=0.0, description="Net gain or loss")


class CapitalLossCarryover(BaseModel):
    """Capital loss carryover from prior years."""
    tax_year: int = Field(description="Year the loss originated")
    short_term_carryover: float = Field(
        default=0.0, ge=0,
        description="Short-term capital loss carryover"
    )
    long_term_carryover: float = Field(
        default=0.0, ge=0,
        description="Long-term capital loss carryover"
    )


class ScheduleD(BaseModel):
    """
    Schedule D (Form 1040) - Capital Gains and Losses

    Complete model for IRS Schedule D with Parts I, II, and III.
    Integrates with Form 8949 for detailed transaction reporting.
    """
    tax_year: int = Field(default=2025, description="Tax year")
    filing_status: str = Field(default="single", description="Filing status")

    # Part I: Short-Term Capital Gains and Losses
    # Line 1a-1b: Form 8949 Box A (basis reported, no adjustments)
    form_8949_box_a: Form8949Summary = Field(
        default_factory=lambda: Form8949Summary(box_code="A"),
        description="Form 8949 Box A totals"
    )
    # Line 2: Form 8949 Box B (basis reported, adjustments needed)
    form_8949_box_b: Form8949Summary = Field(
        default_factory=lambda: Form8949Summary(box_code="B"),
        description="Form 8949 Box B totals"
    )
    # Line 3: Form 8949 Box C (basis not reported)
    form_8949_box_c: Form8949Summary = Field(
        default_factory=lambda: Form8949Summary(box_code="C"),
        description="Form 8949 Box C totals"
    )
    # Line 4: Short-term gain from Form 6252 and like-kind exchanges
    st_gain_from_6252: float = Field(
        default=0.0,
        description="Short-term gain from installment sales (Form 6252)"
    )
    st_gain_from_like_kind: float = Field(
        default=0.0,
        description="Short-term gain from like-kind exchanges (Form 8824)"
    )
    # Line 5: Net short-term gain/loss from partnerships, S corps, etc.
    st_passthrough_gain: float = Field(
        default=0.0,
        description="Short-term gain/loss from partnerships, S corps, estates, trusts"
    )
    # Line 6: Short-term capital loss carryover
    st_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Short-term capital loss carryover from prior year"
    )

    # Part II: Long-Term Capital Gains and Losses
    # Line 8a-8b: Form 8949 Box D (basis reported, no adjustments)
    form_8949_box_d: Form8949Summary = Field(
        default_factory=lambda: Form8949Summary(box_code="D"),
        description="Form 8949 Box D totals"
    )
    # Line 9: Form 8949 Box E (basis reported, adjustments needed)
    form_8949_box_e: Form8949Summary = Field(
        default_factory=lambda: Form8949Summary(box_code="E"),
        description="Form 8949 Box E totals"
    )
    # Line 10: Form 8949 Box F (basis not reported)
    form_8949_box_f: Form8949Summary = Field(
        default_factory=lambda: Form8949Summary(box_code="F"),
        description="Form 8949 Box F totals"
    )
    # Line 11: Long-term gain from Form 6252, 4797, like-kind exchanges
    lt_gain_from_6252: float = Field(
        default=0.0,
        description="Long-term gain from installment sales (Form 6252)"
    )
    lt_gain_from_4797: float = Field(
        default=0.0,
        description="Long-term gain from Form 4797"
    )
    lt_gain_from_like_kind: float = Field(
        default=0.0,
        description="Long-term gain from like-kind exchanges (Form 8824)"
    )
    # Line 12: Net long-term gain/loss from partnerships, S corps, etc.
    lt_passthrough_gain: float = Field(
        default=0.0,
        description="Long-term gain/loss from partnerships, S corps, estates, trusts"
    )
    # Line 13: Capital gain distributions
    capital_gain_distributions: float = Field(
        default=0.0, ge=0,
        description="Capital gain distributions (from Form 1099-DIV Box 2a)"
    )
    # Line 14: Long-term capital loss carryover
    lt_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Long-term capital loss carryover from prior year"
    )

    # Special rate categories
    unrecaptured_1250_gain: float = Field(
        default=0.0, ge=0,
        description="Unrecaptured Section 1250 gain (max 25% rate)"
    )
    collectibles_28_gain: float = Field(
        default=0.0, ge=0,
        description="Collectibles gain (max 28% rate)"
    )
    section_1202_exclusion: float = Field(
        default=0.0, ge=0,
        description="Section 1202 exclusion (QSBS)"
    )

    # Qualified dividends (for tax computation)
    qualified_dividends: float = Field(
        default=0.0, ge=0,
        description="Qualified dividends (from Form 1040 Line 3a)"
    )

    # Configuration
    capital_loss_limit: float = Field(
        default=3000.0,
        description="Annual capital loss deduction limit"
    )

    def calculate_part_i_short_term(self) -> Dict[str, float]:
        """
        Calculate Part I - Short-Term Capital Gains and Losses.

        Returns net short-term gain or loss.
        """
        # Line 1b: Form 8949 Box A total
        line_1b = self.form_8949_box_a.gain_loss
        # Line 2: Form 8949 Box B total
        line_2 = self.form_8949_box_b.gain_loss
        # Line 3: Form 8949 Box C total
        line_3 = self.form_8949_box_c.gain_loss

        # Line 4: Other short-term gains
        line_4 = self.st_gain_from_6252 + self.st_gain_from_like_kind

        # Line 5: Pass-through short-term
        line_5 = self.st_passthrough_gain

        # Line 6: Short-term loss carryover (entered as negative)
        line_6 = -self.st_loss_carryover

        # Line 7: Net short-term gain or loss
        net_short_term = line_1b + line_2 + line_3 + line_4 + line_5 + line_6

        return {
            'line_1b_box_a': float(money(line_1b)),
            'line_2_box_b': float(money(line_2)),
            'line_3_box_c': float(money(line_3)),
            'line_4_other_st_gain': float(money(line_4)),
            'line_5_passthrough': float(money(line_5)),
            'line_6_st_carryover': float(money(line_6)),
            'line_7_net_short_term': float(money(net_short_term)),
        }

    def calculate_part_ii_long_term(self) -> Dict[str, float]:
        """
        Calculate Part II - Long-Term Capital Gains and Losses.

        Returns net long-term gain or loss.
        """
        # Line 8b: Form 8949 Box D total
        line_8b = self.form_8949_box_d.gain_loss
        # Line 9: Form 8949 Box E total
        line_9 = self.form_8949_box_e.gain_loss
        # Line 10: Form 8949 Box F total
        line_10 = self.form_8949_box_f.gain_loss

        # Line 11: Other long-term gains
        line_11 = (
            self.lt_gain_from_6252 +
            self.lt_gain_from_4797 +
            self.lt_gain_from_like_kind
        )

        # Line 12: Pass-through long-term
        line_12 = self.lt_passthrough_gain

        # Line 13: Capital gain distributions
        line_13 = self.capital_gain_distributions

        # Line 14: Long-term loss carryover (entered as negative)
        line_14 = -self.lt_loss_carryover

        # Line 15: Net long-term gain or loss
        net_long_term = (
            line_8b + line_9 + line_10 + line_11 +
            line_12 + line_13 + line_14
        )

        return {
            'line_8b_box_d': float(money(line_8b)),
            'line_9_box_e': float(money(line_9)),
            'line_10_box_f': float(money(line_10)),
            'line_11_other_lt_gain': float(money(line_11)),
            'line_12_passthrough': float(money(line_12)),
            'line_13_cap_gain_dist': float(money(line_13)),
            'line_14_lt_carryover': float(money(line_14)),
            'line_15_net_long_term': float(money(net_long_term)),
        }

    def calculate_part_iii_summary(self) -> Dict[str, Any]:
        """
        Calculate Part III - Summary and Tax Computation.

        Determines net capital gain/loss and capital loss deduction.
        """
        part_i = self.calculate_part_i_short_term()
        part_ii = self.calculate_part_ii_long_term()

        net_st = part_i['line_7_net_short_term']
        net_lt = part_ii['line_15_net_long_term']

        # Line 16: Combine net ST and LT
        line_16 = net_st + net_lt

        # Determine capital loss limit based on filing status
        loss_limit = 1500.0 if self.filing_status == "married_separate" else self.capital_loss_limit

        # Calculate amounts for different scenarios
        if line_16 >= 0:
            # Net capital gain
            capital_loss_deduction = 0.0
            net_capital_gain = line_16
            new_st_carryover = 0.0
            new_lt_carryover = 0.0
        else:
            # Net capital loss
            capital_loss_deduction = min(abs(line_16), loss_limit)
            net_capital_gain = 0.0

            # Calculate carryover
            excess_loss = abs(line_16) - capital_loss_deduction

            # Apply losses in order: ST first, then LT
            if net_st < 0 and net_lt < 0:
                # Both are losses - prorate
                total_loss = abs(net_st) + abs(net_lt)
                st_used = (abs(net_st) / total_loss) * capital_loss_deduction
                lt_used = capital_loss_deduction - st_used
                new_st_carryover = max(0, abs(net_st) - st_used)
                new_lt_carryover = max(0, abs(net_lt) - lt_used)
            elif net_st < 0:
                # Only ST is loss
                st_used = min(abs(net_st), capital_loss_deduction)
                new_st_carryover = max(0, abs(net_st) - st_used)
                # LT gain offsets some ST loss
                new_lt_carryover = 0.0
            else:
                # Only LT is loss
                lt_used = min(abs(net_lt), capital_loss_deduction)
                new_lt_carryover = max(0, abs(net_lt) - lt_used)
                # ST gain offsets some LT loss
                new_st_carryover = 0.0

        # Qualified dividends and net capital gain for tax computation
        # Line 21: Check if need to use Qualified Dividends worksheet
        has_preferential_income = (
            net_capital_gain > 0 or
            self.qualified_dividends > 0 or
            self.unrecaptured_1250_gain > 0 or
            self.collectibles_28_gain > 0
        )

        return {
            'line_16_combined': float(money(line_16)),
            'is_net_gain': line_16 >= 0,
            'is_net_loss': line_16 < 0,

            # Tax computation amounts
            'net_capital_gain': float(money(net_capital_gain)),
            'capital_loss_deduction': float(money(capital_loss_deduction)),
            'loss_limit': loss_limit,

            # Carryover to next year
            'new_st_carryover': float(money(new_st_carryover)),
            'new_lt_carryover': float(money(new_lt_carryover)),
            'total_new_carryover': float(money(new_st_carryover + new_lt_carryover)),

            # Special rate income
            'unrecaptured_1250_gain': self.unrecaptured_1250_gain,
            'collectibles_28_gain': self.collectibles_28_gain,
            'section_1202_exclusion': self.section_1202_exclusion,
            'qualified_dividends': self.qualified_dividends,

            # Line 21: Use QD/CG worksheet?
            'use_preferential_worksheet': has_preferential_income,
        }

    def calculate_schedule_d(self) -> Dict[str, Any]:
        """
        Calculate complete Schedule D with all parts.

        Returns comprehensive breakdown for Form 1040 and tax computation.
        """
        part_i = self.calculate_part_i_short_term()
        part_ii = self.calculate_part_ii_long_term()
        part_iii = self.calculate_part_iii_summary()

        return {
            'tax_year': self.tax_year,
            'filing_status': self.filing_status,

            # Part I summary
            'net_short_term_gain_loss': part_i['line_7_net_short_term'],

            # Part II summary
            'net_long_term_gain_loss': part_ii['line_15_net_long_term'],

            # Part III summary
            'net_capital_gain_loss': part_iii['line_16_combined'],
            'capital_loss_deduction': part_iii['capital_loss_deduction'],
            'net_capital_gain': part_iii['net_capital_gain'],

            # Carryforward
            'new_st_carryover': part_iii['new_st_carryover'],
            'new_lt_carryover': part_iii['new_lt_carryover'],

            # Form 1040 lines
            'form_1040_line_7': (
                part_iii['net_capital_gain'] if part_iii['is_net_gain']
                else -part_iii['capital_loss_deduction']
            ),

            # Tax computation
            'use_qualified_dividends_worksheet': part_iii['use_preferential_worksheet'],
            'preferential_income': float(money(
                part_iii['net_capital_gain'] + self.qualified_dividends
            )),

            # Detailed breakdowns
            'part_i': part_i,
            'part_ii': part_ii,
            'part_iii': part_iii,
        }

    def get_schedule_d_summary(self) -> Dict[str, float]:
        """Get a concise summary of Schedule D."""
        result = self.calculate_schedule_d()
        return {
            'net_short_term': result['net_short_term_gain_loss'],
            'net_long_term': result['net_long_term_gain_loss'],
            'net_capital_gain_loss': result['net_capital_gain_loss'],
            'capital_loss_deduction': result['capital_loss_deduction'],
            'new_carryover': result['new_st_carryover'] + result['new_lt_carryover'],
        }


def create_schedule_d(
    short_term_gain_loss: float = 0.0,
    long_term_gain_loss: float = 0.0,
    capital_gain_distributions: float = 0.0,
    st_loss_carryover: float = 0.0,
    lt_loss_carryover: float = 0.0,
    qualified_dividends: float = 0.0,
    filing_status: str = "single",
) -> Dict[str, Any]:
    """
    Convenience function to create and calculate Schedule D.

    Args:
        short_term_gain_loss: Net short-term gain (positive) or loss (negative)
        long_term_gain_loss: Net long-term gain (positive) or loss (negative)
        capital_gain_distributions: Capital gain distributions from 1099-DIV
        st_loss_carryover: Short-term loss carryover from prior year
        lt_loss_carryover: Long-term loss carryover from prior year
        qualified_dividends: Qualified dividends for tax computation
        filing_status: Filing status

    Returns:
        Dictionary with Schedule D calculation results
    """
    # Create Form 8949 summaries from gain/loss totals
    if short_term_gain_loss >= 0:
        box_a = Form8949Summary(box_code="A", gain_loss=short_term_gain_loss)
        box_b = Form8949Summary(box_code="B")
    else:
        box_a = Form8949Summary(box_code="A")
        box_b = Form8949Summary(box_code="B", gain_loss=short_term_gain_loss)

    if long_term_gain_loss >= 0:
        box_d = Form8949Summary(box_code="D", gain_loss=long_term_gain_loss)
        box_e = Form8949Summary(box_code="E")
    else:
        box_d = Form8949Summary(box_code="D")
        box_e = Form8949Summary(box_code="E", gain_loss=long_term_gain_loss)

    schedule_d = ScheduleD(
        filing_status=filing_status,
        form_8949_box_a=box_a,
        form_8949_box_b=box_b,
        form_8949_box_d=box_d,
        form_8949_box_e=box_e,
        capital_gain_distributions=capital_gain_distributions,
        st_loss_carryover=st_loss_carryover,
        lt_loss_carryover=lt_loss_carryover,
        qualified_dividends=qualified_dividends,
    )

    return schedule_d.calculate_schedule_d()
