"""
Tax Return Adapter for CPA Panel

Provides a clean interface to access tax return data from the core platform
without tight coupling. Handles data transformation and error isolation.

Now supports reading from the new database tables as a fallback.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import logging
import sqlite3
import json
import os

logger = logging.getLogger(__name__)

# Database path for new tax_returns table
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "database", "jorss_gbo.db")


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


# =============================================================================
# COMPATIBILITY WRAPPERS FOR RECOMMENDATION ENGINE
# =============================================================================

class FilingStatusEnum:
    """Mock filing status enum for recommendation engine compatibility."""
    def __init__(self, value: str):
        self.value = value

class TaxpayerCompat:
    """Compatibility wrapper for taxpayer data."""
    def __init__(self, filing_status: str, client_name: str = ""):
        self.filing_status = FilingStatusEnum(filing_status)
        self.is_over_65 = False
        self.is_blind = False
        self.name = client_name
        self.ssn = "***-**-****"  # Masked for security
        self.date_of_birth = None
        self.occupation = ""
        self.can_be_dependent = False
        self.first_name = client_name.split()[0] if client_name else ""
        self.last_name = " ".join(client_name.split()[1:]) if client_name else ""

class ItemizedDeductionsCompat:
    """Compatibility wrapper for itemized deductions."""
    def __init__(self, total: float):
        self._total = total
        self.state_local_taxes = min(total * 0.3, 10000)  # SALT cap
        self.mortgage_interest = total * 0.4
        self.charitable = total * 0.2
        self.medical = total * 0.1

    def get_total_itemized(self, agi: float = 0) -> float:
        """Return total itemized deductions."""
        return self._total


class DeductionsCompat:
    """Compatibility wrapper for deductions data."""
    def __init__(self, db_return: 'DatabaseTaxReturn'):
        # Core deductions
        self.ira_contributions = 0
        self.hsa_contributions = 0
        self.itemized = ItemizedDeductionsCompat(db_return.total_itemized)
        self.standard = db_return.standard_deduction
        self._filing_status = db_return.filing_status
        self._db_return = db_return
        self.use_standard_deduction = db_return.uses_standard_deduction

        # Additional deduction attributes that may be accessed
        self.charitable_contributions = 0
        self.mortgage_interest = 0
        self.state_local_taxes = min(db_return.total_itemized * 0.3, 10000)
        self.student_loan_interest = 0
        self.educator_expenses = 0
        self.moving_expenses = 0
        self.self_employment_tax_deduction = 0
        self.alimony_paid = 0
        self.early_withdrawal_penalty = 0
        self.qbi_deduction = db_return.qbi_deduction

        # Parse adjustments JSON if available
        if hasattr(db_return, '_adjustments_dict') and db_return._adjustments_dict:
            adj = db_return._adjustments_dict
            self.ira_contributions = adj.get('ira_contribution', adj.get('ira', 0))
            self.hsa_contributions = adj.get('hsa_contribution', adj.get('hsa', adj.get('hsa_contribution', 0)))
            self._401k_contributions = adj.get('401k_contribution', adj.get('401k', 0))
            self.student_loan_interest = adj.get('student_loan_interest', 0)
            self.self_employment_tax_deduction = adj.get('se_tax_deduction', 0)

    def _get_standard_deduction(self, filing_status: str, is_over_65: bool = False, is_blind: bool = False) -> float:
        """Return standard deduction amount."""
        base = {
            'single': 14600,
            'married_filing_jointly': 29200,
            'married_filing_separately': 14600,
            'head_of_household': 21900,
        }.get(filing_status, 14600)
        if is_over_65:
            base += 1950 if filing_status == 'single' else 1550
        return base

class IncomeCompat:
    """Compatibility wrapper for income data."""
    def __init__(self, db_return: 'DatabaseTaxReturn'):
        # Basic income
        self.wages = db_return.w2_income
        self.interest = 0
        self.tax_exempt_interest = 0
        self.dividends = db_return.dividend_income
        self.dividend_income = db_return.dividend_income  # Alias
        self.qualified_dividends = db_return.qualified_dividends
        self.ordinary_dividends = db_return.dividend_income - db_return.qualified_dividends
        self.capital_gains = db_return.capital_gains
        self.short_term_capital_gains = 0
        self.long_term_capital_gains = db_return.capital_gains  # Assume all are long-term
        self.business_income = db_return.self_employment_income
        self.self_employment_income = db_return.self_employment_income  # Alias
        self.rental_income = db_return.rental_income
        self.social_security = db_return.social_security_income
        self.pension = db_return.pension_income
        self.ira_distributions = db_return.rmd_income
        self.total = db_return.gross_income

        # Additional income types
        self.rsu_income = db_return.rsu_income
        self.iso_income = db_return.iso_income
        self.foreign_income = db_return.foreign_income
        self.trust_income = db_return.trust_income
        self.crypto_gains = db_return.crypto_gains
        self.unemployment = 0
        self.alimony_received = 0
        self.gambling_winnings = 0
        self.other_income = 0

        # Payments/withholding (often accessed via income object)
        self.federal_withholding = db_return.federal_withheld
        self.state_withholding = db_return.state_withheld
        self.estimated_tax_payments = db_return.estimated_payments


@dataclass
class DatabaseTaxReturn:
    """Tax return data loaded from src.database."""
    session_id: str
    client_id: str = ""
    tax_year: int = 2024
    filing_status: str = "single"

    # Income
    w2_income: float = 0
    self_employment_income: float = 0
    dividend_income: float = 0
    qualified_dividends: float = 0
    capital_gains: float = 0
    rental_income: float = 0
    social_security_income: float = 0
    pension_income: float = 0
    rmd_income: float = 0
    rsu_income: float = 0
    iso_income: float = 0
    foreign_income: float = 0
    trust_income: float = 0
    crypto_gains: float = 0
    gross_income: float = 0

    # Adjustments & Deductions
    total_adjustments: float = 0
    agi: float = 0
    standard_deduction: float = 0
    total_itemized: float = 0
    uses_standard_deduction: bool = True
    deduction_amount: float = 0
    qbi_deduction: float = 0

    # Tax calculation
    taxable_income: float = 0
    federal_tax: float = 0
    self_employment_tax: float = 0
    state_tax: float = 0
    total_credits: float = 0
    total_tax: float = 0

    # Payments
    federal_withheld: float = 0
    state_withheld: float = 0
    estimated_payments: float = 0
    total_payments: float = 0

    # Result
    balance_due: float = 0
    refund_amount: float = 0

    # Flags
    has_amt_exposure: bool = False
    has_foreign_reporting: bool = False
    is_multi_state: bool = False
    has_crypto: bool = False
    has_rental_properties: bool = False
    has_business: bool = False

    # Complexity
    complexity_tier: str = "simple"

    # Internal storage for adjustments dict
    _adjustments_dict: Dict[str, Any] = field(default_factory=dict)

    @property
    def taxpayer(self) -> TaxpayerCompat:
        """Compatibility property for recommendation engine."""
        return TaxpayerCompat(self.filing_status, self.client_id)

    @property
    def deductions(self) -> DeductionsCompat:
        """Compatibility property for recommendation engine."""
        return DeductionsCompat(self)

    @property
    def income(self) -> IncomeCompat:
        """Compatibility property for recommendation engine."""
        return IncomeCompat(self)

    @property
    def adjusted_gross_income(self) -> float:
        """Compatibility property for recommendation engine."""
        return self.agi

    @property
    def tax_liability(self) -> float:
        """Compatibility property for recommendation engine."""
        return self.total_tax

    @property
    def refund_or_owed(self) -> float:
        """Compatibility property for recommendation engine."""
        return self.refund_amount - self.balance_due


class TaxReturnAdapter:
    """
    Adapter for accessing tax return data from the core platform.

    This provides isolation between the CPA panel and core platform,
    allowing the CPA panel to function even if core platform APIs change.

    Now supports reading from the new database tables as a fallback.
    """

    def __init__(self):
        """Initialize the adapter."""
        self._cache: Dict[str, TaxReturnSummary] = {}
        self._db_cache: Dict[str, DatabaseTaxReturn] = {}

    def get_tax_return(self, session_id: str) -> Optional[Any]:
        """
        Get the raw tax return object from the core platform.
        Falls back to database if core platform not available.

        Args:
            session_id: Session identifier

        Returns:
            TaxReturn object or DatabaseTaxReturn or None if not found
        """
        # First try the core platform
        try:
            from web.app import _get_tax_return_for_session
            result = _get_tax_return_for_session(session_id)
            if result:
                return result
        except ImportError:
            logger.debug("Could not import from web.app, trying database")
        except Exception as e:
            logger.debug(f"Core platform error: {e}, trying database")

        # Fallback to database
        return self._get_from_database(session_id)

    def _get_from_database(self, session_id: str) -> Optional[DatabaseTaxReturn]:
        """
        Get tax return from the new database tables.

        Args:
            session_id: Session identifier

        Returns:
            DatabaseTaxReturn or None if not found
        """
        # Check cache first
        if session_id in self._db_cache:
            return self._db_cache[session_id]

        if not os.path.exists(DB_PATH):
            logger.warning(f"Database not found: {DB_PATH}")
            return None

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM tax_returns WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            # Convert to DatabaseTaxReturn
            db_return = DatabaseTaxReturn(
                session_id=row["session_id"],
                client_id=row["client_id"] or "",
                tax_year=row["tax_year"] or 2024,
                filing_status=row["filing_status"] or "single",

                # Income
                w2_income=float(row["w2_income"] or 0),
                self_employment_income=float(row["self_employment_income"] or 0),
                dividend_income=float(row["dividend_income"] or 0),
                qualified_dividends=float(row["qualified_dividends"] or 0),
                capital_gains=float(row["capital_gains"] or 0),
                rental_income=float(row["rental_income"] or 0),
                social_security_income=float(row["social_security_income"] or 0),
                pension_income=float(row["pension_income"] or 0),
                rmd_income=float(row["rmd_income"] or 0),
                rsu_income=float(row["rsu_income"] or 0),
                iso_income=float(row["iso_income"] or 0),
                foreign_income=float(row["foreign_income"] or 0),
                trust_income=float(row["trust_income"] or 0),
                crypto_gains=float(row["crypto_gains"] or 0),
                gross_income=float(row["gross_income"] or 0),

                # Adjustments
                total_adjustments=float(row["total_adjustments"] or 0),
                agi=float(row["agi"] or 0),
                standard_deduction=float(row["standard_deduction"] or 0),
                total_itemized=float(row["total_itemized"] or 0),
                uses_standard_deduction=bool(row["uses_standard_deduction"]),
                deduction_amount=float(row["deduction_amount"] or 0),
                qbi_deduction=float(row["qbi_deduction"] or 0),

                # Tax calculation
                taxable_income=float(row["taxable_income"] or 0),
                federal_tax=float(row["federal_tax"] or 0),
                self_employment_tax=float(row["self_employment_tax"] or 0),
                state_tax=float(row["state_tax"] or 0),
                total_credits=float(row["total_credits"] or 0),
                total_tax=float(row["total_tax"] or 0),

                # Payments
                federal_withheld=float(row["federal_withheld"] or 0),
                state_withheld=float(row["state_withheld"] or 0),
                estimated_payments=float(row["estimated_payments"] or 0),
                total_payments=float(row["total_payments"] or 0),

                # Result
                balance_due=float(row["balance_due"] or 0),
                refund_amount=float(row["refund_amount"] or 0),

                # Flags
                has_amt_exposure=bool(row["has_amt_exposure"]),
                has_foreign_reporting=bool(row["has_foreign_reporting"]),
                is_multi_state=bool(row["is_multi_state"]),
                has_crypto=bool(row["has_crypto"]),
                has_rental_properties=bool(row["has_rental_properties"]),
                has_business=bool(row["has_business"]),

                # Complexity
                complexity_tier=row["complexity_tier"] or "simple",
            )

            # Parse adjustments JSON if available
            try:
                adjustments_json = row["adjustments_json"] if "adjustments_json" in row.keys() else "{}"
                if isinstance(adjustments_json, str):
                    db_return._adjustments_dict = json.loads(adjustments_json)
                elif isinstance(adjustments_json, dict):
                    db_return._adjustments_dict = adjustments_json
                else:
                    db_return._adjustments_dict = {}
            except (json.JSONDecodeError, TypeError, KeyError):
                db_return._adjustments_dict = {}

            # Cache the result
            self._db_cache[session_id] = db_return
            return db_return

        except Exception as e:
            logger.error(f"Error reading from database: {e}")
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
            tax_return: Core platform TaxReturn object or DatabaseTaxReturn

        Returns:
            TaxReturnSummary
        """
        # Handle DatabaseTaxReturn separately
        if isinstance(tax_return, DatabaseTaxReturn):
            return self._convert_db_return_to_summary(session_id, tax_return)

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

    def _convert_db_return_to_summary(self, session_id: str, db_return: DatabaseTaxReturn) -> TaxReturnSummary:
        """
        Convert a DatabaseTaxReturn to TaxReturnSummary.

        Args:
            session_id: Session identifier
            db_return: DatabaseTaxReturn from new database

        Returns:
            TaxReturnSummary
        """
        # Calculate total income from components
        total_income = (
            db_return.w2_income +
            db_return.self_employment_income +
            db_return.dividend_income +
            db_return.capital_gains +
            db_return.rental_income +
            db_return.social_security_income +
            db_return.pension_income +
            db_return.rmd_income +
            db_return.rsu_income +
            db_return.iso_income +
            db_return.foreign_income +
            db_return.trust_income +
            db_return.crypto_gains
        )

        # Use gross_income if available
        if db_return.gross_income > 0:
            total_income = db_return.gross_income

        # Calculate refund/owed
        refund_or_owed = db_return.refund_amount - db_return.balance_due

        # Calculate effective rate
        effective_rate = 0
        if db_return.agi > 0:
            effective_rate = db_return.total_tax / db_return.agi

        summary = TaxReturnSummary(
            session_id=session_id,
            tax_year=db_return.tax_year,
            filing_status=db_return.filing_status,

            # Income
            total_income=total_income,
            wages=db_return.w2_income,
            interest_income=0,  # Not tracked separately in database
            dividend_income=db_return.dividend_income,
            business_income=db_return.self_employment_income,
            capital_gains=db_return.capital_gains + db_return.crypto_gains,
            other_income=(
                db_return.rental_income +
                db_return.social_security_income +
                db_return.pension_income +
                db_return.rmd_income +
                db_return.rsu_income +
                db_return.iso_income +
                db_return.foreign_income +
                db_return.trust_income
            ),

            # Deductions
            total_deductions=db_return.deduction_amount,
            standard_deduction=db_return.standard_deduction,
            itemized_deductions=db_return.total_itemized,
            using_standard_deduction=db_return.uses_standard_deduction,

            # Tax calculation
            adjusted_gross_income=db_return.agi,
            taxable_income=db_return.taxable_income,
            tax_liability=db_return.total_tax,
            total_credits=db_return.total_credits,
            total_payments=db_return.total_payments,
            refund_or_owed=refund_or_owed,

            # Rates
            effective_rate=effective_rate,
            marginal_rate=self._get_marginal_rate(db_return.taxable_income, db_return.filing_status),

            # State
            state="",  # Not tracked in database
            state_tax=db_return.state_tax,

            # Schedule flags
            has_schedule_c=db_return.has_business,
            has_schedule_e=db_return.has_rental_properties,
            has_schedule_d=db_return.capital_gains > 0 or db_return.crypto_gains > 0,

            # Special flags
            has_foreign_accounts=db_return.has_foreign_reporting,
            has_virtual_currency=db_return.has_crypto,
        )

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

    def get_optimizer_compatible_return(self, session_id: str) -> Optional["TaxReturnWrapper"]:
        """
        Get a tax return wrapped for optimizer compatibility.

        This provides a wrapper that makes DatabaseTaxReturn compatible with
        the optimizer modules (credit_optimizer, deduction_analyzer, etc.).

        Args:
            session_id: Session identifier

        Returns:
            TaxReturnWrapper or core TaxReturn or None
        """
        tax_return = self.get_tax_return(session_id)

        if tax_return is None:
            return None

        # If it's already a core platform TaxReturn, return as-is
        if not isinstance(tax_return, DatabaseTaxReturn):
            return tax_return

        # Wrap DatabaseTaxReturn for optimizer compatibility
        return TaxReturnWrapper(tax_return)


