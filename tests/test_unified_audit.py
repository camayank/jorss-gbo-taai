"""
Tests for the Unified Audit System.

Verifies that the consolidated audit service works correctly.
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from audit.unified import (
    AuditService,
    AuditEventType,
    AuditSeverity,
    AuditSource,
    UnifiedAuditEntry,
    ChangeRecord,
    InMemoryAuditStorage,
)


@pytest.fixture
def audit_service():
    """Create a fresh audit service with in-memory storage for testing."""
    storage = InMemoryAuditStorage()
    service = AuditService(storage)
    yield service
    AuditService.reset_instance()


@pytest.fixture
def sample_session_id():
    """Generate a sample session ID."""
    return "test-session-12345"


class TestUnifiedAuditEntry:
    """Tests for UnifiedAuditEntry."""

    def test_entry_creation(self):
        """Test basic entry creation."""
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
            session_id="session-1",
            user_id="user-1",
            action="update_wages",
            resource_type="income",
        )

        assert entry.entry_id is not None
        assert entry.timestamp is not None
        assert entry.event_type == AuditEventType.TAX_DATA_FIELD_CHANGE
        assert entry.session_id == "session-1"
        assert entry.signature_hash is not None

    def test_entry_integrity_verification(self):
        """Test that integrity verification works."""
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
            session_id="session-1",
            user_id="user-1",
        )

        # Entry should pass integrity check
        assert entry.verify_integrity() is True

        # Tampering should fail integrity check
        entry.user_id = "tampered-user"
        assert entry.verify_integrity() is False

    def test_entry_serialization(self):
        """Test entry to_dict and from_dict."""
        changes = [
            ChangeRecord(field_path="wages", old_value=0, new_value=50000)
        ]
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_DATA_INCOME_CHANGE,
            session_id="session-1",
            user_id="user-1",
            changes=changes,
        )

        # Serialize
        data = entry.to_dict()
        assert data["entry_id"] == entry.entry_id
        assert data["event_type"] == "tax.data.income_change"
        assert len(data["changes"]) == 1

        # Deserialize
        restored = UnifiedAuditEntry.from_dict(data)
        assert restored.entry_id == entry.entry_id
        assert restored.event_type == entry.event_type
        assert len(restored.changes) == 1
        assert restored.changes[0].field_path == "wages"


class TestChangeRecord:
    """Tests for ChangeRecord."""

    def test_change_record_creation(self):
        """Test change record creation."""
        record = ChangeRecord(
            field_path="income.wages",
            old_value=0,
            new_value=50000,
            change_reason="W-2 import",
        )

        assert record.field_path == "income.wages"
        assert record.old_value == 0
        assert record.new_value == 50000

    def test_change_record_summary(self):
        """Test change record summary generation."""
        record = ChangeRecord(
            field_path="wages",
            old_value=40000,
            new_value=50000,
        )

        summary = record.get_summary()
        assert "wages" in summary
        assert "40000" in summary
        assert "50000" in summary


class TestAuditService:
    """Tests for AuditService."""

    def test_singleton_instance(self):
        """Test that get_instance returns singleton."""
        AuditService.reset_instance()
        storage = InMemoryAuditStorage()

        service1 = AuditService.get_instance(storage)
        service2 = AuditService.get_instance()

        assert service1 is service2

        AuditService.reset_instance()

    def test_context_management(self, audit_service):
        """Test setting and clearing context."""
        audit_service.set_context(
            user_id="user-123",
            user_name="John Doe",
            tenant_id="tenant-456",
        )

        assert audit_service._current_context["user_id"] == "user-123"
        assert audit_service._current_context["tenant_id"] == "tenant-456"

        audit_service.clear_context()
        assert len(audit_service._current_context) == 0

    def test_log_basic_event(self, audit_service, sample_session_id):
        """Test logging a basic event."""
        entry_id = audit_service.log(
            event_type=AuditEventType.TAX_RETURN_CREATE,
            action="create",
            resource_type="tax_return",
            resource_id="return-1",
            session_id=sample_session_id,
            user_id="user-1",
        )

        assert entry_id is not None

        # Verify it was stored
        entries = audit_service.get_session_trail(sample_session_id)
        assert len(entries) == 1
        assert entries[0].entry_id == entry_id

    def test_log_tax_field_change(self, audit_service, sample_session_id):
        """Test logging tax field changes."""
        entry_id = audit_service.log_tax_field_change(
            session_id=sample_session_id,
            field_name="wages",
            old_value=0,
            new_value=50000,
            source=AuditSource.USER_INPUT,
            user_id="user-1",
        )

        entries = audit_service.get_session_trail(sample_session_id)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == AuditEventType.TAX_DATA_FIELD_CHANGE
        assert len(entry.changes) == 1
        assert entry.changes[0].field_path == "wages"
        assert entry.changes[0].old_value == 0
        assert entry.changes[0].new_value == 50000

    def test_log_income_change(self, audit_service, sample_session_id):
        """Test logging income changes."""
        entry_id = audit_service.log_income_change(
            session_id=sample_session_id,
            income_type="wages",
            old_value=0.0,
            new_value=75000.0,
            form_source="W-2",
        )

        entries = audit_service.get_session_trail(sample_session_id)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == AuditEventType.TAX_DATA_INCOME_CHANGE
        assert entry.new_value["amount"] == 75000.0

    def test_log_calculation(self, audit_service, sample_session_id):
        """Test logging tax calculations."""
        entry_id = audit_service.log_calculation(
            session_id=sample_session_id,
            calculation_type="federal_tax",
            inputs={"gross_income": 100000, "deductions": 20000},
            outputs={"taxable_income": 80000, "tax_liability": 15000},
            calculation_version="2025.1.0",
            tax_year=2025,
        )

        entries = audit_service.get_session_trail(sample_session_id)
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == AuditEventType.TAX_CALC_RUN
        assert entry.calculation_version == "2025.1.0"
        assert entry.tax_year == 2025

    def test_log_pii_access(self, audit_service):
        """Test logging PII access (compliance mandatory)."""
        entry_id = audit_service.log_pii_access(
            user_id="user-1",
            tenant_id="tenant-1",
            pii_fields=["email", "phone"],
            action="read",
            resource_type="lead",
            resource_id="lead-123",
            reason="Customer support request",
        )

        entries = audit_service._storage.query(
            event_type=AuditEventType.PII_ACCESS_READ
        )
        assert len(entries) == 1

        entry = entries[0]
        assert "email" in entry.pii_fields_accessed
        assert "phone" in entry.pii_fields_accessed
        assert entry.pii_access_reason == "Customer support request"

    def test_log_pii_access_ssn_warning(self, audit_service, caplog):
        """Test that SSN access without reason logs warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            audit_service.log_pii_access(
                user_id="user-1",
                tenant_id="tenant-1",
                pii_fields=["ssn"],
                action="read",
                resource_type="tax_return",
                resource_id="return-1",
                reason=None,  # No reason provided
            )

        assert "COMPLIANCE WARNING" in caplog.text
        assert "SSN accessed without reason" in caplog.text

    def test_log_pii_violation(self, audit_service, caplog):
        """Test logging PII violation."""
        import logging

        with caplog.at_level(logging.CRITICAL):
            audit_service.log_pii_violation(
                resource_type="lead",
                resource_id="lead-456",
                unencrypted_fields=["ssn", "email"],
                tenant_id="tenant-1",
            )

        assert "SECURITY VIOLATION" in caplog.text

        entries = audit_service._storage.query(
            event_type=AuditEventType.PII_UNENCRYPTED_DETECTED
        )
        assert len(entries) == 1
        assert entries[0].severity == AuditSeverity.CRITICAL

    def test_log_login(self, audit_service):
        """Test logging login events."""
        # Successful login
        entry_id = audit_service.log_login(
            user_id="user-1",
            user_role="cpa",
            success=True,
            ip_address="192.168.1.1",
        )

        # Failed login
        failed_id = audit_service.log_login(
            user_id="user-2",
            user_role="client",
            success=False,
            error_message="Invalid password",
        )

        # Check successful login
        entries = audit_service._storage.query(
            event_type=AuditEventType.AUTH_LOGIN
        )
        assert len(entries) == 1
        assert entries[0].success is True

        # Check failed login
        failed_entries = audit_service._storage.query(
            event_type=AuditEventType.AUTH_FAILED_LOGIN
        )
        assert len(failed_entries) == 1
        assert failed_entries[0].success is False

    def test_chain_linking(self, audit_service, sample_session_id):
        """Test that entries are linked with previous_hash."""
        # Log first entry
        audit_service.log_tax_field_change(
            session_id=sample_session_id,
            field_name="wages",
            old_value=0,
            new_value=50000,
        )

        # Log second entry
        audit_service.log_tax_field_change(
            session_id=sample_session_id,
            field_name="interest",
            old_value=0,
            new_value=1000,
        )

        entries = audit_service.get_session_trail(sample_session_id)
        assert len(entries) == 2

        # Second entry should have previous_hash
        # Entries are returned in DESC order, so [0] is the latest
        latest = entries[0]
        first = entries[1]

        assert latest.previous_hash == first.signature_hash

    def test_session_audit_report(self, audit_service, sample_session_id):
        """Test generating session audit report."""
        # Log some events
        audit_service.log_tax_field_change(
            session_id=sample_session_id,
            field_name="wages",
            old_value=0,
            new_value=50000,
        )
        audit_service.log_income_change(
            session_id=sample_session_id,
            income_type="interest",
            old_value=0,
            new_value=1000,
        )
        audit_service.log_calculation(
            session_id=sample_session_id,
            calculation_type="federal_tax",
            inputs={},
            outputs={"tax": 5000},
        )

        report = audit_service.get_session_audit_report(sample_session_id)

        assert report["session_id"] == sample_session_id
        assert report["total_events"] == 3
        assert "summary" in report
        assert "timeline" in report
        assert "generated_at" in report

    def test_pii_access_report(self, audit_service):
        """Test generating PII access report."""
        # Log some PII accesses
        audit_service.log_pii_access(
            user_id="user-1",
            tenant_id="tenant-1",
            pii_fields=["email"],
            action="read",
            resource_type="lead",
        )
        audit_service.log_pii_access(
            user_id="user-1",
            tenant_id="tenant-1",
            pii_fields=["ssn"],
            action="decrypt",
            resource_type="tax_return",
            reason="Filing preparation",
        )

        report = audit_service.get_pii_access_report(
            user_id="user-1",
            tenant_id="tenant-1",
            days=30,
        )

        assert report["total_pii_accesses"] == 2
        assert report["ssn_accesses"] == 1
        assert "user-1" in report["users"]


