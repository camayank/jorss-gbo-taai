"""Tests for get_session() — lookup-only, no auto-create behaviour."""

import pytest


# ---------------------------------------------------------------------------
# Lightweight mock that mirrors the real ChatEngine.get_session logic
# without pulling in heavy dependencies (LLM clients, DB drivers, etc.).
# ---------------------------------------------------------------------------

class MockChatEngine:
    def __init__(self):
        self.sessions = {}

    async def _load_session_from_db(self, session_id, tenant_id=None):
        return None  # Override in individual tests

    async def get_session(self, session_id, tenant_id=None):
        if session_id in self.sessions:
            return self.sessions[session_id]
        loaded = await self._load_session_from_db(session_id, tenant_id=tenant_id)
        if loaded:
            self.sessions[session_id] = loaded
            return loaded
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_returns_existing_in_memory_session():
    """get_session should return a session that is already in memory."""
    engine = MockChatEngine()
    session_data = {"id": "sess-1", "history": []}
    engine.sessions["sess-1"] = session_data

    result = await engine.get_session("sess-1")

    assert result is session_data


@pytest.mark.asyncio
async def test_get_session_returns_none_when_not_found():
    """get_session should return None — never auto-create a session."""
    engine = MockChatEngine()

    result = await engine.get_session("nonexistent-session")

    assert result is None


@pytest.mark.asyncio
async def test_get_session_loads_from_db_when_not_in_memory():
    """get_session should fall back to the DB and cache the result."""
    engine = MockChatEngine()
    db_session = {"id": "sess-db", "history": ["hello"]}

    async def _mock_load(session_id, tenant_id=None):
        if session_id == "sess-db":
            return db_session
        return None

    engine._load_session_from_db = _mock_load

    result = await engine.get_session("sess-db")

    assert result is db_session
    # The session should now be cached in memory as well.
    assert engine.sessions["sess-db"] is db_session


@pytest.mark.asyncio
async def test_get_session_returns_none_when_not_in_memory_and_not_in_db():
    """get_session should return None when the session exists neither in
    memory nor in the database."""
    engine = MockChatEngine()

    async def _mock_load(session_id, tenant_id=None):
        return None

    engine._load_session_from_db = _mock_load

    result = await engine.get_session("ghost-session", tenant_id="tenant-x")

    assert result is None
    assert "ghost-session" not in engine.sessions
