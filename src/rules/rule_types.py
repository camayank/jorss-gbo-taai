"""
Rule type definitions.

Provides enums and dataclasses for rule definitions.
"""

from enum import Enum


class RuleCategory(str, Enum):
    """Categories of tax rules."""
    INCOME = "income"
    DEDUCTION = "deduction"
    CREDIT = "credit"
    FILING_STATUS = "filing_status"
    SELF_EMPLOYMENT = "self_employment"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    AMT = "amt"
    NIIT = "niit"
    ESTIMATED_TAX = "estimated_tax"
    PENALTY = "penalty"
    STATE = "state"
    DEPENDENT = "dependent"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    BUSINESS = "business"
    REAL_ESTATE = "real_estate"
    CHARITABLE = "charitable"
    VALIDATION = "validation"
    ELIGIBILITY = "eligibility"


class RuleSeverity(str, Enum):
    """Severity levels for rule violations."""
    CRITICAL = "critical"      # Must be fixed, blocks filing
    ERROR = "error"            # Should be fixed, may cause issues
    WARNING = "warning"        # Should review, but not blocking
    INFO = "info"              # Informational, optimization opportunity
    SUGGESTION = "suggestion"  # AI-generated suggestion


class RuleType(str, Enum):
    """Types of rules."""
    VALIDATION = "validation"      # Data validation rules
    CALCULATION = "calculation"    # Tax calculation rules
    ELIGIBILITY = "eligibility"    # Credit/deduction eligibility
    PHASEOUT = "phaseout"          # Phase-out rules
    LIMIT = "limit"                # Contribution/deduction limits
    THRESHOLD = "threshold"        # Income thresholds
    RECOMMENDATION = "recommendation"  # Tax optimization recommendations
    COMPLIANCE = "compliance"      # IRS compliance rules
