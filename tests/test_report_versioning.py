"""
Tests for Report Versioning and Audit Trail System.

Prompt 6: Report Artifacts - Storage, versioning, linkage.

Tests verify:
1. Reports are versioned correctly
2. Audit trail captures all changes
3. Version chain integrity is verifiable
4. Tenant isolation is enforced
5. Version comparison works correctly
"""

import pytest
import tempfile
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestReportVersioning:
    """Tests for report version creation and retrieval."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create store instance with temp database."""
        from audit.report_versioning import ReportVersionStore
        return ReportVersionStore(db_path=temp_db)

    def test_import(self):
        """Test module can be imported."""
        from audit.report_versioning import (
            ReportVersion,
            ReportVersionStore,
            ReportType,
            ChangeType,
            get_report_version_store
        )
        assert ReportVersion is not None
        assert ReportVersionStore is not None
        assert ReportType is not None

    def test_create_report(self, store):
        """Test creating a new report."""
        from audit.report_versioning import ReportType

        version = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 11000, "status": "draft"},
            tenant_id="tenant-a",
            created_by="user@example.com",
            change_reason="Initial tax return creation"
        )

        assert version.report_id == "report-123"
        assert version.version_number == 1
        assert version.report_type == "tax_return"
        assert version.content["total_tax"] == 11000
        assert version.change_type == "created"

    def test_version_is_frozen(self, store):
        """Test that version cannot be modified."""
        from audit.report_versioning import ReportType

        version = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 11000},
        )

        # Attempt to modify should raise error (frozen dataclass)
        with pytest.raises(AttributeError):
            version.version_number = 99

    def test_update_report_creates_new_version(self, store):
        """Test updating a report creates a new version."""
        from audit.report_versioning import ReportType, ChangeType

        # Create initial version
        v1 = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 11000}
        )

        # Update report
        v2 = store.update_report(
            report_id="report-123",
            content={"total_tax": 12000},
            change_type=ChangeType.RECALCULATED,
            change_reason="Added additional income"
        )

        assert v2.version_number == 2
        assert v2.content["total_tax"] == 12000
        assert v2.previous_version_id == v1.version_id
        assert v2.change_type == "recalculated"

    def test_get_latest_version(self, store):
        """Test getting the latest version."""
        from audit.report_versioning import ReportType, ChangeType

        # Create multiple versions
        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"version": 1}
        )

        store.update_report(
            report_id="report-123",
            content={"version": 2},
            change_type=ChangeType.UPDATED
        )

        store.update_report(
            report_id="report-123",
            content={"version": 3},
            change_type=ChangeType.UPDATED
        )

        latest = store.get_latest_version("report-123")

        assert latest.version_number == 3
        assert latest.content["version"] == 3

    def test_get_version_history(self, store):
        """Test getting complete version history."""
        from audit.report_versioning import ReportType, ChangeType

        # Create versions
        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 10000}
        )

        store.update_report(
            report_id="report-123",
            content={"total_tax": 11000},
            change_type=ChangeType.UPDATED
        )

        store.update_report(
            report_id="report-123",
            content={"total_tax": 12000},
            change_type=ChangeType.FINALIZED
        )

        history = store.get_version_history("report-123")

        assert len(history) == 3
        assert history[0].version_number == 1
        assert history[1].version_number == 2
        assert history[2].version_number == 3


