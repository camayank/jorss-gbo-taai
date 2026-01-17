"""
Decimal Math Utilities for Tax Calculations.

Provides precise decimal arithmetic to avoid floating point errors
in tax calculations. All tax calculations should use these functions
instead of direct float arithmetic.

Prompt 2: Deterministic Calculation - Same inputs always produce same outputs.

Why Decimal?
- Float: 0.1 + 0.2 = 0.30000000000000004
- Decimal: 0.1 + 0.2 = 0.3

This matters for:
- Tax brackets where thresholds are precise ($47,150 vs $47,150.00001)
- Rounding to pennies (IRS requires exact cent amounts)
- Audit trails where $0.01 discrepancy can flag issues
"""

from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP, InvalidOperation
from typing import Union, Optional, List
import logging

logger = logging.getLogger(__name__)

# Type alias for values that can be converted to Decimal
Numeric = Union[int, float, str, Decimal]

# Default precision context
MONEY_PLACES = Decimal("0.01")  # Round to pennies
RATE_PLACES = Decimal("0.0001")  # 4 decimal places for rates


def to_decimal(value: Numeric) -> Decimal:
    """
    Convert a numeric value to Decimal.

    Args:
        value: Value to convert (int, float, str, or Decimal)

    Returns:
        Decimal representation

    Examples:
        >>> to_decimal(100)
        Decimal('100')
        >>> to_decimal(100.50)
        Decimal('100.5')
        >>> to_decimal("100.50")
        Decimal('100.50')
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # Convert float to string first to preserve representation
        return Decimal(str(value))
    return Decimal(value)


def money(value: Numeric) -> Decimal:
    """
    Convert value to money (rounded to pennies).

    Args:
        value: Value to convert

    Returns:
        Decimal rounded to 2 decimal places

    Examples:
        >>> money(100.999)
        Decimal('101.00')
        >>> money(100.994)
        Decimal('100.99')
    """
    return to_decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def money_down(value: Numeric) -> Decimal:
    """
    Convert value to money, rounding down (truncate).

    Used when IRS rules specify rounding down (e.g., some credits).

    Args:
        value: Value to convert

    Returns:
        Decimal truncated to 2 decimal places

    Examples:
        >>> money_down(100.999)
        Decimal('100.99')
    """
    return to_decimal(value).quantize(MONEY_PLACES, rounding=ROUND_DOWN)


def money_up(value: Numeric) -> Decimal:
    """
    Convert value to money, rounding up.

    Args:
        value: Value to convert

    Returns:
        Decimal rounded up to 2 decimal places

    Examples:
        >>> money_up(100.001)
        Decimal('100.01')
    """
    return to_decimal(value).quantize(MONEY_PLACES, rounding=ROUND_UP)


def rate(value: Numeric) -> Decimal:
    """
    Convert value to a rate (4 decimal places).

    Args:
        value: Value to convert (e.g., 0.22 for 22%)

    Returns:
        Decimal with 4 decimal places

    Examples:
        >>> rate(0.22)
        Decimal('0.2200')
    """
    return to_decimal(value).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def add(*values: Numeric) -> Decimal:
    """
    Add multiple values with Decimal precision.

    Args:
        *values: Values to add

    Returns:
        Sum as Decimal

    Examples:
        >>> add(100.10, 200.20, 300.30)
        Decimal('600.60')
    """
    result = Decimal("0")
    for v in values:
        result += to_decimal(v)
    return result


def subtract(a: Numeric, b: Numeric) -> Decimal:
    """
    Subtract b from a with Decimal precision.

    Args:
        a: Minuend
        b: Subtrahend

    Returns:
        Difference as Decimal
    """
    return to_decimal(a) - to_decimal(b)


def multiply(a: Numeric, b: Numeric) -> Decimal:
    """
    Multiply two values with Decimal precision.

    Args:
        a: First factor
        b: Second factor

    Returns:
        Product as Decimal
    """
    return to_decimal(a) * to_decimal(b)


def divide(a: Numeric, b: Numeric, default: Optional[Numeric] = None) -> Decimal:
    """
    Divide a by b with Decimal precision.

    Args:
        a: Dividend
        b: Divisor
        default: Value to return if division by zero (None raises error)

    Returns:
        Quotient as Decimal

    Raises:
        InvalidOperation: If b is zero and no default provided
    """
    b_dec = to_decimal(b)
    if b_dec == 0:
        if default is not None:
            return to_decimal(default)
        raise InvalidOperation("Division by zero")
    return to_decimal(a) / b_dec


def percent(value: Numeric, percentage: Numeric) -> Decimal:
    """
    Calculate percentage of a value.

    Args:
        value: Base value
        percentage: Percentage as decimal (0.22 for 22%)

    Returns:
        Percentage of value

    Examples:
        >>> percent(1000, 0.22)
        Decimal('220')
    """
    return multiply(value, percentage)


def percent_of(part: Numeric, whole: Numeric) -> Decimal:
    """
    Calculate what percentage part is of whole.

    Args:
        part: The part value
        whole: The whole value

    Returns:
        Percentage as decimal (0.5 for 50%)

    Examples:
        >>> percent_of(50, 100)
        Decimal('0.5')
    """
    return divide(part, whole, default=0)


def min_decimal(*values: Numeric) -> Decimal:
    """
    Find minimum of values with Decimal precision.

    Args:
        *values: Values to compare

    Returns:
        Minimum value as Decimal
    """
    return min(to_decimal(v) for v in values)


def max_decimal(*values: Numeric) -> Decimal:
    """
    Find maximum of values with Decimal precision.

    Args:
        *values: Values to compare

    Returns:
        Maximum value as Decimal
    """
    return max(to_decimal(v) for v in values)


def clamp(value: Numeric, minimum: Numeric, maximum: Numeric) -> Decimal:
    """
    Clamp value between minimum and maximum.

    Args:
        value: Value to clamp
        minimum: Minimum allowed
        maximum: Maximum allowed

    Returns:
        Clamped value as Decimal

    Examples:
        >>> clamp(150, 0, 100)
        Decimal('100')
        >>> clamp(-50, 0, 100)
        Decimal('0')
    """
    return max_decimal(minimum, min_decimal(value, maximum))


def sum_money(values: List[Numeric]) -> Decimal:
    """
    Sum a list of monetary values.

    Args:
        values: List of values to sum

    Returns:
        Sum rounded to pennies
    """
    return money(add(*values))


def calculate_tax_in_bracket(
    income: Numeric,
    bracket_start: Numeric,
    bracket_end: Numeric,
    rate_value: Numeric
) -> Decimal:
    """
    Calculate tax for income within a bracket.

    Args:
        income: Total taxable income
        bracket_start: Start of bracket (exclusive)
        bracket_end: End of bracket (inclusive)
        rate_value: Tax rate for this bracket (e.g., 0.22 for 22%)

    Returns:
        Tax amount for this bracket (rounded to pennies)

    Examples:
        >>> calculate_tax_in_bracket(100000, 47150, 100525, 0.22)
        Decimal('11627.00')
    """
    income_d = to_decimal(income)
    start_d = to_decimal(bracket_start)
    end_d = to_decimal(bracket_end)
    rate_d = to_decimal(rate_value)

    if income_d <= start_d:
        return Decimal("0")

    taxable_in_bracket = min_decimal(income_d, end_d) - start_d
    if taxable_in_bracket <= 0:
        return Decimal("0")

    return money(multiply(taxable_in_bracket, rate_d))


def calculate_progressive_tax(
    income: Numeric,
    brackets: List[tuple]
) -> Decimal:
    """
    Calculate tax using progressive brackets.

    Args:
        income: Taxable income
        brackets: List of (threshold, rate) tuples in ascending order.
                  Each bracket applies from previous threshold to this threshold.

    Returns:
        Total tax (rounded to pennies)

    Examples:
        >>> brackets = [
        ...     (11600, 0.10),
        ...     (47150, 0.12),
        ...     (100525, 0.22),
        ...     (191950, 0.24),
        ... ]
        >>> calculate_progressive_tax(75000, brackets)
        Decimal('11862.00')
    """
    income_d = to_decimal(income)
    total_tax = Decimal("0")
    prev_threshold = Decimal("0")

    for threshold, rate_value in brackets:
        threshold_d = to_decimal(threshold)
        rate_d = to_decimal(rate_value)

        if income_d <= prev_threshold:
            break

        taxable = min_decimal(income_d, threshold_d) - prev_threshold
        if taxable > 0:
            total_tax += multiply(taxable, rate_d)

        prev_threshold = threshold_d

    return money(total_tax)


def safe_divide_for_rate(
    numerator: Numeric,
    denominator: Numeric
) -> Decimal:
    """
    Safe division for calculating rates (returns 0 if denominator is 0).

    Args:
        numerator: Top of fraction
        denominator: Bottom of fraction

    Returns:
        Rate with 4 decimal places, or 0 if denominator is 0
    """
    denom = to_decimal(denominator)
    if denom == 0:
        return Decimal("0.0000")
    return rate(divide(numerator, denominator))


def to_float(value: Decimal) -> float:
    """
    Convert Decimal back to float for API responses.

    Use sparingly - prefer keeping as Decimal internally.

    Args:
        value: Decimal value

    Returns:
        Float representation
    """
    return float(value)


def format_money(value: Numeric) -> str:
    """
    Format value as money string.

    Args:
        value: Value to format

    Returns:
        Formatted string with $ and commas

    Examples:
        >>> format_money(1234567.89)
        '$1,234,567.89'
    """
    m = money(value)
    return f"${m:,.2f}"


def format_percentage(value: Numeric, decimal_places: int = 2) -> str:
    """
    Format value as percentage string.

    Args:
        value: Value as decimal (0.22 for 22%)
        decimal_places: Number of decimal places

    Returns:
        Formatted percentage string

    Examples:
        >>> format_percentage(0.2245)
        '22.45%'
    """
    pct = multiply(value, 100)
    return f"{pct:.{decimal_places}f}%"


# Constants for common tax calculations
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

# IRS-specific constants (2025)
SE_NET_EARNINGS_FACTOR = Decimal("0.9235")
SS_RATE = Decimal("0.124")
MEDICARE_RATE = Decimal("0.029")
ADDITIONAL_MEDICARE_RATE = Decimal("0.009")
NIIT_RATE = Decimal("0.038")


def calculate_self_employment_tax(net_self_employment: Numeric) -> dict:
    """
    Calculate self-employment tax with Decimal precision.

    Args:
        net_self_employment: Net self-employment income

    Returns:
        Dictionary with tax breakdown

    Reference: IRS Schedule SE
    """
    net_se = to_decimal(net_self_employment)

    # SE earnings = net_se * 0.9235
    se_earnings = multiply(net_se, SE_NET_EARNINGS_FACTOR)

    # Social Security portion (up to wage base - simplified here)
    ss_wage_base = Decimal("176100")  # 2025
    ss_taxable = min_decimal(se_earnings, ss_wage_base)
    ss_tax = money(multiply(ss_taxable, SS_RATE))

    # Medicare portion
    medicare_tax = money(multiply(se_earnings, MEDICARE_RATE))

    # Total SE tax
    total_se_tax = add(ss_tax, medicare_tax)

    # Deductible portion (1/2 of SE tax)
    se_deduction = money(divide(total_se_tax, 2))

    return {
        "net_self_employment": to_float(net_se),
        "se_earnings": to_float(se_earnings),
        "ss_taxable": to_float(ss_taxable),
        "ss_tax": to_float(ss_tax),
        "medicare_tax": to_float(medicare_tax),
        "total_se_tax": to_float(total_se_tax),
        "se_deduction": to_float(se_deduction),
    }
