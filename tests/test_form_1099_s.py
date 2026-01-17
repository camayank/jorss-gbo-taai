"""
Tests for Form 1099-S - Proceeds from Real Estate Transactions

Comprehensive test suite covering:
- Basic 1099-S data capture
- Primary residence exclusion ($250k/$500k)
- Ownership and use tests
- Gain/loss calculations
- Depreciation recapture
- Schedule D integration
- Various property types
"""

import pytest
from datetime import date
from src.models.form_1099_s import (
    Form1099S,
    RealEstateSaleCalculation,
    PropertyType,
    TransactionType,
    calculate_real_estate_gain,
    calculate_primary_residence_exclusion,
)


class TestForm1099SBasic:
    """Test basic Form 1099-S data capture."""

    def test_create_basic_form(self):
        """Test creating a basic 1099-S form."""
        form = Form1099S(
            tax_year=2025,
            filer_name="ABC Title Company",
            transferor_name="John Doe",
            transferor_tin="123-45-6789",
            box_1_date_of_closing=date(2025, 6, 15),
            box_2_gross_proceeds=450000.00,
            box_3_property_address="123 Main St, Anytown, CA 90210",
        )
        assert form.box_2_gross_proceeds == 450000.00
        assert form.box_1_date_of_closing == date(2025, 6, 15)

    def test_property_types(self):
        """Test property type classification."""
        assert PropertyType.PRINCIPAL_RESIDENCE.value == "principal_residence"
        assert PropertyType.RENTAL_PROPERTY.value == "rental_property"
        assert PropertyType.INVESTMENT_LAND.value == "investment_land"
        assert PropertyType.COMMERCIAL.value == "commercial"

    def test_transaction_types(self):
        """Test transaction type classification."""
        assert TransactionType.SALE.value == "sale"
        assert TransactionType.EXCHANGE.value == "exchange"
        assert TransactionType.INSTALLMENT_SALE.value == "installment_sale"
        assert TransactionType.SHORT_SALE.value == "short_sale"

    def test_foreign_person_flag(self):
        """Test foreign person withholding flag."""
        form = Form1099S(
            box_2_gross_proceeds=500000,
            box_5_foreign_person=True,
        )
        assert form.box_5_foreign_person is True


class TestPrimaryResidenceExclusionTests:
    """Test ownership and use test requirements."""

    def test_meets_both_tests(self):
        """Test meeting both ownership and use tests."""
        form = Form1099S(
            box_2_gross_proceeds=600000,
            is_primary_residence=True,
            ownership_months=36,  # 3 years
            use_as_residence_months=36,
        )
        assert form.meets_ownership_test is True
        assert form.meets_use_test is True
        assert form.qualifies_for_exclusion is True

    def test_exactly_24_months(self):
        """Test exactly 24 months meets requirement."""
        form = Form1099S(
            is_primary_residence=True,
            ownership_months=24,
            use_as_residence_months=24,
        )
        assert form.meets_ownership_test is True
        assert form.meets_use_test is True
        assert form.qualifies_for_exclusion is True

    def test_fails_ownership_test(self):
        """Test failing ownership test."""
        form = Form1099S(
            is_primary_residence=True,
            ownership_months=20,  # Less than 24
            use_as_residence_months=36,
        )
        assert form.meets_ownership_test is False
        assert form.meets_use_test is True
        assert form.qualifies_for_exclusion is False

    def test_fails_use_test(self):
        """Test failing use test (rental conversion)."""
        form = Form1099S(
            is_primary_residence=True,
            ownership_months=60,
            use_as_residence_months=18,  # Only 18 months as residence
        )
        assert form.meets_ownership_test is True
        assert form.meets_use_test is False
        assert form.qualifies_for_exclusion is False

    def test_not_primary_residence(self):
        """Test non-primary residence doesn't qualify."""
        form = Form1099S(
            is_primary_residence=False,
            ownership_months=48,
            use_as_residence_months=48,
        )
        assert form.qualifies_for_exclusion is False