# =============================================================================
# WRAPPER CLASSES FOR OPTIMIZER COMPATIBILITY
# =============================================================================

class FilingStatusEnum:
    """Minimal filing status enum wrapper."""
    def __init__(self, value: str):
        self._value = value

    @property
    def value(self) -> str:
        return self._value


class TaxpayerWrapper:
    """Wrapper to make DatabaseTaxReturn taxpayer data look like TaxpayerInfo."""

    def __init__(self, db_return: DatabaseTaxReturn, client_name: str = ""):
        self._db = db_return
        self._client_name = client_name
        self._dependents: List[Any] = []
        self._filing_status_override: Optional[Any] = None

    @property
    def filing_status(self):
        """Return filing status (may be overridden for analysis)."""
        if self._filing_status_override is not None:
            return self._filing_status_override
        return FilingStatusEnum(self._db.filing_status)

    @filing_status.setter
    def filing_status(self, value):
        """Allow setting filing status for analysis scenarios."""
        self._filing_status_override = value

    @property
    def is_married(self) -> bool:
        """Check if filing status indicates married."""
        status = self._db.filing_status.lower()
        return "married" in status or "joint" in status

    @property
    def dependents(self) -> List[Any]:
        return self._dependents

    @property
    def first_name(self) -> str:
        parts = self._client_name.split()
        return parts[0] if parts else ""

    @property
    def last_name(self) -> str:
        parts = self._client_name.split()
        return parts[-1] if len(parts) > 1 else ""

    @property
    def name(self) -> str:
        return self._client_name

    @property
    def is_over_65(self) -> bool:
        return False  # Not tracked in database

    @property
    def is_blind(self) -> bool:
        return False  # Not tracked in database

    @property
    def state_of_residence(self) -> str:
        return ""  # Not tracked in database

    @property
    def ssn(self) -> str:
        return ""  # Not exposed


