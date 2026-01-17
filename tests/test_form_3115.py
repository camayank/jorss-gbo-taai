"""
Test Suite for Form 3115 - Application for Change in Accounting Method

Tests cover:
- Overall accounting method changes (cash to accrual)
- Depreciation method changes
- Inventory method changes
- Section 481(a) adjustment calculation
- Spread period determination (1 vs 4 years)
- Automatic vs non-automatic changes
- Designated Change Numbers (DCN)
- Convenience functions
"""

import pytest
from datetime import date

from models.form_3115 import (
    Form3115,
    Form3115PartI,
    Form3115PartII,
    Form3115PartIV,
    Form3115ScheduleA,
    Form3115ScheduleD,
    Form3115ScheduleE,
    Section481aAdjustment,
    DesignatedChangeNumber,
    ChangeType,
    AccountingMethodCategory,
    OverallMethod,
    InventoryMethod,
    DepreciationMethod,
    FilingMethod,
    EntityType,
    calculate_cash_to_accrual_adjustment,
    calculate_depreciation_adjustment,
    calculate_inventory_adjustment
)


class TestDesignatedChangeNumber:
    """Test DCN factory methods."""

    def test_cash_to_accrual_dcn(self):
        """Test DCN for cash to accrual change."""
        dcn = DesignatedChangeNumber.cash_to_accrual()

        assert dcn.dcn == 7
        assert dcn.category == AccountingMethodCategory.OVERALL_METHOD
        assert "cash" in dcn.description.lower()
        assert "accrual" in dcn.description.lower()

    def test_accrual_to_cash_dcn(self):
        """Test DCN for accrual to cash change."""
        dcn = DesignatedChangeNumber.accrual_to_cash()

        assert dcn.dcn == 8
        assert dcn.category == AccountingMethodCategory.OVERALL_METHOD

    def test_depreciation_change_dcn(self):
        """Test DCN for depreciation change."""
        dcn = DesignatedChangeNumber.depreciation_change()

        assert dcn.dcn == 184
        assert dcn.category == AccountingMethodCategory.DEPRECIATION

    def test_inventory_capitalization_dcn(self):
        """Test DCN for UNICAP change."""
        dcn = DesignatedChangeNumber.inventory_capitalization()

        assert dcn.dcn == 12
        assert dcn.category == AccountingMethodCategory.CAPITALIZATION

    def test_bad_debt_dcn(self):
        """Test DCN for bad debt method change."""
        dcn = DesignatedChangeNumber.bad_debt_reserve_to_direct()

        assert dcn.dcn == 166
        assert dcn.category == AccountingMethodCategory.BAD_DEBTS


class TestSection481aAdjustment:
    """Test Section 481(a) adjustment calculations."""

    def test_positive_adjustment_4_year_spread(self):
        """Positive adjustment over $50k spreads over 4 years."""
        adj = Section481aAdjustment(
            gross_adjustment=100000,
            year_of_change=2025
        )

        assert adj.is_positive is True
        assert adj.is_negative is False
        assert adj.spread_period == 4
        assert adj.annual_adjustment == 25000

    def test_negative_adjustment_1_year(self):
        """Negative adjustment taken entirely in year of change."""
        adj = Section481aAdjustment(
            gross_adjustment=-50000,
            year_of_change=2025
        )

        assert adj.is_positive is False
        assert adj.is_negative is True
        assert adj.spread_period == 1
        assert adj.annual_adjustment == -50000

    def test_small_positive_adjustment_1_year(self):
        """Small positive adjustment (<$50k) taken in 1 year."""
        adj = Section481aAdjustment(
            gross_adjustment=30000,
            year_of_change=2025
        )

        assert adj.spread_period == 1
        assert adj.annual_adjustment == 30000

    def test_elect_one_year_spread(self):
        """Elect to take large positive adjustment in 1 year."""
        adj = Section481aAdjustment(
            gross_adjustment=200000,
            year_of_change=2025,
            elect_one_year=True
        )

        assert adj.spread_period == 1
        assert adj.annual_adjustment == 200000

    def test_get_adjustment_for_year(self):
        """Test getting adjustment for specific years."""
        adj = Section481aAdjustment(
            gross_adjustment=100000,
            year_of_change=2025
        )

        # 4-year spread: 25000 per year
        assert adj.get_adjustment_for_year(2024) == 0  # Before change
        assert adj.get_adjustment_for_year(2025) == 25000  # Year 1
        assert adj.get_adjustment_for_year(2026) == 25000  # Year 2
        assert adj.get_adjustment_for_year(2027) == 25000  # Year 3
        assert adj.get_adjustment_for_year(2028) == 25000  # Year 4
        assert adj.get_adjustment_for_year(2029) == 0  # After spread

    def test_get_spread_schedule(self):
        """Test full spread schedule."""
        adj = Section481aAdjustment(
            gross_adjustment=80000,
            year_of_change=2025
        )

        schedule = adj.get_spread_schedule()

        assert len(schedule) == 4
        assert schedule[2025] == 20000
        assert schedule[2026] == 20000
        assert schedule[2027] == 20000
        assert schedule[2028] == 20000


