"""Tests for async tax return repository."""

import pytest
import json
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from database.repositories.tax_return_repository import TaxReturnRepository


class TestTaxReturnRepositoryInit:
    """Tests for TaxReturnRepository initialization."""

    def test_init_with_session(self):
        """Should initialize with provided session."""
        mock_session = MagicMock()
        repo = TaxReturnRepository(mock_session)
        assert repo._session is mock_session


class TestTaxReturnRepositoryGet:
    """Tests for get method."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self):
        """Should return None when tax return doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_data_when_found(self):
        """Should return tax return data when found."""
        mock_session = AsyncMock()
        return_id = uuid4()

        # Mock row data matching the SELECT query columns
        mock_row = (
            str(return_id),  # return_id
            "session-123",  # session_id
            "John Doe",  # taxpayer_name
            2025,  # tax_year
            "single",  # filing_status
            "CA",  # state_code
            100000,  # gross_income
            90000,  # adjusted_gross_income
            75000,  # taxable_income
            15000,  # federal_tax_liability
            5000,  # state_tax_liability
            20000,  # combined_tax_liability
            -2000,  # federal_refund_or_owed
            -500,  # state_refund_or_owed
            -2500,  # combined_refund_or_owed
            "draft",  # status
            json.dumps({"taxpayer": {"first_name": "John"}}),  # return_data
            "2025-01-01T00:00:00",  # created_at
            "2025-01-15T00:00:00",  # updated_at
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get(return_id)

        assert result is not None
        assert result["return_id"] == str(return_id)
        assert result["taxpayer_name"] == "John Doe"
        assert result["tax_year"] == 2025
        assert result["status"] == "draft"
        assert "summary" in result
        assert result["summary"]["gross_income"] == 100000


class TestTaxReturnRepositorySave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_save_inserts_new_return(self):
        """Should insert when return doesn't exist."""
        mock_session = AsyncMock()
        return_id = uuid4()

        # Mock exists check to return False
        exists_result = MagicMock()
        exists_result.fetchone.return_value = None

        # Track execute calls
        mock_session.execute.return_value = exists_result

        repo = TaxReturnRepository(mock_session)

        tax_return_data = {
            "taxpayer": {
                "first_name": "Jane",
                "last_name": "Smith",
                "ssn": "123-45-6789",
                "filing_status": "single",
                "state_of_residence": "NY",
            },
            "income": {
                "total_income": 80000,
            },
            "calculation_result": {
                "agi": 75000,
                "taxable_income": 60000,
                "total_tax": 12000,
                "state_tax": 3000,
                "refund_or_owed": -1000,
                "state_refund_or_owed": -200,
            },
            "tax_year": 2025,
            "status": "draft",
        }

        await repo.save(return_id, tax_return_data)

        # Verify execute was called (at least for exists check and insert)
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_save_updates_existing_return(self):
        """Should update when return exists."""
        mock_session = AsyncMock()
        return_id = uuid4()

        # Mock exists check to return True
        exists_result = MagicMock()
        exists_result.fetchone.return_value = (1,)
        mock_session.execute.return_value = exists_result

        repo = TaxReturnRepository(mock_session)

        tax_return_data = {
            "taxpayer": {
                "first_name": "Jane",
                "last_name": "Smith",
            },
            "income": {},
            "calculation_result": {},
        }

        await repo.save(return_id, tax_return_data)

        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_save_handles_missing_taxpayer_data(self):
        """Should handle missing taxpayer data gracefully."""
        mock_session = AsyncMock()
        return_id = uuid4()

        exists_result = MagicMock()
        exists_result.fetchone.return_value = None
        mock_session.execute.return_value = exists_result

        repo = TaxReturnRepository(mock_session)

        # Minimal data
        tax_return_data = {}

        await repo.save(return_id, tax_return_data)

        # Should not raise, execute was called
        assert mock_session.execute.called


class TestTaxReturnRepositoryDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self):
        """Should return True when return was deleted."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.delete(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        """Should return False when return doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.delete(uuid4())

        assert result is False