class IncomeWrapper:
    """Wrapper to make DatabaseTaxReturn income data look like Income model."""

    def __init__(self, db_return: DatabaseTaxReturn):
        self._db = db_return

    @property
    def wages(self) -> float:
        return self._db.w2_income

    @property
    def self_employment_income(self) -> float:
        return self._db.self_employment_income

    @property
    def self_employment_expenses(self) -> float:
        return 0  # Not tracked separately

    @property
    def interest_income(self) -> float:
        return 0  # Not tracked separately

    @property
    def dividend_income(self) -> float:
        return self._db.dividend_income

    @property
    def qualified_dividends(self) -> float:
        return self._db.qualified_dividends

    @property
    def long_term_capital_gains(self) -> float:
        return self._db.capital_gains

    @property
    def short_term_capital_gains(self) -> float:
        return 0  # Not tracked separately

    @property
    def capital_gains(self) -> float:
        return self._db.capital_gains

    @property
    def rental_income(self) -> float:
        return self._db.rental_income

    @property
    def social_security_benefits(self) -> float:
        return self._db.social_security_income

    @property
    def pension_income(self) -> float:
        return self._db.pension_income

    @property
    def rmd_income(self) -> float:
        return self._db.rmd_income

    @property
    def foreign_income(self) -> float:
        return self._db.foreign_income

    @property
    def crypto_gains(self) -> float:
        return self._db.crypto_gains

    @property
    def other_income(self) -> float:
        return (
            self._db.rsu_income +
            self._db.iso_income +
            self._db.trust_income
        )

    @property
    def business_income(self) -> float:
        return self._db.self_employment_income

    @property
    def retirement_contributions(self) -> float:
        return 0  # Not tracked

    @property
    def retirement_contributions_401k(self) -> float:
        return 0  # Not tracked

    def get_total_income(self) -> float:
        return self._db.gross_income

    def get_total_wages(self) -> float:
        return self._db.w2_income

    def get_total_federal_withholding(self) -> float:
        return self._db.federal_withheld