class TestAuditTrail:
    """Tests for audit trail functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create store instance with temp database."""
        from audit.report_versioning import ReportVersionStore
        return ReportVersionStore(db_path=temp_db)

    def test_audit_trail_recorded_on_create(self, store):
        """Test audit entry recorded when report created."""
        from audit.report_versioning import ReportType

        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 11000},
            user_id="user@example.com",
            ip_address="192.168.1.1"
        )

        audit = store.get_audit_trail("report-123")

        assert len(audit) == 1
        assert audit[0].action == "report_created"
        assert audit[0].user_id == "user@example.com"
        assert audit[0].ip_address == "192.168.1.1"

    def test_audit_trail_recorded_on_update(self, store):
        """Test audit entries recorded for all changes."""
        from audit.report_versioning import ReportType, ChangeType

        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 11000}
        )

        store.update_report(
            report_id="report-123",
            content={"total_tax": 12000},
            change_type=ChangeType.CORRECTED,
            change_reason="Fixed calculation error",
            user_id="admin@example.com"
        )

        audit = store.get_audit_trail("report-123")

        assert len(audit) == 2
        # Most recent first
        assert audit[0].action == "report_corrected"
        assert "correction" in audit[0].details.get("change_reason", "").lower() or \
               "Fixed" in audit[0].details.get("change_reason", "")

    def test_audit_trail_includes_details(self, store):
        """Test audit entries include change details."""
        from audit.report_versioning import ReportType

        store.create_report(
            report_id="report-123",
            report_type=ReportType.RECOMMENDATION_REPORT,
            content={"recommendations": []},
            change_reason="Generated recommendations"
        )

        audit = store.get_audit_trail("report-123")

        assert len(audit) == 1
        assert audit[0].details.get("report_type") == "recommendation_report"
        assert audit[0].details.get("change_reason") == "Generated recommendations"


class TestIntegrityVerification:
    """Tests for version chain integrity verification."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create store instance with temp database."""
        from audit.report_versioning import ReportVersionStore
        return ReportVersionStore(db_path=temp_db)

    def test_version_integrity_hash_valid(self, store):
        """Test version integrity hash can be verified."""
        from audit.report_versioning import ReportType

        version = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 11000}
        )

        assert version.verify_integrity() is True

    def test_chain_integrity_valid(self, store):
        """Test chain integrity verification passes for valid chain."""
        from audit.report_versioning import ReportType, ChangeType

        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"version": 1}
        )

        store.update_report(
            report_id="report-123",
            content={"version": 2},
            change_type=ChangeType.UPDATED
        )

        store.update_report(
            report_id="report-123",
            content={"version": 3},
            change_type=ChangeType.UPDATED
        )

        valid, errors = store.verify_chain_integrity("report-123")

        assert valid is True
        assert len(errors) == 0

    def test_content_hash_deterministic(self):
        """Test content hash is deterministic."""
        from audit.report_versioning import compute_content_hash

        content = {"a": 1, "b": 2, "c": {"nested": "value"}}

        hashes = [compute_content_hash(content) for _ in range(100)]

        assert all(h == hashes[0] for h in hashes)

    def test_content_hash_key_order_independent(self):
        """Test content hash is independent of key order."""
        from audit.report_versioning import compute_content_hash

        content1 = {"a": 1, "b": 2, "c": 3}
        content2 = {"c": 3, "a": 1, "b": 2}

        assert compute_content_hash(content1) == compute_content_hash(content2)


class TestTenantIsolation:
    """Tests for tenant isolation in report versioning."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create store instance with temp database."""
        from audit.report_versioning import ReportVersionStore
        return ReportVersionStore(db_path=temp_db)

    def test_reports_isolated_by_tenant(self, store):
        """Test reports are isolated by tenant."""
        from audit.report_versioning import ReportType

        # Create same report_id for different tenants
        v_a = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"tenant": "A"},
            tenant_id="tenant-a"
        )

        v_b = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"tenant": "B"},
            tenant_id="tenant-b"
        )

        # Get latest for each tenant
        latest_a = store.get_latest_version("report-123", tenant_id="tenant-a")
        latest_b = store.get_latest_version("report-123", tenant_id="tenant-b")

        assert latest_a.content["tenant"] == "A"
        assert latest_b.content["tenant"] == "B"
        assert latest_a.version_id != latest_b.version_id

    def test_version_history_tenant_isolated(self, store):
        """Test version history is tenant-isolated."""
        from audit.report_versioning import ReportType, ChangeType

        # Create versions for tenant A
        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"version": 1},
            tenant_id="tenant-a"
        )
        store.update_report(
            report_id="report-123",
            content={"version": 2},
            tenant_id="tenant-a",
            change_type=ChangeType.UPDATED
        )

        # Create version for tenant B
        store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"version": 1},
            tenant_id="tenant-b"
        )

        # Check histories are separate
        history_a = store.get_version_history("report-123", tenant_id="tenant-a")
        history_b = store.get_version_history("report-123", tenant_id="tenant-b")

        assert len(history_a) == 2
        assert len(history_b) == 1


