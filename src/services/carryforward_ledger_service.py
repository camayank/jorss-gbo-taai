"""
Carryforward Ledger Service - Multi-year tracking and application of tax carryforwards.

Implements IRC §172 (NOL), §1211-1212 (capital loss), §170 (charitable),
§904 (foreign tax credit), and other carryforward provisions.

Provides functionality to:
- Query prior-year carryforwards
- Create new carryforward entries
- Calculate carryforward usage in current year
- Apply limitations (e.g., 80% NOL limit for post-2020)
- Track expiration dates
"""

from decimal import Decimal
from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from src.database.models import CarryforwardLedgerRecord, CarryforwardType


class CarryforwardLedgerService:
    """Service for managing tax carryforward ledgers across multiple years."""

    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session

    def get_prior_year_carryforwards(
        self,
        taxpayer_ssn_hash: str,
        current_tax_year: int,
        carryforward_type: Optional[CarryforwardType] = None
    ) -> List[CarryforwardLedgerRecord]:
        """
        Query all available carryforwards from prior years.

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            current_tax_year: Current tax year for filtering
            carryforward_type: Filter by type, or None for all types

        Returns:
            List of non-expired carryforward ledger records
        """
        query = self.db.query(CarryforwardLedgerRecord).filter(
            and_(
                CarryforwardLedgerRecord.taxpayer_ssn_hash == taxpayer_ssn_hash,
                CarryforwardLedgerRecord.tax_year < current_tax_year,
                CarryforwardLedgerRecord.is_expired == False,
                CarryforwardLedgerRecord.amount_remaining > 0
            )
        )

        if carryforward_type:
            query = query.filter(CarryforwardLedgerRecord.carryforward_type == carryforward_type)

        return query.order_by(CarryforwardLedgerRecord.source_year).all()

    def get_available_nol(
        self,
        taxpayer_ssn_hash: str,
        current_tax_year: int,
        taxable_income: Decimal
    ) -> Decimal:
        """
        Calculate available NOL deduction for current year (IRC §172).

        Post-2020 tax years are limited to 80% of taxable income.
        Pre-2021 carryforwards generally had no limitation.

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            current_tax_year: Current tax year
            taxable_income: Current year taxable income before NOL deduction

        Returns:
            Maximum deductible NOL amount
        """
        carryforwards = self.get_prior_year_carryforwards(
            taxpayer_ssn_hash,
            current_tax_year,
            CarryforwardType.NET_OPERATING_LOSS
        )

        if not carryforwards:
            return Decimal(0)

        # Determine NOL limitation percentage
        nol_limit_pct = Decimal("0.80") if current_tax_year >= 2021 else Decimal("1.00")
        max_deductible = taxable_income * nol_limit_pct

        # Calculate total available NOL
        total_available = sum(
            cf.amount_remaining for cf in carryforwards
        )

        # Apply limitation
        deductible = min(total_available, max_deductible)
        return Decimal(str(deductible))

    def get_available_capital_loss(
        self,
        taxpayer_ssn_hash: str,
        current_tax_year: int
    ) -> Decimal:
        """
        Calculate available capital loss deduction for current year.

        Capital losses are indefinite carryforwards but limited to $3,000/year
        against ordinary income (more if capital gains present).

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            current_tax_year: Current tax year

        Returns:
            Available capital loss amount (already includes annual limitation)
        """
        carryforwards = self.get_prior_year_carryforwards(
            taxpayer_ssn_hash,
            current_tax_year,
            CarryforwardType.CAPITAL_LOSS
        )

        if not carryforwards:
            return Decimal(0)

        total_available = sum(
            cf.amount_remaining for cf in carryforwards
        )

        return Decimal(str(total_available))

    def get_available_charitable_contribution(
        self,
        taxpayer_ssn_hash: str,
        current_tax_year: int
    ) -> Decimal:
        """
        Calculate available charitable contribution carryforward.

        Charitable contributions can be carried forward for up to 5 years
        if they exceed the AGI percentage limitation.

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            current_tax_year: Current tax year

        Returns:
            Available charitable carryforward amount
        """
        carryforwards = self.get_prior_year_carryforwards(
            taxpayer_ssn_hash,
            current_tax_year,
            CarryforwardType.CHARITABLE_CONTRIBUTION
        )

        if not carryforwards:
            return Decimal(0)

        total_available = sum(
            cf.amount_remaining for cf in carryforwards
        )

        return Decimal(str(total_available))

    def get_available_foreign_tax_credit(
        self,
        taxpayer_ssn_hash: str,
        current_tax_year: int
    ) -> Decimal:
        """
        Calculate available foreign tax credit carryback/forward.

        Foreign tax credits can generally be carried back 1 year and
        forward indefinitely.

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            current_tax_year: Current tax year

        Returns:
            Available foreign tax credit amount
        """
        carryforwards = self.get_prior_year_carryforwards(
            taxpayer_ssn_hash,
            current_tax_year,
            CarryforwardType.FOREIGN_TAX_CREDIT
        )

        if not carryforwards:
            return Decimal(0)

        total_available = sum(
            cf.amount_remaining for cf in carryforwards
        )

        return Decimal(str(total_available))

    def create_carryforward_entry(
        self,
        taxpayer_ssn_hash: str,
        tax_year: int,
        carryforward_type: CarryforwardType,
        amount_available: Decimal,
        source_year: Optional[int] = None,
        expires_after_year: Optional[int] = None,
        firm_id: Optional[str] = None,
        return_id: Optional[str] = None,
    ) -> CarryforwardLedgerRecord:
        """
        Create a new carryforward ledger entry.

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            tax_year: Tax year this carryforward applies to
            carryforward_type: Type of carryforward
            amount_available: Amount available for use
            source_year: Original year carryforward was generated (defaults to tax_year)
            expires_after_year: Year after which carryforward expires
            firm_id: Optional firm ID for scoping
            return_id: Optional return ID to link to specific return

        Returns:
            New CarryforwardLedgerRecord
        """
        ledger = CarryforwardLedgerRecord(
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            tax_year=tax_year,
            carryforward_type=carryforward_type,
            amount_available=amount_available,
            amount_used=Decimal(0),
            amount_remaining=amount_available,
            source_year=source_year or tax_year,
            expires_after_year=expires_after_year,
            firm_id=firm_id,
            return_id=return_id,
        )

        self.db.add(ledger)
        return ledger

    def apply_carryforward_usage(
        self,
        ledger_record: CarryforwardLedgerRecord,
        amount_used: Decimal
    ) -> Decimal:
        """
        Record carryforward usage and update remaining balance.

        Args:
            ledger_record: CarryforwardLedgerRecord to update
            amount_used: Amount being used in current year

        Returns:
            Remaining balance after usage
        """
        # Ensure we don't use more than available
        safe_amount = min(amount_used, ledger_record.amount_remaining)

        ledger_record.amount_used += safe_amount
        ledger_record.amount_remaining -= safe_amount

        if ledger_record.amount_remaining <= 0:
            ledger_record.amount_remaining = Decimal(0)

        return ledger_record.amount_remaining

    def check_expiration(
        self,
        ledger_record: CarryforwardLedgerRecord,
        current_tax_year: int
    ) -> bool:
        """
        Check if carryforward has expired and mark if so.

        Args:
            ledger_record: CarryforwardLedgerRecord to check
            current_tax_year: Current tax year

        Returns:
            True if expired, False otherwise
        """
        if (
            ledger_record.expires_after_year
            and current_tax_year > ledger_record.expires_after_year
        ):
            ledger_record.is_expired = True
            return True

        return False

    def calculate_carryforward_for_next_year(
        self,
        tax_year: int,
        amount_suspended: Decimal,
        carryforward_type: CarryforwardType,
        taxpayer_ssn_hash: str,
        firm_id: Optional[str] = None,
        return_id: Optional[str] = None,
    ) -> Optional[CarryforwardLedgerRecord]:
        """
        Create a carryforward entry for the next tax year (e.g., suspended losses).

        This is called when a deduction/credit cannot be fully used in the current
        year and must be carried forward.

        Args:
            tax_year: Current tax year (carryforward applies to next year)
            amount_suspended: Amount to carry forward
            carryforward_type: Type of carryforward
            taxpayer_ssn_hash: Hash of taxpayer SSN
            firm_id: Optional firm ID
            return_id: Optional return ID

        Returns:
            New CarryforwardLedgerRecord for next year, or None if amount is zero
        """
        if amount_suspended <= 0:
            return None

        # Determine expiration year based on carryforward type
        next_year = tax_year + 1
        expires_after_year = None

        if carryforward_type == CarryforwardType.CHARITABLE_CONTRIBUTION:
            expires_after_year = tax_year + 5  # 5-year carryforward

        # Indefinite carryforwards: NOL, capital loss, FTC, AMT credit

        return self.create_carryforward_entry(
            taxpayer_ssn_hash=taxpayer_ssn_hash,
            tax_year=next_year,
            carryforward_type=carryforward_type,
            amount_available=amount_suspended,
            source_year=tax_year,
            expires_after_year=expires_after_year,
            firm_id=firm_id,
            return_id=return_id,
        )

    def get_carryforward_summary(
        self,
        taxpayer_ssn_hash: str,
        current_tax_year: int
    ) -> Dict[str, Any]:
        """
        Get summary of all carryforwards for a taxpayer.

        Args:
            taxpayer_ssn_hash: Hash of taxpayer SSN
            current_tax_year: Current tax year

        Returns:
            Dictionary with carryforward summaries by type
        """
        carryforwards = self.get_prior_year_carryforwards(
            taxpayer_ssn_hash,
            current_tax_year
        )

        summary = {
            "total_carryforwards": Decimal(0),
            "by_type": {}
        }

        for cf in carryforwards:
            cf_type_name = cf.carryforward_type.value
            if cf_type_name not in summary["by_type"]:
                summary["by_type"][cf_type_name] = {
                    "total_available": Decimal(0),
                    "entries": []
                }

            summary["by_type"][cf_type_name]["total_available"] += cf.amount_remaining
            summary["by_type"][cf_type_name]["entries"].append({
                "source_year": cf.source_year,
                "amount": float(cf.amount_remaining),
                "expires_after": cf.expires_after_year,
            })

            summary["total_carryforwards"] += cf.amount_remaining

        return summary
