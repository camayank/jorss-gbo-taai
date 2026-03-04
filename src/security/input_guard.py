"""
Input Guard — Prompt Injection Protection & PII Sanitization

Checks user input BEFORE it reaches AI providers.
Blocks prompt injection attempts. Sanitizes PII.

Usage:
    guard = InputGuard()
    result = guard.check("some user input")
    if not result.is_safe:
        return "I can't process that. Please ask a tax question."
    sanitized = guard.sanitize("my SSN is 123-45-6789")
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class InputGuardResult:
    is_safe: bool
    violation_type: Optional[str] = None
    matched_pattern: Optional[str] = None


# Patterns that indicate prompt injection.
_INJECTION_PATTERNS = [
    (re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instruction"), "injection"),
    (re.compile(r"(?i)what\s+(is|are)\s+your\s+system\s+prompt"), "extraction"),
    (re.compile(r"(?i)you\s+are\s+now\s+a\s+different"), "role_override"),
    (re.compile(r"(?i)forget\s+(all\s+)?your\s+instruction"), "injection"),
    (re.compile(r"(?i)override\s+(all\s+)?your\s+rule"), "injection"),
    (re.compile(r"(?i)repeat\s+(your\s+)?system\s+message"), "extraction"),
    (re.compile(r"(?i)disregard\s+(all\s+)?prior\s+instruction"), "injection"),
    (re.compile(r"(?i)act\s+as\s+if\s+you\s+have\s+no\s+restriction"), "role_override"),
]

# PII patterns for sanitization
_PII_PATTERNS = {
    "ssn": (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "[SSN-REDACTED]"),
    "ein": (re.compile(r"\b\d{2}[-\s]?\d{7}\b"), "[EIN-REDACTED]"),
    "email": (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "[EMAIL-REDACTED]",
    ),
    "credit_card": (
        re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        "[CARD-REDACTED]",
    ),
}


class InputGuard:
    """Checks user input for prompt injection and sanitizes PII."""

    def check(self, text: str) -> InputGuardResult:
        """Check if input is safe from prompt injection."""
        if not text or not text.strip():
            return InputGuardResult(is_safe=True)

        for pattern, violation_type in _INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    f"[InputGuard] Prompt injection detected: "
                    f"type={violation_type}, pattern={pattern.pattern}"
                )
                return InputGuardResult(
                    is_safe=False,
                    violation_type=violation_type,
                    matched_pattern=pattern.pattern,
                )

        return InputGuardResult(is_safe=True)

    def sanitize(self, text: str) -> str:
        """Remove PII from text before sending to AI."""
        result = text
        for _name, (pattern, replacement) in _PII_PATTERNS.items():
            result = pattern.sub(replacement, result)
        return result

    def check_and_sanitize(self, text: str) -> Tuple[InputGuardResult, str]:
        """Check for injection AND sanitize PII in one call."""
        result = self.check(text)
        if not result.is_safe:
            return result, text
        return result, self.sanitize(text)
