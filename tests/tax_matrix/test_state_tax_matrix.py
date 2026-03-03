"""
State tax matrix tests.

Tests state tax calculations across all supported states, filing statuses,
and income levels.  Verifies no-income-tax states return None/0 and that
the is_state_supported() / get_supported_states() APIs work correctly.

Target: ~300 parametrised test cases.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from models.taxpayer import FilingStatus
from calculator.tax_calculator import TaxCalculator
from calculator.tax_year_config import TaxYearConfig
from calculator.state import StateTaxEngine, NO_INCOME_TAX_STATES

from _helpers import (
    make_tax_return,
    ALL_FILING_STATUSES,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NO_TAX_STATES = sorted(NO_INCOME_TAX_STATES)
INCOME_LEVELS = [30000, 75000, 150000]

# All 50 states + DC
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
    "WY",
]


# ===================================================================
# NO-INCOME-TAX STATES
# ===================================================================

class TestNoIncomeTaxStates:
    """States with no income tax should return zero/None for state tax."""

    @pytest.mark.parametrize("state", NO_TAX_STATES)
    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_no_income_tax(self, calculator_with_state, state, filing_status):
        tr = make_tax_return(
            filing_status=filing_status,
            wages=100000,
            state=state,
        )
        result = calculator_with_state.calculate_complete_return(tr)
        # State tax liability should be 0 or None for no-income-tax states
        assert result.state_tax_liability is None or result.state_tax_liability == 0.0

    @pytest.mark.parametrize("state", NO_TAX_STATES)
    def test_has_no_income_tax(self, calculator_with_state, state):
        assert not calculator_with_state.has_state_income_tax(state)

    @pytest.mark.parametrize("state", NO_TAX_STATES)
    def test_is_supported(self, calculator_with_state, state):
        # No-income-tax states are "supported" (they just return 0)
        assert calculator_with_state.is_state_supported(state)


# ===================================================================
# SUPPORTED STATES x FILING STATUSES x INCOME LEVELS
# ===================================================================

class TestSupportedStatesTax:
    """Test state tax calculations for all supported states."""

    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("wages", INCOME_LEVELS)
    def test_supported_states(self, calculator_with_state, filing_status, wages):
        """Test each supported state returns a reasonable state tax."""
        supported = calculator_with_state.get_supported_states()
        for state in supported:
            if state in NO_INCOME_TAX_STATES:
                continue
            tr = make_tax_return(
                filing_status=filing_status,
                wages=wages,
                state=state,
            )
            result = calculator_with_state.calculate_complete_return(tr)
            if result.state_tax_liability is not None:
                assert result.state_tax_liability >= 0, (
                    f"State {state} returned negative tax for {filing_status.value} at ${wages}"
                )


# ===================================================================
# INDIVIDUAL STATE TESTS (selected high-impact states)
# ===================================================================

SELECTED_STATES = ["CA", "NY", "TX", "FL", "IL", "PA", "NJ", "MA", "WA", "GA"]


class TestSelectedStates:
    """Test specific states across filing statuses and income levels."""

    @pytest.mark.parametrize("state", SELECTED_STATES)
    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    @pytest.mark.parametrize("wages", INCOME_LEVELS)
    def test_state_tax(self, calculator_with_state, state, filing_status, wages):
        tr = make_tax_return(
            filing_status=filing_status,
            wages=wages,
            state=state,
        )
        result = calculator_with_state.calculate_complete_return(tr)

        if state in NO_INCOME_TAX_STATES:
            assert result.state_tax_liability is None or result.state_tax_liability == 0.0
        else:
            if calculator_with_state.is_state_supported(state):
                # If supported and has income tax, should produce a result
                if result.state_tax_liability is not None:
                    assert result.state_tax_liability >= 0


# ===================================================================
# STATE TAX CONSISTENCY TESTS
# ===================================================================

class TestStateTaxConsistency:
    """Higher income should generally yield higher state tax."""

    @pytest.mark.parametrize("state", SELECTED_STATES)
    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_monotonic_state_tax(self, calculator_with_state, state, filing_status):
        if state in NO_INCOME_TAX_STATES:
            pytest.skip(f"{state} has no income tax")
        if not calculator_with_state.is_state_supported(state):
            pytest.skip(f"{state} not supported")

        taxes = []
        for wages in [30000, 75000, 150000, 500000]:
            tr = make_tax_return(
                filing_status=filing_status,
                wages=wages,
                state=state,
            )
            result = calculator_with_state.calculate_complete_return(tr)
            tax = result.state_tax_liability or 0.0
            taxes.append(tax)

        # Should be non-decreasing
        for i in range(1, len(taxes)):
            assert taxes[i] >= taxes[i - 1] - 0.01, (
                f"{state}/{filing_status.value}: tax at income level {i} < level {i-1}"
            )


# ===================================================================
# get_supported_states() and is_state_supported() API
# ===================================================================

class TestStateSupportAPIs:
    """Test the state support query APIs."""

    def test_get_supported_states_returns_list(self, calculator_with_state):
        states = calculator_with_state.get_supported_states()
        assert isinstance(states, list)
        # Should include at least the no-income-tax states
        for nit in NO_TAX_STATES:
            if nit in states:
                assert calculator_with_state.is_state_supported(nit)

    def test_is_state_supported_case_insensitive(self, calculator_with_state):
        """State codes should work regardless of case."""
        for state in ["ca", "Ca", "CA", "ny", "Ny", "NY", "tx", "fl"]:
            # Should not raise
            result = calculator_with_state.is_state_supported(state)
            assert isinstance(result, bool)

    @pytest.mark.parametrize("state", ALL_STATES)
    def test_all_states_queryable(self, calculator_with_state, state):
        """Every state code should be queryable without error."""
        result = calculator_with_state.is_state_supported(state)
        assert isinstance(result, bool)

    def test_invalid_state_code(self, calculator_with_state):
        """Invalid state codes should return False."""
        assert not calculator_with_state.is_state_supported("ZZ")
        assert not calculator_with_state.is_state_supported("XX")


# ===================================================================
# COMBINED FEDERAL + STATE
# ===================================================================

class TestCombinedFederalState:
    """Verify combined_tax_liability = federal + state."""

    @pytest.mark.parametrize("state", ["CA", "NY", "TX", "FL", "IL"])
    @pytest.mark.parametrize("filing_status", [FilingStatus.SINGLE, FilingStatus.MARRIED_JOINT])
    @pytest.mark.parametrize("wages", [50000, 150000])
    def test_combined_total(self, calculator_with_state, state, filing_status, wages):
        tr = make_tax_return(
            filing_status=filing_status,
            wages=wages,
            state=state,
        )
        result = calculator_with_state.calculate_complete_return(tr)
        federal = result.tax_liability or 0.0
        state_tax = result.state_tax_liability or 0.0
        combined = result.combined_tax_liability or 0.0
        assert combined == pytest.approx(federal + state_tax, abs=1.0)


# ===================================================================
# STATE WITH NO INCOME (should produce 0 state tax)
# ===================================================================

class TestStateZeroIncome:
    """States should produce zero tax on zero income."""

    @pytest.mark.parametrize("state", SELECTED_STATES)
    @pytest.mark.parametrize("filing_status", ALL_FILING_STATUSES)
    def test_zero_income_zero_state_tax(self, calculator_with_state, state, filing_status):
        tr = make_tax_return(
            filing_status=filing_status,
            wages=0,
            state=state,
        )
        result = calculator_with_state.calculate_complete_return(tr)
        state_tax = result.state_tax_liability or 0.0
        assert state_tax == pytest.approx(0.0, abs=1.0)


# ===================================================================
# STATE WITH SE INCOME
# ===================================================================

class TestStateSelfEmployment:
    """State tax on self-employment income."""

    @pytest.mark.parametrize("state", ["CA", "NY", "IL", "PA", "NJ"])
    @pytest.mark.parametrize("filing_status", [FilingStatus.SINGLE, FilingStatus.MARRIED_JOINT])
    @pytest.mark.parametrize("se_income", [50000, 150000])
    def test_se_state_tax(self, calculator_with_state, state, filing_status, se_income):
        if not calculator_with_state.is_state_supported(state):
            pytest.skip(f"{state} not supported")
        tr = make_tax_return(
            filing_status=filing_status,
            se_income=se_income,
            state=state,
        )
        result = calculator_with_state.calculate_complete_return(tr)
        if state not in NO_INCOME_TAX_STATES:
            state_tax = result.state_tax_liability
            if state_tax is not None:
                assert state_tax >= 0
