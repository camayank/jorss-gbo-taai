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
class QBIBusinessDetail:
    """Per-business QBI breakdown for W-2 wage limitation per IRC §199A(b)(2)(B)."""

    business_name: str = ""
    business_type: str = "sole_proprietorship"  # sole_proprietorship, partnership, s_corporation
    ein: str = ""

    # QBI components
    qualified_business_income: Decimal = Decimal("0")

    # W-2 wage limitation inputs
    w2_wages: Decimal = Decimal("0")
    ubia: Decimal = Decimal("0")
    is_sstb: bool = False

    # Calculated limitation values
    wage_limit_50_pct: Decimal = Decimal("0")  # 50% of W-2 wages
    wage_limit_25_2_5_pct: Decimal = Decimal("0")  # 25% of W-2 wages + 2.5% of UBIA
    wage_limitation: Decimal = Decimal("0")  # Greater of the two

    # Deduction calculation
    tentative_deduction: Decimal = Decimal("0")  # 20% of QBI
    limited_deduction: Decimal = Decimal("0")  # After applying wage limitation


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

    # Per-business breakdown for IRC §199A(b)(2)(B) compliance
    business_details: list[QBIBusinessDetail] = field(default_factory=list)


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

        Per IRC §199A(b)(2)(B), the W-2 wage limitation is applied
        per qualified trade or business, not in aggregate.
        """
        breakdown = QBIBreakdown()
        breakdown.taxable_income_before_qbi = to_decimal(taxable_income_before_qbi)

        income = tax_return.income
        qbi_rate = to_decimal(config.qbi_deduction_rate)

        # Step 1: Get thresholds for filing status
        breakdown.threshold_start = to_decimal(self._get_threshold_start(filing_status, config))
        breakdown.threshold_end = to_decimal(self._get_threshold_end(filing_status, config))

        # Step 2: Determine threshold position
        taxable_income_decimal = to_decimal(taxable_income_before_qbi)
        breakdown.is_below_threshold = taxable_income_decimal <= breakdown.threshold_start
        breakdown.is_above_threshold = taxable_income_decimal >= breakdown.threshold_end

        if breakdown.is_below_threshold:
            breakdown.phase_in_ratio = Decimal("0")
        elif breakdown.is_above_threshold:
            breakdown.phase_in_ratio = Decimal("1")
        else:
            phase_range = subtract(breakdown.threshold_end, breakdown.threshold_start)
            excess = subtract(taxable_income_decimal, breakdown.threshold_start)
            breakdown.phase_in_ratio = divide(excess, phase_range) if phase_range > 0 else Decimal("1")

        # Step 3: Build per-business breakdown
        businesses: list[QBIBusinessDetail] = []

        # Self-employment (Schedule C) as one business
        se_income = to_decimal(income.self_employment_income)
        se_expenses = to_decimal(income.self_employment_expenses)
        se_net = subtract(se_income, se_expenses)
        if se_net > 0:
            breakdown.qbi_from_self_employment = se_net
            businesses.append(QBIBusinessDetail(
                business_name="Self-Employment (Schedule C)",
                business_type="sole_proprietorship",
                qualified_business_income=se_net,
                w2_wages=Decimal("0"),  # Sole props don't have W-2 wages
                ubia=Decimal("0"),
                is_sstb=False,
            ))

        # K-1 forms as separate businesses
        for k1 in income.schedule_k1_forms:
            qbi_income = to_decimal(k1.qbi_ordinary_income or 0)
            if qbi_income > 0:
                breakdown.qbi_from_k1 = add(breakdown.qbi_from_k1, qbi_income)
                businesses.append(QBIBusinessDetail(
                    business_name=k1.entity_name,
                    business_type=k1.k1_type.value if hasattr(k1.k1_type, 'value') else str(k1.k1_type),
                    ein=k1.entity_ein or "",
                    qualified_business_income=qbi_income,
                    w2_wages=to_decimal(k1.w2_wages_for_qbi or 0),
                    ubia=to_decimal(k1.ubia_for_qbi or 0),
                    is_sstb=k1.is_sstb,
                ))

        # Total QBI
        breakdown.total_qbi = add(breakdown.qbi_from_self_employment, breakdown.qbi_from_k1)
        breakdown.has_sstb = income.has_sstb_income()

        # If no QBI, return early
        if breakdown.total_qbi <= 0:
            breakdown.business_details = businesses
            return breakdown

        # Aggregate W-2 wages and UBIA for backward compatibility
        breakdown.w2_wages_total = sum((b.w2_wages for b in businesses), Decimal("0"))
        breakdown.ubia_total = sum((b.ubia for b in businesses), Decimal("0"))

        # Step 4: Apply per-business wage limitation
        total_limited_deduction = Decimal("0")

        for biz in businesses:
            # Calculate tentative 20% deduction
            biz.tentative_deduction = multiply(biz.qualified_business_income, qbi_rate)

            # Calculate wage limitations
            biz.wage_limit_50_pct = multiply(biz.w2_wages, Decimal("0.50"))
            wage_25_pct = multiply(biz.w2_wages, Decimal("0.25"))
            ubia_2_5_pct = multiply(biz.ubia, Decimal("0.025"))
            biz.wage_limit_25_2_5_pct = add(wage_25_pct, ubia_2_5_pct)
            biz.wage_limitation = max_decimal(biz.wage_limit_50_pct, biz.wage_limit_25_2_5_pct)

            # Apply SSTB reduction if applicable
            effective_qbi = biz.qualified_business_income
            if biz.is_sstb and not breakdown.is_below_threshold:
                sstb_pct = self._calculate_sstb_percentage(breakdown.phase_in_ratio)
                effective_qbi = multiply(effective_qbi, sstb_pct)
                biz.tentative_deduction = multiply(effective_qbi, qbi_rate)

            # Apply limitation based on threshold position
            if breakdown.is_below_threshold:
                # No limitation - full 20% deduction
                biz.limited_deduction = biz.tentative_deduction
            elif breakdown.is_above_threshold:
                # Full wage limitation applies
                biz.limited_deduction = min_decimal(biz.tentative_deduction, biz.wage_limitation)
            else:
                # Phase-in: partially apply wage limitation
                if biz.tentative_deduction > biz.wage_limitation:
                    reduction = subtract(biz.tentative_deduction, biz.wage_limitation)
                    phased_reduction = multiply(reduction, breakdown.phase_in_ratio)
                    biz.limited_deduction = subtract(biz.tentative_deduction, phased_reduction)
                else:
                    biz.limited_deduction = biz.tentative_deduction

            total_limited_deduction = add(total_limited_deduction, biz.limited_deduction)

        breakdown.business_details = businesses
        breakdown.qbi_after_wage_limit = total_limited_deduction
        breakdown.wage_limitation_applies = not breakdown.is_below_threshold

        # Calculate aggregate wage limits for backward compatibility
        breakdown.wage_limit_50_pct = multiply(breakdown.w2_wages_total, Decimal("0.50"))
        wage_25_pct = multiply(breakdown.w2_wages_total, Decimal("0.25"))
        ubia_2_5_pct = multiply(breakdown.ubia_total, Decimal("0.025"))
        breakdown.wage_limit_25_2_5_pct = add(wage_25_pct, ubia_2_5_pct)
        breakdown.wage_limitation = max_decimal(breakdown.wage_limit_50_pct, breakdown.wage_limit_25_2_5_pct)
        breakdown.tentative_qbi_deduction = multiply(breakdown.total_qbi, qbi_rate)

        # SSTB percentage for backward compatibility
        if breakdown.has_sstb:
            breakdown.sstb_applicable_percentage = self._calculate_sstb_percentage(breakdown.phase_in_ratio)
        else:
            breakdown.sstb_applicable_percentage = Decimal("1")

        # Step 5: Apply taxable income limitation
        net_cap_gain = to_decimal(net_capital_gain)
        ti_minus_gain = subtract(taxable_income_decimal, net_cap_gain)
        taxable_income_for_limit = max_decimal(Decimal("0"), ti_minus_gain)
        breakdown.taxable_income_limit = multiply(taxable_income_for_limit, qbi_rate)

        # Step 6: Final QBI deduction is lesser of per-business total and TI limit
        breakdown.final_qbi_deduction = min_decimal(
            total_limited_deduction, breakdown.taxable_income_limit
        )

        # Ensure non-negative and round to cents
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