class TestScheduleACashToAccrual:
    """Test Schedule A - Overall Method Change."""

    def test_basic_cash_to_accrual(self):
        """Test basic cash to accrual conversion."""
        schedule = Form3115ScheduleA(
            present_method=OverallMethod.CASH,
            proposed_method=OverallMethod.ACCRUAL,
            accounts_receivable=100000,
            accrued_expenses=40000
        )

        # Income items: +100000 (A/R) - 0 (deferred) = 100000
        # Expense items: +0 (prepaid) - 40000 (accrued) = -40000
        # Net: 100000 - (-40000) = 140000

        assert schedule.income_items_adjustment == 100000
        assert schedule.expense_items_adjustment == -40000
        assert schedule.net_481a_adjustment == 140000

    def test_cash_to_accrual_with_deferred_revenue(self):
        """Cash to accrual with deferred revenue reduces adjustment."""
        schedule = Form3115ScheduleA(
            present_method=OverallMethod.CASH,
            proposed_method=OverallMethod.ACCRUAL,
            accounts_receivable=100000,
            deferred_revenue=30000,
            accrued_expenses=20000
        )

        # Income: 100000 - 30000 = 70000
        # Expense: 0 - 20000 = -20000
        # Net: 70000 - (-20000) = 90000

        assert schedule.income_items_adjustment == 70000
        assert schedule.expense_items_adjustment == -20000
        assert schedule.net_481a_adjustment == 90000

    def test_cash_to_accrual_with_prepaid_expenses(self):
        """Prepaid expenses reduce the 481(a) adjustment."""
        schedule = Form3115ScheduleA(
            present_method=OverallMethod.CASH,
            proposed_method=OverallMethod.ACCRUAL,
            accounts_receivable=50000,
            prepaid_expenses=10000,
            accrued_expenses=25000
        )

        # Income: 50000 - 0 = 50000
        # Expense: 10000 - 25000 = -15000
        # Net: 50000 - (-15000) = 65000

        assert schedule.income_items_adjustment == 50000
        assert schedule.expense_items_adjustment == -15000
        assert schedule.net_481a_adjustment == 65000

    def test_accrual_to_cash_reverses_adjustment(self):
        """Accrual to cash reverses the adjustment direction."""
        schedule = Form3115ScheduleA(
            present_method=OverallMethod.ACCRUAL,
            proposed_method=OverallMethod.CASH,
            accounts_receivable=80000,
            accrued_expenses=30000
        )

        # Reverses cash-to-accrual logic
        assert schedule.income_items_adjustment == -80000
        assert schedule.expense_items_adjustment == 30000
        assert schedule.net_481a_adjustment == -110000

    def test_inventory_adjustment(self):
        """Test with inventory adjustment included."""
        schedule = Form3115ScheduleA(
            present_method=OverallMethod.CASH,
            proposed_method=OverallMethod.ACCRUAL,
            accounts_receivable=50000,
            inventory_adjustment=15000
        )

        # 50000 + 15000 = 65000
        assert schedule.net_481a_adjustment == 65000


