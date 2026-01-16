"""
Test suite for Form 5471 - Information Return for Foreign Corporations.

Tests cover:
- Filing category determination
- CFC (Controlled Foreign Corporation) identification
- Ownership percentage calculations
- Subpart F income calculation
- GILTI (Global Intangible Low-Taxed Income) calculation
- Income statement and balance sheet calculations
- Convenience function
"""

import pytest
from models.form_5471 import (
    Form5471,
    FilingCategory,
    ForeignCorporationType,
    ForeignCorporationInfo,
    ShareholderInfo,
    ScheduleC_IncomeStatement,
    ScheduleE_ForeignTaxes,
    ScheduleF_BalanceSheet,
    ScheduleH_EarningsAndProfits,
    ScheduleI1_GILTI,
    SubpartFIncome,
    calculate_cfc_income_inclusion,
)


class TestForm5471Ownership:
    """Tests for ownership and CFC determination."""

    def test_10_percent_shareholder_determination(self):
        """10%+ ownership qualifies as U.S. shareholder."""
        shareholder = ShareholderInfo(
            direct_ownership_percent=15.0,
        )
        form = Form5471(shareholder_info=shareholder)

        assert form.is_10_percent_shareholder() is True

    def test_under_10_percent_not_shareholder(self):
        """Under 10% ownership doesn't qualify."""
        shareholder = ShareholderInfo(
            direct_ownership_percent=8.0,
        )
        form = Form5471(shareholder_info=shareholder)

        assert form.is_10_percent_shareholder() is False

    def test_exactly_10_percent_qualifies(self):
        """Exactly 10% qualifies as U.S. shareholder."""
        shareholder = ShareholderInfo(
            direct_ownership_percent=10.0,
        )
        form = Form5471(shareholder_info=shareholder)

        assert form.is_10_percent_shareholder() is True

    def test_combined_ownership_calculation(self):
        """Direct + indirect + constructive ownership combined."""
        shareholder = ShareholderInfo(
            direct_ownership_percent=5.0,
            indirect_ownership_percent=3.0,
            constructive_ownership_percent=4.0,
        )
        form = Form5471(shareholder_info=shareholder)

        assert shareholder.total_ownership_percent() == 12.0
        assert form.is_10_percent_shareholder() is True

    def test_cfc_determination(self):
        """CFC status determined from foreign corporation info."""
        corp = ForeignCorporationInfo(
            name="Foreign Corp Ltd",
            is_cfc=True,
        )
        form = Form5471(foreign_corporation=corp)

        assert form.is_cfc() is True


class TestForm5471SubpartF:
    """Tests for Subpart F income calculations."""

    def test_subpart_f_not_applicable_non_cfc(self):
        """Subpart F not applicable if not a CFC."""
        corp = ForeignCorporationInfo(is_cfc=False)
        shareholder = ShareholderInfo(direct_ownership_percent=25.0)

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
        )

        result = form.calculate_subpart_f_inclusion()
        assert result['subpart_f_applicable'] is False
        assert result['inclusion_in_income'] == 0.0

    def test_subpart_f_not_applicable_under_10_percent(self):
        """Subpart F not applicable if under 10% ownership."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=5.0)

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
        )

        result = form.calculate_subpart_f_inclusion()
        assert result['subpart_f_applicable'] is False

    def test_basic_subpart_f_calculation(self):
        """Basic Subpart F income calculation."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=25.0)
        subpart_f = SubpartFIncome(
            foreign_personal_holding_company_income=100000.0,
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            subpart_f_income=subpart_f,
        )

        result = form.calculate_subpart_f_inclusion()

        assert result['subpart_f_applicable'] is True
        assert result['gross_subpart_f_income'] == 100000.0
        # Pro-rata share: 25% of $100,000 = $25,000
        assert result['pro_rata_share'] == 25000.0
        assert result['inclusion_in_income'] == 25000.0

    def test_subpart_f_with_exclusions(self):
        """Subpart F with high-tax exception exclusion."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=50.0)
        subpart_f = SubpartFIncome(
            foreign_personal_holding_company_income=100000.0,
            high_tax_exception_amount=30000.0,  # Excluded
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            subpart_f_income=subpart_f,
        )

        result = form.calculate_subpart_f_inclusion()

        # Net: $100,000 - $30,000 = $70,000
        assert result['net_subpart_f_income'] == 70000.0
        # 50% of $70,000 = $35,000
        assert result['pro_rata_share'] == 35000.0

    def test_multiple_subpart_f_categories(self):
        """Multiple types of Subpart F income."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=20.0)
        subpart_f = SubpartFIncome(
            foreign_personal_holding_company_income=50000.0,
            foreign_base_company_sales_income=30000.0,
            insurance_income=20000.0,
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            subpart_f_income=subpart_f,
        )

        result = form.calculate_subpart_f_inclusion()

        assert result['gross_subpart_f_income'] == 100000.0
        # 20% of $100,000 = $20,000
        assert result['pro_rata_share'] == 20000.0


