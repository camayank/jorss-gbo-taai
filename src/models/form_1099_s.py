"""
Form 1099-S - Proceeds from Real Estate Transactions

Complete IRS Form 1099-S implementation for reporting real estate sale proceeds:
- Sale or exchange of real estate
- Includes land, buildings, permanent structures
- Residential and commercial property

Key aspects:
- Reports gross proceeds (not net)
- Required for transactions over $600 unless exempt
- Seller's information (TIN) required
- Primary residence exclusion ($250k single / $500k MFJ) tracked separately

Exempt transactions:
- Principal residence sale meeting exclusion requirements
- Property sold for <$600
- Foreclosures (reported elsewhere)
- Transfers pursuant to divorce
- Like-kind exchanges (Form 8824)

Integration with:
- Schedule D (capital gains)
- Form 4797 (business property)
- Form 8949 (investment property)
- Form 8824 (like-kind exchanges)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field
from datetime import date


class PropertyType(str, Enum):
    """Type of real property sold."""
    PRINCIPAL_RESIDENCE = "principal_residence"
    SECOND_HOME = "second_home"
    RENTAL_PROPERTY = "rental_property"
    INVESTMENT_LAND = "investment_land"
    COMMERCIAL = "commercial"
    MIXED_USE = "mixed_use"
    OTHER = "other"


class TransactionType(str, Enum):
    """Type of real estate transaction."""
    SALE = "sale"
    EXCHANGE = "exchange"  # Like-kind
    INSTALLMENT_SALE = "installment_sale"
    FORECLOSURE = "foreclosure"
    SHORT_SALE = "short_sale"
    CONDEMNATION = "condemnation"


class Form1099S(BaseModel):
    """
    Form 1099-S - Proceeds from Real Estate Transactions

    Reports gross proceeds from real estate sales.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Filer Information (settlement agent, title company)
    filer_name: str = Field(default="", description="Name of filer")
    filer_tin: str = Field(default="", description="Filer TIN/EIN")
    filer_address: str = Field(default="", description="Filer address")

    # Transferor (Seller) Information
    transferor_name: str = Field(default="", description="Seller name")
    transferor_tin: str = Field(default="", description="Seller TIN/SSN")
    transferor_address: str = Field(default="", description="Seller address")

    # Box 1: Date of closing
    box_1_date_of_closing: Optional[date] = Field(
        default=None,
        description="Box 1: Date of closing"
    )

    # Box 2: Gross proceeds
    box_2_gross_proceeds: float = Field(
        default=0.0, ge=0,
        description="Box 2: Gross proceeds from sale"
    )

    # Box 3: Address or legal description
    box_3_property_address: str = Field(
        default="",
        description="Box 3: Property address or legal description"
    )

    # Box 4: Check if transferor received or will receive
    # property or services as part of the consideration
    box_4_property_services_received: bool = Field(
        default=False,
        description="Box 4: Property/services received as consideration"
    )

    # Box 5: Check if foreign person
    box_5_foreign_person: bool = Field(
        default=False,
        description="Box 5: Transferor is a foreign person"
    )

    # Box 6: Buyer's part of real estate tax
    box_6_buyer_real_estate_tax: float = Field(
        default=0.0, ge=0,
        description="Box 6: Buyer's part of real estate tax"
    )

    # Additional tracking fields (not on form but useful)
    property_type: PropertyType = Field(
        default=PropertyType.OTHER,
        description="Type of property"
    )

    transaction_type: TransactionType = Field(
        default=TransactionType.SALE,
        description="Type of transaction"
    )

    # For primary residence exclusion determination
    is_primary_residence: bool = Field(
        default=False,
        description="Is this the primary residence?"
    )

    # Ownership and use test for primary residence
    ownership_months: int = Field(
        default=0, ge=0,
        description="Months of ownership in last 5 years"
    )

    use_as_residence_months: int = Field(
        default=0, ge=0,
        description="Months used as primary residence in last 5 years"
    )

    @computed_field
    @property
    def meets_ownership_test(self) -> bool:
        """Check if ownership test is met (24+ months in last 5 years)."""
        return self.ownership_months >= 24

    @computed_field
    @property
    def meets_use_test(self) -> bool:
        """Check if use test is met (24+ months in last 5 years)."""
        return self.use_as_residence_months >= 24

    @computed_field
    @property
    def qualifies_for_exclusion(self) -> bool:
        """Check if sale qualifies for primary residence exclusion."""
        return (
            self.is_primary_residence and
            self.meets_ownership_test and
            self.meets_use_test
        )


