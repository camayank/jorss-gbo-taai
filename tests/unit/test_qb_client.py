"""
Unit tests for QuickBooks API client wrapper (Task 3).

Tests cover:
- Profit & Loss report fetching
- Account list querying
- Journal entry retrieval
- Error handling (401, 429, 400, timeout, connection)
- Header construction
- Fault message extraction
- Account normalization
- Journal entry normalization
- Sandbox/production base URL selection
"""

import os
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from src.integrations.quickbooks.client import (
    QuickBooksAPIClient,
    QBAPIError,
    QBAuthError,
    QBRateLimitError,
    QBBadRequestError,
    get_quickbooks_api_client,
    _api_base,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Provide a QB API client instance."""
    return QuickBooksAPIClient()


@pytest.fixture
def mock_realm_id():
    """Sample QB realm ID."""
    return "9341452714377780"


@pytest.fixture
def mock_token():
    """Sample Bearer token."""
    return "eyJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwiYWxnIjoiZGlyIn0..."


@pytest.fixture
def mock_date_range():
    """Sample date range."""
    return {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }


# ---------------------------------------------------------------------------
# Tests: _api_base() function
# ---------------------------------------------------------------------------

def test_api_base_production_default():
    """Test that production URL is default when QB_ENVIRONMENT is not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert _api_base() == "https://quickbooks.api.intuit.com"


def test_api_base_sandbox_env():
    """Test that sandbox URL is used when QB_ENVIRONMENT='sandbox'."""
    with patch.dict(os.environ, {"QB_ENVIRONMENT": "sandbox"}):
        assert _api_base() == "https://sandbox-quickbooks.api.intuit.com"


def test_api_base_production_explicit():
    """Test that production URL is used when QB_ENVIRONMENT='production'."""
    with patch.dict(os.environ, {"QB_ENVIRONMENT": "production"}):
        assert _api_base() == "https://quickbooks.api.intuit.com"


def test_api_base_case_insensitive():
    """Test that QB_ENVIRONMENT check is case-insensitive."""
    with patch.dict(os.environ, {"QB_ENVIRONMENT": "SANDBOX"}):
        assert _api_base() == "https://sandbox-quickbooks.api.intuit.com"


# ---------------------------------------------------------------------------
# Tests: _build_headers()
# ---------------------------------------------------------------------------

def test_build_headers(client, mock_token):
    """Test that _build_headers constructs Bearer token correctly."""
    headers = client._build_headers(mock_token)
    assert headers["Authorization"] == f"Bearer {mock_token}"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"


def test_build_headers_with_empty_token(client):
    """Test that _build_headers works with empty token (edge case)."""
    headers = client._build_headers("")
    assert headers["Authorization"] == "Bearer "


# ---------------------------------------------------------------------------
# Tests: _extract_fault_message()
# ---------------------------------------------------------------------------

def test_extract_fault_message_with_valid_fault(client):
    """Test extraction of error message from QB Fault envelope."""
    raw = json.dumps({
        "Fault": {
            "Error": [
                {"Message": "Token expired", "code": "401"}
            ],
            "type": "AuthenticationFault"
        }
    })
    msg = client._extract_fault_message(raw)
    assert msg == "Token expired"


def test_extract_fault_message_with_multiple_errors(client):
    """Test extraction when multiple errors present (returns first)."""
    raw = json.dumps({
        "Fault": {
            "Error": [
                {"Message": "First error", "code": "400"},
                {"Message": "Second error", "code": "400"},
            ]
        }
    })
    msg = client._extract_fault_message(raw)
    assert msg == "First error"


def test_extract_fault_message_with_invalid_json(client):
    """Test extraction with invalid JSON returns truncated raw."""
    raw = "Not valid JSON at all"
    msg = client._extract_fault_message(raw)
    assert msg == raw[:200]


def test_extract_fault_message_with_missing_fault(client):
    """Test extraction when Fault key missing."""
    raw = json.dumps({"SomeOtherKey": "value"})
    msg = client._extract_fault_message(raw)
    assert msg == raw[:200]


# ---------------------------------------------------------------------------
# Tests: _raise_for_status()
# ---------------------------------------------------------------------------

def test_raise_for_status_200_ok(client):
    """Test that 200 status does not raise."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    # Should not raise
    client._raise_for_status(response)


def test_raise_for_status_401_raises_auth_error(client):
    """Test that 401 raises QBAuthError."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = json.dumps({
        "Fault": {"Error": [{"Message": "Invalid token"}]}
    })
    with pytest.raises(QBAuthError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value)


