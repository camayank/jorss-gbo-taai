"""
K-1 Basis Tracking System

Implements partner/shareholder outside basis tracking per IRC Section 705.
Enforces basis limitations on loss deductions per IRC Section 704(d).

Key Concepts:
- Outside Basis: Taxpayer's investment basis in the partnership/S-corp
- Basis is increased by: income, contributions
- Basis is decreased by: losses, distributions
- Losses cannot reduce basis below zero
- Excess losses are carried forward
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal
import uuid


class EntityType(str, Enum):
    """Type of pass-through entity."""
    PARTNERSHIP = "partnership"
    S_CORPORATION = "s_corporation"
    TRUST_ESTATE = "trust_estate"


class BasisAdjustmentType(str, Enum):
    """Types of basis adjustments per IRC §705."""
    # Increases (IRC §705(a)(1))
    CONTRIBUTION_CASH = "contribution_cash"
    CONTRIBUTION_PROPERTY = "contribution_property"
    DISTRIBUTIVE_SHARE_INCOME = "distributive_share_income"
    DISTRIBUTIVE_SHARE_GAIN = "distributive_share_gain"
    TAX_EXEMPT_INCOME = "tax_exempt_income"

    # Decreases (IRC §705(a)(2))
    DISTRIBUTION_CASH = "distribution_cash"
    DISTRIBUTION_PROPERTY = "distribution_property"
    DISTRIBUTIVE_SHARE_LOSS = "distributive_share_loss"
    DISTRIBUTIVE_SHARE_DEDUCTION = "distributive_share_deduction"
    NONDEDUCTIBLE_EXPENSES = "nondeductible_expenses"


@dataclass
class BasisAdjustment:
    """A single basis adjustment event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    adjustment_type: BasisAdjustmentType = BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME
    amount: float = 0.0
    description: Optional[str] = None
    effective_date: Optional[date] = None
    k1_line_reference: Optional[str] = None  # e.g., "Box 1", "Box 2"

    @property
    def is_increase(self) -> bool:
        """Returns True if this adjustment increases basis."""
        return self.adjustment_type in [
            BasisAdjustmentType.CONTRIBUTION_CASH,
            BasisAdjustmentType.CONTRIBUTION_PROPERTY,
            BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
            BasisAdjustmentType.DISTRIBUTIVE_SHARE_GAIN,
            BasisAdjustmentType.TAX_EXEMPT_INCOME
        ]

    def get_signed_amount(self) -> float:
        """Returns amount with sign (positive for increases, negative for decreases)."""
        return self.amount if self.is_increase else -abs(self.amount)