class TestInMemoryStorage:
    """Tests for InMemoryAuditStorage."""

    def test_save_and_get(self):
        """Test saving and retrieving entries."""
        storage = InMemoryAuditStorage()

        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
            session_id="session-1",
        )

        storage.save(entry)

        retrieved = storage.get(entry.entry_id)
        assert retrieved is not None
        assert retrieved.entry_id == entry.entry_id

    def test_query_filters(self):
        """Test query with various filters."""
        storage = InMemoryAuditStorage()

        # Add entries with different attributes
        for i in range(5):
            entry = UnifiedAuditEntry(
                event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
                session_id="session-1" if i < 3 else "session-2",
                user_id="user-1" if i % 2 == 0 else "user-2",
            )
            storage.save(entry)

        # Query by session
        session_1_entries = storage.query(session_id="session-1")
        assert len(session_1_entries) == 3

        # Query by user
        user_1_entries = storage.query(user_id="user-1")
        assert len(user_1_entries) == 3

        # Query with limit
        limited = storage.query(limit=2)
        assert len(limited) == 2

    def test_clear(self):
        """Test clearing storage."""
        storage = InMemoryAuditStorage()

        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
        )
        storage.save(entry)

        assert storage.count() == 1

        storage.clear()
        assert storage.count() == 0


