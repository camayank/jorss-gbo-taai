"""Runtime invariant guards for tax calculations.

Validates that calculation results satisfy fundamental tax law invariants.
These checks run after every calculation and flag violations that indicate
bugs in the calculator or recommendation engine.

Usage:
    from validation.invariant_checker import InvariantChecker

    result = calculator.calculate_complete_return(tax_return)
    violations = InvariantChecker.check(tax_return)
    if violations:
        logger.critical(f"INVARIANT VIOLATIONS: {violations}")
        # Fall back to safe output
"""

import logging
import math
import re
from typing import List, Optional

from models.tax_return import TaxReturn

logger = logging.getLogger(__name__)

# 2025 standard deduction amounts (IRS Rev. Proc. 2024-40)
STANDARD_DEDUCTIONS_2025 = {
    "single": 15000,
    "married_joint": 30000,
    "married_separate": 15000,
    "head_of_household": 22500,
    "qualifying_widow": 30000,
}

# Maximum marginal rates for sanity checks
MAX_FEDERAL_RATE = 0.37
MAX_SE_TAX_RATE = 0.153
MAX_NIIT_RATE = 0.038
MAX_COMBINED_RATE = MAX_FEDERAL_RATE + MAX_SE_TAX_RATE + MAX_NIIT_RATE  # ~56.1%


class InvariantViolation:
    """A single invariant violation."""

    def __init__(self, code: str, message: str, severity: str = "error"):
        self.code = code
        self.message = message
        self.severity = severity  # "error", "warning"

    def __repr__(self):
        return f"InvariantViolation({self.code}: {self.message})"

    def to_dict(self):
        return {"code": self.code, "message": self.message, "severity": self.severity}


class InvariantChecker:
    """Runtime guards that validate tax calculation invariants."""

    @staticmethod
    def check(tax_return: TaxReturn) -> List[InvariantViolation]:
        """Run all invariant checks on a calculated TaxReturn.

        Args:
            tax_return: A TaxReturn that has been through calculate_complete_return()

        Returns:
            List of InvariantViolation objects (empty = all good)
        """
        violations = []

        # Only check if calculation has been performed
        if tax_return.adjusted_gross_income is None:
            return violations

        violations.extend(InvariantChecker._check_taxable_income(tax_return))
        violations.extend(InvariantChecker._check_effective_rate(tax_return))
        violations.extend(InvariantChecker._check_tax_does_not_exceed_income(tax_return))
        violations.extend(InvariantChecker._check_agi_is_finite(tax_return))
        violations.extend(InvariantChecker._check_state_tax(tax_return))

        if violations:
            logger.warning(
                "Invariant violations detected: %s",
                [v.to_dict() for v in violations]
            )

        return violations

    @staticmethod
    def check_ai_narrative(
        narrative: str,
        computed_values: dict,
        tolerance: float = 1.0,
    ) -> List[InvariantViolation]:
        """Validate that AI narrative doesn't contain numbers different from engine.

        Args:
            narrative: The AI-generated text
            computed_values: Dict of engine-computed values (name -> number)
            tolerance: Maximum allowed difference for dollar amounts

        Returns:
            List of violations if AI invented numbers
        """
        violations = []
        if not narrative:
            return violations

        # Extract dollar amounts from narrative
        dollar_pattern = r'\$[\d,]+(?:\.\d{2})?'
        matches = re.findall(dollar_pattern, narrative)

        engine_amounts = set()
        for val in computed_values.values():
            if isinstance(val, (int, float)) and math.isfinite(val):
                engine_amounts.add(round(abs(val), 2))
                engine_amounts.add(round(abs(val)))  # Also check without cents

        for match in matches:
            # Parse the dollar amount
            amount_str = match.replace('$', '').replace(',', '')
            try:
                amount = float(amount_str)
            except ValueError:
                continue

            # Check if this amount exists in engine output (within tolerance)
            found = any(
                abs(amount - eng) <= tolerance
                for eng in engine_amounts
            )

            if not found and amount > 100:  # Only flag significant amounts
                violations.append(InvariantViolation(
                    code="AI_INVENTED_NUMBER",
                    message=f"AI narrative contains ${amount:,.2f} which doesn't match any engine-computed value",
                    severity="warning",
                ))

        return violations

    @staticmethod
    def _check_taxable_income(tax_return: TaxReturn) -> List[InvariantViolation]:
        """Taxable income must be >= 0 (floored at zero by tax law)."""
        violations = []
        if tax_return.taxable_income is not None and tax_return.taxable_income < 0:
            violations.append(InvariantViolation(
                code="NEGATIVE_TAXABLE_INCOME",
                message=f"Taxable income is ${tax_return.taxable_income:,.2f} (must be >= 0)",
            ))
        return violations

    @staticmethod
    def _check_effective_rate(tax_return: TaxReturn) -> List[InvariantViolation]:
        """Effective tax rate must be within reasonable bounds."""
        violations = []

        agi = tax_return.adjusted_gross_income
        tax = tax_return.tax_liability

        if agi is not None and tax is not None and agi > 0:
            effective_rate = tax / agi

            # Tax can be negative (refundable credits), but effective rate
            # should not exceed max combined rate
            if effective_rate > MAX_COMBINED_RATE:
                violations.append(InvariantViolation(
                    code="EXCESSIVE_EFFECTIVE_RATE",
                    message=(
                        f"Effective rate {effective_rate:.1%} exceeds maximum "
                        f"combined rate {MAX_COMBINED_RATE:.1%} "
                        f"(tax=${tax:,.2f}, AGI=${agi:,.2f})"
                    ),
                ))

        return violations

    @staticmethod
    def _check_tax_does_not_exceed_income(tax_return: TaxReturn) -> List[InvariantViolation]:
        """Pre-credit tax should not exceed total income."""
        violations = []

        total_income = tax_return.income.get_total_income() if tax_return.income else 0
        tax = tax_return.tax_liability

        if tax is not None and total_income > 0:
            # Tax (before refundable credits) shouldn't exceed income
            # Note: tax_liability may include negative refundable credits,
            # so we only check the upper bound
            if tax > total_income * 1.1:  # 10% margin for SE tax + NIIT
                violations.append(InvariantViolation(
                    code="TAX_EXCEEDS_INCOME",
                    message=(
                        f"Tax ${tax:,.2f} exceeds income ${total_income:,.2f} by "
                        f"{((tax/total_income - 1) * 100):.0f}%"
                    ),
                    severity="warning",
                ))

        return violations

    @staticmethod
    def _check_agi_is_finite(tax_return: TaxReturn) -> List[InvariantViolation]:
        """AGI and all calculated values must be finite numbers."""
        violations = []

        checks = [
            ("AGI", tax_return.adjusted_gross_income),
            ("taxable_income", tax_return.taxable_income),
            ("tax_liability", tax_return.tax_liability),
            ("combined_tax_liability", tax_return.combined_tax_liability),
        ]

        for name, value in checks:
            if value is not None and not math.isfinite(value):
                violations.append(InvariantViolation(
                    code="NON_FINITE_VALUE",
                    message=f"{name} is {value} (must be finite)",
                ))

        return violations

    @staticmethod
    def _check_state_tax(tax_return: TaxReturn) -> List[InvariantViolation]:
        """State tax must be non-negative if present."""
        violations = []

        if tax_return.state_tax_liability is not None and tax_return.state_tax_liability < 0:
            violations.append(InvariantViolation(
                code="NEGATIVE_STATE_TAX",
                message=f"State tax is ${tax_return.state_tax_liability:,.2f} (must be >= 0)",
            ))

        return violations
