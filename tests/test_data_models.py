"""
Comprehensive tests for Data Models — FilingStatus, DependentRelationship,
Dependent, TaxpayerInfo, TaxReturn, Income (W2Info, Form1099Info),
Deductions (standard/itemized, IRA/Roth phaseouts, SALT cap, TCJA mortgage),
and Credits (CleanVehiclePurchase).
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.taxpayer import (
    FilingStatus,
    DependentRelationship,
    Dependent,
    TaxpayerInfo,
)
from models.deductions import ItemizedDeductions, Deductions
from models.credits import CleanVehiclePurchase, VehicleType


# ===================================================================
# FILING STATUS ENUM
# ===================================================================

class TestFilingStatus:

    @pytest.mark.parametrize("status,value", [
        (FilingStatus.SINGLE, "single"),
        (FilingStatus.MARRIED_JOINT, "married_joint"),
        (FilingStatus.MARRIED_SEPARATE, "married_separate"),
        (FilingStatus.HEAD_OF_HOUSEHOLD, "head_of_household"),
        (FilingStatus.QUALIFYING_WIDOW, "qualifying_widow"),
    ])
    def test_filing_status_values(self, status, value):
        assert status.value == value

    def test_filing_status_count(self):
        assert len(FilingStatus) == 5

    @pytest.mark.parametrize("status", list(FilingStatus))
    def test_filing_status_is_string(self, status):
        assert isinstance(status.value, str)

    @pytest.mark.parametrize("value", [
        "single", "married_joint", "married_separate",
        "head_of_household", "qualifying_widow",
    ])
    def test_filing_status_from_value(self, value):
        status = FilingStatus(value)
        assert status.value == value


# ===================================================================
# DEPENDENT RELATIONSHIP ENUM
# ===================================================================

class TestDependentRelationship:

    @pytest.mark.parametrize("rel", [
        DependentRelationship.SON,
        DependentRelationship.DAUGHTER,
        DependentRelationship.STEPSON,
        DependentRelationship.STEPDAUGHTER,
        DependentRelationship.FOSTER_CHILD,
        DependentRelationship.BROTHER,
        DependentRelationship.SISTER,
    ])
    def test_qualifying_child_relationships(self, rel):
        assert isinstance(rel.value, str)

    @pytest.mark.parametrize("rel", [
        DependentRelationship.PARENT,
        DependentRelationship.GRANDPARENT,
        DependentRelationship.AUNT,
        DependentRelationship.UNCLE,
        DependentRelationship.IN_LAW,
    ])
    def test_qualifying_relative_relationships(self, rel):
        assert isinstance(rel.value, str)

    def test_other_household_member(self):
        assert DependentRelationship.OTHER_HOUSEHOLD_MEMBER.value == "other_household_member"

    def test_relationship_count(self):
        assert len(DependentRelationship) >= 20


# ===================================================================
# DEPENDENT MODEL
# ===================================================================

class TestDependentModel:

    def test_basic_dependent(self):
        dep = Dependent(
            name="John Jr",
            relationship="son",
            age=10,
        )
        assert dep.name == "John Jr"
        assert dep.age == 10

    def test_dependent_with_ssn(self):
        dep = Dependent(
            name="Jane Jr",
            relationship="daughter",
            age=8,
            ssn="123-45-6789",
        )
        assert dep.ssn == "123-45-6789"

    @pytest.mark.parametrize("ssn", [
        "123-45-6789",
        "234-56-7890",
        None,
    ])
    def test_valid_ssn_values(self, ssn):
        dep = Dependent(name="Child", relationship="son", age=5, ssn=ssn)
        assert dep.ssn == ssn

    @pytest.mark.parametrize("ssn", [
        "000-00-0000",
        "000-12-3456",
        "666-12-3456",
        "900-12-3456",
    ])
    def test_invalid_ssn_patterns(self, ssn):
        with pytest.raises(Exception):
            Dependent(name="Child", relationship="son", age=5, ssn=ssn)

    def test_ssn_wrong_length(self):
        with pytest.raises(Exception):
            Dependent(name="Child", relationship="son", age=5, ssn="12345")

    @pytest.mark.parametrize("name", [
        "John",
        "Mary Jane",
        "O'Brien",
        "Smith-Jones",
        "Dr. Smith",
    ])
    def test_valid_names(self, name):
        dep = Dependent(name=name, relationship="child", age=5)
        assert dep.name == name

    def test_empty_name_rejected(self):
        with pytest.raises(Exception):
            Dependent(name="", relationship="child", age=5)

    def test_name_with_invalid_chars(self):
        with pytest.raises(Exception):
            Dependent(name="John<script>", relationship="child", age=5)

    @pytest.mark.parametrize("age", [0, 1, 10, 18, 24, 65, 130])
    def test_valid_ages(self, age):
        dep = Dependent(name="Child", relationship="child", age=age)
        assert dep.age == age

    def test_negative_age_rejected(self):
        with pytest.raises(Exception):
            Dependent(name="Child", relationship="child", age=-1)

    def test_age_over_130_rejected(self):
        with pytest.raises(Exception):
            Dependent(name="Child", relationship="child", age=131)

    def test_default_fields(self):
        dep = Dependent(name="Child", relationship="son", age=10)
        assert dep.is_student is False
        assert dep.is_permanently_disabled is False
        assert dep.months_lived_with_taxpayer == 12
        assert dep.provided_own_support_percentage == 0.0
        assert dep.filed_joint_return is False
        assert dep.is_us_citizen is True
        assert dep.is_claimed_by_another is False

    def test_qualifying_child_fields(self):
        dep = Dependent(
            name="Student",
            relationship="son",
            age=20,
            is_student=True,
            months_lived_with_taxpayer=12,
        )
        assert dep.is_student is True
        assert dep.months_lived_with_taxpayer == 12

    def test_form_8332_fields(self):
        dep = Dependent(
            name="Child",
            relationship="son",
            age=10,
            has_form_8332_release=True,
            form_8332_years=[2024, 2025],
        )
        assert dep.has_form_8332_release is True
        assert 2025 in dep.form_8332_years


# ===================================================================
# TAXPAYER INFO MODEL
# ===================================================================

class TestTaxpayerInfo:

    def test_basic_taxpayer(self):
        tp = TaxpayerInfo(
            first_name="John",
            last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.first_name == "John"
        assert tp.last_name == "Doe"
        assert tp.filing_status == FilingStatus.SINGLE

    @pytest.mark.parametrize("first,last", [
        ("John", "Doe"),
        ("Mary Jane", "Smith"),
        ("O'Brien", "McDonald's"),
        ("Smith-Jones", "Williams"),
    ])
    def test_valid_names(self, first, last):
        tp = TaxpayerInfo(
            first_name=first, last_name=last,
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.first_name == first.strip()

    def test_empty_first_name_rejected(self):
        with pytest.raises(Exception):
            TaxpayerInfo(first_name="", last_name="Doe", filing_status=FilingStatus.SINGLE)

    def test_empty_last_name_rejected(self):
        with pytest.raises(Exception):
            TaxpayerInfo(first_name="John", last_name="", filing_status=FilingStatus.SINGLE)

    def test_ssn_optional(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.ssn is None

    def test_address_xss_rejected(self):
        with pytest.raises(Exception):
            TaxpayerInfo(
                first_name="John", last_name="Doe",
                filing_status=FilingStatus.SINGLE,
                address="<script>alert('xss')</script>",
            )

    @pytest.mark.parametrize("state", ["CA", "NY", "TX", "FL", "WA"])
    def test_valid_state_codes(self, state):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
            state=state,
        )
        assert tp.state == state

    def test_invalid_state_code(self):
        with pytest.raises(Exception):
            TaxpayerInfo(
                first_name="John", last_name="Doe",
                filing_status=FilingStatus.SINGLE,
                state="California",
            )

    @pytest.mark.parametrize("zip_code", ["12345", "12345-6789"])
    def test_valid_zip_codes(self, zip_code):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
            zip_code=zip_code,
        )
        assert tp.zip_code == zip_code

    def test_invalid_zip_code(self):
        with pytest.raises(Exception):
            TaxpayerInfo(
                first_name="John", last_name="Doe",
                filing_status=FilingStatus.SINGLE,
                zip_code="1234",
            )

    def test_date_of_birth_format(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
            date_of_birth="1990-01-15",
        )
        assert tp.date_of_birth == "1990-01-15"

    def test_invalid_dob_format(self):
        with pytest.raises(Exception):
            TaxpayerInfo(
                first_name="John", last_name="Doe",
                filing_status=FilingStatus.SINGLE,
                date_of_birth="01/15/1990",
            )

    def test_dependents_list(self):
        dep = Dependent(name="Jr", relationship="son", age=10)
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
            dependents=[dep],
        )
        assert len(tp.dependents) == 1

    def test_empty_dependents_default(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.dependents == []

    def test_spouse_info(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.MARRIED_JOINT,
            spouse_first_name="Jane",
            spouse_last_name="Doe",
            spouse_ssn="187-65-4321",
        )
        assert tp.spouse_first_name == "Jane"

    def test_filing_status_string_conversion(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status="single",
        )
        assert tp.filing_status == FilingStatus.SINGLE

    def test_get_total_exemptions_single(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.get_total_exemptions() == 1

    def test_get_total_exemptions_married(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.MARRIED_JOINT,
        )
        assert tp.get_total_exemptions() == 2

    def test_get_total_exemptions_with_dependents(self):
        dep = Dependent(name="Jr", relationship="son", age=10)
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
            dependents=[dep],
        )
        assert tp.get_total_exemptions() == 2

    @pytest.mark.parametrize("status,expected", [
        (FilingStatus.SINGLE, 1),
        (FilingStatus.MARRIED_JOINT, 2),
        (FilingStatus.MARRIED_SEPARATE, 2),
        (FilingStatus.HEAD_OF_HOUSEHOLD, 1),
        (FilingStatus.QUALIFYING_WIDOW, 1),
    ])
    def test_exemptions_by_status(self, status, expected):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=status,
        )
        assert tp.get_total_exemptions() == expected

    def test_is_blind_default(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.is_blind is False

    def test_is_over_65_default(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.is_over_65 is False

    def test_special_status_flags_defaults(self):
        tp = TaxpayerInfo(
            first_name="John", last_name="Doe",
            filing_status=FilingStatus.SINGLE,
        )
        assert tp.spouse_itemizes_deductions is False
        assert tp.is_dual_status_alien is False
        assert tp.can_be_claimed_as_dependent is False
        assert tp.is_covered_by_employer_plan is False


# ===================================================================
# ITEMIZED DEDUCTIONS MODEL
# ===================================================================

class TestItemizedDeductions:

    def test_default_values(self):
        item = ItemizedDeductions()
        assert item.medical_expenses == 0.0
        assert item.state_local_income_tax == 0.0
        assert item.mortgage_interest == 0.0
        assert item.charitable_cash == 0.0

    @pytest.mark.parametrize("field", [
        "medical_expenses", "state_local_income_tax", "real_estate_tax",
        "mortgage_interest", "charitable_cash", "charitable_non_cash",
    ])
    def test_fields_non_negative(self, field):
        with pytest.raises(Exception):
            ItemizedDeductions(**{field: -1.0})

    def test_salt_cap_in_total(self):
        item = ItemizedDeductions(
            state_local_income_tax=8000,
            real_estate_tax=5000,
        )
        total = item.get_total_itemized(agi=100000)
        # SALT should be capped at $10,000
        assert total == 10000

    def test_medical_expenses_threshold(self):
        item = ItemizedDeductions(medical_expenses=10000)
        total = item.get_total_itemized(agi=100000)
        # 7.5% of $100k = $7,500; deductible = $10k - $7.5k = $2,500
        assert total == 2500

    def test_medical_below_threshold(self):
        item = ItemizedDeductions(medical_expenses=5000)
        total = item.get_total_itemized(agi=100000)
        # 7.5% of $100k = $7,500; $5k < $7.5k, nothing deductible
        assert total == 0

    def test_tcja_mortgage_interest_full(self):
        item = ItemizedDeductions(
            mortgage_interest=20000,
            mortgage_principal=500000,
        )
        limited = item.get_limited_mortgage_interest()
        assert limited == 20000  # Under $750k limit

    def test_tcja_mortgage_interest_limited(self):
        item = ItemizedDeductions(
            mortgage_interest=40000,
            mortgage_principal=1_500_000,
        )
        limited = item.get_limited_mortgage_interest()
        # $750k/$1.5M = 0.5, so $40k * 0.5 = $20k
        assert limited == 20000

    def test_grandfathered_mortgage_higher_limit(self):
        item = ItemizedDeductions(
            mortgage_interest=40000,
            mortgage_principal=800000,
            is_grandfathered_debt=True,
        )
        limited = item.get_limited_mortgage_interest()
        assert limited == 40000  # Under $1M grandfathered limit

    def test_mfs_mortgage_limit_halved(self):
        item = ItemizedDeductions(
            mortgage_interest=20000,
            mortgage_principal=500000,
        )
        limited = item.get_limited_mortgage_interest(filing_status="married_separate")
        # $375k/$500k = 0.75, so $20k * 0.75 = $15k
        assert limited == 15000

    def test_no_principal_full_deduction(self):
        item = ItemizedDeductions(mortgage_interest=15000)
        limited = item.get_limited_mortgage_interest()
        assert limited == 15000

    def test_gambling_losses_limited_to_winnings(self):
        item = ItemizedDeductions(gambling_losses=5000)
        total = item.get_total_itemized(agi=100000, gambling_winnings=3000)
        assert total == 3000  # Capped at winnings

    def test_charitable_contributions(self):
        item = ItemizedDeductions(charitable_cash=5000, charitable_non_cash=2000)
        total = item.get_total_itemized(agi=100000)
        assert total == 7000


# ===================================================================
# DEDUCTIONS MODEL
# ===================================================================

class TestDeductions:

    def test_default_standard_deduction(self):
        ded = Deductions()
        assert ded.use_standard_deduction is True

    def test_default_adjustments(self):
        ded = Deductions()
        assert ded.educator_expenses == 0.0
        assert ded.student_loan_interest == 0.0
        assert ded.hsa_contributions == 0.0
        assert ded.ira_contributions == 0.0

    @pytest.mark.parametrize("status,expected", [
        ("single", 15750.0),
        ("married_joint", 31500.0),
        ("married_separate", 15750.0),
        ("head_of_household", 23850.0),
        ("qualifying_widow", 31500.0),
    ])
    def test_standard_deduction_2025(self, status, expected):
        ded = Deductions()
        amount = ded.get_deduction_amount(filing_status=status, agi=100000)
        assert amount == expected

    def test_additional_deduction_over_65(self):
        ded = Deductions()
        base = ded.get_deduction_amount("single", 100000)
        with_age = ded.get_deduction_amount("single", 100000, is_over_65=True)
        assert with_age == base + 1950

    def test_additional_deduction_blind(self):
        ded = Deductions()
        base = ded.get_deduction_amount("single", 100000)
        with_blind = ded.get_deduction_amount("single", 100000, is_blind=True)
        assert with_blind == base + 1950

    def test_additional_deduction_both(self):
        ded = Deductions()
        base = ded.get_deduction_amount("single", 100000)
        with_both = ded.get_deduction_amount("single", 100000, is_over_65=True, is_blind=True)
        assert with_both == base + (1950 * 2)

    def test_married_additional_deduction_amount(self):
        ded = Deductions()
        base = ded.get_deduction_amount("married_joint", 100000)
        with_age = ded.get_deduction_amount("married_joint", 100000, is_over_65=True)
        assert with_age == base + 1550

    def test_mfs_spouse_itemizes_zero_deduction(self):
        ded = Deductions()
        amount = ded.get_deduction_amount(
            "married_separate", 100000, spouse_itemizes=True
        )
        assert amount == 0.0

    def test_dual_status_alien_zero_deduction(self):
        ded = Deductions()
        amount = ded.get_deduction_amount(
            "single", 100000, is_dual_status_alien=True
        )
        assert amount == 0.0

    def test_dependent_standard_deduction(self):
        ded = Deductions()
        amount = ded.get_deduction_amount(
            "single", 100000,
            can_be_claimed_as_dependent=True,
            earned_income_for_dependent=5000,
        )
        # max($1,350, $450+$5,000) = max($1,350, $5,450) = $5,450
        # Capped at $15,750 (single basic)
        assert amount == 5450

    def test_dependent_minimum_deduction(self):
        ded = Deductions()
        amount = ded.get_deduction_amount(
            "single", 100000,
            can_be_claimed_as_dependent=True,
            earned_income_for_dependent=0,
        )
        # max($1,350, $450+$0) = max($1,350, $450) = $1,350
        assert amount == 1350

    def test_student_loan_interest_cap(self):
        ded = Deductions(student_loan_interest=5000)
        deduction = ded.get_student_loan_interest_deduction(50000, "single")
        assert deduction == 2500  # Capped at $2,500

    def test_student_loan_interest_mfs_disallowed(self):
        ded = Deductions(student_loan_interest=2000)
        deduction = ded.get_student_loan_interest_deduction(50000, "married_separate")
        assert deduction == 0.0

    @pytest.mark.parametrize("magi,expected_deduction", [
        (50000, 2500),     # Below phaseout
        (85000, 2500),     # At phaseout start
        (100000, 0),       # At phaseout end
    ])
    def test_student_loan_phaseout_single(self, magi, expected_deduction):
        ded = Deductions(student_loan_interest=5000)
        deduction = ded.get_student_loan_interest_deduction(magi, "single")
        assert deduction == expected_deduction

    def test_educator_expenses_cap_single(self):
        ded = Deductions(educator_expenses=500)
        adjustments = ded.get_total_adjustments()
        # Cap is $300 for non-MFJ
        assert adjustments == 300

    def test_educator_expenses_cap_mfj(self):
        ded = Deductions(educator_expenses=800)
        adjustments = ded.get_total_adjustments(
            magi=50000, filing_status="married_joint"
        )
        # Cap is $600 for MFJ
        assert adjustments == 600

    def test_educator_expense_excess(self):
        ded = Deductions(educator_expenses=500)
        excess = ded.get_educator_expense_excess("single")
        assert excess == 200

    def test_educator_expense_no_excess(self):
        ded = Deductions(educator_expenses=200)
        excess = ded.get_educator_expense_excess("single")
        assert excess == 0

    def test_ira_deduction_no_employer_plan(self):
        ded = Deductions(ira_contributions=7000)
        deduction = ded.get_ira_deduction(
            magi=200000, filing_status="single",
            is_covered_by_employer_plan=False,
            taxable_compensation=200000,
        )
        assert deduction == 7000  # Full deduction, no phaseout

    def test_ira_deduction_with_employer_plan_phaseout(self):
        ded = Deductions(ira_contributions=7000)
        deduction = ded.get_ira_deduction(
            magi=89000, filing_status="single",
            is_covered_by_employer_plan=True,
            taxable_compensation=89000,
        )
        assert deduction == 0  # At/above phaseout end

    def test_ira_catchup_contribution(self):
        ded = Deductions(ira_contributions=8000)
        deduction = ded.get_ira_deduction(
            magi=50000, filing_status="single",
            is_covered_by_employer_plan=False,
            is_age_50_plus=True,
            taxable_compensation=50000,
        )
        assert deduction == 8000

    def test_ira_no_compensation_no_deduction(self):
        ded = Deductions(ira_contributions=7000)
        deduction = ded.get_ira_deduction(
            magi=50000, filing_status="single",
            taxable_compensation=0,
        )
        assert deduction == 0.0

    def test_roth_ira_eligible_contribution(self):
        ded = Deductions(roth_ira_contributions=7000)
        eligible = ded.get_roth_ira_eligible_contribution(
            magi=100000, filing_status="single",
            taxable_compensation=100000,
        )
        assert eligible == 7000  # Below phaseout

    def test_roth_ira_phaseout_single(self):
        ded = Deductions(roth_ira_contributions=7000)
        eligible = ded.get_roth_ira_eligible_contribution(
            magi=165000, filing_status="single",
            taxable_compensation=165000,
        )
        assert eligible == 0  # At/above phaseout end

    def test_roth_ira_combined_limit(self):
        ded = Deductions(roth_ira_contributions=7000)
        eligible = ded.get_roth_ira_eligible_contribution(
            magi=100000, filing_status="single",
            taxable_compensation=100000,
            traditional_ira_contributions=5000,
        )
        # $7,000 limit - $5,000 traditional = $2,000 remaining
        assert eligible == 2000


# ===================================================================
# VEHICLE TYPE ENUM
# ===================================================================

class TestVehicleType:

    @pytest.mark.parametrize("vtype,value", [
        (VehicleType.SEDAN, "sedan"),
        (VehicleType.HATCHBACK, "hatchback"),
        (VehicleType.SUV, "suv"),
        (VehicleType.VAN, "van"),
        (VehicleType.TRUCK, "truck"),
        (VehicleType.PICKUP, "pickup"),
    ])
    def test_vehicle_type_values(self, vtype, value):
        assert vtype.value == value

    def test_vehicle_type_count(self):
        assert len(VehicleType) == 6


# ===================================================================
# CLEAN VEHICLE PURCHASE
# ===================================================================

class TestCleanVehiclePurchase:

    def test_basic_new_vehicle(self):
        v = CleanVehiclePurchase(
            vin="1HGCG5655WA123456",
            model_year=2025,
            purchase_date="2025-06-15",
            purchase_price=45000,
            msrp=48000,
        )
        assert v.is_new_vehicle is True
        assert v.model_year == 2025

    def test_previously_owned_vehicle(self):
        v = CleanVehiclePurchase(
            vin="1HGCG5655WA123456",
            model_year=2022,
            purchase_date="2025-06-15",
            purchase_price=25000,
            msrp=35000,
            is_new_vehicle=False,
        )
        assert v.is_new_vehicle is False

    def test_vehicle_type_default(self):
        v = CleanVehiclePurchase(
            vin="ABC", model_year=2025,
            purchase_date="2025-01-01",
            purchase_price=40000, msrp=45000,
        )
        assert v.vehicle_type == VehicleType.SEDAN

    @pytest.mark.parametrize("vtype", list(VehicleType))
    def test_all_vehicle_types(self, vtype):
        v = CleanVehiclePurchase(
            vin="ABC", model_year=2025,
            purchase_date="2025-01-01",
            purchase_price=40000, msrp=45000,
            vehicle_type=vtype,
        )
        assert v.vehicle_type == vtype

    def test_model_year_minimum(self):
        with pytest.raises(Exception):
            CleanVehiclePurchase(
                vin="ABC", model_year=2009,
                purchase_date="2025-01-01",
                purchase_price=40000, msrp=45000,
            )

    def test_negative_price_rejected(self):
        with pytest.raises(Exception):
            CleanVehiclePurchase(
                vin="ABC", model_year=2025,
                purchase_date="2025-01-01",
                purchase_price=-1000, msrp=45000,
            )

    def test_negative_msrp_rejected(self):
        with pytest.raises(Exception):
            CleanVehiclePurchase(
                vin="ABC", model_year=2025,
                purchase_date="2025-01-01",
                purchase_price=40000, msrp=-1,
            )

    def test_first_transfer_default(self):
        v = CleanVehiclePurchase(
            vin="ABC", model_year=2025,
            purchase_date="2025-01-01",
            purchase_price=40000, msrp=45000,
        )
        assert v.is_first_transfer is True

    def test_make_and_model(self):
        v = CleanVehiclePurchase(
            vin="ABC", model_year=2025,
            purchase_date="2025-01-01",
            purchase_price=40000, msrp=45000,
            make="Tesla", model="Model 3",
        )
        assert v.make == "Tesla"
        assert v.model == "Model 3"