@dataclass
class Distribution:
    """A distribution received from the entity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    distribution_date: date = field(default_factory=date.today)
    cash_distributed: float = 0.0
    property_fmv: float = 0.0  # Fair market value of distributed property
    property_basis: float = 0.0  # Entity's basis in distributed property
    is_return_of_capital: bool = False
    is_gain_distribution: bool = False  # If FMV > basis limit
    notes: Optional[str] = None

    @property
    def total_distribution(self) -> float:
        """Total distribution amount (cash + property FMV)."""
        return self.cash_distributed + self.property_fmv


@dataclass
class K1BasisRecord:
    """
    Partner/Shareholder Outside Basis Tracking Record.

    Tracks annual basis for a single K-1 investment, including
    all adjustments, distributions, and loss limitations.
    """
    # Entity identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_name: str = ""
    entity_ein: Optional[str] = None
    entity_type: EntityType = EntityType.PARTNERSHIP

    # Tax year
    tax_year: int = field(default_factory=lambda: datetime.now().year - 1)

    # Basis tracking
    beginning_basis: float = 0.0
    ending_basis: float = 0.0  # Calculated

    # Adjustments during the year (from K-1)
    adjustments: List[BasisAdjustment] = field(default_factory=list)

    # Distributions received
    distributions: List[Distribution] = field(default_factory=list)

    # Loss limitation tracking
    current_year_losses: float = 0.0  # Total losses per K-1
    losses_allowed: float = 0.0  # Losses actually deductible (limited by basis)
    losses_suspended: float = 0.0  # Losses carried forward (basis-limited)
    prior_year_suspended_losses: float = 0.0  # From prior years

    # At-risk tracking (IRC §465)
    at_risk_amount: float = 0.0
    qualified_nonrecourse_debt: float = 0.0  # Real estate exception

    # Capital accounts (from K-1)
    capital_account_beginning: float = 0.0
    capital_account_ending: float = 0.0

    # Ownership
    ownership_percentage: float = 0.0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None

    def add_adjustment(self, adjustment: BasisAdjustment) -> None:
        """Add a basis adjustment."""
        self.adjustments.append(adjustment)
        self.updated_at = datetime.now()

    def add_distribution(self, distribution: Distribution) -> None:
        """Add a distribution."""
        self.distributions.append(distribution)
        self.updated_at = datetime.now()

    def calculate_total_increases(self) -> float:
        """Calculate total basis increases for the year."""
        return sum(
            adj.amount for adj in self.adjustments
            if adj.is_increase
        )

    def calculate_total_decreases(self) -> float:
        """Calculate total basis decreases for the year (excluding losses limited by basis)."""
        distribution_total = sum(d.total_distribution for d in self.distributions)
        other_decreases = sum(
            abs(adj.amount) for adj in self.adjustments
            if not adj.is_increase
            and adj.adjustment_type not in [
                BasisAdjustmentType.DISTRIBUTION_CASH,
                BasisAdjustmentType.DISTRIBUTION_PROPERTY
            ]
        )
        return distribution_total + other_decreases

    def calculate_ending_basis(self) -> float:
        """
        Calculate ending basis per IRC §705.

        Order of operations (IRC §705 and Reg. §1.704-1(d)):
        1. Start with beginning basis
        2. Add contributions
        3. Add distributive share of income/gain
        4. Add tax-exempt income
        5. Subtract distributions (but not below zero)
        6. Subtract non-deductible expenses
        7. Subtract distributive share of losses/deductions (limited by remaining basis)

        Returns the calculated ending basis.
        """
        # Start with beginning basis
        basis = self.beginning_basis

        # Step 1: Add contributions
        contributions = sum(
            adj.amount for adj in self.adjustments
            if adj.adjustment_type in [
                BasisAdjustmentType.CONTRIBUTION_CASH,
                BasisAdjustmentType.CONTRIBUTION_PROPERTY
            ]
        )
        basis += contributions

        # Step 2: Add income/gain items
        income_items = sum(
            adj.amount for adj in self.adjustments
            if adj.adjustment_type in [
                BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                BasisAdjustmentType.DISTRIBUTIVE_SHARE_GAIN,
                BasisAdjustmentType.TAX_EXEMPT_INCOME
            ]
        )
        basis += income_items

        # Step 3: Subtract distributions (limited to avoid negative basis)
        total_distributions = sum(d.total_distribution for d in self.distributions)
        distribution_reduction = min(total_distributions, basis)
        basis -= distribution_reduction

        # Check for gain recognition on excess distribution
        if total_distributions > basis + distribution_reduction:
            # This would trigger gain recognition
            pass

        # Step 4: Subtract non-deductible expenses
        nondeductible = sum(
            abs(adj.amount) for adj in self.adjustments
            if adj.adjustment_type == BasisAdjustmentType.NONDEDUCTIBLE_EXPENSES
        )
        basis = max(0, basis - nondeductible)

        # Step 5: Subtract losses/deductions (limited by remaining basis)
        total_losses = sum(
            abs(adj.amount) for adj in self.adjustments
            if adj.adjustment_type in [
                BasisAdjustmentType.DISTRIBUTIVE_SHARE_LOSS,
                BasisAdjustmentType.DISTRIBUTIVE_SHARE_DEDUCTION
            ]
        )

        # Add prior year suspended losses
        total_losses += self.prior_year_suspended_losses

        # Losses are limited by basis
        self.current_year_losses = total_losses
        self.losses_allowed = min(total_losses, basis)
        self.losses_suspended = max(0, total_losses - basis)

        basis -= self.losses_allowed

        # Update ending basis
        self.ending_basis = max(0, basis)
        self.updated_at = datetime.now()

        return self.ending_basis

    def get_deductible_loss(self) -> float:
        """Get the amount of loss that can be deducted (not suspended)."""
        self.calculate_ending_basis()  # Ensure calculations are current
        return self.losses_allowed

    def get_suspended_loss(self) -> float:
        """Get the amount of loss that must be carried forward."""
        self.calculate_ending_basis()  # Ensure calculations are current
        return self.losses_suspended

    def apply_from_k1(
        self,
        ordinary_income: float = 0,
        net_rental_income: float = 0,
        portfolio_income: float = 0,
        guaranteed_payments: float = 0,
        capital_gains_losses: float = 0,
        section_1231_gains_losses: float = 0,
        other_income: float = 0,
        section_179_deduction: float = 0,
        other_deductions: float = 0,
        tax_exempt_interest: float = 0,
        distributions: float = 0,
        contributions: float = 0
    ) -> None:
        """
        Apply K-1 amounts to basis tracking.

        Maps common K-1 box amounts to basis adjustments.
        """
        # Income items (increase basis)
        if ordinary_income > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                amount=ordinary_income,
                k1_line_reference="Box 1 (Ordinary Income)"
            ))

        if net_rental_income > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                amount=net_rental_income,
                k1_line_reference="Box 2 (Net Rental Income)"
            ))

        if portfolio_income > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                amount=portfolio_income,
                k1_line_reference="Box 5/6/7 (Portfolio Income)"
            ))

        if guaranteed_payments > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                amount=guaranteed_payments,
                k1_line_reference="Box 4 (Guaranteed Payments)"
            ))

        if capital_gains_losses > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_GAIN,
                amount=capital_gains_losses,
                k1_line_reference="Box 8/9 (Capital Gains)"
            ))

        if section_1231_gains_losses > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_GAIN,
                amount=section_1231_gains_losses,
                k1_line_reference="Box 10 (Section 1231 Gain)"
            ))

        if other_income > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                amount=other_income,
                k1_line_reference="Box 11 (Other Income)"
            ))

        if tax_exempt_interest > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.TAX_EXEMPT_INCOME,
                amount=tax_exempt_interest,
                k1_line_reference="Box 18 (Tax-Exempt Income)"
            ))

        # Loss items (decrease basis)
        if ordinary_income < 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_LOSS,
                amount=abs(ordinary_income),
                k1_line_reference="Box 1 (Ordinary Loss)"
            ))

        if net_rental_income < 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_LOSS,
                amount=abs(net_rental_income),
                k1_line_reference="Box 2 (Net Rental Loss)"
            ))

        if capital_gains_losses < 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_LOSS,
                amount=abs(capital_gains_losses),
                k1_line_reference="Box 8/9 (Capital Loss)"
            ))

        if section_1231_gains_losses < 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_LOSS,
                amount=abs(section_1231_gains_losses),
                k1_line_reference="Box 10 (Section 1231 Loss)"
            ))

        if section_179_deduction > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_DEDUCTION,
                amount=section_179_deduction,
                k1_line_reference="Box 12 (Section 179 Deduction)"
            ))

        if other_deductions > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.DISTRIBUTIVE_SHARE_DEDUCTION,
                amount=other_deductions,
                k1_line_reference="Box 13 (Other Deductions)"
            ))

        # Distributions (decrease basis)
        if distributions > 0:
            self.add_distribution(Distribution(
                cash_distributed=distributions,
                notes="From K-1 distribution"
            ))

        # Contributions (increase basis)
        if contributions > 0:
            self.add_adjustment(BasisAdjustment(
                adjustment_type=BasisAdjustmentType.CONTRIBUTION_CASH,
                amount=contributions,
                description="Capital contribution"
            ))

        # Recalculate ending basis
        self.calculate_ending_basis()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "entity_name": self.entity_name,
            "entity_ein": self.entity_ein,
            "entity_type": self.entity_type.value,
            "tax_year": self.tax_year,
            "beginning_basis": self.beginning_basis,
            "ending_basis": self.ending_basis,
            "total_increases": self.calculate_total_increases(),
            "total_decreases": self.calculate_total_decreases(),
            "current_year_losses": self.current_year_losses,
            "losses_allowed": self.losses_allowed,
            "losses_suspended": self.losses_suspended,
            "prior_year_suspended_losses": self.prior_year_suspended_losses,
            "at_risk_amount": self.at_risk_amount,
            "ownership_percentage": self.ownership_percentage,
            "adjustment_count": len(self.adjustments),
            "distribution_count": len(self.distributions)
        }

    def get_basis_worksheet(self) -> Dict[str, Any]:
        """
        Generate a basis worksheet showing step-by-step calculation.

        Useful for documentation and CPA review.
        """
        return {
            "entity": {
                "name": self.entity_name,
                "ein": self.entity_ein,
                "type": self.entity_type.value,
                "ownership": f"{self.ownership_percentage}%"
            },
            "tax_year": self.tax_year,
            "basis_calculation": {
                "1_beginning_basis": self.beginning_basis,
                "2_contributions": sum(
                    adj.amount for adj in self.adjustments
                    if adj.adjustment_type in [
                        BasisAdjustmentType.CONTRIBUTION_CASH,
                        BasisAdjustmentType.CONTRIBUTION_PROPERTY
                    ]
                ),
                "3_income_gain": sum(
                    adj.amount for adj in self.adjustments
                    if adj.adjustment_type in [
                        BasisAdjustmentType.DISTRIBUTIVE_SHARE_INCOME,
                        BasisAdjustmentType.DISTRIBUTIVE_SHARE_GAIN
                    ]
                ),
                "4_tax_exempt_income": sum(
                    adj.amount for adj in self.adjustments
                    if adj.adjustment_type == BasisAdjustmentType.TAX_EXEMPT_INCOME
                ),
                "5_distributions": sum(d.total_distribution for d in self.distributions),
                "6_nondeductible_expenses": sum(
                    abs(adj.amount) for adj in self.adjustments
                    if adj.adjustment_type == BasisAdjustmentType.NONDEDUCTIBLE_EXPENSES
                ),
                "7_losses_deductions": sum(
                    abs(adj.amount) for adj in self.adjustments
                    if adj.adjustment_type in [
                        BasisAdjustmentType.DISTRIBUTIVE_SHARE_LOSS,
                        BasisAdjustmentType.DISTRIBUTIVE_SHARE_DEDUCTION
                    ]
                ),
                "8_ending_basis": self.ending_basis
            },
            "loss_limitation": {
                "total_losses": self.current_year_losses,
                "prior_year_suspended": self.prior_year_suspended_losses,
                "losses_allowed": self.losses_allowed,
                "losses_suspended": self.losses_suspended,
                "suspended_to_next_year": self.losses_suspended
            },
            "at_risk": {
                "at_risk_amount": self.at_risk_amount,
                "qualified_nonrecourse": self.qualified_nonrecourse_debt
            }
        }


class K1BasisTracker:
    """
    Manager for tracking K-1 basis across multiple entities and years.
    """

    def __init__(self):
        self.records: Dict[str, K1BasisRecord] = {}  # Key: record.id (UUID)
        self._ein_index: Dict[str, str] = {}  # EIN/name -> record.id

    def add_record(self, record: K1BasisRecord) -> None:
        """Add or update a basis record."""
        # Store by UUID
        self.records[record.id] = record
        # Also index by EIN or entity name
        key = record.entity_ein or record.entity_name
        self._ein_index[key] = record.id

    def get_record(self, entity_identifier: str) -> Optional[K1BasisRecord]:
        """Get basis record by ID, EIN, or entity name."""
        # First check if it's a UUID/ID
        if entity_identifier in self.records:
            return self.records[entity_identifier]
        # Then check EIN/name index
        if entity_identifier in self._ein_index:
            return self.records.get(self._ein_index[entity_identifier])
        return None

    def get_all_records(self) -> List[K1BasisRecord]:
        """Get all basis records."""
        return list(self.records.values())

    def calculate_total_deductible_losses(self) -> float:
        """Calculate total deductible K-1 losses across all entities."""
        return sum(record.get_deductible_loss() for record in self.records.values())

    def calculate_total_suspended_losses(self) -> float:
        """Calculate total suspended K-1 losses across all entities."""
        return sum(record.get_suspended_loss() for record in self.records.values())

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all K-1 basis tracking."""
        total_deductible = 0
        total_suspended = 0
        total_ending_basis = 0

        entity_summaries = []
        for record in self.records.values():
            record.calculate_ending_basis()
            total_deductible += record.losses_allowed
            total_suspended += record.losses_suspended
            total_ending_basis += record.ending_basis
            entity_summaries.append({
                "entity": record.entity_name,
                "ending_basis": record.ending_basis,
                "losses_allowed": record.losses_allowed,
                "losses_suspended": record.losses_suspended
            })

        return {
            "total_entities": len(self.records),
            "total_ending_basis": total_ending_basis,
            "total_deductible_losses": total_deductible,
            "total_suspended_losses": total_suspended,
            "entities": entity_summaries
        }
