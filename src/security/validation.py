"""
Input Validation and Sanitization

Provides comprehensive input validation and sanitization functions to prevent:
- XSS (Cross-Site Scripting)
- SQL Injection (defense in depth - use with parameterized queries)
- Command Injection
- Path Traversal
- Email/Phone injection

CRITICAL: This is defense-in-depth. Always use parameterized SQL queries.
"""

import re
import html
from typing import Optional, List
from decimal import Decimal, InvalidOperation
from datetime import datetime


# ============================================================================
# STRING SANITIZATION
# ============================================================================

def sanitize_string(
    value: str,
    max_length: int = 1000,
    allow_newlines: bool = False,
    allow_html: bool = False
) -> str:
    """
    Sanitize string input to prevent XSS and injection attacks.

    Args:
        value: Input string
        max_length: Maximum allowed length
        allow_newlines: Allow \\n and \\r characters
        allow_html: Allow HTML tags (escaped by default)

    Returns:
        Sanitized string

    Examples:
        >>> sanitize_string("<script>alert('xss')</script>")
        "&lt;script&gt;alert('xss')&lt;/script&gt;"
        >>> sanitize_string("Hello\\nWorld", allow_newlines=True)
        "Hello\\nWorld"
    """
    if not isinstance(value, str):
        value = str(value)

    # Truncate to max length
    value = value[:max_length]

    # Remove null bytes
    value = value.replace('\x00', '')

    # Remove or escape newlines
    if not allow_newlines:
        value = value.replace('\n', ' ').replace('\r', ' ')

    # Escape HTML unless explicitly allowed
    if not allow_html:
        value = html.escape(value, quote=True)

    # Remove control characters except whitespace
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')

    return value.strip()


def sanitize_email(email: str) -> Optional[str]:
    """
    Validate and sanitize email address.

    Args:
        email: Email address

    Returns:
        Sanitized email or None if invalid

    Examples:
        >>> sanitize_email("user@example.com")
        "user@example.com"
        >>> sanitize_email("invalid.email")
        None
    """
    if not isinstance(email, str):
        return None

    email = email.strip().lower()

    # Basic email validation regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email):
        return None

    # Prevent email injection (newlines, semicolons)
    if any(char in email for char in ['\n', '\r', ';', ',', ' ']):
        return None

    # Max length check
    if len(email) > 254:  # RFC 5321
        return None

    return email


def sanitize_phone(phone: str, country: str = "US") -> Optional[str]:
    """
    Validate and sanitize phone number.

    Args:
        phone: Phone number
        country: Country code (default: US)

    Returns:
        Sanitized phone (digits only) or None if invalid

    Examples:
        >>> sanitize_phone("(555) 123-4567")
        "5551234567"
        >>> sanitize_phone("+1-555-123-4567")
        "15551234567"
    """
    if not isinstance(phone, str):
        return None

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # US phone validation (10 or 11 digits)
    if country == "US":
        if len(digits) == 10:
            return digits
        elif len(digits) == 11 and digits[0] == '1':
            return digits
        else:
            return None

    # International: 7-15 digits
    if 7 <= len(digits) <= 15:
        return digits

    return None


# ============================================================================
# NUMERIC VALIDATION
# ============================================================================

def sanitize_integer(
    value: any,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None
) -> Optional[int]:
    """
    Validate and sanitize integer input.

    Args:
        value: Input value
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Sanitized integer or None if invalid

    Examples:
        >>> sanitize_integer("42")
        42
        >>> sanitize_integer("999", max_value=100)
        None
    """
    try:
        num = int(value)

        if min_value is not None and num < min_value:
            return None
        if max_value is not None and num > max_value:
            return None

        return num
    except (ValueError, TypeError):
        return None