class TestGainLossCalculations:
    """Test gain/loss calculations."""

    def test_simple_gain(self):
        """Test simple gain calculation."""
        form = Form1099S(
            box_2_gross_proceeds=500000,
            property_type=PropertyType.INVESTMENT_LAND,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            selling_closing_costs=5000,
            real_estate_commission=30000,
        )
        # Basis = 300000
        # Selling expenses = 35000
        # Amount realized = 500000 - 35000 = 465000
        # Gain = 465000 - 300000 = 165000
        assert calc.adjusted_basis == 300000
        assert calc.total_selling_expenses == 35000
        assert calc.amount_realized == 465000
        assert calc.realized_gain_loss == 165000

    def test_gain_with_improvements(self):
        """Test gain with capital improvements."""
        form = Form1099S(
            box_2_gross_proceeds=600000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=350000,
            purchase_closing_costs=8000,
            capital_improvements=50000,
            selling_closing_costs=5000,
            real_estate_commission=36000,
        )
        # Basis = 350000 + 8000 + 50000 = 408000
        # Selling expenses = 41000
        # Amount realized = 600000 - 41000 = 559000
        # Gain = 559000 - 408000 = 151000
        assert calc.adjusted_basis == 408000
        assert calc.realized_gain_loss == 151000

    def test_loss_on_sale(self):
        """Test loss on sale."""
        form = Form1099S(
            box_2_gross_proceeds=250000,
            property_type=PropertyType.INVESTMENT_LAND,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            selling_closing_costs=5000,
            real_estate_commission=15000,
        )
        # Amount realized = 230000
        # Gain/Loss = 230000 - 300000 = -70000
        assert calc.realized_gain_loss == -70000
        assert calc.recognized_loss == 70000  # Investment loss is deductible

    def test_loss_on_personal_residence(self):
        """Test loss on personal residence (not deductible)."""
        form = Form1099S(
            box_2_gross_proceeds=400000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=500000,
            selling_closing_costs=5000,
            real_estate_commission=24000,
        )
        # Loss = -129000
        assert calc.realized_gain_loss == -129000
        # Personal residence loss NOT deductible
        assert calc.recognized_loss == 0


class TestPrimaryResidenceExclusionAmount:
    """Test primary residence exclusion amounts."""

    def test_single_filer_exclusion(self):
        """Test $250k exclusion for single filer."""
        form = Form1099S(
            box_2_gross_proceeds=700000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
            is_primary_residence=True,
            ownership_months=60,
            use_as_residence_months=60,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            selling_closing_costs=5000,
            real_estate_commission=42000,
            filing_status="single",
        )
        # Gain = 700000 - 47000 - 300000 = 353000
        # Exclusion = 250000
        # Taxable = 103000
        assert calc.exclusion_amount == 250000
        assert calc.taxable_gain == 103000

    def test_mfj_exclusion(self):
        """Test $500k exclusion for married filing jointly."""
        form = Form1099S(
            box_2_gross_proceeds=900000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
            is_primary_residence=True,
            ownership_months=60,
            use_as_residence_months=60,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            selling_closing_costs=5000,
            real_estate_commission=54000,
            filing_status="mfj",
        )
        # Gain = 900000 - 59000 - 300000 = 541000
        # Exclusion = 500000
        # Taxable = 41000
        assert calc.exclusion_amount == 500000
        assert calc.taxable_gain == 41000

    def test_gain_less_than_exclusion(self):
        """Test gain less than exclusion amount."""
        form = Form1099S(
            box_2_gross_proceeds=400000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
            is_primary_residence=True,
            ownership_months=60,
            use_as_residence_months=60,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=250000,
            selling_closing_costs=5000,
            real_estate_commission=24000,
            filing_status="single",
        )
        # Gain = 400000 - 29000 - 250000 = 121000
        # Exclusion available = 250000, but only need 121000
        # Taxable = 0
        assert calc.taxable_gain == 0

    def test_no_exclusion_without_qualifying(self):
        """Test no exclusion when tests not met."""
        form = Form1099S(
            box_2_gross_proceeds=500000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
            is_primary_residence=True,
            ownership_months=12,  # Not enough
            use_as_residence_months=12,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            filing_status="single",
        )
        assert calc.exclusion_amount == 0
        # Full gain is taxable
        assert calc.taxable_gain == 200000


