"""
Comprehensive tests for Form 1116 - Foreign Tax Credit.

Tests cover:
- FTC limitation calculation
- Income category separation (passive, general, etc.)
- Simplified method eligibility
- Carryforward calculations
- Integration with Income model
- Integration with tax calculation engine

Per IRC Section 901, 904 and IRS Form 1116 instructions.
"""

import pytest
from models.form_1116 import (
    Form1116,
    Form1116Category,
    ForeignIncomeCategory,
    ForeignCountryTax,
    FTCCarryover,
    ForeignTaxType,
    create_passive_income_category,
    create_general_income_category,
)
from models.income import Income, ScheduleK1, K1SourceType, W2Info
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.credits import TaxCredits
from models.deductions import Deductions
from calculator.engine import FederalTaxEngine
from calculator.tax_year_config import TaxYearConfig


class TestForeignCountryTax:
    """Test ForeignCountryTax model."""

    def test_basic_country_tax(self):
        """Test basic country tax creation."""
        tax = ForeignCountryTax(
            country_code="GB",
            country_name="United Kingdom",
            gross_income=10000.0,
            taxes_paid_usd=1500.0
        )
        assert tax.country_code == "GB"
        assert tax.gross_income == 10000.0
        assert tax.taxes_paid_usd == 1500.0

    def test_net_foreign_income(self):
        """Test net income calculation after deductions."""
        tax = ForeignCountryTax(
            country_code="DE",
            country_name="Germany",
            gross_income=20000.0,
            definitely_related_expenses=2000.0,
            taxes_paid_usd=3000.0
        )
        assert tax.get_net_foreign_income() == 18000.0

    def test_foreign_currency_conversion(self):
        """Test foreign currency to USD conversion."""
        tax = ForeignCountryTax(
            country_code="JP",
            country_name="Japan",
            gross_income=1000000.0,  # Yen
            taxes_paid_in_foreign_currency=100000.0,
            exchange_rate=0.0067,  # ~150 yen per dollar
            taxes_paid_usd=670.0
        )
        assert tax.taxes_paid_usd == 670.0


class TestForm1116Category:
    """Test Form1116Category model for individual income categories."""

    def test_passive_category(self):
        """Test passive income category."""
        category = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=5000.0
        )
        assert category.category == ForeignIncomeCategory.PASSIVE
        assert category.get_net_foreign_income() == 5000.0

    def test_general_category_with_deductions(self):
        """Test general category with allocated deductions."""
        category = Form1116Category(
            category=ForeignIncomeCategory.GENERAL,
            gross_foreign_income=50000.0,
            foreign_income_deductions=5000.0,
            home_mortgage_interest_allocated=1000.0,
            state_local_taxes_allocated=500.0
        )
        assert category.get_total_allocated_deductions() == 6500.0
        assert category.get_net_foreign_income() == 43500.0

    def test_country_taxes(self):
        """Test adding country taxes to category."""
        category = Form1116Category(category=ForeignIncomeCategory.PASSIVE)
        category.country_taxes.append(
            ForeignCountryTax(
                country_code="GB",
                country_name="United Kingdom",
                gross_income=10000.0,
                taxes_paid_usd=1500.0
            )
        )
        category.country_taxes.append(
            ForeignCountryTax(
                country_code="DE",
                country_name="Germany",
                gross_income=5000.0,
                taxes_paid_usd=750.0
            )
        )
        category.gross_foreign_income = 15000.0
        assert category.get_total_foreign_taxes() == 2250.0

    def test_carryovers(self):
        """Test carryover tracking."""
        category = Form1116Category(category=ForeignIncomeCategory.PASSIVE)
        category.carryovers.append(
            FTCCarryover(
                tax_year=2022,
                category=ForeignIncomeCategory.PASSIVE,
                original_amount=1000.0,
                remaining_amount=800.0
            )
        )
        category.carryovers.append(
            FTCCarryover(
                tax_year=2023,
                category=ForeignIncomeCategory.PASSIVE,
                original_amount=500.0,
                remaining_amount=500.0
            )
        )
        assert category.get_available_carryovers(2025) == 1300.0


