"""
Tests for Form 6252 - Installment Sale Income

Tests cover:
- Part I: Gross profit and contract price calculations
- Part II: Installment sale income recognition
- Part III: Related party installment sales
- Depreciation recapture (year of sale)
- Section 453A interest charge (large sales >$5M)
- Pledging rules
- Multiple installment obligations
- Integration with tax calculation engine
"""

import pytest
from models.form_6252 import (
    Form6252,
    InstallmentObligation,
    InstallmentPayment,
    PropertyCategory,
    RelatedPartyType,
    calculate_installment_eligibility,
)
from models.income import Income, W2Info
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from models.tax_return import TaxReturn
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


# ============== Helper Functions ==============

def make_obligation(
    description: str = "Test Property",
    selling_price: float = 100000.0,
    adjusted_basis: float = 60000.0,
    selling_expenses: float = 5000.0,
    depreciation: float = 0.0,
    mortgage_assumed: float = 0.0,
    seller_financing: float = 100000.0,
    year_of_sale: int = 2023,
    payments_prior_years: float = 0.0,
    current_year_principal: float = 10000.0,
    current_year_interest: float = 2000.0,
) -> InstallmentObligation:
    """Helper to create InstallmentObligation for tests."""
    return InstallmentObligation(
        property_description=description,
        date_acquired="2015-01-01",
        date_sold=f"{year_of_sale}-06-15",
        year_of_sale=year_of_sale,
        selling_price=selling_price,
        adjusted_basis=adjusted_basis,
        selling_expenses=selling_expenses,
        depreciation_allowed=depreciation,
        existing_mortgage_assumed=mortgage_assumed,
        seller_financing=seller_financing,
        total_payments_prior_years=payments_prior_years,
        payments_current_year=[
            InstallmentPayment(
                payment_date="2025-03-15",
                total_payment=current_year_principal + current_year_interest,
                principal_portion=current_year_principal,
                interest_portion=current_year_interest,
            )
        ] if current_year_principal > 0 else [],
    )


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def create_tax_return(form_6252: Form6252 = None, wages: float = 50000.0) -> TaxReturn:
    """Helper to create TaxReturn with Form 6252."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=FilingStatus.SINGLE,
        ),
        income=Income(
            w2_forms=[make_w2(wages, wages * 0.15)],
            form_6252=form_6252,
        ),
        deductions=Deductions(use_standard_deduction=True),
        credits=TaxCredits(),
    )


@pytest.fixture
def engine():
    return FederalTaxEngine(TaxYearConfig.for_2025())


# ============== InstallmentObligation Tests ==============

class TestInstallmentObligation:
    """Tests for individual installment obligation calculations."""

    def test_gross_profit_calculation(self):
        """Test gross profit = selling price - basis - expenses."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
        )
        # Gross profit = 100000 - 60000 - 5000 = 35000
        assert obligation.get_gross_profit() == 35000.0

    def test_gross_profit_no_negative(self):
        """Gross profit cannot be negative."""
        obligation = make_obligation(
            selling_price=50000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
        )
        assert obligation.get_gross_profit() == 0.0

    def test_contract_price_simple(self):
        """Contract price with no mortgage."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
            mortgage_assumed=0.0,
        )
        # Contract price = selling price - mortgage assumed
        # = 100000 - 0 = 100000
        assert obligation.get_contract_price() == 100000.0

    def test_contract_price_with_mortgage(self):
        """Contract price reduced by mortgage assumed."""
        obligation = make_obligation(
            selling_price=200000.0,
            adjusted_basis=100000.0,
            selling_expenses=10000.0,
            mortgage_assumed=50000.0,
        )
        # Gross profit = 200000 - 100000 - 10000 = 90000
        # Contract price = 200000 - 50000 = 150000
        assert obligation.get_contract_price() == 150000.0

    def test_contract_price_minimum(self):
        """Contract price cannot be less than gross profit."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=30000.0,
            selling_expenses=5000.0,
            mortgage_assumed=80000.0,  # Large mortgage
        )
        # Gross profit = 100000 - 30000 - 5000 = 65000
        # Selling price - mortgage = 100000 - 80000 = 20000
        # Contract price = max(20000, 65000) = 65000
        assert obligation.get_contract_price() == 65000.0

    def test_gross_profit_percentage(self):
        """Test gross profit percentage calculation."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
        )
        # GP = 35000, Contract price = 100000
        # GP% = 35000 / 100000 = 35%
        assert obligation.get_gross_profit_percentage() == 0.35

    def test_gross_profit_percentage_capped_at_100(self):
        """GP% should not exceed 100%."""
        obligation = InstallmentObligation(
            property_description="Test",
            date_acquired="2015-01-01",
            date_sold="2023-06-15",
            year_of_sale=2023,
            selling_price=100000.0,
            adjusted_basis=0.0,  # Fully depreciated
            selling_expenses=0.0,
            seller_financing=100000.0,
        )
        # GP = 100000, Contract price = 100000
        # GP% = 100%
        assert obligation.get_gross_profit_percentage() == 1.0

    def test_mortgage_excess(self):
        """Test mortgage excess over basis calculation."""
        obligation = make_obligation(
            selling_price=200000.0,
            adjusted_basis=50000.0,
            selling_expenses=10000.0,
            mortgage_assumed=80000.0,
        )
        # Mortgage excess = max(0, 80000 - 50000) = 30000
        assert obligation.get_mortgage_excess() == 30000.0

    def test_current_year_payments(self):
        """Test current year payment totals."""
        obligation = make_obligation(
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        assert obligation.get_current_year_principal() == 10000.0
        assert obligation.get_current_year_interest() == 2000.0

    def test_remaining_balance(self):
        """Test remaining installment balance calculation."""
        obligation = make_obligation(
            seller_financing=100000.0,
            payments_prior_years=30000.0,
            current_year_principal=10000.0,
        )
        # Remaining = 100000 - 30000 - 10000 = 60000
        assert obligation.get_remaining_installment_balance() == 60000.0


# ============== Form 6252 Part I Tests ==============

class TestForm6252PartI:
    """Tests for Part I - Gross Profit and Contract Price."""

    def test_part_i_basic_calculation(self):
        """Test Part I line-by-line calculation."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
            depreciation=10000.0,
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_i(obligation)

        assert result['line_5_selling_price'] == 100000.0
        assert result['line_8_basis'] == 60000.0
        assert result['line_9_depreciation'] == 10000.0
        # Adjusted basis = 60000 - 10000 = 50000
        assert result['line_10_adjusted_basis'] == 50000.0
        assert result['line_11_expenses'] == 5000.0
        # Total basis = 50000 + 5000 + 0 (recapture) = 55000
        assert result['line_13_total_basis'] == 55000.0
        # Gross profit = 100000 - 55000 = 45000
        assert result['line_14_gross_profit'] == 45000.0
        # Contract price = 100000 (no mortgage)
        assert result['line_17_contract_price'] == 100000.0
        # GP% = 45000 / 100000 = 45%
        assert result['line_18_gp_percentage'] == 0.45

    def test_part_i_with_mortgage(self):
        """Test Part I with mortgage assumed by buyer."""
        obligation = make_obligation(
            selling_price=200000.0,
            adjusted_basis=100000.0,
            selling_expenses=10000.0,
            mortgage_assumed=50000.0,
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_i(obligation)

        # Line 7: 200000 - 50000 = 150000
        assert result['line_7_subtotal'] == 150000.0
        # Gross profit = 200000 - 100000 - 10000 = 90000
        assert result['line_14_gross_profit'] == 90000.0
        # Line 15 = 0 (mortgage is NOT > total basis)
        assert result['line_15_mortgage_excess'] == 0.0
        # Line 16 = 150000 - 0 = 150000
        assert result['line_16_subtotal'] == 150000.0
        # Contract price = 40000 + 0 = 40000? No, should be 150000
        # Actually need to recalculate...
        # Contract price = selling price - mortgage = 150000
        # But it can't be less than gross profit
        assert result['line_17_contract_price'] >= result['line_14_gross_profit']

    def test_part_i_with_recapture(self):
        """Test Part I with depreciation recapture."""
        obligation = InstallmentObligation(
            property_description="Equipment",
            date_acquired="2015-01-01",
            date_sold="2023-06-15",
            year_of_sale=2023,
            selling_price=100000.0,
            adjusted_basis=80000.0,
            selling_expenses=5000.0,
            depreciation_allowed=30000.0,
            section_1245_recapture=20000.0,
            seller_financing=100000.0,
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_i(obligation)

        # Line 12: Recapture = 20000
        assert result['line_12_recapture'] == 20000.0
        # Adjusted basis = 80000 - 30000 = 50000
        assert result['line_10_adjusted_basis'] == 50000.0
        # Total basis = 50000 + 5000 + 20000 = 75000
        assert result['line_13_total_basis'] == 75000.0


# ============== Form 6252 Part II Tests ==============

class TestForm6252PartII:
    """Tests for Part II - Installment Sale Income."""

    def test_part_ii_installment_income(self):
        """Test installment sale income calculation."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=65000.0,
            selling_expenses=0.0,
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_ii(obligation, is_year_of_sale=False)

        # GP = 35000, Contract = 100000, GP% = 35%
        assert result['line_19_gp_percentage'] == 0.35
        # Payments = 10000
        assert result['line_20_payments_received'] == 10000.0
        # Installment income = 10000 * 0.35 = 3500
        assert result['line_21_installment_income'] == 3500.0
        # Interest income
        assert result['interest_income'] == 2000.0

    def test_part_ii_year_of_sale(self):
        """Test Part II in year of sale (includes mortgage excess)."""
        obligation = InstallmentObligation(
            property_description="Property",
            date_acquired="2015-01-01",
            date_sold="2025-06-15",
            year_of_sale=2025,
            selling_price=200000.0,
            adjusted_basis=80000.0,
            selling_expenses=10000.0,
            existing_mortgage_assumed=100000.0,  # Exceeds basis
            seller_financing=100000.0,
            payments_current_year=[
                InstallmentPayment(
                    payment_date="2025-12-15",
                    total_payment=15000.0,
                    principal_portion=10000.0,
                    interest_portion=5000.0,
                )
            ],
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        result = form.calculate_part_ii(obligation, is_year_of_sale=True)

        # Year of sale includes mortgage excess as deemed payment
        # Mortgage excess = 100000 - (80000 + 10000) = 10000
        # Wait, need to recalculate properly
        # Total basis for Part I = adjusted_basis + expenses + recapture
        # = 80000 + 10000 + 0 = 90000
        # Mortgage excess = max(0, 100000 - 90000) = 10000
        # Payments = 10000 principal + 10000 mortgage excess = 20000
        assert result['line_20_payments_received'] == 20000.0

    def test_part_ii_with_depreciation_recapture(self):
        """Test depreciation recapture in year of sale."""
        obligation = InstallmentObligation(
            property_description="Equipment",
            date_acquired="2015-01-01",
            date_sold="2025-06-15",
            year_of_sale=2025,
            selling_price=100000.0,
            adjusted_basis=80000.0,
            selling_expenses=5000.0,
            depreciation_allowed=30000.0,
            section_1245_recapture=15000.0,
            seller_financing=100000.0,
            payments_current_year=[
                InstallmentPayment(
                    payment_date="2025-12-15",
                    total_payment=12000.0,
                    principal_portion=10000.0,
                    interest_portion=2000.0,
                )
            ],
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        result = form.calculate_part_ii(obligation, is_year_of_sale=True)

        # Depreciation recapture recognized in year of sale
        assert result['depreciation_recapture'] == 15000.0


# ============== Form 6252 Part III Tests ==============

class TestForm6252PartIII:
    """Tests for Part III - Related Party Sales."""

    def test_not_related_party(self):
        """Test non-related party sale."""
        obligation = make_obligation()
        obligation.related_party_type = RelatedPartyType.NOT_RELATED

        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_iii_related_party(obligation)

        assert result['is_related_party_sale'] is False
        assert result['accelerated_gain'] == 0.0

    def test_related_party_no_resale(self):
        """Test related party sale without resale."""
        obligation = make_obligation()
        obligation.related_party_type = RelatedPartyType.CHILD
        obligation.related_party_resold = False

        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_iii_related_party(obligation)

        assert result['is_related_party_sale'] is True
        assert result['accelerated_gain'] == 0.0

    def test_related_party_resale_within_2_years(self):
        """Test related party resale acceleration."""
        obligation = InstallmentObligation(
            property_description="Land",
            property_category=PropertyCategory.REAL_PROPERTY,
            date_acquired="2010-01-01",
            date_sold="2024-06-15",
            year_of_sale=2024,
            selling_price=200000.0,
            adjusted_basis=100000.0,
            selling_expenses=10000.0,
            seller_financing=200000.0,
            total_payments_prior_years=20000.0,
            related_party_type=RelatedPartyType.CHILD,
            related_party_resold=True,
            resale_date="2025-03-01",  # Within 2 years
            resale_amount=220000.0,
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        result = form.calculate_part_iii_related_party(obligation)

        assert result['is_related_party_sale'] is True
        assert result['buyer_resold_within_2_years'] is True
        assert result['accelerated_gain'] > 0

    def test_depreciable_property_to_related_party(self):
        """Test depreciable property to related party (not eligible)."""
        obligation = InstallmentObligation(
            property_description="Equipment",
            property_category=PropertyCategory.DEPRECIABLE_PROPERTY_RELATED,
            date_acquired="2015-01-01",
            date_sold="2025-06-15",
            year_of_sale=2025,
            selling_price=100000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
            depreciation_allowed=20000.0,
            seller_financing=100000.0,
            related_party_type=RelatedPartyType.CONTROLLED_CORPORATION,
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_part_iii_related_party(obligation)

        # All gain should be accelerated
        assert result['accelerated_gain'] == obligation.get_gross_profit()
        assert "depreciable property" in result['reason_for_acceleration'].lower()


# ============== Section 453A Tests ==============

class TestSection453A:
    """Tests for Section 453A interest charge on large sales."""

    def test_small_sale_no_interest(self):
        """No interest charge for sales under $5M."""
        obligation = make_obligation(selling_price=1000000.0)
        obligation.is_large_installment_sale = False

        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_section_453a_interest(obligation)

        assert result['applies'] is False
        assert result['interest_charge'] == 0.0

    def test_large_sale_interest_charge(self):
        """Interest charge applies to large sales."""
        obligation = InstallmentObligation(
            property_description="Commercial Building",
            date_acquired="2010-01-01",
            date_sold="2023-06-15",
            year_of_sale=2023,
            selling_price=8000000.0,  # Over $5M threshold
            adjusted_basis=4000000.0,
            selling_expenses=200000.0,
            seller_financing=8000000.0,
            total_payments_prior_years=1000000.0,
            is_large_installment_sale=True,
            payments_current_year=[
                InstallmentPayment(
                    payment_date="2025-03-15",
                    total_payment=600000.0,
                    principal_portion=500000.0,
                    interest_portion=100000.0,
                )
            ],
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_section_453a_interest(obligation)

        assert result['applies'] is True
        assert result['outstanding_balance'] > 0
        assert result['deferred_tax_liability'] > 0
        assert result['interest_charge'] > 0


# ============== Pledging Rules Tests ==============

class TestPledgingRules:
    """Tests for pledging installment obligations."""

    def test_no_pledging(self):
        """No gain triggered without pledging."""
        obligation = make_obligation()
        obligation.amount_pledged = 0.0

        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_pledging_rules(obligation)

        assert result['applies'] is False
        assert result['triggered_gain'] == 0.0

    def test_pledging_triggers_gain(self):
        """Pledging obligation triggers gain recognition."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=65000.0,
            selling_expenses=0.0,
        )
        obligation.amount_pledged = 20000.0

        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_pledging_rules(obligation)

        # GP% = 35%, Pledged = 20000
        # Triggered gain = 20000 * 0.35 = 7000
        assert result['applies'] is True
        assert result['triggered_gain'] == 7000.0


# ============== Form 6252 Complete Calculation Tests ==============

class TestForm6252Complete:
    """Tests for complete Form 6252 calculations."""

    def test_calculate_for_obligation(self):
        """Test complete calculation for single obligation."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=60000.0,
            selling_expenses=5000.0,
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        result = form.calculate_for_obligation(obligation, is_year_of_sale=False)

        assert 'part_i' in result
        assert 'part_ii' in result
        assert 'summary' in result
        assert result['summary']['gross_profit'] == 35000.0
        assert result['summary']['interest_income'] == 2000.0

    def test_calculate_all_multiple_obligations(self):
        """Test calculation with multiple obligations."""
        obligation1 = make_obligation(
            description="Property 1",
            selling_price=100000.0,
            adjusted_basis=60000.0,
            year_of_sale=2023,
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        obligation2 = make_obligation(
            description="Property 2",
            selling_price=200000.0,
            adjusted_basis=120000.0,
            year_of_sale=2024,
            current_year_principal=20000.0,
            current_year_interest=4000.0,
        )
        form = Form6252(
            tax_year=2025,
            installment_obligations=[obligation1, obligation2]
        )
        result = form.calculate_all()

        assert result['obligation_count'] == 2
        assert result['totals']['total_interest_income'] == 6000.0

    def test_get_total_methods(self):
        """Test convenience methods for totals."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=65000.0,
            selling_expenses=0.0,
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])

        # GP% = 35%, Payments = 10000, Income = 3500
        assert form.get_total_installment_income() == 3500.0
        assert form.get_total_interest_income() == 2000.0


