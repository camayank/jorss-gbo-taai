"""
Decimal utilities for model-layer monetary rounding.

This module provides the same money() and to_decimal() functions as
calculator.decimal_math, but lives in models/ to avoid circular imports
(models -> calculator -> models).

Uses only stdlib 'decimal' - no dependencies on calculator package.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

Numeric = Union[int, float, str, Decimal]

MONEY_PLACES = Decimal("0.01")


def to_decimal(value: Numeric) -> Decimal:
    """Convert a numeric value to Decimal."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def money(value: Numeric) -> Decimal:
    """Round value to pennies using ROUND_HALF_UP (IRS standard)."""
    return to_decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