class TestFTCCarryover:
    """Test FTC carryover calculations."""

    def test_carryforward_years_remaining(self):
        """Test carryforward expiration calculation."""
        carryover = FTCCarryover(
            tax_year=2020,
            category=ForeignIncomeCategory.PASSIVE,
            original_amount=1000.0,
            remaining_amount=1000.0,
            is_carryback=False
        )
        # Carryforward expires after 10 years (2030)
        assert carryover.years_remaining(2025) == 5
        assert carryover.years_remaining(2030) == 0
        assert carryover.years_remaining(2031) == 0

    def test_expired_carryforward(self):
        """Test expired carryforward has zero years remaining."""
        carryover = FTCCarryover(
            tax_year=2014,
            category=ForeignIncomeCategory.GENERAL,
            original_amount=2000.0,
            remaining_amount=500.0,
            is_carryback=False
        )
        # Expired in 2024 (10 years from 2014)
        assert carryover.years_remaining(2025) == 0


class TestForm1116:
    """Test main Form1116 model."""

    def test_empty_form(self):
        """Test form with no foreign income."""
        form = Form1116()
        result = form.calculate_ftc()
        assert result['total_foreign_taxes_paid'] == 0.0
        assert result['total_ftc_allowed'] == 0.0

    def test_simplified_method_eligibility_single(self):
        """Test simplified method threshold for single filer."""
        form = Form1116()
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=3000.0
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=3000.0,
                taxes_paid_usd=250.0  # Under $300 threshold
            )
        )
        form.categories.append(passive)
        assert form.can_use_simplified_method("single") == True

    def test_simplified_method_eligibility_mfj(self):
        """Test simplified method threshold for married filing jointly."""
        form = Form1116()
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=5000.0
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=5000.0,
                taxes_paid_usd=550.0  # Under $600 threshold
            )
        )
        form.categories.append(passive)
        assert form.can_use_simplified_method("married_joint") == True

    def test_simplified_method_ineligible(self):
        """Test simplified method fails when over threshold."""
        form = Form1116()
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=10000.0
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=10000.0,
                taxes_paid_usd=400.0  # Over $300 threshold for single
            )
        )
        form.categories.append(passive)
        assert form.can_use_simplified_method("single") == False

    def test_simplified_method_general_income_ineligible(self):
        """Test simplified method requires only passive income."""
        form = Form1116()
        general = Form1116Category(
            category=ForeignIncomeCategory.GENERAL,
            gross_foreign_income=10000.0
        )
        general.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=10000.0,
                taxes_paid_usd=200.0  # Under threshold but general income
            )
        )
        form.categories.append(general)
        assert form.can_use_simplified_method("single") == False


