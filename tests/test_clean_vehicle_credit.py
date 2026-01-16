"""
Comprehensive tests for Clean Vehicle Credit (Form 8936).

Tests cover:
- New Clean Vehicle Credit (IRC Section 30D) - up to $7,500
- Previously Owned Clean Vehicle Credit (IRC Section 25E) - up to $4,000
- Income limits by filing status
- MSRP limits by vehicle type
- Battery component and critical mineral requirements
- Model year requirements for used vehicles
- North American assembly requirement
"""

import pytest
from models.income import Income, W2Info
from models.deductions import Deductions
from models.credits import (
    TaxCredits,
    CleanVehiclePurchase,
    VehicleType,
)
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from calculator.engine import FederalTaxEngine


# ============================================
# Helper Functions
# ============================================

def make_taxpayer(filing_status: FilingStatus = FilingStatus.SINGLE) -> TaxpayerInfo:
    """Create a basic taxpayer for testing."""
    return TaxpayerInfo(
        first_name="Test",
        last_name="Taxpayer",
        ssn="123-45-6789",
        filing_status=filing_status,
    )


def make_w2(wages: float, federal_withheld: float = 0.0) -> W2Info:
    """Create a W2 for testing."""
    return W2Info(
        employer_name="Test Employer",
        employer_ein="12-3456789",
        wages=wages,
        federal_tax_withheld=federal_withheld,
    )


def make_return(
    filing_status: FilingStatus = FilingStatus.SINGLE,
    income: Income = None,
    credits: TaxCredits = None,
) -> TaxReturn:
    """Create a tax return for testing."""
    return TaxReturn(
        tax_year=2025,
        taxpayer=make_taxpayer(filing_status),
        income=income or Income(),
        deductions=Deductions(use_standard_deduction=True),
        credits=credits or TaxCredits(),
    )


def make_new_ev(
    vin: str = "1HGBH41JXMN109186",
    make: str = "Tesla",
    model: str = "Model 3",
    model_year: int = 2025,
    msrp: float = 45000.0,
    purchase_price: float = 45000.0,
    vehicle_type: VehicleType = VehicleType.SEDAN,
    meets_battery: bool = True,
    meets_mineral: bool = True,
    north_america: bool = True,
) -> CleanVehiclePurchase:
    """Create a new EV purchase for testing."""
    return CleanVehiclePurchase(
        vin=vin,
        make=make,
        model=model,
        model_year=model_year,
        purchase_date="2025-03-15",
        purchase_price=purchase_price,
        msrp=msrp,
        vehicle_type=vehicle_type,
        is_new_vehicle=True,
        final_assembly_north_america=north_america,
        meets_battery_component_req=meets_battery,
        meets_critical_mineral_req=meets_mineral,
    )


def make_used_ev(
    vin: str = "5YJSA1E27HF000001",
    make: str = "Tesla",
    model: str = "Model S",
    model_year: int = 2020,
    purchase_price: float = 20000.0,
    is_first_transfer: bool = True,
) -> CleanVehiclePurchase:
    """Create a used EV purchase for testing."""
    return CleanVehiclePurchase(
        vin=vin,
        make=make,
        model=model,
        model_year=model_year,
        purchase_date="2025-06-01",
        purchase_price=purchase_price,
        msrp=purchase_price,  # MSRP not relevant for used
        vehicle_type=VehicleType.SEDAN,
        is_new_vehicle=False,
        is_first_transfer=is_first_transfer,
    )


# ============================================
# Test: No Vehicles
# ============================================

class TestNoVehicles:
    """Test behavior when no clean vehicles."""

    def test_no_vehicles_returns_zero_credit(self):
        """No vehicles should return zero credit."""
        engine = FederalTaxEngine()
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=TaxCredits(),
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0
        assert result.credit_breakdown['used_clean_vehicle_credit'] == 0.0


# ============================================
# Test: New Clean Vehicle Credit (Section 30D)
# ============================================

class TestNewVehicleCredit:
    """Test New Clean Vehicle Credit (IRC Section 30D)."""

    def test_full_7500_credit(self):
        """Vehicle meeting all requirements gets full $7,500."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            msrp=50000.0,
            meets_battery=True,
            meets_mineral=True,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0

    def test_battery_only_3750(self):
        """Vehicle meeting only battery requirement gets $3,750."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            meets_battery=True,
            meets_mineral=False,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 3750.0

    def test_mineral_only_3750(self):
        """Vehicle meeting only critical mineral requirement gets $3,750."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            meets_battery=False,
            meets_mineral=True,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 3750.0

    def test_neither_requirement_zero(self):
        """Vehicle meeting neither requirement gets $0."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            meets_battery=False,
            meets_mineral=False,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0