class DeductionsWrapper:
    """Wrapper to make DatabaseTaxReturn deduction data look like Deductions model."""

    def __init__(self, db_return: DatabaseTaxReturn):
        self._db = db_return

    @property
    def total_itemized(self) -> float:
        return self._db.total_itemized

    @property
    def charitable_cash(self) -> float:
        return 0  # Not tracked separately

    @property
    def charitable_noncash(self) -> float:
        return 0  # Not tracked separately

    @property
    def medical_expenses(self) -> float:
        return 0  # Not tracked separately

    @property
    def state_income_tax_paid(self) -> float:
        return 0  # Not tracked separately

    @property
    def property_tax_paid(self) -> float:
        return 0  # Not tracked separately

    @property
    def mortgage_interest(self) -> float:
        return 0  # Not tracked separately

    def get_total_adjustments(self) -> float:
        return self._db.total_adjustments

    def get_total_deductions(self) -> float:
        return self._db.deduction_amount

    def get_deduction_amount(self, *args, **kwargs) -> float:
        return self._db.deduction_amount


class CreditsWrapper:
    """Wrapper to make DatabaseTaxReturn credits data look like TaxCredits model."""

    def __init__(self, db_return: DatabaseTaxReturn):
        self._db = db_return

    @property
    def child_care_expenses(self) -> float:
        return 0  # Not tracked

    @property
    def num_qualifying_persons(self) -> int:
        return 0  # Not tracked

    @property
    def child_tax_credit_children(self) -> int:
        return 0  # Not tracked

    @property
    def eitc_eligible(self) -> bool:
        return False  # Not tracked

    @property
    def education_expenses(self) -> float:
        return 0  # Not tracked

    @property
    def students(self) -> List[Any]:
        return []  # Not tracked

    @property
    def elective_deferrals_401k(self) -> float:
        return 0  # Not tracked

    @property
    def savers_credit_eligible(self) -> bool:
        return False  # Not tracked

    @property
    def marketplace_coverage(self) -> List[Any]:
        return []  # Not tracked

    @property
    def foreign_tax_credit(self) -> float:
        return 0  # Not tracked

    @property
    def foreign_tax_credit_carryforward(self) -> float:
        return 0  # Not tracked

    @property
    def residential_energy_credit(self) -> float:
        return 0  # Not tracked

    @property
    def solar_electric_expenses(self) -> float:
        return 0  # Not tracked

    @property
    def solar_water_heating_expenses(self) -> float:
        return 0  # Not tracked

    @property
    def other_credits(self) -> float:
        return 0  # Not tracked


