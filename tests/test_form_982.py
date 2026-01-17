"""
Test Suite for Form 982 - Reduction of Tax Attributes Due to Discharge of Indebtedness

Tests cover:
- Bankruptcy exclusion (full exclusion)
- Insolvency exclusion (limited to insolvency amount)
- Qualified farm indebtedness
- Qualified real property business indebtedness (QRPBI)
- Qualified principal residence indebtedness (QPRI)
- Tax attribute reduction order
- Section 1017 basis reduction
- Convenience functions
"""

import pytest
from datetime import date

from models.form_982 import (
    Form982,
    Form982PartI,
    Form982PartII,
    Form982PartIII,
    InsolvencyCalculation,
    DischargedDebt,
    TaxAttributeReduction,
    BasisReduction,
    ExclusionType,
    DebtType,
    TaxAttributeType,
    calculate_insolvency,
    calculate_bankruptcy_exclusion,
    calculate_qpri_exclusion
)


class TestInsolvencyCalculation:
    """Test insolvency determination."""

    def test_insolvent_taxpayer(self):
        """Test taxpayer who is insolvent."""
        insolvency = InsolvencyCalculation(
            cash_and_bank_accounts=5000,
            real_estate_fmv=100000,
            vehicles_fmv=15000,
            mortgage_debt=120000,
            credit_card_debt=30000,
            auto_loans=10000
        )

        # Assets: 120000, Liabilities: 160000
        assert insolvency.total_assets == 120000
        assert insolvency.total_liabilities == 160000
        assert insolvency.is_insolvent is True
        assert insolvency.insolvency_amount == 40000
        assert insolvency.net_worth == -40000

    def test_solvent_taxpayer(self):
        """Test taxpayer who is solvent."""
        insolvency = InsolvencyCalculation(
            cash_and_bank_accounts=50000,
            real_estate_fmv=300000,
            retirement_accounts=100000,
            mortgage_debt=200000,
            credit_card_debt=20000
        )

        # Assets: 450000, Liabilities: 220000
        assert insolvency.total_assets == 450000
        assert insolvency.total_liabilities == 220000
        assert insolvency.is_insolvent is False
        assert insolvency.insolvency_amount == 0
        assert insolvency.net_worth == 230000

    def test_exactly_solvent(self):
        """Test taxpayer at exactly zero net worth."""
        insolvency = InsolvencyCalculation(
            cash_and_bank_accounts=100000,
            other_liabilities=100000
        )

        assert insolvency.total_assets == 100000
        assert insolvency.total_liabilities == 100000
        assert insolvency.is_insolvent is False
        assert insolvency.insolvency_amount == 0