# ============== Integration Tests ==============

class TestForm6252Integration:
    """Tests for Form 6252 integration with Income and Engine."""

    def test_income_helper_methods(self):
        """Test Income model Form 6252 helper methods."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=65000.0,
            selling_expenses=0.0,
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        income = Income(form_6252=form)

        assert income.get_form_6252_installment_income() == 3500.0
        assert income.get_form_6252_interest_income() == 2000.0
        assert income.get_form_6252_capital_gain() == 3500.0

    def test_engine_calculates_form_6252(self, engine):
        """Test engine calculates Form 6252 fields."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=65000.0,
            selling_expenses=0.0,
            current_year_principal=10000.0,
            current_year_interest=2000.0,
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        tax_return = create_tax_return(form_6252=form)

        breakdown = engine.calculate(tax_return)

        assert breakdown.form_6252_installment_income == 3500.0
        assert breakdown.form_6252_interest_income == 2000.0

    def test_form_6252_summary(self):
        """Test Form 6252 summary generation."""
        obligation = make_obligation(
            selling_price=100000.0,
            adjusted_basis=65000.0,
            selling_expenses=0.0,
        )
        form = Form6252(tax_year=2025, installment_obligations=[obligation])
        income = Income(form_6252=form)

        summary = income.get_form_6252_summary()
        assert summary is not None
        assert summary['total_obligations'] == 1
        assert 'totals' in summary