class TaxReturnWrapper:
    """
    Wrapper that makes DatabaseTaxReturn compatible with optimizer modules.

    Provides the same interface as the core TaxReturn model, allowing
    the optimizer modules to work with database-loaded tax returns.
    """

    def __init__(self, db_return: DatabaseTaxReturn, client_name: str = ""):
        self._db = db_return
        self._client_name = client_name

        # Create wrapped sub-objects
        self.taxpayer = TaxpayerWrapper(db_return, client_name)
        self.income = IncomeWrapper(db_return)
        self.deductions = DeductionsWrapper(db_return)
        self.credits = CreditsWrapper(db_return)

    def __deepcopy__(self, memo):
        """Support deep copy for analysis scenarios."""
        from copy import deepcopy

        # Create a new wrapper with the same db return
        new_wrapper = TaxReturnWrapper.__new__(TaxReturnWrapper)
        memo[id(self)] = new_wrapper

        # Deep copy the database return (it's a dataclass, should work)
        new_wrapper._db = deepcopy(self._db, memo)
        new_wrapper._client_name = self._client_name

        # Create new wrapped sub-objects
        new_wrapper.taxpayer = TaxpayerWrapper(new_wrapper._db, self._client_name)
        new_wrapper.income = IncomeWrapper(new_wrapper._db)
        new_wrapper.deductions = DeductionsWrapper(new_wrapper._db)
        new_wrapper.credits = CreditsWrapper(new_wrapper._db)

        return new_wrapper

    @property
    def tax_year(self) -> int:
        return self._db.tax_year

    @property
    def adjusted_gross_income(self) -> float:
        return self._db.agi

    @property
    def taxable_income(self) -> float:
        return self._db.taxable_income

    @property
    def tax_liability(self) -> float:
        return self._db.total_tax

    @property
    def total_credits(self) -> float:
        return self._db.total_credits

    @property
    def total_payments(self) -> float:
        return self._db.total_payments

    @property
    def refund_or_owed(self) -> float:
        return self._db.refund_amount - self._db.balance_due

    @property
    def state_of_residence(self) -> str:
        return ""  # Not tracked

    @property
    def state_tax_liability(self) -> float:
        return self._db.state_tax

    @property
    def schedule_c(self) -> Optional[Any]:
        return True if self._db.has_business else None

    @property
    def schedule_e(self) -> Optional[Any]:
        return True if self._db.has_rental_properties else None

    @property
    def virtual_currency_transactions(self) -> Optional[Any]:
        return True if self._db.has_crypto else None

    @property
    def foreign_accounts(self) -> Optional[Any]:
        return True if self._db.has_foreign_reporting else None

    def calculate(self):
        """No-op - values are already calculated in database."""
        pass