def sanitize_decimal(
    value: any,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    max_decimal_places: int = 2
) -> Optional[Decimal]:
    """
    Validate and sanitize decimal input (for money, percentages).

    Args:
        value: Input value
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        max_decimal_places: Maximum decimal places

    Returns:
        Sanitized Decimal or None if invalid

    Examples:
        >>> sanitize_decimal("12.34")
        Decimal('12.34')
        >>> sanitize_decimal("12.999", max_decimal_places=2)
        Decimal('12.99')
    """
    try:
        # Handle string conversion
        if isinstance(value, str):
            # Remove currency symbols and commas
            value = value.replace('$', '').replace(',', '').strip()

        num = Decimal(str(value))

        # Check bounds
        if min_value is not None and num < min_value:
            return None
        if max_value is not None and num > max_value:
            return None

        # Round to max decimal places
        quantize_str = '0.' + '0' * max_decimal_places
        num = num.quantize(Decimal(quantize_str))

        return num
    except (ValueError, TypeError, InvalidOperation):
        return None


def sanitize_tax_amount(value: any) -> Optional[Decimal]:
    """
    Sanitize tax-related monetary amounts.

    Args:
        value: Input value

    Returns:
        Sanitized Decimal or None if invalid

    Examples:
        >>> sanitize_tax_amount("$1,234.56")
        Decimal('1234.56')
        >>> sanitize_tax_amount(-100)
        None
    """
    return sanitize_decimal(
        value,
        min_value=Decimal('0'),
        max_value=Decimal('999999999.99'),  # ~1 billion max
        max_decimal_places=2
    )


# ============================================================================
# TAX-SPECIFIC VALIDATION
# ============================================================================

def sanitize_ssn(ssn: str) -> Optional[str]:
    """
    Validate and sanitize Social Security Number.

    Args:
        ssn: SSN (with or without dashes)

    Returns:
        SSN in format XXX-XX-XXXX or None if invalid

    Examples:
        >>> sanitize_ssn("123456789")
        "123-45-6789"
        >>> sanitize_ssn("123-45-6789")
        "123-45-6789"
        >>> sanitize_ssn("000-00-0000")
        None
    """
    if not isinstance(ssn, str):
        return None

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', ssn)

    # Must be exactly 9 digits
    if len(digits) != 9:
        return None

    # Validate SSN rules
    area = digits[0:3]
    group = digits[3:5]
    serial = digits[5:9]

    # Invalid SSNs
    if area == '000' or area == '666' or area.startswith('9'):
        return None
    if group == '00':
        return None
    if serial == '0000':
        return None

    # Return formatted
    return f"{area}-{group}-{serial}"


def sanitize_ein(ein: str) -> Optional[str]:
    """
    Validate and sanitize Employer Identification Number.

    Args:
        ein: EIN (with or without dash)

    Returns:
        EIN in format XX-XXXXXXX or None if invalid

    Examples:
        >>> sanitize_ein("12-3456789")
        "12-3456789"
        >>> sanitize_ein("123456789")
        "12-3456789"
    """
    if not isinstance(ein, str):
        return None

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', ein)

    # Must be exactly 9 digits
    if len(digits) != 9:
        return None

    # Return formatted
    return f"{digits[0:2]}-{digits[2:9]}"


def sanitize_tax_year(year: any) -> Optional[int]:
    """
    Validate tax year.

    Args:
        year: Tax year

    Returns:
        Valid tax year or None

    Examples:
        >>> sanitize_tax_year(2024)
        2024
        >>> sanitize_tax_year(1899)
        None
    """
    current_year = datetime.now().year
    return sanitize_integer(
        year,
        min_value=1900,
        max_value=current_year + 1  # Allow next year for planning
    )


def sanitize_filing_status(status: str) -> Optional[str]:
    """
    Validate filing status.

    Args:
        status: Filing status

    Returns:
        Normalized filing status or None

    Examples:
        >>> sanitize_filing_status("SINGLE")
        "single"
        >>> sanitize_filing_status("invalid")
        None
    """
    if not isinstance(status, str):
        return None

    status = status.lower().strip()

    valid_statuses = {
        'single',
        'married_joint',
        'married_separate',
        'head_of_household',
        'qualifying_widow'
    }

    # Allow common variations
    status_map = {
        'married': 'married_joint',
        'married filing jointly': 'married_joint',
        'married filing separately': 'married_separate',
        'hoh': 'head_of_household',
        'widow': 'qualifying_widow',
        'widower': 'qualifying_widow'
    }

    status = status_map.get(status, status)

    if status in valid_statuses:
        return status

    return None