class TestDepreciationRecapture:
    """Test Section 1250 depreciation recapture."""

    def test_rental_property_recapture(self):
        """Test depreciation recapture on rental property."""
        form = Form1099S(
            box_2_gross_proceeds=400000,
            property_type=PropertyType.RENTAL_PROPERTY,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=250000,
            capital_improvements=30000,
            depreciation_taken=50000,
            selling_closing_costs=5000,
            real_estate_commission=24000,
        )
        # Basis = 250000 + 30000 - 50000 = 230000
        # Amount realized = 400000 - 29000 = 371000
        # Gain = 371000 - 230000 = 141000
        # Recapture = min(141000, 50000) = 50000
        assert calc.adjusted_basis == 230000
        assert calc.realized_gain_loss == 141000
        assert calc.depreciation_recapture == 50000
        assert calc.capital_gain_portion == 91000  # 141000 - 50000

    def test_recapture_limited_to_gain(self):
        """Test recapture limited when gain < depreciation."""
        form = Form1099S(
            box_2_gross_proceeds=280000,
            property_type=PropertyType.RENTAL_PROPERTY,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=250000,
            depreciation_taken=50000,
            selling_closing_costs=5000,
            real_estate_commission=16800,
        )
        # Basis = 200000 (250000 - 50000 depreciation)
        # Amount realized = 280000 - 21800 = 258200
        # Gain = 258200 - 200000 = 58200
        # Recapture = min(58200, 50000) = 50000
        assert calc.depreciation_recapture == 50000

    def test_no_recapture_on_personal_residence(self):
        """Test no recapture on personal residence."""
        form = Form1099S(
            box_2_gross_proceeds=500000,
            property_type=PropertyType.PRINCIPAL_RESIDENCE,
            is_primary_residence=True,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            depreciation_taken=0,  # No depreciation on personal residence
        )
        assert calc.depreciation_recapture == 0

    def test_no_recapture_on_loss(self):
        """Test no recapture when there's a loss."""
        form = Form1099S(
            box_2_gross_proceeds=180000,
            property_type=PropertyType.RENTAL_PROPERTY,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=250000,
            depreciation_taken=30000,
            selling_closing_costs=5000,
        )
        # Basis = 220000, Amount realized = 175000
        # Loss = -45000
        assert calc.realized_gain_loss == -45000
        assert calc.depreciation_recapture == 0


class TestHoldingPeriod:
    """Test holding period calculations."""

    def test_long_term_holding(self):
        """Test long-term holding period (>1 year)."""
        form = Form1099S(
            box_1_date_of_closing=date(2025, 6, 15),
            box_2_gross_proceeds=500000,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            date_acquired=date(2020, 1, 1),
        )
        assert calc.holding_period_days > 365
        assert calc.is_long_term is True

    def test_short_term_holding(self):
        """Test short-term holding period (<1 year)."""
        form = Form1099S(
            box_1_date_of_closing=date(2025, 6, 15),
            box_2_gross_proceeds=500000,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=400000,
            date_acquired=date(2025, 1, 1),
        )
        assert calc.holding_period_days < 365
        assert calc.is_long_term is False

    def test_exactly_one_year(self):
        """Test holding exactly one year (still short-term)."""
        form = Form1099S(
            box_1_date_of_closing=date(2025, 6, 15),
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            date_acquired=date(2024, 6, 15),  # Exactly 365 days
        )
        assert calc.holding_period_days == 365
        assert calc.is_long_term is False  # Need MORE than 365


