"""Tests for _build_tax_context helper in chat_routes."""

import pytest
from unittest.mock import patch, MagicMock


# We need to import the function under test.
# chat_routes lives in src/web/routes/chat_routes.py
from web.routes.chat_routes import _build_tax_context


MOCK_SESSION_DATA_WITH_TAX = {
    "session_id": "test-session-123",
    "tax_computation": {
        "filing_status": "married_filing_jointly",
        "agi": 125000,
        "total_tax": 18750,
        "effective_rate": 15.0,
        "potential_savings": 3200,
    },
}

MOCK_SESSION_DATA_NO_TAX = {
    "session_id": "test-session-456",
}

MOCK_SESSION_DATA_EMPTY_TAX = {
    "session_id": "test-session-789",
    "tax_computation": {},
}


@patch("web.routes.chat_routes.SessionPersistence", create=True)
def test_returns_tax_context_when_data_present(mock_persistence_cls):
    """Returns tax context string when session has tax_computation data."""
    mock_instance = MagicMock()
    mock_instance.load_session_state.return_value = MOCK_SESSION_DATA_WITH_TAX
    mock_persistence_cls.return_value = mock_instance

    with patch("database.session_persistence.SessionPersistence", mock_persistence_cls):
        result = _build_tax_context("test-session-123")

    assert "[Tax Context" in result
    assert "married_filing_jointly" in result
    assert "$125,000" in result
    assert "$18,750" in result
    assert "15.0%" in result
    assert "$3,200" in result


def test_returns_empty_string_when_session_id_is_none():
    """Returns empty string when session_id is None."""
    result = _build_tax_context(None)
    assert result == ""


def test_returns_empty_string_when_session_id_is_empty():
    """Returns empty string when session_id is empty string."""
    result = _build_tax_context("")
    assert result == ""


@patch("database.session_persistence.SessionPersistence")
def test_returns_empty_string_when_no_tax_computation(mock_persistence_cls):
    """Returns empty string when session has no tax_computation."""
    mock_instance = MagicMock()
    mock_instance.load_session_state.return_value = MOCK_SESSION_DATA_NO_TAX
    mock_persistence_cls.return_value = mock_instance

    result = _build_tax_context("test-session-456")
    assert result == ""


@patch("database.session_persistence.SessionPersistence")
def test_returns_empty_string_when_tax_computation_is_empty(mock_persistence_cls):
    """Returns empty string when tax_computation dict is empty."""
    mock_instance = MagicMock()
    mock_instance.load_session_state.return_value = MOCK_SESSION_DATA_EMPTY_TAX
    mock_persistence_cls.return_value = mock_instance

    result = _build_tax_context("test-session-789")
    assert result == ""


@patch("database.session_persistence.SessionPersistence")
def test_returns_empty_string_when_persistence_raises(mock_persistence_cls):
    """Returns empty string when SessionPersistence raises an exception (graceful failure)."""
    mock_persistence_cls.side_effect = RuntimeError("DB connection failed")

    result = _build_tax_context("test-session-error")
    assert result == ""


@patch("database.session_persistence.SessionPersistence")
def test_returns_empty_string_when_load_returns_none(mock_persistence_cls):
    """Returns empty string when load_session_state returns None."""
    mock_instance = MagicMock()
    mock_instance.load_session_state.return_value = None
    mock_persistence_cls.return_value = mock_instance

    result = _build_tax_context("test-session-none")
    assert result == ""


@patch("database.session_persistence.SessionPersistence")
def test_context_contains_key_fields(mock_persistence_cls):
    """Verify the context string contains key fields: filing_status, AGI, total_tax."""
    mock_instance = MagicMock()
    mock_instance.load_session_state.return_value = MOCK_SESSION_DATA_WITH_TAX
    mock_persistence_cls.return_value = mock_instance

    result = _build_tax_context("test-session-123")

    assert "Filing Status:" in result
    assert "AGI:" in result
    assert "Total Tax:" in result
    assert "Effective Rate:" in result


@patch("database.session_persistence.SessionPersistence")
def test_omits_potential_savings_when_zero(mock_persistence_cls):
    """Does not include Potential Savings line when value is 0."""
    data = {
        "tax_computation": {
            "filing_status": "single",
            "agi": 50000,
            "total_tax": 6000,
            "effective_rate": 12.0,
            "potential_savings": 0,
        },
    }
    mock_instance = MagicMock()
    mock_instance.load_session_state.return_value = data
    mock_persistence_cls.return_value = mock_instance

    result = _build_tax_context("test-session-no-savings")
    assert "Potential Savings" not in result
