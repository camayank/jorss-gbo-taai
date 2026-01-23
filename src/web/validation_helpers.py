"""
Validation Helpers - Robust input validation for tax platform

Provides reusable validation functions for:
- SSN/EIN format validation
- Currency/numeric validation
- Date validation
- Name and address validation
- Data sanitization
"""

import re
from typing import Optional, Tuple, Any
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SSN/EIN Validation
# =============================================================================

def validate_ssn(ssn: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Social Security Number format.

    Args:
        ssn: SSN string in various formats

    Returns:
        (is_valid, error_message)

    Examples:
        >>> validate_ssn("123-45-6789")
        (True, None)
        >>> validate_ssn("000-00-0000")
        (False, "Invalid SSN: cannot be all zeros")
    """
    if not ssn:
        return False, "SSN is required"

    # Remove formatting
    clean_ssn = re.sub(r'[^0-9]', '', ssn)

    # Check length
    if len(clean_ssn) != 9:
        return False, f"Invalid SSN format: expected 9 digits, got {len(clean_ssn)}"

    # Check for invalid patterns
    if clean_ssn == "000000000":
        return False, "Invalid SSN: cannot be all zeros"

    if clean_ssn[:3] == "000":
        return False, "Invalid SSN: area number cannot be 000"

    if clean_ssn[:3] == "666":
        return False, "Invalid SSN: area number cannot be 666"

    if clean_ssn[:3].startswith("9"):
        return False, "Invalid SSN: area number cannot start with 9"

    if clean_ssn[3:5] == "00":
        return False, "Invalid SSN: group number cannot be 00"

    if clean_ssn[5:] == "0000":
        return False, "Invalid SSN: serial number cannot be 0000"

    return True, None


def validate_ein(ein: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Employer Identification Number format.

    Args:
        ein: EIN string (e.g., "12-3456789")

    Returns:
        (is_valid, error_message)
    """
    if not ein:
        return False, "EIN is required"

    # Remove formatting
    clean_ein = re.sub(r'[^0-9]', '', ein)

    # Check length
    if len(clean_ein) != 9:
        return False, f"Invalid EIN format: expected 9 digits, got {len(clean_ein)}"

    # Check for invalid patterns
    if clean_ein == "000000000":
        return False, "Invalid EIN: cannot be all zeros"

    # First two digits must be valid prefix (10-99, excluding some)
    prefix = int(clean_ein[:2])
    invalid_prefixes = [7, 8, 9, 17, 18, 19, 28, 29, 49, 69, 70, 78, 79, 89]
    if prefix < 10 or prefix > 99 or prefix in invalid_prefixes:
        return False, f"Invalid EIN: prefix {prefix} is not valid"

    return True, None


# =============================================================================
# Currency/Numeric Validation
# =============================================================================

def validate_currency(value: Any, field_name: str, min_value: Optional[Decimal] = None,
                     max_value: Optional[Decimal] = None, allow_negative: bool = False) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Validate currency value.

    Args:
        value: Value to validate (str, int, float, or Decimal)
        field_name: Name of the field (for error messages)
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_negative: Whether negative values are allowed

    Returns:
        (is_valid, error_message, parsed_value)

    Examples:
        >>> validate_currency(75000, "wages", min_value=Decimal("0"), max_value=Decimal("10000000"))
        (True, None, Decimal('75000'))
        >>> validate_currency(-1000, "wages", allow_negative=False)
        (False, "wages cannot be negative", None)
    """
    if value is None:
        return False, f"{field_name} is required", None

    # Parse to Decimal
    try:
        if isinstance(value, Decimal):
            parsed = value
        else:
            # Remove currency symbols and commas
            clean_value = str(value).replace('$', '').replace(',', '').strip()
            parsed = Decimal(clean_value)
    except (InvalidOperation, ValueError) as e:
        return False, f"Invalid {field_name}: must be a valid number", None

    # Check for negative
    if not allow_negative and parsed < 0:
        return False, f"{field_name} cannot be negative", None

    # Check min value
    if min_value is not None and parsed < min_value:
        return False, f"{field_name} must be at least {min_value}", None

    # Check max value
    if max_value is not None and parsed > max_value:
        return False, f"{field_name} cannot exceed {max_value}", None

    # Check for reasonable precision (max 2 decimal places for currency)
    if parsed.as_tuple().exponent < -2:
        return False, f"{field_name} cannot have more than 2 decimal places", None

    return True, None, parsed


def validate_positive_integer(value: Any, field_name: str, min_value: int = 1,
                              max_value: Optional[int] = None) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate positive integer.

    Args:
        value: Value to validate
        field_name: Name of the field (for error messages)
        min_value: Minimum allowed value (default 1)
        max_value: Maximum allowed value

    Returns:
        (is_valid, error_message, parsed_value)
    """
    if value is None:
        return False, f"{field_name} is required", None

    try:
        parsed = int(value)
    except (ValueError, TypeError):
        return False, f"Invalid {field_name}: must be an integer", None

    if parsed < min_value:
        return False, f"{field_name} must be at least {min_value}", None

    if max_value is not None and parsed > max_value:
        return False, f"{field_name} cannot exceed {max_value}", None

    return True, None, parsed


# =============================================================================
# Date Validation
# =============================================================================

def validate_date(date_str: str, field_name: str, min_date: Optional[date] = None,
                 max_date: Optional[date] = None) -> Tuple[bool, Optional[str], Optional[date]]:
    """
    Validate date string.

    Args:
        date_str: Date string (YYYY-MM-DD or MM/DD/YYYY)
        field_name: Name of the field (for error messages)
        min_date: Minimum allowed date
        max_date: Maximum allowed date

    Returns:
        (is_valid, error_message, parsed_date)
    """
    if not date_str:
        return False, f"{field_name} is required", None

    # Try parsing different formats
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"]
    parsed = None

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue

    if parsed is None:
        return False, f"Invalid {field_name}: expected format YYYY-MM-DD or MM/DD/YYYY", None

    # Check min date
    if min_date and parsed < min_date:
        return False, f"{field_name} cannot be before {min_date}", None

    # Check max date
    if max_date and parsed > max_date:
        return False, f"{field_name} cannot be after {max_date}", None

    return True, None, parsed


def validate_tax_year(year: int) -> Tuple[bool, Optional[str]]:
    """
    Validate tax year.

    Args:
        year: Tax year (e.g., 2024)

    Returns:
        (is_valid, error_message)
    """
    current_year = datetime.now().year

    # Can't file for future years
    if year > current_year:
        return False, f"Cannot file for future year {year}"

    # IRS typically allows amendments up to 3 years back
    if year < current_year - 10:
        return False, f"Tax year {year} is too old (must be within last 10 years)"

    return True, None


# =============================================================================
# Name/Address Validation
# =============================================================================

def validate_name(name: str, field_name: str, max_length: int = 100) -> Tuple[bool, Optional[str]]:
    """
    Validate person's name.

    Args:
        name: Name string
        field_name: Name of the field (for error messages)
        max_length: Maximum allowed length

    Returns:
        (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, f"{field_name} is required"

    name = name.strip()

    # Check length
    if len(name) > max_length:
        return False, f"{field_name} cannot exceed {max_length} characters"

    # Check for valid characters (letters, spaces, hyphens, apostrophes, periods)
    if not re.match(r"^[a-zA-Z\s\-'.]+$", name):
        return False, f"{field_name} contains invalid characters"

    # Check for suspicious patterns (all caps, repeated characters)
    if name.isupper() and len(name) > 5:
        logger.warning(f"{field_name} is all caps: {name}")

    return True, None


def validate_address(address: str, field_name: str = "Address") -> Tuple[bool, Optional[str]]:
    """
    Validate address string.

    Args:
        address: Address string
        field_name: Name of the field (for error messages)

    Returns:
        (is_valid, error_message)
    """
    if not address or not address.strip():
        return False, f"{field_name} is required"

    address = address.strip()

    # Check length
    if len(address) < 5:
        return False, f"{field_name} is too short"

    if len(address) > 500:
        return False, f"{field_name} cannot exceed 500 characters"

    # Very basic validation - just check for suspicious patterns
    if re.search(r'<script|javascript:|onerror=', address, re.IGNORECASE):
        return False, f"{field_name} contains suspicious content"

    return True, None


# =============================================================================
# Business Logic Validation
# =============================================================================

def validate_filing_status_consistency(filing_status: str, has_spouse_data: bool) -> Tuple[bool, Optional[str]]:
    """
    Validate filing status matches provided data.

    Args:
        filing_status: Filing status string
        has_spouse_data: Whether spouse information was provided

    Returns:
        (is_valid, error_message)
    """
    filing_status_lower = filing_status.lower()

    if "married" in filing_status_lower and "joint" in filing_status_lower:
        if not has_spouse_data:
            return False, "Married Filing Jointly requires spouse information"

    if "single" in filing_status_lower:
        if has_spouse_data:
            logger.warning("Single filing status but spouse data provided")

    return True, None


def validate_income_consistency(w2_wages: Optional[Decimal], federal_withheld: Optional[Decimal]) -> Tuple[bool, Optional[str]]:
    """
    Validate income data is internally consistent.

    Args:
        w2_wages: W-2 wages
        federal_withheld: Federal tax withheld

    Returns:
        (is_valid, error_message)
    """
    if w2_wages is None or federal_withheld is None:
        return True, None  # Can't validate without both values

    # Federal withholding should typically be less than wages
    if federal_withheld > w2_wages:
        return False, "Federal tax withheld cannot exceed total wages"

    # Federal withholding shouldn't be more than ~37% (max bracket)
    if federal_withheld > w2_wages * Decimal("0.5"):
        return False, "Federal tax withheld seems unusually high (>50% of wages)"

    # Warn if no federal withholding on substantial income
    if w2_wages > 10000 and federal_withheld == 0:
        logger.warning(f"No federal withholding on ${w2_wages} wages")

    return True, None


# =============================================================================
# Data Sanitization
# =============================================================================

def sanitize_string(value: str, max_length: int = 1000, escape_html: bool = True) -> str:
    """
    Sanitize string input to prevent XSS and injection attacks.

    Args:
        value: Input string
        max_length: Maximum allowed length
        escape_html: Whether to escape HTML entities (default True)

    Returns:
        Sanitized string
    """
    import html as html_module

    if not value:
        return ""

    # Trim whitespace
    sanitized = value.strip()

    # Truncate to max length
    sanitized = sanitized[:max_length]

    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')

    # Remove control characters except newlines/tabs
    sanitized = ''.join(char for char in sanitized if char.isprintable() or char in '\n\t')

    # Escape HTML entities to prevent XSS
    if escape_html:
        sanitized = html_module.escape(sanitized, quote=True)

    # Remove dangerous patterns that might survive HTML escaping
    # (e.g., already-encoded attacks)
    dangerous_patterns = [
        (r'(?i)javascript:', ''),  # javascript: protocol
        (r'(?i)on\w+\s*=', ''),    # Event handlers like onclick=
        (r'(?i)data:', ''),        # data: protocol
        (r'(?i)vbscript:', ''),    # vbscript: protocol
    ]

    for pattern, replacement in dangerous_patterns:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


def sanitize_numeric_string(value: str) -> str:
    """
    Sanitize numeric string (for SSN, EIN, phone, etc).

    Args:
        value: Input string

    Returns:
        String with only digits
    """
    if not value:
        return ""

    return re.sub(r'[^0-9]', '', value)


# =============================================================================
# Comprehensive Validation
# =============================================================================

def validate_express_lane_data(data: dict) -> Tuple[bool, list]:
    """
    Comprehensive validation of Express Lane submission data.

    Args:
        data: Dictionary of extracted/edited data

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    # Validate SSN
    if 'ssn' in data:
        is_valid, error = validate_ssn(data['ssn'])
        if not is_valid:
            errors.append(error)

    # Validate names
    if 'first_name' in data:
        is_valid, error = validate_name(data['first_name'], "First name")
        if not is_valid:
            errors.append(error)

    if 'last_name' in data:
        is_valid, error = validate_name(data['last_name'], "Last name")
        if not is_valid:
            errors.append(error)

    # Validate wages
    if 'w2_wages' in data:
        is_valid, error, _ = validate_currency(
            data['w2_wages'],
            "W-2 wages",
            min_value=Decimal("0"),
            max_value=Decimal("10000000")  # $10M seems like reasonable max
        )
        if not is_valid:
            errors.append(error)

    # Validate withholding
    if 'federal_withheld' in data:
        is_valid, error, _ = validate_currency(
            data['federal_withheld'],
            "Federal withholding",
            min_value=Decimal("0"),
            max_value=Decimal("5000000")
        )
        if not is_valid:
            errors.append(error)

    # Validate consistency
    if 'w2_wages' in data and 'federal_withheld' in data:
        try:
            w2_wages = Decimal(str(data['w2_wages']))
            federal_withheld = Decimal(str(data['federal_withheld']))
            is_valid, error = validate_income_consistency(w2_wages, federal_withheld)
            if not is_valid:
                errors.append(error)
        except (InvalidOperation, ValueError):
            pass  # Already caught by individual validations

    # Validate filing status
    if 'filing_status' in data:
        has_spouse = bool(data.get('spouse_first_name') or data.get('spouse_ssn'))
        is_valid, error = validate_filing_status_consistency(data['filing_status'], has_spouse)
        if not is_valid:
            errors.append(error)

    # Validate EIN if present
    if 'employer_ein' in data and data['employer_ein']:
        is_valid, error = validate_ein(data['employer_ein'])
        if not is_valid:
            errors.append(error)

    # Validate tax year
    if 'tax_year' in data:
        is_valid, error = validate_tax_year(int(data['tax_year']))
        if not is_valid:
            errors.append(error)

    return (len(errors) == 0, errors)


# =============================================================================
# Error Message Formatting
# =============================================================================

def format_validation_errors(errors: list) -> str:
    """
    Format list of validation errors into user-friendly message.

    Args:
        errors: List of error strings

    Returns:
        Formatted error message
    """
    if not errors:
        return ""

    if len(errors) == 1:
        return f"Validation error: {errors[0]}"

    numbered_errors = [f"{i+1}. {err}" for i, err in enumerate(errors)]
    return "Validation errors:\n" + "\n".join(numbered_errors)