class TestScheduleDDepreciation:
    """Test Schedule D - Depreciation Changes."""

    def test_over_depreciation_positive_adjustment(self):
        """Over-depreciation results in positive 481(a) adjustment."""
        schedule = Form3115ScheduleD(
            asset_description="Office furniture",
            original_basis=100000,
            depreciation_claimed=60000,  # Claimed too much
            depreciation_allowable=40000  # Should have claimed
        )

        # Claimed 60000, should have claimed 40000
        # Positive adjustment of 20000 (income)
        assert schedule.section_481a_adjustment == 20000
        assert schedule.adjusted_basis_present == 40000
        assert schedule.adjusted_basis_proposed == 60000

    def test_under_depreciation_negative_adjustment(self):
        """Under-depreciation results in negative 481(a) adjustment."""
        schedule = Form3115ScheduleD(
            asset_description="Equipment",
            original_basis=100000,
            depreciation_claimed=30000,  # Claimed too little
            depreciation_allowable=50000  # Should have claimed
        )

        # Claimed 30000, should have claimed 50000
        # Negative adjustment of -20000 (deduction)
        assert schedule.section_481a_adjustment == -20000
        assert schedule.adjusted_basis_present == 70000
        assert schedule.adjusted_basis_proposed == 50000

    def test_no_adjustment_needed(self):
        """No adjustment when depreciation is correct."""
        schedule = Form3115ScheduleD(
            original_basis=100000,
            depreciation_claimed=40000,
            depreciation_allowable=40000
        )

        assert schedule.section_481a_adjustment == 0


class TestScheduleEInventory:
    """Test Schedule E - Inventory Method Changes."""

    def test_fifo_to_average_cost(self):
        """Test FIFO to average cost change."""
        schedule = Form3115ScheduleE(
            present_method=InventoryMethod.FIFO,
            proposed_method=InventoryMethod.AVERAGE_COST,
            ending_inventory_present=100000,
            ending_inventory_proposed=95000
        )

        # Lower ending inventory = higher COGS = lower income
        assert schedule.inventory_adjustment == -5000
        assert schedule.section_481a_adjustment == -5000

    def test_with_unicap_adjustment(self):
        """Test inventory change with Section 263A adjustment."""
        schedule = Form3115ScheduleE(
            present_method=InventoryMethod.FIFO,
            proposed_method=InventoryMethod.LIFO,
            ending_inventory_present=200000,
            ending_inventory_proposed=180000,
            unicap_adjustment=10000  # Additional capitalized costs
        )

        # Inventory: -20000, UNICAP: +10000
        assert schedule.inventory_adjustment == -20000
        assert schedule.section_481a_adjustment == -10000

    def test_inventory_increase_positive_adjustment(self):
        """Higher ending inventory = positive adjustment."""
        schedule = Form3115ScheduleE(
            ending_inventory_present=50000,
            ending_inventory_proposed=60000
        )

        assert schedule.section_481a_adjustment == 10000