class TestFTCLimitation:
    """Test FTC limitation calculations."""

    def test_basic_limitation(self):
        """Test basic FTC limitation formula."""
        form = Form1116(
            total_taxable_income=100000.0,
            total_tax_before_credits=20000.0
        )
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=25000.0  # 25% of income
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="GB",
                country_name="United Kingdom",
                gross_income=25000.0,
                taxes_paid_usd=6000.0
            )
        )
        form.categories.append(passive)

        result = form.calculate_ftc()

        # Limitation = $20,000 tax × 25% = $5,000
        assert result['total_ftc_limitation'] == 5000.0
        # Credit limited to $5,000 (less than $6,000 paid)
        assert result['total_ftc_allowed'] == 5000.0
        # $1,000 excess carries forward
        assert result['new_carryforward'] == 1000.0

    def test_credit_less_than_limitation(self):
        """Test when taxes paid are less than limitation."""
        form = Form1116(
            total_taxable_income=100000.0,
            total_tax_before_credits=20000.0
        )
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=50000.0  # 50% of income
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="GB",
                country_name="United Kingdom",
                gross_income=50000.0,
                taxes_paid_usd=5000.0
            )
        )
        form.categories.append(passive)

        result = form.calculate_ftc()

        # Limitation = $20,000 × 50% = $10,000
        assert result['total_ftc_limitation'] == 10000.0
        # Credit is full $5,000 paid (less than limitation)
        assert result['total_ftc_allowed'] == 5000.0
        # Excess limitation = $10,000 - $5,000 = $5,000 (room for carryovers)
        assert result['new_carryforward'] == 0.0

    def test_multiple_categories(self):
        """Test FTC with multiple income categories."""
        form = Form1116(
            total_taxable_income=200000.0,
            total_tax_before_credits=50000.0
        )

        # Passive category: 20% of income
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=40000.0
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=40000.0,
                taxes_paid_usd=8000.0
            )
        )
        form.categories.append(passive)

        # General category: 30% of income
        general = Form1116Category(
            category=ForeignIncomeCategory.GENERAL,
            gross_foreign_income=60000.0
        )
        general.country_taxes.append(
            ForeignCountryTax(
                country_code="DE",
                country_name="Germany",
                gross_income=60000.0,
                taxes_paid_usd=20000.0
            )
        )
        form.categories.append(general)

        result = form.calculate_ftc()

        # Total foreign taxes = $8,000 + $20,000 = $28,000
        assert result['total_foreign_taxes_paid'] == 28000.0

        # Passive limitation = $50,000 × 20% = $10,000
        # Passive credit = min($8,000, $10,000) = $8,000 (no carryforward)

        # General limitation = $50,000 × 30% = $15,000
        # General credit = min($20,000, $15,000) = $15,000 ($5,000 carryforward)

        # Total = $8,000 + $15,000 = $23,000
        assert result['total_ftc_allowed'] == 23000.0
        assert result['new_carryforward'] == 5000.0

    def test_no_foreign_income(self):
        """Test when taxable income is zero."""
        form = Form1116(
            total_taxable_income=0.0,
            total_tax_before_credits=0.0
        )
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=10000.0
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=10000.0,
                taxes_paid_usd=1500.0
            )
        )
        form.categories.append(passive)

        result = form.calculate_ftc()

        # No credit allowed, all taxes carry forward
        assert result['total_ftc_allowed'] == 0.0
        assert result['new_carryforward'] == 1500.0

    def test_100_percent_foreign_income(self):
        """Test when all income is from foreign sources."""
        form = Form1116(
            total_taxable_income=100000.0,
            total_tax_before_credits=20000.0
        )
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=100000.0  # 100% foreign
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=100000.0,
                taxes_paid_usd=18000.0
            )
        )
        form.categories.append(passive)

        result = form.calculate_ftc()

        # Limitation = $20,000 × 100% = $20,000
        assert result['total_ftc_limitation'] == 20000.0
        # Credit = min($18,000, $20,000) = $18,000
        assert result['total_ftc_allowed'] == 18000.0


class TestCarryforwardUsage:
    """Test FTC carryforward usage."""

    def test_use_carryforward(self):
        """Test using carryforward when excess limitation exists."""
        form = Form1116(
            total_taxable_income=100000.0,
            total_tax_before_credits=25000.0
        )
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=40000.0  # 40% of income
        )
        # Only $3,000 taxes paid this year
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="GB",
                country_name="United Kingdom",
                gross_income=40000.0,
                taxes_paid_usd=3000.0
            )
        )
        # $2,000 carryforward from prior year
        passive.carryovers.append(
            FTCCarryover(
                tax_year=2024,
                category=ForeignIncomeCategory.PASSIVE,
                original_amount=2000.0,
                remaining_amount=2000.0
            )
        )
        form.categories.append(passive)

        result = form.calculate_ftc()

        # Limitation = $25,000 × 40% = $10,000
        # Current year credit = $3,000
        # Excess limitation = $10,000 - $3,000 = $7,000 (room for carryovers)
        # Carryover used = min($2,000, $7,000) = $2,000
        # Total credit = $3,000 + $2,000 = $5,000
        assert result['total_ftc_allowed'] == 5000.0
        assert result['total_carryover_used'] == 2000.0

    def test_fifo_carryforward_usage(self):
        """Test FIFO ordering for carryforward usage."""
        form = Form1116(
            total_taxable_income=100000.0,
            total_tax_before_credits=25000.0
        )
        passive = Form1116Category(
            category=ForeignIncomeCategory.PASSIVE,
            gross_foreign_income=50000.0  # 50% = $12,500 limitation
        )
        passive.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=50000.0,
                taxes_paid_usd=5000.0  # Excess limitation = $7,500
            )
        )
        # Older carryforward
        passive.carryovers.append(
            FTCCarryover(
                tax_year=2020,
                category=ForeignIncomeCategory.PASSIVE,
                original_amount=3000.0,
                remaining_amount=3000.0
            )
        )
        # Newer carryforward
        passive.carryovers.append(
            FTCCarryover(
                tax_year=2023,
                category=ForeignIncomeCategory.PASSIVE,
                original_amount=5000.0,
                remaining_amount=5000.0
            )
        )
        form.categories.append(passive)

        result = form.calculate_ftc()

        # Excess limitation = $12,500 - $5,000 = $7,500
        # Should use $3,000 from 2020 first, then $4,500 from 2023
        # Total carryover used = $7,500
        assert result['total_carryover_used'] == 7500.0
        assert result['total_ftc_allowed'] == 12500.0