# ============== Edge Cases ==============

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_no_obligations(self):
        """Form 6252 with no obligations."""
        form = Form6252(installment_obligations=[])
        result = form.calculate_all()

        assert result['obligation_count'] == 0
        assert result['totals']['total_installment_income'] == 0.0

    def test_zero_payments(self):
        """Obligation with no payments in current year."""
        obligation = make_obligation(
            current_year_principal=0.0,
            current_year_interest=0.0,
        )
        form = Form6252(installment_obligations=[obligation])
        result = form.calculate_for_obligation(obligation)

        assert result['summary']['installment_income'] == 0.0
        assert result['summary']['interest_income'] == 0.0

    def test_fully_paid_obligation(self):
        """Obligation that was fully paid in prior years."""
        obligation = make_obligation(
            seller_financing=50000.0,
            payments_prior_years=50000.0,
            current_year_principal=0.0,
        )
        assert obligation.get_remaining_installment_balance() == 0.0

    def test_100_percent_gp_percentage(self):
        """Test with 100% gross profit percentage (zero basis)."""
        obligation = InstallmentObligation(
            property_description="Inherited Land",
            date_acquired="2000-01-01",
            date_sold="2023-06-15",
            year_of_sale=2023,
            selling_price=100000.0,
            adjusted_basis=0.0,  # Stepped-up basis or fully depreciated
            selling_expenses=0.0,
            seller_financing=100000.0,
            payments_current_year=[
                InstallmentPayment(
                    payment_date="2025-03-15",
                    total_payment=12000.0,
                    principal_portion=10000.0,
                    interest_portion=2000.0,
                )
            ],
        )
        form = Form6252(installment_obligations=[obligation])

        # GP% = 100%
        assert obligation.get_gross_profit_percentage() == 1.0
        result = form.calculate_part_ii(obligation)
        # All principal is taxable
        assert result['line_21_installment_income'] == 10000.0


# ============== Eligibility Tests ==============

class TestInstallmentEligibility:
    """Tests for installment method eligibility."""

    def test_eligible_real_property(self):
        """Real property is eligible."""
        result = calculate_installment_eligibility(
            property_type="real_property",
            is_inventory=False,
            is_publicly_traded=False,
        )
        assert result['eligible'] is True

    def test_ineligible_inventory(self):
        """Inventory not eligible."""
        result = calculate_installment_eligibility(
            property_type="inventory",
            is_inventory=True,
        )
        assert result['eligible'] is False
        assert "inventory" in result['reason'].lower()

    def test_ineligible_publicly_traded(self):
        """Publicly traded securities not eligible."""
        result = calculate_installment_eligibility(
            property_type="securities",
            is_publicly_traded=True,
        )
        assert result['eligible'] is False
        assert "publicly traded" in result['reason'].lower()

    def test_ineligible_depreciable_to_related(self):
        """Depreciable property to related party not eligible."""
        result = calculate_installment_eligibility(
            property_type="equipment",
            is_related_party_depreciable=True,
        )
        assert result['eligible'] is False
        assert "related party" in result['reason'].lower()
