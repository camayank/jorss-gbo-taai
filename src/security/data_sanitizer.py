"""
Data Sanitization Module.

Provides PII redaction for logging and external API calls.
CRITICAL: Prevents sensitive data exposure in logs and third-party services.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Union

# Patterns for sensitive data detection
PATTERNS = {
    "ssn": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
    "ein": re.compile(r"\b\d{2}[-\s]?\d{7}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),  # Bank account numbers
    "routing_number": re.compile(r"\b\d{9}\b"),  # Routing numbers
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "api_key": re.compile(r"\b(sk-|pk_|api[_-]?key)[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
}

# Field names that likely contain sensitive data
SENSITIVE_FIELDS: Set[str] = {
    # SSN and tax IDs
    "ssn", "social_security", "social_security_number", "taxpayer_ssn",
    "spouse_ssn", "dependent_ssn", "ein", "employer_id", "tax_id",
    "itin", "ptin",
    # Financial
    "bank_account", "account_number", "routing_number", "aba_number",
    "credit_card", "card_number", "cvv", "cvc", "pin",
    # Personal
    "password", "secret", "token", "api_key", "apikey", "access_token",
    "refresh_token", "auth_token", "session_id", "session_key",
    # Contact
    "phone", "phone_number", "mobile", "cell",
    # Address (partial redaction)
    "street_address", "address_line1", "address_line2",
}

# Redaction placeholder
REDACTED = "[REDACTED]"
PARTIAL_REDACTED = "[REDACTED-PARTIAL]"


class DataSanitizer:
    """
    Sanitizes data to remove or mask PII.

    Use Cases:
    - Logging: Remove all PII before writing to logs
    - External APIs: Remove unnecessary PII before sending to OpenAI, etc.
    - Error messages: Prevent PII exposure in error responses
    - Analytics: Allow aggregation without exposing individual data
    """

    def __init__(
        self,
        additional_fields: Optional[Set[str]] = None,
        additional_patterns: Optional[Dict[str, re.Pattern]] = None,
    ):
        """
        Initialize sanitizer.

        Args:
            additional_fields: Extra field names to consider sensitive
            additional_patterns: Extra regex patterns for sensitive data
        """
        self.sensitive_fields = SENSITIVE_FIELDS.copy()
        if additional_fields:
            self.sensitive_fields.update(additional_fields)

        self.patterns = PATTERNS.copy()
        if additional_patterns:
            self.patterns.update(additional_patterns)

    def sanitize_dict(
        self,
        data: Dict[str, Any],
        deep: bool = True,
        preserve_structure: bool = True,
    ) -> Dict[str, Any]:
        """
        Sanitize a dictionary by redacting sensitive fields.

        Args:
            data: Dictionary to sanitize
            deep: If True, recursively sanitize nested dicts
            preserve_structure: If True, keep keys but redact values

        Returns:
            Sanitized copy of the dictionary
        """
        result = {}

        for key, value in data.items():
            key_lower = key.lower().replace("-", "_").replace(" ", "_")

            # Check if key is sensitive
            if self._is_sensitive_field(key_lower):
                if preserve_structure:
                    result[key] = REDACTED
                continue

            # Recursively handle nested structures
            if deep:
                if isinstance(value, dict):
                    result[key] = self.sanitize_dict(value, deep, preserve_structure)
                elif isinstance(value, list):
                    result[key] = [
                        self.sanitize_dict(item, deep, preserve_structure)
                        if isinstance(item, dict)
                        else self.sanitize_value(item)
                        for item in value
                    ]
                else:
                    result[key] = self.sanitize_value(value)
            else:
                result[key] = self.sanitize_value(value)

        return result

    def sanitize_value(self, value: Any) -> Any:
        """
        Sanitize a single value.

        Args:
            value: Value to sanitize

        Returns:
            Sanitized value
        """
        if value is None:
            return None

        if isinstance(value, str):
            return self.sanitize_string(value)

        if isinstance(value, (int, float, bool)):
            return value

        if isinstance(value, dict):
            return self.sanitize_dict(value)

        if isinstance(value, list):
            return [self.sanitize_value(item) for item in value]

        # Convert other types to string and sanitize
        return self.sanitize_string(str(value))

    def sanitize_string(self, text: str) -> str:
        """
        Sanitize a string by replacing detected PII with placeholders.

        Args:
            text: String to sanitize

        Returns:
            Sanitized string
        """
        result = text

        # Apply all patterns
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == "email":
                # Partial redaction for emails
                result = pattern.sub(self._redact_email, result)
            elif pattern_name == "ssn":
                # Full redaction for SSN
                result = pattern.sub("[SSN-REDACTED]", result)
            elif pattern_name == "api_key":
                # Full redaction for API keys
                result = pattern.sub("[API-KEY-REDACTED]", result)
            else:
                result = pattern.sub(REDACTED, result)

        return result

    def sanitize_for_logging(self, data: Any, context: str = "") -> str:
        """
        Prepare data for safe logging.

        Args:
            data: Data to log
            context: Optional context string

        Returns:
            Safe log message string
        """
        if isinstance(data, dict):
            sanitized = self.sanitize_dict(data)
        elif isinstance(data, str):
            sanitized = self.sanitize_string(data)
        else:
            sanitized = self.sanitize_value(data)

        if context:
            return f"[{context}] {sanitized}"
        return str(sanitized)

    def sanitize_for_external_api(
        self,
        data: Dict[str, Any],
        allowed_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sanitize data for sending to external APIs (e.g., OpenAI).

        This is more aggressive than logging sanitization:
        - Removes all PII by default
        - Only keeps explicitly allowed fields
        - Converts financial amounts to ranges

        Args:
            data: Data to sanitize
            allowed_fields: Set of field names that are safe to include

        Returns:
            Sanitized data safe for external APIs
        """
        allowed = allowed_fields or {
            # Safe fields for AI analysis
            "filing_status", "tax_year", "state",
            "num_dependents", "age_range",
            "income_bracket", "deduction_type",
            # Categorized data
            "has_w2", "has_1099", "has_business",
            "has_investments", "has_rental",
        }

        result = {}

        for key, value in data.items():
            key_lower = key.lower()

            # Only include allowed fields
            if key_lower not in allowed:
                continue

            # Sanitize the value even if allowed
            if isinstance(value, dict):
                result[key] = self.sanitize_for_external_api(value, allowed_fields)
            elif isinstance(value, str):
                result[key] = self.sanitize_string(value)
            else:
                result[key] = value

        return result

    def create_analysis_context(
        self,
        tax_return: Any,
        include_amounts: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a sanitized context for AI analysis.

        Converts detailed financial data into categories and ranges
        that are safe for external AI processing.

        Args:
            tax_return: Tax return object
            include_amounts: If True, include rounded amounts (not exact)

        Returns:
            Sanitized context dictionary
        """
        context = {}

        # Safe categorical data
        if hasattr(tax_return, "taxpayer"):
            tp = tax_return.taxpayer
            context["filing_status"] = getattr(tp, "filing_status", "unknown")
            context["state"] = getattr(tp, "state", "unknown")

            # Age as range
            age = getattr(tp, "age", 0)
            context["age_range"] = self._age_to_range(age)

            # Dependents count
            deps = getattr(tp, "dependents", [])
            context["num_dependents"] = len(deps) if isinstance(deps, list) else 0

        # Income categories
        if hasattr(tax_return, "income"):
            inc = tax_return.income
            context["has_w2"] = getattr(inc, "wages", 0) > 0
            context["has_self_employment"] = getattr(inc, "self_employment_income", 0) > 0
            context["has_investments"] = (
                getattr(inc, "dividends_qualified", 0) > 0 or
                getattr(inc, "capital_gains_long", 0) != 0
            )
            context["has_rental"] = getattr(inc, "rental_income", 0) != 0
            context["has_crypto"] = getattr(inc, "has_virtual_currency", False)
            context["has_foreign"] = getattr(inc, "has_foreign_income", False)

            if include_amounts:
                total_income = getattr(tax_return, "total_income", 0)
                context["income_bracket"] = self._amount_to_bracket(total_income)

        # Deduction categories
        if hasattr(tax_return, "deductions"):
            ded = tax_return.deductions
            context["uses_itemized"] = getattr(ded, "uses_itemized", False)
            context["has_mortgage"] = getattr(ded, "mortgage_interest", 0) > 0
            context["has_charity"] = getattr(ded, "charitable_cash", 0) > 0

        return context

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name indicates sensitive data."""
        return (
            field_name in self.sensitive_fields or
            any(sensitive in field_name for sensitive in self.sensitive_fields)
        )

    def _redact_email(self, match: re.Match) -> str:
        """Partially redact email addresses."""
        email = match.group(0)
        parts = email.split("@")
        if len(parts) == 2:
            local = parts[0]
            domain = parts[1]
            if len(local) > 2:
                redacted_local = local[0] + "*" * (len(local) - 2) + local[-1]
            else:
                redacted_local = "*" * len(local)
            return f"{redacted_local}@{domain}"
        return "[EMAIL-REDACTED]"

    def _age_to_range(self, age: int) -> str:
        """Convert age to a range category."""
        if age < 25:
            return "under_25"
        elif age < 35:
            return "25-34"
        elif age < 50:
            return "35-49"
        elif age < 65:
            return "50-64"
        else:
            return "65_plus"

    def _amount_to_bracket(self, amount: float) -> str:
        """Convert dollar amount to income bracket."""
        if amount < 25000:
            return "under_25k"
        elif amount < 50000:
            return "25k-50k"
        elif amount < 100000:
            return "50k-100k"
        elif amount < 200000:
            return "100k-200k"
        elif amount < 500000:
            return "200k-500k"
        else:
            return "500k_plus"


# Singleton instance
_sanitizer: Optional[DataSanitizer] = None


def get_sanitizer() -> DataSanitizer:
    """Get the singleton sanitizer instance."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = DataSanitizer()
    return _sanitizer


def sanitize_for_logging(data: Any, context: str = "") -> str:
    """Convenience function for logging sanitization."""
    return get_sanitizer().sanitize_for_logging(data, context)


def sanitize_for_api(data: Dict[str, Any], allowed_fields: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Convenience function for API sanitization."""
    return get_sanitizer().sanitize_for_external_api(data, allowed_fields)


def create_safe_context(tax_return: Any, include_amounts: bool = False) -> Dict[str, Any]:
    """Convenience function to create safe AI context."""
    return get_sanitizer().create_analysis_context(tax_return, include_amounts)