class TestBankruptcyExclusion:
    """Test bankruptcy (Title 11) exclusion."""

    def test_full_bankruptcy_exclusion(self):
        """Bankruptcy provides full COD exclusion."""
        form = Form982(
            total_cod_income=100000,
            exclusion_type=ExclusionType.BANKRUPTCY
        )

        assert form.is_bankruptcy is True
        assert form.maximum_exclusion == 100000
        assert form.excluded_amount == 100000
        assert form.taxable_cod_income == 0

    def test_bankruptcy_with_attribute_reduction(self):
        """Bankruptcy exclusion requires attribute reduction."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.BANKRUPTCY,
            nol_carryover=30000,
            capital_loss_carryover=25000
        )

        assert form.attribute_reduction_required == 50000

        reductions = form.calculate_attribute_reductions()
        assert len(reductions) == 2

        # First reduce NOL
        nol_reduction = next(r for r in reductions if r.attribute_type == TaxAttributeType.NOL)
        assert nol_reduction.reduction_amount == 30000

        # Then reduce capital loss
        cap_reduction = next(r for r in reductions if r.attribute_type == TaxAttributeType.CAPITAL_LOSS_CARRYOVER)
        assert cap_reduction.reduction_amount == 20000  # Remaining 20000


class TestInsolvencyExclusion:
    """Test insolvency exclusion."""

    def test_insolvency_limited_exclusion(self):
        """Insolvency exclusion limited to insolvency amount."""
        insolvency = InsolvencyCalculation(
            other_assets_fmv=80000,
            other_liabilities=100000  # 20000 insolvent
        )

        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=insolvency
        )

        assert form.is_insolvency is True
        assert insolvency.insolvency_amount == 20000
        assert form.maximum_exclusion == 20000
        assert form.excluded_amount == 20000
        assert form.taxable_cod_income == 30000

    def test_cod_less_than_insolvency(self):
        """COD less than insolvency amount - full exclusion."""
        insolvency = InsolvencyCalculation(
            other_assets_fmv=50000,
            other_liabilities=100000  # 50000 insolvent
        )

        form = Form982(
            total_cod_income=30000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=insolvency
        )

        assert insolvency.insolvency_amount == 50000
        assert form.excluded_amount == 30000  # Full COD excluded
        assert form.taxable_cod_income == 0

    def test_solvent_no_exclusion(self):
        """Solvent taxpayer gets no insolvency exclusion."""
        insolvency = InsolvencyCalculation(
            other_assets_fmv=100000,
            other_liabilities=80000  # Solvent
        )

        form = Form982(
            total_cod_income=20000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=insolvency
        )

        assert insolvency.is_insolvent is False
        assert form.excluded_amount == 0
        assert form.taxable_cod_income == 20000


class TestQPRIExclusion:
    """Test qualified principal residence indebtedness exclusion."""

    def test_qpri_full_exclusion(self):
        """QPRI excludes up to $750,000."""
        form = Form982(
            total_cod_income=100000,
            exclusion_type=ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE,
            property_basis_available=300000
        )

        assert form.is_qpri is True
        assert form.excluded_amount == 100000
        assert form.taxable_cod_income == 0

    def test_qpri_750k_limit(self):
        """QPRI limited to $750,000."""
        form = Form982(
            total_cod_income=1000000,
            exclusion_type=ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE,
            property_basis_available=1500000
        )

        assert form.maximum_exclusion == 750000
        assert form.excluded_amount == 750000
        assert form.taxable_cod_income == 250000

    def test_qpri_no_attribute_reduction(self):
        """QPRI reduces basis only, not other attributes."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE,
            nol_carryover=100000  # Should NOT be reduced
        )

        assert form.attribute_reduction_required == 0
        reductions = form.calculate_attribute_reductions()
        assert len(reductions) == 0


class TestQRPBIExclusion:
    """Test qualified real property business indebtedness exclusion."""

    def test_qrpbi_limited_to_basis(self):
        """QRPBI limited to basis of qualifying property."""
        form = Form982(
            total_cod_income=200000,
            exclusion_type=ExclusionType.QUALIFIED_REAL_PROPERTY,
            qrpbi_property_basis=150000
        )

        assert form.is_qrpbi is True
        assert form.maximum_exclusion == 150000
        assert form.excluded_amount == 150000
        assert form.taxable_cod_income == 50000

    def test_qrpbi_full_exclusion(self):
        """QRPBI with sufficient basis."""
        form = Form982(
            total_cod_income=100000,
            exclusion_type=ExclusionType.QUALIFIED_REAL_PROPERTY,
            qrpbi_property_basis=200000
        )

        assert form.excluded_amount == 100000
        assert form.taxable_cod_income == 0


class TestQualifiedFarmExclusion:
    """Test qualified farm indebtedness exclusion."""

    def test_qualified_farm_exclusion(self):
        """Qualified farm debt exclusion."""
        form = Form982(
            total_cod_income=75000,
            exclusion_type=ExclusionType.QUALIFIED_FARM
        )

        assert form.is_qualified_farm is True
        assert form.excluded_amount == 75000
        assert form.taxable_cod_income == 0


class TestNoExclusion:
    """Test when no exclusion applies."""

    def test_no_exclusion_fully_taxable(self):
        """No exclusion - COD fully taxable."""
        form = Form982(
            total_cod_income=25000,
            exclusion_type=ExclusionType.NONE
        )

        assert form.maximum_exclusion == 0
        assert form.excluded_amount == 0
        assert form.taxable_cod_income == 25000
        assert form.attribute_reduction_required == 0