class TestScheduleDIntegration:
    """Test Schedule D output."""

    def test_schedule_d_output(self):
        """Test Schedule D data generation."""
        form = Form1099S(
            box_2_gross_proceeds=600000,
            property_type=PropertyType.INVESTMENT_LAND,
            box_1_date_of_closing=date(2025, 7, 1),
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=400000,
            selling_closing_costs=5000,
            real_estate_commission=36000,
            date_acquired=date(2020, 3, 15),
        )
        result = calc.to_schedule_d()

        assert result["proceeds"] == 600000
        # Basis for Schedule D includes selling expenses adjustment
        assert result["gain_loss"] == 159000
        assert result["is_long_term"] is True

    def test_form_8949_output(self):
        """Test Form 8949 data generation."""
        form = Form1099S(
            box_2_gross_proceeds=500000,
            box_3_property_address="123 Main St",
            box_1_date_of_closing=date(2025, 8, 1),
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=350000,
            date_acquired=date(2018, 5, 15),
        )
        result = calc.to_form_8949()

        assert result["description"] == "123 Main St"
        assert result["proceeds"] == 500000
        assert result["cost_basis"] == 350000


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_calculate_real_estate_gain(self):
        """Test simple real estate gain calculation."""
        result = calculate_real_estate_gain(
            gross_proceeds=500000,
            purchase_price=300000,
            improvements=50000,
            selling_costs=5000,
            commission=30000,
        )
        # Basis = 350000
        # Amount realized = 465000
        # Gain = 115000
        assert result["adjusted_basis"] == 350000
        assert result["amount_realized"] == 465000
        assert result["realized_gain"] == 115000
        assert result["taxable_gain"] == 115000

    def test_calculate_with_primary_exclusion(self):
        """Test with primary residence exclusion."""
        result = calculate_real_estate_gain(
            gross_proceeds=600000,
            purchase_price=300000,
            selling_costs=5000,
            commission=36000,
            is_primary_residence=True,
            meets_exclusion_tests=True,
            filing_status="single",
        )
        # Gain = 259000
        # Exclusion = 250000
        # Taxable = 9000
        assert result["exclusion_available"] == 250000
        assert result["taxable_gain"] == 9000

    def test_calculate_primary_residence_exclusion(self):
        """Test primary residence exclusion calculation."""
        result = calculate_primary_residence_exclusion(
            sale_price=700000,
            purchase_price=300000,
            improvements=50000,
            selling_costs=40000,
            filing_status="mfj",
            ownership_months=60,
            use_months=60,
        )
        # Basis = 350000
        # Amount realized = 660000
        # Gain = 310000
        # Max exclusion = 500000, used = 310000
        assert result["qualifies_for_exclusion"] is True
        assert result["max_exclusion"] == 500000
        assert result["exclusion_used"] == 310000
        assert result["taxable_gain"] == 0
        assert result["tax_free"] == 310000

    def test_exclusion_not_qualified(self):
        """Test when exclusion not qualified."""
        result = calculate_primary_residence_exclusion(
            sale_price=500000,
            purchase_price=300000,
            improvements=0,
            selling_costs=30000,
            filing_status="single",
            ownership_months=12,  # Not enough
            use_months=12,
        )
        assert result["qualifies_for_exclusion"] is False
        assert result["max_exclusion"] == 0
        assert result["taxable_gain"] == 170000


class TestToDictionary:
    """Test dictionary serialization."""

    def test_to_dict(self):
        """Test full dictionary output."""
        form = Form1099S(
            tax_year=2025,
            box_2_gross_proceeds=500000,
            box_3_property_address="456 Oak Ave",
            property_type=PropertyType.RENTAL_PROPERTY,
            is_primary_residence=False,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
            depreciation_taken=40000,
            selling_closing_costs=5000,
            real_estate_commission=30000,
        )
        result = calc.to_dict()

        assert result["tax_year"] == 2025
        assert result["property_address"] == "456 Oak Ave"
        assert result["property_type"] == "rental_property"
        assert result["gross_proceeds"] == 500000
        assert result["depreciation_recapture"] == 40000
        assert result["primary_residence_exclusion"]["qualifies"] is False


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_basis(self):
        """Test property with zero basis (inherited, gifted)."""
        form = Form1099S(
            box_2_gross_proceeds=300000,
            property_type=PropertyType.INVESTMENT_LAND,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=0,  # Inherited at stepped-up basis = FMV
            selling_closing_costs=10000,
        )
        # All proceeds (minus expenses) are gain
        assert calc.realized_gain_loss == 290000

    def test_very_high_selling_costs(self):
        """Test when selling costs exceed proceeds."""
        form = Form1099S(
            box_2_gross_proceeds=100000,
            property_type=PropertyType.INVESTMENT_LAND,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=80000,
            selling_closing_costs=15000,
            real_estate_commission=20000,
        )
        # Amount realized = 100000 - 35000 = 65000
        # Gain/loss = 65000 - 80000 = -15000
        assert calc.realized_gain_loss == -15000

    def test_second_home(self):
        """Test second home (no exclusion)."""
        form = Form1099S(
            box_2_gross_proceeds=400000,
            property_type=PropertyType.SECOND_HOME,
            is_primary_residence=False,
        )
        calc = RealEstateSaleCalculation(
            form_1099s=form,
            original_purchase_price=300000,
        )
        # No exclusion for second home
        assert calc.exclusion_amount == 0
        # No depreciation recapture (personal use)
        assert calc.depreciation_recapture == 0
        assert calc.taxable_gain == 100000