# ============================================================================
# PATH VALIDATION (Prevent path traversal)
# ============================================================================

def sanitize_filename(filename: str) -> Optional[str]:
    """
    Sanitize filename to prevent path traversal attacks.

    Args:
        filename: Original filename

    Returns:
        Safe filename or None if invalid

    Examples:
        >>> sanitize_filename("document.pdf")
        "document.pdf"
        >>> sanitize_filename("../../../etc/passwd")
        None
        >>> sanitize_filename("my file (1).pdf")
        "my_file_1.pdf"
    """
    if not isinstance(filename, str):
        return None

    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')

    # Remove directory traversal attempts
    if '..' in filename:
        return None

    # Remove non-alphanumeric except . _ -
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Limit length
    if len(filename) > 255:
        # Preserve extension
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')

    # Must have content
    if not filename or filename == '.' or filename == '_':
        return None

    return filename


# ============================================================================
# BATCH SANITIZATION
# ============================================================================

def sanitize_list(
    values: List[any],
    sanitizer_func,
    max_items: int = 100
) -> List[any]:
    """
    Sanitize a list of values.

    Args:
        values: List of values to sanitize
        sanitizer_func: Function to sanitize each value
        max_items: Maximum number of items

    Returns:
        List of sanitized values (None values removed)

    Examples:
        >>> sanitize_list(["user@example.com", "invalid"], sanitize_email)
        ["user@example.com"]
    """
    if not isinstance(values, list):
        return []

    # Limit list size
    values = values[:max_items]

    # Sanitize each item
    sanitized = []
    for value in values:
        result = sanitizer_func(value)
        if result is not None:
            sanitized.append(result)

    return sanitized


# ============================================================================
# AGGREGATE VALIDATORS (For form validation)
# ============================================================================

class ValidationError(Exception):
    """Raised when validation fails"""
    pass


def validate_tax_return_data(data: dict) -> dict:
    """
    Validate complete tax return data.

    Args:
        data: Tax return data dictionary

    Returns:
        Validated and sanitized data dictionary

    Raises:
        ValidationError: If validation fails
    """
    validated = {}

    # Required fields
    if 'tax_year' not in data:
        raise ValidationError("tax_year is required")

    validated['tax_year'] = sanitize_tax_year(data['tax_year'])
    if validated['tax_year'] is None:
        raise ValidationError(f"Invalid tax_year: {data['tax_year']}")

    # Filing status
    if 'filing_status' in data:
        validated['filing_status'] = sanitize_filing_status(data['filing_status'])
        if validated['filing_status'] is None:
            raise ValidationError(f"Invalid filing_status: {data['filing_status']}")

    # Income (required)
    if 'income' in data:
        validated['income'] = sanitize_tax_amount(data['income'])
        if validated['income'] is None:
            raise ValidationError(f"Invalid income: {data['income']}")

    # SSN (optional)
    if 'ssn' in data and data['ssn']:
        validated['ssn'] = sanitize_ssn(data['ssn'])
        if validated['ssn'] is None:
            raise ValidationError(f"Invalid SSN format")

    # EIN (optional)
    if 'ein' in data and data['ein']:
        validated['ein'] = sanitize_ein(data['ein'])
        if validated['ein'] is None:
            raise ValidationError(f"Invalid EIN format")

    return validated


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    'sanitize_string',
    'sanitize_email',
    'sanitize_phone',
    'sanitize_integer',
    'sanitize_decimal',
    'sanitize_tax_amount',
    'sanitize_ssn',
    'sanitize_ein',
    'sanitize_tax_year',
    'sanitize_filing_status',
    'sanitize_filename',
    'sanitize_list',
    'validate_tax_return_data',
    'ValidationError',
]