def test_raise_for_status_429_raises_rate_limit_error(client):
    """Test that 429 raises QBRateLimitError."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 429
    response.text = "{}"
    with pytest.raises(QBRateLimitError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 429


def test_raise_for_status_400_raises_bad_request_error(client):
    """Test that 400 raises QBBadRequestError."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 400
    response.text = json.dumps({
        "Fault": {"Error": [{"Message": "Invalid query"}]}
    })
    with pytest.raises(QBBadRequestError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 400


def test_raise_for_status_500_raises_generic_error(client):
    """Test that 500 raises generic QBAPIError."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 500
    response.text = "Internal server error"
    with pytest.raises(QBAPIError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Tests: get_profit_loss_report()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_profit_loss_report_success(client, mock_realm_id, mock_token, mock_date_range):
    """Test successful P&L report fetch."""
    expected_response = {
        "Report": [
            {"Name": "ProfitAndLoss", "Value": "2024-01-01"}
        ]
    }

    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_profit_loss_report(
            realm_id=mock_realm_id,
            access_token=mock_token,
            **mock_date_range
        )

        assert result == expected_response
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert f"/v3/company/{mock_realm_id}/reports/ProfitAndLoss" in call_args[0][0]
        assert mock_date_range["start_date"] in str(call_args)


@pytest.mark.asyncio
async def test_get_profit_loss_report_timeout(client, mock_realm_id, mock_token, mock_date_range):
    """Test that timeout raises QBAPIError."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with pytest.raises(QBAPIError, match="timed out"):
            await client.get_profit_loss_report(
                realm_id=mock_realm_id,
                access_token=mock_token,
                **mock_date_range
            )


@pytest.mark.asyncio
async def test_get_profit_loss_report_connection_error(client, mock_realm_id, mock_token, mock_date_range):
    """Test that connection error raises QBAPIError."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with pytest.raises(QBAPIError, match="Cannot connect"):
            await client.get_profit_loss_report(
                realm_id=mock_realm_id,
                access_token=mock_token,
                **mock_date_range
            )


@pytest.mark.asyncio
async def test_get_profit_loss_report_401_error(client, mock_realm_id, mock_token, mock_date_range):
    """Test that 401 response raises QBAuthError."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = json.dumps({
            "Fault": {"Error": [{"Message": "Invalid token"}]}
        })
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with pytest.raises(QBAuthError):
            await client.get_profit_loss_report(
                realm_id=mock_realm_id,
                access_token=mock_token,
                **mock_date_range
            )


# ---------------------------------------------------------------------------
# Tests: get_accounts()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_accounts_all(client, mock_realm_id, mock_token):
    """Test fetching all accounts without type filter."""
    expected_accounts = [
        {
            "Id": "1",
            "Name": "Checking Account",
            "AccountType": "Bank",
            "AccountSubType": "Cash",
            "CurrentBalance": 5000.0,
            "Active": True,
            "CurrencyRef": {"value": "USD"}
        },
        {
            "Id": "2",
            "Name": "Sales Revenue",
            "AccountType": "Income",
            "AccountSubType": "Income",
            "CurrentBalance": 50000.0,
            "Active": True,
            "CurrencyRef": {"value": "USD"}
        }
    ]

    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "QueryResponse": {"Account": expected_accounts}
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_accounts(
            realm_id=mock_realm_id,
            access_token=mock_token,
        )

        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[0]["name"] == "Checking Account"
        assert result[0]["current_balance"] == 5000.0
        assert result[1]["account_type"] == "Income"


@pytest.mark.asyncio
async def test_get_accounts_filtered_by_type(client, mock_realm_id, mock_token):
    """Test fetching accounts filtered by type."""
    expected_accounts = [
        {
            "Id": "1",
            "Name": "Checking Account",
            "AccountType": "Bank",
            "AccountSubType": "Cash",
            "CurrentBalance": 5000.0,
            "Active": True,
            "CurrencyRef": {"value": "USD"}
        }
    ]

    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "QueryResponse": {"Account": expected_accounts}
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_accounts(
            realm_id=mock_realm_id,
            access_token=mock_token,
            account_type="Bank"
        )

        assert len(result) == 1
        assert result[0]["account_type"] == "Bank"
        # Verify the query included the type filter
        call_args = mock_client.get.call_args
        assert "Bank" in str(call_args)


@pytest.mark.asyncio
async def test_get_accounts_empty_result(client, mock_realm_id, mock_token):
    """Test fetching accounts when none exist."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "QueryResponse": {"Account": []}
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_accounts(
            realm_id=mock_realm_id,
            access_token=mock_token,
        )

        assert result == []


@pytest.mark.asyncio
async def test_get_accounts_missing_query_response(client, mock_realm_id, mock_token):
    """Test fetching accounts when QueryResponse key missing."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_accounts(
            realm_id=mock_realm_id,
            access_token=mock_token,
        )

        assert result == []


