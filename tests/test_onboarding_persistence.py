"""
Tests for Onboarding Persistence Layer.

Tests database-backed persistence for interview state and documents
to verify Prompt 1 (Persistence Safety) compliance.
"""

import pytest
import tempfile
import uuid
from pathlib import Path
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestOnboardingPersistence:
    """Tests for OnboardingPersistence class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def persistence(self, temp_db):
        """Create persistence instance with temp database."""
        from database.onboarding_persistence import OnboardingPersistence
        return OnboardingPersistence(db_path=temp_db)

    def test_import(self):
        """Test module can be imported."""
        from database.onboarding_persistence import (
            OnboardingPersistence,
            InterviewStateRecord,
            DocumentRecord,
            get_onboarding_persistence
        )
        assert OnboardingPersistence is not None
        assert InterviewStateRecord is not None
        assert DocumentRecord is not None
        assert get_onboarding_persistence is not None

    def test_save_and_load_interview_state(self, persistence):
        """Test saving and loading interview state."""
        session_id = str(uuid.uuid4())

        # Save state
        persistence.save_interview_state(
            session_id=session_id,
            current_stage="personal_info",
            started_at="2025-01-17T10:00:00",
            last_activity="2025-01-17T10:30:00",
            is_complete=False,
            collected_data={"first_name": "John", "last_name": "Doe"},
            detected_forms=["W-2", "1099-INT"],
            estimated_refund=1500.50,
            progress_percentage=25.0,
            questionnaire_state={"current_group_index": 1, "answers": {"q1": "answer1"}}
        )

        # Load state
        record = persistence.load_interview_state(session_id)

        assert record is not None
        assert record.session_id == session_id
        assert record.current_stage == "personal_info"
        assert record.started_at == "2025-01-17T10:00:00"
        assert record.is_complete is False
        assert record.collected_data["first_name"] == "John"
        assert "W-2" in record.detected_forms
        assert record.estimated_refund == 1500.50
        assert record.progress_percentage == 25.0
        assert record.questionnaire_state["current_group_index"] == 1

    def test_update_interview_state(self, persistence):
        """Test updating existing interview state."""
        session_id = str(uuid.uuid4())

        # Initial save
        persistence.save_interview_state(
            session_id=session_id,
            current_stage="personal_info",
            started_at="2025-01-17T10:00:00",
            last_activity="2025-01-17T10:30:00",
            is_complete=False,
            collected_data={},
            detected_forms=[],
            estimated_refund=None,
            progress_percentage=0.0,
            questionnaire_state={}
        )

        # Update
        persistence.save_interview_state(
            session_id=session_id,
            current_stage="income",
            started_at="2025-01-17T10:00:00",
            last_activity="2025-01-17T11:00:00",
            is_complete=False,
            collected_data={"wages": 50000},
            detected_forms=["W-2"],
            estimated_refund=2000.0,
            progress_percentage=50.0,
            questionnaire_state={"current_group_index": 3}
        )

        # Verify update
        record = persistence.load_interview_state(session_id)
        assert record.current_stage == "income"
        assert record.progress_percentage == 50.0
        assert record.collected_data["wages"] == 50000

    def test_delete_interview_state(self, persistence):
        """Test deleting interview state."""
        session_id = str(uuid.uuid4())

        # Save
        persistence.save_interview_state(
            session_id=session_id,
            current_stage="welcome",
            started_at=None,
            last_activity=None,
            is_complete=False,
            collected_data={},
            detected_forms=[],
            estimated_refund=None,
            progress_percentage=0.0,
            questionnaire_state={}
        )

        # Delete
        result = persistence.delete_interview_state(session_id)
        assert result is True

        # Verify deleted
        record = persistence.load_interview_state(session_id)
        assert record is None

    def test_load_nonexistent_interview_state(self, persistence):
        """Test loading non-existent session returns None."""
        record = persistence.load_interview_state("nonexistent-session-id")
        assert record is None


class TestDocumentPersistence:
    """Tests for document persistence."""

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
        from database.onboarding_persistence import OnboardingPersistence
        return OnboardingPersistence(db_path=temp_db)

    def test_save_and_load_document(self, persistence):
        """Test saving and loading a document."""
        session_id = str(uuid.uuid4())
        document_id = "DOC-20250117-0001"

        # Save document
        persistence.save_document(
            document_id=document_id,
            session_id=session_id,
            document_type="W-2",
            status="extracted",
            filename="w2_2025.pdf",
            uploaded_at="2025-01-17T10:00:00",
            processed_at="2025-01-17T10:00:05",
            tax_year=2025,
            issuer_name="Acme Corp",
            issuer_ein="12-3456789",
            recipient_name="John Doe",
            overall_confidence=92.5,
            fields={
                "box_1": {
                    "field_name": "wages_tips",
                    "box_number": "Box 1",
                    "raw_value": "75000.00",
                    "parsed_value": 75000.00,
                    "confidence": 95.0,
                    "needs_review": False,
                    "validation_status": "valid",
                    "irs_mapping": "income.w2_wages"
                }
            },
            fields_needing_review=[],
            extraction_warnings=[],
            raw_text="Form W-2 Wage and Tax Statement..."
        )

        # Load document
        record = persistence.load_document(document_id)

        assert record is not None
        assert record.document_id == document_id
        assert record.session_id == session_id
        assert record.document_type == "W-2"
        assert record.status == "extracted"
        assert record.filename == "w2_2025.pdf"
        assert record.issuer_name == "Acme Corp"
        assert record.overall_confidence == 92.5
        assert "box_1" in record.fields
        assert record.fields["box_1"]["parsed_value"] == 75000.00

    def test_load_session_documents(self, persistence):
        """Test loading all documents for a session."""
        session_id = str(uuid.uuid4())

        # Save multiple documents
        for i in range(3):
            persistence.save_document(
                document_id=f"DOC-20250117-{i:04d}",
                session_id=session_id,
                document_type=["W-2", "1099-INT", "1099-DIV"][i],
                status="extracted",
                filename=f"doc_{i}.pdf"
            )

        # Load all
        documents = persistence.load_session_documents(session_id)

        assert len(documents) == 3
        types = {d.document_type for d in documents}
        assert "W-2" in types
        assert "1099-INT" in types
        assert "1099-DIV" in types

    def test_delete_document(self, persistence):
        """Test deleting a document."""
        session_id = str(uuid.uuid4())
        document_id = "DOC-20250117-9999"

        # Save
        persistence.save_document(
            document_id=document_id,
            session_id=session_id,
            document_type="W-2",
            status="pending"
        )

        # Delete
        result = persistence.delete_document(document_id)
        assert result is True

        # Verify deleted
        record = persistence.load_document(document_id)
        assert record is None

    def test_delete_session_documents(self, persistence):
        """Test deleting all documents for a session."""
        session_id = str(uuid.uuid4())

        # Save multiple documents
        for i in range(5):
            persistence.save_document(
                document_id=f"DOC-20250117-{i:04d}",
                session_id=session_id,
                document_type="W-2",
                status="pending"
            )

        # Delete all
        count = persistence.delete_session_documents(session_id)
        assert count == 5

        # Verify all deleted
        documents = persistence.load_session_documents(session_id)
        assert len(documents) == 0


class TestInterviewFlowPersistence:
    """Tests for InterviewFlow with persistence enabled."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    def test_interview_flow_with_session_id(self, temp_db, monkeypatch):
        """Test InterviewFlow persists state when session_id is provided."""
        from database.onboarding_persistence import OnboardingPersistence
        from onboarding.interview_flow import InterviewFlow

        # Create persistence with temp db
        persistence = OnboardingPersistence(db_path=temp_db)

        # Monkeypatch to use our temp persistence
        def mock_get_persistence():
            return persistence
        monkeypatch.setattr(
            "database.onboarding_persistence.get_onboarding_persistence",
            mock_get_persistence
        )

        session_id = str(uuid.uuid4())

        # Create interview flow with session
        flow = InterviewFlow(session_id=session_id)
        flow.start_interview()

        # Verify state was persisted
        record = persistence.load_interview_state(session_id)
        assert record is not None
        assert record.current_stage == "personal_info"

    def test_interview_flow_without_session_id(self):
        """Test InterviewFlow works without session_id (backward compatible)."""
        from onboarding.interview_flow import InterviewFlow

        # Should work without session_id
        flow = InterviewFlow()
        result = flow.start_interview()

        assert result["status"] == "started"
        assert "current_group" in result


