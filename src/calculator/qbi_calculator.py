"""
QBI (Qualified Business Income) Deduction Calculator - Section 199A

Implements the 20% pass-through deduction for qualified business income
from sole proprietorships, partnerships, S corporations, and some trusts/estates.

Tax Year 2025 implementation per IRS Rev. Proc. 2024-40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from decimal import Decimal

# Import Decimal math utilities for precision
from calculator.decimal_math import (
    add, subtract, multiply, divide, min_decimal, max_decimal, money, to_decimal, to_float
)

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.tax_year_config import TaxYearConfig


@dataclass
class QBIBreakdown:
    """Detailed breakdown of QBI deduction calculation."""

    # QBI components
    total_qbi: Decimal = Decimal("0")
    qbi_from_self_employment: Decimal = Decimal("0")
    qbi_from_k1: Decimal = Decimal("0")

    # Limitation factors
    w2_wages_total: Decimal = Decimal("0")
    ubia_total: Decimal = Decimal("0")
    has_sstb: bool = False

    # Threshold analysis
    taxable_income_before_qbi: Decimal = Decimal("0")
    threshold_start: Decimal = Decimal("0")
    threshold_end: Decimal = Decimal("0")
    is_below_threshold: bool = True
    is_above_threshold: bool = False
    phase_in_ratio: Decimal = Decimal("0")  # 0.0 = below threshold, 1.0 = above threshold

    # Limitation calculations
    sstb_applicable_percentage: Decimal = Decimal("1")  # 1.0 = full QBI, 0.0 = no QBI for SSTB
    wage_limit_50_pct: Decimal = Decimal("0")  # 50% of W-2 wages
    wage_limit_25_2_5_pct: Decimal = Decimal("0")  # 25% of W-2 wages + 2.5% of UBIA
    wage_limitation: Decimal = Decimal("0")  # Greater of the two wage limits
    wage_limitation_applies: bool = False

    # Deduction calculation
    tentative_qbi_deduction: Decimal = Decimal("0")  # 20% of QBI (before limits)
    qbi_after_wage_limit: Decimal = Decimal("0")  # After applying wage limitation
    taxable_income_limit: Decimal = Decimal("0")  # 20% of (taxable income - net capital gain)
    final_qbi_deduction: Decimal = Decimal("0")  # Final deduction amount


class QBICalculator:
    """
    Calculator for Section 199A Qualified Business Income deduction.

    The QBI deduction allows eligible taxpayers to deduct up to 20% of their
    qualified business income from pass-through entities, subject to limitations
    based on taxable income, W-2 wages, and UBIA of qualified property.
    """

    def calculate(
        self,
        tax_return: "TaxReturn",
        taxable_income_before_qbi: float,
        net_capital_gain: float,
        filing_status: str,
        config: "TaxYearConfig",
    ) -> QBIBreakdown:
        """
        Calculate the QBI deduction per Section 199A.

        Args:
            tax_return: The tax return containing income information
            taxable_income_before_qbi: Taxable income before QBI deduction
            net_capital_gain: Net capital gain (LTCG + qualified dividends)
            filing_status: Filing status for threshold lookup
            config: Tax year configuration with thresholds

        Returns:
            QBIBreakdown with detailed calculation breakdown
        """
        breakdown = QBIBreakdown()
        breakdown.taxable_income_before_qbi = taxable_income_before_qbi

        # Step 1: Calculate total QBI from all sources
        income = tax_return.income

        # Self-employment QBI (Schedule C net profit)
        se_income = to_decimal(income.self_employment_income)
        se_expenses = to_decimal(income.self_employment_expenses)
        se_net = subtract(se_income, se_expenses)
        if se_net > 0:
            breakdown.qbi_from_self_employment = se_net

        # K-1 QBI
        breakdown.qbi_from_k1 = to_decimal(income.get_k1_qbi_income())

        # Total QBI
        breakdown.total_qbi = add(breakdown.qbi_from_self_employment, breakdown.qbi_from_k1)

        # If no QBI, return early
        if breakdown.total_qbi <= 0:
            return breakdown

        # Step 2: Get W-2 wages and UBIA for limitations
        breakdown.w2_wages_total = to_decimal(income.get_qbi_w2_wages())
        breakdown.ubia_total = to_decimal(income.get_qbi_ubia())
        breakdown.has_sstb = income.has_sstb_income()

        # Step 3: Get thresholds for filing status
        breakdown.threshold_start = to_decimal(self._get_threshold_start(filing_status, config))
        breakdown.threshold_end = to_decimal(self._get_threshold_end(filing_status, config))

        # Step 4: Determine threshold position
        taxable_income_decimal = to_decimal(taxable_income_before_qbi)
        breakdown.taxable_income_before_qbi = taxable_income_decimal
        breakdown.is_below_threshold = taxable_income_decimal <= breakdown.threshold_start
        breakdown.is_above_threshold = taxable_income_decimal >= breakdown.threshold_end

        if breakdown.is_below_threshold:
            breakdown.phase_in_ratio = Decimal("0")
        elif breakdown.is_above_threshold:
            breakdown.phase_in_ratio = Decimal("1")
        else:
            # Phase-in calculation - CRITICAL: Use Decimal division for precision
            phase_range = subtract(breakdown.threshold_end, breakdown.threshold_start)
            excess = subtract(taxable_income_decimal, breakdown.threshold_start)
            breakdown.phase_in_ratio = divide(excess, phase_range) if phase_range > 0 else Decimal("1")

        # Step 5: Calculate tentative QBI deduction (20% of QBI)
        qbi_rate = to_decimal(config.qbi_deduction_rate)
        breakdown.tentative_qbi_deduction = multiply(breakdown.total_qbi, qbi_rate)

        # Step 6: Apply SSTB reduction if applicable
        if breakdown.has_sstb:
            breakdown.sstb_applicable_percentage = self._calculate_sstb_percentage(
                breakdown.phase_in_ratio
            )
            # Reduce QBI for SSTB businesses
            effective_qbi = multiply(breakdown.total_qbi, breakdown.sstb_applicable_percentage)
        else:
            breakdown.sstb_applicable_percentage = Decimal("1")
            effective_qbi = breakdown.total_qbi

        # Step 7: Calculate wage limitations - CRITICAL: Use Decimal for precision
        breakdown.wage_limit_50_pct = multiply(breakdown.w2_wages_total, Decimal("0.50"))
        wage_25_pct = multiply(breakdown.w2_wages_total, Decimal("0.25"))
        ubia_2_5_pct = multiply(breakdown.ubia_total, Decimal("0.025"))
        breakdown.wage_limit_25_2_5_pct = add(wage_25_pct, ubia_2_5_pct)
        breakdown.wage_limitation = max_decimal(
            breakdown.wage_limit_50_pct, breakdown.wage_limit_25_2_5_pct
        )

        # Step 8: Apply wage limitation if above threshold
        qbi_rate = to_decimal(config.qbi_deduction_rate)

        if breakdown.is_below_threshold:
            # No limitation - full 20% deduction
            breakdown.wage_limitation_applies = False
            breakdown.qbi_after_wage_limit = multiply(effective_qbi, qbi_rate)
        elif breakdown.is_above_threshold:
            # Full wage limitation applies
            breakdown.wage_limitation_applies = True
            # Deduction is lesser of 20% of QBI or wage limitation
            tentative = multiply(effective_qbi, qbi_rate)
            breakdown.qbi_after_wage_limit = min_decimal(tentative, breakdown.wage_limitation)
        else:
            # Phase-in: partially apply wage limitation
            breakdown.wage_limitation_applies = True
            tentative = multiply(effective_qbi, qbi_rate)

            # Calculate the reduction due to wage limitation
            if tentative > breakdown.wage_limitation:
                reduction = subtract(tentative, breakdown.wage_limitation)
                # Apply reduction proportionally based on phase-in ratio
                phased_reduction = multiply(reduction, breakdown.phase_in_ratio)
                breakdown.qbi_after_wage_limit = subtract(tentative, phased_reduction)
            else:
                breakdown.qbi_after_wage_limit = tentative

        # Step 9: Calculate taxable income limitation
        # QBI deduction cannot exceed 20% of (taxable income - net capital gain)
        net_cap_gain = to_decimal(net_capital_gain)
        ti_minus_gain = subtract(taxable_income_decimal, net_cap_gain)
        taxable_income_for_limit = max_decimal(Decimal("0"), ti_minus_gain)
        breakdown.taxable_income_limit = multiply(taxable_income_for_limit, qbi_rate)

        # Step 10: Final QBI deduction is lesser of wage-limited amount and TI limit
        breakdown.final_qbi_deduction = min_decimal(
            breakdown.qbi_after_wage_limit, breakdown.taxable_income_limit
        )

        # Ensure non-negative and round to cents for final result
        breakdown.final_qbi_deduction = money(max_decimal(Decimal("0"), breakdown.final_qbi_deduction))

        return breakdown

    def _get_threshold_start(self, filing_status: str, config: "TaxYearConfig") -> float:
        """Get the QBI threshold start for the given filing status."""
        if config.qbi_threshold_start is None:
            # Default fallback values for 2025
            defaults = {
                "single": 197300.0,
                "married_joint": 394600.0,
                "married_separate": 197300.0,
                "head_of_household": 197300.0,
                "qualifying_widow": 394600.0,
            }
            return defaults.get(filing_status, 197300.0)
        return config.qbi_threshold_start.get(filing_status, 197300.0)

    def _get_threshold_end(self, filing_status: str, config: "TaxYearConfig") -> float:
        """Get the QBI threshold end for the given filing status."""
        if config.qbi_threshold_end is None:
            # Default fallback values for 2025 (+$50K for single, +$100K for MFJ)
            defaults = {
                "single": 247300.0,
                "married_joint": 494600.0,
                "married_separate": 247300.0,
                "head_of_household": 247300.0,
                "qualifying_widow": 494600.0,
            }
            return defaults.get(filing_status, 247300.0)
        return config.qbi_threshold_end.get(filing_status, 247300.0)

    def _calculate_sstb_percentage(self, phase_in_ratio: Decimal) -> Decimal:
        """
        Calculate the applicable percentage for SSTB income.

        For SSTBs, the QBI deduction phases out completely as income
        increases through the threshold range.

        Args:
            phase_in_ratio: 0.0 (at threshold start) to 1.0 (at threshold end)

        Returns:
            Applicable percentage: 1.0 (full deduction) to 0.0 (no deduction)
        """
        # SSTB applicable percentage decreases linearly from 100% to 0%
        # as income increases from threshold_start to threshold_end
        result = subtract(Decimal("1"), phase_in_ratio)
        return max_decimal(Decimal("0"), result)