@pytest.mark.asyncio
async def test_get_accounts_400_error(client, mock_realm_id, mock_token):
    """Test that 400 response raises QBBadRequestError."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = json.dumps({
            "Fault": {"Error": [{"Message": "Invalid query"}]}
        })
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with pytest.raises(QBBadRequestError):
            await client.get_accounts(
                realm_id=mock_realm_id,
                access_token=mock_token,
            )


# ---------------------------------------------------------------------------
# Tests: get_journal_entries()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_journal_entries_success(client, mock_realm_id, mock_token, mock_date_range):
    """Test successful journal entries fetch with normalized output."""
    expected_entries = [
        {
            "Id": "1",
            "TxnDate": "2024-06-15",
            "DocNumber": "001",
            "PrivateNote": "Monthly close",
            "SyncToken": "0",
            "MetaData": {
                "CreateTime": "2024-06-15T10:00:00Z",
                "LastUpdatedTime": "2024-06-15T10:00:00Z"
            },
            "Line": [
                {
                    "Id": "1",
                    "Description": "Revenue entry",
                    "Amount": 1000.0,
                    "JournalEntryLineDetail": {
                        "PostingType": "Credit",
                        "AccountRef": {"value": "2", "name": "Sales Revenue"}
                    }
                },
                {
                    "Id": "2",
                    "Description": None,
                    "Amount": 1000.0,
                    "JournalEntryLineDetail": {
                        "PostingType": "Debit",
                        "AccountRef": {"value": "1", "name": "Checking Account"}
                    }
                }
            ]
        }
    ]

    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "QueryResponse": {"JournalEntry": expected_entries}
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_journal_entries(
            realm_id=mock_realm_id,
            access_token=mock_token,
            **mock_date_range
        )

        assert len(result) == 1
        entry = result[0]
        assert entry["id"] == "1"
        assert entry["txn_date"] == "2024-06-15"
        assert entry["doc_number"] == "001"
        assert len(entry["lines"]) == 2
        assert entry["lines"][0]["posting_type"] == "Credit"
        assert entry["lines"][0]["amount"] == 1000.0
        assert entry["lines"][0]["account_name"] == "Sales Revenue"


@pytest.mark.asyncio
async def test_get_journal_entries_empty(client, mock_realm_id, mock_token, mock_date_range):
    """Test journal entries fetch with no results."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "QueryResponse": {}
        }
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await client.get_journal_entries(
            realm_id=mock_realm_id,
            access_token=mock_token,
            **mock_date_range
        )

        assert result == []


@pytest.mark.asyncio
async def test_get_journal_entries_429_error(client, mock_realm_id, mock_token, mock_date_range):
    """Test that 429 response raises QBRateLimitError."""
    with patch("src.integrations.quickbooks.client.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "{}"
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with pytest.raises(QBRateLimitError):
            await client.get_journal_entries(
                realm_id=mock_realm_id,
                access_token=mock_token,
                **mock_date_range
            )


# ---------------------------------------------------------------------------
# Tests: Normalizers
# ---------------------------------------------------------------------------

def test_normalize_account_complete(client):
    """Test account normalization with all fields."""
    raw = {
        "Id": "42",
        "Name": "Operating Expenses",
        "AccountType": "Expense",
        "AccountSubType": "Utilities",
        "CurrentBalance": 1234.56,
        "Active": True,
        "CurrencyRef": {"value": "GBP"}
    }
    normalized = client._normalize_account(raw)
    assert normalized["id"] == "42"
    assert normalized["name"] == "Operating Expenses"
    assert normalized["account_type"] == "Expense"
    assert normalized["current_balance"] == 1234.56
    assert normalized["currency"] == "GBP"


def test_normalize_account_with_missing_fields(client):
    """Test account normalization with missing optional fields."""
    raw = {
        "Id": "1",
        "Name": "Account"
    }
    normalized = client._normalize_account(raw)
    assert normalized["id"] == "1"
    assert normalized["current_balance"] == 0.0
    assert normalized["currency"] == "USD"


def test_normalize_journal_entry_with_multiple_lines(client):
    """Test journal entry normalization with multiple lines."""
    raw = {
        "Id": "je-1",
        "TxnDate": "2024-06-15",
        "DocNumber": "JE001",
        "PrivateNote": "Test entry",
        "SyncToken": "1",
        "MetaData": {
            "CreateTime": "2024-06-15T10:00:00Z",
            "LastUpdatedTime": "2024-06-15T11:00:00Z"
        },
        "Line": [
            {
                "Id": "line-1",
                "Description": "Debit",
                "Amount": 100.0,
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": "acc-1", "name": "Bank"}
                }
            },
            {
                "Id": "line-2",
                "Amount": 100.0,
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": "acc-2", "name": "Revenue"}
                }
            }
        ]
    }
    normalized = client._normalize_journal_entry(raw)
    assert normalized["id"] == "je-1"
    assert normalized["txn_date"] == "2024-06-15"
    assert len(normalized["lines"]) == 2
    assert normalized["lines"][0]["posting_type"] == "Debit"
    assert normalized["lines"][1]["description"] is None


def test_normalize_journal_entry_no_lines(client):
    """Test journal entry normalization with no lines."""
    raw = {
        "Id": "je-1",
        "TxnDate": "2024-06-15",
        "Line": []
    }
    normalized = client._normalize_journal_entry(raw)
    assert normalized["lines"] == []


# ---------------------------------------------------------------------------
# Tests: Singleton factory
# ---------------------------------------------------------------------------

def test_get_quickbooks_api_client_singleton():
    """Test that get_quickbooks_api_client returns a singleton."""
    client1 = get_quickbooks_api_client()
    client2 = get_quickbooks_api_client()
    assert client1 is client2


def test_get_quickbooks_api_client_returns_client():
    """Test that get_quickbooks_api_client returns a QuickBooksAPIClient instance."""
    client = get_quickbooks_api_client()
    assert isinstance(client, QuickBooksAPIClient)
