"""
Tests for Session Persistence Layer.

Tests database-backed persistence for web session state
including sessions, documents, and tax returns.
"""

import pytest
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSessionPersistence:
    """Tests for session state persistence."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def persistence(self, temp_db):
        """Create persistence instance with temp database."""
        from database.session_persistence import SessionPersistence
        return SessionPersistence(db_path=temp_db, ttl_hours=1)

    def test_import(self):
        """Test module can be imported."""
        from database.session_persistence import (
            SessionPersistence,
            SessionRecord,
            DocumentProcessingRecord,
            get_session_persistence,
        )
        assert SessionPersistence is not None
        assert SessionRecord is not None
        assert DocumentProcessingRecord is not None
        assert get_session_persistence is not None

    def test_save_and_load_session(self, persistence):
        """Test saving and loading a session."""
        session_id = str(uuid.uuid4())
        tenant_id = "test-tenant"

        persistence.save_session(
            session_id=session_id,
            tenant_id=tenant_id,
            session_type="agent",
            data={"conversation": ["Hello", "Hi there"]},
            metadata={"source": "web"}
        )

        record = persistence.load_session(session_id)

        assert record is not None
        assert record.session_id == session_id
        assert record.tenant_id == tenant_id
        assert record.session_type == "agent"
        assert record.data["conversation"] == ["Hello", "Hi there"]

    def test_session_tenant_isolation(self, persistence):
        """Test that sessions are isolated by tenant."""
        session_id = str(uuid.uuid4())

        persistence.save_session(
            session_id=session_id,
            tenant_id="tenant-a",
            data={"value": "tenant-a-data"}
        )

        # Can load with correct tenant
        record = persistence.load_session(session_id, tenant_id="tenant-a")
        assert record is not None

        # Cannot load with wrong tenant
        record = persistence.load_session(session_id, tenant_id="tenant-b")
        assert record is None

    def test_session_expiry(self, temp_db):
        """Test that expired sessions are not returned."""
        from database.session_persistence import SessionPersistence
        # Very short TTL for testing
        persistence = SessionPersistence(db_path=temp_db, ttl_hours=0)

        session_id = str(uuid.uuid4())
        persistence.save_session(session_id=session_id)

        # Session should be expired immediately
        import time
        time.sleep(0.1)

        record = persistence.load_session(session_id)
        assert record is None

    def test_touch_session_extends_expiry(self, persistence):
        """Test that touch_session extends the session expiry."""
        session_id = str(uuid.uuid4())
        persistence.save_session(session_id=session_id)

        result = persistence.touch_session(session_id)
        assert result is True

        record = persistence.load_session(session_id)
        assert record is not None

    def test_delete_session_cascades(self, persistence):
        """Test that deleting a session deletes related data."""
        session_id = str(uuid.uuid4())

        # Create session with documents and tax return
        persistence.save_session(session_id=session_id)
        persistence.save_document_result(
            document_id=f"doc-{session_id}",
            session_id=session_id,
            result={"type": "W-2"}
        )
        persistence.save_session_tax_return(
            session_id=session_id,
            return_data={"wages": 50000}
        )

        # Delete session
        result = persistence.delete_session(session_id)
        assert result is True

        # Verify cascade deletion
        assert persistence.load_session(session_id) is None
        assert persistence.load_document_result(f"doc-{session_id}") is None
        assert persistence.load_session_tax_return(session_id) is None

    def test_list_sessions_by_tenant(self, persistence):
        """Test listing sessions for a tenant."""
        tenant_id = "test-tenant"

        for i in range(3):
            persistence.save_session(
                session_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                data={"index": i}
            )

        # Add session for different tenant
        persistence.save_session(
            session_id=str(uuid.uuid4()),
            tenant_id="other-tenant"
        )

        sessions = persistence.list_sessions(tenant_id)
        assert len(sessions) == 3

    def test_cleanup_expired_sessions(self, temp_db):
        """Test cleanup of expired sessions."""
        from database.session_persistence import SessionPersistence
        persistence = SessionPersistence(db_path=temp_db, ttl_hours=0)

        # Create sessions
        for i in range(5):
            persistence.save_session(session_id=str(uuid.uuid4()))

        import time
        time.sleep(0.1)

        # Cleanup
        count = persistence.cleanup_expired_sessions()
        assert count == 5


class TestDocumentProcessingPersistence:
    """Tests for document processing result persistence."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def persistence(self, temp_db):
        """Create persistence instance with temp database."""
        from database.session_persistence import SessionPersistence
        return SessionPersistence(db_path=temp_db)

    def test_save_and_load_document_result(self, persistence):
        """Test saving and loading document results."""
        session_id = str(uuid.uuid4())
        document_id = f"doc-{uuid.uuid4()}"

        persistence.save_session(session_id=session_id)
        persistence.save_document_result(
            document_id=document_id,
            session_id=session_id,
            tenant_id="test-tenant",
            document_type="W-2",
            status="completed",
            result={
                "fields": {"box1": 75000, "box2": 15000},
                "confidence": 95.5
            }
        )

        record = persistence.load_document_result(document_id)

        assert record is not None
        assert record.document_id == document_id
        assert record.document_type == "W-2"
        assert record.status == "completed"
        assert record.result["fields"]["box1"] == 75000

    def test_document_session_isolation(self, persistence):
        """Test that documents are isolated by session."""
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())
        document_id = f"doc-{uuid.uuid4()}"

        persistence.save_session(session_id=session_a)
        persistence.save_document_result(
            document_id=document_id,
            session_id=session_a
        )

        # Can load with correct session
        record = persistence.load_document_result(document_id, session_id=session_a)
        assert record is not None

        # Cannot load with wrong session
        record = persistence.load_document_result(document_id, session_id=session_b)
        assert record is None

    def test_list_session_documents(self, persistence):
        """Test listing documents for a session."""
        session_id = str(uuid.uuid4())
        persistence.save_session(session_id=session_id)

        for i, doc_type in enumerate(["W-2", "1099-INT", "1099-DIV"]):
            persistence.save_document_result(
                document_id=f"doc-{i}",
                session_id=session_id,
                document_type=doc_type
            )

        documents = persistence.list_session_documents(session_id)
        assert len(documents) == 3


