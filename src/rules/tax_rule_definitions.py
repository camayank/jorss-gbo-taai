"""
Tax Rule Type Definitions.

This module provides the TaxRule dataclass and related enums used by both
the tax_rules_engine and the individual rule modules. This separates the
type definitions from the engine to avoid circular imports.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class RuleCategory(Enum):
    """Categories of tax rules."""
    INCOME = "income"
    DEDUCTION = "deduction"
    CREDIT = "credit"
    FILING_STATUS = "filing_status"
    SELF_EMPLOYMENT = "self_employment"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    BUSINESS = "business"
    CHARITABLE = "charitable"
    FAMILY = "family"
    STATE_TAX = "state_tax"
    INTERNATIONAL = "international"
    AMT = "amt"
    PENALTY = "penalty"
    TIMING = "timing"
    DOCUMENTATION = "documentation"
    # New categories for comprehensive tax coverage (381 new rules)
    VIRTUAL_CURRENCY = "virtual_currency"
    HOUSEHOLD_EMPLOYMENT = "household_employment"
    K1_TRUST = "k1_trust"
    CASUALTY_LOSS = "casualty_loss"
    ALIMONY = "alimony"


class RuleSeverity(Enum):
    """Severity/importance of rule violations."""
    CRITICAL = "critical"  # Must fix - will cause rejection
    HIGH = "high"  # Significant tax impact
    MEDIUM = "medium"  # Moderate tax impact
    LOW = "low"  # Minor optimization
    INFO = "info"  # Informational


@dataclass
class TaxRule:
    """Individual tax rule definition."""
    rule_id: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    irs_reference: str  # Publication, form, or IRC section
    tax_year: int = 2025

    # Rule parameters
    threshold: Optional[float] = None
    limit: Optional[float] = None
    rate: Optional[float] = None
    phase_out_start: Optional[float] = None
    phase_out_end: Optional[float] = None

    # Filing status specific values
    thresholds_by_status: Optional[Dict[str, float]] = None
    limits_by_status: Optional[Dict[str, float]] = None

    # Conditions
    applies_to: Optional[List[str]] = None  # Filing statuses
    requires: Optional[List[str]] = None  # Required conditions
    excludes: Optional[List[str]] = None  # Exclusion conditions

    # Action
    recommendation: Optional[str] = None
    potential_savings: Optional[str] = None
