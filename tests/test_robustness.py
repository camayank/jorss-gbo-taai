"""
Robustness Testing Suite

Tests validation helpers and error handling:
- Input validation functions
- SSN validation
- Currency validation
- String sanitization
"""

import pytest
from decimal import Decimal

from conftest import CSRF_BYPASS_HEADERS


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidationHelpers:
    """Test validation helper functions"""

    def test_validate_ssn_valid(self):
        from src.web.validation_helpers import validate_ssn

        is_valid, error = validate_ssn("123-45-6789")
        assert is_valid == True
        assert error is None

    def test_validate_ssn_invalid_zeros(self):
        from src.web.validation_helpers import validate_ssn

        is_valid, error = validate_ssn("000-00-0000")
        assert is_valid == False
        assert "cannot be all zeros" in error

    def test_validate_ssn_invalid_area(self):
        from src.web.validation_helpers import validate_ssn

        is_valid, error = validate_ssn("666-12-3456")
        assert is_valid == False
        assert "666" in error

    def test_validate_currency_valid(self):
        from src.web.validation_helpers import validate_currency

        is_valid, error, value = validate_currency(75000, "wages", min_value=Decimal("0"))
        assert is_valid == True
        assert error is None
        assert value == Decimal("75000")

    def test_validate_currency_negative(self):
        from src.web.validation_helpers import validate_currency

        is_valid, error, value = validate_currency(-1000, "wages", allow_negative=False)
        assert is_valid == False
        assert "cannot be negative" in error

    def test_sanitize_string_xss(self):
        from src.web.validation_helpers import sanitize_string

        dirty = "<script>alert('xss')</script>"
        clean = sanitize_string(dirty)

        assert "<script>" not in clean
        assert "alert" in clean  # Text preserved

    def test_sanitize_string_sql(self):
        from src.web.validation_helpers import sanitize_string

        dirty = "'; DROP TABLE users;--"
        clean = sanitize_string(dirty)

        # Should be escaped or cleaned
        assert clean != dirty or "'" not in clean

    def test_validate_ssn_various_formats(self):
        """Test SSN validation with various formats"""
        from src.web.validation_helpers import validate_ssn

        # Valid SSN - should pass
        is_valid, error = validate_ssn("123-45-6789")
        assert is_valid == True

        # No dashes
        is_valid, error = validate_ssn("123456789")
        assert is_valid == True

        # Area number 900+ is invalid
        is_valid, error = validate_ssn("900-12-3456")
        assert is_valid == False


class TestInputValidation:
    """Test edge cases in validation"""

    def test_empty_string_sanitization(self):
        from src.web.validation_helpers import sanitize_string

        result = sanitize_string("")
        assert result == ""

    def test_none_string_sanitization(self):
        from src.web.validation_helpers import sanitize_string

        result = sanitize_string(None)
        assert result is None or result == ""

    def test_currency_string_conversion(self):
        from src.web.validation_helpers import validate_currency

        # String input should be converted
        is_valid, error, value = validate_currency("50000.50", "amount")
        assert is_valid == True
        assert value == Decimal("50000.50")

    def test_currency_max_value(self):
        from src.web.validation_helpers import validate_currency

        # Test max value constraint
        is_valid, error, value = validate_currency(
            1000000, "wages",
            max_value=Decimal("500000")
        )
        assert is_valid == False
        assert "maximum" in error.lower() or "exceed" in error.lower()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