class TestTaxAttributeReduction:
    """Test tax attribute reduction order and calculations."""

    def test_reduction_order(self):
        """Test attributes reduced in correct order."""
        form = Form982(
            total_cod_income=100000,
            exclusion_type=ExclusionType.BANKRUPTCY,
            nol_carryover=20000,
            general_business_credit=10000,  # Reduces $30000 of COD
            capital_loss_carryover=30000,
            property_basis_available=50000
        )

        reductions = form.calculate_attribute_reductions()

        # Should reduce in order: NOL, GBC, capital loss, basis
        types = [r.attribute_type for r in reductions]
        assert types[0] == TaxAttributeType.NOL
        assert types[1] == TaxAttributeType.GENERAL_BUSINESS_CREDIT
        assert types[2] == TaxAttributeType.CAPITAL_LOSS_CARRYOVER
        assert types[3] == TaxAttributeType.BASIS_REDUCTION

    def test_credit_reduces_at_one_third_rate(self):
        """Credits reduce COD at 1/3 rate ($1 credit = $3 COD)."""
        form = Form982(
            total_cod_income=30000,
            exclusion_type=ExclusionType.BANKRUPTCY,
            general_business_credit=15000  # Can absorb $45000 of COD
        )

        reductions = form.calculate_attribute_reductions()

        gbc = next(r for r in reductions if r.attribute_type == TaxAttributeType.GENERAL_BUSINESS_CREDIT)
        assert gbc.reduction_amount == 10000  # 30000 / 3 = 10000 credit used

    def test_nol_first_then_credits(self):
        """NOL reduced first, then credits."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.BANKRUPTCY,
            nol_carryover=30000,
            general_business_credit=20000
        )

        reductions = form.calculate_attribute_reductions()

        nol = next(r for r in reductions if r.attribute_type == TaxAttributeType.NOL)
        gbc = next(r for r in reductions if r.attribute_type == TaxAttributeType.GENERAL_BUSINESS_CREDIT)

        assert nol.reduction_amount == 30000  # Full NOL
        # Remaining: 50000 - 30000 = 20000
        # GBC: 20000 / 3 = 6666.67
        assert abs(gbc.reduction_amount - 6666.67) < 1

    def test_attribute_ending_balance(self):
        """Test ending balance calculation."""
        reduction = TaxAttributeReduction(
            attribute_type=TaxAttributeType.NOL,
            beginning_balance=50000,
            reduction_amount=30000
        )

        assert reduction.ending_balance == 20000

    def test_is_credit_flag(self):
        """Test is_credit flag for different attribute types."""
        nol = TaxAttributeReduction(attribute_type=TaxAttributeType.NOL, beginning_balance=0)
        gbc = TaxAttributeReduction(attribute_type=TaxAttributeType.GENERAL_BUSINESS_CREDIT, beginning_balance=0)

        assert nol.is_credit is False
        assert gbc.is_credit is True


class TestBasisReduction:
    """Test Section 1017 basis reduction."""

    def test_basic_basis_reduction(self):
        """Test basic basis reduction."""
        basis = BasisReduction(
            property_description="Rental property",
            original_basis=200000,
            accumulated_depreciation=30000,
            reduction_amount=50000
        )

        assert basis.adjusted_basis_before == 170000
        assert basis.actual_reduction == 50000
        assert basis.adjusted_basis_after == 120000

    def test_basis_reduction_limited_by_liabilities(self):
        """Basis reduction limited - cannot reduce below secured liabilities."""
        basis = BasisReduction(
            original_basis=200000,
            accumulated_depreciation=30000,  # Adjusted basis: 170000
            liabilities_secured=150000,  # Minimum basis
            reduction_amount=50000  # Would reduce to 120000, but limited
        )

        assert basis.minimum_basis == 150000
        assert basis.maximum_reduction == 20000  # 170000 - 150000
        assert basis.actual_reduction == 20000  # Limited
        assert basis.adjusted_basis_after == 150000


class TestDischargedDebt:
    """Test discharged debt tracking."""

    def test_basic_discharged_debt(self):
        """Test basic discharged debt."""
        debt = DischargedDebt(
            creditor_name="Bank of America",
            debt_type=DebtType.CREDIT_CARD,
            original_amount=25000,
            amount_discharged=15000,
            form_1099c_received=True
        )

        assert debt.cod_income == 15000
        assert debt.debt_type == DebtType.CREDIT_CARD

    def test_secured_debt(self):
        """Test secured debt properties."""
        debt = DischargedDebt(
            creditor_name="Wells Fargo",
            debt_type=DebtType.MORTGAGE,
            original_amount=300000,
            amount_discharged=50000,
            is_secured=True,
            secured_property_fmv=250000,
            secured_property_basis=200000
        )

        assert debt.is_secured is True
        assert debt.secured_property_fmv == 250000


class TestForm982PartI:
    """Test Part I - General Information."""

    def test_bankruptcy_checkbox(self):
        """Test bankruptcy checkbox."""
        part_i = Form982PartI(
            line_1a_bankruptcy=True,
            line_2_excluded_amount=50000
        )

        assert part_i.exclusion_type == ExclusionType.BANKRUPTCY
        assert part_i.requires_attribute_reduction is True

    def test_insolvency_checkbox(self):
        """Test insolvency checkbox."""
        part_i = Form982PartI(
            line_1b_insolvency=True,
            line_2_excluded_amount=30000
        )

        assert part_i.exclusion_type == ExclusionType.INSOLVENCY

    def test_qpri_no_attribute_reduction(self):
        """QPRI doesn't require attribute reduction (only basis)."""
        part_i = Form982PartI(
            line_1e_qpri=True,
            line_2_excluded_amount=100000
        )

        assert part_i.exclusion_type == ExclusionType.QUALIFIED_PRINCIPAL_RESIDENCE
        assert part_i.requires_attribute_reduction is False

    def test_no_exclusion_selected(self):
        """No exclusion checkbox selected."""
        part_i = Form982PartI(
            line_2_excluded_amount=0
        )

        assert part_i.exclusion_type == ExclusionType.NONE