class TestForm5471GILTI:
    """Tests for GILTI (Global Intangible Low-Taxed Income) calculations."""

    def test_gilti_not_applicable_non_cfc(self):
        """GILTI not applicable if not a CFC."""
        corp = ForeignCorporationInfo(is_cfc=False)
        shareholder = ShareholderInfo(direct_ownership_percent=25.0)

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
        )

        result = form.calculate_gilti_inclusion()
        assert result['gilti_applicable'] is False

    def test_basic_gilti_calculation(self):
        """Basic GILTI calculation with QBAI offset."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=100.0)
        schedule_i1 = ScheduleI1_GILTI(
            gross_tested_income=500000.0,
            qbai_at_year_end=1000000.0,  # 10% = $100,000 deemed tangible return
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            schedule_i1=schedule_i1,
        )

        result = form.calculate_gilti_inclusion()

        assert result['gilti_applicable'] is True
        assert result['gross_tested_income'] == 500000.0
        assert result['deemed_tangible_return'] == 100000.0
        # GILTI: $500,000 - $100,000 = $400,000
        # 100% ownership = $400,000
        assert result['gilti_before_deduction'] == 400000.0

    def test_gilti_with_high_qbai(self):
        """When QBAI offset exceeds tested income, GILTI is zero."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=100.0)
        schedule_i1 = ScheduleI1_GILTI(
            gross_tested_income=50000.0,
            qbai_at_year_end=1000000.0,  # 10% = $100,000 (exceeds income)
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            schedule_i1=schedule_i1,
        )

        result = form.calculate_gilti_inclusion()

        # GILTI: max(0, $50,000 - $100,000) = $0
        assert result['gilti_before_deduction'] == 0.0

    def test_gilti_prorata_share(self):
        """GILTI pro-rata share based on ownership."""
        corp = ForeignCorporationInfo(is_cfc=True)
        shareholder = ShareholderInfo(direct_ownership_percent=25.0)
        schedule_i1 = ScheduleI1_GILTI(
            gross_tested_income=200000.0,
            qbai_at_year_end=0.0,  # No tangible offset
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            schedule_i1=schedule_i1,
        )

        result = form.calculate_gilti_inclusion()

        # GILTI: $200,000, 25% share = $50,000
        assert result['gilti_before_deduction'] == 50000.0


class TestForm5471Schedules:
    """Tests for Form 5471 schedules."""

    def test_schedule_c_income_calculation(self):
        """Schedule C income statement calculation."""
        schedule_c = ScheduleC_IncomeStatement(
            gross_receipts_or_sales=1000000.0,
            cost_of_goods_sold=600000.0,
            interest=50000.0,
            compensation_of_officers=100000.0,
            salaries_and_wages=150000.0,
        )

        assert schedule_c.gross_income() == 450000.0  # $1M - $600k + $50k
        assert schedule_c.total_deductions() == 250000.0
        assert schedule_c.net_income() == 200000.0

    def test_schedule_f_balance_sheet(self):
        """Schedule F balance sheet calculation."""
        schedule_f = ScheduleF_BalanceSheet(
            cash=100000.0,
            accounts_receivable=200000.0,
            buildings_and_equipment=500000.0,
            less_accumulated_depreciation=100000.0,
            accounts_payable=150000.0,
            long_term_debt=200000.0,
            capital_stock=50000.0,
            retained_earnings=300000.0,
        )

        assert schedule_f.total_assets() == 700000.0
        assert schedule_f.total_liabilities() == 350000.0
        assert schedule_f.total_equity() == 350000.0

    def test_schedule_h_earnings_and_profits(self):
        """Schedule H current E&P calculation."""
        schedule_h = ScheduleH_EarningsAndProfits(
            net_income_per_books=500000.0,
            federal_income_tax_expense=100000.0,
            depreciation_book_tax_diff=20000.0,
            income_on_books_not_taxable=10000.0,
        )

        # E&P: $500k + $100k + $20k - $10k = $610k
        assert schedule_h.current_ep() == 610000.0

    def test_schedule_e_foreign_taxes(self):
        """Schedule E foreign taxes calculation."""
        schedule_e = ScheduleE_ForeignTaxes(
            foreign_income_taxes_paid=50000.0,
            foreign_income_taxes_accrued=10000.0,
        )

        assert schedule_e.total_foreign_taxes() == 60000.0


