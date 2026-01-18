"""
Tax Return Adapter for CPA Panel

Provides a clean interface to access tax return data from the core platform
without tight coupling. Handles data transformation and error isolation.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaxReturnSummary:
    """Simplified tax return summary for CPA panel use."""
    session_id: str
    tax_year: int = 2025
    filing_status: str = "single"

    # Taxpayer info
    taxpayer_name: str = ""
    taxpayer_ssn_last4: str = ""

    # Income summary
    total_income: float = 0
    wages: float = 0
    interest_income: float = 0
    dividend_income: float = 0
    business_income: float = 0
    capital_gains: float = 0
    other_income: float = 0

    # Deduction summary
    total_deductions: float = 0
    standard_deduction: float = 0
    itemized_deductions: float = 0
    using_standard_deduction: bool = True

    # Tax calculation
    adjusted_gross_income: float = 0
    taxable_income: float = 0
    tax_liability: float = 0
    total_credits: float = 0
    total_payments: float = 0
    refund_or_owed: float = 0

    # Rates
    effective_rate: float = 0
    marginal_rate: float = 0

    # State
    state: str = ""
    state_tax: float = 0

    # Metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)
    has_schedule_c: bool = False
    has_schedule_e: bool = False
    has_schedule_d: bool = False
    has_foreign_accounts: bool = False
    has_virtual_currency: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "taxpayer_name": self.taxpayer_name,
            "income": {
                "total": round(self.total_income, 2),
                "wages": round(self.wages, 2),
                "interest": round(self.interest_income, 2),
                "dividends": round(self.dividend_income, 2),
                "business": round(self.business_income, 2),
                "capital_gains": round(self.capital_gains, 2),
                "other": round(self.other_income, 2),
            },
            "deductions": {
                "total": round(self.total_deductions, 2),
                "standard": round(self.standard_deduction, 2),
                "itemized": round(self.itemized_deductions, 2),
                "using_standard": self.using_standard_deduction,
            },
            "tax_calculation": {
                "agi": round(self.adjusted_gross_income, 2),
                "taxable_income": round(self.taxable_income, 2),
                "tax_liability": round(self.tax_liability, 2),
                "total_credits": round(self.total_credits, 2),
                "total_payments": round(self.total_payments, 2),
                "refund_or_owed": round(self.refund_or_owed, 2),
            },
            "rates": {
                "effective_rate": round(self.effective_rate, 4),
                "marginal_rate": round(self.marginal_rate, 4),
            },
            "state": {
                "code": self.state,
                "tax": round(self.state_tax, 2),
            },
            "schedules": {
                "has_schedule_c": self.has_schedule_c,
                "has_schedule_e": self.has_schedule_e,
                "has_schedule_d": self.has_schedule_d,
            },
            "flags": {
                "has_foreign_accounts": self.has_foreign_accounts,
                "has_virtual_currency": self.has_virtual_currency,
            },
            "last_updated": self.last_updated.isoformat(),
        }


class TaxReturnAdapter:
    """
    Adapter for accessing tax return data from the core platform.

    This provides isolation between the CPA panel and core platform,
    allowing the CPA panel to function even if core platform APIs change.
    """

    def __init__(self):
        """Initialize the adapter."""
        self._cache: Dict[str, TaxReturnSummary] = {}

    def get_tax_return(self, session_id: str) -> Optional[Any]:
        """
        Get the raw tax return object from the core platform.

        Args:
            session_id: Session identifier

        Returns:
            TaxReturn object or None if not found
        """
        try:
            # Try to import from web.app (core platform)
            from web.app import _get_tax_return_for_session
            return _get_tax_return_for_session(session_id)
        except ImportError:
            logger.warning("Could not import from web.app")
            return None
        except Exception as e:
            logger.error(f"Error getting tax return: {e}")
            return None

    def get_summary(self, session_id: str) -> Optional[TaxReturnSummary]:
        """
        Get a summary of the tax return for CPA panel use.

        Args:
            session_id: Session identifier

        Returns:
            TaxReturnSummary or None if not found
        """
        tax_return = self.get_tax_return(session_id)

        if not tax_return:
            return None

        return self._convert_to_summary(session_id, tax_return)

    def _convert_to_summary(self, session_id: str, tax_return: Any) -> TaxReturnSummary:
        """
        Convert a TaxReturn object to a TaxReturnSummary.

        Args:
            session_id: Session identifier
            tax_return: Core platform TaxReturn object

        Returns:
            TaxReturnSummary
        """
        summary = TaxReturnSummary(session_id=session_id)

        try:
            # Basic info
            summary.tax_year = getattr(tax_return, 'tax_year', 2025)
            summary.filing_status = getattr(tax_return, 'filing_status', 'single')

            # Taxpayer info
            taxpayer = getattr(tax_return, 'taxpayer', None)
            if taxpayer:
                first = getattr(taxpayer, 'first_name', '') or ''
                last = getattr(taxpayer, 'last_name', '') or ''
                summary.taxpayer_name = f"{first} {last}".strip()
                ssn = getattr(taxpayer, 'ssn', '') or ''
                summary.taxpayer_ssn_last4 = ssn[-4:] if len(ssn) >= 4 else ''

            # Income
            income = getattr(tax_return, 'income', None)
            if income:
                summary.wages = float(getattr(income, 'wages', 0) or 0)
                summary.interest_income = float(getattr(income, 'interest_income', 0) or 0)
                summary.dividend_income = float(getattr(income, 'dividend_income', 0) or 0)
                summary.business_income = float(getattr(income, 'business_income', 0) or 0)
                summary.capital_gains = float(getattr(income, 'capital_gains', 0) or 0)
                summary.other_income = float(getattr(income, 'other_income', 0) or 0)

                # Try to get total income
                if hasattr(income, 'get_total_income'):
                    summary.total_income = float(income.get_total_income())
                else:
                    summary.total_income = (
                        summary.wages + summary.interest_income +
                        summary.dividend_income + summary.business_income +
                        summary.capital_gains + summary.other_income
                    )

            # Deductions
            deductions = getattr(tax_return, 'deductions', None)
            if deductions:
                summary.itemized_deductions = float(getattr(deductions, 'total_itemized', 0) or 0)
                if hasattr(deductions, 'get_total_deductions'):
                    summary.total_deductions = float(deductions.get_total_deductions())
                else:
                    summary.total_deductions = summary.itemized_deductions

            # Standard deduction (based on filing status)
            standard_deductions = {
                'single': 15000,
                'married_joint': 30000,
                'married_separate': 15000,
                'head_of_household': 22500,
            }
            summary.standard_deduction = standard_deductions.get(summary.filing_status, 15000)
            summary.using_standard_deduction = summary.standard_deduction > summary.itemized_deductions

            if summary.using_standard_deduction:
                summary.total_deductions = summary.standard_deduction

            # Tax calculations
            summary.adjusted_gross_income = float(getattr(tax_return, 'adjusted_gross_income', 0) or 0)
            summary.taxable_income = float(getattr(tax_return, 'taxable_income', 0) or 0)
            summary.tax_liability = float(getattr(tax_return, 'tax_liability', 0) or 0)
            summary.total_credits = float(getattr(tax_return, 'total_credits', 0) or 0)
            summary.total_payments = float(getattr(tax_return, 'total_payments', 0) or 0)
            summary.refund_or_owed = float(getattr(tax_return, 'refund_or_owed', 0) or 0)

            # Calculate rates
            if summary.adjusted_gross_income > 0:
                summary.effective_rate = summary.tax_liability / summary.adjusted_gross_income
            summary.marginal_rate = self._get_marginal_rate(summary.taxable_income, summary.filing_status)

            # State
            summary.state = getattr(tax_return, 'state', '') or ''
            state_tax_info = getattr(tax_return, 'state_tax', None)
            if state_tax_info:
                summary.state_tax = float(getattr(state_tax_info, 'state_tax_liability', 0) or 0)

            # Schedule flags
            summary.has_schedule_c = bool(getattr(tax_return, 'schedule_c', None))
            summary.has_schedule_e = bool(getattr(tax_return, 'schedule_e', None))
            summary.has_schedule_d = summary.capital_gains != 0

            # Special flags
            summary.has_virtual_currency = bool(getattr(tax_return, 'virtual_currency_transactions', None))
            summary.has_foreign_accounts = bool(getattr(tax_return, 'foreign_accounts', None))

        except Exception as e:
            logger.error(f"Error converting tax return to summary: {e}")

        return summary

    def _get_marginal_rate(self, taxable_income: float, filing_status: str = "single") -> float:
        """Get marginal tax rate for taxable income."""
        # 2025 single filer brackets (simplified)
        brackets = [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37),
        ]

        for threshold, rate in brackets:
            if taxable_income <= threshold:
                return rate
        return 0.37

    def exists(self, session_id: str) -> bool:
        """Check if a tax return exists for the session."""
        return self.get_tax_return(session_id) is not None

    def get_income_breakdown(self, session_id: str) -> Dict[str, float]:
        """Get income breakdown for the session."""
        summary = self.get_summary(session_id)
        if not summary:
            return {}

        return {
            "wages": summary.wages,
            "interest_income": summary.interest_income,
            "dividend_income": summary.dividend_income,
            "business_income": summary.business_income,
            "capital_gains": summary.capital_gains,
            "other_income": summary.other_income,
            "total": summary.total_income,
        }

    def get_deduction_breakdown(self, session_id: str) -> Dict[str, Any]:
        """Get deduction breakdown for the session."""
        summary = self.get_summary(session_id)
        if not summary:
            return {}

        return {
            "standard_deduction": summary.standard_deduction,
            "itemized_deductions": summary.itemized_deductions,
            "using_standard": summary.using_standard_deduction,
            "total": summary.total_deductions,
        }
