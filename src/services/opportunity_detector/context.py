"""
DetectionContext — holds all per-call pre-computed engine results.

Built once at the start of detect_opportunities(); passed through the
call stack instead of using module-level mutable dicts. This makes
the system safe under concurrent async requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from calculator.engine import CalculationBreakdown
    from calculator.state.state_tax_engine import StateCalculationBreakdown


@dataclass
class DetectionContext:
    """
    Immutable snapshot of the engine results for one detect_opportunities() call.

    Fields:
        breakdown        Federal tax engine result (None if engine failed)
        state_breakdown  State tax engine result (None if no state or failed)
        marginal_rate    Federal marginal rate as a Decimal fraction (e.g. 0.24)
        agi              Adjusted gross income from the engine (or profile estimate)
        taxable_income   Taxable income from the engine (or 0)
        total_tax        Total federal tax liability (or 0)
        effective_rate   Effective federal rate as a Decimal fraction
        niit             Net Investment Income Tax amount
        amt              Alternative Minimum Tax amount
    """

    breakdown: Optional[Any] = None           # CalculationBreakdown | None
    state_breakdown: Optional[Any] = None     # StateCalculationBreakdown | None

    marginal_rate: Decimal = Decimal("0.22")
    agi: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")
    effective_rate: Decimal = Decimal("0")
    niit: Decimal = Decimal("0")
    amt: Decimal = Decimal("0")

    @classmethod
    def build(
        cls,
        breakdown: Optional[Any],
        state_breakdown: Optional[Any],
        agi_estimate: Decimal,
    ) -> "DetectionContext":
        """
        Construct a DetectionContext from engine results.

        Falls back to agi_estimate and a default 22% rate when breakdown is None.
        """
        if breakdown is None:
            return cls(
                breakdown=None,
                state_breakdown=state_breakdown,
                agi=agi_estimate,
            )

        try:
            marginal = Decimal("0.22")
            if breakdown.taxable_income > 0:
                raw = Decimal(str(round(breakdown.marginal_tax_rate / 100, 4)))
                if raw > Decimal("0.01"):
                    marginal = raw

            return cls(
                breakdown=breakdown,
                state_breakdown=state_breakdown,
                marginal_rate=marginal,
                agi=Decimal(str(round(breakdown.agi, 2))),
                taxable_income=Decimal(str(round(breakdown.taxable_income, 2))),
                total_tax=Decimal(str(round(breakdown.total_tax, 2))),
                effective_rate=Decimal(str(round(breakdown.effective_tax_rate / 100, 4))),
                niit=Decimal(str(round(
                    getattr(breakdown, "net_investment_income_tax", 0) or 0, 2
                ))),
                amt=Decimal(str(round(
                    getattr(breakdown, "alternative_minimum_tax", 0) or 0, 2
                ))),
            )
        except Exception as exc:
            logger.warning("DetectionContext.build failed to parse breakdown: %s", exc)
            return cls(breakdown=breakdown, state_breakdown=state_breakdown, agi=agi_estimate)
