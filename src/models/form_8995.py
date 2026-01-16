"""
Form 8995 - Qualified Business Income Deduction Simplified Computation

IRS Form for calculating the Section 199A QBI deduction for taxpayers
with taxable income at or below threshold amounts.

Form 8995 (Simplified):
- Used when taxable income <= $182,100 (single) or $364,200 (MFJ) for 2024
- No W-2 wage or UBIA limitations apply
- No SSTB limitations apply

Form 8995-A (Standard):
- Used when taxable income > threshold
- Requires W-2 wage and UBIA calculations
- SSTB income may be limited or excluded

Key Rules:
- QBI deduction = 20% of qualified business income
- Limited to lesser of 20% QBI or 20% of taxable income minus net capital gain
- Multiple businesses aggregated
- Losses carry forward
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BusinessType(str, Enum):
    """Type of qualified business."""
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    PARTNERSHIP = "partnership"
    S_CORPORATION = "s_corporation"
    REIT = "reit"
    PTP = "ptp"  # Publicly Traded Partnership


class SSTBCategory(str, Enum):
    """Specified Service Trade or Business categories."""
    NOT_SSTB = "not_sstb"
    HEALTH = "health"
    LAW = "law"
    ACCOUNTING = "accounting"
    ACTUARIAL = "actuarial"
    PERFORMING_ARTS = "performing_arts"
    CONSULTING = "consulting"
    ATHLETICS = "athletics"
    FINANCIAL_SERVICES = "financial_services"
    BROKERAGE = "brokerage"
    INVESTING = "investing"
    REPUTATION_SKILL = "reputation_skill"


class QualifiedBusiness(BaseModel):
    """Information about a qualified trade or business."""
    business_name: str = Field(description="Name of the business")
    business_type: BusinessType = Field(
        default=BusinessType.SOLE_PROPRIETORSHIP,
        description="Type of business entity"
    )
    ein: str = Field(default="", description="Business EIN")

    # QBI Components
    qualified_business_income: float = Field(
        default=0.0,
        description="Qualified business income (can be negative)"
    )
    w2_wages: float = Field(
        default=0.0, ge=0,
        description="W-2 wages paid by the business"
    )
    ubia: float = Field(
        default=0.0, ge=0,
        description="Unadjusted basis immediately after acquisition of qualified property"
    )

    # SSTB Classification
    is_sstb: bool = Field(
        default=False,
        description="Is a Specified Service Trade or Business"
    )
    sstb_category: SSTBCategory = Field(
        default=SSTBCategory.NOT_SSTB,
        description="SSTB category if applicable"
    )

    # REIT/PTP dividends
    reit_dividends: float = Field(
        default=0.0, ge=0,
        description="Qualified REIT dividends"
    )
    ptp_income: float = Field(
        default=0.0,
        description="Qualified PTP income (can be negative)"
    )


class Form8995(BaseModel):
    """
    Form 8995 - Qualified Business Income Deduction (Simplified)

    Used for taxpayers with taxable income at or below threshold.
    For income above threshold, use Form8995A model.
    """
    tax_year: int = Field(default=2025, description="Tax year")
    filing_status: str = Field(default="single", description="Filing status")

    # Businesses
    businesses: List[QualifiedBusiness] = Field(
        default_factory=list,
        description="List of qualified businesses"
    )

    # Prior year loss carryforward
    prior_year_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="QBI loss carryforward from prior year"
    )

    # Taxable income (for limitation calculation)
    taxable_income_before_qbi: float = Field(
        default=0.0, ge=0,
        description="Taxable income before QBI deduction"
    )
    net_capital_gain: float = Field(
        default=0.0, ge=0,
        description="Net capital gain (including qualified dividends)"
    )

    # 2025 Thresholds
    THRESHOLD_SINGLE: float = 197300.0
    THRESHOLD_MFJ: float = 394600.0
    PHASE_IN_SINGLE: float = 50000.0
    PHASE_IN_MFJ: float = 100000.0

    def get_threshold(self) -> float:
        """Get the QBI threshold based on filing status."""
        if self.filing_status in ["married_joint", "qualifying_widow"]:
            return self.THRESHOLD_MFJ
        return self.THRESHOLD_SINGLE

    def get_phase_in_range(self) -> float:
        """Get the phase-in range based on filing status."""
        if self.filing_status in ["married_joint", "qualifying_widow"]:
            return self.PHASE_IN_MFJ
        return self.PHASE_IN_SINGLE

    def is_below_threshold(self) -> bool:
        """Check if taxable income is below threshold (can use simplified form)."""
        return self.taxable_income_before_qbi <= self.get_threshold()

    def calculate_total_qbi(self) -> Dict[str, float]:
        """
        Calculate total QBI from all businesses.

        Returns breakdown by business and totals.
        """
        total_qbi = 0.0
        total_reit = 0.0
        total_ptp = 0.0
        total_w2_wages = 0.0
        total_ubia = 0.0

        business_details = []
        for biz in self.businesses:
            total_qbi += biz.qualified_business_income
            total_reit += biz.reit_dividends
            total_ptp += biz.ptp_income
            total_w2_wages += biz.w2_wages
            total_ubia += biz.ubia

            business_details.append({
                'name': biz.business_name,
                'type': biz.business_type.value,
                'qbi': biz.qualified_business_income,
                'is_sstb': biz.is_sstb,
                'w2_wages': biz.w2_wages,
                'ubia': biz.ubia,
            })

        # Apply prior year loss carryforward
        net_qbi = total_qbi - self.prior_year_loss_carryforward

        return {
            'business_count': len(self.businesses),
            'businesses': business_details,
            'total_qbi_before_carryforward': round(total_qbi, 2),
            'prior_year_carryforward': self.prior_year_loss_carryforward,
            'net_qbi': round(net_qbi, 2),
            'total_reit_dividends': round(total_reit, 2),
            'total_ptp_income': round(total_ptp, 2),
            'total_w2_wages': round(total_w2_wages, 2),
            'total_ubia': round(total_ubia, 2),
        }

    def calculate_simplified_deduction(self) -> Dict[str, Any]:
        """
        Calculate QBI deduction using simplified method (Form 8995).

        Used when taxable income is at or below threshold.
        No W-2 wage or UBIA limitations apply.
        """
        qbi_totals = self.calculate_total_qbi()

        # Line 1: Total QBI component
        net_qbi = qbi_totals['net_qbi']

        # Line 2: 20% of QBI
        qbi_component = max(0, net_qbi) * 0.20

        # Line 3: REIT/PTP component
        reit_ptp = qbi_totals['total_reit_dividends'] + qbi_totals['total_ptp_income']
        reit_ptp_component = max(0, reit_ptp) * 0.20

        # Line 4: Total QBI deduction before income limitation
        total_before_limit = qbi_component + reit_ptp_component

        # Line 5: Taxable income limitation
        # Deduction limited to 20% of (taxable income - net capital gain)
        income_limit_base = max(0, self.taxable_income_before_qbi - self.net_capital_gain)
        income_limitation = income_limit_base * 0.20

        # Line 6: QBI deduction (lesser of Line 4 or Line 5)
        qbi_deduction = min(total_before_limit, income_limitation)

        # Calculate new loss carryforward if QBI is negative
        new_carryforward = 0.0
        if net_qbi < 0:
            new_carryforward = abs(net_qbi)

        return {
            'form_type': '8995',  # Simplified
            'below_threshold': True,

            # Line items
            'line_1_total_qbi': round(net_qbi, 2),
            'line_2_qbi_component': round(qbi_component, 2),
            'line_3_reit_ptp_component': round(reit_ptp_component, 2),
            'line_4_total_before_limit': round(total_before_limit, 2),
            'line_5_income_limitation': round(income_limitation, 2),
            'line_6_qbi_deduction': round(qbi_deduction, 2),

            # Summary
            'qbi_deduction': round(qbi_deduction, 2),
            'new_loss_carryforward': round(new_carryforward, 2),

            # Supporting details
            'qbi_totals': qbi_totals,
        }

    def calculate_standard_deduction(self) -> Dict[str, Any]:
        """
        Calculate QBI deduction using standard method (Form 8995-A).

        Used when taxable income is above threshold.
        W-2 wage and UBIA limitations may apply.
        SSTB income may be limited.
        """
        qbi_totals = self.calculate_total_qbi()
        threshold = self.get_threshold()
        phase_in = self.get_phase_in_range()

        # Calculate phase-in percentage for SSTB
        excess_over_threshold = max(0, self.taxable_income_before_qbi - threshold)

        if excess_over_threshold >= phase_in:
            # Fully phased out - SSTB gets nothing
            sstb_applicable_pct = 0.0
            wage_ubia_applicable_pct = 1.0
        else:
            # Partially phased in
            phase_in_ratio = excess_over_threshold / phase_in
            sstb_applicable_pct = 1.0 - phase_in_ratio
            wage_ubia_applicable_pct = phase_in_ratio

        # Calculate QBI component for each business
        total_qbi_component = 0.0
        business_calcs = []

        for biz in self.businesses:
            qbi = biz.qualified_business_income

            # For SSTB, apply phase-in reduction
            if biz.is_sstb:
                applicable_qbi = qbi * sstb_applicable_pct
                applicable_w2 = biz.w2_wages * sstb_applicable_pct
                applicable_ubia = biz.ubia * sstb_applicable_pct
            else:
                applicable_qbi = qbi
                applicable_w2 = biz.w2_wages
                applicable_ubia = biz.ubia

            if applicable_qbi <= 0:
                biz_component = 0.0
            else:
                # 20% of QBI
                qbi_20_pct = applicable_qbi * 0.20

                # W-2 wage limitation (greater of):
                # - 50% of W-2 wages, OR
                # - 25% of W-2 wages + 2.5% of UBIA
                wage_limit_1 = applicable_w2 * 0.50
                wage_limit_2 = (applicable_w2 * 0.25) + (applicable_ubia * 0.025)
                wage_ubia_limit = max(wage_limit_1, wage_limit_2)

                # Apply wage/UBIA limitation with phase-in
                if wage_ubia_applicable_pct >= 1.0:
                    # Fully phased in - use full limitation
                    biz_component = min(qbi_20_pct, wage_ubia_limit)
                else:
                    # Partially phased in - blend
                    limited_amount = min(qbi_20_pct, wage_ubia_limit)
                    reduction = (qbi_20_pct - limited_amount) * wage_ubia_applicable_pct
                    biz_component = qbi_20_pct - reduction

            total_qbi_component += biz_component

            business_calcs.append({
                'name': biz.business_name,
                'original_qbi': qbi,
                'applicable_qbi': round(applicable_qbi, 2),
                'is_sstb': biz.is_sstb,
                'component': round(biz_component, 2),
            })

        # Apply prior year carryforward
        total_qbi_component = max(0, total_qbi_component - self.prior_year_loss_carryforward * 0.20)

        # REIT/PTP component (no W-2/UBIA limitation)
        reit_ptp = qbi_totals['total_reit_dividends'] + qbi_totals['total_ptp_income']
        reit_ptp_component = max(0, reit_ptp) * 0.20

        # Total before income limitation
        total_before_limit = total_qbi_component + reit_ptp_component

        # Income limitation
        income_limit_base = max(0, self.taxable_income_before_qbi - self.net_capital_gain)
        income_limitation = income_limit_base * 0.20

        # Final deduction
        qbi_deduction = min(total_before_limit, income_limitation)

        # New carryforward
        net_qbi = qbi_totals['net_qbi']
        new_carryforward = abs(net_qbi) if net_qbi < 0 else 0.0

        return {
            'form_type': '8995-A',  # Standard
            'below_threshold': False,

            # Phase-in information
            'threshold': threshold,
            'phase_in_range': phase_in,
            'excess_over_threshold': round(excess_over_threshold, 2),
            'sstb_applicable_pct': round(sstb_applicable_pct * 100, 1),
            'wage_ubia_applicable_pct': round(wage_ubia_applicable_pct * 100, 1),

            # Components
            'qbi_component': round(total_qbi_component, 2),
            'reit_ptp_component': round(reit_ptp_component, 2),
            'total_before_limit': round(total_before_limit, 2),
            'income_limitation': round(income_limitation, 2),
            'qbi_deduction': round(qbi_deduction, 2),

            # Carryforward
            'new_loss_carryforward': round(new_carryforward, 2),

            # Business details
            'business_calculations': business_calcs,
            'qbi_totals': qbi_totals,
        }

    def calculate_form_8995(self) -> Dict[str, Any]:
        """
        Calculate Form 8995 QBI deduction.

        Automatically determines whether to use simplified or standard method.
        """
        if self.is_below_threshold():
            return self.calculate_simplified_deduction()
        else:
            return self.calculate_standard_deduction()

    def get_form_8995_summary(self) -> Dict[str, float]:
        """Get a concise summary of Form 8995."""
        result = self.calculate_form_8995()
        return {
            'qbi_deduction': result['qbi_deduction'],
            'below_threshold': result['below_threshold'],
            'new_carryforward': result['new_loss_carryforward'],
        }


def calculate_qbi_deduction(
    qualified_business_income: float,
    taxable_income: float,
    filing_status: str = "single",
    net_capital_gain: float = 0.0,
    w2_wages: float = 0.0,
    ubia: float = 0.0,
    is_sstb: bool = False,
    reit_dividends: float = 0.0,
    ptp_income: float = 0.0,
    prior_year_carryforward: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to calculate QBI deduction.

    Args:
        qualified_business_income: QBI from all businesses
        taxable_income: Taxable income before QBI deduction
        filing_status: Filing status
        net_capital_gain: Net capital gain including qualified dividends
        w2_wages: Total W-2 wages paid by businesses
        ubia: Total UBIA of qualified property
        is_sstb: Whether business is a specified service trade or business
        reit_dividends: Qualified REIT dividends
        ptp_income: Qualified PTP income
        prior_year_carryforward: QBI loss carryforward from prior year

    Returns:
        Dictionary with Form 8995 calculation results
    """
    business = QualifiedBusiness(
        business_name="Combined Business",
        qualified_business_income=qualified_business_income,
        w2_wages=w2_wages,
        ubia=ubia,
        is_sstb=is_sstb,
        reit_dividends=reit_dividends,
        ptp_income=ptp_income,
    )

    form = Form8995(
        filing_status=filing_status,
        businesses=[business],
        taxable_income_before_qbi=taxable_income,
        net_capital_gain=net_capital_gain,
        prior_year_loss_carryforward=prior_year_carryforward,
    )

    return form.calculate_form_8995()