class TestTaxReturnRepositoryExists:
    """Tests for exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_found(self):
        """Should return True when return exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.exists(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_not_found(self):
        """Should return False when return doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.exists(uuid4())

        assert result is False


class TestTaxReturnRepositoryGetByClient:
    """Tests for get_by_client method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_returns(self):
        """Should return empty list when no returns for client."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_by_client(uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_list_of_returns(self):
        """Should return list of tax returns for client."""
        mock_session = AsyncMock()

        mock_row = (
            str(uuid4()),
            "session-123",
            "John Doe",
            2025,
            "single",
            "CA",
            100000,
            90000,
            75000,
            15000,
            5000,
            20000,
            -2000,
            -500,
            -2500,
            "draft",
            json.dumps({}),
            "2025-01-01T00:00:00",
            "2025-01-15T00:00:00",
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_by_client(uuid4())

        assert len(result) == 1
        assert result[0]["tax_year"] == 2025


class TestTaxReturnRepositoryGetByYear:
    """Tests for get_by_year method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Should return None when no return for year."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_by_year(uuid4(), 2025)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_data_when_found(self):
        """Should return tax return data for specific year."""
        mock_session = AsyncMock()

        mock_row = (
            str(uuid4()),
            "session-123",
            "John Doe",
            2024,
            "single",
            "CA",
            100000,
            90000,
            75000,
            15000,
            5000,
            20000,
            -2000,
            -500,
            -2500,
            "filed",
            json.dumps({}),
            "2024-01-01T00:00:00",
            "2024-04-15T00:00:00",
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_by_year(uuid4(), 2024)

        assert result is not None
        assert result["tax_year"] == 2024


class TestTaxReturnRepositoryGetPriorYear:
    """Tests for get_prior_year method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_current_not_found(self):
        """Should return None when current return doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_prior_year(uuid4())

        assert result is None


class TestTaxReturnRepositoryListReturns:
    """Tests for list_returns method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_returns(self):
        """Should return empty list when no returns."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.list_returns()

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_by_tax_year(self):
        """Should filter by tax year when provided."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        await repo.list_returns(tax_year=2025)

        # Verify execute was called with correct params
        call_args = mock_session.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_filters_by_status(self):
        """Should filter by status when provided."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        await repo.list_returns(status="draft")

        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_respects_limit_and_offset(self):
        """Should respect limit and offset parameters."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        await repo.list_returns(limit=10, offset=20)

        assert mock_session.execute.called


class TestTaxReturnRepositoryGetCalculationResult:
    """Tests for get_calculation_result method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Should return None when return doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_calculation_result(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_calculation_result(self):
        """Should return calculation result from return data."""
        mock_session = AsyncMock()

        calculation = {"total_tax": 15000, "agi": 90000}
        mock_row = (
            str(uuid4()),
            "session-123",
            "John Doe",
            2025,
            "single",
            "CA",
            100000,
            90000,
            75000,
            15000,
            5000,
            20000,
            -2000,
            -500,
            -2500,
            "draft",
            json.dumps({"calculation_result": calculation}),
            "2025-01-01T00:00:00",
            "2025-01-15T00:00:00",
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_calculation_result(uuid4())

        assert result is not None
        assert result["total_tax"] == 15000


class TestTaxReturnRepositoryGetBySession:
    """Tests for get_by_session method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Should return None when no return for session."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_by_session("session-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_data_when_found(self):
        """Should return tax return data for session."""
        mock_session = AsyncMock()

        mock_row = (
            str(uuid4()),
            "session-xyz",
            "John Doe",
            2025,
            "single",
            "CA",
            100000,
            90000,
            75000,
            15000,
            5000,
            20000,
            -2000,
            -500,
            -2500,
            "draft",
            json.dumps({}),
            "2025-01-01T00:00:00",
            "2025-01-15T00:00:00",
        )

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get_by_session("session-xyz")

        assert result is not None
        assert result["session_id"] == "session-xyz"


class TestTaxReturnRepositoryRowToDict:
    """Tests for _row_to_dict helper method."""

    def test_returns_none_for_none_row(self):
        """Should return None for None row."""
        mock_session = MagicMock()
        repo = TaxReturnRepository(mock_session)
        result = repo._row_to_dict(None)
        assert result is None

    def test_parses_json_return_data(self):
        """Should parse JSON return_data field."""
        mock_session = MagicMock()
        repo = TaxReturnRepository(mock_session)

        inner_data = {"taxpayer": {"name": "Test"}}
        mock_row = (
            str(uuid4()),
            "session-123",
            "John Doe",
            2025,
            "single",
            "CA",
            100000,
            90000,
            75000,
            15000,
            5000,
            20000,
            -2000,
            -500,
            -2500,
            "draft",
            json.dumps(inner_data),
            "2025-01-01T00:00:00",
            "2025-01-15T00:00:00",
        )

        result = repo._row_to_dict(mock_row)

        assert result is not None
        assert "taxpayer" in result
        assert result["taxpayer"]["name"] == "Test"

    def test_adds_summary_values(self):
        """Should add summary values from row."""
        mock_session = MagicMock()
        repo = TaxReturnRepository(mock_session)

        mock_row = (
            str(uuid4()),
            "session-123",
            "John Doe",
            2025,
            "single",
            "CA",
            100000,  # gross_income
            90000,   # agi
            75000,   # taxable_income
            15000,   # federal_tax
            5000,    # state_tax
            20000,   # combined_tax
            -2000,   # federal_refund
            -500,    # state_refund
            -2500,   # combined_refund
            "draft",
            json.dumps({}),
            "2025-01-01T00:00:00",
            "2025-01-15T00:00:00",
        )

        result = repo._row_to_dict(mock_row)

        assert "summary" in result
        assert result["summary"]["gross_income"] == 100000
        assert result["summary"]["adjusted_gross_income"] == 90000
        assert result["summary"]["federal_tax_liability"] == 15000
