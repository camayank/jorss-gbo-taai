from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from models.tax_return import TaxReturn


@dataclass
class ValidationIssue:
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


class TaxReturnValidator:
    def validate(self, tax_return: TaxReturn) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        if tax_return.tax_year <= 0:
            issues.append(ValidationIssue("tax_year", "Tax year must be a positive integer."))

        if not tax_return.taxpayer or not tax_return.taxpayer.filing_status:
            issues.append(ValidationIssue("taxpayer.filing_status", "Filing status is required."))

        # Income sanity checks
        income = tax_return.income
        if income.self_employment_expenses > income.self_employment_income:
            issues.append(
                ValidationIssue(
                    "income.self_employment_expenses",
                    "Self-employment expenses exceed self-employment income; confirm this is correct.",
                    severity="warning",
                )
            )

        if income.qualified_dividends > income.dividend_income:
            issues.append(
                ValidationIssue(
                    "income.qualified_dividends",
                    "Qualified dividends cannot exceed total dividend income.",
                )
            )

        if income.taxable_social_security > income.social_security_benefits:
            issues.append(
                ValidationIssue(
                    "income.taxable_social_security",
                    "Taxable Social Security cannot exceed total Social Security benefits.",
                )
            )

        return issues

