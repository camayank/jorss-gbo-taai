"""
Form 4797 - Sales of Business Property

Implements IRS Form 4797 for reporting:
- Part I: Sales or exchanges of property used in trade/business (Section 1231)
- Part II: Ordinary gains and losses (property held <= 1 year, recapture)
- Part III: Gain from disposition (Sections 1245, 1250, 1252, 1254, 1255)
- Part IV: Recapture amounts (Sections 179 and 280F(b)(2))

Key IRC Sections:
- Section 1231: Trade/business property held > 1 year (favorable treatment)
- Section 1245: Depreciation recapture on personal property (100% ordinary)
- Section 1250: Depreciation recapture on real property (25% rate cap)
- Section 179: Recapture when business use drops below 50%
- Section 280F(b)(2): Listed property recapture
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class PropertyType(str, Enum):
    """Types of property for Form 4797 purposes."""
    # Section 1245 Property (personal property - full recapture)
    MACHINERY_EQUIPMENT = "machinery_equipment"
    VEHICLES = "vehicles"
    OFFICE_EQUIPMENT = "office_equipment"
    COMPUTERS = "computers"
    FURNITURE_FIXTURES = "furniture_fixtures"

    # Section 1250 Property (real property - partial recapture)
    RESIDENTIAL_RENTAL = "residential_rental"  # 27.5-year property
    COMMERCIAL_BUILDING = "commercial_building"  # 39-year property
    LAND_IMPROVEMENTS = "land_improvements"  # 15-year property

    # Other Section 1231 Property
    LAND = "land"  # Not depreciable, but Section 1231
    TIMBER = "timber"
    LIVESTOCK = "livestock"  # Held for draft, breeding, dairy, sporting
    UNHARVESTED_CROPS = "unharvested_crops"

    # Section 1252 Property
    FARM_LAND = "farm_land"  # With soil/water conservation deductions

    # Section 1254 Property
    OIL_GAS_PROPERTY = "oil_gas_property"
    MINERAL_PROPERTY = "mineral_property"
    GEOTHERMAL_PROPERTY = "geothermal_property"

    # Other
    INTANGIBLES = "intangibles"  # Patents, copyrights (Section 197)
    OTHER = "other"


class DispositionType(str, Enum):
    """Types of property disposition."""
    SALE = "sale"
    EXCHANGE = "exchange"
    INVOLUNTARY_CONVERSION = "involuntary_conversion"  # Casualty, theft, condemnation
    LIKE_KIND_EXCHANGE = "like_kind_exchange"  # Section 1031 (deferred)
    INSTALLMENT_SALE = "installment_sale"  # Section 453
    RELATED_PARTY_SALE = "related_party_sale"
    ABANDONMENT = "abandonment"
    WORTHLESS = "worthless"


class RecaptureType(str, Enum):
    """Types of depreciation recapture."""
    SECTION_1245 = "section_1245"  # Personal property - 100% ordinary
    SECTION_1250 = "section_1250"  # Real property - excess over SL as ordinary
    SECTION_1252 = "section_1252"  # Farm land with soil/water conservation
    SECTION_1254 = "section_1254"  # Natural resource recapture
    SECTION_1255 = "section_1255"  # Section 126 property
    SECTION_179 = "section_179"  # Section 179 recapture
    SECTION_280F = "section_280f"  # Listed property recapture


class Section1231LookbackLoss(BaseModel):
    """
    Track Section 1231 losses from prior 5 years for lookback rule.

    IRS Rule: Net Section 1231 gains are treated as ordinary income
    to the extent of unrecaptured Section 1231 losses from prior 5 years.
    """
    tax_year: int
    loss_amount: float = Field(ge=0)
    recaptured_amount: float = Field(default=0.0, ge=0)

    def get_remaining_loss(self) -> float:
        """Get unrecaptured loss amount."""
        return max(0.0, self.loss_amount - self.recaptured_amount)


class BusinessPropertySale(BaseModel):
    """
    Individual business property sale/disposition for Form 4797.

    Tracks all information needed to calculate:
    - Gain or loss on disposition
    - Section 1245/1250 depreciation recapture
    - Section 1231 gain/loss classification
    - Unrecaptured Section 1250 gain (25% rate)
    """
    # Property identification
    description: str = Field(description="Description of the property")
    property_type: PropertyType = Field(default=PropertyType.OTHER)

    # Acquisition information
    date_acquired: str = Field(description="Date property was acquired (YYYY-MM-DD)")
    cost_or_other_basis: float = Field(ge=0, description="Original cost or other basis")

    # Depreciation information
    depreciation_allowed: float = Field(
        default=0.0, ge=0,
        description="Total depreciation allowed or allowable"
    )
    section_179_deduction: float = Field(
        default=0.0, ge=0,
        description="Section 179 expense deduction taken"
    )
    bonus_depreciation: float = Field(
        default=0.0, ge=0,
        description="Bonus depreciation taken"
    )

    # For Section 1250: Track straight-line vs accelerated
    straight_line_depreciation: Optional[float] = Field(
        default=None,
        description="Straight-line depreciation (for Section 1250 additional depreciation)"
    )

    # Sale/disposition information
    date_sold: str = Field(description="Date property was sold/disposed (YYYY-MM-DD)")
    gross_sales_price: float = Field(ge=0, description="Gross sales price")
    selling_expenses: float = Field(default=0.0, ge=0, description="Commissions, legal fees, etc.")
    disposition_type: DispositionType = Field(default=DispositionType.SALE)

    # Special situations
    is_related_party_transaction: bool = Field(default=False)
    is_installment_sale: bool = Field(default=False)
    installment_sale_payments_received: float = Field(default=0.0, ge=0)

    # For involuntary conversions
    insurance_or_other_reimbursement: float = Field(default=0.0, ge=0)

    # Section 179/280F recapture (when business use drops)
    prior_business_use_percentage: float = Field(default=100.0, ge=0, le=100)
    current_business_use_percentage: float = Field(default=100.0, ge=0, le=100)
    is_listed_property: bool = Field(default=False)

    def get_holding_period_days(self) -> int:
        """Calculate holding period in days."""
        try:
            acquired = datetime.strptime(self.date_acquired, "%Y-%m-%d")
            sold = datetime.strptime(self.date_sold, "%Y-%m-%d")
            return (sold - acquired).days
        except (ValueError, TypeError):
            return 0

    def is_long_term(self) -> bool:
        """Check if property was held more than 1 year (Section 1231 eligibility)."""
        return self.get_holding_period_days() > 365

    def get_adjusted_basis(self) -> float:
        """
        Calculate adjusted basis at time of sale.

        Adjusted Basis = Cost Basis - All Depreciation
        """
        total_depreciation = (
            self.depreciation_allowed +
            self.section_179_deduction +
            self.bonus_depreciation
        )
        return max(0.0, self.cost_or_other_basis - total_depreciation)

    def get_amount_realized(self) -> float:
        """
        Calculate amount realized from sale.

        Amount Realized = Gross Sales Price - Selling Expenses
        """
        if self.disposition_type == DispositionType.INVOLUNTARY_CONVERSION:
            return self.insurance_or_other_reimbursement - self.selling_expenses
        return self.gross_sales_price - self.selling_expenses

    def get_total_gain_loss(self) -> float:
        """
        Calculate total gain or loss.

        Gain/Loss = Amount Realized - Adjusted Basis
        """
        return self.get_amount_realized() - self.get_adjusted_basis()

    def is_section_1245_property(self) -> bool:
        """Check if property is Section 1245 (personal property with full recapture)."""
        return self.property_type in [
            PropertyType.MACHINERY_EQUIPMENT,
            PropertyType.VEHICLES,
            PropertyType.OFFICE_EQUIPMENT,
            PropertyType.COMPUTERS,
            PropertyType.FURNITURE_FIXTURES,
            PropertyType.INTANGIBLES,
        ]

    def is_section_1250_property(self) -> bool:
        """Check if property is Section 1250 (real property with partial recapture)."""
        return self.property_type in [
            PropertyType.RESIDENTIAL_RENTAL,
            PropertyType.COMMERCIAL_BUILDING,
            PropertyType.LAND_IMPROVEMENTS,
        ]

    def is_section_1231_property(self) -> bool:
        """
        Check if property qualifies for Section 1231 treatment.

        Section 1231 applies to depreciable/real property used in trade/business
        and held more than 1 year.
        """
        if not self.is_long_term():
            return False

        # Land and depreciable business property qualify
        return self.property_type not in [
            PropertyType.OTHER,  # May need more specific handling
        ]

    def calculate_section_1245_recapture(self) -> float:
        """
        Calculate Section 1245 depreciation recapture.

        Section 1245: ALL depreciation is recaptured as ordinary income,
        limited to the gain on the property.
        """
        if not self.is_section_1245_property():
            return 0.0

        gain = self.get_total_gain_loss()
        if gain <= 0:
            return 0.0

        # Total depreciation subject to recapture
        total_depreciation = (
            self.depreciation_allowed +
            self.section_179_deduction +
            self.bonus_depreciation
        )

        # Recapture is lesser of gain or total depreciation
        return min(gain, total_depreciation)

    def calculate_section_1250_recapture(self) -> dict:
        """
        Calculate Section 1250 depreciation recapture.

        Section 1250 has two components:
        1. Additional depreciation (excess over straight-line) - ordinary income
        2. Unrecaptured Section 1250 gain - taxed at max 25%

        Returns:
            Dict with 'ordinary_income' and 'unrecaptured_1250_gain'
        """
        result = {
            'ordinary_income': 0.0,
            'unrecaptured_1250_gain': 0.0,
            'section_1231_gain': 0.0,
        }

        if not self.is_section_1250_property():
            return result

        gain = self.get_total_gain_loss()
        if gain <= 0:
            return result

        total_depreciation = (
            self.depreciation_allowed +
            self.section_179_deduction +
            self.bonus_depreciation
        )

        # Calculate additional depreciation (excess over straight-line)
        # For post-1986 real property, there's usually no additional depreciation
        # because MACRS uses straight-line for real property
        straight_line = self.straight_line_depreciation
        if straight_line is None:
            # Assume MACRS straight-line (no additional depreciation for post-1986)
            straight_line = total_depreciation

        additional_depreciation = max(0.0, total_depreciation - straight_line)

        # Additional depreciation is ordinary income (limited to gain)
        result['ordinary_income'] = min(gain, additional_depreciation)

        remaining_gain = gain - result['ordinary_income']

        # Unrecaptured Section 1250 gain = remaining depreciation (up to remaining gain)
        remaining_depreciation = total_depreciation - additional_depreciation
        result['unrecaptured_1250_gain'] = min(remaining_gain, remaining_depreciation)

        # Any remaining gain is Section 1231 gain
        result['section_1231_gain'] = max(
            0.0,
            remaining_gain - result['unrecaptured_1250_gain']
        )

        return result

    def calculate_section_179_recapture(self) -> float:
        """
        Calculate Section 179 recapture when business use drops below 50%.

        IRC Section 179(d)(10): If business use drops below 50%,
        recapture = (Section 179 deduction) - (MACRS depreciation that would have been allowed)
        """
        if self.section_179_deduction <= 0:
            return 0.0

        # Recapture triggers when business use drops below 50%
        if self.current_business_use_percentage >= 50:
            return 0.0

        # This is a simplified calculation
        # Full calculation would need recovery period and year of recapture
        # Recapture amount is Section 179 minus what MACRS would have allowed
        return self.section_179_deduction


class Form4797(BaseModel):
    """
    IRS Form 4797 - Sales of Business Property.

    Handles:
    - Part I: Section 1231 gains/losses (property held > 1 year)
    - Part II: Ordinary gains/losses (property held <= 1 year, recapture)
    - Part III: Depreciation recapture (Sections 1245, 1250, 1252, 1254, 1255)
    - Part IV: Section 179/280F recapture

    Section 1231 Lookback Rule:
    Net Section 1231 gains are treated as ordinary income to the extent
    of unrecaptured Section 1231 losses from the prior 5 years.
    """
    # Property sales for the year
    property_sales: List[BusinessPropertySale] = Field(default_factory=list)

    # Section 1231 5-year lookback losses
    prior_section_1231_losses: List[Section1231LookbackLoss] = Field(
        default_factory=list,
        description="Section 1231 losses from prior 5 years for lookback rule"
    )

    # Pass-through Section 1231 gain/loss from partnerships/S-corps
    passthrough_section_1231_gain: float = Field(
        default=0.0,
        description="Net Section 1231 gain from K-1s (partnerships/S-corps)"
    )
    passthrough_section_1231_loss: float = Field(
        default=0.0, ge=0,
        description="Net Section 1231 loss from K-1s"
    )

    # Pass-through ordinary income from recapture
    passthrough_ordinary_recapture: float = Field(
        default=0.0, ge=0,
        description="Ordinary income from depreciation recapture on K-1s"
    )

    def calculate_part_i(self, current_year: int = 2025) -> dict:
        """
        Calculate Part I - Sales or Exchanges of Property Used in Trade/Business.

        Section 1231 transactions (property held > 1 year):
        - Net gain: Treated as long-term capital gain
        - Net loss: Treated as ordinary loss

        Subject to 5-year lookback rule for prior Section 1231 losses.

        Returns:
            Dict with Part I calculation results
        """
        result = {
            'line_2_section_1231_gains': 0.0,
            'line_3_section_1231_losses': 0.0,
            'line_6_gain_from_part_iii': 0.0,  # Section 1231 gain from Part III
            'line_7_net_section_1231_gain_loss': 0.0,
            'line_8_lookback_recapture': 0.0,
            'line_9_net_section_1231_gain': 0.0,
            'property_details': [],
            'goes_to_schedule_d': False,
            'is_long_term_capital_gain': False,
            'is_ordinary_loss': False,
        }

        # Process each property sale
        for sale in self.property_sales:
            if not sale.is_long_term():
                continue  # Short-term goes to Part II

            if not sale.is_section_1231_property():
                continue

            gain_loss = sale.get_total_gain_loss()

            # For Section 1245 property, the recapture is ordinary income (Part III)
            # The remaining gain (if any) is Section 1231 gain
            if sale.is_section_1245_property():
                recapture = sale.calculate_section_1245_recapture()
                section_1231_portion = max(0.0, gain_loss - recapture)
                if section_1231_portion > 0:
                    result['line_2_section_1231_gains'] += section_1231_portion
                elif gain_loss < 0:
                    result['line_3_section_1231_losses'] += abs(gain_loss)

            # For Section 1250 property
            elif sale.is_section_1250_property():
                recapture_result = sale.calculate_section_1250_recapture()
                # Section 1231 gain from real property (after recapture)
                section_1231_portion = recapture_result['section_1231_gain']
                if section_1231_portion > 0:
                    result['line_2_section_1231_gains'] += section_1231_portion
                # Note: unrecaptured 1250 gain tracked separately
                if gain_loss < 0:
                    result['line_3_section_1231_losses'] += abs(gain_loss)

            # Other Section 1231 property (land, livestock, etc.)
            else:
                if gain_loss > 0:
                    result['line_2_section_1231_gains'] += gain_loss
                else:
                    result['line_3_section_1231_losses'] += abs(gain_loss)

            result['property_details'].append({
                'description': sale.description,
                'gain_loss': gain_loss,
                'property_type': sale.property_type.value,
                'holding_period_days': sale.get_holding_period_days(),
            })

        # Add pass-through Section 1231 from K-1s
        result['line_2_section_1231_gains'] += max(0.0, self.passthrough_section_1231_gain)
        result['line_3_section_1231_losses'] += self.passthrough_section_1231_loss

        # Line 7: Net Section 1231 gain or loss
        net_1231 = (
            result['line_2_section_1231_gains'] -
            result['line_3_section_1231_losses'] +
            result['line_6_gain_from_part_iii']
        )
        result['line_7_net_section_1231_gain_loss'] = net_1231

        # Apply 5-year lookback rule if net gain
        if net_1231 > 0:
            # Calculate unrecaptured losses from prior 5 years
            lookback_recapture = self._calculate_lookback_recapture(net_1231, current_year)
            result['line_8_lookback_recapture'] = lookback_recapture

            # Net Section 1231 gain after lookback (goes to Schedule D)
            result['line_9_net_section_1231_gain'] = net_1231 - lookback_recapture

            if result['line_9_net_section_1231_gain'] > 0:
                result['goes_to_schedule_d'] = True
                result['is_long_term_capital_gain'] = True
        else:
            # Net Section 1231 loss is ordinary loss
            result['is_ordinary_loss'] = True

        return result

    def _calculate_lookback_recapture(self, net_gain: float, current_year: int) -> float:
        """
        Calculate Section 1231 lookback recapture.

        Net Section 1231 gains are treated as ordinary income to the extent
        of unrecaptured Section 1231 losses from the prior 5 tax years.
        """
        if net_gain <= 0:
            return 0.0

        # Get losses from prior 5 years
        cutoff_year = current_year - 5
        unrecaptured_losses = 0.0

        for loss in self.prior_section_1231_losses:
            if loss.tax_year >= cutoff_year:
                unrecaptured_losses += loss.get_remaining_loss()

        # Recapture is lesser of net gain or unrecaptured losses
        return min(net_gain, unrecaptured_losses)

    def calculate_part_ii(self) -> dict:
        """
        Calculate Part II - Ordinary Gains and Losses.

        Includes:
        - Property held 1 year or less
        - Depreciation recapture from Part III
        - Section 179/280F recapture from Part IV

        Returns:
            Dict with Part II calculation results
        """
        result = {
            'line_10_ordinary_gains': 0.0,
            'line_11_ordinary_losses': 0.0,
            'line_12_gain_from_part_iii': 0.0,  # Recapture from Part III
            'line_13_gain_from_part_iv': 0.0,   # Section 179/280F recapture
            'line_17_total_ordinary_gain_loss': 0.0,
            'property_details': [],
        }

        # Process short-term property sales (held <= 1 year)
        for sale in self.property_sales:
            if sale.is_long_term():
                continue  # Long-term goes to Part I

            gain_loss = sale.get_total_gain_loss()

            if gain_loss > 0:
                result['line_10_ordinary_gains'] += gain_loss
            else:
                result['line_11_ordinary_losses'] += abs(gain_loss)

            result['property_details'].append({
                'description': sale.description,
                'gain_loss': gain_loss,
                'property_type': sale.property_type.value,
                'holding_period_days': sale.get_holding_period_days(),
            })

        # Add depreciation recapture from Part III
        part_iii = self.calculate_part_iii()
        result['line_12_gain_from_part_iii'] = part_iii['total_ordinary_income']

        # Add Section 179/280F recapture from Part IV
        part_iv = self.calculate_part_iv()
        result['line_13_gain_from_part_iv'] = part_iv['total_recapture']

        # Add pass-through ordinary recapture from K-1s
        result['line_12_gain_from_part_iii'] += self.passthrough_ordinary_recapture

        # Total ordinary gain/loss
        result['line_17_total_ordinary_gain_loss'] = (
            result['line_10_ordinary_gains'] -
            result['line_11_ordinary_losses'] +
            result['line_12_gain_from_part_iii'] +
            result['line_13_gain_from_part_iv']
        )

        return result

    def calculate_part_iii(self) -> dict:
        """
        Calculate Part III - Gain From Disposition Under Sections 1245, 1250, etc.

        Section 1245: Personal property - ALL depreciation recaptured as ordinary
        Section 1250: Real property - Additional depreciation as ordinary,
                      remaining depreciation at 25% (unrecaptured 1250 gain)

        Returns:
            Dict with Part III calculation results
        """
        result = {
            'section_1245_recapture': 0.0,
            'section_1250_ordinary': 0.0,
            'unrecaptured_1250_gain': 0.0,
            'section_1252_recapture': 0.0,
            'section_1254_recapture': 0.0,
            'section_1255_recapture': 0.0,
            'total_ordinary_income': 0.0,
            'property_details': [],
        }

        for sale in self.property_sales:
            if not sale.is_long_term():
                continue  # Short-term doesn't need recapture split

            gain = sale.get_total_gain_loss()
            if gain <= 0:
                continue  # No recapture on losses

            detail = {
                'description': sale.description,
                'total_gain': gain,
                'section_1245_recapture': 0.0,
                'section_1250_ordinary': 0.0,
                'unrecaptured_1250_gain': 0.0,
                'section_1231_gain': 0.0,
            }

            # Section 1245 property (personal property)
            if sale.is_section_1245_property():
                recapture = sale.calculate_section_1245_recapture()
                result['section_1245_recapture'] += recapture
                detail['section_1245_recapture'] = recapture
                detail['section_1231_gain'] = max(0.0, gain - recapture)

            # Section 1250 property (real property)
            elif sale.is_section_1250_property():
                recapture_result = sale.calculate_section_1250_recapture()
                result['section_1250_ordinary'] += recapture_result['ordinary_income']
                result['unrecaptured_1250_gain'] += recapture_result['unrecaptured_1250_gain']
                detail['section_1250_ordinary'] = recapture_result['ordinary_income']
                detail['unrecaptured_1250_gain'] = recapture_result['unrecaptured_1250_gain']
                detail['section_1231_gain'] = recapture_result['section_1231_gain']

            # Section 1252 (farm land) - simplified
            elif sale.property_type == PropertyType.FARM_LAND:
                # Farm land with soil/water conservation deductions
                # Simplified: treat like Section 1231
                detail['section_1231_gain'] = gain

            # Section 1254 (natural resources) - simplified
            elif sale.property_type in [
                PropertyType.OIL_GAS_PROPERTY,
                PropertyType.MINERAL_PROPERTY,
                PropertyType.GEOTHERMAL_PROPERTY
            ]:
                # Intangible drilling/development costs recapture
                # Simplified: assume full recapture
                result['section_1254_recapture'] += gain
                detail['section_1254_recapture'] = gain

            result['property_details'].append(detail)

        # Total ordinary income from recapture
        result['total_ordinary_income'] = (
            result['section_1245_recapture'] +
            result['section_1250_ordinary'] +
            result['section_1252_recapture'] +
            result['section_1254_recapture'] +
            result['section_1255_recapture']
        )

        return result

    def calculate_part_iv(self) -> dict:
        """
        Calculate Part IV - Section 179 and 280F(b)(2) Recapture.

        Recapture triggers when:
        - Section 179: Business use drops below 50%
        - Section 280F: Listed property business use drops below 50%

        Returns:
            Dict with Part IV calculation results
        """
        result = {
            'section_179_recapture': 0.0,
            'section_280f_recapture': 0.0,
            'total_recapture': 0.0,
            'property_details': [],
        }

        for sale in self.property_sales:
            # Check for Section 179 recapture
            if sale.section_179_deduction > 0:
                if sale.current_business_use_percentage < 50:
                    recapture = sale.calculate_section_179_recapture()
                    result['section_179_recapture'] += recapture
                    result['property_details'].append({
                        'description': sale.description,
                        'recapture_type': 'Section 179',
                        'amount': recapture,
                        'reason': f'Business use dropped to {sale.current_business_use_percentage}%'
                    })

            # Check for Section 280F recapture (listed property)
            if sale.is_listed_property:
                if sale.current_business_use_percentage < 50:
                    # Simplified: recapture excess depreciation
                    recapture = sale.bonus_depreciation  # Simplified calculation
                    result['section_280f_recapture'] += recapture
                    result['property_details'].append({
                        'description': sale.description,
                        'recapture_type': 'Section 280F',
                        'amount': recapture,
                        'reason': f'Listed property business use dropped to {sale.current_business_use_percentage}%'
                    })

        result['total_recapture'] = (
            result['section_179_recapture'] +
            result['section_280f_recapture']
        )

        return result

    def calculate_all(self, current_year: int = 2025) -> dict:
        """
        Calculate all parts of Form 4797.

        Returns:
            Comprehensive dict with all Form 4797 calculations
        """
        part_i = self.calculate_part_i(current_year)
        part_ii = self.calculate_part_ii()
        part_iii = self.calculate_part_iii()
        part_iv = self.calculate_part_iv()

        # Summary totals
        return {
            'part_i': part_i,
            'part_ii': part_ii,
            'part_iii': part_iii,
            'part_iv': part_iv,
            'summary': {
                # Ordinary income (goes to Form 1040 Line 7)
                'total_ordinary_income': part_ii['line_17_total_ordinary_gain_loss'],
                # Section 1231 gain (goes to Schedule D as LTCG)
                'net_section_1231_gain': max(0.0, part_i['line_9_net_section_1231_gain']),
                # Section 1231 loss (goes to Schedule D as ordinary loss)
                'net_section_1231_loss': abs(min(0.0, part_i['line_7_net_section_1231_gain_loss'])),
                # Unrecaptured Section 1250 gain (25% max rate)
                'unrecaptured_1250_gain': part_iii['unrecaptured_1250_gain'],
                # Lookback recapture (ordinary income from prior 1231 losses)
                'lookback_recapture_ordinary': part_i['line_8_lookback_recapture'],
            }
        }

    def get_ordinary_income(self, current_year: int = 2025) -> float:
        """Get total ordinary income from Form 4797."""
        result = self.calculate_all(current_year)
        return result['summary']['total_ordinary_income']

    def get_section_1231_gain_for_schedule_d(self, current_year: int = 2025) -> float:
        """Get net Section 1231 gain for Schedule D (as LTCG)."""
        result = self.calculate_all(current_year)
        return result['summary']['net_section_1231_gain']

    def get_section_1231_loss_for_schedule_d(self, current_year: int = 2025) -> float:
        """Get net Section 1231 loss for Form 1040 (ordinary loss)."""
        result = self.calculate_all(current_year)
        return result['summary']['net_section_1231_loss']

    def get_unrecaptured_1250_gain(self) -> float:
        """Get unrecaptured Section 1250 gain (taxed at max 25%)."""
        part_iii = self.calculate_part_iii()
        return part_iii['unrecaptured_1250_gain']

    def generate_form_4797_summary(self, current_year: int = 2025) -> dict:
        """Generate comprehensive Form 4797 summary."""
        result = self.calculate_all(current_year)

        return {
            'tax_year': current_year,
            'total_property_sales': len(self.property_sales),
            'part_i_section_1231': {
                'gross_gains': result['part_i']['line_2_section_1231_gains'],
                'gross_losses': result['part_i']['line_3_section_1231_losses'],
                'net_gain_loss': result['part_i']['line_7_net_section_1231_gain_loss'],
                'lookback_recapture': result['part_i']['line_8_lookback_recapture'],
                'net_to_schedule_d': result['part_i']['line_9_net_section_1231_gain'],
                'is_long_term_capital_gain': result['part_i']['is_long_term_capital_gain'],
                'is_ordinary_loss': result['part_i']['is_ordinary_loss'],
            },
            'part_ii_ordinary': {
                'ordinary_gains': result['part_ii']['line_10_ordinary_gains'],
                'ordinary_losses': result['part_ii']['line_11_ordinary_losses'],
                'recapture_from_part_iii': result['part_ii']['line_12_gain_from_part_iii'],
                'recapture_from_part_iv': result['part_ii']['line_13_gain_from_part_iv'],
                'total_ordinary': result['part_ii']['line_17_total_ordinary_gain_loss'],
            },
            'part_iii_recapture': {
                'section_1245': result['part_iii']['section_1245_recapture'],
                'section_1250_ordinary': result['part_iii']['section_1250_ordinary'],
                'unrecaptured_1250_gain': result['part_iii']['unrecaptured_1250_gain'],
                'total_ordinary': result['part_iii']['total_ordinary_income'],
            },
            'part_iv_179_280f': {
                'section_179_recapture': result['part_iv']['section_179_recapture'],
                'section_280f_recapture': result['part_iv']['section_280f_recapture'],
                'total_recapture': result['part_iv']['total_recapture'],
            },
            'summary': result['summary'],
        }