class TestEventTypes:
    """Tests for AuditEventType."""

    def test_get_category(self):
        """Test getting event category."""
        assert AuditEventType.get_category(AuditEventType.AUTH_LOGIN) == "auth"
        assert AuditEventType.get_category(AuditEventType.TAX_RETURN_CREATE) == "tax"
        assert AuditEventType.get_category(AuditEventType.PII_ACCESS_READ) == "pii"

    def test_is_pii_event(self):
        """Test PII event detection."""
        assert AuditEventType.is_pii_event(AuditEventType.PII_ACCESS_READ) is True
        assert AuditEventType.is_pii_event(AuditEventType.PII_DELETION) is True
        assert AuditEventType.is_pii_event(AuditEventType.AUTH_LOGIN) is False

    def test_is_security_event(self):
        """Test security event detection."""
        assert AuditEventType.is_security_event(AuditEventType.SECURITY_SUSPICIOUS) is True
        assert AuditEventType.is_security_event(AuditEventType.AUTH_FAILED_LOGIN) is True
        assert AuditEventType.is_security_event(AuditEventType.TAX_DATA_FIELD_CHANGE) is False


class TestSeverity:
    """Tests for AuditSeverity."""

    def test_from_event_type(self):
        """Test automatic severity assignment."""
        # Critical events
        assert AuditSeverity.from_event_type(
            AuditEventType.PII_UNENCRYPTED_DETECTED
        ) == AuditSeverity.CRITICAL

        # Warning events
        assert AuditSeverity.from_event_type(
            AuditEventType.AUTH_FAILED_LOGIN
        ) == AuditSeverity.WARNING

        assert AuditSeverity.from_event_type(
            AuditEventType.PERMISSION_DENIED
        ) == AuditSeverity.WARNING

        # Info events (default)
        assert AuditSeverity.from_event_type(
            AuditEventType.TAX_DATA_FIELD_CHANGE
        ) == AuditSeverity.INFO