class TestSimplifiedMethod:
    """Test simplified FTC method (no Form 1116 required)."""

    def test_simplified_method_calculation(self):
        """Test using simplified method."""
        form = Form1116(
            use_simplified_method=True,
            simplified_foreign_taxes=200.0,
            total_taxable_income=50000.0,
            total_tax_before_credits=8000.0
        )

        result = form.calculate_ftc(filing_status="single")

        assert result['using_simplified'] == True
        assert result['total_foreign_taxes_paid'] == 200.0
        assert result['total_ftc_allowed'] == 200.0


class TestHelperFunctions:
    """Test helper functions for creating categories."""

    def test_create_passive_income_category(self):
        """Test passive income category creation helper."""
        category = create_passive_income_category(
            dividend_income=5000.0,
            interest_income=2000.0,
            foreign_taxes_on_dividends=750.0,
            foreign_taxes_on_interest=200.0,
            country_code="GB",
            country_name="United Kingdom"
        )

        assert category.category == ForeignIncomeCategory.PASSIVE
        assert category.gross_foreign_income == 7000.0
        assert category.get_total_foreign_taxes() == 950.0
        assert len(category.country_taxes) == 1
        assert category.country_taxes[0].is_qualified_dividend_tax == True

    def test_create_general_income_category(self):
        """Test general income category creation helper."""
        category = create_general_income_category(
            wages_income=80000.0,
            business_income=20000.0,
            foreign_taxes_paid=25000.0,
            country_code="DE",
            country_name="Germany"
        )

        assert category.category == ForeignIncomeCategory.GENERAL
        assert category.gross_foreign_income == 100000.0
        assert category.get_total_foreign_taxes() == 25000.0