class TestVersionComparison:
    """Tests for version comparison functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create store instance with temp database."""
        from audit.report_versioning import ReportVersionStore
        return ReportVersionStore(db_path=temp_db)

    def test_compare_versions_detects_changes(self, store):
        """Test version comparison detects changes."""
        from audit.report_versioning import ReportType, ChangeType

        v1 = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 10000, "status": "draft"}
        )

        v2 = store.update_report(
            report_id="report-123",
            content={"total_tax": 12000, "status": "draft"},
            change_type=ChangeType.RECALCULATED
        )

        comparison = store.compare_versions(v1.version_id, v2.version_id)

        assert comparison["has_changes"] is True
        assert len(comparison["changes"]) == 1
        assert comparison["changes"][0]["path"] == "total_tax"
        assert comparison["changes"][0]["old_value"] == 10000
        assert comparison["changes"][0]["new_value"] == 12000

    def test_compare_versions_detects_added_fields(self, store):
        """Test version comparison detects added fields."""
        from audit.report_versioning import ReportType, ChangeType

        v1 = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 10000}
        )

        v2 = store.update_report(
            report_id="report-123",
            content={"total_tax": 10000, "refund": 500},
            change_type=ChangeType.UPDATED
        )

        comparison = store.compare_versions(v1.version_id, v2.version_id)

        assert comparison["has_changes"] is True
        added = [c for c in comparison["changes"] if c["type"] == "added"]
        assert len(added) == 1
        assert added[0]["path"] == "refund"

    def test_compare_versions_detects_removed_fields(self, store):
        """Test version comparison detects removed fields."""
        from audit.report_versioning import ReportType, ChangeType

        v1 = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 10000, "temp_field": "value"}
        )

        v2 = store.update_report(
            report_id="report-123",
            content={"total_tax": 10000},
            change_type=ChangeType.UPDATED
        )

        comparison = store.compare_versions(v1.version_id, v2.version_id)

        removed = [c for c in comparison["changes"] if c["type"] == "removed"]
        assert len(removed) == 1
        assert removed[0]["path"] == "temp_field"

    def test_compare_identical_versions(self, store):
        """Test comparing identical versions shows no changes."""
        from audit.report_versioning import ReportType

        v1 = store.create_report(
            report_id="report-123",
            report_type=ReportType.TAX_RETURN,
            content={"total_tax": 10000}
        )

        comparison = store.compare_versions(v1.version_id, v1.version_id)

        assert comparison["has_changes"] is False
        assert len(comparison["changes"]) == 0


class TestSnapshotLinkage:
    """Tests for linking reports to calculation snapshots."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create store instance with temp database."""
        from audit.report_versioning import ReportVersionStore
        return ReportVersionStore(db_path=temp_db)

    def test_report_linked_to_snapshot(self, store):
        """Test report can be linked to calculation snapshot."""
        from audit.report_versioning import ReportType

        version = store.create_report(
            report_id="report-123",
            report_type=ReportType.CALCULATION_BREAKDOWN,
            content={"total_tax": 11000},
            snapshot_id="snapshot-abc-123"
        )

        assert version.snapshot_id == "snapshot-abc-123"

    def test_version_update_with_new_snapshot(self, store):
        """Test version update can reference new snapshot."""
        from audit.report_versioning import ReportType, ChangeType

        store.create_report(
            report_id="report-123",
            report_type=ReportType.CALCULATION_BREAKDOWN,
            content={"total_tax": 10000},
            snapshot_id="snapshot-1"
        )

        v2 = store.update_report(
            report_id="report-123",
            content={"total_tax": 11000},
            change_type=ChangeType.RECALCULATED,
            snapshot_id="snapshot-2"
        )

        assert v2.snapshot_id == "snapshot-2"