class TestTaxReturnPersistence:
    """Tests for session tax return persistence."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def persistence(self, temp_db):
        """Create persistence instance with temp database."""
        from database.session_persistence import SessionPersistence
        return SessionPersistence(db_path=temp_db)

    def test_save_and_load_tax_return(self, persistence):
        """Test saving and loading tax return data."""
        session_id = str(uuid.uuid4())

        persistence.save_session(session_id=session_id)
        persistence.save_session_tax_return(
            session_id=session_id,
            tenant_id="test-tenant",
            tax_year=2025,
            return_data={
                "wages": 75000,
                "interest": 500,
                "dividends": 200
            },
            calculated_results={
                "agi": 75700,
                "taxable_income": 60700,
                "total_tax": 8500
            }
        )

        data = persistence.load_session_tax_return(session_id)

        assert data is not None
        assert data["tax_year"] == 2025
        assert data["return_data"]["wages"] == 75000
        assert data["calculated_results"]["total_tax"] == 8500

    def test_tax_return_update(self, persistence):
        """Test updating tax return data."""
        session_id = str(uuid.uuid4())
        persistence.save_session(session_id=session_id)

        # Initial save
        persistence.save_session_tax_return(
            session_id=session_id,
            return_data={"wages": 50000}
        )

        # Update
        persistence.save_session_tax_return(
            session_id=session_id,
            return_data={"wages": 75000, "interest": 500}
        )

        data = persistence.load_session_tax_return(session_id)
        assert data["return_data"]["wages"] == 75000
        assert data["return_data"]["interest"] == 500
