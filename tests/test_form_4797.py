"""
Tests for Form 4797 - Sales of Business Property

Tests cover:
- Part I: Section 1231 gains/losses (long-term business property)
- Part II: Ordinary gains/losses (short-term, recapture)
- Part III: Depreciation recapture (Sections 1245, 1250)
- Part IV: Section 179/280F recapture
- 5-year lookback rule for prior Section 1231 losses
- Integration with tax calculation engine
"""

import pytest
from models.form_4797 import (
    Form4797,
    BusinessPropertySale,
    PropertyType,
    DispositionType,
    RecaptureType,
    Section1231LookbackLoss,
)
from models.income import Income, W2Info
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


# ============== Helper Functions ==============

def make_property_sale(
    description: str = "Test Property",
    property_type: PropertyType = PropertyType.MACHINERY_EQUIPMENT,
    date_acquired: str = "2020-01-01",
    cost_basis: float = 50000.0,
    depreciation: float = 20000.0,
    date_sold: str = "2025-06-15",
    sales_price: float = 40000.0,
    selling_expenses: float = 1000.0,
    section_179: float = 0.0,
    bonus_depreciation: float = 0.0,
) -> BusinessPropertySale:
    """Helper to create BusinessPropertySale for tests."""
    return BusinessPropertySale(
        description=description,
        property_type=property_type,
        date_acquired=date_acquired,
        cost_or_other_basis=cost_basis,
        depreciation_allowed=depreciation,
        section_179_deduction=section_179,
        bonus_depreciation=bonus_depreciation,
        date_sold=date_sold,
        gross_sales_price=sales_price,
        selling_expenses=selling_expenses,
    )


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def create_tax_return(form_4797: Form4797 = None, wages: float = 50000.0) -> TaxReturn:
    """Helper to create TaxReturn with Form 4797."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            w2_forms=[make_w2(wages, wages * 0.15)],
            form_4797=form_4797,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


# ============== BusinessPropertySale Tests ==============

class TestBusinessPropertySale:
    """Tests for individual property sale calculations."""

    def test_holding_period_calculation(self):
        """Test holding period calculation."""
        sale = make_property_sale(
            date_acquired="2020-01-01",
            date_sold="2025-06-15",
        )
        days = sale.get_holding_period_days()
        assert days > 365 * 5  # More than 5 years
        assert sale.is_long_term() is True

    def test_short_term_holding_period(self):
        """Test short-term holding period (< 1 year)."""
        sale = make_property_sale(
            date_acquired="2025-01-01",
            date_sold="2025-06-15",
        )
        assert sale.is_long_term() is False

    def test_adjusted_basis_calculation(self):
        """Test adjusted basis with depreciation."""
        sale = make_property_sale(
            cost_basis=100000.0,
            depreciation=30000.0,
            section_179=10000.0,
            bonus_depreciation=5000.0,
        )
        # Adjusted basis = 100000 - 30000 - 10000 - 5000 = 55000
        assert sale.get_adjusted_basis() == 55000.0

    def test_amount_realized(self):
        """Test amount realized from sale."""
        sale = make_property_sale(
            sales_price=80000.0,
            selling_expenses=5000.0,
        )
        # Amount realized = 80000 - 5000 = 75000
        assert sale.get_amount_realized() == 75000.0

    def test_gain_calculation(self):
        """Test gain calculation."""
        sale = make_property_sale(
            cost_basis=50000.0,
            depreciation=20000.0,
            sales_price=45000.0,
            selling_expenses=1000.0,
        )
        # Adjusted basis = 50000 - 20000 = 30000
        # Amount realized = 45000 - 1000 = 44000
        # Gain = 44000 - 30000 = 14000
        assert sale.get_total_gain_loss() == 14000.0

    def test_loss_calculation(self):
        """Test loss calculation."""
        sale = make_property_sale(
            cost_basis=50000.0,
            depreciation=10000.0,
            sales_price=35000.0,
            selling_expenses=2000.0,
        )
        # Adjusted basis = 50000 - 10000 = 40000
        # Amount realized = 35000 - 2000 = 33000
        # Loss = 33000 - 40000 = -7000
        assert sale.get_total_gain_loss() == -7000.0

    def test_is_section_1245_property(self):
        """Test Section 1245 property classification."""
        equipment = make_property_sale(property_type=PropertyType.MACHINERY_EQUIPMENT)
        assert equipment.is_section_1245_property() is True

        building = make_property_sale(property_type=PropertyType.COMMERCIAL_BUILDING)
        assert building.is_section_1245_property() is False

    def test_is_section_1250_property(self):
        """Test Section 1250 property classification."""
        building = make_property_sale(property_type=PropertyType.RESIDENTIAL_RENTAL)
        assert building.is_section_1250_property() is True

        equipment = make_property_sale(property_type=PropertyType.MACHINERY_EQUIPMENT)
        assert equipment.is_section_1250_property() is False


# ============== Section 1245 Recapture Tests ==============

class TestSection1245Recapture:
    """Tests for Section 1245 depreciation recapture (personal property)."""

    def test_full_recapture_when_gain_exceeds_depreciation(self):
        """All depreciation recaptured when gain > depreciation."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=50000.0,
            depreciation=20000.0,  # Total depreciation
            sales_price=60000.0,
            selling_expenses=0.0,
        )
        # Adjusted basis = 50000 - 20000 = 30000
        # Amount realized = 60000
        # Gain = 60000 - 30000 = 30000
        # Recapture = min(30000 gain, 20000 depreciation) = 20000
        assert sale.calculate_section_1245_recapture() == 20000.0

    def test_partial_recapture_when_gain_less_than_depreciation(self):
        """Recapture limited to gain when gain < depreciation."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=50000.0,
            depreciation=30000.0,
            sales_price=35000.0,
            selling_expenses=0.0,
        )
        # Adjusted basis = 50000 - 30000 = 20000
        # Gain = 35000 - 20000 = 15000
        # Recapture = min(15000 gain, 30000 depreciation) = 15000
        assert sale.calculate_section_1245_recapture() == 15000.0

    def test_no_recapture_on_loss(self):
        """No recapture when property sold at a loss."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=50000.0,
            depreciation=10000.0,
            sales_price=30000.0,
            selling_expenses=0.0,
        )
        # Adjusted basis = 40000, Sale = 30000, Loss = -10000
        assert sale.calculate_section_1245_recapture() == 0.0

    def test_recapture_includes_section_179(self):
        """Section 179 deduction included in recapture."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=50000.0,
            depreciation=10000.0,
            section_179=15000.0,
            sales_price=50000.0,
            selling_expenses=0.0,
        )
        # Adjusted basis = 50000 - 10000 - 15000 = 25000
        # Gain = 50000 - 25000 = 25000
        # Total depreciation = 10000 + 15000 = 25000
        # Recapture = min(25000, 25000) = 25000
        assert sale.calculate_section_1245_recapture() == 25000.0


# ============== Section 1250 Recapture Tests ==============

class TestSection1250Recapture:
    """Tests for Section 1250 depreciation recapture (real property)."""

    def test_section_1250_with_no_additional_depreciation(self):
        """Real property with straight-line only (no ordinary recapture)."""
        sale = BusinessPropertySale(
            description="Commercial Building",
            property_type=PropertyType.COMMERCIAL_BUILDING,
            date_acquired="2015-01-01",
            cost_or_other_basis=500000.0,
            depreciation_allowed=100000.0,  # Straight-line
            straight_line_depreciation=100000.0,  # Same as allowed
            date_sold="2025-06-15",
            gross_sales_price=550000.0,
            selling_expenses=10000.0,
        )
        result = sale.calculate_section_1250_recapture()
        # No additional depreciation (SL = total)
        assert result['ordinary_income'] == 0.0
        # Unrecaptured 1250 = min(gain, depreciation) up to remaining gain
        # Adjusted basis = 400000, Realized = 540000, Gain = 140000
        # Unrecaptured = min(100000 depreciation, gain after ordinary) = 100000
        assert result['unrecaptured_1250_gain'] == 100000.0
        # Remaining Section 1231 gain = 140000 - 0 - 100000 = 40000
        assert result['section_1231_gain'] == 40000.0

    def test_section_1250_with_additional_depreciation(self):
        """Real property with excess depreciation (pre-1987 property)."""
        sale = BusinessPropertySale(
            description="Old Building",
            property_type=PropertyType.RESIDENTIAL_RENTAL,
            date_acquired="1980-01-01",
            cost_or_other_basis=200000.0,
            depreciation_allowed=150000.0,
            straight_line_depreciation=100000.0,  # Less than total
            date_sold="2025-06-15",
            gross_sales_price=180000.0,
            selling_expenses=5000.0,
        )
        result = sale.calculate_section_1250_recapture()
        # Adjusted basis = 200000 - 150000 = 50000
        # Realized = 175000
        # Gain = 175000 - 50000 = 125000
        # Additional depreciation = 150000 - 100000 = 50000
        # Ordinary income = min(125000, 50000) = 50000
        assert result['ordinary_income'] == 50000.0
        # Remaining gain = 125000 - 50000 = 75000
        # Remaining depreciation = 150000 - 50000 = 100000
        # Unrecaptured = min(75000, 100000) = 75000
        assert result['unrecaptured_1250_gain'] == 75000.0

    def test_no_section_1250_recapture_on_loss(self):
        """No recapture when real property sold at loss."""
        sale = make_property_sale(
            property_type=PropertyType.COMMERCIAL_BUILDING,
            cost_basis=500000.0,
            depreciation=100000.0,
            sales_price=350000.0,
            selling_expenses=10000.0,
        )
        result = sale.calculate_section_1250_recapture()
        assert result['ordinary_income'] == 0.0
        assert result['unrecaptured_1250_gain'] == 0.0


# ============== Form 4797 Part I Tests ==============

class TestForm4797PartI:
    """Tests for Part I - Section 1231 gains/losses."""

    def test_net_section_1231_gain(self):
        """Net Section 1231 gain goes to Schedule D as LTCG."""
        sale = make_property_sale(
            property_type=PropertyType.LAND,  # Section 1231, no recapture
            date_acquired="2020-01-01",
            cost_basis=100000.0,
            depreciation=0.0,
            date_sold="2025-06-15",
            sales_price=150000.0,
            selling_expenses=5000.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_i()

        # Gain = 145000 - 100000 = 45000
        assert result['line_2_section_1231_gains'] == 45000.0
        assert result['line_3_section_1231_losses'] == 0.0
        assert result['line_7_net_section_1231_gain_loss'] == 45000.0
        assert result['is_long_term_capital_gain'] is True
        assert result['goes_to_schedule_d'] is True

    def test_net_section_1231_loss(self):
        """Net Section 1231 loss is ordinary loss."""
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            date_acquired="2020-01-01",
            cost_basis=100000.0,
            depreciation=0.0,
            date_sold="2025-06-15",
            sales_price=70000.0,
            selling_expenses=5000.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_i()

        # Loss = 65000 - 100000 = -35000
        assert result['line_3_section_1231_losses'] == 35000.0
        assert result['line_7_net_section_1231_gain_loss'] == -35000.0
        assert result['is_ordinary_loss'] is True

    def test_section_1245_gain_split(self):
        """Section 1245 property: recapture vs 1231 gain."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            date_acquired="2020-01-01",
            cost_basis=50000.0,
            depreciation=20000.0,
            date_sold="2025-06-15",
            sales_price=60000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_i()

        # Adjusted basis = 30000, Gain = 30000
        # Recapture = 20000 (goes to Part II/III as ordinary)
        # Section 1231 gain = 30000 - 20000 = 10000
        assert result['line_2_section_1231_gains'] == 10000.0

    def test_multiple_properties_netting(self):
        """Multiple properties netted together."""
        gain_sale = make_property_sale(
            description="Property with Gain",
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=130000.0,
            selling_expenses=0.0,
        )
        loss_sale = make_property_sale(
            description="Property with Loss",
            property_type=PropertyType.LAND,
            cost_basis=80000.0,
            depreciation=0.0,
            sales_price=60000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[gain_sale, loss_sale])
        result = form.calculate_part_i()

        # Gain = 30000, Loss = 20000, Net = 10000
        assert result['line_2_section_1231_gains'] == 30000.0
        assert result['line_3_section_1231_losses'] == 20000.0
        assert result['line_7_net_section_1231_gain_loss'] == 10000.0

    def test_short_term_property_excluded(self):
        """Short-term property excluded from Part I."""
        short_term = make_property_sale(
            date_acquired="2025-01-01",
            date_sold="2025-06-15",
        )
        form = Form4797(property_sales=[short_term])
        result = form.calculate_part_i()

        # Short-term goes to Part II, not Part I
        assert result['line_2_section_1231_gains'] == 0.0
        assert result['line_3_section_1231_losses'] == 0.0


