"""Tests for AsyncTaxReturnService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from services.async_tax_return_service import AsyncTaxReturnService, CalculationResult
from domain.repositories import IUnitOfWork, ITaxReturnRepository
from calculator.engine import CalculationBreakdown


# Test UUID to use consistently
TEST_RETURN_ID = "12345678-1234-5678-1234-567812345678"
TEST_SESSION_ID = "test-session-id"


def create_mock_breakdown():
    """Create a fully mocked CalculationBreakdown with all required attributes."""
    mock_breakdown = MagicMock(spec=CalculationBreakdown)
    mock_breakdown.agi = 75000
    mock_breakdown.taxable_income = 60000
    mock_breakdown.total_tax = 10000
    mock_breakdown.total_credits = 2000
    mock_breakdown.total_payments = 12000
    mock_breakdown.refund_or_owed = 2000
    mock_breakdown.gross_income = 75000
    mock_breakdown.adjustments_to_income = 0
    mock_breakdown.deduction_type = "standard"
    mock_breakdown.deduction_amount = 15000
    mock_breakdown.ordinary_income_tax = 10000
    mock_breakdown.preferential_income_tax = 0
    mock_breakdown.self_employment_tax = 0
    mock_breakdown.total_tax_before_credits = 10000
    mock_breakdown.nonrefundable_credits = 1000
    mock_breakdown.refundable_credits = 1000
    mock_breakdown.effective_tax_rate = 0.133
    mock_breakdown.schedule_a_total_deductions = 0
    mock_breakdown.schedule_d_net_gain_loss = 0
    mock_breakdown.qbi_deduction = 0
    mock_breakdown.alternative_minimum_tax = 0
    mock_breakdown.form_1116_ftc_allowed = 0
    mock_breakdown.new_st_loss_carryforward = 0
    mock_breakdown.new_lt_loss_carryforward = 0
    return mock_breakdown


class TestAsyncTaxReturnService:
    """Tests for AsyncTaxReturnService class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock unit of work
        self.mock_uow = MagicMock(spec=IUnitOfWork)
        self.mock_tax_returns = AsyncMock(spec=ITaxReturnRepository)
        self.mock_uow.tax_returns = self.mock_tax_returns
        self.mock_uow.collect_event = MagicMock()

        # Mock engines
        self.mock_federal_engine = MagicMock()
        self.mock_state_engine = MagicMock()

        # Create service
        self.service = AsyncTaxReturnService(
            unit_of_work=self.mock_uow,
            federal_engine=self.mock_federal_engine,
            state_engine=self.mock_state_engine,
        )

    @pytest.mark.asyncio
    async def test_create_return_success(self):
        """Should create a new tax return."""
        self.mock_tax_returns.save = AsyncMock()

        return_id = await self.service.create_return(
            session_id=TEST_SESSION_ID,
            tax_year=2025
        )

        assert return_id is not None
        assert isinstance(UUID(return_id), UUID)
        self.mock_tax_returns.save.assert_called_once()
        self.mock_uow.collect_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_return_with_initial_data(self):
        """Should create return with provided initial data."""
        self.mock_tax_returns.save = AsyncMock()

        initial_data = {
            "taxpayer": {
                "filing_status": "married_joint",
                "first_name": "John",
                "last_name": "Doe",
            },
            "income": {"wages": 75000},
        }

        return_id = await self.service.create_return(
            session_id=TEST_SESSION_ID,
            tax_year=2025,
            initial_data=initial_data
        )

        # Verify save was called with the initial data
        call_args = self.mock_tax_returns.save.call_args
        saved_data = call_args[0][1]
        assert saved_data["taxpayer"]["first_name"] == "John"
        assert saved_data["tax_year"] == 2025

    @pytest.mark.asyncio
    async def test_get_return_success(self):
        """Should get a tax return by ID."""
        expected_data = {"return_id": TEST_RETURN_ID, "tax_year": 2025}
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=expected_data)

        result = await self.service.get_return(TEST_RETURN_ID)

        assert result == expected_data
        self.mock_tax_returns.get_by_id.assert_called_once_with(TEST_RETURN_ID)

    @pytest.mark.asyncio
    async def test_get_return_not_found(self):
        """Should return None if return not found."""
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=None)

        result = await self.service.get_return(TEST_RETURN_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_return_by_session(self):
        """Should get return by session ID."""
        expected_data = {"return_id": TEST_RETURN_ID, "session_id": TEST_SESSION_ID}
        self.mock_tax_returns.get_by_session = AsyncMock(return_value=expected_data)

        result = await self.service.get_return_by_session(TEST_SESSION_ID)

        assert result == expected_data
        self.mock_tax_returns.get_by_session.assert_called_once_with(TEST_SESSION_ID)

    @pytest.mark.asyncio
    async def test_update_return_success(self):
        """Should update a tax return."""
        existing = {
            "return_id": TEST_RETURN_ID,
            "tax_year": 2025,
            "taxpayer": {"first_name": "John", "last_name": "Doe", "filing_status": "single"},
            "income": {"w2_forms": [], "self_employment_income": 0},
            "deductions": {},
            "credits": {},
        }
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=existing.copy())
        self.mock_tax_returns.save = AsyncMock()

        # Mock calculation with full breakdown
        mock_breakdown = create_mock_breakdown()
        self.mock_federal_engine.calculate.return_value = mock_breakdown

        result = await self.service.update_return(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID,
            updates={"taxpayer": {"first_name": "Jane"}},
            recalculate=True
        )

        assert result is not None
        self.mock_tax_returns.save.assert_called()

    @pytest.mark.asyncio
    async def test_update_return_without_recalculate(self):
        """Should update without recalculating when recalculate=False."""
        existing = {
            "return_id": TEST_RETURN_ID,
            "tax_year": 2025,
            "taxpayer": {"first_name": "John", "last_name": "Doe", "filing_status": "single"},
            "income": {},
        }
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=existing.copy())
        self.mock_tax_returns.save = AsyncMock()

        result = await self.service.update_return(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID,
            updates={"taxpayer": {"first_name": "Jane"}},
            recalculate=False
        )

        assert result is not None
        self.mock_federal_engine.calculate.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_return_not_found(self):
        """Should return None if return not found for update."""
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=None)

        result = await self.service.update_return(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID,
            updates={"field": "value"}
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_return_success(self):
        """Should delete a tax return."""
        self.mock_tax_returns.delete = AsyncMock(return_value=True)

        result = await self.service.delete_return(TEST_RETURN_ID)

        assert result is True
        self.mock_tax_returns.delete.assert_called_once_with(TEST_RETURN_ID)

    @pytest.mark.asyncio
    async def test_calculate_success(self):
        """Should perform full tax calculation."""
        tax_return_data = {
            "return_id": TEST_RETURN_ID,
            "tax_year": 2025,
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "filing_status": "single",
            },
            "income": {
                "w2_forms": [],
                "self_employment_income": 0,
            },
            "deductions": {},
            "credits": {},
        }
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=tax_return_data.copy())
        self.mock_tax_returns.save = AsyncMock()

        mock_breakdown = create_mock_breakdown()
        self.mock_federal_engine.calculate.return_value = mock_breakdown

        result = await self.service.calculate(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID
        )

        assert result.success is True
        assert result.breakdown is not None
        assert result.breakdown.total_tax == 10000
        self.mock_uow.collect_event.assert_called()

    @pytest.mark.asyncio
    async def test_calculate_return_not_found(self):
        """Should return error if return not found."""
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=None)

        result = await self.service.calculate(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID
        )

        assert result.success is False
        assert "Tax return not found" in result.errors

    @pytest.mark.asyncio
    async def test_calculate_with_state_tax(self):
        """Should calculate state taxes if state specified."""
        tax_return_data = {
            "return_id": TEST_RETURN_ID,
            "tax_year": 2025,
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "filing_status": "single",
            },
            "income": {"w2_forms": [], "self_employment_income": 0},
            "deductions": {},
            "credits": {},
            "state_of_residence": "CA",
        }
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=tax_return_data.copy())
        self.mock_tax_returns.save = AsyncMock()

        mock_breakdown = create_mock_breakdown()
        self.mock_federal_engine.calculate.return_value = mock_breakdown

        state_result = {"tax_liability": 5000, "refund_or_owed": -5000}
        self.mock_state_engine.calculate.return_value = state_result

        result = await self.service.calculate(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID
        )

        assert result.success is True
        assert result.state_result is not None
        assert result.state_result["tax_liability"] == 5000
        self.mock_state_engine.calculate.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_handles_exception(self):
        """Should handle calculation exceptions gracefully."""
        tax_return_data = {
            "return_id": TEST_RETURN_ID,
            "tax_year": 2025,
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "filing_status": "single",
            },
            "income": {"w2_forms": [], "self_employment_income": 0},
            "deductions": {},
            "credits": {},
        }
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=tax_return_data.copy())
        self.mock_federal_engine.calculate.side_effect = Exception("Calculation error")

        result = await self.service.calculate(
            return_id=TEST_RETURN_ID,
            session_id=TEST_SESSION_ID
        )

        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_get_summary(self):
        """Should get tax return summary."""
        tax_return_data = {
            "return_id": TEST_RETURN_ID,
            "tax_year": 2025,
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "filing_status": "single",
            },
            "adjusted_gross_income": 75000,
            "taxable_income": 60000,
            "tax_liability": 10000,
            "total_payments": 12000,
            "refund_or_owed": 2000,
        }
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=tax_return_data)

        result = await self.service.get_summary(TEST_RETURN_ID)

        assert result is not None
        assert result["tax_year"] == 2025
        assert result["taxpayer_name"] == "John Doe"
        assert result["gross_income"] == 75000
        assert result["refund_or_owed"] == 2000

    @pytest.mark.asyncio
    async def test_get_summary_not_found(self):
        """Should return None for non-existent return."""
        self.mock_tax_returns.get_by_id = AsyncMock(return_value=None)

        result = await self.service.get_summary(TEST_RETURN_ID)

        assert result is None


class TestCalculationResult:
    """Tests for CalculationResult dataclass."""

    def test_init_with_defaults(self):
        """Should initialize with default values."""
        result = CalculationResult(success=True)

        assert result.success is True
        assert result.breakdown is None
        assert result.state_result is None
        assert result.errors == []
        assert result.warnings == []
        assert result.computation_time_ms == 0

    def test_init_with_values(self):
        """Should initialize with provided values."""
        breakdown = MagicMock()
        result = CalculationResult(
            success=True,
            breakdown=breakdown,
            errors=["error1"],
            warnings=["warning1"],
            computation_time_ms=100
        )

        assert result.breakdown is breakdown
        assert result.errors == ["error1"]
        assert result.warnings == ["warning1"]
        assert result.computation_time_ms == 100

    def test_post_init_creates_empty_lists(self):
        """Post-init should create empty lists for None values."""
        result = CalculationResult(success=False, errors=None, warnings=None)

        assert result.errors == []
        assert result.warnings == []