class TestForm5471CompleteCalculation:
    """Tests for complete Form 5471 calculation."""

    def test_complete_form_5471(self):
        """Complete Form 5471 with all components."""
        corp = ForeignCorporationInfo(
            name="Overseas Holdings Ltd",
            country_of_incorporation="UK",
            is_cfc=True,
            functional_currency="GBP",
        )
        shareholder = ShareholderInfo(
            name="John Taxpayer",
            direct_ownership_percent=30.0,
        )
        schedule_c = ScheduleC_IncomeStatement(
            gross_receipts_or_sales=2000000.0,
            cost_of_goods_sold=1200000.0,
            salaries_and_wages=300000.0,
        )
        schedule_e = ScheduleE_ForeignTaxes(
            foreign_income_taxes_paid=80000.0,
        )
        subpart_f = SubpartFIncome(
            foreign_personal_holding_company_income=150000.0,
        )
        schedule_i1 = ScheduleI1_GILTI(
            gross_tested_income=350000.0,
            qbai_at_year_end=500000.0,
        )

        form = Form5471(
            filer_name="John Taxpayer",
            foreign_corporation=corp,
            shareholder_info=shareholder,
            schedule_c=schedule_c,
            schedule_e=schedule_e,
            subpart_f_income=subpart_f,
            schedule_i1=schedule_i1,
            filing_categories=[FilingCategory.CATEGORY_4, FilingCategory.CATEGORY_5],
        )

        result = form.calculate_form_5471()

        assert result['is_cfc'] is True
        assert result['total_ownership'] == 30.0
        assert result['foreign_taxes_paid'] == 80000.0
        assert result['total_income_inclusion'] > 0


class TestForm5471ConvenienceFunction:
    """Tests for convenience function."""

    def test_convenience_function_basic(self):
        """Convenience function calculates CFC inclusion."""
        result = calculate_cfc_income_inclusion(
            ownership_percent=25.0,
            subpart_f_income=100000.0,
            tested_income=200000.0,
            qbai=500000.0,
        )

        assert result['is_10_percent_shareholder'] is True
        # Subpart F: 25% of $100k = $25k
        assert result['subpart_f_pro_rata'] == 25000.0
        # GILTI: $200k - $50k (10% of QBAI) = $150k; 25% = $37.5k
        assert result['gilti_pro_rata'] == 37500.0
        assert result['total_inclusion'] == 62500.0

    def test_convenience_function_under_10_percent(self):
        """Under 10% ownership gets no inclusion."""
        result = calculate_cfc_income_inclusion(
            ownership_percent=5.0,
            subpart_f_income=100000.0,
            tested_income=200000.0,
        )

        assert result['is_10_percent_shareholder'] is False
        assert result['total_inclusion'] == 0.0


class TestForm5471Summary:
    """Tests for summary methods."""

    def test_get_form_5471_summary(self):
        """Summary method returns correct fields."""
        corp = ForeignCorporationInfo(
            name="Test Corp",
            is_cfc=True,
        )
        shareholder = ShareholderInfo(direct_ownership_percent=50.0)
        subpart_f = SubpartFIncome(
            foreign_personal_holding_company_income=100000.0,
        )

        form = Form5471(
            foreign_corporation=corp,
            shareholder_info=shareholder,
            subpart_f_income=subpart_f,
        )

        summary = form.get_form_5471_summary()

        assert 'foreign_corporation' in summary
        assert 'is_cfc' in summary
        assert 'ownership_percent' in summary
        assert 'subpart_f_inclusion' in summary
        assert 'total_income_inclusion' in summary