class TestForm3115Complete:
    """Test complete Form 3115."""

    def test_automatic_change_basic(self):
        """Test basic automatic change."""
        form = Form3115(
            tax_year=2025,
            change_type=ChangeType.AUTOMATIC,
            dcn=DesignatedChangeNumber.cash_to_accrual(),
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=80000,
                accrued_expenses=20000
            )
        )

        assert form.is_automatic is True
        assert form.category == AccountingMethodCategory.OVERALL_METHOD
        assert form.section_481a_adjustment == 100000
        assert form.is_positive_adjustment is True
        assert form.spread_period == 4
        assert form.annual_481a_amount == 25000
        assert form.user_fee_required == 0

    def test_non_automatic_change(self):
        """Test non-automatic change requires user fee."""
        form = Form3115(
            tax_year=2025,
            change_type=ChangeType.NON_AUTOMATIC
        )

        assert form.is_automatic is False
        assert form.user_fee_required == 12500

    def test_negative_adjustment_1_year_spread(self):
        """Negative adjustment spreads over 1 year."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.ACCRUAL,
                proposed_method=OverallMethod.CASH,
                accounts_receivable=50000,
                accrued_expenses=10000
            )
        )

        # Accrual to cash: -50000 income + 10000 expense = -60000
        assert form.section_481a_adjustment == -60000
        assert form.is_negative_adjustment is True
        assert form.spread_period == 1
        assert form.annual_481a_amount == -60000

    def test_small_positive_1_year_spread(self):
        """Small positive adjustment (<$50k) in 1 year."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=30000
            )
        )

        assert form.section_481a_adjustment == 30000
        assert form.spread_period == 1

    def test_elect_one_year_spread(self):
        """Elect to take large adjustment in 1 year."""
        form = Form3115(
            tax_year=2025,
            elect_one_year_spread=True,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=200000
            )
        )

        assert form.section_481a_adjustment == 200000
        assert form.spread_period == 1
        assert form.annual_481a_amount == 200000

    def test_get_481a_schedule(self):
        """Test 481(a) spread schedule."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=80000
            )
        )

        schedule = form.get_481a_schedule()

        assert len(schedule) == 4
        assert schedule[2025] == 20000
        assert schedule[2026] == 20000
        assert schedule[2027] == 20000
        assert schedule[2028] == 20000

    def test_multiple_schedules(self):
        """Test form with multiple schedules."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=50000
            ),
            schedule_d=Form3115ScheduleD(
                depreciation_claimed=30000,
                depreciation_allowable=40000
            )
        )

        # A: +50000, D: -10000
        assert form.section_481a_adjustment == 40000

    def test_get_method_descriptions(self):
        """Test method description getters."""
        form = Form3115(
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL
            )
        )

        assert "cash" in form.get_present_method_description().lower()
        assert "accrual" in form.get_proposed_method_description().lower()


class TestForm3115PartI:
    """Test Part I - Applicant Information."""

    def test_basic_info(self):
        """Test basic applicant information."""
        part_i = Form3115PartI(
            applicant_name="ABC Corporation",
            applicant_ein="12-3456789",
            entity_type=EntityType.CORPORATION,
            principal_business="Manufacturing",
            naics_code="332312",
            tax_year_of_change_begin=date(2025, 1, 1),
            tax_year_of_change_end=date(2025, 12, 31)
        )

        assert part_i.tax_year == 2025
        assert part_i.entity_type == EntityType.CORPORATION

    def test_individual_filer(self):
        """Test individual filer."""
        part_i = Form3115PartI(
            applicant_name="John Smith",
            applicant_ssn="123-45-6789",
            entity_type=EntityType.INDIVIDUAL,
            tax_year_of_change_begin=date(2025, 1, 1),
            tax_year_of_change_end=date(2025, 12, 31)
        )

        assert part_i.entity_type == EntityType.INDIVIDUAL


class TestForm3115PartII:
    """Test Part II - Change Details."""

    def test_automatic_change_details(self):
        """Test automatic change details."""
        part_ii = Form3115PartII(
            change_type=ChangeType.AUTOMATIC,
            dcn_number=7,
            category=AccountingMethodCategory.OVERALL_METHOD,
            present_method_description="Cash receipts and disbursements",
            proposed_method_description="Accrual method",
            is_trade_or_business=True
        )

        assert part_ii.change_type == ChangeType.AUTOMATIC
        assert part_ii.dcn_number == 7

    def test_audit_flags(self):
        """Test audit-related flags."""
        part_ii = Form3115PartII(
            under_examination=True,
            in_appeals=False,
            in_litigation=False
        )

        assert part_ii.under_examination is True

    def test_prior_change_flag(self):
        """Test change within 5 years flag."""
        part_ii = Form3115PartII(
            change_made_within_5_years=True
        )

        assert part_ii.change_made_within_5_years is True