# ============== Lookback Rule Tests ==============

class TestLookbackRule:
    """Tests for 5-year Section 1231 lookback rule."""

    def test_lookback_recapture(self):
        """Net gain recaptured as ordinary to extent of prior losses."""
        prior_losses = [
            Section1231LookbackLoss(tax_year=2022, loss_amount=10000.0),
            Section1231LookbackLoss(tax_year=2023, loss_amount=5000.0),
        ]
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=150000.0,
            selling_expenses=0.0,
        )
        form = Form4797(
            property_sales=[sale],
            prior_section_1231_losses=prior_losses,
        )
        result = form.calculate_part_i(current_year=2025)

        # Gain = 50000
        # Prior losses = 15000
        # Lookback recapture = 15000 (treated as ordinary)
        # Net Section 1231 gain = 50000 - 15000 = 35000
        assert result['line_7_net_section_1231_gain_loss'] == 50000.0
        assert result['line_8_lookback_recapture'] == 15000.0
        assert result['line_9_net_section_1231_gain'] == 35000.0

    def test_lookback_limited_to_gain(self):
        """Lookback recapture limited to net gain amount."""
        prior_losses = [
            Section1231LookbackLoss(tax_year=2023, loss_amount=100000.0),
        ]
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=130000.0,
            selling_expenses=0.0,
        )
        form = Form4797(
            property_sales=[sale],
            prior_section_1231_losses=prior_losses,
        )
        result = form.calculate_part_i(current_year=2025)

        # Gain = 30000, Prior losses = 100000
        # Recapture = min(30000, 100000) = 30000
        assert result['line_8_lookback_recapture'] == 30000.0
        assert result['line_9_net_section_1231_gain'] == 0.0

    def test_lookback_excludes_old_losses(self):
        """Losses older than 5 years excluded from lookback."""
        prior_losses = [
            Section1231LookbackLoss(tax_year=2019, loss_amount=50000.0),  # Too old
            Section1231LookbackLoss(tax_year=2022, loss_amount=10000.0),  # Within 5 years
        ]
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=180000.0,
            selling_expenses=0.0,
        )
        form = Form4797(
            property_sales=[sale],
            prior_section_1231_losses=prior_losses,
        )
        result = form.calculate_part_i(current_year=2025)

        # Only 2022 loss counts (2020-2024 are within 5 years of 2025)
        # 2019 is outside the window
        assert result['line_8_lookback_recapture'] == 10000.0

    def test_no_lookback_on_net_loss(self):
        """No lookback when there's a net Section 1231 loss."""
        prior_losses = [
            Section1231LookbackLoss(tax_year=2023, loss_amount=20000.0),
        ]
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=80000.0,
            selling_expenses=0.0,
        )
        form = Form4797(
            property_sales=[sale],
            prior_section_1231_losses=prior_losses,
        )
        result = form.calculate_part_i(current_year=2025)

        assert result['line_7_net_section_1231_gain_loss'] == -20000.0
        assert result['line_8_lookback_recapture'] == 0.0