class RealEstateSaleCalculation(BaseModel):
    """
    Calculate gain/loss and tax from real estate sale.

    Integrates Form 1099-S data with basis and expense information.
    """
    # From Form 1099-S
    form_1099s: Form1099S = Field(
        default_factory=Form1099S,
        description="Form 1099-S data"
    )

    # Basis Information
    original_purchase_price: float = Field(
        default=0.0, ge=0,
        description="Original purchase price"
    )

    purchase_closing_costs: float = Field(
        default=0.0, ge=0,
        description="Closing costs when purchased"
    )

    capital_improvements: float = Field(
        default=0.0, ge=0,
        description="Cost of capital improvements"
    )

    # Depreciation (for rental/business property)
    depreciation_taken: float = Field(
        default=0.0, ge=0,
        description="Total depreciation taken"
    )

    # Selling Expenses
    selling_closing_costs: float = Field(
        default=0.0, ge=0,
        description="Closing costs when sold"
    )

    real_estate_commission: float = Field(
        default=0.0, ge=0,
        description="Real estate agent commissions"
    )

    other_selling_expenses: float = Field(
        default=0.0, ge=0,
        description="Other selling expenses"
    )

    # Primary Residence Exclusion
    filing_status: str = Field(
        default="single",
        description="Filing status (single, mfj, mfs, hoh)"
    )

    # Installment sale
    is_installment_sale: bool = Field(
        default=False,
        description="Is this an installment sale?"
    )

    # Holding period
    date_acquired: Optional[date] = Field(
        default=None,
        description="Date property was acquired"
    )

    @computed_field
    @property
    def adjusted_basis(self) -> float:
        """Calculate adjusted basis of property."""
        basis = (
            self.original_purchase_price +
            self.purchase_closing_costs +
            self.capital_improvements -
            self.depreciation_taken
        )
        return max(0, basis)

    @computed_field
    @property
    def total_selling_expenses(self) -> float:
        """Total selling expenses."""
        return (
            self.selling_closing_costs +
            self.real_estate_commission +
            self.other_selling_expenses
        )

    @computed_field
    @property
    def amount_realized(self) -> float:
        """Amount realized from sale (gross - selling expenses)."""
        return self.form_1099s.box_2_gross_proceeds - self.total_selling_expenses

    @computed_field
    @property
    def realized_gain_loss(self) -> float:
        """Realized gain or loss on sale."""
        return self.amount_realized - self.adjusted_basis

    @computed_field
    @property
    def exclusion_amount(self) -> float:
        """Amount of primary residence exclusion available."""
        if not self.form_1099s.qualifies_for_exclusion:
            return 0.0

        # Max exclusion: $250k single, $500k MFJ
        if self.filing_status.lower() in ['mfj', 'married_filing_jointly']:
            max_exclusion = 500000.0
        else:
            max_exclusion = 250000.0

        return max_exclusion

    @computed_field
    @property
    def taxable_gain(self) -> float:
        """Calculate taxable gain after exclusion."""
        if self.realized_gain_loss <= 0:
            return 0.0  # Loss, no taxable gain

        gain_after_exclusion = max(0, self.realized_gain_loss - self.exclusion_amount)
        return gain_after_exclusion

    @computed_field
    @property
    def recognized_loss(self) -> float:
        """Calculate recognized loss (personal residence loss not deductible)."""
        if self.realized_gain_loss >= 0:
            return 0.0

        # Personal residence loss is NOT deductible
        if self.form_1099s.property_type == PropertyType.PRINCIPAL_RESIDENCE:
            return 0.0

        # Investment/rental property loss IS deductible
        return abs(self.realized_gain_loss)

    @computed_field
    @property
    def depreciation_recapture(self) -> float:
        """
        Calculate Section 1250 depreciation recapture (25% rate).

        Only applies to rental/business property.
        """
        if self.depreciation_taken <= 0:
            return 0.0

        if self.form_1099s.property_type in [
            PropertyType.PRINCIPAL_RESIDENCE,
            PropertyType.SECOND_HOME
        ]:
            return 0.0  # No recapture for personal use

        # Recapture is lesser of gain or depreciation taken
        if self.realized_gain_loss <= 0:
            return 0.0

        return min(self.realized_gain_loss, self.depreciation_taken)

    @computed_field
    @property
    def capital_gain_portion(self) -> float:
        """Capital gain portion (after recapture)."""
        if self.taxable_gain <= 0:
            return 0.0

        return max(0, self.taxable_gain - self.depreciation_recapture)

    @computed_field
    @property
    def holding_period_days(self) -> Optional[int]:
        """Days property was held."""
        if self.date_acquired and self.form_1099s.box_1_date_of_closing:
            delta = self.form_1099s.box_1_date_of_closing - self.date_acquired
            return delta.days
        return None

    @computed_field
    @property
    def is_long_term(self) -> bool:
        """Check if holding period qualifies for long-term rates."""
        days = self.holding_period_days
        if days is None:
            return False
        return days > 365  # More than 1 year

    def to_schedule_d(self) -> Dict[str, Any]:
        """Get amounts for Schedule D reporting."""
        return {
            "proceeds": self.form_1099s.box_2_gross_proceeds,
            "basis": self.adjusted_basis + self.total_selling_expenses,
            "gain_loss": self.realized_gain_loss,
            "exclusion": self.exclusion_amount if self.realized_gain_loss > 0 else 0,
            "taxable_gain": self.taxable_gain,
            "is_long_term": self.is_long_term,
            "depreciation_recapture": self.depreciation_recapture,
        }

    def to_form_8949(self) -> Dict[str, Any]:
        """Get data for Form 8949."""
        return {
            "description": self.form_1099s.box_3_property_address,
            "date_acquired": self.date_acquired.isoformat() if self.date_acquired else "",
            "date_sold": (
                self.form_1099s.box_1_date_of_closing.isoformat()
                if self.form_1099s.box_1_date_of_closing else ""
            ),
            "proceeds": self.form_1099s.box_2_gross_proceeds,
            "cost_basis": self.adjusted_basis,
            "adjustment": -self.total_selling_expenses,
            "gain_loss": self.realized_gain_loss,
            "code": "H" if self.realized_gain_loss < 0 else "",  # Loss on personal residence
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.form_1099s.tax_year,
            "property_address": self.form_1099s.box_3_property_address,
            "property_type": self.form_1099s.property_type.value,
            "gross_proceeds": self.form_1099s.box_2_gross_proceeds,
            "adjusted_basis": self.adjusted_basis,
            "selling_expenses": self.total_selling_expenses,
            "amount_realized": self.amount_realized,
            "realized_gain_loss": self.realized_gain_loss,
            "primary_residence_exclusion": {
                "qualifies": self.form_1099s.qualifies_for_exclusion,
                "amount": self.exclusion_amount,
            },
            "taxable_gain": self.taxable_gain,
            "depreciation_recapture": self.depreciation_recapture,
            "capital_gain": self.capital_gain_portion,
            "holding_period": {
                "days": self.holding_period_days,
                "is_long_term": self.is_long_term,
            },
        }