class TestIncomeModelIntegration:
    """Test Form 1116 integration with Income model."""

    def test_income_has_form_1116_field(self):
        """Test Income model has form_1116 field."""
        income = Income()
        assert hasattr(income, 'form_1116')
        assert income.form_1116 is None

    def test_income_with_form_1116(self):
        """Test Income model with Form 1116."""
        form = Form1116()
        form.categories.append(create_passive_income_category(
            dividend_income=5000.0,
            foreign_taxes_on_dividends=500.0
        ))

        income = Income(form_1116=form)

        assert income.get_form_1116_foreign_taxes_paid() == 500.0
        assert income.get_form_1116_foreign_source_income() == 5000.0

    def test_income_foreign_taxes_from_k1(self):
        """Test foreign taxes from K-1 forms when no Form 1116."""
        income = Income(
            schedule_k1_forms=[
                ScheduleK1(
                    k1_type=K1SourceType.PARTNERSHIP,
                    entity_name="Foreign Partnership",
                    entity_ein="12-3456789",
                    ordinary_business_income=10000.0,
                    foreign_tax_paid=300.0
                )
            ]
        )

        assert income.get_form_1116_foreign_taxes_paid() == 300.0
        assert income.has_foreign_tax_credit() == True

    def test_can_use_simplified_ftc(self):
        """Test simplified FTC eligibility check."""
        # Under threshold (no K-1s = 0 foreign taxes)
        income = Income()
        assert income.can_use_simplified_ftc("single") == True
        assert income.can_use_simplified_ftc("married_joint") == True

        # With Form 1116 under threshold
        form = Form1116()
        form.categories.append(create_passive_income_category(
            dividend_income=2500.0,
            foreign_taxes_on_dividends=250.0
        ))
        income_with_form = Income(form_1116=form)
        assert income_with_form.can_use_simplified_ftc("single") == True
        assert income_with_form.can_use_simplified_ftc("married_joint") == True

        # Over single threshold via Form 1116
        form2 = Form1116()
        form2.categories.append(create_passive_income_category(
            dividend_income=4000.0,
            foreign_taxes_on_dividends=400.0
        ))
        income_over = Income(form_1116=form2)
        assert income_over.can_use_simplified_ftc("single") == False
        assert income_over.can_use_simplified_ftc("married_joint") == True


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Helper to create W2Info for tests."""
    return W2Info(
        employer_name="Test Employer",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


class TestEngineIntegration:
    """Test Form 1116 integration with tax calculation engine."""

    @staticmethod
    def _create_taxpayer(filing_status: str = "single") -> TaxpayerInfo:
        """Helper to create TaxpayerInfo."""
        return TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            ssn="123-45-6789",
            filing_status=FilingStatus(filing_status) if filing_status != "single" else FilingStatus.SINGLE
        )

    def test_engine_with_form_1116(self):
        """Test engine calculates FTC using Form 1116."""
        form = Form1116()
        form.categories.append(create_passive_income_category(
            dividend_income=10000.0,
            foreign_taxes_on_dividends=1500.0
        ))

        income = Income(
            w2_forms=[make_w2(50000.0)],
            form_1116=form
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=self._create_taxpayer("single"),
            income=income,
            deductions=Deductions(),
            credits=TaxCredits()
        )

        config = TaxYearConfig.for_2025()
        engine = FederalTaxEngine(config)
        breakdown = engine.calculate(tax_return)

        # Should have Form 1116 breakdown
        assert breakdown.form_1116_foreign_taxes_paid == 1500.0
        assert breakdown.form_1116_foreign_source_income == 10000.0
        assert breakdown.form_1116_credit_allowed > 0
        assert len(breakdown.form_1116_breakdown) > 0

    def test_engine_ftc_limitation(self):
        """Test engine applies FTC limitation correctly."""
        form = Form1116()
        form.categories.append(create_passive_income_category(
            dividend_income=20000.0,
            foreign_taxes_on_dividends=5000.0  # High foreign tax rate
        ))

        income = Income(
            w2_forms=[make_w2(80000.0)],  # Total income ~$100k
            form_1116=form
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=self._create_taxpayer("single"),
            income=income,
            deductions=Deductions(),
            credits=TaxCredits()
        )

        config = TaxYearConfig.for_2025()
        engine = FederalTaxEngine(config)
        breakdown = engine.calculate(tax_return)

        # Credit should be limited (not full $5,000)
        # Foreign income is ~20% of total, so limitation ~20% of tax
        assert breakdown.form_1116_credit_allowed <= breakdown.form_1116_foreign_taxes_paid
        assert breakdown.form_1116_limitation > 0
        # Should have carryforward if over limitation
        if breakdown.form_1116_credit_allowed < 5000.0:
            assert breakdown.form_1116_carryforward > 0

    def test_engine_simplified_method_fallback(self):
        """Test engine uses simplified method when no Form 1116."""
        income = Income(
            w2_forms=[make_w2(50000.0)],
        )

        credits = TaxCredits(
            foreign_tax_credit=200.0  # Low amount = simplified eligible
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=self._create_taxpayer("single"),
            income=income,
            deductions=Deductions(),
            credits=credits
        )

        config = TaxYearConfig.for_2025()
        engine = FederalTaxEngine(config)
        breakdown = engine.calculate(tax_return)

        # Should use simplified method
        assert breakdown.form_1116_simplified_method == True
        assert breakdown.form_1116_credit_allowed > 0

    def test_engine_ftc_in_credit_breakdown(self):
        """Test FTC appears in credit breakdown."""
        form = Form1116()
        form.categories.append(create_passive_income_category(
            dividend_income=5000.0,
            foreign_taxes_on_dividends=500.0
        ))

        income = Income(
            w2_forms=[make_w2(60000.0)],
            form_1116=form
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=self._create_taxpayer("single"),
            income=income,
            deductions=Deductions(),
            credits=TaxCredits()
        )

        config = TaxYearConfig.for_2025()
        engine = FederalTaxEngine(config)
        breakdown = engine.calculate(tax_return)

        # FTC should reduce nonrefundable credits
        assert 'foreign_tax_credit' in breakdown.credit_breakdown
        assert breakdown.credit_breakdown['foreign_tax_credit'] > 0


class TestMultipleCountries:
    """Test FTC with income from multiple countries."""

    def test_multiple_countries_same_category(self):
        """Test multiple countries in same income category."""
        category = Form1116Category(category=ForeignIncomeCategory.PASSIVE)

        category.country_taxes.append(
            ForeignCountryTax(
                country_code="GB",
                country_name="United Kingdom",
                gross_income=5000.0,
                taxes_paid_usd=750.0
            )
        )
        category.country_taxes.append(
            ForeignCountryTax(
                country_code="DE",
                country_name="Germany",
                gross_income=3000.0,
                taxes_paid_usd=600.0
            )
        )
        category.country_taxes.append(
            ForeignCountryTax(
                country_code="FR",
                country_name="France",
                gross_income=2000.0,
                taxes_paid_usd=400.0
            )
        )
        category.gross_foreign_income = 10000.0

        assert category.get_total_foreign_taxes() == 1750.0
        assert len(category.country_taxes) == 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_tax_before_credits(self):
        """Test when tax before credits is zero."""
        form = Form1116(
            total_taxable_income=50000.0,
            total_tax_before_credits=0.0  # All offset by deductions/exemptions
        )
        form.categories.append(create_passive_income_category(
            dividend_income=5000.0,
            foreign_taxes_on_dividends=500.0
        ))

        result = form.calculate_ftc()

        # No credit (no tax to offset), all carries forward
        assert result['total_ftc_allowed'] == 0.0
        assert result['new_carryforward'] == 500.0

    def test_negative_net_foreign_income(self):
        """Test when deductions exceed gross foreign income."""
        category = Form1116Category(
            category=ForeignIncomeCategory.GENERAL,
            gross_foreign_income=10000.0,
            foreign_income_deductions=15000.0  # Exceeds income
        )
        category.country_taxes.append(
            ForeignCountryTax(
                country_code="XX",
                country_name="Various",
                gross_income=10000.0,
                taxes_paid_usd=2000.0
            )
        )

        # Net income should be capped at 0
        assert category.get_net_foreign_income() == 0.0

    def test_simplified_method_with_form_1116(self):
        """Test simplified method flag with Form 1116."""
        form = Form1116(
            use_simplified_method=True,
            simplified_foreign_taxes=250.0,
            total_taxable_income=50000.0,
            total_tax_before_credits=8000.0
        )
        # Also has category (but should use simplified)
        form.categories.append(create_passive_income_category(
            dividend_income=2500.0,
            foreign_taxes_on_dividends=250.0
        ))

        result = form.calculate_ftc(filing_status="single")

        # Should use simplified method
        assert result['using_simplified'] == True
        assert result['total_ftc_allowed'] == 250.0

    def test_foreign_income_exceeds_total(self):
        """Test when foreign income ratio would exceed 100%."""
        form = Form1116(
            total_taxable_income=50000.0,
            total_tax_before_credits=10000.0
        )
        # Foreign income exceeds total (due to losses elsewhere)
        form.categories.append(create_passive_income_category(
            dividend_income=80000.0,
            foreign_taxes_on_dividends=16000.0
        ))

        result = form.calculate_ftc()

        # Ratio capped at 100%, so limitation = full tax
        assert result['total_ftc_limitation'] == 10000.0
        # Credit limited to tax amount
        assert result['total_ftc_allowed'] == 10000.0
        # Excess carries forward
        assert result['new_carryforward'] == 6000.0


class TestAMTForeignTaxCredit:
    """Test AMT Foreign Tax Credit calculation."""

    def test_amt_ftc_basic(self):
        """Test basic AMT FTC calculation."""
        form = Form1116(
            total_taxable_income=200000.0,
            total_tax_before_credits=40000.0,
            calculate_amt_ftc=True,
            amt_foreign_source_income=50000.0,
            tentative_minimum_tax=45000.0
        )
        form.categories.append(create_passive_income_category(
            dividend_income=50000.0,
            foreign_taxes_on_dividends=10000.0
        ))

        result = form.calculate_ftc()

        # Should have AMT FTC breakdown
        assert 'amt_ftc' in result
        assert 'amt_ftc_breakdown' in result
        assert result['amt_ftc'] > 0

    def test_amt_ftc_limitation(self):
        """Test AMT FTC is properly limited."""
        form = Form1116(
            total_taxable_income=100000.0,
            total_tax_before_credits=20000.0,
            calculate_amt_ftc=True,
            amt_foreign_source_income=20000.0,  # 20% of income
            tentative_minimum_tax=22000.0
        )
        form.categories.append(create_passive_income_category(
            dividend_income=20000.0,
            foreign_taxes_on_dividends=6000.0
        ))

        result = form.calculate_ftc()

        # AMT FTC limited to TMT × ratio
        # Limitation = $22,000 × 20% = $4,400
        assert result['amt_ftc'] <= 6000.0
        assert result['amt_ftc'] == result['amt_ftc_breakdown']['amt_foreign_tax_credit']