# ============== Form 4797 Part II Tests ==============

class TestForm4797PartII:
    """Tests for Part II - Ordinary gains/losses."""

    def test_short_term_gain(self):
        """Short-term gain is ordinary income."""
        sale = make_property_sale(
            date_acquired="2025-01-01",
            date_sold="2025-06-15",
            cost_basis=50000.0,
            depreciation=5000.0,
            sales_price=60000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_ii()

        # Adjusted basis = 45000, Gain = 15000
        assert result['line_10_ordinary_gains'] == 15000.0

    def test_short_term_loss(self):
        """Short-term loss is ordinary loss."""
        sale = make_property_sale(
            date_acquired="2025-01-01",
            date_sold="2025-06-15",
            cost_basis=50000.0,
            depreciation=5000.0,
            sales_price=35000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_ii()

        # Adjusted basis = 45000, Loss = -10000
        assert result['line_11_ordinary_losses'] == 10000.0

    def test_includes_part_iii_recapture(self):
        """Part II includes recapture from Part III."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            date_acquired="2020-01-01",
            cost_basis=50000.0,
            depreciation=20000.0,
            sales_price=45000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_ii()

        # Gain = 15000, Recapture = 15000 (limited to gain)
        assert result['line_12_gain_from_part_iii'] == 15000.0


# ============== Form 4797 Part III Tests ==============

class TestForm4797PartIII:
    """Tests for Part III - Depreciation recapture."""

    def test_section_1245_recapture_in_part_iii(self):
        """Section 1245 recapture calculated correctly."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            date_acquired="2020-01-01",
            cost_basis=80000.0,
            depreciation=40000.0,
            sales_price=70000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_iii()

        # Adjusted basis = 40000, Gain = 30000
        # Recapture = min(30000, 40000) = 30000
        assert result['section_1245_recapture'] == 30000.0

    def test_section_1250_recapture_in_part_iii(self):
        """Section 1250 recapture with unrecaptured gain."""
        sale = BusinessPropertySale(
            description="Building",
            property_type=PropertyType.COMMERCIAL_BUILDING,
            date_acquired="2015-01-01",
            cost_or_other_basis=400000.0,
            depreciation_allowed=100000.0,
            straight_line_depreciation=100000.0,
            date_sold="2025-06-15",
            gross_sales_price=420000.0,
            selling_expenses=10000.0,
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_iii()

        # Adjusted basis = 300000, Realized = 410000, Gain = 110000
        # No additional depreciation (SL = total)
        assert result['section_1250_ordinary'] == 0.0
        # Unrecaptured = min(100000 depreciation, remaining gain)
        assert result['unrecaptured_1250_gain'] == 100000.0


# ============== Form 4797 Part IV Tests ==============

class TestForm4797PartIV:
    """Tests for Part IV - Section 179/280F recapture."""

    def test_section_179_recapture(self):
        """Section 179 recapture when business use drops below 50%."""
        sale = BusinessPropertySale(
            description="Equipment",
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            date_acquired="2023-01-01",
            cost_or_other_basis=50000.0,
            section_179_deduction=20000.0,
            depreciation_allowed=5000.0,
            date_sold="2025-06-15",
            gross_sales_price=40000.0,
            selling_expenses=0.0,
            prior_business_use_percentage=100.0,
            current_business_use_percentage=40.0,  # Dropped below 50%
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_iv()

        # Section 179 recapture when business use < 50%
        assert result['section_179_recapture'] == 20000.0

    def test_no_section_179_recapture_above_50_percent(self):
        """No Section 179 recapture when business use stays >= 50%."""
        sale = BusinessPropertySale(
            description="Equipment",
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            date_acquired="2023-01-01",
            cost_or_other_basis=50000.0,
            section_179_deduction=20000.0,
            depreciation_allowed=5000.0,
            date_sold="2025-06-15",
            gross_sales_price=40000.0,
            selling_expenses=0.0,
            current_business_use_percentage=60.0,  # Still >= 50%
        )
        form = Form4797(property_sales=[sale])
        result = form.calculate_part_iv()

        assert result['section_179_recapture'] == 0.0


# ============== Integration Tests ==============

class TestForm4797Integration:
    """Tests for Form 4797 integration with Income and Engine."""

    def test_income_helper_methods(self):
        """Test Income model Form 4797 helper methods."""
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=150000.0,
            selling_expenses=5000.0,
        )
        form = Form4797(property_sales=[sale])
        income = Income(form_4797=form)

        # Land sale has no recapture, just Section 1231 gain
        assert income.get_form_4797_section_1231_gain() == 45000.0
        assert income.get_form_4797_ordinary_income() == 0.0
        assert income.get_form_4797_section_1231_loss() == 0.0

    def test_income_with_equipment_sale(self):
        """Test Income with equipment sale (Section 1245 recapture)."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=80000.0,
            depreciation=30000.0,
            sales_price=70000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        income = Income(form_4797=form)

        # Adjusted basis = 50000, Gain = 20000
        # Recapture = 20000 (all ordinary)
        assert income.get_form_4797_ordinary_income() == 20000.0
        assert income.get_form_4797_depreciation_recapture() == 20000.0

    def test_engine_calculates_form_4797(self, engine):
        """Test engine calculates Form 4797 fields."""
        sale = make_property_sale(
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=140000.0,
            selling_expenses=5000.0,
        )
        form = Form4797(property_sales=[sale])
        tax_return = create_tax_return(form_4797=form)

        breakdown = engine.calculate(tax_return)

        # Land sale: Section 1231 gain = 35000 (LTCG)
        assert breakdown.form_4797_section_1231_gain == 35000.0
        assert breakdown.form_4797_ordinary_income == 0.0
        assert breakdown.form_4797_section_1231_loss == 0.0

    def test_engine_with_recapture(self, engine):
        """Test engine handles depreciation recapture."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=100000.0,
            depreciation=40000.0,
            sales_price=90000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        tax_return = create_tax_return(form_4797=form)

        breakdown = engine.calculate(tax_return)

        # Adjusted basis = 60000, Gain = 30000
        # Recapture = 30000 (ordinary)
        assert breakdown.form_4797_depreciation_recapture == 30000.0

    def test_engine_with_building_sale(self, engine):
        """Test engine handles real property with unrecaptured 1250 gain."""
        sale = BusinessPropertySale(
            description="Office Building",
            property_type=PropertyType.COMMERCIAL_BUILDING,
            date_acquired="2015-01-01",
            cost_or_other_basis=500000.0,
            depreciation_allowed=100000.0,
            straight_line_depreciation=100000.0,
            date_sold="2025-06-15",
            gross_sales_price=550000.0,
            selling_expenses=10000.0,
        )
        form = Form4797(property_sales=[sale])
        tax_return = create_tax_return(form_4797=form)

        breakdown = engine.calculate(tax_return)

        # Adjusted basis = 400000, Realized = 540000, Gain = 140000
        # No additional depreciation, so no ordinary from 1250
        # Unrecaptured 1250 gain = 100000 (depreciation)
        # Section 1231 gain = 40000
        assert breakdown.form_4797_unrecaptured_1250_gain == 100000.0
        assert breakdown.form_4797_section_1231_gain == 40000.0

    def test_form_4797_summary(self):
        """Test Form 4797 summary generation."""
        sale = make_property_sale(
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=50000.0,
            depreciation=20000.0,
            sales_price=45000.0,
            selling_expenses=0.0,
        )
        form = Form4797(property_sales=[sale])
        income = Income(form_4797=form)

        summary = income.get_form_4797_summary()
        assert summary is not None
        assert summary['total_property_sales'] == 1
        assert 'part_i_section_1231' in summary
        assert 'part_ii_ordinary' in summary
        assert 'part_iii_recapture' in summary
        assert 'summary' in summary


# ============== Edge Cases ==============

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_zero_gain_zero_loss(self):
        """Property sold at exactly adjusted basis."""
        sale = make_property_sale(
            cost_basis=50000.0,
            depreciation=20000.0,
            sales_price=30000.0,  # Exactly adjusted basis
            selling_expenses=0.0,
        )
        assert sale.get_total_gain_loss() == 0.0

    def test_involuntary_conversion(self):
        """Involuntary conversion uses insurance proceeds."""
        sale = BusinessPropertySale(
            description="Stolen Equipment",
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            date_acquired="2020-01-01",
            cost_or_other_basis=50000.0,
            depreciation_allowed=20000.0,
            date_sold="2025-06-15",
            gross_sales_price=0.0,
            selling_expenses=500.0,
            disposition_type=DispositionType.INVOLUNTARY_CONVERSION,
            insurance_or_other_reimbursement=45000.0,
        )
        # Amount realized = 45000 - 500 = 44500
        # Adjusted basis = 30000
        # Gain = 14500
        assert sale.get_amount_realized() == 44500.0
        assert sale.get_total_gain_loss() == 14500.0

    def test_passthrough_income(self):
        """Form 4797 with K-1 passthrough amounts."""
        form = Form4797(
            property_sales=[],
            passthrough_section_1231_gain=25000.0,
            passthrough_ordinary_recapture=5000.0,
        )
        result = form.calculate_part_i()

        assert result['line_2_section_1231_gains'] == 25000.0
        assert result['line_7_net_section_1231_gain_loss'] == 25000.0

    def test_no_property_sales(self):
        """Form 4797 with no property sales."""
        form = Form4797(property_sales=[])
        result = form.calculate_all()

        assert result['summary']['total_ordinary_income'] == 0.0
        assert result['summary']['net_section_1231_gain'] == 0.0

    def test_multiple_property_types_mixed(self):
        """Multiple property types in same Form 4797."""
        equipment = make_property_sale(
            description="Equipment",
            property_type=PropertyType.MACHINERY_EQUIPMENT,
            cost_basis=50000.0,
            depreciation=20000.0,
            sales_price=45000.0,
            selling_expenses=0.0,
        )
        land = make_property_sale(
            description="Land",
            property_type=PropertyType.LAND,
            cost_basis=100000.0,
            depreciation=0.0,
            sales_price=130000.0,
            selling_expenses=5000.0,
        )
        form = Form4797(property_sales=[equipment, land])
        result = form.calculate_all()

        # Equipment: Gain = 15000, Recapture = 15000
        # Land: Gain = 25000 (Section 1231)
        assert result['part_iii']['section_1245_recapture'] == 15000.0
        assert result['part_i']['line_2_section_1231_gains'] == 25000.0