def calculate_real_estate_gain(
    gross_proceeds: float,
    purchase_price: float,
    improvements: float = 0.0,
    depreciation: float = 0.0,
    selling_costs: float = 0.0,
    commission: float = 0.0,
    is_primary_residence: bool = False,
    filing_status: str = "single",
    meets_exclusion_tests: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to calculate real estate sale gain/loss.

    Args:
        gross_proceeds: Amount from 1099-S
        purchase_price: Original purchase price
        improvements: Capital improvements made
        depreciation: Depreciation taken (rental property)
        selling_costs: Closing costs, etc.
        commission: Real estate commission
        is_primary_residence: Is this primary residence?
        filing_status: Tax filing status
        meets_exclusion_tests: Meets ownership/use tests?

    Returns:
        Dictionary with gain calculations and tax implications
    """
    form = Form1099S(
        box_2_gross_proceeds=gross_proceeds,
        is_primary_residence=is_primary_residence,
        property_type=(
            PropertyType.PRINCIPAL_RESIDENCE if is_primary_residence
            else PropertyType.INVESTMENT_LAND
        ),
        ownership_months=24 if meets_exclusion_tests else 0,
        use_as_residence_months=24 if meets_exclusion_tests else 0,
    )

    calc = RealEstateSaleCalculation(
        form_1099s=form,
        original_purchase_price=purchase_price,
        capital_improvements=improvements,
        depreciation_taken=depreciation,
        selling_closing_costs=selling_costs,
        real_estate_commission=commission,
        filing_status=filing_status,
    )

    return {
        "gross_proceeds": gross_proceeds,
        "adjusted_basis": calc.adjusted_basis,
        "selling_expenses": calc.total_selling_expenses,
        "amount_realized": calc.amount_realized,
        "realized_gain": max(0, calc.realized_gain_loss),
        "realized_loss": max(0, -calc.realized_gain_loss),
        "exclusion_available": calc.exclusion_amount,
        "taxable_gain": calc.taxable_gain,
        "depreciation_recapture": calc.depreciation_recapture,
        "capital_gain": calc.capital_gain_portion,
    }


def calculate_primary_residence_exclusion(
    sale_price: float,
    purchase_price: float,
    improvements: float,
    selling_costs: float,
    filing_status: str,
    ownership_months: int,
    use_months: int,
) -> Dict[str, Any]:
    """
    Specifically calculate primary residence exclusion.

    Section 121 allows exclusion of:
    - $250,000 for single filers
    - $500,000 for married filing jointly

    Requirements:
    - Owned home for at least 2 of last 5 years
    - Used as primary residence for at least 2 of last 5 years
    """
    meets_ownership = ownership_months >= 24
    meets_use = use_months >= 24
    qualifies = meets_ownership and meets_use

    # Calculate gain
    basis = purchase_price + improvements
    amount_realized = sale_price - selling_costs
    gain = amount_realized - basis

    # Exclusion amount
    if filing_status.lower() in ['mfj', 'married_filing_jointly']:
        max_exclusion = 500000.0
    else:
        max_exclusion = 250000.0

    if not qualifies:
        exclusion = 0.0
    elif gain <= 0:
        exclusion = 0.0
    else:
        exclusion = min(gain, max_exclusion)

    taxable_gain = max(0, gain - exclusion)

    return {
        "sale_price": sale_price,
        "basis": basis,
        "selling_costs": selling_costs,
        "gain": gain,
        "qualifies_for_exclusion": qualifies,
        "ownership_test_met": meets_ownership,
        "use_test_met": meets_use,
        "max_exclusion": max_exclusion if qualifies else 0,
        "exclusion_used": exclusion,
        "taxable_gain": taxable_gain,
        "tax_free": exclusion,
    }
