"""
Form 6252 - Installment Sale Income

Implements IRS Form 6252 for reporting income from installment sales
per IRC Section 453.

Key Concepts:
- Installment Method: Spread gain recognition over payment period
- Gross Profit Percentage: (Gross Profit / Contract Price)
- Each payment = (Principal × GP%) taxable + Interest (ordinary income)
- Depreciation Recapture: Recognized in year of sale (not deferred)
- Related Party Rules: Special restrictions on resales within 2 years

IRC References:
- Section 453: Installment method
- Section 453A: Interest charge on deferred tax (>$5M sales)
- Section 453B: Disposition of installment obligations
- Section 1245/1250: Depreciation recapture
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class PropertyCategory(str, Enum):
    """Property categories for installment sales."""
    REAL_PROPERTY = "real_property"  # Real estate
    PERSONAL_PROPERTY = "personal_property"  # Equipment, machinery
    TIMESHARES = "timeshares"
    RESIDENTIAL_LOTS = "residential_lots"
    FARM_PROPERTY = "farm_property"
    BUSINESS_ASSETS = "business_assets"
    SECURITIES = "securities"  # Generally NOT eligible for installment method
    INVENTORY = "inventory"  # NOT eligible for installment method
    DEPRECIABLE_PROPERTY_RELATED = "depreciable_property_related"  # To related party


class RelatedPartyType(str, Enum):
    """Types of related party relationships for Section 453 purposes."""
    NOT_RELATED = "not_related"
    SPOUSE = "spouse"
    CHILD = "child"
    GRANDCHILD = "grandchild"
    PARENT = "parent"
    SIBLING = "sibling"
    CONTROLLED_CORPORATION = "controlled_corporation"  # >50% ownership
    CONTROLLED_PARTNERSHIP = "controlled_partnership"  # >50% interest
    TRUST_BENEFICIARY = "trust_beneficiary"
    ESTATE_BENEFICIARY = "estate_beneficiary"
    OTHER_RELATED = "other_related"


class InstallmentPayment(BaseModel):
    """
    Individual installment payment received.

    Tracks both principal and interest components of each payment.
    Interest is taxed as ordinary income, principal as capital gain.
    """
    payment_date: str = Field(description="Date payment received (YYYY-MM-DD)")
    total_payment: float = Field(ge=0, description="Total payment received")
    principal_portion: float = Field(ge=0, description="Principal portion of payment")
    interest_portion: float = Field(default=0.0, ge=0, description="Interest income")

    def validate_portions(self) -> bool:
        """Validate that principal + interest = total payment."""
        return abs(self.principal_portion + self.interest_portion - self.total_payment) < 0.01


class InstallmentObligation(BaseModel):
    """
    Tracks an installment sale obligation from year of sale through completion.

    Used for multi-year tracking of a single installment sale.
    """
    # Sale identification
    property_description: str = Field(description="Description of property sold")
    property_category: PropertyCategory = Field(default=PropertyCategory.REAL_PROPERTY)

    # Sale dates
    date_acquired: str = Field(description="Date property was originally acquired")
    date_sold: str = Field(description="Date of installment sale")
    year_of_sale: int = Field(description="Tax year of original sale")

    # Sale amounts (from year of sale)
    selling_price: float = Field(ge=0, description="Total selling price")
    adjusted_basis: float = Field(ge=0, description="Adjusted basis at time of sale")
    selling_expenses: float = Field(default=0.0, ge=0, description="Commissions, legal fees")

    # Depreciation (for recapture)
    depreciation_allowed: float = Field(
        default=0.0, ge=0,
        description="Total depreciation allowed/allowable"
    )
    section_1245_recapture: float = Field(
        default=0.0, ge=0,
        description="Section 1245 recapture (recognized in year of sale)"
    )
    section_1250_recapture: float = Field(
        default=0.0, ge=0,
        description="Section 1250 ordinary recapture (recognized in year of sale)"
    )
    unrecaptured_1250_gain: float = Field(
        default=0.0, ge=0,
        description="Unrecaptured Section 1250 gain (25% rate)"
    )

    # Mortgage/debt information
    existing_mortgage_assumed: float = Field(
        default=0.0, ge=0,
        description="Existing mortgage assumed by buyer"
    )
    seller_financing: float = Field(
        default=0.0, ge=0,
        description="Amount financed by seller (installment note)"
    )

    # Payment tracking
    total_payments_prior_years: float = Field(
        default=0.0, ge=0,
        description="Total principal payments received in prior years"
    )
    payments_current_year: List[InstallmentPayment] = Field(
        default_factory=list,
        description="Payments received in current year"
    )

    # Related party information
    related_party_type: RelatedPartyType = Field(default=RelatedPartyType.NOT_RELATED)
    buyer_name: Optional[str] = Field(default=None)
    buyer_ssn_ein: Optional[str] = Field(default=None)  # Last 4 digits only for privacy

    # Related party resale tracking (Section 453(e))
    related_party_resold: bool = Field(default=False)
    resale_date: Optional[str] = Field(default=None)
    resale_amount: float = Field(default=0.0, ge=0)

    # Large installment sale (Section 453A - interest charge on deferred tax)
    is_large_installment_sale: bool = Field(
        default=False,
        description="Sale > $5,000,000 threshold (Section 453A)"
    )

    # Pledging (Section 453A(d))
    amount_pledged: float = Field(
        default=0.0, ge=0,
        description="Amount of installment obligation used as collateral"
    )

    def get_gross_profit(self) -> float:
        """
        Calculate gross profit from the sale.

        Gross Profit = Selling Price - Adjusted Basis - Selling Expenses
        """
        return max(0.0, self.selling_price - self.adjusted_basis - self.selling_expenses)

    def get_contract_price(self) -> float:
        """
        Calculate contract price for gross profit percentage.

        Contract Price = Selling Price - Mortgage Assumed (but not below adjusted basis)

        If mortgage exceeds basis, the excess is treated as a payment in year of sale.
        """
        # Start with selling price
        contract_price = self.selling_price

        # Subtract mortgage assumed by buyer
        contract_price -= self.existing_mortgage_assumed

        # Contract price cannot be less than gross profit
        gross_profit = self.get_gross_profit()
        return max(contract_price, gross_profit)

    def get_gross_profit_percentage(self) -> float:
        """
        Calculate gross profit percentage.

        GP% = Gross Profit / Contract Price

        This percentage is applied to each principal payment to determine
        the taxable gain portion.
        """
        contract_price = self.get_contract_price()
        if contract_price <= 0:
            return 0.0

        gross_profit = self.get_gross_profit()
        return min(1.0, gross_profit / contract_price)  # Cap at 100%

    def get_mortgage_excess(self) -> float:
        """
        Calculate excess mortgage over adjusted basis.

        If mortgage assumed by buyer exceeds seller's adjusted basis,
        the excess is treated as a payment received in year of sale.
        """
        return max(0.0, self.existing_mortgage_assumed - self.adjusted_basis)

    def get_year_of_sale_payments(self) -> float:
        """
        Calculate total payments considered received in year of sale.

        Includes:
        - Actual cash received
        - Mortgage excess over basis (treated as payment)
        """
        # For year of sale, also include mortgage excess
        # This is simplified - actual tracking would be per-year
        return self.get_mortgage_excess()

    def get_current_year_principal(self) -> float:
        """Get total principal received in current year."""
        return sum(p.principal_portion for p in self.payments_current_year)

    def get_current_year_interest(self) -> float:
        """Get total interest received in current year (ordinary income)."""
        return sum(p.interest_portion for p in self.payments_current_year)

    def get_remaining_installment_balance(self) -> float:
        """Calculate remaining balance on installment note."""
        total_principal_received = (
            self.total_payments_prior_years +
            self.get_current_year_principal()
        )
        return max(0.0, self.seller_financing - total_principal_received)

    def is_related_party_sale(self) -> bool:
        """Check if this is a related party sale."""
        return self.related_party_type != RelatedPartyType.NOT_RELATED

    def is_depreciable_property_to_related(self) -> bool:
        """
        Check if depreciable property sold to related party.

        Installment method NOT allowed for depreciable property sold
        to a related party (Section 453(g)).
        """
        if not self.is_related_party_sale():
            return False

        return (
            self.property_category == PropertyCategory.DEPRECIABLE_PROPERTY_RELATED or
            self.depreciation_allowed > 0
        )


class Form6252(BaseModel):
    """
    IRS Form 6252 - Installment Sale Income

    Reports income from installment sales under IRC Section 453.

    Part I: Gross Profit and Contract Price
    Part II: Installment Sale Income
    Part III: Related Party Installment Sale Income

    Key Rules:
    1. At least one payment must be received after year of sale
    2. Depreciation recapture recognized in year of sale
    3. Related party sales: Acceleration if resold within 2 years
    4. Large sales (>$5M): Interest charge on deferred tax liability
    5. Securities/inventory: NOT eligible for installment method
    """
    # Current tax year
    tax_year: int = Field(default=2025)

    # All installment obligations (can have multiple sales)
    installment_obligations: List[InstallmentObligation] = Field(default_factory=list)

    # Section 453A interest charge rate (for large installment sales)
    section_453a_interest_rate: float = Field(
        default=0.08,
        description="Interest rate for Section 453A interest charge"
    )

    def calculate_part_i(self, obligation: InstallmentObligation) -> dict:
        """
        Calculate Part I - Gross Profit and Contract Price.

        This establishes the key ratios used to calculate taxable income
        from installment payments.
        """
        result = {
            # Line 5: Selling price
            'line_5_selling_price': obligation.selling_price,
            # Line 6: Mortgages and debts assumed by buyer
            'line_6_mortgages_assumed': obligation.existing_mortgage_assumed,
            # Line 7: Subtract line 6 from line 5
            'line_7_subtotal': obligation.selling_price - obligation.existing_mortgage_assumed,
            # Line 8: Cost or other basis
            'line_8_basis': obligation.adjusted_basis,
            # Line 9: Depreciation allowed
            'line_9_depreciation': obligation.depreciation_allowed,
            # Line 10: Adjusted basis (line 8 - line 9)
            'line_10_adjusted_basis': obligation.adjusted_basis - obligation.depreciation_allowed,
            # Line 11: Commissions and expenses
            'line_11_expenses': obligation.selling_expenses,
            # Line 12: Income recapture (Sections 1245, 1250, etc.)
            'line_12_recapture': (
                obligation.section_1245_recapture +
                obligation.section_1250_recapture
            ),
            # Line 13: Add lines 10, 11, and 12
            'line_13_total_basis': 0.0,
            # Line 14: Subtract line 13 from line 5 = Gross Profit
            'line_14_gross_profit': 0.0,
            # Line 15: If line 6 > line 13, subtract line 13 from line 6; else 0
            'line_15_mortgage_excess': 0.0,
            # Line 16: Subtract line 15 from line 7 (if positive, else 0)
            'line_16_subtotal': 0.0,
            # Line 17: Larger of line 16 or line 14 = Contract Price
            'line_17_contract_price': 0.0,
            # Line 18: Gross Profit Percentage (line 14 / line 17)
            'line_18_gp_percentage': 0.0,
        }

        # Calculate adjusted basis (basis - depreciation already taken)
        result['line_10_adjusted_basis'] = max(
            0.0,
            obligation.adjusted_basis - obligation.depreciation_allowed
        )

        # Line 13: Total to subtract from selling price
        result['line_13_total_basis'] = (
            result['line_10_adjusted_basis'] +
            result['line_11_expenses'] +
            result['line_12_recapture']
        )

        # Line 14: Gross Profit
        result['line_14_gross_profit'] = max(
            0.0,
            obligation.selling_price - result['line_13_total_basis']
        )

        # Line 15: Mortgage excess over total basis (if any)
        if obligation.existing_mortgage_assumed > result['line_13_total_basis']:
            result['line_15_mortgage_excess'] = (
                obligation.existing_mortgage_assumed - result['line_13_total_basis']
            )

        # Line 16: Line 7 minus Line 15
        result['line_16_subtotal'] = max(
            0.0,
            result['line_7_subtotal'] - result['line_15_mortgage_excess']
        )

        # Line 17: Contract Price = larger of Line 16 or Line 14
        result['line_17_contract_price'] = max(
            result['line_16_subtotal'],
            result['line_14_gross_profit']
        )

        # Line 18: Gross Profit Percentage
        if result['line_17_contract_price'] > 0:
            result['line_18_gp_percentage'] = (
                result['line_14_gross_profit'] / result['line_17_contract_price']
            )

        return result

    def calculate_part_ii(
        self,
        obligation: InstallmentObligation,
        is_year_of_sale: bool = False
    ) -> dict:
        """
        Calculate Part II - Installment Sale Income.

        Applies gross profit percentage to payments received to determine
        taxable installment sale income.
        """
        part_i = self.calculate_part_i(obligation)
        gp_percentage = part_i['line_18_gp_percentage']

        result = {
            'is_year_of_sale': is_year_of_sale,
            # Line 19: Gross profit percentage from Part I
            'line_19_gp_percentage': gp_percentage,
            # Line 20: Payments received this year (excluding interest)
            'line_20_payments_received': 0.0,
            # Line 21: Payments times GP% = Installment sale income
            'line_21_installment_income': 0.0,
            # Line 22: Section 1250 gain (Part II, line 26 of Form 4797)
            'line_22_section_1250_gain': 0.0,
            # Line 23: Subtract line 22 from line 21
            'line_23_remaining_gain': 0.0,
            # Line 24: Section 1250 portion taxed at 25%
            'line_24_section_1250_at_25': 0.0,
            # Line 25: Remaining gain (line 23 - line 24)
            'line_25_capital_gain': 0.0,
            # Interest income (ordinary)
            'interest_income': 0.0,
            # Recapture income (recognized in year of sale only)
            'depreciation_recapture': 0.0,
        }

        # Calculate payments received
        if is_year_of_sale:
            # Year of sale: Include mortgage excess as deemed payment
            result['line_20_payments_received'] = (
                obligation.get_current_year_principal() +
                part_i['line_15_mortgage_excess']
            )
            # Depreciation recapture recognized in year of sale
            result['depreciation_recapture'] = part_i['line_12_recapture']
        else:
            # Subsequent years: Just actual payments
            result['line_20_payments_received'] = obligation.get_current_year_principal()

        # Line 21: Installment sale income
        result['line_21_installment_income'] = round(
            result['line_20_payments_received'] * gp_percentage,
            2
        )

        # Section 1250 gain allocation
        if obligation.unrecaptured_1250_gain > 0:
            # Unrecaptured 1250 gain is allocated proportionally to payments
            total_remaining = obligation.seller_financing - obligation.total_payments_prior_years
            if total_remaining > 0:
                payment_ratio = result['line_20_payments_received'] / total_remaining
                result['line_24_section_1250_at_25'] = round(
                    min(
                        obligation.unrecaptured_1250_gain * payment_ratio,
                        result['line_21_installment_income']
                    ),
                    2
                )

        # Remaining capital gain
        result['line_25_capital_gain'] = max(
            0.0,
            result['line_21_installment_income'] - result['line_24_section_1250_at_25']
        )

        # Interest income (ordinary income, separate from installment gain)
        result['interest_income'] = obligation.get_current_year_interest()

        return result

    def calculate_part_iii_related_party(self, obligation: InstallmentObligation) -> dict:
        """
        Calculate Part III - Related Party Installment Sale Income.

        Special rules for related party sales (Section 453(e)):
        - If buyer resells within 2 years, seller may have accelerated gain
        - Applies to marketable securities and certain other property
        """
        result = {
            'is_related_party_sale': obligation.is_related_party_sale(),
            'related_party_type': obligation.related_party_type.value,
            'buyer_resold_within_2_years': obligation.related_party_resold,
            'resale_amount': obligation.resale_amount,
            'accelerated_gain': 0.0,
            'reason_for_acceleration': None,
        }

        if not obligation.is_related_party_sale():
            return result

        # Check if depreciable property to related party (not eligible for installment)
        if obligation.is_depreciable_property_to_related():
            result['reason_for_acceleration'] = (
                "Depreciable property to related party - "
                "installment method not allowed (Section 453(g))"
            )
            # All gain recognized in year of sale
            result['accelerated_gain'] = obligation.get_gross_profit()
            return result

        # Check for resale within 2 years
        if obligation.related_party_resold and obligation.resale_date:
            try:
                sale_date = datetime.strptime(obligation.date_sold, "%Y-%m-%d")
                resale_date = datetime.strptime(obligation.resale_date, "%Y-%m-%d")
                days_between = (resale_date - sale_date).days

                if days_between <= 730:  # 2 years
                    # Acceleration triggered
                    # Amount accelerated = lesser of:
                    # 1. Amount realized on resale
                    # 2. Remaining gain not yet recognized
                    remaining_gain = (
                        obligation.get_gross_profit() -
                        obligation.total_payments_prior_years * obligation.get_gross_profit_percentage()
                    )
                    result['accelerated_gain'] = min(
                        obligation.resale_amount,
                        max(0.0, remaining_gain)
                    )
                    result['reason_for_acceleration'] = (
                        f"Related party resold within 2 years ({days_between} days)"
                    )
            except (ValueError, TypeError):
                pass

        return result

    def calculate_section_453a_interest(self, obligation: InstallmentObligation) -> dict:
        """
        Calculate Section 453A interest charge for large installment sales.

        For installment sales > $5,000,000:
        - Interest charge on deferred tax liability
        - Applies to outstanding installment balance at year end
        """
        result = {
            'applies': False,
            'outstanding_balance': 0.0,
            'deferred_tax_liability': 0.0,
            'interest_charge': 0.0,
            'threshold': 5000000.0,
        }

        if not obligation.is_large_installment_sale:
            return result

        if obligation.selling_price <= 5000000:
            return result

        result['applies'] = True
        result['outstanding_balance'] = obligation.get_remaining_installment_balance()

        # Calculate deferred tax liability
        # Simplified: Assume 20% capital gains rate on remaining gain
        gp_percentage = obligation.get_gross_profit_percentage()
        remaining_gain = result['outstanding_balance'] * gp_percentage
        result['deferred_tax_liability'] = remaining_gain * 0.20

        # Interest charge on deferred tax
        result['interest_charge'] = round(
            result['deferred_tax_liability'] * self.section_453a_interest_rate,
            2
        )

        return result

    def calculate_pledging_rules(self, obligation: InstallmentObligation) -> dict:
        """
        Calculate gain from pledging installment obligation.

        Under Section 453A(d), if an installment obligation is pledged
        as collateral, gain is triggered as if payment was received.
        """
        result = {
            'amount_pledged': obligation.amount_pledged,
            'triggered_gain': 0.0,
            'applies': False,
        }

        if obligation.amount_pledged <= 0:
            return result

        result['applies'] = True

        # Gain triggered = amount pledged × gross profit percentage
        gp_percentage = obligation.get_gross_profit_percentage()
        result['triggered_gain'] = round(
            obligation.amount_pledged * gp_percentage,
            2
        )

        return result

    def calculate_for_obligation(
        self,
        obligation: InstallmentObligation,
        is_year_of_sale: bool = False
    ) -> dict:
        """
        Calculate all Form 6252 components for a single obligation.
        """
        part_i = self.calculate_part_i(obligation)
        part_ii = self.calculate_part_ii(obligation, is_year_of_sale)
        part_iii = self.calculate_part_iii_related_party(obligation)
        section_453a = self.calculate_section_453a_interest(obligation)
        pledging = self.calculate_pledging_rules(obligation)

        # Determine total taxable income
        total_ordinary_income = (
            part_ii['interest_income'] +
            part_ii['depreciation_recapture'] +
            part_iii['accelerated_gain']
        )

        total_capital_gain = part_ii['line_25_capital_gain']
        unrecaptured_1250 = part_ii['line_24_section_1250_at_25']

        # Add pledging gain if applicable
        if pledging['applies']:
            total_capital_gain += pledging['triggered_gain']

        return {
            'property_description': obligation.property_description,
            'year_of_sale': obligation.year_of_sale,
            'is_year_of_sale': is_year_of_sale,
            'part_i': part_i,
            'part_ii': part_ii,
            'part_iii': part_iii,
            'section_453a': section_453a,
            'pledging': pledging,
            'summary': {
                'gross_profit': part_i['line_14_gross_profit'],
                'gross_profit_percentage': part_i['line_18_gp_percentage'],
                'contract_price': part_i['line_17_contract_price'],
                'payments_received': part_ii['line_20_payments_received'],
                'installment_income': part_ii['line_21_installment_income'],
                'interest_income': part_ii['interest_income'],
                'depreciation_recapture': part_ii['depreciation_recapture'],
                'related_party_acceleration': part_iii['accelerated_gain'],
                'unrecaptured_1250_gain': unrecaptured_1250,
                'capital_gain': total_capital_gain,
                'ordinary_income': total_ordinary_income,
                'section_453a_interest': section_453a['interest_charge'],
                'pledging_gain': pledging['triggered_gain'],
            }
        }

    def calculate_all(self) -> dict:
        """
        Calculate Form 6252 for all installment obligations.
        """
        results = []
        totals = {
            'total_installment_income': 0.0,
            'total_interest_income': 0.0,
            'total_depreciation_recapture': 0.0,
            'total_capital_gain': 0.0,
            'total_ordinary_income': 0.0,
            'total_unrecaptured_1250': 0.0,
            'total_section_453a_interest': 0.0,
            'total_related_party_acceleration': 0.0,
        }

        for obligation in self.installment_obligations:
            is_year_of_sale = (obligation.year_of_sale == self.tax_year)
            calc = self.calculate_for_obligation(obligation, is_year_of_sale)
            results.append(calc)

            # Aggregate totals
            summary = calc['summary']
            totals['total_installment_income'] += summary['installment_income']
            totals['total_interest_income'] += summary['interest_income']
            totals['total_depreciation_recapture'] += summary['depreciation_recapture']
            totals['total_capital_gain'] += summary['capital_gain']
            totals['total_ordinary_income'] += summary['ordinary_income']
            totals['total_unrecaptured_1250'] += summary['unrecaptured_1250_gain']
            totals['total_section_453a_interest'] += summary['section_453a_interest']
            totals['total_related_party_acceleration'] += summary['related_party_acceleration']

        return {
            'tax_year': self.tax_year,
            'obligations': results,
            'totals': totals,
            'obligation_count': len(self.installment_obligations),
        }

    def get_total_installment_income(self) -> float:
        """Get total installment sale income (capital gain portion)."""
        result = self.calculate_all()
        return result['totals']['total_installment_income']

    def get_total_interest_income(self) -> float:
        """Get total interest income (ordinary income)."""
        result = self.calculate_all()
        return result['totals']['total_interest_income']

    def get_total_depreciation_recapture(self) -> float:
        """Get total depreciation recapture (ordinary income)."""
        result = self.calculate_all()
        return result['totals']['total_depreciation_recapture']

    def get_total_capital_gain(self) -> float:
        """Get total capital gain from installment sales."""
        result = self.calculate_all()
        return result['totals']['total_capital_gain']

    def get_total_ordinary_income(self) -> float:
        """Get total ordinary income (interest + recapture + acceleration)."""
        result = self.calculate_all()
        return result['totals']['total_ordinary_income']

    def get_unrecaptured_1250_gain(self) -> float:
        """Get total unrecaptured Section 1250 gain (25% rate)."""
        result = self.calculate_all()
        return result['totals']['total_unrecaptured_1250']

    def get_section_453a_interest_charge(self) -> float:
        """Get Section 453A interest charge for large installment sales."""
        result = self.calculate_all()
        return result['totals']['total_section_453a_interest']

    def generate_form_6252_summary(self) -> dict:
        """Generate comprehensive Form 6252 summary."""
        result = self.calculate_all()

        return {
            'tax_year': self.tax_year,
            'total_obligations': result['obligation_count'],
            'obligations': [
                {
                    'property': calc['property_description'],
                    'year_of_sale': calc['year_of_sale'],
                    'gross_profit_pct': f"{calc['summary']['gross_profit_percentage'] * 100:.2f}%",
                    'payments_received': calc['summary']['payments_received'],
                    'installment_income': calc['summary']['installment_income'],
                    'interest_income': calc['summary']['interest_income'],
                }
                for calc in result['obligations']
            ],
            'totals': {
                'installment_income': result['totals']['total_installment_income'],
                'interest_income': result['totals']['total_interest_income'],
                'depreciation_recapture': result['totals']['total_depreciation_recapture'],
                'capital_gain': result['totals']['total_capital_gain'],
                'ordinary_income': result['totals']['total_ordinary_income'],
                'unrecaptured_1250': result['totals']['total_unrecaptured_1250'],
                'section_453a_interest': result['totals']['total_section_453a_interest'],
            }
        }


def calculate_installment_eligibility(
    property_type: str,
    is_inventory: bool = False,
    is_publicly_traded: bool = False,
    is_related_party_depreciable: bool = False
) -> dict:
    """
    Determine if property is eligible for installment sale treatment.

    NOT eligible:
    - Inventory property
    - Publicly traded securities
    - Depreciable property sold to related party
    """
    result = {
        'eligible': True,
        'reason': None,
    }

    if is_inventory:
        result['eligible'] = False
        result['reason'] = "Inventory property not eligible for installment method"
    elif is_publicly_traded:
        result['eligible'] = False
        result['reason'] = "Publicly traded securities not eligible"
    elif is_related_party_depreciable:
        result['eligible'] = False
        result['reason'] = "Depreciable property to related party not eligible (Section 453(g))"

    return result