class TestDocumentCollectorPersistence:
    """Tests for DocumentCollector with persistence enabled."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    def test_document_collector_with_session_id(self, temp_db, monkeypatch):
        """Test DocumentCollector persists documents when session_id provided."""
        from database.onboarding_persistence import OnboardingPersistence
        from onboarding.document_collector import DocumentCollector, DocumentType

        # Create persistence with temp db
        persistence = OnboardingPersistence(db_path=temp_db)

        # Monkeypatch to use our temp persistence
        def mock_get_persistence():
            return persistence
        monkeypatch.setattr(
            "database.onboarding_persistence.get_onboarding_persistence",
            mock_get_persistence
        )

        session_id = str(uuid.uuid4())

        # Create collector with session
        collector = DocumentCollector(session_id=session_id)
        doc_id = collector.generate_document_id()

        # Parse a document
        collector.parse_document(
            document_id=doc_id,
            document_type=DocumentType.W2,
            raw_text="Form W-2 Box 1 Wages: $50,000"
        )

        # Verify document was persisted
        records = persistence.load_session_documents(session_id)
        assert len(records) == 1
        assert records[0].document_type == "W-2"

    def test_document_collector_restores_on_init(self, temp_db, monkeypatch):
        """Test DocumentCollector restores documents on initialization."""
        from database.onboarding_persistence import OnboardingPersistence
        from onboarding.document_collector import DocumentCollector, DocumentType

        # Create persistence with temp db
        persistence = OnboardingPersistence(db_path=temp_db)

        # Monkeypatch
        def mock_get_persistence():
            return persistence
        monkeypatch.setattr(
            "database.onboarding_persistence.get_onboarding_persistence",
            mock_get_persistence
        )

        session_id = str(uuid.uuid4())

        # First collector - save a document
        collector1 = DocumentCollector(session_id=session_id)
        doc_id = collector1.generate_document_id()
        collector1.parse_document(
            document_id=doc_id,
            document_type=DocumentType.W2,
            raw_text="Form W-2 Box 1 Wages: $75,000"
        )

        # Second collector - should restore the document
        collector2 = DocumentCollector(session_id=session_id)
        docs = collector2.get_all_documents()

        assert len(docs) == 1
        assert docs[0].document_id == doc_id
        assert docs[0].document_type == DocumentType.W2

    def test_document_collector_without_session_id(self):
        """Test DocumentCollector works without session_id (backward compatible)."""
        from onboarding.document_collector import DocumentCollector, DocumentType

        # Should work without session_id
        collector = DocumentCollector()
        doc_id = collector.generate_document_id()
        doc = collector.parse_document(
            document_id=doc_id,
            document_type=DocumentType.W2,
            raw_text="Form W-2"
        )

        assert doc is not None
        assert doc.document_id == doc_id