class TestForm982PartII:
    """Test Part II - Tax Attribute Reductions."""

    def test_total_attribute_reduction(self):
        """Test total attribute reduction calculation."""
        part_ii = Form982PartII(
            line_3_nol_reduction=20000,
            line_4_general_business_credit=5000,  # × 3 = 15000
            line_6_capital_loss=10000,
            line_7_basis_reduction=15000
        )

        # Losses: 20000 + 10000 + 15000 = 45000
        # Credits: 5000 × 3 = 15000
        # Total: 60000
        assert part_ii.total_attribute_reduction == 60000


class TestForm982Complete:
    """Test complete Form 982."""

    def test_complete_form_bankruptcy(self):
        """Test complete bankruptcy scenario."""
        form = Form982(
            tax_year=2025,
            total_cod_income=80000,
            exclusion_type=ExclusionType.BANKRUPTCY,
            nol_carryover=50000,
            capital_loss_carryover=20000,
            property_basis_available=30000
        )

        assert form.excluded_amount == 80000
        assert form.taxable_cod_income == 0

        reductions = form.calculate_attribute_reductions()
        total_reduced = sum(
            r.reduction_amount * (3 if r.is_credit else 1)
            for r in reductions
        )
        assert total_reduced == 80000

    def test_complete_form_insolvency(self):
        """Test complete insolvency scenario."""
        insolvency = InsolvencyCalculation(
            cash_and_bank_accounts=10000,
            real_estate_fmv=150000,
            vehicles_fmv=20000,
            mortgage_debt=180000,
            credit_card_debt=40000,
            auto_loans=15000
        )

        form = Form982(
            tax_year=2025,
            total_cod_income=60000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=insolvency,
            nol_carryover=30000
        )

        # Assets: 180000, Liabilities: 235000, Insolvency: 55000
        assert insolvency.insolvency_amount == 55000
        assert form.excluded_amount == 55000
        assert form.taxable_cod_income == 5000

    def test_get_part_i(self):
        """Test generating Part I."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.BANKRUPTCY
        )

        part_i = form.get_part_i()

        assert part_i.line_1a_bankruptcy is True
        assert part_i.line_2_excluded_amount == 50000

    def test_get_part_ii(self):
        """Test generating Part II."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.BANKRUPTCY,
            nol_carryover=30000,
            capital_loss_carryover=25000
        )

        part_ii = form.get_part_ii()

        assert part_ii.line_3_nol_reduction == 30000
        assert part_ii.line_6_capital_loss == 20000