class TestForm3115PartIV:
    """Test Part IV - Section 481(a) Calculation."""

    def test_explicit_481a_calculation(self):
        """Test explicit 481(a) calculation."""
        part_iv = Form3115PartIV(
            income_under_present_method=100000,
            deductions_under_present_method=60000,
            income_under_proposed_method=120000,
            deductions_under_proposed_method=70000
        )

        # Present: 100000 - 60000 = 40000
        # Proposed: 120000 - 70000 = 50000
        # 481(a): 50000 - 40000 = 10000

        assert part_iv.net_present_method == 40000
        assert part_iv.net_proposed_method == 50000
        assert part_iv.section_481a_adjustment == 10000


class TestConvenienceFunctions:
    """Test convenience calculation functions."""

    def test_calculate_cash_to_accrual(self):
        """Test cash to accrual convenience function."""
        result = calculate_cash_to_accrual_adjustment(
            accounts_receivable=100000,
            accrued_expenses=40000,
            prepaid_expenses=5000
        )

        # Income: +100000 (A/R)
        # Expense: +5000 (prepaid) - 40000 (accrued) = -35000
        # Net 481a: 100000 - (-35000) = 135000

        assert result["change_type"] == "automatic"
        assert result["category"] == "overall_method"
        assert result["section_481a_adjustment"] == 135000
        assert result["spread_period"] == 4
        assert result["annual_481a_amount"] == 33750
        assert result["dcn"] == 7

    def test_calculate_depreciation_adjustment(self):
        """Test depreciation adjustment convenience function."""
        result = calculate_depreciation_adjustment(
            original_basis=100000,
            depreciation_claimed=50000,
            depreciation_allowable=40000,
            asset_description="Machinery"
        )

        assert result["section_481a_adjustment"] == 10000
        assert result["category"] == "depreciation"
        assert result["dcn"] == 184

    def test_calculate_inventory_adjustment(self):
        """Test inventory adjustment convenience function."""
        result = calculate_inventory_adjustment(
            ending_inventory_present=200000,
            ending_inventory_proposed=180000,
            present_method=InventoryMethod.FIFO,
            proposed_method=InventoryMethod.AVERAGE_COST
        )

        assert result["section_481a_adjustment"] == -20000
        assert result["spread_period"] == 1  # Negative = 1 year