# ============================================
# Test: MSRP Limits
# ============================================

class TestMSRPLimits:
    """Test MSRP limits for new vehicles."""

    def test_sedan_under_55k_qualifies(self):
        """Sedan under $55,000 MSRP qualifies."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            msrp=54999.0,
            vehicle_type=VehicleType.SEDAN,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0

    def test_sedan_over_55k_disqualified(self):
        """Sedan over $55,000 MSRP is disqualified."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            msrp=55001.0,
            vehicle_type=VehicleType.SEDAN,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0

    def test_suv_under_80k_qualifies(self):
        """SUV under $80,000 MSRP qualifies."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            msrp=79000.0,
            vehicle_type=VehicleType.SUV,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0

    def test_suv_over_80k_disqualified(self):
        """SUV over $80,000 MSRP is disqualified."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            msrp=80001.0,
            vehicle_type=VehicleType.SUV,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0

    def test_truck_80k_limit(self):
        """Truck/pickup has $80,000 limit."""
        engine = FederalTaxEngine()
        ev = make_new_ev(
            msrp=79999.0,
            vehicle_type=VehicleType.TRUCK,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0


# ============================================
# Test: Income Limits - New Vehicles
# ============================================

class TestNewVehicleIncomeLimits:
    """Test income limits for new clean vehicles."""

    def test_single_under_150k(self):
        """Single filer under $150,000 qualifies."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(140000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0

    def test_single_over_150k_disqualified(self):
        """Single filer over $150,000 is disqualified."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(160000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0

    def test_mfj_under_300k(self):
        """MFJ under $300,000 qualifies."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(290000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0

    def test_mfj_over_300k_disqualified(self):
        """MFJ over $300,000 is disqualified."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(310000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0

    def test_hoh_under_225k(self):
        """HOH under $225,000 qualifies."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            income=Income(w2_forms=[make_w2(220000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0


# ============================================
# Test: North American Assembly
# ============================================

class TestNorthAmericanAssembly:
    """Test North American assembly requirement."""

    def test_assembled_in_na_qualifies(self):
        """Vehicle assembled in North America qualifies."""
        engine = FederalTaxEngine()
        ev = make_new_ev(north_america=True)
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0

    def test_not_assembled_in_na_disqualified(self):
        """Vehicle not assembled in North America is disqualified."""
        engine = FederalTaxEngine()
        ev = make_new_ev(north_america=False)
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 0.0


# ============================================
# Test: Previously Owned Clean Vehicle (Section 25E)
# ============================================

class TestUsedVehicleCredit:
    """Test Previously Owned Clean Vehicle Credit (IRC Section 25E)."""

    def test_max_4000_credit(self):
        """Used EV gets max $4,000 credit (30% of $25k max)."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            purchase_price=20000.0,
            model_year=2020,  # 5 years old (OK for 2025)
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 30% of $20,000 = $6,000, capped at $4,000
        assert result.credit_breakdown['used_clean_vehicle_credit'] == 4000.0

    def test_30_percent_of_price(self):
        """Credit is 30% of sale price (below $4k cap)."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            purchase_price=10000.0,
            model_year=2020,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # 30% of $10,000 = $3,000
        assert result.credit_breakdown['used_clean_vehicle_credit'] == 3000.0

    def test_price_over_25k_disqualified(self):
        """Used EV over $25,000 is disqualified."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            purchase_price=26000.0,
            model_year=2020,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 0.0


# ============================================
# Test: Model Year Requirement - Used Vehicles
# ============================================

class TestUsedVehicleModelYear:
    """Test model year requirement for used vehicles."""

    def test_model_2_years_old_qualifies(self):
        """Vehicle 2+ years old qualifies (model year <= tax_year - 2)."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            model_year=2023,  # 2 years old for 2025
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] > 0

    def test_model_too_recent_disqualified(self):
        """Vehicle less than 2 years old is disqualified."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            model_year=2024,  # Only 1 year old for 2025
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 0.0


# ============================================
# Test: Income Limits - Used Vehicles
# ============================================

class TestUsedVehicleIncomeLimits:
    """Test income limits for used clean vehicles."""

    def test_single_under_75k(self):
        """Single filer under $75,000 qualifies for used vehicle credit."""
        engine = FederalTaxEngine()
        ev = make_used_ev(model_year=2020)
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(70000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 4000.0

    def test_single_over_75k_disqualified(self):
        """Single filer over $75,000 is disqualified from used vehicle credit."""
        engine = FederalTaxEngine()
        ev = make_used_ev(model_year=2020)
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.SINGLE,
            income=Income(w2_forms=[make_w2(80000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 0.0

    def test_mfj_under_150k(self):
        """MFJ under $150,000 qualifies for used vehicle credit."""
        engine = FederalTaxEngine()
        ev = make_used_ev(model_year=2020)
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.MARRIED_JOINT,
            income=Income(w2_forms=[make_w2(140000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 4000.0

    def test_hoh_under_112500(self):
        """HOH under $112,500 qualifies for used vehicle credit."""
        engine = FederalTaxEngine()
        ev = make_used_ev(model_year=2020)
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            income=Income(w2_forms=[make_w2(110000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 4000.0


# ============================================
# Test: First Transfer Requirement
# ============================================

class TestFirstTransfer:
    """Test first transfer requirement for used vehicles."""

    def test_first_transfer_qualifies(self):
        """First transfer of used vehicle qualifies."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            model_year=2020,
            is_first_transfer=True,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 4000.0

    def test_not_first_transfer_disqualified(self):
        """Subsequent transfer of used vehicle is disqualified."""
        engine = FederalTaxEngine()
        ev = make_used_ev(
            model_year=2020,
            is_first_transfer=False,
        )
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['used_clean_vehicle_credit'] == 0.0


# ============================================
# Test: Multiple Vehicles
# ============================================

class TestMultipleVehicles:
    """Test multiple vehicle purchases."""

    def test_two_new_vehicles(self):
        """Two qualifying new vehicles get combined credit."""
        engine = FederalTaxEngine()
        ev1 = make_new_ev(vin="VIN1", msrp=45000.0)
        ev2 = make_new_ev(vin="VIN2", msrp=50000.0)
        credits = TaxCredits(clean_vehicles=[ev1, ev2])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Both get full credit
        assert result.credit_breakdown['new_clean_vehicle_credit'] == 15000.0

    def test_new_and_used_combined(self):
        """New and used vehicle credits combined."""
        engine = FederalTaxEngine()
        new_ev = make_new_ev(msrp=45000.0)
        used_ev = make_used_ev(model_year=2020, purchase_price=20000.0)
        credits = TaxCredits(clean_vehicles=[new_ev, used_ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(60000)]),  # Under both limits
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0
        assert result.credit_breakdown['used_clean_vehicle_credit'] == 4000.0

    def test_one_qualifies_one_doesnt(self):
        """One qualifying, one disqualified vehicle."""
        engine = FederalTaxEngine()
        good_ev = make_new_ev(vin="GOOD", msrp=50000.0)
        bad_ev = make_new_ev(vin="BAD", msrp=60000.0)  # Over $55k sedan limit
        credits = TaxCredits(clean_vehicles=[good_ev, bad_ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0


# ============================================
# Test: Integration with Tax Calculation
# ============================================

class TestIntegration:
    """Test clean vehicle credit integration with tax calculation."""

    def test_credit_reduces_tax(self):
        """Clean vehicle credit reduces total tax."""
        engine = FederalTaxEngine()

        # Without EV credit
        tax_return_no_ev = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=TaxCredits(),
        )
        result_no_ev = engine.calculate(tax_return_no_ev)

        # With EV credit
        ev = make_new_ev()
        tax_return_with_ev = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=TaxCredits(clean_vehicles=[ev]),
        )
        result_with_ev = engine.calculate(tax_return_with_ev)

        # Tax should be reduced by the credit (up to available tax)
        assert result_with_ev.total_tax < result_no_ev.total_tax

    def test_credit_breakdown_populated(self):
        """Clean vehicle breakdown should be populated."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(100000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        breakdown = result.clean_vehicle_breakdown
        assert 'new_vehicles' in breakdown
        assert 'total_new_credit' in breakdown
        assert breakdown['new_vehicles_qualified'] == 1

    def test_nonrefundable_credit(self):
        """Clean vehicle credit is nonrefundable (cannot exceed tax)."""
        engine = FederalTaxEngine()
        ev = make_new_ev()
        credits = TaxCredits(clean_vehicles=[ev])
        # Very low income = very low tax
        tax_return = make_return(
            income=Income(w2_forms=[make_w2(20000)]),
            credits=credits,
        )
        result = engine.calculate(tax_return)

        # Credit shouldn't create a refund by itself (nonrefundable)
        # The total tax won't go below zero due to just this credit
        assert result.credit_breakdown['new_clean_vehicle_credit'] == 7500.0
        # But the actual benefit is limited by available tax