class TestConvenienceFunctions:
    """Test convenience calculation functions."""

    def test_calculate_insolvency(self):
        """Test calculate_insolvency function."""
        result = calculate_insolvency(
            total_assets=100000,
            total_liabilities=150000,
            cod_income=80000
        )

        assert result["is_insolvent"] is True
        assert result["insolvency_amount"] == 50000
        assert result["excluded_amount"] == 50000
        assert result["taxable_cod"] == 30000

    def test_calculate_bankruptcy_exclusion(self):
        """Test calculate_bankruptcy_exclusion function."""
        result = calculate_bankruptcy_exclusion(
            cod_income=100000,
            nol_carryover=60000,
            capital_loss_carryover=50000
        )

        assert result["exclusion_type"] == "bankruptcy"
        assert result["excluded_amount"] == 100000
        assert result["taxable_cod_income"] == 0
        assert len(result["attribute_reductions"]) > 0

    def test_calculate_qpri_exclusion(self):
        """Test calculate_qpri_exclusion function."""
        result = calculate_qpri_exclusion(
            cod_income=150000,
            principal_residence_basis=400000
        )

        assert result["excluded_amount"] == 150000
        assert result["taxable_cod"] == 0
        assert result["basis_reduction"] == 150000
        assert result["new_basis"] == 250000


class TestToDictionary:
    """Test form serialization."""

    def test_to_dict(self):
        """Test to_dict method."""
        insolvency = InsolvencyCalculation(
            other_assets_fmv=80000,
            other_liabilities=100000
        )

        form = Form982(
            tax_year=2025,
            total_cod_income=30000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=insolvency,
            nol_carryover=15000
        )

        result = form.to_dict()

        assert result["tax_year"] == 2025
        assert result["total_cod_income"] == 30000
        assert result["exclusion_type"] == "insolvency"
        assert result["excluded_amount"] == 20000
        assert result["insolvency_amount"] == 20000
        assert "attribute_reductions" in result

    def test_to_form_1040(self):
        """Test to_form_1040 method."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.INSOLVENCY,
            insolvency_calculation=InsolvencyCalculation(
                other_assets_fmv=80000,
                other_liabilities=100000  # 20000 insolvent
            )
        )

        result = form.to_form_1040()

        assert result["excluded_cod_income"] == 20000
        assert result["taxable_cod_income"] == 30000
        assert result["other_income_cod"] == 30000


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_cod_income(self):
        """Test with zero COD income."""
        form = Form982(
            total_cod_income=0,
            exclusion_type=ExclusionType.BANKRUPTCY
        )

        assert form.excluded_amount == 0
        assert form.taxable_cod_income == 0
        assert len(form.calculate_attribute_reductions()) == 0

    def test_no_attributes_to_reduce(self):
        """Test with no tax attributes available."""
        form = Form982(
            total_cod_income=50000,
            exclusion_type=ExclusionType.BANKRUPTCY
            # No attributes specified - all default to 0
        )

        assert form.excluded_amount == 50000
        reductions = form.calculate_attribute_reductions()
        assert len(reductions) == 0

    def test_all_exclusion_types(self):
        """Test all exclusion types are valid."""
        for exclusion_type in ExclusionType:
            form = Form982(
                total_cod_income=10000,
                exclusion_type=exclusion_type
            )
            assert form.exclusion_type == exclusion_type

    def test_all_debt_types(self):
        """Test all debt types are valid."""
        for debt_type in DebtType:
            debt = DischargedDebt(
                creditor_name="Test",
                debt_type=debt_type,
                amount_discharged=1000
            )
            assert debt.debt_type == debt_type

    def test_all_attribute_types(self):
        """Test all attribute types are valid."""
        for attr_type in TaxAttributeType:
            reduction = TaxAttributeReduction(
                attribute_type=attr_type,
                beginning_balance=1000,
                reduction_amount=500
            )
            assert reduction.attribute_type == attr_type


class TestMultipleDebts:
    """Test scenarios with multiple discharged debts."""

    def test_multiple_debts_total(self):
        """Test aggregating multiple discharged debts."""
        debts = [
            DischargedDebt(
                creditor_name="Chase",
                debt_type=DebtType.CREDIT_CARD,
                amount_discharged=15000
            ),
            DischargedDebt(
                creditor_name="Citi",
                debt_type=DebtType.CREDIT_CARD,
                amount_discharged=10000
            ),
            DischargedDebt(
                creditor_name="Hospital",
                debt_type=DebtType.MEDICAL_DEBT,
                amount_discharged=25000
            )
        ]

        total_cod = sum(d.cod_income for d in debts)
        assert total_cod == 50000

        form = Form982(
            total_cod_income=total_cod,
            exclusion_type=ExclusionType.BANKRUPTCY,
            discharged_debts=debts
        )

        assert form.excluded_amount == 50000