class TestToDictionary:
    """Test form serialization."""

    def test_to_dict(self):
        """Test to_dict method."""
        form = Form3115(
            tax_year=2025,
            change_type=ChangeType.AUTOMATIC,
            dcn=DesignatedChangeNumber.cash_to_accrual(),
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=60000
            )
        )

        result = form.to_dict()

        assert result["tax_year"] == 2025
        assert result["change_type"] == "automatic"
        assert result["is_automatic"] is True
        assert result["section_481a_adjustment"] == 60000
        assert result["dcn"] == 7
        assert "spread_schedule" in result
        assert len(result["spread_schedule"]) == 4

    def test_to_form_1040(self):
        """Test to_form_1040 method."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=80000
            )
        )

        result = form.to_form_1040()

        assert result["section_481a_adjustment"] == 20000  # 80000/4
        assert result["other_income_481a"] == 20000
        assert result["other_deduction_481a"] == 0

    def test_to_form_1040_negative(self):
        """Test to_form_1040 with negative adjustment."""
        form = Form3115(
            tax_year=2025,
            schedule_d=Form3115ScheduleD(
                depreciation_claimed=30000,
                depreciation_allowable=50000
            )
        )

        result = form.to_form_1040()

        assert result["section_481a_adjustment"] == -20000
        assert result["other_income_481a"] == 0
        assert result["other_deduction_481a"] == 20000


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_adjustment(self):
        """Test with zero 481(a) adjustment."""
        form = Form3115(
            tax_year=2025,
            schedule_d=Form3115ScheduleD(
                depreciation_claimed=40000,
                depreciation_allowable=40000
            )
        )

        assert form.section_481a_adjustment == 0
        assert form.spread_period == 1  # 0 < 50000

    def test_exactly_50000_threshold(self):
        """Test at exactly $50,000 threshold."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=50000
            )
        )

        assert form.section_481a_adjustment == 50000
        assert form.spread_period == 1  # <= 50000

    def test_just_over_50000_threshold(self):
        """Test just over $50,000 threshold."""
        form = Form3115(
            tax_year=2025,
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=50001
            )
        )

        assert form.section_481a_adjustment == 50001
        assert form.spread_period == 4  # > 50000

    def test_no_schedules(self):
        """Test form with no schedules."""
        form = Form3115(
            tax_year=2025,
            change_type=ChangeType.NON_AUTOMATIC
        )

        assert form.section_481a_adjustment == 0
        assert form.category == AccountingMethodCategory.OTHER

    def test_all_entity_types(self):
        """Test all entity types."""
        for entity_type in EntityType:
            part_i = Form3115PartI(
                applicant_name="Test Entity",
                entity_type=entity_type,
                tax_year_of_change_begin=date(2025, 1, 1),
                tax_year_of_change_end=date(2025, 12, 31)
            )

            assert part_i.entity_type == entity_type

    def test_all_filing_methods(self):
        """Test all filing methods."""
        for method in FilingMethod:
            form = Form3115(
                tax_year=2025,
                filing_method=method
            )

            assert form.filing_method == method


class TestAuditProtection:
    """Test audit protection rules."""

    def test_automatic_change_has_audit_protection(self):
        """Automatic changes get audit protection."""
        form = Form3115(
            change_type=ChangeType.AUTOMATIC,
            audit_protection_applies=True
        )

        assert form.audit_protection_applies is True
        assert form.requires_national_office_copy is True

    def test_non_automatic_no_automatic_protection(self):
        """Non-automatic doesn't have automatic audit protection."""
        form = Form3115(
            change_type=ChangeType.NON_AUTOMATIC
        )

        assert form.requires_national_office_copy is False


class TestInventoryMethods:
    """Test all inventory methods."""

    def test_fifo_method(self):
        """Test FIFO inventory method."""
        schedule = Form3115ScheduleE(
            present_method=InventoryMethod.FIFO,
            proposed_method=InventoryMethod.LIFO
        )

        assert schedule.present_method == InventoryMethod.FIFO

    def test_lifo_method(self):
        """Test LIFO inventory method."""
        schedule = Form3115ScheduleE(
            present_method=InventoryMethod.LIFO,
            proposed_method=InventoryMethod.AVERAGE_COST
        )

        assert schedule.present_method == InventoryMethod.LIFO

    def test_all_inventory_methods(self):
        """Test all inventory methods are valid."""
        for method in InventoryMethod:
            schedule = Form3115ScheduleE(
                present_method=method,
                proposed_method=InventoryMethod.FIFO
            )

            assert schedule.present_method == method


class TestDepreciationMethods:
    """Test all depreciation methods."""

    def test_macrs_gds(self):
        """Test MACRS GDS method."""
        schedule = Form3115ScheduleD(
            present_depreciation_method=DepreciationMethod.MACRS_GDS,
            proposed_depreciation_method=DepreciationMethod.STRAIGHT_LINE
        )

        assert schedule.present_depreciation_method == DepreciationMethod.MACRS_GDS

    def test_all_depreciation_methods(self):
        """Test all depreciation methods are valid."""
        for method in DepreciationMethod:
            schedule = Form3115ScheduleD(
                present_depreciation_method=method,
                proposed_depreciation_method=DepreciationMethod.MACRS_GDS
            )

            assert schedule.present_depreciation_method == method
